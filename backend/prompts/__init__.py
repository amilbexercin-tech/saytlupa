"""Promptlar ayrıca saxlanılır.

Səbəb: prompt məhsulun davranışını kod qədər müəyyən edir. Kodun içinə
səpələnsə, dəyişdirmək və müqayisə etmək çətinləşir. Burada hər prompt
adlandırılıb, şərhlə izah olunub və bir yerdən idarə olunur.
"""

from . import hesabat, muasir, rag

__all__ = ["hesabat", "rag", "muasir"]
