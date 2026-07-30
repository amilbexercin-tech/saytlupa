# Ümumi məlumat — SaytLupa nədir və necə işləyir

Bu sənəd layihəni əvvəldən, addım-addım izah edir. Texniki təfərrüat üçün
[`MEMARLIQ.md`](MEMARLIQ.md), qərarların səbəbi üçün [`QERARLAR.md`](QERARLAR.md),
işə salma üçün [`ISTIFADE.md`](ISTIFADE.md).

---

## 1. Problem və ideya

Bir saytı qiymətləndirmək lazım gələndə adam onlarla ayrı alət açır: WHOIS, DNS
yoxlayıcı, SSL yoxlayıcı, PageSpeed, texnologiya aşkarlayıcı, SEO aləti. Hər
biri ayrı pəncərə, ayrı format, heç biri digərini görmür.

SaytLupa bir cümlə ilə budur: **link yaz → saytı tanı → saytla danış → daha
yaxşısını qur.**

Dörd mərhələ:

1. Sayt hərtərəfli analiz olunur (domen, DNS, sertifikat, texnologiya, sürət,
   dizayn, reklam alətləri, məzmun)
2. AI 6 bəndlik peşəkar hesabat yazır
3. Saytın **məzmunu ilə söhbət** edirsən — «bu sayt nə üçündür?» soruşursan,
   mənbə linki ilə cavab alırsan
4. İstəsən saytın **müasir versiyasını** qurdurursan

---

## 2. Bir analiz necə gedir

İstifadəçi ünvanı yazır, «Analiz et» basır. Arxada bunlar baş verir:

```
1. Səhifə BİR DƏFƏ yüklənir     → HTML bütün toplayıcılar arasında paylaşılır
2. Bot qoruması yoxlanılır       → varsa məzmun analizi etibarsızdır, dürüst deyilir
3. 9 toplayıcı PARALEL işləyir   → asyncio.gather
4. Crawler saytı gəzir           → robots.txt + sitemap + enliyinə gəziş (BFS)
5. RAG indeksi qurulur           → parçalama → embedding → pgvector
6. AI hesabat yazılır            → LCEL zənciri
```

Bütün bunlar **canlı** görünür — SSE (Server-Sent Events) ilə hər addım ekrana
düşür:

```
[0.3s] domen         hazır
[1.2s] toplayıcılar  9/9 uğurlu
[1.7s] səhifə  1/30  https://asan.gov.az
[3.2s] RAG hazır     104 parça · gemini · 4.1 san
```

Ölçmə: 9 toplayıcının paralel icrası **1.2 saniyə**. Ardıcıl olsaydı 4-6 saniyə
çəkərdi, çünki hər biri şəbəkə gözləyir.

---

## 3. Memarlıq

Hər modul **bir iş** görür:

| Qat | Fayllar | İş |
|---|---|---|
| Toplayıcılar | `collectors/` — 9 fayl | hər biri bir məlumat növü |
| Gəziş | `crawler.py`, `metn.py` | səhifə yığma, HTML → təmiz mətn |
| RAG | `rag/` — 5 fayl | parçalama, embedding, axtarış, re-ranking, yaddaş |
| Zəncirlər | `chains/` — 4 fayl | LCEL: hesabat, RAG cavabı, müasir versiya |
| Təhvil | `builder/` — 5 fayl | 4 düymənin arxası |
| Səth | `main.py` | REST + SSE + WebSocket |

Dekoratorlar təkrarı aradan qaldırır: `@cached`, `@retry`, `@timed`,
`@safe_collector`. Sonuncusu vacibdir — **bir toplayıcı sınsa digərləri davam
edir**, analiz bütövlükdə dayanmır.

---

## 4. RAG — layihənin ürəyi

Saytın 30 səhifəsini bütövlükdə modelə göndərmək olmaz (kontekst limiti). Ona
görə:

1. **Parçalama** — mətn 800 simvollıq parçalara bölünür, 120 simvol üst-üstə
   düşür (cümlə ortadan kəsilməsin)
2. **Embedding** — hər parça `gemini-embedding-001` ilə vektora çevrilir, 768
   ölçüyə qısaldılır
3. **Saxlama** — `pgvector` (PostgreSQL genişlənməsi)
4. **Axtarış** — **hibrid**: vektor oxşarlığı + açar söz axtarışı, nəticələr
   RRF ilə birləşdirilir
5. **Re-ranking** — namizədləri kiçik model yenidən sıralayır
6. **Yaddaş** — əvvəlki suallar xatırlanır

Ölçmə (10 sual, `asan.gov.az`):

| Üsul | Hit@1 | Hit@3 | MRR |
|---|---|---|---|
| Yalnız embedding | 8/10 | 10/10 | 0.90 |
| + re-ranking | **10/10** | 10/10 | **1.00** |

Re-ranking dəqiqliyi 100%-ə çatdırdı, əvəzində 5.5 saniyə əlavə etdi.

---

## 5. Üç model, hər biri öz işində

| İş | Model | Səbəb |
|---|---|---|
| Hesabat, RAG cavabı, müasir versiya | **Claude sonnet-5** | ən keyfiyyətli düşüncə, uzun kontekst |
| Embedding | **Gemini** | ucuz, sürətli |
| Re-ranking, təsnifat | **Gemma 3 4B** (lokal) | pulsuz, ölçmə ilə təsdiqləndi |

Fallback zənciri var: Claude → Gemini → Gemma. Açar olmasa layihə dayanmır.

Beş ölçmə sənədləşdirilib ([`../docs/model-secimi.md`](../docs/model-secimi.md)).
Sonuncusu maraqlıdır: `claude-opus-5` sınandı — **25% yavaş** oldu, fayl ölçüsü
eyni, üstəlik qurduğu səhifədə hero bölməsi ağ üzərində ağ mətnlə çıxdı, yəni
oxunmurdu. Model dəyişmədi. Sənəddə dürüst yazılıb: bu bir ölçmədir və prompt
sonnet ilə tənzimlənib.

---

## 6. Avtomatlaşdırma və inteqrasiya

**n8n — 4 workflow:** webhook ilə analiz başlatma; hər gün 09:00-da rəqib
izləmə (sayt dəyişsə Telegram-a xəbər); mərkəzi xəta workflow-u; lokal Gemma
agenti (sualı təsnif edib düzgün endpoint-ə yönləndirir).

**MCP serveri — 3 alət.** Layihə Claude Code və Cursor-a **tool kimi** verilir:
`sayt_analiz_et`, `saytla_danis`, `saytlari_muqayise_et`. Vacib qərar: MCP
serveri işi **özü görmür**, işləyən FastAPI-yə HTTP sorğusu göndərir. Səbəb —
crawler, embedding və LLM kiçik alt-prosesdə yox, serverdə işləməlidir.

---

## 7. Ən vacib prinsip: uydurma yazılmır

Bu, layihənin kimliyidir.

**`.az` domenlərinin pulsuz WHOIS-u yoxdur.** Yaşı uydurmaq əvəzinə arxiv.org-a
baxılır və açıq yazılır: *«Bu TLD üçün pulsuz WHOIS yoxdur. Arxiv.org-a görə
sayt ən azı 2013-dən mövcuddur (~13.5 il). Bu TƏXMİNİ göstəricidir.»*

**Bot qoruması.** `kontakt.az` Cloudflare arxasındadır — bizə real məzmun yox,
yoxlama səhifəsi verilir. Sistem bunu aşkarlayır və hesabat qurmur.

**Müqayisədə üstünlük hökmü.** Ən incə hissə budur. İlk versiyada `kontakt.az`
«Skript sayı 1 ✓» ilə üstün görünürdü — halbuki o rəqəm yoxlama səhifəsinindir.
Yəni interfeys bloklanmış saytı «daha yaxşı» elan edirdi. İndi tərəflərdən biri
etibarsızdırsa saytın məzmununa əsaslanan ölçülərdə **hökm verilmir**; yalnız
domen yaşı və sertifikat müqayisə olunur, çünki onlar saytın verdiyi HTML-dən
asılı deyil.

**Etika.** Crawler `robots.txt`-ə hörmət edir, sorğu tezliyi məhdudlaşdırılır,
arşivdən xarici izləyici skriptlər silinir.

---

## 8. İki böyük dərs

**Funksiyanı gizlətmək onu yox etməkdir.** Kodda bir neçə yerdə funksiya
səssizcə gizlənirdi: söhbət kartı (`if chunk_sayi > 0 göstər`) bloklanmış
saytda yoxa çıxırdı, əlaqə bölməsi boş qalırdı, `domen` toplayıcısı istifadəçiyə
`HTTPStatusError: 404 rdap.org` göstərirdi. Hamısı düzəldildi. Boş bölmə,
səbəbi yazılmaqla, gizli bölmədən yaxşıdır.

**Örtülməyən yol gec-tez sınır.** Bir funksiya silinərkən onun istifadə yeri
yoxlanılmadı, `NameError` yarandı və **192 testin heç biri tutmadı** — çünki
həmin yol örtülməmişdi. Səhv canlı serverdə üzə çıxdı. Boşluq bağlandı, 3 test
yazıldı və testlərin işlədiyi səhvi qəsdən geri qoymaqla yoxlanıldı.

---

## 9. Rəqəmlər

| Göstərici | Dəyər |
|---|---|
| Müddət | 15 gün |
| Kod | ~7 700 sətir (+ ~2 300 sətir test və skript) |
| Testlər | **195 keçir** |
| Toplayıcı | 9 (+ bot qoruması və JS saytı aşkarlanması) |
| Tam analiz + gəziş | 3.2 saniyə |
| RAG dəqiqliyi | Hit@1 10/10 · MRR 1.00 |
| n8n workflow | 4 |
| MCP aləti | 3 |
| İnterfeys | 12 bölmə · 12 addımlıq nümayiş ssenarisi |

Kod açıqdır: <https://github.com/amilbexercin-tech/saytlupa>

---

## 10. Nəyi bacarmır

Dürüstlük naminə məhdudiyyətlər də açıq yazılır:

- bot qoruması olan saytlarda məzmun analizi mümkün deyil
- brauzerdə çəkilən (React/Vue) saytların serverdən gələn HTML-i boşdur, RAG
  qurulmur
- `.az` domenlərinin dəqiq yaşı alınmır
- PageSpeed açarsız kiçik kvota ilə işləyir

Bunların hamısı interfeysdə **səbəbi ilə** bildirilir — sistem susmur və
uydurmur.
