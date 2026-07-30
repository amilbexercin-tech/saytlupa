"""Brauzerdə çəkilən (client-side) saytların aşkarlanması.

React/Vue/Angular saytlarında serverin verdiyi HTML boş qabıqdır — məzmunu
brauzer çəkir. Crawler belə səhifəni haqlı olaraq atır (mətn yoxdur), amma
istifadəçi "proqram tapmadı, yoxsa sayt belədir?" sualı ilə qalmamalıdır.

`qoruma.py` ilə eyni məntiq; fərq odur ki, burada sayt bizi bloklamır —
sadəcə məzmununu serverdə vermir.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Crawler `MIN_METN = 150`-dən qısa səhifəni RAG-a salmır — eyni hədd
HEDD_METN = 150

# Boş qabığın "məzmun bura çəkiləcək" düyünü
BAGLAMA_NOQTELERI = re.compile(
    r'id="(root|app|__next|__nuxt)"|data-reactroot|<app-root', re.IGNORECASE
)

# Yalnız birmənalı işarələr adlandırılır — qalanı üçün çərçivə adı uydurulmur
CERCEVELER: list[tuple[str, str]] = [
    ("Next.js", r'id="__next"|__NEXT_DATA__'),
    ("Nuxt", r'id="__nuxt"|__NUXT__'),
    ("Angular", r"ng-version|<app-root"),
    ("React", r"data-reactroot"),
]


def _netice(qabiq: bool, cerceve: str, gorunen: int) -> dict:
    return {
        "js_ile_qurulur": qabiq,
        "cerceve": cerceve,
        "gorunen_metn": gorunen,
        "qeyd": (
            f"Sayt {cerceve + ' ilə ' if cerceve else ''}brauzerdə çəkilir — serverin "
            f"verdiyi HTML-də cəmi {gorunen} simvol mətn var. Məzmun, sosial linklər "
            "və RAG indeksi bu sayt üçün toplana bilmədi. Bu, saytın nasazlığı deyil."
            if qabiq
            else ""
        ),
    }


def yoxla(html: str) -> dict:
    if not html:
        return _netice(False, "", 0)

    supa = BeautifulSoup(html, "lxml")
    for teq in supa(["script", "style", "noscript", "template"]):
        teq.decompose()
    # Yalnız gövdə: `<title>` başlıqdır, səhifənin görünən mətni deyil
    govde = supa.body or supa
    gorunen = len(" ".join(govde.get_text(" ").split()))

    qabiq = bool(BAGLAMA_NOQTELERI.search(html)) and gorunen < HEDD_METN

    cerceve = ""
    if qabiq:
        for ad, naxis in CERCEVELER:
            if re.search(naxis, html, re.IGNORECASE):
                cerceve = ad
                break

    return _netice(qabiq, cerceve, gorunen)
