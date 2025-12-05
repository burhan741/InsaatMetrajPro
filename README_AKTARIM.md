# 🚀 Hızlı Aktarım Rehberi

## Başka Bilgisayara Aktarma - 3 Adım

### 1️⃣ Aktarım Hazırlama (Bu Bilgisayarda)

**Seçenek A: Otomatik (Önerilen)**
- `AKTARIM_HAZIRLA.bat` dosyasına çift tıklayın
- `InsaatMetrajPro_Aktarim` klasörü oluşturulacak
- Bu klasörü ZIP yapın

**Seçenek B: Manuel**
- Aşağıdaki klasörleri ZIP yapın:
  - `app/` klasörü (tüm içeriği)
  - `main.py`
  - `requirements.txt`
  - `InsaatMetrajPro.bat`
  - `KURULUM.bat`
  - `KURULUM_REHBERI.md`

### 2️⃣ Yeni Bilgisayarda Kurulum

1. ZIP dosyasını açın
2. `KURULUM.bat` dosyasına çift tıklayın (otomatik kurulum)
   - VEYA manuel: `pip install -r requirements.txt`
3. `InsaatMetrajPro.bat` ile uygulamayı başlatın

### 3️⃣ İlk Kullanım

- Uygulama açıldığında pozlar yüklenmek istenirse **"Evet"** deyin
- İlk projenizi oluşturun

---

## 📋 Aktarılması Gereken Dosyalar

✅ **Aktar:**
- `app/` klasörü (tüm içeriği)
- `main.py`
- `requirements.txt`
- `InsaatMetrajPro.bat`
- `KURULUM.bat`
- `KURULUM_REHBERI.md`

❌ **Aktarma:**
- `__pycache__/` klasörleri
- `data/insaat_metraj.db` (yeni bilgisayarda otomatik oluşturulur)
- `.xlsx` dosyaları (geçici raporlar)
- `.git/` klasörü

---

## 💾 Projelerinizi Yedeklemek İçin

Projelerinizi korumak istiyorsanız:
- `data/insaat_metraj.db` dosyasını da kopyalayın
- Yeni bilgisayarda aynı konuma yerleştirin

---

## ⚠️ Gereksinimler

Yeni bilgisayarda:
- **Python 3.8+** yüklü olmalı
- İnternet bağlantısı (kütüphaneleri indirmek için)

---

Detaylı bilgi için: `KURULUM_REHBERI.md`



