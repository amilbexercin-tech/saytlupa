"""Toplayıcı testləri — şəbəkəsiz, saxta HTML üzərində."""

import asyncio

import pytest

from backend.collectors import dizayn, qoruma, reklam, sehife, texnologiya
from backend.collectors.base import domen, kok_url, mutleq_url, tam_host
from backend.collectors.domen import _sahe_tap, _whois_tarix

NUMUNE_HTML = """
<!doctype html>
<html lang="az">
<head>
  <title>Gül Salonu Bakı</title>
  <meta name="description" content="Baküda gül çatdırılması">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta property="og:title" content="Gül Salonu">
  <link rel="canonical" href="https://gul.az/">
  <link rel="stylesheet" href="/style.css">
  <script src="https://cdn.shopify.com/s/shopify.js"></script>
  <script>gtag('config', 'G-ABC123');</script>
  <script src="https://mc.yandex.ru/metrika/tag.js"></script>
  <style>body{color:#2678d8;font-family:'Inter',sans-serif}</style>
</head>
<body>
  <h1>Bakıda gül çatdırılması</h1>
  <h2>Qiymətlər</h2>
  <img src="/1.jpg"><img src="/2.jpg" loading="lazy">
  <a href="/haqqimizda">Haqqımızda</a>
  <a href="https://gul.az/elaqe">Əlaqə</a>
  <a href="https://instagram.com/gulsalonu">Instagram</a>
  <a href="https://facebook.com/gulsalonu">Facebook</a>
  <p>Bizimlə əlaqə: info@gul.az, +994 50 123 45 67</p>
  <form><input name="ad"></form>
</body>
</html>
"""

BASLIQLAR = {"server": "nginx/1.24", "content-encoding": "gzip"}


def isle(korutin):
    return asyncio.run(korutin)


# ---------- base ----------


@pytest.mark.parametrize(
    "url, gozlenilen",
    [
        ("https://www.magaza.az/kataloq", "magaza.az"),
        ("http://alt.numune.co.uk/", "numune.co.uk"),
        ("https://gul.az", "gul.az"),
    ],
)
def test_domen_cixarilir(url, gozlenilen):
    assert domen(url) == gozlenilen


def test_host_ve_kok():
    assert tam_host("https://www.gul.az/kataloq?a=1") == "www.gul.az"
    assert kok_url("https://www.gul.az/kataloq?a=1") == "https://www.gul.az"


def test_mutleq_url():
    assert mutleq_url("https://gul.az/kataloq/", "../elaqe") == "https://gul.az/elaqe"


# ---------- qoruma ----------


def test_qoruma_cloudflare_tanidilir():
    n = qoruma.yoxla("<html><title>Just a moment...</title></html>", 403)
    assert n["qorunur"] is True
    assert n["xidmet"] == "Cloudflare"
    assert "yoxlama səhifəsi" in n["qeyd"]


def test_qoruma_normal_sehifede_isləmir():
    n = qoruma.yoxla(NUMUNE_HTML, 200)
    assert n["qorunur"] is False
    assert n["qeyd"] == ""


def test_qoruma_status_koduna_gore_bloklayir():
    assert qoruma.yoxla("<html>salam</html>", 429)["qorunur"] is True


# ---------- texnologiya ----------


def test_texnologiya_tapir():
    n = isle(texnologiya.topla("https://gul.az", NUMUNE_HTML, BASLIQLAR))
    tapilan = n["data"]["texnologiyalar"]
    assert "Shopify" in tapilan
    assert "nginx" in tapilan
    assert n["data"]["server"] == "nginx/1.24"


def test_texnologiya_bos_htmlde_sinmir():
    n = isle(texnologiya.topla("https://gul.az", "", {}))
    assert n["ugurlu"] is True
    assert n["data"]["sayi"] == 0


# ---------- reklam ----------


def test_reklam_aletleri_tapilir():
    n = isle(reklam.topla("https://gul.az", NUMUNE_HTML, BASLIQLAR))
    adlar = [a["ad"] for a in n["data"]["aletler"]]
    assert "Google Analytics 4" in adlar
    assert "Yandex Metrica" in adlar
    assert n["data"]["analitika_var"] is True


# ---------- sehife ----------


def test_sehife_meta_ve_struktur():
    d = isle(sehife.topla("https://gul.az", NUMUNE_HTML, BASLIQLAR))["data"]
    assert d["basliq"] == "Gül Salonu Bakı"
    assert d["tesvir"] == "Baküda gül çatdırılması"
    assert d["dil"] == "az"
    assert d["mobil_uygun"] is True
    assert d["sekil_sayi"] == 2
    assert d["form_sayi"] == 1
    assert d["basliq_saylari"]["h1"] == 1


def test_sehife_elaqe_ve_sosial():
    d = isle(sehife.topla("https://gul.az", NUMUNE_HTML, BASLIQLAR))["data"]
    assert "info@gul.az" in d["epostalar"]
    assert any("994" in t.replace(" ", "") for t in d["telefonlar"])
    assert set(d["sosial_linkler"]) == {"Instagram", "Facebook"}


def test_sehife_daxili_xarici_link_ayirir():
    d = isle(sehife.topla("https://gul.az", NUMUNE_HTML, BASLIQLAR))["data"]
    assert d["daxili_link_sayi"] == 2       # /haqqimizda + gul.az/elaqe
    assert d["xarici_link_sayi"] == 2       # instagram + facebook


# ---------- dizayn ----------


def test_umumi_sriftler_ayrilir():
    """`serif`, `monospace`, `Menlo` saytın dizayn seçimi deyil — ehtiyat dəyərlərdir."""
    css = (
        "body{font-family:'Inter',-apple-system,sans-serif}"
        "code{font-family:Menlo,Monaco,monospace}"
        "h1{font-family:Georgia,serif}"
    )
    oz, ehtiyat = dizayn._sriftler(css)
    assert "Inter" in oz
    assert "Georgia" in oz
    assert "serif" not in oz and "monospace" not in oz and "Menlo" not in oz
    assert "serif" in ehtiyat


def test_srift_var_ifadesi_atilir():
    oz, _ = dizayn._sriftler("body{font-family:var(--esas-srift)}")
    assert oz == []


def test_hex_renq_normallasir():
    assert dizayn._hex_normal("#ABC") == "#aabbcc"
    assert dizayn._hex_normal("#A1B2C3") == "#a1b2c3"


# ---------- domen köməkçiləri ----------


def test_whois_sahe_tapilir():
    metn = "Domain: gul.az\nRegistrar: AzNIC\nCreation Date: 2015-04-12\n"
    assert _sahe_tap(metn, ("registrar",)) == "AzNIC"
    assert _sahe_tap(metn, ("creation date",)) == "2015-04-12"
    assert _sahe_tap(metn, ("olmayan",)) == ""


@pytest.mark.parametrize("xam, il", [("2015-04-12", 2015), ("12-04-2015", 2015), ("2020-01-01T10:00:00Z", 2020)])
def test_whois_tarix_oxunur(xam, il):
    tarix = _whois_tarix(xam)
    assert tarix is not None and tarix.year == il


def test_whois_tarix_bos_qaytarir():
    assert _whois_tarix("") is None
    assert _whois_tarix("zibil") is None
