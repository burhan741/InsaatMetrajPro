"""
pytest ortak duzeni.

Gercek puantaj.db'ye ASLA dokunulmaz: modul importundan ONCE
PUANTAJ_DB_PATH gecici bir dosyaya yonlendirilir; her test kendi gecici
veritabanini 'yeni_db' fikstur'u ile alir.
"""
import importlib.util
import os
import shutil
import sys
import tempfile

import pytest

KLASOR = os.path.dirname(os.path.abspath(__file__))
_OTURUM_KLASORU = tempfile.mkdtemp(prefix='santiye_test_')
os.environ['PUANTAJ_DB_PATH'] = os.path.join(_OTURUM_KLASORU, 'oturum.db')
if KLASOR not in sys.path:
    sys.path.insert(0, KLASOR)

import ortak  # noqa: E402
import puantaj  # noqa: E402
import app as app_modul  # noqa: E402

ESKI_APP = os.path.join(KLASOR, 'eski', 'app_tek_dosya.py')
YEREL_GERCEK_DB = os.path.join(KLASOR, 'puantaj.db')


def db_yonlendir(monkeypatch, yol):
    """Tum yeni modulleri verilen veritabani dosyasina yonlendirir."""
    monkeypatch.setattr(ortak, 'DB_PATH', yol)
    monkeypatch.setattr(puantaj, 'DB_PATH', yol)


@pytest.fixture
def yeni_db(tmp_path, monkeypatch):
    yol = str(tmp_path / 'puantaj.db')
    db_yonlendir(monkeypatch, yol)
    ortak.veritabani_hazirla(app_modul.INIT_FONKSIYONLARI)
    return yol


@pytest.fixture
def istemci(yeni_db):
    app_modul.app.config['TESTING'] = True
    return app_modul.app.test_client()


_ESKI_SAYAC = [0]


def eski_app_yukle(klasor, kaynak_db=None):
    """Eski tek dosyalik app.py'yi 'klasor' icinde, kendi puantaj.db'siyle yukler.

    Eski dosya DB_PATH'i kendi klasorunden turettigi icin gecici klasore
    kopyalanip oradan import edilir (gercek veritabanina dokunmaz).
    """
    os.makedirs(klasor, exist_ok=True)
    if kaynak_db:
        shutil.copy2(kaynak_db, os.path.join(klasor, 'puantaj.db'))
    hedef = os.path.join(klasor, 'eski_app_kopya.py')
    shutil.copy2(ESKI_APP, hedef)
    _ESKI_SAYAC[0] += 1
    spec = importlib.util.spec_from_file_location('eski_app_%d' % _ESKI_SAYAC[0], hedef)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.app.config['TESTING'] = True
    return mod
