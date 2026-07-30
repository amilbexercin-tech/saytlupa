"""RAG testləri — chunking, embedding, RRF, yaddaş (şəbəkəsiz)."""

import pytest

from backend.rag import chunker, embedder, reranker
from backend.rag.store import _rrf, _vektor_metni

QISA = "Sifarişlər 2-3 iş günü ərzində çatdırılır."

UZUN = "\n\n".join(
    [
        "Çatdırılma şərtləri. " + "Bakı daxilində çatdırılma pulsuzdur. " * 12,
        "Ödəniş üsulları. " + "Kartla və ya nağd ödəniş mümkündür. " * 12,
        "Zəmanət. " + "Bütün məhsullara 12 ay zəmanət verilir. " * 12,
    ]
)


# ---------- chunking ----------


def test_qisa_metn_bir_parca_qalir():
    parcalar = chunker.bol(QISA * 4)
    assert len(parcalar) == 1


def test_cox_qisa_metn_atilir():
    assert chunker.bol("salam") == []


def test_bos_metn_bos_qaytarir():
    assert chunker.bol("") == []
    assert chunker.bol(None) == []


def test_uzun_metn_bolunur():
    parcalar = chunker.bol(UZUN)
    assert len(parcalar) > 1
    assert all(len(p) <= chunker.OLCU * 1.6 for p in parcalar)


def test_parcalar_ust_uste_dusur():
    """Qonşu parçaların kəsişməsi olmalıdır ki, cümlə sərhəddə itməsin."""
    parcalar = chunker.bol(UZUN)
    birinci_sozler = set(parcalar[0].split())
    ikinci_sozler = set(parcalar[1].split())
    assert birinci_sozler & ikinci_sozler


def test_butun_mezmun_saxlanilir():
    parcalar = chunker.bol(UZUN)
    hamisi = " ".join(parcalar)
    for acar in ("Çatdırılma şərtləri", "Ödəniş üsulları", "Zəmanət"):
        assert acar in hamisi


def test_sehife_bolunende_basliq_elave_olunur():
    parcalar = chunker.sehifeni_bol({"basliq": "Çatdırılma", "metn": UZUN})
    assert parcalar
    assert all(p["metn"].startswith("Çatdırılma") for p in parcalar)
    assert parcalar[0]["sira"] == 0


# ---------- lokal embedding ----------


def test_lokal_vektor_olcusu_ve_normasi():
    vektor = embedder.lokal_vektor("çatdırılma neçə gün çəkir")
    assert len(vektor) == embedder.OLCU
    uzunluq = sum(d * d for d in vektor) ** 0.5
    assert uzunluq == pytest.approx(1.0, abs=1e-6)


def test_lokal_vektor_sabitdir():
    assert embedder.lokal_vektor("salam") == embedder.lokal_vektor("salam")


def test_oxsar_metnler_yaxin_olur():
    a = embedder.lokal_vektor("çatdırılma 2-3 iş günü çəkir")
    b = embedder.lokal_vektor("çatdırılma neçə iş günü çəkir")
    c = embedder.lokal_vektor("şirkət 2015-ci ildə yaradılıb")
    assert embedder.oxsarliq(a, b) > embedder.oxsarliq(a, c)


def test_bos_vektorlar_oxsarligi_sifirdir():
    assert embedder.oxsarliq([], [1.0, 2.0]) == 0.0


def test_vektorla_bos_siyahi():
    vektorlar, menbe = embedder.vektorla([])
    assert vektorlar == []
    assert menbe in ("lokal", "gemini")


# ---------- RRF ----------


def test_rrf_iki_siyahini_birlesdirir():
    vektor = [{"id": 1}, {"id": 2}, {"id": 3}]
    acar = [{"id": 3}, {"id": 4}]
    netice = _rrf([vektor, acar])
    idler = [n["id"] for n in netice]
    # 3 hər iki siyahıda var — birinci olmalıdır
    assert idler[0] == 3
    assert set(idler) == {1, 2, 3, 4}


def test_rrf_bos_siyahilarla_isleyir():
    assert _rrf([[], []]) == []


def test_vektor_metni_formati():
    assert _vektor_metni([0.5, -0.25]) == "[0.500000,-0.250000]"


# ---------- re-ranker ----------


def test_rerank_sondurulubse_axtaris_sirasi_qalir():
    namizedler = [{"id": i, "metn": f"parça {i}"} for i in range(1, 6)]
    secilmis, olcme = reranker.sirala("sual", namizedler, ust=3, menbe="")
    assert [n["id"] for n in secilmis] == [1, 2, 3]
    assert olcme["usul"] == "axtaris_sirasi"


def test_rerank_bos_namizedle_sinmir():
    secilmis, olcme = reranker.sirala("sual", [], menbe="gemma")
    assert secilmis == []


def test_ballar_oxunur():
    cavab = {"ballar": [{"id": 1, "bal": 9}, {"id": 2, "bal": 0}]}
    assert reranker._ballari_oxu(cavab, 3) == {1: 9.0, 2: 0.0}


def test_ballar_yanlis_formatda_bos_qaytarir():
    assert reranker._ballari_oxu({"zibil": 1}, 3) == {}
    assert reranker._ballari_oxu(["mətn"], 3) == {}


def test_ballar_diapazondan_kenari_kesir():
    cavab = [{"id": 1, "bal": 99}, {"id": 9, "bal": 5}]
    ballar = reranker._ballari_oxu(cavab, 3)
    assert ballar == {1: 10.0}  # 99 → 10, id=9 diapazondan kənar
