"""SaytLupa — sayt analiz və söhbət agenti."""

import logging

__version__ = "0.1.0"

# Jurnal burada qurulur, `main.py`-də yox.
#
# Səbəb sınaq zamanı üzə çıxdı: `db.py` Postgres yoxlamasını **import anında**
# edir, `main.py`-dəki `basicConfig` isə importlardan sonra işləyirdi. Nəticədə
# baza gözlənilən 60 saniyə ərzində konteyner jurnalı tamamilə boş qalırdı —
# kənardan baxanda proqram donmuş kimi görünürdü. Paket `__init__`-i istənilən
# `backend.*` importundan əvvəl işlədiyi üçün jurnal artıq ilk sətirdən hazırdır.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
