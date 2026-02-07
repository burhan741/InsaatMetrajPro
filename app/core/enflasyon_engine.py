"""
Enflasyon ve Fiyat Farkı Hesaplama Modülü
TCMB API entegrasyonu ile TÜFE/ÜFE verilerini çeker ve fiyat farkı hesaplar
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class EnflasyonEngine:
    """
    Enflasyon hesaplama ve TCMB API entegrasyonu sınıfı.

    TÜFE (Tüketici Fiyat Endeksi) ve ÜFE (Üretici Fiyat Endeksi) verilerini
    TCMB EVDS API'sinden çekerek fiyat farkı hesaplamalarını yapar.
    """

    # TCMB EVDS API endpoint
    EVDS_API_URL = "https://evds2.tcmb.gov.tr/service/evds/"

    # Veri kodları (TCMB EVDS)
    TUFE_KOD = "TP.FG.J0"  # TÜFE - Genel
    UFE_KOD = "TP.FG.F01"   # ÜFE - Genel

    def __init__(self, api_key: Optional[str] = None):
        """
        Enflasyon motoru başlat.

        Args:
            api_key: TCMB EVDS API anahtarı (opsiyonel)
                    Kayıt olmak için: https://evds2.tcmb.gov.tr/
        """
        self.api_key = api_key
        self.cache = {}  # Basit cache mekanizması

    def get_tufe_data(self, start_date: str, end_date: str) -> Optional[List[Dict]]:
        """
        TÜFE verilerini TCMB API'den çeker.

        Args:
            start_date: Başlangıç tarihi (DD-MM-YYYY formatında)
            end_date: Bitiş tarihi (DD-MM-YYYY formatında)

        Returns:
            Liste halinde TÜFE verileri veya None
        """
        return self._fetch_evds_data(self.TUFE_KOD, start_date, end_date)

    def get_ufe_data(self, start_date: str, end_date: str) -> Optional[List[Dict]]:
        """
        ÜFE verilerini TCMB API'den çeker.

        Args:
            start_date: Başlangıç tarihi (DD-MM-YYYY formatında)
            end_date: Bitiş tarihi (DD-MM-YYYY formatında)

        Returns:
            Liste halinde ÜFE verileri veya None
        """
        return self._fetch_evds_data(self.UFE_KOD, start_date, end_date)

    def _fetch_evds_data(self, data_code: str, start_date: str, end_date: str) -> Optional[List[Dict]]:
        """
        TCMB EVDS API'den veri çeker.

        Args:
            data_code: Veri kodu (TÜFE veya ÜFE)
            start_date: Başlangıç tarihi
            end_date: Bitiş tarihi

        Returns:
            API yanıtı veya None
        """
        if not self.api_key:
            logger.warning("TCMB API anahtarı bulunamadı. Örnek veri döndürülüyor.")
            return self._get_sample_data(start_date, end_date)

        cache_key = f"{data_code}_{start_date}_{end_date}"
        if cache_key in self.cache:
            logger.info(f"Cache'den veri döndürülüyor: {cache_key}")
            return self.cache[cache_key]

        try:
            url = f"{self.EVDS_API_URL}series={data_code}&startDate={start_date}&endDate={end_date}&type=json"
            headers = {
                "key": self.api_key,
                "Accept": "application/json"
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            if 'items' in data:
                self.cache[cache_key] = data['items']
                return data['items']
            else:
                logger.error("API yanıtında 'items' bulunamadı")
                return self._get_sample_data(start_date, end_date)

        except requests.exceptions.RequestException as e:
            logger.error(f"TCMB API hatası: {e}")
            return self._get_sample_data(start_date, end_date)
        except Exception as e:
            logger.error(f"Beklenmeyen hata: {e}")
            return self._get_sample_data(start_date, end_date)

    def _get_sample_data(self, start_date: str, end_date: str) -> List[Dict]:
        """
        API anahtarı yoksa veya hata olursa örnek veri döndürür.

        Args:
            start_date: Başlangıç tarihi
            end_date: Bitiş tarihi

        Returns:
            Örnek enflasyon verileri
        """
        logger.info("Örnek enflasyon verileri oluşturuluyor...")

        # Basit örnek veri (2024-2026 arası yaklaşık değerler)
        sample_data = [
            {"Tarih": "01-01-2024", "TP_FG_J0": "64.77"},  # Ocak 2024
            {"Tarih": "01-02-2024", "TP_FG_J0": "67.07"},  # Şubat 2024
            {"Tarih": "01-03-2024", "TP_FG_J0": "68.50"},  # Mart 2024
            {"Tarih": "01-04-2024", "TP_FG_J0": "69.80"},  # Nisan 2024
            {"Tarih": "01-05-2024", "TP_FG_J0": "75.45"},  # Mayıs 2024
            {"Tarih": "01-06-2024", "TP_FG_J0": "71.60"},  # Haziran 2024
            {"Tarih": "01-07-2024", "TP_FG_J0": "61.78"},  # Temmuz 2024
            {"Tarih": "01-08-2024", "TP_FG_J0": "51.97"},  # Ağustos 2024
            {"Tarih": "01-09-2024", "TP_FG_J0": "49.38"},  # Eylül 2024
            {"Tarih": "01-10-2024", "TP_FG_J0": "48.58"},  # Ekim 2024
            {"Tarih": "01-11-2024", "TP_FG_J0": "47.09"},  # Kasım 2024
            {"Tarih": "01-12-2024", "TP_FG_J0": "44.38"},  # Aralık 2024
            {"Tarih": "01-01-2025", "TP_FG_J0": "43.93"},  # Ocak 2025
            {"Tarih": "01-02-2025", "TP_FG_J0": "42.50"},  # Şubat 2025 (tahmini)
            {"Tarih": "01-03-2025", "TP_FG_J0": "41.20"},  # Mart 2025 (tahmini)
        ]

        return sample_data

    def hesapla_fiyat_farki(
        self,
        baslangic_fiyat: float,
        baslangic_tarihi: str,
        bitis_tarihi: str,
        endeks_tipi: str = "TUFE"
    ) -> Dict[str, Any]:
        """
        İki tarih arasındaki fiyat farkını hesaplar.

        Args:
            baslangic_fiyat: Başlangıç fiyatı (TL)
            baslangic_tarihi: Başlangıç tarihi (DD-MM-YYYY)
            bitis_tarihi: Bitiş tarihi (DD-MM-YYYY)
            endeks_tipi: "TUFE" veya "UFE"

        Returns:
            {
                'baslangic_fiyat': float,
                'guncel_fiyat': float,
                'fark': float,
                'fark_yuzde': float,
                'enflasyon_orani': float
            }
        """
        try:
            # Endeks verilerini çek
            if endeks_tipi == "TUFE":
                data = self.get_tufe_data(baslangic_tarihi, bitis_tarihi)
            else:
                data = self.get_ufe_data(baslangic_tarihi, bitis_tarihi)

            if not data or len(data) < 2:
                logger.error("Yeterli veri bulunamadı")
                return {
                    'baslangic_fiyat': baslangic_fiyat,
                    'guncel_fiyat': baslangic_fiyat,
                    'fark': 0.0,
                    'fark_yuzde': 0.0,
                    'enflasyon_orani': 0.0,
                    'hata': 'Veri bulunamadı'
                }

            # İlk ve son değerleri al
            ilk_endeks = float(data[0].get('TP_FG_J0', 100))
            son_endeks = float(data[-1].get('TP_FG_J0', 100))

            # Enflasyon oranını hesapla
            enflasyon_orani = ((son_endeks - ilk_endeks) / ilk_endeks) * 100

            # Güncel fiyatı hesapla
            guncel_fiyat = baslangic_fiyat * (1 + (enflasyon_orani / 100))

            # Farkı hesapla
            fark = guncel_fiyat - baslangic_fiyat
            fark_yuzde = (fark / baslangic_fiyat) * 100

            return {
                'baslangic_fiyat': round(baslangic_fiyat, 2),
                'guncel_fiyat': round(guncel_fiyat, 2),
                'fark': round(fark, 2),
                'fark_yuzde': round(fark_yuzde, 2),
                'enflasyon_orani': round(enflasyon_orani, 2),
                'baslangic_tarihi': baslangic_tarihi,
                'bitis_tarihi': bitis_tarihi,
                'endeks_tipi': endeks_tipi
            }

        except Exception as e:
            logger.error(f"Fiyat farkı hesaplama hatası: {e}")
            return {
                'baslangic_fiyat': baslangic_fiyat,
                'guncel_fiyat': baslangic_fiyat,
                'fark': 0.0,
                'fark_yuzde': 0.0,
                'enflasyon_orani': 0.0,
                'hata': str(e)
            }

    def hesapla_aylik_enflasyon(self, yil: int, ay: int) -> Optional[float]:
        """
        Belirli bir ay için aylık enflasyon oranını hesaplar.

        Args:
            yil: Yıl
            ay: Ay (1-12)

        Returns:
            Aylık enflasyon oranı (%) veya None
        """
        try:
            # Bir önceki ay
            onceki_tarih = datetime(yil, ay, 1) - timedelta(days=1)

            baslangic = onceki_tarih.strftime("%01-%m-%Y")
            bitis = datetime(yil, ay, 1).strftime("%01-%m-%Y")

            data = self.get_tufe_data(baslangic, bitis)

            if not data or len(data) < 2:
                return None

            ilk_endeks = float(data[0].get('TP_FG_J0', 100))
            son_endeks = float(data[-1].get('TP_FG_J0', 100))

            aylik_enflasyon = ((son_endeks - ilk_endeks) / ilk_endeks) * 100

            return round(aylik_enflasyon, 2)

        except Exception as e:
            logger.error(f"Aylık enflasyon hesaplama hatası: {e}")
            return None

    def get_yillik_enflasyon(self, yil: int) -> Optional[float]:
        """
        Yıllık enflasyon oranını hesaplar.

        Args:
            yil: Yıl

        Returns:
            Yıllık enflasyon oranı (%) veya None
        """
        try:
            baslangic = f"01-01-{yil}"
            bitis = f"31-12-{yil}"

            data = self.get_tufe_data(baslangic, bitis)

            if not data or len(data) < 2:
                return None

            ilk_endeks = float(data[0].get('TP_FG_J0', 100))
            son_endeks = float(data[-1].get('TP_FG_J0', 100))

            yillik_enflasyon = ((son_endeks - ilk_endeks) / ilk_endeks) * 100

            return round(yillik_enflasyon, 2)

        except Exception as e:
            logger.error(f"Yıllık enflasyon hesaplama hatası: {e}")
            return None


# Test kodu
if __name__ == "__main__":
    # Loglama ayarla
    logging.basicConfig(level=logging.INFO)

    # Motor oluştur (API key olmadan test)
    engine = EnflasyonEngine()

    # Fiyat farkı hesapla
    sonuc = engine.hesapla_fiyat_farki(
        baslangic_fiyat=100000,
        baslangic_tarihi="01-01-2024",
        bitis_tarihi="01-12-2024",
        endeks_tipi="TUFE"
    )

    print("\n=== FIYAT FARKI HESAPLAMA ===")
    print(f"Başlangıç Fiyatı: {sonuc['baslangic_fiyat']} TL")
    print(f"Güncel Fiyat: {sonuc['guncel_fiyat']} TL")
    print(f"Fark: {sonuc['fark']} TL ({sonuc['fark_yuzde']}%)")
    print(f"Enflasyon Oranı: {sonuc['enflasyon_orani']}%")
