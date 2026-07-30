"""Müasir versiya zənciri (LCEL) — analizdən tək fayllıq HTML.

Zəncirin quruluşu:

    {url, xam analiz, məzmun nümunələri}
        │
        ├─ RunnableParallel ──► url
        │                   ├─► melumat  (xam JSON → oxunaqlı xülasə + AI rəy)
        │                   └─► mezmun   (saytdan yığılmış real mətnlər)
        │
        ▼
    ChatPromptTemplate (System + Human)
        │
        ▼
    Model  (Claude → Gemini; **Gemma daxil deyil**)
        │
        ▼
    StrOutputParser → temizle()   ← ``` çərçivəsi atılır, HTML kəsilib götürülür

Gemma bu zəncirdən qəsdən çıxarılıb: 1-2 min sətirlik HTML yazmaq lokal modellə
bu maşında dəqiqələrlə çəkir və nəticə istifadəyə yararsız olur.
"""

from __future__ import annotations

import logging
import re
import time

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel

from ..prompts import muasir as prompt_metni
from .hesabat import xulase_qur
from .model import guclu_model_var, model_adi, model_zenciri

log = logging.getLogger("saytlupa")

MAX_TOKEN = 8000          # tam səhifə HTML-i üçün
MEZMUN_LIMITI = 6         # neçə səhifənin mətni modelə verilir
MEZMUN_UZUNLUGU = 1200    # hər səhifədən neçə simvol

CERCIVE = re.compile(r"^```[a-zA-Z]*\n|\n```$")


# ------------------------------------------------------------ modelin cavabı


def temizle(cavab: str) -> str:
    """Modelin cavabından təmiz HTML çıxarır.

    Model bəzən HTML-i ``` çərçivəsinə salır, bəzən qabağına "Budur:" kimi
    bir cümlə yazır. Hər ikisi atılır; HTML tapılmasa xəta qaldırılır.
    """
    metn = (cavab or "").strip()
    metn = CERCIVE.sub("", metn).strip()

    # ``` çərçivəsi mətnin ortasındadırsa içindəkini götürürük
    blok = re.search(r"```(?:html)?\s*\n(.*?)\n```", metn, re.DOTALL)
    if blok:
        metn = blok.group(1).strip()

    asagi = metn.lower()
    for baslangic in ("<!doctype", "<html"):
        yer = asagi.find(baslangic)
        if yer != -1:
            return metn[yer:].strip()

    if "<body" in asagi or "<section" in asagi:
        return metn  # tam sənəd deyil, amma HTML-dir — olduğu kimi saxlayırıq

    raise ValueError("Model HTML qaytarmadı")


def _mezmun_metni(sehifeler: list[dict]) -> str:
    """Yığılmış səhifələrdən modelə veriləcək real məzmun nümunələri.

    Uydurma mətn yazılmasın deyə model saytın **öz** cümlələrini görməlidir.
    """
    if not sehifeler:
        return "(məzmun yığılmayıb — sayt bot qoruması arxasında ola bilər)"

    parcalar = []
    for sehife in sehifeler[:MEZMUN_LIMITI]:
        metn = (sehife.get("metn") or "")[:MEZMUN_UZUNLUGU]
        parcalar.append(
            f"### {sehife.get('basliq') or sehife.get('url', '')}\n"
            f"{sehife.get('url', '')}\n{metn}"
        )
    return "\n\n".join(parcalar)


def _melumat_metni(xam: dict, ai_hesabat: dict | None) -> str:
    """Xam analizin xülasəsi + (varsa) AI hesabatın tövsiyələri."""
    setirler = [xulase_qur(xam)]

    if ai_hesabat:
        setirler.append("\n## AI hesabatın qeydləri")
        for sahe, basliq in (
            ("meqsed", "Saytın məqsədi"),
            ("hedef_auditoriya", "Hədəf auditoriya"),
        ):
            if ai_hesabat.get(sahe):
                setirler.append(f"- {basliq}: {ai_hesabat[sahe]}")
        for sahe, basliq in (
            ("performans_problemleri", "Düzəldiləsi performans problemləri"),
            ("seo_catismazliqlari", "Düzəldiləsi SEO çatışmazlıqları"),
            ("muasir_versiya_tovsiyeleri", "Müasir versiya üçün tövsiyələr"),
        ):
            deyerler = ai_hesabat.get(sahe) or []
            if deyerler:
                setirler.append(f"\n### {basliq}")
                setirler += [f"- {d}" for d in deyerler]

    return "\n".join(setirler)


# ------------------------------------------------------------------ zəncir


def zencir(temperatur: float = 0.4):
    """Müasir versiya zəncirini qurur (LCEL). Model yoxdursa `None`."""
    model = model_zenciri(temperatur, max_token=MAX_TOKEN, gemma_daxil=False)
    if model is None:
        return None, "yoxdur"

    prompt = ChatPromptTemplate.from_messages(
        [("system", prompt_metni.SISTEM), ("human", prompt_metni.INSAN)]
    )

    hazirliq = RunnableParallel(
        url=RunnableLambda(lambda x: x["url"]),
        melumat=RunnableLambda(lambda x: _melumat_metni(x["xam"], x.get("hesabat"))),
        mezmun=RunnableLambda(lambda x: _mezmun_metni(x.get("sehifeler") or [])),
    )

    return (
        hazirliq | prompt | model | StrOutputParser() | RunnableLambda(temizle)
    ), model_adi(model)


def yarat(
    url: str,
    xam: dict,
    sehifeler: list[dict] | None = None,
    ai_hesabat: dict | None = None,
) -> dict:
    """Müasir versiyanı yazdırır. Nəticə: {"html": str|None, "olcme": {...}}"""
    olcme: dict = {"model": "yoxdur", "saniye": 0.0, "ugurlu": False}

    if not guclu_model_var():
        olcme["sebeb"] = (
            "Bu düymə üçün Claude və ya Gemini açarı lazımdır. Lokal Gemma tam "
            "səhifə HTML-i yazmaqda bu maşında dəqiqələrlə çəkir və nəticə "
            "istifadəyə yararsız olur. Açarı `.env`-ə yaz — düymə öz-özünə işə düşəcək."
        )
        return {"html": None, "olcme": olcme}

    qurulan, ad = zencir()
    if qurulan is None:
        olcme["sebeb"] = "Heç bir model əlçatan deyil."
        return {"html": None, "olcme": olcme}

    olcme["model"] = ad
    basla = time.perf_counter()
    html: str | None = None
    try:
        html = qurulan.invoke(
            {"url": url, "xam": xam, "sehifeler": sehifeler or [], "hesabat": ai_hesabat}
        )
        olcme["ugurlu"] = True
        olcme["olcu_kb"] = round(len(html.encode("utf-8")) / 1024, 1)
    except Exception as xeta:
        log.warning("Müasir versiya zənciri sındı: %s", xeta)
        olcme["sebeb"] = str(xeta)[:300]

    olcme["saniye"] = round(time.perf_counter() - basla, 2)
    return {"html": html, "olcme": olcme}
