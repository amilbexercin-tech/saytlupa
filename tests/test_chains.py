"""LCEL zəncirlərinin testləri — saxta model ilə, şəbəkəsiz."""

import json

import pytest
from langchain_core.language_models import FakeListChatModel
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel

from backend.chains import model as model_modulu
from backend.chains.hesabat import normalla, xulase_qur
from backend.prompts import hesabat as hesabat_promptu
from backend.prompts import rag as rag_promptu
from backend.schemas import AIHesabat

XAM = {
    "url": "https://gul.az",
    "sehife_sayi": 12,
    "qoruma": {"qorunur": False, "xidmet": ""},
    "neticeler": {
        "domen": {
            "ugurlu": True,
            "data": {
                "domen": "gul.az",
                "yas_il": None,
                "menbe": "wayback (təxmini)",
                "qeydiyyatci": "",
                "arxiv_ipucu": {"en_azi_yas_il": 8.4, "ilk_arxiv_il": 2018},
            },
        },
        "dns": {
            "ugurlu": True,
            "data": {
                "a": ["1.2.3.4"], "cdn": "Cloudflare", "poct_xidmeti": "Google Workspace",
                "ipv6_destekleyir": False, "spf_var": True, "dmarc_var": False,
            },
        },
        "geo": {"ugurlu": True, "data": {"olke": "Azerbaijan", "seher": "Baku",
                                          "provayder": "Delta Telecom"}},
        "sertifikat": {"ugurlu": True, "data": {"veren": "Let's Encrypt",
                                                 "qalan_gun": 60, "protokol": "TLSv1.3"}},
        "sehife": {
            "ugurlu": True,
            "data": {
                "basliq": "Gül Salonu", "tesvir": "", "dil": "az", "canonical": "",
                "basliq_saylari": {"h1": 1, "h2": 4}, "sekil_sayi": 22,
                "skript_sayi": 15, "form_sayi": 1, "mobil_uygun": True,
                "daxili_link_sayi": 30, "xarici_link_sayi": 4,
                "sosial_linkler": {"Instagram": "..."},
                "epostalar": ["info@gul.az"], "telefonlar": [],
            },
        },
        "texnologiya": {"ugurlu": True, "data": {"texnologiyalar": ["WordPress", "jQuery"],
                                                  "server": "nginx", "guclendirici": "PHP"}},
        "dizayn": {
            "ugurlu": True,
            "data": {
                "esas_renqler": [{"reng": "#e91e63", "tekrar": 40}],
                "sriftler": [{"ad": "Roboto", "tekrar": 12}],
                "google_sriftler": ["Roboto"], "css_fayl_sayi": 6, "xarici_css_kb": 210.5,
            },
        },
        "reklam": {"ugurlu": True, "data": {"aletler": [{"ad": "Meta Pixel",
                                                          "kateqoriya": "Reklam"}]}},
        "surat": {
            "ugurlu": True,
            "data": {
                "oz_olcme": {"yuklenme_saniye": 2.4, "html_olcusu_kb": 180.2,
                             "sixilma": "gzip", "lazy_sekil_sayi": 0, "sekil_sayi": 22,
                             "css_sayi": 6, "skript_sayi": 15},
                "mobil": None,
            },
        },
    },
}

HESABAT_CAVABI = json.dumps(
    {
        "meqsed": "Onlayn gül satışı",
        "hedef_auditoriya": "Bakıda yaşayan 25-45 yaş arası alıcılar",
        "texnologiyalar": "WordPress + jQuery, nginx server",
        "performans_problemleri": ["22 şəkilin heç birində lazy loading yoxdur"],
        "seo_catismazliqlari": ["meta description yoxdur", "canonical təyin edilməyib"],
        "muasir_versiya_tovsiyeleri": ["şəkilləri WebP-yə keçir", "CSS-i birləşdir"],
    },
    ensure_ascii=False,
)


# ---------- xam məlumatın xülasəsi ----------


def test_xulase_esas_faktlari_daxil_edir():
    xulase = xulase_qur(XAM)
    for gozlenilen in (
        "gul.az", "Cloudflare", "Baku", "Let's Encrypt",
        "WordPress", "nginx", "#e91e63", "Roboto", "Meta Pixel",
    ):
        assert gozlenilen in xulase


def test_xulase_olmayan_melumati_isareleyir():
    xulase = xulase_qur(XAM)
    assert "Meta description: YOXDUR" in xulase
    assert "PageSpeed balı: alınmadı" in xulase


def test_xulase_texmini_yasi_isareleyir():
    """`.az` domenlərində yaş təxminidir — model bunu bilməlidir."""
    xulase = xulase_qur(XAM)
    assert "TƏXMİNİ" in xulase
    assert "8.4 il" in xulase


def test_xulase_ugursuz_toplayicini_atlayir():
    xam = {"url": "https://x.az", "neticeler": {
        "domen": {"ugurlu": False, "xeta": "sındı", "data": {}}}}
    xulase = xulase_qur(xam)
    assert "Domen: —" in xulase


def test_xulase_bot_qorumasini_bildirir():
    xam = dict(XAM)
    xam["qoruma"] = {"qorunur": True, "xidmet": "Cloudflare"}
    assert "DİQQƏT" in xulase_qur(xam)


def test_xulase_bos_analizde_sinmir():
    assert isinstance(xulase_qur({}), str)


# ---------- hesabat zənciri (saxta model ilə) ----------


def test_hesabat_zenciri_json_qaytarir():
    saxta = FakeListChatModel(responses=[HESABAT_CAVABI])
    prompt = ChatPromptTemplate.from_messages(
        [("system", hesabat_promptu.SISTEM), ("human", hesabat_promptu.INSAN)]
    )
    hazirliq = RunnableParallel(
        url=RunnableLambda(lambda x: x["url"]),
        melumat=RunnableLambda(lambda x: xulase_qur(x["xam"])),
    )
    zencir = hazirliq | prompt | saxta | JsonOutputParser(pydantic_object=AIHesabat)

    netice = zencir.invoke({"url": "https://gul.az", "xam": XAM})
    assert netice["meqsed"] == "Onlayn gül satışı"
    assert len(netice["seo_catismazliqlari"]) == 2


def test_hesabat_sxemi_dogrulanir():
    """Model natamam JSON qaytarsa Pydantic bunu tutmalıdır."""
    with pytest.raises(Exception):
        AIHesabat(meqsed="yalnız bu var")


# ---------- modelin cavabının normallaşdırılması ----------


def test_orfoqrafiya_ferqi_bagislanir():
    """Gemma real sınaqda `seo_catismazlıqlari` (nöqtəsiz ı) qaytardı və bütün
    hesabat sındı. Normallaşdırma bunu tutmalıdır."""
    xam = {
        "meqsed": "Dövlət xidmətləri",
        "hedef_auditoriya": "Azərbaycan sakinləri",
        "texnologiyalar": "Bootstrap, nginx",
        "performans_problemleri": ["CSS böyükdür"],
        "seo_catismazlıqlari": ["Meta description yoxdur"],   # ← ı ilə
        "muasir_versiya_tovsiyeleri": ["lazy loading əlavə et"],
    }
    netice = normalla(xam)
    assert netice["seo_catismazliqlari"] == ["Meta description yoxdur"]
    assert netice["_catmayan"] == []
    AIHesabat(**{k: v for k, v in netice.items() if not k.startswith("_")})


def test_catmayan_sahe_hesabati_oldurmur():
    netice = normalla({"meqsed": "yalnız bu var"})
    assert netice["meqsed"] == "yalnız bu var"
    assert netice["performans_problemleri"] == []
    assert netice["texnologiyalar"] == ""
    assert "seo_catismazliqlari" in netice["_catmayan"]


def test_siyahi_gozlenilende_metn_gelse_cevrilir():
    netice = normalla({"seo_catismazliqlari": "birinci\nikinci"})
    assert netice["seo_catismazliqlari"] == ["birinci", "ikinci"]


def test_metn_gozlenilende_siyahi_gelse_birlesir():
    netice = normalla({"meqsed": ["onlayn", "mağaza"]})
    assert netice["meqsed"] == "onlayn mağaza"


def test_boyuk_herf_ve_defis_bagislanir():
    netice = normalla({"MEQSED": "x", "hedef-auditoriya": "y"})
    assert netice["meqsed"] == "x"
    assert netice["hedef_auditoriya"] == "y"


def test_luget_olmayan_cavab_xeta_verir():
    with pytest.raises(ValueError):
        normalla(["siyahı"])


# ---------- RAG cavab zənciri ----------


def test_rag_zenciri_metn_qaytarir():
    saxta = FakeListChatModel(responses=["Çatdırılma 2-3 iş günü çəkir."])
    prompt = ChatPromptTemplate.from_messages(
        [("system", rag_promptu.SISTEM), ("human", rag_promptu.INSAN)]
    )
    zencir = prompt | saxta | StrOutputParser()

    cavab = zencir.invoke(
        {"yaddas": "", "kontekst": "[1] Sifarişlər 2-3 iş günü ərzində çatdırılır.",
         "sual": "Çatdırılma neçə gün çəkir?"}
    )
    assert "2-3 iş günü" in cavab


def test_rag_promptu_uydurmagi_qadagan_edir():
    assert "məlumat tapılmadı" in rag_promptu.SISTEM
    assert "uydurma" in rag_promptu.SISTEM


def test_rag_promptu_yaddasi_qebul_edir():
    prompt = ChatPromptTemplate.from_messages(
        [("system", rag_promptu.SISTEM), ("human", rag_promptu.INSAN)]
    )
    mesajlar = prompt.format_messages(
        yaddas="ƏVVƏLKİ SÖHBƏT:\nİstifadəçi: salam\n\n", kontekst="[1] mətn", sual="nə?"
    )
    assert "ƏVVƏLKİ SÖHBƏT" in mesajlar[1].content


# ---------- fallback zənciri ----------


def test_model_adi_saxta_modelde_isleyir():
    saxta = FakeListChatModel(responses=["a"])
    assert isinstance(model_modulu.model_adi(saxta), str)


def test_model_adi_none_ile_sinmir():
    assert model_modulu.model_adi(None) == "yoxdur"


def test_fallback_birinci_sinanda_ikinciye_kecir():
    """`with_fallbacks` — əsas model sınsa növbəti işə düşməlidir."""

    class HemiseSinan(FakeListChatModel):
        def _call(self, *args, **kwargs):
            raise RuntimeError("model əlçatmazdır")

    zencir = HemiseSinan(responses=["x"]).with_fallbacks(
        [FakeListChatModel(responses=["ehtiyat cavab"])]
    )
    assert zencir.invoke("salam").content == "ehtiyat cavab"
