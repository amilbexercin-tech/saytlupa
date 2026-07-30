"""Layihədə istifadə olunan dekoratorlar.

Hamısı həm adi, həm də async funksiyalarla işləyir.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import inspect
import logging
import time
from typing import Any, Callable

from . import cache

log = logging.getLogger("saytlupa")


def _tam_ad(func: Callable) -> str:
    """Modul + funksiya adı.

    Yalnız `func.__name__` kifayət etmir: bütün toplayıcılarda funksiya `topla`
    adlanır və açarlar toqquşub bir-birinin nəticəsini qaytarır.
    """
    return f"{func.__module__}.{func.__qualname__}"


def _acar(ad: str, args: tuple, kwargs: dict) -> str:
    xam = f"{ad}|{args}|{sorted(kwargs.items())}"
    return f"kes:{ad}:{hashlib.sha256(xam.encode()).hexdigest()[:16]}"


def cached(saniye: int = 3600):
    """Nəticəni Redis-də (və ya yaddaşda) saxlayır."""

    def sarğı(func: Callable) -> Callable:
        ad = _tam_ad(func)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_icra(*args, **kwargs):
                acar = _acar(ad, args, kwargs)
                hazir = cache.oxu(acar)
                if hazir is not None:
                    log.debug("keşdən: %s", ad)
                    return hazir
                netice = await func(*args, **kwargs)
                cache.yaz(acar, netice, saniye)
                return netice

            return async_icra

        @functools.wraps(func)
        def icra(*args, **kwargs):
            acar = _acar(ad, args, kwargs)
            hazir = cache.oxu(acar)
            if hazir is not None:
                return hazir
            netice = func(*args, **kwargs)
            cache.yaz(acar, netice, saniye)
            return netice

        return icra

    return sarğı


def retry(cehd: int = 3, gozleme: float = 1.0, artim: float = 2.0):
    """Xəta olsa təkrar cəhd edir — hər dəfə gözləmə müddəti artır."""

    def sarğı(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_icra(*args, **kwargs):
                gecikme = gozleme
                son_xeta: Exception | None = None
                for nomre in range(1, cehd + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as xeta:
                        son_xeta = xeta
                        if nomre < cehd:
                            log.warning(
                                "%s uğursuz (%s/%s): %s", func.__name__, nomre, cehd, xeta
                            )
                            await asyncio.sleep(gecikme)
                            gecikme *= artim
                raise son_xeta  # type: ignore[misc]

            return async_icra

        @functools.wraps(func)
        def icra(*args, **kwargs):
            gecikme = gozleme
            son_xeta: Exception | None = None
            for nomre in range(1, cehd + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as xeta:
                    son_xeta = xeta
                    if nomre < cehd:
                        time.sleep(gecikme)
                        gecikme *= artim
            raise son_xeta  # type: ignore[misc]

        return icra

    return sarğı


def timed(func: Callable) -> Callable:
    """Funksiyanın neçə saniyə çəkdiyini loglayır."""

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_icra(*args, **kwargs):
            basla = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                log.info("%s — %.2f san", func.__name__, time.perf_counter() - basla)

        return async_icra

    @functools.wraps(func)
    def icra(*args, **kwargs):
        basla = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            log.info("%s — %.2f san", func.__name__, time.perf_counter() - basla)

    return icra


def safe_collector(ad: str):
    """Bir toplayıcı sınsa bütün analiz dayanmasın — xəta nəticəyə yazılır."""

    def sarğı(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_icra(*args, **kwargs) -> dict[str, Any]:
                try:
                    return {"ad": ad, "ugurlu": True, "data": await func(*args, **kwargs)}
                except Exception as xeta:
                    log.warning("collector '%s' sındı: %s", ad, xeta)
                    return {"ad": ad, "ugurlu": False, "xeta": str(xeta), "data": {}}

            return async_icra

        @functools.wraps(func)
        def icra(*args, **kwargs) -> dict[str, Any]:
            try:
                return {"ad": ad, "ugurlu": True, "data": func(*args, **kwargs)}
            except Exception as xeta:
                log.warning("collector '%s' sındı: %s", ad, xeta)
                return {"ad": ad, "ugurlu": False, "xeta": str(xeta), "data": {}}

        return icra

    return sarğı
