"""
Proje Kimligi Penceresi
DXF dosyasından oda ve kat isimlerini okur ve görselleştirir
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QWidget, QSplitter, QFrame,
    QTabWidget, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont

from app.core.dxf_engine import DXFAnaliz

logger = logging.getLogger(__name__)


class ProjeGorselWidget(QWidget):
    """Proje kimligini 2D olarak gosteren widget (odalar ve katlar)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.oda_isimleri: List[Dict[str, Any]] = []
        self.kat_isimleri: List[Dict[str, Any]] = []
        self.hesap_siniri: Optional[tuple] = None  # (min_x, min_y, max_x, max_y)
        self.setMinimumSize(400, 400)
        self.setStyleSheet("background-color: #1e1e1e;")

        # Zoom ve Pan
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.last_mouse_pos = None
        self.dragging = False

        # Gorunum ayarlari
        self.oda_font_size = 10
        self.kat_font_size = 20
        self.show_odalar = True
        self.show_katlar = True

    def set_data(self, oda_isimleri: List[Dict[str, Any]], kat_isimleri: List[Dict[str, Any]] = None,
                 hesap_siniri: Optional[tuple] = None):
        """Veriyi ayarla"""
        self.oda_isimleri = oda_isimleri or []
        self.kat_isimleri = kat_isimleri or []
        self.hesap_siniri = hesap_siniri
        self.fit_to_view()
        self.update()

    def fit_to_view(self):
        """Tum veriler gorunecek sekilde zoom ayarla"""
        all_items = self.oda_isimleri + self.kat_isimleri
        if not all_items:
            return

        # Min/max koordinatlari bul
        x_coords = [item['x'] for item in all_items]
        y_coords = [item['y'] for item in all_items]

        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)

        # Margin ekle
        margin = 50
        data_width = max_x - min_x if max_x != min_x else 100
        data_height = max_y - min_y if max_y != min_y else 100

        # Scale hesapla
        scale_x = (self.width() - 2 * margin) / data_width if data_width > 0 else 1
        scale_y = (self.height() - 2 * margin) / data_height if data_height > 0 else 1
        self.scale = min(scale_x, scale_y) * 0.8

        # Merkeze al
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        self.offset_x = self.width() / 2 - center_x * self.scale
        self.offset_y = self.height() / 2 + center_y * self.scale  # Y ekseni ters

    def world_to_screen(self, x: float, y: float) -> tuple:
        """Dunya koordinatlarindan ekran koordinatlarina cevir"""
        screen_x = x * self.scale + self.offset_x
        screen_y = -y * self.scale + self.offset_y  # Y ekseni ters
        return int(screen_x), int(screen_y)

    def paintEvent(self, event):
        """Cizim eventi"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Arka plan
        painter.fillRect(self.rect(), QColor('#1e1e1e'))

        if not self.oda_isimleri and not self.kat_isimleri:
            # Bos mesaji
            painter.setPen(QPen(QColor('#888888')))
            painter.setFont(QFont('Segoe UI', 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "DXF dosyasi yukleyin")
            return

        # Hesap sinirini ciz
        if self.hesap_siniri:
            min_x, min_y, max_x, max_y = self.hesap_siniri
            p1 = self.world_to_screen(min_x, min_y)
            p2 = self.world_to_screen(max_x, max_y)

            pen = QPen(QColor('#e74c3c'))
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(p1[0], p2[1], p2[0] - p1[0], p1[1] - p2[1])

        # ODA isimlerini ciz (Sari kutu)
        if self.show_odalar:
            for oda in self.oda_isimleri:
                x, y = self.world_to_screen(oda['x'], oda['y'])
                text = oda['text']

                font = QFont('Segoe UI', self.oda_font_size, QFont.Weight.Bold)
                painter.setFont(font)
                metrics = painter.fontMetrics()
                text_width = metrics.horizontalAdvance(text)
                text_height = metrics.height()

                padding = 4
                rect_x = x - text_width // 2 - padding
                rect_y = y - text_height // 2 - padding
                rect_w = text_width + 2 * padding
                rect_h = text_height + 2 * padding

                # Sari kutu
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(241, 196, 15, 180)))  # #f1c40f with alpha
                painter.drawRoundedRect(rect_x, rect_y, rect_w, rect_h, 3, 3)

                # Yazi
                painter.setPen(QPen(QColor('#1e1e1e')))
                painter.drawText(rect_x + padding, rect_y + padding + metrics.ascent(), text)

        # KAT isimlerini ciz (Mavi kutu, BUYUK)
        if self.show_katlar:
            for kat in self.kat_isimleri:
                x, y = self.world_to_screen(kat['x'], kat['y'])
                text = kat['text']

                font = QFont('Segoe UI', self.kat_font_size, QFont.Weight.Bold)
                painter.setFont(font)
                metrics = painter.fontMetrics()
                text_width = metrics.horizontalAdvance(text)
                text_height = metrics.height()

                padding = 8
                rect_x = x - text_width // 2 - padding
                rect_y = y - text_height // 2 - padding
                rect_w = text_width + 2 * padding
                rect_h = text_height + 2 * padding

                # Mavi kutu
                painter.setPen(QPen(QColor('white'), 2))
                painter.setBrush(QBrush(QColor(0, 0, 255, 100)))  # blue with alpha
                painter.drawRoundedRect(rect_x, rect_y, rect_w, rect_h, 5, 5)

                # Yazi (cyan)
                painter.setPen(QPen(QColor('cyan')))
                painter.drawText(rect_x + padding, rect_y + padding + metrics.ascent(), text)

    def wheelEvent(self, event):
        """Mouse tekerlek ile zoom"""
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9

        mouse_x = event.position().x()
        mouse_y = event.position().y()

        world_x = (mouse_x - self.offset_x) / self.scale
        world_y = -(mouse_y - self.offset_y) / self.scale

        self.scale *= factor

        self.offset_x = mouse_x - world_x * self.scale
        self.offset_y = mouse_y + world_y * self.scale

        self.update()

    def mousePressEvent(self, event):
        """Mouse tiklamasi"""
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self.dragging = True
            self.last_mouse_pos = event.position()

    def mouseReleaseEvent(self, event):
        """Mouse birakma"""
        self.dragging = False
        self.last_mouse_pos = None

    def mouseMoveEvent(self, event):
        """Mouse hareketi"""
        if self.dragging and self.last_mouse_pos:
            delta_x = event.position().x() - self.last_mouse_pos.x()
            delta_y = event.position().y() - self.last_mouse_pos.y()
            self.offset_x += delta_x
            self.offset_y += delta_y
            self.last_mouse_pos = event.position()
            self.update()

    def resizeEvent(self, event):
        """Pencere boyutu degistiginde"""
        super().resizeEvent(event)
        self.fit_to_view()


class OdaIsimleriWindow(QDialog):
    """Proje Kimligi Penceresi (Oda ve Kat Isimleri)"""

    oda_secildi = pyqtSignal(dict)
    kat_secildi = pyqtSignal(dict)

    def __init__(self, parent=None, dxf_dosyasi: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Proje Kimligi - Oda ve Kat Isimleri")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        self.dxf_analiz: Optional[DXFAnaliz] = None
        self.oda_isimleri: List[Dict[str, Any]] = []
        self.kat_isimleri: List[Dict[str, Any]] = []
        self.dxf_dosyasi = dxf_dosyasi

        self.init_ui()

        if dxf_dosyasi:
            self.dosya_yukle(dxf_dosyasi)

    def init_ui(self):
        """Arayuzu olustur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Ust kontrol paneli
        kontrol_group = QGroupBox("Dosya ve Layer Secimi")
        kontrol_layout = QVBoxLayout(kontrol_group)

        # Ust satir - Dosya secimi
        dosya_layout = QHBoxLayout()
        self.dosya_btn = QPushButton("DXF Dosyasi Sec")
        self.dosya_btn.clicked.connect(self.dosya_sec)
        dosya_layout.addWidget(self.dosya_btn)

        self.dosya_label = QLabel("Dosya secilmedi")
        self.dosya_label.setStyleSheet("color: #888;")
        dosya_layout.addWidget(self.dosya_label, 1)
        kontrol_layout.addLayout(dosya_layout)

        # Alt satir - Layer secimleri
        layer_layout = QHBoxLayout()

        # Oda layer
        layer_layout.addWidget(QLabel("Oda Ismi Layer:"))
        self.oda_layer_combo = QComboBox()
        self.oda_layer_combo.setMinimumWidth(180)
        layer_layout.addWidget(self.oda_layer_combo)

        layer_layout.addSpacing(20)

        # Kat layer
        layer_layout.addWidget(QLabel("Kat Ismi Layer:"))
        self.kat_layer_combo = QComboBox()
        self.kat_layer_combo.setMinimumWidth(180)
        layer_layout.addWidget(self.kat_layer_combo)

        layer_layout.addStretch()

        # Tara butonu
        self.tara_btn = QPushButton("Proje Kimligini Tara")
        self.tara_btn.clicked.connect(self.proje_kimligini_tara)
        self.tara_btn.setEnabled(False)
        self.tara_btn.setStyleSheet("background-color: #27ae60; font-weight: bold;")
        layer_layout.addWidget(self.tara_btn)

        kontrol_layout.addLayout(layer_layout)
        layout.addWidget(kontrol_group)

        # Ana icerik - Splitter ile bol
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sol: Tablolar (Tab widget icinde)
        tablo_frame = QFrame()
        tablo_layout = QVBoxLayout(tablo_frame)
        tablo_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget()

        # Odalar tablosu
        oda_tab = QWidget()
        oda_tab_layout = QVBoxLayout(oda_tab)
        self.oda_tablosu = QTableWidget()
        self.oda_tablosu.setColumnCount(3)
        self.oda_tablosu.setHorizontalHeaderLabels(["Oda Ismi", "X", "Y"])
        self.oda_tablosu.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.oda_tablosu.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.oda_tablosu.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.oda_tablosu.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        oda_tab_layout.addWidget(self.oda_tablosu)
        self.tab_widget.addTab(oda_tab, "Odalar (0)")

        # Katlar tablosu
        kat_tab = QWidget()
        kat_tab_layout = QVBoxLayout(kat_tab)
        self.kat_tablosu = QTableWidget()
        self.kat_tablosu.setColumnCount(3)
        self.kat_tablosu.setHorizontalHeaderLabels(["Kat Ismi", "X", "Y"])
        self.kat_tablosu.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.kat_tablosu.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.kat_tablosu.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.kat_tablosu.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        kat_tab_layout.addWidget(self.kat_tablosu)
        self.tab_widget.addTab(kat_tab, "Katlar (0)")

        tablo_layout.addWidget(self.tab_widget)

        # Ozet label
        self.ozet_label = QLabel("Toplam: 0 oda, 0 kat")
        self.ozet_label.setStyleSheet("color: #888; padding: 5px; font-weight: bold;")
        tablo_layout.addWidget(self.ozet_label)

        splitter.addWidget(tablo_frame)

        # Sag: Gorsel
        gorsel_frame = QFrame()
        gorsel_layout = QVBoxLayout(gorsel_frame)
        gorsel_layout.setContentsMargins(0, 0, 0, 0)

        gorsel_baslik = QLabel("2D Gorunum (Mouse ile Zoom/Pan)")
        gorsel_baslik.setStyleSheet("font-weight: bold; font-size: 14px;")
        gorsel_layout.addWidget(gorsel_baslik)

        self.gorsel_widget = ProjeGorselWidget()
        gorsel_layout.addWidget(self.gorsel_widget)

        # Gorsel kontrolleri
        gorsel_kontrol = QHBoxLayout()

        from PyQt6.QtWidgets import QCheckBox
        self.show_oda_cb = QCheckBox("Odalari Goster")
        self.show_oda_cb.setChecked(True)
        self.show_oda_cb.stateChanged.connect(self.gorsel_ayarlarini_guncelle)
        gorsel_kontrol.addWidget(self.show_oda_cb)

        self.show_kat_cb = QCheckBox("Katlari Goster")
        self.show_kat_cb.setChecked(True)
        self.show_kat_cb.stateChanged.connect(self.gorsel_ayarlarini_guncelle)
        gorsel_kontrol.addWidget(self.show_kat_cb)

        gorsel_kontrol.addStretch()

        fit_btn = QPushButton("Tumu Goster")
        fit_btn.clicked.connect(lambda: (self.gorsel_widget.fit_to_view(), self.gorsel_widget.update()))
        gorsel_kontrol.addWidget(fit_btn)

        gorsel_layout.addLayout(gorsel_kontrol)

        splitter.addWidget(gorsel_frame)

        # Splitter oranlarini ayarla
        splitter.setSizes([400, 700])

        layout.addWidget(splitter, 1)

        # Alt butonlar
        buton_layout = QHBoxLayout()

        # Lejand
        lejand = QLabel("Lejand:  ")
        lejand.setStyleSheet("font-weight: bold;")
        buton_layout.addWidget(lejand)

        oda_lejand = QLabel("  Oda  ")
        oda_lejand.setStyleSheet("background-color: #f1c40f; color: #1e1e1e; padding: 3px 8px; border-radius: 3px; font-weight: bold;")
        buton_layout.addWidget(oda_lejand)

        kat_lejand = QLabel("  Kat  ")
        kat_lejand.setStyleSheet("background-color: blue; color: cyan; padding: 3px 8px; border-radius: 3px; font-weight: bold; border: 1px solid white;")
        buton_layout.addWidget(kat_lejand)

        buton_layout.addStretch()

        kapat_btn = QPushButton("Kapat")
        kapat_btn.clicked.connect(self.close)
        buton_layout.addWidget(kapat_btn)

        layout.addLayout(buton_layout)

    def dosya_sec(self):
        """DXF dosyasi sec"""
        dosya, _ = QFileDialog.getOpenFileName(
            self,
            "DXF Dosyasi Sec",
            "",
            "DXF Dosyalari (*.dxf);;Tum Dosyalar (*.*)"
        )

        if dosya:
            self.dosya_yukle(dosya)

    def dosya_yukle(self, dosya_yolu: str):
        """DXF dosyasini yukle"""
        try:
            self.dxf_analiz = DXFAnaliz(dosya_yolu, cizim_birimi="cm")
            self.dxf_dosyasi = dosya_yolu

            dosya_adi = Path(dosya_yolu).name
            self.dosya_label.setText(dosya_adi)
            self.dosya_label.setStyleSheet("color: #2ecc71; font-weight: bold;")

            # Text layer'larini listele
            text_layers = self.dxf_analiz.tum_text_layerlarini_listele()

            # Oda layer combo
            self.oda_layer_combo.clear()
            self.oda_layer_combo.addItems(text_layers)

            # Kat layer combo
            self.kat_layer_combo.clear()
            self.kat_layer_combo.addItems(text_layers)

            # Varsayilan layer'lari sec
            oda_varsayilan = ["A_ODA_ISMI", "ODA_ISMI", "ROOM_NAME", "ODA", "ROOMS"]
            kat_varsayilan = ["A_KAT_ISMI", "KAT_ISMI", "FLOOR_NAME", "KAT", "FLOORS"]

            for varsayilan in oda_varsayilan:
                if varsayilan in text_layers:
                    self.oda_layer_combo.setCurrentText(varsayilan)
                    break

            for varsayilan in kat_varsayilan:
                if varsayilan in text_layers:
                    self.kat_layer_combo.setCurrentText(varsayilan)
                    break

            self.tara_btn.setEnabled(True)

            logger.info(f"DXF yuklendi: {dosya_yolu}, {len(text_layers)} text layer bulundu")

        except Exception as e:
            logger.error(f"DXF yukleme hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"DXF dosyasi yuklenemedi:\n{str(e)}")

    def proje_kimligini_tara(self):
        """Proje kimligini tara (oda ve kat isimleri)"""
        if not self.dxf_analiz:
            return

        oda_layer = self.oda_layer_combo.currentText()
        kat_layer = self.kat_layer_combo.currentText()

        try:
            # Proje kimligini oku
            kimlik = self.dxf_analiz.proje_kimligini_oku(
                oda_layer=oda_layer,
                kat_layer=kat_layer
            )

            self.oda_isimleri = kimlik['odalar']
            self.kat_isimleri = kimlik['katlar']

            # Oda tablosunu guncelle
            self.oda_tablosu.setRowCount(len(self.oda_isimleri))
            for i, oda in enumerate(self.oda_isimleri):
                self.oda_tablosu.setItem(i, 0, QTableWidgetItem(oda['text']))
                self.oda_tablosu.setItem(i, 1, QTableWidgetItem(f"{oda['x']:.2f}"))
                self.oda_tablosu.setItem(i, 2, QTableWidgetItem(f"{oda['y']:.2f}"))

            # Kat tablosunu guncelle
            self.kat_tablosu.setRowCount(len(self.kat_isimleri))
            for i, kat in enumerate(self.kat_isimleri):
                self.kat_tablosu.setItem(i, 0, QTableWidgetItem(kat['text']))
                self.kat_tablosu.setItem(i, 1, QTableWidgetItem(f"{kat['x']:.2f}"))
                self.kat_tablosu.setItem(i, 2, QTableWidgetItem(f"{kat['y']:.2f}"))

            # Tab basliklarini guncelle
            self.tab_widget.setTabText(0, f"Odalar ({len(self.oda_isimleri)})")
            self.tab_widget.setTabText(1, f"Katlar ({len(self.kat_isimleri)})")

            # Ozet guncelle
            self.ozet_label.setText(f"Toplam: {len(self.oda_isimleri)} oda, {len(self.kat_isimleri)} kat bulundu")

            # Gorseli guncelle
            self.gorsel_widget.set_data(
                self.oda_isimleri,
                self.kat_isimleri,
                kimlik.get('hesap_siniri')
            )

            # Bilgi mesaji
            if not self.oda_isimleri and not self.kat_isimleri:
                QMessageBox.information(
                    self, "Bilgi",
                    f"Secilen layer'larda hicbir veri bulunamadi.\n"
                    f"Oda Layer: {oda_layer}\n"
                    f"Kat Layer: {kat_layer}\n\n"
                    f"Farkli layer'lar secmeyi deneyin."
                )

        except Exception as e:
            logger.error(f"Proje kimligi tarama hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Tarama sirasinda hata olustu:\n{str(e)}")

    def gorsel_ayarlarini_guncelle(self):
        """Gorsel ayarlarini guncelle"""
        self.gorsel_widget.show_odalar = self.show_oda_cb.isChecked()
        self.gorsel_widget.show_katlar = self.show_kat_cb.isChecked()
        self.gorsel_widget.update()


# Test icin
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Koyu tema
    app.setStyleSheet("""
        QWidget {
            background-color: #2b2b2b;
            color: #e0e0e0;
            font-family: 'Segoe UI', Arial;
        }
        QGroupBox {
            border: 1px solid #555;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:disabled {
            background-color: #555;
            color: #888;
        }
        QTableWidget {
            background-color: #1e1e1e;
            gridline-color: #444;
        }
        QHeaderView::section {
            background-color: #333;
            padding: 5px;
            border: 1px solid #444;
        }
        QComboBox {
            background-color: #333;
            border: 1px solid #555;
            padding: 5px;
            border-radius: 3px;
        }
        QTabWidget::pane {
            border: 1px solid #555;
        }
        QTabBar::tab {
            background-color: #333;
            padding: 8px 16px;
            border: 1px solid #555;
        }
        QTabBar::tab:selected {
            background-color: #3498db;
        }
        QCheckBox {
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
        }
    """)

    window = OdaIsimleriWindow()
    window.show()

    sys.exit(app.exec())
