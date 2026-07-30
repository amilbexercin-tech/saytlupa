# SaytLupa 🔍

**Link yaz → saytı tanı → saytla danış → daha yaxşısını qur.**

İstənilən saytın linkini verirsən; proqram onu hərtərəfli analiz edir, AI peşəkar
hesabat yazır, saytın məzmunu ilə **söhbət edə bilirsən** (mənbə göstərməklə), və
istəsən saytın **müasir versiyasını** qurdurursan.

> AI Engineering kursunun aylıq layihəsi. Dizayn sənədi:
> [`docs/specs/2026-07-28-saytlupa-design.md`](docs/specs/2026-07-28-saytlupa-design.md)

---

## İşə salma

```bash
cd /d D:\SaytLupa
.venv\Scripts\activate
copy .env.example .env          # açarları doldur (məcburi deyil)
uvicorn backend.main:app --reload
```

Brauzerdə: <http://localhost:8000>

Heç bir açar və ya xidmət olmasa da işləyir:

| Yoxdursa | Nə olur |
|---|---|
| PostgreSQL | SQLite-a keçir (`data/saytlupa.db`) |
| Redis | yaddaşdaxili keşə keçir |
| Ollama / Gemma | re-ranking Gemini-yə keçir |
| API açarları | mock rejim — axın və interfeys görünür |

Modellər: `gemini-3.6-flash` (mətn) · `gemini-embedding-001` (embedding, 768 ölçüyə
qısaldılır) · `gemma3:4b` (lokal ehtiyat). Ölçmələr: [`docs/model-secimi.md`](docs/model-secimi.md).

## Təhvil düymələri

Analiz bitəndən sonra nəticə səhifəsində dörd düymə çıxır:

| Düymə | Nə edir | Açar lazımdır? |
|---|---|---|
| ⚡ Müasir versiyanı qur | Analizə əsasən yeni, təmiz tək fayllıq HTML yazır → `storage/modern/` | **bəli** (Claude və ya Gemini) |
| 🧬 Tam klon üçün hazırla | `ai-website-cloner` üçün 5 araşdırma sənədi + hazır `/clone-website` əmri → `storage/klon/` | xeyr |
| 📦 Səhifə arşivi | Ana səhifənin HTML + CSS + şəkilləri → `storage/archives/` + ZIP | xeyr |
| 📄 PDF hesabat | Bütün analiz bir faylda → `storage/pdf/` | xeyr |
| 🔔 Bu saytı izlə | Saytı n8n cron-una qoşur; səhifə dəyişsə Telegram-a xəbər gedir | xeyr |

Arşivdə **xarici skriptlər saxlanılmır** — arşiv açılanda heç bir izləyiciyə
sorğu getmir. `robots.txt` icazə vermirsə arşiv qurulmur.

## Testlər

```bash
pytest -q
```

## Docker (xidmətlər)

RAM 7.8 GB olduğuna görə xidmətlər **profillərə** bölünüb — hamısını birdən
qaldırmaq lazım deyil:

```bash
docker compose --profile core up -d    # PostgreSQL (pgvector 0.8.5) + Redis
docker compose --profile n8n  up -d    # n8n — yalnız yeni maşında lazımdır (port 5679)
```

Bu maşında artıq **5678 portunda işləyən n8n var** (self-hosted-ai-starter-kit) —
layihənin workflow-ları orada qurulur, ikinci n8n qaldırmağa ehtiyac yoxdur.

Docker-in disk image-i `D:\DockerData` qovluğuna köçürülüb (C: diskdə 11.7 GB azad oldu).

## MCP — Claude Code / Cursor-dan istifadə

```bash
claude mcp add saytlupa -- "D:/SaytLupa/.venv/Scripts/python.exe" "D:/SaytLupa/backend/mcp_server.py"
```

> PowerShell `--` ayırıcısını udur (`unknown option` xətası verir) — bu əmri
> Git Bash-da və ya `cmd`-də işlət. Faylın tam yolu ilə çağırılır ki, hansı
> qovluqdan işə salınmasından asılı olmasın. Yoxlama: `claude mcp list` →
> `saytlupa … ✔ Connected`.

| Tool | Nə edir |
|---|---|
| `sayt_analiz_et(url, max_sehife)` | analizi fonda başladır, `analiz_id` qaytarır |
| `saytla_danis(sayt, sual)` | RAG cavabı + mənbə linkləri (`sayt` = domen, ünvan və ya id) |
| `saytlari_muqayise_et(sayt1, sayt2)` | iki saytı yan-yana qoyur (sürət, texnologiya, SEO, AI rəyi) |

MCP serveri **özü iş görmür** — işləyən FastAPI-yə HTTP sorğusu göndərir
(`API_URL`, standart `http://localhost:8000`). Səbəb: crawler, embedding və LLM
Claude Code-un işə saldığı kiçik prosesdə yox, serverdə işləməlidir. Server
bağlıdırsa alət aydın mesaj qaytarır, susmur.

`.env`-də `N8N_WEBHOOK_URL` doldurulsa, `sayt_analiz_et` analizi n8n Workflow 1
üzərindən başladır.

Müqayisə həm də REST-dədir: `GET /api/muqayise?sayt1=asan.gov.az&sayt2=kontakt.az`.

## n8n — 4 workflow

JSON-lar `n8n/` qovluğundadır. n8n-də **Workflows → ⋯ → Import from File**:

| Fayl | Nə edir | Nə lazımdır |
|---|---|---|
| `1-analiz-tetikleyici.json` | Webhook `POST /webhook/saytlupa-analiz` → analiz → nəticə `n8n_jurnal` cədvəlinə | Postgres credential |
| `2-reqib-izleme.json` | Hər gün 09:00 → izlənən saytları yenidən gəzir → dəyişiklik varsa Telegram | Telegram credential |
| `3-xeta-workflow.json` | Digər workflow sınanda → `job_errors` + Telegram | Telegram credential |
| `4-gemma-agenti.json` | Webhook `POST /webhook/saytlupa-agent` → Gemma sualı təsnif edir → Switch uyğun endpoint-ə yönləndirir | Ollama credential |

n8n konteynerdən FastAPI-yə `http://host.docker.internal:8000` ünvanı ilə çıxır.
3-cü workflow-u digər üçünün **Settings → Error workflow** sahəsində seçmək lazımdır.

Dördü də 2026-07-29-da canlı n8n-də (port 5678) sınaqdan keçib: webhook → analiz →
Postgres, cron → dəyişiklik → Telegram, xəta → `job_errors` → Telegram, təsnifat →
üç budaq.

İzləməyə sayt qoymaq:

```bash
curl -X POST http://localhost:8000/api/izleme \
  -H "Content-Type: application/json" \
  -d "{\"site_id\": 1, \"cron\": \"0 9 * * *\", \"telegram_chat_id\": \"...\"}"
```

| Endpoint | Nə edir |
|---|---|
| `GET /api/izleme?min_saat=20` | izlənən saytlar (təzə yoxlananlar süzülür) |
| `POST /api/izleme` · `DELETE /api/izleme/{site_id}` | izləməni açır / bağlayır |
| `POST /api/izleme/{site_id}/yoxla` | saytı yenidən gəzir, fərqi qaytarır |
| `POST /api/xetalar` · `GET /api/xetalar` | n8n Error Workflow-un jurnalı |

## Quruluş

```
backend/
  config.py       parametrlər (pydantic-settings)
  main.py         FastAPI — REST + SSE + WebSocket
  schemas.py      Pydantic modelləri
  db.py           SQLAlchemy — Postgres(pgvector) / SQLite fallback
  cache.py        Redis keş + fallback
  decorators.py   @cached, @retry, @timed, @safe_collector
  collectors/     9 analiz toplayıcısı + bot qoruması aşkarlanması
  crawler.py      sayt gəzişi (robots.txt, sitemap, BFS)
  metn.py         HTML → təmiz mətn + barmaq izi
  hadise.py       SSE üçün hadisə brokeri
  analiz.py       analiz axını (toplayıcılar → gəziş → RAG → baza)
  llm.py          Claude / Gemini / Gemma — vahid interfeys
  rag/chunker.py  mətnin parçalanması (800 simvol, 120 üst-üstə)
  rag/embedder.py Gemini embedding + lokal ehtiyat üsul + keş
  rag/store.py    pgvector + hibrid axtarış (vektor + açar söz, RRF)
  rag/reranker.py Gemma ilə yenidən sıralama (seçim edilə bilən)
  rag/memory.py   söhbət yaddaşı
  chains/model.py model fallback zənciri (Claude → Gemini → Gemma)
  chains/hesabat.py    LCEL: xam analiz → 6 bəndlik AI rəy (JSON sxemi ilə)
  chains/rag_cavab.py  LCEL: sual + mənbə + yaddaş → cavab
  chains/muasir.py     LCEL: analiz → tək fayllıq müasir HTML (Gemma-sız)
  prompts/        promptlar ayrıca (hesabat, rag, muasir)
  builder/kontekst.py  dörd təhvil düyməsi üçün ortaq məlumat və qovluqlar
  builder/muasir.py    ⚡ müasir versiyanı qurur və saxlayır
  builder/klon.py      🧬 ai-website-cloner üçün 5 araşdırma sənədi
  builder/arsiv.py     📦 səhifə arşivi (HTML + CSS + şəkillər, ZIP)
  builder/pdf.py       📄 PDF hesabat (reportlab, Azərbaycan şrifti ilə)
  izleme.py       sayt izləmə: barmaq izi müqayisəsi + iş xətaları jurnalı
  muqayise.py     iki saytın analizini yan-yana qoyur
  mcp_server.py   MCP serveri (stdio) — 3 tool Claude Code/Cursor-a verilir
frontend/         interfeys (HTML + JS)
n8n/              4 workflow JSON
tests/            pytest
docs/specs/       dizayn sənədi
storage/          yığılan səhifələr, arşivlər, PDF-lər
docs/ekran/       10 ekran görüntüsü (işləyən sistemdən)
```

## Vəziyyət

> Son yenilənmə: **2026-07-29** · 174 test keçir · hər üç model qoşuludur
> (Claude sonnet-5 · Gemini 3.6 flash · gemma3:4b)

| Gün | İş | Status |
|---|---|---|
| 1 | Skelet: FastAPI, Pydantic, SQLAlchemy, Redis, Docker, dekoratorlar | ✅ |
| 2-3 | 9 collector + bot qoruması aşkarlanması | ✅ |
| 4 | Crawler (robots.txt + sitemap) + səhifə saxlama + SSE canlı gedişat | ✅ |
| 5-6 | RAG: chunking, embedding, pgvector, hibrid axtarış, re-ranking, yaddaş | ✅ |
| 7 | LangChain / LCEL zəncirləri + promptlar | ✅ |
| 8 | İnterfeys: nəticə səhifəsi, qrafiklər, söhbət pəncərəsi | ✅ |
| 9 | Təhvil: müasir versiya · klon hazırlığı · arşiv · PDF | ✅ |
| 10 | n8n (4 workflow + Gemma agenti) + izləmə xidməti | ✅ |
| 11 | MCP serveri (3 tool) + sayt müqayisəsi + testlər | ✅ |
| 12 | Sənədləşdirmə + 10 ekran görüntüsü + model ölçməsi | ✅ |

## Etik qeyd

Bu alət öyrənmək, analiz və ilham üçündür. Crawler `robots.txt`-ə hörmət edir,
sorğu tezliyi məhdudlaşdırılır. Analizdə **heç vaxt uydurma rəqəm yazılmır** —
dəqiq bilinməyən məlumat "təxmini" işarəsi ilə verilir və ya boş saxlanılır.
