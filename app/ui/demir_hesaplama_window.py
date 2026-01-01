"""
Demir Hesaplama Penceresi
DXF dosyasından demir hesaplamalarını yapan arayüz
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QComboBox, QSpinBox,
    QDoubleSpinBox, QTableWidget, QTableWidgetItem, 
    QFileDialog, QMessageBox, QTabWidget, QGroupBox,
    QFormLayout, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from pathlib import Path
import logging

from app.core.dxf_demir_analyzer import DXFDemirAnalyzer
from app.core.demir_engine import TemelTipi

logger = logging.getLogger(__name__)


class DemirHesaplamaWindow(QMainWindow):
    """Demir hesaplama penceresi"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dxf_dosya = None
        self.analyzer = None
        self.hesaplama_sonucu = None
        self.init_ui()
    
    def init_ui(self):
        """Arayüzü oluştur"""
        self.setWindowTitle("Yapısal Demir Hesaplama Sistemi")
        self.setGeometry(100, 100, 1200, 800)
        
        # Ana widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # Sol panel - Giriş
        left_panel = self._create_input_panel()
        main_layout.addWidget(left_panel, 1)
        
        # Sağ panel - Sonuçlar
        right_panel = self._create_results_panel()
        main_layout.addWidget(right_panel, 2)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }
            QLabel {
                color: #e0e0e0;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #00BFFF;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #00BFFF;
                color: #1a1a2e;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00CCFF;
            }
            QGroupBox {
                color: #e0e0e0;
                border: 2px solid #00BFFF;
                border-radius: 5px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTableWidget {
                background-color: #16213e;
                gridline-color: #00BFFF;
                color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #0f3460;
                color: #e0e0e0;
                padding: 5px;
                border: none;
            }
            QTextEdit {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #00BFFF;
            }
        """)
    
    def _create_input_panel(self) -> QGroupBox:
        """Giriş panelini oluştur"""
        panel = QGroupBox("DXF Dosyası & Yapı Parametreleri")
        layout = QVBoxLayout()
        
        # Dosya seçme
        file_layout = QHBoxLayout()
        self.file_label = QLabel("Dosya seçilmedi")
        file_layout.addWidget(QLabel("DXF Dosyası:"))
        file_layout.addWidget(self.file_label, 1)
        btn_dosya = QPushButton("Dosya Seç")
        btn_dosya.clicked.connect(self.dosya_sec)
        file_layout.addWidget(btn_dosya)
        layout.addLayout(file_layout)
        
        # Temel tipi
        temel_layout = QHBoxLayout()
        temel_layout.addWidget(QLabel("Temel Tipi:"))
        self.combo_temel = QComboBox()
        self.combo_temel.addItems([t.value for t in TemelTipi])
        temel_layout.addWidget(self.combo_temel)
        temel_layout.addStretch()
        layout.addLayout(temel_layout)
        
        # Demir parametreleri
        params_group = QGroupBox("Demir Parametreleri")
        params_layout = QFormLayout()
        
        self.spin_demir_capi = QSpinBox()
        self.spin_demir_capi.setValue(12)
        self.spin_demir_capi.setSuffix(" mm")
        params_layout.addRow("Demir Çapı:", self.spin_demir_capi)
        
        self.spin_aralık = QDoubleSpinBox()
        self.spin_aralık.setValue(15.0)
        self.spin_aralık.setSuffix(" cm")
        params_layout.addRow("Demir Aralığı:", self.spin_aralık)
        
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)
        
        # Ölçüler
        olcum_group = QGroupBox("Yapı Ölçüleri (cm)")
        olcum_layout = QFormLayout()
        
        self.spin_uzunluk = QDoubleSpinBox()
        self.spin_uzunluk.setValue(500)
        olcum_layout.addRow("Uzunluk:", self.spin_uzunluk)
        
        self.spin_eni = QDoubleSpinBox()
        self.spin_eni.setValue(300)
        olcum_layout.addRow("Eni:", self.spin_eni)
        
        self.spin_yukseklik = QDoubleSpinBox()
        self.spin_yukseklik.setValue(50)
        olcum_layout.addRow("Yükseklik:", self.spin_yukseklik)
        
        olcum_group.setLayout(olcum_layout)
        layout.addWidget(olcum_group)
        
        # Hesapla butonu
        btn_hesapla = QPushButton("DXF'den Demir Hesapla")
        btn_hesapla.setFixedHeight(40)
        btn_hesapla.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn_hesapla.clicked.connect(self.demiri_hesapla)
        layout.addWidget(btn_hesapla)
        
        layout.addStretch()
        panel.setLayout(layout)
        return panel
    
    def _create_results_panel(self) -> QWidget:
        """Sonuç panelini oluştur"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Sekme
        tabs = QTabWidget()
        
        # Tablo sekmesi
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Eleman Tipi", "Adı", "Uzunluk (cm)", "Eni (cm)",
            "Demir Ø (mm)", "Demir Adet", "Toplam Uzunluk (cm)", "Ağırlık (kg)"
        ])
        self.table.resizeColumnsToContents()
        tabs.addTab(self.table, "Detaylı Hesaplama")
        
        # Rapor sekmesi
        self.text_rapor = QTextEdit()
        self.text_rapor.setReadOnly(True)
        tabs.addTab(self.text_rapor, "Rapor")
        
        layout.addWidget(tabs)
        
        # Özet
        ozet_group = QGroupBox("Hesaplama Özeti")
        ozet_layout = QFormLayout()
        
        self.label_toplam_agirlik = QLabel("0 kg")
        self.label_toplam_agirlik.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.label_toplam_agirlik.setStyleSheet("color: #00FF00;")
        ozet_layout.addRow("Toplam Demir Ağırlığı:", self.label_toplam_agirlik)
        
        self.label_toplam_uzunluk = QLabel("0 cm")
        self.label_toplam_uzunluk.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.label_toplam_uzunluk.setStyleSheet("color: #00FF00;")
        ozet_layout.addRow("Toplam Demir Uzunluğu:", self.label_toplam_uzunluk)
        
        ozet_group.setLayout(ozet_layout)
        layout.addWidget(ozet_group)
        
        return widget
    
    def dosya_sec(self):
        """DXF dosyası seç"""
        dosya, _ = QFileDialog.getOpenFileName(
            self, "DXF Dosyası Seç", "",
            "DXF Dosyaları (*.dxf);;Tüm Dosyalar (*)"
        )
        
        if dosya:
            self.dxf_dosya = dosya
            self.file_label.setText(Path(dosya).name)
    
    def demiri_hesapla(self):
        """DXF'den demir hesaplamalarını yap"""
        if not self.dxf_dosya:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce DXF dosyası seçin!")
            return
        
        try:
            # Analyzer'ı oluştur
            self.analyzer = DXFDemirAnalyzer(self.dxf_dosya)
            
            # Hesaplamaları yap
            self.hesaplama_sonucu = self.analyzer.demiri_hesapla()
            
            # Tabloyu güncelle
            self._tablo_guncelle()
            
            # Raporu güncelle
            rapor = self.analyzer.rapor_olustur()
            self.text_rapor.setText(rapor)
            
            # Özeti güncelle
            ozet = self.hesaplama_sonucu['ozet']
            self.label_toplam_agirlik.setText(f"{ozet['toplam_agirlik_kg']} kg")
            self.label_toplam_uzunluk.setText(f"{ozet['toplam_uzunluk_cm']} cm")
            
            QMessageBox.information(self, "Başarılı", "Demir hesaplamaları tamamlandı!")
            
        except Exception as e:
            logger.error(f"Hesaplama hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Hesaplama sırasında hata:\n{str(e)}")
    
    def _tablo_guncelle(self):
        """Sonuç tablosunu güncelle"""
        self.table.setRowCount(0)
        
        for eleman_tipi, veri in self.hesaplama_sonucu.items():
            if eleman_tipi != 'ozet':
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                self.table.setItem(row, 0, QTableWidgetItem(veri['eleman_tipi']))
                self.table.setItem(row, 1, QTableWidgetItem(veri['eleman_adi']))
                self.table.setItem(row, 2, QTableWidgetItem(f"{veri['uzunluk']:.2f}"))
                self.table.setItem(row, 3, QTableWidgetItem(f"{veri['eni']:.2f}"))
                self.table.setItem(row, 4, QTableWidgetItem(f"Ø{veri['demir_capi']}"))
                self.table.setItem(row, 5, QTableWidgetItem(str(veri['demir_sayisi'])))
                self.table.setItem(row, 6, QTableWidgetItem(f"{veri['toplam_uzunluk']:.2f}"))
                self.table.setItem(row, 7, QTableWidgetItem(f"{veri['toplam_agirlik']:.2f}"))
        
        self.table.resizeColumnsToContents()
