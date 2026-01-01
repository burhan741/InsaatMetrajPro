"""
DXF Demir Analiz Modülü
DXF dosyasındaki yapı elemanlarını otomatik tanıyıp demir hesaplamalarını yapan modül
"""

from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import logging
import re

from app.core.dxf_engine import DXFAnaliz
from app.core.demir_engine import DemirEngine, TemelTipi

logger = logging.getLogger(__name__)


class DXFDemirAnalyzer:
    """DXF dosyasından yapı elemanlarını tanıyıp demir hesaplamalarını yapan sınıf"""
    
    def __init__(self, dxf_dosya_yolu: str):
        """
        Analizcyi başlat
        
        Args:
            dxf_dosya_yolu: DXF dosyasının tam yolu
        """
        self.dxf_yolu = dxf_dosya_yolu
        self.dxf_analiz = None
        self.demir_engine = DemirEngine()
        self.yapilar = {
            "temellar": [],
            "kolonlar": [],
            "kirisler": [],
            "dosemeler": []
        }
        
        self.yukle()
    
    def yukle(self):
        """DXF dosyasını analiz için yükle"""
        try:
            self.dxf_analiz = DXFAnaliz(self.dxf_yolu, cizim_birimi="cm")
            logger.info(f"DXF dosyası yüklendi: {self.dxf_yolu}")
        except Exception as e:
            logger.error(f"DXF yükleme hatası: {e}")
            raise
    
    def katman_adlarini_getir(self) -> List[str]:
        """DXF dosyasındaki tüm katmanları getir"""
        if self.dxf_analiz and self.dxf_analiz.doc:
            katmanlar = [l.dxf.name for l in self.dxf_analiz.doc.layers]
            return katmanlar
        return []
    
    def temel_ozelliklerini_tanı(self) -> Dict[str, Any]:
        """
        DXF'deki temel özelliklerini tanı
        
        Katman adlarından veya blok isminden temel türünü belirler
        """
        temel_tipi = None
        katmanlar = self.katman_adlarini_getir()
        
        # Katman adlarında ara
        katman_text = " ".join(katmanlar).lower()
        
        if "radye" in katman_text and "kiriş" in katman_text:
            temel_tipi = TemelTipi.KIRIŞ_LI_RADYE
        elif "radye" in katman_text:
            temel_tipi = TemelTipi.RADYE
        elif "mütemadi" in katman_text and "kiriş" in katman_text:
            temel_tipi = TemelTipi.KIRIŞ_LI_TEMEL
        elif "mütemadi" in katman_text:
            temel_tipi = TemelTipi.MUTEMADI_TEMEL
        
        return {
            "temel_tipi": temel_tipi,
            "katmanlar": katmanlar
        }
    
    def ölçüleri_ekstrak_et(self) -> Dict[str, Any]:
        """
        DXF'den ölçüleri çıkar
        Blok ve entity boyutlarından yapı elemanı ölçülerini belirler
        """
        ölçüler = {
            "uzunluk": 0,
            "eni": 0,
            "yükseklik": 0,
            "alan": 0
        }
        
        try:
            if self.dxf_analiz and self.dxf_analiz.msp:
                # Bounding box'ı kullan
                bounding_box = None
                for entity in self.dxf_analiz.msp:
                    if hasattr(entity, 'dxf'):
                        try:
                            bbox = entity.bbox()
                            if bbox.has_data:
                                bounding_box = bbox
                                break
                        except:
                            pass
                
                if bounding_box:
                    extmin = bounding_box.extmin
                    extmax = bounding_box.extmax
                    
                    ölçüler['uzunluk'] = abs(extmax.x - extmin.x)
                    ölçüler['eni'] = abs(extmax.y - extmin.y)
                    ölçüler['yükseklik'] = abs(extmax.z - extmin.z) if extmax.z else 50  # Default 50cm
                    ölçüler['alan'] = (ölçüler['uzunluk'] * ölçüler['eni']) / 10000  # m²'ye çevir
        
        except Exception as e:
            logger.warning(f"Ölçü çıkarma hatası: {e}")
        
        return ölçüler
    
    def demiri_hesapla(self) -> Dict[str, Any]:
        """
        DXF'den elde edilen verilerle demir hesaplamalarını yap
        """
        sonuc = {}
        
        try:
            # Temel özelliklerini tanı
            temel_info = self.temel_ozelliklerini_tanı()
            ölçüler = self.ölçüleri_ekstrak_et()
            
            # Temel demiri hesapla
            if temel_info['temel_tipi']:
                temel_hesap = self.demir_engine.temel_demiri_hesapla(
                    temel_tipi=temel_info['temel_tipi'],
                    uzunluk=ölçüler['uzunluk'],
                    eni=ölçüler['eni'],
                    yukseklik=ölçüler['yükseklik'] if ölçüler['yükseklik'] else 50,
                    demir_capi=12,
                    aralık=15.0
                )
                self.demir_engine.hesaplamalar.append(temel_hesap)
                sonuc['temel'] = self._hesap_to_dict(temel_hesap)
            
            # Kolon demiri (örnek)
            if ölçüler['uzunluk'] > 0:
                kolon_hesap = self.demir_engine.kolon_demiri_hesapla(
                    uzunluk=300,  # 3m kolon
                    eni=30,
                    demir_capi=12
                )
                self.demir_engine.hesaplamalar.append(kolon_hesap)
                sonuc['kolon'] = self._hesap_to_dict(kolon_hesap)
            
            # Kiriş demiri (örnek)
            kiris_hesap = self.demir_engine.kiris_demiri_hesapla(
                uzunluk=500,  # 5m kiriş
                yukseklik=60,
                demir_capi=14
            )
            self.demir_engine.hesaplamalar.append(kiris_hesap)
            sonuc['kiris'] = self._hesap_to_dict(kiris_hesap)
            
            # Döşeme demiri (örnek)
            doseme_hesap = self.demir_engine.doseme_demiri_hesapla(
                alan=100,  # 100 m²
                demir_capi=10
            )
            self.demir_engine.hesaplamalar.append(doseme_hesap)
            sonuc['doseme'] = self._hesap_to_dict(doseme_hesap)
            
            # Özet
            sonuc['ozet'] = self.demir_engine.ozet_hesapla()
            
        except Exception as e:
            logger.error(f"Demir hesaplama hatası: {e}")
            raise
        
        return sonuc
    
    def _hesap_to_dict(self, hesap) -> Dict[str, Any]:
        """DemirHesap nesnesini dictionary'e çevir"""
        return {
            'eleman_tipi': hesap.eleman_tipi,
            'eleman_adi': hesap.eleman_adi,
            'uzunluk': round(hesap.uzunluk, 2),
            'eni': round(hesap.eni, 2),
            'yukseklik': round(hesap.yükseklik, 2),
            'demir_capi': hesap.demir_capi,
            'demir_sayisi': hesap.demir_sayisi,
            'toplam_uzunluk': round(hesap.toplam_uzunluk, 2),
            'birim_agirlik': hesap.birim_agirlik,
            'toplam_agirlik': round(hesap.toplam_agirlik, 2)
        }
    
    def rapor_olustur(self) -> str:
        """Demir hesaplamalarından rapor oluştur"""
        hesaplama_sonucu = self.demiri_hesapla()
        
        rapor = "=" * 60 + "\n"
        rapor += "YAPISAL DEMİR HESAPLAMA RAPORU\n"
        rapor += "=" * 60 + "\n\n"
        
        for eleman_tipi, veri in hesaplama_sonucu.items():
            if eleman_tipi == 'ozet':
                rapor += "\nÖZET\n"
                rapor += "-" * 60 + "\n"
                rapor += f"Toplam Demir Ağırlığı: {veri['toplam_agirlik_kg']} kg\n"
                rapor += f"Toplam Demir Uzunluğu: {veri['toplam_uzunluk_cm']} cm\n"
                rapor += f"Hesaplama Sayısı: {veri['hesaplama_sayisi']}\n"
            else:
                rapor += f"\n{veri['eleman_adi'].upper()}\n"
                rapor += "-" * 60 + "\n"
                rapor += f"Tip: {veri['eleman_tipi']}\n"
                rapor += f"Ölçüler: {veri['uzunluk']}cm × {veri['eni']}cm × {veri['yukseklik']}cm\n"
                rapor += f"Demir: Ø{veri['demir_capi']}mm × {veri['demir_sayisi']} adet\n"
                rapor += f"Toplam Ağırlık: {veri['toplam_agirlik']} kg\n"
        
        rapor += "\n" + "=" * 60 + "\n"
        
        return rapor
