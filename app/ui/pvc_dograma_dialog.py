"""
PVC Dograma (Pencere ve Kapi) Hesaplama Dialog Penceresi
========================================================
Kullanici dostu arayuz ile PVC pencere ve kapi maliyet hesabi.

Yazar: Insaat Metraj Pro
Versiyon: 1.0
"""

from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import (
 QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
 QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
 QLabel, QTextEdit, QMessageBox, QGroupBox, QTableWidget,
 QTableWidgetItem, QHeaderView, QScrollArea, QWidget, QFrame,
 QCheckBox, QTabWidget, QSplitter, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush

from app.core.pvc_dograma_hesaplama import (
 hesapla_pvc_dograma_detayli,
 get_standart_pencere_boyutlari,
 get_tip_aciklama,
 format_para,
 rapor_olustur,
 VARSAYILAN_FIYATLAR
)


class DogramaEklemeDialog(QDialog):
 """Dograma ekleme alt dialogu"""

 def __init__(self, parent=None, dograma_data: Optional[Dict] = None):
 super().__init__(parent)
 self.setWindowTitle("Dograma Ekle" if not dograma_data else "Dograma Duzenle")
 self.setMinimumWidth(450)
 self.dograma_data = dograma_data
 self.init_ui()

 if dograma_data:
 self.load_data()

 def init_ui(self):
 layout = QVBoxLayout(self)

 # Standart boyutlar
 std_group = QGroupBox("Standart Boyutlar")
 std_layout = QHBoxLayout(std_group)

 self.standart_combo = QComboBox()
 self.standart_combo.addItem("-- Ozel Boyut --", None)
 for std in get_standart_pencere_boyutlari():
 self.standart_combo.addItem(std['ad'], std)
 self.standart_combo.currentIndexChanged.connect(self.on_standart_selected)
 std_layout.addWidget(self.standart_combo)
 layout.addWidget(std_group)

 # Form
 form = QFormLayout()

 # Aciklama
 self.aciklama_input = QLineEdit()
 self.aciklama_input.setPlaceholderText("Orn: Salon Penceresi")
 form.addRow("Aciklama:", self.aciklama_input)

 # En
 self.en_spin = QDoubleSpinBox()
 self.en_spin.setRange(30, 500)
 self.en_spin.setValue(120)
 self.en_spin.setSuffix(" cm")
 self.en_spin.valueChanged.connect(self.update_hesap)
 form.addRow("En (Genislik):", self.en_spin)

 # Boy
 self.boy_spin = QDoubleSpinBox()
 self.boy_spin.setRange(30, 300)
 self.boy_spin.setValue(150)
 self.boy_spin.setSuffix(" cm")
 self.boy_spin.valueChanged.connect(self.update_hesap)
 form.addRow("Boy (Yukseklik):", self.boy_spin)

 # Adet
 self.adet_spin = QSpinBox()
 self.adet_spin.setRange(1, 200)
 self.adet_spin.setValue(1)
 self.adet_spin.valueChanged.connect(self.update_hesap)
 form.addRow("Adet:", self.adet_spin)

 # Tip
 self.tip_combo = QComboBox()
 self.tip_combo.addItem("Sabit (Acilmaz)", "sabit")
 self.tip_combo.addItem("Tek Acilir", "tek_acilir")
 self.tip_combo.addItem("Cift Acilir (Orta Kayitli)", "cift_acilir_orta_kayitli")
 self.tip_combo.addItem("Balkon Kapisi", "balkon_kapisi")
 self.tip_combo.currentIndexChanged.connect(self.on_tip_changed)
 form.addRow("Tip:", self.tip_combo)

 # Vasistas
 self.vasistas_check = QCheckBox("Vasistas (Cift Acilim) Mekanizmasi")
 self.vasistas_check.setToolTip("Aksesuar maliyetini %50 arttirir")
 form.addRow("", self.vasistas_check)

 # Sineklik
 self.sineklik_check = QCheckBox("Sineklik Ekle")
 form.addRow("", self.sineklik_check)

 # Hesaplanan
 self.hesap_label = QLabel()
 self.hesap_label.setStyleSheet("color: #2196F3; font-weight: bold; padding: 10px;")
 self.hesap_label.setWordWrap(True)
 form.addRow("Hesaplanan:", self.hesap_label)

 layout.addLayout(form)

 # Butonlar
 btn_layout = QHBoxLayout()
 btn_layout.addStretch()

 btn_cancel = QPushButton("Iptal")
 btn_cancel.clicked.connect(self.reject)
 btn_layout.addWidget(btn_cancel)

 btn_save = QPushButton("Ekle" if not self.dograma_data else "Guncelle")
 btn_save.clicked.connect(self.accept)
 btn_save.setDefault(True)
 btn_save.setStyleSheet("background-color: #2196F3; color: white; padding: 8px 20px;")
 btn_layout.addWidget(btn_save)

 layout.addLayout(btn_layout)
 self.update_hesap()

 def on_standart_selected(self, index):
 """Standart secildiginde"""
 data = self.standart_combo.currentData()
 if data:
 self.en_spin.setValue(data['en_cm'])
 self.boy_spin.setValue(data['boy_cm'])

 # Tipi ayarla
 tip = data.get('tip', 'tek_acilir')
 tip_index = self.tip_combo.findData(tip)
 if tip_index >= 0:
 self.tip_combo.setCurrentIndex(tip_index)

 if not self.aciklama_input.text():
 self.aciklama_input.setText(data['ad'])

 def on_tip_changed(self, index):
 """Tip degistiginde vasistas secenegini ayarla"""
 tip = self.tip_combo.currentData()
 # Sabit pencerede vasistas olmaz
 if tip == 'sabit':
 self.vasistas_check.setEnabled(False)
 self.vasistas_check.setChecked(False)
 else:
 self.vasistas_check.setEnabled(True)

 self.update_hesap()

 def update_hesap(self):
 """Hesaplanan degerleri goster"""
 en = self.en_spin.value()
 boy = self.boy_spin.value()
 adet = self.adet_spin.value()
 tip = self.tip_combo.currentData()

 brut_alan = (en * boy) / 10000
 net_cam = brut_alan * 0.85

 # Profil metraji tahmini
 fire = 1.20 if tip == 'balkon_kapisi' else 1.15
 if tip == 'sabit':
 profil_cm = 2 * (en + boy) * fire
 elif tip == 'tek_acilir':
 kasa = 2 * (en + boy)
 kanat = 2 * ((en - 10) + (boy - 10))
 profil_cm = (kasa + kanat) * fire
 elif tip == 'cift_acilir_orta_kayitli':
 kasa = 2 * (en + boy)
 orta = boy
 kanat = 2 * (2 * ((en / 2) + boy))
 profil_cm = (kasa + orta + kanat) * fire
 else: # balkon_kapisi
 kasa = 2 * (en + boy)
 kanat = 2 * (en + boy)
 profil_cm = (kasa + kanat) * fire

 profil_m = profil_cm / 100

 self.hesap_label.setText(
 f"Brut Alan: {brut_alan:.3f} m2\n"
 f"Net Cam Alani: {net_cam:.3f} m2 (-%15 profil)\n"
 f"Profil Metraji: {profil_m:.2f} mtul\n"
 f"Toplam ({adet} adet): {net_cam*adet:.2f} m2 cam, {profil_m*adet:.2f} mtul profil"
 )

 def load_data(self):
 """Mevcut veriyi yukle"""
 if self.dograma_data:
 self.aciklama_input.setText(self.dograma_data.get('aciklama', ''))
 self.en_spin.setValue(self.dograma_data.get('en_cm', 120))
 self.boy_spin.setValue(self.dograma_data.get('boy_cm', 150))
 self.adet_spin.setValue(self.dograma_data.get('adet', 1))

 tip = self.dograma_data.get('tip', 'tek_acilir')
 tip_index = self.tip_combo.findData(tip)
 if tip_index >= 0:
 self.tip_combo.setCurrentIndex(tip_index)

 self.vasistas_check.setChecked(self.dograma_data.get('cift_acilim_aksesuar', False))
 self.sineklik_check.setChecked(self.dograma_data.get('sineklik_var_mi', False))

 def get_data(self) -> Dict[str, Any]:
 """Dialog verilerini al"""
 tip = self.tip_combo.currentData()
 return {
 'aciklama': self.aciklama_input.text().strip() or f"{self.en_spin.value():.0f}x{self.boy_spin.value():.0f} {get_tip_aciklama(tip)}",
 'en_cm': self.en_spin.value(),
 'boy_cm': self.boy_spin.value(),
 'adet': self.adet_spin.value(),
 'tip': tip,
 'cift_acilim_aksesuar': self.vasistas_check.isChecked(),
 'sineklik_var_mi': self.sineklik_check.isChecked()
 }


class PVCDogramaHesaplamaDialog(QDialog):
 """Ana PVC Dograma Hesaplama Dialog Penceresi"""

 hesaplama_tamamlandi = pyqtSignal(dict)

 def __init__(self, parent=None, db=None):
 super().__init__(parent)
 self.db = db
 self.dogramalar = []
 self.son_hesaplama = None

 self.setWindowTitle("PVC Dograma Hesaplama (Pencere ve Kapi)")
 self.setMinimumSize(1200, 850)
 self.init_ui()

 def init_ui(self):
 main_layout = QVBoxLayout(self)

 # Baslik
 baslik = QLabel("PVC DOGRAMA (PENCERE/KAPI) HESAPLAMA")
 baslik.setFont(QFont("Arial", 14, QFont.Weight.Bold))
 baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
 baslik.setStyleSheet("color: #2196F3; padding: 10px;")
 main_layout.addWidget(baslik)

 # Ana splitter
 splitter = QSplitter(Qt.Orientation.Horizontal)

 # =====================
 # SOL PANEL - GIRISLER
 # =====================
 sol_widget = QWidget()
 sol_layout = QVBoxLayout(sol_widget)

 # 1. Dograma Listesi
 dograma_group = QGroupBox("1. Dograma Listesi")
 dograma_layout = QVBoxLayout(dograma_group)

 self.dograma_table = QTableWidget()
 self.dograma_table.setColumnCount(7)
 self.dograma_table.setHorizontalHeaderLabels([
 "Aciklama", "En", "Boy", "Adet", "Tip", "Vasistas", "Sineklik"
 ])
 self.dograma_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
 self.dograma_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
 self.dograma_table.setMinimumHeight(180)
 dograma_layout.addWidget(self.dograma_table)

 # Butonlar
 dograma_btn_layout = QHBoxLayout()

 btn_ekle = QPushButton("+ Dograma Ekle")
 btn_ekle.clicked.connect(self.dograma_ekle)
 btn_ekle.setStyleSheet("background-color: #2196F3; color: white;")
 dograma_btn_layout.addWidget(btn_ekle)

 btn_duzenle = QPushButton("Duzenle")
 btn_duzenle.clicked.connect(self.dograma_duzenle)
 dograma_btn_layout.addWidget(btn_duzenle)

 btn_sil = QPushButton("Sil")
 btn_sil.clicked.connect(self.dograma_sil)
 btn_sil.setStyleSheet("background-color: #f44336; color: white;")
 dograma_btn_layout.addWidget(btn_sil)

 dograma_btn_layout.addStretch()
 dograma_layout.addLayout(dograma_btn_layout)

 self.dograma_ozet_label = QLabel("Toplam: 0 dograma")
 self.dograma_ozet_label.setStyleSheet("color: #666; font-style: italic;")
 dograma_layout.addWidget(self.dograma_ozet_label)

 sol_layout.addWidget(dograma_group)

 # 2. Profil ve Cam Secimi
 malzeme_group = QGroupBox("2. Malzeme Secimi")
 malzeme_layout = QFormLayout(malzeme_group)

 self.profil_rengi_combo = QComboBox()
 self.profil_rengi_combo.addItems(["Beyaz", "Agac Desenli", "Antrasit", "Kahverengi"])
 malzeme_layout.addRow("Profil Rengi:", self.profil_rengi_combo)

 self.cam_tipi_combo = QComboBox()
 self.cam_tipi_combo.addItems([
 "Tek Cam (4mm)",
 "Cift Cam (4+12+4)",
 "Isi Camli (Low-E)",
 "Lamine Cam"
 ])
 self.cam_tipi_combo.setCurrentIndex(1) # Cift cam varsayilan
 malzeme_layout.addRow("Cam Tipi:", self.cam_tipi_combo)

 sol_layout.addWidget(malzeme_group)

 # 3. Fiyatlar
 fiyat_group = QGroupBox("3. Birim Fiyatlar")
 fiyat_layout = QFormLayout(fiyat_group)

 self.profil_fiyat_spin = QDoubleSpinBox()
 self.profil_fiyat_spin.setRange(100, 2000)
 self.profil_fiyat_spin.setValue(VARSAYILAN_FIYATLAR['profil_mtul_fiyat'])
 self.profil_fiyat_spin.setSuffix(" TL/mtul")
 fiyat_layout.addRow("Profil:", self.profil_fiyat_spin)

 self.cam_fiyat_spin = QDoubleSpinBox()
 self.cam_fiyat_spin.setRange(100, 3000)
 self.cam_fiyat_spin.setValue(VARSAYILAN_FIYATLAR['cam_m2_fiyat'])
 self.cam_fiyat_spin.setSuffix(" TL/m2")
 fiyat_layout.addRow("Cam:", self.cam_fiyat_spin)

 self.aksesuar_fiyat_spin = QDoubleSpinBox()
 self.aksesuar_fiyat_spin.setRange(100, 3000)
 self.aksesuar_fiyat_spin.setValue(VARSAYILAN_FIYATLAR['aksesuar_set_fiyat'])
 self.aksesuar_fiyat_spin.setSuffix(" TL/set")
 self.aksesuar_fiyat_spin.setToolTip("Kol, mentese, ispanyolet seti")
 fiyat_layout.addRow("Aksesuar Set:", self.aksesuar_fiyat_spin)

 self.sineklik_fiyat_spin = QDoubleSpinBox()
 self.sineklik_fiyat_spin.setRange(50, 1000)
 self.sineklik_fiyat_spin.setValue(VARSAYILAN_FIYATLAR['sineklik_birim_fiyat'])
 self.sineklik_fiyat_spin.setSuffix(" TL/adet")
 fiyat_layout.addRow("Sineklik:", self.sineklik_fiyat_spin)

 self.montaj_fiyat_spin = QDoubleSpinBox()
 self.montaj_fiyat_spin.setRange(100, 2000)
 self.montaj_fiyat_spin.setValue(VARSAYILAN_FIYATLAR['iscilik_montaj_bedeli'])
 self.montaj_fiyat_spin.setSuffix(" TL/adet")
 fiyat_layout.addRow("Montaj:", self.montaj_fiyat_spin)

 sol_layout.addWidget(fiyat_group)

 # Hesapla butonu
 self.btn_hesapla = QPushButton("HESAPLA")
 self.btn_hesapla.setFont(QFont("Arial", 12, QFont.Weight.Bold))
 self.btn_hesapla.setMinimumHeight(50)
 self.btn_hesapla.setStyleSheet("""
 QPushButton {
 background-color: #2196F3;
 color: white;
 border-radius: 5px;
 }
 QPushButton:hover {
 background-color: #1976D2;
 }
 """)
 self.btn_hesapla.clicked.connect(self.hesapla)
 sol_layout.addWidget(self.btn_hesapla)

 sol_layout.addStretch()
 splitter.addWidget(sol_widget)

 # ======================
 # SAG PANEL - SONUCLAR
 # ======================
 sag_widget = QWidget()
 sag_layout = QVBoxLayout(sag_widget)

 self.tab_widget = QTabWidget()

 # Tab 1: Ozet Rapor
 ozet_tab = QWidget()
 ozet_layout = QVBoxLayout(ozet_tab)
 self.ozet_text = QTextEdit()
 self.ozet_text.setReadOnly(True)
 self.ozet_text.setFont(QFont("Consolas", 10))
 self.ozet_text.setPlaceholderText("Hesaplama sonuclari burada gorunecek...")
 ozet_layout.addWidget(self.ozet_text)
 self.tab_widget.addTab(ozet_tab, "Ozet Rapor")

 # Tab 2: Dograma Detay
 detay_tab = QWidget()
 detay_layout = QVBoxLayout(detay_tab)
 self.detay_table = QTableWidget()
 self.detay_table.setColumnCount(8)
 self.detay_table.setHorizontalHeaderLabels([
 "Aciklama", "Boyut", "Adet", "Tip", "Profil (mtul)", "Cam (m2)", "Aksesuar", "Montaj"
 ])
 self.detay_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
 detay_layout.addWidget(self.detay_table)
 self.tab_widget.addTab(detay_tab, "Dograma Detay")

 # Tab 3: Maliyet
 maliyet_tab = QWidget()
 maliyet_layout = QVBoxLayout(maliyet_tab)
 self.maliyet_text = QTextEdit()
 self.maliyet_text.setReadOnly(True)
 self.maliyet_text.setFont(QFont("Consolas", 11))
 maliyet_layout.addWidget(self.maliyet_text)
 self.tab_widget.addTab(maliyet_tab, "Maliyet")

 sag_layout.addWidget(self.tab_widget)

 # Export butonlari
 export_layout = QHBoxLayout()

 btn_excel = QPushButton("Excel'e Aktar")
 btn_excel.clicked.connect(self.export_excel)
 export_layout.addWidget(btn_excel)

 btn_metraj = QPushButton("Metraja Ekle")
 btn_metraj.clicked.connect(self.metraja_ekle)
 btn_metraj.setStyleSheet("background-color: #4CAF50; color: white;")
 export_layout.addWidget(btn_metraj)

 sag_layout.addLayout(export_layout)

 splitter.addWidget(sag_widget)
 splitter.setSizes([450, 750])

 main_layout.addWidget(splitter)

 # Alt butonlar
 bottom_layout = QHBoxLayout()
 bottom_layout.addStretch()
 btn_kapat = QPushButton("Kapat")
 btn_kapat.clicked.connect(self.close)
 bottom_layout.addWidget(btn_kapat)
 main_layout.addLayout(bottom_layout)

 def dograma_ekle(self):
 """Yeni dograma ekle"""
 dialog = DogramaEklemeDialog(self)
 if dialog.exec():
 data = dialog.get_data()
 self.dogramalar.append(data)
 self.dograma_tablosunu_guncelle()

 def dograma_duzenle(self):
 """Secili dogramayi duzenle"""
 row = self.dograma_table.currentRow()
 if row < 0 or row >= len(self.dogramalar):
 QMessageBox.warning(self, "Uyari", "Lutfen duzenlenecek dogramayi secin!")
 return

 dialog = DogramaEklemeDialog(self, self.dogramalar[row])
 if dialog.exec():
 self.dogramalar[row] = dialog.get_data()
 self.dograma_tablosunu_guncelle()

 def dograma_sil(self):
 """Secili dogramayi sil"""
 row = self.dograma_table.currentRow()
 if row < 0 or row >= len(self.dogramalar):
 QMessageBox.warning(self, "Uyari", "Lutfen silinecek dogramayi secin!")
 return

 reply = QMessageBox.question(
 self, "Onay",
 f"'{self.dogramalar[row]['aciklama']}' dogramasini silmek istiyor musunuz?",
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
 )

 if reply == QMessageBox.StandardButton.Yes:
 del self.dogramalar[row]
 self.dograma_tablosunu_guncelle()

 def dograma_tablosunu_guncelle(self):
 """Dograma tablosunu guncelle"""
 self.dograma_table.setRowCount(len(self.dogramalar))

 toplam_adet = 0
 for row, d in enumerate(self.dogramalar):
 toplam_adet += d['adet']

 self.dograma_table.setItem(row, 0, QTableWidgetItem(d['aciklama']))
 self.dograma_table.setItem(row, 1, QTableWidgetItem(f"{d['en_cm']:.0f}"))
 self.dograma_table.setItem(row, 2, QTableWidgetItem(f"{d['boy_cm']:.0f}"))
 self.dograma_table.setItem(row, 3, QTableWidgetItem(str(d['adet'])))
 self.dograma_table.setItem(row, 4, QTableWidgetItem(get_tip_aciklama(d['tip'])))
 self.dograma_table.setItem(row, 5, QTableWidgetItem("" if d.get('cift_acilim_aksesuar') else ""))
 self.dograma_table.setItem(row, 6, QTableWidgetItem("" if d.get('sineklik_var_mi') else ""))

 self.dograma_ozet_label.setText(f"Toplam: {len(self.dogramalar)} kalem, {toplam_adet} adet dograma")

 def hesapla(self):
 """Hesaplamayi calistir"""
 if not self.dogramalar:
 QMessageBox.warning(self, "Uyari", "En az bir dograma eklemelisiniz!")
 return

 try:
 sonuc = hesapla_pvc_dograma_detayli(
 dograma_listesi=self.dogramalar,
 profil_rengi=self.profil_rengi_combo.currentText(),
 cam_tipi=self.cam_tipi_combo.currentText(),
 profil_mtul_fiyat=self.profil_fiyat_spin.value(),
 cam_m2_fiyat=self.cam_fiyat_spin.value(),
 aksesuar_set_fiyat=self.aksesuar_fiyat_spin.value(),
 sineklik_birim_fiyat=self.sineklik_fiyat_spin.value(),
 iscilik_montaj_bedeli=self.montaj_fiyat_spin.value()
 )

 self.son_hesaplama = sonuc
 self.sonuclari_goster(sonuc)
 self.hesaplama_tamamlandi.emit(sonuc)

 except Exception as e:
 QMessageBox.critical(self, "Hata", f"Hesaplama hatasi:\n{str(e)}")

 def sonuclari_goster(self, sonuc: Dict):
 """Hesaplama sonuclarini goster"""

 # 1. Ozet Rapor
 self.ozet_text.setPlainText(rapor_olustur(sonuc))

 # 2. Detay Tablosu
 dd = sonuc['dograma_detay']
 self.detay_table.setRowCount(len(dd))
 for row, d in enumerate(dd):
 self.detay_table.setItem(row, 0, QTableWidgetItem(d['aciklama']))
 self.detay_table.setItem(row, 1, QTableWidgetItem(f"{d['en_cm']:.0f}x{d['boy_cm']:.0f}"))
 self.detay_table.setItem(row, 2, QTableWidgetItem(str(d['adet'])))
 self.detay_table.setItem(row, 3, QTableWidgetItem(d['tip_aciklama']))
 self.detay_table.setItem(row, 4, QTableWidgetItem(f"{d['profil_mtul']:.2f}"))
 self.detay_table.setItem(row, 5, QTableWidgetItem(f"{d['net_cam_m2']:.3f}"))
 self.detay_table.setItem(row, 6, QTableWidgetItem(f"{d['birim_aksesuar_tl']:.0f} TL"))
 self.detay_table.setItem(row, 7, QTableWidgetItem(f"{d['birim_montaj_tl']:.0f} TL"))

 # 3. Maliyet
 maliyet_text = []
 maliyet_text.append("MALIYET DETAYI")
 maliyet_text.append("=" * 50)
 maliyet_text.append("")
 maliyet_text.append(f"Profil: {sonuc['profil_rengi']}")
 maliyet_text.append(f"Cam: {sonuc['cam_tipi']}")
 maliyet_text.append("")
 maliyet_text.append("MIKTAR OZETI:")
 maliyet_text.append(f" Toplam Pencere : {sonuc['toplam_pencere_adet']} adet")
 maliyet_text.append(f" Toplam Kapi : {sonuc['toplam_kapi_adet']} adet")
 maliyet_text.append(f" Profil Metraji : {sonuc['hesaplanan_toplam_profil_mtul']:.2f} mtul")
 maliyet_text.append(f" Net Cam Alani : {sonuc['hesaplanan_net_cam_m2']:.2f} m2")
 maliyet_text.append(f" Sineklik : {sonuc['gereken_sineklik_adet']} adet")
 maliyet_text.append("")
 maliyet_text.append("-" * 50)
 maliyet_text.append("MALIYET:")
 m = sonuc['maliyet_detayi']
 maliyet_text.append(f" Profil : {sonuc['hesaplanan_toplam_profil_mtul']:.2f} mtul x {format_para(sonuc['parametreler']['profil_mtul_fiyat'])}")
 maliyet_text.append(f" = {format_para(m['profil_tl'])}")
 maliyet_text.append(f" Cam : {sonuc['hesaplanan_net_cam_m2']:.2f} m2 x {format_para(sonuc['parametreler']['cam_m2_fiyat'])}")
 maliyet_text.append(f" = {format_para(m['cam_tl'])}")
 maliyet_text.append(f" Aksesuar : {format_para(m['aksesuar_tl'])}")
 maliyet_text.append(f" Sineklik : {sonuc['gereken_sineklik_adet']} x {format_para(sonuc['parametreler']['sineklik_birim_fiyat'])}")
 maliyet_text.append(f" = {format_para(m['sineklik_tl'])}")
 maliyet_text.append(f" Montaj : {sonuc['toplam_dograma_adet']} x {format_para(sonuc['parametreler']['iscilik_montaj_bedeli'])}")
 maliyet_text.append(f" = {format_para(m['montaj_tl'])}")
 maliyet_text.append("")
 maliyet_text.append("=" * 50)
 maliyet_text.append(f" GENEL TOPLAM : {format_para(sonuc['genel_toplam_maliyet_tl'])}")
 maliyet_text.append("")
 maliyet_text.append(f" Tahmini Sure : {sonuc['tahmini_sure_gun']} is gunu")

 self.maliyet_text.setPlainText("\n".join(maliyet_text))

 # Ozet tab'a gec
 self.tab_widget.setCurrentIndex(0)

 def export_excel(self):
 """Excel'e aktar"""
 if not self.son_hesaplama:
 QMessageBox.warning(self, "Uyari", "Once hesaplama yapmalisiniz!")
 return

 try:
 from openpyxl import Workbook
 from openpyxl.styles import Font

 file_path, _ = QFileDialog.getSaveFileName(
 self, "Excel Kaydet", "pvc_dograma_raporu.xlsx",
 "Excel Dosyasi (*.xlsx)"
 )

 if not file_path:
 return

 wb = Workbook()
 ws = wb.active
 ws.title = "PVC Dograma"

 ws['A1'] = "PVC DOGRAMA HESAPLAMA RAPORU"
 ws['A1'].font = Font(bold=True, size=14)
 ws.merge_cells('A1:E1')

 sonuc = self.son_hesaplama
 row = 3

 ws[f'A{row}'] = f"Profil: {sonuc['profil_rengi']}, Cam: {sonuc['cam_tipi']}"
 row += 2

 ws[f'A{row}'] = "OZET"
 ws[f'A{row}'].font = Font(bold=True)
 row += 1

 ozet = [
 ("Toplam Dograma", f"{sonuc['toplam_dograma_adet']} adet"),
 ("Profil Metraji", f"{sonuc['hesaplanan_toplam_profil_mtul']:.2f} mtul"),
 ("Net Cam Alani", f"{sonuc['hesaplanan_net_cam_m2']:.2f} m2"),
 ("Sineklik", f"{sonuc['gereken_sineklik_adet']} adet"),
 ]

 for ad, deger in ozet:
 ws[f'A{row}'] = ad
 ws[f'B{row}'] = deger
 row += 1

 row += 1
 ws[f'A{row}'] = "MALIYET"
 ws[f'A{row}'].font = Font(bold=True)
 row += 1

 m = sonuc['maliyet_detayi']
 maliyet = [
 ("Profil", f"{m['profil_tl']:,.2f} TL"),
 ("Cam", f"{m['cam_tl']:,.2f} TL"),
 ("Aksesuar", f"{m['aksesuar_tl']:,.2f} TL"),
 ("Sineklik", f"{m['sineklik_tl']:,.2f} TL"),
 ("Montaj", f"{m['montaj_tl']:,.2f} TL"),
 ("GENEL TOPLAM", f"{sonuc['genel_toplam_maliyet_tl']:,.2f} TL"),
 ]

 for ad, deger in maliyet:
 ws[f'A{row}'] = ad
 ws[f'B{row}'] = deger
 if ad == "GENEL TOPLAM":
 ws[f'A{row}'].font = Font(bold=True)
 ws[f'B{row}'].font = Font(bold=True)
 row += 1

 ws.column_dimensions['A'].width = 20
 ws.column_dimensions['B'].width = 20

 wb.save(file_path)
 QMessageBox.information(self, "Basarili", f"Rapor kaydedildi:\n{file_path}")

 except ImportError:
 QMessageBox.warning(self, "Hata", "Excel export icin 'openpyxl' kutuphanesi gerekli!")
 except Exception as e:
 QMessageBox.critical(self, "Hata", f"Excel kaydetme hatasi:\n{str(e)}")

 def metraja_ekle(self):
 """Metraja ekle"""
 if not self.son_hesaplama:
 QMessageBox.warning(self, "Uyari", "Once hesaplama yapmalisiniz!")
 return

 self.hesaplama_tamamlandi.emit(self.son_hesaplama)
 QMessageBox.information(
 self, "Basarili",
 f"PVC dograma metraja eklendi:\n"
 f"Dograma: {self.son_hesaplama['toplam_dograma_adet']} adet\n"
 f"Toplam: {format_para(self.son_hesaplama['genel_toplam_maliyet_tl'])}"
 )


# Test
if __name__ == "__main__":
 import sys
 from PyQt6.QtWidgets import QApplication

 app = QApplication(sys.argv)
 app.setStyle("Fusion")

 dialog = PVCDogramaHesaplamaDialog()
 dialog.show()

 sys.exit(app.exec())
