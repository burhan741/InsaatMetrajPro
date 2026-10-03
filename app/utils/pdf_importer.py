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
            r'\b\d{2}\.\d{3}\.\d{4}\b',
            r'\b\d{2}\.\d{3}\.\d{3}\b',
            r'\b\d{2}\.\d{3}(?:[/\.]\d+)?(?:[/\.][A-Z])?\b',
            r'\b\d{2}[-/]\d{3}(?:[/\.]\d+)?\b',
        ]

        self.birim_patterns = [
            'adet', 'ad', 'mt', 'm²', 'm2', 'm³', 'm3', 'kg', 'ton', 'lt',
            'takım', 'tk', 'set', 'grup', 'gün', 'saat', 'sa', 'ay', 'yıl',
            'm', 'cm', 'mm', 'km'
        ]

        self.header_keywords = [
            'poz no', 'poz numarası', 'tanım', 'tanımı', 'birim', 'fiyat',
            'ölçü', 'rayiç', 'satın alma', 'açıklama'
        ]

    def extract_from_pdf(self, pdf_path: Path, progress_callback=None) -> List[Dict[str, Any]]:
        """PDF'den poz ve fiyat bilgilerini çıkar."""
        if not PDFPLUMBER_AVAILABLE and not PYPDF2_AVAILABLE:
            raise ImportError(
                "PDF işleme kütüphanesi yüklü değil. "
                "Yüklemek için: pip install pdfplumber veya pip install PyPDF2"
            )

        extracted_data = []

        try:
            if PDFPLUMBER_AVAILABLE:
                with pdfplumber.open(pdf_path) as pdf:
                    total_pages = len(pdf.pages)
                    for page_num, page in enumerate(pdf.pages, 1):
                        if progress_callback:
                            if not progress_callback(page_num, total_pages):
                                break
                        tables = page.extract_tables()
                        if tables:
                            for table in tables:
                                table_data = self._parse_table(table)
                                extracted_data.extend(table_data)
                        else:
                            continue

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
                        text_data = self._parse_text(text)
                        extracted_data.extend(text_data)

        except Exception as e:
            print(f"PDF okuma hatası: {e}")
            raise

        return self._deduplicate_and_merge(extracted_data)

    def _parse_table(self, table: List[List]) -> List[Dict[str, Any]]:
        """Tablodan poz ve fiyat bilgilerini çıkar."""
        data = []
        if not table or len(table) < 1:
            return data

        column_map = self._detect_column_structure(table)

        for row in table:
            if not row or len(row) < 2:
                continue
            if self._is_header_row(row):
                continue
            if self._is_category_row(row):
                continue
            result = self._extract_from_columns(row, column_map)
            if result and result.get('poz_no'):
                data.append(result)

        return data

    def _detect_column_structure(self, table: List[List]) -> Dict[str, int]:
        """Tablo sütun yapısını tespit et."""
        column_map = {
            'poz_no': 0,
            'tanim': 1,
            'birim': -1,
            'fiyat': -1
        }

        for row in table[:5]:
            if not row:
                continue
            row_lower = [str(cell).lower().strip() if cell else '' for cell in row]
            for col_idx, cell in enumerate(row_lower):
                if any(kw in cell for kw in ['poz no', 'poz numarası', 'poz']):
                    column_map['poz_no'] = col_idx
                elif any(kw in cell for kw in ['tanım', 'açıklama', 'iş kalemi']):
                    column_map['tanim'] = col_idx
                elif any(kw in cell for kw in ['birim', 'ölçü', 'br']):
                    column_map['birim'] = col_idx
                elif any(kw in cell for kw in ['fiyat', 'rayiç', 'tutar', 'bedel']):
                    column_map['fiyat'] = col_idx

        if column_map['fiyat'] == -1:
            for row in table:
                if row and len(row) >= 2 and not self._is_header_row(row):
                    column_map['fiyat'] = len(row) - 1
                    break

        return column_map

    def _is_header_row(self, row: List) -> bool:
        """Başlık satırı mı kontrol et."""
        if not row:
            return False
        row_text = ' '.join([str(cell).lower() if cell else '' for cell in row])
        match_count = sum(1 for kw in self.header_keywords if kw in row_text)
        return match_count >= 2

    def _is_category_row(self, row: List) -> bool:
        """Kategori/ara başlık satırı mı kontrol et."""
        if not row:
            return False
        row_text = ' '.join([str(cell) if cell else '' for cell in row])
        poz_no = self._find_poz_number(row_text)
        if poz_no:
            return False
        non_empty_cells = [cell for cell in row if cell and str(cell).strip()]
        if len(non_empty_cells) == 1:
            text = str(non_empty_cells[0]).strip()
            if len(text) > 20 and (text.isupper() or text.istitle()):
                return True
        return False

    def _extract_from_columns(self, row: List, column_map: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """Sütunlardan veri çıkar."""
        if not row:
            return None

        def get_cell(idx: int) -> str:
            if 0 <= idx < len(row) and row[idx]:
                return str(row[idx]).strip()
            return ''

        poz_cell = get_cell(column_map['poz_no'])
        poz_no = self._find_poz_number(poz_cell)

        if not poz_no:
            row_text = ' '.join([str(cell) if cell else '' for cell in row])
            poz_no = self._find_poz_number(row_text)

        if not poz_no:
            return None

        tanim_cell = get_cell(column_map['tanim'])
        tanim = tanim_cell[:200] if tanim_cell else "PDF'den içe aktarıldı"
        tanim = ' '.join(tanim.split())

        birim = ''
        if column_map['birim'] >= 0:
            birim_cell = get_cell(column_map['birim']).lower()
            for b in self.birim_patterns:
                if b in birim_cell or birim_cell == b:
                    birim = birim_cell
                    break

        fiyat = None
        fiyat_idx = column_map['fiyat']
        if fiyat_idx >= 0:
            fiyat_cell = get_cell(fiyat_idx)
            fiyat = self._parse_price_cell(fiyat_cell)

        if fiyat is None:
            for idx in range(len(row) - 1, max(0, len(row) - 3), -1):
                cell = get_cell(idx)
                parsed = self._parse_price_cell(cell)
                if parsed is not None and parsed > 0:
                    fiyat = parsed
                    break

        return {
            'poz_no': poz_no,
            'tanim': tanim,
            'birim': birim,
            'birim_fiyat': fiyat if fiyat is not None else 0,
            'kaynak': 'PDF Import'
        }

    def _parse_price_cell(self, cell: str) -> Optional[float]:
        """Tek bir hücreden fiyat çıkar."""
        if not cell:
            return None
        cell = cell.strip()
        cell = cell.replace('TL', '').replace('₺', '').replace('tl', '').strip()
        cell = cell.replace(' ', '')
        if not cell:
            return None

        try:
            if ',' in cell and '.' in cell:
                last_comma = cell.rfind(',')
                last_dot = cell.rfind('.')
                if last_comma > last_dot:
                    price_str = cell.replace('.', '').replace(',', '.')
                else:
                    price_str = cell.replace(',', '')
                return float(price_str)
            elif ',' in cell:
                return float(cell.replace(',', '.'))
            elif '.' in cell:
                parts = cell.split('.')
                if len(parts) == 2:
                    if len(parts[1]) <= 2:
                        return float(cell)
                    elif len(parts[1]) == 3:
                        return float(cell.replace('.', ''))
                    else:
                        return float(cell)
                elif len(parts) > 2:
                    last_part = parts[-1]
                    if len(last_part) <= 2:
                        integer_part = ''.join(parts[:-1])
                        return float(f"{integer_part}.{last_part}")
                    else:
                        return float(cell.replace('.', ''))
            else:
                return float(cell)
        except (ValueError, AttributeError):
            return None

    def _parse_text(self, text: str) -> List[Dict[str, Any]]:
        """Metinden poz ve fiyat bilgilerini çıkar."""
        data = []
        lines = text.split('\n')

        for i, line in enumerate(lines):
            poz_no = self._find_poz_number(line)
            if not poz_no:
                continue

            fiyat = self._find_price(line)
            if not fiyat:
                for j in range(i + 1, min(i + 5, len(lines))):
                    fiyat = self._find_price(lines[j])
                    if fiyat:
                        break

            tanim = self._extract_description(line, poz_no)
            data.append({
                'poz_no': poz_no,
                'tanim': tanim,
                'birim_fiyat': fiyat if fiyat is not None else 0,
                'kaynak': 'PDF Import'
            })

        return data

    def _find_poz_number(self, text: str) -> Optional[str]:
        """Metinden poz numarası bul."""
        for pattern in self.poz_patterns:
            match = re.search(pattern, text)
            if match:
                poz_no = match.group(0)
                poz_no = poz_no.replace('-', '.').replace('/', '.')
                return poz_no
        return None

    def _find_price(self, text: str) -> Optional[float]:
        """Metinden fiyat bul."""
        poz_no = self._find_poz_number(text)
        poz_start = text.find(poz_no) if poz_no else -1
        poz_end = poz_start + len(poz_no) if poz_start >= 0 else -1
        search_text = text[poz_end + 1:] if poz_end >= 0 else text

        price_patterns = [
            (r'(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)\s*(?:TL|₺|tl)', True),
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:TL|₺|tl)', 'english'),
            (r'(\d+[.,]\d{1,2})\s*(?:TL|₺|tl)', True),
            (r'(?<!\d)(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?)(?!\d)', True),
            (r'(?<!\d)(\d{1,4}(?:,\d{3})+(?:\.\d{1,2})?)(?!\d)', 'english'),
        ]

        all_matches = []
        for pattern, is_turkish_format in price_patterns:
            for match_obj in re.finditer(pattern, search_text):
                match_str = match_obj.group(1)
                start_pos = match_obj.start(1)
                end_pos = match_obj.end(1)
                all_matches.append((match_str, start_pos, end_pos, is_turkish_format))

        filtered_matches = []
        for match_str, start, end, fmt in all_matches:
            is_contained = any(
                match_str != other_str and other_start <= start and other_end >= end
                for other_str, other_start, other_end, _ in all_matches
            )
            if not is_contained:
                filtered_matches.append((match_str, fmt))

        if not filtered_matches:
            return None

        filtered_matches.sort(key=lambda x: len(x[0]), reverse=True)
        match_str, is_turkish_format = filtered_matches[0]

        prices = []
        try:
            if is_turkish_format is True:
                price_str = match_str.replace('.', '').replace(',', '.')
                price = float(price_str)
                if price > 0 and not (price < 100 and '.' in match_str and len(match_str.split('.')[0]) <= 2):
                    prices.append(price)
            elif is_turkish_format == 'english':
                if ',' in match_str:
                    price = float(match_str.replace(',', ''))
                    if price > 0:
                        prices.append(price)
            else:
                price_str = match_str.replace('.', '').replace(',', '.')
                price = float(price_str)
                if price > 0:
                    prices.append(price)
        except (ValueError, AttributeError):
            pass

        if prices:
            valid_prices = [p for p in prices if p < 100_000_000_000]
            return max(valid_prices) if valid_prices else max(prices)

        return None

    def _extract_description(self, text: str, poz_no: str) -> str:
        """Poz tanımını çıkar."""
        poz_index = text.find(poz_no)
        if poz_index >= 0:
            after_poz = text[poz_index + len(poz_no):].strip()
            tanim = after_poz[:100].strip()
            tanim = ' '.join(tanim.split())
            return tanim if tanim else "PDF'den içe aktarıldı"
        return "PDF'den içe aktarıldı"

    def _deduplicate_and_merge(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Duplikatları temizle ve birleştir."""
        poz_dict = {}
        for item in data:
            poz_no = item.get('poz_no')
            if not poz_no:
                continue
            if poz_no not in poz_dict:
                poz_dict[poz_no] = item
            else:
                existing = poz_dict[poz_no]
                old_price = float(existing.get('birim_fiyat') or 0)
                new_price = float(item.get('birim_fiyat') or 0)
                if new_price > old_price:
                    existing['birim_fiyat'] = new_price
                old_tanim = existing.get('tanim', '') or ''
                new_tanim = item.get('tanim', '') or ''
                if len(new_tanim) > len(old_tanim) and new_tanim != "PDF'den içe aktarıldı":
                    existing['tanim'] = new_tanim
                new_birim = item.get('birim', '') or ''
                if new_birim and not existing.get('birim'):
                    existing['birim'] = new_birim
        return list(poz_dict.values())
