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
3. **Şərh `<!doctype>`-dan əvvəl gəlməməlidir** — müasir versiyanın başına qoyulan mənşə qeydi doctype-dan qabaq olsa brauzer quirks rejiminə keçir. *(Qeyd 2026-07-30-da tamamilə götürüldü — aşağıya bax.)*
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

## 2026-07-30 (davamı) — Gün 14: tema düyməsi və opus ölçməsi

### ✅ Bitən işlər

| Nə | Harada |
|---|---|
| Açıq/qaranlıq keçid düyməsi (yaddaşda saxlanılır) | `index.html`, `app.js`, `style.css` |
| 5-ci ölçmə: `claude-opus-5` müasir versiyanı necə qurur | `docs/model-secimi.md` |
| gh CLI quraşdırıldı (2.96.0) | maşın |

### 🎨 Tema düyməsi

Əvvəl yalnız `prefers-color-scheme` var idi — sistem nə deyirdisə, o olurdu.
İndi düymə `<html data-tema="isiqli|qaranliq">` qoyur və seçim
`localStorage`-də saxlanılır.

**Bir incəlik:** media bloku `:root:not([data-tema="qaranliq"])` kimi yazıldı.
Əks halda sistem açıq rejimdə olanda istifadəçinin qaranlıq seçimi işləməzdi —
media bloku onu üstələyərdi.

**İkinci incəlik:** rejim `<head>`-dəki kiçik skriptdə, ilk boyamadan əvvəl
qoyulur. `app.js` faylın sonunda yüklənir, orada qoysaydıq səhifə bir an
yanlış rəngdə görünərdi.

Yoxlandı: klik → fon dəyişir, yenilədikdə seçim qalır, geri keçid işləyir,
konsol xətası yoxdur.

### 📊 Opus daha yaxşı qurmadı

Eyni analiz (#46), eyni prompt, yalnız model dəyişdi:

| Model | Vaxt | Fayl | Nəticə |
|---|---|---|---|
| **`claude-sonnet-5`** | **72.9 san** | 16.9 KB | ✅ işlək səhifə |
| `claude-opus-5` | 91.5 san | 16.7 KB | ❌ hero görünmür |

Opus 25% yavaşdır, fayl ölçüsü eynidir. Kağız üzərində üstünlükləri var (11
media sorğusu vs 3, 14 `aria`/`alt` vs 4), **amma səhifə sınıqdır**: brauzerdə
başlıq görünmür, çünki `section.hero` şəffafdır və `h1` ağdır — ağ üzərində ağ.
DOM-da mətn var, sadəcə oxunmur.

Bu, bir ölçmədir və prompt sonnet ilə tənzimlənib — nəticə «opus pisdir» yox,
«bu prompt opus ilə sınanmayıb» kimi oxunmalıdır. Standart model dəyişmir.

Görüntü: `docs/ekran/13-opus-muasir.png`. Ölçmə zamanı sonnet faylı silinməsin
deyə əvvəlcədən ehtiyat nüsxə götürüldü — 4-cü ölçmədə Gemini faylı üzərinə
yazıldığı üçün müqayisə edilə bilməmişdi, bu dəfə səhv təkrarlanmadı.

### 🌍 GitHub

Repo: <https://github.com/amilbexercin-tech/saytlupa> (public, 6 commit).

Push-dan əvvəl sirr yoxlaması **işçi qovluqda deyil, bütün tarixçədə** aparıldı
(`git log --all -p`) — açar, token, Telegram id və şəxsi məlumat tapılmadı.
`.env` heç bir commit-də olmayıb, `.env.example`-in dəyərləri boşdur.
Uzaqdan da təsdiqləndi: `contents/.env` → 404.

**Tələ:** qabıq artefaktı olan boş fayllar (`5`, `(Claude`) commit-lərə
qarışırdı. İkisi də boş olduğu üçün git birini o birinin «adı dəyişdirilmiş
variantı» saydı. Ona görə push-dan əvvəl repodakı bütün boş fayllar ayrıca
yoxlandı.

---

## 2026-07-30 (davamı) — Gün 15: yekun keçid

Nümayiş ssenarisinin 12 addımı işləyən sistemdə baş-ayaq keçirildi.

| Addım | Necə yoxlandı | Nəticə |
|---|---|---|
| 1 — Sistem vəziyyəti | interfeys | `Baza: postgresql · Keş: redis · Claude · Gemini · Gemma` |
| 2 — Analiz və canlı gedişat | interfeysdən `asan.gov.az` (analiz 426) | 9/9 toplayıcı · 30 səhifə · 104 chunk · 6 bəndlik hesabat (37.2 san) |
| 3 — Dayanıqlılıq | `kontakt.az` (analiz 131) | Cloudflare aşkarlanır, gəziş atlanır |
| 4 — Təxmini məlumatın işarələnməsi | analiz 426 | `wayback (təxmini)` · 2013 · ~13.5 il |
| 5 — RAG söhbəti | interfeysdə sual | cavab **4 mənbə** ilə, real məzmundan |
| 6 — Təhvil düymələri | PDF 85.2 KB · klon 6 sənəd · arşiv 2.3 MB | üçü də `ugurlu`, yükləmə linkləri işləyir |
| 7 — Müqayisə | `asan.gov.az ↔ kontakt.az` | 1 xəbərdarlıq, yalnız 1 hökm (sertifikat) |
| 8 — Model bölgüsü | `scripts/model_olcme.py` | yerindədir, ölçmə nəticəsi sənəddə |
| 9 — İzləmə | `POST/GET/DELETE /api/izleme` | üçü də işləyir |
| 10 — n8n | `localhost:5678` | HTTP 200 |
| 11 — MCP | `claude mcp list` | `saytlupa … ✔ Connected` |
| 12 — Açıq/qaranlıq rejim | düymə + yeniləmə | `data-tema` qoyulur, `localStorage`-də qalır |

Konsol xətası yoxdur. Yekun ekran görüntüləri: `14-yekun-isiqli.png`,
`15-yekun-qaranliq.png`.

### 🔧 Yol boyu tapılan iki səhv

**Sənəddəki rəqəm yanlış idi.** Ssenari `.az` domen yaşı üçün «ən azı 2010,
~15.6 il» yazırdı; ölçdüm — `asan.gov.az` üçün **2013, ~13.5 il**. Nümayişdə
müəllim ekranda başqa rəqəm görərdi. Düzəldildi və hansı domen olduğu yazıldı.
`github.com` üçün yazılan 18.8 il isə doğru çıxdı.

**Qlobal hook konfiqurasiyası sınıq idi.** `~/.claude/settings.json`-dakı 16
hook əmri `cmd /c "IF EXIST "..." (node ...)"` formasında idi, amma maşında
Git Bash olduğu üçün hook əmrləri **bash-da** işləyir. Nəticə: əmr xəta
vermirdi, **interaktiv `cmd.exe` açırdı** — yəni hooklar heç vaxt işləməyib və
hər çağırışda işçi qovluqda 0 baytlıq zibil fayllar qalırdı (bu sessiyada 11
ədəd təmizləndi). Əmrlər düzgün bash sintaksisinə keçirildi. Əlavə: `timeout`
sahəsi saniyə ilədir, dəyərlər isə millisaniyə kimi yazılmışdı (`5000` = 83
dəqiqə) — 14 dəyər saniyəyə çevrildi.

---

## 2026-07-30 (davamı) — İnterfeysin canlı dizaynı

Amil interfeysi «müasir və möhtəşəm» görkəmə keçirməyi istədi: qara canlı arxa
fon, 3D dərinlik, yazıların üzərinə gələndə hərəkət, analiz başlayanda isə
**matrix** fonu.

### 🎨 Nə edildi

| Nə | Harada |
|---|---|
| Canlı arxa fon (qara + üzən işıq + perspektivli şəbəkə) | `efekt.js` — **yeni**, 188 sətir |
| Matrix rejimi (analiz gedərkən düşən simvol yağışı) | `efekt.js` |
| Kartların mausa görə 3D əyilməsi + parıltı | `efekt.js` + `style.css` |
| Başlıq, cədvəl sətri, teq, qutu, düymə — `translateZ` hərəkətləri | `style.css` |
| Matrix-in analiz axınına qoşulması | `app.js` (2 sətir) |

### 🧭 Qərarlar

**Kitabxana işlədilmədi.** `three.js` təklif olunmuşdu, amma layihənin qaydası
«xarici fayl və şrift yüklənmir»dir və maşında 7.8 GB RAM var. Bütün effektlər
CSS 3D + bir `<canvas>` ilə quruldu — nəticə offline açılır, proyektorda
ilişmir. Matrix yağışı 60 sətirdən azdır.

**Simvollar Azərbaycan əlifbasındandır.** Katakana klişedir; burada `0/1`, kod
işarələri və `ƏĞİÖŞÜÇ` yağır — alət Azərbaycan saytlarını analiz edir.

**Standart rejim qaranlığa keçdi.** Fon artıq həmişə qaradır, ona görə sistemin
işıqlı rejimini izləmək mənasız idi: ağ panel qara lövhənin üstündə kəskin
görünürdü. İndi standart qaranlıqdır, işıqlı rejim düymə ilə açılır (qara lövhə
qalır, panellər açılır — işıq qutusu görünüşü).

**Mətn oxunaqlı qaldı.** AI hesabat, məzmun, səhifə siyahısı və müqayisə
kartları `backdrop-filter` ilə bulanıq örtük alır — fon uzun mətnlə vuruşmur.
Matrix onsuz da yalnız analiz gedərkən, yəni oxunacaq hesabat hələ yoxkən
işləyir.

### 🛡️ Qoruyucular

`prefers-reduced-motion` seçilibsə bütün hərəkət sönür; tab arxa plana keçəndə
kadrlar dayanır (CPU/batareya); piksel sıxlığı 2 ilə məhdudlaşır; toxunma
ekranlarda kart əyilməsi işləmir; kadr sürəti 30-a bağlanıb.

Yoxlandı: hər iki rejim, matrix açıq/bağlı, 13 kart görünür, konsol xətası
yoxdur. Görüntü: `docs/ekran/16-dizayn-netice.png`.

---

## 2026-07-30 (davamı) — Söhbətin səbəbi və müqayisəyə ünvan sahəsi

### 💬 Söhbət kartı niyə yox idi

Amil «saytla danışmaq üçün bölmə olmalıdır» dedi — halbuki bölmə var idi.
Səbəb: `kontakt.az` Cloudflare arxasındadır, 0 səhifə → 0 parça, kod isə
`if (n.chunk_sayi > 0) gorset('k-sohbet')` yazırdı. Kart **səssizcə**
gizlənirdi, istifadəçi isə funksiyanın ümumiyyətlə olmadığını sanırdı.

İndi kart həmişə görünür, sual qutusunun yerinə səbəb yazılır — bloklanmış
sayt, JS ilə qurulan sayt və mətn tapılmayan sayt üçün ayrı-ayrı cümlə.

Dərs: **funksiyanı gizlətmək onu yox etməkdir.** Boş bölmə səbəblə birlikdə
gizli bölmədən yaxşıdır.

### ⚖️ Müqayisəyə ünvan sahəsi

Əvvəl yalnız açılan siyahı var idi (analiz olunmuş saytlar). İndi yanında
ünvan sahəsi də var. Yazılan sayt bazada yoxdursa axın belədir:

```
GET /api/muqayise → 404  →  POST /api/analyze → SSE gedişat → GET /api/muqayise → 200
```

Yoxlandı: `example.org` bazada yox idi → 404, analiz 32 saniyəyə bitdi →
müqayisə açıldı. İkinci analiz cari nəticə səhifəsini pozmur, gedişat müqayisə
kartında qısa sətir kimi görünür; matrix fonu da qoşulur.

**Bir qüsur düzəldildi:** ünvan sorğuya kodlanmadan qoyulurdu
(`sayt2=https://…`). Sorğu sətrində `?` və ya `&` olan ünvan parçalanardı —
`encodeURIComponent` əlavə edildi.

Siyahı boş olanda (bazada tək sayt var) açılan siyahı gizlənir, ünvan sahəsi
qalır — yəni müqayisə artıq həmişə mümkündür.

---

## 2026-07-30 (davamı) — Mənşə damğasının götürülməsi

«Müasir versiyanı qur» düyməsi yaradılan HTML-in başına şərh qoyurdu:

```html
<!--
  SaytLupa ilə yaradılıb — 2026-07-30 12:05 UTC
  Mənbə sayt: https://asan.gov.az/
  Model: claude-sonnet-5
  Bu, saytın kopyası DEYİL — analizə əsaslanan müasir versiya təklifidir.
-->
```

Amil onun götürülməsini istədi. Qeyd əvvəl qəsdən qoyulmuşdu (fayl saytın öz
kodu ilə qarışdırılmasın deyə) — bu, açıq şəkildə bildirildi, qərar sahibin
oldu. `_qeyd_elave()` funksiyası tamamilə silindi, artıq zəncirdən nə gəlirsə
fayla o yazılır. Sınaq zamanı yaradılmış zip fayllar da silindi.

### 🔴 Silərkən səhv buraxıldı — test onu tutmadı

`html` dəyişəni ləğv edildi, amma aşağıdakı `olcu_kb` sətri hələ ona
istinad edirdi → `NameError`. **192 testin heç biri bunu tutmadı**, çünki
`builder/muasir.py`-nin uğurlu yolu ümumiyyətlə örtülməmişdi: yalnız
`chains/muasir.py` (zəncir) test edilirdi.

Səhv canlı serverdə üzə çıxdı. Sonra 3 test yazıldı (`test_builder.py`):
fayl yazılır və ölçü qaytarılır · **fayla əlavə qeyd yazılmır** · html boş
olanda səbəb qaytarılır. Testlərin həqiqətən işlədiyi yoxlanıldı — səhv
qəsdən geri qoyuldu, ikisi də sındı, sonra düzəliş bərpa edildi.

Testlər: 192 → **195**.

**Dərs:** funksiya silinəndə onun *istifadə yerləri* də yoxlanmalıdır, və
örtülməyən uğurlu yol belə anlarda özünü göstərir.

---

## 📋 PLAN — Onlayn yerləşdirmə (2026-07-31-də ediləcək)

> Bu bölmə **hələ edilməyib**. Məqsəd: layihəni hər kəsin görə biləcəyi
> ünvana çıxarmaq — indi yalnız `localhost`-da görünür.

### Verilmiş qərarlar

| Sual | Qərar |
|---|---|
| Platforma | **DigitalOcean Droplet** (Docker + compose) |
| Yeni analiz kim işlədə bilər | **Yalnız açarla** — ziyarətçi hazır analizləri görür |
| n8n serverə çıxsınmı | **Xeyr** — avtomatlaşdırma qatıdır, ziyarətçi onu görmür; nümayişdə lokal maşında göstərilir |

### Araşdırma nəticəsi: böyük server lazım deyil

Layihə **Postgres və Redis olmadan da tam işləyir** — `rag/store.py`-də həm
vektor, həm açar söz axtarışının SQLite yolu var (`if db.POSTGRES:` budaqları),
keş isə yaddaşdaxili rejimə düşür. 2026-07-30-da yoxlanıldı: SQLite ilə 81
parça, söhbət 4 mənbə ilə cavab verdi.

| Yol | RAM | Təxmini qiymət |
|---|---|---|
| Yalnız FastAPI + SQLite | ~500 MB | $6-12/ay |
| + Postgres/pgvector + Redis | ~1.5 GB | $12-24/ay |
| + Ollama/gemma3:4b | ~6 GB | ~$48/ay |

Gemma serverə çıxarılmır — `.env`-də onsuz da `RERANK=gemini`-dir.

### Hazır olmayan üç şey

1. **Tətbiqin `Dockerfile`-ı yoxdur** — lokalda `uvicorn` ilə işləyir
2. **API-də giriş qoruması yoxdur** — `main.py`-də heç bir autentifikasiya
   yoxdur. Bu, ən vacib maddədir: `/docs` səhifəsi bütün endpoint-ləri hazır
   düymələrlə göstərir, ünvanı bilən hər kəs `POST /api/analyze` çağırıb
   Anthropic/Gemini açarı ilə **pul xərcləyə bilər**
3. **n8n workflow-larında ünvan** — `host.docker.internal:8000` lokal üçündür

### Addımlar (bu sıra ilə)

1. **Giriş qoruması** (lokal sınaqla, TDD)
   - `.env`-də `API_ACAR`; boş olsa hər şey açıq qalır (lokal inkişaf pozulmur)
   - Açar tələb olunan: `POST /api/analyze`, təhvil düymələri, `rag/yenile`,
     izləmə və xəta yazan endpoint-lər
   - Açıq qalan: bütün `GET` sorğuları, SSE axını, statik fayllar
   - Söhbət (`POST /sites/{id}/chat`) — **həll edilməli**: bağlansa nümayişin
     ən güclü hissəsi itir, açıq qalsa xərc sərhədsizdir. Təklif: IP başına
     gündə 5 sual, limit dolanda səbəb yazılır
2. **Dockerfile** — Python 3.14, `requirements.txt`, `uvicorn`
3. **`docker-compose.prod.yml`** — `api` xidməti + (istəsək) `db`/`redis`;
   `host.docker.internal` əvəzinə Docker şəbəkə adları
4. **HTTPS** — Caddy (Let's Encrypt pulsuz, avtomatik)
5. **Domen** — ~$10-15/il, ayrıca alınır
6. **Serverdə `.env`** — açarlar repoya düşmür, əl ilə qoyulur
7. **Hazır analizlərin köçürülməsi** — ziyarətçi boş səhifə görməsin deyə
   `asan.gov.az` və bir-iki sayt əvvəlcədən analiz edilmiş olmalıdır

### Nəzərə alınmalı risklər

- **Datacenter IP-ləri daha tez bloklanır.** Cloudflare və bənzərləri
  DigitalOcean IP-lərinə lokal maşından şübhəli baxır — serverdə daha çox sayt
  «qorunur» kimi görünə bilər
- **Analiz 30-120 saniyə çəkir** — DigitalOcean App Platform buna uyğun deyil,
  adi Droplet + Docker düzgün seçimdir
- **n8n-in cron-u** serverə çıxarılsa hər gün pullu analiz işlədəcək

### Ayrıca kiçik iş

`PAGESPEED_API_KEY` — `console.cloud.google.com` → PageSpeed Insights API →
pulsuz açar. Hazırda açarsız kvota bitir və 429 mesajı çıxır (bu, xəta deyil,
öz ölçmələrimiz onsuz da göstərilir).

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
