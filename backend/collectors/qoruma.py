"""Bot qorumasının aşkarlanması.

Cloudflare və bənzər xidmətlər bota real səhifə əvəzinə "yoxlama" səhifəsi verir.
Bunu tanımasaq, analiz **yalan** nəticə verər (boş məzmun, yanlış texnologiya).
Ona görə əvvəlcə yoxlayırıq və dürüst bildiririk.
"""

from __future__ import annotations

import re

IMZALAR: list[tuple[str, str]] = [
    ("Cloudflare", r"just a moment|cf-browser-verification|cdn-cgi/challenge-platform|_cf_chl_opt"),
    ("Cloudflare Turnstile", r"challenges\.cloudflare\.com/turnstile"),
    ("DDoS-Guard", r"ddos-guard"),
    ("Sucuri", r"sucuri_cloudproxy|cloudproxy"),
    ("Imperva/Incapsula", r"_Incapsula_Resource|incapsula"),
    ("PerimeterX", r"perimeterx|px-captcha"),
    ("Akamai Bot Manager", r"_abck|akam/\d+/"),
    ("reCAPTCHA divarı", r"g-recaptcha.*(verify|robot)"),
]

# Yoxlama səhifələri kiçik olur — real səhifə bundan böyükdür
KICIK_HEDD_KB = 25


def yoxla(html: str, status_kodu: int = 200) -> dict:
    kicik = html.lower()
    olcu_kb = len(html.encode("utf-8")) / 1024

    tapilan = ""
    for ad, naxis in IMZALAR:
        if re.search(naxis, kicik, re.IGNORECASE):
            tapilan = ad
            break

    bloklanib = bool(tapilan) or status_kodu in (403, 429, 503)

    return {
        "qorunur": bloklanib,
        "xidmet": tapilan,
        "status_kodu": status_kodu,
        "olcu_kb": round(olcu_kb, 1),
        "supheli_kicik": olcu_kb < KICIK_HEDD_KB,
        "qeyd": (
            f"Sayt {tapilan or 'bot qoruması'} arxasındadır — bizə real məzmun əvəzinə "
            "yoxlama səhifəsi verildi. Məzmun analizi və RAG bu sayt üçün etibarsızdır."
            if bloklanib
            else ""
        ),
    }
