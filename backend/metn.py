"""HTML → təmiz mətn.

RAG-ın keyfiyyəti burada başlayır: menyu, footer, skript və reklam mətni
chunk-lara düşsə, axtarış nəticələri zibillənir.
"""

from __future__ import annotations

import hashlib
import re

from bs4 import BeautifulSoup

# Məzmun daşımayan bölmələr
ATILAN_ETIKETLER = (
    "script", "style", "noscript", "iframe", "svg", "canvas",
    "nav", "footer", "header", "aside", "form", "button", "template",
)

# Bu sinif/id-lər adətən menyu, cookie xəbərdarlığı, sosial düymələrdir
ATILAN_NAXIS = re.compile(
    r"(menu|navbar|nav-|footer|header|sidebar|cookie|banner|breadcrumb|"
    r"social|share|popup|modal|advert|reklam)",
    re.IGNORECASE,
)

# Əsas məzmunun ola biləcəyi yerlər — sıra ilə axtarılır
ESAS_SECICILER = ("main", "article", '[role="main"]', "#content", ".content", "#main")

BOSLUQ = re.compile(r"[ \t\xa0]+")
COX_SETIR = re.compile(r"\n{3,}")


def _temizle(supa: BeautifulSoup) -> None:
    for etiket in supa(list(ATILAN_ETIKETLER)):
        etiket.decompose()

    for etiket in supa.find_all(attrs={"class": ATILAN_NAXIS}):
        etiket.decompose()
    for etiket in supa.find_all(attrs={"id": ATILAN_NAXIS}):
        etiket.decompose()


def _govde(supa: BeautifulSoup):
    for secici in ESAS_SECICILER:
        tapilan = supa.select_one(secici)
        if tapilan and len(tapilan.get_text(strip=True)) > 200:
            return tapilan
    return supa.body or supa


def cixart(html: str) -> tuple[str, str]:
    """(başlıq, təmiz mətn) qaytarır."""
    supa = BeautifulSoup(html, "lxml")
    # Başlıqda çox vaxt sətir keçidi və artıq boşluq olur ("ASAN\n  -\n ASAN")
    xam_basliq = supa.title.get_text() if supa.title else ""
    basliq = " ".join(xam_basliq.split())

    _temizle(supa)
    govde = _govde(supa)

    # Blok elementlərini sətir kimi ayırırıq ki, cümlələr bir-birinə yapışmasın
    metn = govde.get_text("\n", strip=True)
    metn = BOSLUQ.sub(" ", metn)
    metn = COX_SETIR.sub("\n\n", metn)

    return basliq, metn.strip()


def barmaq_izi(metn: str) -> str:
    """Səhifənin dəyişib-dəyişmədiyini bilmək üçün (n8n izləmə workflow-u üçün)."""
    return hashlib.sha256(metn.encode("utf-8")).hexdigest()
