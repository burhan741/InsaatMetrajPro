"""
Çevre ve Sürdürülebilirlik Modülü UI
Karbon ayak izi, enerji verimliliği, atık yönetimi ve yeşil sertifika arayüzü
"""

from PyQt6.QtWidgets import (
QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
QLineEdit, QComboBox, QDateEdit, QTextEdit, QMessageBox,
QHeaderView, QDoubleSpinBox, QTabWidget, QProgressBar,
QSpinBox, QCheckBox, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QColor, QFont
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

from app.core.database import DatabaseManager
from app.core.surdurulebilirlik_engine import SurdurulebilirlikEngine

logger = logging.getLogger(__name__)


class SurdurulebilirlikWindow(QWidget):
 """Sürdürülebilirlik ve çevre yönetimi widget'i"""

 def __init__(self, db: DatabaseManager):
  super().__init__()
  self.db = db
  self.engine = SurdurulebilirlikEngine(db)
  self.current_project_id: Optional[int] = None
  self.init_ui()
  self.load_projeler()

 def init_ui(self):
  """UI elementlerini oluştur"""
  layout = QVBoxLayout()

  # Başlık
  baslik = QLabel(" Çevre ve Sürdürülebilirlik Modülü")
  baslik.setStyleSheet("font-size: 20pt; font-weight: bold; margin: 10px; color: #27ae60;")
  layout.addWidget(baslik)

  # Proje seçimi
  proje_layout = QHBoxLayout()
  proje_label = QLabel("Proje:")
  proje_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
  self.proje_combo = QComboBox()
  self.proje_combo.currentIndexChanged.connect(self.on_proje_changed)
  proje_layout.addWidget(proje_label)
  proje_layout.addWidget(self.proje_combo)
  proje_layout.addStretch()

  # Yenile butonu
  yenile_btn = QPushButton("Yenile")
  yenile_btn.setStyleSheet(self._get_button_style("#1a5276"))
  yenile_btn.clicked.connect(self.yenile_dashboard)
  proje_layout.addWidget(yenile_btn)

  layout.addLayout(proje_layout)

  # Sekmeler
  self.tab_widget = QTabWidget()
  self.tab_widget.setStyleSheet("""
  QTabWidget::pane {
  border: 1px solid #ccc;
  border-radius: 5px;
  background-color: white;
  }
  QTabBar::tab {
  background-color: #ecf0f1;
  padding: 10px 20px;
  margin-right: 2px;
  border-top-left-radius: 5px;
  border-top-right-radius: 5px;
  }
  QTabBar::tab:selected {
  background-color: #27ae60;
  color: white;
  font-weight: bold;
  }
  """)

  # Sekmeler oluştur
  self.tab_widget.addTab(self._create_ozet_tab(), "Özet Dashboard")
  self.tab_widget.addTab(self._create_karbon_tab(), "Karbon Ayak İzi")
  self.tab_widget.addTab(self._create_enerji_tab(), "Enerji Verimliliği")
  self.tab_widget.addTab(self._create_atik_tab(), "Atık Yönetimi")
  self.tab_widget.addTab(self._create_leed_tab(), "LEED/BREEAM Sertifika")

  layout.addWidget(self.tab_widget)
  self.setLayout(layout)

  def _create_ozet_tab(self) -> QWidget:
  """Özet dashboard sekmesi"""
  widget = QWidget()
  layout = QVBoxLayout()

  # KPI Kartları
  kpi_layout = QHBoxLayout()

  # Karbon Ayak İzi Kartı
  self.karbon_kart = self._create_kpi_card(
  "Karbon Ayak İzi",
  "0 ton CO₂",
  "#e74c3c",
  "Hesaplanıyor..."
  )
  kpi_layout.addWidget(self.karbon_kart)

  # Enerji Sınıfı Kartı
  self.enerji_kart = self._create_kpi_card(
  " Enerji Sınıfı",
  "N/A",
  "#f39c12",
  "Henüz hesaplanmadı"
  )
  kpi_layout.addWidget(self.enerji_kart)

  # Geri Dönüşüm Kartı
  self.geri_donusum_kart = self._create_kpi_card(
  " Geri Dönüşüm",
  "0%",
  "#27ae60",
  "Atık kaydı yok"
  )
  kpi_layout.addWidget(self.geri_donusum_kart)

  # LEED Puanı Kartı
  self.leed_kart = self._create_kpi_card(
  " LEED Puanı",
  "0/110",
  "#3498db",
  "Sertifika Alamaz"
  )
  kpi_layout.addWidget(self.leed_kart)

  layout.addLayout(kpi_layout)

  # Grafik ve detay alanı
  detay_group = QGroupBox(" Detaylı Analiz")
  detay_layout = QVBoxLayout()

  # Karbon dağılımı tablosu
  self.karbon_dagilim_table = QTableWidget()
  self.karbon_dagilim_table.setColumnCount(3)
  self.karbon_dagilim_table.setHorizontalHeaderLabels([
  "Kategori", "Karbon (kg CO₂)", "Oran (%)"
  ])
  self.karbon_dagilim_table.horizontalHeader().setStretchLastSection(True)
  self.karbon_dagilim_table.setMaximumHeight(200)
  detay_layout.addWidget(QLabel("Karbon Ayak İzi Dağılımı:"))
  detay_layout.addWidget(self.karbon_dagilim_table)

  # Öneriler alanı
  self.oneriler_text = QTextEdit()
  self.oneriler_text.setReadOnly(True)
  self.oneriler_text.setMaximumHeight(150)
  self.oneriler_text.setStyleSheet("""
  QTextEdit {
  background-color: #e8f5e9;
  border: 2px solid #27ae60;
  border-radius: 5px;
  padding: 10px;
  font-size: 11pt;
  }
  """)
  detay_layout.addWidget(QLabel(" Sürdürülebilirlik Önerileri:"))
  detay_layout.addWidget(self.oneriler_text)

  detay_group.setLayout(detay_layout)
  layout.addWidget(detay_group)

  layout.addStretch()
  widget.setLayout(layout)
  return widget

  def _create_karbon_tab(self) -> QWidget:
  """Karbon ayak izi sekmesi"""
  widget = QWidget()
  layout = QVBoxLayout()

  # Hesaplama formu
  form_group = QGroupBox("Karbon Ayak İzi Hesaplama")
  form_layout = QFormLayout()

  # Malzeme seçimi
  self.karbon_malzeme_combo = QComboBox()
  self.karbon_malzeme_combo.addItems([
  "Beton", "Çimento", "Çelik", "Demir", "Alüminyum",
  "Cam", "Tuğla", "Ahşap", "Yalıtım (Taş Yünü)",
  "Yalıtım (EPS)", "PVC", "Asfalt", "Kireç", "Mermer",
  "Seramik", "Boya"
  ])
  form_layout.addRow("Malzeme:", self.karbon_malzeme_combo)

  # Miktar
  self.karbon_miktar_input = QDoubleSpinBox()
  self.karbon_miktar_input.setRange(0, 999999)
  self.karbon_miktar_input.setDecimals(2)
  self.karbon_miktar_input.setValue(1.0)
  form_layout.addRow("Miktar:", self.karbon_miktar_input)

  # Birim
  self.karbon_birim_combo = QComboBox()
  self.karbon_birim_combo.addItems(["ton", "kg", "m³", "m²"])
  form_layout.addRow("Birim:", self.karbon_birim_combo)

  # Hesapla butonu
  hesapla_btn = QPushButton("Karbon Ayak İzi Hesapla")
  hesapla_btn.setStyleSheet(self._get_button_style("#27ae60"))
  hesapla_btn.clicked.connect(self.hesapla_karbon)
  form_layout.addRow("", hesapla_btn)

  # Proje geneli hesapla
  proje_hesapla_btn = QPushButton("Tüm Proje Karbon Hesapla")
  proje_hesapla_btn.setStyleSheet(self._get_button_style("#784212"))
  proje_hesapla_btn.clicked.connect(self.hesapla_proje_karbon)
  form_layout.addRow("", proje_hesapla_btn)

  form_group.setLayout(form_layout)
  layout.addWidget(form_group)

  # Sonuç alanı
  sonuc_group = QGroupBox(" Hesaplama Sonuçları")
  sonuc_layout = QVBoxLayout()

  self.karbon_sonuc_text = QTextEdit()
  self.karbon_sonuc_text.setReadOnly(True)
  self.karbon_sonuc_text.setMaximumHeight(250)
  self.karbon_sonuc_text.setStyleSheet("""
  QTextEdit {
  background-color: #1e1e2e;
  color: #e0e0e0;
  border: 1px solid #3a3a4a;
  border-radius: 5px;
  padding: 10px;
  font-size: 11pt;
  font-family: 'Consolas', monospace;
  }
  """)
  sonuc_layout.addWidget(self.karbon_sonuc_text)

  sonuc_group.setLayout(sonuc_layout)
  layout.addWidget(sonuc_group)

  # En yüksek emisyonlu kalemler
  en_yuksek_group = QGroupBox(" En Yüksek Karbon Emisyonlu Kalemler")
  en_yuksek_layout = QVBoxLayout()

  self.en_yuksek_table = QTableWidget()
  self.en_yuksek_table.setColumnCount(4)
  self.en_yuksek_table.setHorizontalHeaderLabels([
  "Poz No", "Tanım", "Miktar", "Karbon (kg CO₂)"
  ])
  self.en_yuksek_table.horizontalHeader().setStretchLastSection(True)
  en_yuksek_layout.addWidget(self.en_yuksek_table)

  en_yuksek_group.setLayout(en_yuksek_layout)
  layout.addWidget(en_yuksek_group)

  layout.addStretch()
  widget.setLayout(layout)
  return widget

  def _create_enerji_tab(self) -> QWidget:
  """Enerji verimliliği sekmesi"""
  widget = QWidget()
  layout = QVBoxLayout()

  # Form
  form_group = QGroupBox("Enerji Verimliliği Hesaplama")
  form_layout = QFormLayout()

  # Yıllık tüketim
  self.enerji_tuketim_input = QDoubleSpinBox()
  self.enerji_tuketim_input.setRange(0, 9999999)
  self.enerji_tuketim_input.setDecimals(2)
  self.enerji_tuketim_input.setSuffix(" kWh/yıl")
  self.enerji_tuketim_input.setValue(50000)
  form_layout.addRow("Yıllık Enerji Tüketimi:", self.enerji_tuketim_input)

  # Toplam alan
  self.enerji_alan_input = QDoubleSpinBox()
  self.enerji_alan_input.setRange(0, 999999)
  self.enerji_alan_input.setDecimals(2)
  self.enerji_alan_input.setSuffix(" m²")
  self.enerji_alan_input.setValue(500)
  form_layout.addRow("Toplam Bina Alanı:", self.enerji_alan_input)

  # Hesapla butonu
  hesapla_btn = QPushButton("Enerji Sınıfı Hesapla")
  hesapla_btn.setStyleSheet(self._get_button_style("#7d6608"))
  hesapla_btn.clicked.connect(self.hesapla_enerji)
  form_layout.addRow("", hesapla_btn)

  form_group.setLayout(form_layout)
  layout.addWidget(form_group)

  # Sonuç kartı
  sonuc_group = QGroupBox(" Enerji Verimliliği Sonuçları")
  sonuc_layout = QVBoxLayout()

  # Enerji sınıfı göstergesi
  self.enerji_sinif_label = QLabel("Enerji Sınıfı: N/A")
  self.enerji_sinif_label.setStyleSheet("font-size: 24pt; font-weight: bold; color: #f39c12;")
  self.enerji_sinif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
  sonuc_layout.addWidget(self.enerji_sinif_label)

  # Progress bar
  self.enerji_progress = QProgressBar()
  self.enerji_progress.setRange(0, 100)
  self.enerji_progress.setValue(0)
  self.enerji_progress.setTextVisible(True)
  self.enerji_progress.setFormat("Puan: %v / 100")
  self.enerji_progress.setStyleSheet("""
  QProgressBar {
  border: 2px solid #ccc;
  border-radius: 5px;
  text-align: center;
  height: 30px;
  font-size: 12pt;
  font-weight: bold;
  }
  QProgressBar::chunk {
  background-color: qlineargradient(
  x1:0, y1:0, x2:1, y2:0,
  stop:0 #f39c12, stop:1 #e67e22
  );
  }
  """)
  sonuc_layout.addWidget(self.enerji_progress)

  # Detay bilgileri
  self.enerji_detay_text = QTextEdit()
  self.enerji_detay_text.setReadOnly(True)
  self.enerji_detay_text.setMaximumHeight(200)
  self.enerji_detay_text.setStyleSheet("""
  QTextEdit {
  background-color: #fff3e0;
  border: 2px solid #f39c12;
  border-radius: 5px;
  padding: 10px;
  font-size: 11pt;
  }
  """)
  sonuc_layout.addWidget(self.enerji_detay_text)

  # Kaydet butonu
  kaydet_btn = QPushButton("Enerji Verilerini Kaydet")
  kaydet_btn.setStyleSheet(self._get_button_style("#154360"))
  kaydet_btn.clicked.connect(self.kaydet_enerji)
  sonuc_layout.addWidget(kaydet_btn)

  sonuc_group.setLayout(sonuc_layout)
  layout.addWidget(sonuc_group)

  layout.addStretch()
  widget.setLayout(layout)
  return widget

  def _create_atik_tab(self) -> QWidget:
  """Atık yönetimi sekmesi"""
  widget = QWidget()
  layout = QVBoxLayout()

  # Atık kaydı formu
  form_group = QGroupBox(" Yeni Atık Kaydı")
  form_layout = QFormLayout()

  # Atık türü
  self.atik_tur_combo = QComboBox()
  self.atik_tur_combo.addItems([
  "beton_moloz", "ahsap", "metal", "plastik",
  "cam", "yalitim", "boya_kimyasal", "asbest", "karisik"
  ])
  form_layout.addRow("Atık Türü:", self.atik_tur_combo)

  # Miktar
  self.atik_miktar_input = QDoubleSpinBox()
  self.atik_miktar_input.setRange(0, 999999)
  self.atik_miktar_input.setDecimals(2)
  self.atik_miktar_input.setSuffix(" ton")
  form_layout.addRow("Miktar:", self.atik_miktar_input)

  # Geri dönüştürüldü mü?
  self.atik_geri_donusum_check = QCheckBox("Geri dönüştürüldü")
  form_layout.addRow("", self.atik_geri_donusum_check)

  # Açıklama
  self.atik_aciklama_input = QLineEdit()
  self.atik_aciklama_input.setPlaceholderText("Opsiyonel açıklama...")
  form_layout.addRow("Açıklama:", self.atik_aciklama_input)

  # Kaydet butonu
  kaydet_btn = QPushButton("Atık Kaydı Oluştur")
  kaydet_btn.setStyleSheet(self._get_button_style("#27ae60"))
  kaydet_btn.clicked.connect(self.kaydet_atik)
  form_layout.addRow("", kaydet_btn)

  form_group.setLayout(form_layout)
  layout.addWidget(form_group)

  # Atık özeti
  ozet_group = QGroupBox(" Atık Yönetimi Özeti")
  ozet_layout = QVBoxLayout()

  # Özet kartlar
  ozet_kart_layout = QHBoxLayout()

  self.toplam_atik_label = QLabel("Toplam Atık\n0 ton")
  self.toplam_atik_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
  self.toplam_atik_label.setStyleSheet("""
  QLabel {
  background-color: #e74c3c;
  color: white;
  padding: 20px;
  border-radius: 10px;
  font-size: 14pt;
  font-weight: bold;
  }
  """)
  ozet_kart_layout.addWidget(self.toplam_atik_label)

  self.geri_donusum_label = QLabel("Geri Dönüşüm\n0%")
  self.geri_donusum_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
  self.geri_donusum_label.setStyleSheet("""
  QLabel {
  background-color: #27ae60;
  color: white;
  padding: 20px;
  border-radius: 10px;
  font-size: 14pt;
  font-weight: bold;
  }
  """)
  ozet_kart_layout.addWidget(self.geri_donusum_label)

  self.atik_durum_label = QLabel("Durum\nN/A")
  self.atik_durum_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
  self.atik_durum_label.setStyleSheet("""
  QLabel {
  background-color: #95a5a6;
  color: white;
  padding: 20px;
  border-radius: 10px;
  font-size: 14pt;
  font-weight: bold;
  }
  """)
  ozet_kart_layout.addWidget(self.atik_durum_label)

  ozet_layout.addLayout(ozet_kart_layout)

  # Atık detay tablosu
  self.atik_table = QTableWidget()
  self.atik_table.setColumnCount(4)
  self.atik_table.setHorizontalHeaderLabels([
  "Atık Türü", "Miktar (ton)", "Geri Dönüşüm", "Tarih"
  ])
  self.atik_table.horizontalHeader().setStretchLastSection(True)
  ozet_layout.addWidget(self.atik_table)

  ozet_group.setLayout(ozet_layout)
  layout.addWidget(ozet_group)

  layout.addStretch()
  widget.setLayout(layout)
  return widget

  def _create_leed_tab(self) -> QWidget:
  """LEED/BREEAM sertifika sekmesi"""
  widget = QWidget()
  layout = QVBoxLayout()

  # Açıklama
  aciklama = QLabel("""
  <b>LEED (Leadership in Energy and Environmental Design)</b> yeşil bina sertifikasıdır.
  <br>Toplam 110 puan üzerinden değerlendirme yapılır:
  <br>• <b>Platinum:</b> 80+ puan
  <br>• <b>Gold:</b> 60-79 puan
  <br>• <b>Silver:</b> 50-59 puan
  <br>• <b>Certified:</b> 40-49 puan
  """)
  aciklama.setWordWrap(True)
  aciklama.setStyleSheet("""
  QLabel {
  background-color: #ecf0f1;
  padding: 15px;
  border-radius: 5px;
  font-size: 10pt;
  }
  """)
  layout.addWidget(aciklama)

  # Puan girişi
  form_group = QGroupBox(" LEED Puan Girişi")
  form_layout = QFormLayout()

  # Kategori puanları
  self.leed_enerji_input = QSpinBox()
  self.leed_enerji_input.setRange(0, 33)
  self.leed_enerji_input.setSuffix(" / 33")
  form_layout.addRow("Enerji Tasarrufu:", self.leed_enerji_input)

  self.leed_su_input = QSpinBox()
  self.leed_su_input.setRange(0, 12)
  self.leed_su_input.setSuffix(" / 12")
  form_layout.addRow("Su Verimliliği:", self.leed_su_input)

  self.leed_malzeme_input = QSpinBox()
  self.leed_malzeme_input.setRange(0, 13)
  self.leed_malzeme_input.setSuffix(" / 13")
  form_layout.addRow("Malzeme ve Kaynak:", self.leed_malzeme_input)

  self.leed_ic_mekan_input = QSpinBox()
  self.leed_ic_mekan_input.setRange(0, 16)
  self.leed_ic_mekan_input.setSuffix(" / 16")
  form_layout.addRow("İç Mekan Kalitesi:", self.leed_ic_mekan_input)

  self.leed_yenilikcilik_input = QSpinBox()
  self.leed_yenilikcilik_input.setRange(0, 6)
  self.leed_yenilikcilik_input.setSuffix(" / 6")
  form_layout.addRow("Yenilikçilik:", self.leed_yenilikcilik_input)

  # Hesapla butonu
  hesapla_btn = QPushButton("LEED Puanı Hesapla")
  hesapla_btn.setStyleSheet(self._get_button_style("#3498db"))
  hesapla_btn.clicked.connect(self.hesapla_leed)
  form_layout.addRow("", hesapla_btn)

  form_group.setLayout(form_layout)
  layout.addWidget(form_group)

  # Sonuç alanı
  sonuc_group = QGroupBox(" LEED Sertifika Sonucu")
  sonuc_layout = QVBoxLayout()

  # Sertifika seviyesi
  self.leed_seviye_label = QLabel("Sertifika Seviyesi: N/A")
  self.leed_seviye_label.setStyleSheet("font-size: 20pt; font-weight: bold;")
  self.leed_seviye_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
  sonuc_layout.addWidget(self.leed_seviye_label)

  # Progress bar
  self.leed_progress = QProgressBar()
  self.leed_progress.setRange(0, 110)
  self.leed_progress.setValue(0)
  self.leed_progress.setTextVisible(True)
  self.leed_progress.setFormat("Toplam Puan: %v / 110 (%p%)")
  self.leed_progress.setStyleSheet("""
  QProgressBar {
  border: 2px solid #ccc;
  border-radius: 5px;
  text-align: center;
  height: 30px;
  font-size: 12pt;
  font-weight: bold;
  }
  QProgressBar::chunk {
  background-color: #3498db;
  }
  """)
  sonuc_layout.addWidget(self.leed_progress)

  # Kategori detayı
  self.leed_kategori_table = QTableWidget()
  self.leed_kategori_table.setColumnCount(3)
  self.leed_kategori_table.setHorizontalHeaderLabels([
  "Kategori", "Puan", "Maksimum"
  ])
  self.leed_kategori_table.horizontalHeader().setStretchLastSection(True)
  self.leed_kategori_table.setMaximumHeight(200)
  sonuc_layout.addWidget(self.leed_kategori_table)

  # Öneriler
  self.leed_oneriler_text = QTextEdit()
  self.leed_oneriler_text.setReadOnly(True)
  self.leed_oneriler_text.setMaximumHeight(150)
  self.leed_oneriler_text.setStyleSheet("""
  QTextEdit {
  background-color: #e8f4f8;
  border: 2px solid #3498db;
  border-radius: 5px;
  padding: 10px;
  font-size: 11pt;
  }
  """)
  sonuc_layout.addWidget(QLabel(" Sertifika Önerileri:"))
  sonuc_layout.addWidget(self.leed_oneriler_text)

  sonuc_group.setLayout(sonuc_layout)
  layout.addWidget(sonuc_group)

  layout.addStretch()
  widget.setLayout(layout)
  return widget

  # Yardımcı metodlar

  def _create_kpi_card(self, baslik: str, deger: str, renk: str, alt_metin: str) -> QFrame:
  """KPI kartı oluştur"""
  card = QFrame()
  card.setFrameShape(QFrame.Shape.StyledPanel)
  card.setStyleSheet(f"""
  QFrame {{
  background-color: {renk};
  border-radius: 10px;
  padding: 15px;
  }}
  """)

  layout = QVBoxLayout()

  # Başlık
  baslik_label = QLabel(baslik)
  baslik_label.setStyleSheet("color: white; font-size: 12pt; font-weight: bold;")
  baslik_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
  layout.addWidget(baslik_label)

  # Değer
  deger_label = QLabel(deger)
  deger_label.setObjectName("deger_label") # Güncellemek için
  deger_label.setStyleSheet("color: white; font-size: 24pt; font-weight: bold;")
  deger_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
  layout.addWidget(deger_label)

  # Alt metin
  alt_label = QLabel(alt_metin)
  alt_label.setObjectName("alt_label")
  alt_label.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 9pt;")
  alt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
  layout.addWidget(alt_label)

  card.setLayout(layout)
  return card

  def _get_button_style(self, color: str) -> str:
  """Buton stili — koyu arka plan, beyaz yazı, yüksek kontrast."""
  return f"""
  QPushButton {{
  background-color: {color};
  color: #ffffff;
  padding: 8px 18px;
  font-size: 11pt;
  font-weight: bold;
  border-radius: 5px;
  border: none;
  }}
  QPushButton:hover {{
  background-color: {color};
  border: 2px solid #aaaaaa;
  }}
  QPushButton:pressed {{
  background-color: {color};
  border: 2px solid #ffffff;
  }}
  """

  # Veri yükleme metodları

  def load_projeler(self):
  """Projeleri yükle"""
  try:
  with self.db.get_connection() as conn:
  cursor = conn.cursor()
  cursor.execute("SELECT id, ad FROM projects ORDER BY id DESC")
  projeler = cursor.fetchall()

  self.proje_combo.clear()
  for proje in projeler:
  self.proje_combo.addItem(proje['ad'], proje['id'])

  except Exception as e:
  logger.error(f"Proje yükleme hatası: {e}")
  QMessageBox.warning(self, "Hata", f"Projeler yüklenemedi: {e}")

  def on_proje_changed(self, index: int):
  """Proje değiştiğinde"""
  if index >= 0:
  self.current_project_id = self.proje_combo.itemData(index)
  self.yenile_dashboard()

  def yenile_dashboard(self):
  """Dashboard'u yenile"""
  if not self.current_project_id:
  return

  # Karbon ayak izi hesapla
  karbon_sonuc = self.engine.hesapla_proje_karbon_ayakizi(self.current_project_id)
  if 'error' not in karbon_sonuc:
  # Karbon kartını güncelle
  deger_label = self.karbon_kart.findChild(QLabel, "deger_label")
  alt_label = self.karbon_kart.findChild(QLabel, "alt_label")
  if deger_label and alt_label:
  deger_label.setText(f"{karbon_sonuc['toplam_karbon_ton']} ton CO₂")
  alt_label.setText(f" {karbon_sonuc['agac_esdegeri']} ağaç eşdeğeri")

  # Karbon dağılımı tablosunu doldur
  self.karbon_dagilim_table.setRowCount(0)
  toplam_karbon = karbon_sonuc['toplam_karbon_kg']
  for kategori, miktar in karbon_sonuc['kategori_dagilim'].items():
  row = self.karbon_dagilim_table.rowCount()
  self.karbon_dagilim_table.insertRow(row)
  self.karbon_dagilim_table.setItem(row, 0, QTableWidgetItem(kategori))
  self.karbon_dagilim_table.setItem(row, 1, QTableWidgetItem(f"{miktar:.2f}"))
  oran = (miktar / toplam_karbon * 100) if toplam_karbon > 0 else 0
  self.karbon_dagilim_table.setItem(row, 2, QTableWidgetItem(f"{oran:.1f}%"))

  # Atık özetini güncelle
  atik_ozet = self.engine.get_proje_atik_ozeti(self.current_project_id)
  if 'error' not in atik_ozet:
  deger_label = self.geri_donusum_kart.findChild(QLabel, "deger_label")
  alt_label = self.geri_donusum_kart.findChild(QLabel, "alt_label")
  if deger_label and alt_label:
  deger_label.setText(f"{atik_ozet['geri_donusum_orani']:.1f}%")
  alt_label.setText(f"{atik_ozet['durum']}")

  # Öneriler oluştur
  self._guncelle_oneriler()

  def _guncelle_oneriler(self):
  """Sürdürülebilirlik önerileri güncelle"""
  oneriler = [
  " Daha düşük karbonlu malzemeler tercih edin (ahşap, geri dönüştürülmüş)",
  " LED aydınlatma kullanarak enerji tüketimini %30 azaltabilirsiniz",
  " İnşaat atıklarının en az %70'ini geri dönüştürmeyi hedefleyin",
  " Yağmur suyu toplama sistemi ile su tüketimini azaltın",
  " Güneş panelleri ile yenilenebilir enerji kullanımını artırın"
  ]

  self.oneriler_text.setHtml("<br>".join(oneriler))

  # Hesaplama metodları

  def hesapla_karbon(self):
  """Tekil malzeme karbon hesaplama"""
  malzeme = self.karbon_malzeme_combo.currentText()
  miktar = self.karbon_miktar_input.value()
  birim = self.karbon_birim_combo.currentText()

  sonuc = self.engine.hesapla_karbon_ayakizi(malzeme, miktar, birim)

  # Sonucu göster
  metin = f"""
  ╔══════════════════════════════════════════════════════╗
  ║ KARBON AYAK İZİ HESAPLAMA SONUCU ║
  ╚══════════════════════════════════════════════════════╝

  Malzeme : {sonuc['malzeme']}
  Miktar : {sonuc['miktar']} {sonuc['birim']}
  Karbon Faktörü : {sonuc['karbon_faktor']} kg CO₂/birim

  SONUÇLAR:
  ├─ Karbon Emisyonu : {sonuc['karbon_emisyon_kg']:,.2f} kg CO₂
  ├─ Ton Cinsinden : {sonuc['karbon_emisyon_ton']:,.3f} ton CO₂
  └─ Ağaç Eşdeğeri : {sonuc['agac_esdegeri']:,.1f} ağaç/yıl

  {' Karbon pozitif (emisyon var)' if sonuc['karbon_pozitif'] else ' Karbon negatif (karbon tutucu)'}

  Not: 1 ağaç yılda yaklaşık 20 kg CO₂ emer.
  """

  self.karbon_sonuc_text.setPlainText(metin)

  def hesapla_proje_karbon(self):
  """Tüm proje karbon hesaplama"""
  if not self.current_project_id:
  QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
  return

  sonuc = self.engine.hesapla_proje_karbon_ayakizi(self.current_project_id)

  if 'error' in sonuc:
  QMessageBox.critical(self, "Hata", sonuc['error'])
  return

  # Sonucu göster
  metin = f"""
  ╔══════════════════════════════════════════════════════╗
  ║ PROJE KARBON AYAK İZİ ANALİZİ ║
  ╚══════════════════════════════════════════════════════╝

  Proje ID : {sonuc['proje_id']}
  Toplam Kalem : {sonuc['toplam_kalem']}
  Hesaplama Tarihi: {sonuc['tarih']}

  TOPLAM KARBON EMİSYONU:
  ├─ {sonuc['toplam_karbon_kg']:,.2f} kg CO₂
  ├─ {sonuc['toplam_karbon_ton']:,.3f} ton CO₂
  └─ {sonuc['agac_esdegeri']:,.1f} ağaç/yıl eşdeğeri

  EN YÜKSEK EMİSYONLU 5 KALEM:
  """

  for i, kalem in enumerate(sonuc['en_yuksek_10'][:5], 1):
  metin += f"{i}. {kalem['poz_no']} - {kalem['tanim']}: {kalem['karbon_kg']:,.2f} kg CO₂\n"

  self.karbon_sonuc_text.setPlainText(metin)

  # Tabloyu doldur
  self.en_yuksek_table.setRowCount(0)
  for kalem in sonuc['en_yuksek_10']:
  row = self.en_yuksek_table.rowCount()
  self.en_yuksek_table.insertRow(row)
  self.en_yuksek_table.setItem(row, 0, QTableWidgetItem(kalem['poz_no'] or ''))
  self.en_yuksek_table.setItem(row, 1, QTableWidgetItem(kalem['tanim'] or ''))
  self.en_yuksek_table.setItem(row, 2, QTableWidgetItem(f"{kalem['miktar']} {kalem['birim']}"))
  self.en_yuksek_table.setItem(row, 3, QTableWidgetItem(f"{kalem['karbon_kg']:,.2f}"))

  # Dashboard'u güncelle
  self.yenile_dashboard()

  def hesapla_enerji(self):
  """Enerji verimliliği hesaplama"""
  tuketim = self.enerji_tuketim_input.value()
  alan = self.enerji_alan_input.value()

  if alan <= 0:
  QMessageBox.warning(self, "Uyarı", "Bina alanı 0'dan büyük olmalıdır")
  return

  sonuc = self.engine.hesapla_enerji_sinifi(tuketim, alan)

  if 'error' in sonuc:
  QMessageBox.critical(self, "Hata", sonuc['error'])
  return

  # Sınıfı göster
  self.enerji_sinif_label.setText(f"Enerji Sınıfı: {sonuc['enerji_sinifi']}")

  # Renk ayarla
  renk_map = {
  'A+': '#27ae60', 'A': '#2ecc71', 'B': '#f39c12',
  'C': '#e67e22', 'D': '#e74c3c', 'E': '#c0392b',
  'F': '#8e44ad', 'G': '#7f8c8d'
  }
  renk = renk_map.get(sonuc['enerji_sinifi'], '#95a5a6')
  self.enerji_sinif_label.setStyleSheet(f"font-size: 24pt; font-weight: bold; color: {renk};")

  # Progress bar
  self.enerji_progress.setValue(int(sonuc['puan']))

  # Detay göster
  detay = f"""
  <b>Birim Tüketim:</b> {sonuc['birim_tuketim_kwh_m2']:.2f} kWh/m²/yıl<br>
  <b>Yıllık Tüketim:</b> {sonuc['yillik_tuketim_kwh']:,.0f} kWh<br>
  <b>Toplam Alan:</b> {sonuc['toplam_alan_m2']:,.0f} m²<br>
  <b>Yıllık Maliyet:</b> {sonuc['yillik_maliyet_tl']:,.2f} TL<br>
  <b>CO₂ Emisyonu:</b> {sonuc['co2_emisyon_ton']:.3f} ton CO₂/yıl<br>
  <br>
  <b>Puan:</b> {sonuc['puan']:.1f} / 100
  """
  self.enerji_detay_text.setHtml(detay)

  # Enerji kartını güncelle
  deger_label = self.enerji_kart.findChild(QLabel, "deger_label")
  alt_label = self.enerji_kart.findChild(QLabel, "alt_label")
  if deger_label and alt_label:
  deger_label.setText(sonuc['enerji_sinifi'])
  alt_label.setText(f"Puan: {sonuc['puan']:.1f}/100")

  def kaydet_enerji(self):
  """Enerji verilerini kaydet"""
  if not self.current_project_id:
  QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
  return

  tuketim = self.enerji_tuketim_input.value()
  alan = self.enerji_alan_input.value()

  try:
  with self.db.get_connection() as conn:
  cursor = conn.cursor()
  cursor.execute("""
  INSERT INTO enerji_verileri (
  proje_id, yillik_tuketim_kwh, toplam_alan_m2, tarih
  ) VALUES (?, ?, ?, ?)
  """, (
  self.current_project_id,
  tuketim,
  alan,
  datetime.now().strftime('%Y-%m-%d')
  ))
  conn.commit()

  QMessageBox.information(self, "Başarılı", "Enerji verileri kaydedildi")

  except Exception as e:
  logger.error(f"Enerji kayıt hatası: {e}")
  QMessageBox.critical(self, "Hata", f"Kayıt başarısız: {e}")

  def kaydet_atik(self):
  """Atık kaydı oluştur"""
  if not self.current_project_id:
  QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
  return

  atik_turu = self.atik_tur_combo.currentText()
  miktar = self.atik_miktar_input.value()
  geri_donusum = self.atik_geri_donusum_check.isChecked()
  aciklama = self.atik_aciklama_input.text()

  if miktar <= 0:
  QMessageBox.warning(self, "Uyarı", "Miktar 0'dan büyük olmalıdır")
  return

  sonuc = self.engine.kaydet_atik_kaydi(
  self.current_project_id,
  atik_turu,
  miktar,
  geri_donusum,
  aciklama
  )

  if sonuc['success']:
  QMessageBox.information(self, "Başarılı", "Atık kaydı oluşturuldu")
  self.atik_miktar_input.setValue(0)
  self.atik_aciklama_input.clear()
  self.atik_geri_donusum_check.setChecked(False)
  self.yukle_atik_listesi()
  self.yenile_dashboard()
  else:
  QMessageBox.critical(self, "Hata", sonuc['error'])

  def yukle_atik_listesi(self):
  """Atık listesini yükle"""
  if not self.current_project_id:
  return

  atik_ozet = self.engine.get_proje_atik_ozeti(self.current_project_id)

  if 'error' in atik_ozet:
  return

  # Özet kartları güncelle
  self.toplam_atik_label.setText(f"Toplam Atık\n{atik_ozet['toplam_atik_ton']:.2f} ton")
  self.geri_donusum_label.setText(f"Geri Dönüşüm\n{atik_ozet['geri_donusum_orani']:.1f}%")
  self.atik_durum_label.setText(f"Durum\n{atik_ozet['durum']}")

  # Durum rengini ayarla
  durum_renk = {
  'Mükemmel': '#27ae60',
  'İyi': '#2ecc71',
  'Orta': '#f39c12',
  'Düşük': '#e74c3c'
  }
  renk = durum_renk.get(atik_ozet['durum'], '#95a5a6')
  self.atik_durum_label.setStyleSheet(f"""
  QLabel {{
  background-color: {renk};
  color: white;
  padding: 20px;
  border-radius: 10px;
  font-size: 14pt;
  font-weight: bold;
  }}
  """)

  # Tabloyu doldur
  self.atik_table.setRowCount(0)
  try:
  with self.db.get_connection() as conn:
  cursor = conn.cursor()
  cursor.execute("""
  SELECT atik_turu, miktar_ton, geri_donusturuldu, tarih
  FROM atik_yonetimi
  WHERE proje_id = ?
  ORDER BY tarih DESC
  """, (self.current_project_id,))

  atiklar = cursor.fetchall()
  for atik in atiklar:
  row = self.atik_table.rowCount()
  self.atik_table.insertRow(row)
  self.atik_table.setItem(row, 0, QTableWidgetItem(atik['atik_turu']))
  self.atik_table.setItem(row, 1, QTableWidgetItem(f"{atik['miktar_ton']:.2f}"))
  self.atik_table.setItem(row, 2, QTableWidgetItem(" Evet" if atik['geri_donusturuldu'] else " Hayır"))
  self.atik_table.setItem(row, 3, QTableWidgetItem(atik['tarih']))

  except Exception as e:
  logger.error(f"Atık listesi yükleme hatası: {e}")

  def hesapla_leed(self):
  """LEED puanı hesapla"""
  enerji = self.leed_enerji_input.value()
  su = self.leed_su_input.value()
  malzeme = self.leed_malzeme_input.value()
  ic_mekan = self.leed_ic_mekan_input.value()
  yenilikcilik = self.leed_yenilikcilik_input.value()

  sonuc = self.engine.hesapla_leed_puani(enerji, su, malzeme, ic_mekan, yenilikcilik)

  # Seviye göster
  self.leed_seviye_label.setText(f" {sonuc['seviye']}")
  self.leed_seviye_label.setStyleSheet(f"""
  font-size: 24pt;
  font-weight: bold;
  color: {sonuc['renk']};
  """)

  # Progress bar
  self.leed_progress.setValue(int(sonuc['toplam_puan']))

  # Kategori tablosu
  self.leed_kategori_table.setRowCount(0)
  for kategori, veri in sonuc['detay'].items():
  row = self.leed_kategori_table.rowCount()
  self.leed_kategori_table.insertRow(row)
  self.leed_kategori_table.setItem(row, 0, QTableWidgetItem(kategori.capitalize()))
  self.leed_kategori_table.setItem(row, 1, QTableWidgetItem(str(veri['puan'])))
  self.leed_kategori_table.setItem(row, 2, QTableWidgetItem(str(veri['max'])))

  # Öneriler
  oneriler_html = "<ul>"
  for oneri in sonuc['oneriler']:
  oneriler_html += f"<li>{oneri}</li>"
  oneriler_html += "</ul>"
  self.leed_oneriler_text.setHtml(oneriler_html)

  # LEED kartını güncelle
  deger_label = self.leed_kart.findChild(QLabel, "deger_label")
  alt_label = self.leed_kart.findChild(QLabel, "alt_label")
  if deger_label and alt_label:
  deger_label.setText(f"{sonuc['toplam_puan']}/110")
  alt_label.setText(sonuc['seviye'])
