"""Toplayıcılar üçün ortaq köməkçilər."""

from __future__ import annotations

import socket
from urllib.parse import urljoin, urlparse

import httpx
import tldextract

from .. import sebeke
from ..config import ayarlar

# HTTP başlıqları yalnız ASCII qəbul edir — burada Azərbaycan hərfi olmamalıdır.
BASLIQLAR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
        "SaytLupa/0.1 (+site analysis tool)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "az,en;q=0.8,ru;q=0.6",
}


def domen(url: str) -> str:
    """https://www.magaza.az/kataloq → magaza.az"""
    parca = tldextract.extract(url)
    return ".".join(p for p in (parca.domain, parca.suffix) if p)


def tam_host(url: str) -> str:
    """https://www.magaza.az/kataloq → www.magaza.az"""
    return urlparse(url).hostname or ""


def kok_url(url: str) -> str:
    bolgu = urlparse(url)
    return f"{bolgu.scheme}://{bolgu.netloc}"


def mutleq_url(esas: str, link: str) -> str:
    return urljoin(esas, link)


def ip_tap(host: str) -> str:
    return socket.gethostbyname(host)


async def getir(
    url: str, *, metod: str = "GET", timeout: int | None = None
) -> httpx.Response:
    """Səhifəni gətirir (yönləndirmələri izləyir)."""
    async with httpx.AsyncClient(
        headers=BASLIQLAR,
        timeout=timeout or ayarlar.request_timeout,
        follow_redirects=True,
        verify=False,
        event_hooks=sebeke.HOOKLAR,
    ) as musteri:
        return await musteri.request(metod, url)
