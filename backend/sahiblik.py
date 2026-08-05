"""Domen sahibliyinin təsdiqi — aktiv skan üçün ön şərt.

Aktiv skan real payload göndərir, ona görə **yalnız sahibi olduğun** domenə
icazə verilir. Sahiblik iki üsulla sübut olunur:

- **DNS TXT:** domenin TXT qeydinə `saytlupa-verify=<token>` yazılır;
- **fayl:** `http(s)://domen/.well-known/saytlupa-verify.txt` faylına token qoyulur.

`.env`-dəki `OWNED_DOMAINS` allowlist-i öz domenlərindir — onlar avtomatik
təsdiqli sayılır (DNS/fayl tələb olunmur).

Prinsip: təsdiq **həm burada, həm də worker-də** yoxlanır (müdafiə dərinliyi).
"""

from __future__ import annotations

import secrets

import dns.resolver
import httpx

from . import db
from .collectors.base import domen as domen_cixart
from .config import ayarlar

TXT_ACAR = "saytlupa-verify="
FAYL_YOLU = "/.well-known/saytlupa-verify.txt"


def owned_allowlist() -> set[str]:
    """`.env`-dəki OWNED_DOMAINS — vergüllə ayrılmış öz domenlərin."""
    xam = getattr(ayarlar, "owned_domains", "") or ""
    return {d.strip().lower() for d in xam.split(",") if d.strip()}


def _normalize(deyer: str) -> str:
    """URL və ya domen → təmiz kök domen (magaza.az)."""
    deyer = (deyer or "").strip().lower()
    if "://" in deyer or "/" in deyer:
        return domen_cixart(deyer)
    return domen_cixart("http://" + deyer)


def domen_tesdiqlidir(deyer: str) -> bool:
    """Domen skana hazırdır? (allowlist və ya bazada `tesdiqli`)."""
    domain = _normalize(deyer)
    if not domain:
        return False
    if domain in owned_allowlist():
        return True
    with db.sessiya() as s:
        qeyd = (
            s.query(db.TesdiqDomen)
            .filter(db.TesdiqDomen.domain == domain,
                    db.TesdiqDomen.status == "tesdiqli")
            .first()
        )
        return qeyd is not None


def token_yarat(deyer: str, usul: str = "dns") -> dict:
    """Domen üçün təsdiq token-i yaradır (varsa təkrar istifadə) və təlimat qaytarır."""
    domain = _normalize(deyer)
    if not domain:
        raise ValueError("Domen tanınmadı")

    with db.sessiya() as s:
        qeyd = (
            s.query(db.TesdiqDomen)
            .filter(db.TesdiqDomen.domain == domain)
            .order_by(db.TesdiqDomen.id.desc())
            .first()
        )
        if qeyd and qeyd.status == "tesdiqli":
            return {"domain": domain, "status": "tesdiqli", "token": qeyd.token}
        if not qeyd:
            qeyd = db.TesdiqDomen(domain=domain, token=secrets.token_hex(16), usul=usul)
            s.add(qeyd)
            s.commit()
        token = qeyd.token

    return {
        "domain": domain,
        "status": "gozleyir",
        "token": token,
        "dns_qeyd": f"{TXT_ACAR}{token}",
        "fayl_yolu": FAYL_YOLU,
        "telimat": (
            f"Domeninin DNS-inə TXT qeyd əlavə et: «{TXT_ACAR}{token}» — "
            f"və ya «https://{domain}{FAYL_YOLU}» faylına həmin token-i qoy. "
            "Sonra «Yoxla» düyməsinə bas."
        ),
    }


def _dns_txt_uygun(domain: str, token: str) -> bool:
    hedef = f"{TXT_ACAR}{token}"
    try:
        cavablar = dns.resolver.resolve(domain, "TXT")
    except Exception:
        return False
    for r in cavablar:
        metn = "".join(p.decode() if isinstance(p, bytes) else str(p)
                       for p in getattr(r, "strings", []) or [str(r)])
        if hedef in metn.replace('"', ""):
            return True
    return False


def _fayl_uygun(domain: str, token: str) -> bool:
    for sxem in ("https", "http"):
        try:
            cavab = httpx.get(f"{sxem}://{domain}{FAYL_YOLU}", timeout=10,
                              follow_redirects=True, verify=False)
            if cavab.status_code == 200 and token in cavab.text[:500]:
                return True
        except Exception:
            continue
    return False


def yoxla(deyer: str) -> dict:
    """Token DNS/faylda varmı? Varsa domeni `tesdiqli` işarələyir."""
    domain = _normalize(deyer)
    if domain in owned_allowlist():
        return {"domain": domain, "status": "tesdiqli", "menbe": "allowlist"}

    with db.sessiya() as s:
        qeyd = (
            s.query(db.TesdiqDomen)
            .filter(db.TesdiqDomen.domain == domain)
            .order_by(db.TesdiqDomen.id.desc())
            .first()
        )
        if not qeyd:
            return {"domain": domain, "status": "yoxdur",
                    "qeyd": "Əvvəlcə token al."}
        token = qeyd.token

        if _dns_txt_uygun(domain, token):
            menbe = "dns"
        elif _fayl_uygun(domain, token):
            menbe = "fayl"
        else:
            return {"domain": domain, "status": "gozleyir",
                    "qeyd": "Token hələ tapılmadı — DNS-in yayılması bir neçə "
                            "dəqiqə çəkə bilər. Yenidən yoxla."}

        qeyd.status = "tesdiqli"
        qeyd.tesdiq_tarixi = db.indi()
        qeyd.usul = menbe
        s.commit()
        return {"domain": domain, "status": "tesdiqli", "menbe": menbe}


def siyahi() -> list[dict]:
    """Təsdiqli domenlər (allowlist + baza) — interfeys üçün."""
    neticeler = [{"domain": d, "status": "tesdiqli", "menbe": "allowlist"}
                 for d in sorted(owned_allowlist())]
    with db.sessiya() as s:
        for q in (s.query(db.TesdiqDomen)
                  .filter(db.TesdiqDomen.status == "tesdiqli").all()):
            if q.domain not in owned_allowlist():
                neticeler.append({"domain": q.domain, "status": "tesdiqli",
                                  "menbe": q.usul})
    return neticeler
