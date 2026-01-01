"""
Excel Importer
Excel dosyalarından veri içe aktarma
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

logger = logging.getLogger(__name__)


class ExcelImporter:
    """Excel dosyalarından veri içe aktarma sınıfı"""
    
    def __init__(self):
        """Excel Importer'ı başlat"""
        if not PANDAS_AVAILABLE:
            logger.warning("pandas kütüphanesi yüklü değil. Excel import için: pip install pandas openpyxl")
    
    def import_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Excel dosyasını içe aktar"""
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas kütüphanesi gerekli")
        
        try:
            df = pd.read_excel(file_path)
            logger.info(f"Excel dosyası başarıyla yüklendi: {file_path}")
            return df
        except Exception as e:
            logger.error(f"Excel yükleme hatası: {e}")
            return None


