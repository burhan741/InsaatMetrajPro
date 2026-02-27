"""
Vitrifiye ve Armatur Maliyet Hesaplama Penceresi
Batarya, Musluk, Klozet, Alaturka, Dus Seti, Petek envanter ve maliyet hesaplama arayuzu
"""

from PyQt6.QtWidgets import (
 QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
 QPushButton, QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
 QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView,
 QFormLayout, QMessageBox, QFrame, QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import logging

from app.core.calculator import hesapla_vitrifiye_armatur

logger = logging.getLogger(__name__)


class VitrifiyeMaliyetWindow(QMainWindow):
 """Vitrifiye ve armatur maliyet hesaplama penceresi"""

 hesaplama_tamamlandi = pyqtSignal(dict)

 def __init__(self, parent=None):
     super().__init__(parent)
 self.urun_listesi = []
 self.son_hesaplama = None
 self.init_ui()

 def init_ui(self):
     """Arayuzu olustur"""
 self.setWindowTitle("Vitrifiye ve Armatur Maliyet Hesaplama")
 self.setGeometry(100, 100, 1100, 800)

 # Ana widget
 main_widget = QWidget()
 self.setCentralWidget(main_widget)
 main_layout = QHBoxLayout(main_widget)

 # Sol panel - Girisler
 left_panel = self._create_input_panel()
 main_layout.addWidget(left_panel, 1)

 # Sag panel - Sonuclar
 right_panel = self._create_results_panel()
 main_layout.addWidget(right_panel, 1)

 self._apply_styles()

 def _apply_styles(self):
     """Stil uygula"""
 self.setStyleSheet("""
 QMainWindow {
 background-color: #1a1a2e;
 }
 QLabel {
 color: #e0e0e0;
 }
 QComboBox, QDoubleSpinBox, QSpinBox {
 background-color: #16213e;
 color: #e0e0e0;
 border: 1px solid #00CED1;
 padding: 5px;
 border-radius: 3px;
 min-height: 25px;
 }
 QComboBox::drop-down {
 border: none;
 }
 QPushButton {
 background-color: #00CED1;
 color: #1a1a2e;
 border: none;
 padding: 10px;
 border-radius: 4px;
 font-weight: bold;
 }
 QPushButton:hover {
 background-color: #20B2AA;
 }
 QPushButton#btn_sil {
 background-color: #FF6B6B;
 }
 QPushButton#btn_sil:hover {
 background-color: #FF5252;
 }
 QPushButton#btn_temizle {
 background-color: #FFA500;
 }
 QPushButton#btn_temizle:hover {
 background-color: #FF8C00;
 }
 QGroupBox {
 color: #00CED1;
 border: 2px solid #00CED1;
 border-radius: 5px;
 margin-top: 10px;
 padding-top: 10px;
 font-weight: bold;
 }
 QGroupBox::title {
 subcontrol-origin: margin;
 left: 10px;
 padding: 0 5px 0 5px;
 }
 QTableWidget {
 background-color: #16213e;
 color: #e0e0e0;
 gridline-color: #00CED1;
 border: 1px solid #00CED1;
 border-radius: 3px;
 }
 QTableWidget::item {
 padding: 5px;
 }
 QTableWidget::item:selected {
 background-color: #0f3460;
 }
 QHeaderView::section {
 background-color: #0f3460;
 color: #00CED1;
 padding: 5px;
 border: 1px solid #00CED1;
 font-weight: bold;
 }
 QFrame#sonuc_frame {
 background-color: #0f3460;
 border: 2px solid #00FF00;
 border-radius: 8px;
 padding: 10px;
 }
 """)

 def _create_input_panel(self) -> QGroupBox:
     """Giris panelini olustur"""
 panel = QGroupBox("Urun Girisi ve Fiyatlar")
 layout = QVBoxLayout()
 layout.setSpacing(10)

 # === URUN EKLEME ===
 urun_group = QGroupBox("1. Urun Ekle")
 urun_layout = QFormLayout()

 # Urun tipi
 self.combo_urun_tipi = QComboBox()
 self.combo_urun_tipi.addItem("Batarya (Lavabo/Banyo Mix)", "batarya")
 self.combo_urun_tipi.addItem("Musluk (Taharet/Camasir)", "musluk")
 self.combo_urun_tipi.addItem("Klozet Takim (Kapak + Ic Takim)", "klozet")
 self.combo_urun_tipi.addItem("Alaturka Tuvalet Tasi", "alaturka")
 self.combo_urun_tipi.addItem("Dus Seti (Robot/Surgulu)", "dus")
 self.combo_urun_tipi.addItem("Petek (Radyator/Havlupan)", "petek")
 urun_layout.addRow("Urun Tipi:", self.combo_urun_tipi)

 # Adet
 self.spin_adet = QSpinBox()
 self.spin_adet.setRange(1, 1000)
 self.spin_adet.setValue(1)
 self.spin_adet.setSuffix(" adet")
 urun_layout.addRow("Adet:", self.spin_adet)

 urun_group.setLayout(urun_layout)
 layout.addWidget(urun_group)

 # Ekle butonu
 btn_ekle = QPushButton("+ URUN EKLE")
 btn_ekle.clicked.connect(self.urun_ekle)
 layout.addWidget(btn_ekle)

 # === URUN LISTESI ===
 liste_group = QGroupBox("2. Urun Listesi")
 liste_layout = QVBoxLayout()

 self.table_urunler = QTableWidget()
 self.table_urunler.setColumnCount(2)
 self.table_urunler.setHorizontalHeaderLabels(["Urun Tipi", "Adet"])
 self.table_urunler.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
 self.table_urunler.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
 self.table_urunler.setMaximumHeight(150)
 liste_layout.addWidget(self.table_urunler)

 # Sil ve Temizle butonlari
 btn_layout = QHBoxLayout()
 btn_sil = QPushButton("Secili Sil")
 btn_sil.setObjectName("btn_sil")
 btn_sil.clicked.connect(self.secili_sil)
 btn_layout.addWidget(btn_sil)

 btn_temizle = QPushButton("Tumu Temizle")
 btn_temizle.setObjectName("btn_temizle")
 btn_temizle.clicked.connect(self.tumu_temizle)
 btn_layout.addWidget(btn_temizle)
 liste_layout.addLayout(btn_layout)

 liste_group.setLayout(liste_layout)
 layout.addWidget(liste_group)

 # === BIRIM FIYATLAR ===
 fiyat_group = QGroupBox("3. Birim Fiyatlar (Urun Bedeli)")
 fiyat_layout = QFormLayout()

 self.spin_batarya_fiyat = QDoubleSpinBox()
 self.spin_batarya_fiyat.setRange(0, 1000000)
 self.spin_batarya_fiyat.setValue(3500)
 self.spin_batarya_fiyat.setSuffix(" TL")
 self.spin_batarya_fiyat.setDecimals(2)
 fiyat_layout.addRow("Batarya:", self.spin_batarya_fiyat)

 self.spin_musluk_fiyat = QDoubleSpinBox()
 self.spin_musluk_fiyat.setRange(0, 1000000)
 self.spin_musluk_fiyat.setValue(850)
 self.spin_musluk_fiyat.setSuffix(" TL")
 self.spin_musluk_fiyat.setDecimals(2)
 fiyat_layout.addRow("Musluk:", self.spin_musluk_fiyat)

 self.spin_klozet_fiyat = QDoubleSpinBox()
 self.spin_klozet_fiyat.setRange(0, 1000000)
 self.spin_klozet_fiyat.setValue(5500)
 self.spin_klozet_fiyat.setSuffix(" TL")
 self.spin_klozet_fiyat.setDecimals(2)
 fiyat_layout.addRow("Klozet Takim:", self.spin_klozet_fiyat)

 self.spin_alaturka_fiyat = QDoubleSpinBox()
 self.spin_alaturka_fiyat.setRange(0, 1000000)
 self.spin_alaturka_fiyat.setValue(1800)
 self.spin_alaturka_fiyat.setSuffix(" TL")
 self.spin_alaturka_fiyat.setDecimals(2)
 fiyat_layout.addRow("Alaturka Tas:", self.spin_alaturka_fiyat)

 self.spin_dus_fiyat = QDoubleSpinBox()
 self.spin_dus_fiyat.setRange(0, 1000000)
 self.spin_dus_fiyat.setValue(4200)
 self.spin_dus_fiyat.setSuffix(" TL")
 self.spin_dus_fiyat.setDecimals(2)
 fiyat_layout.addRow("Dus Seti:", self.spin_dus_fiyat)

 self.spin_petek_fiyat = QDoubleSpinBox()
 self.spin_petek_fiyat.setRange(0, 1000000)
 self.spin_petek_fiyat.setValue(6500)
 self.spin_petek_fiyat.setSuffix(" TL")
 self.spin_petek_fiyat.setDecimals(2)
 fiyat_layout.addRow("Petek:", self.spin_petek_fiyat)

 # Separator
 sep_label = QLabel("--- Montaj Iscilik ---")
 sep_label.setStyleSheet("color: #888; font-size: 10px;")
 sep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
 fiyat_layout.addRow(sep_label)

 self.spin_montaj_fiyat = QDoubleSpinBox()
 self.spin_montaj_fiyat.setRange(0, 100000)
 self.spin_montaj_fiyat.setValue(350)
 self.spin_montaj_fiyat.setSuffix(" TL/adet")
 self.spin_montaj_fiyat.setDecimals(2)
 fiyat_layout.addRow("Montaj Ucreti:", self.spin_montaj_fiyat)

 fiyat_group.setLayout(fiyat_layout)
 layout.addWidget(fiyat_group)

 # === HESAPLA BUTONU ===
 btn_hesapla = QPushButton("HESAPLA")
 btn_hesapla.setFixedHeight(50)
 btn_hesapla.setFont(QFont("Arial", 12, QFont.Weight.Bold))
 btn_hesapla.setStyleSheet("""
 QPushButton {
 background-color: #00FF00;
 color: #000;
 border: 2px solid #00AA00;
 font-size: 14px;
 }
 QPushButton:hover {
 background-color: #00DD00;
 }
 """)
 btn_hesapla.clicked.connect(self.hesapla)
 layout.addWidget(btn_hesapla)

 layout.addStretch()
 panel.setLayout(layout)
 return panel

 def _create_results_panel(self) -> QGroupBox:
     """Sonuc panelini olustur"""
 panel = QGroupBox("Hesaplama Sonuclari")
 layout = QVBoxLayout()

 # Sonuc frame'i
 sonuc_frame = QFrame()
 sonuc_frame.setObjectName("sonuc_frame")
 sonuc_layout = QGridLayout(sonuc_frame)
 sonuc_layout.setSpacing(10)

 row = 0

 # Baslik
 baslik = QLabel("VITRIFIYE VE ARMATUR LISTESI")
 baslik.setStyleSheet("color: #00CED1; font-size: 14px; font-weight: bold;")
 baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
 sonuc_layout.addWidget(baslik, row, 0, 1, 2)
 row += 1

 # Ayirici
 sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
 row += 1

 # ADET DOKUMU BOLUMU
 adet_baslik = QLabel("ADET DOKUMU")
 adet_baslik.setStyleSheet("color: #FFD700; font-weight: bold;")
 sonuc_layout.addWidget(adet_baslik, row, 0, 1, 2)
 row += 1

 # Batarya/Musluk
 sonuc_layout.addWidget(self._create_label("Batarya / Musluk:"), row, 0)
 self.lbl_batarya_musluk = self._create_value_label("-")
 sonuc_layout.addWidget(self.lbl_batarya_musluk, row, 1)
 row += 1

 # Klozet/Alaturka
 sonuc_layout.addWidget(self._create_label("Klozet / Alaturka:"), row, 0)
 self.lbl_klozet_alaturka = self._create_value_label("-")
 sonuc_layout.addWidget(self.lbl_klozet_alaturka, row, 1)
 row += 1

 # Dus/Petek
 sonuc_layout.addWidget(self._create_label("Dus Seti / Petek:"), row, 0)
 self.lbl_dus_petek = self._create_value_label("-")
 sonuc_layout.addWidget(self.lbl_dus_petek, row, 1)
 row += 1

 # Toplam Parca
 sonuc_layout.addWidget(self._create_label("Toplam Parca Sayisi:"), row, 0)
 self.lbl_toplam_parca = self._create_value_label("- adet", "#00CED1")
 sonuc_layout.addWidget(self.lbl_toplam_parca, row, 1)
 row += 1

 # Ayirici
 sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
 row += 1

 # MALIYET KIRILIMI BOLUMU
 maliyet_baslik = QLabel("MALIYET KIRILIMI")
 maliyet_baslik.setStyleSheet("color: #FFD700; font-weight: bold;")
 sonuc_layout.addWidget(maliyet_baslik, row, 0, 1, 2)
 row += 1

 # Malzeme Bedeli
 sonuc_layout.addWidget(self._create_label("Urun Malzeme Bedeli:"), row, 0)
 self.lbl_malzeme_tl = self._create_value_label("- TL", "#00FF00")
 sonuc_layout.addWidget(self.lbl_malzeme_tl, row, 1)
 row += 1

 # Montaj Iscilik
 sonuc_layout.addWidget(self._create_label("Montaj Iscilik Bedeli:"), row, 0)
 self.lbl_iscilik_tl = self._create_value_label("- TL", "#00FF00")
 sonuc_layout.addWidget(self.lbl_iscilik_tl, row, 1)
 row += 1

 # Ayirici
 sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
 row += 1

 # GENEL TOPLAM
 toplam_label = QLabel("GENEL TOPLAM:")
 toplam_label.setStyleSheet("color: #00FF00; font-size: 16px; font-weight: bold;")
 sonuc_layout.addWidget(toplam_label, row, 0)

 self.lbl_toplam = QLabel("- TL")
 self.lbl_toplam.setStyleSheet("color: #00FF00; font-size: 20px; font-weight: bold;")
 self.lbl_toplam.setAlignment(Qt.AlignmentFlag.AlignRight)
 sonuc_layout.addWidget(self.lbl_toplam, row, 1)

 layout.addWidget(sonuc_frame)

 # JSON Cikti Goster
 json_group = QGroupBox("JSON Cikti")
 json_layout = QVBoxLayout()

 self.lbl_json = QLabel("")
 self.lbl_json.setStyleSheet("""
 color: #00CED1;
 font-family: Consolas, monospace;
 font-size: 10px;
 background-color: #0a0a1a;
 padding: 10px;
 border-radius: 5px;
 """)
 self.lbl_json.setWordWrap(True)
 self.lbl_json.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

 scroll = QScrollArea()
 scroll.setWidget(self.lbl_json)
 scroll.setWidgetResizable(True)
 scroll.setMaximumHeight(200)
 scroll.setStyleSheet("background-color: #0a0a1a; border: 1px solid #00CED1;")

 json_layout.addWidget(scroll)
 json_group.setLayout(json_layout)
 layout.addWidget(json_group)

 # Metraya Aktar butonu
 btn_metraya_aktar = QPushButton(" Metraya Aktar")
 btn_metraya_aktar.setStyleSheet("background-color: #FF6600; color: white; font-weight: bold; padding: 8px;")
 btn_metraya_aktar.clicked.connect(self._metraya_aktar)
 layout.addWidget(btn_metraya_aktar)

 layout.addStretch()
 panel.setLayout(layout)
 return panel

 def _create_label(self, text: str) -> QLabel:
     """Normal etiket olustur"""
 label = QLabel(text)
 label.setStyleSheet("color: #e0e0e0;")
 return label

 def _create_value_label(self, text: str, color: str = "#FFFFFF") -> QLabel:
     """Deger etiketi olustur"""
 label = QLabel(text)
 label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")
 label.setAlignment(Qt.AlignmentFlag.AlignRight)
 return label

 def _create_separator(self) -> QFrame:
     """Ayirici cizgi olustur"""
 line = QFrame()
 line.setFrameShape(QFrame.Shape.HLine)
 line.setStyleSheet("background-color: #00CED1;")
 line.setFixedHeight(1)
 return line

 def urun_ekle(self):
     """Listeye urun ekle"""
 tip = self.combo_urun_tipi.currentData()
 tip_adi = self.combo_urun_tipi.currentText()
 adet = self.spin_adet.value()

 urun = {
 'tip': tip,
 'tip_adi': tip_adi,
 'adet': adet
 }

 self.urun_listesi.append(urun)
 self._tabloya_ekle(urun)
 logger.info(f"Urun eklendi: {urun}")

 def _tabloya_ekle(self, urun: dict):
     """Tabloya urun ekle"""
 row = self.table_urunler.rowCount()
 self.table_urunler.insertRow(row)

 self.table_urunler.setItem(row, 0, QTableWidgetItem(urun['tip_adi']))
 self.table_urunler.setItem(row, 1, QTableWidgetItem(str(urun['adet'])))

 def secili_sil(self):
     """Secili urunu sil"""
 selected_rows = self.table_urunler.selectionModel().selectedRows()
 if not selected_rows:
     QMessageBox.warning(self, "Uyari", "Lutfen silmek icin bir urun secin.")
 return

 rows = sorted([r.row() for r in selected_rows], reverse=True)
 for row in rows:
     self.table_urunler.removeRow(row)
 del self.urun_listesi[row]

 def tumu_temizle(self):
     """Tum urunleri temizle"""
 self.urun_listesi.clear()
 self.table_urunler.setRowCount(0)

 def hesapla(self):
     """Hesaplama yap"""
 try:
     if not self.urun_listesi:
         QMessageBox.warning(self, "Uyari", "Lutfen en az bir urun ekleyin.")
     return

 # Fiyatlari al
     fiyatlar = {
 'batarya_fiyat': self.spin_batarya_fiyat.value(),
 'musluk_fiyat': self.spin_musluk_fiyat.value(),
 'klozet_takim_fiyat': self.spin_klozet_fiyat.value(),
 'alaturka_tas_fiyat': self.spin_alaturka_fiyat.value(),
 'dus_basligi_set_fiyat': self.spin_dus_fiyat.value(),
 'petek_fiyat': self.spin_petek_fiyat.value(),
 'montaj_ucreti_adet': self.spin_montaj_fiyat.value()
 }

 # Hesapla
     sonuc = hesapla_vitrifiye_armatur(
 urun_listesi=self.urun_listesi,
 fiyatlar=fiyatlar
 )

 # Sonuclari goster
     self.son_hesaplama = sonuc
     self._sonuclari_goster(sonuc)
     logger.info(f"Vitrifiye hesaplama yapildi: {sonuc}")

 except Exception as e:
     logger.error(f"Hesaplama hatasi: {e}")
 QMessageBox.critical(self, "Hata", f"Hesaplama sirasinda hata:\n{str(e)}")

 def _sonuclari_goster(self, sonuc: dict):
     """Sonuclari arayuzde goster"""
 adet = sonuc['adet_dokumu']
 maliyet = sonuc['maliyet_detayi_tl']

 # Adet Dokumu
 self.lbl_batarya_musluk.setText(adet['batarya_musluk_grubu'])
 self.lbl_klozet_alaturka.setText(adet['tuvalet_grubu'])
 self.lbl_dus_petek.setText(adet['banyo_ve_isitma'])
 self.lbl_toplam_parca.setText(f"{adet['toplam_parca_sayisi']} adet")

 # Maliyet Kirilimi
 self.lbl_malzeme_tl.setText(f"{maliyet['urun_malzeme_bedeli']:,.2f} TL")
 self.lbl_iscilik_tl.setText(f"{maliyet['montaj_iscilik_bedeli']:,.2f} TL")

 # Genel Toplam
 self.lbl_toplam.setText(f"{sonuc['genel_toplam_tl']:,.2f} TL")

 # JSON cikti
 import json
 json_str = json.dumps(sonuc, indent=2, ensure_ascii=False)
 self.lbl_json.setText(json_str)

 def _metraya_aktar(self):
     """Hesaplama sonucunu metraj listesine aktar"""
 if self.son_hesaplama is None:
     from PyQt6.QtWidgets import QMessageBox
 QMessageBox.warning(self, "Uyarı", "Önce bir hesaplama yapın!")
 return
 self.hesaplama_tamamlandi.emit(self.son_hesaplama)
