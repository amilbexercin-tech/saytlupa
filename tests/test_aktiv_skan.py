"""Aktiv skan mərhələsinin testləri — nuclei parseri, sahiblik, iş axını.

Şəbəkə tələb edən hissələr (real DNS, nuclei) mock-lanır. Baza sqlite ehtiyat
bazasında yaradılır (`db.baza_qur`), digər DB testləri ilə eyni nümunə.
"""

import time
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


def test_gedisat_endpointi_hadiseye_dusur(monkeypatch):
    """Worker → API → SSE zənciri REAL endpoint üzərindən yoxlanılır.

    Bu test ona görə var ki, worker testləri `_post`-u əvəzləyir və endpoint-i
    heç vaxt işlətmir. Bir dəfə `gorunus` sahəsi `hadise.gonder`-in `nov`
    parametri ilə toqquşdu: baza yenilənirdi, hadisə isə TypeError-la itirdi —
    ekran boş qalırdı. Bu zənciri qoruyur.
    """
    from fastapi.testclient import TestClient

    from backend import hadise
    from backend.main import app

    monkeypatch.setattr(ayarlar, "owned_domains", "hadise-test.az")
    db.baza_qur()
    job_id = aktiv.yeni_skan("https://hadise-test.az")["job_id"]
    hadise.temizle(aktiv._hid(job_id))

    muvekkil = TestClient(app)
    cavab = muvekkil.post(
        f"/api/aktiv-skan/{job_id}/gedisat",
        json={"mesaj": "yoxlanılır", "faiz": 42, "gorunus": "veziyyet"},
    )
    assert cavab.status_code == 200, cavab.text

    novbe = hadise.novbe(aktiv._hid(job_id))
    assert not novbe.empty(), "gedişat hadisəsi SSE növbəsinə düşmədi"
    qeyd = novbe.get_nowait()
    assert qeyd["nov"] == "gedisat"          # hadisə növü
    assert qeyd["gorunus"] == "veziyyet"     # interfeys göstərilişi
    assert qeyd["faiz"] == 42

    # Test bazası qaçışlar arasında qalır: iş «gozleyir» qalsa, növbəti
    # qaçışda `novbeden_goturt()` onu götürüb başqa testi pozar.
    aktiv.dayandir(job_id)


# ---------- worker: canlı gedişat ----------
#
# Əsas tələb: nuclei şablonları yükləyərkən **dəqiqələrlə** heç nə yazmır.
# Worker o vaxt da gedişat göndərməli, dayandırmanı və vaxt limitini
# yoxlamalıdır. Aşağıdakı testlər məhz bunu qoruyur.


class _SahteBoru:
    """Saxta boru: (gecikmə, sətir) addımları. Sətir None-dursa yalnız gözləyir."""

    def __init__(self, addimlar=()):
        self._addimlar = list(addimlar)

    def __iter__(self):
        for gecikme, setir in self._addimlar:
            time.sleep(gecikme)
            if setir is not None:
                yield setir


class _SahteProses:
    def __init__(self, stdout, stderr):
        self.stdout, self.stderr = stdout, stderr
        self.oldurulub = False

    def poll(self):
        return 1 if self.oldurulub else None

    def kill(self):
        self.oldurulub = True

    def wait(self, timeout=None):
        return 0


def _worker_qur(monkeypatch, stdout=(), stderr=(), cavab=None):
    """Worker-i şəbəkəsiz qurur; göndərilən bütün POST-ları toplayır."""
    from scripts import aktiv_worker as w

    gonderilenler: list[tuple[str, dict]] = []

    def sahte_post(yol, govde):
        gonderilenler.append((yol, govde))
        return dict(cavab or {})

    monkeypatch.setattr(w, "_post", sahte_post)
    monkeypatch.setattr(w, "TIK", 0.2)
    monkeypatch.setattr(w, "_nuclei_yol", lambda: "nuclei")
    monkeypatch.setattr(
        w, "_prosess_ac",
        lambda emr: _SahteProses(_SahteBoru(stdout), _SahteBoru(stderr)),
    )
    return w, gonderilenler


def _gedisatlar(gonderilenler):
    return [g for yol, g in gonderilenler if yol.endswith("/gedisat")]


def test_nuclei_susanda_da_gedisat_gonderilir(monkeypatch):
    """nuclei 1.5 saniyə heç nə yazmır — ekran yenə də canlı qalmalıdır."""
    w, gonderilenler = _worker_qur(monkeypatch, stdout=[(1.5, None)])
    w.skan_et(1, "https://x.az")

    # TIK = 0.2s → 1.5 saniyəlik sükutda bir neçə yeniləmə olmalıdır
    assert len(_gedisatlar(gonderilenler)) >= 4


def test_dayandirma_sukut_vaxti_da_isleyir(monkeypatch):
    """Dayandırma yoxlaması nuclei çıxışından asılı olmamalıdır."""
    w, gonderilenler = _worker_qur(
        monkeypatch, stdout=[(3.0, None)], cavab={"dayandirildi": True})
    basla = time.time()
    w.skan_et(1, "https://x.az")

    assert time.time() - basla < 2.0          # 3 saniyəni gözləmədən kəsilib
    assert not any(yol.endswith("/netice") for yol, _ in gonderilenler)


def test_vaxt_limiti_sukut_vaxti_da_isleyir(monkeypatch):
    """Vaxt limiti nuclei susarkən də tətbiq olunmalıdır."""
    w, gonderilenler = _worker_qur(monkeypatch, stdout=[(3.0, None)])
    monkeypatch.setattr(w, "MAX_MUDDET", 0.4)
    basla = time.time()
    w.skan_et(1, "https://x.az")

    assert time.time() - basla < 2.0
    assert any(yol.endswith("/netice") for yol, _ in gonderilenler)  # nəticə yenə yazılır


def test_stats_json_faizi_cixarilir(monkeypatch):
    """`-stats-json` sətrindən faiz oxunmalı və gedişata düşməlidir."""
    stats = ('{"duration":"0:00:12","errors":"0","hosts":"1","matched":"2",'
             '"percent":"42","requests":"400","rps":"33","templates":"8000",'
             '"total":"9000"}')
    w, gonderilenler = _worker_qur(monkeypatch, stderr=[(0.1, stats), (0.5, None)])
    w.skan_et(1, "https://x.az")

    assert any(g.get("faiz") == 42 for g in _gedisatlar(gonderilenler))


def test_nuclei_jurnali_ekrana_oturulur(monkeypatch):
    """nuclei-nin öz jurnal sətirləri istifadəçiyə görünməlidir."""
    w, gonderilenler = _worker_qur(monkeypatch, stderr=[
        (0.05, "                     __     _"),          # banner — atılmalı
        (0.05, "\t\tprojectdiscovery.io"),                # banner — atılmalı
        (0.05, "[INF] Templates loaded for current scan: 8412"),
        (0.3, None),
    ])
    w.skan_et(1, "https://x.az")

    mesajlar = [g["mesaj"] for g in _gedisatlar(gonderilenler)]
    assert any("8412" in m for m in mesajlar)
    assert not any("projectdiscovery.io" in m for m in mesajlar)


def test_tapinti_derhal_gonderilir_ve_neticeye_dusur(monkeypatch):
    """Hər tapıntı tapılan anda göndərilməli, sonda nəticəyə yazılmalıdır."""
    tapinti = ('{"template-id":"xss-1","matched-at":"https://x.az/a",'
               '"info":{"name":"Refleksiv XSS","severity":"high"}}')
    w, gonderilenler = _worker_qur(monkeypatch, stdout=[(0.05, tapinti), (0.3, None)])
    w.skan_et(1, "https://x.az")

    assert any("Refleksiv XSS" in g["mesaj"] for g in _gedisatlar(gonderilenler))
    netice = [g for yol, g in gonderilenler if yol.endswith("/netice")]
    assert netice and len(netice[0]["tapintilar"]) == 1
