"""SQLAlchemy modelləri və sessiya idarəsi.

Postgres (psycopg2 + pgvector) əsas bazadır. Əlçatmaz olsa layihə çökmür —
SQLite-a keçir və embedding-lər mətn kimi saxlanır.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from .config import ayarlar

log = logging.getLogger("saytlupa")

EMBEDDING_OLCUSU = 768

# Postgres gözlənilərkən cəhdlər arasındakı fasilə
GOZLEME_ADDIMI = 2.0


def _qosulur(url: str) -> bool:
    """Bir dəfəlik qoşulma sınağı."""
    try:
        sinaq = create_engine(url, pool_pre_ping=True)
        with sinaq.connect() as qosulma:
            qosulma.execute(text("SELECT 1"))
        sinaq.dispose()
        return True
    except Exception:
        return False


def _movcud(url: str, gozleme: float = 0.0) -> bool:
    """Verilən bazaya qoşulmaq mümkündürmü?

    `gozleme` saniyə verilsə, alınmayana qədər təkrar cəhd edilir. Bu, Docker
    Compose üçündür: `api` konteyneri `db`-dən tez qalxa bilər və bir dəfəlik
    yoxlama uğursuz olsa tətbiq **ömrünün sonuna qədər** SQLite-da işləyərdi
    (`POSTGRES` modul sabitidir, sonradan dəyişmir).
    """
    if not url:
        return False

    son = time.monotonic() + gozleme
    while True:
        if _qosulur(url):
            return True
        if time.monotonic() >= son:
            return False
        log.info("Postgres hələ hazır deyil — %s san sonra yenidən", GOZLEME_ADDIMI)
        time.sleep(GOZLEME_ADDIMI)


POSTGRES = _movcud(ayarlar.database_url, ayarlar.db_gozleme_saniye)
DB_URL = ayarlar.database_url if POSTGRES else ayarlar.sqlite_yolu

# Səssiz enmə ən təhlükəli haldır: `DATABASE_URL` yazılıb, amma baza cavab
# vermirsə layihə SQLite-da işləyir və heç kim fərqinə varmır — vektor axtarışı
# Python tərəfə keçir, köhnə Postgres məlumatı isə görünmür.
SESSIZ_ENDI = bool(ayarlar.database_url) and not POSTGRES
if SESSIZ_ENDI:
    log.warning(
        "DATABASE_URL təyin edilib, amma baza cavab vermədi — SQLite-a keçildi. "
        "Postgres gözlənilməlidirsə `DB_GOZLEME_SANIYE` dəyərini artır."
    )

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)
SessionYaradan = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _embedding_sutunu():
    """Postgres-də vector, SQLite-da mətn."""
    if POSTGRES:
        from pgvector.sqlalchemy import Vector

        return Column(Vector(EMBEDDING_OLCUSU))
    return Column(Text)


def indi() -> datetime:
    return datetime.now(timezone.utc)


class Baza(DeclarativeBase):
    pass


class Sayt(Baza):
    __tablename__ = "sites"

    id = Column(Integer, primary_key=True)
    url = Column(String(500), nullable=False)
    domain = Column(String(255), index=True, nullable=False)
    ilk_analiz = Column(DateTime(timezone=True), default=indi)
    son_analiz = Column(DateTime(timezone=True), default=indi)
    izlenir = Column(Boolean, default=False)

    analizler = relationship("Analiz", back_populates="sayt", cascade="all, delete")
    sehifeler = relationship("Sehife", back_populates="sayt", cascade="all, delete")


class Analiz(Baza):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    tarix = Column(DateTime(timezone=True), default=indi)
    xam_json = Column(JSON, default=dict)      # collector-lərin xam nəticəsi
    ai_hesabat = Column(JSON, default=dict)    # Claude-un 6 bəndlik hesabatı
    status = Column(String(30), default="gozleyir")  # gozleyir/isleyir/hazir/xeta
    xeta = Column(Text, default="")

    sayt = relationship("Sayt", back_populates="analizler")


class Sehife(Baza):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    url = Column(String(1000), nullable=False)
    basliq = Column(String(500), default="")
    metn = Column(Text, default="")
    hash = Column(String(64), index=True, default="")
    yigilma_tarixi = Column(DateTime(timezone=True), default=indi)

    sayt = relationship("Sayt", back_populates="sehifeler")
    chunklar = relationship("Chunk", back_populates="sehife", cascade="all, delete")


class Chunk(Baza):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    page_id = Column(Integer, ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    sira = Column(Integer, default=0)
    metn = Column(Text, nullable=False)
    embedding = _embedding_sutunu()
    # Hansı üsulla vektorlaşdırılıb: "gemini" və ya "lokal".
    # Üsul dəyişəndə köhnə vektorlar yenisi ilə müqayisə oluna bilməz —
    # bu sütun sayəsində köhnələri tapıb yenidən hesablamaq mümkündür.
    model = Column(String(30), default="")

    sehife = relationship("Sehife", back_populates="chunklar")

    def embedding_yaz(self, vektor: list[float]) -> None:
        self.embedding = vektor if POSTGRES else json.dumps(vektor)

    def embedding_oxu(self) -> list[float]:
        if self.embedding is None:
            return []
        return list(self.embedding) if POSTGRES else json.loads(self.embedding)


class Sohbet(Baza):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    yaradilma = Column(DateTime(timezone=True), default=indi)

    mesajlar = relationship("Mesaj", back_populates="sohbet", cascade="all, delete")


class Mesaj(Baza):
    """RAG yaddaşı — söhbətin tarixçəsi burada saxlanır."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    rol = Column(String(20))  # istifadeci / asistent
    metn = Column(Text)
    istifade_olunan_chunklar = Column(JSON, default=list)
    tarix = Column(DateTime(timezone=True), default=indi)

    sohbet = relationship("Sohbet", back_populates="mesajlar")


class Izleme(Baza):
    __tablename__ = "site_watches"

    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    cron = Column(String(50), default="0 9 * * *")
    son_yoxlama = Column(DateTime(timezone=True))
    son_deyisiklik = Column(Text, default="")
    telegram_chat_id = Column(String(50), default="")


class IsXetasi(Baza):
    """n8n Error Workflow buraya yazır."""

    __tablename__ = "job_errors"

    id = Column(Integer, primary_key=True)
    menbe = Column(String(100), default="")
    workflow = Column(String(200), default="")
    xeta_metni = Column(Text, default="")
    tarix = Column(DateTime(timezone=True), default=indi)


class N8nQeyd(Baza):
    """n8n workflow-larının bazaya yazdığı jurnal.

    Workflow 1 (analiz tetikleyicisi) nəticəni birbaşa Postgres node ilə bura
    yazır — kursun "n8n + PostgreSQL" tələbi. Cədvəli Python yaradır ki, n8n
    tərəfdə əl ilə SQL yazmağa ehtiyac qalmasın.
    """

    __tablename__ = "n8n_jurnal"

    id = Column(Integer, primary_key=True)
    workflow = Column(String(200), default="")
    site_id = Column(Integer)
    analiz_id = Column(Integer)
    xulase = Column(Text, default="")
    data = Column(JSON, default=dict)
    tarix = Column(DateTime(timezone=True), default=indi)


class TesdiqDomen(Baza):
    """Aktiv skan üçün sahibliyi təsdiqlənmiş domenlər.

    Aktiv skan real payload göndərir — yalnız sahibi olduğun saytda qanunidir.
    Sahiblik DNS TXT (`saytlupa-verify=<token>`) və ya kök fayl-token ilə sübut
    olunur. `.env`-dəki `OWNED_DOMAINS` allowlist-i buradan asılı deyil.
    """

    __tablename__ = "verified_domains"

    id = Column(Integer, primary_key=True)
    domain = Column(String(255), index=True, nullable=False)
    token = Column(String(64), nullable=False)
    usul = Column(String(10), default="dns")            # dns / fayl
    status = Column(String(20), default="gozleyir")     # gozleyir / tesdiqli
    yaradilma = Column(DateTime(timezone=True), default=indi)
    tesdiq_tarixi = Column(DateTime(timezone=True))


class AktivSkan(Baza):
    """Aktiv skan işi (job). Worker növbədən götürür, nuclei işlədir, nəticə yazır."""

    __tablename__ = "active_scans"

    id = Column(Integer, primary_key=True)
    domain = Column(String(255), index=True, nullable=False)
    target_url = Column(String(500), nullable=False)
    # gozleyir / isleyir / bitdi / xeta / dayandirildi
    status = Column(String(20), default="gozleyir", index=True)
    tapintilar = Column(JSON, default=list)             # finding sxemi (aktiv)
    bal = Column(Integer)
    herf = Column(String(1), default="")
    gedisat = Column(Text, default="")                  # son gedişat mesajı
    xeta = Column(Text, default="")
    yaradilma = Column(DateTime(timezone=True), default=indi)
    baslama = Column(DateTime(timezone=True))
    bitme = Column(DateTime(timezone=True))


def _sutun_elave_et(cedvel: str, sutun: str, tip: str) -> None:
    """Kiçik miqrasiya: sütun yoxdursa əlavə edir.

    Layihə inkişaf mərhələsindədir; tam Alembic miqrasiyası əvəzinə bu kifayətdir.
    Sütun artıq varsa xəta udulur.
    """
    try:
        with engine.connect() as qosulma:
            qosulma.execute(text(f"ALTER TABLE {cedvel} ADD COLUMN {sutun} {tip}"))
            qosulma.commit()
    except Exception:
        pass


def baza_qur() -> None:
    """Cədvəlləri, pgvector genişlənməsini və indeksləri yaradır."""
    if POSTGRES:
        with engine.connect() as qosulma:
            qosulma.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            qosulma.commit()

    Baza.metadata.create_all(engine)
    _sutun_elave_et("chunks", "model", "VARCHAR(30)")

    if POSTGRES:
        with engine.connect() as qosulma:
            # Vektor axtarışı üçün HNSW indeks (kosinus məsafəsi)
            qosulma.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw "
                    f"ON chunks USING hnsw (embedding vector_cosine_ops)"
                )
            )
            # Açar söz axtarışı üçün GIN indeks.
            # 'simple' konfiqurasiyası seçilib: Postgres-də Azərbaycan dili üçün
            # hazır lüğət yoxdur, 'simple' isə sözləri olduğu kimi indeksləyir.
            qosulma.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS chunks_metn_gin "
                    "ON chunks USING gin (to_tsvector('simple', metn))"
                )
            )
            qosulma.commit()


def sessiya() -> Session:
    return SessionYaradan()


def veziyyet() -> dict:
    return {
        "baza": "postgresql" if POSTGRES else "sqlite",
        "url_sxemi": DB_URL.split("://")[0],
        "xeberdarliq": (
            "DATABASE_URL təyin edilib, amma baza cavab vermədi — SQLite işlədilir."
            if SESSIZ_ENDI
            else ""
        ),
    }
