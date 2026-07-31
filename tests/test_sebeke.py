"""SSRF qoruması testləri — server öz şəbəkəsini analiz edə bilməməlidir.

Şəbəkəsizdir: IP ünvanları hərfi verilir, ad həlli isə `_ipler` əvəzlənərək
təqlid olunur.
"""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import sebeke
from backend.main import app

muvekkil = TestClient(app)


# ---------- qapalı diapazonlar ----------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/",                 # SaytLupa-nın özü
        "http://169.254.169.254/metadata/v1/",    # bulud metadata xidməti
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://100.64.0.1/",                     # operator NAT-ı (CGNAT)
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://[fd00::1]/",
        "http://[64:ff9b::7f00:1]/",              # NAT64 → 127.0.0.1
        "http://[fe80::1]/",
    ],
)
def test_qapali_unvan_redd_edilir(url):
    assert sebeke.unvan_sebebi(url) != ""


@pytest.mark.parametrize("url", ["http://8.8.8.8/", "https://93.184.216.34/yol"])
def test_acik_ip_kecir(url):
    assert sebeke.unvan_sebebi(url) == ""


def test_yalniz_http_qebul_edilir():
    assert "http/https" in sebeke.unvan_sebebi("file:///etc/passwd")
    assert "http/https" in sebeke.unvan_sebebi("gopher://127.0.0.1/")


# ---------- ad həlli ----------


def test_ad_dns_ile_yoxlanilir(monkeypatch):
    """Zərərsiz görünən ad daxili IP-yə həll oluna bilər."""
    monkeypatch.setattr(sebeke, "_ipler", lambda host: ["169.254.169.254"])
    assert "daxili şəbəkə" in sebeke.host_sebebi("zerersiz-gorunen.az")


def test_acik_ada_icaze_verilir(monkeypatch):
    monkeypatch.setattr(sebeke, "_ipler", lambda host: ["93.184.216.34"])
    assert sebeke.host_sebebi("example.com") == ""


def test_bir_ip_qapalidirsa_bes_edir(monkeypatch):
    """A qeydi açıq, AAAA qeydi daxili ola bilər — hər ikisi yoxlanılır."""
    monkeypatch.setattr(sebeke, "_ipler", lambda host: ["93.184.216.34", "::1"])
    assert sebeke.host_sebebi("iki_uzlu.az") != ""


def test_ad_hell_olunmasa_bloklanmir(monkeypatch):
    """Ad ümumiyyətlə həll olunmursa bu, "daxili ünvan" demək deyil —
    sorğu onsuz da alınmayacaq və səbəbi başqa cürdür."""
    monkeypatch.setattr(sebeke, "_ipler", lambda host: [])
    assert sebeke.host_sebebi("yoxdur.invalid") == ""


def test_yoxla_xeta_qaldirir():
    with pytest.raises(sebeke.DaxiliUnvanXetasi):
        sebeke.yoxla("http://127.0.0.1/")


# ---------- yönləndirmə ----------


def test_yonlendirme_de_yoxlanilir(monkeypatch):
    """Açıq ünvan daxili ünvana yönləndirə bilər — hər addım yoxlanmalıdır."""
    monkeypatch.setattr(sebeke, "_ipler", lambda host: ["93.184.216.34"])

    def cavabla(sorgu: httpx.Request) -> httpx.Response:
        if sorgu.url.host == "acik.example":
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/"})
        return httpx.Response(200, text="daxili sirr")

    async def sinaq():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(cavabla),
            follow_redirects=True,
            event_hooks=sebeke.HOOKLAR,
        ) as musteri:
            return await musteri.get("http://acik.example/")

    with pytest.raises(sebeke.DaxiliUnvanXetasi):
        asyncio.run(sinaq())


def test_acik_yonlendirme_kecir(monkeypatch):
    monkeypatch.setattr(sebeke, "_ipler", lambda host: ["93.184.216.34"])

    def cavabla(sorgu: httpx.Request) -> httpx.Response:
        if sorgu.url.host == "acik.example":
            return httpx.Response(302, headers={"Location": "http://basqa.example/"})
        return httpx.Response(200, text="salam")

    async def sinaq():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(cavabla),
            follow_redirects=True,
            event_hooks=sebeke.HOOKLAR,
        ) as musteri:
            return await musteri.get("http://acik.example/")

    assert asyncio.run(sinaq()).text == "salam"


# ---------- API sərhədi ----------


def test_api_daxili_unvani_redd_edir():
    cavab = muvekkil.post("/api/analyze", json={"url": "http://169.254.169.254/"})
    assert cavab.status_code == 400
    assert "daxili şəbəkə" in cavab.json()["detail"]


def test_api_localhostu_redd_edir():
    cavab = muvekkil.post("/api/analyze", json={"url": "http://127.0.0.1:8000/"})
    assert cavab.status_code == 400
