"""
PDF Birim Fiyat İçe Aktarma Modülü
PDF dosyalarından poz numaraları ve birim fiyatları çıkarır
"""

import re
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    pdfplumber = None


class PDFBirimFiyatImporter:
    """PDF'den birim fiyat içe aktarma sınıfı"""
    
    def __init__(self):
        self.poz_patterns = [
            # Standart poz formatları: 03.001, 03.001/1, 03.001/A, 03.001.001
            r'\b\d{2}\.\d{3}(?:[/\.]\d+)?(?:[/\.][A-Z])?\b',
            # Alternatif: 03-001, 03/001
            r'\b\d{2}[-/]\d{3}(?:[/\.]\d+)?\b',
        ]
        
    def extract_from_pdf(self, pdf_path: Path, progress_callback=None) -> List[Dict[str, Any]]:
        """
        PDF'den poz ve fiyat bilgilerini çıkar.
        
        Args:
            pdf_path: PDF dosya yolu
            progress_callback: İlerleme callback fonksiyonu (sayfa_no, toplam_sayfa)
            
        Returns:
            List[Dict]: Poz ve fiyat bilgileri listesi
        """
        if not PDFPLUMBER_AVAILABLE:
            raise ImportError(
                "pdfplumber kütüphanesi yüklü değil. "
                "Yüklemek için: pip install pdfplumber"
            )
        
        extracted_data = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, 1):
                    if progress_callback:
                        progress_callback(page_num, total_pages)
                    
                    # Sayfadan metni al
                    text = page.extract_text()
                    
                    if not text:
                        continue
                    
                    # Tabloları dene (daha yapılandırılmış veri)
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            table_data = self._parse_table(table)
                            extracted_data.extend(table_data)
                    
                    # Metinden poz ve fiyat çıkar
                    text_data = self._parse_text(text)
                    extracted_data.extend(text_data)
        
        except Exception as e:
            print(f"PDF okuma hatası: {e}")
            raise
        
        # Duplikatları temizle ve birleştir
        return self._deduplicate_and_merge(extracted_data)
    
    def _parse_table(self, table: List[List]) -> List[Dict[str, Any]]:
        """Tablodan poz ve fiyat bilgilerini çıkar"""
        data = []
        
        for row in table:
            if not row or len(row) < 2:
                continue
            
            row_text = ' '.join([str(cell) if cell else '' for cell in row])
            
            # Poz numarası bul
            poz_no = self._find_poz_number(row_text)
            if not poz_no:
                continue
            
            # Fiyat bul
            fiyat = self._find_price(row_text)
            
            # Poz tanımı (genellikle poz numarasından sonraki metin)
            tanim = self._extract_description(row_text, poz_no)
            
            if poz_no:
                data.append({
                    'poz_no': poz_no,
                    'tanim': tanim,
                    'birim_fiyat': fiyat,
                    'kaynak': 'PDF Import'
                })
        
        return data
    
    def _parse_text(self, text: str) -> List[Dict[str, Any]]:
        """Metinden poz ve fiyat bilgilerini çıkar"""
        data = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            # Poz numarası bul
            poz_no = self._find_poz_number(line)
            if not poz_no:
                continue
            
            # Fiyat bul (aynı satırda veya sonraki birkaç satırda)
            fiyat = self._find_price(line)
            
            # Eğer aynı satırda fiyat yoksa, sonraki satırlara bak
            if not fiyat:
                for j in range(i + 1, min(i + 5, len(lines))):
                    fiyat = self._find_price(lines[j])
                    if fiyat:
                        break
            
            # Poz tanımı
            tanim = self._extract_description(line, poz_no)
            
            if poz_no:
                data.append({
                    'poz_no': poz_no,
                    'tanim': tanim,
                    'birim_fiyat': fiyat,
                    'kaynak': 'PDF Import'
                })
        
        return data
    
    def _find_poz_number(self, text: str) -> Optional[str]:
        """Metinden poz numarası bul"""
        for pattern in self.poz_patterns:
            match = re.search(pattern, text)
            if match:
                poz_no = match.group(0)
                # Formatı normalize et (nokta ile)
                poz_no = poz_no.replace('-', '.').replace('/', '.')
                return poz_no
        return None
    
    def _find_price(self, text: str) -> Optional[float]:
        """Metinden fiyat bul (TL, ₺, veya sadece sayı)"""
        # Türk Lirası formatları: 1.234,56 TL, 1,234.56 ₺, 1234.56
        price_patterns = [
            r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:TL|₺|tl)',
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:TL|₺|tl)',
            r'(\d+[.,]\d{2})\s*(?:TL|₺|tl)',
            r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # Sadece sayı (nokta binlik, virgül ondalık)
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Sadece sayı (virgül binlik, nokta ondalık)
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text)
            if matches:
                # En büyük sayıyı al (genellikle fiyat)
                prices = []
                for match in matches:
                    try:
                        # Türk formatı: 1.234,56 -> 1234.56
                        price_str = match.replace('.', '').replace(',', '.')
                        price = float(price_str)
                        if price > 0:
                            prices.append(price)
                    except ValueError:
                        continue
                
                if prices:
                    # En büyük fiyatı döndür (genellikle birim fiyat)
                    return max(prices)
        
        return None
    
    def _extract_description(self, text: str, poz_no: str) -> str:
        """Poz tanımını çıkar"""
        # Poz numarasından sonraki metni al
        poz_index = text.find(poz_no)
        if poz_index >= 0:
            after_poz = text[poz_index + len(poz_no):].strip()
            # İlk 100 karakteri al
            tanim = after_poz[:100].strip()
            # Gereksiz boşlukları temizle
            tanim = ' '.join(tanim.split())
            return tanim if tanim else "PDF'den içe aktarıldı"
        return "PDF'den içe aktarıldı"
    
    def _deduplicate_and_merge(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Duplikatları temizle ve birleştir"""
        poz_dict = {}
        
        for item in data:
            poz_no = item.get('poz_no')
            if not poz_no:
                continue
            
            # Eğer bu poz daha önce görülmediyse veya yeni fiyat daha büyükse
            if poz_no not in poz_dict:
                poz_dict[poz_no] = item
            else:
                # Fiyat varsa ve daha büyükse güncelle
                old_price = poz_dict[poz_no].get('birim_fiyat', 0) or 0
                new_price = item.get('birim_fiyat', 0) or 0
                if new_price > old_price:
                    poz_dict[poz_no] = item
        
        return list(poz_dict.values())

