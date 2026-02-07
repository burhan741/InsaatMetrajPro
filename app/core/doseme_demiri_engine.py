"""
Döşeme Demiri Hesaplama Engine
STA4CAD DXF dosyalarından döşeme donatı bilgilerini okur ve metraj hesaplar
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import ezdxf

logger = logging.getLogger(__name__)


@dataclass
class DosemeDonatiDetay:
    """Döşeme donatı detay bilgisi"""
    adet: int
    cap: int  # mm (8, 10, 12, 14, 16, ...)
    aralik: int  # cm
    uzunluk: int  # cm

    def hesapla_toplam_boy_m(self) -> float:
        """Toplam boy hesapla (metre)"""
        return (self.adet * self.uzunluk) / 100.0

    def hesapla_agirlik_kg(self, birim_agirlik: float) -> float:
        """Ağırlık hesapla (kg)"""
        return self.hesapla_toplam_boy_m() * birim_agirlik


@dataclass
class KatDosemeDetay:
    """Bir kat için döşeme donatı bilgileri"""
    kat_adi: str
    donatilar: List[DosemeDonatiDetay] = field(default_factory=list)
    y_koordinat: float = 0.0  # Kat başlığının Y koordinatı

    def tum_donatilar(self) -> List[DosemeDonatiDetay]:
        """Tüm donatıları döndür"""
        return self.donatilar


class DosemeDemiriEngine:
    """Döşeme demiri hesaplama motoru"""

    # Demir ağırlık sabitleri (kg/m)
    DEMIR_ORANLAR = {
        6: 0.222, 8: 0.395, 10: 0.617, 12: 0.888,
        14: 1.21, 16: 1.58, 18: 2.0, 20: 2.47,
        22: 2.98, 24: 3.55, 28: 4.83, 32: 6.31
    }

    # Regex pattern'leri
    PATTERN_KAT_ADI = re.compile(r'(NORMAL KAT|ZEMİN|ZEMIN|TAVAN|KAT|BODRUM).*?(KALIP|PLANI)?', re.IGNORECASE)
    PATTERN_DOSEME_DONATI = re.compile(r'^\s*(\d+)ƒ(\d+)/(\d+)\s+l=(\d+)')

    # Y koordinat toleransı (aynı kata ait kabul etme mesafesi - DXF birimlerinde)
    Y_TOLERANS = 1.0  # 1 birim (genelde metre veya cm)

    def __init__(self):
        self.katlar: List[KatDosemeDetay] = []

    def dxf_oku(self, dosya_yolu: str) -> Dict:
        """
        DXF dosyasını oku ve döşeme donatı bilgilerini parse et

        Args:
            dosya_yolu: DXF dosyasının tam yolu

        Returns:
            Dict: Sonuç dictionary'si
        """
        try:
            logger.info(f"DXF dosyası okunuyor: {dosya_yolu}")

            # DXF dosyasını aç
            doc = ezdxf.readfile(dosya_yolu)
            msp = doc.modelspace()

            # TEXT entity'leri al (REBAR, DETAIL layer'larından)
            text_entities = []
            for entity in msp.query('TEXT'):
                layer = entity.dxf.layer
                text = entity.dxf.text.strip()

                # Sadece ilgili layer'ları al
                if any(keyword in layer.upper() for keyword in ['REBAR', 'DETAIL', 'SLAB']):
                    text_entities.append({
                        'text': text,
                        'layer': layer,
                        'y': entity.dxf.insert.y,
                        'x': entity.dxf.insert.x
                    })

            logger.info(f"Toplam {len(text_entities)} TEXT entity bulundu")

            # Y koordinatına göre sırala (yukarıdan aşağıya)
            text_entities.sort(key=lambda e: -e['y'])

            # Katları parse et
            self.katlar = self._parse_katlar(text_entities)

            logger.info(f"Toplam {len(self.katlar)} kat parse edildi")

            if not self.katlar:
                return {
                    'status': 'warning',
                    'message': 'DXF dosyasında döşeme katı bulunamadı',
                    'katlar': [],
                    'ozet_cap_bazinda': {},
                    'toplam_agirlik_kg': 0,
                    'toplam_adet': 0
                }

            # Özet hesapla
            ozet_cap = self.hesapla_toplam_agirlik(self.katlar)
            ozet_kat = self.olustur_ozet(self.katlar)

            return {
                'status': 'success',
                'message': f'{len(self.katlar)} kat döşeme demiri başarıyla okundu',
                'katlar': self.katlar,
                'ozet_cap_bazinda': ozet_cap,
                'ozet_kat_bazinda': ozet_kat,
                'toplam_agirlik_kg': sum(v['agirlik_kg'] for v in ozet_cap.values()),
                'toplam_adet': sum(v['adet'] for v in ozet_cap.values())
            }

        except IOError as e:
            logger.error(f"Dosya okuma hatası: {e}")
            return {'status': 'error', 'error': f'Dosya okunamadı: {str(e)}'}
        except ezdxf.DXFStructureError as e:
            logger.error(f"DXF yapı hatası: {e}")
            return {'status': 'error', 'error': f'Geçersiz DXF formatı: {str(e)}'}
        except Exception as e:
            logger.exception("Beklenmeyen hata")
            return {'status': 'error', 'error': f'Beklenmeyen hata: {str(e)}'}

    def _parse_katlar(self, text_entities: List[Dict]) -> List[KatDosemeDetay]:
        """
        TEXT entity'lerden kat bilgilerini çıkar

        Args:
            text_entities: TEXT entity listesi (Y'ye göre sıralı)

        Returns:
            List[KatDosemeDetay]: Parse edilmiş kat listesi
        """
        katlar = []
        current_kat: Optional[KatDosemeDetay] = None

        for entity in text_entities:
            text = entity['text']
            y_coord = entity['y']

            # Kat başlığı mı kontrol et
            kat_match = self.PATTERN_KAT_ADI.search(text)
            if kat_match and ('PLANI' in text.upper() or 'KALIP' in text.upper()):
                # Önceki katı kaydet
                if current_kat and current_kat.donatilar:
                    katlar.append(current_kat)

                # Yeni kat başlat
                current_kat = KatDosemeDetay(
                    kat_adi=text.strip(),
                    y_koordinat=y_coord
                )
                logger.debug(f"Yeni kat bulundu: {text.strip()} (Y={y_coord:.2f})")
                continue

            # Eğer henüz kat başlamamışsa, atla
            if not current_kat:
                continue

            # Y koordinatı çok uzaksa (farklı kat), atla
            if abs(y_coord - current_kat.y_koordinat) > self.Y_TOLERANS:
                # Eğer aşağı doğru çok uzaklaştıysak, bu kat bitmiş demektir
                if current_kat.y_koordinat - y_coord > self.Y_TOLERANS:
                    continue

            # Döşeme donatı bilgisini parse et
            donati = self._parse_doseme_donati(text)
            if donati:
                current_kat.donatilar.append(donati)
                logger.debug(f"  Donatı eklendi: {donati.adet}ƒ{donati.cap}/{donati.aralik} l={donati.uzunluk}")

        # Son katı kaydet
        if current_kat and current_kat.donatilar:
            katlar.append(current_kat)

        return katlar

    def _parse_doseme_donati(self, text: str) -> Optional[DosemeDonatiDetay]:
        """
        Tek bir TEXT'ten döşeme donatı bilgisi çıkar

        Args:
            text: Parse edilecek metin (örn: "58ƒ8/20 l=95")

        Returns:
            Optional[DosemeDonatiDetay]: Parse edilmiş donatı veya None
        """
        match = self.PATTERN_DOSEME_DONATI.match(text)
        if match:
            adet, cap, aralik, uzunluk = map(int, match.groups())
            return DosemeDonatiDetay(
                adet=adet,
                cap=cap,
                aralik=aralik,
                uzunluk=uzunluk
            )
        return None

    def hesapla_toplam_agirlik(self, katlar: List[KatDosemeDetay]) -> Dict:
        """
        Çap bazında toplam ağırlık hesapla

        Args:
            katlar: Kat listesi

        Returns:
            Dict: Çap bazında özet
        """
        cap_ozeti = {}

        for kat in katlar:
            for donati in kat.tum_donatilar():
                cap_key = f'fi_{donati.cap}'

                if cap_key not in cap_ozeti:
                    cap_ozeti[cap_key] = {
                        'cap': donati.cap,
                        'adet': 0,
                        'toplam_boy_m': 0.0,
                        'agirlik_kg': 0.0
                    }

                cap_ozeti[cap_key]['adet'] += donati.adet

                # Toplam boy hesapla
                toplam_boy_m = donati.hesapla_toplam_boy_m()
                cap_ozeti[cap_key]['toplam_boy_m'] += toplam_boy_m

                # Ağırlık hesapla
                birim_agirlik = self.DEMIR_ORANLAR.get(donati.cap, 0)
                agirlik = donati.hesapla_agirlik_kg(birim_agirlik)
                cap_ozeti[cap_key]['agirlik_kg'] += agirlik

        return cap_ozeti

    def olustur_ozet(self, katlar: List[KatDosemeDetay]) -> List[Dict]:
        """
        Kat bazında özet oluştur

        Args:
            katlar: Kat listesi

        Returns:
            List[Dict]: Kat bazında özet
        """
        ozet = []

        for kat in katlar:
            toplam_agirlik = 0.0
            toplam_adet = 0
            cap_dagilimi = {}

            for donati in kat.tum_donatilar():
                toplam_adet += donati.adet

                # Çap dağılımı
                cap_key = f'ƒ{donati.cap}'
                if cap_key not in cap_dagilimi:
                    cap_dagilimi[cap_key] = 0
                cap_dagilimi[cap_key] += donati.adet

                # Ağırlık hesapla
                birim_agirlik = self.DEMIR_ORANLAR.get(donati.cap, 0)
                toplam_agirlik += donati.hesapla_agirlik_kg(birim_agirlik)

            # Çap dağılımını string'e çevir
            cap_dagilimi_str = ', '.join([f'{adet}{cap}' for cap, adet in sorted(cap_dagilimi.items())])

            ozet.append({
                'kat_adi': kat.kat_adi,
                'toplam_adet': toplam_adet,
                'cap_dagilimi': cap_dagilimi_str,
                'toplam_agirlik_kg': round(toplam_agirlik, 2)
            })

        return ozet


# Test kodu
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    engine = DosemeDemiriEngine()

    # Test dosyası
    test_dxf = r"D:\Drawing3.dxf"

    print("=" * 60)
    print("DXF dosyası okunuyor...")
    print("=" * 60)

    sonuc = engine.dxf_oku(test_dxf)

    if sonuc['status'] == 'success':
        print(f"\n✅ {sonuc['message']}")
        print(f"\nToplam Ağırlık: {sonuc['toplam_agirlik_kg']:.2f} kg")
        print(f"Toplam Adet: {sonuc['toplam_adet']}")

        print("\n📊 Çap Bazında Özet:")
        for cap_key, veri in sorted(sonuc['ozet_cap_bazinda'].items()):
            print(f"  {cap_key}: {veri['adet']} adet, {veri['toplam_boy_m']:.2f} m, {veri['agirlik_kg']:.2f} kg")

        print("\n🏢 Kat Bazında Özet:")
        for kat_ozet in sonuc['ozet_kat_bazinda']:
            print(f"\n  {kat_ozet['kat_adi']}:")
            print(f"    Toplam Adet: {kat_ozet['toplam_adet']}")
            print(f"    Çap Dağılımı: {kat_ozet['cap_dagilimi']}")
            print(f"    Ağırlık: {kat_ozet['toplam_agirlik_kg']:.2f} kg")

        print("\n🏗️ İlk Kat Detayı:")
        if sonuc['katlar']:
            kat = sonuc['katlar'][0]
            print(f"\n  {kat.kat_adi}:")
            for i, donati in enumerate(kat.donatilar[:5], 1):
                print(f"    {i}. {donati.adet}ƒ{donati.cap}/{donati.aralik} l={donati.uzunluk}")
            if len(kat.donatilar) > 5:
                print(f"    ... ve {len(kat.donatilar) - 5} donatı daha")

    else:
        print(f"\n❌ Hata: {sonuc.get('error', 'Bilinmeyen hata')}")

    print("\n" + "=" * 60)
