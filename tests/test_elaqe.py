"""Sosial şəbəkə/əlaqə toplanması və PageSpeed xəta mesajları."""

import asyncio

import httpx

from backend import analiz
from backend.collectors.sehife import elaqe_cixart
from backend.collectors.sehife import topla as sehife_topla

ANA_SEHIFE = """
<!doctype html><html lang="az"><head><title>Mağaza</title></head>
<body>
  <main><h1>Xoş gəldiniz</h1><p>Məhsullarımıza baxın.</p></main>
</body></html>
"""

# Sosial linklər altlıqdadır və yalnız daxili səhifədədir — real saytlarda
# ən çox rast gəlinən hal
ELAQE_SEHIFESI = """
<!doctype html><html><body>
  <main><h1>Əlaqə</h1><p>Bizimlə əlaqə saxlayın: info@magaza.az, +994 12 345 67 89</p></main>
  <footer>
    <a href="https://www.instagram.com/magaza.az/">Instagram</a>
    <a href="https://facebook.com/magaza">Facebook</a>
    <a href="mailto:info@magaza.az">Yaz</a>
    <a href="/haqqimizda">Haqqımızda</a>
  </footer>
</body></html>
"""


# ---------- tək səhifədən çıxarış ----------


def test_altliqdaki_sosial_linkler_tapilir():
    netice = elaqe_cixart("https://magaza.az/elaqe", ELAQE_SEHIFESI)

    assert netice["sosial_linkler"]["Instagram"] == "https://www.instagram.com/magaza.az/"
    assert netice["sosial_linkler"]["Facebook"] == "https://facebook.com/magaza"


def test_eposta_ve_telefon_tapilir():
    netice = elaqe_cixart("https://magaza.az/elaqe", ELAQE_SEHIFESI)

    assert "info@magaza.az" in netice["epostalar"]
    assert any("345" in t for t in netice["telefonlar"])


def test_bos_sehifede_hec_ne_uydurulmur():
    netice = elaqe_cixart("https://magaza.az", ANA_SEHIFE)

    assert netice["sosial_linkler"] == {}
    assert netice["epostalar"] == []
    assert netice["telefonlar"] == []


def test_toplayici_eyni_neticeni_verir():
    """`sehife` toplayıcısı da eyni funksiyanı işlədir."""
    netice = asyncio.run(sehife_topla("https://magaza.az/elaqe", ELAQE_SEHIFESI, {}))

    assert netice["ugurlu"] is True
    assert "Instagram" in netice["data"]["sosial_linkler"]


# ---------- səhifələr arası birləşdirmə ----------


def _xam_bos() -> dict:
    return {
        "neticeler": {
            "sehife": {
                "ugurlu": True,
                "data": {"sosial_linkler": {}, "epostalar": [], "telefonlar": []},
            }
        }
    }


def _gezilen(url: str, html: str) -> dict:
    return {"url": url, "basliq": "", "metn": "x", "hash": "h",
            "elaqe": elaqe_cixart(url, html)}


def test_daxili_sehifedeki_elaqe_analize_dusur():
    """Ana səhifədə heç nə yoxdur, `/elaqe` səhifəsində var — nəticə tapılmalıdır."""
    xam = _xam_bos()
    sehifeler = [
        _gezilen("https://magaza.az", ANA_SEHIFE),
        _gezilen("https://magaza.az/elaqe", ELAQE_SEHIFESI),
    ]

    analiz.elaqe_birlesdir(xam, sehifeler)
    data = xam["neticeler"]["sehife"]["data"]

    assert set(data["sosial_linkler"]) == {"Instagram", "Facebook"}
    assert "info@magaza.az" in data["epostalar"]
    # Hansı səhifədə tapıldığı qeyd olunur — şəffaflıq
    assert data["elaqe_menbeleri"]["Instagram"] == "https://magaza.az/elaqe"


def test_ana_sehifedeki_link_ustun_tutulur():
    xam = _xam_bos()
    xam["neticeler"]["sehife"]["data"]["sosial_linkler"] = {
        "Instagram": "https://instagram.com/resmi"
    }
    sehifeler = [_gezilen("https://magaza.az/elaqe", ELAQE_SEHIFESI)]

    analiz.elaqe_birlesdir(xam, sehifeler)
    data = xam["neticeler"]["sehife"]["data"]

    assert data["sosial_linkler"]["Instagram"] == "https://instagram.com/resmi"
    assert "Instagram" not in data["elaqe_menbeleri"]  # ana səhifədən gəlib


def test_birlesdirme_tekrarlari_atir():
    xam = _xam_bos()
    sehifeler = [
        _gezilen("https://magaza.az/elaqe", ELAQE_SEHIFESI),
        _gezilen("https://magaza.az/haqqimizda", ELAQE_SEHIFESI),
    ]

    analiz.elaqe_birlesdir(xam, sehifeler)
    data = xam["neticeler"]["sehife"]["data"]

    assert len(data["sosial_linkler"]) == 2
    assert data["epostalar"] == ["info@magaza.az"]


def test_gezis_olmayanda_cokmur():
    xam = _xam_bos()
    analiz.elaqe_birlesdir(xam, [])

    assert xam["neticeler"]["sehife"]["data"]["sosial_linkler"] == {}


# ---------- PageSpeed xəta mesajı ----------


def _http_xetasi(kod: int) -> httpx.HTTPStatusError:
    istek = httpx.Request("GET", "https://example.com")
    return httpx.HTTPStatusError(
        "xeta", request=istek, response=httpx.Response(kod, request=istek)
    )


def test_kvota_xetasi_izah_edilir():
    from backend.collectors.surat import pagespeed_sebeb

    mesaj = pagespeed_sebeb(_http_xetasi(429))

    assert "kvota" in mesaj.lower()
    assert "HTTPStatusError" not in mesaj  # texniki ad istifadəçiyə heç nə demir


def test_acarsiz_halda_tovsiye_verilir(monkeypatch):
    from backend.collectors import surat

    monkeypatch.setattr(surat.ayarlar, "pagespeed_api_key", "")
    mesaj = surat.pagespeed_sebeb(_http_xetasi(429))

    assert "PAGESPEED_API_KEY" in mesaj


def test_acar_varsa_tovsiye_tekrarlanmir(monkeypatch):
    from backend.collectors import surat

    monkeypatch.setattr(surat.ayarlar, "pagespeed_api_key", "sinaq-acar")
    mesaj = surat.pagespeed_sebeb(_http_xetasi(429))

    assert "PAGESPEED_API_KEY" not in mesaj


def test_400_ucun_ayri_izah():
    from backend.collectors.surat import pagespeed_sebeb

    assert "yoxlaya bilmədi" in pagespeed_sebeb(_http_xetasi(400))


def test_timeout_ayrica_izah_edilir():
    from backend.collectors.surat import pagespeed_sebeb

    assert "cavab vermədi" in pagespeed_sebeb(httpx.TimeoutException("gec"))


# ---------- bazaya yazma ----------


def test_elaqe_sahesi_bazaya_yazilmir(monkeypatch):
    """Crawler qeydə `elaqe` sahəsi əlavə edir — `pages` cədvəlində belə sütun yoxdur."""
    from backend import db

    db.baza_qur()
    with db.sessiya() as s:
        sayt = db.Sayt(url="https://elaqe-sinaq.az", domain="elaqe-sinaq.az")
        s.add(sayt)
        s.commit()
        site_id = sayt.id

    try:
        sayi = analiz.sehifeleri_yaz(
            site_id, [_gezilen("https://elaqe-sinaq.az/elaqe", ELAQE_SEHIFESI)]
        )
        assert sayi == 1
    finally:
        with db.sessiya() as s:
            for p in s.query(db.Sehife).filter(db.Sehife.site_id == site_id):
                s.delete(p)
            s.delete(s.get(db.Sayt, site_id))
            s.commit()
