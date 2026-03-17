"""
Su Yalitim Maliyet Hesaplama Penceresi
Bez (Rulo), Toz (Cimento esasli), Surme (Likit/PU) yalitim maliyet hesaplama arayuzu
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView,
    QFormLayout, QMessageBox, QFrame, QGridLayout, QScrollArea,
    QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import logging

from app.core.calculator import hesapla_yalitim_maliyeti

logger = logging.getLogger(__name__)


class YalitimMaliyetWindow(QMainWindow):
    """Su yalitim maliyet hesaplama penceresi"""

    hesaplama_tamamlandi = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_listesi = []
        self.son_hesaplama = None
        self.init_ui()

    def init_ui(self):
        """Arayuzu olustur"""
        self.setWindowTitle("Su Yalitim Maliyet Hesaplama")
        self.setGeometry(100, 100, 1150, 850)

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
            QComboBox, QDoubleSpinBox, QLineEdit {
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
        panel = QGroupBox("Is Kalemi Girisi ve Fiyatlar")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # === IS KALEMI EKLEME ===
        is_group = QGroupBox("1. Is Kalemi Ekle")
        is_layout = QFormLayout()

        # Yalitim turu
        self.combo_yalitim_turu = QComboBox()
        self.combo_yalitim_turu.addItem("Bez Membran (Bitumlu Rulo)", "bez")
        self.combo_yalitim_turu.addItem("Toz Membran (Cimento Esasli)", "toz")
        self.combo_yalitim_turu.addItem("Surme Membran (Likit/PU/Bitum)", "surme")
        self.combo_yalitim_turu.currentIndexChanged.connect(self._tur_degisti)
        is_layout.addRow("Yalitim Turu:", self.combo_yalitim_turu)

        # Aciklama
        self.txt_aciklama = QLineEdit()
        self.txt_aciklama.setPlaceholderText("Ornek: Temel perde, Teras, WC zemin...")
        is_layout.addRow("Aciklama:", self.txt_aciklama)

        # Alan (m2)
        self.spin_alan = QDoubleSpinBox()
        self.spin_alan.setRange(0.1, 100000)
        self.spin_alan.setValue(50)
        self.spin_alan.setSuffix(" m2")
        self.spin_alan.setDecimals(2)
        is_layout.addRow("Alan:", self.spin_alan)

        # Bilgi etiketi
        self.label_tur_bilgi = QLabel("Bez membran icin %10 bindirme payi otomatik eklenir.")
        self.label_tur_bilgi.setStyleSheet("color: #FFD700; font-size: 11px;")
        is_layout.addRow("", self.label_tur_bilgi)

        is_group.setLayout(is_layout)
        layout.addWidget(is_group)

        # Ekle butonu
        btn_ekle = QPushButton("+ IS KALEMI EKLE")
        btn_ekle.clicked.connect(self.is_kalemi_ekle)
        layout.addWidget(btn_ekle)

        # === IS LISTESI ===
        liste_group = QGroupBox("2. Is Kalemleri Listesi")
        liste_layout = QVBoxLayout()

        self.table_isler = QTableWidget()
        self.table_isler.setColumnCount(4)
        self.table_isler.setHorizontalHeaderLabels(["Tur", "Aciklama", "Net Alan (m2)", "Brut Alan (m2)"])
        self.table_isler.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_isler.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_isler.setMaximumHeight(180)
        liste_layout.addWidget(self.table_isler)

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
        fiyat_group = QGroupBox("3. Birim Fiyatlar (TL/m2)")
        fiyat_layout = QFormLayout()

        self.spin_bez_fiyat = QDoubleSpinBox()
        self.spin_bez_fiyat.setRange(0, 100000)
        self.spin_bez_fiyat.setValue(350)
        self.spin_bez_fiyat.setSuffix(" TL/m2")
        self.spin_bez_fiyat.setDecimals(2)
        fiyat_layout.addRow("Bez Membran:", self.spin_bez_fiyat)

        self.spin_toz_fiyat = QDoubleSpinBox()
        self.spin_toz_fiyat.setRange(0, 100000)
        self.spin_toz_fiyat.setValue(180)
        self.spin_toz_fiyat.setSuffix(" TL/m2")
        self.spin_toz_fiyat.setDecimals(2)
        fiyat_layout.addRow("Toz Membran:", self.spin_toz_fiyat)

        self.spin_surme_fiyat = QDoubleSpinBox()
        self.spin_surme_fiyat.setRange(0, 100000)
        self.spin_surme_fiyat.setValue(220)
        self.spin_surme_fiyat.setSuffix(" TL/m2")
        self.spin_surme_fiyat.setDecimals(2)
        fiyat_layout.addRow("Surme Membran:", self.spin_surme_fiyat)

        # Separator
        sep_label = QLabel("--- Yan Giderler (Opsiyonel) ---")
        sep_label.setStyleSheet("color: #888; font-size: 10px;")
        sep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fiyat_layout.addRow(sep_label)

        self.spin_astar_fiyat = QDoubleSpinBox()
        self.spin_astar_fiyat.setRange(0, 100000)
        self.spin_astar_fiyat.setValue(0)
        self.spin_astar_fiyat.setSuffix(" TL/m2")
        self.spin_astar_fiyat.setDecimals(2)
        fiyat_layout.addRow("Astar (Primer):", self.spin_astar_fiyat)

        self.spin_iscilik_fiyat = QDoubleSpinBox()
        self.spin_iscilik_fiyat.setRange(0, 100000)
        self.spin_iscilik_fiyat.setValue(0)
        self.spin_iscilik_fiyat.setSuffix(" TL/m2")
        self.spin_iscilik_fiyat.setDecimals(2)
        fiyat_layout.addRow("Iscilik (Ayr.):", self.spin_iscilik_fiyat)

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
        baslik = QLabel("SU YALITIMI METRAJ VE MALIYET DOKUMU")
        baslik.setStyleSheet("color: #00BFFF; font-size: 14px; font-weight: bold;")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sonuc_layout.addWidget(baslik, row, 0, 1, 2)
        row += 1

        # Ayirici
        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # METRAJ ANALIZI BOLUMU
        metraj_baslik = QLabel("METRAJ ANALIZI")
        metraj_baslik.setStyleSheet("color: #FFD700; font-weight: bold;")
        sonuc_layout.addWidget(metraj_baslik, row, 0, 1, 2)
        row += 1

        # Bez Membran - Net
        sonuc_layout.addWidget(self._create_label("Bez Membran Net Alan:"), row, 0)
        self.lbl_bez_net = self._create_value_label("- m2")
        sonuc_layout.addWidget(self.lbl_bez_net, row, 1)
        row += 1

        # Bez Membran - Brut (Bini dahil)
        sonuc_layout.addWidget(self._create_label("Bez Membran Satin Alma (%10 bini):"), row, 0)
        self.lbl_bez_brut = self._create_value_label("- m2", "#FFA500")
        sonuc_layout.addWidget(self.lbl_bez_brut, row, 1)
        row += 1

        # Toz Membran
        sonuc_layout.addWidget(self._create_label("Toz Membran Net Alan:"), row, 0)
        self.lbl_toz = self._create_value_label("- m2")
        sonuc_layout.addWidget(self.lbl_toz, row, 1)
        row += 1

        # Surme Membran
        sonuc_layout.addWidget(self._create_label("Surme Membran Net Alan:"), row, 0)
        self.lbl_surme = self._create_value_label("- m2")
        sonuc_layout.addWidget(self.lbl_surme, row, 1)
        row += 1

        # Toplam Is Alani
        sonuc_layout.addWidget(self._create_label("Toplam Is Alani:"), row, 0)
        self.lbl_toplam_alan = self._create_value_label("- m2", "#00BFFF")
        sonuc_layout.addWidget(self.lbl_toplam_alan, row, 1)
        row += 1

        # Ayirici
        sonuc_layout.addWidget(self._create_separator(), row, 0, 1, 2)
        row += 1

        # MALIYET KIRILIMI BOLUMU
        maliyet_baslik = QLabel("MALIYET KIRILIMI")
        maliyet_baslik.setStyleSheet("color: #FFD700; font-weight: bold;")
        sonuc_layout.addWidget(maliyet_baslik, row, 0, 1, 2)
        row += 1

        # Bez Membran Maliyet
        sonuc_layout.addWidget(self._create_label("Bez Membran Tutari:"), row, 0)
        self.lbl_bez_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_bez_tl, row, 1)
        row += 1

        # Toz Membran Maliyet
        sonuc_layout.addWidget(self._create_label("Toz Membran Tutari:"), row, 0)
        self.lbl_toz_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_toz_tl, row, 1)
        row += 1

        # Surme Membran Maliyet
        sonuc_layout.addWidget(self._create_label("Surme Membran Tutari:"), row, 0)
        self.lbl_surme_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_surme_tl, row, 1)
        row += 1

        # Astar Maliyet
        sonuc_layout.addWidget(self._create_label("Astar Tutari:"), row, 0)
        self.lbl_astar_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_astar_tl, row, 1)
        row += 1

        # Iscilik Maliyet
        sonuc_layout.addWidget(self._create_label("Iscilik Tutari:"), row, 0)
        self.lbl_iscilik_tl = self._create_value_label("- TL", "#00FF00")
        sonuc_layout.addWidget(self.lbl_iscilik_tl, row, 1)
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
        scroll.setMaximumHeight(180)
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

    def _tur_degisti(self, index):
        """Yalitim turu degistiginde bilgi guncelle"""
        tur = self.combo_yalitim_turu.currentData()
        if tur == 'bez':
            self.label_tur_bilgi.setText("Bez membran icin %10 bindirme payi otomatik eklenir.")
            self.label_tur_bilgi.setStyleSheet("color: #FFD700; font-size: 11px;")
        elif tur == 'toz':
            self.label_tur_bilgi.setText("Toz membran: Cimento esasli, 2 kat uygulama onerilir.")
            self.label_tur_bilgi.setStyleSheet("color: #00BFFF; font-size: 11px;")
        elif tur == 'surme':
            self.label_tur_bilgi.setText("Surme membran: Likit/PU bazli, esnek ve dikissiz.")
            self.label_tur_bilgi.setStyleSheet("color: #00FF00; font-size: 11px;")

    def is_kalemi_ekle(self):
        """Listeye is kalemi ekle"""
        tur = self.combo_yalitim_turu.currentData()
        tur_adi = self.combo_yalitim_turu.currentText()
        alan = self.spin_alan.value()
        aciklama = self.txt_aciklama.text().strip() or "-"

        # Brut alan hesapla (bez icin %10 eklenir)
        brut_alan = alan * 1.10 if tur == 'bez' else alan

        is_kalemi = {
            'tur': tur,
            'tur_adi': tur_adi,
            'alan_m2': alan,
            'brut_alan_m2': brut_alan,
            'aciklama': aciklama
        }

        self.is_listesi.append(is_kalemi)
        self._tabloya_ekle(is_kalemi)

        # Aciklama alanini temizle
        self.txt_aciklama.clear()
        logger.info(f"Is kalemi eklendi: {is_kalemi}")

    def _tabloya_ekle(self, is_kalemi: dict):
        """Tabloya is kalemi ekle"""
        row = self.table_isler.rowCount()
        self.table_isler.insertRow(row)

        # Tur adi kisa goster
        tur_kisa = {
            'bez': 'Bez (Rulo)',
            'toz': 'Toz',
            'surme': 'Surme'
        }.get(is_kalemi['tur'], is_kalemi['tur'])

        self.table_isler.setItem(row, 0, QTableWidgetItem(tur_kisa))
        self.table_isler.setItem(row, 1, QTableWidgetItem(is_kalemi['aciklama']))
        self.table_isler.setItem(row, 2, QTableWidgetItem(f"{is_kalemi['alan_m2']:.2f}"))
        self.table_isler.setItem(row, 3, QTableWidgetItem(f"{is_kalemi['brut_alan_m2']:.2f}"))

    def secili_sil(self):
        """Secili is kalemini sil"""
        selected_rows = self.table_isler.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Uyari", "Lutfen silmek icin bir is kalemi secin.")
            return

        rows = sorted([r.row() for r in selected_rows], reverse=True)
        for row in rows:
            self.table_isler.removeRow(row)
            del self.is_listesi[row]

    def tumu_temizle(self):
        """Tum is kalemlerini temizle"""
        self.is_listesi.clear()
        self.table_isler.setRowCount(0)

    def hesapla(self):
        """Hesaplama yap"""
        try:
            if not self.is_listesi:
                QMessageBox.warning(self, "Uyari", "Lutfen en az bir is kalemi ekleyin.")
                return

            # Fiyatlari al
            fiyatlar = {
                'bez_membran_m2_fiyat': self.spin_bez_fiyat.value(),
                'toz_membran_m2_fiyat': self.spin_toz_fiyat.value(),
                'surme_membran_m2_fiyat': self.spin_surme_fiyat.value(),
                'astar_m2_fiyat': self.spin_astar_fiyat.value(),
                'iscilik_m2_fiyat': self.spin_iscilik_fiyat.value()
            }

            # Hesapla
            sonuc = hesapla_yalitim_maliyeti(
                is_listesi=self.is_listesi,
                fiyatlar=fiyatlar
            )

            # Sonuclari goster
            self.son_hesaplama = sonuc
            self._sonuclari_goster(sonuc)
            logger.info(f"Yalitim hesaplama yapildi: {sonuc}")

        except Exception as e:
            logger.error(f"Hesaplama hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Hesaplama sirasinda hata:\n{str(e)}")

    def _sonuclari_goster(self, sonuc: dict):
        """Sonuclari arayuzde goster"""
        metraj = sonuc['metraj_analizi']
        maliyet = sonuc['maliyet_detayi_tl']

        # Metraj Analizi
        bez_data = metraj['bez_membran_rulo']
        self.lbl_bez_net.setText(f"{bez_data['uygulanan_net_alan']:.2f} m2")
        self.lbl_bez_brut.setText(f"{bez_data['satin_alma_metraji_bini_dahil']:.2f} m2")
        self.lbl_toz.setText(f"{metraj['toz_sistem_net_m2']:.2f} m2")
        self.lbl_surme.setText(f"{metraj['surme_sistem_net_m2']:.2f} m2")
        self.lbl_toplam_alan.setText(f"{metraj['toplam_is_alani_m2']:.2f} m2")

        # Maliyet Kirilimi
        self.lbl_bez_tl.setText(f"{maliyet['bez_membran_tutari']:,.2f} TL")
        self.lbl_toz_tl.setText(f"{maliyet['toz_membran_tutari']:,.2f} TL")
        self.lbl_surme_tl.setText(f"{maliyet['surme_membran_tutari']:,.2f} TL")
        self.lbl_astar_tl.setText(f"{maliyet['astar_tutari']:,.2f} TL")
        self.lbl_iscilik_tl.setText(f"{maliyet['iscilik_tutari']:,.2f} TL")

        # Genel Toplam
        self.lbl_toplam.setText(f"{sonuc['genel_toplam_tl']:,.2f} TL")

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
