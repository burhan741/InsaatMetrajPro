"""
Metal Isleri (Demir Dograma & Aluminyum) Maliyet Hesaplama Penceresi
Korkuluk, Pencere Demiri, Bahce Kapisi maliyet hesaplama arayuzu
"""

from PyQt6.QtWidgets import (
 QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
 QPushButton, QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
 QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView,
 QFormLayout, QMessageBox, QFrame, QGridLayout, QScrollArea,
 QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import logging

from app.core.calculator import hesapla_metal_isleri

logger = logging.getLogger(__name__)


class MetalIsleriMaliyetWindow(QMainWindow):
 """Metal isleri maliyet hesaplama penceresi"""

 hesaplama_tamamlandi = pyqtSignal(dict)

 def __init__(self, parent=None):
 super().__init__(parent)
 self.is_listesi = []
 self.son_hesaplama = None
 self.init_ui()

 def init_ui(self):
 """Arayuzu olustur"""
 self.setWindowTitle("Metal Isleri Maliyet Hesaplama (Korkuluk/Pencere Demiri/Kapi)")
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
 border: 1px solid #708090;
 padding: 5px;
 border-radius: 3px;
 min-height: 25px;
 }
 QComboBox::drop-down {
 border: none;
 }
 QPushButton {
 background-color: #708090;
 color: #FFFFFF;
 border: none;
 padding: 10px;
 border-radius: 4px;
 font-weight: bold;
 }
 QPushButton:hover {
 background-color: #778899;
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
 color: #B0C4DE;
 border: 2px solid #708090;
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
 gridline-color: #708090;
 border: 1px solid #708090;
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
 color: #B0C4DE;
 padding: 5px;
 border: 1px solid #708090;
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
 panel = QGroupBox("Is Kalemi Girisi ve Fiyatlar")
 layout = QVBoxLayout()
 layout.setSpacing(10)

 # === IS KALEMI EKLEME ===
 is_group = QGroupBox("1. Is Kalemi Ekle")
 is_layout = QFormLayout()

 # Is turu
 self.combo_is_turu = QComboBox()
 self.combo_is_turu.addItem("Balkon Korkulugu (mt)", "balkon_korkuluk")
 self.combo_is_turu.addItem("Merdiven Korkulugu/Kupeste (mt)", "merdiven_korkuluk")
 self.combo_is_turu.addItem("Pencere Demiri (m2)", "pencere_demiri")
 self.combo_is_turu.addItem("Bahce/Garaj Kapisi (adet)", "bahce_kapisi")
 self.combo_is_turu.currentIndexChanged.connect(self._tur_degisti)
 is_layout.addRow("Is Turu:", self.combo_is_turu)

 # Stacked widget - tur'e gore farkli girdi alanlari
 self.stacked = QStackedWidget()

 # Page 0: Korkuluk (uzunluk)
 korkuluk_widget = QWidget()
 korkuluk_layout = QFormLayout(korkuluk_widget)
 self.spin_uzunluk = QDoubleSpinBox()
 self.spin_uzunluk.setRange(0.1, 10000)
 self.spin_uzunluk.setValue(10)
 self.spin_uzunluk.setSuffix(" mt")
 self.spin_uzunluk.setDecimals(2)
 korkuluk_layout.addRow("Uzunluk:", self.spin_uzunluk)
 self.stacked.addWidget(korkuluk_widget)

 # Page 1: Pencere Demiri (en x boy veya m2)
 pencere_widget = QWidget()
 pencere_layout = QFormLayout(pencere_widget)
 self.spin_pencere_en = QDoubleSpinBox()
 self.spin_pencere_en.setRange(1, 1000)
 self.spin_pencere_en.setValue(120)
 self.spin_pencere_en.setSuffix(" cm")
 self.spin_pencere_en.setDecimals(1)
 pencere_layout.addRow("En:", self.spin_pencere_en)

 self.spin_pencere_boy = QDoubleSpinBox()
 self.spin_pencere_boy.setRange(1, 1000)
 self.spin_pencere_boy.setValue(150)
 self.spin_pencere_boy.setSuffix(" cm")
 self.spin_pencere_boy.setDecimals(1)
 pencere_layout.addRow("Boy:", self.spin_pencere_boy)

 self.spin_pencere_adet = QSpinBox()
 self.spin_pencere_adet.setRange(1, 1000)
 self.spin_pencere_adet.setValue(4)
 self.spin_pencere_adet.setSuffix(" adet")
 pencere_layout.addRow("Adet:", self.spin_pencere_adet)

 self.lbl_pencere_alan = QLabel("Toplam: 7.20 m2")
 self.lbl_pencere_alan.setStyleSheet("color: #FFD700; font-size: 11px;")
 pencere_layout.addRow("", self.lbl_pencere_alan)

 self.spin_pencere_en.valueChanged.connect(self._pencere_alan_hesapla)
 self.spin_pencere_boy.valueChanged.connect(self._pencere_alan_hesapla)
 self.spin_pencere_adet.valueChanged.connect(self._pencere_alan_hesapla)

 self.stacked.addWidget(pencere_widget)

 # Page 2: Bahce Kapisi (adet)
 kapi_widget = QWidget()
 kapi_layout = QFormLayout(kapi_widget)
 self.spin_kapi_adet = QSpinBox()
 self.spin_kapi_adet.setRange(1, 100)
 self.spin_kapi_adet.setValue(1)
 self.spin_kapi_adet.setSuffix(" adet")
 kapi_layout.addRow("Adet:", self.spin_kapi_adet)
 self.stacked.addWidget(kapi_widget)

 is_layout.addRow(self.stacked)
 is_group.setLayout(is_layout)
 layout.addWidget(is_group)

 # Ekle butonu
 btn_ekle = QPushButton("+ IS KALEMI EKLE")
 btn_ekle.clicked.connect(self.is_kalemi_ekle)
 layout.addWidget(btn_ekle)

 # === IS LISTESI ===
 liste_group = QGroupBox("2. Is Kalemleri Listesi")
 liste_layout = QVBoxLayout()

 self.table_isler = QTableWidget()
 self.table_isler.setColumnCount(3)
 self.table_isler.setHorizontalHeaderLabels(["Tur", "Olcu", "Deger"])
 self.table_isler.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
 self.table_isler.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
 self.table_isler.setMaximumHeight(150)
 liste_layout.addWidget(self.table_isler)

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
 fiyat_group = QGroupBox("3. Birim Fiyatlar (Montaj Dahil)")
 fiyat_layout = QFormLayout()

 self.spin_korkuluk_fiyat = QDoubleSpinBox()
 self.spin_korkuluk_fiyat.setRange(0, 1000000)
 self.spin_korkuluk_fiyat.setValue(2500)
 self.spin_korkuluk_fiyat.setSuffix(" TL/mt")
 self.spin_korkuluk_fiyat.setDecimals(2)
 fiyat_layout.addRow("Korkuluk:", self.spin_korkuluk_fiyat)

 self.spin_pencere_fiyat = QDoubleSpinBox()
 self.spin_pencere_fiyat.setRange(0, 1000000)
 self.spin_pencere_fiyat.setValue(1800)
 self.spin_pencere_fiyat.setSuffix(" TL/m2")
 self.spin_pencere_fiyat.setDecimals(2)
 fiyat_layout.addRow("Pencere Demiri:", self.spin_pencere_fiyat)

 self.spin_kapi_fiyat = QDoubleSpinBox()
 self.spin_kapi_fiyat.setRange(0, 1000000)
 self.spin_kapi_fiyat.setValue(35000)
 self.spin_kapi_fiyat.setSuffix(" TL/adet")
 self.spin_kapi_fiyat.setDecimals(2)
 fiyat_layout.addRow("Bahce Kapisi:", self.spin_kapi_fiyat)

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
 baslik = QLabel("DEMIR VE ALUMINYUM DOGRAMA DOKUMU")
 baslik.setStyleSheet("color: #B0C4DE; font-size: 14px; font-weight: bold;")
 baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
 sonuc_layout.addWidget(baslik, row, 0, 1, 2)
 row += 1

 # Ayirici
 sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
 row += 1

 # METRAJLAR BOLUMU
 metraj_baslik = QLabel("METRAJLAR")
 metraj_baslik.setStyleSheet("color: #FFD700; font-weight: bold;")
 sonuc_layout.addWidget(metraj_baslik, row, 0, 1, 2)
 row += 1

 # Korkuluk
 sonuc_layout.addWidget(self._create_label("Toplam Korkuluk:"), row, 0)
 self.lbl_korkuluk = self._create_value_label("- mt")
 sonuc_layout.addWidget(self.lbl_korkuluk, row, 1)
 row += 1

 # Pencere Demiri
 sonuc_layout.addWidget(self._create_label("Pencere Koruma:"), row, 0)
 self.lbl_pencere = self._create_value_label("- m2")
 sonuc_layout.addWidget(self.lbl_pencere, row, 1)
 row += 1

 # Bahce Kapisi
 sonuc_layout.addWidget(self._create_label("Bahce Kapisi:"), row, 0)
 self.lbl_kapi = self._create_value_label("- adet")
 sonuc_layout.addWidget(self.lbl_kapi, row, 1)
 row += 1

 # Ayirici
 sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
 row += 1

 # MALIYET TABLOSU BOLUMU
 maliyet_baslik = QLabel("MALIYET TABLOSU")
 maliyet_baslik.setStyleSheet("color: #FFD700; font-weight: bold;")
 sonuc_layout.addWidget(maliyet_baslik, row, 0, 1, 2)
 row += 1

 # Korkuluk Tutari
 sonuc_layout.addWidget(self._create_label("Korkuluk Tutari:"), row, 0)
 self.lbl_korkuluk_tl = self._create_value_label("- TL", "#00FF00")
 sonuc_layout.addWidget(self.lbl_korkuluk_tl, row, 1)
 row += 1

 # Pencere Demir Tutari
 sonuc_layout.addWidget(self._create_label("Pencere Demir Tutari:"), row, 0)
 self.lbl_pencere_tl = self._create_value_label("- TL", "#00FF00")
 sonuc_layout.addWidget(self.lbl_pencere_tl, row, 1)
 row += 1

 # Kapi Tutari
 sonuc_layout.addWidget(self._create_label("Kapi Tutari:"), row, 0)
 self.lbl_kapi_tl = self._create_value_label("- TL", "#00FF00")
 sonuc_layout.addWidget(self.lbl_kapi_tl, row, 1)
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
 color: #B0C4DE;
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
 scroll.setStyleSheet("background-color: #0a0a1a; border: 1px solid #708090;")

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
 line.setStyleSheet("background-color: #708090;")
 line.setFixedHeight(1)
 return line

 def _tur_degisti(self, index):
 """Is turu degistiginde ilgili girdi alanini goster"""
 tur = self.combo_is_turu.currentData()
 if tur in ['balkon_korkuluk', 'merdiven_korkuluk']:
 self.stacked.setCurrentIndex(0)
 elif tur == 'pencere_demiri':
 self.stacked.setCurrentIndex(1)
 self._pencere_alan_hesapla()
 elif tur == 'bahce_kapisi':
 self.stacked.setCurrentIndex(2)

 def _pencere_alan_hesapla(self):
 """Pencere demiri alan hesapla"""
 en = self.spin_pencere_en.value()
 boy = self.spin_pencere_boy.value()
 adet = self.spin_pencere_adet.value()
 alan = (en * boy / 10000) * adet
 self.lbl_pencere_alan.setText(f"Toplam: {alan:.2f} m2")

 def is_kalemi_ekle(self):
 """Listeye is kalemi ekle"""
 tur = self.combo_is_turu.currentData()
 tur_adi = self.combo_is_turu.currentText()

 if tur in ['balkon_korkuluk', 'merdiven_korkuluk']:
 miktar = self.spin_uzunluk.value()
 is_kalemi = {
 'tur': tur,
 'tur_adi': tur_adi,
 'miktar': miktar,
 'birim': 'mt'
 }
 elif tur == 'pencere_demiri':
 en = self.spin_pencere_en.value()
 boy = self.spin_pencere_boy.value()
 adet = self.spin_pencere_adet.value()
 alan = (en * boy / 10000) * adet
 is_kalemi = {
 'tur': tur,
 'tur_adi': tur_adi,
 'en': en,
 'boy': boy,
 'adet': adet,
 'miktar': alan,
 'birim': 'm2'
 }
 elif tur == 'bahce_kapisi':
 adet = self.spin_kapi_adet.value()
 is_kalemi = {
 'tur': tur,
 'tur_adi': tur_adi,
 'adet': adet,
 'miktar': adet,
 'birim': 'adet'
 }

 self.is_listesi.append(is_kalemi)
 self._tabloya_ekle(is_kalemi)
 logger.info(f"Is kalemi eklendi: {is_kalemi}")

 def _tabloya_ekle(self, is_kalemi: dict):
 """Tabloya is kalemi ekle"""
 row = self.table_isler.rowCount()
 self.table_isler.insertRow(row)

 tur_kisa = is_kalemi['tur_adi'].split('(')[0].strip()
 self.table_isler.setItem(row, 0, QTableWidgetItem(tur_kisa))
 self.table_isler.setItem(row, 1, QTableWidgetItem(is_kalemi['birim']))
 self.table_isler.setItem(row, 2, QTableWidgetItem(f"{is_kalemi['miktar']:.2f}"))

 def secili_sil(self):
 """Secili is kalemini sil"""
 selected_rows = self.table_isler.selectionModel().selectedRows()
 if not selected_rows:
 QMessageBox.warning(self, "Uyari", "Lutfen silmek icin bir is kalemi secin.")
 return

 rows = sorted([r.row() for r in selected_rows], reverse=True)
 for row in rows:
 self.table_isler.removeRow(row)
 del self.is_listesi[row]

 def tumu_temizle(self):
 """Tum is kalemlerini temizle"""
 self.is_listesi.clear()
 self.table_isler.setRowCount(0)

 def hesapla(self):
 """Hesaplama yap"""
 try:
 if not self.is_listesi:
 QMessageBox.warning(self, "Uyari", "Lutfen en az bir is kalemi ekleyin.")
 return

 # Fiyatlari al
 fiyatlar = {
 'korkuluk_mt_fiyat': self.spin_korkuluk_fiyat.value(),
 'pencere_demiri_m2_fiyat': self.spin_pencere_fiyat.value(),
 'bahce_kapisi_fiyat': self.spin_kapi_fiyat.value()
 }

 # Hesapla
 sonuc = hesapla_metal_isleri(
 girdiler=self.is_listesi,
 fiyatlar=fiyatlar
 )

 # Sonuclari goster
 self.son_hesaplama = sonuc
 self._sonuclari_goster(sonuc)
 logger.info(f"Metal isleri hesaplama yapildi: {sonuc}")

 except Exception as e:
 logger.error(f"Hesaplama hatasi: {e}")
 QMessageBox.critical(self, "Hata", f"Hesaplama sirasinda hata:\n{str(e)}")

 def _sonuclari_goster(self, sonuc: dict):
 """Sonuclari arayuzde goster"""
 metraj = sonuc['metrajlar']
 maliyet = sonuc['maliyet_tablosu_tl']

 # Metrajlar
 self.lbl_korkuluk.setText(f"{metraj['toplam_korkuluk_mt']:.2f} mt")
 self.lbl_pencere.setText(f"{metraj['pencere_koruma_m2']:.2f} m2")
 self.lbl_kapi.setText(f"{metraj['bahce_kapisi_adet']} adet")

 # Maliyet Tablosu
 self.lbl_korkuluk_tl.setText(f"{maliyet['korkuluk_tutari']:,.2f} TL")
 self.lbl_pencere_tl.setText(f"{maliyet['pencere_demir_tutari']:,.2f} TL")
 self.lbl_kapi_tl.setText(f"{maliyet['kapi_tutari']:,.2f} TL")

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
