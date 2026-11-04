# Ana Program Planı — Şantiye Cari + Puantaj + Mobil Vinç

> **Durum (2026-11-04):** 6 adımın hepsi kodlandı (Rev-171..176), 100 pytest PASS. Kullanıcının sunucuda uçtan uca denemesi bekleniyor. Uygulamada plana eklenen kararlar: rapor başlığı ayrı `cari_ayar` tablosunda (puantaj `ayarlar`'ına dokunulmadı); gün sonu "kalan" = o günün sonundaki bakiye; firma dökümünde tarih aralığı seçilirse "Devreden bakiye"; PWA ikonu `ortak.py`'ye gömülü (ek dosya yok).

> Bu dosya `yeni_proje/pythonanywhere/` klasöründe durur. CLAUDE.md'deki genel protokol ve "Puantaj Flask" kuralları aynen geçerlidir; bu dosya o kuralların üzerine bu projeye özel kararları ekler. Kararların hepsi kullanıcı onaylıdır — tekrar sorma.

## 1. Amaç

Mevcut puantaj uygulamasını da içeren tek bir Flask programı. Kullanıcı iPhone'da Safari üzerinden kullanır ("Ana Ekrana Ekle"). Sunucu: PythonAnywhere ücretsiz hesap, kullanıcı `burhan852`, giriş noktası `/home/burhan852/app.py` (WSGI `from app import app`).

Ana menüde 4 kart:

| Kart | Ne yapar | Para yönü |
|---|---|---|
| Müteahhitler | Döktüğüm beton + giderler → hakediş; müteahhitten aldığım para | Kalan = **alacağım** |
| Demirciler | Demirci taşeronların işi → hakediş; onlara ödediğim para | Kalan = **borcum** |
| Puantaj | Mevcut uygulama, **aynen** | — |
| Mobil Vinç | Mevcut vinç gelir-gider defteri, puantajdan ayrılmış | Net = gelir − gider |

## 2. Kesin kararlar (kullanıcı onaylı)

- **Şifre / giriş ekranı YOK.** Ekleme, önerme.
- **Puantaj DEĞİŞMEYECEK.** Görünüm, hesaplar, endpoint'ler, tablo yapısı aynen kalır. İzin verilen değişiklikler yalnızca şunlar:
  1. Mobil Vinç sekmesi ve `/api/vinc/*` route'ları puantajdan çıkarılıp Vinç modülüne taşınır.
  2. Puantaj sayfasının üstüne "‹ Ana Menü" bağlantısı eklenir.
  3. Puantaj ana sayfa adresi `/` yerine `/puantaj` olur (mevcut `?v=` cache-bust yönlendirmesi `/puantaj?v=...` olarak korunur).
  4. `app.route` → Blueprint dönüşümü (mekanik, mantık değişmez).
  Puantaj JS'i `/api/...` adreslerini çağırıyor; bu adresler aynen kalmalı. Yeni modüllerin API'leri `/api/cari/...` ve `/api/vinc/...` altında olur, çakışma olmaz.
- **Tek veritabanı:** Sunucudaki mevcut `puantaj.db` kullanılır, yeni tablolar ona eklenir (`CREATE TABLE IF NOT EXISTS`). Mevcut tablolara dokunulmaz. Böylece puantaj ve vinç verisi taşıma gerektirmez, `_gunluk_otomatik_yedek` her şeyi yedekler.
- Müteahhit ve demirci **aynı kodu** kullanır (`tur` alanı: `muteahhit` / `demirci`). Bir özellik bir kez yazılır, ikisine de gelir.
- Yeni modüllerde (Müteahhit, Demirci, Vinç) **her kayıtta Düzenle + Sil** var. Her silmede onay sorulur. Firma silinince tüm hareketleri ve fiyat kalemleri de silinir (veritabanında artık kalmaz).
- Beton dışı **giderler hakedişe eklenir** (müteahhide yansır; demircide borcumu artırır).
- Kalan eksiye düşerse sıfırlanmaz; "Fazla ödeme: ₺…" olarak gösterilir (yalnız yeni modüllerde; puantaja dokunma).

## 3. Dosya yapısı

```
pythonanywhere/
  app.py            # Flask app, Blueprint kayıtları, ana menü route'u (/), init_db çağrıları
  puantaj.py        # Mevcut app.py içeriği, Blueprint'e çevrilmiş, vinç çıkarılmış
  cari.py           # Müteahhit + Demirci (ortak motor) — route'lar, hesap, PDF
  vinc.py           # Vinç defteri (mevcut vinc_defter tablosu)
  ortak.py          # DB_PATH, bağlantı, para/tarih biçimleme, PDF font yardımcıları
  test_*.py         # pytest testleri (temp DB ile)
```

HTML'ler mevcut alışkanlığa uygun olarak her modülün içinde string şablon olarak tutulabilir; CLAUDE.md'deki `r'''` / normal string kuralına dikkat. Kullanıcı dosyaları elle yüklüyor: yüklenmesi gereken dosyaların listesini her teslimde açıkça yaz.

`.gitignore`'a `*.db`, `backups/`, `__pycache__/`, `.venv_test/` ekle. `yeni_proje` deposu herkese açık; müteahhit/demirci bakiyeleri müşteri verisidir, asla commit'lenmez. Eski kopyalar (`app - Kopya.py`, `app_test.py` kopya mantığı yeni yapıda gerekirse yeniden kurulur, `fix.py`, `fix2.py`) yeni yapıya taşınmaz.

## 4. Veritabanı (yeni tablolar)

```sql
cari_firma (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tur TEXT NOT NULL CHECK (tur IN ('muteahhit','demirci')),
  ad TEXT NOT NULL,
  olusturma TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
cari_fiyat_kalemi (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  firma_id INTEGER NOT NULL REFERENCES cari_firma(id),
  ad TEXT NOT NULL,            -- "Gro beton", "Temel betonu", "Normal katlar" / "Temel demiri"...
  birim_fiyat REAL NOT NULL,
  sira INTEGER DEFAULT 0
)
cari_hareket (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  firma_id INTEGER NOT NULL REFERENCES cari_firma(id),
  tarih DATE NOT NULL,
  tip TEXT NOT NULL CHECK (tip IN ('is','gider','odeme')),
  kalem_id INTEGER,            -- sadece tip='is'
  kalem_adi TEXT,              -- kayıt anındaki ad (kalem sonradan silinse/yeniden adlandırılsa da satır bozulmaz)
  miktar REAL,                 -- m³ (müteahhit) / ton (demirci)
  birim_fiyat REAL,            -- kayıt anındaki fiyat, satıra KİLİTLİ
  tutar REAL NOT NULL,         -- is: miktar*birim_fiyat; gider/odeme: elle
  aciklama TEXT,
  olusturma TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

- Fiyat kilidi (CLAUDE.md kuralı): birim fiyat değişse geçmiş satırlar değişmez. Satır düzenlenirken kullanıcı fiyatı bilerek değiştirebilir.
- Hesap: `hakedis = SUM(tutar WHERE tip IN ('is','gider'))`, `odenen = SUM(tutar WHERE tip='odeme')`, `kalan = hakedis - odenen`. Hesap tek fonksiyonda (`firma_bakiye`), liste, firma sayfası, rapor ve PDF hepsi bunu çağırır.
- Silmeler tek transaction içinde (firma → hareketler → kalemler).

## 5. Ekranlar

Mobil öncelikli (390 px), iOS PWA meta etiketleri (`apple-mobile-web-app-capable`, ikon, `viewport-fit=cover`, safe-area). Para `₺1.284.500` biçiminde, tarih ekranda `GG.AA.YYYY`, veritabanında ISO. Her ekranda "?" Yardım butonu + sade Türkçe kılavuz (CLAUDE.md zorunluluğu).

### 5.1 Ana Menü (`/`)
4 büyük kart. Her kartta kısa özet: Müteahhitler toplam alacak, Demirciler toplam borç, Vinç net, Puantaj için sadece giriş.

### 5.2 Firma listesi (`/muteahhit`, `/demirci`)
- Başlık (açık zemin, siyah özet alanı YOK), arama kutusu, firma kartları: ad, son hareket özeti, kalan.
- Satırı sola kaydırınca **Düzenle / Sil**. Sil → "X ve tüm kayıtları silinecek, emin misin?"
- Altta sabit "+ Müteahhit Ekle" / "+ Demirci Ekle". Sağ üstte Gün Sonu Raporu.

### 5.3 Firma ekle / düzenle
- Sadece **Firma adı**.
- **Birim fiyat kalemleri listesi:** her satır kalem adı + fiyat, satır silme (×), "+ Yeni kalem ekle". Birim: müteahhitte ₺/m³, demircide ₺/ton.
- Yetkili, telefon, ada/parsel, beton sınıfı, pompa, açılış bakiyesi alanları YOK.

### 5.4 Firma sayfası (`/muteahhit/<id>`, `/demirci/<id>`)
- Üstte siyah alan: geri, firma adı, kalan (müteahhit "Kalan alacak", demirci "Kalan borcum"), PDF butonu.
- **Giriş formu** (sayfanın içinde, ayrı ekran değil), 3 sekme:
  - Müteahhit: **Beton** (tarih, kalem seçimi, miktar m³, hakediş otomatik) · **Gider** (tarih, açıklama, tutar) · **Alınan para** (tarih, tutar, not: nakit/çek/havale).
  - Demirci: **İş** (tarih, kalem, miktar ton, hakediş otomatik) · **Gider** · **Ödenen para**.
  - Tarih varsayılan bugün. "Satırı Ekle".
- **Defter tablosu:** Tarih | Açıklama (alt satırda `12 m³ × ₺3.250`) | Hakediş | Alınan (demircide "Ödenen"). Eskiden yeniye sıralı; eski kayıtlar tek "Önceki kayıtlar" satırında toplanır, dokununca açılır. Her satırda Düzenle / Sil (kaydırma).
- Tablonun altında Toplam satırı ve büyük **KALAN** satırı.

### 5.5 Gün Sonu Raporu
Tarih seçimi (varsayılan bugün), kapsam: Tümü / Tek firma. Günün özeti (toplam miktar, hakediş, alınan/ödenen) ve o gün hareket gören firmalar (miktar, hakediş, alınan, güncel kalan). "PDF Oluştur". Paylaşım: PDF Safari'de açılır, kullanıcı iOS paylaş menüsünden WhatsApp/Mail'e gönderir.

### 5.6 PDF'ler (reportlab, route içinde `try/except ImportError` → 503)
- **Firma hesap dökümü:** firma adı, tarih aralığı (varsayılan tümü), defter tablosu, toplamlar, KALAN.
- **Gün sonu raporu (A4):** başlıkta `[FİRMA ADI]` yer tutucu (Ayarlar'dan değiştirilebilir), özet kutuları, firma özet tablosu + toplam satırı, günün hareketleri tablosu, oluşturma zamanı, imza alanı.
- Türkçe karakterler için mevcut `_pdf_font_hazirla` yaklaşımı kullanılır.

### 5.7 Mobil Vinç (`/vinc`)
Mevcut `vinc_defter` tablosu ve verisi aynen. Mevcut ekle/liste/sil davranışı korunur, **düzenleme eklenir**. Toplam gelir, gider, net.

## 6. Test ve teslim

- pytest, her testte geçici DB (gerçek `puantaj.db`'ye dokunma). En az: bakiye hesabı, fiyat kilidi, firma silme kaskadı, fazla ödeme gösterimi, demirci etiketleri, puantaj endpoint'lerinin aynen cevap verdiği (regresyon), vinç taşıması sonrası verinin okunduğu.
- Gömülü JS'i `node --check` ile doğrula.
- **Canlıya almadan önce:** kullanıcı sunucudaki `/home/burhan852/puantaj.db`'yi indirir; yeni kod bu dosyanın kopyasıyla yerelde denenir (puantaj ve vinç ekranlarında eski kayıtların aynen göründüğü kontrol edilir).
- Teslimde kullanıcıya: yüklenecek dosya listesi, PythonAnywhere'de "Reload", gerekiyorsa `pip install --user reportlab`.
- Her aşama sonunda `PROGRAM_OZELLIKLERI.txt`'ye Rev kaydı; CLAUDE.md "Puantaj Flask" bölümüne bu projenin kalıcı kurallarını kısa ekle.

## 7. Yapım sırası

1. `ortak.py` + `app.py` ana menü + puantajın Blueprint'e taşınması (vinç çıkarılmış). Puantaj regresyon testi.
2. Vinç modülü (taşıma + düzenleme).
3. Cari motoru + Müteahhitler (liste, ekle/düzenle, firma sayfası, düzenle/sil, PDF dökümü).
4. Demirciler (aynı motor, etiket/birim farkları).
5. Gün sonu raporu + A4 PDF.
6. Yardım kılavuzları, PWA ikon/meta, son test, teslim listesi.
