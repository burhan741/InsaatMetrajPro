"""
Veri Yükleme Yardımcı Modülü
Poz ve malzeme verilerini veritabanına yükler
"""

from typing import List, Dict, Any
from app.core.database import DatabaseManager
from app.data.konut_is_kalemleri import POZLAR
from app.data.malzeme_formulleri import get_all_materials, get_all_formulas
from app.data.fire_oranlari import get_fire_orani


def load_pozlar_to_database(db: DatabaseManager) -> Dict[str, int]:
    """
    Pozları veritabanına yükle.
    
    Args:
        db: DatabaseManager instance
        
    Returns:
        Dict: {'success': başarılı sayısı, 'failed': başarısız sayısı}
    """
    success_count = 0
    failed_count = 0
    
    for poz in POZLAR:
        try:
            # Poz için fire oranını belirle (Literatür/Kitap değerleri)
            fire_orani = get_fire_orani(poz['poz_no'], poz.get('kategori', ''))
            
            db.add_poz(
                poz_no=poz['poz_no'],
                tanim=poz['tanim'],
                birim=poz['birim'],
                resmi_fiyat=0.0,  # Varsayılan fiyat, sonra güncellenebilir
                kategori=poz['kategori'],
                fire_orani=fire_orani
            )
            success_count += 1
        except Exception as e:
            print(f"Poz eklenirken hata: {poz['poz_no']} - {e}")
            failed_count += 1
    
    return {'success': success_count, 'failed': failed_count}


def check_pozlar_loaded(db: DatabaseManager) -> bool:
    """
    Pozların yüklenip yüklenmediğini kontrol et.
    
    Args:
        db: DatabaseManager instance
        
    Returns:
        bool: Pozlar yüklü ise True
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM pozlar")
        result = cursor.fetchone()
        return result['count'] > 0 if result else False


def initialize_database_data(db: DatabaseManager, force_reload: bool = False) -> Dict[str, Any]:
    """
    Veritabanına başlangıç verilerini yükle.
    
    Args:
        db: DatabaseManager instance
        force_reload: Mevcut verileri silip yeniden yükle
        
    Returns:
        Dict: Yükleme sonuçları
    """
    results = {
        'pozlar': {'success': 0, 'failed': 0},
        'message': ''
    }
    
    # Pozlar zaten yüklü mü kontrol et
    if not force_reload and check_pozlar_loaded(db):
        results['message'] = 'Pozlar zaten yüklü. Yeniden yüklemek için force_reload=True kullanın.'
        return results
    
    # Pozları yükle
    poz_result = load_pozlar_to_database(db)
    results['pozlar'] = poz_result
    
    if poz_result['success'] > 0:
        results['message'] = f"Başarıyla {poz_result['success']} poz yüklendi."
        if poz_result['failed'] > 0:
            results['message'] += f" {poz_result['failed']} poz yüklenemedi."
    else:
        results['message'] = "Pozlar yüklenemedi."
    
    return results


def load_malzemeler_to_database(db: DatabaseManager) -> Dict[str, int]:
    """
    Malzemeleri veritabanına yükle.
    
    Args:
        db: DatabaseManager instance
        
    Returns:
        Dict: {'success': başarılı sayısı, 'failed': başarısız sayısı}
    """
    success_count = 0
    failed_count = 0
    
    materials = get_all_materials()
    
    for material in materials:
        try:
            db.add_malzeme(
                ad=material['ad'],
                birim=material['birim'],
                kategori=material.get('kategori', ''),
                aciklama=material.get('aciklama', '')
            )
            success_count += 1
        except Exception as e:
            print(f"Malzeme eklenirken hata: {material['ad']} - {e}")
            failed_count += 1
    
    return {'success': success_count, 'failed': failed_count}


def load_malzeme_formulleri_to_database(db: DatabaseManager) -> Dict[str, int]:
    """
    Malzeme formüllerini veritabanına yükle.
    
    Args:
        db: DatabaseManager instance
        
    Returns:
        Dict: {'success': başarılı sayısı, 'failed': başarısız sayısı}
    """
    success_count = 0
    failed_count = 0
    
    formulas = get_all_formulas()
    
    for formula_data in formulas:
        poz_no = formula_data['poz_no']
        formuller = formula_data.get('formuller', [])
        
        # Poz ID'sini bul
        poz = db.get_poz(poz_no)
        if not poz:
            print(f"Poz bulunamadı: {poz_no}")
            failed_count += len(formuller)
            continue
        
        poz_id = poz['id']
        
        # Her formülü ekle
        for formul in formuller:
            try:
                malzeme_adi = formul['malzeme']
                miktar = formul['miktar']
                birim = formul['birim']
                
                # Malzeme ID'sini bul
                malzeme = db.get_malzeme_by_name(malzeme_adi)
                if not malzeme:
                    print(f"Malzeme bulunamadı: {malzeme_adi}")
                    failed_count += 1
                    continue
                
                malzeme_id = malzeme['id']
                
                # Formülü ekle
                db.add_malzeme_formulu(
                    poz_id=poz_id,
                    malzeme_id=malzeme_id,
                    miktar=miktar,
                    birim=birim,
                    formul_tipi='direkt',
                    aciklama=f"{poz_no} için {malzeme_adi} formülü"
                )
                success_count += 1
            except Exception as e:
                print(f"Formül eklenirken hata: {poz_no} - {malzeme_adi} - {e}")
                failed_count += 1
    
    return {'success': success_count, 'failed': failed_count}


def check_malzemeler_loaded(db: DatabaseManager) -> bool:
    """Malzemelerin yüklenip yüklenmediğini kontrol et."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM malzemeler")
        result = cursor.fetchone()
        return result['count'] > 0 if result else False


def check_formuller_loaded(db: DatabaseManager) -> bool:
    """Formüllerin yüklenip yüklenmediğini kontrol et."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM malzeme_formulleri")
        result = cursor.fetchone()
        return result['count'] > 0 if result else False


def initialize_material_data(db: DatabaseManager, force_reload: bool = False) -> Dict[str, Any]:
    """
    Malzeme ve formül verilerini veritabanına yükle.
    
    Args:
        db: DatabaseManager instance
        force_reload: Mevcut verileri silip yeniden yükle
        
    Returns:
        Dict: Yükleme sonuçları
    """
    results = {
        'malzemeler': {'success': 0, 'failed': 0},
        'formuller': {'success': 0, 'failed': 0},
        'message': ''
    }
    
    # Malzemeler zaten yüklü mü kontrol et
    if not force_reload and check_malzemeler_loaded(db):
        results['message'] = 'Malzemeler zaten yüklü.'
    else:
        # Malzemeleri yükle
        malzeme_result = load_malzemeler_to_database(db)
        results['malzemeler'] = malzeme_result
    
    # Formüller zaten yüklü mü kontrol et
    if not force_reload and check_formuller_loaded(db):
        if results['message']:
            results['message'] += ' Formüller zaten yüklü.'
        else:
            results['message'] = 'Formüller zaten yüklü.'
    else:
        # Formülleri yükle
        formul_result = load_malzeme_formulleri_to_database(db)
        results['formuller'] = formul_result
    
    if not results['message']:
        results['message'] = (
            f"Malzemeler: {results['malzemeler']['success']} başarılı, "
            f"{results['malzemeler']['failed']} başarısız. "
            f"Formüller: {results['formuller']['success']} başarılı, "
            f"{results['formuller']['failed']} başarısız."
        )
    
    return results

