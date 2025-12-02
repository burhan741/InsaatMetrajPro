"""
Yardımcı Fonksiyonlar
Genel kullanım için utility fonksiyonları
"""

from typing import Optional
from pathlib import Path
from datetime import datetime


def format_currency(amount: float, symbol: str = "₺") -> str:
    """
    Para birimini formatla.
    
    Args:
        amount: Tutar
        symbol: Para birimi sembolü
        
    Returns:
        str: Formatlanmış tutar
    """
    return f"{amount:,.2f} {symbol}".replace(",", "X").replace(".", ",").replace("X", ".")
    

def format_date(date_string: Optional[str], format_str: str = "%d.%m.%Y") -> str:
    """
    Tarih string'ini formatla.
    
    Args:
        date_string: ISO formatında tarih string'i
        format_str: Çıktı formatı
        
    Returns:
        str: Formatlanmış tarih
    """
    if not date_string:
        return ""
        
    try:
        dt = datetime.fromisoformat(date_string)
        return dt.strftime(format_str)
    except:
        return date_string
        

def validate_file_path(file_path: Path, extensions: list) -> bool:
    """
    Dosya yolunu ve uzantısını kontrol et.
    
    Args:
        file_path: Dosya yolu
        extensions: İzin verilen uzantılar listesi
        
    Returns:
        bool: Geçerli ise True
    """
    if not file_path.exists():
        return False
        
    return file_path.suffix.lower() in [ext.lower() for ext in extensions]





