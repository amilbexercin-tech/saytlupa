"""Zəncirlərdə işlədilən model — fallback ilə.

LangChain-in `with_fallbacks` mexanizmi: əsas model sınsa (açar yoxdur, kvota
bitib, şəbəkə xətası) zəncir avtomatik növbəti modelə keçir. Bu, layihənin
"heç nə çökmür" prinsipini model səviyyəsində təmin edir.

Sıra: **Claude → Gemini → Gemma (lokal)**
"""

from __future__ import annotations

import logging

from .. import llm

log = logging.getLogger("saytlupa")


def model_zenciri(
    temperatur: float = 0.2,
    *,
    max_token: int = 4000,
    gemma_daxil: bool = True,
):
    """Mövcud modellərdən fallback zənciri qurur.

    Heç bir model yoxdursa `None` qaytarır — çağıran tərəf bunu yoxlamalıdır.
    """
    esas = llm.claude(temperatur, max_token)
    ehtiyatlar = []

    gemini = llm.gemini(temperatur)
    if gemini is not None:
        ehtiyatlar.append(gemini)

    if gemma_daxil:
        gemma = llm.gemma(temperatur, max_token=max_token)
        if gemma is not None:
            ehtiyatlar.append(gemma)

    if esas is None:
        if not ehtiyatlar:
            return None
        esas, ehtiyatlar = ehtiyatlar[0], ehtiyatlar[1:]

    return esas.with_fallbacks(ehtiyatlar) if ehtiyatlar else esas


def model_adi(model) -> str:
    """Loq və ölçmə üçün modelin adı."""
    if model is None:
        return "yoxdur"
    for sahe in ("model", "model_name"):
        deyer = getattr(model, sahe, None)
        if isinstance(deyer, str):
            return deyer
    # with_fallbacks nəticəsi RunnableWithFallbacks-dir — içindəkinə baxırıq
    icerik = getattr(model, "runnable", None)
    return model_adi(icerik) if icerik is not None else type(model).__name__


def guclu_model_var() -> bool:
    """Claude və ya Gemini mövcuddurmu?

    Uzun mətn yazan işlər (AI hesabat, müasir versiya) yalnız bunlarla
    mənalıdır — lokal Gemma bu maşında dəqiqələrlə çəkir.
    """
    return llm.ayarlar.claude_var or llm.ayarlar.gemini_var
