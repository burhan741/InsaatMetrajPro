import pandas as pd
from app.core.dxf_engine import DXFAnaliz
import os


def rapor_olustur(dxf_dosya_adi):
    print(f"🔄 '{dxf_dosya_adi}' dosyası analiz ediliyor...")
    
    # 1. Motoru Başlat
    try:
        proje = DXFAnaliz(dxf_dosya_adi)
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
    # Buraya kendi dosya adını yazmayı unutma!
    dosya = "mimari.dxf"
    rapor_olustur(dosya)
