"""Sayt gəzişi — RAG üçün səhifə toplama.

Qaydalar:
- `robots.txt`-ə hörmət edilir (icazə verilməyən ünvanlar açılmır)
- əvvəlcə `sitemap.xml` yoxlanılır (varsa, ən dəqiq siyahıdır)
- sitemap yoxdursa daxili linklərlə enliyinə gəziş (BFS)
- eyni anda 4 sorğu, hər sorğu arasında kiçik fasilə — sayta yük salmırıq
- yalnız eyni domen, yalnız HTML səhifələr
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urldefrag, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from . import sebeke
from .config import ayarlar
from .collectors.base import BASLIQLAR, domen, kok_url, mutleq_url
from .collectors.sehife import elaqe_cixart
from .decorators import timed
from .metn import barmaq_izi, cixart

PARALEL = 4
FASILE = 0.25  # saniyə — sorğular arasında
MIN_METN = 150  # bundan qısa səhifələr RAG üçün faydasızdır

FAYL_SONLUQLARI = re.compile(
    r"\.(pdf|jpe?g|png|gif|webp|svg|ico|mp4|mp3|avi|zip|rar|docx?|xlsx?|pptx?|css|js)$",
    re.IGNORECASE,
)

# Analiz üçün mənasız, sonsuz sayda ola bilən ünvanlar
ATILAN_YOLLAR = re.compile(
    r"/(wp-admin|wp-json|admin|login|logout|signin|register|cart|sepet|basket|"
    r"checkout|search|axtaris|feed|rss|tag/|etiket/|page/\d+|sehife/\d+)",
    re.IGNORECASE,
)


def _temiz_url(url: str) -> str:
    """Fraqmenti (#...) və sondakı kəsiyi atır — eyni səhifə iki dəfə yığılmasın.

    Sondakı kəsik həmişə atılır: `site.az/` və `site.az` eyni səhifədir, əks halda
    ana səhifə iki dəfə yığılır (sitemap `/` ilə, başlanğıc ünvan `/`-siz verir).
    """
    url, _ = urldefrag(url)
    if url.endswith("/"):
        url = url[:-1]
    return url


def uygun_url(url: str, kok_domen: str) -> bool:
    if domen(url) != kok_domen:
        return False
    if not url.startswith(("http://", "https://")):
        return False
    if FAYL_SONLUQLARI.search(urlparse(url).path):
        return False
    if ATILAN_YOLLAR.search(url):
        return False
    return True


async def robots_qaydalari(kok: str) -> RobotFileParser:
    oxuyucu = RobotFileParser()
    oxuyucu.set_url(f"{kok}/robots.txt")
    try:
        async with httpx.AsyncClient(
            headers=BASLIQLAR, timeout=8, verify=False, event_hooks=sebeke.HOOKLAR
        ) as m:
            cavab = await m.get(f"{kok}/robots.txt")
        oxuyucu.parse(cavab.text.splitlines() if cavab.status_code == 200 else [])
    except Exception:
        oxuyucu.parse([])  # robots.txt yoxdursa hər şeyə icazə
    return oxuyucu


async def _sitemap_unvanlari(kok: str, kok_domen: str, limit: int) -> list[str]:
    """sitemap.xml (və sitemap indeksi) oxunur."""
    tapilan: list[str] = []
    gozleyen = [f"{kok}/sitemap.xml", f"{kok}/sitemap_index.xml"]
    baxilan: set[str] = set()

    async with httpx.AsyncClient(
        headers=BASLIQLAR, timeout=12, follow_redirects=True, verify=False,
        event_hooks=sebeke.HOOKLAR,
    ) as musteri:
        while gozleyen and len(tapilan) < limit:
            unvan = gozleyen.pop(0)
            if unvan in baxilan:
                continue
            baxilan.add(unvan)
            try:
                cavab = await musteri.get(unvan)
                if cavab.status_code != 200 or "<" not in cavab.text[:200]:
                    continue
                supa = BeautifulSoup(cavab.text, "xml")
            except Exception:
                continue

            # Sitemap indeksi → daxilindəki sitemap-ları da yoxla
            for sm in supa.find_all("sitemap"):
                yer = sm.find("loc")
                if yer and len(baxilan) < 6:
                    gozleyen.append(yer.get_text(strip=True))

            for qeyd in supa.find_all("url"):
                yer = qeyd.find("loc")
                if not yer:
                    continue
                u = _temiz_url(yer.get_text(strip=True))
                if uygun_url(u, kok_domen):
                    tapilan.append(u)
                if len(tapilan) >= limit:
                    break

    # Qısa ünvanlar adətən daha vacib səhifələrdir (ana bölmələr)
    return sorted(dict.fromkeys(tapilan), key=len)[:limit]


async def _sehife_getir(
    musteri: httpx.AsyncClient, url: str, kilid: asyncio.Semaphore
) -> tuple[str, str] | None:
    async with kilid:
        await asyncio.sleep(FASILE)
        try:
            cavab = await musteri.get(url)
        except Exception:
            return None
    if cavab.status_code != 200:
        return None
    if "html" not in cavab.headers.get("content-type", "").lower():
        return None
    return url, cavab.text


@timed
async def gez(
    baslangic_url: str,
    *,
    max_sehife: int | None = None,
    xeber=None,
) -> list[dict]:
    """Saytı gəzir və səhifələri qaytarır.

    `xeber(yigilan, hedef, url)` verilsə hər səhifədən sonra çağırılır.
    """
    max_sehife = max_sehife or ayarlar.max_pages
    kok = kok_url(baslangic_url)
    kok_domen = domen(baslangic_url)

    oxuyucu = await robots_qaydalari(kok)

    def icaze(u: str) -> bool:
        try:
            return oxuyucu.can_fetch(BASLIQLAR["User-Agent"], u)
        except Exception:
            return True

    # 1) Sitemap varsa ondan başlayırıq
    novbe = await _sitemap_unvanlari(kok, kok_domen, max_sehife * 2)
    menbe = "sitemap" if novbe else "linkler"
    if not novbe:
        novbe = [_temiz_url(baslangic_url)]
    elif _temiz_url(baslangic_url) not in novbe:
        novbe.insert(0, _temiz_url(baslangic_url))

    gorulen: set[str] = set()
    gorulen_hash: set[str] = set()  # eyni məzmun fərqli ünvanda təkrarlana bilər
    sehifeler: list[dict] = []
    kilid = asyncio.Semaphore(PARALEL)

    async with httpx.AsyncClient(
        headers=BASLIQLAR, timeout=ayarlar.request_timeout,
        follow_redirects=True, verify=False, event_hooks=sebeke.HOOKLAR,
    ) as musteri:
        while novbe and len(sehifeler) < max_sehife:
            dest = []
            while novbe and len(dest) < PARALEL:
                u = novbe.pop(0)
                if u in gorulen or not uygun_url(u, kok_domen) or not icaze(u):
                    continue
                gorulen.add(u)
                dest.append(u)

            if not dest:
                continue

            neticeler = await asyncio.gather(
                *[_sehife_getir(musteri, u, kilid) for u in dest]
            )

            for netice in neticeler:
                if not netice or len(sehifeler) >= max_sehife:
                    continue
                url, html = netice
                basliq, metn = cixart(html)

                izi = barmaq_izi(metn)
                if len(metn) >= MIN_METN and izi not in gorulen_hash:
                    gorulen_hash.add(izi)
                    sehifeler.append(
                        {
                            "url": url,
                            "basliq": basliq,
                            "metn": metn,
                            "hash": izi,
                            # Sosial link və əlaqə çox vaxt altlıqdadır; `metn`
                            # təmizlənəndə altlıq atılır, ona görə xam HTML-dən
                            # elə burada çıxarırıq.
                            "elaqe": elaqe_cixart(url, html),
                        }
                    )
                    if xeber:
                        xeber(len(sehifeler), max_sehife, url)

                # Sitemap yoxdursa yeni linkləri növbəyə əlavə et
                if menbe == "linkler" and len(sehifeler) + len(novbe) < max_sehife * 3:
                    supa = BeautifulSoup(html, "lxml")
                    for a in supa.find_all("a", href=True):
                        yeni = _temiz_url(mutleq_url(url, a["href"]))
                        if yeni not in gorulen and uygun_url(yeni, kok_domen):
                            novbe.append(yeni)

    return sehifeler
