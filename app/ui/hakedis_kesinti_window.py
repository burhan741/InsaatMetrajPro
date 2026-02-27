"""
Hakediş Kesinti ve Mahsup Hesabı — UI Penceresi
================================================
4734 / 4735 sayılı Kamu İhale Kanunları
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date

from PyQt6.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
 QGroupBox, QLabel, QLineEdit, QDoubleSpinBox, QSpinBox,
 QCheckBox, QPushButton, QTableWidget, QTableWidgetItem,
 QHeaderView, QMessageBox, QSizePolicy, QScrollArea,
 QFrame, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from app.core.hakedis_kesinti_engine import (
 HakedisKesintEngine, HakedisKesintiBilgisi, HakedisKesintleri,
 KESIN_TEMINAT_ORANI, DAMGA_VERGISI_ORANI,
 GELIR_VERGISI_STOPAJ, SGK_PRIM_KESINTI_ORANI, GUNLUK_GECIKME_ORANI
)


# ---------------------------------------------------------------------------
# Stil sabitleri
# ---------------------------------------------------------------------------
DARK_BG = "#1a1a2e"
CARD_BG = "#16213e"
ACCENT = "#00BFFF"
TEXT_WHITE = "#e0e0e0"
TEXT_GRAY = "#a0a0b0"
GREEN = "#27ae60"
RED = "#e74c3c"
YELLOW = "#f39c12"

BUTTON_STYLE = f"""
 QPushButton {{
 background-color: {ACCENT};
 color: #000;
 border: none;
 border-radius: 4px;
 padding: 6px 16px;
 font-weight: bold;
 font-size: 13px;
 }}
 QPushButton:hover {{ background-color: #33d6ff; }}
 QPushButton:pressed {{ background-color: #0090cc; }}
"""

INPUT_STYLE = f"""
 QDoubleSpinBox, QSpinBox, QLineEdit {{
 background-color: #0f3460;
 color: {TEXT_WHITE};
 border: 1px solid #2a4a7f;
 border-radius: 4px;
 padding: 4px 8px;
 font-size: 13px;
 }}
 QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus {{
 border: 1px solid {ACCENT};
 }}
"""

LABEL_STYLE = f"color: {TEXT_GRAY}; font-size: 12px;"
VALUE_STYLE = f"color: {TEXT_WHITE}; font-size: 13px; font-weight: bold;"


class HakedisKesintWindow(QWidget):
 """
 Kamu yapım işi hakediş kesinti hesabı ana penceresi.

 Sol panel — girdi formu
 Sağ panel — kesinti tablosu + net ödeme özeti
 Alt panel — uyarı alanı + export butonları
 """

 def __init__(self, db=None, parent: QWidget | None = None) -> None:
 super().__init__(parent)
 self.db = db
 self.engine = HakedisKesintEngine()
 self._son_bilgi: HakedisKesintiBilgisi | None = None
 self._son_sonuc: HakedisKesintleri | None = None

 self._build_ui()
 self._apply_styles()

 # ------------------------------------------------------------------
 # UI oluşturma
 # ------------------------------------------------------------------

 def _build_ui(self) -> None:
 root = QVBoxLayout(self)
 root.setContentsMargins(12, 12, 12, 12)
 root.setSpacing(8)

 # Başlık
 baslik = QLabel(" Hakediş Kesinti ve Mahsup Hesabı")
 baslik.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
 baslik.setStyleSheet(f"color: {ACCENT}; padding-bottom: 4px;")
 root.addWidget(baslik)

 alt_baslik = QLabel(
 "4734 Kamu İhale Kanunu + 4735 Kamu İhale Sözleşmeleri Kanunu"
 )
 alt_baslik.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px;")
 root.addWidget(alt_baslik)

 sep = QFrame()
 sep.setFrameShape(QFrame.Shape.HLine)
 sep.setStyleSheet(f"color: #2a4a7f;")
 root.addWidget(sep)

 # Ana içerik (sol form + sağ tablo)
 icerik = QHBoxLayout()
 icerik.setSpacing(12)

 icerik.addWidget(self._build_form(), 2)
 icerik.addWidget(self._build_sonuc_panel(), 3)

 root.addLayout(icerik)

 # Toolbar
 root.addWidget(self._build_toolbar())

 # Uyarı alanı
 self.uyari_text = QTextEdit()
 self.uyari_text.setReadOnly(True)
 self.uyari_text.setMaximumHeight(80)
 self.uyari_text.setStyleSheet(
 f"background-color: #1a1a2e; color: {YELLOW}; "
 f"border: 1px solid #2a4a7f; font-size: 12px;"
 )
 self.uyari_text.setPlaceholderText("Uyarılar burada görünür...")
 root.addWidget(self.uyari_text)

 def _build_form(self) -> QGroupBox:
 grp = QGroupBox("Hakediş Bilgileri")
 layout = QFormLayout(grp)
 layout.setSpacing(8)

 # Hakediş no
 self.hakedis_no_spin = QSpinBox()
 self.hakedis_no_spin.setRange(1, 999)
 self.hakedis_no_spin.setValue(1)
 layout.addRow("Hakediş No:", self.hakedis_no_spin)

 # Sözleşme bedeli
 self.sozlesme_spin = QDoubleSpinBox()
 self.sozlesme_spin.setRange(0, 99_999_999_999)
 self.sozlesme_spin.setDecimals(2)
 self.sozlesme_spin.setSuffix(" TL")
 self.sozlesme_spin.setSingleStep(100_000)
 layout.addRow("Sözleşme Bedeli:", self.sozlesme_spin)

 # Brüt hakediş
 self.brut_spin = QDoubleSpinBox()
 self.brut_spin.setRange(0, 99_999_999_999)
 self.brut_spin.setDecimals(2)
 self.brut_spin.setSuffix(" TL")
 self.brut_spin.setSingleStep(10_000)
 layout.addRow("Brüt Hakediş:", self.brut_spin)

 sep = QFrame()
 sep.setFrameShape(QFrame.Shape.HLine)
 sep.setStyleSheet("color: #2a4a7f;")
 layout.addRow(sep)

 # Avans bilgileri
 avans_baslik = QLabel("Avans Bilgileri")
 avans_baslik.setStyleSheet(f"color: {ACCENT}; font-weight: bold;")
 layout.addRow(avans_baslik)

 self.avans_orani_spin = QDoubleSpinBox()
 self.avans_orani_spin.setRange(0, 30)
 self.avans_orani_spin.setDecimals(1)
 self.avans_orani_spin.setSuffix(" %")
 self.avans_orani_spin.setValue(30.0)
 layout.addRow("Avans Oranı:", self.avans_orani_spin)

 self.verilen_avans_spin = QDoubleSpinBox()
 self.verilen_avans_spin.setRange(0, 99_999_999_999)
 self.verilen_avans_spin.setDecimals(2)
 self.verilen_avans_spin.setSuffix(" TL")
 self.verilen_avans_spin.setSingleStep(10_000)
 layout.addRow("Verilen Avans:", self.verilen_avans_spin)

 self.onceki_mahsup_spin = QDoubleSpinBox()
 self.onceki_mahsup_spin.setRange(0, 99_999_999_999)
 self.onceki_mahsup_spin.setDecimals(2)
 self.onceki_mahsup_spin.setSuffix(" TL")
 layout.addRow("Önceki Mahsuplar:", self.onceki_mahsup_spin)

 sep2 = QFrame()
 sep2.setFrameShape(QFrame.Shape.HLine)
 sep2.setStyleSheet("color: #2a4a7f;")
 layout.addRow(sep2)

 # Kesin teminat
 kt_baslik = QLabel("Kesin Teminat")
 kt_baslik.setStyleSheet(f"color: {ACCENT}; font-weight: bold;")
 layout.addRow(kt_baslik)

 self.kt_tamamlandi_check = QCheckBox("Kesin teminat limiti tamamlandı")
 self.kt_tamamlandi_check.setStyleSheet(f"color: {TEXT_GRAY};")
 layout.addRow(self.kt_tamamlandi_check)

 sep3 = QFrame()
 sep3.setFrameShape(QFrame.Shape.HLine)
 sep3.setStyleSheet("color: #2a4a7f;")
 layout.addRow(sep3)

 # Gecikme
 gecikme_baslik = QLabel("Gecikme Cezası")
 gecikme_baslik.setStyleSheet(f"color: {ACCENT}; font-weight: bold;")
 layout.addRow(gecikme_baslik)

 self.gecikme_gun_spin = QSpinBox()
 self.gecikme_gun_spin.setRange(0, 999)
 self.gecikme_gun_spin.setSuffix(" gün")
 layout.addRow("Gecikme Günü:", self.gecikme_gun_spin)

 sep4 = QFrame()
 sep4.setFrameShape(QFrame.Shape.HLine)
 sep4.setStyleSheet("color: #2a4a7f;")
 layout.addRow(sep4)

 # Seçenekler
 secenekler_baslik = QLabel("Kesinti Seçenekleri")
 secenekler_baslik.setStyleSheet(f"color: {ACCENT}; font-weight: bold;")
 layout.addRow(secenekler_baslik)

 self.sgk_check = QCheckBox("SGK Prim Kesintisi (%1)")
 self.sgk_check.setChecked(True)
 self.sgk_check.setStyleSheet(f"color: {TEXT_GRAY};")
 layout.addRow(self.sgk_check)

 self.gv_check = QCheckBox("Gelir Vergisi Stopajı (%3)")
 self.gv_check.setChecked(True)
 self.gv_check.setStyleSheet(f"color: {TEXT_GRAY};")
 layout.addRow(self.gv_check)

 return grp

 def _build_sonuc_panel(self) -> QWidget:
 w = QWidget()
 layout = QVBoxLayout(w)
 layout.setContentsMargins(0, 0, 0, 0)
 layout.setSpacing(8)

 # Kesinti tablosu
 tablo_baslik = QLabel("Kesinti Dökümü")
 tablo_baslik.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 13px;")
 layout.addWidget(tablo_baslik)

 self.kesinti_table = QTableWidget(8, 3)
 self.kesinti_table.setHorizontalHeaderLabels(["Kesinti Kalemi", "Oran", "Tutar (TL)"])
 self.kesinti_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
 self.kesinti_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
 self.kesinti_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
 self.kesinti_table.verticalHeader().setVisible(False)
 self.kesinti_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 self.kesinti_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
 self.kesinti_table.setAlternatingRowColors(True)
 layout.addWidget(self.kesinti_table)

 # Özet kartlar
 ozet_grp = QGroupBox("Özet")
 ozet_layout = QFormLayout(ozet_grp)

 self.brut_label = self._ozet_label()
 self.kesinti_label = self._ozet_label(renk=RED)
 self.net_label = self._ozet_label(renk=GREEN, buyuk=True)

 ozet_layout.addRow("Brüt Hakediş:", self.brut_label)
 ozet_layout.addRow("Toplam Kesinti:", self.kesinti_label)
 ozet_layout.addRow("NET ÖDENECEK:", self.net_label)

 layout.addWidget(ozet_grp)

 return w

 def _ozet_label(self, renk: str = TEXT_WHITE, buyuk: bool = False) -> QLabel:
 lbl = QLabel("—")
 size = 14 if buyuk else 13
 weight = QFont.Weight.Bold
 lbl.setFont(QFont("Segoe UI", size, weight))
 lbl.setStyleSheet(f"color: {renk};")
 return lbl

 def _build_toolbar(self) -> QWidget:
 w = QWidget()
 layout = QHBoxLayout(w)
 layout.setContentsMargins(0, 0, 0, 0)

 btn_hesapla = QPushButton(" Hesapla")
 btn_hesapla.clicked.connect(self.hesapla)
 btn_hesapla.setStyleSheet(BUTTON_STYLE)

 btn_temizle = QPushButton(" Temizle")
 btn_temizle.clicked.connect(self.temizle)
 btn_temizle.setStyleSheet(BUTTON_STYLE.replace(ACCENT, "#555"))

 btn_excel = QPushButton(" Excel")
 btn_excel.clicked.connect(self.export_excel)
 btn_excel.setStyleSheet(BUTTON_STYLE.replace(ACCENT, GREEN))

 btn_pdf = QPushButton(" PDF")
 btn_pdf.clicked.connect(self.export_pdf)
 btn_pdf.setStyleSheet(BUTTON_STYLE.replace(ACCENT, "#8e44ad"))

 layout.addWidget(btn_hesapla)
 layout.addWidget(btn_temizle)
 layout.addStretch()
 layout.addWidget(btn_excel)
 layout.addWidget(btn_pdf)

 return w

 def _apply_styles(self) -> None:
 self.setStyleSheet(f"""
 QWidget {{
 background-color: {DARK_BG};
 color: {TEXT_WHITE};
 font-family: "Segoe UI", sans-serif;
 }}
 QGroupBox {{
 background-color: {CARD_BG};
 border: 1px solid #2a4a7f;
 border-radius: 6px;
 margin-top: 8px;
 padding: 8px;
 font-size: 12px;
 color: {TEXT_GRAY};
 }}
 QGroupBox::title {{
 subcontrol-origin: margin;
 left: 8px;
 color: {ACCENT};
 font-weight: bold;
 }}
 QTableWidget {{
 background-color: #0f1f3d;
 color: {TEXT_WHITE};
 gridline-color: #2a4a7f;
 border: 1px solid #2a4a7f;
 border-radius: 4px;
 font-size: 12px;
 }}
 QTableWidget::item:alternate {{ background-color: #142040; }}
 QHeaderView::section {{
 background-color: #0a1628;
 color: {ACCENT};
 border: none;
 padding: 5px;
 font-weight: bold;
 }}
 {INPUT_STYLE}
 """)

 # ------------------------------------------------------------------
 # Hesaplama
 # ------------------------------------------------------------------

 def hesapla(self) -> None:
 try:
 bilgi = HakedisKesintiBilgisi(
 sozlesme_bedeli = Decimal(str(self.sozlesme_spin.value())),
 hakedis_no = self.hakedis_no_spin.value(),
 hakedis_tarihi = date.today(),
 brut_hakedis = Decimal(str(self.brut_spin.value())),
 avans_orani = Decimal(str(self.avans_orani_spin.value() / 100)),
 verilen_avans = Decimal(str(self.verilen_avans_spin.value())),
 onceki_avans_mahsubu = Decimal(str(self.onceki_mahsup_spin.value())),
 kesin_teminat_tamamlandi = self.kt_tamamlandi_check.isChecked(),
 gecikme_gun = self.gecikme_gun_spin.value(),
 sgk_kesinti_aktif = self.sgk_check.isChecked(),
 gv_stopaj_aktif = self.gv_check.isChecked(),
 )
 sonuc = self.engine.hesapla(bilgi)
 self._son_bilgi = bilgi
 self._son_sonuc = sonuc
 self._goster_sonuc(bilgi, sonuc)
 except Exception as e:
 QMessageBox.critical(self, "Hata", f"Hesaplama hatası:\n{e}")

 def _goster_sonuc(
 self, bilgi: HakedisKesintiBilgisi, sonuc: HakedisKesintleri
 ) -> None:
 satirlar = self.engine.ozet_dict(bilgi, sonuc)["satirlar"]

 self.kesinti_table.setRowCount(len(satirlar))
 for row, (kalem, tutar, oran) in enumerate(satirlar):
 self._set_cell(row, 0, kalem)
 self._set_cell(row, 1, oran, Qt.AlignmentFlag.AlignCenter)
 renk = RED if tutar < 0 else (GREEN if "NET" in kalem else TEXT_WHITE)
 self._set_cell(
 row, 2,
 f"{tutar:,.2f} TL",
 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
 renk
 )
 if "NET" in kalem:
 for col in range(3):
 item = self.kesinti_table.item(row, col)
 if item:
 f = item.font()
 f.setBold(True)
 item.setFont(f)
 item.setBackground(QColor("#0a2a0a"))

 # Özet
 self.brut_label.setText(f"{float(sonuc.brut_hakedis):,.2f} TL")
 self.kesinti_label.setText(f"–{float(sonuc.toplam_kesinti):,.2f} TL")
 net = float(sonuc.net_odeme)
 self.net_label.setText(f"{net:,.2f} TL")
 self.net_label.setStyleSheet(
 f"color: {GREEN};" if net >= 0 else f"color: {RED};"
 )

 # Uyarılar
 if sonuc.uyarilar:
 self.uyari_text.setText("\n".join(sonuc.uyarilar))
 else:
 self.uyari_text.clear()
 self.uyari_text.setPlaceholderText("Uyarı yok.")

 def _set_cell(
 self, row: int, col: int, text: str,
 align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
 color: str = TEXT_WHITE
 ) -> None:
 item = QTableWidgetItem(text)
 item.setTextAlignment(align)
 item.setForeground(QColor(color))
 self.kesinti_table.setItem(row, col, item)

 # ------------------------------------------------------------------
 # Temizle
 # ------------------------------------------------------------------

 def temizle(self) -> None:
 self.sozlesme_spin.setValue(0)
 self.brut_spin.setValue(0)
 self.verilen_avans_spin.setValue(0)
 self.onceki_mahsup_spin.setValue(0)
 self.gecikme_gun_spin.setValue(0)
 self.kt_tamamlandi_check.setChecked(False)
 self.kesinti_table.setRowCount(0)
 self.brut_label.setText("—")
 self.kesinti_label.setText("—")
 self.net_label.setText("—")
 self.uyari_text.clear()
 self._son_bilgi = None
 self._son_sonuc = None

 # ------------------------------------------------------------------
 # Export
 # ------------------------------------------------------------------

 def export_excel(self) -> None:
 if not self._son_bilgi or not self._son_sonuc:
 QMessageBox.warning(self, "Uyarı", "Önce hesaplama yapın.")
 return
 try:
 import openpyxl
 from openpyxl.styles import Font, PatternFill, Alignment
 from PyQt6.QtWidgets import QFileDialog

 path, _ = QFileDialog.getSaveFileName(
 self, "Excel Kaydet", "hakedis_kesintisi.xlsx",
 "Excel Dosyası (*.xlsx)"
 )
 if not path:
 return

 wb = openpyxl.Workbook()
 ws = wb.active
 ws.title = "Hakediş Kesintisi"

 # Başlık
 ws.merge_cells("A1:C1")
 ws["A1"] = f"HAKEDİŞ KESİNTİ HESABI — Hakediş No: {self._son_bilgi.hakedis_no}"
 ws["A1"].font = Font(bold=True, size=14, color="FFFFFF")
 ws["A1"].fill = PatternFill("solid", fgColor="003366")
 ws["A1"].alignment = Alignment(horizontal="center")

 ws["A2"] = f"Sözleşme Bedeli: {float(self._son_bilgi.sozlesme_bedeli):,.2f} TL"
 ws["A2"].font = Font(bold=True)

 # Tablo başlıkları
 ws.append([])
 ws.append(["Kesinti Kalemi", "Oran", "Tutar (TL)"])
 header_row = ws.max_row
 for col in range(1, 4):
 cell = ws.cell(header_row, col)
 cell.font = Font(bold=True, color="FFFFFF")
 cell.fill = PatternFill("solid", fgColor="003366")

 # Veri
 satirlar = self.engine.ozet_dict(self._son_bilgi, self._son_sonuc)["satirlar"]
 for kalem, tutar, oran in satirlar:
 ws.append([kalem, oran, round(tutar, 2)])
 if "NET" in kalem:
 r = ws.max_row
 for c in range(1, 4):
 ws.cell(r, c).font = Font(bold=True)
 ws.cell(r, c).fill = PatternFill("solid", fgColor="003300")

 ws.column_dimensions["A"].width = 38
 ws.column_dimensions["B"].width = 12
 ws.column_dimensions["C"].width = 20

 wb.save(path)
 QMessageBox.information(self, "Başarılı", f"Excel kaydedildi:\n{path}")

 except ImportError:
 QMessageBox.warning(self, "Eksik Kütüphane", "openpyxl kurulu değil.\npip install openpyxl")
 except Exception as e:
 QMessageBox.critical(self, "Hata", str(e))

 def export_pdf(self) -> None:
 if not self._son_bilgi or not self._son_sonuc:
 QMessageBox.warning(self, "Uyarı", "Önce hesaplama yapın.")
 return
 try:
 from reportlab.lib.pagesizes import A4
 from reportlab.lib import colors
 from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
 from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
 from reportlab.lib.units import cm
 from PyQt6.QtWidgets import QFileDialog

 path, _ = QFileDialog.getSaveFileName(
 self, "PDF Kaydet", "hakedis_kesintisi.pdf",
 "PDF Dosyası (*.pdf)"
 )
 if not path:
 return

 doc = SimpleDocTemplate(path, pagesize=A4,
 leftMargin=2*cm, rightMargin=2*cm,
 topMargin=2*cm, bottomMargin=2*cm)
 story = []
 styles = getSampleStyleSheet()

 baslik_style = ParagraphStyle(
 "baslik", parent=styles["Title"],
 fontSize=14, spaceAfter=6
 )
 story.append(Paragraph(
 f"HAKEDİŞ KESİNTİ HESABI — Hakediş No: {self._son_bilgi.hakedis_no}",
 baslik_style
 ))
 story.append(Paragraph(
 f"Sözleşme Bedeli: {float(self._son_bilgi.sozlesme_bedeli):,.2f} TL | "
 f"Tarih: {self._son_bilgi.hakedis_tarihi}",
 styles["Normal"]
 ))
 story.append(Spacer(1, 0.4*cm))

 satirlar = self.engine.ozet_dict(self._son_bilgi, self._son_sonuc)["satirlar"]

 tablo_veri = [["Kesinti Kalemi", "Oran", "Tutar (TL)"]]
 for kalem, tutar, oran in satirlar:
 tablo_veri.append([kalem, oran, f"{tutar:,.2f}"])

 tablo = Table(tablo_veri, colWidths=[10*cm, 3*cm, 4*cm])
 tablo_style = TableStyle([
 ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
 ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
 ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
 ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
 ("ROWBACKGROUNDS", (0, 1), (-1, -1),
 [colors.HexColor("#eaf0f8"), colors.HexColor("#ffffff")]),
 ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
 ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
 ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#003300")),
 ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
 ])
 tablo.setStyle(tablo_style)
 story.append(tablo)

 if self._son_sonuc.uyarilar:
 story.append(Spacer(1, 0.4*cm))
 for u in self._son_sonuc.uyarilar:
 story.append(Paragraph(u, styles["Normal"]))

 doc.build(story)
 QMessageBox.information(self, "Başarılı", f"PDF kaydedildi:\n{path}")

 except ImportError:
 QMessageBox.warning(
 self, "Eksik Kütüphane",
 "reportlab kurulu değil.\npip install reportlab"
 )
 except Exception as e:
 QMessageBox.critical(self, "Hata", str(e))
