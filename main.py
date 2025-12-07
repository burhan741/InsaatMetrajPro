import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt6.QtCore import Qt, QFileSystemWatcher, QTimer
from PyQt6.QtGui import QPixmap, QFont
from app.ui.main_window import MainWindow
from app.ui.styles import apply_dark_theme

# --- AYARLAR ---
DOSYA_ADI = "senin_dosyanin_adi.dxf"  # <-- Dosya adını buraya yaz
BIRIM = "cm"                           # Projenin birimi
BOSLUK_TOLERANSI = 20                  # CM olduğu için 20 yazdık (20 cm boşlukları kapatır)


def log_error_to_file(error_msg: str, error_trace: str = "") -> None:
    """Hatayı dosyaya yaz"""
    try:
        error_log_path = Path(__file__).parent / "error_log.txt"
        with open(error_log_path, 'a', encoding='utf-8') as f:
            from datetime import datetime
            f.write(f"\n{'='*60}\n")
            f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{error_msg}\n")
            if error_trace:
                f.write(f"{error_trace}\n")
            f.write(f"{'='*60}\n")
        print(f"✅ Hata log dosyasına yazıldı: {error_log_path}")
    except Exception as e:
        print(f"Log yazma hatası: {e}")


def gui_uygulamasi():
    """PyQt6 GUI uygulamasını başlat"""
    # Global exception handler (tüm yakalanmamış hatalar için)
    def exception_handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        import traceback
        error_msg = f"Yakalanmamış hata: {exc_type.__name__}: {exc_value}"
        error_trace = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(f"\n❌ {error_msg}")
        print(error_trace)
        log_error_to_file(error_msg, error_trace)
        
        # Uygulamayı kapatmadan devam et (kullanıcıya hata göster)
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance()
            if app:
                QMessageBox.critical(
                    None, "Kritik Hata",
                    f"Bir hata oluştu:\n{str(exc_value)}\n\n"
                    f"Hata detayları 'error_log.txt' dosyasına kaydedildi.\n\n"
                    f"Lütfen programı yeniden başlatın."
                )
        except:
            pass  # QMessageBox da hata verirse sessizce geç
    
    sys.excepthook = exception_handler
    
    # Hot reload özelliği (sadece development modunda)
    def setup_hot_reload(app):
        """Dosya değişikliklerini izle ve otomatik yeniden yükle"""
        # Sadece normal Python modunda çalış (EXE'de çalışmasın)
        if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS'):
            return
        
        try:
            watcher = QFileSystemWatcher()
            project_root = Path(__file__).parent
            
            # İzlenecek dosyalar ve klasörler
            watch_paths = []
            
            # app/ klasöründeki tüm .py dosyalarını izle
            app_dir = project_root / "app"
            if app_dir.exists():
                for py_file in app_dir.rglob("*.py"):
                    watch_paths.append(str(py_file))
            
            # main.py'yi de izle
            main_py = project_root / "main.py"
            if main_py.exists():
                watch_paths.append(str(main_py))
            
            if not watch_paths:
                return
            
            # Dosyaları izlemeye başla
            watcher.addPaths(watch_paths)
            
            # Yeniden başlatma timer'ı (çoklu değişiklikleri tek seferde işle)
            restart_timer = QTimer()
            restart_timer.setSingleShot(True)
            restart_timer.timeout.connect(lambda: restart_application(app))
            
            def on_file_changed(path):
                """Dosya değiştiğinde çağrılır"""
                # Sadece .py dosyaları için yeniden başlat
                if path.endswith('.py'):
                    print(f"🔄 Dosya değişti: {Path(path).name}")
                    # 1 saniye bekle (çoklu kaydetmeleri tek seferde işle)
                    restart_timer.stop()
                    restart_timer.start(1000)  # 1 saniye
            
            watcher.fileChanged.connect(on_file_changed)
            
            print(f"✅ Hot reload aktif: {len(watch_paths)} dosya izleniyor")
            
        except Exception as e:
            print(f"⚠️ Hot reload kurulumu başarısız: {e}")
    
    def restart_application(app):
        """Uygulamayı yeniden başlat"""
        try:
            reply = QMessageBox.question(
                None, "Kod Değişikliği",
                "Kod dosyalarında değişiklik algılandı.\n\n"
                "Uygulamayı yeniden başlatmak ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                print("🔄 Uygulama yeniden başlatılıyor...")
                # Python'u yeniden başlat
                python = sys.executable
                os.execl(python, python, *sys.argv)
        except Exception as e:
            print(f"❌ Yeniden başlatma hatası: {e}")
    
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("InsaatMetrajPro")
        app.setOrganizationName("InsaatMetrajPro")
        
        # Splash screen oluştur (görsel arka plan ile)
        splash_path = Path(__file__).parent / "assets" / "splash.jpg"
        splash = None
        try:
            if splash_path.exists():
                splash_pixmap = QPixmap(str(splash_path))
                if not splash_pixmap.isNull():
                    splash = QSplashScreen(splash_pixmap)
                else:
                    splash = QSplashScreen()
            else:
                splash = QSplashScreen()
        except Exception as e:
            print(f"Splash screen görsel yükleme hatası: {e}")
            splash = QSplashScreen()
        
        # Splash screen stili (wireframe teması)
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
            "🏗️ İnşaat Metraj Pro Yükleniyor...",
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
            Qt.GlobalColor.white
        )
        splash.show()
        app.processEvents()  # UI'ı güncelle
        
        splash.showMessage(
            "Tema yükleniyor...",
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
            Qt.GlobalColor.white
        )
        app.processEvents()
        apply_dark_theme(app)
        
        splash.showMessage(
            "Arayüz hazırlanıyor...",
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
            Qt.GlobalColor.white
        )
        app.processEvents()
        
        # Başlangıç ekranı - Kullanıcı tipi seçimi
        try:
            from app.ui.startup_dialog import StartupDialog
            
            startup = StartupDialog()
            if not startup.exec():
                # Kullanıcı iptal etti
                sys.exit(0)
            
            user_type = startup.user_type
            
            if not user_type:
                QMessageBox.critical(None, "Hata", "Kullanıcı tipi seçilmedi!")
                sys.exit(1)
            
            # Splash mesajını güncelle
            if user_type == 'muteahhit':
                splash.showMessage(
                    "Müteahhit modu yükleniyor...",
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                    Qt.GlobalColor.white
                )
            else:
                splash.showMessage(
                    "Taşeron modu yükleniyor...",
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                    Qt.GlobalColor.white
                )
            app.processEvents()
            
            # Veritabanı bağlantısını oluştur
            from app.core.database import DatabaseManager
            db = DatabaseManager()
            
            # Ana pencereyi oluştur (kullanıcı tipi ile)
            if user_type == 'taseron':
                from app.ui.taseron_window import TaseronWindow
                window = TaseronWindow(db=db, splash=splash)
            else:
                window = MainWindow(splash=splash, user_type=user_type)
            
            # Splash screen'i kapat
            splash.finish(window)
            window.show()
        except Exception as e:
            error_msg = f"Pencere oluşturma hatası: {e}"
            print(f"❌ {error_msg}")
            import traceback
            error_trace = traceback.format_exc()
            print(error_trace)
            log_error_to_file(error_msg, error_trace)
            QMessageBox.critical(None, "Kritik Hata", 
                              f"Uygulama başlatılamadı:\n{str(e)}\n\n"
                              f"Detaylar 'error_log.txt' dosyasına kaydedildi.")
            sys.exit(1)
        
        # Hot reload özelliğini aktif et (development modunda)
        setup_hot_reload(app)
        
        sys.exit(app.exec())
    except Exception as e:
        error_msg = f"Uygulama başlatma hatası: {e}"
        print(f"❌ {error_msg}")
        import traceback
        error_trace = traceback.format_exc()
        print(error_trace)
        log_error_to_file(error_msg, error_trace)
        sys.exit(1)


def rapor_olustur(dxf_dosya_adi=None, cizim_birimi=None, bosluk_toleransi=None):
    """
    DXF analiz raporu oluşturur.
    
    Args:
        dxf_dosya_adi: DXF dosya yolu (None ise AYARLAR'dan alınır)
        cizim_birimi: Çizim birimi (None ise AYARLAR'dan alınır)
        bosluk_toleransi: Boşluk toleransı (None ise AYARLAR'dan alınır)
    """
    # Lazy import - sadece gerektiğinde yükle
    import pandas as pd
    from app.core.dxf_engine import DXFAnaliz
    
    # Parametreler verilmemişse AYARLAR'dan al
    if dxf_dosya_adi is None:
        dxf_dosya_adi = DOSYA_ADI
    if cizim_birimi is None:
        cizim_birimi = BIRIM
    if bosluk_toleransi is None:
        bosluk_toleransi = BOSLUK_TOLERANSI
    
    print(f"📏 Proje Birimi: {cizim_birimi.upper()}")
    print(f"🔧 Tamir Toleransı: {bosluk_toleransi} birim")
    print("-" * 30)
    
    try:
        # Motoru başlat
        proje = DXFAnaliz(dxf_dosya_adi, cizim_birimi=cizim_birimi)
    except SystemExit:
        return
    
    katmanlar = proje.katmanlari_listele()
    metraj_verileri = []
    
    for katman in katmanlar:
        # Toleransı buraya gönderiyoruz
        sonuc = proje.alan_hesapla(katman, tolerans=bosluk_toleransi)
        
        # Sadece 0'dan büyük ve mantıklı alanları al (Örn: 0.5 m2'den küçük tozları alma)
        if sonuc["toplam_miktar"] > 0.5:
            metraj_verileri.append({
                "Katman": katman,
                "Alan (m²)": sonuc["toplam_miktar"],
                "Parça": sonuc["parca_sayisi"],
                "AI Notu": sonuc.get("not", "")
            })
            print(f"✅ {katman}: {sonuc['toplam_miktar']} m² ({sonuc.get('not', '')})")
    
    # Excel Çıktısı
    if metraj_verileri:
        df = pd.DataFrame(metraj_verileri)
        excel_adi = "metraj_sonuc.xlsx"
        
        try:
            df.to_excel(excel_adi, index=False)
            print(f"\n💾 Rapor kaydedildi: {excel_adi}")
        except PermissionError:
            print(f"\n❌ HATA: '{excel_adi}' dosyası şu an açık! Lütfen Excel'i kapatıp tekrar dene.")
    else:
        print("\n⚠️ Hiçbir kapalı alan bulunamadı. Toleransı artırmayı dene (Örn: 30 veya 50 yap).")


# --- ÇALIŞTIR ---
if __name__ == "__main__":
    # EXE olup olmadığını kontrol et (PyInstaller ile oluşturulmuş mu?)
    # EXE'de sys.frozen True olur ve konsol yok, direkt GUI açılmalı
    is_exe = getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')
    
    if is_exe:
        # EXE modunda: Direkt GUI'yi aç (konsol yok, input() çalışmaz)
        gui_uygulamasi()
    else:
        # Normal Python modunda: Menü göster
        # Kullanıcıya seçim yaptır
        print("=" * 60)
        print("🏗️  İNŞAAT METRAJ PRO - Hoş Geldiniz!")
        print("=" * 60)
        print("\nNe yapmak istersiniz?")
        print("  1. GUI Uygulamasını Aç (Metraj Cetveli, CAD İşleyici, vb.)")
        print("  2. DXF Analiz Scripti Çalıştır (Excel Raporu Oluştur)")
        print("  3. Çıkış")
        
        secim = input("\nSeçiminiz (1/2/3): ").strip()
        
        if secim == "1":
            # GUI uygulamasını başlat
            print("\n🖥️  GUI uygulaması başlatılıyor...\n")
            gui_uygulamasi()
        
        elif secim == "2":
            # DXF analiz scriptini çalıştır
            print("\n📊 DXF Analiz modu başlatılıyor...\n")
            
            # DXF dosya yolu - Kendi dosyanızın tam yolunu buraya yazın
            import glob
            dxf_files = glob.glob("*.dxf") + glob.glob("../*.dxf") + glob.glob("../../*.dxf")
            
            if dxf_files:
                print("📁 Bulunan DXF dosyaları:")
                for i, f in enumerate(dxf_files, 1):
                    print(f"   {i}. {f}")
                print()
                # İlk bulunan dosyayı kullan
                dosya = dxf_files[0]
                print(f"✅ Kullanılan dosya: {dosya}\n")
            else:
                # Manuel dosya yolu (kendi dosyanızı buraya yazın)
                # Desktop'ta bulunan mimari.dxf dosyasını kullan
                dosya = r"C:\Users\USER\Desktop\mimari.dxf"
                
                # Alternatif dosya yolları:
                # dosya = r"C:\Users\USER\Desktop\Yaşar Ekersular Mimari.dxf"
                # dosya = "mimari.dxf"  # Aynı klasördeyse
                
                # Dosya var mı kontrol et
                if not os.path.exists(dosya):
                    print(f"❌ HATA: '{dosya}' dosyası bulunamadı!")
                    print("Lütfen main.py dosyasındaki 'dosya' değişkenini kendi DXF dosyanızın yolu ile güncelleyin.")
                    print("Örnek: dosya = r'C:\\Users\\USER\\Desktop\\dosya_adi.dxf'")
                    exit(1)
            
            # AYARLAR'dan değerleri kullan veya manuel ayarla
            # Çizim birimi seçimi
            # Eğer kapılar "90" veya odalar "400" gibi değerlerse "cm" yaz:
            cizim_birimi = BIRIM if DOSYA_ADI != "senin_dosyanin_adi.dxf" else "cm"
            
            # Eğer kapılar "900" ise "mm" yaz:
            # cizim_birimi = "mm"
            
            # Tolerans ayarı
            bosluk_toleransi = BOSLUK_TOLERANSI if DOSYA_ADI != "senin_dosyanin_adi.dxf" else 20
            
            # Dosya adı AYARLAR'da değiştirilmişse onu kullan
            if DOSYA_ADI != "senin_dosyanin_adi.dxf" and os.path.exists(DOSYA_ADI):
                dosya = DOSYA_ADI
            
            rapor_olustur(dosya, cizim_birimi=cizim_birimi, bosluk_toleransi=bosluk_toleransi)
        
        elif secim == "3":
            print("\n👋 Çıkılıyor...")
            sys.exit(0)
        
        else:
            print("\n❌ Geçersiz seçim! Lütfen 1, 2 veya 3 girin.")
            sys.exit(1)
