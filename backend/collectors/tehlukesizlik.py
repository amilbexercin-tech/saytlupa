"""Passiv təhlükəsizlik auditi — saytın açıqlarını tapır və həll təklif edir.

**Yalnız passiv yoxlama:** brauzerin/analizatorun onsuz da etdiyi GET/HEAD
sorğuları. Heç bir istismar, injection payload, brute-force YOXDUR — ona görə
istənilən saytda qanunidir (mövcud analizlə eyni statusda).

**Uydurma yoxdur (ƏSAS QANUN):** açıq yalnız **həqiqətən təsdiqlənəndə** yazılır.
Məsələn açıq fayl üçün təkcə HTTP 200 kifayət etmir — məzmun imzası da uyğun
gəlməlidir (SPA-lar hər yola 200 + index.html qaytara bilər).

**Bal riyazi hesablanır**, LLM ilə yox — rəqəm həmişə dürüstdür.

Tapıntı sxemi ümumidir; gələcək dərin/aktiv skan (Strix və s.) eyni formatda
tapıntı verib elə bu UI-yə düşəcək.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

import httpx

from .. import sebeke
from ..config import ayarlar
from ..decorators import safe_collector, timed
from .base import kok_url

# Səviyyə → bal cəzası (100-dən çıxılır). Riyazidir, dəyişməzdir.
CEZA = {"kritik": 40, "yuksek": 20, "orta": 10, "asagi": 4, "melumat": 0}

# HTML-də açıq sızan sirlərin dəqiq nümunələri (yalançı siqnal olmasın deyə spesifik).
SIRR_NAXISLARI: list[tuple[str, str, str]] = [
    ("sirr_google", "Google API açarı", r"AIza[0-9A-Za-z\-_]{35}"),
    ("sirr_aws", "AWS giriş açarı", r"AKIA[0-9A-Z]{16}"),
    ("sirr_stripe", "Stripe canlı açarı", r"sk_live_[0-9a-zA-Z]{24}"),
    ("sirr_slack", "Slack token-i", r"xox[baprs]-[0-9A-Za-z\-]{10,}"),
    ("sirr_private_key", "private key bloku", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]

# Yoxlanan təhlükəsizlik başlıqları: (başlıq, səviyyə, ad, risk, həll)
BASLIQ_YOXLAMALARI: list[tuple[str, str, str, str, str]] = [
    (
        "content-security-policy", "orta",
        "CSP (Content-Security-Policy) yoxdur",
        "Zərərli skriptlərin (XSS) qarşısını alan əsas müdafiə yoxdur.",
        "Serverə uyğun bir CSP başlığı əlavə et, məs: "
        "Content-Security-Policy: default-src 'self'",
    ),
    (
        "strict-transport-security", "orta",
        "HSTS başlığı yoxdur",
        "Brauzer HTTPS-i məcbur etmir; downgrade (HTTP-yə endirmə) hücumu mümkündür.",
        "Əlavə et: Strict-Transport-Security: max-age=31536000; includeSubDomains",
    ),
    (
        "x-content-type-options", "asagi",
        "X-Content-Type-Options yoxdur",
        "Brauzer fayl növünü təxmin edə (MIME-sniffing) və zərərli məzmunu işə sala bilər.",
        "Əlavə et: X-Content-Type-Options: nosniff",
    ),
    (
        "referrer-policy", "asagi",
        "Referrer-Policy yoxdur",
        "İstifadəçinin gəldiyi tam ünvan xarici saytlara sıza bilər.",
        "Əlavə et: Referrer-Policy: strict-origin-when-cross-origin",
    ),
    (
        "permissions-policy", "melumat",
        "Permissions-Policy yoxdur",
        "Kamera, mikrofon, geolokasiya kimi brauzer imkanları məhdudlaşdırılmayıb.",
        "Ehtiyac olmayan imkanları bağla, məs: Permissions-Policy: geolocation=(), camera=()",
    ),
]

# Açıq qalması təhlükəli fayllar: (yol, səviyyə, imza-yoxlayıcı, ad, risk, həll)
# İmza funksiyası cavabı alıb "həqiqətən bu fayldırmı?" deyir — 200 tək kifayət etmir.
def _env_imza(cavab: httpx.Response) -> bool:
    m = cavab.text[:2000]
    return "<html" not in m.lower() and bool(re.search(r"[A-Z][A-Z0-9_]{2,}\s*=", m))


def _git_config_imza(cavab: httpx.Response) -> bool:
    return "[core]" in cavab.text[:500] and "repositoryformatversion" in cavab.text[:500]


def _git_head_imza(cavab: httpx.Response) -> bool:
    return cavab.text[:64].strip().startswith("ref:")


def _sql_imza(cavab: httpx.Response) -> bool:
    m = cavab.text[:4000].upper()
    return "<HTML" not in m and ("INSERT INTO" in m or "CREATE TABLE" in m)


def _phpinfo_imza(cavab: httpx.Response) -> bool:
    return "phpinfo()" in cavab.text[:3000] or "<title>phpinfo()" in cavab.text[:3000]


def _server_status_imza(cavab: httpx.Response) -> bool:
    return "Apache Server Status" in cavab.text[:2000]


def _ds_store_imza(cavab: httpx.Response) -> bool:
    return b"Bud1" in cavab.content[:8]


def _htpasswd_imza(cavab: httpx.Response) -> bool:
    m = cavab.text[:1000]
    return "<html" not in m.lower() and bool(re.search(r"^[^:\s]+:\$?", m.strip()))


def _acar_fayl_imza(cavab: httpx.Response) -> bool:
    """Private key / SSH açar faylları."""
    return "-----BEGIN" in cavab.text[:400] and "PRIVATE KEY" in cavab.text[:400]


def _aws_imza(cavab: httpx.Response) -> bool:
    m = cavab.text[:1500]
    return "aws_access_key_id" in m.lower() or bool(re.search(r"AKIA[0-9A-Z]{16}", m))


def _htaccess_imza(cavab: httpx.Response) -> bool:
    m = cavab.text[:1500]
    return "<html" not in m.lower() and bool(
        re.search(r"RewriteEngine|<IfModule|Order\s+(allow|deny)|AuthType", m, re.IGNORECASE))


def _json_imza(cavab: httpx.Response) -> bool:
    m = cavab.text[:600].lstrip()
    return m.startswith("{") and ('"dependencies"' in cavab.text[:3000]
                                  or '"name"' in cavab.text[:1500]
                                  or '"require"' in cavab.text[:3000])


def _web_config_imza(cavab: httpx.Response) -> bool:
    return "<configuration" in cavab.text[:800] and "system.web" in cavab.text[:2000]


def _npmrc_imza(cavab: httpx.Response) -> bool:
    m = cavab.text[:800]
    return "<html" not in m.lower() and ("_authToken" in m or "//registry" in m)


FAYL_YOXLAMALARI = [
    ("/.env", "kritik", _env_imza, "«.env» faylı açıqdır",
     "Parollar, API açarları və verilənlər bazası girişi hər kəsə görünür.",
     "Bu faylı veb qovluğundan çıxar və serverdə birbaşa girişi bağla."),
    ("/.git/config", "kritik", _git_config_imza, "«.git» qovluğu açıqdır",
     "Bütün mənbə kodu və keçmiş dəyişikliklər (bəlkə parollar) yüklənə bilər.",
     "«.git» qovluğunu veb kökündən sil və ya girişi qadağan et."),
    ("/.git/HEAD", "kritik", _git_head_imza, "«.git/HEAD» açıqdır",
     "Repozitoriyanın strukturu görünür — mənbə kodu bərpa oluna bilər.",
     "«.git» qovluğuna veb girişini bağla."),
    ("/backup.sql", "kritik", _sql_imza, "Verilənlər bazası yedəyi («backup.sql») açıqdır",
     "Bütün baza (istifadəçilər, parol hash-ləri) yüklənə bilər.",
     "Yedək fayllarını veb qovluğundan çıxar."),
    ("/database.sql", "kritik", _sql_imza, "Verilənlər bazası faylı («database.sql») açıqdır",
     "Bütün baza məzmunu yüklənə bilər.",
     "Bu faylı veb qovluğundan sil."),
    ("/phpinfo.php", "yuksek", _phpinfo_imza, "«phpinfo.php» açıqdır",
     "Server konfiqurasiyası, yollar və modullar açılır — hücum üçün ipucu verir.",
     "Bu test faylını serverdən sil."),
    ("/server-status", "yuksek", _server_status_imza, "Apache «server-status» açıqdır",
     "Aktiv sorğular, IP-lər və daxili yollar görünür.",
     "mod_status-u bağla və ya yalnız localhost-a icazə ver."),
    ("/.DS_Store", "asagi", _ds_store_imza, "«.DS_Store» faylı açıqdır",
     "Qovluqdakı fayl adları sızır — gizli səhifələr aşkarlana bilər.",
     "Bu macOS faylını serverdən sil və yükləmə siyahısına «.DS_Store» əlavə et."),
    ("/.env.local", "kritik", _env_imza, "«.env.local» faylı açıqdır",
     "Yerli mühitin parolları və açarları görünür.",
     "Bu faylı veb qovluğundan çıxar."),
    ("/.env.production", "kritik", _env_imza, "«.env.production» faylı açıqdır",
     "İstehsal mühitinin parolları və açarları görünür.",
     "Bu faylı veb qovluğundan çıxar."),
    ("/.htpasswd", "kritik", _htpasswd_imza, "«.htpasswd» faylı açıqdır",
     "İstifadəçi adları və parol hash-ləri sızır.",
     "Bu faylı veb kökündən çıxar və girişi bağla."),
    ("/.htaccess", "yuksek", _htaccess_imza, "«.htaccess» faylı açıqdır",
     "Server qaydaları və gizli yollar görünür.",
     "«.htaccess» faylına veb girişini qadağan et."),
    ("/id_rsa", "kritik", _acar_fayl_imza, "SSH private açar («id_rsa») açıqdır",
     "Serverə tam giriş verən gizli açar sızır.",
     "Açarı dərhal sil və yenisini yarat (kompromis sayılır)."),
    ("/.ssh/id_rsa", "kritik", _acar_fayl_imza, "«.ssh/id_rsa» açıqdır",
     "Serverə giriş verən SSH açarı sızır.",
     "Açarı dərhal sil və yenisi ilə əvəz et."),
    ("/.aws/credentials", "kritik", _aws_imza, "AWS açarları («.aws/credentials») açıqdır",
     "Bulud hesabına tam giriş verən açarlar sızır.",
     "Açarları dərhal ləğv et və faylı serverdən sil."),
    ("/web.config", "yuksek", _web_config_imza, "«web.config» açıqdır",
     "IIS/ASP.NET konfiqurasiyası, bağlantı sətirləri görünə bilər.",
     "Bu faylın verilməsini serverdə qadağan et."),
    ("/composer.lock", "asagi", _json_imza, "«composer.lock» açıqdır",
     "İstifadə olunan PHP paketləri və dəqiq versiyaları görünür.",
     "Bu faylı veb qovluğundan çıxar."),
    ("/package.json", "asagi", _json_imza, "«package.json» açıqdır",
     "İstifadə olunan JS paketləri və versiyaları görünür.",
     "Bu faylı veb kökündən çıxar."),
    ("/.npmrc", "yuksek", _npmrc_imza, "«.npmrc» açıqdır",
     "npm reyestr token-i (giriş açarı) sıza bilər.",
     "Faylı sil və token-i yenilə."),
    ("/dump.sql", "kritik", _sql_imza, "Baza dump-u («dump.sql») açıqdır",
     "Bütün baza məzmunu yüklənə bilər.",
     "Yedək fayllarını veb qovluğundan çıxar."),
]


def _tap(basliqlar: dict) -> dict:
    """Başlıqları kiçik hərfli açara salır — httpx onsuz da belə verir, amma
    testdə əl ilə verilən başlıqlar üçün də dürüst işləsin."""
    return {str(k).lower(): v for k, v in (basliqlar or {}).items()}


def _tapinti(id, ad, seviyye, tapinti, risk, hell, menbe) -> dict:
    return {
        "id": id, "ad": ad, "seviyye": seviyye,
        "tapinti": tapinti, "risk": risk, "hell": hell, "menbe": menbe,
    }


def _basliq_tapintilari(b: dict, https: bool) -> list[dict]:
    tapintilar = []
    csp = b.get("content-security-policy", "")

    for acar, seviyye, ad, risk, hell in BASLIQ_YOXLAMALARI:
        # HSTS yalnız HTTPS saytda mənalıdır
        if acar == "strict-transport-security" and not https:
            continue
        if not b.get(acar):
            tapintilar.append(_tapinti(acar, ad, seviyye,
                                       f"«{acar}» cavab başlığı yoxdur.", risk, hell, "basliq"))

    # Clickjacking: X-Frame-Options YOX və CSP-də frame-ancestors YOX
    if not b.get("x-frame-options") and "frame-ancestors" not in csp:
        tapintilar.append(_tapinti(
            "x-frame-options", "X-Frame-Options yoxdur", "orta",
            "Nə X-Frame-Options, nə də CSP frame-ancestors var.",
            "Sayt <iframe> içində göstərilib clickjacking hücumuna məruz qala bilər.",
            "Əlavə et: X-Frame-Options: SAMEORIGIN", "basliq"))

    # Versiya/texnologiya sızması
    server = str(b.get("server", ""))
    if server and re.search(r"\d", server):
        tapintilar.append(_tapinti(
            "server_versiya", f"Server versiyası açıqdır: {server}", "asagi",
            f"«Server» başlığı dəqiq versiyanı göstərir: {server}.",
            "Hücumçu həmin versiyanın məlum açıqlarını axtara bilər.",
            "Server başlığından versiya nömrəsini gizlə.", "basliq"))
    if b.get("x-powered-by"):
        tapintilar.append(_tapinti(
            "x_powered_by", f"X-Powered-By açıqdır: {b.get('x-powered-by')}", "asagi",
            f"«X-Powered-By» texnologiyanı açır: {b.get('x-powered-by')}.",
            "Texnologiya və versiya ipucu hücumu asanlaşdırır.",
            "X-Powered-By başlığını sil.", "basliq"))
    for acar in ("x-aspnet-version", "x-aspnetmvc-version"):
        if b.get(acar):
            tapintilar.append(_tapinti(
                acar, f"{acar} açıqdır: {b.get(acar)}", "asagi",
                f"«{acar}» ASP.NET versiyasını açır.",
                "Framework versiyası hücum üçün ipucu verir.",
                f"{acar} başlığını sil.", "basliq"))

    # CORS: hər mənbəyə açıq paylaşım
    aco = str(b.get("access-control-allow-origin", "")).strip()
    if aco == "*":
        kredensial = str(b.get("access-control-allow-credentials", "")).lower() == "true"
        tapintilar.append(_tapinti(
            "cors_aciq", "CORS hər mənbəyə açıqdır (*)",
            "yuksek" if kredensial else "orta",
            "Access-Control-Allow-Origin: * — istənilən sayt bu API-yə sorğu göndərə bilər."
            + (" Üstəlik Allow-Credentials: true — sessiya da paylaşılır." if kredensial else ""),
            "Zərərli sayt istifadəçinin adından məlumat oxuya bilər.",
            "Yalnız etibarlı mənbələrə icazə ver, «*» yerinə konkret domen yaz.", "basliq"))

    # Zəif CSP: unsafe-inline / unsafe-eval XSS müdafiəsini zəiflədir
    if csp and ("unsafe-inline" in csp or "unsafe-eval" in csp):
        tapintilar.append(_tapinti(
            "zeif_csp", "CSP zəifdir (unsafe-inline / unsafe-eval)", "orta",
            "CSP var, amma «unsafe-inline» və ya «unsafe-eval» icazəsi verir.",
            "Bu icazələr CSP-nin XSS-ə qarşı əsas faydasını aradan qaldırır.",
            "CSP-dən unsafe-inline/unsafe-eval-i çıxar, nonce və ya hash işlət.", "basliq"))

    # Zəif HSTS: müddət 6 aydan azdır
    hsts = str(b.get("strict-transport-security", ""))
    if hsts:
        m = re.search(r"max-age\s*=\s*(\d+)", hsts)
        if m and int(m.group(1)) < 15768000:  # ~6 ay
            tapintilar.append(_tapinti(
                "zeif_hsts", "HSTS müddəti çox qısadır", "asagi",
                f"HSTS var, amma max-age azdır ({m.group(1)} san).",
                "Qısa müddət HTTPS məcburiyyətini zəiflədir.",
                "max-age dəyərini ən azı 31536000 (1 il) et.", "basliq"))

    return tapintilar


def _cookie_tapintilari(b: dict, https: bool) -> list[dict]:
    xam = b.get("set-cookie")
    if not xam:
        return []
    metn = xam.lower()
    tapintilar = []
    if https and "secure" not in metn:
        tapintilar.append(_tapinti(
            "cookie_secure", "Cookie «Secure» bayrağı yoxdur", "orta",
            "Set-Cookie başlığında Secure yoxdur.",
            "Cookie şifrələnməmiş HTTP üzərindən oğurlana bilər.",
            "Cookie-yə «Secure» bayrağı əlavə et.", "cookie"))
    if "httponly" not in metn:
        tapintilar.append(_tapinti(
            "cookie_httponly", "Cookie «HttpOnly» bayrağı yoxdur", "orta",
            "Set-Cookie başlığında HttpOnly yoxdur.",
            "JavaScript (XSS) cookie-ni oxuya və sessiyanı oğurlaya bilər.",
            "Cookie-yə «HttpOnly» bayrağı əlavə et.", "cookie"))
    if "samesite" not in metn:
        tapintilar.append(_tapinti(
            "cookie_samesite", "Cookie «SameSite» bayrağı yoxdur", "asagi",
            "Set-Cookie başlığında SameSite yoxdur.",
            "CSRF (saxta sorğu) hücumuna qapı açıq qalır.",
            "Cookie-yə «SameSite=Lax» və ya «Strict» əlavə et.", "cookie"))
    return tapintilar


def _mezmun_tapintilari(url: str, html: str, https: bool) -> list[dict]:
    tapintilar = []
    # Qarışıq məzmun: HTTPS səhifədə http:// ilə yüklənən resurslar
    if https and html:
        qarisiq = re.findall(r'(?:src|href)\s*=\s*["\']http://[^"\']+', html, re.IGNORECASE)
        if qarisiq:
            tapintilar.append(_tapinti(
                "qarisiq_mezmun", f"Qarışıq məzmun: {len(qarisiq)} resurs http:// ilə yüklənir",
                "orta",
                f"HTTPS səhifədə {len(qarisiq)} resurs şifrələnməmiş http:// ilə çağırılır.",
                "Bu resurslar dəyişdirilə (MITM) bilər və brauzer «təhlükəsiz deyil» göstərir.",
                "Bütün resursları https:// (və ya protokolsuz //) ilə yüklə.", "html"))
    # Versiya sızması: generator meta
    if html:
        m = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)',
                      html, re.IGNORECASE)
        if m and re.search(r"\d", m.group(1)):
            tapintilar.append(_tapinti(
                "generator_versiya", f"Versiya açıqdır (generator): {m.group(1)}", "asagi",
                f"Səhifə «generator» meta ilə versiyanı açır: {m.group(1)}.",
                "Hücumçu həmin versiyanın məlum açıqlarını hədəfləyə bilər.",
                "generator meta teqindən versiyanı sil.", "html"))
        if re.search(r"<title>\s*Index of /", html, re.IGNORECASE):
            tapintilar.append(_tapinti(
                "qovluq_siyahisi", "Qovluq siyahılanması (directory listing) açıqdır", "orta",
                "Səhifə server qovluğunun fayl siyahısını göstərir.",
                "Gizli fayllar və struktur hücumçuya görünür.",
                "Serverdə «autoindex»/directory listing-i söndür.", "html"))

        # HTTP-yə göndərən forma (parol/məlumat şifrələnmədən gedir)
        if re.search(r'<form[^>]+action\s*=\s*["\']http://', html, re.IGNORECASE):
            tapintilar.append(_tapinti(
                "forma_http", "Forma məlumatı şifrələnmədən (http://) göndərir", "yuksek",
                "Səhifədə action-u http:// olan forma var.",
                "İstifadəçinin yazdığı parol/məlumat açıq mətnlə gedir və oğurlana bilər.",
                "Forma action-unu https:// et.", "html"))

        # HTML-də açıq sızan sirlər (API açarları, private key)
        for sirr_id, ad, naxis in SIRR_NAXISLARI:
            if re.search(naxis, html):
                tapintilar.append(_tapinti(
                    sirr_id, f"HTML-də açıq sirr: {ad}", "kritik",
                    f"Səhifə mənbəyində {ad} nümunəsi tapıldı.",
                    "Açıq açar/token oğurlanıb sui-istifadə oluna bilər.",
                    "Bu sirri koddan çıxar, dərhal ləğv edib yenisi ilə əvəz et.", "html"))
    return tapintilar


def _sertifikat_tapintilari(neticeler: dict | None) -> list[dict]:
    """Mövcud «sertifikat» toplayıcısının nəticəsindən istifadə edir (təkrar
    TLS əl-sıxması etmirik)."""
    if not neticeler:
        return []
    s = (neticeler.get("sertifikat") or {})
    data = s.get("data") or {}
    if not data:
        return []
    tapintilar = []
    qalan = data.get("qalan_gun")
    if isinstance(qalan, int):
        if qalan <= 0:
            tapintilar.append(_tapinti(
                "sert_bitib", "SSL sertifikatı bitib", "yuksek",
                "Sertifikatın etibarlılıq müddəti keçib.",
                "Brauzer «təhlükəsiz deyil» xəbərdarlığı göstərir, istifadəçilər qaçır.",
                "Sertifikatı dərhal yenilə (məs. Let's Encrypt avtomatik yeniləmə).", "sertifikat"))
        elif qalan <= 14:
            tapintilar.append(_tapinti(
                "sert_bitir", f"SSL sertifikatı {qalan} günə bitir", "orta",
                f"Sertifikatın bitməsinə {qalan} gün qalıb.",
                "Vaxtında yenilənməsə sayt əlçatmaz olacaq.",
                "Yeniləməni indidən planla (avtomatik yeniləmə qur).", "sertifikat"))
    protokol = str(data.get("protokol", ""))
    if protokol and re.search(r"TLSv1(\.[01])?$", protokol):
        tapintilar.append(_tapinti(
            "zeif_tls", f"Köhnə TLS protokolu: {protokol}", "orta",
            f"Server köhnə {protokol} protokolunu işlədir.",
            "Köhnə TLS versiyalarının məlum zəiflikləri var.",
            "Serverdə yalnız TLS 1.2 və 1.3-ə icazə ver.", "sertifikat"))
    return tapintilar


async def _fayl_yoxla(kok: str) -> list[dict]:
    """Həssas faylların açıq olub-olmadığını yoxlayır — yalnız imza uyğun
    gələndə tapıntı yaranır. Şəbəkə xətası səssizcə keçilir."""
    tapintilar: list[dict] = []

    async with httpx.AsyncClient(
        timeout=8, follow_redirects=False, verify=False, event_hooks=sebeke.HOOKLAR,
    ) as musteri:

        async def bir(yol, seviyye, imza, ad, risk, hell):
            try:
                cavab = await musteri.get(kok + yol)
            except Exception:
                return None
            if cavab.status_code == 200 and imza(cavab):
                return _tapinti(f"fayl{yol}", ad, seviyye,
                                f"«{yol}» ünvanı 200 qaytarır və məzmunu uyğundur.",
                                risk, hell, "fayl")
            return None

        neticeler = await asyncio.gather(*[bir(*y) for y in FAYL_YOXLAMALARI])

    return [t for t in neticeler if t]


# Qovluq siyahılanması üçün yoxlanan ümumi qovluqlar
QOVLUQLAR = ["/uploads/", "/images/", "/img/", "/files/", "/assets/", "/backup/", "/media/"]


async def _elave_probelar(kok: str, https: bool) -> list[dict]:
    """robots.txt sızması, security.txt yoxluğu, TRACE metodu, qovluq
    siyahılanması — hamısı passiv, paralel. Xəta səssizcə keçilir."""
    tapintilar: list[dict] = []

    async with httpx.AsyncClient(
        timeout=8, follow_redirects=False, verify=False, event_hooks=sebeke.HOOKLAR,
    ) as m:

        async def robots():
            try:
                c = await m.get(kok + "/robots.txt")
            except Exception:
                return
            if c.status_code != 200 or "<html" in c.text[:200].lower():
                return
            hessas = re.findall(r"(?im)^\s*Disallow:\s*(\S*(?:admin|login|private|backup|"
                                r"config|secret|panel|dashboard|wp-admin)\S*)", c.text)
            if hessas:
                nüm = ", ".join(dict.fromkeys(hessas))[:200]
                tapintilar.append(_tapinti(
                    "robots_sizma", "robots.txt həssas yolları açır", "asagi",
                    f"robots.txt gizli yolları göstərir: {nüm}",
                    "Hücumçu bu «gizli» qovluqları birbaşa yoxlaya bilər.",
                    "Həssas yolları robots.txt-dən çıxar; qorumanı giriş nəzarəti ilə et.",
                    "fayl"))

        async def security_txt():
            for yol in ("/.well-known/security.txt", "/security.txt"):
                try:
                    c = await m.get(kok + yol)
                    if c.status_code == 200 and "contact" in c.text[:500].lower():
                        return  # var — problem yoxdur
                except Exception:
                    pass
            tapintilar.append(_tapinti(
                "security_txt_yox", "security.txt yoxdur", "melumat",
                "«/.well-known/security.txt» tapılmadı.",
                "Təhlükəsizlik araşdırıcısının açıq bildirmək üçün rəsmi kanalı yoxdur.",
                "Bir security.txt əlavə et (əlaqə + siyasət) — yaxşı təcrübədir.", "fayl"))

        async def trace():
            try:
                c = await m.request("TRACE", kok + "/")
            except Exception:
                return
            govde = c.text[:200].lower()
            if c.status_code == 200 and "trace" in govde:
                tapintilar.append(_tapinti(
                    "trace_aciq", "TRACE metodu açıqdır", "asagi",
                    "Server TRACE sorğusuna cavab verir.",
                    "Cross-Site Tracing (XST) ilə başlıqlar/cookie oxuna bilər.",
                    "Serverdə TRACE metodunu söndür.", "metod"))

        async def qovluq(yol):
            try:
                c = await m.get(kok + yol)
            except Exception:
                return
            if c.status_code == 200 and re.search(r"<title>\s*Index of /", c.text, re.IGNORECASE):
                tapintilar.append(_tapinti(
                    f"listing{yol}", f"Qovluq siyahılanması açıqdır: {yol}", "orta",
                    f"«{yol}» qovluğunun fayl siyahısı görünür.",
                    "Gizli fayllar və struktur hücumçuya açılır.",
                    "Serverdə bu qovluq üçün autoindex-i söndür.", "fayl"))

        await asyncio.gather(robots(), security_txt(), trace(),
                             *[qovluq(y) for y in QOVLUQLAR])

    return tapintilar


async def _https_yonlendirme(kok: str, https: bool) -> list[dict]:
    """HTTP-nin HTTPS-ə yönləndirdiyini yoxlayır (yalnız sayt HTTPS-i
    dəstəkləyirsə mənalıdır)."""
    if not https:
        # Sayt ümumiyyətlə HTTP-dədir — bu, daha ciddidir
        return [_tapinti(
            "https_yox", "Sayt HTTPS işlətmir", "yuksek",
            "Ünvan http:// ilədir və şifrələmə yoxdur.",
            "Bütün məlumat (parollar daxil) açıq mətnlə gedir və oğurlana bilər.",
            "SSL sertifikatı qur (Let's Encrypt pulsuzdur) və HTTPS-ə keç.", "https")]
    host = urlparse(kok).hostname or ""
    try:
        async with httpx.AsyncClient(
            timeout=8, follow_redirects=True, verify=False, event_hooks=sebeke.HOOKLAR,
        ) as musteri:
            cavab = await musteri.get(f"http://{host}")
        if not str(cavab.url).lower().startswith("https"):
            return [_tapinti(
                "http_yonlenmir", "HTTP → HTTPS yönləndirmə yoxdur", "orta",
                "http:// ünvanı açılır və https-ə yönləndirmir.",
                "İstifadəçi təsadüfən şifrələnməmiş versiyada qala bilər.",
                "Serverdə bütün HTTP sorğularını HTTPS-ə 301 yönləndir.", "https")]
    except Exception:
        pass
    return []


def hesabla(tapintilar: list[dict]) -> dict:
    """Tapıntılardan bal, hərf və sayı hesablayır — deterministik, şəbəkəsiz.

    Ayrıca funksiyadır ki, həm `topla`, həm də test onu birbaşa çağıra bilsin.
    """
    sira = {"kritik": 0, "yuksek": 1, "orta": 2, "asagi": 3, "melumat": 4}
    tapintilar = sorted(tapintilar, key=lambda t: sira.get(t["seviyye"], 9))

    sayi = {s: 0 for s in CEZA}
    for t in tapintilar:
        sayi[t["seviyye"]] = sayi.get(t["seviyye"], 0) + 1

    bal = max(0, 100 - sum(CEZA.get(t["seviyye"], 0) for t in tapintilar))
    herf = ("A" if bal >= 90 else "B" if bal >= 75 else "C" if bal >= 60
            else "D" if bal >= 40 else "F")

    return {
        "bal": bal,
        "herf": herf,
        "tapintilar": tapintilar,
        "sayi": sayi,
        # Yoxlanan maddələr: başlıq + fayl + qovluq + sirr nümunələri + sabit
        # yoxlamalar (CORS, CSP, HSTS, cookie×3, qarışıq məzmun, forma, generator,
        # sertifikat×3, https, robots, security.txt, TRACE).
        "yoxlanan": (len(BASLIQ_YOXLAMALARI) + len(FAYL_YOXLAMALARI)
                     + len(QOVLUQLAR) + len(SIRR_NAXISLARI) + 18),
    }


@safe_collector("tehlukesizlik")
@timed
async def topla(url: str, html: str, basliqlar: dict, neticeler: dict | None = None) -> dict:
    """Passiv təhlükəsizlik auditini işlədir və tapıntı + bal qaytarır."""
    b = _tap(basliqlar)
    kok = kok_url(url)
    https = urlparse(url).scheme == "https"

    # Şəbəkə tələb edən yoxlamalar paralel
    fayl_isi = _fayl_yoxla(kok)
    elave_isi = _elave_probelar(kok, https)
    yonlendirme_isi = _https_yonlendirme(kok, https)

    tapintilar: list[dict] = []
    tapintilar += _basliq_tapintilari(b, https)
    tapintilar += _cookie_tapintilari(b, https)
    tapintilar += _mezmun_tapintilari(url, html or "", https)
    tapintilar += _sertifikat_tapintilari(neticeler)

    fayl_tap, elave_tap, yon_tap = await asyncio.gather(fayl_isi, elave_isi, yonlendirme_isi)
    tapintilar += fayl_tap
    tapintilar += elave_tap
    tapintilar += yon_tap

    return hesabla(tapintilar)
