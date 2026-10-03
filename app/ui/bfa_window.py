"""
bfa_window.py — Birim Fiyat Analizi (BFA) Penceresi
CŞB standardına göre analiz cetveli oluşturma, düzenleme ve PDF çıktı.
Rev-74 (2026-04-25)
"""

import logging
from typing import List, Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QListWidget, QListWidgetItem, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox,
    QDoubleSpinBox, QGridLayout, QFrame, QMessageBox,
    QFileDialog, QToolBar, QSizePolicy, QAbstractItemView,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Renk şeması
# ---------------------------------------------------------------------------
DARK_BG    = "#1a1a2e"
CARD_BG    = "#16213e"
ACCENT     = "#00BFFF"
TEXT_WHITE = "#e0e0e0"
TEXT_GRAY  = "#a0a0b0"
GREEN      = "#27ae60"
RED        = "#e74c3c"
ORANGE     = "#f39c12"
PURPLE     = "#8e44ad"

# Tür bazında tablo satır renkleri (RGBA)
_RENK_MALZEME = QColor(80, 120, 180, 60)
_RENK_ISCILIK = QColor(40, 160, 80, 60)
_RENK_MAKINE  = QColor(200, 130, 40, 60)

_TUR_RENK_MAP = {
    "malzeme": _RENK_MALZEME,
    "iscilik":  _RENK_ISCILIK,
    "makine":   _RENK_MAKINE,
}

_TUR_ETIKET = {
    "malzeme": "Malzeme",
    "iscilik":  "İşçilik",
    "makine":   "Makine",
}

_BIRIM_SECENEKLER = ["m²", "m³", "kg", "adet", "m", "ton", "lt", "saat", "gün"]

# ---------------------------------------------------------------------------
# Import — hata toleranslı
# ---------------------------------------------------------------------------
try:
    from app.core.bfa_engine import BFAEngine
    _ENGINE_OK = True
except Exception as _e:
    logger.error("BFAEngine import hatası: %s", _e)
    _ENGINE_OK = False

    class BFAEngine:  # type: ignore[no-redef]
        """Sahte motor — import başarısız olduğunda kullanılır."""
        def tum_analizler(self) -> list:
            return []
        def hesapla(self, k: str) -> dict:
            return {}
        def analiz_getir(self, k: str):
            return None
        def analiz_kaydet(self, *a, **kw) -> int:
            return -1
        def bilesen_ekle(self, *a, **kw) -> int:
            return -1
        def bilesen_sil(self, k: int) -> bool:
            return False
        def bilesen_guncelle(self, *a, **kw) -> bool:
            return False
        def pdf_analiz_belgesi_uret(self, k: str, d: str) -> bool:
            return False
        def csv_disari_aktar(self, k: str, d: str) -> bool:
            return False


# ---------------------------------------------------------------------------
# Yardımcı: para formatı
# ---------------------------------------------------------------------------
def _para(deger: float) -> str:
    """1234567.89 → '1.234.567,89'"""
    try:
        return "{:,.2f}".format(float(deger)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


# ===========================================================================
# _YeniAnalizDialog
# ===========================================================================
class _YeniAnalizDialog(QDialog):
    """Yeni analiz oluşturma diyaloğu."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Yeni BFA Analizi")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        self._poz_kodu = QLineEdit()
        self._poz_kodu.setPlaceholderText("Örn: 21.003")
        form.addRow("Poz Kodu:", self._poz_kodu)

        self._tanim = QLineEdit()
        self._tanim.setPlaceholderText("Analiz tanımı…")
        form.addRow("Tanım:", self._tanim)

        self._birim = QComboBox()
        self._birim.addItems(_BIRIM_SECENEKLER)
        form.addRow("Birim:", self._birim)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._dogrula)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _dogrula(self) -> None:
        if not self._poz_kodu.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Poz kodu boş bırakılamaz.")
            return
        if not self._tanim.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Tanım boş bırakılamaz.")
            return
        self.accept()

    def degerler(self) -> dict:
        return {
            "poz_kodu": self._poz_kodu.text().strip(),
            "tanim": self._tanim.text().strip(),
            "birim": self._birim.currentText(),
        }


# ===========================================================================
# _BilesenDialog
# ===========================================================================
class _BilesenDialog(QDialog):
    """Bileşen ekleme / düzenleme diyaloğu."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        bilesen: Optional[dict] = None,
        varsayilan_tur: str = "malzeme",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bileşen Düzenle" if bilesen else "Yeni Bileşen")
        self.setMinimumWidth(450)
        self._bilesen = bilesen or {}
        self._varsayilan_tur = varsayilan_tur
        self._build_ui()
        if bilesen:
            self._doldur(bilesen)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        self._tur = QComboBox()
        self._tur.addItems(["malzeme", "iscilik", "makine"])
        # Etiket göster
        self._tur.setItemText(0, "Malzeme")
        self._tur.setItemText(1, "İşçilik")
        self._tur.setItemText(2, "Makine")
        # Gerçek değerleri UserRole ile sakla
        self._tur.setItemData(0, "malzeme", Qt.ItemDataRole.UserRole)
        self._tur.setItemData(1, "iscilik", Qt.ItemDataRole.UserRole)
        self._tur.setItemData(2, "makine", Qt.ItemDataRole.UserRole)
        form.addRow("Tür:", self._tur)

        self._aciklama = QLineEdit()
        self._aciklama.setPlaceholderText("Malzeme / işçilik / makine açıklaması…")
        form.addRow("Açıklama:", self._aciklama)

        self._birim = QComboBox()
        self._birim.addItems(_BIRIM_SECENEKLER)
        form.addRow("Birim:", self._birim)

        self._miktar = QDoubleSpinBox()
        self._miktar.setRange(0.001, 99999.0)
        self._miktar.setDecimals(3)
        self._miktar.setSingleStep(0.1)
        self._miktar.valueChanged.connect(self._tutar_guncelle)
        form.addRow("Miktar:", self._miktar)

        self._birim_fiyat = QDoubleSpinBox()
        self._birim_fiyat.setRange(0.01, 9_999_999.0)
        self._birim_fiyat.setDecimals(2)
        self._birim_fiyat.setSingleStep(10.0)
        self._birim_fiyat.setPrefix("₺ ")
        self._birim_fiyat.valueChanged.connect(self._tutar_guncelle)
        form.addRow("Birim Fiyat:", self._birim_fiyat)

        self._tutar_label = QLabel("0,00 TL")
        fnt = self._tutar_label.font()
        fnt.setBold(True)
        fnt.setPointSize(11)
        self._tutar_label.setFont(fnt)
        self._tutar_label.setStyleSheet(f"color: {GREEN};")
        form.addRow("Tutar:", self._tutar_label)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._dogrula)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Varsayılan tür seçimi
        for i in range(self._tur.count()):
            if self._tur.itemData(i, Qt.ItemDataRole.UserRole) == self._varsayilan_tur:
                self._tur.setCurrentIndex(i)
                break

    def _doldur(self, b: dict) -> None:
        tur_val = b.get("tur", "malzeme")
        for i in range(self._tur.count()):
            if self._tur.itemData(i, Qt.ItemDataRole.UserRole) == tur_val:
                self._tur.setCurrentIndex(i)
                break

        self._aciklama.setText(b.get("aciklama", ""))

        birim_val = b.get("birim", "")
        idx = self._birim.findText(birim_val)
        if idx >= 0:
            self._birim.setCurrentIndex(idx)

        self._miktar.setValue(float(b.get("miktar", 0)))
        self._birim_fiyat.setValue(float(b.get("birim_fiyat", 0)))
        self._tutar_guncelle()

    def _tutar_guncelle(self) -> None:
        tutar = self._miktar.value() * self._birim_fiyat.value()
        self._tutar_label.setText(f"{_para(tutar)} TL")

    def _dogrula(self) -> None:
        if not self._aciklama.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Açıklama boş bırakılamaz.")
            return
        self.accept()

    def degerler(self) -> dict:
        return {
            "tur": self._tur.currentData(Qt.ItemDataRole.UserRole),
            "aciklama": self._aciklama.text().strip(),
            "birim": self._birim.currentText(),
            "miktar": self._miktar.value(),
            "birim_fiyat": self._birim_fiyat.value(),
        }


# ===========================================================================
# BFAWindow
# ===========================================================================
class BFAWindow(QWidget):
    """
    Birim Fiyat Analizi (BFA) ana penceresi.
    CŞB standardına uygun analiz cetveli görüntüleme, düzenleme ve PDF çıktı.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Birim Fiyat Analizi — BFA Cetveli")
        self.setMinimumSize(1100, 700)

        self._engine = BFAEngine()
        self._aktif_poz: Optional[str] = None
        self._aktif_analiz_id: Optional[int] = None
        self._bileseler: List[dict] = []

        self._build_ui()
        self._uygula_stil()
        self._analiz_listesi_yukle()

        if not _ENGINE_OK:
            QMessageBox.warning(
                self,
                "Motor Hatası",
                "BFAEngine yüklenemedi. Demo modunda çalışılıyor.\n"
                "Kaydetme ve PDF işlemleri devre dışı.",
            )

    # -----------------------------------------------------------------------
    # UI oluşturma
    # -----------------------------------------------------------------------
    def _build_ui(self) -> None:
        ana_layout = QHBoxLayout(self)
        ana_layout.setContentsMargins(8, 8, 8, 8)
        ana_layout.setSpacing(0)

        # Ana splitter
        ana_splitter = QSplitter(Qt.Orientation.Horizontal)
        ana_splitter.setChildrenCollapsible(False)

        # Sol panel
        sol_panel = self._sol_panel_olustur()
        ana_splitter.addWidget(sol_panel)

        # Sağ panel (dikey splitter)
        sag_splitter = QSplitter(Qt.Orientation.Vertical)
        sag_splitter.setChildrenCollapsible(False)

        sag_ust = self._bilesen_tablosu_olustur()
        sag_alt = self._hesaplama_ozeti_olustur()

        sag_splitter.addWidget(sag_ust)
        sag_splitter.addWidget(sag_alt)
        sag_splitter.setSizes([420, 280])

        ana_splitter.addWidget(sag_splitter)
        ana_splitter.setSizes([300, 800])

        ana_layout.addWidget(ana_splitter)

    # -----------------------------------------------------------------------
    # Sol panel — Analiz Listesi
    # -----------------------------------------------------------------------
    def _sol_panel_olustur(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("SolPanel")
        panel.setMaximumWidth(340)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Başlık
        baslik = QLabel("BFA Analizleri")
        baslik.setObjectName("PanelBaslik")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(baslik)

        # Arama
        self._arama = QLineEdit()
        self._arama.setPlaceholderText("Poz kodu veya tanım ara…")
        self._arama.textChanged.connect(self._filtrele)
        layout.addWidget(self._arama)

        # Liste
        self._liste = QListWidget()
        self._liste.setAlternatingRowColors(True)
        self._liste.itemClicked.connect(self._analiz_sec)
        layout.addWidget(self._liste)

        # Alt butonlar
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)

        self._btn_yeni = QPushButton("+ Yeni Analiz")
        self._btn_yeni.setObjectName("BtnYesil")
        self._btn_yeni.clicked.connect(self._yeni_analiz)
        btn_layout.addWidget(self._btn_yeni)

        self._btn_sil_analiz = QPushButton("Analiz Sil")
        self._btn_sil_analiz.setObjectName("BtnKirmizi")
        self._btn_sil_analiz.clicked.connect(self._analiz_sil)
        btn_layout.addWidget(self._btn_sil_analiz)

        self._btn_csv_disari = QPushButton("CSV Dışa Aktar")
        self._btn_csv_disari.setObjectName("BtnTuruncu")
        self._btn_csv_disari.clicked.connect(self._csv_disari_aktar)
        btn_layout.addWidget(self._btn_csv_disari)

        layout.addLayout(btn_layout)
        return panel

    # -----------------------------------------------------------------------
    # Sağ üst — Bileşen Tablosu
    # -----------------------------------------------------------------------
    def _bilesen_tablosu_olustur(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("SagPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Dinamik başlık
        self._bilesen_baslik = QLabel("Bileşen Cetveli")
        self._bilesen_baslik.setObjectName("PanelBaslik")
        layout.addWidget(self._bilesen_baslik)

        # Tablo
        self._tablo = QTableWidget()
        self._tablo.setColumnCount(7)
        self._tablo.setHorizontalHeaderLabels([
            "Sıra", "Tür", "Açıklama", "Birim", "Miktar", "Birim Fiyat (TL)", "Tutar (TL)"
        ])
        self._tablo.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._tablo.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._tablo.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._tablo.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tablo.setAlternatingRowColors(False)
        self._tablo.verticalHeader().setVisible(False)
        self._tablo.itemDoubleClicked.connect(self._bilesen_duzenle_secili)
        layout.addWidget(self._tablo)

        # Alt toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(6)

        self._btn_malzeme = QPushButton("+ Malzeme")
        self._btn_malzeme.setObjectName("BtnMavi")
        self._btn_malzeme.clicked.connect(lambda: self._bilesen_ekle_dialog("malzeme"))
        toolbar_layout.addWidget(self._btn_malzeme)

        self._btn_iscilik = QPushButton("+ İşçilik")
        self._btn_iscilik.setObjectName("BtnYesil")
        self._btn_iscilik.clicked.connect(lambda: self._bilesen_ekle_dialog("iscilik"))
        toolbar_layout.addWidget(self._btn_iscilik)

        self._btn_makine = QPushButton("+ Makine")
        self._btn_makine.setObjectName("BtnTuruncu")
        self._btn_makine.clicked.connect(lambda: self._bilesen_ekle_dialog("makine"))
        toolbar_layout.addWidget(self._btn_makine)

        toolbar_layout.addStretch()

        self._btn_secili_sil = QPushButton("Seçili Sil")
        self._btn_secili_sil.setObjectName("BtnKirmizi")
        self._btn_secili_sil.clicked.connect(self._bilesen_sil)
        toolbar_layout.addWidget(self._btn_secili_sil)

        self._btn_kaydet = QPushButton("Kaydet")
        self._btn_kaydet.setObjectName("BtnYesil")
        self._btn_kaydet.clicked.connect(self._kaydet)
        toolbar_layout.addWidget(self._btn_kaydet)

        self._btn_pdf = QPushButton("PDF Üret")
        self._btn_pdf.setObjectName("BtnTuruncu")
        self._btn_pdf.clicked.connect(self._pdf_uret)
        toolbar_layout.addWidget(self._btn_pdf)

        layout.addLayout(toolbar_layout)
        return panel

    # -----------------------------------------------------------------------
    # Sağ alt — Hesaplama Özeti
    # -----------------------------------------------------------------------
    def _hesaplama_ozeti_olustur(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("OzetPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Başlık
        baslik_row = QHBoxLayout()
        ozet_baslik = QLabel("Hesaplama Özeti (CŞB Formülü)")
        ozet_baslik.setObjectName("PanelBaslik")
        baslik_row.addWidget(ozet_baslik)
        baslik_row.addStretch()

        self._btn_yenile = QPushButton("Yenile")
        self._btn_yenile.setObjectName("BtnMavi")
        self._btn_yenile.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._btn_yenile.clicked.connect(self._hesaplama_guncelle)
        baslik_row.addWidget(self._btn_yenile)

        layout.addLayout(baslik_row)

        # Ayırıcı çizgi
        cizgi = QFrame()
        cizgi.setFrameShape(QFrame.Shape.HLine)
        cizgi.setStyleSheet(f"color: {TEXT_GRAY};")
        layout.addWidget(cizgi)

        # Grid
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)

        def _etiket(metin: str, bold: bool = False) -> QLabel:
            lbl = QLabel(metin)
            lbl.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 12px;")
            if bold:
                f = lbl.font()
                f.setBold(True)
                lbl.setFont(f)
            return lbl

        def _deger_lbl(renk: str = TEXT_WHITE, boyut: int = 12, bold: bool = False) -> QLabel:
            lbl = QLabel("—")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            style = f"color: {renk}; font-size: {boyut}px;"
            if bold:
                style += " font-weight: bold;"
            lbl.setStyleSheet(style)
            return lbl

        satir = 0
        grid.addWidget(_etiket("Malzeme Toplamı:"), satir, 0)
        self._lbl_malzeme = _deger_lbl()
        grid.addWidget(self._lbl_malzeme, satir, 1)
        satir += 1

        grid.addWidget(_etiket("İşçilik Toplamı:"), satir, 0)
        self._lbl_iscilik = _deger_lbl()
        grid.addWidget(self._lbl_iscilik, satir, 1)
        satir += 1

        grid.addWidget(_etiket("Makine Toplamı:"), satir, 0)
        self._lbl_makine = _deger_lbl()
        grid.addWidget(self._lbl_makine, satir, 1)
        satir += 1

        # Ayırıcı
        hr1 = QFrame()
        hr1.setFrameShape(QFrame.Shape.HLine)
        hr1.setStyleSheet(f"color: {TEXT_GRAY};")
        grid.addWidget(hr1, satir, 0, 1, 2)
        satir += 1

        grid.addWidget(_etiket("Ara Toplam:", bold=True), satir, 0)
        self._lbl_ara = _deger_lbl(TEXT_WHITE, 13, True)
        grid.addWidget(self._lbl_ara, satir, 1)
        satir += 1

        grid.addWidget(_etiket("+ %15 Genel Gider:"), satir, 0)
        self._lbl_genel = _deger_lbl(ORANGE)
        grid.addWidget(self._lbl_genel, satir, 1)
        satir += 1

        grid.addWidget(_etiket("+ %10 Kâr ve Risk:"), satir, 0)
        self._lbl_kar = _deger_lbl(ORANGE)
        grid.addWidget(self._lbl_kar, satir, 1)
        satir += 1

        # Ayırıcı
        hr2 = QFrame()
        hr2.setFrameShape(QFrame.Shape.HLine)
        hr2.setStyleSheet(f"color: {ACCENT};")
        grid.addWidget(hr2, satir, 0, 1, 2)
        satir += 1

        grid.addWidget(_etiket("BİRİM FİYAT:", bold=True), satir, 0)
        self._lbl_birim_fiyat = _deger_lbl(GREEN, 16, True)
        grid.addWidget(self._lbl_birim_fiyat, satir, 1)
        satir += 1

        layout.addLayout(grid)
        layout.addStretch()
        return panel

    # -----------------------------------------------------------------------
    # Stil
    # -----------------------------------------------------------------------
    def _uygula_stil(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_BG};
                color: {TEXT_WHITE};
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }}
            QWidget#SolPanel {{
                background-color: {CARD_BG};
                border-right: 1px solid #2a2a4a;
            }}
            QWidget#SagPanel, QWidget#OzetPanel {{
                background-color: {DARK_BG};
            }}
            QLabel#PanelBaslik {{
                color: {ACCENT};
                font-size: 14px;
                font-weight: bold;
                padding: 4px 0;
            }}
            QLineEdit {{
                background-color: #0d1b2a;
                color: {TEXT_WHITE};
                border: 1px solid #2a2a5a;
                border-radius: 4px;
                padding: 5px 8px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
            }}
            QListWidget {{
                background-color: #0d1b2a;
                color: {TEXT_WHITE};
                border: 1px solid #2a2a5a;
                border-radius: 4px;
                alternate-background-color: #111828;
            }}
            QListWidget::item:selected {{
                background-color: {ACCENT};
                color: #000;
            }}
            QListWidget::item:hover {{
                background-color: #1e3050;
            }}
            QTableWidget {{
                background-color: #0d1b2a;
                color: {TEXT_WHITE};
                gridline-color: #1e2a3a;
                border: 1px solid #2a2a5a;
            }}
            QHeaderView::section {{
                background-color: #2c3e50;
                color: {TEXT_WHITE};
                font-weight: bold;
                padding: 5px;
                border: none;
                border-right: 1px solid #3a4a5a;
            }}
            QTableWidget::item:selected {{
                background-color: rgba(0, 191, 255, 80);
                color: {TEXT_WHITE};
            }}
            QPushButton {{
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
                border: none;
            }}
            QPushButton#BtnYesil {{
                background-color: {GREEN};
                color: white;
            }}
            QPushButton#BtnYesil:hover {{
                background-color: #2ecc71;
            }}
            QPushButton#BtnKirmizi {{
                background-color: {RED};
                color: white;
            }}
            QPushButton#BtnKirmizi:hover {{
                background-color: #ff5a4a;
            }}
            QPushButton#BtnTuruncu {{
                background-color: {ORANGE};
                color: white;
            }}
            QPushButton#BtnTuruncu:hover {{
                background-color: #f0b429;
            }}
            QPushButton#BtnMavi {{
                background-color: #2980b9;
                color: white;
            }}
            QPushButton#BtnMavi:hover {{
                background-color: #3498db;
            }}
            QSplitter::handle {{
                background-color: #2a2a4a;
            }}
            QComboBox {{
                background-color: #0d1b2a;
                color: {TEXT_WHITE};
                border: 1px solid #2a2a5a;
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: #0d1b2a;
                color: {TEXT_WHITE};
                selection-background-color: {ACCENT};
                selection-color: #000;
            }}
            QDoubleSpinBox {{
                background-color: #0d1b2a;
                color: {TEXT_WHITE};
                border: 1px solid #2a2a5a;
                border-radius: 4px;
                padding: 4px 6px;
            }}
            QScrollBar:vertical {{
                background: {CARD_BG};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #3a4a6a;
                border-radius: 4px;
            }}
        """)

    # -----------------------------------------------------------------------
    # Analiz listesi yükleme
    # -----------------------------------------------------------------------
    def _analiz_listesi_yukle(self) -> None:
        self._liste.blockSignals(True)
        self._liste.clear()
        try:
            analizler = self._engine.tum_analizler()
            self._tum_analizler = analizler
            for a in analizler:
                metin = f"{a['poz_kodu']} — {a['poz_tanimi'] or '(tanım yok)'}"
                item = QListWidgetItem(metin)
                item.setData(Qt.ItemDataRole.UserRole, a["poz_kodu"])
                item.setToolTip(
                    f"Poz: {a['poz_kodu']}\n"
                    f"Birim: {a['birim']}\n"
                    f"Bileşen sayısı: {a.get('bilesen_sayisi', 0)}"
                )
                self._liste.addItem(item)
        except Exception as e:
            logger.error("Analiz listesi yükleme hatası: %s", e)
        finally:
            self._liste.blockSignals(False)

    def _filtrele(self, metin: str) -> None:
        metin = metin.lower().strip()
        for i in range(self._liste.count()):
            item = self._liste.item(i)
            gorunu = metin == "" or metin in item.text().lower()
            item.setHidden(not gorunu)

    # -----------------------------------------------------------------------
    # Analiz seçme
    # -----------------------------------------------------------------------
    def _analiz_sec(self, item: QListWidgetItem) -> None:
        poz_kodu = item.data(Qt.ItemDataRole.UserRole)
        if not poz_kodu:
            return
        self._aktif_poz = poz_kodu
        self._bilesen_tablosu_yukle(poz_kodu)
        self._hesaplama_guncelle()

    def _bilesen_tablosu_yukle(self, poz_kodu: str) -> None:
        try:
            analiz = self._engine.analiz_getir(poz_kodu)
            if analiz is None:
                return

            self._aktif_analiz_id = analiz.get("id")
            self._bileseler = analiz.get("bileseler", [])

            tanim = analiz.get("poz_tanimi", "")
            birim = analiz.get("birim", "")
            self._bilesen_baslik.setText(
                f"Bileşen Cetveli — {poz_kodu}  {tanim}  [{birim}]"
            )

            self._tablo.blockSignals(True)
            self._tablo.setRowCount(0)

            for sira, b in enumerate(self._bileseler, start=1):
                self._tablo.insertRow(self._tablo.rowCount())
                satir_idx = self._tablo.rowCount() - 1

                tur = b.get("tur", "malzeme")
                tur_etiketi = _TUR_ETIKET.get(tur, tur.capitalize())
                tutar = float(b.get("miktar", 0)) * float(b.get("birim_fiyat", 0))

                degerler = [
                    str(sira),
                    tur_etiketi,
                    b.get("aciklama", ""),
                    b.get("birim", ""),
                    "{:.3f}".format(float(b.get("miktar", 0))),
                    _para(b.get("birim_fiyat", 0)),
                    _para(tutar),
                ]

                renk = _TUR_RENK_MAP.get(tur, QColor(50, 50, 80, 60))

                for sutun, deger in enumerate(degerler):
                    cell = QTableWidgetItem(deger)
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if sutun == 2:
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    cell.setBackground(QBrush(renk))
                    # Bileşen id'sini ilk sütunda sakla
                    if sutun == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, b.get("id"))
                    self._tablo.setItem(satir_idx, sutun, cell)

        except Exception as e:
            logger.error("Bileşen tablosu yükleme hatası: %s", e)
            QMessageBox.critical(self, "Hata", f"Bileşenler yüklenemedi:\n{e}")
        finally:
            self._tablo.blockSignals(False)

    # -----------------------------------------------------------------------
    # Hesaplama özeti güncelleme
    # -----------------------------------------------------------------------
    def _hesaplama_guncelle(self) -> None:
        if not self._aktif_poz:
            return
        try:
            sonuc = self._engine.hesapla(self._aktif_poz)
            if not sonuc:
                return

            birim = sonuc.get("birim", "")

            self._lbl_malzeme.setText(f"{_para(sonuc['malzeme_toplam'])} TL")
            self._lbl_iscilik.setText(f"{_para(sonuc['iscilik_toplam'])} TL")
            self._lbl_makine.setText(f"{_para(sonuc['makine_toplam'])} TL")
            self._lbl_ara.setText(f"{_para(sonuc['ara_toplam'])} TL")
            self._lbl_genel.setText(f"{_para(sonuc['genel_gider'])} TL")
            self._lbl_kar.setText(f"{_para(sonuc['kar_risk'])} TL")

            birim_fiyat_str = (
                f"{_para(sonuc['birim_fiyat'])} TL/{birim}" if birim
                else f"{_para(sonuc['birim_fiyat'])} TL"
            )
            self._lbl_birim_fiyat.setText(birim_fiyat_str)

        except Exception as e:
            logger.error("Hesaplama güncellenemedi: %s", e)

    # -----------------------------------------------------------------------
    # Yeni analiz
    # -----------------------------------------------------------------------
    def _yeni_analiz(self) -> None:
        dlg = _YeniAnalizDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = dlg.degerler()
        poz_kodu = vals["poz_kodu"]
        tanim = vals["tanim"]
        birim = vals["birim"]

        # Varolan poz kodu kontrolü
        mevcut = self._engine.analiz_getir(poz_kodu)
        if mevcut:
            QMessageBox.warning(
                self,
                "Poz Kodu Mevcut",
                f"'{poz_kodu}' poz kodu zaten kayıtlı.\n"
                "Farklı bir poz kodu giriniz.",
            )
            return

        analiz_id = self._engine.analiz_kaydet(poz_kodu, tanim, birim, [])
        if analiz_id == -1:
            QMessageBox.critical(self, "Hata", "Analiz kaydedilemedi.")
            return

        self._analiz_listesi_yukle()
        # Yeni oluşturulan analizi seç
        for i in range(self._liste.count()):
            item = self._liste.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == poz_kodu:
                self._liste.setCurrentItem(item)
                self._analiz_sec(item)
                break

    # -----------------------------------------------------------------------
    # Analiz silme (aktif olanı sil)
    # -----------------------------------------------------------------------
    def _analiz_sil(self) -> None:
        if not self._aktif_poz:
            QMessageBox.information(self, "Bilgi", "Önce silinecek bir analiz seçiniz.")
            return
        cevap = QMessageBox.question(
            self,
            "Analiz Sil",
            f"'{self._aktif_poz}' analizini ve tüm bileşenlerini silmek istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return

        # Engine'de doğrudan silme metodu yok; aktif=0 yapmak yerine
        # analiz_kaydet ile boş bileşen listesi kaydet ve UI'dan kaldır.
        # Gerçek silme için SQLite'a doğrudan erişim (engine genişletilebilir).
        # Şimdilik: mevcut analizi kaydedip, aktif=0 SQL ile işle.
        try:
            # Bileşenlerle birlikte kaydet (boş liste → bileşenler silinir)
            # Sonra engine içindeki analizi inactive yap (engine._get_conn kullan)
            import sqlite3
            from pathlib import Path
            db_yolu = self._engine._db_yolu
            with sqlite3.connect(str(db_yolu)) as conn:
                analiz = conn.execute(
                    "SELECT id FROM bfa_analizleri WHERE poz_kodu = ?",
                    (self._aktif_poz,),
                ).fetchone()
                if analiz:
                    conn.execute(
                        "UPDATE bfa_analizleri SET aktif = 0 WHERE id = ?",
                        (analiz[0],),
                    )
                    conn.commit()

            self._aktif_poz = None
            self._aktif_analiz_id = None
            self._bileseler = []
            self._tablo.setRowCount(0)
            self._bilesen_baslik.setText("Bileşen Cetveli")
            self._analiz_listesi_yukle()
            self._ozet_sifirla()

        except Exception as e:
            logger.error("Analiz sil hatası: %s", e)
            QMessageBox.critical(self, "Hata", f"Analiz silinemedi:\n{e}")

    def _ozet_sifirla(self) -> None:
        for lbl in (
            self._lbl_malzeme, self._lbl_iscilik, self._lbl_makine,
            self._lbl_ara, self._lbl_genel, self._lbl_kar, self._lbl_birim_fiyat,
        ):
            lbl.setText("—")

    # -----------------------------------------------------------------------
    # CSV dışa aktar
    # -----------------------------------------------------------------------
    def _csv_disari_aktar(self) -> None:
        if not self._aktif_poz:
            QMessageBox.information(self, "Bilgi", "Önce bir analiz seçiniz.")
            return
        dosya, _ = QFileDialog.getSaveFileName(
            self,
            "CSV Olarak Kaydet",
            f"BFA_{self._aktif_poz.replace('.', '_')}.csv",
            "CSV Dosyaları (*.csv);;Tüm Dosyalar (*)",
        )
        if not dosya:
            return
        basarili = self._engine.csv_disari_aktar(self._aktif_poz, dosya)
        if basarili:
            QMessageBox.information(self, "Başarılı", f"CSV dosyası kaydedildi:\n{dosya}")
        else:
            QMessageBox.critical(self, "Hata", "CSV dışa aktarma başarısız.")

    # -----------------------------------------------------------------------
    # Bileşen ekleme dialog
    # -----------------------------------------------------------------------
    def _bilesen_ekle_dialog(self, tur: str = "malzeme") -> None:
        if not self._aktif_analiz_id:
            QMessageBox.information(self, "Bilgi", "Önce bir analiz seçiniz.")
            return
        dlg = _BilesenDialog(self, varsayilan_tur=tur)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = dlg.degerler()
        sira = self._tablo.rowCount() + 1
        bilesen_id = self._engine.bilesen_ekle(
            analiz_id=self._aktif_analiz_id,
            tur=vals["tur"],
            aciklama=vals["aciklama"],
            birim=vals["birim"],
            miktar=vals["miktar"],
            birim_fiyat=vals["birim_fiyat"],
            sira=sira,
        )
        if bilesen_id == -1:
            QMessageBox.critical(self, "Hata", "Bileşen eklenemedi.")
            return
        self._bilesen_tablosu_yukle(self._aktif_poz)
        self._hesaplama_guncelle()

    # -----------------------------------------------------------------------
    # Bileşen düzenleme — çift tıklama
    # -----------------------------------------------------------------------
    def _bilesen_duzenle_secili(self, item: QTableWidgetItem) -> None:
        satir = item.row()
        if satir < 0 or satir >= len(self._bileseler):
            return
        bilesen = self._bileseler[satir]
        dlg = _BilesenDialog(self, bilesen=bilesen)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = dlg.degerler()
        bilesen_id = bilesen.get("id")
        if not bilesen_id:
            return

        # Engine üzerinden tam güncelleme için: sil + ekle (tur/aciklama değişebilir)
        # bilesen_guncelle sadece miktar+birim_fiyat değiştiriyor; tür/açıklama için:
        try:
            import sqlite3
            db_yolu = self._engine._db_yolu
            tutar = vals["miktar"] * vals["birim_fiyat"]
            with sqlite3.connect(str(db_yolu)) as conn:
                conn.execute(
                    """
                    UPDATE bfa_bilesenler
                    SET tur = ?, aciklama = ?, birim = ?,
                        miktar = ?, birim_fiyat = ?, tutar = ?
                    WHERE id = ?
                    """,
                    (
                        vals["tur"], vals["aciklama"], vals["birim"],
                        vals["miktar"], vals["birim_fiyat"], tutar,
                        bilesen_id,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error("Bileşen güncelleme hatası: %s", e)
            QMessageBox.critical(self, "Hata", f"Bileşen güncellenemedi:\n{e}")
            return

        self._bilesen_tablosu_yukle(self._aktif_poz)
        self._hesaplama_guncelle()

    # -----------------------------------------------------------------------
    # Bileşen silme
    # -----------------------------------------------------------------------
    def _bilesen_sil(self) -> None:
        secili_satirlar = self._tablo.selectionModel().selectedRows()
        if not secili_satirlar:
            QMessageBox.information(self, "Bilgi", "Silmek için bir bileşen satırı seçiniz.")
            return

        satir_idxler = sorted([s.row() for s in secili_satirlar], reverse=True)

        for satir_idx in satir_idxler:
            if satir_idx >= len(self._bileseler):
                continue
            bilesen = self._bileseler[satir_idx]
            bilesen_id = bilesen.get("id")
            if not bilesen_id:
                continue
            basarili = self._engine.bilesen_sil(bilesen_id)
            if not basarili:
                QMessageBox.warning(
                    self, "Uyarı",
                    f"'{bilesen.get('aciklama', '')}' bileşeni silinemedi."
                )

        self._bilesen_tablosu_yukle(self._aktif_poz)
        self._hesaplama_guncelle()

    # -----------------------------------------------------------------------
    # Kaydet
    # -----------------------------------------------------------------------
    def _kaydet(self) -> None:
        if not self._aktif_poz:
            QMessageBox.information(self, "Bilgi", "Önce bir analiz seçiniz.")
            return

        analiz = self._engine.analiz_getir(self._aktif_poz)
        if not analiz:
            QMessageBox.critical(self, "Hata", "Analiz verisi alınamadı.")
            return

        # Mevcut bileşenleri tablodaki sıra ile kaydet
        bileseler = []
        for sira, b in enumerate(self._bileseler, start=1):
            bileseler.append({
                "tur": b.get("tur", "malzeme"),
                "aciklama": b.get("aciklama", ""),
                "birim": b.get("birim", ""),
                "miktar": float(b.get("miktar", 0)),
                "birim_fiyat": float(b.get("birim_fiyat", 0)),
                "sira": sira,
            })

        analiz_id = self._engine.analiz_kaydet(
            poz_kodu=self._aktif_poz,
            tanim=analiz.get("poz_tanimi", ""),
            birim=analiz.get("birim", ""),
            bileseler=bileseler,
        )
        if analiz_id == -1:
            QMessageBox.critical(self, "Hata", "Analiz kaydedilemedi.")
            return

        self._aktif_analiz_id = analiz_id
        self._bilesen_tablosu_yukle(self._aktif_poz)
        self._hesaplama_guncelle()
        QMessageBox.information(self, "Kaydedildi", "Analiz başarıyla kaydedildi.")

    # -----------------------------------------------------------------------
    # PDF üret
    # -----------------------------------------------------------------------
    def _pdf_uret(self) -> None:
        if not self._aktif_poz:
            QMessageBox.information(self, "Bilgi", "Önce bir analiz seçiniz.")
            return

        dosya, _ = QFileDialog.getSaveFileName(
            self,
            "PDF Olarak Kaydet",
            f"BFA_{self._aktif_poz.replace('.', '_')}.pdf",
            "PDF Dosyaları (*.pdf);;Tüm Dosyalar (*)",
        )
        if not dosya:
            return

        basarili = self._engine.pdf_analiz_belgesi_uret(self._aktif_poz, dosya)
        if basarili:
            QMessageBox.information(self, "Başarılı", f"PDF oluşturuldu:\n{dosya}")
        else:
            QMessageBox.critical(
                self,
                "PDF Hatası",
                "PDF oluşturulamadı.\n\n"
                "Olası neden: 'reportlab' kütüphanesi kurulu değil.\n"
                "Kurulum: pip install reportlab",
            )
