"""
Export Yöneticisi
Malzeme listesi ve raporlar için export işlemleri
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


class ExportManager:
    """Export işlemleri yöneticisi"""
    
    def __init__(self) -> None:
        """Export yöneticisini başlat"""
        pass
    
    def export_to_excel(self, materials: List[Dict[str, Any]], 
                       output_path: Path, proje_adi: str = "") -> bool:
        """
        Malzeme listesini Excel dosyasına export et.
        
        Args:
            materials: Malzeme listesi
            output_path: Çıktı dosya yolu
            proje_adi: Proje adı
            
        Returns:
            bool: Başarı durumu
        """
        try:
            # DataFrame oluştur
            data = []
            for material in materials:
                data.append({
                    'Malzeme Adı': material.get('malzeme_adi', ''),
                    'Miktar': material.get('miktar', 0),
                    'Birim': material.get('birim', ''),
                    'Poz No': material.get('poz_no', ''),
                    'Poz Tanım': material.get('poz_tanim', ''),
                    'Açıklama': material.get('aciklama', '')
                })
            
            df = pd.DataFrame(data)
            
            # Excel'e yaz
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Malzeme Listesi', index=False)
                
                # Stil ayarları
                worksheet = writer.sheets['Malzeme Listesi']
                
                # Sütun genişlikleri
                worksheet.column_dimensions['A'].width = 30
                worksheet.column_dimensions['B'].width = 15
                worksheet.column_dimensions['C'].width = 10
                worksheet.column_dimensions['D'].width = 15
                worksheet.column_dimensions['E'].width = 40
                worksheet.column_dimensions['F'].width = 30
                
                # Başlık satırını kalın yap
                from openpyxl.styles import Font, Alignment
                header_font = Font(bold=True)
                for cell in worksheet[1]:
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal='center', vertical='center')
            
            return True
            
        except Exception as e:
            print(f"Excel export hatası: {e}")
            return False
    
    def export_to_pdf(self, materials: List[Dict[str, Any]], 
                     output_path: Path, proje_adi: str = "", 
                     fire_orani: float = 0.0) -> bool:
        """
        Malzeme listesini PDF dosyasına export et.
        
        Args:
            materials: Malzeme listesi
            output_path: Çıktı dosya yolu
            proje_adi: Proje adı
            fire_orani: Fire oranı
            
        Returns:
            bool: Başarı durumu
        """
        try:
            doc = SimpleDocTemplate(str(output_path), pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Başlık
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#1a1a2e'),
                spaceAfter=30,
                alignment=1  # Center
            )
            
            title_text = f"Malzeme Listesi"
            if proje_adi:
                title_text += f" - {proje_adi}"
            story.append(Paragraph(title_text, title_style))
            story.append(Spacer(1, 0.5*cm))
            
            # Bilgiler
            info_style = styles['Normal']
            info_text = f"<b>Oluşturulma Tarihi:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}<br/>"
            if fire_orani > 0:
                info_text += f"<b>Fire/Atık Oranı:</b> %{fire_orani*100:.2f}<br/>"
            info_text += f"<b>Toplam Malzeme Çeşidi:</b> {len(materials)}"
            story.append(Paragraph(info_text, info_style))
            story.append(Spacer(1, 0.5*cm))
            
            # Tablo verileri
            table_data = [['Malzeme Adı', 'Miktar', 'Birim', 'Poz No']]
            
            for material in materials:
                table_data.append([
                    material.get('malzeme_adi', ''),
                    f"{material.get('miktar', 0):,.2f}",
                    material.get('birim', ''),
                    material.get('poz_no', '')
                ])
            
            # Tablo oluştur
            table = Table(table_data, colWidths=[8*cm, 3*cm, 2*cm, 3*cm])
            table.setStyle(TableStyle([
                # Başlık satırı
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                
                # Veri satırları
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Malzeme adı
                ('ALIGN', (1, 1), (1, -1), 'RIGHT'),  # Miktar
                ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Birim
                ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Poz No
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ]))
            
            story.append(table)
            
            # PDF oluştur
            doc.build(story)
            return True
            
        except Exception as e:
            print(f"PDF export hatası: {e}")
            return False
    
    def export_supplier_format(self, materials: List[Dict[str, Any]], 
                              output_path: Path, firma_adi: str = "") -> bool:
        """
        Tedarikçi formatında export (basit liste).
        
        Args:
            materials: Malzeme listesi
            output_path: Çıktı dosya yolu
            firma_adi: Firma adı
            
        Returns:
            bool: Başarı durumu
        """
        try:
            # Basit metin formatı
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("MALZEME SİPARİŞ LİSTESİ\n")
                if firma_adi:
                    f.write(f"Firma: {firma_adi}\n")
                f.write(f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
                f.write("=" * 60 + "\n\n")
                
                for i, material in enumerate(materials, 1):
                    f.write(f"{i}. {material.get('malzeme_adi', '')}\n")
                    f.write(f"   Miktar: {material.get('miktar', 0):,.2f} {material.get('birim', '')}\n")
                    if material.get('poz_no'):
                        f.write(f"   Poz: {material.get('poz_no', '')}\n")
                    f.write("\n")
            
            return True
            
        except Exception as e:
            print(f"Tedarikçi format export hatası: {e}")
            return False

