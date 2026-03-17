"""
Saha Demiri Hesaplama Penceresi
Kolonlar, kirişler ve döşeme için demir hacmi ve ağırlık hesaplama
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDoubleSpinBox, QSpinBox,
    QGroupBox, QFormLayout, QMessageBox, QFrame,
    QGridLayout, QScrollArea, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import logging

logger = logging.getLogger(__name__)


class SahaDemiriWindow(QMainWindow):
    """Saha demiri (kolon, kiriş, döşeme) hesaplama penceresi"""

    hesaplama_tamamlandi = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.son_hesaplama = None
        self.init_ui()

    def init_ui(self):
        """Arayüzü oluştur"""
        self.setWindowTitle("Saha Demiri Hesaplama")
        self.setGeometry(100, 100, 1000, 800)

        # Ana widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Başlık
        title = QLabel("Saha Demiri Hesaplama")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        # Sol panel - Girişler
        input_group = QGroupBox("Giriş Parametreleri")
        input_layout = QFormLayout()

        # Kolon demiri girişleri
        kolon_label = QLabel("Kolonlar")
        kolon_label_font = QFont()
        kolon_label_font.setBold(True)
        kolon_label.setFont(kolon_label_font)
        input_layout.addRow(kolon_label)

        self.kolon_sayisi = QSpinBox()
        self.kolon_sayisi.setMinimum(0)
        self.kolon_sayisi.setMaximum(1000)
        self.kolon_sayisi.setValue(0)
        input_layout.addRow("Kolon Sayısı:", self.kolon_sayisi)

        self.kolon_yukseklik = QDoubleSpinBox()
        self.kolon_yukseklik.setMinimum(0)
        self.kolon_yukseklik.setMaximum(100)
        self.kolon_yukseklik.setValue(0)
        self.kolon_yukseklik.setSuffix(" m")
        input_layout.addRow("Kat Yüksekliği:", self.kolon_yukseklik)

        self.kolon_boyut_b = QDoubleSpinBox()
        self.kolon_boyut_b.setMinimum(0)
        self.kolon_boyut_b.setMaximum(10)
        self.kolon_boyut_b.setValue(0.30)
        self.kolon_boyut_b.setSuffix(" m")
        input_layout.addRow("Kolon Genişliği (b):", self.kolon_boyut_b)

        self.kolon_boyut_h = QDoubleSpinBox()
        self.kolon_boyut_h.setMinimum(0)
        self.kolon_boyut_h.setMaximum(10)
        self.kolon_boyut_h.setValue(0.30)
        self.kolon_boyut_h.setSuffix(" m")
        input_layout.addRow("Kolon Yüksekliği (h):", self.kolon_boyut_h)

        self.kolon_dogal_oyer_sayi = QSpinBox()
        self.kolon_dogal_oyer_sayi.setMinimum(0)
        self.kolon_dogal_oyer_sayi.setMaximum(20)
        self.kolon_dogal_oyer_sayi.setValue(4)
        input_layout.addRow("Kolon Doğal Çoğaltı (adet):", self.kolon_dogal_oyer_sayi)

        # Kiriş demiri girişleri
        kiris_label = QLabel("Kirişler")
        kiris_label.setFont(kolon_label_font)
        input_layout.addRow(kiris_label)

        self.kiris_uzunluk = QDoubleSpinBox()
        self.kiris_uzunluk.setMinimum(0)
        self.kiris_uzunluk.setMaximum(1000)
        self.kiris_uzunluk.setValue(0)
        self.kiris_uzunluk.setSuffix(" m")
        input_layout.addRow("Kiriş Toplam Uzunluğu:", self.kiris_uzunluk)

        self.kiris_boyut_b = QDoubleSpinBox()
        self.kiris_boyut_b.setMinimum(0)
        self.kiris_boyut_b.setMaximum(10)
        self.kiris_boyut_b.setValue(0.25)
        self.kiris_boyut_b.setSuffix(" m")
        input_layout.addRow("Kiriş Genişliği (b):", self.kiris_boyut_b)

        self.kiris_boyut_h = QDoubleSpinBox()
        self.kiris_boyut_h.setMinimum(0)
        self.kiris_boyut_h.setMaximum(10)
        self.kiris_boyut_h.setValue(0.50)
        self.kiris_boyut_h.setSuffix(" m")
        input_layout.addRow("Kiriş Yüksekliği (h):", self.kiris_boyut_h)

        # Döşeme demiri girişleri
        doseme_label = QLabel("Döşeme")
        doseme_label.setFont(kolon_label_font)
        input_layout.addRow(doseme_label)

        self.doseme_alani = QDoubleSpinBox()
        self.doseme_alani.setMinimum(0)
        self.doseme_alani.setMaximum(10000)
        self.doseme_alani.setValue(0)
        self.doseme_alani.setSuffix(" m²")
        input_layout.addRow("Döşeme Alanı:", self.doseme_alani)

        self.doseme_oyer_sayi = QSpinBox()
        self.doseme_oyer_sayi.setMinimum(0)
        self.doseme_oyer_sayi.setMaximum(100)
        self.doseme_oyer_sayi.setValue(8)
        input_layout.addRow("Döşeme Demir Sayısı (m²'de):", self.doseme_oyer_sayi)

        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        # Tablo - Sonuçlar
        results_group = QGroupBox("Hesaplama Sonuçları")
        results_layout = QVBoxLayout()

        self.results_table = QTableWidget()
        self.results_table.setRowCount(3)
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Eleman", "Hacim (m³)", "Ağırlık (kg)"])

        # Kolon satırı
        self.results_table.setItem(0, 0, QTableWidgetItem("Kolonlar"))
        self.results_table.setItem(0, 1, QTableWidgetItem("0.00"))
        self.results_table.setItem(0, 2, QTableWidgetItem("0.00"))

        # Kiriş satırı
        self.results_table.setItem(1, 0, QTableWidgetItem("Kirişler"))
        self.results_table.setItem(1, 1, QTableWidgetItem("0.00"))
        self.results_table.setItem(1, 2, QTableWidgetItem("0.00"))

        # Döşeme satırı
        self.results_table.setItem(2, 0, QTableWidgetItem("Döşeme"))
        self.results_table.setItem(2, 1, QTableWidgetItem("0.00"))
        self.results_table.setItem(2, 2, QTableWidgetItem("0.00"))

        self.results_table.resizeColumnsToContents()
        results_layout.addWidget(self.results_table)

        # Toplam satırı
        total_layout = QHBoxLayout()
        total_layout.addStretch()
        total_label = QLabel("TOPLAM:")
        total_label_font = QFont()
        total_label_font.setBold(True)
        total_label.setFont(total_label_font)
        total_layout.addWidget(total_label)

        self.total_hacim = QLabel("0.00 m³")
        self.total_hacim.setFont(total_label_font)
        total_layout.addWidget(self.total_hacim)

        self.total_agirlik = QLabel("0.00 kg")
        self.total_agirlik.setFont(total_label_font)
        total_layout.addWidget(self.total_agirlik)

        results_layout.addLayout(total_layout)
        results_group.setLayout(results_layout)
        main_layout.addWidget(results_group)

        # Butonlar
        button_layout = QHBoxLayout()

        self.calculate_btn = QPushButton("Hesapla")
        self.calculate_btn.clicked.connect(self.hesapla)
        button_layout.addWidget(self.calculate_btn)

        self.close_btn = QPushButton("Kapat")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        main_layout.addLayout(button_layout)
        main_layout.addStretch()

        self._apply_styles()

    def _apply_styles(self):
        """Stilleri uygula"""
        # Koyu tema için renkler
        style = """
        QGroupBox {
            font-weight: bold;
            border: 2px solid #444;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0px 5px;
        }
        QPushButton {
            background-color: #0d47a1;
            color: white;
            border: none;
            padding: 8px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1565c0;
        }
        """
        self.setStyleSheet(style)

    def hesapla(self):
        """Demiri hesapla"""
        try:
            try:
                # Kolon demiri
                kolon_sayisi = self.kolon_sayisi.value()
                kolon_yukseklik = self.kolon_yukseklik.value()
                kolon_b = self.kolon_boyut_b.value()
                kolon_h = self.kolon_boyut_h.value()
                kolon_dogal = self.kolon_dogal_oyer_sayi.value()

                kolon_hacim = kolon_sayisi * kolon_yukseklik * kolon_b * kolon_h
                kolon_agirlik = kolon_hacim * 7850 * (kolon_dogal / 100)  # 7850 kg/m³ çelik yoğunluğu

                # Kiriş demiri
                kiris_uzunluk = self.kiris_uzunluk.value()
                kiris_b = self.kiris_boyut_b.value()
                kiris_h = self.kiris_boyut_h.value()

                kiris_hacim = kiris_uzunluk * kiris_b * kiris_h
                kiris_agirlik = kiris_hacim * 7850 * 0.015  # %1.5 demir oranı

                # Döşeme demiri
                doseme_alani = self.doseme_alani.value()
                doseme_oyer_sayi = self.doseme_oyer_sayi.value()

                doseme_hacim = (doseme_alani * doseme_oyer_sayi * 0.01) * 0.05  # m³
                doseme_agirlik = doseme_hacim * 7850

                # Tabloyu güncelle
                self.results_table.setItem(0, 1, QTableWidgetItem(f"{kolon_hacim:.2f}"))
                self.results_table.setItem(0, 2, QTableWidgetItem(f"{kolon_agirlik:.0f}"))

                self.results_table.setItem(1, 1, QTableWidgetItem(f"{kiris_hacim:.2f}"))
                self.results_table.setItem(1, 2, QTableWidgetItem(f"{kiris_agirlik:.0f}"))

                self.results_table.setItem(2, 1, QTableWidgetItem(f"{doseme_hacim:.2f}"))
                self.results_table.setItem(2, 2, QTableWidgetItem(f"{doseme_agirlik:.0f}"))

                # Toplamları hesapla
                total_hacim = kolon_hacim + kiris_hacim + doseme_hacim
                total_agirlik = kolon_agirlik + kiris_agirlik + doseme_agirlik

                self.total_hacim.setText(f"{total_hacim:.2f} m³")
                self.total_agirlik.setText(f"{total_agirlik:.0f} kg")

                # Signal gönder
                result = {
                    'kolon_hacim': kolon_hacim,
                    'kolon_agirlik': kolon_agirlik,
                    'kiris_hacim': kiris_hacim,
                    'kiris_agirlik': kiris_agirlik,
                    'doseme_hacim': doseme_hacim,
                    'doseme_agirlik': doseme_agirlik,
                    'total_hacim': total_hacim,
                    'total_agirlik': total_agirlik
                }
                self.son_hesaplama = result
                self.hesaplama_tamamlandi.emit(result)
                logger.info("Saha demiri hesabı tamamlandı")
            except Exception as e:
                # Hesaplama hatası, dummy sonuç dön
                logger.warning(f"Saha demiri hesaplama hatası (dummy sonuç döndürülüyor): {str(e)}")
                QMessageBox.warning(self, "Uyarı", f"Hesaplama kısmi: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Beklenmeyen hata: {str(e)}")
            logger.error(f"Saha demiri beklenmeyen hata: {str(e)}")
