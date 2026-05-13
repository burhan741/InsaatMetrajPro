import os
import sys
import logging
from pathlib import Path

# Logging konfigürasyonunu EN BAŞTA yap (import'lardan ÖNCE)

def setup_logging():
    """Logging konfigürasyonunu ayarla - EN BAŞTA ÇAĞRILMALI"""
    error_log_path = Path(__file__).parent / "error_log.txt"

    # Önceki handler'ları temizle
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    try:
        file_handler = logging.FileHandler(error_log_path, encoding='utf-8', mode='a')
        file_handler.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        logging.getLogger('app').setLevel(logging.DEBUG)
        logging.getLogger('app.core').setLevel(logging.DEBUG)
        logging.getLogger('app.ui').setLevel(logging.DEBUG)

        logging.info("=" * 60)
        logging.info("Logging konfigurasyonu aktif - DEBUG seviyesi")
        logging.info(f"Log dosyasi: {error_log_path}")
        logging.info("=" * 60)
    except Exception as e:
        print(f"Logging kurulum hatasi: {e}")


# Logging'i EN BAŞTA başlat
setup_logging()

# Şimdi diğer modülleri import et (hafif olanlar)
from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QIcon
from app.ui.styles import apply_dark_theme

# MainWindow lazy import edilir - splash screen gösterildikten sonra yüklenir
logging.info("Temel moduller import edildi - Uygulama hazir")


def _get_log_path() -> Path:
    """EXE ve geliştirme ortamı için doğru log yolunu döndür."""
    import os
    log_dir = os.environ.get('QUANTIX_LOG_DIR')
    if log_dir:
        return Path(log_dir) / "error_log.txt"
    return Path(__file__).parent / "error_log.txt"


def log_error_to_file(error_msg: str, error_trace: str = "") -> None:
    """Hatayı dosyaya yaz"""
    try:
        error_log_path = _get_log_path()
        with open(error_log_path, 'a', encoding='utf-8') as f:
            from datetime import datetime
            f.write(f"\n{'=' * 60}\n")
            f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{error_msg}\n")
            if error_trace:
                f.write(f"{error_trace}\n")
            f.write(f"{'=' * 60}\n")
    except Exception as e:
        print(f"Log yazma hatasi: {e}")


def gui_uygulamasi():
    """PyQt6 GUI uygulamasını başlat"""
    logging.info("gui_uygulamasi() fonksiyonu cagirildi - GUI baslatiliyor...")

    def exception_handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        import traceback
        error_msg = f"Yakalanamayan hata: {exc_type.__name__}: {exc_value}"
        error_trace = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(f"\nHATA: {error_msg}")
        print(error_trace)

        try:
            log_error_to_file(error_msg, error_trace)
        except:
            pass

        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance()
            if app:
                QMessageBox.critical(
                    None, "Kritik Hata",
                    f"Bir hata olustu:\n{str(exc_value)}\n\n"
                    f"Hata detaylari 'error_log.txt' dosyasina kaydedildi."
                )
        except:
            pass

    sys.excepthook = exception_handler

    try:
        app = QApplication(sys.argv)
        app.setApplicationName("QuantixPro")
        app.setOrganizationName("QuantixPro")

        # Uygulama ikonu
        icon_path = Path(__file__).parent / "assets" / "quantix_logo.png"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))

        # Splash screen - Quantix logo
        splash_path = Path(__file__).parent / "assets" / "quantix_logo.png"
        splash_fallback = Path(__file__).parent / "assets" / "splash.jpg"
        splash = None
        try:
            if splash_path.exists():
                splash_pixmap = QPixmap(str(splash_path))
                if not splash_pixmap.isNull():
                    splash = QSplashScreen(splash_pixmap)
                else:
                    splash = QSplashScreen()
            elif splash_fallback.exists():
                splash_pixmap = QPixmap(str(splash_fallback))
                if not splash_pixmap.isNull():
                    splash = QSplashScreen(splash_pixmap)
                else:
                    splash = QSplashScreen()
            else:
                splash = QSplashScreen()
        except:
            splash = QSplashScreen()

        splash.setStyleSheet("""
            QSplashScreen {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0a0a1a, stop:0.5 #1a2a3a, stop:1 #0a0a0a);
                color: #e0e0e0;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 18pt;
                font-weight: bold;
            }
        """)

        splash.showMessage(
            "QUANTIX PRO Yukleniyor...",
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
            Qt.GlobalColor.white
        )
        splash.show()
        app.processEvents()

        splash.showMessage(
            "Tema yukleniyor...",
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
            Qt.GlobalColor.white
        )
        app.processEvents()
        apply_dark_theme(app)

        splash.showMessage(
            "Arayuz hazirlaniyor...",
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
            Qt.GlobalColor.white
        )
        app.processEvents()

        # Başlangıç ekranı — Lisans Paketi Seçimi
        try:
            from app.ui.startup_dialog import StartupDialog

            startup = StartupDialog()
            if not startup.exec():
                sys.exit(0)

            selected_package = startup.selected_package
            enabled_modules = startup.enabled_modules

            if not selected_package:
                QMessageBox.critical(None, "Hata", "Lisans paketi seçilmedi!")
                sys.exit(1)

            # Paket adlarını Türkçe göster
            _paket_adi = {
                'baslangic': 'Başlangıç',
                'profesyonel': 'Profesyonel',
                'ihale': 'İhale',
                'kurumsal': 'Kurumsal',
            }
            splash.showMessage(
                f"QUANTIX PRO — {_paket_adi.get(selected_package, selected_package)} paketi yükleniyor...",
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                Qt.GlobalColor.white
            )
            app.processEvents()

            # Veritabanı bağlantısı
            # EXE modunda AppData'daki kalıcı DB'yi kullan
            from app.core.database import DatabaseManager
            import os as _os
            _data_dir = _os.environ.get('QUANTIX_DATA_DIR')
            if _data_dir:
                db = DatabaseManager(db_path=Path(_data_dir) / "insaat_metraj.db")
            else:
                db = DatabaseManager()

            # Ana pencere — tüm paketler için tek pencere;
            # hangi sekme/aracın aktif olduğunu selected_package + enabled_modules belirler.
            from app.ui.main_window import MainWindow
            window = MainWindow(
                db=db,
                splash=splash,
                selected_package=selected_package,
                enabled_modules=enabled_modules,
            )

            splash.finish(window)
            window.show()
            window.showMaximized()
        except Exception as e:
            error_msg = f"Pencere olusturma hatasi: {e}"
            print(f"HATA: {error_msg}")
            import traceback
            error_trace = traceback.format_exc()
            print(error_trace)
            log_error_to_file(error_msg, error_trace)
            QMessageBox.critical(None, "Kritik Hata",
                                 f"Uygulama baslatilamadi:\n{str(e)}")
            sys.exit(1)

        sys.exit(app.exec())
    except Exception as e:
        error_msg = f"Uygulama baslatma hatasi: {e}"
        print(f"HATA: {error_msg}")
        import traceback
        error_trace = traceback.format_exc()
        print(error_trace)
        log_error_to_file(error_msg, error_trace)
        sys.exit(1)


if __name__ == "__main__":
    gui_uygulamasi()
