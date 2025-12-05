# 📦 InsaatMetrajPro - EXE Kurulum Rehberi

## 🎯 Python Olmadan Çalışan Versiyon

Bu versiyon **Python yüklü olmadan** çalışır. Tek bir `.exe` dosyası veya bir klasör içinde tüm bağımlılıklarla birlikte gelir.

---

## 🔨 EXE Dosyası Oluşturma

### Yöntem 1: Tek Dosya (Önerilen - Kolay Dağıtım)

```bash
EXE_OLUSTUR.bat
```

**Sonuç:**
- `dist\InsaatMetrajPro.exe` - Tek dosya, tüm bağımlılıklar içinde
- **Avantaj:** Tek dosya, kolay paylaşım
- **Dezavantaj:** İlk açılış biraz yavaş olabilir (~2-3 saniye)

### Yöntem 2: Klasör Yapısı (Önerilen - Hızlı Başlatma)

```bash
EXE_OLUSTUR_GELISMIS.bat
```

**Sonuç:**
- `dist\InsaatMetrajPro\` klasörü
- `InsaatMetrajPro.exe` + tüm bağımlılıklar
- **Avantaj:** Daha hızlı başlatma, daha küçük ana dosya
- **Dezavantaj:** Tüm klasörü kopyalamanız gerekir

---

## 📋 Gereksinimler (Sadece EXE Oluştururken)

EXE oluşturmak için **sadece geliştirici bilgisayarında** gerekli:

- Python 3.8+
- pip
- PyInstaller (otomatik yüklenir)

**Not:** EXE'yi kullanan kullanıcılarda Python gerekmez!

---

## 🚀 Kullanıcılar İçin Kurulum

### Adım 1: EXE Dosyasını İndirin

- **Tek dosya versiyonu:** `InsaatMetrajPro.exe`
- **Klasör versiyonu:** `InsaatMetrajPro` klasörünün tamamı

### Adım 2: Çalıştırın

- **Tek dosya:** `InsaatMetrajPro.exe` dosyasına çift tıklayın
- **Klasör:** `InsaatMetrajPro.exe` dosyasına çift tıklayın

**Bu kadar!** Python yüklemenize gerek yok!

---

## 📦 Dağıtım Paketi Hazırlama

### Tek Dosya Versiyonu İçin:

1. `dist\InsaatMetrajPro.exe` dosyasını alın
2. ZIP yapın veya direkt gönderin
3. Kullanıcılar çift tıklayarak çalıştırır

### Klasör Versiyonu İçin:

1. `dist\InsaatMetrajPro` klasörünün tamamını ZIP yapın
2. Kullanıcılar ZIP'i açıp `InsaatMetrajPro.exe` dosyasını çalıştırır

---

## ⚙️ PyInstaller Ayarları

### Mevcut Ayarlar:

- `--onefile`: Tek dosya oluştur (Yöntem 1)
- `--windowed`: Konsol penceresi gösterme
- `--add-data "app;app"`: app klasörünü ekle
- `--hidden-import`: Gerekli modülleri ekle
- `--collect-all=PyQt6`: PyQt6 bağımlılıklarını topla

### Özelleştirme:

`EXE_OLUSTUR.bat` dosyasını düzenleyerek:
- İkon ekleyebilirsiniz: `--icon=icon.ico`
- Versiyon bilgisi ekleyebilirsiniz: `--version-file=version.txt`
- Daha fazla gizli modül ekleyebilirsiniz

---

## 🐛 Sorun Giderme

### "Windows protected your PC" Uyarısı

**Çözüm:**
- "More info" tıklayın
- "Run anyway" seçin
- Bu, imzalanmamış yazılım uyarısıdır (normal)

### EXE Açılmıyor

**Kontrol:**
1. Antivirus yazılımı engelliyor olabilir
2. Windows Defender'ı kontrol edin
3. EXE'yi "Güvenli" klasöre koyun

### "ModuleNotFoundError" Hatası

**Çözüm:**
- `--hidden-import` ile eksik modülü ekleyin
- `EXE_OLUSTUR.bat` dosyasını güncelleyin
- Yeniden derleyin

### EXE Çok Büyük

**Çözüm:**
- Klasör versiyonunu kullanın (daha küçük)
- Gereksiz modülleri kaldırın
- UPX sıkıştırma kullanın (ileri seviye)

---

## 📊 Dosya Boyutları

### Tek Dosya Versiyonu:
- **Beklenen boyut:** ~80-120 MB
- **İçerik:** Tüm Python, PyQt6, pandas, vb.

### Klasör Versiyonu:
- **Ana EXE:** ~5-10 MB
- **Toplam klasör:** ~80-120 MB
- **Avantaj:** Daha hızlı başlatma

---

## 🎁 Test Paketi ile Birleştirme

EXE'yi test paketi ile birleştirebilirsiniz:

1. EXE oluşturun
2. `PAKET_HAZIRLA.bat` çalıştırın
3. EXE'yi test paketine ekleyin
4. Kullanıcılara hem EXE hem de kaynak kod gönderin

---

## ✅ Öneriler

1. **İlk test:** Klasör versiyonunu kullanın (daha hızlı)
2. **Dağıtım:** Tek dosya versiyonunu kullanın (kolay)
3. **Güncelleme:** Versiyon numarası ekleyin
4. **İkon:** Uygulama ikonu ekleyin
5. **İmzalama:** İleride dijital imza ekleyin (profesyonel)

---

## 📝 Notlar

- EXE oluşturma sadece **Windows** için çalışır
- Linux/Mac için farklı yöntemler gerekir
- İlk derleme 2-5 dakika sürebilir
- Sonraki derlemeler daha hızlıdır (cache sayesinde)

---

**Hazırlayan:** Geliştirici  
**Tarih:** 2024  
**Versiyon:** 1.0



