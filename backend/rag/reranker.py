"""Re-ranking — namizəd parçaların yenidən sıralanması.

Vektor axtarışı 20-30 namizəd verir, amma onların sıralaması həmişə düzgün olmur.
Kiçik açıq model (Gemma 3 4B, lokal) hər namizədin suala nə dərəcədə cavab
verdiyini qiymətləndirir və ən yaxşı 5-i seçilir — Claude-a az, amma dəqiq
kontekst gedir.

**Niyə toplu (batch)?** Ölçmə göstərdi ki, Gemma çağırışı ~6 saniyə çəkir
(bax `docs/model-secimi.md`). 20 namizədi bir-bir qiymətləndirmək 2 dəqiqə
deməkdir — istifadəçi bu qədər gözləyə bilməz. Ona görə hamısı **bir promptda**
göndərilir və cavab JSON siyahı kimi alınır.

Gemma əlçatmazdırsa və ya cavabı oxunmursa, axtarışın öz sıralaması saxlanılır —
söhbət dayanmır.
"""

from __future__ import annotations

import logging
import time

from .. import llm
from ..config import ayarlar

log = logging.getLogger("saytlupa")

# Bu iki ədəd ölçmə ilə seçilib (bax `docs/model-secimi.md`).
# 20 namizəd × 400 simvol variantı bu maşında 173 saniyə çəkdi — istifadəyə yararsız.
PARCA_LIMITI = 200   # hər namizəddən modelə göndərilən simvol sayı
MAX_NAMIZED = 8      # qiymətləndirilən namizəd sayı
CIXIS_LIMITI = 300   # modelin yaza biləcəyi maksimum token — JSON qısadır

SISTEM = (
    "Sən axtarış nəticələrini qiymətləndirən köməkçisən. "
    "Yalnız JSON qaytar, başqa heç nə yazma."
)

SABLON = """SUAL: {sual}

Aşağıdakı mətn parçalarının hər birinin bu SUALA nə dərəcədə cavab verdiyini
0-dan 10-a qədər qiymətləndir (0 = tamamilə əlaqəsiz, 10 = suala birbaşa cavab verir).

{namizedler}

Cavabı dəqiq bu formatda JSON kimi qaytar:
{{"ballar": [{{"id": <parçanın nömrəsi>, "bal": <0-10>}}]}}

Hər parça üçün bir sətir olmalıdır. Başqa heç nə yazma."""


def _namized_metni(namizedler: list[dict]) -> str:
    setirler = []
    for nomre, namized in enumerate(namizedler, start=1):
        parca = " ".join((namized["metn"] or "").split())[:PARCA_LIMITI]
        setirler.append(f"[{nomre}] {parca}")
    return "\n\n".join(setirler)


def _ballari_oxu(cavab: dict | list, say: int) -> dict[int, float]:
    """Modelin cavabından {nömrə: bal} lüğəti çıxarır (müxtəlif formatlara dözümlü)."""
    xam = cavab.get("ballar", cavab) if isinstance(cavab, dict) else cavab
    if not isinstance(xam, list):
        return {}

    ballar: dict[int, float] = {}
    for qeyd in xam:
        if not isinstance(qeyd, dict):
            continue
        try:
            nomre = int(qeyd.get("id", qeyd.get("nomre", 0)))
            bal = float(qeyd.get("bal", qeyd.get("score", 0)))
        except (TypeError, ValueError):
            continue
        if 1 <= nomre <= say:
            ballar[nomre] = max(0.0, min(bal, 10.0))
    return ballar


def _model(menbe: str):
    """Re-ranking modelini seçir."""
    if menbe == "gemma":
        return llm.gemma(max_token=CIXIS_LIMITI, json_cixis=True), ayarlar.gemma_model
    if menbe == "gemini":
        return llm.gemini(temperatur=0.0), ayarlar.gemini_model
    return None, ""


def sirala(
    sual: str, namizedler: list[dict], *, ust: int = 5, menbe: str | None = None
) -> tuple[list[dict], dict]:
    """Namizədləri yenidən sıralayır.

    `menbe`: "gemma" | "gemini" | "" (söndürülüb). Verilməsə `.env`-dəki dəyər.
    Qaytarır: (seçilmiş parçalar, ölçmə məlumatı)
    """
    menbe = ayarlar.rerank if menbe is None else menbe
    olcme = {"usul": "axtaris_sirasi", "model": "", "saniye": 0.0, "namized": len(namizedler)}

    if not namizedler:
        return [], olcme

    if not menbe:
        return namizedler[:ust], olcme

    namizedler = namizedler[:MAX_NAMIZED]
    model, model_adi = _model(menbe)

    if model is None:
        log.info("'%s' re-ranking modeli əlçatmazdır — axtarış sırası saxlanılır", menbe)
        return namizedler[:ust], olcme

    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_messages(
        [("system", SISTEM), ("human", SABLON)]
    )
    # LCEL: prompt → model → JSON parser
    zencir = prompt | model | JsonOutputParser()

    basla = time.perf_counter()
    try:
        cavab = zencir.invoke(
            {"sual": sual, "namizedler": _namized_metni(namizedler)}
        )
        ballar = _ballari_oxu(cavab, len(namizedler))
    except Exception as xeta:
        log.warning("Re-ranking alınmadı (%s) — axtarış sırası saxlanılır", xeta)
        olcme["saniye"] = round(time.perf_counter() - basla, 2)
        olcme["xeta"] = str(xeta)[:200]
        return namizedler[:ust], olcme

    olcme["saniye"] = round(time.perf_counter() - basla, 2)

    if not ballar:
        log.warning("Model oxunaqlı bal qaytarmadı — axtarış sırası saxlanılır")
        return namizedler[:ust], olcme

    olcme["usul"] = menbe
    olcme["model"] = model_adi
    olcme["ballanan"] = len(ballar)

    for nomre, namized in enumerate(namizedler, start=1):
        namized["rerank_bal"] = ballar.get(nomre, 0.0)

    sirali = sorted(namizedler, key=lambda n: -n.get("rerank_bal", 0.0))
    # Tamamilə əlaqəsiz sayılanları (0 bal) kontekstə salmırıq
    faydali = [n for n in sirali if n.get("rerank_bal", 0) > 0] or sirali
    return faydali[:ust], olcme
