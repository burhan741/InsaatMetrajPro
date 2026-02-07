"""
Kaba Yapi (Hafriyat - Demir - Beton) Maliyet Hesaplama Penceresi
Manuel girdi ile kaba insaat maliyet hesaplama arayuzu
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDoubleSpinBox,
    QGroupBox, QFormLayout, QMessageBox, QFrame,
    QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import logging

from app.core.calculator import hesapla_kaba_yapi_manuel

logger = logging.getLogger(__name__)


class KabaYapiMaliyetWindow(QMainWindow):
    """Kaba yapi maliyet hesaplama penceresi"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Arayuzu olustur"""
        self.setWindowTitle("Kaba Yapi Maliyet Hesaplama (Hafriyat - Demir - Beton)")
        self.setGeometry(100, 100, 1000, 850)

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
            QDoubleSpinBox {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #8B4513;
                padding: 5px;
                border-radius: 3px;
                min-height: 25px;
            }
            QPushButton {
                background-color: #8B4513;
                color: #FFFFFF;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #A0522D;
            }
            QGroupBox {
                color: #CD853F;
                border: 2px solid #8B4513;
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
            QFrame#sonuc_frame {
                background-color: #0f3460;
                border: 2px solid #00FF00;
                border-radius: 8px;
                padding: 10px;
            }
        """)

    def _create_input_panel(self) -> QGroupBox:
        """Giris panelini olustur"""
        panel = QGroupBox("Kaba Yapi Giris Parametreleri")
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # === HAFRIYAT ===
        hafriyat_group = QGroupBox("1. Hafriyat")
        hafriyat_layout = QFormLayout()

        self.spin_hafriyat_miktar = QDoubleSpinBox()
        self.spin_hafriyat_miktar.setRange(0, 1000000)
        self.spin_hafriyat_miktar.setValue(500)
        self.spin_hafriyat_miktar.setSuffix(" m3/sefer")
        self.spin_hafriyat_miktar.setDecimals(2)
        hafriyat_layout.addRow("Hafriyat Miktari:", self.spin_hafriyat_miktar)

        self.spin_hafriyat_fiyat = QDoubleSpinBox()
        self.spin_hafriyat_fiyat.setRange(0, 100000)
        self.spin_hafriyat_fiyat.setValue(180)
        self.spin_hafriyat_fiyat.setSuffix(" TL/birim")
        self.spin_hafriyat_fiyat.setDecimals(2)
        hafriyat_layout.addRow("Birim Fiyat:", self.spin_hafriyat_fiyat)

        hafriyat_group.setLayout(hafriyat_layout)
        layout.addWidget(hafriyat_group)

        # === DEMIR ===
        demir_group = QGroupBox("2. Demir (Insaat Demiri)")
        demir_layout = QFormLayout()

        # Ince Demir
        lbl_ince = QLabel("--- Ince Demir (8mm - 12mm) ---")
        lbl_ince.setStyleSheet("color: #888; font-size: 10px;")
        lbl_ince.setAlignment(Qt.AlignmentFlag.AlignCenter)
        demir_layout.addRow(lbl_ince)

        self.spin_demir_ince_ton = QDoubleSpinBox()
        self.spin_demir_ince_ton.setRange(0, 100000)
        self.spin_demir_ince_ton.setValue(5)
        self.spin_demir_ince_ton.setSuffix(" ton")
        self.spin_demir_ince_ton.setDecimals(3)
        demir_layout.addRow("Proje Tonaji:", self.spin_demir_ince_ton)

        self.spin_demir_ince_fiyat = QDoubleSpinBox()
        self.spin_demir_ince_fiyat.setRange(0, 1000000)
        self.spin_demir_ince_fiyat.setValue(32000)
        self.spin_demir_ince_fiyat.setSuffix(" TL/ton")
        self.spin_demir_ince_fiyat.setDecimals(2)
        demir_layout.addRow("Birim Fiyat:", self.spin_demir_ince_fiyat)

        # Kalin Demir
        lbl_kalin = QLabel("--- Kalin Demir (14mm ve uzeri) ---")
        lbl_kalin.setStyleSheet("color: #888; font-size: 10px;")
        lbl_kalin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        demir_layout.addRow(lbl_kalin)

        self.spin_demir_kalin_ton = QDoubleSpinBox()
        self.spin_demir_kalin_ton.setRange(0, 100000)
        self.spin_demir_kalin_ton.setValue(8)
        self.spin_demir_kalin_ton.setSuffix(" ton")
        self.spin_demir_kalin_ton.setDecimals(3)
        demir_layout.addRow("Proje Tonaji:", self.spin_demir_kalin_ton)

        self.spin_demir_kalin_fiyat = QDoubleSpinBox()
        self.spin_demir_kalin_fiyat.setRange(0, 1000000)
        self.spin_demir_kalin_fiyat.setValue(30000)
        self.spin_demir_kalin_fiyat.setSuffix(" TL/ton")
        self.spin_demir_kalin_fiyat.setDecimals(2)
        demir_layout.addRow("Birim Fiyat:", self.spin_demir_kalin_fiyat)

        # Demir Fire
        lbl_fire = QLabel("--- Fire Orani ---")
        lbl_fire.setStyleSheet("color: #FFD700; font-size: 10px;")
        lbl_fire.setAlignment(Qt.AlignmentFlag.AlignCenter)
        demir_layout.addRow(lbl_fire)

        self.spin_demir_fire = QDoubleSpinBox()
        self.spin_demir_fire.setRange(0, 50)
        self.spin_demir_fire.setValue(3)
        self.spin_demir_fire.setSuffix(" %")
        self.spin_demir_fire.setDecimals(1)
        demir_layout.addRow("Demir Fire:", self.spin_demir_fire)

        demir_group.setLayout(demir_layout)
        layout.addWidget(demir_group)

        # === BETON ===
        beton_group = QGroupBox("3. Hazir Beton")
        beton_layout = QFormLayout()

        self.spin_beton_m3 = QDoubleSpinBox()
        self.spin_beton_m3.setRange(0, 100000)
        self.spin_beton_m3.setValue(150)
        self.spin_beton_m3.setSuffix(" m3")
        self.spin_beton_m3.setDecimals(2)
        beton_layout.addRow("Proje Betonaji:", self.spin_beton_m3)

        self.spin_beton_fiyat = QDoubleSpinBox()
        self.spin_beton_fiyat.setRange(0, 100000)
        self.spin_beton_fiyat.setValue(2800)
        self.spin_beton_fiyat.setSuffix(" TL/m3")
        self.spin_beton_fiyat.setDecimals(2)
        beton_layout.addRow("Beton Birim Fiyat:", self.spin_beton_fiyat)

        self.spin_pompa_fiyat = QDoubleSpinBox()
        self.spin_pompa_fiyat.setRange(0, 100000)
        self.spin_pompa_fiyat.setValue(150)
        self.spin_pompa_fiyat.setSuffix(" TL/m3")
        self.spin_pompa_fiyat.setDecimals(2)
        beton_layout.addRow("Pompa Fiyati:", self.spin_pompa_fiyat)

        # Beton Fire
        self.spin_beton_fire = QDoubleSpinBox()
        self.spin_beton_fire.setRange(0, 50)
        self.spin_beton_fire.setValue(5)
        self.spin_beton_fire.setSuffix(" %")
        self.spin_beton_fire.setDecimals(1)
        beton_layout.addRow("Beton Fire:", self.spin_beton_fire)

        beton_group.setLayout(beton_layout)
        layout.addWidget(beton_group)

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
        baslik = QLabel("KABA YAPI MALZEME DOKUMU")
        baslik.setStyleSheet("color: #CD853F; font-size: 14px; font-weight: bold;")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sonuc_layout.addWidget(baslik, row, 0, 1, 2)
        row += 1

        # Ayirici
        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # METRAJ DETAYLARI BOLUMU
        metraj_baslik = QLabel("METRAJ DETAYLARI")
        metraj_baslik.setStyleSheet("color: #FFD700; font-weight: bold;")
        sonuc_layout.addWidget(metraj_baslik, row, 0, 1, 2)
        row += 1

        # Hafriyat
        sonuc_layout.addWidget(self._create_label("Hafriyat:"), row, 0)
        self.lbl_hafriyat = self._create_value_label("-")
        sonuc_layout.addWidget(self.lbl_hafriyat, row, 1)
        row += 1

        # Ince Demir - Proje
        sonuc_layout.addWidget(self._create_label("Ince Demir Proje:"), row, 0)
        self.lbl_ince_proje = self._create_value_label("- ton")
        sonuc_layout.addWidget(self.lbl_ince_proje, row, 1)
        row += 1

        # Ince Demir - Satin Alma
        sonuc_layout.addWidget(self._create_label("Ince Demir Satin Alma:"), row, 0)
        self.lbl_ince_fireli = self._create_value_label("- ton", "#FFA500")
        sonuc_layout.addWidget(self.lbl_ince_fireli, row, 1)
        row += 1

        # Kalin Demir - Proje
        sonuc_layout.addWidget(self._create_label("Kalin Demir Proje:"), row, 0)
        self.lbl_kalin_proje = self._create_value_label("- ton")
        sonuc_layout.addWidget(self.lbl_kalin_proje, row, 1)
        row += 1

        # Kalin Demir - Satin Alma
        sonuc_layout.addWidget(self._create_label("Kalin Demir Satin Alma:"), row, 0)
        self.lbl_kalin_fireli = self._create_value_label("- ton", "#FFA500")
        sonuc_layout.addWidget(self.lbl_kalin_fireli, row, 1)
        row += 1

        # Beton - Proje
        sonuc_layout.addWidget(self._create_label("Beton Proje:"), row, 0)
        self.lbl_beton_proje = self._create_value_label("- m3")
        sonuc_layout.addWidget(self.lbl_beton_proje, row, 1)
        row += 1

        # Beton - Siparis
        sonuc_layout.addWidget(self._create_label("Beton Siparis (Fireli):"), row, 0)
        self.lbl_beton_fireli = self._create_value_label("- m3", "#FFA500")
        sonuc_layout.addWidget(self.lbl_beton_fireli, row, 1)
        row += 1

        # Fire Oranlari
        sonuc_layout.addWidget(self._create_label("Kullanilan Fire Oranlari:"), row, 0)
        self.lbl_fire = self._create_value_label("-", "#888")
        sonuc_layout.addWidget(self.lbl_fire, row, 1)
        row += 1

        # Ayirici
        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # MALIYET TABLOSU BOLUMU
        maliyet_baslik = QLabel("MALIYET TABLOSU")
        maliyet_baslik.setStyleSheet("color: #FFD700; font-weight: bold;")
        sonuc_layout.addWidget(maliyet_baslik, row, 0, 1, 2)
        row += 1

        # Hafriyat Tutari
        sonuc_layout.addWidget(self._create_label("Hafriyat Tutari:"), row, 0)
        self.lbl_hafriyat_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_hafriyat_tl, row, 1)
        row += 1

        # Ince Demir Tutari
        sonuc_layout.addWidget(self._create_label("Ince Demir Tutari:"), row, 0)
        self.lbl_ince_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_ince_tl, row, 1)
        row += 1

        # Kalin Demir Tutari
        sonuc_layout.addWidget(self._create_label("Kalin Demir Tutari:"), row, 0)
        self.lbl_kalin_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_kalin_tl, row, 1)
        row += 1

        # Beton Tutari
        sonuc_layout.addWidget(self._create_label("Beton Tutari:"), row, 0)
        self.lbl_beton_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_beton_tl, row, 1)
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
            color: #CD853F;
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
        scroll.setMaximumHeight(160)
        scroll.setStyleSheet("background-color: #0a0a1a; border: 1px solid #8B4513;")

        json_layout.addWidget(scroll)
        json_group.setLayout(json_layout)
        layout.addWidget(json_group)

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
        line.setStyleSheet("background-color: #8B4513;")
        line.setFixedHeight(1)
        return line

    def hesapla(self):
        """Hesaplama yap"""
        try:
            # Girdileri al
            girdiler = {
                'hafriyat_miktar': self.spin_hafriyat_miktar.value(),
                'demir_ince_ton': self.spin_demir_ince_ton.value(),
                'demir_kalin_ton': self.spin_demir_kalin_ton.value(),
                'beton_m3': self.spin_beton_m3.value()
            }

            # Fiyatlari al
            fiyatlar = {
                'hafriyat_birim_fiyat': self.spin_hafriyat_fiyat.value(),
                'demir_ince_ton_fiyat': self.spin_demir_ince_fiyat.value(),
                'demir_kalin_ton_fiyat': self.spin_demir_kalin_fiyat.value(),
                'beton_m3_fiyat': self.spin_beton_fiyat.value(),
                'beton_pompa_fiyat': self.spin_pompa_fiyat.value()
            }

            # Fire oranlarini al
            fire_oranlari = {
                'demir_fire_yuzde': self.spin_demir_fire.value(),
                'beton_fire_yuzde': self.spin_beton_fire.value()
            }

            # Hesapla
            sonuc = hesapla_kaba_yapi_manuel(
                girdiler=girdiler,
                fiyatlar=fiyatlar,
                fire_oranlari=fire_oranlari
            )

            # Sonuclari goster
            self._sonuclari_goster(sonuc)
            logger.info(f"Kaba yapi hesaplama yapildi: {sonuc}")

        except Exception as e:
            logger.error(f"Hesaplama hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Hesaplama sirasinda hata:\n{str(e)}")

    def _sonuclari_goster(self, sonuc: dict):
        """Sonuclari arayuzde goster"""
        metraj = sonuc['metraj_detaylari']
        fire = sonuc['kullanilan_fire_oranlari']
        maliyet = sonuc['maliyet_tablosu_tl']

        # Metraj Detaylari
        self.lbl_hafriyat.setText(f"{metraj['hafriyat']['miktar']} {metraj['hafriyat']['birim']}")

        self.lbl_ince_proje.setText(f"{metraj['demir_ince_8_12mm']['proje_tonaji']} ton")
        self.lbl_ince_fireli.setText(f"{metraj['demir_ince_8_12mm']['satin_alinacak_tonaj_fireli']:.3f} ton")

        self.lbl_kalin_proje.setText(f"{metraj['demir_kalin_14mm_plus']['proje_tonaji']} ton")
        self.lbl_kalin_fireli.setText(f"{metraj['demir_kalin_14mm_plus']['satin_alinacak_tonaj_fireli']:.3f} ton")

        self.lbl_beton_proje.setText(f"{metraj['hazir_beton']['proje_m3']} m3")
        self.lbl_beton_fireli.setText(f"{metraj['hazir_beton']['siparis_m3_fireli']:.2f} m3")

        # Fire Oranlari
        self.lbl_fire.setText(f"Demir: {fire['demir_fire']}, Beton: {fire['beton_fire']}")

        # Maliyet Tablosu
        self.lbl_hafriyat_tl.setText(f"{maliyet['hafriyat_tutari']:,.2f} TL")
        self.lbl_ince_tl.setText(f"{maliyet['ince_demir_tutari']:,.2f} TL")
        self.lbl_kalin_tl.setText(f"{maliyet['kalin_demir_tutari']:,.2f} TL")
        self.lbl_beton_tl.setText(f"{maliyet['beton_tutari']:,.2f} TL")

        # Genel Toplam
        self.lbl_toplam.setText(f"{sonuc['genel_toplam_tl']:,.2f} TL")

        # JSON cikti
        import json
        json_str = json.dumps(sonuc, indent=2, ensure_ascii=False)
        self.lbl_json.setText(json_str)
