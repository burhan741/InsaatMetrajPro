"""
Fayans Hesaplama Penceresi
Oda bazli dinamik fayans hesaplama arayuzu - Grid yontemi ile gercek fire hesaplama
"""

from PyQt6.QtWidgets import (
QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
QPushButton, QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView,
QFormLayout, QMessageBox, QFrame, QGridLayout, QLineEdit,
QRadioButton, QButtonGroup, QScrollArea, QSplitter, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import logging

from app.core.fayans_hesaplama import (
hesapla_fayans_oda_detayli,
STANDART_FAYANS_EBATLARI
)

logger = logging.getLogger(__name__)


class FayansHesaplamaWindow(QMainWindow):
    """Fayans hesaplama penceresi - Oda bazli dinamik hesaplama"""

    hesaplama_tamamlandi = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.odalar = [] # Oda listesi
        self.son_sonuc = None # Son hesaplama sonucu
        self.son_hesaplama = None
        self.init_ui()

        def init_ui(self):
            """Arayuzu olustur"""
            self.setWindowTitle("Oda Bazli Fayans Hesaplama")
            self.setGeometry(100, 100, 1400, 900)

            # Ana widget
            main_widget = QWidget()
            self.setCentralWidget(main_widget)
            main_layout = QHBoxLayout(main_widget)

            # Splitter ile bolunmus panel
            splitter = QSplitter(Qt.Orientation.Horizontal)

            # Sol panel - Girisler
            left_widget = QWidget()
            left_layout = QVBoxLayout(left_widget)
            left_layout.setContentsMargins(5, 5, 5, 5)

            # Scroll area icinde sol panel
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

            scroll_content = QWidget()
            scroll_layout = QVBoxLayout(scroll_content)
            scroll_layout.setSpacing(10)

            # Parametre paneli
            scroll_layout.addWidget(self._create_parameter_panel())

            # Oda ekleme paneli
            scroll_layout.addWidget(self._create_oda_panel())

            # Oda listesi
            scroll_layout.addWidget(self._create_oda_list_panel())

            # Hesapla butonu
            btn_hesapla = QPushButton("HESAPLA")
            btn_hesapla.setFixedHeight(50)
            btn_hesapla.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            btn_hesapla.setStyleSheet("""
            QPushButton {
            background-color: #00FF00;
            color: #000;
            border: 2px solid #00AA00;
            border-radius: 8px;
            font-size: 16px;
            }
            QPushButton:hover {
            background-color: #00DD00;
            }
            """)
            btn_hesapla.clicked.connect(self.hesapla)
            scroll_layout.addWidget(btn_hesapla)

            scroll_layout.addStretch()
            scroll.setWidget(scroll_content)
            left_layout.addWidget(scroll)

            splitter.addWidget(left_widget)

            # Sag panel - Sonuclar
            right_widget = self._create_results_panel()
            splitter.addWidget(right_widget)

            # Splitter oranlarini ayarla
            splitter.setSizes([500, 900])

            main_layout.addWidget(splitter)
            self._apply_styles()

            def _apply_styles(self):
                """Stil uygula"""
                self.setStyleSheet("""
                QMainWindow {
                background-color: #0a0a1a;
                }
                QWidget {
                background-color: #0a0a1a;
                }
                QLabel {
                color: #e0e0e0;
                }
                QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #00BFFF;
                padding: 5px;
                border-radius: 4px;
                min-height: 25px;
                }
                QComboBox::drop-down {
                border: none;
                }
                QComboBox QAbstractItemView {
                background-color: #16213e;
                color: #e0e0e0;
                selection-background-color: #00BFFF;
                }
                QPushButton {
                background-color: #00BFFF;
                color: #0a0a1a;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                }
                QPushButton:hover {
                background-color: #00CCFF;
                }
                QPushButton:disabled {
                background-color: #333;
                color: #666;
                }
                QGroupBox {
                color: #00BFFF;
                border: 2px solid #00BFFF;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
                }
                QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                }
                QRadioButton {
                color: #e0e0e0;
                }
                QRadioButton::indicator:checked {
                background-color: #00FF00;
                border: 2px solid #00AA00;
                border-radius: 8px;
                }
                QRadioButton::indicator:unchecked {
                background-color: #16213e;
                border: 2px solid #00BFFF;
                border-radius: 8px;
                }
                QTableWidget {
                background-color: #14191e;
                color: #e0e0e0;
                border: 2px solid #00BFFF;
                border-radius: 6px;
                gridline-color: #2a3a4a;
                }
                QTableWidget::item {
                padding: 4px;
                }
                QTableWidget::item:selected {
                background-color: #00BFFF;
                color: #000;
                }
                QHeaderView::section {
                background-color: #1a3a5a;
                color: #fff;
                padding: 6px;
                border: 1px solid #00BFFF;
                font-weight: bold;
                }
                QScrollArea {
                border: none;
                }
                QTabWidget::pane {
                border: 2px solid #00BFFF;
                border-radius: 6px;
                background-color: #0f1a2a;
                }
                QTabBar::tab {
                background-color: #1a2a3a;
                color: #e0e0e0;
                padding: 8px 16px;
                border: 1px solid #00BFFF;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                }
                QTabBar::tab:selected {
                background-color: #00BFFF;
                color: #000;
                font-weight: bold;
                }
                """)

                def _create_parameter_panel(self) -> QGroupBox:
                    """Parametre panelini olustur"""
                    panel = QGroupBox("Genel Parametreler")
                    layout = QFormLayout()
                    layout.setSpacing(10)

                    # Fayans kutu m2
                    self.spin_kutu_m2 = QDoubleSpinBox()
                    self.spin_kutu_m2.setRange(0.1, 10)
                    self.spin_kutu_m2.setValue(1.44)
                    self.spin_kutu_m2.setSuffix(" m2/kutu")
                    self.spin_kutu_m2.setDecimals(2)
                    layout.addRow("Kutu Icerigi:", self.spin_kutu_m2)

                    # Fayans m2 fiyat
                    self.spin_fayans_fiyat = QDoubleSpinBox()
                    self.spin_fayans_fiyat.setRange(0, 10000)
                    self.spin_fayans_fiyat.setValue(180)
                    self.spin_fayans_fiyat.setSuffix(" TL/m2")
                    self.spin_fayans_fiyat.setDecimals(2)
                    layout.addRow("Fayans Fiyati:", self.spin_fayans_fiyat)

                    # Ekip gunluk ucret
                    self.spin_ekip_ucret = QDoubleSpinBox()
                    self.spin_ekip_ucret.setRange(0, 50000)
                    self.spin_ekip_ucret.setValue(3500)
                    self.spin_ekip_ucret.setSuffix(" TL/gun")
                    self.spin_ekip_ucret.setDecimals(0)
                    layout.addRow("Ekip Gunluk Ucret:", self.spin_ekip_ucret)

                    # Ekip aciklamasi
                    ekip_aciklama = QLabel("(1 Usta + 1 Yardimci - 40+ yas tecrubeli)")
                    ekip_aciklama.setStyleSheet("color: #888; font-size: 10px;")
                    layout.addRow("", ekip_aciklama)

                    # Verimlilik kaynagi
                    verim_group = QGroupBox("Iscilik Hizi Kaynagi")
                    verim_layout = QVBoxLayout()

                    self.radio_group = QButtonGroup(self)

                    self.radio_piyasa = QRadioButton("Piyasa (Gercekci Hizlar)")
                    self.radio_piyasa.setChecked(True)
                    self.radio_group.addButton(self.radio_piyasa, 0)
                    verim_layout.addWidget(self.radio_piyasa)

                    piyasa_info = QLabel(" Buyuk Ebat: 15, Kucuk Ebat: 22, Islak Zemin: 10 m2/gun")
                    piyasa_info.setStyleSheet("color: #00FF00; font-size: 10px;")
                    verim_layout.addWidget(piyasa_info)

                    self.radio_manuel = QRadioButton("Manuel (Kendi Hiziniz)")
                    self.radio_group.addButton(self.radio_manuel, 1)
                    self.radio_manuel.toggled.connect(self._manuel_toggled)
                    verim_layout.addWidget(self.radio_manuel)

                    manuel_layout = QHBoxLayout()
                    manuel_layout.addSpacing(20)
                    self.spin_manuel_hiz = QDoubleSpinBox()
                    self.spin_manuel_hiz.setRange(1, 100)
                    self.spin_manuel_hiz.setValue(18)
                    self.spin_manuel_hiz.setSuffix(" m2/gun")
                    self.spin_manuel_hiz.setEnabled(False)
                    manuel_layout.addWidget(QLabel("Hiz:"))
                    manuel_layout.addWidget(self.spin_manuel_hiz)
                    manuel_layout.addStretch()
                    verim_layout.addLayout(manuel_layout)

                    verim_group.setLayout(verim_layout)
                    layout.addRow(verim_group)

                    panel.setLayout(layout)
                    return panel

                    def _create_oda_panel(self) -> QGroupBox:
                        """Oda ekleme panelini olustur"""
                        panel = QGroupBox("Yeni Oda Ekle")
                        layout = QGridLayout()
                        layout.setSpacing(8)

                        # Oda adi
                        layout.addWidget(QLabel("Oda Adi:"), 0, 0)
                        self.txt_oda_adi = QLineEdit()
                        self.txt_oda_adi.setPlaceholderText("Ornek: Salon")
                        layout.addWidget(self.txt_oda_adi, 0, 1)

                        # Oda boyutlari
                        layout.addWidget(QLabel("Oda Eni (cm):"), 1, 0)
                        self.spin_oda_en = QSpinBox()
                        self.spin_oda_en.setRange(50, 10000)
                        self.spin_oda_en.setValue(400)
                        self.spin_oda_en.setSuffix(" cm")
                        layout.addWidget(self.spin_oda_en, 1, 1)

                        layout.addWidget(QLabel("Oda Boyu (cm):"), 2, 0)
                        self.spin_oda_boy = QSpinBox()
                        self.spin_oda_boy.setRange(50, 10000)
                        self.spin_oda_boy.setValue(500)
                        self.spin_oda_boy.setSuffix(" cm")
                        layout.addWidget(self.spin_oda_boy, 2, 1)

                        # Fayans ebadi
                        layout.addWidget(QLabel("Fayans Ebadi:"), 3, 0)
                        self.combo_fayans_ebat = QComboBox()
                        for ebat in STANDART_FAYANS_EBATLARI:
                            self.combo_fayans_ebat.addItem(
                            ebat["ad"],
                            {"en": ebat["en"], "boy": ebat["boy"]}
                            )
                            self.combo_fayans_ebat.setCurrentIndex(8) # 60x60 varsayilan
                            layout.addWidget(self.combo_fayans_ebat, 3, 1)

                            # Manuel fayans ebadi
                            layout.addWidget(QLabel("veya Manuel:"), 4, 0)
                            manuel_ebat_layout = QHBoxLayout()
                            self.spin_fayans_en = QSpinBox()
                            self.spin_fayans_en.setRange(10, 200)
                            self.spin_fayans_en.setValue(60)
                            self.spin_fayans_en.setSuffix(" cm")
                            manuel_ebat_layout.addWidget(self.spin_fayans_en)
                            manuel_ebat_layout.addWidget(QLabel("x"))
                            self.spin_fayans_boy = QSpinBox()
                            self.spin_fayans_boy.setRange(10, 200)
                            self.spin_fayans_boy.setValue(60)
                            self.spin_fayans_boy.setSuffix(" cm")
                            manuel_ebat_layout.addWidget(self.spin_fayans_boy)
                            layout.addLayout(manuel_ebat_layout, 4, 1)

                            # Fayans ebadi combobox degistiginde manuel degerler guncelle
                            self.combo_fayans_ebat.currentIndexChanged.connect(self._fayans_ebat_degisti)

                            # Oda turu
                            layout.addWidget(QLabel("Oda Turu:"), 5, 0)
                            self.combo_oda_turu = QComboBox()
                            self.combo_oda_turu.addItem("Kuru Zemin (Salon, Yatak Odasi)", "kuru_zemin")
                            self.combo_oda_turu.addItem("Islak Zemin (Banyo, WC, Mutfak)", "islak_zemin")
                            layout.addWidget(self.combo_oda_turu, 5, 1)

                            # Hesaplanan alan goster
                            self.lbl_hesaplanan_alan = QLabel("Hesaplanan Alan: 20.00 m2")
                            self.lbl_hesaplanan_alan.setStyleSheet("color: #FFD700; font-weight: bold;")
                            layout.addWidget(self.lbl_hesaplanan_alan, 6, 0, 1, 2)

                            # Oda eni/boyu degistiginde alani guncelle
                            self.spin_oda_en.valueChanged.connect(self._alan_guncelle)
                            self.spin_oda_boy.valueChanged.connect(self._alan_guncelle)
                            self._alan_guncelle()

                            # Butonlar
                            btn_layout = QHBoxLayout()

                            btn_ekle = QPushButton("ODA EKLE")
                            btn_ekle.setStyleSheet("""
                            QPushButton {
                            background-color: #00AA00;
                            padding: 10px;
                            }
                            QPushButton:hover {
                            background-color: #00CC00;
                            }
                            """)
                            btn_ekle.clicked.connect(self.oda_ekle)
                            btn_layout.addWidget(btn_ekle)

                            btn_temizle = QPushButton("Formu Temizle")
                            btn_temizle.clicked.connect(self.formu_temizle)
                            btn_layout.addWidget(btn_temizle)

                            layout.addLayout(btn_layout, 7, 0, 1, 2)

                            panel.setLayout(layout)
                            return panel

                            def _create_oda_list_panel(self) -> QGroupBox:
                                """Oda listesi panelini olustur"""
                                panel = QGroupBox("Eklenen Odalar")
                                layout = QVBoxLayout()

                                # Oda tablosu
                                self.tbl_odalar = QTableWidget()
                                self.tbl_odalar.setColumnCount(6)
                                self.tbl_odalar.setHorizontalHeaderLabels([
                                "Oda Adi", "Boyut (cm)", "Fayans (cm)", "Tur", "Alan (m2)", "Sil"
                                ])
                                self.tbl_odalar.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
                                self.tbl_odalar.setMaximumHeight(200)
                                self.tbl_odalar.setAlternatingRowColors(True)
                                layout.addWidget(self.tbl_odalar)

                                # Toplam bilgi
                                self.lbl_toplam_oda = QLabel("Toplam: 0 oda, 0.00 m2")
                                self.lbl_toplam_oda.setStyleSheet("color: #00FF00; font-weight: bold;")
                                layout.addWidget(self.lbl_toplam_oda)

                                # Tum odalari temizle butonu
                                btn_tum_temizle = QPushButton("Tum Odalari Temizle")
                                btn_tum_temizle.setStyleSheet("""
                                QPushButton {
                                background-color: #AA0000;
                                }
                                QPushButton:hover {
                                background-color: #CC0000;
                                }
                                """)
                                btn_tum_temizle.clicked.connect(self.tum_odalari_temizle)
                                layout.addWidget(btn_tum_temizle)

                                panel.setLayout(layout)
                                return panel

                                def _create_results_panel(self) -> QWidget:
                                    """Sonuc panelini olustur"""
                                    widget = QWidget()
                                    layout = QVBoxLayout(widget)

                                    # Tab widget
                                    self.tab_widget = QTabWidget()

                                    # Tab 1: Oda Detaylari
                                    tab_detay = QWidget()
                                    tab_detay_layout = QVBoxLayout(tab_detay)

                                    self.tbl_sonuclar = QTableWidget()
                                    self.tbl_sonuclar.setColumnCount(11)
                                    self.tbl_sonuclar.setHorizontalHeaderLabels([
                                    "Oda", "Net m2", "Brut m2", "Grid", "Fayans Adet",
                                    "Fire %", "Optimal Yon", "Yapistirici kg", "Derz kg",
                                    "Verim m2/gun", "Sure (gun)"
                                    ])
                                    self.tbl_sonuclar.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
                                    self.tbl_sonuclar.setAlternatingRowColors(True)
                                    tab_detay_layout.addWidget(self.tbl_sonuclar)

                                    self.tab_widget.addTab(tab_detay, "Oda Detaylari")

                                    # Tab 2: Ozet
                                    tab_ozet = QWidget()
                                    tab_ozet_layout = QVBoxLayout(tab_ozet)

                                    # Ozet frame
                                    ozet_frame = QFrame()
                                    ozet_frame.setStyleSheet("""
                                    QFrame {
                                    background-color: #0f1a2a;
                                    border: 2px solid #00BFFF;
                                    border-radius: 8px;
                                    padding: 15px;
                                    }
                                    """)
                                    ozet_grid = QGridLayout(ozet_frame)
                                    ozet_grid.setSpacing(12)

                                    row = 0

                                    # Baslik
                                    baslik = QLabel("HESAPLAMA OZETI")
                                    baslik.setStyleSheet("color: #00BFFF; font-size: 16px; font-weight: bold;")
                                    baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
                                    ozet_grid.addWidget(baslik, row, 0, 1, 2)
                                    row += 1

                                    # Ayirici
                                    ozet_grid.addWidget(self._create_separator(), row, 0, 1, 2)
                                    row += 1

                                    # Alan bilgileri
                                    ozet_grid.addWidget(self._label("Toplam Net Alan:"), row, 0)
                                    self.lbl_net_alan = self._value_label("- m2")
                                    ozet_grid.addWidget(self.lbl_net_alan, row, 1)
                                    row += 1

                                    ozet_grid.addWidget(self._label("Toplam Brut Alan:"), row, 0)
                                    self.lbl_brut_alan = self._value_label("- m2")
                                    ozet_grid.addWidget(self.lbl_brut_alan, row, 1)
                                    row += 1

                                    ozet_grid.addWidget(self._label("Ortalama Fire Orani:"), row, 0)
                                    self.lbl_fire = self._value_label("- %", "#FFD700")
                                    ozet_grid.addWidget(self.lbl_fire, row, 1)
                                    row += 1

                                    # Ayirici
                                    ozet_grid.addWidget(self._create_separator(), row, 0, 1, 2)
                                    row += 1

                                    # Siparis bilgileri
                                    siparis_baslik = QLabel("SIPARIS BILGILERI")
                                    siparis_baslik.setStyleSheet("color: #00FF00; font-weight: bold;")
                                    ozet_grid.addWidget(siparis_baslik, row, 0, 1, 2)
                                    row += 1

                                    ozet_grid.addWidget(self._label("Gereken Fayans Adet:"), row, 0)
                                    self.lbl_fayans_adet = self._value_label("- adet")
                                    ozet_grid.addWidget(self.lbl_fayans_adet, row, 1)
                                    row += 1

                                    ozet_grid.addWidget(self._label("Gereken Kutu:"), row, 0)
                                    self.lbl_kutu = self._value_label("- kutu", "#00FF00")
                                    ozet_grid.addWidget(self.lbl_kutu, row, 1)
                                    row += 1

                                    # Ayirici
                                    ozet_grid.addWidget(self._create_separator(), row, 0, 1, 2)
                                    row += 1

                                    # Malzeme bilgileri
                                    malzeme_baslik = QLabel("MALZEME IHTIYACI")
                                    malzeme_baslik.setStyleSheet("color: #00BFFF; font-weight: bold;")
                                    ozet_grid.addWidget(malzeme_baslik, row, 0, 1, 2)
                                    row += 1

                                    ozet_grid.addWidget(self._label("Yapistirici:"), row, 0)
                                    self.lbl_yapistirici = self._value_label("- kg (- torba)")
                                    ozet_grid.addWidget(self.lbl_yapistirici, row, 1)
                                    row += 1

                                    ozet_grid.addWidget(self._label("Derz:"), row, 0)
                                    self.lbl_derz = self._value_label("- kg (- torba)")
                                    ozet_grid.addWidget(self.lbl_derz, row, 1)
                                    row += 1

                                    # Ayirici
                                    ozet_grid.addWidget(self._create_separator(), row, 0, 1, 2)
                                    row += 1

                                    # Sure bilgisi
                                    ozet_grid.addWidget(self._label("Tahmini Is Suresi:"), row, 0)
                                    self.lbl_sure = self._value_label("- gun", "#FFD700")
                                    ozet_grid.addWidget(self.lbl_sure, row, 1)
                                    row += 1

                                    tab_ozet_layout.addWidget(ozet_frame)
                                    tab_ozet_layout.addStretch()

                                    self.tab_widget.addTab(tab_ozet, "Ozet")

                                    # Tab 3: Maliyet
                                    tab_maliyet = QWidget()
                                    tab_maliyet_layout = QVBoxLayout(tab_maliyet)

                                    maliyet_frame = QFrame()
                                    maliyet_frame.setStyleSheet("""
                                    QFrame {
                                    background-color: #0f1a2a;
                                    border: 2px solid #00FF00;
                                    border-radius: 8px;
                                    padding: 15px;
                                    }
                                    """)
                                    maliyet_grid = QGridLayout(maliyet_frame)
                                    maliyet_grid.setSpacing(12)

                                    row = 0

                                    # Baslik
                                    m_baslik = QLabel("MALIYET OZETI")
                                    m_baslik.setStyleSheet("color: #00FF00; font-size: 16px; font-weight: bold;")
                                    m_baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
                                    maliyet_grid.addWidget(m_baslik, row, 0, 1, 2)
                                    row += 1

                                    maliyet_grid.addWidget(self._create_separator("#00FF00"), row, 0, 1, 2)
                                    row += 1

                                    # Malzeme maliyetleri
                                    maliyet_grid.addWidget(self._label("Fayans Maliyeti:"), row, 0)
                                    self.lbl_fayans_maliyet = self._value_label("- TL")
                                    maliyet_grid.addWidget(self.lbl_fayans_maliyet, row, 1)
                                    row += 1

                                    maliyet_grid.addWidget(self._label("Yapistirici Maliyeti:"), row, 0)
                                    self.lbl_yapistirici_maliyet = self._value_label("- TL")
                                    maliyet_grid.addWidget(self.lbl_yapistirici_maliyet, row, 1)
                                    row += 1

                                    maliyet_grid.addWidget(self._label("Derz Maliyeti:"), row, 0)
                                    self.lbl_derz_maliyet = self._value_label("- TL")
                                    maliyet_grid.addWidget(self.lbl_derz_maliyet, row, 1)
                                    row += 1

                                    maliyet_grid.addWidget(self._create_separator("#00FF00"), row, 0, 1, 2)
                                    row += 1

                                    maliyet_grid.addWidget(self._label("Toplam Malzeme:"), row, 0)
                                    self.lbl_malzeme_toplam = self._value_label("- TL", "#FFD700")
                                    maliyet_grid.addWidget(self.lbl_malzeme_toplam, row, 1)
                                    row += 1

                                    maliyet_grid.addWidget(self._label("Iscilik Maliyeti:"), row, 0)
                                    self.lbl_iscilik_maliyet = self._value_label("- TL", "#FFD700")
                                    maliyet_grid.addWidget(self.lbl_iscilik_maliyet, row, 1)
                                    row += 1

                                    maliyet_grid.addWidget(self._create_separator("#00FF00"), row, 0, 1, 2)
                                    row += 1

                                    # Genel toplam
                                    toplam_label = QLabel("GENEL TOPLAM:")
                                    toplam_label.setStyleSheet("color: #00FF00; font-size: 16px; font-weight: bold;")
                                    maliyet_grid.addWidget(toplam_label, row, 0)

                                    self.lbl_genel_toplam = QLabel("- TL")
                                    self.lbl_genel_toplam.setStyleSheet("color: #00FF00; font-size: 20px; font-weight: bold;")
                                    self.lbl_genel_toplam.setAlignment(Qt.AlignmentFlag.AlignRight)
                                    maliyet_grid.addWidget(self.lbl_genel_toplam, row, 1)

                                    tab_maliyet_layout.addWidget(maliyet_frame)

                                    # Not
                                    not_label = QLabel(
                                    "Not: Yapistirici fiyati 180 TL/torba (25kg), Derz fiyati 120 TL/torba (20kg) olarak hesaplanmistir.\n"
                                    "Gercek fiyatlar degiskenlik gosterebilir."
                                    )
                                    not_label.setStyleSheet("color: #888; font-size: 10px;")
                                    tab_maliyet_layout.addWidget(not_label)

                                    tab_maliyet_layout.addStretch()

                                    self.tab_widget.addTab(tab_maliyet, "Maliyet")

                                    layout.addWidget(self.tab_widget)

                                    # Metraya Aktar butonu
                                    btn_metraya_aktar = QPushButton(" Metraya Aktar")
                                    btn_metraya_aktar.setStyleSheet("background-color: #FF6600; color: white; font-weight: bold; padding: 8px;")
                                    btn_metraya_aktar.clicked.connect(self._metraya_aktar)
                                    layout.addWidget(btn_metraya_aktar)

                                    return widget

                                    def _label(self, text: str) -> QLabel:
                                        """Normal etiket"""
                                        label = QLabel(text)
                                        label.setStyleSheet("color: #e0e0e0;")
                                        return label

                                        def _value_label(self, text: str, color: str = "#FFFFFF") -> QLabel:
                                            """Deger etiketi"""
                                            label = QLabel(text)
                                            label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")
                                            label.setAlignment(Qt.AlignmentFlag.AlignRight)
                                            return label

                                            def _create_separator(self, color: str = "#00BFFF") -> QFrame:
                                                """Ayirici cizgi"""
                                                line = QFrame()
                                                line.setFrameShape(QFrame.Shape.HLine)
                                                line.setStyleSheet(f"background-color: {color};")
                                                line.setFixedHeight(1)
                                                return line

                                                def _manuel_toggled(self, checked):
                                                    """Manuel secenegi toggle edildginde"""
                                                    self.spin_manuel_hiz.setEnabled(checked)

                                                    def _fayans_ebat_degisti(self, index):
                                                        """Fayans ebadi degistiginde manuel degerlerini guncelle"""
                                                        data = self.combo_fayans_ebat.currentData()
                                                        if data:
                                                            self.spin_fayans_en.setValue(data["en"])
                                                            self.spin_fayans_boy.setValue(data["boy"])

                                                            def _alan_guncelle(self):
                                                                """Hesaplanan alani guncelle"""
                                                                en_cm = self.spin_oda_en.value()
                                                                boy_cm = self.spin_oda_boy.value()
                                                                alan_m2 = (en_cm * boy_cm) / 10000
                                                                self.lbl_hesaplanan_alan.setText(f"Hesaplanan Alan: {alan_m2:.2f} m2")

                                                                def oda_ekle(self):
                                                                    """Odayi listeye ekle"""
                                                                    oda_adi = self.txt_oda_adi.text().strip()
                                                                    if not oda_adi:
                                                                        oda_adi = f"Oda {len(self.odalar) + 1}"

                                                                        oda = {
                                                                        "oda_adi": oda_adi,
                                                                        "en_cm": self.spin_oda_en.value(),
                                                                        "boy_cm": self.spin_oda_boy.value(),
                                                                        "fayans_en_cm": self.spin_fayans_en.value(),
                                                                        "fayans_boy_cm": self.spin_fayans_boy.value(),
                                                                        "oda_turu": self.combo_oda_turu.currentData()
                                                                        }

                                                                        self.odalar.append(oda)
                                                                        self._oda_tablosunu_guncelle()
                                                                        self.formu_temizle()

                                                                        logger.info(f"Oda eklendi: {oda_adi}")

                                                                        def formu_temizle(self):
                                                                            """Oda ekleme formunu temizle"""
                                                                            self.txt_oda_adi.clear()
                                                                            self.spin_oda_en.setValue(400)
                                                                            self.spin_oda_boy.setValue(500)
                                                                            self.combo_fayans_ebat.setCurrentIndex(8)
                                                                            self.combo_oda_turu.setCurrentIndex(0)

                                                                            def _oda_tablosunu_guncelle(self):
                                                                                """Oda tablosunu guncelle"""
                                                                                self.tbl_odalar.setRowCount(len(self.odalar))

                                                                                toplam_alan = 0.0

                                                                                for i, oda in enumerate(self.odalar):
                                                                                    alan = (oda["en_cm"] * oda["boy_cm"]) / 10000
                                                                                    toplam_alan += alan

                                                                                    self.tbl_odalar.setItem(i, 0, QTableWidgetItem(oda["oda_adi"]))
                                                                                    self.tbl_odalar.setItem(i, 1, QTableWidgetItem(f"{oda['en_cm']}x{oda['boy_cm']}"))
                                                                                    self.tbl_odalar.setItem(i, 2, QTableWidgetItem(f"{oda['fayans_en_cm']}x{oda['fayans_boy_cm']}"))

                                                                                    tur_text = "Kuru" if oda["oda_turu"] == "kuru_zemin" else "Islak"
                                                                                    self.tbl_odalar.setItem(i, 3, QTableWidgetItem(tur_text))
                                                                                    self.tbl_odalar.setItem(i, 4, QTableWidgetItem(f"{alan:.2f}"))

                                                                                    # Sil butonu
                                                                                    btn_sil = QPushButton("X")
                                                                                    btn_sil.setStyleSheet("""
                                                                                    QPushButton {
                                                                                    background-color: #AA0000;
                                                                                    color: white;
                                                                                    border: none;
                                                                                    padding: 2px 8px;
                                                                                    border-radius: 3px;
                                                                                    }
                                                                                    QPushButton:hover {
                                                                                    background-color: #CC0000;
                                                                                    }
                                                                                    """)
                                                                                    btn_sil.clicked.connect(lambda checked, idx=i: self.oda_sil(idx))
                                                                                    self.tbl_odalar.setCellWidget(i, 5, btn_sil)

                                                                                    self.lbl_toplam_oda.setText(f"Toplam: {len(self.odalar)} oda, {toplam_alan:.2f} m2")

                                                                                    def oda_sil(self, index: int):
                                                                                        """Odayi listeden sil"""
                                                                                        if 0 <= index < len(self.odalar):
                                                                                            silinen = self.odalar.pop(index)
                                                                                            self._oda_tablosunu_guncelle()
                                                                                            logger.info(f"Oda silindi: {silinen['oda_adi']}")

                                                                                            def tum_odalari_temizle(self):
                                                                                                """Tum odalari temizle"""
                                                                                                if self.odalar:
                                                                                                    reply = QMessageBox.question(
                                                                                                    self, "Onay",
                                                                                                    "Tum odalar silinecek. Emin misiniz?",
                                                                                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                                                                                    )
                                                                                                    if reply == QMessageBox.StandardButton.Yes:
                                                                                                        self.odalar.clear()
                                                                                                        self._oda_tablosunu_guncelle()
                                                                                                        logger.info("Tum odalar temizlendi")

                                                                                                        def hesapla(self):
                                                                                                            """Hesaplama yap"""
                                                                                                            if not self.odalar:
                                                                                                                QMessageBox.warning(self, "Uyari", "Lutfen en az bir oda ekleyin!")
                                                                                                                return

                                                                                                                try:
                                                                                                                    # Parametreleri al
                                                                                                                    kutu_m2 = self.spin_kutu_m2.value()
                                                                                                                    fayans_fiyat = self.spin_fayans_fiyat.value()
                                                                                                                    ekip_ucret = self.spin_ekip_ucret.value()

                                                                                                                    verim_kaynagi = "piyasa" if self.radio_piyasa.isChecked() else "manuel"
                                                                                                                    manuel_hiz = self.spin_manuel_hiz.value() if verim_kaynagi == "manuel" else None

                                                                                                                    # Hesaplama yap
                                                                                                                    sonuc = hesapla_fayans_oda_detayli(
                                                                                                                    odalar_listesi=self.odalar,
                                                                                                                    fayans_kutu_m2=kutu_m2,
                                                                                                                    fayans_m2_fiyat=fayans_fiyat,
                                                                                                                    ekip_gunluk_ucret=ekip_ucret,
                                                                                                                    verim_kaynagi=verim_kaynagi,
                                                                                                                    manuel_verim_m2_gun=manuel_hiz
                                                                                                                    )

                                                                                                                    self.son_sonuc = sonuc
                                                                                                                    self.son_hesaplama = sonuc
                                                                                                                    self._sonuclari_goster(sonuc)

                                                                                                                    logger.info(f"Hesaplama tamamlandi: {len(self.odalar)} oda, {sonuc['toplam_net_alan_m2']} m2")

                                                                                                                except Exception as e:
                                                                                                                    logger.error(f"Hesaplama hatasi: {e}")
                                                                                                                    QMessageBox.critical(self, "Hata", f"Hesaplama sirasinda hata:\n{str(e)}")

                                                                                                                    def _sonuclari_goster(self, sonuc: dict):
                                                                                                                        """Sonuclari arayuzde goster"""
                                                                                                                        # Oda detaylari tablosu
                                                                                                                        oda_detaylari = sonuc["oda_detaylari"]
                                                                                                                        self.tbl_sonuclar.setRowCount(len(oda_detaylari))

                                                                                                                        for i, oda in enumerate(oda_detaylari):
                                                                                                                            self.tbl_sonuclar.setItem(i, 0, QTableWidgetItem(oda["oda_adi"]))
                                                                                                                            self.tbl_sonuclar.setItem(i, 1, QTableWidgetItem(f"{oda['net_alan_m2']:.2f}"))
                                                                                                                            self.tbl_sonuclar.setItem(i, 2, QTableWidgetItem(f"{oda['brut_alan_m2']:.2f}"))
                                                                                                                            self.tbl_sonuclar.setItem(i, 3, QTableWidgetItem(f"{oda['satir_sayisi']}x{oda['sutun_sayisi']}"))
                                                                                                                            self.tbl_sonuclar.setItem(i, 4, QTableWidgetItem(str(oda["gereken_fayans_adet"])))

                                                                                                                            # Fire orani - yuksekse kirmizi
                                                                                                                            fire_item = QTableWidgetItem(f"{oda['fire_orani_yuzde']:.1f}%")
                                                                                                                            if oda["fire_orani_yuzde"] > 15:
                                                                                                                                fire_item.setForeground(QColor("#FF6B6B"))
                                                                                                                            elif oda["fire_orani_yuzde"] > 10:
                                                                                                                                fire_item.setForeground(QColor("#FFD700"))
                                                                                                                            else:
                                                                                                                                fire_item.setForeground(QColor("#00FF00"))
                                                                                                                                self.tbl_sonuclar.setItem(i, 5, fire_item)

                                                                                                                                # Optimal yon
                                                                                                                                yon_text = "Normal" if oda["optimal_yon"] == "normal" else "90 Donuk"
                                                                                                                                if oda["tasarruf_adet"] > 0:
                                                                                                                                    yon_text += f" ({oda['tasarruf_adet']} tasarruf)"
                                                                                                                                    self.tbl_sonuclar.setItem(i, 6, QTableWidgetItem(yon_text))

                                                                                                                                    self.tbl_sonuclar.setItem(i, 7, QTableWidgetItem(f"{oda['yapistirici_kg']:.1f}"))
                                                                                                                                    self.tbl_sonuclar.setItem(i, 8, QTableWidgetItem(f"{oda['derz_kg']:.1f}"))
                                                                                                                                    self.tbl_sonuclar.setItem(i, 9, QTableWidgetItem(f"{oda['gunluk_verim_m2']:.0f}"))
                                                                                                                                    self.tbl_sonuclar.setItem(i, 10, QTableWidgetItem(f"{oda['tahmini_sure_gun']:.1f}"))

                                                                                                                                    # Ozet bilgileri
                                                                                                                                    self.lbl_net_alan.setText(f"{sonuc['toplam_net_alan_m2']:.2f} m2")
                                                                                                                                    self.lbl_brut_alan.setText(f"{sonuc['toplam_brut_alan_m2']:.2f} m2")
                                                                                                                                    self.lbl_fire.setText(f"{sonuc['hesaplanan_ortalama_fire_yuzdesi']:.1f}%")

                                                                                                                                    self.lbl_fayans_adet.setText(f"{sonuc['toplam_gereken_fayans_adet']:,} adet")
                                                                                                                                    self.lbl_kutu.setText(f"{sonuc['toplam_gereken_kutu']} kutu")

                                                                                                                                    self.lbl_yapistirici.setText(
                                                                                                                                    f"{sonuc['toplam_yapistirici_kg']:.1f} kg ({sonuc['toplam_yapistirici_torba']} torba x 25kg)"
                                                                                                                                    )
                                                                                                                                    self.lbl_derz.setText(
                                                                                                                                    f"{sonuc['toplam_derz_kg']:.1f} kg ({sonuc['toplam_derz_torba']} torba x 20kg)"
                                                                                                                                    )

                                                                                                                                    self.lbl_sure.setText(f"{sonuc['tahmini_toplam_sure_gun']} gun")

                                                                                                                                    # Maliyet bilgileri
                                                                                                                                    m = sonuc["maliyet_ozeti"]
                                                                                                                                    self.lbl_fayans_maliyet.setText(f"{m['fayans_maliyeti']:,.2f} TL")
                                                                                                                                    self.lbl_yapistirici_maliyet.setText(f"{m['yapistirici_maliyeti']:,.2f} TL")
                                                                                                                                    self.lbl_derz_maliyet.setText(f"{m['derz_maliyeti']:,.2f} TL")
                                                                                                                                    self.lbl_malzeme_toplam.setText(f"{m['toplam_malzeme_maliyeti']:,.2f} TL")
                                                                                                                                    self.lbl_iscilik_maliyet.setText(f"{m['iscilik_maliyeti']:,.2f} TL")
                                                                                                                                    self.lbl_genel_toplam.setText(f"{m['genel_toplam']:,.2f} TL")

                                                                                                                                    # Sonuc sekmesine gec
                                                                                                                                    self.tab_widget.setCurrentIndex(0)

                                                                                                                                    def _metraya_aktar(self):
                                                                                                                                        """Hesaplama sonucunu metraj listesine aktar"""
                                                                                                                                        if self.son_hesaplama is None:
                                                                                                                                            from PyQt6.QtWidgets import QMessageBox
                                                                                                                                            QMessageBox.warning(self, "Uyarı", "Önce bir hesaplama yapın!")
                                                                                                                                            return
                                                                                                                                            self.hesaplama_tamamlandi.emit(self.son_hesaplama)
