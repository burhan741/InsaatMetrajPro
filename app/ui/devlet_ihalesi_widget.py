"""
Devlet İhalesi Ana Konteyner Widget
====================================
4734 Kamu İhale Kanunu kapsamındaki tüm alt araçları QTabWidget altında toplar.
Sekmeler lazy-load + try/except ile yüklenir — bir sekme bozuksa diğerleri etkilenmez.

Alt sekmeler:
  0 — Yaklaşık Maliyet ve Keşif Özeti
  1 — Hakediş Kesinti ve Mahsup Hesabı
  2 — SGK Asgari İşçilik Hesabı
  3 — Fiyat Farkı Hesabı
  4 — Birim Fiyat Analiz Cetveli
  5 — Gecikme Cezası / Süre Uzatımı
  6 — Teminat Yönetimi

Rev-79 (2026-04-26): Lazy-load + try/except koruma eklendi.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import logging

logger = logging.getLogger(__name__)

DARK_BG = "#1a1a2e"
ACCENT  = "#00BFFF"

_SEKME_ISIMLERI = [
    "Yaklaşık Maliyet",
    "Hakediş Kesintileri",
    "SGK İşçilik",
    "Fiyat Farkı",
    "Birim Fiyat Analizi",
    "Gecikme Cezası",
    "Teminat Yönetimi",
]


class _PlaceholderTab(QWidget):
    """Yükleme sırasında veya hata durumunda gösterilen geçici sekme."""

    def __init__(self, mesaj: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(mesaj or "Yükleniyor…")
        lbl.setFont(QFont("Segoe UI", 13))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #555; padding: 40px;")
        layout.addWidget(lbl)
        self.setStyleSheet(f"background-color: {DARK_BG};")


class DevletIhalesiWidget(QWidget):
    """
    Devlet İhalesi ana sekmesinin kök widget'ı.

    Her alt sekme ilk tıklandığında lazy-load edilir.
    Import hatası olursa o sekme hata mesajı gösterir — diğerleri etkilenmez.
    """

    def __init__(self, db=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self._yuklendi: dict[int, bool] = {}
        self._build_ui()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.alt_tabs = QTabWidget()
        self.alt_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.alt_tabs.currentChanged.connect(self._lazy_yukle)
        self.alt_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: {DARK_BG};
            }}
            QTabBar::tab {{
                background-color: #0f3460;
                color: #a0a0b0;
                padding: 7px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background-color: #003366;
                color: {ACCENT};
                font-weight: bold;
            }}
            QTabBar::tab:hover {{
                background-color: #1a3a6e;
            }}
        """)

        # Tüm sekmeler placeholder olarak eklenir
        for isim in _SEKME_ISIMLERI:
            self.alt_tabs.addTab(_PlaceholderTab("Yükleniyor…"), isim)

        root.addWidget(self.alt_tabs)
        self.setStyleSheet(f"background-color: {DARK_BG};")

        # İlk sekmeyi hemen yükle
        self._lazy_yukle(0)

    # ── Lazy load çekirdeği ──────────────────────────────────────────────────

    def _lazy_yukle(self, index: int) -> None:
        if self._yuklendi.get(index):
            return
        _YUKLEYICILER = {
            0: self._yukle_yaklasik_maliyet,
            1: self._yukle_hakedis_kesinti,
            2: self._yukle_sgk,
            3: self._yukle_fiyat_farki,
            4: self._yukle_birim_fiyat,
            5: self._yukle_gecikme,
            6: self._yukle_teminat,
        }
        yukleyici = _YUKLEYICILER.get(index)
        if yukleyici:
            yukleyici()
        self._yuklendi[index] = True

    def _sekme_degistir(self, index: int, widget: QWidget) -> None:
        """Placeholder'ı gerçek widget ile değiştirir."""
        self.alt_tabs.blockSignals(True)
        isim = self.alt_tabs.tabText(index)
        self.alt_tabs.removeTab(index)
        self.alt_tabs.insertTab(index, widget, isim)
        self.alt_tabs.setCurrentIndex(index)
        self.alt_tabs.blockSignals(False)

    def _hata_goster(self, index: int, hata: Exception) -> None:
        logger.error("Sekme %d yüklenemedi: %s", index, hata)
        isim = _SEKME_ISIMLERI[index] if index < len(_SEKME_ISIMLERI) else f"Sekme {index}"
        w = _PlaceholderTab(
            f"🚧 {isim}\nYüklenemedi — modül bozuk veya eksik.\n\n"
            f"Hata: {type(hata).__name__}: {str(hata)[:120]}"
        )
        self._sekme_degistir(index, w)

    # ── Bireysel yükleyiciler ────────────────────────────────────────────────

    def _yukle_yaklasik_maliyet(self) -> None:
        try:
            from app.ui.yaklasik_maliyet_window import YaklasikMaliyetWindow
            self._sekme_degistir(0, YaklasikMaliyetWindow(self.db))
        except Exception as e:
            self._hata_goster(0, e)

    def _yukle_hakedis_kesinti(self) -> None:
        try:
            from app.ui.hakedis_kesinti_window import HakedisKesintWindow
            self._sekme_degistir(1, HakedisKesintWindow(self.db))
        except Exception as e:
            self._hata_goster(1, e)

    def _yukle_sgk(self) -> None:
        try:
            from app.ui.sgk_iscilik_window import SgkIscilkWindow
            self._sekme_degistir(2, SgkIscilkWindow(self.db))
        except Exception as e:
            self._hata_goster(2, e)

    def _yukle_fiyat_farki(self) -> None:
        try:
            from app.ui.fiyat_farki_window import FiyatFarkiWindow
            self._sekme_degistir(3, FiyatFarkiWindow(self.db))
        except Exception as e:
            self._hata_goster(3, e)

    def _yukle_birim_fiyat(self) -> None:
        try:
            from app.ui.birim_fiyat_analiz_window import BirimFiyatAnalizWindow
            self._sekme_degistir(4, BirimFiyatAnalizWindow(self.db))
        except Exception as e:
            self._hata_goster(4, e)

    def _yukle_gecikme(self) -> None:
        try:
            from app.ui.gecikme_ceza_window import GecikmeCezaWindow
            self._sekme_degistir(5, GecikmeCezaWindow(self.db))
        except Exception as e:
            self._hata_goster(5, e)

    def _yukle_teminat(self) -> None:
        try:
            from app.ui.teminat_window import TeminatWindow
            self._sekme_degistir(6, TeminatWindow(self.db))
        except Exception as e:
            self._hata_goster(6, e)
