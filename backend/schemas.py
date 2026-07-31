"""Pydantic modelləri — API-nin giriş/çıxış müqaviləsi."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ---------- Giriş ----------


class AnalizIstek(BaseModel):
    url: HttpUrl
    max_sehife: int = Field(default=30, ge=1, le=100)

    @field_validator("url")
    @classmethod
    def yalniz_http(cls, v: HttpUrl) -> HttpUrl:
        if v.scheme not in ("http", "https"):
            raise ValueError("Yalnız http/https ünvanları qəbul edilir")
        return v


class SualIstek(BaseModel):
    sual: str = Field(min_length=2, max_length=1000)
    session_id: int | None = None


class IzlemeIstek(BaseModel):
    site_id: int
    cron: str = "0 9 * * *"
    telegram_chat_id: str = ""


class XetaIstek(BaseModel):
    """n8n Error Workflow-un göndərdiyi qeyd."""

    menbe: str = "n8n"
    workflow: str = ""
    xeta_metni: str = ""


# ---------- Çıxış ----------


class AIHesabat(BaseModel):
    """Claude-un 6 bəndlik hesabatı — LCEL zəncirinin çıxış sxemi."""

    meqsed: str
    hedef_auditoriya: str
    texnologiyalar: str
    performans_problemleri: list[str]
    seo_catismazliqlari: list[str]
    muasir_versiya_tovsiyeleri: list[str]


class AnalizBasladi(BaseModel):
    """POST /api/analyze cavabı — analiz fonda başladı."""

    analiz_id: int
    site_id: int
    url: str


class SaytXulase(BaseModel):
    id: int
    url: str
    domain: str
    son_analiz: datetime | None = None
    izlenir: bool = False


class AnalizXulase(BaseModel):
    id: int
    site_id: int
    url: str
    domain: str
    status: Literal["gozleyir", "isleyir", "hazir", "xeta"]
    tarix: datetime
    xeta: str = ""


class AnalizTam(AnalizXulase):
    xam: dict[str, Any] = {}
    ai_hesabat: AIHesabat | None = None
    sehife_sayi: int = 0
    chunk_sayi: int = 0


class Menbe(BaseModel):
    url: str
    basliq: str
    parca: str
    bal: float = 0.0


class SualCavab(BaseModel):
    cavab: str
    menbeler: list[Menbe] = []
    session_id: int
    # Şəffaflıq üçün: neçə namizəd tapıldı, hansı embedding üsulu, re-ranking
    # işlədilib-işlədilməyib, hansı model cavab verdi, nə qədər çəkdi
    olcme: dict[str, Any] = {}


class Veziyyet(BaseModel):
    status: str = "isleyir"
    baza: str
    kes: str
    claude: bool
    gemini: bool
    gemma: bool
    # `hazir` · `elcatmaz` · `islenmir`. Sonuncu o deməkdir ki, bu qurulumda
    # Gemma ümumiyyətlə çağırılmır (Claude/Gemini var, re-ranking Gemini-dədir) —
    # yəni əlçatmaz olması nasazlıq deyil.
    gemma_veziyyeti: str = "islenmir"
    # Açıq model başqa qatda işlədilirsə onun yeri (məs. "n8n agentində").
    # `GEMMA_QEYDI` ilə təyin olunur; boş olsa interfeys heç nə yazmır.
    gemma_qeydi: str = ""
    # Postgres gözlənilirdi, amma cavab vermədi — səssiz enmə görünsün deyə
    baza_xeberdarligi: str = ""
    # Serverdə API açarı qoyulubmu — interfeys buna görə açar düyməsini göstərir
    acar_teleb_olunur: bool = False
