"""Səhifə məzmunu — başlıq, məqsəd, əlaqə, sosial linklər, struktur."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..decorators import safe_collector, timed
from .base import domen, mutleq_url

EMAIL_NUMUNE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
TELEFON_NUMUNE = re.compile(r"(?:\+994|0)\s?\(?\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}")

SOSIAL = {
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "youtube.com": "YouTube",
    "linkedin.com": "LinkedIn",
    "t.me": "Telegram",
    "wa.me": "WhatsApp",
    "tiktok.com": "TikTok",
    "twitter.com": "X (Twitter)",
    "x.com": "X (Twitter)",
    "pinterest.com": "Pinterest",
}


def _meta(supa: BeautifulSoup, ad: str, xusus: str = "name") -> str:
    etiket = supa.find("meta", attrs={xusus: ad})
    return (etiket.get("content") or "").strip() if etiket else ""


def elaqe_cixart(url: str, html: str, supa: BeautifulSoup | None = None) -> dict:
    """Bir səhifədən sosial link, e-poçt və telefon çıxarır.

    Ayrıca funksiyadır, çünki crawler bunu **hər** gəzilən səhifəyə tətbiq edir:
    sosial linklər çox vaxt ana səhifədə yox, altlıqda və ya `/elaqe`
    səhifəsindədir (bax `analiz.elaqe_birlesdir`).
    """
    supa = supa or BeautifulSoup(html, "lxml")
    sosial: dict[str, str] = {}

    for a in supa.find_all("a", href=True):
        link = a["href"].strip()
        if link.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        tam = mutleq_url(url, link)
        for parca, ad in SOSIAL.items():
            if parca in tam and ad not in sosial:
                sosial[ad] = tam

    metn = supa.get_text(" ", strip=True)
    return {
        "sosial_linkler": sosial,
        "epostalar": sorted(set(EMAIL_NUMUNE.findall(html)))[:5],
        "telefonlar": sorted({t.strip() for t in TELEFON_NUMUNE.findall(metn)})[:5],
    }


@safe_collector("sehife")
@timed
async def topla(url: str, html: str, basliqlar: dict) -> dict:
    supa = BeautifulSoup(html, "lxml")
    kok_domen = domen(url)

    # --- Linklər ---
    daxili: set[str] = set()
    xarici: set[str] = set()

    for a in supa.find_all("a", href=True):
        link = a["href"].strip()
        if link.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        tam = mutleq_url(url, link)
        if domen(tam) == kok_domen:
            daxili.add(tam.split("#")[0])
        else:
            xarici.add(tam)

    # --- Əlaqə ---
    metn = supa.get_text(" ", strip=True)
    elaqe = elaqe_cixart(url, html, supa)
    sosial_linkler = elaqe["sosial_linkler"]
    epostalar = elaqe["epostalar"]
    telefonlar = elaqe["telefonlar"]

    # --- Struktur ---
    basliqlar_h = {f"h{n}": len(supa.find_all(f"h{n}")) for n in range(1, 4)}
    h1_metn = [h.get_text(strip=True) for h in supa.find_all("h1")][:3]

    viewport = _meta(supa, "viewport")

    return {
        "basliq": (supa.title.string or "").strip() if supa.title else "",
        "tesvir": _meta(supa, "description"),
        "acar_sozler": _meta(supa, "keywords"),
        "og_basliq": _meta(supa, "og:title", "property"),
        "og_tesvir": _meta(supa, "og:description", "property"),
        "og_sekil": _meta(supa, "og:image", "property"),
        "dil": (supa.html.get("lang") or "") if supa.html else "",
        "canonical": (
            supa.find("link", rel="canonical").get("href", "")
            if supa.find("link", rel="canonical")
            else ""
        ),
        "h1_metnler": h1_metn,
        "basliq_saylari": basliqlar_h,
        "sekil_sayi": len(supa.find_all("img")),
        "form_sayi": len(supa.find_all("form")),
        "skript_sayi": len(supa.find_all("script")),
        "daxili_link_sayi": len(daxili),
        "xarici_link_sayi": len(xarici),
        "daxili_linkler": sorted(daxili)[:60],
        "sosial_linkler": sosial_linkler,
        "epostalar": epostalar,
        "telefonlar": telefonlar,
        "mobil_uygun": bool(viewport and "width=device-width" in viewport),
        "viewport": viewport,
        "metn_uzunlugu": len(metn),
        "html_olcusu_kb": round(len(html) / 1024, 1),
        "server_basligi": basliqlar.get("server", ""),
    }
