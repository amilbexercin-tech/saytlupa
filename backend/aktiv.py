"""Aktiv (dərin) skan işlərinin idarəsi — job növbəsi, gedişat, nəticə.

Axın: brauzer iş yaradır (`yeni_skan`) → öz kompüterindəki worker növbədən
götürür (`novbeden_goturt`) → nuclei işlədir → gedişat və nəticə göndərir
(`gedisat_yaz`, `netice_yaz`). Brauzer SSE ilə canlı izləyir.

Sahiblik **burada** yoxlanır (iş yaradılanda) və **worker-də** təkrar — aktiv
skan yalnız təsdiqlənmiş domendə işləyir.
"""

from __future__ import annotations

from . import db, hadise, sahiblik
from .collectors import tehlukesizlik

# hadisə brokeri analizlə ortaqdır; toqquşma olmasın deyə aktiv işlərin id-si
# bu qədər sürüşdürülür (analiz id-ləri bu həddə çatmır).
HADISE_OFFSET = 900_000_000


def _hid(job_id: int) -> int:
    return HADISE_OFFSET + job_id


class TesdiqYoxdur(Exception):
    """Domen təsdiqlənməyib — aktiv skan qadağandır."""


def yeni_skan(url: str) -> dict:
    """İş yaradır (yalnız təsdiqli domendə). → {job_id, domain}."""
    domain = sahiblik._normalize(url)
    if not sahiblik.domen_tesdiqlidir(url):
        raise TesdiqYoxdur(
            f"«{domain}» təsdiqlənməyib. Aktiv skan yalnız sahibi olduğun "
            "domendə mümkündür — əvvəlcə domeni təsdiqlə."
        )
    with db.sessiya() as s:
        skan = db.AktivSkan(domain=domain, target_url=url, status="gozleyir")
        s.add(skan)
        s.commit()
        return {"job_id": skan.id, "domain": domain}


def novbeden_goturt() -> dict | None:
    """Ən köhnə `gozleyir` işi atomik olaraq `isleyir`-ə keçirir və qaytarır.

    Worker bunu çağırır. Bir anda yalnız bir worker eyni işi götürsün deyə
    dəyişiklik tək sessiyada, tək commit-lə edilir.
    """
    with db.sessiya() as s:
        skan = (
            s.query(db.AktivSkan)
            .filter(db.AktivSkan.status == "gozleyir")
            .order_by(db.AktivSkan.id.asc())
            .first()
        )
        if not skan:
            return None
        skan.status = "isleyir"
        skan.baslama = db.indi()
        s.commit()
        return {"job_id": skan.id, "target_url": skan.target_url, "domain": skan.domain}


def gedisat_yaz(job_id: int, mesaj: str, faiz: int | None = None) -> None:
    """Gedişatı bazaya yazır və SSE-yə ötürür."""
    with db.sessiya() as s:
        skan = s.get(db.AktivSkan, job_id)
        if skan:
            skan.gedisat = mesaj[:500]
            s.commit()
    hadise.gonder(_hid(job_id), "gedisat", mesaj=mesaj, faiz=faiz)


def netice_yaz(job_id: int, tapintilar: list[dict]) -> dict:
    """Tapıntıları saxlayır, balı hesablayır (passivdəki eyni düstur), işi bitirir."""
    hesab = tehlukesizlik.hesabla(list(tapintilar))
    with db.sessiya() as s:
        skan = s.get(db.AktivSkan, job_id)
        if skan and skan.status != "dayandirildi":
            skan.tapintilar = hesab["tapintilar"]
            skan.bal = hesab["bal"]
            skan.herf = hesab["herf"]
            skan.status = "bitdi"
            skan.bitme = db.indi()
            s.commit()
    hadise.gonder(_hid(job_id), "hazir", bal=hesab["bal"], herf=hesab["herf"],
                  sayi=hesab["sayi"])
    hadise.bitir(_hid(job_id))
    return hesab


def xeta_yaz(job_id: int, mesaj: str) -> None:
    with db.sessiya() as s:
        skan = s.get(db.AktivSkan, job_id)
        if skan:
            skan.status = "xeta"
            skan.xeta = mesaj[:2000]
            skan.bitme = db.indi()
            s.commit()
    hadise.gonder(_hid(job_id), "xeta", mesaj=mesaj)
    hadise.bitir(_hid(job_id))


def dayandir(job_id: int) -> bool:
    with db.sessiya() as s:
        skan = s.get(db.AktivSkan, job_id)
        if not skan or skan.status in ("bitdi", "xeta"):
            return False
        skan.status = "dayandirildi"
        skan.bitme = db.indi()
        s.commit()
    hadise.gonder(_hid(job_id), "xeta", mesaj="Skan istifadəçi tərəfindən dayandırıldı.")
    hadise.bitir(_hid(job_id))
    return True


def dayandirilibmi(job_id: int) -> bool:
    """Worker skan gedərkən bunu yoxlayır — dayandırılıbsa nuclei-ni kəsir."""
    with db.sessiya() as s:
        skan = s.get(db.AktivSkan, job_id)
        return bool(skan and skan.status == "dayandirildi")


def oxu(job_id: int) -> dict | None:
    with db.sessiya() as s:
        skan = s.get(db.AktivSkan, job_id)
        if not skan:
            return None
        return {
            "job_id": skan.id,
            "domain": skan.domain,
            "url": skan.target_url,
            "status": skan.status,
            "tapintilar": skan.tapintilar or [],
            "bal": skan.bal,
            "herf": skan.herf or "",
            "gedisat": skan.gedisat or "",
            "xeta": skan.xeta or "",
        }
