"""Gün 1 testləri — skelet işləyirmi."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import cache, db
from backend.decorators import cached, retry, safe_collector
from backend.main import app
from backend.schemas import AIHesabat, AnalizIstek

muvekkil = TestClient(app)


# ---------- API ----------


def test_health_cavab_verir():
    cavab = muvekkil.get("/api/health")
    assert cavab.status_code == 200
    data = cavab.json()
    assert data["baza"] in ("postgresql", "sqlite")
    assert data["kes"] in ("redis", "yaddas")
    assert "baza_xeberdarligi" in data
    assert data["gemma_veziyyeti"] in ("hazir", "elcatmaz", "islenmir")


# ---------- Gemma vəziyyəti ----------


def test_gemma_islenmir_deyilir(monkeypatch):
    """Claude/Gemini varsa və re-ranking Gemini-dədirsə Gemma çağırılmır.

    Belə halda `false` qaytarmaq yanıldıcıdır — buludda Ollama qəsdən yoxdur.
    """
    from backend import main
    from backend.config import ayarlar

    monkeypatch.setattr(ayarlar, "anthropic_api_key", "var")
    monkeypatch.setattr(ayarlar, "rerank", "gemini")
    monkeypatch.setattr(main, "_gemma_var", lambda: (_ for _ in ()).throw(
        AssertionError("Ollama-ya sorğu atılmamalıdır")))

    assert main._gemma_veziyyeti() == "islenmir"


def test_rerank_gemma_olanda_yoxlanilir(monkeypatch):
    from backend import main
    from backend.config import ayarlar

    monkeypatch.setattr(ayarlar, "anthropic_api_key", "var")
    monkeypatch.setattr(ayarlar, "rerank", "gemma")

    monkeypatch.setattr(main, "_gemma_var", lambda: True)
    assert main._gemma_veziyyeti() == "hazir"

    monkeypatch.setattr(main, "_gemma_var", lambda: False)
    assert main._gemma_veziyyeti() == "elcatmaz"


def test_acar_yoxdursa_gemma_lazimdir(monkeypatch):
    """Claude və Gemini olmasa Gemma zəncirin sonuncu həlqəsidir."""
    from backend import main
    from backend.config import ayarlar

    monkeypatch.setattr(ayarlar, "anthropic_api_key", "")
    monkeypatch.setattr(ayarlar, "google_api_key", "")
    monkeypatch.setattr(ayarlar, "rerank", "gemini")
    monkeypatch.setattr(main, "_gemma_var", lambda: False)

    assert main._gemma_veziyyeti() == "elcatmaz"


# ---------- baza seçimi ----------


def test_postgres_hazir_olana_qeder_gozlenilir(monkeypatch):
    """Docker-də `api` konteyneri `db`-dən tez qalxa bilər.

    Bir dəfəlik yoxlama uğursuz olsa layihə ömrünün sonuna qədər SQLite-da
    işləyirdi — `POSTGRES` modul sabitidir, sonradan dəyişmir.
    """
    cehd = {"say": 0}

    def yalanci(url: str) -> bool:
        cehd["say"] += 1
        return cehd["say"] >= 3

    monkeypatch.setattr(db, "_qosulur", yalanci)
    monkeypatch.setattr(db, "GOZLEME_ADDIMI", 0)

    assert db._movcud("postgresql://x", gozleme=10) is True
    assert cehd["say"] == 3


def test_gozleme_bitende_sqlitea_kecilir(monkeypatch):
    monkeypatch.setattr(db, "_qosulur", lambda url: False)
    monkeypatch.setattr(db, "GOZLEME_ADDIMI", 0)

    assert db._movcud("postgresql://x", gozleme=0) is False
    assert db._movcud("", gozleme=10) is False  # ünvan yoxdursa gözləmirik


def test_ana_sehife_acilir():
    cavab = muvekkil.get("/")
    assert cavab.status_code == 200
    assert "SaytLupa" in cavab.text


# ---------- Pydantic ----------


def test_analiz_istek_duzgun_url():
    istek = AnalizIstek(url="https://example.com")
    assert istek.max_sehife == 30


def test_analiz_istek_yanlis_sxem():
    with pytest.raises(ValidationError):
        AnalizIstek(url="ftp://example.com")


def test_analiz_istek_sehife_limiti():
    with pytest.raises(ValidationError):
        AnalizIstek(url="https://example.com", max_sehife=500)


def test_ai_hesabat_sxemi():
    hesabat = AIHesabat(
        meqsed="onlayn mağaza",
        hedef_auditoriya="25-40 yaş",
        texnologiyalar="Next.js",
        performans_problemleri=["böyük şəkillər"],
        seo_catismazliqlari=["meta description yoxdur"],
        muasir_versiya_tovsiyeleri=["şəkilləri WebP-yə keçir"],
    )
    assert len(hesabat.performans_problemleri) == 1


# ---------- Keş ----------


def test_kes_yaz_oxu_sil():
    cache.yaz("sinaq", {"a": 1}, 60)
    assert cache.oxu("sinaq") == {"a": 1}
    cache.sil("sinaq")
    assert cache.oxu("sinaq") is None


# ---------- Dekoratorlar ----------


def test_cached_ikinci_defe_cagirmir():
    sayğac = {"n": 0}

    @cached(saniye=60)
    def hesabla(x):
        sayğac["n"] += 1
        return x * 2

    assert hesabla(21) == 42
    assert hesabla(21) == 42
    assert sayğac["n"] == 1


def test_cached_eyni_adli_funksiyalar_toqqusmur():
    """Bütün toplayıcılarda funksiya 'topla' adlanır — açarlar qarışmamalıdır."""

    def yarat(modul_adi, deyer):
        def topla(url):
            return {"kim": deyer}

        topla.__module__ = modul_adi
        return cached(saniye=60)(topla)

    a = yarat("backend.collectors.a", "domen")
    b = yarat("backend.collectors.b", "geo")

    assert a("https://example.com") == {"kim": "domen"}
    assert b("https://example.com") == {"kim": "geo"}  # a-nın nəticəsini qaytarmamalıdır


def test_retry_cehd_edir_ve_ugur_qazanir():
    sayğac = {"n": 0}

    @retry(cehd=3, gozleme=0.01)
    def kovrek():
        sayğac["n"] += 1
        if sayğac["n"] < 3:
            raise RuntimeError("hələ yox")
        return "oldu"

    assert kovrek() == "oldu"
    assert sayğac["n"] == 3


def test_retry_hamisi_sinsa_xeta_atir():
    @retry(cehd=2, gozleme=0.01)
    def hemise_sinir():
        raise ValueError("sındı")

    with pytest.raises(ValueError):
        hemise_sinir()


def test_safe_collector_xetani_uduc_edir():
    @safe_collector("sinaq")
    def sinir():
        raise RuntimeError("xarab")

    netice = sinir()
    assert netice["ugurlu"] is False
    assert netice["ad"] == "sinaq"
    assert "xarab" in netice["xeta"]


def test_safe_collector_async_isleyir():
    @safe_collector("async_sinaq")
    async def islek():
        return {"deyer": 5}

    netice = asyncio.run(islek())
    assert netice["ugurlu"] is True
    assert netice["data"]["deyer"] == 5


# ---------- Baza ----------


def test_baza_qurulur_ve_sayt_yazilir():
    db.baza_qur()
    with db.sessiya() as s:
        sayt = db.Sayt(url="https://example.com", domain="example.com")
        s.add(sayt)
        s.commit()
        assert sayt.id is not None
        s.delete(sayt)
        s.commit()


def test_chunk_embedding_yaz_oxu():
    chunk = db.Chunk(metn="salam")
    chunk.embedding_yaz([0.1, 0.2, 0.3])
    assert chunk.embedding_oxu() == pytest.approx([0.1, 0.2, 0.3])
