# SaytLupa — Təhlükəsizlik Bölməsi (Dizayn / Spec)

> **Tarix:** 2026-08-05
> **Status:** Təsdiqlənib, planlaşdırmaya hazır
> **Müəllif:** Amil + Claude
> **Qovluq:** `D:\SaytLupa`

---

## 1. Məqsəd

SaytLupada yeni bir **🛡️ Təhlükəsizlik** bölməsi yaratmaq: istifadəçi saytını yoxlayır,
proqram **açıqları (təhlükəsizlik zəifliklərini)** göstərir və hər biri üçün **həll təklif edir**.

Bu, birinci mərhələdir (**Yol A — Passiv audit**). Sonra dərin/aktiv skana
(Strix və s.) genişlənəcək şəkildə qurulur.

**Bir cümlə ilə:** Saytını yoxla → açıqları gör → hər açığın həllini oxu.

---

## 2. Prinsiplər (dəyişməz)

- **Passiv və qanuni:** Yalnız GET/HEAD sorğuları — brauzerin/analizatorun onsuz da etdiyi.
  Heç bir istismar, injection payload, brute-force YOXDUR. İstənilən saytda qanunidir.
- **Uydurma yoxdur:** Açıq yalnız **həqiqətən təsdiqlənəndə** göstərilir
  (məs. fayl açıqdırsa — HTTP 200 **və** gözlənilən məzmun imzası olmalıdır, təkcə 200 kifayət deyil).
- **Bal riyazi hesablanır**, LLM ilə yox → rəqəm həmişə dürüstdür (PLAN.md prinsipi).
- **LLM yalnız izah edir**, yeni açıq uydurmur.
- **İzolyasiya:** `@safe_collector` — təhlükəsizlik toplayıcısı sınsa, qalan analiz davam edir.

---

## 3. Arxitektura (mövcud pattern-ə oturur)

SaytLupa collector-lər üzərində qurulub: hər yoxlama bir modul, hamısı paralel işləyir,
nəticələr `xam.neticeler[<ad>]`-də saxlanır, frontend "kart"larda göstərir.

### 3.1 Yeni collector — `backend/collectors/tehlukesizlik.py`

Mövcud toplayıcılarla eyni imza və dekoratorlar:

```python
@safe_collector("tehlukesizlik")
@timed
async def topla(url: str, html: str, basliqlar: dict) -> dict: ...
```

- HTML və cavab başlıqları **artıq** `butun_analiz`-də çəkilib — təkrar yükləmə yoxdur.
- Yalnız açıq-fayl yoxlaması üçün bir neçə əlavə qısa sorğu (whitelist, qısa timeout).
- `collectors/__init__.py` içində `HTML_TOPLAYICILAR`-a əlavə olunur (url+html+basliqlar alır),
  beləcə mövcud `asyncio.gather` axınında paralel işləyir və nəticə avtomatik saxlanır.

### 3.2 Yoxlamalar (yalnız passiv)

| # | Yoxlama | Mənbə | Nümunə tapıntı |
|---|---------|-------|----------------|
| 1 | Təhlükəsizlik başlıqları: CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy | `basliqlar` | "HSTS yoxdur" |
| 2 | Sızan başlıqlar: `Server` versiyası, `X-Powered-By`, `X-AspNet-Version` | `basliqlar` | "Server versiyası açıqdır: nginx/1.18.0" |
| 3 | Cookie bayraqları: Secure / HttpOnly / SameSite | `Set-Cookie` | "Cookie HttpOnly deyil" |
| 4 | HTTPS: sayt HTTPS-dədir? HTTP→HTTPS yönləndirir? | 1 əlavə sorğu (http://) | "HTTP HTTPS-ə yönləndirmir" |
| 5 | Sertifikat: bitib / tezliklə bitir / zəif protokol (TLS<1.2) | mövcud `sertifikat` nəticəsi | "Sertifikat 8 günə bitir" |
| 6 | Qarışıq məzmun (mixed content): HTTPS səhifədə `http://` resurslar | `html` | "5 resurs http:// ilə yüklənir" |
| 7 | Açıq həssas fayllar: `/.env`, `/.git/config`, `/.git/HEAD`, `/backup.sql`, `/phpinfo.php`, `/server-status`, `/.DS_Store` | əlavə GET (whitelist) | "/.env faylı açıqdır — KRİTİK" |
| 8 | Qovluq siyahılanması (Index of /) | əlavə GET / html | "Qovluq siyahılanması açıqdır" |
| 9 | Versiya sızması (CMS generator meta, məs. WordPress x.y) | `texnologiya`/html | "WordPress versiyası açıqdır" |

> Açıq-fayl whitelist-i qısa saxlanır (≈7-10 yol). Şəbəkə xətası ≠ tapıntı — səssizcə keçilir.

### 3.3 Tapıntı sxemi (ümumi — gələcək dərin skan da bunu işlədəcək)

```python
{
  "id": "hsts_yoxdur",
  "ad": "HSTS başlığı yoxdur",
  "seviyye": "orta",         # kritik | yuksek | orta | asagi | melumat
  "tapinti": "Strict-Transport-Security başlığı cavabda yoxdur.",
  "risk": "Brauzer HTTPS-i məcbur etmir; downgrade hücumu mümkündür.",
  "hell": "Serverə əlavə et: Strict-Transport-Security: max-age=31536000; includeSubDomains",
  "menbe": "basliq"          # basliq | cookie | fayl | html | sertifikat
}
```

### 3.4 Collector nəticəsi

```python
{
  "ugurlu": True,
  "bal": 72,                              # 0-100, riyazi
  "herf": "B",                            # A-F
  "tapintilar": [ {...}, ... ],           # səviyyəyə görə sıralı
  "sayi": {"kritik": 0, "yuksek": 1, "orta": 3, "asagi": 2, "melumat": 4},
  "yoxlanan": 24                          # neçə yoxlama edildi
}
```

**Bal düsturu (deterministik):** 100-dən başla, hər tapıntı üçün çıx:
kritik −40, yuksek −20, orta −10, asagi −4, melumat −0. Minimum 0.
Hərf: ≥90 A, ≥75 B, ≥60 C, ≥40 D, <40 F. (Dəqiq çəkilər plan mərhələsində sabitlənir.)

---

## 4. LLM qatı (könüllü, ucuz)

- Deterministik tapıntılar **onsuz da** `hell` (həll) mətni ilə gəlir — biz yazırıq, dəqiqdir.
- Əlavə: `chains/tehlukesizlik.py` — tapıntıları **Azərbaycanca sadə dildə xülasə** və
  **prioritet sıra** halına salır. LLM **yalnız verilən tapıntıları** izah edir, yenisini uydurmur.
- RAG söhbətinə də tapıntılar əlavə olunur ki, istifadəçi "açıqlarımı necə düzəldim?" soruşa bilsin.

---

## 5. API

1. **Tam analizin içində (avtomatik):** `POST /api/analyze` nəticəsində
   `xam.neticeler.tehlukesizlik` gəlir — heç bir yeni endpoint tələb etmir.
2. **Ayrıca sürətli düymə:** `POST /api/tehlukesizlik` — yalnız təhlükəsizlik toplayıcısını
   işlədir (tam crawl yox), URL alır, tapıntı+bal qaytarır. Sənin istədiyin müstəqil "bölmə".
   `dependencies=ACAR` ilə (mövcud yazma-endpointləri kimi qorunur).

---

## 6. Frontend

- `index.html`: yeni kart `#k-tehlukesizlik` — başlıq, **bal nişanı**, tapıntı siyahısı.
  Kartın içində müstəqil "🛡️ Təhlükəsizlik yoxla" düyməsi (ayrıca endpoint-i çağırır).
- `render.js`: `function tehlukesizlik(n)` — bal + rəngli səviyyə nişanları, hər tapıntı açılır
  (risk + həll görünür). Mövcud `qutu/setir/teqler` köməkçiləri işlədilir.
- `app.js`: düymə hadisəsi + kartın göstərilməsi (mövcud kart-göstərmə pattern-i).
- Söhbət konteksti: təhlükəsizlik tapıntıları RAG cavabına daxil edilir.

---

## 7. Testlər (`tests/`)

Mövcud pytest quruluşu ilə eyni. Hər yoxlama izolyasiyada:

- Başlıq yoxdursa → tapıntı yaranır; düzgün başlıq varsa → tapıntı yoxdur.
- Cookie `HttpOnly` yoxdursa → tapıntı.
- Bal düsturu: verilən tapıntı dəstinə görə bal & hərf düz gəlir.
- Açıq fayl: 200 **və** imza → tapıntı; təkcə 200 (məs. custom 404 səhifəsi) → tapıntı YOX.
- Qarışıq məzmun: HTTPS html-də http:// resurs → tapıntı.

---

## 8. Xəta idarəetməsi

- `@safe_collector` bütün toplayıcını izolə edir.
- Açıq-fayl sorğuları: qısa timeout, kiçik whitelist, şəbəkə xətası səssizcə keçilir.
- Heç vaxt təsdiqlənməmiş açıq göstərilmir (yuxarıdakı imza qaydası).

---

## 9. Gələcəyə körpü (dərin/aktiv skan)

Tapıntı sxemi, səviyyə və bal ümumidir. Sonrakı mərhələdə "Dərin skan" rejimi
(Strix və ya ayrıca serverdə aktiv skaner, yalnız təsdiqlənmiş öz saytlarına)
**eyni sxemdə** tapıntı verəcək və elə bu UI/hesabat/söhbətə düşəcək.
Yəni indi qurduğumuz — həmin gələcəyin təməlidir.

---

## 10. Əhatədən kənar (bu mərhələdə YOX)

- Aktiv istismar, injection/XSS/SQLi payload göndərmək.
- Sahiblik təsdiqi (DNS TXT) axını — dərin skan mərhələsinə aiddir.
- Strix Docker inteqrasiyası, ayrıca skan serveri.
