"""
Malzeme Hesaplama Yöneticisi
Poz bazlı malzeme hesaplamaları için core modül
"""

from typing import List, Dict, Any, Optional, Literal
from decimal import Decimal
import math
from app.core.database import DatabaseManager
from app.core.calculator import Calculator


# ============================================================================
# BOYA MALİYET HESAPLAMA FONKSİYONU (GELİŞMİŞ)
# ============================================================================

def hesapla_boya_maliyet_gelismis(
    boyanacak_alan_m2: float,
    kat_sayisi: int = 2,
    astar_yapilacak_mi: bool = True,
    kova_birim_fiyat: float = 0.0,
    astar_kova_fiyat: float = 0.0,
    ekip_gunluk_ucret: float = 0.0,
    fire_orani: float = 0.05,
    verim_kaynagi: Literal['piyasa', 'csb_resmi', 'manuel'] = 'piyasa',
    manuel_hiz: Optional[float] = None
) -> Dict[str, Any]:
    """
    Gelişmiş boya maliyet hesaplama fonksiyonu.

    Kat sayısı ve astar durumuna göre dinamik hesaplama yapar.

    Args:
        boyanacak_alan_m2: Boyanacak toplam alan (m²)
        kat_sayisi: Boya kat sayısı (1 veya 2, varsayılan: 2)
        astar_yapilacak_mi: Astar uygulanacak mı (True/False, varsayılan: True)
        kova_birim_fiyat: 20 Kg'lık boya kovası fiyatı (TL)
        astar_kova_fiyat: 20 Kg'lık astar kovası fiyatı (TL)
        ekip_gunluk_ucret: 1 Usta + 1 Yardımcı günlük ücret (TL)
        fire_orani: Fire oranı (Örn: 0.05 = %5)
        verim_kaynagi: Verim kaynağı ('piyasa', 'csb_resmi', 'manuel')
        manuel_hiz: Manuel hız (m²/gün) - sadece verim_kaynagi='manuel' ise kullanılır

    Returns:
        Dict: Hesaplama sonuçları
            - uygulanan_kat_sayisi: int
            - astar_durumu: bool
            - tahmini_sure_gun: int
            - gereken_boya_kova_adet: int
            - gereken_astar_kova_adet: int
            - toplam_boya_kg: float
            - toplam_astar_kg: float
            - toplam_iscilik_tl: float
            - toplam_malzeme_tl: float
            - genel_toplam_maliyet_tl: float

    Raises:
        ValueError: Geçersiz parametre değerleri için

    Example:
        >>> sonuc = hesapla_boya_maliyet_gelismis(
        ...     boyanacak_alan_m2=500.0,
        ...     kat_sayisi=2,
        ...     astar_yapilacak_mi=True,
        ...     kova_birim_fiyat=1500.0,
        ...     astar_kova_fiyat=800.0,
        ...     ekip_gunluk_ucret=3500.0,
        ...     fire_orani=0.05,
        ...     verim_kaynagi='piyasa'
        ... )
        >>> print(sonuc['genel_toplam_maliyet_tl'])
    """

    # =========================================================================
    # 1. GİRDİ VALİDASYONU
    # =========================================================================
    if boyanacak_alan_m2 <= 0:
        raise ValueError("Boyanacak alan 0'dan büyük olmalıdır.")

    if kat_sayisi not in (1, 2):
        raise ValueError("Kat sayısı sadece 1 veya 2 olabilir.")

    if fire_orani < 0 or fire_orani > 1:
        raise ValueError("Fire oranı 0 ile 1 arasında olmalıdır.")

    if verim_kaynagi == 'manuel' and (manuel_hiz is None or manuel_hiz <= 0):
        raise ValueError("Manuel verim kaynağı seçildiğinde geçerli bir manuel_hiz değeri gereklidir.")

    # =========================================================================
    # 2. SABİT DEĞERLER
    # =========================================================================
    BOYA_SARFIYAT_KG_M2 = 0.150  # Her kat için m² başına kg
    ASTAR_SARFIYAT_KG_M2 = 0.150  # m² başına kg
    KOVA_AGIRLIK_KG = 20.0  # 20 Kg'lık kova

    # Baz hızlar (2 kat boya + astar için, m²/gün)
    BAZ_HIZLAR = {
        'piyasa': 90.0,
        'csb_resmi': 45.0,
        'manuel': manuel_hiz if manuel_hiz else 90.0
    }

    # =========================================================================
    # 3. MALZEME SARFIYATI HESABI
    # =========================================================================

    # A. Boya Miktarı (kat sayısına göre)
    # Formül: (alan * kat_sayisi * sarfiyat) * (1 + fire_orani)
    toplam_boya_kg = (boyanacak_alan_m2 * kat_sayisi * BOYA_SARFIYAT_KG_M2) * (1 + fire_orani)

    # B. Astar Miktarı (sadece astar seçildiyse)
    if astar_yapilacak_mi:
        toplam_astar_kg = (boyanacak_alan_m2 * ASTAR_SARFIYAT_KG_M2) * (1 + fire_orani)
    else:
        toplam_astar_kg = 0.0

    # C. Kova Çevrimi (yukarı yuvarlama)
    gereken_boya_kova_adet = math.ceil(toplam_boya_kg / KOVA_AGIRLIK_KG)
    gereken_astar_kova_adet = math.ceil(toplam_astar_kg / KOVA_AGIRLIK_KG) if astar_yapilacak_mi else 0

    # =========================================================================
    # 4. İŞÇİLİK HIZI HESABI (Dinamik Çarpanlarla)
    # =========================================================================

    # Baz hızı al
    baz_hiz = BAZ_HIZLAR.get(verim_kaynagi, BAZ_HIZLAR['piyasa'])

    # Hız çarpanını başlat
    hiz_carpani = 1.0

    # Kat sayısı çarpanı: 1 kat seçilirse iş daha hızlı biter (1.5x)
    if kat_sayisi == 1:
        hiz_carpani *= 1.5

    # Astar durumu çarpanı: Astar yoksa ekstra %10 hız artışı (1.1x)
    if not astar_yapilacak_mi:
        hiz_carpani *= 1.1

    # Efektif hız (günlük tamamlanan m²)
    efektif_hiz = baz_hiz * hiz_carpani

    # =========================================================================
    # 5. SÜRE VE MALİYET HESABI
    # =========================================================================

    # A. Tahmini süre (gün) - yukarı yuvarlama
    tahmini_sure_gun = math.ceil(boyanacak_alan_m2 / efektif_hiz)

    # B. İşçilik maliyeti
    toplam_iscilik_tl = tahmini_sure_gun * ekip_gunluk_ucret

    # C. Malzeme maliyeti
    boya_maliyeti = gereken_boya_kova_adet * kova_birim_fiyat
    astar_maliyeti = gereken_astar_kova_adet * astar_kova_fiyat
    toplam_malzeme_tl = boya_maliyeti + astar_maliyeti

    # D. Genel toplam
    genel_toplam_maliyet_tl = toplam_iscilik_tl + toplam_malzeme_tl

    # =========================================================================
    # 6. SONUÇ DÖNDÜR
    # =========================================================================
    return {
        # Uygulama parametreleri
        'uygulanan_kat_sayisi': kat_sayisi,
        'astar_durumu': astar_yapilacak_mi,

        # Zaman
        'tahmini_sure_gun': tahmini_sure_gun,

        # Malzeme miktarları
        'gereken_boya_kova_adet': gereken_boya_kova_adet,
        'gereken_astar_kova_adet': gereken_astar_kova_adet,
        'toplam_boya_kg': round(toplam_boya_kg, 2),
        'toplam_astar_kg': round(toplam_astar_kg, 2),

        # Maliyetler
        'toplam_iscilik_tl': round(toplam_iscilik_tl, 2),
        'toplam_malzeme_tl': round(toplam_malzeme_tl, 2),
        'genel_toplam_maliyet_tl': round(genel_toplam_maliyet_tl, 2),

        # Detay bilgileri (opsiyonel - raporlama için)
        '_detay': {
            'boyanacak_alan_m2': boyanacak_alan_m2,
            'fire_orani': fire_orani,
            'verim_kaynagi': verim_kaynagi,
            'baz_hiz_m2_gun': baz_hiz,
            'hiz_carpani': round(hiz_carpani, 2),
            'efektif_hiz_m2_gun': round(efektif_hiz, 2),
            'boya_sarfiyat_kg_m2': BOYA_SARFIYAT_KG_M2,
            'astar_sarfiyat_kg_m2': ASTAR_SARFIYAT_KG_M2,
            'kova_agirlik_kg': KOVA_AGIRLIK_KG,
            'kova_birim_fiyat': kova_birim_fiyat,
            'astar_kova_fiyat': astar_kova_fiyat,
            'ekip_gunluk_ucret': ekip_gunluk_ucret,
            'boya_maliyeti_tl': round(boya_maliyeti, 2),
            'astar_maliyeti_tl': round(astar_maliyeti, 2)
        }
    }


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

