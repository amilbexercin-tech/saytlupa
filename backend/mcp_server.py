"""SaytLupa MCP serveri (Gün 11) — stdio.

Claude Code / Cursor bu server vasitəsilə SaytLupa-nın üç imkanına çatır:
analiz başlatmaq, saytla danışmaq (RAG), iki saytı müqayisə etmək.

Server **özü iş görmür** — işləyən FastAPI-yə HTTP sorğusu göndərir. Səbəb: ağır
iş (crawler, embedding, LLM) Claude Code-un işə saldığı kiçik prosesdə yox,
serverdə getməlidir. Ona görə istifadədən əvvəl `uvicorn backend.main:app`
işləməlidir.

Qeydiyyat (Claude Code):

    claude mcp add saytlupa -- D:\\SaytLupa\\.venv\\Scripts\\python.exe -m backend.mcp_server

və ya birbaşa fayl kimi:

    claude mcp add saytlupa -- D:\\SaytLupa\\.venv\\Scripts\\python.exe D:\\SaytLupa\\backend\\mcp_server.py
"""

from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

try:  # paket kimi: python -m backend.mcp_server
    from .config import ayarlar
except ImportError:  # birbaşa fayl kimi işə salınanda
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from backend.config import ayarlar

API = ayarlar.api_url.rstrip("/")

# Analiz və RAG cavabı uzun çəkə bilər; siyahı sorğusu isə qısa.
UZUN_GOZLEME = 180.0
QISA_GOZLEME = 20.0

mcp = FastMCP("saytlupa")


# --------------------------------------------------------------- köməkçilər


async def _sorgu(metod: str, yol: str, gozleme: float = QISA_GOZLEME, **kwargs):
    """(uğurlu, məlumat və ya xəta mətni) qaytarır — heç vaxt istisna atmır."""
    try:
        async with httpx.AsyncClient(timeout=gozleme) as musteri:
            cavab = await musteri.request(metod, f"{API}{yol}", **kwargs)
    except httpx.ConnectError:
        return False, (
            f"SaytLupa serveri cavab vermir ({API}). "
            "Əvvəlcə işə sal: uvicorn backend.main:app"
        )
    except httpx.TimeoutException:
        return False, f"Sorğu {gozleme:.0f} saniyəyə cavab vermədi: {yol}"

    if cavab.status_code >= 400:
        try:
            sebeb = cavab.json().get("detail", cavab.text)
        except Exception:
            sebeb = cavab.text
        return False, f"Server xətası ({cavab.status_code}): {sebeb}"

    return True, cavab.json()


async def _sayt_tap(gosterici: str):
    """Domen/ünvan/nömrə → sayt qeydi. Tapılmasa mövcud saytları sadalayır."""
    ugurlu, saytlar = await _sorgu("GET", "/api/sites")
    if not ugurlu:
        return None, saytlar

    ad = (gosterici or "").strip().lower()
    for on in ("https://", "http://", "www."):
        ad = ad.removeprefix(on)
    ad = ad.rstrip("/")

    for s in saytlar:
        if ad.isdigit() and s["id"] == int(ad):
            return s, ""
        if s["domain"].lower() == ad or ad in s["url"].lower() or ad in s["domain"]:
            return s, ""

    movcud = ", ".join(f"{s['domain']} (id {s['id']})" for s in saytlar) or "heç nə"
    return None, (
        f"'{gosterici}' bazada tapılmadı — əvvəlcə onu analiz etmək lazımdır.\n"
        f"Mövcud saytlar: {movcud}"
    )


# --------------------------------------------------------------- alətlər


@mcp.tool()
async def sayt_analiz_et(url: str, max_sehife: int = 10) -> str:
    """Saytın tam analizini başladır (toplayıcılar + gəziş + RAG indeksi + AI hesabat).

    Analiz fonda gedir və dərhal `analiz_id` qaytarılır; nəticəni bir neçə
    dəqiqədən sonra `saytla_danis` ilə yoxlaya bilərsən.

    `.env`-də `N8N_WEBHOOK_URL` doldurulubsa, analiz n8n Workflow 1 üzərindən
    başladılır (webhook → API → Postgres jurnalı).
    """
    if ayarlar.n8n_webhook_url:
        ugurlu, netice = await _n8n_ile(url, max_sehife)
        if not ugurlu:
            return f"❌ {netice}"
        return f"✅ n8n workflow-u işlədi: {netice}"

    ugurlu, netice = await _sorgu(
        "POST", "/api/analyze", json={"url": url, "max_sehife": max_sehife}
    )
    if not ugurlu:
        return f"❌ {netice}"

    return (
        f"✅ Analiz başladı\n"
        f"- analiz_id: {netice['analiz_id']}\n"
        f"- site_id: {netice['site_id']}\n"
        f"- ünvan: {netice['url']}\n\n"
        f"Fonda gedir (adətən 1-3 dəqiqə). Bitəndən sonra `saytla_danis` ilə "
        f"məzmun haqqında sual verə bilərsən."
    )


async def _n8n_ile(url: str, max_sehife: int):
    """Analizi n8n Workflow 1 webhook-u ilə başladır."""
    try:
        async with httpx.AsyncClient(timeout=UZUN_GOZLEME) as musteri:
            cavab = await musteri.post(
                ayarlar.n8n_webhook_url, json={"url": url, "max_sehife": max_sehife}
            )
        if cavab.status_code >= 400:
            return False, f"n8n {cavab.status_code}: {cavab.text[:300]}"
        return True, cavab.text[:500]
    except Exception as xeta:
        return False, f"n8n webhook-u cavab vermədi: {xeta}"


@mcp.tool()
async def saytla_danis(sayt: str, sual: str) -> str:
    """Analiz edilmiş saytın məzmunu haqqında sual verir (RAG + mənbələr).

    `sayt` — domen (`example.com`), tam ünvan və ya sayt nömrəsi.
    Cavab yalnız saytın öz mətninə əsaslanır; mənbə linkləri əlavə olunur.
    """
    qeyd, xeta = await _sayt_tap(sayt)
    if qeyd is None:
        return f"❌ {xeta}"

    ugurlu, netice = await _sorgu(
        "POST", f"/api/sites/{qeyd['id']}/chat",
        gozleme=UZUN_GOZLEME, json={"sual": sual},
    )
    if not ugurlu:
        return f"❌ {netice}"

    menbeler = "\n".join(
        f"- {m['basliq'] or m['url']}: {m['url']}" for m in netice.get("menbeler", [])
    )
    olcme = netice.get("olcme", {})

    return (
        f"{netice['cavab']}\n\n"
        f"**Mənbələr ({qeyd['domain']}):**\n{menbeler or '- mənbə tapılmadı'}\n\n"
        f"_{olcme.get('namized', 0)} namizəd → {olcme.get('secilmis', 0)} seçildi · "
        f"{olcme.get('model', '—')} · {olcme.get('umumi_saniye', 0)} san_"
    )


@mcp.tool()
async def saytlari_muqayise_et(sayt1: str, sayt2: str) -> str:
    """İki analiz edilmiş saytı yan-yana qoyur.

    Sürət, texnologiyalar, server, SEO çatışmazlıqları və AI rəyi müqayisə
    olunur. Hər ikisi əvvəlcədən analiz edilmiş olmalıdır.
    """
    ugurlu, netice = await _sorgu(
        "GET", "/api/muqayise", params={"sayt1": sayt1, "sayt2": sayt2}
    )
    if not ugurlu:
        return f"❌ {netice}"
    return netice["xulase"]


def isle() -> None:
    mcp.run()


if __name__ == "__main__":
    isle()
