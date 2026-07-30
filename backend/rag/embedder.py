"""Embedding — mətni ədəd vektoruna çevirmək.

İki yol var:

1. **Gemini `gemini-embedding-001`** (əsas) — `GOOGLE_API_KEY` varsa işlədilir.
2. **Lokal hashing embedding** (ehtiyat) — açar yoxdursa. Sözləri və hərf
   n-qramlarını sabit vektor xanalarına yayır. Semantik yaxınlığı (sinonimləri)
   tutmur, amma eyni/oxşar sözlü mətnləri tapır və layihənin açarsız işləməsini
   təmin edir.

Hansı üsulun işlədildiyi **hər zaman qaytarılır** ki, nəticə şərh edilərkən
səhv fikir yaranmasın.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Literal

from .. import cache
from ..config import ayarlar

log = logging.getLogger("saytlupa")

OLCU = 768
Menbe = Literal["gemini", "lokal"]

SOZ = re.compile(r"\w+", re.UNICODE)
QRAM = 4  # hərf n-qramının uzunluğu


# ------------------------------------------------------------------ lokal üsul


def _xana(acar: str, tuz: str) -> int:
    xam = hashlib.blake2b(f"{tuz}:{acar}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(xam, "big") % OLCU


def _isare(acar: str) -> int:
    """Xanaların bir-birini ləğv etməsi üçün işarə (hashing trick)."""
    xam = hashlib.blake2b(f"isare:{acar}".encode("utf-8"), digest_size=4).digest()
    return 1 if xam[0] % 2 == 0 else -1


def lokal_vektor(metn: str) -> list[float]:
    """Sözlər + hərf n-qramları üzərində hashing embedding."""
    vektor = [0.0] * OLCU
    kicik = metn.lower()

    sozler = SOZ.findall(kicik)
    for soz in sozler:
        vektor[_xana(soz, "soz")] += _isare(soz) * 1.0

    # Hərf n-qramları söz formalarındakı fərqi (hal, şəkilçi) yumşaldır
    duz = " ".join(sozler)
    for i in range(len(duz) - QRAM + 1):
        qram = duz[i : i + QRAM]
        vektor[_xana(qram, "qram")] += _isare(qram) * 0.5

    uzunluq = math.sqrt(sum(d * d for d in vektor))
    return [d / uzunluq for d in vektor] if uzunluq else vektor


# ----------------------------------------------------------------- Gemini üsulu


def _normalla(vektor: list[float]) -> list[float]:
    """Vektoru vahid uzunluğa gətirir.

    `gemini-embedding-001` standart olaraq 3072 ölçü verir və yalnız tam ölçüdə
    normallaşdırılmış olur. 768-ə qısaldılmış (Matryoshka) vektorun norması 1
    deyil — ölçülüb: ~0.59. Kosinus oxşarlığı miqyasdan asılı olmasa da, lokal
    üsulun vektorları normallaşdırılmış olduğuna görə hər ikisi eyni formada
    saxlanılır; RRF və SQLite rejimindəki hesablamalar da bundan faydalanır.
    """
    uzunluq = math.sqrt(sum(d * d for d in vektor))
    return [d / uzunluq for d in vektor] if uzunluq else vektor


def _gemini_vektorlar(metnler: list[str], sorgudur: bool) -> list[list[float]]:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    model = GoogleGenerativeAIEmbeddings(
        model=f"models/{ayarlar.embedding_model}",
        google_api_key=ayarlar.google_api_key,
        # Baza sütunu 768 ölçülüdür (`db.EMBEDDING_OLCUSU`)
        output_dimensionality=OLCU,
    )
    xam = (
        [model.embed_query(m) for m in metnler]
        if sorgudur
        else model.embed_documents(metnler)
    )
    return [_normalla(v) for v in xam]


# ------------------------------------------------------------------- ümumi giriş


def menbe() -> Menbe:
    return "gemini" if ayarlar.gemini_var else "lokal"


def _kes_acari(metn: str, m: Menbe) -> str:
    izi = hashlib.sha256(metn.encode("utf-8")).hexdigest()[:24]
    return f"emb:{m}:{ayarlar.embedding_model}:{izi}"


def vektorla(metnler: list[str], *, sorgudur: bool = False) -> tuple[list[list[float]], Menbe]:
    """Mətn siyahısını vektorlara çevirir.

    Keşdə olanlar götürülür, yalnız qalanları modelə göndərilir.
    Qaytarır: (vektorlar, hansı üsul işlədildi)
    """
    if not metnler:
        return [], menbe()

    m = menbe()
    neticeler: list[list[float] | None] = [None] * len(metnler)
    qalan: list[int] = []

    for i, metn in enumerate(metnler):
        hazir = cache.oxu(_kes_acari(metn, m))
        if hazir:
            neticeler[i] = hazir
        else:
            qalan.append(i)

    if qalan:
        xam = [metnler[i] for i in qalan]
        if m == "gemini":
            try:
                yeni = _gemini_vektorlar(xam, sorgudur)
            except Exception as xeta:
                log.warning("Gemini embedding alınmadı (%s) — lokal üsula keçilir", xeta)
                m = "lokal"
                yeni = [lokal_vektor(t) for t in xam]
        else:
            yeni = [lokal_vektor(t) for t in xam]

        for i, vektor in zip(qalan, yeni):
            neticeler[i] = vektor
            cache.yaz(_kes_acari(metnler[i], m), vektor, saniye=30 * 24 * 3600)

    return [v for v in neticeler if v is not None], m


def oxsarliq(a: list[float], b: list[float]) -> float:
    """Kosinus oxşarlığı — SQLite rejimində axtarış üçün."""
    if not a or not b:
        return 0.0
    hasil = sum(x * y for x, y in zip(a, b))
    ua = math.sqrt(sum(x * x for x in a))
    ub = math.sqrt(sum(y * y for y in b))
    return hasil / (ua * ub) if ua and ub else 0.0
