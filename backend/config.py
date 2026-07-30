"""Layihənin bütün parametrləri bir yerdə (pydantic-settings)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

KOK = Path(__file__).resolve().parent.parent
STORAGE = KOK / "storage"


class Ayarlar(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=KOK / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # LLM
    anthropic_api_key: str = ""
    google_api_key: str = ""
    claude_model: str = "claude-sonnet-5"
    # `gemini-2.5-flash` və `text-embedding-004` 2026-07-29-da yoxlandı: hər ikisi
    # yeni açarlara 404 verir ("no longer available to new users").
    gemini_model: str = "gemini-3.6-flash"
    embedding_model: str = "gemini-embedding-001"
    ollama_base_url: str = "http://localhost:11434"
    gemma_model: str = "gemma3:1b"

    # İnfrastruktur
    database_url: str = ""
    redis_url: str = ""

    # Xarici xidmətlər
    # MCP serveri FastAPI ilə HTTP üzərindən danışır — ağır iş (analiz, RAG)
    # Claude Code-un işə saldığı prosesdə yox, serverdə getsin.
    api_url: str = "http://localhost:8000"
    n8n_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    pagespeed_api_key: str = ""

    # `ai-website-cloner` şablonunun yerli nüsxəsi. Boş olsa klon sənədləri yenə
    # yazılır, sadəcə köçürmə əmrində qovluğun yerini istifadəçi özü yazır.
    # SaytLupa bu qovluğa **heç vaxt özü yazmır** — yalnız hazır əmri göstərir.
    cloner_yolu: str = ""

    # Crawler
    max_pages: int = 30
    request_timeout: int = 15

    # Re-ranking. Ölçmə (bax `docs/model-secimi.md`) göstərdi ki, bu maşında
    # lokal Gemma re-ranking-i 46-134 saniyə çəkir və nəticəni yaxşılaşdırmır.
    # Ona görə standart olaraq söndürülüb; "gemini" və ya "gemma" ilə açılır.
    rerank: str = ""  # "" | "gemma" | "gemini"

    @property
    def sqlite_yolu(self) -> str:
        """Postgres yoxdursa istifadə olunan ehtiyat baza."""
        (KOK / "data").mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(KOK / 'data' / 'saytlupa.db').as_posix()}"

    @property
    def claude_var(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def gemini_var(self) -> bool:
        return bool(self.google_api_key)


ayarlar = Ayarlar()

# Fayl qovluqları — proqram işə düşəndə hazır olsun
for alt in ("pages", "archives", "modern", "pdf", "klon"):
    (STORAGE / alt).mkdir(parents=True, exist_ok=True)
