/* Analiz axını (SSE) və söhbət. Nəticələrin çəkilməsi `render.js`-dədir. */

const dugme = el('analiz');
const girish = el('url');
const qutuGedisat = el('gedisat');
const setirler = el('setirler');
const sualGirish = el('sual');
const gonderDugme = el('gonder');

let basla = 0;
let cariSayt = null;
let cariAnaliz = null;
let sohbetId = null;

const kecen = () => ((Date.now() - basla) / 1000).toFixed(1) + 's';

function gedisatSetri(ad, metn, sinif = '') {
  const d = document.createElement('div');
  d.className = 'setir';
  d.innerHTML = `<span class="vaxt">${kecen()}</span>` +
                `<span class="ad ${sinif}">${tehlukesiz(ad)}</span>` +
                `<span class="link">${tehlukesiz(metn)}</span>`;
  setirler.appendChild(d);
  setirler.scrollTop = setirler.scrollHeight;
}

function butunBolmeleriGizlet() {
  ['k-umumi', 'k-hesabat', 'k-tehvil', 'k-sohbet', 'k-texno', 'k-server',
   'k-performans', 'k-dizayn', 'k-reklam', 'k-mezmun', 'k-muqayise',
   'k-sehifeler'].forEach(gizlet);
  el('xeberdarliq').innerHTML = '';
  el('sohbet').innerHTML = '';
  el('tehvil-netice').innerHTML = '';
  el('muqayise-netice').innerHTML = '';
  sohbetId = null;
}

/* ---------------- açıq/qaranlıq rejim (Gün 14) ---------------- */

const temaDugme = el('d-tema');

/* Standart rejim qaranlıqdır — dizayn qara fon üzərində qurulub. */
function temaOxu() {
  return document.documentElement.getAttribute('data-tema') || 'qaranliq';
}

/* Düymədə keçiləcək rejimin işarəsi göstərilir, cari rejimin yox. */
function temaDugmeniYenile() {
  temaDugme.textContent = temaOxu() === 'isiqli' ? '🌙' : '☀️';
}

temaDugme.addEventListener('click', () => {
  const yeni = temaOxu() === 'isiqli' ? 'qaranliq' : 'isiqli';
  document.documentElement.setAttribute('data-tema', yeni);
  localStorage.setItem('tema', yeni);
  temaDugmeniYenile();
});

temaDugmeniYenile();

/* ---------------- sistem vəziyyəti ---------------- */

const nisan = (ad, aktiv) =>
  `<span class="nisan"><span class="nöqtə ${aktiv ? 'var' : 'yox'}"></span>${ad}</span>`;

fetch('/api/health').then((c) => c.json()).then((v) => {
  el('veziyyet').innerHTML = [
    nisan('Baza: ' + v.baza, true),
    nisan('Keş: ' + v.kes, true),
    nisan('Claude', v.claude),
    nisan('Gemini', v.gemini),
    nisan('Gemma', v.gemma),
  ].join('');
}).catch(() => {
  el('veziyyet').innerHTML = nisan('Server cavab vermir', false);
});

/* ---------------- analiz ---------------- */

dugme.addEventListener('click', async () => {
  const url = girish.value.trim();
  if (!url) return;

  dugme.disabled = true;
  dugme.textContent = 'Analiz gedir…';
  setirler.innerHTML = '';
  qutuGedisat.classList.remove('gizli');
  butunBolmeleriGizlet();
  basla = Date.now();
  efektMatrix(true);   // arxa fon matrix rejiminə keçir

  let cavab;
  try {
    cavab = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, max_sehife: 20 }),
    });
  } catch {
    return bitir('Server cavab vermir');
  }

  if (!cavab.ok) {
    const x = await cavab.json().catch(() => ({}));
    const mesaj = (x.detail && x.detail[0] && x.detail[0].msg) || cavab.status;
    return bitir('Yanlış ünvan: ' + mesaj);
  }

  const { analiz_id, site_id } = await cavab.json();
  cariSayt = site_id;
  cariAnaliz = analiz_id;
  gedisatSetri('başladı', url);

  const axin = new EventSource(`/api/analyze/${analiz_id}/axin`);

  const dinle = (hadise, isleyici) => axin.addEventListener(hadise, (e) => {
    isleyici(JSON.parse(e.data || '{}'));
  });

  dinle('toplayici', (d) => {
    if (d.veziyyet === 'isleyir') return;
    gedisatSetri(d.ad, d.veziyyet, d.veziyyet === 'hazir' ? 'ok' : 'pis');
  });
  dinle('toplayicilar_bitdi', (d) =>
    gedisatSetri('toplayıcılar', `${d.ugurlu}/${d.umumi} uğurlu`, 'ok'));
  dinle('gezis_atlandi', (d) => gedisatSetri('gəziş', d.sebeb, 'pis'));
  dinle('sehife', (d) => gedisatSetri(`səhifə ${d.yigilan}/${d.hedef}`, d.url));
  dinle('gezis_bitdi', (d) => gedisatSetri('gəziş bitdi', d.sehife_sayi + ' səhifə', 'ok'));
  dinle('rag', (d) => gedisatSetri('RAG indeksi', `${d.sehife}/${d.umumi} · ${d.chunk} parça`));
  dinle('rag_bitdi', (d) =>
    gedisatSetri('RAG hazır', `${d.chunk_sayi} parça · ${d.menbe} · ${d.saniye} san`, 'ok'));
  dinle('hesabat_basladi', () => gedisatSetri('AI hesabat', 'yazılır…'));
  dinle('hesabat_bitdi', (d) => gedisatSetri('AI hesabat',
    d.ugurlu ? `${d.model} · ${d.saniye} san` : (d.sebeb || 'buraxıldı'),
    d.ugurlu ? 'ok' : 'pis'));
  dinle('xeta', (d) => gedisatSetri('xəta', d.mesaj, 'pis'));

  dinle('hazir', () => {
    gedisatSetri('HAZIR', 'nəticə hazırlanır…', 'ok');
    neticeniGoster(analiz_id);
  });

  axin.addEventListener('son', () => { axin.close(); bitir(); });
  axin.onerror = () => { axin.close(); bitir(); };
});

async function neticeniGoster(analizId) {
  try {
    const n = await (await fetch(`/api/analyze/${analizId}`)).json();
    neticeniCiz(n);
    ragVeziyyeti(n.site_id);
    izlemeVeziyyeti(n.site_id);
    muqayiseHazirla(n.site_id, n.domain);
    el('k-umumi').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (x) {
    gedisatSetri('xəta', 'Nəticə oxunmadı: ' + x, 'pis');
  }
}

function bitir(xeta) {
  dugme.disabled = false;
  dugme.textContent = 'Analiz et';
  efektMatrix(false);  // matrix sönür, sakit fona qayıdır
  if (xeta) gedisatSetri('xəta', xeta, 'pis');
}

/* ---------------- söhbət (RAG) ---------------- */

async function ragVeziyyeti(siteId) {
  try {
    const r = await (await fetch(`/api/sites/${siteId}/rag`)).json();
    el('rag-veziyyet').textContent =
      `${r.chunk_sayi} parça · embedding: ${r.embedding_menbeyi}` +
      (r.modeller.claude ? ' · Claude' : r.modeller.gemini ? ' · Gemini'
        : r.modeller.gemma ? ' · ' + r.modeller.gemma_model : ' · model yoxdur');
  } catch { /* vəziyyət olmasa da söhbət işləyir */ }
}

function mesajElave(sinif, html) {
  const d = document.createElement('div');
  d.className = 'mesaj ' + sinif;
  d.innerHTML = html;
  el('sohbet').appendChild(d);
  el('sohbet').scrollTop = el('sohbet').scrollHeight;
  return d;
}

function menbeBloku(menbeler) {
  if (!menbeler || !menbeler.length) return '';
  return `<div class="menbeler">Mənbələr:` + menbeler.map((m) =>
    `<a href="${tehlukesiz(m.url)}" target="_blank" rel="noopener">
       ${tehlukesiz(m.basliq || m.url)}</a>`).join('') + `</div>`;
}

async function sualGonder() {
  const sual = sualGirish.value.trim();
  if (!sual || !cariSayt) return;

  mesajElave('men', tehlukesiz(sual));
  sualGirish.value = '';
  gonderDugme.disabled = true;
  const gozle = mesajElave('bot', '<span class="yuklenir">düşünürəm…</span>');

  try {
    const c = await (await fetch(`/api/sites/${cariSayt}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sual, session_id: sohbetId }),
    })).json();

    sohbetId = c.session_id;
    const o = c.olcme || {};
    const paraqraflar = (c.cavab || '').split('\n').filter(Boolean)
      .map((s) => `<p>${tehlukesiz(s)}</p>`).join('');

    gozle.innerHTML = paraqraflar + menbeBloku(c.menbeler) +
      `<div class="olcme-qeyd">${tehlukesiz(o.namized || 0)} namizəd →
        ${tehlukesiz(o.secilmis || 0)} seçildi · re-ranking:
        ${tehlukesiz((o.rerank || {}).usul || '—')} ·
        ${tehlukesiz(o.model || '—')} · ${tehlukesiz(o.umumi_saniye || 0)} san</div>`;
  } catch (x) {
    gozle.innerHTML = `<span class="pis">Cavab alınmadı: ${tehlukesiz(x)}</span>`;
  } finally {
    gonderDugme.disabled = false;
    sualGirish.focus();
  }
}

/* ---------------- təhvil düymələri (Gün 9) ---------------- */

const link = (unvan, ad) =>
  `<a href="${tehlukesiz(unvan)}" target="_blank" rel="noopener">${tehlukesiz(ad)}</a>`;

function tehvilSetri(basliq, icerik, xeberdarliq = false) {
  const d = document.createElement('div');
  d.className = 'tehvil-setir' + (xeberdarliq ? ' pis-fon' : '');
  d.innerHTML = `<div class="basliq">${tehlukesiz(basliq)}</div>${icerik}`;
  el('tehvil-netice').appendChild(d);
}

/* Hər düymənin cavabı fərqli görünür — göstərmə qaydası burada. */
const GORUNUS = {
  muasir: (c) => `<p>${tehlukesiz(c.olcme.model)} · ${tehlukesiz(c.olcme.saniye)} san ·
      ${tehlukesiz(c.olcu_kb)} KB</p>
    <p>${link(c.onizleme_url, 'Brauzerdə aç')}${link(c.yukle_url, 'HTML-i yüklə')}</p>`,

  klon: (c) => `<p>${c.fayllar.length} sənəd yazıldı:
      <code>${tehlukesiz(c.qovluq)}</code></p>
    <p>Claude Code-da işə sal: <code>${tehlukesiz(c.emr)}</code></p>
    <p>${link(c.yukle_url, 'Sənədləri ZIP kimi yüklə')}</p>`,

  arsiv: (c) => `<p>${tehlukesiz(c.fayl_sayi)} fayl · ${tehlukesiz(c.olcu_kb)} KB ·
      ${tehlukesiz(c.silinen_skript)} xarici skript silindi${
        c.atlanan ? ` · ${tehlukesiz(c.atlanan)} resurs limitə görə atlandı` : ''}</p>
    <p><code>${tehlukesiz(c.qovluq)}</code></p>
    <p>${link(c.yukle_url, 'ZIP-i yüklə')}</p>`,

  pdf: (c) => `<p>${tehlukesiz(c.olcu_kb)} KB · <code>${tehlukesiz(c.fayl)}</code></p>
    <p>${link(c.yukle_url, 'PDF-i yüklə')}</p>`,
};

async function tehvil(nov, ad, dugme) {
  if (!cariAnaliz) return;
  const kohne = dugme.textContent;
  dugme.disabled = true;
  dugme.textContent = 'gedir…';

  try {
    const cavab = await fetch(`/api/analyze/${cariAnaliz}/${nov}`, { method: 'POST' });
    const c = await cavab.json();

    if (!cavab.ok) tehvilSetri(ad, `<p>${tehlukesiz(c.detail || cavab.status)}</p>`, true);
    else if (!c.ugurlu) tehvilSetri(ad, `<p>${tehlukesiz(c.sebeb)}</p>`, true);
    else tehvilSetri(ad, GORUNUS[nov](c));
  } catch (x) {
    tehvilSetri(ad, `<p>Server cavab vermədi: ${tehlukesiz(x)}</p>`, true);
  } finally {
    dugme.disabled = false;
    dugme.textContent = kohne;
    el('tehvil-netice').lastChild.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

/* ---------------- izləmə düyməsi (Gün 10) ---------------- */

const izleDugme = el('d-izle');
let izlenir = false;

/* Düymə iki vəziyyətlidir: izləməyə qoy / izləməni dayandır. */
function izleDugmeniYenile(qeyd) {
  izleDugme.textContent = izlenir ? '🔕 İzləməni dayandır' : '🔔 Bu saytı izlə';
  izleDugme.title = qeyd && qeyd.son_yoxlama
    ? 'Son yoxlama: ' + qeyd.son_yoxlama
    : '';
}

async function izlemeVeziyyeti(siteId) {
  izlenir = false;
  let qeyd = null;
  try {
    const siyahi = await (await fetch('/api/izleme')).json();
    qeyd = siyahi.find((q) => q.site_id === siteId) || null;
    izlenir = Boolean(qeyd);
  } catch { /* izləmə oxunmasa da qalan bölmələr işləyir */ }
  izleDugmeniYenile(qeyd);
}

izleDugme.addEventListener('click', async () => {
  if (!cariSayt) return;
  izleDugme.disabled = true;

  try {
    if (izlenir) {
      await fetch(`/api/izleme/${cariSayt}`, { method: 'DELETE' });
      izlenir = false;
      tehvilSetri('İzləmə', '<p>İzləmə dayandırıldı — bu sayt artıq yoxlanmayacaq.</p>');
    } else {
      const cavab = await fetch('/api/izleme', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ site_id: cariSayt }),
      });
      const q = await cavab.json();

      if (!cavab.ok) {
        tehvilSetri('İzləmə', `<p>${tehlukesiz(q.detail || cavab.status)}</p>`, true);
      } else {
        izlenir = true;
        tehvilSetri('İzləmə',
          `<p>Sayt izləməyə qoyuldu. n8n <code>${tehlukesiz(q.cron)}</code> cədvəli ilə
             saytı yenidən gəzir; səhifə dəyişsə Telegram-a xəbər gedir.</p>`);
      }
    }
  } catch (x) {
    tehvilSetri('İzləmə', `<p>Server cavab vermədi: ${tehlukesiz(x)}</p>`, true);
  } finally {
    izleDugme.disabled = false;
    izleDugmeniYenile(null);
  }
});

/* ---------------- müqayisə (Gün 13) ---------------- */

const muqayiseDugme = el('d-muqayise');

/* İkinci saytı bazadan seçirik: müqayisə üçün hər iki saytın analizi olmalıdır,
   ona görə ünvan yazdırmaq yox, analiz olunmuşları siyahıya qoyuruq. */
async function muqayiseHazirla(siteId, domain) {
  el('muqayise-netice').innerHTML = '';
  el('muqayise-unvan').value = '';
  el('muqayise-cari').textContent = domain || '';

  let saytlar = [];
  try {
    saytlar = await (await fetch('/api/sites')).json();
  } catch { /* siyahı gəlməsə ünvan yazmaqla yenə müqayisə etmək olar */ }

  const digerler = saytlar.filter((s) => s.id !== siteId);

  // Siyahı boş ola bilər (bazada tək sayt var) — o halda yalnız ünvan qalır
  el('muqayise-sayt').classList.toggle('gizli', !digerler.length);
  el('muqayise-veya').classList.toggle('gizli', !digerler.length);
  el('muqayise-sayt').innerHTML = digerler.map((s) =>
    `<option value="${tehlukesiz(s.id)}">${tehlukesiz(s.domain)}</option>`).join('');

  gorset('muqayise-secim');
  gorset('k-muqayise');
}

const muqayiseQeyd = (metn) => {
  el('muqayise-netice').innerHTML = `<span class="teq">${tehlukesiz(metn)}</span>`;
};

/* Yazılan sayt bazada yoxdursa əvvəlcə analiz edilir. Bu, əsas analizdən
   ayrı gedir: cari nəticə səhifəsi pozulmur, gedişat müqayisə kartında
   qısa sətir kimi görünür. */
function ikinciSaytiAnaliz(unvan) {
  return new Promise((hell, red) => {
    fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: unvan, max_sehife: 20 }),
    }).then(async (cavab) => {
      if (!cavab.ok) {
        const x = await cavab.json().catch(() => ({}));
        const m = (x.detail && x.detail[0] && x.detail[0].msg) || cavab.status;
        return red(new Error('Yanlış ünvan: ' + m));
      }
      const { analiz_id, site_id } = await cavab.json();
      efektMatrix(true);

      const axin = new EventSource(`/api/analyze/${analiz_id}/axin`);
      const bitir2 = () => { axin.close(); efektMatrix(false); hell(site_id); };
      const dinle2 = (ad, isleyici) =>
        axin.addEventListener(ad, (e) => isleyici(JSON.parse(e.data || '{}')));

      muqayiseQeyd(`${unvan} analiz edilir…`);
      dinle2('sehife', (d) => muqayiseQeyd(`${unvan}: səhifə ${d.yigilan}/${d.hedef}`));
      dinle2('rag', (d) => muqayiseQeyd(`${unvan}: RAG ${d.sehife}/${d.umumi}`));
      dinle2('hesabat_basladi', () => muqayiseQeyd(`${unvan}: AI hesabat yazılır…`));
      dinle2('gezis_atlandi', (d) => muqayiseQeyd(`${unvan}: ${d.sebeb}`));
      axin.addEventListener('hazir', bitir2);
      axin.addEventListener('son', bitir2);
      axin.onerror = bitir2;
    }).catch(() => red(new Error('Server cavab vermir')));
  });
}

async function muqayiseGoster(ikinci) {
  // Ünvan `https://…/?a=b` şəklində ola bilər — kodlanmasa sorğu parçalanır
  const cavab = await fetch(
    `/api/muqayise?sayt1=${cariSayt}&sayt2=${encodeURIComponent(ikinci)}`
  );
  const m = await cavab.json();
  if (cavab.ok) {
    el('muqayise-netice').innerHTML = muqayiseCedveli(m);
    return true;
  }
  return false;   // 404 — sayt bazada yoxdur
}

muqayiseDugme.addEventListener('click', async () => {
  const unvan = el('muqayise-unvan').value.trim();
  const secilmis = el('muqayise-sayt').value;
  if (!cariSayt || (!unvan && !secilmis)) return;

  const kohne = muqayiseDugme.textContent;
  muqayiseDugme.disabled = true;
  muqayiseDugme.textContent = 'gedir…';

  try {
    // Yazılan ünvan siyahıdakı seçimi üstələyir
    if (!unvan) {
      await muqayiseGoster(secilmis);
    } else if (!(await muqayiseGoster(unvan))) {
      // Bazada yoxdur — analiz et, sonra yenidən müqayisə
      const yeniId = await ikinciSaytiAnaliz(unvan);
      if (!(await muqayiseGoster(yeniId))) {
        muqayiseQeyd('Analiz bitdi, amma müqayisə alınmadı — sayt açılmadı.');
      }
    }
  } catch (x) {
    efektMatrix(false);
    muqayiseQeyd(String(x.message || x));
  } finally {
    muqayiseDugme.disabled = false;
    muqayiseDugme.textContent = kohne;
  }
});

[['d-muasir', 'muasir', 'Müasir versiya'],
 ['d-klon', 'klon', 'Klon sənədləri'],
 ['d-arsiv', 'arsiv', 'Səhifə arşivi'],
 ['d-pdf', 'pdf', 'PDF hesabat']].forEach(([dugmeId, nov, ad]) => {
  const d = el(dugmeId);
  d.addEventListener('click', () => tehvil(nov, ad, d));
});

gonderDugme.addEventListener('click', sualGonder);
sualGirish.addEventListener('keydown', (e) => { if (e.key === 'Enter') sualGonder(); });
girish.addEventListener('keydown', (e) => { if (e.key === 'Enter') dugme.click(); });
