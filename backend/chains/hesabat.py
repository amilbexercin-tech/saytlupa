"""AI hesabat zənciri (LCEL).

Zəncirin quruluşu:

    {xam analiz}
        │
        ├─ RunnableParallel ──► url        (olduğu kimi ötürülür)
        │                   └─► melumat    (xam JSON → oxunaqlı xülasə)
        │
        ▼
    ChatPromptTemplate  (System + Human mesajları)
        │
        ▼
    Model  (Claude → Gemini → Gemma fallback zənciri)
        │
        ▼
    JsonOutputParser(pydantic_object=AIHesabat)   ← sxem yoxlanışı
"""

from __future__ import annotations

import logging
import time

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel

from ..prompts import hesabat as prompt_metni
from ..schemas import AIHesabat
from .model import guclu_model_var, model_adi, model_zenciri

log = logging.getLogger("saytlupa")

# Model sahə adlarını Azərbaycan orfoqrafiyasına uyğun "düzəldə" bilir:
# `seo_catismazliqlari` → `seo_catismazlıqlari` (nöqtəsiz ı). Bu, real sınaqda
# baş verdi və bütün hesabatı sındırdı. Ona görə açarlar müqayisədən əvvəl
# sadələşdirilir.
HERF_EVEZI = str.maketrans(
    {"ı": "i", "ə": "e", "ç": "c", "ş": "s", "ğ": "g", "ö": "o", "ü": "u", "İ": "i"}
)


# ------------------------------------------------------ modelin cavabının təmizi


def _sadelesdir(acar: str) -> str:
    return acar.strip().lower().translate(HERF_EVEZI).replace("-", "_").replace(" ", "_")


def normalla(cavab: dict) -> dict:
    """Modelin JSON cavabını sxemə uyğunlaşdırır.

    - açar adlarındakı orfoqrafiya fərqlərini bağışlayır
    - siyahı gözlənilən yerdə mətn gəlsə siyahıya çevirir
    - çatmayan sahələri boş qoyur (hesabat tamamilə itməsin) və `_catmayan`
      açarında hansıların çatmadığını qeyd edir
    """
    if not isinstance(cavab, dict):
        raise ValueError(f"Model lüğət qaytarmadı: {type(cavab).__name__}")

    gelenler = {_sadelesdir(a): d for a, d in cavab.items()}
    netice: dict = {}
    catmayan: list[str] = []

    for sahe, melumat in AIHesabat.model_fields.items():
        deyer = gelenler.get(_sadelesdir(sahe))
        siyahidir = melumat.annotation is not str

        if deyer is None:
            catmayan.append(sahe)
            netice[sahe] = [] if siyahidir else ""
            continue

        if siyahidir and isinstance(deyer, str):
            deyer = [s.strip() for s in deyer.split("\n") if s.strip()] or [deyer]
        elif not siyahidir and isinstance(deyer, list):
            deyer = " ".join(str(d) for d in deyer)

        netice[sahe] = deyer

    if catmayan:
        log.warning("Hesabatda çatmayan sahələr: %s", ", ".join(catmayan))
    netice["_catmayan"] = catmayan
    return netice


# ------------------------------------------------------- xam məlumatın xülasəsi


def _sahe(neticeler: dict, ad: str) -> dict:
    """Toplayıcının məlumatı — uğursuz olubsa boş lüğət."""
    qeyd = neticeler.get(ad) or {}
    return qeyd.get("data") or {} if qeyd.get("ugurlu") else {}


def xulase_qur(xam: dict) -> str:
    """Xam analizi modelə veriləcək qısa, oxunaqlı mətnə çevirir.

    Bütün JSON-u göndərmək olmaz: həm token bahadır, həm də model lazımsız
    sahələrdə itir. Burada yalnız rəy üçün lazım olan faktlar yığılır.
    """
    n = xam.get("neticeler", {})
    domen, dns = _sahe(n, "domen"), _sahe(n, "dns")
    geo, sert = _sahe(n, "geo"), _sahe(n, "sertifikat")
    sehife, texno = _sahe(n, "sehife"), _sahe(n, "texnologiya")
    dizayn, reklam = _sahe(n, "dizayn"), _sahe(n, "reklam")
    surat = _sahe(n, "surat")
    oz_olcme = surat.get("oz_olcme", {})
    mobil = surat.get("mobil") or {}

    setirler: list[str] = []
    yaz = setirler.append

    yaz("## Domen")
    yaz(f"- Domen: {domen.get('domen', '—')}")
    if domen.get("yas_il"):
        yaz(f"- Yaş: {domen['yas_il']} il (dəqiq, {domen.get('menbe')})")
    elif domen.get("arxiv_ipucu", {}).get("en_azi_yas_il"):
        yaz(
            f"- Yaş: ən azı {domen['arxiv_ipucu']['en_azi_yas_il']} il "
            f"(TƏXMİNİ — bu TLD üçün pulsuz WHOIS yoxdur)"
        )
    if domen.get("qeydiyyatci"):
        yaz(f"- Qeydiyyatçı: {domen['qeydiyyatci']}")

    yaz("\n## Server və infrastruktur")
    yaz(f"- IP: {', '.join(dns.get('a', [])) or '—'}")
    yaz(f"- Ölkə/şəhər: {geo.get('olke', '—')} / {geo.get('seher', '—')}")
    yaz(f"- Provayder: {geo.get('provayder', '—')}")
    yaz(f"- CDN: {dns.get('cdn') or 'yoxdur'}")
    yaz(f"- Poçt xidməti: {dns.get('poct_xidmeti') or '—'}")
    yaz(f"- IPv6: {'var' if dns.get('ipv6_destekleyir') else 'yoxdur'}")
    yaz(f"- SPF: {'var' if dns.get('spf_var') else 'yoxdur'}, "
        f"DMARC: {'var' if dns.get('dmarc_var') else 'yoxdur'}")
    if sert:
        yaz(f"- SSL: {sert.get('veren', '—')}, {sert.get('qalan_gun', '?')} gün qalıb, "
            f"{sert.get('protokol', '—')}")

    yaz("\n## Texnologiya")
    yaz(f"- Tapılanlar: {', '.join(texno.get('texnologiyalar', [])) or '—'}")
    yaz(f"- Server proqramı: {texno.get('server') or '—'}")
    if texno.get("guclendirici"):
        yaz(f"- X-Powered-By: {texno['guclendirici']}")

    yaz("\n## Səhifə və məzmun")
    yaz(f"- Başlıq: {sehife.get('basliq') or '—'}")
    yaz(f"- Meta description: {sehife.get('tesvir') or 'YOXDUR'}")
    yaz(f"- Dil (lang): {sehife.get('dil') or 'TƏYİN EDİLMƏYİB'}")
    yaz(f"- Canonical: {sehife.get('canonical') or 'yoxdur'}")
    yaz(f"- H1 sayı: {sehife.get('basliq_saylari', {}).get('h1', 0)}, "
        f"H2: {sehife.get('basliq_saylari', {}).get('h2', 0)}")
    yaz(f"- Şəkil: {sehife.get('sekil_sayi', 0)}, "
        f"skript: {sehife.get('skript_sayi', 0)}, form: {sehife.get('form_sayi', 0)}")
    yaz(f"- Mobil uyğunluq (viewport): {'var' if sehife.get('mobil_uygun') else 'YOXDUR'}")
    yaz(f"- Daxili link: {sehife.get('daxili_link_sayi', 0)}, "
        f"xarici: {sehife.get('xarici_link_sayi', 0)}")
    if sehife.get("sosial_linkler"):
        yaz(f"- Sosial şəbəkələr: {', '.join(sehife['sosial_linkler'])}")
    if sehife.get("epostalar") or sehife.get("telefonlar"):
        yaz(f"- Əlaqə: {', '.join(sehife.get('epostalar', []) + sehife.get('telefonlar', []))}")
    yaz(f"- Yığılan səhifə sayı: {xam.get('sehife_sayi', 0)}")

    yaz("\n## Performans")
    yaz(f"- Yüklənmə vaxtı: {oz_olcme.get('yuklenme_saniye', '—')} san")
    yaz(f"- HTML ölçüsü: {oz_olcme.get('html_olcusu_kb', '—')} KB")
    yaz(f"- Sıxılma: {oz_olcme.get('sixilma', '—')}")
    yaz(f"- Lazy loading olan şəkil: {oz_olcme.get('lazy_sekil_sayi', 0)} / "
        f"{oz_olcme.get('sekil_sayi', 0)}")
    yaz(f"- CSS faylı: {oz_olcme.get('css_sayi', 0)}, skript: {oz_olcme.get('skript_sayi', 0)}")
    if mobil.get("bal") is not None:
        yaz(f"- PageSpeed (mobil) balı: {mobil['bal']}/100")
        for acar in ("fcp", "lcp", "cls", "tbt"):
            if mobil.get(acar, {}).get("deyer"):
                yaz(f"  - {acar.upper()}: {mobil[acar]['deyer']}")
    else:
        yaz("- PageSpeed balı: alınmadı (açar yoxdur) — yalnız öz ölçmələrimiz var")

    yaz("\n## Dizayn")
    renqler = [r["reng"] for r in dizayn.get("esas_renqler", [])[:6]]
    yaz(f"- Əsas rənglər: {', '.join(renqler) or '—'}")
    sriftler = [s["ad"] for s in dizayn.get("sriftler", [])[:6]]
    yaz(f"- Şriftlər: {', '.join(sriftler) or '—'}")
    if dizayn.get("google_sriftler"):
        yaz(f"- Google Fonts: {', '.join(dizayn['google_sriftler'])}")
    yaz(f"- CSS faylı sayı: {dizayn.get('css_fayl_sayi', 0)}, "
        f"xarici CSS həcmi: {dizayn.get('xarici_css_kb', 0)} KB")

    yaz("\n## Reklam və analitika")
    aletler = [a["ad"] for a in reklam.get("aletler", [])]
    yaz(f"- Alətlər: {', '.join(aletler) or 'heç biri tapılmadı'}")

    qoruma = xam.get("qoruma", {})
    if qoruma.get("qorunur"):
        yaz(f"\n## DİQQƏT\n- Sayt {qoruma.get('xidmet')} bot qoruması arxasındadır. "
            f"Məzmun analizi məhduddur — bu barədə fikir bildirmə.")

    return "\n".join(setirler)


# ------------------------------------------------------------------ zəncir


def zencir(temperatur: float = 0.3):
    """Hesabat zəncirini qurur (LCEL). Model yoxdursa `None`."""
    model = model_zenciri(temperatur, max_token=3000)
    if model is None:
        return None, "yoxdur"

    prompt = ChatPromptTemplate.from_messages(
        [("system", prompt_metni.SISTEM), ("human", prompt_metni.INSAN)]
    )

    hazirliq = RunnableParallel(
        url=RunnableLambda(lambda x: x["url"]),
        melumat=RunnableLambda(lambda x: xulase_qur(x["xam"])),
    )

    # LCEL: hazırlıq → prompt → model → JSON → açarların normallaşdırılması
    # JsonOutputParser sxemi promptda göstərmək üçün `pydantic_object` alır,
    # amma doğrulama `normalla`-dan sonra edilir — model orfoqrafiyanı
    # dəyişəndə bütün hesabat itməsin.
    return (
        hazirliq
        | prompt
        | model
        | JsonOutputParser(pydantic_object=AIHesabat)
        | RunnableLambda(normalla)
    ), model_adi(model)


def yarat(url: str, xam: dict) -> dict:
    """Hesabatı yaradır. Nəticə: {"hesabat": {...}, "olcme": {...}}"""
    olcme: dict = {"model": "yoxdur", "saniye": 0.0, "ugurlu": False}

    if not guclu_model_var():
        olcme["sebeb"] = (
            "Claude və ya Gemini açarı təyin edilməyib. Lokal Gemma ilə uzun mətn "
            "yazmaq bu maşında dəqiqələrlə çəkir, ona görə hesabat buraxılır."
        )
        return {"hesabat": None, "olcme": olcme}

    qurulan, ad = zencir()
    if qurulan is None:
        olcme["sebeb"] = "Heç bir model əlçatan deyil."
        return {"hesabat": None, "olcme": olcme}

    olcme["model"] = ad
    basla = time.perf_counter()
    try:
        hesabat = qurulan.invoke({"url": url, "xam": xam})
        catmayan = hesabat.pop("_catmayan", [])
        olcme["ugurlu"] = True
        if catmayan:
            olcme["catmayan_saheler"] = catmayan
    except Exception as xeta:
        log.warning("Hesabat zənciri sındı: %s", xeta)
        olcme["sebeb"] = str(xeta)[:300]
        hesabat = None

    olcme["saniye"] = round(time.perf_counter() - basla, 2)
    return {"hesabat": hesabat, "olcme": olcme}
