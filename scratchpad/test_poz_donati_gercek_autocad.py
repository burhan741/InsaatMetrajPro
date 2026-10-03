"""AŞAMA 1+2 — GERÇEK AutoCAD ile tek seferlik doğrulama betiği.

Bu betik henüz programın (main.py) bir parçası DEĞİL — UI'ya buton
eklenmeden önce, get_poz_bazli_donati_tablosu()'nu gerçek AutoCAD
çiziminizle deneyip hem ham ızgarayı hem de poz/adet/çap/boy önizlemesini
gözle doğrulamanız için yazıldı.

AŞAMA 1 daha önce bu betikle doğrulandı (21 satır x 8 sütun, "doğru"
onaylandı — bkz. CLAUDE.md Rev-128). Bu güncelleme AŞAMA 2'yi (başlık
tespiti + sütun→alan eşleme + çap normalizasyonu) da konsola ekliyor.

Nasıl çalıştırılır:
    1) AutoCAD'i açın, "Poza Göre Donatı Metraj Tablosu"nun göründüğü
       çizimi açık tutun.
    2) Bu terminalde (tek satır halinde) çalıştırın:
       & "E:\İNŞAAT METRAJ PRO\.venv\Scripts\python.exe" "E:\İNŞAAT METRAJ PRO\yeni_proje\scratchpad\test_poz_donati_gercek_autocad.py"
    3) AutoCAD öne gelecek, tabloyu KUTU ÇİZEREK (başlık satırı dahil)
       seçin, ENTER'a basın.
    4) Konsolda sırasıyla şunlar çıkacak:
       a) Satır satır ham ızgara (Aşama 1 — zaten doğrulandı)
       b) "SÜTUN TESPİTİ: OTOMATIK/MANUEL/BASARISIZ"
       c) Sütun→alan eşlemesi ve çap-bazlı toplam sütunları
       d) Her poz için "Poz X: N adet ØÇ x Bm  [tablo: Ø..=...]" önizlemesi

    Kontrol edilecekler:
       - SÜTUN TESPİTİ "OTOMATIK" mi çıktı (başlık doğru tanındı mı)?
       - Her pozun adet/çap/boy değeri AutoCAD'deki tabloyla birebir aynı mı?
       - "tablo:" kısmındaki değer (tablodaki hazır TOPLAM sütunu) her poz
         için AutoCAD'deki ilgili hücreyle eşleşiyor mu?
       - "BELİRSİZ toplam sütunu" uyarısı çıkarsa, o sütunda gerçekten
         birden fazla farklı çap mı var (veri hatası) yoksa algoritma mı
         yanılıyor — bize bildirin.

    "SÜTUN TESPİTİ: BASARISIZ" çıkarsa (başlık satırı tanınamadı — örn.
    tablonuzda "POZ"/"ADET"/"ÇAP"/"BOY" yerine farklı kelimeler var):
    aşağıdaki SUTUN_SIRASI listesini gerçek sütun sırasına göre doldurup
    (soldan sağa, her sütun için 'poz'|'adet'|'cap'|'boy'|'sekil'|'toplam'|
    'yoksay') tekrar deneyin.

    Yanlış satır/sütun BÖLÜNMESİ olursa (Aşama 1 sorunu, sütun eşleme
    değil): KUMELEME_X_ESIK / KUMELEME_Y_ESIK değerlerini elle bir sayı
    ile doldurun (bkz. CLAUDE.md Rev-128 "BİLİNEN SINIR").
"""
import os
import sys

os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Yanlis satir/sutun BOLUNMESI olursa bir sayi girin (ornek: 40.0).
KUMELEME_X_ESIK = None
KUMELEME_Y_ESIK = None

# "SUTUN TESPITI: BASARISIZ" cikarsa doldurun, orn:
# SUTUN_SIRASI = ["poz","adet","cap","boy","sekil","toplam","toplam","toplam"]
SUTUN_SIRASI = None


def main():
    from app.core.autocad_connector import AutoCADConnector

    connector = AutoCADConnector()

    print(">>> AutoCAD'e bağlanılıyor...")
    connector.baglan()
    print(">>> Bağlandı. Şimdi AutoCAD penceresine geçip tabloyu kutu ile seçin.\n")

    rapor = connector.get_poz_bazli_donati_tablosu(
        x_esik=KUMELEME_X_ESIK,
        y_esik=KUMELEME_Y_ESIK,
        sutun_sirasi=SUTUN_SIRASI,
    )

    print("\n>>> ÖZET:")
    print(f"    Seçim sayısı   : {rapor['secim_sayisi']}")
    print(f"    Metin sayısı   : {rapor['metin_sayisi']}")
    print(f"    Grid boyutu    : {len(rapor['grid'])} satır x "
          f"{len(rapor['grid'][0]) if rapor['grid'] else 0} sütun")
    pk = rapor.get("poz_kayitlari", {})
    print(f"    Sütun tespiti  : {pk.get('sutun_tespiti')}")
    print(f"    Bulunan poz    : {len(pk.get('basarili', []))}")

    print("\n>>> Bitti. Konsoldaki 'ÖNİZLEME' listesi AutoCAD'deki tabloyla eşleşiyor mu kontrol edin.")


if __name__ == "__main__":
    main()
