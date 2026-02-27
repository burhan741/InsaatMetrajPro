"""
Sap (Tesviye Betonu) Maliyet Hesaplama Penceresi
Elle ve Makineli yontem karsilastirmali detayli maliyet analizi
"""

from PyQt6.QtWidgets import (
QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
QPushButton, QLabel, QComboBox, QDoubleSpinBox,
QGroupBox, QFormLayout, QMessageBox, QFrame, QGridLayout,
QRadioButton, QButtonGroup, QTabWidget, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import logging

from app.core.sap_hesaplama import (
hesapla_sap_maliyet_detayli,
karsilastir_yontemler,
VERIMLILIK_VERITABANI
)

logger = logging.getLogger(__name__)


class SapMaliyetWindow(QMainWindow):
    """Sap maliyet hesaplama penceresi"""

    hesaplama_tamamlandi = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.son_sonuc = None
        self.son_hesaplama = None
        self.init_ui()

        def init_ui(self):
            """Arayuzu olustur"""
            self.setWindowTitle("Sap (Tesviye Betonu) Maliyet Hesaplama")
            self.setGeometry(100, 100, 1100, 800)

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
                background-color: #0a0a1a;
                }
                QWidget {
                background-color: #0a0a1a;
                }
                QLabel {
                color: #e0e0e0;
                }
                QComboBox, QDoubleSpinBox {
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
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
                }
                QPushButton:hover {
                background-color: #00CCFF;
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
                QFrame#sonuc_frame {
                background-color: #0f1a2a;
                border: 2px solid #00FF00;
                border-radius: 8px;
                padding: 10px;
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

                def _create_input_panel(self) -> QWidget:
                    """Giris panelini olustur"""
                    scroll = QScrollArea()
                    scroll.setWidgetResizable(True)
                    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

                    container = QWidget()
                    layout = QVBoxLayout(container)
                    layout.setSpacing(15)

                    # === ALAN VE KALINLIK ===
                    alan_group = QGroupBox("1. Alan ve Kalinlik")
                    alan_layout = QFormLayout()

                    self.spin_alan = QDoubleSpinBox()
                    self.spin_alan.setRange(1, 100000)
                    self.spin_alan.setValue(100)
                    self.spin_alan.setSuffix(" m2")
                    self.spin_alan.setDecimals(1)
                    self.spin_alan.valueChanged.connect(self._hacim_guncelle)
                    alan_layout.addRow("Uygulama Alani:", self.spin_alan)

                    self.spin_kalinlik = QDoubleSpinBox()
                    self.spin_kalinlik.setRange(2, 20)
                    self.spin_kalinlik.setValue(5)
                    self.spin_kalinlik.setSuffix(" cm")
                    self.spin_kalinlik.setDecimals(1)
                    self.spin_kalinlik.valueChanged.connect(self._hacim_guncelle)
                    alan_layout.addRow("Ortalama Kalinlik:", self.spin_kalinlik)

                    # Hacim bilgisi
                    self.lbl_hacim = QLabel("Hesaplanan Hacim: 5.00 m3")
                    self.lbl_hacim.setStyleSheet("color: #FFD700; font-weight: bold;")
                    alan_layout.addRow("", self.lbl_hacim)

                    alan_group.setLayout(alan_layout)
                    layout.addWidget(alan_group)

                    # === UYGULAMA YONTEMI ===
                    yontem_group = QGroupBox("2. Uygulama Yontemi")
                    yontem_layout = QVBoxLayout()

                    self.yontem_group = QButtonGroup(self)

                    # Elle yontem
                    self.radio_elle = QRadioButton("Elle Kara Usulu (Manuel)")
                    self.radio_elle.setChecked(True)
                    self.yontem_group.addButton(self.radio_elle, 0)
                    yontem_layout.addWidget(self.radio_elle)

                    elle_aciklama = QLabel(" Harc yerde karilir, el arabasiyla tasinir, mastarlanir.")
                    elle_aciklama.setStyleSheet("color: #888; font-size: 10px;")
                    yontem_layout.addWidget(elle_aciklama)

                    elle_hiz = QLabel(" Hiz: 30-35 m2/gun (Yorucu, yas ortalaması yuksek ekip icin)")
                    elle_hiz.setStyleSheet("color: #FFA500; font-size: 10px;")
                    yontem_layout.addWidget(elle_hiz)

                    yontem_layout.addSpacing(10)

                    # Makineli yontem
                    self.radio_makineli = QRadioButton("Makineli Pompa + Helikopter Perdah")
                    self.yontem_group.addButton(self.radio_makineli, 1)
                    self.radio_makineli.toggled.connect(self._yontem_degisti)
                    yontem_layout.addWidget(self.radio_makineli)

                    makineli_aciklama = QLabel(" Harc pompalanir, usta yayar, helikopter perdahi yapilir.")
                    makineli_aciklama.setStyleSheet("color: #888; font-size: 10px;")
                    yontem_layout.addWidget(makineli_aciklama)

                    makineli_hiz = QLabel(" Hiz: 200-250 m2/gun (Hizli, verimli)")
                    makineli_hiz.setStyleSheet("color: #00FF00; font-size: 10px;")
                    yontem_layout.addWidget(makineli_hiz)

                    yontem_group.setLayout(yontem_layout)
                    layout.addWidget(yontem_group)

                    # === FIYATLAR ===
                    fiyat_group = QGroupBox("3. Fiyatlar")
                    fiyat_layout = QFormLayout()

                    self.spin_kum_fiyat = QDoubleSpinBox()
                    self.spin_kum_fiyat.setRange(0, 10000)
                    self.spin_kum_fiyat.setValue(450)
                    self.spin_kum_fiyat.setSuffix(" TL/m3")
                    self.spin_kum_fiyat.setDecimals(0)
                    fiyat_layout.addRow("Kum Fiyati:", self.spin_kum_fiyat)

                    self.spin_cimento_fiyat = QDoubleSpinBox()
                    self.spin_cimento_fiyat.setRange(0, 1000)
                    self.spin_cimento_fiyat.setValue(180)
                    self.spin_cimento_fiyat.setSuffix(" TL/torba (50kg)")
                    self.spin_cimento_fiyat.setDecimals(0)
                    fiyat_layout.addRow("Cimento Fiyati:", self.spin_cimento_fiyat)

                    self.spin_ekip_ucret = QDoubleSpinBox()
                    self.spin_ekip_ucret.setRange(0, 50000)
                    self.spin_ekip_ucret.setValue(4000)
                    self.spin_ekip_ucret.setSuffix(" TL/gun")
                    self.spin_ekip_ucret.setDecimals(0)
                    fiyat_layout.addRow("Ekip Gunluk Ucret:", self.spin_ekip_ucret)

                    ekip_aciklama = QLabel("(Tum ekip - Usta + Yardimcilar)")
                    ekip_aciklama.setStyleSheet("color: #888; font-size: 10px;")
                    fiyat_layout.addRow("", ekip_aciklama)

                    self.spin_pompa_kira = QDoubleSpinBox()
                    self.spin_pompa_kira.setRange(0, 50000)
                    self.spin_pompa_kira.setValue(3500)
                    self.spin_pompa_kira.setSuffix(" TL/gun")
                    self.spin_pompa_kira.setDecimals(0)
                    self.spin_pompa_kira.setEnabled(False) # Baslangicta devre disi
                    fiyat_layout.addRow("Pompa Gunluk Kira:", self.spin_pompa_kira)

                    self.spin_fire = QDoubleSpinBox()
                    self.spin_fire.setRange(0, 30)
                    self.spin_fire.setValue(5)
                    self.spin_fire.setSuffix(" %")
                    self.spin_fire.setDecimals(1)
                    fiyat_layout.addRow("Fire Orani:", self.spin_fire)

                    fiyat_group.setLayout(fiyat_layout)
                    layout.addWidget(fiyat_group)

                    # === VERIMLILIK KAYNAGI ===
                    verim_group = QGroupBox("4. Iscilik Hizi Kaynagi")
                    verim_layout = QVBoxLayout()

                    self.verim_group = QButtonGroup(self)

                    self.radio_piyasa = QRadioButton("Piyasa (Gercekci Degerler)")
                    self.radio_piyasa.setChecked(True)
                    self.verim_group.addButton(self.radio_piyasa, 0)
                    verim_layout.addWidget(self.radio_piyasa)

                    self.radio_csb = QRadioButton("CSB Resmi (Bakanlik Analizi)")
                    self.verim_group.addButton(self.radio_csb, 1)
                    verim_layout.addWidget(self.radio_csb)

                    self.radio_manuel = QRadioButton("Manuel (Kendi Hiziniz)")
                    self.verim_group.addButton(self.radio_manuel, 2)
                    self.radio_manuel.toggled.connect(self._manuel_toggled)
                    verim_layout.addWidget(self.radio_manuel)

                    manuel_layout = QHBoxLayout()
                    manuel_layout.addSpacing(20)
                    self.spin_manuel_hiz = QDoubleSpinBox()
                    self.spin_manuel_hiz.setRange(5, 500)
                    self.spin_manuel_hiz.setValue(35)
                    self.spin_manuel_hiz.setSuffix(" m2/gun")
                    self.spin_manuel_hiz.setEnabled(False)
                    manuel_layout.addWidget(QLabel("Hiz:"))
                    manuel_layout.addWidget(self.spin_manuel_hiz)
                    manuel_layout.addStretch()
                    verim_layout.addLayout(manuel_layout)

                    verim_group.setLayout(verim_layout)
                    layout.addWidget(verim_group)

                    # === BUTONLAR ===
                    btn_layout = QHBoxLayout()

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
                    btn_layout.addWidget(btn_hesapla)

                    btn_karsilastir = QPushButton("KARSILASTIR")
                    btn_karsilastir.setFixedHeight(50)
                    btn_karsilastir.setFont(QFont("Arial", 11, QFont.Weight.Bold))
                    btn_karsilastir.setStyleSheet("""
                    QPushButton {
                    background-color: #FFD700;
                    color: #000;
                    border: 2px solid #DAA520;
                    font-size: 12px;
                    }
                    QPushButton:hover {
                    background-color: #FFC000;
                    }
                    """)
                    btn_karsilastir.clicked.connect(self.karsilastir)
                    btn_layout.addWidget(btn_karsilastir)

                    layout.addLayout(btn_layout)

                    layout.addStretch()
                    scroll.setWidget(container)
                    return scroll

                    def _create_results_panel(self) -> QWidget:
                        """Sonuc panelini olustur"""
                        widget = QWidget()
                        layout = QVBoxLayout(widget)

                        # Tab widget
                        self.tab_widget = QTabWidget()

                        # Tab 1: Hesaplama Sonucu
                        tab_sonuc = self._create_sonuc_tab()
                        self.tab_widget.addTab(tab_sonuc, "Hesaplama Sonucu")

                        # Tab 2: Karsilastirma
                        tab_karsilastirma = self._create_karsilastirma_tab()
                        self.tab_widget.addTab(tab_karsilastirma, "Yontem Karsilastirma")

                        layout.addWidget(self.tab_widget)

                        # Metraya Aktar butonu
                        btn_metraya_aktar = QPushButton(" Metraya Aktar")
                        btn_metraya_aktar.setStyleSheet("background-color: #FF6600; color: white; font-weight: bold; padding: 8px;")
                        btn_metraya_aktar.clicked.connect(self._metraya_aktar)
                        layout.addWidget(btn_metraya_aktar)

                        return widget

                        def _create_sonuc_tab(self) -> QWidget:
                            """Sonuc sekmesini olustur"""
                            widget = QWidget()
                            layout = QVBoxLayout(widget)

                            # Sonuc frame
                            sonuc_frame = QFrame()
                            sonuc_frame.setObjectName("sonuc_frame")
                            sonuc_layout = QGridLayout(sonuc_frame)
                            sonuc_layout.setSpacing(10)

                            row = 0

                            # Baslik
                            baslik = QLabel("HESAPLAMA SONUCU")
                            baslik.setStyleSheet("color: #00BFFF; font-size: 16px; font-weight: bold;")
                            baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
                            sonuc_layout.addWidget(baslik, row, 0, 1, 2)
                            row += 1

                            sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
                            row += 1

                            # Uygulama bilgisi
                            sonuc_layout.addWidget(self._label("Uygulama Yontemi:"), row, 0)
                            self.lbl_yontem = self._value_label("- ")
                            sonuc_layout.addWidget(self.lbl_yontem, row, 1)
                            row += 1

                            sonuc_layout.addWidget(self._label("Kullanilan Hiz:"), row, 0)
                            self.lbl_hiz = self._value_label("- m2/gun")
                            sonuc_layout.addWidget(self.lbl_hiz, row, 1)
                            row += 1

                            sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
                            row += 1

                            # Hacim ve malzeme
                            malzeme_baslik = QLabel("MALZEME IHTIYACI")
                            malzeme_baslik.setStyleSheet("color: #00FF00; font-weight: bold;")
                            sonuc_layout.addWidget(malzeme_baslik, row, 0, 1, 2)
                            row += 1

                            sonuc_layout.addWidget(self._label("Dokulen Hacim:"), row, 0)
                            self.lbl_hacim_sonuc = self._value_label("- m3")
                            sonuc_layout.addWidget(self.lbl_hacim_sonuc, row, 1)
                            row += 1

                            sonuc_layout.addWidget(self._label("Gereken Kum:"), row, 0)
                            self.lbl_kum = self._value_label("- m3")
                            sonuc_layout.addWidget(self.lbl_kum, row, 1)
                            row += 1

                            sonuc_layout.addWidget(self._label("Gereken Cimento:"), row, 0)
                            self.lbl_cimento = self._value_label("- torba (50kg)")
                            sonuc_layout.addWidget(self.lbl_cimento, row, 1)
                            row += 1

                            sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
                            row += 1

                            # Sure
                            sonuc_layout.addWidget(self._label("Tahmini Is Suresi:"), row, 0)
                            self.lbl_sure = self._value_label("- gun", "#FFD700")
                            sonuc_layout.addWidget(self.lbl_sure, row, 1)
                            row += 1

                            sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
                            row += 1

                            # Maliyet detaylari
                            maliyet_baslik = QLabel("MALIYET DETAYI")
                            maliyet_baslik.setStyleSheet("color: #00BFFF; font-weight: bold;")
                            sonuc_layout.addWidget(maliyet_baslik, row, 0, 1, 2)
                            row += 1

                            sonuc_layout.addWidget(self._label("Kum Maliyeti:"), row, 0)
                            self.lbl_kum_maliyet = self._value_label("- TL")
                            sonuc_layout.addWidget(self.lbl_kum_maliyet, row, 1)
                            row += 1

                            sonuc_layout.addWidget(self._label("Cimento Maliyeti:"), row, 0)
                            self.lbl_cimento_maliyet = self._value_label("- TL")
                            sonuc_layout.addWidget(self.lbl_cimento_maliyet, row, 1)
                            row += 1

                            sonuc_layout.addWidget(self._label("Toplam Malzeme:"), row, 0)
                            self.lbl_malzeme_toplam = self._value_label("- TL", "#FFD700")
                            sonuc_layout.addWidget(self.lbl_malzeme_toplam, row, 1)
                            row += 1

                            sonuc_layout.addWidget(self._label("Iscilik Maliyeti:"), row, 0)
                            self.lbl_iscilik = self._value_label("- TL", "#FFD700")
                            sonuc_layout.addWidget(self.lbl_iscilik, row, 1)
                            row += 1

                            sonuc_layout.addWidget(self._label("Makine Kira:"), row, 0)
                            self.lbl_makine = self._value_label("- TL")
                            sonuc_layout.addWidget(self.lbl_makine, row, 1)
                            row += 1

                            sonuc_layout.addWidget(self._create_separator("#00FF00"), row, 0, 1, 2)
                            row += 1

                            # Genel toplam
                            toplam_label = QLabel("GENEL TOPLAM:")
                            toplam_label.setStyleSheet("color: #00FF00; font-size: 14px; font-weight: bold;")
                            sonuc_layout.addWidget(toplam_label, row, 0)

                            self.lbl_toplam = QLabel("- TL")
                            self.lbl_toplam.setStyleSheet("color: #00FF00; font-size: 18px; font-weight: bold;")
                            self.lbl_toplam.setAlignment(Qt.AlignmentFlag.AlignRight)
                            sonuc_layout.addWidget(self.lbl_toplam, row, 1)
                            row += 1

                            # Birim maliyet
                            sonuc_layout.addWidget(self._label("Birim Maliyet:"), row, 0)
                            self.lbl_birim = self._value_label("- TL/m2")
                            sonuc_layout.addWidget(self.lbl_birim, row, 1)

                            layout.addWidget(sonuc_frame)

                            # Bilgi notu
                            not_label = QLabel(
                            "Karisim: 300 Dozaj Sap (1 m3 icin 1.1 m3 kum + 7 torba cimento)"
                            )
                            not_label.setStyleSheet("color: #888; font-size: 10px;")
                            layout.addWidget(not_label)

                            layout.addStretch()
                            return widget

                            def _create_karsilastirma_tab(self) -> QWidget:
                                """Karsilastirma sekmesini olustur"""
                                widget = QWidget()
                                layout = QVBoxLayout(widget)

                                # Karsilastirma frame
                                kars_frame = QFrame()
                                kars_frame.setStyleSheet("""
                                QFrame {
                                background-color: #0f1a2a;
                                border: 2px solid #FFD700;
                                border-radius: 8px;
                                padding: 15px;
                                }
                                """)
                                kars_layout = QGridLayout(kars_frame)
                                kars_layout.setSpacing(12)

                                row = 0

                                # Baslik
                                baslik = QLabel("YONTEM KARSILASTIRMA")
                                baslik.setStyleSheet("color: #FFD700; font-size: 16px; font-weight: bold;")
                                baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
                                kars_layout.addWidget(baslik, row, 0, 1, 3)
                                row += 1

                                kars_layout.addWidget(self._create_separator("#FFD700"), row, 0, 1, 3)
                                row += 1

                                # Basliklar
                                kars_layout.addWidget(self._label(""), row, 0)
                                elle_baslik = QLabel("ELLE")
                                elle_baslik.setStyleSheet("color: #FFA500; font-weight: bold;")
                                elle_baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
                                kars_layout.addWidget(elle_baslik, row, 1)
                                makine_baslik = QLabel("MAKINELI")
                                makine_baslik.setStyleSheet("color: #00FF00; font-weight: bold;")
                                makine_baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
                                kars_layout.addWidget(makine_baslik, row, 2)
                                row += 1

                                # Sure
                                kars_layout.addWidget(self._label("Tahmini Sure:"), row, 0)
                                self.lbl_kars_elle_sure = self._value_label("- gun", "#FFA500")
                                kars_layout.addWidget(self.lbl_kars_elle_sure, row, 1)
                                self.lbl_kars_makine_sure = self._value_label("- gun", "#00FF00")
                                kars_layout.addWidget(self.lbl_kars_makine_sure, row, 2)
                                row += 1

                                # Iscilik
                                kars_layout.addWidget(self._label("Iscilik:"), row, 0)
                                self.lbl_kars_elle_iscilik = self._value_label("- TL", "#FFA500")
                                kars_layout.addWidget(self.lbl_kars_elle_iscilik, row, 1)
                                self.lbl_kars_makine_iscilik = self._value_label("- TL", "#00FF00")
                                kars_layout.addWidget(self.lbl_kars_makine_iscilik, row, 2)
                                row += 1

                                # Makine kira
                                kars_layout.addWidget(self._label("Makine Kira:"), row, 0)
                                self.lbl_kars_elle_makine = self._value_label("0 TL", "#FFA500")
                                kars_layout.addWidget(self.lbl_kars_elle_makine, row, 1)
                                self.lbl_kars_makine_makine = self._value_label("- TL", "#00FF00")
                                kars_layout.addWidget(self.lbl_kars_makine_makine, row, 2)
                                row += 1

                                # Malzeme
                                kars_layout.addWidget(self._label("Malzeme:"), row, 0)
                                self.lbl_kars_elle_malzeme = self._value_label("- TL", "#FFA500")
                                kars_layout.addWidget(self.lbl_kars_elle_malzeme, row, 1)
                                self.lbl_kars_makine_malzeme = self._value_label("- TL", "#00FF00")
                                kars_layout.addWidget(self.lbl_kars_makine_malzeme, row, 2)
                                row += 1

                                kars_layout.addWidget(self._create_separator("#FFD700"), row, 0, 1, 3)
                                row += 1

                                # Toplam
                                kars_layout.addWidget(self._label("TOPLAM:"), row, 0)
                                self.lbl_kars_elle_toplam = QLabel("- TL")
                                self.lbl_kars_elle_toplam.setStyleSheet("color: #FFA500; font-size: 14px; font-weight: bold;")
                                self.lbl_kars_elle_toplam.setAlignment(Qt.AlignmentFlag.AlignRight)
                                kars_layout.addWidget(self.lbl_kars_elle_toplam, row, 1)
                                self.lbl_kars_makine_toplam = QLabel("- TL")
                                self.lbl_kars_makine_toplam.setStyleSheet("color: #00FF00; font-size: 14px; font-weight: bold;")
                                self.lbl_kars_makine_toplam.setAlignment(Qt.AlignmentFlag.AlignRight)
                                kars_layout.addWidget(self.lbl_kars_makine_toplam, row, 2)
                                row += 1

                                kars_layout.addWidget(self._create_separator("#FFD700"), row, 0, 1, 3)
                                row += 1

                                # Tavsiye
                                tavsiye_baslik = QLabel("TAVSIYE")
                                tavsiye_baslik.setStyleSheet("color: #FFD700; font-weight: bold;")
                                kars_layout.addWidget(tavsiye_baslik, row, 0, 1, 3)
                                row += 1

                                self.lbl_tavsiye = QLabel("Henuz karsilastirma yapilmadi")
                                self.lbl_tavsiye.setStyleSheet("color: #e0e0e0; font-size: 11px;")
                                self.lbl_tavsiye.setWordWrap(True)
                                kars_layout.addWidget(self.lbl_tavsiye, row, 0, 1, 3)

                                layout.addWidget(kars_frame)
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

                                        def _create_separator(self, color: str = "#00BFFF") -> QFrame:
                                            """Ayirici cizgi"""
                                            line = QFrame()
                                            line.setFrameShape(QFrame.Shape.HLine)
                                            line.setStyleSheet(f"background-color: {color};")
                                            line.setFixedHeight(1)
                                            return line

                                            def _hacim_guncelle(self):
                                                """Hacim bilgisini guncelle"""
                                                alan = self.spin_alan.value()
                                                kalinlik = self.spin_kalinlik.value()
                                                hacim = alan * (kalinlik / 100)
                                                self.lbl_hacim.setText(f"Hesaplanan Hacim: {hacim:.2f} m3")

                                                def _yontem_degisti(self, checked):
                                                    """Yontem degistiginde pompa kirasini etkinlestir/devre disi birak"""
                                                    self.spin_pompa_kira.setEnabled(checked)

                                                    def _manuel_toggled(self, checked):
                                                        """Manuel verim toggled"""
                                                        self.spin_manuel_hiz.setEnabled(checked)

                                                        def _get_verim_kaynagi(self) -> str:
                                                            """Secili verim kaynagini dondur"""
                                                            if self.radio_piyasa.isChecked():
                                                                return 'piyasa'
                                                            elif self.radio_csb.isChecked():
                                                                return 'csb_resmi'
                                                            else:
                                                                return 'manuel'

                                                                def _get_uygulama_yontemi(self) -> str:
                                                                    """Secili uygulama yontemini dondur"""
                                                                    if self.radio_elle.isChecked():
                                                                        return 'elle_kara_usulu'
                                                                    else:
                                                                        return 'makineli_pompa_helikopter'

                                                                        def hesapla(self):
                                                                            """Hesaplama yap"""
                                                                            try:
                                                                                sonuc = hesapla_sap_maliyet_detayli(
                                                                                uygulama_alani_m2=self.spin_alan.value(),
                                                                                ortalama_kalinlik_cm=self.spin_kalinlik.value(),
                                                                                uygulama_yontemi=self._get_uygulama_yontemi(),
                                                                                kum_m3_fiyat=self.spin_kum_fiyat.value(),
                                                                                cimento_torba_fiyat=self.spin_cimento_fiyat.value(),
                                                                                ekip_gunluk_ucret=self.spin_ekip_ucret.value(),
                                                                                pompa_gunluk_kira=self.spin_pompa_kira.value(),
                                                                                fire_orani=self.spin_fire.value() / 100,
                                                                                verim_kaynagi=self._get_verim_kaynagi(),
                                                                                manuel_hiz=self.spin_manuel_hiz.value() if self.radio_manuel.isChecked() else None
                                                                                )

                                                                                self.son_sonuc = sonuc
                                                                                self.son_hesaplama = sonuc
                                                                                self._sonuclari_goster(sonuc)
                                                                                self.tab_widget.setCurrentIndex(0)

                                                                                logger.info(f"Sap hesaplama tamamlandi: {sonuc['genel_toplam_maliyet_tl']:,.2f} TL")

                                                                            except ValueError as e:
                                                                                QMessageBox.warning(self, "Uyari", str(e))
                                                                            except Exception as e:
                                                                                logger.error(f"Hesaplama hatasi: {e}")
                                                                                QMessageBox.critical(self, "Hata", f"Hesaplama sirasinda hata:\n{str(e)}")

                                                                                def karsilastir(self):
                                                                                    """Elle ve makineli yontemleri karsilastir"""
                                                                                    try:
                                                                                        sonuc = karsilastir_yontemler(
                                                                                        uygulama_alani_m2=self.spin_alan.value(),
                                                                                        ortalama_kalinlik_cm=self.spin_kalinlik.value(),
                                                                                        kum_m3_fiyat=self.spin_kum_fiyat.value(),
                                                                                        cimento_torba_fiyat=self.spin_cimento_fiyat.value(),
                                                                                        ekip_gunluk_ucret=self.spin_ekip_ucret.value(),
                                                                                        pompa_gunluk_kira=self.spin_pompa_kira.value(),
                                                                                        fire_orani=self.spin_fire.value() / 100
                                                                                        )

                                                                                        self._karsilastirma_goster(sonuc)
                                                                                        self.tab_widget.setCurrentIndex(1)

                                                                                        logger.info(f"Yontem karsilastirma tamamlandi: Tavsiye = {sonuc['tavsiye_edilen']}")

                                                                                    except Exception as e:
                                                                                        logger.error(f"Karsilastirma hatasi: {e}")
                                                                                        QMessageBox.critical(self, "Hata", f"Karsilastirma sirasinda hata:\n{str(e)}")

                                                                                        def _sonuclari_goster(self, sonuc: dict):
                                                                                            """Sonuclari arayuzde goster"""
                                                                                            # Yontem bilgisi
                                                                                            self.lbl_yontem.setText(sonuc['uygulama_turu'])
                                                                                            self.lbl_hiz.setText(f"{sonuc['kullanilan_hiz_m2_gun']} m2/gun")

                                                                                            # Hacim ve malzeme
                                                                                            self.lbl_hacim_sonuc.setText(f"{sonuc['dokulen_hacim_m3']} m3")
                                                                                            self.lbl_kum.setText(f"{sonuc['gereken_kum_m3']} m3")
                                                                                            self.lbl_cimento.setText(f"{sonuc['gereken_cimento_torba']} torba (50kg)")

                                                                                            # Sure
                                                                                            self.lbl_sure.setText(f"{sonuc['tahmini_sure_gun']} gun")

                                                                                            # Maliyetler
                                                                                            self.lbl_kum_maliyet.setText(f"{sonuc['kum_maliyet_tl']:,.2f} TL")
                                                                                            self.lbl_cimento_maliyet.setText(f"{sonuc['cimento_maliyet_tl']:,.2f} TL")
                                                                                            self.lbl_malzeme_toplam.setText(f"{sonuc['toplam_malzeme_tl']:,.2f} TL")
                                                                                            self.lbl_iscilik.setText(f"{sonuc['toplam_iscilik_tl']:,.2f} TL")

                                                                                            if sonuc['toplam_makine_kira_tl'] > 0:
                                                                                                self.lbl_makine.setText(f"{sonuc['toplam_makine_kira_tl']:,.2f} TL")
                                                                                            else:
                                                                                                self.lbl_makine.setText("0 TL (Elle yontem)")

                                                                                                # Toplam
                                                                                                self.lbl_toplam.setText(f"{sonuc['genel_toplam_maliyet_tl']:,.2f} TL")
                                                                                                self.lbl_birim.setText(f"{sonuc['birim_maliyet_m2']:.2f} TL/m2")

                                                                                                def _karsilastirma_goster(self, sonuc: dict):
                                                                                                    """Karsilastirma sonuclarini goster"""
                                                                                                    elle = sonuc['elle']
                                                                                                    makine = sonuc['makineli']

                                                                                                    # Elle sonuclar
                                                                                                    self.lbl_kars_elle_sure.setText(f"{elle['tahmini_sure_gun']} gun")
                                                                                                    self.lbl_kars_elle_iscilik.setText(f"{elle['toplam_iscilik_tl']:,.0f} TL")
                                                                                                    self.lbl_kars_elle_makine.setText("0 TL")
                                                                                                    self.lbl_kars_elle_malzeme.setText(f"{elle['toplam_malzeme_tl']:,.0f} TL")
                                                                                                    self.lbl_kars_elle_toplam.setText(f"{elle['genel_toplam_maliyet_tl']:,.0f} TL")

                                                                                                    # Makineli sonuclar
                                                                                                    self.lbl_kars_makine_sure.setText(f"{makine['tahmini_sure_gun']} gun")
                                                                                                    self.lbl_kars_makine_iscilik.setText(f"{makine['toplam_iscilik_tl']:,.0f} TL")
                                                                                                    self.lbl_kars_makine_makine.setText(f"{makine['toplam_makine_kira_tl']:,.0f} TL")
                                                                                                    self.lbl_kars_makine_malzeme.setText(f"{makine['toplam_malzeme_tl']:,.0f} TL")
                                                                                                    self.lbl_kars_makine_toplam.setText(f"{makine['genel_toplam_maliyet_tl']:,.0f} TL")

                                                                                                    # Tavsiye
                                                                                                    tavsiye_text = f"Tavsiye Edilen: {sonuc['tavsiye_edilen'].upper()}\n\n{sonuc['tavsiye_aciklama']}"
                                                                                                    self.lbl_tavsiye.setText(tavsiye_text)

                                                                                                    # Tavsiye edilen yontemi vurgula
                                                                                                    if sonuc['tavsiye_edilen'] == 'makineli':
                                                                                                        self.lbl_kars_makine_toplam.setStyleSheet("color: #00FF00; font-size: 16px; font-weight: bold; background-color: #003300; padding: 5px; border-radius: 4px;")
                                                                                                        self.lbl_kars_elle_toplam.setStyleSheet("color: #FFA500; font-size: 14px; font-weight: bold;")
                                                                                                    else:
                                                                                                        self.lbl_kars_elle_toplam.setStyleSheet("color: #FFA500; font-size: 16px; font-weight: bold; background-color: #332200; padding: 5px; border-radius: 4px;")
                                                                                                        self.lbl_kars_makine_toplam.setStyleSheet("color: #00FF00; font-size: 14px; font-weight: bold;")

                                                                                                        def _metraya_aktar(self):
                                                                                                            """Hesaplama sonucunu metraj listesine aktar"""
                                                                                                            if self.son_hesaplama is None:
                                                                                                                from PyQt6.QtWidgets import QMessageBox
                                                                                                                QMessageBox.warning(self, "Uyarı", "Önce bir hesaplama yapın!")
                                                                                                                return
                                                                                                                self.hesaplama_tamamlandi.emit(self.son_hesaplama)
