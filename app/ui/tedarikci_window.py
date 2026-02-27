"""
Tedarikçi Fiyat Karşılaştırma Sekmesi
Tedarikçi yönetimi, fiyat girişi ve karşılaştırma analizi
"""

from PyQt6.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
 QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
 QLineEdit, QComboBox, QTextEdit, QMessageBox, QDialog,
 QHeaderView, QDoubleSpinBox, QCheckBox, QSplitter,
 QSpinBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from typing import Optional, List, Dict
import logging

from app.core.database import DatabaseManager
from app.core.tedarikci_engine import TedarikciEngine

logger = logging.getLogger(__name__)


class TedarikciWindow(QWidget):
 """Tedarikçi fiyat karşılaştırma widget'i"""

 def __init__(self, db: DatabaseManager):
 super().__init__()
 self.db = db
 self.engine = TedarikciEngine(db=db)
 self._ensure_default_tedarikcilar()
 self.init_ui()
 self.load_tedarikci_listesi()

 def _ensure_default_tedarikcilar(self):
 """Veritabanında tedarikçi yoksa varsayılanları ekle"""
 mevcut = self.db.get_tedarikci_listesi()
 if not mevcut:
 for ad in ['Tedarikçi A', 'Tedarikçi B', 'Tedarikçi C']:
 self.db.add_tedarikci(ad=ad)

 def init_ui(self):
 layout = QVBoxLayout(self)
 layout.setContentsMargins(10, 10, 10, 10)

 baslik = QLabel(" Tedarikçi Fiyat Karşılaştırma")
 baslik.setStyleSheet("font-size: 16pt; font-weight: bold; margin-bottom: 6px;")
 layout.addWidget(baslik)

 splitter = QSplitter(Qt.Orientation.Horizontal)

 # Sol: Tedarikçi listesi + yönetim
 sol = QWidget()
 sol_layout = QVBoxLayout(sol)
 sol_layout.setContentsMargins(0, 0, 0, 0)
 sol_layout.addWidget(self._create_tedarikci_yonetimi())
 splitter.addWidget(sol)

 # Sağ: Fiyat girişi + karşılaştırma
 sag = QWidget()
 sag_layout = QVBoxLayout(sag)
 sag_layout.setContentsMargins(0, 0, 0, 0)
 sag_layout.addWidget(self._create_fiyat_giris_formu())
 sag_layout.addWidget(self._create_karsilastirma_alani())
 splitter.addWidget(sag)

 splitter.setSizes([380, 620])
 layout.addWidget(splitter)

 # ── Tedarikçi Listesi ──────────────────────────────────────────
 def _create_tedarikci_yonetimi(self) -> QGroupBox:
 group = QGroupBox("Tedarikçi Listesi")
 layout = QVBoxLayout(group)

 self.tedarikci_table = QTableWidget()
 self.tedarikci_table.setColumnCount(6)
 self.tedarikci_table.setHorizontalHeaderLabels(
 ["ID", "Tedarikçi Adı", "Telefon", "E-posta", "Adres", "Durum"])
 self.tedarikci_table.setColumnHidden(0, True)
 self.tedarikci_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
 self.tedarikci_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 self.tedarikci_table.horizontalHeader().setStretchLastSection(True)
 self.tedarikci_table.setAlternatingRowColors(True)
 self.tedarikci_table.selectionModel().currentRowChanged.connect(
 lambda current, _prev: self._on_tedarikci_secildi(current.row())
 )
 layout.addWidget(self.tedarikci_table)

 btn_layout = QHBoxLayout()
 ekle_btn = QPushButton("Tedarikçi Ekle")
 ekle_btn.clicked.connect(self.tedarikci_ekle)
 btn_layout.addWidget(ekle_btn)

 duzenle_btn = QPushButton("Düzenle")
 duzenle_btn.clicked.connect(self.tedarikci_duzenle)
 btn_layout.addWidget(duzenle_btn)

 sil_btn = QPushButton("Sil")
 sil_btn.setStyleSheet("background-color: #c9184a;")
 sil_btn.clicked.connect(self.tedarikci_sil)
 btn_layout.addWidget(sil_btn)

 layout.addLayout(btn_layout)

 # Seçili tedarikçinin fiyat listesi
 fiyat_baslik = QLabel("Seçili Tedarikçi Fiyatları:")
 fiyat_baslik.setFont(QFont("Arial", 10, QFont.Weight.Bold))
 layout.addWidget(fiyat_baslik)

 self.tedarikci_fiyat_table = QTableWidget()
 self.tedarikci_fiyat_table.setColumnCount(5)
 self.tedarikci_fiyat_table.setHorizontalHeaderLabels(
 ["ID", "Malzeme Kodu", "Birim", "Birim Fiyat", "İndirim %"])
 self.tedarikci_fiyat_table.setColumnHidden(0, True)
 self.tedarikci_fiyat_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
 self.tedarikci_fiyat_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 self.tedarikci_fiyat_table.horizontalHeader().setStretchLastSection(True)
 self.tedarikci_fiyat_table.setAlternatingRowColors(True)
 layout.addWidget(self.tedarikci_fiyat_table)

 fiyat_btn_layout = QHBoxLayout()
 fiyat_ekle_btn = QPushButton("Fiyat Ekle/Güncelle")
 fiyat_ekle_btn.clicked.connect(self.tedarikci_fiyat_ekle)
 fiyat_btn_layout.addWidget(fiyat_ekle_btn)

 fiyat_sil_btn = QPushButton("Fiyat Sil")
 fiyat_sil_btn.setStyleSheet("background-color: #c9184a;")
 fiyat_sil_btn.clicked.connect(self.tedarikci_fiyat_sil)
 fiyat_btn_layout.addWidget(fiyat_sil_btn)

 layout.addLayout(fiyat_btn_layout)
 return group

 # ── Fiyat Karşılaştırma ────────────────────────────────────────
 def _create_fiyat_giris_formu(self) -> QGroupBox:
 group = QGroupBox("Fiyat Karşılaştırma")
 layout = QFormLayout(group)

 self.malzeme_kodu_input = QLineEdit()
 self.malzeme_kodu_input.setPlaceholderText("Örn: BETON-C30, DEMIR-S420")
 layout.addRow("Malzeme Kodu:", self.malzeme_kodu_input)

 self.miktar_input = QDoubleSpinBox()
 self.miktar_input.setRange(0.01, 9999999)
 self.miktar_input.setDecimals(2)
 self.miktar_input.setValue(1.0)
 layout.addRow("Miktar:", self.miktar_input)

 karsilastir_btn = QPushButton(" Fiyatları Karşılaştır")
 karsilastir_btn.setStyleSheet(
 "background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
 karsilastir_btn.clicked.connect(self.karsilastir_fiyatlar)
 layout.addRow("", karsilastir_btn)
 return group

 def _create_karsilastirma_alani(self) -> QGroupBox:
 group = QGroupBox("Karşılaştırma Sonuçları")
 layout = QVBoxLayout(group)

 self.karsilastirma_table = QTableWidget()
 self.karsilastirma_table.setColumnCount(9)
 self.karsilastirma_table.setHorizontalHeaderLabels([
 "Sıra", "Tedarikçi", "Birim Fiyat", "İndirim %",
 "İndirimli Fiyat", "KDV", "Genel Toplam", "Teslimat", "Stok"
 ])
 self.karsilastirma_table.horizontalHeader().setSectionResizeMode(
 1, QHeaderView.ResizeMode.Stretch)
 self.karsilastirma_table.setAlternatingRowColors(True)
 self.karsilastirma_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 self.karsilastirma_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
 layout.addWidget(self.karsilastirma_table)

 self.tasarruf_label = QLabel("")
 self.tasarruf_label.setWordWrap(True)
 self.tasarruf_label.setStyleSheet(
 "padding: 8px; background-color: #1e2a1e; color: #a0e0a0; "
 "border: 1px solid #3a4a3a; border-radius: 4px; font-size: 11pt;")
 layout.addWidget(self.tasarruf_label)

 export_btn = QPushButton(" Excel'e Aktar")
 export_btn.clicked.connect(self.export_karsilastirma)
 layout.addWidget(export_btn)
 return group

 # ── Karşılaştırma Mantığı ──────────────────────────────────────
 def karsilastir_fiyatlar(self):
 malzeme_kodu = self.malzeme_kodu_input.text().strip()
 miktar = self.miktar_input.value()

 if not malzeme_kodu:
 QMessageBox.warning(self, "Uyarı", "Lütfen malzeme kodu girin!")
 return

 try:
 fiyatlar = self.engine.karsilastir_fiyatlar(malzeme_kodu, miktar)

 if not fiyatlar:
 self.karsilastirma_table.setRowCount(0)
 self.tasarruf_label.setText(
 f"'{malzeme_kodu}' için fiyat kaydı bulunamadı.\n"
 "Tedarikçi listesinden fiyat ekleyin.")
 return

 self._doldur_karsilastirma_tablosu(fiyatlar)
 tasarruf = self.engine.hesapla_tasarruf(fiyatlar)
 self._goster_tasarruf(tasarruf)

 except Exception as e:
 logger.error(f"Karşılaştırma hatası: {e}")
 QMessageBox.critical(self, "Hata", f"Karşılaştırma sırasında hata:\n{str(e)}")

 def _doldur_karsilastirma_tablosu(self, fiyatlar: List[Dict]):
 self.karsilastirma_table.setRowCount(len(fiyatlar))

 for idx, f in enumerate(fiyatlar):
 sira = QTableWidgetItem(str(idx + 1))
 sira.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
 self.karsilastirma_table.setItem(idx, 0, sira)

 tedarikci_item = QTableWidgetItem(
 f" {f['tedarikci_ad']}" if f.get('en_ucuz') else f['tedarikci_ad'])
 if f.get('en_ucuz'):
 tedarikci_item.setBackground(QColor(76, 175, 80, 60))
 elif f.get('en_pahali'):
 tedarikci_item.setBackground(QColor(244, 67, 54, 50))
 self.karsilastirma_table.setItem(idx, 1, tedarikci_item)

 self.karsilastirma_table.setItem(idx, 2,
 QTableWidgetItem(f"{f['birim_fiyat']:,.2f} ₺"))
 self.karsilastirma_table.setItem(idx, 3,
 QTableWidgetItem(f"%{f['indirim_orani']:.0f}"))
 self.karsilastirma_table.setItem(idx, 4,
 QTableWidgetItem(f"{f['indirimli_birim_fiyat']:,.2f} ₺"))
 self.karsilastirma_table.setItem(idx, 5,
 QTableWidgetItem(f"{f['kdv']:,.2f} ₺"))

 toplam_item = QTableWidgetItem(f"{f['genel_toplam']:,.2f} ₺")
 font = toplam_item.font()
 font.setBold(True)
 toplam_item.setFont(font)
 self.karsilastirma_table.setItem(idx, 6, toplam_item)

 self.karsilastirma_table.setItem(idx, 7,
 QTableWidgetItem(f['teslimat_suresi']))

 stok_item = QTableWidgetItem(f['stok_durumu'])
 if f['stok_durumu'] and 'var' in f['stok_durumu'].lower():
 stok_item.setForeground(QColor(76, 175, 80))
 self.karsilastirma_table.setItem(idx, 8, stok_item)

 def _goster_tasarruf(self, tasarruf: Dict):
 if tasarruf['tasarruf'] > 0:
 metin = (
 f" En Ucuz: {tasarruf['en_ucuz_tedarikci']} — "
 f"{tasarruf['en_ucuz_fiyat']:,.2f} ₺ | "
 f"En Pahalı: {tasarruf['en_pahali_tedarikci']} — "
 f"{tasarruf['en_pahali_fiyat']:,.2f} ₺\n"
 f" {tasarruf['mesaj']}"
 )
 else:
 metin = tasarruf.get('mesaj', '')
 self.tasarruf_label.setText(metin)

 def export_karsilastirma(self):
 """Karşılaştırma tablosunu Excel'e aktar"""
 if self.karsilastirma_table.rowCount() == 0:
 QMessageBox.warning(self, "Uyarı", "Önce bir karşılaştırma yapın.")
 return

 file_path, _ = QFileDialog.getSaveFileName(
 self, "Excel'e Aktar", "", "Excel Dosyaları (*.xlsx)")
 if not file_path:
 return

 try:
 import openpyxl
 from openpyxl.styles import Font, PatternFill, Alignment

 wb = openpyxl.Workbook()
 ws = wb.active
 ws.title = "Fiyat Karşılaştırma"

 basliklar = ["Sıra", "Tedarikçi", "Birim Fiyat", "İndirim %",
 "İndirimli Fiyat", "KDV", "Genel Toplam", "Teslimat", "Stok"]
 header_fill = PatternFill(start_color="16213e", end_color="16213e", fill_type="solid")
 for col, baslik in enumerate(basliklar, 1):
 cell = ws.cell(row=1, column=col, value=baslik)
 cell.font = Font(bold=True, color="FFFFFF")
 cell.fill = header_fill
 cell.alignment = Alignment(horizontal="center")

 for row in range(self.karsilastirma_table.rowCount()):
 for col in range(self.karsilastirma_table.columnCount()):
 item = self.karsilastirma_table.item(row, col)
 ws.cell(row=row + 2, column=col + 1,
 value=item.text() if item else "")

 # Sütun genişliklerini ayarla
 for col in ws.columns:
 max_len = max((len(str(c.value or "")) for c in col), default=0)
 ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

 wb.save(file_path)
 QMessageBox.information(self, "Başarılı",
 f"Karşılaştırma Excel'e aktarıldı:\n{file_path}")
 except Exception as e:
 QMessageBox.critical(self, "Hata", f"Excel oluşturulamadı:\n{str(e)}")

 # ── Tedarikçi CRUD ─────────────────────────────────────────────
 def load_tedarikci_listesi(self):
 try:
 liste = self.engine.get_tedarikci_listesi()
 self.tedarikci_table.setRowCount(len(liste))
 for idx, t in enumerate(liste):
 self.tedarikci_table.setItem(idx, 0, QTableWidgetItem(str(t['id'])))
 self.tedarikci_table.setItem(idx, 1, QTableWidgetItem(t.get('ad', '')))
 self.tedarikci_table.setItem(idx, 2, QTableWidgetItem(t.get('telefon', '') or ''))
 self.tedarikci_table.setItem(idx, 3, QTableWidgetItem(t.get('email', '') or ''))
 self.tedarikci_table.setItem(idx, 4, QTableWidgetItem(t.get('adres', '') or ''))
 aktif = bool(t.get('aktif', 1))
 durum = QTableWidgetItem("Aktif" if aktif else "Pasif")
 durum.setForeground(QColor(76, 175, 80) if aktif else QColor(244, 67, 54))
 self.tedarikci_table.setItem(idx, 5, durum)
 except Exception as e:
 logger.error(f"Tedarikçi listesi yükleme hatası: {e}")

 def _on_tedarikci_secildi(self, row: int):
 """Tedarikçi seçildiğinde o tedarikçinin fiyatlarını göster"""
 if row < 0:
 return
 id_item = self.tedarikci_table.item(row, 0)
 if not id_item:
 return
 tedarikci_id = int(id_item.text())
 self._load_tedarikci_fiyatlari(tedarikci_id)

 def _load_tedarikci_fiyatlari(self, tedarikci_id: int):
 """Seçili tedarikçinin kayıtlı fiyatlarını yükle"""
 try:
 fiyatlar = self.db.get_tedarikci_fiyatlari(tedarikci_id=tedarikci_id)
 self.tedarikci_fiyat_table.setRowCount(len(fiyatlar))
 for idx, f in enumerate(fiyatlar):
 self.tedarikci_fiyat_table.setItem(idx, 0, QTableWidgetItem(str(f['id'])))
 self.tedarikci_fiyat_table.setItem(idx, 1, QTableWidgetItem(f.get('malzeme_kodu', '')))
 self.tedarikci_fiyat_table.setItem(idx, 2, QTableWidgetItem(f.get('birim', '')))
 self.tedarikci_fiyat_table.setItem(idx, 3,
 QTableWidgetItem(f"{f.get('birim_fiyat', 0):,.2f} ₺"))
 self.tedarikci_fiyat_table.setItem(idx, 4,
 QTableWidgetItem(f"%{f.get('indirim_orani', 0):.0f}"))
 except Exception as e:
 logger.error(f"Tedarikçi fiyatları yükleme hatası: {e}")

 def _get_selected_tedarikci(self) -> Optional[Dict]:
 row = self.tedarikci_table.currentRow()
 if row < 0:
 return None
 id_item = self.tedarikci_table.item(row, 0)
 if not id_item:
 return None
 tedarikci_id = int(id_item.text())
 liste = self.engine.get_tedarikci_listesi()
 return next((t for t in liste if t['id'] == tedarikci_id), None)

 def tedarikci_ekle(self):
 dialog = TedarikciDialog(self)
 if dialog.exec() == QDialog.DialogCode.Accepted:
 data = dialog.get_data()
 if not data['ad']:
 QMessageBox.warning(self, "Uyarı", "Tedarikçi adı boş olamaz!")
 return
 self.db.add_tedarikci(
 ad=data['ad'], telefon=data['telefon'],
 email=data['email'], adres=data['adres'], notlar=data['notlar'])
 self.load_tedarikci_listesi()

 def tedarikci_duzenle(self):
 tedarikci = self._get_selected_tedarikci()
 if not tedarikci:
 QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir tedarikçi seçin.")
 return
 dialog = TedarikciDialog(self, tedarikci)
 if dialog.exec() == QDialog.DialogCode.Accepted:
 data = dialog.get_data()
 if not data['ad']:
 QMessageBox.warning(self, "Uyarı", "Tedarikçi adı boş olamaz!")
 return
 self.db.update_tedarikci(
 tedarikci['id'], ad=data['ad'], telefon=data['telefon'],
 email=data['email'], adres=data['adres'],
 notlar=data['notlar'], aktif=data['aktif'])
 self.load_tedarikci_listesi()

 def tedarikci_sil(self):
 tedarikci = self._get_selected_tedarikci()
 if not tedarikci:
 QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir tedarikçi seçin.")
 return
 reply = QMessageBox.question(
 self, "Onay",
 f"'{tedarikci['ad']}' tedarikçisini ve tüm fiyat kayıtlarını silmek istediğinize emin misiniz?",
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
 QMessageBox.StandardButton.No)
 if reply == QMessageBox.StandardButton.Yes:
 self.db.delete_tedarikci(tedarikci['id'])
 self.tedarikci_fiyat_table.setRowCount(0)
 self.load_tedarikci_listesi()

 # ── Tedarikçi Fiyat CRUD ───────────────────────────────────────
 def tedarikci_fiyat_ekle(self):
 tedarikci = self._get_selected_tedarikci()
 if not tedarikci:
 QMessageBox.warning(self, "Uyarı", "Lütfen önce bir tedarikçi seçin.")
 return
 dialog = TedarikciiFiyatDialog(self, tedarikci['ad'])
 if dialog.exec() == QDialog.DialogCode.Accepted:
 data = dialog.get_data()
 if not data['malzeme_kodu']:
 QMessageBox.warning(self, "Uyarı", "Malzeme kodu boş olamaz!")
 return
 self.db.add_tedarikci_fiyat(
 tedarikci_id=tedarikci['id'],
 malzeme_kodu=data['malzeme_kodu'],
 malzeme_adi=data['malzeme_adi'],
 birim=data['birim'],
 birim_fiyat=data['birim_fiyat'],
 kdv_orani=data['kdv_orani'],
 indirim_orani=data['indirim_orani'],
 teslimat_suresi=data['teslimat_suresi'],
 stok_durumu=data['stok_durumu'],
 notlar=data['notlar'])
 self._load_tedarikci_fiyatlari(tedarikci['id'])

 def tedarikci_fiyat_sil(self):
 row = self.tedarikci_fiyat_table.currentRow()
 if row < 0:
 QMessageBox.warning(self, "Uyarı", "Silmek için bir fiyat satırı seçin.")
 return
 id_item = self.tedarikci_fiyat_table.item(row, 0)
 malzeme_item = self.tedarikci_fiyat_table.item(row, 1)
 if not id_item:
 return
 reply = QMessageBox.question(
 self, "Onay",
 f"'{malzeme_item.text() if malzeme_item else ''}' fiyat kaydını silmek istediğinize emin misiniz?",
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
 QMessageBox.StandardButton.No)
 if reply == QMessageBox.StandardButton.Yes:
 self.db.delete_tedarikci_fiyat(int(id_item.text()))
 tedarikci = self._get_selected_tedarikci()
 if tedarikci:
 self._load_tedarikci_fiyatlari(tedarikci['id'])


# ── Dialoglar ──────────────────────────────────────────────────────

class TedarikciDialog(QDialog):
 """Tedarikçi ekleme/düzenleme dialogu"""

 def __init__(self, parent=None, tedarikci_data: Optional[Dict] = None):
 super().__init__(parent)
 self.tedarikci_data = tedarikci_data
 self.is_edit = tedarikci_data is not None
 self.setWindowTitle("Tedarikçi Düzenle" if self.is_edit else "Yeni Tedarikçi")
 self.setMinimumWidth(420)
 self._init_ui()
 if self.is_edit:
 self._load_data()

 def _init_ui(self):
 layout = QVBoxLayout(self)
 form = QFormLayout()

 self.ad_input = QLineEdit()
 self.ad_input.setPlaceholderText("Tedarikçi adı")
 form.addRow("Ad *:", self.ad_input)

 self.telefon_input = QLineEdit()
 self.telefon_input.setPlaceholderText("0xxx xxx xx xx")
 form.addRow("Telefon:", self.telefon_input)

 self.email_input = QLineEdit()
 self.email_input.setPlaceholderText("ornek@firma.com")
 form.addRow("E-posta:", self.email_input)

 self.adres_input = QLineEdit()
 self.adres_input.setPlaceholderText("Adres bilgisi")
 form.addRow("Adres:", self.adres_input)

 self.notlar_input = QTextEdit()
 self.notlar_input.setMaximumHeight(60)
 self.notlar_input.setPlaceholderText("Notlar...")
 form.addRow("Notlar:", self.notlar_input)

 self.aktif_check = QCheckBox("Aktif")
 self.aktif_check.setChecked(True)
 form.addRow("Durum:", self.aktif_check)

 layout.addLayout(form)

 btn_layout = QHBoxLayout()
 btn_layout.addStretch()
 btn_cancel = QPushButton("İptal")
 btn_cancel.clicked.connect(self.reject)
 btn_layout.addWidget(btn_cancel)
 btn_save = QPushButton("Kaydet")
 btn_save.setDefault(True)
 btn_save.clicked.connect(self.accept)
 btn_layout.addWidget(btn_save)
 layout.addLayout(btn_layout)

 def _load_data(self):
 d = self.tedarikci_data
 self.ad_input.setText(d.get('ad', '') or '')
 self.telefon_input.setText(d.get('telefon', '') or '')
 self.email_input.setText(d.get('email', '') or '')
 self.adres_input.setText(d.get('adres', '') or '')
 self.notlar_input.setPlainText(d.get('notlar', '') or '')
 self.aktif_check.setChecked(bool(d.get('aktif', 1)))

 def get_data(self) -> Dict:
 return {
 'ad': self.ad_input.text().strip(),
 'telefon': self.telefon_input.text().strip(),
 'email': self.email_input.text().strip(),
 'adres': self.adres_input.text().strip(),
 'notlar': self.notlar_input.toPlainText().strip(),
 'aktif': 1 if self.aktif_check.isChecked() else 0
 }


class TedarikciiFiyatDialog(QDialog):
 """Tedarikçi fiyat ekleme dialogu"""

 def __init__(self, parent=None, tedarikci_adi: str = ""):
 super().__init__(parent)
 self.setWindowTitle(f"Fiyat Ekle / Güncelle — {tedarikci_adi}")
 self.setMinimumWidth(400)
 self._init_ui()

 def _init_ui(self):
 layout = QVBoxLayout(self)
 form = QFormLayout()

 self.malzeme_kodu_input = QLineEdit()
 self.malzeme_kodu_input.setPlaceholderText("Örn: BETON-C30")
 form.addRow("Malzeme Kodu *:", self.malzeme_kodu_input)

 self.malzeme_adi_input = QLineEdit()
 self.malzeme_adi_input.setPlaceholderText("Örn: C30 Hazır Beton")
 form.addRow("Malzeme Adı:", self.malzeme_adi_input)

 self.birim_input = QLineEdit()
 self.birim_input.setPlaceholderText("m³, kg, adet...")
 form.addRow("Birim:", self.birim_input)

 self.birim_fiyat_input = QDoubleSpinBox()
 self.birim_fiyat_input.setRange(0, 99999999)
 self.birim_fiyat_input.setDecimals(2)
 self.birim_fiyat_input.setPrefix("₺ ")
 form.addRow("Birim Fiyat *:", self.birim_fiyat_input)

 self.kdv_input = QDoubleSpinBox()
 self.kdv_input.setRange(0, 100)
 self.kdv_input.setDecimals(0)
 self.kdv_input.setSuffix(" %")
 self.kdv_input.setValue(20)
 form.addRow("KDV Oranı:", self.kdv_input)

 self.indirim_input = QDoubleSpinBox()
 self.indirim_input.setRange(0, 100)
 self.indirim_input.setDecimals(1)
 self.indirim_input.setSuffix(" %")
 form.addRow("İndirim:", self.indirim_input)

 self.teslimat_input = QLineEdit()
 self.teslimat_input.setPlaceholderText("Örn: 3-5 iş günü")
 form.addRow("Teslimat Süresi:", self.teslimat_input)

 self.stok_combo = QComboBox()
 self.stok_combo.addItems(["Stokta var", "Stokta yok", "Sipariş ile"])
 form.addRow("Stok Durumu:", self.stok_combo)

 self.notlar_input = QLineEdit()
 self.notlar_input.setPlaceholderText("Opsiyonel notlar")
 form.addRow("Notlar:", self.notlar_input)

 layout.addLayout(form)

 btn_layout = QHBoxLayout()
 btn_layout.addStretch()
 btn_cancel = QPushButton("İptal")
 btn_cancel.clicked.connect(self.reject)
 btn_layout.addWidget(btn_cancel)
 btn_save = QPushButton("Kaydet")
 btn_save.setDefault(True)
 btn_save.clicked.connect(self.accept)
 btn_layout.addWidget(btn_save)
 layout.addLayout(btn_layout)

 def get_data(self) -> Dict:
 return {
 'malzeme_kodu': self.malzeme_kodu_input.text().strip().upper(),
 'malzeme_adi': self.malzeme_adi_input.text().strip(),
 'birim': self.birim_input.text().strip(),
 'birim_fiyat': self.birim_fiyat_input.value(),
 'kdv_orani': self.kdv_input.value(),
 'indirim_orani': self.indirim_input.value(),
 'teslimat_suresi': self.teslimat_input.text().strip(),
 'stok_durumu': self.stok_combo.currentText(),
 'notlar': self.notlar_input.text().strip(),
 }
