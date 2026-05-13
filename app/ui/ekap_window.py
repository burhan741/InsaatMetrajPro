"""
EKAP — Elektronik Kamu Alımları Platformu Penceresi
Kamu İhale Kurumu ihaleleri arama, takip ve istatistik arayüzü

Sekmeler:
  0 — İhale Ara       : Anahtar kelime + filtre ile gerçek zamanlı arama
  1 — Son 10 Yıl      : 2015–2025 yıl bazlı ihale istatistikleri, bedel ve kazanan firma
"""
import csv
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QGroupBox, QFormLayout, QComboBox, QLineEdit,
    QSplitter, QTextEdit, QHeaderView, QMessageBox, QDateEdit,
    QDoubleSpinBox, QApplication, QCheckBox, QAbstractItemView,
    QTabWidget, QProgressBar, QSpinBox, QFileDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)

_STIL = """
    QWidget        { background-color: #1a1a2e; color: #e0e0e0; }
    QTabWidget::pane { border: 1px solid #0f3460; }
    QTabBar::tab   { background: #16213e; color: #aaa; padding: 7px 18px;
                     border: 1px solid #0f3460; border-bottom: none; border-radius: 4px 4px 0 0; }
    QTabBar::tab:selected { background: #0f3460; color: #00BFFF; font-weight: bold; }
    QGroupBox      { border: 1px solid #0f3460; border-radius: 6px; margin-top: 10px;
                     padding-top: 8px; color: #00BFFF; font-weight: bold; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
    QTableWidget   { background-color: #0d1117; color: #e0e0e0; gridline-color: #1e2a3a;
                     border: 1px solid #0f3460; alternate-background-color: #0f1923; }
    QHeaderView::section { background-color: #0f3460; color: #00BFFF;
                           padding: 6px; border: none; font-weight: bold; }
    QLineEdit      { background-color: #16213e; color: #e0e0e0;
                     border: 1px solid #0f3460; padding: 5px; border-radius: 4px; }
    QComboBox      { background-color: #16213e; color: #e0e0e0;
                     border: 1px solid #0f3460; padding: 5px; border-radius: 4px; }
    QDoubleSpinBox, QSpinBox { background-color: #16213e; color: #e0e0e0;
                               border: 1px solid #0f3460; padding: 4px; border-radius: 4px; }
    QDateEdit      { background-color: #16213e; color: #e0e0e0;
                     border: 1px solid #0f3460; padding: 4px; border-radius: 4px; }
    QPushButton    { background-color: #0f3460; color: white;
                     padding: 7px 14px; border-radius: 4px; border: none; }
    QPushButton:hover    { background-color: #1a5276; }
    QPushButton:disabled { background-color: #2c2c2c; color: #666; }
    QTextEdit      { background-color: #0d1117; color: #e0e0e0;
                     border: 1px solid #0f3460; border-radius: 4px; }
    QProgressBar   { background-color: #0d1117; border: 1px solid #0f3460; border-radius: 4px;
                     color: #e0e0e0; text-align: center; }
    QProgressBar::chunk { background-color: #00BFFF; border-radius: 3px; }
    QCheckBox      { color: #e0e0e0; }
"""


# ── Thread: Arama ────────────────────────────────────────────────────────────

class EKAPAramaThread(QThread):
    """Arka planda EKAP araması yapan thread."""
    sonuc_geldi  = pyqtSignal(dict)
    hata_olustu  = pyqtSignal(str)

    def __init__(self, engine, parametreler: dict):
        super().__init__()
        self.engine      = engine
        self.parametreler = parametreler

    def run(self):
        try:
            sonuc = self.engine.ihale_ara(**self.parametreler)
            if not sonuc["basarili"] or not sonuc["ihaleler"]:
                hata_msg = sonuc.get("hata") or "EKAP sonuç döndürmedi."
                self.hata_olustu.emit(hata_msg)
            else:
                self.sonuc_geldi.emit(sonuc)
        except Exception as e:
            self.hata_olustu.emit(str(e))


# ── Thread: İstatistik (yıl bazlı) ──────────────────────────────────────────

class EKAPIstatistikThread(QThread):
    """Son N yılın ihale verilerini yıl yıl çeken thread."""
    yil_tamamlandi = pyqtSignal(int, dict)   # yil, yil_sonucu
    hata_olustu    = pyqtSignal(str)
    bitti          = pyqtSignal()

    def __init__(self, engine, yil_baslangic: int, yil_bitis: int,
                 ihale_turu: str = "", il: str = ""):
        super().__init__()
        self.engine        = engine
        self.yil_baslangic = yil_baslangic
        self.yil_bitis     = yil_bitis
        self.ihale_turu    = ihale_turu
        self.il            = il
        self._iptal        = False

    def iptal_et(self):
        self._iptal = True

    def run(self):
        for yil in range(self.yil_baslangic, self.yil_bitis + 1):
            if self._iptal:
                break
            try:
                sonuc = self.engine.ihale_istatistik_yillik(
                    yil=yil,
                    ihale_turu=self.ihale_turu,
                    il=self.il,
                )
                self.yil_tamamlandi.emit(yil, sonuc)
            except Exception as e:
                logger.warning(f"İstatistik yıl {yil} hatası: {e}")
                self.yil_tamamlandi.emit(yil, {"basarili": False, "ihaleler": [], "hata": str(e)})
        self.bitti.emit()


# ── Ana Pencere ──────────────────────────────────────────────────────────────

class EKAPWindow(QWidget):
    """EKAP ihale arama, takip ve 10 yıllık istatistik penceresi."""

    ARAMA_SUTUNLARI = [
        "İhale No", "İhale Adı", "İdare", "İl",
        "Tür", "Usul", "İhale Tarihi", "Tahmini Bedel (₺)", "Durum",
    ]

    ISTAT_OZET_SUTUNLARI = [
        "Yıl", "İhale Sayısı", "Toplam Bedel (₺)",
        "Ortalama Bedel (₺)", "En Yüksek Bedel (₺)", "En Büyük İhale",
    ]

    ISTAT_DETAY_SUTUNLARI = [
        "Yıl", "İhale No", "İhale Adı", "İdare",
        "Tahmini Bedel (₺)", "Kazanan Firma", "Durum",
    ]

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db
        self._arama_thread:    Optional[EKAPAramaThread]     = None
        self._istat_thread:    Optional[EKAPIstatistikThread] = None
        # İstatistik verileri: {yil: [ihale_dict, ...]}
        self._istat_veri:      Dict[int, List[Dict]] = {}

        try:
            from app.core.ekap_engine import EKAPEngine
            self.engine      = EKAPEngine()
            self._engine_ok  = True
        except Exception as e:
            logger.error(f"EKAPEngine yüklenemedi: {e}")
            self._engine_ok  = False
            self.engine      = None

        self.setStyleSheet(_STIL)
        self._ui_olustur()

    # ── UI Oluşturma ─────────────────────────────────────────────────────────

    def _ui_olustur(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(10, 10, 10, 10)
        ana.setSpacing(6)

        # Başlık + bağlantı durumu
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
        ana.addLayout(ust)

        # Sekme widget
        self.tabs = QTabWidget()
        ana.addWidget(self.tabs)

        self.tabs.addTab(self._arama_sekmesi(), "🔍 İhale Ara")
        self.tabs.addTab(self._istatistik_sekmesi(), "📊 Son 10 Yıl İstatistikleri")

    # ── Sekme 0: Arama ───────────────────────────────────────────────────────

    def _arama_sekmesi(self) -> QWidget:
        widget = QWidget()
        lay    = QVBoxLayout(widget)
        lay.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Arama formu
        form_widget = QWidget()
        form_lay    = QVBoxLayout(form_widget)
        form_lay.setContentsMargins(0, 0, 0, 0)
        group = QGroupBox("🔍 İhale Arama ve Filtreleme")
        g_lay = QVBoxLayout(group)

        # Anahtar kelime + IKN arama
        s1 = QHBoxLayout()
        s1.addWidget(QLabel("Anahtar Kelime:"))
        self.kelime_input = QLineEdit()
        self.kelime_input.setPlaceholderText("'okul yapım', 'yol onarım', 'hastane inşaatı'...")
        self.kelime_input.returnPressed.connect(self._ara)
        s1.addWidget(self.kelime_input, 3)

        s1.addWidget(QLabel("  —  IKN Yılı:"))
        self.ikn_yil_input = QSpinBox()
        self.ikn_yil_input.setRange(0, datetime.now().year)
        self.ikn_yil_input.setValue(0)
        self.ikn_yil_input.setSpecialValueText("—")
        self.ikn_yil_input.setToolTip("İhale Kayıt Numarası yılı (0 = kullanma)")
        s1.addWidget(self.ikn_yil_input)

        s1.addWidget(QLabel("IKN Sayısı:"))
        self.ikn_sayi_input = QSpinBox()
        self.ikn_sayi_input.setRange(0, 9_999_999)
        self.ikn_sayi_input.setValue(0)
        self.ikn_sayi_input.setSpecialValueText("—")
        self.ikn_sayi_input.setToolTip("İhale Kayıt Numarası (IKN numarası)")
        s1.addWidget(self.ikn_sayi_input)
        g_lay.addLayout(s1)

        # İl + Tür + Durum
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
        self.tur_combo.addItem("Yapım İşi",      "1")
        self.tur_combo.addItem("Hizmet Alımı",   "2")
        self.tur_combo.addItem("Mal Alımı",       "3")
        self.tur_combo.addItem("Danışmanlık",     "4")
        s2.addWidget(self.tur_combo)

        s2.addWidget(QLabel("Durum:"))
        self.durum_combo = QComboBox()
        self.durum_combo.addItem("İhale İlanı (Aktif)", "2")
        self.durum_combo.addItem("Sonuçlandı",           "3")
        self.durum_combo.addItem("İptal Edildi",         "4")
        self.durum_combo.addItem("Tümü",                 "")
        s2.addWidget(self.durum_combo)
        g_lay.addLayout(s2)

        # Tarih + Bedel
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
        g_lay.addLayout(s3)

        # Butonlar
        s4 = QHBoxLayout()
        self.ara_btn = QPushButton("🔍 İhale Ara")
        self.ara_btn.setStyleSheet(
            "background-color:#00BFFF; color:#0d0d0d; font-weight:bold; padding:8px 20px;"
        )
        self.ara_btn.clicked.connect(self._ara)
        s4.addWidget(self.ara_btn)

        temizle_btn = QPushButton("🗑 Temizle")
        temizle_btn.clicked.connect(self._filtre_temizle)
        s4.addWidget(temizle_btn)
        s4.addStretch()

        self.durum_label = QLabel("Arama yapmak için formu doldurun.")
        self.durum_label.setStyleSheet("color:#aaaaaa; font-size:10px;")
        s4.addWidget(self.durum_label)
        g_lay.addLayout(s4)

        form_lay.addWidget(group)
        splitter.addWidget(form_widget)

        # Sonuç tablosu + Detay
        alt = QSplitter(Qt.Orientation.Horizontal)

        tablo_w = QWidget()
        tablo_l = QVBoxLayout(tablo_w)
        tablo_l.setContentsMargins(0, 0, 0, 0)
        self.sonuc_baslik = QLabel("Sonuçlar (0 ihale)")
        self.sonuc_baslik.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.sonuc_baslik.setStyleSheet("color:#00BFFF; margin-bottom:4px;")
        tablo_l.addWidget(self.sonuc_baslik)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(len(self.ARAMA_SUTUNLARI))
        self.tablo.setHorizontalHeaderLabels(self.ARAMA_SUTUNLARI)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tablo.setColumnWidth(0, 100)
        self.tablo.setColumnWidth(3,  90)
        self.tablo.setColumnWidth(4, 110)
        self.tablo.setColumnWidth(5, 120)
        self.tablo.setColumnWidth(6, 100)
        self.tablo.setColumnWidth(7, 140)
        self.tablo.setColumnWidth(8, 100)
        self.tablo.itemSelectionChanged.connect(self._secim_degisti)
        tablo_l.addWidget(self.tablo)

        aksiyon = QHBoxLayout()
        self.detay_btn   = QPushButton("📋 Detay")
        self.kopyala_btn = QPushButton("📋 Kopyala")
        self.excel_btn   = QPushButton("📤 Excel'e Aktar")
        self.detay_btn.setEnabled(False)
        self.kopyala_btn.setEnabled(False)
        self.excel_btn.setEnabled(False)
        self.excel_btn.setStyleSheet("background-color:#1a5276;")
        self.detay_btn.clicked.connect(lambda: self.detay_alani.setFocus())
        self.kopyala_btn.clicked.connect(self._secili_kopyala)
        self.excel_btn.clicked.connect(self._excele_aktar)
        aksiyon.addWidget(self.detay_btn)
        aksiyon.addWidget(self.kopyala_btn)
        aksiyon.addWidget(self.excel_btn)
        aksiyon.addStretch()
        tablo_l.addLayout(aksiyon)
        alt.addWidget(tablo_w)

        # Detay paneli
        detay_w = QWidget()
        detay_l = QVBoxLayout(detay_w)
        detay_l.setContentsMargins(4, 0, 0, 0)
        detay_baslik = QLabel("📄 İhale Detayı")
        detay_baslik.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        detay_baslik.setStyleSheet("color:#00BFFF;")
        detay_l.addWidget(detay_baslik)
        self.detay_alani = QTextEdit()
        self.detay_alani.setReadOnly(True)
        self.detay_alani.setFont(QFont("Consolas", 10))
        self.detay_alani.setPlaceholderText("Tablodaki bir ihaleye tıklayarak detayları görün.")
        detay_l.addWidget(self.detay_alani)

        teminat_group = QGroupBox("💰 Maliyet ve Teminat Hesabı")
        tf = QFormLayout(teminat_group)
        self.lb_bedel  = QLabel("—")
        self.lb_kdv    = QLabel("—")
        self.lb_gecici = QLabel("—")
        self.lb_kesin  = QLabel("—")
        tf.addRow("Tahmini Bedel:",       self.lb_bedel)
        tf.addRow("KDV (%20):",           self.lb_kdv)
        tf.addRow("Geçici Teminat (%3):", self.lb_gecici)
        tf.addRow("Kesin Teminat (%6):",  self.lb_kesin)
        detay_l.addWidget(teminat_group)
        alt.addWidget(detay_w)
        alt.setSizes([700, 320])

        splitter.addWidget(alt)
        splitter.setSizes([240, 520])
        lay.addWidget(splitter)
        return widget

    # ── Sekme 1: İstatistik ──────────────────────────────────────────────────

    def _istatistik_sekmesi(self) -> QWidget:
        widget = QWidget()
        lay    = QVBoxLayout(widget)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # Başlık
        baslik = QLabel("📊 Son 10 Yıl EKAP İhale İstatistikleri (2015 – 2025)")
        baslik.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        baslik.setStyleSheet("color:#00BFFF; margin-bottom:6px;")
        lay.addWidget(baslik)

        # Parametre satırı
        param_group = QGroupBox("⚙️ Filtreler ve Dönem Seçimi")
        param_lay   = QHBoxLayout(param_group)

        param_lay.addWidget(QLabel("Başlangıç Yılı:"))
        self.istat_yil_bas = QSpinBox()
        self.istat_yil_bas.setRange(2010, datetime.now().year)
        self.istat_yil_bas.setValue(datetime.now().year - 9)
        param_lay.addWidget(self.istat_yil_bas)

        param_lay.addWidget(QLabel("Bitiş Yılı:"))
        self.istat_yil_bit = QSpinBox()
        self.istat_yil_bit.setRange(2010, datetime.now().year)
        self.istat_yil_bit.setValue(datetime.now().year - 1)
        param_lay.addWidget(self.istat_yil_bit)

        param_lay.addWidget(QLabel("İhale Türü:"))
        self.istat_tur = QComboBox()
        self.istat_tur.addItem("Tümü",           "")
        self.istat_tur.addItem("Yapım İşi",      "1")
        self.istat_tur.addItem("Hizmet Alımı",   "2")
        self.istat_tur.addItem("Mal Alımı",       "3")
        self.istat_tur.addItem("Danışmanlık",     "4")
        param_lay.addWidget(self.istat_tur)

        param_lay.addWidget(QLabel("İl:"))
        self.istat_il = QComboBox()
        self.istat_il.addItem("Tüm İller", "")
        if self._engine_ok:
            for il in self.engine.il_listesi():
                self.istat_il.addItem(il, il)
        param_lay.addWidget(self.istat_il)

        param_lay.addStretch()

        self.istat_cek_btn = QPushButton("📥 İstatistik Çek")
        self.istat_cek_btn.setStyleSheet(
            "background-color:#00BFFF; color:#0d0d0d; font-weight:bold; padding:8px 18px;"
        )
        self.istat_cek_btn.clicked.connect(self._istatistik_cek)
        param_lay.addWidget(self.istat_cek_btn)

        self.istat_iptal_btn = QPushButton("⏹ İptal")
        self.istat_iptal_btn.setEnabled(False)
        self.istat_iptal_btn.clicked.connect(self._istatistik_iptal)
        param_lay.addWidget(self.istat_iptal_btn)
        lay.addWidget(param_group)

        # İlerleme çubuğu
        prog_lay = QHBoxLayout()
        self.istat_progress = QProgressBar()
        self.istat_progress.setValue(0)
        self.istat_progress.setVisible(False)
        self.istat_progress.setFixedHeight(18)
        prog_lay.addWidget(self.istat_progress)
        self.istat_durum = QLabel("")
        self.istat_durum.setStyleSheet("color:#aaaaaa; font-size:10px;")
        prog_lay.addWidget(self.istat_durum)
        lay.addLayout(prog_lay)

        # Alt splitter: Özet tablosu | Detay tablosu
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Özet tablosu (yıl bazlı)
        ozet_w = QWidget()
        ozet_l = QVBoxLayout(ozet_w)
        ozet_l.setContentsMargins(0, 0, 0, 0)
        ozet_baslik = QLabel("📋 Yıl Bazlı Özet")
        ozet_baslik.setStyleSheet("color:#00BFFF; font-weight:bold;")
        ozet_l.addWidget(ozet_baslik)

        self.istat_ozet_tablo = QTableWidget()
        self.istat_ozet_tablo.setColumnCount(len(self.ISTAT_OZET_SUTUNLARI))
        self.istat_ozet_tablo.setHorizontalHeaderLabels(self.ISTAT_OZET_SUTUNLARI)
        self.istat_ozet_tablo.setAlternatingRowColors(True)
        self.istat_ozet_tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.istat_ozet_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.istat_ozet_tablo.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        self.istat_ozet_tablo.setColumnWidth(0,  60)
        self.istat_ozet_tablo.setColumnWidth(1,  90)
        self.istat_ozet_tablo.setColumnWidth(2, 160)
        self.istat_ozet_tablo.setColumnWidth(3, 160)
        self.istat_ozet_tablo.setColumnWidth(4, 160)
        self.istat_ozet_tablo.itemSelectionChanged.connect(self._istat_ozet_secim)
        ozet_l.addWidget(self.istat_ozet_tablo)

        # Toplam satırı
        self.istat_toplam_label = QLabel("")
        self.istat_toplam_label.setStyleSheet(
            "color:#00ff88; font-size:11px; font-weight:bold; margin-top:4px;"
        )
        ozet_l.addWidget(self.istat_toplam_label)
        splitter.addWidget(ozet_w)

        # Detay tablosu (seçilen yılın ihaleleri)
        detay_w = QWidget()
        detay_l = QVBoxLayout(detay_w)
        detay_l.setContentsMargins(0, 0, 0, 0)
        self.istat_detay_baslik = QLabel("📄 Yıl Detayı — Tüm İhaleler")
        self.istat_detay_baslik.setStyleSheet("color:#00BFFF; font-weight:bold;")
        detay_l.addWidget(self.istat_detay_baslik)

        self.istat_detay_tablo = QTableWidget()
        self.istat_detay_tablo.setColumnCount(len(self.ISTAT_DETAY_SUTUNLARI))
        self.istat_detay_tablo.setHorizontalHeaderLabels(self.ISTAT_DETAY_SUTUNLARI)
        self.istat_detay_tablo.setAlternatingRowColors(True)
        self.istat_detay_tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.istat_detay_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.istat_detay_tablo.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.istat_detay_tablo.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.istat_detay_tablo.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        self.istat_detay_tablo.setColumnWidth(0,  50)
        self.istat_detay_tablo.setColumnWidth(1, 100)
        self.istat_detay_tablo.setColumnWidth(4, 140)
        self.istat_detay_tablo.setColumnWidth(6,  90)
        detay_l.addWidget(self.istat_detay_tablo)

        # Firmalar tablosu
        firma_lay = QHBoxLayout()
        firma_w   = QWidget()
        firma_l   = QVBoxLayout(firma_w)
        firma_l.setContentsMargins(0, 4, 0, 0)
        self.istat_firma_baslik = QLabel("🏢 İdarelere Göre Dağılım (Top 20)")
        self.istat_firma_baslik.setStyleSheet("color:#00BFFF; font-weight:bold;")
        firma_l.addWidget(self.istat_firma_baslik)
        self.istat_firma_tablo = QTableWidget()
        self.istat_firma_tablo.setColumnCount(4)
        self.istat_firma_tablo.setHorizontalHeaderLabels(
            ["İdare / Firma", "İhale Sayısı", "Toplam Bedel (₺)", "Ort. Bedel (₺)"]
        )
        self.istat_firma_tablo.setAlternatingRowColors(True)
        self.istat_firma_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.istat_firma_tablo.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.istat_firma_tablo.setColumnWidth(1, 100)
        self.istat_firma_tablo.setColumnWidth(2, 150)
        self.istat_firma_tablo.setColumnWidth(3, 130)
        firma_l.addWidget(self.istat_firma_tablo)
        firma_lay.addWidget(firma_w)
        detay_l.addLayout(firma_lay)
        splitter.addWidget(detay_w)

        splitter.setSizes([250, 450])
        lay.addWidget(splitter)
        return widget

    # ── Arama Slotları ────────────────────────────────────────────────────────

    def _baglanti_test(self):
        if not self._engine_ok:
            self.baglanti_label.setText("❌ Engine yüklenemedi")
            return
        self.baglanti_label.setText("⏳ Test ediliyor...")
        QApplication.processEvents()
        ok = self.engine.baglanabilirlik_test()
        if ok:
            self.baglanti_label.setText("✅ EKAP'a bağlı")
            self.baglanti_label.setStyleSheet("color:#00ff88; font-size:11px;")
        else:
            self.baglanti_label.setText("⚠️ EKAP erişilemiyor")
            self.baglanti_label.setStyleSheet("color:#ffaa00; font-size:11px;")

    def _ara(self):
        if not self._engine_ok:
            QMessageBox.warning(self, "Hata", "EKAP Engine yüklenemedi.")
            return
        self.ara_btn.setEnabled(False)
        self.durum_label.setText("⏳ Aranıyor...")
        self.tablo.setRowCount(0)

        ikn_yil  = self.ikn_yil_input.value()
        ikn_sayi = self.ikn_sayi_input.value()
        params: Dict[str, Any] = {
            "anahtar_kelime": self.kelime_input.text().strip(),
            "il":             self.il_combo.currentData() or "",
            "ihale_turu":     self.tur_combo.currentData() or "",
            "durum":          self.durum_combo.currentData() or "",
            "min_bedel":      self.min_bedel.value(),
            "max_bedel":      self.max_bedel.value(),
            "ikn_yili":       ikn_yil if ikn_yil > 0 else None,
            "ikn_sayi":       ikn_sayi if ikn_sayi > 0 else None,
        }
        if self.tarih_kullan_cb.isChecked():
            params["baslangic_tarihi"] = self.baslangic_tarih.date().toString("dd.MM.yyyy")
            params["bitis_tarihi"]     = self.bitis_tarih.date().toString("dd.MM.yyyy")

        thread = EKAPAramaThread(self.engine, params)
        self._arama_thread = thread
        thread.sonuc_geldi.connect(self._sonuc_goster)
        thread.hata_olustu.connect(self._arama_hata)
        thread.start()

    def _filtre_temizle(self):
        self.kelime_input.clear()
        self.il_combo.setCurrentIndex(0)
        self.tur_combo.setCurrentIndex(0)
        self.durum_combo.setCurrentIndex(0)
        self.min_bedel.setValue(0)
        self.max_bedel.setValue(0)
        self.ikn_yil_input.setValue(0)
        self.ikn_sayi_input.setValue(0)
        self.tarih_kullan_cb.setChecked(False)
        self.tablo.setRowCount(0)
        self.sonuc_baslik.setText("Sonuçlar (0 ihale)")
        self.durum_label.setText("Filtreler temizlendi.")

    def _sonuc_goster(self, sonuc: dict):
        self.ara_btn.setEnabled(True)
        ihaleler = sonuc.get("ihaleler", [])
        toplam   = sonuc.get("toplam", len(ihaleler))
        kaynak   = sonuc.get("_kaynak", "")

        self.tablo.setRowCount(0)
        self.tablo.setRowCount(len(ihaleler))

        for row, ihale in enumerate(ihaleler):
            d     = ihale.to_dict() if hasattr(ihale, "to_dict") else ihale
            bedel = d.get("tahmini_bedel", 0) or 0
            degerler = [
                d.get("ihale_no",    ""),
                d.get("ihale_adi",   ""),
                d.get("idare_adi",   ""),
                d.get("il",          ""),
                d.get("ihale_turu",  ""),
                d.get("ihale_usulu", ""),
                d.get("ihale_tarihi",""),
                f"{bedel:,.0f} ₺" if bedel else "—",
                d.get("durum",       ""),
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

        if kaynak == "api":
            self.baglanti_label.setText("🟢 Gerçek Veri (REST API)")
            self.baglanti_label.setStyleSheet("color:#00ff88; font-size:11px;")
        elif kaynak == "scraping":
            self.baglanti_label.setText("🟢 Gerçek Veri (Web Scraping)")
            self.baglanti_label.setStyleSheet("color:#00ff88; font-size:11px;")
        else:
            self.baglanti_label.setText("🔴 Gerçek Veri Alınamadı")
            self.baglanti_label.setStyleSheet("color:#ff4444; font-size:11px;")

        self.sonuc_baslik.setText(f"Sonuçlar — {toplam} ihale")
        self.durum_label.setText(
            f"✅ {len(ihaleler)} ihale listelendi"
            + (f" [{kaynak.upper()}]" if kaynak else "")
        )
        # Excel butonu: sonuç varsa aktif
        self.excel_btn.setEnabled(len(ihaleler) > 0)

    def _arama_hata(self, hata: str):
        self.ara_btn.setEnabled(True)
        self.tablo.setRowCount(0)
        self.baglanti_label.setText("🔴 EKAP bağlantısı yok")
        self.baglanti_label.setStyleSheet("color:#ff4444; font-size:11px;")
        self.sonuc_baslik.setText("Sonuçlar — Bağlantı Hatası")
        self.durum_label.setText("❌ EKAP'a bağlanılamadı.")
        QMessageBox.warning(
            self, "EKAP Bağlantı Hatası",
            "EKAP'a bağlanılamadı — gerçek ihale verisi alınamıyor.\n\n"
            f"Teknik detay: {hata[:200]}\n\n"
            "Gerçek ihaleler için: https://ekapv2.kik.gov.tr/ekap/search/ihale-arama adresini ziyaret edin."
        )

    def _secim_degisti(self):
        row   = self.tablo.currentRow()
        aktif = row >= 0
        self.detay_btn.setEnabled(aktif)
        self.kopyala_btn.setEnabled(aktif)
        if not aktif:
            return

        def col(i):
            item = self.tablo.item(row, i)
            return item.text() if item else ""

        ihale_no = col(0)
        ihale_adi = col(1)
        idare     = col(2)
        il        = col(3)
        tur       = col(4)
        usul      = col(5)
        tarih     = col(6)
        bedel_str = col(7)
        durum     = col(8)

        try:
            bedel = float(bedel_str.replace("₺", "").replace(",", "").strip())
        except Exception:
            bedel = 0.0

        detay = (
            f"{'═' * 40}\n  İHALE DETAYI\n{'═' * 40}\n\n"
            f"İhale No      : {ihale_no}\n"
            f"İhale Adı     : {ihale_adi}\n"
            f"İdare         : {idare}\n"
            f"İl            : {il}\n"
            f"Tür           : {tur}\n"
            f"Usul          : {usul}\n"
            f"İhale Tarihi  : {tarih}\n"
            f"Durum         : {durum}\n"
            f"\n{'─' * 40}\n  MALİYET BİLGİLERİ\n{'─' * 40}\n\n"
            f"Tahmini Bedel     : {bedel:>18,.2f} ₺\n"
            f"KDV (%20)         : {bedel * 0.20:>18,.2f} ₺\n"
            f"KDV Dahil Toplam  : {bedel * 1.20:>18,.2f} ₺\n"
            f"\n{'─' * 40}\n  TEMİNAT HESAPLARI\n{'─' * 40}\n\n"
            f"Geçici Teminat (%3) : {bedel * 0.03:>16,.2f} ₺\n"
            f"Kesin Teminat (%6)  : {bedel * 0.06:>16,.2f} ₺\n"
            f"\n{'─' * 40}\n  YASAL NOTLAR (4734/4735)\n{'─' * 40}\n\n"
            f"Gecikme Cezası    : Sözleşme × ‰5/gün (max %30)\n"
            f"Damga Vergisi     : %0.948\n"
            f"Gelir Vergisi     : %3 (stopaj)\n"
            f"KDV Oranı         : %20\n"
        )
        self.detay_alani.setPlainText(detay)

        if bedel > 0:
            self.lb_bedel.setText(f"{bedel:,.2f} ₺")
            self.lb_bedel.setStyleSheet("color:#00BFFF; font-weight:bold;")
            self.lb_kdv.setText(f"{bedel * 0.20:,.2f} ₺")
            self.lb_gecici.setText(f"{bedel * 0.03:,.2f} ₺")
            self.lb_gecici.setStyleSheet("color:#ffaa00; font-weight:bold;")
            self.lb_kesin.setText(f"{bedel * 0.06:,.2f} ₺")
            self.lb_kesin.setStyleSheet("color:#ff4444; font-weight:bold;")
        else:
            for lbl in [self.lb_bedel, self.lb_kdv, self.lb_gecici, self.lb_kesin]:
                lbl.setText("—")

    def _excele_aktar(self):
        """Mevcut sonuç listesini CSV/Excel formatında dışa aktar."""
        if self.tablo.rowCount() == 0:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak sonuç yok.")
            return
        dosya, _ = QFileDialog.getSaveFileName(
            self, "Excel / CSV Olarak Kaydet", "",
            "CSV Dosyası (*.csv);;Tüm Dosyalar (*)"
        )
        if not dosya:
            return
        if not dosya.lower().endswith(".csv"):
            dosya += ".csv"
        try:
            sutunlar = self.ARAMA_SUTUNLARI
            with open(dosya, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(sutunlar)
                for row in range(self.tablo.rowCount()):
                    satir = []
                    for col in range(self.tablo.columnCount()):
                        item = self.tablo.item(row, col)
                        satir.append(item.text() if item else "")
                    writer.writerow(satir)
            self.durum_label.setText(f"✅ {self.tablo.rowCount()} satır dışa aktarıldı.")
            QMessageBox.information(
                self, "Dışa Aktarıldı",
                f"{self.tablo.rowCount()} ihale kaydedildi:\n{dosya}\n\n"
                "Excel'de açmak için CSV Alma sihirbazını kullanın (UTF-8 kodlaması)."
            )
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Dışa aktarma hatası:\n{e}")

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

    # ── İstatistik Slotları ───────────────────────────────────────────────────

    def _istatistik_cek(self):
        if not self._engine_ok:
            QMessageBox.warning(self, "Hata", "EKAP Engine yüklenemedi.")
            return

        yil_bas = self.istat_yil_bas.value()
        yil_bit = self.istat_yil_bit.value()
        if yil_bas > yil_bit:
            QMessageBox.warning(self, "Hata", "Başlangıç yılı bitiş yılından büyük olamaz.")
            return

        self._istat_veri.clear()
        self.istat_ozet_tablo.setRowCount(0)
        self.istat_detay_tablo.setRowCount(0)
        self.istat_firma_tablo.setRowCount(0)
        self.istat_toplam_label.setText("")

        yil_sayisi = yil_bit - yil_bas + 1
        self.istat_progress.setMaximum(yil_sayisi)
        self.istat_progress.setValue(0)
        self.istat_progress.setVisible(True)
        self.istat_durum.setText(f"0 / {yil_sayisi} yıl işlendi…")

        self.istat_cek_btn.setEnabled(False)
        self.istat_iptal_btn.setEnabled(True)

        ihale_turu = self.istat_tur.currentData() or ""
        il         = self.istat_il.currentData() or ""

        self._istat_thread = EKAPIstatistikThread(
            self.engine, yil_bas, yil_bit, ihale_turu, il
        )
        self._istat_thread.yil_tamamlandi.connect(self._istat_yil_geldi)
        self._istat_thread.bitti.connect(self._istat_bitti)
        self._istat_thread.start()

    def _istatistik_iptal(self):
        if self._istat_thread and self._istat_thread.isRunning():
            self._istat_thread.iptal_et()
        self.istat_iptal_btn.setEnabled(False)
        self.istat_durum.setText("İptal edildi.")

    def _istat_yil_geldi(self, yil: int, sonuc: dict):
        ihaleler = sonuc.get("ihaleler", [])
        self._istat_veri[yil] = [
            (i.to_dict() if hasattr(i, "to_dict") else i) for i in ihaleler
        ]

        # İlerleme güncelle
        done = len(self._istat_veri)
        yil_bas = self.istat_yil_bas.value()
        yil_bit = self.istat_yil_bit.value()
        toplam  = yil_bit - yil_bas + 1
        self.istat_progress.setValue(done)
        self.istat_durum.setText(
            f"{done} / {toplam} yıl işlendi — {yil}: {len(ihaleler)} ihale"
        )

        # Özet tablosuna satır ekle
        bedeller  = [d.get("tahmini_bedel", 0) or 0 for d in self._istat_veri[yil]]
        sayisi    = len(bedeller)
        toplam_b  = sum(bedeller)
        ort_b     = toplam_b / sayisi if sayisi > 0 else 0
        max_b     = max(bedeller) if bedeller else 0
        max_ihale = ""
        if bedeller:
            idx = bedeller.index(max_b)
            max_ihale = self._istat_veri[yil][idx].get("ihale_adi", "")[:60]

        row = self.istat_ozet_tablo.rowCount()
        self.istat_ozet_tablo.insertRow(row)
        degerler = [
            str(yil),
            f"{sayisi:,}",
            f"{toplam_b:,.0f} ₺",
            f"{ort_b:,.0f} ₺",
            f"{max_b:,.0f} ₺",
            max_ihale,
        ]
        for col, val in enumerate(degerler):
            item = QTableWidgetItem(val)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == 0:
                item.setForeground(QColor("#00BFFF"))
                item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            elif col == 2:
                item.setForeground(QColor("#00ff88"))
            self.istat_ozet_tablo.setItem(row, col, item)
            self.istat_ozet_tablo.setRowHeight(row, 24)

    def _istat_bitti(self):
        self.istat_cek_btn.setEnabled(True)
        self.istat_iptal_btn.setEnabled(False)
        self.istat_progress.setVisible(False)

        # Genel toplam hesapla
        tum_ihaleler: List[Dict] = []
        for ihaleler in self._istat_veri.values():
            tum_ihaleler.extend(ihaleler)

        g_sayi  = len(tum_ihaleler)
        g_bedel = sum(d.get("tahmini_bedel", 0) or 0 for d in tum_ihaleler)
        self.istat_toplam_label.setText(
            f"GENEL TOPLAM — {g_sayi:,} ihale  |  {g_bedel:,.0f} ₺"
        )
        self.istat_durum.setText(
            f"✅ Tamamlandı — {g_sayi:,} ihale, toplam {g_bedel:,.0f} ₺"
        )

        # Firmalara göre tüm yılların birleşik toplamını hesapla
        self._istat_firma_goster(tum_ihaleler)

    def _istat_ozet_secim(self):
        """Özet tablosundan yıl seçilince detay tablosunu doldur."""
        row = self.istat_ozet_tablo.currentRow()
        if row < 0:
            return
        yil_item = self.istat_ozet_tablo.item(row, 0)
        if not yil_item:
            return
        try:
            yil = int(yil_item.text())
        except Exception:
            return

        ihaleler = self._istat_veri.get(yil, [])
        self.istat_detay_baslik.setText(
            f"📄 {yil} Yılı İhaleleri — {len(ihaleler)} kayıt"
        )
        self.istat_detay_tablo.setRowCount(0)
        self.istat_detay_tablo.setRowCount(len(ihaleler))

        for r, d in enumerate(ihaleler):
            bedel = d.get("tahmini_bedel", 0) or 0
            firma = d.get("kazanan_firma", "") or "—"
            degerler = [
                str(yil),
                d.get("ihale_no",    ""),
                d.get("ihale_adi",   ""),
                d.get("idare_adi",   ""),
                f"{bedel:,.0f} ₺" if bedel else "—",
                firma,
                d.get("durum",       ""),
            ]
            for col, val in enumerate(degerler):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 4 and bedel > 0:
                    item.setForeground(QColor("#00ff88"))
                if col == 5 and firma != "—":
                    item.setForeground(QColor("#FFD580"))
                self.istat_detay_tablo.setItem(r, col, item)
                self.istat_detay_tablo.setRowHeight(r, 22)

        # Seçilen yılın firmaları
        self._istat_firma_goster(ihaleler)

    def _istat_firma_goster(self, ihaleler: List[Dict]):
        """İdarelere göre ihale sayısı ve toplam bedel tablosunu doldur."""
        firma_dict: Dict[str, Dict] = {}
        for d in ihaleler:
            anahtar = d.get("idare_adi", "") or "Bilinmiyor"
            bedel   = d.get("tahmini_bedel", 0) or 0
            if anahtar not in firma_dict:
                firma_dict[anahtar] = {"sayi": 0, "toplam": 0.0}
            firma_dict[anahtar]["sayi"]   += 1
            firma_dict[anahtar]["toplam"] += bedel

        # Toplam bedele göre sırala, top 20 al
        sirali = sorted(
            firma_dict.items(),
            key=lambda x: x[1]["toplam"],
            reverse=True
        )[:20]

        self.istat_firma_tablo.setRowCount(0)
        self.istat_firma_tablo.setRowCount(len(sirali))

        for r, (ad, veri) in enumerate(sirali):
            sayi   = veri["sayi"]
            toplam = veri["toplam"]
            ort    = toplam / sayi if sayi > 0 else 0
            degerler = [
                ad,
                f"{sayi:,}",
                f"{toplam:,.0f} ₺",
                f"{ort:,.0f} ₺",
            ]
            for col, val in enumerate(degerler):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 2:
                    item.setForeground(QColor("#00ff88"))
                self.istat_firma_tablo.setItem(r, col, item)
                self.istat_firma_tablo.setRowHeight(r, 22)
