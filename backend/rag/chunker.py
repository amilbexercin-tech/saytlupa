"""Mətnin hissələrə (chunk) bölünməsi.

RAG-ın keyfiyyəti buradan asılıdır:
- çox kiçik parça → kontekst itir ("2-3 iş günü" cümləsi nəyə aiddir bilinmir)
- çox böyük parça → axtarış dəqiqliyi düşür, modelə lazımsız mətn gedir

Ona görə paraqraf sərhədlərinə hörmət edilir və parçalar bir-birinin üstünə
müəyyən qədər düşür (overlap) — cümlə iki parçanın arasında qalıb itməsin.
"""

from __future__ import annotations

import re

OLCU = 800          # hədəf parça ölçüsü (simvol)
UST_USTE = 120      # qonşu parçaların üst-üstə düşən hissəsi
MIN_OLCU = 100      # bundan kiçik parça saxlanmır

PARAQRAF = re.compile(r"\n\s*\n")
CUMLE_SONU = re.compile(r"(?<=[.!?…])\s+")


def _paraqraflar(metn: str) -> list[str]:
    return [p.strip() for p in PARAQRAF.split(metn) if p.strip()]


def _cumlelere_bol(paraqraf: str) -> list[str]:
    """Paraqraf tək başına çox böyükdürsə cümlələrə bölürük."""
    cumleler = [c.strip() for c in CUMLE_SONU.split(paraqraf) if c.strip()]
    return cumleler or [paraqraf]


def _quyruq(metn: str, uzunluq: int) -> str:
    """Parçanın son hissəsi — növbəti parçanın əvvəlinə qoyulur (overlap)."""
    if len(metn) <= uzunluq:
        return metn
    kesik = metn[-uzunluq:]
    # Sözün ortasından başlamayaq
    bosluq = kesik.find(" ")
    return kesik[bosluq + 1 :] if bosluq != -1 else kesik


def bol(metn: str, *, olcu: int = OLCU, ust_uste: int = UST_USTE) -> list[str]:
    """Mətni parçalara bölür."""
    metn = (metn or "").strip()
    if not metn:
        return []
    if len(metn) <= olcu:
        return [metn] if len(metn) >= MIN_OLCU else []

    parcalar: list[str] = []
    cari = ""

    def yaz() -> None:
        nonlocal cari
        if len(cari.strip()) >= MIN_OLCU:
            parcalar.append(cari.strip())

    for paraqraf in _paraqraflar(metn):
        # Paraqraf tək başına limitdən böyükdürsə cümlələrə bölürük
        hisseler = [paraqraf] if len(paraqraf) <= olcu else _cumlelere_bol(paraqraf)

        for hisse in hisseler:
            if len(cari) + len(hisse) + 1 <= olcu:
                cari = f"{cari}\n{hisse}" if cari else hisse
                continue

            yaz()
            # Yeni parça əvvəlkinin quyruğu ilə başlayır
            quyruq = _quyruq(cari, ust_uste) if cari else ""
            cari = f"{quyruq}\n{hisse}" if quyruq else hisse

            # Bir cümlə tək başına limitdən böyükdürsə zorla kəsirik
            while len(cari) > olcu * 1.5:
                parcalar.append(cari[:olcu].strip())
                cari = _quyruq(cari[:olcu], ust_uste) + cari[olcu:]

    yaz()
    return parcalar


def sehifeni_bol(sehife: dict) -> list[dict]:
    """Səhifəni parçalara bölür; hər parçaya başlıq kontekst kimi əlavə olunur.

    Başlıq əlavə etməyin səbəbi: "2-3 iş günü ərzində çatdırılır" parçası tək
    başına hansı sayta/bölməyə aid olduğunu bilmir. Başlıqla birlikdə həm
    embedding daha mənalı olur, həm də model cavab verəndə kontekst görür.
    """
    basliq = (sehife.get("basliq") or "").strip()
    parcalar = bol(sehife.get("metn") or "")

    neticeler = []
    for sira, parca in enumerate(parcalar):
        metn = f"{basliq}\n\n{parca}" if basliq else parca
        neticeler.append({"sira": sira, "metn": metn, "xam": parca})
    return neticeler
