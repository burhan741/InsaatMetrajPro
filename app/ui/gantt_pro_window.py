"""
Insaat Metraj Pro -- Is Programi (Gantt Pro)
=============================================
CPM (Critical Path Method) + EVM (Earned Value Management) + PERT (3 Nokta Tahmin)
entegreli, insaat sektörüne ozgl proje planlama ve hakediş takip modülü.

5 Sekme:
 BUGÜN -- Puantaj ozeti, aktif is kalemleri, trafik isigi durumu
 PROGRAM -- Gantt Chart (kritik yol, baseline, WBS hiyerarşisi)
 MALIYET -- EVM Dashboard (CPI/SPI kartlari, tahmini bitiş maliyeti)
 KAYNAKLAR -- Ekip/Taseron kapasitesi, cakisma tespiti, otomatik dengeleme
 TEKNIK RAPOR -- Algoritma metodolojisi, standart referanslar, surum bilgisi

Algoritmalar:
 CPM : Kahn topolojik siralama, Forward/Backward Pass, Float hesabi
 EVM : PMBOK 7 uyumlu CPI/SPI/EAC/TCPI
 PERT : Beta dagilimi 3 nokta tahmin (Malcolm 1959 / TS ISO 21500:2022)
 Kaynak Dengeleme: Minimum gecikme, bolluk oncelik sirasi
"""

from PyQt6.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
 QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
 QLineEdit, QComboBox, QDateEdit, QTextEdit, QMessageBox,
 QHeaderView, QDoubleSpinBox, QTabWidget, QProgressBar,
 QSpinBox, QCheckBox, QScrollArea, QFrame, QDialog,
 QDialogButtonBox, QSplitter, QGraphicsView, QGraphicsScene,
 QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
 QGraphicsEllipseItem, QFileDialog, QTreeWidget, QTreeWidgetItem,
 QMenu, QToolButton, QGridLayout, QApplication, QSizePolicy,
 QStackedWidget, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import (
 Qt, QDate, QTimer, QRectF, QPointF, pyqtSignal, QThread, pyqtSlot
)
from PyQt6.QtGui import (
 QColor, QFont, QBrush, QPen, QPainter, QLinearGradient,
 QPainterPath, QFontMetrics, QIcon
)

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import os

from app.core.gantt_engine import GanttEngine, Task
from app.core.evm_engine import EVMEngine, GorevEVM
from app.core.kaynak_dengeleme_engine import (
 KaynakDengeleme, AtamaKayit
)
from app.core.pert_engine import PertEngine, PertGorev

logger = logging.getLogger(__name__)

# ── Renk Paleti ──────────────────────────────────────────────────────────────
C_BG = "#1a1a2e"
C_BG2 = "#16213e"
C_BG3 = "#0f3460"
C_ACCENT = "#00bfff"
C_ACCENT2 = "#00e5ff"
C_SUCCESS = "#27ae60"
C_WARNING = "#e67e22"
C_DANGER = "#e74c3c"
C_KRITIK = "#e74c3c"
C_TEXT = "#ecf0f1"
C_TEXT_DIM = "#95a5a6"
C_BORDER = "#2c3e50"
C_CARD = "#1e2a3a"
C_GANTT_ROW = "#1e2d3d"
C_GANTT_ALT = "#1a2535"

# ── Görev Renkleri ────────────────────────────────────────────────────────────
TASK_COLORS = {
 "normal": "#3498db",
 "kritik": "#e74c3c",
 "tamamlandi": "#27ae60",
 "gecikme": "#e67e22",
 "milestone": "#9b59b6",
 "ozet": "#34495e",
}

# ── Stil sabitleri ────────────────────────────────────────────────────────────
CARD_STYLE = """
 QFrame {{
 background: {bg};
 border: 1px solid {border};
 border-radius: 8px;
 padding: 4px;
 }}
"""

BTN_PRIMARY = f"""
 QPushButton {{
 background: {C_BG3};
 color: {C_ACCENT};
 border: 1px solid {C_ACCENT};
 border-radius: 6px;
 padding: 7px 16px;
 font-weight: bold;
 font-size: 12px;
 }}
 QPushButton:hover {{
 background: {C_ACCENT};
 color: #000;
 }}
 QPushButton:pressed {{
 background: {C_ACCENT2};
 }}
"""

BTN_SUCCESS = f"""
 QPushButton {{
 background: #1a3a2a;
 color: {C_SUCCESS};
 border: 1px solid {C_SUCCESS};
 border-radius: 6px;
 padding: 7px 16px;
 font-weight: bold;
 }}
 QPushButton:hover {{
 background: {C_SUCCESS};
 color: #fff;
 }}
"""

BTN_DANGER = f"""
 QPushButton {{
 background: #3a1a1a;
 color: {C_DANGER};
 border: 1px solid {C_DANGER};
 border-radius: 6px;
 padding: 7px 16px;
 font-weight: bold;
 }}
 QPushButton:hover {{
 background: {C_DANGER};
 color: #fff;
 }}
"""

TABLE_STYLE = f"""
 QTableWidget {{
 background: {C_BG2};
 color: {C_TEXT};
 gridline-color: {C_BORDER};
 border: 1px solid {C_BORDER};
 border-radius: 6px;
 font-size: 12px;
 }}
 QTableWidget::item {{
 padding: 6px;
 border-bottom: 1px solid {C_BORDER};
 }}
 QTableWidget::item:selected {{
 background: {C_BG3};
 color: {C_ACCENT};
 }}
 QHeaderView::section {{
 background: {C_BG3};
 color: {C_ACCENT};
 padding: 8px;
 border: none;
 border-bottom: 2px solid {C_ACCENT};
 font-weight: bold;
 font-size: 11px;
 }}
"""

TAB_STYLE = f"""
 QTabWidget::pane {{
 border: 1px solid {C_BORDER};
 background: {C_BG};
 border-radius: 8px;
 }}
 QTabBar::tab {{
 background: {C_BG2};
 color: {C_TEXT_DIM};
 padding: 10px 20px;
 margin-right: 2px;
 border-top-left-radius: 6px;
 border-top-right-radius: 6px;
 font-size: 13px;
 font-weight: bold;
 min-width: 130px;
 }}
 QTabBar::tab:selected {{
 background: {C_BG3};
 color: {C_ACCENT};
 border-bottom: 3px solid {C_ACCENT};
 }}
 QTabBar::tab:hover {{
 background: {C_BG3};
 color: {C_TEXT};
 }}
"""


# =============================================================================
# YARDIMCI: KPI Kartı
# =============================================================================
class KPIKarti(QFrame):
 """Tek değer + başlık + ikon gösteren kart bileşeni."""

 def __init__(
 self,
 baslik: str,
 deger: str = "—",
 ikon: str = "",
 renk: str = C_ACCENT,
 parent=None,
 ):
 super().__init__(parent)
 self.renk = renk
 self.setMinimumWidth(160)
 self.setMinimumHeight(90)
 self.setStyleSheet(f"""
 QFrame {{
 background: {C_CARD};
 border: 1px solid {renk}44;
 border-left: 4px solid {renk};
 border-radius: 8px;
 }}
 """)

 layout = QVBoxLayout(self)
 layout.setContentsMargins(14, 10, 14, 10)
 layout.setSpacing(4)

 # Başlık
 self.lbl_baslik = QLabel(f"{ikon} {baslik}" if ikon else baslik)
 self.lbl_baslik.setStyleSheet(
 f"color: {C_TEXT_DIM}; font-size: 11px; font-weight: bold;"
 "border: none; background: transparent;"
 )
 layout.addWidget(self.lbl_baslik)

 # Değer
 self.lbl_deger = QLabel(deger)
 self.lbl_deger.setStyleSheet(
 f"color: {renk}; font-size: 22px; font-weight: bold;"
 "border: none; background: transparent;"
 )
 layout.addWidget(self.lbl_deger)

 def guncelle(self, deger: str, renk: Optional[str] = None) -> None:
 """Değeri ve isteğe bağlı rengi güncelle."""
 self.lbl_deger.setText(deger)
 if renk:
 self.lbl_deger.setStyleSheet(
 f"color: {renk}; font-size: 22px; font-weight: bold;"
 "border: none; background: transparent;"
 )


# =============================================================================
# YARDIMCI: Trafik Işığı Gösterge
# =============================================================================
class TIGostergesi(QFrame):
 """Bir durum için trafik ışığı rengi + açıklama."""

 RENKLER = {
 "yesil": ("#27ae60", ""),
 "sari": ("#e67e22", ""),
 "kirmizi": ("#e74c3c", ""),
 }

 def __init__(self, baslik: str, parent=None):
 super().__init__(parent)
 self.setFixedWidth(200)
 self.setFixedHeight(70)
 self.setStyleSheet(f"""
 QFrame {{ background: {C_CARD}; border-radius: 8px;
 border: 1px solid {C_BORDER}; }}
 """)

 lay = QHBoxLayout(self)
 lay.setContentsMargins(10, 8, 10, 8)

 self.lbl_ikon = QLabel("")
 self.lbl_ikon.setFixedWidth(28)
 self.lbl_ikon.setStyleSheet("font-size: 22px; border: none; background: transparent;")
 lay.addWidget(self.lbl_ikon)

 sag = QVBoxLayout()
 self.lbl_baslik = QLabel(baslik)
 self.lbl_baslik.setStyleSheet(
 f"color: {C_TEXT_DIM}; font-size: 10px; border: none; background: transparent;"
 )
 self.lbl_deger = QLabel("—")
 self.lbl_deger.setStyleSheet(
 f"color: {C_TEXT}; font-size: 12px; font-weight: bold;"
 "border: none; background: transparent;"
 )
 sag.addWidget(self.lbl_baslik)
 sag.addWidget(self.lbl_deger)
 lay.addLayout(sag)

 def guncelle(self, durum: str, metin: str = "") -> None:
 renk, emoji = self.RENKLER.get(durum, (C_TEXT_DIM, ""))
 self.lbl_ikon.setStyleSheet(
 f"color: {renk}; font-size: 22px; border: none; background: transparent;"
 )
 self.lbl_deger.setText(metin or durum.capitalize())


# =============================================================================
# GANTT CHART — Görsel Çizim Bileşeni
# =============================================================================
class GanttChartGrafik(QGraphicsView):
 """
 QGraphicsView tabanlı Gantt Chart çizici.
 Özellikler: Kritik yol kırmızı, tamamlanma yeşil doldurma,
 Baseline gri çizgi, zoom desteği, görev tıklama sinyali.
 """

 gorev_tiklandi = pyqtSignal(int) # task_id

 ROW_H = 32
 DAY_W_BASE = 22
 HEADER_H = 50
 NAME_W = 240

 def __init__(self, parent=None):
 super().__init__(parent)
 self.scene = QGraphicsScene(self)
 self.setScene(self.scene)
 self.engine: Optional[GanttEngine] = None
 self.zoom_level = 1.0
 self.day_width = self.DAY_W_BASE

 self.setStyleSheet(f"background: {C_BG2}; border: 1px solid {C_BORDER};")
 self.setRenderHint(QPainter.RenderHint.Antialiasing)
 self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
 self.setTransformationAnchor(
 QGraphicsView.ViewportAnchor.AnchorUnderMouse
 )

 def ciz(self, engine: GanttEngine) -> None:
 """Engine verisinden Gantt grafiğini çiz."""
 self.engine = engine
 self.scene.clear()

 if not engine.proje_baslangic or not engine.proje_bitis:
 self._bos_mesaj()
 return

 tasks = sorted(
 engine.tasks.values(),
 key=lambda t: (t.wbs_kodu or "999", t.early_start or datetime.max)
 )
 if not tasks:
 self._bos_mesaj()
 return

 proje_bas = engine.proje_baslangic
 proje_bit = engine.proje_bitis
 toplam_gun = max(1, (proje_bit - proje_bas).days + 14)

 W = self.NAME_W + toplam_gun * self.day_width
 H = self.HEADER_H + len(tasks) * self.ROW_H + 20

 self.scene.setSceneRect(0, 0, W, H)

 # ── Başlık ───────────────────────────────────────────────
 self._ciz_baslik(proje_bas, toplam_gun, W)

 # ── Satırlar ─────────────────────────────────────────────
 for i, task in enumerate(tasks):
 y = self.HEADER_H + i * self.ROW_H
 self._ciz_satir(task, i, y, proje_bas)

 # ── Bugün çizgisi ────────────────────────────────────────
 self._ciz_bugun_cizgisi(proje_bas, toplam_gun, H)

 def _ciz_baslik(self, proje_bas: datetime, toplam_gun: int, W: float) -> None:
 """Ay ve hafta başlıkları."""
 # Arka plan
 r = self.scene.addRect(
 0, 0, W, self.HEADER_H,
 QPen(Qt.PenStyle.NoPen),
 QBrush(QColor(C_BG3))
 )

 # Sol panel başlık
 self.scene.addRect(
 0, 0, self.NAME_W, self.HEADER_H,
 QPen(QColor(C_BORDER)),
 QBrush(QColor(C_BG3))
 )
 t = self.scene.addText("İŞ TANIMI")
 t.setDefaultTextColor(QColor(C_ACCENT))
 t.setFont(QFont("Arial", 9, QFont.Weight.Bold))
 t.setPos(10, 15)

 # Ay başlıkları
 tarih = proje_bas
 ay_baslangic_x: Dict[str, float] = {}
 for gun in range(toplam_gun):
 tarih = proje_bas + timedelta(days=gun)
 ay_anahtar = tarih.strftime("%Y-%m")
 x = self.NAME_W + gun * self.day_width
 if ay_anahtar not in ay_baslangic_x:
 ay_baslangic_x[ay_anahtar] = x

 for ay_str, x in ay_baslangic_x.items():
 dt = datetime.strptime(ay_str, "%Y-%m")
 ay_ad = ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
 "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"][dt.month - 1]
 t = self.scene.addText(f"{ay_ad} {dt.year}")
 t.setDefaultTextColor(QColor(C_ACCENT2))
 t.setFont(QFont("Arial", 8, QFont.Weight.Bold))
 t.setPos(x + 2, 2)

 # Dikey ay çizgisi
 self.scene.addLine(
 x, 0, x, self.HEADER_H,
 QPen(QColor(C_BORDER), 1)
 )

 # Gün numaraları (alt satır)
 for gun in range(toplam_gun):
 tarih = proje_bas + timedelta(days=gun)
 x = self.NAME_W + gun * self.day_width
 if tarih.weekday() < 5 and gun % 5 == 0:
 t = self.scene.addText(str(tarih.day))
 t.setDefaultTextColor(QColor(C_TEXT_DIM))
 t.setFont(QFont("Arial", 7))
 t.setPos(x + 1, 30)

 def _ciz_satir(
 self,
 task: Task,
 indeks: int,
 y: float,
 proje_bas: datetime,
 ) -> None:
 """Tek görev satırını çiz."""
 row_renk = C_GANTT_ROW if indeks % 2 == 0 else C_GANTT_ALT

 # Satır arka planı
 self.scene.addRect(
 0, y, self.scene.width(), self.ROW_H,
 QPen(Qt.PenStyle.NoPen),
 QBrush(QColor(row_renk))
 )

 # İnce yatay çizgi
 self.scene.addLine(
 0, y + self.ROW_H, self.scene.width(), y + self.ROW_H,
 QPen(QColor(C_BORDER), 0.5)
 )

 # Görev adı (girintili WBS)
 seviye = getattr(task, "seviye", 0)
 girinti = 8 + seviye * 16
 ad_kisalt = task.ad[:32] + ("…" if len(task.ad) > 32 else "")

 font_ad = QFont("Arial", 9, QFont.Weight.Bold if seviye == 0 else QFont.Weight.Normal)
 t = self.scene.addText(ad_kisalt)
 t.setDefaultTextColor(QColor(C_TEXT if not task.kritik else C_KRITIK))
 t.setFont(font_ad)
 t.setPos(girinti, y + 7)

 if not task.early_start or not task.early_finish:
 return

 # ── Görev çubuğu ─────────────────────────────────────────
 gun_bas = (task.early_start - proje_bas).days
 gun_bit = (task.early_finish - proje_bas).days
 x_bas = self.NAME_W + gun_bas * self.day_width
 x_bit = self.NAME_W + gun_bit * self.day_width
 bar_w = max(8, x_bit - x_bas)
 bar_h = 20
 bar_y = y + (self.ROW_H - bar_h) / 2

 # Milestone
 if task.milestone:
 diamond_size = 14
 dx = x_bas
 dy = y + self.ROW_H / 2
 diamond = QPainterPath()
 diamond.moveTo(dx, dy - diamond_size / 2)
 diamond.lineTo(dx + diamond_size / 2, dy)
 diamond.lineTo(dx, dy + diamond_size / 2)
 diamond.lineTo(dx - diamond_size / 2, dy)
 diamond.closeSubpath()
 path_item = self.scene.addPath(
 diamond,
 QPen(QColor(TASK_COLORS["milestone"])),
 QBrush(QColor(TASK_COLORS["milestone"]))
 )
 return

 # Çubuk rengi
 if task.kritik:
 bar_renk = TASK_COLORS["kritik"]
 elif task.ilerleme >= 100:
 bar_renk = TASK_COLORS["tamamlandi"]
 elif (task.early_start and task.early_start < datetime.now()
 and task.ilerleme < self._planlanan_ilerleme(task)):
 bar_renk = TASK_COLORS["gecikme"]
 elif hasattr(task, "parent_id") and task.parent_id is not None:
 bar_renk = TASK_COLORS["ozet"]
 else:
 bar_renk = TASK_COLORS["normal"]

 # Gradient çubuk
 gradient = QLinearGradient(x_bas, bar_y, x_bas, bar_y + bar_h)
 gradient.setColorAt(0, QColor(bar_renk).lighter(130))
 gradient.setColorAt(1, QColor(bar_renk))

 bar = self.scene.addRect(
 x_bas, bar_y, bar_w, bar_h,
 QPen(QColor(bar_renk).darker(120), 1),
 QBrush(gradient)
 )
 bar.setToolTip(
 f"{task.ad}\n"
 f"Başlangıç: {task.early_start.strftime('%d.%m.%Y')}\n"
 f"Bitiş: {task.early_finish.strftime('%d.%m.%Y')}\n"
 f"Süre: {task.sure_gun} gün\n"
 f"İlerleme: %{task.ilerleme:.0f}\n"
 f"Float: {task.float_gun} gün\n"
 f"{' KRİTİK' if task.kritik else ' Normal'}"
 )

 # İlerleme dolgu
 if task.ilerleme > 0:
 prog_w = bar_w * task.ilerleme / 100
 self.scene.addRect(
 x_bas, bar_y, prog_w, bar_h,
 QPen(Qt.PenStyle.NoPen),
 QBrush(QColor(C_SUCCESS).lighter(120) if not task.kritik
 else QColor(C_WARNING))
 )

 # İlerleme % metni
 if bar_w > 40:
 prog_t = self.scene.addText(f"%{task.ilerleme:.0f}")
 prog_t.setDefaultTextColor(QColor("#fff"))
 prog_t.setFont(QFont("Arial", 7, QFont.Weight.Bold))
 prog_t.setPos(x_bas + 4, bar_y + 3)

 # Baseline çizgisi
 if task.baseline_bitis:
 base_gun_bit = (task.baseline_bitis - proje_bas).days
 x_base_bit = self.NAME_W + base_gun_bit * self.day_width
 base_gun_bas = (task.baseline_baslangic - proje_bas).days if task.baseline_baslangic else gun_bas
 x_base_bas = self.NAME_W + base_gun_bas * self.day_width

 self.scene.addLine(
 x_base_bas, bar_y + bar_h + 3,
 x_base_bit, bar_y + bar_h + 3,
 QPen(QColor("#7f8c8d"), 2)
 )

 # Bağımlılık okları (sadece FS)
 for pred_id, dep_type, lag in task.predecessors:
 if dep_type == "FS" and pred_id in self.engine.tasks:
 pred_task = self.engine.tasks[pred_id]
 if pred_task.early_finish:
 px = self.NAME_W + (pred_task.early_finish - proje_bas).days * self.day_width
 py_mid = y + self.ROW_H / 2
 pred_y_idx = list(sorted(
 self.engine.tasks.values(),
 key=lambda t: (t.wbs_kodu or "", t.early_start or datetime.max)
 )).index(pred_task)
 pred_py = self.HEADER_H + pred_y_idx * self.ROW_H + self.ROW_H / 2

 ok_rengi = C_KRITIK if task.kritik else C_BORDER
 pen = QPen(QColor(ok_rengi), 1)
 pen.setStyle(Qt.PenStyle.DotLine)
 self.scene.addLine(px, pred_py, x_bas, py_mid, pen)

 def _ciz_bugun_cizgisi(
 self, proje_bas: datetime, toplam_gun: int, H: float
 ) -> None:
 """Bugünün tarihini gösteren dikey kırmızı çizgi."""
 bugun = datetime.now()
 if proje_bas <= bugun:
 gun = (bugun - proje_bas).days
 if gun <= toplam_gun:
 x = self.NAME_W + gun * self.day_width
 pen = QPen(QColor(C_DANGER), 2)
 pen.setStyle(Qt.PenStyle.DashLine)
 self.scene.addLine(x, 0, x, H, pen)

 t = self.scene.addText("BUGÜN")
 t.setDefaultTextColor(QColor(C_DANGER))
 t.setFont(QFont("Arial", 7, QFont.Weight.Bold))
 t.setPos(x + 2, 2)

 def _bos_mesaj(self) -> None:
 t = self.scene.addText(
 "Görev ekleyin ve 'Hesapla' butonuna basın."
 )
 t.setDefaultTextColor(QColor(C_TEXT_DIM))
 t.setFont(QFont("Arial", 14))
 t.setPos(100, 100)

 @staticmethod
 def _planlanan_ilerleme(task: Task) -> float:
 """Bugün itibarıyla planlanan ilerleme yüzdesi."""
 if not task.early_start or not task.early_finish:
 return 0.0
 bugun = datetime.now()
 if bugun < task.early_start:
 return 0.0
 if bugun > task.early_finish:
 return 100.0
 toplam = max(1, (task.early_finish - task.early_start).days)
 gecen = (bugun - task.early_start).days
 return (gecen / toplam) * 100

 def wheelEvent(self, event) -> None:
 """Scroll ile zoom."""
 factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
 self.zoom_level *= factor
 self.scale(factor, factor)


# =============================================================================
# BEKLENMEDIK DURUM DIALOGU
# =============================================================================
class BeklenmedikDurumDialog(QDialog):
 """
 Sahada beklenmedik durumları kaydeden dialog.

 Saha karşılığı:
 Yağış, çimento gecikmesi, ekip eksikliği gibi durumlar
 ataşman kaydı olarak is programına işlenir.
 Etkilenen iş kalemlerinde sure_gun otomatik güncellenir.
 """

 DURUM_TURLERI = [
 "Çimento/Beton Sevkiyat Gecikmesi",
 "Yoğun Yağış — Beton Dökümü İptal",
 "Kalıp Malzemesi Eksikliği",
 "İşçi/Ekip Yetersizliği",
 "Makina Arızası / Beklenmeyen Tamir",
 "Resmi/Dini Tatil (Takvim Dışı)",
 "Serbest Giriş",
 ]

 def __init__(self, tum_gorevler: Optional[Dict] = None, parent=None):
 super().__init__(parent)
 self.tum_gorevler = tum_gorevler or {}
 self.setWindowTitle("Beklenmedik Durum Girişi — Saha Ataşman Kaydı")
 self.setMinimumWidth(540)
 self.setMinimumHeight(520)
 self.setStyleSheet(f"""
 QDialog {{ background: {C_BG}; color: {C_TEXT}; }}
 QLabel {{ color: {C_TEXT}; }}
 QLineEdit, QSpinBox, QComboBox, QTextEdit, QListWidget {{
 background: {C_BG2}; color: {C_TEXT};
 border: 1px solid {C_BORDER}; border-radius: 4px; padding: 5px;
 }}
 QGroupBox {{
 color: {C_WARNING}; font-weight: bold;
 border: 1px solid {C_WARNING}44;
 border-radius: 6px; padding-top: 14px;
 }}
 """)
 self._build_ui()

 def _build_ui(self) -> None:
 lay = QVBoxLayout(self)
 lay.setSpacing(10)

 # Başlık bandı
 lbl_baslik = QLabel("SAHADAN BİLDİRİM — Beklenmedik Durum Kaydı")
 lbl_baslik.setStyleSheet(
 f"color: {C_WARNING}; font-size: 13px; font-weight: bold;"
 "border: none; background: transparent;"
 )
 lay.addWidget(lbl_baslik)

 form = QFormLayout()
 form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
 form.setSpacing(8)

 # Durum türü
 self.cmb_tur = QComboBox()
 for tur in self.DURUM_TURLERI:
 self.cmb_tur.addItem(tur)
 form.addRow("Durum Türü:", self.cmb_tur)

 # Gecikme günü
 self.spn_gecikme_gun = QSpinBox()
 self.spn_gecikme_gun.setRange(1, 120)
 self.spn_gecikme_gun.setValue(3)
 self.spn_gecikme_gun.setSuffix(" gün")
 form.addRow("Gecikme Süresi:", self.spn_gecikme_gun)

 lay.addLayout(form)

 # Etkilenen iş kalemleri
 etk_grp = QGroupBox("Etkilenen İş Kalemleri (Çoklu Seçim)")
 etk_lay = QVBoxLayout(etk_grp)
 self.lst_etkilenen = QListWidget()
 self.lst_etkilenen.setSelectionMode(
 QListWidget.SelectionMode.MultiSelection
 )
 self.lst_etkilenen.setMaximumHeight(150)
 for tid, task in self.tum_gorevler.items():
 item_text = f"{task.wbs_kodu or '—'} | {task.ad} ({task.sure_gun}g)"
 it = QListWidgetItem(item_text)
 it.setData(Qt.ItemDataRole.UserRole, tid)
 self.lst_etkilenen.addItem(it)
 etk_lay.addWidget(self.lst_etkilenen)
 lay.addWidget(etk_grp)

 # Ataşman notu
 not_grp = QGroupBox("Saha Ataşman Notu")
 not_lay = QVBoxLayout(not_grp)
 self.inp_ataman_notu = QTextEdit()
 self.inp_ataman_notu.setPlaceholderText(
 "Durum açıklaması, saha gözlemi, fotoğraf referansı vb.\n"
 "Bu not hakediş dosyasına ataşman olarak eklenebilir."
 )
 self.inp_ataman_notu.setMaximumHeight(90)
 not_lay.addWidget(self.inp_ataman_notu)
 lay.addWidget(not_grp)

 # Hakediş etkisi
 hak_grp = QGroupBox("Hakediş / Tahsilat Durumu")
 hak_lay = QVBoxLayout(hak_grp)
 self.inp_tahsilat_durumu = QLineEdit()
 self.inp_tahsilat_durumu.setPlaceholderText(
 "Örn: 3. Hakediş'te iş duruş bedeli talep edilecek — İdare onayı bekleniyor."
 )
 hak_lay.addWidget(self.inp_tahsilat_durumu)
 lay.addWidget(hak_grp)

 # Butonlar
 btnbox = QDialogButtonBox(
 QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
 )
 btnbox.setStyleSheet(f"""
 QPushButton {{
 background: {C_BG3}; color: {C_WARNING};
 border: 1px solid {C_WARNING}; border-radius: 5px;
 padding: 6px 20px; font-weight: bold;
 }}
 QPushButton:hover {{ background: {C_WARNING}; color: #000; }}
 """)
 btnbox.accepted.connect(self.accept)
 btnbox.rejected.connect(self.reject)
 lay.addWidget(btnbox)

 def get_data(self) -> Dict:
 """Dialog verilerini döndür."""
 etkilenen_ids = [
 self.lst_etkilenen.item(i).data(Qt.ItemDataRole.UserRole)
 for i in range(self.lst_etkilenen.count())
 if self.lst_etkilenen.item(i).isSelected()
 ]
 return {
 "tur": self.cmb_tur.currentText(),
 "etkilenen_ids": etkilenen_ids,
 "gecikme_gun": self.spn_gecikme_gun.value(),
 "ataman_notu": self.inp_ataman_notu.toPlainText().strip(),
 "tahsilat_durumu": self.inp_tahsilat_durumu.text().strip(),
 }


# =============================================================================
# GOREV DIALOG
# =============================================================================
class GorevDialog(QDialog):
 """Görev ekleme ve düzenleme diyaloğu — inşaat odaklı."""

 def __init__(self, task: Optional[Task] = None,
 tum_gorevler: Optional[Dict] = None,
 parent=None):
 super().__init__(parent)
 self.task = task
 self.tum_gorevler = tum_gorevler or {}
 self.setWindowTitle("Görev Ekle / Düzenle" if not task else f"Düzenle: {task.ad}")
 self.setMinimumWidth(520)
 self.setStyleSheet(f"""
 QDialog {{ background: {C_BG}; color: {C_TEXT}; }}
 QLabel {{ color: {C_TEXT}; }}
 QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QTextEdit {{
 background: {C_BG2}; color: {C_TEXT};
 border: 1px solid {C_BORDER}; border-radius: 4px;
 padding: 5px;
 }}
 """)
 self._build_ui()
 if task:
 self._fill_data(task)

 def _build_ui(self) -> None:
 lay = QVBoxLayout(self)
 lay.setSpacing(8)

 form = QFormLayout()
 form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

 self.inp_ad = QLineEdit()
 self.inp_ad.setPlaceholderText("Örn: Temel Hafriyatı")
 self.inp_sure = QSpinBox()
 self.inp_sure.setRange(0, 999)
 self.inp_sure.setSuffix(" gün")

 # ── PERT 3 Nokta Tahmin Alanları ─────────────────────────────────────
 self.spn_iyimser_gun = QSpinBox()
 self.spn_iyimser_gun.setRange(1, 999)
 self.spn_iyimser_gun.setSuffix(" gün (t_o — her şey yolunda giderse)")
 self.spn_kotumser_gun = QSpinBox()
 self.spn_kotumser_gun.setRange(1, 999)
 self.spn_kotumser_gun.setSuffix(" gün (t_p — Murphy Kanunu devrede)")
 self.btn_pert_hesapla = QPushButton("PERT Hesapla → Süreyi Güncelle")
 self.btn_pert_hesapla.setStyleSheet(BTN_PRIMARY)
 self.btn_pert_hesapla.clicked.connect(self._pert_hesapla)
 self.lbl_pert_sonuc = QLabel("—")
 self.lbl_pert_sonuc.setStyleSheet(
 f"color: {C_ACCENT2}; font-weight: bold; background: transparent; border: none;"
 )

 self.inp_kaynak = QLineEdit()
 self.inp_kaynak.setPlaceholderText("Örn: Kalıpçı Ekibi A Takımı")
 self.inp_maliyet = QDoubleSpinBox()
 self.inp_maliyet.setRange(0, 99_999_999)
 self.inp_maliyet.setSuffix(" TL")
 self.inp_maliyet.setDecimals(0)
 self.inp_ilerleme = QSpinBox()
 self.inp_ilerleme.setRange(0, 100)
 self.inp_ilerleme.setSuffix(" %")
 self.inp_gercek_maliyet = QDoubleSpinBox()
 self.inp_gercek_maliyet.setRange(0, 99_999_999)
 self.inp_gercek_maliyet.setSuffix(" TL")
 self.inp_gercek_maliyet.setDecimals(0)
 self.chk_milestone = QCheckBox("Milestone (dönüm noktası)")
 self.chk_kritik = QCheckBox("Kritik olarak işaretle")
 self.inp_wbs = QLineEdit()
 self.inp_wbs.setPlaceholderText("Örn: 1.2.3 (boş bırakılabilir)")
 self.inp_aciklama = QTextEdit()
 self.inp_aciklama.setMaximumHeight(60)

 # Öncül (predecessor)
 self.cmb_oncul = QComboBox()
 self.cmb_oncul.addItem("Yok", None)
 for tid, t in self.tum_gorevler.items():
 if self.task and tid == self.task.task_id:
 continue
 self.cmb_oncul.addItem(f"{t.wbs_kodu} — {t.ad}", tid)

 self.inp_lag = QSpinBox()
 self.inp_lag.setRange(-99, 999)
 self.inp_lag.setSuffix(" gün (+ gecikme / − örtüşme)")

 form.addRow("İş Adı *:", self.inp_ad)
 form.addRow("Süre (Olası) *:", self.inp_sure)
 form.addRow("İyimser Süre:", self.spn_iyimser_gun)
 form.addRow("Kötümser Süre:", self.spn_kotumser_gun)
 form.addRow("", self.btn_pert_hesapla)
 form.addRow("PERT Sonucu:", self.lbl_pert_sonuc)
 form.addRow("WBS Kodu:", self.inp_wbs)
 form.addRow("Ekip / Taşeron:", self.inp_kaynak)
 form.addRow("Bütçe (TL):", self.inp_maliyet)
 form.addRow("Gerçek Maliyet:", self.inp_gercek_maliyet)
 form.addRow("Hakedişe Esas İlerleme %:", self.inp_ilerleme)
 form.addRow("Öncül Görev:", self.cmb_oncul)
 form.addRow("Lag / Lead:", self.inp_lag)
 form.addRow("", self.chk_milestone)
 form.addRow("", self.chk_kritik)
 form.addRow("Açıklama:", self.inp_aciklama)

 lay.addLayout(form)

 # Butonlar
 btnbox = QDialogButtonBox(
 QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
 )
 btnbox.setStyleSheet(f"""
 QPushButton {{
 background: {C_BG3}; color: {C_ACCENT};
 border: 1px solid {C_ACCENT}; border-radius: 5px;
 padding: 6px 20px; font-weight: bold;
 }}
 QPushButton:hover {{ background: {C_ACCENT}; color: #000; }}
 """)
 btnbox.accepted.connect(self.accept)
 btnbox.rejected.connect(self.reject)
 lay.addWidget(btnbox)

 def _pert_hesapla(self) -> None:
 """PERT 3 nokta formülüyle beklenen süreyi hesaplar ve inp_sure'yu günceller."""
 t_o = float(self.spn_iyimser_gun.value())
 t_m = float(self.inp_sure.value())
 t_p = float(self.spn_kotumser_gun.value())

 if t_p < t_m:
 QMessageBox.warning(
 self, "Veri Hatası",
 f"Kötümser süre ({t_p:.0f}g) < Olası süre ({t_m:.0f}g).\n"
 "Kötümser süre en büyük değer olmalıdır."
 )
 return
 if t_o > t_m:
 QMessageBox.warning(
 self, "Veri Hatası",
 f"İyimser süre ({t_o:.0f}g) > Olası süre ({t_m:.0f}g).\n"
 "İyimser süre en küçük değer olmalıdır."
 )
 return

 t_e = (t_o + 4.0 * t_m + t_p) / 6.0
 sigma = (t_p - t_o) / 6.0
 sigma2 = sigma ** 2

 self.inp_sure.setValue(round(t_e))
 self.lbl_pert_sonuc.setText(
 f"PERT: {t_e:.1f} gün, σ={sigma:.2f}g, σ²={sigma2:.2f} "
 f"[P80={t_e + 0.842*sigma:.1f}g | P90={t_e + 1.282*sigma:.1f}g]"
 )

 def _fill_data(self, task: Task) -> None:
 self.inp_ad.setText(task.ad)
 self.inp_sure.setValue(task.sure_gun)
 self.inp_wbs.setText(task.wbs_kodu or "")
 self.inp_kaynak.setText(task.kaynak or "")
 self.inp_ilerleme.setValue(int(task.ilerleme))
 self.chk_milestone.setChecked(task.milestone)
 self.chk_kritik.setChecked(task.kritik)
 self.inp_aciklama.setPlainText(task.aciklama or "")
 if hasattr(task, "butce_tl"):
 self.inp_maliyet.setValue(float(getattr(task, "butce_tl", 0)))
 if hasattr(task, "gercek_maliyet_tl"):
 self.inp_gercek_maliyet.setValue(float(getattr(task, "gercek_maliyet_tl", 0)))

 def get_data(self) -> Dict:
 return {
 "ad": self.inp_ad.text().strip(),
 "sure_gun": self.inp_sure.value(),
 "iyimser_gun": self.spn_iyimser_gun.value(),
 "kotumser_gun": self.spn_kotumser_gun.value(),
 "wbs_kodu": self.inp_wbs.text().strip(),
 "kaynak": self.inp_kaynak.text().strip(),
 "butce_tl": Decimal(str(self.inp_maliyet.value())),
 "gercek_maliyet_tl": Decimal(str(self.inp_gercek_maliyet.value())),
 "ilerleme": float(self.inp_ilerleme.value()),
 "milestone": self.chk_milestone.isChecked(),
 "kritik_override": self.chk_kritik.isChecked(),
 "aciklama": self.inp_aciklama.toPlainText(),
 "oncul_id": self.cmb_oncul.currentData(),
 "lag_days": self.inp_lag.value(),
 }


# =============================================================================
# SEKMELİ ANA PENCERE
# =============================================================================
class GanttProWindow(QWidget):
 """
 İnşaat Metraj Pro — İş Programı Ana Penceresi.
 4 sekmeli, MS Project alternatifi modül.
 """

 def __init__(self, db_manager=None, parent=None):
 super().__init__(parent)
 self.db = db_manager
 self.engine = GanttEngine(db_manager)
 self.evm_eng = EVMEngine()
 self.den_eng = KaynakDengeleme()

 # Her görev için ek finansal veri
 self._butce: Dict[int, Decimal] = {}
 self._gercek_mal: Dict[int, Decimal] = {}

 self.setStyleSheet(f"QWidget {{ background: {C_BG}; color: {C_TEXT}; }}")
 self._build_ui()
 self._demo_veri_yukle()

 # ── UI İnşası ─────────────────────────────────────────────────────────────

 def _build_ui(self) -> None:
 layout = QVBoxLayout(self)
 layout.setContentsMargins(8, 8, 8, 8)
 layout.setSpacing(6)

 # Üst araç çubuğu
 layout.addWidget(self._build_toolbar())

 # Sekme widget
 self.tabs = QTabWidget()
 self.tabs.setStyleSheet(TAB_STYLE)

 self.tabs.addTab(self._build_bugün_sekmesi(), "BUGÜN")
 self.tabs.addTab(self._build_program_sekmesi(), "PROGRAM")
 self.tabs.addTab(self._build_maliyet_sekmesi(), "MALİYET")
 self.tabs.addTab(self._build_kaynaklar_sekmesi(), "KAYNAKLAR")
 self.tabs.addTab(self._build_teknik_rapor_sekmesi(), "TEKNİK RAPOR")

 layout.addWidget(self.tabs)

 # Alt durum çubuğu
 self.lbl_durum = QLabel("Hazır — Görev ekleyin veya şablon yükleyin.")
 self.lbl_durum.setStyleSheet(
 f"color: {C_TEXT_DIM}; padding: 4px 8px; "
 f"background: {C_BG2}; border-radius: 4px; font-size: 11px;"
 )
 layout.addWidget(self.lbl_durum)

 def _build_toolbar(self) -> QFrame:
 bar = QFrame()
 bar.setStyleSheet(f"""
 QFrame {{
 background: {C_BG2};
 border: 1px solid {C_BORDER};
 border-radius: 8px;
 }}
 """)
 outer = QVBoxLayout(bar)
 outer.setContentsMargins(10, 6, 10, 6)
 outer.setSpacing(4)

 # ── Üst satır: Başlık + Tarih + Şablon + Temel işlemler ────────────
 ust = QHBoxLayout()
 ust.setSpacing(6)

 lbl = QLabel("İnşaat İş Programı")
 lbl.setStyleSheet(
 f"color: {C_ACCENT}; font-size: 14px; font-weight: bold;"
 "border: none; background: transparent;"
 )
 ust.addWidget(lbl)
 ust.addStretch()

 # Proje başlangıç tarihi
 lbl_bas = QLabel("Proje Başlangıcı:")
 lbl_bas.setStyleSheet("color: #95a5a6; font-size: 11px; border: none; background: transparent;")
 ust.addWidget(lbl_bas)
 self.dt_proje_bas = QDateEdit()
 self.dt_proje_bas.setCalendarPopup(True)
 self.dt_proje_bas.setDate(QDate.currentDate())
 self.dt_proje_bas.setStyleSheet(
 f"background: {C_BG3}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
 "border-radius: 4px; padding: 3px;"
 )
 self.dt_proje_bas.setFixedWidth(115)
 ust.addWidget(self.dt_proje_bas)

 # Şablon
 self.cmb_sablon = QComboBox()
 self._sablon_doldur()
 self.cmb_sablon.setFixedWidth(190)
 self.cmb_sablon.setStyleSheet(
 f"background: {C_BG3}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
 "border-radius: 4px; padding: 3px;"
 )
 ust.addWidget(self.cmb_sablon)

 btn_sablon = QPushButton("Şablon Yükle")
 btn_sablon.setStyleSheet(BTN_PRIMARY)
 btn_sablon.clicked.connect(self._sablon_yukle)
 ust.addWidget(btn_sablon)

 btn_hesapla = QPushButton("Hesapla")
 btn_hesapla.setStyleSheet(BTN_SUCCESS)
 btn_hesapla.clicked.connect(self.hesapla)
 ust.addWidget(btn_hesapla)

 btn_baseline = QPushButton("Baseline")
 btn_baseline.setStyleSheet(BTN_PRIMARY)
 btn_baseline.clicked.connect(self._baseline_kaydet)
 ust.addWidget(btn_baseline)

 btn_export = QPushButton("Excel")
 btn_export.setStyleSheet(BTN_PRIMARY)
 btn_export.clicked.connect(self._excel_export)
 ust.addWidget(btn_export)

 outer.addLayout(ust)

 # ── Alt satır: Risk araçları + Sözleşme tarihi ──────────────────────
 alt = QHBoxLayout()
 alt.setSpacing(6)

 btn_beklenmedik = QPushButton("Beklenmedik Durum")
 btn_beklenmedik.setStyleSheet(BTN_DANGER)
 btn_beklenmedik.clicked.connect(self._beklenmedik_durum_ekle)
 alt.addWidget(btn_beklenmedik)

 btn_pert = QPushButton("PERT Analizi")
 btn_pert.setStyleSheet(f"""
 QPushButton {{
 background: #2a1a3a;
 color: {C_ACCENT2};
 border: 1px solid {C_ACCENT2};
 border-radius: 6px;
 padding: 5px 14px;
 font-weight: bold;
 }}
 QPushButton:hover {{ background: {C_ACCENT2}; color: #000; }}
 """)
 btn_pert.clicked.connect(self._pert_analizi_goster)
 alt.addWidget(btn_pert)

 alt.addStretch()

 lbl_soz = QLabel("Sözleşme Bitişi:")
 lbl_soz.setStyleSheet("color: #e67e22; font-size: 11px; border: none; background: transparent;")
 alt.addWidget(lbl_soz)
 self.dt_sozlesme = QDateEdit()
 self.dt_sozlesme.setCalendarPopup(True)
 self.dt_sozlesme.setDate(QDate.currentDate().addDays(180))
 self.dt_sozlesme.setStyleSheet(
 f"background: {C_BG3}; color: {C_WARNING}; border: 1px solid {C_WARNING}44;"
 "border-radius: 4px; padding: 3px;"
 )
 self.dt_sozlesme.setFixedWidth(115)
 alt.addWidget(self.dt_sozlesme)

 outer.addLayout(alt)

 return bar

 # ── SEKME 5: TEKNİK RAPOR ─────────────────────────────────────────────────

 def _build_teknik_rapor_sekmesi(self) -> QWidget:
 """
 Teknik Rapor sekmesi: Algoritma metodolojisi, standart referanslar
 ve sürüm bilgisi. Müşteri/idare sunumları için kaynak doküman.
 """
 w = QWidget()
 lay = QVBoxLayout(w)
 lay.setContentsMargins(10, 10, 10, 10)
 lay.setSpacing(8)

 # İç sekme widget
 ic_tabs = QTabWidget()
 ic_tabs.setStyleSheet(f"""
 QTabWidget::pane {{
 border: 1px solid {C_BORDER}; background: {C_BG};
 }}
 QTabBar::tab {{
 background: {C_BG2}; color: {C_TEXT_DIM};
 padding: 8px 16px; margin-right: 2px;
 border-top-left-radius: 5px; border-top-right-radius: 5px;
 font-size: 12px; font-weight: bold;
 }}
 QTabBar::tab:selected {{
 background: {C_BG3}; color: {C_ACCENT2};
 border-bottom: 2px solid {C_ACCENT2};
 }}
 """)

 # ── İç Sekme 1: Metodoloji ────────────────────────────────────────
 metod_w = QWidget()
 metod_lay = QVBoxLayout(metod_w)
 metod_lay.setContentsMargins(12, 12, 12, 12)

 metod_txt = QTextEdit()
 metod_txt.setReadOnly(True)
 metod_txt.setStyleSheet(
 f"background: {C_BG2}; color: {C_TEXT}; border: none;"
 "border-radius: 6px; padding: 10px; font-size: 12px; font-family: Consolas;"
 )
 metod_icerik = """KRİTİK YOL ANALİZİ (CPM — Critical Path Method)
══════════════════════════════════════════════════
Algoritma : Kahn's topolojik sıralama (yönlü asiklik graf — DAG)
Forward Pass : ES (Early Start) ve EF (Early Finish) hesabı
 ES_i = max(EF_j + lag) for all predecessors j
 EF_i = ES_i + duration_i
Backward Pass: LS (Late Start) ve LF (Late Finish) hesabı
 LF_i = min(LS_j - lag) for all successors j
 LS_i = LF_i - duration_i
Float : float_gun = LF - EF (toplam bolluk, gün)
Kritik Yol : float_gun == 0 olan tüm görevlerin zinciri


KAZANILMIŞ DEĞER YÖNETİMİ (EVM — PMBOK 7 Uyumlu)
══════════════════════════════════════════════════
PV = Planned Value (BCWS) → Planlanan iş değeri
EV = Earned Value (BCWP) → Tamamlanan işin bütçe değeri
AC = Actual Cost (ACWP) → Fiili harcama
BAC = Budget at Completion → Toplam proje bütçesi

CPI = EV / AC → ≥ 1.0: tasarruf | < 1.0: aşım
SPI = EV / PV → ≥ 1.0: önde | < 1.0: geride
CV = EV - AC → Maliyet farkı (TL)
SV = EV - PV → Zaman farkı (TL)
EAC = BAC / CPI → Proje sonunda tahmin edilen toplam maliyet
ETC = EAC - AC → Kalan maliyet tahmini
VAC = BAC - EAC → Bitişteki tahmini fark
TCPI = (BAC - EV) / (BAC - AC) → Hedefte kalmak için gereken CPI


PERT — 3 NOKTALI TAHMİN (Beta Dağılımı)
══════════════════════════════════════════════════
Kaynak : Malcolm et al. (1959), Operations Research 7(5)
 PMBOK 7th Edition, TS ISO 21500:2022

t_e = (t_o + 4 × t_m + t_p) / 6 Beklenen süre
σ = (t_p - t_o) / 6 Standart sapma
σ² = σ² Varyans

Proje_σ = √(Σ σ²_kritik_görevler) Merkezi Limit Teoremi (CLT)
 Not: Görevlerin bağımsız olduğu varsayılır.

P-değerleri (Standart Normal Dağılım):
 P50 → z=0.000 (Beklenen senaryo)
 P80 → z=0.842 (İhale teklifinde önerilen tampon)
 P90 → z=1.282 (Kamu projeleri için önerilen)
 P95 → z=1.645 (Yüksek riskli projeler)


BETON KÜRLEME HESABI (ACI 305R-10 + TS 500)
══════════════════════════════════════════════════
Temel formül:
 t_güvenli = t_temel × k_sıcaklık × k_çimento × k_güvenlik

 k_güvenlik = 1.20 (sabit güvenlik katsayısı)
 k_sıcaklık : Maturity Method (ASTM C1074) tablosundan
 k_çimento : TS EN 197-1 çimento sınıfı katsayısı

 Donma riski (< 0°C) : Döküm durdur uyarısı — fiziksel limit


KAYNAK DENGELEME (Resource Leveling)
══════════════════════════════════════════════════
Algoritma : Minimum gecikme prensibi
Öncelik : Bolluk > olan görev önce kaydırılır (kritik görevler son)
İterasyon : Maksimum 50 iterasyon (sonsuz döngü koruması)
Çıktı : Kaydırma günü, kritik yol etkisi, kaynak histogram"""

 metod_txt.setPlainText(metod_icerik)
 metod_lay.addWidget(metod_txt)
 ic_tabs.addTab(metod_w, "Metodoloji")

 # ── İç Sekme 2: Teknik Referanslar ───────────────────────────────
 ref_w = QWidget()
 ref_lay = QVBoxLayout(ref_w)
 ref_lay.setContentsMargins(12, 12, 12, 12)

 tbl_ref = QTableWidget()
 tbl_ref.setColumnCount(3)
 tbl_ref.setHorizontalHeaderLabels(["Standart / Kaynak", "Konu", "Uygulama"])
 tbl_ref.setStyleSheet(TABLE_STYLE)
 tbl_ref.horizontalHeader().setSectionResizeMode(
 1, QHeaderView.ResizeMode.Stretch
 )
 tbl_ref.verticalHeader().setVisible(False)
 tbl_ref.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 tbl_ref.setAlternatingRowColors(True)

 referanslar = [
 ("PMBOK 7 (PMI, 2021)", "EVM, PERT, Proje Yönetimi", "EVM motoru, PERT motoru"),
 ("TS EN 197-1", "Çimento Sınıflandırması", "Malzeme sınıfı referansı"),
 ("4734 / 4735 Sayılı Kanun", "Kamu İhale Mevzuatı", "Hakediş modülü"),
 ("TS ISO 21500:2022", "Proje Yönetimi Kılavuzu", "PERT motoru, proses grupları"),
 ("Malcolm et al. (1959)", "PERT Tekniğinin Kaynağı", "3 nokta tahmin formülleri"),
 ("Kahn (1962)", "Topolojik Sıralama Algoritması","CPM / DAG hesabı"),
 ]
 tbl_ref.setRowCount(len(referanslar))
 for i, (std, konu, uyg) in enumerate(referanslar):
 tbl_ref.setItem(i, 0, QTableWidgetItem(std))
 tbl_ref.setItem(i, 1, QTableWidgetItem(konu))
 tbl_ref.setItem(i, 2, QTableWidgetItem(uyg))
 # Standart sütununu vurgula
 it = tbl_ref.item(i, 0)
 it.setForeground(QColor(C_ACCENT2))

 ref_lay.addWidget(tbl_ref)
 ic_tabs.addTab(ref_w, "Teknik Referanslar")

 # ── İç Sekme 3: Sürüm Bilgisi ────────────────────────────────────
 surum_w = QWidget()
 surum_lay = QVBoxLayout(surum_w)
 surum_lay.setContentsMargins(12, 12, 12, 12)

 surum_txt = QTextEdit()
 surum_txt.setReadOnly(True)
 surum_txt.setStyleSheet(
 f"background: {C_BG2}; color: {C_TEXT}; border: none;"
 "border-radius: 6px; padding: 10px; font-size: 12px; font-family: Consolas;"
 )
 surum_icerik = """INSAAT METRAJ PRO — Is Programi Modulu
══════════════════════════════════════════════════

Uygulama : Insaat Metraj Pro
Surum : 2.1 (Is Programi Pro modulu)
Modul : Gantt Pro — CPM + EVM + PERT + Kaynak Dengeleme

Teknik Altyapi:
 Dil : Python 3.8+
 Arayuz : PyQt6
 Veritabani : SQLite (offline-first mimari)
 Mimari : Katmanli — Core (is mantigi) + UI (gorunum) ayirimi

Algoritmalar:
 CPM : Kahn's DAG topolojik siralama
 EVM : PMBOK 7 uyumlu formul seti
 PERT : Beta dagilimi 3 nokta tahmin
 Kurleme : ACI 305R-10 + TS 500 maturity yaklasimlari
 Kaynak : Minimum gecikme, bolluk oncelik sirasi

Hedef Kullanici:
 Proje yoneticisi, insaat muhendisi, taseron ve musterilere
 kapsamli is programi takibi ve hakedis yonetimi saglar.

Veri Guvenigi:
 Decimal ile mali hesaplamalar (IEEE 754 float hatasi yok)
 Tarih dogrulamasi: datetime.datetime nesneleri
 Olasiliksal PERT: beta dagilimi yaklasimi (CLT uyumlu)"""

 surum_txt.setPlainText(surum_icerik)
 surum_lay.addWidget(surum_txt)
 ic_tabs.addTab(surum_w, "Surum Bilgisi")

 lay.addWidget(ic_tabs)
 return w

 # ── SEKME 1: BUGÜN ────────────────────────────────────────────────────────

 def _build_bugün_sekmesi(self) -> QWidget:
 w = QWidget()
 lay = QVBoxLayout(w)
 lay.setContentsMargins(10, 10, 10, 10)
 lay.setSpacing(10)

 # ── KPI Kartları ────────────────────────────────────────
 kpi_lay = QHBoxLayout()
 kpi_lay.setSpacing(10)

 self.kpi_toplam = KPIKarti("Toplam Görev", "—", "", C_ACCENT)
 self.kpi_devam = KPIKarti("Devam Eden", "—", "", C_WARNING)
 self.kpi_tamamlan = KPIKarti("Tamamlanan", "—", "", C_SUCCESS)
 self.kpi_gecikme = KPIKarti("Geciken", "—", "", C_DANGER)
 self.kpi_bitis = KPIKarti("Tahmini Bitiş", "—", "", C_ACCENT2)
 self.kpi_float = KPIKarti("Ort. Float (Gün)","—", "", C_TEXT_DIM)

 for k in [self.kpi_toplam, self.kpi_devam, self.kpi_tamamlan,
 self.kpi_gecikme, self.kpi_bitis, self.kpi_float]:
 kpi_lay.addWidget(k)

 lay.addLayout(kpi_lay)

 # ── Trafik Işığı Satırı ──────────────────────────────────
 ti_lay = QHBoxLayout()
 self.ti_proje = TIGostergesi("Proje Durumu")
 self.ti_butce = TIGostergesi("Bütçe Durumu")
 self.ti_takvim = TIGostergesi("Takvim Durumu")
 self.ti_kritik_yol = TIGostergesi("Kritik Yol")

 for ti in [self.ti_proje, self.ti_butce, self.ti_takvim, self.ti_kritik_yol]:
 ti_lay.addWidget(ti)
 ti_lay.addStretch()
 lay.addLayout(ti_lay)

 # ── Bugün Yapılacaklar ────────────────────────────────────
 bugun_grp = QGroupBox("Bugün Aktif İş Kalemleri (Puantaj)")
 bugun_grp.setStyleSheet(
 f"QGroupBox {{ color: {C_ACCENT}; font-weight: bold;"
 f"border: 1px solid {C_BORDER}; border-radius: 6px;"
 f"padding-top: 14px; background: {C_CARD}; }}"
 )
 b_lay = QVBoxLayout(bugun_grp)
 self.tbl_bugun = QTableWidget()
 self.tbl_bugun.setColumnCount(6)
 self.tbl_bugun.setHorizontalHeaderLabels([
 "WBS", "İş Kalemi", "Ekip/Taşeron", "Süre", "Hakedişe Esas İlerleme", "Durum"
 ])
 self.tbl_bugun.setStyleSheet(TABLE_STYLE)
 self.tbl_bugun.horizontalHeader().setSectionResizeMode(
 1, QHeaderView.ResizeMode.Stretch
 )
 self.tbl_bugun.setAlternatingRowColors(True)
 self.tbl_bugun.verticalHeader().setVisible(False)
 self.tbl_bugun.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 b_lay.addWidget(self.tbl_bugun)
 lay.addWidget(bugun_grp)

 # ── Kritik Yol Özeti ─────────────────────────────────────
 kp_grp = QGroupBox("Kritik Yol")
 kp_grp.setStyleSheet(
 f"QGroupBox {{ color: {C_DANGER}; font-weight: bold;"
 f"border: 1px solid {C_DANGER}44; border-radius: 6px;"
 f"padding-top: 14px; background: {C_CARD}; }}"
 )
 kp_lay = QVBoxLayout(kp_grp)
 self.lbl_kritik_yol = QLabel(
 "Henüz hesaplanmadı. 'Hesapla' butonuna basın."
 )
 self.lbl_kritik_yol.setWordWrap(True)
 self.lbl_kritik_yol.setStyleSheet(
 f"color: {C_TEXT}; padding: 6px; background: transparent; border: none;"
 )
 kp_lay.addWidget(self.lbl_kritik_yol)
 lay.addWidget(kp_grp)

 # ── Yorum Paneli ─────────────────────────────────────────
 self.txt_yorum = QTextEdit()
 self.txt_yorum.setReadOnly(True)
 self.txt_yorum.setMaximumHeight(90)
 self.txt_yorum.setStyleSheet(
 f"background: {C_CARD}; color: {C_TEXT_DIM}; border: 1px solid {C_BORDER};"
 "border-radius: 6px; padding: 6px; font-size: 11px;"
 )
 self.txt_yorum.setPlainText("EVM analizi için görevlere bütçe ve ilerleme bilgisi girin.")
 lay.addWidget(self.txt_yorum)

 return w

 # ── SEKME 2: PROGRAM ──────────────────────────────────────────────────────

 def _build_program_sekmesi(self) -> QWidget:
 w = QWidget()
 lay = QVBoxLayout(w)
 lay.setContentsMargins(6, 6, 6, 6)
 lay.setSpacing(6)

 # Araç çubuğu
 t_bar = QHBoxLayout()
 t_bar.setSpacing(6)

 btn_ekle = QPushButton("Görev Ekle")
 btn_ekle.setStyleSheet(BTN_SUCCESS)
 btn_ekle.clicked.connect(self._gorev_ekle)
 btn_duzenle = QPushButton("Düzenle")
 btn_duzenle.setStyleSheet(BTN_PRIMARY)
 btn_duzenle.clicked.connect(self._gorev_duzenle)
 btn_sil = QPushButton("Sil")
 btn_sil.setStyleSheet(BTN_DANGER)
 btn_sil.clicked.connect(self._gorev_sil)
 btn_yukari = QPushButton("Yukari")
 btn_yukari.setStyleSheet(BTN_PRIMARY)
 btn_yukari.setFixedWidth(60)
 btn_asagi = QPushButton("Asagi")
 btn_asagi.setStyleSheet(BTN_PRIMARY)
 btn_asagi.setFixedWidth(60)

 self.chk_sadece_kritik = QCheckBox("Sadece Kritik")
 self.chk_sadece_kritik.setStyleSheet(
 f"color: {C_DANGER}; font-weight: bold;"
 )
 self.chk_sadece_kritik.stateChanged.connect(self._guncelle_gorev_tablosu)

 for w2 in [btn_ekle, btn_duzenle, btn_sil, btn_yukari, btn_asagi,
 self.chk_sadece_kritik]:
 t_bar.addWidget(w2)
 t_bar.addStretch()
 lay.addLayout(t_bar)

 # Splitter: Görev tablosu + Gantt grafiği
 splitter = QSplitter(Qt.Orientation.Vertical)

 # Görev tablosu
 self.tbl_gorevler = QTableWidget()
 self.tbl_gorevler.setColumnCount(10)
 self.tbl_gorevler.setHorizontalHeaderLabels([
 "WBS", "İş Kalemi", "Süre", "Başlangıç", "Bitiş",
 "Hakediş İlerleme", "Float", "Ekip/Taşeron", "Durum", "Kritik"
 ])
 self.tbl_gorevler.setStyleSheet(TABLE_STYLE)
 self.tbl_gorevler.horizontalHeader().setSectionResizeMode(
 1, QHeaderView.ResizeMode.Stretch
 )
 self.tbl_gorevler.setAlternatingRowColors(True)
 self.tbl_gorevler.verticalHeader().setVisible(False)
 self.tbl_gorevler.setSelectionBehavior(
 QTableWidget.SelectionBehavior.SelectRows
 )
 self.tbl_gorevler.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 splitter.addWidget(self.tbl_gorevler)

 # Gantt grafiği
 self.gantt_grafik = GanttChartGrafik()
 splitter.addWidget(self.gantt_grafik)
 splitter.setSizes([280, 380])

 lay.addWidget(splitter)
 return w

 # ── SEKME 3: MALİYET / EVM ────────────────────────────────────────────────

 def _build_maliyet_sekmesi(self) -> QWidget:
 w = QWidget()
 lay = QVBoxLayout(w)
 lay.setContentsMargins(10, 10, 10, 10)
 lay.setSpacing(10)

 # EVM KPI Kartları
 evm_lay = QHBoxLayout()
 evm_lay.setSpacing(10)

 self.kpi_bac = KPIKarti("Toplam Bütçe (BAC)", "—", "", C_ACCENT)
 self.kpi_ev = KPIKarti("Kazanılan Değer (EV)", "—", "", C_SUCCESS)
 self.kpi_ac = KPIKarti("Gerçek Maliyet (AC)", "—", "", C_DANGER)
 self.kpi_cpi = KPIKarti("CPI (Maliyet Perf.)", "—", "", C_ACCENT2)
 self.kpi_spi = KPIKarti("SPI (Zaman Perf.)", "—", "", C_ACCENT2)
 self.kpi_eac = KPIKarti("Proje Bitişte (EAC)", "—", "", C_WARNING)

 for k in [self.kpi_bac, self.kpi_ev, self.kpi_ac,
 self.kpi_cpi, self.kpi_spi, self.kpi_eac]:
 evm_lay.addWidget(k)
 lay.addLayout(evm_lay)

 # EVM Açıklama bandı
 self.lbl_evm_yorum = QLabel("EVM hesaplanmadı.")
 self.lbl_evm_yorum.setWordWrap(True)
 self.lbl_evm_yorum.setStyleSheet(
 f"background: {C_CARD}; color: {C_TEXT_DIM};"
 f"border: 1px solid {C_BORDER}; border-radius: 6px;"
 "padding: 8px; font-size: 11px;"
 )
 lay.addWidget(self.lbl_evm_yorum)

 # EVM Görev Tablosu
 evm_grp = QGroupBox("Görev Bazlı EVM Tablosu")
 evm_grp.setStyleSheet(
 f"QGroupBox {{ color: {C_ACCENT}; font-weight: bold;"
 f"border: 1px solid {C_BORDER}; border-radius: 6px; padding-top: 14px; }}"
 )
 eg_lay = QVBoxLayout(evm_grp)
 self.tbl_evm = QTableWidget()
 self.tbl_evm.setColumnCount(8)
 self.tbl_evm.setHorizontalHeaderLabels([
 "WBS", "İş Kalemi", "Bütçe (BAC)", "PV", "EV",
 "AC (Gerçek)", "CPI", "SPI"
 ])
 self.tbl_evm.setStyleSheet(TABLE_STYLE)
 self.tbl_evm.horizontalHeader().setSectionResizeMode(
 1, QHeaderView.ResizeMode.Stretch
 )
 self.tbl_evm.verticalHeader().setVisible(False)
 self.tbl_evm.setAlternatingRowColors(True)
 self.tbl_evm.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 eg_lay.addWidget(self.tbl_evm)
 lay.addWidget(evm_grp)

 # S-Eğrisi notu
 self.lbl_segri = QLabel(
 "S-Eğrisi: Matplotlib grafiği için tüm görevlere Bütçe ve Gerçek Maliyet girin."
 )
 self.lbl_segri.setStyleSheet(
 f"color: {C_TEXT_DIM}; padding: 4px; background: transparent; font-size: 11px;"
 )
 lay.addWidget(self.lbl_segri)

 return w

 # ── SEKME 4: KAYNAKLAR ────────────────────────────────────────────────────

 def _build_kaynaklar_sekmesi(self) -> QWidget:
 w = QWidget()
 lay = QVBoxLayout(w)
 lay.setContentsMargins(10, 10, 10, 10)
 lay.setSpacing(10)

 # Araç çubuğu
 k_bar = QHBoxLayout()
 btn_cakisma = QPushButton("Çakışma Tara")
 btn_cakisma.setStyleSheet(BTN_PRIMARY)
 btn_cakisma.clicked.connect(self._cakisma_tara)
 btn_dengele = QPushButton("Otomatik Dengele")
 btn_dengele.setStyleSheet(BTN_SUCCESS)
 btn_dengele.clicked.connect(self._otomatik_dengele)

 for b in [btn_cakisma, btn_dengele]:
 k_bar.addWidget(b)
 k_bar.addStretch()
 lay.addLayout(k_bar)

 # Çakışma tablosu
 cak_grp = QGroupBox("Kaynak Çakışmaları")
 cak_grp.setStyleSheet(
 f"QGroupBox {{ color: {C_WARNING}; font-weight: bold;"
 f"border: 1px solid {C_WARNING}44; border-radius: 6px; padding-top: 14px; }}"
 )
 cak_lay = QVBoxLayout(cak_grp)
 self.tbl_cakisma = QTableWidget()
 self.tbl_cakisma.setColumnCount(5)
 self.tbl_cakisma.setHorizontalHeaderLabels([
 "Kaynak", "Tarih", "Çakışan Görevler", "Kapasite Aşımı", "Durum"
 ])
 self.tbl_cakisma.setStyleSheet(TABLE_STYLE)
 self.tbl_cakisma.horizontalHeader().setSectionResizeMode(
 2, QHeaderView.ResizeMode.Stretch
 )
 self.tbl_cakisma.verticalHeader().setVisible(False)
 self.tbl_cakisma.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 cak_lay.addWidget(self.tbl_cakisma)
 lay.addWidget(cak_grp)

 # Dengeleme sonucu
 den_grp = QGroupBox("Dengeleme Raporu")
 den_grp.setStyleSheet(
 f"QGroupBox {{ color: {C_SUCCESS}; font-weight: bold;"
 f"border: 1px solid {C_SUCCESS}44; border-radius: 6px; padding-top: 14px; }}"
 )
 den_lay = QVBoxLayout(den_grp)
 self.tbl_dengele = QTableWidget()
 self.tbl_dengele.setColumnCount(6)
 self.tbl_dengele.setHorizontalHeaderLabels([
 "Görev", "Kaynak", "Eski Başlangıç", "Yeni Başlangıç",
 "Kaydırma (Gün)", "Kritik Etki"
 ])
 self.tbl_dengele.setStyleSheet(TABLE_STYLE)
 self.tbl_dengele.horizontalHeader().setSectionResizeMode(
 0, QHeaderView.ResizeMode.Stretch
 )
 self.tbl_dengele.verticalHeader().setVisible(False)
 self.tbl_dengele.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 den_lay.addWidget(self.tbl_dengele)
 lay.addWidget(den_grp)

 # Kaynak Kapasitesi Tanımlama
 kap_grp = QGroupBox("Ekip/Taşeron Kapasitesi Tanımla")
 kap_grp.setStyleSheet(
 f"QGroupBox {{ color: {C_ACCENT}; font-weight: bold;"
 f"border: 1px solid {C_ACCENT}44; border-radius: 6px; padding-top: 14px; }}"
 )
 kap_form = QHBoxLayout(kap_grp)
 self.inp_kap_ad = QLineEdit()
 self.inp_kap_ad.setPlaceholderText("Kaynak adı")
 self.inp_kap_kapasite = QSpinBox()
 self.inp_kap_kapasite.setRange(1, 20)
 self.inp_kap_kapasite.setValue(1)
 self.inp_kap_maliyet = QDoubleSpinBox()
 self.inp_kap_maliyet.setRange(0, 99999)
 self.inp_kap_maliyet.setSuffix(" TL/gün")
 btn_kap_ekle = QPushButton("Ekle")
 btn_kap_ekle.setStyleSheet(BTN_PRIMARY)
 btn_kap_ekle.clicked.connect(self._kapasite_ekle)

 for lbl, wgt in [
 ("Kaynak:", self.inp_kap_ad),
 ("Kapasite:", self.inp_kap_kapasite),
 ("Maliyet:", self.inp_kap_maliyet),
 ]:
 kap_form.addWidget(QLabel(lbl))
 kap_form.addWidget(wgt)
 kap_form.addWidget(btn_kap_ekle)
 kap_form.addStretch()
 lay.addWidget(kap_grp)

 return w

 # ── İŞ LOJİĞİ ────────────────────────────────────────────────────────────

 def hesapla(self) -> None:
 """CPM + EVM hesapla, tüm sekmeleri güncelle."""
 if not self.engine.tasks:
 self._durum("Once gorev ekleyin veya sablon yukleyin.")
 return

 proje_bas = self.dt_proje_bas.date().toPyDate()
 proje_bas_dt = datetime.combine(proje_bas, datetime.min.time())

 logger.info(
 f"CPM hesabı başlatıldı: {len(self.engine.tasks)} iş kalemi, "
 f"başlangıç {proje_bas_dt.strftime('%d.%m.%Y')}"
 )

 sonuc = self.engine.calculate_schedule(proje_bas_dt)
 if "error" in sonuc:
 QMessageBox.critical(self, "Hata", sonuc["error"])
 return

 self._guncelle_bugun_sekmesi(sonuc)
 self._guncelle_gorev_tablosu()
 self.gantt_grafik.ciz(self.engine)
 self._guncelle_evm()
 self._durum(
 f"Hesaplandi — {sonuc['toplam_is']} is kalemi, "
 f"proje bitis: {sonuc['proje_bitis'].strftime('%d.%m.%Y')}, "
 f"kritik: {sonuc['kritik_is_sayisi']} kalem"
 )

 def _guncelle_bugun_sekmesi(self, cpm_sonuc: Dict) -> None:
 """Bugün sekmesi KPI ve tablo güncellemesi."""
 tasks = list(self.engine.tasks.values())
 tamamlanan = sum(1 for t in tasks if t.ilerleme >= 100)
 devam = sum(1 for t in tasks if 0 < t.ilerleme < 100)
 geciken = sum(1 for t in tasks
 if t.early_start and t.early_start < datetime.now()
 and t.ilerleme < 100)

 self.kpi_toplam.guncelle(str(cpm_sonuc["toplam_is"]))
 self.kpi_devam.guncelle(str(devam), C_WARNING)
 self.kpi_tamamlan.guncelle(str(tamamlanan), C_SUCCESS)
 self.kpi_gecikme.guncelle(str(geciken), C_DANGER if geciken > 0 else C_SUCCESS)
 self.kpi_float.guncelle(f"{cpm_sonuc.get('ortalama_float', 0):.1f}")

 if cpm_sonuc["proje_bitis"]:
 self.kpi_bitis.guncelle(
 cpm_sonuc["proje_bitis"].strftime("%d.%m.%Y")
 )

 # Proje durumu
 if geciken == 0 and devam + tamamlanan > 0:
 self.ti_proje.guncelle("yesil", "Normal Seyrediyor")
 elif geciken <= len(tasks) * 0.1:
 self.ti_proje.guncelle("sari", f"{geciken} Gecikme")
 else:
 self.ti_proje.guncelle("kirmizi", f" {geciken} Gecikme!")

 # Kritik yol etiketi
 kritik_isimler = [
 self.engine.tasks[tid].ad
 for tid in cpm_sonuc.get("kritik_yol", [])
 if tid in self.engine.tasks
 ]
 if kritik_isimler:
 yol_str = " → ".join(kritik_isimler[:6])
 if len(kritik_isimler) > 6:
 yol_str += f" … (+{len(kritik_isimler)-6} görev)"
 self.lbl_kritik_yol.setText(f"Proje Süresi: {cpm_sonuc['toplam_sure_gun']} gün\n{yol_str}")
 self.ti_kritik_yol.guncelle(
 "kirmizi" if len(kritik_isimler) > len(tasks) * 0.4 else "sari",
 f"{len(kritik_isimler)} Kritik Görev"
 )
 else:
 self.lbl_kritik_yol.setText("Kritik yol yok (tüm görevlerde bolluk var).")

 # Bugün tablosu
 bugun = datetime.now()
 aktif = [
 t for t in tasks
 if t.early_start and t.early_finish
 and t.early_start <= bugun <= t.early_finish
 and t.ilerleme < 100
 ]
 self.tbl_bugun.setRowCount(len(aktif))
 for i, task in enumerate(aktif):
 durum = task.get_durum()
 durum_metin = {
 "tamamlandi": " Tamamlandı",
 "devam_ediyor":" Devam Ediyor",
 "gecikmis": " Gecikmeli",
 "baslanmadi": " Başlamadı",
 }.get(durum, durum)

 for j, val in enumerate([
 task.wbs_kodu or "—",
 task.ad,
 task.kaynak or "—",
 f"{task.sure_gun} gün",
 f"%{task.ilerleme:.0f}",
 durum_metin,
 ]):
 item = QTableWidgetItem(str(val))
 item.setForeground(QColor(task.get_durum_rengi()))
 self.tbl_bugun.setItem(i, j, item)

 def _guncelle_gorev_tablosu(self) -> None:
 """Program sekmesi görev tablosunu güncelle."""
 sadece_kritik = self.chk_sadece_kritik.isChecked()
 tasks = sorted(
 self.engine.tasks.values(),
 key=lambda t: (t.wbs_kodu or "999", t.early_start or datetime.max)
 )
 if sadece_kritik:
 tasks = [t for t in tasks if t.kritik]

 self.tbl_gorevler.setRowCount(len(tasks))
 for i, task in enumerate(tasks):
 def it(v, renk=None):
 item = QTableWidgetItem(str(v))
 if renk:
 item.setForeground(QColor(renk))
 return item

 renk = C_KRITIK if task.kritik else C_TEXT

 self.tbl_gorevler.setItem(i, 0, it(task.wbs_kodu or "—"))
 self.tbl_gorevler.setItem(i, 1, it(task.ad, renk))
 self.tbl_gorevler.setItem(i, 2, it(f"{task.sure_gun}g"))
 self.tbl_gorevler.setItem(
 i, 3, it(task.early_start.strftime("%d.%m.%Y")
 if task.early_start else "—")
 )
 self.tbl_gorevler.setItem(
 i, 4, it(task.early_finish.strftime("%d.%m.%Y")
 if task.early_finish else "—")
 )

 # İlerleme progress
 prog = QProgressBar()
 prog.setValue(int(task.ilerleme))
 prog.setStyleSheet(f"""
 QProgressBar {{ background: {C_BG3}; border-radius: 4px;
 text-align: center; color: #fff; font-size: 10px; }}
 QProgressBar::chunk {{ background: {C_SUCCESS if task.ilerleme >= 100 else C_ACCENT}; border-radius: 4px; }}
 """)
 self.tbl_gorevler.setCellWidget(i, 5, prog)

 self.tbl_gorevler.setItem(
 i, 6, it(f"{task.float_gun}g",
 C_DANGER if task.float_gun == 0 else C_TEXT_DIM)
 )
 self.tbl_gorevler.setItem(i, 7, it(task.kaynak or "—"))
 self.tbl_gorevler.setItem(i, 8, it(task.get_durum()))
 self.tbl_gorevler.setItem(
 i, 9, it(" Kritik" if task.kritik else "—",
 C_KRITIK if task.kritik else C_TEXT_DIM)
 )

 def _guncelle_evm(self) -> None:
 """Maliyet/EVM sekmesini güncelle."""
 gorevler_evm: List[GorevEVM] = []

 for tid, task in self.engine.tasks.items():
 butce = self._butce.get(tid, Decimal("0"))
 gercek = self._gercek_mal.get(tid, Decimal("0"))
 if butce == 0:
 continue

 # Bugün itibarıyla planlanan ilerleme
 planlanan = GanttChartGrafik._planlanan_ilerleme(task)

 gorevler_evm.append(GorevEVM(
 id=tid,
 ad=task.ad,
 butce_tl=butce,
 ilerleme_yuzde=task.ilerleme,
 gercek_maliyet_tl=gercek,
 planlanan_ilerleme=planlanan,
 kaynak=task.kaynak,
 wbs_kodu=task.wbs_kodu or "",
 kritik=task.kritik,
 ))

 if not gorevler_evm:
 self.lbl_evm_yorum.setText(
 " EVM için görevlere Bütçe ve Gerçek Maliyet bilgisi girin "
 "(Görev Ekle / Düzenle dialogundan)."
 )
 return

 sonuc = self.evm_eng.hesapla(gorevler_evm)

 # KPI kartları
 self.kpi_bac.guncelle(f"{float(sonuc.bac_tl):,.0f} TL", C_ACCENT)
 self.kpi_ev.guncelle(f"{float(sonuc.ev_tl):,.0f} TL", C_SUCCESS)
 self.kpi_ac.guncelle(f"{float(sonuc.ac_tl):,.0f} TL",
 C_DANGER if sonuc.ac_tl > sonuc.ev_tl else C_SUCCESS)
 self.kpi_cpi.guncelle(
 f"{sonuc.cpi:.2f}",
 {"yesil": C_SUCCESS, "sari": C_WARNING, "kirmizi": C_DANGER}[sonuc.butce_durumu]
 )
 self.kpi_spi.guncelle(
 f"{sonuc.spi:.2f}",
 {"yesil": C_SUCCESS, "sari": C_WARNING, "kirmizi": C_DANGER}[sonuc.takvim_durumu]
 )
 self.kpi_eac.guncelle(f"{float(sonuc.eac_tl):,.0f} TL",
 C_DANGER if sonuc.eac_tl > sonuc.bac_tl else C_SUCCESS)

 # Trafik ışıkları
 self.ti_butce.guncelle(
 sonuc.butce_durumu,
 f"CPI={sonuc.cpi:.2f}"
 )
 self.ti_takvim.guncelle(
 sonuc.takvim_durumu,
 f"SPI={sonuc.spi:.2f}"
 )

 # Yorum
 self.lbl_evm_yorum.setText(sonuc.yorum)
 self.txt_yorum.setPlainText(sonuc.yorum)

 # Görev EVM tablosu
 detaylar = sonuc.gorev_detaylari
 self.tbl_evm.setRowCount(len(detaylar))
 for i, d in enumerate(detaylar):
 for j, (val, renk) in enumerate([
 (d.get("wbs", "—"), None),
 (d.get("ad", "—"), None),
 (f"{d.get('bac', 0):,.0f} TL", None),
 (f"{d.get('pv', 0):,.0f} TL", None),
 (f"{d.get('ev', 0):,.0f} TL", None),
 (f"{d.get('ac', 0):,.0f} TL", None),
 (f"{d.get('cpi', 1):.2f}", d.get("cpi_renk", C_TEXT)),
 (f"{d.get('spi', 1):.2f}", d.get("spi_renk", C_TEXT)),
 ]):
 item = QTableWidgetItem(str(val))
 if renk:
 item.setForeground(QColor(renk))
 self.tbl_evm.setItem(i, j, item)

 def _cakisma_tara(self) -> None:
 """Kaynak çakışmalarını tespit et ve tabloya dök."""
 self.den_eng.atamalari_temizle()
 for tid, task in self.engine.tasks.items():
 if not task.kaynak or not task.early_start or not task.early_finish:
 continue
 self.den_eng.atama_ekle(AtamaKayit(
 gorev_id=tid,
 gorev_ad=task.ad,
 kaynak_ad=task.kaynak,
 baslangic=task.early_start,
 bitis=task.early_finish,
 sure_gun=task.sure_gun,
 bolluk_gun=task.float_gun,
 kritik=task.kritik,
 ))

 # Motordaki çakışmaları GanttEngine'dan da al
 motor_cakismalar = self.engine.check_kaynak_cakisma()
 dengeleme_cakismalar = self.den_eng.cakismalari_bul()

 # Birleştir
 tum_cakismalar = dengeleme_cakismalar

 self.tbl_cakisma.setRowCount(len(tum_cakismalar))
 for i, c in enumerate(tum_cakismalar):
 gorevler_str = " + ".join(c.gorev_adlar[:3])
 if len(c.gorev_adlar) > 3:
 gorevler_str += f" (+{len(c.gorev_adlar)-3})"

 self.tbl_cakisma.setItem(i, 0, QTableWidgetItem(c.kaynak_ad))
 self.tbl_cakisma.setItem(
 i, 1, QTableWidgetItem(c.tarih.strftime("%d.%m.%Y"))
 )
 self.tbl_cakisma.setItem(i, 2, QTableWidgetItem(gorevler_str))
 asim_item = QTableWidgetItem(f"+{c.kapasite_asim} birim")
 asim_item.setForeground(QColor(C_DANGER))
 self.tbl_cakisma.setItem(i, 3, asim_item)
 self.tbl_cakisma.setItem(i, 4, QTableWidgetItem(" Çakışma Var"))

 if tum_cakismalar:
 self._durum(
 f"{len(tum_cakismalar)} kaynak cakismasi tespit edildi. "
 "'Otomatik Dengele' ile cozun."
 )
 else:
 self._durum("Kaynak cakismasi bulunamadi.")

 def _otomatik_dengele(self) -> None:
 """Çakışmaları otomatik düzelt ve raporu tabloya yaz."""
 self.den_eng.atamalari_temizle()
 for tid, task in self.engine.tasks.items():
 if not task.kaynak or not task.early_start or not task.early_finish:
 continue
 self.den_eng.atama_ekle(AtamaKayit(
 gorev_id=tid,
 gorev_ad=task.ad,
 kaynak_ad=task.kaynak,
 baslangic=task.early_start,
 bitis=task.early_finish,
 sure_gun=task.sure_gun,
 bolluk_gun=task.float_gun,
 kritik=task.kritik,
 ))

 rapor = self.den_eng.tam_dengele()

 # GanttEngine'e geri besle
 for k in rapor.kaydirmalar:
 if k.gorev_id in self.engine.tasks:
 self.engine.tasks[k.gorev_id].early_start = k.yeni_baslangic
 self.engine.tasks[k.gorev_id].early_finish = k.yeni_bitis

 # Tabloyu güncelle
 self.tbl_dengele.setRowCount(len(rapor.kaydirmalar))
 for i, k in enumerate(rapor.kaydirmalar):
 renk = C_DANGER if k.kritik_etki else C_SUCCESS
 for j, val in enumerate([
 k.gorev_ad,
 k.kaynak_ad,
 k.eski_baslangic.strftime("%d.%m.%Y"),
 k.yeni_baslangic.strftime("%d.%m.%Y"),
 f"+{k.kaydi_gun} gün",
 " Kritik Etki" if k.kritik_etki else " Normal",
 ]):
 item = QTableWidgetItem(str(val))
 if j == 5:
 item.setForeground(QColor(renk))
 self.tbl_dengele.setItem(i, j, item)

 # Gantt'ı yenile
 if rapor.kaydirmalar:
 self.gantt_grafik.ciz(self.engine)
 self._guncelle_gorev_tablosu()

 self._durum(rapor.ozet_metin)
 QMessageBox.information(self, "Dengeleme Tamamlandı", rapor.ozet_metin)

 def _kapasite_ekle(self) -> None:
 ad = self.inp_kap_ad.text().strip()
 kap = self.inp_kap_kapasite.value()
 mal = self.inp_kap_maliyet.value()
 if ad:
 self.den_eng.kapasite_tanimla(ad, kap, mal)
 self.engine.add_kaynak(ad, kap, mal)
 self._durum(f"Kapasite tanimlandi: {ad} — {kap} ekip, {mal:,.0f} TL/gun")

 # ── Görev CRUD ────────────────────────────────────────────────────────────

 def _gorev_ekle(self) -> None:
 dlg = GorevDialog(tum_gorevler=self.engine.tasks, parent=self)
 if dlg.exec() != QDialog.DialogCode.Accepted:
 return

 veri = dlg.get_data()
 if not veri["ad"] or veri["sure_gun"] == 0 and not veri["milestone"]:
 QMessageBox.warning(self, "Eksik Bilgi", "Görev adı ve süre zorunludur.")
 return

 # Yeni ID
 yeni_id = max(self.engine.tasks.keys(), default=0) + 1
 task = Task(
 task_id=yeni_id,
 ad=veri["ad"],
 sure_gun=veri["sure_gun"],
 wbs_kodu=veri["wbs_kodu"] or str(yeni_id),
 kaynak=veri["kaynak"],
 ilerleme=veri["ilerleme"],
 milestone=veri["milestone"],
 aciklama=veri["aciklama"],
 )
 if veri["kritik_override"]:
 task.kritik = True

 self.engine.add_task(task)

 # Bütçe ve gerçek maliyet kaydet
 if veri["butce_tl"] > 0:
 self._butce[yeni_id] = veri["butce_tl"]
 if veri["gercek_maliyet_tl"] > 0:
 self._gercek_mal[yeni_id] = veri["gercek_maliyet_tl"]

 # Öncül bağlantısı
 if veri["oncul_id"]:
 self.engine.add_dependency(
 veri["oncul_id"], yeni_id,
 dep_type="FS",
 lag_days=veri["lag_days"]
 )

 self._guncelle_gorev_tablosu()
 self._durum(f"Is kalemi eklendi: {veri['ad']}")

 def _gorev_duzenle(self) -> None:
 secili = self.tbl_gorevler.currentRow()
 if secili < 0:
 return
 tasks = sorted(
 self.engine.tasks.values(),
 key=lambda t: (t.wbs_kodu or "999",)
 )
 if self.chk_sadece_kritik.isChecked():
 tasks = [t for t in tasks if t.kritik]
 if secili >= len(tasks):
 return
 task = tasks[secili]

 dlg = GorevDialog(task=task, tum_gorevler=self.engine.tasks, parent=self)
 if dlg.exec() != QDialog.DialogCode.Accepted:
 return

 veri = dlg.get_data()
 task.ad = veri["ad"]
 task.sure_gun = veri["sure_gun"]
 task.wbs_kodu = veri["wbs_kodu"] or task.wbs_kodu
 task.kaynak = veri["kaynak"]
 task.ilerleme = veri["ilerleme"]
 task.milestone = veri["milestone"]
 task.aciklama = veri["aciklama"]
 if veri["butce_tl"] > 0:
 self._butce[task.task_id] = veri["butce_tl"]
 if veri["gercek_maliyet_tl"] > 0:
 self._gercek_mal[task.task_id] = veri["gercek_maliyet_tl"]

 self._guncelle_gorev_tablosu()
 self._durum(f"Is kalemi guncellendi: {task.ad}")

 def _gorev_sil(self) -> None:
 secili = self.tbl_gorevler.currentRow()
 if secili < 0:
 return
 tasks = sorted(
 self.engine.tasks.values(),
 key=lambda t: (t.wbs_kodu or "999",)
 )
 if secili >= len(tasks):
 return
 task = tasks[secili]
 if QMessageBox.question(
 self, "Sil",
 f"'{task.ad}' görevi silinsin mi?",
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
 ) != QMessageBox.StandardButton.Yes:
 return

 del self.engine.tasks[task.task_id]
 self._butce.pop(task.task_id, None)
 self._gercek_mal.pop(task.task_id, None)
 self._guncelle_gorev_tablosu()
 self._durum(f"Is kalemi silindi: {task.ad}")

 # ── Şablon & Export ──────────────────────────────────────────────────────

 def _sablon_doldur(self) -> None:
 from app.data.gantt_templates import SABLON_LISTESI
 self.cmb_sablon.clear()
 self.cmb_sablon.addItem("Şablon Seç…", None)
 for key, val in SABLON_LISTESI.items():
 self.cmb_sablon.addItem(
 f"{val['ad']} ({len(val['gorevler'])} görev)", key
 )

 def _sablon_yukle(self) -> None:
 sablon_id = self.cmb_sablon.currentData()
 if not sablon_id:
 return

 if self.engine.tasks:
 if QMessageBox.question(
 self, "Onayla",
 "Mevcut görevler temizlensin mi?",
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
 ) != QMessageBox.StandardButton.Yes:
 return

 from app.data.gantt_templates import SABLON_LISTESI
 sablon = SABLON_LISTESI.get(sablon_id)
 if not sablon:
 return

 self.engine.tasks.clear()
 self._butce.clear()
 self._gercek_mal.clear()
 self.engine.kaynaklar.clear()
 self.engine.wbs_sayac.clear()
 self.engine.baseline_kayitli = False

 id_eslem: Dict[int, int] = {}
 for g in sablon["gorevler"]:
 yeni_id = g["sira"]
 task = Task(
 task_id=yeni_id,
 ad=g["ad"],
 sure_gun=g["sure"],
 kaynak=g.get("kaynak", ""),
 milestone=g.get("milestone", False),
 wbs_kodu=str(yeni_id),
 )
 self.engine.add_task(task)
 id_eslem[g["sira"]] = yeni_id

 # Bağımlılıklar
 for g in sablon["gorevler"]:
 for bag in g.get("bagimlilık", []):
 if bag in id_eslem and g["sira"] in id_eslem:
 self.engine.add_dependency(
 id_eslem[bag], id_eslem[g["sira"]], "FS", 0
 )

 self.hesapla()
 self._durum(
 f"Sablon yuklendi: {sablon['ad']} — {len(sablon['gorevler'])} is kalemi"
 )

 def _baseline_kaydet(self) -> None:
 if not self.engine.tasks:
 return
 sonuc = self.engine.save_baseline()
 if sonuc.get("success"):
 self._durum(
 f"Baseline kaydedildi — "
 f"{sonuc['gorev_sayisi']} is kalemi, "
 f"{sonuc['tarih'].strftime('%d.%m.%Y %H:%M')}"
 )
 self.gantt_grafik.ciz(self.engine)

 def _excel_export(self) -> None:
 """Görev listesini Excel'e aktar."""
 dosya, _ = QFileDialog.getSaveFileName(
 self, "Excel Kaydet", "is_programi.xlsx",
 "Excel (*.xlsx)"
 )
 if not dosya:
 return
 try:
 import openpyxl
 from openpyxl.styles import Font, PatternFill, Alignment

 wb = openpyxl.Workbook()
 ws = wb.active
 ws.title = "İş Programı"

 basliklar = [
 "WBS", "Görev Adı", "Süre (Gün)", "Başlangıç",
 "Bitiş", "İlerleme (%)", "Float (Gün)",
 "Kaynak", "Baseline Başlangıç", "Baseline Bitiş",
 "Kritik", "Bütçe (TL)", "Gerçek Maliyet (TL)"
 ]
 for col, b in enumerate(basliklar, 1):
 hc = ws.cell(row=1, column=col, value=b)
 hc.font = Font(bold=True, color="FFFFFF")
 hc.fill = PatternFill("solid", fgColor="0F3460")
 hc.alignment = Alignment(horizontal="center")

 sorted_tasks = sorted(
 self.engine.tasks.values(),
 key=lambda t: t.wbs_kodu or ""
 )
 excel_data = self.engine.export_to_excel_data()
 for row_idx, (data, task) in enumerate(
 zip(excel_data, sorted_tasks), 2
 ):
 row_data = [
 data.get("WBS", ""),
 data.get("İş Adı", ""),
 data.get("Süre (Gün)", ""),
 data.get("Başlangıç", ""),
 data.get("Bitiş", ""),
 data.get("İlerleme (%)", ""),
 data.get("Float (Gün)", ""),
 data.get("Kaynak", ""),
 data.get("Baseline Başlangıç", ""),
 data.get("Baseline Bitiş", ""),
 data.get("Kritik", "Hayır"),
 float(self._butce.get(task.task_id, 0)),
 float(self._gercek_mal.get(task.task_id, 0)),
 ]
 for col, val in enumerate(row_data, 1):
 ws.cell(row=row_idx, column=col, value=val)

 for col in ws.columns:
 ws.column_dimensions[col[0].column_letter].width = 18

 wb.save(dosya)
 self._durum(f"Excel kaydedildi: {dosya}")
 except Exception as e:
 QMessageBox.critical(self, "Excel Hatası", str(e))

 # ── Demo Veri ─────────────────────────────────────────────────────────────

 def _demo_veri_yukle(self) -> None:
 """
 Uygulama ilk açıldığında gösterilecek örnek proje.
 5 kat konut inşaatı — temel + kaba + ince.
 """
 pass # Şablon ile yükleme tercih edildi; boş başlasın

 # ── Beklenmedik Durum & PERT ──────────────────────────────────────────────

 def _beklenmedik_durum_ekle(self) -> None:
 """
 Sahadan bildirilen beklenmedik durumu is programına işler.

 Saha Karşılığı:
 Yağış veya sevkiyat gecikmesi gibi durumlarda etkilenen
 iş kalemlerinin sure_gun değeri artırılır ve CPM yeniden hesaplanır.
 Ataşman notu hakediş dosyasına referans olarak kaydedilir.
 """
 if not self.engine.tasks:
 self._durum(" Is programı boş. Önce görev ekleyin.")
 return

 dlg = BeklenmedikDurumDialog(tum_gorevler=self.engine.tasks, parent=self)
 if dlg.exec() != QDialog.DialogCode.Accepted:
 return

 veri = dlg.get_data()
 etkilenen_ids = veri["etkilenen_ids"]
 gecikme_gun = veri["gecikme_gun"]
 tur = veri["tur"]

 if not etkilenen_ids:
 QMessageBox.warning(
 self, "Etkilenen Görev Yok",
 "En az bir iş kalemi seçin."
 )
 return

 # Etkilenen görevlerin sürelerini güncelle
 toplam_gun = 0
 etkilenen_adlar = []
 for tid in etkilenen_ids:
 if tid in self.engine.tasks:
 task = self.engine.tasks[tid]
 task.sure_gun += gecikme_gun
 toplam_gun += gecikme_gun
 etkilenen_adlar.append(task.ad)

 logger.warning(
 f"BEKLENMEDIK DURUM: {tur} — "
 f"{len(etkilenen_ids)} is kalemi etkilendi, "
 f"toplam gecikme: {toplam_gun} gün — "
 f"Etkilenen: {', '.join(etkilenen_adlar[:3])}"
 + (f" (+{len(etkilenen_adlar)-3} daha)" if len(etkilenen_adlar) > 3 else "")
 )

 # CPM yeniden hesapla
 self.hesapla()

 # Ataşman notunu durum çubuğuna yansıt
 not_ozet = veri["ataman_notu"][:80] if veri["ataman_notu"] else ""
 self._durum(
 f"BEKLENMEDIK DURUM ISLENDI: {tur} — "
 f"{len(etkilenen_ids)} is kalemi +{gecikme_gun} gün kaydırıldı. "
 + (f"Ataseman: {not_ozet}" if not_ozet else "")
 )

 QMessageBox.information(
 self,
 "Beklenmedik Durum Kaydedildi",
 f"Durum türü : {tur}\n"
 f"Etkilenen : {len(etkilenen_ids)} iş kalemi\n"
 f"Gecikme : +{gecikme_gun} gün / kalemi\n\n"
 f"CPM yeniden hesaplandı. Kritik yol güncellemesi için "
 f"PROGRAM sekmesini kontrol edin.\n\n"
 + (f"Hakediş notu: {veri['tahsilat_durumu']}" if veri['tahsilat_durumu'] else "")
 )

 def _pert_analizi_goster(self) -> None:
 """
 Mevcut is programı üzerinde PERT 3 noktalı tahmin analizi yapar
 ve sonuçları tablo formatında gösterir.

 Not:
 Görevlerde iyimser/kötümser verisi yoksa sure_gun *0.80 ve *1.30
 ile otomatik tahmin üretilir (varsayılan beta dağılımı yaklaşımı).
 """
 if not self.engine.tasks:
 self._durum(" Is programı boş. PERT için görev ekleyin.")
 return

 sozlesme_dt: Optional[datetime] = None
 if hasattr(self, 'dt_sozlesme'):
 sozlesme_qdate = self.dt_sozlesme.date()
 sozlesme_dt = datetime(
 sozlesme_qdate.year(),
 sozlesme_qdate.month(),
 sozlesme_qdate.day()
 )

 proje_bas = self.dt_proje_bas.date()
 proje_bas_dt = datetime(
 proje_bas.year(), proje_bas.month(), proje_bas.day()
 )

 # PertGorev listesi üret
 pert_gorevler: List[PertGorev] = []
 for tid, task in self.engine.tasks.items():
 t_m = float(task.sure_gun)
 # Görevde kayıtlı iyimser/kötümser değerleri yoksa kural tabanlı tahmin
 t_o = t_m * 0.80
 t_p = t_m * 1.30
 pert_gorevler.append(PertGorev(
 gorev_id=tid,
 ad=task.ad,
 iyimser_gun=round(t_o, 1),
 olasi_gun=t_m,
 kotumser_gun=round(t_p, 1),
 wbs_kodu=task.wbs_kodu or "",
 kritik=task.kritik,
 baslangic=task.early_start or proje_bas_dt,
 ))

 pert_eng = PertEngine()
 sonuc = pert_eng.hesapla(pert_gorevler, proje_bas_dt, sozlesme_dt)

 # Sonuç metnini hazırla
 asim_metin = ""
 if sonuc.sozlesme_asim_gun is not None:
 if sonuc.sozlesme_asim_gun > 0:
 asim_metin = (
 f"\n\nSOZLESME ASILMASI: +{sonuc.sozlesme_asim_gun} gün asim bekleniyor!"
 )
 else:
 asim_metin = (
 f"\n\nSozlesme tampon: {abs(sonuc.sozlesme_asim_gun)} gün"
 )

 uyari_metin = ""
 if sonuc.uyari_listesi:
 uyari_metin = "\n\nUyarılar:\n" + "\n".join(
 f" - {u}" for u in sonuc.uyari_listesi[:4]
 )

 ozet = (
 f"PROJE PERT ANALİZİ\n"
 f"{'='*50}\n"
 f"Toplam PERT Süresi (t_e) : {sonuc.toplam_pert_sure:.1f} gün\n"
 f"Proje Sigma (σ) : {sonuc.proje_sapma:.2f} gün\n"
 f"\nBITIS TARIHİ SENARYOLARI:\n"
 f" P50 (Beklenen) : {sonuc.proje_bitis_p50.strftime('%d.%m.%Y')}\n"
 f" P80 : {sonuc.proje_bitis_p80.strftime('%d.%m.%Y')}\n"
 f" P90 : {sonuc.proje_bitis_p90.strftime('%d.%m.%Y')}\n"
 f" P95 (Ihtiyatli) : {sonuc.proje_bitis_p95.strftime('%d.%m.%Y')}\n"
 f"\nKRITIK IS KALEMLERI PERT:\n"
 )

 for gs in sonuc.gorev_sonuclari:
 if gs.kritik:
 ozet += (
 f" {gs.wbs_kodu or '—'} {gs.ad[:30]:<30} "
 f"t_e={gs.pert_sure:.1f}g σ={gs.standart_sapma:.2f}g\n"
 )

 ozet += asim_metin + uyari_metin

 # Dialog göster
 dlg = QDialog(self)
 dlg.setWindowTitle("PERT Analizi — 3 Noktalı Tahmin Sonucu")
 dlg.setMinimumWidth(620)
 dlg.setMinimumHeight(500)
 dlg.setStyleSheet(f"QDialog {{ background: {C_BG}; color: {C_TEXT}; }}")
 d_lay = QVBoxLayout(dlg)

 txt = QTextEdit()
 txt.setReadOnly(True)
 txt.setStyleSheet(
 f"background: {C_BG2}; color: {C_TEXT}; border: none;"
 "border-radius: 6px; padding: 10px; font-family: Consolas; font-size: 12px;"
 )
 txt.setPlainText(ozet)
 d_lay.addWidget(txt)

 kapat_btn = QPushButton("Kapat")
 kapat_btn.setStyleSheet(BTN_PRIMARY)
 kapat_btn.clicked.connect(dlg.accept)
 d_lay.addWidget(kapat_btn)
 dlg.exec()

 # ── Yardımcı ──────────────────────────────────────────────────────────────

 def _durum(self, mesaj: str) -> None:
 self.lbl_durum.setText(mesaj)
