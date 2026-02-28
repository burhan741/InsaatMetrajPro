"""
İnce İşler 3D Önizleme Widget
==============================
Matplotlib mpl_toolkits.mplot3d + Poly3DCollection ile
oda yüzeylerini materyal rengiyle dark temada çizer.

Layout (InceIsler3DPanel):
┌────────────────────────────────────────────────────┐
│ 3D Önizleme [Temizle] [Yenile] │ ← başlık + butonlar
├────────────────────────┬───────────────────────────┤
│ Oda Listesi │ 3D Canvas │
│ ───────────────── │ (matplotlib 3D) │
│ Salon 25m² [] │ │
│ Yatak 18m² [] │ ← mouse döndürme │
│ Banyo 6m² [] │ │
│ [+ AutoCAD'den Ekle] │ │
├────────────────────────┴───────────────────────────┤
│ Legend: ■ Parke ■ Fayans ■ Şap ■ Boya │
└────────────────────────────────────────────────────┘

Neyi çözer?
Kullanıcı metraj işlemi yaparken hangi odaya ne malzeme
hesapladığını 3D görsel ile anında doğrular.
"Salon fayans çıktı ama parke olacaktı" hatası görsel tespiti.

Nasıl test edilir?
panel = InceIsler3DPanel()
panel.show()
# sap_eslestirme ile otomatik:
panel.load_from_sap([{"mahal_adi": "Salon", "deger": 25}], 2.80)
"""

import logging
from typing import List, Optional, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QListWidget, QListWidgetItem, QComboBox,
    QGroupBox, QScrollArea, QDialog, QLineEdit, QDialogButtonBox,
    QFrame, QGridLayout, QSizePolicy, QColorDialog, QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

logger = logging.getLogger(__name__)

# ── İç import ─────────────────────────────────────────────────────────────
try:
    from app.core.room_3d_builder import (
        Room3DBuilder, Oda3D, ZEMIN_MALZEMELERI, DUVAR_MALZEMELERI,
        DisCepheBuilder, DisCephe3D, CEPHE_MALZEMELERI,
    )
    _BUILDER_OK = True
except ImportError:
    _BUILDER_OK = False
    Room3DBuilder = None
    Oda3D = None
    DisCepheBuilder = None
    DisCephe3D = None
    ZEMIN_MALZEMELERI = ["Laminat Parke", "Yer Fayansı + Derz", "Şap Çimentosu"]
    DUVAR_MALZEMELERI = ["Duvar Boyası", "Duvar Fayansı + Derz", "Saten Alçı"]
    CEPHE_MALZEMELERI = ["Cephe Boyası (Beyaz)", "Mantolama (EPS Karbonlu)"]

try:
    from app.data.malzeme_renkleri import MALZEME_RENKLERI
    _MALZEME_RENK_OK = True
except ImportError:
    _MALZEME_RENK_OK = False
    MALZEME_RENKLERI = {}

# ── Matplotlib 3D ──────────────────────────────────────────────────────────
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import numpy as np
    _MPL_OK = True
except ImportError:
    _MPL_OK = False

# ── Dark Tema Sabitleri ─────────────────────────────────────────────────────
_BG = "#1a1a2e"
_AX = "#16213e"
_GRID = "#2a3a5a"
_TEXT = "#d4d4d4"
_TITLE = "#e0e0e0"
_CYAN = "#00BFFF"


# ══════════════════════════════════════════════════════════════════════════════
# InceIsler3DWidget — saf matplotlib canvas
# ══════════════════════════════════════════════════════════════════════════════

class InceIsler3DWidget(QWidget):
    """
    Matplotlib mpl_toolkits.mplot3d canvas'ı.
    Dışarıdan Oda3D listesi verilir, Poly3DCollection ile çizer.

    Kullanım:
    widget = InceIsler3DWidget()
    widget.load_rooms(oda_listesi) # → 3D render
    widget.reset() # → canvas temizle
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._rooms: List = []
        self._dis_cephe = None
        self._show_dis_cephe: bool = False
        self._mpl_ok = _MPL_OK and _BUILDER_OK
        self._init_canvas()

    # ── Canvas Kurulumu ────────────────────────────────────────────────

    def _init_canvas(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not self._mpl_ok:
            warn = QLabel(
                " 3D görselleştirme için matplotlib ve\n"
                "mpl_toolkits.mplot3d gereklidir.\n\n"
                "pip install matplotlib"
            )
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            warn.setStyleSheet(
                f"color: #888888; font-size: 11pt; background: {_BG}; padding: 30px;"
            )
            layout.addWidget(warn)
            return

        self.fig = Figure(figsize=(9, 6), facecolor=_BG)
        self.ax = self.fig.add_subplot(111, projection="3d")
        self._apply_dark()

        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setStyleSheet(
            f"background-color: {_BG}; border-radius: 6px;"
            f" border: 1px solid {_GRID};"
        )
        layout.addWidget(self.canvas)

        ipucu = QLabel(" Sürükle: döndür | Kaydır: zoom")
        ipucu.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ipucu.setStyleSheet(
            f"color: #556677; font-size: 8pt; background: transparent; padding: 2px;"
        )
        layout.addWidget(ipucu)

    def _apply_dark(self):
        """3D axes'e dark tema uygula."""
        if not self._mpl_ok:
            return
        self.ax.set_facecolor(_AX)
        self.fig.patch.set_facecolor(_BG)

        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            axis.label.set_color(_TEXT)
            axis.pane.fill = False
            axis.pane.set_edgecolor(_GRID)

        self.ax.tick_params(colors="#888888", labelsize=7)
        self.ax.grid(True, color=_GRID, alpha=0.25, linestyle="--")

    # ── Public API ─────────────────────────────────────────────────────

    def load_rooms(self, rooms: list):
        """Oda3D listesini al ve 3D çiz."""
        if not self._mpl_ok:
            return
        self._rooms = rooms
        self._redraw()

    def reset(self):
        """Canvas'ı temizle."""
        self._rooms = []
        if self._mpl_ok:
            self.ax.cla()
            self._apply_dark()
            self.ax.text2D(
                0.5, 0.5,
                "3D Önizleme Bekleniyor…",
                transform=self.ax.transAxes,
                ha="center", va="center",
                fontsize=12, color="#556677"
            )
            self.canvas.draw()

    # ── Render ─────────────────────────────────────────────────────────

    def _redraw(self):
        """Tüm oda listesini Poly3DCollection ile çiz."""
        if not self._mpl_ok:
            return

        self.ax.cla()
        self._apply_dark()

        if not self._rooms:
            self.ax.text2D(
                0.5, 0.5,
                "Oda verisi yok.\nHesapla butonuna tıklayın.",
                transform=self.ax.transAxes,
                ha="center", va="center",
                fontsize=11, color="#556677"
            )
            self.canvas.draw()
            return

        all_x, all_y, all_z = [], [], []

        for room in self._rooms:
            for yuzey in room.yuzeyler:
                verts = [yuzey.vertices]
                rgba = yuzey.rgba

                poly = Poly3DCollection(
                    verts,
                    facecolor=rgba[:3],
                    alpha=float(rgba[3]),
                    edgecolor=_BG,
                    linewidth=0.4,
                    zorder=2 if yuzey.surface_type == "ZEMIN" else 1,
                )
                self.ax.add_collection3d(poly)

                for v in yuzey.vertices:
                    all_x.append(v[0])
                    all_y.append(v[1])
                    all_z.append(v[2])

            # ─ Oda etiketi (centroid, tavan üstü +10 cm) ─
            mx, my = room.merkez
            mz = room.yukseklik * 100.0 + 15.0
            self.ax.text(
                mx, my, mz,
                room.oda_adi,
                fontsize=7.5, color=_TITLE,
                ha="center", va="bottom",
                fontweight="bold",
                zorder=10,
            )

            # ─ Alan etiketi (zemin üstü +5 cm) ─
            self.ax.text(
                mx, my, 5.0,
                f"{room.alan:.1f} m²",
                fontsize=6.5, color="#aaaaaa",
                ha="center", va="bottom",
                zorder=10,
            )

        # ─ Axes sınırları ─
        if all_x:
            pad = 30.0
            self.ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
            self.ax.set_ylim(min(all_y) - pad, max(all_y) + pad)
            self.ax.set_zlim(0, max(all_z) + pad)

        # ─ Başlık ─
        n_oda = len(self._rooms)
        total_m2 = sum(r.alan for r in self._rooms)
        self.ax.set_title(
            f"{n_oda} Oda | Toplam: {total_m2:.1f} m²",
            fontsize=9, color=_TITLE, pad=10,
        )

        self.ax.set_xlabel("X (cm)", fontsize=7, color="#888888")
        self.ax.set_ylabel("Y (cm)", fontsize=7, color="#888888")
        self.ax.set_zlabel("Z (cm)", fontsize=7, color="#888888")

        # ─ Görüş açısı ─
        self.ax.view_init(elev=28, azim=-55)

        self.fig.tight_layout(pad=1.0)
        self.canvas.draw()


# ══════════════════════════════════════════════════════════════════════════════
# OdaSatiri — oda listesindeki tek satır (ad + alan + malzeme combo)
# ══════════════════════════════════════════════════════════════════════════════

class OdaSatiri(QWidget):
    """
    Oda listesi için tek satır widget.

    İçerir: renk göstergesi | oda adı | alan | malzeme combo | renk seçici
    Sinyaller:
    malzeme_degisti(oda_adi, malzeme_str)
    renk_degisti(oda_adi, rgba_tuple) ← kullanıcı özel renk seçerse
    """

    malzeme_degisti = pyqtSignal(str, str)  # (oda_adi, yeni_malzeme)
    renk_degisti = pyqtSignal(str, tuple)   # (oda_adi, (r,g,b,a) 0-1 arası)

    # Malzeme adı → varsayılan hex renk
    _MALZEME_RENK_MAP = {
        "Laminat Parke": "#8B5E3C",
        "Yer Fayansı + Derz": "#2196F3",
        "Şap Çimentosu": "#9E9E9E",
        "Tezgah Arası Seramik": "#FF9800",
        "Duvar Boyası": "#EEEEEE",
        "Duvar Fayansı + Derz": "#00BCD4",
    }

    def __init__(self, oda_adi: str, alan: float, zemin_malzeme: str,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.oda_adi = oda_adi
        self._ozel_renk: Optional[tuple] = None  # (r,g,b,a) kullanıcı seçimi

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(5)

        # ── Renkli gösterge küpü ─────────────────────────────────────
        self._renk_kutu = QLabel("■")
        self._renk_kutu.setFixedWidth(14)
        self._renk_kutu.setStyleSheet(
            f"color: {self._malzeme_renk(zemin_malzeme)};"
        )
        layout.addWidget(self._renk_kutu)

        # ── Oda adı ──────────────────────────────────────────────────
        isim_lbl = QLabel(oda_adi)
        isim_lbl.setFixedWidth(100)
        isim_lbl.setStyleSheet(
            "font-weight: bold; color: #e0e0e0; font-size: 9pt;"
        )
        layout.addWidget(isim_lbl)

        # ── Alan ─────────────────────────────────────────────────────
        alan_lbl = QLabel(f"{alan:.1f} m²")
        alan_lbl.setFixedWidth(50)
        alan_lbl.setStyleSheet("color: #aaaaaa; font-size: 8pt;")
        layout.addWidget(alan_lbl)

        # ── Malzeme combo ─────────────────────────────────────────────
        self.malzeme_combo = QComboBox()
        self.malzeme_combo.addItems(ZEMIN_MALZEMELERI)
        if zemin_malzeme in ZEMIN_MALZEMELERI:
            self.malzeme_combo.setCurrentText(zemin_malzeme)
        self.malzeme_combo.setFixedWidth(155)
        self.malzeme_combo.currentTextChanged.connect(self._on_malzeme_change)
        layout.addWidget(self.malzeme_combo)

        # ── Özel renk seçici buton ────────────────────────────────
        baslangic_hex = self._malzeme_renk(zemin_malzeme)
        self._renk_btn = QPushButton("")
        self._renk_btn.setFixedSize(26, 26)
        self._renk_btn.setToolTip(
            "Özel renk seç\n"
            "Bu odanın 3D zemin rengini istediğin renkle değiştir."
        )
        self._renk_btn.setStyleSheet(
            f"QPushButton {{ background: {baslangic_hex}; "
            f"border: 1px solid #555; border-radius: 4px; font-size: 11pt; }}"
            f"QPushButton:hover {{ border: 2px solid #00BFFF; }}"
        )
        self._renk_btn.clicked.connect(self._renk_sec)
        layout.addWidget(self._renk_btn)

    # ── Yardımcılar ────────────────────────────────────────────────────────

    @classmethod
    def _malzeme_renk(cls, malzeme: str) -> str:
        """Malzeme adından hex renk kodu."""
        return cls._MALZEME_RENK_MAP.get(malzeme, "#BBBBBB")

    @staticmethod
    def _hex_to_rgba01(hex_str: str, alpha: float = 0.90) -> tuple:
        """'#RRGGBB' → (r, g, b, a) 0.0-1.0 arası."""
        h = hex_str.lstrip("#")
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return (r, g, b, alpha)

    # ── Olay İşleyicileri ──────────────────────────────────────────────────

    def _on_malzeme_change(self, yeni: str):
        """Malzeme combo değişti → göstergeyi güncelle, sinyali gönder."""
        self._renk_kutu.setStyleSheet(f"color: {self._malzeme_renk(yeni)};")
        # Özel renk seçilmemişse buton rengini de güncelle
        if self._ozel_renk is None:
            self._renk_btn.setStyleSheet(
                f"QPushButton {{ background: {self._malzeme_renk(yeni)}; "
                f"border: 1px solid #555; border-radius: 4px; font-size: 11pt; }}"
                f"QPushButton:hover {{ border: 2px solid #00BFFF; }}"
            )
        self.malzeme_degisti.emit(self.oda_adi, yeni)

    def _renk_sec(self):
        """Renk butonuna tıklandı → QColorDialog aç, seçilen rengi 3D'ye yansıt."""
        # Başlangıç rengi: özel renk varsa onu, yoksa malzeme varsayılanı
        if self._ozel_renk:
            r, g, b, a = self._ozel_renk
            baslangic = QColor(
                int(r * 255), int(g * 255),
                int(b * 255), int(a * 255)
            )
        else:
            baslangic = QColor(self._malzeme_renk(self.malzeme_combo.currentText()))

        secilen = QColorDialog.getColor(
            baslangic,
            self,
            f"'{self.oda_adi}' — Zemin Rengi Seç",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )

        if not secilen.isValid():
            return  # kullanıcı iptal etti

        # Rengi sakla ve buton + göstergeyi güncelle
        self._ozel_renk = (
            secilen.redF(),
            secilen.greenF(),
            secilen.blueF(),
            max(secilen.alphaF(), 0.50),  # alpha min 0.5 (görünürlük)
        )
        hex_str = secilen.name()
        self._renk_btn.setStyleSheet(
            f"QPushButton {{ background: {hex_str}; "
            f"border: 2px solid #00BFFF; border-radius: 4px; font-size: 11pt; }}"
            f"QPushButton:hover {{ border: 2px solid #4FC3F7; }}"
        )
        self._renk_kutu.setStyleSheet(f"color: {hex_str};")

        # Sinyali gönder → InceIsler3DPanel dinler ve 3D'yi günceller
        self.renk_degisti.emit(self.oda_adi, self._ozel_renk)

    # ── Public ─────────────────────────────────────────────────────────

    def get_malzeme(self) -> str:
        return self.malzeme_combo.currentText()

    def get_ozel_renk(self) -> Optional[tuple]:
        """Kullanıcı özel renk seçtiyse (r,g,b,a) döndür, yoksa None."""
        return self._ozel_renk


# ══════════════════════════════════════════════════════════════════════════════
# InceIsler3DPanel — tam panel (kontroller + canvas + legend)
# ══════════════════════════════════════════════════════════════════════════════

class InceIsler3DPanel(QWidget):
    """
    Tam 3D önizleme paneli.

    Sol: Oda listesi (ad, alan, zemin malzeme combo)
    Sağ: InceIsler3DWidget (3D canvas)
    Alt: Malzeme legendı

    Kullanım:
    panel = InceIsler3DPanel(parent)
    # DXF/sap yüklenince otomatik:
    panel.load_from_sap(self.sap_eslestirme, kat_yuksekligi=2.80)
    # AutoCAD polyline seçilince:
    panel.add_acad_room(metraj_obj, oda_adi="Salon", zemin_malzeme="Laminat Parke")
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._builder = Room3DBuilder() if _BUILDER_OK else None
        self._odalar: List = []
        self._satir_widgetlari: List[OdaSatiri] = []
        self._init_ui()

    # ── UI Kurulumu ────────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ─ Başlık + Butonlar ─────────────────────────────────────────
        baslik_row = QHBoxLayout()

        baslik = QLabel(" 3D Materyal Önizleme")
        baslik.setStyleSheet(
            f"font-size: 13pt; font-weight: bold; color: {_CYAN}; background: transparent;"
        )
        baslik_row.addWidget(baslik)
        baslik_row.addStretch()

        self.btn_yenile = QPushButton(" Yenile")
        self.btn_yenile.setFixedWidth(80)
        self.btn_yenile.setToolTip("Malzeme seçimlerini 3D'ye uygula")
        self.btn_yenile.clicked.connect(self._yenile)
        baslik_row.addWidget(self.btn_yenile)

        self.btn_temizle = QPushButton(" Temizle")
        self.btn_temizle.setFixedWidth(80)
        self.btn_temizle.clicked.connect(self._temizle)
        baslik_row.addWidget(self.btn_temizle)

        root.addLayout(baslik_row)

        # ─ Ayırıcı ───────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {_GRID};")
        root.addWidget(sep)

        # ─ Ana içerik (splitter: sol oda listesi + sağ 3D) ───────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(
            "QSplitter::handle { background: #2a3a5a; }"
        )

        # ─── Sol panel: Oda listesi ───────────────────────────────────
        sol = QWidget()
        sol_layout = QVBoxLayout(sol)
        sol_layout.setContentsMargins(0, 0, 0, 0)
        sol_layout.setSpacing(4)
        sol.setMaximumWidth(380)

        oda_group = QGroupBox("Odalar / Malzeme")
        oda_group.setStyleSheet(
            "QGroupBox { color: #aaaaaa; font-size: 9pt; font-weight: bold; "
            "border: 1px solid #2a3a5a; border-radius: 4px; "
            "margin-top: 8px; padding-top: 10px; }"
            "QGroupBox::title { left: 8px; }"
        )
        oda_inner = QVBoxLayout(oda_group)
        oda_inner.setSpacing(3)

        # Başlık satırı
        header = QHBoxLayout()
        for txt, w in [("", 14), ("Oda Adı", 110), ("Alan", 55), ("Zemin Malzeme", 160)]:
            lbl = QLabel(txt)
            lbl.setFixedWidth(w)
            lbl.setStyleSheet("font-size: 8pt; color: #888888; font-weight: bold;")
            header.addWidget(lbl)
        oda_inner.addLayout(header)

        # Scrollable oda satırları
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical { background:#1a1a2e; width:6px; }"
            "QScrollBar::handle:vertical { background:#444; border-radius:3px; }"
        )
        self._satir_container = QWidget()
        self._satir_container.setStyleSheet("background: transparent;")
        self._satir_layout = QVBoxLayout(self._satir_container)
        self._satir_layout.setSpacing(2)
        self._satir_layout.setContentsMargins(0, 0, 0, 0)
        self._satir_layout.addStretch()
        self._scroll_area.setWidget(self._satir_container)
        oda_inner.addWidget(self._scroll_area)

        sol_layout.addWidget(oda_group)

        # AutoCAD'den ekle butonu
        self.btn_acad_ekle = QPushButton(" AutoCAD'den Oda Ekle")
        self.btn_acad_ekle.setToolTip(
            "AutoCAD'de seçili polyline'ı oda sınırı olarak ekle.\n"
            "Önce MetrajAnaliz penceresinde 'Obje Seç' yapın."
        )
        self.btn_acad_ekle.clicked.connect(self._acad_oda_ekle_dialog)
        self.btn_acad_ekle.setStyleSheet(
            "QPushButton { background: #1a3a5a; color: #00BFFF; font-weight: bold; "
            "padding: 7px; border: 1px solid #2a6a9a; border-radius: 4px; }"
            "QPushButton:hover { background: #2a5a8a; }"
        )
        sol_layout.addWidget(self.btn_acad_ekle)

        splitter.addWidget(sol)

        # ─── Sağ panel: 3D canvas ─────────────────────────────────────
        self.widget_3d = InceIsler3DWidget()
        self.widget_3d.reset()
        splitter.addWidget(self.widget_3d)

        splitter.setSizes([340, 700])
        root.addWidget(splitter, 1)

        # ─ Legend ─────────────────────────────────────────────────────
        root.addWidget(self._legend_yap())

    def _legend_yap(self) -> QWidget:
        """Malzeme renk göstergesi."""
        w = QWidget()
        w.setStyleSheet(f"background: {_AX}; border-radius: 4px; padding: 4px;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(14)

        legend_items = [
            ("#8B5E3C", "Parke"),
            ("#2196F3", "Fayans"),
            ("#9E9E9E", "Şap"),
            ("#EEEEEE", "Boya"),
            ("#00BCD4", "Duvar Fayans"),
            ("#FF9800", "Seramik"),
        ]

        lbl_legend = QLabel("Legend:")
        lbl_legend.setStyleSheet("color:#888;")
        layout.addWidget(lbl_legend)
        for renk, isim in legend_items:
            kutu = QLabel(f"■ {isim}")
            kutu.setStyleSheet(
                f"color: {renk}; font-size: 8pt; font-weight: bold; background: transparent;"
            )
            layout.addWidget(kutu)
        layout.addStretch()

        return w

    # ── Oda Satırı Yönetimi ────────────────────────────────────────────

    def _satir_temizle(self):
        """Oda satırlarını temizle."""
        for s in self._satir_widgetlari:
            s.setParent(None)
        self._satir_widgetlari.clear()

    def _satir_ekle(self, oda: "Oda3D"):
        """Tek oda için satır widget ekle."""
        satir = OdaSatiri(oda.oda_adi, oda.alan, oda.zemin_malzeme)
        satir.malzeme_degisti.connect(self._on_malzeme_degisti)
        satir.renk_degisti.connect(self._on_renk_degisti)
        self._satir_widgetlari.append(satir)
        # stretch'ten önce ekle
        self._satir_layout.insertWidget(
            self._satir_layout.count() - 1, satir
        )

    def _on_malzeme_degisti(self, oda_adi: str, yeni_malzeme: str):
        """Malzeme combo değişti → odayı yeniden üret, özel rengi koru."""
        for oda in self._odalar:
            if oda.oda_adi == oda_adi:
                if self._builder:
                    yeni_oda = self._builder.koordinatlardan_oda(
                        oda_adi=oda.oda_adi,
                        koordinatlar=list(oda.taban_polygon),
                        yukseklik=oda.yukseklik,
                        zemin_malzeme=yeni_malzeme,
                        duvar_malzeme=oda.duvar_malzeme,
                        tavan_malzeme=oda.tavan_malzeme,
                    )
                    idx = self._odalar.index(oda)
                    self._odalar[idx] = yeni_oda

                # Özel renk seçilmişse onu koru
                satir = next(
                    (s for s in self._satir_widgetlari if s.oda_adi == oda_adi),
                    None
                )
                if satir and satir.get_ozel_renk():
                    self._zemin_renk_uygula(oda_adi, satir.get_ozel_renk())
                    return  # load_rooms _zemin_renk_uygula içinde çağrılır
                break
        self.widget_3d.load_rooms(self._odalar)

    def _on_renk_degisti(self, oda_adi: str, rgba: tuple):
        """
        Kullanıcı butonuyla özel renk seçti.
        O odanın ZEMİN yüzeyinin rengini direkt günceller — render anlık değişir.
        """
        self._zemin_renk_uygula(oda_adi, rgba)

    def _zemin_renk_uygula(self, oda_adi: str, rgba: tuple):
        """O odanın ilk ZEMIN yüzeyine rgba uygula ve canvas'ı yenile."""
        for oda in self._odalar:
            if oda.oda_adi == oda_adi:
                for yuzey in oda.yuzeyler:
                    if yuzey.surface_type == "ZEMIN":
                        yuzey.rgba = rgba
                        break
                break
        self.widget_3d.load_rooms(self._odalar)

    # ── Public API ─────────────────────────────────────────────────────

    def load_from_sap(self, sap_eslestirme: list, kat_yuksekligi: float = 2.80,
                      malzeme_haritasi: Optional[Dict[str, str]] = None):
        """
        sap_eslestirme listesinden tüm odaları yükle ve 3D çiz.

        Parametre:
        sap_eslestirme: [{"mahal_adi": str, "deger": float, ...}, ...]
        kat_yuksekligi: metre cinsinden (varsayılan 2.80)
        malzeme_haritasi: {"Salon": "Laminat Parke", ...} ← kullanıcı seçimi
        """
        if not self._builder or not sap_eslestirme:
            logger.warning("3D panel: builder yok veya sap_eslestirme boş.")
            return

        self._odalar = self._builder.sap_eslestirmeden_odalar(
            sap_eslestirme, kat_yuksekligi, malzeme_haritasi
        )
        self._satir_temizle()
        for oda in self._odalar:
            self._satir_ekle(oda)

        self.widget_3d.load_rooms(self._odalar)
        logger.info(f"3D panel: {len(self._odalar)} oda yüklendi.")

    def add_acad_room(self, metraj_obj, oda_adi: str,
                      kat_yuksekligi: float = 2.80,
                      zemin_malzeme: Optional[str] = None):
        """
        AutoCAD MetrajObjesi'nden oda ekle (koordinatlar okunur).

        Parametre:
        metraj_obj: AutoCAD'den gelen MetrajObjesi
        oda_adi: Oda adı (kullanıcı girer)
        kat_yuksekligi: metre
        zemin_malzeme: seçilen zemin malzeme
        """
        if not self._builder:
            return
        oda = self._builder.autocad_objesinden_oda(
            metraj_obj, oda_adi, kat_yuksekligi, zemin_malzeme
        )
        if oda is None:
            logger.warning(f"3D panel: '{oda_adi}' için koordinat okunamadı.")
            return

        self._odalar.append(oda)
        self._satir_ekle(oda)
        self.widget_3d.load_rooms(self._odalar)
        logger.info(f"3D panel: '{oda_adi}' AutoCAD'den eklendi.")

    def _yenile(self):
        """Mevcut malzeme seçimlerine göre 3D'yi yeniden çiz.

        Kullanıcının ile seçtiği özel renkler korunur:
        her oda yeniden üretildikten sonra özel renk varsa
        zemin yüzeyine tekrar uygulanır.
        """
        # Satır widget'larından güncel malzemeleri ve özel renkleri oku
        malzeme_haritasi = {
            s.oda_adi: s.get_malzeme()
            for s in self._satir_widgetlari
        }
        ozel_renkler = {
            s.oda_adi: s.get_ozel_renk()
            for s in self._satir_widgetlari
            if s.get_ozel_renk() is not None
        }

        # Odaları güncelle
        if self._builder:
            yeni_odalar = []
            for oda in self._odalar:
                zm = malzeme_haritasi.get(oda.oda_adi, oda.zemin_malzeme)
                yeni = self._builder.koordinatlardan_oda(
                    oda_adi=oda.oda_adi,
                    koordinatlar=list(oda.taban_polygon),
                    yukseklik=oda.yukseklik,
                    zemin_malzeme=zm,
                    duvar_malzeme=oda.duvar_malzeme,
                    tavan_malzeme=oda.tavan_malzeme,
                )
                # Özel renk seçilmişse zemin yüzeyine tekrar uygula
                if oda.oda_adi in ozel_renkler:
                    for yuzey in yeni.yuzeyler:
                        if yuzey.surface_type == "ZEMIN":
                            yuzey.rgba = ozel_renkler[oda.oda_adi]
                            break
                yeni_odalar.append(yeni)
            self._odalar = yeni_odalar
            self.widget_3d.load_rooms(self._odalar)

    def _temizle(self):
        """Tüm odaları temizle."""
        self._odalar.clear()
        self._satir_temizle()
        self.widget_3d.reset()

    def _acad_oda_ekle_dialog(self):
        """
        AutoCAD'den oda ekleme mini diyaloğu.
        Üst pencere (MetrajAnalizWindow) üzerinden son seçili objeyi alır.
        """
        parent_win = self.window()

        # Üst pencereden acad_metraj_objeleri al
        acad_objeler = getattr(parent_win, "acad_metraj_objeleri", [])
        if not acad_objeler:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "AutoCAD",
                "AutoCAD'den seçili obje yok.\n\n"
                "Akıllı Metraj Analizi penceresinde önce\n"
                "' AutoCAD'e Bağlan' → ' Obje Seç' yapın."
            )
            return

        son_obj = acad_objeler[-1]

        dialog = _AcadOdaDialog(self)
        if dialog.exec():
            oda_adi = dialog.oda_adi()
            zemin_malz = dialog.zemin_malzeme()
            kat_yukseklik = getattr(parent_win, "kat_yuksekligi_spin", None)
            h = kat_yukseklik.value() if kat_yukseklik else 2.80
            self.add_acad_room(son_obj, oda_adi, h, zemin_malz)


# ── Mini Diyalog: AutoCAD Oda Ekleme ────────────────────────────────────────

class _AcadOdaDialog(QDialog):
    """AutoCAD'den oda eklerken oda adı + malzeme seçme diyaloğu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AutoCAD'den Oda Ekle")
        self.setFixedSize(320, 170)
        self.setStyleSheet(
            "QDialog { background: #1a1a2e; color: #e0e0e0; }"
            "QLabel { color: #e0e0e0; }"
            "QLineEdit, QComboBox { background: #16213e; color: #e0e0e0; "
            "border: 1px solid #2a3a5a; padding: 4px; border-radius: 3px; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QGridLayout()
        form.addWidget(QLabel("Oda Adı:"), 0, 0)
        self._ad = QLineEdit("Salon")
        form.addWidget(self._ad, 0, 1)

        form.addWidget(QLabel("Zemin Malzeme:"), 1, 0)
        self._malzeme = QComboBox()
        self._malzeme.addItems(ZEMIN_MALZEMELERI)
        form.addWidget(self._malzeme, 1, 1)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def oda_adi(self) -> str:
        return self._ad.text().strip() or "Oda"

    def zemin_malzeme(self) -> str:
        return self._malzeme.currentText()
