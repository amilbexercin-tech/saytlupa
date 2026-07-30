"""Texnologiya detektoru — framework, CMS, server, CSS yanaşması, analitika.

Wappalyzer məntiqi: HTTP başlıqları + HTML imzaları + skript ünvanları.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..decorators import safe_collector, timed

# (ad, kateqoriya, HTML/skript içində axtarılan naxış)
HTML_IMZALARI: list[tuple[str, str, str]] = [
    ("Next.js", "Framework", r"__NEXT_DATA__|/_next/static"),
    ("Nuxt", "Framework", r"__NUXT__|/_nuxt/"),
    ("React", "Kitabxana", r"data-reactroot|react(-dom)?[.@\-]"),
    ("Vue.js", "Kitabxana", r"data-v-[0-9a-f]{8}|vue(\.min)?\.js"),
    ("Angular", "Framework", r"ng-version|angular(\.min)?\.js"),
    ("Svelte", "Framework", r"svelte-[0-9a-z]{6}"),
    ("WordPress", "CMS", r"/wp-content/|/wp-includes/"),
    ("Shopify", "E-ticarət", r"cdn\.shopify\.com|Shopify\.theme"),
    ("WooCommerce", "E-ticarət", r"woocommerce"),
    ("Wix", "Sayt qurucusu", r"static\.wixstatic\.com|wix-code"),
    ("Tilda", "Sayt qurucusu", r"tildacdn\.com"),
    ("Squarespace", "Sayt qurucusu", r"squarespace"),
    ("Joomla", "CMS", r"/media/jui/|joomla"),
    ("Drupal", "CMS", r"drupal\.js|/sites/default/files"),
    ("OpenCart", "E-ticarət", r"catalog/view/theme"),
    ("Bitrix", "CMS", r"bitrix/js|/bitrix/"),
    ("jQuery", "Kitabxana", r"jquery[.\-]?\d?"),
    ("Bootstrap", "CSS", r"bootstrap(\.min)?\.(css|js)"),
    ("Tailwind CSS", "CSS", r"tailwind|(\s|\")(bg-|text-|flex\s|grid\s)[a-z0-9\-]+"),
    ("Font Awesome", "İkon", r"font-?awesome"),
    ("Swiper", "Kitabxana", r"swiper(\.min)?\.(js|css)"),
    ("GSAP", "Animasiya", r"gsap(\.min)?\.js"),
    ("Framer Motion", "Animasiya", r"framer-motion"),
    ("Cloudflare", "CDN", r"cdn-cgi/"),
]

BASLIQ_IMZALARI: list[tuple[str, str, str, str]] = [
    ("nginx", "Server", "server", r"nginx"),
    ("Apache", "Server", "server", r"apache"),
    ("Microsoft IIS", "Server", "server", r"iis|microsoft-httpapi"),
    ("LiteSpeed", "Server", "server", r"litespeed"),
    ("Cloudflare", "CDN", "server", r"cloudflare"),
    ("Vercel", "Hosting", "server", r"vercel"),
    ("Netlify", "Hosting", "server", r"netlify"),
    ("PHP", "Dil", "x-powered-by", r"php"),
    ("ASP.NET", "Framework", "x-powered-by", r"asp\.net"),
    ("Express", "Framework", "x-powered-by", r"express"),
    ("AWS CloudFront", "CDN", "via", r"cloudfront"),
    ("Fastly", "CDN", "x-served-by", r"cache-"),
]


@safe_collector("texnologiya")
@timed
async def topla(url: str, html: str, basliqlar: dict) -> dict:
    tapilanlar: dict[str, str] = {}
    kicik_html = html.lower()

    for ad, kateqoriya, naxis in HTML_IMZALARI:
        if re.search(naxis, kicik_html, re.IGNORECASE):
            tapilanlar[ad] = kateqoriya

    kicik_basliqlar = {k.lower(): str(v).lower() for k, v in basliqlar.items()}
    for ad, kateqoriya, basliq, naxis in BASLIQ_IMZALARI:
        deyer = kicik_basliqlar.get(basliq, "")
        if deyer and re.search(naxis, deyer):
            tapilanlar[ad] = kateqoriya

    supa = BeautifulSoup(html, "lxml")
    generator = supa.find("meta", attrs={"name": "generator"})
    if generator and generator.get("content"):
        tapilanlar[generator["content"].strip()[:60]] = "Generator (meta)"

    kateqoriyalar: dict[str, list[str]] = {}
    for ad, kateqoriya in tapilanlar.items():
        kateqoriyalar.setdefault(kateqoriya, []).append(ad)

    return {
        "texnologiyalar": sorted(tapilanlar),
        "kateqoriyalar": kateqoriyalar,
        "server": basliqlar.get("server", ""),
        "guclendirici": basliqlar.get("x-powered-by", ""),
        "sayi": len(tapilanlar),
    }
