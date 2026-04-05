# PyInstaller Runtime Hook — QuantixPro
# EXE calisirken AppData yollarini, SSL sertifikalarini ve DB seed'ini ayarlar

import os
import sys
from pathlib import Path


def _setup_appdata_dir():
    """Kullanici AppData klasorunde QuantixPro dizinini olustur."""
    appdata = Path(os.environ.get('APPDATA', Path.home())) / "QuantixPro"
    (appdata / "data").mkdir(parents=True, exist_ok=True)
    (appdata / "logs").mkdir(parents=True, exist_ok=True)
    (appdata / "exports").mkdir(parents=True, exist_ok=True)
    return appdata


def _seed_data_files(appdata: Path):
    """
    Ilk calistirmada seed dosyalarini _MEIPASS'dan AppData'ya kopyala.
    Mevcut dosyalarin ustune YAZMAZ (kullanici verisini korur).
    """
    import shutil
    meipass_data = Path(sys._MEIPASS) / "data"
    target_data = appdata / "data"

    seed_files = [
        "insaat_metraj.db",
        "claude_config.json",
    ]
    for fname in seed_files:
        src = meipass_data / fname
        dst = target_data / fname
        if src.exists() and not dst.exists():
            shutil.copy2(str(src), str(dst))


def _setup_env_vars(appdata: Path):
    """
    Modul seviyesinde path'leri override etmek icin env variable'lari set et.
    claude_engine.py ve database.py bu degiskenleri okur.
    """
    os.environ['QUANTIX_DATA_DIR'] = str(appdata / "data")
    os.environ['QUANTIX_LOG_DIR'] = str(appdata / "logs")
    os.environ['QUANTIX_EXPORT_DIR'] = str(appdata / "exports")


def _setup_ssl_certs():
    """certifi SSL sertifikalarini ayarla (requests / anthropic icin)."""
    try:
        import certifi
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    except ImportError:
        pass


def _setup_qt_plugins():
    """PyQt6 plugin yolunu ayarla."""
    if hasattr(sys, '_MEIPASS'):
        qt_plugins = Path(sys._MEIPASS) / "PyQt6" / "Qt6" / "plugins"
        if qt_plugins.exists():
            os.environ['QT_PLUGIN_PATH'] = str(qt_plugins)


def _setup_matplotlib():
    """
    Matplotlib backend'i EXE modunda dogrudan ayarla.
    Oto-tespit EXE ortaminda RuntimeError veya segfault uretebilir.
    QtAgg: PyQt6 ile entegre calisir, FigureCanvasQTAgg ile uyumlu.
    """
    os.environ.setdefault('MPLBACKEND', 'QtAgg')
    # Matplotlib font cache'i AppData'ya yonlendir (EXE icinde yazılamaz)
    appdata_mpl = Path(os.environ.get('APPDATA', Path.home())) / "QuantixPro" / "mpl_cache"
    appdata_mpl.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(appdata_mpl))


# EXE baslarken calistir
if getattr(sys, 'frozen', False):
    _appdata = _setup_appdata_dir()
    _seed_data_files(_appdata)
    _setup_env_vars(_appdata)
    _setup_ssl_certs()
    _setup_qt_plugins()
    _setup_matplotlib()
