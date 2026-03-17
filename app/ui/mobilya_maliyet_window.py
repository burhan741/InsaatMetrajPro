"""
Mobilya Maliyet Hesaplama Penceresi
Mutfak, Vestiyer, Banyo Dolabi ve Ahsap Kapi maliyet hesaplama arayuzu
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView,
    QFormLayout, QMessageBox, QFrame, QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import logging

from app.core.calculator import hesapla_mobilya_maliyet

logger = logging.getLogger(__name__)


class MobilyaMaliyetWindow(QMainWindow):
    """Mobilya maliyet hesaplama penceresi"""

    hesaplama_tamamlandi = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.urun_listesi = []
        self.son_hesaplama = None
        self.init_ui()

    def init_ui(self):
        """Arayuzu olustur"""
        self.setWindowTitle("Mobilya Maliyet Hesaplama")
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
                background-color: #1a1a2e;
            }
            QLabel {
                color: #e0e0e0;
            }
            QComboBox, QDoubleSpinBox, QSpinBox {
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
            QPushButton#btn_sil {
                background-color: #FF6B6B;
            }
            QPushButton#btn_sil:hover {
                background-color: #FF5252;
            }
            QPushButton#btn_temizle {
                background-color: #FFA500;
            }
            QPushButton#btn_temizle:hover {
                background-color: #FF8C00;
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
            QTableWidget {
                background-color: #16213e;
                color: #e0e0e0;
                gridline-color: #00BFFF;
                border: 1px solid #00BFFF;
                border-radius: 3px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #0f3460;
            }
            QHeaderView::section {
                background-color: #0f3460;
                color: #00BFFF;
                padding: 5px;
                border: 1px solid #00BFFF;
                font-weight: bold;
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
        panel = QGroupBox("Urun Girisi ve Fiyatlar")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # === URUN EKLEME ===
        urun_group = QGroupBox("1. Urun Ekle")
        urun_layout = QFormLayout()

        # Urun tipi
        self.combo_urun_tipi = QComboBox()
        self.combo_urun_tipi.addItem("Mutfak Dolabi", "mutfak")
        self.combo_urun_tipi.addItem("Vestiyer", "vestiyer")
        self.combo_urun_tipi.addItem("Banyo Dolabi", "banyo")
        self.combo_urun_tipi.addItem("Ahsap Kapi", "kapi")
        self.combo_urun_tipi.currentIndexChanged.connect(self._urun_tipi_degisti)
        urun_layout.addRow("Urun Tipi:", self.combo_urun_tipi)

        # En (cm)
        self.spin_en = QDoubleSpinBox()
        self.spin_en.setRange(1, 10000)
        self.spin_en.setValue(100)
        self.spin_en.setSuffix(" cm")
        self.spin_en.setDecimals(1)
        urun_layout.addRow("En:", self.spin_en)

        # Boy (cm)
        self.spin_boy = QDoubleSpinBox()
        self.spin_boy.setRange(1, 10000)
        self.spin_boy.setValue(220)
        self.spin_boy.setSuffix(" cm")
        self.spin_boy.setDecimals(1)
        urun_layout.addRow("Boy:", self.spin_boy)

        # Adet
        self.spin_adet = QSpinBox()
        self.spin_adet.setRange(1, 1000)
        self.spin_adet.setValue(1)
        self.spin_adet.setSuffix(" adet")
        urun_layout.addRow("Adet:", self.spin_adet)

        # Aciklama label (dinamik)
        self.label_alan_bilgi = QLabel("Alan: 2.20 m2")
        self.label_alan_bilgi.setStyleSheet("color: #FFD700; font-size: 11px;")
        urun_layout.addRow("", self.label_alan_bilgi)

        # Alan hesaplama guncelle
        self.spin_en.valueChanged.connect(self._alan_hesapla)
        self.spin_boy.valueChanged.connect(self._alan_hesapla)
        self.spin_adet.valueChanged.connect(self._alan_hesapla)

        urun_group.setLayout(urun_layout)
        layout.addWidget(urun_group)

        # Ekle butonu
        btn_ekle = QPushButton("+ URUN EKLE")
        btn_ekle.clicked.connect(self.urun_ekle)
        layout.addWidget(btn_ekle)

        # === URUN LISTESI ===
        liste_group = QGroupBox("2. Urun Listesi")
        liste_layout = QVBoxLayout()

        self.table_urunler = QTableWidget()
        self.table_urunler.setColumnCount(5)
        self.table_urunler.setHorizontalHeaderLabels(["Tip", "En (cm)", "Boy (cm)", "Adet", "Alan (m2)"])
        self.table_urunler.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_urunler.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_urunler.setMaximumHeight(200)
        liste_layout.addWidget(self.table_urunler)

        # Sil ve Temizle butonlari
        btn_layout = QHBoxLayout()
        btn_sil = QPushButton("Secili Sil")
        btn_sil.setObjectName("btn_sil")
        btn_sil.clicked.connect(self.secili_sil)
        btn_layout.addWidget(btn_sil)

        btn_temizle = QPushButton("Tumu Temizle")
        btn_temizle.setObjectName("btn_temizle")
        btn_temizle.clicked.connect(self.tumu_temizle)
        btn_layout.addWidget(btn_temizle)
        liste_layout.addLayout(btn_layout)

        liste_group.setLayout(liste_layout)
        layout.addWidget(liste_group)

        # === BIRIM FIYATLAR ===
        fiyat_group = QGroupBox("3. Birim Fiyatlar")
        fiyat_layout = QFormLayout()

        self.spin_mutfak_vestiyer_fiyat = QDoubleSpinBox()
        self.spin_mutfak_vestiyer_fiyat.setRange(0, 1000000)
        self.spin_mutfak_vestiyer_fiyat.setValue(8500)
        self.spin_mutfak_vestiyer_fiyat.setSuffix(" TL/m2")
        self.spin_mutfak_vestiyer_fiyat.setDecimals(2)
        fiyat_layout.addRow("Mutfak/Vestiyer:", self.spin_mutfak_vestiyer_fiyat)

        self.spin_banyo_fiyat = QDoubleSpinBox()
        self.spin_banyo_fiyat.setRange(0, 1000000)
        self.spin_banyo_fiyat.setValue(7500)
        self.spin_banyo_fiyat.setSuffix(" TL/m2")
        self.spin_banyo_fiyat.setDecimals(2)
        fiyat_layout.addRow("Banyo Dolabi:", self.spin_banyo_fiyat)

        self.spin_kapi_fiyat = QDoubleSpinBox()
        self.spin_kapi_fiyat.setRange(0, 1000000)
        self.spin_kapi_fiyat.setValue(12000)
        self.spin_kapi_fiyat.setSuffix(" TL/adet")
        self.spin_kapi_fiyat.setDecimals(2)
        fiyat_layout.addRow("Ahsap Kapi:", self.spin_kapi_fiyat)

        self.spin_montaj_nakliye = QDoubleSpinBox()
        self.spin_montaj_nakliye.setRange(0, 10000000)
        self.spin_montaj_nakliye.setValue(0)
        self.spin_montaj_nakliye.setSuffix(" TL")
        self.spin_montaj_nakliye.setDecimals(2)
        fiyat_layout.addRow("Montaj/Nakliye:", self.spin_montaj_nakliye)

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
        sonuc_layout.setSpacing(10)

        row = 0

        # Baslik
        baslik = QLabel("MOBILYA IMALAT DOKUMU")
        baslik.setStyleSheet("color: #00BFFF; font-size: 14px; font-weight: bold;")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sonuc_layout.addWidget(baslik, row, 0, 1, 2)
        row += 1

        # Ayirici
        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # DETAYLAR BOLUMU
        detay_baslik = QLabel("ALAN VE ADET DETAYLARI")
        detay_baslik.setStyleSheet("color: #FFD700; font-weight: bold;")
        sonuc_layout.addWidget(detay_baslik, row, 0, 1, 2)
        row += 1

        # Mutfak/Vestiyer Alani
        sonuc_layout.addWidget(self._create_label("Mutfak/Vestiyer Alani:"), row, 0)
        self.lbl_mutfak_vestiyer_m2 = self._create_value_label("- m2")
        sonuc_layout.addWidget(self.lbl_mutfak_vestiyer_m2, row, 1)
        row += 1

        # Banyo Dolabi Alani
        sonuc_layout.addWidget(self._create_label("Banyo Dolabi Alani:"), row, 0)
        self.lbl_banyo_m2 = self._create_value_label("- m2")
        sonuc_layout.addWidget(self.lbl_banyo_m2, row, 1)
        row += 1

        # Kapi Adedi
        sonuc_layout.addWidget(self._create_label("Ahsap Kapi Adedi:"), row, 0)
        self.lbl_kapi_adet = self._create_value_label("- adet")
        sonuc_layout.addWidget(self.lbl_kapi_adet, row, 1)
        row += 1

        # Ayirici
        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # MALIYET KIRILIMI BOLUMU
        maliyet_baslik = QLabel("MALIYET KIRILIMI")
        maliyet_baslik.setStyleSheet("color: #FFD700; font-weight: bold;")
        sonuc_layout.addWidget(maliyet_baslik, row, 0, 1, 2)
        row += 1

        # Mutfak/Vestiyer Maliyet
        sonuc_layout.addWidget(self._create_label("Mutfak/Vestiyer:"), row, 0)
        self.lbl_mutfak_vestiyer_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_mutfak_vestiyer_tl, row, 1)
        row += 1

        # Banyo Dolabi Maliyet
        sonuc_layout.addWidget(self._create_label("Banyo Dolabi:"), row, 0)
        self.lbl_banyo_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_banyo_tl, row, 1)
        row += 1

        # Ahsap Kapi Maliyet
        sonuc_layout.addWidget(self._create_label("Ahsap Kapi:"), row, 0)
        self.lbl_kapi_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_kapi_tl, row, 1)
        row += 1

        # Montaj/Nakliye Maliyet
        sonuc_layout.addWidget(self._create_label("Montaj/Nakliye:"), row, 0)
        self.lbl_montaj_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_montaj_tl, row, 1)
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
            color: #00BFFF;
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
        scroll.setMaximumHeight(200)
        scroll.setStyleSheet("background-color: #0a0a1a; border: 1px solid #00BFFF;")

        json_layout.addWidget(scroll)
        json_group.setLayout(json_layout)
        layout.addWidget(json_group)

        # Metraya Aktar butonu
        btn_metraya_aktar = QPushButton(" Metraya Aktar")
        btn_metraya_aktar.setStyleSheet("background-color: #FF6600; color: white; font-weight: bold; padding: 8px;")
        btn_metraya_aktar.clicked.connect(self._metraya_aktar)
        layout.addWidget(btn_metraya_aktar)

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
        line.setStyleSheet("background-color: #00BFFF;")
        line.setFixedHeight(1)
        return line

    def _urun_tipi_degisti(self, index):
        """Urun tipi degistiginde alanlari guncelle"""
        tip = self.combo_urun_tipi.currentData()
        if tip == 'kapi':
            self.spin_en.setEnabled(False)
            self.spin_boy.setEnabled(False)
            self.label_alan_bilgi.setText("Adet bazli hesaplanir")
        else:
            self.spin_en.setEnabled(True)
            self.spin_boy.setEnabled(True)
            self._alan_hesapla()

    def _alan_hesapla(self):
        """Alan hesapla ve goster"""
        tip = self.combo_urun_tipi.currentData()
        if tip == 'kapi':
            return

        en = self.spin_en.value()
        boy = self.spin_boy.value()
        adet = self.spin_adet.value()
        alan = (en * boy / 10000) * adet
        self.label_alan_bilgi.setText(f"Alan: {alan:.2f} m2")

    def urun_ekle(self):
        """Listeye urun ekle"""
        tip = self.combo_urun_tipi.currentData()
        tip_adi = self.combo_urun_tipi.currentText()
        adet = self.spin_adet.value()

        if tip == 'kapi':
            urun = {
                'tip': tip,
                'tip_adi': tip_adi,
                'adet': adet,
                'en_cm': 0,
                'boy_cm': 0
            }
        else:
            en = self.spin_en.value()
            boy = self.spin_boy.value()
            urun = {
                'tip': tip,
                'tip_adi': tip_adi,
                'en_cm': en,
                'boy_cm': boy,
                'adet': adet
            }

        self.urun_listesi.append(urun)
        self._tabloya_ekle(urun)
        logger.info(f"Urun eklendi: {urun}")

    def _tabloya_ekle(self, urun: dict):
        """Tabloya urun ekle"""
        row = self.table_urunler.rowCount()
        self.table_urunler.insertRow(row)

        self.table_urunler.setItem(row, 0, QTableWidgetItem(urun['tip_adi']))
        self.table_urunler.setItem(row, 1, QTableWidgetItem(str(urun.get('en_cm', '-'))))
        self.table_urunler.setItem(row, 2, QTableWidgetItem(str(urun.get('boy_cm', '-'))))
        self.table_urunler.setItem(row, 3, QTableWidgetItem(str(urun['adet'])))

        if urun['tip'] == 'kapi':
            self.table_urunler.setItem(row, 4, QTableWidgetItem('-'))
        else:
            alan = (urun['en_cm'] * urun['boy_cm'] / 10000) * urun['adet']
            self.table_urunler.setItem(row, 4, QTableWidgetItem(f"{alan:.2f}"))

    def secili_sil(self):
        """Secili urunu sil"""
        selected_rows = self.table_urunler.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Uyari", "Lutfen silmek icin bir urun secin.")
            return

        # Buyukten kucuge sirala ki index kaymasi olmasin
        rows = sorted([r.row() for r in selected_rows], reverse=True)
        for row in rows:
            self.table_urunler.removeRow(row)
            del self.urun_listesi[row]

    def tumu_temizle(self):
        """Tum urunleri temizle"""
        self.urun_listesi.clear()
        self.table_urunler.setRowCount(0)

    def hesapla(self):
        """Hesaplama yap"""
        try:
            if not self.urun_listesi:
                QMessageBox.warning(self, "Uyari", "Lutfen en az bir urun ekleyin.")
                return

            # Fiyatlari al
            mutfak_vestiyer_fiyat = self.spin_mutfak_vestiyer_fiyat.value()
            banyo_fiyat = self.spin_banyo_fiyat.value()
            kapi_fiyat = self.spin_kapi_fiyat.value()
            montaj_nakliye = self.spin_montaj_nakliye.value()

            # Hesapla
            sonuc = hesapla_mobilya_maliyet(
                urun_listesi=self.urun_listesi,
                mutfak_vestiyer_m2_fiyat=mutfak_vestiyer_fiyat,
                banyo_dolabi_m2_fiyat=banyo_fiyat,
                ahsap_kapi_adet_fiyat=kapi_fiyat,
                montaj_nakliye_sabit_bedel=montaj_nakliye
            )

            # Sonuclari goster
            self.son_hesaplama = sonuc
            self._sonuclari_goster(sonuc)
            logger.info(f"Mobilya hesaplama yapildi: {sonuc}")

        except Exception as e:
            logger.error(f"Hesaplama hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Hesaplama sirasinda hata:\n{str(e)}")

    def _sonuclari_goster(self, sonuc: dict):
        """Sonuclari arayuzde goster"""
        detaylar = sonuc['detaylar']
        maliyet = sonuc['maliyet_kirilimi']

        # Detaylar
        self.lbl_mutfak_vestiyer_m2.setText(f"{detaylar['toplam_mutfak_vestiyer_alani_m2']:.2f} m2")
        self.lbl_banyo_m2.setText(f"{detaylar['toplam_banyo_dolabi_alani_m2']:.2f} m2")
        self.lbl_kapi_adet.setText(f"{detaylar['toplam_kapi_adedi']} adet")

        # Maliyet kirilimi
        self.lbl_mutfak_vestiyer_tl.setText(f"{maliyet['mutfak_vestiyer_grup_tl']:,.2f} TL")
        self.lbl_banyo_tl.setText(f"{maliyet['banyo_dolabi_tl']:,.2f} TL")
        self.lbl_kapi_tl.setText(f"{maliyet['ahsap_kapi_tl']:,.2f} TL")
        self.lbl_montaj_tl.setText(f"{maliyet['montaj_nakliye_tl']:,.2f} TL")

        # Genel toplam
        self.lbl_toplam.setText(f"{sonuc['genel_toplam_maliyet_tl']:,.2f} TL")

        # JSON cikti
        import json
        json_str = json.dumps(sonuc, indent=2, ensure_ascii=False)
        self.lbl_json.setText(json_str)

    def _metraya_aktar(self):
        """Hesaplama sonucunu metraj listesine aktar"""
        if self.son_hesaplama is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Uyari", "Once bir hesaplama yapin!")
            return
        self.hesaplama_tamamlandi.emit(self.son_hesaplama)
