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
    """Metraj kalemi ekleme/düzenleme dialogu.

    mod = "kamu" → Poz No zorunlu, kategori sabit listeden, resmi BF
    mod = "serbest" → Poz No gizli, kategori serbest metin, birim fiyat serbest
    """

    # Serbest piyasada yaygın kullanılan kategori önerileri
    SERBEST_KATEGORILER = [
        "Kaba Yapı", "Temel İşleri", "Betonarme",
        "Duvar / Sıva / Boya", "Zemin / Döşeme",
        "Elektrik Tesisatı", "Su Tesisatı", "Doğalgaz Tesisatı",
        "Isıtma / Soğutma", "Çatı İşleri", "Dış Cephe",
        "İç Mekan Dekorasyon", "Mutfak / Banyo",
        "Bahçe / Peyzaj", "Diğer",
    ]

    # Kategori → yaygın iş kalemi önerileri (serbest piyasa modu)
    SERBEST_ALT_BASLIKLAR: dict = {
        "Kaba Yapı": [
            "Hafriyat kazısı",
            "Dolgu ve sıkıştırma",
            "Şap atılması",
            "Moloz taşıma ve nakli",
            "Kazı artığı boşaltımı",
        ],
        "Temel İşleri": [
            "Temel kazısı",
            "Grobeton (bodoslama)",
            "Temel betonarme",
            "Su yalıtımı (temel)",
            "Temel dolgusu ve sıkıştırma",
        ],
        "Betonarme": [
            "Kolon betonarme",
            "Kiriş betonarme",
            "Döşeme betonarme",
            "Merdiven betonarme",
            "Perde duvar betonarme",
            "Demir imalatı ve montajı",
            "Kalıp imalatı ve sökümü",
            "Hazır beton dökümü",
        ],
        "Duvar / Sıva / Boya": [
            "Tuğla duvar örme",
            "Gazbeton duvar örme",
            "Briket duvar örme",
            "İç sıva — çimento harcı",
            "İç sıva — alçı (makineli)",
            "Dış sıva",
            "İç boya (astar + 2 kat)",
            "Dış cephe boyası",
        ],
        "Zemin / Döşeme": [
            "Seramik döşeme",
            "Fayans döşeme",
            "Granit döşeme",
            "Mermer döşeme",
            "Ahşap parke döşeme",
            "Laminant parke döşeme",
            "Epoksi zemin kaplama",
            "Şap döşeme",
        ],
        "Elektrik Tesisatı": [
            "Elektrik tesisat (kaba)",
            "Elektrik tesisat (ince)",
            "Priz ve anahtar montajı",
            "Sigorta ve dağıtım kutusu",
            "Aydınlatma armatür montajı",
            "Kablo çekim işleri",
            "Topraklama sistemi",
            "Zayıf akım tesisatı",
        ],
        "Su Tesisatı": [
            "Sıhhi tesisat (kaba)",
            "Sıhhi tesisat (ince)",
            "Lavabo ve batarya montajı",
            "Klozet ve rezervuar montajı",
            "Duş kabini montajı",
            "Su sayacı ve vana montajı",
            "Pis su tesisatı",
            "Çatı su deposu montajı",
        ],
        "Doğalgaz Tesisatı": [
            "Doğalgaz boru hattı döşeme",
            "Kombi montajı ve devreye alma",
            "Gaz sayacı montajı",
            "Petek montajı",
            "Doğalgaz dedektörü montajı",
        ],
        "Isıtma / Soğutma": [
            "Split klima montajı",
            "VRF/VRV sistem montajı",
            "Kombi montajı",
            "Yerden ısıtma sistemi",
            "Fan-coil montajı",
            "Havalandırma kanalı döşeme",
            "Petek ve radyatör montajı",
        ],
        "Çatı İşleri": [
            "Çatı makası — çelik konstrüksiyon",
            "Çatı örtüsü — kiremit",
            "Çatı örtüsü — trapez sac",
            "Çatı ısı yalıtımı (XPS / taş yünü)",
            "Dere ve saçak olukları",
            "Çatı su yalıtımı (bitüm)",
            "Çatı penceresi montajı",
        ],
        "Dış Cephe": [
            "Dış cephe sıvası",
            "Dış cephe boyası",
            "Mantolama — EPS 5 cm",
            "Mantolama — taş yünü 5 cm",
            "Kompozit panel kaplama",
            "Doğaltaş cephe kaplama",
            "Cam giydirme cephe",
        ],
        "İç Mekan Dekorasyon": [
            "Asma tavan — alçıpan",
            "Alçıpan bölme duvar",
            "Kartonpiyer montajı",
            "İç kapı ve kasası montajı",
            "Gömme dolap montajı",
            "Dekoratif panel kaplama",
        ],
        "Mutfak / Banyo": [
            "Mutfak tezgahı montajı",
            "Banyo seramik döşeme",
            "Banyo fayans kaplama",
            "Mutfak dolabı montajı",
            "Banyo aksesuarları montajı",
            "Ankastre ürünler montajı",
            "Bulaşık / çamaşır makine bağlantısı",
        ],
        "Bahçe / Peyzaj": [
            "Bahçe duvarı örme",
            "Peyzaj düzenlemesi",
            "Bahçe aydınlatması",
            "Parke taşı döşeme",
            "Havuz yapımı",
            "Çim ekimi ve sulama sistemi",
            "Bahçe kapısı montajı",
        ],
        "Diğer": [
            "Yıkım ve söküm işleri",
            "Moloz taşıma ve boşaltım",
            "Proje ve ruhsat giderleri",
            "İskele kurulum ve söküm",
            "Genel işçilik gideri",
            "Şantiye kurulum ve yönetimi",
        ],
    }

    def __init__(
        self,
        db: DatabaseManager,
        parent=None,
        item_data: Optional[Dict[str, Any]] = None,
        mod: str = "kamu",
    ) -> None:
        """
        Args:
            db: DatabaseManager instance
            parent: Parent widget
            item_data: Düzenleme için mevcut kalem verisi (None ise yeni ekleme)
            mod: "kamu" veya "serbest"
        """
        super().__init__(parent)
        self.db = db
        self.item_data = item_data
        self.mod = mod  # "kamu" | "serbest"
        self.is_edit_mode = item_data is not None

        baslik = "Metraj Kalemi Düzenle" if self.is_edit_mode else "Yeni Metraj Kalemi"
        mod_etiketi = " Kamu" if mod == "kamu" else " Serbest Piyasa"
        self.setWindowTitle(f"{baslik} — {mod_etiketi}")
        self.setMinimumWidth(500)
        self.init_ui()

        if self.is_edit_mode:
            self.load_item_data()

    def init_ui(self) -> None:
        """Arayüzü oluştur — moda göre poz/kategori alanları değişir."""
        layout = QVBoxLayout(self)

        # Mod bilgi bandı
        mod_lbl = QLabel(
            " Kamu İhalesi Modu — Poz no ve resmi birim fiyat aktif"
            if self.mod == "kamu"
            else " Serbest Piyasa Modu — Poz no gizli, serbest tanım ve fiyat"
        )
        mod_lbl.setStyleSheet(
            "background:#0d2137; color:#00BFFF; padding:4px 8px; "
            "border-radius:4px; font-size:10px;"
        )
        layout.addWidget(mod_lbl)

        # Form
        form = QFormLayout()

        # ── KAMU MODU ── Kategori + Poz No (sabit DB listesi)
        if self.mod == "kamu":
            self.kategori_combo = QComboBox()
            self.kategori_combo.setEditable(False)
            self.kategori_combo.addItem("-- Kategori Seçiniz --", None)
            self.load_categories()
            self.kategori_combo.currentIndexChanged.connect(self.on_category_changed)
            form.addRow("Kategori *:", self.kategori_combo)

            self.poz_combo = QComboBox()
            self.poz_combo.setEditable(True)
            self.poz_combo.setMinimumWidth(200)
            self.poz_combo.setEnabled(False)
            self.poz_combo.addItem("-- Önce kategori seçiniz --")
            form.addRow("Poz No:", self.poz_combo)

        # ── SERBEST PIYASA MODU ── Kategori serbest metin, poz yok
        else:
            self.kategori_serbest = QComboBox()
            self.kategori_serbest.setEditable(True)
            self.kategori_serbest.addItem("")
            self.kategori_serbest.addItems(self.SERBEST_KATEGORILER)
            self.kategori_serbest.setCurrentText("")
            self.kategori_serbest.setPlaceholderText("Kategori seçin veya yazın…")
            form.addRow("Kategori:", self.kategori_serbest)
            # Poz No alanı serbest modda YOK

        # Tanım (kamu: QLineEdit | serbest: editable QComboBox ile öneri)
        if self.mod == "kamu":
            self.tanim_input = QLineEdit()
            self.tanim_input.setPlaceholderText("Kalem tanımı giriniz")
            form.addRow("Tanım *:", self.tanim_input)
        else:
            self.tanim_serbest = QComboBox()
            self.tanim_serbest.setEditable(True)
            self.tanim_serbest.setMinimumWidth(260)
            self.tanim_serbest.addItem("")
            self.tanim_serbest.setCurrentText("")
            self.tanim_serbest.setPlaceholderText("Kategori seçin, öneriler gelecek…")
            form.addRow("Tanım *:", self.tanim_serbest)
            # Kategori değişince tanım önerilerini güncelle
            self.kategori_serbest.currentTextChanged.connect(
                self._on_serbest_kategori_degistir
            )

        # Miktar
        self.miktar_spin = QDoubleSpinBox()
        self.miktar_spin.setMinimum(0.0)
        self.miktar_spin.setMaximum(99999999.99)
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
        self.birim_fiyat_spin.setMaximum(99999999.99)
        self.birim_fiyat_spin.setDecimals(2)
        self.birim_fiyat_spin.setValue(0.0)
        form.addRow("Birim Fiyat:", self.birim_fiyat_spin)

        # Toplam (düzenlenebilir - otomatik hesaplanır ama manuel değiştirilebilir)
        self.toplam_spin = QDoubleSpinBox()
        self.toplam_spin.setMinimum(0.0)
        self.toplam_spin.setMaximum(99999999999.99)
        self.toplam_spin.setDecimals(2)
        self.toplam_spin.setValue(0.0)
        self.toplam_spin.setSuffix(" ₺")
        self.toplam_spin.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        form.addRow("Toplam:", self.toplam_spin)

        # Otomatik hesaplama sinyalleri (tek sefer bağla)
        self.birim_fiyat_spin.valueChanged.connect(self.calculate_total)
        self.miktar_spin.valueChanged.connect(self.calculate_total)

        # Notlar
        self.notlar_text = QTextEdit()
        self.notlar_text.setMaximumHeight(80)
        self.notlar_text.setPlaceholderText("İsteğe bağlı notlar...")
        form.addRow("Notlar:", self.notlar_text)

        layout.addLayout(form)

        # Poz seçildiğinde otomatik doldur (sadece kamu modunda)
        if self.mod == "kamu":
            self.poz_combo.currentTextChanged.connect(self.on_poz_selected)

        # Tüm pozları sakla (filtreleme için — sadece kamu modunda gerekli)
        self.all_pozlar = []
        if self.mod == "kamu":
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
                cursor.execute(
                    "SELECT poz_no, tanim, birim, resmi_fiyat, kategori FROM pozlar ORDER BY kategori, poz_no"
                )
                self.all_pozlar = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Pozlar yüklenirken hata: {e}")
            self.all_pozlar = []

    def on_category_changed(self, index: int) -> None:
        """Kategori değiştiğinde pozları filtrele"""
        if index == 0:
            self.poz_combo.clear()
            self.poz_combo.addItem("-- Önce kategori seçiniz --")
            self.poz_combo.setEnabled(False)
            return

        selected_category = self.kategori_combo.currentText()
        self.poz_combo.clear()
        self.poz_combo.setEnabled(True)

        filtered_pozlar = [
            poz for poz in self.all_pozlar
            if poz.get('kategori', '') == selected_category
        ]

        if filtered_pozlar:
            for poz in filtered_pozlar:
                display_text = f"{poz['poz_no']} - {poz['tanim']}"
                self.poz_combo.addItem(display_text, poz['poz_no'])
        else:
            self.poz_combo.addItem("-- Poz bulunamadı, manuel giriniz --", None)

    def load_pozlar(self) -> None:
        """Pozları yükle (eski metod - artık kullanılmıyor)"""
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
        """Poz seçildiğinde tanım, birim ve fiyatı otomatik doldur"""
        try:
            if not text or text.startswith("--"):
                return

            poz_no = text.split(" - ")[0].strip() if " - " in text else text.strip()

            if not poz_no:
                return

            poz = None
            for p in self.all_pozlar:
                if p['poz_no'] == poz_no:
                    poz = p
                    break

            if not poz:
                poz = self.db.get_poz(poz_no)

            if poz:
                self.tanim_input.setText(poz['tanim'])
                self.birim_combo.setCurrentText(poz.get('birim', 'm'))
                # Önce pozlar tablosundaki resmi_fiyat'a bak
                resmi_fiyat = poz.get('resmi_fiyat') or 0
                # resmi_fiyat 0 ise birim_fiyatlar tablosundan aktif fiyatı çek
                if not resmi_fiyat:
                    bf = self.db.get_birim_fiyat(poz_no=poz_no)
                    if bf and bf.get('birim_fiyat'):
                        resmi_fiyat = bf['birim_fiyat']
                    elif bf is None:
                        # aktif fiyat yoksa pasif kayıtlara bak
                        bf = self.db.get_birim_fiyat(poz_no=poz_no, aktif_only=False)
                        if bf and bf.get('birim_fiyat'):
                            resmi_fiyat = bf['birim_fiyat']
                if resmi_fiyat and resmi_fiyat > 0:
                    self.birim_fiyat_spin.setValue(float(resmi_fiyat))
        except Exception as e:
            print(f"Poz seçimi hatası: {e}")

    def calculate_total(self) -> None:
        """Toplam tutarı hesapla"""
        miktar = self.miktar_spin.value()
        birim_fiyat = self.birim_fiyat_spin.value()
        toplam = miktar * birim_fiyat
        self.toplam_spin.blockSignals(True)
        self.toplam_spin.setValue(toplam)
        self.toplam_spin.blockSignals(False)

    def load_item_data(self) -> None:
        """Mevcut kalem verilerini yükle (düzenleme modu)"""
        if not self.item_data:
            return

        kategori = self.item_data.get('kategori', '')
        tanim = self.item_data.get('tanim', '')

        if self.mod == "serbest":
            if kategori:
                self.kategori_serbest.setCurrentText(kategori)
            self.tanim_serbest.setCurrentText(tanim)
        else:
            if kategori:
                index = self.kategori_combo.findText(kategori)
                if index >= 0:
                    self.kategori_combo.setCurrentIndex(index)

            poz_no = self.item_data.get('poz_no', '')
            if poz_no and self.poz_combo.isEnabled():
                index = self.poz_combo.findData(poz_no)
                if index >= 0:
                    self.poz_combo.setCurrentIndex(index)
                else:
                    self.poz_combo.setCurrentText(poz_no)

            self.tanim_input.setText(tanim)

        # Ortak alanlar
        self.miktar_spin.setValue(self.item_data.get('miktar', 0))
        self.birim_combo.setCurrentText(self.item_data.get('birim', 'm'))
        self.birim_fiyat_spin.setValue(self.item_data.get('birim_fiyat', 0))
        self.notlar_text.setPlainText(self.item_data.get('notlar', ''))

        toplam = self.item_data.get('toplam', 0)
        expected_total = self.item_data.get('miktar', 0) * self.item_data.get('birim_fiyat', 0)
        if abs(toplam - expected_total) > 0.01:
            self.toplam_spin.setValue(toplam)
        else:
            self.calculate_total()

    def _on_serbest_kategori_degistir(self, kategori: str) -> None:
        """Serbest modda kategori değişince tanım önerilerini güncelle."""
        onceki_tanim = self.tanim_serbest.currentText()
        oneriler = self.SERBEST_ALT_BASLIKLAR.get(kategori, [])
        self.tanim_serbest.blockSignals(True)
        self.tanim_serbest.clear()
        self.tanim_serbest.addItem("")
        self.tanim_serbest.addItems(oneriler)
        if onceki_tanim and onceki_tanim in oneriler:
            self.tanim_serbest.setCurrentText(onceki_tanim)
        else:
            self.tanim_serbest.setCurrentText("")
        self.tanim_serbest.blockSignals(False)

    def get_data(self) -> Dict[str, Any]:
        """Dialog verilerini al (moda göre poz_no ve kategori farklı döner)."""
        toplam = self.toplam_spin.value()

        if self.mod == "serbest":
            return {
                'poz_no': None,
                'tanim': self.tanim_serbest.currentText().strip(),
                'miktar': self.miktar_spin.value(),
                'birim': self.birim_combo.currentText().strip(),
                'birim_fiyat': self.birim_fiyat_spin.value(),
                'toplam': toplam,
                'kategori': self.kategori_serbest.currentText().strip(),
                'notlar': self.notlar_text.toPlainText().strip(),
            }

        # Kamu modu
        poz_text = self.poz_combo.currentText()
        if poz_text.startswith("--") or not poz_text.strip():
            poz_no = None
        else:
            poz_no = poz_text.split(" - ")[0] if " - " in poz_text else poz_text
            if not poz_no or poz_no.strip() == "":
                poz_no = None

        return {
            'poz_no': poz_no if poz_no else None,
            'tanim': self.tanim_input.text().strip(),
            'miktar': self.miktar_spin.value(),
            'birim': self.birim_combo.currentText().strip(),
            'birim_fiyat': self.birim_fiyat_spin.value(),
            'toplam': toplam,
            'kategori': (
                self.kategori_combo.currentText().strip()
                if self.kategori_combo.currentIndex() > 0
                else ''
            ),
            'notlar': self.notlar_text.toPlainText().strip(),
        }

    def accept(self) -> None:
        """Kaydet butonuna tıklandığında — validasyon moda göre değişir."""
        data = self.get_data()

        if self.mod == "kamu" and self.kategori_combo.currentIndex() == 0:
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

        # Bug-3: Kamu modunda poz_no zorunlu alan
        if self.mod == "kamu" and not data.get('poz_no'):
            QMessageBox.warning(
                self, "Zorunlu Alan",
                "Poz numarası zorunludur!\nLütfen listeden bir poz seçiniz."
            )
            return

        # Bug-1: Kamu modunda birim uyuşmazlık kontrolü
        if self.mod == "kamu" and data.get('poz_no'):
            try:
                poz = self.db.get_poz(data['poz_no'])
                if poz and poz.get('birim') and poz['birim'] != data['birim']:
                    yanit = QMessageBox.question(
                        self, "Birim Uyuşmazlığı",
                        f"Seçili pozun birimi:  {poz['birim']}\n"
                        f"Girilen birim:        {data['birim']}\n\n"
                        f"Birim yanlış girilmiş olabilir. Devam edilsin mi?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if yanit == QMessageBox.StandardButton.No:
                        return
            except Exception:
                pass

        # Bug-2: Sıfır birim fiyat uyarısı
        if data['birim_fiyat'] == 0:
            yanit = QMessageBox.question(
                self, "Sıfır Fiyat Uyarısı",
                "Birim fiyat sıfır (0) girildi.\n"
                "Bu kalem toplam maliyete katkı sağlamayacaktır.\n\n"
                "Yine de kaydetmek istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if yanit == QMessageBox.StandardButton.No:
                return

        super().accept()


class TaseronOfferDialog(QDialog):
    """Taşeron teklifi ekleme/düzenleme dialogu"""

    def __init__(
        self,
        db: DatabaseManager,
        parent=None,
        offer_data: Optional[Dict[str, Any]] = None,
        proje_id: Optional[int] = None,
    ) -> None:
        """
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

        self.setWindowTitle(
            "Taşeron Teklifi Düzenle" if self.is_edit_mode else "Yeni Taşeron Teklifi"
        )
        self.setMinimumWidth(600)
        self.init_ui()

        if self.is_edit_mode:
            self.load_offer_data()

    def init_ui(self) -> None:
        """Arayüzü oluştur"""
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Firma Adı
        self.firma_input = QLineEdit()
        self.firma_input.setPlaceholderText("Firma adı giriniz")
        form.addRow("Firma Adı *:", self.firma_input)

        # Tüm metraj kalemlerini hafızada tut
        self._all_metraj_items = []
        if self.proje_id:
            try:
                self._all_metraj_items = self.db.get_project_metraj(self.proje_id)
            except Exception as e:
                print(f"Metraj kalemleri yüklenirken hata: {e}")

        # İş Kolu (Kategori) Seçimi
        self.kategori_combo = QComboBox()
        self.kategori_combo.setEditable(False)
        self.kategori_combo.addItem("-- Tüm İş Kolları --", None)
        kategoriler = sorted(set(
            item.get('kategori', '') or 'Kategorisiz'
            for item in self._all_metraj_items
        ))
        for kat in kategoriler:
            self.kategori_combo.addItem(kat, kat)
        self.kategori_combo.currentIndexChanged.connect(self._filter_metraj_kalemleri)
        form.addRow("İş Kolu:", self.kategori_combo)

        # Metraj Kalemi Seçimi (opsiyonel)
        self.kalem_combo = QComboBox()
        self.kalem_combo.setEditable(False)
        self._populate_kalem_combo(self._all_metraj_items)
        form.addRow("Metraj Kalemi:", self.kalem_combo)

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

    def _populate_kalem_combo(self, items) -> None:
        """Metraj kalemi combo'sunu verilen listeyle doldur"""
        self.kalem_combo.blockSignals(True)
        self.kalem_combo.clear()
        self.kalem_combo.addItem("-- Metraj Kalemi Seçiniz (Opsiyonel) --", None)
        for item in items:
            kategori = item.get('kategori', '') or ''
            poz = item.get('poz_no', 'N/A') or 'N/A'
            tanim = (item.get('tanim', '') or '')[:50]
            prefix = f"[{kategori}] " if kategori else ""
            display_text = f"{prefix}{poz} - {tanim}"
            self.kalem_combo.addItem(display_text, item['id'])
        self.kalem_combo.blockSignals(False)

    def _filter_metraj_kalemleri(self, index: int) -> None:
        """İş kolu seçimine göre metraj kalemlerini filtrele"""
        secilen_kategori = self.kategori_combo.itemData(index)
        if secilen_kategori is None:
            filtered = self._all_metraj_items
        else:
            filtered = [
                item for item in self._all_metraj_items
                if (item.get('kategori', '') or 'Kategorisiz') == secilen_kategori
            ]
        self._populate_kalem_combo(filtered)

    def on_kalem_selected(self, index: int) -> None:
        """Metraj kalemi seçildiğinde otomatik doldur"""
        if index == 0:
            return

        kalem_id = self.kalem_combo.itemData(index)
        if not kalem_id:
            return

        kalem = next(
            (item for item in self._all_metraj_items if item['id'] == kalem_id),
            None
        )
        if kalem:
            self.poz_input.setText(kalem.get('poz_no', ''))
            self.tanim_input.setText(kalem.get('tanim', ''))
            self.miktar_spin.setValue(kalem.get('miktar', 1.0))
            self.birim_combo.setCurrentText(kalem.get('birim', 'm'))

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

        kalem_id = self.offer_data.get('kalem_id')
        if kalem_id:
            kalem = next(
                (item for item in self._all_metraj_items if item['id'] == kalem_id),
                None
            )
            if kalem:
                kat = (kalem.get('kategori', '') or 'Kategorisiz')
                kat_index = self.kategori_combo.findData(kat)
                if kat_index >= 0:
                    self.kategori_combo.setCurrentIndex(kat_index)
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
