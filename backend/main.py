"""FastAPI tətbiqi — SaytLupa.

Gün 1: skelet · Gün 2-3: toplayıcılar · Gün 4: analiz axını + SSE canlı gedişat
Gün 5-7: RAG və zəncirlər · Gün 8: interfeys · Gün 9: təhvil düymələri
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from . import analiz as analiz_xidmeti
from . import builder, cache, db, hadise, izleme, llm, muqayise, rag
from .config import ayarlar
from .schemas import (
    AnalizBasladi,
    AnalizIstek,
    AnalizTam,
    IzlemeIstek,
    SaytXulase,
    SualCavab,
    SualIstek,
    Veziyyet,
    XetaIstek,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("saytlupa")

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
SSE_GOZLEME = 30  # saniyə — bu müddətdə hadisə gəlməsə "nəbz" göndərilir


def _gemma_var() -> bool:
    """Ollama işləyirmi və Gemma yüklənibmi?"""
    try:
        cavab = httpx.get(f"{ayarlar.ollama_base_url}/api/tags", timeout=1.5)
        modeller = [m.get("name", "") for m in cavab.json().get("models", [])]
        return any("gemma" in ad for ad in modeller)
    except Exception:
        return False


@asynccontextmanager
async def omur(app: FastAPI):
    db.baza_qur()
    log.info("Baza: %s | Keş: %s", db.veziyyet()["baza"], cache.veziyyet()["kes"])
    yield


app = FastAPI(
    title="SaytLupa",
    description="Sayt analiz və söhbət agenti",
    version="0.2.0",
    lifespan=omur,
)


# ------------------------------------------------------------------ sistem


@app.get("/api/health", response_model=Veziyyet)
def saglamliq() -> Veziyyet:
    return Veziyyet(
        baza=db.veziyyet()["baza"],
        kes=cache.veziyyet()["kes"],
        claude=ayarlar.claude_var,
        gemini=ayarlar.gemini_var,
        gemma=_gemma_var(),
    )


# ------------------------------------------------------------------ analiz


@app.post("/api/analyze", response_model=AnalizBasladi)
async def analiz_basla(istek: AnalizIstek) -> AnalizBasladi:
    """Analizi fonda başladır. Gedişatı `/api/analyze/{id}/axin` ilə izlə."""
    netice = analiz_xidmeti.basla(str(istek.url), istek.max_sehife)
    return AnalizBasladi(**netice)


@app.get("/api/analyze/{analiz_id}/axin")
async def analiz_axini(analiz_id: int):
    """Canlı gedişat (Server-Sent Events)."""
    if analiz_xidmeti.analiz_oxu(analiz_id) is None:
        raise HTTPException(404, "Belə analiz yoxdur")

    novbe = hadise.novbe(analiz_id)

    async def axin():
        try:
            while True:
                try:
                    qeyd = await asyncio.wait_for(novbe.get(), timeout=SSE_GOZLEME)
                except asyncio.TimeoutError:
                    yield {"event": "nebz", "data": "{}"}
                    continue

                yield {
                    "event": qeyd["nov"],
                    "data": json.dumps(qeyd, ensure_ascii=False, default=str),
                }
                if qeyd["nov"] == "son":
                    break
        finally:
            hadise.temizle(analiz_id)

    return EventSourceResponse(axin())


@app.get("/api/analyze/{analiz_id}", response_model=AnalizTam)
def analiz_netice(analiz_id: int) -> AnalizTam:
    netice = analiz_xidmeti.analiz_oxu(analiz_id)
    if netice is None:
        raise HTTPException(404, "Belə analiz yoxdur")
    return AnalizTam(**netice)


@app.get("/api/sites", response_model=list[SaytXulase])
def sayt_siyahisi() -> list[SaytXulase]:
    return [SaytXulase(**s) for s in analiz_xidmeti.saytlar()]


@app.get("/api/sites/{site_id}/pages")
def sayt_sehifeleri(site_id: int) -> list[dict]:
    """Yığılmış səhifələr — RAG bazasının nə ilə doldurulduğunu göstərir."""
    with db.sessiya() as s:
        sehifeler = (
            s.query(db.Sehife).filter(db.Sehife.site_id == site_id).limit(200).all()
        )
        return [
            {
                "url": p.url,
                "basliq": p.basliq,
                "metn_uzunlugu": len(p.metn or ""),
                "onizleme": (p.metn or "")[:200],
            }
            for p in sehifeler
        ]


# ------------------------------------------------------------------ söhbət (RAG)


@app.post("/api/sites/{site_id}/chat", response_model=SualCavab)
async def saytla_danis(site_id: int, istek: SualIstek) -> SualCavab:
    """Saytın məzmunu ilə söhbət — cavab mənbə göstərməklə qaytarılır."""
    with db.sessiya() as s:
        if s.get(db.Sayt, site_id) is None:
            raise HTTPException(404, "Belə sayt yoxdur")

    # RAG sinxron kitabxanalarla işləyir — axını bloklamamaq üçün ayrı sapda
    netice = await asyncio.to_thread(
        rag.cavab_ver, site_id, istek.sual, istek.session_id
    )
    return SualCavab(**netice)


@app.get("/api/sites/{site_id}/rag")
def rag_veziyyeti(site_id: int) -> dict:
    """Bu sayt üçün RAG bazasının vəziyyəti."""
    with db.sessiya() as s:
        sehife_sayi = s.query(db.Sehife).filter(db.Sehife.site_id == site_id).count()
    return {
        "site_id": site_id,
        "sehife_sayi": sehife_sayi,
        "chunk_sayi": rag.store.chunk_sayi(site_id),
        "embedding_menbeyi": rag.embedder.menbe(),
        "modeller": llm.veziyyet(),
    }


@app.post("/api/sites/{site_id}/rag/yenile")
async def rag_yenile(site_id: int) -> dict:
    """RAG indeksini yenidən qurur (embedding üsulu dəyişəndə lazımdır)."""
    with db.sessiya() as s:
        if s.get(db.Sayt, site_id) is None:
            raise HTTPException(404, "Belə sayt yoxdur")
    return await asyncio.to_thread(rag.qur, site_id)


# ------------------------------------------------------------------ təhvil (Gün 9)


def _tehvil(netice: dict) -> dict:
    """Təhvil funksiyasının nəticəsini REST cavabına çevirir.

    Analiz yoxdursa 404. Digər uğursuzluqlar 200 ilə qaytarılır: səbəb
    istifadəçiyə göstərilməlidir (məsələn "Claude açarı yoxdur"), bu, server
    xətası deyil.
    """
    if netice.get("tapilmadi"):
        raise HTTPException(404, "Belə analiz yoxdur")
    return netice


@app.post("/api/analyze/{analiz_id}/muasir")
async def muasir_qur(analiz_id: int) -> dict:
    """⚡ Analizə əsasən saytın müasir versiyasını yazdırır (Claude/Gemini)."""
    return _tehvil(await asyncio.to_thread(builder.muasir.qur, analiz_id))


@app.get("/api/analyze/{analiz_id}/muasir/onizleme")
def muasir_onizleme(analiz_id: int) -> FileResponse:
    """Yazılmış müasir versiyanı brauzerdə göstərir."""
    tapinti = builder.yukle_yolu("muasir", analiz_id)
    if tapinti is None:
        raise HTTPException(404, "Müasir versiya hələ qurulmayıb")
    return FileResponse(tapinti[0], media_type="text/html")


@app.post("/api/analyze/{analiz_id}/klon")
async def klon_hazirla(analiz_id: int) -> dict:
    """🧬 `ai-website-cloner` üçün araşdırma sənədlərini yazır."""
    return _tehvil(await asyncio.to_thread(builder.klon.hazirla, analiz_id))


@app.post("/api/analyze/{analiz_id}/arsiv")
async def arsiv_qur(analiz_id: int) -> dict:
    """📦 Ana səhifəni (HTML + CSS + şəkillər) lokal qovluğa yığır."""
    return _tehvil(await builder.arsiv.arsivle(analiz_id))


@app.post("/api/analyze/{analiz_id}/pdf")
async def pdf_qur(analiz_id: int) -> dict:
    """📄 Bütün analizi bir PDF faylına yazır."""
    return _tehvil(await asyncio.to_thread(builder.pdf.yarat, analiz_id))


@app.get("/api/analyze/{analiz_id}/yukle/{nov}")
def tehvil_yukle(analiz_id: int, nov: str) -> FileResponse:
    """Hazır faylı yükləyir: `muasir` · `klon` · `arsiv` · `pdf`."""
    if nov not in builder.YUKLEME:
        raise HTTPException(400, f"Naməlum təhvil növü: {nov}")
    tapinti = builder.yukle_yolu(nov, analiz_id)
    if tapinti is None:
        raise HTTPException(404, "Fayl hazır deyil — əvvəlcə müvafiq düyməni işlət")
    yol, ad = tapinti
    return FileResponse(yol, filename=ad)


# ------------------------------------------------------------------ müqayisə (Gün 11)


@app.get("/api/muqayise")
def saytlari_muqayise_et(sayt1: str, sayt2: str) -> dict:
    """İki analiz edilmiş saytı yan-yana qoyur.

    `sayt1`/`sayt2` — sayt nömrəsi, domen və ya tam ünvan ola bilər.
    """
    netice = muqayise.muqayise_et(sayt1, sayt2)
    if netice.get("tapilmadi"):
        raise HTTPException(404, netice["sebeb"])
    return netice


# ------------------------------------------------------------------ izləmə (Gün 10)
#
# Bu bölmə n8n workflow-ları üçündür: cron nə vaxt yoxlayacağını bilir,
# dəyişikliyin nə olduğunu isə Python hesablayır.


@app.get("/api/izleme")
def izleme_siyahisi(min_saat: int = 0) -> list[dict]:
    """İzlənən saytlar. `min_saat` — bu qədər saat içində yoxlananları atır."""
    return izleme.siyahi(min_saat=min_saat)


@app.post("/api/izleme")
def izleme_elave(istek: IzlemeIstek) -> dict:
    """🔔 Saytı izləməyə qoyur."""
    netice = izleme.elave_et(istek.site_id, istek.cron, istek.telegram_chat_id)
    if netice.get("tapilmadi"):
        raise HTTPException(404, "Belə sayt yoxdur")
    return netice


@app.delete("/api/izleme/{site_id}")
def izleme_dayandir(site_id: int) -> dict:
    if not izleme.sil(site_id):
        raise HTTPException(404, "Bu sayt izlənmir")
    return {"site_id": site_id, "izlenir": False}


@app.post("/api/izleme/{site_id}/yoxla")
async def izleme_yoxla(site_id: int, rag_yenile: bool = True) -> dict:
    """Saytı yenidən gəzir və əvvəlki nüsxə ilə fərqi qaytarır."""
    netice = await izleme.yoxla(site_id, rag_yenile=rag_yenile)
    if netice.get("tapilmadi"):
        raise HTTPException(404, "Belə sayt yoxdur")
    return netice


# ------------------------------------------------------------------ iş xətaları


@app.post("/api/xetalar")
def xeta_qeyd_et(istek: XetaIstek) -> dict:
    """n8n Error Workflow buraya yazır."""
    return izleme.xeta_yaz(istek.menbe, istek.workflow, istek.xeta_metni)


@app.get("/api/xetalar")
def xeta_siyahisi(limit: int = 50) -> list[dict]:
    return izleme.xetalar(limit)


# ------------------------------------------------------------------ interfeys


@app.get("/")
def ana_sehife() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
