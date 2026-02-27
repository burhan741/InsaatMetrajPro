"""
SGK Asgari İşçilik Hesabı — UI Penceresi
==========================================
5510 sayılı Kanun md.85
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date

from PyQt6.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
 QGroupBox, QLabel, QDoubleSpinBox, QSpinBox,
 QCheckBox, QPushButton, QTableWidget, QTableWidgetItem,
 QHeaderView, QMessageBox, QComboBox, QFrame, QTextEdit,
 QDateEdit, QTabWidget
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from app.core.sgk_iscilik_engine import (
 SgkIscilkEngine, SgkIscilkBilgisi, SgkIscilkSonucu,
 IS_KOLU_ORANLARI, ASGARI_UCRET_AYLIK_2025
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
 QDoubleSpinBox, QSpinBox, QComboBox, QDateEdit {{
 background-color: #0f3460;
 color: {TEXT_WHITE};
 border: 1px solid #2a4a7f;
 border-radius: 4px;
 padding: 4px 8px;
 font-size: 13px;
 }}
 QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QDateEdit:focus {{
 border: 1px solid {ACCENT};
 }}
 QComboBox QAbstractItemView {{
 background-color: #0f3460;
 color: {TEXT_WHITE};
 selection-background-color: {ACCENT};
 }}
"""


class SgkIscilkWindow(QWidget):
 """SGK Asgari İşçilik hesaplama ana penceresi."""

 def __init__(self, db=None, parent: QWidget | None = None) -> None:
     super().__init__(parent)
 self.db = db
 self.engine = SgkIscilkEngine()
 self._son_bilgi: SgkIscilkBilgisi | None = None
 self._son_sonuc: SgkIscilkSonucu | None = None
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
 baslik = QLabel(" SGK Asgari İşçilik Hesabı")
 baslik.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
 baslik.setStyleSheet(f"color: {ACCENT}; padding-bottom: 4px;")
 root.addWidget(baslik)

 alt_b = QLabel("5510 Sayılı Kanun md.85 — Zorunlu Sigortalı Gün Hesabı")
 alt_b.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px;")
 root.addWidget(alt_b)

 sep = QFrame()
 sep.setFrameShape(QFrame.Shape.HLine)
 sep.setStyleSheet("color: #2a4a7f;")
 root.addWidget(sep)

 # İçerik
 icerik = QHBoxLayout()
 icerik.setSpacing(12)
 icerik.addWidget(self._build_form(), 2)
 icerik.addWidget(self._build_sonuc(), 3)
 root.addLayout(icerik)

 # Toolbar
 root.addWidget(self._build_toolbar())

 # Uyarılar
 self.uyari_text = QTextEdit()
 self.uyari_text.setReadOnly(True)
 self.uyari_text.setMaximumHeight(70)
 self.uyari_text.setStyleSheet(
 f"background-color: {DARK_BG}; color: {YELLOW}; "
 "border: 1px solid #2a4a7f; font-size: 12px;"
 )
 root.addWidget(self.uyari_text)

 def _build_form(self) -> QGroupBox:
     grp = QGroupBox("İşçilik Bilgileri")
 layout = QFormLayout(grp)
 layout.setSpacing(8)

 # Sözleşme bedeli
 self.sozlesme_spin = QDoubleSpinBox()
 self.sozlesme_spin.setRange(0, 99_999_999_999)
 self.sozlesme_spin.setDecimals(2)
 self.sozlesme_spin.setSuffix(" TL")
 self.sozlesme_spin.setSingleStep(100_000)
 layout.addRow("Sözleşme Bedeli:", self.sozlesme_spin)

 # İş kolu
 self.is_kolu_combo = QComboBox()
 for kod, aciklama in SgkIscilkEngine.is_kolu_secenekleri():
     self.is_kolu_combo.addItem(aciklama, kod)
 layout.addRow("İş Kolu:", self.is_kolu_combo)

 # Özel oran
 self.ozel_oran_spin = QDoubleSpinBox()
 self.ozel_oran_spin.setRange(0, 30)
 self.ozel_oran_spin.setDecimals(2)
 self.ozel_oran_spin.setSuffix(" %")
 self.ozel_oran_spin.setEnabled(False)
 layout.addRow("Özel Oran:", self.ozel_oran_spin)
 self.is_kolu_combo.currentIndexChanged.connect(self._is_kolu_degisti)

 sep = QFrame()
 sep.setFrameShape(QFrame.Shape.HLine)
 sep.setStyleSheet("color: #2a4a7f;")
 layout.addRow(sep)

 # Tarihler
 self.baslangic_edit = QDateEdit()
 self.baslangic_edit.setCalendarPopup(True)
 self.baslangic_edit.setDate(QDate.currentDate())
 layout.addRow("İşin Başlangıcı:", self.baslangic_edit)

 self.bitis_edit = QDateEdit()
 self.bitis_edit.setCalendarPopup(True)
 self.bitis_edit.setDate(QDate.currentDate().addYears(1))
 layout.addRow("İşin Bitişi:", self.bitis_edit)

 sep2 = QFrame()
 sep2.setFrameShape(QFrame.Shape.HLine)
 sep2.setStyleSheet("color: #2a4a7f;")
 layout.addRow(sep2)

 # Ücret
 self.ucret_spin = QDoubleSpinBox()
 self.ucret_spin.setRange(0, 9_999_999)
 self.ucret_spin.setDecimals(2)
 self.ucret_spin.setSuffix(" TL")
 self.ucret_spin.setValue(float(ASGARI_UCRET_AYLIK_2025))
 layout.addRow("Aylık Brüt Ücret:", self.ucret_spin)

 # Teşvik
 self.tesvik_check = QCheckBox("5510/81-ı Teşviki (işveren %15.5)")
 self.tesvik_check.setStyleSheet(f"color: {TEXT_GRAY};")
 layout.addRow(self.tesvik_check)

 return grp

 def _is_kolu_degisti(self, idx: int) -> None:
     kod = self.is_kolu_combo.currentData()
 self.ozel_oran_spin.setEnabled(kod == "ozel")

 def _build_sonuc(self) -> QWidget:
     w = QWidget()
 layout = QVBoxLayout(w)
 layout.setContentsMargins(0, 0, 0, 0)

 # Özet
 ozet_grp = QGroupBox("Hesap Özeti")
 ozet_form = QFormLayout(ozet_grp)

 def lbl(renk=TEXT_WHITE, buyuk=False):
     l = QLabel("—")
 l.setFont(QFont("Segoe UI", 14 if buyuk else 12, QFont.Weight.Bold))
 l.setStyleSheet(f"color: {renk};")
 return l

 self.zorunlu_tutar_lbl = lbl(ACCENT, True)
 self.zorunlu_ay_lbl = lbl()
 self.zorunlu_gun_lbl = lbl()
 self.ort_isci_lbl = lbl()
 self.isveren_prim_lbl = lbl(YELLOW)

 ozet_form.addRow("Zorunlu İşçilik Tutarı:", self.zorunlu_tutar_lbl)
 ozet_form.addRow("Zorunlu Sigortalı Ay:", self.zorunlu_ay_lbl)
 ozet_form.addRow("Zorunlu Sigortalı Gün:", self.zorunlu_gun_lbl)
 ozet_form.addRow("Ort. Aylık İşçi Sayısı:", self.ort_isci_lbl)
 ozet_form.addRow("İşveren SGK Prim Tutarı:", self.isveren_prim_lbl)

 layout.addWidget(ozet_grp)

 # Aylık prim takvimi
 takvim_lbl = QLabel("Aylık Prim Takvimi")
 takvim_lbl.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 13px;")
 layout.addWidget(takvim_lbl)

 self.takvim_table = QTableWidget(0, 4)
 self.takvim_table.setHorizontalHeaderLabels(
 ["Ay", "Zorunlu Gün", "Zorunlu Ay", "İşveren Prim (TL)"]
 )
 self.takvim_table.horizontalHeader().setSectionResizeMode(
 QHeaderView.ResizeMode.Stretch
 )
 self.takvim_table.verticalHeader().setVisible(False)
 self.takvim_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 self.takvim_table.setAlternatingRowColors(True)
 layout.addWidget(self.takvim_table)

 return w

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

 layout.addWidget(btn_hesapla)
 layout.addWidget(btn_temizle)
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
         bas_q = self.baslangic_edit.date()
         bit_q = self.bitis_edit.date()
         bilgi = SgkIscilkBilgisi(
 sozlesme_bedeli = Decimal(str(self.sozlesme_spin.value())),
 is_kolu_kodu = self.is_kolu_combo.currentData(),
 ozel_oran = Decimal(str(self.ozel_oran_spin.value() / 100))
 if self.is_kolu_combo.currentData() == "ozel" else None,
 baslangic_tarihi = date(bas_q.year(), bas_q.month(), bas_q.day()),
 bitis_tarihi = date(bit_q.year(), bit_q.month(), bit_q.day()),
 aylik_brut_ucret = Decimal(str(self.ucret_spin.value())),
 tesvik_aktif = self.tesvik_check.isChecked(),
 )
         sonuc = self.engine.hesapla(bilgi)
         self._son_bilgi = bilgi
         self._son_sonuc = sonuc
         self._goster_sonuc(sonuc)
     except Exception as e:
         QMessageBox.critical(self, "Hata", str(e))

 def _goster_sonuc(self, sonuc: SgkIscilkSonucu) -> None:
     self.zorunlu_tutar_lbl.setText(
 f"{float(sonuc.zorunlu_iscilik_tutari):,.2f} TL"
 )
 self.zorunlu_ay_lbl.setText(f"{float(sonuc.zorunlu_sigortalı_ay):.2f} ay")
 self.zorunlu_gun_lbl.setText(f"{sonuc.zorunlu_sigortalı_gun} gün")
 self.ort_isci_lbl.setText(f"{float(sonuc.aylik_sigortalı_sayisi):.2f} kişi/ay")
 self.isveren_prim_lbl.setText(f"{float(sonuc.isveren_sgk_tutari):,.2f} TL")

 # Takvim
 takvim = sonuc.uylik_prim_takvimi
 self.takvim_table.setRowCount(len(takvim))
 for r, satir in enumerate(takvim):
     self.takvim_table.setItem(r, 0,
 QTableWidgetItem(f"{satir['ay_adi']} {satir['yil']}"))
 self.takvim_table.setItem(r, 1,
 QTableWidgetItem(str(satir['zorunlu_gun'])))
 self.takvim_table.setItem(r, 2,
 QTableWidgetItem(f"{satir['zorunlu_ay']:.2f}"))
 item = QTableWidgetItem(f"{satir['isveren_prim']:,.2f}")
 item.setTextAlignment(
 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
 )
 self.takvim_table.setItem(r, 3, item)

 # Uyarılar
 if sonuc.uyarilar:
     self.uyari_text.setText("\n".join(sonuc.uyarilar))
 else:
     self.uyari_text.clear()

 def temizle(self) -> None:
     self.sozlesme_spin.setValue(0)
 self.takvim_table.setRowCount(0)
 self.zorunlu_tutar_lbl.setText("—")
 self.zorunlu_ay_lbl.setText("—")
 self.zorunlu_gun_lbl.setText("—")
 self.ort_isci_lbl.setText("—")
 self.isveren_prim_lbl.setText("—")
 self.uyari_text.clear()

 # ------------------------------------------------------------------
 # Excel export
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
 self, "Excel Kaydet", "sgk_asgari_iscilik.xlsx",
 "Excel Dosyası (*.xlsx)"
 )
     if not path:
         return

     wb = openpyxl.Workbook()
     ws = wb.active
     ws.title = "SGK Asgari İşçilik"

     ws.merge_cells("A1:D1")
     ws["A1"] = "SGK ASGARİ İŞÇİLİK HESABI"
     ws["A1"].font = Font(bold=True, size=14, color="FFFFFF")
     ws["A1"].fill = PatternFill("solid", fgColor="003366")
     ws["A1"].alignment = Alignment(horizontal="center")

     ozet = self.engine.ozet_dict(self._son_bilgi, self._son_sonuc)
     ws.append([
 f"Sözleşme Bedeli: {ozet['sozlesme_bedeli']:,.2f} TL",
 f"İş Kolu: {ozet['is_kolu']}",
 f"Oran: %{ozet['uygulanan_oran_pct']:.2f}",
 f"Zorunlu: {ozet['zorunlu_iscilik_tutari']:,.2f} TL",
 ])
     ws.append([
 f"Zorunlu Sigortalı Gün: {ozet['zorunlu_sigortalı_gun']}",
 f"Ort. İşçi: {ozet['ortalama_aylik_isci']:.2f}/ay",
 f"İşveren SGK Prim: {ozet['isveren_sgk_tutari']:,.2f} TL",
 "",
 ])
     ws.append([])
     ws.append(["Ay", "Zorunlu Gün", "Zorunlu Ay", "İşveren Prim (TL)"])

     for satir in ozet["takvim"]:
         ws.append([
 f"{satir['ay_adi']} {satir['yil']}",
 satir["zorunlu_gun"],
 round(satir["zorunlu_ay"], 2),
 round(satir["isveren_prim"], 2),
 ])

     for col in ["A", "B", "C", "D"]:
         ws.column_dimensions[col].width = 22

     wb.save(path)
     QMessageBox.information(self, "Başarılı", f"Excel kaydedildi:\n{path}")

 except ImportError:
     QMessageBox.warning(self, "Eksik", "pip install openpyxl")
 except Exception as e:
     QMessageBox.critical(self, "Hata", str(e))
