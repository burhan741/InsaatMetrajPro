"""
Taşeron Modu Ana Pencere
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QFileDialog, QMessageBox,
    QLabel, QLineEdit, QDoubleSpinBox, QDateEdit, QComboBox, QTextEdit,
    QGroupBox, QFormLayout, QHeaderView, QSpinBox, QCheckBox, QScrollArea
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon, QFont

from app.core.database import DatabaseManager


class TaseronWindow(QMainWindow):
    """Taşeron modu ana pencere"""
    
    def __init__(self, db: DatabaseManager, splash=None):
        super().__init__()
        self.db = db
        self.splash = splash
        self.current_is_id: Optional[int] = None
        
        self.init_ui()
    
    def init_ui(self):
        """Taşeron arayüzünü oluştur"""
        self.setWindowTitle("Taşeron Modu - İnşaat Metraj Pro")
        self.setGeometry(100, 100, 1400, 900)
        
        # Merkezi widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Ana layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Üst panel: İş seçimi
        top_layout = QHBoxLayout()
        
        is_label = QLabel("Yapılan İş:")
        top_layout.addWidget(is_label)
        
        self.is_combo = QComboBox()
        self.is_combo.setMinimumWidth(300)
        self.is_combo.currentIndexChanged.connect(self.on_is_changed)
        top_layout.addWidget(self.is_combo)
        
        btn_new_is = QPushButton("Yeni İş Ekle")
        btn_new_is.clicked.connect(self.new_is)
        top_layout.addWidget(btn_new_is)
        
        btn_delete_is = QPushButton("İş Sil")
        btn_delete_is.setStyleSheet("background-color: #c9184a;")
        btn_delete_is.clicked.connect(self.delete_is)
        top_layout.addWidget(btn_delete_is)
        
        top_layout.addStretch()
        
        main_layout.addLayout(top_layout)
        
        # Sekmeler
        self.tabs = QTabWidget()
        
        # Sekme 1: Puantaj Tablosu
        self.create_puantaj_tab()
        
        # Sekme 2: Yapılan İş ve Birim Fiyat
        self.create_is_birim_fiyat_tab()
        
        # Sekme 3: Gelir/Gider Takibi
        self.create_gelir_gider_tab()
        
        # Sekme 4: Raporlar
        self.create_raporlar_tab()
        
        main_layout.addWidget(self.tabs)
        
        # Durum çubuğu
        self.statusBar().showMessage("Hazır")
        
        # İşleri yükle
        self.load_isler()
    
    def create_puantaj_tab(self):
        """Puantaj tablosu sekmesi"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        
        btn_add_personel = QPushButton("Personel Ekle")
        btn_add_personel.clicked.connect(self.add_personel)
        btn_layout.addWidget(btn_add_personel)
        
        btn_edit_personel = QPushButton("Personel Düzenle")
        btn_edit_personel.clicked.connect(self.edit_personel)
        btn_layout.addWidget(btn_edit_personel)
        
        btn_delete_personel = QPushButton("Personel Sil")
        btn_delete_personel.setStyleSheet("background-color: #c9184a;")
        btn_delete_personel.clicked.connect(self.delete_personel)
        btn_layout.addWidget(btn_delete_personel)
        
        btn_add_puantaj = QPushButton("Puantaj Ekle")
        btn_add_puantaj.clicked.connect(self.add_puantaj)
        btn_layout.addWidget(btn_add_puantaj)
        
        btn_bulk_puantaj = QPushButton("Toplu Puantaj Ekle")
        btn_bulk_puantaj.setStyleSheet("background-color: #4CAF50;")
        btn_bulk_puantaj.clicked.connect(self.bulk_add_puantaj)
        btn_layout.addWidget(btn_bulk_puantaj)
        
        btn_layout.addStretch()
        
        # Toplam etiketleri
        self.puantaj_total_label = QLabel("Toplam Personel: 0")
        self.puantaj_total_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn_layout.addWidget(self.puantaj_total_label)
        
        layout.addLayout(btn_layout)
        
        # Personel tablosu
        self.personel_table = QTableWidget()
        self.personel_table.setColumnCount(4)
        self.personel_table.setHorizontalHeaderLabels([
            "ID", "Ad Soyad", "Günlük Ücret (₺)", "Saatlik Ücret (₺)"
        ])
        self.personel_table.setAlternatingRowColors(True)
        self.personel_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.personel_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.personel_table.horizontalHeader().setStretchLastSection(True)
        self.personel_table.setColumnHidden(0, True)
        # Satır yüksekliğini otomatik ayarla (isim soyisim sığsın)
        self.personel_table.verticalHeader().setDefaultSectionSize(35)  # Minimum satır yüksekliği
        layout.addWidget(self.personel_table)
        
        # Puantaj tablosu
        puantaj_title = QLabel("📅 Puantaj Kayıtları")
        puantaj_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(puantaj_title)
        
        # Puantaj işlem butonları
        puantaj_btn_layout = QHBoxLayout()
        
        btn_edit_puantaj = QPushButton("Düzenle")
        btn_edit_puantaj.clicked.connect(self.edit_puantaj)
        puantaj_btn_layout.addWidget(btn_edit_puantaj)
        
        btn_delete_puantaj = QPushButton("Sil")
        btn_delete_puantaj.setStyleSheet("background-color: #c9184a;")
        btn_delete_puantaj.clicked.connect(self.delete_puantaj)
        puantaj_btn_layout.addWidget(btn_delete_puantaj)
        
        puantaj_btn_layout.addStretch()
        layout.addLayout(puantaj_btn_layout)
        
        # Tarih filtresi
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Tarih Filtresi:"))
        
        self.puantaj_filter_enabled = True  # Filtre aktif mi?
        
        self.puantaj_tarih_filter = QDateEdit()
        self.puantaj_tarih_filter.setDate(QDate.currentDate())
        self.puantaj_tarih_filter.setCalendarPopup(True)
        self.puantaj_tarih_filter.setDisplayFormat("dd.MM.yyyy")
        self.puantaj_tarih_filter.setMinimumDate(QDate(2020, 1, 1))
        self.puantaj_tarih_filter.setMaximumDate(QDate(2100, 12, 31))
        self.puantaj_tarih_filter.dateChanged.connect(self.load_puantaj)
        filter_layout.addWidget(self.puantaj_tarih_filter)
        
        btn_clear_filter = QPushButton("Tümünü Göster")
        btn_clear_filter.clicked.connect(self.clear_puantaj_filter)
        filter_layout.addWidget(btn_clear_filter)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        self.puantaj_table = QTableWidget()
        self.puantaj_table.setColumnCount(6)
        self.puantaj_table.setHorizontalHeaderLabels([
            "ID", "Tarih", "Personel", "Çalışma Saati", "Çalışma Günü", "Toplam Ücret (₺)"
        ])
        self.puantaj_table.setColumnHidden(0, True)  # ID sütununu gizle
        self.puantaj_table.setAlternatingRowColors(True)
        self.puantaj_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.puantaj_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.puantaj_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.puantaj_table)
        
        self.tabs.addTab(tab, "👥 Puantaj")
    
    def create_is_birim_fiyat_tab(self):
        """Yapılan iş ve birim fiyat sekmesi"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        
        btn_add_is = QPushButton("İş Ekle")
        btn_add_is.clicked.connect(self.add_is_birim_fiyat)
        btn_layout.addWidget(btn_add_is)
        
        btn_edit_is = QPushButton("Düzenle")
        btn_edit_is.clicked.connect(self.edit_is_birim_fiyat)
        btn_layout.addWidget(btn_edit_is)
        
        btn_delete_is = QPushButton("Sil")
        btn_delete_is.setStyleSheet("background-color: #c9184a;")
        btn_delete_is.clicked.connect(self.delete_is_birim_fiyat)
        btn_layout.addWidget(btn_delete_is)
        
        btn_layout.addStretch()
        
        # Toplam etiketleri
        self.is_total_label = QLabel("Toplam Gelir: 0.00 ₺")
        self.is_total_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.is_total_label.setStyleSheet("color: #4CAF50;")
        btn_layout.addWidget(self.is_total_label)
        
        layout.addLayout(btn_layout)
        
        # İş ve birim fiyat tablosu
        self.is_birim_fiyat_table = QTableWidget()
        self.is_birim_fiyat_table.setColumnCount(5)
        self.is_birim_fiyat_table.setHorizontalHeaderLabels([
            "ID", "İş Adı", "Birim", "Birim Fiyat (₺)", "Miktar", "Toplam (₺)"
        ])
        self.is_birim_fiyat_table.setAlternatingRowColors(True)
        self.is_birim_fiyat_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.is_birim_fiyat_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.is_birim_fiyat_table.horizontalHeader().setStretchLastSection(True)
        self.is_birim_fiyat_table.setColumnHidden(0, True)
        layout.addWidget(self.is_birim_fiyat_table)
        
        self.tabs.addTab(tab, "💰 Yapılan İş ve Birim Fiyat")
    
    def create_gelir_gider_tab(self):
        """Gelir/Gider takibi sekmesi"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        
        btn_add_gelir = QPushButton("Gelir Ekle")
        btn_add_gelir.setStyleSheet("background-color: #4CAF50;")
        btn_add_gelir.clicked.connect(lambda: self.add_gelir_gider('gelir'))
        btn_layout.addWidget(btn_add_gelir)
        
        btn_add_gider = QPushButton("Gider Ekle")
        btn_add_gider.setStyleSheet("background-color: #c9184a;")
        btn_add_gider.clicked.connect(lambda: self.add_gelir_gider('gider'))
        btn_layout.addWidget(btn_add_gider)
        
        btn_layout.addStretch()
        
        # Özet kartları
        summary_layout = QHBoxLayout()
        
        self.gelir_card = QGroupBox("Toplam Gelir")
        gelir_layout = QVBoxLayout()
        self.gelir_label = QLabel("0.00 ₺")
        self.gelir_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.gelir_label.setStyleSheet("color: #4CAF50;")
        self.gelir_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gelir_layout.addWidget(self.gelir_label)
        self.gelir_card.setLayout(gelir_layout)
        summary_layout.addWidget(self.gelir_card)
        
        self.gider_card = QGroupBox("Toplam Gider")
        gider_layout = QVBoxLayout()
        self.gider_label = QLabel("0.00 ₺")
        self.gider_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.gider_label.setStyleSheet("color: #c9184a;")
        self.gider_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gider_layout.addWidget(self.gider_label)
        self.gider_card.setLayout(gider_layout)
        summary_layout.addWidget(self.gider_card)
        
        self.kar_card = QGroupBox("Net Kar/Zarar")
        kar_layout = QVBoxLayout()
        self.kar_label = QLabel("0.00 ₺")
        self.kar_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.kar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        kar_layout.addWidget(self.kar_label)
        self.kar_card.setLayout(kar_layout)
        summary_layout.addWidget(self.kar_card)
        
        layout.addLayout(btn_layout)
        layout.addLayout(summary_layout)
        
        # Gelir/Gider tablosu
        self.gelir_gider_table = QTableWidget()
        self.gelir_gider_table.setColumnCount(5)
        self.gelir_gider_table.setHorizontalHeaderLabels([
            "ID", "Tarih", "Tip", "Kategori", "Açıklama", "Tutar (₺)"
        ])
        self.gelir_gider_table.setAlternatingRowColors(True)
        self.gelir_gider_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.gelir_gider_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.gelir_gider_table.horizontalHeader().setStretchLastSection(True)
        self.gelir_gider_table.setColumnHidden(0, True)
        layout.addWidget(self.gelir_gider_table)
        
        self.tabs.addTab(tab, "📊 Gelir/Gider Takibi")
    
    def create_raporlar_tab(self):
        """Raporlar sekmesi"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Filtreleme
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Dönem:"))
        self.rapor_period = QComboBox()
        self.rapor_period.addItems(["Bu Ay", "Bu Yıl", "Tümü", "Özel Tarih"])
        self.rapor_period.currentTextChanged.connect(self.update_raporlar)
        filter_layout.addWidget(self.rapor_period)
        
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.start_date.setCalendarPopup(True)
        filter_layout.addWidget(QLabel("Başlangıç:"))
        filter_layout.addWidget(self.start_date)
        
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        filter_layout.addWidget(QLabel("Bitiş:"))
        filter_layout.addWidget(self.end_date)
        
        filter_layout.addStretch()
        
        btn_export = QPushButton("Excel'e Aktar")
        btn_export.clicked.connect(self.export_rapor)
        filter_layout.addWidget(btn_export)
        
        layout.addLayout(filter_layout)
        
        # Rapor özeti
        summary_group = QGroupBox("📈 Aylık/Yıllık Özet")
        summary_layout = QVBoxLayout()
        
        self.rapor_table = QTableWidget()
        self.rapor_table.setColumnCount(4)
        self.rapor_table.setHorizontalHeaderLabels([
            "Dönem", "Gelir (₺)", "Gider (₺)", "Net Kar/Zarar (₺)"
        ])
        self.rapor_table.setAlternatingRowColors(True)
        self.rapor_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.rapor_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rapor_table.horizontalHeader().setStretchLastSection(True)
        summary_layout.addWidget(self.rapor_table)
        
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        self.tabs.addTab(tab, "📋 Raporlar")
    
    # Veritabanı işlemleri
    def load_isler(self):
        """İşleri yükle"""
        try:
            self.is_combo.clear()
            isler = self.db.get_taseron_isleri()
            for is_item in isler:
                self.is_combo.addItem(is_item['is_adi'], is_item['id'])
            
            if isler and not self.current_is_id:
                self.current_is_id = isler[0]['id']
                self.is_combo.setCurrentIndex(0)
                self.on_is_changed()
        except Exception as e:
            print(f"İş yükleme hatası: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Hata", f"İşler yüklenirken hata oluştu:\n{str(e)}")
    
    def on_is_changed(self):
        """İş değiştiğinde"""
        try:
            is_id = self.is_combo.currentData()
            self.current_is_id = is_id
            
            if is_id:
                self.load_personel()
                self.load_puantaj()
                self.load_is_birim_fiyat()
                self.load_gelir_gider()
                self.update_raporlar()
        except Exception as e:
            print(f"İş değiştirme hatası: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Hata", f"İş değiştirilirken hata oluştu:\n{str(e)}")
    
    def new_is(self):
        """Yeni iş ekle"""
        from PyQt6.QtWidgets import QInputDialog
        
        is_adi, ok = QInputDialog.getText(
            self, "Yeni İş",
            "İş adı:"
        )
        
        if not ok or not is_adi.strip():
            return
        
        aciklama, ok = QInputDialog.getText(
            self, "İş Açıklaması",
            "Açıklama (isteğe bağlı):"
        )
        
        if not ok:
            return
        
        try:
            is_id = self.db.create_taseron_is(is_adi.strip(), aciklama.strip())
            QMessageBox.information(self, "Başarılı", "İş başarıyla eklendi")
            self.load_isler()
            self.is_combo.setCurrentIndex(0)
            self.statusBar().showMessage(f"Yeni iş eklendi: {is_adi}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"İş eklenirken hata oluştu:\n{str(e)}")
    
    def delete_is(self):
        """İş sil"""
        if not self.current_is_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir iş seçin")
            return
        
        reply = QMessageBox.question(
            self, "Onay",
            "Bu işi silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.db.delete_taseron_is(self.current_is_id):
                QMessageBox.information(self, "Başarılı", "İş silindi")
                self.current_is_id = None
                self.load_isler()
            else:
                QMessageBox.critical(self, "Hata", "İş silinirken hata oluştu")
    
    def add_personel(self):
        """Personel ekle"""
        if not self.current_is_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir iş seçin")
            return
        
        from PyQt6.QtWidgets import QDialog, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Personel Ekle")
        dialog.setGeometry(400, 400, 400, 200)
        
        layout = QFormLayout(dialog)
        
        ad_input = QLineEdit()
        layout.addRow("Ad Soyad:", ad_input)
        
        gunluk_spin = QDoubleSpinBox()
        gunluk_spin.setRange(0, 999999)
        gunluk_spin.setDecimals(2)
        layout.addRow("Günlük Ücret (₺):", gunluk_spin)
        
        saatlik_spin = QDoubleSpinBox()
        saatlik_spin.setRange(0, 999999)
        saatlik_spin.setDecimals(2)
        layout.addRow("Saatlik Ücret (₺):", saatlik_spin)
        
        # Günlük ücret değiştiğinde saatlik ücreti otomatik hesapla (8'e böl)
        def on_gunluk_changed(value):
            if value > 0:
                saatlik_spin.setValue(value / 8.0)
        
        gunluk_spin.valueChanged.connect(on_gunluk_changed)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Ekle")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if not ad_input.text().strip():
                QMessageBox.warning(self, "Uyarı", "Ad soyad gereklidir")
                return
            
            try:
                self.db.add_taseron_personel(
                    self.current_is_id,
                    ad_input.text().strip(),
                    gunluk_spin.value(),
                    saatlik_spin.value()
                )
                QMessageBox.information(self, "Başarılı", "Personel eklendi")
                self.load_personel()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Personel eklenirken hata oluştu:\n{str(e)}")
    
    def edit_personel(self):
        """Personel bilgilerini düzenle"""
        if not self.current_is_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir iş seçin")
            return
        
        current_row = self.personel_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz bir personeli seçin")
            return
        
        personel_id_item = self.personel_table.item(current_row, 0)
        if not personel_id_item:
            return
        
        personel_id = int(personel_id_item.text())
        personel = self.db.get_taseron_personel_by_id(personel_id)
        
        if not personel:
            QMessageBox.warning(self, "Uyarı", "Personel bulunamadı")
            return
        
        from PyQt6.QtWidgets import QDialog, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Personel Düzenle")
        dialog.setGeometry(400, 400, 400, 200)
        
        layout = QFormLayout(dialog)
        
        ad_input = QLineEdit()
        ad_input.setText(personel['ad_soyad'])
        layout.addRow("Ad Soyad:", ad_input)
        
        gunluk_spin = QDoubleSpinBox()
        gunluk_spin.setRange(0, 999999)
        gunluk_spin.setDecimals(2)
        gunluk_spin.setValue(personel.get('gunluk_ucret', 0))
        layout.addRow("Günlük Ücret (₺):", gunluk_spin)
        
        saatlik_spin = QDoubleSpinBox()
        saatlik_spin.setRange(0, 999999)
        saatlik_spin.setDecimals(2)
        saatlik_spin.setValue(personel.get('saatlik_ucret', 0))
        layout.addRow("Saatlik Ücret (₺):", saatlik_spin)
        
        # Günlük ücret değiştiğinde saatlik ücreti otomatik hesapla (8'e böl)
        def on_gunluk_changed(value):
            if value > 0:
                saatlik_spin.setValue(value / 8.0)
        
        gunluk_spin.valueChanged.connect(on_gunluk_changed)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Kaydet")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if not ad_input.text().strip():
                QMessageBox.warning(self, "Uyarı", "Ad soyad gereklidir")
                return
            
            try:
                if self.db.update_taseron_personel(
                    personel_id,
                    ad_input.text().strip(),
                    gunluk_spin.value(),
                    saatlik_spin.value()
                ):
                    QMessageBox.information(self, "Başarılı", "Personel bilgileri güncellendi")
                    self.load_personel()
                    self.load_puantaj()  # Puantaj kayıtlarını da yeniden yükle (ücret değişmiş olabilir)
                else:
                    QMessageBox.warning(self, "Uyarı", "Personel güncellenirken bir hata oluştu")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Personel güncellenirken hata oluştu:\n{str(e)}")
    
    def delete_personel(self):
        """Personel sil"""
        if not self.current_is_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir iş seçin")
            return
        
        current_row = self.personel_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz bir personeli seçin")
            return
        
        personel_id_item = self.personel_table.item(current_row, 0)
        if not personel_id_item:
            return
        
        personel_id = int(personel_id_item.text())
        personel = self.db.get_taseron_personel_by_id(personel_id)
        
        if not personel:
            QMessageBox.warning(self, "Uyarı", "Personel bulunamadı")
            return
        
        reply = QMessageBox.question(
            self, "Onay",
            f"'{personel['ad_soyad']}' personelini silmek istediğinize emin misiniz?\n\n"
            "Bu işlem geri alınamaz ve tüm puantaj kayıtları da silinecektir.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self.db.delete_taseron_personel(personel_id):
                    QMessageBox.information(self, "Başarılı", "Personel silindi")
                    self.load_personel()
                    self.load_puantaj()  # Puantaj listesini de güncelle
                else:
                    QMessageBox.warning(self, "Uyarı", "Personel silinirken bir hata oluştu")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Personel silinirken hata oluştu:\n{str(e)}")
    
    def load_personel(self):
        """Personel listesini yükle (günlük ücrete göre yüksekten düşüğe sıralı)"""
        if not self.current_is_id:
            self.personel_table.setRowCount(0)
            return
        
        personel_list = self.db.get_taseron_personel(self.current_is_id)
        # Günlük ücrete göre yüksekten düşüğe sırala
        personel_list.sort(key=lambda x: x.get('gunluk_ucret', 0), reverse=True)
        
        self.personel_table.setRowCount(len(personel_list))
        
        for row, personel in enumerate(personel_list):
            self.personel_table.setItem(row, 0, QTableWidgetItem(str(personel['id'])))
            self.personel_table.setItem(row, 1, QTableWidgetItem(personel['ad_soyad']))
            self.personel_table.setItem(row, 2, QTableWidgetItem(f"{personel['gunluk_ucret']:,.2f}"))
            self.personel_table.setItem(row, 3, QTableWidgetItem(f"{personel['saatlik_ucret']:,.2f}"))
            
            # Satır yüksekliğini isim soyisim uzunluğuna göre ayarla
            ad_soyad = personel['ad_soyad']
            # Uzun isimler için satır yüksekliğini artır
            if len(ad_soyad) > 25:
                # Çok uzun isimler için daha yüksek satır
                self.personel_table.setRowHeight(row, max(35, min(60, len(ad_soyad) // 2 + 20)))
            else:
                # Normal isimler için varsayılan yükseklik
                self.personel_table.setRowHeight(row, 35)
        
        self.puantaj_total_label.setText(f"Toplam Personel: {len(personel_list)}")
    
    def add_puantaj(self):
        """Puantaj ekle"""
        if not self.current_is_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir iş seçin")
            return
        
        personel_list = self.db.get_taseron_personel(self.current_is_id)
        if not personel_list:
            QMessageBox.warning(self, "Uyarı", "Önce personel eklemelisiniz")
            return
        
        from PyQt6.QtWidgets import QDialog, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Puantaj Ekle")
        dialog.setGeometry(400, 400, 400, 250)
        
        layout = QFormLayout(dialog)
        
        personel_combo = QComboBox()
        for personel in personel_list:
            personel_combo.addItem(personel['ad_soyad'], personel['id'])
        layout.addRow("Personel:", personel_combo)
        
        tarih_input = QDateEdit()
        tarih_input.setDate(QDate.currentDate())
        tarih_input.setCalendarPopup(True)
        tarih_input.setDisplayFormat("dd.MM.yyyy")
        tarih_input.setMinimumDate(QDate(2020, 1, 1))
        tarih_input.setMaximumDate(QDate(2100, 12, 31))
        layout.addRow("Tarih Seçin:", tarih_input)
        
        saat_spin = QDoubleSpinBox()
        saat_spin.setRange(0, 24)
        saat_spin.setDecimals(2)
        layout.addRow("Çalışma Saati:", saat_spin)
        
        gun_spin = QSpinBox()
        gun_spin.setRange(0, 31)
        layout.addRow("Çalışma Günü:", gun_spin)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Ekle")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.db.add_taseron_puantaj(
                    personel_combo.currentData(),
                    tarih_input.date().toString("yyyy-MM-dd"),
                    saat_spin.value(),
                    gun_spin.value()
                )
                QMessageBox.information(self, "Başarılı", "Puantaj eklendi")
                self.load_puantaj()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Puantaj eklenirken hata oluştu:\n{str(e)}")
    
    def bulk_add_puantaj(self):
        """Toplu puantaj ekle - Bir tarih seçip birden fazla personeli tek seferde ekle"""
        if not self.current_is_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir iş seçin")
            return
        
        personel_list = self.db.get_taseron_personel(self.current_is_id)
        if not personel_list:
            QMessageBox.warning(self, "Uyarı", "Önce personel eklemelisiniz")
            return
        
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QScrollArea
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Toplu Puantaj Ekle")
        dialog.setGeometry(300, 100, 600, 700)
        
        main_layout = QVBoxLayout(dialog)
        
        # Tarih seçici
        tarih_layout = QHBoxLayout()
        tarih_layout.addWidget(QLabel("Tarih Seçin:"))
        tarih_input = QDateEdit()
        tarih_input.setDate(QDate.currentDate())
        tarih_input.setCalendarPopup(True)
        tarih_input.setDisplayFormat("dd.MM.yyyy")
        tarih_input.setMinimumDate(QDate(2020, 1, 1))
        tarih_input.setMaximumDate(QDate(2100, 12, 31))
        tarih_layout.addWidget(tarih_input)
        tarih_layout.addStretch()
        main_layout.addLayout(tarih_layout)
        
        # Varsayılan değerler
        default_layout = QHBoxLayout()
        default_layout.addWidget(QLabel("Varsayılan Değerler:"))
        
        default_saat = QDoubleSpinBox()
        default_saat.setRange(0, 24)
        default_saat.setDecimals(2)
        default_saat.setValue(8.0)
        default_layout.addWidget(QLabel("Saat:"))
        default_layout.addWidget(default_saat)
        
        default_gun = QSpinBox()
        default_gun.setRange(0, 31)
        default_gun.setValue(1)
        default_layout.addWidget(QLabel("Gün:"))
        default_layout.addWidget(default_gun)
        default_layout.addStretch()
        main_layout.addLayout(default_layout)
        
        # Personel listesi (scroll area)
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Personel checkbox'ları ve input'ları
        personel_widgets = {}
        personel_frames = {}  # Frame referanslarını sakla (silme için)
        
        # Toplam tutar gösterimi (önce tanımla - calculate_total için gerekli)
        total_label = QLabel("Toplam Bedel: 0.00 ₺")
        total_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        total_label.setStyleSheet("color: #4CAF50; padding: 10px; background-color: #1a1a2e; border-radius: 5px;")
        total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        def calculate_total():
            """Seçili personellerin toplam bedelini hesapla"""
            toplam = 0.0
            for personel_id, widgets in personel_widgets.items():
                if widgets['checkbox'].isChecked():
                    # Personel bilgilerini al
                    personel = next((p for p in personel_list if p['id'] == personel_id), None)
                    if personel:
                        calisma_gunu = widgets['gun'].value()
                        calisma_saati = widgets['saat'].value()
                        
                        # Ücreti hesapla (günlük ücret öncelikli)
                        if calisma_gunu > 0 and personel.get('gunluk_ucret', 0) > 0:
                            toplam += calisma_gunu * personel['gunluk_ucret']
                        elif calisma_saati > 0 and personel.get('saatlik_ucret', 0) > 0:
                            toplam += calisma_saati * personel['saatlik_ucret']
            
            total_label.setText(f"Toplam Bedel: {toplam:,.2f} ₺")
        
        def add_personel_row(personel):
            """Personel satırı ekle"""
            personel_frame = QGroupBox(f"{personel['ad_soyad']} (Günlük: {personel.get('gunluk_ucret', 0):,.2f} ₺)")
            personel_layout = QHBoxLayout()
            
            checkbox = QCheckBox()
            checkbox.setChecked(True)  # Varsayılan olarak seçili
            personel_layout.addWidget(checkbox)
            
            personel_layout.addWidget(QLabel("Saat:"))
            saat_spin = QDoubleSpinBox()
            saat_spin.setRange(0, 24)
            saat_spin.setDecimals(2)
            saat_spin.setValue(8.0)
            personel_layout.addWidget(saat_spin)
            
            personel_layout.addWidget(QLabel("Gün:"))
            gun_spin = QSpinBox()
            gun_spin.setRange(0, 31)
            gun_spin.setValue(1)  # Varsayılan olarak 1 (gelmeyenler için manuel 0 yazılacak)
            personel_layout.addWidget(gun_spin)
            
            # Silme butonu
            btn_remove = QPushButton("✖")
            btn_remove.setMaximumWidth(30)
            btn_remove.setStyleSheet("background-color: #c9184a; color: white; font-weight: bold;")
            btn_remove.clicked.connect(lambda checked, pid=personel['id']: remove_personel_row(pid))
            personel_layout.addWidget(btn_remove)
            
            personel_layout.addStretch()
            personel_frame.setLayout(personel_layout)
            scroll_layout.addWidget(personel_frame)
            
            personel_widgets[personel['id']] = {
                'checkbox': checkbox,
                'saat': saat_spin,
                'gun': gun_spin,
                'ad_soyad': personel['ad_soyad'],
                'frame': personel_frame
            }
            personel_frames[personel['id']] = personel_frame
            
            # Signal'ları bağla
            checkbox.toggled.connect(calculate_total)
            saat_spin.valueChanged.connect(calculate_total)
            gun_spin.valueChanged.connect(calculate_total)
        
        def remove_personel_row(personel_id):
            """Personel satırını kaldır"""
            if personel_id in personel_frames:
                personel_frames[personel_id].setParent(None)
                personel_frames[personel_id].deleteLater()
                del personel_frames[personel_id]
                if personel_id in personel_widgets:
                    del personel_widgets[personel_id]
                calculate_total()
        
        # Mevcut personelleri ekle
        for personel in personel_list:
            add_personel_row(personel)
        
        # Yeni personel ekleme butonu
        btn_add_personel = QPushButton("➕ Yeni Personel Ekle")
        btn_add_personel.setStyleSheet("background-color: #4CAF50; font-weight: bold;")
        scroll_layout.addWidget(btn_add_personel)
        
        def add_new_personel():
            """Yeni personel ekle dialog'u"""
            from PyQt6.QtWidgets import QInputDialog
            ad_soyad, ok = QInputDialog.getText(
                dialog, "Yeni Personel",
                "Ad Soyad:"
            )
            if not ok or not ad_soyad.strip():
                return
            
            gunluk_ucret, ok = QInputDialog.getDouble(
                dialog, "Günlük Ücret",
                "Günlük Ücret (₺):", 0, 0, 999999, 2
            )
            if not ok:
                return
            
            saatlik_ucret = gunluk_ucret / 8.0 if gunluk_ucret > 0 else 0
            
            try:
                # Veritabanına ekle
                new_personel_id = self.db.add_taseron_personel(
                    self.current_is_id,
                    ad_soyad.strip(),
                    gunluk_ucret,
                    saatlik_ucret
                )
                
                # Listeye ekle
                new_personel = {
                    'id': new_personel_id,
                    'ad_soyad': ad_soyad.strip(),
                    'gunluk_ucret': gunluk_ucret,
                    'saatlik_ucret': saatlik_ucret
                }
                personel_list.append(new_personel)
                
                # Personel listesini tekrar sırala
                personel_list.sort(key=lambda x: x.get('gunluk_ucret', 0), reverse=True)
                
                # Yeni personeli ekle (sıralı konuma)
                add_personel_row(new_personel)
                
                QMessageBox.information(dialog, "Başarılı", "Personel eklendi")
            except Exception as e:
                QMessageBox.critical(dialog, "Hata", f"Personel eklenirken hata oluştu:\n{str(e)}")
        
        btn_add_personel.clicked.connect(add_new_personel)
        
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)
        
        # Toplam tutar gösterimini ekle
        main_layout.addWidget(total_label)
        
        # Varsayılan değerleri uygula butonu
        def apply_defaults():
            for widgets in personel_widgets.values():
                widgets['saat'].setValue(default_saat.value())
                widgets['gun'].setValue(1)  # Her zaman 1 olarak ayarla
            calculate_total()  # Toplamı güncelle
        
        btn_apply_defaults = QPushButton("Varsayılanları Uygula")
        btn_apply_defaults.clicked.connect(apply_defaults)
        main_layout.addWidget(btn_apply_defaults)
        
        # Varsayılan değerler değiştiğinde de toplamı güncelle
        default_saat.valueChanged.connect(calculate_total)
        default_gun.valueChanged.connect(calculate_total)
        
        # İlk toplam hesaplama
        calculate_total()
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Seçilenleri Ekle")
        btn_ok.setStyleSheet("background-color: #4CAF50; font-weight: bold;")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        main_layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            tarih_str = tarih_input.date().toString("yyyy-MM-dd")
            eklenen_sayisi = 0
            hata_sayisi = 0
            
            for personel_id, widgets in personel_widgets.items():
                if widgets['checkbox'].isChecked():
                    try:
                        self.db.add_taseron_puantaj(
                            personel_id,
                            tarih_str,
                            widgets['saat'].value(),
                            widgets['gun'].value()
                        )
                        eklenen_sayisi += 1
                    except Exception as e:
                        hata_sayisi += 1
                        print(f"Puantaj ekleme hatası ({widgets['ad_soyad']}): {e}")
            
            if eklenen_sayisi > 0:
                QMessageBox.information(
                    self, "Başarılı",
                    f"{eklenen_sayisi} personel için puantaj eklendi!\n"
                    f"Tarih: {tarih_input.date().toString('dd.MM.yyyy')}"
                )
                self.load_puantaj()
            else:
                QMessageBox.warning(self, "Uyarı", "Hiçbir personel seçilmedi veya ekleme başarısız oldu")
            
            if hata_sayisi > 0:
                QMessageBox.warning(self, "Uyarı", f"{hata_sayisi} personel için hata oluştu")
    
    def edit_puantaj(self):
        """Puantaj kaydını düzenle"""
        if not self.current_is_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir iş seçin")
            return
        
        current_row = self.puantaj_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz bir kaydı seçin")
            return
        
        # ID'yi al
        id_item = self.puantaj_table.item(current_row, 0)
        if not id_item:
            return
        
        puantaj_id = id_item.data(Qt.ItemDataRole.UserRole)
        if not puantaj_id:
            return
        
        puantaj = self.db.get_taseron_puantaj_by_id(puantaj_id)
        if not puantaj:
            QMessageBox.warning(self, "Uyarı", "Puantaj kaydı bulunamadı")
            return
        
        from PyQt6.QtWidgets import QDialog, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Puantaj Düzenle")
        dialog.setGeometry(400, 400, 400, 250)
        
        layout = QFormLayout(dialog)
        
        # Personel (sadece göster, değiştirilemez)
        personel_label = QLabel(puantaj.get('ad_soyad', ''))
        personel_label.setStyleSheet("font-weight: bold;")
        layout.addRow("Personel:", personel_label)
        
        tarih_input = QDateEdit()
        try:
            from datetime import datetime
            tarih_obj = datetime.strptime(puantaj['tarih'], "%Y-%m-%d")
            tarih_input.setDate(QDate(tarih_obj.year, tarih_obj.month, tarih_obj.day))
        except:
            tarih_input.setDate(QDate.currentDate())
        tarih_input.setCalendarPopup(True)
        tarih_input.setDisplayFormat("dd.MM.yyyy")
        tarih_input.setMinimumDate(QDate(2020, 1, 1))
        tarih_input.setMaximumDate(QDate(2100, 12, 31))
        layout.addRow("Tarih:", tarih_input)
        
        saat_spin = QDoubleSpinBox()
        saat_spin.setRange(0, 24)
        saat_spin.setDecimals(2)
        saat_spin.setValue(puantaj.get('calisma_saati', 0))
        layout.addRow("Çalışma Saati:", saat_spin)
        
        gun_spin = QSpinBox()
        gun_spin.setRange(0, 31)
        gun_spin.setValue(puantaj.get('calisma_gunu', 0))
        layout.addRow("Çalışma Günü:", gun_spin)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Kaydet")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                if self.db.update_taseron_puantaj(
                    puantaj_id,
                    tarih_input.date().toString("yyyy-MM-dd"),
                    saat_spin.value(),
                    gun_spin.value()
                ):
                    QMessageBox.information(self, "Başarılı", "Puantaj kaydı güncellendi")
                    self.load_puantaj()
                else:
                    QMessageBox.warning(self, "Uyarı", "Puantaj güncellenirken bir hata oluştu")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Puantaj güncellenirken hata oluştu:\n{str(e)}")
    
    def delete_puantaj(self):
        """Puantaj kaydını sil"""
        if not self.current_is_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir iş seçin")
            return
        
        current_row = self.puantaj_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz bir kaydı seçin")
            return
        
        # ID'yi al
        id_item = self.puantaj_table.item(current_row, 0)
        if not id_item:
            return
        
        puantaj_id = id_item.data(Qt.ItemDataRole.UserRole)
        if not puantaj_id:
            return
        
        # Personel adını al (onay mesajı için)
        personel_item = self.puantaj_table.item(current_row, 2)
        personel_adi = personel_item.text() if personel_item else "bilinmeyen"
        
        tarih_item = self.puantaj_table.item(current_row, 1)
        tarih = tarih_item.text() if tarih_item else "bilinmeyen"
        
        reply = QMessageBox.question(
            self, "Onay",
            f"'{personel_adi}' personelinin '{tarih}' tarihli puantaj kaydını silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self.db.delete_taseron_puantaj(puantaj_id):
                    QMessageBox.information(self, "Başarılı", "Puantaj kaydı silindi")
                    self.load_puantaj()
                else:
                    QMessageBox.warning(self, "Uyarı", "Puantaj silinirken bir hata oluştu")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Puantaj silinirken hata oluştu:\n{str(e)}")
    
    def clear_puantaj_filter(self):
        """Puantaj tarih filtresini temizle - tüm kayıtları göster"""
        if hasattr(self, 'puantaj_filter_enabled'):
            self.puantaj_filter_enabled = False
            self.load_puantaj()
            self.puantaj_filter_enabled = True
    
    def load_puantaj(self):
        """Puantaj listesini yükle (tarih filtresi ile)"""
        if not self.current_is_id:
            self.puantaj_table.setRowCount(0)
            return
        
        puantaj_list = self.db.get_taseron_puantaj(self.current_is_id)
        
        # Tarih filtresi uygula
        if hasattr(self, 'puantaj_tarih_filter') and hasattr(self, 'puantaj_filter_enabled') and self.puantaj_filter_enabled:
            filter_date = self.puantaj_tarih_filter.date()
            filter_date_str = filter_date.toString("yyyy-MM-dd")
            puantaj_list = [p for p in puantaj_list if p['tarih'] == filter_date_str]
        
        # Tarihe göre sırala (en yeni önce)
        puantaj_list.sort(key=lambda x: x.get('tarih', ''), reverse=True)
        
        self.puantaj_table.setRowCount(len(puantaj_list))
        
        for row, puantaj in enumerate(puantaj_list):
            # Tarihi Türkçe formatında göster
            tarih_str = puantaj['tarih']
            try:
                from datetime import datetime
                tarih_obj = datetime.strptime(tarih_str, "%Y-%m-%d")
                tarih_formatted = tarih_obj.strftime("%d.%m.%Y")
            except:
                tarih_formatted = tarih_str
            
            # ID'yi sakla (ilk sütuna)
            id_item = QTableWidgetItem(str(puantaj.get('id', '')))
            id_item.setData(Qt.ItemDataRole.UserRole, puantaj.get('id'))
            self.puantaj_table.setItem(row, 0, id_item)
            
            self.puantaj_table.setItem(row, 1, QTableWidgetItem(tarih_formatted))
            self.puantaj_table.setItem(row, 2, QTableWidgetItem(puantaj.get('ad_soyad', '')))
            self.puantaj_table.setItem(row, 3, QTableWidgetItem(f"{puantaj['calisma_saati']:,.2f}"))
            self.puantaj_table.setItem(row, 4, QTableWidgetItem(str(puantaj['calisma_gunu'])))
            self.puantaj_table.setItem(row, 5, QTableWidgetItem(f"{puantaj['toplam_ucret']:,.2f}"))
    
    def add_is_birim_fiyat(self):
        """İş ve birim fiyat ekle"""
        if not self.current_is_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir iş seçin")
            return
        
        from PyQt6.QtWidgets import QDialog, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("İş ve Birim Fiyat Ekle")
        dialog.setGeometry(400, 400, 400, 250)
        
        layout = QFormLayout(dialog)
        
        is_adi_input = QLineEdit()
        layout.addRow("İş Adı:", is_adi_input)
        
        birim_input = QLineEdit()
        birim_input.setText("m²")
        layout.addRow("Birim:", birim_input)
        
        birim_fiyat_spin = QDoubleSpinBox()
        birim_fiyat_spin.setRange(0, 999999)
        birim_fiyat_spin.setDecimals(2)
        layout.addRow("Birim Fiyat (₺):", birim_fiyat_spin)
        
        miktar_spin = QDoubleSpinBox()
        miktar_spin.setRange(0, 999999)
        miktar_spin.setDecimals(2)
        layout.addRow("Miktar:", miktar_spin)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Ekle")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if not is_adi_input.text().strip():
                QMessageBox.warning(self, "Uyarı", "İş adı gereklidir")
                return
            
            try:
                self.db.add_taseron_is_birim_fiyat(
                    self.current_is_id,
                    is_adi_input.text().strip(),
                    birim_input.text().strip(),
                    birim_fiyat_spin.value(),
                    miktar_spin.value()
                )
                QMessageBox.information(self, "Başarılı", "İş birim fiyat eklendi")
                self.load_is_birim_fiyat()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"İş birim fiyat eklenirken hata oluştu:\n{str(e)}")
    
    def load_is_birim_fiyat(self):
        """İş birim fiyat listesini yükle"""
        if not self.current_is_id:
            self.is_birim_fiyat_table.setRowCount(0)
            self.is_total_label.setText("Toplam Gelir: 0.00 ₺")
            return
        
        is_list = self.db.get_taseron_is_birim_fiyat(self.current_is_id)
        self.is_birim_fiyat_table.setRowCount(len(is_list))
        
        toplam = 0.0
        for row, is_item in enumerate(is_list):
            self.is_birim_fiyat_table.setItem(row, 0, QTableWidgetItem(str(is_item['id'])))
            self.is_birim_fiyat_table.setItem(row, 1, QTableWidgetItem(is_item['is_adi']))
            self.is_birim_fiyat_table.setItem(row, 2, QTableWidgetItem(is_item['birim']))
            self.is_birim_fiyat_table.setItem(row, 3, QTableWidgetItem(f"{is_item['birim_fiyat']:,.2f}"))
            self.is_birim_fiyat_table.setItem(row, 4, QTableWidgetItem(f"{is_item['miktar']:,.2f}"))
            self.is_birim_fiyat_table.setItem(row, 5, QTableWidgetItem(f"{is_item['toplam']:,.2f}"))
            toplam += is_item.get('toplam', 0)
        
        self.is_total_label.setText(f"Toplam Gelir: {toplam:,.2f} ₺")
    
    def edit_is_birim_fiyat(self):
        """İş birim fiyat düzenle"""
        # TODO: Düzenleme dialogu
        QMessageBox.information(self, "Bilgi", "Düzenleme özelliği yakında eklenecek")
    
    def delete_is_birim_fiyat(self):
        """İş birim fiyat sil"""
        # TODO: Silme işlemi
        QMessageBox.information(self, "Bilgi", "Silme özelliği yakında eklenecek")
    
    def add_gelir_gider(self, tip: str):
        """Gelir/Gider ekle"""
        if not self.current_is_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir iş seçin")
            return
        
        from PyQt6.QtWidgets import QDialog, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{tip.upper()} Ekle")
        dialog.setGeometry(400, 400, 400, 300)
        
        layout = QFormLayout(dialog)
        
        kategori_combo = QComboBox()
        if tip == 'gelir':
            kategori_combo.addItems(["İş", "Diğer"])
        else:
            kategori_combo.addItems(["Yemek", "Malzeme", "Personel İşçilik", "Diğer"])
        layout.addRow("Kategori:", kategori_combo)
        
        aciklama_input = QTextEdit()
        aciklama_input.setMaximumHeight(80)
        layout.addRow("Açıklama:", aciklama_input)
        
        tutar_spin = QDoubleSpinBox()
        tutar_spin.setRange(0, 999999999)
        tutar_spin.setDecimals(2)
        layout.addRow("Tutar (₺):", tutar_spin)
        
        tarih_input = QDateEdit()
        tarih_input.setDate(QDate.currentDate())
        tarih_input.setCalendarPopup(True)
        layout.addRow("Tarih:", tarih_input)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Ekle")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.db.add_taseron_gelir_gider(
                    self.current_is_id,
                    tip,
                    kategori_combo.currentText(),
                    aciklama_input.toPlainText().strip(),
                    tutar_spin.value(),
                    tarih_input.date().toString("yyyy-MM-dd")
                )
                QMessageBox.information(self, "Başarılı", f"{tip.upper()} eklendi")
                self.load_gelir_gider()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"{tip.upper()} eklenirken hata oluştu:\n{str(e)}")
    
    def load_gelir_gider(self):
        """Gelir/Gider listesini yükle"""
        if not self.current_is_id:
            self.gelir_gider_table.setRowCount(0)
            self.gelir_label.setText("0.00 ₺")
            self.gider_label.setText("0.00 ₺")
            self.kar_label.setText("0.00 ₺")
            return
        
        gelir_gider_list = self.db.get_taseron_gelir_gider(self.current_is_id)
        self.gelir_gider_table.setRowCount(len(gelir_gider_list))
        
        toplam_gelir = 0.0
        toplam_gider = 0.0
        
        for row, item in enumerate(gelir_gider_list):
            self.gelir_gider_table.setItem(row, 0, QTableWidgetItem(str(item['id'])))
            self.gelir_gider_table.setItem(row, 1, QTableWidgetItem(item['tarih']))
            self.gelir_gider_table.setItem(row, 2, QTableWidgetItem(item['tip'].upper()))
            self.gelir_gider_table.setItem(row, 3, QTableWidgetItem(item['kategori']))
            self.gelir_gider_table.setItem(row, 4, QTableWidgetItem(item.get('aciklama', '')))
            self.gelir_gider_table.setItem(row, 5, QTableWidgetItem(f"{item['tutar']:,.2f}"))
            
            if item['tip'] == 'gelir':
                toplam_gelir += item['tutar']
            else:
                toplam_gider += item['tutar']
        
        self.gelir_label.setText(f"{toplam_gelir:,.2f} ₺")
        self.gider_label.setText(f"{toplam_gider:,.2f} ₺")
        
        net_kar = toplam_gelir - toplam_gider
        self.kar_label.setText(f"{net_kar:,.2f} ₺")
        if net_kar >= 0:
            self.kar_label.setStyleSheet("color: #4CAF50;")
        else:
            self.kar_label.setStyleSheet("color: #c9184a;")
    
    def update_raporlar(self):
        """Raporları güncelle"""
        if not self.current_is_id:
            self.rapor_table.setRowCount(0)
            return
        
        period = self.rapor_period.currentText()
        start_date = None
        end_date = None
        
        if period == "Bu Ay":
            start_date = QDate.currentDate().toString("yyyy-MM-01")
            end_date = QDate.currentDate().toString("yyyy-MM-dd")
        elif period == "Bu Yıl":
            start_date = QDate.currentDate().toString("yyyy-01-01")
            end_date = QDate.currentDate().toString("yyyy-12-31")
        elif period == "Özel Tarih":
            start_date = self.start_date.date().toString("yyyy-MM-dd")
            end_date = self.end_date.date().toString("yyyy-MM-dd")
        
        gelir_gider_list = self.db.get_taseron_gelir_gider(
            self.current_is_id, start_date, end_date
        )
        
        # Aylık/Yıllık özet hesapla
        from collections import defaultdict
        monthly_data = defaultdict(lambda: {'gelir': 0.0, 'gider': 0.0})
        
        for item in gelir_gider_list:
            tarih = item['tarih']
            ay_yil = tarih[:7]  # YYYY-MM
            if item['tip'] == 'gelir':
                monthly_data[ay_yil]['gelir'] += item['tutar']
            else:
                monthly_data[ay_yil]['gider'] += item['tutar']
        
        self.rapor_table.setRowCount(len(monthly_data))
        for row, (ay_yil, data) in enumerate(sorted(monthly_data.items(), reverse=True)):
            net = data['gelir'] - data['gider']
            self.rapor_table.setItem(row, 0, QTableWidgetItem(ay_yil))
            self.rapor_table.setItem(row, 1, QTableWidgetItem(f"{data['gelir']:,.2f}"))
            self.rapor_table.setItem(row, 2, QTableWidgetItem(f"{data['gider']:,.2f}"))
            self.rapor_table.setItem(row, 3, QTableWidgetItem(f"{net:,.2f}"))
    
    def export_rapor(self):
        """Raporu Excel'e aktar"""
        # TODO: Excel export
        QMessageBox.information(self, "Bilgi", "Excel export özelliği yakında eklenecek")

