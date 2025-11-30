"""
Malzeme Hesaplama Yöneticisi
Poz bazlı malzeme hesaplamaları için core modül
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from app.core.database import DatabaseManager
from app.core.calculator import Calculator


class MaterialCalculator:
    """
    Malzeme hesaplama yöneticisi.
    
    Poz ve miktar bilgilerine göre gereken malzemeleri hesaplar.
    """
    
    def __init__(self, db: DatabaseManager) -> None:
        """
        Malzeme hesaplama yöneticisini başlat.
        
        Args:
            db: DatabaseManager instance
        """
        self.db = db
        self.calculator = Calculator()
    
    def calculate_materials_for_project(self, proje_id: int, 
                                      fire_orani_override: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Proje için toplam malzeme ihtiyacını hesapla.
        Poz bazlı otomatik fire oranları kullanılır (Literatür/Kitap değerleri).
        
        Args:
            proje_id: Proje ID'si
            fire_orani_override: Manuel fire oranı (None ise poz bazlı kullanılır)
            
        Returns:
            List[Dict]: Toplam malzeme listesi
        """
        # Projeye ait metraj kalemlerini getir
        metraj_kalemleri = self.db.get_project_metraj(proje_id)
        
        if not metraj_kalemleri:
            return []
        
        # Her kalem için malzeme hesapla
        all_materials = []
        
        for kalem in metraj_kalemleri:
            poz_no = kalem.get('poz_no')
            miktar = kalem.get('miktar', 0)
            
            if not poz_no or miktar <= 0:
                continue
            
            # Poz ID'sini bul
            poz = self.db.get_poz(poz_no)
            if not poz:
                continue
            
            poz_id = poz['id']
            
            # Fire oranını belirle: Override varsa onu kullan, yoksa poz bazlı
            if fire_orani_override is not None:
                fire_orani = fire_orani_override
            else:
                # Poz bazlı otomatik fire oranı (veritabanından)
                fire_orani = poz.get('fire_orani', 0.05)  # Varsayılan %5
            
            # Poz için formülleri getir
            formuller = self.db.get_poz_formulleri(poz_id)
            
            if not formuller:
                continue
            
            # Malzemeleri hesapla
            materials = self.calculator.calculate_materials_for_poz(
                miktar, formuller, fire_orani
            )
            
            # Poz bilgisini ekle
            for material in materials:
                material['poz_no'] = poz_no
                material['poz_tanim'] = kalem.get('tanim', '')
                material['poz_miktar'] = miktar
                material['poz_birim'] = kalem.get('birim', '')
                material['poz_fire_orani'] = fire_orani  # Kullanılan fire oranı
            
            all_materials.append(materials)
        
        # Tüm malzemeleri birleştir
        aggregated = self.calculator.aggregate_materials(all_materials)
        
        return aggregated
    
    def calculate_materials_for_poz_no(self, poz_no: str, miktar: float, 
                                      fire_orani_override: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Belirli bir poz için malzeme ihtiyacını hesapla.
        
        Args:
            poz_no: Poz numarası
            miktar: Poz miktarı
            fire_orani_override: Manuel fire oranı (None ise poz bazlı kullanılır)
            
        Returns:
            List[Dict]: Malzeme listesi
        """
        # Poz ID'sini bul
        poz = self.db.get_poz(poz_no)
        if not poz:
            return []
        
        poz_id = poz['id']
        
        # Fire oranını belirle
        if fire_orani_override is not None:
            fire_orani = fire_orani_override
        else:
            fire_orani = poz.get('fire_orani', 0.05)
        
        # Formülleri getir
        formuller = self.db.get_poz_formulleri(poz_id)
        
        if not formuller:
            return []
        
        # Hesapla
        materials = self.calculator.calculate_materials_for_poz(
            miktar, formuller, fire_orani
        )
        
        return materials
    
    def get_material_summary(self, proje_id: int, 
                            fire_orani_override: Optional[float] = None) -> Dict[str, Any]:
        """
        Proje için malzeme özeti getir.
        
        Args:
            proje_id: Proje ID'si
            fire_orani_override: Manuel fire oranı (None ise poz bazlı kullanılır)
            
        Returns:
            Dict: Özet bilgiler
        """
        materials = self.calculate_materials_for_project(proje_id, fire_orani_override)
        
        # Kategori bazlı grupla
        by_category = {}
        total_items = 0
        
        for material in materials:
            kategori = material.get('formul_tipi', 'Diğer')
            if kategori not in by_category:
                by_category[kategori] = []
            by_category[kategori].append(material)
            total_items += 1
        
        return {
            'toplam_malzeme_cesidi': len(materials),
            'toplam_kalem_sayisi': total_items,
            'kategori_bazli': by_category,
            'malzemeler': materials
        }
    
    def convert_unit(self, value: float, from_unit: str, to_unit: str, 
                    malzeme_id: Optional[int] = None) -> Optional[float]:
        """
        Birim dönüşümü yap.
        
        Args:
            value: Dönüştürülecek değer
            from_unit: Kaynak birim
            to_unit: Hedef birim
            malzeme_id: Malzeme ID'si (opsiyonel, malzeme bazlı dönüşüm için)
            
        Returns:
            Optional[float]: Dönüştürülmüş değer veya None
        """
        if from_unit == to_unit:
            return value
        
        # Önce veritabanından dönüşüm katsayısını ara
        katsayi = self.db.get_birim_donusum(from_unit, to_unit, malzeme_id)
        
        if katsayi is not None:
            return float(Decimal(str(value)) * Decimal(str(katsayi)))
        
        # Standart dönüşümler (malzeme bağımsız)
        standard_conversions = {
            # Ağırlık
            ('kg', 'ton'): 0.001,
            ('ton', 'kg'): 1000.0,
            ('kg', 'g'): 1000.0,
            ('g', 'kg'): 0.001,
            
            # Hacim
            ('m³', 'lt'): 1000.0,
            ('lt', 'm³'): 0.001,
            ('m³', 'dm³'): 1000.0,
            ('dm³', 'm³'): 0.001,
            
            # Alan
            ('m²', 'cm²'): 10000.0,
            ('cm²', 'm²'): 0.0001,
            
            # Uzunluk
            ('m', 'cm'): 100.0,
            ('cm', 'm'): 0.01,
            ('m', 'mm'): 1000.0,
            ('mm', 'm'): 0.001,
        }
        
        key = (from_unit, to_unit)
        if key in standard_conversions:
            katsayi = standard_conversions[key]
            return float(Decimal(str(value)) * Decimal(str(katsayi)))
        
        return None
    
    def convert_material_units(self, materials: List[Dict[str, Any]], 
                               target_unit: str) -> List[Dict[str, Any]]:
        """
        Malzeme listesindeki birimleri dönüştür.
        
        Args:
            materials: Malzeme listesi
            target_unit: Hedef birim
            
        Returns:
            List[Dict]: Birimleri dönüştürülmüş malzeme listesi
        """
        converted = []
        
        for material in materials:
            malzeme_id = material.get('malzeme_id')
            current_unit = material.get('birim', '')
            miktar = material.get('miktar', 0)
            
            if current_unit == target_unit:
                converted.append(material)
                continue
            
            # Birim dönüşümü yap
            converted_value = self.convert_unit(miktar, current_unit, target_unit, malzeme_id)
            
            if converted_value is not None:
                new_material = material.copy()
                new_material['miktar'] = converted_value
                new_material['birim'] = target_unit
                converted.append(new_material)
            else:
                # Dönüşüm yapılamazsa orijinal birimi koru
                converted.append(material)
        
        return converted

