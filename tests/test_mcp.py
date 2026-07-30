"""Gün 11 testləri — müqayisə məntiqi və MCP alətləri."""

import asyncio
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from backend import db, mcp_server, muqayise
from backend.main import app

muvekkil = TestClient(app)
API = mcp_server.API


def _xam(yuklenme: float, texnologiyalar: list[str], tesvir: str = "") -> dict:
    """Analizin xam JSON-unun kiçildilmiş nüsxəsi."""
    return {
        "yuklenme_saniye": yuklenme,
        "sehife_sayi": 5,
        "rag": {"chunk_sayi": 12},
        "neticeler": {
            "sehife": {
                "ugurlu": True,
                "data": {
                    "tesvir": tesvir,
                    "og_basliq": "",
                    "canonical": "",
                    "dil": "az",
                    "h1_metnler": ["Salam"],
                    "skript_sayi": 7,
                    "sekil_sayi": 3,
                },
            },
            "texnologiya": {
                "ugurlu": True,
                "data": {"texnologiyalar": texnologiyalar, "server": "nginx"},
            },
            "dizayn": {"ugurlu": True, "data": {"reng_sayi": 4, "sriftler": ["Inter"]}},
            "reklam": {"ugurlu": True, "data": {"sayi": 2, "analitika_var": True}},
            "dns": {"ugurlu": True, "data": {"cdn": "Cloudflare", "ipv6_destekleyir": True}},
            "geo": {"ugurlu": True, "data": {"olke": "Almaniya", "provayder": "Hetzner"}},
            "sertifikat": {"ugurlu": True, "data": {"qalan_gun": 60}},
            "domen": {"ugurlu": True, "data": {"yas_il": 5}},
            # Sınmış toplayıcı: `data` oxunmamalıdır
            "surat": {"ugurlu": False, "data": {"oz_olcme": 999}},
        },
    }


@pytest.fixture
def iki_sayt():
    """İki sayt + hər birinə bir hazır analiz yaradır, sonda təmizləyir."""
    db.baza_qur()
    with db.sessiya() as s:
        a = db.Sayt(url="https://birinci-sinaq.az", domain="birinci-sinaq.az")
        b = db.Sayt(url="https://ikinci-sinaq.az", domain="ikinci-sinaq.az")
        s.add_all([a, b])
        s.commit()

        an_a = db.Analiz(
            site_id=a.id, status="hazir",
            xam_json=_xam(1.2, ["WordPress", "jQuery"], tesvir="var"),
            ai_hesabat={"meqsed": "xəbər saytı"},
        )
        an_b = db.Analiz(
            site_id=b.id, status="hazir",
            xam_json=_xam(3.4, ["Next.js", "jQuery"]),
            ai_hesabat={},
        )
        s.add_all([an_a, an_b])
        s.commit()
        ids = (a.id, b.id, an_a.id, an_b.id)

    yield ids

    with db.sessiya() as s:
        for analiz_id in ids[2:]:
            qeyd = s.get(db.Analiz, analiz_id)
            if qeyd:
                s.delete(qeyd)
        for site_id in ids[:2]:
            qeyd = s.get(db.Sayt, site_id)
            if qeyd:
                s.delete(qeyd)
        s.commit()


# ---------- sayt tapma ----------


def test_sayt_nomre_domen_ve_unvanla_tapilir(iki_sayt):
    site_id = iki_sayt[0]
    assert muqayise.sayt_tap(str(site_id)).id == site_id
    assert muqayise.sayt_tap("birinci-sinaq.az").id == site_id
    assert muqayise.sayt_tap("https://birinci-sinaq.az/haqqimizda").id == site_id


def test_olmayan_sayt_tapilmir():
    assert muqayise.sayt_tap("yoxdur-belə-sayt.az") is None
    assert muqayise.sayt_tap("") is None


# ---------- müqayisə ----------


def test_muqayise_ustunlukleri_duzgun_secir(iki_sayt):
    netice = muqayise.muqayise_et("birinci-sinaq.az", "ikinci-sinaq.az")
    olculer = {o["olcu"]: o for o in netice["olculer"]}

    # 1.2 san < 3.4 san — kiçik olan üstündür
    assert olculer["Yüklənmə (san)"]["ustun"] == "birinci"
    # eyni dəyər — bərabər
    assert olculer["Yığılan səhifə"]["ustun"] == "beraber"
    # şəkil sayının "yaxşı" istiqaməti yoxdur — üstünlük elan edilmir
    assert olculer["Şəkil sayı"]["ustun"] == "neytral"


def test_bos_saheler_bilinmir_kimi_gosterilir(iki_sayt):
    """Toplayıcı sahəni tapmayıbsa cədvəldə boş xana qalmamalıdır."""
    with db.sessiya() as s:
        analiz = s.get(db.Analiz, iki_sayt[2])
        # Dərin nüsxə: dayaz nüsxədə köhnə və yeni dəyər eyni obyekti göstərir,
        # SQLAlchemy dəyişikliyi görmür və UPDATE göndərmir.
        xam = json.loads(json.dumps(analiz.xam_json))
        xam["neticeler"]["dns"]["data"] = {"cdn": "", "ipv6_destekleyir": None}
        analiz.xam_json = xam
        s.commit()

    xulase = muqayise.muqayise_et("birinci-sinaq.az", "ikinci-sinaq.az")["xulase"]
    assert "**CDN:** bilinmir ↔ Cloudflare" in xulase


def test_muqayise_texnologiyalari_ayirir(iki_sayt):
    t = muqayise.muqayise_et("birinci-sinaq.az", "ikinci-sinaq.az")["texnologiya"]

    assert t["ortaq"] == ["jQuery"]
    assert t["yalniz_birinci"] == ["WordPress"]
    assert t["yalniz_ikinci"] == ["Next.js"]


def test_muqayise_seo_catismazligini_tapir(iki_sayt):
    netice = muqayise.muqayise_et("birinci-sinaq.az", "ikinci-sinaq.az")
    catismazliq = netice["seo_catismazliqlari"]

    # birincidə meta description var, ikincidə yoxdur
    assert "meta description" not in catismazliq["birinci-sinaq.az"]
    assert "meta description" in catismazliq["ikinci-sinaq.az"]


def test_sinmis_toplayicinin_datasi_oxunmur(iki_sayt):
    """`ugurlu: false` olan toplayıcının məlumatı hesabata düşməməlidir."""
    netice = muqayise.muqayise_et("birinci-sinaq.az", "ikinci-sinaq.az")
    assert "999" not in netice["xulase"]


def test_xulase_metni_cedvel_qaytarir(iki_sayt):
    xulase = muqayise.muqayise_et("birinci-sinaq.az", "ikinci-sinaq.az")["xulase"]

    assert "birinci-sinaq.az ↔ ikinci-sinaq.az" in xulase
    assert "| Ölçü |" in xulase
    assert "xəbər saytı" in xulase  # AI rəyi
    assert "hesabat yoxdur" in xulase  # ikincidə hesabat yoxdur — uydurulmur


def test_eyni_sayt_muqayise_edilmir(iki_sayt):
    netice = muqayise.muqayise_et("birinci-sinaq.az", "birinci-sinaq.az")
    assert netice["tapilmadi"] is True


def test_analizsiz_sayt_cokmur():
    """Analizi olmayan sayt müqayisəni sındırmamalıdır."""
    db.baza_qur()
    with db.sessiya() as s:
        bos = db.Sayt(url="https://bos-sayt.az", domain="bos-sayt.az")
        var = db.Sayt(url="https://dolu-sayt.az", domain="dolu-sayt.az")
        s.add_all([bos, var])
        s.commit()
        analiz = db.Analiz(site_id=var.id, status="hazir", xam_json=_xam(1.0, ["Vue"]))
        s.add(analiz)
        s.commit()
        idler = (bos.id, var.id, analiz.id)

    try:
        netice = muqayise.muqayise_et("bos-sayt.az", "dolu-sayt.az")
        assert netice["birinci"]["status"] == "analiz yoxdur"
        assert netice["birinci"]["yuklenme_saniye"] is None
        olcu = next(o for o in netice["olculer"] if o["olcu"] == "Yüklənmə (san)")
        assert olcu["ustun"] == "bilinmir"
        assert "bilinmir" in netice["xulase"]
    finally:
        with db.sessiya() as s:
            s.delete(s.get(db.Analiz, idler[2]))
            s.delete(s.get(db.Sayt, idler[0]))
            s.delete(s.get(db.Sayt, idler[1]))
            s.commit()


# ---------- API ----------


def test_muqayise_api(iki_sayt):
    cavab = muvekkil.get(
        "/api/muqayise", params={"sayt1": "birinci-sinaq.az", "sayt2": "ikinci-sinaq.az"}
    )
    assert cavab.status_code == 200
    assert cavab.json()["birinci"]["domain"] == "birinci-sinaq.az"


def test_muqayise_api_olmayan_sayt(iki_sayt):
    cavab = muvekkil.get(
        "/api/muqayise", params={"sayt1": "birinci-sinaq.az", "sayt2": "yoxdur.az"}
    )
    assert cavab.status_code == 404


# ---------- MCP alətləri (şəbəkə saxtalaşdırılır) ----------


@respx.mock
def test_mcp_analiz_baslatir():
    respx.post(f"{API}/api/analyze").mock(
        return_value=Response(
            200, json={"analiz_id": 7, "site_id": 3, "url": "https://example.com/"}
        )
    )
    metn = asyncio.run(mcp_server.sayt_analiz_et("https://example.com"))

    assert "analiz_id: 7" in metn
    assert metn.startswith("✅")


@respx.mock
def test_mcp_server_bagli_olanda_aydin_mesaj():
    respx.post(f"{API}/api/analyze").mock(side_effect=httpx.ConnectError)
    metn = asyncio.run(mcp_server.sayt_analiz_et("https://example.com"))

    assert "cavab vermir" in metn
    assert "uvicorn" in metn


@respx.mock
def test_mcp_sohbet_menbeleri_qaytarir():
    respx.get(f"{API}/api/sites").mock(
        return_value=Response(
            200,
            json=[{"id": 3, "url": "https://example.com/", "domain": "example.com"}],
        )
    )
    respx.post(f"{API}/api/sites/3/chat").mock(
        return_value=Response(
            200,
            json={
                "cavab": "Çatdırılma 2 gün çəkir.",
                "menbeler": [{"url": "https://example.com/kargo", "basliq": "Kargo"}],
                "session_id": 1,
                "olcme": {"namized": 20, "secilmis": 5, "model": "claude", "umumi_saniye": 3},
            },
        )
    )
    metn = asyncio.run(mcp_server.saytla_danis("example.com", "çatdırılma neçə gün?"))

    assert "Çatdırılma 2 gün çəkir." in metn
    assert "https://example.com/kargo" in metn


@respx.mock
def test_mcp_olmayan_sayt_ucun_movcudlari_sadalayir():
    respx.get(f"{API}/api/sites").mock(
        return_value=Response(
            200,
            json=[{"id": 3, "url": "https://example.com/", "domain": "example.com"}],
        )
    )
    metn = asyncio.run(mcp_server.saytla_danis("basqa-sayt.az", "sual"))

    assert "tapılmadı" in metn
    assert "example.com (id 3)" in metn


@respx.mock
def test_mcp_muqayise_xulaseni_qaytarir():
    respx.get(f"{API}/api/muqayise").mock(
        return_value=Response(200, json={"xulase": "# a.az ↔ b.az\n| Ölçü |"})
    )
    metn = asyncio.run(mcp_server.saytlari_muqayise_et("a.az", "b.az"))

    assert metn.startswith("# a.az ↔ b.az")


def test_uc_alet_qeydiyyatdan_kecib():
    adlar = {alet.name for alet in asyncio.run(mcp_server.mcp.list_tools())}
    assert adlar == {"sayt_analiz_et", "saytla_danis", "saytlari_muqayise_et"}
