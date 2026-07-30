"""Reklam və analitika alətlərinin aşkarlanması."""

from __future__ import annotations

import re

from ..decorators import safe_collector, timed

# (ad, kateqoriya, naxış)
ALETLER: list[tuple[str, str, str]] = [
    ("Google Analytics 4", "Analitika", r"gtag\('config',\s*'G-|googletagmanager\.com/gtag/js\?id=G-"),
    ("Google Analytics (UA)", "Analitika", r"UA-\d{4,}-\d+|google-analytics\.com/analytics\.js"),
    ("Google Tag Manager", "Teq meneceri", r"googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]+"),
    ("Google Ads", "Reklam", r"googleadservices\.com|googlesyndication\.com|AW-\d+"),
    ("Meta Pixel", "Reklam", r"connect\.facebook\.net/.*/fbevents\.js|fbq\('init'"),
    ("TikTok Pixel", "Reklam", r"analytics\.tiktok\.com"),
    ("Yandex Metrica", "Analitika", r"mc\.yandex\.ru/metrika"),
    ("Hotjar", "İstifadəçi davranışı", r"static\.hotjar\.com|hjid"),
    ("Microsoft Clarity", "İstifadəçi davranışı", r"clarity\.ms"),
    ("Mixpanel", "Analitika", r"cdn\.mxpnl\.com|mixpanel"),
    ("Amplitude", "Analitika", r"amplitude\.com|cdn\.amplitude"),
    ("Segment", "Analitika", r"cdn\.segment\.com"),
    ("Plausible", "Analitika", r"plausible\.io/js"),
    ("Matomo", "Analitika", r"matomo\.js|piwik\.js"),
    ("LinkedIn Insight", "Reklam", r"snap\.licdn\.com"),
    ("Pinterest Tag", "Reklam", r"s\.pinimg\.com/ct"),
    ("Intercom", "Söhbət", r"widget\.intercom\.io"),
    ("Tawk.to", "Söhbət", r"embed\.tawk\.to"),
    ("Crisp", "Söhbət", r"client\.crisp\.chat"),
    ("Jivo", "Söhbət", r"code\.jivo(site)?\.com"),
    ("Zendesk", "Dəstək", r"static\.zdassets\.com"),
    ("Hubspot", "CRM", r"js\.hs-scripts\.com"),
    ("reCAPTCHA", "Təhlükəsizlik", r"google\.com/recaptcha"),
    ("Cloudflare Insights", "Analitika", r"static\.cloudflareinsights\.com"),
]


@safe_collector("reklam")
@timed
async def topla(url: str, html: str, basliqlar: dict) -> dict:
    tapilanlar: list[dict[str, str]] = []
    for ad, kateqoriya, naxis in ALETLER:
        if re.search(naxis, html, re.IGNORECASE):
            tapilanlar.append({"ad": ad, "kateqoriya": kateqoriya})

    kateqoriyalar: dict[str, list[str]] = {}
    for alet in tapilanlar:
        kateqoriyalar.setdefault(alet["kateqoriya"], []).append(alet["ad"])

    return {
        "aletler": tapilanlar,
        "kateqoriyalar": kateqoriyalar,
        "sayi": len(tapilanlar),
        "analitika_var": "Analitika" in kateqoriyalar,
        "reklam_var": "Reklam" in kateqoriyalar,
        "sohbet_var": "Söhbət" in kateqoriyalar,
    }
