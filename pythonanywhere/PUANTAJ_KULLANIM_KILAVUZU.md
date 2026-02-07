# ŞANTİYE PUANTAJ SİSTEMİ
## Kullanım Kılavuzu

---

## 1. SİSTEMİ KURMA (Tek Seferlik)

### Adım 1: PythonAnywhere Hesabı Aç
1. Tarayıcıdan **www.pythonanywhere.com** adresine git
2. **"Start for free"** butonuna tıkla
3. Kullanıcı adı, e-posta ve şifre belirle
4. Hesabı oluştur (ücretsiz)

### Adım 2: Dosyayı Yükle
1. Giriş yaptıktan sonra **"Files"** sekmesine tıkla
2. **"mysite"** klasörüne gir
3. **"Upload a file"** butonuna tıkla
4. Bilgisayarındaki **app.py** dosyasını seç ve yükle

### Adım 3: Web Uygulaması Oluştur
1. Üst menüden **"Web"** sekmesine tıkla
2. **"Add a new web app"** butonuna tıkla
3. **"Next"** e tıkla
4. **"Flask"** seçeneğini seç
5. **"Python 3.10"** seç
6. Path kısmına yaz: `/home/KULLANICIADIN/mysite/app.py`
   (KULLANICIADIN yerine kendi kullanıcı adını yaz)
7. **"Next"** e tıkla

### Adım 4: Şifreni Belirle (ÖNEMLİ!)
1. **"Files"** sekmesine git
2. **mysite** klasöründeki **app.py** dosyasına tıkla
3. Dosyada şu satırları bul ve kendi şifreni yaz:
   ```
   API_USERNAME = "santiye"    # Kullanıcı adın
   API_PASSWORD = "2024"       # Şifren
   ```
4. **"Save"** butonuna tıkla

### Adım 5: Sistemi Başlat
1. **"Web"** sekmesine git
2. Yeşil **"Reload"** butonuna tıkla
3. Sistemin adresi: **https://KULLANICIADIN.pythonanywhere.com**

---

## 2. TELEFONA EKLEME (iPhone)

### Safari ile Kurulum
1. iPhone'da **Safari** uygulamasını aç (Chrome değil!)
2. Adres çubuğuna yaz: **https://KULLANICIADIN.pythonanywhere.com**
3. Kullanıcı adı ve şifreni gir
4. Sayfayı aç

### Ana Ekrana Ekleme
1. Safari'de **Paylaş** butonuna tıkla (altta ortadaki kare ok simgesi)
2. Aşağı kaydır, **"Ana Ekrana Ekle"** seçeneğine tıkla
3. İsim olarak **"Puantaj"** yaz
4. **"Ekle"** butonuna tıkla
5. Artık ana ekranda **Puantaj** ikonu görünecek!

---

## 3. GÜNLÜK KULLANIM

### Giriş Yapma
1. Ana ekrandaki **Puantaj** ikonuna tıkla
2. Kullanıcı adı ve şifreni gir
3. Sistem açılacak

### Puantaj Girişi (Hızlı Yöntem)
1. Üstteki tarih doğru mu kontrol et (değilse ok tuşlarıyla değiştir)
2. Her işçinin yanında 3 buton var:
   - **✓ (Yeşil)** = Tam gün çalıştı
   - **½ (Sarı)** = Yarım gün çalıştı
   - **✗ (Kırmızı)** = Gelmedi / İzinli
3. İlgili butona dokun, otomatik kaydedilir

### Puantaj Girişi (Detaylı Yöntem)
1. İşçinin kartına dokun (butona değil, karta)
2. Açılan pencerede:
   - Çalışma durumu seç
   - Giriş/çıkış saati gir
   - Mesai saati gir (varsa)
   - Yapılan işi yaz
3. **"Kaydet"** butonuna tıkla

---

## 4. İŞÇİ EKLEME

1. Alt menüden **"İşçiler"** sekmesine git
2. Formu doldur:
   - **Ad Soyad**: İşçinin adı
   - **Ustalık**: Düz İşçi, Kalıpçı, Demirci vb.
   - **Günlük Ücret**: TL cinsinden günlük yevmiye
3. **"Ekle"** butonuna tıkla

---

## 5. HAFTALIK ÖZET GÖRME

1. Alt menüden **"Özet"** sekmesine git
2. Haftalık tablo görünür:
   - Her işçinin çalıştığı gün sayısı
   - Toplam hakediş tutarı

---

## 6. EK GİDER EKLEME

1. Alt menüden **"Giderler"** sekmesine git
2. Formu doldur:
   - **Gider Adı**: Yakıt, Yemek, Malzeme vb.
   - **Tutar**: TL cinsinden
   - **Açıklama**: İsteğe bağlı not
3. **"Gider Ekle"** butonuna tıkla
4. Ay seçerek o aya ait giderleri görüntüle
5. Silmek için giderin yanındaki **✗** butonuna tıkla

---

## 7. HATA DÜZELTME

### Yanlış Puantaj Girdiysen
1. İlgili tarihe git (ok tuşlarıyla)
2. İşçinin kartına dokun
3. Doğru bilgileri gir
4. **"Kaydet"** e tıkla

### Yanlış Güne Girdiysen
1. **Yanlış tarihe** git
2. İşçinin kartına dokun
3. **"Bu Günü Sil"** butonuna tıkla
4. **Doğru tarihe** git
5. Puantajı yeniden gir

### İşçi Silmek İstersen
- Şu an işçi silme yok, sadece puantaj silinebilir
- İşçiyi pasif yapmak için PythonAnywhere'den veritabanını düzenlemen gerekir

---

## 8. ÖNEMLİ BİLGİLER

### İnternet Bağlantısı
- Sistem çalışması için internet gerekli
- WiFi veya mobil veri olabilir
- Bilgisayarın açık olması GEREKMEZ

### Güvenlik
- Şifreni kimseyle paylaşma
- Tarayıcıda "Şifreyi Hatırla" seçersen her seferinde girmene gerek kalmaz

### Yedekleme
- Veriler PythonAnywhere sunucusunda saklanır
- Yedek almak için: Files > mysite > puantaj.db dosyasını indir

### Sorun Olursa
1. Sayfayı yenile
2. Çıkış yap, tekrar giriş yap
3. PythonAnywhere'de "Web" sekmesinden "Reload" yap

---

## 9. EKRAN GÖRÜNÜMLERİ

### Ana Ekran (Puantaj)
```
┌─────────────────────────────┐
│ 👷 Şantiye Puantaj          │
│ [  2024-01-15  ] [◀] [▶]   │
├─────────────────────────────┤
│  12    3     2              │
│ Gelen Yok  Mesai            │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ AY  Ahmet Yılmaz        │ │
│ │     Kalıpçı    [✓][½][✗]│ │
│ └─────────────────────────┘ │
│ ┌─────────────────────────┐ │
│ │ MK  Mehmet Kaya         │ │
│ │     Demirci    [✓][½][✗]│ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ 📋    👷    📊    💸       │
│Puantaj İşçi  Özet Gider    │
└─────────────────────────────┘
```

---

## 10. SIKÇA SORULAN SORULAR

**S: Birden fazla kişi aynı anda kullanabilir mi?**
C: Evet, şifreyi bilen herkes aynı anda girebilir.

**S: Eski tarihlere giriş yapabilir miyim?**
C: Evet, tarih seçerek istediğin güne giriş yapabilirsin.

**S: Veriler nerede saklanıyor?**
C: PythonAnywhere sunucusunda, güvenli şekilde saklanıyor.

**S: Ücretsiz mi?**
C: Evet, PythonAnywhere ücretsiz hesapla çalışır.

**S: Bilgisayarım kapalıyken çalışır mı?**
C: Evet, sistem bulutta çalışır, bilgisayar gerekmez.

---

**Hazırlayan:** İnşaat Metraj Pro
**Versiyon:** 1.0
**Tarih:** 2024
