"""Müqayisədə etibarsız məlumatın üstün sayılmaması.

Bot qoruması arxasındakı və ya brauzerdə çəkilən saytda HTML-dən çıxarılan
rəqəmlər real sayta aid deyil (yoxlama səhifəsi / boş qabıq). Belə rəqəmlərlə
"üstündür" yazmaq uydurmadır — ona görə həmin ölçülərdə hökm verilmir.
"""

import pytest

from backend import db, muqayise


def _xam(*, yuklenme: float, skript: int, qoruma: dict | None = None,
         js_sayt: dict | None = None) -> dict:
    xam = {
        "yuklenme_saniye": yuklenme,
        "sehife_sayi": 5,
        "neticeler": {
            "sehife": {
                "ugurlu": True,
                "data": {"skript_sayi": skript, "sekil_sayi": 3, "h1_metnler": ["S"]},
            },
            "dizayn": {"ugurlu": True, "data": {"reng_sayi": 4}},
            "reklam": {"ugurlu": True, "data": {"sayi": 2}},
            "sertifikat": {"ugurlu": True, "data": {"qalan_gun": 60}},
            "domen": {"ugurlu": True, "data": {"yas_il": 5}},
        },
    }
    if qoruma:
        xam["qoruma"] = qoruma
    if js_sayt:
        xam["js_sayt"] = js_sayt
    return xam


def _sayt_yarat(s, ad: str, xam: dict):
    sayt = db.Sayt(url=f"https://{ad}", domain=ad)
    s.add(sayt)
    s.commit()
    analiz = db.Analiz(site_id=sayt.id, status="hazir", xam_json=xam, ai_hesabat={})
    s.add(analiz)
    s.commit()
    return sayt.id, analiz.id


@pytest.fixture
def normal_ve_qorunan():
    """Adi sayt (7 skript) + Cloudflare arxasındakı sayt (1 skript)."""
    db.baza_qur()
    with db.sessiya() as s:
        a = _sayt_yarat(s, "adi-sinaq.az", _xam(yuklenme=1.2, skript=7))
        b = _sayt_yarat(s, "qorunan-sinaq.az", _xam(
            yuklenme=3.4, skript=1,
            qoruma={"qorunur": True, "xidmet": "Cloudflare"},
        ))
        ids = (a, b)

    yield ids

    with db.sessiya() as s:
        for site_id, analiz_id in ids:
            qeyd = s.get(db.Analiz, analiz_id)
            if qeyd:
                s.delete(qeyd)
            qeyd = s.get(db.Sayt, site_id)
            if qeyd:
                s.delete(qeyd)
        s.commit()


def _olculer(netice: dict) -> dict:
    return {o["olcu"]: o for o in netice["olculer"]}


def test_qorunan_saytin_html_olcusu_ustun_sayilmir(normal_ve_qorunan):
    """1 skript < 7 skript, amma o 1 rəqəmi yoxlama səhifəsindəndir."""
    netice = muqayise.muqayise_et("adi-sinaq.az", "qorunan-sinaq.az")

    assert _olculer(netice)["Skript sayı"]["ustun"] == "etibarsiz"


def test_yalniz_saytdan_kenar_olculer_etibarli_qalir(normal_ve_qorunan):
    """WHOIS və TLS saytın verdiyi cavabdan asılı deyil — onlar etibarlıdır.

    Yüklənmə vaxtı isə etibarlı deyil: ölçülən şey yoxlama səhifəsinin
    açılma vaxtıdır, real saytınkı deyil.
    """
    olculer = _olculer(muqayise.muqayise_et("adi-sinaq.az", "qorunan-sinaq.az"))

    assert olculer["Sertifikat (qalan gün)"]["ustun"] == "beraber"
    assert olculer["Domen yaşı (il)"]["ustun"] == "beraber"
    assert olculer["Yüklənmə (san)"]["ustun"] == "etibarsiz"


def test_xeberdarliqda_sebeb_ve_domen_yazilir(normal_ve_qorunan):
    xeberdarliqlar = muqayise.muqayise_et("adi-sinaq.az", "qorunan-sinaq.az")["xeberdarliqlar"]

    assert len(xeberdarliqlar) == 1
    assert "qorunan-sinaq.az" in xeberdarliqlar[0]
    assert "Cloudflare" in xeberdarliqlar[0]


def test_iki_adi_saytda_xeberdarliq_olmur_ve_hokm_verilir():
    db.baza_qur()
    with db.sessiya() as s:
        a = _sayt_yarat(s, "birinci-adi.az", _xam(yuklenme=1.0, skript=7))
        b = _sayt_yarat(s, "ikinci-adi.az", _xam(yuklenme=2.0, skript=3))
    try:
        netice = muqayise.muqayise_et("birinci-adi.az", "ikinci-adi.az")

        assert netice["xeberdarliqlar"] == []
        assert _olculer(netice)["Skript sayı"]["ustun"] == "ikinci"  # 3 < 7
    finally:
        with db.sessiya() as s:
            for site_id, analiz_id in (a, b):
                s.delete(s.get(db.Analiz, analiz_id))
                s.delete(s.get(db.Sayt, site_id))
            s.commit()


def test_js_sayti_da_etibarsiz_sayilir():
    db.baza_qur()
    with db.sessiya() as s:
        a = _sayt_yarat(s, "adi-iki.az", _xam(yuklenme=1.0, skript=7))
        b = _sayt_yarat(s, "js-sinaq.az", _xam(
            yuklenme=2.0, skript=1,
            js_sayt={"js_ile_qurulur": True, "cerceve": "Next.js"},
        ))
    try:
        netice = muqayise.muqayise_et("adi-iki.az", "js-sinaq.az")

        assert _olculer(netice)["Skript sayı"]["ustun"] == "etibarsiz"
        assert "js-sinaq.az" in netice["xeberdarliqlar"][0]
    finally:
        with db.sessiya() as s:
            for site_id, analiz_id in (a, b):
                s.delete(s.get(db.Analiz, analiz_id))
                s.delete(s.get(db.Sayt, site_id))
            s.commit()
