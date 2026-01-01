"""
Demir Engine
DXF dosyalarından otomatik demir hesaplamalarını yapan motor
Temel, Kolon, Kiriş ve Döşeme demiri hesaplamaları
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TemelTipi(Enum):
    """Temel tiplerileri"""
    RADYE = "radye"
    KIRIŞ_LI_RADYE = "kirişli_radye"
    MUTEMADI_TEMEL = "mutemadi_temel"
    KIRIŞ_LI_TEMEL = "kirişli_temel"


@dataclass
class DemirHesap:
    """Demir hesaplama sonuçları"""
    eleman_tipi: str  # "temel", "kolon", "kiriş", "döşeme"
    eleman_adi: str
    uzunluk: float  # cm
    eni: float  # cm
    yükseklik: float  # cm
    demir_capi: int  # mm
    demir_sayisi: int
    toplam_uzunluk: float  # cm
    birim_agirlik: float  # kg/m
    toplam_agirlik: float  # kg


class DemirEngine:
    """Yapı elemanlarından demir hesaplamalarını yapan motor"""
    
    # Demir birim ağırlıkları (kg/m)
    DEMIR_ORANLAR = {
        6: 0.222,
        8: 0.395,
        10: 0.617,
        12: 0.888,
        14: 1.208,
        16: 1.578,
        18: 2.000,
        20: 2.466,
        22: 2.984,
        25: 3.853,
        28: 4.834,
        32: 6.313,
    }
    
    def __init__(self):
        """Demir Engine'i başlat"""
        self.hesaplamalar: List[DemirHesap] = []
    
    def temel_demiri_hesapla(self, temel_tipi: TemelTipi, 
                            uzunluk: float, eni: float, yukseklik: float,
                            demir_capi: int = 12, aralık: float = 15.0) -> DemirHesap:
        """
        Temel demirini hesapla
        
        Args:
            temel_tipi: Temel türü
            uzunluk: Temel uzunluğu (cm)
            eni: Temel eni (cm)
            yukseklik: Temel yüksekliği (cm)
            demir_capi: Demir çapı (mm) - varsayılan 12
            aralık: Demir aralığı (cm) - varsayılan 15
        """
        if demir_capi not in self.DEMIR_ORANLAR:
            raise ValueError(f"Geçersiz demir çapı: {demir_capi}mm")
        
        # Temel türüne göre demir sayısını hesapla
        if temel_tipi == TemelTipi.RADYE:
            # Radye: uzunluk ve enine demir ağları
            demir_sayisi_u = int(uzunluk / aralık) + 1
            demir_sayisi_e = int(eni / aralık) + 1
            demir_sayisi = (demir_sayisi_u * 2) + (demir_sayisi_e * 2)
            
        elif temel_tipi == TemelTipi.KIRIŞ_LI_RADYE:
            # Kirişli Radye: radye demiri + kiriş demiri
            demir_sayisi_u = int(uzunluk / aralık) + 1
            demir_sayisi_e = int(eni / aralık) + 1
            kiriş_demiri = int(uzunluk / 100) + 1  # Her metrede bir kiriş
            demir_sayisi = (demir_sayisi_u * 2) + (demir_sayisi_e * 2) + (kiriş_demiri * 4)
            
        elif temel_tipi == TemelTipi.MUTEMADI_TEMEL:
            # Mütemadi Temel: şerit halinde
            demir_sayisi = int(uzunluk / aralık) + 1
            demir_sayisi *= 4  # 4 layer
            
        elif temel_tipi == TemelTipi.KIRIŞ_LI_TEMEL:
            # Kirişli Temel: mütemadi + kiriş
            demir_sayisi = int(uzunluk / aralık) + 1
            demir_sayisi *= 6  # 6 layer
        else:
            demir_sayisi = 0
        
        # Toplam demir uzunluğunu hesapla
        ort_uzunluk = (uzunluk + eni) / 2
        toplam_uzunluk = demir_sayisi * ort_uzunluk
        
        # Ağırlığı hesapla
        birim_agirlik = self.DEMIR_ORANLAR[demir_capi]
        toplam_agirlik = (toplam_uzunluk / 100) * birim_agirlik  # cm'den m'ye çevir
        
        return DemirHesap(
            eleman_tipi="temel",
            eleman_adi=temel_tipi.value,
            uzunluk=uzunluk,
            eni=eni,
            yükseklik=yukseklik,
            demir_capi=demir_capi,
            demir_sayisi=demir_sayisi,
            toplam_uzunluk=toplam_uzunluk,
            birim_agirlik=birim_agirlik,
            toplam_agirlik=toplam_agirlik
        )
    
    def kolon_demiri_hesapla(self, uzunluk: float, eni: float, demir_capi: int = 12,
                            asama_capi: int = 8, asama_araligi: float = 15.0) -> DemirHesap:
        """
        Kolon demirini hesapla
        
        Args:
            uzunluk: Kolon uzunluğu (cm)
            eni: Kolon eni (cm)
            demir_capi: Boyuna demir çapı (mm)
            asama_capi: Asama demiri çapı (mm)
            asama_araligi: Asama aralığı (cm)
        """
        # Boyuna demir (4 veya 6 adım)
        if eni < 30:
            boyuna_demir_sayisi = 4
        else:
            boyuna_demir_sayisi = 6
        
        # Asama demiri sayısı
        asama_sayisi = int(uzunluk / asama_araligi) + 1
        asama_cevre = (eni * 2 + 20) * 2  # cm cinsinden çevre + kaynama
        
        # Toplam hesaplama
        toplam_uzunluk = (boyuna_demir_sayisi * uzunluk) + (asama_sayisi * asama_cevre)
        
        # Ağırlık hesaplama (ortalama çap)
        ort_capi = (demir_capi + asama_capi) / 2
        ort_capi_degeri = min(self.DEMIR_ORANLAR.keys(), 
                              key=lambda x: abs(x - ort_capi))
        birim_agirlik = self.DEMIR_ORANLAR[ort_capi_degeri]
        toplam_agirlik = (toplam_uzunluk / 100) * birim_agirlik
        
        return DemirHesap(
            eleman_tipi="kolon",
            eleman_adi="kolon",
            uzunluk=uzunluk,
            eni=eni,
            yükseklik=0,
            demir_capi=demir_capi,
            demir_sayisi=boyuna_demir_sayisi + asama_sayisi,
            toplam_uzunluk=toplam_uzunluk,
            birim_agirlik=birim_agirlik,
            toplam_agirlik=toplam_agirlik
        )
    
    def kiris_demiri_hesapla(self, uzunluk: float, yukseklik: float, 
                             demir_capi: int = 14, asama_capi: int = 8,
                             asama_araligi: float = 20.0) -> DemirHesap:
        """
        Kiriş demirini hesapla
        
        Args:
            uzunluk: Kiriş uzunluğu (cm)
            yukseklik: Kiriş yüksekliği (cm)
            demir_capi: Boyuna demir çapı (mm)
            asama_capi: Asama demiri çapı (mm)
            asama_araligi: Asama aralığı (cm)
        """
        # Boyuna demir (üst: 2, alt: 2)
        boyuna_demir_sayisi = 4
        
        # Asama demiri
        asama_sayisi = int(uzunluk / asama_araligi) + 1
        asama_cevre = (yukseklik * 2 + 10) * 2  # çevre + kaynama
        
        # Toplam uzunluk
        toplam_uzunluk = (boyuna_demir_sayisi * uzunluk) + (asama_sayisi * asama_cevre)
        
        # Ağırlık
        ort_capi = (demir_capi + asama_capi) / 2
        ort_capi_degeri = min(self.DEMIR_ORANLAR.keys(), 
                              key=lambda x: abs(x - ort_capi))
        birim_agirlik = self.DEMIR_ORANLAR[ort_capi_degeri]
        toplam_agirlik = (toplam_uzunluk / 100) * birim_agirlik
        
        return DemirHesap(
            eleman_tipi="kiriş",
            eleman_adi="kiriş",
            uzunluk=uzunluk,
            eni=yukseklik,
            yükseklik=yukseklik,
            demir_capi=demir_capi,
            demir_sayisi=boyuna_demir_sayisi + asama_sayisi,
            toplam_uzunluk=toplam_uzunluk,
            birim_agirlik=birim_agirlik,
            toplam_agirlik=toplam_agirlik
        )
    
    def doseme_demiri_hesapla(self, alan: float, demir_capi: int = 10,
                              aralık: float = 15.0) -> DemirHesap:
        """
        Döşeme demirini hesapla
        
        Args:
            alan: Döşeme alanı (m²)
            demir_capi: Demir çapı (mm)
            aralık: Demir aralığı (cm)
        """
        # Döşeme demiri (her iki yönde)
        alan_cm = alan * 10000  # m² to cm²
        eni_cm = int((alan_cm) ** 0.5)  # Kare olduğu varsayılarak
        
        demir_sayisi = int(eni_cm / aralık) + 1
        toplam_uzunluk = demir_sayisi * eni_cm * 2  # Her iki yön
        
        birim_agirlik = self.DEMIR_ORANLAR[demir_capi]
        toplam_agirlik = (toplam_uzunluk / 100) * birim_agirlik
        
        return DemirHesap(
            eleman_tipi="döşeme",
            eleman_adi="döşeme",
            uzunluk=float(eni_cm),
            eni=float(eni_cm),
            yükseklik=0,
            demir_capi=demir_capi,
            demir_sayisi=demir_sayisi * 2,
            toplam_uzunluk=toplam_uzunluk,
            birim_agirlik=birim_agirlik,
            toplam_agirlik=toplam_agirlik
        )
    
    def ozet_hesapla(self) -> Dict[str, Any]:
        """Tüm hesaplamaların özetini yap"""
        toplam_agirlik = sum(h.toplam_agirlik for h in self.hesaplamalar)
        toplam_uzunluk = sum(h.toplam_uzunluk for h in self.hesaplamalar)
        
        return {
            "toplam_agirlik_kg": round(toplam_agirlik, 2),
            "toplam_uzunluk_cm": round(toplam_uzunluk, 2),
            "hesaplama_sayisi": len(self.hesaplamalar),
            "detaylar": [
                {
                    "tipi": h.eleman_tipi,
                    "adi": h.eleman_adi,
                    "agirlik": round(h.toplam_agirlik, 2),
                    "uzunluk": round(h.toplam_uzunluk, 2)
                }
                for h in self.hesaplamalar
            ]
        }


