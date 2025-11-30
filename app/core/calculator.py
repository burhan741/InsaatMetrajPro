"""
Hesaplama Motoru
Metraj ve maliyet hesaplamaları için core modül
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal, ROUND_HALF_UP


class Calculator:
    """
    Metraj ve maliyet hesaplama sınıfı.
    
    Tüm matematiksel işlemler Decimal kullanarak yüksek hassasiyetle yapılır.
    """
    
    @staticmethod
    def calculate_total(quantity: float, unit_price: float) -> float:
        """
        Toplam tutarı hesapla.
        
        Args:
            quantity: Miktar
            unit_price: Birim fiyat
            
        Returns:
            float: Toplam tutar (2 ondalık basamak)
        """
        qty = Decimal(str(quantity))
        price = Decimal(str(unit_price))
        total = qty * price
        return float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        
    @staticmethod
    def calculate_project_total(metraj_items: List[Dict[str, Any]]) -> float:
        """
        Proje toplam maliyetini hesapla.
        
        Args:
            metraj_items: Metraj kalemleri listesi
            
        Returns:
            float: Toplam maliyet
        """
        total = Decimal('0')
        for item in metraj_items:
            quantity = Decimal(str(item.get('miktar', 0)))
            unit_price = Decimal(str(item.get('birim_fiyat', 0)))
            total += quantity * unit_price
            
        return float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        
    @staticmethod
    def calculate_kdv(amount: float, kdv_rate: float = 20.0) -> float:
        """
        KDV hesapla.
        
        Args:
            amount: Tutar
            kdv_rate: KDV oranı (varsayılan %20)
            
        Returns:
            float: KDV tutarı
        """
        amount_decimal = Decimal(str(amount))
        rate = Decimal(str(kdv_rate)) / Decimal('100')
        kdv = amount_decimal * rate
        return float(kdv.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        
    @staticmethod
    def calculate_with_kdv(amount: float, kdv_rate: float = 20.0) -> Dict[str, float]:
        """
        KDV dahil ve hariç tutarları hesapla.
        
        Args:
            amount: KDV hariç tutar
            kdv_rate: KDV oranı
            
        Returns:
            Dict: {'kdv_haric', 'kdv', 'kdv_dahil'}
        """
        kdv_haric = Decimal(str(amount))
        kdv = Calculator.calculate_kdv(amount, kdv_rate)
        kdv_decimal = Decimal(str(kdv))
        kdv_dahil = kdv_haric + kdv_decimal
        
        return {
            'kdv_haric': float(kdv_haric),
            'kdv': kdv,
            'kdv_dahil': float(kdv_dahil.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        }
        
    @staticmethod
    def compare_taseron_offers(offers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Taşeron tekliflerini karşılaştır.
        
        Args:
            offers: Taşeron teklifleri listesi
            
        Returns:
            Dict: Karşılaştırma sonuçları
        """
        if not offers:
            return {
                'en_dusuk': None,
                'en_yuksek': None,
                'ortalama': 0.0,
                'firma_sayisi': 0
            }
            
        totals = [offer.get('toplam', 0) for offer in offers if offer.get('toplam', 0) > 0]
        
        if not totals:
            return {
                'en_dusuk': None,
                'en_yuksek': None,
                'ortalama': 0.0,
                'firma_sayisi': len(offers)
            }
            
        totals_decimal = [Decimal(str(t)) for t in totals]
        en_dusuk = min(totals_decimal)
        en_yuksek = max(totals_decimal)
        ortalama = sum(totals_decimal) / Decimal(str(len(totals_decimal)))
        
        # En düşük ve en yüksek teklifleri bul
        en_dusuk_offer = next(
            (o for o in offers if Decimal(str(o.get('toplam', 0))) == en_dusuk),
            None
        )
        en_yuksek_offer = next(
            (o for o in offers if Decimal(str(o.get('toplam', 0))) == en_yuksek),
            None
        )
        
        return {
            'en_dusuk': {
                'firma': en_dusuk_offer.get('firma_adi', '') if en_dusuk_offer else '',
                'tutar': float(en_dusuk)
            },
            'en_yuksek': {
                'firma': en_yuksek_offer.get('firma_adi', '') if en_yuksek_offer else '',
                'tutar': float(en_yuksek)
            },
            'ortalama': float(ortalama.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'firma_sayisi': len(offers)
        }
    
    @staticmethod
    def calculate_materials_for_poz(poz_miktar: float, formuller: List[Dict[str, Any]], 
                                    fire_orani: float = 0.0, 
                                    sub_formulas: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> List[Dict[str, Any]]:
        """
        Poz miktarına göre gereken malzemeleri hesapla.
        Alt formüller (harç, beton karışımı) desteklenir.
        
        Args:
            poz_miktar: Poz miktarı (örn: 100 m²)
            formuller: Poz için malzeme formülleri listesi
            fire_orani: Fire/atık oranı (0.05 = %5)
            sub_formulas: Alt formüller (formul_tipi -> formül listesi)
            
        Returns:
            List[Dict]: Hesaplanan malzeme listesi
        """
        materials = []
        poz_decimal = Decimal(str(poz_miktar))
        fire_katsayi = Decimal('1') + Decimal(str(fire_orani))
        
        if sub_formulas is None:
            sub_formulas = {}
        
        for formul in formuller:
            miktar = Decimal(str(formul.get('miktar', 0)))
            birim = formul.get('birim', '')
            malzeme_adi = formul.get('malzeme_adi', '')
            malzeme_birim = formul.get('malzeme_birim', birim)
            formul_tipi = formul.get('formul_tipi', 'direkt')
            
            # Alt formül kontrolü (harç, beton_karisimi vb.)
            if formul_tipi in sub_formulas:
                # Alt formülün miktarını hesapla
                alt_formul_miktar = poz_decimal * miktar * fire_katsayi
                
                # Alt formülün içindeki malzemeleri hesapla
                alt_formul_listesi = sub_formulas[formul_tipi]
                for alt_formul in alt_formul_listesi:
                    alt_miktar = Decimal(str(alt_formul.get('miktar', 0)))
                    alt_malzeme_adi = alt_formul.get('malzeme_adi', '')
                    alt_birim = alt_formul.get('birim', '')
                    
                    # Alt formül miktarı × alt formül oranı
                    toplam_alt_miktar = alt_formul_miktar * alt_miktar
                    
                    materials.append({
                        'malzeme_id': alt_formul.get('malzeme_id'),
                        'malzeme_adi': alt_malzeme_adi,
                        'miktar': float(toplam_alt_miktar.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                        'birim': alt_birim,
                        'formul_tipi': 'direkt',
                        'aciklama': f"{malzeme_adi} ({formul_tipi}) içinde"
                    })
            else:
                # Normal direkt formül
                toplam_miktar = poz_decimal * miktar * fire_katsayi
                
                materials.append({
                    'malzeme_id': formul.get('malzeme_id'),
                    'malzeme_adi': malzeme_adi,
                    'miktar': float(toplam_miktar.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                    'birim': malzeme_birim,
                    'formul_tipi': formul_tipi,
                    'aciklama': formul.get('aciklama', '')
                })
            
        return materials
    
    @staticmethod
    def aggregate_materials(material_lists: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Birden fazla poz için hesaplanan malzemeleri birleştir.
        Aynı malzemeler toplanır.
        
        Args:
            material_lists: Malzeme listelerinin listesi
            
        Returns:
            List[Dict]: Birleştirilmiş malzeme listesi
        """
        aggregated = {}
        
        for material_list in material_lists:
            for material in material_list:
                malzeme_id = material.get('malzeme_id')
                malzeme_adi = material.get('malzeme_adi', '')
                birim = material.get('birim', '')
                
                # Key: malzeme_id veya malzeme_adi + birim
                key = f"{malzeme_id}_{birim}" if malzeme_id else f"{malzeme_adi}_{birim}"
                
                if key in aggregated:
                    # Mevcut malzemeye ekle
                    mevcut_miktar = Decimal(str(aggregated[key]['miktar']))
                    yeni_miktar = Decimal(str(material.get('miktar', 0)))
                    toplam = mevcut_miktar + yeni_miktar
                    aggregated[key]['miktar'] = float(toplam.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                else:
                    # Yeni malzeme ekle
                    aggregated[key] = {
                        'malzeme_id': malzeme_id,
                        'malzeme_adi': malzeme_adi,
                        'miktar': material.get('miktar', 0),
                        'birim': birim,
                        'formul_tipi': material.get('formul_tipi', 'direkt')
                    }
        
        # Listeye dönüştür ve sırala
        result = list(aggregated.values())
        result.sort(key=lambda x: (x.get('malzeme_adi', ''), x.get('birim', '')))
        
        return result

