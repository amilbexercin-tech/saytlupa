"""Giriş qapısı — API açarı və gündəlik sual limiti.

Serverdə iki fərqli istifadəçi var:

- **sahib** — analiz başladır, təhvil düymələrini işlədir, izləmə qurur. Bunların
  hamısı Anthropic/Gemini çağırışıdır, yəni birbaşa **pul xərcləyir**;
- **ziyarətçi** — hazır analizlərə baxır və saytla söhbət edir.

Ona görə **yazan** əməliyyatlar açar tələb edir, **oxuyanlar** açıq qalır.
Söhbət ortadadır: bağlansa nümayişin ən güclü hissəsi itir, tamamilə açıq
qalsa xərc sərhədsizdir — həll IP başına gündəlik limitdir.

`API_ACAR` boş olsa **heç bir məhdudiyyət yoxdur**. Bu, qəsdəndir: lokal
inkişafda və testlərdə hər şey əvvəlki kimi işləməlidir. Yəni qoruma yalnız
serverdə, açar yazılandan sonra qüvvəyə minir.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from . import cache
from .config import ayarlar

BASLIQ = "X-API-Acar"


def teleb_olunur() -> bool:
    """Serverdə açar qoyulubmu?"""
    return bool(ayarlar.api_acar)


def acar_duzgundur(sorgu: Request) -> bool:
    """Sorğuda düzgün açar var? (`secrets.compare_digest` — vaxt hücumuna qarşı)"""
    verilen = sorgu.headers.get(BASLIQ, "")
    return bool(verilen) and secrets.compare_digest(verilen, ayarlar.api_acar)


def acar_teleb(sorgu: Request) -> None:
    """Yazan endpoint-lər üçün asılılıq: `dependencies=[Depends(qapi.acar_teleb)]`."""
    if not teleb_olunur() or acar_duzgundur(sorgu):
        return
    raise HTTPException(
        401,
        f"Bu əməliyyat üçün API açarı lazımdır — «{BASLIQ}» başlığında göndər. "
        "Səbəb: analiz və təhvil düymələri pullu model çağırışıdır.",
    )


# --------------------------------------------------------------- sual limiti


def _ip(sorgu: Request) -> str:
    """Ziyarətçinin IP-si.

    Caddy arxasında `sorgu.client.host` həmişə Caddy-nin özüdür. Caddy
    `X-Forwarded-For`-un **sonuna** gördüyü peer-in IP-sini əlavə edir, ona görə
    **sonuncu** element götürülür — müştəri başlığın əvvəlinə saxta IP yazsa da
    sonuncunu dəyişə bilmir.
    """
    xam = sorgu.headers.get("X-Forwarded-For", "")
    if xam:
        return xam.split(",")[-1].strip()
    return sorgu.client.host if sorgu.client else "namelum"


def _gunun_acari(ip: str) -> str:
    gun = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"limit:sual:{ip}:{gun}"


def sual_sayi(ip: str) -> int:
    return int(cache.oxu(_gunun_acari(ip)) or 0)


def sual_limiti(sorgu: Request) -> None:
    """Söhbət üçün asılılıq — IP başına gündəlik limit.

    Açar yoxdursa (lokal) və ya düzgün açar verilibsə (sahib) limit tətbiq
    olunmur. Sayğac keşdədir: Redis varsa orada, yoxsa yaddaşda — server yenidən
    qalxanda sıfırlanır, bu, nümayiş üçün qəbul ediləndir.
    """
    if not teleb_olunur() or acar_duzgundur(sorgu):
        return

    ip = _ip(sorgu)
    sayi = sual_sayi(ip)
    if sayi >= ayarlar.gunluk_sual_limiti:
        raise HTTPException(
            429,
            f"Gündəlik sual limiti doldu ({ayarlar.gunluk_sual_limiti} sual). "
            "Limit hər gün sıfırlanır — sabah yenidən soruşa bilərsən. "
            "Səbəb: hər cavab pullu model çağırışıdır.",
        )
    cache.yaz(_gunun_acari(ip), sayi + 1, saniye=24 * 3600)
