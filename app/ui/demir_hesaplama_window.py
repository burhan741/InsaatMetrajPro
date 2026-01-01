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
        
        # Sol panel - Sadece DXF Dosyası Seçimi
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
        """Giriş panelini oluştur - Sadece DXF Dosyası Seçimi"""
        panel = QGroupBox("DXF Dosyası Seç")
        layout = QVBoxLayout()
        
        # Dosya seçme
        file_layout = QHBoxLayout()
        self.file_label = QLabel("Dosya seçilmedi")
        self.file_label.setStyleSheet("color: #FFD700; font-weight: bold;")
        file_layout.addWidget(QLabel("DXF Dosyası:"))
        file_layout.addWidget(self.file_label, 1)
        btn_dosya = QPushButton("📁 Dosya Seç")
        btn_dosya.clicked.connect(self.dosya_sec)
        btn_dosya.setFixedHeight(40)
        file_layout.addWidget(btn_dosya)
        layout.addLayout(file_layout)
        
        layout.addSpacing(20)
        
        # Hesapla butonu
        btn_hesapla = QPushButton("⚡ DXF'den Demir Hesapla")
        btn_hesapla.setFixedHeight(50)
        btn_hesapla.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        btn_hesapla.setStyleSheet("""
            QPushButton {
                background-color: #00FF00;
                color: #000;
                border: 2px solid #00AA00;
            }
            QPushButton:hover {
                background-color: #00DD00;
            }
        """)
        btn_hesapla.clicked.connect(self.demiri_hesapla)
        layout.addWidget(btn_hesapla)
        
        layout.addStretch()
        panel.setLayout(layout)
        return panel
    
    def _create_input_panel_eski(self) -> QGroupBox:
        """Giriş panelini oluştur"""
    
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
            from app.core.temel_demir_analyzer import TemelDemirAnalyzer
            self.analyzer = TemelDemirAnalyzer(self.dxf_dosya)
            
            # Hesaplamaları yap
            self.hesaplama_sonucu = self.analyzer.demiri_hesapla()
            
            # Tabloyu güncelle
            self._tablo_guncelle()
            
            # Raporu güncelle
            rapor = self.analyzer.rapor_olustur()
            self.text_rapor.setText(rapor)
            
            # Özeti güncelle
            genel_ozet = self.hesaplama_sonucu['genel_ozet']
            self.label_toplam_agirlik.setText(f"{genel_ozet['toplam_agirlik_kg']} kg")
            self.label_toplam_uzunluk.setText(f"{genel_ozet['toplam_uzunluk_m']} m")
            
            QMessageBox.information(self, "✅ Başarılı", "Demir hesaplamaları tamamlandı!")
            
        except Exception as e:
            logger.error(f"Hesaplama hatası: {e}")
            QMessageBox.critical(self, "❌ Hata", f"Hesaplama sırasında hata:\n{str(e)}")
    
    def _tablo_guncelle(self):
        """Sonuç tablosunu güncelle"""
        self.table.setRowCount(0)
        
        tip_ozet = self.hesaplama_sonucu.get('tip_ozet', {})
        
        logger.info(f"Tablo güncelleniyor - Tip özet: {len(tip_ozet)} tip bulundu")
        
        if not tip_ozet:
            logger.warning("Tip özeti boş! Hesaplama sonucu: " + str(self.hesaplama_sonucu))
            return
        
        for tip, veri in tip_ozet.items():
            logger.info(f"Tablo: {tip} - {len(veri.get('detaylar', []))} detay")
            for detay in veri.get('detaylar', []):
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                self.table.setItem(row, 0, QTableWidgetItem(tip))
                self.table.setItem(row, 1, QTableWidgetItem(detay.get('adi', 'N/A')))
                self.table.setItem(row, 2, QTableWidgetItem(f"{detay.get('uzunluk', 0):.2f}"))
                self.table.setItem(row, 3, QTableWidgetItem(f"{detay.get('cap', 0):.2f}"))
                self.table.setItem(row, 4, QTableWidgetItem(f"Ø{detay.get('cap', 0)}"))
                self.table.setItem(row, 5, QTableWidgetItem(str(detay.get('adet', 0))))
                self.table.setItem(row, 6, QTableWidgetItem(f"{detay.get('toplam_uzunluk', 0):.2f}"))
                self.table.setItem(row, 7, QTableWidgetItem(f"{detay.get('agirlik', 0):.2f}"))
        
        self.table.resizeColumnsToContents()
        logger.info(f"Tablo güncelleme tamamlandı - {self.table.rowCount()} satır")
