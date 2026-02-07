"""
Duvar Maliyet Hesaplama Penceresi
Detaylı duvar maliyet analizi arayüzü - Verimlilik kaynağı seçimli
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QGroupBox,
    QFormLayout, QMessageBox, QFrame, QGridLayout,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import logging

from app.core.calculator import (
    hesapla_duvar_maliyet_detayli,
    VERIMLILIK_VERITABANI,
    MALZEME_SARFIYAT
)

logger = logging.getLogger(__name__)


class DuvarMaliyetWindow(QMainWindow):
    """Duvar maliyet hesaplama penceresi"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Arayüzü oluştur"""
        self.setWindowTitle("Duvar Maliyet Hesaplama")
        self.setGeometry(100, 100, 900, 700)

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
            QComboBox, QDoubleSpinBox {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #00BFFF;
                padding: 5px;
                border-radius: 3px;
                min-height: 25px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QPushButton {
                background-color: #00BFFF;
                color: #1a1a2e;
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
                border: 2px solid #00BFFF;
                border-radius: 8px;
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

        # === DUVAR TİPİ ===
        duvar_group = QGroupBox("1. Duvar Tipi")
        duvar_layout = QFormLayout()

        self.combo_duvar_tipi = QComboBox()
        self.combo_duvar_tipi.addItem("Bims Blok 19 cm", "bims_19")
        self.combo_duvar_tipi.addItem("Tuğla 13.5 cm", "tugla_13.5")
        self.combo_duvar_tipi.addItem("Gazbeton 15 cm", "gazbeton_15")
        self.combo_duvar_tipi.currentIndexChanged.connect(self._duvar_tipi_degisti)
        duvar_layout.addRow("Duvar Tipi:", self.combo_duvar_tipi)

        # Sarfiyat bilgi etiketi
        self.label_sarfiyat_bilgi = QLabel("Sarfiyat: 13 adet/m² + Harç")
        self.label_sarfiyat_bilgi.setStyleSheet("color: #FFD700; font-size: 11px;")
        duvar_layout.addRow("", self.label_sarfiyat_bilgi)

        duvar_group.setLayout(duvar_layout)
        layout.addWidget(duvar_group)

        # === MİKTAR VE FİYAT ===
        miktar_group = QGroupBox("2. Miktar ve Fiyat")
        miktar_layout = QFormLayout()

        self.spin_duvar_m2 = QDoubleSpinBox()
        self.spin_duvar_m2.setRange(0.1, 100000)
        self.spin_duvar_m2.setValue(100)
        self.spin_duvar_m2.setSuffix(" m²")
        self.spin_duvar_m2.setDecimals(1)
        miktar_layout.addRow("Duvar Alanı:", self.spin_duvar_m2)

        self.spin_birim_fiyat = QDoubleSpinBox()
        self.spin_birim_fiyat.setRange(0, 10000)
        self.spin_birim_fiyat.setValue(15)
        self.spin_birim_fiyat.setSuffix(" TL/adet")
        self.spin_birim_fiyat.setDecimals(2)
        miktar_layout.addRow("Malzeme Birim Fiyat:", self.spin_birim_fiyat)

        self.spin_ekip_ucret = QDoubleSpinBox()
        self.spin_ekip_ucret.setRange(0, 100000)
        self.spin_ekip_ucret.setValue(3500)
        self.spin_ekip_ucret.setSuffix(" TL/gün")
        self.spin_ekip_ucret.setDecimals(0)
        miktar_layout.addRow("Ekip Günlük Ücret:", self.spin_ekip_ucret)

        # Ekip açıklaması
        ekip_aciklama = QLabel("(1 Usta + 1 Yardımcı)")
        ekip_aciklama.setStyleSheet("color: #888; font-size: 10px;")
        miktar_layout.addRow("", ekip_aciklama)

        self.spin_fire = QDoubleSpinBox()
        self.spin_fire.setRange(0, 50)
        self.spin_fire.setValue(5)
        self.spin_fire.setSuffix(" %")
        self.spin_fire.setDecimals(1)
        miktar_layout.addRow("Fire Oranı:", self.spin_fire)

        miktar_group.setLayout(miktar_layout)
        layout.addWidget(miktar_group)

        # === VERİMLİLİK KAYNAĞI ===
        verim_group = QGroupBox("3. İşçilik Hızı Kaynağı")
        verim_layout = QVBoxLayout()

        self.radio_group = QButtonGroup(self)

        # Piyasa seçeneği
        self.radio_piyasa = QRadioButton("Piyasa (Özel Sektör - Hızlı)")
        self.radio_piyasa.setChecked(True)
        self.radio_group.addButton(self.radio_piyasa, 0)
        verim_layout.addWidget(self.radio_piyasa)

        self.label_piyasa_hiz = QLabel("   → Bims: 22, Tuğla: 20, Gazbeton: 28 m²/gün")
        self.label_piyasa_hiz.setStyleSheet("color: #00FF00; font-size: 10px;")
        verim_layout.addWidget(self.label_piyasa_hiz)

        # CSB Resmi seçeneği
        self.radio_csb = QRadioButton("ÇŞB Resmi (Bakanlık Analizi - Yavaş)")
        self.radio_group.addButton(self.radio_csb, 1)
        verim_layout.addWidget(self.radio_csb)

        self.label_csb_hiz = QLabel("   → Bims: 14, Tuğla: 12, Gazbeton: 16 m²/gün")
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
        self.spin_manuel_hiz.setRange(1, 100)
        self.spin_manuel_hiz.setValue(20)
        self.spin_manuel_hiz.setSuffix(" m²/gün")
        self.spin_manuel_hiz.setEnabled(False)
        manuel_layout.addWidget(QLabel("Hız:"))
        manuel_layout.addWidget(self.spin_manuel_hiz)
        manuel_layout.addStretch()
        verim_layout.addLayout(manuel_layout)

        verim_group.setLayout(verim_layout)
        layout.addWidget(verim_group)

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
        sonuc_layout.setSpacing(10)

        # Başlıklar ve değerler
        row = 0

        # Kullanılan Hız
        sonuc_layout.addWidget(self._create_label("Kullanılan Hız:"), row, 0)
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

        # İşçilik Tutarı
        sonuc_layout.addWidget(self._create_label("İşçilik Tutarı:"), row, 0)
        self.lbl_iscilik = self._create_value_label("- TL", "#FFD700")
        sonuc_layout.addWidget(self.lbl_iscilik, row, 1)
        row += 1

        # Ana Malzeme Adet
        sonuc_layout.addWidget(self._create_label("Ana Malzeme Adet:"), row, 0)
        self.lbl_malzeme_adet = self._create_value_label("- adet")
        sonuc_layout.addWidget(self.lbl_malzeme_adet, row, 1)
        row += 1

        # Ana Malzeme Maliyet
        sonuc_layout.addWidget(self._create_label("Ana Malzeme Maliyet:"), row, 0)
        self.lbl_malzeme_maliyet = self._create_value_label("- TL", "#FFD700")
        sonuc_layout.addWidget(self.lbl_malzeme_maliyet, row, 1)
        row += 1

        # Ayırıcı
        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # Yan Ürünler Başlık
        yan_baslik = QLabel("YAN ÜRÜNLER (Fire Dahil)")
        yan_baslik.setStyleSheet("color: #00BFFF; font-weight: bold;")
        sonuc_layout.addWidget(yan_baslik, row, 0, 1, 2)
        row += 1

        # Kum
        sonuc_layout.addWidget(self._create_label("Gereken Kum:"), row, 0)
        self.lbl_kum = self._create_value_label("- m³")
        sonuc_layout.addWidget(self.lbl_kum, row, 1)
        row += 1

        # Çimento
        sonuc_layout.addWidget(self._create_label("Gereken Çimento:"), row, 0)
        self.lbl_cimento = self._create_value_label("- torba")
        sonuc_layout.addWidget(self.lbl_cimento, row, 1)
        row += 1

        # Yapıştırıcı
        sonuc_layout.addWidget(self._create_label("Gereken Yapıştırıcı:"), row, 0)
        self.lbl_yapistirici = self._create_value_label("- kg")
        sonuc_layout.addWidget(self.lbl_yapistirici, row, 1)
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
            "Not: Genel toplam = İşçilik + Ana Malzeme\n"
            "Kum, çimento ve yapıştırıcı maliyetleri dahil değildir."
        )
        not_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(not_label)

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
        line.setStyleSheet("background-color: #00BFFF;")
        line.setFixedHeight(1)
        return line

    def _duvar_tipi_degisti(self, index):
        """Duvar tipi değiştiğinde sarfiyat bilgisini güncelle"""
        duvar_tipi = self.combo_duvar_tipi.currentData()
        sarfiyat = MALZEME_SARFIYAT.get(duvar_tipi, {})

        adet = sarfiyat.get('adet_m2', 0)
        if 'harc_m3_m2' in sarfiyat:
            self.label_sarfiyat_bilgi.setText(f"Sarfiyat: {adet} adet/m² + Harç")
        else:
            yapistirici = sarfiyat.get('yapistirici_kg_m2', 0)
            self.label_sarfiyat_bilgi.setText(f"Sarfiyat: {adet} adet/m² + {yapistirici} kg/m² yapıştırıcı")

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
            duvar_tipi = self.combo_duvar_tipi.currentData()
            duvar_m2 = self.spin_duvar_m2.value()
            birim_fiyat = self.spin_birim_fiyat.value()
            ekip_ucret = self.spin_ekip_ucret.value()
            fire_orani = self.spin_fire.value() / 100  # Yüzdeyi orana çevir
            verim_kaynagi = self._get_verim_kaynagi()
            manuel_hiz = self.spin_manuel_hiz.value() if verim_kaynagi == 'manuel' else None

            # Hesapla
            sonuc = hesapla_duvar_maliyet_detayli(
                duvar_tipi=duvar_tipi,
                duvar_m2=duvar_m2,
                malzeme_birim_fiyat=birim_fiyat,
                ekip_gunluk_ucret=ekip_ucret,
                fire_orani=fire_orani,
                verim_kaynagi=verim_kaynagi,
                manuel_hiz=manuel_hiz
            )

            # Sonuçları göster
            self._sonuclari_goster(sonuc)

        except ValueError as e:
            QMessageBox.warning(self, "Hata", str(e))
        except Exception as e:
            logger.error(f"Hesaplama hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Hesaplama sırasında hata:\n{str(e)}")

    def _sonuclari_goster(self, sonuc: dict):
        """Sonuçları arayüzde göster"""
        self.lbl_hiz.setText(f"{sonuc['kullanilan_hiz_m2_gun']} m²/gün")
        self.lbl_sure.setText(f"{sonuc['tahmini_sure_gun']} gün")
        self.lbl_iscilik.setText(f"{sonuc['toplam_iscilik_tl']:,.2f} TL")
        self.lbl_malzeme_adet.setText(f"{sonuc['ana_malzeme_adet']:,} adet")
        self.lbl_malzeme_maliyet.setText(f"{sonuc['ana_malzeme_maliyet_tl']:,.2f} TL")

        # Yan ürünler
        if sonuc['gereken_kum_m3'] > 0:
            self.lbl_kum.setText(f"{sonuc['gereken_kum_m3']:.3f} m³")
        else:
            self.lbl_kum.setText("-")

        if sonuc['gereken_cimento_torba'] > 0:
            self.lbl_cimento.setText(f"{sonuc['gereken_cimento_torba']} torba")
        else:
            self.lbl_cimento.setText("-")

        if sonuc['gereken_yapistirici_kg'] > 0:
            self.lbl_yapistirici.setText(f"{sonuc['gereken_yapistirici_kg']:.2f} kg")
        else:
            self.lbl_yapistirici.setText("-")

        # Genel toplam
        self.lbl_toplam.setText(f"{sonuc['genel_toplam_maliyet_tl']:,.2f} TL")
