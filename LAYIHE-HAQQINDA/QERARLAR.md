# SaytLupa — Qərarlar və səbəbləri

Bu sənəd layihədə verilən texniki qərarları və **niyə** belə edildiyini saxlayır.
Hər qərarın arxasında ya ölçmə, ya da real qarşılaşdığımız problem dayanır.

---

## 1. Niyə Python/FastAPI, halbuki ilkin plan Next.js idi?

SaytLupa-nın ilk planı (`C:\Users\amilb\SaytLupa\PLAN.md`, 2026-07-11) Next.js API
route-ları üzərində qurulmuşdu. Kurs isə FastAPI, Pydantic, SQLAlchemy və psycopg2
tələb edir. İki dildə paralel backend saxlamaq mənasız olduğu üçün backend tam
Python-a keçirildi. Frontend isə sadə HTML + vanilla JS saxlanıldı — bir konteyner,
bir dil, kurs mövzularına diqqət.

---

## 2. Niyə "Saytla söhbət" (RAG) əlavə edildi?

Təkcə "analiz göstər" funksiyası ilə RAG mövzusu layihəyə **süni şəkildə**
yapışdırılmalı olardı. Saytın 20-30 səhifəsindən təbii dildə sual cavablandırmaq isə
RAG-ı **məcburi** edir: kontekst limitinə görə bütün səhifələri modelə göndərmək
mümkün deyil, deməli chunking, embedding, axtarış və re-ranking gerçək ehtiyacdır.

---

## 3. Niyə "Saytı kopyala" düyməsi üç düyməyə bölündü?

İlkin planda "Bu saytı kopyala" düyməsi `ai-website-cloner` motorunu çağırmalı idi.
Araşdırdıqda məlum oldu ki, `ai-website-cloner` **proqram deyil** — o, Next.js şablonu
və `clone-website` adlı **Claude Code skill**-idir. İşi kod yox, AI agent komandası
görür (10-20 dəqiqə, yüksək RAM). FastAPI-dəki bir düymə bunu etibarlı çağıra bilməz.

Həll — işi üç real hissəyə bölmək:

| Düymə | Nə edir | Niyə işləyir |
|---|---|---|
| ⚡ **Müasir versiyanı qur** | Claude analizə əsasən yeni, təmiz səhifə yazır | Proqramlaşdırıla bilir, ~30 saniyə |
| 🧬 **Tam klon üçün hazırla** | `ai-website-cloner`-in gözlədiyi `docs/research/*.md` sənədlərini avtomatik yazır + hazır `/clone-website` əmrini verir | Cloner-in `INSPECTION_GUIDE.md`-də tələb etdiyi Faza 1 (dizayn token-ləri) və Faza 4 (texnoloji stek) — SaytLupa onsuz da onları çıxarır |
| 📦 **Səhifə arşivi** | HTML/CSS/şəkilləri lokal qovluğa yazır | Sadə, dərhal işləyir |

Beləliklə klonlama **həqiqətən işləyir**, sadəcə iş düzgün alətlər arasında bölünür.

---

## 4. Hansı model hansı işə? (ölçmə ilə)

**Sual:** RAG re-ranking kütləvi işdir (hər sual üçün ~20 namizəd). Bunu pulsuz, lokal
Gemma edə bilərmi?

**Ölçmə:** 8 sual-parça cütü, Azərbaycan dilində, doğru ballar əvvəlcədən təyin edilib.
Skript: `scripts/model_olcme.py`.

| Model | Ölçü | Dəqiqlik | Orta fərq | Orta vaxt | Cavabsız |
|---|---|---|---|---|---|
| **gemma3:4b** ✅ | 3.3 GB | **100%** | 0.5 | 7.6 san | 0 |
| gemma3:1b | 0.8 GB | 50% | 3.17 | 4.6 san | 2 |
| gemma4:12b | 7.0 GB | 0% | — | **99.1 san** | 8 |

**Nəticə:**
- `1b` — "12 ay zəmanət verilir" cümləsinə zəmanət sualı üçün **2 bal**, tamamilə
  əlaqəsiz cümləyə **10 bal** verdi. İki halda ümumiyyətlə rəqəm qaytarmadı.
- `12b` — 7 GB model 7.8 GB RAM-da swap-a düşür; hər çağırış 92-122 saniyə.
- `4b` — 8/8 düz, orta fərq 0.5 bal.

**Qərar:** `gemma3:4b`. Ətraflı: [`../docs/model-secimi.md`](../docs/model-secimi.md).

**Açıq məsələ:** ~6 san/çağırış × 20 namizəd = 2 dəqiqə — çox uzundur. Ona görə
re-ranking **toplu** olacaq (hamısı bir promptda) və eyni skriptlə yenidən ölçüləcək.

---

## 5. Niyə Docker volume-ları "bind mount" yox, "named volume"?

İlkin dizaynda baza faylları birbaşa `D:\SaytLupa\data\postgres` qovluğuna bağlanacaqdı.
Windows-da PostgreSQL-i NTFS qovluğuna bind mount etmək **icazə xətaları** verir
(konteynerdəki `postgres` istifadəçisi qovluğun sahibini dəyişə bilmir).

Əvəzinə: named volume + **Docker-in öz disk image-i D: diskinə köçürüldü**
(Settings → Resources → Advanced → Disk image location = `D:\DockerData`).

Nəticə eynidir (hər şey D:-dədir), üstəlik **C: diskdə 11.7 GB azad oldu**
(10.5 GB → 22.2 GB).

---

## 6. Niyə `.az` domenlərinin yaşı "təxmini" göstərilir?

`.az` üçün pulsuz WHOIS **ümumiyyətlə yoxdur** — yoxlanıldı:

| Mənbə | Nəticə |
|---|---|
| RDAP (`rdap.org`) | 404 — `.az` dəstəklənmir |
| IANA-nın göstərdiyi server | `.az` üçün WHOIS serveri qeyd edilməyib |
| `whois.az:43` | Timeout — cavab vermir |
| `whois.nic.az` | DNS-də mövcud deyil |
| RIPE | Qeyd yoxdur |

Uydurmaq əvəzinə **Wayback Machine CDX API** əlavə edildi: saytın ilk arxivləşdirilmə
tarixi. Bu, domenin qeydiyyat tarixi **deyil** — yalnız "sayt ən azı bu tarixdən bəri
mövcuddur" deməkdir və nəticədə **açıq şəkildə "TƏXMİNİ" işarələnir**:

> *"Bu TLD üçün pulsuz WHOIS yoxdur — dəqiq qeydiyyat tarixi alınmadı. Arxiv.org-a görə
> sayt ən azı 2010 ilindən mövcuddur (~15.6 il). Bu TƏXMİNİ göstəricidir."*

`.com`, `.net`, `.org` kimi domenlərdə RDAP dəqiq tarix verir (`github.com` → 18.8 il).

---

## 7. Niyə bot qoruması ayrıca aşkarlanır?

`kontakt.az` sınananda sistem 200 əvəzinə **HTTP 403** və "Just a moment..." səhifəsi aldı —
Cloudflare-in yoxlama səhifəsi. Aşkarlanmasaydı analiz belə görünərdi:

```
başlıq: "Just a moment..."      dil: en-US        daxili link: 0
texnologiya: ['Cloudflare']     rəng: ['#313131'] reklam: []
```

Yəni **tamamilə yanlış, amma inandırıcı görünən hesabat**. `collectors/qoruma.py`
8 fərqli qoruma xidmətinin imzasını tanıyır və belə halda:

1. Gəziş (crawl) **atlanır** — mənasız məzmun RAG bazasına düşmür
2. İstifadəçiyə açıq bildirilir: *"Məzmun analizi və RAG bu sayt üçün etibarsızdır"*
3. Texniki analiz (DNS, SSL, geo) davam edir — onlar HTML-dən asılı deyil

---

## 8. Yol boyu tapılan səhvlər

| # | Səhv | Necə aşkarlandı | Həll |
|---|---|---|---|
| 1 | **Keş açarları toqquşurdu** — bütün toplayıcılarda funksiya `topla` adlanır, `@cached` isə açarı yalnız funksiya adından qururdu. `domen`, `dns`, `geo`, `sertifikat` bir-birinin nəticəsini oxuyurdu | Real sınaqda `dns` collector-i `geo`-nun nəticəsini qaytardı | Açar `modul + funksiya adı`-ndan qurulur + regressiya testi |
| 2 | HTTP başlığında Azərbaycan hərfi (`ə`) vardı | `'ascii' codec can't encode character '\u0259'` | Başlıqlar yalnız ASCII |
| 3 | `arxiv.org` bizim `Accept: text/html` başlığımıza **498** qaytarırdı | Wayback həmişə boş qayıdırdı | Wayback üçün ayrıca sadə başlıqlar |
| 4 | IANA cavabında regex sətir keçirdi — `whois:` boş olanda növbəti sətrin açarını (`status:`) tuturdu | `.az` üçün server adı `'status:'` gəldi | `[^\S\n]*` — yalnız eyni sətirdəki boşluqlar |
| 5 | `hadise.gonder()`-ə `analiz_id` həm mövqe, həm ad ilə ötürülürdü | Analiz sonda `status="xeta"` alırdı, halbuki hər şey uğurlu idi | Təkrar arqument silindi |
| 6 | `site.az/` və `site.az` **iki ayrı səhifə** kimi yığılırdı | Ana səhifə həmişə təkrarlanırdı | Sondakı kəsik həmişə atılır + məzmun barmaq izi ilə təkrar yoxlaması |
| 7 | Başlıqlarda sətir keçidləri qalırdı (`"ASAN xidmətlər\n - \n ASAN"`) | Səhifə siyahısı səliqəsiz görünürdü | `" ".join(basliq.split())` |
| 8 | `web.archive.org` `http://` üzərindən timeout verirdi | Wayback sorğusu 15 saniyə gözləyib sınırdı | Yalnız `https://` |
| 9 | **Model JSON sahə adını "düzəldirdi"** — `seo_catismazliqlari` əvəzinə `seo_catismazlıqlari` (nöqtəsiz `ı`) qaytardı; Pydantic doğrulaması sındı və **bütün hesabat itdi** | Zənciri saxta model yox, **real Gemma** ilə sınayanda | `normalla()` funksiyası: açarlar müqayisədən əvvəl sadələşdirilir (`ı→i`, `ə→e`, `ç→c`…), çatmayan sahə hesabatı öldürmür, yalnız qeyd olunur |
| 10 | `num_predict` `bind()` ilə ötürülmürdü — `Client.chat() got an unexpected keyword argument` | Re-ranking həmişə fallback-a düşürdü | Ollama parametrləri konstruktora verilir |
| 11 | **Performans zolaqları görünmürdü** — DOM-da en 98.8%, rəng yaşıl idi, ekranda isə boş boz xətt | Brauzerdə ekran görüntüsü alınanda | `.zolaq` və `.zolaq-fon` `<span>`-dır; **inline elementlərə `width`/`height` tətbiq olunmur**. `display: block` əlavə edildi |
| 12 | **Şrift regex-i dırnaqda dayanırdı** — `font-family: 'Inter', sans-serif` yazılışında saytın öz şrifti heç vaxt tutulmurdu, yalnız `sans-serif` qalırdı | Yazılan test (`test_umumi_sriftler_ayrilir`) düşdü | `[^;}\"']+` → `[^;}]+` |
| 13 | Tərsinə göstəricilərdə (yüklənmə vaxtı, HTML ölçüsü) zolaq **xam nisbəti** göstərirdi — 0.09 saniyəyə yüklənən sayt demək olar boş zolaq alırdı | Ekran görüntüsündə məntiqsiz görünürdü | Zolaq artıq "nə qədər yaxşıdır"ı göstərir: sürətli sayt = dolu yaşıl |
| 14 | Şriftlər siyahısında `serif, monospace, inherit, Menlo, Consolas` görünürdü — bunlar CSS ehtiyat dəyərləridir, saytın dizayn seçimi deyil | Ekran görüntüsündə | `UMUMI_SRIFTLER` süzgəci; ehtiyat şriftlər ayrıca, solğun göstərilir |
| 15 | **n8n boş siyahıya bir "boş element" buraxırdı** — `alwaysOutputData` açıq olduğu üçün izlənəcək sayt olmayanda da növbəti node işə düşür, `site_id`-siz ünvana sorğu gedir | Canlı icrada `job_errors`-da 3 ədəd `site_id=? → 404` qeydi | Ayar söndürüldü; JSON faylını yoxlayan test yazıldı |
| 16 | **`gemma3:4b` alət çağırışını dəstəkləmir** — WF4 AI Agent + 3 alət kimi yazılmışdı, model isə bunu bacarmır | Ollama `/api/show` → `capabilities: completion, vision` | WF4 təsnifat + Switch kimi yenidən quruldu (bax 12-ci qərar) |
| 17 | Müqayisə cədvəlində **istiqaməti olmayan ölçülər "bərabər" yazılırdı** — şəkil sayı 14 ↔ 0 olsa belə | MCP alətinin real çıxışına baxanda | `neytral` vəziyyəti əlavə edildi, cədvəldə "—" görünür |
| 18 | Testdə `dict(analiz.xam_json)` **dayaz** nüsxə idi: iç-içə lüğət dəyişdirildikdə SQLAlchemy fərq görmür və UPDATE göndərmirdi | Yazılan test səbəbsiz düşdü | `json.loads(json.dumps(...))` — dərin nüsxə |
| 19 | **Sosial link və əlaqə yalnız ana səhifədən axtarılırdı** — halbuki onlar çox vaxt altlıqda və ya `/elaqe` səhifəsindədir | İstifadəçi bir neçə saytda "tapa bilmir" dedi | `elaqe_cixart()` ayrıldı, crawler onu **hər** gəzilən səhifəyə tətbiq edir, `elaqe_birlesdir()` nəticələri birləşdirir. `asan.gov.az`-da `info@asan.gov.az` beləcə tapıldı |
| 20 | **Boş bölmə səbəbsiz görünürdü** — sayt bloklandıqda da, məlumat həqiqətən olmadıqda da eyni boşluq | Eyni şikayət | İnterfeys səbəbi yazır: "Sayt Cloudflare arxasındadır…" və ya "30 səhifənin heç birində tapılmadı" |
| 21 | PageSpeed xətası `Səbəb: HTTPStatusError` kimi görünürdü — istifadəçiyə heç nə demir | İstifadəçi ekran şəklini göndərdi | `pagespeed_sebeb()`: 429 → kvota, 401/403 → açar, 400 → Google sayta çata bilmir; açar yoxdursa pulsuz açarın necə alınacağı yazılır |

> **11-13-cü səhvlər haqqında:** heç biri testlə tutula bilməzdi — DOM düzgün idi,
> API düzgün idi. Yalnız **brauzerdə ekran görüntüsünə baxanda** göründülər.
> Bu, "işləyir" ilə "düzgün görünür" arasındakı fərqdir.

> **9-cu səhv haqqında:** bu, "saxta model ilə test kifayət deyil" dərsidir.
> `FakeListChatModel` zəncirin **qurulduğunu** yoxlayır, amma modelin real
> davranışını yox. Prompt və parser yalnız real modellə sınananda bu tapıldı.

---

## 9. Niyə hər şey "fallback"-lı qurulub?

Layihə müəllimin maşınında **heç nə quraşdırılmadan** işə düşməlidir. Ona görə hər
xarici asılılıq üçün ehtiyat yol var: Postgres → SQLite, Redis → yaddaş, Gemma → Gemini,
açar yoxdursa → mock rejim.

Bu, həm də inkişaf zamanı faydalıdır: Docker qalxmayanda iş dayanmır.

---

## 10. Niyə fərqi n8n yox, Python hesablayır?

n8n-də iki səhifə siyahısını tutuşdurub fərqi tapmaq mümkündür — bir Code node
kifayət edərdi. Yenə də bu iş Python-da qaldı:

- **Sərhəd qaydası:** n8n *nə vaxt* və *kimə xəbər* sualını həll edir. İş məntiqi
  ora köçsə, hər dəyişiklik üçün iki yerə baxmaq lazım gələcək.
- **Test olunur:** `izleme.yoxla()` üçün 6 test var (yeni/dəyişən/silinən səhifə,
  boş gəziş, təkrar yoxlama). n8n Code node-u üçün belə test yazmaq olmur.
- **Təkrar istifadə:** eyni funksiya sabah interfeysdən və ya MCP-dən də
  çağırıla bilər.

Nəticədə n8n workflow-u cəmi 8 node-dur və heç bir hesablama aparmır.

---

## 11. Niyə MCP serveri işi özü görmür?

`mcp_server.py` analizi özü işlədə bilərdi — `analiz.basla()` çağırmaq kifayət idi.
Əvəzinə hər şey HTTP ilə FastAPI-yə göndərilir:

| Səbəb | İzah |
|---|---|
| Proses ölçüsü | Claude Code MCP serverini kiçik alt-proses kimi işə salır; crawler + embedding + LLM orada işləsəydi hər çağırış ağır olardı |
| İki proses, bir baza | Analiz həm serverdə, həm MCP prosesində getsəydi, eyni cədvəllərə iki tərəfdən yazılardı |
| Vahid davranış | İnterfeys, n8n və MCP eyni endpoint-ləri çağırır — düzəliş bir yerdə edilir |

Əvəzində bir şərt yarandı: **uvicorn işləməlidir**. Alət bunu susaraq gizlətmir —
server bağlıdırsa "uvicorn backend.main:app işə sal" mesajı qaytarır.

---

## 12. Niyə n8n agenti alət çağırmır?

Dizayn sənədində WF4 "AI Agent node → Ollama Gemma" kimi planlanmışdı. Ollama-dan
soruşduq:

| Model | Ölçü | `capabilities` |
|---|---|---|
| `gemma3:1b` | 0.76 GB | completion |
| `gemma3:4b` | 3.11 GB | completion, vision |
| `gemma4:12b` | 7.04 GB | completion, vision, audio, **tools**, thinking |

Alət çağırışını yalnız 12B model bacarır, maşında isə **7.8 GB RAM** var — 7 GB-lıq
model praktiki deyil. Ona görə WF4 belə quruldu: **Gemma sualı təsnif edir (JSON
qaytarır) → n8n Switch üç endpoint-dən birinə yönləndirir**.

Bu, dizayn sənədindəki cümlə ilə ("sualı təsnif edir və uyğun endpoint-ə
yönləndirir") üst-üstə düşür və 3 GB model ilə işləyir. Alət-agenti variantı güclü
maşında bir sətir dəyişikliklə (model adı) geri qaytarıla bilər.

---

## 13. Niyə AI sosial hesabları "adına görə tapmır"?

Sayt bloklandıqda (məsələn `kontakt.az` → Cloudflare 403) sosial linkləri
tapmaq mümkün olmur. Təklif belə idi: **AI brend adına görə hesabı özü tapsın**.

Yoxladıq — təklifi **yoxlamaq mümkün deyil**:

| Platforma | Real hesab | Uydurma hesab |
|---|---|---|
| Instagram | 200 · 590 KB | **200 · 590 KB** (giriş divarı, eyni cavab) |
| Facebook | 400 | **400** |
| Telegram | 200 | **200** |

Yəni `instagram.com/kontakt.az` mövcuddur, ya yox — HTTP cavabından bilinmir.
AI-nin təklifini yoxlamadan yazsaq, hesabatda **uydurma link** görünərdi. Bu,
layihənin əsas vədini pozur: "dəqiq bilinməyən məlumat uydurulmur".

Əvəzinə iki real dəyişiklik edildi (bax 19 və 20-ci səhvlər): bütün gəzilən
səhifələrdən toplama, və tapılmayanda **səbəbin** yazılması. İstifadəçi indi
"proqram tapa bilmədi" ilə "sayt bizi bloklayır" arasındakı fərqi görür.

---

## 14. Niyə səhifə bir dəfə yüklənir?

İlk yanaşmada hər toplayıcı (`sehife`, `texnologiya`, `dizayn`, `reklam`) səhifəni özü
yükləyəcəkdi — bu, sayta **4 eyni sorğu** deməkdir. İndi `surat.olc_ve_getir()` səhifəni
bir dəfə gətirir, yüklənmə vaxtını ölçür və HTML-i bütün toplayıcılar arasında paylaşır.

Nəticə: sayta 4 dəfə az yük, analiz isə 4-6 saniyədən **1.2 saniyəyə** düşdü.

## 15. Niyə DigitalOcean əvəzinə Railway?

Plan DigitalOcean Droplet idi (30 iyul). 31 iyulda Railway seçildi, çünki
Droplet yolu **yerləşdirməyə aid olmayan çoxlu iş** tələb edirdi: Caddy
konfiqurasiyası, Let's Encrypt, domen (və ya sslip.io), SSH, swap faylı,
Docker qurulumu. Railway bunların hamısını əvəz edir — hər xidmətə avtomatik
HTTPS və ünvan verir.

Ödənən qiymət: `docker-compose.prod.yml` yerləşdirmə vasitəsi olmaqdan çıxdı
(Railway compose işlətmir, hər xidmət ayrıca qurulur). Fayl silinmədi —
lokalda tam dəsti sınamaq üçün dəyərlidir və məhz o sınaq iki səhv tutdu.

**Vacib nəticə:** Caddy çıxanda orada saxlanan təhlükəsizlik başlıqları da
gedirdi — `/muasir/onizleme` üçün `Content-Security-Policy: sandbox` daxil.
Onlar tətbiqin öz middleware-inə köçürüldü (`backend/main.py`). İndi qoruma
hostinqdən asılı deyil: lokalda, Docker-də və Railway-də eynidir. Bu, əslində
əvvəlkindən yaxşıdır — proxy dəyişəndə qoruma səssizcə itmir.

## 16. Niyə n8n serverə çıxarılmadı?

Müəllim n8n-in də onlayn olmasını istəmişdi, amma iki maneə vardı.

**Gemma agenti.** 4-cü workflow `lmChatOllama` node-u ilə `gemma3:4b`-yə
müraciət edir. Model işləmək üçün ~5 GB RAM istəyir; Railway RAM-ı $10/GB/ay
hesablayır, yəni tək bu model ayda ~$50 deməkdir. Üstəlik bulud maşınında GPU
yoxdur — cavab prosessorda gələcək, yəni yavaş.

**Volume icazəsi.** Railway volume-ları root sahibliyi ilə bağlayır, n8n isə
`node` istifadəçisi kimi işləyir: `EACCES: permission denied, open
'/home/node/.n8n/config'`. Konteyner qalxmadı.

Seçim: n8n lokalda qalır və buludakı API ilə HTTPS üzərindən danışır
(`SAYTLUPA_API` + `API_ACAR` mühit dəyişənləri). Gemma agenti lokal Ollama ilə
tam sürətində işləyir, xərc sıfırdır. Şərt odur ki, nümayiş zamanı həmin
kompüter açıq olsun.

## 17. Niyə Gemma nişanı «yoxdur» yazmır?

Buludda Ollama yoxdur, ona görə `/api/health` əvvəl `gemma: false` qaytarırdı.
Bu, doğru idi, amma **yanıldıcı**: baxan adam nəyinsə sındığını düşünürdü.
Halbuki Gemma bu tətbiqdə onsuz da çağırılmır — re-ranking Gemini-dədir və
model zəncirində Claude/Gemini var; Gemma yalnız n8n agentində işlədilir.

İki dəyişiklik edildi. Birincisi: vəziyyət indi üç haldan biridir — `hazir`,
`elcatmaz`, `islenmir`. Sonuncu halda Ollama-ya sorğu ümumiyyətlə atılmır
(hər sağlamlıq yoxlamasında 2 saniyəlik gözləmə aradan qalxdı). İkincisi:
`GEMMA_QEYDI` dəyişəni ilə açıq modelin **yeri** bəyan edilir və nişan yaşıl
olur — `Gemma: n8n agentində`.

Niyə sadəcə yaşıl «Gemma» yazılmadı: tətbiqin özündə model yoxdur, bunu
gizlətsək `/api/health` ilə interfeys bir-birinə zidd olardı. İndiki variant
həm doğrudur, həm də sınmış görünmür.
