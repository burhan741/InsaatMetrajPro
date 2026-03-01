"""
Hava Durumu Modülü
Open-Meteo API entegrasyonu ve inşaat hava kuralları motoru

Özellikler:
- Ücretsiz Open-Meteo API (API key gerektirmez)
- 7 günlük hava tahmini
- İnşaat koşullarına göre otomatik uyarı motoru (TS 500 referanslı)
- 30 dakikalık bellek cache
- Offline kullanım için graceful hata yönetimi

API Referans: https://open-meteo.com/en/docs
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# ─── WMO Hava Durum Kodları (kısaltılmış Türkçe açıklama) ───────────────────
WMO_ACIKLAMA: Dict[int, str] = {
    0: "Açık",
    1: "Çoğunlukla Açık", 2: "Parçalı Bulutlu", 3: "Kapalı",
    45: "Sisli", 48: "Kırağılı Sis",
    51: "Hafif Çiseleyen", 53: "Orta Çiseleyen", 55: "Yoğun Çiseleyen",
    61: "Hafif Yağmur", 63: "Orta Yağmur", 65: "Kuvvetli Yağmur",
    71: "Hafif Kar", 73: "Orta Kar", 75: "Yoğun Kar",
    77: "Kar Taneleri",
    80: "Hafif Sağanak", 81: "Orta Sağanak", 82: "Şiddetli Sağanak",
    85: "Hafif Kar Sağanağı", 86: "Yoğun Kar Sağanağı",
    95: "Gök Gürültülü Fırtına",
    96: "Dolu ile Fırtına", 99: "Şiddetli Dolu ile Fırtına",
}

# WMO kodlarına göre kar yağışı tespiti
KAR_KODLARI = {71, 73, 75, 77, 85, 86}


@dataclass
class HavaDurumu:
    """Tek günlük hava durumu verisi"""
    tarih: date
    max_sicaklik: float       # °C
    min_sicaklik: float       # °C
    yagis_mm: float           # mm (günlük toplam yağış)
    ruzgar_kmh: float         # km/h (10 m yükseklik max)
    kar_yagisi: bool          # Kar yağışı var mı?
    durum_kodu: int           # WMO weather code
    durum_aciklama: str = ""  # Türkçe açıklama

    def __post_init__(self):
        if not self.durum_aciklama:
            self.durum_aciklama = WMO_ACIKLAMA.get(self.durum_kodu, "Bilinmiyor")


@dataclass
class HavaUyari:
    """İnşaat hava uyarısı"""
    tarih: date
    seviye: str      # "KRİTİK" veya "UYARI"
    mesaj: str
    kategori: str    # "SICAKLIK", "YAĞIŞ", "RÜZGAR", "KAR"


# ─── İNŞAAT HAVA KURALLARI ──────────────────────────────────────────────────

def insaat_uyari_kontrol(hava: HavaDurumu) -> List[HavaUyari]:
    """
    Tek günlük hava durumuna göre inşaat uyarılarını hesapla.

    Kural kaynağı:
    - TS 500: Betonarme yapıların hesap ve yapım kuralları
    - İş Sağlığı ve Güvenliği Yönetmeliği

    Neyi çözüyoruz?
    - Müteahhitin hava koşullarından kaynaklı inşaat hatası riskini azaltmak.
    - Test: hava = HavaDurumu(date.today(), -5, -8, 0, 20, False, 3)
             uyarilar = insaat_uyari_kontrol(hava)  # KRİTİK: don riski
    """
    uyarilar: List[HavaUyari] = []

    # ── SICAKLIK KONTROLLERI ──────────────────────────────────────
    if hava.min_sicaklik < -3:
        uyarilar.append(HavaUyari(
            tarih=hava.tarih,
            seviye="KRİTİK",
            mesaj=f"Beton dökme YAPILMAZ — don riski (min: {hava.min_sicaklik:.1f}°C)",
            kategori="SICAKLIK"
        ))
    elif hava.min_sicaklik < 5:
        uyarilar.append(HavaUyari(
            tarih=hava.tarih,
            seviye="UYARI",
            mesaj=f"Soğuk hava — beton karma suyunu ısıt, antifriz kullan (min: {hava.min_sicaklik:.1f}°C)",
            kategori="SICAKLIK"
        ))

    if hava.max_sicaklik > 38:
        uyarilar.append(HavaUyari(
            tarih=hava.tarih,
            seviye="KRİTİK",
            mesaj=f"Aşırı sıcak — dış sıva ve beton dökümünü ERTELE (max: {hava.max_sicaklik:.1f}°C)",
            kategori="SICAKLIK"
        ))
    elif hava.max_sicaklik > 35:
        uyarilar.append(HavaUyari(
            tarih=hava.tarih,
            seviye="UYARI",
            mesaj=f"Sıcak hava — beton kürü kritik, sulama şart (max: {hava.max_sicaklik:.1f}°C)",
            kategori="SICAKLIK"
        ))

    # ── YAĞIŞ KONTROLLERI ────────────────────────────────────────
    if hava.yagis_mm > 20:
        uyarilar.append(HavaUyari(
            tarih=hava.tarih,
            seviye="KRİTİK",
            mesaj=f"Yoğun yağış — beton ve sıva işleri ERTELEME ({hava.yagis_mm:.1f} mm)",
            kategori="YAĞIŞ"
        ))
    elif hava.yagis_mm > 5:
        uyarilar.append(HavaUyari(
            tarih=hava.tarih,
            seviye="UYARI",
            mesaj=f"Yağış bekleniyor — beton/sıva planını gözden geçir ({hava.yagis_mm:.1f} mm)",
            kategori="YAĞIŞ"
        ))

    # ── RÜZGAR KONTROLLERI ───────────────────────────────────────
    if hava.ruzgar_kmh > 80:
        uyarilar.append(HavaUyari(
            tarih=hava.tarih,
            seviye="KRİTİK",
            mesaj=f"Fırtına — yüksekte çalışma DURDUR ({hava.ruzgar_kmh:.0f} km/s)",
            kategori="RÜZGAR"
        ))
    elif hava.ruzgar_kmh > 50:
        uyarilar.append(HavaUyari(
            tarih=hava.tarih,
            seviye="UYARI",
            mesaj=f"Kuvvetli rüzgar — iskele ve kalıp güvenliğini kontrol et ({hava.ruzgar_kmh:.0f} km/s)",
            kategori="RÜZGAR"
        ))

    # ── KAR YAĞIŞI ───────────────────────────────────────────────
    if hava.kar_yagisi:
        uyarilar.append(HavaUyari(
            tarih=hava.tarih,
            seviye="KRİTİK",
            mesaj="Kar yağışı — çatı ve yüksekte çalışma DURDUR, beton dökme YAPILMAZ",
            kategori="KAR"
        ))

    return uyarilar


# ─── HAVA DURUMU SERVİSİ ────────────────────────────────────────────────────

class HavaDurumuServisi:
    """
    Open-Meteo API üzerinden hava durumu sorgulama.

    Neyi çözüyoruz?
    - API key olmadan ücretsiz 7 günlük hava tahmini.
    - İnşaat planlamasına entegre uyarı sistemi.
    - Offline çalışma: hata durumunda None döner, uygulama kırılmaz.

    Test:
    - servis = HavaDurumuServisi()
    - konum = servis.sehir_ara("Ankara")
    - tahminler = servis.tahmin_al(konum['lat'], konum['lon'])
    - uyarilar = servis.insaat_uyarilari_al(tahminler)
    """

    FORECAST_URL = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude={lat}&longitude={lon}"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min"
        ",precipitation_sum,wind_speed_10m_max"
        "&timezone=Europe%2FIstanbul"
        "&forecast_days=7"
    )
    GEOCODING_URL = (
        "https://geocoding-api.open-meteo.com/v1/search"
        "?name={name}&count=5&language=tr&format=json"
    )

    def __init__(self):
        # 30 dakikalık bellek cache
        self._cache: Dict[str, Any] = {}          # key -> (veri, zaman)
        self._cache_sure_dk = 30

    def _cache_al(self, key: str) -> Optional[Any]:
        """Cache'den veri al, süresi geçmişse None döndür"""
        if key in self._cache:
            veri, zaman = self._cache[key]
            if datetime.now() - zaman < timedelta(minutes=self._cache_sure_dk):
                return veri
            del self._cache[key]
        return None

    def _cache_yaz(self, key: str, veri: Any) -> None:
        self._cache[key] = (veri, datetime.now())

    def sehir_ara(self, isim: str) -> Optional[Dict[str, Any]]:
        """
        Şehir adına göre koordinat ara.

        Returns:
            {'lat': float, 'lon': float, 'display_name': str} veya None
        """
        if not isim or len(isim.strip()) < 2:
            return None

        cache_key = f"geo_{isim.lower().strip()}"
        cached = self._cache_al(cache_key)
        if cached is not None:
            return cached

        try:
            import requests
            url = self.GEOCODING_URL.format(name=isim.strip())
            resp = requests.get(url, timeout=8)
            resp.raise_for_status()
            data = resp.json()

            sonuclar = data.get('results', [])
            if not sonuclar:
                logger.warning(f"Şehir bulunamadı: {isim}")
                return None

            ilk = sonuclar[0]
            konum = {
                'lat': ilk['latitude'],
                'lon': ilk['longitude'],
                'display_name': f"{ilk.get('name', isim)}, {ilk.get('country', '')}".strip(', '),
                'tum_sonuclar': [
                    {
                        'lat': r['latitude'],
                        'lon': r['longitude'],
                        'display_name': f"{r.get('name','')}, {r.get('admin1','')}, {r.get('country','')}"
                                        .replace(', ,', ',').strip(', ')
                    }
                    for r in sonuclar
                ]
            }
            self._cache_yaz(cache_key, konum)
            return konum

        except ImportError:
            logger.error("requests kütüphanesi yüklü değil")
            return None
        except Exception as e:
            logger.warning(f"Şehir arama hatası ({isim}): {e}")
            return None

    def tahmin_al(self, lat: float, lon: float) -> Optional[List[HavaDurumu]]:
        """
        Koordinata göre 7 günlük hava tahmini al.

        Returns:
            List[HavaDurumu] (7 eleman) veya None (hata durumunda)
        """
        cache_key = f"forecast_{lat:.3f}_{lon:.3f}"
        cached = self._cache_al(cache_key)
        if cached is not None:
            return cached

        try:
            import requests
            url = self.FORECAST_URL.format(lat=lat, lon=lon)
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            daily = data.get('daily', {})
            tarihler      = daily.get('time', [])
            max_sicaklik  = daily.get('temperature_2m_max', [])
            min_sicaklik  = daily.get('temperature_2m_min', [])
            yagis         = daily.get('precipitation_sum', [])
            ruzgar        = daily.get('wind_speed_10m_max', [])
            wmo_kod       = daily.get('weather_code', [])

            tahminler = []
            for i in range(len(tarihler)):
                try:
                    tarih_dt = date.fromisoformat(tarihler[i])
                except Exception:
                    continue

                kod = int(wmo_kod[i]) if i < len(wmo_kod) else 0
                hava = HavaDurumu(
                    tarih=tarih_dt,
                    max_sicaklik=float(max_sicaklik[i]) if i < len(max_sicaklik) else 0.0,
                    min_sicaklik=float(min_sicaklik[i]) if i < len(min_sicaklik) else 0.0,
                    yagis_mm=float(yagis[i]) if i < len(yagis) else 0.0,
                    ruzgar_kmh=float(ruzgar[i]) if i < len(ruzgar) else 0.0,
                    kar_yagisi=(kod in KAR_KODLARI),
                    durum_kodu=kod,
                )
                tahminler.append(hava)

            self._cache_yaz(cache_key, tahminler)
            logger.info(f"Hava durumu alındı: {lat:.3f},{lon:.3f} — {len(tahminler)} gün")
            return tahminler

        except ImportError:
            logger.error("requests kütüphanesi yüklü değil")
            return None
        except Exception as e:
            logger.warning(f"Hava durumu alınamadı ({lat},{lon}): {e}")
            return None

    def insaat_uyarilari_al(
        self,
        tahminler: Optional[List[HavaDurumu]]
    ) -> List[Dict[str, Any]]:
        """
        Tahmin listesinden inşaat uyarılarını hesapla.

        Returns:
            [{'tarih': str, 'seviye': str, 'mesaj': str, 'kategori': str}, ...]
        """
        if not tahminler:
            return []

        sonuclar = []
        for hava in tahminler:
            uyarilar = insaat_uyari_kontrol(hava)
            for u in uyarilar:
                sonuclar.append({
                    'tarih': u.tarih.strftime('%d.%m.%Y'),
                    'tarih_dt': u.tarih,
                    'seviye': u.seviye,
                    'mesaj': u.mesaj,
                    'kategori': u.kategori,
                })
        return sonuclar

    def bugun_ozet(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """
        Bugünkü hava durumu ve inşaat uyarılarını tek sözlükte döndür.
        """
        tahminler = self.tahmin_al(lat, lon)
        if not tahminler:
            return None

        bugun = date.today()
        hava_bugun = next((h for h in tahminler if h.tarih == bugun), tahminler[0])
        uyarilar = insaat_uyari_kontrol(hava_bugun)

        return {
            'hava': hava_bugun,
            'uyarilar': uyarilar,
            'kritik_sayisi': sum(1 for u in uyarilar if u.seviye == "KRİTİK"),
            'uyari_sayisi': sum(1 for u in uyarilar if u.seviye == "UYARI"),
        }

    def cache_temizle(self) -> None:
        """Tüm cache'i temizle (test için)"""
        self._cache.clear()
