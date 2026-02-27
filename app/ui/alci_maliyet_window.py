"""
Makine Alçı (Sıva) Maliyet Hesaplama Penceresi
Detaylı alçı sıva maliyet analizi arayüzü - Perdah dahil
"""

from PyQt6.QtWidgets import (
QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
QPushButton, QLabel, QDoubleSpinBox, QGroupBox,
QFormLayout, QMessageBox, QFrame, QGridLayout,
QRadioButton, QButtonGroup, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import logging

from app.core.calculator import (
hesapla_alci_maliyet_detayli,
ALCI_SARFIYAT,
ALCI_VERIMLILIK
)

logger = logging.getLogger(__name__)


class AlciMaliyetWindow(QMainWindow):
    """Makine alçı maliyet hesaplama penceresi"""

    hesaplama_tamamlandi = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.son_hesaplama = None
        self.init_ui()

        def init_ui(self):
            """Arayüzü oluştur"""
            self.setWindowTitle("Makine Alçı (Sıva) Maliyet Hesaplama")
            self.setGeometry(100, 100, 950, 750)

            # Ana widget
            main_widget = QWidget()
            self.setCentralWidget(main_widget)
            main_layout = QHBoxLayout(main_widget)

            # Sol panel - Girişler
            left_panel = self._create_input_panel()
            main_layout.addWidget(left_panel, 1)

            # Sağ panel - Sonuçlar
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
                border: 1px solid #FF6B6B;
                padding: 5px;
                border-radius: 3px;
                min-height: 25px;
                }
                QPushButton {
                background-color: #FF6B6B;
                color: #1a1a2e;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
                }
                QPushButton:hover {
                background-color: #FF8E8E;
                }
                QGroupBox {
                color: #FF6B6B;
                border: 2px solid #FF6B6B;
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
                QRadioButton {
                color: #e0e0e0;
                }
                QRadioButton::indicator {
                width: 15px;
                height: 15px;
                }
                QRadioButton::indicator:checked {
                background-color: #00FF00;
                border: 2px solid #00AA00;
                border-radius: 8px;
                }
                QRadioButton::indicator:unchecked {
                background-color: #16213e;
                border: 2px solid #FF6B6B;
                border-radius: 8px;
                }
                QCheckBox {
                color: #e0e0e0;
                }
                QCheckBox::indicator {
                width: 18px;
                height: 18px;
                }
                QCheckBox::indicator:checked {
                background-color: #00FF00;
                border: 2px solid #00AA00;
                border-radius: 3px;
                }
                QCheckBox::indicator:unchecked {
                background-color: #16213e;
                border: 2px solid #FF6B6B;
                border-radius: 3px;
                }
                QFrame#sonuc_frame {
                background-color: #0f3460;
                border: 2px solid #00FF00;
                border-radius: 8px;
                padding: 10px;
                }
                """)

                def _create_input_panel(self) -> QGroupBox:
                    """Giriş panelini oluştur"""
                    panel = QGroupBox("Hesaplama Parametreleri")
                    layout = QVBoxLayout()
                    layout.setSpacing(15)

                    # === ALAN VE KALINLIK ===
                    alan_group = QGroupBox("1. Alan ve Kalınlık")
                    alan_layout = QFormLayout()

                    self.spin_alan_m2 = QDoubleSpinBox()
                    self.spin_alan_m2.setRange(0.1, 100000)
                    self.spin_alan_m2.setValue(500)
                    self.spin_alan_m2.setSuffix(" m²")
                    self.spin_alan_m2.setDecimals(1)
                    alan_layout.addRow("Uygulama Alanı:", self.spin_alan_m2)

                    self.spin_kalinlik = QDoubleSpinBox()
                    self.spin_kalinlik.setRange(0.5, 10)
                    self.spin_kalinlik.setValue(1.5)
                    self.spin_kalinlik.setSuffix(" cm")
                    self.spin_kalinlik.setDecimals(1)
                    alan_layout.addRow("Ortalama Kalınlık:", self.spin_kalinlik)

                    # Sarfiyat bilgisi
                    sarfiyat_info = QLabel(f"Sarfiyat: {ALCI_SARFIYAT['kg_m2_cm']} kg/m²/cm")
                    sarfiyat_info.setStyleSheet("color: #FFD700; font-size: 11px;")
                    alan_layout.addRow("", sarfiyat_info)

                    alan_group.setLayout(alan_layout)
                    layout.addWidget(alan_group)

                    # === FİYAT VE İŞÇİLİK ===
                    fiyat_group = QGroupBox("2. Fiyat ve İşçilik")
                    fiyat_layout = QFormLayout()

                    self.spin_torba_fiyat = QDoubleSpinBox()
                    self.spin_torba_fiyat.setRange(0, 10000)
                    self.spin_torba_fiyat.setValue(350)
                    self.spin_torba_fiyat.setSuffix(" TL")
                    self.spin_torba_fiyat.setDecimals(2)
                    fiyat_layout.addRow("Torba Birim Fiyat (25kg):", self.spin_torba_fiyat)

                    self.spin_ekip_ucret = QDoubleSpinBox()
                    self.spin_ekip_ucret.setRange(0, 100000)
                    self.spin_ekip_ucret.setValue(5000)
                    self.spin_ekip_ucret.setSuffix(" TL/gün")
                    self.spin_ekip_ucret.setDecimals(0)
                    fiyat_layout.addRow("Ekip Günlük Ücret:", self.spin_ekip_ucret)

                    # Ekip açıklaması
                    ekip_aciklama = QLabel("(Makine + Operatör + Yardımcılar)")
                    ekip_aciklama.setStyleSheet("color: #888; font-size: 10px;")
                    fiyat_layout.addRow("", ekip_aciklama)

                    self.spin_fire = QDoubleSpinBox()
                    self.spin_fire.setRange(0, 50)
                    self.spin_fire.setValue(5)
                    self.spin_fire.setSuffix(" %")
                    self.spin_fire.setDecimals(1)
                    fiyat_layout.addRow("Fire Oranı:", self.spin_fire)

                    fiyat_group.setLayout(fiyat_layout)
                    layout.addWidget(fiyat_group)

                    # === VERİMLİLİK KAYNAĞI ===
                    verim_group = QGroupBox("3. İşçilik Hızı Kaynağı (Perdah Dahil)")
                    verim_layout = QVBoxLayout()

                    self.radio_group = QButtonGroup(self)

                    # Piyasa seçeneği
                    self.radio_piyasa = QRadioButton("Piyasa (Özel Sektör)")
                    self.radio_piyasa.setChecked(True)
                    self.radio_group.addButton(self.radio_piyasa, 0)
                    verim_layout.addWidget(self.radio_piyasa)

                    piyasa_hiz = ALCI_VERIMLILIK['piyasa']
                    self.label_piyasa_hiz = QLabel(f" → {piyasa_hiz} m²/gün (80-100 arası)")
                    self.label_piyasa_hiz.setStyleSheet("color: #00FF00; font-size: 10px;")
                    verim_layout.addWidget(self.label_piyasa_hiz)

                    # CSB Resmi seçeneği
                    self.radio_csb = QRadioButton("ÇŞB Resmi (Bakanlık Analizi)")
                    self.radio_group.addButton(self.radio_csb, 1)
                    verim_layout.addWidget(self.radio_csb)

                    csb_hiz = ALCI_VERIMLILIK['csb_resmi']
                    self.label_csb_hiz = QLabel(f" → {csb_hiz} m²/gün (40-50 arası)")
                    self.label_csb_hiz.setStyleSheet("color: #FFA500; font-size: 10px;")
                    verim_layout.addWidget(self.label_csb_hiz)

                    # Manuel seçeneği
                    self.radio_manuel = QRadioButton("Manuel (Kendi Hızınız)")
                    self.radio_group.addButton(self.radio_manuel, 2)
                    self.radio_manuel.toggled.connect(self._manuel_toggled)
                    verim_layout.addWidget(self.radio_manuel)

                    # Manuel hız girişi
                    manuel_layout = QHBoxLayout()
                    manuel_layout.addSpacing(20)
                    self.spin_manuel_hiz = QDoubleSpinBox()
                    self.spin_manuel_hiz.setRange(1, 500)
                    self.spin_manuel_hiz.setValue(70)
                    self.spin_manuel_hiz.setSuffix(" m²/gün")
                    self.spin_manuel_hiz.setEnabled(False)
                    manuel_layout.addWidget(QLabel("Hız:"))
                    manuel_layout.addWidget(self.spin_manuel_hiz)
                    manuel_layout.addStretch()
                    verim_layout.addLayout(manuel_layout)

                    verim_group.setLayout(verim_layout)
                    layout.addWidget(verim_group)

                    # === EK SEÇENEKLER ===
                    ek_group = QGroupBox("4. Ek Seçenekler")
                    ek_layout = QVBoxLayout()

                    self.check_ano = QCheckBox("Köşe Profili / Ano Kullan")
                    self.check_ano.setChecked(True)
                    ek_layout.addWidget(self.check_ano)

                    ano_info = QLabel(f" (Sarfiyat: {ALCI_SARFIYAT['ano_profil_m_m2']} mt/m²)")
                    ano_info.setStyleSheet("color: #888; font-size: 10px;")
                    ek_layout.addWidget(ano_info)

                    ek_group.setLayout(ek_layout)
                    layout.addWidget(ek_group)

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
                        """Sonuç panelini oluştur"""
                        panel = QGroupBox("Hesaplama Sonuçları")
                        layout = QVBoxLayout()

                        # Sonuç frame'i
                        sonuc_frame = QFrame()
                        sonuc_frame.setObjectName("sonuc_frame")
                        sonuc_layout = QGridLayout(sonuc_frame)
                        sonuc_layout.setSpacing(12)

                        row = 0

                        # Kullanılan Hız
                        sonuc_layout.addWidget(self._create_label("Baz Alınan Hız:"), row, 0)
                        self.lbl_hiz = self._create_value_label("- m²/gün")
                        sonuc_layout.addWidget(self.lbl_hiz, row, 1)
                        row += 1

                        # Tahmini Süre
                        sonuc_layout.addWidget(self._create_label("Tahmini Süre:"), row, 0)
                        self.lbl_sure = self._create_value_label("- gün")
                        sonuc_layout.addWidget(self.lbl_sure, row, 1)
                        row += 1

                        # Ayırıcı
                        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
                        row += 1

                        # Malzeme Başlık
                        malzeme_baslik = QLabel("MALZEME İHTİYACI (Fire Dahil)")
                        malzeme_baslik.setStyleSheet("color: #FF6B6B; font-weight: bold;")
                        sonuc_layout.addWidget(malzeme_baslik, row, 0, 1, 2)
                        row += 1

                        # Toplam Alçı kg
                        sonuc_layout.addWidget(self._create_label("Toplam Alçı:"), row, 0)
                        self.lbl_alci_kg = self._create_value_label("- kg")
                        sonuc_layout.addWidget(self.lbl_alci_kg, row, 1)
                        row += 1

                        # Torba Adet
                        sonuc_layout.addWidget(self._create_label("Gereken Torba (25kg):"), row, 0)
                        self.lbl_torba = self._create_value_label("- adet")
                        sonuc_layout.addWidget(self.lbl_torba, row, 1)
                        row += 1

                        # Ano Profil
                        sonuc_layout.addWidget(self._create_label("Köşe Profili/Ano:"), row, 0)
                        self.lbl_ano = self._create_value_label("- mt")
                        sonuc_layout.addWidget(self.lbl_ano, row, 1)
                        row += 1

                        # Astar
                        sonuc_layout.addWidget(self._create_label("Astar:"), row, 0)
                        self.lbl_astar = self._create_value_label("- kg")
                        sonuc_layout.addWidget(self.lbl_astar, row, 1)
                        row += 1

                        # Ayırıcı
                        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
                        row += 1

                        # Maliyet Başlık
                        maliyet_baslik = QLabel("MALİYET DÖKÜMÜ")
                        maliyet_baslik.setStyleSheet("color: #FF6B6B; font-weight: bold;")
                        sonuc_layout.addWidget(maliyet_baslik, row, 0, 1, 2)
                        row += 1

                        # İşçilik Tutarı
                        sonuc_layout.addWidget(self._create_label("İşçilik Tutarı:"), row, 0)
                        self.lbl_iscilik = self._create_value_label("- TL", "#FFD700")
                        sonuc_layout.addWidget(self.lbl_iscilik, row, 1)
                        row += 1

                        # Malzeme Tutarı
                        sonuc_layout.addWidget(self._create_label("Malzeme Tutarı (Alçı):"), row, 0)
                        self.lbl_malzeme = self._create_value_label("- TL", "#FFD700")
                        sonuc_layout.addWidget(self.lbl_malzeme, row, 1)
                        row += 1

                        # Ayırıcı
                        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
                        row += 1

                        # GENEL TOPLAM
                        toplam_label = QLabel("GENEL TOPLAM:")
                        toplam_label.setStyleSheet("color: #00FF00; font-size: 14px; font-weight: bold;")
                        sonuc_layout.addWidget(toplam_label, row, 0)

                        self.lbl_toplam = QLabel("- TL")
                        self.lbl_toplam.setStyleSheet("color: #00FF00; font-size: 18px; font-weight: bold;")
                        sonuc_layout.addWidget(self.lbl_toplam, row, 1)

                        layout.addWidget(sonuc_frame)

                        # Açıklama notu
                        not_label = QLabel(
                        "Not: Genel toplam = İşçilik + Alçı Malzemesi\n"
                        "Profil ve astar maliyetleri dahil değildir (miktarlar gösterilmektedir)."
                        )
                        not_label.setStyleSheet("color: #888; font-size: 10px;")
                        layout.addWidget(not_label)

                        # Birim maliyet bilgisi
                        self.lbl_birim_maliyet = QLabel("")
                        self.lbl_birim_maliyet.setStyleSheet("color: #00BFFF; font-size: 11px; margin-top: 10px;")
                        layout.addWidget(self.lbl_birim_maliyet)

                        # Metraya Aktar butonu
                        btn_metraya_aktar = QPushButton(" Metraya Aktar")
                        btn_metraya_aktar.setStyleSheet("background-color: #FF6600; color: white; font-weight: bold; padding: 8px;")
                        btn_metraya_aktar.clicked.connect(self._metraya_aktar)
                        layout.addWidget(btn_metraya_aktar)

                        layout.addStretch()
                        panel.setLayout(layout)
                        return panel

                        def _create_label(self, text: str) -> QLabel:
                            """Normal etiket oluştur"""
                            label = QLabel(text)
                            label.setStyleSheet("color: #e0e0e0;")
                            return label

                            def _create_value_label(self, text: str, color: str = "#FFFFFF") -> QLabel:
                                """Değer etiketi oluştur"""
                                label = QLabel(text)
                                label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")
                                label.setAlignment(Qt.AlignmentFlag.AlignRight)
                                return label

                                def _create_separator(self) -> QFrame:
                                    """Ayırıcı çizgi oluştur"""
                                    line = QFrame()
                                    line.setFrameShape(QFrame.Shape.HLine)
                                    line.setStyleSheet("background-color: #FF6B6B;")
                                    line.setFixedHeight(1)
                                    return line

                                    def _manuel_toggled(self, checked):
                                        """Manuel seçeneği toggle edildiğinde"""
                                        self.spin_manuel_hiz.setEnabled(checked)

                                        def _get_verim_kaynagi(self) -> str:
                                            """Seçili verim kaynağını döndür"""
                                            if self.radio_piyasa.isChecked():
                                                return 'piyasa'
                                            elif self.radio_csb.isChecked():
                                                return 'csb_resmi'
                                            else:
                                                return 'manuel'

                                                def hesapla(self):
                                                    """Hesaplama yap"""
                                                    try:
                                                        uygulama_alani_m2 = self.spin_alan_m2.value()
                                                        ortalama_kalinlik_cm = self.spin_kalinlik.value()
                                                        torba_birim_fiyat = self.spin_torba_fiyat.value()
                                                        ekip_gunluk_ucret = self.spin_ekip_ucret.value()
                                                        fire_orani = self.spin_fire.value() / 100 # Yüzdeyi orana çevir
                                                        verim_kaynagi = self._get_verim_kaynagi()
                                                        manuel_hiz = self.spin_manuel_hiz.value() if verim_kaynagi == 'manuel' else None
                                                        ano_kullanimi = self.check_ano.isChecked()

                                                        # Hesapla
                                                        sonuc = hesapla_alci_maliyet_detayli(
                                                        uygulama_alani_m2=uygulama_alani_m2,
                                                        torba_birim_fiyat=torba_birim_fiyat,
                                                        ekip_gunluk_ucret=ekip_gunluk_ucret,
                                                        fire_orani=fire_orani,
                                                        verim_kaynagi=verim_kaynagi,
                                                        ortalama_kalinlik_cm=ortalama_kalinlik_cm,
                                                        manuel_hiz=manuel_hiz,
                                                        ano_kullanimi=ano_kullanimi
                                                        )

                                                        # Sonuçları göster
                                                        self.son_hesaplama = sonuc
                                                        self._sonuclari_goster(sonuc, uygulama_alani_m2)

                                                    except ValueError as e:
                                                        QMessageBox.warning(self, "Hata", str(e))
                                                    except Exception as e:
                                                        logger.error(f"Hesaplama hatası: {e}")
                                                        QMessageBox.critical(self, "Hata", f"Hesaplama sırasında hata:\n{str(e)}")

                                                        def _sonuclari_goster(self, sonuc: dict, alan_m2: float):
                                                            """Sonuçları arayüzde göster"""
                                                            self.lbl_hiz.setText(f"{sonuc['baz_alinan_hiz_m2']} m²/gün")
                                                            self.lbl_sure.setText(f"{sonuc['tahmini_sure_gun']} gün")

                                                            # Malzeme
                                                            self.lbl_alci_kg.setText(f"{sonuc['toplam_alci_kg']:,.2f} kg")
                                                            self.lbl_torba.setText(f"{sonuc['gereken_torba_adet']:,} adet")

                                                            if sonuc['gereken_ano_profil_mt'] > 0:
                                                                self.lbl_ano.setText(f"{sonuc['gereken_ano_profil_mt']:,.2f} mt")
                                                            else:
                                                                self.lbl_ano.setText("Kullanılmıyor")

                                                                self.lbl_astar.setText(f"{sonuc['gereken_astar_kg']:,.2f} kg")

                                                                # Maliyet
                                                                self.lbl_iscilik.setText(f"{sonuc['toplam_iscilik_tl']:,.2f} TL")
                                                                self.lbl_malzeme.setText(f"{sonuc['toplam_malzeme_tl']:,.2f} TL")

                                                                # Genel toplam
                                                                self.lbl_toplam.setText(f"{sonuc['genel_toplam_maliyet_tl']:,.2f} TL")

                                                                # Birim maliyet
                                                                birim_maliyet = sonuc['genel_toplam_maliyet_tl'] / alan_m2
                                                                self.lbl_birim_maliyet.setText(
                                                                f"Birim Maliyet: {birim_maliyet:,.2f} TL/m² (İşçilik + Alçı)"
                                                                )

                                                                def _metraya_aktar(self):
                                                                    """Hesaplama sonucunu metraj listesine aktar"""
                                                                    if self.son_hesaplama is None:
                                                                        from PyQt6.QtWidgets import QMessageBox
                                                                        QMessageBox.warning(self, "Uyarı", "Önce bir hesaplama yapın!")
                                                                        return
                                                                        self.hesaplama_tamamlandi.emit(self.son_hesaplama)
