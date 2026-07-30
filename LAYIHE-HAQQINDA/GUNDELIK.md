# SaytLupa — İş gündəliyi

Hər iş günündə nə edildiyi, nəyin işlədiyi və nəyin işləmədiyi burada saxlanılır.

---

## 2026-07-28 (1-ci gün) — Gün 1-8 tamamlandı

Bir gündə planın **8 mərhələsi** bitdi. Layihə işləyən vəziyyətdədir.

### ✅ Bitən işlər

| Mərhələ | Nə edildi |
|---|---|
| **Gün 1** | Skelet: FastAPI, Pydantic, SQLAlchemy (8 cədvəl), Redis keş, Docker profilləri, 4 öz dekoratorumuz |
| **Gün 2-3** | 9 analiz toplayıcısı + bot qoruması aşkarlanması |
| **Gün 4** | Crawler (robots.txt → sitemap → BFS), mətn təmizləmə, SSE canlı gedişat |
| **Gün 5-6** | RAG: chunking, embedding, pgvector, hibrid axtarış + RRF, re-ranking, söhbət yaddaşı |
| **Gün 7** | LangChain/LCEL zəncirləri, promptlar ayrıca modulda, model fallback zənciri |
| **Gün 8** | İnterfeys: 10 bölmə, qrafiklər, söhbət pəncərəsi, mobil uyğunluq |

### 🔧 İnfrastruktur qurulması

- Layihə **D: diskinə** köçürüldü (C:-də yalnız 10.5 GB boş idi)
- Docker-in disk image-i `D:\DockerData`-ya köçürüldü → **C:-də 11.7 GB azad oldu** (10.5 → 22.2 GB)
- PostgreSQL 16 + **pgvector 0.8.5** (HNSW + GIN indeksləri), Redis 7 qaldırıldı
- Ollama-ya `gemma3:1b` və `gemma3:4b` yükləndi (modellər onsuz da D:-də saxlanılır)
- Python 3.14 yoxlanıldı — bütün paketlər (psycopg2, pgvector, LangChain 1.3, mcp) problemsiz quruldu

### 📊 Ölçülmüş nəticələr

| Göstərici | Dəyər |
|---|---|
| Tam analiz + 15 səhifə gəzişi + RAG | **8.6 saniyə** |
| 9 toplayıcının paralel icrası | 1.2 saniyə |
| RAG indeksi (15 səhifə → 60-81 parça) | 4.1 san (təkrarda keşlə **0.9 san**) |
| RAG axtarış dəqiqliyi (10 suallıq dəst) | Hit@1 6/10 · Hit@3 9/10 · MRR 0.70 |
| Testlər | **97 keçir** |
| Kod həcmi | ~5 200 sətir |

### ✅ Nə işləyir

- Sayt analizi — 9 toplayıcının hamısı (`asan.gov.az`-da 9/9)
- `.az` domenləri — WHOIS olmadıqda Wayback ilə **təxmini** yaş, açıq işarələnir
- Bot qoruması aşkarlanması — `kontakt.az` (Cloudflare) düzgün tanınır, saxta analiz qurulmur
- Crawler — robots.txt-ə hörmət, sitemap oxuma, təkrar səhifə süzgəci
- RAG — sual verirsən, cavab **mənbə linki ilə** gəlir, yaddaş işləyir
- İnterfeys — 10 bölmə, canlı gedişat, açıq/qaranlıq rejim, mobil uyğun
- Dayanıqlılıq — Postgres yoxsa SQLite, Redis yoxsa yaddaş, açar yoxsa mock; heç nə çökmür

### ⚠️ Nə hələ işləmir (və niyə)

> **Sonrakı qeyd:** bu cədvəldəki problemlərin hamısı ertəsi gün açar gələndə
> həll olundu — bax [«Google açarı gəldi»](#-google-açarı-gəldi-həmin-gün-sonra).

| Problem | Səbəb | Nə vaxt həll olunacaq |
|---|---|---|
| **AI hesabat yazılmır** | `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` yoxdur. Lokal Gemma ilə yazmaq 198 saniyə çəkir — analizi bloklayır, ona görə buraxılır | Açar əlavə ediləndə **öz-özünə işə düşəcək**, kod hazırdır |
| **Embedding zəifdir** | Gemini açarı yoxdur → lokal hashing üsulu işlədilir. Sinonimləri tutmur, yalnız söz oxşarlığına baxır | `GOOGLE_API_KEY` əlavə ediləndə |
| **Söhbət cavabı yavaşdır (~110 san)** | Cavabı Claude yox, `gemma3:4b` yazır | Claude açarı ilə 3-5 saniyəyə düşəcək |
| **PageSpeed balı alınmır** | Google PageSpeed açarı yoxdur (pulsuz) | `.env` → `PAGESPEED_API_KEY` |
| **Re-ranking söndürülüb** | Ölçüldü: Gemma 50 saniyə əlavə edir, Hit@1-i 6→7 qaldırır, Hit@3-ü 9→8 salır. Qiymətinə dəymir | Gemini açarı ilə yenidən ölçüləcək (bulud modeli ~1-2 san) |

### 🐛 Tapılan və düzəldilən 14 səhv

Ən əhəmiyyətliləri:

1. **Keş açarları toqquşurdu** — bütün toplayıcılarda funksiya `topla` adlanır, `@cached` isə açarı yalnız funksiya adından qururdu. `domen`, `dns`, `geo`, `sertifikat` **bir-birinin nəticəsini oxuyurdu**.
2. **Model JSON sahə adını "düzəldirdi"** — `seo_catismazliqlari` əvəzinə `seo_catismazlıqlari` qaytardı, Pydantic sındı, **198 saniyəlik hesabat itdi**.
3. **Performans zolaqları görünmürdü** — DOM düzgün, ekranda boş. `<span>` inline olduğu üçün `width` tətbiq olunmurdu.
4. **Şrift regex-i dırnaqda dayanırdı** — `font-family: 'Inter', sans-serif` yazılışında saytın öz şrifti heç vaxt tutulmurdu.
5. `.az` domenləri, arxiv.org 498 xətası, HTTP başlığında Azərbaycan hərfi, ana səhifənin iki dəfə yığılması…

Tam siyahı: [`QERARLAR.md`](QERARLAR.md) → "Yol boyu tapılan səhvlər".

### 📚 Yazılan sənədlər

`LAYIHE-HAQQINDA/`: README (ideya, texnologiya xəritəsi, etika), TEXNOLOGIYALAR (kurs mövzusu → fayl), MEMARLIQ (modullar, baza, axınlar), QERARLAR (10 qərar + 14 səhv), ISTIFADE (qurulma + 8 addımlıq nümayiş), GUNDELIK (bu fayl).

`docs/`: model-secimi.md (3 modelin ölçülməsi), olcme-desti.json (10 sual), rag-olcme-neticesi.json, specs/ (ilkin dizayn).

---

## 2026-07-29 (2-ci gün) — Gün 9 tamamlandı

Dörd təhvil düyməsi hazırdır. Kök qovluqdakı 11 boş zibil fayl (sınmış shell
əmrlərindən qalan `0]`, `dict`, `tuple[list[dict]` və s.) silindi.

### ✅ Bitən işlər

| Düymə | Modul | Nəticə |
|---|---|---|
| ⚡ Müasir versiyanı qur | `chains/muasir.py` + `builder/muasir.py` | `storage/modern/<domain>/index.html` |
| 🧬 Tam klon üçün hazırla | `builder/klon.py` | `storage/klon/<domain>/docs/research/` — 5 sənəd + `EMR.md` |
| 📦 Səhifə arşivi | `builder/arsiv.py` | `storage/archives/<domain>/` + ZIP |
| 📄 PDF hesabat | `builder/pdf.py` | `storage/pdf/<domain>/hesabat.pdf` |

Əlavə: 5 yeni endpoint + yükləmə endpoint-i, interfeysdə «Təhvil» kartı,
27 yeni test (**cəmi 124 test keçir**).

### 🔍 Qərarlar

| Qərar | Səbəb |
|---|---|
| Müasir versiya zəncirindən **Gemma çıxarıldı** | Lokal model tam səhifə HTML-i bu maşında dəqiqələrlə yazır və nəticə yararsız olur. Açar yoxdursa düymə səbəbi izah edir, uydurmur |
| Klon sənədləri **ingiliscədir** | Onları oxuyan tərəf cloner şablonudur; `INSPECTION_GUIDE.md` və `AGENTS.md` ingiliscədir, terminlər uyğun gəlməlidir. İstifadəçiyə ünvanlanan `EMR.md` azərbaycancadır |
| SaytLupa cloner qovluğuna **özü yazmır** | Başqa layihənin içini dəyişmək təhlükəlidir. Sənədlər `storage/klon/`-a yazılır, hazır `xcopy` əmri verilir |
| Arşivdən **xarici skriptlər silinir** | Arşiv açılanda izləyicilərə sorğu getməsin |
| PDF-də **sistem şrifti axtarılır** | reportlab-ın Helvetica-sı `ə`, `ğ`, `ş`, `ı` hərflərini tanımır — Arial/Segoe/Calibri/DejaVu sırayla yoxlanılır |

### 🐛 Yol boyu tutulan tələlər

1. **PDF cədvəl xanaları `Paragraph` olmalıdır** — adi mətn xanası sətrə sığmayanda kəsilmir, səhifədən çölə daşır. Uzun ünvanlar və meta description hesabatı korlayırdı.
2. **`&` və `<` PDF-i sındırır** — reportlab xanaları XML kimi oxuyur; bütün dinamik mətn qaçırılır (`qacir`).
3. **Şərh `<!doctype>`-dan əvvəl gəlməməlidir** — müasir versiyanın başına qoyulan mənşə qeydi doctype-dan qabaq olsa brauzer quirks rejiminə keçir.
4. **CSS içindəki `url(...)`** — arşivdə yalnız `<img>` və `<link>` yönləndirilsə fon şəkilləri qırılır; CSS bir səviyyə dərinliyə qədər açılır.
5. **Emoji PDF-də boş qutu çıxır** — sistem şriftlərində emoji qlifi yoxdur, başlıqdan çıxarıldı.

### 📊 Ölçmə (sınaq: `example.com` + lokal sınaq saytı)

| İş | Nəticə |
|---|---|
| PDF hesabat | 78.9 KB, Arial alt-dəsti yerləşdirilir (Azərbaycan hərfləri düzgün) |
| Klon sənədləri | 6 fayl, tapılmayan hər şey `NOT DETECTED` kimi işarələnir |
| Arşiv (CSS + 3 şəkil + ikon) | 6 fayl, 1 xarici skript silindi, `url()` yönləndirildi |
| Müasir versiya | açar yoxdur → səbəb göstərilir, çökmür |

### 🔑 Google açarı gəldi (həmin gün, sonra)

`GOOGLE_API_KEY` `.env`-ə yazıldı. Açar işlədi, amma **iki model adı köhnəlmişdi**:

| Köhnə ad | Nə oldu | Yeni ad |
|---|---|---|
| `gemini-2.5-flash` | 404: *"no longer available to new users"* | **`gemini-3.6-flash`** |
| `text-embedding-004` | siyahıda ümumiyyətlə yoxdur | **`gemini-embedding-001`** |

> Modellərin siyahısı `GET https://generativelanguage.googleapis.com/v1beta/models`
> ilə alındı. `models.list` köhnə modeli **hələ də göstərir**, amma çağırışda 404
> verir — siyahıya inanmaq kifayət deyil, çağırıb yoxlamaq lazımdır.

**Embedding ölçüsü.** `gemini-embedding-001` standart olaraq 3072 ölçü verir,
bizim baza sütunu isə 768-dir. `output_dimensionality=768` verildi; ölçüldü ki,
qısaldılmış vektorun norması 1 deyil (~0.59), ona görə `_normalla()` əlavə edildi.

### 📊 Açarla ölçülmüş nəticələr

| Göstərici | Açarsız (dünən) | Açarla |
|---|---|---|
| AI hesabat | yazılmırdı | **19.3 san** (gemini-3.6-flash) |
| RAG söhbət cavabı | ~110 san (gemma3:4b) | **14.5 san** |
| Embedding | lokal hashing | Gemini, sinonim oxşarlığı 0.936 / əlaqəsiz 0.623 |
| ⚡ Müasir versiya | işləmirdi | **78.6 san**, 51 KB tək fayllıq HTML |

Müasir versiya yoxlandı (`asan.gov.az`): doctype, `lang="az"`, viewport, **meta
description** (orijinalda yoxdur), OG teqləri, semantik HTML, qaranlıq rejim,
xarici resurs yoxdur, «lorem ipsum» yoxdur — promptun bütün qaydaları yerinə yetdi.

### 🎯 RAG dəqiqliyi yenidən ölçüldü

`scripts/rag_olcme.py 1 "" gemini` · eyni 10 suallıq dəst · `asan.gov.az`

| Re-ranking | Embedding | Hit@1 | Hit@3 | MRR | Orta vaxt |
|---|---|---|---|---|---|
| yox | lokal (28 iyul) | 6/10 | 9/10 | 0.700 | 0.0 san |
| yox | **Gemini** | **8/10** | **10/10** | **0.900** | 1.8 san |
| gemma3:4b | lokal (28 iyul) | 7/10 | 8/10 | 0.775 | 50.3 san |
| **gemini-3.6-flash** | **Gemini** | **10/10** | **10/10** | **1.000** | 7.3 san |

**Re-ranking qərarı tərsinə döndü.** Dünən söndürülmüşdü (Gemma 50 saniyə əlavə
edib nəticəni yaxşılaşdırmırdı); bulud modeli ~5.5 saniyəyə axtarışı 10/10-a
qaldırır. `.env` → `RERANK=gemini` açıldı. `config.py`-dakı standart dəyər boş
qalır — açarı olmayan maşında özbaşına qoşulmasın.

> Dürüstlük qeydi: 28 iyul ölçməsi 15, bugünkü 20 səhifəlik indeks üzərindədir —
> korpus eyni deyil, rəqəmlər istiqamət göstərir.

### 🔑 Anthropic açarı da gəldi — sayt lokal qaldırıldı

`ANTHROPIC_API_KEY` `.env`-ə yazıldı. İlk çağırışda **400** gəldi:

```
temperature is deprecated for this model
```

`claude-sonnet-5` artıq `temperature` parametrini qəbul etmir. `backend/llm.py`-da
Claude üçün parametr ötürülmür; imzada qalır (Gemini və Gemma onu hələ də işlədir),
səbəb koda şərh kimi yazıldı.

Yoxlandı: AI hesabat indi **`claude-sonnet-5` ilə 24.2 saniyəyə** yazılır, məzmun
düzgündür. Sayt <http://127.0.0.1:8000> ünvanında qaldırıldı:

```
{"baza":"sqlite","kes":"yaddas","claude":true,"gemini":true,"gemma":true}
```

**Model bölgüsü indi tam işləyir:**

| İş | Model |
|---|---|
| AI hesabat · RAG cavabı · ⚡ müasir versiya | Claude sonnet-5 → Gemini → Gemma |
| Embedding | Gemini `gemini-embedding-001` (768 ölçü) |
| Re-ranking | Gemini `gemini-3.6-flash` |

### 📌 Günün yekunu (2026-07-29)

| Nə | Nəticə |
|---|---|
| Gün 9 — dörd təhvil düyməsi | ✅ hazır, hamısı canlı yoxlanıb |
| Google açarı | ✅ qoşulub, 2 köhnə model adı dəyişdirildi |
| Anthropic açarı | ✅ qoşulub, `temperature` problemi həll edildi |
| RAG dəqiqliyi | 6/10 → **10/10** (Hit@1), MRR 0.70 → **1.00** |
| Testlər | 97 → **124** |
| Kök qovluqdakı zibil fayllar | ✅ silindi (11 ədəd) |

**3 mərhələ qalıb: Gün 10 (n8n), Gün 11 (MCP), Gün 12 (cilalama).**

---

## 2026-07-29 (davamı) — Gün 10: n8n

### ✅ Yazılanlar

| Nə | Harada |
|---|---|
| İzləmə xidməti (fərq hesablama, `job_errors`) | `backend/izleme.py` |
| 6 yeni endpoint (`/api/izleme…`, `/api/xetalar`) | `backend/main.py` |
| `n8n_jurnal` cədvəli — Postgres node bura yazır | `backend/db.py` |
| 4 workflow JSON | `n8n/1…4-*.json` |
| 18 yeni test (124 → **142**) | `tests/test_izleme.py` |

### 🔍 Qərarlar

- **Fərqi Python hesablayır, n8n yox.** Sərhəd qaydası pozulmasın deyə n8n yalnız
  *nə vaxt* və *kimə xəbər* sualını həll edir; hansı səhifənin dəyişdiyini
  `izleme.yoxla()` tapır (səhifə mətninin `sha256` barmaq izi ilə).
- **Boş gəziş dəyişiklik sayılmır.** Sayt bağlı olanda və ya `robots.txt`
  qadağan edəndə crawler boş siyahı qaytarır — bunu "bütün səhifələr silindi"
  kimi oxumaq yalan xəbərdarlıq göndərərdi. Ayrıca yoxlanılır (test var).
- **Dəyişiklik tapılanda RAG indeksi yenilənir.** Köhnə mətn üzərində qurulmuş
  indekslə söhbət istifadəçini yanıldar.
- **Cron n8n-də, `min_saat` Python-da.** Sayt başına ayrı cron üçün `croniter`
  asılılığı lazım gələrdi; əvəzinə n8n gündə bir dəfə işə düşür, backend isə
  son 20 saatda yoxlanmış saytları siyahıdan çıxarır — sayt iki dəfə gəzilmir.
- **Postgres node `executeQuery` ilə işləyir** (`insert` mapping-i n8n
  versiyaları arasında dəyişir), cədvəli isə Python yaradır.

### 🧪 Canlı sınaq (hamısı 5678 portundakı n8n-də)

| Workflow | Nəticə |
|---|---|
| 1 — Analiz tetikleyicisi | ✅ webhook → analiz → Code → **Postgres** (`n8n_jurnal`-da 3 sətir) → cavab |
| 2 — Rəqib izləmə | ✅ cron → siyahı → batch → yoxlama → `deyisdi: true` → **Telegram mesajı gəldi** |
| 3 — Error Workflow | ✅ nümunə xəta → `job_errors`-a 2 qeyd → Telegram |
| 4 — Gemma agenti | ✅ üç niyyət də düzgün təsnif edildi: `siyahi`, `sohbet` (RAG cavabı), `analiz` |

### 🐛 Canlı sınaqda tutulan 2 səhv

**1. Boş siyahı → saxta element → 404.** `İzlənən saytlar` node-unda
`alwaysOutputData: true` qoymuşdum. API boş siyahı qaytaranda (bütün saytlar son
20 saatda yoxlanıbsa) n8n bir **boş** element buraxır, `Saytı yoxla` isə
`site_id`-siz ünvana sorğu göndərib 404 alır. Ayar silindi; `job_errors`-dakı 3
ədəd `site_id=? 404` qeydi məhz bundandır. Təkrarlanmasın deyə test yazıldı.

**2. `gemma3:4b` alət çağırışını dəstəkləmir.** WF4 əvvəlcə AI Agent + 3 HTTP
aləti kimi yazılmışdı. Ollama `/api/show` göstərdi:

| Model | Ölçü | İmkanlar |
|---|---|---|
| `gemma3:1b` | 0.76 GB | completion |
| `gemma3:4b` | 3.11 GB | completion, vision — **tools yoxdur** |
| `gemma4:12b` | 7.04 GB | completion, vision, audio, **tools**, thinking |

Yeganə alət dəstəkləyən model 7 GB-dır, maşında isə 7.8 GB RAM var. Ona görə WF4
yenidən yazıldı: **Gemma sualı təsnif edir (JSON) → n8n Switch üç endpoint-dən
birinə yönləndirir**. Bu, həm bu maşında işləyir, həm də dizayn sənədindəki
təsvirlə ("sualı təsnif edir və uyğun endpoint-ə yönləndirir") üst-üstə düşür.

### 🔔 İzləmə düyməsi

Nəticə səhifəsindəki təhvil düymələrinin yanına beşinci düymə əlavə edildi
(`frontend/index.html`, `app.js`). İki vəziyyətlidir: sayt izlənmirsə
"🔔 Bu saytı izlə", izlənirsə "🔕 İzləməni dayandır". Vəziyyət səhifə açılanda
`GET /api/izleme` ilə oxunur, düymənin üstünə gələndə son yoxlama vaxtı görünür.

### ⚠️ Qalıq

- WF3-də Telegram chat id node-un içinə birbaşa yazılıb: n8n konteyneri layihənin
  `.env` faylını görmür.

---

## 2026-07-29 (davamı) — Gün 11: MCP serveri

### ✅ Yazılanlar

| Nə | Harada |
|---|---|
| MCP serveri (stdio, FastMCP) — 3 tool | `backend/mcp_server.py` |
| Sayt müqayisəsi (9 ölçü + texnologiya + SEO) | `backend/muqayise.py` |
| `GET /api/muqayise?sayt1=&sayt2=` | `backend/main.py` |
| `API_URL` parametri | `backend/config.py` |
| 18 yeni test (142 → **160**) | `tests/test_mcp.py` |

### 🔍 Qərarlar

- **MCP serveri işi özü görmür, HTTP ilə FastAPI-yə göndərir.** Claude Code MCP
  serverini kiçik alt-proses kimi işə salır; crawler, embedding və LLM orada
  işləsəydi hər çağırış ağır olardı və baza ilə iki ayrı proses yazışardı.
  Server bağlıdırsa alət susmur — "uvicorn backend.main:app işə sal" deyir.
- **Müqayisə məntiqi backend-dədir, MCP-də yox.** Eyni məntiq həm REST-dən,
  həm MCP-dən, gələcəkdə interfeysdən də işlədilə bilər.
- **Üstünlük yalnız istiqaməti olan ölçülərdə elan olunur.** Şəkil sayı, rəng
  sayı, H1 sayı üçün "çox" nə yaxşı, nə pisdir — cədvəldə "—" yazılır.
  İlk versiyada bunlar səhvən "bərabər" göstərilirdi (14 ↔ 0 olsa belə).
- **Sayt göstəricisi çevikdir:** `5`, `asan.gov.az`, `https://asan.gov.az/x`
  — hamısı işləyir; tapılmasa mövcud saytlar sadalanır.

### 🧪 Sınaq

`mcp` paketinin öz stdio müştərisi ilə real qoşulma yoxlanıldı: server qalxdı,
üç alət də göründü, `saytlari_muqayise_et("asan.gov.az", "kontakt.az")` real
cədvəl qaytardı (asan.gov.az 3 ölçüdə, kontakt.az 2 ölçüdə üstün çıxdı).

### 🔌 Claude Code-a qoşulma

```bash
claude mcp add saytlupa -- "D:/SaytLupa/.venv/Scripts/python.exe" "D:/SaytLupa/backend/mcp_server.py"
```

`claude mcp list` → **✔ Connected**. İki tələ çıxdı:

- PowerShell `--` ayırıcısını udur (`unknown option '-m'`), `--%` da kömək etmir
  — əmr Git Bash-da işlədildi.
- `-m backend.mcp_server` yalnız cari qovluq `D:\SaytLupa` olanda işləyir; Claude
  Code serveri başqa qovluqdan işə sala bilər. Ona görə faylın tam yolu verilir,
  `mcp_server.py` isə birbaşa fayl kimi çağırılanda `sys.path`-i özü düzəldir.

### 🐛 Testdə tutulan tələ

`dict(analiz.xam_json)` **dayaz** nüsxədir — iç-içə lüğəti dəyişəndə köhnə və
yeni dəyər eyni obyektə baxır, SQLAlchemy fərq görmür və UPDATE göndərmir.
Testdə `json.loads(json.dumps(...))` ilə dərin nüsxə götürüldü.

---

## 2026-07-29 (davamı) — Gün 12: sənədləşdirmə

### ✅ Bitən işlər

| Nə | Harada |
|---|---|
| 10 ekran görüntüsü (işləyən sistemdən) | `docs/ekran/` |
| Müasir versiyanın Claude ilə ölçülməsi | `docs/model-secimi.md` → 4-cü ölçmə |
| Memarlıq: izləmə axını, 4 workflow, MCP bölmələri | `MEMARLIQ.md` |
| 4 yeni qərar + 4 yeni səhv (cəmi 18) | `QERARLAR.md` |
| n8n/MCP qurulması + yenilənmiş nümayiş ssenarisi (10 addım) | `ISTIFADE.md` |
| Kurs mövzuları: 🔨 qalmadı, hamısı ✅ | `TEXNOLOGIYALAR.md` |

### 📊 Müasir versiya: Claude ↔ Gemini

| Model | Vaxt | Fayl |
|---|---|---|
| `gemini-3.6-flash` | 78.6 san | 51 KB |
| **`claude-sonnet-5`** | **72.9 san** | **15.6 KB** |

Claude eyni işi üç dəfə kiçik fayl ilə görür (557 sətir, 24 CSS dəyişəni).
Gemini faylı üzərinə yazıldığı üçün içi müqayisə edilə bilmədi — sənəddə bu
açıq yazılıb, səbəb uydurulmayıb.

### 🧪 Ekran görüntüləri necə alındı

Başsız brauzer (`gstack browse`) ilə `localhost:8000` sürüldü: analiz işə
salındı, canlı gedişat çəkildi, sonra söhbət pəncərəsində real sual verildi
(cavab 21.7 saniyəyə gəldi, 5 mənbə ilə). Heç bir şəkil sonradan
redaktə edilməyib.

**Tələ:** brauzer daemon-u uzun boş gözləmələrdə söndürülür. Həlli — gözləmə
CLI-də yox, səhifənin içində (`js` + `Promise`) aparıldı.

### 🔧 Təhvildən sonrakı düzəlişlər (istifadəçi sınağından)

Amil bir neçə saytda "sosial şəbəkə və əlaqə tapılmır" problemi bildirdi.
Araşdırma iki ayrı səbəb tapdı:

1. **`kontakt.az` bizi bloklayır** — Cloudflare 403, HTML 5 KB, `<a>` sayı 0.
   Sistem bunu düzgün aşkarlayırdı, amma interfeys sadəcə boş bölmə göstərirdi.
2. **Yalnız ana səhifə skan olunurdu** — sosial linklər adətən altlıqda və ya
   `/elaqe` səhifəsindədir.

Həll: `elaqe_cixart()` ayrıca funksiyaya çıxarıldı, crawler onu hər gəzilən
səhifəyə tətbiq edir, `analiz.elaqe_birlesdir()` nəticələri birləşdirir və
mənbə səhifəni qeyd edir. Nəticə: `asan.gov.az`-da `info@asan.gov.az` tapıldı
(əvvəl e-poçt siyahısı boş idi).

İnterfeys artıq səbəbi yazır — ekran görüntüsü: `docs/ekran/10-qorunan-sayt.png`.

**AI ilə tapmaq təklifi rədd edildi** — səbəb ölçmə ilə sənədləşdirildi
([QERARLAR §13](QERARLAR.md)): uydurma və real hesab HTTP cavabına görə
fərqlənmir, yəni təklifi yoxlamaq mümkün deyil.

Əlavə: PageSpeed xəta mesajı insan dilinə çevrildi (429 → kvota, 401/403 →
açar, 400 → Google sayta çata bilmir).

Testlər: 160 → **174**.

### 📌 Layihənin yekunu

12 günün hamısı bağlandı: **174 test**, ~7 400 sətir kod, 4 n8n workflow,
3 MCP aləti, 10 ekran görüntüsü, 4 ölçmə sənədi.

---

## 2026-07-30 — Elektrik kəsilməsindən sonrakı yığışdırma

Gün 12 axşamı iş elektrik kəsilməsi ilə yarımçıq dayandı (son fayl 23:45-də
yazılıb). Bu gün qalan uclar bağlandı.

### ✅ Bitən işlər

| Nə | Harada |
|---|---|
| Git repo quruldu, iki commit (baseline + düzəlişlər) | `.git/` |
| Qabıq dırnaq xətasından yaranan 5 boş fayl silindi | layihə kökü |
| Köhnəlmiş sənəd rəqəmləri düzəldildi (9→10 ekran, kod həcmi) | `README.md`, bu fayl |
| `domen` toplayıcısının xəta mesajı insan dilinə çevrildi | `collectors/domen.py` |
| JS ilə qurulan saytların aşkarlanması | `collectors/js_sayt.py` |
| 13 yeni test (174 → **187**) | `tests/test_sebebler.py` |

### 🔍 Tam yoxlama: kodda yarımçıqlıq tapılmadı

Şübhə vardı ki, elektrik kəsiləndə kod yarımçıq qalıb. Yoxlanıldı: sintaksis,
faylların kəsilməsi, TODO işarələri, JS-in istədiyi bütün element ID-ləri,
frontend↔backend endpoint uyğunluğu; sonra proqram işə salınıb bütün axınlar
sınandı (analiz, RAG söhbəti, 4 təhvil düyməsi, yükləmə, müqayisə, izləmə,
MCP, 4 n8n JSON). **Hamısı işlədi.** Yarımçıq qalan yalnız sənəd rəqəmləri idi.

Bir yanlış şübhə də araşdırıldı: `example.com` analizi 0 səhifə verirdi.
Səbəb xəta deyil — saytın mətni 127 simvoldur, `MIN_METN = 150` filtri onu
qəsdən atır. Düzəliş edilmədi.

### 🔧 Səbəb yazılmayan iki hal

`aiworks.az` analizinə (id 153) baxanda iki boşluq göründü:

1. **`domen` toplayıcısı xam texniki xəta göstərirdi:**
   `HTTPStatusError: 404 ... rdap.org | RuntimeError: 'az' üçün WHOIS serveri
   tapılmadı`. Bu, Gün 12-də PageSpeed üçün edilən işin (`pagespeed_sebeb`)
   eynisidir — həmin keçid `domen`-ə tətbiq olunmamışdı. İndi `domen_sebeb()`
   üç halı ayırır: WHOIS-u olmayan zona, tapılmayan domen, cavab verməyən
   reyestr. Hər üçündə "analizin qalan hissəsi etibarlıdır" yazılır.

2. **JS ilə qurulan sayt səbəbsiz boş qalırdı.** `qoruma.py` bot qoruması
   üçün "niyə boşdur" izahını verirdi, amma `aiworks.az` bloklanmır — sadəcə
   React/Vite qabığıdır: serverin verdiyi HTML 1.8 KB, görünən mətn **0
   simvol**, 0 link. Crawler onu haqlı olaraq atırdı, istifadəçi isə səbəbi
   görmürdü. `js_sayt.yoxla()` əlavə edildi (`qoruma.py` ilə eyni quruluşda),
   nəticə `xam.js_sayt`-a düşür, interfeys həm yuxarı zolaqda, həm əlaqə
   bölməsində səbəbi yazır.

**Çərçivə adı uydurulmur:** yalnız birmənalı işarə olanda yazılır
(`__NEXT_DATA__` → Next.js, `ng-version` → Angular). `id="root"` tək başına
heç nə sübut etmir — belə halda ad boş qalır.

**Yanlış müsbətə qarşı:** `#root` olan, amma mətni də olan sayt (server
tərəfdə çəkilmiş React) JS saytı sayılmır — hədd `MIN_METN` ilə eynidir (150
simvol). Bunun testi var.

Yoxlama: `aiworks.az` yenidən analiz edildi (id 239) — hər iki mesaj brauzerdə
göründü, konsol xətası yoxdur (`docs/ekran/11-js-sayt.png`). `kontakt.az`
(Cloudflare) yenidən yoxlandı — köhnə davranış pozulmayıb.

---

## 2026-07-30 (davamı) — Gün 13: müqayisə səhifəsi

Dizayn sənədinin §15-i («bu ay daxil olmayan») bu sətri saxlayırdı: *«Bir neçə
saytın yan-yana müqayisə səhifəsi — MCP tool-u var, UI yoxdur»*. Bağlandı.

### ✅ Bitən işlər

| Nə | Harada |
|---|---|
| «⚖️ Başqa saytla müqayisə» kartı | `index.html`, `app.js`, `render.js`, `style.css` |
| Etibarsız məlumatda üstünlük hökmünün verilməməsi | `muqayise.py` |
| 5 yeni test (187 → **192**) | `tests/test_muqayise_etibar.py` |
| Ekran görüntüsü | `docs/ekran/12-muqayise.png` |

Backend-ə interfeys üçün bir sətir də əlavə olunmadı — `GET /api/sites` və
`GET /api/muqayise` Gün 11-dən hazır idi. İkinci sayt açılan siyahıdan seçilir
(analiz olunmuş saytlar), çünki müqayisə üçün hər ikisinin analizi lazımdır.
Bazada başqa sayt yoxdursa siyahı gizlənir və səbəbi yazılır.

### 🔴 İlk versiya yanlış idi — ekran görüntüsü göstərdi

Cədvəl işə düşdü, amma `asan.gov.az ↔ kontakt.az` müqayisəsində kontakt.az
**«Skript sayı 1 ✓»** və **«İzləyici 0 ✓»** ilə üstün göründü. Halbuki
kontakt.az Cloudflare arxasındadır — o rəqəmlər yoxlama səhifəsinindir, real
saytın deyil. Yəni interfeys bloklanmış saytı «daha yaxşı» elan edirdi.

Bu, layihənin əsas qaydasını pozur: **uydurma rəqəm yazılmır**. Boş sahə
buraxmaqdan pisdir, çünki yanlış nəticə inandırıcı görünür.

Həll: `_profil()` artıq `qorunur` və `js_ile_qurulur` sahələrini də oxuyur.
Tərəflərdən biri etibarsızdırsa, `_ustun()` **`etibarsiz`** qaytarır və heç nə
vurğulanmır. İstisna `KENAR_OLCULER`-dir: domen yaşı (WHOIS) və sertifikat
(TLS) saytın verdiyi HTML-dən asılı deyil, ona görə onlarda hökm qalır.

**Yüklənmə vaxtı da etibarsız sayıldı.** İlk testi yazanda onu «etibarlı»
qoymuşdum, sonra fikirləşdim: bloklanmış saytda ölçülən vaxt yoxlama
səhifəsinin açılma vaxtıdır, real səhifənin yox. Test düzəldildi, sonra kod
yazıldı.

Xəbərdarlıq həm interfeysdə, həm MCP-nin markdown xülasəsində cədvəldən
**əvvəl** gəlir — rəqəmlərə baxmazdan qabaq oxunmalıdır.

Yoxlama: `asan.gov.az ↔ kontakt.az` (qorunan) → 1 hökm, 1 xəbərdarlıq;
`asan.gov.az ↔ example.com` (adi) → 5 hökm, xəbərdarlıq yoxdur; konsol
xətası yoxdur.

---

## Arxiv — əvvəlki planlar

### Gün 12 — Sənədləşdirmə və cilalama
- Ekran görüntüləri (interfeys, təhvil düymələri, PDF nümunəsi)
- ~~Açar gələndə ölçmələrin təkrarı~~ ✅ 29 iyulda edildi
- Müasir versiya düyməsi indi **Claude ilə** işləyir — nəticəni bir dəfə də ölçüb
  `docs/model-secimi.md`-yə əlavə etmək olar (bu gün yalnız Gemini ilə ölçüldü: 78.6 san)

### Kiçik qalıqlar (unudulmasın)

| Nə | Niyə |
|---|---|
| Docker qalxanda **RAG indeksini yenilə** | Postgres bazasındakı köhnə chunk-lar `lokal` embedding ilədir; `POST /api/sites/{id}/rag/yenile` onları Gemini ilə yenidən qurur |
| `claude-opus-5` variantını sınamaq | Ağır iş (müasir versiya) üçün dizayn sənədində nəzərdə tutulub |
| Arşivi böyük real saytda sınamaq | İndiyə qədər `example.com` və lokal sınaq saytında yoxlanıb |

---

## Növbəti dəfə ilk addım

```bash
cd /d D:\SaytLupa
docker compose --profile core up -d          # Postgres + Redis (istəyə bağlı)
.venv\Scripts\activate
uvicorn backend.main:app --reload
```
Brauzer: <http://localhost:8000>

> Açarlar artıq `.env`-dədir (`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`) — heç nə
> əlavə etmək lazım deyil. `/api/health` hər üç modeli `true` göstərməlidir.
