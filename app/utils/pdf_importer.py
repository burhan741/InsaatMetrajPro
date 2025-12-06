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

# Alternatif: PyPDF2
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    PyPDF2 = None


class PDFBirimFiyatImporter:
    """PDF'den birim fiyat içe aktarma sınıfı"""
    
    def __init__(self):
        self.poz_patterns = [
            # Standart poz formatları: 03.001, 03.001/1, 03.001/A, 03.001.001
            r'\b\d{2}\.\d{3}(?:[/\.]\d+)?(?:[/\.][A-Z])?\b',
            # 3 seviyeli poz formatları: 15.250.1011, 03.001.001
            r'\b\d{2}\.\d{3}\.\d{4}\b',
            r'\b\d{2}\.\d{3}\.\d{3}\b',
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
        if not PDFPLUMBER_AVAILABLE and not PYPDF2_AVAILABLE:
            raise ImportError(
                "PDF işleme kütüphanesi yüklü değil. "
                "Yüklemek için: pip install pdfplumber veya pip install PyPDF2"
            )
        
        extracted_data = []
        
        try:
            # Önce pdfplumber dene (daha iyi tablo desteği)
            if PDFPLUMBER_AVAILABLE:
                with pdfplumber.open(pdf_path) as pdf:
                    total_pages = len(pdf.pages)
                    
                    for page_num, page in enumerate(pdf.pages, 1):
                        if progress_callback:
                            if not progress_callback(page_num, total_pages):
                                break
                        
                        # OPTİMİZASYON: Sadece tablo içeren sayfaları işle
                        # Önce tabloları kontrol et
                        tables = page.extract_tables()
                        
                        if tables:
                            # Tablo varsa işle (çok daha hızlı)
                            for table in tables:
                                table_data = self._parse_table(table)
                                extracted_data.extend(table_data)
                        else:
                            # Tablo yoksa sayfayı atla (metin parsing yapma)
                            # Bu sayede çok daha hızlı işlem yapılır
                            continue
            
            # Alternatif: PyPDF2 kullan
            elif PYPDF2_AVAILABLE:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    total_pages = len(pdf_reader.pages)
                    
                    for page_num in range(total_pages):
                        if progress_callback:
                            if not progress_callback(page_num + 1, total_pages):
                                break
                        
                        page = pdf_reader.pages[page_num]
                        text = page.extract_text()
                        
                        if not text:
                            continue
                        
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
        # Önce poz numarasını bul (poz numarasını fiyat sanmamak için)
        poz_no = self._find_poz_number(text)
        poz_start = text.find(poz_no) if poz_no else -1
        poz_end = poz_start + len(poz_no) if poz_start >= 0 else -1
        
        # Poz numarasından sonraki metni al (fiyat genellikle poz numarasından sonra gelir)
        search_text = text[poz_end + 1:] if poz_end >= 0 else text
        
        # Türk Lirası formatları: 1.234,56 TL, 1,234.56 ₺, 1234.56
        # Öncelik sırası: TL/₺ işaretli olanlar, sonra sadece sayılar
        price_patterns = [
            # TL/₺ işaretli formatlar (en güvenilir)
            (r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:TL|₺|tl)', True),  # 1.234,56 TL (Türk formatı)
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:TL|₺|tl)', 'english'),  # 1,234.56 TL (İngiliz formatı)
            (r'(\d+[.,]\d{2})\s*(?:TL|₺|tl)', True),  # 1250.50 TL veya 1250,50 TL
            
            # Sadece sayı formatları (daha dikkatli)
            (r'(?<!\d)(\d{1,4}(?:\.\d{3})*(?:,\d{2})?)(?!\d)', True),  # 1.234,56 (Türk formatı, poz numarası değil)
            (r'(?<!\d)(\d{1,4}(?:,\d{3})+(?:\.\d{2})?)(?!\d)', 'english'),  # 1,234.56 (İngiliz formatı - en az 1 virgül olmalı)
        ]
        
        prices = []
        
        # Tüm pattern'lerden match'leri topla
        all_matches = []
        for pattern, is_turkish_format in price_patterns:
            for match_obj in re.finditer(pattern, search_text):
                match_str = match_obj.group(1)  # İlk capture group'u al
                start_pos = match_obj.start(1)  # Capture group'un başlangıcı
                end_pos = match_obj.end(1)      # Capture group'un sonu
                all_matches.append((match_str, start_pos, end_pos, is_turkish_format))
        
        # İç içe match'leri temizle (küçük olanlar büyük olanların içindeyse at)
        filtered_matches = []
        for match_str, start, end, fmt in all_matches:
            is_contained = False
            for other_str, other_start, other_end, _ in all_matches:
                if match_str != other_str and other_start <= start and other_end >= end:
                    # Bu match başka bir match'in içinde
                    is_contained = True
                    break
            if not is_contained:
                filtered_matches.append((match_str, fmt))
        
        # Eğer birden fazla match varsa, en uzun olanı al (tam fiyat)
        if filtered_matches:
            # Uzunluğa göre sırala (en uzun önce)
            filtered_matches.sort(key=lambda x: len(x[0]), reverse=True)
            
            # En uzun match'i işle
            match_str, is_turkish_format = filtered_matches[0]
            
            try:
                if is_turkish_format == True:
                    # Türk formatı: 1.234,56 -> nokta binlik, virgül ondalık
                    # Önce noktaları kaldır (binlik ayraç), sonra virgülü noktaya çevir
                    price_str = match_str.replace('.', '').replace(',', '.')
                    price = float(price_str)
                    if price > 0 and not (price < 100 and '.' in match_str and len(match_str.split('.')[0]) <= 2):
                        prices.append(price)
                elif is_turkish_format == 'english':
                    # İngiliz formatı: 1,234.56 -> virgül binlik, nokta ondalık
                    # Önce virgülleri kaldır (binlik ayraç), nokta zaten ondalık
                    # En az 1 virgül olmalı (binlik ayraç için)
                    if ',' in match_str:
                        price_str = match_str.replace(',', '')
                        price = float(price_str)
                        if price > 0:
                            prices.append(price)
                else:
                    # Varsayılan: Türk formatı gibi işle
                    price_str = match_str.replace('.', '').replace(',', '.')
                    price = float(price_str)
                    if price > 0 and not (price < 100 and '.' in match_str and len(match_str.split('.')[0]) <= 2):
                        prices.append(price)
            except (ValueError, AttributeError):
                pass
        
        if prices:
            # En büyük fiyatı döndür (genellikle birim fiyat)
            # Ama çok büyük sayıları filtrele (muhtemelen poz numarası)
            valid_prices = [p for p in prices if p < 1000000]  # 1 milyondan küçük olmalı
            if valid_prices:
                return max(valid_prices)
            elif prices:
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

