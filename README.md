# InsaatMetrajPro

İnşaat sektörü için profesyonel masaüstü metraj uygulaması.

## Özellikler

- ✅ **Offline-First** yaklaşım - İnternet bağlantısı olmadan çalışır
- ✅ **Proje Yönetimi** - Birden fazla proje yönetimi
- ✅ **Metraj Cetveli** - Detaylı metraj kalemleri takibi
- ✅ **CAD Entegrasyonu** - DXF dosyalarından otomatik metraj çıkarma
- ✅ **Taşeron Analizi** - Taşeron tekliflerini karşılaştırma
- ✅ **Modern Arayüz** - Koyu kurumsal tema ile profesyonel görünüm
- ✅ **SQLite Veritabanı** - Yerel veri saklama

## Teknoloji Yığını

- **Python 3.8+**
- **PyQt6** - Modern GUI framework
- **SQLite** - Yerel veritabanı
- **ezdxf** - DXF dosya işleme
- **Pandas** - Veri işleme (Excel, tablo işlemleri)

## Kurulum

### Gereksinimler

- Python 3.8 veya üzeri
- pip (Python paket yöneticisi)

### Adımlar

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

2. Uygulamayı çalıştırın:
```bash
python main.py
```

## Proje Yapısı

```
yeni_proje/
├── main.py                 # Ana giriş noktası
├── app/
│   ├── core/              # Core modüller
│   │   ├── database.py    # Veritabanı yöneticisi
│   │   ├── cad_manager.py # CAD dosya işlemleri
│   │   └── calculator.py  # Hesaplama motoru
│   ├── ui/                # Kullanıcı arayüzü
│   │   ├── main_window.py # Ana pencere
│   │   └── styles.py      # QSS stilleri
│   ├── models/            # Veri modelleri
│   └── utils/             # Yardımcı fonksiyonlar
│       └── helpers.py
├── data/                  # Veritabanı dosyaları (otomatik oluşturulur)
├── requirements.txt       # Python bağımlılıkları
└── README.md             # Bu dosya
```

## Kullanım

### Yeni Proje Oluşturma

1. Sol panelde "Yeni Proje" butonuna tıklayın
2. Proje adını girin
3. Proje ağacında görünecektir

### Metraj Kalemi Ekleme

1. Bir proje seçin
2. "Metraj Cetveli" sekmesine gidin
3. "Kalem Ekle" butonuna tıklayın (yakında eklenecek)

### CAD Dosyası İşleme

1. "CAD İşleyici" sekmesine gidin
2. "Dosya Seç" butonuna tıklayın
3. DXF dosyasını seçin
4. "DXF Dosyasını Analiz Et" butonuna tıklayın
5. Bulunan kalemleri projeye ekleyebilirsiniz

### Taşeron Analizi

1. "Taşeron Analizi" sekmesine gidin
2. "Teklif Ekle" ile teklifleri ekleyin
3. "Karşılaştır" ile teklifleri karşılaştırın

## Veritabanı Yapısı

### Tablolar

- **projects** - Proje bilgileri
- **pozlar** - Çevre ve Şehircilik pozları
- **metraj_kalemleri** - Metraj kalemleri
- **taseron_teklifleri** - Taşeron teklifleri

## Geliştirme Notları

- Tüm kodlar **Type Hints** ve **Docstrings** ile yazılmıştır
- **Offline-First** yaklaşım ile çalışır
- İleride online senkronizasyon için genişletilebilir yapı
- Modern **best-practices** kullanılmıştır

## Gelecek Özellikler

- [ ] Kalem ekleme/düzenleme dialog pencereleri
- [ ] Excel import/export
- [ ] PDF rapor oluşturma
- [ ] Birim fiyat listesi yönetimi
- [ ] Online senkronizasyon
- [ ] Kullanıcı yetkilendirme
- [ ] Gelişmiş CAD analizi

## Lisans

Bu proje eğitim ve ticari kullanım için geliştirilmiştir.

## 🧪 Test Kullanıcıları İçin

Bu uygulama test aşamasındadır. Test etmek ve geri bildirim vermek isterseniz:

1. **PAKET_HAZIRLA.bat** dosyasını çalıştırarak test paketini hazırlayın
2. **TEST_KULLANICILARI_ICIN.md** dosyasını okuyun
3. **GERI_BILDIRIM_FORMU.txt** dosyasını doldurarak geri bildirim gönderin

### Test Paketi Hazırlama

```bash
PAKET_HAZIRLA.bat
```

Bu script, test kullanıcılarına gönderilecek hazır paketi oluşturur.

## Destek

Sorularınız için issue açabilir veya iletişime geçebilirsiniz.
