"""nuclei JSONL çıxışını SaytLupa finding sxeminə çevirir.

Ortaq modul: həm worker (`scripts/aktiv_worker.py`), həm də test import edir.
Şəbəkəsizdir — yalnız çevirmə.

nuclei hər tapıntını bir JSON sətri kimi verir (`-jsonl`). Əsas sahələr:
`template-id`, `info` (name/severity/description/remediation/reference/
classification), `matched-at`, `extracted-results`.
"""

from __future__ import annotations

import json
from typing import Any

# nuclei severity → SaytLupa səviyyəsi
SEVIYYE = {
    "critical": "kritik",
    "high": "yuksek",
    "medium": "orta",
    "low": "asagi",
    "info": "melumat",
    "unknown": "melumat",
}


def _istinad(info: dict) -> list[str]:
    """CVE + reference linklərini bir siyahıda toplayır."""
    istinadlar: list[str] = []
    klass = info.get("classification") or {}
    for acar in ("cve-id", "cwe-id"):
        deyer = klass.get(acar)
        if isinstance(deyer, list):
            istinadlar += [str(x).upper() for x in deyer if x]
        elif deyer:
            istinadlar.append(str(deyer).upper())
    ref = info.get("reference")
    if isinstance(ref, list):
        istinadlar += [str(x) for x in ref if x]
    elif ref:
        istinadlar.append(str(ref))
    # Təkrarları at, sırasını saxla
    return list(dict.fromkeys(istinadlar))[:8]


def bir_tapinti(qeyd: dict) -> dict | None:
    """Bir nuclei JSON qeydini finding lüğətinə çevirir (uğursuzsa None)."""
    if not isinstance(qeyd, dict):
        return None
    info = qeyd.get("info") or {}
    ad = info.get("name") or qeyd.get("template-id")
    if not ad:
        return None

    sev = str(info.get("severity", "unknown")).lower()
    seviyye = SEVIYYE.get(sev, "melumat")

    harada = qeyd.get("matched-at") or qeyd.get("host") or ""
    cixarilan = qeyd.get("extracted-results") or []
    subut = harada
    if cixarilan:
        subut = f"{harada} → {', '.join(str(x) for x in cixarilan)[:200]}"

    risk = info.get("description") or "nuclei şablonu uyğunluq tapdı."
    hell = info.get("remediation") or (
        "Bu zəifliyi aradan qaldır: müvafiq komponenti yenilə/konfiqurasiyanı düzəlt "
        "(ətraflı üçün aşağıdakı istinadlara bax)."
    )

    return {
        "id": f"aktiv:{qeyd.get('template-id', ad)}:{harada}"[:200],
        "ad": str(ad),
        "seviyye": seviyye,
        "tapinti": f"nuclei tapdı: {harada}" if harada else "nuclei uyğunluq tapdı.",
        "risk": str(risk)[:600],
        "hell": str(hell)[:600],
        "subut": str(subut)[:400],
        "sablon": qeyd.get("template-id", ""),
        "istinad": _istinad(info),
        "menbe": "aktiv",
    }


def parse_jsonl(metn: str) -> list[dict]:
    """nuclei `-jsonl` çıxışını (çox sətir) finding siyahısına çevirir."""
    tapintilar: list[dict] = []
    for setir in (metn or "").splitlines():
        setir = setir.strip()
        if not setir:
            continue
        try:
            qeyd = json.loads(setir)
        except json.JSONDecodeError:
            continue
        t = bir_tapinti(qeyd)
        if t:
            tapintilar.append(t)
    return tapintilar
