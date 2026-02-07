"""
Geleneksel Kara Sıva (El ile) Maliyet Hesaplama Penceresi
Harç kararak yapılan klasik sıva yöntemi maliyet analizi
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDoubleSpinBox, QGroupBox,
    QFormLayout, QMessageBox, QFrame, QGridLayout,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import logging

from app.core.calculator import (
    hesapla_kara_siva_manuel,
    KARA_SIVA_KARISIM,
    KARA_SIVA_VERIMLILIK
)

logger = logging.getLogger(__name__)


class KaraSivaWindow(QMainWindow):
    """Geleneksel kara sıva maliyet hesaplama penceresi"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Arayüzü oluştur"""
        self.setWindowTitle("Kara Sıva (El ile) Maliyet Hesaplama")
        self.setGeometry(100, 100, 950, 700)

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
                border: 1px solid #D4A574;
                padding: 5px;
                border-radius: 3px;
                min-height: 25px;
            }
            QPushButton {
                background-color: #D4A574;
                color: #1a1a2e;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E0B88A;
            }
            QGroupBox {
                color: #D4A574;
                border: 2px solid #D4A574;
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
                border: 2px solid #D4A574;
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

        # === ALAN VE KALINLIK ===
        alan_group = QGroupBox("1. Alan ve Kalınlık")
        alan_layout = QFormLayout()

        self.spin_alan_m2 = QDoubleSpinBox()
        self.spin_alan_m2.setRange(0.1, 100000)
        self.spin_alan_m2.setValue(200)
        self.spin_alan_m2.setSuffix(" m²")
        self.spin_alan_m2.setDecimals(1)
        alan_layout.addRow("Sıva Alanı:", self.spin_alan_m2)

        self.spin_kalinlik = QDoubleSpinBox()
        self.spin_kalinlik.setRange(0.5, 10)
        self.spin_kalinlik.setValue(2.0)
        self.spin_kalinlik.setSuffix(" cm")
        self.spin_kalinlik.setDecimals(1)
        alan_layout.addRow("Ortalama Kalınlık:", self.spin_kalinlik)

        # Bilgi etiketi
        info_label = QLabel("Harç: 1m³ için 1.1m³ kum + 6 torba çimento")
        info_label.setStyleSheet("color: #FFD700; font-size: 10px;")
        alan_layout.addRow("", info_label)

        alan_group.setLayout(alan_layout)
        layout.addWidget(alan_group)

        # === MALZEME FİYATLARI ===
        fiyat_group = QGroupBox("2. Malzeme Fiyatları")
        fiyat_layout = QFormLayout()

        self.spin_cimento_fiyat = QDoubleSpinBox()
        self.spin_cimento_fiyat.setRange(0, 10000)
        self.spin_cimento_fiyat.setValue(280)
        self.spin_cimento_fiyat.setSuffix(" TL")
        self.spin_cimento_fiyat.setDecimals(2)
        fiyat_layout.addRow("Çimento (50kg Torba):", self.spin_cimento_fiyat)

        self.spin_kum_fiyat = QDoubleSpinBox()
        self.spin_kum_fiyat.setRange(0, 10000)
        self.spin_kum_fiyat.setValue(850)
        self.spin_kum_fiyat.setSuffix(" TL/m³")
        self.spin_kum_fiyat.setDecimals(2)
        fiyat_layout.addRow("Kum (Nakliye dahil):", self.spin_kum_fiyat)

        fiyat_group.setLayout(fiyat_layout)
        layout.addWidget(fiyat_group)

        # === İŞÇİLİK ===
        iscilik_group = QGroupBox("3. İşçilik")
        iscilik_layout = QFormLayout()

        self.spin_ekip_ucret = QDoubleSpinBox()
        self.spin_ekip_ucret.setRange(0, 100000)
        self.spin_ekip_ucret.setValue(3000)
        self.spin_ekip_ucret.setSuffix(" TL/gün")
        self.spin_ekip_ucret.setDecimals(0)
        iscilik_layout.addRow("Ekip Günlük Ücret:", self.spin_ekip_ucret)

        ekip_aciklama = QLabel("(1 Usta + 1 Yardımcı)")
        ekip_aciklama.setStyleSheet("color: #888; font-size: 10px;")
        iscilik_layout.addRow("", ekip_aciklama)

        self.spin_fire = QDoubleSpinBox()
        self.spin_fire.setRange(0, 50)
        self.spin_fire.setValue(5)
        self.spin_fire.setSuffix(" %")
        self.spin_fire.setDecimals(1)
        iscilik_layout.addRow("Fire Oranı:", self.spin_fire)

        iscilik_group.setLayout(iscilik_layout)
        layout.addWidget(iscilik_group)

        # === VERİMLİLİK KAYNAĞI ===
        verim_group = QGroupBox("4. İşçilik Hızı Kaynağı (El ile)")
        verim_layout = QVBoxLayout()

        self.radio_group = QButtonGroup(self)

        # Piyasa seçeneği
        self.radio_piyasa = QRadioButton("Piyasa (Özel Sektör)")
        self.radio_piyasa.setChecked(True)
        self.radio_group.addButton(self.radio_piyasa, 0)
        verim_layout.addWidget(self.radio_piyasa)

        piyasa_hiz = KARA_SIVA_VERIMLILIK['piyasa']
        self.label_piyasa_hiz = QLabel(f"   → {piyasa_hiz} m²/gün (20-25 arası)")
        self.label_piyasa_hiz.setStyleSheet("color: #00FF00; font-size: 10px;")
        verim_layout.addWidget(self.label_piyasa_hiz)

        # CSB Resmi seçeneği
        self.radio_csb = QRadioButton("ÇŞB Resmi (Poz 27.501)")
        self.radio_group.addButton(self.radio_csb, 1)
        verim_layout.addWidget(self.radio_csb)

        csb_hiz = KARA_SIVA_VERIMLILIK['csb_resmi']
        self.label_csb_hiz = QLabel(f"   → {csb_hiz} m²/gün (12-14 arası)")
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
        self.spin_manuel_hiz.setValue(18)
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
        malzeme_baslik.setStyleSheet("color: #D4A574; font-weight: bold;")
        sonuc_layout.addWidget(malzeme_baslik, row, 0, 1, 2)
        row += 1

        # Kum
        sonuc_layout.addWidget(self._create_label("Gereken Kum:"), row, 0)
        self.lbl_kum = self._create_value_label("- m³")
        sonuc_layout.addWidget(self.lbl_kum, row, 1)
        row += 1

        # Çimento
        sonuc_layout.addWidget(self._create_label("Gereken Çimento (50kg):"), row, 0)
        self.lbl_cimento = self._create_value_label("- torba")
        sonuc_layout.addWidget(self.lbl_cimento, row, 1)
        row += 1

        # Ayırıcı
        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # Maliyet Başlık
        maliyet_baslik = QLabel("MALİYET DÖKÜMÜ")
        maliyet_baslik.setStyleSheet("color: #D4A574; font-weight: bold;")
        sonuc_layout.addWidget(maliyet_baslik, row, 0, 1, 2)
        row += 1

        # İşçilik
        sonuc_layout.addWidget(self._create_label("İşçilik Tutarı:"), row, 0)
        self.lbl_iscilik = self._create_value_label("- TL", "#FFD700")
        sonuc_layout.addWidget(self.lbl_iscilik, row, 1)
        row += 1

        # Kum Maliyeti
        sonuc_layout.addWidget(self._create_label("Kum Maliyeti:"), row, 0)
        self.lbl_kum_maliyet = self._create_value_label("- TL")
        sonuc_layout.addWidget(self.lbl_kum_maliyet, row, 1)
        row += 1

        # Çimento Maliyeti
        sonuc_layout.addWidget(self._create_label("Çimento Maliyeti:"), row, 0)
        self.lbl_cimento_maliyet = self._create_value_label("- TL")
        sonuc_layout.addWidget(self.lbl_cimento_maliyet, row, 1)
        row += 1

        # Toplam Malzeme
        sonuc_layout.addWidget(self._create_label("Toplam Malzeme:"), row, 0)
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

        # Birim maliyet bilgisi
        self.lbl_birim_maliyet = QLabel("")
        self.lbl_birim_maliyet.setStyleSheet("color: #00BFFF; font-size: 11px; margin-top: 10px;")
        layout.addWidget(self.lbl_birim_maliyet)

        # Not
        not_label = QLabel(
            "Not: El ile sıva, makine sıvaya göre daha yavaş\n"
            "ancak küçük alanlarda daha ekonomik olabilir."
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
        line.setStyleSheet("background-color: #D4A574;")
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
            duvar_m2 = self.spin_alan_m2.value()
            ortalama_kalinlik_cm = self.spin_kalinlik.value()
            cimento_torba_fiyat = self.spin_cimento_fiyat.value()
            kum_m3_fiyat = self.spin_kum_fiyat.value()
            ekip_gunluk_ucret = self.spin_ekip_ucret.value()
            fire_orani = self.spin_fire.value() / 100
            verim_kaynagi = self._get_verim_kaynagi()
            manuel_hiz = self.spin_manuel_hiz.value() if verim_kaynagi == 'manuel' else None

            # Hesapla
            sonuc = hesapla_kara_siva_manuel(
                duvar_m2=duvar_m2,
                cimento_torba_fiyat=cimento_torba_fiyat,
                kum_m3_fiyat=kum_m3_fiyat,
                ekip_gunluk_ucret=ekip_gunluk_ucret,
                fire_orani=fire_orani,
                verim_kaynagi=verim_kaynagi,
                ortalama_kalinlik_cm=ortalama_kalinlik_cm,
                manuel_hiz=manuel_hiz
            )

            # Sonuçları göster
            self._sonuclari_goster(sonuc, duvar_m2)

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
        self.lbl_kum.setText(f"{sonuc['gereken_kum_m3']:,.3f} m³")
        self.lbl_cimento.setText(f"{sonuc['gereken_cimento_torba']:,} torba")

        # Maliyet detayları
        self.lbl_iscilik.setText(f"{sonuc['toplam_iscilik_tl']:,.2f} TL")
        self.lbl_kum_maliyet.setText(f"{sonuc['kum_maliyet_tl']:,.2f} TL")
        self.lbl_cimento_maliyet.setText(f"{sonuc['cimento_maliyet_tl']:,.2f} TL")
        self.lbl_malzeme.setText(f"{sonuc['toplam_malzeme_tl']:,.2f} TL")

        # Genel toplam
        self.lbl_toplam.setText(f"{sonuc['genel_toplam_maliyet_tl']:,.2f} TL")

        # Birim maliyet
        birim_maliyet = sonuc['genel_toplam_maliyet_tl'] / alan_m2
        self.lbl_birim_maliyet.setText(
            f"Birim Maliyet: {birim_maliyet:,.2f} TL/m²"
        )
