"""RAG cavab zənciri (LCEL).

    {sual, kontekst, yaddaş}
        │
        ▼
    ChatPromptTemplate  (System: "yalnız mənbələrə əsaslan" + Human)
        │
        ▼
    Model  (Claude → Gemini → Gemma fallback)
        │
        ▼
    StrOutputParser
"""

from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ..prompts import rag as prompt_metni
from .model import model_adi, model_zenciri


def zencir(temperatur: float = 0.1):
    """Cavab zəncirini qurur. Model yoxdursa `(None, "yoxdur")`."""
    model = model_zenciri(temperatur, max_token=1200)
    if model is None:
        return None, "yoxdur"

    prompt = ChatPromptTemplate.from_messages(
        [("system", prompt_metni.SISTEM), ("human", prompt_metni.INSAN)]
    )
    return prompt | model | StrOutputParser(), model_adi(model)
