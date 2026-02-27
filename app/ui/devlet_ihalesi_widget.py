"""
Devlet İhalesi Ana Konteyner Widget
====================================
4734 Kamu İhale Kanunu kapsamındaki tüm alt araçları bir QTabWidget
altında toplar. Araçlar lazy loading ile yüklenir.

Alt sekmeler:
 0 — Yaklaşık Maliyet ve Keşif Özeti
 1 — Hakediş Kesinti ve Mahsup Hesabı
 2 — SGK Asgari İşçilik Hesabı
 3 — Fiyat Farkı Hesabı
 4 — Birim Fiyat Analiz Cetveli
 5 — Gecikme Cezası / Süre Uzatımı
 6 — Teminat Yönetimi
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


DARK_BG = "#1a1a2e"
ACCENT = "#00BFFF"


class _PlaceholderTab(QWidget):
    """Henüz eklenmemiş araç için geçici sekme."""

    def __init__(self, araç_adi: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(f"🚧 {araç_adi}\nGeliştirme aşamasında…")
        lbl.setFont(QFont("Segoe UI", 14))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #555; padding: 40px;")
        layout.addWidget(lbl)
        self.setStyleSheet(f"background-color: {DARK_BG};")


class DevletIhalesiWidget(QWidget):
    """
    Devlet İhalesi ana sekmesinin kök widget'ı.

    main_window.py'de lazy-load ile oluşturulur ve index 12'ye yerleştirilir.
    """

    def __init__(self, db=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self._alt_tabs_created: dict[int, bool] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.alt_tabs = QTabWidget()
        self.alt_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.alt_tabs.currentChanged.connect(self._on_alt_tab_changed)
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

        # Sekme 0 — Yaklaşık Maliyet (hemen yükle)
        from app.ui.yaklasik_maliyet_window import YaklasikMaliyetWindow
        yaklasik_widget = YaklasikMaliyetWindow(self.db)
        self.alt_tabs.addTab(yaklasik_widget, "Yaklaşık Maliyet")
        self._alt_tabs_created[0] = True

        # Sekme 1 — Hakediş Kesintileri (hemen yükle)
        from app.ui.hakedis_kesinti_window import HakedisKesintWindow
        hakedis_widget = HakedisKesintWindow(self.db)
        self.alt_tabs.addTab(hakedis_widget, "Hakediş Kesintileri")
        self._alt_tabs_created[1] = True

        # Sekme 2 — SGK Asgari İşçilik (hemen yükle)
        from app.ui.sgk_iscilik_window import SgkIscilkWindow
        sgk_widget = SgkIscilkWindow(self.db)
        self.alt_tabs.addTab(sgk_widget, "SGK İşçilik")
        self._alt_tabs_created[2] = True

        # Sekme 3 — Fiyat Farkı Hesabı (hemen yükle)
        from app.ui.fiyat_farki_window import FiyatFarkiWindow
        ff_widget = FiyatFarkiWindow(self.db)
        self.alt_tabs.addTab(ff_widget, "Fiyat Farkı")
        self._alt_tabs_created[3] = True

        # Sekme 4 — Birim Fiyat Analiz Cetveli (hemen yükle)
        from app.ui.birim_fiyat_analiz_window import BirimFiyatAnalizWindow
        bfa_widget = BirimFiyatAnalizWindow(self.db)
        self.alt_tabs.addTab(bfa_widget, "Birim Fiyat Analizi")
        self._alt_tabs_created[4] = True

        # Sekme 5 — Gecikme Cezası (hemen yükle)
        from app.ui.gecikme_ceza_window import GecikmeCezaWindow
        gecikme_widget = GecikmeCezaWindow(self.db)
        self.alt_tabs.addTab(gecikme_widget, "Gecikme Cezası")
        self._alt_tabs_created[5] = True

        # Sekme 6 — Teminat Yönetimi (hemen yükle)
        from app.ui.teminat_window import TeminatWindow
        teminat_widget = TeminatWindow(self.db)
        self.alt_tabs.addTab(teminat_widget, "Teminat Yönetimi")
        self._alt_tabs_created[6] = True

        root.addWidget(self.alt_tabs)
        self.setStyleSheet(f"background-color: {DARK_BG};")

    # ------------------------------------------------------------------
    # Lazy loading (ilerideki araçlar için)
    # ------------------------------------------------------------------

    def _on_alt_tab_changed(self, index: int) -> None:
        """
        Şu an tüm sekmeler hemen yüklendiği için burada ek işlem yok.
        İleride yeni araçlar lazy-load ile buraya eklenebilir.
        """
        pass
