"""Model provayderləri — Claude, Gemini, Gemma bir interfeys altında.

Heç bir açar olmasa da layihə işləyir: söhbət modelləri "mock" rejimə,
embedding isə lokal ehtiyat üsuluna keçir.
"""

from __future__ import annotations

import logging

import httpx

from .config import ayarlar

log = logging.getLogger("saytlupa")

EMBEDDING_OLCUSU = 768


# ------------------------------------------------------------- söhbət modelləri


def claude(temperatur: float = 0.2, max_token: int = 4000):
    """Əsas düşünən model — AI hesabat, RAG cavabı, kod yazma.

    `temperatur` qəsdən ötürülmür: `claude-sonnet-5` bu parametri qəbul etmir və
    `400 — "temperature is deprecated for this model"` qaytarır (2026-07-29-da
    yoxlandı). Parametr imzada qalır ki, çağıran tərəf bütün modellər üçün eyni
    interfeysi işlətsin — Gemini və Gemma onu hələ də istifadə edir.
    """
    if not ayarlar.claude_var:
        return None
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=ayarlar.claude_model,
        api_key=ayarlar.anthropic_api_key,
        max_tokens=max_token,
        timeout=120,
    )


def gemini(temperatur: float = 0.2):
    """Ehtiyat mətn modeli."""
    if not ayarlar.gemini_var:
        return None
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=ayarlar.gemini_model,
        google_api_key=ayarlar.google_api_key,
        temperature=temperatur,
    )


def gemma(
    temperatur: float = 0.0,
    *,
    max_token: int | None = None,
    json_cixis: bool = False,
):
    """Lokal açıq model — re-ranking, təsnifat, ucuz kütləvi iş.

    `num_predict` və `format` Ollama parametrləridir və konstruktorda verilməlidir
    (`bind()` ilə ötürülmür — `Client.chat()` onları qəbul etmir).
    """
    if not gemma_hazirdir():
        return None
    from langchain_ollama import ChatOllama

    parametrler: dict = {
        "model": ayarlar.gemma_model,
        "base_url": ayarlar.ollama_base_url,
        "temperature": temperatur,
    }
    if max_token:
        parametrler["num_predict"] = max_token
    if json_cixis:
        parametrler["format"] = "json"

    return ChatOllama(**parametrler)


def gemma_hazirdir() -> bool:
    """Ollama işləyirmi və seçilmiş Gemma modeli yüklənibmi?"""
    try:
        cavab = httpx.get(f"{ayarlar.ollama_base_url}/api/tags", timeout=2)
        adlar = [m.get("name", "") for m in cavab.json().get("models", [])]
        return ayarlar.gemma_model in adlar
    except Exception:
        return False


def esas_model(temperatur: float = 0.2):
    """Claude → Gemini → Gemma ardıcıllığı ilə ilk mövcud model."""
    for qurucu in (lambda: claude(temperatur), lambda: gemini(temperatur), lambda: gemma(temperatur)):
        model = qurucu()
        if model is not None:
            return model
    return None


def veziyyet() -> dict:
    return {
        "claude": ayarlar.claude_var,
        "gemini": ayarlar.gemini_var,
        "gemma": gemma_hazirdir(),
        "gemma_model": ayarlar.gemma_model,
    }
