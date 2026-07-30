"""Boş nəticənin səbəbi izah olunur.

İki hal: domen məlumatı alınmayanda və sayt JS ilə qurulanda. Hər ikisində
istifadəçi "proqram tapmadı, yoxsa sayt belədir?" sualı ilə qalmamalıdır.
"""

from backend.collectors import js_sayt
from backend.collectors.domen import domen_sebeb

# `aiworks.az` analizindən gələn real xəta zənciri
AZ_XETALARI = [
    "HTTPStatusError: Client error '404 Not Found' for url "
    "'https://rdap.org/domain/aiworks.az'",
    "RuntimeError: 'az' üçün WHOIS serveri tapılmadı",
    "WhoisError: Whois command returned no output",
]

TEXNIKI_ADLAR = ("HTTPStatusError", "RuntimeError", "WhoisError", "rdap.org", "Traceback")


# ---------- domen xətası insan dilinə çevrilir ----------


def test_texniki_adlar_istifadeciye_gosterilmir():
    mesaj = domen_sebeb("aiworks.az", AZ_XETALARI)

    for ad in TEXNIKI_ADLAR:
        assert ad not in mesaj


def test_whois_olmayan_zona_adi_ile_izah_edilir():
    mesaj = domen_sebeb("aiworks.az", AZ_XETALARI)

    assert ".az" in mesaj
    assert "WHOIS" in mesaj


def test_saytin_qusuru_olmadigi_yazilir():
    """Bu, analiz olunan saytın problemi deyil — istifadəçi belə başa düşməməlidir."""
    mesaj = domen_sebeb("aiworks.az", AZ_XETALARI)

    assert "qüsur" in mesaj.lower()


def test_taninmayan_domen_ucun_ayri_izah():
    mesaj = domen_sebeb("yoxdur.com", [AZ_XETALARI[0].replace("aiworks.az", "yoxdur.com")])

    assert "reyestr" in mesaj.lower()
    assert "WHOIS" not in mesaj  # .com-un WHOIS-u var, səbəb başqadır


def test_sebeb_bilinmeyende_de_cumle_qaytarilir():
    mesaj = domen_sebeb("nese.az", ["ConnectTimeout: "])

    assert mesaj
    assert "ConnectTimeout" not in mesaj


# ---------- JS ilə qurulan sayt ----------

# `aiworks.az` — React/Vite qabığı: mətn yoxdur, məzmunu brauzer çəkir
JS_QABIGI = """<!doctype html><html lang="az">
<head><meta charset="utf-8"><title>AIWorks</title></head>
<body><div id="root"></div><script src="/assets/index-a1b2.js"></script></body></html>"""

ADI_SAYT = """<!doctype html><html><body><main>
<h1>Mağaza</h1><p>{}</p>
<a href="/haqqimizda">Haqqımızda</a></main></body></html>""".format("Məhsullarımıza baxın. " * 20)


def test_bos_qabiq_js_sayti_kimi_taninir():
    assert js_sayt.yoxla(JS_QABIGI)["js_ile_qurulur"] is True


def test_metni_olan_sayt_js_sayti_sayilmir():
    assert js_sayt.yoxla(ADI_SAYT)["js_ile_qurulur"] is False


def test_serverde_cizilen_sayt_js_sayti_sayilmir():
    """`#root` var, amma mətn də var — məzmun server tərəfdə çəkilib."""
    html = JS_QABIGI.replace(
        '<div id="root"></div>', '<div id="root"><p>' + "real mətn " * 40 + "</p></div>"
    )

    assert js_sayt.yoxla(html)["js_ile_qurulur"] is False


def test_next_js_adi_ile_taninir():
    html = JS_QABIGI.replace('id="root"', 'id="__next"')

    assert js_sayt.yoxla(html)["cerceve"] == "Next.js"


def test_taninmayan_cercevenin_adi_uydurulmur():
    assert js_sayt.yoxla(JS_QABIGI)["cerceve"] == ""


def test_qeyd_yalniz_js_saytinda_yazilir():
    assert js_sayt.yoxla(JS_QABIGI)["qeyd"]
    assert js_sayt.yoxla(ADI_SAYT)["qeyd"] == ""


def test_gorunen_metn_uzunlugu_qaytarilir():
    """Rəqəm interfeysdə göstərilir — uydurulmur, ölçülür."""
    assert js_sayt.yoxla(JS_QABIGI)["gorunen_metn"] == 0


def test_bos_html_cokmur():
    assert js_sayt.yoxla("")["js_ile_qurulur"] is False
