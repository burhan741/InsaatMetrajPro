"""
Kolon Demiri Hesaplama Engine
STA4CAD DXF dosyalarından kolon donatı bilgilerini okur ve metraj hesaplar
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import ezdxf

logger = logging.getLogger(__name__)


@dataclass
class KolonDonatiDetay:
    """Kolon donatı detay bilgisi"""
    tip: str  # 'boyuna', 'ciroz'
    adet: int
    cap: int  # mm
    uzunluk: int  # cm

    def hesapla_toplam_boy_m(self) -> float:
        """Toplam boy hesapla (metre)"""
        return (self.adet * self.uzunluk) / 100.0

    def hesapla_agirlik_kg(self, birim_agirlik: float) -> float:
        """Ağırlık hesapla (kg)"""
        return self.hesapla_toplam_boy_m() * birim_agirlik


@dataclass
class EtriyeDetay:
    """Etriye detay bilgisi (toplu)"""
    adet: int
    cap: int  # mm
    uzunluk: int  # cm

    def hesapla_toplam_boy_m(self) -> float:
        """Toplam boy hesapla (metre)"""
        return (self.adet * self.uzunluk) / 100.0

    def hesapla_agirlik_kg(self, birim_agirlik: float) -> float:
        """Ağırlık hesapla (kg)"""
        return self.hesapla_toplam_boy_m() * birim_agirlik


@dataclass
class KolonDetay:
    """Bir kolon için donatı bilgileri"""
    kolon_adi: str
    boyuna_donatilar: List[KolonDonatiDetay] = field(default_factory=list)
    ciroz_donatilar: List[KolonDonatiDetay] = field(default_factory=list)

    def tum_donatilar(self) -> List[KolonDonatiDetay]:
        """Tüm donatıları döndür"""
        return self.boyuna_donatilar + self.ciroz_donatilar


@dataclass
class KatKolonDetay:
    """Bir kat için kolon bilgileri"""
    kat_adi: str
    kolonlar: List[KolonDetay] = field(default_factory=list)
    etriyeler: List[EtriyeDetay] = field(default_factory=list)


class KolonDemiriEngine:
    """Kolon demiri hesaplama motoru"""

    # Demir ağırlık sabitleri (kg/m)
    DEMIR_ORANLAR = {
        6: 0.222, 8: 0.395, 10: 0.617, 12: 0.888,
        14: 1.21, 16: 1.58, 18: 2.0, 20: 2.47,
        22: 2.98, 24: 3.55, 28: 4.83, 32: 6.31
    }

    # Regex pattern'leri
    PATTERN_KAT_ADI = re.compile(r'(NORMAL KAT|ZEMİN|ZEMIN|TAVAN|KAT|BODRUM).*?(KOLON|APLIKASYON)', re.IGNORECASE)
    PATTERN_KOLON_ADI = re.compile(r'^S\d{3}$')
    PATTERN_DONATI = re.compile(r'^\s*(\d+)ƒ(\d+)\s+l=(\d+)$')
    PATTERN_ETRIYE = re.compile(r'^\s*(\d+)ƒ(\d+)\s+[Ee]tr\.\s+l=\s*(\d+)')

    # Y koordinat toleransı
    Y_TOLERANS = 2.0

    def __init__(self):
        self.katlar: List[KatKolonDetay] = []

    def dxf_oku(self, dosya_yolu: str) -> Dict:
        """
        DXF dosyasını oku ve kolon donatı bilgilerini parse et

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

            # TEXT entity'leri al
            text_entities = []
            for entity in msp.query('TEXT'):
                layer = entity.dxf.layer
                text = entity.dxf.text.strip()

                # İlgili layer'ları al
                if any(keyword in layer.upper() for keyword in ['DETAIL', 'TABLE', 'COLUMN']):
                    text_entities.append({
                        'text': text,
                        'layer': layer,
                        'y': entity.dxf.insert.y,
                        'x': entity.dxf.insert.x
                    })

            logger.info(f"Toplam {len(text_entities)} TEXT entity bulundu")

            # Y koordinatına göre sırala
            text_entities.sort(key=lambda e: -e['y'])

            # Katları parse et
            self.katlar = self._parse_katlar(text_entities)

            logger.info(f"Toplam {len(self.katlar)} kat parse edildi")

            if not self.katlar:
                return {
                    'status': 'warning',
                    'message': 'DXF dosyasında kolon katı bulunamadı',
                    'katlar': [],
                    'ozet_cap_bazinda': {},
                    'toplam_agirlik_kg': 0,
                    'toplam_adet': 0
                }

            # Özet hesapla
            ozet_cap = self.hesapla_toplam_agirlik(self.katlar)
            ozet_kolon = self.olustur_kolon_ozeti(self.katlar)

            return {
                'status': 'success',
                'message': f'{len(self.katlar)} kat kolon demiri başarıyla okundu',
                'katlar': self.katlar,
                'ozet_cap_bazinda': ozet_cap,
                'ozet_kolon_bazinda': ozet_kolon,
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

    def _parse_katlar(self, text_entities: List[Dict]) -> List[KatKolonDetay]:
        """TEXT entity'lerden kat ve kolon bilgilerini çıkar"""
        katlar = []
        current_kat: Optional[KatKolonDetay] = None
        current_kolon: Optional[KolonDetay] = None
        kolon_detay_mode = False  # "KOLON DETAYI" text'inden sonra mıyız?

        for entity in text_entities:
            text = entity['text']
            y_coord = entity['y']

            # Kat başlığı kontrolü
            kat_match = self.PATTERN_KAT_ADI.search(text)
            if kat_match and ('PLANI' in text.upper() or 'APLIKASYON' in text.upper()):
                # Önceki katı kaydet
                if current_kat:
                    if current_kolon:
                        current_kat.kolonlar.append(current_kolon)
                        current_kolon = None
                    if current_kat.kolonlar or current_kat.etriyeler:
                        katlar.append(current_kat)

                # Yeni kat başlat
                current_kat = KatKolonDetay(kat_adi=text.strip())
                kolon_detay_mode = False
                logger.debug(f"Yeni kat bulundu: {text.strip()}")
                continue

            if not current_kat:
                continue

            # Kolon adı kontrolü (S001, S002...)
            kolon_match = self.PATTERN_KOLON_ADI.match(text)
            if kolon_match:
                # Önceki kolonu kaydet
                if current_kolon:
                    current_kat.kolonlar.append(current_kolon)

                # Yeni kolon başlat
                current_kolon = KolonDetay(kolon_adi=text)
                kolon_detay_mode = False
                logger.debug(f"  Kolon bulundu: {text}")
                continue

            # "KOLON DETAYI" text'i
            if "KOLON DETAYI" in text.upper():
                kolon_detay_mode = True
                continue

            # Etriye kontrolü (toplu)
            etriye_match = self.PATTERN_ETRIYE.search(text)
            if etriye_match:
                adet, cap, uzunluk = map(int, etriye_match.groups())
                etriye = EtriyeDetay(adet=adet, cap=cap, uzunluk=uzunluk)
                current_kat.etriyeler.append(etriye)
                logger.debug(f"  Etriye bulundu: {adet}ƒ{cap} Etr. l={uzunluk}")
                continue

            # Donatı kontrolü (boyuna veya çiroz)
            if current_kolon or kolon_detay_mode:
                donati_match = self.PATTERN_DONATI.match(text)
                if donati_match:
                    adet, cap, uzunluk = map(int, donati_match.groups())

                    # Boyuna mu çiroz mu? (fi >= 12 genelde boyuna, fi <= 10 genelde çiroz)
                    # Ama daha kesin ayırt için: DETAIL3 layer'ı genelde boyuna, TABLE3 çiroz
                    tip = 'boyuna' if cap >= 12 else 'ciroz'

                    donati = KolonDonatiDetay(tip=tip, adet=adet, cap=cap, uzunluk=uzunluk)

                    if current_kolon:
                        if tip == 'boyuna':
                            current_kolon.boyuna_donatilar.append(donati)
                        else:
                            current_kolon.ciroz_donatilar.append(donati)
                        logger.debug(f"    {tip.capitalize()}: {adet}ƒ{cap} l={uzunluk}")

        # Son kolon ve katı kaydet
        if current_kolon and current_kat:
            current_kat.kolonlar.append(current_kolon)
        if current_kat and (current_kat.kolonlar or current_kat.etriyeler):
            katlar.append(current_kat)

        return katlar

    def hesapla_toplam_agirlik(self, katlar: List[KatKolonDetay]) -> Dict:
        """Çap bazında toplam ağırlık hesapla"""
        cap_ozeti = {}

        for kat in katlar:
            # Kolonlardaki donatılar
            for kolon in kat.kolonlar:
                for donati in kolon.tum_donatilar():
                    cap_key = f'fi_{donati.cap}'

                    if cap_key not in cap_ozeti:
                        cap_ozeti[cap_key] = {
                            'cap': donati.cap,
                            'adet': 0,
                            'toplam_boy_m': 0.0,
                            'agirlik_kg': 0.0
                        }

                    cap_ozeti[cap_key]['adet'] += donati.adet
                    toplam_boy_m = donati.hesapla_toplam_boy_m()
                    cap_ozeti[cap_key]['toplam_boy_m'] += toplam_boy_m

                    birim_agirlik = self.DEMIR_ORANLAR.get(donati.cap, 0)
                    agirlik = donati.hesapla_agirlik_kg(birim_agirlik)
                    cap_ozeti[cap_key]['agirlik_kg'] += agirlik

            # Etriyeler
            for etriye in kat.etriyeler:
                cap_key = f'fi_{etriye.cap}'

                if cap_key not in cap_ozeti:
                    cap_ozeti[cap_key] = {
                        'cap': etriye.cap,
                        'adet': 0,
                        'toplam_boy_m': 0.0,
                        'agirlik_kg': 0.0
                    }

                cap_ozeti[cap_key]['adet'] += etriye.adet
                toplam_boy_m = etriye.hesapla_toplam_boy_m()
                cap_ozeti[cap_key]['toplam_boy_m'] += toplam_boy_m

                birim_agirlik = self.DEMIR_ORANLAR.get(etriye.cap, 0)
                agirlik = etriye.hesapla_agirlik_kg(birim_agirlik)
                cap_ozeti[cap_key]['agirlik_kg'] += agirlik

        return cap_ozeti

    def olustur_kolon_ozeti(self, katlar: List[KatKolonDetay]) -> List[Dict]:
        """Kolon bazında özet oluştur"""
        ozet = []

        for kat in katlar:
            for kolon in kat.kolonlar:
                toplam_agirlik = 0.0
                boyuna_str = []
                ciroz_str = []

                for donati in kolon.boyuna_donatilar:
                    boyuna_str.append(f"{donati.adet}ƒ{donati.cap}")
                    birim_agirlik = self.DEMIR_ORANLAR.get(donati.cap, 0)
                    toplam_agirlik += donati.hesapla_agirlik_kg(birim_agirlik)

                for donati in kolon.ciroz_donatilar:
                    ciroz_str.append(f"{donati.adet}ƒ{donati.cap}")
                    birim_agirlik = self.DEMIR_ORANLAR.get(donati.cap, 0)
                    toplam_agirlik += donati.hesapla_agirlik_kg(birim_agirlik)

                ozet.append({
                    'kat_adi': kat.kat_adi,
                    'kolon_adi': kolon.kolon_adi,
                    'boyuna': ', '.join(boyuna_str) if boyuna_str else '-',
                    'ciroz': ', '.join(ciroz_str) if ciroz_str else '-',
                    'toplam_agirlik_kg': round(toplam_agirlik, 2)
                })

        return ozet


# Test kodu
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    engine = KolonDemiriEngine()
    test_dxf = r"D:\Drawing3.dxf"

    print("=" * 60)
    print("Testing KolonDemiriEngine")
    print("=" * 60)

    sonuc = engine.dxf_oku(test_dxf)

    if sonuc['status'] == 'success':
        print(f"\n✅ {sonuc['message']}")
        print(f"\nToplam Ağırlık: {sonuc['toplam_agirlik_kg']:.2f} kg")
        print(f"Toplam Adet: {sonuc['toplam_adet']}")

        print("\n📊 Çap Bazında Özet:")
        for cap_key, veri in sorted(sonuc['ozet_cap_bazinda'].items()):
            print(f"  {cap_key}: {veri['adet']} adet, {veri['toplam_boy_m']:.2f} m, {veri['agirlik_kg']:.2f} kg")

        print("\n🏛️ İlk 5 Kolon:")
        for kolon_ozet in sonuc['ozet_kolon_bazinda'][:5]:
            print(f"\n  {kolon_ozet['kolon_adi']} ({kolon_ozet['kat_adi']}):")
            print(f"    Boyuna: {kolon_ozet['boyuna']}")
            print(f"    Çiroz: {kolon_ozet['ciroz']}")
            print(f"    Ağırlık: {kolon_ozet['toplam_agirlik_kg']:.2f} kg")

        if sonuc['katlar']:
            print(f"\n📋 Etriye Özeti:")
            for kat in sonuc['katlar']:
                if kat.etriyeler:
                    print(f"\n  {kat.kat_adi}:")
                    for etr in kat.etriyeler:
                        print(f"    {etr.adet}ƒ{etr.cap} Etr. l={etr.uzunluk}")

    else:
        print(f"\n❌ Hata: {sonuc.get('error', 'Bilinmeyen hata')}")

    print("\n" + "=" * 60)
