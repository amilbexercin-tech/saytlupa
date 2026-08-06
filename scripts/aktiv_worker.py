"""Aktiv skan işçisi (worker) — öz kompüterində işləyir.

Nə edir: SaytLupa API-dən aktiv skan işi götürür, hədəf domenin təsdiqli
olduğunu təkrar yoxlayır, **nuclei** ilə skan edir, gedişat və nəticəni API-yə
göndərir. Brauzer nəticəni canlı görür.

İşə salmaq (repo kökündən):

    py scripts/aktiv_worker.py

Tələblər:
  * nuclei ikili faylı PATH-də olmalıdır  (https://github.com/projectdiscovery/nuclei)
    şablonları yenilə:  nuclei -update-templates
  * mühit dəyişənləri (ya .env-dən götürülür):
      SAYTLUPA_API   — API ünvanı (default http://localhost:8000)
      API_ACAR       — yazma açarı (əks halda backend .env-dən oxunur)

Təhlükəsizlik: worker yalnız API-nin verdiyi işi götürür və domen təsdiqini
`sahiblik` modulu ilə **yenidən** yoxlayır — təsdiqsiz domen skan olunmur.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

# Repo kökünü yola əlavə et ki, `backend` paketini import edə bilək.
KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from backend import nuclei_parse  # noqa: E402

API = os.getenv("SAYTLUPA_API", "http://localhost:8000").rstrip("/")
ACAR = os.getenv("API_ACAR", "")
BASLIQ = {"X-API-Acar": ACAR} if ACAR else {}

BOŞ_GOZLEME = 5          # növbə boşdursa bu qədər saniyə gözlə
MAX_MUDDET = 900         # bir skan ən çoxu bu qədər saniyə (15 dəq)
TIK = 2.0                # nuclei sussa BELƏ bu qədər saniyədən bir xəbər ver
JURNAL_HEDDI = 150       # nuclei jurnalından ən çoxu bu qədər sətir ötürülür


def _nuclei_yol() -> str | None:
    """nuclei-nin yerini tapır: əvvəl repo `tools/`, sonra PATH."""
    yerli = KOK / "tools" / ("nuclei.exe" if os.name == "nt" else "nuclei")
    if yerli.exists():
        return str(yerli)
    return shutil.which("nuclei")


def _log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def _post(yol: str, govde: dict) -> dict:
    try:
        c = httpx.post(f"{API}{yol}", json=govde, headers=BASLIQ, timeout=30)
        return c.json() if c.headers.get("content-type", "").startswith("application/json") else {}
    except Exception as x:
        _log("API xətası:", yol, x)
        return {}


def _nuclei_var() -> bool:
    return _nuclei_yol() is not None


def _domen_tesdiqli(domain: str) -> bool:
    """Sahibliyi API-dən soruşur (doğru mənbə — Railway-dəki allowlist + baza).

    Müdafiə dərinliyi: iş API-də onsuz da təsdiqlənib, worker yenidən yoxlayır.
    """
    try:
        c = httpx.get(f"{API}/api/sahiblik", headers=BASLIQ, timeout=15)
        siyahi = c.json() if c.status_code == 200 else []
        return any(d.get("domain") == domain for d in siyahi)
    except Exception:
        return False


# Səviyyə → interfeys rəngi
_SINIF = {"kritik": "pis", "yuksek": "pis", "orta": "pis", "asagi": "ok", "melumat": "ok"}
_NISAN = {"kritik": "🔴", "yuksek": "🟠", "orta": "🟡", "asagi": "🔵", "melumat": "⚪"}

# nuclei jurnal sətri: "[INF] Templates loaded for current scan: 8412".
# Yalnız bunlar ötürülür — ASCII banner və versiya sətirləri süzülüb atılır.
_JURNAL_NAXIS = re.compile(r"^\[(INF|WRN|ERR|FTL|DBG|VER)\]\s*(.+)$")
_ANSI_NAXIS = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _prosess_ac(emr: list[str]) -> subprocess.Popen:
    """nuclei-ni işə salır. Borular AYRIdır: stdout = tapıntı, stderr = gedişat.

    Testlər bu funksiyanı əvəzləyir (real nuclei olmadan skan axınını yoxlamaq).
    """
    return subprocess.Popen(emr, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")


def _boru_oxu(boru, etiket: str, novbe: queue.Queue) -> None:
    """Borunu AYRICA sapda oxuyur və növbəyə ötürür.

    Bu, düyün nöqtəsidir: nuclei şablonları yükləyərkən dəqiqələrlə heç nə
    yazmır. Oxuma əsas dövrədə olsaydı, dövrə həmin müddət bloklanar,
    gedişat göndərilməz, «dayandır» düyməsi və vaxt limiti işləməzdi.
    """
    try:
        for setir in boru:
            novbe.put((etiket, setir.rstrip("\n")))
    except Exception:                       # boru qırıldı — skan onsuz da bitir
        pass
    finally:
        novbe.put((etiket, None))           # bu axın bağlandı


def _faiz_cixar(qeyd: dict) -> int | None:
    """`-stats-json` qeydindən faizi götürür (dəyərlər mətn kimi gəlir)."""
    xam = str(qeyd.get("percent", "")).strip()
    if not xam:
        return None
    try:
        return max(1, min(99, int(float(xam))))
    except ValueError:
        return None


def skan_et(job_id: int, url: str) -> None:
    """nuclei-ni işə salır; tapıntıları, nuclei jurnalını və faizi CANLI göndərir.

    Axın: iki oxuyucu sap borulardan sətirləri növbəyə tökür, əsas dövrə isə
    onları emal edir **və** `TIK` saniyədən bir — nuclei sussa belə — vəziyyət
    göndərir, dayandırmanı və vaxt limitini yoxlayır. Beləliklə ekran heç vaxt
    donmur.
    """
    tapintilar: list[dict] = []
    emr = [
        _nuclei_yol(), "-u", url, "-jsonl",
        "-stats-json", "-stats-interval", "2",  # maşınoxunan gedişat → stderr
        "-duc",                                 # yeniləmə yoxlaması ~1 dəq yeyirdi
        "-nc",                                  # rəng kodları olmasın
        "-severity", "critical,high,medium,low,info",
        "-rate-limit", "50", "-timeout", "10", "-retries", "1",
        "-no-interactsh",
    ]
    _log("nuclei:", " ".join(emr))

    def xeber(mesaj: str, faiz: int | None = None, sinif: str = "",
              gorunus: str = "setir") -> dict:
        return _post(f"/api/aktiv-skan/{job_id}/gedisat",
                     {"mesaj": mesaj, "faiz": faiz, "sinif": sinif,
                      "gorunus": gorunus})

    xeber("nuclei başladı — şablonlar yüklənir", 3)

    basla = time.time()
    proses = _prosess_ac(emr)
    novbe: queue.Queue = queue.Queue()
    for boru, etiket in ((proses.stdout, "tapinti"), (proses.stderr, "jurnal")):
        threading.Thread(target=_boru_oxu, args=(boru, etiket, novbe),
                         daemon=True).start()

    merhele = "şablonlar yüklənir"
    faiz: int | None = 3
    jurnal_sayi = 0
    son_jurnal = ""
    bitmis = 0            # bağlanan boru sayı — 2 olanda nuclei bitib
    son_tik = 0.0
    dayandirildi = False

    try:
        while True:
            try:
                etiket, setir = novbe.get(timeout=0.3)
            except queue.Empty:
                pass
            else:
                if setir is None:
                    bitmis += 1
                elif etiket == "tapinti":
                    # stdout = tapıntı JSONL-i — tapılan anda göndər
                    t = nuclei_parse.bir_tapinti(_yukle(setir))
                    if t:
                        tapintilar.append(t)
                        sev = t["seviyye"]
                        xeber(f"{_NISAN.get(sev, '•')} {t['ad']}", faiz,
                              _SINIF.get(sev, ""))
                elif setir.startswith("{"):
                    # stderr + JSON = `-stats-json` gedişat qeydi
                    qeyd = _yukle(setir)
                    yeni = _faiz_cixar(qeyd)
                    if yeni is not None:
                        # Zolaq geri getməsin: başlanğıc 3%-dir, nuclei-nin ilk
                        # ölçüsü isə 1% ola bilər.
                        faiz = max(faiz or 0, yeni)
                    merhele = (f"yoxlanılır · {qeyd.get('requests', '?')}/"
                               f"{qeyd.get('total', '?')} sorğu · "
                               f"{qeyd.get('rps', '?')} rps")
                else:
                    # stderr + mətn = nuclei jurnalı (banner süzülür)
                    uygun = _JURNAL_NAXIS.match(_ANSI_NAXIS.sub("", setir).strip())
                    metn = uygun.group(2).strip() if uygun else ""
                    if metn and metn != son_jurnal and jurnal_sayi < JURNAL_HEDDI:
                        son_jurnal = metn
                        jurnal_sayi += 1
                        pis = uygun.group(1) in ("ERR", "FTL")
                        xeber(f"· {metn[:160]}", faiz, "pis" if pis else "")
                        if "Templates loaded" in metn:
                            merhele = "şablonlar hazırdır — yoxlama başlayır"

            indi = time.time()
            if indi - son_tik >= TIK:
                # nuclei sussa da vəziyyət göndərilir: mərhələ + keçən vaxt +
                # faiz + tapıntı sayı. Eyni zamanda dayandırma/limit yoxlanır.
                son_tik = indi
                kecen = int(indi - basla)
                cavab = xeber(
                    f"{merhele} · {kecen // 60}:{kecen % 60:02d} · "
                    f"{len(tapintilar)} tapıntı", faiz, gorunus="veziyyet")
                if cavab.get("dayandirildi"):
                    _log("dayandırıldı — nuclei kəsilir")
                    dayandirildi = True
                    break
                if indi - basla > MAX_MUDDET:
                    _log("vaxt limiti — nuclei kəsilir")
                    xeber("vaxt limiti doldu — toplanan tapıntılar yazılır", faiz,
                          "pis")
                    break

            if bitmis >= 2 and novbe.empty():
                break
    finally:
        if proses.poll() is None:
            proses.kill()

    if dayandirildi:
        return

    _log(f"bitdi — {len(tapintilar)} tapıntı")
    xeber(f"skan bitdi — {len(tapintilar)} tapıntı işlənir", 100)
    _post(f"/api/aktiv-skan/{job_id}/netice", {"tapintilar": tapintilar})


def _yukle(setir: str) -> dict:
    try:
        return json.loads(setir)
    except json.JSONDecodeError:
        return {}


def bir_dovre() -> bool:
    """Bir iş götürüb işlədir. İş yoxdursa False qaytarır."""
    try:
        c = httpx.get(f"{API}/api/aktiv-skan/novbe", headers=BASLIQ, timeout=20)
        is_ = c.json() if c.status_code == 200 else {}
    except Exception as x:
        _log("növbə oxunmadı:", x)
        return False

    if not is_ or "job_id" not in is_:
        return False

    job_id, url, domain = is_["job_id"], is_["target_url"], is_["domain"]
    _log(f"iş #{job_id}: {url}")

    # Müdafiə dərinliyi: domen təsdiqini worker də API-dən yoxlayır
    if not _domen_tesdiqli(domain):
        _log("TƏSDİQSİZ domen — skan edilmir")
        _post(f"/api/aktiv-skan/{job_id}/xeta",
              {"mesaj": f"«{domain}» worker-də təsdiqlənmədi — skan dayandırıldı."})
        return True

    if not _nuclei_var():
        _post(f"/api/aktiv-skan/{job_id}/xeta", {
            "mesaj": "nuclei tapılmadı. Quraşdır: github.com/projectdiscovery/nuclei "
                     "və PATH-ə əlavə et."})
        _log("XƏTA: nuclei PATH-də yoxdur")
        return True

    try:
        skan_et(job_id, url)
    except Exception as x:
        _log("skan xətası:", x)
        _post(f"/api/aktiv-skan/{job_id}/xeta", {"mesaj": f"Worker xətası: {x}"})
    return True


def main() -> None:
    _log(f"worker başladı → API: {API} | açar: {'var' if ACAR else 'YOX'} | "
         f"nuclei: {'var' if _nuclei_var() else 'YOX'}")
    while True:
        try:
            if not bir_dovre():
                time.sleep(BOŞ_GOZLEME)
        except KeyboardInterrupt:
            _log("dayandırıldı (Ctrl+C)")
            break
        except Exception as x:
            _log("dövrə xətası:", x)
            time.sleep(BOŞ_GOZLEME)


if __name__ == "__main__":
    main()
