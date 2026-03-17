"""
EKAP — Elektronik Kamu Alımları Platformu Penceresi
Kamu İhale Kurumu ihaleleri arama ve takip arayüzü
"""
import logging
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QGroupBox, QFormLayout, QComboBox, QLineEdit,
    QSplitter, QTextEdit, QHeaderView, QMessageBox, QDateEdit,
    QDoubleSpinBox, QApplication, QCheckBox, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


class EKAPAramaThread(QThread):
    """Arka planda EKAP araması yapan thread"""
    sonuc_geldi = pyqtSignal(dict)
    hata_olustu = pyqtSignal(str)

    def __init__(self, engine, parametreler: dict):
        super().__init__()
        self.engine = engine
        self.parametreler = parametreler

    def run(self):
        try:
            sonuc = self.engine.ihale_ara(**self.parametreler)
            if not sonuc["basarili"] or not sonuc["ihaleler"]:
                demo = self.engine.demo_veri_uret(
                    self.parametreler.get("anahtar_kelime", "")
                )
                demo["_demo"] = True
                self.sonuc_geldi.emit(demo)
            else:
                self.sonuc_geldi.emit(sonuc)
        except Exception as e:
            self.hata_olustu.emit(str(e))


class EKAPWindow(QWidget):
    """EKAP ihale arama ve takip penceresi"""

    TABLO_SUTUNLARI = [
        "İhale No", "İhale Adı", "İdare", "İl",
        "Tür", "Usul", "İhale Tarihi", "Tahmini Bedel (₺)", "Durum",
    ]

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db
        self._arama_thread: Optional[EKAPAramaThread] = None

        try:
            from app.core.ekap_engine import EKAPEngine
            self.engine = EKAPEngine()
            self._engine_ok = True
        except Exception as e:
            logger.error(f"EKAPEngine yüklenemedi: {e}")
            self._engine_ok = False
            self.engine = None

        self._ui_olustur()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _ui_olustur(self):
        self.setStyleSheet("""
            QWidget { background-color: #1a1a2e; color: #e0e0e0; }
            QGroupBox { border: 1px solid #0f3460; border-radius: 6px;
                        margin-top: 10px; padding-top: 8px;
                        color: #00BFFF; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QTableWidget { background-color: #0d1117; color: #e0e0e0;
                           gridline-color: #1e2a3a; border: 1px solid #0f3460;
                           alternate-background-color: #0f1923; }
            QHeaderView::section { background-color: #0f3460; color: #00BFFF;
                                   padding: 6px; border: none; font-weight: bold; }
            QLineEdit { background-color: #16213e; color: #e0e0e0;
                        border: 1px solid #0f3460; padding: 5px; border-radius: 4px; }
            QComboBox { background-color: #16213e; color: #e0e0e0;
                        border: 1px solid #0f3460; padding: 5px; border-radius: 4px; }
            QDoubleSpinBox { background-color: #16213e; color: #e0e0e0;
                             border: 1px solid #0f3460; padding: 4px; border-radius: 4px; }
            QDateEdit { background-color: #16213e; color: #e0e0e0;
                        border: 1px solid #0f3460; padding: 4px; border-radius: 4px; }
            QPushButton { background-color: #0f3460; color: white;
                          padding: 7px 14px; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #1a5276; }
            QPushButton:disabled { background-color: #2c2c2c; color: #666; }
            QTextEdit { background-color: #0d1117; color: #e0e0e0;
                        border: 1px solid #0f3460; border-radius: 4px; }
            QCheckBox { color: #e0e0e0; }
        """)

        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(10, 10, 10, 10)
        ana_layout.setSpacing(8)

        # Başlık satırı
        ust = QHBoxLayout()
        baslik = QLabel("🏛 EKAP — Elektronik Kamu Alımları Platformu")
        baslik.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        baslik.setStyleSheet("color: #00BFFF;")
        ust.addWidget(baslik)
        ust.addStretch()
        self.baglanti_label = QLabel("⚪ Bağlantı kontrol edilmedi")
        self.baglanti_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        ust.addWidget(self.baglanti_label)
        test_btn = QPushButton("🔄 Bağlantı Testi")
        test_btn.clicked.connect(self._baglanti_test)
        ust.addWidget(test_btn)
        ana_layout.addLayout(ust)

        # Ana dikey splitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Arama formu ───────────────────────────────────────────────────────
        arama_widget = QWidget()
        arama_layout = QVBoxLayout(arama_widget)
        arama_layout.setContentsMargins(0, 0, 0, 0)

        arama_group = QGroupBox("🔍 İhale Arama ve Filtreleme")
        form_layout = QVBoxLayout(arama_group)

        # Satır 1: anahtar kelime
        s1 = QHBoxLayout()
        s1.addWidget(QLabel("Anahtar Kelime:"))
        self.kelime_input = QLineEdit()
        self.kelime_input.setPlaceholderText(
            "'okul yapım', 'yol onarım', 'hastane inşaatı'..."
        )
        self.kelime_input.returnPressed.connect(self._ara)
        s1.addWidget(self.kelime_input, 3)
        form_layout.addLayout(s1)

        # Satır 2: il + tür + durum
        s2 = QHBoxLayout()
        s2.addWidget(QLabel("İl:"))
        self.il_combo = QComboBox()
        self.il_combo.addItem("Tüm İller", "")
        if self._engine_ok:
            for il in self.engine.il_listesi():
                self.il_combo.addItem(il, il)
        s2.addWidget(self.il_combo)

        s2.addWidget(QLabel("Tür:"))
        self.tur_combo = QComboBox()
        self.tur_combo.addItem("Tümü", "")
        self.tur_combo.addItem("Yapım İşi", "1")
        self.tur_combo.addItem("Hizmet Alımı", "2")
        self.tur_combo.addItem("Mal Alımı", "3")
        self.tur_combo.addItem("Danışmanlık", "4")
        s2.addWidget(self.tur_combo)

        s2.addWidget(QLabel("Durum:"))
        self.durum_combo = QComboBox()
        self.durum_combo.addItem("İhale İlanı (Aktif)", "2")
        self.durum_combo.addItem("Sonuçlandı", "3")
        self.durum_combo.addItem("İptal Edildi", "4")
        self.durum_combo.addItem("Tümü", "")
        s2.addWidget(self.durum_combo)
        form_layout.addLayout(s2)

        # Satır 3: tarih + bedel
        s3 = QHBoxLayout()

        self.tarih_kullan_cb = QCheckBox("Tarih Filtresi")
        self.tarih_kullan_cb.setChecked(False)
        s3.addWidget(self.tarih_kullan_cb)

        s3.addWidget(QLabel("Başlangıç:"))
        self.baslangic_tarih = QDateEdit()
        self.baslangic_tarih.setCalendarPopup(True)
        self.baslangic_tarih.setDate(QDate.currentDate().addDays(-30))
        self.baslangic_tarih.setDisplayFormat("dd.MM.yyyy")
        s3.addWidget(self.baslangic_tarih)

        s3.addWidget(QLabel("Bitiş:"))
        self.bitis_tarih = QDateEdit()
        self.bitis_tarih.setCalendarPopup(True)
        self.bitis_tarih.setDate(QDate.currentDate().addDays(90))
        self.bitis_tarih.setDisplayFormat("dd.MM.yyyy")
        s3.addWidget(self.bitis_tarih)

        s3.addWidget(QLabel("Min (₺):"))
        self.min_bedel = QDoubleSpinBox()
        self.min_bedel.setRange(0, 1_000_000_000)
        self.min_bedel.setSingleStep(100_000)
        self.min_bedel.setPrefix("₺ ")
        s3.addWidget(self.min_bedel)

        s3.addWidget(QLabel("Max (₺):"))
        self.max_bedel = QDoubleSpinBox()
        self.max_bedel.setRange(0, 9_999_999_999)
        self.max_bedel.setSingleStep(1_000_000)
        self.max_bedel.setPrefix("₺ ")
        s3.addWidget(self.max_bedel)
        form_layout.addLayout(s3)

        # Buton satırı
        s4 = QHBoxLayout()
        self.ara_btn = QPushButton("🔍 İhale Ara")
        self.ara_btn.setStyleSheet(
            "background-color: #00BFFF; color: #0d0d0d; font-weight: bold; padding: 8px 20px;"
        )
        self.ara_btn.clicked.connect(self._ara)
        s4.addWidget(self.ara_btn)

        temizle_btn = QPushButton("🗑 Temizle")
        temizle_btn.clicked.connect(self._filtre_temizle)
        s4.addWidget(temizle_btn)

        demo_btn = QPushButton("🧪 Demo Veri")
        demo_btn.setStyleSheet("background-color: #6c3483;")
        demo_btn.clicked.connect(self._demo_goster)
        s4.addWidget(demo_btn)

        s4.addStretch()

        self.durum_label = QLabel("Arama yapmak için yukarıdaki formu doldurun.")
        self.durum_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        s4.addWidget(self.durum_label)

        form_layout.addLayout(s4)
        arama_layout.addWidget(arama_group)
        splitter.addWidget(arama_widget)

        # ── Sonuç + Detay ─────────────────────────────────────────────────────
        alt_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sol: Tablo
        tablo_widget = QWidget()
        tablo_layout = QVBoxLayout(tablo_widget)
        tablo_layout.setContentsMargins(0, 0, 0, 0)

        self.sonuc_baslik = QLabel("Sonuçlar (0 ihale)")
        self.sonuc_baslik.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.sonuc_baslik.setStyleSheet("color: #00BFFF; margin-bottom: 4px;")
        tablo_layout.addWidget(self.sonuc_baslik)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(len(self.TABLO_SUTUNLARI))
        self.tablo.setHorizontalHeaderLabels(self.TABLO_SUTUNLARI)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.tablo.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.tablo.setColumnWidth(0, 100)
        self.tablo.setColumnWidth(3, 90)
        self.tablo.setColumnWidth(4, 110)
        self.tablo.setColumnWidth(5, 120)
        self.tablo.setColumnWidth(6, 100)
        self.tablo.setColumnWidth(7, 140)
        self.tablo.setColumnWidth(8, 100)
        self.tablo.itemSelectionChanged.connect(self._secim_degisti)
        tablo_layout.addWidget(self.tablo)

        # Aksiyon butonları
        aksiyon = QHBoxLayout()
        self.detay_btn = QPushButton("📋 Detay")
        self.detay_btn.setEnabled(False)
        self.detay_btn.clicked.connect(lambda: self.detay_alani.setFocus())
        aksiyon.addWidget(self.detay_btn)

        self.metraj_btn = QPushButton("📊 Metraj'a Ekle")
        self.metraj_btn.setEnabled(False)
        self.metraj_btn.setStyleSheet("background-color: #1a6b3c;")
        self.metraj_btn.clicked.connect(self._metraja_ekle)
        aksiyon.addWidget(self.metraj_btn)

        self.kopyala_btn = QPushButton("📋 Kopyala")
        self.kopyala_btn.setEnabled(False)
        self.kopyala_btn.clicked.connect(self._secili_kopyala)
        aksiyon.addWidget(self.kopyala_btn)

        aksiyon.addStretch()
        tablo_layout.addLayout(aksiyon)
        alt_splitter.addWidget(tablo_widget)

        # Sağ: Detay paneli
        detay_widget = QWidget()
        detay_layout = QVBoxLayout(detay_widget)
        detay_layout.setContentsMargins(4, 0, 0, 0)

        detay_baslik = QLabel("📄 İhale Detayı")
        detay_baslik.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        detay_baslik.setStyleSheet("color: #00BFFF;")
        detay_layout.addWidget(detay_baslik)

        self.detay_alani = QTextEdit()
        self.detay_alani.setReadOnly(True)
        self.detay_alani.setFont(QFont("Consolas", 10))
        self.detay_alani.setPlaceholderText(
            "Tablodaki bir ihaleye tıklayarak detaylarını görün."
        )
        detay_layout.addWidget(self.detay_alani)

        # Teminat KPI
        teminat_group = QGroupBox("💰 Maliyet ve Teminat Hesabı")
        teminat_form = QFormLayout(teminat_group)
        self.lb_bedel = QLabel("—")
        self.lb_kdv = QLabel("—")
        self.lb_gecici = QLabel("—")
        self.lb_kesin = QLabel("—")
        teminat_form.addRow("Tahmini Bedel:", self.lb_bedel)
        teminat_form.addRow("KDV (%20):", self.lb_kdv)
        teminat_form.addRow("Geçici Teminat (%3):", self.lb_gecici)
        teminat_form.addRow("Kesin Teminat (%6):", self.lb_kesin)
        detay_layout.addWidget(teminat_group)

        alt_splitter.addWidget(detay_widget)
        alt_splitter.setSizes([700, 320])

        splitter.addWidget(alt_splitter)
        splitter.setSizes([240, 520])
        ana_layout.addWidget(splitter)

    # ── Slotlar ───────────────────────────────────────────────────────────────

    def _baglanti_test(self):
        if not self._engine_ok:
            self.baglanti_label.setText("❌ Engine yüklenemedi")
            return
        self.baglanti_label.setText("⏳ Test ediliyor...")
        QApplication.processEvents()
        ok = self.engine.baglanabilirlik_test()
        if ok:
            self.baglanti_label.setText("✅ EKAP'a bağlı")
            self.baglanti_label.setStyleSheet("color: #00ff88; font-size: 11px;")
        else:
            self.baglanti_label.setText("⚠️ Bağlantı yok — Demo mod aktif")
            self.baglanti_label.setStyleSheet("color: #ffaa00; font-size: 11px;")

    def _ara(self):
        if not self._engine_ok:
            QMessageBox.warning(self, "Hata", "EKAP Engine yüklenemedi.")
            return
        self.ara_btn.setEnabled(False)
        self.durum_label.setText("⏳ Aranıyor...")
        self.tablo.setRowCount(0)

        params: Dict[str, Any] = {
            "anahtar_kelime": self.kelime_input.text().strip(),
            "il":             self.il_combo.currentData() or "",
            "ihale_turu":     self.tur_combo.currentData() or "",
            "durum":          self.durum_combo.currentData() or "",
            "min_bedel":      self.min_bedel.value(),
            "max_bedel":      self.max_bedel.value(),
        }
        if self.tarih_kullan_cb.isChecked():
            params["baslangic_tarihi"] = self.baslangic_tarih.date().toString("dd.MM.yyyy")
            params["bitis_tarihi"]     = self.bitis_tarih.date().toString("dd.MM.yyyy")

        thread = EKAPAramaThread(self.engine, params)
        self._arama_thread = thread
        thread.sonuc_geldi.connect(self._sonuc_goster)
        thread.hata_olustu.connect(self._arama_hata)
        thread.start()

    def _demo_goster(self):
        if not self._engine_ok:
            return
        kelime = self.kelime_input.text().strip()
        sonuc = self.engine.demo_veri_uret(kelime)
        self._sonuc_goster(sonuc)

    def _filtre_temizle(self):
        self.kelime_input.clear()
        self.il_combo.setCurrentIndex(0)
        self.tur_combo.setCurrentIndex(0)
        self.durum_combo.setCurrentIndex(0)
        self.min_bedel.setValue(0)
        self.max_bedel.setValue(0)
        self.tarih_kullan_cb.setChecked(False)
        self.tablo.setRowCount(0)
        self.sonuc_baslik.setText("Sonuçlar (0 ihale)")
        self.durum_label.setText("Filtreler temizlendi.")

    def _sonuc_goster(self, sonuc: dict):
        self.ara_btn.setEnabled(True)
        ihaleler = sonuc.get("ihaleler", [])
        toplam   = sonuc.get("toplam", len(ihaleler))
        demo     = sonuc.get("_demo", False)

        self.tablo.setRowCount(0)
        self.tablo.setRowCount(len(ihaleler))

        for row, ihale in enumerate(ihaleler):
            d = ihale.to_dict() if hasattr(ihale, "to_dict") else ihale
            bedel = d.get("tahmini_bedel", 0) or 0

            degerler = [
                d.get("ihale_no", ""),
                d.get("ihale_adi", ""),
                d.get("idare_adi", ""),
                d.get("il", ""),
                d.get("ihale_turu", ""),
                d.get("ihale_usulu", ""),
                d.get("ihale_tarihi", ""),
                f"{bedel:,.0f} ₺" if bedel else "—",
                d.get("durum", ""),
            ]
            for col, val in enumerate(degerler):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 8:
                    if "Sonuç" in val:
                        item.setForeground(QColor("#aaaaaa"))
                    elif "İptal" in val:
                        item.setForeground(QColor("#ff4444"))
                    else:
                        item.setForeground(QColor("#00ff88"))
                self.tablo.setItem(row, col, item)
            self.tablo.setRowHeight(row, 24)

        demo_txt = " (⚠️ Demo Veri — EKAP bağlantısı yok)" if demo else ""
        self.sonuc_baslik.setText(f"Sonuçlar — {toplam} ihale{demo_txt}")
        self.durum_label.setText(f"✅ {len(ihaleler)} ihale listelendi" + (" [Demo Mod]" if demo else ""))

    def _arama_hata(self, hata: str):
        self.ara_btn.setEnabled(True)
        self.durum_label.setText(f"❌ Hata: {hata[:100]} — Demo veri yüklendi")
        self._demo_goster()

    def _secim_degisti(self):
        row = self.tablo.currentRow()
        aktif = row >= 0
        self.detay_btn.setEnabled(aktif)
        self.metraj_btn.setEnabled(aktif)
        self.kopyala_btn.setEnabled(aktif)
        if not aktif:
            return

        def col(i):
            item = self.tablo.item(row, i)
            return item.text() if item else ""

        ihale_no = col(0)
        ihale_adi = col(1)
        idare = col(2)
        il = col(3)
        tur = col(4)
        usul = col(5)
        tarih = col(6)
        bedel_str = col(7)
        durum = col(8)

        try:
            bedel = float(bedel_str.replace("₺", "").replace(",", "").strip())
        except Exception:
            bedel = 0.0

        detay = (
            f"{'═' * 40}\n"
            f"  İHALE DETAYI\n"
            f"{'═' * 40}\n\n"
            f"İhale No      : {ihale_no}\n"
            f"İhale Adı     : {ihale_adi}\n"
            f"İdare         : {idare}\n"
            f"İl            : {il}\n"
            f"Tür           : {tur}\n"
            f"Usul          : {usul}\n"
            f"İhale Tarihi  : {tarih}\n"
            f"Durum         : {durum}\n"
            f"\n{'─' * 40}\n"
            f"  MALİYET BİLGİLERİ\n"
            f"{'─' * 40}\n\n"
            f"Tahmini Bedel     : {bedel:>18,.2f} ₺\n"
            f"KDV (%20)         : {bedel * 0.20:>18,.2f} ₺\n"
            f"KDV Dahil Toplam  : {bedel * 1.20:>18,.2f} ₺\n"
            f"\n{'─' * 40}\n"
            f"  TEMİNAT HESAPLARI\n"
            f"{'─' * 40}\n\n"
            f"Geçici Teminat (%3) : {bedel * 0.03:>16,.2f} ₺\n"
            f"Kesin Teminat (%6)  : {bedel * 0.06:>16,.2f} ₺\n"
            f"\n{'─' * 40}\n"
            f"  YASAL NOTLAR (4734/4735)\n"
            f"{'─' * 40}\n\n"
            f"Gecikme Cezası    : Sözleşme × ‰5/gün (max %30)\n"
            f"Damga Vergisi     : %0.948\n"
            f"Gelir Vergisi     : %3 (stopaj)\n"
            f"KDV Oranı         : %20\n"
        )
        self.detay_alani.setPlainText(detay)

        if bedel > 0:
            self.lb_bedel.setText(f"{bedel:,.2f} ₺")
            self.lb_bedel.setStyleSheet("color: #00BFFF; font-weight: bold;")
            self.lb_kdv.setText(f"{bedel * 0.20:,.2f} ₺")
            self.lb_gecici.setText(f"{bedel * 0.03:,.2f} ₺")
            self.lb_gecici.setStyleSheet("color: #ffaa00; font-weight: bold;")
            self.lb_kesin.setText(f"{bedel * 0.06:,.2f} ₺")
            self.lb_kesin.setStyleSheet("color: #ff4444; font-weight: bold;")
        else:
            for lbl in [self.lb_bedel, self.lb_kdv, self.lb_gecici, self.lb_kesin]:
                lbl.setText("—")

    def _metraja_ekle(self):
        row = self.tablo.currentRow()
        if row < 0:
            return
        if not self.db:
            QMessageBox.information(
                self, "Bilgi",
                "Metraj'a eklemek için ana pencereden bir proje seçin."
            )
            return

        def col(i):
            item = self.tablo.item(row, i)
            return item.text() if item else ""

        ihale_adi = col(1)
        bedel_str = col(7)
        try:
            bedel = float(bedel_str.replace("₺", "").replace(",", "").strip())
        except Exception:
            bedel = 0.0

        try:
            parent_win = self.window()
            proje_id = getattr(parent_win, "current_project_id", None)
            if not proje_id:
                QMessageBox.warning(
                    self, "Proje Seçilmedi",
                    "Sol panelden önce bir proje seçin, ardından tekrar deneyin."
                )
                return
            self.db.add_metraj_kalem(
                proje_id=proje_id,
                tanim=f"[EKAP] {ihale_adi}",
                miktar=1,
                birim="adet",
                birim_fiyat=bedel,
                poz_no="",
                kategori="Kamu İhalesi",
            )
            QMessageBox.information(
                self, "Eklendi",
                f"'{ihale_adi}'\nMetraj cetveline eklendi."
            )
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Metraj'a eklenirken hata:\n{e}")

    def _secili_kopyala(self):
        row = self.tablo.currentRow()
        if row < 0:
            return
        parts = []
        for c in range(self.tablo.columnCount()):
            item = self.tablo.item(row, c)
            parts.append(item.text() if item else "")
        QApplication.clipboard().setText(" | ".join(parts))
        self.durum_label.setText("✅ Satır panoya kopyalandı.")
