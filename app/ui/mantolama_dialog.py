"""
Dış Cephe Mantolama Hesaplama Dialog Penceresi
==============================================
Kullanıcı dostu arayüz ile Minha hesabı ve maliyet analizi.

Yazar: İnşaat Metraj Pro
Versiyon: 1.0
"""

import json
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
    QLabel, QTextEdit, QMessageBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea, QWidget, QFrame,
    QCheckBox, QTabWidget, QSplitter, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush

from app.core.mantolama_hesaplama import (
    hesapla_mantolama_minhali,
    get_standart_bosluklar,
    VARSAYILAN_FIYATLAR,
    VARSAYILAN_MINHA_LIMITI_M2
)


class BoslukEklemeDialog(QDialog):
    """Boşluk (Pencere/Kapı) ekleme alt dialogu"""

    def __init__(self, parent=None, bosluk_data: Optional[Dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Boşluk Ekle" if not bosluk_data else "Boşluk Düzenle")
        self.setMinimumWidth(400)
        self.bosluk_data = bosluk_data
        self.init_ui()

        if bosluk_data:
            self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Standart boyutlar
        std_group = QGroupBox("Standart Boyutlar")
        std_layout = QHBoxLayout(std_group)

        self.standart_combo = QComboBox()
        self.standart_combo.addItem("-- Özel Boyut --", None)
        for std in get_standart_bosluklar():
            self.standart_combo.addItem(
                f"{std['ad']} ({std['alan_m2']:.2f} m²)",
                std
            )
        self.standart_combo.currentIndexChanged.connect(self.on_standart_selected)
        std_layout.addWidget(self.standart_combo)
        layout.addWidget(std_group)

        # Form
        form = QFormLayout()

        # Açıklama
        self.aciklama_input = QLineEdit()
        self.aciklama_input.setPlaceholderText("Örn: Salon Penceresi")
        form.addRow("Açıklama:", self.aciklama_input)

        # En (cm)
        self.en_spin = QDoubleSpinBox()
        self.en_spin.setRange(10, 1000)
        self.en_spin.setValue(120)
        self.en_spin.setSuffix(" cm")
        self.en_spin.valueChanged.connect(self.update_alan)
        form.addRow("Genişlik (En):", self.en_spin)

        # Boy (cm)
        self.boy_spin = QDoubleSpinBox()
        self.boy_spin.setRange(10, 500)
        self.boy_spin.setValue(150)
        self.boy_spin.setSuffix(" cm")
        self.boy_spin.valueChanged.connect(self.update_alan)
        form.addRow("Yükseklik (Boy):", self.boy_spin)

        # Adet
        self.adet_spin = QSpinBox()
        self.adet_spin.setRange(1, 100)
        self.adet_spin.setValue(1)
        self.adet_spin.valueChanged.connect(self.update_alan)
        form.addRow("Adet:", self.adet_spin)

        # Denizlik dönüşü
        self.denizlik_check = QCheckBox("Denizlik dönüşü yapılacak")
        self.denizlik_check.setChecked(True)
        self.denizlik_check.setToolTip("Pencere kenarlarına mantolama dönüşü yapılsın mı?")
        form.addRow("", self.denizlik_check)

        # Alan bilgisi
        self.alan_label = QLabel()
        self.alan_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        form.addRow("Hesaplanan Alan:", self.alan_label)

        layout.addLayout(form)

        # Minha uyarısı
        self.minha_uyari_label = QLabel()
        self.minha_uyari_label.setWordWrap(True)
        layout.addWidget(self.minha_uyari_label)

        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Ekle" if not self.bosluk_data else "Güncelle")
        btn_save.clicked.connect(self.accept)
        btn_save.setDefault(True)
        btn_save.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 20px;")
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        self.update_alan()

    def on_standart_selected(self, index):
        """Standart boyut seçildiğinde"""
        data = self.standart_combo.currentData()
        if data:
            self.en_spin.setValue(data['en_cm'])
            self.boy_spin.setValue(data['boy_cm'])
            if not self.aciklama_input.text():
                self.aciklama_input.setText(data['ad'])

    def update_alan(self):
        """Alan ve minha durumunu güncelle"""
        en = self.en_spin.value()
        boy = self.boy_spin.value()
        adet = self.adet_spin.value()

        tek_alan = (en * boy) / 10000
        toplam_alan = tek_alan * adet

        self.alan_label.setText(f"{tek_alan:.3f} m² × {adet} = {toplam_alan:.2f} m²")

        # Minha kontrolü
        if tek_alan < VARSAYILAN_MINHA_LIMITI_M2:
            self.minha_uyari_label.setText(
                f" Bu boşluk {tek_alan:.2f} m² < {VARSAYILAN_MINHA_LIMITI_M2} m² olduğu için "
                f"Minha kuralı gereği DÜŞÜLMEYECEK (alan aynen sayılacak)."
            )
            self.minha_uyari_label.setStyleSheet("color: #FF9800; padding: 5px;")
        else:
            self.minha_uyari_label.setText(
                f" Bu boşluk {tek_alan:.2f} m² ≥ {VARSAYILAN_MINHA_LIMITI_M2} m² olduğu için "
                f"brüt alandan DÜŞÜLECEK."
            )
            self.minha_uyari_label.setStyleSheet("color: #4CAF50; padding: 5px;")

    def load_data(self):
        """Mevcut veriyi yükle (düzenleme modu)"""
        if self.bosluk_data:
            self.aciklama_input.setText(self.bosluk_data.get('aciklama', ''))
            self.en_spin.setValue(self.bosluk_data.get('en_cm', 120))
            self.boy_spin.setValue(self.bosluk_data.get('boy_cm', 150))
            self.adet_spin.setValue(self.bosluk_data.get('adet', 1))
            self.denizlik_check.setChecked(self.bosluk_data.get('denizlik_donulecek_mi', True))

    def get_data(self) -> Dict[str, Any]:
        """Dialog verilerini al"""
        return {
            'aciklama': self.aciklama_input.text().strip() or f"{self.en_spin.value():.0f}x{self.boy_spin.value():.0f} cm",
            'en_cm': self.en_spin.value(),
            'boy_cm': self.boy_spin.value(),
            'adet': self.adet_spin.value(),
            'denizlik_donulecek_mi': self.denizlik_check.isChecked()
        }


class MantolamaHesaplamaDialog(QDialog):
    """Ana Mantolama Hesaplama Dialog Penceresi"""

    # Hesaplama tamamlandığında sinyal
    hesaplama_tamamlandi = pyqtSignal(dict)

    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.db = db
        self.bosluklar = []
        self.son_hesaplama = None

        self.setWindowTitle("Dış Cephe Mantolama Hesaplama (Minha Kuralı)")
        self.setMinimumSize(1100, 800)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Başlık
        baslik = QLabel(" DIS CEPHE MANTOLAMA MINHA HESAPLAMA")
        baslik.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        baslik.setStyleSheet("color: #2196F3; padding: 10px;")
        main_layout.addWidget(baslik)

        # Ana içerik splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # =====================
        # SOL PANEL - GİRİŞLER
        # =====================
        sol_widget = QWidget()
        sol_layout = QVBoxLayout(sol_widget)

        # 1. Cephe Alanı Grubu
        alan_group = QGroupBox("1. Brüt Cephe Alanı")
        alan_layout = QFormLayout(alan_group)

        self.brut_alan_spin = QDoubleSpinBox()
        self.brut_alan_spin.setRange(10, 100000)
        self.brut_alan_spin.setValue(500)
        self.brut_alan_spin.setSuffix(" m²")
        self.brut_alan_spin.setDecimals(2)
        alan_layout.addRow("Brüt Cephe Alanı:", self.brut_alan_spin)

        sol_layout.addWidget(alan_group)

        # 2. Boşluklar Grubu
        bosluk_group = QGroupBox("2. Pencere/Kapı Boşlukları")
        bosluk_layout = QVBoxLayout(bosluk_group)

        # Boşluk tablosu
        self.bosluk_table = QTableWidget()
        self.bosluk_table.setColumnCount(6)
        self.bosluk_table.setHorizontalHeaderLabels([
            "Açıklama", "En (cm)", "Boy (cm)", "Adet", "Alan (m²)", "Denizlik"
        ])
        self.bosluk_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.bosluk_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bosluk_table.setMinimumHeight(150)
        bosluk_layout.addWidget(self.bosluk_table)

        # Boşluk butonları
        bosluk_btn_layout = QHBoxLayout()

        btn_bosluk_ekle = QPushButton("+ Boşluk Ekle")
        btn_bosluk_ekle.clicked.connect(self.bosluk_ekle)
        btn_bosluk_ekle.setStyleSheet("background-color: #4CAF50; color: white;")
        bosluk_btn_layout.addWidget(btn_bosluk_ekle)

        btn_bosluk_duzenle = QPushButton(" Düzenle")
        btn_bosluk_duzenle.clicked.connect(self.bosluk_duzenle)
        bosluk_btn_layout.addWidget(btn_bosluk_duzenle)

        btn_bosluk_sil = QPushButton(" Sil")
        btn_bosluk_sil.clicked.connect(self.bosluk_sil)
        btn_bosluk_sil.setStyleSheet("background-color: #f44336; color: white;")
        bosluk_btn_layout.addWidget(btn_bosluk_sil)

        bosluk_btn_layout.addStretch()
        bosluk_layout.addLayout(bosluk_btn_layout)

        # Boşluk özeti
        self.bosluk_ozet_label = QLabel("Toplam: 0 boşluk, 0.00 m²")
        self.bosluk_ozet_label.setStyleSheet("color: #666; font-style: italic;")
        bosluk_layout.addWidget(self.bosluk_ozet_label)

        sol_layout.addWidget(bosluk_group)

        # 3. Sistem Seçimi Grubu
        sistem_group = QGroupBox("3. Mantolama Sistemi")
        sistem_layout = QFormLayout(sistem_group)

        self.levha_combo = QComboBox()
        self.levha_combo.addItem("EPS Karbonlu (Grafit Katkılı) - Yüksek İzolasyon", "eps_karbonlu")
        self.levha_combo.addItem("Taş Yünü - Yangın Dayanımı Yüksek (A1)", "tas_yunu")
        self.levha_combo.currentIndexChanged.connect(self.on_levha_degisti)
        sistem_layout.addRow("Levha Tipi:", self.levha_combo)

        sol_layout.addWidget(sistem_group)

        # 4. Parametreler Grubu
        param_group = QGroupBox("4. Hesaplama Parametreleri")
        param_layout = QFormLayout(param_group)

        self.minha_spin = QDoubleSpinBox()
        self.minha_spin.setRange(0, 10)
        self.minha_spin.setValue(VARSAYILAN_MINHA_LIMITI_M2)
        self.minha_spin.setSuffix(" m²")
        self.minha_spin.setToolTip("Bu değerden küçük boşluklar brüt alandan düşülmez")
        param_layout.addRow("Minha Limiti:", self.minha_spin)

        self.ekip_ucret_spin = QDoubleSpinBox()
        self.ekip_ucret_spin.setRange(1000, 50000)
        self.ekip_ucret_spin.setValue(4500)
        self.ekip_ucret_spin.setSuffix(" TL/gün")
        param_layout.addRow("Ekip Günlük Ücret:", self.ekip_ucret_spin)

        self.kat_sayisi_spin = QSpinBox()
        self.kat_sayisi_spin.setRange(1, 50)
        self.kat_sayisi_spin.setValue(4)
        param_layout.addRow("Bina Kat Sayısı:", self.kat_sayisi_spin)

        self.iskele_check = QCheckBox("İskele maliyeti dahil")
        self.iskele_check.setChecked(True)
        param_layout.addRow("", self.iskele_check)

        sol_layout.addWidget(param_group)

        # Hesapla butonu
        self.btn_hesapla = QPushButton(" HESAPLA")
        self.btn_hesapla.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.btn_hesapla.setMinimumHeight(50)
        self.btn_hesapla.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.btn_hesapla.clicked.connect(self.hesapla)
        sol_layout.addWidget(self.btn_hesapla)

        sol_layout.addStretch()
        splitter.addWidget(sol_widget)

        # ======================
        # SAĞ PANEL - SONUÇLAR
        # ======================
        sag_widget = QWidget()
        sag_layout = QVBoxLayout(sag_widget)

        # Tab widget
        self.tab_widget = QTabWidget()

        # Tab 1: Özet
        ozet_tab = QWidget()
        ozet_layout = QVBoxLayout(ozet_tab)

        self.ozet_text = QTextEdit()
        self.ozet_text.setReadOnly(True)
        self.ozet_text.setFont(QFont("Consolas", 10))
        self.ozet_text.setPlaceholderText("Hesaplama sonuçları burada görünecek...")
        ozet_layout.addWidget(self.ozet_text)

        self.tab_widget.addTab(ozet_tab, " Özet Rapor")

        # Tab 2: Minha Analizi
        minha_tab = QWidget()
        minha_layout = QVBoxLayout(minha_tab)

        self.minha_table = QTableWidget()
        self.minha_table.setColumnCount(7)
        self.minha_table.setHorizontalHeaderLabels([
            "Boşluk", "Tek Alan", "Adet", "Toplam", "Durum", "Düşülen", "Denizlik Dönüş"
        ])
        self.minha_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        minha_layout.addWidget(self.minha_table)

        self.tab_widget.addTab(minha_tab, " Minha Analizi")

        # Tab 3: Malzeme Listesi
        malzeme_tab = QWidget()
        malzeme_layout = QVBoxLayout(malzeme_tab)

        self.malzeme_table = QTableWidget()
        self.malzeme_table.setColumnCount(5)
        self.malzeme_table.setHorizontalHeaderLabels([
            "Malzeme", "Miktar", "Birim", "Birim Fiyat", "Toplam"
        ])
        self.malzeme_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        malzeme_layout.addWidget(self.malzeme_table)

        self.tab_widget.addTab(malzeme_tab, " Malzeme Listesi")

        # Tab 4: Maliyet Özeti
        maliyet_tab = QWidget()
        maliyet_layout = QVBoxLayout(maliyet_tab)

        self.maliyet_text = QTextEdit()
        self.maliyet_text.setReadOnly(True)
        self.maliyet_text.setFont(QFont("Consolas", 11))
        maliyet_layout.addWidget(self.maliyet_text)

        self.tab_widget.addTab(maliyet_tab, " Maliyet Özeti")

        sag_layout.addWidget(self.tab_widget)

        # Dışa aktarma butonları
        export_layout = QHBoxLayout()

        btn_excel = QPushButton(" Excel'e Aktar")
        btn_excel.clicked.connect(self.export_excel)
        export_layout.addWidget(btn_excel)

        btn_pdf = QPushButton(" PDF Rapor")
        btn_pdf.clicked.connect(self.export_pdf)
        export_layout.addWidget(btn_pdf)

        btn_metraj = QPushButton(" Metraja Ekle")
        btn_metraj.clicked.connect(self.metraja_ekle)
        btn_metraj.setStyleSheet("background-color: #4CAF50; color: white;")
        export_layout.addWidget(btn_metraj)

        sag_layout.addLayout(export_layout)

        splitter.addWidget(sag_widget)

        # Splitter oranı
        splitter.setSizes([400, 700])

        main_layout.addWidget(splitter)

        # Alt butonlar
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.close)
        bottom_layout.addWidget(btn_kapat)

        main_layout.addLayout(bottom_layout)

    def bosluk_ekle(self):
        """Yeni boşluk ekle"""
        dialog = BoslukEklemeDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            self.bosluklar.append(data)
            self.bosluk_tablosunu_guncelle()

    def bosluk_duzenle(self):
        """Seçili boşluğu düzenle"""
        row = self.bosluk_table.currentRow()
        if row < 0 or row >= len(self.bosluklar):
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlenecek boşluğu seçin!")
            return

        dialog = BoslukEklemeDialog(self, self.bosluklar[row])
        if dialog.exec():
            self.bosluklar[row] = dialog.get_data()
            self.bosluk_tablosunu_guncelle()

    def bosluk_sil(self):
        """Seçili boşluğu sil"""
        row = self.bosluk_table.currentRow()
        if row < 0 or row >= len(self.bosluklar):
            QMessageBox.warning(self, "Uyarı", "Lütfen silinecek boşluğu seçin!")
            return

        reply = QMessageBox.question(
            self, "Onay",
            f"'{self.bosluklar[row]['aciklama']}' boşluğunu silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            del self.bosluklar[row]
            self.bosluk_tablosunu_guncelle()

    def bosluk_tablosunu_guncelle(self):
        """Boşluk tablosunu güncelle"""
        self.bosluk_table.setRowCount(len(self.bosluklar))

        toplam_alan = 0
        for row, bosluk in enumerate(self.bosluklar):
            tek_alan = (bosluk['en_cm'] * bosluk['boy_cm']) / 10000
            toplam = tek_alan * bosluk['adet']
            toplam_alan += toplam

            self.bosluk_table.setItem(row, 0, QTableWidgetItem(bosluk['aciklama']))
            self.bosluk_table.setItem(row, 1, QTableWidgetItem(f"{bosluk['en_cm']:.0f}"))
            self.bosluk_table.setItem(row, 2, QTableWidgetItem(f"{bosluk['boy_cm']:.0f}"))
            self.bosluk_table.setItem(row, 3, QTableWidgetItem(str(bosluk['adet'])))
            self.bosluk_table.setItem(row, 4, QTableWidgetItem(f"{toplam:.2f}"))

            denizlik_item = QTableWidgetItem("" if bosluk['denizlik_donulecek_mi'] else "")
            denizlik_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.bosluk_table.setItem(row, 5, denizlik_item)

            # Minha renklendirmesi
            if tek_alan < self.minha_spin.value():
                for col in range(6):
                    item = self.bosluk_table.item(row, col)
                    if item:
                        item.setBackground(QBrush(QColor(255, 243, 224)))  # Açık turuncu

        self.bosluk_ozet_label.setText(
            f"Toplam: {len(self.bosluklar)} boşluk, {toplam_alan:.2f} m² "
            f"(Minha limiti: {self.minha_spin.value()} m²)"
        )

    def on_levha_degisti(self, index):
        """Levha tipi değiştiğinde"""
        pass  # İleride fiyat güncelleme eklenebilir

    def hesapla(self):
        """Hesaplamayı çalıştır"""
        if not self.bosluklar:
            reply = QMessageBox.question(
                self, "Uyarı",
                "Hiç boşluk eklenmedi. Boşluksuz devam etmek istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        try:
            sonuc = hesapla_mantolama_minhali(
                brut_cephe_alani_m2=self.brut_alan_spin.value(),
                bosluklar_listesi=self.bosluklar,
                levha_tipi=self.levha_combo.currentData(),
                ekip_gunluk_ucret=self.ekip_ucret_spin.value(),
                iskele_dahil=self.iskele_check.isChecked(),
                minha_limiti_m2=self.minha_spin.value(),
                bina_kat_sayisi=self.kat_sayisi_spin.value()
            )

            self.son_hesaplama = sonuc
            self.sonuclari_goster(sonuc)
            self.hesaplama_tamamlandi.emit(sonuc)

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Hesaplama hatası:\n{str(e)}")

    def sonuclari_goster(self, sonuc: Dict):
        """Hesaplama sonuçlarını göster"""

        # 1. Özet Rapor
        ozet = []
        ozet.append("=" * 60)
        ozet.append(" DIS CEPHE MANTOLAMA HESAPLAMA RAPORU")
        ozet.append("=" * 60)
        ozet.append("")
        ozet.append(f"Levha Tipi: {sonuc['levha_aciklama']}")
        ozet.append(f"Minha Limiti: {sonuc['minha_limiti_m2']} m²")
        ozet.append("")
        ozet.append("-" * 60)
        ozet.append("ALAN HESABI")
        ozet.append("-" * 60)
        ozet.append(f"Brüt Cephe Alanı : {sonuc['girilen_brut_alan_m2']:>10.2f} m²")
        ozet.append(f"Düşülen Boşluk Alanı : {sonuc['dusulen_bosluk_alani_m2']:>10.2f} m²")
        ozet.append(f"Düşülmeyen Boşluklar : {sonuc['dusulmeyen_toplam_alan_m2']:>10.2f} m² ({sonuc['dusulmeyen_bosluk_sayisi']} adet)")
        ozet.append(f"Eklenen Denizlik Dönüş: {sonuc['eklenen_denizlik_donus_m2']:>10.2f} m²")
        ozet.append("-" * 60)
        ozet.append(f"UYGULAMA ALANI : {sonuc['uygulamaya_esas_net_alan_m2']:>10.2f} m²")
        ozet.append("")
        ozet.append(f"Formül: {sonuc['net_alan_formulu']}")
        ozet.append("")
        ozet.append("-" * 60)
        ozet.append("MALİYET ÖZETİ")
        ozet.append("-" * 60)
        m = sonuc['maliyet_ozeti']
        ozet.append(f"Malzeme Toplamı : {m['toplam_malzeme_tl']:>15,.2f} TL")
        ozet.append(f"İşçilik ({sonuc['tahmini_sure_gun']} gün) : {m['toplam_iscilik_tl']:>15,.2f} TL")
        ozet.append(f"İskele : {m['iskele_maliyet_tl']:>15,.2f} TL")
        ozet.append("=" * 60)
        ozet.append(f"GENEL TOPLAM : {m['genel_toplam_tl']:>15,.2f} TL")
        ozet.append(f"m² Birim Maliyet : {m['birim_maliyet_m2']:>15,.2f} TL/m²")
        ozet.append("=" * 60)

        self.ozet_text.setPlainText("\n".join(ozet))

        # 2. Minha Analizi Tablosu
        analizler = sonuc['minha_analizleri']
        self.minha_table.setRowCount(len(analizler))

        for row, a in enumerate(analizler):
            self.minha_table.setItem(row, 0, QTableWidgetItem(a['aciklama']))
            self.minha_table.setItem(row, 1, QTableWidgetItem(f"{a['tek_alan_m2']:.3f} m²"))
            self.minha_table.setItem(row, 2, QTableWidgetItem(str(a['adet'])))
            self.minha_table.setItem(row, 3, QTableWidgetItem(f"{a['toplam_alan_m2']:.2f} m²"))

            durum = "DÜŞÜLDÜ" if a['dusuldu_mu'] else "DÜŞÜLMEZ (Minha)"
            durum_item = QTableWidgetItem(durum)
            if a['dusuldu_mu']:
                durum_item.setBackground(QBrush(QColor(200, 230, 201)))  # Yeşil
            else:
                durum_item.setBackground(QBrush(QColor(255, 224, 178)))  # Turuncu
            self.minha_table.setItem(row, 4, durum_item)

            self.minha_table.setItem(row, 5, QTableWidgetItem(f"{a['dusulen_alan_m2']:.2f} m²"))
            self.minha_table.setItem(row, 6, QTableWidgetItem(f"+{a['denizlik_donusu_m2']:.2f} m²"))

        # 3. Malzeme Listesi
        malzemeler = sonuc['malzeme_listesi']
        self.malzeme_table.setRowCount(len(malzemeler))

        for row, mal in enumerate(malzemeler):
            self.malzeme_table.setItem(row, 0, QTableWidgetItem(mal['ad']))
            self.malzeme_table.setItem(row, 1, QTableWidgetItem(f"{mal['miktar']:,.2f}"))
            self.malzeme_table.setItem(row, 2, QTableWidgetItem(mal['birim']))
            self.malzeme_table.setItem(row, 3, QTableWidgetItem(f"{mal['birim_fiyat']:,.2f} TL"))

            toplam_item = QTableWidgetItem(f"{mal['toplam_fiyat']:,.2f} TL")
            toplam_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.malzeme_table.setItem(row, 4, toplam_item)

        # 4. Maliyet Özeti
        maliyet = []
        maliyet.append("=" * 50)
        maliyet.append(" MALİYET DETAYI")
        maliyet.append("=" * 50)
        maliyet.append("")
        maliyet.append("MALZEME MALİYETLERİ:")
        maliyet.append("-" * 50)
        for mal in malzemeler:
            maliyet.append(f" {mal['ad'][:35]:<35} {mal['toplam_fiyat']:>12,.2f} TL")
        maliyet.append("-" * 50)
        maliyet.append(f" {'MALZEME TOPLAMI':<35} {m['toplam_malzeme_tl']:>12,.2f} TL")
        maliyet.append("")
        maliyet.append("İŞÇİLİK:")
        maliyet.append("-" * 50)
        maliyet.append(f" Tahmini Süre: {sonuc['tahmini_sure_gun']} gün")
        maliyet.append(f" Verimlilik: {sonuc['kullanilan_hiz_m2_gun']} m²/gün ({sonuc['verim_kaynagi']})")
        maliyet.append(f" {'İŞÇİLİK TOPLAMI':<35} {m['toplam_iscilik_tl']:>12,.2f} TL")
        maliyet.append("")
        if sonuc['iskele_bilgisi']['dahil_mi']:
            maliyet.append("İSKELE:")
            maliyet.append("-" * 50)
            maliyet.append(f" İskele Alanı: {sonuc['iskele_bilgisi']['iskele_alani_m2']:.2f} m²")
            maliyet.append(f" İskele Süresi: {sonuc['iskele_bilgisi']['iskele_gun']} gün")
            maliyet.append(f" {'İSKELE TOPLAMI':<35} {m['iskele_maliyet_tl']:>12,.2f} TL")
            maliyet.append("")
        maliyet.append("=" * 50)
        maliyet.append(f" {'GENEL TOPLAM':<35} {m['genel_toplam_tl']:>12,.2f} TL")
        maliyet.append(f" {'m² BİRİM MALİYET':<35} {m['birim_maliyet_m2']:>12,.2f} TL/m²")
        maliyet.append("=" * 50)

        self.maliyet_text.setPlainText("\n".join(maliyet))

        # Özet tab'ına geç
        self.tab_widget.setCurrentIndex(0)

    def export_excel(self):
        """Excel'e aktar"""
        if not self.son_hesaplama:
            QMessageBox.warning(self, "Uyarı", "Önce hesaplama yapmalısınız!")
            return

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

            file_path, _ = QFileDialog.getSaveFileName(
                self, "Excel Kaydet", "mantolama_raporu.xlsx",
                "Excel Dosyası (*.xlsx)"
            )

            if not file_path:
                return

            wb = Workbook()
            ws = wb.active
            ws.title = "Mantolama Raporu"

            # Başlık
            ws['A1'] = "DIS CEPHE MANTOLAMA HESAPLAMA RAPORU"
            ws['A1'].font = Font(bold=True, size=14)
            ws.merge_cells('A1:E1')

            # Alan bilgileri
            row = 3
            ws[f'A{row}'] = "ALAN BİLGİLERİ"
            ws[f'A{row}'].font = Font(bold=True)
            row += 1

            sonuc = self.son_hesaplama
            alan_bilgileri = [
                ("Brüt Cephe Alanı", f"{sonuc['girilen_brut_alan_m2']:.2f} m²"),
                ("Düşülen Boşluk Alanı", f"{sonuc['dusulen_bosluk_alani_m2']:.2f} m²"),
                ("Düşülmeyen Boşluklar", f"{sonuc['dusulmeyen_toplam_alan_m2']:.2f} m²"),
                ("Denizlik Dönüş", f"{sonuc['eklenen_denizlik_donus_m2']:.2f} m²"),
                ("Uygulama Alanı", f"{sonuc['uygulamaya_esas_net_alan_m2']:.2f} m²"),
            ]

            for ad, deger in alan_bilgileri:
                ws[f'A{row}'] = ad
                ws[f'B{row}'] = deger
                row += 1

            # Malzeme listesi
            row += 1
            ws[f'A{row}'] = "MALZEME LİSTESİ"
            ws[f'A{row}'].font = Font(bold=True)
            row += 1

            headers = ["Malzeme", "Miktar", "Birim", "Birim Fiyat", "Toplam"]
            for col, header in enumerate(headers, 1):
                ws.cell(row=row, column=col, value=header).font = Font(bold=True)
            row += 1

            for mal in sonuc['malzeme_listesi']:
                ws.cell(row=row, column=1, value=mal['ad'])
                ws.cell(row=row, column=2, value=mal['miktar'])
                ws.cell(row=row, column=3, value=mal['birim'])
                ws.cell(row=row, column=4, value=mal['birim_fiyat'])
                ws.cell(row=row, column=5, value=mal['toplam_fiyat'])
                row += 1

            # Maliyet özeti
            row += 1
            ws[f'A{row}'] = "MALİYET ÖZETİ"
            ws[f'A{row}'].font = Font(bold=True)
            row += 1

            m = sonuc['maliyet_ozeti']
            maliyet_bilgileri = [
                ("Malzeme Toplamı", f"{m['toplam_malzeme_tl']:,.2f} TL"),
                ("İşçilik", f"{m['toplam_iscilik_tl']:,.2f} TL"),
                ("İskele", f"{m['iskele_maliyet_tl']:,.2f} TL"),
                ("GENEL TOPLAM", f"{m['genel_toplam_tl']:,.2f} TL"),
                ("m² Birim Maliyet", f"{m['birim_maliyet_m2']:,.2f} TL/m²"),
            ]

            for ad, deger in maliyet_bilgileri:
                ws[f'A{row}'] = ad
                ws[f'B{row}'] = deger
                if ad == "GENEL TOPLAM":
                    ws[f'A{row}'].font = Font(bold=True)
                    ws[f'B{row}'].font = Font(bold=True)
                row += 1

            # Sütun genişlikleri
            ws.column_dimensions['A'].width = 40
            ws.column_dimensions['B'].width = 15
            ws.column_dimensions['C'].width = 15
            ws.column_dimensions['D'].width = 15
            ws.column_dimensions['E'].width = 15

            wb.save(file_path)
            QMessageBox.information(self, "Başarılı", f"Rapor kaydedildi:\n{file_path}")

        except ImportError:
            QMessageBox.warning(self, "Hata", "Excel export için 'openpyxl' kütüphanesi gerekli!\npip install openpyxl")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel kaydetme hatası:\n{str(e)}")

    def export_pdf(self):
        """PDF'e aktar"""
        if not self.son_hesaplama:
            QMessageBox.warning(self, "Uyarı", "Önce hesaplama yapmalısınız!")
            return

        QMessageBox.information(
            self, "Bilgi",
            "PDF export özelliği geliştirme aşamasında.\n"
            "Şimdilik Excel export kullanabilirsiniz."
        )

    def metraja_ekle(self):
        """Hesaplama sonucunu metraja ekle"""
        if not self.son_hesaplama:
            QMessageBox.warning(self, "Uyarı", "Önce hesaplama yapmalısınız!")
            return

        # Sinyal gönder
        self.hesaplama_tamamlandi.emit(self.son_hesaplama)

        QMessageBox.information(
            self, "Başarılı",
            f"Mantolama kalemi metraja eklendi:\n"
            f"Alan: {self.son_hesaplama['uygulamaya_esas_net_alan_m2']:.2f} m²\n"
            f"Toplam: {self.son_hesaplama['maliyet_ozeti']['genel_toplam_tl']:,.2f} TL"
        )


# Test için
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Dark tema (opsiyonel)
    app.setStyle("Fusion")

    dialog = MantolamaHesaplamaDialog()
    dialog.show()

    sys.exit(app.exec())
