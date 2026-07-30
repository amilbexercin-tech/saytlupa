"""Təhvil funksiyaları — 9-cu günün dörd düyməsi.

| Düymə | Modul | Nəticə |
|---|---|---|
| ⚡ Müasir versiyanı qur | `muasir.py` | `storage/modern/<domain>/index.html` |
| 🧬 Tam klon üçün hazırla | `klon.py` | `storage/klon/<domain>/docs/research/*.md` |
| 📦 Səhifə arşivi | `arsiv.py` | `storage/archives/<domain>/` + `.zip` |
| 📄 PDF hesabat | `pdf.py` | `storage/pdf/<domain>/hesabat.pdf` |

Hamısı eyni müqavilə ilə işləyir: `analiz_id` alır, lüğət qaytarır. Analiz
tapılmasa `{"ugurlu": False, "tapilmadi": True}` gəlir — REST qatı bunu 404-ə
çevirir. Digər uğursuzluqlarda `sebeb` sahəsi doldurulur; heç bir düymə xəta
qaldırıb interfeysi qırmır.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..config import STORAGE
from . import arsiv, klon, kontekst, muasir, pdf

__all__ = ["muasir", "klon", "arsiv", "pdf", "kontekst", "yukle_yolu"]

# nov → (fayl yolunu quran funksiya, yüklənmə adının sonluğu)
YUKLEME = {
    "muasir": lambda ad: (STORAGE / "modern" / ad / muasir.FAYL, f"{ad}-muasir.html"),
    "pdf": lambda ad: (STORAGE / "pdf" / ad / pdf.FAYL, f"{ad}-hesabat.pdf"),
    "arsiv": lambda ad: (STORAGE / "archives" / f"{ad}.zip", f"{ad}-arsiv.zip"),
    "klon": lambda ad: (STORAGE / "klon" / f"{ad}.zip", f"{ad}-klon.zip"),
}


def yukle_yolu(nov: str, analiz_id: int) -> tuple[Path, str] | None:
    """Yüklənəcək faylın yolu və adı. Fayl hazır deyilsə `None`.

    Klon sənədləri qovluqdur — yükləmə anında ZIP-ə yığılır.
    """
    if nov not in YUKLEME:
        return None
    kim = kontekst.kimlik(analiz_id)
    if kim is None:
        return None

    ad = kontekst.temiz_ad(kim["domain"])
    yol, yukleme_adi = YUKLEME[nov](ad)

    if nov == "klon" and not yol.exists():
        qovluq = STORAGE / "klon" / ad
        if not qovluq.is_dir():
            return None
        shutil.make_archive(str(STORAGE / "klon" / ad), "zip", str(qovluq))

    return (yol, yukleme_adi) if yol.exists() else None
