"""
Temel Demir Analiz Modülü
DXF dosyasından temel demir metrajlarını otomatik çıkaran modül
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
import re

from app.core.dxf_engine import DXFAnaliz
from app.core.demir_engine import DemirEngine

logger = logging.getLogger(__name__)


class TemelDemirAnalyzer:
    """DXF'nin temel paftasından demir hesaplamalarını yapan sınıf"""
    
    def __init__(self, dxf_dosya_yolu: str):
        """
        Analizcyi başlat
        
        Args:
            dxf_dosya_yolu: DXF dosyasının tam yolu
        """
        self.dxf_yolu = dxf_dosya_yolu
        self.dxf_analiz = None
        self.demir_engine = DemirEngine()
        self.temel_tipi = None
        
        self.yukle()
    
    def yukle(self):
        """DXF dosyasını analiz için yükle"""
        try:
            self.dxf_analiz = DXFAnaliz(self.dxf_yolu, cizim_birimi="cm")
            logger.info(f"DXF dosyası yüklendi: {self.dxf_yolu}")
        except Exception as e:
            logger.error(f"DXF yükleme hatası: {e}")
            raise
    
    def tum_textleri_getir(self) -> Dict[str, List[str]]:
        """DXF'deki tüm text nesnelerini katman bazında topla"""
        textler = {}
        
        try:
            if self.dxf_analiz and self.dxf_analiz.msp:
                for entity in self.dxf_analiz.msp:
                    if entity.dxf.entity_type == 'TEXT':
                        text_degeri = entity.dxf.text
                        katman = entity.dxf.layer
                        
                        if katman not in textler:
                            textler[katman] = []
                        textler[katman].append(text_degeri)
        
        except Exception as e:
            logger.warning(f"Text çıkarma hatası: {e}")
        
        return textler
    
    def temel_tipi_belirle(self) -> Optional[str]:
        """DXF'den temel türünü belirle"""
        textler = self.tum_textleri_getir()
        
        # Tüm textleri birleştir
        tum_text = " ".join([t for metinler in textler.values() for t in metinler]).lower()
        
        if "radye" in tum_text and "kiriş" in tum_text:
            self.temel_tipi = "kirişli_radye"
        elif "radye" in tum_text:
            self.temel_tipi = "radye"
        elif "mütemadi" in tum_text and "kiriş" in tum_text:
            self.temel_tipi = "kirişli_temel"
        elif "mütemadi" in tum_text:
            self.temel_tipi = "mutemadi_temel"
        
        logger.info(f"Temel tipi belirlendi: {self.temel_tipi}")
        return self.temel_tipi
    
    def temel_kesit_demirlerini_cikart(self) -> Dict[str, Tuple[int, int, float]]:
        """
        DXF kesit gösterimlerinden temel demirlerini çıkar
        Format: "56Ø12/20 l=1200" → (56, 12, 1200)
        """
        kesit_demirler = {}
        textler = self.tum_textleri_getir()
        
        # Kesitleri ara (A-A KESİTİ, B-B KESİTİ, vb.)
        kesit_pattern = r'([A-Z])-([A-Z])\s*KESİTİ'
        
        for katman, metinler in textler.items():
            for metin in metinler:
                # Kesit başlığını ara
                kesit_match = re.search(kesit_pattern, metin.upper())
                if kesit_match:
                    kesit_adi = f"{kesit_match.group(1)}-{kesit_match.group(2)}"
                    
                    # Bu kesitle ilişkili demir textlerini ara
                    # (Basit olarak aynı katmandaki numerik textleri kontrol et)
                    for metin_check in metinler:
                        demir_info = DemirEngine.parse_demir_text(metin_check)
                        if demir_info:
                            adet, cap, uzunluk = demir_info
                            if kesit_adi not in kesit_demirler:
                                kesit_demirler[kesit_adi] = []
                            kesit_demirler[kesit_adi].append((adet, cap, uzunluk))
        
        return kesit_demirler
    
    def temel_ilave_demirlerini_cikart(self) -> List[Tuple[str, int, int, float]]:
        """
        DXF'den temel ilave demirlerini çıkar
        İlave demirler: temel alanı içinde ek olarak yerleştirilen demirler
        """
        ilave_demirler = []
        textler = self.tum_textleri_getir()
        
        # POZ numaraları ve demir bilgileri
        for katman, metinler in textler.items():
            for metin in metinler:
                # POZ patternu: "POZ 7", "PZ7", vb.
                poz_match = re.search(r'P[OZ]+\s*(\d+)', metin)
                if poz_match:
                    poz_no = poz_match.group(1)
                    
                    # Demir bilgisini ara
                    demir_info = DemirEngine.parse_demir_text(metin)
                    if demir_info:
                        adet, cap, uzunluk = demir_info
                        ilave_demirler.append((f"POZ{poz_no}", adet, cap, uzunluk))
        
        return ilave_demirler
    
    def kolon_filizi_tablosunu_oku(self) -> Dict[str, Tuple[int, int, float]]:
        """
        KOLON FİLİZİ tablosunu oku
        Format:
        S001 | P36-12Ø16 | 275
        """
        filizler = {}
        textler = self.tum_textleri_getir()
        
        tum_text = " ".join([t for metinler in textler.values() for t in metinler])
        
        # Kolon filizi tablosu kontrolü
        if "kolon" in tum_text.lower() and "filiz" in tum_text.lower():
            # Basit pattern: "S001 ... P36-12Ø16 ... 275"
            # Tüm kolon numerik pattern'lerini ara
            kolon_pattern = r'(S\d+)\s*\|?\s*P\d+[-]?(\d+)[Ø@](\d+)\s*\|?\s*(\d+)'
            
            matches = re.finditer(kolon_pattern, tum_text)
            for match in matches:
                kolon_adi = match.group(1)
                adet = int(match.group(2))
                cap = int(match.group(3))
                uzunluk = float(match.group(4))
                
                if kolon_adi not in filizler:
                    filizler[kolon_adi] = (adet, cap, uzunluk)
        
        return filizler
    
    def kolon_etriye_tablosunu_oku(self) -> Dict[str, List[Tuple[str, int, int, float]]]:
        """
        KOLON ETRİYE DONATI tablosunu oku
        Format:
        S001 | 32 | 5Ø8/3 | l=196
        """
        etriyeler = {}
        textler = self.tum_textleri_getir()
        
        tum_text = " ".join([t for metinler in textler.values() for t in metinler])
        
        # Etriye tablosu kontrolü
        if "etriye" in tum_text.lower() and "donati" in tum_text.lower():
            # Pattern: "S001 ... 32 ... 5Ø8 ... 196"
            etriye_pattern = r'(S\d+)\s*\|?\s*(\d+)\s*\|?\s*(\d+)[Ø@](\d+).*?l=(\d+)'
            
            matches = re.finditer(etriye_pattern, tum_text)
            for match in matches:
                kolon_adi = match.group(1)
                poz_no = match.group(2)
                adet = int(match.group(3))
                cap = int(match.group(4))
                uzunluk = float(match.group(5))
                
                if kolon_adi not in etriyeler:
                    etriyeler[kolon_adi] = []
                etriyeler[kolon_adi].append((f"POZ{poz_no}", adet, cap, uzunluk))
        
        return etriyeler
    
    def hatil_donati_tablosunu_oku(self) -> Dict[str, List[Tuple[str, int, int, float]]]:
        """
        HATIL DONATI tablosunu oku (opsiyonel)
        Format:
        BK1 | 20 | 12Ø10/20 | l=4000 | 21Ø12/20 | l=330
        """
        hatillar = {}
        textler = self.tum_textleri_getir()
        
        tum_text = " ".join([t for metinler in textler.values() for t in metinler])
        
        # Hatıl tablosu kontrolü
        if "hatil" in tum_text.lower() and "donati" in tum_text.lower():
            # Pattern: "BK1 ... 20 ... 12Ø10 ... l=4000"
            hatil_pattern = r'(BK\d+)\s*\|?\s*(\d+)\s*\|?\s*(\d+)[Ø@](\d+).*?l=(\d+)'
            
            matches = re.finditer(hatil_pattern, tum_text)
            for match in matches:
                hatil_adi = match.group(1)
                poz_no = match.group(2)
                adet = int(match.group(3))
                cap = int(match.group(4))
                uzunluk = float(match.group(5))
                
                if hatil_adi not in hatillar:
                    hatillar[hatil_adi] = []
                hatillar[hatil_adi].append((f"POZ{poz_no}", adet, cap, uzunluk))
        
        return hatillar
    
    def demiri_hesapla(self) -> Dict[str, Any]:
        """
        DXF'den elde edilen verilerle temel demir hesaplamalarını yap
        """
        sonuc = {}
        
        try:
            # Temel tipi belirle
            self.temel_tipi_belirle()
            
            # 1. Kesit demirlerini çıkar ve hesapla
            kesit_demirler = self.temel_kesit_demirlerini_cikart()
            for kesit_adi, demirler in kesit_demirler.items():
                for adet, cap, uzunluk in demirler:
                    self.demir_engine.demir_ekle(
                        poz_no=f"KESİT-{kesit_adi}",
                        eleman_tipi="temel_kesit",
                        eleman_adi=kesit_adi,
                        adet=adet,
                        demir_capi=cap,
                        uzunluk=uzunluk
                    )
            
            # 2. İlave demirlerini çıkar ve hesapla
            ilave_demirler = self.temel_ilave_demirlerini_cikart()
            for poz_no, adet, cap, uzunluk in ilave_demirler:
                # POZ 7, 8, 9... gibi numaraları belirle
                if poz_no.startswith("POZ9"):
                    eleman_tipi = "temel_sehpa"
                    adi = "Sehpa"
                else:
                    eleman_tipi = "temel_ilave"
                    adi = "İlave"
                
                self.demir_engine.demir_ekle(
                    poz_no=poz_no,
                    eleman_tipi=eleman_tipi,
                    eleman_adi=adi,
                    adet=adet,
                    demir_capi=cap,
                    uzunluk=uzunluk
                )
            
            # 3. Kolon filizlerini çıkar
            filizler = self.kolon_filizi_tablosunu_oku()
            for kolon_adi, (adet, cap, uzunluk) in filizler.items():
                self.demir_engine.demir_ekle(
                    poz_no=f"FILIZ-{kolon_adi}",
                    eleman_tipi="kolon_filizi",
                    eleman_adi=kolon_adi,
                    adet=adet,
                    demir_capi=cap,
                    uzunluk=uzunluk
                )
            
            # 4. Kolon etriyelerini çıkar
            etriyeler = self.kolon_etriye_tablosunu_oku()
            for kolon_adi, etriye_listesi in etriyeler.items():
                for poz_no, adet, cap, uzunluk in etriye_listesi:
                    self.demir_engine.demir_ekle(
                        poz_no=poz_no,
                        eleman_tipi="kolon_etriye",
                        eleman_adi=kolon_adi,
                        adet=adet,
                        demir_capi=cap,
                        uzunluk=uzunluk
                    )
            
            # 5. Hatıl donatısını çıkar (varsa)
            hatillar = self.hatil_donati_tablosunu_oku()
            for hatil_adi, hatil_listesi in hatillar.items():
                for poz_no, adet, cap, uzunluk in hatil_listesi:
                    self.demir_engine.demir_ekle(
                        poz_no=poz_no,
                        eleman_tipi="hatil",
                        eleman_adi=hatil_adi,
                        adet=adet,
                        demir_capi=cap,
                        uzunluk=uzunluk
                    )
            
            # Özetleri hazırla
            sonuc['tip_ozet'] = self.demir_engine.ozet_by_type()
            sonuc['genel_ozet'] = self.demir_engine.ozet_genel()
            sonuc['temel_tipi'] = self.temel_tipi
            
        except Exception as e:
            logger.error(f"Demir hesaplama hatası: {e}")
            raise
        
        return sonuc
    
    def rapor_olustur(self) -> str:
        """Demir hesaplamalarından rapor oluştur"""
        hesaplama_sonucu = self.demiri_hesapla()
        
        rapor = "=" * 80 + "\n"
        rapor += "TEMEL YAPISAL DEMİR HESAPLAMA RAPORU\n"
        rapor += "=" * 80 + "\n\n"
        
        if hesaplama_sonucu['temel_tipi']:
            rapor += f"Temel Tipi: {hesaplama_sonucu['temel_tipi'].upper()}\n"
            rapor += "-" * 80 + "\n\n"
        
        # Tip bazında özetler
        tip_ozet = hesaplama_sonucu['tip_ozet']
        
        for tip, veri in tip_ozet.items():
            rapor += f"\n{tip.upper()}\n"
            rapor += "-" * 80 + "\n"
            rapor += f"Toplam Ağırlık: {veri['toplam_agirlik_kg']} kg\n"
            rapor += f"Toplam Uzunluk: {veri['toplam_uzunluk_m']} m\n"
            rapor += f"Hesaplama Sayısı: {veri['hesaplama_sayisi']}\n\n"
            
            # Detaylar
            for detay in veri['detaylar']:
                rapor += f"  {detay['poz_no']:10s} {detay['adi']:15s} "
                rapor += f"{detay['adet']:3d}Ø{detay['cap']:2d} "
                rapor += f"l={detay['uzunluk']:7.2f}cm "
                rapor += f"Toplam={detay['agirlik']:8.2f}kg\n"
        
        # Genel özet
        genel_ozet = hesaplama_sonucu['genel_ozet']
        rapor += "\n" + "=" * 80 + "\n"
        rapor += "GENEL ÖZET\n"
        rapor += "=" * 80 + "\n"
        rapor += f"Toplam Demir Ağırlığı: {genel_ozet['toplam_agirlik_kg']} kg\n"
        rapor += f"Toplam Demir Uzunluğu: {genel_ozet['toplam_uzunluk_m']} m\n"
        rapor += f"Toplam Poz Sayısı: {genel_ozet['hesaplama_sayisi']}\n"
        rapor += "=" * 80 + "\n"
        
        return rapor
