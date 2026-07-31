"""Bütün testlər üçün ortaq şərtlər.

Testlər tərtibatçının `.env` faylından **asılı olmamalıdır**. Bu, real hadisə
nəticəsində yazıldı: servere hazırlıq zamanı `.env`-ə `API_ACAR` əlavə edildi və
kodda bir sətir də dəyişməmiş 17 test sındı — çünki qapı testləri "serverdə açar
qoyulmayıb" vəziyyətini `.env`-in boşluğundan alırdı.

İndi qapı hər testdə standart olaraq **açıq** vəziyyətə salınır. Açar lazım olan
testlər onu özləri qoyur (bax `test_qapi.py`-dəki `acarli` fixture) — autouse
fixture eyni əhatədə açıq istənilən fixture-dən əvvəl işlədiyi üçün sıra düzdür.
"""

import pytest

from backend.config import ayarlar


@pytest.fixture(autouse=True)
def acarsiz_qapi(monkeypatch):
    """Standart vəziyyət: `API_ACAR` boş, yəni heç bir məhdudiyyət yoxdur."""
    monkeypatch.setattr(ayarlar, "api_acar", "")
