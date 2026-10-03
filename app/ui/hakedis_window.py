"""
Hakediş Penceresi — Kamu Yapım İşi Resmi Hakediş Belgesi
==========================================================
4734 / 4735 sayılı Kanunlar çerçevesinde:
  - Sözleşme bilgileri girişi
  - İmalat kalemleri ve brüt hakediş hesabı (CSBPozEngine entegrasyonu)
  - Kesinti cetveli (avans, kesin teminat, damga, GV stopaj, SGK, gecikme)
  - HTML önizlemeli resmi belge + PDF çıktısı

Kullanım:
    from app.ui.hakedis_window import HakedisWindow
    w = HakedisWindow()
    w.show()
"""
from __future__ import annotations

import logging
from decimal import Decimal
from datetime import date
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QLineEdit, QDoubleSpinBox, QSpinBox,
    QDateEdit, QCheckBox, QComboBox, QTextEdit, QSplitter,
    QGroupBox, QFrame, QScrollArea, QMessageBox, QFileDialog,
    QInputDialog, QAbstractItemView, QStatusBar,
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QFont, QColor, QBrush, QIntValidator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bağımlılıklar — hata toleranslı import
# ---------------------------------------------------------------------------

try:
    from app.core.hakedis_kesinti_engine import (
        HakedisKesintEngine, HakedisKesintiBilgisi, HakedisKesintleri,
        KESIN_TEMINAT_ORANI, DAMGA_VERGISI_ORANI,
        GELIR_VERGISI_STOPAJ, SGK_PRIM_KESINTI_ORANI, GUNLUK_GECIKME_ORANI,
    )
    _ENGINE_OK = True
except Exception as e:
    _ENGINE_OK = False
    logger.error(f"hakedis_kesinti_engine import hatası: {e}")

try:
    from app.core.csb_poz_engine import CSBPozEngine
    _CSB_OK = True
except Exception:
    _CSB_OK = False

# ---------------------------------------------------------------------------
# Renk şeması
# ---------------------------------------------------------------------------

DARK_BG    = "#1a1a2e"
CARD_BG    = "#16213e"
ACCENT     = "#00BFFF"
TEXT_WHITE = "#e0e0e0"
GREEN      = "#27ae60"
RED        = "#e74c3c"
ORANGE     = "#f39c12"
HEADER_BG  = "#0f3460"
INPUT_BG   = "#1e2a45"

_STYLE_BASE = f"""
    QMainWindow, QWidget {{
        background-color: {DARK_BG};
        color: {TEXT_WHITE};
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 13px;
    }}
    QTabWidget::pane {{
        border: 1px solid #2a4070;
        background: {CARD_BG};
    }}
    QTabBar::tab {{
        background: {DARK_BG};
        color: {TEXT_WHITE};
        padding: 8px 18px;
        border: 1px solid #2a4070;
        border-bottom: none;
        min-width: 160px;
    }}
    QTabBar::tab:selected {{
        background: {CARD_BG};
        color: {ACCENT};
        font-weight: bold;
    }}
    QGroupBox {{
        border: 1px solid #2a4070;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 8px;
        color: {ACCENT};
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
    }}
    QLineEdit, QDoubleSpinBox, QSpinBox, QDateEdit, QComboBox {{
        background: {INPUT_BG};
        border: 1px solid #2a4070;
        border-radius: 4px;
        color: {TEXT_WHITE};
        padding: 4px 8px;
        min-height: 26px;
    }}
    QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QDateEdit:focus {{
        border: 1px solid {ACCENT};
    }}
    QCheckBox {{
        color: {TEXT_WHITE};
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid #2a4070;
        background: {INPUT_BG};
        border-radius: 3px;
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
    QPushButton {{
        background-color: {ACCENT};
        color: #000;
        border: none;
        border-radius: 5px;
        padding: 7px 18px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: #33ccff;
    }}
    QPushButton:pressed {{
        background-color: #009acc;
    }}
    QPushButton#danger_btn {{
        background-color: {RED};
        color: #fff;
    }}
    QPushButton#danger_btn:hover {{
        background-color: #ff6b6b;
    }}
    QPushButton#success_btn {{
        background-color: {GREEN};
        color: #fff;
    }}
    QPushButton#success_btn:hover {{
        background-color: #2ecc71;
    }}
    QTableWidget {{
        background: {CARD_BG};
        color: {TEXT_WHITE};
        gridline-color: #2a4070;
        border: 1px solid #2a4070;
        selection-background-color: #1e4080;
    }}
    QTableWidget QHeaderView::section {{
        background: {HEADER_BG};
        color: {TEXT_WHITE};
        font-weight: bold;
        padding: 5px;
        border: none;
        border-right: 1px solid #2a4070;
    }}
    QTextEdit {{
        background: {CARD_BG};
        color: {TEXT_WHITE};
        border: 1px solid #2a4070;
        border-radius: 4px;
    }}
    QLabel#baslik {{
        font-size: 15px;
        font-weight: bold;
        color: {ACCENT};
        padding: 4px 0;
    }}
    QLabel#tutar {{
        font-size: 14px;
        font-weight: bold;
        color: {GREEN};
    }}
    QFrame#ayrac {{
        background: #2a4070;
        max-height: 1px;
    }}
    QScrollBar:vertical {{
        background: {DARK_BG};
        width: 10px;
    }}
    QScrollBar::handle:vertical {{
        background: #2a4070;
        border-radius: 4px;
    }}
"""


# ---------------------------------------------------------------------------
# CSBPozEngine stub — engine yokken çökmemek için
# ---------------------------------------------------------------------------

class _CSBStub:
    def metin_ara(self, _q):
        return []

    def tum_pozlar(self):
        return []

    def kategoriler(self):
        return []


# ---------------------------------------------------------------------------
# Ana pencere
# ---------------------------------------------------------------------------

class HakedisWindow(QMainWindow):
    """
    Kamu yapım işi hakediş yönetim penceresi.
    Araçlar menüsünden veya doğrudan çağrılabilir.
    """

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Hakediş Belgesi — Kamu Yapım İşi")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        # Engine
        self._engine = HakedisKesintEngine() if _ENGINE_OK else None
        self._poz_engine = CSBPozEngine() if _CSB_OK else _CSBStub()

        # Hesaplama sonucu
        self._son_sonuc: Optional[HakedisKesintleri] = None

        # İmalat kalemleri listesi
        self._imalat_kalemleri: List[dict] = []

        self._build_ui()
        self._apply_styles()
        self._refresh_poz_listesi()

    # ------------------------------------------------------------------
    # UI inşası
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(8)

        # Üst başlık
        baslik = QLabel("KAMU YAPIM İŞİ HAKEDİŞ BELGESİ")
        baslik.setObjectName("baslik")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(baslik)

        ayrac = QFrame()
        ayrac.setObjectName("ayrac")
        ayrac.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(ayrac)

        # Sekmeler
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        self._build_sozlesme_sekmesi()
        self._build_imalat_sekmesi()
        self._build_kesinti_sekmesi()
        self._build_belge_sekmesi()

        # Durum çubuğu
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Hazır — Sözleşme bilgilerini girin, ardından hesapla.")

    # ── Sekme 1: Sözleşme Bilgileri ──────────────────────────────────

    def _build_sozlesme_sekmesi(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        scroll.setWidget(w)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # ── Proje / Sözleşme grubu ──
        grp1 = QGroupBox("Proje ve Sözleşme")
        g1 = QGridLayout(grp1)
        g1.setColumnStretch(1, 1)
        g1.setColumnStretch(3, 1)

        satirlar = [
            ("Proje Adı", "proje_adi", "line"),
            ("İhale / Sözleşme No", "sozlesme_no", "line"),
            ("İdare Adı", "idare_adi", "line"),
            ("Müteahhit / Firma Adı", "firma_adi", "line"),
        ]
        for row, (etiket, key, _tip) in enumerate(satirlar):
            g1.addWidget(QLabel(etiket), row, 0)
            w2 = QLineEdit()
            w2.setPlaceholderText(etiket)
            setattr(self, f"_{key}_input", w2)
            g1.addWidget(w2, row, 1, 1, 3)

        layout.addWidget(grp1)

        # ── Finansal bilgiler grubu ──
        grp2 = QGroupBox("Finansal Bilgiler")
        g2 = QGridLayout(grp2)
        g2.setColumnStretch(1, 1)
        g2.setColumnStretch(3, 1)

        # Sözleşme Bedeli
        g2.addWidget(QLabel("Sözleşme Bedeli (TL)"), 0, 0)
        self._sozlesme_bedeli_input = QDoubleSpinBox()
        self._sozlesme_bedeli_input.setRange(0, 999_999_999_999)
        self._sozlesme_bedeli_input.setDecimals(2)
        self._sozlesme_bedeli_input.setGroupSeparatorShown(True)
        self._sozlesme_bedeli_input.setSuffix(" TL")
        g2.addWidget(self._sozlesme_bedeli_input, 0, 1)

        # Sözleşme Tarihi
        g2.addWidget(QLabel("Sözleşme Tarihi"), 0, 2)
        self._sozlesme_tarihi_input = QDateEdit(QDate.currentDate())
        self._sozlesme_tarihi_input.setCalendarPopup(True)
        self._sozlesme_tarihi_input.setDisplayFormat("dd.MM.yyyy")
        g2.addWidget(self._sozlesme_tarihi_input, 0, 3)

        # Verilen Avans
        g2.addWidget(QLabel("Verilen Avans (TL)"), 1, 0)
        self._verilen_avans_input = QDoubleSpinBox()
        self._verilen_avans_input.setRange(0, 999_999_999_999)
        self._verilen_avans_input.setDecimals(2)
        self._verilen_avans_input.setGroupSeparatorShown(True)
        self._verilen_avans_input.setSuffix(" TL")
        g2.addWidget(self._verilen_avans_input, 1, 1)

        # Avans Oranı
        g2.addWidget(QLabel("Avans Oranı (%)"), 1, 2)
        self._avans_orani_input = QDoubleSpinBox()
        self._avans_orani_input.setRange(0, 100)
        self._avans_orani_input.setDecimals(1)
        self._avans_orani_input.setValue(30.0)
        self._avans_orani_input.setSuffix(" %")
        g2.addWidget(self._avans_orani_input, 1, 3)

        # Önceki Avans Mahsubu
        g2.addWidget(QLabel("Önceki Avans Mahsubu (TL)"), 2, 0)
        self._onceki_avans_mahsubu_input = QDoubleSpinBox()
        self._onceki_avans_mahsubu_input.setRange(0, 999_999_999_999)
        self._onceki_avans_mahsubu_input.setDecimals(2)
        self._onceki_avans_mahsubu_input.setGroupSeparatorShown(True)
        self._onceki_avans_mahsubu_input.setSuffix(" TL")
        g2.addWidget(self._onceki_avans_mahsubu_input, 2, 1)

        # KDV Oranı
        g2.addWidget(QLabel("KDV Oranı (%)"), 2, 2)
        self._kdv_orani_input = QDoubleSpinBox()
        self._kdv_orani_input.setRange(0, 50)
        self._kdv_orani_input.setDecimals(1)
        self._kdv_orani_input.setValue(20.0)
        self._kdv_orani_input.setSuffix(" %")
        g2.addWidget(self._kdv_orani_input, 2, 3)

        layout.addWidget(grp2)

        # ── Hakediş bilgileri grubu ──
        grp3 = QGroupBox("Hakediş Bilgileri")
        g3 = QGridLayout(grp3)
        g3.setColumnStretch(1, 1)
        g3.setColumnStretch(3, 1)

        # Hakediş No
        g3.addWidget(QLabel("Hakediş No"), 0, 0)
        self._hakedis_no_input = QSpinBox()
        self._hakedis_no_input.setRange(1, 999)
        self._hakedis_no_input.setValue(1)
        g3.addWidget(self._hakedis_no_input, 0, 1)

        # Hakediş Tarihi
        g3.addWidget(QLabel("Hakediş Tarihi"), 0, 2)
        self._hakedis_tarihi_input = QDateEdit(QDate.currentDate())
        self._hakedis_tarihi_input.setCalendarPopup(True)
        self._hakedis_tarihi_input.setDisplayFormat("dd.MM.yyyy")
        g3.addWidget(self._hakedis_tarihi_input, 0, 3)

        # Hakediş Dönemi
        g3.addWidget(QLabel("Hakediş Dönemi (Ay-Yıl)"), 1, 0)
        self._hakedis_donemi_input = QLineEdit()
        self._hakedis_donemi_input.setPlaceholderText("örn: Nisan 2026")
        g3.addWidget(self._hakedis_donemi_input, 1, 1)

        # Gecikme Günü
        g3.addWidget(QLabel("Gecikme Günü"), 1, 2)
        self._gecikme_gun_input = QSpinBox()
        self._gecikme_gun_input.setRange(0, 999)
        self._gecikme_gun_input.setValue(0)
        self._gecikme_gun_input.setSuffix(" gün")
        g3.addWidget(self._gecikme_gun_input, 1, 3)

        layout.addWidget(grp3)

        # ── Aktif/Pasif seçenekler ──
        grp4 = QGroupBox("Kesinti Seçenekleri")
        g4 = QHBoxLayout(grp4)

        self._kt_tamamlandi_chk = QCheckBox("Kesin Teminat Tamamlandı")
        self._kt_tamamlandi_chk.setToolTip(
            "İşaretlenirse bu dönemde kesin teminat kesilmez."
        )
        g4.addWidget(self._kt_tamamlandi_chk)

        self._gv_stopaj_chk = QCheckBox("GV Stopaj Aktif")
        self._gv_stopaj_chk.setChecked(True)
        self._gv_stopaj_chk.setToolTip(
            "Gelir vergisi stopajı — %3 (GVK Geçici md.67)."
        )
        g4.addWidget(self._gv_stopaj_chk)

        self._sgk_chk = QCheckBox("SGK Kesinti Aktif")
        self._sgk_chk.setChecked(True)
        self._sgk_chk.setToolTip(
            "SGK asgari işçilik fark primi — %1 (5510 md.85)."
        )
        g4.addWidget(self._sgk_chk)

        g4.addStretch()
        layout.addWidget(grp4)
        layout.addStretch()

        self._tabs.addTab(scroll, "Sözleşme Bilgileri")

    # ── Sekme 2: İmalat Kalemleri ────────────────────────────────────

    def _build_imalat_sekmesi(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sol: Poz arama
        sol = QWidget()
        sol_layout = QVBoxLayout(sol)
        sol_layout.setContentsMargins(0, 0, 6, 0)
        sol_layout.setSpacing(6)

        poz_baslik = QLabel("CŞB Poz Arama")
        poz_baslik.setObjectName("baslik")
        sol_layout.addWidget(poz_baslik)

        self._poz_arama_input = QLineEdit()
        self._poz_arama_input.setPlaceholderText("Poz kodu veya tanım ara...")
        self._poz_arama_input.textChanged.connect(self._on_poz_arama)
        sol_layout.addWidget(self._poz_arama_input)

        self._poz_listesi = QTableWidget(0, 4)
        self._poz_listesi.setHorizontalHeaderLabels(
            ["Poz No", "Tanım", "Birim", "B.Fiyat (TL)"]
        )
        self._poz_listesi.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._poz_listesi.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._poz_listesi.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._poz_listesi.doubleClicked.connect(self._on_poz_ekle_poz_secim)
        sol_layout.addWidget(self._poz_listesi)

        btn_poz_ekle = QPushButton("Secili Pozu Ekle →")
        btn_poz_ekle.clicked.connect(self._on_poz_ekle_poz_secim)
        sol_layout.addWidget(btn_poz_ekle)

        splitter.addWidget(sol)

        # Sağ: İmalat tablosu
        sag = QWidget()
        sag_layout = QVBoxLayout(sag)
        sag_layout.setContentsMargins(6, 0, 0, 0)
        sag_layout.setSpacing(6)

        im_baslik = QLabel("İmalat Kalemleri")
        im_baslik.setObjectName("baslik")
        sag_layout.addWidget(im_baslik)

        self._imalat_tablo = QTableWidget(0, 8)
        self._imalat_tablo.setHorizontalHeaderLabels([
            "Sıra", "Poz No", "Tanım", "Birim",
            "Sözl. Miktar", "Gerç. Miktar", "B.Fiyat (TL)", "Tutar (TL)",
        ])
        self._imalat_tablo.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._imalat_tablo.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._imalat_tablo.itemChanged.connect(self._on_imalat_item_changed)
        sag_layout.addWidget(self._imalat_tablo)

        # Alt butonlar ve toplam
        alt_bar = QHBoxLayout()
        btn_sil = QPushButton("Secili Kalemi Sil")
        btn_sil.setObjectName("danger_btn")
        btn_sil.clicked.connect(self._on_imalat_sil)
        alt_bar.addWidget(btn_sil)

        btn_temizle = QPushButton("Tümünü Temizle")
        btn_temizle.setObjectName("danger_btn")
        btn_temizle.clicked.connect(self._on_imalat_temizle)
        alt_bar.addWidget(btn_temizle)

        alt_bar.addStretch()

        self._brut_hakedis_label = QLabel("Brüt Hakediş: 0,00 TL")
        self._brut_hakedis_label.setObjectName("tutar")
        alt_bar.addWidget(self._brut_hakedis_label)

        sag_layout.addLayout(alt_bar)

        splitter.addWidget(sag)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)
        self._tabs.addTab(w, "İmalat Kalemleri")

    # ── Sekme 3: Kesinti Hesabı ───────────────────────────────────────

    def _build_kesinti_sekmesi(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Hesapla butonu
        btn_hesapla = QPushButton("Kesintileri Hesapla")
        btn_hesapla.setObjectName("success_btn")
        btn_hesapla.setMinimumHeight(38)
        btn_hesapla.clicked.connect(self._on_hesapla)
        layout.addWidget(btn_hesapla)

        # Sonuç tablosu
        self._kesinti_tablo = QTableWidget(0, 3)
        self._kesinti_tablo.setHorizontalHeaderLabels(
            ["Kesinti Kalemi", "Oran / Gün", "Tutar (TL)"]
        )
        self._kesinti_tablo.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._kesinti_tablo.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._kesinti_tablo.verticalHeader().setVisible(False)
        layout.addWidget(self._kesinti_tablo)

        # Uyarı alanı
        self._uyari_label = QLabel("")
        self._uyari_label.setWordWrap(True)
        self._uyari_label.setStyleSheet(
            "background: #7d6608; color: #fff; border-radius: 5px;"
            "padding: 8px; font-size: 12px;"
        )
        self._uyari_label.hide()
        layout.addWidget(self._uyari_label)

        layout.addStretch()
        self._tabs.addTab(w, "Kesinti Hesabı")

    # ── Sekme 4: Hakediş Belgesi ─────────────────────────────────────

    def _build_belge_sekmesi(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Üst butonlar
        ust = QHBoxLayout()
        btn_onizle = QPushButton("Belgeyi Oluştur / Yenile")
        btn_onizle.clicked.connect(self._on_belge_olustur)
        ust.addWidget(btn_onizle)

        btn_pdf = QPushButton("PDF Çıktı Al")
        btn_pdf.setObjectName("success_btn")
        btn_pdf.clicked.connect(self._on_pdf_al)
        ust.addWidget(btn_pdf)

        ust.addStretch()
        layout.addLayout(ust)

        self._belge_view = QTextEdit()
        self._belge_view.setReadOnly(True)
        self._belge_view.setPlaceholderText(
            "Önce kesinti hesabı yapın, ardından 'Belgeyi Oluştur' butonuna tıklayın."
        )
        layout.addWidget(self._belge_view)

        self._tabs.addTab(w, "Hakediş Belgesi")

    # ------------------------------------------------------------------
    # Stil uygulama
    # ------------------------------------------------------------------

    def _apply_styles(self):
        self.setStyleSheet(_STYLE_BASE)

    # ------------------------------------------------------------------
    # Poz listesi
    # ------------------------------------------------------------------

    def _refresh_poz_listesi(self, arama: str = ""):
        try:
            if arama:
                pozlar = self._poz_engine.metin_ara(arama)
            else:
                pozlar = self._poz_engine.tum_pozlar()
        except Exception as exc:
            logger.error("Poz listesi yüklenemedi: %s", exc)
            pozlar = []

        self._poz_listesi.blockSignals(True)
        self._poz_listesi.setRowCount(0)
        for poz in pozlar:
            row = self._poz_listesi.rowCount()
            self._poz_listesi.insertRow(row)
            # poz: (poz_kodu, aciklama, birim, birim_fiyat, kategori, ...)
            degerler = [
                str(poz[0]),
                str(poz[1]),
                str(poz[2]),
                f"{poz[3]:,.2f}",
            ]
            for col, val in enumerate(degerler):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self._poz_listesi.setItem(row, col, item)
        self._poz_listesi.blockSignals(False)

    def _on_poz_arama(self, metin: str):
        self._refresh_poz_listesi(metin.strip())

    # ------------------------------------------------------------------
    # İmalat kalemleri
    # ------------------------------------------------------------------

    def _on_poz_ekle_poz_secim(self):
        secili = self._poz_listesi.selectedItems()
        if not secili:
            QMessageBox.information(self, "Seçim Yok", "Lütfen listeden bir poz seçin.")
            return

        row = self._poz_listesi.currentRow()
        poz_kodu_item = self._poz_listesi.item(row, 0)
        aciklama_item = self._poz_listesi.item(row, 1)
        birim_item    = self._poz_listesi.item(row, 2)
        fiyat_item    = self._poz_listesi.item(row, 3)

        if not poz_kodu_item:
            return

        poz_kodu = poz_kodu_item.text()
        aciklama = aciklama_item.text() if aciklama_item else ""
        birim    = birim_item.text() if birim_item else ""
        fiyat_str = fiyat_item.text().replace(",", "") if fiyat_item else "0"
        try:
            birim_fiyat = float(fiyat_str)
        except ValueError:
            birim_fiyat = 0.0

        # Miktar sor
        miktar, ok = QInputDialog.getDouble(
            self,
            "Miktar Girin",
            f"{aciklama}\n\nGerçekleşen Miktar ({birim}):",
            value=1.0,
            min=0.0,
            max=9_999_999,
            decimals=3,
        )
        if not ok:
            return

        sozlesme_miktar, ok2 = QInputDialog.getDouble(
            self,
            "Sözleşme Miktarı",
            f"Sözleşmedeki Miktar ({birim}):",
            value=miktar,
            min=0.0,
            max=9_999_999,
            decimals=3,
        )
        if not ok2:
            sozlesme_miktar = miktar

        kalem = {
            "poz_kodu": poz_kodu,
            "aciklama": aciklama,
            "birim": birim,
            "sozlesme_miktar": sozlesme_miktar,
            "gerceklesen_miktar": miktar,
            "birim_fiyat": birim_fiyat,
            "tutar": miktar * birim_fiyat,
        }
        self._imalat_kalemleri.append(kalem)
        self._refresh_imalat_tablo()

    def _refresh_imalat_tablo(self):
        self._imalat_tablo.blockSignals(True)
        self._imalat_tablo.setRowCount(0)

        brut_toplam = 0.0
        for idx, kalem in enumerate(self._imalat_kalemleri):
            row = self._imalat_tablo.rowCount()
            self._imalat_tablo.insertRow(row)
            tutar = kalem.get("tutar", 0.0)
            brut_toplam += tutar

            degerler = [
                str(idx + 1),
                kalem.get("poz_kodu", ""),
                kalem.get("aciklama", ""),
                kalem.get("birim", ""),
                f"{kalem.get('sozlesme_miktar', 0):.3f}",
                f"{kalem.get('gerceklesen_miktar', 0):.3f}",
                f"{kalem.get('birim_fiyat', 0):,.2f}",
                f"{tutar:,.2f}",
            ]
            for col, val in enumerate(degerler):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if col in (4, 5, 6, 7):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
                    )
                self._imalat_tablo.setItem(row, col, item)

        self._imalat_tablo.blockSignals(False)
        self._brut_hakedis_label.setText(f"Brüt Hakediş: {brut_toplam:,.2f} TL")

    def _on_imalat_item_changed(self, item):
        # Gerçekleşen miktar veya birim fiyat değişirse tutarı güncelle
        row = item.row()
        col = item.column()
        if col not in (5, 6):
            return
        if row >= len(self._imalat_kalemleri):
            return

        self._imalat_tablo.blockSignals(True)
        try:
            miktar = float(
                self._imalat_tablo.item(row, 5).text().replace(",", "")
            )
            fiyat = float(
                self._imalat_tablo.item(row, 6).text().replace(",", "")
            )
            tutar = miktar * fiyat
            self._imalat_kalemleri[row]["gerceklesen_miktar"] = miktar
            self._imalat_kalemleri[row]["birim_fiyat"] = fiyat
            self._imalat_kalemleri[row]["tutar"] = tutar
            tutar_item = QTableWidgetItem(f"{tutar:,.2f}")
            tutar_item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
            )
            self._imalat_tablo.setItem(row, 7, tutar_item)
        except Exception:
            pass
        finally:
            self._imalat_tablo.blockSignals(False)

        # Brüt hakedişi güncelle
        brut = sum(k.get("tutar", 0) for k in self._imalat_kalemleri)
        self._brut_hakedis_label.setText(f"Brüt Hakediş: {brut:,.2f} TL")

    def _on_imalat_sil(self):
        row = self._imalat_tablo.currentRow()
        if row < 0 or row >= len(self._imalat_kalemleri):
            return
        self._imalat_kalemleri.pop(row)
        self._refresh_imalat_tablo()

    def _on_imalat_temizle(self):
        cevap = QMessageBox.question(
            self,
            "Tümünü Temizle",
            "Tüm imalat kalemleri silinecek. Devam edilsin mi?",
        )
        if cevap == QMessageBox.StandardButton.Yes:
            self._imalat_kalemleri.clear()
            self._refresh_imalat_tablo()

    # ------------------------------------------------------------------
    # Kesinti hesabı
    # ------------------------------------------------------------------

    def _on_hesapla(self):
        if not _ENGINE_OK or self._engine is None:
            QMessageBox.critical(
                self,
                "Engine Hatası",
                "Hakediş kesinti motoru yüklenemedi. Uygulama loglarını kontrol edin.",
            )
            return

        # Brüt hakedişi imalat tablosundan al
        brut = Decimal(str(
            sum(k.get("tutar", 0.0) for k in self._imalat_kalemleri)
        ))

        # Sözleşme bilgileri
        qd = self._hakedis_tarihi_input.date()
        hakedis_tar = date(qd.year(), qd.month(), qd.day())

        bilgi = HakedisKesintiBilgisi(
            sozlesme_bedeli=Decimal(str(self._sozlesme_bedeli_input.value())),
            hakedis_no=self._hakedis_no_input.value(),
            hakedis_tarihi=hakedis_tar,
            brut_hakedis=brut,
            avans_orani=Decimal(str(self._avans_orani_input.value() / 100)),
            verilen_avans=Decimal(str(self._verilen_avans_input.value())),
            onceki_avans_mahsubu=Decimal(str(self._onceki_avans_mahsubu_input.value())),
            kesin_teminat_tamamlandi=self._kt_tamamlandi_chk.isChecked(),
            gecikme_gun=self._gecikme_gun_input.value(),
            sgk_kesinti_aktif=self._sgk_chk.isChecked(),
            gv_stopaj_aktif=self._gv_stopaj_chk.isChecked(),
        )

        try:
            sonuc = self._engine.hesapla(bilgi)
            self._son_sonuc = sonuc
            self._son_bilgi = bilgi
            self._doldur_kesinti_tablo(bilgi, sonuc)
            self._status.showMessage(
                f"Hesaplama tamamlandi — Net Odeme: {float(sonuc.net_odeme):,.2f} TL"
            )
        except Exception as exc:
            logger.error("Hesaplama hatası: %s", exc)
            QMessageBox.critical(self, "Hesaplama Hatası", str(exc))

    def _doldur_kesinti_tablo(
        self, bilgi: HakedisKesintiBilgisi, sonuc: HakedisKesintleri
    ):
        satirlar = [
            ("Brüt Hakediş Tutarı", "—", float(sonuc.brut_hakedis), False),
            (
                "(–) Avans Mahsubu",
                f"%{float(bilgi.avans_orani * 100):.0f}",
                -float(sonuc.avans_mahsubu),
                True,
            ),
            ("(–) Kesin Teminat Kesintisi", "%6", -float(sonuc.kesin_teminat), True),
            ("(–) Damga Vergisi", "%0.948", -float(sonuc.damga_vergisi), True),
            ("(–) Gelir Vergisi Stopajı", "%3", -float(sonuc.gelir_vergisi), True),
            ("(–) SGK Prim Kesintisi", "%1", -float(sonuc.sgk_prim), True),
            (
                f"(–) Gecikme Cezası",
                f"{bilgi.gecikme_gun} gün × ‰5",
                -float(sonuc.gecikme_cezasi),
                True,
            ),
            ("TOPLAM KESİNTİ", "—", -float(sonuc.toplam_kesinti), True),
            ("NET ÖDEME", "—", float(sonuc.net_odeme), False),
        ]

        self._kesinti_tablo.blockSignals(True)
        self._kesinti_tablo.setRowCount(0)

        for kalem, oran, tutar, kesinti_mi in satirlar:
            row = self._kesinti_tablo.rowCount()
            self._kesinti_tablo.insertRow(row)

            item_kalem = QTableWidgetItem(kalem)
            item_oran  = QTableWidgetItem(oran)
            tutar_str  = f"{tutar:,.2f} TL"
            item_tutar = QTableWidgetItem(tutar_str)
            item_tutar.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
            )

            # Renklendirme
            if kalem == "NET ÖDEME":
                renk = QColor(GREEN) if tutar >= 0 else QColor(RED)
                for it in (item_kalem, item_oran, item_tutar):
                    it.setBackground(QBrush(renk))
                    it.setForeground(QBrush(QColor("#fff")))
                font = item_kalem.font()
                font.setBold(True)
                font.setPointSize(11)
                for it in (item_kalem, item_oran, item_tutar):
                    it.setFont(font)
            elif kalem == "TOPLAM KESİNTİ":
                for it in (item_kalem, item_oran, item_tutar):
                    it.setBackground(QBrush(QColor(RED)))
                    it.setForeground(QBrush(QColor("#fff")))
                font = item_kalem.font()
                font.setBold(True)
                for it in (item_kalem, item_oran, item_tutar):
                    it.setFont(font)
            elif kesinti_mi and tutar < 0:
                for it in (item_kalem, item_oran, item_tutar):
                    it.setForeground(QBrush(QColor("#ffaaaa")))

            self._kesinti_tablo.setItem(row, 0, item_kalem)
            self._kesinti_tablo.setItem(row, 1, item_oran)
            self._kesinti_tablo.setItem(row, 2, item_tutar)

        self._kesinti_tablo.resizeRowsToContents()
        self._kesinti_tablo.blockSignals(False)

        # Uyarılar
        if sonuc.uyarilar:
            uyari_metni = "\n".join(f"• {u}" for u in sonuc.uyarilar)
            self._uyari_label.setText(uyari_metni)
            self._uyari_label.show()
        else:
            self._uyari_label.hide()

    # ------------------------------------------------------------------
    # Belge önizleme
    # ------------------------------------------------------------------

    def _on_belge_olustur(self):
        if self._son_sonuc is None:
            QMessageBox.information(
                self,
                "Önce Hesaplayın",
                "Belge oluşturmak için önce 'Kesinti Hesabı' sekmesinde hesaplama yapın.",
            )
            return
        html = self._uret_html_belge(self._son_bilgi, self._son_sonuc)
        self._belge_view.setHtml(html)
        self._tabs.setCurrentIndex(3)

    def _uret_html_belge(
        self, bilgi: HakedisKesintiBilgisi, sonuc: HakedisKesintleri
    ) -> str:
        proje_adi   = getattr(self, "_proje_adi_input", None)
        proje_adi   = self._proje_adi_input.text() if hasattr(self, "_proje_adi_input") else ""
        sozlesme_no = self._sozlesme_no_input.text() if hasattr(self, "_sozlesme_no_input") else ""
        idare_adi   = self._idare_adi_input.text() if hasattr(self, "_idare_adi_input") else ""
        firma_adi   = self._firma_adi_input.text() if hasattr(self, "_firma_adi_input") else ""
        donemi      = self._hakedis_donemi_input.text()

        tarih_str = bilgi.hakedis_tarihi.strftime("%d/%m/%Y") if bilgi.hakedis_tarihi else "—"

        # İmalat tablosu HTML
        imalat_satirlari_html = ""
        for idx, kalem in enumerate(self._imalat_kalemleri):
            imalat_satirlari_html += f"""
            <tr>
                <td>{idx + 1}</td>
                <td>{kalem.get('poz_kodu', '')}</td>
                <td>{kalem.get('aciklama', '')}</td>
                <td>{kalem.get('birim', '')}</td>
                <td style="text-align:right">{kalem.get('sozlesme_miktar', 0):.3f}</td>
                <td style="text-align:right">{kalem.get('gerceklesen_miktar', 0):.3f}</td>
                <td style="text-align:right">{kalem.get('birim_fiyat', 0):,.2f}</td>
                <td style="text-align:right">{kalem.get('tutar', 0):,.2f}</td>
            </tr>"""

        # Kesinti satırları HTML
        kesinti_satirlari_html = f"""
            <tr><td>Brüt Hakediş Tutarı</td><td>—</td>
                <td style="text-align:right">{float(sonuc.brut_hakedis):,.2f}</td></tr>
            <tr><td>(–) Avans Mahsubu</td>
                <td>%{float(bilgi.avans_orani * 100):.0f}</td>
                <td style="text-align:right">-{float(sonuc.avans_mahsubu):,.2f}</td></tr>
            <tr><td>(–) Kesin Teminat Kesintisi</td><td>%6</td>
                <td style="text-align:right">-{float(sonuc.kesin_teminat):,.2f}</td></tr>
            <tr><td>(–) Damga Vergisi</td><td>%0.948</td>
                <td style="text-align:right">-{float(sonuc.damga_vergisi):,.2f}</td></tr>
            <tr><td>(–) Gelir Vergisi Stopajı</td><td>%3</td>
                <td style="text-align:right">-{float(sonuc.gelir_vergisi):,.2f}</td></tr>
            <tr><td>(–) SGK Prim Kesintisi</td><td>%1</td>
                <td style="text-align:right">-{float(sonuc.sgk_prim):,.2f}</td></tr>
            <tr><td>(–) Gecikme Cezası</td>
                <td>{bilgi.gecikme_gun} gün × ‰5</td>
                <td style="text-align:right">-{float(sonuc.gecikme_cezasi):,.2f}</td></tr>
            <tr style="background:#c0392b;color:#fff;font-weight:bold">
                <td>TOPLAM KESİNTİ</td><td>—</td>
                <td style="text-align:right">-{float(sonuc.toplam_kesinti):,.2f}</td></tr>
            <tr style="background:#27ae60;color:#fff;font-weight:bold;font-size:14px">
                <td>NET ÖDEME (TL)</td><td>—</td>
                <td style="text-align:right">{float(sonuc.net_odeme):,.2f}</td></tr>
        """

        uyarilar_html = ""
        if sonuc.uyarilar:
            uyarilar_html = "<div style='background:#7d6608;color:#fff;padding:8px;border-radius:4px;margin-top:12px'>"
            for u in sonuc.uyarilar:
                uyarilar_html += f"<p style='margin:4px 0'>&#9888; {u}</p>"
            uyarilar_html += "</div>"

        html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px;
         background: #fff; color: #111; margin: 20px;}}
  h1 {{text-align:center; font-size:18px; margin-bottom:4px; color:#2c3e50;}}
  h2 {{font-size:13px; color:#2c3e50; margin:16px 0 4px 0; border-bottom:1px solid #aaa; padding-bottom:2px;}}
  table {{border-collapse:collapse; width:100%; margin-bottom:10px; font-size:12px;}}
  th {{background:#2c3e50; color:#fff; padding:5px 8px; text-align:left;}}
  td {{padding:4px 8px; border:1px solid #ccc;}}
  tr:nth-child(even) {{background:#f5f5f5;}}
  .info-tablo td:first-child {{font-weight:bold; background:#ecf0f1; width:200px;}}
  .imza-tablo td {{height:60px; width:33%; text-align:center; font-weight:bold; background:#fafafa;}}
</style>
</head>
<body>
<h1>KAMU YAPIM İŞİ HAKEDİŞ BELGESİ</h1>
<p style="text-align:center;color:#555">
  Hakediş No: {bilgi.hakedis_no} &nbsp;|&nbsp; Tarih: {tarih_str}
  &nbsp;|&nbsp; Dönem: {donemi or "—"}
</p>
<hr>

<h2>PROJE BİLGİLERİ</h2>
<table class="info-tablo">
  <tr><td>Proje Adı</td><td>{proje_adi or "—"}</td></tr>
  <tr><td>Sözleşme No</td><td>{sozlesme_no or "—"}</td></tr>
  <tr><td>İdare Adı</td><td>{idare_adi or "—"}</td></tr>
  <tr><td>Müteahhit / Firma</td><td>{firma_adi or "—"}</td></tr>
  <tr><td>Sözleşme Bedeli</td><td>{float(bilgi.sozlesme_bedeli):,.2f} TL</td></tr>
</table>

<h2>İMALAT KALEMLERİ</h2>
<table>
  <tr>
    <th>Sıra</th><th>Poz No</th><th>Tanım</th><th>Birim</th>
    <th>Sözl. Miktar</th><th>Gerç. Miktar</th><th>B.Fiyat (TL)</th><th>Tutar (TL)</th>
  </tr>
  {imalat_satirlari_html}
  <tr style="font-weight:bold;background:#ecf0f1">
    <td colspan="7" style="text-align:right">BRÜT HAKEDİŞ TOPLAMI:</td>
    <td style="text-align:right">{float(sonuc.brut_hakedis):,.2f}</td>
  </tr>
</table>

<h2>KESİNTİ CETVELİ</h2>
<table>
  <tr><th>Kesinti Kalemi</th><th>Oran / Gün</th><th>Tutar (TL)</th></tr>
  {kesinti_satirlari_html}
</table>

{uyarilar_html}

<h2>İMZA BÖLÜMLERİ</h2>
<table class="imza-tablo">
  <tr>
    <td>İdare Yetkilisi<br><br><br>Ad Soyad / İmza / Tarih</td>
    <td>Kontrol Mühendisi<br><br><br>Ad Soyad / İmza / Tarih</td>
    <td>Müteahhit / Firma<br><br><br>Ad Soyad / İmza / Tarih</td>
  </tr>
</table>

<p style="text-align:center;color:#999;font-size:10px;margin-top:20px">
  Bu belge İnşaat Metraj Pro yazılımı ile 4734/4735 sayılı Kanunlar çerçevesinde hazırlanmıştır.
</p>
</body>
</html>"""
        return html

    # ------------------------------------------------------------------
    # PDF çıktısı
    # ------------------------------------------------------------------

    def _on_pdf_al(self):
        if self._son_sonuc is None:
            QMessageBox.information(
                self,
                "Önce Hesaplayın",
                "PDF almak için önce kesinti hesabı yapın.",
            )
            return

        dosya, _ = QFileDialog.getSaveFileName(
            self,
            "PDF Kaydet",
            f"hakedis_{self._son_bilgi.hakedis_no}.pdf",
            "PDF Dosyaları (*.pdf)",
        )
        if not dosya:
            return

        # İmalat satırları PDF için hazırla
        imalat_satirlari = []
        for idx, kalem in enumerate(self._imalat_kalemleri):
            imalat_satirlari.append([
                str(idx + 1),
                kalem.get("poz_kodu", ""),
                kalem.get("aciklama", ""),
                kalem.get("birim", ""),
                f"{kalem.get('sozlesme_miktar', 0):.3f}",
                f"{kalem.get('gerceklesen_miktar', 0):.3f}",
                f"{kalem.get('birim_fiyat', 0):,.2f}",
                f"{kalem.get('tutar', 0):,.2f}",
            ])

        basari = self._engine.pdf_hakedis_belgesi_uret(
            bilgi=self._son_bilgi,
            sonuc=self._son_sonuc,
            dosya_yolu=dosya,
            proje_adi=self._proje_adi_input.text(),
            idare_adi=self._idare_adi_input.text(),
            firma_adi=self._firma_adi_input.text(),
            sozlesme_no=self._sozlesme_no_input.text(),
            imalat_satirlari=imalat_satirlari,
        )

        if basari:
            QMessageBox.information(
                self,
                "PDF Kaydedildi",
                f"Hakediş belgesi PDF olarak kaydedildi:\n{dosya}",
            )
            self._status.showMessage(f"PDF kaydedildi: {dosya}")
        else:
            QMessageBox.critical(
                self,
                "PDF Hatası",
                "PDF oluşturulamadı. reportlab kurulu olduğundan emin olun:\n"
                "pip install reportlab",
            )
