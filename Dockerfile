# SaytLupa — istehsal image-i.
#
# Qurmaq:   docker build -t saytlupa:son .
# Sınamaq:  docker run --rm -p 8000:8000 --env-file .env saytlupa:son
#
# Qeyd: `requirements.lock.txt` işlədilir, `requirements.txt` yox — transitiv
# asılılıqlar da kilidlidir, yəni serverdə qurulan image lokaldakı ilə eynidir.

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# `curl` yalnız HEALTHCHECK üçündür — Docker konteynerin sağlamlığını
# onunla yoxlayır və compose `depends_on: condition: service_healthy` işləyir.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Asılılıqlar koddan ƏVVƏL köçürülür: kod dəyişəndə bu qat keşdən götürülür və
# image yenidən qurulanda `pip install` təkrarlanmır.
COPY requirements.lock.txt ./
RUN pip install -r requirements.lock.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Root olaraq işləmirik: konteyner ələ keçsə belə fayl sistemi məhdud qalsın.
# `data/` və `storage/` volume kimi bağlanır (bax docker-compose.prod.yml) —
# qovluqlar əvvəlcədən yaradılır ki, sahibi düzgün olsun.
RUN useradd --create-home --uid 1000 saytlupa \
    && mkdir -p /app/data /app/storage \
    && chown -R saytlupa:saytlupa /app
USER saytlupa

EXPOSE 8000

# `start-period` böyükdür: ilk qalxışda baza cədvəlləri yaradılır və
# `DB_GOZLEME_SANIYE` qədər Postgres gözlənilə bilər.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8000}/api/health || exit 1

# Tək işçi: analiz fonda `asyncio.create_task` ilə gedir və SSE növbəsi həmin
# prosesin yaddaşındadır (`hadise.py`). İki işçi olsa SSE sorğusu analizi
# başlatmayan prosesə düşüb boş növbə gözləyə bilər.
#
# `exec` formasında yox, qabıq formasında yazılıb ki, `$PORT` açılsın: Railway
# portu özü seçib mühit dəyişəni kimi verir və tətbiq **məhz** ona qulaq
# asmalıdır. Lokalda və Docker Compose-da dəyişən yoxdur — 8000 qalır.
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
