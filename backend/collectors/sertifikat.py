"""SSL/TLS sertifikatı — kim verib, nə vaxt bitir, protokol."""

from __future__ import annotations

import asyncio
import socket
import ssl
from datetime import datetime, timezone

from .. import sebeke
from ..decorators import cached, safe_collector, timed
from .base import tam_host


def _ad_cixar(sahe) -> str:
    """(('commonName', 'X'),) → 'X'"""
    for qrup in sahe or ():
        for acar, deyer in qrup:
            if acar in ("commonName", "organizationName"):
                return deyer
    return ""


def _oxu(host: str, port: int = 443, timeout: int = 10) -> dict:
    kontekst = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as xam:
        with kontekst.wrap_socket(xam, server_hostname=host) as qorunan:
            sert = qorunan.getpeercert()
            protokol = qorunan.version()
            sifre = qorunan.cipher()

    bitme = datetime.strptime(sert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(
        tzinfo=timezone.utc
    )
    baslama = datetime.strptime(sert["notBefore"], "%b %d %H:%M:%S %Y %Z").replace(
        tzinfo=timezone.utc
    )
    qalan = (bitme - datetime.now(timezone.utc)).days

    alternativ = [d for nov, d in sert.get("subjectAltName", ()) if nov == "DNS"]

    return {
        "etibarli": qalan > 0,
        "veren": _ad_cixar(sert.get("issuer")),
        "kime": _ad_cixar(sert.get("subject")),
        "baslama": baslama.isoformat(),
        "bitme": bitme.isoformat(),
        "qalan_gun": qalan,
        "protokol": protokol,
        "sifre": sifre[0] if sifre else "",
        "alternativ_adlar": alternativ[:10],
        "alternativ_sayi": len(alternativ),
    }


@safe_collector("sertifikat")
@timed
@cached(saniye=21600)
async def topla(url: str) -> dict:
    host = tam_host(url)
    if not url.startswith("https"):
        return {"etibarli": False, "qeyd": "Sayt HTTPS istifadə etmir"}
    # Bu toplayıcı httpx-dən yox, birbaşa soketdən istifadə edir — SSRF
    # qoruması ona görə əl ilə çağırılır (bax `sebeke` modulu).
    sebeke.yoxla(url)
    return await asyncio.to_thread(_oxu, host)
