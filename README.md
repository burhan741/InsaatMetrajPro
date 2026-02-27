# İnşaat Metraj Pro  v2.0

İnşaat sektörü için profesyonel masaüstü metraj ve maliyet analiz uygulaması.
Python 3 + PyQt6 ile geliştirilmiş, tamamen **Offline-First** çalışır.

## Özellikler

### Proje Yönetimi
- ✅ **Offline-First** — İnternet bağlantısı olmadan tam verimli çalışır
- ✅ **Proje ZIP İçe/Dışa Aktarma** — `.impzip` formatıyla proje taşıma (Ctrl+E)
- ✅ **Yedekleme & Versiyonlama** — Tek tıkla yedek, geri dönebilir versiyonlar

### Metraj & Hesaplama
- ✅ **150+ İş Kalemi** — Konut yapısı için hazır poz veritabanı
- ✅ **30+ Uzman Hesaplama Aracı** — 5 kategorili gruplandırılmış menü
- ✅ **"Metraya Aktar" Entegrasyonu** — 13 hesaplama aracından tek tıkla aktarım
- ✅ **Excel Birim Fiyat Toplu Güncelleme** — Toplu fiyat güncellemesi

### AutoCAD / CAD Entegrasyonu
- ✅ **AutoCAD COM + 6 LISP Rutini** — Canlı bağlantı ile otomatik metraj
  - `DUVAR-ALAN` — Net duvar alanı (kapı/pencere menhalı)
  - `ODA-ALAN` — Oda bazlı net alan + isim okuma
  - `SUPURGELIK` — Karkas/süpürgelik uzunluğu
  - `KOLON-HACIM` — Kolon beton hacmi (enkesit × kat yüksekliği)
  - `KIRIS-HACIM` — Kiriş beton hacmi (uzunluk × b × h)
  - `KALIP-ALAN` — Kolon + Kiriş + Döşeme kalıp alanı (TS 500)
- ✅ **DXF Otomatik Metraj** — Katman eşleştirme ile ince işler metrajı

### Akıllı Özellikler
- ✅ **AI Öğrenme** — Katman bazlı duvar parametresi önerisi
- ✅ **Gerçek Zamanlı Bütçe Takibi** — Trafik ışığı (🟢/🟡/🔴) ile hedef/gerçekleşen
- ✅ **Çoklu Kat Yönetimi** — Kat bazlı ölçüm ve metraj

### Raporlama
- ✅ **Taşeron Analizi** — Teklif karşılaştırma ve PDF çıktısı
- ✅ **Gantt & İş Programı** — Görsel zaman çizelgesi
- ✅ **Mobil Puantaj** — QR kodlu saha yoklama sistemi
- ✅ **BI Dashboard** — Proje performans metrikleri
- ✅ **Modern Koyu Tema** — Kurumsal profesyonel görünüm
- ✅ **SQLite Veritabanı** — Yerel, güvenli veri saklama

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

- [ ] Online senkronizasyon
- [ ] Kullanıcı yetkilendirme sistemi
- [ ] LISP rutinleri için interaktif parametre girişi (Qt dialog → AutoCAD)
- [ ] Çoklu dil desteği (EN/TR)
- [ ] Bulut tabanlı birim fiyat veritabanı güncelleme

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
