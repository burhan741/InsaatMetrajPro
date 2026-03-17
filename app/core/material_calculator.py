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
    """Gelişmiş boya maliyet hesaplama fonksiyonu."""
    # 1. GİRDİ VALİDASYONU
    if boyanacak_alan_m2 <= 0:
        raise ValueError("Boyanacak alan 0'dan büyük olmalıdır.")
    if kat_sayisi not in (1, 2):
        raise ValueError("Kat sayısı sadece 1 veya 2 olabilir.")
    if fire_orani < 0 or fire_orani > 1:
        raise ValueError("Fire oranı 0 ile 1 arasında olmalıdır.")
    if verim_kaynagi == 'manuel' and (manuel_hiz is None or manuel_hiz <= 0):
        raise ValueError("Manuel verim kaynağı seçildiğinde geçerli bir manuel_hiz değeri gereklidir.")

    # 2. SABİT DEĞERLER
    BOYA_SARFIYAT_KG_M2 = 0.150
    ASTAR_SARFIYAT_KG_M2 = 0.150
    KOVA_AGIRLIK_KG = 20.0
    BAZ_HIZLAR = {
        'piyasa': 90.0,
        'csb_resmi': 45.0,
        'manuel': manuel_hiz if manuel_hiz else 90.0
    }

    # 3. MALZEME SARFIYATI HESABI
    toplam_boya_kg = (boyanacak_alan_m2 * kat_sayisi * BOYA_SARFIYAT_KG_M2) * (1 + fire_orani)
    if astar_yapilacak_mi:
        toplam_astar_kg = (boyanacak_alan_m2 * ASTAR_SARFIYAT_KG_M2) * (1 + fire_orani)
    else:
        toplam_astar_kg = 0.0
    gereken_boya_kova_adet = math.ceil(toplam_boya_kg / KOVA_AGIRLIK_KG)
    gereken_astar_kova_adet = math.ceil(toplam_astar_kg / KOVA_AGIRLIK_KG) if astar_yapilacak_mi else 0

    # 4. İŞÇİLİK HIZI HESABI
    baz_hiz = BAZ_HIZLAR.get(verim_kaynagi, BAZ_HIZLAR['piyasa'])
    hiz_carpani = 1.0
    if kat_sayisi == 1:
        hiz_carpani *= 1.5
    if not astar_yapilacak_mi:
        hiz_carpani *= 1.1
    efektif_hiz = baz_hiz * hiz_carpani

    # 5. SÜRE VE MALİYET HESABI
    tahmini_sure_gun = math.ceil(boyanacak_alan_m2 / efektif_hiz)
    toplam_iscilik_tl = tahmini_sure_gun * ekip_gunluk_ucret
    boya_maliyeti = gereken_boya_kova_adet * kova_birim_fiyat
    astar_maliyeti = gereken_astar_kova_adet * astar_kova_fiyat
    toplam_malzeme_tl = boya_maliyeti + astar_maliyeti
    genel_toplam_maliyet_tl = toplam_iscilik_tl + toplam_malzeme_tl

    # 6. SONUÇ DÖNDÜR
    return {
        'uygulanan_kat_sayisi': kat_sayisi,
        'astar_durumu': astar_yapilacak_mi,
        'tahmini_sure_gun': tahmini_sure_gun,
        'gereken_boya_kova_adet': gereken_boya_kova_adet,
        'gereken_astar_kova_adet': gereken_astar_kova_adet,
        'toplam_boya_kg': round(toplam_boya_kg, 2),
        'toplam_astar_kg': round(toplam_astar_kg, 2),
        'toplam_iscilik_tl': round(toplam_iscilik_tl, 2),
        'toplam_malzeme_tl': round(toplam_malzeme_tl, 2),
        'genel_toplam_maliyet_tl': round(genel_toplam_maliyet_tl, 2),
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

    def calculate_materials_for_project(
        self,
        proje_id: int,
        fire_orani_override: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Proje için toplam malzeme ihtiyacını hesapla.
        Poz bazlı ve serbest piyasa kalemlerini birlikte işler.
        """
        from app.data.malzeme_formulleri import BASIC_MATERIALS
        _fiyat_map = {m['ad']: m['birim_fiyat'] for m in BASIC_MATERIALS}
        _kat_map = {m['ad']: m.get('kategori', 'Diğer') for m in BASIC_MATERIALS}

        metraj_kalemleri = self.db.get_project_metraj(proje_id)
        if not metraj_kalemleri:
            return []

        all_materials: list = []
        sp_fiyat_tablosu: dict = {}

        for kalem in metraj_kalemleri:
            poz_no = kalem.get('poz_no')
            miktar = kalem.get('miktar', 0)
            if miktar <= 0:
                continue
            if not poz_no:
                fire_orani = fire_orani_override if fire_orani_override is not None else 0.0
                birim_fiyat = float(kalem.get('birim_fiyat', 0) or 0)
                tanim = kalem.get('tanim', '') or 'Bilinmeyen Kalem'
                kategori = kalem.get('kategori', '') or 'Serbest Piyasa'
                miktar_fire = round(miktar * (1.0 + fire_orani), 2)
                sp_fiyat_tablosu[tanim] = birim_fiyat
                all_materials.append([{
                    'malzeme_id': None,
                    'malzeme_adi': tanim,
                    'miktar': miktar_fire,
                    'birim': kalem.get('birim', 'adet'),
                    'birim_fiyat': birim_fiyat,
                    'formul_tipi': 'serbest_piyasa',
                    'poz_no': None,
                    'poz_tanim': tanim,
                    'poz_miktar': miktar,
                    'poz_birim': kalem.get('birim', ''),
                    'poz_fire_orani': fire_orani,
                    'malzeme_kategori': kategori,
                }])
                continue
            poz = self.db.get_poz(poz_no)
            if not poz:
                continue
            poz_id = poz['id']
            fire_orani = (
                fire_orani_override if fire_orani_override is not None
                else poz.get('fire_orani', 0.05)
            )
            formuller = self.db.get_poz_formulleri(poz_id)
            if not formuller:
                continue
            materials = self.calculator.calculate_materials_for_poz(miktar, formuller, fire_orani)
            for material in materials:
                material['poz_no'] = poz_no
                material['poz_tanim'] = kalem.get('tanim', '')
                material['poz_miktar'] = miktar
                material['poz_birim'] = kalem.get('birim', '')
                material['poz_fire_orani'] = fire_orani
                adi = material.get('malzeme_adi', '')
                material['malzeme_kategori'] = _kat_map.get(adi, 'Diğer')
            all_materials.append(materials)

        aggregated = self.calculator.aggregate_materials(all_materials)

        for m in aggregated:
            adi = m.get('malzeme_adi', '')
            if adi in sp_fiyat_tablosu:
                m['birim_fiyat'] = sp_fiyat_tablosu[adi]
            else:
                m.setdefault('birim_fiyat', _fiyat_map.get(adi, 0.0))
            m.setdefault('malzeme_kategori', _kat_map.get(adi, 'Diğer'))
            m['toplam_maliyet'] = round(m.get('miktar', 0) * m.get('birim_fiyat', 0.0), 2)

        return aggregated

    def calculate_materials_for_poz_no(
        self,
        poz_no: str,
        miktar: float,
        fire_orani_override: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Belirli bir poz için malzeme ihtiyacını hesapla.

        Args:
            poz_no: Poz numarası
            miktar: Poz miktarı
            fire_orani_override: Manuel fire oranı (None ise poz bazlı kullanılır)

        Returns:
            List[Dict]: Malzeme listesi
        """
        poz = self.db.get_poz(poz_no)
        if not poz:
            return []

        poz_id = poz['id']

        if fire_orani_override is not None:
            fire_orani = fire_orani_override
        else:
            fire_orani = poz.get('fire_orani', 0.05)

        formuller = self.db.get_poz_formulleri(poz_id)

        if not formuller:
            return []

        materials = self.calculator.calculate_materials_for_poz(
            miktar, formuller, fire_orani
        )

        return materials

    def get_material_summary(
        self,
        proje_id: int,
        fire_orani_override: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Proje için malzeme özeti getir.

        Args:
            proje_id: Proje ID'si
            fire_orani_override: Manuel fire oranı (None ise poz bazlı kullanılır)

        Returns:
            Dict: Özet bilgiler
        """
        materials = self.calculate_materials_for_project(proje_id, fire_orani_override)

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

    def convert_unit(
        self,
        value: float,
        from_unit: str,
        to_unit: str,
        malzeme_id: Optional[int] = None
    ) -> Optional[float]:
        """
        Birim dönüşümü yap.

        Args:
            value: Dönüştürülecek değer
            from_unit: Kaynak birim
            to_unit: Hedef birim
            malzeme_id: Malzeme ID'si (opsiyonel)

        Returns:
            Optional[float]: Dönüştürülmüş değer veya None
        """
        if from_unit == to_unit:
            return value

        katsayi = self.db.get_birim_donusum(from_unit, to_unit, malzeme_id)

        if katsayi is not None:
            return float(Decimal(str(value)) * Decimal(str(katsayi)))

        standard_conversions = {
            ('kg', 'ton'): 0.001,
            ('ton', 'kg'): 1000.0,
            ('kg', 'g'): 1000.0,
            ('g', 'kg'): 0.001,
            ('m³', 'lt'): 1000.0,
            ('lt', 'm³'): 0.001,
            ('m³', 'dm³'): 1000.0,
            ('dm³', 'm³'): 0.001,
            ('m²', 'cm²'): 10000.0,
            ('cm²', 'm²'): 0.0001,
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

    def convert_material_units(
        self,
        materials: List[Dict[str, Any]],
        target_unit: str
    ) -> List[Dict[str, Any]]:
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

            converted_value = self.convert_unit(miktar, current_unit, target_unit, malzeme_id)

            if converted_value is not None:
                new_material = material.copy()
                new_material['miktar'] = converted_value
                new_material['birim'] = target_unit
                converted.append(new_material)
            else:
                converted.append(material)

        return converted
