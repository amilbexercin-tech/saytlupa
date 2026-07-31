"""Şəbəkə təhlükəsizliyi — daxili ünvanlara sorğu getməsin (SSRF qoruması).

Server istənilən ünvanı analiz edir, deməli ünvanı yazan tərəf serverin **öz**
şəbəkəsini də göstərə bilər:

- `http://localhost:8000` — SaytLupa-nın özü;
- `http://10.0.0.5` — eyni şəbəkədəki başqa xidmət;
- `http://169.254.169.254/metadata/v1/` — bulud provayderinin metadata xidməti.

Sonuncusu DigitalOcean-da user-data və SSH açarlarını qaytarır. Gəzilən mətn
bazaya yazılır, RAG-a indekslənir və **söhbətdən oxunur** — yəni bir dəfəlik
analiz həmin məlumatı hər ziyarətçiyə açır. Ona görə ünvan sorğudan əvvəl
yoxlanılır.

Yönləndirmə də yoxlanılır: hər yerdə `follow_redirects=True` işlədirik, yəni
açıq ünvan daxili ünvana yönləndirə bilər. `HOOKLAR` httpx-in **hər** sorğusunda
işə düşür — yönləndirmə addımları daxil.

Qalan risk: DNS yenidən bağlama (rebinding). Ad yoxlama anında açıq IP, qoşulma
anında daxili IP qaytara bilər. Bunun qarşısını almaq üçün həll edilmiş IP-yə
qoşulmaq lazımdır; hazırda edilmir və bu, şüurlu seçimdir.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx


class DaxiliUnvanXetasi(Exception):
    """Sorğu qapalı şəbəkə ünvanına gedirdi — dayandırıldı."""


def _qapalidir(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """IP internetdən əlçatan deyilmi?

    Ölçü kimi `is_global` seçilib, `is_private` yox: Python-da `100.64.0.0/10`
    (operator NAT-ı) `is_private` üçün **False** qaytarır, amma internetdən
    marşrutlanmır — 2026-07-31-də yoxlanıldı. `is_global` onu da tutur, üstəlik
    10/8, 127/8, 169.254/16 (bulud metadata ünvanı) və IPv6 qarşılıqlarını.

    `is_reserved` ayrıca lazımdır: `64:ff9b::7f00:1` kimi NAT64 ünvanı daxildə
    127.0.0.1-ə düşür, amma `is_global` onu açıq sayır.
    """
    return (
        not ip.is_global
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _ipler(host: str) -> list[str]:
    """Hostun bütün IP ünvanları (A + AAAA). Ad həll olunmasa boş siyahı."""
    try:
        return sorted({q[4][0] for q in socket.getaddrinfo(host, None)})
    except socket.gaierror:
        return []


def host_sebebi(host: str) -> str:
    """Host qapalı şəbəkəyə işarə edirsə səbəb, əks halda boş sətir.

    Ad ümumiyyətlə həll olunmursa boş qaytarılır: sorğu onsuz da alınmayacaq və
    "daxili ünvan" demək yanlış olardı.
    """
    if not host:
        return "Ünvanda host adı yoxdur."

    try:  # host özü IP-dirsə DNS-ə ehtiyac yoxdur
        xam_ipler = [str(ipaddress.ip_address(host))]
    except ValueError:
        xam_ipler = _ipler(host)

    for xam in xam_ipler:
        try:
            ip = ipaddress.ip_address(xam)
        except ValueError:
            continue
        if _qapalidir(ip):
            return (
                f"«{host}» daxili şəbəkə ünvanına işarə edir ({xam}) — "
                "server öz şəbəkəsini analiz edə bilməz."
            )
    return ""


def unvan_sebebi(url: str) -> str:
    """Ünvan qəbul edilə bilməzsə səbəb, əks halda boş sətir."""
    bolgu = urlparse(url)
    if bolgu.scheme not in ("http", "https"):
        return f"Yalnız http/https ünvanları qəbul edilir, «{bolgu.scheme}» yox."
    return host_sebebi(bolgu.hostname or "")


def yoxla(url: str) -> None:
    """Ünvan qapalıdırsa `DaxiliUnvanXetasi` qaldırır."""
    sebeb = unvan_sebebi(url)
    if sebeb:
        raise DaxiliUnvanXetasi(sebeb)


async def _sorgunu_yoxla(sorgu: httpx.Request) -> None:
    yoxla(str(sorgu.url))


# httpx müştərilərinə verilir: `httpx.AsyncClient(..., event_hooks=HOOKLAR)`.
# Hook `_send_handling_redirects` içində, hər addımdan əvvəl çağırılır.
HOOKLAR: dict[str, list] = {"request": [_sorgunu_yoxla]}
