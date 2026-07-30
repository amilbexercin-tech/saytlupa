"""Serverin coğrafi yeri və hosting provayderi (ip-api.com — pulsuz, açarsız)."""

from __future__ import annotations

import httpx

from ..decorators import cached, retry, safe_collector, timed
from .base import BASLIQLAR, ip_tap, tam_host

API = "http://ip-api.com/json/{}"
SAHELER = "status,message,country,countryCode,regionName,city,lat,lon,isp,org,as,query"


@safe_collector("geo")
@timed
@cached(saniye=86400)
@retry(cehd=2, gozleme=1.0)
async def topla(url: str) -> dict:
    host = tam_host(url)
    ip = ip_tap(host)

    async with httpx.AsyncClient(headers=BASLIQLAR, timeout=10) as musteri:
        cavab = await musteri.get(API.format(ip), params={"fields": SAHELER})
        cavab.raise_for_status()
        data = cavab.json()

    if data.get("status") != "success":
        return {"ip": ip, "xeta": data.get("message", "naməlum")}

    return {
        "ip": ip,
        "olke": data.get("country", ""),
        "olke_kodu": data.get("countryCode", ""),
        "region": data.get("regionName", ""),
        "seher": data.get("city", ""),
        "en_dairesi": data.get("lat"),
        "uzunluq_dairesi": data.get("lon"),
        "provayder": data.get("isp", ""),
        "teskilat": data.get("org", ""),
        "as": data.get("as", ""),
    }
