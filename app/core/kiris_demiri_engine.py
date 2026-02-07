"""
Kiriş Demiri Hesaplama Engine
STA4CAD DXF dosyalarından kiriş donatı bilgilerini okur ve metraj hesaplar

KURAL:
1. Kiriş adını bul (K001, K002...)
2. Kirişe ait tüm donatıları topla ve Y koordinatına göre sırala (yukarıdan aşağıya)
3. Sıralı donatıları şu kurallara göre sınıflandır:
   - EN ÜSTTEKİ: "ila" varsa ÜST İLAVE, yoksa ÜST MONTAJ
   - 2. SIRA: "gov" varsa GÖVDE, yoksa PİLYE
   - EN ALTTAKİ: ALT MONTAJ
   - 4. SIRA (varsa): "ila" varsa ALT İLAVE
4. Etriyeler ayrı pattern ile tespit edilir (etr.)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import ezdxf
from ezdxf.document import Drawing

logger = logging.getLogger(__name__)


@dataclass
class DonatiDetay:
    """Donatı detay bilgisi"""
    tip: str  # 'ust_montaj', 'ust_ilave', 'govde', 'pilye', 'alt_montaj', 'alt_ilave', 'etriye'
    adet: int
    cap: int  # mm (8, 10, 12, 14, 16, ...)
    aralik: int = 0  # cm (sadece etriye için)
    uzunluk: int = 0  # cm
    y_koordinat: float = 0.0  # Sıralama için

    def hesapla_toplam_boy_m(self) -> float:
        """Toplam boy hesapla (metre)"""
        if self.uzunluk > 0:
            return (self.adet * self.uzunluk) / 100.0
        return 0.0

    def hesapla_agirlik_kg(self, birim_agirlik: float) -> float:
        """Ağırlık hesapla (kg)"""
        return self.hesapla_toplam_boy_m() * birim_agirlik


@dataclass
class KirisDetay:
    """Bir kiriş için tüm donatı bilgileri"""
    kiris_adi: str
    ust_montaj: List[DonatiDetay] = field(default_factory=list)
    ust_ilave: List[DonatiDetay] = field(default_factory=list)
    govde: List[DonatiDetay] = field(default_factory=list)
    pilye: List[DonatiDetay] = field(default_factory=list)
    alt_montaj: List[DonatiDetay] = field(default_factory=list)
    alt_ilave: List[DonatiDetay] = field(default_factory=list)
    etriyeler: List[DonatiDetay] = field(default_factory=list)

    def tum_donatilar(self) -> List[DonatiDetay]:
        """Tüm donatıları tek listede döndür"""
        return (self.ust_montaj + self.ust_ilave + self.govde + self.pilye +
                self.alt_montaj + self.alt_ilave + self.etriyeler)


class KirisDemiriEngine:
    """Kiriş demiri hesaplama motoru"""

    # Demir ağırlık sabitleri (kg/m)
    DEMIR_ORANLAR = {
        6: 0.222, 8: 0.395, 10: 0.617, 12: 0.888,
        14: 1.21, 16: 1.58, 18: 2.0, 20: 2.47,
        22: 2.98, 24: 3.55, 28: 4.83, 32: 6.31
    }

    # Regex pattern'leri
    PATTERN_KIRIS_ADI = re.compile(r'^K\d{3}$')
    PATTERN_DONATI = re.compile(r'(\d+)ƒ(\d+)')  # Genel donatı pattern'i
    PATTERN_ETRIYE = re.compile(r'(\d+)ƒ(\d+)/(\d+)\s+etr\.\s*l=\s*(\d+)', re.IGNORECASE)
    PATTERN_ILAVE = re.compile(r'ila', re.IGNORECASE)  # "ila" içeren
    PATTERN_MONTAJ = re.compile(r'mon', re.IGNORECASE)  # "mon" içeren
    PATTERN_GOVDE = re.compile(r'gov', re.IGNORECASE)   # "gov" içeren
    PATTERN_PILYE = re.compile(r'pil', re.IGNORECASE)   # "pil" içeren
    PATTERN_UZUNLUK = re.compile(r'l=\s*(\d+)')  # Uzunluk bilgisi

    # Kiriş X toleransı (aynı kiriş içindeki donatılar için)
    # K050-K051 arası mesafe ~0.16, tolerans bunun yarısından az olmalı
    KIRIS_X_TOLERANS = 0.08

    def __init__(self):
        self.kirisler: List[KirisDetay] = []

    def dxf_oku(self, dosya_yolu: str) -> Dict:
        """
        DXF dosyasını oku ve kiriş donatı bilgilerini parse et

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

            # REBAR, DETAIL, BEAM layer'larından TEXT entity'leri al
            text_entities = []
            for entity in msp.query('TEXT'):
                layer = entity.dxf.layer.upper()
                # Kiriş adları BEAM layer'ında, donatılar REBAR/DETAIL layer'larında
                if 'REBAR' in layer or 'DETAIL' in layer or 'BEAM' in layer:
                    text_entities.append({
                        'text': entity.dxf.text.strip(),
                        'layer': entity.dxf.layer,
                        'y': entity.dxf.insert.y,
                        'x': entity.dxf.insert.x
                    })

            logger.info(f"Toplam {len(text_entities)} TEXT entity bulundu")

            # Y koordinatına göre sırala (yukarıdan aşağıya)
            text_entities.sort(key=lambda e: -e['y'])

            # Kirişleri parse et
            self.kirisler = self._parse_kirisler(text_entities)

            logger.info(f"Toplam {len(self.kirisler)} kiriş parse edildi")

            if not self.kirisler:
                return {
                    'status': 'warning',
                    'message': 'DXF dosyasında kiriş bulunamadı',
                    'kirisler': [],
                    'ozet_cap_bazinda': {},
                    'toplam_agirlik_kg': 0,
                    'toplam_adet': 0
                }

            # Özet hesapla
            ozet_cap = self.hesapla_toplam_agirlik(self.kirisler)
            ozet_kiris = self.olustur_ozet(self.kirisler)

            # KirisDetay objelerini dict'e çevir
            kirisler_dict = []
            for kiris in self.kirisler:
                kiris_dict = {
                    'ad': kiris.kiris_adi,
                    'ust_montaj': self._donati_list_to_dict(kiris.ust_montaj),
                    'ust_ilave': self._donati_list_to_dict(kiris.ust_ilave),
                    'govde': self._donati_list_to_dict(kiris.govde),
                    'pilye': self._donati_list_to_dict(kiris.pilye),
                    'alt_montaj': self._donati_list_to_dict(kiris.alt_montaj),
                    'alt_ilave': self._donati_list_to_dict(kiris.alt_ilave),
                    'etriyeler': self._donati_list_to_dict(kiris.etriyeler),
                    'toplam_demir_kg': 0.0
                }

                # Toplam ağırlık hesapla
                for donati in kiris.tum_donatilar():
                    birim_agirlik = self.DEMIR_ORANLAR.get(donati.cap, 0)
                    kiris_dict['toplam_demir_kg'] += donati.hesapla_agirlik_kg(birim_agirlik)

                kiris_dict['toplam_demir_kg'] = round(kiris_dict['toplam_demir_kg'], 2)
                kirisler_dict.append(kiris_dict)

            return {
                'status': 'success',
                'message': f'{len(self.kirisler)} kiriş başarıyla okundu',
                'kirisler': kirisler_dict,
                'ozet_cap_bazinda': ozet_cap,
                'ozet_kiris_bazinda': ozet_kiris,
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

    def _parse_kirisler(self, text_entities: List[Dict]) -> List[KirisDetay]:
        """
        TEXT entity'lerden kiriş bilgilerini çıkar

        KURAL:
        1. Tüm kiriş adlarını ve X koordinatlarını bul
        2. Her kiriş için X koordinatına yakın donatıları topla
        3. Donatıları etiketlerine göre sınıflandır (ila, mon, gov, etr)
        """
        kirisler = []

        # Önce tüm kiriş adlarını ve konumlarını bul
        kiris_konumlari = {}
        for entity in text_entities:
            text = entity['text']
            if self.PATTERN_KIRIS_ADI.match(text):
                kiris_konumlari[text] = {
                    'x': entity['x'],
                    'y': entity['y']
                }
                logger.debug(f"Kiriş bulundu: {text} X={entity['x']:.4f}")

        # Tüm donatıları topla
        tum_donatilar = []
        for entity in text_entities:
            text = entity['text']
            if 'ƒ' in text:
                donati_info = self._parse_donati_text(text, entity['y'], entity['x'])
                if donati_info:
                    tum_donatilar.append(donati_info)

        # Her donatıyı en yakın kirişe ata
        kiris_donati_map = {kiris_adi: [] for kiris_adi in kiris_konumlari.keys()}

        for donati in tum_donatilar:
            donati_x = donati['x']

            # En yakın kirişi bul
            min_dist = float('inf')
            en_yakin_kiris = None

            for kiris_adi, konum in kiris_konumlari.items():
                dist = abs(donati_x - konum['x'])
                if dist < min_dist:
                    min_dist = dist
                    en_yakin_kiris = kiris_adi

            if en_yakin_kiris:
                kiris_donati_map[en_yakin_kiris].append(donati)

        # Her kiriş için donatıları sınıflandır
        for kiris_adi, donatilar in kiris_donati_map.items():
            if donatilar:
                kiris = KirisDetay(kiris_adi=kiris_adi)
                self._siniflandir_donatilar(kiris, donatilar)
                kirisler.append(kiris)
                logger.debug(f"{kiris_adi}: {len(donatilar)} donatı bulundu")

        # Kiriş adına göre sırala
        kirisler.sort(key=lambda k: k.kiris_adi)

        return kirisler

    def _parse_donati_text(self, text: str, y_koordinat: float, x_koordinat: float = 0.0) -> Optional[Dict]:
        """
        Tek bir TEXT'ten donatı bilgisi çıkar

        Returns:
            Dict: {'tip_pattern': str, 'adet': int, 'cap': int, 'aralik': int, 'uzunluk': int, 'y': float, 'x': float}
        """
        # Etriye kontrolü (önce etriye, çünkü en belirgin pattern)
        match = self.PATTERN_ETRIYE.search(text)
        if match:
            adet, cap, aralik, uzunluk = map(int, match.groups())
            return {
                'tip_pattern': 'etriye',
                'adet': adet,
                'cap': cap,
                'aralik': aralik,
                'uzunluk': uzunluk,
                'y': y_koordinat,
                'x': x_koordinat,
                'text': text
            }

        # Genel donatı pattern'i ile adet ve çap bul
        match_donati = self.PATTERN_DONATI.search(text)
        if not match_donati:
            return None

        adet, cap = map(int, match_donati.groups())

        # Uzunluk bilgisini ara
        uzunluk = 0
        uzunluk_match = self.PATTERN_UZUNLUK.search(text)
        if uzunluk_match:
            uzunluk = int(uzunluk_match.group(1))

        # Tip belirleme (etiketlere göre)
        if self.PATTERN_ILAVE.search(text):
            tip_pattern = 'ilave'
        elif self.PATTERN_MONTAJ.search(text):
            tip_pattern = 'montaj'
        elif self.PATTERN_GOVDE.search(text):
            tip_pattern = 'govde'
        elif self.PATTERN_PILYE.search(text):
            tip_pattern = 'pilye'
        else:
            tip_pattern = 'boyuna'  # Etiket yok, pozisyona göre belirlenecek

        return {
            'tip_pattern': tip_pattern,
            'adet': adet,
            'cap': cap,
            'uzunluk': uzunluk,
            'aralik': 0,
            'y': y_koordinat,
            'x': x_koordinat,
            'text': text
        }

    def _siniflandir_donatilar(self, kiris: KirisDetay, donatilar: List[Dict]):
        """
        Kiriş donatılarını etiketlerine ve Y koordinatına göre sınıflandır

        KURAL:
        1. Etriyeleri ayır (etr. içeren)
        2. İlave donatıları ayır (ila. içeren)
        3. Montaj donatılarını ayır (mon. içeren)
        4. Gövde donatılarını ayır (gov. içeren)
        5. Etiketsiz donatıları Y koordinatına göre alt montaj olarak sınıflandır
        """
        # Etriyeleri ekle
        for don in donatilar:
            if don['tip_pattern'] == 'etriye':
                donati = DonatiDetay(
                    tip='etriye',
                    adet=don['adet'],
                    cap=don['cap'],
                    aralik=don['aralik'],
                    uzunluk=don['uzunluk'],
                    y_koordinat=don['y']
                )
                kiris.etriyeler.append(donati)

        # İlave donatıları ekle (üst ilave olarak)
        for don in donatilar:
            if don['tip_pattern'] == 'ilave':
                donati = DonatiDetay(
                    tip='ust_ilave',
                    adet=don['adet'],
                    cap=don['cap'],
                    uzunluk=don['uzunluk'],
                    y_koordinat=don['y']
                )
                kiris.ust_ilave.append(donati)

        # Montaj donatılarını ekle (üst montaj olarak)
        for don in donatilar:
            if don['tip_pattern'] == 'montaj':
                donati = DonatiDetay(
                    tip='ust_montaj',
                    adet=don['adet'],
                    cap=don['cap'],
                    uzunluk=don['uzunluk'],
                    y_koordinat=don['y']
                )
                kiris.ust_montaj.append(donati)

        # Gövde donatılarını ekle
        for don in donatilar:
            if don['tip_pattern'] == 'govde':
                donati = DonatiDetay(
                    tip='govde',
                    adet=don['adet'],
                    cap=don['cap'],
                    uzunluk=don['uzunluk'],
                    y_koordinat=don['y']
                )
                kiris.govde.append(donati)

        # Pilye donatılarını ekle
        for don in donatilar:
            if don['tip_pattern'] == 'pilye':
                donati = DonatiDetay(
                    tip='pilye',
                    adet=don['adet'],
                    cap=don['cap'],
                    uzunluk=don['uzunluk'],
                    y_koordinat=don['y']
                )
                kiris.pilye.append(donati)

        # Etiketsiz boyuna donatıları alt montaj olarak ekle
        # (genellikle uzunluk bilgisi olan ve etiket olmayan donatılar)
        for don in donatilar:
            if don['tip_pattern'] == 'boyuna' and don['uzunluk'] > 0:
                donati = DonatiDetay(
                    tip='alt_montaj',
                    adet=don['adet'],
                    cap=don['cap'],
                    uzunluk=don['uzunluk'],
                    y_koordinat=don['y']
                )
                kiris.alt_montaj.append(donati)

    def _donati_list_to_dict(self, donati_listesi: List[DonatiDetay]) -> List[Dict]:
        """DonatiDetay objelerini dictionary'ye çevir"""
        result = []
        for donati in donati_listesi:
            birim_agirlik = self.DEMIR_ORANLAR.get(donati.cap, 0)
            result.append({
                'tip': donati.tip,
                'adet': donati.adet,
                'cap': donati.cap,
                'aralik_cm': donati.aralik,
                'uzunluk_cm': donati.uzunluk,
                'toplam_agirlik_kg': round(donati.hesapla_agirlik_kg(birim_agirlik), 2)
            })
        return result

    def hesapla_toplam_agirlik(self, kirisler: List[KirisDetay]) -> Dict:
        """
        Çap bazında toplam ağırlık hesapla
        """
        cap_ozeti = {}

        for kiris in kirisler:
            for donati in kiris.tum_donatilar():
                cap_key = f'fi_{donati.cap}'

                if cap_key not in cap_ozeti:
                    cap_ozeti[cap_key] = {
                        'cap': donati.cap,
                        'adet': 0,
                        'toplam_boy_m': 0.0,
                        'agirlik_kg': 0.0
                    }

                cap_ozeti[cap_key]['adet'] += donati.adet

                # Uzunluk bilgisi varsa toplam boy hesapla
                if donati.uzunluk > 0:
                    toplam_boy_m = donati.hesapla_toplam_boy_m()
                    cap_ozeti[cap_key]['toplam_boy_m'] += toplam_boy_m

                    # Ağırlık hesapla
                    birim_agirlik = self.DEMIR_ORANLAR.get(donati.cap, 0)
                    agirlik = donati.hesapla_agirlik_kg(birim_agirlik)
                    cap_ozeti[cap_key]['agirlik_kg'] += agirlik

        return cap_ozeti

    def olustur_ozet(self, kirisler: List[KirisDetay]) -> List[Dict]:
        """
        Kiriş bazında özet oluştur
        """
        ozet = []

        for kiris in kirisler:
            toplam_agirlik = 0.0
            boyuna_ozet = []
            etriye_ozet = []

            # Boyuna donatılar (etriye hariç tüm donatılar)
            for donati in (kiris.ust_montaj + kiris.ust_ilave + kiris.govde +
                          kiris.pilye + kiris.alt_montaj + kiris.alt_ilave):
                boyuna_ozet.append(f"{donati.adet}ƒ{donati.cap}")
                if donati.uzunluk > 0:
                    birim_agirlik = self.DEMIR_ORANLAR.get(donati.cap, 0)
                    toplam_agirlik += donati.hesapla_agirlik_kg(birim_agirlik)

            # Etriyeler
            for donati in kiris.etriyeler:
                etriye_ozet.append(f"{donati.adet}ƒ{donati.cap}/{donati.aralik}")
                if donati.uzunluk > 0:
                    birim_agirlik = self.DEMIR_ORANLAR.get(donati.cap, 0)
                    toplam_agirlik += donati.hesapla_agirlik_kg(birim_agirlik)

            ozet.append({
                'kiris_adi': kiris.kiris_adi,
                'boyuna': ', '.join(boyuna_ozet) if boyuna_ozet else '-',
                'etriye': ', '.join(etriye_ozet) if etriye_ozet else '-',
                'toplam_agirlik_kg': round(toplam_agirlik, 2)
            })

        return ozet


# Test kodu
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    engine = KirisDemiriEngine()

    # Test dosyası
    test_dxf = r"D:\Drawing3.dxf"

    print("DXF dosyası okunuyor...")
    sonuc = engine.dxf_oku(test_dxf)

    if sonuc['status'] == 'success':
        print(f"\n[OK] {sonuc['message']}")
        print(f"\nToplam Agirlik: {sonuc['toplam_agirlik_kg']:.2f} kg")
        print(f"Toplam Adet: {sonuc['toplam_adet']}")

        print("\n[STATS] Cap Bazinda Ozet:")
        for cap_key, veri in sorted(sonuc['ozet_cap_bazinda'].items()):
            print(f"  {cap_key}: {veri['adet']} adet, {veri['toplam_boy_m']:.2f} m, {veri['agirlik_kg']:.2f} kg")

        print("\n[STATS] Ilk 5 Kiris:")
        for kiris in sonuc['kirisler'][:5]:
            print(f"\n  {kiris.kiris_adi}:")
            if kiris.ust_montaj:
                print(f"    Ust Montaj: {', '.join(f'{d.adet}f{d.cap}' for d in kiris.ust_montaj)}")
            if kiris.ust_ilave:
                print(f"    Ust Ilave: {', '.join(f'{d.adet}f{d.cap}' for d in kiris.ust_ilave)}")
            if kiris.govde:
                print(f"    Govde: {', '.join(f'{d.adet}f{d.cap}' for d in kiris.govde)}")
            if kiris.pilye:
                print(f"    Pilye: {', '.join(f'{d.adet}f{d.cap}' for d in kiris.pilye)}")
            if kiris.alt_montaj:
                print(f"    Alt Montaj: {', '.join(f'{d.adet}f{d.cap}' for d in kiris.alt_montaj)}")
            if kiris.alt_ilave:
                print(f"    Alt Ilave: {', '.join(f'{d.adet}f{d.cap}' for d in kiris.alt_ilave)}")
            if kiris.etriyeler:
                print(f"    Etriye: {', '.join(f'{d.adet}f{d.cap}/{d.aralik}' for d in kiris.etriyeler)}")
    else:
        print(f"\n[ERROR] Hata: {sonuc.get('error', 'Bilinmeyen hata')}")
