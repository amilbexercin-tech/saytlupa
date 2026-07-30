# SaytLupa — Qurulma, işə salma və nümayiş

## 1. Ən sadə yol (heç nə quraşdırmadan)

```bash
cd /d D:\SaytLupa
.venv\Scripts\activate
uvicorn backend.main:app --reload
```

Brauzerdə: <http://localhost:8000>

Bu halda layihə **SQLite + yaddaşdaxili keş + mock LLM** ilə işləyir.
Analiz, gəziş və canlı gedişat tam görünür.

---

## 2. Sıfırdan qurulma (başqa maşında)

```bash
git clone <repo>  &&  cd SaytLupa

py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env      # açarları doldur (məcburi deyil)
uvicorn backend.main:app --reload
```

> **Qeyd:** Python 3.14 sınanıb — `psycopg2-binary`, `pgvector`, LangChain 1.3 və
> `mcp` paketlərinin hamısı problemsiz qurulur.

---

## 3. Tam mühit (PostgreSQL + Redis + n8n)

RAM az olan maşınlar üçün xidmətlər **profillərə** bölünüb — hamısını birdən
qaldırmaq lazım deyil:

```bash
# Baza və keş (~450 MB)
docker compose --profile core up -d

# pgvector genişlənməsi (bir dəfə)
docker exec saytlupa-db-1 psql -U saytlupa -d saytlupa -c "CREATE EXTENSION IF NOT EXISTS vector;"

# n8n — yalnız avtomatlaşdırma nümayişi üçün (~500 MB)
docker compose --profile n8n up -d
```

`.env`-də:
```
DATABASE_URL=postgresql+psycopg2://saytlupa:saytlupa@localhost:5432/saytlupa
REDIS_URL=redis://localhost:6379/0
```

Yoxlama:
```bash
curl http://localhost:8000/api/health
# {"baza":"postgresql","kes":"redis","claude":true,"gemini":true,"gemma":true}
```

---

## 4. Gemma (lokal açıq model)

```bash
ollama pull gemma3:4b        # ~3.3 GB
ollama run gemma3:4b         # sınaq
```

Modellər `D:\.ollama\models` qovluğunda saxlanılır (`OLLAMA_MODELS` dəyişəni ilə).

Model müqayisəsini yenidən aparmaq üçün:
```bash
py scripts/model_olcme.py                 # bütün gemma modelləri
py scripts/model_olcme.py gemma3:4b       # yalnız biri
```

---

## 5. API açarları

| Açar | Haradan | Məcburidirmi |
|---|---|---|
| `ANTHROPIC_API_KEY` | <https://console.anthropic.com> | Yox — olmasa mock rejim |
| `GOOGLE_API_KEY` | <https://aistudio.google.com/apikey> (pulsuz) | Yox — olmasa lokal embedding |
| `PAGESPEED_API_KEY` | <https://developers.google.com/speed/docs/insights/v5/get-started> (pulsuz) | Yox — olmasa öz ölçmələrimiz |

---

## 6. Testlər

```bash
pytest -q                    # hamısı
pytest tests/test_crawler.py -v
```

Testlər **şəbəkəsizdir** — saxta HTML üzərində işləyir, internet tələb etmir.
Şəbəkə lazım olan yerdə `respx` ilə saxta cavab verilir (MCP alətləri belə
sınanır).

---

## 7. n8n və MCP qoşulması

### n8n workflow-ları

`n8n/` qovluğunda 4 JSON var. n8n-də **Workflows → ⋯ → Import from File**
(və ya faylın içindəkini kopyalayıb boş canvas-da `Ctrl+V`). Hər fayl **ayrıca**
workflow-dur.

| Workflow | Lazım olan credential |
|---|---|
| 1 — Analiz tetikleyicisi | Postgres: host `host.docker.internal`, port `5432`, baza/istifadəçi/parol = `saytlupa` |
| 2 — Rəqib izləmə | Telegram (bot tokeni) |
| 3 — Error Workflow | Telegram; `Chat ID` sahəsinə öz nömrəni yaz (n8n konteyneri `.env`-i görmür) |
| 4 — Gemma agenti | Ollama: Base URL `http://host.docker.internal:11434` |

Sonra 1, 2 və 4-də **⋯ → Settings → Error Workflow → "SaytLupa 3"** seç.

n8n konteynerdən host maşına `host.docker.internal` ilə çıxır. Yoxlamaq üçün:
```bash
docker exec n8n wget -qO- http://host.docker.internal:8000/api/health
```

### MCP serveri

```bash
claude mcp add saytlupa -- "D:/SaytLupa/.venv/Scripts/python.exe" "D:/SaytLupa/backend/mcp_server.py"
claude mcp list        # saytlupa … ✔ Connected
```

> Bu əmri **Git Bash** və ya `cmd`-də işlət — PowerShell `--` ayırıcısını udur
> (`unknown option` xətası verir).

---

## 8. Nümayiş ssenarisi (müəllimə göstərmək üçün)

> Bütün addımlar işləyir (2026-07-29 vəziyyəti). Şərt: uvicorn pəncərəsi açıq
> olsun; n8n və MCP addımları üçün 7-ci bölmədəki qoşulma bir dəfə edilməlidir.

### Addım 1 — Sistem vəziyyəti
Ana səhifəni aç. Aşağıda **Baza / Keş / Claude / Gemini / Gemma** göstəriciləri var —
hansı komponentin qoşulu olduğu dərhal görünür.

### Addım 2 — Analiz və canlı gedişat
`https://asan.gov.az` yaz → **Analiz et**.
Ekranda canlı görünür:
```
[0.3s] domen         hazir
[0.8s] dns           hazir
[1.2s] toplayıcılar  9/9 uğurlu
[1.7s] səhifə  1/12  https://asan.gov.az
[3.1s] səhifə 12/12  https://asan.gov.az/service/...
[3.2s] HAZIR — 12 səhifə yığıldı
```
**Nəyi göstərir:** paralel icra (`asyncio.gather`), SSE, crawler, robots.txt.

### Addım 3 — Dayanıqlılıq
`https://kontakt.az` yaz. Sayt Cloudflare arxasındadır:
```
gəziş — Sayt Cloudflare arxasındadır — bizə real məzmun əvəzinə yoxlama
        səhifəsi verildi. Məzmun analizi və RAG bu sayt üçün etibarsızdır.
HAZIR — 0 səhifə
```
**Nəyi göstərir:** sistem yalan hesabat qurmur, məhdudiyyəti dürüst bildirir.

### Addım 4 — Dəqiq olmayan məlumatın işarələnməsi
`.az` domenlərində domen yaşı bölməsində:
> *"Bu TLD üçün pulsuz WHOIS yoxdur… Arxiv.org-a görə sayt ən azı 2010 ilindən
> mövcuddur (~15.6 il). Bu TƏXMİNİ göstəricidir."*

`github.com` isə RDAP-dan dəqiq **18.8 il** verir.
**Nəyi göstərir:** "heç vaxt uydurma rəqəm yazılmır" prinsipi koda yazılıb.

### Addım 5 — Saytla söhbət (RAG)
Analiz bitəndən sonra söhbət bölməsində sual ver:
> *"Sifarişli xidmətlər hansılardır?"*

Cavab **mənbə linki ilə** gəlir. Sonra ikinci sual ver — sistem əvvəlki sualı
xatırlayır (yaddaş).
**Nəyi göstərir:** chunking, embedding, pgvector, hibrid axtarış, re-ranking, memory.

### Addım 6 — Təhvil düymələri
Nəticə səhifəsindəki **Təhvil** kartında dörd düymə var:

| Düymə | Nə çıxır | Açar |
|---|---|---|
| ⚡ Müasir versiyanı qur | yeni tək fayllıq HTML, brauzerdə önizləmə + yükləmə | Claude/Gemini lazımdır |
| 🧬 Tam klon üçün hazırla | `ai-website-cloner` üçün 5 sənəd + hazır `/clone-website` əmri | lazım deyil |
| 📦 Səhifə arşivi | HTML + CSS + şəkillər, ZIP | lazım deyil |
| 📄 PDF hesabat | bütün analiz bir faylda | lazım deyil |

Klon sənədlərini aç və göstər: tapılmayan hər şey `NOT DETECTED` kimi
işarələnib — **uydurulmayıb**. Arşivdən xarici skriptlər silinib.
**Nəyi göstərir:** alətlərin düzgün bölgüsü (SaytLupa hazırlayır, cloner skill
qurur), etik crawl, uydurmasız hesabat.

### Addım 7 — Model bölgüsü
Terminalda:
```bash
py scripts/model_olcme.py
```
Cədvəl çıxır: hansı model neçə faiz dəqiqdir, neçə saniyə çəkir.
**Nəyi göstərir:** LLM anatomiyası — iddia yox, ölçmə.

### Addım 8 — İzləmə düyməsi
Nəticə səhifəsində **🔔 Bu saytı izlə** düyməsini bas. Sayt n8n cron-una qoşulur;
düymə "🔕 İzləməni dayandır"a çevrilir. Yoxlama:
```bash
curl http://localhost:8000/api/izleme
```
**Nəyi göstərir:** interfeys → API → baza → n8n zənciri.

### Addım 9 — n8n avtomatlaşdırması
n8n-i aç (<http://localhost:5678>) və dörd workflow-u sırayla göstər:

| Workflow | Nə göstərir | Necə nümayiş etdirilir |
|---|---|---|
| 1 — Analiz tetikleyicisi | Webhook, JS Code, **Postgres node** | "Execute workflow" → `curl` ilə webhook çağır → node-lar yaşıllanır → `n8n_jurnal` cədvəlinə bax |
| 2 — Rəqib izləmə | cron, **batch**, **retry 3×**, `onError` marşrutu | "Execute workflow" → dəyişiklik varsa Telegram mesajı gəlir |
| 3 — Error Workflow | mərkəzi xəta idarəsi | "Execute workflow" (n8n nümunə xəta verir) → `curl http://localhost:8000/api/xetalar` |
| 4 — Gemma agenti | **lokal açıq model** + Switch marşrutu | `curl` ilə üç fərqli sual göndər: siyahı · söhbət · analiz |

Sınaq sorğusu (WF4):
```bash
curl.exe -X POST http://localhost:5678/webhook/saytlupa-agent \
  -H "Content-Type: application/json" -d "{\"sual\":\"hansi saytlar var?\"}"
```

**Nəyi göstərir:** n8n production naxışları — retry, error workflow, batch,
lokal modelin avtomatlaşdırmaya qoşulması.

### Addım 10 — MCP
Claude Code-u `D:\SaytLupa` qovluğundan aç və yaz:

> *"asan.gov.az ilə kontakt.az-ı müqayisə et"*

Cavabda 9 ölçülü cədvəl, texnologiya fərqi və SEO çatışmazlıqları çıxır.
Qoşulma yoxlaması: `claude mcp list` → `saytlupa … ✔ Connected`.
**Nəyi göstərir:** layihə başqa alətlərə **tool** kimi verilib; MCP serveri
işi özü görmür, FastAPI-yə ötürür.

> Şərt: uvicorn pəncərəsi açıq olmalıdır — yoxsa alət "server cavab vermir" deyir.

---

## 9. Tez-tez qarşılaşılan hallar

| Problem | Səbəb | Həll |
|---|---|---|
| `/api/health` `"baza":"sqlite"` göstərir | Postgres qalxmayıb | `docker compose --profile core up -d` |
| n8n node-u `ECONNREFUSED` verir | n8n konteynerdən host-a çıxa bilmir | URL-dəki `host.docker.internal`-ı `localhost` ilə əvəz et (n8n Docker-də deyilsə) |
| WF2 `İzlənən saytlar`-dan o yana keçmir | Bütün saytlar son 20 saatda yoxlanıb, siyahı boşdur | Normal davranışdır; sınamaq üçün node-dakı `min_saat` dəyərini `0` et |
| MCP aləti "server cavab vermir" deyir | uvicorn işləmir | `uvicorn backend.main:app --reload` |
| `claude mcp add` → `unknown option '-m'` | PowerShell `--` ayırıcısını udur | Əmri Git Bash və ya `cmd`-də işlət |
| Analiz "0 səhifə" verir | Sayt bot qoruması altındadır | Normal davranışdır — səbəb ekranda yazılır |
| PageSpeed balı yoxdur | Açar təyin edilməyib | `.env` → `PAGESPEED_API_KEY` |
| Gemma cavab vermir | Ollama işləmir | `ollama serve` və ya Ollama tətbiqini aç |
| İlk Gemma cavabı 25 saniyə çəkir | Model yaddaşa yüklənir | Normaldır — sonrakılar ~6 saniyə |
| Docker C: diski doldurur | Disk image C:-dədir | Settings → Resources → Advanced → Disk image location = `D:\DockerData` |
