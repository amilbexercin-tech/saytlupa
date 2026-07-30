"""📄 PDF hesabat — bütün analiz bir faylda (reportlab).

İki incəlik:

1. **Şrift.** reportlab-ın standart şriftləri (Helvetica) `ə`, `ğ`, `ş`, `ı`
   hərflərini tanımır və hesabat oxunmaz hala düşür. Ona görə sistemdən
   Azərbaycan hərflərini bilən TTF axtarılır.
2. **Cədvəl xanaları `Paragraph`-dır.** Adi mətn xanası sətrə sığmayanda
   kəsilmir, çölə daşır — uzun ünvanlar və meta description səhifəni korlayır.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import kontekst

log = logging.getLogger("saytlupa")

FAYL = "hesabat.pdf"

# (adi, qalın) — sırayla yoxlanılır, ilk tapılan işlədilir
SRIFT_NAMIZEDLERI = (
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf"),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
)

ESAS_RENG = colors.HexColor("#1f6feb")
ACIQ = colors.HexColor("#f2f4f8")
XETT = colors.HexColor("#d9dde3")


# ------------------------------------------------------------------ şrift/üslub


def srift_qur() -> tuple[str, str]:
    """(adi, qalın) şrift adlarını qaytarır. Tapılmasa Helvetica-ya qayıdır."""
    for adi_yol, qalin_yol in SRIFT_NAMIZEDLERI:
        if not Path(adi_yol).exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("SaytLupa", adi_yol))
            qalin = "SaytLupa"
            if Path(qalin_yol).exists():
                pdfmetrics.registerFont(TTFont("SaytLupa-Bold", qalin_yol))
                qalin = "SaytLupa-Bold"
            return "SaytLupa", qalin
        except Exception as xeta:  # şrift sınıqdırsa növbətini yoxlayırıq
            log.warning("Şrift qeydiyyatı alınmadı (%s): %s", adi_yol, xeta)

    log.warning(
        "Azərbaycan hərflərini bilən şrift tapılmadı — PDF-də 'ə', 'ğ', 'ş' "
        "hərfləri düzgün görünməyə bilər."
    )
    return "Helvetica", "Helvetica-Bold"


def uslublar() -> dict:
    adi, qalin = srift_qur()
    esas = getSampleStyleSheet()
    return {
        "_srift": (adi, qalin),
        "basliq": ParagraphStyle(
            "basliq", parent=esas["Title"], fontName=qalin, fontSize=22, spaceAfter=4
        ),
        "alt": ParagraphStyle(
            "alt", parent=esas["Normal"], fontName=adi, fontSize=9.5,
            textColor=colors.grey, spaceAfter=12,
        ),
        "bolme": ParagraphStyle(
            "bolme", parent=esas["Heading2"], fontName=qalin, fontSize=13,
            textColor=ESAS_RENG, spaceBefore=14, spaceAfter=6,
        ),
        "metn": ParagraphStyle(
            "metn", parent=esas["Normal"], fontName=adi, fontSize=9.5, leading=14
        ),
        "xana_ad": ParagraphStyle(
            "xana_ad", parent=esas["Normal"], fontName=qalin, fontSize=8.5, leading=11
        ),
        "xana": ParagraphStyle(
            "xana", parent=esas["Normal"], fontName=adi, fontSize=8.5, leading=11
        ),
        "xirda": ParagraphStyle(
            "xirda", parent=esas["Normal"], fontName=adi, fontSize=8,
            textColor=colors.grey, leading=11,
        ),
    }


def qacir(deyer) -> str:
    """reportlab xanaları XML kimi oxuyur — `&`, `<`, `>` qaçırılmalıdır."""
    return (
        str(deyer if deyer is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ------------------------------------------------------------------ hissələr


def _cedvel(setirler: list[list], u: dict, en: list | None = None) -> Table:
    """Ad-dəyər cədvəli. Xanalar `Paragraph`-dır ki, uzun mətn sətrə bölünsün."""
    hazir = [
        [Paragraph(qacir(setir[0]), u["xana_ad"])]
        + [Paragraph(qacir(x), u["xana"]) for x in setir[1:]]
        for setir in setirler
    ]
    cedvel = Table(hazir, colWidths=en or [45 * mm, 129 * mm], hAlign="LEFT")
    cedvel.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), ACIQ),
                ("GRID", (0, 0), (-1, -1), 0.4, XETT),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return cedvel


def _reng_cedveli(renqler: list[dict], u: dict):
    """Rəng palitrası — birinci sütun rəngin özü ilə boyanır."""
    if not renqler:
        return Paragraph("Rəng tapılmadı.", u["metn"])

    secilmis = renqler[:10]
    hazir = [
        [
            Paragraph("", u["xana"]),
            Paragraph(qacir(r.get("reng", "")), u["xana"]),
            Paragraph(f"{r.get('tekrar', 0)} dəfə", u["xana"]),
        ]
        for r in secilmis
    ]
    cedvel = Table(hazir, colWidths=[20 * mm, 60 * mm, 30 * mm], hAlign="LEFT")
    uslub = [
        ("GRID", (0, 0), (-1, -1), 0.4, XETT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for sira, qeyd in enumerate(secilmis):
        try:
            uslub.append(
                ("BACKGROUND", (0, sira), (0, sira), colors.HexColor(qeyd["reng"]))
            )
        except Exception:
            pass  # yanlış hex dəyəri hesabatı dayandırmasın
    cedvel.setStyle(TableStyle(uslub))
    return cedvel


def _hesabat_bolmesi(hesabat: dict, u: dict) -> list:
    """AI hesabatın 6 bəndi."""
    parcalar: list = [Paragraph("AI hesabat", u["bolme"])]

    for sahe, ad in (
        ("meqsed", "Saytın məqsədi"),
        ("hedef_auditoriya", "Hədəf auditoriya"),
        ("texnologiyalar", "Texnologiyalar"),
    ):
        if hesabat.get(sahe):
            parcalar += [
                Paragraph(f"<b>{ad}:</b> {qacir(hesabat[sahe])}", u["metn"]),
                Spacer(1, 4),
            ]

    for sahe, ad in (
        ("performans_problemleri", "Performans problemləri"),
        ("seo_catismazliqlari", "SEO çatışmazlıqları"),
        ("muasir_versiya_tovsiyeleri", "Müasir versiya üçün tövsiyələr"),
    ):
        deyerler = hesabat.get(sahe) or []
        if not deyerler:
            continue
        parcalar += [Spacer(1, 6), Paragraph(f"<b>{ad}</b>", u["metn"])]
        parcalar += [Paragraph(f"• {qacir(d)}", u["metn"]) for d in deyerler]
    return parcalar


# ------------------------------------------------------------------ sənəd


def qur(netice: dict, yol: Path) -> Path:
    """Analizin nəticəsindən PDF yaradır (bazadan asılı deyil — sınaqlar üçün)."""
    u = uslublar()
    xam = netice.get("xam") or {}

    domen = kontekst.sahe(xam, "domen")
    dns = kontekst.sahe(xam, "dns")
    geo = kontekst.sahe(xam, "geo")
    sert = kontekst.sahe(xam, "sertifikat")
    sehife = kontekst.sahe(xam, "sehife")
    texno = kontekst.sahe(xam, "texnologiya")
    dizayn = kontekst.sahe(xam, "dizayn")
    reklam = kontekst.sahe(xam, "reklam")
    surat = kontekst.sahe(xam, "surat")
    oz_olcme = surat.get("oz_olcme", {}) or {}
    mobil = surat.get("mobil") or {}

    tarix = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    parcalar: list = [
        # Emoji işlədilmir: sistem şriftlərində emoji qlifi yoxdur, boş qutu çıxır
        Paragraph(qacir(netice.get("domain", "")), u["basliq"]),
        Paragraph(
            f"{qacir(netice.get('url', ''))} · SaytLupa hesabatı · {tarix}", u["alt"]
        ),
        HRFlowable(width="100%", color=ESAS_RENG, thickness=1.2),
        Spacer(1, 10),
    ]

    # --- Ümumi baxış ---
    yas = "—"
    if domen.get("yas_il"):
        yas = f"{domen['yas_il']} il ({domen.get('menbe', '')})"
    elif (domen.get("arxiv_ipucu") or {}).get("en_azi_yas_il"):
        yas = f"ən azı {domen['arxiv_ipucu']['en_azi_yas_il']} il (TƏXMİNİ)"

    parcalar += [
        Paragraph("Ümumi baxış", u["bolme"]),
        _cedvel(
            [
                ["Domen", domen.get("domen") or netice.get("domain", "")],
                ["Yaş", yas],
                ["Qeydiyyatçı", domen.get("qeydiyyatci") or "—"],
                ["Analiz vəziyyəti", netice.get("status", "")],
                ["Yığılan səhifə", netice.get("sehife_sayi", 0)],
                ["RAG parçası", netice.get("chunk_sayi", 0)],
            ],
            u,
        ),
    ]

    if (xam.get("qoruma") or {}).get("qorunur"):
        parcalar += [
            Spacer(1, 8),
            Paragraph(
                f"<b>Diqqət:</b> sayt {qacir(xam['qoruma'].get('xidmet', ''))} bot "
                "qoruması arxasındadır — məzmun analizi məhduddur.",
                u["metn"],
            ),
        ]

    # --- AI hesabat ---
    if netice.get("ai_hesabat"):
        parcalar += _hesabat_bolmesi(netice["ai_hesabat"], u)
    else:
        sebeb = (xam.get("hesabat_olcme") or {}).get("sebeb", "")
        parcalar += [
            Paragraph("AI hesabat", u["bolme"]),
            Paragraph(qacir(sebeb) or "AI hesabat yazılmayıb.", u["metn"]),
        ]

    # --- Server və texnologiya ---
    parcalar += [
        Paragraph("Server və texnologiya", u["bolme"]),
        _cedvel(
            [
                ["IP ünvanları", ", ".join(dns.get("a", [])) or "—"],
                ["Ölkə / şəhər", f"{geo.get('olke', '—')} / {geo.get('seher', '—')}"],
                ["Provayder", geo.get("provayder") or "—"],
                ["CDN", dns.get("cdn") or "yoxdur"],
                ["Poçt xidməti", dns.get("poct_xidmeti") or "—"],
                [
                    "SPF / DMARC",
                    f"{'var' if dns.get('spf_var') else 'yox'} / "
                    f"{'var' if dns.get('dmarc_var') else 'yox'}",
                ],
                [
                    "SSL",
                    f"{sert.get('veren', '—')} · {sert.get('protokol', '—')} · "
                    f"{sert.get('qalan_gun', '?')} gün qalıb",
                ],
                ["Texnologiyalar", ", ".join(texno.get("texnologiyalar", [])) or "—"],
                ["Server proqramı", texno.get("server") or "—"],
            ],
            u,
        ),
    ]

    # --- Performans ---
    performans = [
        ["Yüklənmə vaxtı", f"{oz_olcme.get('yuklenme_saniye', '—')} san"],
        ["HTML ölçüsü", f"{oz_olcme.get('html_olcusu_kb', '—')} KB"],
        ["Sıxılma", oz_olcme.get("sixilma") or "—"],
        [
            "Lazy loading",
            f"{oz_olcme.get('lazy_sekil_sayi', 0)} / {oz_olcme.get('sekil_sayi', 0)} şəkil",
        ],
        [
            "CSS / skript sayı",
            f"{oz_olcme.get('css_sayi', 0)} / {oz_olcme.get('skript_sayi', 0)}",
        ],
        [
            "PageSpeed (mobil)",
            f"{mobil['bal']}/100" if mobil.get("bal") is not None
            else "alınmadı — açar yoxdur",
        ],
    ]
    parcalar += [Paragraph("Performans", u["bolme"]), _cedvel(performans, u)]

    # --- Dizayn ---
    parcalar += [
        PageBreak(),
        Paragraph("Dizayn", u["bolme"]),
        Paragraph("Ən çox təkrarlanan rənglər:", u["metn"]),
        Spacer(1, 6),
        _reng_cedveli(dizayn.get("esas_renqler", []), u),
        Spacer(1, 10),
        _cedvel(
            [
                [
                    "Şriftlər",
                    ", ".join(s.get("ad", "") for s in dizayn.get("sriftler", [])) or "—",
                ],
                ["Google Fonts", ", ".join(dizayn.get("google_sriftler", [])) or "—"],
                ["CSS faylı", dizayn.get("css_fayl_sayi", 0)],
                ["Xarici CSS həcmi", f"{dizayn.get('xarici_css_kb', 0)} KB"],
            ],
            u,
        ),
    ]

    # --- Məzmun ---
    sosial = sehife.get("sosial_linkler", {}) or {}
    sayilar = sehife.get("basliq_saylari", {}) or {}
    parcalar += [
        Paragraph("Məzmun və struktur", u["bolme"]),
        _cedvel(
            [
                ["Başlıq", sehife.get("basliq") or "—"],
                ["Meta description", sehife.get("tesvir") or "YOXDUR"],
                ["Dil (lang)", sehife.get("dil") or "TƏYİN EDİLMƏYİB"],
                ["Canonical", sehife.get("canonical") or "yoxdur"],
                [
                    "Başlıqlar",
                    f"H1: {sayilar.get('h1', 0)} · H2: {sayilar.get('h2', 0)} "
                    f"· H3: {sayilar.get('h3', 0)}",
                ],
                ["Mobil uyğunluq", "var" if sehife.get("mobil_uygun") else "YOXDUR"],
                [
                    "Şəkil / form / skript",
                    f"{sehife.get('sekil_sayi', 0)} / {sehife.get('form_sayi', 0)} / "
                    f"{sehife.get('skript_sayi', 0)}",
                ],
                ["Sosial şəbəkələr", ", ".join(sosial) or "—"],
                [
                    "Əlaqə",
                    ", ".join(
                        list(sehife.get("epostalar", []))
                        + list(sehife.get("telefonlar", []))
                    ) or "—",
                ],
                [
                    "Reklam / analitika",
                    ", ".join(a.get("ad", "") for a in reklam.get("aletler", []))
                    or "tapılmadı",
                ],
            ],
            u,
        ),
    ]

    # --- Yığılan səhifələr ---
    sehifeler = netice.get("sehifeler") or []
    if sehifeler:
        parcalar += [
            Paragraph("Yığılan səhifələr", u["bolme"]),
            _cedvel(
                [[s.get("basliq") or "—", s.get("url", "")] for s in sehifeler[:15]],
                u,
                en=[70 * mm, 104 * mm],
            ),
        ]

    parcalar += [
        Spacer(1, 16),
        HRFlowable(width="100%", color=XETT),
        Spacer(1, 6),
        Paragraph(
            "SaytLupa ilə yaradılıb. Bütün rəqəmlər ölçmə nəticəsidir; dəqiq "
            "bilinməyən məlumat «TƏXMİNİ» kimi işarələnib və ya boş saxlanılıb. "
            "Analiz robots.txt qaydalarına hörmətlə aparılıb.",
            u["xirda"],
        ),
    ]

    yol.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(
        str(yol),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"SaytLupa — {netice.get('domain', '')}",
        author="SaytLupa",
    ).build(parcalar)
    return yol


def yarat(analiz_id: int) -> dict:
    """PDF-i `storage/pdf/<domain>/hesabat.pdf` faylına yazır."""
    k = kontekst.konteks(analiz_id)
    if k is None:
        return {"ugurlu": False, "tapilmadi": True, "sebeb": "Belə analiz yoxdur"}

    yol = kontekst.qovluq("pdf", k["domain"]) / FAYL
    try:
        qur(k, yol)
    except Exception as xeta:
        log.exception("PDF yaradıla bilmədi")
        return {"ugurlu": False, "sebeb": str(xeta)[:300]}

    olcu_kb = round(yol.stat().st_size / 1024, 1)
    log.info("PDF hazırdır: %s (%s KB)", yol, olcu_kb)
    return {
        "ugurlu": True,
        "fayl": str(yol),
        "olcu_kb": olcu_kb,
        "yukle_url": f"/api/analyze/{analiz_id}/yukle/pdf",
    }
