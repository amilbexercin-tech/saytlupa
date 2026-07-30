"""LangChain zəncirləri (LCEL).

Hər zəncir eyni quruluşdadır: **prompt → model → parser**, `|` operatoru ilə
birləşdirilir. Model həmişə fallback zənciridir (Claude → Gemini → Gemma).

| Zəncir | Fayl | Nə edir |
|---|---|---|
| Hesabat | `hesabat.py` | Xam analiz → 6 bəndlik AI rəy (JSON, sxem yoxlanışı ilə) |
| RAG cavab | `rag_cavab.py` | Sual + mənbələr + yaddaş → mətn cavab |
| Müasir versiya | `muasir.py` | Analiz → tək fayllıq HTML (Gemma-sız) |
"""

from . import hesabat, muasir, rag_cavab
from .model import guclu_model_var, model_adi, model_zenciri

__all__ = [
    "hesabat",
    "muasir",
    "rag_cavab",
    "model_zenciri",
    "model_adi",
    "guclu_model_var",
]
