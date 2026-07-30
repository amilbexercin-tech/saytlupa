/* Nəticələrin ekrana çıxarılması.
   Bütün funksiyalar bir analiz obyektini alıb müvafiq bölməni doldurur. */

const el = (id) => document.getElementById(id);
const gorset = (id) => el(id).classList.remove('gizli');
const gizlet = (id) => el(id).classList.add('gizli');

/* HTML-ə düşən mətn həmişə təmizlənir — analiz olunan sayt bizə istənilən
   məzmunu göndərə bilər. */
function tehlukesiz(metn) {
  const d = document.createElement('div');
  d.textContent = metn == null ? '' : String(metn);
  return d.innerHTML;
}

/* Toplayıcının məlumatı; uğursuz olubsa boş obyekt */
function data(xam, ad) {
  const q = (xam.neticeler || {})[ad];
  return q && q.ugurlu ? (q.data || {}) : {};
}

function qutu(etiket, deyer, qeyd) {
  return `<div class="qutu">
    <div class="etiket">${tehlukesiz(etiket)}</div>
    <div class="deyer">${tehlukesiz(deyer ?? '—')}</div>
    ${qeyd ? `<div class="qeyd">${tehlukesiz(qeyd)}</div>` : ''}
  </div>`;
}

function setir(ad, deyer) {
  if (deyer == null || deyer === '' || (Array.isArray(deyer) && !deyer.length)) return '';
  const m = Array.isArray(deyer) ? deyer.join(', ') : deyer;
  return `<tr><td>${tehlukesiz(ad)}</td><td>${tehlukesiz(m)}</td></tr>`;
}

function teqler(siyahi, sinif = '') {
  if (!siyahi || !siyahi.length) return '<span class="teq">tapılmadı</span>';
  return siyahi.map((t) => `<span class="teq ${sinif}">${tehlukesiz(t)}</span>`).join('');
}

/* Zolaqlı qrafik.
   `tersine` — kiçik dəyər yaxşıdırsa (yüklənmə vaxtı, HTML ölçüsü, skript sayı).
   Belə hallarda zolaq xam nisbəti yox, **nə qədər yaxşı olduğunu** göstərir:
   0.09 saniyəyə yüklənən sayt boş zolaq yox, dolu yaşıl zolaq almalıdır. */
function zolaq(ad, deyer, maks, vahid, tersine) {
  const xam = Math.min(100, (deyer / maks) * 100);
  const yaxsiliq = tersine ? 100 - xam : xam;
  const en = Math.max(3, yaxsiliq);
  const sinif = yaxsiliq > 66 ? 'yaxsi' : yaxsiliq > 33 ? 'orta' : 'pis';
  return `<div class="zolaq-setir">
    <span>${tehlukesiz(ad)}</span>
    <span class="zolaq-fon"><span class="zolaq ${sinif}" style="width:${en}%"></span></span>
    <span class="zolaq-deyer">${tehlukesiz(deyer)}${vahid}</span>
  </div>`;
}

/* ---------------- bölmələr ---------------- */

function umumiBaxis(n) {
  const x = n.xam, d = data(x, 'domen'), t = data(x, 'texnologiya');
  const g = data(x, 'geo'), s = data(x, 'surat').oz_olcme || {};

  const yas = d.yas_il
    ? [`${d.yas_il} il`, `dəqiq (${d.menbe || ''})`]
    : d.arxiv_ipucu && d.arxiv_ipucu.en_azi_yas_il
      ? [`~${d.arxiv_ipucu.en_azi_yas_il} il`, 'TƏXMİNİ — WHOIS yoxdur']
      : ['—', 'müəyyən edilmədi'];

  el('umumi').innerHTML = [
    qutu('Domen', n.domain),
    qutu('Domenin yaşı', yas[0], yas[1]),
    qutu('Əsas texnologiya', (t.texnologiyalar || []).slice(0, 2).join(', ') || '—'),
    qutu('Server yeri', g.olke ? `${g.olke}${g.seher ? ' / ' + g.seher : ''}` : '—', g.provayder),
    qutu('Yüklənmə', s.yuklenme_saniye != null ? s.yuklenme_saniye + ' san' : '—',
         s.html_olcusu_kb ? s.html_olcusu_kb + ' KB HTML' : ''),
    qutu('RAG bazası', `${n.chunk_sayi} parça`, `${n.sehife_sayi} səhifədən`),
  ].join('');
  gorset('k-umumi');
}

function aiHesabat(n) {
  const h = n.ai_hesabat;
  if (!h || !h.meqsed) {
    const sebeb = (n.xam.hesabat_olcme || {}).sebeb;
    if (sebeb) {
      el('hesabat').innerHTML = `<div class="xeb sari">${tehlukesiz(sebeb)}</div>`;
      gorset('k-hesabat');
    }
    return;
  }

  const bend = (basliq, mezmun) => {
    if (!mezmun || (Array.isArray(mezmun) && !mezmun.length)) return '';
    const govde = Array.isArray(mezmun)
      ? `<ul>${mezmun.map((s) => `<li>${tehlukesiz(s)}</li>`).join('')}</ul>`
      : `<p>${tehlukesiz(mezmun)}</p>`;
    return `<div class="hesabat-bend"><h3>${basliq}</h3>${govde}</div>`;
  };

  const olcme = n.xam.hesabat_olcme || {};
  el('hesabat').innerHTML =
    bend('1. Saytın məqsədi', h.meqsed) +
    bend('2. Hədəf auditoriya', h.hedef_auditoriya) +
    bend('3. Texnologiyalar', h.texnologiyalar) +
    bend('4. Performans problemləri', h.performans_problemleri) +
    bend('5. SEO çatışmazlıqları', h.seo_catismazliqlari) +
    bend('6. Müasir versiya üçün tövsiyələr', h.muasir_versiya_tovsiyeleri) +
    `<div class="olcme-qeyd">Model: ${tehlukesiz(olcme.model || '—')} ·
      ${tehlukesiz(olcme.saniye || 0)} san</div>`;
  gorset('k-hesabat');
}

function texnologiyalar(n) {
  const t = data(n.xam, 'texnologiya');
  el('texno').innerHTML = teqler(t.texnologiyalar, 'mavi');
  const k = t.kateqoriyalar || {};
  el('texno-cedvel').innerHTML = Object.keys(k).length
    ? `<table class="cedvel"><tbody>${Object.entries(k)
        .map(([ad, siyahi]) => setir(ad, siyahi)).join('')}</tbody></table>`
    : '';
  gorset('k-texno');
}

function server(n) {
  const d = data(n.xam, 'dns'), g = data(n.xam, 'geo'), s = data(n.xam, 'sertifikat');
  el('server').innerHTML =
    setir('IP ünvanı', d.a) +
    setir('Ölkə / şəhər', g.olke ? `${g.olke} / ${g.seher || '—'}` : '') +
    setir('Provayder', g.provayder) +
    setir('Təşkilat', g.teskilat) +
    setir('CDN', d.cdn || 'yoxdur') +
    setir('Poçt xidməti', d.poct_xidmeti) +
    setir('NS serverləri', (d.ns || []).slice(0, 3)) +
    setir('IPv6', d.ipv6_destekleyir ? 'var' : 'yoxdur') +
    setir('SPF / DMARC', `${d.spf_var ? 'var' : 'yox'} / ${d.dmarc_var ? 'var' : 'yox'}`) +
    setir('SSL verən', s.veren) +
    setir('SSL bitməsinə qalıb', s.qalan_gun != null ? s.qalan_gun + ' gün' : '') +
    setir('TLS protokolu', s.protokol);
  gorset('k-server');
}

function performans(n) {
  const s = data(n.xam, 'surat'), o = s.oz_olcme || {}, m = s.mobil;
  let html = '';

  if (m && m.bal != null) html += zolaq('PageSpeed (mobil)', m.bal, 100, '/100');
  if (o.yuklenme_saniye != null) html += zolaq('Yüklənmə vaxtı', o.yuklenme_saniye, 5, ' san', true);
  if (o.html_olcusu_kb != null) html += zolaq('HTML ölçüsü', o.html_olcusu_kb, 500, ' KB', true);
  if (o.skript_sayi != null) html += zolaq('Skript sayı', o.skript_sayi, 40, '', true);
  if (o.css_sayi != null) html += zolaq('CSS faylı', o.css_sayi, 15, '', true);
  if (o.sekil_sayi) html += zolaq('Lazy loading', o.lazy_sekil_sayi || 0, o.sekil_sayi, ` / ${o.sekil_sayi}`);

  el('performans').innerHTML = html || '<p class="alt">Məlumat yoxdur</p>';
  el('performans-qeyd').innerHTML =
    (!m ? `<div class="xeb sari">${tehlukesiz(s.pagespeed_qeyd ||
      'PageSpeed balı alınmadı — yalnız öz ölçmələrimiz göstərilir.')}</div>` : '') +
    (o.sixilma ? `<p class="olcme-qeyd">Sıxılma: ${tehlukesiz(o.sixilma)}</p>` : '');
  gorset('k-performans');
}

function dizayn(n) {
  const d = data(n.xam, 'dizayn');
  el('renqler').innerHTML = (d.esas_renqler || []).length
    ? d.esas_renqler.map((r) =>
        `<div class="reng"><div class="numune" style="background:${tehlukesiz(r.reng)}"></div>
         ${tehlukesiz(r.reng)}</div>`).join('')
    : '<span class="teq">tapılmadı</span>';
  const oz = (d.sriftler || []).map((s) => s.ad).concat(d.google_sriftler || []);
  el('sriftler').innerHTML = teqler([...new Set(oz)], 'mavi') +
    ((d.ehtiyat_sriftler || []).length
      ? `<span class="teq" style="opacity:.6">ehtiyat: ${
          tehlukesiz(d.ehtiyat_sriftler.join(', '))}</span>`
      : '');
  gorset('k-dizayn');
}

function reklam(n) {
  const r = data(n.xam, 'reklam');
  el('reklam').innerHTML = teqler((r.aletler || []).map((a) => `${a.ad} · ${a.kateqoriya}`));
  gorset('k-reklam');
}

function mezmun(n) {
  const s = data(n.xam, 'sehife'), b = s.basliq_saylari || {};
  el('mezmun').innerHTML =
    setir('Başlıq', s.basliq) +
    setir('Meta description', s.tesvir || 'YOXDUR') +
    setir('Dil (lang)', s.dil || 'təyin edilməyib') +
    setir('Canonical', s.canonical || 'yoxdur') +
    setir('Başlıq strukturu', `H1: ${b.h1 || 0}, H2: ${b.h2 || 0}, H3: ${b.h3 || 0}`) +
    setir('Şəkil / skript / form', `${s.sekil_sayi || 0} / ${s.skript_sayi || 0} / ${s.form_sayi || 0}`) +
    setir('Mobil uyğunluq', s.mobil_uygun ? 'var' : 'YOXDUR') +
    setir('Daxili / xarici link', `${s.daxili_link_sayi || 0} / ${s.xarici_link_sayi || 0}`) +
    setir('Yığılan səhifə', n.sehife_sayi);

  el('elaqe').innerHTML = elaqeBloku(n, s);
  gorset('k-mezmun');
}

/* Sosial şəbəkə və əlaqə. Boş qalanda səbəbi yazılır — istifadəçi "proqram
   tapmadı" ilə "sayt bizi bloklayır" arasındakı fərqi görməlidir. */
function elaqeBloku(n, s) {
  const sosial = s.sosial_linkler || {};
  const adlar = Object.keys(sosial);
  const menbeler = s.elaqe_menbeleri || {};

  if (adlar.length || (s.epostalar || []).length || (s.telefonlar || []).length) {
    const teqSosial = adlar.map((ad) =>
      `<a class="teq mavi" href="${tehlukesiz(sosial[ad])}" target="_blank"
          rel="noopener" title="${tehlukesiz(menbeler[ad] || 'ana səhifədə tapıldı')}"
       >${tehlukesiz(ad)}</a>`).join('');
    return teqSosial + teqler((s.epostalar || []).concat(s.telefonlar || []));
  }

  const qoruma = (n.xam || {}).qoruma || {};
  if (qoruma.qorunur) {
    return `<span class="teq">Sayt ${tehlukesiz(qoruma.xidmet || 'bot qoruması')}
      arxasındadır — səhifənin məzmunu bizə verilmədi, əlaqə məlumatı
      çıxarıla bilmədi</span>`;
  }
  const js = (n.xam || {}).js_sayt || {};
  if (js.js_ile_qurulur) {
    return `<span class="teq">Sayt ${tehlukesiz(js.cerceve || 'JS')} ilə brauzerdə
      çəkilir — serverin verdiyi HTML-də mətn yoxdur, əlaqə məlumatı
      çıxarıla bilmədi</span>`;
  }
  if (!n.sehife_sayi) {
    return '<span class="teq">Səhifə yığılmadı — əlaqə məlumatı axtarıla bilmədi</span>';
  }
  return `<span class="teq">${n.sehife_sayi} səhifənin heç birində sosial şəbəkə
    linki, e-poçt və ya telefon tapılmadı</span>`;
}

async function sehifeSiyahisi(siteId) {
  try {
    const s = await (await fetch(`/api/sites/${siteId}/pages`)).json();
    if (!s.length) return;
    el('sehifeler').innerHTML = s.slice(0, 30).map((p) =>
      `<tr><td><a href="${tehlukesiz(p.url)}" target="_blank" rel="noopener"
         style="color:var(--vurgu);text-decoration:none">${tehlukesiz(p.basliq || p.url)}</a></td>
       <td>${tehlukesiz(p.metn_uzunlugu)} simvol</td></tr>`).join('');
    gorset('k-sehifeler');
  } catch { /* səhifə siyahısı olmasa da nəticə göstərilir */ }
}

/* ---------------- hamısı ---------------- */

function neticeniCiz(n) {
  /* Boş nəticənin səbəbi başda yazılır: ya sayt bizi bloklayır, ya da
     məzmununu serverdə vermir. Səbəbsiz boş bölmə nasazlıq kimi görünür. */
  const x = n.xam || {}, q = x.qoruma || {}, j = x.js_sayt || {};
  el('xeberdarliq').innerHTML =
    q.qorunur ? `<div class="xeb">⚠️ ${tehlukesiz(q.qeyd)}</div>`
    : j.js_ile_qurulur ? `<div class="xeb">⚠️ ${tehlukesiz(j.qeyd)}</div>`
    : '';

  umumiBaxis(n);
  aiHesabat(n);
  texnologiyalar(n);
  server(n);
  performans(n);
  dizayn(n);
  reklam(n);
  mezmun(n);
  sehifeSiyahisi(n.site_id);

  gorset('k-tehvil');
  if (n.chunk_sayi > 0) gorset('k-sohbet');
}
