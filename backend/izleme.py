"""Sayt izləmə — n8n cron workflow-unun Python tərəfi (Gün 10).

Sərhəd qaydası: n8n yalnız **nə vaxt** yoxlanacağını və **kimə** xəbər
gedəcəyini bilir. Dəyişikliyin nə olduğunu bu modul hesablayır.

Müqayisə səhifə mətninin barmaq izi (`metn.barmaq_izi`) üzərində aparılır:
səhifə yenidən yığılır, köhnə hash-larla tutuşdurulur, yalnız bundan **sonra**
baza yenilənir.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from . import analiz, crawler, db, rag
from .config import ayarlar

log = logging.getLogger("saytlupa")


# --------------------------------------------------------------- oxuma


def _qeyd(iz: db.Izleme, sayt: db.Sayt | None) -> dict:
    return {
        "id": iz.id,
        "site_id": iz.site_id,
        "url": sayt.url if sayt else "",
        "domain": sayt.domain if sayt else "",
        "cron": iz.cron,
        "son_yoxlama": iz.son_yoxlama,
        "son_deyisiklik": iz.son_deyisiklik or "",
        "telegram_chat_id": iz.telegram_chat_id or ayarlar.telegram_chat_id,
    }


def siyahi(min_saat: int = 0) -> list[dict]:
    """İzlənən saytlar.

    `min_saat` verilsə, son `min_saat` saat ərzində artıq yoxlanmış saytlar
    siyahıya düşmür — n8n cron-u tez-tez işə düşsə də sayt iki dəfə gəzilmir.
    """
    hedd = datetime.now(timezone.utc) - timedelta(hours=min_saat)
    with db.sessiya() as s:
        neticeler = []
        for iz in s.query(db.Izleme).order_by(db.Izleme.id):
            if min_saat and iz.son_yoxlama:
                son = iz.son_yoxlama
                if son.tzinfo is None:  # SQLite tarixi saat qurşağı saxlamır
                    son = son.replace(tzinfo=timezone.utc)
                if son > hedd:
                    continue
            neticeler.append(_qeyd(iz, s.get(db.Sayt, iz.site_id)))
        return neticeler


# --------------------------------------------------------------- yazma


def elave_et(site_id: int, cron: str = "0 9 * * *", telegram_chat_id: str = "") -> dict:
    """İzləməni açır (varsa parametrlərini yeniləyir)."""
    with db.sessiya() as s:
        sayt = s.get(db.Sayt, site_id)
        if sayt is None:
            return {"tapilmadi": True}

        iz = s.query(db.Izleme).filter(db.Izleme.site_id == site_id).first()
        if iz is None:
            iz = db.Izleme(site_id=site_id)
            s.add(iz)
        iz.cron = cron
        iz.telegram_chat_id = telegram_chat_id
        sayt.izlenir = True
        s.commit()
        return _qeyd(iz, sayt)


def sil(site_id: int) -> bool:
    """İzləməni bağlayır."""
    with db.sessiya() as s:
        iz = s.query(db.Izleme).filter(db.Izleme.site_id == site_id).first()
        if iz is None:
            return False
        s.delete(iz)
        sayt = s.get(db.Sayt, site_id)
        if sayt:
            sayt.izlenir = False
        s.commit()
        return True


def _hashlar(site_id: int) -> dict[str, str]:
    with db.sessiya() as s:
        return {
            p.url: (p.hash or "")
            for p in s.query(db.Sehife).filter(db.Sehife.site_id == site_id)
        }


def _xulase(yeni: list[str], deyisen: list[str], silinen: list[str]) -> str:
    hisseler = []
    if yeni:
        hisseler.append(f"{len(yeni)} yeni səhifə")
    if deyisen:
        hisseler.append(f"{len(deyisen)} dəyişən səhifə")
    if silinen:
        hisseler.append(f"{len(silinen)} səhifə yoxa çıxıb")
    return ", ".join(hisseler) if hisseler else "dəyişiklik yoxdur"


def _yoxlama_yaz(site_id: int, xulase: str, deyisdi: bool) -> None:
    with db.sessiya() as s:
        iz = s.query(db.Izleme).filter(db.Izleme.site_id == site_id).first()
        if iz is None:
            return
        iz.son_yoxlama = datetime.now(timezone.utc)
        if deyisdi:
            iz.son_deyisiklik = xulase[:2000]
        s.commit()


async def yoxla(site_id: int, rag_yenile: bool = True) -> dict:
    """Saytı yenidən gəzir, köhnə barmaq izləri ilə müqayisə edir.

    Dəyişiklik varsa RAG indeksi də yenilənir — köhnə mətn üzərində qurulmuş
    indekslə söhbət etmək istifadəçini yanıldar.
    """
    with db.sessiya() as s:
        sayt = s.get(db.Sayt, site_id)
        if sayt is None:
            return {"tapilmadi": True}
        url, domain = sayt.url, sayt.domain

    kohne = await asyncio.to_thread(_hashlar, site_id)
    hedef = ayarlar.max_pages
    sehifeler = await crawler.gez(url, max_sehife=hedef)
    yeni_hash = {p["url"]: p["hash"] for p in sehifeler}

    if not sehifeler:
        # Sayt açılmadı və ya robots.txt icazə vermir — bunu "hər şey silinib"
        # kimi başa düşmək və xəbərdarlıq göndərmək yanlış olardı.
        await asyncio.to_thread(_yoxlama_yaz, site_id, "sayt gəzilə bilmədi", False)
        return {
            "site_id": site_id, "url": url, "domain": domain,
            "deyisdi": False, "yeni": [], "deyisen": [], "silinen": [],
            "yoxlanan_sehife": 0, "limite_catdi": False,
            "xulase": "sayt gəzilə bilmədi",
            "qeyd": "Səhifə yığılmadı — sayt bağlıdır və ya robots.txt qadağan edir",
            "telegram_chat_id": _telegram_id(site_id),
        }

    # Gəziş limitə dayanıbsa görünməyən səhifə "silinib" sayıla bilməz — sadəcə
    # ona növbə çatmayıb. Belə halda yalnız yeni və dəyişən səhifələr sayılır.
    limite_catdi = len(sehifeler) >= hedef

    yeni = sorted(set(yeni_hash) - set(kohne))
    silinen = [] if limite_catdi else sorted(set(kohne) - set(yeni_hash))
    deyisen = sorted(
        u for u, h in yeni_hash.items() if u in kohne and kohne[u] and kohne[u] != h
    )
    deyisdi = bool(yeni or deyisen or silinen)

    await asyncio.to_thread(analiz.sehifeleri_yaz, site_id, sehifeler)
    # Yoxa çıxanlar bazadan da silinir — yoxsa eyni xəbər hər yoxlamada təkrarlanır
    if silinen:
        await asyncio.to_thread(analiz.sehifeleri_sil, site_id, silinen)
    if deyisdi and rag_yenile:
        await asyncio.to_thread(rag.qur, site_id)

    xulase = _xulase(yeni, deyisen, silinen)
    await asyncio.to_thread(_yoxlama_yaz, site_id, xulase, deyisdi)
    log.info("İzləmə %s (%s): %s", site_id, domain, xulase)

    return {
        "site_id": site_id,
        "url": url,
        "domain": domain,
        "deyisdi": deyisdi,
        "yeni": yeni[:20],
        "deyisen": deyisen[:20],
        "silinen": silinen[:20],
        "yoxlanan_sehife": len(sehifeler),
        # Limitə çatıbsa silinmə hesablanmayıb — nəticəni oxuyan bunu bilməlidir
        "limite_catdi": limite_catdi,
        "xulase": xulase,
        "yoxlama_tarixi": datetime.now(timezone.utc).isoformat(),
        "telegram_chat_id": _telegram_id(site_id),
    }


def _telegram_id(site_id: int) -> str:
    with db.sessiya() as s:
        iz = s.query(db.Izleme).filter(db.Izleme.site_id == site_id).first()
        return (iz.telegram_chat_id if iz else "") or ayarlar.telegram_chat_id


# --------------------------------------------------------------- iş xətaları


def xeta_yaz(menbe: str, workflow: str, xeta_metni: str) -> dict:
    """n8n Error Workflow buraya yazır."""
    with db.sessiya() as s:
        qeyd = db.IsXetasi(
            menbe=menbe[:100], workflow=workflow[:200], xeta_metni=xeta_metni[:5000]
        )
        s.add(qeyd)
        s.commit()
        return {"id": qeyd.id, "tarix": qeyd.tarix}


def xetalar(limit: int = 50) -> list[dict]:
    with db.sessiya() as s:
        return [
            {
                "id": x.id,
                "menbe": x.menbe,
                "workflow": x.workflow,
                "xeta_metni": x.xeta_metni,
                "tarix": x.tarix,
            }
            for x in s.query(db.IsXetasi)
            .order_by(db.IsXetasi.id.desc())
            .limit(min(limit, 200))
        ]
