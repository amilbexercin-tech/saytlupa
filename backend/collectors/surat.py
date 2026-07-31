"""Sürət və performans.

İki mənbə:
1. Google PageSpeed Insights (rəsmi bal, Core Web Vitals) — açar olmasa da
   məhdud kvota ilə işləyir, alınmasa keçilir.
2. Öz ölçmələrimiz — yüklənmə vaxtı, səhifə ölçüsü, resurs sayı (həmişə işləyir).
"""

from __future__ import annotations

import time

import httpx
from bs4 import BeautifulSoup

from .. import sebeke
from ..config import ayarlar
from ..decorators import cached, safe_collector, timed
from .base import BASLIQLAR

PSI = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def _oz_olcme(html: str, saniye: float, basliqlar: dict) -> dict:
    supa = BeautifulSoup(html, "lxml")
    return {
        "yuklenme_saniye": round(saniye, 2),
        "html_olcusu_kb": round(len(html.encode("utf-8")) / 1024, 1),
        "skript_sayi": len(supa.find_all("script")),
        "css_sayi": len(supa.find_all("link", rel="stylesheet")),
        "sekil_sayi": len(supa.find_all("img")),
        "lazy_sekil_sayi": len(supa.find_all("img", loading="lazy")),
        "sixilma": basliqlar.get("content-encoding", "yoxdur"),
    }


@cached(saniye=21600)
async def _pagespeed(url: str, strategiya: str) -> dict:
    parametrler = {"url": url, "strategy": strategiya, "category": "performance"}
    if ayarlar.pagespeed_api_key:
        parametrler["key"] = ayarlar.pagespeed_api_key

    async with httpx.AsyncClient(headers=BASLIQLAR, timeout=60) as musteri:
        cavab = await musteri.get(PSI, params=parametrler)
        cavab.raise_for_status()
        data = cavab.json()

    mayak = data.get("lighthouseResult", {})
    olcmeler = mayak.get("audits", {})

    def olc(acar: str) -> dict:
        qeyd = olcmeler.get(acar, {})
        return {"deyer": qeyd.get("displayValue", ""), "bal": qeyd.get("score")}

    return {
        "bal": round((mayak.get("categories", {}).get("performance", {}).get("score") or 0) * 100),
        "fcp": olc("first-contentful-paint"),
        "lcp": olc("largest-contentful-paint"),
        "cls": olc("cumulative-layout-shift"),
        "tbt": olc("total-blocking-time"),
        "speed_index": olc("speed-index"),
    }


def pagespeed_sebeb(xeta: Exception) -> str:
    """Xətanı istifadəçinin başa düşəcəyi cümləyə çevirir.

    `HTTPStatusError` yazmaq heç nə demir — nə baş verdiyi və nə etmək lazım
    olduğu yazılmalıdır.
    """
    acar_var = bool(ayarlar.pagespeed_api_key)
    tovsiye = (
        "" if acar_var
        else " Pulsuz açar: console.cloud.google.com → PageSpeed Insights API "
        "→ `.env`-də `PAGESPEED_API_KEY`."
    )

    if isinstance(xeta, httpx.HTTPStatusError):
        kod = xeta.response.status_code
        if kod == 429:
            return (
                "Google PageSpeed kvotası bitib (429)."
                + (" Açar limitini gözləmək lazımdır." if acar_var
                   else " Açarsız sorğular çox məhduddur." + tovsiye)
            )
        if kod in (401, 403):
            return f"Google PageSpeed açarı qəbul etmədi ({kod}) — açarı yoxla.{tovsiye}"
        if kod == 400:
            return (
                "Google PageSpeed bu ünvanı yoxlaya bilmədi (400) — "
                "sayt Google-a açıq olmaya bilər (lokal ünvan, bot qoruması)."
            )
        return f"Google PageSpeed {kod} qaytardı.{tovsiye}"

    if isinstance(xeta, httpx.TimeoutException):
        return "Google PageSpeed 60 saniyəyə cavab vermədi — ağır saytlarda olur."

    return f"Google PageSpeed sorğusu alınmadı ({type(xeta).__name__}).{tovsiye}"


@safe_collector("surat")
@timed
async def topla(url: str, html: str, basliqlar: dict, yuklenme: float = 0.0) -> dict:
    netice: dict = {"oz_olcme": _oz_olcme(html, yuklenme, basliqlar)}

    try:
        netice["mobil"] = await _pagespeed(url, "mobile")
    except Exception as xeta:
        netice["mobil"] = None
        netice["pagespeed_qeyd"] = (
            f"{pagespeed_sebeb(xeta)} Öz ölçmələrimiz aşağıda göstərilir."
        )

    return netice


async def olc_ve_getir(url: str) -> tuple[str, dict, float, int]:
    """Səhifəni bir dəfə gətirir və yüklənmə vaxtını ölçür.

    Nəticə bütün HTML əsaslı toplayıcılar arasında paylaşılır — sayt bir dəfə yüklənir.
    Qaytarır: (html, başlıqlar, saniyə, status kodu)
    """
    basla = time.perf_counter()
    async with httpx.AsyncClient(
        headers=BASLIQLAR, timeout=ayarlar.request_timeout,
        follow_redirects=True, verify=False, event_hooks=sebeke.HOOKLAR,
    ) as musteri:
        cavab = await musteri.get(url)
    kecen = time.perf_counter() - basla
    return cavab.text, dict(cavab.headers), kecen, cavab.status_code
