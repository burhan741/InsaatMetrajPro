"""
Laminat Parke ve Supurgelik Maliyet Hesaplama Penceresi
Oda bazli parke, supurgelik ve silte hesabi - Kapi dusumlu
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView,
    QFormLayout, QMessageBox, QFrame, QGridLayout, QLineEdit,
    QRadioButton, QButtonGroup, QScrollArea, QSplitter, QTabWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
import logging

from app.core.parke_hesaplama import (
    hesapla_parke_supurgelik_detayli,
    STANDART_PARKE_KUTULARI,
    STANDART_SUPURGELIK_BOYLARI,
    VERIMLILIK_VERITABANI
)

logger = logging.getLogger(__name__)


class ParkeMaliyetWindow(QMainWindow):
    """Laminat parke ve supurgelik maliyet hesaplama penceresi"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.odalar = []  # Oda listesi
        self.son_sonuc = None
        self.init_ui()

    def init_ui(self):
        """Arayuzu olustur"""
        self.setWindowTitle("Laminat Parke ve Supurgelik Hesaplama")
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

        # Scroll area
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
                background-color: #8B4513;
                color: #FFF;
                border: 2px solid #654321;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #A0522D;
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
                background-color: #1a1a1a;
            }
            QWidget {
                background-color: #1a1a1a;
            }
            QLabel {
                color: #e0e0e0;
            }
            QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #8B4513;
                padding: 5px;
                border-radius: 4px;
                min-height: 25px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #e0e0e0;
                selection-background-color: #8B4513;
            }
            QPushButton {
                background-color: #8B4513;
                color: #FFF;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #A0522D;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
            }
            QGroupBox {
                color: #DEB887;
                border: 2px solid #8B4513;
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
                background-color: #8B4513;
                border: 2px solid #DEB887;
                border-radius: 8px;
            }
            QRadioButton::indicator:unchecked {
                background-color: #2d2d2d;
                border: 2px solid #8B4513;
                border-radius: 8px;
            }
            QTableWidget {
                background-color: #252525;
                color: #e0e0e0;
                border: 2px solid #8B4513;
                border-radius: 6px;
                gridline-color: #3d3d3d;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #8B4513;
                color: #FFF;
            }
            QHeaderView::section {
                background-color: #3d2d1d;
                color: #FFF;
                padding: 6px;
                border: 1px solid #8B4513;
                font-weight: bold;
            }
            QScrollArea {
                border: none;
            }
            QTabWidget::pane {
                border: 2px solid #8B4513;
                border-radius: 6px;
                background-color: #252525;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #e0e0e0;
                padding: 8px 16px;
                border: 1px solid #8B4513;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #8B4513;
                color: #FFF;
                font-weight: bold;
            }
        """)

    def _create_parameter_panel(self) -> QGroupBox:
        """Parametre panelini olustur"""
        panel = QGroupBox("Genel Parametreler")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Parke kutu m2
        kutu_layout = QHBoxLayout()
        self.combo_parke_kutu = QComboBox()
        for kutu in STANDART_PARKE_KUTULARI:
            self.combo_parke_kutu.addItem(kutu["ad"], kutu["m2"])
        self.combo_parke_kutu.currentIndexChanged.connect(self._parke_kutu_degisti)
        kutu_layout.addWidget(self.combo_parke_kutu)

        self.spin_parke_kutu_m2 = QDoubleSpinBox()
        self.spin_parke_kutu_m2.setRange(0.5, 5)
        self.spin_parke_kutu_m2.setValue(1.84)
        self.spin_parke_kutu_m2.setSuffix(" m2")
        self.spin_parke_kutu_m2.setDecimals(2)
        kutu_layout.addWidget(self.spin_parke_kutu_m2)
        layout.addRow("Parke Kutu:", kutu_layout)

        # Parke kutu fiyati
        self.spin_parke_fiyat = QDoubleSpinBox()
        self.spin_parke_fiyat.setRange(0, 10000)
        self.spin_parke_fiyat.setValue(850)
        self.spin_parke_fiyat.setSuffix(" TL/kutu")
        self.spin_parke_fiyat.setDecimals(0)
        layout.addRow("Parke Fiyati:", self.spin_parke_fiyat)

        # Supurgelik boy uzunlugu
        sup_layout = QHBoxLayout()
        self.combo_supurgelik_boy = QComboBox()
        for boy in STANDART_SUPURGELIK_BOYLARI:
            self.combo_supurgelik_boy.addItem(boy["ad"], boy["cm"])
        self.combo_supurgelik_boy.setCurrentIndex(2)  # 280 cm varsayilan
        self.combo_supurgelik_boy.currentIndexChanged.connect(self._supurgelik_boy_degisti)
        sup_layout.addWidget(self.combo_supurgelik_boy)

        self.spin_supurgelik_boy = QDoubleSpinBox()
        self.spin_supurgelik_boy.setRange(100, 400)
        self.spin_supurgelik_boy.setValue(280)
        self.spin_supurgelik_boy.setSuffix(" cm")
        self.spin_supurgelik_boy.setDecimals(0)
        sup_layout.addWidget(self.spin_supurgelik_boy)
        layout.addRow("Supurgelik Boy:", sup_layout)

        # Supurgelik boy fiyati
        self.spin_supurgelik_fiyat = QDoubleSpinBox()
        self.spin_supurgelik_fiyat.setRange(0, 1000)
        self.spin_supurgelik_fiyat.setValue(120)
        self.spin_supurgelik_fiyat.setSuffix(" TL/boy")
        self.spin_supurgelik_fiyat.setDecimals(0)
        layout.addRow("Supurgelik Fiyati:", self.spin_supurgelik_fiyat)

        # Silte m2 fiyati
        self.spin_silte_fiyat = QDoubleSpinBox()
        self.spin_silte_fiyat.setRange(0, 500)
        self.spin_silte_fiyat.setValue(25)
        self.spin_silte_fiyat.setSuffix(" TL/m2")
        self.spin_silte_fiyat.setDecimals(0)
        layout.addRow("Silte (Kapron) Fiyati:", self.spin_silte_fiyat)

        # Ekip gunluk ucret
        self.spin_ekip_ucret = QDoubleSpinBox()
        self.spin_ekip_ucret.setRange(0, 50000)
        self.spin_ekip_ucret.setValue(3500)
        self.spin_ekip_ucret.setSuffix(" TL/gun")
        self.spin_ekip_ucret.setDecimals(0)
        layout.addRow("Ekip Gunluk Ucret:", self.spin_ekip_ucret)

        ekip_aciklama = QLabel("(1 Usta + 1 Yardimci)")
        ekip_aciklama.setStyleSheet("color: #888; font-size: 10px;")
        layout.addRow("", ekip_aciklama)

        # Fire orani
        self.spin_fire = QDoubleSpinBox()
        self.spin_fire.setRange(0, 20)
        self.spin_fire.setValue(5)
        self.spin_fire.setSuffix(" %")
        self.spin_fire.setDecimals(1)
        layout.addRow("Parke Fire Orani:", self.spin_fire)

        fire_info = QLabel("(Supurgelik +%7 gonye firesi otomatik eklenir)")
        fire_info.setStyleSheet("color: #888; font-size: 10px;")
        layout.addRow("", fire_info)

        # Verimlilik kaynagi
        verim_group = QGroupBox("Iscilik Hizi")
        verim_layout = QVBoxLayout()

        self.verim_group = QButtonGroup(self)

        self.radio_piyasa = QRadioButton("Piyasa Ortalamasi (90 m2/gun)")
        self.radio_piyasa.setChecked(True)
        self.verim_group.addButton(self.radio_piyasa, 0)
        verim_layout.addWidget(self.radio_piyasa)

        self.radio_manuel = QRadioButton("Manuel")
        self.verim_group.addButton(self.radio_manuel, 1)
        self.radio_manuel.toggled.connect(self._manuel_toggled)
        verim_layout.addWidget(self.radio_manuel)

        manuel_layout = QHBoxLayout()
        manuel_layout.addSpacing(20)
        self.spin_manuel_hiz = QDoubleSpinBox()
        self.spin_manuel_hiz.setRange(20, 200)
        self.spin_manuel_hiz.setValue(90)
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
        self.spin_oda_en.valueChanged.connect(self._alan_guncelle)
        layout.addWidget(self.spin_oda_en, 1, 1)

        layout.addWidget(QLabel("Oda Boyu (cm):"), 2, 0)
        self.spin_oda_boy = QSpinBox()
        self.spin_oda_boy.setRange(50, 10000)
        self.spin_oda_boy.setValue(500)
        self.spin_oda_boy.setSuffix(" cm")
        self.spin_oda_boy.valueChanged.connect(self._alan_guncelle)
        layout.addWidget(self.spin_oda_boy, 2, 1)

        # Kapi sayisi
        layout.addWidget(QLabel("Kapi Sayisi:"), 3, 0)
        self.spin_kapi = QSpinBox()
        self.spin_kapi.setRange(0, 10)
        self.spin_kapi.setValue(1)
        self.spin_kapi.valueChanged.connect(self._alan_guncelle)
        layout.addWidget(self.spin_kapi, 3, 1)

        kapi_info = QLabel("(Supurgelik dusumu icin - her kapi 90 cm)")
        kapi_info.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(kapi_info, 4, 0, 1, 2)

        # Hesaplanan degerler
        self.lbl_hesaplanan = QLabel("Alan: 20.00 m2 | Cevre: 18.00 m | Net Sup: 17.10 m")
        self.lbl_hesaplanan.setStyleSheet("color: #DEB887; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.lbl_hesaplanan, 5, 0, 1, 2)
        self._alan_guncelle()

        # Butonlar
        btn_layout = QHBoxLayout()

        btn_ekle = QPushButton("ODA EKLE")
        btn_ekle.setStyleSheet("""
            QPushButton {
                background-color: #228B22;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #2E8B22;
            }
        """)
        btn_ekle.clicked.connect(self.oda_ekle)
        btn_layout.addWidget(btn_ekle)

        btn_temizle = QPushButton("Formu Temizle")
        btn_temizle.clicked.connect(self.formu_temizle)
        btn_layout.addWidget(btn_temizle)

        layout.addLayout(btn_layout, 6, 0, 1, 2)

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
            "Oda Adi", "Boyut (cm)", "Alan (m2)", "Cevre (m)", "Kapi", "Sil"
        ])
        self.tbl_odalar.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_odalar.setMaximumHeight(180)
        self.tbl_odalar.setAlternatingRowColors(True)
        layout.addWidget(self.tbl_odalar)

        # Toplam bilgi
        self.lbl_toplam_oda = QLabel("Toplam: 0 oda | 0.00 m2 | 0.00 m sup.")
        self.lbl_toplam_oda.setStyleSheet("color: #DEB887; font-weight: bold;")
        layout.addWidget(self.lbl_toplam_oda)

        # Tum odalari temizle butonu
        btn_tum_temizle = QPushButton("Tum Odalari Temizle")
        btn_tum_temizle.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
            }
            QPushButton:hover {
                background-color: #A52A2A;
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
        self.tbl_sonuclar.setColumnCount(8)
        self.tbl_sonuclar.setHorizontalHeaderLabels([
            "Oda", "Alan m2", "Fireli m2", "Cevre m", "Kapi Dus.", "Net Sup.", "Fireli Sup.", "Kapi"
        ])
        self.tbl_sonuclar.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_sonuclar.setAlternatingRowColors(True)
        tab_detay_layout.addWidget(self.tbl_sonuclar)

        self.tab_widget.addTab(tab_detay, "Oda Detaylari")

        # Tab 2: Ozet ve Siparis
        tab_ozet = self._create_ozet_tab()
        self.tab_widget.addTab(tab_ozet, "Ozet ve Siparis")

        # Tab 3: Maliyet
        tab_maliyet = self._create_maliyet_tab()
        self.tab_widget.addTab(tab_maliyet, "Maliyet")

        layout.addWidget(self.tab_widget)
        return widget

    def _create_ozet_tab(self) -> QWidget:
        """Ozet sekmesini olustur"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Ozet frame
        ozet_frame = QFrame()
        ozet_frame.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 2px solid #8B4513;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        ozet_grid = QGridLayout(ozet_frame)
        ozet_grid.setSpacing(12)

        row = 0

        # Baslik
        baslik = QLabel("SIPARIS OZETI")
        baslik.setStyleSheet("color: #DEB887; font-size: 16px; font-weight: bold;")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ozet_grid.addWidget(baslik, row, 0, 1, 2)
        row += 1

        ozet_grid.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # Parke bilgileri
        parke_baslik = QLabel("PARKE")
        parke_baslik.setStyleSheet("color: #CD853F; font-weight: bold;")
        ozet_grid.addWidget(parke_baslik, row, 0, 1, 2)
        row += 1

        ozet_grid.addWidget(self._label("Net Alan:"), row, 0)
        self.lbl_net_alan = self._value_label("- m2")
        ozet_grid.addWidget(self.lbl_net_alan, row, 1)
        row += 1

        ozet_grid.addWidget(self._label("Fireli Alan:"), row, 0)
        self.lbl_fireli_alan = self._value_label("- m2")
        ozet_grid.addWidget(self.lbl_fireli_alan, row, 1)
        row += 1

        ozet_grid.addWidget(self._label("Gereken Kutu:"), row, 0)
        self.lbl_parke_kutu = self._value_label("- kutu", "#CD853F")
        ozet_grid.addWidget(self.lbl_parke_kutu, row, 1)
        row += 1

        ozet_grid.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # Supurgelik bilgileri
        sup_baslik = QLabel("SUPURGELIK")
        sup_baslik.setStyleSheet("color: #D2691E; font-weight: bold;")
        ozet_grid.addWidget(sup_baslik, row, 0, 1, 2)
        row += 1

        ozet_grid.addWidget(self._label("Brut Cevre:"), row, 0)
        self.lbl_brut_cevre = self._value_label("- m")
        ozet_grid.addWidget(self.lbl_brut_cevre, row, 1)
        row += 1

        ozet_grid.addWidget(self._label("Kapi Dusumu:"), row, 0)
        self.lbl_kapi_dusumu = self._value_label("- m")
        ozet_grid.addWidget(self.lbl_kapi_dusumu, row, 1)
        row += 1

        ozet_grid.addWidget(self._label("Net Supurgelik:"), row, 0)
        self.lbl_net_sup = self._value_label("- m")
        ozet_grid.addWidget(self.lbl_net_sup, row, 1)
        row += 1

        ozet_grid.addWidget(self._label("Fireli (+%7 gonye):"), row, 0)
        self.lbl_fireli_sup = self._value_label("- m")
        ozet_grid.addWidget(self.lbl_fireli_sup, row, 1)
        row += 1

        ozet_grid.addWidget(self._label("Gereken Boy:"), row, 0)
        self.lbl_sup_boy = self._value_label("- boy", "#D2691E")
        ozet_grid.addWidget(self.lbl_sup_boy, row, 1)
        row += 1

        ozet_grid.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # Silte
        ozet_grid.addWidget(self._label("Silte (Kapron):"), row, 0)
        self.lbl_silte = self._value_label("- m2")
        ozet_grid.addWidget(self.lbl_silte, row, 1)
        row += 1

        ozet_grid.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # Sure
        ozet_grid.addWidget(self._label("Tahmini Sure:"), row, 0)
        self.lbl_sure = self._value_label("- gun", "#DEB887")
        ozet_grid.addWidget(self.lbl_sure, row, 1)

        layout.addWidget(ozet_frame)
        layout.addStretch()
        return widget

    def _create_maliyet_tab(self) -> QWidget:
        """Maliyet sekmesini olustur"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        maliyet_frame = QFrame()
        maliyet_frame.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 2px solid #228B22;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        maliyet_grid = QGridLayout(maliyet_frame)
        maliyet_grid.setSpacing(12)

        row = 0

        # Baslik
        baslik = QLabel("MALIYET OZETI")
        baslik.setStyleSheet("color: #228B22; font-size: 16px; font-weight: bold;")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        maliyet_grid.addWidget(baslik, row, 0, 1, 2)
        row += 1

        maliyet_grid.addWidget(self._create_separator("#228B22"), row, 0, 1, 2)
        row += 1

        # Malzeme maliyetleri
        maliyet_grid.addWidget(self._label("Parke Maliyeti:"), row, 0)
        self.lbl_parke_maliyet = self._value_label("- TL")
        maliyet_grid.addWidget(self.lbl_parke_maliyet, row, 1)
        row += 1

        maliyet_grid.addWidget(self._label("Supurgelik Maliyeti:"), row, 0)
        self.lbl_sup_maliyet = self._value_label("- TL")
        maliyet_grid.addWidget(self.lbl_sup_maliyet, row, 1)
        row += 1

        maliyet_grid.addWidget(self._label("Silte Maliyeti:"), row, 0)
        self.lbl_silte_maliyet = self._value_label("- TL")
        maliyet_grid.addWidget(self.lbl_silte_maliyet, row, 1)
        row += 1

        maliyet_grid.addWidget(self._create_separator("#228B22"), row, 0, 1, 2)
        row += 1

        maliyet_grid.addWidget(self._label("Toplam Malzeme:"), row, 0)
        self.lbl_malzeme_toplam = self._value_label("- TL", "#DEB887")
        maliyet_grid.addWidget(self.lbl_malzeme_toplam, row, 1)
        row += 1

        maliyet_grid.addWidget(self._label("Iscilik Maliyeti:"), row, 0)
        self.lbl_iscilik = self._value_label("- TL", "#DEB887")
        maliyet_grid.addWidget(self.lbl_iscilik, row, 1)
        row += 1

        maliyet_grid.addWidget(self._create_separator("#228B22"), row, 0, 1, 2)
        row += 1

        # Genel toplam
        toplam_label = QLabel("GENEL TOPLAM:")
        toplam_label.setStyleSheet("color: #228B22; font-size: 14px; font-weight: bold;")
        maliyet_grid.addWidget(toplam_label, row, 0)

        self.lbl_genel_toplam = QLabel("- TL")
        self.lbl_genel_toplam.setStyleSheet("color: #228B22; font-size: 18px; font-weight: bold;")
        self.lbl_genel_toplam.setAlignment(Qt.AlignmentFlag.AlignRight)
        maliyet_grid.addWidget(self.lbl_genel_toplam, row, 1)
        row += 1

        # Birim maliyet
        maliyet_grid.addWidget(self._label("Birim Maliyet:"), row, 0)
        self.lbl_birim = self._value_label("- TL/m2")
        maliyet_grid.addWidget(self.lbl_birim, row, 1)

        layout.addWidget(maliyet_frame)
        layout.addStretch()
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

    def _create_separator(self, color: str = "#8B4513") -> QFrame:
        """Ayirici cizgi"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {color};")
        line.setFixedHeight(1)
        return line

    def _parke_kutu_degisti(self, index):
        """Parke kutu secimi degistiginde"""
        m2 = self.combo_parke_kutu.currentData()
        if m2:
            self.spin_parke_kutu_m2.setValue(m2)

    def _supurgelik_boy_degisti(self, index):
        """Supurgelik boy secimi degistiginde"""
        cm = self.combo_supurgelik_boy.currentData()
        if cm:
            self.spin_supurgelik_boy.setValue(cm)

    def _manuel_toggled(self, checked):
        """Manuel verim toggled"""
        self.spin_manuel_hiz.setEnabled(checked)

    def _alan_guncelle(self):
        """Hesaplanan degerleri guncelle"""
        en_cm = self.spin_oda_en.value()
        boy_cm = self.spin_oda_boy.value()
        kapi = self.spin_kapi.value()

        alan_m2 = (en_cm * boy_cm) / 10000
        cevre_m = 2 * (en_cm + boy_cm) / 100
        kapi_dusumu = kapi * 0.9
        net_sup = cevre_m - kapi_dusumu

        self.lbl_hesaplanan.setText(
            f"Alan: {alan_m2:.2f} m2 | Cevre: {cevre_m:.2f} m | Net Sup: {net_sup:.2f} m"
        )

    def oda_ekle(self):
        """Odayi listeye ekle"""
        oda_adi = self.txt_oda_adi.text().strip()
        if not oda_adi:
            oda_adi = f"Oda {len(self.odalar) + 1}"

        oda = {
            "oda_adi": oda_adi,
            "en_cm": self.spin_oda_en.value(),
            "boy_cm": self.spin_oda_boy.value(),
            "kapi_sayisi": self.spin_kapi.value()
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
        self.spin_kapi.setValue(1)

    def _oda_tablosunu_guncelle(self):
        """Oda tablosunu guncelle"""
        self.tbl_odalar.setRowCount(len(self.odalar))

        toplam_alan = 0.0
        toplam_cevre = 0.0
        toplam_kapi_dusumu = 0.0

        for i, oda in enumerate(self.odalar):
            alan = (oda["en_cm"] * oda["boy_cm"]) / 10000
            cevre = 2 * (oda["en_cm"] + oda["boy_cm"]) / 100
            kapi_dusumu = oda["kapi_sayisi"] * 0.9

            toplam_alan += alan
            toplam_cevre += cevre
            toplam_kapi_dusumu += kapi_dusumu

            self.tbl_odalar.setItem(i, 0, QTableWidgetItem(oda["oda_adi"]))
            self.tbl_odalar.setItem(i, 1, QTableWidgetItem(f"{oda['en_cm']}x{oda['boy_cm']}"))
            self.tbl_odalar.setItem(i, 2, QTableWidgetItem(f"{alan:.2f}"))
            self.tbl_odalar.setItem(i, 3, QTableWidgetItem(f"{cevre:.2f}"))
            self.tbl_odalar.setItem(i, 4, QTableWidgetItem(str(oda["kapi_sayisi"])))

            # Sil butonu
            btn_sil = QPushButton("X")
            btn_sil.setStyleSheet("""
                QPushButton {
                    background-color: #8B0000;
                    color: white;
                    border: none;
                    padding: 2px 8px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #A52A2A;
                }
            """)
            btn_sil.clicked.connect(lambda checked, idx=i: self.oda_sil(idx))
            self.tbl_odalar.setCellWidget(i, 5, btn_sil)

        net_sup = toplam_cevre - toplam_kapi_dusumu
        self.lbl_toplam_oda.setText(
            f"Toplam: {len(self.odalar)} oda | {toplam_alan:.2f} m2 | {net_sup:.2f} m sup."
        )

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
            verim_kaynagi = "piyasa" if self.radio_piyasa.isChecked() else "manuel"
            manuel_hiz = self.spin_manuel_hiz.value() if verim_kaynagi == "manuel" else None

            sonuc = hesapla_parke_supurgelik_detayli(
                odalar_listesi=self.odalar,
                parke_kutu_m2=self.spin_parke_kutu_m2.value(),
                supurgelik_boy_uzunlugu_cm=self.spin_supurgelik_boy.value(),
                parke_kutu_fiyat=self.spin_parke_fiyat.value(),
                supurgelik_boy_fiyat=self.spin_supurgelik_fiyat.value(),
                silte_m2_fiyat=self.spin_silte_fiyat.value(),
                ekip_gunluk_ucret=self.spin_ekip_ucret.value(),
                fire_orani=self.spin_fire.value() / 100,
                verim_kaynagi=verim_kaynagi,
                manuel_hiz=manuel_hiz
            )

            self.son_sonuc = sonuc
            self._sonuclari_goster(sonuc)
            self.tab_widget.setCurrentIndex(0)

            logger.info(f"Parke hesaplama tamamlandi: {sonuc['genel_toplam_maliyet_tl']:,.2f} TL")

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
            self.tbl_sonuclar.setItem(i, 2, QTableWidgetItem(f"{oda['fireli_alan_m2']:.2f}"))
            self.tbl_sonuclar.setItem(i, 3, QTableWidgetItem(f"{oda['brut_cevre_m']:.2f}"))
            self.tbl_sonuclar.setItem(i, 4, QTableWidgetItem(f"{oda['kapi_dusumu_m']:.2f}"))
            self.tbl_sonuclar.setItem(i, 5, QTableWidgetItem(f"{oda['net_supurgelik_m']:.2f}"))
            self.tbl_sonuclar.setItem(i, 6, QTableWidgetItem(f"{oda['fireli_supurgelik_m']:.2f}"))
            self.tbl_sonuclar.setItem(i, 7, QTableWidgetItem(str(oda["kapi_sayisi"])))

        # Ozet bilgileri
        self.lbl_net_alan.setText(f"{sonuc['toplam_net_alan_m2']:.2f} m2")
        self.lbl_fireli_alan.setText(f"{sonuc['toplam_fireli_alan_m2']:.2f} m2 (+%{sonuc['parke_fire_orani_yuzde']})")
        self.lbl_parke_kutu.setText(f"{sonuc['gereken_parke_kutu_adet']} kutu ({sonuc['parke_kutu_m2']} m2/kutu)")

        self.lbl_brut_cevre.setText(f"{sonuc['toplam_brut_cevre_m']:.2f} m")
        self.lbl_kapi_dusumu.setText(f"{sonuc['toplam_kapi_dusumu_m']:.2f} m")
        self.lbl_net_sup.setText(f"{sonuc['toplam_net_supurgelik_m']:.2f} m")
        self.lbl_fireli_sup.setText(f"{sonuc['toplam_fireli_supurgelik_m']:.2f} m")
        self.lbl_sup_boy.setText(f"{sonuc['gereken_supurgelik_boy_adet']} boy ({sonuc['supurgelik_boy_uzunlugu_cm']:.0f} cm/boy)")

        self.lbl_silte.setText(f"{sonuc['gereken_silte_m2']:.2f} m2")
        self.lbl_sure.setText(f"{sonuc['tahmini_sure_gun']} gun ({sonuc['kullanilan_hiz_m2_gun']} m2/gun)")

        # Maliyet bilgileri
        self.lbl_parke_maliyet.setText(f"{sonuc['toplam_parke_maliyet']:,.2f} TL")
        self.lbl_sup_maliyet.setText(f"{sonuc['toplam_supurgelik_maliyet']:,.2f} TL")
        self.lbl_silte_maliyet.setText(f"{sonuc['toplam_silte_maliyet']:,.2f} TL")
        self.lbl_malzeme_toplam.setText(f"{sonuc['toplam_malzeme_maliyet']:,.2f} TL")
        self.lbl_iscilik.setText(f"{sonuc['toplam_iscilik_tl']:,.2f} TL")
        self.lbl_genel_toplam.setText(f"{sonuc['genel_toplam_maliyet_tl']:,.2f} TL")
        self.lbl_birim.setText(f"{sonuc['birim_maliyet_m2']:.2f} TL/m2")
