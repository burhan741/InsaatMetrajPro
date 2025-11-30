"""
InsaatMetrajPro - Ana Giriş Noktası
İnşaat sektörü için profesyonel masaüstü metraj uygulaması
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.styles import apply_dark_theme


def main() -> None:
    """
    Uygulamanın ana giriş noktası.
    
    PyQt6 uygulamasını başlatır, temayı uygular ve ana pencereyi gösterir.
    """
    try:
        # Uygulama oluştur (PyQt6'da High DPI desteği otomatik)
        app = QApplication(sys.argv)
        app.setApplicationName("InsaatMetrajPro")
        app.setOrganizationName("InsaatMetrajPro")
        
        # Koyu temayı uygula
        apply_dark_theme(app)
        
        # Ana pencereyi oluştur ve göster
        print("Ana pencere oluşturuluyor...")
        window = MainWindow()
        print("Ana pencere oluşturuldu, gösteriliyor...")
        window.show()
        print("Pencere gösterildi, uygulama başlatılıyor...")
        
        # Uygulamayı çalıştır
        sys.exit(app.exec())
    except Exception as e:
        print(f"HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
