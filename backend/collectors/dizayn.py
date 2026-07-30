"""Dizayn — rəng palitrası və şriftlər (HTML + xarici CSS fayllarından)."""

from __future__ import annotations

import asyncio
import re
from collections import Counter

from bs4 import BeautifulSoup

from ..decorators import safe_collector, timed
from .base import getir, mutleq_url

HEX_NUMUNE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
RGB_NUMUNE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})")
# Dırnaqlar YIĞINA daxildir: `font-family: 'Inter', sans-serif` çox yayılmış
# yazılışdır və dırnaqda dayansaq saytın öz şrifti heç vaxt tutulmur.
SRIFT_NUMUNE = re.compile(r"font-family\s*:\s*([^;}]+)", re.IGNORECASE)

# Analizi korlayan çox ümumi rənglər
NEZERE_ALINMAYAN = {"#fff", "#ffffff", "#000", "#000000", "#transparent"}

MAX_CSS = 4  # neçə xarici CSS faylı yüklənsin

# Bunlar saytın şrifti deyil — CSS-in ehtiyat (fallback) dəyərləridir.
# Süzülməsə siyahı "serif, monospace, inherit, Menlo, Consolas" kimi zibilə çevrilir.
UMUMI_SRIFTLER = {
    "serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui",
    "ui-serif", "ui-sans-serif", "ui-monospace", "ui-rounded",
    "inherit", "initial", "unset", "revert", "none", "auto",
    "-apple-system", "blinkmacsystemfont", "segoe ui", "apple color emoji",
    "segoe ui emoji", "segoe ui symbol", "noto color emoji",
    # Kod bloklarının standart şriftləri — dizayn seçimi deyil
    "menlo", "monaco", "consolas", "courier", "courier new", "liberation mono",
}


def _hex_normal(rəng: str) -> str:
    rəng = rəng.lower()
    if len(rəng) == 4:  # #abc → #aabbcc
        return "#" + "".join(h * 2 for h in rəng[1:])
    return rəng


def _rgb_hex(r: int, g: int, b: int) -> str:
    return "#{:02x}{:02x}{:02x}".format(min(r, 255), min(g, 255), min(b, 255))


def _sriftler(metn: str) -> tuple[list[str], list[str]]:
    """(saytın öz şriftləri, ehtiyat/ümumi şriftlər) qaytarır."""
    oz: list[str] = []
    ehtiyat: list[str] = []
    for yigin in SRIFT_NUMUNE.findall(metn):
        for ad in yigin.split(","):
            ad = ad.strip().strip("\"'")
            if not ad or ad.startswith("var(") or len(ad) >= 40:
                continue
            (ehtiyat if ad.lower() in UMUMI_SRIFTLER else oz).append(ad)
    return oz, ehtiyat


async def _css_yigin(url: str, supa: BeautifulSoup) -> str:
    """Xarici CSS fayllarını (məhdud sayda) yükləyib birləşdirir."""
    unvanlar = [
        mutleq_url(url, etiket["href"])
        for etiket in supa.find_all("link", rel="stylesheet", href=True)
    ][:MAX_CSS]

    async def bir(unvan: str) -> str:
        try:
            cavab = await getir(unvan, timeout=8)
            return cavab.text if cavab.status_code == 200 else ""
        except Exception:
            return ""

    parcalar = await asyncio.gather(*[bir(u) for u in unvanlar])
    return "\n".join(parcalar)


@safe_collector("dizayn")
@timed
async def topla(url: str, html: str, basliqlar: dict) -> dict:
    supa = BeautifulSoup(html, "lxml")

    daxili_css = "\n".join(e.get_text() for e in supa.find_all("style"))
    xarici_css = await _css_yigin(url, supa)
    hamisi = f"{html}\n{daxili_css}\n{xarici_css}"

    renqler: Counter[str] = Counter()
    for tapinti in HEX_NUMUNE.findall(hamisi):
        renqler[_hex_normal(f"#{tapinti}")] += 1
    for r, g, b in RGB_NUMUNE.findall(hamisi):
        renqler[_rgb_hex(int(r), int(g), int(b))] += 1

    esas_renqler = [
        {"reng": r, "tekrar": say}
        for r, say in renqler.most_common(30)
        if r not in NEZERE_ALINMAYAN
    ][:10]

    oz_sriftler, ehtiyat_sriftler = _sriftler(hamisi)
    srift_sayi = Counter(oz_sriftler)
    esas_sriftler = [{"ad": a, "tekrar": s} for a, s in srift_sayi.most_common(8)]

    google_sriftler = sorted(
        {
            m
            for m in re.findall(
                r"fonts\.googleapis\.com/css2?\?family=([^&\"'<>]+)", hamisi
            )
        }
    )[:5]

    return {
        "esas_renqler": esas_renqler,
        "reng_sayi": len(renqler),
        "sriftler": esas_sriftler,
        "ehtiyat_sriftler": [a for a, _ in Counter(ehtiyat_sriftler).most_common(5)],
        "google_sriftler": [g.replace("+", " ") for g in google_sriftler],
        "daxili_css_kb": round(len(daxili_css) / 1024, 1),
        "xarici_css_kb": round(len(xarici_css) / 1024, 1),
        "css_fayl_sayi": len(supa.find_all("link", rel="stylesheet")),
    }
