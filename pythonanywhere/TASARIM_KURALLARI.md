# Tasarım Kuralları — "Kurumsal" Tema (beyaz + lacivert)

> `yeni_proje/pythonanywhere/` klasöründe durur. ANA_PROGRAM_PLANI.md ile birlikte geçerlidir. Kullanıcı bu temayı seçti, onaylıdır. Ekran yapısı ve iş mantığı değişmez; bu dosya sadece görünümü tanımlar.

> **Uygulama notu (Rev-177):** Renkler `ortak.TEMA` sözlüğünde; CSS `:root` değişkenleri ve PDF renkleri bu sözlükten üretilir (tek nokta). İkonlar `ortak.IKONLAR`. Ana menü selamlaması saate göre (Günaydın / İyi günler / İyi akşamlar).

## 1. Tek noktadan stil

- Tüm renkler, yazı tipi ve ölçüler `ortak.py` içinde **tek bir ortak CSS** olarak tanımlanır (CSS değişkenleri `:root` üzerinde). Ana menü, Müteahhitler, Demirciler ve Vinç bu CSS'i kullanır. Hiçbir modül kendi renk kodunu yazmaz; değişken kullanır.
- Puantaj'a bu dosya kapsamında DOKUNULMAZ (ayrı, isteğe bağlı iş olarak bkz. bölüm 9).

## 2. Renkler

```css
:root {
  color-scheme: light;
  --lacivert:        #1E3A8A;  /* başlık bandı, ana buton, aktif sekme */
  --lacivert-koyu:   #172E6E;  /* basılı/hover */
  --lacivert-acik:   #EEF2FF;  /* ikon dairesi, tablo başlığı zemini, seçili satır */
  --lacivert-cizgi:  #C7D2FE;  /* başlık üstündeki soluk metin, odak halkası */
  --zemin:           #FFFFFF;
  --zemin-2:         #F8FAFC;  /* form alanları, toplam satırı */
  --cizgi:           #E2E8F0;  /* ayırıcılar, kart kenarları */
  --metin:           #0F172A;
  --metin-soluk:     #475569;  /* alt bilgi, etiket */
  --ikon-soluk:      #64748B;  /* ok ikonları */
  --alacak:          #15803D;  /* para bana gelecek: müteahhit kalanı */
  --borc:            #B91C1C;  /* benim borcum: demirci kalanı; Sil butonu */
  --odeme:           #1E40AF;  /* Alınan / Ödenen sütunu */
  --uyari:           #B45309;  /* "Fazla ödeme" */
}
```

Anlam kuralları:
- Müteahhit **KALAN** her yerde `--alacak` (yeşil), demirci **KALAN** her yerde `--borc` (kırmızı). Kalan sıfırsa `--metin-soluk`.
- Hakediş sütunu `--metin`, Alınan/Ödenen sütunu `--odeme`.
- Fazla ödeme (kalan < 0): `--uyari` renkte "Fazla ödeme: ₺…".
- Renk tek başına anlam taşımaz; yanında her zaman "alacak", "borç", "fazla ödeme" yazısı bulunur.

## 3. Yazı tipi

- **Manrope** (Google Fonts, ağırlıklar 500/600/700/800), yedek: `system-ui, -apple-system, sans-serif`. Türkçe karakterleri destekler.
- Tüm para ve miktar rakamlarında `font-variant-numeric: tabular-nums;` (sütunlarda rakamlar alt alta hizalı durur).
- Ölçüler: sayfa başlığı 28px/800 · kart/satır başlığı 17px/700 · normal metin 15px/500 · alt bilgi 13px/500 · küçük etiket 12px/600. Hiçbir metin 12px'ten küçük olmaz.

## 4. Ölçüler

- Kenar boşluğu: yatay 20px. Bölümler arası 24px.
- Köşe yarıçapı: büyük kart 18px · buton ve form alanı 12px · ikon dairesi tam yuvarlak.
- Gölge sadece "yüzen" özet kartında: `0 8px 24px rgba(15,23,42,0.12)`. Diğer kartlar gölgesiz, `1px solid var(--cizgi)`.
- Dokunma hedefi en az 44×44px. Ana buton yüksekliği 52px.
- iPhone çentiği/alt çubuğu için `viewport-fit=cover` + `env(safe-area-inset-*)` boşlukları.

## 5. Ortak bileşenler

**Başlık bandı (her ana sayfada):** lacivert zemin, beyaz metin. Üst satırda küçük soluk metin (`--lacivert-cizgi`: tarih veya "‹ Geri") ve sağda yuvarlak "?" Yardım butonu (`rgba(255,255,255,0.15)` zemin). Altında 28px/800 sayfa başlığı. Bandın alt boşluğu 64px; altındaki özet kartı -44px ile bandın üstüne biner.

**Yüzen özet kartı:** beyaz, 18px köşe, gölgeli. İki sütun ve aralarında ince dikey çizgi. Ana menüde: Toplam alacak | Toplam borç. Firma sayfasında: Hakediş | Alınan (Ödenen) ve altında tam genişlikte KALAN.

**Liste satırı:** solda 48px yuvarlak `--lacivert-acik` daire içinde lacivert çizgi ikon, ortada başlık + alt bilgi, sağda tutar veya `›` oku. Satırlar arası `1px solid var(--cizgi)`, kart kutusu yok.

**Sola kaydırma eylemleri:** Düzenle (`--lacivert`), Sil (`--borc`), beyaz yazı ve ikon. Sil her zaman onay penceresi açar.

**Butonlar:**
- Ana: dolu `--lacivert`, beyaz yazı, 52px, 12px köşe.
- İkincil: beyaz zemin, `--cizgi` kenar, `--metin` yazı.
- Tehlikeli: `--borc` zemin, beyaz yazı (sadece onay penceresinde).

**Sekmeler (Beton / Gider / Alınan para):** `--zemin-2` zemin üzerinde segment. Seçili sekme beyaz, lacivert yazı, ince gölge.

**Form alanları:** `--zemin-2` zemin, `--cizgi` kenar, 12px köşe, 48px yükseklik. Odakta `2px solid var(--lacivert)`. Otomatik hesaplanan "Hakediş" kutusu `--lacivert-acik` zemin, lacivert yazı.

**Defter tablosu:** başlık satırı `--lacivert-acik` zemin, 12px/700 büyük harf etiketler. Toplam satırı `--zemin-2`. En altta KALAN satırı: lacivert zemin, beyaz "KALAN" yazısı, tutar beyaz ve büyük (20px/800); altında küçük "alacak" / "borç" etiketi.

**Onay penceresi:** beyaz kart, ortada başlık ("Silinsin mi?"), açıklama ("Yılmaz İnşaat ve tüm kayıtları silinecek."), yan yana İkincil "Vazgeç" + Tehlikeli "Sil".

**İkonlar:** sade çizgi ikonlar (stroke 1.9, yuvarlak uçlar), inline SVG. Modül ikonları: Müteahhitler bina, Demirciler ızgara/hasır, Puantaj onay işaretli liste, Mobil Vinç vinç.

## 6. Ekran ekran

- **Ana Menü:** başlık bandı ("Günaydın · 4 Kasım 2026" + "Şantiye Defteri"), yüzen kart (Toplam alacak yeşil, Toplam borç kırmızı), altında 4 liste satırı (Müteahhitler, Demirciler, Puantaj, Mobil Vinç) ve her birinin alt bilgisinde kısa özet.
- **Firma listesi:** başlık bandı ("‹ Ana Menü", "Müteahhitler"), bandın altında yüzen arama kutusu, liste satırları (sağda kalan tutar), altta sabit ana buton "+ Müteahhit Ekle".
- **Firma sayfası:** başlık bandında firma adı ve sağ üstte PDF butonu. Yüzen özet kartı, ardından giriş formu kartı (sekmeler + alanlar + "Satırı Ekle"), ardından defter tablosu ve KALAN satırı.
- **Firma ekle/düzenle:** başlık bandı ("Vazgeç", "Yeni Müteahhit"), Firma adı alanı, fiyat kalemleri listesi, "+ Yeni kalem ekle" lacivert metin butonu, altta "Kaydet".
- **Gün sonu raporu:** başlık bandı, tarih + kapsam seçimi, yüzen özet kartı (miktar, hakediş, alınan), firma listesi, "PDF Oluştur".
- **Mobil Vinç:** aynı başlık bandı ve yüzen kart (Gelir | Gider, altında Net), kayıt listesi.

## 7. PDF'ler (reportlab)

Manrope yerine mevcut Türkçe uyumlu PDF fontu kullanılır; sadece renkler temaya uyar: üstte lacivert (#1E3A8A) ince bant ve başlık, tablo başlık satırı #EEF2FF, toplam satırı #F8FAFC, KALAN satırı lacivert zemin beyaz yazı, alacak yeşil (#15803D) / borç kırmızı (#B91C1C).

## 8. iPhone uygulama görünümü

- `<meta name="theme-color" content="#1E3A8A">`, `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style` = `black-translucent`.
- `apple-touch-icon` (180×180 PNG): lacivert zemin üzerinde beyaz basit bina ikonu. Ana ekran adı: "Şantiye Defteri".

## 9. (İsteğe bağlı, ayrı iş) Puantaj renk uyumu

Sadece kullanıcı ayrıca isterse yapılır. Puantajda yalnız CSS renk değişkenleri ve yazı tipi bu temaya eşlenir; düzen, metin, hesap, JS ve endpoint'ler değişmez. Önce/sonra ekran görüntüsüyle kontrol edilir.
