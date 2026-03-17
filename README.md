# İnşaat Metraj Pro  v2.0

İnşaat sektörü için profesyonel masaüstü metraj ve maliyet analiz uygulaması.
Python 3 + PyQt6 ile geliştirilmiş, tamamen **Offline-First** çalışır.

## Özellikler

### İSTATÜ: ÇALIŞAN MODÜLLER (v2.0 Stabilizasyon)

**✅ OPERATIONAL (Tam Fonksiyonel)**
- **Veritabanı Katmanı** — DatabaseManager 45 metod, 9 tablo, tüm CRUD işlemleri aktif
- **Ana Pencere (MainWindow)** — GUI başlanıyor, TabWidget + 7 pencere sınıfı
- **Duvar, Alçı, Fayans, Elektrik, Sap, Parke, Kaba Yapı Hesaplamaları** — init_ui() fixed
- **Saha Demiri Calculator** — Yeni pencere oluşturuldu (296 satır)

**⚠️ FALLBACK (Minimal Stub Modülleri ile - sınırlı işlevsellik)**
- **calculator_minimal.py** — Hesaplama motoru stub (69 satır) - matematiksel fonksiyonlar test için hazır
- **data_loader_minimal.py** — Veri yükleyici stub (55 satır) - pozlar/malzemeler kontrol fonsiyonları
- **dialogs_minimal.py** — Diyalog stub (27 satır) - MetrajItemDialog ve TaseronOfferDialog template

**OTEL: ETKINLEŞTIRILDI - Try/Except fallback mekanizması - gerçek modüllere erişim yoktur, minimal versiyonlar kullanılır**

### Proje Yönetimi
- ✅ **Offline-First** — İnternet bağlantısı olmadan tam verimli çalışır
- ✅ **Proje ZIP İçe/Dışa Aktarma** — `.impzip` formatıyla proje taşıma (Ctrl+E)
- ✅ **Yedekleme & Versiyonlama** — Tek tıkla yedek, geri dönebilir versiyonlar

### Metraj & Hesaplama
- ✅ **150+ İş Kalemi** — Konut yapısı için hazır poz veritabanı (DatabaseManager operasyonel)
- ⚠️ **30+ Uzman Hesaplama Aracı** — 5 kategorili menü (hesaplama motoru minimal versiyonda)
- ⚠️ **"Metraya Aktar" Entegrasyonu** — 13 aracı stub versiyonu
- ✅ **Excel Birim Fiyat Toplu Güncelleme** — Veritabanı destekler

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

## Veritabanı Mimarisi

### DatabaseManager (app.core.database)

SQLite veritabanı işlemleri merkezi yönetim sınıfı **45 metod** ile bütün CRUD ve domain-specific işlemleri yönetir.

#### Tablo Yapısı

| Tablo | Amaç | Ana Sütunlar |
|-------|------|--------------|
| **projects** | Proje bilgileri | id, ad, aciklama, durum, toplam_maliyet |
| **tedarikcilar** | Taşeron/Tedarikçi veri | id, ad, telefon, email, adres |
| **sablonlar** | Metraj şablonları | id, ad, aciklama, olusturma_tarihi |
| **sablon_kalemleri** | Şablona bağlı kalemler | id, sablon_id, poz_no, tanim, kategori |
| **ayarlar** | Uygulama ayarları (key-value) | id, anahtar, deger |
| **ihaleler** | İhale/Teklifler | id, ad, aciklama, durum |
| **ihale_kalemleri** | İhale alt kalemleri | id, ihale_id, poz_no, birim_fiyat |
| **birim_fiyatlar** | Bütçe birim fiyatları | id, poz_no, birim_fiyat, tarih, kaynak |
| **pozlar** | İş kalem veritabanı | id, poz_no, tanim, birim, resmi_fiyat |

#### Metodlar (45 Toplam)

- **Genel CRUD (6):** execute, execute_single, insert, update, delete, get_connection
- **Proje Yönetimi (5):** get_all_projects, get_project, create_project, update_project, delete_project
- **Tedarikçi Yönetimi (5):** get_tedarikci_listesi, get_tedarikci, create_tedarikci, update_tedarikci, delete_tedarikci
- **Ayarlar (4):** get_ayar, set_ayar, get_tum_ayarlar, delete_ayar
- **İhale Yönetimi (8):** get_all_ihaleler, get_ihale, create_ihale, update_ihale, delete_ihale, get_ihale_kalemleri, add_ihale_kalemi, delete_ihale_kalemi
- **Birim Fiyat (7):** get_all_birim_fiyatlar, get_birim_fiyat, create_birim_fiyat, update_birim_fiyat, delete_birim_fiyat, get_poz_birim_fiyatlar, deaktif_et_birim_fiyat
- **Şablon Yönetimi (10):** get_all_templates, get_template, create_template, update_template, delete_template, get_template_items, get_template_kalemleri, add_template_kalemi, update_template_kalemi, delete_template_kalemi

### Optimizasyonlar

- **WAL Mode:** Eşzamanlı okuma-yazma
- **Foreign Keys:** Referans bütünlüğü
- **Indexes:** Hızlı sorgular
- **PRAGMA:** İyileştirmelmiş ayarlar (journal mode, cache size, synchronous)

