"""İki saytın analizini yan-yana qoyur (Gün 11).

MCP `saytlari_muqayise_et` alətinin və `/api/muqayise` endpoint-inin məntiqi
buradadır. Qayda dəyişmir: **uydurma rəqəm yazılmır** — məlumat yoxdursa sahə
`None` qalır və mətndə "bilinmir" kimi görünür.
"""

from __future__ import annotations

from . import db
from .collectors.base import domen as domen_cixart


# --------------------------------------------------------------- sayt tapma


def sayt_tap(gosterici: str) -> db.Sayt | None:
    """`5`, `example.com` və ya `https://example.com/abc` — hamısını qəbul edir."""
    gosterici = (gosterici or "").strip()
    if not gosterici:
        return None

    with db.sessiya() as s:
        if gosterici.isdigit():
            return s.get(db.Sayt, int(gosterici))

        ad = domen_cixart(gosterici) or gosterici.lower()
        sayt = s.query(db.Sayt).filter(db.Sayt.domain == ad).first()
        if sayt:
            return sayt
        # "asan" kimi yarımçıq yazılışa da imkan veririk
        return s.query(db.Sayt).filter(db.Sayt.domain.like(f"%{ad}%")).first()


def _son_analiz(site_id: int) -> db.Analiz | None:
    """Saytın sonuncu **uğurlu** analizi; yoxdursa sonuncusu."""
    with db.sessiya() as s:
        hazir = (
            s.query(db.Analiz)
            .filter(db.Analiz.site_id == site_id, db.Analiz.status == "hazir")
            .order_by(db.Analiz.id.desc())
            .first()
        )
        if hazir:
            return hazir
        return (
            s.query(db.Analiz)
            .filter(db.Analiz.site_id == site_id)
            .order_by(db.Analiz.id.desc())
            .first()
        )


# --------------------------------------------------------------- sahə çıxarma


def _data(xam: dict, toplayici: str) -> dict:
    """Toplayıcının `data` hissəsi — toplayıcı sınıbsa boş lüğət."""
    netice = (xam.get("neticeler") or {}).get(toplayici) or {}
    return netice.get("data") or {} if netice.get("ugurlu") else {}


def _profil(sayt: db.Sayt, analiz: db.Analiz | None) -> dict:
    """Bir saytın müqayisəyə girən göstəriciləri."""
    xam = (analiz.xam_json if analiz else None) or {}
    sehife = _data(xam, "sehife")
    texno = _data(xam, "texnologiya")
    dizayn = _data(xam, "dizayn")
    reklam = _data(xam, "reklam")
    dns = _data(xam, "dns")
    geo = _data(xam, "geo")
    sert = _data(xam, "sertifikat")
    domen = _data(xam, "domen")

    return {
        "site_id": sayt.id,
        "url": sayt.url,
        "domain": sayt.domain,
        "analiz_id": analiz.id if analiz else None,
        "analiz_tarixi": analiz.tarix if analiz else None,
        "status": analiz.status if analiz else "analiz yoxdur",
        # performans
        "yuklenme_saniye": xam.get("yuklenme_saniye"),
        "sehife_sayi": xam.get("sehife_sayi"),
        "chunk_sayi": (xam.get("rag") or {}).get("chunk_sayi"),
        "skript_sayi": sehife.get("skript_sayi"),
        "sekil_sayi": sehife.get("sekil_sayi"),
        # texnologiya və infrastruktur
        "texnologiyalar": texno.get("texnologiyalar") or [],
        "server": texno.get("server"),
        "cdn": dns.get("cdn"),
        "olke": geo.get("olke"),
        "provayder": geo.get("provayder"),
        "ipv6": dns.get("ipv6_destekleyir"),
        "sertifikat_qalan_gun": sert.get("qalan_gun"),
        "domen_yas_il": domen.get("yas_il"),
        # SEO
        "meta_tesvir_var": bool(sehife.get("tesvir")),
        "og_var": bool(sehife.get("og_basliq")),
        "canonical_var": bool(sehife.get("canonical")),
        "dil": sehife.get("dil"),
        "h1_sayi": len(sehife.get("h1_metnler") or []),
        # dizayn və izləyicilər
        "reng_sayi": dizayn.get("reng_sayi"),
        "srift_sayi": len(dizayn.get("sriftler") or []),
        "izleyici_sayi": reklam.get("sayi"),
        "analitika_var": reklam.get("analitika_var"),
        # AI rəyi
        "meqsed": (analiz.ai_hesabat or {}).get("meqsed") if analiz else None,
        # Məlumatın etibarlılığı — aşağıda hökm verilib-verilməyəcəyini həll edir
        "qorunur": bool((xam.get("qoruma") or {}).get("qorunur")),
        "qoruma_xidmeti": (xam.get("qoruma") or {}).get("xidmet") or "bot qoruması",
        "js_ile_qurulur": bool((xam.get("js_sayt") or {}).get("js_ile_qurulur")),
        "js_cerceve": (xam.get("js_sayt") or {}).get("cerceve") or "JS",
    }


def _etibarsizliq(p: dict) -> str:
    """Saytın öz məzmununa əsaslanan rəqəmlər niyə etibarsızdır — yoxdursa boş."""
    if p["qorunur"]:
        return (
            f"{p['domain']} {p['qoruma_xidmeti']} arxasındadır — ölçülən rəqəmlər "
            "yoxlama səhifəsinə aiddir, real sayta yox."
        )
    if p["js_ile_qurulur"]:
        return (
            f"{p['domain']} {p['js_cerceve']} ilə brauzerdə çəkilir — serverin "
            "verdiyi HTML boş qabıqdır, ölçülən rəqəmlər real səhifəni göstərmir."
        )
    return ""


# --------------------------------------------------------------- müqayisə


# Saytın öz cavabından asılı OLMAYAN ölçülər: WHOIS və TLS əl dəyişməsi
# saytın verdiyi HTML-dən asılı deyil, ona görə sayt bloklansa da etibarlıdır.
KENAR_OLCULER = {"domen_yas_il", "sertifikat_qalan_gun"}

# (açar, başlıq, "boyuk"/"kicik"/"" — hansı tərəf üstün sayılır)
OLCULER = [
    ("yuklenme_saniye", "Yüklənmə (san)", "kicik"),
    ("sehife_sayi", "Yığılan səhifə", "boyuk"),
    ("skript_sayi", "Skript sayı", "kicik"),
    ("sekil_sayi", "Şəkil sayı", ""),
    ("domen_yas_il", "Domen yaşı (il)", "boyuk"),
    ("sertifikat_qalan_gun", "Sertifikat (qalan gün)", "boyuk"),
    ("reng_sayi", "Rəng sayı", ""),
    ("izleyici_sayi", "İzləyici/reklam aləti", "kicik"),
    ("h1_sayi", "H1 başlıq sayı", ""),
]


def _ustun(acar: str, istiqamet: str, a, b, etibarli: bool = True) -> str:
    """Hansı sayt bu ölçüdə üstündür.

    'birinci' | 'ikinci' | 'beraber' | 'neytral' | 'bilinmir' | 'etibarsiz'.
    `neytral` — ölçünün yaxşı/pis istiqaməti yoxdur (məsələn şəkil sayı):
    fərqli olsalar da birini üstün saymaq düzgün olmazdı.
    `etibarsiz` — tərəflərdən biri bloklanıb və ya brauzerdə çəkilir: rəqəm
    real sayta aid deyil, ona görə hökm verilmir (bax `KENAR_OLCULER`).
    """
    if not etibarli and acar not in KENAR_OLCULER:
        return "etibarsiz"
    if a is None or b is None:
        return "bilinmir"
    if not istiqamet:
        return "neytral"
    if a == b:
        return "beraber"
    if istiqamet == "kicik":
        return "birinci" if a < b else "ikinci"
    return "birinci" if a > b else "ikinci"


def _seo_ferqi(p: dict) -> list[str]:
    catismayan = []
    if not p["meta_tesvir_var"]:
        catismayan.append("meta description")
    if not p["og_var"]:
        catismayan.append("Open Graph")
    if not p["canonical_var"]:
        catismayan.append("canonical")
    return catismayan


def muqayise_et(gosterici1: str, gosterici2: str) -> dict:
    """İki saytı yan-yana qoyur. Sayt tapılmasa `tapilmadi` qaytarır."""
    sayt1, sayt2 = sayt_tap(gosterici1), sayt_tap(gosterici2)
    if sayt1 is None or sayt2 is None:
        return {
            "tapilmadi": True,
            "sebeb": f"Bazada tapılmadı: {gosterici1 if sayt1 is None else gosterici2}. "
                     f"Əvvəlcə həmin saytı analiz etmək lazımdır.",
        }
    if sayt1.id == sayt2.id:
        return {"tapilmadi": True, "sebeb": "Eyni sayt iki dəfə göstərilib."}

    p1 = _profil(sayt1, _son_analiz(sayt1.id))
    p2 = _profil(sayt2, _son_analiz(sayt2.id))

    # Bir tərəf bloklanıbsa və ya brauzerdə çəkilirsə, saytın məzmunundan
    # çıxarılan rəqəmlərlə "üstündür" yazmaq uydurma olar
    xeberdarliqlar = [m for m in (_etibarsizliq(p1), _etibarsizliq(p2)) if m]
    etibarli = not xeberdarliqlar

    olculer = [
        {
            "olcu": basliq,
            "birinci": p1[acar],
            "ikinci": p2[acar],
            "ustun": _ustun(acar, istiqamet, p1[acar], p2[acar], etibarli),
        }
        for acar, basliq, istiqamet in OLCULER
    ]

    t1, t2 = set(p1["texnologiyalar"]), set(p2["texnologiyalar"])

    return {
        "birinci": p1,
        "ikinci": p2,
        "olculer": olculer,
        "xeberdarliqlar": xeberdarliqlar,
        "texnologiya": {
            "ortaq": sorted(t1 & t2),
            "yalniz_birinci": sorted(t1 - t2),
            "yalniz_ikinci": sorted(t2 - t1),
        },
        "seo_catismazliqlari": {
            p1["domain"]: _seo_ferqi(p1),
            p2["domain"]: _seo_ferqi(p2),
        },
        "xulase": xulase_metni(p1, p2, olculer, t1, t2, xeberdarliqlar),
    }


def _deyer(v) -> str:
    """Cədvəl xanası. Boş sətir də "bilinmir"dir — toplayıcı sahəni tapa bilməyib."""
    if v is None or v == "" or v == []:
        return "bilinmir"
    if v is True:
        return "var"
    if v is False:
        return "yox"
    return str(v)


def xulase_metni(
    p1: dict, p2: dict, olculer: list[dict], t1: set, t2: set,
    xeberdarliqlar: list[str] | None = None,
) -> str:
    """MCP alətinin qaytardığı oxunaqlı mətn (markdown cədvəli)."""
    setirler = [f"# {p1['domain']} ↔ {p2['domain']}", ""]

    # Xəbərdarlıq cədvəldən ƏVVƏL gəlir — rəqəmlərə baxmazdan qabaq oxunmalıdır
    for mesaj in xeberdarliqlar or []:
        setirler.append(f"> ⚠️ {mesaj}")
    if xeberdarliqlar:
        setirler += ["", "Bu səbəbdən saytın məzmununa əsaslanan ölçülərdə "
                     "üstünlük hökmü verilmir (`—`).", ""]

    setirler += [
        f"| Ölçü | {p1['domain']} | {p2['domain']} | Üstün |",
        "|---|---|---|---|",
    ]
    ad = {"birinci": p1["domain"], "ikinci": p2["domain"],
          "beraber": "bərabər", "neytral": "—", "bilinmir": "—",
          "etibarsiz": "—"}
    for o in olculer:
        setirler.append(
            f"| {o['olcu']} | {_deyer(o['birinci'])} | {_deyer(o['ikinci'])} "
            f"| {ad[o['ustun']]} |"
        )

    setirler += [
        "",
        f"**Server:** {p1['domain']} → {_deyer(p1['server'])} · "
        f"{p2['domain']} → {_deyer(p2['server'])}",
        f"**CDN:** {_deyer(p1['cdn'])} ↔ {_deyer(p2['cdn'])}",
        f"**Yerləşdiyi ölkə:** {_deyer(p1['olke'])} ↔ {_deyer(p2['olke'])}",
        "",
        f"**Ortaq texnologiyalar:** {', '.join(sorted(t1 & t2)) or 'yoxdur'}",
        f"**Yalnız {p1['domain']}:** {', '.join(sorted(t1 - t2)) or 'yoxdur'}",
        f"**Yalnız {p2['domain']}:** {', '.join(sorted(t2 - t1)) or 'yoxdur'}",
    ]

    for p in (p1, p2):
        catismayan = _seo_ferqi(p)
        setirler.append(
            f"**{p['domain']} SEO çatışmazlıqları:** "
            + (", ".join(catismayan) if catismayan else "tapılmadı")
        )

    if p1["meqsed"] or p2["meqsed"]:
        setirler += [
            "",
            f"**AI rəyi — {p1['domain']}:** {p1['meqsed'] or 'hesabat yoxdur'}",
            f"**AI rəyi — {p2['domain']}:** {p2['meqsed'] or 'hesabat yoxdur'}",
        ]

    return "\n".join(setirler)
