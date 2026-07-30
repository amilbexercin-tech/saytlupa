"""Domen məlumatı — yaş, qeydiyyatçı, bitmə tarixi.

Üç mənbə, sıra ilə sınanır:
1. RDAP (rəsmi, JSON) — əksər beynəlxalq domenlər üçün.
2. Öz WHOIS müştərimiz (xam TCP/43) — `.az` kimi RDAP-ı olmayan domenlər üçün.
   IANA-dan həmin TLD-nin serverini soruşur, sonra birbaşa ona müraciət edir.
3. `python-whois` — son ehtiyat.
"""

from __future__ import annotations

import asyncio
import re
import socket
from datetime import datetime, timezone
from typing import Any

import httpx

from ..decorators import cached, retry, safe_collector, timed
from .base import BASLIQLAR, domen

RDAP_URL = "https://rdap.org/domain/{}"
IANA_WHOIS = "whois.iana.org"

# Wayback Machine — saytın ilk arxiv tarixi (pulsuz, açarsız).
# Mütləq https: http variantı cavab vermir (timeout).
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"

# IANA-da WHOIS serveri göstərilməyən TLD-lər üçün əl ilə yazılmış cədvəl.
# `.az` burada YOXDUR — Azərbaycan reyestri pulsuz WHOIS xidməti vermir
# (whois.az cavab vermir, whois.nic.az mövcud deyil). Bunu uydurmuruq.
ELAVE_SERVERLER: dict[str, str] = {
    "ge": "whois.nic.ge",
    "am": "whois.amnic.net",
    "kz": "whois.nic.kz",
    "ua": "whois.ua",
    "by": "whois.cctld.by",
}

# Fərqli reyestrlər fərqli adlar işlədir — hamısını tanıyırıq
YARADILMA_ACARLARI = (
    "creation date", "created", "created on", "registered on", "registration date",
    "domain registration date", "registered", "activated",
)
BITME_ACARLARI = (
    "registry expiry date", "expiry date", "expiration date", "expires on",
    "paid-till", "renewal date", "expire",
)
QEYDIYYATCI_ACARLARI = ("registrar", "sponsoring registrar", "registrar name")


def _tarix_oxu(deyer: Any) -> datetime | None:
    if not deyer:
        return None
    if isinstance(deyer, list):
        deyer = deyer[0] if deyer else None
    if isinstance(deyer, datetime):
        return deyer if deyer.tzinfo else deyer.replace(tzinfo=timezone.utc)
    if isinstance(deyer, str):
        try:
            return datetime.fromisoformat(deyer.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _yas_gun(yaradilma: datetime | None) -> int | None:
    if not yaradilma:
        return None
    return (datetime.now(timezone.utc) - yaradilma).days


async def _rdap(ad: str) -> dict:
    async with httpx.AsyncClient(
        headers=BASLIQLAR, timeout=12, follow_redirects=True
    ) as musteri:
        cavab = await musteri.get(RDAP_URL.format(ad))
        cavab.raise_for_status()
        data = cavab.json()

    hadiseler = {h.get("eventAction"): h.get("eventDate") for h in data.get("events", [])}
    qeydiyyatci = ""
    for varlıq in data.get("entities", []):
        if "registrar" in varlıq.get("roles", []):
            for parca in varlıq.get("vcardArray", [[], []])[1]:
                if parca[0] == "fn":
                    qeydiyyatci = parca[3]
                    break
    return {
        "menbe": "rdap",
        "yaradilma": _tarix_oxu(hadiseler.get("registration")),
        "bitme": _tarix_oxu(hadiseler.get("expiration")),
        "yenilenme": _tarix_oxu(hadiseler.get("last changed")),
        "qeydiyyatci": qeydiyyatci,
        "statuslar": data.get("status", []),
    }


def _whois_sorgu(server: str, sorgu: str, timeout: int = 10) -> str:
    """Xam WHOIS protokolu (TCP port 43): sorğunu göndər, mətni oxu."""
    with socket.create_connection((server, 43), timeout=timeout) as baglanti:
        baglanti.sendall((sorgu + "\r\n").encode("utf-8", errors="ignore"))
        parcalar = []
        while True:
            data = baglanti.recv(4096)
            if not data:
                break
            parcalar.append(data)
    return b"".join(parcalar).decode("utf-8", errors="ignore")


def _tld_serveri(tld: str) -> str:
    """Həmin TLD-nin WHOIS serverini tapır.

    Əvvəlcə IANA-dan soruşur. Bəzi TLD-lər (məsələn `.az`) IANA-da WHOIS serveri
    göstərmir — onlar üçün əl ilə yazılmış cədvələ baxırıq.
    """
    cavab = _whois_sorgu(IANA_WHOIS, tld)
    # `[^\S\n]*` — yalnız eyni sətirdəki boşluqlar; `\s*` sətir keçib növbəti
    # açarı tuturdu ("whois:" boş olanda "status:" qaytarırdı).
    uygunluq = re.search(r"^whois:[^\S\n]*(\S+)[^\S\n]*$", cavab, re.IGNORECASE | re.MULTILINE)
    if uygunluq:
        return uygunluq.group(1).strip()
    return ELAVE_SERVERLER.get(tld.lower(), "")


def _sahe_tap(metn: str, acarlar: tuple[str, ...]) -> str:
    """WHOIS mətnindən 'acar: deyer' sətrini çıxarır."""
    for setir in metn.splitlines():
        if ":" not in setir:
            continue
        acar, _, deyer = setir.partition(":")
        if acar.strip().lower() in acarlar and deyer.strip():
            return deyer.strip()
    return ""


def _whois_tarix(xam: str) -> datetime | None:
    if not xam:
        return None
    xam = xam.strip().replace("/", "-")
    formatlar = (
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y",
    )
    for f in formatlar:
        try:
            n = datetime.strptime(xam[: len(datetime.now().strftime(f)) + 6], f)
            return n if n.tzinfo else n.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return _tarix_oxu(xam)


def _xam_whois(ad: str) -> dict:
    """RDAP-ı olmayan TLD-lər üçün (məs. .az) öz WHOIS müştərimiz."""
    tld = ad.rsplit(".", 1)[-1]
    server = _tld_serveri(tld)
    if not server:
        raise RuntimeError(f"'{tld}' üçün WHOIS serveri tapılmadı")

    metn = _whois_sorgu(server, ad)
    return {
        "menbe": f"whois ({server})",
        "yaradilma": _whois_tarix(_sahe_tap(metn, YARADILMA_ACARLARI)),
        "bitme": _whois_tarix(_sahe_tap(metn, BITME_ACARLARI)),
        "yenilenme": _whois_tarix(_sahe_tap(metn, ("updated date", "last updated", "modified"))),
        "qeydiyyatci": _sahe_tap(metn, QEYDIYYATCI_ACARLARI),
        "statuslar": re.findall(r"^\s*status:\s*(.+)$", metn, re.IGNORECASE | re.MULTILINE)[:5],
    }


async def _wayback_ilk_arxiv(ad: str) -> dict:
    """Saytın ilk arxivləşdirilmə tarixi (arxiv.org).

    Bu **domenin qeydiyyat tarixi deyil** — yalnız "sayt ən azı bu tarixdən bəri
    mövcuddur" deməkdir. `.az` kimi WHOIS-u olmayan domenlər üçün yeganə dürüst
    ipucudur, ona görə nəticədə açıq şəkildə "təxmini" kimi işarələnir.
    """
    parametrler = {"url": ad, "output": "json", "limit": 1, "fl": "timestamp"}
    # Arxiv.org bizim adi `Accept: text/html...` başlığımıza 498 qaytarır —
    # burada sadə, JSON gözləyən başlıqlar işlədilir.
    async with httpx.AsyncClient(
        headers={"User-Agent": "SaytLupa/0.1", "Accept": "application/json"},
        timeout=25,
        follow_redirects=True,
    ) as musteri:
        cavab = await musteri.get(WAYBACK_CDX, params=parametrler)
        cavab.raise_for_status()
        setirler = cavab.json()

    if len(setirler) < 2:  # ilk sətir başlıqdır
        return {}

    damga = setirler[1][0]  # YYYYMMDDhhmmss
    tarix = datetime.strptime(damga[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
    return {
        "ilk_arxiv": tarix.isoformat(),
        "ilk_arxiv_il": tarix.year,
        "en_azi_yas_il": round((datetime.now(timezone.utc) - tarix).days / 365.25, 1),
    }


def _whois(ad: str) -> dict:
    """Son ehtiyat — python-whois kitabxanası."""
    import whois  # python-whois

    n = whois.whois(ad)
    return {
        "menbe": "python-whois",
        "yaradilma": _tarix_oxu(n.creation_date),
        "bitme": _tarix_oxu(n.expiration_date),
        "yenilenme": _tarix_oxu(n.updated_date),
        "qeydiyyatci": (n.registrar or "") if isinstance(n.registrar, str) else "",
        "statuslar": n.status if isinstance(n.status, list) else [n.status or ""],
    }


@safe_collector("domen")
@timed
@cached(saniye=86400)  # domen məlumatı gün ərzində dəyişmir
@retry(cehd=2, gozleme=1.0)
async def topla(url: str) -> dict:
    ad = domen(url)
    xetalar: list[str] = []
    netice: dict | None = None

    # Sıra ilə sınanır; biri nəticə versə dayanırıq (coroutine-lər tələb olunanda yaradılır)
    yollar = (
        lambda: _rdap(ad),
        lambda: asyncio.to_thread(_xam_whois, ad),
        lambda: asyncio.to_thread(_whois, ad),
    )
    for yol in yollar:
        try:
            netice = await yol()
            if netice.get("yaradilma") or netice.get("qeydiyyatci"):
                break
        except Exception as xeta:
            xetalar.append(f"{type(xeta).__name__}: {xeta}")
            netice = None

    # WHOIS/RDAP alınmasa da Wayback ipucusu verilə bilər (məs. `.az` domenləri)
    arxiv: dict = {}
    if netice is None or not netice.get("yaradilma"):
        try:
            arxiv = await _wayback_ilk_arxiv(ad)
        except Exception as xeta:
            xetalar.append(f"wayback: {type(xeta).__name__}")

    if netice is None:
        if not arxiv:
            raise RuntimeError("Domen məlumatı alınmadı — " + " | ".join(xetalar[:3]))
        netice = {
            "menbe": "wayback (təxmini)",
            "yaradilma": None, "bitme": None, "yenilenme": None,
            "qeydiyyatci": "", "statuslar": [],
        }

    yas = _yas_gun(netice["yaradilma"])
    return {
        "domen": ad,
        "menbe": netice["menbe"],
        "yaradilma": netice["yaradilma"].isoformat() if netice["yaradilma"] else None,
        "bitme": netice["bitme"].isoformat() if netice["bitme"] else None,
        "yenilenme": netice["yenilenme"].isoformat() if netice["yenilenme"] else None,
        "yas_gun": yas,
        "yas_il": round(yas / 365.25, 1) if yas else None,
        "qeydiyyatci": netice["qeydiyyatci"],
        "statuslar": netice["statuslar"],
        # Dəqiq WHOIS yoxdursa — dürüst, "təxmini" işarəli ipucu
        "arxiv_ipucu": arxiv,
        "dəqiq_yaş_var": yas is not None,
        "qeyd": (
            ""
            if yas is not None
            else (
                f"Bu TLD üçün pulsuz WHOIS yoxdur — dəqiq qeydiyyat tarixi alınmadı. "
                f"Arxiv.org-a görə sayt ən azı {arxiv.get('ilk_arxiv_il')} ilindən mövcuddur "
                f"(~{arxiv.get('en_azi_yas_il')} il). Bu TƏXMİNİ göstəricidir."
                if arxiv
                else "Bu TLD üçün pulsuz WHOIS yoxdur — domen yaşı müəyyən edilə bilmədi."
            )
        ),
    }
