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
import re
import shutil
import subprocess
import sys
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


# nuclei -stats sətrindən irəliləyişi çıxarmaq üçün: "Requests: 4500/58000 (7%)"
_FAIZ_NAXIS = re.compile(r"(\d+)\s*%")
_ISTEK_NAXIS = re.compile(r"[Rr]equests?[:\s]+(\d+)\s*/\s*(\d+)")

# Səviyyə → interfeys rəngi
_SINIF = {"kritik": "pis", "yuksek": "pis", "orta": "pis", "asagi": "ok", "melumat": "ok"}
_NISAN = {"kritik": "🔴", "yuksek": "🟠", "orta": "🟡", "asagi": "🔵", "melumat": "⚪"}


def skan_et(job_id: int, url: str) -> None:
    """nuclei-ni işə salır; hər tapıntını və irəliləyişi CANLI göndərir."""
    tapintilar: list[dict] = []
    emr = [
        _nuclei_yol(), "-u", url, "-jsonl",
        "-stats", "-stats-interval", "3",       # irəliləyiş stderr-ə yazılır
        "-severity", "critical,high,medium,low,info",
        "-rate-limit", "50", "-timeout", "10", "-retries", "1",
        "-no-interactsh",
    ]
    _log("nuclei:", " ".join(emr))
    _post(f"/api/aktiv-skan/{job_id}/gedisat",
          {"mesaj": "nuclei başladı — şablonlar yüklənir", "faiz": 3})

    basla = time.time()
    # stderr → stdout birləşdirilir: JSON sətir = tapıntı, qalan = stats/log
    proses = subprocess.Popen(emr, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace")
    son_dayan_yoxlama = 0.0

    def dayanibmi() -> bool:
        cavab = _post(f"/api/aktiv-skan/{job_id}/gedisat",
                      {"mesaj": f"skan gedir — {len(tapintilar)} tapıntı"})
        return bool(cavab.get("dayandirildi"))

    try:
        for setir in proses.stdout:
            setir = setir.strip()
            if not setir:
                continue

            if setir.startswith("{"):
                # Tapıntı — dərhal canlı göndər
                t = nuclei_parse.bir_tapinti(_yukle(setir))
                if t:
                    tapintilar.append(t)
                    sev = t["seviyye"]
                    _post(f"/api/aktiv-skan/{job_id}/gedisat", {
                        "mesaj": f"{_NISAN.get(sev, '•')} {t['ad']}",
                        "sinif": _SINIF.get(sev, ""),
                    })
            else:
                # nuclei stats sətri — faizi çıxar
                m = _ISTEK_NAXIS.search(setir)
                f = _FAIZ_NAXIS.search(setir)
                if m or f:
                    faiz = int(f.group(1)) if f else None
                    if m and not faiz:
                        edilmis, umumi = int(m.group(1)), max(1, int(m.group(2)))
                        faiz = min(99, int(edilmis * 100 / umumi))
                    _post(f"/api/aktiv-skan/{job_id}/gedisat", {
                        "mesaj": f"şablonlar yoxlanılır… {len(tapintilar)} tapıntı",
                        "faiz": faiz,
                    })

            indi = time.time()
            if indi - son_dayan_yoxlama > 3:      # dayandırma yoxlaması
                son_dayan_yoxlama = indi
                if dayanibmi():
                    _log("dayandırıldı — nuclei kəsilir")
                    proses.kill()
                    return
            if indi - basla > MAX_MUDDET:
                _log("vaxt limiti — nuclei kəsilir")
                proses.kill()
                break
        proses.wait(timeout=10)
    finally:
        if proses.poll() is None:
            proses.kill()

    _log(f"bitdi — {len(tapintilar)} tapıntı")
    _post(f"/api/aktiv-skan/{job_id}/gedisat",
          {"mesaj": f"skan bitdi — {len(tapintilar)} tapıntı işlənir", "faiz": 100})
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
