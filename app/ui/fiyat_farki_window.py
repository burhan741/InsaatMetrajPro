"""
Fiyat Farkı Hesabı — UI Penceresi
====================================
4735 sayılı Kamu İhale Sözleşmeleri Kanunu md.8
TÜİK D1/D2/D3/A endeks katsayıları
"""
from __future__ import annotations

from decimal import Decimal

from PyQt6.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
 QGroupBox, QLabel, QDoubleSpinBox, QPushButton,
 QTableWidget, QTableWidgetItem, QHeaderView,
 QMessageBox, QFrame, QTextEdit, QSplitter,
 QToolBar, QScrollArea, QDialog, QDialogButtonBox,
 QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from app.core.fiyat_farki_engine import (
 FiyatFarkiEngine, EndeksKatsayi, FiyatFarkiSonucu
)

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
 QDoubleSpinBox, QLineEdit {{
 background-color: #0f3460;
 color: {TEXT_WHITE};
 border: 1px solid #2a4a7f;
 border-radius: 4px;
 padding: 4px 8px;
 font-size: 12px;
 }}
 QDoubleSpinBox:focus, QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
"""


# ---------------------------------------------------------------------------
# Poz Ekleme Diyalogu
# ---------------------------------------------------------------------------

class PozFiyatFarkiDialog(QDialog):
 """Yeni bir fiyat farkı kalemi ekle"""

 def __init__(self, parent=None) -> None:
 super().__init__(parent)
 self.setWindowTitle("Poz Fiyat Farkı Kalemi Ekle")
 self.setMinimumWidth(480)
 self._build()
 self.setStyleSheet(f"""
 QDialog {{background-color: {DARK_BG}; color: {TEXT_WHITE};}}
 QLabel {{color: {TEXT_GRAY};}}
 QGroupBox {{background-color: {CARD_BG}; border: 1px solid #2a4a7f;
 border-radius: 6px; margin-top: 8px; padding: 6px;}}
 QGroupBox::title {{color: {ACCENT}; font-weight: bold; left: 8px;}}
 {INPUT_STYLE}
 """)

 def _build(self) -> None:
 layout = QVBoxLayout(self)

 # Poz bilgisi
 poz_grp = QGroupBox("Poz Bilgisi")
 poz_form = QFormLayout(poz_grp)

 self.poz_kodu_edit = QLineEdit()
 self.poz_tanimi_edit = QLineEdit()
 self.imalat_spin = QDoubleSpinBox()
 self.imalat_spin.setRange(0, 99_999_999_999)
 self.imalat_spin.setDecimals(2)
 self.imalat_spin.setSuffix(" TL")
 self.imalat_spin.setSingleStep(10_000)

 poz_form.addRow("Poz Kodu:", self.poz_kodu_edit)
 poz_form.addRow("Poz Tanımı:", self.poz_tanimi_edit)
 poz_form.addRow("İmalat Bedeli:", self.imalat_spin)

 layout.addWidget(poz_grp)

 # Endeks katsayıları
 kat_grp = QGroupBox("Endeks Ağırlık Katsayıları (toplam ≤ 1.00)")
 kat_form = QFormLayout(kat_grp)

 def spin_kat():
 s = QDoubleSpinBox()
 s.setRange(0, 1)
 s.setDecimals(3)
 s.setSingleStep(0.05)
 return s

 self.d1_kat = spin_kat()
 self.d2_kat = spin_kat()
 self.d3_kat = spin_kat()
 self.a_kat = spin_kat()

 kat_form.addRow("D1 — Akaryakıt:", self.d1_kat)
 kat_form.addRow("D2 — Çelik/Demir:", self.d2_kat)
 kat_form.addRow("D3 — Diğer Malzeme:", self.d3_kat)
 kat_form.addRow("A — İşçilik/Ücret:", self.a_kat)

 layout.addWidget(kat_grp)

 # Temel endeksler
 temel_grp = QGroupBox("Temel Endeks Değerleri (P0 — Sözleşme Tarihi)")
 temel_form = QFormLayout(temel_grp)

 def spin_endeks():
 s = QDoubleSpinBox()
 s.setRange(0, 999_999)
 s.setDecimals(2)
 s.setValue(1000)
 return s

 self.temel_d1 = spin_endeks()
 self.temel_d2 = spin_endeks()
 self.temel_d3 = spin_endeks()
 self.temel_a = spin_endeks()

 temel_form.addRow("P0 D1:", self.temel_d1)
 temel_form.addRow("P0 D2:", self.temel_d2)
 temel_form.addRow("P0 D3:", self.temel_d3)
 temel_form.addRow("P0 A:", self.temel_a)

 layout.addWidget(temel_grp)

 # Uygulama endeksleri
 uyg_grp = QGroupBox("Uygulama Endeks Değerleri (Pn — Fiyat Farkı Dönemi)")
 uyg_form = QFormLayout(uyg_grp)

 self.uyg_d1 = spin_endeks()
 self.uyg_d2 = spin_endeks()
 self.uyg_d3 = spin_endeks()
 self.uyg_a = spin_endeks()

 uyg_form.addRow("Pn D1:", self.uyg_d1)
 uyg_form.addRow("Pn D2:", self.uyg_d2)
 uyg_form.addRow("Pn D3:", self.uyg_d3)
 uyg_form.addRow("Pn A:", self.uyg_a)

 layout.addWidget(uyg_grp)

 # Onay
 buttons = QDialogButtonBox(
 QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
 )
 buttons.accepted.connect(self.accept)
 buttons.rejected.connect(self.reject)
 layout.addWidget(buttons)

 def get_kalem(self) -> EndeksKatsayi:
 return EndeksKatsayi(
 poz_kodu = self.poz_kodu_edit.text().strip(),
 poz_tanimi = self.poz_tanimi_edit.text().strip(),
 d1_katsayi = Decimal(str(self.d1_kat.value())),
 d2_katsayi = Decimal(str(self.d2_kat.value())),
 d3_katsayi = Decimal(str(self.d3_kat.value())),
 a_katsayi = Decimal(str(self.a_kat.value())),
 temel_d1 = Decimal(str(self.temel_d1.value())),
 temel_d2 = Decimal(str(self.temel_d2.value())),
 temel_d3 = Decimal(str(self.temel_d3.value())),
 temel_a = Decimal(str(self.temel_a.value())),
 uygulama_d1 = Decimal(str(self.uyg_d1.value())),
 uygulama_d2 = Decimal(str(self.uyg_d2.value())),
 uygulama_d3 = Decimal(str(self.uyg_d3.value())),
 uygulama_a = Decimal(str(self.uyg_a.value())),
 imalat_bedeli = Decimal(str(self.imalat_spin.value())),
 )


# ---------------------------------------------------------------------------
# Ana Pencere
# ---------------------------------------------------------------------------

class FiyatFarkiWindow(QWidget):
 """Fiyat Farkı Hesabı ana penceresi."""

 def __init__(self, db=None, parent: QWidget | None = None) -> None:
 super().__init__(parent)
 self.db = db
 self.engine = FiyatFarkiEngine()
 self._kalemler: list[EndeksKatsayi] = []
 self._son_sonuc: FiyatFarkiSonucu | None = None
 self._build_ui()
 self._apply_styles()

 # ------------------------------------------------------------------
 # UI
 # ------------------------------------------------------------------

 def _build_ui(self) -> None:
 root = QVBoxLayout(self)
 root.setContentsMargins(12, 12, 12, 12)
 root.setSpacing(8)

 # Başlık
 baslik = QLabel(" Fiyat Farkı Hesabı")
 baslik.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
 baslik.setStyleSheet(f"color: {ACCENT};")
 root.addWidget(baslik)

 alt_b = QLabel("4735 md.8 — TÜİK D1/D2/D3/A Endeks Katsayıları")
 alt_b.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px;")
 root.addWidget(alt_b)

 sep = QFrame()
 sep.setFrameShape(QFrame.Shape.HLine)
 sep.setStyleSheet("color: #2a4a7f;")
 root.addWidget(sep)

 # Toolbar
 root.addWidget(self._build_toolbar())

 # Poz tablosu
 poz_lbl = QLabel("Poz Listesi")
 poz_lbl.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 13px;")
 root.addWidget(poz_lbl)

 self.poz_table = QTableWidget(0, 8)
 self.poz_table.setHorizontalHeaderLabels([
 "Poz Kodu", "Poz Tanımı", "İmalat Bedeli (TL)",
 "FF D1", "FF D2", "FF D3", "FF A",
 "Toplam FF (TL)"
 ])
 self.poz_table.horizontalHeader().setSectionResizeMode(
 1, QHeaderView.ResizeMode.Stretch
 )
 for col in [0, 2, 3, 4, 5, 6, 7]:
 self.poz_table.horizontalHeader().setSectionResizeMode(
 col, QHeaderView.ResizeMode.ResizeToContents
 )
 self.poz_table.verticalHeader().setVisible(False)
 self.poz_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 self.poz_table.setAlternatingRowColors(True)
 root.addWidget(self.poz_table)

 # Özet
 ozet_grp = QGroupBox("Toplam Özet")
 ozet_layout = QHBoxLayout(ozet_grp)

 self.toplam_imalat_lbl = self._ozet_lbl()
 self.toplam_ff_lbl = self._ozet_lbl(ACCENT, True)

 ozet_layout.addWidget(QLabel("Toplam İmalat Bedeli:"))
 ozet_layout.addWidget(self.toplam_imalat_lbl)
 ozet_layout.addStretch()
 ozet_layout.addWidget(QLabel("Toplam Fiyat Farkı:"))
 ozet_layout.addWidget(self.toplam_ff_lbl)

 root.addWidget(ozet_grp)

 # Uyarılar
 self.uyari_text = QTextEdit()
 self.uyari_text.setReadOnly(True)
 self.uyari_text.setMaximumHeight(60)
 self.uyari_text.setStyleSheet(
 f"background-color: {DARK_BG}; color: {YELLOW}; "
 "border: 1px solid #2a4a7f; font-size: 12px;"
 )
 root.addWidget(self.uyari_text)

 def _ozet_lbl(self, renk=TEXT_WHITE, buyuk=False):
 l = QLabel("—")
 l.setFont(QFont("Segoe UI", 13 if buyuk else 12, QFont.Weight.Bold))
 l.setStyleSheet(f"color: {renk};")
 return l

 def _build_toolbar(self) -> QWidget:
 w = QWidget()
 layout = QHBoxLayout(w)
 layout.setContentsMargins(0, 0, 0, 0)

 btn_ekle = QPushButton(" Poz Ekle")
 btn_ekle.clicked.connect(self.poz_ekle)
 btn_ekle.setStyleSheet(BUTTON_STYLE)

 btn_sil = QPushButton(" Poz Sil")
 btn_sil.clicked.connect(self.poz_sil)
 btn_sil.setStyleSheet(BUTTON_STYLE.replace(ACCENT, RED))

 btn_hesapla = QPushButton(" Hesapla")
 btn_hesapla.clicked.connect(self.hesapla)
 btn_hesapla.setStyleSheet(BUTTON_STYLE)

 btn_excel = QPushButton(" Excel")
 btn_excel.clicked.connect(self.export_excel)
 btn_excel.setStyleSheet(BUTTON_STYLE.replace(ACCENT, GREEN))

 layout.addWidget(btn_ekle)
 layout.addWidget(btn_sil)
 layout.addWidget(btn_hesapla)
 layout.addStretch()
 layout.addWidget(btn_excel)

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
 # İşlevler
 # ------------------------------------------------------------------

 def poz_ekle(self) -> None:
 dlg = PozFiyatFarkiDialog(self)
 if dlg.exec() == QDialog.DialogCode.Accepted:
 self._kalemler.append(dlg.get_kalem())
 self._tablo_guncelle()

 def poz_sil(self) -> None:
 row = self.poz_table.currentRow()
 if 0 <= row < len(self._kalemler):
 self._kalemler.pop(row)
 self._tablo_guncelle()

 def _tablo_guncelle(self) -> None:
 self.poz_table.setRowCount(len(self._kalemler))
 for r, k in enumerate(self._kalemler):
 self.poz_table.setItem(r, 0, QTableWidgetItem(k.poz_kodu))
 self.poz_table.setItem(r, 1, QTableWidgetItem(k.poz_tanimi))
 self._num_item(r, 2, float(k.imalat_bedeli))
 # FF değerleri önce hesap yapılmamışsa sıfır göster
 self.poz_table.setItem(r, 3, QTableWidgetItem("—"))
 self.poz_table.setItem(r, 4, QTableWidgetItem("—"))
 self.poz_table.setItem(r, 5, QTableWidgetItem("—"))
 self.poz_table.setItem(r, 6, QTableWidgetItem("—"))
 self.poz_table.setItem(r, 7, QTableWidgetItem("—"))

 def hesapla(self) -> None:
 if not self._kalemler:
 QMessageBox.warning(self, "Uyarı", "Önce poz ekleyin.")
 return
 sonuc = self.engine.hesapla(self._kalemler)
 self._son_sonuc = sonuc

 for r, hk in enumerate(sonuc.kalemler):
 self._num_item(r, 2, float(hk.imalat_bedeli))
 self._ff_item(r, 3, float(hk.ff_d1))
 self._ff_item(r, 4, float(hk.ff_d2))
 self._ff_item(r, 5, float(hk.ff_d3))
 self._ff_item(r, 6, float(hk.ff_a))
 self._ff_item(r, 7, float(hk.toplam_ff), bold=True)

 self.toplam_imalat_lbl.setText(
 f"{float(sonuc.toplam_imalat):,.2f} TL"
 )
 self.toplam_ff_lbl.setText(
 f"{float(sonuc.toplam_fiyat_farki):,.2f} TL"
 )
 renk = GREEN if sonuc.toplam_fiyat_farki >= 0 else RED
 self.toplam_ff_lbl.setStyleSheet(f"color: {renk}; font-weight: bold;")

 self.uyari_text.setText("\n".join(sonuc.uyarilar) if sonuc.uyarilar else "")

 def _num_item(self, row: int, col: int, val: float) -> None:
 item = QTableWidgetItem(f"{val:,.2f}")
 item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
 self.poz_table.setItem(row, col, item)

 def _ff_item(self, row: int, col: int, val: float, bold: bool = False) -> None:
 item = QTableWidgetItem(f"{val:,.2f}")
 item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
 renk = GREEN if val >= 0 else RED
 item.setForeground(QColor(renk))
 if bold:
 f = item.font()
 f.setBold(True)
 item.setFont(f)
 self.poz_table.setItem(row, col, item)

 # ------------------------------------------------------------------
 # Excel export
 # ------------------------------------------------------------------

 def export_excel(self) -> None:
 if not self._son_sonuc:
 QMessageBox.warning(self, "Uyarı", "Önce hesaplama yapın.")
 return
 try:
 import openpyxl
 from openpyxl.styles import Font, PatternFill, Alignment
 from PyQt6.QtWidgets import QFileDialog

 path, _ = QFileDialog.getSaveFileName(
 self, "Excel Kaydet", "fiyat_farki.xlsx",
 "Excel Dosyası (*.xlsx)"
 )
 if not path:
 return

 wb = openpyxl.Workbook()
 ws = wb.active
 ws.title = "Fiyat Farkı"

 ws.merge_cells("A1:H1")
 ws["A1"] = "FİYAT FARKI HESABI — 4735 md.8"
 ws["A1"].font = Font(bold=True, size=13, color="FFFFFF")
 ws["A1"].fill = PatternFill("solid", fgColor="003366")
 ws["A1"].alignment = Alignment(horizontal="center")

 basliklar = [
 "Poz Kodu", "Poz Tanımı", "İmalat Bedeli (TL)",
 "FF D1", "FF D2", "FF D3", "FF A", "Toplam FF (TL)"
 ]
 ws.append(basliklar)
 h_row = ws.max_row
 for c in range(1, 9):
 ws.cell(h_row, c).font = Font(bold=True, color="FFFFFF")
 ws.cell(h_row, c).fill = PatternFill("solid", fgColor="003366")

 ozet = self.engine.ozet_dict(self._son_sonuc)
 for k in ozet["kalemler"]:
 ws.append([
 k["poz_kodu"], k["poz_tanimi"],
 round(k["imalat_bedeli"], 2),
 round(k["ff_d1"], 2), round(k["ff_d2"], 2),
 round(k["ff_d3"], 2), round(k["ff_a"], 2),
 round(k["toplam_ff"], 2),
 ])

 ws.append([])
 ws.append([
 "TOPLAM", "",
 round(ozet["toplam_imalat"], 2),
 "", "", "", "",
 round(ozet["toplam_fiyat_farki"], 2),
 ])
 tot_row = ws.max_row
 for c in range(1, 9):
 ws.cell(tot_row, c).font = Font(bold=True)

 ws.column_dimensions["A"].width = 12
 ws.column_dimensions["B"].width = 35
 for col in ["C", "D", "E", "F", "G", "H"]:
 ws.column_dimensions[col].width = 18

 wb.save(path)
 QMessageBox.information(self, "Başarılı", f"Excel kaydedildi:\n{path}")

 except ImportError:
 QMessageBox.warning(self, "Eksik", "pip install openpyxl")
 except Exception as e:
 QMessageBox.critical(self, "Hata", str(e))
