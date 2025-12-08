# EXE Oluşturma Talimatları

## Hızlı Başlangıç

### Yöntem 1: Spec Dosyası ile (Önerilen)
```bash
EXE_OLUSTUR_SIMPLE.bat
```
Bu script `InsaatMetrajPro.spec` dosyasını kullanır ve tüm ayarları otomatik yapar.

### Yöntem 2: Manuel Komut ile
```bash
EXE_OLUSTUR.bat
```
Bu script tüm parametreleri manuel olarak belirtir.

## Gereksinimler

1. **Python 3.8+** yüklü olmalı
2. **Tüm bağımlılıklar** yüklü olmalı:
   ```bash
   pip install -r requirements.txt
   ```
3. **PyInstaller** yüklü olmalı (script otomatik yükler)

## EXE Oluşturma Adımları

1. **Proje klasörüne gidin:**
   ```bash
   cd E:\data\yeni_proje
   ```

2. **EXE oluşturma scriptini çalıştırın:**
   ```bash
   EXE_OLUSTUR_SIMPLE.bat
   ```

3. **Bekleyin:** İşlem 2-5 dakika sürebilir.

4. **EXE dosyası:** `dist\InsaatMetrajPro.exe` konumunda oluşturulur.

## EXE Dosyasını Başka Bilgisayara Taşıma

### Tek Dosya Yöntemi (OneFile)
- `dist\InsaatMetrajPro.exe` dosyasını kopyalayın
- Başka bilgisayarda çift tıklayarak çalıştırın
- **NOT:** İlk çalıştırmada Windows Defender uyarı verebilir
  - "Daha fazla bilgi" > "Yine de çalıştır" seçin

### Gerekli Dosyalar
EXE dosyası içinde şunlar paketlenir:
- ✅ Tüm Python modülleri
- ✅ PyQt6 kütüphanesi
- ✅ Veritabanı dosyaları (data klasörü)
- ✅ Assets (ikonlar, splash screen)
- ✅ App modülleri

## Sorun Giderme

### Hata: "PyInstaller bulunamadı"
```bash
pip install pyinstaller
```

### Hata: "Modül bulunamadı"
```bash
pip install -r requirements.txt
```

### EXE çalışmıyor / Hata veriyor
1. `error_log.txt` dosyasını kontrol edin
2. Konsol modunda çalıştırın (test için):
   - `InsaatMetrajPro.spec` dosyasında `console=True` yapın
   - Tekrar EXE oluşturun
   - Konsolda hata mesajlarını görün

### Windows Defender Uyarısı
Bu normaldir. EXE dosyası imzalanmamış olduğu için Windows uyarı verir.
- "Daha fazla bilgi" > "Yine de çalıştır" seçin
- Veya Windows Defender'dan istisna ekleyin

## EXE Boyutu Optimizasyonu

EXE dosyası yaklaşık **50-100 MB** olabilir. Bu normaldir çünkü:
- Python interpreter dahil
- PyQt6 kütüphanesi dahil
- Tüm bağımlılıklar dahil

Boyutu küçültmek için:
- UPX sıkıştırma aktif (spec dosyasında `upx=True`)
- Gereksiz modüller kaldırılabilir

## Test Etme

1. **Kendi bilgisayarınızda test edin:**
   ```bash
   dist\InsaatMetrajPro.exe
   ```

2. **Başka bir bilgisayarda test edin:**
   - EXE dosyasını USB ile taşıyın
   - Python yüklü olmayan bir bilgisayarda test edin
   - Tüm özelliklerin çalıştığını kontrol edin

## Notlar

- ✅ EXE dosyası Python gerektirmez
- ✅ Veritabanı ilk çalıştırmada otomatik oluşturulur
- ✅ Tüm assets (ikonlar, splash) EXE içinde paketlenir
- ⚠️ İlk çalıştırmada Windows Defender uyarı verebilir (normal)

## İletişim

Sorun yaşarsanız `error_log.txt` dosyasını kontrol edin veya geliştiriciye bildirin.




