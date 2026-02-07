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
            # 3 seviyeli poz formatları (öncelikli): 10.202.3003, 15.250.1011
            r'\b\d{2}\.\d{3}\.\d{4}\b',
            r'\b\d{2}\.\d{3}\.\d{3}\b',
            # Standart poz formatları: 03.001, 03.001/1, 03.001/A
            r'\b\d{2}\.\d{3}(?:[/\.]\d+)?(?:[/\.][A-Z])?\b',
            # Alternatif: 03-001, 03/001
            r'\b\d{2}[-/]\d{3}(?:[/\.]\d+)?\b',
        ]

        # Birim tanıma desenleri
        self.birim_patterns = [
            'adet', 'ad', 'mt', 'm²', 'm2', 'm³', 'm3', 'kg', 'ton', 'lt',
            'takım', 'tk', 'set', 'grup', 'gün', 'saat', 'sa', 'ay', 'yıl',
            'm', 'cm', 'mm', 'km'
        ]

        # Başlık satırı tespiti için anahtar kelimeler
        self.header_keywords = [
            'poz no', 'poz numarası', 'tanım', 'tanımı', 'birim', 'fiyat',
            'ölçü', 'rayiç', 'satın alma', 'açıklama'
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
        """Tablodan poz ve fiyat bilgilerini çıkar - Sütun bazlı akıllı işleme"""
        data = []

        if not table or len(table) < 1:
            return data

        # Sütun indekslerini tespit et
        column_map = self._detect_column_structure(table)

        for row_idx, row in enumerate(table):
            if not row or len(row) < 2:
                continue

            # Başlık satırını atla
            if self._is_header_row(row):
                continue

            # Kategori/başlık satırını atla (poz numarası olmayan uzun metin)
            if self._is_category_row(row):
                continue

            # Sütun bazlı veri çıkarma
            result = self._extract_from_columns(row, column_map)

            if result and result.get('poz_no'):
                data.append(result)

        return data

    def _detect_column_structure(self, table: List[List]) -> Dict[str, int]:
        """Tablo sütun yapısını tespit et"""
        column_map = {
            'poz_no': 0,      # Varsayılan: ilk sütun
            'tanim': 1,       # Varsayılan: ikinci sütun
            'birim': -1,      # Bulunamazsa -1
            'fiyat': -1       # Son sütun olacak (aşağıda ayarlanır)
        }

        # İlk birkaç satırdan sütun yapısını anlamaya çalış
        for row in table[:5]:
            if not row:
                continue

            row_lower = [str(cell).lower().strip() if cell else '' for cell in row]

            for col_idx, cell in enumerate(row_lower):
                # Poz No sütunu
                if any(kw in cell for kw in ['poz no', 'poz numarası', 'poz']):
                    column_map['poz_no'] = col_idx

                # Tanım sütunu
                elif any(kw in cell for kw in ['tanım', 'açıklama', 'iş kalemi']):
                    column_map['tanim'] = col_idx

                # Birim sütunu
                elif any(kw in cell for kw in ['birim', 'ölçü', 'br']):
                    column_map['birim'] = col_idx

                # Fiyat sütunu
                elif any(kw in cell for kw in ['fiyat', 'rayiç', 'tutar', 'bedel']):
                    column_map['fiyat'] = col_idx

        # Fiyat sütunu bulunamadıysa son sütunu kullan
        if column_map['fiyat'] == -1:
            # İlk veri satırının uzunluğunu bul
            for row in table:
                if row and len(row) >= 2 and not self._is_header_row(row):
                    column_map['fiyat'] = len(row) - 1
                    break

        return column_map

    def _is_header_row(self, row: List) -> bool:
        """Başlık satırı mı kontrol et"""
        if not row:
            return False

        row_text = ' '.join([str(cell).lower() if cell else '' for cell in row])

        # Başlık anahtar kelimelerinden en az 2 tanesi varsa başlık satırıdır
        match_count = sum(1 for kw in self.header_keywords if kw in row_text)
        return match_count >= 2

    def _is_category_row(self, row: List) -> bool:
        """Kategori/ara başlık satırı mı kontrol et"""
        if not row:
            return False

        # Tüm satırı birleştir
        row_text = ' '.join([str(cell) if cell else '' for cell in row])

        # Poz numarası var mı kontrol et
        poz_no = self._find_poz_number(row_text)
        if poz_no:
            return False  # Poz numarası varsa kategori değil

        # Sadece ilk hücrede uzun metin varsa ve diğerleri boşsa = kategori
        non_empty_cells = [cell for cell in row if cell and str(cell).strip()]
        if len(non_empty_cells) == 1:
            text = str(non_empty_cells[0]).strip()
            # 20 karakterden uzun ve tamamen büyük harf veya başlık formatındaysa
            if len(text) > 20 and (text.isupper() or text.istitle()):
                return True

        return False

    def _extract_from_columns(self, row: List, column_map: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """Sütunlardan veri çıkar"""
        if not row:
            return None

        # Güvenli hücre erişimi
        def get_cell(idx: int) -> str:
            if 0 <= idx < len(row) and row[idx]:
                return str(row[idx]).strip()
            return ''

        # Poz numarası
        poz_cell = get_cell(column_map['poz_no'])
        poz_no = self._find_poz_number(poz_cell)

        # Poz numarası ilk sütunda bulunamadıysa tüm satırda ara
        if not poz_no:
            row_text = ' '.join([str(cell) if cell else '' for cell in row])
            poz_no = self._find_poz_number(row_text)

        if not poz_no:
            return None

        # Tanım
        tanim_cell = get_cell(column_map['tanim'])
        tanim = tanim_cell[:200] if tanim_cell else "PDF'den içe aktarıldı"
        # Gereksiz boşlukları temizle
        tanim = ' '.join(tanim.split())

        # Birim
        birim = ''
        if column_map['birim'] >= 0:
            birim_cell = get_cell(column_map['birim']).lower()
            # Bilinen birimlerden biriyse al
            for b in self.birim_patterns:
                if b in birim_cell or birim_cell == b:
                    birim = birim_cell
                    break

        # Fiyat - son sütundan veya tespit edilen sütundan
        fiyat = None
        fiyat_idx = column_map['fiyat']

        # Önce tespit edilen fiyat sütununu dene
        if fiyat_idx >= 0:
            fiyat_cell = get_cell(fiyat_idx)
            fiyat = self._parse_price_cell(fiyat_cell)

        # Bulunamadıysa son birkaç sütunu dene (sağdan sola)
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
        """Tek bir hücreden fiyat çıkar"""
        if not cell:
            return None

        cell = cell.strip()

        # TL/₺ sembolünü temizle
        cell = cell.replace('TL', '').replace('₺', '').replace('tl', '').strip()

        # Boşlukları temizle
        cell = cell.replace(' ', '')

        if not cell:
            return None

        try:
            # Türk formatı: 1.234,56 (nokta binlik, virgül ondalık)
            if ',' in cell and '.' in cell:
                # Hangisi son? Son olan ondalık ayracıdır
                last_comma = cell.rfind(',')
                last_dot = cell.rfind('.')
                if last_comma > last_dot:
                    # Türk formatı: 1.234,56 veya 140.000.000,00
                    price_str = cell.replace('.', '').replace(',', '.')
                else:
                    # İngiliz formatı: 1,234.56
                    price_str = cell.replace(',', '')
                return float(price_str)

            # Sadece virgül var: 184,80 (Türk formatı - ondalık)
            elif ',' in cell:
                price_str = cell.replace(',', '.')
                return float(price_str)

            # Sadece nokta var (karmaşık durum)
            elif '.' in cell:
                parts = cell.split('.')

                # Tek nokta: 184.80 veya 1.234
                if len(parts) == 2:
                    if len(parts[1]) <= 2:
                        # Son kısım 1-2 haneli = ondalık (184.80, 184.8)
                        return float(cell)
                    elif len(parts[1]) == 3:
                        # Son kısım 3 haneli = binlik (1.234 = 1234)
                        return float(cell.replace('.', ''))
                    else:
                        return float(cell)

                # Birden fazla nokta: 140.000.000 veya 140.000.000.00
                elif len(parts) > 2:
                    last_part = parts[-1]

                    # Son kısım 1-2 haneli ise ondalık: 140.000.000.00 → 140000000.00
                    if len(last_part) <= 2:
                        # Son kısım ondalık, geri kalanı binlik ayraçlı
                        integer_part = ''.join(parts[:-1])  # 140000000
                        decimal_part = last_part  # 00
                        return float(f"{integer_part}.{decimal_part}")

                    # Tüm kısımlar 3 haneli = hepsi binlik: 140.000.000 → 140000000
                    else:
                        return float(cell.replace('.', ''))

                else:
                    return float(cell)

            # Sadece rakam
            else:
                return float(cell)

        except (ValueError, AttributeError):
            return None
    
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
                    'birim_fiyat': fiyat if fiyat is not None else 0,
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
        
        # Türk Lirası formatları: 1.234,56 TL, 140.000.000,0 TL, 1,234.56 ₺
        # Öncelik sırası: TL/₺ işaretli olanlar, sonra sadece sayılar
        price_patterns = [
            # TL/₺ işaretli formatlar (en güvenilir)
            (r'(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)\s*(?:TL|₺|tl)', True),  # 140.000.000,0 TL (Türk formatı)
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:TL|₺|tl)', 'english'),  # 1,234.56 TL (İngiliz formatı)
            (r'(\d+[.,]\d{1,2})\s*(?:TL|₺|tl)', True),  # 1250.5 TL veya 1250,50 TL

            # Sadece sayı formatları (büyük fiyatlar için)
            (r'(?<!\d)(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?)(?!\d)', True),  # 140.000.000,0 (Türk formatı - en az 1 nokta)
            (r'(?<!\d)(\d{1,4}(?:,\d{3})+(?:\.\d{1,2})?)(?!\d)', 'english'),  # 1,234.56 (İngiliz formatı)
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
            # İnşaat sektöründe çok büyük fiyatlar olabilir (milyarlar)
            valid_prices = [p for p in prices if p < 100000000000]  # 100 milyara kadar
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
        """Duplikatları temizle ve birleştir - birim bilgisini de koru"""
        poz_dict = {}

        for item in data:
            poz_no = item.get('poz_no')
            if not poz_no:
                continue

            if poz_no not in poz_dict:
                poz_dict[poz_no] = item
            else:
                # Mevcut kayıtla karşılaştır ve en iyi verileri birleştir
                existing = poz_dict[poz_no]

                # Fiyat: Daha büyük olanı al (None kontrolü ile)
                old_price = float(existing.get('birim_fiyat') or 0)
                new_price = float(item.get('birim_fiyat') or 0)
                if new_price > old_price:
                    existing['birim_fiyat'] = new_price

                # Tanım: Daha uzun olanı al
                old_tanim = existing.get('tanim', '') or ''
                new_tanim = item.get('tanim', '') or ''
                if len(new_tanim) > len(old_tanim) and new_tanim != "PDF'den içe aktarıldı":
                    existing['tanim'] = new_tanim

                # Birim: Boş değilse güncelle
                new_birim = item.get('birim', '') or ''
                if new_birim and not existing.get('birim'):
                    existing['birim'] = new_birim

        return list(poz_dict.values())

