"""Re-ranking parametrlərinin ölçülməsi.

Sual: neçə namizədi, neçə simvolla göndərmək lazımdır ki, həm dəqiq olsun,
həm də istifadəçi gözləyə bilsin?

İşə salma (server işləməlidir):
    py scripts/rerank_olcme.py <site_id> "sual"
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from backend.rag import reranker, store  # noqa: E402

# (namizəd sayı, parça uzunluğu)
VARIANTLAR = [(4, 200), (8, 200), (8, 400), (12, 200), (20, 400)]


def main() -> None:
    site_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sual = sys.argv[2] if len(sys.argv) > 2 else "Sifarişli xidmətlər hansılardır?"

    namizedler, emb = store.hibrid_axtar(site_id, sual, vektor_limit=25, acar_limit=15)
    print(f"Sual: {sual}")
    print(f"Embedding üsulu: {emb} · tapılan namizəd: {len(namizedler)}\n")

    if not namizedler:
        print("Namizəd tapılmadı — əvvəlcə saytı analiz et.")
        return

    print(f"{'Namizəd':>8}{'Simvol':>8}{'Vaxt':>10}{'Üsul':>10}   Ən yaxşı mənbə")
    print("-" * 90)

    kohne_max, kohne_parca = reranker.MAX_NAMIZED, reranker.PARCA_LIMITI
    try:
        for say, uzunluq in VARIANTLAR:
            reranker.MAX_NAMIZED = say
            reranker.PARCA_LIMITI = uzunluq

            basla = time.perf_counter()
            secilmis, olcme = reranker.sirala(sual, [dict(n) for n in namizedler], ust=3)
            kecen = time.perf_counter() - basla

            en_yaxsi = secilmis[0]["url"] if secilmis else "-"
            print(
                f"{say:>8}{uzunluq:>8}{kecen:>9.1f}s{olcme['usul']:>10}   {en_yaxsi[:52]}"
            )
    finally:
        reranker.MAX_NAMIZED, reranker.PARCA_LIMITI = kohne_max, kohne_parca


if __name__ == "__main__":
    main()
