"""
PDF Metraj Penceresi — PDF plan uzerinde fare ile uzunluk/alan/sayim olcumu.
"""

import logging
from enum import Enum

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QGroupBox, QFrame, QInputDialog,
    QMessageBox, QFileDialog, QSpinBox, QDoubleSpinBox, QComboBox,
    QFormLayout, QSizePolicy, QToolButton,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPixmap, QImage,
    QCursor, QKeySequence,
)

logger = logging.getLogger(__name__)

try:
    from app.core.pdf_metraj_engine import PDFMetrajEngine, OlcuTipi, Olcu
    ENGINE_AVAILABLE = True
except Exception as exc:
    logger.error("pdf_metraj_engine import hatasi: %s", exc)
    ENGINE_AVAILABLE = False


class _ModTipi(Enum):
    BOSTA = "bosta"
    KALIBRASYON = "kalibrasyon"
    UZUNLUK = "uzunluk"
    ALAN = "alan"
    SAYIM = "sayim"


_MOD_RENK = {
    OlcuTipi.UZUNLUK: QColor("#e74c3c"),   # kirmizi
    OlcuTipi.ALAN:    QColor("#2980b9"),   # mavi
    OlcuTipi.SAYIM:   QColor("#27ae60"),   # yesil
}

_KALIBRASYON_RENK = QColor("#f39c12")   # turuncu


# ---------------------------------------------------------------------------
# Kanvas widget — PDF sayfasini gosterir, mouse olcumleri alir
# ---------------------------------------------------------------------------
class _PDFKanvas(QWidget):
    kalibrasyon_bitti  = pyqtSignal(list)   # [(x,y),(x,y)]
    olcu_bitti         = pyqtSignal(object, list)   # (OlcuTipi, noktalar)
    sayim_nokta_eklendi = pyqtSignal(list)  # tum noktalar
    koordinat          = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._mod = _ModTipi.BOSTA
        self._mevcut_noktalar: list = []
        self._fare_pos: tuple | None = None
        self._cizimler: list = []   # [(OlcuTipi, noktalar_list, aciklama)]
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def pixmap_goster(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.setFixedSize(pixmap.size())
        self.update()

    def mod_sec(self, mod: _ModTipi):
        self._mod = mod
        self._mevcut_noktalar = []
        self._guncelle_cursor()
        self.update()

    def cizim_ekle(self, tip: OlcuTipi, noktalar: list, aciklama: str = ""):
        self._cizimler.append((tip, list(noktalar), aciklama))
        self.update()

    def son_cizimi_sil(self):
        if self._cizimler:
            self._cizimler.pop()
            self.update()

    def tum_cizimleri_sil(self):
        self._cizimler.clear()
        self.update()

    def aktif_iptal(self):
        self._mevcut_noktalar = []
        self.update()

    # -- painting --
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._pixmap:
            painter.drawPixmap(0, 0, self._pixmap)
        else:
            painter.fillRect(self.rect(), QColor("#e8e8e8"))
            painter.setPen(QPen(QColor("#888")))
            painter.setFont(QFont("Segoe UI", 14))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "PDF dosyasi acin"
            )
            painter.end()
            return

        # Tamamlanmis olcumler
        for tip, noktalar, _ in self._cizimler:
            self._ciz_tamamlandi(painter, tip, noktalar)

        # Aktif olcum
        if self._mevcut_noktalar:
            self._ciz_aktif(painter)

        painter.end()

    def _ciz_tamamlandi(self, painter: QPainter, tip: OlcuTipi, noktalar: list):
        if not noktalar:
            return
        renk = _MOD_RENK.get(tip, QColor("#333"))
        pen = QPen(renk, 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        if tip == OlcuTipi.UZUNLUK:
            for i in range(len(noktalar) - 1):
                painter.drawLine(
                    int(noktalar[i][0]), int(noktalar[i][1]),
                    int(noktalar[i+1][0]), int(noktalar[i+1][1])
                )
            for p in noktalar:
                painter.setBrush(QBrush(renk))
                painter.drawEllipse(int(p[0])-4, int(p[1])-4, 8, 8)

        elif tip == OlcuTipi.ALAN:
            if len(noktalar) >= 2:
                dolgu = QColor(renk)
                dolgu.setAlpha(40)
                painter.setBrush(QBrush(dolgu))
                from PyQt6.QtGui import QPolygon
                from PyQt6.QtCore import QPoint
                poly = QPolygon([QPoint(int(x), int(y)) for x, y in noktalar])
                painter.drawPolygon(poly)
            for p in noktalar:
                painter.setBrush(QBrush(renk))
                painter.drawEllipse(int(p[0])-4, int(p[1])-4, 8, 8)

        elif tip == OlcuTipi.SAYIM:
            painter.setBrush(QBrush(renk))
            for i, p in enumerate(noktalar):
                painter.drawEllipse(int(p[0])-6, int(p[1])-6, 12, 12)
                painter.setPen(QPen(Qt.GlobalColor.white, 1))
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.drawText(
                    QRect(int(p[0])-6, int(p[1])-6, 12, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    str(i + 1)
                )
                painter.setPen(pen)

    def _ciz_aktif(self, painter: QPainter):
        noktalar = self._mevcut_noktalar
        if self._mod == _ModTipi.KALIBRASYON:
            renk = _KALIBRASYON_RENK
        elif self._mod == _ModTipi.UZUNLUK:
            renk = _MOD_RENK[OlcuTipi.UZUNLUK]
        elif self._mod == _ModTipi.ALAN:
            renk = _MOD_RENK[OlcuTipi.ALAN]
        elif self._mod == _ModTipi.SAYIM:
            renk = _MOD_RENK[OlcuTipi.SAYIM]
        else:
            return

        pen = QPen(renk, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)

        for i in range(len(noktalar) - 1):
            painter.drawLine(
                int(noktalar[i][0]), int(noktalar[i][1]),
                int(noktalar[i+1][0]), int(noktalar[i+1][1])
            )

        # Fare pozisyonuna cizgi (rehber)
        if self._fare_pos and noktalar:
            painter.drawLine(
                int(noktalar[-1][0]), int(noktalar[-1][1]),
                self._fare_pos[0], self._fare_pos[1]
            )

        solid_pen = QPen(renk, 2)
        painter.setPen(solid_pen)
        painter.setBrush(QBrush(renk))
        for p in noktalar:
            painter.drawEllipse(int(p[0])-4, int(p[1])-4, 8, 8)

    # -- mouse --
    def mousePressEvent(self, event):
        if not self._pixmap:
            return
        pos = (event.pos().x(), event.pos().y())

        if event.button() == Qt.MouseButton.LeftButton:
            if self._mod == _ModTipi.KALIBRASYON:
                self._mevcut_noktalar.append(pos)
                if len(self._mevcut_noktalar) == 2:
                    self.kalibrasyon_bitti.emit(list(self._mevcut_noktalar))
                    self._mevcut_noktalar = []

            elif self._mod in (_ModTipi.UZUNLUK, _ModTipi.ALAN):
                self._mevcut_noktalar.append(pos)

            elif self._mod == _ModTipi.SAYIM:
                self._mevcut_noktalar.append(pos)
                self.sayim_nokta_eklendi.emit(list(self._mevcut_noktalar))

        elif event.button() == Qt.MouseButton.RightButton:
            self._olcumu_tamamla()

        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._olcumu_tamamla()

    def mouseMoveEvent(self, event):
        self._fare_pos = (event.pos().x(), event.pos().y())
        self.koordinat.emit(event.pos().x(), event.pos().y())
        if self._mevcut_noktalar:
            self.update()

    def _olcumu_tamamla(self):
        if self._mod == _ModTipi.UZUNLUK and len(self._mevcut_noktalar) >= 2:
            self.olcu_bitti.emit(OlcuTipi.UZUNLUK, list(self._mevcut_noktalar))
            self._mevcut_noktalar = []
        elif self._mod == _ModTipi.ALAN and len(self._mevcut_noktalar) >= 3:
            self.olcu_bitti.emit(OlcuTipi.ALAN, list(self._mevcut_noktalar))
            self._mevcut_noktalar = []
        elif self._mod == _ModTipi.SAYIM and self._mevcut_noktalar:
            self.olcu_bitti.emit(OlcuTipi.SAYIM, list(self._mevcut_noktalar))
            self._mevcut_noktalar = []
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._mevcut_noktalar = []
            self.update()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._olcumu_tamamla()
        else:
            super().keyPressEvent(event)

    def _guncelle_cursor(self):
        if self._mod == _ModTipi.BOSTA:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))


# ---------------------------------------------------------------------------
# Ana pencere
# ---------------------------------------------------------------------------
class PDFMetrajWindow(QMainWindow):
    """
    PDF plan uzerinde fare ile metraj alma penceresi.

    Neyi cozuyoruz?
      Kullanici elindeki PDF plan uzerinden uzunluk, alan veya sayim yapabilsin;
      sonuclari tabloda gorebilsin ve CSV'ye aktarabilsin.

    Nasil test ederiz?
      >>> from app.ui.pdf_metraj_window import PDFMetrajWindow
      >>> win = PDFMetrajWindow()
      >>> assert win.windowTitle() == "PDF Metraj"
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._engine = PDFMetrajEngine() if ENGINE_AVAILABLE else None
        self._mevcut_sayfa = 0
        self._zoom = 1.5
        self._aktif_mod = _ModTipi.BOSTA
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("PDF Metraj")
        self.setGeometry(100, 80, 1280, 820)
        self.setMinimumSize(900, 600)

        merkez = QWidget()
        self.setCentralWidget(merkez)
        ana = QVBoxLayout(merkez)
        ana.setContentsMargins(0, 0, 0, 0)
        ana.setSpacing(0)

        ana.addWidget(self._ust_aracligi())

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sol: PDF kanvas
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setStyleSheet("background: #555;")
        self._kanvas = _PDFKanvas()
        self._kanvas.kalibrasyon_bitti.connect(self._kalibrasyon_al)
        self._kanvas.olcu_bitti.connect(self._olcu_tamamlandi)
        self._kanvas.sayim_nokta_eklendi.connect(self._sayim_guncelle)
        self._kanvas.koordinat.connect(self._koordinat_goster)
        self._scroll.setWidget(self._kanvas)
        splitter.addWidget(self._scroll)

        # Sag: olcum paneli
        splitter.addWidget(self._sag_panel())
        splitter.setSizes([850, 380])
        splitter.setCollapsible(0, False)

        ana.addWidget(splitter, stretch=1)
        ana.addWidget(self._alt_durum())

        self._uygula_stil()

    def _ust_aracligi(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("ustAraclik")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # PDF ac
        ac_btn = QPushButton("PDF Ac")
        ac_btn.setObjectName("primaryBtn")
        ac_btn.setToolTip("PDF dosyasini ac")
        ac_btn.clicked.connect(self._pdf_ac)
        layout.addWidget(ac_btn)

        layout.addWidget(self._ayirici())

        # Sayfa navigasyon
        layout.addWidget(QLabel("Sayfa:"))
        self.sayfa_geri_btn = QPushButton("<")
        self.sayfa_geri_btn.setFixedWidth(30)
        self.sayfa_geri_btn.clicked.connect(self._onceki_sayfa)
        layout.addWidget(self.sayfa_geri_btn)

        self.sayfa_label = QLabel("0 / 0")
        self.sayfa_label.setFixedWidth(70)
        self.sayfa_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sayfa_label)

        self.sayfa_ileri_btn = QPushButton(">")
        self.sayfa_ileri_btn.setFixedWidth(30)
        self.sayfa_ileri_btn.clicked.connect(self._sonraki_sayfa)
        layout.addWidget(self.sayfa_ileri_btn)

        layout.addWidget(self._ayirici())

        # Zoom
        layout.addWidget(QLabel("Zoom:"))
        self.zoom_combo = QComboBox()
        for z in ["75%", "100%", "125%", "150%", "175%", "200%"]:
            self.zoom_combo.addItem(z)
        self.zoom_combo.setCurrentIndex(3)
        self.zoom_combo.setFixedWidth(70)
        self.zoom_combo.currentTextChanged.connect(self._zoom_degisti)
        layout.addWidget(self.zoom_combo)

        layout.addWidget(self._ayirici())

        # Olcum modlari
        kalibrasyon_btn = QPushButton("Olcek Kalibrasyon")
        kalibrasyon_btn.setObjectName("modBtn")
        kalibrasyon_btn.setCheckable(True)
        kalibrasyon_btn.setToolTip(
            "2 nokta sec, aralarindaki gercek mesafeyi gir → olcek ayarlanir"
        )
        kalibrasyon_btn.clicked.connect(lambda: self._mod_sec(_ModTipi.KALIBRASYON, kalibrasyon_btn))
        layout.addWidget(kalibrasyon_btn)
        self._kalibrasyon_btn = kalibrasyon_btn

        uzunluk_btn = QPushButton("Uzunluk")
        uzunluk_btn.setObjectName("modBtn")
        uzunluk_btn.setCheckable(True)
        uzunluk_btn.setToolTip(
            "Tikla → noktalar ekle → cift-tik veya sag-tik ile tamamla"
        )
        uzunluk_btn.clicked.connect(lambda: self._mod_sec(_ModTipi.UZUNLUK, uzunluk_btn))
        layout.addWidget(uzunluk_btn)
        self._uzunluk_btn = uzunluk_btn

        alan_btn = QPushButton("Alan")
        alan_btn.setObjectName("modBtn")
        alan_btn.setCheckable(True)
        alan_btn.setToolTip(
            "3+ nokta ile polygon ciz → cift-tik veya sag-tik ile tamamla"
        )
        alan_btn.clicked.connect(lambda: self._mod_sec(_ModTipi.ALAN, alan_btn))
        layout.addWidget(alan_btn)
        self._alan_btn = alan_btn

        sayim_btn = QPushButton("Sayim")
        sayim_btn.setObjectName("modBtn")
        sayim_btn.setCheckable(True)
        sayim_btn.setToolTip(
            "Her tiklama bir birim sayar → sag-tik ile tamamla"
        )
        sayim_btn.clicked.connect(lambda: self._mod_sec(_ModTipi.SAYIM, sayim_btn))
        layout.addWidget(sayim_btn)
        self._sayim_btn = sayim_btn

        self._mod_butonlari = [kalibrasyon_btn, uzunluk_btn, alan_btn, sayim_btn]

        layout.addWidget(self._ayirici())

        # Iptal
        iptal_btn = QPushButton("Iptal (Esc)")
        iptal_btn.setToolTip("Mevcut olcumu iptal et")
        iptal_btn.clicked.connect(self._iptal)
        layout.addWidget(iptal_btn)

        layout.addStretch()

        # Olcek gostergesi
        self.olcek_label = QLabel("Olcek: ayarlanmadi")
        self.olcek_label.setStyleSheet(
            "color: #c0392b; font-weight: bold; font-size: 11px;"
        )
        layout.addWidget(self.olcek_label)

        layout.addWidget(self._ayirici())

        # CSV
        csv_btn = QPushButton("CSV Aktar")
        csv_btn.setToolTip("Olcumleri CSV olarak kaydet")
        csv_btn.clicked.connect(self._csv_aktar)
        layout.addWidget(csv_btn)

        yardim_btn = QPushButton("? Yardim")
        yardim_btn.clicked.connect(self._yardim_goster)
        layout.addWidget(yardim_btn)

        return panel

    def _sag_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        baslik = QLabel("Olcum Listesi")
        baslik.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        baslik.setStyleSheet("color: #1a3a5c;")
        layout.addWidget(baslik)

        self.olcu_tablo = QTableWidget(0, 5)
        self.olcu_tablo.setHorizontalHeaderLabels([
            "No", "Tip", "Deger", "Birim", "Aciklama"
        ])
        self.olcu_tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.olcu_tablo.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.olcu_tablo.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Fixed
        )
        self.olcu_tablo.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Fixed
        )
        self.olcu_tablo.setColumnWidth(0, 36)
        self.olcu_tablo.setColumnWidth(2, 80)
        self.olcu_tablo.setColumnWidth(3, 52)
        self.olcu_tablo.verticalHeader().setVisible(False)
        self.olcu_tablo.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.olcu_tablo.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.olcu_tablo.setAlternatingRowColors(True)
        layout.addWidget(self.olcu_tablo, stretch=1)

        # Tablo alt butonlar
        tablo_btn_layout = QHBoxLayout()
        sil_btn = QPushButton("Secili Sil")
        sil_btn.clicked.connect(self._olcu_sil)
        sil_btn.setToolTip("Secili olcumu sil")
        tablo_btn_layout.addWidget(sil_btn)

        hepsini_sil_btn = QPushButton("Tümünü Sil")
        hepsini_sil_btn.clicked.connect(self._tum_olculeri_sil)
        tablo_btn_layout.addWidget(hepsini_sil_btn)
        layout.addLayout(tablo_btn_layout)

        # Ozet
        ozet_group = QGroupBox("Ozet")
        ozet_layout = QFormLayout(ozet_group)
        ozet_layout.setSpacing(6)

        self.ozet_uzunluk = QLabel("--")
        self.ozet_uzunluk.setStyleSheet("font-weight: bold; color: #e74c3c;")
        ozet_layout.addRow("Toplam Uzunluk:", self.ozet_uzunluk)

        self.ozet_alan = QLabel("--")
        self.ozet_alan.setStyleSheet("font-weight: bold; color: #2980b9;")
        ozet_layout.addRow("Toplam Alan:", self.ozet_alan)

        self.ozet_sayim = QLabel("--")
        self.ozet_sayim.setStyleSheet("font-weight: bold; color: #27ae60;")
        ozet_layout.addRow("Toplam Sayim:", self.ozet_sayim)

        layout.addWidget(ozet_group)

        return panel

    def _alt_durum(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("altDurum")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)

        self.durum_label = QLabel("PDF dosyasi acin.")
        self.durum_label.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(self.durum_label)

        layout.addStretch()

        self.koordinat_label = QLabel("X: -- Y: --")
        self.koordinat_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.koordinat_label)

        self.mod_durum_label = QLabel("Mod: --")
        self.mod_durum_label.setStyleSheet(
            "color: #1a3a5c; font-weight: bold; font-size: 11px; margin-left: 16px;"
        )
        layout.addWidget(self.mod_durum_label)

        return frame

    def _ayirici(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setFrameShadow(QFrame.Shadow.Sunken)
        return f

    # ------------------------------------------------------------------
    # Slotlar
    # ------------------------------------------------------------------
    def _pdf_ac(self):
        if not ENGINE_AVAILABLE:
            QMessageBox.critical(
                self, "Hata",
                "PDF motor yuklenemedi. PyMuPDF (fitz) kurulu degil.\n"
                "Kurmak icin: pip install PyMuPDF"
            )
            return

        dosya, _ = QFileDialog.getOpenFileName(
            self, "PDF Dosyasi Ac", "", "PDF Dosyalari (*.pdf);;Tum Dosyalar (*)"
        )
        if not dosya:
            return

        if not self._engine.pdf_yukle(dosya):
            QMessageBox.critical(self, "Hata", "PDF yuklenemedi.")
            return

        self._mevcut_sayfa = 0
        self._sayfa_render()
        self.durum_label.setText(
            f"Yuklu: {dosya.split('/')[-1].split(chr(92))[-1]} "
            f"({self._engine.sayfa_sayisi()} sayfa)"
        )

    def _sayfa_render(self):
        if not self._engine:
            return
        img = self._engine.sayfa_render(self._mevcut_sayfa, self._zoom)
        if img is None:
            return
        pixmap = QPixmap.fromImage(img)
        self._kanvas.pixmap_goster(pixmap)
        toplam = self._engine.sayfa_sayisi()
        self.sayfa_label.setText(f"{self._mevcut_sayfa + 1} / {toplam}")
        self.sayfa_geri_btn.setEnabled(self._mevcut_sayfa > 0)
        self.sayfa_ileri_btn.setEnabled(self._mevcut_sayfa < toplam - 1)

    def _onceki_sayfa(self):
        if self._mevcut_sayfa > 0:
            self._mevcut_sayfa -= 1
            self._sayfa_render()

    def _sonraki_sayfa(self):
        if self._engine and self._mevcut_sayfa < self._engine.sayfa_sayisi() - 1:
            self._mevcut_sayfa += 1
            self._sayfa_render()

    def _zoom_degisti(self, metin: str):
        try:
            self._zoom = float(metin.replace("%", "")) / 100.0
            if self._engine and self._engine.sayfa_sayisi() > 0:
                self._sayfa_render()
        except ValueError:
            pass

    def _mod_sec(self, mod: _ModTipi, kaynak_btn):
        if not self._engine or self._engine.sayfa_sayisi() == 0:
            kaynak_btn.setChecked(False)
            QMessageBox.information(self, "Bilgi", "Once bir PDF dosyasi acin.")
            return

        if self._aktif_mod == mod and kaynak_btn.isChecked() is False:
            self._aktif_mod = _ModTipi.BOSTA
            self._kanvas.mod_sec(_ModTipi.BOSTA)
            self.mod_durum_label.setText("Mod: --")
            return

        self._aktif_mod = mod
        self._kanvas.mod_sec(mod)
        for btn in self._mod_butonlari:
            btn.setChecked(btn is kaynak_btn)

        mod_aciklama = {
            _ModTipi.KALIBRASYON: "Kalibrasyon: 2 nokta sec",
            _ModTipi.UZUNLUK:    "Uzunluk: noktalar tikla, cift-tik ile tamamla",
            _ModTipi.ALAN:       "Alan: polygon ciz, cift-tik ile tamamla",
            _ModTipi.SAYIM:      "Sayim: tikla, sag-tik ile tamamla",
        }
        self.mod_durum_label.setText(f"Mod: {mod_aciklama.get(mod, '--')}")

        if mod == _ModTipi.UZUNLUK and not self._engine.olcek_var_mi():
            self.durum_label.setText(
                "Uyari: Olcek kalibre edilmedi! Once 'Olcek Kalibrasyon' yapmayi unuttunuz mu?"
            )

    def _kalibrasyon_al(self, noktalar: list):
        mesafe, tamam = QInputDialog.getDouble(
            self, "Olcek Kalibrasyonu",
            "Secilen 2 nokta arasindaki GERCEK mesafe (metre):",
            value=1.0, min=0.001, max=9999.0, decimals=3
        )
        if not tamam or mesafe <= 0:
            self.durum_label.setText("Kalibrasyon iptal edildi.")
            return

        self._engine.olcek_ayarla(noktalar[0], noktalar[1], mesafe)
        self.olcek_label.setText(
            f"Olcek: {self._engine._olcek_px_per_m:.2f} px/m"
        )
        self.olcek_label.setStyleSheet(
            "color: #1a6b3a; font-weight: bold; font-size: 11px;"
        )
        self.durum_label.setText(
            f"Olcek kalibre edildi: {mesafe:.3f} m = {noktalar} piksel arasi"
        )

        # Kalibrasyonu bitir, modu sifirla
        self._aktif_mod = _ModTipi.BOSTA
        self._kanvas.mod_sec(_ModTipi.BOSTA)
        for btn in self._mod_butonlari:
            btn.setChecked(False)
        self.mod_durum_label.setText("Mod: --")

    def _olcu_tamamlandi(self, tip: OlcuTipi, noktalar: list):
        if not self._engine.olcek_var_mi() and tip != OlcuTipi.SAYIM:
            QMessageBox.warning(
                self, "Uyari",
                "Olcek kalibre edilmedi!\n"
                "Once 'Olcek Kalibrasyon' modunu kullanin."
            )
            return

        aciklama, tamam = QInputDialog.getText(
            self, "Olcum Aciklamasi",
            "Aciklama (opsiyonel, Enter ile atla):"
        )
        if not tamam:
            aciklama = ""

        try:
            olcu = self._engine.olcu_ekle(tip, noktalar, aciklama)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Hata", str(exc))
            return

        self._kanvas.cizim_ekle(tip, noktalar, aciklama)
        self._tabloya_ekle(olcu)
        self._ozet_guncelle()
        self.durum_label.setText(
            f"Olcum #{olcu.id}: {olcu.gercek_deger:.4f} {olcu.birim}"
        )

    def _sayim_guncelle(self, noktalar: list):
        self.durum_label.setText(
            f"Sayim: {len(noktalar)} adet sayildi (sag-tik ile tamamla)"
        )

    def _tabloya_ekle(self, olcu: Olcu):
        satir = self.olcu_tablo.rowCount()
        self.olcu_tablo.insertRow(satir)

        tip_metinler = {
            OlcuTipi.UZUNLUK: "Uzunluk",
            OlcuTipi.ALAN:    "Alan",
            OlcuTipi.SAYIM:   "Sayim",
        }
        tip_renkler = {
            OlcuTipi.UZUNLUK: QColor("#fde8e8"),
            OlcuTipi.ALAN:    QColor("#dbeafe"),
            OlcuTipi.SAYIM:   QColor("#d5f5e3"),
        }

        def item(metin, renk=None):
            it = QTableWidgetItem(str(metin))
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if renk:
                it.setBackground(renk)
            return it

        renk = tip_renkler.get(olcu.tip)
        self.olcu_tablo.setItem(satir, 0, item(str(olcu.id), renk))
        self.olcu_tablo.setItem(satir, 1, item(tip_metinler.get(olcu.tip, "--"), renk))
        self.olcu_tablo.setItem(satir, 2, item(f"{olcu.gercek_deger:.4f}", renk))
        self.olcu_tablo.setItem(satir, 3, item(olcu.birim, renk))

        aciklama_item = QTableWidgetItem(olcu.aciklama)
        aciklama_item.setFlags(aciklama_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if renk:
            aciklama_item.setBackground(renk)
        self.olcu_tablo.setItem(satir, 4, aciklama_item)
        self.olcu_tablo.scrollToBottom()

    def _olcu_sil(self):
        secili = self.olcu_tablo.currentRow()
        if secili < 0:
            return
        id_item = self.olcu_tablo.item(secili, 0)
        if id_item:
            try:
                olcu_id = int(id_item.text())
                self._engine.olcu_sil(olcu_id)
            except (ValueError, AttributeError):
                pass
        self.olcu_tablo.removeRow(secili)
        self._kanvas.tum_cizimleri_sil()
        # Kalan olculeri tekrar ciz
        for olcu in self._engine.olcu_listesi_al():
            self._kanvas.cizim_ekle(olcu.tip, olcu.noktalar, olcu.aciklama)
        self._ozet_guncelle()

    def _tum_olculeri_sil(self):
        cevap = QMessageBox.question(
            self, "Onay", "Tum olcumler silinecek. Devam?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return
        if self._engine:
            self._engine.olculeri_temizle()
        self._kanvas.tum_cizimleri_sil()
        self.olcu_tablo.setRowCount(0)
        self._ozet_guncelle()

    def _iptal(self):
        self._kanvas.aktif_iptal()
        self.durum_label.setText("Aktif olcum iptal edildi.")

    def _ozet_guncelle(self):
        if not self._engine:
            return
        olcumler = self._engine.olcu_listesi_al()
        toplam_uzunluk = sum(
            o.gercek_deger for o in olcumler if o.tip == OlcuTipi.UZUNLUK
        )
        toplam_alan = sum(
            o.gercek_deger for o in olcumler if o.tip == OlcuTipi.ALAN
        )
        toplam_sayim = sum(
            o.gercek_deger for o in olcumler if o.tip == OlcuTipi.SAYIM
        )
        self.ozet_uzunluk.setText(
            f"{toplam_uzunluk:.3f} m" if toplam_uzunluk > 0 else "--"
        )
        self.ozet_alan.setText(
            f"{toplam_alan:.4f} m2" if toplam_alan > 0 else "--"
        )
        self.ozet_sayim.setText(
            f"{int(toplam_sayim)} adet" if toplam_sayim > 0 else "--"
        )

    def _koordinat_goster(self, x: int, y: int):
        self.koordinat_label.setText(f"X: {x}  Y: {y}")

    def _csv_aktar(self):
        if not self._engine or not self._engine.olcu_listesi_al():
            QMessageBox.information(self, "Bilgi", "Aktarilacak olcum yok.")
            return
        try:
            import csv
            import datetime
            dosya, _ = QFileDialog.getSaveFileName(
                self, "CSV Kaydet", "", "CSV Dosyasi (*.csv);;Tum Dosyalar (*)"
            )
            if not dosya:
                return
            with open(dosya, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["INSAAT METRAJ PRO — PDF Metraj Raporu"])
                w.writerow(["Tarih:", datetime.date.today().strftime("%d/%m/%Y")])
                w.writerow([])
                w.writerow(["No", "Tip", "Deger", "Birim", "Aciklama"])
                tip_metinler = {
                    OlcuTipi.UZUNLUK: "Uzunluk",
                    OlcuTipi.ALAN:    "Alan",
                    OlcuTipi.SAYIM:   "Sayim",
                }
                for o in self._engine.olcu_listesi_al():
                    w.writerow([
                        o.id,
                        tip_metinler.get(o.tip, "--"),
                        f"{o.gercek_deger:.4f}",
                        o.birim,
                        o.aciklama,
                    ])
                w.writerow([])
                w.writerow(["TOPLAM UZUNLUK:", self.ozet_uzunluk.text()])
                w.writerow(["TOPLAM ALAN:",    self.ozet_alan.text()])
                w.writerow(["TOPLAM SAYIM:",   self.ozet_sayim.text()])
            QMessageBox.information(self, "Basarili", f"Kaydedildi:\n{dosya}")
            self.durum_label.setText(f"CSV aktarildi: {dosya}")
        except Exception as hata:
            QMessageBox.critical(self, "Hata", f"Aktarim hatasi:\n{hata}")

    def _yardim_goster(self):
        QMessageBox.information(
            self, "PDF Metraj — Kullanim Kilavuzu",
            "PDF METRAJ KULLANIM KILAVUZU\n"
            "==============================\n\n"
            "1. 'PDF Ac' ile plan dosyasini yukleyin.\n\n"
            "2. OLCEK KALIBRASYON (zorunlu, sayim haric):\n"
            "   - 'Olcek Kalibrasyon' butonuna basin.\n"
            "   - Planda uzunlugunu bildiginiz bir cizginin "
            "iki ucuna tiklayin.\n"
            "   - Gercek mesafeyi (metre) girin → olcek ayarlanir.\n\n"
            "3. UZUNLUK OLCUMU:\n"
            "   - 'Uzunluk' butonuna basin.\n"
            "   - Ardindan planda noktalara tiklayin (polyline).\n"
            "   - Cift-tik veya sag-tik ile tamamlayin.\n\n"
            "4. ALAN OLCUMU:\n"
            "   - 'Alan' butonuna basin.\n"
            "   - 3+ nokta ile polygon cizin.\n"
            "   - Cift-tik veya sag-tik ile tamamlayin.\n\n"
            "5. SAYIM:\n"
            "   - 'Sayim' butonuna basin.\n"
            "   - Her tiklama 1 birim sayar.\n"
            "   - Sag-tik ile grubu tamamlayin.\n\n"
            "6. Esc = aktif olcumu iptal et.\n"
            "7. 'CSV Aktar' ile sonuclari disa aktarin.\n\n"
            "Renk kodu: kirmizi=uzunluk, mavi=alan, yesil=sayim"
        )

    # ------------------------------------------------------------------
    # Stil
    # ------------------------------------------------------------------
    def _uygula_stil(self):
        self.setStyleSheet("""
            QMainWindow { background: #f5f7fa; }
            QWidget#ustAraclik {
                background: #1a3a5c;
                border-bottom: 2px solid #0d2137;
            }
            QWidget#ustAraclik QLabel { color: #cde; font-size: 12px; }
            QWidget#ustAraclik QPushButton {
                background: #2e5d8e;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-weight: bold;
            }
            QWidget#ustAraclik QPushButton:hover { background: #3a74b0; }
            QWidget#ustAraclik QPushButton#primaryBtn { background: #1a6b3a; }
            QWidget#ustAraclik QPushButton#primaryBtn:hover { background: #145a2f; }
            QWidget#ustAraclik QPushButton#modBtn:checked {
                background: #e67e22;
                color: white;
            }
            QWidget#ustAraclik QComboBox {
                background: #2e5d8e;
                color: white;
                border: 1px solid #4a8ac4;
                border-radius: 3px;
                padding: 3px 6px;
            }
            QFrame#altDurum {
                background: #f0f4f8;
                border-top: 1px solid #c8d6e5;
                max-height: 28px;
            }
            QGroupBox {
                font-weight: bold;
                color: #1a3a5c;
                border: 1px solid #c8d6e5;
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
                left: 10px;
            }
            QTableWidget {
                gridline-color: #d5e8f0;
                selection-background-color: #b3d1e8;
            }
            QHeaderView::section {
                background: #1a3a5c;
                color: white;
                padding: 4px;
                font-weight: bold;
                border: none;
            }
            QPushButton {
                background: #5d8aa8;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #4a7a96; }
        """)

    def closeEvent(self, event):
        if self._engine:
            self._engine.kapat()
        super().closeEvent(event)
