import pandas as pd
from app.core.dxf_engine import DXFAnaliz
import os
import sys
from PyQt6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.ui.styles import apply_dark_theme


def gui_uygulamasi():
    """PyQt6 GUI uygulamasını başlat"""
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("InsaatMetrajPro")
        app.setOrganizationName("InsaatMetrajPro")
        
        apply_dark_theme(app)
        
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec())
    except Exception as e:
        print(f"HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def rapor_olustur(dxf_dosya_adi, cizim_birimi="cm"):
    print(f"🔄 '{dxf_dosya_adi}' dosyası analiz ediliyor...")
    print(f"📏 Çizim birimi: {cizim_birimi}\n")
    
    # 1. Motoru Başlat
    try:
        # Eğer kapılar "90" veya odalar "400" gibi değerlerse "cm" yaz:
        proje = DXFAnaliz(dxf_dosya_adi, cizim_birimi=cizim_birimi)
        
        # Eğer kapılar "900" ise "mm" yaz:
        # proje = DXFAnaliz(dxf_dosya_adi, cizim_birimi="mm")
    except SystemExit:
        print("İşlem durduruldu.")
        return
    
    # 2. Tüm Katmanları Çek
    katmanlar = proje.katmanlari_listele()
    print(f"📂 Toplam {len(katmanlar)} katman bulundu. Hesaplama başlıyor...\n")
    
    metraj_verileri = []
    
    # 3. Her katman için döngüye gir
    for katman in katmanlar:
        # Alan hesabı dene
        sonuc_alan = proje.alan_hesapla(katman)
        
        # Eğer o katmanda çizim varsa (Alan > 0) listeye ekle
        if "toplam_miktar" in sonuc_alan and sonuc_alan["toplam_miktar"] > 0:
            metraj_verileri.append({
                "Katman Adı": katman,
                "İşlem Türü": "Alan (m²)",
                "Miktar": sonuc_alan["toplam_miktar"],
                "Parça Sayısı": sonuc_alan["parca_sayisi"]
            })
            print(f"   ✅ {katman}: {sonuc_alan['toplam_miktar']} m²")
    
        # Blok/Adet sayımı da eklenebilir (Şimdilik sadece alan odaklıyız)
    
    # 4. Verileri Excel'e Aktar (Pandas ile)
    if metraj_verileri:
        df = pd.DataFrame(metraj_verileri)
        
        # Excel dosya adı
        excel_adi = "metraj_raporu.xlsx"
        
        # Eğer dosya açıksan hata verir, onu engellemek için try-except
        try:
            df.to_excel(excel_adi, index=False)
            print(f"\n🎉 BAŞARILI! Rapor oluşturuldu: {os.path.abspath(excel_adi)}")
            print("Klasöründeki 'metraj_raporu.xlsx' dosyasını açıp inceleyebilirsin.")
        except PermissionError:
            print(f"\n❌ HATA: '{excel_adi}' dosyası şu an açık! Lütfen Excel'i kapatıp tekrar dene.")
    else:
        print("\n⚠️ Uyarı: Hesaplanacak kapalı alan bulunamadı (Çizgiler birleşmemiş olabilir).")


# --- ÇALIŞTIR ---
if __name__ == "__main__":
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
        
        # Çizim birimi seçimi
        # Eğer kapılar "90" veya odalar "400" gibi değerlerse "cm" yaz:
        cizim_birimi = "cm"
        
        # Eğer kapılar "900" ise "mm" yaz:
        # cizim_birimi = "mm"
        
        rapor_olustur(dosya, cizim_birimi=cizim_birimi)
    
    elif secim == "3":
        print("\n👋 Çıkılıyor...")
        sys.exit(0)
    
    else:
        print("\n❌ Geçersiz seçim! Lütfen 1, 2 veya 3 girin.")
        sys.exit(1)
