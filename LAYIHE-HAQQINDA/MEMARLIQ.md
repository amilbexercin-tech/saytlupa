# SaytLupa — Memarlıq

## Əsas prinsip

**Python düşünür, n8n xatırladır.**

Bütün iş məntiqi (analiz, RAG, LLM çağırışları) **yalnız** Python tərəfdədir.
n8n heç vaxt məntiq saxlamır — o, yalnız **nə vaxt** işə düşməli və **kimə** xəbər
verməli olduğunu bilir. Bu sərhəd qəsdən çəkilib: məntiq n8n node-larına yayılsa,
onu test etmək, versiya nəzarətində saxlamaq və səhvi tapmaq çətinləşir.

---

## Ümumi quruluş

```
                         Brauzer (HTML + vanilla JS)
                    REST · SSE (EventSource) · WebSocket
                                   │
   ┌───────────────────────────────┴────────────────────────────────┐
   │                          FastAPI                                │
   │                                                                 │
   │  main.py        marşrutlar, SSE axını                          │
   │  analiz.py      dirijor: toplayıcılar → gəziş → baza           │
   │  hadise.py      canlı gedişat brokeri (asyncio.Queue)          │
   │                                                                 │
   │  collectors/    9 toplayıcı + bot qoruması aşkarlanması        │
   │  crawler.py     robots.txt → sitemap → BFS gəziş               │
   │  metn.py        HTML → təmiz mətn + barmaq izi                 │
   │  rag/           chunking · embedding · axtarış · re-ranking    │
   │  chains/        LCEL zəncirləri                                │
   │  llm.py         Claude / Gemini / Gemma — bir interfeys        │
   │  builder/       müasir versiya · klon hazırlığı · arşiv · PDF  │
   │  izleme.py      sayt izləmə: barmaq izi fərqi + xəta jurnalı   │
   │  muqayise.py    iki saytın analizini yan-yana qoyur            │
   └──┬──────────────────┬──────────────────┬───────────────────────┘
      │                  │                  │
      ▼                  ▼                  ▼
  PostgreSQL          Redis             Ollama
  + pgvector          (keş)             Gemma 3 4B
      ▲                                     ▲
      │ SQL                            HTTP │
   ┌──┴──────────────┐              ┌───────┴──────┐
   │  n8n — 4 wf     │─── HTTP ────▶│  FastAPI     │◀── HTTP ── mcp_server.py
   │  webhook · cron │   /api/…     └──────────────┘            (stdio)
   │  error · agent  │                                               ▲
   └─────────────────┘                                               │
                                                    Claude Code / Cursor
```

**Sərhəd qaydası:** iş məntiqi (analiz, RAG, LLM, fərq hesablama, müqayisə)
**yalnız** Python-dadır. n8n *nə vaxt* və *kimə xəbər* sualını həll edir;
MCP serveri isə yalnız tərcüməçidir — hər ikisi FastAPI-yə HTTP sorğusu göndərir.

---

## Modullar və məsuliyyətləri

Hər modulun **bir vəzifəsi** var; heç bir fayl 500 sətri keçmir.
Bütün modullar yazılıb və işləyir.

| Modul | Sətir | Vəzifəsi | Nədən asılıdır |
|---|---|---|---|
| ✅ `config.py` | 56 | Bütün parametrlər bir yerdə (pydantic-settings) | — |
| ✅ `db.py` | 191 | 9 cədvəl, sessiya, Postgres/SQLite seçimi | `config` |
| ✅ `cache.py` | 50 | Redis + yaddaşdaxili fallback | `config` |
| ✅ `decorators.py` | 125 | `@cached`, `@retry`, `@timed`, `@safe_collector` | `cache` |
| ✅ `schemas.py` | 77 | API giriş/çıxış müqaviləsi (Pydantic) | — |
| ✅ `collectors/base.py` | 42 | Ortaq köməkçilər: domen, URL, HTTP başlıqları | `config` |
| ✅ `collectors/*.py` | 41-244 | Hər biri **bir** məlumat növünü toplayır | `base`, `decorators` |
| ✅ `collectors/__init__.py` | 90 | Toplayıcıları paralel işlədən dirijor | bütün toplayıcılar |
| ✅ `metn.py` | 52 | HTML → təmiz mətn, barmaq izi | — |
| ✅ `crawler.py` | 179 | Sayt gəzişi | `metn`, `base` |
| ✅ `hadise.py` | 26 | SSE hadisə növbələri | — |
| ✅ `analiz.py` | 199 | Tam axın + baza yazışı | `collectors`, `crawler`, `db`, `hadise` |
| ✅ `main.py` | 241 | HTTP səthi | hamısı |
| ✅ `llm.py` | 108 | Claude / Gemini / Gemma — vahid interfeys | `config` |
| ✅ `rag/chunker.py` | 105 | Mətnin parçalanması | — |
| ✅ `rag/embedder.py` | 158 | Embedding + keş + lokal ehtiyat | `cache`, `config` |
| ✅ `rag/store.py` | 213 | pgvector, hibrid axtarış, RRF | `db`, `embedder` |
| ✅ `rag/reranker.py` | 156 | Gemma ilə yenidən sıralama (LCEL) | `llm` |
| ✅ `rag/memory.py` | 105 | Söhbət yaddaşı | `db` |
| ✅ `chains/model.py` | 66 | Model fallback zənciri | `llm` |
| ✅ `chains/hesabat.py` | 185 | LCEL: analiz → 6 bəndlik rəy | `prompts`, `schemas` |
| ✅ `chains/rag_cavab.py` | 36 | LCEL: sual → cavab | `prompts` |
| ✅ `chains/muasir.py` | 179 | LCEL: analiz → müasir HTML (Gemma-sız) | `prompts`, `hesabat` |
| ✅ `prompts/` | 3 fayl | Promptlar ayrıca saxlanılır | — |
| ✅ `builder/kontekst.py` | 88 | Təhvil üçün ortaq məlumat və qovluqlar | `analiz`, `db` |
| ✅ `builder/muasir.py` | 69 | ⚡ Müasir versiyanı qurur və saxlayır | `chains.muasir` |
| ✅ `builder/klon.py` | 362 | 🧬 Cloner üçün 5 araşdırma sənədi | `kontekst` |
| ✅ `builder/arsiv.py` | 261 | 📦 Səhifə arşivi + ZIP | `crawler`, `collectors` |
| ✅ `builder/pdf.py` | 400 | 📄 PDF hesabat (reportlab) | `kontekst` |
| ✅ `izleme.py` | 172 | Sayt izləmə: fərq hesablama + `job_errors` | `analiz`, `crawler`, `rag` |
| ✅ `muqayise.py` | 215 | İki saytın analizini yan-yana qoyur | `db`, `collectors.base` |
| ✅ `mcp_server.py` | 146 | MCP (stdio) — 3 tool; işi FastAPI-yə ötürür | `config` + `httpx` |

**Asılılıq istiqaməti həmişə aşağıdan yuxarıdır** — `config` heç nədən asılı deyil,
`main.py` isə hamısından asılıdır. Dövrə (circular import) yoxdur.

---

## Verilənlər bazası

```
sites          (id, url, domain, ilk_analiz, son_analiz, izlenir)
   │
   ├── analyses     (id, site_id, tarix, xam_json, ai_hesabat, status, xeta)
   │
   ├── pages        (id, site_id, url, basliq, metn, hash, yigilma_tarixi)
   │      │
   │      └── chunks   (id, page_id, sira, metn, embedding VECTOR(768))
   │
   ├── chat_sessions (id, site_id, yaradilma)
   │      │
   │      └── messages  (id, session_id, rol, metn, istifade_olunan_chunklar, tarix)
   │
   └── site_watches (id, site_id, cron, son_yoxlama, son_deyisiklik, telegram_chat_id)

job_errors     (id, menbe, workflow, xeta_metni, tarix)   ← n8n Error Workflow yazır
n8n_jurnal     (id, workflow, site_id, analiz_id, xulase, data, tarix)
                                                          ← n8n Postgres node yazır
```

Son iki cədvəli **n8n doldurur**, Python isə yalnız yaradır və oxuyur. Cədvəlin
sxemini Python-da saxlamaq n8n tərəfdə əl ilə `CREATE TABLE` yazmaq ehtiyacını
aradan qaldırır: `baza_qur()` işə düşəndə hər ikisi hazır olur.

### Diqqətəlayiq həllər

**`pages.hash`** — səhifə mətninin SHA-256 barmaq izi. İki yerdə işləyir:
gəziş zamanı eyni məzmunlu səhifə iki dəfə saxlanmır; n8n izləmə workflow-u isə
köhnə və yeni hash-ı müqayisə edib dəyişikliyi aşkarlayır.

**`chunks.embedding`** — Postgres-də `VECTOR(768)` (pgvector, HNSW indeks), SQLite-da
isə JSON mətn. Seçim `db.py`-də işə düşəndə edilir:

```python
def _embedding_sutunu():
    if POSTGRES:
        from pgvector.sqlalchemy import Vector
        return Column(Vector(EMBEDDING_OLCUSU))
    return Column(Text)
```

**`messages.istifade_olunan_chunklar`** — hər cavabın hansı parçalara əsaslandığı
saxlanılır. Bu, həm mənbə göstərmək, həm də sonradan "cavab niyə belə oldu?" sualını
araşdırmaq üçündür.

---

## Analiz axını (addım-addım)

```
POST /api/analyze  {url, max_sehife}
   │
   ├─ sites + analyses sətirləri yaradılır (status: "gozleyir")
   ├─ fon tapşırığı başlayır (asyncio.create_task)
   └─ dərhal {analiz_id} qaytarılır          ← istifadəçi gözləmir

Fon tapşırığı:
   1. status → "isleyir"
   2. Səhifə BİR DƏFƏ yüklənir, vaxt ölçülür
   3. Bot qoruması yoxlanılır
        └─ qorunursa: gəziş atlanır, səbəb bildirilir
   4. 9 toplayıcı asyncio.gather ilə paralel
        └─ hər biri @safe_collector altında — biri sınsa digərləri davam edir
   5. Nəticə analyses.xam_json-a yazılır
   6. Crawler: robots.txt → sitemap.xml → BFS
        └─ hər səhifədə hadise.gonder(...) → SSE
   7. Səhifələr pages cədvəlinə (varsa yenilənir)
   8. RAG: chunking → embedding → chunks cədvəli
   9. LCEL zənciri: xam analiz → Claude → ai_hesabat
  10. status → "hazir"

GET /api/analyze/{id}/axin   ← SSE, brauzer bütün bu addımları canlı görür
GET /api/analyze/{id}        ← hazır nəticə
```

Bütün gedişat hadisələri `hadise.py`-dəki `asyncio.Queue` vasitəsilə ötürülür.
Növbə dolarsa hadisə atılır — **analiz heç vaxt gedişat bildirişinə görə dayanmır**.

---

## RAG boru xətti

```
Səhifələr (max 30)
   ↓ təmizləmə    metn.py — menyu, footer, cookie, skript, sidebar atılır
   ↓ chunking     ~800 simvol, 120 üst-üstə düşmə, başlıq sərhədinə hörmət
   ↓ embedding    Gemini text-embedding-004 (768 ölçü) — mətn hash-ı ilə keşlənir
   ↓ saxlama      pgvector, HNSW indeks
   ↓
Sual
   ↓ retrieval    HİBRİD:  vektor oxşarlığı (top 20)  +  açar söz ts_rank (top 10)
   ↓ birləşdirmə  Reciprocal Rank Fusion
   ↓ re-ranking   Gemma 3 4B — TOPLU (hamısı bir promptda, ~6-10 san)
   ↓ yaddaş       son 6 mesaj + söhbətin xülasəsi (messages cədvəlindən)
   ↓ cavab        Claude → mətn + mənbə linkləri
```

**Niyə hibrid axtarış?** Vektor axtarışı mənanı tutur ("nə qədər gözləmək lazımdır?"
→ "2-3 iş günü"), amma dəqiq söz və rəqəmləri (model nömrəsi, qiymət) itirir. Açar söz
axtarışı isə əksinə. İkisini birləşdirmək hər iki halı örtür.

**Niyə re-ranking?** Vektor axtarışı 20 namizəd verir, amma onların sıralaması həmişə
düzgün olmur. Kiçik model hər namizədin suala nə dərəcədə cavab verdiyini qiymətləndirib
ən yaxşı 5-ni seçir — Claude-a az, amma dəqiq kontekst gedir.

---

## LCEL zəncirləri

Hər zəncir eyni quruluşdadır: **prompt → model → parser**, `|` operatoru ilə.

```python
# chains/hesabat.py — xam analiz → 6 bəndlik AI rəy
hazirliq = RunnableParallel(
    url=RunnableLambda(lambda x: x["url"]),
    melumat=RunnableLambda(lambda x: xulase_qur(x["xam"])),  # JSON → oxunaqlı mətn
)
zencir = hazirliq | prompt | model | JsonOutputParser(pydantic_object=AIHesabat)

# chains/rag_cavab.py — sual + mənbələr + yaddaş → cavab
zencir = prompt | model | StrOutputParser()

# chains/model.py — fallback zənciri
model = claude.with_fallbacks([gemini, gemma])
```

**`xulase_qur()` niyə lazımdır?** Xam analiz JSON-u 10-20 KB olur. Onu olduğu kimi
modelə göndərmək həm bahadır, həm də model lazımsız sahələrdə itir. Bu funksiya
yalnız rəy üçün lazım olan faktları oxunaqlı mətnə çevirir və **naməlum olanı
açıq işarələyir** ("Meta description: YOXDUR", "Yaş: ən azı 8.4 il (TƏXMİNİ)").
Beləliklə model uydurmağa məcbur qalmır.

**Uzun mətn yazan işlər lokal modeldə işlədilmir.** `guclu_model_var()` yoxlayır
ki, Claude və ya Gemini varmı; yoxdursa AI hesabat buraxılır və səbəb açıq
yazılır. Səbəb: gemma3:4b bu maşında belə mətni dəqiqələrlə yazır və analizi
bloklayır.

---

## Avtomatlaşdırma və xarici səth (Gün 10-11)

### İzləmə axını

```
n8n cron (hər gün 09:00)
   │
   ├─ GET  /api/izleme?min_saat=20      son 20 saatda yoxlananlar süzülür
   │
   └─ POST /api/izleme/{id}/yoxla       hər sayt üçün, retry 3×
         ├ köhnə barmaq izləri oxunur   (pages.hash)
         ├ sayt yenidən gəzilir
         ├ fərq hesablanır              yeni · dəyişən · silinən
         ├ baza yenilənir; dəyişiklik varsa RAG indeksi də
         └ {deyisdi, xulase, telegram_chat_id}
   │
   └─ deyisdi = true  →  Telegram
```

**Boş gəziş dəyişiklik sayılmır.** Sayt bağlı olanda və ya `robots.txt` qadağan
edəndə crawler boş siyahı qaytarır; bunu "bütün səhifələr silindi" kimi oxumaq
yalan xəbərdarlıq göndərərdi.

### 4 workflow

| # | Tetikleyici | Naxış | Nəyə toxunur |
|---|---|---|---|
| 1 | Webhook | status döngüsü (Wait + IF), JS Code, Postgres node | `n8n_jurnal` |
| 2 | Schedule (cron) | batch (bir-bir), retry 3×, `onError` marşrutu | `site_watches`, Telegram |
| 3 | Error Trigger | mərkəzi xəta toplama | `job_errors`, Telegram |
| 4 | Webhook | Gemma təsnifatı → Switch → 3 endpoint | `/api/analyze`, `/api/sites/*` |

Workflow 3 digər üçünün **Error workflow** sahəsində seçilib — hər hansı biri
sınsa, xəta bazaya düşür və Telegram-a xəbər gedir.

### MCP serveri

| Tool | Nə edir |
|---|---|
| `sayt_analiz_et(url, max_sehife)` | analizi fonda başladır |
| `saytla_danis(sayt, sual)` | RAG cavabı + mənbələr |
| `saytlari_muqayise_et(sayt1, sayt2)` | 9 ölçü + texnologiya + SEO müqayisəsi |

Server **öz prosesində iş görmür** — hamısını FastAPI-yə HTTP ilə ötürür.
Səbəb: Claude Code MCP serverini kiçik alt-proses kimi işə salır; crawler,
embedding və LLM orada işləsəydi hər çağırış ağır olar, baza ilə iki ayrı proses
yazışardı. Server bağlıdırsa alət susmur, "uvicorn işə sal" deyir.

---

## Modellərin bölgüsü

| İş | Model | Səbəb |
|---|---|---|
| AI hesabat, RAG cavabı, müasir versiya | **Claude** | Ən keyfiyyətli düşüncə, uzun kontekst |
| Embedding | **Gemini** `text-embedding-004` | Ucuz, sürətli, 768 ölçü |
| Re-ranking, təsnifat, n8n agenti | **Gemma 3 4B** (lokal) | Pulsuz; ölçmə ilə seçilib — bax [`../docs/model-secimi.md`](../docs/model-secimi.md) |

LangChain-in `with_fallbacks` mexanizmi ilə: Claude əlçatmaz olsa Gemini, o da olmasa
Gemma işə düşür. Heç biri yoxdursa sistem **mock rejimdə** işləyir — nümayiş dayanmır.

---

## Dayanıqlılıq (heç nə layihəni çökdürmür)

| Nə yoxdur | Nə olur |
|---|---|
| PostgreSQL | SQLite-a keçir (`data/saytlupa.db`) |
| Redis | Yaddaşdaxili lüğətə keçir |
| Ollama / Gemma | Re-ranking Gemini-yə keçir |
| API açarları | Mock rejim — interfeys və axın işləyir |
| PageSpeed açarı | Öz ölçmələrimiz göstərilir |
| n8n | İzləmə söndürülür, qalan hər şey işləyir |
| Bir toplayıcı sınır | Digər 8-i davam edir, nəticədə `"ugurlu": false` yazılır |
| `robots.txt` yoxdur | Hər şeyə icazə sayılır |
| Sayt bot qoruması altındadır | Gəziş atlanır, səbəb dürüst bildirilir |

Bu, "hər şey qurulmalıdır" tələbini aradan qaldırır: layihəni müəllim öz maşınında
`uvicorn backend.main:app` ilə **heç nə quraşdırmadan** işə sala bilər.

---

## Yaddaş və resurs məhdudiyyəti

Layihə **7.8 GB RAM**-lı maşında qurulub. Buna görə:

- Docker xidmətləri **profillərə** bölünüb (`core` = Postgres + Redis, `n8n` ayrı)
- Gemma modeli **3.3 GB**-lıq `gemma3:4b`-dir; 7 GB-lıq `gemma4:12b` ölçüldü və
  bu maşında **istifadəyə yararsız** çıxdı (çağırış başına ~99 saniyə)
- Səhifə **bir dəfə** yüklənir və bütün toplayıcılar arasında paylaşılır
- Crawler eyni anda 4 sorğu saxlayır, HTML-i yaddaşda saxlamır — mətnə çevirib atır
