# InsaatMetrajPro - Kurulum ve Aktarım Rehberi

## 📦 Başka Bilgisayara Aktarma

### 1. Aktarılması Gereken Dosyalar

Aşağıdaki dosya ve klasörleri **ZIP** olarak sıkıştırıp başka bilgisayara aktarın:

```
yeni_proje/
├── app/                    # Tüm uygulama klasörü (__pycache__ hariç)
│   ├── core/
│   ├── data/
│   ├── ui/
│   └── utils/
├── main.py                 # Ana başlatma dosyası
├── requirements.txt        # Python kütüphaneleri listesi
├── InsaatMetrajPro.bat     # Windows başlatma scripti (opsiyonel)
└── README.md              # Dokümantasyon (varsa)
```

### 2. Aktarılmaması Gereken Dosyalar

Bu dosyaları **AKTARMAYIN** (yeni bilgisayarda otomatik oluşturulacak):

- `__pycache__/` klasörleri (Python cache)
- `data/insaat_metraj.db` (veritabanı - yeni bilgisayarda yeniden oluşturulacak)
- `.xlsx` dosyaları (geçici raporlar)
- `.git/` klasörü (versiyon kontrolü - opsiyonel)

---

## 🖥️ Yeni Bilgisayarda Kurulum

### Adım 1: Python Kurulumu

1. Python 3.8 veya üzeri sürümünü indirin: https://www.python.org/downloads/
2. Kurulum sırasında **"Add Python to PATH"** seçeneğini işaretleyin
3. Kurulumu tamamlayın

### Adım 2: Proje Dosyalarını Kopyalama

1. ZIP dosyasını açın
2. Proje klasörünü istediğiniz yere kopyalayın (örn: `C:\InsaatMetrajPro\`)

### Adım 3: Python Kütüphanelerini Yükleme

**Komut İstemi (CMD)** veya **PowerShell**'i açın ve proje klasörüne gidin:

```bash
cd C:\InsaatMetrajPro
```

Sonra şu komutu çalıştırın:

```bash
pip install -r requirements.txt
```

Bu komut şu kütüphaneleri yükleyecek:
- PyQt6 (GUI arayüzü)
- pandas (Excel işlemleri)
- openpyxl (Excel dosya formatı)
- reportlab (PDF oluşturma)
- ezdxf (DXF dosya işleme - opsiyonel)

### Adım 4: Uygulamayı Başlatma

#### Yöntem 1: Python ile (Önerilen)

Komut İstemi'nde:

```bash
python main.py
```

#### Yöntem 2: Batch Dosyası ile (Windows)

`InsaatMetrajPro.bat` dosyasına çift tıklayın.

---

## ✅ İlk Kullanım

1. Uygulama açıldığında **splash screen** görünecek
2. Veritabanı otomatik oluşturulacak
3. Pozlar ve malzeme formülleri yüklenmek istenirse **"Evet"** deyin
4. İlk projenizi oluşturarak başlayın!

---

## 🔧 Sorun Giderme

### "ModuleNotFoundError" Hatası

Eksik kütüphane hatası alırsanız:

```bash
pip install PyQt6 pandas openpyxl reportlab ezdxf
```

### Veritabanı Hatası

Eğer veritabanı hatası alırsanız:
- `data/` klasörünün yazma izni olduğundan emin olun
- Uygulamayı yönetici olarak çalıştırmayı deneyin

### Python Bulunamadı Hatası

- Python'un PATH'e eklendiğinden emin olun
- `python --version` komutu ile Python'un kurulu olduğunu kontrol edin

---

## 📝 Notlar

- **Veritabanı**: İlk açılışta `data/insaat_metraj.db` dosyası otomatik oluşturulur
- **Pozlar**: İlk açılışta pozlar yüklenmek istenirse 150+ poz otomatik yüklenir
- **Malzemeler**: Malzeme formülleri otomatik yüklenir
- **Projeler**: Projeleriniz veritabanında saklanır, yedek almak için `data/insaat_metraj.db` dosyasını kopyalayın

---

## 💾 Yedekleme

Projelerinizi yedeklemek için:

1. `data/insaat_metraj.db` dosyasını kopyalayın
2. Bu dosyayı güvenli bir yere kaydedin
3. Başka bilgisayara aktarırken bu dosyayı da kopyalayın (mevcut projeleriniz korunur)

---

## 📞 Destek

Sorun yaşarsanız:
1. Hata mesajını not edin
2. Python sürümünü kontrol edin: `python --version`
3. Kütüphanelerin yüklü olduğunu kontrol edin: `pip list`

