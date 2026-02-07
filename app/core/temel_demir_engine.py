"""
Temel Demir Hesaplama Engine
STA4CAD DXF dosyalarından temel donatı bilgilerini otomatik okur ve metraj çıkarır

KURAL:
1. Temel ismini ve paftasını bul (RADYE, MÜTEMADI vb.)
2. Temelin kesit detaylarını bul ve demirleri hesapla
3. Temel alanındaki ilave demirleri bul (genelde "alt" etiketi ile)
4. Temeldeki hatıl demirlerini bul ve hesapla
5. Temel paftasındaki kolon filizlerini bul
6. Kolon etriye tablosunu bul ve hesapla
"""

import ezdxf
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path


class TemelDemirEngine:
    """
    STA4CAD DXF dosyalarından temel demir metrajı hesaplayan engine.

    Kurallar:
    1. Temel paftasını bul (RADYE, MÜTEMADI)
    2. Kesit demirlerini al
    3. İlave demirleri al
    4. Hatıl demirlerini al
    5. Kolon filizlerini al
    6. Kolon etriyelerini al
    """

    # Demir ağırlıkları (kg/m)
    DEMIR_AGIRLIKLARI = {
        6: 0.222,
        8: 0.395,
        10: 0.617,
        12: 0.888,
        14: 1.208,
        16: 1.578,
        18: 2.000,
        20: 2.466,
        22: 2.984,
        24: 3.553,
        28: 4.834,
        32: 6.313
    }

    def __init__(self, db_manager):
        """
        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager
        self.demir_listesi = []
        self.temel_adi = None  # "RADYE" veya "MÜTEMADI"

    def dxf_oku(self, dxf_path: str, proje_id: Optional[int] = None) -> Dict:
        """
        DXF dosyasından temel donatı bilgilerini okur.

        KURAL:
        1. Temel paftasını bul
        2. Kesit demirlerini al
        3. İlave demirleri al
        4. Hatıl demirlerini al
        5. Kolon filizlerini al
        6. Kolon etriyelerini al

        Returns:
            Dict: {
                'temel_adi': str,
                'kesit_demirleri': [...],
                'ilave_demirler': [...],
                'hatil_demirleri': [...],
                'kolon_filizeleri': [...],
                'kolon_etriyeleri': [...],
                'toplam_adet': int,
                'toplam_agirlik_kg': float
            }
        """
        if not Path(dxf_path).exists():
            raise FileNotFoundError(f"DXF dosyası bulunamadı: {dxf_path}")

        try:
            doc = ezdxf.readfile(dxf_path)
        except Exception as e:
            raise Exception(f"DXF dosyası okunamadı: {e}")

        msp = doc.modelspace()

        # Tüm TEXT/MTEXT entity'lerini topla
        all_texts = []
        for entity in msp.query('TEXT MTEXT'):
            if entity.dxftype() == 'TEXT':
                text = entity.dxf.text
                layer = entity.dxf.layer
                x = entity.dxf.insert.x
                y = entity.dxf.insert.y
            else:  # MTEXT
                text = entity.text
                layer = entity.dxf.layer
                x = entity.dxf.insert.x
                y = entity.dxf.insert.y

            all_texts.append({
                'text': text,
                'layer': layer,
                'x': x,
                'y': y
            })

        # Y koordinatına göre sırala (yukarıdan aşağıya)
        all_texts.sort(key=lambda t: -t['y'])

        # KURAL 1: Temel paftasını bul
        self.temel_adi = self._parse_temel_paftasi(all_texts)

        # KURAL 2: Kesit demirlerini al
        kesit_demirleri = self._parse_temel_kesit_demirleri(all_texts)

        # KURAL 3: İlave demirleri al
        ilave_demirler = self._parse_ilave_demirler(all_texts)

        # KURAL 4: Hatıl demirlerini al
        hatil_demirleri = self._parse_hatil_demirleri(all_texts)

        # KURAL 5: Kolon filizlerini al
        kolon_filizeleri = self._parse_kolon_filizeleri(all_texts)

        # KURAL 6: Kolon etriyelerini al
        kolon_etriyeleri = self._parse_kolon_etriyeleri(all_texts)

        # Tüm donatıları birleştir
        self.demir_listesi = []
        self.demir_listesi.extend(kesit_demirleri)
        self.demir_listesi.extend(ilave_demirler)
        self.demir_listesi.extend(hatil_demirleri)
        self.demir_listesi.extend(kolon_filizeleri)
        self.demir_listesi.extend(kolon_etriyeleri)

        # Toplam hesapla
        toplam_adet = sum(item['adet'] for item in self.demir_listesi)
        toplam_agirlik = sum(item['toplam_agirlik_kg'] for item in self.demir_listesi)

        return {
            'temel_adi': self.temel_adi or 'TEMEL',
            'kesit_demirleri': kesit_demirleri,
            'ilave_demirler': ilave_demirler,
            'hatil_demirleri': hatil_demirleri,
            'kolon_filizeleri': kolon_filizeleri,
            'kolon_etriyeleri': kolon_etriyeleri,
            'toplam_adet': toplam_adet,
            'toplam_agirlik_kg': toplam_agirlik,
            'tum_liste': self.demir_listesi
        }

    def _parse_temel_paftasi(self, all_texts: List[Dict]) -> Optional[str]:
        """
        KURAL 1: Temel paftasını bul

        Aranacak kelimeler:
        - RADYE TEMEL
        - MÜTEMADI TEMEL
        - TEMEL APLIKASYON
        - TEMEL PLANI

        Returns:
            str: "RADYE", "MÜTEMADI", veya "TEMEL"
        """
        temel_keywords = ['RADYE', 'MÜTEMADI', 'MÜTEMADİ', 'TEMEL']
        pafta_keywords = ['APLIKASYON', 'PLAN', 'PAFTA', 'KALIP']

        for t in all_texts:
            text_upper = t['text'].upper()

            # Temel kelimesi var mı?
            for temel_kw in temel_keywords:
                if temel_kw in text_upper:
                    # Pafta kelimesi de var mı?
                    if any(pafta_kw in text_upper for pafta_kw in pafta_keywords):
                        # RADYE mi MÜTEMADI mi?
                        if 'RADYE' in text_upper:
                            return 'RADYE'
                        elif 'MÜTEMAD' in text_upper or 'MUTEMAD' in text_upper:
                            return 'MÜTEMADI'
                        elif 'TEMEL' in text_upper:
                            return 'TEMEL'

        # Bulunamadıysa varsayılan
        return 'RADYE'

    def _parse_temel_kesit_demirleri(self, all_texts: List[Dict]) -> List[Dict]:
        """
        KURAL 2: Temelin kesit detaylarından demirleri al

        Layer'lar: PENC3, DETAIL3
        Format:
        - 6ƒ12/33 l=355 (alt)
        - 6ƒ12/33 l=400 (ust)
        - 169ƒ12/20 l=1200 (standart)
        """
        kesit_list = []

        # PENC3 ve DETAIL3 layer'larını kontrol et
        target_layers = ['PENC3', 'DETAIL3']
        target_texts = [t for t in all_texts if t['layer'] in target_layers]

        # Pattern: adet-cap-aralik-uzunluk-(opsiyonel tip)
        pattern_tipli = re.compile(r'(\d+)[ØøΦφƒ\u0192](\d+)/(\d+)\s+l=(\d+)\s*\((\w+)\)', re.IGNORECASE)
        pattern_standart = re.compile(r'(\d+)[ØøΦφƒ\u0192](\d+)/(\d+)\s+l=(\d+)')

        kesit_counter = 1

        for item in target_texts:
            text = item['text'].strip()
            layer = item['layer']

            # Alt/Üst donatı kontrolü
            match_tipli = pattern_tipli.search(text)
            if match_tipli:
                adet, cap, aralik, uzunluk, tip = match_tipli.groups()

                # Tip belirle
                if 'alt' in tip.lower():
                    donati_tipi = 'KESIT_ALT'
                elif 'ust' in tip.lower() or 'üst' in tip.lower():
                    donati_tipi = 'KESIT_UST'
                else:
                    donati_tipi = 'KESIT_DIGER'

                demir_info = self._create_demir_dict(
                    temel_tipi=self.temel_adi or 'TEMEL',
                    temel_adi=self.temel_adi or 'TEMEL',
                    pozisyon_no=None,
                    donati_tipi=donati_tipi,
                    demir_capi=int(cap),
                    demir_uzunlugu=float(uzunluk),
                    demir_adeti=int(adet),
                    aralik_cm=float(aralik),
                    dxf_layer=layer,
                    kaynak_text=text
                )
                kesit_list.append(demir_info)
                kesit_counter += 1
                continue

            # Standart donatı kontrolü
            match_standart = pattern_standart.search(text)
            if match_standart:
                adet, cap, aralik, uzunluk = match_standart.groups()

                demir_info = self._create_demir_dict(
                    temel_tipi=self.temel_adi or 'TEMEL',
                    temel_adi=self.temel_adi or 'TEMEL',
                    pozisyon_no=None,
                    donati_tipi='KESIT_STANDART',
                    demir_capi=int(cap),
                    demir_uzunlugu=float(uzunluk),
                    demir_adeti=int(adet),
                    aralik_cm=float(aralik),
                    dxf_layer=layer,
                    kaynak_text=text
                )
                kesit_list.append(demir_info)
                kesit_counter += 1

        return kesit_list

    def _parse_ilave_demirler(self, all_texts: List[Dict]) -> List[Dict]:
        """
        KURAL 3: İlave demirleri al

        İlave demir genelde "alt" etiketi ile gelir.
        Ancak zaten kesit demirlerinde "(alt)" olanları aldık.
        Bu fonksiyon ek ilave demirleri aramak için.

        Format:
        - 6ƒ12 l=340 (ilave)
        - 589ƒ12 l=112 (sehpa 1 adet/m2)
        """
        ilave_list = []

        # DETAIL3, PENC3 layer'ları
        target_layers = ['DETAIL3', 'PENC3', 'REBAR3']
        target_texts = [t for t in all_texts if t['layer'] in target_layers]

        # Pattern: sehpa demiri
        pattern_sehpa = re.compile(r'(\d+)[ØøΦφƒ\u0192](\d+)\s+l=(\d+)\s*\(sehpa', re.IGNORECASE)
        # Pattern: ilave demiri
        pattern_ilave = re.compile(r'(\d+)[ØøΦφƒ\u0192](\d+)\s+l=(\d+)\s*\(ilave\)', re.IGNORECASE)

        for item in target_texts:
            text = item['text'].strip()
            layer = item['layer']

            # Sehpa demiri
            match_sehpa = pattern_sehpa.search(text)
            if match_sehpa:
                adet, cap, uzunluk = match_sehpa.groups()
                demir_info = self._create_demir_dict(
                    temel_tipi=self.temel_adi or 'TEMEL',
                    temel_adi=self.temel_adi or 'TEMEL',
                    pozisyon_no=None,
                    donati_tipi='SEHPA',
                    demir_capi=int(cap),
                    demir_uzunlugu=float(uzunluk),
                    demir_adeti=int(adet),
                    aralik_cm=None,
                    dxf_layer=layer,
                    kaynak_text=text
                )
                ilave_list.append(demir_info)
                continue

            # İlave demiri
            match_ilave = pattern_ilave.search(text)
            if match_ilave:
                adet, cap, uzunluk = match_ilave.groups()
                demir_info = self._create_demir_dict(
                    temel_tipi=self.temel_adi or 'TEMEL',
                    temel_adi=self.temel_adi or 'TEMEL',
                    pozisyon_no=None,
                    donati_tipi='ILAVE',
                    demir_capi=int(cap),
                    demir_uzunlugu=float(uzunluk),
                    demir_adeti=int(adet),
                    aralik_cm=None,
                    dxf_layer=layer,
                    kaynak_text=text
                )
                ilave_list.append(demir_info)

        return ilave_list

    def _parse_hatil_demirleri(self, all_texts: List[Dict]) -> List[Dict]:
        """
        KURAL 4: Hatıl demirlerini al

        Layer: TABLE3
        Format:
        - BK1
        - 12ƒ10/20 l=4000 (boyuna)
        - 201ƒ12/20 l=330 (enine)
        """
        hatil_list = []

        # TABLE3 layer'ındaki metinleri filtrele
        table3_texts = [t for t in all_texts if t['layer'] == 'TABLE3']

        # Pattern: BK numarası (BK1, BK17 vb.)
        bk_pattern = re.compile(r'^BK\d+$')
        # Pattern: Donatı bilgisi
        donati_pattern = re.compile(r'(\d+)[ØøΦφƒ\u0192](\d+)/(\d+)\s+l=(\d+)')

        current_bk = None
        donati_sira = 0

        for item in table3_texts:
            text = item['text'].strip()
            layer = item['layer']

            # Hatıl numarası mı?
            match_bk = bk_pattern.match(text)
            if match_bk:
                current_bk = text  # BK1, BK2, vb.
                donati_sira = 0
                continue

            # Donatı bilgisi mi?
            if current_bk:
                match_donati = donati_pattern.search(text)
                if match_donati:
                    adet, cap, aralik, uzunluk = match_donati.groups()
                    donati_sira += 1

                    # İlk donatı boyuna, ikincisi enine
                    donati_tipi = 'HATIL_BOYUNA' if donati_sira == 1 else 'HATIL_ENINE'

                    demir_info = self._create_demir_dict(
                        temel_tipi='HATIL',
                        temel_adi=current_bk,
                        pozisyon_no=None,
                        donati_tipi=donati_tipi,
                        demir_capi=int(cap),
                        demir_uzunlugu=float(uzunluk),
                        demir_adeti=int(adet),
                        aralik_cm=float(aralik),
                        dxf_layer=layer,
                        kaynak_text=f"{current_bk} {text}"
                    )
                    hatil_list.append(demir_info)

        return hatil_list

    def _parse_kolon_filizeleri(self, all_texts: List[Dict]) -> List[Dict]:
        """
        KURAL 5: Kolon filizlerini al

        Layer: DETAIL3, TABLE3
        Format:
        - S001 (kolon adı)
        - Pozisyon ve donatı bilgisi (varsa P36-12ƒ16 formatında)
        - Veya doğrudan donatı bilgisi
        """
        kolon_list = []

        # DETAIL3 ve TABLE3 layer'larını kontrol et
        target_layers = ['DETAIL3', 'TABLE3']
        target_texts = [t for t in all_texts if t['layer'] in target_layers]

        # Pattern: S001, S002 vb. (kolon adı)
        kolon_pattern = re.compile(r'^S\d{3}$')
        # Pattern: P36-12ƒ16 (pozisyon-adet-çap)
        poz_pattern = re.compile(r'(P\d+)-(\d+)[ØøΦφƒ\u0192](\d+)')
        # Pattern: Basit donatı (2x4ƒ16)
        basit_pattern = re.compile(r'(\d+)x(\d+)[ØøΦφƒ\u0192](\d+)')

        # Y koordinatına göre sırala
        sorted_texts = sorted(target_texts, key=lambda x: -x['y'])

        i = 0
        while i < len(sorted_texts):
            text1 = sorted_texts[i]['text'].strip()

            # Kolon adı mı?
            match_kolon = kolon_pattern.match(text1)
            if match_kolon:
                kolon_adi = text1  # S001, S002, vb.

                # Sonraki 3 text'i kontrol et
                if i + 1 < len(sorted_texts):
                    text2 = sorted_texts[i + 1]['text'].strip()

                    # Pozisyon bilgisi var mı?
                    match_poz = poz_pattern.search(text2)
                    if match_poz and i + 2 < len(sorted_texts):
                        pozisyon, adet, cap = match_poz.groups()
                        text3 = sorted_texts[i + 2]['text'].strip()

                        # Uzunluk bilgisi
                        try:
                            uzunluk = float(text3)

                            demir_info = self._create_demir_dict(
                                temel_tipi='KOLON_FILIZI',
                                temel_adi=kolon_adi,
                                pozisyon_no=pozisyon,
                                donati_tipi='FILIZ',
                                demir_capi=int(cap),
                                demir_uzunlugu=uzunluk,
                                demir_adeti=int(adet),
                                aralik_cm=None,
                                dxf_layer=sorted_texts[i]['layer'],
                                kaynak_text=f"{kolon_adi} {text2} {text3}"
                            )
                            kolon_list.append(demir_info)

                            i += 3
                            continue
                        except ValueError:
                            pass

                    # Basit donatı formatı var mı? (2x4ƒ16 + uzunluk)
                    match_basit = basit_pattern.search(text2)
                    if match_basit and i + 2 < len(sorted_texts):
                        carpan, adet, cap = match_basit.groups()
                        toplam_adet = int(carpan) * int(adet)
                        text3 = sorted_texts[i + 2]['text'].strip()

                        # Uzunluk bilgisi al (muhakkak olmalı)
                        try:
                            uzunluk = float(text3)

                            demir_info = self._create_demir_dict(
                                temel_tipi='KOLON_FILIZI',
                                temel_adi=kolon_adi,
                                pozisyon_no=None,
                                donati_tipi='FILIZ',
                                demir_capi=int(cap),
                                demir_uzunlugu=uzunluk,
                                demir_adeti=toplam_adet,
                                aralik_cm=None,
                                dxf_layer=sorted_texts[i]['layer'],
                                kaynak_text=f"{kolon_adi} {text2} {text3}"
                            )
                            kolon_list.append(demir_info)

                            i += 3
                            continue
                        except ValueError:
                            pass

            i += 1

        return kolon_list

    def _parse_kolon_etriyeleri(self, all_texts: List[Dict]) -> List[Dict]:
        """
        KURAL 6: Kolon etriye tablosunu al

        Layer: PILES3
        Format:
        - S001
        - 5ƒ8/8 l=196
        - 5ƒ8/8 l=128
        - ... (bir kolon için birden fazla etriye satırı olabilir)

        Her kolon için tüm etriye satırlarını al (ezbere değil).
        """
        kolon_etriye_list = []

        # PILES3 layer'ındaki metinleri filtrele
        piles3_texts = [t for t in all_texts if t['layer'] == 'PILES3']

        if not piles3_texts:
            return kolon_etriye_list

        # Pattern: S001, S002 vb. (kolon adı)
        kolon_pattern = re.compile(r'^S\d{3}$')
        # Pattern: 5ƒ8/8 l=196 (adet-çap-aralık-uzunluk)
        etriye_pattern = re.compile(r'(\d+)[ØøΦφƒ\u0192](\d+)/(\d+)\s+l=(\d+)')

        # Y koordinatına göre sırala
        sorted_texts = sorted(piles3_texts, key=lambda x: -x['y'])

        i = 0
        while i < len(sorted_texts):
            text = sorted_texts[i]['text'].strip()

            # Kolon adı mı?
            match_kolon = kolon_pattern.match(text)
            if match_kolon:
                kolon_adi = text  # S001, S002, vb.
                j = i + 1

                # Bu kolon için tüm etriye satırlarını al
                while j < len(sorted_texts):
                    current_text = sorted_texts[j]['text'].strip()

                    # Başka bir kolon adı mı? O zaman bu kolon için etriyeler bitti
                    if kolon_pattern.match(current_text):
                        break

                    # Etriye donatı bilgisi mi?
                    match_etriye = etriye_pattern.search(current_text)
                    if match_etriye:
                        adet, cap, aralik, uzunluk = match_etriye.groups()

                        # Etriye bilgisini kaydet
                        demir_info = self._create_demir_dict(
                            temel_tipi='KOLON_FILIZI',
                            temel_adi=kolon_adi,
                            pozisyon_no=None,
                            donati_tipi='ETRIYE',
                            demir_capi=int(cap),
                            demir_uzunlugu=float(uzunluk),
                            demir_adeti=int(adet),
                            aralik_cm=float(aralik),
                            dxf_layer='PILES3',
                            kaynak_text=f"{kolon_adi} {current_text}"
                        )
                        kolon_etriye_list.append(demir_info)

                    j += 1

                i = j  # Bir sonraki kolon adından devam et
                continue

            i += 1

        return kolon_etriye_list

    def _create_demir_dict(
        self,
        temel_tipi: str,
        temel_adi: str,
        pozisyon_no: Optional[str],
        donati_tipi: str,
        demir_capi: int,
        demir_uzunlugu: float,
        demir_adeti: int,
        aralik_cm: Optional[float],
        dxf_layer: str,
        kaynak_text: str
    ) -> Dict:
        """
        Demir bilgisi dictionary'si oluşturur ve hesaplamaları yapar.
        """
        # Toplam uzunluk (cm)
        toplam_uzunluk_cm = demir_adeti * demir_uzunlugu
        # Toplam uzunluk (m)
        toplam_uzunluk_m = toplam_uzunluk_cm / 100.0
        # Birim ağırlık (kg/m)
        birim_agirlik = self.DEMIR_AGIRLIKLARI.get(demir_capi, 0)
        # Toplam ağırlık (kg)
        toplam_agirlik_kg = toplam_uzunluk_m * birim_agirlik

        return {
            'temel_tipi': temel_tipi,
            'temel_adi': temel_adi,
            'pozisyon_no': pozisyon_no,
            'donati_tipi': donati_tipi,
            'cap': demir_capi,
            'uzunluk_cm': demir_uzunlugu,
            'adet': demir_adeti,
            'aralik_cm': aralik_cm,
            'toplam_uzunluk_cm': toplam_uzunluk_cm,
            'toplam_uzunluk_m': toplam_uzunluk_m,
            'birim_agirlik_kg_m': birim_agirlik,
            'toplam_agirlik_kg': toplam_agirlik_kg,
            'dxf_layer': dxf_layer,
            'kaynak_text': kaynak_text
        }

    def veritabanina_kaydet(self, proje_id: int, silip_yeniden_kaydet: bool = True) -> int:
        """
        Parse edilmiş demir listesini veritabanına kaydeder.

        Args:
            proje_id: Proje ID
            silip_yeniden_kaydet: True ise önce eski kayıtları sil

        Returns:
            int: Kaydedilen kayıt sayısı
        """
        if not self.demir_listesi:
            return 0

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Eski kayıtları sil
            if silip_yeniden_kaydet:
                cursor.execute("""
                    DELETE FROM temel_demir_listesi WHERE proje_id = ?
                """, (proje_id,))
                cursor.execute("""
                    DELETE FROM temel_demir_ozet WHERE proje_id = ?
                """, (proje_id,))

            # Yeni kayıtları ekle
            kayit_sayisi = 0
            for demir in self.demir_listesi:
                cursor.execute("""
                    INSERT INTO temel_demir_listesi (
                        proje_id, temel_tipi, temel_adi, pozisyon_no,
                        donati_tipi, demir_capi, demir_uzunlugu, demir_adeti,
                        aralik_cm, toplam_uzunluk, toplam_uzunluk_m,
                        birim_agirlik, toplam_agirlik, kaynak, dxf_layer,
                        olusturma_tarihi
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    proje_id,
                    demir['temel_tipi'],
                    demir['temel_adi'],
                    demir['pozisyon_no'],
                    demir['donati_tipi'],
                    demir['cap'],
                    demir['uzunluk_cm'],
                    demir['adet'],
                    demir['aralik_cm'],
                    demir['toplam_uzunluk_cm'],
                    demir['toplam_uzunluk_m'],
                    demir['birim_agirlik_kg_m'],
                    demir['toplam_agirlik_kg'],
                    'DXF',
                    demir['dxf_layer'],
                    datetime.now().isoformat()
                ))
                kayit_sayisi += 1

            # Özet tabloyu oluştur
            self._ozet_olustur(cursor, proje_id)

            conn.commit()

        return kayit_sayisi

    def _ozet_olustur(self, cursor, proje_id: int):
        """
        Çapa göre gruplandırılmış özet oluşturur.
        """
        # Çapa göre topla
        cursor.execute("""
            SELECT
                demir_capi,
                SUM(toplam_uzunluk_m) as toplam_uzunluk,
                SUM(toplam_agirlik) as toplam_agirlik,
                SUM(demir_adeti) as toplam_adet
            FROM temel_demir_listesi
            WHERE proje_id = ?
            GROUP BY demir_capi
            ORDER BY demir_capi
        """, (proje_id,))

        ozetler = cursor.fetchall()

        for ozet in ozetler:
            cap = ozet[0]
            uzunluk_m = ozet[1]
            agirlik_kg = ozet[2]
            adet = ozet[3]
            agirlik_ton = agirlik_kg / 1000.0

            cursor.execute("""
                INSERT INTO temel_demir_ozet (
                    proje_id, demir_capi, toplam_uzunluk_m,
                    toplam_agirlik_kg, toplam_agirlik_ton, adet_sayisi,
                    olusturma_tarihi
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                proje_id, cap, uzunluk_m, agirlik_kg, agirlik_ton,
                adet, datetime.now().isoformat()
            ))

    def get_ozet(self, proje_id: int) -> List[Dict]:
        """
        Proje için özet bilgilerini getirir.

        Returns:
            List[Dict]: Çapa göre özet listesi
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    demir_capi, toplam_uzunluk_m, toplam_agirlik_kg,
                    toplam_agirlik_ton, adet_sayisi
                FROM temel_demir_ozet
                WHERE proje_id = ?
                ORDER BY demir_capi
            """, (proje_id,))

            rows = cursor.fetchall()

            ozet_list = []
            for row in rows:
                ozet_list.append({
                    'cap': row[0],
                    'toplam_uzunluk_m': row[1],
                    'toplam_agirlik_kg': row[2],
                    'toplam_agirlik_ton': row[3],
                    'adet_sayisi': row[4]
                })

            return ozet_list

    def get_detay_liste(self, proje_id: int, temel_tipi: Optional[str] = None) -> List[Dict]:
        """
        Detaylı demir listesini getirir.

        Args:
            proje_id: Proje ID
            temel_tipi: Filtre (opsiyonel)

        Returns:
            List[Dict]: Detaylı liste
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            if temel_tipi:
                cursor.execute("""
                    SELECT
                        id, temel_tipi, temel_adi, pozisyon_no, donati_tipi,
                        demir_capi, demir_uzunlugu, demir_adeti, aralik_cm,
                        toplam_uzunluk, toplam_uzunluk_m, birim_agirlik,
                        toplam_agirlik, dxf_layer
                    FROM temel_demir_listesi
                    WHERE proje_id = ? AND temel_tipi = ?
                    ORDER BY temel_adi, donati_tipi
                """, (proje_id, temel_tipi))
            else:
                cursor.execute("""
                    SELECT
                        id, temel_tipi, temel_adi, pozisyon_no, donati_tipi,
                        demir_capi, demir_uzunlugu, demir_adeti, aralik_cm,
                        toplam_uzunluk, toplam_uzunluk_m, birim_agirlik,
                        toplam_agirlik, dxf_layer
                    FROM temel_demir_listesi
                    WHERE proje_id = ?
                    ORDER BY temel_tipi, temel_adi, donati_tipi
                """, (proje_id,))

            rows = cursor.fetchall()

            detay_list = []
            for row in rows:
                detay_list.append({
                    'id': row[0],
                    'temel_tipi': row[1],
                    'temel_adi': row[2],
                    'pozisyon_no': row[3],
                    'donati_tipi': row[4],
                    'cap': row[5],
                    'uzunluk_cm': row[6],
                    'adet': row[7],
                    'aralik_cm': row[8],
                    'toplam_uzunluk_cm': row[9],
                    'toplam_uzunluk_m': row[10],
                    'birim_agirlik_kg_m': row[11],
                    'toplam_agirlik_kg': row[12],
                    'dxf_layer': row[13]
                })

            return detay_list
