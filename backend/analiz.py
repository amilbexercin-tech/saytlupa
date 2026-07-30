"""Analiz xidməti — toplayıcıları, crawler-i və bazanı bir yerə gətirir.

Ağır iş fonda gedir; brauzer gedişatı SSE ilə izləyir (`hadise` modulu).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from . import chains, crawler, db, hadise, rag
from .collectors import butun_analiz
from .collectors.base import domen as domen_cixart
from .config import ayarlar

log = logging.getLogger("saytlupa")


# --------------------------------------------------------------- baza işləri


def _sayt_tap_ve_ya_yarat(sessiya: db.Session, url: str) -> db.Sayt:
    ad = domen_cixart(url)
    sayt = sessiya.query(db.Sayt).filter(db.Sayt.domain == ad).first()
    if sayt:
        sayt.son_analiz = datetime.now(timezone.utc)
        sayt.url = url
    else:
        sayt = db.Sayt(url=url, domain=ad)
        sessiya.add(sayt)
    sessiya.commit()
    return sayt


def yeni_analiz(url: str) -> tuple[int, int]:
    """Sayt və analiz sətirlərini yaradır → (site_id, analiz_id)."""
    with db.sessiya() as s:
        sayt = _sayt_tap_ve_ya_yarat(s, url)
        analiz = db.Analiz(site_id=sayt.id, status="gozleyir")
        s.add(analiz)
        s.commit()
        return sayt.id, analiz.id


def _status_yaz(analiz_id: int, status: str, xeta: str = "") -> None:
    with db.sessiya() as s:
        analiz = s.get(db.Analiz, analiz_id)
        if analiz:
            analiz.status = status
            analiz.xeta = xeta[:2000]
            s.commit()


def _netice_yaz(analiz_id: int, xam: dict) -> None:
    with db.sessiya() as s:
        analiz = s.get(db.Analiz, analiz_id)
        if analiz:
            analiz.xam_json = xam
            s.commit()


def _hesabat_yaz(analiz_id: int, hesabat: dict | None) -> None:
    with db.sessiya() as s:
        analiz = s.get(db.Analiz, analiz_id)
        if analiz:
            analiz.ai_hesabat = hesabat or {}
            s.commit()


def sehifeleri_yaz(site_id: int, sehifeler: list[dict]) -> int:
    """Səhifələri yazır; eyni URL varsa yeniləyir (təkrar analizdə vacibdir).

    `izleme` modulu da bunu çağırır — ona görə açıqdır.
    """
    with db.sessiya() as s:
        movcud = {
            p.url: p
            for p in s.query(db.Sehife).filter(db.Sehife.site_id == site_id).all()
        }
        for qeyd in sehifeler:
            kohne = movcud.get(qeyd["url"])
            if kohne:
                kohne.basliq = qeyd["basliq"]
                kohne.metn = qeyd["metn"]
                kohne.hash = qeyd["hash"]
                kohne.yigilma_tarixi = datetime.now(timezone.utc)
            else:
                # Yalnız cədvəldə olan sahələr yazılır: crawler qeydə əlavə
                # sahələr (məsələn `elaqe`) qoyur, onlar bazaya getməməlidir.
                s.add(
                    db.Sehife(
                        site_id=site_id,
                        url=qeyd["url"],
                        basliq=qeyd["basliq"],
                        metn=qeyd["metn"],
                        hash=qeyd["hash"],
                    )
                )
        s.commit()
        return s.query(db.Sehife).filter(db.Sehife.site_id == site_id).count()


def elaqe_birlesdir(xam: dict, sehifeler: list[dict]) -> dict:
    """Gəzilən səhifələrdən toplanan əlaqə məlumatını analizə əlavə edir.

    Ana səhifədə sosial link olmaya bilər — çox saytda onlar `/elaqe`
    səhifəsində və ya daxili səhifələrin altlığındadır. Burada hamısı
    birləşdirilir; ilk tapılan üstün tutulur, təkrarlar atılır.

    Nəticə `sehife` toplayıcısının məlumatına yazılır ki, PDF, klon sənədləri
    və AI hesabatı da avtomatik faydalansın.
    """
    sehife_netice = (xam.get("neticeler") or {}).get("sehife") or {}
    data = sehife_netice.get("data") or {}

    sosial = dict(data.get("sosial_linkler") or {})
    epostalar = list(data.get("epostalar") or [])
    telefonlar = list(data.get("telefonlar") or [])
    menbeler: dict[str, str] = {}

    for qeyd in sehifeler:
        elaqe = qeyd.get("elaqe") or {}
        for ad, link in (elaqe.get("sosial_linkler") or {}).items():
            if ad not in sosial:
                sosial[ad] = link
                menbeler[ad] = qeyd["url"]
        for eposta in elaqe.get("epostalar") or []:
            if eposta not in epostalar and len(epostalar) < 8:
                epostalar.append(eposta)
        for telefon in elaqe.get("telefonlar") or []:
            if telefon not in telefonlar and len(telefonlar) < 8:
                telefonlar.append(telefon)

    data["sosial_linkler"] = sosial
    data["epostalar"] = epostalar
    data["telefonlar"] = telefonlar
    # Hansı məlumat ana səhifədən kənarda tapılıb — şəffaflıq üçün
    data["elaqe_menbeleri"] = menbeler
    sehife_netice["data"] = data
    return xam


# --------------------------------------------------------------- əsas axın


async def isle(analiz_id: int, site_id: int, url: str, max_sehife: int) -> dict:
    """Tam analizi icra edir. Xəta olsa status 'xeta' kimi yazılır."""
    await asyncio.to_thread(_status_yaz, analiz_id, "isleyir")
    hadise.gonder(analiz_id, "basladi", url=url)

    try:
        # 1) Toplayıcılar
        def toplayici_xeber(ad: str, veziyyet: str) -> None:
            hadise.gonder(analiz_id, "toplayici", ad=ad, veziyyet=veziyyet)

        netice = await butun_analiz(url, xeber=toplayici_xeber)

        if not netice["ugurlu"]:
            await asyncio.to_thread(_status_yaz, analiz_id, "xeta", netice["xeta"])
            hadise.gonder(analiz_id, "xeta", mesaj=netice["xeta"])
            hadise.bitir(analiz_id)
            return netice

        # HTML böyükdür — bazaya yazmırıq, yalnız nəticələri saxlayırıq
        xam = {
            "url": netice["url"],
            "status_kodu": netice["status_kodu"],
            "yuklenme_saniye": netice["yuklenme_saniye"],
            "qoruma": netice["qoruma"],
            "neticeler": netice["neticeler"],
            "ugurlu_toplayici": netice["ugurlu_toplayici"],
            "umumi_toplayici": netice["umumi_toplayici"],
        }
        await asyncio.to_thread(_netice_yaz, analiz_id, xam)
        hadise.gonder(
            analiz_id, "toplayicilar_bitdi",
            ugurlu=netice["ugurlu_toplayici"], umumi=netice["umumi_toplayici"],
        )

        # 2) Səhifə gəzişi — bot qoruması varsa mənasızdır
        if netice["qoruma"]["qorunur"]:
            hadise.gonder(
                analiz_id, "gezis_atlandi",
                sebeb=netice["qoruma"]["qeyd"] or "Sayt bot qoruması arxasındadır",
            )
            sehife_sayi = 0
        else:
            hadise.gonder(analiz_id, "gezis_basladi", hedef=max_sehife)

            def gezis_xeber(yigilan: int, hedef: int, sehife_url: str) -> None:
                hadise.gonder(
                    analiz_id, "sehife", yigilan=yigilan, hedef=hedef, url=sehife_url
                )

            sehifeler = await crawler.gez(
                url, max_sehife=max_sehife, xeber=gezis_xeber
            )
            sehife_sayi = await asyncio.to_thread(
                sehifeleri_yaz, site_id, sehifeler
            )
            hadise.gonder(analiz_id, "gezis_bitdi", sehife_sayi=sehife_sayi)

            # Sosial link və əlaqə bütün gəzilən səhifələrdən toplanır
            elaqe_birlesdir(xam, sehifeler)

            # 3) RAG indeksi — parçalama, vektorlaşdırma, saxlama
            hadise.gonder(analiz_id, "rag_basladi", sehife_sayi=sehife_sayi)

            def rag_xeber(sira: int, umumi: int, chunk: int) -> None:
                hadise.gonder(
                    analiz_id, "rag", sehife=sira, umumi=umumi, chunk=chunk
                )

            rag_netice = await asyncio.to_thread(rag.qur, site_id, xeber=rag_xeber)
            xam["rag"] = rag_netice
            hadise.gonder(analiz_id, "rag_bitdi", **rag_netice)

        xam["sehife_sayi"] = sehife_sayi
        await asyncio.to_thread(_netice_yaz, analiz_id, xam)

        # 4) AI hesabat — LCEL zənciri (xam analiz → 6 bəndlik rəy)
        hadise.gonder(analiz_id, "hesabat_basladi")
        hesabat_netice = await asyncio.to_thread(chains.hesabat.yarat, url, xam)
        await asyncio.to_thread(_hesabat_yaz, analiz_id, hesabat_netice["hesabat"])
        xam["hesabat_olcme"] = hesabat_netice["olcme"]
        await asyncio.to_thread(_netice_yaz, analiz_id, xam)
        hadise.gonder(
            analiz_id,
            "hesabat_bitdi",
            ugurlu=hesabat_netice["olcme"]["ugurlu"],
            model=hesabat_netice["olcme"]["model"],
            saniye=hesabat_netice["olcme"]["saniye"],
            sebeb=hesabat_netice["olcme"].get("sebeb", ""),
        )

        await asyncio.to_thread(_status_yaz, analiz_id, "hazir")
        hadise.gonder(analiz_id, "hazir", sehife_sayi=sehife_sayi)
        return netice

    except Exception as xeta:  # gözlənilməz xəta analizi yarımçıq qoymasın
        log.exception("Analiz %s sındı", analiz_id)
        await asyncio.to_thread(_status_yaz, analiz_id, "xeta", str(xeta))
        hadise.gonder(analiz_id, "xeta", mesaj=str(xeta))
        return {"ugurlu": False, "xeta": str(xeta)}
    finally:
        hadise.bitir(analiz_id)


def basla(url: str, max_sehife: int | None = None) -> dict:
    """Analizi fonda başladır və identifikatorları qaytarır."""
    site_id, analiz_id = yeni_analiz(url)
    hadise.novbe(analiz_id)  # SSE qoşulana qədər hadisələr itməsin
    asyncio.create_task(
        isle(analiz_id, site_id, url, max_sehife or ayarlar.max_pages)
    )
    return {"analiz_id": analiz_id, "site_id": site_id, "url": url}


# --------------------------------------------------------------- oxuma


def analiz_oxu(analiz_id: int) -> dict | None:
    with db.sessiya() as s:
        analiz = s.get(db.Analiz, analiz_id)
        if not analiz:
            return None
        sayt = s.get(db.Sayt, analiz.site_id)
        sehife_sayi = (
            s.query(db.Sehife).filter(db.Sehife.site_id == analiz.site_id).count()
        )
        return {
            "id": analiz.id,
            "site_id": analiz.site_id,
            "url": sayt.url if sayt else "",
            "domain": sayt.domain if sayt else "",
            "status": analiz.status,
            "tarix": analiz.tarix,
            "xeta": analiz.xeta or "",
            "xam": analiz.xam_json or {},
            "ai_hesabat": analiz.ai_hesabat or None,
            "sehife_sayi": sehife_sayi,
            "chunk_sayi": rag.store.chunk_sayi(analiz.site_id),
        }


def saytlar() -> list[dict]:
    with db.sessiya() as s:
        return [
            {
                "id": sayt.id,
                "url": sayt.url,
                "domain": sayt.domain,
                "son_analiz": sayt.son_analiz,
                "izlenir": sayt.izlenir,
            }
            for sayt in s.query(db.Sayt).order_by(db.Sayt.son_analiz.desc()).limit(50)
        ]
