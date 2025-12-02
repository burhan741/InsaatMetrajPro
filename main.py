import pandas as pd
from app.core.dxf_engine import DXFAnaliz
import os
import sys
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont
from app.ui.main_window import MainWindow
from app.ui.styles import apply_dark_theme

# --- AYARLAR ---
DOSYA_ADI = "senin_dosyanin_adi.dxf"  # <-- Dosya adını buraya yaz
BIRIM = "cm"                           # Projenin birimi
BOSLUK_TOLERANSI = 20                  # CM olduğu için 20 yazdık (20 cm boşlukları kapatır)


def gui_uygulamasi():
    """PyQt6 GUI uygulamasını başlat"""
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("InsaatMetrajPro")
        app.setOrganizationName("InsaatMetrajPro")
        
        # Splash screen oluştur
        splash = QSplashScreen()
        splash.setStyleSheet("""
            QSplashScreen {
                background-color: #1a1a2e;
                color: white;
            }
        """)
        splash.showMessage(
            "InsaatMetrajPro Yükleniyor...",
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
            Qt.GlobalColor.white
        )
        splash.show()
        app.processEvents()  # UI'ı güncelle
        
        apply_dark_theme(app)
        
        # Ana pencereyi oluştur (optimizasyonlar sayesinde hızlı)
        window = MainWindow()
        
        # Splash screen'i kapat
        splash.finish(window)
        window.show()
        
        sys.exit(app.exec())
    except Exception as e:
        print(f"HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def rapor_olustur(dxf_dosya_adi=None, cizim_birimi=None, bosluk_toleransi=None):
    """
    DXF analiz raporu oluşturur.
    
    Args:
        dxf_dosya_adi: DXF dosya yolu (None ise AYARLAR'dan alınır)
        cizim_birimi: Çizim birimi (None ise AYARLAR'dan alınır)
        bosluk_toleransi: Boşluk toleransı (None ise AYARLAR'dan alınır)
    """
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
