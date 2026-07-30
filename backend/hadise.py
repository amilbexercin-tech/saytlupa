"""Canlı gedişat üçün sadə hadisə brokeri.

Analiz fonda işləyir, brauzer isə SSE ilə qulaq asır. Hər analiz üçün bir növbə
saxlanılır; analiz bitəndə növbə bağlanır.
"""

from __future__ import annotations

import asyncio
from typing import Any

BITDI = {"nov": "son"}

_novbeler: dict[int, asyncio.Queue] = {}


def novbe(analiz_id: int) -> asyncio.Queue:
    """Həmin analiz üçün növbəni qaytarır (yoxdursa yaradır)."""
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
    gonder(analiz_id, "son")


def temizle(analiz_id: int) -> None:
    _novbeler.pop(analiz_id, None)


def aktivdir(analiz_id: int) -> bool:
    return analiz_id in _novbeler
