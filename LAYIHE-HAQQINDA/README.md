# SaytLupa 🔍 — Layihə haqqında

> **Bir cümlə ilə:** Link yaz → saytı tanı → saytla danış → daha yaxşısını qur.

---

## 📌 İDEYANIN BAZASI

**SaytLupa** istənilən veb-saytın linkini alıb o sayt haqqında **hərtərəfli hesabat**
hazırlayan, sonra həmin saytın **məzmunu ilə söhbət etməyə** imkan verən və nəhayət
saytın **daha müasir versiyasını qurduran** analiz agentidir.

İş üç mərhələdən ibarətdir:

1. **Texniki analiz** — proqram saytı özü ölçür: domenin yaşı, hansı texnologiya ilə
   qurulub, serveri harada yerləşir, SSL sertifikatı nə vaxt bitir, sürəti necədir,
   hansı reklam və analitika alətləri işlədir, rəng palitrası və şriftləri hansılardır.
2. **AI hesabat** — toplanan xam məlumat Claude-a verilir və o, insan dilində altı suala
   cavab yazır: saytın məqsədi nədir, hədəf auditoriyası kimdir, hansı texnologiyalar
   işlədilib və niyə, performans problemləri nədir, SEO çatışmazlıqları nədir, daha
   müasir versiya necə görünə bilər.
3. **Saytla söhbət (RAG)** — sistem saytın 20-30 səhifəsini gəzib mətnini yığır, hissələrə
   bölür, vektor bazasına yazır. Sonra istifadəçi sadə dildə sual verir — *"Çatdırılma neçə
   gün çəkir?"* — və cavabı **hansı səhifədən götürüldüyünü göstərməklə** alır.

Sonda üç düymə var: **müasir versiyanı qur** (Claude yeni səhifə yazır), **tam klon üçün
hazırla** (`ai-website-cloner` üçün lazım olan sənədləri avtomatik yazır), **səhifə arşivi**.

### Həll etdiyi problem

Bir sayta kənardan baxanda görünən şey yalnız dizayndır. Onun **necə qurulduğu**, **nə
qədər sürətli olduğu**, **hansı zəif nöqtələri olduğu** və **içindəki məlumat** görünmür.
Bunu əl ilə öyrənmək üçün adam WHOIS sorğusu etməli, DNS-ə baxmalı, HTML-i açıb
oxumalı, PageSpeed işə salmalı, sonra saytın onlarla səhifəsini gəzib məlumat axtarmalıdır —
bu, bir mütəxəssis üçün **1-2 saatlıq** işdir.

SaytLupa həmin işi **3-15 saniyəyə** görür və üstünə iki şey əlavə edir ki, əl ilə ümumiyyətlə
alınmır: saytın məzmunu ilə **danışıq**, və qüsurların **həllini kod şəklində**.

### Kim istifadə edir

| İstifadəçi | Nə üçün |
|---|---|
| **Sahibkar** | Rəqib saytını öyrənmək: nə təklif edir, qiymətləri nədir, hansı platformada qurulub |
| **Sayt sifariş edən** | Bazara baxmaq: bəyəndiyi saytlar necə qurulub, öz saytı nə qədər tutacaq |
| **Sayt sahibi** | Öz saytının zəif nöqtələrini görmək — sürət, SEO, mobil uyğunluq |
| **Developer / dizayner** | İlham və texniki araşdırma: dizayn token-ləri, texnologiya seçimi |
| **Marketoloq** | Rəqibin hansı reklam və analitika alətlərindən istifadə etdiyini görmək |

### Niyə bu layihə seçildi

Kursun bu ayki əsas mövzuları **RAG + Memory**, **LangChain/LCEL**, **n8n production
naxışları**, **MCP** və **açıq model (Gemma)** idi. Bu mövzuların hamısını **süni şəkildə
yapışdırılmış demo** kimi yox, **məcburi ehtiyac** kimi tələb edən bir layihə lazım idi:

- Saytın 30 səhifəsindən sual cavablandırmaq → **RAG olmadan mümkün deyil**
- Rəqib saytını hər gün yoxlayıb dəyişiklik olanda xəbər vermək → **n8n cron + retry + error workflow**
- 20 namizəd parçanı ucuz qiymətləndirmək → **açıq model (Gemma) üçün real iş**
- Analiz zəncirini modeldən asılı olmadan qurmaq → **LCEL və fallback zənciri**
- Bu alətdən Claude Code / Cursor daxilində istifadə etmək → **MCP**

---

## 🏗 NECƏ İŞLƏYİR (axın)

```
   İstifadəçi:  https://numune-sayt.com   [Analiz et]
        │
        ▼
   ┌──────────────────────── FastAPI ────────────────────────┐
   │                                                          │
   │  1) Səhifə BİR DƏFƏ yüklənir (vaxt ölçülür)             │
   │     └─ bot qoruması yoxlanılır (Cloudflare və s.)        │
   │                                                          │
   │  2) 9 toplayıcı PARALEL işləyir                          │
   │     domen · dns · geo · sertifikat                       │
   │     səhifə · texnologiya · dizayn · reklam · sürət       │
   │     (biri sınsa digərləri davam edir)                    │
   │                                                          │
   │  3) Crawler: robots.txt → sitemap.xml → daxili linklər   │
   │     20-30 səhifə yığılır, mətn təmizlənir                │
   │                                                          │
   │  4) RAG: chunking → embedding → pgvector                 │
   │                                                          │
   │  5) LCEL zənciri: xam analiz → Claude → 6 bəndlik hesabat│
   └──────────────────────────────────────────────────────────┘
        │                          │                    │
        ▼                          ▼                    ▼
   PostgreSQL               Redis (keş)          Ollama (Gemma)
   + pgvector                                    re-ranking
        ▲
        │
   ┌────┴─────┐          ┌──────────────┐
   │   n8n    │          │ MCP serveri  │◄── Claude Code / Cursor
   │ izləmə,  │          └──────────────┘
   │ retry,   │
   │ Telegram │
   └──────────┘
```

Gedişat brauzerə **SSE (Server-Sent Events)** ilə canlı ötürülür — istifadəçi hansı
toplayıcının işlədiyini və neçənci səhifənin yığıldığını real vaxtda görür.

---

## 🚀 İNKİŞAF İSTİQAMƏTLƏRİ

**v1 (bu layihə)** — 9 analiz toplayıcısı, bot qoruması aşkarlanması, robots.txt-ə hörmət
edən crawler, RAG ilə saytla söhbət (mənbə göstərməklə), Claude ilə 6 bəndlik AI hesabat,
Gemma ilə lokal re-ranking, n8n ilə rəqib izləmə və xəbərdarlıq, MCP serveri, PDF hesabat,
müasir versiya qurucusu.

**v2** — bir neçə saytın yan-yana müqayisə səhifəsi; analiz tarixçəsi və dəyişiklik qrafiki
("bu sayt 3 ay əvvəl WordPress idi, indi Next.js-dir"); Playwright ilə JavaScript-lə qurulan
saytların (SPA) düzgün oxunması; çoxdilli interfeys (rus, ingilis).

**v3** — onlayn yerləşdirmə və istifadəçi hesabları; kredit/abunə modeli (Trading Analyzer
və Kontent Studiyası ilə eyni kommersiya sxemi); pullu API-lərlə (SimilarWeb) real trafik;
komanda üçün ortaq iş sahəsi.

---

## 🛠 TEXNOLOGİYA XƏRİTƏSİ

| Texnologiya | Rolu (nə üçün) |
|---|---|
| **Python 3.14** | Layihənin əsas dili — bütün backend məntiqi |
| **FastAPI** | HTTP API, SSE axını, WebSocket (söhbət) |
| **Pydantic** | API giriş/çıxış məlumatının tipini və doğruluğunu yoxlamaq |
| **SQLAlchemy** | Verilənlər bazası ilə OOP (ORM) şəklində işləmək |
| **PostgreSQL + psycopg2** | Əsas verilənlər bazası |
| **pgvector** | Embedding-lərin saxlanması və vektor oxşarlıq axtarışı (HNSW indeks) |
| **SQLite** | Postgres yoxdursa avtomatik ehtiyat baza |
| **Redis** | Analiz nəticələrinin və embedding-lərin keşlənməsi |
| **LangChain + LCEL** | Zəncir dizaynı: prompt → model → parser, provayder fallback-ı |
| **Claude (Anthropic API)** | AI hesabat, RAG cavabları, müasir versiya kodu |
| **Gemini API** | Embedding (`text-embedding-004`) və ehtiyat mətn modeli |
| **Gemma 3 4B (Ollama)** | Lokal, pulsuz re-ranking və n8n agenti — ölçmə ilə seçilib |
| **httpx** | Asinxron HTTP — bütün xarici sorğular |
| **BeautifulSoup + lxml** | HTML təhlili, mətn çıxarma |
| **dnspython** | DNS qeydləri (A, MX, NS, TXT, CNAME) |
| **RDAP / xam WHOIS (TCP 43)** | Domen yaşı və qeydiyyatçı |
| **Wayback Machine API** | WHOIS-u olmayan domenlər üçün (`.az`) təxmini yaş |
| **ip-api.com** | Serverin ölkəsi, şəhəri, provayderi |
| **Google PageSpeed Insights** | Rəsmi performans balı və Core Web Vitals |
| **ssl / socket (stdlib)** | SSL sertifikatının oxunması |
| **urllib.robotparser** | `robots.txt` qaydalarına hörmət |
| **SSE (sse-starlette)** | Canlı gedişatın brauzerə ötürülməsi |
| **n8n** | Cron izləmə, retry, error workflow, Telegram bildirişi |
| **MCP (Model Context Protocol)** | Alətin Claude Code / Cursor-a tool kimi verilməsi |
| **Docker + docker-compose** | Postgres, Redis, n8n mühitinin qaldırılması (profillərlə) |
| **ReportLab** | PDF hesabatın hazırlanması |
| **HTML / CSS / JavaScript** | İnterfeys (vanilla JS, EventSource, WebSocket) |
| **pytest** | Avtomatlaşdırılmış testlər |

---

## 👷 ƏVƏZ OLUNAN İXTİSAS

Bu layihə real dünyada **veb-analitik / texniki auditor** işinin böyük hissəsini əvəz edir.
Adətən bir sayt haqqında hesabat hazırlamaq üçün mütəxəssis:

1. WHOIS və DNS sorğuları edir
2. Brauzerin DevTools-u ilə texnologiyaları müəyyənləşdirir
3. PageSpeed işə salır və nəticəni şərh edir
4. Səhifələri gəzib məzmunu oxuyur
5. Tapıntıları hesabata çevirir və tövsiyələr yazır

SaytLupa 1-4 addımları **tam avtomatlaşdırır**, 5-ci addımı isə AI ilə hazırlayır.
Ayrıca **rəqib izləmə** (n8n ilə hər gün yoxlama və dəyişiklikdə xəbərdarlıq) hissəsi
insanın ümumiyyətlə davamlı edə bilmədiyi işdir.

**Tam əvəz etmir:** biznes kontekstini qiymətləndirmək, hüquqi məsələlər, dizayn zövqü
haqqında son qərar — bunlar insanda qalır. Alət **məlumat toplayır və variant təklif edir**,
qərarı sahibkar verir.

---

## ⚖️ ETİK VƏ HÜQUQİ ÇƏRÇİVƏ

Bu alət **öyrənmək, analiz və ilham** üçündür. Layihəyə aşağıdakı məhdudiyyətlər
**koda yazılıb**, sadəcə sənəddə vəd edilməyib:

| Qayda | Harada tətbiq olunur |
|---|---|
| `robots.txt`-ə hörmət — icazə verilməyən ünvan açılmır | `crawler.py` → `urllib.robotparser` |
| Sorğu tezliyi məhdudlaşdırılır (4 paralel, 0.25 san fasilə) | `crawler.py` → `Semaphore`, `asyncio.sleep` |
| Səhifə sayı limitlidir (standart 30) | `config.py` → `MAX_PAGES` |
| İdarə panelləri, səbət, giriş səhifələri gəzilmir | `crawler.py` → `ATILAN_YOLLAR` |
| Bot qoruması olan sayt **zorla açılmır**, dürüst bildirilir | `collectors/qoruma.py` |
| Uydurma rəqəm yazılmır — dəqiq olmayan məlumat "təxmini" işarələnir | `collectors/domen.py` (Wayback ipucusu) |
| Arşiv yalnız lokal qovluğa yazılır, paylaşılmır | `storage/archives/` |

**İstifadə edilmir:** fişinq və saxta sayt qurmaq, başqasının brendini öz adına çıxarmaq,
müəllif hüququnu pozmaq, saytların istifadə şərtlərini pozmaq.

---

## 📊 HAZIRKI VƏZİYYƏT

> Son yenilənmə: **2026-07-30** · 174 test keçir · ~7 400 sətir kod

| Gün | İş | Vəziyyət |
|---|---|---|
| 1 | Skelet: FastAPI, Pydantic, SQLAlchemy, Redis, Docker, 4 dekorator | ✅ hazır |
| 2-3 | 9 analiz toplayıcısı + bot qoruması aşkarlanması | ✅ hazır |
| 4 | Crawler (robots.txt + sitemap + BFS), mətn çıxarma, SSE canlı gedişat | ✅ hazır |
| 5-6 | **RAG**: chunking, embedding, pgvector, hibrid axtarış, re-ranking, yaddaş | ✅ hazır |
| 7 | **LangChain / LCEL** zəncirləri + promptlar | ✅ hazır |
| 8 | Nəticə səhifəsi, qrafiklər, söhbət interfeysi | ✅ hazır |
| 9 | 4 düymə: müasir versiya, klon hazırlığı, arşiv, PDF | ✅ hazır |
| 10 | **n8n**: 4 workflow + sayt izləmə xidməti | ✅ hazır |
| 11 | **MCP** serveri (3 tool) + sayt müqayisəsi | ✅ hazır |
| 12 | Sənədləşdirmə və cilalama | ✅ hazır |

**Ölçülmüş nəticələr (hazırkı hissə üzrə):**

| Göstərici | Dəyər |
|---|---|
| Tam analiz + 12 səhifə gəzişi | **3.2 saniyə** (`asan.gov.az`) |
| Toplayıcıların paralel icrası | **1.2 saniyə** (9 toplayıcı) |
| Uğurlu toplayıcı nisbəti | 9/9 (qorunmayan saytda) |
| RAG indeksi (15 səhifə → 60 chunk) | **4.1 saniyə** |
| RAG axtarış dəqiqliyi (10 sual, Gemini embedding) | Hit@1 **8/10** · Hit@3 **10/10** · MRR **0.90** |
| Eyni + Gemini re-ranking | Hit@1 **10/10** · Hit@3 10/10 · MRR **1.00** (+5.5 san) |
| Təkrar analizdə RAG (keşlə) | **0.9 saniyə** (4.1 → 0.9) |
| AI hesabat (gemini-3.6-flash) | **19.3 saniyə** |
| RAG söhbət cavabı | **14.5 saniyə** (re-ranking ilə ~25 san) |
| Müasir versiya (tək fayllıq HTML) | **78.6 saniyə** · 51 KB |
| İzləmə yoxlaması (30 səhifə, dəyişiklik yoxdur) | **11.4 saniyə** (`asan.gov.az`) |
| Sayt müqayisəsi (`/api/muqayise`, hazır analizlər) | **2.4 saniyə** |
| Gemma təsnifatı (n8n WF4, `gemma3:4b`) | **41.8 san** (soyuq) → **14.2 san** (model yaddaşda) |
| Testlər | **174 keçir** |
| Kod həcmi | ~7 400 sətir (backend + interfeys) · ayrıca ~2 300 sətir test və skript |
| İnterfeys | 11 bölmə · açıq/qaranlıq rejim · mobil uyğun (yatay sürüşmə yoxdur) |

> **İzləmə rəqəmi haqqında:** 11.4 saniyə — dəyişiklik **tapılmayan** haldır.
> Dəyişiklik olanda üstünə RAG indeksinin yenidən qurulması əlavə olunur.
>
> **Gemma təsnifatı haqqında:** 41.8 → 14.2 saniyə fərqi modelin yaddaşa
> yüklənməsindəndir. Bu maşında 7.8 GB RAM var, model tez-tez yaddaşdan düşür.

> Qeyd: 28 iyul ölçməsi lokal hashing embedding ilə idi (Hit@1 6/10, MRR 0.70).
> Yuxarıdakı rəqəmlər 29 iyulda Gemini embedding ilə alınıb — korpus 15 yerinə
> 20 səhifədir, ona görə müqayisə **istiqamət göstərir**, dəqiq nəzarətli deyil.

---

## 🖼 EKRAN GÖRÜNTÜLƏRİ

Hamısı `asan.gov.az` üzərində, işləyən sistemdən alınıb — `docs/ekran/`:

| Fayl | Nə görünür |
|---|---|
| [`01-ana-sehife.png`](../docs/ekran/01-ana-sehife.png) | Başlanğıc ekranı, sistem vəziyyəti (baza, keş, üç model) |
| [`02-gedisat.png`](../docs/ekran/02-gedisat.png) | Canlı gedişat (SSE) — RAG indeksi 30/30 səhifə, 104 parça |
| [`03-umumi-baxis.png`](../docs/ekran/03-umumi-baxis.png) | Ümumi baxış kartları |
| [`04-ai-hesabat.png`](../docs/ekran/04-ai-hesabat.png) | AI hesabatın 6 bəndi |
| [`05-tehvil-duymeleri.png`](../docs/ekran/05-tehvil-duymeleri.png) | 5 düymə; sayt izləndiyi üçün sonuncusu "🔕 İzləməni dayandır" |
| [`06-performans.png`](../docs/ekran/06-performans.png) | Performans zolaqları |
| [`07-dizayn.png`](../docs/ekran/07-dizayn.png) | Rəng palitrası və şriftlər |
| [`08-sohbet-rag.png`](../docs/ekran/08-sohbet-rag.png) | RAG cavabı + 5 mənbə + ölçmə sətri (12 namizəd → 5 seçildi, 21.7 san) |
| [`09-muasir-versiya.png`](../docs/ekran/09-muasir-versiya.png) | ⚡ Claude-un qurduğu müasir versiya |

> n8n canvas-ları və Telegram bildirişi bu siyahıda yoxdur — onlar brauzer
> sessiyasından kənardadır və əl ilə çəkilməlidir.

---

## 📂 SƏNƏDLƏR

| Fayl | Nə var |
|---|---|
| [`TEXNOLOGIYALAR.md`](TEXNOLOGIYALAR.md) | Hansı kurs mövzusu hansı faylda tətbiq olunub |
| [`MEMARLIQ.md`](MEMARLIQ.md) | Modul quruluşu, verilənlər bazası, axınlar |
| [`QERARLAR.md`](QERARLAR.md) | Qərarlar və səbəbləri — ölçmə nəticələri ilə |
| [`ISTIFADE.md`](ISTIFADE.md) | Qurulma, işə salma və nümayiş ssenarisi |
| [`../docs/model-secimi.md`](../docs/model-secimi.md) | Model müqayisəsi (Gemma 1b / 4b / 12b) |
| [`../docs/specs/`](../docs/specs/) | İlkin dizayn sənədi |
