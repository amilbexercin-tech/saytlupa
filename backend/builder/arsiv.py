"""📦 Səhifə arşivi — ana səhifənin HTML + CSS + şəkilləri lokal qovluğa.

Qaydalar (etik və texniki):
- `robots.txt` icazə vermirsə arşiv qurulmur
- xarici skriptlər saxlanılmır — arşiv açılanda heç bir izləyiciyə sorğu getmir
- ölçü və say limitləri var, sayta yük salınmır (paralel 4, fasilə ilə)
- nə yığıldığı `QEYD.md`-də açıq yazılır

Bu, saytın "oğurlanması" deyil: brauzerin "Save page as" funksiyasının
proqramla edilmiş, məhdudlaşdırılmış və sənədləşdirilmiş variantıdır.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from .. import sebeke
from ..collectors.base import BASLIQLAR, kok_url, mutleq_url
from ..config import STORAGE
from ..crawler import robots_qaydalari
from . import kontekst

log = logging.getLogger("saytlupa")

PARALEL = 4
FASILE = 0.2          # saniyə — sorğular arasında
MAX_FAYL = 60         # ən çoxu neçə resurs yüklənsin
MAX_FAYL_MB = 3       # bir faylın yuxarı həddi
MAX_UMUMI_MB = 25     # bütün arşivin yuxarı həddi
CSS_RESURS_LIMITI = 20  # CSS içindən çıxarılan əlavə şəkillərin sayı

ASSET_QOVLUQ = "assets"
CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")
TEHLUKESIZ = re.compile(r"[^a-zA-Z0-9._-]+")

# Hansı etiketin hansı atributu resursa işarə edir
HEDEFLER = (
    ("link", "href", {"rel": "stylesheet"}),
    ("link", "href", {"rel": "icon"}),
    ("img", "src", {}),
    ("source", "src", {}),
)


def yerli_ad(url: str, sira: int) -> str:
    """Resurs ünvanından təkrarlanmayan, təhlükəsiz fayl adı."""
    yol = unquote(urlparse(url).path)
    ad = TEHLUKESIZ.sub("_", Path(yol).name).strip("._-") or "resurs"
    if len(ad) > 60:
        kok, nokte, sonluq = ad.rpartition(".")
        ad = f"{kok[:50]}.{sonluq}" if nokte else ad[:60]
    return f"{sira:02d}_{ad}"


def _resurs_unvanlari(supa: BeautifulSoup, esas: str) -> list[tuple]:
    """(etiket, atribut, mütləq ünvan) siyahısı."""
    tapilanlar: list[tuple] = []
    for ad, atribut, suzgec in HEDEFLER:
        for etiket in supa.find_all(ad, attrs=suzgec):
            deyer = (etiket.get(atribut) or "").strip()
            # `data-src` — lazy loading işlədən saytlarda əsl ünvan orada olur
            if not deyer and etiket.get("data-src"):
                deyer = etiket["data-src"].strip()
            if not deyer or deyer.startswith("data:"):
                continue
            tam = mutleq_url(esas, deyer)
            if tam.startswith(("http://", "https://")):
                tapilanlar.append((etiket, atribut, tam))
    return tapilanlar


async def _yukle(
    musteri: httpx.AsyncClient, url: str, kilid: asyncio.Semaphore
) -> bytes | None:
    async with kilid:
        await asyncio.sleep(FASILE)
        try:
            cavab = await musteri.get(url)
        except Exception as xeta:
            log.debug("arşiv: %s alınmadı (%s)", url, xeta)
            return None
    if cavab.status_code != 200:
        return None
    if len(cavab.content) > MAX_FAYL_MB * 1024 * 1024:
        return None
    return cavab.content


async def _hamisini_yukle(
    musteri: httpx.AsyncClient, unvanlar: list[str], kilid: asyncio.Semaphore
) -> dict[str, bytes]:
    """Ünvanları paralel yükləyir, limitə çatanda dayanır."""
    tek = list(dict.fromkeys(unvanlar))[:MAX_FAYL]
    neticeler = await asyncio.gather(*[_yukle(musteri, u, kilid) for u in tek])

    yigilan: dict[str, bytes] = {}
    umumi = 0
    for unvan, mezmun in zip(tek, neticeler):
        if not mezmun:
            continue
        if umumi + len(mezmun) > MAX_UMUMI_MB * 1024 * 1024:
            log.info("arşiv: ümumi ölçü həddinə çatdı, qalanı atlanır")
            break
        yigilan[unvan] = mezmun
        umumi += len(mezmun)
    return yigilan


def _css_resurslari(css_metni: str, css_unvani: str) -> list[str]:
    """CSS içindəki `url(...)` şəkillərinin mütləq ünvanları."""
    tapilanlar = []
    for xam in CSS_URL.findall(css_metni):
        if xam.startswith(("data:", "#")):
            continue
        tam = mutleq_url(css_unvani, xam.strip())
        if tam.startswith(("http://", "https://")):
            tapilanlar.append(tam)
    return tapilanlar[:CSS_RESURS_LIMITI]


def _qeyd_metni(url: str, fayllar: list[str], atlanan: int, skript: int) -> str:
    tarix = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    siyahi = "\n".join(f"- `{f}`" for f in sorted(fayllar))
    return (
        f"# Arşiv — {url}\n\n"
        f"SaytLupa ilə yığılıb: {tarix}\n\n"
        "## Nə var\n\n"
        f"- `index.html` — ana səhifənin HTML-i (resurs linkləri lokala yönləndirilib)\n"
        f"- `{ASSET_QOVLUQ}/` — {len(fayllar)} fayl (CSS, şəkil, ikon)\n\n"
        "## Nə yoxdur və niyə\n\n"
        f"- **Xarici skriptlər silinib** ({skript} ədəd) — arşiv açılanda heç bir\n"
        "  analitika/izləyici xidmətinə sorğu getməsin deyə.\n"
        f"- Limitə görə yığılmayan resurs: {atlanan}\n"
        f"  (limitlər: fayl başına {MAX_FAYL_MB} MB, ümumi {MAX_UMUMI_MB} MB, "
        f"ən çoxu {MAX_FAYL} fayl)\n"
        "- Yalnız ana səhifə arşivlənir, bütün sayt yox.\n\n"
        "## Yığılan fayllar\n\n"
        f"{siyahi}\n\n"
        "## Etik qeyd\n\n"
        "Bu arşiv **öyrənmə və analiz üçündür**. `robots.txt` yoxlanılıb və icazə\n"
        "verilib. Məzmun başqasına aiddir — olduğu kimi yayımlamaq müəllif\n"
        "hüququnun pozulmasıdır.\n"
    )


async def arsivle(analiz_id: int) -> dict:
    """Ana səhifəni arşivləyir və ZIP qaytarır."""
    k = kontekst.konteks(analiz_id)
    if k is None:
        return {"ugurlu": False, "tapilmadi": True, "sebeb": "Belə analiz yoxdur"}

    url = k["url"]

    qaydalar = await robots_qaydalari(kok_url(url))
    try:
        icaze = qaydalar.can_fetch(BASLIQLAR["User-Agent"], url)
    except Exception:
        icaze = True
    if not icaze:
        return {
            "ugurlu": False,
            "sebeb": "Saytın robots.txt faylı bu səhifənin yığılmasına icazə vermir.",
        }

    kilid = asyncio.Semaphore(PARALEL)
    async with httpx.AsyncClient(
        headers=BASLIQLAR, timeout=20, follow_redirects=True, verify=False,
        event_hooks=sebeke.HOOKLAR,
    ) as musteri:
        try:
            cavab = await musteri.get(url)
        except Exception as xeta:
            return {"ugurlu": False, "sebeb": f"Səhifə açılmadı: {xeta}"}
        if cavab.status_code != 200:
            return {"ugurlu": False, "sebeb": f"Səhifə {cavab.status_code} qaytardı"}

        supa = BeautifulSoup(cavab.text, "lxml")
        hedefler = _resurs_unvanlari(supa, url)
        yigilan = await _hamisini_yukle(
            musteri, [u for _, _, u in hedefler], kilid
        )

        # CSS fayllarının içindəki şəkillər (bir səviyyə dərinlik)
        css_resurslari: list[str] = []
        for unvan, mezmun in list(yigilan.items()):
            if unvan.lower().split("?")[0].endswith(".css"):
                css_resurslari += _css_resurslari(
                    mezmun.decode("utf-8", "ignore"), unvan
                )
        if css_resurslari:
            elave = await _hamisini_yukle(
                musteri, [u for u in css_resurslari if u not in yigilan], kilid
            )
            yigilan.update(elave)

    # --- fayl sisteminə yazılış ---
    kok = kontekst.qovluq("arsiv", k["domain"])
    if kok.exists():
        shutil.rmtree(kok)  # köhnə arşivin qalıqları yeni ilə qarışmasın
    (kok / ASSET_QOVLUQ).mkdir(parents=True, exist_ok=True)

    xerite: dict[str, str] = {}
    for sira, (unvan, mezmun) in enumerate(yigilan.items(), start=1):
        ad = yerli_ad(unvan, sira)
        (kok / ASSET_QOVLUQ / ad).write_bytes(mezmun)
        xerite[unvan] = ad

    # HTML-dəki ünvanları lokala yönləndiririk
    for etiket, atribut, unvan in hedefler:
        if unvan in xerite:
            etiket[atribut] = f"{ASSET_QOVLUQ}/{xerite[unvan]}"
            etiket.attrs.pop("srcset", None)   # brauzer uzaq nüsxəni çəkməsin
            etiket.attrs.pop("data-src", None)

    # CSS içindəki ünvanlar — fayllar eyni qovluqdadır, ad kifayətdir
    for unvan, ad in xerite.items():
        if not ad.lower().endswith(".css"):
            continue
        yol = kok / ASSET_QOVLUQ / ad
        metn = yol.read_text(encoding="utf-8", errors="ignore")
        for xam in CSS_URL.findall(metn):
            tam = mutleq_url(unvan, xam.strip())
            if tam in xerite:
                metn = metn.replace(xam, xerite[tam])
        yol.write_text(metn, encoding="utf-8")

    skript_sayi = 0
    for etiket in supa.find_all("script", src=True):
        etiket.decompose()
        skript_sayi += 1

    (kok / "index.html").write_text(str(supa), encoding="utf-8")
    atlanan = len({u for _, _, u in hedefler}) - len(xerite)
    (kok / "QEYD.md").write_text(
        _qeyd_metni(url, list(xerite.values()), max(atlanan, 0), skript_sayi),
        encoding="utf-8",
    )

    zip_yolu = shutil.make_archive(
        str(STORAGE / "archives" / kontekst.temiz_ad(k["domain"])), "zip", str(kok)
    )
    olcu_kb = round(Path(zip_yolu).stat().st_size / 1024, 1)
    log.info("Arşiv hazırdır: %s (%s fayl, %s KB)", kok, len(xerite), olcu_kb)

    return {
        "ugurlu": True,
        "qovluq": str(kok),
        "zip": zip_yolu,
        "fayl_sayi": len(xerite) + 2,  # + index.html + QEYD.md
        "atlanan": max(atlanan, 0),
        "silinen_skript": skript_sayi,
        "olcu_kb": olcu_kb,
        "yukle_url": f"/api/analyze/{analiz_id}/yukle/arsiv",
    }
