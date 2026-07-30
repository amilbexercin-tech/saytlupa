"""RAG — saytın məzmunu üzərində sual-cavab.

İki əməliyyat var:

- `qur(site_id)` — yığılmış səhifələri parçalara bölür, vektorlaşdırır, bazaya yazır
- `cavab_ver(site_id, sual)` — hibrid axtarış → re-ranking → yaddaş → cavab
"""

from __future__ import annotations

import logging
import time

from .. import chains, db
from . import chunker, embedder, memory, reranker, store

log = logging.getLogger("saytlupa")

USTDEN_SECILEN = 5  # kontekstə düşən parça sayı


# ------------------------------------------------------------------ indeks qurma


def qur(site_id: int, *, xeber=None) -> dict:
    """Saytın səhifələrini parçalayıb vektor bazasına yazır."""
    basla = time.perf_counter()

    with db.sessiya() as s:
        sehifeler = [
            {"id": p.id, "basliq": p.basliq, "metn": p.metn}
            for p in s.query(db.Sehife).filter(db.Sehife.site_id == site_id).all()
        ]

    if not sehifeler:
        return {"chunk_sayi": 0, "sehife_sayi": 0, "menbe": embedder.menbe(), "saniye": 0.0}

    umumi = 0
    menbe = embedder.menbe()

    for sira, sehife in enumerate(sehifeler, start=1):
        parcalar = chunker.sehifeni_bol(sehife)
        if not parcalar:
            continue

        vektorlar, menbe = embedder.vektorla([p["metn"] for p in parcalar])
        umumi += store.sehife_chunklarini_yaz(sehife["id"], parcalar, vektorlar, menbe)

        if xeber:
            xeber(sira, len(sehifeler), umumi)

    kecen = round(time.perf_counter() - basla, 2)
    log.info("RAG quruldu: %s chunk, %s səhifə, %s san (%s)", umumi, len(sehifeler), kecen, menbe)
    return {
        "chunk_sayi": umumi,
        "sehife_sayi": len(sehifeler),
        "menbe": menbe,
        "saniye": kecen,
    }


# ------------------------------------------------------------------ sual-cavab


def _kontekst(parcalar: list[dict]) -> str:
    setirler = []
    for nomre, parca in enumerate(parcalar, start=1):
        metn = " ".join((parca["metn"] or "").split())
        setirler.append(f"[{nomre}] Mənbə: {parca.get('url', '')}\n{metn}")
    return "\n\n".join(setirler)


def _menbeler(parcalar: list[dict]) -> list[dict]:
    gorulen: set[str] = set()
    neticeler = []
    for parca in parcalar:
        url = parca.get("url", "")
        if url in gorulen:
            continue
        gorulen.add(url)
        metn = " ".join((parca["metn"] or "").split())
        neticeler.append(
            {
                "url": url,
                "basliq": parca.get("basliq", "") or "",
                "parca": metn[:300],
                "bal": float(parca.get("rerank_bal", parca.get("rrf_bal", 0)) or 0),
            }
        )
    return neticeler


def cavab_ver(site_id: int, sual: str, session_id: int | None = None) -> dict:
    """Suala cavab verir və mənbələri göstərir."""
    basla = time.perf_counter()
    sohbet_id = memory.sohbet_tap_ve_ya_yarat(site_id, session_id)

    if store.chunk_sayi(site_id) == 0:
        return {
            "cavab": (
                "Bu sayt üçün məzmun bazası qurulmayıb — səhifələr yığılmayıb "
                "(sayt bot qoruması altında ola bilər)."
            ),
            "menbeler": [],
            "session_id": sohbet_id,
            "olcme": {},
        }

    # 1) Hibrid axtarış
    namizedler, emb_menbe = store.hibrid_axtar(site_id, sual)

    # 2) Re-ranking
    secilmis, rerank_olcme = reranker.sirala(sual, namizedler, ust=USTDEN_SECILEN)

    # 3) Yaddaş
    yaddas = memory.kontekst_metni(sohbet_id)
    yaddas_bloku = f"ƏVVƏLKİ SÖHBƏT:\n{yaddas}\n\n" if yaddas else ""

    # 4) Cavab — LCEL zənciri (prompt → model → parser)
    zencir, model_adi = chains.rag_cavab.zencir()
    if zencir is None:
        # Açar yoxdursa uydurmuruq — ən uyğun parçaları olduğu kimi göstəririk
        cavab = (
            "Model açarı təyin edilməyib, ona görə cavab yazıla bilmir. "
            "Suala ən uyğun tapılan parçalar aşağıdadır:\n\n"
            + "\n\n".join(f"• {' '.join(p['metn'].split())[:300]}" for p in secilmis[:3])
        )
    else:
        try:
            cavab = zencir.invoke(
                {
                    "yaddas": yaddas_bloku,
                    "kontekst": _kontekst(secilmis),
                    "sual": sual,
                }
            )
        except Exception as xeta:
            log.warning("Cavab zənciri sındı: %s", xeta)
            cavab = f"Cavab hazırlana bilmədi: {xeta}"

    # 5) Yaddaşa yaz
    memory.mesaj_yaz(sohbet_id, "istifadeci", sual)
    memory.mesaj_yaz(sohbet_id, "asistent", cavab, secilmis)

    return {
        "cavab": cavab.strip(),
        "menbeler": _menbeler(secilmis),
        "session_id": sohbet_id,
        "olcme": {
            "namized": len(namizedler),
            "secilmis": len(secilmis),
            "embedding": emb_menbe,
            "rerank": rerank_olcme,
            "model": model_adi,
            "umumi_saniye": round(time.perf_counter() - basla, 2),
        },
    }


__all__ = ["qur", "cavab_ver", "chunker", "embedder", "memory", "reranker", "store"]
