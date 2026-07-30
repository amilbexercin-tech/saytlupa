"""Crawler, mətn çıxarma və hadisə brokeri testləri (şəbəkəsiz)."""

import asyncio

import pytest

from backend import hadise
from backend.crawler import _temiz_url, uygun_url
from backend.metn import barmaq_izi, cixart

HTML = """
<!doctype html><html><head><title>  Qiymətlər\n   -\n  Mağaza  </title></head>
<body>
  <nav>Ana səhifə Kataloq Əlaqə</nav>
  <header>Loqo</header>
  <div class="cookie-banner">Kukilərlə razısınız?</div>
  <main>
    <h1>Çatdırılma şərtləri</h1>
    <p>Sifarişlər 2-3 iş günü ərzində çatdırılır.</p>
    <p>Bakı daxilində çatdırılma pulsuzdur.</p>
  </main>
  <aside class="sidebar">Oxşar məhsullar</aside>
  <footer>© 2026 Mağaza</footer>
  <script>var x = 1;</script>
</body></html>
"""


# ---------- mətn çıxarma ----------


def test_basliq_bosluqlardan_temizlenir():
    basliq, _ = cixart(HTML)
    assert basliq == "Qiymətlər - Mağaza"


def test_esas_mezmun_saxlanilir():
    _, metn = cixart(HTML)
    assert "2-3 iş günü" in metn
    assert "Bakı daxilində" in metn


def test_menyu_footer_skript_atilir():
    _, metn = cixart(HTML)
    for zibil in ("Kataloq", "© 2026", "var x = 1", "Kukilərlə", "Oxşar məhsullar"):
        assert zibil not in metn


def test_barmaq_izi_deyisiklikde_deyisir():
    a = barmaq_izi("salam dünya")
    assert a == barmaq_izi("salam dünya")
    assert a != barmaq_izi("salam dünya!")


# ---------- URL qaydaları ----------


@pytest.mark.parametrize(
    "xam, gozlenilen",
    [
        ("https://gul.az/", "https://gul.az"),
        ("https://gul.az/kataloq/", "https://gul.az/kataloq"),
        ("https://gul.az/kataloq#bolme", "https://gul.az/kataloq"),
        ("https://gul.az", "https://gul.az"),
    ],
)
def test_url_normallasdirilir(xam, gozlenilen):
    assert _temiz_url(xam) == gozlenilen


def test_ana_sehife_iki_defe_yigilmir():
    """`site.az/` və `site.az` eyni səhifədir — normallaşdırma bunu təmin edir."""
    assert _temiz_url("https://gul.az/") == _temiz_url("https://gul.az")


@pytest.mark.parametrize(
    "url, uygunmu",
    [
        ("https://gul.az/kataloq", True),
        ("https://gul.az/haqqimizda", True),
        ("https://basqa.az/kataloq", False),      # başqa domen
        ("https://gul.az/senedler/qaydalar.pdf", False),  # fayl
        ("https://gul.az/logo.png", False),
        ("https://gul.az/wp-admin/index.php", False),     # idarə paneli
        ("https://gul.az/cart", False),                   # səbət
        ("https://gul.az/page/7", False),                 # sonsuz səhifələmə
        ("mailto:info@gul.az", False),
    ],
)
def test_uygun_url_filtri(url, uygunmu):
    assert uygun_url(url, "gul.az") is uygunmu


# ---------- hadisə brokeri ----------


def test_hadise_novbesi_isleyir():
    async def sinaq():
        hadise.temizle(999)
        novbe = hadise.novbe(999)
        hadise.gonder(999, "sehife", yigilan=1, hedef=10)
        hadise.bitir(999)

        birinci = await novbe.get()
        ikinci = await novbe.get()
        return birinci, ikinci

    birinci, ikinci = asyncio.run(sinaq())
    assert birinci == {"nov": "sehife", "yigilan": 1, "hedef": 10}
    assert ikinci["nov"] == "son"
    hadise.temizle(999)


def test_hadise_temizlenir():
    hadise.novbe(1000)
    assert hadise.aktivdir(1000) is True
    hadise.temizle(1000)
    assert hadise.aktivdir(1000) is False
