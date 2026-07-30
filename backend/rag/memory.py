"""Söhbət yaddaşı.

RAG-da yaddaş olmasa hər sual təkbaşına qalır və "bəs qiyməti nə qədərdir?"
kimi davam sualları mənasızlaşır. Ona görə:

- bütün mesajlar `messages` cədvəlində saxlanılır;
- modelə son N mesaj **olduğu kimi** verilir;
- söhbət uzananda köhnə hissə bir cümləlik xülasəyə çevrilir ki, kontekst
  həddindən artıq böyüməsin.
"""

from __future__ import annotations

from .. import db

SON_MESAJ = 6          # modelə olduğu kimi verilən son mesaj sayı
XULASE_HEDDI = 10      # bundan çox mesaj olsa köhnələr xülasələnir


def sohbet_yarat(site_id: int) -> int:
    with db.sessiya() as s:
        sohbet = db.Sohbet(site_id=site_id)
        s.add(sohbet)
        s.commit()
        return sohbet.id


def sohbet_tap_ve_ya_yarat(site_id: int, session_id: int | None) -> int:
    if session_id:
        with db.sessiya() as s:
            sohbet = s.get(db.Sohbet, session_id)
            if sohbet and sohbet.site_id == site_id:
                return sohbet.id
    return sohbet_yarat(site_id)


def mesaj_yaz(
    session_id: int, rol: str, metn: str, chunklar: list[dict] | None = None
) -> None:
    with db.sessiya() as s:
        s.add(
            db.Mesaj(
                session_id=session_id,
                rol=rol,
                metn=metn,
                istifade_olunan_chunklar=[
                    {"id": c.get("id"), "url": c.get("url")} for c in (chunklar or [])
                ],
            )
        )
        s.commit()


def tarixce(session_id: int, limit: int = SON_MESAJ) -> list[dict]:
    """Son mesajlar — köhnədən yeniyə sıra ilə."""
    with db.sessiya() as s:
        qeydler = (
            s.query(db.Mesaj)
            .filter(db.Mesaj.session_id == session_id)
            .order_by(db.Mesaj.id.desc())
            .limit(limit)
            .all()
        )
    return [{"rol": m.rol, "metn": m.metn} for m in reversed(qeydler)]


def mesaj_sayi(session_id: int) -> int:
    with db.sessiya() as s:
        return s.query(db.Mesaj).filter(db.Mesaj.session_id == session_id).count()


def kohne_xulase(session_id: int) -> str:
    """Son mesajlardan əvvəlki hissənin qısa xülasəsi.

    Model çağırmadan qurulur — söhbətin əvvəlində nədən danışıldığını xatırlatmaq
    üçün istifadəçi suallarını sadalamaq kifayətdir və pulsuzdur.
    """
    if mesaj_sayi(session_id) <= XULASE_HEDDI:
        return ""

    with db.sessiya() as s:
        kohneler = (
            s.query(db.Mesaj)
            .filter(db.Mesaj.session_id == session_id, db.Mesaj.rol == "istifadeci")
            .order_by(db.Mesaj.id)
            .limit(20)
            .all()
        )
    suallar = [m.metn.strip() for m in kohneler][:-2]
    if not suallar:
        return ""
    return "Söhbətin əvvəlində soruşulanlar: " + "; ".join(suallar)


def kontekst_metni(session_id: int) -> str:
    """Modelə veriləcək yaddaş bloku."""
    parcalar = []
    xulase = kohne_xulase(session_id)
    if xulase:
        parcalar.append(xulase)

    for mesaj in tarixce(session_id):
        kim = "İstifadəçi" if mesaj["rol"] == "istifadeci" else "Sən"
        parcalar.append(f"{kim}: {mesaj['metn']}")

    return "\n".join(parcalar)
