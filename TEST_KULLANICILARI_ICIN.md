# 🧪 InsaatMetrajPro - Test Kullanıcıları İçin Rehber

Merhaba! Bu uygulamayı test ettiğiniz için teşekkür ederiz. Geri bildirimleriniz bizim için çok değerli.

---

## 📥 Hızlı Kurulum

### 1. Gereksinimler
- **Windows 10/11** (veya Windows 7+)
- **Python 3.8 veya üzeri** ([İndir](https://www.python.org/downloads/))
  - Kurulum sırasında **"Add Python to PATH"** seçeneğini işaretleyin!

### 2. Kurulum Adımları

1. **Proje dosyalarını indirin** ve bir klasöre çıkarın (örn: `C:\InsaatMetrajPro\`)

2. **Kurulum scriptini çalıştırın:**
   - `KURULUM.bat` dosyasına çift tıklayın
   - VEYA komut satırından: `pip install -r requirements.txt`

3. **Uygulamayı başlatın:**
   - `InsaatMetrajPro.bat` dosyasına çift tıklayın
   - VEYA komut satırından: `python main.py`

---

## 🎯 Test Edilmesi Gereken Özellikler

### ✅ Temel Özellikler

1. **Proje Yönetimi**
   - [ ] Yeni proje oluşturma
   - [ ] Proje silme
   - [ ] Proje seçme

2. **Metraj Cetveli**
   - [ ] Kalem ekleme (kategori seçimi → poz seçimi)
   - [ ] Kalem düzenleme
   - [ ] Kalem silme
   - [ ] Toplam maliyet hesaplama
   - [ ] Seçili kalem için malzeme listesi görüntüleme
   - [ ] Birim fiyat düzenleme

3. **Taşeron Analizi**
   - [ ] Teklif ekleme
   - [ ] Teklif düzenleme
   - [ ] Teklif silme
   - [ ] Teklif karşılaştırma
   - [ ] Excel export
   - [ ] PDF export

4. **Malzeme Listesi**
   - [ ] Malzeme hesaplama (otomatik fire oranı)
   - [ ] Manuel fire oranı modu
   - [ ] Excel export
   - [ ] PDF export
   - [ ] Tedarikçi formatı export

### 🔍 Performans ve Kullanılabilirlik

- [ ] Uygulama açılış hızı (ilk açılışta pozlar yüklenirken)
- [ ] Arayüz kullanım kolaylığı
- [ ] Hata mesajlarının anlaşılır olması
- [ ] Veri kaybı olmadan kapanma/açılma

---

## 🐛 Hata Bildirimi

Bir hata ile karşılaşırsanız, lütfen şu bilgileri paylaşın:

1. **Hata mesajı** (tam metin)
2. **Ne yapıyordunuz?** (adım adım)
3. **Ekran görüntüsü** (varsa)
4. **Python sürümü:** `python --version`
5. **İşletim sistemi:** Windows 10/11 vb.

### Hata Örnekleri:
- Uygulama açılmıyor
- Buton çalışmıyor
- Veri kayboldu
- Hesaplama yanlış
- Export çalışmıyor

---

## 💡 Öneri ve İyileştirmeler

Lütfen şu konularda görüşlerinizi paylaşın:

1. **Arayüz Tasarımı**
   - Renkler, butonlar, menüler nasıl?
   - Daha iyi olabilir mi?

2. **Kullanım Kolaylığı**
   - Hangi özellikler eksik?
   - Hangi özellikler karışık?
   - Ne eklenmeli?

3. **Performans**
   - Hangi işlemler yavaş?
   - Hangi işlemler hızlı?

4. **Özellik İstekleri**
   - Hangi özellikler eklenmeli?
   - Hangi özellikler geliştirilmeli?

---

## 📝 Geri Bildirim Formu

Lütfen aşağıdaki formu doldurarak geri bildirim gönderin:

```
TEST KULLANICI GERİ BİLDİRİMİ
================================

1. GENEL DEĞERLENDİRME
   - Uygulama genel olarak nasıl? (1-10 arası puan)
   - Kullanım kolaylığı? (1-10 arası puan)
   - Tasarım? (1-10 arası puan)

2. EN ÇOK BEĞENDİKLERİNİZ
   - Hangi özellikleri beğendiniz?
   - Hangi özellikler işinize yaradı?

3. SORUNLAR VE HATALAR
   - Karşılaştığınız hatalar
   - Çalışmayan özellikler
   - Karışık bulduğunuz kısımlar

4. ÖNERİLER
   - Eklenmesini istediğiniz özellikler
   - İyileştirme önerileri
   - Tasarım önerileri

5. İLETİŞİM (İsteğe bağlı)
   - İsim:
   - E-posta:
   - Telefon:
```

---

## 🎓 Kullanım İpuçları

### İlk Kullanım
1. Uygulama açıldığında **"Pozlar yüklenmek ister misiniz?"** sorusuna **"Evet"** deyin
2. İlk projenizi oluşturun
3. Kategori seçerek kalem eklemeye başlayın

### Metraj Cetveli
- Kategori seçtikten sonra pozlar otomatik filtrelenir
- Bir kalem seçtiğinizde altında malzeme listesi görünür
- Birim fiyatları düzenleyebilirsiniz

### Taşeron Analizi
- Birden fazla firma teklifi ekleyin
- "Karşılaştır" butonu ile firmaları karşılaştırın
- Excel/PDF export ile rapor alın

### Malzeme Listesi
- Otomatik mod: Her poz için literatür fire oranı kullanılır
- Manuel mod: Tüm pozlar için aynı fire oranı
- Export ile tedarikçilere gönderebilirsiniz

---

## ❓ Sık Sorulan Sorular

**S: Python kurulu değil, ne yapmalıyım?**
C: https://www.python.org/downloads/ adresinden Python 3.8+ indirin. Kurulum sırasında "Add Python to PATH" seçeneğini işaretleyin.

**S: "ModuleNotFoundError" hatası alıyorum**
C: Komut satırından `pip install -r requirements.txt` komutunu çalıştırın.

**S: Projelerim kayboldu mu?**
C: Projeler `data/insaat_metraj.db` dosyasında saklanır. Bu dosyayı yedekleyin.

**S: Pozlar yüklenmedi**
C: Menüden "Veri > Pozları Yükle" seçeneğini kullanın.

**S: Export çalışmıyor**
C: Excel/PDF dosyası açık olmamalı. Dosyayı kapatıp tekrar deneyin.

---

## 📧 İletişim

Geri bildirimlerinizi şu şekillerde gönderebilirsiniz:

- **E-posta:** [E-posta adresiniz]
- **GitHub Issues:** [GitHub repo linki]
- **Form:** [Form linki]

---

## 🙏 Teşekkürler!

Test ettiğiniz ve geri bildirim verdiğiniz için çok teşekkür ederiz. 
Görüşleriniz uygulamayı daha iyi hale getirmemize yardımcı olacak!

---

**Not:** Bu bir test sürümüdür. Üretim ortamında kullanmadan önce tüm özellikleri test edin.



