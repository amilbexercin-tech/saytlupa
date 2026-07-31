"""Giriş qapısı testləri — API açarı və gündəlik sual limiti.

Ən vacib şərt: `API_ACAR` boş olanda **heç nə dəyişməməlidir**. Lokal inkişaf və
qalan 225 test bu davranışa güvənir.
"""

import pytest
from fastapi.testclient import TestClient

from backend import cache, db, qapi
from backend.config import ayarlar
from backend.main import app

muvekkil = TestClient(app)

ACAR = "sinaq-acari-12345"

# Olmayan nömrə qəsdən seçilib: qapıdan keçən sorğu dərhal 404 alsın və **real
# iş görməsin**. Əks halda `izleme/1/yoxla` həqiqi saytı gəzir və test dəqiqələrlə
# çəkir (ilk yazılışda məhz belə oldu).
YOX = 999999

# Açar tələb edən yazan endpoint-lər (metod, yol)
QORUNANLAR = [
    ("post", "/api/analyze"),
    ("post", f"/api/sites/{YOX}/rag/yenile"),
    ("post", f"/api/analyze/{YOX}/muasir"),
    ("post", f"/api/analyze/{YOX}/klon"),
    ("post", f"/api/analyze/{YOX}/arsiv"),
    ("post", f"/api/analyze/{YOX}/pdf"),
    ("post", "/api/izleme"),
    ("delete", f"/api/izleme/{YOX}"),
    ("post", f"/api/izleme/{YOX}/yoxla"),
    ("post", "/api/xetalar"),
]


def _cagir(metod: str, yol: str, basliqlar: dict | None = None):
    """DELETE gövdə qəbul etmir — metoda görə `json` yalnız POST-a verilir."""
    return muvekkil.request(
        metod.upper(),
        yol,
        json={} if metod == "post" else None,
        headers=basliqlar,
    )


@pytest.fixture
def acarli(monkeypatch):
    """Serverdə açar qoyulmuş vəziyyəti təqlid edir."""
    monkeypatch.setattr(ayarlar, "api_acar", ACAR)
    yield ACAR


@pytest.fixture
def sinaq_sayti():
    db.baza_qur()
    with db.sessiya() as s:
        sayt = db.Sayt(url="https://qapi-sinaq.az", domain="qapi-sinaq.az")
        s.add(sayt)
        s.commit()
        site_id = sayt.id
    yield site_id
    with db.sessiya() as s:
        for sohbet in s.query(db.Sohbet).filter(db.Sohbet.site_id == site_id):
            s.delete(sohbet)
        sayt = s.get(db.Sayt, site_id)
        if sayt:
            s.delete(sayt)
        s.commit()


# ---------- açar qoyulmayanda heç nə dəyişmir ----------


@pytest.mark.parametrize("metod, yol", QORUNANLAR)
def test_acarsiz_serverde_qapi_aciqdir(metod, yol):
    """`API_ACAR` boşdursa 401 gəlməməlidir — lokal inkişaf pozulmur."""
    cavab = _cagir(metod, yol)
    assert cavab.status_code != 401


def test_health_acar_teleb_olunmadigini_gosterir():
    assert muvekkil.get("/api/health").json()["acar_teleb_olunur"] is False


# ---------- açar qoyulanda ----------


@pytest.mark.parametrize("metod, yol", QORUNANLAR)
def test_acarsiz_sorgu_401_alir(metod, yol, acarli):
    cavab = _cagir(metod, yol)
    assert cavab.status_code == 401
    assert "API açarı" in cavab.json()["detail"]


@pytest.mark.parametrize("metod, yol", QORUNANLAR)
def test_duzgun_acar_kecir(metod, yol, acarli):
    """401 olmamalıdır. 404/422 normaldır — qapıdan keçib məntiqə çatıb."""
    cavab = _cagir(metod, yol, {qapi.BASLIQ: acarli})
    assert cavab.status_code != 401


def test_yanlis_acar_kecmir(acarli):
    cavab = muvekkil.post("/api/xetalar", json={}, headers={qapi.BASLIQ: "yanlis-acar"})
    assert cavab.status_code == 401


def test_oxuyan_endpointler_aciq_qalir(acarli):
    """Ziyarətçi hazır analizlərə açarsız baxa bilməlidir."""
    assert muvekkil.get("/api/health").status_code == 200
    assert muvekkil.get("/api/sites").status_code == 200
    assert muvekkil.get("/api/izleme").status_code == 200
    assert muvekkil.get("/").status_code == 200


def test_health_acar_teleb_olundugunu_gosterir(acarli):
    assert muvekkil.get("/api/health").json()["acar_teleb_olunur"] is True


# ---------- sual limiti ----------


def test_ziyaretci_limite_dusur(acarli, sinaq_sayti, monkeypatch):
    monkeypatch.setattr(ayarlar, "gunluk_sual_limiti", 2)
    ip = "203.0.113.77"
    cache.sil(qapi._gunun_acari(ip))
    basliq = {"X-Forwarded-For": ip}

    for _ in range(2):
        cavab = muvekkil.post(
            f"/api/sites/{sinaq_sayti}/chat", json={"sual": "salam"}, headers=basliq
        )
        assert cavab.status_code == 200

    ucuncu = muvekkil.post(
        f"/api/sites/{sinaq_sayti}/chat", json={"sual": "salam"}, headers=basliq
    )
    assert ucuncu.status_code == 429
    assert "limiti doldu" in ucuncu.json()["detail"]

    cache.sil(qapi._gunun_acari(ip))


def test_sahib_limite_dusmur(acarli, sinaq_sayti, monkeypatch):
    """Düzgün açarla gələn limitə düşmür — sahibin öz saytıdır."""
    monkeypatch.setattr(ayarlar, "gunluk_sual_limiti", 1)
    ip = "203.0.113.88"
    cache.sil(qapi._gunun_acari(ip))
    basliq = {"X-Forwarded-For": ip, qapi.BASLIQ: acarli}

    for _ in range(3):
        cavab = muvekkil.post(
            f"/api/sites/{sinaq_sayti}/chat", json={"sual": "salam"}, headers=basliq
        )
        assert cavab.status_code == 200

    cache.sil(qapi._gunun_acari(ip))


def test_acar_yoxdursa_limit_de_yoxdur(sinaq_sayti, monkeypatch):
    """Lokalda (açarsız) söhbət məhdudlaşdırılmır."""
    monkeypatch.setattr(ayarlar, "gunluk_sual_limiti", 1)
    ip = "203.0.113.99"
    cache.sil(qapi._gunun_acari(ip))

    for _ in range(3):
        cavab = muvekkil.post(
            f"/api/sites/{sinaq_sayti}/chat",
            json={"sual": "salam"},
            headers={"X-Forwarded-For": ip},
        )
        assert cavab.status_code == 200


# ---------- təhlükəsizlik başlıqları ----------
#
# Bunlar əvvəl Caddy-də idi. Railway-də tərs proxy bizim deyil, ona görə
# tətbiqin özünə köçürüldü — və test məhz ona görə lazımdır ki, bir daha
# hostinq dəyişəndə səssizcə itməsinlər.


def test_onizlemede_sandbox_var():
    """Modelin yazdığı HTML təcrid olunmalıdır (skript işləməsin).

    Analiz olmadığına görə cavab 404-dür, amma başlıq yenə qoyulmalıdır —
    middleware yola baxır, nəticəyə yox.
    """
    cavab = muvekkil.get(f"/api/analyze/{YOX}/muasir/onizleme")
    assert cavab.headers.get("content-security-policy") == "sandbox"


def test_adi_sehifede_sandbox_yoxdur():
    """Öz interfeysimizə tətbiq olunsa səhifə işləməz."""
    assert "content-security-policy" not in muvekkil.get("/").headers
    assert "content-security-policy" not in muvekkil.get("/api/health").headers


def test_umumi_basliqlar_her_cavabda():
    basliqlar = muvekkil.get("/api/health").headers
    assert basliqlar["x-content-type-options"] == "nosniff"
    assert basliqlar["x-frame-options"] == "SAMEORIGIN"
    assert basliqlar["referrer-policy"] == "strict-origin-when-cross-origin"


# ---------- IP-nin oxunması ----------


def test_saxta_x_forwarded_for_isleməz():
    """Caddy gördüyü IP-ni başlığın SONUNA əlavə edir, ona görə sonuncu alınır —
    müştəri əvvələ saxta IP yazsa da limitdən yaxa qurtara bilmir."""

    class YalanciSorgu:
        headers = {"X-Forwarded-For": "1.1.1.1, 2.2.2.2, 203.0.113.5"}
        client = None

    assert qapi._ip(YalanciSorgu()) == "203.0.113.5"


def test_basliq_yoxdursa_muveqqil_ipi_alinir():
    class YalanciSorgu:
        headers: dict = {}

        class client:
            host = "198.51.100.7"

    assert qapi._ip(YalanciSorgu()) == "198.51.100.7"
