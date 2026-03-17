"""
Minimal Calculator Stub
Esas hesaplama modülü syntax hataları nedeniyle kullanılamıyor.
Bu minimal sürüm sadece temel interface sağlıyor.
"""

from typing import Dict, Any, Optional


class Calculator:
    """Minimal hesap makinesi"""
    
    def __init__(self):
        pass
    
    def hesapla_duvar_maliyet(self, **kwargs) -> Dict[str, Any]:
        """Duvar maliyet hesaplama (dummy)"""
        return {
            'toplam_maliyet': 0,
            'birim_fiyat': 0,
            'detaylar': {}
        }
    
    def hesapla_alci_maliyet(self, **kwargs) -> Dict[str, Any]:
        """Alçı maliyet hesaplama (dummy)"""
        return {
            'toplam_maliyet': 0,
            'birim_fiyat': 0,
            'detaylar': {}
        }


# Placeholder fonksiyonları
def hesapla_duvar_maliyet_detayli(**kwargs) -> Dict[str, Any]:
    """Duvar maliyet (dummy)"""
    return {'toplam': 0, 'birim_fiyat': 0}


def hesapla_alci_maliyet_detayli(**kwargs) -> Dict[str, Any]:
    """Alçı maliyet (dummy)"""
    return {'toplam': 0, 'birim_fiyat': 0}


def hesapla_elektrik_ozel(**kwargs) -> Dict[str, Any]:
    """Elektrik maliyet (dummy)"""
    return {'toplam': 0}


def hesapla_kaba_yapi_manuel(**kwargs) -> Dict[str, Any]:
    """Kaba yapı maliyet (dummy)"""
    return {'toplam': 0}


# Placeholder dictionaries
VERIMLILIK_VERITABANI = {
    'piyasa': 10,
    'csb_resmi': 13,
    'manuel': 15
}

MALZEME_SARFIYAT = {
    'cimento': 100,  # kg
    'kum': 200,      # kg
    'su': 50         # litre
}

ALCI_SARFIYAT = {
    'alci': 1.0,
    'agirlik': 100
}

ALCI_VERIMLILIK = {
    'piyasa': 5,
    'csb_resmi': 4
}

HAFRIYAT_VERIMLILIK = {
    'manuel': 3,
    'makine': 20
}

DEMIR_KAYNAKLAR = {
    'piyasa': 500,
    'csb_resmi': 450
}
