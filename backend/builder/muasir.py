"""⚡ Müasir versiyanı qur — analizdən yeni, təmiz tək fayllıq sayt.

Zəncir `chains/muasir.py`-dədir; burada yalnız məlumatın yığılması, faylın
yazılması və nəticənin qaytarılması var.
"""

from __future__ import annotations

import logging

from ..chains import muasir as zencir
from . import kontekst

log = logging.getLogger("saytlupa")

FAYL = "index.html"


def qur(analiz_id: int) -> dict:
    """Müasir versiyanı yazdırıb `storage/modern/<domain>/index.html`-ə saxlayır."""
    k = kontekst.konteks(analiz_id)
    if k is None:
        return {"ugurlu": False, "tapilmadi": True, "sebeb": "Belə analiz yoxdur"}

    netice = zencir.yarat(
        k["url"], k["xam"], sehifeler=k["sehifeler"], ai_hesabat=k["ai_hesabat"]
    )
    olcme = netice["olcme"]

    if not netice["html"]:
        return {"ugurlu": False, "sebeb": olcme.get("sebeb", ""), "olcme": olcme}

    html = netice["html"]
    yol = kontekst.qovluq("muasir", k["domain"]) / FAYL
    yol.write_text(html, encoding="utf-8")
    log.info("Müasir versiya yazıldı: %s (%s KB)", yol, olcme.get("olcu_kb"))

    return {
        "ugurlu": True,
        "fayl": str(yol),
        "olcu_kb": round(len(html.encode("utf-8")) / 1024, 1),
        "onizleme_url": f"/api/analyze/{analiz_id}/muasir/onizleme",
        "yukle_url": f"/api/analyze/{analiz_id}/yukle/muasir",
        "olcme": olcme,
    }
