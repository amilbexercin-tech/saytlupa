/* Aktiv (dərin) skan interfeysi.
   Sahiblik təsdiqi → razılıq → nuclei skanı (SSE canlı) → nəticə.
   Qlobal köməkçilər app.js/render.js-dən gəlir: el, tehlukesiz, sorgu,
   gedisatSetri, efektMatrix, basla, TEHL_SEVIYYE, xetaMetni. */

let aktivUrl = '';
let aktivDomain = '';
let aktivJob = null;
let aktivAxin = null;
let aktivQopma = 0;      // ardıcıl SSE kəsilməsi sayı

/* Canlı vəziyyət zolağı: yerində yenilənir, gedişat siyahısını doldurmur.
   Worker bunu hər 2 saniyədən bir göndərir — nuclei sussa belə. */
function aktivCanli(mesaj, faiz) {
  el('canli').classList.remove('gizli');
  el('canli-metn').textContent = mesaj;
  if (faiz != null) el('canli-dolu').style.width = Math.max(1, Math.min(100, faiz)) + '%';
}

/* Təhlükəsizlik nəticəsi göstəriləndən sonra çağırılır (app.js-dən). */
window.aktivHazirla = async function (domain, url) {
  aktivUrl = url || '';
  /* Domeni URL-in tam host adından götürürük (backend allowlist-i tam host
     saxlayır). `base_domen` tldextract ilə `railway.app`-a yığır — uyğun gəlmir. */
  try {
    aktivDomain = new URL(aktivUrl).hostname.replace(/^www\./, '').toLowerCase();
  } catch {
    aktivDomain = (domain || '').toLowerCase();
  }
  el('aktiv-domen').value = aktivDomain;
  el('aktiv-telimat').innerHTML = '';
  el('aktiv-netice').innerHTML = '';
  gorset('k-aktiv');

  await aktivVeziyyetYenile();
};

/* Domen təsdiqlidirsə skan rejimini, deyilsə təsdiq rejimini göstərir. */
async function aktivVeziyyetYenile() {
  let tesdiqli = false;
  try {
    const siyahi = await (await fetch('/api/sahiblik')).json();
    tesdiqli = (siyahi || []).some((d) => d.domain === aktivDomain);
  } catch { /* siyahı gəlməsə təsdiq rejimi qalır */ }

  el('aktiv-idare').classList.toggle('gizli', !tesdiqli);
  if (tesdiqli) {
    el('aktiv-telimat').innerHTML =
      `<div class="xeb yasil">✓ «${tehlukesiz(aktivDomain)}» təsdiqlənib — dərin skan hazırdır.</div>`;
  }
}

/* ---- sahiblik ---- */

el('aktiv-token').addEventListener('click', async () => {
  const domen = el('aktiv-domen').value.trim();
  if (!domen) return;
  try {
    const c = await sorgu('/api/sahiblik/token', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain: domen }),
    });
    const d = await c.json();
    if (!c.ok) { el('aktiv-telimat').innerHTML = `<div class="xeb sari">${tehlukesiz(xetaMetni(d, c))}</div>`; return; }
    if (d.status === 'tesdiqli') { await aktivVeziyyetYenile(); return; }
    el('aktiv-telimat').innerHTML = `
      <div class="xeb sari">
        <p><b>Domeni təsdiqlə</b> — bu üsullardan birini seç:</p>
        <p>① DNS TXT qeyd əlavə et:<br><code>${tehlukesiz(d.dns_qeyd)}</code></p>
        <p>② və ya bu faylı yerləşdir:<br>
           <code>https://${tehlukesiz(d.domain)}${tehlukesiz(d.fayl_yolu)}</code><br>
           içində: <code>${tehlukesiz(d.token)}</code></p>
        <p>Sonra <b>Yoxla</b> düyməsinə bas.</p>
      </div>`;
  } catch (x) {
    el('aktiv-telimat').innerHTML = `<div class="xeb sari">Server cavab vermədi: ${tehlukesiz(x)}</div>`;
  }
});

el('aktiv-yoxla').addEventListener('click', async () => {
  const domen = el('aktiv-domen').value.trim();
  if (!domen) return;
  const d0 = el('aktiv-yoxla');
  d0.disabled = true; const kohne = d0.textContent; d0.textContent = 'yoxlanılır…';
  try {
    const c = await sorgu('/api/sahiblik/yoxla', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain: domen }),
    });
    const d = await c.json();
    if (d.status === 'tesdiqli') {
      aktivDomain = d.domain;
      await aktivVeziyyetYenile();
    } else {
      el('aktiv-telimat').innerHTML =
        `<div class="xeb sari">${tehlukesiz(d.qeyd || 'Hələ təsdiqlənmədi.')}</div>` +
        el('aktiv-telimat').innerHTML;
    }
  } catch (x) {
    el('aktiv-telimat').innerHTML = `<div class="xeb sari">Server cavab vermədi: ${tehlukesiz(x)}</div>`;
  } finally {
    d0.disabled = false; d0.textContent = kohne;
  }
});

/* ---- skan ---- */

el('aktiv-basla').addEventListener('click', async () => {
  if (!el('aktiv-razi').checked) {
    el('aktiv-telimat').innerHTML =
      `<div class="xeb sari">Əvvəlcə «bu sayt mənimdir» qutusunu işarələ.</div>`;
    return;
  }
  const url = aktivUrl || ('https://' + el('aktiv-domen').value.trim());

  el('aktiv-basla').disabled = true;
  el('aktiv-netice').innerHTML = '';
  el('setirler').innerHTML = '';
  el('gedisat').classList.remove('gizli');
  basla = Date.now();
  aktivQopma = 0;
  efektMatrix(true);
  gedisatSetri('aktiv skan', 'başladı — worker gözlənilir…');
  aktivCanli('worker gözlənilir…', 1);

  let cavab;
  try {
    cavab = await sorgu('/api/aktiv-skan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, razilioq: true }),
    });
  } catch {
    return aktivBitir('Server cavab vermədi');
  }
  const d = await cavab.json();
  if (!cavab.ok) return aktivBitir(xetaMetni(d, cavab));

  aktivJob = d.job_id;
  el('aktiv-dayandir').classList.remove('gizli');
  aktivAxin = new EventSource(`/api/aktiv-skan/${aktivJob}/axin`);

  aktivAxin.addEventListener('gedisat', (e) => {
    aktivQopma = 0;                       // hadisə gəldi → əlaqə sağlamdır
    const q = JSON.parse(e.data || '{}');
    if (q.gorunus === 'veziyyet') {
      /* Taymer yeniləməsi — hər 2 saniyədən bir gəlir, siyahını doldurmasın. */
      aktivCanli(q.mesaj || '', q.faiz);
      return;
    }
    const etiket = q.faiz != null ? `nuclei ${q.faiz}%` : 'nuclei';
    gedisatSetri(etiket, q.mesaj || '', q.sinif || '');
  });
  aktivAxin.addEventListener('hazir', async (e) => {
    const q = JSON.parse(e.data || '{}');
    gedisatSetri('HAZIR', `bal ${q.bal}/100 · ${q.herf}`, 'ok');
    try {
      const oxu = await (await sorgu(`/api/aktiv-skan/${aktivJob}`)).json();
      aktivNeticeCiz(oxu);
    } catch { /* nəticə oxunmasa gedişat qalır */ }
  });
  aktivAxin.addEventListener('xeta', (e) => {
    const q = JSON.parse(e.data || '{}');
    gedisatSetri('xəta', q.mesaj || 'skan dayandı', 'pis');
    el('aktiv-netice').innerHTML =
      `<div class="xeb sari">${tehlukesiz(q.mesaj || 'Skan tamamlanmadı.')}</div>`;
  });
  aktivAxin.addEventListener('son', () => aktivBitir());
  aktivAxin.onerror = () => {
    /* Bir kəsilmə skanı bitirməməlidir: nuclei arxa planda işləməkdə davam
       edir və EventSource özü yenidən qoşulur. Əvvəllər burada dərhal
       `close()` çağırılırdı — bir şəbəkə çınqılı canlı görüntünü əbədi
       öldürürdü. İndi yalnız təkrar-təkrar uğursuzluqdan sonra əl çəkirik. */
    if (++aktivQopma >= 6) {
      return aktivBitir('canlı əlaqə kəsildi — skan arxada davam edir, '
                        + 'səhifəni yeniləyib nəticəyə bax');
    }
    aktivCanli(`əlaqə kəsildi, yenidən qoşulur… (${aktivQopma}/6)`, null);
  };
});

el('aktiv-dayandir').addEventListener('click', async () => {
  if (!aktivJob) return;
  try { await sorgu(`/api/aktiv-skan/${aktivJob}/dayandir`, { method: 'POST' }); } catch {}
  gedisatSetri('aktiv skan', 'dayandırılır…', 'pis');
});

function aktivBitir(xeta) {
  if (aktivAxin) { aktivAxin.close(); aktivAxin = null; }
  el('aktiv-basla').disabled = false;
  el('aktiv-dayandir').classList.add('gizli');
  el('canli').classList.add('gizli');
  efektMatrix(false);
  if (xeta) gedisatSetri('xəta', xeta, 'pis');
}

/* ---- nəticə ---- */

function aktivNeticeCiz(o) {
  const t = o.tapintilar || [];
  const balSinif = o.bal >= 75 ? 'yaxsi' : o.bal >= 40 ? 'orta' : 'pis';

  const tapintiHtml = t.length
    ? t.map((f) => {
        const [sinif, etiket] = TEHL_SEVIYYE[f.seviyye] || ['', f.seviyye];
        const istinad = (f.istinad || []).length
          ? `<div class="tehl-hell"><b>İstinad:</b> ${f.istinad.map((r) =>
              /^https?:/.test(r)
                ? `<a href="${tehlukesiz(r)}" target="_blank" rel="noopener">${tehlukesiz(r)}</a>`
                : tehlukesiz(r)).join(' · ')}</div>`
          : '';
        return `<div class="tehl-tapinti ${sinif}">
          <div class="tehl-bas">
            <span class="teq ${sinif}">${tehlukesiz(etiket)}</span>
            <span class="teq mavi">🔬 aktiv</span>
            <strong>${tehlukesiz(f.ad)}</strong>
          </div>
          <div class="tehl-risk"><b>Risk:</b> ${tehlukesiz(f.risk)}</div>
          ${f.subut ? `<div class="tehl-hell"><b>Sübut:</b> <code>${tehlukesiz(f.subut)}</code></div>` : ''}
          <div class="tehl-hell"><b>Həll:</b> ${tehlukesiz(f.hell)}</div>
          ${istinad}
        </div>`;
      }).join('')
    : `<div class="xeb yasil">✓ nuclei açıq tapmadı — bu şablonlarla zəiflik görünmür.</div>`;

  el('aktiv-netice').innerHTML =
    `<div class="tehl-bal">
       <div class="tehl-herf ${balSinif}">${tehlukesiz(o.herf || '')}</div>
       <div><div class="tehl-rəqəm">${tehlukesiz(o.bal)}<span class="alt">/100</span></div>
         <div class="teqler"><span class="teq">${t.length} aktiv tapıntı</span></div></div>
     </div>${tapintiHtml}`;
}
