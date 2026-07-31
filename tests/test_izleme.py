"""Gün 10 testləri — izləmə xidməti, iş xətaları və n8n workflow faylları."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import analiz, db, izleme
from backend.main import app

muvekkil = TestClient(app)

N8N = Path(__file__).resolve().parent.parent / "n8n"


# ---------- köməkçi ----------


@pytest.fixture
def sinaq_sayti():
    """Müvəqqəti sayt yaradır və testdən sonra silir."""
    db.baza_qur()
    with db.sessiya() as s:
        sayt = db.Sayt(url="https://izleme-sinaq.az", domain="izleme-sinaq.az")
        s.add(sayt)
        s.commit()
        site_id = sayt.id

    yield site_id

    with db.sessiya() as s:
        for iz in s.query(db.Izleme).filter(db.Izleme.site_id == site_id):
            s.delete(iz)
        for p in s.query(db.Sehife).filter(db.Sehife.site_id == site_id):
            s.delete(p)
        sayt = s.get(db.Sayt, site_id)
        if sayt:
            s.delete(sayt)
        s.commit()


def _sehife(url: str, izi: str) -> dict:
    return {"url": url, "basliq": "Sınaq", "metn": "mətn " + izi, "hash": izi}


# ---------- izləmə qeydi ----------


def test_izleme_elave_edilir_ve_silinir(sinaq_sayti):
    qeyd = izleme.elave_et(sinaq_sayti, cron="0 8 * * *", telegram_chat_id="123")
    assert qeyd["cron"] == "0 8 * * *"
    assert qeyd["telegram_chat_id"] == "123"

    with db.sessiya() as s:
        assert s.get(db.Sayt, sinaq_sayti).izlenir is True

    assert any(q["site_id"] == sinaq_sayti for q in izleme.siyahi())
    assert izleme.sil(sinaq_sayti) is True
    assert izleme.sil(sinaq_sayti) is False  # ikinci dəfə yoxdur

    with db.sessiya() as s:
        assert s.get(db.Sayt, sinaq_sayti).izlenir is False


def test_izleme_olmayan_sayta_qoyulmur():
    assert izleme.elave_et(999999).get("tapilmadi") is True


def test_min_saat_teze_yoxlanani_atir(sinaq_sayti):
    izleme.elave_et(sinaq_sayti)
    izleme._yoxlama_yaz(sinaq_sayti, "dəyişiklik yoxdur", False)

    hamisi = [q["site_id"] for q in izleme.siyahi()]
    suzulmus = [q["site_id"] for q in izleme.siyahi(min_saat=20)]

    assert sinaq_sayti in hamisi
    assert sinaq_sayti not in suzulmus


# ---------- dəyişikliyin tapılması ----------


def test_yoxla_deyisikliyi_tapir(sinaq_sayti, monkeypatch):
    izleme.elave_et(sinaq_sayti)
    monkeypatch.setattr(izleme.rag, "qur", lambda site_id, **k: {"chunk": 0})

    async def birinci(url, **kwargs):
        return [_sehife("https://izleme-sinaq.az/", "aaa")]

    async def ikinci(url, **kwargs):
        return [
            _sehife("https://izleme-sinaq.az/", "bbb"),      # dəyişdi
            _sehife("https://izleme-sinaq.az/yeni", "ccc"),  # yeni
        ]

    monkeypatch.setattr(izleme.crawler, "gez", birinci)
    ilk = asyncio.run(izleme.yoxla(sinaq_sayti))
    assert ilk["deyisdi"] is True          # baza boş idi — hamısı yenidir
    assert ilk["yeni"] == ["https://izleme-sinaq.az/"]

    monkeypatch.setattr(izleme.crawler, "gez", ikinci)
    sonra = asyncio.run(izleme.yoxla(sinaq_sayti))
    assert sonra["deyisdi"] is True
    assert sonra["deyisen"] == ["https://izleme-sinaq.az/"]
    assert sonra["yeni"] == ["https://izleme-sinaq.az/yeni"]
    assert "1 yeni səhifə" in sonra["xulase"]


def test_yoxla_deyisiklik_yoxdursa_sakit_qalir(sinaq_sayti, monkeypatch):
    izleme.elave_et(sinaq_sayti)
    monkeypatch.setattr(izleme.rag, "qur", lambda site_id, **k: {"chunk": 0})

    async def sabit(url, **kwargs):
        return [_sehife("https://izleme-sinaq.az/", "aaa")]

    monkeypatch.setattr(izleme.crawler, "gez", sabit)
    asyncio.run(izleme.yoxla(sinaq_sayti))
    ikinci = asyncio.run(izleme.yoxla(sinaq_sayti))

    assert ikinci["deyisdi"] is False
    assert ikinci["xulase"] == "dəyişiklik yoxdur"


def test_bos_gezis_silinme_kimi_oxunmur(sinaq_sayti, monkeypatch):
    """Sayt açılmasa "bütün səhifələr silindi" xəbərdarlığı getməməlidir."""
    izleme.elave_et(sinaq_sayti)
    monkeypatch.setattr(izleme.rag, "qur", lambda site_id, **k: {"chunk": 0})

    async def dolu(url, **kwargs):
        return [_sehife("https://izleme-sinaq.az/", "aaa")]

    async def bos(url, **kwargs):
        return []

    monkeypatch.setattr(izleme.crawler, "gez", dolu)
    asyncio.run(izleme.yoxla(sinaq_sayti))

    monkeypatch.setattr(izleme.crawler, "gez", bos)
    netice = asyncio.run(izleme.yoxla(sinaq_sayti))

    assert netice["deyisdi"] is False
    assert netice["silinen"] == []
    assert "gəzilə bilmədi" in netice["xulase"]


def test_yoxa_cixan_sehife_ikinci_defe_xeber_vermir(sinaq_sayti, monkeypatch):
    """Silinən səhifə bazadan da getməlidir.

    `sehifeleri_yaz` yalnız əlavə edib yenilədiyi üçün yoxa çıxan səhifə bazada
    qalırdı və hər yoxlamada yenidən "silinib" kimi hesablanırdı — Telegram-a
    eyni xəbər hər gün gedirdi.
    """
    izleme.elave_et(sinaq_sayti)
    monkeypatch.setattr(izleme.rag, "qur", lambda site_id, **k: {"chunk": 0})

    async def iki(url, **kwargs):
        return [
            _sehife("https://izleme-sinaq.az/", "aaa"),
            _sehife("https://izleme-sinaq.az/kohne", "bbb"),
        ]

    async def bir(url, **kwargs):
        return [_sehife("https://izleme-sinaq.az/", "aaa")]

    monkeypatch.setattr(izleme.crawler, "gez", iki)
    asyncio.run(izleme.yoxla(sinaq_sayti))

    monkeypatch.setattr(izleme.crawler, "gez", bir)
    birinci = asyncio.run(izleme.yoxla(sinaq_sayti))
    assert birinci["silinen"] == ["https://izleme-sinaq.az/kohne"]
    assert birinci["deyisdi"] is True

    ikinci = asyncio.run(izleme.yoxla(sinaq_sayti))
    assert ikinci["silinen"] == []
    assert ikinci["deyisdi"] is False
    assert ikinci["xulase"] == "dəyişiklik yoxdur"


def test_limite_catanda_silinme_hesablanmir(sinaq_sayti, monkeypatch):
    """Gəziş limitə dayanıbsa görünməyən səhifə silinmiş sayıla bilməz —
    sadəcə ona növbə çatmayıb."""
    izleme.elave_et(sinaq_sayti)
    monkeypatch.setattr(izleme.rag, "qur", lambda site_id, **k: {"chunk": 0})
    monkeypatch.setattr(izleme.ayarlar, "max_pages", 2)

    async def uc(url, **kwargs):
        return [_sehife(f"https://izleme-sinaq.az/{i}", f"h{i}") for i in range(3)]

    async def iki(url, **kwargs):
        return [_sehife(f"https://izleme-sinaq.az/{i}", f"h{i}") for i in range(2)]

    monkeypatch.setattr(izleme.crawler, "gez", uc)
    asyncio.run(izleme.yoxla(sinaq_sayti))

    monkeypatch.setattr(izleme.crawler, "gez", iki)
    netice = asyncio.run(izleme.yoxla(sinaq_sayti))

    assert netice["limite_catdi"] is True
    assert netice["silinen"] == []


def test_sehifeleri_sil_sayi_qaytarir(sinaq_sayti):
    analiz.sehifeleri_yaz(
        sinaq_sayti,
        [_sehife("https://izleme-sinaq.az/a", "1"), _sehife("https://izleme-sinaq.az/b", "2")],
    )

    assert analiz.sehifeleri_sil(sinaq_sayti, []) == 0
    assert analiz.sehifeleri_sil(sinaq_sayti, ["https://izleme-sinaq.az/a"]) == 1
    # İkinci dəfə silinəcək bir şey qalmır
    assert analiz.sehifeleri_sil(sinaq_sayti, ["https://izleme-sinaq.az/a"]) == 0

    with db.sessiya() as s:
        qalan = [
            p.url for p in s.query(db.Sehife).filter(db.Sehife.site_id == sinaq_sayti)
        ]
    assert qalan == ["https://izleme-sinaq.az/b"]


def test_yoxla_olmayan_sayt():
    assert asyncio.run(izleme.yoxla(999999)).get("tapilmadi") is True


# ---------- iş xətaları ----------


def test_xeta_yazilir_ve_oxunur():
    qeyd = izleme.xeta_yaz("n8n", "Sınaq workflow", "sındı: timeout")
    assert qeyd["id"] is not None

    sonuncular = izleme.xetalar(limit=5)
    assert sonuncular[0]["workflow"] == "Sınaq workflow"
    assert "timeout" in sonuncular[0]["xeta_metni"]

    with db.sessiya() as s:
        s.delete(s.get(db.IsXetasi, qeyd["id"]))
        s.commit()


# ---------- API ----------


def test_izleme_api_axini(sinaq_sayti):
    cavab = muvekkil.post(
        "/api/izleme", json={"site_id": sinaq_sayti, "cron": "0 7 * * *"}
    )
    assert cavab.status_code == 200
    assert cavab.json()["cron"] == "0 7 * * *"

    siyahi = muvekkil.get("/api/izleme").json()
    assert any(q["site_id"] == sinaq_sayti for q in siyahi)

    assert muvekkil.delete(f"/api/izleme/{sinaq_sayti}").status_code == 200
    assert muvekkil.delete(f"/api/izleme/{sinaq_sayti}").status_code == 404


def test_izleme_api_olmayan_sayt():
    cavab = muvekkil.post("/api/izleme", json={"site_id": 999999})
    assert cavab.status_code == 404


def test_xeta_api(monkeypatch):
    cavab = muvekkil.post(
        "/api/xetalar",
        json={"menbe": "n8n", "workflow": "API sınağı", "xeta_metni": "xəta"},
    )
    assert cavab.status_code == 200
    qeyd_id = cavab.json()["id"]

    assert any(x["id"] == qeyd_id for x in muvekkil.get("/api/xetalar").json())

    with db.sessiya() as s:
        s.delete(s.get(db.IsXetasi, qeyd_id))
        s.commit()


# ---------- n8n workflow faylları ----------

WORKFLOWLAR = [
    "1-analiz-tetikleyici.json",
    "2-reqib-izleme.json",
    "3-xeta-workflow.json",
    "4-gemma-agenti.json",
]


@pytest.mark.parametrize("fayl", WORKFLOWLAR)
def test_workflow_json_duzgundur(fayl):
    """İmport edilməmişdən əvvəl fayl özü sağlam olmalıdır."""
    data = json.loads((N8N / fayl).read_text(encoding="utf-8"))

    assert data["name"].startswith("SaytLupa")
    assert data["nodes"], "node siyahısı boşdur"

    adlar = set()
    for node in data["nodes"]:
        assert node["name"] not in adlar, f"təkrar node adı: {node['name']}"
        adlar.add(node["name"])
        assert node["type"] and node["typeVersion"]

    # Hər bağlantının hədəfi mövcud node olmalıdır — yoxsa n8n import edəndə qırılır
    for menbe, novler in data["connections"].items():
        assert menbe in adlar, f"olmayan node-dan bağlantı: {menbe}"
        for budaqlar in novler.values():
            for budaq in budaqlar:
                for baglanti in budaq or []:
                    assert baglanti["node"] in adlar, f"olmayan node-a bağlantı: {baglanti['node']}"


def test_workflowlar_unvani_muhit_deyisenden_alir():
    """Ünvan workflow-a yazılmamalıdır.

    Əvvəl `host.docker.internal:8000` sabit yazılırdı — lokalda işləyir, serverdə
    yox: Docker daxilində xidmətlər bir-birini `http://api:8000` kimi tanıyır.
    İndi ünvan `SAYTLUPA_API` mühit dəyişənindən gəlir, yəni eyni workflow həm
    lokalda, həm serverdə işləyir.
    """
    for fayl in WORKFLOWLAR:
        data = json.loads((N8N / fayl).read_text(encoding="utf-8"))
        for node in data["nodes"]:
            url = node.get("parameters", {}).get("url", "")
            if not url:
                continue
            assert "$env.SAYTLUPA_API" in url, f"{fayl} · {node['name']}: {url}"
            assert "host.docker.internal" not in url, f"{fayl} · {node['name']}"


def test_workflowlar_api_acarini_gonderir():
    """Serverdə yazan endpoint-lər açar tələb edir (bax `backend/qapi.py`) —
    açar workflow JSON-una yazılmır, mühit dəyişənindən gəlir."""
    for fayl in WORKFLOWLAR:
        data = json.loads((N8N / fayl).read_text(encoding="utf-8"))
        for node in data["nodes"]:
            p = node.get("parameters", {})
            if not p.get("url"):
                continue
            basliqlar = p.get("headerParameters", {}).get("parameters", [])
            acar = next((b for b in basliqlar if b["name"] == "X-API-Acar"), None)
            assert acar, f"{fayl} · {node['name']}: açar başlığı yoxdur"
            assert acar["value"] == "={{ $env.API_ACAR }}", f"{fayl} · {node['name']}"
            assert p.get("sendHeaders") is True, f"{fayl} · {node['name']}"


def test_bos_siyahi_bos_element_yaratmir():
    """`alwaysOutputData` bu node-da olmamalıdır.

    Açıq olsa, API boş siyahı qaytaranda n8n bir **boş** element buraxır və
    `Saytı yoxla` node-u `site_id`-siz ünvana sorğu göndərib 404 alır
    (2026-07-29-da canlı sınaqda tutuldu).
    """
    data = json.loads((N8N / "2-reqib-izleme.json").read_text(encoding="utf-8"))
    siyahi_node = next(n for n in data["nodes"] if n["name"] == "İzlənən saytlar")

    assert siyahi_node.get("alwaysOutputData") is not True


def test_izleme_workflowunda_retry_var():
    """Kurs tələbi: rəqib izləmə workflow-unda təkrar cəhd siyasəti olmalıdır."""
    data = json.loads((N8N / "2-reqib-izleme.json").read_text(encoding="utf-8"))
    yoxla = next(n for n in data["nodes"] if n["name"] == "Saytı yoxla")

    assert yoxla["retryOnFail"] is True
    assert yoxla["maxTries"] == 3
    assert yoxla["onError"] == "continueErrorOutput"  # bir sayt sınsa döngü dayanmır
