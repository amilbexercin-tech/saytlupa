"""Model müqayisəsi — hansı model hansı işə uyğundur?

RAG-da re-ranking kütləvi işdir: hər sual üçün 20 namizəd qiymətləndirilir.
Bunu ən güclü modelə vermək bahadır və yavaşdır. Bu skript ölçür ki, kiçik açıq
modellər (Gemma) bu işi kifayət qədər yaxşı görürmü.

İşə salma:
    py scripts/model_olcme.py                # bütün mövcud modellər
    py scripts/model_olcme.py gemma3:4b      # yalnız biri
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import httpx

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from backend.config import ayarlar  # noqa: E402

CAGIRIS_LIMITI = 120  # saniyə — bundan uzun çəkən model istifadəyə yararsızdır

# Sual + parça + doğru bal (0 = əlaqəsiz, 10 = tam cavab)
OLCME_DESTI: list[tuple[str, str, int]] = [
    ("çatdırılma neçə gün çəkir?",
     "Sifarişlər 2-3 iş günü ərzində çatdırılır.", 10),
    ("çatdırılma neçə gün çəkir?",
     "Şirkətimiz 2015-ci ildən fəaliyyət göstərir.", 0),
    ("çatdırılma neçə gün çəkir?",
     "Çatdırılma Bakı daxilində pulsuzdur, regionlara 5 AZN.", 6),
    ("məhsulun zəmanəti nə qədərdir?",
     "Bütün məhsullara 12 ay rəsmi zəmanət verilir.", 10),
    ("məhsulun zəmanəti nə qədərdir?",
     "Ödəniş kartla və ya nağd şəkildə edilir.", 0),
    ("hansı ödəniş üsulları var?",
     "Ödəniş kartla, nağd və ya hissə-hissə edilə bilər.", 10),
    ("hansı ödəniş üsulları var?",
     "Mağazamız Nizami küçəsi 12 ünvanında yerləşir.", 0),
    ("mağaza haradadır?",
     "Mağazamız Nizami küçəsi 12 ünvanında yerləşir.", 10),
]

PROMPT = """Sən axtarış nəticələrini qiymətləndirən köməkçisən.
Aşağıdakı MƏTN verilmiş SUALA nə dərəcədə cavab verir?

SUAL: {sual}
MƏTN: {parca}

0-dan 10-a qədər bir rəqəm yaz. Yalnız rəqəm yaz, başqa heç nə yazma.
Bal:"""


def modelleri_tap() -> list[str]:
    cavab = httpx.get(f"{ayarlar.ollama_base_url}/api/tags", timeout=5)
    return [m["name"] for m in cavab.json().get("models", [])]


def bal_cixar(metn: str) -> int | None:
    """Modelin cavabından ilk rəqəmi çıxarır."""
    reqem = ""
    for simvol in metn.strip():
        if simvol.isdigit():
            reqem += simvol
        elif reqem:
            break
    if not reqem:
        return None
    return min(int(reqem), 10)


def bir_cagiris(model: str, sual: str, parca: str) -> tuple[int | None, float]:
    govde = {
        "model": model,
        "prompt": PROMPT.format(sual=sual, parca=parca),
        "stream": False,
        "options": {"temperature": 0, "num_predict": 6},
    }
    basla = time.perf_counter()
    try:
        cavab = httpx.post(
            f"{ayarlar.ollama_base_url}/api/generate",
            json=govde,
            timeout=CAGIRIS_LIMITI,
        )
        kecen = time.perf_counter() - basla
        return bal_cixar(cavab.json().get("response", "")), kecen
    except Exception:
        return None, time.perf_counter() - basla


def modeli_olc(model: str) -> dict:
    print(f"\n  {model} ölçülür ({len(OLCME_DESTI)} sual)...", flush=True)
    vaxtlar: list[float] = []
    sehvler: list[int] = []
    cavabsiz = 0

    for sual, parca, dogru in OLCME_DESTI:
        bal, vaxt = bir_cagiris(model, sual, parca)
        vaxtlar.append(vaxt)
        if bal is None:
            cavabsiz += 1
            print(f"    ✗ cavab yoxdur ({vaxt:.1f}s)")
            continue
        sehv = abs(bal - dogru)
        sehvler.append(sehv)
        isare = "✓" if sehv <= 3 else "✗"
        print(f"    {isare} bal={bal:<3} doğru={dogru:<3} fərq={sehv:<3} ({vaxt:.1f}s)")

        if vaxt > CAGIRIS_LIMITI * 0.9:
            print("    (çox yavaş — ölçmə dayandırılır)")
            break

    duzgun = sum(1 for s in sehvler if s <= 3)
    return {
        "model": model,
        "orta_vaxt": round(statistics.mean(vaxtlar), 2) if vaxtlar else None,
        "orta_sehv": round(statistics.mean(sehvler), 2) if sehvler else None,
        "duzgun": duzgun,
        "cemi": len(OLCME_DESTI),
        "cavabsiz": cavabsiz,
        "deqiqlik_faiz": round(100 * duzgun / len(OLCME_DESTI)),
    }


def main() -> None:
    istenilen = sys.argv[1:]
    movcud = modelleri_tap()
    modeller = istenilen or [m for m in movcud if "gemma" in m]

    print("Ollama-dakı modellər:", ", ".join(movcud))
    print("Ölçüləcək:", ", ".join(modeller))
    print("Meyar: |bal - doğru| ≤ 3 olsa 'düzgün' sayılır")

    neticeler = [modeli_olc(m) for m in modeller]

    print("\n" + "=" * 72)
    print(f"{'Model':<16}{'Dəqiqlik':>12}{'Orta fərq':>12}{'Orta vaxt':>12}{'Cavabsız':>12}")
    print("-" * 72)
    for n in sorted(neticeler, key=lambda x: -(x["deqiqlik_faiz"])):
        print(
            f"{n['model']:<16}"
            f"{str(n['deqiqlik_faiz']) + '%':>12}"
            f"{str(n['orta_sehv']):>12}"
            f"{str(n['orta_vaxt']) + 's':>12}"
            f"{n['cavabsiz']:>12}"
        )
    print("=" * 72)

    # Köhnə nəticələri saxlayırıq — hər model ayrıca ölçülə bilsin deyə
    cixis = KOK / "docs" / "model-olcme-neticesi.json"
    kohne: dict[str, dict] = {}
    if cixis.exists():
        try:
            kohne = {n["model"]: n for n in json.loads(cixis.read_text(encoding="utf-8"))}
        except Exception:
            kohne = {}

    for n in neticeler:
        kohne[n["model"]] = n

    cixis.write_text(
        json.dumps(list(kohne.values()), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nNəticə yazıldı: {cixis}  ({len(kohne)} model)")


if __name__ == "__main__":
    main()
