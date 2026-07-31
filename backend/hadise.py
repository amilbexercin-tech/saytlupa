"""Canlı gedişat üçün sadə hadisə brokeri.

Analiz fonda işləyir, brauzer isə SSE ilə qulaq asır. Hər analiz üçün bir növbə
saxlanılır.

**Növbə nə vaxt silinir?** Əvvəllər yalnız SSE bağlananda silinirdi, amma
növbəni analizin özü yaradır (`analiz.basla`). Brauzersiz başlayan analizlər
(MCP aləti, n8n cron, `curl`) heç vaxt SSE açmır — onların növbəsi əbədi qalırdı
və hərəsi 500 hadisəyə qədər yaddaş tuturdu. Üstəlik brauzer analizin ortasında
bağlansa, `temizle()` işləyir, sonrakı `gonder()` isə **yeni** növbə yaradırdı və
o da qalırdı.

İndi analiz bitəndə (`bitir`) vaxt damğası qoyulur və `SAXLAMA` müddətindən sonra
növbə süpürülür. Müddət ona görə lazımdır ki, SSE hələ oxumamış hadisələri itməsin:
brauzer "son" hadisəsini alana qədər növbə yerində qalmalıdır.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

# Analiz bitəndən sonra növbə bu qədər saniyə saxlanılır — SSE sonuncu
# hadisələri oxuya bilsin deyə.
SAXLAMA = 300

_novbeler: dict[int, asyncio.Queue] = {}
_bitme: dict[int, float] = {}  # analiz_id → bitmə anı (monotonic saniyə)


def _supur() -> None:
    """Bitmiş və saxlama müddəti keçmiş növbələri atır."""
    indi = time.monotonic()
    for analiz_id, vaxt in list(_bitme.items()):
        if indi - vaxt > SAXLAMA:
            _novbeler.pop(analiz_id, None)
            _bitme.pop(analiz_id, None)


def novbe(analiz_id: int) -> asyncio.Queue:
    """Həmin analiz üçün növbəni qaytarır (yoxdursa yaradır)."""
    _supur()
    if analiz_id not in _novbeler:
        _novbeler[analiz_id] = asyncio.Queue(maxsize=500)
    return _novbeler[analiz_id]


def gonder(analiz_id: int, nov: str, **melumat: Any) -> None:
    """Hadisəni növbəyə qoyur. Növbə dolubsa hadisə atılır — analiz dayanmır."""
    try:
        novbe(analiz_id).put_nowait({"nov": nov, **melumat})
    except asyncio.QueueFull:
        pass


def bitir(analiz_id: int) -> None:
    """Analizin bitdiyini bildirir və növbəni süpürülməyə işarələyir."""
    gonder(analiz_id, "son")
    _bitme[analiz_id] = time.monotonic()


def temizle(analiz_id: int) -> None:
    _novbeler.pop(analiz_id, None)
    _bitme.pop(analiz_id, None)


def aktivdir(analiz_id: int) -> bool:
    return analiz_id in _novbeler
