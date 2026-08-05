# SaytLupa — Aktiv (Dərin) Təhlükəsizlik Skanı (Dizayn / Spec)

> **Tarix:** 2026-08-05
> **Status:** Təsdiqlənib (3 qərar tövsiyə variantı ilə), planlaşdırmaya hazır
> **Müəllif:** Amil + Claude
> **Qovluq:** `D:\SaytLupa`
> **Öncəki mərhələ:** passiv audit — `2026-08-05-tehlukesizlik-bolmesi-design.md`

---

## 1. Məqsəd

Passiv audit "kənardan baxır" (başlıqlar, açıq fayllar). **Aktiv skan** real payload
göndərib "qapını sınayır" (XSS, SQLi, CVE, açıq panellər və s.). Bu, hüquqi cəhətdən
yalnız **sahibi olduğun** saytlarda edilə bilər — ona görə mərkəzi şərt **sahiblik
təsdiqidir**.

**Bir cümlə ilə:** Domenini bir dəfə təsdiqlə → "🔬 Dərin aktiv skan" düyməsi açılır →
nuclei ilə real skan → tapıntılar (sübut + CVE + həll) eyni təhlükəsizlik kartında.

---

## 2. Prinsiplər (dəyişməz)

- **Yalnız təsdiqlənmiş domen.** Təsdiqlənməyən domendə düymə sönülüdür, API 403 verir.
- **Açıq razılıq.** Hər skandan əvvəl "bu sayt mənimdir, skana icazə verirəm" qutusu.
- **Əhatə məhdud.** Yalnız hədəf domen daxilində qalır (kənar hostlara getmir), maksimum
  müddət limiti, dayandırma düyməsi, sürət məhdudiyyəti (rate-limit).
- **Eyni finding sxemi.** Aktiv tapıntılar passiv tapıntılarla eyni formatda + `menbe:
  "aktiv"` + `subut` (PoC) + `sablon`/`istinad` (CVE). Elə həmin kartda görünür.
- **Ucuz və deterministik.** Əsas motor nuclei — LLM yox. (Strix/AI rejimi sonra, könüllü.)
- **Müdafiə dərinliyi.** Sahiblik həm API-də, həm də worker-də təkrar yoxlanır.

---

## 3. Üç qərar (təsdiqlənmiş)

1. **Sahiblik:** DNS TXT (`saytlupa-verify=<token>`) + `.env`-də öz domenlərinin allowlist-i.
   (Alternativ fayl-token da dəstəklənir.)
2. **Motor:** **nuclei** (ProjectDiscovery) — əsas. Strix "AI dərin" rejimi sonrakı mərhələ.
3. **Worker yeri:** əvvəl **öz kompüterində** (on-demand), sonra istəsə Railway daimi worker.

---

## 4. Arxitektura

```
Brauzer ──POST /api/aktiv-skan──► FastAPI (Railway)
                                    │  job "gozleyir" (DB növbəsi)
                                    │
Öz kompüterin: aktiv_worker.py ─────┤  GET /novbe (claim) → job götürür
   │  domen təsdiqini TƏKRAR yoxla   │
   │  nuclei -u <url> -jsonl ...     │
   │  hər tapıntı → schema           │
   └──POST /gedisat + /netice───────►│  DB-yə yazır, SSE ilə canlı göstərir
                                    ▼
Brauzer ◄──SSE /axin──── gedişat + matrix ──► təhlükəsizlik kartı (aktiv nişanı)
```

### 4.1 Sahiblik təsdiqi — `backend/sahiblik.py`

- **Token yaratma:** istifadəçi domen yazır → API təsadüfi `token` yaradır, DB-yə
  `gozleyir` kimi yazır, təlimat qaytarır:
  > DNS TXT əlavə et: `saytlupa-verify=<token>` — və ya `/.well-known/saytlupa-verify.txt`
  > faylına həmin token-i qoy.
- **Yoxlama:** "Yoxla" → API DNS TXT sorğusu edir (`dnspython`, artıq layihədə var) və ya
  faylı çəkir → token uyğundursa `verified_at` qoyulur, domen **təsdiqlənmiş** olur.
- **Allowlist:** `.env`-də `OWNED_DOMAINS=malqara.az,oazis-sifaris...,saytlupa...` — bunlar
  öz domenlərin, avtomatik təsdiqlənmiş sayılır (sənin üçün dərhal açıq).
- **`domen_tesdiqlidir(domain) -> bool`** — həm API endpoint-ləri, həm də worker bunu çağırır.

### 4.2 Skan işi (job) — `backend/aktiv.py`

- **Yaratma:** `POST /api/aktiv-skan {url, razilioq: true}` (ACAR + domen təsdiqli olmalı,
  yoxsa 403) → DB-də `aktiv_skan` sətri `gozleyir`, `job_id` qaytarır.
- **Növbə/claim:** `GET /api/aktiv-skan/novbe` (worker açarla çağırır) → ən köhnə `gozleyir`
  işi `isleyir`-ə keçirib qaytarır (atomik — iki worker eyni işi götürməsin).
- **Gedişat:** worker `POST /api/aktiv-skan/{id}/gedisat {mesaj, faiz}` → mövcud `hadise`
  modulu ilə SSE-yə ötürülür (analizlə eyni mexanizm).
- **Nəticə:** worker `POST /api/aktiv-skan/{id}/netice {tapintilar, bal, herf}` → DB-yə
  yazılır, iş `bitdi` olur.
- **Vəziyyət/dayandırma:** `GET /api/aktiv-skan/{id}`, `POST /api/aktiv-skan/{id}/dayandir`
  (işi `dayandirildi` işarələyir; worker növbəti yoxlamada dayanır).
- **Axın:** `GET /api/aktiv-skan/{id}/axin` — SSE (analizdəki `axin` ilə eyni nümunə).

### 4.3 Worker — `scripts/aktiv_worker.py` (öz kompüterində)

```
py scripts/aktiv_worker.py           # dövrə: növbəni yoxla → iş götür → skan et → bildir
```

Addımlar:
1. `GET /novbe` ilə iş götürür (API açarı ilə).
2. **Domen təsdiqini TƏKRAR yoxlayır** (`domen_tesdiqlidir`) — müdafiə dərinliyi.
3. nuclei-ni işə salır:
   ```
   nuclei -u <url> -jsonl -o -                     \
     -severity critical,high,medium,low,info       \
     -rate-limit 50 -timeout 10 -retries 1         \
     -scope-file <yalnız hədəf domen>              \
     -no-interactsh            # kənar xidmətə asılılıq olmasın (opsional)
   ```
   Vaxt limiti bir "wrapper" ilə (məs. 15 dəq) — keçsə proses öldürülür.
4. Hər JSONL sətrini `nuclei_parse.py` ilə **finding sxeminə** çevirir.
5. Ara-ara `POST /gedisat` (neçə şablon işlədi, neçə tapıntı), sonda `POST /netice`.

> nuclei **ikili fayldır** (Go) — Windows-da Docker olmadan işləyir. Şablonlar
> `nuclei -update-templates` ilə yenilənir.

### 4.4 nuclei → finding sxemi — `backend/nuclei_parse.py`

Ortaq modul (həm worker, həm test import edir). Uyğunlaşma:

| Finding sahəsi | nuclei mənbəyi |
|---|---|
| `seviyye` | `info.severity`: critical→kritik, high→yuksek, medium→orta, low→asagi, info→melumat |
| `ad` | `info.name` |
| `tapinti` | `matched-at` (harada tapıldı) |
| `risk` | `info.description` |
| `hell` | `info.remediation` (yoxdursa ümumi mətn) |
| `subut` | `matched-at` + `extracted-results` (PoC/dəlil) |
| `sablon` | `template-id` |
| `istinad` | `info.reference` + `info.classification.cve-id` |
| `menbe` | sabit `"aktiv"` |

Bal: passivdəki eyni `hesabla()` funksiyası (deterministik, A–F).

### 4.5 Verilənlər bazası — `backend/db.py`

- `tesdiq_domenler(id, domain, token, method, status, verified_at)`
- `aktiv_skan(id, domain, target_url, status, started_at, finished_at, netice_json,
  bal, herf, progress)`

---

## 5. Frontend

- **Sahiblik paneli** (təhlükəsizlik kartının içində, kiçik bölmə):
  domen yaz → "Token al" → təlimat (DNS TXT / fayl) → "Yoxla". Təsdiqlənəndə yaşıl nişan.
- **"🔬 Dərin (aktiv) skan" düyməsi:** yalnız cari URL-in domeni təsdiqlidirsə **aktiv**;
  deyilsə sönülü + "əvvəlcə domeni təsdiqlə" izahı.
- **Razılıq qutusu:** skandan əvvəl "bu sayt mənimdir, aktiv skana icazə verirəm".
- **Gedişat:** matrix + `⏳ Gedişat` paneli (bu dəfə **real SSE**, uzunmüddətli:
  "nuclei başladı → 320 şablon → tapıntı: SQLi ..."), **Dayandır** düyməsi.
- **Nəticələr:** eyni təhlükəsizlik kartında, aktiv tapıntılarda **🔬 aktiv** nişanı +
  `subut` (PoC) + CVE/istinad linki. Passiv və aktiv yan-yana görünür.

---

## 6. Təhlükəsizlik və hüquqi qorunma

- Aktiv skan **yalnız təsdiqlənmiş domenə** — API 403, düymə sönülü, worker təkrar yoxlayır.
- Açıq razılıq hər dəfə. Skan yalnız hədəf domen daxilində (scope). Müddət + rate limit.
- `sebeke.py` SSRF yoxlaması saxlanılır (daxili ünvanlar rədd).
- Nəticələr yalnız açar sahibinə (ACAR) görünür.

---

## 7. Testlər

- `nuclei_parse.py`: nümunə JSONL sətirləri → düz finding sxeminə çevrilir (severity
  uyğunluğu, sübut, CVE). Şəbəkəsiz.
- `sahiblik.py`: token yaratma; DNS TXT/fayl uyğun gələndə təsdiq, gəlməyəndə rədd;
  allowlist domeni avtomatik təsdiqli (mock DNS).
- `aktiv.py`: iş yaratma yalnız təsdiqli domendə (403 testi), növbə claim atomikliyi,
  dayandırma vəziyyəti.
- Bal: passivdəki `hesabla` təkrar istifadə (artıq test olunub).

---

## 8. Mərhələlər (implementasiya sırası)

1. **Sahiblik:** `sahiblik.py` + DB cədvəli + allowlist + verify endpoint + UI panel.
2. **Skan boru xətti:** `aktiv.py` (job/novbe/gedisat/netice) + `nuclei_parse.py` +
   `scripts/aktiv_worker.py` (lokal).
3. **UI:** aktiv skan düyməsi (təsdiqə bağlı) + razılıq + real SSE gedişat + aktiv
   tapıntıların göstərilməsi.
4. **Cilalama:** dayandırma, müddət limiti, şablon seçimi (məs. yalnız critical/high).

---

## 9. Gələcək / könüllü (bu spec-dən kənar)

- **Strix "AI dərin" rejimi:** Docker + LLM açarı ilə avtonom exploit + PoC zənciri.
  Eyni job/worker/finding sxeminə oturacaq — sadəcə "motor = strix" seçimi. Pullu, yavaş,
  ona görə ayrıca, könüllü rejim.
- **OWASP ZAP** əlavə motor kimi (dərin DAST).
- Railway-də daimi worker (lokal kompüter əvəzinə).

---

## 10. Əhatədən kənar (bu mərhələdə YOX)

- Təsdiqlənməyən / başqasının saytını skan etmək — heç bir halda.
- Avtomatik exploit icrası (yalnız aşkarlama + PoC, dağıdıcı əməliyyat yox).
- Strix inteqrasiyası (9-cu bənd — sonrakı könüllü mərhələ).
