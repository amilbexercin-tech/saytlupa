"""FastAPI tətbiqi — SaytLupa.

Gün 1: skelet · Gün 2-3: toplayıcılar · Gün 4: analiz axını + SSE canlı gedişat
Gün 5-7: RAG və zəncirlər · Gün 8: interfeys · Gün 9: təhvil düymələri
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from . import aktiv as aktiv_skan
from . import analiz as analiz_xidmeti
from . import builder, cache, db, hadise, izleme, llm, muqayise, qapi, rag, sahiblik, sebeke
from . import __version__
from .collectors import sertifikat, surat, tehlukesizlik
from .collectors.base import domen as base_domen
from .config import ayarlar
from .schemas import (
    AktivSkanIstek,
    AnalizBasladi,
    AnalizIstek,
    AnalizTam,
    GedisatIstek,
    IzlemeIstek,
    NeticeIstek,
    SahiblikIstek,
    SaytXulase,
    SualCavab,
    SualIstek,
    TehlukesizlikIstek,
    Veziyyet,
    XetaAktivIstek,
    XetaIstek,
)

log = logging.getLogger("saytlupa")  # qurulması `backend/__init__.py`-dədir

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
SSE_GOZLEME = 30  # saniyə — bu müddətdə hadisə gəlməsə "nəbz" göndərilir

# Pul xərcləyən (model çağıran) endpoint-lər üçün: `API_ACAR` qoyulubsa açar
# tələb olunur, qoyulmayıbsa heç nə dəyişmir. Bax `qapi.py`.
ACAR = [Depends(qapi.acar_teleb)]


def _gemma_var() -> bool:
    """Ollama işləyirmi və Gemma yüklənibmi?"""
    try:
        cavab = httpx.get(f"{ayarlar.ollama_base_url}/api/tags", timeout=1.5)
        modeller = [m.get("name", "") for m in cavab.json().get("models", [])]
        return any("gemma" in ad for ad in modeller)
    except Exception:
        return False


def _gemma_lazimdir() -> bool:
    """Bu qurulumda Gemma ümumiyyətlə işə düşürmü?

    İki hal var: re-ranking ona qurulubsa, ya da güclü modellərin heç biri
    yoxdursa (Gemma model zəncirinin sonuncu həlqəsidir). Hər ikisi yoxdursa
    Gemma heç vaxt çağırılmır və onun əlçatmazlığı nasazlıq deyil.
    """
    return ayarlar.rerank == "gemma" or not (ayarlar.claude_var or ayarlar.gemini_var)


def _gemma_veziyyeti() -> str:
    """`hazir` · `elcatmaz` · `islenmir`.

    Sadəcə `false` qaytarmaq yanıldıcıdır: buludda Ollama qəsdən yoxdur və
    `false` görən adam nəyinsə sındığını düşünür. `islenmir` isə vəziyyəti
    olduğu kimi deyir. Üstəlik bu halda Ollama-ya sorğu da atılmır.
    """
    if not _gemma_lazimdir():
        return "islenmir"
    return "hazir" if _gemma_var() else "elcatmaz"


@asynccontextmanager
async def omur(app: FastAPI):
    db.baza_qur()
    log.info("Baza: %s | Keş: %s", db.veziyyet()["baza"], cache.veziyyet()["kes"])
    yield


app = FastAPI(
    title="SaytLupa",
    description="Sayt analiz və söhbət agenti",
    version=__version__,
    lifespan=omur,
)


# `/api/analyze/{id}/muasir/onizleme` — modelin yazdığı HTML
ONIZLEME_YOLU = re.compile(r"^/api/analyze/\d+/muasir/onizleme/?$")


@app.middleware("http")
async def tehlukesizlik_basliqlari(sorgu, sonraki):
    """Təhlükəsizlik başlıqları.

    Əvvəl bunlar Caddy-də idi, amma Railway-də tərs proxy bizim deyil və onun
    konfiqurasiyasına çatmırıq — ona görə başlıqları tətbiqin özü qoyur. Belə
    olanda qoruma hostinqdən asılı qalmır: lokalda, Docker-də və Railway-də
    eynidir.

    `sandbox` yalnız önizləmə yolunda tətbiq olunur. Səbəb: həmin HTML-i model
    yazır, modelin girişində isə analiz edilən saytın **xam mətni** var — yəni
    sayt sahibi promptu manipulyasiya edib ora skript saldıra bilər. `sandbox`
    onu təcrid edir: skript işləmir, forma göndərilmir. Adi səhifələrə tətbiq
    etsək öz interfeysimiz də sınardı.
    """
    cavab = await sonraki(sorgu)
    cavab.headers.setdefault("X-Content-Type-Options", "nosniff")
    cavab.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    cavab.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if ONIZLEME_YOLU.match(sorgu.url.path):
        cavab.headers["Content-Security-Policy"] = "sandbox"
    return cavab


# ------------------------------------------------------------------ sistem


@app.get("/api/health", response_model=Veziyyet)
def saglamliq() -> Veziyyet:
    baza = db.veziyyet()
    gemma = _gemma_veziyyeti()
    return Veziyyet(
        baza=baza["baza"],
        kes=cache.veziyyet()["kes"],
        claude=ayarlar.claude_var,
        gemini=ayarlar.gemini_var,
        gemma=gemma == "hazir",
        gemma_veziyyeti=gemma,
        # Qeyd yalnız Gemma bu tətbiqdə çağırılmayanda mənalıdır
        gemma_qeydi=ayarlar.gemma_qeydi if gemma == "islenmir" else "",
        baza_xeberdarligi=baza["xeberdarliq"],
        acar_teleb_olunur=qapi.teleb_olunur(),
    )


# ------------------------------------------------------------------ analiz


@app.post("/api/analyze", response_model=AnalizBasladi, dependencies=ACAR)
async def analiz_basla(istek: AnalizIstek) -> AnalizBasladi:
    """Analizi fonda başladır. Gedişatı `/api/analyze/{id}/axin` ilə izlə."""
    # Daxili şəbəkə ünvanları rədd edilir (bax `sebeke` modulu). Ad həlli
    # blokedicidir, ona görə ayrı sapda gedir.
    sebeb = await asyncio.to_thread(sebeke.unvan_sebebi, str(istek.url))
    if sebeb:
        raise HTTPException(400, sebeb)

    netice = analiz_xidmeti.basla(str(istek.url), istek.max_sehife)
    return AnalizBasladi(**netice)


@app.post("/api/tehlukesizlik", dependencies=ACAR)
async def tehlukesizlik_yoxla(istek: TehlukesizlikIstek) -> dict:
    """Yalnız təhlükəsizlik auditi — tam analiz/crawl olmadan, sürətli.

    Səhifəni bir dəfə çəkir, sertifikatı yoxlayır, sonra passiv auditi işlədir.
    Tapıntı + bal qaytarır; interfeys eyni kartda göstərir.
    """
    url = str(istek.url)
    sebeb = await asyncio.to_thread(sebeke.unvan_sebebi, url)
    if sebeb:
        raise HTTPException(400, sebeb)

    try:
        html, basliqlar, _yuklenme, _kod = await surat.olc_ve_getir(url)
    except Exception as xeta:
        raise HTTPException(502, f"Sayt yüklənmədi: {xeta}")

    # Sertifikat (SSL) tapıntıları üçün — səhifə çəkilişi ilə paralel getmir,
    # çünki tələb olunan yeganə asılılıqdır və keşlənir.
    sert = await sertifikat.topla(url)
    tehl = await tehlukesizlik.topla(url, html, basliqlar, {"sertifikat": sert})

    return {
        "ugurlu": tehl.get("ugurlu", False),
        "url": url,
        "domain": base_domen(url),
        **(tehl.get("data") or {}),
    }


# ---------------- Aktiv (dərin) skan — yalnız təsdiqli domen ----------------


@app.get("/api/sahiblik")
def sahiblik_siyahisi() -> list[dict]:
    """Təsdiqlənmiş domenlər (interfeys düyməni açmaq üçün yoxlayır)."""
    return sahiblik.siyahi()


@app.post("/api/sahiblik/token", dependencies=ACAR)
def sahiblik_token(istek: SahiblikIstek) -> dict:
    """Domen üçün təsdiq token-i və təlimat qaytarır."""
    try:
        return sahiblik.token_yarat(istek.domain)
    except ValueError as xeta:
        raise HTTPException(400, str(xeta))


@app.post("/api/sahiblik/yoxla", dependencies=ACAR)
def sahiblik_yoxla(istek: SahiblikIstek) -> dict:
    """Token-in DNS/faylda olub-olmadığını yoxlayır və domeni təsdiqləyir."""
    return sahiblik.yoxla(istek.domain)


@app.post("/api/aktiv-skan", dependencies=ACAR)
async def aktiv_skan_basla(istek: AktivSkanIstek) -> dict:
    """Aktiv skan işi yaradır (yalnız təsdiqli domen + açıq razılıq)."""
    if not istek.razilioq:
        raise HTTPException(400, "Aktiv skan üçün açıq razılıq lazımdır "
                                 "(«bu sayt mənimdir»).")
    url = str(istek.url)
    sebeb = await asyncio.to_thread(sebeke.unvan_sebebi, url)
    if sebeb:
        raise HTTPException(400, sebeb)
    try:
        return aktiv_skan.yeni_skan(url)
    except aktiv_skan.TesdiqYoxdur as xeta:
        raise HTTPException(403, str(xeta))


@app.get("/api/aktiv-skan/novbe", dependencies=ACAR)
def aktiv_skan_novbe() -> dict:
    """Worker növbədən iş götürür (yoxdursa boş)."""
    return aktiv_skan.novbeden_goturt() or {}


@app.post("/api/aktiv-skan/{job_id}/gedisat", dependencies=ACAR)
def aktiv_skan_gedisat(job_id: int, istek: GedisatIstek) -> dict:
    aktiv_skan.gedisat_yaz(job_id, istek.mesaj, istek.faiz)
    return {"ok": True, "dayandirildi": aktiv_skan.dayandirilibmi(job_id)}


@app.post("/api/aktiv-skan/{job_id}/netice", dependencies=ACAR)
def aktiv_skan_netice(job_id: int, istek: NeticeIstek) -> dict:
    return aktiv_skan.netice_yaz(job_id, istek.tapintilar)


@app.post("/api/aktiv-skan/{job_id}/xeta", dependencies=ACAR)
def aktiv_skan_xeta(job_id: int, istek: XetaAktivIstek) -> dict:
    aktiv_skan.xeta_yaz(job_id, istek.mesaj)
    return {"ok": True}


@app.post("/api/aktiv-skan/{job_id}/dayandir", dependencies=ACAR)
def aktiv_skan_dayandir(job_id: int) -> dict:
    return {"dayandirildi": aktiv_skan.dayandir(job_id)}


@app.get("/api/aktiv-skan/{job_id}", dependencies=ACAR)
def aktiv_skan_oxu(job_id: int) -> dict:
    netice = aktiv_skan.oxu(job_id)
    if netice is None:
        raise HTTPException(404, "Belə skan yoxdur")
    return netice


@app.get("/api/aktiv-skan/{job_id}/axin")
async def aktiv_skan_axin(job_id: int):
    """Aktiv skanın canlı gedişatı (SSE) — analizlə eyni nümunə."""
    if aktiv_skan.oxu(job_id) is None:
        raise HTTPException(404, "Belə skan yoxdur")

    hid = aktiv_skan._hid(job_id)
    novbe = hadise.novbe(hid)

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
            hadise.temizle(hid)

    return EventSourceResponse(axin())


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


@app.post("/api/sites/{site_id}/chat", response_model=SualCavab,
          dependencies=[Depends(qapi.sual_limiti)])
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


@app.post("/api/sites/{site_id}/rag/yenile", dependencies=ACAR)
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


@app.post("/api/analyze/{analiz_id}/muasir", dependencies=ACAR)
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


@app.post("/api/analyze/{analiz_id}/klon", dependencies=ACAR)
async def klon_hazirla(analiz_id: int) -> dict:
    """🧬 `ai-website-cloner` üçün araşdırma sənədlərini yazır."""
    return _tehvil(await asyncio.to_thread(builder.klon.hazirla, analiz_id))


@app.post("/api/analyze/{analiz_id}/arsiv", dependencies=ACAR)
async def arsiv_qur(analiz_id: int) -> dict:
    """📦 Ana səhifəni (HTML + CSS + şəkillər) lokal qovluğa yığır."""
    return _tehvil(await builder.arsiv.arsivle(analiz_id))


@app.post("/api/analyze/{analiz_id}/pdf", dependencies=ACAR)
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


@app.post("/api/izleme", dependencies=ACAR)
def izleme_elave(istek: IzlemeIstek) -> dict:
    """🔔 Saytı izləməyə qoyur."""
    netice = izleme.elave_et(istek.site_id, istek.cron, istek.telegram_chat_id)
    if netice.get("tapilmadi"):
        raise HTTPException(404, "Belə sayt yoxdur")
    return netice


@app.delete("/api/izleme/{site_id}", dependencies=ACAR)
def izleme_dayandir(site_id: int) -> dict:
    if not izleme.sil(site_id):
        raise HTTPException(404, "Bu sayt izlənmir")
    return {"site_id": site_id, "izlenir": False}


@app.post("/api/izleme/{site_id}/yoxla", dependencies=ACAR)
async def izleme_yoxla(site_id: int, rag_yenile: bool = True) -> dict:
    """Saytı yenidən gəzir və əvvəlki nüsxə ilə fərqi qaytarır."""
    netice = await izleme.yoxla(site_id, rag_yenile=rag_yenile)
    if netice.get("tapilmadi"):
        raise HTTPException(404, "Belə sayt yoxdur")
    return netice


# ------------------------------------------------------------------ iş xətaları


@app.post("/api/xetalar", dependencies=ACAR)
def xeta_qeyd_et(istek: XetaIstek) -> dict:
    """n8n Error Workflow buraya yazır."""
    return izleme.xeta_yaz(istek.menbe, istek.workflow, istek.xeta_metni)


@app.get("/api/xetalar")
def xeta_siyahisi(limit: int = 50) -> list[dict]:
    return izleme.xetalar(limit)


# ------------------------------------------------------------------ interfeys


@app.get("/")
def ana_sehife() -> FileResponse:
    # index.html keşlənməsin — statik fayllar `?v=` ilə busted olur, amma HTML
    # özü keşlənsə brauzer köhnə skript siyahısını (yeni fayllar daxil) saxlayır.
    return FileResponse(FRONTEND / "index.html",
                        headers={"Cache-Control": "no-cache, must-revalidate"})


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
