# -*- coding: utf-8 -*-
"""
asistan_pencere.py — Bağımsız (floating) AI İnşaat Danışmanı Penceresi

AsistanPanel'i QMainWindow içinde barındırır. Kapatıldığında yok edilmez,
sadece gizlenir; sonraki çağrıda tekrar gösterilir.

Mimari:
    AsistanPencere(QMainWindow)
        └─ AsistanPanel (setCentralWidget)
        └─ QToolBar  (Üstte Tut / Geçmişi Temizle / API Ayarları)
"""

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow,
    QPushButton,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AsistanPanel import guard
# ---------------------------------------------------------------------------
try:
    from app.ui.asistan_panel import AsistanPanel
    _ASISTAN_PANEL_OK = True
except Exception as exc:
    logger.warning("AsistanPanel yüklenemedi: %s", exc)
    _ASISTAN_PANEL_OK = False
    AsistanPanel = None  # type: ignore


class AsistanPencere(QMainWindow):
    """
    Bağımsız AI İnşaat Danışmanı penceresi.

    Kapatma düğmesine basıldığında gizlenir (yok edilmez).
    goster_veya_one_getir() metodu ile tekrar açılır.
    """

    _BASLIK_TEMEL = "🤖 AI İnşaat Danışmanı"

    # Ana pencereye Gantt sekmesini aç isteği (panel'den yönlendirilir)
    gantt_ac_istegi = pyqtSignal()
    # Gantt güncellemesi (panel'den yönlendirilir)
    gantt_guncellendi = pyqtSignal()

    def __init__(self, db, parent=None):
        """
        Parametreler
        ------------
        db : DatabaseManager
            Veritabanı bağlantısı.
        parent : QWidget, isteğe bağlı
            Ana pencere referansı.
        """
        super().__init__(parent)

        self._db = db
        self._proje_adi = None

        # Kapatınca yok etme — sadece gizle
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._pencere_kur()
        self._toolbar_kur()
        self._merkezi_widget_kur()
        self._stiller_uygula()

    # ------------------------------------------------------------------
    # Kurulum metodları
    # ------------------------------------------------------------------

    def _pencere_kur(self):
        """Pencere başlığı, boyutu ve temel ayarlar."""
        self.setWindowTitle(self._BASLIK_TEMEL)
        self.resize(520, 750)
        self.setMinimumSize(480, 600)

    def _toolbar_kur(self):
        """Üst araç çubuğunu (QToolBar) oluşturur ve butonları ekler."""
        toolbar = self.addToolBar("Araçlar")
        toolbar.setMovable(False)
        toolbar.setObjectName("AsistanToolbar")

        # ── Üstte Tut ──────────────────────────────────────────────────
        self._ust_tut_btn = QPushButton("📌 Üstte Tut")
        self._ust_tut_btn.setCheckable(True)
        self._ust_tut_btn.setFixedHeight(28)
        self._ust_tut_btn.setToolTip("Pencereyi her zaman üstte tut")
        self._ust_tut_btn.toggled.connect(self._toggle_ust_tut)
        toolbar.addWidget(self._ust_tut_btn)

        toolbar.addSeparator()

        # ── Geçmişi Temizle ────────────────────────────────────────────
        temizle_btn = QPushButton("🗑 Geçmişi Temizle")
        temizle_btn.setFixedHeight(28)
        temizle_btn.setToolTip("Sohbet geçmişini ve ekran görüntüsünü temizle")
        temizle_btn.clicked.connect(self._gecmisi_temizle)
        toolbar.addWidget(temizle_btn)

        toolbar.addSeparator()

        # ── API Ayarları ───────────────────────────────────────────────
        ayar_btn = QPushButton("⚙️ API Ayarları")
        ayar_btn.setFixedHeight(28)
        ayar_btn.setToolTip("Claude API anahtarı ve model ayarları")
        ayar_btn.clicked.connect(self._api_ayarla)
        toolbar.addWidget(ayar_btn)

        # Toolbar referansını sakla (stil için)
        self._toolbar = toolbar

    def _merkezi_widget_kur(self):
        """AsistanPanel'i oluşturur ve merkezi widget olarak atar."""
        if _ASISTAN_PANEL_OK and AsistanPanel is not None:
            try:
                self._asistan_panel = AsistanPanel(self._db, parent=self)
                self.setCentralWidget(self._asistan_panel)
                # Panel sinyallerini pencere sinyallerine köprüle
                self._asistan_panel.gantt_ac_istegi.connect(self.gantt_ac_istegi)
                self._asistan_panel.gantt_guncellendi.connect(self.gantt_guncellendi)
                logger.info("AsistanPanel başarıyla yüklendi.")
            except Exception as exc:
                logger.error("AsistanPanel oluşturulamadı: %s", exc)
                self._asistan_panel = None
                self._yedek_widget_kur()
        else:
            self._asistan_panel = None
            self._yedek_widget_kur()

    def _yedek_widget_kur(self):
        """AsistanPanel yüklenemezse basit hata mesajı gösterir."""
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtCore import Qt as _Qt

        hata_lbl = QLabel(
            "⚠️ AI Asistan paneli yüklenemedi.\n"
            "Lütfen 'app/ui/asistan_panel.py' dosyasını kontrol edin."
        )
        hata_lbl.setAlignment(_Qt.AlignmentFlag.AlignCenter)
        hata_lbl.setStyleSheet("color: #ff6b6b; font-size: 13px; padding: 20px;")
        self.setCentralWidget(hata_lbl)

    def _stiller_uygula(self):
        """Koyu tema stillerini uygular."""
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #1a1a2e;
            }
            QToolBar#AsistanToolbar {
                background-color: #0f3460;
                border-bottom: 1px solid #16213e;
                spacing: 4px;
                padding: 2px 4px;
            }
            QToolBar#AsistanToolbar QPushButton {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #0f3460;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 12px;
            }
            QToolBar#AsistanToolbar QPushButton:hover {
                background-color: #1a4a7a;
                border-color: #4fc3f7;
            }
            QToolBar#AsistanToolbar QPushButton:checked {
                background-color: #1565c0;
                border-color: #42a5f5;
                color: #ffffff;
            }
            QToolBar#AsistanToolbar QToolBarSeparator {
                background-color: #0f3460;
                width: 1px;
                margin: 4px 2px;
            }
            """
        )

    # ------------------------------------------------------------------
    # Genel API
    # ------------------------------------------------------------------

    def goster_veya_one_getir(self):
        """
        Pencere gizliyse gösterir; görünürse ön plana getirir.
        Ana pencereden çağrılacak birincil metottur.
        """
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

    def proje_guncelle(self, proje_id: int, proje_adi: str):
        """
        Aktif projeyi asistan paneline ve başlığa iletir.

        Parametreler
        ------------
        proje_id : int
            Veritabanı proje kimliği.
        proje_adi : str
            Gösterilecek proje adı.
        """
        self._proje_adi = proje_adi

        # Başlığı güncelle
        self.setWindowTitle(f"{self._BASLIK_TEMEL} — {proje_adi}")

        # Panele proxy
        if self._asistan_panel is not None:
            try:
                self._asistan_panel.proje_guncelle(proje_id, proje_adi)
            except Exception as exc:
                logger.warning("proje_guncelle proxy hatası: %s", exc)

    def set_gantt_engine(self, engine):
        """
        Gantt motorunu asistan paneline iletir.

        Parametreler
        ------------
        engine : GanttEngine
            Gantt hesaplama motoru referansı.
        """
        if self._asistan_panel is not None:
            try:
                self._asistan_panel.set_gantt_engine(engine)
            except Exception as exc:
                logger.warning("set_gantt_engine proxy hatası: %s", exc)

    def set_gantt_window(self, gantt_window):
        """GanttWindow referansını asistan paneline iletir."""
        if self._asistan_panel is not None:
            try:
                self._asistan_panel.set_gantt_window(gantt_window)
            except Exception as exc:
                logger.warning("set_gantt_window proxy hatası: %s", exc)

    # ------------------------------------------------------------------
    # Toolbar slot'ları
    # ------------------------------------------------------------------

    def _toggle_ust_tut(self, checked: bool):
        """
        Pencerenin "her zaman üstte" bayrağını açıp kapatır.
        Flag değişince pencere yeniden gösterilir (Qt zorunluluğu).
        """
        flags = self.windowFlags()
        if checked:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)

        # Flag değişince Qt pencereyi gizler, manuel olarak yeniden göster
        self.show()
        self._ust_tut_btn.setText(
            "📌 Üstte Sabitlendi" if checked else "📌 Üstte Tut"
        )

    def _gecmisi_temizle(self):
        """Sohbet geçmişini temizle — AsistanPanel'e proxy."""
        if self._asistan_panel is not None:
            try:
                self._asistan_panel._gecmisi_temizle()
            except Exception as exc:
                logger.warning("_gecmisi_temizle proxy hatası: %s", exc)

    def _api_ayarla(self):
        """API ayarları diyaloğunu aç — AsistanPanel'e proxy."""
        if self._asistan_panel is not None:
            try:
                self._asistan_panel._api_ayarla()
            except Exception as exc:
                logger.warning("_api_ayarla proxy hatası: %s", exc)

    # ------------------------------------------------------------------
    # Olay yönetimi
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        """
        Kapatma düğmesine basıldığında pencereyi gizler, yok etmez.
        WA_DeleteOnClose False olduğundan accept() çağrılsa bile
        nesne bellekte kalır; biz yine de ignore() ile açık bırakırız.
        """
        self.hide()
        event.ignore()
