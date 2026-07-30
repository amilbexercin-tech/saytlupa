# SaytLupa — İstifadə olunan texnologiyalar

Layihədə istifadə olunan hər şey üç hissəyə bölünüb:

- **1-ci hissə** — bu ayın (cari ay) məcburi mövzuları
- **2-ci hissə** — əvvəlki ayların mövzuları (layihənin təməli)
- **3-cü hissə** — kurs siyahısında olmayan, əlavə istifadə edilən texnologiyalar

> ⭐ = layihənin **əsas dayaqları**
> ✅ = hazır və işləyir — 2026-07-29 vəziyyəti ilə **bütün mövzular tamamlanıb**

---

## 1-ci hissə — CARİ AYIN MÖVZULARI (layihənin nüvəsi)

| Mövzu | Vəziyyət | Harada tətbiq olunub |
|---|---|---|
| ⭐ **RAG + Memory** — embeddings, vektor DB, chunking, retrieval, re-ranking, yaddaş | ✅ | `rag/chunker.py` (800 simvol, 120 üst-üstə, paraqraf sərhədi), `rag/embedder.py` (Gemini `text-embedding-004` + lokal ehtiyat, Redis keşi), `rag/store.py` (pgvector + HNSW + GIN, **hibrid axtarış + RRF**), `rag/reranker.py` (Gemma 3 4B, seçim edilə bilən), `rag/memory.py` (`messages` cədvəli — son 6 mesaj + xülasə) |
| ⭐ **n8n Production Patterns** — error handling, execution modes, queue, retry, arxitektura | ✅ | `n8n/` — 4 workflow: **1** analiz tetikleyici (Webhook + status döngüsü + Postgres node), **2** rəqib izləmə (Schedule + `splitInBatches` + `retryOnFail: 3` + `onError: continueErrorOutput`), **3** Error Workflow (Error Trigger → `job_errors` → Telegram; digər üçünün *Error workflow* sahəsində seçilib), **4** Gemma agenti. Hamısı canlı n8n-də (5678) sınanıb |
| ⭐ **GenAI, Prompt Engineering, LLM anatomiyası** | ✅ | `prompts/hesabat.py`, `prompts/rag.py`, `prompts/muasir.py` — rol təyini, uydurmağın qadağası, çıxış sxemi, bənd-bənd izah; `docs/model-secimi.md` — **3 modelin + re-ranking-in ölçülməsi** |
| ⭐ **LangChain: building blocks, Messages, ilk Chain** | ✅ | `chains/` — `ChatPromptTemplate.from_messages([("system",...),("human",...)])`, `JsonOutputParser(pydantic_object=...)`, `StrOutputParser` |
| ⭐ **LCEL və chain dizaynı** | ✅ | `chains/hesabat.py` — `RunnableParallel \| prompt \| model \| JsonOutputParser`; `chains/rag_cavab.py` — `prompt \| model \| StrOutputParser`; `chains/model.py` — `with_fallbacks([gemini, gemma])` |
| ⭐ **n8n MCP Integration** — layihəni Claude/Cursor-a tool kimi vermək | ✅ | `mcp_server.py` (FastMCP, stdio) — `sayt_analiz_et`, `saytla_danis`, `saytlari_muqayise_et`; `claude mcp list` → ✔ Connected. Alətlər işi özləri görmür, FastAPI-yə ötürür |
| ⭐ **Gemma (açıq model) n8n-də** | ✅ | `rag/reranker.py` (lokal Ollama) və `n8n/4-gemma-agenti.json` — **Ollama Chat Model** node → `gemma3:4b` sualı təsnif edir, **Switch** node uyğun endpoint-ə yönləndirir. Alət çağırışı əvəzinə təsnifat seçildi: `gemma3:4b`-də `tools` imkanı yoxdur (bax [QERARLAR §12](QERARLAR.md)) |

---

## 2-ci hissə — ƏVVƏLKİ AYLARIN MÖVZULARI

| Mövzu | Vəziyyət | Harada tətbiq olunub |
|---|---|---|
| ⭐ **Python əsasları** — dəyişənlər, I/O, məntiq | ✅ | Bütün backend |
| ⭐ **Şərt operatorları (if/else)** | ✅ | Hər yerdə; xüsusilə `collectors/qoruma.py`, `db.py` (Postgres/SQLite seçimi) |
| ⭐ **Dövr operatorları (for / while)** | ✅ | `crawler.py` (`while novbe and ...` — gəziş növbəsi), `collectors/__init__.py` (for) |
| ⭐ **List / Tuple** | ✅ | `collectors/texnologiya.py` — imza siyahıları `list[tuple[str, str, str]]`; `crawler.py` — növbə |
| ⭐ **Dictionary / Set** | ✅ | `collectors/__init__.py` (toplayıcı lüğəti), `crawler.py` (`gorulen: set[str]`, `gorulen_hash: set[str]`), `dizayn.py` (`Counter`) |
| ⭐ **Funksiyalar** — parametr, return, scope | ✅ | Hər yerdə; `crawler.py`-də daxili funksiya (`icaze`) closure ilə xarici dəyişəni tutur |
| ⭐ **Dekoratorlar** | ✅ | `decorators.py` — **öz yazdığımız 4 dekorator**: `@cached` (Redis keşi), `@retry` (eksponensial gözləmə ilə təkrar), `@timed` (icra vaxtı), `@safe_collector` (xətanı udub analizi dayandırmır). Hamısı həm sync, həm async funksiyaları dəstəkləyir |
| **Gemini API çağırışları** | ✅ | `rag/embedder.py` — `gemini-embedding-001` (768 ölçüyə qısaldılır); `llm.py` — `gemini-3.6-flash` ehtiyat mətn modeli |
| **Docker: mühit qurulması** | ✅ | `docker-compose.yml` — Postgres (pgvector), Redis, n8n; **profillərlə** (`--profile core`, `--profile n8n`) — 7.8 GB RAM üçün |
| **n8n: workflow, Webhook, HTTP Request, JS Expression** | ✅ | `n8n/1-analiz-tetikleyici.json` — Webhook → HTTP Request → Wait/IF döngüsü → **Code node (JS)** nəticəni formatlayır → Respond |
| **n8n ilə PostgreSQL inteqrasiyası** | ✅ | `n8n/1-analiz-tetikleyici.json` — **Postgres node** (`executeQuery`, parametrli INSERT) analiz xülasəsini `n8n_jurnal` cədvəlinə yazır |
| ⭐ **Python + Database: SQLAlchemy, psycopg2** | ✅ | `db.py` — 9 cədvəl, `relationship`, `cascade`, `ForeignKey`; `psycopg2` sürücüsü ilə Postgres |
| ⭐ **FastAPI əsasları** | ✅ | `main.py` — REST marşrutlar, `lifespan`, `HTTPException`, `StaticFiles`, SSE |
| ⭐ **Pydantic modelləri** | ✅ | `schemas.py` — `HttpUrl`, `Field(ge=, le=)`, `field_validator`, `Literal`, `response_model` |
| ⭐ **DB inteqrasiyası + Redis caching** | ✅ | `cache.py` — Redis + yaddaşdaxili fallback; `@cached` dekoratoru ilə birləşdirilib |

---

## 3-cü hissə — SİYAHIDA OLMAYAN ƏLAVƏ TEXNOLOGİYALAR

Bunlar kurs siyahısında yoxdur, amma layihənin işləməsi üçün lazım olub:

| Texnologiya | Harada | Nə üçün |
|---|---|---|
| **async / await (asyncio)** | bütün backend | 9 toplayıcı və 4 səhifə paralel yüklənir |
| **`asyncio.gather`** | `collectors/__init__.py`, `dns_qeydleri.py` | Paralel icra — analiz 6 saniyə əvəzinə 1.2 saniyə |
| **`asyncio.Semaphore`** | `crawler.py` | Sayta eyni anda 4-dən çox sorğu getməsin |
| **`asyncio.to_thread`** | `analiz.py`, `sertifikat.py`, `domen.py` | Bloklayan əməliyyatları (baza, socket) axından çıxarmaq |
| **`asyncio.Queue`** | `hadise.py` | SSE hadisə brokeri |
| **SSE — Server-Sent Events** | `main.py`, `frontend/index.html` | Canlı gedişat (WebSocket-dən sadədir, tək istiqamətlidir) |
| **`EventSource` (brauzer API)** | `frontend/index.html` | SSE-ni brauzerdə qəbul etmək |
| **httpx (async HTTP client)** | hər yerdə | Bütün xarici sorğular |
| **BeautifulSoup + lxml** | `metn.py`, `sehife.py`, `dizayn.py` | HTML/XML təhlili |
| **Regex (`re`)** | `texnologiya.py`, `reklam.py`, `dizayn.py`, `qoruma.py` | 24 texnologiya + 24 reklam aləti imzası, rəng və şrift çıxarma |
| **`collections.Counter`** | `dizayn.py` | Ən çox işlənən rəng və şriftlərin tapılması |
| **Xam WHOIS protokolu (TCP/43, `socket`)** | `domen.py` | `.az` kimi RDAP-ı olmayan domenlər üçün öz WHOIS müştərimiz |
| **RDAP** | `domen.py` | Domen məlumatının rəsmi, JSON formatı |
| **Wayback Machine CDX API** | `domen.py` | WHOIS yoxdursa saytın ilk arxiv tarixi (təxmini yaş) |
| **`ssl` + `socket` (stdlib)** | `sertifikat.py` | TLS əl-sıxma, sertifikatın oxunması |
| **`dnspython` (asyncresolver)** | `dns_qeydleri.py` | Asinxron DNS sorğuları |
| **`urllib.robotparser`** | `crawler.py` | `robots.txt` qaydalarına hörmət |
| **`tldextract`** | `base.py` | `www.magaza.az/kataloq` → `magaza.az` (ikili suffikslər də düzgün: `.co.uk`) |
| **`hashlib` (SHA-256)** | `metn.py`, `decorators.py` | Səhifə barmaq izi (dəyişiklik aşkarlanması) və keş açarları |
| **`urllib.parse` (urljoin, urldefrag)** | `base.py`, `crawler.py` | URL normallaşdırma |
| **`functools.wraps` + `inspect`** | `decorators.py` | Dekoratorların həm sync, həm async funksiyaları dəstəkləməsi |
| **Context managers (`with` / `async with`)** | hər yerdə | DB sessiyası, httpx client, socket |
| **Exception handling + fallback zənciri** | hər yerdə | RDAP → WHOIS → python-whois → Wayback; Postgres → SQLite; Redis → yaddaş |
| **`pathlib`** | `config.py`, `builder.py` | Fayl yolları |
| **Environment variables + `.env`** | `config.py` | `pydantic-settings` ilə |
| **pytest + parametrize** | `tests/` | 54 test (artmaqda) |
| **ReportLab** | `builder.py` | PDF hesabat |
| **HTML / CSS / JavaScript (vanilla)** | `frontend/` | İnterfeys — açıq/qaranlıq rejim dəstəyi ilə |

---

## Öz yazdığımız dekoratorlar — nümunə

Kurs mövzusu olan "dekoratorlar" burada süni nümunə deyil, layihənin işləmə şərtidir:

```python
@safe_collector("domen")      # xəta olsa analiz dayanmır, nəticəyə "ugurlu: False" yazılır
@timed                        # neçə saniyə çəkdiyini loglayır
@cached(saniye=86400)         # nəticəni Redis-də saxlayır (domen məlumatı gün ərzində dəyişmir)
@retry(cehd=2, gozleme=1.0)   # şəbəkə sınsa təkrar cəhd edir
async def topla(url: str) -> dict:
    ...
```

Sıralama vacibdir: `safe_collector` ən xaricdədir ki, `retry` bütün cəhdləri bitirəndən
sonra qalan xətanı tutub analizi dayandırmasın.

> **Yol boyu tapılan səhv:** `@cached` əvvəlcə açarı yalnız `func.__name__`-dən qururdu.
> Bütün toplayıcılarda funksiya `topla` adlandığı üçün `domen`, `dns`, `geo` və
> `sertifikat` **eyni keş xanasını paylaşırdı** və bir-birinin nəticəsini qaytarırdı.
> İndi açar `modul + funksiya adı`-ndan qurulur; `test_cached_eyni_adli_funksiyalar_toqqusmur`
> testi bunun qayıtmasına imkan vermir.
