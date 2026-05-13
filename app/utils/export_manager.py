# -*- coding: utf-8 -*-
"""
Export Yöneticisi
Malzeme listesi ve raporlar için export işlemleri (PDF/Excel/Metin).
Türkçe karakter desteği: font_utils modülü üzerinden Arial/Calibri kullanır.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime


class ExportManager:
    """Export işlemleri yöneticisi"""

    def __init__(self) -> None:
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # Excel Export
    # ─────────────────────────────────────────────────────────────────────────

    def export_to_excel(self, materials: List[Dict[str, Any]],
                        output_path: Path, proje_adi: str = "") -> bool:
        """Malzeme listesini Excel dosyasına aktar."""
        try:
            import pandas as pd
            from openpyxl.styles import Font, Alignment

            data = []
            for material in materials:
                data.append({
                    'Malzeme Adı': material.get('malzeme_adi', ''),
                    'Miktar': material.get('miktar', 0),
                    'Birim': material.get('birim', ''),
                    'Poz No': material.get('poz_no', ''),
                    'Poz Tanım': material.get('poz_tanim', ''),
                    'Açıklama': material.get('aciklama', ''),
                })

            df = pd.DataFrame(data)

            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Malzeme Listesi', index=False)
                ws = writer.sheets['Malzeme Listesi']
                for col, w in zip('ABCDEF', [30, 15, 10, 15, 40, 30]):
                    ws.column_dimensions[col].width = w
                header_font = Font(bold=True)
                for cell in ws[1]:
                    cell.font = header_font
                    cell.alignment = Alignment(
                        horizontal='center', vertical='center'
                    )

            return True

        except Exception as e:
            print(f"Excel export hatası: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # PDF Export — Malzeme Listesi
    # ─────────────────────────────────────────────────────────────────────────

    def export_to_pdf(self, materials: List[Dict[str, Any]],
                      output_path: Path, proje_adi: str = "",
                      fire_orani: float = 0.0) -> bool:
        """Malzeme listesini PDF dosyasına aktar (Türkçe karakter destekli)."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            )
            from app.utils.font_utils import get_fonts
            F, FB = get_fonts()  # ana_font, kalin_font

            doc = SimpleDocTemplate(str(output_path), pagesize=A4)
            story = []
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontName=FB,
                fontSize=18,
                textColor=colors.HexColor('#1a1a2e'),
                spaceAfter=30,
                alignment=1,
            )

            title_text = "Malzeme Listesi"
            if proje_adi:
                title_text += f" - {proje_adi}"
            story.append(Paragraph(title_text, title_style))
            story.append(Spacer(1, 0.5 * cm))

            info_style = ParagraphStyle(
                'Info', parent=styles['Normal'], fontName=F, fontSize=9
            )
            info_text = (
                f"<b>Oluşturulma Tarihi:</b> "
                + datetime.now().strftime('%d.%m.%Y %H:%M') + "<br/>"
            )
            if fire_orani > 0:
                info_text += f"<b>Fire/Atık Oranı:</b> %{fire_orani * 100:.2f}<br/>"
            info_text += f"<b>Toplam Malzeme Çeşidi:</b> {len(materials)}"
            story.append(Paragraph(info_text, info_style))
            story.append(Spacer(1, 0.5 * cm))

            table_data = [['Malzeme Adı', 'Miktar', 'Birim', 'Poz No']]
            for m in materials:
                table_data.append([
                    m.get('malzeme_adi', ''),
                    f"{m.get('miktar', 0):,.2f}",
                    m.get('birim', ''),
                    m.get('poz_no', ''),
                ])

            table = Table(
                table_data, colWidths=[8 * cm, 3 * cm, 2 * cm, 3 * cm]
            )
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
                ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN',      (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME',   (0, 0), (-1, 0), FB),
                ('FONTSIZE',   (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR',  (0, 1), (-1, -1), colors.black),
                ('ALIGN',  (0, 1), (0, -1), 'LEFT'),
                ('ALIGN',  (1, 1), (1, -1), 'RIGHT'),
                ('ALIGN',  (2, 1), (2, -1), 'CENTER'),
                ('ALIGN',  (3, 1), (3, -1), 'CENTER'),
                ('FONTNAME', (0, 1), (-1, -1), F),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID',     (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                 [colors.white, colors.HexColor('#f5f5f5')]),
            ]))

            story.append(table)
            doc.build(story)
            return True

        except Exception as e:
            print(f"PDF export hatası: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Tedarikçi Metin Formatı
    # ─────────────────────────────────────────────────────────────────────────

    def export_supplier_format(self, materials: List[Dict[str, Any]],
                               output_path: Path, firma_adi: str = "") -> bool:
        """Tedarikçi formatında metin olarak aktar."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("MALZEME SİPARİŞ LİSTESİ\n")
                if firma_adi:
                    f.write(f"Firma: {firma_adi}\n")
                f.write(
                    "Tarih: " + datetime.now().strftime('%d.%m.%Y %H:%M') + "\n"
                )
                f.write("=" * 60 + "\n\n")

                for i, m in enumerate(materials, 1):
                    f.write(f"{i}. {m.get('malzeme_adi', '')}\n")
                    f.write(
                        f"   Miktar: {m.get('miktar', 0):,.2f} "
                        f"{m.get('birim', '')}\n"
                    )
                    if m.get('poz_no'):
                        f.write(f"   Poz: {m.get('poz_no', '')}\n")
                    f.write("\n")

            return True

        except Exception as e:
            print(f"Tedarikçi format export hatası: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Excel Export — Taşeron Teklifleri
    # ─────────────────────────────────────────────────────────────────────────

    def export_taseron_offers_to_excel(self, offers: List[Dict[str, Any]],
                                       output_path: Path,
                                       proje_adi: str = "") -> bool:
        """Taşeron tekliflerini Excel dosyasına aktar."""
        try:
            import pandas as pd
            from openpyxl.styles import Font, Alignment, PatternFill

            data = []
            for offer in offers:
                data.append({
                    'Firma Adı':    offer.get('firma_adi', ''),
                    'Poz No':       offer.get('poz_no', ''),
                    'Tanım':        offer.get('tanim', ''),
                    'Miktar':       offer.get('miktar', 0),
                    'Birim':        offer.get('birim', ''),
                    'Birim Fiyat':  offer.get('fiyat', 0),
                    'Toplam':       offer.get('toplam', 0),
                    'Durum':        offer.get('durum', 'beklemede'),
                    'Teklif Tarihi': offer.get('teklif_tarihi', ''),
                })

            df = pd.DataFrame(data)

            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(
                    writer, sheet_name='Taşeron Teklifleri', index=False
                )
                ws = writer.sheets['Taşeron Teklifleri']
                for col, w in zip('ABCDEFGHI',
                                  [25, 15, 40, 12, 10, 15, 15, 15, 20]):
                    ws.column_dimensions[col].width = w

                header_fill = PatternFill(
                    start_color='16213e', end_color='16213e',
                    fill_type='solid'
                )
                for cell in ws[1]:
                    cell.font = Font(bold=True, color='FFFFFF')
                    cell.fill = header_fill
                    cell.alignment = Alignment(
                        horizontal='center', vertical='center'
                    )

                if len(data) > 0:
                    total_row = len(data) + 2
                    ws.cell(row=total_row, column=1, value="TOPLAM")
                    ws.cell(
                        row=total_row, column=7,
                        value=f"=SUM(G2:G{len(data)+1})"
                    )
                    ws.cell(row=total_row, column=1).font = Font(bold=True)
                    ws.cell(row=total_row, column=7).font = Font(bold=True)

            return True

        except Exception as e:
            print(f"Taşeron Excel export hatası: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # PDF Export — Taşeron Teklifleri
    # ─────────────────────────────────────────────────────────────────────────

    def export_taseron_offers_to_pdf(self, offers: List[Dict[str, Any]],
                                     output_path: Path,
                                     proje_adi: str = "") -> bool:
        """Taşeron tekliflerini PDF dosyasına aktar (Türkçe karakter destekli)."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            )
            from app.utils.font_utils import get_fonts
            F, FB = get_fonts()

            doc = SimpleDocTemplate(str(output_path), pagesize=A4)
            story = []
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontName=FB,
                fontSize=18,
                textColor=colors.HexColor('#1a1a2e'),
                spaceAfter=30,
                alignment=1,
            )

            title_text = "Taşeron Teklifleri"
            if proje_adi:
                title_text += f" - {proje_adi}"
            story.append(Paragraph(title_text, title_style))
            story.append(Spacer(1, 0.5 * cm))

            info_style = ParagraphStyle(
                'Info', parent=styles['Normal'], fontName=F, fontSize=9
            )
            firma_totals: Dict[str, float] = {}
            for offer in offers:
                firma = offer.get('firma_adi', '')
                firma_totals[firma] = (
                    firma_totals.get(firma, 0.0) + offer.get('toplam', 0)
                )

            info_text = (
                "<b>Oluşturulma Tarihi:</b> "
                + datetime.now().strftime('%d.%m.%Y %H:%M') + "<br/>"
                + f"<b>Toplam Teklif Sayısı:</b> {len(offers)}<br/>"
            )
            if firma_totals:
                en_dusuk = min(firma_totals.items(), key=lambda x: x[1])
                en_yuksek = max(firma_totals.items(), key=lambda x: x[1])
                info_text += (
                    f"<b>Firma Sayısı:</b> {len(firma_totals)}<br/>"
                    f"<b>En Düşük Teklif:</b> {en_dusuk[0]} "
                    f"({en_dusuk[1]:,.2f} TL)<br/>"
                    f"<b>En Yüksek Teklif:</b> {en_yuksek[0]} "
                    f"({en_yuksek[1]:,.2f} TL)<br/>"
                )
            story.append(Paragraph(info_text, info_style))
            story.append(Spacer(1, 0.5 * cm))

            table_data = [
                ['Firma', 'Tanım', 'Miktar', 'Birim', 'Fiyat', 'Toplam', 'Durum']
            ]
            for offer in offers:
                tanim = offer.get('tanim', '')
                table_data.append([
                    offer.get('firma_adi', ''),
                    tanim[:30] + ('...' if len(tanim) > 30 else ''),
                    f"{offer.get('miktar', 0):,.2f}" if offer.get('miktar', 0) > 0 else '-',
                    offer.get('birim', ''),
                    f"{offer.get('fiyat', 0):,.2f} TL",
                    f"{offer.get('toplam', 0):,.2f} TL",
                    offer.get('durum', 'beklemede').title(),
                ])

            toplam = sum(o.get('toplam', 0) for o in offers)
            table_data.append(['TOPLAM', '', '', '', '', f"{toplam:,.2f} TL", ''])

            table = Table(
                table_data,
                colWidths=[4 * cm, 6 * cm, 2 * cm, 1.5 * cm,
                           2.5 * cm, 2.5 * cm, 2 * cm],
            )
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
                ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN',      (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME',   (0, 0), (-1, 0), FB),
                ('FONTSIZE',   (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.white),
                ('TEXTCOLOR',  (0, 1), (-1, -2), colors.black),
                ('ALIGN',  (0, 1), (0, -2), 'LEFT'),
                ('ALIGN',  (1, 1), (1, -2), 'LEFT'),
                ('ALIGN',  (2, 1), (2, -2), 'RIGHT'),
                ('ALIGN',  (3, 1), (3, -2), 'CENTER'),
                ('ALIGN',  (4, 1), (5, -2), 'RIGHT'),
                ('ALIGN',  (6, 1), (6, -2), 'CENTER'),
                ('FONTNAME', (0, 1), (-1, -2), F),
                ('FONTSIZE', (0, 1), (-1, -2), 8),
                ('GRID',     (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2),
                 [colors.white, colors.HexColor('#f5f5f5')]),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#c9184a')),
                ('TEXTCOLOR',  (0, -1), (-1, -1), colors.whitesmoke),
                ('FONTNAME',   (0, -1), (-1, -1), FB),
                ('FONTSIZE',   (0, -1), (-1, -1), 10),
            ]))

            story.append(table)
            doc.build(story)
            return True

        except Exception as e:
            print(f"Taşeron PDF export hatası: {e}")
            return False
