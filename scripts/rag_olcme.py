"""RAG keyfiyyətinin ölçülməsi.

Sual: hibrid axtarış nə qədər dəqiqdir və re-ranking onu yaxşılaşdırırmı?

Ölçmə dəsti `docs/olcme-desti.json` faylındadır: hər sualın yanında hansı
səhifədə cavabın olduğu göstərilib. Ölçülən göstəricilər:

- **Hit@1** — birinci nəticə düzgün səhifədəndirmi
- **Hit@3** — ilk üç nəticədə düzgün səhifə varmı
- **MRR**   — düzgün nəticənin sırasının tərs ortalaması (1.0 = həmişə birinci)

İşə salma:
    py scripts/rag_olcme.py <site_id>
    py scripts/rag_olcme.py <site_id> gemma      # re-ranking ilə
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from backend.rag import reranker, store  # noqa: E402

DEST_FAYLI = KOK / "docs" / "olcme-desti.json"


def dest_oxu() -> list[dict]:
    if not DEST_FAYLI.exists():
        print(f"Ölçmə dəsti tapılmadı: {DEST_FAYLI}")
        sys.exit(1)
    return json.loads(DEST_FAYLI.read_text(encoding="utf-8"))


def sira_tap(neticeler: list[dict], gozlenilen: str) -> int | None:
    """Düzgün səhifə neçənci sıradadır? (1-dən başlayaraq; tapılmasa None)"""
    for sira, netice in enumerate(neticeler, start=1):
        if gozlenilen in (netice.get("url") or ""):
            return sira
    return None


def olc(site_id: int, menbe: str) -> dict:
    dest = dest_oxu()
    siralar: list[int | None] = []
    vaxtlar: list[float] = []

    baslik = f"re-ranking: {menbe or 'YOX'}"
    print(f"\n{'=' * 78}\n{baslik}\n{'=' * 78}")

    for qeyd in dest:
        basla = time.perf_counter()
        namizedler, _ = store.hibrid_axtar(site_id, qeyd["sual"])
        secilmis, _ = reranker.sirala(qeyd["sual"], namizedler, ust=5, menbe=menbe)
        kecen = time.perf_counter() - basla

        sira = sira_tap(secilmis, qeyd["gozlenilen_url"])
        siralar.append(sira)
        vaxtlar.append(kecen)

        isare = "✓" if sira == 1 else ("~" if sira else "✗")
        yer = f"sıra {sira}" if sira else "TAPILMADI"
        print(f"  {isare} {qeyd['sual'][:48]:<50} {yer:<12} {kecen:>6.1f}s")

    tapilan = [s for s in siralar if s]
    return {
        "menbe": menbe or "yox",
        "sual_sayi": len(dest),
        "hit1": sum(1 for s in siralar if s == 1),
        "hit3": sum(1 for s in tapilan if s <= 3),
        "mrr": round(statistics.mean([1 / s for s in siralar if s] + [0] * (len(siralar) - len(tapilan))), 3),
        "orta_vaxt": round(statistics.mean(vaxtlar), 1),
    }


def main() -> None:
    site_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    menbeler = sys.argv[2:] or ["", "gemma"]

    neticeler = [olc(site_id, m) for m in menbeler]

    print(f"\n{'=' * 78}")
    print(f"{'Re-ranking':<14}{'Hit@1':>10}{'Hit@3':>10}{'MRR':>10}{'Orta vaxt':>12}")
    print("-" * 78)
    for n in neticeler:
        print(
            f"{n['menbe']:<14}"
            f"{f'{n['hit1']}/{n['sual_sayi']}':>10}"
            f"{f'{n['hit3']}/{n['sual_sayi']}':>10}"
            f"{n['mrr']:>10}"
            f"{f'{n['orta_vaxt']}s':>12}"
        )
    print("=" * 78)

    cixis = KOK / "docs" / "rag-olcme-neticesi.json"
    cixis.write_text(json.dumps(neticeler, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nNəticə yazıldı: {cixis}")


if __name__ == "__main__":
    main()
