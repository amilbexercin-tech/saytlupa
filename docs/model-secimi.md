# Hansı iş hansı modelə verilməlidir? (ölçmə ilə)

> Ölçmə tarixi: 2026-07-28 · Skript: [`scripts/model_olcme.py`](../scripts/model_olcme.py)
> Xam nəticə: [`model-olcme-neticesi.json`](model-olcme-neticesi.json)
> Maşın: Intel i5-11320H, 4 nüvə, **7.8 GB RAM**, Ollama (lokal)

## Problem

RAG-da **re-ranking** kütləvi işdir: hər sual üçün vektor axtarışından gələn ~20
namizəd parça ayrıca qiymətləndirilməlidir. Bunu ən güclü modelə (Claude) vermək
həm bahadır, həm yavaşdır. Sual: **açıq və pulsuz Gemma bu işi kifayət qədər
yaxşı görürmü?**

## Ölçmə üsulu

8 sual-parça cütü. Hər cütün doğru balı əvvəlcədən təyin olunub (0 = əlaqəsiz,
10 = tam cavab). Model 0-10 arası bal verir. `|model - doğru| ≤ 3` olsa düzgün
sayılır. Temperatur 0, çağırış limiti 120 saniyə.

Sual və parçalar **Azərbaycan dilindədir** — layihə Azərbaycan saytlarını analiz
edəcək, ona görə ölçmə də real şəraiti əks etdirməlidir.

## Nəticə

| Model | Ölçü | Dəqiqlik | Orta fərq | Orta vaxt | Cavabsız |
|---|---|---|---|---|---|
| **gemma3:4b** | 3.3 GB | **100%** (8/8) | **0.5** | 7.6 san | 0 |
| gemma3:1b | 0.8 GB | 50% (4/8) | 3.17 | 4.6 san | 2 |
| gemma4:12b | 7.0 GB | 0% (0/8) | — | **99.1 san** | 8 |

### Nə göründü

**`gemma3:1b` — kiçikdir, amma etibarsızdır.** "Bütün məhsullara 12 ay rəsmi
zəmanət verilir" cümləsinə zəmanət sualı üçün **2 bal** verdi; tamamilə əlaqəsiz
ödəniş cümləsinə isə **10 bal**. İki halda ümumiyyətlə rəqəm qaytarmadı, sualın
sözlərini təkrarladı. Ayrıca ingilis dilində də sınandı — 4 sualın hamısına eyni
cavabı verdi. 1 milyard parametr göstəriş izləmək üçün azdır.

**`gemma4:12b` — bu maşında işləmir.** 7 GB model 7.8 GB RAM-da swap-a düşür;
hər çağırış 92-122 saniyə çəkdi və heç birindən oxunaqlı rəqəm alınmadı.
Keyfiyyət sualı belə qalxmır — sadəcə istifadəyə yararsızdır.

**`gemma3:4b` — düzgün seçim.** 8 sualın hamısını düz qiymətləndirdi, orta fərq
0.5 bal. İlk çağırış 25 saniyə (model yaddaşa yüklənir), sonrakılar ~6 saniyə.

## Qərar

| İş | Model | Səbəb |
|---|---|---|
| AI hesabat, RAG cavabı, müasir versiya | **Claude** | ən keyfiyyətli düşüncə, uzun kontekst |
| Embedding | **Gemini** `gemini-embedding-001` | ucuz, sürətli, 768 ölçüyə qısaldılır |
| **Re-ranking**, təsnifat, n8n agenti | **Gemma 3 4B** (lokal) | ölçmə ilə təsdiqləndi: 100% dəqiqlik, pulsuz |
| Ehtiyat | Gemini → Gemma | Claude əlçatmaz olsa layihə dayanmır |

---

# 2-ci ölçmə: toplu re-ranking real şəraitdə (2026-07-28)

Birinci ölçmədən sonra gözlənti belə idi: namizədləri **bir promptda** göndərsək
1 çağırış ≈ 6-10 saniyə olar. Real sistemdə yoxlandı — **gözlənti düz çıxmadı.**

## Parametr ölçməsi

`scripts/rerank_olcme.py` · sayt: `asan.gov.az` · 60 chunk

| Namizəd × simvol | Vaxt | Ən yaxşı mənbə |
|---|---|---|
| 4 × 200 | 48.1 san | ✅ düzgün |
| 8 × 200 | 46.3 san | ✅ düzgün |
| 8 × 400 | 69.1 san | ✅ düzgün |
| 12 × 200 | 60.5 san | ✅ düzgün |
| 20 × 400 | 134.3 san | ❌ **səhv səhifə** |
| re-ranking yoxdur | ~0 san | ✅ düzgün |

Səbəb aydındır: 1-ci ölçmədə prompt bir cümlə idi (~30 söz). Burada isə prompta
8-20 mətn parçası düşür — girişin özü yüzlərlə token, və bu maşında (4 nüvə, GPU
yoxdur) hər token bahalıdır. **Prompt uzunluğu gecikməni xətti artırır.**

## Keyfiyyət ölçməsi

Bir sual üzərində qərar vermək düzgün olmazdı. `docs/olcme-desti.json`-da
**10 sual** var, hər birinin cavabının hansı səhifədə olduğu qeyd edilib.
Skript: `scripts/rag_olcme.py`.

| Re-ranking | Hit@1 | Hit@3 | MRR | Orta vaxt |
|---|---|---|---|---|
| **yox** (yalnız hibrid axtarış) | 6/10 | **9/10** | 0.700 | **0.0 san** |
| gemma3:4b | **7/10** | 8/10 | **0.775** | 50.3 san |

## Qərar

Re-ranking **standart olaraq söndürülüb** (`.env` → `RERANK=`).

Səbəb: Gemma bir sualı yuxarı qaldırır (Hit@1 6→7), amma başqa birini aşağı salır
(Hit@3 9→8). Xalis qazanc MRR-də +0.075-dir və bunun qiyməti **hər sual üçün 50
saniyə**dir. İnteraktiv söhbətdə istifadəçi 50 saniyə gözləyə bilməz.

Kod yerində qalır və `RERANK=gemma` ilə açılır — həm nümayiş üçün, həm də daha
güclü maşında faydalı ola biləcəyi üçün.

## Nə vaxt yenidən ölçülməlidir

Bu ölçmə **lokal hashing embedding** ilə aparılıb (`GOOGLE_API_KEY` hələ yoxdur).
Lokal üsul sinonimləri tutmur, yalnız söz oxşarlığına baxır. Gemini embedding-i
qoşulanda:

1. Hibrid axtarışın öz dəqiqliyi (6/10) yüksəlməlidir
2. `RERANK=gemini` variantı ölçülməlidir — bulud modeli 1-2 saniyə çəkir,
   50 saniyə deyil; bu halda re-ranking sərfəli ola bilər

> ✅ Hər ikisi 2026-07-29-da ölçüldü — aşağıdakı bölmə.

---

# 3-cü ölçmə: Gemini embedding + Gemini re-ranking (2026-07-29)

`GOOGLE_API_KEY` gəldi. Eyni skript, eyni 10 suallıq dəst, eyni sayt
(`asan.gov.az`), amma indi **real semantik embedding** ilə.

## Model adları dəyişdi

Açar işlədi, lakin iki model adı köhnəlmişdi:

| Köhnə | Nə oldu | Yeni |
|---|---|---|
| `gemini-2.5-flash` | 404 — *"no longer available to new users"* | `gemini-3.6-flash` |
| `text-embedding-004` | model siyahısında yoxdur | `gemini-embedding-001` |

`gemini-embedding-001` standart olaraq **3072 ölçü** verir; baza sütunumuz 768-dir.
`output_dimensionality=768` verilir və vektor **yenidən normallaşdırılır** —
qısaldılmış (Matryoshka) vektorun norması 1 deyil, ölçüldü: ~0.59.

## Nəticə

| Re-ranking | Embedding | Hit@1 | Hit@3 | MRR | Orta vaxt |
|---|---|---|---|---|---|
| yox | lokal hashing (2026-07-28) | 6/10 | 9/10 | 0.700 | 0.0 san |
| yox | **Gemini** | **8/10** | **10/10** | **0.900** | 1.8 san |
| gemma3:4b | lokal hashing (2026-07-28) | 7/10 | 8/10 | 0.775 | 50.3 san |
| **gemini-3.6-flash** | **Gemini** | **10/10** | **10/10** | **1.000** | 7.3 san |

> Qeyd: 28 iyul ölçməsi 15 səhifəlik, bu ölçmə 20 səhifəlik indeks üzərindədir —
> korpus eyni deyil, ona görə rəqəmlər **istiqamət göstərir**, dəqiq nəzarətli
> müqayisə deyil. Sual dəsti və sayt eynidir.

Ayrıca ölçüldü: sinonim cümlələrin oxşarlığı **0.936**, əlaqəsiz cümlələrinki
**0.623**. Lokal hashing üsulunda sinonim cütü demək olar tutulmurdu.

## Qərar dəyişdi

Re-ranking **açıldı**: `.env` → `RERANK=gemini`.

Səbəb: bulud modeli lokal Gemma-nın 50 saniyəsi əvəzinə ~5.5 saniyə əlavə edir və
axtarışı **10/10-a** qaldırır. Gemma ilə qərar tərsinə idi (bir sualı qaldırıb
başqasını salırdı, qiyməti 50 saniyə). Ölçmə dəyişdi — qərar da dəyişdi.

`config.py`-dakı **standart dəyər boş qalır** (`rerank: str = ""`): açarı olmayan
maşında re-ranking özbaşına qoşulmamalıdır.

---

# 4-cü ölçmə: müasir versiyanı kim yaxşı qurur? (2026-07-29)

## Problem

⚡ **Müasir versiyanı qur** düyməsi analizdən çıxan məlumatı tək fayllıq HTML-ə
çevirir. Bu, layihənin **ən ağır** LLM işidir: uzun kontekst (analiz + məzmun
xülasəsi) girişdə, tam səhifə çıxışda. 29 iyulda yalnız Gemini ilə ölçülmüşdü;
Anthropic açarı gələndən sonra Claude variantı da ölçüldü.

## Ölçmə

Eyni sayt (`asan.gov.az`, analiz #46), eyni prompt, eyni zəncir
(`chains/muasir.py`), fərq yalnız modeldədir.

| Model | Vaxt | Fayl ölçüsü | Nəticə |
|---|---|---|---|
| `gemini-3.6-flash` | 78.6 san | 51 KB | işlək səhifə |
| **`claude-sonnet-5`** | **72.9 san** | **15.6 KB** | işlək səhifə |

> Ölçmə endpoint-in tam cavab müddətidir (94.7 san), modelin öz vaxtı 72.9 san —
> qalanı fayla yazma və analizin bazadan oxunmasıdır.

## Nə göründü

**Claude eyni işi 3 dəfə kiçik fayl ilə görür.** Claude-un çıxışı 557 sətirdir
və 24 CSS dəyişəni (`--reng-...`) elan edir — stil bir yerdə toplanır.
Gemini-nin 51 KB-lıq faylı **üzərinə yazıldığı üçün içi müqayisə edilə bilmədi**;
yalnız ölçü fərqi qeydə alınıb. Səbəbi araşdırılmayıb.

Claude versiyasının görüntüsü: [`ekran/09-muasir-versiya.png`](ekran/09-muasir-versiya.png).

Vaxt fərqi (5.7 saniyə) bu ölçüdə **əhəmiyyətsizdir** — hər ikisi bir dəqiqədən
uzun çəkir, çünki çıxış bütöv səhifədir.

## Qərar

Standart model **Claude** olaraq qalır (`chains/model.py` fallback zənciri:
Claude → Gemini → Gemma). Ölçmə bu seçimi təsdiqlədi: eyni keyfiyyət, üç dəfə
kiçik fayl. Claude açarı olmayan maşında Gemini variantı da işlək nəticə verir —
nümayiş dayanmır.

---

# 5-ci ölçmə: opus daha yaxşı qurur? (2026-07-30)

## Problem

Dizayn sənədində ağır iş (müasir versiya) üçün `claude-opus-5` variantının
sınanması nəzərdə tutulmuşdu. 4-cü ölçmə sonnet ilə aparılmışdı; sual belədir:
daha güclü model daha yaxşı səhifə qururmu?

## Ölçmə

Eyni sayt, **eyni analiz (#46)**, eyni prompt, eyni zəncir (`chains/muasir.py`).
Fərq yalnız `CLAUDE_MODEL` dəyişənindədir.

| Model | Vaxt | Fayl | Media sorğusu | `aria`/`alt` | Nəticə |
|---|---|---|---|---|---|
| **`claude-sonnet-5`** | **72.9 san** | 16.9 KB | 3 | 4 | ✅ işlək səhifə |
| `claude-opus-5` | 91.5 san | 16.7 KB | 11 | 14 | ❌ hero görünmür |

## Nə göründü

Opus **25% yavaşdır**, fayl ölçüsü isə praktiki olaraq eynidir. Kağız üzərində
iki üstünlüyü var: üç dəfə çox media sorğusu (daha ciddi uyğunlaşan tərtibat) və
üç dəfə çox əlçatanlıq atributu.

**Amma səhifə sınıqdır.** Brauzerdə açanda başlıq görünmür: `section.hero`-nun
fonu şəffafdır, `h1` isə ağdır — yəni **ağ üzərində ağ mətn**. DOM-da mətn var
(`opacity: 1`, `visibility: visible`), sadəcə oxunmur. Sonnet versiyasında hero
tünd fonludur və düzgün görünür.

| Səhifə | Görüntü |
|---|---|
| sonnet (işləyir) | [`ekran/09-muasir-versiya.png`](ekran/09-muasir-versiya.png) |
| opus (hero boş görünür) | [`ekran/13-opus-muasir.png`](ekran/13-opus-muasir.png) |

Bu, **bir ölçmədir** — opus-un həmişə belə edəcəyini sübut etmir. İki dürüst
qeyd: promptun özü sonnet ilə sınanıb və ona uyğunlaşdırılıb, ölçmə də bir dəfə
aparılıb. Ona görə nəticə «opus pisdir» yox, «bu prompt opus ilə sınanmayıb»
kimi oxunmalıdır.

## Qərar

Standart model **`claude-sonnet-5`** olaraq qalır. Opus nə sürətdə, nə ölçüdə
üstünlük vermədi, üstəlik bu ölçmədə istifadəyə yararsız səhifə qaytardı —
daha bahalı modelə keçmək üçün səbəb tapılmadı.
