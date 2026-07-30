/* Canlı arxa fon və 3D effektlər.

   Kitabxana işlədilmir — layihədə xarici fayl yüklənmir (bax `style.css`).
   Bir `<canvas>` iki rejimdə işləyir:
     sakit  — qara fonda üzən işıq ləkələri + dərinlikli nöqtə şəbəkəsi
     matrix — analiz gedərkən düşən simvol yağışı

   Qoruyucular: `prefers-reduced-motion` seçilibsə heç nə hərəkət etmir,
   tab arxa plana keçəndə kadrlar dayanır, piksel sıxlığı 2 ilə məhdudlaşır
   (zəif maşında proyektorda ilişməsin). */

(function () {
  const lovhe = document.getElementById('fon');
  if (!lovhe) return;

  const kontekst = lovhe.getContext('2d', { alpha: false });
  const sakitIstek = window.matchMedia('(prefers-reduced-motion: reduce)');

  let en = 0;
  let hund = 0;
  let matrixRejimi = false;
  let matrixGuc = 0;      // 0 → 1 arası yumşaq keçid
  let kadr = null;
  let sonVaxt = 0;

  /* Simvollar: rəqəmlər, kod işarələri və Azərbaycan hərfləri —
     sayt analiz alətidir, mənasız katakana yerinə öz əlifbamız. */
  const SIMVOLLAR = '01<>{}[]()/\\#$%&*+=:;ABCÇDƏEFGĞHXIİJKQLMNOÖPRSŞTUÜVYZ';
  const SUTUN_ENI = 16;

  let sutunlar = [];      // matrix: hər sütunun cari y mövqeyi
  let lekeler = [];       // sakit rejim: üzən işıq ləkələri

  function reng(ad, ehtiyat) {
    const d = getComputedStyle(document.documentElement).getPropertyValue(ad).trim();
    return d || ehtiyat;
  }

  function olcuVer() {
    const sixliq = Math.min(window.devicePixelRatio || 1, 2);
    en = window.innerWidth;
    hund = window.innerHeight;
    lovhe.width = Math.floor(en * sixliq);
    lovhe.height = Math.floor(hund * sixliq);
    lovhe.style.width = en + 'px';
    lovhe.style.height = hund + 'px';
    kontekst.setTransform(sixliq, 0, 0, sixliq, 0, 0);

    sutunlar = new Array(Math.ceil(en / SUTUN_ENI)).fill(0).map(function () {
      return Math.random() * -hund;
    });
  }

  function lekeleriQur() {
    lekeler = [
      { x: 0.2, y: 0.3, r: 420, sur: 0.00013, faz: 0, reng: '--vurgu' },
      { x: 0.8, y: 0.25, r: 360, sur: 0.00009, faz: 2, reng: '--yasil' },
      { x: 0.5, y: 0.8, r: 460, sur: 0.00011, faz: 4, reng: '--vurgu' },
    ];
  }

  /* ---------------- sakit rejim ---------------- */

  function sakitCiz(vaxt) {
    kontekst.fillStyle = '#05060a';
    kontekst.fillRect(0, 0, en, hund);

    lekeler.forEach(function (l) {
      const x = (l.x + Math.sin(vaxt * l.sur + l.faz) * 0.09) * en;
      const y = (l.y + Math.cos(vaxt * l.sur * 1.3 + l.faz) * 0.07) * hund;
      const boya = reng(l.reng, '#4f8cff');
      const qradiyent = kontekst.createRadialGradient(x, y, 0, x, y, l.r);
      qradiyent.addColorStop(0, boya + '26');
      qradiyent.addColorStop(1, boya + '00');
      kontekst.fillStyle = qradiyent;
      kontekst.fillRect(x - l.r, y - l.r, l.r * 2, l.r * 2);
    });

    /* Perspektivli nöqtə şəbəkəsi — aşağı getdikcə sıxlaşır, dərinlik verir */
    kontekst.fillStyle = 'rgba(255,255,255,0.05)';
    for (let sira = 0; sira < 26; sira++) {
      const t = sira / 26;
      const y = hund * (0.45 + t * t * 0.75) + Math.sin(vaxt * 0.0002 + sira) * 3;
      const aralik = 26 + t * 52;
      for (let x = (vaxt * 0.004) % aralik; x < en; x += aralik) {
        kontekst.fillRect(x, y, 1.6, 1.6);
      }
    }
  }

  /* ---------------- matrix rejimi ---------------- */

  function matrixCiz() {
    // Şəffaf qara örtük: köhnə simvollar tədricən sönür, iz qalır
    kontekst.fillStyle = 'rgba(5, 6, 10, ' + (0.10 + (1 - matrixGuc) * 0.2) + ')';
    kontekst.fillRect(0, 0, en, hund);

    const yasil = reng('--yasil', '#3ddc97');
    kontekst.font = '600 14px ui-monospace, Consolas, monospace';

    for (let i = 0; i < sutunlar.length; i++) {
      const simvol = SIMVOLLAR[Math.floor(Math.random() * SIMVOLLAR.length)];
      const x = i * SUTUN_ENI;
      const y = sutunlar[i];

      kontekst.fillStyle = '#dfffe9';          // baş simvol daha parlaq
      kontekst.globalAlpha = matrixGuc;
      kontekst.fillText(simvol, x, y);
      kontekst.fillStyle = yasil;
      kontekst.globalAlpha = matrixGuc * 0.55;
      kontekst.fillText(simvol, x, y - 16);
      kontekst.globalAlpha = 1;

      sutunlar[i] = y > hund + Math.random() * 400 ? 0 : y + 16;
    }
  }

  /* ---------------- kadr dövrü ---------------- */

  function kadrCiz(vaxt) {
    kadr = requestAnimationFrame(kadrCiz);
    if (vaxt - sonVaxt < 33) return;          // ~30 kadr/san bəsdir
    sonVaxt = vaxt;

    const hedef = matrixRejimi ? 1 : 0;
    matrixGuc += (hedef - matrixGuc) * 0.06;  // yumşaq keçid

    if (matrixGuc > 0.02) matrixCiz();
    else sakitCiz(vaxt);
  }

  function basla() {
    if (kadr || sakitIstek.matches) return;
    kadr = requestAnimationFrame(kadrCiz);
  }

  function dayan() {
    if (kadr) cancelAnimationFrame(kadr);
    kadr = null;
  }

  /* ---------------- kartların 3D əyilməsi ---------------- */

  /* Maus kartın üstündə gəzəndə kart ona tərəf çevrilir. Bucaq qəsdən
     kiçikdir (6°) — mətn oxunaqlı qalmalıdır. Toxunma ekranlarda işləmir. */
  function kartEyilmesi() {
    if (sakitIstek.matches || !window.matchMedia('(hover: hover)').matches) return;

    document.addEventListener('pointermove', function (h) {
      const kart = h.target.closest ? h.target.closest('.kart') : null;
      if (!kart) return;
      const q = kart.getBoundingClientRect();
      const nx = (h.clientX - q.left) / q.width - 0.5;
      const ny = (h.clientY - q.top) / q.height - 0.5;
      kart.style.setProperty('--rx', (-ny * 6).toFixed(2) + 'deg');
      kart.style.setProperty('--ry', (nx * 6).toFixed(2) + 'deg');
      kart.style.setProperty('--isiq-x', ((nx + 0.5) * 100).toFixed(1) + '%');
      kart.style.setProperty('--isiq-y', ((ny + 0.5) * 100).toFixed(1) + '%');
    });

    document.addEventListener('pointerleave', function (h) {
      const kart = h.target.closest ? h.target.closest('.kart') : null;
      if (kart) {
        kart.style.removeProperty('--rx');
        kart.style.removeProperty('--ry');
      }
    }, true);
  }

  /* ---------------- xaricə verilən ---------------- */

  window.efektMatrix = function (aktiv) {
    matrixRejimi = Boolean(aktiv);
  };

  window.addEventListener('resize', olcuVer);
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) dayan();
    else basla();
  });

  olcuVer();
  lekeleriQur();
  kartEyilmesi();

  if (sakitIstek.matches) sakitCiz(0);        // hərəkətsiz, amma boş qalmasın
  else basla();
})();
