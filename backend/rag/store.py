"""Vektor bazası — chunk-ların saxlanması və hibrid axtarış.

**Hibrid axtarış** iki üsulu birləşdirir:

- *vektor axtarışı* mənanı tutur ("nə qədər gözləmək lazımdır?" → "2-3 iş günü"),
  amma dəqiq söz və rəqəmləri (model nömrəsi, qiymət) itirə bilir;
- *açar söz axtarışı* əksinə — dəqiq sözü tapır, mənanı yox.

Nəticələr **Reciprocal Rank Fusion (RRF)** ilə birləşdirilir: hər sənədin balı
`Σ 1/(k + sıra)` düsturu ilə hesablanır. RRF balların özünü yox, **sıralamanı**
işlətdiyi üçün iki fərqli miqyaslı üsulu birləşdirməyə imkan verir.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import text

from .. import db
from . import embedder

log = logging.getLogger("saytlupa")

RRF_K = 60  # RRF sabiti — standart dəyər
SOZ = re.compile(r"\w+", re.UNICODE)


# ------------------------------------------------------------------ yazma


def sehife_chunklarini_yaz(
    sehife_id: int, parcalar: list[dict], vektorlar: list[list[float]], model: str
) -> int:
    """Səhifənin chunk-larını yazır (köhnələri əvəz edərək)."""
    with db.sessiya() as s:
        s.query(db.Chunk).filter(db.Chunk.page_id == sehife_id).delete()
        for parca, vektor in zip(parcalar, vektorlar):
            chunk = db.Chunk(
                page_id=sehife_id, sira=parca["sira"], metn=parca["metn"], model=model
            )
            chunk.embedding_yaz(vektor)
            s.add(chunk)
        s.commit()
    return len(parcalar)


def chunk_sayi(site_id: int) -> int:
    with db.sessiya() as s:
        return (
            s.query(db.Chunk)
            .join(db.Sehife, db.Sehife.id == db.Chunk.page_id)
            .filter(db.Sehife.site_id == site_id)
            .count()
        )


def sil(site_id: int) -> None:
    with db.sessiya() as s:
        sehife_idler = [
            p.id for p in s.query(db.Sehife).filter(db.Sehife.site_id == site_id).all()
        ]
        if sehife_idler:
            s.query(db.Chunk).filter(db.Chunk.page_id.in_(sehife_idler)).delete(
                synchronize_session=False
            )
            s.commit()


# ------------------------------------------------------------------ axtarış


def _vektor_metni(vektor: list[float]) -> str:
    """pgvector `[0.1,0.2,...]` formatını gözləyir."""
    return "[" + ",".join(f"{d:.6f}" for d in vektor) + "]"


def vektor_axtar(site_id: int, sorgu_vektoru: list[float], limit: int = 20) -> list[dict]:
    if db.POSTGRES:
        sorgu = text(
            """
            SELECT c.id, c.page_id, c.metn, p.url, p.basliq,
                   1 - (c.embedding <=> CAST(:vektor AS vector)) AS bal
            FROM chunks c
            JOIN pages p ON p.id = c.page_id
            WHERE p.site_id = :site_id
            ORDER BY c.embedding <=> CAST(:vektor AS vector)
            LIMIT :limit
            """
        )
        with db.engine.connect() as qosulma:
            setirler = qosulma.execute(
                sorgu,
                {
                    "vektor": _vektor_metni(sorgu_vektoru),
                    "site_id": site_id,
                    "limit": limit,
                },
            ).mappings().all()
        return [dict(s) for s in setirler]

    # SQLite — vektor müqayisəsi Python tərəfdə
    with db.sessiya() as s:
        qeydler = (
            s.query(db.Chunk, db.Sehife)
            .join(db.Sehife, db.Sehife.id == db.Chunk.page_id)
            .filter(db.Sehife.site_id == site_id)
            .all()
        )
        neticeler = [
            {
                "id": chunk.id,
                "page_id": chunk.page_id,
                "metn": chunk.metn,
                "url": sehife.url,
                "basliq": sehife.basliq,
                "bal": embedder.oxsarliq(sorgu_vektoru, chunk.embedding_oxu()),
            }
            for chunk, sehife in qeydler
        ]
    neticeler.sort(key=lambda n: n["bal"], reverse=True)
    return neticeler[:limit]


def acar_soz_axtar(site_id: int, sual: str, limit: int = 10) -> list[dict]:
    if db.POSTGRES:
        sorgu = text(
            """
            SELECT c.id, c.page_id, c.metn, p.url, p.basliq,
                   ts_rank(to_tsvector('simple', c.metn),
                           plainto_tsquery('simple', :sual)) AS bal
            FROM chunks c
            JOIN pages p ON p.id = c.page_id
            WHERE p.site_id = :site_id
              AND to_tsvector('simple', c.metn) @@ plainto_tsquery('simple', :sual)
            ORDER BY bal DESC
            LIMIT :limit
            """
        )
        with db.engine.connect() as qosulma:
            setirler = qosulma.execute(
                sorgu, {"sual": sual, "site_id": site_id, "limit": limit}
            ).mappings().all()
        return [dict(s) for s in setirler]

    # SQLite — sadə söz uyğunluğu
    sozler = {s.lower() for s in SOZ.findall(sual) if len(s) > 2}
    if not sozler:
        return []

    with db.sessiya() as s:
        qeydler = (
            s.query(db.Chunk, db.Sehife)
            .join(db.Sehife, db.Sehife.id == db.Chunk.page_id)
            .filter(db.Sehife.site_id == site_id)
            .all()
        )
    neticeler = []
    for chunk, sehife in qeydler:
        kicik = chunk.metn.lower()
        tapilan = sum(1 for soz in sozler if soz in kicik)
        if tapilan:
            neticeler.append(
                {
                    "id": chunk.id,
                    "page_id": chunk.page_id,
                    "metn": chunk.metn,
                    "url": sehife.url,
                    "basliq": sehife.basliq,
                    "bal": tapilan / len(sozler),
                }
            )
    neticeler.sort(key=lambda n: n["bal"], reverse=True)
    return neticeler[:limit]


def _rrf(siyahilar: list[list[dict]], k: int = RRF_K) -> list[dict]:
    """Reciprocal Rank Fusion — bir neçə sıralamanı birləşdirir."""
    ballar: dict[int, float] = {}
    qeydler: dict[int, dict] = {}

    for siyahi in siyahilar:
        for sira, qeyd in enumerate(siyahi, start=1):
            ballar[qeyd["id"]] = ballar.get(qeyd["id"], 0.0) + 1.0 / (k + sira)
            qeydler.setdefault(qeyd["id"], qeyd)

    birlesik = []
    for chunk_id, bal in sorted(ballar.items(), key=lambda x: -x[1]):
        qeyd = dict(qeydler[chunk_id])
        qeyd["rrf_bal"] = round(bal, 5)
        birlesik.append(qeyd)
    return birlesik


def hibrid_axtar(
    site_id: int, sual: str, *, vektor_limit: int = 12, acar_limit: int = 6
) -> tuple[list[dict], str]:
    """Vektor + açar söz axtarışı, RRF ilə birləşdirilmiş.

    Qaytarır: (namizədlər, hansı embedding üsulu işlədildi)
    """
    vektorlar, menbe = embedder.vektorla([sual], sorgudur=True)
    vektor_neticeleri = vektor_axtar(site_id, vektorlar[0], vektor_limit) if vektorlar else []
    acar_neticeleri = acar_soz_axtar(site_id, sual, acar_limit)

    log.info(
        "axtarış: vektor=%s açar söz=%s (%s)",
        len(vektor_neticeleri), len(acar_neticeleri), menbe,
    )
    return _rrf([vektor_neticeleri, acar_neticeleri]), menbe
