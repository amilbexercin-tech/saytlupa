"""Təhvil funksiyaları üçün ortaq məlumat.

Dörd düymənin hamısı eyni şeylərə ehtiyac duyur: analizin nəticəsi, yığılmış
səhifələr və yazılacaq qovluq. Təkrar olmasın deyə hamısı burada.
"""

from __future__ import annotations

import re
from pathlib import Path

from .. import analiz as analiz_xidmeti
from .. import db
from ..config import STORAGE

# Düymə → `storage/` altındakı qovluq
QOVLUQLAR = {
    "muasir": "modern",
    "arsiv": "archives",
    "pdf": "pdf",
    "klon": "klon",
}

SEHIFE_LIMITI = 20  # təhvil sənədlərində neçə səhifə nəzərə alınır

TEHLUKESIZ_AD = re.compile(r"[^a-zA-Z0-9._-]+")


def temiz_ad(metn: str, ehtiyat: str = "sayt") -> str:
    """Domeni/URL-i fayl sistemi üçün təhlükəsiz ada çevirir."""
    ad = TEHLUKESIZ_AD.sub("_", (metn or "").strip()).strip("._-")
    return ad[:80] or ehtiyat


def qovluq(nov: str, domain: str, *, yarat: bool = True) -> Path:
    """`storage/<nov>/<domain>` yolunu qaytarır."""
    if nov not in QOVLUQLAR:
        raise ValueError(f"Naməlum təhvil növü: {nov}")
    yol = STORAGE / QOVLUQLAR[nov] / temiz_ad(domain)
    if yarat:
        yol.mkdir(parents=True, exist_ok=True)
    return yol


def sehifeler(site_id: int, limit: int = SEHIFE_LIMITI) -> list[dict]:
    """Bu sayt üçün yığılmış səhifələr (ən uzun mətnlilər əvvəldə).

    Uzun mətn adətən əsas məzmun səhifəsidir; qısa olanlar (əlaqə, 404) sonda.
    """
    with db.sessiya() as s:
        qeydler = (
            s.query(db.Sehife).filter(db.Sehife.site_id == site_id).limit(200).all()
        )
    siyahi = [
        {"url": p.url, "basliq": p.basliq or "", "metn": p.metn or ""} for p in qeydler
    ]
    siyahi.sort(key=lambda p: len(p["metn"]), reverse=True)
    return siyahi[:limit]


def sahe(xam: dict, ad: str) -> dict:
    """Toplayıcının məlumatı — uğursuz olubsa boş lüğət."""
    qeyd = (xam.get("neticeler") or {}).get(ad) or {}
    return qeyd.get("data") or {} if qeyd.get("ugurlu") else {}


def kimlik(analiz_id: int) -> dict | None:
    """Yalnız domen və ünvan — yükləmə yollarını qurmaq üçün yüngül sorğu."""
    with db.sessiya() as s:
        analiz = s.get(db.Analiz, analiz_id)
        if analiz is None:
            return None
        sayt = s.get(db.Sayt, analiz.site_id)
        return {
            "analiz_id": analiz_id,
            "site_id": analiz.site_id,
            "url": sayt.url if sayt else "",
            "domain": sayt.domain if sayt else "",
        }


def konteks(analiz_id: int) -> dict | None:
    """Analizin nəticəsi + yığılmış səhifələr. Analiz yoxdursa `None`."""
    netice = analiz_xidmeti.analiz_oxu(analiz_id)
    if netice is None:
        return None
    netice["sehifeler"] = sehifeler(netice["site_id"])
    return netice
