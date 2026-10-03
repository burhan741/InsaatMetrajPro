"""
Minimal Data Loader Stub
Veri yükleme modülü syntax hataları nedeniyle minimal versiyona dönüştürüldü.
"""

import logging
from typing import Dict, Any, Optional
from app.core.database import DatabaseManager

logger = logging.getLogger(__name__)


def check_pozlar_loaded(db: DatabaseManager) -> bool:
    """CŞB poz tablosunun dolu olup olmadigini kontrol et."""
    try:
        from app.core.csb_poz_engine import CSBPozEngine
        return len(CSBPozEngine().tum_pozlar()) > 0
    except Exception:
        pass
    try:
        pozlar = db.execute("SELECT COUNT(*) as count FROM pozlar")
        return (pozlar[0]['count'] if pozlar else 0) > 0
    except Exception:
        return False


def check_malzemeler_loaded(db: DatabaseManager) -> bool:
    """Check if materials are loaded (minimal)"""
    try:
        malzemeler = db.execute("SELECT COUNT(*) as count FROM malzemeler")
        return (malzemeler[0]['count'] if malzemeler else 0) > 0
    except:
        return False


def check_formuller_loaded(db: DatabaseManager) -> bool:
    """Check if formulas are loaded (minimal)"""
    try:
        formuller = db.execute("SELECT COUNT(*) as count FROM malzeme_formulleri")
        return (formuller[0]['count'] if formuller else 0) > 0
    except:
        return False


def initialize_database_data(db: DatabaseManager, force_reload: bool = False) -> Dict[str, Any]:
    """Initialize database data — CŞB poz seed'ini csb_poz_engine uzerinden calistirir."""
    try:
        from app.core.csb_poz_engine import CSBPozEngine
        engine = CSBPozEngine()
        count = len(engine.tum_pozlar())
        return {
            'pozlar': {'success': count, 'failed': 0},
            'malzemeler': {'success': 0, 'failed': 0},
            'formuller': {'success': 0, 'failed': 0},
            'message': f'CŞB poz veritabanı hazır ({count} poz)',
        }
    except Exception as e:
        logger.warning("CŞB poz seed hatası: %s", e)
        return {
            'pozlar': {'success': 0, 'failed': 0},
            'malzemeler': {'success': 0, 'failed': 0},
            'formuller': {'success': 0, 'failed': 0},
            'message': 'Poz veritabanı hazırlanamadı',
        }


def initialize_material_data(db: DatabaseManager, force_reload: bool = False) -> Dict[str, Any]:
    """Initialize material data (minimal - dummy)"""
    return {
        'malzemeler': {'success': 0, 'failed': 0},
        'formuller': {'success': 0, 'failed': 0}
    }


# Placeholder constants
POZLAR = []
MALZEME_LISTESI = {}
FORMUL_LISTESI = {}
