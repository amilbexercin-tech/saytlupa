"""Analiz toplayıcıları və onları paralel işlədən dirijor.

Sayt **bir dəfə** yüklənir, HTML bütün toplayıcılar arasında paylaşılır.
Şəbəkədən asılı olanlar (domen, dns, geo, sertifikat) paralel işləyir.
Biri sınsa digərləri davam edir — `@safe_collector` sayəsində.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from ..decorators import timed
from . import (
    dizayn,
    dns_qeydleri,
    domen,
    geo,
    qoruma,
    reklam,
    sehife,
    sertifikat,
    surat,
    texnologiya,
)

# Yalnız URL tələb edən toplayıcılar (şəbəkə sorğuları)
URL_TOPLAYICILAR: dict[str, Callable[[str], Awaitable[dict]]] = {
    "domen": domen.topla,
    "dns": dns_qeydleri.topla,
    "geo": geo.topla,
    "sertifikat": sertifikat.topla,
}

# HTML tələb edən toplayıcılar (səhifə bir dəfə yüklənir)
HTML_TOPLAYICILAR: dict[str, Callable[..., Awaitable[dict]]] = {
    "sehife": sehife.topla,
    "texnologiya": texnologiya.topla,
    "dizayn": dizayn.topla,
    "reklam": reklam.topla,
}

ADLAR = list(URL_TOPLAYICILAR) + list(HTML_TOPLAYICILAR) + ["surat"]


@timed
async def butun_analiz(
    url: str, *, xeber: Callable[[str, str], None] | None = None
) -> dict[str, Any]:
    """Bütün toplayıcıları işlədir və nəticəni bir lüğətdə qaytarır.

    `xeber(ad, veziyyet)` verilsə hər addımda çağırılır — SSE canlı gedişat üçün.
    """

    def bildir(ad: str, veziyyet: str) -> None:
        if xeber:
            xeber(ad, veziyyet)

    # 1) Səhifəni bir dəfə gətir
    bildir("sehife_yukleme", "isleyir")
    try:
        html, basliqlar, yuklenme, status_kodu = await surat.olc_ve_getir(url)
        bildir("sehife_yukleme", "hazir")
    except Exception as xeta:
        bildir("sehife_yukleme", "xeta")
        return {
            "url": url,
            "ugurlu": False,
            "xeta": f"Sayt yüklənmədi: {xeta}",
            "neticeler": {},
        }

    # 2) Bot qoruması varmı? (varsa məzmun analizi etibarsızdır — dürüst bildiririk)
    qoruma_neticesi = qoruma.yoxla(html, status_kodu)

    # 3) Şəbəkə toplayıcıları paralel
    for ad in URL_TOPLAYICILAR:
        bildir(ad, "isleyir")
    url_isleri = [f(url) for f in URL_TOPLAYICILAR.values()]

    # 4) HTML toplayıcıları paralel
    for ad in HTML_TOPLAYICILAR:
        bildir(ad, "isleyir")
    html_isleri = [f(url, html, basliqlar) for f in HTML_TOPLAYICILAR.values()]

    bildir("surat", "isleyir")
    surat_isi = surat.topla(url, html, basliqlar, yuklenme)

    hamisi = await asyncio.gather(*url_isleri, *html_isleri, surat_isi)

    neticeler: dict[str, Any] = {}
    for ad, netice in zip(ADLAR, hamisi):
        neticeler[ad] = netice
        bildir(ad, "hazir" if netice.get("ugurlu") else "xeta")

    ugurlu_sayi = sum(1 for n in neticeler.values() if n.get("ugurlu"))

    return {
        "url": url,
        "ugurlu": True,
        "html": html,
        "basliqlar": basliqlar,
        "status_kodu": status_kodu,
        "yuklenme_saniye": round(yuklenme, 2),
        "qoruma": qoruma_neticesi,
        "neticeler": neticeler,
        "ugurlu_toplayici": ugurlu_sayi,
        "umumi_toplayici": len(ADLAR),
    }


__all__ = ["butun_analiz", "ADLAR"]
