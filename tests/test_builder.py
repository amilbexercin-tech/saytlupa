"""Təhvil funksiyalarının testləri (Gün 9) — şəbəkəsiz, modelsiz, bazasız.

Fayl sisteminə yazan funksiyalar `tmp_path` ilə sınanır; şəbəkə tələb edən
hissələr (arşivin yükləmə mərhələsi) təmiz funksiyalara bölünüb və ayrıca
yoxlanılır.
"""

import pytest
from bs4 import BeautifulSoup

from backend import builder
from backend.builder import arsiv, klon, kontekst, pdf
from backend.chains import muasir as muasir_zenciri

XAM = {
    "url": "https://gul.az",
    "sehife_sayi": 12,
    "qoruma": {"qorunur": False, "xidmet": ""},
    "neticeler": {
        "domen": {"ugurlu": True, "data": {"domen": "gul.az", "yas_il": None,
                                            "arxiv_ipucu": {"en_azi_yas_il": 8.4}}},
        "dns": {"ugurlu": True, "data": {"a": ["1.2.3.4"], "cdn": "Cloudflare",
                                          "spf_var": True, "dmarc_var": False}},
        "geo": {"ugurlu": True, "data": {"olke": "Azerbaijan", "seher": "Baku",
                                          "provayder": "Delta Telecom"}},
        "sertifikat": {"ugurlu": True, "data": {"veren": "Let's Encrypt",
                                                 "qalan_gun": 60, "protokol": "TLSv1.3"}},
        "sehife": {
            "ugurlu": True,
            "data": {
                "basliq": "Gül Salonu", "tesvir": "", "dil": "az",
                "basliq_saylari": {"h1": 1, "h2": 4, "h3": 6}, "sekil_sayi": 22,
                "skript_sayi": 15, "form_sayi": 1, "mobil_uygun": True,
                "viewport": "width=device-width, initial-scale=1",
                "daxili_link_sayi": 30, "xarici_link_sayi": 4,
                "daxili_linkler": ["https://gul.az/kataloq"],
                "h1_metnler": ["Təzə güllər"],
                "sosial_linkler": {"Instagram": "https://instagram.com/gul"},
                "epostalar": ["info@gul.az"], "telefonlar": [],
                "html_olcusu_kb": 180.2,
            },
        },
        "texnologiya": {"ugurlu": True, "data": {"texnologiyalar": ["WordPress", "jQuery"],
                                                  "server": "nginx", "guclendirici": "PHP"}},
        "dizayn": {
            "ugurlu": True,
            "data": {
                "esas_renqler": [{"reng": "#e91e63", "tekrar": 40},
                                 {"reng": "yanlis-hex", "tekrar": 2}],
                "sriftler": [{"ad": "Roboto", "tekrar": 12}],
                "ehtiyat_sriftler": ["sans-serif"], "google_sriftler": ["Roboto"],
                "css_fayl_sayi": 6, "xarici_css_kb": 210.5, "daxili_css_kb": 4.2,
                "reng_sayi": 34,
            },
        },
        "reklam": {"ugurlu": True, "data": {"aletler": [{"ad": "Meta Pixel"}]}},
        "surat": {
            "ugurlu": True,
            "data": {"oz_olcme": {"yuklenme_saniye": 2.4, "html_olcusu_kb": 180.2,
                                   "sixilma": "gzip", "lazy_sekil_sayi": 0,
                                   "sekil_sayi": 22, "css_sayi": 6, "skript_sayi": 15},
                      "mobil": None},
        },
    },
}

SEHIFELER = [
    {"url": "https://gul.az", "basliq": "Ana səhifə", "metn": "Təzə güllər " * 40},
    {"url": "https://gul.az/catdirilma", "basliq": "Çatdırılma",
     "metn": "Sifarişlər 2-3 iş günü ərzində çatdırılır."},
]

NETICE = {
    "id": 1, "site_id": 1, "url": "https://gul.az", "domain": "gul.az",
    "status": "hazir", "sehife_sayi": 12, "chunk_sayi": 81,
    "xam": XAM, "ai_hesabat": None, "sehifeler": SEHIFELER,
}


# ---------- müasir versiya zənciri (modelsiz) ----------


def test_temizle_cercive_atir():
    assert muasir_zenciri.temizle("```html\n<html><body>a</body></html>\n```").startswith(
        "<html>"
    )


def test_temizle_izahati_atir():
    xam = "Budur sizin sayt:\n\n<!DOCTYPE html>\n<html><body>x</body></html>"
    assert muasir_zenciri.temizle(xam).startswith("<!DOCTYPE html>")


def test_temizle_html_olmayanda_xeta_verir():
    with pytest.raises(ValueError):
        muasir_zenciri.temizle("Bağışlayın, bu saytı qura bilmirəm.")


def test_mezmun_metni_real_metnden_istifade_edir():
    metn = muasir_zenciri._mezmun_metni(SEHIFELER)
    assert "Çatdırılma" in metn and "2-3 iş günü" in metn


def test_mezmun_bos_olanda_isarelenir():
    assert "yığılmayıb" in muasir_zenciri._mezmun_metni([])


def test_melumat_metni_hesabat_tovsiyelerini_daxil_edir():
    hesabat = {"meqsed": "Gül satışı", "seo_catismazliqlari": ["meta description yoxdur"]}
    metn = muasir_zenciri._melumat_metni(XAM, hesabat)
    assert "Gül satışı" in metn
    assert "meta description yoxdur" in metn
    assert "#e91e63" in metn  # xam analizin xülasəsi də içindədir


def test_guclu_model_yoxdursa_sebeb_qaytarilir(monkeypatch):
    """Gemma ilə HTML yazmaq mənasızdır — düymə səbəbi izah etməlidir."""
    monkeypatch.setattr(muasir_zenciri, "guclu_model_var", lambda: False)
    netice = muasir_zenciri.yarat("https://gul.az", XAM)
    assert netice["html"] is None
    assert netice["olcme"]["ugurlu"] is False
    assert "açar" in netice["olcme"]["sebeb"]


# ---------- klon sənədləri ----------


def test_klon_bes_sened_yazir():
    senedler = klon.senedler("https://gul.az", XAM, SEHIFELER)
    assert len(senedler) == 5
    assert all(yol.startswith("docs/research/") for yol in senedler)


def test_klon_olculen_melumati_yazir():
    senedler = klon.senedler("https://gul.az", XAM, SEHIFELER)
    tokenler = senedler["docs/research/DESIGN_TOKENS.md"]
    stek = senedler["docs/research/TECH_STACK_ANALYSIS.md"]
    assert "#e91e63" in tokenler and "Roboto" in tokenler
    assert "WordPress" in stek and "nginx" in stek and "Cloudflare" in stek


def test_klon_tapilmayani_uydurmur():
    """Statik analizlə tapılmayan hər şey açıq işarələnməlidir."""
    senedler = klon.senedler("https://gul.az", XAM, SEHIFELER)
    tokenler = senedler["docs/research/DESIGN_TOKENS.md"]
    assert "NOT DETECTED" in tokenler
    assert "Spacing scale" in tokenler          # yoxlanmalı siyahıya düşüb
    assert "Border radius" in tokenler


def test_klon_real_mezmunu_ceviridir():
    senedler = klon.senedler("https://gul.az", XAM, SEHIFELER)
    komponentler = senedler["docs/research/COMPONENT_INVENTORY.md"]
    assert "Təzə güllər" in komponentler
    assert "info@gul.az" in komponentler
    assert "https://gul.az/catdirilma" in komponentler


def test_klon_emri_hazirdir():
    emr = klon._emr("https://gul.az", r"D:\SaytLupa\storage\klon\gul.az")
    assert "/clone-website https://gul.az" in emr


def test_klon_hedef_stek_cloner_sablonuna_uygundur():
    stek = klon.senedler("https://gul.az", XAM, SEHIFELER)[
        "docs/research/TECH_STACK_ANALYSIS.md"
    ]
    assert "Next.js 16" in stek and "shadcn/ui" in stek and "Tailwind CSS v4" in stek


# ---------- arşiv (təmiz hissələr) ----------


def test_yerli_ad_tehlukesizdir():
    ad = arsiv.yerli_ad("https://x.az/media/../gül şəkli.png?v=2", 3)
    assert ad.startswith("03_")
    assert "/" not in ad and ".." not in ad and " " not in ad


def test_yerli_ad_uzun_adi_qisaldir():
    assert len(arsiv.yerli_ad("https://x.az/" + "a" * 200 + ".css", 1)) <= 64


def test_resurs_unvanlari_tapilir():
    html = """<html><head>
      <link rel="stylesheet" href="/uslub.css">
      <link rel="icon" href="/favicon.ico">
      </head><body>
      <img src="/sekil.png"><img data-src="/lazy.png">
      <img src="data:image/png;base64,AAA">
      </body></html>"""
    supa = BeautifulSoup(html, "lxml")
    unvanlar = [u for _, _, u in arsiv._resurs_unvanlari(supa, "https://gul.az/")]
    assert "https://gul.az/uslub.css" in unvanlar
    assert "https://gul.az/favicon.ico" in unvanlar
    assert "https://gul.az/lazy.png" in unvanlar        # lazy loading ünvanı
    assert not any(u.startswith("data:") for u in unvanlar)


def test_css_daxilindeki_sekiller_tapilir():
    css = "body{background:url('img/fon.jpg')} .a{background:url(data:image/gif;base64,A)}"
    tapilanlar = arsiv._css_resurslari(css, "https://gul.az/css/uslub.css")
    assert tapilanlar == ["https://gul.az/css/img/fon.jpg"]


# ---------- PDF ----------


def test_pdf_yaradilir(tmp_path):
    yol = pdf.qur(NETICE, tmp_path / "hesabat.pdf")
    mezmun = yol.read_bytes()
    assert mezmun.startswith(b"%PDF")
    assert len(mezmun) > 2000


def test_pdf_ai_hesabatsiz_da_isleyir(tmp_path):
    netice = dict(NETICE, ai_hesabat=None)
    assert pdf.qur(netice, tmp_path / "a.pdf").exists()


def test_pdf_ai_hesabatla_isleyir(tmp_path):
    netice = dict(
        NETICE,
        ai_hesabat={
            "meqsed": "Onlayn gül satışı",
            "hedef_auditoriya": "Bakı sakinləri",
            "texnologiyalar": "WordPress",
            "performans_problemleri": ["lazy loading yoxdur"],
            "seo_catismazliqlari": ["meta description yoxdur"],
            "muasir_versiya_tovsiyeleri": ["şəkilləri WebP-yə keçir"],
        },
    )
    assert pdf.qur(netice, tmp_path / "b.pdf").stat().st_size > 2000


def test_pdf_bos_analizde_sinmir(tmp_path):
    bos = {"domain": "x.az", "url": "https://x.az", "status": "xeta", "xam": {}}
    assert pdf.qur(bos, tmp_path / "c.pdf").exists()


def test_pdf_xarakterleri_qacirilir():
    assert pdf.qacir("a & b <c>") == "a &amp; b &lt;c&gt;"


def test_pdf_srifti_azerbaycan_herflerini_bilir():
    """Helvetica `ə` hərfini tanımır — sistem şrifti tapılmalıdır."""
    adi, qalin = pdf.srift_qur()
    assert isinstance(adi, str) and isinstance(qalin, str)


# ---------- ortaq qatlar ----------


def test_temiz_ad_qovluq_qacisina_icaze_vermir():
    assert "/" not in kontekst.temiz_ad("../../etc/passwd")
    assert ".." not in kontekst.temiz_ad("..")


def test_naməlum_tehvil_novu_xeta_verir():
    with pytest.raises(ValueError):
        kontekst.qovluq("naməlum", "gul.az")


def test_butun_dord_duyme_yukleme_yolu_var():
    assert set(builder.YUKLEME) == {"muasir", "klon", "arsiv", "pdf"}


def test_yukleme_naməlum_novde_none_qaytarir():
    assert builder.yukle_yolu("virus", 1) is None


# ---------- müasir versiyanın yazılması ----------


def _muasir_sinaq(monkeypatch, tmp_path, html: str):
    """`qur()`-u şəbəkəsiz işlədir: kontekst və zəncir əvəz olunur."""
    from backend.builder import muasir

    monkeypatch.setattr(muasir.kontekst, "konteks", lambda a: {
        "url": "https://sinaq.az", "domain": "sinaq.az",
        "xam": {}, "sehifeler": [], "ai_hesabat": {},
    })
    monkeypatch.setattr(muasir.zencir, "yarat", lambda *a, **k: {
        "html": html, "olcme": {"model": "sinaq-model", "ugurlu": True},
    })
    monkeypatch.setattr(muasir.kontekst, "qovluq", lambda *a: tmp_path)
    return muasir.qur(1)


def test_muasir_fayli_yazilir_ve_olcu_qaytarilir(tmp_path, monkeypatch):
    """Uğurlu yol tam icra olunur — nəticə qaytarılanda sınmır."""
    # Ölçü KB-la yuvarlaqlaşdırılır, ona görə nümunə real səhifə boydadır
    boyuk = "<!DOCTYPE html><html><body>" + "salam " * 400 + "</body></html>"

    netice = _muasir_sinaq(monkeypatch, tmp_path, boyuk)

    assert netice["ugurlu"] is True
    assert netice["olcu_kb"] > 0
    assert (tmp_path / "index.html").exists()


def test_muasir_fayla_elave_qeyd_yazmir(tmp_path, monkeypatch):
    """Nə gəlirsə fayla o yazılır — üstünə mənşə şərhi əlavə edilmir."""
    xam_html = "<!DOCTYPE html><html><body>salam</body></html>"
    _muasir_sinaq(monkeypatch, tmp_path, xam_html)

    assert (tmp_path / "index.html").read_text(encoding="utf-8") == xam_html


def test_muasir_html_bos_olanda_sebeb_qaytarir(tmp_path, monkeypatch):
    netice = _muasir_sinaq(monkeypatch, tmp_path, "")

    assert netice["ugurlu"] is False
    assert not (tmp_path / "index.html").exists()
