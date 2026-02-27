"""
Profesyonel Teklif Hazırlama — UI Penceresi
=============================================
Serbest piyasa özel müşteri teklifi.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date

from PyQt6.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
 QGroupBox, QLabel, QDoubleSpinBox, QPushButton,
 QTableWidget, QTableWidgetItem, QHeaderView,
 QMessageBox, QFrame, QTextEdit, QLineEdit,
 QComboBox, QSpinBox, QCheckBox, QDateEdit,
 QDialog, QDialogButtonBox, QFileDialog,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from app.core.teklif_engine import (
 TeklifEngine, TeklifBilgisi, TeklifKalemi,
 PROJE_TURLERI, ODEME_PLANLARI,
)

# ---------------------------------------------------------------------------
# Stil sabitleri (projeyle uyumlu)
# ---------------------------------------------------------------------------
DARK_BG = "#1a1a2e"
CARD_BG = "#16213e"
ACCENT = "#00BFFF"
TEXT_WHITE = "#e0e0e0"
TEXT_GRAY = "#a0a0b0"
GREEN = "#27ae60"
RED = "#e74c3c"
YELLOW = "#f39c12"
ORANGE = "#e67e22"

BUTTON_STYLE = f"""
 QPushButton {{
 background-color: {ACCENT};
 color: #000;
 border: none;
 border-radius: 4px;
 padding: 6px 16px;
 font-weight: bold;
 }}
 QPushButton:hover {{ background-color: #33d6ff; }}
"""

INPUT_STYLE = f"""
 QDoubleSpinBox, QLineEdit, QComboBox, QSpinBox, QDateEdit, QTextEdit {{
 background-color: #0f3460;
 color: {TEXT_WHITE};
 border: 1px solid #2a4a7f;
 border-radius: 4px;
 padding: 4px 8px;
 }}
 QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus,
 QSpinBox:focus, QDateEdit:focus, QTextEdit:focus {{
 border: 1px solid {ACCENT};
 }}
 QComboBox QAbstractItemView {{
 background-color: #0f3460;
 color: {TEXT_WHITE};
 selection-background-color: {ACCENT};
 }}
"""


# ---------------------------------------------------------------------------
# Kalem ekleme / düzenleme dialog
# ---------------------------------------------------------------------------

class KalemDialog(QDialog):
 """Yeni iş kalemi ekle veya düzenle."""

 def __init__(self, kalem: TeklifKalemi | None = None, parent=None):
 super().__init__(parent)
 self.setWindowTitle("İş Kalemi")
 self.setMinimumWidth(440)
 self._build()
 self.setStyleSheet(f"""
 QDialog {{background-color: {DARK_BG}; color: {TEXT_WHITE};}}
 QLabel {{color: {TEXT_GRAY};}}
 {INPUT_STYLE}
 """)
 if kalem:
 self._doldur(kalem)

 def _build(self):
 layout = QFormLayout(self)
 layout.setSpacing(8)

 self.poz_edit = QLineEdit(); self.poz_edit.setPlaceholderText("05.003")
 self.tanim_edit = QLineEdit(); self.tanim_edit.setPlaceholderText("Briket Duvar - 20cm")
 self.birim_combo = QComboBox()
 self.birim_combo.addItems(["m²", "m³", "m", "adet", "kg", "ton", "lt", "takım", "götürü"])
 self.miktar_spin = QDoubleSpinBox()
 self.miktar_spin.setRange(0, 999_999)
 self.miktar_spin.setDecimals(2)
 self.fiyat_spin = QDoubleSpinBox()
 self.fiyat_spin.setRange(0, 99_999_999)
 self.fiyat_spin.setDecimals(2)
 self.fiyat_spin.setSuffix(" ₺")
 self.not_edit = QLineEdit(); self.not_edit.setPlaceholderText("İsteğe bağlı not…")

 layout.addRow("Poz No:", self.poz_edit)
 layout.addRow("Tanım:", self.tanim_edit)
 layout.addRow("Birim:", self.birim_combo)
 layout.addRow("Miktar:", self.miktar_spin)
 layout.addRow("Birim Fiyat:", self.fiyat_spin)
 layout.addRow("Not:", self.not_edit)

 btns = QDialogButtonBox(
 QDialogButtonBox.StandardButton.Ok |
 QDialogButtonBox.StandardButton.Cancel
 )
 btns.accepted.connect(self.accept)
 btns.rejected.connect(self.reject)
 layout.addRow(btns)

 def _doldur(self, k: TeklifKalemi):
 self.poz_edit.setText(k.poz_no)
 self.tanim_edit.setText(k.tanim)
 idx = self.birim_combo.findText(k.birim)
 if idx >= 0:
 self.birim_combo.setCurrentIndex(idx)
 self.miktar_spin.setValue(float(k.miktar))
 self.fiyat_spin.setValue(float(k.birim_fiyat))
 self.not_edit.setText(k.notlar)

 def get_kalem(self) -> TeklifKalemi:
 return TeklifKalemi(
 poz_no = self.poz_edit.text().strip(),
 tanim = self.tanim_edit.text().strip(),
 birim = self.birim_combo.currentText(),
 miktar = Decimal(str(self.miktar_spin.value())),
 birim_fiyat = Decimal(str(self.fiyat_spin.value())),
 notlar = self.not_edit.text().strip(),
 )


# ---------------------------------------------------------------------------
# Ana teklif penceresi
# ---------------------------------------------------------------------------

class TeklifWindow(QWidget):
 """Profesyonel müşteri teklifi hazırlama penceresi."""

 def __init__(self, db=None, parent: QWidget | None = None):
 super().__init__(parent)
 self.db = db
 self.engine = TeklifEngine()
 self._kalemler: list[TeklifKalemi] = []
 self._sira_sayac = 1
 self._build_ui()
 self._apply_styles()
 self._yeni_teklif()

 # ------------------------------------------------------------------
 # UI inşa
 # ------------------------------------------------------------------

 def _build_ui(self):
 root = QVBoxLayout(self)
 root.setContentsMargins(12, 12, 12, 12)
 root.setSpacing(8)

 # Başlık
 baslik = QLabel(" Profesyonel Müşteri Teklifi")
 baslik.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
 baslik.setStyleSheet(f"color: {ACCENT};")
 root.addWidget(baslik)

 alt = QLabel("Serbest Piyasa — KDV dahil, kar marjlı teklif hazırlama")
 alt.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px;")
 root.addWidget(alt)

 sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
 sep.setStyleSheet("color: #2a4a7f;"); root.addWidget(sep)

 # Üst iki panel
 ust = QHBoxLayout()
 ust.addWidget(self._build_musteri_panel(), 3)
 ust.addWidget(self._build_proje_panel(), 3)
 ust.addWidget(self._build_ozet_panel(), 2)
 root.addLayout(ust)

 # Toolbar
 root.addWidget(self._build_toolbar())

 # Kalem tablosu
 lbl = QLabel("İş Kalemleri")
 lbl.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 13px;")
 root.addWidget(lbl)
 root.addWidget(self._build_tablo())

 # Alt satır: notlar + ödeme planı
 alt_layout = QHBoxLayout()
 alt_layout.addWidget(self._build_notlar(), 2)
 alt_layout.addWidget(self._build_odeme_panel(), 1)
 root.addLayout(alt_layout)

 def _build_musteri_panel(self) -> QGroupBox:
 grp = QGroupBox("Müşteri Bilgileri")
 lay = QFormLayout(grp)

 self.musteri_adi = QLineEdit(); self.musteri_adi.setPlaceholderText("Ad Soyad / Firma Adı")
 self.musteri_tel = QLineEdit(); self.musteri_tel.setPlaceholderText("0 5xx xxx xx xx")
 self.musteri_adres = QLineEdit(); self.musteri_adres.setPlaceholderText("Mahalle, İlçe, İl")
 self.musteri_tc_vkn = QLineEdit(); self.musteri_tc_vkn.setPlaceholderText("TC / Vergi No")
 self.stopaj_check = QCheckBox("Gerçek kişi — %3 stopaj uygulanır")

 lay.addRow("Ad / Firma:", self.musteri_adi)
 lay.addRow("Telefon:", self.musteri_tel)
 lay.addRow("Adres:", self.musteri_adres)
 lay.addRow("TC / VKN:", self.musteri_tc_vkn)
 lay.addRow(self.stopaj_check)
 return grp

 def _build_proje_panel(self) -> QGroupBox:
 grp = QGroupBox("Proje Bilgileri")
 lay = QFormLayout(grp)

 self.proje_adi = QLineEdit(); self.proje_adi.setPlaceholderText("Konut Yapımı / Tadilat…")
 self.proje_adresi = QLineEdit(); self.proje_adresi.setPlaceholderText("Şantiye adresi")
 self.proje_turu = QComboBox(); self.proje_turu.addItems(PROJE_TURLERI)
 self.teklif_no_edit = QLineEdit(); self.teklif_no_edit.setReadOnly(True)
 self.tarih_edit = QDateEdit(); self.tarih_edit.setCalendarPopup(True)
 self.tarih_edit.setDate(QDate.currentDate())
 self.gecerlilik_spin = QSpinBox()
 self.gecerlilik_spin.setRange(7, 90); self.gecerlilik_spin.setValue(30)
 self.gecerlilik_spin.setSuffix(" gün")
 self.firma_adi = QLineEdit(); self.firma_adi.setPlaceholderText("Teklifi veren firma")

 lay.addRow("Teklif No:", self.teklif_no_edit)
 lay.addRow("Tarih:", self.tarih_edit)
 lay.addRow("Geçerlilik:", self.gecerlilik_spin)
 lay.addRow("Proje Adı:", self.proje_adi)
 lay.addRow("Şantiye Adresi:", self.proje_adresi)
 lay.addRow("Proje Türü:", self.proje_turu)
 lay.addRow("Firmamız:", self.firma_adi)
 return grp

 def _build_ozet_panel(self) -> QGroupBox:
 grp = QGroupBox("Finansal Özet")
 lay = QFormLayout(grp)

 def lbl(renk=TEXT_WHITE, buyuk=False):
 l = QLabel("—")
 l.setFont(QFont("Segoe UI", 13 if buyuk else 12, QFont.Weight.Bold))
 l.setStyleSheet(f"color: {renk};")
 return l

 # Kar marjı ayarı
 self.kar_spin = QDoubleSpinBox()
 self.kar_spin.setRange(0, 100)
 self.kar_spin.setDecimals(1)
 self.kar_spin.setValue(20.0)
 self.kar_spin.setSuffix(" %")
 lay.addRow("Kar Marjı:", self.kar_spin)

 # KDV seçeneği
 self.kdv_haric_check = QCheckBox("KDV Hariç Teklif")
 lay.addRow(self.kdv_haric_check)

 sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
 sep.setStyleSheet("color: #2a4a7f;"); lay.addRow(sep)

 self.lbl_ara = lbl()
 self.lbl_kar = lbl(GREEN)
 self.lbl_matrah = lbl()
 self.lbl_kdv = lbl(YELLOW)
 self.lbl_stopaj = lbl(ORANGE)
 self.lbl_genel = lbl(ACCENT, True)
 self.lbl_avans = lbl(GREEN)

 lay.addRow("Ara Toplam:", self.lbl_ara)
 lay.addRow("Kar:", self.lbl_kar)
 lay.addRow("KDV Matrahı:", self.lbl_matrah)
 lay.addRow("KDV (%20):", self.lbl_kdv)
 lay.addRow("Stopaj (%3):", self.lbl_stopaj)
 lay.addRow("GENEL TOPLAM:", self.lbl_genel)
 lay.addRow("Avans:", self.lbl_avans)
 return grp

 def _build_toolbar(self) -> QWidget:
 w = QWidget()
 lay = QHBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0)

 def btn(label, color=ACCENT, slot=None):
 b = QPushButton(label)
 b.setStyleSheet(BUTTON_STYLE.replace(ACCENT, color))
 if slot:
 b.clicked.connect(slot)
 return b

 lay.addWidget(btn(" Kalem Ekle", slot=self.kalem_ekle))
 lay.addWidget(btn(" Düzenle", slot=self.kalem_duzenle))
 lay.addWidget(btn(" Sil", RED, slot=self.kalem_sil))
 lay.addWidget(btn(" Hesapla", slot=self.hesapla))
 lay.addStretch()
 lay.addWidget(btn(" Yeni Teklif", ORANGE, slot=self._yeni_teklif))
 lay.addWidget(btn(" Excel", GREEN, slot=self.export_excel))
 lay.addWidget(btn(" PDF", GREEN, slot=self.export_pdf))
 return w

 def _build_tablo(self) -> QTableWidget:
 self.tablo = QTableWidget(0, 7)
 self.tablo.setHorizontalHeaderLabels(
 ["#", "Poz No", "Tanım", "Miktar", "Birim", "Birim Fiyat (₺)", "Toplam (₺)"]
 )
 hdr = self.tablo.horizontalHeader()
 hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
 for c in [0, 1, 3, 4, 5, 6]:
 hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
 self.tablo.verticalHeader().setVisible(False)
 self.tablo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 self.tablo.setAlternatingRowColors(True)
 self.tablo.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
 self.tablo.itemDoubleClicked.connect(self.kalem_duzenle)
 return self.tablo

 def _build_notlar(self) -> QGroupBox:
 grp = QGroupBox("Notlar / Özel Şartlar")
 lay = QVBoxLayout(grp)
 self.notlar_edit = QTextEdit()
 self.notlar_edit.setPlaceholderText(
 "• Teklif fiyatları malzeme + işçilik dahildir.\n"
 "• Çıkan metraj değişirse fiyat revize edilir.\n"
 "• Zemin/altyapı beklenmedik durumlar kapsam dışıdır."
 )
 self.notlar_edit.setMaximumHeight(100)
 lay.addWidget(self.notlar_edit)
 return grp

 def _build_odeme_panel(self) -> QGroupBox:
 grp = QGroupBox("Ödeme Planı")
 lay = QFormLayout(grp)
 self.odeme_combo = QComboBox()
 self.odeme_combo.addItems(ODEME_PLANLARI)
 self.avans_spin = QDoubleSpinBox()
 self.avans_spin.setRange(0, 100)
 self.avans_spin.setDecimals(0)
 self.avans_spin.setValue(30)
 self.avans_spin.setSuffix(" %")
 lay.addRow("Plan:", self.odeme_combo)
 lay.addRow("Avans Oranı:", self.avans_spin)
 return grp

 def _apply_styles(self):
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
 QCheckBox {{ color: {TEXT_GRAY}; }}
 {INPUT_STYLE}
 """)

 # ------------------------------------------------------------------
 # İş mantığı
 # ------------------------------------------------------------------

 def _yeni_teklif(self):
 """Formu sıfırla ve yeni teklif no üret."""
 self._kalemler.clear()
 self._sira_sayac = 1
 self._tablo_guncelle()
 self._ozet_sifirla()

 bugun = date.today()
 no = self.engine.teklif_no_uret(bugun.year, bugun.timetuple().tm_yday)
 self.teklif_no_edit.setText(no)
 self.tarih_edit.setDate(QDate(bugun.year, bugun.month, bugun.day))

 self.musteri_adi.clear()
 self.musteri_tel.clear()
 self.musteri_adres.clear()
 self.musteri_tc_vkn.clear()
 self.proje_adi.clear()
 self.proje_adresi.clear()
 self.notlar_edit.clear()
 self.stopaj_check.setChecked(False)
 self.kdv_haric_check.setChecked(False)

 def kalem_ekle(self):
 dlg = KalemDialog(parent=self)
 if dlg.exec() == QDialog.DialogCode.Accepted:
 k = dlg.get_kalem()
 if not k.tanim:
 QMessageBox.warning(self, "Uyarı", "Tanım boş olamaz.")
 return
 k.sira_no = self._sira_sayac
 self._sira_sayac += 1
 self._kalemler.append(k)
 self._tablo_guncelle()

 def kalem_duzenle(self):
 row = self.tablo.currentRow()
 if not (0 <= row < len(self._kalemler)):
 return
 dlg = KalemDialog(kalem=self._kalemler[row], parent=self)
 if dlg.exec() == QDialog.DialogCode.Accepted:
 k = dlg.get_kalem()
 k.sira_no = self._kalemler[row].sira_no
 self._kalemler[row] = k
 self._tablo_guncelle()

 def kalem_sil(self):
 row = self.tablo.currentRow()
 if 0 <= row < len(self._kalemler):
 tanim = self._kalemler[row].tanim
 cevap = QMessageBox.question(
 self, "Sil", f'"{tanim}" silinsin mi?',
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
 )
 if cevap == QMessageBox.StandardButton.Yes:
 self._kalemler.pop(row)
 self._tablo_guncelle()

 def hesapla(self):
 if not self._kalemler:
 QMessageBox.warning(self, "Uyarı", "Önce iş kalemi ekleyin.")
 return

 bilgi = self._bilgi_topla()
 sonuc = self.engine.hesapla(bilgi)
 self._kalemler = bilgi.kalemler
 self._tablo_guncelle()

 def para(v): return f"{float(v):,.2f} ₺"

 self.lbl_ara.setText(para(sonuc.ara_toplam))
 self.lbl_kar.setText(
 f"{para(sonuc.kar_tutari)} (%{float(bilgi.kar_marji_orani)*100:.0f})"
 )
 self.lbl_matrah.setText(para(sonuc.kdv_matrah))
 self.lbl_kdv.setText(para(sonuc.kdv_tutari) if not bilgi.kdv_haric_mi else "KDV Hariç")
 self.lbl_stopaj.setText(
 para(sonuc.stopaj_tutari) if bilgi.stopaj_var_mi else "—"
 )
 self.lbl_genel.setText(para(sonuc.net_odenecek))
 self.lbl_avans.setText(para(sonuc.avans_tutari))

 def _bilgi_topla(self) -> TeklifBilgisi:
 q = self.tarih_edit.date()
 bilgi = TeklifBilgisi(
 musteri_adi = self.musteri_adi.text().strip(),
 musteri_telefon = self.musteri_tel.text().strip(),
 musteri_adres = self.musteri_adres.text().strip(),
 musteri_tc_vkn = self.musteri_tc_vkn.text().strip(),
 proje_adi = self.proje_adi.text().strip(),
 proje_adresi = self.proje_adresi.text().strip(),
 proje_turu = self.proje_turu.currentText(),
 teklif_no = self.teklif_no_edit.text(),
 teklif_tarihi = date(q.year(), q.month(), q.day()),
 kar_marji_orani = Decimal(str(self.kar_spin.value() / 100)),
 avans_orani = Decimal(str(self.avans_spin.value() / 100)),
 stopaj_var_mi = self.stopaj_check.isChecked(),
 kdv_haric_mi = self.kdv_haric_check.isChecked(),
 odeme_plani = self.odeme_combo.currentText(),
 notlar = self.notlar_edit.toPlainText().strip(),
 firma_adi = self.firma_adi.text().strip(),
 kalemler = [TeklifKalemi(
 sira_no = k.sira_no,
 poz_no = k.poz_no,
 tanim = k.tanim,
 birim = k.birim,
 miktar = k.miktar,
 birim_fiyat = k.birim_fiyat,
 notlar = k.notlar,
 ) for k in self._kalemler],
 )
 gecerlilik = self.engine.gecerlilik_tarihi_hesapla(
 bilgi.teklif_tarihi, self.gecerlilik_spin.value()
 )
 bilgi.gecerlilik_tarihi = gecerlilik
 return bilgi

 def _tablo_guncelle(self):
 self.tablo.setRowCount(len(self._kalemler))
 for r, k in enumerate(self._kalemler):
 self.tablo.setItem(r, 0, QTableWidgetItem(str(k.sira_no)))
 self.tablo.setItem(r, 1, QTableWidgetItem(k.poz_no))
 self.tablo.setItem(r, 2, QTableWidgetItem(k.tanim))
 self.tablo.setItem(r, 3, QTableWidgetItem(f"{float(k.miktar):,.2f}"))
 self.tablo.setItem(r, 4, QTableWidgetItem(k.birim))
 self.tablo.setItem(r, 5, QTableWidgetItem(f"{float(k.birim_fiyat):,.2f}"))
 toplam_item = QTableWidgetItem(f"{float(k.toplam):,.2f}")
 toplam_item.setForeground(QColor(ACCENT))
 self.tablo.setItem(r, 6, toplam_item)

 def _ozet_sifirla(self):
 for lbl in [self.lbl_ara, self.lbl_kar, self.lbl_matrah,
 self.lbl_kdv, self.lbl_stopaj, self.lbl_genel, self.lbl_avans]:
 lbl.setText("—")

 # ------------------------------------------------------------------
 # Export
 # ------------------------------------------------------------------

 def export_excel(self):
 self.hesapla()
 bilgi = self._bilgi_topla()
 sonuc = self.engine.hesapla(bilgi)

 path, _ = QFileDialog.getSaveFileName(
 self, "Excel Kaydet", f"teklif_{bilgi.teklif_no}.xlsx",
 "Excel Dosyası (*.xlsx)"
 )
 if not path:
 return
 try:
 import openpyxl
 from openpyxl.styles import Font, PatternFill, Alignment
 wb = openpyxl.Workbook()
 ws = wb.active
 ws.title = "Teklif"

 # Başlık
 ws.append([f"{bilgi.firma_adi or 'İnşaat Metraj Pro'} — MÜŞTERİ TEKLİFİ"])
 ws.append([f"Teklif No: {bilgi.teklif_no}",
 f"Tarih: {bilgi.teklif_tarihi}",
 f"Geçerlilik: {bilgi.gecerlilik_tarihi}"])
 ws.append([f"Müşteri: {bilgi.musteri_adi}",
 f"Proje: {bilgi.proje_adi}",
 f"Tür: {bilgi.proje_turu}"])
 ws.append([])

 # Tablo başlıkları
 ws.append(["#", "Poz No", "Tanım", "Miktar", "Birim",
 "Birim Fiyat (₺)", "Toplam (₺)"])
 for k in bilgi.kalemler:
 ws.append([k.sira_no, k.poz_no, k.tanim,
 float(k.miktar), k.birim,
 float(k.birim_fiyat), float(k.toplam)])
 ws.append([])

 # Özet
 ws.append(["", "", "", "", "", "Ara Toplam:", float(sonuc.ara_toplam)])
 ws.append(["", "", "", "", "", f"Kar (%{float(bilgi.kar_marji_orani)*100:.0f}):",
 float(sonuc.kar_tutari)])
 ws.append(["", "", "", "", "", "KDV Matrahı:", float(sonuc.kdv_matrah)])
 ws.append(["", "", "", "", "", "KDV (%20):", float(sonuc.kdv_tutari)])
 if bilgi.stopaj_var_mi:
 ws.append(["", "", "", "", "", "Stopaj (%3):", float(sonuc.stopaj_tutari)])
 ws.append(["", "", "", "", "", "GENEL TOPLAM:", float(sonuc.net_odenecek)])
 ws.append(["", "", "", "", "", "Avans:", float(sonuc.avans_tutari)])
 ws.append([])
 ws.append(["Ödeme Planı:", bilgi.odeme_plani])
 if bilgi.notlar:
 ws.append(["Notlar:", bilgi.notlar])

 ws.column_dimensions["C"].width = 40
 wb.save(path)
 QMessageBox.information(self, "Başarılı", f"Excel kaydedildi:\n{path}")
 except Exception as e:
 QMessageBox.critical(self, "Hata", str(e))

 def export_pdf(self):
 self.hesapla()
 bilgi = self._bilgi_topla()
 sonuc = self.engine.hesapla(bilgi)

 path, _ = QFileDialog.getSaveFileName(
 self, "PDF Kaydet", f"teklif_{bilgi.teklif_no}.pdf",
 "PDF Dosyası (*.pdf)"
 )
 if not path:
 return
 try:
 from reportlab.lib.pagesizes import A4
 from reportlab.lib import colors
 from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
 from reportlab.lib.units import cm
 from reportlab.platypus import (
 SimpleDocTemplate, Table, TableStyle, Paragraph,
 Spacer, HRFlowable,
 )

 doc = SimpleDocTemplate(path, pagesize=A4,
 leftMargin=2*cm, rightMargin=2*cm,
 topMargin=2*cm, bottomMargin=2*cm)
 styles = getSampleStyleSheet()
 story = []

 # Başlık
 firma = bilgi.firma_adi or "İnşaat Metraj Pro"
 story.append(Paragraph(
 f"<b>{firma}</b>",
 ParagraphStyle("firma", fontSize=16, textColor=colors.HexColor("#00BFFF"))
 ))
 story.append(Paragraph("MÜŞTERİ TEKLİFİ", styles["Heading2"]))
 story.append(HRFlowable(width="100%", color=colors.HexColor("#00BFFF")))
 story.append(Spacer(1, 0.3*cm))

 # Bilgi satırları
 bilgi_data = [
 ["Teklif No", bilgi.teklif_no,
 "Tarih", str(bilgi.teklif_tarihi)],
 ["Müşteri", bilgi.musteri_adi,
 "Geçerlilik", str(bilgi.gecerlilik_tarihi)],
 ["Proje", bilgi.proje_adi,
 "Tür", bilgi.proje_turu],
 ["Adres", bilgi.proje_adresi,
 "Ödeme", bilgi.odeme_plani],
 ]
 t = Table(bilgi_data, colWidths=[3*cm, 6*cm, 3*cm, 5*cm])
 t.setStyle(TableStyle([
 ("FONTSIZE", (0,0), (-1,-1), 9),
 ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
 ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
 ("GRID", (0,0), (-1,-1), 0.3, colors.lightgrey),
 ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#e8f4f8")),
 ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#e8f4f8")),
 ]))
 story.append(t)
 story.append(Spacer(1, 0.4*cm))

 # Kalem tablosu
 tablo_data = [["#", "Poz No", "Tanım", "Miktar", "Birim", "B.Fiyat ₺", "Toplam ₺"]]
 for k in bilgi.kalemler:
 tablo_data.append([
 str(k.sira_no), k.poz_no, k.tanim,
 f"{float(k.miktar):,.2f}", k.birim,
 f"{float(k.birim_fiyat):,.2f}",
 f"{float(k.toplam):,.2f}",
 ])

 kt = Table(tablo_data, colWidths=[1*cm, 2*cm, 7.5*cm, 2*cm, 1.5*cm, 2.5*cm, 2.5*cm])
 kt.setStyle(TableStyle([
 ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#00BFFF")),
 ("TEXTCOLOR", (0,0), (-1,0), colors.black),
 ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
 ("FONTSIZE", (0,0), (-1,-1), 8),
 ("GRID", (0,0), (-1,-1), 0.3, colors.lightgrey),
 ("ROWBACKGROUNDS", (0,1), (-1,-1),
 [colors.white, colors.HexColor("#f5f9ff")]),
 ("ALIGN", (3,0), (-1,-1), "RIGHT"),
 ]))
 story.append(kt)
 story.append(Spacer(1, 0.4*cm))

 # Finansal özet
 def fp(v): return f"{float(v):,.2f} ₺"
 ozet_data = [
 ["Ara Toplam", fp(sonuc.ara_toplam)],
 [f"Kar (%{float(bilgi.kar_marji_orani)*100:.0f})",
 fp(sonuc.kar_tutari)],
 ["KDV Matrahı", fp(sonuc.kdv_matrah)],
 ]
 if not bilgi.kdv_haric_mi:
 ozet_data.append(["KDV (%20)", fp(sonuc.kdv_tutari)])
 if bilgi.stopaj_var_mi:
 ozet_data.append(["Stopaj (%3) (−)", fp(sonuc.stopaj_tutari)])
 ozet_data.append(["GENEL TOPLAM", fp(sonuc.net_odenecek)])
 ozet_data.append([f"Avans (%{float(bilgi.avans_orani)*100:.0f})",
 fp(sonuc.avans_tutari)])

 ot = Table(ozet_data, colWidths=[8*cm, 4*cm], hAlign="RIGHT")
 ot.setStyle(TableStyle([
 ("FONTSIZE", (0,0), (-1,-1), 9),
 ("ALIGN", (1,0), (1,-1), "RIGHT"),
 ("GRID", (0,0), (-1,-1), 0.3, colors.lightgrey),
 ("FONTNAME", (0,-2), (-1,-2), "Helvetica-Bold"),
 ("BACKGROUND", (0,-2), (-1,-2), colors.HexColor("#00BFFF")),
 ("FONTSIZE", (0,-2), (-1,-2), 11),
 ]))
 story.append(ot)

 if bilgi.notlar:
 story.append(Spacer(1, 0.4*cm))
 story.append(Paragraph(f"<b>Notlar:</b> {bilgi.notlar}", styles["Normal"]))

 doc.build(story)
 QMessageBox.information(self, "Başarılı", f"PDF kaydedildi:\n{path}")
 except ImportError:
 QMessageBox.warning(self, "Eksik", "pip install reportlab")
 except Exception as e:
 QMessageBox.critical(self, "Hata", str(e))
