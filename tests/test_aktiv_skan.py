"""Aktiv skan mərhələsinin testləri — nuclei parseri, sahiblik, iş axını.

Şəbəkə tələb edən hissələr (real DNS, nuclei) mock-lanır. Baza sqlite ehtiyat
bazasında yaradılır (`db.baza_qur`), digər DB testləri ilə eyni nümunə.
"""

import uuid

import pytest

from backend import aktiv, db, nuclei_parse, sahiblik
from backend.config import ayarlar


def _tek_domen() -> str:
    """Hər test üçün unikal domen — davamlı test bazasında toqquşma olmasın."""
    return f"test-{uuid.uuid4().hex[:10]}.az"


# ---------- nuclei_parse ----------

def test_severity_uygunlasmasi():
    q = {"template-id": "t1", "matched-at": "https://s.az/x",
         "info": {"name": "SQL Injection", "severity": "critical",
                  "description": "SQLi tapıldı", "remediation": "Parametrləşdir"}}
    t = nuclei_parse.bir_tapinti(q)
    assert t["seviyye"] == "kritik"
    assert t["ad"] == "SQL Injection"
    assert t["menbe"] == "aktiv"
    assert t["hell"] == "Parametrləşdir"
    assert "s.az" in t["subut"]


def test_cve_ve_istinad_toplanir():
    q = {"template-id": "cve-2021-1234", "matched-at": "https://s.az",
         "info": {"name": "Köhnə komponent", "severity": "high",
                  "reference": ["https://misal.com/cve"],
                  "classification": {"cve-id": ["cve-2021-1234"]}}}
    t = nuclei_parse.bir_tapinti(q)
    assert "CVE-2021-1234" in t["istinad"]
    assert "https://misal.com/cve" in t["istinad"]
    assert t["seviyye"] == "yuksek"


def test_extracted_results_subutda():
    q = {"template-id": "t", "matched-at": "https://s.az",
         "extracted-results": ["admin", "root"],
         "info": {"name": "Sızma", "severity": "medium"}}
    t = nuclei_parse.bir_tapinti(q)
    assert "admin" in t["subut"]


def test_adsiz_qeyd_atlanir():
    assert nuclei_parse.bir_tapinti({"matched-at": "x"}) is None
    assert nuclei_parse.bir_tapinti("zibil") is None


def test_parse_jsonl_bir_nece_setir():
    metn = (
        '{"template-id":"a","info":{"name":"A","severity":"low"}}\n'
        'zibil sətir\n'
        '{"template-id":"b","info":{"name":"B","severity":"info"}}\n'
    )
    t = nuclei_parse.parse_jsonl(metn)
    assert len(t) == 2
    assert {x["ad"] for x in t} == {"A", "B"}


# ---------- sahiblik ----------

def test_normalize():
    assert sahiblik._normalize("https://www.magaza.az/kataloq") == "magaza.az"
    assert sahiblik._normalize("magaza.az") == "magaza.az"


def test_allowlist_avtomatik_tesdiqli(monkeypatch):
    monkeypatch.setattr(ayarlar, "owned_domains", "malqara.az, oazis.az")
    assert sahiblik.domen_tesdiqlidir("https://malqara.az/x") is True
    assert sahiblik.domen_tesdiqlidir("oazis.az") is True


def test_tesdiqsiz_domen_false(monkeypatch):
    monkeypatch.setattr(ayarlar, "owned_domains", "")
    db.baza_qur()
    assert sahiblik.domen_tesdiqlidir("https://tesadufi-yoxdur-12345.az") is False


def test_token_yarat_ve_dns_ile_tesdiq(monkeypatch):
    monkeypatch.setattr(ayarlar, "owned_domains", "")
    db.baza_qur()
    domen = _tek_domen()
    info = sahiblik.token_yarat(domen)
    assert info["status"] == "gozleyir"
    assert info["token"] in info["dns_qeyd"]

    # DNS-i mock et — sanki TXT qeyd yerindədir
    monkeypatch.setattr(sahiblik, "_dns_txt_uygun", lambda d, t: True)
    netice = sahiblik.yoxla(domen)
    assert netice["status"] == "tesdiqli"
    assert sahiblik.domen_tesdiqlidir(domen) is True


def test_token_yoxdursa_yoxla_yoxdur(monkeypatch):
    monkeypatch.setattr(ayarlar, "owned_domains", "")
    db.baza_qur()
    netice = sahiblik.yoxla("hec-token-yoxdur-999.az")
    assert netice["status"] == "yoxdur"


# ---------- aktiv iş axını ----------

def test_yeni_skan_tesdiqsiz_domende_qadagan(monkeypatch):
    monkeypatch.setattr(ayarlar, "owned_domains", "")
    db.baza_qur()
    with pytest.raises(aktiv.TesdiqYoxdur):
        aktiv.yeni_skan("https://tesdiqsiz-domen-abc.az")


def test_is_axini_yaratma_novbe_netice(monkeypatch):
    monkeypatch.setattr(ayarlar, "owned_domains", "isaxini-test.az")
    db.baza_qur()

    yeni = aktiv.yeni_skan("https://isaxini-test.az")
    job_id = yeni["job_id"]
    assert aktiv.oxu(job_id)["status"] == "gozleyir"

    goturt = aktiv.novbeden_goturt()
    assert goturt is not None                       # ən azı bir iş var
    assert aktiv.oxu(job_id)["status"] in ("isleyir", "bitdi", "dayandirildi")

    tapinti = {"seviyye": "yuksek", "ad": "Test", "menbe": "aktiv"}
    hesab = aktiv.netice_yaz(job_id, [tapinti])
    assert hesab["bal"] == 80                        # 100 - 20 (yuksek)
    oxu = aktiv.oxu(job_id)
    assert oxu["status"] == "bitdi" and oxu["bal"] == 80


def test_dayandir(monkeypatch):
    monkeypatch.setattr(ayarlar, "owned_domains", "dayan-test.az")
    db.baza_qur()
    job_id = aktiv.yeni_skan("https://dayan-test.az")["job_id"]
    assert aktiv.dayandir(job_id) is True
    assert aktiv.oxu(job_id)["status"] == "dayandirildi"
    assert aktiv.dayandirilibmi(job_id) is True
