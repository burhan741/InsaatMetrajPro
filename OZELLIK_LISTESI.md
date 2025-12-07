# 📋 İnşaat Metraj Pro - Özellik Listesi

## ✅ MEVCUT ÖZELLİKLER

### 🏗️ Proje Yönetimi
- ✅ Çoklu proje yönetimi (proje ağacı)
- ✅ Proje oluşturma, silme, düzenleme
- ✅ Proje notları ekleme/düzenleme
- ✅ Proje durumu takibi (aktif/pasif)
- ✅ Proje özeti sekmesi (toplam maliyet, kalem sayısı, kategori dağılımı)
- ✅ Proje özeti PDF/Excel export

### 📊 Metraj Cetveli
- ✅ Metraj kalemi ekleme/düzenleme/silme
- ✅ Poz numarası ile otomatik poz bilgisi getirme
- ✅ Birim fiyat otomatik hesaplama
- ✅ Toplam değer hesaplama (miktar × birim fiyat)
- ✅ Kategori bazlı filtreleme
- ✅ Excel'den toplu kalem import
- ✅ Excel export
- ✅ Metraj kalemlerine not ekleme

### 💼 Taşeron Analizi
- ✅ Taşeron teklifi ekleme/düzenleme/silme
- ✅ Teklif karşılaştırma tablosu
- ✅ En düşük/yüksek teklif gösterimi
- ✅ Excel export
- ✅ PDF export

### 📦 Malzeme Listesi
- ✅ Otomatik malzeme hesaplama (poz bazlı)
- ✅ Fire oranı hesaplama (standart/özel)
- ✅ Malzeme formülleri ile hesaplama
- ✅ Malzeme listesi Excel export
- ✅ Malzeme listesi PDF export
- ✅ Tedarikçi formatında export

### 📋 Şablonlar
- ✅ Proje şablonu oluşturma
- ✅ Şablon kalemleri ekleme/düzenleme
- ✅ Şablondan proje oluşturma
- ✅ Şablon silme

### 💰 Birim Fiyat Yönetimi
- ✅ Birim fiyat ekleme/düzenleme
- ✅ Tarihli fiyat takibi
- ✅ Aktif/pasif fiyat yönetimi
- ✅ Poz bazlı fiyat listesi
- ✅ PDF'den birim fiyat import (Çevre ve Şehircilik Bakanlığı formatı)

### 📄 İhale Dosyası Hazırlama
- ✅ İhale oluşturma/yönetme
- ✅ İhale kalemleri ekleme (poz seçimi ile)
- ✅ Birim miktar ve birim düzenlenebilir
- ✅ Toplam bedel otomatik hesaplama
- ✅ Tanım (açıklama) tam görüntüleme ve düzenleme
- ✅ İhale dosyası PDF export (Türkçe karakter desteği)
- ✅ İhale dosyası Excel export
- ✅ Excel'den ihale kalemleri import

### 🗄️ Veritabanı
- ✅ SQLite veritabanı (offline-first)
- ✅ Pozlar tablosu (Çevre ve Şehircilik Bakanlığı verileri)
- ✅ Birim fiyatlar tablosu (tarihli takip)
- ✅ Projeler, metraj kalemleri, taşeron teklifleri
- ✅ İhale ve ihale kalemleri tabloları
- ✅ Şablonlar ve şablon kalemleri

### 🎨 Kullanıcı Arayüzü
- ✅ Modern koyu tema (wireframe şehir arka planı)
- ✅ Sekme bazlı navigasyon (lazy loading)
- ✅ Responsive tablo görünümleri
- ✅ Türkçe karakter desteği
- ✅ Uygulama ikonu ve logo
- ✅ Splash screen

### 🔧 Teknik Özellikler
- ✅ Hot reload (development modunda otomatik yeniden başlatma)
- ✅ Global exception handler (hata yakalama ve loglama)
- ✅ Async veri yükleme (UI bloklamadan)
- ✅ Lazy loading (performans optimizasyonu)
- ✅ Type hints ve docstrings
- ✅ Git versiyon kontrolü

### 📤 Export/Import
- ✅ Excel export (metraj, taşeron, proje özeti, ihale, malzeme)
- ✅ PDF export (metraj, taşeron, proje özeti, ihale, malzeme)
- ✅ Excel import (metraj kalemleri, ihale kalemleri)
- ✅ PDF import (birim fiyatlar - Çevre ve Şehircilik Bakanlığı)

---

## 🚀 EKLENEBİLECEK ÖZELLİKLER

### 🔍 Arama ve Filtreleme (Öncelik: Yüksek)
- [ ] Global arama çubuğu (projeler, kalemler, pozlar)
- [ ] Gelişmiş filtreleme (tarih aralığı, kategori, fiyat aralığı)
- [ ] Hızlı arama kısayolları (Ctrl+F)
- [ ] Arama geçmişi
- [ ] Poz numarası ile hızlı arama

### 📊 Görselleştirme ve Raporlama (Öncelik: Orta)
- [ ] Kategori bazında pie chart (maliyet dağılımı)
- [ ] Bar chart (en pahalı kalemler)
- [ ] Zaman bazlı maliyet grafikleri
- [ ] Proje karşılaştırma grafikleri
- [ ] Dashboard görünümü (ana ekran özeti)

### 💾 Yedekleme ve Versiyonlama (Öncelik: Yüksek)
- [ ] Tek tıkla proje yedekleme
- [ ] Yedekten geri yükleme
- [ ] Otomatik yedekleme (günlük/haftalık)
- [ ] Proje versiyonlama (snapshot)
- [ ] Versiyon geri alma
- [ ] Yedek dosyası şifreleme

### 💰 KDV ve Vergi Hesaplamaları (Öncelik: Orta)
- [ ] KDV oranı seçimi (%1, %10, %20)
- [ ] KDV dahil/hariç görünüm
- [ ] KDV raporu export
- [ ] Stopaj hesaplama
- [ ] İndirim/artırım oranları

### 📅 Takvim ve İş Programı (Öncelik: Düşük)
- [ ] Proje başlangıç/bitiş tarihleri
- [ ] Milestone (kilometre taşı) takibi
- [ ] Takvim görünümü
- [ ] Hatırlatıcılar
- [ ] Gantt chart (basit)

### 🔄 Senkronizasyon (Öncelik: Düşük - İleri Seviye)
- [ ] Cloud senkronizasyon (Google Drive, Dropbox)
- [ ] Çoklu cihaz desteği
- [ ] Çevrimdışı çalışma desteği
- [ ] Çakışma çözümleme

### 👥 Kullanıcı Yönetimi (Öncelik: Düşük - İleri Seviye)
- [ ] Kullanıcı girişi
- [ ] Rol yönetimi (admin, kullanıcı, görüntüleyici)
- [ ] Proje bazında yetkilendirme
- [ ] Aktivite logları (kim ne yaptı)

### 📱 Mobil/Web Erişimi (Öncelik: Çok Düşük - İleri Seviye)
- [ ] Web arayüzü (Flask/FastAPI)
- [ ] Mobil uygulama (React Native/Flutter)
- [ ] API endpoint'leri

### 🎯 Gelişmiş Hesaplamalar (Öncelik: Orta)
- [ ] Birim dönüşümleri (m² → m³, kg → ton)
- [ ] Fire oranı otomatik hesaplama (kategori bazlı)
- [ ] İndirim/artırım yüzdesi
- [ ] Toplu fiyat güncelleme
- [ ] Fiyat karşılaştırması (tarihsel)

### 📋 Rapor Şablonları (Öncelik: Orta)
- [ ] Özel PDF şablonları
- [ ] Logo ekleme (PDF'de)
- [ ] Firma bilgileri şablonu
- [ ] İmza alanı
- [ ] Sayfa numaralandırma ve başlık/alt bilgi

### 🔔 Bildirimler ve Hatırlatıcılar (Öncelik: Düşük)
- [ ] Proje bitiş tarihi hatırlatıcıları
- [ ] Fiyat güncelleme bildirimleri
- [ ] Yedekleme hatırlatıcıları
- [ ] Sistem bildirimleri (Windows)

### 📈 İstatistikler ve Analiz (Öncelik: Orta)
- [ ] Proje bazında detaylı istatistikler
- [ ] Ortalama birim fiyat analizi
- [ ] Kategori bazında maliyet trendleri
- [ ] Karşılaştırmalı analiz (projeler arası)
- [ ] Export edilebilir istatistik raporları

### 🛠️ Araçlar ve Yardımcılar (Öncelik: Düşük)
- [ ] Birim dönüştürücü (m², m³, kg, ton, vb.)
- [ ] Hesaplama makinesi (entegre)
- [ ] QR kod oluşturma (proje linki için)
- [ ] Toplu işlemler (toplu silme, güncelleme)

### 🎨 Tema ve Özelleştirme (Öncelik: Düşük)
- [ ] Açık/koyu tema seçimi
- [ ] Renk şeması özelleştirme
- [ ] Font boyutu ayarlama
- [ ] Tablo görünümü özelleştirme

### 📚 Dokümantasyon ve Yardım (Öncelik: Orta)
- [ ] İçeride yardım menüsü
- [ ] Kısayol tuşları listesi
- [ ] Video eğitimler (link)
- [ ] SSS (Sık Sorulan Sorular)
- [ ] Kullanım kılavuzu (PDF)

### 🔐 Güvenlik (Öncelik: Orta)
- [ ] Veritabanı şifreleme
- [ ] Yedek dosyası şifreleme
- [ ] Otomatik kilitlenme (belirli süre hareketsizlik)
- [ ] Aktivite logları

### 🌐 Çoklu Dil Desteği (Öncelik: Düşük)
- [ ] İngilizce dil desteği
- [ ] Dil seçimi ayarları
- [ ] Çeviri dosyaları (i18n)

### 📊 Excel Gelişmiş Özellikler (Öncelik: Orta)
- [ ] Excel şablonu indirme
- [ ] Excel validasyon kuralları
- [ ] Toplu Excel import (birden fazla dosya)
- [ ] Excel'de formül desteği

### 🔍 Poz Yönetimi Gelişmiş (Öncelik: Orta)
- [ ] Poz arama ve filtreleme
- [ ] Poz kategorileri yönetimi
- [ ] Poz favorileri
- [ ] Poz geçmişi (kullanılan pozlar)
- [ ] Poz karşılaştırması

### 💼 İhale Gelişmiş Özellikler (Öncelik: Orta)
- [ ] İhale şablonları
- [ ] İhale versiyonlama
- [ ] İhale karşılaştırması (farklı ihaleler)
- [ ] İhale onay süreci
- [ ] İhale durumu takibi (hazırlanıyor, onaylandı, iptal)

### 📦 Malzeme Gelişmiş Özellikler (Öncelik: Düşük)
- [ ] Malzeme stok takibi
- [ ] Tedarikçi yönetimi
- [ ] Malzeme fiyat karşılaştırması
- [ ] Malzeme kategorileri

---

## 🎯 ÖNCELİK SIRALAMASI (Önerilen)

### 🔴 Yüksek Öncelik (Hemen Eklenebilir)
1. **Arama ve Filtreleme** - Kullanıcı deneyimini çok iyileştirir
2. **Yedekleme ve Versiyonlama** - Veri güvenliği kritik
3. **KDV Hesaplamaları** - İş gereksinimi

### 🟡 Orta Öncelik (Yakın Gelecekte)
4. **Görselleştirme** - Raporlama için önemli
5. **Gelişmiş Hesaplamalar** - İşlevsellik artışı
6. **Rapor Şablonları** - Profesyonellik
7. **İstatistikler ve Analiz** - Karar verme desteği

### 🟢 Düşük Öncelik (İleri Seviye)
8. **Takvim ve İş Programı** - Nice to have
9. **Kullanıcı Yönetimi** - Çoklu kullanıcı gerektiğinde
10. **Mobil/Web Erişimi** - Büyük proje

---

## 📝 NOTLAR

- Mevcut özellikler tam çalışır durumda
- Hot reload özelliği development için aktif
- Türkçe karakter desteği PDF ve Excel export'ta mevcut
- Lazy loading ile performans optimizasyonu yapılmış
- Veritabanı WAL mode ile optimize edilmiş

---

## 🤝 Gemini'ye Sorulacak Sorular

1. Hangi özellikler en çok kullanıcı değeri sağlar?
2. Hangi özellikler teknik olarak en kolay implement edilir?
3. Hangi özellikler pazarlama açısından en çekici?
4. Hangi özellikler rakiplerden fark yaratır?
5. Kullanıcı geri bildirimlerine göre en çok istenen özellikler nelerdir?


