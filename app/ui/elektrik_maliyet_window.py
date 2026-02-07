"""
Elektrik Tesisat Maliyet Hesaplama Penceresi
Lamba, Priz, Diyafon, Pano, Anahtar envanter ve maliyet hesaplama arayuzu
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDoubleSpinBox, QSpinBox,
    QGroupBox, QFormLayout, QMessageBox, QFrame,
    QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import logging

from app.core.calculator import hesapla_elektrik_ozel

logger = logging.getLogger(__name__)


class ElektrikMaliyetWindow(QMainWindow):
    """Elektrik tesisat maliyet hesaplama penceresi"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Arayuzu olustur"""
        self.setWindowTitle("Elektrik Tesisat Maliyet Hesaplama")
        self.setGeometry(100, 100, 950, 750)

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
            QDoubleSpinBox, QSpinBox {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #FFD700;
                padding: 5px;
                border-radius: 3px;
                min-height: 25px;
            }
            QPushButton {
                background-color: #FFD700;
                color: #1a1a2e;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFC000;
            }
            QGroupBox {
                color: #FFD700;
                border: 2px solid #FFD700;
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
        panel = QGroupBox("Elektrik Tesisat Envanter Girisi")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # === ENVANTER (ADET) GIRISI ===
        envanter_group = QGroupBox("1. Envanter Adetleri")
        envanter_layout = QFormLayout()
        envanter_layout.setSpacing(12)

        # Lamba/Armatur
        self.spin_lamba = QSpinBox()
        self.spin_lamba.setRange(0, 10000)
        self.spin_lamba.setValue(20)
        self.spin_lamba.setSuffix(" adet")
        lamba_label = QLabel("Lamba / Armatur:")
        lamba_label.setToolTip("Tavan lambasi, spot, aplik vb.")
        envanter_layout.addRow(lamba_label, self.spin_lamba)

        # Priz
        self.spin_priz = QSpinBox()
        self.spin_priz.setRange(0, 10000)
        self.spin_priz.setValue(30)
        self.spin_priz.setSuffix(" adet")
        priz_label = QLabel("Priz:")
        priz_label.setToolTip("Tekli, ikili, uclu prizler")
        envanter_layout.addRow(priz_label, self.spin_priz)

        # Diyafon
        self.spin_diyafon = QSpinBox()
        self.spin_diyafon.setRange(0, 1000)
        self.spin_diyafon.setValue(1)
        self.spin_diyafon.setSuffix(" adet")
        diyafon_label = QLabel("Diyafon Unitesi:")
        diyafon_label.setToolTip("Zil, interkom, goruntulu diyafon")
        envanter_layout.addRow(diyafon_label, self.spin_diyafon)

        # Sartel Pano
        self.spin_pano = QSpinBox()
        self.spin_pano.setRange(0, 100)
        self.spin_pano.setValue(1)
        self.spin_pano.setSuffix(" adet")
        pano_label = QLabel("Sartel Pano / Sigorta Kutusu:")
        pano_label.setToolTip("Ana pano, tali pano, sigorta kutusu")
        envanter_layout.addRow(pano_label, self.spin_pano)

        # Anahtar/Tus
        self.spin_anahtar = QSpinBox()
        self.spin_anahtar.setRange(0, 10000)
        self.spin_anahtar.setValue(15)
        self.spin_anahtar.setSuffix(" adet")
        anahtar_label = QLabel("Lamba Acma Tusu / Anahtar:")
        anahtar_label.setToolTip("Tekli, ikili, komutator, dimmer")
        envanter_layout.addRow(anahtar_label, self.spin_anahtar)

        envanter_group.setLayout(envanter_layout)
        layout.addWidget(envanter_group)

        # === BIRIM FIYATLAR ===
        fiyat_group = QGroupBox("2. Birim Fiyatlar (Malzeme + Iscilik Dahil)")
        fiyat_layout = QFormLayout()
        fiyat_layout.setSpacing(12)

        # Lamba Fiyat
        self.spin_lamba_fiyat = QDoubleSpinBox()
        self.spin_lamba_fiyat.setRange(0, 1000000)
        self.spin_lamba_fiyat.setValue(850)
        self.spin_lamba_fiyat.setSuffix(" TL/adet")
        self.spin_lamba_fiyat.setDecimals(2)
        fiyat_layout.addRow("Lamba / Armatur:", self.spin_lamba_fiyat)

        # Priz Fiyat
        self.spin_priz_fiyat = QDoubleSpinBox()
        self.spin_priz_fiyat.setRange(0, 1000000)
        self.spin_priz_fiyat.setValue(320)
        self.spin_priz_fiyat.setSuffix(" TL/adet")
        self.spin_priz_fiyat.setDecimals(2)
        fiyat_layout.addRow("Priz:", self.spin_priz_fiyat)

        # Diyafon Fiyat
        self.spin_diyafon_fiyat = QDoubleSpinBox()
        self.spin_diyafon_fiyat.setRange(0, 1000000)
        self.spin_diyafon_fiyat.setValue(4500)
        self.spin_diyafon_fiyat.setSuffix(" TL/adet")
        self.spin_diyafon_fiyat.setDecimals(2)
        fiyat_layout.addRow("Diyafon Unitesi:", self.spin_diyafon_fiyat)

        # Pano Fiyat
        self.spin_pano_fiyat = QDoubleSpinBox()
        self.spin_pano_fiyat.setRange(0, 1000000)
        self.spin_pano_fiyat.setValue(8500)
        self.spin_pano_fiyat.setSuffix(" TL/adet")
        self.spin_pano_fiyat.setDecimals(2)
        fiyat_layout.addRow("Sartel Pano:", self.spin_pano_fiyat)

        # Anahtar Fiyat
        self.spin_anahtar_fiyat = QDoubleSpinBox()
        self.spin_anahtar_fiyat.setRange(0, 1000000)
        self.spin_anahtar_fiyat.setValue(280)
        self.spin_anahtar_fiyat.setSuffix(" TL/adet")
        self.spin_anahtar_fiyat.setDecimals(2)
        fiyat_layout.addRow("Lamba Acma Tusu:", self.spin_anahtar_fiyat)

        # Bilgi notu
        bilgi_label = QLabel("Not: Fiyatlara kablo, boru ve iscilik dahildir.")
        bilgi_label.setStyleSheet("color: #888; font-size: 10px; font-style: italic;")
        fiyat_layout.addRow("", bilgi_label)

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
        sonuc_layout.setSpacing(12)

        row = 0

        # Baslik
        baslik = QLabel("ELEKTRIK TESISAT ENVANTER DOKUMU")
        baslik.setStyleSheet("color: #FFD700; font-size: 14px; font-weight: bold;")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sonuc_layout.addWidget(baslik, row, 0, 1, 2)
        row += 1

        # Ayirici
        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # ADET BILGILERI BOLUMU
        adet_baslik = QLabel("ADET BILGILERI")
        adet_baslik.setStyleSheet("color: #00BFFF; font-weight: bold;")
        sonuc_layout.addWidget(adet_baslik, row, 0, 1, 2)
        row += 1

        # Lamba
        sonuc_layout.addWidget(self._create_label("Lamba / Armatur:"), row, 0)
        self.lbl_lamba_adet = self._create_value_label("- adet")
        sonuc_layout.addWidget(self.lbl_lamba_adet, row, 1)
        row += 1

        # Priz
        sonuc_layout.addWidget(self._create_label("Priz:"), row, 0)
        self.lbl_priz_adet = self._create_value_label("- adet")
        sonuc_layout.addWidget(self.lbl_priz_adet, row, 1)
        row += 1

        # Diyafon
        sonuc_layout.addWidget(self._create_label("Diyafon Unitesi:"), row, 0)
        self.lbl_diyafon_adet = self._create_value_label("- adet")
        sonuc_layout.addWidget(self.lbl_diyafon_adet, row, 1)
        row += 1

        # Pano
        sonuc_layout.addWidget(self._create_label("Sartel Pano:"), row, 0)
        self.lbl_pano_adet = self._create_value_label("- adet")
        sonuc_layout.addWidget(self.lbl_pano_adet, row, 1)
        row += 1

        # Anahtar
        sonuc_layout.addWidget(self._create_label("Lamba Acma Tusu:"), row, 0)
        self.lbl_anahtar_adet = self._create_value_label("- adet")
        sonuc_layout.addWidget(self.lbl_anahtar_adet, row, 1)
        row += 1

        # Ayirici
        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # MALIYET KIRILIMI BOLUMU
        maliyet_baslik = QLabel("MALIYET KIRILIMI")
        maliyet_baslik.setStyleSheet("color: #00BFFF; font-weight: bold;")
        sonuc_layout.addWidget(maliyet_baslik, row, 0, 1, 2)
        row += 1

        # Lamba Maliyet
        sonuc_layout.addWidget(self._create_label("Lamba Tutari:"), row, 0)
        self.lbl_lamba_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_lamba_tl, row, 1)
        row += 1

        # Priz Maliyet
        sonuc_layout.addWidget(self._create_label("Priz Tutari:"), row, 0)
        self.lbl_priz_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_priz_tl, row, 1)
        row += 1

        # Diyafon Maliyet
        sonuc_layout.addWidget(self._create_label("Diyafon Tutari:"), row, 0)
        self.lbl_diyafon_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_diyafon_tl, row, 1)
        row += 1

        # Pano Maliyet
        sonuc_layout.addWidget(self._create_label("Pano Tutari:"), row, 0)
        self.lbl_pano_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_pano_tl, row, 1)
        row += 1

        # Anahtar Maliyet
        sonuc_layout.addWidget(self._create_label("Tus/Anahtar Tutari:"), row, 0)
        self.lbl_anahtar_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_anahtar_tl, row, 1)
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
            color: #FFD700;
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
        scroll.setMaximumHeight(180)
        scroll.setStyleSheet("background-color: #0a0a1a; border: 1px solid #FFD700;")

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
        line.setStyleSheet("background-color: #FFD700;")
        line.setFixedHeight(1)
        return line

    def hesapla(self):
        """Hesaplama yap"""
        try:
            # Envanter bilgilerini al
            envanter = {
                'lamba_adet': self.spin_lamba.value(),
                'priz_adet': self.spin_priz.value(),
                'diyafon_adet': self.spin_diyafon.value(),
                'sartel_pano_adet': self.spin_pano.value(),
                'tus_kilit_adet': self.spin_anahtar.value()
            }

            # Fiyatlari al
            fiyatlar = {
                'lamba_birim_fiyat': self.spin_lamba_fiyat.value(),
                'priz_birim_fiyat': self.spin_priz_fiyat.value(),
                'diyafon_birim_fiyat': self.spin_diyafon_fiyat.value(),
                'pano_birim_fiyat': self.spin_pano_fiyat.value(),
                'anahtar_birim_fiyat': self.spin_anahtar_fiyat.value()
            }

            # Hesapla
            sonuc = hesapla_elektrik_ozel(
                envanter=envanter,
                fiyatlar=fiyatlar
            )

            # Sonuclari goster
            self._sonuclari_goster(sonuc)
            logger.info(f"Elektrik hesaplama yapildi: {sonuc}")

        except Exception as e:
            logger.error(f"Hesaplama hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Hesaplama sirasinda hata:\n{str(e)}")

    def _sonuclari_goster(self, sonuc: dict):
        """Sonuclari arayuzde goster"""
        adet = sonuc['adet_bilgileri']
        maliyet = sonuc['maliyet_detayi_tl']

        # Adet Bilgileri
        self.lbl_lamba_adet.setText(f"{adet['lamba_sayisi']} adet")
        self.lbl_priz_adet.setText(f"{adet['priz_sayisi']} adet")
        self.lbl_diyafon_adet.setText(f"{adet['diyafon_sayisi']} adet")
        self.lbl_pano_adet.setText(f"{adet['sartel_pano_sayisi']} adet")
        self.lbl_anahtar_adet.setText(f"{adet['lamba_acma_tusu_sayisi']} adet")

        # Maliyet Kirilimi
        self.lbl_lamba_tl.setText(f"{maliyet['lamba_tutari']:,.2f} TL")
        self.lbl_priz_tl.setText(f"{maliyet['priz_tutari']:,.2f} TL")
        self.lbl_diyafon_tl.setText(f"{maliyet['diyafon_tutari']:,.2f} TL")
        self.lbl_pano_tl.setText(f"{maliyet['pano_tutari']:,.2f} TL")
        self.lbl_anahtar_tl.setText(f"{maliyet['tus_kilit_tutari']:,.2f} TL")

        # Genel Toplam
        self.lbl_toplam.setText(f"{sonuc['genel_toplam_tl']:,.2f} TL")

        # JSON cikti
        import json
        json_str = json.dumps(sonuc, indent=2, ensure_ascii=False)
        self.lbl_json.setText(json_str)
