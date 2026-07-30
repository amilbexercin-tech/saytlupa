"""DNS qeydləri — A, AAAA, MX, NS, TXT, CNAME + CDN təxmini."""

from __future__ import annotations

import asyncio

import dns.asyncresolver

from ..decorators import cached, safe_collector, timed
from .base import domen, tam_host

NOVLER = ("A", "AAAA", "MX", "NS", "TXT", "CNAME")

CDN_IMZALARI = {
    "cloudflare": "Cloudflare",
    "akamai": "Akamai",
    "fastly": "Fastly",
    "cloudfront": "AWS CloudFront",
    "azureedge": "Azure CDN",
    "bunnycdn": "Bunny CDN",
    "b-cdn": "Bunny CDN",
    "stackpath": "StackPath",
    "gcorelabs": "G-Core",
    "sucuri": "Sucuri",
}

POCT_IMZALARI = {
    "google": "Google Workspace",
    "outlook": "Microsoft 365",
    "yandex": "Yandex Mail",
    "zoho": "Zoho Mail",
    "mail.ru": "Mail.ru",
}


async def _sorgu(ad: str, nov: str) -> list[str]:
    try:
        cavab = await dns.asyncresolver.resolve(ad, nov, lifetime=6)
        return [q.to_text().strip('"') for q in cavab]
    except Exception:
        return []


def _tap(metnler: list[str], imzalar: dict[str, str]) -> str:
    birlesik = " ".join(metnler).lower()
    for acar, ad in imzalar.items():
        if acar in birlesik:
            return ad
    return ""


@safe_collector("dns")
@timed
@cached(saniye=3600)
async def topla(url: str) -> dict:
    host = tam_host(url) or domen(url)
    kok = domen(url)

    neticeler = await asyncio.gather(*[_sorgu(host, n) for n in NOVLER])
    qeydler = dict(zip(NOVLER, neticeler))

    # NS və MX kök domendə olur, alt domendə yox
    if not qeydler["NS"]:
        qeydler["NS"] = await _sorgu(kok, "NS")
    if not qeydler["MX"]:
        qeydler["MX"] = await _sorgu(kok, "MX")

    cdn = _tap(qeydler["CNAME"] + qeydler["NS"], CDN_IMZALARI)
    poct = _tap(qeydler["MX"], POCT_IMZALARI)

    spf = next((t for t in qeydler["TXT"] if t.startswith("v=spf1")), "")
    dmarc = await _sorgu(f"_dmarc.{kok}", "TXT")

    return {
        "host": host,
        "a": qeydler["A"],
        "aaaa": qeydler["AAAA"],
        "mx": qeydler["MX"],
        "ns": qeydler["NS"],
        "cname": qeydler["CNAME"],
        "txt_sayi": len(qeydler["TXT"]),
        "cdn": cdn,
        "poct_xidmeti": poct,
        "spf_var": bool(spf),
        "dmarc_var": bool(dmarc),
        "ipv6_destekleyir": bool(qeydler["AAAA"]),
    }
