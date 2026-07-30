"""Redis keşi — Redis olmasa yaddaşdaxili lüğətə keçir (layihə çökmür)."""

from __future__ import annotations

import json
import time
from typing import Any

from .config import ayarlar

_yaddas: dict[str, tuple[float, Any]] = {}
_redis = None
REDIS_VAR = False

if ayarlar.redis_url:
    try:
        import redis as _redis_kitabxana

        _redis = _redis_kitabxana.from_url(ayarlar.redis_url, decode_responses=True)
        _redis.ping()
        REDIS_VAR = True
    except Exception:
        _redis = None
        REDIS_VAR = False


def yaz(acar: str, deyer: Any, saniye: int = 3600) -> None:
    if REDIS_VAR:
        try:
            _redis.setex(acar, saniye, json.dumps(deyer, ensure_ascii=False))
            return
        except Exception:
            pass
    _yaddas[acar] = (time.time() + saniye, deyer)


def oxu(acar: str) -> Any | None:
    if REDIS_VAR:
        try:
            xam = _redis.get(acar)
            return json.loads(xam) if xam else None
        except Exception:
            pass
    qeyd = _yaddas.get(acar)
    if not qeyd:
        return None
    bitme, deyer = qeyd
    if time.time() > bitme:
        _yaddas.pop(acar, None)
        return None
    return deyer


def sil(acar: str) -> None:
    if REDIS_VAR:
        try:
            _redis.delete(acar)
        except Exception:
            pass
    _yaddas.pop(acar, None)


def veziyyet() -> dict:
    return {"kes": "redis" if REDIS_VAR else "yaddas", "aktiv": True}
