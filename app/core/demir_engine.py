"""
Demir Engine
DXF dosyalarından otomatik demir hesaplamalarını yapan motor
Temel, Kolon, Kiriş ve Döşeme demiri hesaplamaları
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
import re
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
    poz_no: str  # Poz numarası
    eleman_tipi: str  # "temel_kesit", "temel_ilave", "sehpa", "kolon_filizi", "kolon_etriye", "hatil"
    eleman_adi: str
    adet: int  # Demir adet sayısı
    demir_capi: int  # mm
    uzunluk: float  # cm (bir adet için)
    toplam_uzunluk: float  # cm (adet × uzunluk)
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
    
    def demir_ekle(self, poz_no: str, eleman_tipi: str, eleman_adi: str,
                   adet: int, demir_capi: int, uzunluk: float) -> DemirHesap:
        """
        Demir hesabı ekle ve kayıt tutar
        
        Args:
            poz_no: Poz numarası
            eleman_tipi: Eleman tipi
            eleman_adi: Eleman adı
            adet: Demir adet sayısı
            demir_capi: Demir çapı (mm)
            uzunluk: Bir adet demirin uzunluğu (cm)
        """
        if demir_capi not in self.DEMIR_ORANLAR:
            logger.warning(f"Bilinmeyen demir çapı: {demir_capi}mm, en yakın değer kullanılıyor")
            demir_capi = min(self.DEMIR_ORANLAR.keys(), key=lambda x: abs(x - demir_capi))
        
        toplam_uzunluk = adet * uzunluk
        birim_agirlik = self.DEMIR_ORANLAR[demir_capi]
        toplam_agirlik = (toplam_uzunluk / 100) * birim_agirlik  # cm'den m'ye çevir
        
        hesap = DemirHesap(
            poz_no=poz_no,
            eleman_tipi=eleman_tipi,
            eleman_adi=eleman_adi,
            adet=adet,
            demir_capi=demir_capi,
            uzunluk=uzunluk,
            toplam_uzunluk=toplam_uzunluk,
            birim_agirlik=birim_agirlik,
            toplam_agirlik=toplam_agirlik
        )
        
        self.hesaplamalar.append(hesap)
        logger.debug(f"Demir eklendi: {poz_no} - {adet}Ø{demir_capi} l={uzunluk}cm")
        
        return hesap
    
    def ozet_by_type(self) -> Dict[str, Dict[str, Any]]:
        """Eleman tipi bazında özet hesaplama yap"""
        ozet = {}
        
        tiplar = {}
        for h in self.hesaplamalar:
            if h.eleman_tipi not in tiplar:
                tiplar[h.eleman_tipi] = []
            tiplar[h.eleman_tipi].append(h)
        
        for tip, hesaplar in tiplar.items():
            toplam_agirlik = sum(h.toplam_agirlik for h in hesaplar)
            toplam_uzunluk = sum(h.toplam_uzunluk for h in hesaplar)
            
            ozet[tip] = {
                "toplam_agirlik_kg": round(toplam_agirlik, 2),
                "toplam_uzunluk_cm": round(toplam_uzunluk, 2),
                "toplam_uzunluk_m": round(toplam_uzunluk / 100, 2),
                "hesaplama_sayisi": len(hesaplar),
                "detaylar": [
                    {
                        "poz_no": h.poz_no,
                        "adi": h.eleman_adi,
                        "adet": h.adet,
                        "cap": h.demir_capi,
                        "uzunluk": round(h.uzunluk, 2),
                        "toplam_uzunluk": round(h.toplam_uzunluk, 2),
                        "agirlik": round(h.toplam_agirlik, 2)
                    }
                    for h in hesaplar
                ]
            }
        
        return ozet
    
    def ozet_genel(self) -> Dict[str, Any]:
        """Tüm demirler için genel özet"""
        toplam_agirlik = sum(h.toplam_agirlik for h in self.hesaplamalar)
        toplam_uzunluk = sum(h.toplam_uzunluk for h in self.hesaplamalar)
        
        return {
            "toplam_agirlik_kg": round(toplam_agirlik, 2),
            "toplam_uzunluk_cm": round(toplam_uzunluk, 2),
            "toplam_uzunluk_m": round(toplam_uzunluk / 100, 2),
            "hesaplama_sayisi": len(self.hesaplamalar)
        }
    
    @staticmethod
    def parse_demir_text(text: str) -> Optional[Tuple[int, int, float]]:
        """
        Demir textini parse et
        Format: 56Ø12 l=1200 veya 12@10 l=4000 vb.
        
        Returns: (adet, çap, uzunluk) veya None
        """
        # Çeşitli format desteği
        patterns = [
            r'(\d+)[Ø@](\d+).*?l=(\d+)',  # 56Ø12 l=1200 veya 56@12 l=1200
            r'(\d+)\s*[Ø@]\s*(\d+).*?l=(\d+)',  # Boşluk toleransı
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                adet = int(match.group(1))
                cap = int(match.group(2))
                uzunluk = float(match.group(3))
                return (adet, cap, uzunluk)
        
        return None
    
    @staticmethod
    def parse_table_donati(donati_text: str) -> Optional[Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]]:
        """
        Tablo format donatısını parse et
        Format: "12Ø10/20 | 21Ø12/20" (boyuna | enine)
        
        Returns: ((boyuna_list), (enine_list)) veya None
        """
        try:
            parts = donati_text.split('|')
            
            boyuna_list = []
            enine_list = []
            
            for part in parts:
                part = part.strip()
                # Pattern: 12Ø10/20
                match = re.search(r'(\d+)[Ø@](\d+)', part)
                if match:
                    adet = int(match.group(1))
                    cap = int(match.group(2))
                    
                    if parts.index(part) == 0:  # Boyuna
                        boyuna_list.append((adet, cap))
                    else:  # Enine
                        enine_list.append((adet, cap))
            
            return (boyuna_list, enine_list) if boyuna_list or enine_list else None
        
        except:
            return None


