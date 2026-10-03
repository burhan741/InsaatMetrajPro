"""
Mermer Isleri (Merdiven, Denizlik, Harc) Hesaplama Dialog Penceresi
===================================================================
Kullanici dostu arayuz ile merdiven tasi, denizlik ve harc hesabi.

Yazar: Insaat Metraj Pro
Versiyon: 1.0
"""

from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
    QLabel, QTextEdit, QMessageBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea, QWidget, QFrame,
    QCheckBox, QTabWidget, QSplitter, QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush

from app.core.mermer_hesaplama import (
    hesapla_mermer_isleri_final,
    get_standart_denizlik_boyutlari,
    format_para,
    rapor_olustur,
    VARSAYILAN_FIRE_ORANI,
    merdiven_mermer_metraj_dxf,
    EZDXF_AVAILABLE,
    PANDAS_AVAILABLE,
)


class DenizlikEklemeDialog(QDialog):
    """Denizlik ekleme alt dialogu"""

    def __init__(self, parent=None, denizlik_data: Optional[Dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Denizlik Ekle" if not denizlik_data else "Denizlik Duzenle")
        self.setMinimumWidth(400)
        self.denizlik_data = denizlik_data
        self.init_ui()

        if denizlik_data:
            self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Standart boyutlar
        std_group = QGroupBox("Standart Boyutlar")
        std_layout = QHBoxLayout(std_group)

        self.standart_combo = QComboBox()
        self.standart_combo.addItem("-- Ozel Boyut --", None)
        for std in get_standart_denizlik_boyutlari():
            self.standart_combo.addItem(std['ad'], std)
        self.standart_combo.currentIndexChanged.connect(self.on_standart_selected)
        std_layout.addWidget(self.standart_combo)
        layout.addWidget(std_group)

        # Form
        form = QFormLayout()

        # Aciklama
        self.aciklama_input = QLineEdit()
        self.aciklama_input.setPlaceholderText("Orn: Salon Penceresi")
        form.addRow("Aciklama:", self.aciklama_input)

        # Pencere Eni
        self.en_spin = QDoubleSpinBox()
        self.en_spin.setRange(30, 500)
        self.en_spin.setValue(120)
        self.en_spin.setSuffix(" cm")
        self.en_spin.valueChanged.connect(self.update_hesap)
        form.addRow("Pencere Eni:", self.en_spin)

        # Duvar Kalinligi
        self.kalinlik_spin = QDoubleSpinBox()
        self.kalinlik_spin.setRange(10, 60)
        self.kalinlik_spin.setValue(30)
        self.kalinlik_spin.setSuffix(" cm")
        self.kalinlik_spin.valueChanged.connect(self.update_hesap)
        form.addRow("Duvar Kalinligi:", self.kalinlik_spin)

        # Adet
        self.adet_spin = QSpinBox()
        self.adet_spin.setRange(1, 200)
        self.adet_spin.setValue(1)
        self.adet_spin.valueChanged.connect(self.update_hesap)
        form.addRow("Adet:", self.adet_spin)

        # Hesaplanan degerler
        self.hesap_label = QLabel()
        self.hesap_label.setStyleSheet("color: #4CAF50; font-weight: bold; padding: 10px;")
        self.hesap_label.setWordWrap(True)
        form.addRow("Hesaplanan:", self.hesap_label)

        layout.addLayout(form)

        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Iptal")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Ekle" if not self.denizlik_data else "Guncelle")
        btn_save.clicked.connect(self.accept)
        btn_save.setDefault(True)
        btn_save.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 20px;")
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)
        self.update_hesap()

    def on_standart_selected(self, index):
        """Standart boyut secildiginde"""
        data = self.standart_combo.currentData()
        if data:
            self.en_spin.setValue(data['pencere_en_cm'])
            self.kalinlik_spin.setValue(data['duvar_kalinligi_cm'])
            if not self.aciklama_input.text():
                self.aciklama_input.setText(data['ad'])

    def update_hesap(self):
        """Hesaplanan degerleri goster"""
        en = self.en_spin.value()
        kalinlik = self.kalinlik_spin.value()
        adet = self.adet_spin.value()

        # Kulak ve damlalik paylari
        net_en = en + 10  # +10 cm kulak payi
        net_derinlik = kalinlik + 5  # +5 cm damlalik

        birim_alan = (net_en * net_derinlik) / 10000
        toplam_alan = birim_alan * adet
        toplam_uzunluk = (net_en / 100) * adet

        self.hesap_label.setText(
            f"Net Boyut: {net_en:.0f} x {net_derinlik:.0f} cm\n"
            f"(Kulak +10cm, Damlalik +5cm dahil)\n"
            f"Birim Alan: {birim_alan:.4f} m2\n"
            f"Toplam: {toplam_alan:.3f} m2, {toplam_uzunluk:.2f} mtul"
        )

    def load_data(self):
        """Mevcut veriyi yukle"""
        if self.denizlik_data:
            self.aciklama_input.setText(self.denizlik_data.get('aciklama', ''))
            self.en_spin.setValue(self.denizlik_data.get('pencere_en_cm', 120))
            self.kalinlik_spin.setValue(self.denizlik_data.get('duvar_kalinligi_cm', 30))
            self.adet_spin.setValue(self.denizlik_data.get('adet', 1))

    def get_data(self) -> Dict[str, Any]:
        """Dialog verilerini al"""
        return {
            'aciklama': self.aciklama_input.text().strip() or f"{self.en_spin.value():.0f}cm Pencere",
            'pencere_en_cm': self.en_spin.value(),
            'duvar_kalinligi_cm': self.kalinlik_spin.value(),
            'adet': self.adet_spin.value()
        }


class MermerHesaplamaDialog(QDialog):
    """Ana Mermer Isleri Hesaplama Dialog Penceresi"""

    hesaplama_tamamlandi = pyqtSignal(dict)

    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.db = db
        self.denizlikler = []
        self.son_hesaplama = None

        self.setWindowTitle("Mermer Isleri Hesaplama (Merdiven, Denizlik, Harc)")
        self.setMinimumSize(1150, 850)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Baslik
        baslik = QLabel("MERMER ISLERI HESAPLAMA")
        baslik.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        baslik.setStyleSheet("color: #795548; padding: 10px;")
        main_layout.addWidget(baslik)

        # Ana splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # =====================
        # SOL PANEL - GIRISLER
        # =====================
        sol_widget = QWidget()
        sol_layout = QVBoxLayout(sol_widget)

        # 1. Merdiven Bilgisi
        merdiven_group = QGroupBox("1. Merdiven Bilgisi")
        merdiven_layout = QFormLayout(merdiven_group)

        self.kat_sayisi_spin = QSpinBox()
        self.kat_sayisi_spin.setRange(0, 50)
        self.kat_sayisi_spin.setValue(5)
        self.kat_sayisi_spin.setToolTip("0 girilirse merdiven hesabi yapilmaz")
        merdiven_layout.addRow("Kat Sayisi:", self.kat_sayisi_spin)

        self.basamak_sayisi_spin = QSpinBox()
        self.basamak_sayisi_spin.setRange(10, 25)
        self.basamak_sayisi_spin.setValue(17)
        merdiven_layout.addRow("Kat Basi Basamak:", self.basamak_sayisi_spin)

        self.basamak_genislik_spin = QDoubleSpinBox()
        self.basamak_genislik_spin.setRange(80, 200)
        self.basamak_genislik_spin.setValue(120)
        self.basamak_genislik_spin.setSuffix(" cm")
        merdiven_layout.addRow("Basamak Genisligi:", self.basamak_genislik_spin)

        self.sahanlik_spin = QDoubleSpinBox()
        self.sahanlik_spin.setRange(0, 100)
        self.sahanlik_spin.setValue(8.0)
        self.sahanlik_spin.setSuffix(" m2")
        self.sahanlik_spin.setToolTip("Tum donuslerdeki duz alanlarin toplami")
        merdiven_layout.addRow("Sahanlik Alani:", self.sahanlik_spin)

        # Merdiven ozeti
        self.merdiven_ozet_label = QLabel()
        self.merdiven_ozet_label.setStyleSheet("color: #666; font-style: italic;")
        merdiven_layout.addRow("", self.merdiven_ozet_label)

        self.kat_sayisi_spin.valueChanged.connect(self.update_merdiven_ozet)
        self.basamak_sayisi_spin.valueChanged.connect(self.update_merdiven_ozet)
        self.update_merdiven_ozet()

        sol_layout.addWidget(merdiven_group)

        # 2. Denizlik Listesi
        denizlik_group = QGroupBox("2. Denizlik Listesi")
        denizlik_layout = QVBoxLayout(denizlik_group)

        self.denizlik_table = QTableWidget()
        self.denizlik_table.setColumnCount(5)
        self.denizlik_table.setHorizontalHeaderLabels([
            "Aciklama", "Pencere En", "Duvar Kal.", "Adet", "Alan (m2)"
        ])
        self.denizlik_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.denizlik_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.denizlik_table.setMinimumHeight(120)
        denizlik_layout.addWidget(self.denizlik_table)

        # Denizlik butonlari
        denizlik_btn_layout = QHBoxLayout()

        btn_denizlik_ekle = QPushButton("+ Denizlik Ekle")
        btn_denizlik_ekle.clicked.connect(self.denizlik_ekle)
        btn_denizlik_ekle.setStyleSheet("background-color: #795548; color: white;")
        denizlik_btn_layout.addWidget(btn_denizlik_ekle)

        btn_denizlik_duzenle = QPushButton("Duzenle")
        btn_denizlik_duzenle.clicked.connect(self.denizlik_duzenle)
        denizlik_btn_layout.addWidget(btn_denizlik_duzenle)

        btn_denizlik_sil = QPushButton("Sil")
        btn_denizlik_sil.clicked.connect(self.denizlik_sil)
        btn_denizlik_sil.setStyleSheet("background-color: #f44336; color: white;")
        denizlik_btn_layout.addWidget(btn_denizlik_sil)

        denizlik_btn_layout.addStretch()
        denizlik_layout.addLayout(denizlik_btn_layout)

        self.denizlik_ozet_label = QLabel("Toplam: 0 denizlik")
        self.denizlik_ozet_label.setStyleSheet("color: #666; font-style: italic;")
        denizlik_layout.addWidget(self.denizlik_ozet_label)

        sol_layout.addWidget(denizlik_group)

        # 3. Fiyatlar
        fiyat_group = QGroupBox("3. Birim Fiyatlar")
        fiyat_layout = QFormLayout(fiyat_group)

        self.mermer_fiyat_spin = QDoubleSpinBox()
        self.mermer_fiyat_spin.setRange(100, 10000)
        self.mermer_fiyat_spin.setValue(850)
        self.mermer_fiyat_spin.setSuffix(" TL/m2")
        fiyat_layout.addRow("Mermer/Tas m2:", self.mermer_fiyat_spin)

        self.iscilik_basamak_spin = QDoubleSpinBox()
        self.iscilik_basamak_spin.setRange(50, 1000)
        self.iscilik_basamak_spin.setValue(150)
        self.iscilik_basamak_spin.setSuffix(" TL/adet")
        fiyat_layout.addRow("Iscilik (Basamak):", self.iscilik_basamak_spin)

        self.iscilik_mtul_spin = QDoubleSpinBox()
        self.iscilik_mtul_spin.setRange(50, 500)
        self.iscilik_mtul_spin.setValue(120)
        self.iscilik_mtul_spin.setSuffix(" TL/mtul")
        fiyat_layout.addRow("Iscilik (Denizlik):", self.iscilik_mtul_spin)

        self.kum_fiyat_spin = QDoubleSpinBox()
        self.kum_fiyat_spin.setRange(100, 2000)
        self.kum_fiyat_spin.setValue(650)
        self.kum_fiyat_spin.setSuffix(" TL/m3")
        fiyat_layout.addRow("Kum m3:", self.kum_fiyat_spin)

        self.cimento_fiyat_spin = QDoubleSpinBox()
        self.cimento_fiyat_spin.setRange(50, 500)
        self.cimento_fiyat_spin.setValue(180)
        self.cimento_fiyat_spin.setSuffix(" TL/torba")
        fiyat_layout.addRow("Cimento (50kg):", self.cimento_fiyat_spin)

        sol_layout.addWidget(fiyat_group)

        # 4. Parametreler
        param_group = QGroupBox("4. Parametreler")
        param_layout = QFormLayout(param_group)

        self.asansor_check = QCheckBox("Asansor Aktif (Yuk tasima icin)")
        self.asansor_check.setChecked(True)
        self.asansor_check.setToolTip("Isaretli degilse iscilige %20 hamaliye farki eklenir")
        param_layout.addRow("", self.asansor_check)

        self.fire_spin = QDoubleSpinBox()
        self.fire_spin.setRange(0, 0.30)
        self.fire_spin.setValue(VARSAYILAN_FIRE_ORANI)
        self.fire_spin.setSingleStep(0.01)
        self.fire_spin.setDecimals(2)
        param_layout.addRow("Fire Orani:", self.fire_spin)

        sol_layout.addWidget(param_group)

        # Hesapla butonu
        self.btn_hesapla = QPushButton("HESAPLA")
        self.btn_hesapla.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.btn_hesapla.setMinimumHeight(50)
        self.btn_hesapla.setStyleSheet("""
            QPushButton {
                background-color: #795548;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5D4037;
            }
        """)
        self.btn_hesapla.clicked.connect(self.hesapla)
        sol_layout.addWidget(self.btn_hesapla)

        sol_layout.addStretch()
        splitter.addWidget(sol_widget)

        # ======================
        # SAG PANEL - SONUCLAR
        # ======================
        sag_widget = QWidget()
        sag_layout = QVBoxLayout(sag_widget)

        self.tab_widget = QTabWidget()

        # Tab 1: Ozet Rapor
        ozet_tab = QWidget()
        ozet_layout = QVBoxLayout(ozet_tab)
        self.ozet_text = QTextEdit()
        self.ozet_text.setReadOnly(True)
        self.ozet_text.setFont(QFont("Consolas", 10))
        self.ozet_text.setPlaceholderText("Hesaplama sonuclari burada gorunecek...")
        ozet_layout.addWidget(self.ozet_text)
        self.tab_widget.addTab(ozet_tab, "Ozet Rapor")

        # Tab 2: Merdiven Detay
        merdiven_tab = QWidget()
        merdiven_tab_layout = QVBoxLayout(merdiven_tab)
        self.merdiven_detay_text = QTextEdit()
        self.merdiven_detay_text.setReadOnly(True)
        self.merdiven_detay_text.setFont(QFont("Consolas", 10))
        merdiven_tab_layout.addWidget(self.merdiven_detay_text)
        self.tab_widget.addTab(merdiven_tab, "Merdiven Detay")

        # Tab 3: Denizlik Detay
        denizlik_tab = QWidget()
        denizlik_tab_layout = QVBoxLayout(denizlik_tab)
        self.denizlik_detay_table = QTableWidget()
        self.denizlik_detay_table.setColumnCount(7)
        self.denizlik_detay_table.setHorizontalHeaderLabels([
            "Aciklama", "Pencere En", "Net En", "Net Derinlik", "Adet", "Alan m2", "Uzunluk m"
        ])
        self.denizlik_detay_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        denizlik_tab_layout.addWidget(self.denizlik_detay_table)
        self.tab_widget.addTab(denizlik_tab, "Denizlik Detay")

        # Tab 4: Malzeme ve Harc
        malzeme_tab = QWidget()
        malzeme_layout = QVBoxLayout(malzeme_tab)
        self.malzeme_text = QTextEdit()
        self.malzeme_text.setReadOnly(True)
        self.malzeme_text.setFont(QFont("Consolas", 11))
        malzeme_layout.addWidget(self.malzeme_text)
        self.tab_widget.addTab(malzeme_tab, "Malzeme/Harc")

        # Tab 5: Maliyet
        maliyet_tab = QWidget()
        maliyet_layout = QVBoxLayout(maliyet_tab)
        self.maliyet_text = QTextEdit()
        self.maliyet_text.setReadOnly(True)
        self.maliyet_text.setFont(QFont("Consolas", 11))
        maliyet_layout.addWidget(self.maliyet_text)
        self.tab_widget.addTab(maliyet_tab, "Maliyet")

        # Tab 6: DXF Metraj
        dxf_tab = QWidget()
        dxf_tab_layout = QVBoxLayout(dxf_tab)

        # DXF dosya seçimi
        dxf_dosya_group = QGroupBox("DXF Dosyasi ve Ayarlar")
        dxf_dosya_form = QFormLayout(dxf_dosya_group)

        dxf_dosya_row = QHBoxLayout()
        self.dxf_path_edit = QLineEdit()
        self.dxf_path_edit.setPlaceholderText("DXF dosyasi seciniz...")
        self.dxf_path_edit.setReadOnly(True)
        dxf_dosya_row.addWidget(self.dxf_path_edit)
        btn_dxf_sec = QPushButton("Gozat...")
        btn_dxf_sec.clicked.connect(self.dxf_dosya_sec)
        btn_dxf_sec.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        dxf_dosya_row.addWidget(btn_dxf_sec)
        dxf_dosya_form.addRow("DXF Dosyasi:", dxf_dosya_row)

        self.dxf_layer_edit = QLineEdit("A-MERMER")
        self.dxf_layer_edit.setToolTip("Merdiven mermer cizimlerinin bulundugu layer ismi")
        dxf_dosya_form.addRow("Layer Adı:", self.dxf_layer_edit)

        dxf_birim_row = QHBoxLayout()
        self.dxf_birim_combo = QComboBox()
        self.dxf_birim_combo.addItems(["cm", "mm", "m"])
        self.dxf_birim_combo.setCurrentText("cm")
        self.dxf_birim_combo.setToolTip("Cizim birimi (cogu AutoCAD cizimi cm'dir)")
        dxf_birim_row.addWidget(self.dxf_birim_combo)
        dxf_birim_row.addStretch()
        dxf_dosya_form.addRow("Cizim Birimi:", dxf_birim_row)

        self.dxf_riht_spin = QDoubleSpinBox()
        self.dxf_riht_spin.setRange(0.10, 0.25)
        self.dxf_riht_spin.setValue(0.16)
        self.dxf_riht_spin.setSingleStep(0.01)
        self.dxf_riht_spin.setSuffix(" m")
        self.dxf_riht_spin.setToolTip("Standart: 16 cm")
        dxf_dosya_form.addRow("Riht Yüksekliği:", self.dxf_riht_spin)

        self.dxf_basamak_spin = QDoubleSpinBox()
        self.dxf_basamak_spin.setRange(0.25, 0.40)
        self.dxf_basamak_spin.setValue(0.30)
        self.dxf_basamak_spin.setSingleStep(0.01)
        self.dxf_basamak_spin.setSuffix(" m")
        self.dxf_basamak_spin.setToolTip("Standart: 30 cm (baskisi/basamak genisligi)")
        dxf_dosya_form.addRow("Basamak Derinliği:", self.dxf_basamak_spin)

        dxf_tab_layout.addWidget(dxf_dosya_group)

        btn_dxf_hesapla = QPushButton("DXF'den Metraj Hesapla")
        btn_dxf_hesapla.setMinimumHeight(40)
        btn_dxf_hesapla.setStyleSheet("background-color: #795548; color: white; font-weight: bold;")
        btn_dxf_hesapla.clicked.connect(self.dxf_metraj_hesapla)
        dxf_tab_layout.addWidget(btn_dxf_hesapla)

        # DXF sonuç tablosu
        self.dxf_sonuc_table = QTableWidget()
        self.dxf_sonuc_table.setColumnCount(8)
        self.dxf_sonuc_table.setHorizontalHeaderLabels([
            "Tip", "No", "Uzunluk/Cevre (m)", "Basamak Alan (m2)",
            "Riht Alan (m2)", "Toplam Alan (m2)", "Hacim (m3)", "Limonluk (mtul)"
        ])
        self.dxf_sonuc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dxf_sonuc_table.setAlternatingRowColors(True)
        dxf_tab_layout.addWidget(self.dxf_sonuc_table)

        # DXF özet label
        self.dxf_ozet_label = QLabel("DXF dosyasi secip 'Hesapla' butonuna basin.")
        self.dxf_ozet_label.setStyleSheet("color: #aaa; padding: 6px;")
        dxf_tab_layout.addWidget(self.dxf_ozet_label)

        _dxf_ok = EZDXF_AVAILABLE and PANDAS_AVAILABLE
        _dxf_tab_title = "DXF Metraj" if _dxf_ok else "DXF Metraj (ezdxf gerekli)"
        self.tab_widget.addTab(dxf_tab, _dxf_tab_title)

        sag_layout.addWidget(self.tab_widget)

        # Export butonlari
        export_layout = QHBoxLayout()

        btn_excel = QPushButton("Excel'e Aktar")
        btn_excel.clicked.connect(self.export_excel)
        export_layout.addWidget(btn_excel)

        btn_metraj = QPushButton("Metraja Ekle")
        btn_metraj.clicked.connect(self.metraja_ekle)
        btn_metraj.setStyleSheet("background-color: #4CAF50; color: white;")
        export_layout.addWidget(btn_metraj)

        sag_layout.addLayout(export_layout)

        splitter.addWidget(sag_widget)
        splitter.setSizes([420, 730])

        main_layout.addWidget(splitter)

        # Alt butonlar
        bottom_layout = QHBoxLayout()

        btn_yardim = QPushButton("? Yardım")
        btn_yardim.setToolTip("Kullanım kılavuzu")
        btn_yardim.clicked.connect(self.yardim_goster)
        btn_yardim.setStyleSheet("background-color: #37474F; color: white; padding: 6px 14px;")
        bottom_layout.addWidget(btn_yardim)

        bottom_layout.addStretch()
        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close)
        bottom_layout.addWidget(btn_kapat)
        main_layout.addLayout(bottom_layout)

    def update_merdiven_ozet(self):
        """Merdiven ozetini guncelle"""
        kat = self.kat_sayisi_spin.value()
        basamak = self.basamak_sayisi_spin.value()
        toplam = kat * basamak
        self.merdiven_ozet_label.setText(f"Toplam: {toplam} basamak" if kat > 0 else "Merdiven hesabi yapilmayacak")

    def denizlik_ekle(self):
        """Yeni denizlik ekle"""
        dialog = DenizlikEklemeDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            self.denizlikler.append(data)
            self.denizlik_tablosunu_guncelle()

    def denizlik_duzenle(self):
        """Secili denizligi duzenle"""
        row = self.denizlik_table.currentRow()
        if row < 0 or row >= len(self.denizlikler):
            QMessageBox.warning(self, "Uyari", "Lutfen duzenlenecek denizligi secin!")
            return

        dialog = DenizlikEklemeDialog(self, self.denizlikler[row])
        if dialog.exec():
            self.denizlikler[row] = dialog.get_data()
            self.denizlik_tablosunu_guncelle()

    def denizlik_sil(self):
        """Secili denizligi sil"""
        row = self.denizlik_table.currentRow()
        if row < 0 or row >= len(self.denizlikler):
            QMessageBox.warning(self, "Uyari", "Lutfen silinecek denizligi secin!")
            return

        reply = QMessageBox.question(
            self, "Onay",
            f"'{self.denizlikler[row]['aciklama']}' denizligini silmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            del self.denizlikler[row]
            self.denizlik_tablosunu_guncelle()

    def denizlik_tablosunu_guncelle(self):
        """Denizlik tablosunu guncelle"""
        self.denizlik_table.setRowCount(len(self.denizlikler))

        toplam_alan = 0
        toplam_adet = 0

        for row, d in enumerate(self.denizlikler):
            net_en = d['pencere_en_cm'] + 10
            net_derinlik = d['duvar_kalinligi_cm'] + 5
            alan = (net_en * net_derinlik) / 10000 * d['adet']
            toplam_alan += alan
            toplam_adet += d['adet']

            self.denizlik_table.setItem(row, 0, QTableWidgetItem(d['aciklama']))
            self.denizlik_table.setItem(row, 1, QTableWidgetItem(f"{d['pencere_en_cm']:.0f} cm"))
            self.denizlik_table.setItem(row, 2, QTableWidgetItem(f"{d['duvar_kalinligi_cm']:.0f} cm"))
            self.denizlik_table.setItem(row, 3, QTableWidgetItem(str(d['adet'])))
            self.denizlik_table.setItem(row, 4, QTableWidgetItem(f"{alan:.3f}"))

        self.denizlik_ozet_label.setText(f"Toplam: {toplam_adet} denizlik, {toplam_alan:.3f} m2")

    def hesapla(self):
        """Hesaplamayi calistir"""
        kat_sayisi = self.kat_sayisi_spin.value()

        if kat_sayisi == 0 and len(self.denizlikler) == 0:
            QMessageBox.warning(self, "Uyari", "En az merdiven veya denizlik bilgisi girilmeli!")
            return

        try:
            merdiven_bilgisi = None
            if kat_sayisi > 0:
                merdiven_bilgisi = {
                    'kat_sayisi': kat_sayisi,
                    'kat_basi_basamak_sayisi': self.basamak_sayisi_spin.value(),
                    'basamak_genisligi_cm': self.basamak_genislik_spin.value(),
                    'sahanlik_m2': self.sahanlik_spin.value()
                }

            sonuc = hesapla_mermer_isleri_final(
                merdiven_bilgisi=merdiven_bilgisi,
                denizlik_listesi=self.denizlikler,
                mermer_m2_fiyat=self.mermer_fiyat_spin.value(),
                mermer_iscilik_basamak_fiyat=self.iscilik_basamak_spin.value(),
                mermer_iscilik_mtul_fiyat=self.iscilik_mtul_spin.value(),
                kum_m3_fiyat=self.kum_fiyat_spin.value(),
                cimento_torba_fiyat=self.cimento_fiyat_spin.value(),
                asansor_aktif_mi=self.asansor_check.isChecked(),
                fire_orani=self.fire_spin.value()
            )

            self.son_hesaplama = sonuc
            self.sonuclari_goster(sonuc)
            self.hesaplama_tamamlandi.emit(sonuc)

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Hesaplama hatasi:\n{str(e)}")

    def sonuclari_goster(self, sonuc: Dict):
        """Hesaplama sonuclarini goster"""

        # 1. Ozet Rapor
        self.ozet_text.setPlainText(rapor_olustur(sonuc))

        # 2. Merdiven Detay
        md = sonuc['merdiven_detay']
        if md['toplam_basamak'] > 0:
            merdiven_text = []
            merdiven_text.append("MERDIVEN TASI HESABI")
            merdiven_text.append("=" * 50)
            merdiven_text.append(f"Kat Sayisi: {md['kat_sayisi']}")
            merdiven_text.append(f"Kat Basi Basamak: {md['kat_basi_basamak']} adet")
            merdiven_text.append(f"TOPLAM BASAMAK: {md['toplam_basamak']} adet")
            merdiven_text.append(f"Basamak Genisligi: {md['basamak_genisligi_cm']:.0f} cm")
            merdiven_text.append("")
            merdiven_text.append("ALAN HESABI:")
            merdiven_text.append(f" Tek Basamak = (0.33m + 0.16m) x {md['basamak_genisligi_cm']/100:.2f}m")
            merdiven_text.append(f" = {md.get('tek_basamak_m2', 0):.4f} m2")
            merdiven_text.append("")
            merdiven_text.append(f" Basamak+Riht Alani : {md['basamak_alani_m2']:>10.2f} m2")
            merdiven_text.append(f" Supurgelik (%20) : {md['supurgelik_alani_m2']:>10.2f} m2")
            merdiven_text.append(f" Sahanlik : {md['sahanlik_alani_m2']:>10.2f} m2")
            merdiven_text.append("-" * 50)
            merdiven_text.append(f" MERDIVEN TOPLAM : {md['toplam_merdiven_m2']:>10.2f} m2")
            self.merdiven_detay_text.setPlainText("\n".join(merdiven_text))
        else:
            self.merdiven_detay_text.setPlainText("Merdiven hesabi yapilmadi.")

        # 3. Denizlik Detay Tablosu
        dd = sonuc['denizlik_detay']
        self.denizlik_detay_table.setRowCount(len(dd))
        for row, d in enumerate(dd):
            self.denizlik_detay_table.setItem(row, 0, QTableWidgetItem(d['aciklama']))
            self.denizlik_detay_table.setItem(row, 1, QTableWidgetItem(f"{d['pencere_en_cm']:.0f} cm"))
            self.denizlik_detay_table.setItem(row, 2, QTableWidgetItem(f"{d['net_en_cm']:.0f} cm"))
            self.denizlik_detay_table.setItem(row, 3, QTableWidgetItem(f"{d['net_derinlik_cm']:.0f} cm"))
            self.denizlik_detay_table.setItem(row, 4, QTableWidgetItem(str(d['adet'])))
            self.denizlik_detay_table.setItem(row, 5, QTableWidgetItem(f"{d['toplam_alan_m2']:.4f}"))
            self.denizlik_detay_table.setItem(row, 6, QTableWidgetItem(f"{d['toplam_uzunluk_m']:.2f}"))

        # 4. Malzeme ve Harc
        malzeme_text = []
        malzeme_text.append("MALZEME VE HARC SARFIYATI")
        malzeme_text.append("=" * 50)
        malzeme_text.append("")
        malzeme_text.append("SIPARIS MIKTARLARI (Fire Dahil):")
        malzeme_text.append(f" Fire Orani: %{sonuc['parametreler']['fire_orani']*100:.0f}")
        malzeme_text.append("")
        malzeme_text.append(f" Mermer/Tas : {sonuc['gereken_mermer_m2']:>10.2f} m2")
        malzeme_text.append(f" Kum : {sonuc['gereken_kum_m3']:>10.3f} m3")
        malzeme_text.append(f" Cimento : {sonuc['gereken_cimento_torba']:>10} torba")
        malzeme_text.append("")
        malzeme_text.append("-" * 50)
        malzeme_text.append("HARC SARFIYAT DETAYI:")
        malzeme_text.append("")
        hd = sonuc['harc_detay']
        if hd['merdiven']['alan_m2'] > 0:
            malzeme_text.append(f"Merdiven ({hd['merdiven']['tip']}):")
            malzeme_text.append(f" Alan: {hd['merdiven']['alan_m2']:.2f} m2")
            malzeme_text.append(f" Kum: {hd['merdiven']['kum_m3']:.3f} m3 (0.05 m3/m2)")
            malzeme_text.append(f" Cimento: {hd['merdiven']['cimento_torba']:.1f} torba (1.2 torba/m2)")
            malzeme_text.append("")
        if hd['denizlik']['alan_m2'] > 0:
            malzeme_text.append(f"Denizlik ({hd['denizlik']['tip']}):")
            malzeme_text.append(f" Alan: {hd['denizlik']['alan_m2']:.2f} m2")
            malzeme_text.append(f" Kum: {hd['denizlik']['kum_m3']:.3f} m3 (0.025 m3/m2)")
            malzeme_text.append(f" Cimento: {hd['denizlik']['cimento_torba']:.1f} torba (0.5 torba/m2)")
        self.malzeme_text.setPlainText("\n".join(malzeme_text))

        # 5. Maliyet
        maliyet_text = []
        maliyet_text.append("MALIYET HESABI")
        maliyet_text.append("=" * 50)
        maliyet_text.append("")

        iscilik_d = sonuc['iscilik_detay']
        maliyet_text.append(f"Asansor: {'AKTIF' if iscilik_d['asansor_aktif'] else 'YOK (Hamaliye +%20)'}")
        maliyet_text.append("")

        maliyet_text.append("ISCILIK:")
        if iscilik_d['basamak_sayisi'] > 0:
            maliyet_text.append(f" Merdiven: {iscilik_d['basamak_sayisi']} basamak x {format_para(iscilik_d['basamak_birim_fiyat'])}")
            maliyet_text.append(f" = {format_para(iscilik_d['basamak_iscilik_tl'])}")
        if iscilik_d['denizlik_mtul'] > 0:
            maliyet_text.append(f" Denizlik: {iscilik_d['denizlik_mtul']:.2f} mtul x {format_para(iscilik_d['denizlik_birim_fiyat'])}")
            maliyet_text.append(f" = {format_para(iscilik_d['denizlik_iscilik_tl'])}")
        if iscilik_d['hamaliye_farki_tl'] > 0:
            maliyet_text.append(f" Hamaliye Farki: {format_para(iscilik_d['hamaliye_farki_tl'])}")
        maliyet_text.append(f" ISCILIK TOPLAM: {format_para(iscilik_d['final_toplam_tl'])}")
        maliyet_text.append("")

        sd = sonuc['sure_detay']
        maliyet_text.append(f"SURE: {sd['final_sure_gun']} is gunu")
        maliyet_text.append(f" (Merdiven: {sd['merdiven_gun']:.1f}, Denizlik: {sd['denizlik_gun']:.1f} gun)")
        maliyet_text.append("")

        m = sonuc['maliyet_detayi']
        maliyet_text.append("-" * 50)
        maliyet_text.append("MALIYET OZETI:")
        maliyet_text.append(f" Tas Maliyeti : {format_para(m['tas_maliyeti_tl']):>20}")
        maliyet_text.append(f" Harc Maliyeti : {format_para(m['harc_maliyeti_tl']):>20}")
        maliyet_text.append(f" - Kum : {format_para(m['kum_maliyeti_tl']):>20}")
        maliyet_text.append(f" - Cimento : {format_para(m['cimento_maliyeti_tl']):>20}")
        maliyet_text.append(f" Iscilik : {format_para(m['iscilik_maliyeti_tl']):>20}")
        maliyet_text.append("=" * 50)
        maliyet_text.append(f" GENEL TOPLAM : {format_para(m['genel_toplam_tl']):>20}")

        self.maliyet_text.setPlainText("\n".join(maliyet_text))

        # Ozet tab'a gec
        self.tab_widget.setCurrentIndex(0)

    def export_excel(self):
        """Excel'e aktar"""
        if not self.son_hesaplama:
            QMessageBox.warning(self, "Uyari", "Once hesaplama yapmalisiniz!")
            return

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font

            file_path, _ = QFileDialog.getSaveFileName(
                self, "Excel Kaydet", "mermer_isleri_raporu.xlsx",
                "Excel Dosyasi (*.xlsx)"
            )

            if not file_path:
                return

            wb = Workbook()
            ws = wb.active
            ws.title = "Mermer Isleri"

            ws['A1'] = "MERMER ISLERI HESAPLAMA RAPORU"
            ws['A1'].font = Font(bold=True, size=14)
            ws.merge_cells('A1:E1')

            sonuc = self.son_hesaplama
            row = 3

            ws[f'A{row}'] = "OZET BILGILER"
            ws[f'A{row}'].font = Font(bold=True)
            row += 1

            ozet = [
                ("Toplam Basamak", f"{sonuc['toplam_basamak_adet']} adet"),
                ("Toplam Denizlik", f"{sonuc['toplam_denizlik_adet']} adet, {sonuc['toplam_denizlik_mtul']:.2f} mtul"),
                ("Gereken Mermer", f"{sonuc['gereken_mermer_m2']:.2f} m2"),
                ("Gereken Kum", f"{sonuc['gereken_kum_m3']:.3f} m3"),
                ("Gereken Cimento", f"{sonuc['gereken_cimento_torba']} torba"),
                ("Tahmini Sure", f"{sonuc['tahmini_sure_gun']} gun"),
            ]

            for ad, deger in ozet:
                ws[f'A{row}'] = ad
                ws[f'B{row}'] = deger
                row += 1

            row += 1
            ws[f'A{row}'] = "MALIYET"
            ws[f'A{row}'].font = Font(bold=True)
            row += 1

            m = sonuc['maliyet_detayi']
            maliyet = [
                ("Tas Maliyeti", f"{m['tas_maliyeti_tl']:,.2f} TL"),
                ("Harc Maliyeti", f"{m['harc_maliyeti_tl']:,.2f} TL"),
                ("Iscilik Maliyeti", f"{m['iscilik_maliyeti_tl']:,.2f} TL"),
                ("GENEL TOPLAM", f"{m['genel_toplam_tl']:,.2f} TL"),
            ]

            for ad, deger in maliyet:
                ws[f'A{row}'] = ad
                ws[f'B{row}'] = deger
                if ad == "GENEL TOPLAM":
                    ws[f'A{row}'].font = Font(bold=True)
                    ws[f'B{row}'].font = Font(bold=True)
                row += 1

            ws.column_dimensions['A'].width = 25
            ws.column_dimensions['B'].width = 20

            wb.save(file_path)
            QMessageBox.information(self, "Basarili", f"Rapor kaydedildi:\n{file_path}")

        except ImportError:
            QMessageBox.warning(self, "Hata", "Excel export icin 'openpyxl' kutuphanesi gerekli!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel kaydetme hatasi:\n{str(e)}")

    def metraja_ekle(self):
        """Metraja ekle"""
        if not self.son_hesaplama:
            QMessageBox.warning(self, "Uyari", "Once hesaplama yapmalisiniz!")
            return

        self.hesaplama_tamamlandi.emit(self.son_hesaplama)
        QMessageBox.information(
            self, "Basarili",
            f"Mermer isleri metraja eklendi:\n"
            f"Tas: {self.son_hesaplama['gereken_mermer_m2']:.2f} m2\n"
            f"Toplam: {format_para(self.son_hesaplama['maliyet_detayi']['genel_toplam_tl'])}"
        )

    # ── DXF Metraj ────────────────────────────────────────────────────────────

    def dxf_dosya_sec(self):
        """DXF dosyası seç"""
        path, _ = QFileDialog.getOpenFileName(
            self, "DXF Dosyasi Sec", "", "DXF Dosyalari (*.dxf);;Tum Dosyalar (*)"
        )
        if path:
            self.dxf_path_edit.setText(path)

    def dxf_metraj_hesapla(self):
        """DXF'den merdiven mermer metrajını hesapla"""
        if not EZDXF_AVAILABLE:
            QMessageBox.warning(
                self, "Eksik Kutüphane",
                "DXF metraj için 'ezdxf' kütüphanesi gerekli.\nKurulum: pip install ezdxf"
            )
            return
        if not PANDAS_AVAILABLE:
            QMessageBox.warning(
                self, "Eksik Kütüphane",
                "DXF metraj için 'pandas' kütüphanesi gerekli.\nKurulum: pip install pandas"
            )
            return

        dxf_path = self.dxf_path_edit.text().strip()
        if not dxf_path:
            QMessageBox.warning(self, "Uyari", "Lutfen DXF dosyasi seciniz!")
            return

        layer = self.dxf_layer_edit.text().strip() or "A-MERMER"
        birim = self.dxf_birim_combo.currentText()
        riht = self.dxf_riht_spin.value()
        basamak_d = self.dxf_basamak_spin.value()

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            df = merdiven_mermer_metraj_dxf(
                dxf_path=dxf_path,
                layer_name=layer,
                riht_yuksekligi=riht,
                basamak_genisligi=basamak_d,
                cizim_birimi=birim,
            )
        except FileNotFoundError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Dosya Bulunamadı", str(e))
            return
        except RuntimeError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "DXF Okuma Hatası", str(e))
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Hata", f"DXF metraj hatası:\n{str(e)}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        # Tabloyu doldur
        self.dxf_sonuc_table.blockSignals(True)
        self.dxf_sonuc_table.setRowCount(0)

        if df.empty:
            self.dxf_ozet_label.setText(
                f"'{layer}' layer'ında hiç merdiven entity bulunamadı. "
                "Layer adını kontrol ediniz."
            )
            self.dxf_sonuc_table.blockSignals(False)
            return

        self.dxf_sonuc_table.setRowCount(len(df))
        sutunlar = [
            "Tip", "No", "Uzunluk/Cevre (m)", "Basamak Alani (m2)",
            "Riht Alani (m2)", "Toplam Alan (m2)", "Hacim (m3)", "Limonluk (mtul)"
        ]
        for row_idx, row_data in df.iterrows():
            for col_idx, col in enumerate(sutunlar):
                val = row_data.get(col, "")
                item = QTableWidgetItem(str(val) if val != "" else "")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # Toplam satırlarını kalın yap
                tip = str(row_data.get("Tip", ""))
                if "Toplam" in tip or tip == "TOPLAM":
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor("#FFD700"))
                self.dxf_sonuc_table.setItem(row_idx, col_idx, item)

        self.dxf_sonuc_table.blockSignals(False)

        # Özet
        try:
            toplam_row = df[df["Tip"] == "TOPLAM"].iloc[0]
            toplam_alan = toplam_row["Toplam Alan (m2)"]
            limonluk = toplam_row["Limonluk (mtul)"]
            basamak_sayisi = len(df[df["Tip"] == "Basamak"])
            sahanlik_sayisi = len(df[df["Tip"] == "Sahanlik"])
            self.dxf_ozet_label.setText(
                f"Sonuç: {basamak_sayisi} basamak + {sahanlik_sayisi} sahanlık  |  "
                f"Toplam Alan: {toplam_alan:.4f} m2  |  "
                f"Limonluk: {limonluk:.3f} mtul"
            )
            self.dxf_ozet_label.setStyleSheet("color: #4CAF50; font-weight: bold; padding: 6px;")
        except Exception:
            self.dxf_ozet_label.setText("Hesaplama tamamlandı.")

        # DXF sekmesine geç
        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)

    # ── Yardım ────────────────────────────────────────────────────────────────

    def yardim_goster(self):
        """Kullanım kılavuzunu göster"""
        kilavuz = """
MERMER İŞLERİ HESAPLAMA — KULLANIM KILAVUZU
============================================================

📐 1. MERDİVEN BİLGİSİ
  • Kat Sayısı    : Binanın kat adedi (0 girilirse merdiven hesaplanmaz)
  • Kat Başı Basamak : Genellikle 15–18 adet (standart: 17)
  • Basamak Genişliği : Mermer taşının boyu (cm) — genellikle 120 cm
  • Sahanlık Alanı : Tüm katlardaki dönüş sahanlıklarının toplam m2'si

  Hesaplama: (0.33m + 0.16m) × genişlik = tek basamak m2
  Süpürgelik: Basamak alanının %20'si otomatik eklenir

🪟 2. DENİZLİK LİSTESİ
  • "+ Denizlik Ekle" ile her pencere tipi için ayrı kayıt girin
  • Kulak Payı: +10 cm (5 sağ + 5 sol) otomatik eklenir
  • Damlalık Payı: +5 cm (dışa taşma) otomatik eklenir

💰 3. BİRİM FİYATLAR
  • Mermer/Taş m2  : Malzeme fiyatı (işçilik dahil değil)
  • İşçilik (Basamak) : Basamak başına (adet)
  • İşçilik (Denizlik) : Metre uzunluk başına

⚙️ 4. PARAMETRELER
  • Asansör Aktif  : İşaretliyse normal tempo; değilse %20 hamaliye zammı
  • Fire Oranı    : Sipariş miktarına eklenen fire (varsayılan %10)

📄 5. SEKME AÇIKLAMALARI
  • Özet Rapor    : Tüm hesaplamanın yazılı çıktısı
  • Merdiven Detay : Adım adım alan hesabı
  • Denizlik Detay : Her pencere boyutunun tablosu
  • Malzeme/Harç  : Fire dahil sipariş miktarları + harç sarfiyatı
  • Maliyet      : İşçilik, malzeme ve genel toplam
  • DXF Metraj   : AutoCAD çiziminden otomatik metraj

📁 6. DXF METRAJ (AutoCAD)
  • DXF dosyanızdaki merdiven mermer çizimlerini seçin
  • Layer adını doğru girin (genellikle "A-MERMER")
  • LINE entity → basamak kenarları
  • Kapalı LWPOLYLINE → sahanlık alanları

📊 7. DIŞA AKTARMA
  • "Excel'e Aktar" : .xlsx formatında rapor
  • "Metraja Ekle"  : Sonuçları ana program metraj listesine aktarır
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("Mermer İşleri Hesaplama — Yardım")
        msg.setText(kilavuz)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setMinimumWidth(700)
        msg.exec()


# Test
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    dialog = MermerHesaplamaDialog()
    dialog.show()

    sys.exit(app.exec())
