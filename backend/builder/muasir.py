"""⚡ Müasir versiyanı qur — analizdən yeni, təmiz tək fayllıq sayt.

Zəncir `chains/muasir.py`-dədir; burada yalnız məlumatın yığılması, faylın
yazılması və nəticənin qaytarılması var.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..chains import muasir as zencir
from . import kontekst

log = logging.getLogger("saytlupa")

FAYL = "index.html"


def _qeyd_elave(html: str, url: str, model: str) -> str:
    """Faylın başına mənşə qeydi qoyur.

    Bu fayl AI tərəfindən yazılıb — sonradan kimsə onu saytın öz kodu ilə
    qarışdırmasın deyə mənbə, tarix və model açıq yazılır.
    """
    tarix = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    qeyd = (
        "<!--\n"
        f"  SaytLupa ilə yaradılıb — {tarix}\n"
        f"  Mənbə sayt: {url}\n"
        f"  Model: {model}\n"
        "  Bu, saytın kopyası DEYİL — analizə əsaslanan müasir versiya təklifidir.\n"
        "-->"
    )
    # Şərh <!doctype>-dan ƏVVƏL gəlsə bəzi brauzerlər quirks rejiminə keçir,
    # ona görə doctype varsa şərh ondan sonra qoyulur.
    if html.lower().startswith("<!doctype"):
        son = html.find(">") + 1
        return f"{html[:son]}\n{qeyd}{html[son:]}"
    return f"{qeyd}\n{html}"


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

    html = _qeyd_elave(netice["html"], k["url"], olcme["model"])
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
