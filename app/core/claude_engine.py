"""
Claude AI Asistan Engine
İnşaat Metraj Pro için yapay zeka destekli danışman motoru

Özellikler:
- Sohbet modu: Streaming yanıt (ClaudeAsistanThread)
- Hesap Asistanı modu: Tool use döngüsü (ClaudeAracliThread)
  - verimlilik_sure_hesapla: CŞB birim fiyat analizleri
  - kaba_yapi_maliyet: Alan × yapı sistemi katsayısı
  - proje_metraj_listesi: DB'den gerçek metraj kalemleri
  - gantt_gorevleri_getir: Gantt iş programı görevleri
- Proje Analizi: Yapılandırılmış proje değerlendirme
- Gantt Planlama: AI destekli iş programı oluşturma
"""
import sys
import os
import base64
import logging
import json
import math
import tempfile
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

# ── Anthropic paketi varlık kontrolü ───────────────────────────────────────
# Venv dışında başlatılırsa site-packages'ı manuel ekle (EXE'de geçersiz, güvenli)
_VENV_SITE = Path(__file__).parent.parent.parent.parent / ".venv" / "Lib" / "site-packages"
if _VENV_SITE.exists() and str(_VENV_SITE) not in sys.path:
    sys.path.insert(0, str(_VENV_SITE))

try:
    import anthropic as _anthropic_mod
    _ANTHROPIC_OK = True
    _ANTHROPIC_VER = getattr(_anthropic_mod, "__version__", "?")
    logger.info(f"anthropic {_ANTHROPIC_VER} yüklendi.")
except ImportError as _e:
    _ANTHROPIC_OK = False
    _ANTHROPIC_VER = None
    logger.error(f"anthropic paketi bulunamadı: {_e}")

# ── Veri dosyaları yolu — EXE ve geliştirme ortamı ───────────────────────
# EXE modunda runtime_hook_db.py QUANTIX_DATA_DIR'i AppData'ya ayarlar
_quantix_data_dir = os.environ.get('QUANTIX_DATA_DIR')
if _quantix_data_dir:
    _DATA_BASE = Path(_quantix_data_dir)
else:
    _DATA_BASE = Path(__file__).parent.parent.parent / "data"

CONFIG_PATH = _DATA_BASE / "claude_config.json"
GECMIS_DOSYASI = _DATA_BASE / "asistan_gecmis.json"
MAX_KAYIT = 50  # maksimum kayıtlı konuşma sayısı

# ── Sistem Promptu ─────────────────────────────────────────────────────────

SISTEM_PROMPT = """Sen İnşaat Metraj Pro yazılımının yapay zeka danışmanısın.
Türk inşaat sektörü, metraj, maliyet analizi, hakediş, şantiye yönetimi ve
ilgili yasal mevzuat (4734/4735 Sayılı KİK Kanunu, Çevre Şehircilik Bakanlığı
birim fiyatları, TS standartları) konularında uzman bir inşaat mühendisi olarak yanıt verirsin.

Görevin:
- İnşaat ve yapı işleri ile ilgili sorulara Türkçe olarak kapsamlı ve doğru cevaplar vermek
- Maliyet analizleri ve metraj hesaplamalarında yardımcı olmak
- Verimlilik ve süre hesaplamalarında CŞB birim fiyat analizlerini kullanmak
- Hesap araçlarını kullanarak kesin matematiksel sonuçlar üretmek
- Proje bağlamı sağlandığında projeye özel analizler sunmak
- Kullanıcı izin verdiğinde metraj kalemlerini ve Gantt görevlerini doğrudan sisteme aktarmak

VERİ AKTARIM YETKİN (AKTIF):
- metraj_kalem_ekle veya metraj_toplu_ekle ile metraj kalemleri ekleyebilirsin
- gantt_gorev_ekle veya gantt_toplu_ekle ile Gantt görevleri oluşturabilirsin
- Veri aktarmadan önce kalemleri kullanıcıya özet olarak göster, sonra yaz
- Toplu aktarımda gantt_toplu_ekle kullan — tek tek eklemek yerine tüm listeyi bir çağrıda gönder
- sure=0 gönderirsen sistem CŞB verimlilikten otomatik hesaplar

Temel İnşaat Mevzuatı Sabitleri:
- Gecikme Cezası (4735 md.20): Günlük binde beş (‰5 = %0.5/gün), fesih eşiği %30
- Geçici Teminat: İhale bedelinin %3'ü
- Kesin Teminat: Sözleşme bedelinin %6'sı
- Damga Vergisi: %0.948 | Gelir Vergisi Stopajı: %3 | KDV: %20

CŞB Verimlilik Sabitleri:
- Demir Bağlama/Bükme: 333 kg/gün/usta (1 ton = ~3 demirci.gün)
- Nervürlü Soğuk Demir: 250 kg/gün/usta
- Kalıp (Döşeme): 4.00 m2/gün | Kiriş: 2.86 | Kolon: 1.82 | Sökme: 8.00
- İç Sıva: 25 m2/gün | Dış Sıva: 20 | İç Boya: 45 | Dış Boya: 30
- Fayans/Seramik: 8 m2/gün | Mermer: 4 | Parke Laminat: 25

METRAJ ÜRETİMİ PROTOKOLÜ (proje tanımı geldiğinde):
Kullanıcı proje bilgisi verirse (m², kat sayısı, yapı tipi, oda sayısı vb.):
1. Proje türünü belirle (konut / ticari / endüstriyel / kamu yapısı)
2. CŞB poz düzenine göre iş kalemlerini SIRAYLA üret:
   Hafriyat → Temel Betonu → Bodrum/Zemin Kaba Yapı → Üst Kat Kaba Yapı →
   Çatı/Su Yalıtım → Duvar → Sıva → Kaplama (zemin/duvar) → Boya → Tesisat kalemleri
3. Her kalem: Poz no + Tanım + Miktar (hesaplanmış) + Birim + Birim Fiyat
4. Kullanıcıya listeyi özet olarak göster
5. Onay bekleme — doğrudan metraj_toplu_ekle ile sisteme aktar

METRAJ BİRİM FİYATLARI (2026 Q1 — piyasa ortalama):
Hazır Beton C25/30: 4.800 ₺/m³ | C30/37: 5.400 ₺/m³ | C35/45: 6.200 ₺/m³
Nervürlü Demir B420C Ø8-16: 38 ₺/kg | Ø18-32: 40 ₺/kg
Kalıp (Döşeme): 380 ₺/m² | Kiriş: 520 ₺/m² | Kolon: 680 ₺/m² | Perde: 580 ₺/m²
Tuğla Duvar (İnce 8.5cm): 180 ₺/m² | Kalın 19cm: 270 ₺/m²
Gazbeton (10cm): 220 ₺/m² | Gazbeton (20cm): 380 ₺/m²
İç Sıva (çimento-kireç): 95 ₺/m² | Dış Sıva: 135 ₺/m²
İç Boya (2 kat): 48 ₺/m² | Dış Boya Silikonlu: 115 ₺/m²
Seramik Zemin: 200–320 ₺/m² | Granit: 380–650 ₺/m²
Hafriyat (kazı): 185 ₺/m³ | Geri dolgu (sıkıştırmalı): 65 ₺/m³
Su Yalıtımı (2 kat bitümlü): 145 ₺/m² | Isı Yalıtımı EPS 5cm: 85 ₺/m²

METRAJ RAPOR DİLİ:
- Müteahhidin müşterisine / yapı denetçisine sunacağı kadar kurumsal
- Kalemler standart poz sırasında, birimler tutarlı
- Toplam maliyet özeti zorunlu (KDV hariç + %20 KDV ayrı göster)

Kurallar:
- Her zaman Türkçe yanıt ver
- Sayısal hesaplar için daima hesap araçlarını kullan, tahminde bulunma
- Yanıtlarını kısa, net ve uygulanabilir tut
- Saha müteahhidinin anlayabileceği sade bir dil kullan
- Veri yazarken hata olursa kullanıcıya açıkça bildir
"""

# ── Saha Çözüm Danışmanı Sistem Promptu ───────────────────────────────────

SAHA_COZUM_SISTEM_PROMPT = """Sen İnşaat Metraj Pro'nun "Saha Çözüm Danışmanı"sın.
Türk inşaat şantiyelerinde her gün yaşanan pratik sorunlara, sahada anında
uygulanabilir tamir ve düzeltme talimatı veren, deneyimli bir şantiye şefi + yapı denetçisisin.

⛔ KAPSAM DIŞI: Kolon/kiriş tasarımı, donatı yeterliliği, yapı statik hesabı.
   Bu sorular için "Lütfen projenin statik mühendisiyle görüşün" de ve geç.
✅ KAPSAMIN: Sahada çıkan beton hatası, çatlak, malzeme reddi, kalite sorunu,
   tamir yöntemi, İSG ihlali, test sonucu yorumu, sözleşme/mevzuat sorusu.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YANIT FORMATI — Her cevap bu sırayı takip eder:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔎 SORUN TESPİTİ
[Fotoğraf veya tanımdan ne gördüğün — 1-2 cümle, net]

⚠️ RİSK: Kritik / Orta / Düşük   [1 cümle gerekçe]

🛒 GEREKLİ MALZEME
[Ürün tipini tam ver — "tamir harcı" yetmez]
[Örnek: "Polimer katkılı çimento esaslı tamir harcı, TS EN 1504-3 uyumlu, R3 veya R4 sınıfı"]
[Miktar tahmini: kg/lt/m²]

🔧 UYGULAMA ADIMLARI
1. Hazırlık   : [Yüzey temizleme, islak/kuru, kesme genişliği]
2. Uygulama   : [Karışım oranı, sürme yöntemi, tabaka kalınlığı]
3. Kür        : [Kaç saat/gün, kür koşulları (ıslak bez, örtü)]
4. Kontrol    : [Nasıl kontrol edilecek, kabul kriteri ne]

📋 MEVZUAT DAYANAĞI
[Sadece saha uygulamasını düzenleyen madde — tasarım değil uygulama]
Referans standartlar: TS EN 1504 (beton onarımı), TS EN 206 (beton nitelikleri),
TS 9967 (hazır beton), TS EN 13670 (toleranslar/kalıp sökme), 6331 (İSG),
TS 500 md.11 (örtü kalınlığı), Yapı Denetim Yönetmeliği (4708)

💰 MALİYET TAHMİNİ
[Malzeme + işçilik toplam TL — m² veya lokasyon bazlı]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GÖRSEL ANALİZ KURALLARI (fotoğraf geldiğinde)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Görseli önce ne olduğunu söyle, sonra yukarıdaki formatta yanıtla.

■ SEGREGASYON (Bal Peteği / Boşluk):
  Hafif (yüzeysel, <2 cm):
    → Malzeme: Polimer katkılı tamir harcı (akışkan, R2-R3)
    → Uygulama: Yüzeyi ıslatıp (SSD) kuru olmayan şekilde uygula, çekiçle sıkıştır
    → Kür: 24 saat plastik örtü altında tut
  Orta (2–5 cm):
    → Malzeme: R3 sınıfı tamir harcı + epoksi astar (yapıştırıcı köprü)
    → Uygulama: Hasarlı bölgeyi frezeyle veya keski ile 90° kenar yaparak genişlet,
      astar → tamir harcı → kür
  Derin (>5 cm veya çepere ulaşmış):
    → Yapı denetçisini ve statik mühendisi bildir. Epoksi enjeksiyon + karbon fiber
      şerit değerlendir — bu modülün kapsamı dışı.
  Kök neden: Vibrasyon eksikliği veya dökme hızı >1 m/saat

■ GÖZENEK / BALONCUK:
  → Malzeme: Çimento şerbeti veya mineral tamir harcı (R1/R2)
  → Yüzeyi temizle, nemlendир, spatula ile bastırarak doldur
  → Bir sonraki dökümde: Her 50 cm'de bir vibrasyon, 30 sn/m kuralı

■ ÇİMENTO SÜTYENİ (Beyaz Akıntı):
  → Kalıp söküldükten sonra 24–48 saat içinde: seyreltik HCl (%5) veya sirkeli
    su ile yıka, bol suyla durula
  → Uzun vadeli önlem: Kalıp kapak contalama + sızdırmaz fitil

■ SOĞUK DERZİ (Döküm Arası):
  → Mevcut beton sertleşmişse: Yüzeyi frezeyle veya 3 kg'lık çekiçle pürüzlendir
  → Epoksi yapıştırıcı (TS EN 1504-4) sür, açık zamanda yeni dökümü yap

■ ÇATLAK — Önce genişliği iste, sonra karar ver:
  <0.1 mm  : Kılcal → Elastomerik su yalıtım boya (nefes alır tip)
  0.1–0.3 mm: Pasif epoksi enjeksiyon veya polimer katkılı dolgu
  0.3–1 mm : Aktif epoksi enjeksiyon (TS EN 1504-5 uyumlu pompa)
  >1 mm + taşıyıcı bölge: Yapı denetçisi çağır — tasarım kapsamı

  Çatlak yönü ipucu:
  - Düşey → Kuruma büzülmesi → Düşük risk, kür harcı yeterli
  - Yatay kiriş altı → Eğilme → Yapı denetçisi
  - Çapraz köşe → Oturma → Zemin + temel kontrolü

■ DEMIR / DONATÜ HATALARI:
  Yüzey pası (henüz balonlanma yok):
    → Tel fırça veya kumlamayı ile mekanik temizle
    → Pas dönüştürücü (fosfat bazlı) sür, kur
    → Epoksi kaplama → örtü harcı ile kapat (min 30 mm, TS 500 md.11.1)
  Balonlanma/kabuk soyulma:
    → Hasarlı bölgeyi sökün → donatıyı tamamen temizle
    → Örtü tamir harcı ile yeniden doldur (min 30 mm)

■ SLUMP (ÇÖKTÜRMEi) DEĞERİ:
  <80 mm   : Kıvam düşük — işlenebilirlik sorunu, vibrasyona dikkat
  80–160 mm: Normal — kabul
  160–200 mm: İzleme gerekli — su/çimento yüksekse reddet
  >200 mm veya çökmüş: REDDET, irsaliyeye "Red" yaz, şantiye defterine kaydet

■ 28 GÜNLÜK BASINÇ SONUCU:
  Tasarım değerinin ≥%100: Kabul
  %85–99: Numune/kür sorunu olabilir → Karot al, karşılaştır
  %75–84: Yapı denetçisine bildir, yük taşıma kapasitesi değerlendirmesi iste
  <%75   : Yapı denetçisi + statik mühendisi → kabul mümkün değil, işlem durdur

■ KAROT SONUCU:
  Tasarım fcm'nin %85'i üstü: Genellikle kabul
  Altında: Yapı denetçisi kararı — bu modülün kapsamı dışı

■ İSG DURUMU:
  Baret/emniyet kemeri eksikliği → UYARI: Çalışmayı durdur. 6331 md.17 gereği
  İskele korkuluğu eksik → UYARI: Boşluğu barikat ile kapat, sonra devam et
  İskele mesafesi fazla → TS EN 12811 maksimum 3.0 m aralık

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DİL KURALLARI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Müteahhit ve formen dilinde yaz — teknik terim kullan ama açıkla
- "Yaklaşık" veya "belki" kullanma → somut ürün adı, somut miktar, somut süre ver
- Maliyet tahmini her cevapta zorunlu
- Acil güvenlik riski → cevabın başına UYARI: ekle, önce dur dedikten sonra çöz
"""

# ── Gayrimenkul Değerleme Uzmanı Sistem Promptu ───────────────────────────

GAYRIMENKUL_SISTEM_PROMPT = """Sen Türkiye'nin en deneyimli SPK lisanslı gayrimenkul değerleme uzmanısın.
20 yıllık sektör tecrübesiyle İstanbul, Ankara, İzmir başta olmak üzere Türkiye'nin
tüm şehirlerindeki gayrimenkul piyasasını avucunun içi gibi biliyorsun.

SENİN TEMEL KURALLARIN:
1. ASLA tahmin yürütme — bildiklerini kullan, bilmiyorsan açıkça söyle
2. Kullanıcıya gerçek, sahaya uygulanabilir bilgi ver
3. "Yaklaşık", "tahminen", "belki" yerine somut aralıklar ver
4. İlan fiyatının gerçek değerin ne kadar üstünde/altında olduğunu söyle
5. AL / BEKLE / ALMA kararını net ver, gerekçesini açıkla

DEĞERLEME METODOLOJİN:

▶ ADIM 1 — MÜLK VERİSİ AL
Kullanıcı formu doldurmuş olarak gelir — fiyat, m², konum, oda sayısı, bina yaşı, tapu türü vb.
Eğer herhangi bir bilgi eksikse kısaca sor. Ekran görüntüsü gönderilmişse görselden verileri oku.

▶ ADIM 2 — BÖLGE PİYASASINI DEĞERLENDİR
emsal_karsilastir aracını çağır. Araç çalışsın ya da çalışmasın,
KENDİ BİLDİKLERİNİ KULLAN — sen bu piyasayı biliyorsun.

Bildiğin gerçek piyasa verileri (2024–2025 sonu itibarıyla):

İSTANBUL — SATILIK DAİRE m² FİYATLARI (ortalama):
  Beşiktaş, Şişli, Sarıyer: 120.000–250.000 ₺/m²
  Kadıköy, Moda, Fenerbahçe: 90.000–160.000 ₺/m²
  Üsküdar, Ataşehir: 65.000–120.000 ₺/m²
  Bakırköy, Bahçelievler, Zeytinburnu: 55.000–100.000 ₺/m²
  Beylikdüzü, Esenyurt, Avcılar: 30.000–55.000 ₺/m²
  Bağcılar, Esenler, Sultangazi: 28.000–50.000 ₺/m²
  Pendik, Kartal, Maltepe: 45.000–85.000 ₺/m²
  Başakşehir, Kağıthane: 50.000–90.000 ₺/m²
  Arnavutköy, Silivri, Çatalca: 18.000–40.000 ₺/m²

ANKARA — SATILIK DAİRE m² FİYATLARI:
  Çankaya (Kavaklıdere, Gaziosmanpaşa): 35.000–75.000 ₺/m²
  Çankaya (genel): 22.000–45.000 ₺/m²
  Yenimahalle, Etimesgut: 18.000–35.000 ₺/m²
  Keçiören: 14.000–28.000 ₺/m²
  Mamak, Altındağ, Sincan: 10.000–22.000 ₺/m²

İZMİR — SATILIK DAİRE m² FİYATLARI:
  Konak, Alsancak, Karşıyaka: 40.000–85.000 ₺/m²
  Bornova, Bayraklı: 28.000–55.000 ₺/m²
  Buca, Gaziemir: 22.000–42.000 ₺/m²
  Çiğli, Menemen: 18.000–35.000 ₺/m²

ANTALYA: Muratpaşa/Lara: 35.000–80.000 | Kepez: 18.000–35.000 ₺/m²
BURSA: Nilüfer: 22.000–48.000 | Osmangazi: 20.000–42.000 ₺/m²
TRABZON: 12.000–28.000 | GAZİANTEP: 10.000–22.000 ₺/m²
DİĞER İL MERKEZLERİ: 8.000–20.000 ₺/m² (konuma göre)

KİRALIK — KABA KIRA/SATIŞ ORANI:
  İstanbul merkezi: %2,5–3,5 brüt yıllık
  İstanbul çevre: %3,5–5,5 brüt yıllık
  Ankara, İzmir: %3–5 brüt yıllık
  Taşra: %5–8 brüt yıllık

ARSA/TARLA (İMAR DURUMU KRİTİK):
  İstanbul imarlı arsa: 3.000–80.000+ ₺/m² (konuma göre dev fark)
  Ankara imarlı arsa: 1.500–25.000 ₺/m²
  Tarla (tarım arazisi): 50–2.000 ₺/m² (il ve ulaşıma göre)

▶ ADIM 3 — DÜZELTME FAKTÖRLERİ UYGULA
Baz fiyata şu düzeltmeleri yap:
  Sıfır bina: +%15–20
  0–5 yaş: +%10
  15–25 yaş: -%8–12
  25+ yaş: -%15–30 (ruhsatına bak, deprem yönetmeliği öncesi mi?)
  Zemin kat: -%10–20
  Gürültülü cadde: -%5–10
  Deniz/boğaz manzarası: +%20–50
  Şehir manzarası: +%8–15
  Kat mülkiyeti: baz fiyat
  Kat irtifakı: -%5–8
  Hisseli tapu: -%15–25 (artı risk primi)
  Site içi (güvenlik, sosyal): +%5–10
  Otopark: +%3–5
  Metro <500m: +%8–15

▶ ADIM 4 — RAPOR ÜRET
gayrimenkul_degerle aracını çağır, tüm hesaplanmış değerleri ver.

RAPOR FORMATI (her değerlemede zorunlu):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏠 GAYRİMENKUL DEĞERLEME RAPORU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 MÜLK BİLGİLERİ
  [konum, tip, m², oda, kat/toplam kat, yaş, tapu]

📊 EMSAL ANALİZİ
  Bölge m² ortalaması: X.XXX — Y.YYY ₺/m²
  Düzeltilmiş m²: Z.ZZZ ₺/m²
  [Düzeltme gerekçeleri maddeler halinde]

💰 DEĞERLEME SONUCU
  ■ Minimum değer: X.XXX.XXX ₺
  ■ Orta değer  : Y.YYY.YYY ₺  ← Gerçekçi piyasa değeri
  ■ Maximum değer: Z.ZZZ.ZZZ ₺

📋 İLAN FİYATI KARŞILAŞTIRMASI (ilan varsa)
  İlan fiyatı: A.AAA.AAA ₺
  Piyasaya göre: %X [pahalı/uygun/ucuz] — [gerekçe]

🏦 KİRA GETİRİSİ
  Tahmini aylık kira: X.XXX — Y.YYY ₺
  Brüt yıllık getiri: %X,X
  Geri ödeme (gerçek değerden): XX yıl
  [Geri ödeme yorumu SADECE şu kriterlere göre yap — başka ifade kullanma:]
    < 15 yıl  → "İyi getiri"
    15–20 yıl → "Orta getiri"
    20–25 yıl → "Zayıf getiri"
    > 25 yıl  → "Düşük getiri"
  ["Taşra", "büyükşehir", "merkez" gibi coğrafi yorum EKLEME — sadece süreyi değerlendir]

⭐ YATIRIM PUANI: X/10
  [Puanın gerekçesi 2–3 cümle]

⚠️ RİSK FAKTÖRLERİ
  [Varsa: tapu sorunu, deprem riski, imar sorunu, piyasa riski]

✅ KARAR: AL / BEKLE / ALMA
  [Net gerekçe — müteahhit/yatırımcı dilinde]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SON KURAL: Eğer kullanıcının verdiği fiyat gerçek piyasa değerinin çok
üstündeyse bunu açıkça söyle. "Fiyat yüksek" deme — "Bu fiyattan alma,
piyasa değeri X TL, %Y fazla istiyor" de. Kullanıcı para kaybetmesin.
"""

# ── Araç Tanımları ─────────────────────────────────────────────────────────

ARACLAR = [
    {
        "name": "verimlilik_sure_hesapla",
        "description": (
            "CŞB birim fiyat analizlerine göre bir iş için gereken iş günü sayısını hesaplar. "
            "Formül: süre = ceil(miktar / (verimlilik × usta_sayısı)). "
            "Verimlilik değerleri Çevre Şehircilik Bakanlığı resmi analizlerine dayanır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "is_tipi": {
                    "type": "string",
                    "description": (
                        "İş tipi adı. Örnek: 'Kalıp Döşeme', 'Demir Bağlama', "
                        "'İç Sıva', 'Fayans/Seramik', 'Nervürlü Soğuk Demir'"
                    )
                },
                "miktar": {
                    "type": "number",
                    "description": "İş miktarı (birim cinsinden: m², kg, m³)"
                },
                "usta_sayisi": {
                    "type": "integer",
                    "description": "Çalışacak usta/işçi sayısı (en az 1)"
                }
            },
            "required": ["is_tipi", "miktar", "usta_sayisi"]
        }
    },
    {
        "name": "kaba_yapi_maliyet",
        "description": (
            "İnşaat alanı ve yapı sistemine göre kaba yapı maliyet tahmini hesaplar. "
            "Katsayılar CŞB standartlarına dayalıdır (beton m³/m², kalıp m²/m², demir kg/m²). "
            "2026 Q1 piyasa fiyatları kullanılır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "alan_m2": {
                    "type": "number",
                    "description": "Toplam inşaat alanı (m²)"
                },
                "yapi_sistemi": {
                    "type": "string",
                    "description": (
                        "Yapı sistemi. Seçenekler: 'Betonarme Çerçeve', "
                        "'Betonarme Perde+Çerçeve', 'Yığma Tuğla', 'Çelik Konstrüksiyon'"
                    )
                },
                "birim_fiyat_beton": {
                    "type": "number",
                    "description": "Hazır beton birim fiyatı TL/m³ (opsiyonel, varsayılan: 4800)"
                },
                "birim_fiyat_demir": {
                    "type": "number",
                    "description": "Demir birim fiyatı TL/kg (opsiyonel, varsayılan: 38)"
                }
            },
            "required": ["alan_m2", "yapi_sistemi"]
        }
    },
    {
        "name": "proje_metraj_listesi",
        "description": (
            "Aktif projenin metraj kalemlerini, miktarlarını, birim fiyatlarını ve "
            "toplam maliyetini listeler. Proje analizi ve optimizasyon için kullanılır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "gantt_gorevleri_getir",
        "description": (
            "Aktif Gantt iş programındaki mevcut görevleri listeler. "
            "İş planı hazırlamak için projenin mevcut durumunu görmek amacıyla kullanılır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "metraj_kalem_ekle",
        "description": (
            "Aktif projeye tek bir metraj kalemi ekler. "
            "Poz no, iş kalemi adı, miktar, birim, birim fiyat ve kategori bilgilerini alır. "
            "Ekleme sonrası kalem ID'si ve hesaplanan toplam tutarı döndürür."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "poz_no": {
                    "type": "string",
                    "description": "Poz numarası (örn: '16.001/1')"
                },
                "is_kalemi": {
                    "type": "string",
                    "description": "İş kalemi tanımı / açıklaması"
                },
                "miktar": {
                    "type": "number",
                    "description": "Metraj miktarı (sayısal değer)"
                },
                "birim": {
                    "type": "string",
                    "description": "Birim (m², m³, ton, adet, m, kg vb.)"
                },
                "birim_fiyat": {
                    "type": "number",
                    "description": "Birim fiyat (TL)"
                },
                "kategori": {
                    "type": "string",
                    "description": "Kategori (Hafriyat, Beton İşleri, Demir İşleri, Kalıp İşleri, Duvar İşleri, Sıva/Boya, Kaplama, Tesisat, vb.)"
                }
            },
            "required": ["poz_no", "is_kalemi", "miktar", "birim", "birim_fiyat"]
        }
    },
    {
        "name": "metraj_toplu_ekle",
        "description": (
            "Aktif projeye birden fazla metraj kalemini tek seferde ekler. "
            "kalemler listesindeki her öğe: poz_no, is_kalemi, miktar, birim, birim_fiyat, kategori içermelidir. "
            "Toplu aktarım için bu aracı kullan — tek tek metraj_kalem_ekle çağırmak yerine daha verimlidir."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kalemler": {
                    "type": "array",
                    "description": "Eklenecek metraj kalemleri listesi",
                    "items": {
                        "type": "object",
                        "properties": {
                            "poz_no": {"type": "string"},
                            "is_kalemi": {"type": "string"},
                            "miktar": {"type": "number"},
                            "birim": {"type": "string"},
                            "birim_fiyat": {"type": "number"},
                            "kategori": {"type": "string"}
                        },
                        "required": ["poz_no", "is_kalemi", "miktar", "birim", "birim_fiyat"]
                    }
                }
            },
            "required": ["kalemler"]
        }
    },
    {
        "name": "gantt_gorev_ekle",
        "description": (
            "Aktif Gantt iş programına tek bir görev ekler. "
            "sure=0 gönderilirse CŞB verimlilik tablosundan otomatik hesaplanır. "
            "oncul: bağımlı olduğu görev ID'leri virgülle ayrılmış (örn: '1,2,3'). "
            "Başarılı eklemede görev ID'si ve hesaplanan süre döner."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ad": {
                    "type": "string",
                    "description": "Görev adı (iş kalemi)"
                },
                "sure_gun": {
                    "type": "integer",
                    "description": "Süre (iş günü). 0 gönderilirse miktar+is_tipi'nden CŞB ile hesaplanır."
                },
                "miktar": {
                    "type": "number",
                    "description": "İş miktarı (CŞB süre hesabı için gerekli)"
                },
                "birim": {
                    "type": "string",
                    "description": "Birim (m², m³, kg, ton vb.)"
                },
                "is_tipi": {
                    "type": "string",
                    "description": "İş tipi — CŞB verimlilik eşleştirmesi için (örn: 'Kalıp Döşeme', 'Demir Bağlama')"
                },
                "ekip_sayisi": {
                    "type": "integer",
                    "description": "Ekip/usta sayısı (varsayılan: 3)"
                },
                "oncul": {
                    "type": "string",
                    "description": "Öncül görev ID'leri virgülle ayrılmış (örn: '1,2'). FS bağımlılığı."
                },
                "kaynak": {
                    "type": "string",
                    "description": "Atanan kaynak/ekip adı"
                },
                "baslangic_gun": {
                    "type": "integer",
                    "description": "Başlangıç günü (gün offset, varsayılan: 0)"
                }
            },
            "required": ["ad"]
        }
    },
    {
        "name": "gantt_toplu_ekle",
        "description": (
            "Gantt iş programına birden fazla görevi tek seferde ekler. "
            "Tüm 30 kalemlik bir iş programını tek çağrıda oluşturmak için kullanılır. "
            "gorevler listesindeki her öğe: ad, sure_gun, miktar, birim, is_tipi, ekip_sayisi, oncul, kaynak içerebilir."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gorevler": {
                    "type": "array",
                    "description": "Eklenecek görev listesi",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ad": {"type": "string"},
                            "sure_gun": {"type": "integer"},
                            "miktar": {"type": "number"},
                            "birim": {"type": "string"},
                            "is_tipi": {"type": "string"},
                            "ekip_sayisi": {"type": "integer"},
                            "oncul": {"type": "string"},
                            "kaynak": {"type": "string"},
                            "baslangic_gun": {"type": "integer"}
                        },
                        "required": ["ad"]
                    }
                }
            },
            "required": ["gorevler"]
        }
    },
    {
        "name": "ekap_ihale_ara",
        "description": (
            "EKAP (Elektronik Kamu Alımları Platformu) üzerinden kamu ihalelerini arar. "
            "Yapım işi, hizmet alımı veya mal alımı ihalelerini il, tür ve tarih aralığına göre filtreler. "
            "Kullanıcı 'ihale ara', 'kamu ihalesi', 'yapım işi ihale' gibi ifadeler kullandığında çağır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "anahtar_kelime": {
                    "type": "string",
                    "description": "Arama anahtar kelimesi (ihale adı veya IKN)"
                },
                "il": {
                    "type": "string",
                    "description": "İl adı (örn: 'İstanbul', 'Ankara')"
                },
                "ihale_turu": {
                    "type": "string",
                    "description": "İhale türü ID: 1=Yapım İşi, 2=Hizmet Alımı, 3=Mal Alımı, 4=Danışmanlık"
                },
                "baslangic_tarihi": {
                    "type": "string",
                    "description": "Başlangıç tarihi (dd.mm.yyyy formatı)"
                },
                "bitis_tarihi": {
                    "type": "string",
                    "description": "Bitiş tarihi (dd.mm.yyyy formatı)"
                },
                "sayfa_boyutu": {
                    "type": "integer",
                    "description": "Sayfa başına sonuç sayısı (varsayılan: 20)"
                }
            },
            "required": []
        }
    },
    {
        "name": "hakedis_hesapla",
        "description": (
            "Sözleşme bedeli ve tamamlanma yüzdesine göre KDV, stopaj, teminat kesintileri dahil "
            "hakediş tutarını hesaplar. 4734/4735 Sayılı KİK mevzuatına uygun hesaplama. "
            "Kullanıcı 'hakediş', 'ara hakediş', 'ödeme tutarı' sorduğunda çağır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sozlesme_bedeli": {
                    "type": "number",
                    "description": "Sözleşme bedeli (TL, KDV hariç)"
                },
                "tamamlanma_yuzdesi": {
                    "type": "number",
                    "description": "Tamamlanma yüzdesi (0-100 arası, örn: 45.5)"
                },
                "onceki_hakedis_yuzdesi": {
                    "type": "number",
                    "description": "Önceki hakediş tamamlanma yüzdesi (ilk hakedişte 0)"
                },
                "kdv_orani": {
                    "type": "number",
                    "description": "KDV oranı (varsayılan: 20)"
                },
                "stopaj_orani": {
                    "type": "number",
                    "description": "Gelir vergisi stopaj oranı % (varsayılan: 3)"
                },
                "damga_vergisi_orani": {
                    "type": "number",
                    "description": "Damga vergisi oranı % (varsayılan: 0.948)"
                }
            },
            "required": ["sozlesme_bedeli", "tamamlanma_yuzdesi"]
        }
    },
    {
        "name": "gecikme_ceza_hesapla",
        "description": (
            "4735 Sayılı KİK Kanunu 20. maddesine göre gecikme cezası hesaplar. "
            "Günlük binde beş (‰5 = %0.5/gün) oranında ceza, fesih eşiği %30. "
            "Kullanıcı 'gecikme cezası', 'ceza hesabı', 'fesih eşiği' sorduğunda çağır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sozlesme_bedeli": {
                    "type": "number",
                    "description": "Sözleşme bedeli (TL)"
                },
                "gecikme_gun_sayisi": {
                    "type": "integer",
                    "description": "Gecikme gün sayısı"
                },
                "onceki_ceza_yuzdesi": {
                    "type": "number",
                    "description": "Daha önce kesilmiş toplam ceza yüzdesi (varsayılan: 0)"
                }
            },
            "required": ["sozlesme_bedeli", "gecikme_gun_sayisi"]
        }
    },
    {
        "name": "gantt_dosya_iceri_aktar",
        "description": (
            "Bir dosyadan (Excel .xlsx, CSV .csv veya JSON .json) Gantt görevlerini içeri aktarır. "
            "dosya_yolu parametresi tam dosya yolunu alır. "
            "mod='yenile' mevcut programı sıfırlar, mod='ekle' mevcut programa ekler (varsayılan). "
            "Kullanıcı sana bir dosya yolu verdiğinde bunu kullan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dosya_yolu": {
                    "type": "string",
                    "description": "İçeri aktarılacak dosyanın tam yolu (.xlsx, .csv veya .json)"
                },
                "mod": {
                    "type": "string",
                    "description": "İçeri aktarma modu: 'ekle' (varsayılan) veya 'yenile'"
                }
            },
            "required": ["dosya_yolu"]
        }
    },
    # ── Saha Çözüm Araçları ────────────────────────────────────────────────
    {
        "name": "saha_sorun_tani",
        "description": (
            "Şantiye sahası sorununun yapılandırılmış teknik analizini yapar. "
            "Sorun kategorisini, ilgili yönetmelikleri (TS 500, TBDY 2018, TS EN 206 vb.) "
            "ve çözüm çerçevesini belirler. "
            "Her saha problemi bildirildiğinde bu aracı kullan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sorun_tanimi": {
                    "type": "string",
                    "description": "Sorunun serbest metin tanımı (örn: 'perde betonunda segregasyon oluştu')"
                },
                "yapi_turu": {
                    "type": "string",
                    "description": "Yapı türü: 'Betonarme', 'Çelik', 'Yığma', 'Karma'"
                },
                "imalat_asamasi": {
                    "type": "string",
                    "description": (
                        "İmalat aşaması: 'Hafriyat', 'Temel', 'Bodrum', 'Kaba Yapı', "
                        "'İnce İşler', 'Dış Cephe', 'Teslim Sonrası'"
                    )
                },
                "aciliyet": {
                    "type": "string",
                    "description": "Aciliyet: 'Kritik' (iş durdurulmalı), 'Yüksek', 'Orta', 'Düşük'"
                }
            },
            "required": ["sorun_tanimi"]
        }
    },
    {
        "name": "malzeme_test_degerlendir",
        "description": (
            "Malzeme test sonucunu ilgili standartlara (TS 500, TS EN 206, TBDY 2018) "
            "göre değerlendirir. Beton basınç dayanımı, slump, demir çekme/akma, "
            "zemin CBR vb. için KABUL / RED kararı verir ve acil önlemleri listeler."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "malzeme_turu": {
                    "type": "string",
                    "description": "Malzeme türü: 'Beton', 'Demir/Donatı', 'Zemin', 'Sıva/Harç', 'Tuğla/Blok'"
                },
                "test_turu": {
                    "type": "string",
                    "description": (
                        "Test türü: 'Basınç Dayanımı', 'Slump/Kıvam', 'Çekme Dayanımı', "
                        "'Akma Dayanımı', 'Su/Çimento Oranı', 'CBR', 'Sıkışma'"
                    )
                },
                "olculen_deger": {
                    "type": "number",
                    "description": "Ölçülen test değeri (sayısal)"
                },
                "birim": {
                    "type": "string",
                    "description": "Birimi: 'MPa', 'N/mm²', 'kg/cm²', 'mm', '%'"
                },
                "beton_sinifi": {
                    "type": "string",
                    "description": "Beton sınıfı: 'C20', 'C25', 'C30', 'C35', 'C40' (beton testlerinde)"
                }
            },
            "required": ["malzeme_turu", "test_turu", "olculen_deger", "birim"]
        }
    },
    {
        "name": "isg_risk_degerlendirme",
        "description": (
            "6331 Sayılı İSG Kanunu ve Yapı İşlerinde Güvenlik Yönetmeliğine göre "
            "şantiye risk değerlendirmesi yapar. Çalışma türüne, yüksekliğe ve personel "
            "sayısına göre risk seviyesi belirler, zorunlu tedbirleri listeler."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "calisma_turu": {
                    "type": "string",
                    "description": (
                        "Çalışma türü: 'Kazı/Hafriyat', 'Kalıp/İskele', 'Beton Dökümü', "
                        "'Demir İşleri', 'Yüksekte Çalışma', 'Çatı', 'Elektrik', 'Vinç/Kaldırma'"
                    )
                },
                "yukseklik_m": {
                    "type": "number",
                    "description": "Çalışma yüksekliği metre cinsinden (yüksekte çalışma için)"
                },
                "personel_sayisi": {
                    "type": "integer",
                    "description": "Aynı anda çalışacak kişi sayısı"
                },
                "ortam": {
                    "type": "string",
                    "description": "Ortam: 'Açık Hava', 'Kapalı Alan', 'Dar Kapalı Alan', 'Su Kenarı'"
                }
            },
            "required": ["calisma_turu"]
        }
    },
    # ── Gayrimenkul Değerleme Araçları ─────────────────────────────────────
    {
        "name": "emsal_karsilastir",
        "description": (
            "Belirtilen bölge ve gayrimenkul tipine göre emsal m² fiyatlarını, "
            "kira getirisi oranlarını ve piyasa trendini analiz eder. "
            "Değerleme öncesi bölge fiyat araştırması için kullan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "il": {
                    "type": "string",
                    "description": "İl adı (örn: 'İstanbul', 'Ankara')"
                },
                "ilce": {
                    "type": "string",
                    "description": "İlçe adı (örn: 'Kadıköy', 'Çankaya')"
                },
                "mahalle": {
                    "type": "string",
                    "description": "Mahalle adı (opsiyonel)"
                },
                "mulk_tipi": {
                    "type": "string",
                    "description": "Mülk tipi: 'Daire', 'Villa', 'Arsa', 'Tarla', 'Dükkan/Ofis', 'Bina'"
                },
                "alan_m2": {
                    "type": "number",
                    "description": "Mülk alanı m² (opsiyonel, karşılaştırma için)"
                }
            },
            "required": ["il", "mulk_tipi"]
        }
    },
    {
        "name": "gayrimenkul_degerle",
        "description": (
            "Tüm toplanan verilerle kapsamlı gayrimenkul değerleme raporu üretir. "
            "Emsal karşılaştırma, gelir ve maliyet yaklaşımlarını birleştirerek "
            "min-maks piyasa değeri, kira getirisi ve yatırım puanı hesaplar. "
            "Tüm veriler hazır olduğunda bu aracı kullan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mulk_tipi": {
                    "type": "string",
                    "description": "Mülk tipi: 'Daire', 'Villa', 'Arsa', 'Tarla', 'Dükkan/Ofis', 'Bina'"
                },
                "il": {"type": "string", "description": "İl"},
                "ilce": {"type": "string", "description": "İlçe"},
                "mahalle": {"type": "string", "description": "Mahalle (opsiyonel)"},
                "alan_m2": {
                    "type": "number",
                    "description": "Mülk alanı m²"
                },
                "oda_sayisi": {
                    "type": "string",
                    "description": "Oda sayısı (daireler için, örn: '3+1', '2+1')"
                },
                "bina_yasi": {
                    "type": "integer",
                    "description": "Bina yaşı (yıl)"
                },
                "kat": {
                    "type": "string",
                    "description": "Kat bilgisi (örn: '3/8', 'Zemin', 'Çatı')"
                },
                "tapu_turu": {
                    "type": "string",
                    "description": "Tapu türü: 'Kat Mülkiyeti', 'Kat İrtifakı', 'Arsa Tapusu', 'Hisseli', 'Zilyetlik'"
                },
                "ilan_fiyati": {
                    "type": "number",
                    "description": "İlandaki satış fiyatı TL (opsiyonel, piyasa karşılaştırması için)"
                },
                "ozellikler": {
                    "type": "string",
                    "description": "Ek özellikler: manzara, otopark, asansör, site içi vb."
                },
                "imar_durumu": {
                    "type": "string",
                    "description": "İmar durumu (arsa/tarla için): 'Konut', 'Ticari', 'Tarım', 'Karma', 'İmarsız'"
                },
                "ticari_kat": {
                    "type": "string",
                    "description": "Ticari mülk kat konumu: 'Zemin', 'Asma', '1. Kat', '2. Kat ve Uzeri', 'AVM Ici'"
                },
                "cephe_turu": {
                    "type": "string",
                    "description": "Ticari mülk cephe türü: 'Ana Cadde', 'Sokak/Ara Yol', 'Pasaj/Carsi Ici', 'AVM Ici'"
                },
                "mevcut_kira_aylik": {
                    "type": "number",
                    "description": "Mevcut aylık kira geliri TL (dükkan/ofis için, opsiyonel)"
                },
                "ada_no": {
                    "type": "string",
                    "description": "Tapu ada numarası (opsiyonel)"
                },
                "parsel_no": {
                    "type": "string",
                    "description": "Tapu parsel numarası (opsiyonel)"
                }
            },
            "required": ["mulk_tipi", "il", "alan_m2"]
        }
    },
]

# ── Analiz ve Planlama Promptları ──────────────────────────────────────────

PROJE_ANALIZ_PROMPT = """Aktif projenin aşağıdaki verilerine dayanarak kapsamlı bir proje analizi yap:

{proje_baglam}

Lütfen sırasıyla şu başlıklar altında analiz et:

1. **Genel Değerlendirme** — Proje kapsamı, maliyet seviyesi, genel izlenim
2. **Maliyet Analizi** — Hangi iş kalemleri toplam maliyette büyük pay tutuyor? Birim fiyatlar piyasayla uyumlu mu?
3. **Risk Alanları** — Gecikme, maliyet aşımı, eksik kalem riski taşıyan konular
4. **Eksik Kalemler** — Bu tür bir projede genellikle bulunması gereken ancak listede görünmeyen kalemler
5. **Optimizasyon Önerileri** — Maliyet düşürme veya etkinlik artırma fırsatları
6. **Yasal Kontrol** — KDV, stopaj, damga vergisi, teminat açısından dikkat edilmesi gerekenler

Yanıtını madde madde, net ve uygulanabilir tut. Saha müteahhidine hitap eden sade bir dil kullan."""

GANTT_PLAN_PROMPT = """Sen deneyimli bir inşaat proje yöneticisisin.

Aşağıdaki proje bilgilerine dayanarak gerçekçi ve uygulanabilir bir Gantt iş programı hazırla:

{proje_baglam}

KURALLAR:
- CŞB birim fiyat analizlerindeki verimlilik değerlerini kullan
- Türkiye resmi tatillerini ve mevsimsel kısıtları göz önünde bulundur
- Mantıklı bir bağımlılık sırası kur (temel bitmeden kolon olmaz vb.)
- Gerçekçi süreler ver, iş kalemlerini fazla bölme

ÇIKTI FORMATI — Açıklamadan sonra mutlaka şu bloku yaz:

GANTT_PLAN_BASLANGIC
sıra|iş_adı|süre_gün|kaynak|bağımlılık
1|Hafriyat ve Kazı|10|Kazıcı/Hafriyatçı|Yok
2|Temel Kalıp ve Demiri|8|Kalıpçı + Demirci|1
3|Temel Betonu|5|Betoncu|2
GANTT_PLAN_BITIS

Bağımlılık sütununa önceki görevin sıra numarasını yaz; bağımsızsa "Yok" yaz.
Birden fazla bağımlılık varsa "2,3" formatında yaz."""


# ── Yardımcı Fonksiyon ─────────────────────────────────────────────────────

def _content_blocks_to_dict(content_blocks) -> list:
    """Anthropic SDK content bloklarını mesaj formatına uygun dict listesine dönüştürür."""
    result = []
    for block in content_blocks:
        if not hasattr(block, "type"):
            continue
        if block.type == "text":
            result.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return result


# ── Thread: Streaming (Sohbet Modu) ───────────────────────────────────────

class ClaudeAsistanThread(QThread):
    """Claude API streaming yanıt thread — Sohbet modu."""

    yanit_parcasi = pyqtSignal(str)
    hata_olustu = pyqtSignal(str)
    islem_bitti = pyqtSignal()

    def __init__(self, api_key: str, mesajlar: list, model: str):
        super().__init__()
        self.api_key = api_key
        self.mesajlar = mesajlar
        self.model = model
        self._iptal = False

    def iptal_et(self):
        self._iptal = True

    def run(self):
        try:
            if not _ANTHROPIC_OK:
                raise ImportError(
                    "anthropic paketi kurulu değil.\n"
                    "Lütfen terminalde şunu çalıştırın:\n"
                    r'"E:\İNŞAAT METRAJ PRO\.venv\Scripts\pip.exe" install anthropic'
                )
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            with client.messages.stream(
                model=self.model,
                max_tokens=2048,
                system=SISTEM_PROMPT,
                messages=self.mesajlar,
            ) as stream:
                for text in stream.text_stream:
                    if self._iptal:
                        break
                    self.yanit_parcasi.emit(text)
            self.islem_bitti.emit()
        except Exception as e:
            self.hata_olustu.emit(str(e))
            self.islem_bitti.emit()


# ── Thread: Tool Use (Hesap Asistanı + Analiz Modu) ───────────────────────

class ClaudeAracliThread(QThread):
    """
    Claude API araç kullanımı (tool use) destekli thread.

    Hesap Asistanı, Proje Analizi ve Gantt Planlama modları için kullanılır.
    Döngü: istek → araç çağrısı → Python fonksiyonu → sonuç → Claude → nihai yanıt
    """

    yanit_tamamlandi = pyqtSignal(str)    # Nihai tam yanıt metni
    arac_cagrildi = pyqtSignal(str, str)  # (arac_adi, sonuc) — UI'da gösterilir
    hata_olustu = pyqtSignal(str)
    islem_bitti = pyqtSignal()

    def __init__(self, api_key: str, mesajlar: list, model: str, arac_callback,
                 sistem_prompt: str = None):
        super().__init__()
        self.api_key = api_key
        self.mesajlar = mesajlar
        self.model = model
        self.arac_callback = arac_callback  # callable(arac_adi: str, params: dict) -> str
        self._sistem_prompt = sistem_prompt if sistem_prompt else SISTEM_PROMPT
        self._iptal = False

    def iptal_et(self):
        self._iptal = True

    def run(self):
        try:
            if not _ANTHROPIC_OK:
                raise ImportError(
                    "anthropic paketi kurulu değil.\n"
                    "Lütfen terminalde şunu çalıştırın:\n"
                    r'"E:\İNŞAAT METRAJ PRO\.venv\Scripts\pip.exe" install anthropic'
                )
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            messages = list(self.mesajlar)

            max_dongu = 10  # sonsuz döngü koruması
            dongu = 0

            while dongu < max_dongu:
                if self._iptal:
                    break
                dongu += 1

                response = client.messages.create(
                    model=self.model,
                    max_tokens=3000,
                    system=self._sistem_prompt,
                    tools=ARACLAR,
                    messages=messages,
                )

                if response.stop_reason == "tool_use":
                    # 1. Asistan cevabını dict formatında messages'a ekle
                    messages.append({
                        "role": "assistant",
                        "content": _content_blocks_to_dict(response.content),
                    })

                    # 2. Her tool_use bloğunu işle
                    tool_results = []
                    for block in response.content:
                        if self._iptal:
                            break
                        if not hasattr(block, "type") or block.type != "tool_use":
                            continue
                        sonuc = self.arac_callback(block.name, block.input)
                        self.arac_cagrildi.emit(block.name, sonuc)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": sonuc,
                        })

                    if not tool_results:
                        break

                    # 3. Araç sonuçlarını messages'a ekle — döngü devam eder
                    messages.append({"role": "user", "content": tool_results})

                elif response.stop_reason == "end_turn":
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text
                    self.yanit_tamamlandi.emit(final_text)
                    break

                else:
                    # Beklenmedik stop reason — mevcut metni gönder
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text
                    if final_text:
                        self.yanit_tamamlandi.emit(final_text)
                    break

            self.islem_bitti.emit()

        except Exception as e:
            self.hata_olustu.emit(str(e))
            self.islem_bitti.emit()


# ── ClaudeEngine ───────────────────────────────────────────────────────────

class ClaudeEngine:
    """Claude API yönetim sınıfı — İnşaat asistanı motor."""

    DESTEKLENEN_MODELLER = [
        ("claude-sonnet-4-6",         "Claude Sonnet 4.6 (Önerilen)"),
        ("claude-opus-4-6",           "Claude Opus 4.6 (Güçlü)"),
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5 (Hızlı)"),
    ]

    def __init__(self):
        self.api_key: str = ""
        self.model: str = "claude-sonnet-4-6"
        self.gecmis: List[Dict[str, str]] = []
        self._active_thread = None
        self._aktif_konusma_id: str = ""  # disk'e kaydedilmiş aktif konuşma ID'si

        # Bağlam referansları
        self._db = None
        self._proje_id: Optional[int] = None
        self._gantt_engine = None
        self._gantt_window = None   # GanttWindow ref — _is_list güncellemesi için

        self._yukle_config()

    # ── Config ──────────────────────────────────────────────────────────────

    def _yukle_config(self):
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.api_key = cfg.get("api_key", "")
                self.model = cfg.get("model", "claude-sonnet-4-6")
        except Exception as e:
            logger.warning(f"Claude config yüklenemedi: {e}")

    def kaydet_config(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.api_key = api_key.strip()
        self.model = model
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"api_key": self.api_key, "model": model}, f,
                          ensure_ascii=False, indent=2)
            logger.info("Claude config kaydedildi.")
        except Exception as e:
            logger.error(f"Claude config kaydedilemedi: {e}")

    def api_key_gecerli(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("sk-ant-"))

    # ── Bağlam Yönetimi ─────────────────────────────────────────────────────

    def set_proje_baglam(self, db, proje_id: Optional[int]):
        """Veritabanı ve proje bağlamını ayarla."""
        self._db = db
        self._proje_id = proje_id

    def set_gantt_engine(self, gantt_engine):
        """Gantt engine referansını ayarla."""
        self._gantt_engine = gantt_engine

    def set_gantt_window(self, gantt_window):
        """GanttWindow referansını ayarla — _is_list güncelleme için gerekli."""
        self._gantt_window = gantt_window
        if gantt_window is not None and self._gantt_engine is None:
            self._gantt_engine = getattr(gantt_window, '_engine', None)

    def _task_to_is_dict(self, tid: int, ad: str, sure_gun: int,
                         miktar: float, birim: str, ekip: int,
                         kaynak: str, oncul_listesi: list) -> dict:
        """GanttWindow._is_list formatında görev dict'i üretir."""
        return {
            "id": tid,
            "ad": ad,
            "sure": sure_gun,           # dikkat: 'sure' (sure_gun değil)
            "miktar": miktar,
            "miktar_birim": birim or "adet",
            "ekip_turu": f"Ekip ({ekip} kişi)" if ekip else "",
            "kaynak": kaynak or "",
            "milestone": False,
            "bagimliliklar": [int(p) for p in oncul_listesi if str(p).isdigit()],
            "bagimliliklar_detay": [
                {"id": int(p), "tip": "FS", "lag": 0}
                for p in oncul_listesi if str(p).isdigit()
            ],
            "butce": 0.0,
            "birim_fiyat": 0.0,
            "gercek_maliyet": 0.0,
        }

    # ── Sohbet Geçmişi ──────────────────────────────────────────────────────

    def gecmis_temizle(self):
        self.gecmis.clear()
        self._aktif_konusma_id = ""

    def mesaj_ekle_kullanici(self, icerik: str):
        self.gecmis.append({"role": "user", "content": icerik})
        self._gecmis_kisalt()

    def mesaj_ekle_asistan(self, icerik: str):
        self.gecmis.append({"role": "assistant", "content": icerik})
        self._gecmis_kisalt()
        self.gecmis_otomatik_kaydet()

    def mesaj_ekle_dosyali(self, metin: str, dosya_yolu: str):
        """
        Excel (.xlsx/.xls) veya görsel (PNG/JPG/WEBP) dosyasıyla birlikte mesaj ekle.

        - Excel: pandas ile markdown tabloya çevrilir → metin bağlamı olarak eklenir
        - Görsel: base64 encode → Anthropic vision API formatında eklenir
        """
        uzanti = os.path.splitext(dosya_yolu)[1].lower()
        if uzanti in (".xlsx", ".xls"):
            tablo_metin = self._excel_to_markdown(dosya_yolu)
            dosya_adi = os.path.basename(dosya_yolu)
            icerik = (
                f"[EXCEL DOSYASI: {dosya_adi}]\n\n"
                f"{tablo_metin}\n\n"
                f"Kullanıcı sorusu: {metin}"
            )
            self.gecmis.append({"role": "user", "content": icerik})
        elif uzanti in (".png", ".jpg", ".jpeg", ".webp"):
            if not os.path.exists(dosya_yolu):
                raise FileNotFoundError(f"Dosya bulunamadı: {dosya_yolu}")
            with open(dosya_yolu, "rb") as f:
                gorsel_bytes = f.read()
            b64 = base64.b64encode(gorsel_bytes).decode("utf-8")
            media_type_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }
            media_type = media_type_map.get(uzanti, "image/jpeg")
            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64,
                    },
                },
                {"type": "text", "text": metin},
            ]
            self.gecmis.append({"role": "user", "content": content})
        else:
            # Desteklenmeyen format — düz metin olarak ekle
            self.gecmis.append({"role": "user", "content": metin})
        self._gecmis_kisalt()

    def mesaj_ekle_saha_gorseli(self, gorsel_yolu: str, ek_aciklama: str = "") -> str:
        """
        Saha Çözüm modu için fotoğraf mesajı hazırlar.
        Görsel + yapılandırılmış analiz isteği birlikte gönderilir.
        Döndürür: görüntülenen mesaj metni (UI için)
        """
        uzanti = os.path.splitext(gorsel_yolu)[1].lower()
        desteklenen = {".png": "image/png", ".jpg": "image/jpeg",
                       ".jpeg": "image/jpeg", ".webp": "image/webp"}
        if uzanti not in desteklenen:
            raise ValueError(
                f"Desteklenmeyen görsel formatı: {uzanti} "
                "(desteklenen: PNG, JPG, WEBP)"
            )

        try:
            with open(gorsel_yolu, "rb") as f:
                gorsel_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            raise IOError(f"Görsel okunamadı: {e}")

        media_type = desteklenen[uzanti]
        dosya_adi = os.path.basename(gorsel_yolu)

        analiz_istegi = (
            f"Lütfen bu fotoğrafı inşaat sahası problemi perspektifinden analiz et."
        )
        if ek_aciklama.strip():
            analiz_istegi = f"{ek_aciklama.strip()}"

        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": gorsel_b64,
                },
            },
            {
                "type": "text",
                "text": analiz_istegi,
            },
        ]
        self.gecmis.append({"role": "user", "content": content})
        self._gecmis_kisalt()
        return f"[📷 {dosya_adi}] {analiz_istegi}"

    def _excel_to_markdown(self, dosya_yolu: str) -> str:
        """Excel dosyasını okunabilir markdown tabloya çevirir."""
        try:
            import pandas as pd
        except ImportError:
            return "[HATA: pandas kurulu değil — pip install pandas]"

        try:
            sheets: dict = pd.read_excel(
                dosya_yolu, sheet_name=None, engine="openpyxl"
            )
        except Exception as e:
            return f"[Excel okunamadı: {e}]"

        MAX_SATIR = 500
        parcalar = []
        for sheet_adi, df in sheets.items():
            if df.empty:
                continue
            # Çok büyük sheet'leri kes
            fazla = len(df) - MAX_SATIR
            df_goster = df.head(MAX_SATIR)
            try:
                tablo = df_goster.to_markdown(index=False)
            except Exception:
                tablo = df_goster.to_string(index=False)
            baslik = f"## Sheet: {sheet_adi}" if len(sheets) > 1 else ""
            blok = f"{baslik}\n\n{tablo}" if baslik else tablo
            if fazla > 0:
                blok += f"\n\n[+{fazla} satır daha gösterilmedi — toplam {len(df)} satır]"
            parcalar.append(blok.strip())

        return "\n\n---\n\n".join(parcalar) if parcalar else "[Excel boş veya okunamadı]"

    def _gecmis_kisalt(self):
        if len(self.gecmis) > 20:
            self.gecmis = self.gecmis[-20:]

    # ── Disk Geçmişi ────────────────────────────────────────────────────────

    def _gecmis_dosyasini_oku(self) -> List[Dict]:
        """Disk'teki geçmiş JSON'ını okur. Hata varsa boş liste döner."""
        try:
            if not GECMIS_DOSYASI.exists():
                return []
            with open(GECMIS_DOSYASI, "r", encoding="utf-8") as f:
                veri = json.load(f)
            if not isinstance(veri, list):
                return []
            return veri
        except Exception as e:
            logger.warning(f"Geçmiş dosyası okunamadı: {e}")
            return []

    def _gecmis_dosyasina_yaz(self, kayitlar: List[Dict]) -> bool:
        """Geçmişi atomic şekilde diske yazar (temp → rename).
        Döndürür: başarılı mı"""
        try:
            GECMIS_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=GECMIS_DOSYASI.parent,
                prefix=".asistan_gecmis_tmp_",
                suffix=".json",
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(kayitlar, f, ensure_ascii=False, indent=2)
            except Exception:
                os.unlink(tmp_path)
                raise
            shutil.move(tmp_path, str(GECMIS_DOSYASI))
            return True
        except Exception as e:
            logger.error(f"Geçmiş dosyası yazılamadı: {e}")
            return False

    def _baslik_uret(self) -> str:
        """Başlık boşsa ilk user mesajından kısa başlık üretir."""
        for m in self.gecmis:
            if m.get("role") == "user":
                icerik = m.get("content", "")
                if isinstance(icerik, list):
                    # vision/excel içerik bloğu → text parçasını bul
                    for blok in icerik:
                        if isinstance(blok, dict) and blok.get("type") == "text":
                            icerik = blok.get("text", "")
                            break
                    else:
                        icerik = "Görsel veya Dosya İçerikli Sohbet"
                return str(icerik)[:60].strip()
        return "Yeni Sohbet"

    def gecmis_kaydet(self, baslik: str = "") -> str:
        """Mevcut sohbeti diske kaydeder.
        baslik boşsa ilk user mesajından üretilir.
        Döndürür: kaydedilen konuşma ID'si"""
        try:
            if not self.gecmis:
                logger.debug("Kaydedilecek mesaj yok.")
                return ""
            # ID oluştur veya mevcut ID'yi güncelle
            if self._aktif_konusma_id:
                konusma_id = self._aktif_konusma_id
            else:
                konusma_id = datetime.now().strftime("%Y%m%d_%H%M%S")

            if not baslik:
                baslik = self._baslik_uret()

            tarih_str = datetime.now().strftime("%d.%m.%Y %H:%M")

            kayitlar = self._gecmis_dosyasini_oku()

            # Mevcut kayıt varsa güncelle, yoksa yeni ekle
            guncellendi = False
            for i, k in enumerate(kayitlar):
                if k.get("id") == konusma_id:
                    kayitlar[i] = {
                        "id": konusma_id,
                        "baslik": baslik,
                        "tarih": tarih_str,
                        "mod": getattr(self, "_mod", 0),
                        "mesajlar": list(self.gecmis),
                    }
                    guncellendi = True
                    break

            if not guncellendi:
                kayitlar.insert(0, {
                    "id": konusma_id,
                    "baslik": baslik,
                    "tarih": tarih_str,
                    "mod": getattr(self, "_mod", 0),
                    "mesajlar": list(self.gecmis),
                })

            # MAX_KAYIT sınırını uygula (en eskiler silinir)
            if len(kayitlar) > MAX_KAYIT:
                kayitlar = kayitlar[:MAX_KAYIT]

            if self._gecmis_dosyasina_yaz(kayitlar):
                self._aktif_konusma_id = konusma_id
                logger.debug(f"Konuşma kaydedildi: {konusma_id}")
                return konusma_id
            return ""
        except Exception as e:
            logger.error(f"gecmis_kaydet hatası: {e}")
            return ""

    def gecmis_listesi(self) -> List[Dict]:
        """Kayıtlı konuşmaları listeler (mesajlar hariç, sadece meta).
        Döndürür: [{"id", "baslik", "tarih", "mesaj_sayisi", "mod"}, ...]"""
        try:
            kayitlar = self._gecmis_dosyasini_oku()
            meta = []
            for k in kayitlar:
                meta.append({
                    "id": k.get("id", ""),
                    "baslik": k.get("baslik", "Başlıksız"),
                    "tarih": k.get("tarih", ""),
                    "mesaj_sayisi": len(k.get("mesajlar", [])),
                    "mod": k.get("mod", 0),
                })
            return meta
        except Exception as e:
            logger.error(f"gecmis_listesi hatası: {e}")
            return []

    def gecmis_yukle(self, konusma_id: str) -> bool:
        """ID'ye göre konuşmayı yükler ve self.gecmis'e atar.
        Döndürür: başarılı mı"""
        try:
            kayitlar = self._gecmis_dosyasini_oku()
            for k in kayitlar:
                if k.get("id") == konusma_id:
                    mesajlar = k.get("mesajlar", [])
                    if not isinstance(mesajlar, list):
                        logger.warning(f"Geçersiz mesaj formatı: {konusma_id}")
                        return False
                    self.gecmis = mesajlar
                    self._aktif_konusma_id = konusma_id
                    logger.debug(f"Konuşma yüklendi: {konusma_id} ({len(mesajlar)} mesaj)")
                    return True
            logger.warning(f"Konuşma bulunamadı: {konusma_id}")
            return False
        except Exception as e:
            logger.error(f"gecmis_yukle hatası: {e}")
            return False

    def gecmis_sil(self, konusma_id: str) -> bool:
        """ID'ye göre konuşmayı siler.
        Döndürür: başarılı mı"""
        try:
            kayitlar = self._gecmis_dosyasini_oku()
            yeni_kayitlar = [k for k in kayitlar if k.get("id") != konusma_id]
            if len(yeni_kayitlar) == len(kayitlar):
                logger.warning(f"Silinecek konuşma bulunamadı: {konusma_id}")
                return False
            if self._gecmis_dosyasina_yaz(yeni_kayitlar):
                if self._aktif_konusma_id == konusma_id:
                    self._aktif_konusma_id = ""
                logger.debug(f"Konuşma silindi: {konusma_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"gecmis_sil hatası: {e}")
            return False

    def gecmis_otomatik_kaydet(self) -> None:
        """Mevcut sohbet 2+ mesaj içeriyorsa otomatik kaydeder/günceller.
        _aktif_konusma_id varsa günceller, yoksa yeni oluşturur."""
        try:
            if len(self.gecmis) < 2:
                return
            self.gecmis_kaydet()
        except Exception as e:
            logger.warning(f"Otomatik kayıt başarısız: {e}")

    # ── Thread Oluşturma ────────────────────────────────────────────────────

    def sorgu_thread_olustur(self) -> Optional[ClaudeAsistanThread]:
        """Streaming sohbet thread'i oluştur."""
        if not self.api_key_gecerli():
            return None
        thread = ClaudeAsistanThread(self.api_key, list(self.gecmis), self.model)
        self._active_thread = thread
        return thread

    def sorgu_aracli_thread_olustur(self) -> Optional[ClaudeAracliThread]:
        """Araç kullanımı destekli thread oluştur (Hesap Asistanı + Analiz)."""
        if not self.api_key_gecerli():
            return None
        thread = ClaudeAracliThread(
            api_key=self.api_key,
            mesajlar=list(self.gecmis),
            model=self.model,
            arac_callback=self._arac_calistir,
        )
        self._active_thread = thread
        return thread

    def sorgu_saha_cozum_thread_olustur(self) -> Optional[ClaudeAracliThread]:
        """Saha Çözüm Danışmanı thread — uzmanlaşmış sistem promptuyla."""
        if not self.api_key_gecerli():
            return None
        thread = ClaudeAracliThread(
            api_key=self.api_key,
            mesajlar=list(self.gecmis),
            model=self.model,
            arac_callback=self._arac_calistir,
            sistem_prompt=SAHA_COZUM_SISTEM_PROMPT,
        )
        self._active_thread = thread
        return thread

    def aktif_istegi_iptal_et(self):
        if self._active_thread and self._active_thread.isRunning():
            self._active_thread.iptal_et()

    def hizli_sor(self, soru: str, ekstra_baglam: str = "") -> Optional[ClaudeAsistanThread]:
        tam_soru = f"{ekstra_baglam}\n\n{soru}" if ekstra_baglam else soru
        self.mesaj_ekle_kullanici(tam_soru)
        return self.sorgu_thread_olustur()

    # ── Bağlam Üreticiler ───────────────────────────────────────────────────

    def proje_baglam_olustur(self, proje_data: Dict[str, Any]) -> str:
        """Proje verisinden Claude için bağlam metni oluşturur."""
        satirlar = ["=== AKTİF PROJE BİLGİLERİ ==="]
        if proje_data.get("ad"):
            satirlar.append(f"Proje Adı     : {proje_data['ad']}")
        if proje_data.get("toplam_maliyet"):
            satirlar.append(
                f"Toplam Maliyet: {proje_data['toplam_maliyet']:,.2f} ₺"
            )
        if proje_data.get("kalem_sayisi"):
            satirlar.append(f"Kalem Sayısı  : {proje_data['kalem_sayisi']}")
        if proje_data.get("durum"):
            satirlar.append(f"Durum         : {proje_data['durum']}")
        if proje_data.get("notlar"):
            satirlar.append(f"Notlar        : {proje_data['notlar']}")

        # Kategori dağılımı
        kategori_dagilimi = proje_data.get("kategori_dagilimi", {})
        if kategori_dagilimi:
            satirlar.append("\nKategori Dağılımı:")
            for kat, tutar in sorted(
                kategori_dagilimi.items(), key=lambda x: x[1], reverse=True
            ):
                satirlar.append(f"  {kat:<25}: {tutar:>12,.0f} ₺")

        # İlk 15 metraj kalemi
        kalemler = proje_data.get("kalemler", [])
        if kalemler:
            gosterilen = min(15, len(kalemler))
            satirlar.append(f"\nÖnemli Kalemler ({gosterilen}/{len(kalemler)}):")
            for k in kalemler[:15]:
                satirlar.append(
                    f"  - {k.get('tanim', '?')}: "
                    f"{k.get('miktar', 0):.2f} {k.get('birim', '')} × "
                    f"{k.get('birim_fiyat', 0):,.2f} ₺"
                )

        return "\n".join(satirlar)

    # ── Araç Yürütücüsü ─────────────────────────────────────────────────────

    def _arac_calistir(self, arac_adi: str, parametreler: dict) -> str:
        """Claude'un çağırdığı araçları çalıştırır ve sonucu string olarak döndürür."""
        try:
            if arac_adi == "verimlilik_sure_hesapla":
                return self._arac_verimlilik_sure(parametreler)
            elif arac_adi == "kaba_yapi_maliyet":
                return self._arac_kaba_yapi_maliyet(parametreler)
            elif arac_adi == "proje_metraj_listesi":
                return self._arac_proje_metraj_listesi()
            elif arac_adi == "gantt_gorevleri_getir":
                return self._arac_gantt_gorevleri_getir()
            elif arac_adi == "metraj_kalem_ekle":
                return self._arac_metraj_kalem_ekle(parametreler)
            elif arac_adi == "metraj_toplu_ekle":
                return self._arac_metraj_toplu_ekle(parametreler)
            elif arac_adi == "gantt_gorev_ekle":
                return self._arac_gantt_gorev_ekle(parametreler)
            elif arac_adi == "gantt_toplu_ekle":
                return self._arac_gantt_toplu_ekle(parametreler)
            elif arac_adi == "gantt_dosya_iceri_aktar":
                return self._arac_gantt_dosya_iceri_aktar(parametreler)
            elif arac_adi == "ekap_ihale_ara":
                return self._arac_ekap_ihale_ara(parametreler)
            elif arac_adi == "hakedis_hesapla":
                return self._arac_hakedis_hesapla(parametreler)
            elif arac_adi == "gecikme_ceza_hesapla":
                return self._arac_gecikme_ceza_hesapla(parametreler)
            elif arac_adi == "saha_sorun_tani":
                return self._arac_saha_sorun_tani(parametreler)
            elif arac_adi == "malzeme_test_degerlendir":
                return self._arac_malzeme_test_degerlendir(parametreler)
            elif arac_adi == "isg_risk_degerlendirme":
                return self._arac_isg_risk_degerlendirme(parametreler)
            elif arac_adi == "emlak_url_analiz":
                return self._arac_emlak_url_analiz(parametreler)
            elif arac_adi == "emsal_karsilastir":
                return self._arac_emsal_karsilastir(parametreler)
            elif arac_adi == "gayrimenkul_degerle":
                return self._arac_gayrimenkul_degerle(parametreler)
            else:
                return f"Bilinmeyen araç: {arac_adi}"
        except Exception as e:
            logger.error(f"Araç çalıştırma hatası [{arac_adi}]: {e}")
            return f"Araç hatası [{arac_adi}]: {e}"

    # ── Araç Implementasyonları ─────────────────────────────────────────────

    def _arac_verimlilik_sure(self, parametreler: dict) -> str:
        """CŞB verimlilik tablosundan süre hesabı."""
        VERIMLILIK = {
            "Demir Bağlama/Bükme":      (333,  "kg"),
            "Nervürlü Soğuk Demir":     (250,  "kg"),
            "Kalıp Döşeme":             (4.0,  "m²"),
            "Kalıp Kiriş":              (2.86, "m²"),
            "Kalıp Kolon":              (1.82, "m²"),
            "Kalıp Sökme":              (8.0,  "m²"),
            "Kalıp (Karma)":            (3.33, "m²"),
            "Beton Dökme (Pompalı)":    (2.5,  "m³"),
            "Beton Dökme (Elle)":       (1.5,  "m³"),
            "İç Sıva":                  (25,   "m²"),
            "Dış Sıva":                 (20,   "m²"),
            "İç Boya":                  (45,   "m²"),
            "Dış Boya":                 (30,   "m²"),
            "Fayans/Seramik":           (8,    "m²"),
            "Mermer":                   (4,    "m²"),
            "Parke Laminat":            (25,   "m²"),
            "Parke Ahşap":              (15,   "m²"),
            "Mantolama":                (10,   "m²"),
            "Su Yalıtımı":              (8,    "m²"),
            "Tuğla":                    (4.5,  "m²"),
            "Gazbeton":                 (6,    "m²"),
            "Şap":                      (25,   "m²"),
            "Elektrik (m)":             (20,   "m"),
            "Su Tesisatı (m)":          (8,    "m"),
        }

        is_tipi = str(parametreler.get("is_tipi", ""))
        miktar = float(parametreler.get("miktar", 0))
        usta = max(1, int(parametreler.get("usta_sayisi", 1)))

        # Fuzzy match — büyük/küçük harf duyarsız
        eslesme = None
        is_tipi_lower = is_tipi.lower()
        for k in VERIMLILIK:
            if is_tipi_lower in k.lower() or k.lower() in is_tipi_lower:
                eslesme = k
                break

        if not eslesme:
            liste = "\n  ".join(VERIMLILIK.keys())
            return (
                f"'{is_tipi}' için verimlilik verisi bulunamadı.\n"
                f"Mevcut iş tipleri:\n  {liste}"
            )

        verimlilik, birim = VERIMLILIK[eslesme]
        sure = math.ceil(miktar / (verimlilik * usta))
        hafta, gun = divmod(sure, 5)
        if hafta:
            sure_metin = f"{hafta} hafta {gun} gün" if gun else f"{hafta} hafta"
        else:
            sure_metin = f"{gun} iş günü"

        return (
            f"Süre Hesabı — CŞB Birim Fiyat Analizleri:\n"
            f"  İş Tipi      : {eslesme}\n"
            f"  Miktar       : {miktar:,.2f} {birim}\n"
            f"  Verimlilik   : {verimlilik} {birim}/gün/usta\n"
            f"  Usta Sayısı  : {usta}\n"
            f"  Hesap        : ⌈{miktar:.1f} ÷ ({verimlilik} × {usta})⌉ = {sure} gün\n"
            f"  SONUÇ        : {sure} iş günü ({sure_metin})"
        )

    def _arac_kaba_yapi_maliyet(self, parametreler: dict) -> str:
        """Yapı sistemi katsayılarına göre kaba yapı maliyet tahmini."""
        KATSAYILAR = {
            "Betonarme Çerçeve": {
                "beton": 0.35, "kalip": 2.20, "demir": 95, "temel": 0.50,
            },
            "Betonarme Perde+Çerçeve": {
                "beton": 0.42, "kalip": 2.80, "demir": 120, "temel": 0.60,
            },
            "Yığma Tuğla": {
                "beton": 0.10, "kalip": 0.50, "demir": 20, "temel": 0.30,
            },
            "Çelik Konstrüksiyon": {
                "beton": 0.15, "kalip": 0.80, "demir": 50, "temel": 0.40,
            },
        }

        alan = float(parametreler.get("alan_m2", 0))
        sistem = str(parametreler.get("yapi_sistemi", ""))
        fiyat_beton = float(parametreler.get("birim_fiyat_beton", 4800))
        fiyat_demir = float(parametreler.get("birim_fiyat_demir", 38))
        fiyat_kalip = 180.0  # TL/m² (2026 Q1)

        # Fuzzy match
        eslesme = "Betonarme Çerçeve"
        for k in KATSAYILAR:
            if sistem.lower() in k.lower() or k.lower() in sistem.lower():
                eslesme = k
                break

        k = KATSAYILAR[eslesme]
        beton_hacim = alan * k["beton"]
        kalip_alani = alan * k["kalip"]
        demir_kg = alan * k["demir"]
        temel_m3 = alan * k["temel"]

        mal_beton = beton_hacim * fiyat_beton
        mal_kalip = kalip_alani * fiyat_kalip
        mal_demir = demir_kg * fiyat_demir
        mal_temel = temel_m3 * fiyat_beton
        toplam = mal_beton + mal_kalip + mal_demir + mal_temel
        birim_m2 = toplam / alan if alan > 0 else 0

        return (
            f"Kaba Yapı Maliyet Tahmini — {eslesme}:\n"
            f"  Alan           : {alan:,.0f} m²\n"
            f"  ─────────────────────────────────────\n"
            f"  Beton Dökme    : {beton_hacim:,.1f} m³ × {fiyat_beton:,.0f} ₺ = {mal_beton:,.0f} ₺\n"
            f"  Kalıp          : {kalip_alani:,.1f} m² × {fiyat_kalip:.0f} ₺    = {mal_kalip:,.0f} ₺\n"
            f"  Demir          : {demir_kg:,.0f} kg × {fiyat_demir:.0f} ₺      = {mal_demir:,.0f} ₺\n"
            f"  Temel Betonu   : {temel_m3:,.1f} m³ × {fiyat_beton:,.0f} ₺ = {mal_temel:,.0f} ₺\n"
            f"  ─────────────────────────────────────\n"
            f"  TOPLAM         : {toplam:,.0f} ₺\n"
            f"  Birim Maliyet  : {birim_m2:,.0f} ₺/m²\n"
            f"  Kaynak         : CŞB katsayıları, 2026 Q1 piyasa fiyatları\n"
            f"  Uyarı          : Bu tahmin ±%20 sapma içerebilir."
        )

    def _arac_proje_metraj_listesi(self) -> str:
        """Aktif projeden metraj kalemlerini DB'den çeker."""
        if not self._db or not self._proje_id:
            return "Aktif proje seçilmemiş veya veritabanı bağlantısı yok."
        try:
            kalemler = self._db.get_project_metraj(self._proje_id)
            if not kalemler:
                return "Aktif projede metraj kalemi bulunamadı."

            satirlar = [f"Proje Metraj Kalemleri ({len(kalemler)} kalem):"]
            toplam = 0.0
            for i, k in enumerate(kalemler[:30], 1):
                miktar = float(k.get("miktar") or 0)
                bf = float(k.get("birim_fiyat") or 0)
                tutar = miktar * bf
                toplam += tutar
                satirlar.append(
                    f"  {i:2d}. {str(k.get('tanim', 'Tanımsız'))[:45]:<45} "
                    f"{miktar:>8.2f} {str(k.get('birim', '')):5} × "
                    f"{bf:>10,.2f} ₺ = {tutar:>12,.2f} ₺"
                )

            if len(kalemler) > 30:
                satirlar.append(f"  ... ve {len(kalemler) - 30} kalem daha")

            satirlar.append(f"  {'─' * 70}")
            satirlar.append(f"  TOPLAM: {toplam:,.2f} ₺  ({len(kalemler)} kalem)")
            return "\n".join(satirlar)

        except Exception as e:
            return f"Metraj listesi alınamadı: {e}"

    def _arac_gantt_gorevleri_getir(self) -> str:
        """Aktif Gantt iş programındaki görevleri listeler."""
        if not self._gantt_engine:
            return (
                "Gantt iş programı bağlantısı yok.\n"
                "Ana pencereden Gantt sekmesine gidin ve ardından tekrar deneyin."
            )
        try:
            tasks = self._gantt_engine.tasks
            if not tasks:
                return "Gantt iş programında henüz görev yok."

            satirlar = [f"Mevcut Gantt Görevleri ({len(tasks)} adet):"]
            for task_id, task in list(tasks.items())[:25]:
                bas = (
                    task.baslangic_tarihi.strftime("%d.%m.%Y")
                    if task.baslangic_tarihi else "—"
                )
                bit = (
                    task.bitis_tarihi.strftime("%d.%m.%Y")
                    if task.bitis_tarihi else "—"
                )
                satirlar.append(
                    f"  [{task.wbs_kodu or task_id}] {task.ad} — "
                    f"{task.sure_gun} gün | "
                    f"%{task.ilerleme:.0f} tamamlandı | "
                    f"{bas} → {bit} | "
                    f"Kaynak: {task.kaynak or '—'}"
                )

            if len(tasks) > 25:
                satirlar.append(f"  ... ve {len(tasks) - 25} görev daha")

            return "\n".join(satirlar)

        except Exception as e:
            return f"Gantt görevleri alınamadı: {e}"

    # ── Veri Yazma Araçları ─────────────────────────────────────────────────

    # CŞB verimlilik tablosu (modül seviyesinde paylaşılan sabit)
    _VERIMLILIK_MAP = {
        "demir bağlama":     (333,  "kg"),
        "demir büküm":       (333,  "kg"),
        "nervürlü demir":    (250,  "kg"),
        "kalıp döşeme":      (4.0,  "m²"),
        "döşeme kalıbı":     (4.0,  "m²"),
        "kiriş kalıbı":      (2.86, "m²"),
        "kolon kalıbı":      (1.82, "m²"),
        "perde kalıbı":      (1.82, "m²"),
        "kalıp sökme":       (8.0,  "m²"),
        "kalıp karma":       (3.33, "m²"),
        "beton döküm":       (2.5,  "m³"),
        "beton pompalı":     (2.5,  "m³"),
        "beton elle":        (1.5,  "m³"),
        "iç sıva":           (25,   "m²"),
        "dış sıva":          (20,   "m²"),
        "iç boya":           (45,   "m²"),
        "dış boya":          (30,   "m²"),
        "fayans":            (8,    "m²"),
        "seramik":           (8,    "m²"),
        "mermer":            (4,    "m²"),
        "parke laminat":     (25,   "m²"),
        "parke ahşap":       (15,   "m²"),
        "mantolama":         (10,   "m²"),
        "su yalıtım":        (8,    "m²"),
        "tuğla":             (4.5,  "m²"),
        "gazbeton":          (6,    "m²"),
        "şap":               (25,   "m²"),
        "hafriyat":          (120,  "m³"),
        "grobeton":          (3.0,  "m³"),
        "dolgu":             (80,   "m³"),
    }

    def _csb_sure_hesapla(self, is_tipi: str, miktar: float, ekip: int = 3) -> int:
        """CŞB verimliliğinden iş günü hesaplar; eşleşme yoksa miktar/2 fallback."""
        if not is_tipi or miktar <= 0:
            return max(1, int(miktar / 2)) if miktar > 0 else 1
        is_lower = is_tipi.lower()
        for anahtar, (verim, _) in self._VERIMLILIK_MAP.items():
            if anahtar in is_lower or is_lower in anahtar:
                return max(1, math.ceil(miktar / (verim * max(1, ekip))))
        return max(1, int(miktar / 2))

    def _arac_metraj_kalem_ekle(self, parametreler: dict) -> str:
        """Tek metraj kalemi ekler — DB.add_metraj_kalem() çağırır."""
        if not self._db or not self._proje_id:
            return "HATA: Aktif proje seçilmemiş veya veritabanı bağlantısı yok."
        try:
            poz_no = str(parametreler.get("poz_no", ""))
            is_kalemi = str(parametreler.get("is_kalemi", ""))
            miktar = float(parametreler.get("miktar", 0))
            birim = str(parametreler.get("birim", ""))
            birim_fiyat = float(parametreler.get("birim_fiyat", 0))
            kategori = str(parametreler.get("kategori", "Genel"))

            if not is_kalemi:
                return "HATA: is_kalemi boş olamaz."

            kalem_id = self._db.add_metraj_kalem(
                proje_id=self._proje_id,
                poz_no=poz_no,
                tanim=is_kalemi,
                miktar=miktar,
                birim=birim,
                birim_fiyat=birim_fiyat,
                kategori=kategori,
            )
            toplam = miktar * birim_fiyat
            return (
                f"Metraj kalemi eklendi.\n"
                f"  ID         : {kalem_id}\n"
                f"  Poz No     : {poz_no}\n"
                f"  Tanım      : {is_kalemi}\n"
                f"  Miktar     : {miktar:,.2f} {birim}\n"
                f"  Birim Fiyat: {birim_fiyat:,.2f} ₺\n"
                f"  Toplam     : {toplam:,.2f} ₺\n"
                f"  Kategori   : {kategori}"
            )
        except Exception as e:
            return f"HATA — metraj_kalem_ekle: {e}"

    def _arac_metraj_toplu_ekle(self, parametreler: dict) -> str:
        """Birden fazla metraj kalemini toplu ekler."""
        if not self._db or not self._proje_id:
            return "HATA: Aktif proje seçilmemiş veya veritabanı bağlantısı yok."
        kalemler = parametreler.get("kalemler", [])
        if not kalemler:
            return "HATA: kalemler listesi boş."

        eklenen = 0
        hatalar = []
        toplam_tutar = 0.0

        for i, k in enumerate(kalemler):
            try:
                poz_no = str(k.get("poz_no", f"P{i+1:03d}"))
                is_kalemi = str(k.get("is_kalemi", ""))
                miktar = float(k.get("miktar", 0))
                birim = str(k.get("birim", ""))
                birim_fiyat = float(k.get("birim_fiyat", 0))
                kategori = str(k.get("kategori", "Genel"))

                if not is_kalemi:
                    hatalar.append(f"  Sıra {i+1}: is_kalemi boş — atlandı")
                    continue

                self._db.add_metraj_kalem(
                    proje_id=self._proje_id,
                    poz_no=poz_no,
                    tanim=is_kalemi,
                    miktar=miktar,
                    birim=birim,
                    birim_fiyat=birim_fiyat,
                    kategori=kategori,
                )
                toplam_tutar += miktar * birim_fiyat
                eklenen += 1
            except Exception as e:
                hatalar.append(f"  Sıra {i+1} ({k.get('is_kalemi', '?')}): {e}")

        satirlar = [
            f"Toplu metraj aktarımı tamamlandı.",
            f"  Eklenen  : {eklenen}/{len(kalemler)} kalem",
            f"  Toplam   : {toplam_tutar:,.2f} ₺",
        ]
        if hatalar:
            satirlar.append(f"  Hatalar  : {len(hatalar)} adet")
            satirlar.extend(hatalar[:5])
            if len(hatalar) > 5:
                satirlar.append(f"  ... ve {len(hatalar) - 5} hata daha")
        return "\n".join(satirlar)

    def _arac_gantt_gorev_ekle(self, parametreler: dict) -> str:
        """Gantt iş programına tek görev ekler; GanttEngine.tasks dict'ine yazar."""
        if not self._gantt_engine:
            return (
                "HATA: Gantt motoru bağlantısı yok.\n"
                "Ana pencereden Gantt sekmesini açık bırakarak tekrar deneyin."
            )
        try:
            import math as _math
            from datetime import datetime, timedelta

            ad = str(parametreler.get("ad", ""))
            if not ad:
                return "HATA: Görev adı (ad) boş olamaz."

            sure_gun = int(parametreler.get("sure_gun", 0))
            miktar = float(parametreler.get("miktar", 0))
            birim = str(parametreler.get("birim", ""))
            is_tipi = str(parametreler.get("is_tipi", ""))
            ekip = int(parametreler.get("ekip_sayisi", 3))
            oncul_str = str(parametreler.get("oncul", ""))
            kaynak = str(parametreler.get("kaynak", ""))
            baslangic_gun = int(parametreler.get("baslangic_gun", 0))

            # CŞB süre hesabı
            if sure_gun <= 0 and miktar > 0 and is_tipi:
                sure_gun = self._csb_sure_hesapla(is_tipi, miktar, ekip)

            if sure_gun <= 0:
                sure_gun = 1

            # Görev ID'si
            mevcut_ids = [
                int(k) for k in self._gantt_engine.tasks.keys()
                if str(k).isdigit()
            ]
            yeni_id = str(max(mevcut_ids) + 1) if mevcut_ids else "1"

            # Öncüller listesi
            oncul_listesi = []
            if oncul_str:
                for p in oncul_str.replace(";", ",").split(","):
                    p = p.strip()
                    if p:
                        oncul_listesi.append(p)

            # Başlangıç tarihi
            baslangic = datetime.today() + timedelta(days=baslangic_gun)

            # Task oluştur
            from app.core.gantt_engine import Task as GanttTask
            tid = int(yeni_id)
            yeni_task = GanttTask(
                task_id=tid,
                ad=ad,
                sure_gun=sure_gun,
                baslangic_tarihi=baslangic,
                bitis_tarihi=baslangic + timedelta(days=sure_gun),
                kaynak=kaynak or "",
                ilerleme=0.0,
            )
            for p in oncul_listesi:
                try:
                    yeni_task.predecessors.append((int(p), "FS", 0))
                except (ValueError, TypeError):
                    pass
            self._gantt_engine.tasks[tid] = yeni_task

            # _is_list güncelleme — GanttWindow UI'yı besleyen asıl kaynak
            if self._gantt_window is not None:
                try:
                    from PyQt6.QtCore import QMetaObject, Qt
                    is_dict = self._task_to_is_dict(
                        tid, ad, sure_gun, miktar, birim, ekip, kaynak, oncul_listesi
                    )
                    # Çift eklemeyi önle
                    mevcut_ids = {t.get("id") for t in self._gantt_window._is_list}
                    if tid not in mevcut_ids:
                        self._gantt_window._is_list.append(is_dict)
                    # Tablo yenile
                    QMetaObject.invokeMethod(
                        self._gantt_window,
                        "_yukle_is_listesi",
                        Qt.ConnectionType.QueuedConnection,
                    )
                    # Görsel Gantt chart yenile
                    QMetaObject.invokeMethod(
                        self._gantt_window,
                        "refresh_visual_gantt",
                        Qt.ConnectionType.QueuedConnection,
                    )
                except Exception as _e:
                    logger.warning(f"_is_list güncelleme hatası: {_e}")

            return (
                f"Gantt görevi eklendi.\n"
                f"  ID         : {yeni_id}\n"
                f"  Ad         : {ad}\n"
                f"  Süre       : {sure_gun} iş günü\n"
                f"  Başlangıç  : {baslangic.strftime('%d.%m.%Y')}\n"
                f"  Öncüller   : {', '.join(oncul_listesi) if oncul_listesi else 'Yok'}\n"
                f"  Kaynak     : {kaynak or 'Atanmadı'}"
            )
        except Exception as e:
            return f"HATA — gantt_gorev_ekle: {e}"

    def _arac_gantt_toplu_ekle(self, parametreler: dict) -> str:
        """Gantt iş programına birden fazla görevi toplu ekler."""
        if not self._gantt_engine:
            return (
                "HATA: Gantt motoru bağlantısı yok.\n"
                "Ana pencereden Gantt sekmesini açık bırakarak tekrar deneyin."
            )
        gorevler = parametreler.get("gorevler", [])
        if not gorevler:
            return "HATA: gorevler listesi boş."

        from datetime import datetime, timedelta
        try:
            from app.core.gantt_engine import Task as GanttTask
            _gantt_task_cls = GanttTask
        except Exception:
            return "HATA: GanttTask sınıfı yüklenemedi."

        eklenen = 0
        hatalar = []
        _is_dict_listesi: list = []   # _is_list'e eklenecek dict'ler

        # Mevcut max ID
        mevcut_ids = [
            int(k) for k in self._gantt_engine.tasks.keys()
            if str(k).isdigit()
        ]
        sonraki_id = (max(mevcut_ids) + 1) if mevcut_ids else 1

        # ID mapping: gorev index → yeni_id (öncül referansları için)
        id_map: dict = {}

        for i, g in enumerate(gorevler):
            try:
                ad = str(g.get("ad", ""))
                if not ad:
                    hatalar.append(f"  Sıra {i+1}: ad boş — atlandı")
                    continue

                sure_gun = int(g.get("sure_gun", 0))
                miktar = float(g.get("miktar", 0))
                birim = str(g.get("birim", ""))
                is_tipi = str(g.get("is_tipi", ""))
                ekip = int(g.get("ekip_sayisi", 3))
                oncul_str = str(g.get("oncul", ""))
                kaynak = str(g.get("kaynak", ""))
                baslangic_gun = int(g.get("baslangic_gun", 0))

                # CŞB süre hesabı
                if sure_gun <= 0 and miktar > 0 and is_tipi:
                    sure_gun = self._csb_sure_hesapla(is_tipi, miktar, ekip)
                if sure_gun <= 0:
                    sure_gun = 1

                yeni_id = str(sonraki_id)
                id_map[i] = yeni_id
                sonraki_id += 1

                # Öncül dönüşümü — index referansını gerçek ID'ye çevir
                oncul_listesi = []
                if oncul_str:
                    for p in oncul_str.replace(";", ",").split(","):
                        p = p.strip()
                        if not p:
                            continue
                        # Sayısal index mi, yoksa ID mi?
                        if p.isdigit() and int(p) < len(gorevler):
                            mapped = id_map.get(int(p))
                            if mapped:
                                oncul_listesi.append(mapped)
                            else:
                                oncul_listesi.append(p)
                        else:
                            oncul_listesi.append(p)

                baslangic = datetime.today() + timedelta(days=baslangic_gun)
                tid = int(yeni_id)
                yeni_task = _gantt_task_cls(
                    task_id=tid,
                    ad=ad,
                    sure_gun=sure_gun,
                    baslangic_tarihi=baslangic,
                    bitis_tarihi=baslangic + timedelta(days=sure_gun),
                    kaynak=kaynak or "",
                    ilerleme=0.0,
                )
                for p in oncul_listesi:
                    try:
                        yeni_task.predecessors.append((int(p), "FS", 0))
                    except (ValueError, TypeError):
                        pass
                self._gantt_engine.tasks[tid] = yeni_task
                # _is_list için dict topla
                _is_dict_listesi.append(self._task_to_is_dict(
                    tid, ad, sure_gun, miktar, birim, ekip, kaynak, oncul_listesi
                ))
                eklenen += 1

            except Exception as e:
                hatalar.append(f"  Sıra {i+1} ({g.get('ad', '?')}): {e}")

        # GanttWindow._is_list'e toplu yaz + thread-safe UI yenileme
        if self._gantt_window is not None and _is_dict_listesi:
            try:
                from PyQt6.QtCore import QMetaObject, Qt
                mevcut_ids_set = {t.get("id") for t in self._gantt_window._is_list}
                for d in _is_dict_listesi:
                    if d["id"] not in mevcut_ids_set:
                        self._gantt_window._is_list.append(d)
                        mevcut_ids_set.add(d["id"])
                # Tablo yenile
                QMetaObject.invokeMethod(
                    self._gantt_window,
                    "_yukle_is_listesi",
                    Qt.ConnectionType.QueuedConnection,
                )
                # Görsel Gantt chart yenile
                QMetaObject.invokeMethod(
                    self._gantt_window,
                    "refresh_visual_gantt",
                    Qt.ConnectionType.QueuedConnection,
                )
            except Exception as _e:
                logger.warning(f"Toplu _is_list güncelleme hatası: {_e}")

        satirlar = [
            f"Toplu Gantt aktarımı tamamlandı.",
            f"  Eklenen  : {eklenen}/{len(gorevler)} görev",
        ]
        if hatalar:
            satirlar.append(f"  Hatalar  : {len(hatalar)} adet")
            satirlar.extend(hatalar[:5])
            if len(hatalar) > 5:
                satirlar.append(f"  ... ve {len(hatalar) - 5} hata daha")
        return "\n".join(satirlar)

    def _arac_gantt_dosya_iceri_aktar(self, parametreler: dict) -> str:
        """Dosyadan (Excel/CSV/JSON) Gantt görevlerini içeri aktarır; GanttEngine.tasks'a yazar."""
        import csv as _csv

        dosya_yolu = str(parametreler.get("dosya_yolu", "")).strip()
        mod = str(parametreler.get("mod", "ekle")).strip().lower()

        if not dosya_yolu:
            return "HATA: dosya_yolu parametresi boş."
        if not os.path.isfile(dosya_yolu):
            return f"HATA: Dosya bulunamadı: {dosya_yolu}"

        uzanti = os.path.splitext(dosya_yolu)[1].lower()
        gorev_listesi = []

        try:
            # ── JSON ──────────────────────────────────────────────────
            if uzanti == ".json":
                with open(dosya_yolu, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    gorev_listesi = data
                elif isinstance(data, dict):
                    gorev_listesi = data.get("tasks", data.get("gorevler", []))

            # ── CSV ───────────────────────────────────────────────────
            elif uzanti in (".csv", ".txt"):
                with open(dosya_yolu, "r", encoding="utf-8-sig", newline="") as f:
                    reader = _csv.DictReader(f)
                    for row in reader:
                        row_lower = {k.lower().strip(): v for k, v in row.items()}
                        ad = row_lower.get("iş adı") or row_lower.get("ad") or row_lower.get("task name", "")
                        if not str(ad).strip():
                            continue
                        try:
                            sure = int(float(str(row_lower.get("süre (gün)") or row_lower.get("süre") or row_lower.get("duration") or 1)))
                        except (ValueError, TypeError):
                            sure = 1
                        gorev_listesi.append({
                            "ad": str(ad).strip(),
                            "sure": max(1, sure),
                            "baslangic": str(row_lower.get("başlangıç") or row_lower.get("start") or "").strip(),
                            "bitis": str(row_lower.get("bitiş") or row_lower.get("finish") or "").strip(),
                            "miktar": float(str(row_lower.get("miktar") or row_lower.get("quantity") or 0) or 0),
                            "miktar_birim": str(row_lower.get("birim") or row_lower.get("unit") or "m²").strip(),
                            "kaynak": str(row_lower.get("kaynak/ekip") or row_lower.get("kaynak") or row_lower.get("resource") or "").strip(),
                            "bagimliliklar": [],
                            "milestone": str(row_lower.get("milestone", "")).lower() in ("evet", "1", "true"),
                            "tamamlanma_yuzdesi": 0,
                            "butce": float(str(row_lower.get("bütçe (tl)") or row_lower.get("bütçe") or row_lower.get("budget") or 0) or 0),
                            "aciklama": str(row_lower.get("açıklama") or row_lower.get("description") or "").strip(),
                        })

            # ── Excel ─────────────────────────────────────────────────
            elif uzanti in (".xlsx", ".xls"):
                try:
                    import openpyxl as _opxl
                except ImportError:
                    return "HATA: openpyxl paketi yüklü değil. 'pip install openpyxl' çalıştırın."
                wb = _opxl.load_workbook(dosya_yolu, data_only=True)
                ws = wb.active
                basliklar = [str(c.value).lower().strip() if c.value else "" for c in ws[1]]

                def _kolon(adaylar):
                    for a in adaylar:
                        try:
                            return basliklar.index(a.lower())
                        except ValueError:
                            pass
                    return -1

                idx_ad  = _kolon(["iş adı", "ad", "task name", "name"])
                idx_sur = _kolon(["süre (gün)", "süre", "duration"])
                idx_bas = _kolon(["başlangıç", "başlangıç tarihi", "start"])
                idx_bit = _kolon(["bitiş", "bitiş tarihi", "finish", "end"])
                idx_mik = _kolon(["miktar", "quantity"])
                idx_bir = _kolon(["birim", "unit"])
                idx_kay = _kolon(["kaynak/ekip", "kaynak", "ekip", "resource"])
                idx_onc = _kolon(["öncüller (id)", "öncüller", "predecessors"])
                idx_mil = _kolon(["milestone (evet/hayır)", "milestone"])
                idx_tam = _kolon(["tamamlanma (%)", "tamamlanma", "progress"])
                idx_but = _kolon(["bütçe (tl)", "bütçe", "budget"])
                idx_ack = _kolon(["açıklama", "notlar", "description"])

                def _cell(row, idx):
                    return row[idx] if idx >= 0 and idx < len(row) else None

                for row in ws.iter_rows(min_row=2, values_only=True):
                    if all(v is None for v in row):
                        continue
                    ad_val = _cell(row, idx_ad)
                    if not ad_val:
                        continue
                    try:
                        sure = int(float(str(_cell(row, idx_sur) or 1)))
                    except (ValueError, TypeError):
                        sure = 1
                    oncul_str = str(_cell(row, idx_onc) or "")
                    bagimliliklar = []
                    for p in oncul_str.replace(";", ",").split(","):
                        p = p.strip()
                        if p.isdigit():
                            bagimliliklar.append(int(p))
                    gorev_listesi.append({
                        "ad": str(ad_val).strip(),
                        "sure": max(1, sure),
                        "baslangic": str(_cell(row, idx_bas) or "").strip(),
                        "bitis": str(_cell(row, idx_bit) or "").strip(),
                        "miktar": float(str(_cell(row, idx_mik) or 0) or 0),
                        "miktar_birim": str(_cell(row, idx_bir) or "m²").strip() or "m²",
                        "kaynak": str(_cell(row, idx_kay) or "").strip(),
                        "bagimliliklar": bagimliliklar,
                        "milestone": str(_cell(row, idx_mil) or "").lower() in ("evet", "1", "true"),
                        "tamamlanma_yuzdesi": int(float(str(_cell(row, idx_tam) or 0) or 0)),
                        "butce": float(str(_cell(row, idx_but) or 0) or 0),
                        "aciklama": str(_cell(row, idx_ack) or "").strip(),
                    })
            else:
                return f"HATA: Desteklenmeyen dosya formatı: {uzanti} (desteklenen: .xlsx, .csv, .json)"

        except Exception as e:
            return f"HATA — dosya okuma: {e}"

        # Geçerli görevleri filtrele
        gorevler = [g for g in gorev_listesi if isinstance(g, dict) and str(g.get("ad", "")).strip()]
        if not gorevler:
            return f"HATA: Dosyada geçerli görev bulunamadı. ({dosya_yolu})"

        if not self._gantt_engine:
            return (
                "HATA: Gantt motoru bağlantısı yok.\n"
                "Ana pencereden Gantt sekmesini açık bırakarak tekrar deneyin."
            )

        try:
            from app.core.gantt_engine import Task as GanttTask
        except Exception as e:
            return f"HATA: GanttTask sınıfı yüklenemedi: {e}"

        from datetime import datetime as _dt, timedelta, date as _date

        # ID offset
        mevcut_ids = [int(k) for k in self._gantt_engine.tasks.keys() if str(k).isdigit()]
        if mod == "yenile":
            self._gantt_engine.tasks.clear()
            id_offset = 0
        else:
            id_offset = max(mevcut_ids) if mevcut_ids else 0

        def _tarih_parse(s):
            if not s or str(s).strip() in ("", "None"):
                return _dt.today()
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    return _dt.strptime(str(s).strip(), fmt)
                except ValueError:
                    pass
            return _dt.today()

        eklenen = 0
        hatalar = []
        for i, g in enumerate(gorevler):
            try:
                yeni_id = str(id_offset + i + 1)
                sure = max(1, int(g.get("sure", 1)))
                bas = _tarih_parse(g.get("baslangic", ""))
                bit = bas + timedelta(days=sure)
                oncul_listesi = [str(id_offset + b) for b in g.get("bagimliliklar", []) if b > 0]
                tid = int(id_offset + i + 1)
                task = GanttTask(
                    task_id=tid,
                    ad=str(g["ad"]),
                    sure_gun=sure,
                    baslangic_tarihi=bas,
                    bitis_tarihi=bit,
                    kaynak=g.get("kaynak") or "",
                    ilerleme=float(g.get("tamamlanma_yuzdesi", 0)),
                )
                for p in oncul_listesi:
                    try:
                        task.predecessors.append((int(p), "FS", 0))
                    except (ValueError, TypeError):
                        pass
                self._gantt_engine.tasks[tid] = task
                eklenen += 1
            except Exception as e:
                hatalar.append(f"  Sıra {i+1} ({g.get('ad', '?')}): {e}")

        try:
            if hasattr(self._gantt_engine, "veri_degisti"):
                self._gantt_engine.veri_degisti.emit()
        except Exception:
            pass

        satirlar = [
            f"Dosya içeri aktarıldı — {os.path.basename(dosya_yolu)}",
            f"  Format  : {uzanti.upper()}",
            f"  Mod     : {'Yenile (sıfırdan)' if mod == 'yenile' else 'Ekle (mevcut programa)'}",
            f"  Eklenen : {eklenen}/{len(gorevler)} görev",
        ]
        if hatalar:
            satirlar.append(f"  Hatalar : {len(hatalar)} adet")
            satirlar.extend(hatalar[:3])
        return "\n".join(satirlar)

    # ── Yeni Araçlar: EKAP, Hakediş, Gecikme Cezası ─────────────────────────

    def _arac_ekap_ihale_ara(self, parametreler: dict) -> str:
        """EKAP v2 API üzerinden ihale arama."""
        try:
            from app.core.ekap_engine import EKAPEngine
            engine = EKAPEngine()
            sonuc = engine.ihale_ara(
                anahtar_kelime=str(parametreler.get("anahtar_kelime", "")),
                il=str(parametreler.get("il", "")),
                ihale_turu=str(parametreler.get("ihale_turu", "")),
                baslangic_tarihi=str(parametreler.get("baslangic_tarihi", "")),
                bitis_tarihi=str(parametreler.get("bitis_tarihi", "")),
                sayfa_boyutu=int(parametreler.get("sayfa_boyutu", 20)),
            )
        except Exception as e:
            return f"EKAP bağlantı hatası: {e}"

        if not sonuc.get("basarili"):
            return f"EKAP Arama Başarısız:\n{sonuc.get('hata', 'Bilinmeyen hata')}"

        ihaleler = sonuc.get("ihaleler", [])
        toplam = sonuc.get("toplam", 0)
        if not ihaleler:
            return "Arama kriterlerine uygun ihale bulunamadı."

        satirlar = [
            f"EKAP İhale Arama Sonuçları — Toplam: {toplam} ihale",
            f"  (İlk {len(ihaleler)} gösteriliyor)",
            "─" * 60,
        ]
        for i, ih in enumerate(ihaleler[:15], 1):
            d = ih.to_dict() if hasattr(ih, "to_dict") else ih
            satirlar.append(
                f"  {i:2d}. {str(d.get('ihale_adi', '?'))[:55]}\n"
                f"      Kurum : {str(d.get('idare_adi', '?'))[:45]}\n"
                f"      Tarih : {d.get('ihale_tarihi', '?')} | "
                f"Tür: {d.get('ihale_turu', '?')} | "
                f"Durum: {d.get('durum', '?')}\n"
                f"      İl    : {d.get('il', '?')} | "
                f"IKN: {d.get('ihale_no', '?')}"
            )
        return "\n".join(satirlar)

    def _arac_hakedis_hesapla(self, parametreler: dict) -> str:
        """KİK mevzuatına uygun hakediş hesabı (4734/4735)."""
        try:
            sozlesme = float(parametreler.get("sozlesme_bedeli", 0))
            yuzde = float(parametreler.get("tamamlanma_yuzdesi", 0))
            onceki = float(parametreler.get("onceki_hakedis_yuzdesi", 0))
            kdv_oran = float(parametreler.get("kdv_orani", 20))
            stopaj_oran = float(parametreler.get("stopaj_orani", 3))
            damga_oran = float(parametreler.get("damga_vergisi_orani", 0.948))

            if sozlesme <= 0:
                return "HATA: Sözleşme bedeli sıfırdan büyük olmalıdır."
            if not (0 <= yuzde <= 100):
                return "HATA: Tamamlanma yüzdesi 0-100 arasında olmalıdır."
            if onceki >= yuzde:
                return "HATA: Mevcut tamamlanma yüzdesi önceki hakedişten düşük olamaz."

            # Bu dönem tamamlanma farkı
            donem_yuzdesi = yuzde - onceki
            # Bu dönem brüt iş tutarı (KDV hariç)
            brut_is = sozlesme * (donem_yuzdesi / 100)
            # Toplam birikimli tutar
            toplam_birikim = sozlesme * (yuzde / 100)

            # KDV
            kdv_tutari = brut_is * (kdv_oran / 100)
            kdv_dahil = brut_is + kdv_tutari

            # Kesintiler (KDV dahil tutardan)
            stopaj_tutari = brut_is * (stopaj_oran / 100)  # Stopaj KDV hariç
            damga_tutari = brut_is * (damga_oran / 100)

            # Net ödeme
            net_odeme = kdv_dahil - stopaj_tutari - damga_tutari

            return (
                f"Hakediş Hesabı — 4734/4735 KİK Mevzuatı\n"
                f"{'─' * 55}\n"
                f"  Sözleşme Bedeli      : {sozlesme:>15,.2f} ₺\n"
                f"  Önceki Tamamlanma    : %{onceki:.2f}\n"
                f"  Mevcut Tamamlanma    : %{yuzde:.2f}\n"
                f"  Bu Dönem Farkı       : %{donem_yuzdesi:.2f}\n"
                f"{'─' * 55}\n"
                f"  Dönem İş Tutarı (KDV hariç) : {brut_is:>12,.2f} ₺\n"
                f"  KDV (%{kdv_oran:.0f})              : {kdv_tutari:>12,.2f} ₺\n"
                f"  KDV Dahil Tutar      : {kdv_dahil:>12,.2f} ₺\n"
                f"{'─' * 55}\n"
                f"  Gelir Vergisi Stopajı (%{stopaj_oran:.0f})  : -{stopaj_tutari:>10,.2f} ₺\n"
                f"  Damga Vergisi (%{damga_oran:.3f})   : -{damga_tutari:>10,.2f} ₺\n"
                f"{'─' * 55}\n"
                f"  NET ÖDEME TUTARI     : {net_odeme:>12,.2f} ₺\n"
                f"{'─' * 55}\n"
                f"  Birikimli İş Tutarı  : {toplam_birikim:>12,.2f} ₺ (%{yuzde:.2f})\n"
                f"  Kalan İş             : {sozlesme - toplam_birikim:>12,.2f} ₺ (%{100 - yuzde:.2f})"
            )
        except Exception as e:
            return f"Hakediş hesap hatası: {e}"

    # ── Saha Çözüm Araç Implementasyonları ─────────────────────────────────

    def _arac_saha_sorun_tani(self, parametreler: dict) -> str:
        """Saha sorununun kategorisini ve ilgili yönetmelikleri tespit eder."""
        sorun = str(parametreler.get("sorun_tanimi", "")).lower()
        yapi = parametreler.get("yapi_turu", "Betonarme")
        asama = parametreler.get("imalat_asamasi", "Kaba Yapı")
        aciliyet = parametreler.get("aciliyet", "Orta")

        KATEGORI_YONETMELIK = {
            "beton": {
                "anahtar": ["beton", "segregasyon", "boşluk", "slump", "basınç",
                            "dayanım", "kür", "çatlak", "balonc", "gözenek"],
                "yonetmelikler": [
                    "TS EN 206+A2:2021 — slump, su/çimento, dayanım sınıfları",
                    "TS 500:2000 md.4.3 — minimum beton örtü kalınlıkları",
                    "TS EN 13670:2010 md.8 — beton dökümü, sıkıştırma, kür",
                    "TS 9967 — hazır beton: su ekleme YASAK, nakliye ≤90 dk",
                ],
                "risk_krisel": ["segregasyon", "dayanım düşük", "boşluk", "gözenek"]
            },
            "demir": {
                "anahtar": ["demir", "donatı", "pası", "örtü", "bindirme",
                            "nervür", "çap", "filiz"],
                "yonetmelikler": [
                    "TS 500:2000 md.5.3 — donatı örtü kalınlıkları (min 30mm)",
                    "TBDY 2018 md.7.2 — bindirme ve kanca uzunlukları",
                    "TS EN 1992-1-1 md.8 — donatı yerleşim ve birleşim kuralları",
                    "TBDY 2018 — sargı donatısı, kolon-kiriş birleşim bölgesi",
                ],
                "risk_krisel": ["sargı yok", "örtü yok", "paslanma ciddi"]
            },
            "kalıp": {
                "anahtar": ["kalıp", "söküm", "şişme", "göçme", "iskele",
                            "payanda", "form"],
                "yonetmelikler": [
                    "TS EN 13670 md.9 — kalıp sökme süreleri (döşeme min 21 gün C25)",
                    "TS 500:2000 md.4.4.4 — erken yükleme kısıtları",
                    "İSG Yapı Yönetmeliği — iskele ve kalıp güvenlik kontrolleri",
                ],
                "risk_krisel": ["göçme", "çöküş", "erken sökme"]
            },
            "zemin": {
                "anahtar": ["zemin", "oturma", "sıvılaşma", "heyelan", "kayma",
                            "taşıma", "çökme", "zemin suyu"],
                "yonetmelikler": [
                    "TBDY 2018 Bölüm 16 — zemin sınıflaması ve sıvılaşma analizi",
                    "Zemin Mekaniği ve Temel İnşaatı Yönetmeliği",
                    "TS EN 1997 (Eurocode 7) — zemin tasarımı ve şev stabilitesi",
                ],
                "risk_krisel": ["sıvılaşma", "oturma", "heyelan", "kayma"]
            },
            "hafriyat": {
                "anahtar": ["hafriyat", "kazı", "iksa", "destek", "göçme",
                            "hendek", "şev"],
                "yonetmelikler": [
                    "6331 İSG Kanunu md.12 — kazılarda göçme riski önlemleri",
                    "Yapı İşleri İSG Yönetmeliği — hendek güvenlik kuralları",
                    "1m üzeri hendek: iksa veya min 45° şev açısı zorunlu",
                    "2m+ derinlik: yatay destek veya şev + giriş merdiveni",
                ],
                "risk_krisel": ["göçme", "2m", "3m", "su geldi"]
            },
            "çatlak": {
                "anahtar": ["çatlak", "kırılma", "deformasyon", "çatla"],
                "yonetmelikler": [
                    "TS 500:2000 md.11 — izin verilen çatlak genişlikleri",
                    "  (w_k ≤ 0.3mm dış/nem, ≤ 0.4mm iç kuru ortam)",
                    "TBDY 2018 — deprem sonrası hasar tespiti kriterleri",
                    "Yapı Denetim Yönetmeliği 4708 — hasar bildirimi zorunluluğu",
                ],
                "risk_krisel": ["taşıyıcı", "yapısal", "kolon", "kiriş", "perde"]
            },
            "su_yalitim": {
                "anahtar": ["su sızıntı", "nem", "yalıtım", "rutubet", "ıslaklık",
                            "drenaj"],
                "yonetmelikler": [
                    "TS EN 14891 — su yalıtım malzemeleri performans standardı",
                    "TS 11727 — su yalıtım uygulamaları",
                    "CŞB 2026: Su yalıtımı poz no 27.xxx birim fiyatları",
                ],
                "risk_krisel": ["bodrum", "temel"]
            },
            "isg": {
                "anahtar": ["kaza", "yaralanma", "güvenlik", "baret", "emniyet",
                            "koruyucu", "iş kazası"],
                "yonetmelikler": [
                    "6331 İSG Kanunu — kaza anında durum tespiti ve bildirim",
                    "SGK — 3 iş günü içinde kaza bildirimi zorunlu",
                    "İşveren sorumluluğu — tüm işçiler SGK'lı olmalı",
                    "Yapı İşleri İSG Yönetmeliği (2013/35076)",
                ],
                "risk_krisel": ["ölüm", "ağır yaralanma", "düşme", "elektrik"]
            },
        }

        eslesen_kategoriler = []
        eslesen_yonetmelikler = []
        risk_seviyesi = aciliyet if aciliyet in ["Kritik", "Yüksek", "Orta", "Düşük"] else "Orta"

        for kat, veri in KATEGORI_YONETMELIK.items():
            for kelime in veri["anahtar"]:
                if kelime in sorun:
                    eslesen_kategoriler.append(kat)
                    eslesen_yonetmelikler.extend(veri["yonetmelikler"])
                    # Kritik risk anahtar kelimesi var mı?
                    for kk in veri["risk_krisel"]:
                        if kk in sorun:
                            risk_seviyesi = "Kritik"
                            break
                    break

        eslesen_yonetmelikler = list(dict.fromkeys(eslesen_yonetmelikler))

        satirlar = [
            "SAHA SORUN ANALİZ BAĞLAMI:",
            f"  Sorun         : {parametreler.get('sorun_tanimi', '')}",
            f"  Yapı Türü     : {yapi}",
            f"  İmalat Aşaması: {asama}",
            f"  Aciliyet      : {aciliyet}",
            f"  Risk Seviyesi : {risk_seviyesi}",
        ]

        if eslesen_kategoriler:
            satirlar.append(
                f"\nTespit Edilen Kategori(ler): {', '.join(set(eslesen_kategoriler))}"
            )

        if eslesen_yonetmelikler:
            satirlar.append("\nİlgili Yönetmelik / Standartlar:")
            for yonetmelik in eslesen_yonetmelikler[:10]:
                satirlar.append(f"  • {yonetmelik}")
        else:
            satirlar.append(
                "\nNot: Otomatik kategori eşleşmesi bulunamadı — "
                "genel mühendislik ve İSG kuralları geçerlidir."
            )

        satirlar.extend([
            "\nBu bağlama dayanarak şu yapıda yanıt ver:",
            "1. SORUN TEŞHİSİ — Teknik tanım",
            "2. KÖK NEDEN — Öncelikli nedenler (2-3 madde)",
            "3. YÖNETMELİK DAYANAĞI — Yukarıdaki maddeleri kullan",
            "4. ÇÖZÜM ADIMLARI — Sıralı, sahada uygulanabilir",
            "5. MALİYET ETKİSİ — TL/m² veya toplam tahmini",
            f"6. RİSK: {risk_seviyesi}",
        ])

        return "\n".join(satirlar)

    def _arac_malzeme_test_degerlendir(self, parametreler: dict) -> str:
        """Malzeme test sonucunu standartlara göre değerlendirir."""
        malzeme = str(parametreler.get("malzeme_turu", "")).lower()
        test = str(parametreler.get("test_turu", "")).lower()
        deger = float(parametreler.get("olculen_deger", 0))
        birim = str(parametreler.get("birim", "MPa"))
        beton_sinifi = str(parametreler.get("beton_sinifi", "C25")).upper()

        # kg/cm² → MPa dönüşümü
        deger_mpa = deger / 10.197 if birim in ("kg/cm²", "kgf/cm²") else deger

        BETON_DAYANIM = {
            "C16": 16, "C20": 20, "C25": 25, "C30": 30,
            "C35": 35, "C40": 40, "C45": 45, "C50": 50,
        }

        satirlar = []

        # ── Beton Basınç Dayanımı ─────────────────────────────────────────
        if "beton" in malzeme and any(x in test for x in ["basınç", "dayanım", "küp", "silindir"]):
            fck = BETON_DAYANIM.get(beton_sinifi, 25)
            min_kabul = fck * 0.85  # TS EN 206: numune değeri fck × 0.85
            kabul = deger_mpa >= min_kabul
            etiket = "✅ KABUL" if kabul else "❌ RED"
            oran = (deger_mpa / fck) * 100

            satirlar = [
                "BETON BASINÇ DAYANIMI DEĞERLENDİRMESİ (TS EN 206 + TS 500):",
                f"  Beton Sınıfı            : {beton_sinifi}",
                f"  Karakteristik Dayanım   : {fck} MPa",
                f"  Min. Kabul Sınırı       : {min_kabul:.1f} MPa  (fck × 0.85 — TS EN 206)",
                f"  Ölçülen Değer           : {deger:.1f} {birim}  ≈ {deger_mpa:.1f} MPa",
                f"  KARAR                   : {etiket}",
                f"  fck'ya Oranı            : %{oran:.0f}",
            ]
            if not kabul:
                satirlar.extend([
                    "",
                    "ACİL ÖNLEMLER (Yüklenici ve Yapı Denetim Bilgilendirilmeli):",
                    "  1. İlgili bölümde yüklemeyi DURDURUN (TS 500 md.4.4.4)",
                    "  2. Yapı denetim kuruluşuna yazılı bildirim (4708 sayılı Kanun)",
                    "  3. Karot testi ile teyit edin (min 3 karot, TS EN 12504-1)",
                    "  4. Karot sonucu da düşükse: statik hesap kontrolü zorunlu",
                    "  5. Nihai karar: Güçlendirme veya ilgili bölüm yeniden yapım",
                ])
            else:
                satirlar.append(
                    f"  Durum: Değer kabul sınırı üzerinde. "
                    f"{'Yeterli güvenlik marjı.' if oran >= 100 else 'Limitin hemen üzerinde, yakın takip önerilir.'}"
                )

        # ── Slump / Kıvam Testi ───────────────────────────────────────────
        elif any(x in test for x in ["slump", "kıvam", "çökme"]):
            if 50 <= deger <= 90:
                sinif, durum, kabul = "S2", "Normal — döşeme, kolon, kiriş", True
            elif 90 < deger <= 150:
                sinif, durum, kabul = "S3", "Akışkan — pompalı beton için uygun", True
            elif deger < 50:
                sinif, durum, kabul = "S1", "Çok kuru — işlenemez beton", False
            else:
                sinif, durum, kabul = "S4+", "Çok akışkan — su/çimento oranı fazla", False

            etiket = "✅ KABUL" if kabul else "❌ RED"
            satirlar = [
                "SLUMP TESTİ DEĞERLENDİRMESİ (TS 9967 + TS EN 12350-2):",
                f"  Ölçülen Slump : {deger:.0f} mm",
                f"  Kıvam Sınıfı  : {sinif}",
                f"  Durum         : {durum}",
                f"  KARAR         : {etiket}",
            ]
            if not kabul:
                onlem = (
                    "Superplastizan katkı ekleyin — ASLA su eklemeyin (TS 9967 yasak)"
                    if deger < 50
                    else "Mikser geri gönderin. Su eklenmişse tüm partiyi reddedin."
                )
                satirlar.extend(["", f"Önlem: {onlem}"])

        # ── Demir Çekme / Akma ────────────────────────────────────────────
        elif any(x in malzeme for x in ["demir", "donatı", "çelik"]):
            # B500C (yaygın): fy_min=500 MPa, ft_min=575 MPa
            if any(x in test for x in ["akma", "fy", "yield"]):
                min_val, sinif_adi = 500, "B500C Akma Dayanımı"
            else:
                min_val, sinif_adi = 575, "B500C Çekme Dayanımı"

            kabul = deger_mpa >= min_val
            etiket = "✅ KABUL" if kabul else "❌ RED — Parti Reddedilmeli"
            satirlar = [
                f"DEMİR TEST DEĞERLENDİRMESİ (TS 708 + TS EN 10080):",
                f"  Test Türü     : {sinif_adi}",
                f"  Min. Sınır    : {min_val} MPa",
                f"  Ölçülen Değer : {deger:.1f} {birim}",
                f"  KARAR         : {etiket}",
            ]
            if not kabul:
                satirlar.extend([
                    "",
                    "Önlemler:",
                    "  1. Tüm partiyi sertifika ile birlikte reddedin",
                    "  2. Farklı partiden numune alın ve tekrar test ettirin",
                    "  3. Yapı denetim kuruluşuna bilgi verin",
                ])

        else:
            satirlar = [
                "MALZEME TEST DEĞERLENDİRMESİ:",
                f"  Malzeme    : {parametreler.get('malzeme_turu', '')}",
                f"  Test       : {parametreler.get('test_turu', '')}",
                f"  Ölçülen    : {deger} {birim}",
                "",
                "Bu test türü için otomatik değerlendirme henüz tanımlı değil.",
                "İlgili TS/EN standardını ve CŞB özelname değerlerini kontrol edin.",
            ]

        return "\n".join(satirlar)

    def _arac_isg_risk_degerlendirme(self, parametreler: dict) -> str:
        """6331 İSG Kanunu + Yapı İşleri Yönetmeliğine göre risk değerlendirmesi."""
        calisma = str(parametreler.get("calisma_turu", "")).lower()
        yukseklik = float(parametreler.get("yukseklik_m", 0))
        personel = int(parametreler.get("personel_sayisi", 1))
        ortam = str(parametreler.get("ortam", "Açık Hava"))

        CALISMA_KURALLARI = {
            "kazı": {
                "anahtar": ["kazı", "hafriyat", "hendek"],
                "temel_tedbirler": [
                    "1.5m üzeri kazı: iksa/destek ZORUNLU (Yapı İSG Yön. md.28)",
                    "2m+ derinlik: her 2m'de destek veya şev açısı ≤45° (killi zemin)",
                    "Kazı kenarına malzeme yığmayı yasakla — en az 1m mesafe bırak",
                    "Günlük zemin stabilitesi kontrolü (özellikle yağmur/kar sonrası)",
                    "Gece ve gündüz ışıklandırma + bariyer zorunlu",
                    "3m+ derinlikte giriş/çıkış merdiveni zorunlu",
                ],
                "baz_risk": "Kritik"
            },
            "yüksekte": {
                "anahtar": ["yüksekte", "çatı", "iskele", "çelik", "bina kenar"],
                "temel_tedbirler": [
                    "2m+ yükseklik: tam vücut paraşüt kemeri zorunlu (TS EN 361)",
                    "İskele: zemine 4:1 oranı, çapraz ve yatay bağlantı şart",
                    "İskele yükleme kapasitesi hesabı yapılmalı",
                    "Paraşüt ağı veya koruma ağı kurulumu",
                    "Sağlık raporu: vertigo, epilepsi olan çalışan çıkamaZ",
                    "Rüzgar hızı >10 m/s → çalışmayı durdur",
                ],
                "baz_risk": "Kritik"
            },
            "beton dökümü": {
                "anahtar": ["beton", "döküm", "pompa"],
                "temel_tedbirler": [
                    "Beton pompası hortumu: ani hareket riski — 2 kişi tutmalı",
                    "Vibratör operatörü: yalıtımlı eldiven + uzun çizme",
                    "Dökümden önce kalıp stabilitesi ve payanda kontrolü",
                    "Gece dökümünde: min 50 lux aydınlatma",
                    "Sıcak hava (>30°C): erken akşam saatlerinde dök, kür sulaması yap",
                ],
                "baz_risk": "Orta"
            },
            "demir": {
                "anahtar": ["demir", "donatı", "kesim", "bükme"],
                "temel_tedbirler": [
                    "Demir uçları: mandal/plastik kapak ZORUNLU (göz yaralanması)",
                    "Kesim ve bükme sırasında: koruyucu gözlük + deri eldiven",
                    "Geçiş yollarına dağınık demir yığma — temiz koridor bırak",
                    "Uzun demir taşıma: koordineli hareket, min 2 kişi",
                    "Yatay demirler: altına destek konarak depolanmalı",
                ],
                "baz_risk": "Orta"
            },
            "kalıp": {
                "anahtar": ["kalıp", "form", "iskele kurulum"],
                "temel_tedbirler": [
                    "Kalıp tasarımı: beton yükü + dinamik yük kapasitesi hesabı",
                    "Lateral basınç: dökme hızı 1m/saatten fazlaysa ek destek",
                    "Payandalar düz ve sağlam zemine oturmalı",
                    "Söküm: TS EN 13670 süreleri kesinlikle bekle",
                    "Kalıp sökme: destekler aşamalı kaldırılmalı, tek seferde değil",
                ],
                "baz_risk": "Yüksek"
            },
            "elektrik": {
                "anahtar": ["elektrik", "kablo", "hat", "trafo"],
                "temel_tedbirler": [
                    "Şantiye dağıtım panosu: topraklama + kaçak akım rölesi ZORUNLU",
                    "Kablo geçişleri: yerde plastik koruma tüpü içinde",
                    "Islak zemin/su bölgesinde elektrikli alet kullanmayı yasakla",
                    "ENERJ İkesim: lockout/tagout prosedürü uygula",
                    "Elektrik uzmanı belgesi olmayan personel panel açamaz",
                ],
                "baz_risk": "Kritik"
            },
        }

        eslesen_tedbirler = []
        genel_risk = "Orta"

        for kategori, veri in CALISMA_KURALLARI.items():
            for kelime in veri["anahtar"]:
                if kelime in calisma:
                    eslesen_tedbirler = veri["temel_tedbirler"]
                    genel_risk = veri["baz_risk"]
                    break

        # Yüksekliğe göre ek kurallar
        ek_tedbirler = []
        if yukseklik >= 2.0:
            ek_tedbirler.append(
                f"YÜKSEKLIK {yukseklik:.1f}m: Düşme önlemleri zorunlu (6331 md.12)"
            )
        if yukseklik >= 6.0:
            ek_tedbirler.append(
                f"YÜKSEKLIK {yukseklik:.1f}m: Güvenlik ağı + tam vücut kemeri ZORUNLU"
            )
            genel_risk = "Kritik"

        # Personel sayısına göre yasal zorunluluklar
        if personel >= 20:
            ek_tedbirler.append(
                "20+ PERSONEL: Tam zamanlı İSG uzmanı zorunlu (6331 md.8)"
            )
        if personel >= 50:
            ek_tedbirler.append(
                "50+ PERSONEL: İşyeri hekimi + sağlık birimi zorunlu"
            )

        # Kapalı alan
        if any(x in ortam.lower() for x in ["kapalı", "bodrum", "tünel"]):
            ek_tedbirler.extend([
                "KAPALI ALAN: Oksijen seviyesi ölçümü (min %19.5) — girmeden önce",
                "KAPALI ALAN: Tahliye planı + acil çıkış işaretleme zorunlu",
            ])

        emoji_risk = {
            "Kritik": "🔴", "Yüksek": "🟠", "Orta": "🟡", "Düşük": "🟢"
        }.get(genel_risk, "🟡")

        satirlar = [
            "İSG RİSK DEĞERLENDİRMESİ:",
            f"  Çalışma Türü  : {parametreler.get('calisma_turu', '')}",
            f"  Personel      : {personel} kişi",
            f"  Yükseklik     : {yukseklik:.1f} m",
            f"  Ortam         : {ortam}",
            f"  RİSK SEVİYESİ : {emoji_risk} {genel_risk}",
            "",
            "Zorunlu Tedbirler (6331 + Yapı İşleri İSG Yönetmeliği):",
        ]
        for tedbir in eslesen_tedbirler:
            satirlar.append(f"  ✔ {tedbir}")
        for tedbir in ek_tedbirler:
            satirlar.append(f"  ⚠ {tedbir}")

        satirlar.extend([
            "",
            "Her Şantiyede Genel Zorunluluklar:",
            "  ✔ Tüm işçiler SGK'ya kayıtlı olmalı",
            "  ✔ KKD: baret + reflektif yelek + güvenlik ayakkabısı",
            "  ✔ İş talimatları Türkçe levhalarla bildirilmeli",
            "  ✔ Kaza → işveren 3 iş günü içinde SGK'ya bildirim",
            "  Yasal Dayanak: 6331 Sayılı İSG Kanunu + Yapı İşlerinde",
            "                 Sağlık ve Güvenlik Yönetmeliği (2013/35076)",
        ])

        return "\n".join(satirlar)

    def _arac_gecikme_ceza_hesapla(self, parametreler: dict) -> str:
        """4735 md.20 gecikme cezası hesabı — günlük ‰5."""
        try:
            from decimal import Decimal, ROUND_HALF_UP
            sozlesme = Decimal(str(parametreler.get("sozlesme_bedeli", 0)))
            gun = int(parametreler.get("gecikme_gun_sayisi", 0))
            onceki_yuzde = Decimal(str(parametreler.get("onceki_ceza_yuzdesi", 0)))

            if sozlesme <= 0:
                return "HATA: Sözleşme bedeli sıfırdan büyük olmalıdır."
            if gun < 0:
                return "HATA: Gecikme gün sayısı negatif olamaz."

            GUNLUK_ORAN = Decimal("0.005")   # ‰5 = %0.5/gün
            FESIH_ESIGI = Decimal("0.30")    # %30 toplam ceza → fesih

            ceza_bu_donem = sozlesme * GUNLUK_ORAN * gun
            ceza_bu_donem_yuzdesi = GUNLUK_ORAN * gun * 100

            toplam_ceza_yuzdesi = onceki_yuzde + ceza_bu_donem_yuzdesi
            toplam_ceza_tutari = sozlesme * (toplam_ceza_yuzdesi / 100)

            fesih_esigi_tl = sozlesme * FESIH_ESIGI
            fesih_asim = toplam_ceza_yuzdesi > (FESIH_ESIGI * 100)

            kalan_fesih_gun = 0
            if not fesih_asim:
                kalan_yuzde = (FESIH_ESIGI * 100) - toplam_ceza_yuzdesi
                kalan_fesih_gun = int(kalan_yuzde / (GUNLUK_ORAN * 100)) + 1

            sonuc = (
                f"Gecikme Cezası Hesabı — 4735 Sayılı KİK md.20\n"
                f"{'─' * 55}\n"
                f"  Sözleşme Bedeli      : {float(sozlesme):>15,.2f} ₺\n"
                f"  Günlük Ceza Oranı    : ‰5 (%0.5/gün)\n"
                f"  Fesih Eşiği          : %30\n"
                f"{'─' * 55}\n"
                f"  Gecikme Süresi       : {gun} gün\n"
                f"  Bu Dönem Ceza (%{float(ceza_bu_donem_yuzdesi):.1f}) : {float(ceza_bu_donem):>12,.2f} ₺\n"
                f"{'─' * 55}\n"
                f"  Önceki Birikimli     : %{float(onceki_yuzde):.2f}\n"
                f"  TOPLAM CEZA ORANI    : %{float(toplam_ceza_yuzdesi):.2f}\n"
                f"  TOPLAM CEZA TUTARI   : {float(toplam_ceza_tutari):>12,.2f} ₺\n"
                f"{'─' * 55}\n"
                f"  Fesih Eşiği Tutarı   : {float(fesih_esigi_tl):>12,.2f} ₺ (%30)\n"
            )
            if fesih_asim:
                sonuc += (
                    f"  ⚠️  FESİH EŞİĞİ AŞILDI!\n"
                    f"  Toplam ceza %30'u geçti → İdare sözleşmeyi feshedebilir.\n"
                    f"  (4735 md.20: İdare tek taraflı fesih hakkına sahiptir)"
                )
            else:
                sonuc += (
                    f"  Fesih Eşiğine Kalan  : {kalan_fesih_gun} gün daha gecikme\n"
                    f"  Durum                : Fesih eşiği henüz aşılmadı"
                )
            return sonuc
        except Exception as e:
            return f"Gecikme ceza hesap hatası: {e}"

    # ── Gayrimenkul Değerleme Araç İmplementasyonları ──────────────────────

    def _arac_emlak_url_analiz(self, parametreler: dict) -> str:
        """
        Gayrimenkul ilan URL'sinden veri çeker.
        JSON-LD schema → Open Graph meta → sayfa metni sırasıyla dener.
        Başarısızsa kullanıcıdan manuel bilgi ister.
        """
        url = str(parametreler.get("url", "")).strip()
        if not url:
            return "HATA: URL boş."

        MANUEL_ISTEK = (
            "\n\nSayfaya ulaşamadım (site bot koruması kullanıyor).\n"
            "Lütfen ilanın şu bilgilerini mesaj kutusuna yazın:\n"
            "  • Fiyat (TL)\n"
            "  • Brüt/net m²\n"
            "  • Oda sayısı (örn: 3+1)\n"
            "  • Kat bilgisi (örn: 4/8)\n"
            "  • Bina yaşı\n"
            "  • Tapu türü (kat mülkiyeti / kat irtifakı / hisseli)\n"
            "  • İlçe ve mahalle\n"
            "  • Öne çıkan özellikler (site, otopark, manzara vb.)\n\n"
            "Bu bilgileri verirseniz gerçek bir değerleme yapabilirim."
        )

        try:
            import requests
            import re
            import json as _json

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "tr-TR,tr;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

            try:
                resp = requests.get(url, headers=headers, timeout=12,
                                    allow_redirects=True)
            except requests.exceptions.Timeout:
                return f"Zaman aşımı: {url}" + MANUEL_ISTEK
            except requests.exceptions.ConnectionError:
                return f"Bağlantı hatası: {url}" + MANUEL_ISTEK

            # Cloudflare veya başka koruma → HTML çok kısa veya hata kodu
            if resp.status_code in (403, 429, 503):
                return f"Site erişimi engellendi (HTTP {resp.status_code})." + MANUEL_ISTEK
            if resp.status_code != 200:
                return f"HTTP {resp.status_code} hatası." + MANUEL_ISTEK

            try:
                resp.encoding = resp.apparent_encoding or "utf-8"
            except Exception:
                resp.encoding = "utf-8"

            html = resp.text

            # Cloudflare JS challenge tespiti
            if len(html) < 2000 or "cf-browser-verification" in html or \
               "Just a moment" in html or "Enable JavaScript" in html:
                return "Site Cloudflare koruması kullanıyor." + MANUEL_ISTEK

            bulunan = {}

            # ── 1. JSON-LD schema.org verisi (en güvenilir) ────────────────
            ld_blocks = re.findall(
                r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                html, re.DOTALL | re.IGNORECASE
            )
            for blok in ld_blocks:
                try:
                    veri = _json.loads(blok.strip())
                    if isinstance(veri, list):
                        veri = veri[0]
                    tip = str(veri.get("@type", "")).lower()
                    if any(x in tip for x in ["realestate", "residence", "house",
                                              "apartment", "product", "offer"]):
                        if "offers" in veri:
                            bulunan["fiyat"] = veri["offers"].get("price", "")
                            bulunan["para_birimi"] = veri["offers"].get("priceCurrency", "TRY")
                        if "name" in veri:
                            bulunan["baslik"] = veri["name"]
                        if "description" in veri:
                            bulunan["aciklama"] = str(veri["description"])[:500]
                        if "address" in veri:
                            adres = veri["address"]
                            if isinstance(adres, dict):
                                bulunan["adres"] = (
                                    adres.get("addressLocality", "") + " " +
                                    adres.get("addressRegion", "")
                                ).strip()
                        if "floorSize" in veri:
                            bulunan["m2"] = veri["floorSize"].get("value", "")
                        if "numberOfRooms" in veri:
                            bulunan["oda"] = veri["numberOfRooms"]
                except Exception:
                    pass

            # ── 2. Open Graph ve meta etiketleri ──────────────────────────
            meta_patterns = {
                "og_title":       r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                "og_desc":        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
                "og_price":       r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([^"\']+)',
                "twitter_title":  r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)',
                "twitter_desc":   r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)',
            }
            meta = {}
            for k, pat in meta_patterns.items():
                m = re.search(pat, html, re.IGNORECASE)
                if m:
                    meta[k] = m.group(1).strip()

            if not bulunan.get("baslik") and (meta.get("og_title") or meta.get("twitter_title")):
                bulunan["baslik"] = meta.get("og_title") or meta.get("twitter_title", "")
            if not bulunan.get("aciklama") and (meta.get("og_desc") or meta.get("twitter_desc")):
                bulunan["aciklama"] = (meta.get("og_desc") or meta.get("twitter_desc", ""))[:400]
            if not bulunan.get("fiyat") and meta.get("og_price"):
                bulunan["fiyat"] = meta["og_price"]

            # ── 3. Regex ile ham HTML'den veri çek ───────────────────────
            # Fiyat
            if not bulunan.get("fiyat"):
                fiyat_match = re.search(
                    r'(\d[\d.,]{4,})\s*(?:TL|₺|lira)',
                    html, re.IGNORECASE
                )
                if fiyat_match:
                    bulunan["fiyat"] = fiyat_match.group(1)

            # m²
            if not bulunan.get("m2"):
                m2_match = re.search(r'(\d{2,4})\s*m[²2²]', html)
                if m2_match:
                    bulunan["m2"] = m2_match.group(1)

            # Oda sayısı
            if not bulunan.get("oda"):
                oda_match = re.search(r'(\d\+\d|\d\s*\+\s*\d)\s*(?:oda|room)', html, re.IGNORECASE)
                if oda_match:
                    bulunan["oda"] = oda_match.group(1).replace(" ", "")

            # Sayfa metninden özet al (script/style temizlenmiş)
            temiz_html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL)
            temiz_html = re.sub(r'<style[^>]*>.*?</style>', ' ', temiz_html, flags=re.DOTALL)
            temiz_html = re.sub(r'<[^>]+>', ' ', temiz_html)
            temiz_html = re.sub(r'\s+', ' ', temiz_html).strip()
            sayfa_ozeti = temiz_html[:4000]

            # ── Sonuç raporu ──────────────────────────────────────────────
            kaynak = (
                "sahibinden.com" if "sahibinden" in url else
                "emlakjet.com"   if "emlakjet"   in url else
                "hepsiemlak.com" if "hepsiemlak" in url else
                "zingat.com"     if "zingat"     in url else
                url.split("/")[2] if "/" in url else url
            )

            satirlar = [f"İlan Kaynağı: {kaynak}", f"URL: {url}", "─" * 50]

            if bulunan.get("baslik"):
                satirlar.append(f"Başlık  : {bulunan['baslik']}")
            if bulunan.get("fiyat"):
                satirlar.append(f"Fiyat   : {bulunan['fiyat']} TL")
            if bulunan.get("m2"):
                satirlar.append(f"Alan    : {bulunan['m2']} m²")
            if bulunan.get("oda"):
                satirlar.append(f"Oda     : {bulunan['oda']}")
            if bulunan.get("adres"):
                satirlar.append(f"Adres   : {bulunan['adres']}")
            if bulunan.get("aciklama"):
                satirlar.append(f"Açıklama: {bulunan['aciklama']}")

            satirlar.append("─" * 50)
            satirlar.append("Sayfa İçeriği:")
            satirlar.append(sayfa_ozeti)

            # Hiç yapısal veri bulunamadıysa uyar
            if not any(bulunan.values()):
                satirlar.insert(3,
                    "⚠️ Yapısal veri (JSON-LD/meta) bulunamadı — "
                    "aşağıdaki ham metin üzerinden analiz yapılıyor."
                )

            return "\n".join(satirlar)

        except Exception as e:
            return f"URL analizi beklenmedik hata: {e}" + MANUEL_ISTEK

    def _arac_emsal_karsilastir(self, parametreler: dict) -> str:
        """
        Emsal analizi için bölge parametrelerini yapılandırır.
        Gerçek m² fiyatlarını sistem promptundaki bilgisiyle Claude belirler.
        """
        il = str(parametreler.get("il", "")).strip()
        ilce = str(parametreler.get("ilce", "")).strip()
        mahalle = str(parametreler.get("mahalle", "")).strip()
        mulk_tipi = str(parametreler.get("mulk_tipi", "Daire")).strip()
        alan_m2 = float(parametreler.get("alan_m2", 0) or 0)

        # Bölgesel fiyat veritabanı (2025–2026 piyasa ortalama, ₺/m²)
        BOLGE_FIYATLARI = {
            "istanbul": {
                "_default": (40000, 80000),
                "şişli": (80000, 180000),
                "beşiktaş": (90000, 220000),
                "kadıköy": (70000, 140000),
                "üsküdar": (55000, 110000),
                "beyoğlu": (60000, 130000),
                "fatih": (50000, 110000),
                "bakırköy": (60000, 130000),
                "avcılar": (35000, 65000),
                "bağcılar": (30000, 60000),
                "esenler": (28000, 55000),
                "ataşehir": (65000, 130000),
                "maltepe": (50000, 95000),
                "pendik": (35000, 70000),
                "kartal": (40000, 75000),
                "bahçelievler": (45000, 90000),
                "başakşehir": (40000, 80000),
                "esenyurt": (25000, 50000),
                "eyüpsultan": (40000, 75000),
                "sarıyer": (80000, 200000),
                "zeytinburnu": (45000, 85000),
                "sultangazi": (25000, 48000),
                "gaziosmanpaşa": (30000, 58000),
                "kağıthane": (50000, 100000),
                "küçükçekmece": (40000, 75000),
                "büyükçekmece": (30000, 60000),
                "silivri": (20000, 45000),
                "çatalca": (15000, 35000),
                "arnavutköy": (20000, 45000),
                "tuzla": (35000, 65000),
                "çekmeköy": (45000, 85000),
                "sancaktepe": (35000, 65000),
                "sultanbeyli": (25000, 48000),
                "beykoz": (55000, 130000),
                "şile": (15000, 40000),
                "adalar": (60000, 150000),
            },
            "ankara": {
                "_default": (18000, 40000),
                "çankaya": (25000, 65000),
                "keçiören": (14000, 28000),
                "mamak": (12000, 25000),
                "yenimahalle": (16000, 35000),
                "etimesgut": (18000, 38000),
                "sincan": (12000, 24000),
                "altındağ": (10000, 22000),
                "pursaklar": (13000, 26000),
                "gölbaşı": (20000, 42000),
            },
            "izmir": {
                "_default": (25000, 60000),
                "konak": (30000, 75000),
                "karşıyaka": (35000, 75000),
                "bornova": (25000, 55000),
                "buca": (20000, 45000),
                "çiğli": (22000, 50000),
                "bayraklı": (28000, 60000),
                "balçova": (30000, 65000),
                "narlıdere": (30000, 65000),
                "gaziemir": (18000, 40000),
            },
            "antalya": {
                "_default": (25000, 55000),
                "muratpaşa": (30000, 70000),
                "konyaaltı": (35000, 80000),
                "kepez": (18000, 38000),
                "lara": (40000, 90000),
                "döşemealtı": (20000, 45000),
            },
            "bursa": {
                "_default": (18000, 40000),
                "osmangazi": (20000, 45000),
                "nilüfer": (22000, 50000),
                "yıldırım": (14000, 30000),
                "görükle": (18000, 40000),
            },
        }

        # Tarla ve arsa için ayrı tablo (₺/m²)
        TARLA_ARSA_FIYAT = {
            "istanbul": {
                "arsa_imarlı": (5000, 80000),
                "tarla": (200, 2000),
            },
            "ankara": {
                "arsa_imarlı": (2000, 25000),
                "tarla": (100, 800),
            },
            "izmir": {
                "arsa_imarlı": (3000, 40000),
                "tarla": (150, 1200),
            },
            "_default": {
                "arsa_imarlı": (500, 15000),
                "tarla": (50, 500),
            },
        }

        # Bu araç yapısal parametreleri döndürür.
        # Gerçek m² fiyatlarını Claude kendi bilgisiyle belirler (sistem promptuna bakılır).
        konum = il
        if ilce:
            konum += f" / {ilce}"
        if mahalle:
            konum += f" / {mahalle}"

        satirlar = [
            "EMSAL ANALİZİ PARAMETRELERİ",
            "─" * 50,
            f"  Konum     : {konum}",
            f"  Mülk Tipi : {mulk_tipi}",
        ]
        if alan_m2 > 0:
            satirlar.append(f"  Alan      : {alan_m2:,.0f} m²")

        satirlar.extend([
            "─" * 50,
            "BU BÖLGEDEKİ GERÇEK PİYASA VERİLERİNİ KULLAN:",
            f"  → {konum} için {mulk_tipi} m² birim fiyat aralığını bildiğin",
            "    piyasa verilerinden belirle (sistem promptundaki tabloya bak).",
            "  → Mahalle özelinde bilgin varsa onu kullan.",
            "  → Benzer özellikteki son ilanlardan m² ortalaması hesapla.",
            "  → Kira/satış oranını (brüt yield) bu bölge için gerçekçi ver.",
        ])
        if alan_m2 > 0:
            satirlar.extend([
                "─" * 50,
                f"  Alan {alan_m2:,.0f} m² için toplam değer hesabını",
                "  belirleyeceğin m² fiyatı üzerinden gayrimenkul_degerle",
                "  aracına aktar.",
            ])

        return "\n".join(satirlar)

    def _arac_gayrimenkul_degerle(self, parametreler: dict) -> str:
        """Kapsamlı gayrimenkul değerleme raporu üretir."""
        mulk_tipi = str(parametreler.get("mulk_tipi", "Daire"))
        il = str(parametreler.get("il", ""))
        ilce = str(parametreler.get("ilce", ""))
        mahalle = str(parametreler.get("mahalle", ""))
        alan_m2 = float(parametreler.get("alan_m2", 0) or 0)
        oda_sayisi = str(parametreler.get("oda_sayisi", ""))
        bina_yasi = int(parametreler.get("bina_yasi", 0) or 0)
        kat = str(parametreler.get("kat", ""))
        tapu_turu = str(parametreler.get("tapu_turu", "Kat Mülkiyeti"))
        ilan_fiyati = float(parametreler.get("ilan_fiyati", 0) or 0)
        ozellikler = str(parametreler.get("ozellikler", ""))
        imar_durumu = str(parametreler.get("imar_durumu", ""))
        ticari_kat = str(parametreler.get("ticari_kat", ""))
        cephe_turu = str(parametreler.get("cephe_turu", ""))
        mevcut_kira_aylik = float(parametreler.get("mevcut_kira_aylik", 0) or 0)
        ada_no = str(parametreler.get("ada_no", "")).strip()
        parsel_no = str(parametreler.get("parsel_no", "")).strip()
        tahmini_mod = (ilan_fiyati == 0)  # Fiyat girilmemişse tahmini mod

        if alan_m2 <= 0:
            return "HATA: alan_m2 sıfırdan büyük olmalıdır."

        # Bölge bazlı m² birim fiyatı (emsal karşılaştırma sonucuyla aynı tablo)
        BOLGE_M2 = {
            "istanbul": {
                "_default": (40000, 80000),
                "şişli": (80000, 180000), "beşiktaş": (90000, 220000),
                "kadıköy": (70000, 140000), "üsküdar": (55000, 110000),
                "bakırköy": (60000, 130000), "ataşehir": (65000, 130000),
                "avcılar": (35000, 65000), "bağcılar": (30000, 60000),
                "esenyurt": (25000, 50000), "maltepe": (50000, 95000),
                "sarıyer": (80000, 200000), "başakşehir": (40000, 80000),
                "kağıthane": (50000, 100000), "pendik": (35000, 70000),
                "beyoğlu": (60000, 130000), "fatih": (50000, 110000),
            },
            "ankara": {
                "_default": (18000, 40000),
                "çankaya": (25000, 65000), "keçiören": (14000, 28000),
                "yenimahalle": (16000, 35000), "etimesgut": (18000, 38000),
            },
            "izmir": {
                "_default": (25000, 60000),
                "konak": (30000, 75000), "karşıyaka": (35000, 75000),
                "bornova": (25000, 55000), "buca": (20000, 45000),
            },
            "antalya": {"_default": (25000, 55000), "muratpaşa": (30000, 70000)},
            "bursa": {"_default": (18000, 40000), "nilüfer": (22000, 50000)},
            "_default": (8000, 20000),
        }

        # Bölge fiyatını bul
        il_lower = il.lower()
        ilce_lower = ilce.lower()
        mt_lower = mulk_tipi.lower()
        tarla_mi = any(x in mt_lower for x in ["tarla", "arazi"])
        arsa_mi = "arsa" in mt_lower
        dukkan_ofis_mi = any(x in mt_lower for x in ["dükkan", "ofis", "dukkan"])

        if tarla_mi:
            bolge_fmin, bolge_fmax = 100, 800
        elif arsa_mi:
            arsa_carpan = {"istanbul": (5000, 80000), "ankara": (2000, 25000),
                           "izmir": (3000, 40000)}.get(il_lower, (500, 15000))
            bolge_fmin, bolge_fmax = arsa_carpan
        elif dukkan_ofis_mi:
            # Ticari m² fiyatı konut fiyatının ~1.3-1.8x (cephe/kat düzeltmesi ayrıca uygulanır)
            bolge = BOLGE_M2.get(il_lower, {})
            if isinstance(bolge, dict):
                base_min, base_max = bolge.get(ilce_lower, bolge.get("_default", (8000, 20000)))
            else:
                base_min, base_max = BOLGE_M2.get("_default", (8000, 20000))
            bolge_fmin, bolge_fmax = int(base_min * 1.3), int(base_max * 1.8)
        else:
            bolge = BOLGE_M2.get(il_lower, {})
            if isinstance(bolge, dict):
                bolge_fmin, bolge_fmax = bolge.get(ilce_lower, bolge.get("_default", (8000, 20000)))
            else:
                bolge_fmin, bolge_fmax = BOLGE_M2.get("_default", (8000, 20000))

        # Düzeltme faktörleri
        duzeltme = 1.0

        # Bina yaşı düzeltmesi
        if bina_yasi == 0:
            duzeltme *= 1.15  # Sıfır bina +%15
        elif bina_yasi <= 5:
            duzeltme *= 1.10
        elif bina_yasi <= 15:
            duzeltme *= 1.00
        elif bina_yasi <= 25:
            duzeltme *= 0.90
        else:
            duzeltme *= 0.80

        # Kat düzeltmesi
        kat_lower = kat.lower()
        if "zemin" in kat_lower or kat_lower.startswith("0"):
            duzeltme *= 0.90
        elif "çatı" in kat_lower or "penthouse" in kat_lower:
            duzeltme *= 0.95
        elif "son" in kat_lower:
            duzeltme *= 1.05

        # Tapu türü düzeltmesi
        if "kat mülkiyeti" in tapu_turu.lower():
            duzeltme *= 1.00
        elif "kat irtifakı" in tapu_turu.lower():
            duzeltme *= 0.92
        elif "hisseli" in tapu_turu.lower():
            duzeltme *= 0.80
        elif "zilyetlik" in tapu_turu.lower():
            duzeltme *= 0.60

        # Özellik düzeltmeleri
        ozel_lower = ozellikler.lower()
        if "deniz manzara" in ozel_lower or "boğaz manzara" in ozel_lower:
            duzeltme *= 1.20
        elif "manzara" in ozel_lower:
            duzeltme *= 1.08
        if "site" in ozel_lower:
            duzeltme *= 1.05
        if "otopark" in ozel_lower:
            duzeltme *= 1.03

        # Dükkan/Ofis ticari düzeltmeleri
        if dukkan_ofis_mi:
            cephe_lower = cephe_turu.lower()
            if "ana cadde" in cephe_lower:
                duzeltme *= 1.25
            elif "sokak" in cephe_lower or "ara yol" in cephe_lower:
                duzeltme *= 0.85
            elif "pasaj" in cephe_lower or "çarşı" in cephe_lower or "carsi" in cephe_lower:
                duzeltme *= 0.75
            elif "avm" in cephe_lower:
                duzeltme *= 1.10
            tkat_lower = ticari_kat.lower()
            if "asma" in tkat_lower:
                duzeltme *= 0.80
            elif "1. kat" in tkat_lower:
                duzeltme *= 0.70
            elif "2. kat" in tkat_lower or "üzeri" in tkat_lower or "uzeri" in tkat_lower:
                duzeltme *= 0.60

        # Hesaplamalar
        m2_fmin = bolge_fmin * duzeltme
        m2_fmax = bolge_fmax * duzeltme
        m2_fiyat_orta = (m2_fmin + m2_fmax) / 2

        deger_min = alan_m2 * m2_fmin
        deger_max = alan_m2 * m2_fmax
        deger_orta = alan_m2 * m2_fiyat_orta

        # Kira getirisi — Türkiye brüt kira getirisi %3–5/yıl (2024-2026 gerçeği)
        # Düşük fiyatlı bölge (m²<30k): %4–5, pahalı bölge (m²>80k): %2.5–3.5
        if m2_fiyat_orta < 30000:
            getiri_min, getiri_max = 0.04, 0.05   # %4–5
        elif m2_fiyat_orta < 60000:
            getiri_min, getiri_max = 0.035, 0.045  # %3.5–4.5
        elif m2_fiyat_orta < 100000:
            getiri_min, getiri_max = 0.03, 0.04    # %3–4
        else:
            getiri_min, getiri_max = 0.025, 0.035  # %2.5–3.5
        kira_aylik_min = deger_min * getiri_min / 12
        kira_aylik_max = deger_max * getiri_max / 12
        kira_aylik_orta = (kira_aylik_min + kira_aylik_max) / 2
        brut_getiri = (kira_aylik_orta * 12) / deger_orta * 100 if deger_orta > 0 else 0
        geri_odeme_yil = 100 / brut_getiri if brut_getiri > 0 else 0

        # Dükkan/Ofis: mevcut kira biliniyorsa gerçek getiriyi kullan
        if dukkan_ofis_mi and mevcut_kira_aylik > 0:
            kira_aylik_orta = mevcut_kira_aylik
            kira_aylik_min = mevcut_kira_aylik * 0.9
            kira_aylik_max = mevcut_kira_aylik * 1.1
            brut_getiri = (mevcut_kira_aylik * 12) / deger_orta * 100 if deger_orta > 0 else 0
            geri_odeme_yil = 100 / brut_getiri if brut_getiri > 0 else 0

        # İlan fiyatı karşılaştırması
        ilan_yorum = ""
        if ilan_fiyati > 0:
            fark = (ilan_fiyati - deger_orta) / deger_orta * 100
            if fark > 20:
                ilan_yorum = f"  ⚠️  İlan fiyatı piyasa ortalamasının %{fark:.0f} ÜSTÜNDE (pahalı)"
            elif fark < -15:
                ilan_yorum = f"  ✅ İlan fiyatı piyasa ortalamasının %{abs(fark):.0f} ALTINDA (uygun)"
            else:
                ilan_yorum = f"  ✅ İlan fiyatı piyasa değeriyle UYUMLU (%{abs(fark):.0f} {'fazla' if fark > 0 else 'az'})"

        # Yatırım puanı (1–10)
        yatirim_puani = 5
        if brut_getiri >= 6:
            yatirim_puani += 2
        elif brut_getiri >= 4:
            yatirim_puani += 1
        if "kat mülkiyeti" in tapu_turu.lower():
            yatirim_puani += 1
        if bina_yasi <= 5:
            yatirim_puani += 1
        if "hisseli" in tapu_turu.lower() or "zilyetlik" in tapu_turu.lower():
            yatirim_puani -= 2
        yatirim_puani = max(1, min(10, yatirim_puani))

        yatirim_yorum = {
            1: "Riskli — almayın",
            2: "Çok riskli",
            3: "Zayıf yatırım",
            4: "Ortanın altı",
            5: "Orta düzey",
            6: "İyi yatırım",
            7: "Çok iyi",
            8: "Mükemmel",
            9: "Olağanüstü",
            10: "Kaçırılmaz fırsat",
        }.get(yatirim_puani, "Orta")

        # Tapu uyarısı
        tapu_uyari = ""
        if "hisseli" in tapu_turu.lower():
            tapu_uyari = "\n  ⚠️  UYARI: Hisseli tapu — mutlaka avukat danışmanı alın!"
        elif "zilyetlik" in tapu_turu.lower():
            tapu_uyari = "\n  ⚠️  KRİTİK: Zilyetlik tapusu yüksek risk! Mutlaka hukuki danışmanlık alın."

        rapor_basligi = "  TAHMİNİ DEĞERLEME RAPORU" if tahmini_mod else "  GAYRİMENKUL DEĞERLEME RAPORU"
        rapor = [
            "=" * 60,
            rapor_basligi,
            "=" * 60,
            f"  Mülk Tipi  : {mulk_tipi}" + (f" / {oda_sayisi}" if oda_sayisi else ""),
            f"  Konum      : {il}" + (f" / {ilce}" if ilce else "") + (f" / {mahalle}" if mahalle else ""),
            f"  Ada/Parsel : {ada_no}/{parsel_no}" if (ada_no and parsel_no) else (
                f"  Ada No     : {ada_no}" if ada_no else (
                    f"  Parsel No  : {parsel_no}" if parsel_no else ""
                )
            ),
            f"  Alan       : {alan_m2:,.0f} m²",
            f"  Bina Yaşı  : {bina_yasi} yıl" if bina_yasi else "  Bina Yaşı  : Sıfır/Belirtilmemiş",
            f"  Kat        : {kat}" if kat else "",
            f"  Tapu       : {tapu_turu}" + tapu_uyari,
            f"  Özellikler : {ozellikler}" if ozellikler else "",
            f"  İmar       : {imar_durumu}" if imar_durumu else "",
            f"  Ticari Kat : {ticari_kat}" if ticari_kat else "",
            f"  Cephe      : {cephe_turu}" if cephe_turu else "",
            f"  Mevcut Kira: {mevcut_kira_aylik:,.0f} ₺/ay (gerçek)" if mevcut_kira_aylik > 0 else "",
            "",
            "── EMSAL KARŞILAŞTIRMA (Ağırlık %60) ──────────────────",
            f"  Bölge m² Aralığı  : {bolge_fmin:,.0f} — {bolge_fmax:,.0f} ₺/m²",
            f"  Düzeltme Katsayısı: ×{duzeltme:.2f}",
            f"  Düzeltilmiş m²    : {m2_fmin:,.0f} — {m2_fmax:,.0f} ₺/m²",
            "",
            "── DEĞERLEME SONUCU ────────────────────────────────────",
            f"  Minimum Değer : {deger_min:,.0f} ₺",
            f"  Orta Değer    : {deger_orta:,.0f} ₺",
            f"  Maximum Değer : {deger_max:,.0f} ₺",
        ]

        if ilan_fiyati > 0:
            rapor.extend([
                "",
                "── İLAN FİYATI KARŞILAŞTIRMASI ─────────────────────────",
                f"  İlan Fiyatı   : {ilan_fiyati:,.0f} ₺",
                ilan_yorum,
            ])

        rapor.extend([
            "",
            "── KİRA GETİRİSİ ANALİZİ ──────────────────────────────",
            f"  Tahmini Aylık Kira : {kira_aylik_min:,.0f} — {kira_aylik_max:,.0f} ₺",
            f"  Brüt Kira Getirisi : %{brut_getiri:.1f} yıllık",
            f"  Geri Ödeme Süresi  : {geri_odeme_yil:.0f} yıl",
            "",
            "── YATIRIM DEĞERLENDİRMESİ ─────────────────────────────",
            f"  Yatırım Puanı : {yatirim_puani}/10 — {yatirim_yorum}",
            "",
            "── SONUÇ ───────────────────────────────────────────────",
            f"  Gerçekçi Pazar Değeri: {deger_orta:,.0f} ₺",
            f"  (Min: {deger_min:,.0f} ₺ — Max: {deger_max:,.0f} ₺)",
            "",
            "  Uyarı: Bu değerleme piyasa gözlem ortalamalarına dayalıdır.",
            "  Veri tabanı: Ağustos 2025 — güncel fiyatlar farklılık gösterebilir." if tahmini_mod else "",
            "  Kesin değer için SPK lisanslı gayrimenkul değerleme uzmanına",
            "  danışmanız önerilir.",
            "=" * 60,
        ])

        return "\n".join([x for x in rapor if x != "" or True])

    def sorgu_gayrimenkul_thread_olustur(self) -> Optional["ClaudeAracliThread"]:
        """Gayrimenkul Değerleme Uzmanı thread — uzmanlaşmış sistem promptuyla."""
        if not self.api_key_gecerli():
            return None
        thread = ClaudeAracliThread(
            api_key=self.api_key,
            mesajlar=list(self.gecmis),
            model=self.model,
            arac_callback=self._arac_calistir,
            sistem_prompt=GAYRIMENKUL_SISTEM_PROMPT,
        )
        self._active_thread = thread
        return thread
