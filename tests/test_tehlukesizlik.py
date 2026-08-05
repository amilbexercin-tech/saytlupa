"""Passiv təhlükəsizlik auditinin testləri — şəbəkəsiz.

Şəbəkə tələb edən hissələr (açıq fayl yoxlaması, HTTP→HTTPS yönləndirmə) təmiz
funksiyalardan ayrıdır; burada başlıq/cookie/məzmun/sertifikat qərarları və bal
düsturu yoxlanılır. Prinsip: açıq yalnız həqiqətən varsa yaranır, bal riyazidir.
"""

from backend.collectors import tehlukesizlik as tehl


def _idler(tapintilar):
    return {t["id"] for t in tapintilar}


# ---------- başlıqlar ----------

def test_basliqlar_yoxdursa_tapinti_yaranir():
    t = tehl._basliq_tapintilari({}, https=True)
    idler = _idler(t)
    assert "content-security-policy" in idler
    assert "strict-transport-security" in idler
    assert "x-content-type-options" in idler
    assert "x-frame-options" in idler


def test_dogru_basliqlar_tapinti_yaratmir():
    b = {
        "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
        "strict-transport-security": "max-age=31536000",
        "x-content-type-options": "nosniff",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": "geolocation=()",
        "x-frame-options": "SAMEORIGIN",
    }
    assert tehl._basliq_tapintilari(b, https=True) == []


def test_csp_frame_ancestors_x_frame_optionsu_evez_edir():
    b = {"content-security-policy": "frame-ancestors 'none'"}
    assert "x-frame-options" not in _idler(tehl._basliq_tapintilari(b, https=True))


def test_hsts_yalniz_https_uchun():
    # HTTP saytda HSTS gözlənilmir — səhv tapıntı yaranmamalıdır
    assert "strict-transport-security" not in _idler(tehl._basliq_tapintilari({}, https=False))


def test_server_versiya_sizmasi():
    t = tehl._basliq_tapintilari({"server": "nginx/1.18.0"}, https=True)
    assert "server_versiya" in _idler(t)
    # Versiyasız server adı ipucu vermir — tapıntı olmamalıdır
    t2 = tehl._basliq_tapintilari({"server": "cloudflare"}, https=True)
    assert "server_versiya" not in _idler(t2)


def test_x_powered_by_sizmasi():
    t = tehl._basliq_tapintilari({"x-powered-by": "PHP/8.1"}, https=True)
    assert "x_powered_by" in _idler(t)


# ---------- cookie ----------

def test_cookie_bayraqlari_catismir():
    t = tehl._cookie_tapintilari({"set-cookie": "sid=abc; Path=/"}, https=True)
    idler = _idler(t)
    assert {"cookie_secure", "cookie_httponly", "cookie_samesite"} <= idler


def test_tam_cookie_tapinti_yaratmir():
    b = {"set-cookie": "sid=abc; Secure; HttpOnly; SameSite=Lax"}
    assert tehl._cookie_tapintilari(b, https=True) == []


def test_cookie_yoxdursa_bos():
    assert tehl._cookie_tapintilari({}, https=True) == []


# ---------- məzmun ----------

def test_qarisiq_mezmun_https_sehifede():
    html = '<img src="http://misal.com/a.jpg"><script src="http://misal.com/x.js">'
    t = tehl._mezmun_tapintilari("https://sayt.az", html, https=True)
    assert "qarisiq_mezmun" in _idler(t)


def test_http_sehifede_qarisiq_mezmun_yoxlanmir():
    html = '<img src="http://misal.com/a.jpg">'
    assert "qarisiq_mezmun" not in _idler(tehl._mezmun_tapintilari("http://sayt.az", html, https=False))


def test_generator_versiya_sizmasi():
    html = '<meta name="generator" content="WordPress 6.2.1">'
    assert "generator_versiya" in _idler(tehl._mezmun_tapintilari("https://s.az", html, True))


def test_qovluq_siyahisi():
    html = "<html><head><title>Index of /uploads</title></head></html>"
    assert "qovluq_siyahisi" in _idler(tehl._mezmun_tapintilari("https://s.az", html, True))


# ---------- sertifikat ----------

def test_sertifikat_bitib():
    neticeler = {"sertifikat": {"ugurlu": True, "data": {"qalan_gun": -3, "protokol": "TLSv1.3"}}}
    assert "sert_bitib" in _idler(tehl._sertifikat_tapintilari(neticeler))


def test_sertifikat_tezlikle_bitir():
    neticeler = {"sertifikat": {"ugurlu": True, "data": {"qalan_gun": 8, "protokol": "TLSv1.3"}}}
    assert "sert_bitir" in _idler(tehl._sertifikat_tapintilari(neticeler))


def test_zeif_tls():
    neticeler = {"sertifikat": {"ugurlu": True, "data": {"qalan_gun": 90, "protokol": "TLSv1"}}}
    assert "zeif_tls" in _idler(tehl._sertifikat_tapintilari(neticeler))


def test_saglam_sertifikat_tapinti_yaratmir():
    neticeler = {"sertifikat": {"ugurlu": True, "data": {"qalan_gun": 90, "protokol": "TLSv1.3"}}}
    assert tehl._sertifikat_tapintilari(neticeler) == []


# ---------- bal düsturu ----------

def test_bos_tapinti_tam_bal():
    n = tehl.hesabla([])
    assert n["bal"] == 100 and n["herf"] == "A"


def test_kritik_tapinti_bali_ciddi_salir():
    n = tehl.hesabla([{"seviyye": "kritik"}])
    assert n["bal"] == 60 and n["herf"] == "C"
    assert n["sayi"]["kritik"] == 1


def test_bal_sifirin_altina_dushmur():
    n = tehl.hesabla([{"seviyye": "kritik"}] * 5)
    assert n["bal"] == 0 and n["herf"] == "F"


def test_tapintilar_seviyyeye_gore_siralanir():
    n = tehl.hesabla([{"seviyye": "asagi"}, {"seviyye": "kritik"}, {"seviyye": "orta"}])
    assert [t["seviyye"] for t in n["tapintilar"]] == ["kritik", "orta", "asagi"]
