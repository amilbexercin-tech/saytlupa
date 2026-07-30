# SaytLupa — Sayt Analiz və Söhbət Agenti (Dizayn Sənədi)

> **Tarix:** 2026-07-28
> **Müəllif:** Amil + Claude
> **Məqsəd:** AI Engineering kursunun aylıq layihəsi
> **Qovluq:** `D:\SaytLupa`
> **Status:** Dizayn təsdiqi gözlənilir

---

## 1. Layihə nədir?

Link yazırsan → proqram saytı hərtərəfli analiz edir → AI peşəkar hesabat yazır →
saytın məzmunu ilə **söhbət edirsən** (mənbə göstərməklə) → istəsən saytın
**müasir versiyasını qurdurursan** və ya tam klon üçün hazırlıq alırsan.

Bir cümlə ilə:
> **Link yaz → saytı tanı → saytla danış → daha yaxşısını qur.**

### Kim üçün
- Rəqib saytını öyrənmək istəyən sahibkar
- Sayt sifariş etməzdən əvvəl bazarı araşdıran adam
- Öz saytının zəif nöqtələrini görmək istəyən sahib

---

## 2. Kurs şərtlərinin örtülməsi

### Əvvəlki ayların mövzuları
| Mövzu | Layihədə harada |
|---|---|
| Python əsasları (list, dict, set, tuple, if/else, for/while) | Bütün collector-lər, chunking, parsing |
| Funksiyalar, scope, **dekoratorlar** | `@cached`, `@retry`, `@timed`, `@safe_collector` |
| **Gemini API** | Embedding (`text-embedding-004`) + ehtiyat mətn modeli |
| **Docker** | `docker-compose.yml` — Postgres+pgvector, Redis, n8n (profillərlə) |
| **n8n** əsasları: Webhook, HTTP Request, JS Expression | Workflow 1 (analiz tetikleyici) |
| **n8n + PostgreSQL** | Workflow 2 nəticələri birbaşa bazaya yazır |
| **SQLAlchemy, psycopg2** | `backend/db.py`, `backend/models_db.py` |
| **FastAPI, Pydantic** | `backend/main.py`, `backend/schemas.py` |
| **Redis caching** | `backend/cache.py` — domen keşi, embedding keşi, PageSpeed keşi |

### CARİ AYIN MƏCBURİ MÖVZULARI (nüvə)
| Mövzu | Layihədə harada |
|---|---|
| ⭐ **RAG + Memory** (embeddings, vektor DB, chunking, retrieval, re-ranking, yaddaş) | `backend/rag/` — bütün boru xətti; `messages` cədvəli = yaddaş |
| ⭐ **n8n Production Patterns** (error handling, execution modes, queue, retry, arxitektura) | 4 workflow, ayrıca Error Workflow, retry siyasəti, queue mode |
| ⭐ **GenAI, Prompt Engineering, LLM anatomiyası** | `backend/prompts/` — struktur promptlar, few-shot, çıxış sxemi; sənəddə token/kontekst təhlili |
| ⭐ **LangChain: building blocks, Messages, ilk Chain** | `backend/chains/` — `ChatPromptTemplate`, `Messages`, `Runnable` |
| ⭐ **LCEL və chain dizaynı** | Bütün zəncirlər `\|` operatoru ilə; `with_fallbacks`, `RunnableParallel` |
| ⭐ **n8n MCP Integration** | `backend/mcp_server.py` — 3 tool Claude/Cursor-a verilir |
| ⭐ **Gemma n8n-də** | Re-ranking Gemma ilə (Ollama); n8n AI Agent node → Ollama Gemma |

---

## 3. İstifadəçi axını

```
1. Ana səhifə:   [ https://numune-sayt.com ]   [ 🔍 Analiz et ]

2. Canlı gedişat (SSE):
   WHOIS ✓   DNS/IP ✓   SSL ✓   HTML ✓   Texnologiya ✓
   PageSpeed ✓   Səhifələr yığılır (17/24)   Embedding ✓

3. Nəticə səhifəsi:

   ┌─ TEXNİKİ ANALİZ ─────────────────────────────────┐
   │ Domen yaşı · Registrar                            │
   │ Texnologiya (framework, server, CDN)              │
   │ Hosting, IP, ölkə, SSL                            │
   │ Performans balı (qrafik), ölçü, yüklənmə          │
   │ Reklam & analitika alətləri                       │
   │ Rəng palitrası, şriftlər                          │
   │ Struktur: səhifə sayı, dillər, robots/sitemap     │
   ├─ AI HESABAT (Claude yazır) ──────────────────────┤
   │ 1. Bu saytın məqsədi nədir?                       │
   │ 2. Hədəf auditoriyası kimdir?                     │
   │ 3. Hansı texnologiyalar istifadə olunub, niyə?    │
   │ 4. Performans problemləri nədir?                  │
   │ 5. SEO çatışmazlıqları nədir?                     │
   │ 6. Daha müasir versiya necə görünə bilər?         │
   ├─ 💬 SAYTLA SÖHBƏT (RAG) ─────────────────────────┤
   │ "Çatdırılma neçə gün çəkir?"                      │
   │ → cavab + [mənbə: /kargo]                         │
   │ (əvvəlki sualları xatırlayır)                     │
   └───────────────────────────────────────────────────┘

4. Düymələr:
   [ ⚡ MÜASİR VERSİYASINI QUR ]   Claude yeni səhifə yazır (~30 san)
   [ 🧬 TAM KLON ÜÇÜN HAZIRLA ]    cloner sənədləri + hazır əmr
   [ 📦 Səhifə arşivi ]            HTML/CSS/şəkil qovluğa
   [ 📄 PDF hesabat ]              hər şey bir PDF-də
   [ 🔔 Bu saytı izlə ]            n8n cron ilə dəyişiklik xəbərdarlığı
```

---

## 4. Memarlıq

**Seçilmiş variant: A — FastAPI beyin, n8n avtomatlaşdırma.**

```
   Brauzer (HTML+JS)
        │ REST + SSE + WebSocket
        ▼
   ┌──────────────── FastAPI ────────────────┐
   │ collectors/  crawler  rag/  chains/     │
   │ llm.py (Claude · Gemini · Gemma)        │
   └───┬──────────────┬──────────────┬───────┘
       │              │              │
   PostgreSQL      Redis          Ollama
   + pgvector      (keş)          (Gemma)
       ▲
       │ HTTP / SQL
   ┌───┴────┐        ┌──────────────┐
   │  n8n   │◄───────┤ MCP serveri  │◄── Claude Code / Cursor
   │ 4 wf   │        └──────────────┘
   └────────┘
```

**Sərhəd qaydası:** iş məntiqi (analiz, RAG, LLM) **yalnız** Python-dadır.
n8n heç vaxt məntiq yazmır — o, **nə vaxt** və **kimə xəbər** məsələsini həll edir.

### Modul cədvəli

| Fayl / qovluq | Vəzifəsi | Sətir təxmini |
|---|---|---|
| `backend/main.py` | FastAPI marşrutları, SSE, WebSocket | ~250 |
| `backend/schemas.py` | Pydantic giriş/çıxış modelləri | ~150 |
| `backend/db.py` | SQLAlchemy engine, session, cədvəllər | ~200 |
| `backend/cache.py` | Redis keş + fallback | ~80 |
| `backend/llm.py` | Claude/Gemini/Gemma provayder abstraksiyası | ~150 |
| `backend/decorators.py` | `@cached`, `@retry`, `@timed`, `@safe_collector` | ~120 |
| `backend/collectors/*.py` | 9 müstəqil toplayıcı (hər biri ayrı fayl) | ~90 hər biri |
| `backend/crawler.py` | sitemap + daxili link gəzişi (async, limitli) | ~180 |
| `backend/rag/chunker.py` | mətn təmizləmə + chunking | ~120 |
| `backend/rag/embedder.py` | embedding + keş | ~90 |
| `backend/rag/store.py` | pgvector yazma/axtarış (hibrid) | ~160 |
| `backend/rag/reranker.py` | Gemma ilə yenidən sıralama | ~100 |
| `backend/rag/memory.py` | söhbət yaddaşı + xülasə | ~110 |
| `backend/chains/*.py` | LCEL zəncirləri | ~100 hər biri |
| `backend/prompts/*.py` | promptlar (ayrıca saxlanır) | — |
| `backend/builder.py` | müasir versiya + klon hazırlığı + arşiv | ~200 |
| `backend/mcp_server.py` | MCP tool-ları | ~120 |
| `frontend/index.html`, `app.js` | interfeys | ~600 |
| `n8n/*.json` | 4 workflow | — |
| `tests/` | pytest | ~50 test |

> Qayda: heç bir fayl 500 sətri keçmir.

---

## 5. Verilənlər bazası (PostgreSQL 16 + pgvector)

```sql
sites          (id, url, domain, ilk_analiz, son_analiz, izlenir, cron)
analyses       (id, site_id, tarix, xam_json JSONB, ai_hesabat JSONB, status, xeta)
pages          (id, site_id, url, basliq, metn, hash, yigilma_tarixi)
chunks         (id, page_id, sira, metn, embedding VECTOR(768))
chat_sessions  (id, site_id, yaradilma)
messages       (id, session_id, rol, metn, istifade_olunan_chunklar JSONB, tarix)
site_watches   (id, site_id, cron, son_yoxlama, son_deyisiklik, telegram_chat_id)
job_errors     (id, mənbə, workflow, xeta_metni, tarix)   -- n8n Error Workflow yazır
```

İndekslər: `chunks.embedding` üzərində HNSW, `pages.metn` üzərində `tsvector` (GIN).

---

## 6. RAG boru xətti (nüvə)

```
Səhifələr (max 30, eyni domen, robots.txt-ə hörmət)
   ↓ təmizləmə    HTML → mətn; menyu/footer/skript atılır (readability məntiqi)
   ↓ chunking     ~800 simvol, 120 üst-üstə düşmə, başlıq sərhədinə hörmət
   ↓ embedding    Gemini text-embedding-004 (768) — mətn hash-ı ilə Redis-də keşlənir
   ↓ saxlama      pgvector, HNSW indeks
   ↓
Sual
   ↓ retrieval    HİBRİD: vektor oxşarlığı (top 20) + açar söz ts_rank (top 10)
   ↓ birləşdirmə  Reciprocal Rank Fusion
   ↓ re-ranking   Gemma 3 (Ollama) hər namizədi 0-10 balla qiymətləndirir → top 5
   ↓ memory       son 6 mesaj + söhbətin qısa xülasəsi (bazadan)
   ↓ cavab        Claude → mətn + mənbə linkləri
```

**Niyə re-ranking Gemma-da?** 20 namizədi Claude-a göndərmək həm baha, həm yavaşdır.
Gemma lokal və pulsuzdur, bu iş üçün kifayətdir. Hesabatda hər iki variantın
gecikmə və qiymət müqayisəsi veriləcək.

**Ölçmə:** 15 sual-cavab dəsti hazırlanır; re-ranking olan/olmayan variantlar
müqayisə edilir (hit rate + gecikmə).

---

## 7. LangChain / LCEL

```python
# report_chain — texniki analiz → 6 bəndlik hesabat
report_chain = (
    RunnableParallel(analiz=..., xulase=...)
    | REPORT_PROMPT
    | llm.claude
    | JsonOutputParser(pydantic_object=AIHesabat)
)

# rag_chain — sual → mənbəli cavab
rag_chain = (
    RunnableParallel(
        context=retriever | reranker | format_docs,
        sual=RunnablePassthrough(),
        yaddas=memory_loader,
    )
    | RAG_PROMPT
    | llm.claude
    | StrOutputParser()
)

# modernize_chain — dizayn token + məzmun → yeni HTML
modernize_chain = MODERNIZE_PROMPT | llm.claude | HtmlExtractor()
```

Provayder zənciri: `claude.with_fallbacks([gemini, gemma_local])`.
`Messages` (System/Human/AI) açıq şəkildə istifadə olunur — kurs tələbi.

---

## 8. n8n — 4 workflow

| # | Workflow | Naxış |
|---|---|---|
| 1 | **Analiz tetikleyici** — Webhook → HTTP Request `/api/analyze` → JS Expression ilə nəticə formatlanır → Postgres | Webhook, HTTP Request, JS Expression, Postgres node |
| 2 | **Rəqib izləmə** — Schedule (cron) → izlənən saytlar → təkrar analiz → əvvəlki ilə fərq → dəyişiklik varsa Telegram | **Retry (3 cəhd, eksponensial), queue/execution mode, batch** |
| 3 | **Error Workflow** — digər workflow sınanda avtomatik işə düşür → `job_errors` cədvəlinə yazır → Telegram xəbərdarlığı | **Error handling, `continueOnFail`, `onError` marşrutu** |
| 4 | **Gemma agenti** — AI Agent node → Ollama (Gemma 3) → gələn sualı təsnif edir və uyğun endpoint-ə yönləndirir | **Açıq modeli agentə qoşmaq** |

Workflow JSON-ları `n8n/` qovluğunda saxlanır (versiya nəzarətində).

---

## 9. MCP inteqrasiyası

`backend/mcp_server.py` — stdio MCP serveri, Claude Code / Cursor-a qoşulur:

| Tool | Nə edir |
|---|---|
| `sayt_analiz_et(url)` | n8n Workflow 1 webhook-unu çağırır, analiz ID qaytarır |
| `saytla_danis(url, sual)` | RAG cavabı + mənbələr |
| `saytlari_muqayise_et(url1, url2)` | iki analizin fərqli cəhətləri |

Qeydiyyat: `claude mcp add saytlupa -- py D:\SaytLupa\backend\mcp_server.py`

---

## 10. Üç düymə (klonlama hissəsi)

### ⚡ Müasir versiyasını qur
Analizdən çıxan dizayn token-ləri (rənglər, şriftlər), məzmun xülasəsi və
SEO/performans qüsurları `modernize_chain`-ə verilir → Claude **yeni, təmiz,
sürətli tək-səhifəlik sayt** yazır. Nəticə: brauzerdə önizləmə + ZIP yükləmə.
Saxlanır: `storage/modern/<domain>/`.

### 🧬 Tam klon üçün hazırla
SaytLupa `ai-website-cloner` şablonunun gözlədiyi sənədləri **avtomatik yazır**:
```
docs/research/DESIGN_TOKENS.md        ← rənglər, şriftlər, spacing, radius
docs/research/TECH_STACK_ANALYSIS.md  ← framework, CSS, server, CDN
docs/research/COMPONENT_INVENTORY.md  ← tapılan komponentlər
docs/design-references/               ← ekran görüntüləri
```
və istifadəçiyə hazır əmri verir: `/clone-website https://...`
İstifadəçi bunu Claude Code-da işə salır, tam klon qurulur.

> **Niyə birbaşa çağırmırıq?** `ai-website-cloner` proqram deyil — Claude Code
> skill-idir; işi AI agent komandası görür (10-20 dəq, yüksək RAM). Serverdən
> avtomatik başlatmaq etibarsızdır. Ona görə SaytLupa **hazırlıq** edir, tam işi
> Claude Code görür — bu, real və işləyən inteqrasiyadır.

### 📦 Səhifə arşivi
Səhifənin HTML + CSS + şəkilləri `storage/archives/<domain>/` qovluğuna yazılır.
Yalnız öyrənmə məqsədilə; interfeysdə etik qeyd göstərilir.

---

## 11. Modellər və məsrəf

| İş | Model | Səbəb |
|---|---|---|
| AI hesabat (6 bənd), RAG cavabı, müasir versiya | **Claude** (`claude-sonnet-5`, ağır işdə `claude-opus-5`) | ən keyfiyyətli düşüncə |
| Embedding | **Gemini** `text-embedding-004` | ucuz, 768 ölçü, kurs şərti |
| Re-ranking, chunk xülasəsi, təsnifat, n8n agenti | **Gemma 3 (Ollama, lokal)** | pulsuz, sürətli, açıq model şərti |
| Ehtiyat (fallback) | Gemini → Gemma | Claude əlçatmaz olsa layihə dayanmır |

`.env` açarları: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OLLAMA_BASE_URL`.
**Açar olmasa sistem mock rejimdə işləyir** — nümayiş dayanmır.

---

## 12. Disk və RAM planı

Maşın: **RAM 7.8 GB** (boş ~1.2 GB), **C: 10.5 GB boş**, **D: 316.8 GB boş**.
Buna görə hər şey D:-də saxlanır və servislər **profillərlə** ayrıca qaldırılır.

```
D:\SaytLupa\
  backend\  frontend\  n8n\  tests\  docs\
  data\        postgres\  redis\  n8n\        ← Docker bind mount
  storage\     pages\  archives\  modern\  pdf\
  .venv\       Python mühiti
  docker-compose.yml  .env  README.md
D:\ollama-models\      OLLAMA_MODELS env dəyişəni
D:\.cache\             pip, HuggingFace keşi
D:\DockerData\         Docker Desktop disk image (GUI-dən dəyişilir)
```

```bash
docker compose --profile core up -d    # Postgres + Redis        ~450 MB
docker compose --profile n8n  up -d    # n8n (lazım olanda)      ~500 MB
ollama run gemma3:1b                   # Gemma (lazım olanda)    ~1.5 GB
uvicorn backend.main:app --reload      # FastAPI (host-da)       ~250 MB
```

**Fallback qaydası:** Redis yoxdursa keşsiz işləyir. Postgres yoxdursa SQLite +
lokal vektor axtarışı. Ollama yoxdursa re-ranking Gemini-yə keçir. n8n yoxdursa
izləmə söndürülür. Heç bir halda layihə çökmür.

---

## 13. Testlər

| Sahə | Nə yoxlanılır |
|---|---|
| Collector-lər | mock HTTP cavabları ilə hər 9 modul |
| Dekoratorlar | `@retry` neçə dəfə cəhd edir, `@cached` keşi işlədir |
| Chunking | sərhədlər, üst-üstə düşmə, boş mətn |
| Retrieval | hibrid axtarış sıralaması, RRF |
| Zəncirlər | `FakeListLLM` ilə LCEL çıxışı və sxem uyğunluğu |
| Pydantic | yanlış URL, boş sahə, tip xətaları |
| API | FastAPI `TestClient` ilə əsas marşrutlar |

Hədəf: **~50 test**, `pytest -q` ilə keçir.

---

## 14. 12 günlük yol xəritəsi

| Gün | İş | Nəticə |
|---|---|---|
| 1 | Skelet: FastAPI + Pydantic + SQLAlchemy + Docker core profil + D: quruluşu | `/health` işləyir, baza qalxır |
| 2 | 5 collector (whois, dns, geo, ssl, tech) + dekoratorlar | `/api/analyze` xam nəticə verir |
| 3 | 4 collector (html, speed, design, ads) + Redis keş | analiz tam |
| 4 | Crawler + səhifə saxlama + SSE canlı gedişat | səhifələr bazada |
| 5 | ⭐ Chunking + embedding + pgvector saxlama | chunk-lar bazada |
| 6 | ⭐ Hibrid retrieval + Gemma re-ranking + yaddaş | RAG cavab verir |
| 7 | ⭐ LCEL: `report_chain` + `rag_chain` + promptlar | 6 bəndlik AI hesabat |
| 8 | İnterfeys: nəticə səhifəsi, qrafiklər, chat | tam görünüş |
| 9 | 3 düymə: müasir versiya / klon hazırlığı / arşiv + PDF | təhvil funksiyaları |
| 10 | ⭐ n8n: 4 workflow + Gemma agenti + Telegram | avtomatlaşdırma |
| 11 | ⭐ MCP serveri + testlər (~50) | Claude Code-dan çağırılır |
| 12 | Sənədləşdirmə (`LAYIHE-HAQQINDA/`), cilalama | təhvilə hazır |

---

## 15. Bu ay daxil OLMAYAN (gələcək)

- Pullu API ilə real trafik (SimilarWeb/Semrush)
- Çoxdilli interfeys (rus/ingilis)
- Onlayn hosting və kommersiya modeli
- Bir neçə saytın yan-yana müqayisə səhifəsi (MCP tool-u var, UI yoxdur)
- Açıq/qaranlıq rejim

---

## 16. Etik qeyd

Bu alət **öyrənmək, analiz və ilham** üçündür. İstifadə edilmir: fişinq, saxta sayt,
başqasının brendini öz adına çıxarmaq, müəllif hüququ pozuntusu, saytların istifadə
şərtlərini pozmaq. Crawler `robots.txt`-ə hörmət edir, sorğu tezliyi məhdudlaşdırılır,
səhifə arşivi yalnız lokal qovluğa yazılır.

Analiz nəticələrində **heç vaxt uydurma rəqəm yazılmır** — dəqiq bilinməyən
məlumat "təxmini" işarəsi ilə verilir və ya boş saxlanılır.
