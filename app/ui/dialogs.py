"""
Dialog Pencereleri
Kalem ekleme/düzenleme dialogları
"""

from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QDoubleSpinBox, QComboBox, QPushButton,
    QLabel, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from app.core.database import DatabaseManager


class MetrajItemDialog(QDialog):
    """Metraj kalemi ekleme/düzenleme dialogu"""
    
    def __init__(self, db: DatabaseManager, parent=None, item_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Dialog'u başlat.
        
        Args:
            db: DatabaseManager instance
            parent: Parent widget
            item_data: Düzenleme için mevcut kalem verisi (None ise yeni ekleme)
        """
        super().__init__(parent)
        self.db = db
        self.item_data = item_data
        self.is_edit_mode = item_data is not None
        
        self.setWindowTitle("Metraj Kalemi Düzenle" if self.is_edit_mode else "Yeni Metraj Kalemi")
        self.setMinimumWidth(500)
        self.init_ui()
        
        if self.is_edit_mode:
            self.load_item_data()
            
    def init_ui(self) -> None:
        """Arayüzü oluştur"""
        layout = QVBoxLayout(self)
        
        # Form
        form = QFormLayout()
        
        # Kategori (İLK - kategori seçilince pozlar filtrelenir)
        self.kategori_combo = QComboBox()
        self.kategori_combo.setEditable(False)
        self.kategori_combo.addItem("-- Kategori Seçiniz --", None)
        self.load_categories()
        self.kategori_combo.currentIndexChanged.connect(self.on_category_changed)
        form.addRow("Kategori *:", self.kategori_combo)
        
        # Poz No (Kategoriye göre filtrelenmiş)
        self.poz_combo = QComboBox()
        self.poz_combo.setEditable(True)
        self.poz_combo.setMinimumWidth(200)
        self.poz_combo.setEnabled(False)  # Önce kategori seçilmeli
        self.poz_combo.addItem("-- Önce kategori seçiniz --")
        form.addRow("Poz No:", self.poz_combo)
        
        # Tanım
        self.tanim_input = QLineEdit()
        self.tanim_input.setPlaceholderText("Kalem tanımı giriniz")
        form.addRow("Tanım *:", self.tanim_input)
        
        # Miktar
        self.miktar_spin = QDoubleSpinBox()
        self.miktar_spin.setMinimum(0.0)
        self.miktar_spin.setMaximum(999999.99)
        self.miktar_spin.setDecimals(2)
        self.miktar_spin.setValue(1.0)
        form.addRow("Miktar *:", self.miktar_spin)
        
        # Birim
        self.birim_combo = QComboBox()
        self.birim_combo.setEditable(True)
        self.birim_combo.addItems(["m", "m²", "m³", "kg", "adet", "lt", "ton"])
        form.addRow("Birim *:", self.birim_combo)
        
        # Birim Fiyat
        self.birim_fiyat_spin = QDoubleSpinBox()
        self.birim_fiyat_spin.setMinimum(0.0)
        self.birim_fiyat_spin.setMaximum(999999.99)
        self.birim_fiyat_spin.setDecimals(2)
        self.birim_fiyat_spin.setValue(0.0)
        self.birim_fiyat_spin.valueChanged.connect(self.calculate_total)
        self.miktar_spin.valueChanged.connect(self.calculate_total)
        form.addRow("Birim Fiyat:", self.birim_fiyat_spin)
        
        # Toplam (otomatik hesaplanır)
        self.toplam_label = QLabel("0.00 ₺")
        self.toplam_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        form.addRow("Toplam:", self.toplam_label)
        
        # Notlar
        self.notlar_text = QTextEdit()
        self.notlar_text.setMaximumHeight(80)
        self.notlar_text.setPlaceholderText("İsteğe bağlı notlar...")
        form.addRow("Notlar:", self.notlar_text)
        
        layout.addLayout(form)
        
        # Poz seçildiğinde otomatik doldur
        self.poz_combo.currentTextChanged.connect(self.on_poz_selected)
        
        # Tüm pozları sakla (filtreleme için)
        self.all_pozlar = []
        self.load_all_pozlar()
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_save = QPushButton("Kaydet")
        btn_save.clicked.connect(self.accept)
        btn_save.setDefault(True)
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)
        
    def load_all_pozlar(self) -> None:
        """Tüm pozları yükle (filtreleme için)"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT poz_no, tanim, birim, kategori FROM pozlar ORDER BY kategori, poz_no")
                self.all_pozlar = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Pozlar yüklenirken hata: {e}")
            self.all_pozlar = []
            
    def on_category_changed(self, index: int) -> None:
        """Kategori değiştiğinde pozları filtrele"""
        # İlk öğe "-- Kategori Seçiniz --" ise
        if index == 0:
            self.poz_combo.clear()
            self.poz_combo.addItem("-- Önce kategori seçiniz --")
            self.poz_combo.setEnabled(False)
            return
            
        # Kategori seçildi
        selected_category = self.kategori_combo.currentText()
        self.poz_combo.clear()
        self.poz_combo.setEnabled(True)
        
        # Seçili kategoriye göre pozları filtrele
        filtered_pozlar = [
            poz for poz in self.all_pozlar 
            if poz.get('kategori', '') == selected_category
        ]
        
        if filtered_pozlar:
            for poz in filtered_pozlar:
                display_text = f"{poz['poz_no']} - {poz['tanim']}"
                self.poz_combo.addItem(display_text, poz['poz_no'])
        else:
            # Kategoriye ait poz yoksa manuel giriş için boş bırak
            self.poz_combo.addItem("-- Poz bulunamadı, manuel giriniz --", None)
            
    def load_pozlar(self) -> None:
        """Pozları yükle (eski metod - artık kullanılmıyor)"""
        # Bu metod artık kullanılmıyor, kategori değiştiğinde otomatik yükleniyor
        pass
            
    def load_categories(self) -> None:
        """Kategorileri yükle"""
        categories = [
            "Toprak İşleri", "Beton İşleri", "Duvar İşleri", "Sıva İşleri",
            "Boya İşleri", "Döşeme İşleri", "Çatı İşleri", "Elektrik Tesisatı",
            "Su Tesisatı", "Isıtma/Soğutma", "Alçıpan İşleri", "Kapı/Pencere",
            "Asansör", "Güvenlik Sistemleri", "Bahçe/Peyzaj", "Dış Cephe İşleri",
            "İzolasyon İşleri", "Merdiven İşleri", "Banyo/WC İşleri",
            "Mutfak İşleri", "Genel İşler"
        ]
        self.kategori_combo.addItems(categories)
        
    def on_poz_selected(self, text: str) -> None:
        """Poz seçildiğinde otomatik doldur"""
        try:
            # Poz no'yu ayır
            poz_no = text.split(" - ")[0] if " - " in text else text
            
            if not poz_no or poz_no == "-- Poz bulunamadı, manuel giriniz --":
                return
                
            # Poz bilgilerini getir
            poz = self.db.get_poz(poz_no)
            if poz:
                self.tanim_input.setText(poz['tanim'])
                self.birim_combo.setCurrentText(poz['birim'])
                if poz.get('resmi_fiyat', 0) > 0:
                    self.birim_fiyat_spin.setValue(poz['resmi_fiyat'])
                # Kategori zaten seçili olduğu için değiştirmiyoruz
        except:
            pass
            
    def calculate_total(self) -> None:
        """Toplam tutarı hesapla"""
        miktar = self.miktar_spin.value()
        birim_fiyat = self.birim_fiyat_spin.value()
        toplam = miktar * birim_fiyat
        self.toplam_label.setText(f"{toplam:.2f} ₺")
        
    def load_item_data(self) -> None:
        """Mevcut kalem verilerini yükle (düzenleme modu)"""
        if not self.item_data:
            return
            
        # Önce kategoriyi seç (bu pozları yükleyecek)
        kategori = self.item_data.get('kategori', '')
        if kategori:
            index = self.kategori_combo.findText(kategori)
            if index >= 0:
                self.kategori_combo.setCurrentIndex(index)
                # Kategori değişti, pozlar yüklendi, şimdi poz seçilebilir
                
        # Poz no
        poz_no = self.item_data.get('poz_no', '')
        if poz_no and self.poz_combo.isEnabled():
            index = self.poz_combo.findData(poz_no)
            if index >= 0:
                self.poz_combo.setCurrentIndex(index)
            else:
                self.poz_combo.setCurrentText(poz_no)
                
        # Diğer alanlar
        self.tanim_input.setText(self.item_data.get('tanim', ''))
        self.miktar_spin.setValue(self.item_data.get('miktar', 0))
        self.birim_combo.setCurrentText(self.item_data.get('birim', 'm'))
        self.birim_fiyat_spin.setValue(self.item_data.get('birim_fiyat', 0))
        self.notlar_text.setPlainText(self.item_data.get('notlar', ''))
        self.calculate_total()
        
    def get_data(self) -> Dict[str, Any]:
        """Dialog verilerini al"""
        poz_text = self.poz_combo.currentText()
        
        # Placeholder item'ları filtrele
        if poz_text.startswith("--") or not poz_text.strip():
            poz_no = None
        else:
            poz_no = poz_text.split(" - ")[0] if " - " in poz_text else poz_text
            # Poz no boş veya geçersizse None yap
            if not poz_no or poz_no.strip() == "":
                poz_no = None
        
        return {
            'poz_no': poz_no if poz_no else None,
            'tanim': self.tanim_input.text().strip(),
            'miktar': self.miktar_spin.value(),
            'birim': self.birim_combo.currentText().strip(),
            'birim_fiyat': self.birim_fiyat_spin.value(),
            'kategori': self.kategori_combo.currentText().strip(),
            'notlar': self.notlar_text.toPlainText().strip()
        }
        
    def accept(self) -> None:
        """Kaydet butonuna tıklandığında"""
        data = self.get_data()
        
        # Validasyon
        if self.kategori_combo.currentIndex() == 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir kategori seçiniz!")
            return
            
        if not data['tanim']:
            QMessageBox.warning(self, "Uyarı", "Tanım alanı zorunludur!")
            return
            
        if data['miktar'] <= 0:
            QMessageBox.warning(self, "Uyarı", "Miktar 0'dan büyük olmalıdır!")
            return
            
        if not data['birim']:
            QMessageBox.warning(self, "Uyarı", "Birim alanı zorunludur!")
            return
            
        super().accept()


class TaseronOfferDialog(QDialog):
    """Taşeron teklifi ekleme/düzenleme dialogu"""
    
    def __init__(self, db: DatabaseManager, parent=None, offer_data: Optional[Dict[str, Any]] = None, 
                 proje_id: Optional[int] = None) -> None:
        """
        Dialog'u başlat.
        
        Args:
            db: DatabaseManager instance
            parent: Parent widget
            offer_data: Düzenleme için mevcut teklif verisi (None ise yeni ekleme)
            proje_id: Proje ID'si (metraj kalemlerini yüklemek için)
        """
        super().__init__(parent)
        self.db = db
        self.offer_data = offer_data
        self.proje_id = proje_id
        self.is_edit_mode = offer_data is not None
        
        self.setWindowTitle("Taşeron Teklifi Düzenle" if self.is_edit_mode else "Yeni Taşeron Teklifi")
        self.setMinimumWidth(600)
        self.init_ui()
        
        if self.is_edit_mode:
            self.load_offer_data()
            
    def init_ui(self) -> None:
        """Arayüzü oluştur"""
        layout = QVBoxLayout(self)
        
        # Form
        form = QFormLayout()
        
        # Firma Adı
        self.firma_input = QLineEdit()
        self.firma_input.setPlaceholderText("Firma adı giriniz")
        form.addRow("Firma Adı *:", self.firma_input)
        
        # Metraj Kalemi Seçimi (opsiyonel)
        self.kalem_combo = QComboBox()
        self.kalem_combo.setEditable(False)
        self.kalem_combo.addItem("-- Metraj Kalemi Seçiniz (Opsiyonel) --", None)
        if self.proje_id:
            self.load_metraj_kalemleri()
        form.addRow("Metraj Kalemi:", self.kalem_combo)
        
        # Kalem seçildiğinde otomatik doldur
        self.kalem_combo.currentIndexChanged.connect(self.on_kalem_selected)
        
        # Poz No
        self.poz_input = QLineEdit()
        self.poz_input.setPlaceholderText("Poz numarası (opsiyonel)")
        form.addRow("Poz No:", self.poz_input)
        
        # Tanım
        self.tanim_input = QLineEdit()
        self.tanim_input.setPlaceholderText("İş tanımı giriniz")
        form.addRow("Tanım *:", self.tanim_input)
        
        # Miktar
        self.miktar_spin = QDoubleSpinBox()
        self.miktar_spin.setMinimum(0.0)
        self.miktar_spin.setMaximum(999999.99)
        self.miktar_spin.setDecimals(2)
        self.miktar_spin.setValue(1.0)
        self.miktar_spin.valueChanged.connect(self.calculate_total)
        form.addRow("Miktar:", self.miktar_spin)
        
        # Birim
        self.birim_combo = QComboBox()
        self.birim_combo.setEditable(True)
        self.birim_combo.addItems(["m", "m²", "m³", "kg", "adet", "lt", "ton"])
        form.addRow("Birim:", self.birim_combo)
        
        # Birim Fiyat
        self.fiyat_spin = QDoubleSpinBox()
        self.fiyat_spin.setMinimum(0.0)
        self.fiyat_spin.setMaximum(999999.99)
        self.fiyat_spin.setDecimals(2)
        self.fiyat_spin.setValue(0.0)
        self.fiyat_spin.valueChanged.connect(self.calculate_total)
        form.addRow("Birim Fiyat *:", self.fiyat_spin)
        
        # Toplam (otomatik hesaplanır)
        self.toplam_label = QLabel("0.00 ₺")
        self.toplam_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        form.addRow("Toplam:", self.toplam_label)
        
        # Durum
        self.durum_combo = QComboBox()
        self.durum_combo.addItems(["beklemede", "değerlendirmede", "onaylandı", "reddedildi"])
        form.addRow("Durum:", self.durum_combo)
        
        # Notlar
        self.notlar_text = QTextEdit()
        self.notlar_text.setMaximumHeight(80)
        self.notlar_text.setPlaceholderText("İsteğe bağlı notlar...")
        form.addRow("Notlar:", self.notlar_text)
        
        layout.addLayout(form)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_save = QPushButton("Kaydet")
        btn_save.clicked.connect(self.accept)
        btn_save.setDefault(True)
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)
        
    def load_metraj_kalemleri(self) -> None:
        """Projeye ait metraj kalemlerini yükle"""
        if not self.proje_id:
            return
            
        try:
            items = self.db.get_project_metraj(self.proje_id)
            for item in items:
                display_text = f"{item.get('poz_no', 'N/A')} - {item['tanim'][:50]}"
                self.kalem_combo.addItem(display_text, item['id'])
        except Exception as e:
            print(f"Metraj kalemleri yüklenirken hata: {e}")
            
    def on_kalem_selected(self, index: int) -> None:
        """Metraj kalemi seçildiğinde otomatik doldur"""
        if index == 0:  # Placeholder seçildi
            return
            
        kalem_id = self.kalem_combo.itemData(index)
        if not kalem_id:
            return
            
        try:
            items = self.db.get_project_metraj(self.proje_id)
            kalem = next((item for item in items if item['id'] == kalem_id), None)
            if kalem:
                self.poz_input.setText(kalem.get('poz_no', ''))
                self.tanim_input.setText(kalem.get('tanim', ''))
                self.miktar_spin.setValue(kalem.get('miktar', 1.0))
                self.birim_combo.setCurrentText(kalem.get('birim', 'm'))
                # Fiyat otomatik doldurulmaz (taşeron teklifi olduğu için)
        except Exception as e:
            print(f"Kalem bilgileri yüklenirken hata: {e}")
            
    def calculate_total(self) -> None:
        """Toplam tutarı hesapla"""
        miktar = self.miktar_spin.value()
        fiyat = self.fiyat_spin.value()
        toplam = miktar * fiyat
        self.toplam_label.setText(f"{toplam:.2f} ₺")
        
    def load_offer_data(self) -> None:
        """Mevcut teklif verilerini yükle (düzenleme modu)"""
        if not self.offer_data:
            return
            
        self.firma_input.setText(self.offer_data.get('firma_adi', ''))
        self.poz_input.setText(self.offer_data.get('poz_no', ''))
        self.tanim_input.setText(self.offer_data.get('tanim', ''))
        self.miktar_spin.setValue(self.offer_data.get('miktar', 0))
        self.birim_combo.setCurrentText(self.offer_data.get('birim', 'm'))
        self.fiyat_spin.setValue(self.offer_data.get('fiyat', 0))
        
        durum = self.offer_data.get('durum', 'beklemede')
        index = self.durum_combo.findText(durum)
        if index >= 0:
            self.durum_combo.setCurrentIndex(index)
            
        self.notlar_text.setPlainText(self.offer_data.get('notlar', ''))
        
        # Metraj kalemi seçimi
        kalem_id = self.offer_data.get('kalem_id')
        if kalem_id:
            index = self.kalem_combo.findData(kalem_id)
            if index >= 0:
                self.kalem_combo.setCurrentIndex(index)
        
        self.calculate_total()
        
    def get_data(self) -> Dict[str, Any]:
        """Dialog verilerini al"""
        kalem_id = self.kalem_combo.currentData()
        
        return {
            'firma_adi': self.firma_input.text().strip(),
            'kalem_id': kalem_id if kalem_id else None,
            'poz_no': self.poz_input.text().strip() or None,
            'tanim': self.tanim_input.text().strip(),
            'miktar': self.miktar_spin.value(),
            'birim': self.birim_combo.currentText().strip(),
            'fiyat': self.fiyat_spin.value(),
            'durum': self.durum_combo.currentText(),
            'notlar': self.notlar_text.toPlainText().strip()
        }
        
    def accept(self) -> None:
        """Kaydet butonuna tıklandığında"""
        data = self.get_data()
        
        # Validasyon
        if not data['firma_adi']:
            QMessageBox.warning(self, "Uyarı", "Firma adı zorunludur!")
            return
            
        if not data['tanim']:
            QMessageBox.warning(self, "Uyarı", "Tanım alanı zorunludur!")
            return
            
        if data['fiyat'] <= 0:
            QMessageBox.warning(self, "Uyarı", "Birim fiyat 0'dan büyük olmalıdır!")
            return
            
        super().accept()

