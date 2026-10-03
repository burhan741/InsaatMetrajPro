"""
Gantt Chart Window — İnşaat Metraj Pro v2.0
PyQt6 tabanlı görsel iş programı, CPM/WBS, S-Curve, What-If, Baseline modülleri.
4-space PEP8 — tam yeniden yazım. 2026-03-16 Rev-16: genişletilmiş ekip/birim/verimlilik.
"""

import json
import logging
import math
import os
import copy
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import (
    QDate, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDateEdit,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QGraphicsItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsTextItem, QGraphicsView, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QSlider, QSpinBox, QSplitter, QStackedWidget, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QToolBar, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Opsiyonel modül importları
# ---------------------------------------------------------------------------
_BUGUN_PANEL_OK = False
_SABLON_SIHIRBAZ_OK = False
_SABLON_YON_OK = False

try:
    from app.ui.bugun_paneli import BugunPaneli
    _BUGUN_PANEL_OK = True
except Exception:
    pass

try:
    from app.ui.sablon_sihirbazi import SablonSihirbazi
    _SABLON_SIHIRBAZ_OK = True
except Exception:
    pass

try:
    from app.core.proje_sablonlari import SablonYoneticisi
    _SABLON_YON_OK = True
except Exception:
    pass

try:
    from app.core.gantt_engine import GanttEngine, Task
except Exception as exc:
    logger.error("GanttEngine import hatası: %s", exc)
    GanttEngine = None
    Task = None

try:
    import openpyxl
    _OPENPYXL_OK = True
except ImportError:
    _OPENPYXL_OK = False

try:
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    _REPORTLAB_OK = True
except ImportError:
    _REPORTLAB_OK = False

# Görev dialog'u için son ek veri köprüsü (monkey-patch uyumluluğu)
_LAST_TASK_DIALOG_EXTRA: Dict[str, Any] = {}


# ===========================================================================
# DraggableTaskBar
# ===========================================================================
class DraggableTaskBar(QGraphicsRectItem):
    """Gantt görsel panelinde sürüklenebilir iş çubuğu."""

    def __init__(
        self,
        task_id: int,
        label: str,
        color: QColor,
        callback,
        parent=None,
    ):
        super().__init__(parent)
        self.task_id = task_id
        self.label = label
        self.callback = callback
        self._drag_start_x: float = 0.0
        self._original_x: float = 0.0

        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(130), 1))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(Qt.CursorShape.SizeHorCursor)

        # Etiket
        self._text = QGraphicsTextItem(label, self)
        self._text.setDefaultTextColor(Qt.GlobalColor.white)
        font = QFont("Arial", 7, QFont.Weight.Bold)
        self._text.setFont(font)

    def mousePressEvent(self, event) -> None:
        self._drag_start_x = event.scenePos().x()
        self._original_x = self.x()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        delta_x = self.x() - self._original_x
        if abs(delta_x) > 2 and self.callback:
            self.callback(self.task_id, delta_x)
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value
            new_pos.setY(self.y())
            return new_pos
        return super().itemChange(change, value)


# ===========================================================================
# GanttChartView
# ===========================================================================
class GanttChartView(QGraphicsView):
    """Görsel Gantt grafiği — QGraphicsView tabanlı."""

    task_dragged = pyqtSignal(int, float)

    ROW_HEIGHT = 28
    HEADER_HEIGHT = 48
    DAY_WIDTH = 22
    LEFT_MARGIN = 200
    MIN_DATE_RANGE = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._tasks: List[Dict] = []
        self._start_date: Optional[date] = None
        self._end_date: Optional[date] = None
        self._zoom = 1.0
        self._today_line = None
        self._task_bars: Dict[int, DraggableTaskBar] = {}

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def draw_gantt(self, tasks: List[Dict], start: date, end: date) -> None:
        self._tasks = tasks
        self._start_date = start
        self._end_date = end
        self._scene.clear()
        self._task_bars.clear()

        if not tasks or not start or not end:
            return

        total_days = (end - start).days + 1
        total_days = max(total_days, self.MIN_DATE_RANGE)
        scene_w = self.LEFT_MARGIN + total_days * self.DAY_WIDTH * self._zoom
        scene_h = self.HEADER_HEIGHT + len(tasks) * self.ROW_HEIGHT + 20

        self._scene.setSceneRect(0, 0, scene_w, scene_h)
        self._draw_month_headers(start, total_days)
        self._draw_day_grid(start, total_days, len(tasks))
        self._draw_task_bars(tasks, start)
        if len(tasks) <= 200:
            self._draw_dependency_arrows(tasks, start, total_days)
        self._draw_today_line(start, total_days, len(tasks))

    def _draw_month_headers(self, start: date, total_days: int) -> None:
        dw = self.DAY_WIDTH * self._zoom
        font_bold = QFont("Arial", 8, QFont.Weight.Bold)
        font_small = QFont("Arial", 7)
        current = start
        for i in range(total_days):
            x = self.LEFT_MARGIN + i * dw
            if current.day == 1:
                month_label = current.strftime("%B %Y")
                t = self._scene.addText(month_label, font_bold)
                t.setPos(x + 2, 2)
                t.setDefaultTextColor(QColor("#1976D2"))
            day_t = self._scene.addText(str(current.day), font_small)
            day_t.setPos(x + 1, 26)
            day_t.setDefaultTextColor(QColor("#555"))
            current += timedelta(days=1)

        self._scene.addRect(
            0, 0, self.LEFT_MARGIN, self.HEADER_HEIGHT,
            QPen(Qt.PenStyle.NoPen), QBrush(QColor("#E3F2FD"))
        )

    def _draw_day_grid(self, start: date, total_days: int, row_count: int) -> None:
        dw = self.DAY_WIDTH * self._zoom
        scene_h = self.HEADER_HEIGHT + row_count * self.ROW_HEIGHT + 20

        current = start
        for i in range(total_days + 1):
            x = self.LEFT_MARGIN + i * dw
            is_weekend = current.weekday() >= 5 if i < total_days else False
            if is_weekend:
                self._scene.addRect(
                    x, self.HEADER_HEIGHT, dw, scene_h - self.HEADER_HEIGHT,
                    QPen(Qt.PenStyle.NoPen), QBrush(QColor("#FFF9C4"))
                )
            pen = QPen(QColor("#DDDDDD"), 0.5)
            self._scene.addLine(x, self.HEADER_HEIGHT, x, scene_h, pen)
            if i < total_days:
                current += timedelta(days=1)

        for row in range(row_count + 1):
            y = self.HEADER_HEIGHT + row * self.ROW_HEIGHT
            pen = QPen(QColor("#EEEEEE"), 0.5)
            self._scene.addLine(0, y, self.LEFT_MARGIN + total_days * dw, y, pen)

    def _draw_task_bars(self, tasks: List[Dict], start: date) -> None:
        dw = self.DAY_WIDTH * self._zoom
        font_label = QFont("Arial", 8)

        COLORS = {
            "kritik": QColor("#F44336"),
            "normal": QColor("#2196F3"),
            "milestone": QColor("#FF9800"),
            "gecikme": QColor("#9C27B0"),
        }

        for row, task in enumerate(tasks):
            y = self.HEADER_HEIGHT + row * self.ROW_HEIGHT

            label_bg_color = QColor("#F5F5F5") if row % 2 == 0 else QColor("#FAFAFA")
            self._scene.addRect(
                0, y, self.LEFT_MARGIN, self.ROW_HEIGHT,
                QPen(Qt.PenStyle.NoPen), QBrush(label_bg_color)
            )
            task_label = self._scene.addText(task.get("ad", ""), font_label)
            indent = task.get("wbs_level", 0) * 12
            task_label.setPos(4 + indent, y + 4)
            task_label.setDefaultTextColor(QColor("#212121"))

            t_start = task.get("baslangic")
            t_end = task.get("bitis")
            if not t_start or not t_end:
                continue

            if isinstance(t_start, str):
                try:
                    t_start = date.fromisoformat(t_start)
                except ValueError:
                    continue
            if isinstance(t_end, str):
                try:
                    t_end = date.fromisoformat(t_end)
                except ValueError:
                    continue

            offset_start = (t_start - start).days
            offset_end = (t_end - start).days + 1
            bar_x = self.LEFT_MARGIN + offset_start * dw
            bar_w = (offset_end - offset_start) * dw

            is_kritik = task.get("kritik_yol", False)
            is_milestone = task.get("milestone", False)
            is_gecikme = task.get("gecikme_var", False)

            if is_milestone:
                color = COLORS["milestone"]
            elif is_gecikme:
                color = COLORS["gecikme"]
            elif is_kritik:
                color = COLORS["kritik"]
            else:
                color = COLORS["normal"]

            bar = DraggableTaskBar(
                task.get("id", 0),
                task.get("ad", ""),
                color,
                self._on_task_bar_dragged,
            )
            bar_h = self.ROW_HEIGHT - 6
            bar.setRect(0, 0, max(bar_w, 4), bar_h)
            bar.setPos(bar_x, y + 3)
            self._scene.addItem(bar)
            self._task_bars[task.get("id", 0)] = bar

            float_days = task.get("float", 0)
            if float_days and float_days > 0:
                float_w = float_days * dw
                self._scene.addRect(
                    bar_x + bar_w, y + bar_h // 2 + 3, float_w, 3,
                    QPen(Qt.PenStyle.NoPen), QBrush(QColor("#81D4FA"))
                )

            progress = task.get("tamamlanma_yuzdesi", 0)
            if progress and progress > 0:
                prog_w = bar_w * progress / 100.0
                self._scene.addRect(
                    bar_x, y + 3, prog_w, bar_h,
                    QPen(Qt.PenStyle.NoPen), QBrush(QColor(255, 255, 255, 80))
                )

    def _draw_dependency_arrows(self, tasks: List[Dict], start: date, total_days: int) -> None:
        """Bağımlılık oklarını L-şeklinde çizer. Kırmızı=kritik, Gri=normal."""
        dw = self.DAY_WIDTH * self._zoom
        id_to_row = {t.get("id"): i for i, t in enumerate(tasks)}

        for row, task in enumerate(tasks):
            deps = task.get("bagimliliklar_detay", [])
            if not deps:
                dep_ids = task.get("bagimliliklar", [])
                deps = [{"id": d, "tip": "FS"} for d in dep_ids if isinstance(d, int)]

            t_start = task.get("baslangic")
            if not t_start:
                continue
            try:
                t_start = date.fromisoformat(str(t_start))
            except (ValueError, TypeError):
                continue

            offset_to = (t_start - start).days
            if not (0 <= offset_to <= total_days):
                continue

            x_to = self.LEFT_MARGIN + offset_to * dw
            y_to = self.HEADER_HEIGHT + row * self.ROW_HEIGHT + self.ROW_HEIGHT // 2

            for dep in deps:
                pred_id = dep.get("id")
                pred_row = id_to_row.get(pred_id)
                if pred_row is None:
                    continue
                pred_task = tasks[pred_row]
                pred_bitis = pred_task.get("bitis")
                if not pred_bitis:
                    continue
                try:
                    pred_bitis = date.fromisoformat(str(pred_bitis))
                except (ValueError, TypeError):
                    continue

                offset_from = (pred_bitis - start).days + 1
                if not (0 <= offset_from <= total_days):
                    continue

                x_from = self.LEFT_MARGIN + offset_from * dw
                y_from = self.HEADER_HEIGHT + pred_row * self.ROW_HEIGHT + self.ROW_HEIGHT // 2

                is_kritik = task.get("kritik_yol") and pred_task.get("kritik_yol")
                pen = QPen(
                    QColor("#F44336") if is_kritik else QColor("#9E9E9E"),
                    1.2,
                    Qt.PenStyle.SolidLine,
                )
                # L-şekilli ok: yatay sonra dikey
                mid_x = x_from + max(dw * 0.5, 4)
                self._scene.addLine(x_from, y_from, mid_x, y_from, pen)
                self._scene.addLine(mid_x, y_from, mid_x, y_to, pen)
                self._scene.addLine(mid_x, y_to, x_to, y_to, pen)
                # Ok ucu
                arrow_pen = QPen(pen.color(), 1.2)
                self._scene.addLine(x_to - 5, y_to - 4, x_to, y_to, arrow_pen)
                self._scene.addLine(x_to - 5, y_to + 4, x_to, y_to, arrow_pen)

    def _draw_today_line(self, start: date, total_days: int, row_count: int) -> None:
        today = date.today()
        if start <= today <= start + timedelta(days=total_days):
            dw = self.DAY_WIDTH * self._zoom
            x = self.LEFT_MARGIN + (today - start).days * dw
            scene_h = self.HEADER_HEIGHT + row_count * self.ROW_HEIGHT + 20
            pen = QPen(QColor("#E53935"), 2, Qt.PenStyle.DashLine)
            self._today_line = self._scene.addLine(x, 0, x, scene_h, pen)
            label = self._scene.addText("Bugün", QFont("Arial", 7, QFont.Weight.Bold))
            label.setPos(x + 2, 2)
            label.setDefaultTextColor(QColor("#E53935"))

    def _on_task_bar_dragged(self, task_id: int, delta_x: float) -> None:
        dw = self.DAY_WIDTH * self._zoom
        delta_days = round(delta_x / dw)
        if delta_days != 0:
            self.task_dragged.emit(task_id, float(delta_days))

    def zoom_in(self) -> None:
        self._zoom = min(self._zoom * 1.25, 4.0)
        if self._tasks and self._start_date:
            self.draw_gantt(self._tasks, self._start_date, self._end_date)

    def zoom_out(self) -> None:
        self._zoom = max(self._zoom / 1.25, 0.25)
        if self._tasks and self._start_date:
            self.draw_gantt(self._tasks, self._start_date, self._end_date)

    def zoom_fit(self) -> None:
        self._zoom = 1.0
        if self._tasks and self._start_date:
            self.draw_gantt(self._tasks, self._start_date, self._end_date)
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


# ===========================================================================
# SCurveWidget
# ===========================================================================
class SCurveWidget(QWidget):
    """S-Eğrisi (Planlanan vs Gerçekleşen değer) çizim widget'ı."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: Dict = {}
        self.setMinimumHeight(300)

    def set_data(self, data: Dict) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_background(painter)
        if self._data:
            self._draw_curve(painter)
            self._draw_legend(painter)
        else:
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "S-Eğrisi verisi yok — önce hesapla düğmesine tıklayın."
            )

    def _draw_background(self, painter: QPainter) -> None:
        painter.fillRect(self.rect(), QColor("#FAFAFA"))
        pen = QPen(QColor("#DDDDDD"), 1)
        painter.setPen(pen)
        w, h = self.width(), self.height()
        margin = 60
        for i in range(11):
            y = margin + (h - 2 * margin) * i / 10
            painter.drawLine(margin, int(y), w - 20, int(y))
            label = f"{100 - i * 10}%"
            painter.drawText(2, int(y) + 5, label)

    def _draw_curve(self, painter: QPainter) -> None:
        planned = self._data.get("planlanan", [])
        actual = self._data.get("gerceklesen", [])
        if not planned:
            return

        w, h = self.width(), self.height()
        margin = 60
        chart_w = w - margin - 20
        chart_h = h - 2 * margin
        n = len(planned)

        def to_xy(idx, val):
            x = margin + chart_w * idx / max(n - 1, 1)
            y = margin + chart_h * (1.0 - val / 100.0)
            return int(x), int(y)

        pen = QPen(QColor("#1976D2"), 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        for i in range(1, len(planned)):
            x1, y1 = to_xy(i - 1, planned[i - 1])
            x2, y2 = to_xy(i, planned[i])
            painter.drawLine(x1, y1, x2, y2)

        if actual:
            pen = QPen(QColor("#F57C00"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            for i in range(1, len(actual)):
                x1, y1 = to_xy(i - 1, actual[i - 1])
                x2, y2 = to_xy(i, actual[i])
                painter.drawLine(x1, y1, x2, y2)

    def _draw_legend(self, painter: QPainter) -> None:
        w = self.width()
        painter.setPen(QPen(QColor("#1976D2"), 2))
        painter.drawLine(w - 180, 16, w - 155, 16)
        painter.setPen(QColor("#333"))
        painter.drawText(w - 150, 20, "Planlanan (PV)")

        painter.setPen(QPen(QColor("#F57C00"), 2, Qt.PenStyle.DashLine))
        painter.drawLine(w - 180, 36, w - 155, 36)
        painter.setPen(QColor("#333"))
        painter.drawText(w - 150, 40, "Gerçekleşen (EV)")


# ===========================================================================
# TemplateDialog
# ===========================================================================
class TemplateDialog(QDialog):
    """Şablon seçim diyaloğu (eski yöntem fallback)."""

    def __init__(self, templates: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Şablon Seç")
        self.setMinimumSize(500, 400)
        self._templates = templates
        self._selected: Optional[Dict] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Hazır şablondan seçin:"))

        self._list = QListWidget()
        for t in self._templates:
            item = QListWidgetItem(
                f"[{t.get('kategori', '')}] {t.get('ad', '')} — "
                f"{t.get('gorev_sayisi', t.get('is_sayisi', 0))} iş"
            )
            item.setData(Qt.ItemDataRole.UserRole, t)
            self._list.addItem(item)
        layout.addWidget(self._list)

        self._desc = QLabel("Açıklama: —")
        self._desc.setWordWrap(True)
        layout.addWidget(self._desc)
        self._list.currentItemChanged.connect(self._on_selection_changed)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_selection_changed(self, current, previous) -> None:
        if current:
            t = current.data(Qt.ItemDataRole.UserRole)
            self._desc.setText(f"Açıklama: {t.get('aciklama', '—')}")

    def _accept(self) -> None:
        item = self._list.currentItem()
        if item:
            self._selected = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
        else:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir şablon seçin.")

    def get_selected(self) -> Optional[Dict]:
        return self._selected


# ===========================================================================
# WhatIfResultDialog
# ===========================================================================
class WhatIfResultDialog(QDialog):
    """What-If analiz sonuçları diyaloğu."""

    def __init__(self, original: Dict, scenario: Dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("What-If Analiz Sonucu")
        self.setMinimumSize(640, 480)
        self._original = original
        self._scenario = scenario
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Senaryo Analiz Karşılaştırması")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1976D2;")
        layout.addWidget(title)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(
            ["İş Adı", "Orijinal Bitiş", "Senaryo Bitiş", "Fark (Gün)"]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        orig_tasks = {t["id"]: t for t in self._original.get("tasks", [])}
        for t in self._scenario.get("tasks", []):
            tid = t.get("id")
            orig = orig_tasks.get(tid)
            if not orig:
                continue
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(t.get("ad", "")))
            table.setItem(row, 1, QTableWidgetItem(str(orig.get("bitis", ""))))
            table.setItem(row, 2, QTableWidgetItem(str(t.get("bitis", ""))))
            try:
                o_end = date.fromisoformat(str(orig.get("bitis", "")))
                s_end = date.fromisoformat(str(t.get("bitis", "")))
                diff = (s_end - o_end).days
                diff_item = QTableWidgetItem(f"{diff:+d}")
                if diff > 0:
                    diff_item.setForeground(QColor("#F44336"))
                elif diff < 0:
                    diff_item.setForeground(QColor("#4CAF50"))
                table.setItem(row, 3, diff_item)
            except (ValueError, TypeError):
                table.setItem(row, 3, QTableWidgetItem("—"))

        layout.addWidget(table)

        orig_end = self._original.get("proje_bitis", "—")
        scen_end = self._scenario.get("proje_bitis", "—")
        summary = QLabel(
            f"<b>Orijinal proje bitişi:</b> {orig_end} &nbsp;&nbsp; "
            f"<b>Senaryo bitişi:</b> {scen_end}"
        )
        layout.addWidget(summary)

        btn = QPushButton("Kapat")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)


# ===========================================================================
# AlertsPanel
# ===========================================================================
class AlertsPanel(QWidget):
    """Proje uyarıları ve risk göstergesi paneli."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        title = QLabel("Proje Uyarıları")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(title)
        header.addStretch()
        self._badge = QLabel("0")
        self._badge.setStyleSheet(
            "background: #4CAF50; color: white; border-radius: 10px;"
            " padding: 2px 8px; font-weight: bold;"
        )
        header.addWidget(self._badge)
        layout.addLayout(header)

        self._list = QListWidget()
        layout.addWidget(self._list)

    def set_alerts(self, alerts: List[Dict]) -> None:
        self._list.clear()
        self._badge.setText(str(len(alerts)))
        if len(alerts) == 0:
            self._badge.setStyleSheet(
                "background: #4CAF50; color: white; border-radius: 10px;"
                " padding: 2px 8px; font-weight: bold;"
            )
        else:
            self._badge.setStyleSheet(
                "background: #F44336; color: white; border-radius: 10px;"
                " padding: 2px 8px; font-weight: bold;"
            )

        severity_icons = {"kritik": "🔴", "uyari": "🟡", "bilgi": "🔵"}
        for alert in alerts:
            sev = alert.get("severity", "bilgi")
            icon = severity_icons.get(sev, "⚪")
            item = QListWidgetItem(f"{icon} {alert.get('mesaj', '')}")
            if sev == "kritik":
                item.setForeground(QColor("#F44336"))
            elif sev == "uyari":
                item.setForeground(QColor("#F57C00"))
            self._list.addItem(item)


# ===========================================================================
# TatilDialog
# ===========================================================================
class TatilDialog(QDialog):
    """Tatil ve çalışma günü yönetimi diyaloğu."""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tatil & Çalışma Günü Yönetimi")
        self.setMinimumSize(560, 420)
        self._engine = engine
        self._build_ui()
        self._load_holidays()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Resmi tatiller ve özel iş günleri/tatilleri yönetin. "
            "Bu bilgiler CPM hesaplamalarını etkiler."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Tarih", "Açıklama", "Tip"])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_ekle = QPushButton("+ Tatil Ekle")
        btn_ekle.clicked.connect(self._ekle_tatil)
        btn_sil = QPushButton("Sil")
        btn_sil.clicked.connect(self._sil_tatil)
        btn_hava = QPushButton("Hava Kosulu Gunleri Ekle")
        btn_hava.clicked.connect(self._ekle_hava_tatil)
        btn_row.addWidget(btn_ekle)
        btn_row.addWidget(btn_sil)
        btn_row.addWidget(btn_hava)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        chk_row = QHBoxLayout()
        self._chk_cumartesi = QCheckBox("Cumartesi çalışılıyor")
        self._chk_pazar = QCheckBox("Pazar çalışılıyor")
        chk_row.addWidget(self._chk_cumartesi)
        chk_row.addWidget(self._chk_pazar)
        chk_row.addStretch()
        layout.addLayout(chk_row)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._kaydet)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_holidays(self) -> None:
        if not self._engine:
            return
        mgr = getattr(self._engine, "tatil_yoneticisi", None)
        if not mgr:
            return
        holidays = getattr(mgr, "ozel_tatiller", [])
        for h in holidays:
            self._append_row(
                str(h.get("tarih", "")),
                h.get("aciklama", ""),
                h.get("tip", "tatil"),
            )
        self._chk_cumartesi.setChecked(getattr(mgr, "cumartesi_calisma", False))
        self._chk_pazar.setChecked(getattr(mgr, "pazar_calisma", False))

    def _append_row(self, tarih: str, aciklama: str, tip: str) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(tarih))
        self._table.setItem(row, 1, QTableWidgetItem(aciklama))
        self._table.setItem(row, 2, QTableWidgetItem(tip))

    def _ekle_tatil(self) -> None:
        self._append_row(date.today().isoformat(), "Yeni Tatil", "tatil")

    def _sil_tatil(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)

    def _kaydet(self) -> None:
        if not self._engine:
            self.accept()
            return
        mgr = getattr(self._engine, "tatil_yoneticisi", None)
        if mgr and hasattr(mgr, "ozel_tatiller"):
            holidays = []
            for row in range(self._table.rowCount()):
                holidays.append({
                    "tarih": self._table.item(row, 0).text() if self._table.item(row, 0) else "",
                    "aciklama": self._table.item(row, 1).text() if self._table.item(row, 1) else "",
                    "tip": self._table.item(row, 2).text() if self._table.item(row, 2) else "tatil",
                })
            mgr.ozel_tatiller = holidays
        self.accept()

    def _ekle_hava_tatil(self) -> None:
        """Kötü hava koşulu günlerini tatil olarak ekle."""
        from PyQt6.QtWidgets import QInputDialog
        try:
            from app.core.hava_durumu import HavaDurumuServisi
            servis = HavaDurumuServisi()
        except Exception:
            # Hava durumu servisi yoksa manuel giriş yap
            tarih_str, ok = QInputDialog.getText(
                self, "Hava Kosulu Gunu",
                "Tarih girin (GG.AA.YYYY):",
            )
            if ok and tarih_str:
                self._append_row(tarih_str, "Kötü Hava Koşulu", "Hava")
            return

        # Tarih aralığı seç
        yil = datetime.now().year
        ay_str, ok = QInputDialog.getItem(
            self, "Ay Sec", "Kontrol edilecek ay:",
            [f"{i:02d}.{yil}" for i in range(1, 13)],
            datetime.now().month - 1, False
        )
        if not ok:
            return
        ay, yil_str = int(ay_str[:2]), int(ay_str[3:])
        import calendar
        bitis_gun = calendar.monthrange(yil_str, ay)[1]
        bas = datetime(yil_str, ay, 1)
        bit = datetime(yil_str, ay, bitis_gun)
        try:
            tahmin = servis.tahmin_al(
                enlem=39.9, boylam=32.8,
                baslangic=bas, bitis=bit
            )
            eklenen = 0
            for gun_data in (tahmin or []):
                if gun_data.get("calisma_durumu") in ("YASAKLI", "RISKLI"):
                    tarih = gun_data.get("tarih", "")
                    self._append_row(str(tarih), f"Hava Kosulu: {gun_data.get('aciklama','')}", "Hava")
                    eklenen += 1
            QMessageBox.information(self, "Tamamlandi", f"{eklenen} hava kosulu gunu eklendi.")
        except Exception as e:
            QMessageBox.warning(self, "Uyari", f"Hava durumu alinamadi: {e}\nManuel ekleme yapabilirsiniz.")


# ===========================================================================
# TaskDialog
# ===========================================================================
class TaskDialog(QDialog):
    """Görev ekle / düzenle diyaloğu — genişletilmiş Ekip & Verimlilik."""

    BIRIMLER = ["m²", "m³", "m", "adet", "kg", "ton", "takım", "lt"]

    # (görünen ad, varsayılan birim)  —  None birim = grup başlığı (seçilemez)
    EKIP_GRUPLARI: List[Tuple[str, Optional[str]]] = [
        ("━━ KABA YAPI ━━",           None),
        ("Demirci (Bağlama/Bükme)",    "kg"),
        ("Demirci (Nervürlü Soğuk)",   "kg"),
        ("Kalıpçı (Döşeme)",           "m²"),
        ("Kalıpçı (Kiriş)",            "m²"),
        ("Kalıpçı (Kolon)",            "m²"),
        ("Kalıpçı (Karma)",            "m²"),
        ("Kalıp Söküm Ekibi",          "m²"),
        ("Betoncu",                    "m³"),
        ("Duvarcı (Tuğla)",            "m²"),
        ("Duvarcı (Gazbeton)",         "m²"),
        ("━━ İNCE İŞLER ━━",          None),
        ("Sıvacı (İç)",                "m²"),
        ("Sıvacı (Dış)",               "m²"),
        ("Boyacı (İç)",                "m²"),
        ("Boyacı (Dış)",               "m²"),
        ("Fayansçı / Seramikçi",       "m²"),
        ("Mermerci",                   "m²"),
        ("Parke / Laminat Ustası",     "m²"),
        ("Şap Ustası",                 "m²"),
        ("━━ TESİSAT ━━",             None),
        ("Elektrikçi",                 "m"),
        ("Tesisatçı (Su/Pis Su)",      "m"),
        ("Tesisatçı (Isı)",            "adet"),
        ("━━ DOĞRAMA & DIŞ CEPHE ━━", None),
        ("Doğramacı (PVC)",            "adet"),
        ("Doğramacı (Alüminyum)",      "adet"),
        ("Çatıcı",                     "m²"),
        ("Yalıtımcı (Mantolama)",      "m²"),
        ("Yalıtımcı (Su)",             "m²"),
        ("━━ DİĞER ━━",               None),
        ("İskele Ustası",              "m²"),
        ("Kazıcı / Hafriyatçı",        "m³"),
        ("Vinç Operatörü",             "adet"),
        ("Genel İşçi",                 "adet"),
    ]

    # (label, verimlilik değeri, birim)  — Kaynak: ÇŞB Birim Fiyat Analizleri
    EKIP_VERIMLILIK: Dict[str, List[Tuple[str, float, str]]] = {
        "Demirci (Bağlama/Bükme)": [
            ("ÇŞB — 333 kg/usta/gün",   333.0, "kg"),
            ("Standart — 300 kg/usta/gün", 300.0, "kg"),
            ("Ağır İş — 200 kg/usta/gün", 200.0, "kg"),
        ],
        "Demirci (Nervürlü Soğuk)": [
            ("ÇŞB — 250 kg/usta/gün",   250.0, "kg"),
            ("Standart — 220 kg/usta/gün", 220.0, "kg"),
        ],
        "Kalıpçı (Döşeme)": [
            ("ÇŞB — 4.00 m²/usta/gün",  4.0,  "m²"),
            ("Playwood — 12.5 m²/usta/gün", 12.5, "m²"),
        ],
        "Kalıpçı (Kiriş)": [
            ("ÇŞB — 2.86 m²/usta/gün",  2.86, "m²"),
        ],
        "Kalıpçı (Kolon)": [
            ("ÇŞB — 1.82 m²/usta/gün",  1.82, "m²"),
        ],
        "Kalıpçı (Karma)": [
            ("ÇŞB — 3.33 m²/usta/gün",  3.33, "m²"),
        ],
        "Kalıp Söküm Ekibi": [
            ("ÇŞB — 8.00 m²/usta/gün",  8.0,  "m²"),
        ],
        "Betoncu": [
            ("Mikser İle — 20 m³/usta/gün",  20.0, "m³"),
            ("Elle Beton — 5 m³/usta/gün",    5.0, "m³"),
        ],
        "Duvarcı (Tuğla)": [
            ("İnce Tuğla 8.5 cm — 8 m²/usta/gün",  8.0, "m²"),
            ("Kalın Tuğla 13.5 cm — 6 m²/usta/gün", 6.0, "m²"),
        ],
        "Duvarcı (Gazbeton)": [
            ("Gazbeton — 12 m²/usta/gün", 12.0, "m²"),
        ],
        "Sıvacı (İç)": [
            ("ÇŞB — 25 m²/usta/gün",   25.0, "m²"),
            ("Alçı Sıva — 30 m²/usta/gün", 30.0, "m²"),
        ],
        "Sıvacı (Dış)": [
            ("ÇŞB — 20 m²/usta/gün",   20.0, "m²"),
        ],
        "Boyacı (İç)": [
            ("ÇŞB — 45 m²/usta/gün",   45.0, "m²"),
        ],
        "Boyacı (Dış)": [
            ("ÇŞB — 30 m²/usta/gün",   30.0, "m²"),
        ],
        "Fayansçı / Seramikçi": [
            ("ÇŞB — 8 m²/usta/gün",     8.0, "m²"),
            ("Mozaik — 5 m²/usta/gün",  5.0, "m²"),
        ],
        "Mermerci": [
            ("ÇŞB — 4 m²/usta/gün",     4.0, "m²"),
        ],
        "Parke / Laminat Ustası": [
            ("ÇŞB — 25 m²/usta/gün",   25.0, "m²"),
            ("Karo Parke — 15 m²/usta/gün", 15.0, "m²"),
        ],
        "Şap Ustası": [
            ("Şap — 40 m²/usta/gün",   40.0, "m²"),
            ("Kalın Şap — 25 m²/usta/gün", 25.0, "m²"),
        ],
        "Elektrikçi": [
            ("Tesisat Hattı — 50 m/usta/gün",  50.0, "m"),
            ("Pano Montaj — 5 adet/usta/gün",   5.0, "adet"),
        ],
        "Tesisatçı (Su/Pis Su)": [
            ("Boru Döşeme — 30 m/usta/gün",  30.0, "m"),
            ("PPR Boru — 40 m/usta/gün",     40.0, "m"),
        ],
        "Tesisatçı (Isı)": [
            ("Radyatör Montaj — 8 adet/usta/gün", 8.0, "adet"),
            ("Kombi Bağlantı — 2 adet/usta/gün",  2.0, "adet"),
        ],
        "Doğramacı (PVC)": [
            ("PVC Standart — 4 adet/usta/gün",  4.0, "adet"),
            ("PVC Büyük — 2 adet/usta/gün",     2.0, "adet"),
        ],
        "Doğramacı (Alüminyum)": [
            ("Alüminyum — 3 adet/usta/gün",     3.0, "adet"),
        ],
        "Çatıcı": [
            ("Kiremit — 80 m²/usta/gün",       80.0, "m²"),
            ("Trapez Sac — 120 m²/usta/gün",  120.0, "m²"),
        ],
        "Yalıtımcı (Mantolama)": [
            ("ÇŞB — 15 m²/usta/gün",   15.0, "m²"),
            ("Hızlı — 20 m²/usta/gün", 20.0, "m²"),
        ],
        "Yalıtımcı (Su)": [
            ("Su Yalıtımı — 25 m²/usta/gün", 25.0, "m²"),
        ],
        "İskele Ustası": [
            ("Kurma — 20 m²/usta/gün",  20.0, "m²"),
            ("Sökme — 30 m²/usta/gün",  30.0, "m²"),
        ],
        "Kazıcı / Hafriyatçı": [
            ("Elle Kazı — 3 m³/usta/gün",       3.0, "m³"),
            ("Makine Kazı — 100 m³/usta/gün", 100.0, "m³"),
        ],
        "Vinç Operatörü": [
            ("Vinç — 20 tur/usta/gün", 20.0, "adet"),
        ],
        "Genel İşçi": [
            ("Genel — 10 adet/usta/gün",    10.0, "adet"),
            ("Temizlik — 100 m²/usta/gün", 100.0, "m²"),
        ],
    }

    def __init__(self, task_data: Optional[Dict] = None,
                 tasks_list: Optional[List[Dict]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İş Ekle" if not task_data else "İş Düzenle")
        self.setMinimumSize(600, 720)
        self._task = task_data or {}
        self._all_tasks = [
            t for t in (tasks_list or [])
            if t.get("id") != (task_data or {}).get("id")
        ]
        self._dep_rows: List[Dict] = []
        self._build_ui()
        if task_data:
            self._load_data(task_data)

    # ------------------------------------------------------------------
    # UI İnşası
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # İş Adı
        self.ad_input = QLineEdit()
        form.addRow("İş Adı:", self.ad_input)

        # Süre
        self.sure_input = QSpinBox()
        self.sure_input.setRange(1, 3650)
        self.sure_input.setSuffix(" gün")
        form.addRow("Süre:", self.sure_input)

        # Tarih
        date_row = QHBoxLayout()
        self.baslangic_input = QDateEdit(QDate.currentDate())
        self.baslangic_input.setCalendarPopup(True)
        self.baslangic_input.setDisplayFormat("dd.MM.yyyy")
        date_row.addWidget(self.baslangic_input)
        date_row.addWidget(QLabel("—"))
        self.bitis_input = QDateEdit(QDate.currentDate().addDays(7))
        self.bitis_input.setCalendarPopup(True)
        self.bitis_input.setDisplayFormat("dd.MM.yyyy")
        date_row.addWidget(self.bitis_input)
        form.addRow("Tarih:", date_row)

        # Miktar + Birim combo + Otomatik süre butonu
        miktar_row = QHBoxLayout()
        self.miktar_input = QDoubleSpinBox()
        self.miktar_input.setRange(0, 999_999_999)
        self.miktar_input.setDecimals(2)
        self.miktar_input.setMinimumWidth(110)
        self.miktar_input.valueChanged.connect(self._auto_butce)
        miktar_row.addWidget(self.miktar_input)

        self.birim_combo = QComboBox()
        self.birim_combo.addItems(self.BIRIMLER)
        self.birim_combo.setFixedWidth(72)
        self.birim_combo.setToolTip("Miktar birimi")
        self.birim_combo.currentTextChanged.connect(self._on_birim_degisti)
        miktar_row.addWidget(self.birim_combo)

        auto_btn = QPushButton("🔄 Süre")
        auto_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        auto_btn.setToolTip("Miktar / (Verimlilik × Usta Sayısı) → Süre otomatik hesapla")
        auto_btn.clicked.connect(self._auto_sure)
        miktar_row.addWidget(auto_btn)
        form.addRow("Miktar:", miktar_row)

        # Ekip Türü (grup başlıklı)
        self.ekip_turu_input = QComboBox()
        self.ekip_turu_input.setMinimumWidth(220)
        self._ekip_doldur()
        self.ekip_turu_input.currentIndexChanged.connect(self._on_ekip_degisti)
        form.addRow("Ekip Türü:", self.ekip_turu_input)

        # Usta Sayısı
        self.usta_sayisi_input = QSpinBox()
        self.usta_sayisi_input.setRange(1, 50)
        self.usta_sayisi_input.setValue(2)
        form.addRow("Usta Sayısı:", self.usta_sayisi_input)

        # Verimlilik: Preset combo + manuel spin
        verim_row = QHBoxLayout()
        self.verimlilik_preset_combo = QComboBox()
        self.verimlilik_preset_combo.setMinimumWidth(240)
        self.verimlilik_preset_combo.setToolTip("ÇŞB birim fiyat analizine göre hazır değerler")
        self.verimlilik_preset_combo.currentIndexChanged.connect(
            self._on_verimlilik_preset_degisti
        )
        verim_row.addWidget(self.verimlilik_preset_combo)

        self.verimlilik_input = QDoubleSpinBox()
        self.verimlilik_input.setRange(0.01, 100_000)
        self.verimlilik_input.setDecimals(2)
        self.verimlilik_input.setValue(10.0)
        self.verimlilik_input.setFixedWidth(110)
        self.verimlilik_input.setToolTip("Manuel düzenleme yapabilirsiniz")
        verim_row.addWidget(self.verimlilik_input)

        self._verim_birim_label = QLabel("birim/usta/gün")
        self._verim_birim_label.setStyleSheet("color: #666; font-size: 10px;")
        verim_row.addWidget(self._verim_birim_label)
        form.addRow("Verimlilik:", verim_row)

        # Tamamlanma
        self.tamamlanma_input = QSpinBox()
        self.tamamlanma_input.setRange(0, 100)
        self.tamamlanma_input.setSuffix(" %")
        form.addRow("Tamamlanma:", self.tamamlanma_input)

        # Maliyet
        self.maliyet_input = QDoubleSpinBox()
        self.maliyet_input.setRange(0, 999_999_999)
        self.maliyet_input.setDecimals(2)
        self.maliyet_input.setSuffix(" ₺")
        form.addRow("Maliyet:", self.maliyet_input)

        # Birim Fiyat
        self.birim_fiyat_input = QDoubleSpinBox()
        self.birim_fiyat_input.setRange(0, 999_999_999)
        self.birim_fiyat_input.setDecimals(2)
        self.birim_fiyat_input.setSuffix(" ₺/birim")
        self.birim_fiyat_input.setToolTip("Birim Fiyat × Miktar = Bütçe (otomatik)")
        self.birim_fiyat_input.valueChanged.connect(self._auto_butce)
        form.addRow("Birim Fiyat:", self.birim_fiyat_input)

        # Bütçe
        self.butce_input = QDoubleSpinBox()
        self.butce_input.setRange(0, 999_999_999)
        self.butce_input.setDecimals(2)
        self.butce_input.setSuffix(" ₺")
        self.butce_input.setToolTip("Planlanan bütçe — hakediş hesabında kullanılır")
        form.addRow("Bütçe (Planlanan):", self.butce_input)

        # Gerçek Maliyet
        self.gercek_maliyet_input = QDoubleSpinBox()
        self.gercek_maliyet_input.setRange(0, 999_999_999)
        self.gercek_maliyet_input.setDecimals(2)
        self.gercek_maliyet_input.setSuffix(" ₺")
        self.gercek_maliyet_input.setToolTip("Gerçekleşen maliyet — EVM/CPI hesabında kullanılır")
        form.addRow("Gerçek Maliyet:", self.gercek_maliyet_input)

        # Kaynak
        self.kaynak_input = QLineEdit()
        form.addRow("Kaynak:", self.kaynak_input)

        # Milestone
        self.milestone_chk = QCheckBox("Kilometre Taşı (Milestone)")
        form.addRow("", self.milestone_chk)

        # Açıklama
        self.aciklama_input = QTextEdit()
        self.aciklama_input.setMaximumHeight(60)
        form.addRow("Açıklama:", self.aciklama_input)

        layout.addLayout(form)

        # ------------------------------------------------------------------
        # Önceki İşler (Bağımlılık) — sadece tasks_list verilmişse göster
        # ------------------------------------------------------------------
        if self._all_tasks:
            from PyQt6.QtWidgets import QGroupBox
            grp = QGroupBox("Önceki İşler (Bağımlılık)")
            grp_layout = QVBoxLayout(grp)
            grp_layout.setContentsMargins(6, 6, 6, 6)
            grp_layout.addWidget(QLabel(
                "Önce bitmesi gereken işleri işaretleyin (FS = Bitiş→Başlangıç)."
            ))
            self._dep_table = QTableWidget(len(self._all_tasks), 4)
            self._dep_table.setHorizontalHeaderLabels(
                ["Seç", "Görev Adı", "Tip", "Lag (Gün)"]
            )
            self._dep_table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.ResizeToContents
            )
            self._dep_table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.Stretch
            )
            self._dep_table.horizontalHeader().setSectionResizeMode(
                2, QHeaderView.ResizeMode.ResizeToContents
            )
            self._dep_table.horizontalHeader().setSectionResizeMode(
                3, QHeaderView.ResizeMode.ResizeToContents
            )
            self._dep_table.verticalHeader().setVisible(False)
            self._dep_table.setMaximumHeight(160)

            for row, t in enumerate(self._all_tasks):
                chk = QCheckBox()
                chk_widget = QWidget()
                chk_layout = QHBoxLayout(chk_widget)
                chk_layout.addWidget(chk)
                chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                chk_layout.setContentsMargins(0, 0, 0, 0)
                self._dep_table.setCellWidget(row, 0, chk_widget)
                self._dep_rows.append({"chk": chk})

                self._dep_table.setItem(
                    row, 1,
                    QTableWidgetItem(f"[{t.get('id')}] {t.get('ad', '')}")
                )

                tip_combo = QComboBox()
                tip_combo.addItems(["FS", "SS", "FF", "SF"])
                self._dep_table.setCellWidget(row, 2, tip_combo)
                self._dep_rows[row]["tip"] = tip_combo

                lag_spin = QSpinBox()
                lag_spin.setRange(-30, 30)
                lag_spin.setSuffix(" gün")
                self._dep_table.setCellWidget(row, 3, lag_spin)
                self._dep_rows[row]["lag"] = lag_spin

            grp_layout.addWidget(self._dep_table)
            layout.addWidget(grp)
        else:
            self._dep_table = None

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._validate_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        # İlk ekip türüne göre verimlilik listesini doldur
        self._on_ekip_degisti(self.ekip_turu_input.currentIndex())

    # ------------------------------------------------------------------
    # Yardımcı: Ekip combo'yu grup başlıklı doldur
    # ------------------------------------------------------------------
    def _ekip_doldur(self) -> None:
        from PyQt6.QtGui import QStandardItem
        from PyQt6.QtGui import QFont as _QFont
        model = self.ekip_turu_input.model()
        for ad, birim in self.EKIP_GRUPLARI:
            self.ekip_turu_input.addItem(ad)
            idx = self.ekip_turu_input.count() - 1
            item = model.item(idx)
            if item is None:
                continue
            if birim is None:
                # Grup başlığı: seçilemez, kalın-italik stil
                item.setEnabled(False)
                font = _QFont()
                font.setBold(True)
                font.setItalic(True)
                item.setFont(font)
                item.setForeground(QColor("#1976D2"))

    # ------------------------------------------------------------------
    # Sinyaller
    # ------------------------------------------------------------------
    def _on_ekip_degisti(self, idx: int) -> None:
        """Ekip türü değişince verimlilik presetlerini ve varsayılan birimi güncelle."""
        ekip_ad = self.ekip_turu_input.itemText(idx)
        presetler = self.EKIP_VERIMLILIK.get(ekip_ad, [])

        self.verimlilik_preset_combo.blockSignals(True)
        self.verimlilik_preset_combo.clear()
        if presetler:
            self.verimlilik_preset_combo.addItem("— Preset seçin —")
            for label, _val, _birim in presetler:
                self.verimlilik_preset_combo.addItem(label)
        else:
            self.verimlilik_preset_combo.addItem("— Bu ekip için preset yok —")
        self.verimlilik_preset_combo.blockSignals(False)

        # Ekip türünün varsayılan birimini birim_combo'ya yansıt
        varsayilan_birim = next(
            (b for a, b in self.EKIP_GRUPLARI if a == ekip_ad and b is not None),
            None
        )
        if varsayilan_birim:
            birim_idx = self.birim_combo.findText(varsayilan_birim)
            if birim_idx >= 0:
                self.birim_combo.setCurrentIndex(birim_idx)

        # İlk preset varsa otomatik uygula
        if presetler:
            _label, val, birim = presetler[0]
            self.verimlilik_input.setValue(val)
            self._verim_birim_label.setText(f"{birim}/usta/gün")
            self.verimlilik_preset_combo.setCurrentIndex(1)

    def _on_verimlilik_preset_degisti(self, idx: int) -> None:
        """Preset seçilince verimlilik değerini ve birimi güncelle."""
        if idx <= 0:
            return
        ekip_ad = self.ekip_turu_input.currentText()
        presetler = self.EKIP_VERIMLILIK.get(ekip_ad, [])
        preset_idx = idx - 1  # ilk item "— Preset seçin —"
        if 0 <= preset_idx < len(presetler):
            _label, val, birim = presetler[preset_idx]
            self.verimlilik_input.setValue(val)
            self._verim_birim_label.setText(f"{birim}/usta/gün")
            # Birimi miktar combo'ya yansıt
            b_idx = self.birim_combo.findText(birim)
            if b_idx >= 0:
                self.birim_combo.setCurrentIndex(b_idx)

    def _on_birim_degisti(self, birim: str) -> None:
        """Birim değişince verimlilik birim etiketini güncelle."""
        self._verim_birim_label.setText(f"{birim}/usta/gün")

    # ------------------------------------------------------------------
    # Veri Yükleme
    # ------------------------------------------------------------------
    def _load_data(self, task: Dict) -> None:
        self.ad_input.setText(task.get("ad", ""))
        self.sure_input.setValue(task.get("sure", 1))
        if task.get("baslangic"):
            try:
                d = date.fromisoformat(str(task["baslangic"]))
                self.baslangic_input.setDate(QDate(d.year, d.month, d.day))
            except (ValueError, TypeError):
                pass
        if task.get("bitis"):
            try:
                d = date.fromisoformat(str(task["bitis"]))
                self.bitis_input.setDate(QDate(d.year, d.month, d.day))
            except (ValueError, TypeError):
                pass
        self.miktar_input.setValue(task.get("miktar", 0.0))
        # Birim
        birim = task.get("miktar_birim", "m²")
        b_idx = self.birim_combo.findText(birim)
        if b_idx >= 0:
            self.birim_combo.setCurrentIndex(b_idx)
        # Ekip türü
        ekip = task.get("ekip_turu", "")
        e_idx = self.ekip_turu_input.findText(ekip)
        if e_idx >= 0:
            self.ekip_turu_input.setCurrentIndex(e_idx)
        # Verimlilik sonradan setlenir (ekip değişimi sinyali tetiklemiş olabilir)
        verimlilik = task.get("verimlilik", 0.0)
        if verimlilik > 0:
            self.verimlilik_input.setValue(verimlilik)
        self.usta_sayisi_input.setValue(task.get("usta_sayisi", 2))
        self.tamamlanma_input.setValue(task.get("tamamlanma_yuzdesi", 0))
        self.maliyet_input.setValue(task.get("maliyet", 0.0))
        self.birim_fiyat_input.setValue(task.get("birim_fiyat", 0.0))
        self.butce_input.setValue(task.get("butce", 0.0))
        self.gercek_maliyet_input.setValue(task.get("gercek_maliyet", 0.0))
        self.kaynak_input.setText(task.get("kaynak", ""))
        self.milestone_chk.setChecked(task.get("milestone", False))
        self.aciklama_input.setText(task.get("aciklama", ""))
        # Mevcut bağımlılıkları dep_table'a yükle
        if self._dep_table is not None:
            existing = {
                d["id"]: d
                for d in task.get("bagimliliklar_detay", [])
            }
            for row, t in enumerate(self._all_tasks):
                tid = t.get("id")
                ex = existing.get(tid)
                if ex:
                    self._dep_rows[row]["chk"].setChecked(True)
                    tip_idx = ["FS", "SS", "FF", "SF"].index(
                        ex.get("tip", "FS")
                    ) if ex.get("tip", "FS") in ["FS", "SS", "FF", "SF"] else 0
                    self._dep_rows[row]["tip"].setCurrentIndex(tip_idx)
                    self._dep_rows[row]["lag"].setValue(ex.get("lag", 0))

    # ------------------------------------------------------------------
    # Hesaplama Yardımcıları
    # ------------------------------------------------------------------
    def _auto_sure(self) -> None:
        """Miktar / (Verimlilik × Usta Sayısı) → Süre hesapla."""
        miktar = self.miktar_input.value()
        usta = self.usta_sayisi_input.value()
        verimlilik = self.verimlilik_input.value()
        if verimlilik > 0 and usta > 0 and miktar > 0:
            sure = math.ceil(miktar / (verimlilik * usta))
            self.sure_input.setValue(max(sure, 1))

    def _auto_butce(self) -> None:
        """Birim Fiyat × Miktar → Bütçe otomatik hesabı."""
        birim_fiyat = self.birim_fiyat_input.value()
        miktar = self.miktar_input.value()
        if birim_fiyat > 0 and miktar > 0:
            self.butce_input.setValue(birim_fiyat * miktar)

    def _validate_and_accept(self) -> None:
        if not self.ad_input.text().strip():
            QMessageBox.warning(self, "Hata", "İş adı boş olamaz.")
            return
        self.accept()

    # ------------------------------------------------------------------
    # Veri Çıkarma
    # ------------------------------------------------------------------
    def get_task_data(self) -> Dict:
        baslangic_qdate = self.baslangic_input.date()
        bitis_qdate = self.bitis_input.date()
        # Seçilen bağımlılıkları topla
        bagimliliklar_detay = []
        bagimliliklar = []
        if self._dep_table is not None:
            for row, t in enumerate(self._all_tasks):
                if self._dep_rows[row]["chk"].isChecked():
                    tid = t.get("id")
                    tip = self._dep_rows[row]["tip"].currentText()
                    lag = self._dep_rows[row]["lag"].value()
                    bagimliliklar_detay.append({"id": tid, "tip": tip, "lag": lag})
                    bagimliliklar.append(tid)
        return {
            "ad": self.ad_input.text().strip(),
            "sure": self.sure_input.value(),
            "baslangic": date(
                baslangic_qdate.year(), baslangic_qdate.month(), baslangic_qdate.day()
            ).isoformat(),
            "bitis": date(
                bitis_qdate.year(), bitis_qdate.month(), bitis_qdate.day()
            ).isoformat(),
            "miktar": self.miktar_input.value(),
            "miktar_birim": self.birim_combo.currentText(),
            "ekip_turu": self.ekip_turu_input.currentText(),
            "usta_sayisi": self.usta_sayisi_input.value(),
            "verimlilik": self.verimlilik_input.value(),
            "tamamlanma_yuzdesi": self.tamamlanma_input.value(),
            "maliyet": self.maliyet_input.value(),
            "birim_fiyat": self.birim_fiyat_input.value(),
            "butce": self.butce_input.value(),
            "gercek_maliyet": self.gercek_maliyet_input.value(),
            "kaynak": self.kaynak_input.text().strip(),
            "milestone": self.milestone_chk.isChecked(),
            "aciklama": self.aciklama_input.toPlainText().strip(),
            "bagimliliklar": bagimliliklar,
            "bagimliliklar_detay": bagimliliklar_detay,
        }


# ===========================================================================
# DependencyDialog
# ===========================================================================
class DependencyDialog(QDialog):
    """Bağımlılık yönetimi — FS/SS/FF/SF tip + Lag/Lead süresi."""

    def __init__(self, tasks: List[Dict], current_id: int,
                 existing_deps: Optional[List[Dict]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bağımlılıkları Düzenle")
        self.setMinimumSize(580, 400)
        self._tasks = [t for t in tasks if t.get("id") != current_id]
        self._current_id = current_id
        self._existing = {d["id"]: d for d in (existing_deps or [])}
        self._rows: List[Dict] = []  # {"check": QCheckBox, "tip": QComboBox, "lag": QSpinBox}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Önceki işleri seçin. Bağımlılık tipi ve gecikme (Lag) belirleyin."
        ))

        self._table = QTableWidget(len(self._tasks), 4)
        self._table.setHorizontalHeaderLabels(["Seç", "Görev Adı", "Tip", "Lag (Gün)"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)

        for row, t in enumerate(self._tasks):
            tid = t.get("id")
            ex = self._existing.get(tid, {})

            chk = QCheckBox()
            chk.setChecked(bool(ex))
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self._table.setCellWidget(row, 0, chk_widget)

            self._table.setItem(row, 1, QTableWidgetItem(
                f"[{tid}] {t.get('ad', '')}"
            ))

            tip_combo = QComboBox()
            tip_combo.addItems(["FS", "SS", "FF", "SF"])
            tip_combo.setCurrentText(ex.get("tip", "FS"))
            self._table.setCellWidget(row, 2, tip_combo)

            lag_spin = QSpinBox()
            lag_spin.setRange(-30, 30)
            lag_spin.setSuffix(" gün")
            lag_spin.setValue(ex.get("lag", 0))
            self._table.setCellWidget(row, 3, lag_spin)

            self._rows.append({
                "id": tid, "check": chk, "tip": tip_combo, "lag": lag_spin
            })

        layout.addWidget(self._table)

        legend = QLabel(
            "FS=Finish-to-Start (varsayılan) | SS=Start-to-Start | "
            "FF=Finish-to-Finish | SF=Start-to-Finish\n"
            "Lag>0: gecikme (kür süresi vb.) | Lag<0: örtüşme"
        )
        legend.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        layout.addWidget(legend)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_selected_deps(self) -> List[Dict]:
        result = []
        for r in self._rows:
            chk = r["check"]
            if chk.isChecked():
                result.append({
                    "id": r["id"],
                    "tip": r["tip"].currentText(),
                    "lag": r["lag"].value(),
                })
        return result

    def get_selected_ids(self) -> List[int]:
        """Geriye uyumluluk — sadece ID listesi döndür."""
        return [d["id"] for d in self.get_selected_deps()]


# ===========================================================================
# IlerlemeGuncellemeDialog
# ===========================================================================
class IlerlemeGuncellemeDialog(QDialog):
    """Tüm görevler için toplu ilerleme % güncelleme diyalogu."""

    def __init__(self, is_list: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("İlerleme % Güncelle")
        self.setMinimumSize(560, 400)
        self._is_list = is_list
        self._spin_map: Dict[int, QSpinBox] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        filtre_row = QHBoxLayout()
        filtre_row.addWidget(QLabel("Filtre:"))
        self._filtre_combo = QComboBox()
        self._filtre_combo.addItems(["Tümü", "Başlanmamış", "Devam Eden", "Tamamlananlar Hariç"])
        filtre_row.addWidget(self._filtre_combo)
        filtre_row.addStretch()
        layout.addLayout(filtre_row)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["İş Adı", "Mevcut %", "Yeni %"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table)

        for task in self._is_list:
            mevcut = int(task.get("tamamlanma_yuzdesi", 0) or 0)
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(task.get("ad", "")))
            self._table.setItem(row, 1, QTableWidgetItem(f"{mevcut}%"))
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setSuffix("%")
            spin.setValue(mevcut)
            self._table.setCellWidget(row, 2, spin)
            self._spin_map[task.get("id", row)] = spin

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_updates(self) -> Dict[int, int]:
        return {tid: spin.value() for tid, spin in self._spin_map.items()}


# ===========================================================================
# GanttWindow
# ===========================================================================
class GanttWindow(QWidget):
    """
    Ana Gantt iş programı penceresi.
    Sekmeler: İş Programı, Görsel Gantt, Tablo, Kritik Yol, S-Curve,
              What-If, Baseline, Kaynaklar, Gecikme, Bugün
    """

    def __init__(self, db_manager=None, parent=None):
        super().__init__(parent)
        self._db = db_manager
        self._engine = GanttEngine() if GanttEngine else None
        self._current_project_id: Optional[int] = None
        self._undo_stack: List[List[Dict]] = []
        self._max_undo = 20
        self._drag_drop_enabled = False
        self._baseline_data: Optional[Dict] = None
        self._alerts: List[Dict] = []
        self._is_list: List[Dict] = []

        self.setWindowTitle("Gantt İş Programı")
        self.setMinimumSize(1200, 750)
        self._build_ui()
        self._load_projeler()

        # Otomatik CPM — iş ekle/sil/düzenle sonrası 500ms debounce
        self._cpm_timer = QTimer(self)
        self._cpm_timer.setSingleShot(True)
        self._cpm_timer.setInterval(500)
        self._cpm_timer.timeout.connect(lambda: self.hesapla_program(silent=True))

    # ------------------------------------------------------------------
    # Ana UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._create_program_tab()
        self._create_gantt_tab()
        self._create_kritik_tab()
        self._create_s_curve_tab()
        self._create_what_if_tab()
        self._create_baseline_tab()
        self._create_gecikme_tab()
        self._create_hakedis_tab()
        self._create_bugun_tab()
        splitter.addWidget(self._tabs)

        splitter.setSizes([220, 980])
        main_layout.addWidget(splitter)

        status_bar = self._create_status_bar()
        main_layout.addWidget(status_bar)

    def _create_toolbar(self) -> QToolBar:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet(
            "QToolBar { background: #1565C0; padding: 4px; spacing: 4px; }"
            "QPushButton { color: white; background: #1976D2; border: none;"
            " border-radius: 4px; padding: 5px 10px; }"
            "QPushButton:hover { background: #1E88E5; }"
        )

        title = QLabel("  Gantt İş Programı")
        title.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        toolbar.addWidget(title)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        for label, slot in [
            ("▶ Hesapla (CPM)", self.hesapla_program),
            ("📅 Tarihi Kaydır", self._toplu_tarih_kaydir),
            ("📋 Metrajdan Üret", self._metrajdan_gorev_uret),
            ("💾 Kaydet", self.kaydet_program),
            ("📂 Yükle", self.yukle_program),
            ("📥 İçeri Aktar", self.goster_iceri_aktar_menu),
            ("📤 Dışa Aktar", self.goster_export_menu),
            ("↩ Geri Al", self._undo),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            toolbar.addWidget(btn)

        self._uyari_btn = QPushButton("⚠ Uyarılar [0]")
        self._uyari_btn.clicked.connect(self.goster_uyarilar)
        toolbar.addWidget(self._uyari_btn)

        return toolbar

    def _create_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        panel.setMaximumWidth(220)
        layout = QVBoxLayout(panel)

        lbl = QLabel("Proje Seç")
        lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl)

        self._proje_combo = QComboBox()
        self._proje_combo.currentIndexChanged.connect(self.on_proje_changed)
        layout.addWidget(self._proje_combo)

        lbl_bas = QLabel("Proje Başlangıcı:")
        lbl_bas.setStyleSheet("font-size: 11px;")
        layout.addWidget(lbl_bas)
        self._proje_baslangic_input = QDateEdit(QDate.currentDate())
        self._proje_baslangic_input.setCalendarPopup(True)
        self._proje_baslangic_input.setDisplayFormat("dd.MM.yyyy")
        layout.addWidget(self._proje_baslangic_input)

        for label, slot in [
            ("🧩 Şablon Sihirbazı", self.goster_sablon_dialog),
            ("📅 Tatil Ayarları", self.goster_tatil_dialog),
            ("📌 Baseline Kaydet", self.kaydet_baseline),
            ("⚖ Kaynak Dengele", self.otomatik_kaynak_dengele),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        self._drag_btn = QPushButton("🔀 Sürükle-Bırak: KAPALI")
        self._drag_btn.setCheckable(True)
        self._drag_btn.clicked.connect(self.toggle_drag_drop)
        layout.addWidget(self._drag_btn)

        layout.addStretch()

        self._alerts_panel = AlertsPanel()
        layout.addWidget(self._alerts_panel)

        return panel

    def _create_status_bar(self) -> QLabel:
        self._status_label = QLabel("Hazır")
        self._status_label.setStyleSheet(
            "background: #E3F2FD; padding: 3px 8px; border-top: 1px solid #90CAF9;"
        )
        return self._status_label

    # ------------------------------------------------------------------
    # Sekmeler
    # ------------------------------------------------------------------
    def _create_program_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        btn_row = QHBoxLayout()
        for label, slot in [
            ("+ İş Ekle", self.ekle_is),
            ("✏ Düzenle", self.duzenle_is),
            ("🗑 Sil", self.sil_is),
            ("🔗 Bağımlılık", self.ekle_bagimliluk),
            ("📊 İlerleme Güncelle", self._toplu_ilerleme_guncelle),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._is_table = QTableWidget(0, 8)
        self._is_table.setHorizontalHeaderLabels([
            "ID", "İş Adı", "Süre (Gün)", "Miktar", "Ekip", "Kaynak",
            "Milestone", "Bağımlılıklar",
        ])
        hdr = self._is_table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._is_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._is_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._is_table.doubleClicked.connect(self.duzenle_is)
        self._is_table.itemChanged.connect(self._on_is_table_item_changed)
        layout.addWidget(self._is_table)

        self._tabs.addTab(tab, "📋 İş Programı")

    def _create_gantt_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        ctrl = QHBoxLayout()
        for label, slot in [
            ("🔍+", self._zoom_in),
            ("🔍-", self._zoom_out),
            ("⊡ Sığdır", self._zoom_fit),
            ("🔄 Yenile", self.refresh_visual_gantt),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            ctrl.addWidget(btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._gantt_view = GanttChartView()
        self._gantt_view.task_dragged.connect(self.on_task_dragged)
        layout.addWidget(self._gantt_view)

        self._tabs.addTab(tab, "📊 Görsel Gantt")

    def _create_tablo_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._tablo = QTableWidget(0, 9)
        self._tablo.setHorizontalHeaderLabels([
            "İş Adı", "Süre", "ES", "EF", "LS", "LF",
            "Float", "Kritik", "Tamamlanma",
        ])
        self._tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._tablo)

        self._tabs.addTab(tab, "📑 Tablo Görünüm")

    def _create_kritik_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            "Kritik Yol — Float=0 olan görevler; gecikme proje bitiş tarihini doğrudan etkiler."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #B71C1C; font-weight: bold;")
        layout.addWidget(info)

        self._kritik_table = QTableWidget(0, 5)
        self._kritik_table.setHorizontalHeaderLabels([
            "İş Adı", "Başlangıç", "Bitiş", "Süre", "Bağımlılıklar",
        ])
        self._kritik_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._kritik_table)

        kpi_row = QHBoxLayout()
        self._kpi_proje_suresi = self._create_kpi_card(
            "Proje Süresi", "— gün", "#1976D2"
        )
        self._kpi_kritik_sayisi = self._create_kpi_card("Kritik İş", "—", "#F44336")
        self._kpi_toplam_float = self._create_kpi_card(
            "Toplam Float", "— gün", "#388E3C"
        )
        kpi_row.addWidget(self._kpi_proje_suresi)
        kpi_row.addWidget(self._kpi_kritik_sayisi)
        kpi_row.addWidget(self._kpi_toplam_float)
        layout.addLayout(kpi_row)

        renk_row = QHBoxLayout()
        for color, label in [
            ("#F44336", "Kritik Yol"),
            ("#2196F3", "Normal İş"),
            ("#FF9800", "Milestone"),
            ("#81D4FA", "Float (Bolluk)"),
        ]:
            self._add_renk_aciklama(renk_row, color, label)
        renk_row.addStretch()
        layout.addLayout(renk_row)

        self._tabs.addTab(tab, "🔴 Kritik Yol")

    def _create_s_curve_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        ctrl = QHBoxLayout()
        btn_refresh = QPushButton("🔄 S-Eğrisi Güncelle")
        btn_refresh.clicked.connect(self.refresh_s_curve)
        ctrl.addWidget(btn_refresh)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._s_curve = SCurveWidget()
        layout.addWidget(self._s_curve)

        evm_frame = QGroupBox("Kazanılmış Değer (EVM) Özeti")
        evm_layout = QGridLayout(evm_frame)
        self._evm_labels: Dict[str, QLabel] = {}
        evm_fields = [
            ("BAC", "Bütçe (BAC)"), ("PV", "Planlanan Değer (PV)"),
            ("EV", "Kazanılmış Değer (EV)"), ("AC", "Gerçek Maliyet (AC)"),
            ("SPI", "Zaman Performansı (SPI)"), ("CPI", "Maliyet Performansı (CPI)"),
        ]
        for i, (key, lbl_text) in enumerate(evm_fields):
            row, col = divmod(i, 3)
            evm_layout.addWidget(QLabel(lbl_text + ":"), row, col * 2)
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet("font-weight: bold;")
            self._evm_labels[key] = val_lbl
            evm_layout.addWidget(val_lbl, row, col * 2 + 1)
        layout.addWidget(evm_frame)

        self._tabs.addTab(tab, "📈 S-Curve")

    def _create_what_if_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel(
            "What-If analizi — seçilen işin süresini değiştirerek proje etkisini simüle edin."
        ))

        form = QFormLayout()
        self._whatif_is_combo = QComboBox()
        form.addRow("İş Seç:", self._whatif_is_combo)

        self._whatif_delta_spin = QSpinBox()
        self._whatif_delta_spin.setRange(-365, 365)
        self._whatif_delta_spin.setSuffix(" gün")
        form.addRow("Süre Değişimi:", self._whatif_delta_spin)
        layout.addLayout(form)

        btn_run = QPushButton("▶ Senaryoyu Çalıştır")
        btn_run.clicked.connect(self.calistir_what_if)
        layout.addWidget(btn_run)

        self._whatif_result_label = QLabel("Sonuç: —")
        self._whatif_result_label.setWordWrap(True)
        layout.addWidget(self._whatif_result_label)
        layout.addStretch()

        self._tabs.addTab(tab, "🧪 What-If")

    def _create_baseline_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        ctrl = QHBoxLayout()
        btn_analiz = QPushButton("📊 Baseline Karşılaştır")
        btn_analiz.clicked.connect(self.analiz_baseline)
        ctrl.addWidget(btn_analiz)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._baseline_table = QTableWidget(0, 5)
        self._baseline_table.setHorizontalHeaderLabels([
            "İş Adı", "Plan Bitiş", "Gerçek Bitiş", "Sapma (Gün)", "Durum",
        ])
        self._baseline_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._baseline_table)

        self._tabs.addTab(tab, "📌 Baseline")

    def _create_kaynak_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        ctrl = QHBoxLayout()
        btn_ekle = QPushButton("+ Kaynak Ekle")
        btn_ekle.clicked.connect(self.ekle_kaynak)
        btn_kontrol = QPushButton("⚠ Çakışma Kontrol")
        btn_kontrol.clicked.connect(self.kontrol_kaynak_cakisma)
        ctrl.addWidget(btn_ekle)
        ctrl.addWidget(btn_kontrol)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._kaynak_table = QTableWidget(0, 4)
        self._kaynak_table.setHorizontalHeaderLabels([
            "Kaynak", "Kapasite", "Kullanım (%)", "Durum",
        ])
        self._kaynak_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._kaynak_table)

        self._tabs.addTab(tab, "👷 Kaynaklar")

    def _create_gecikme_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("Gecikme Analizi — Taahhüt vs Gerçekleşen / 4735 sayılı K. Md.20 Ceza Hesabı"))

        # ── Sözleşme Bedeli Girişi ─────────────────────────────────────
        sozlesme_row = QHBoxLayout()
        sozlesme_row.addWidget(QLabel("Sözleşme Bedeli (₺):"))
        self._sozlesme_bedeli_spin = QDoubleSpinBox()
        self._sozlesme_bedeli_spin.setRange(0, 999_999_999_999)
        self._sozlesme_bedeli_spin.setDecimals(2)
        self._sozlesme_bedeli_spin.setSingleStep(10_000)
        self._sozlesme_bedeli_spin.setGroupSeparatorShown(True)
        self._sozlesme_bedeli_spin.setFixedWidth(200)
        self._sozlesme_bedeli_spin.setToolTip(
            "İhale sözleşme bedeli — gecikme cezası hesabında kullanılır.\n"
            "Boş bırakılırsa Gantt bütçe toplamı kullanılır."
        )
        sozlesme_row.addWidget(self._sozlesme_bedeli_spin)
        btn_gecikme_hesapla = QPushButton("🔄 Yenile")
        btn_gecikme_hesapla.clicked.connect(self._analiz_gecikme)
        sozlesme_row.addWidget(btn_gecikme_hesapla)
        sozlesme_row.addStretch()
        layout.addLayout(sozlesme_row)

        # ── Gecikme Tablosu ────────────────────────────────────────────
        self._gecikme_table = QTableWidget(0, 8)
        self._gecikme_table.setHorizontalHeaderLabels([
            "İş Adı", "Plan Bitiş", "Gerçek Bitiş",
            "Gecikme (Gün)", "Gecikme Türü", "Risk Skoru",
            "Ceza (₺)", "4735 K.20 Durumu",
        ])
        hdr = self._gecikme_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._gecikme_table)

        # ── KPI Özet Satırı ───────────────────────────────────────────
        kpi_row = QHBoxLayout()
        self._risk_label = QLabel("Risk Skoru: —")
        self._risk_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        kpi_row.addWidget(self._risk_label)

        self._ceza_toplam_label = QLabel("Toplam Ceza: —")
        self._ceza_toplam_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        kpi_row.addWidget(self._ceza_toplam_label)

        self._ceza_oran_label = QLabel("Ceza Oranı: —")
        self._ceza_oran_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        kpi_row.addWidget(self._ceza_oran_label)

        kpi_row.addStretch()
        layout.addLayout(kpi_row)

        # ── 4735 K.20 Uyarı Paneli ────────────────────────────────────
        self._k20_uyari_label = QLabel("")
        self._k20_uyari_label.setWordWrap(True)
        self._k20_uyari_label.setStyleSheet(
            "padding: 8px; border-radius: 4px; font-size: 12px;"
        )
        self._k20_uyari_label.setVisible(False)
        layout.addWidget(self._k20_uyari_label)

        self._tabs.addTab(tab, "⏰ Gecikme")

    def _create_hakedis_tab(self) -> None:
        """Hakediş Entegrasyonu — ilerleme% × bütçe = hak edilen tutar."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # KPI satırı
        kpi_row = QHBoxLayout()
        self._hak_kpi_toplam = self._create_kpi_card("Toplam Bütçe", "—", "#1976D2")
        self._hak_kpi_hakedis = self._create_kpi_card("Hak Edilen Tutar", "—", "#388E3C")
        self._hak_kpi_kalan = self._create_kpi_card("Kalan Bütçe", "—", "#F57C00")
        self._hak_kpi_yuzde = self._create_kpi_card("Tamamlanma", "—", "#7B1FA2")
        kpi_row.addWidget(self._hak_kpi_toplam)
        kpi_row.addWidget(self._hak_kpi_hakedis)
        kpi_row.addWidget(self._hak_kpi_kalan)
        kpi_row.addWidget(self._hak_kpi_yuzde)
        layout.addLayout(kpi_row)

        # Tablo
        self._hakedis_table = QTableWidget(0, 7)
        self._hakedis_table.setHorizontalHeaderLabels([
            "WBS", "İş Adı", "Tamamlanma%", "Bütçe (₺)",
            "Hak Edilen (₺)", "Kalan (₺)", "Durum",
        ])
        hdr = self._hakedis_table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._hakedis_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._hakedis_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._hakedis_table)

        # Butonlar
        btn_row = QHBoxLayout()
        btn_guncelle = QPushButton("🔄 Hakediş Hesapla")
        btn_guncelle.clicked.connect(self.guncelle_hakedis)
        btn_excel = QPushButton("📊 Excel'e Aktar")
        btn_excel.clicked.connect(self._hakedis_excel_export)
        btn_row.addWidget(btn_guncelle)
        btn_row.addWidget(btn_excel)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._tabs.addTab(tab, "💰 Hakediş")

    def _create_maliyet_takibi_tab(self) -> None:
        """Maliyet Takibi — EVM (Earned Value Management) analizi."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # EVM KPI kartları
        evm_row = QHBoxLayout()
        self._evm_bac = self._create_kpi_card("BAC (Toplam Bütçe)", "—", "#1565C0")
        self._evm_pv = self._create_kpi_card("PV (Planlanan Değer)", "—", "#0277BD")
        self._evm_ev = self._create_kpi_card("EV (Kazanılan Değer)", "—", "#2E7D32")
        self._evm_ac = self._create_kpi_card("AC (Gerçek Maliyet)", "—", "#C62828")
        evm_row.addWidget(self._evm_bac)
        evm_row.addWidget(self._evm_pv)
        evm_row.addWidget(self._evm_ev)
        evm_row.addWidget(self._evm_ac)
        layout.addLayout(evm_row)

        # Performans endeksleri
        perf_row = QHBoxLayout()
        self._evm_cpi = self._create_kpi_card("CPI (Maliyet Perf.)", "—", "#6A1B9A")
        self._evm_spi = self._create_kpi_card("SPI (Zaman Perf.)", "—", "#AD1457")
        self._evm_eac = self._create_kpi_card("EAC (Tahmini Toplam)", "—", "#E65100")
        self._evm_etc = self._create_kpi_card("ETC (Kalan Tahmin)", "—", "#4E342E")
        perf_row.addWidget(self._evm_cpi)
        perf_row.addWidget(self._evm_spi)
        perf_row.addWidget(self._evm_eac)
        perf_row.addWidget(self._evm_etc)
        layout.addLayout(perf_row)

        # Durum uyarı etiketi
        self._evm_durum_label = QLabel("Proje hesaplanmadı — önce CPM hesaplayın.")
        self._evm_durum_label.setStyleSheet(
            "padding: 6px; border-radius: 4px; font-weight: bold; "
            "background: #E3F2FD; color: #1565C0;"
        )
        layout.addWidget(self._evm_durum_label)

        # Görev bazlı detay tablosu
        self._maliyet_table = QTableWidget(0, 6)
        self._maliyet_table.setHorizontalHeaderLabels([
            "WBS", "İş Adı", "Bütçe (₺)", "Gerçek Maliyet (₺)",
            "EV (₺)", "CV (₺) Sapma",
        ])
        hdr = self._maliyet_table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._maliyet_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._maliyet_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._maliyet_table)

        btn_row = QHBoxLayout()
        btn_guncelle = QPushButton("🔄 Maliyet Analizi Yap")
        btn_guncelle.clicked.connect(self.guncelle_maliyet_takibi)
        btn_excel = QPushButton("📊 Excel'e Aktar")
        btn_excel.clicked.connect(self._maliyet_excel_export)
        btn_row.addWidget(btn_guncelle)
        btn_row.addWidget(btn_excel)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._tabs.addTab(tab, "📊 Maliyet Takibi")

    # ------------------------------------------------------------------
    # Auto-CPM & Tarih Kaydırma
    # ------------------------------------------------------------------
    def _schedule_auto_cpm(self) -> None:
        """İş değişikliğinden 500ms sonra CPM'i sessiz modda yeniden hesapla."""
        if hasattr(self, "_cpm_timer"):
            self._cpm_timer.start()

    def _toplu_tarih_kaydir(self) -> None:
        """Tüm işlerin başlangıç ve bitiş tarihlerini N gün kaydır."""
        if not self._is_list:
            QMessageBox.information(self, "Bilgi", "Kaydırılacak iş yok.")
            return
        gun, ok = QInputDialog.getInt(
            self, "Tarihi Kaydır",
            "Tüm işlerin tarihlerini kaç gün kaydırmak istiyorsunuz?\n"
            "(Pozitif = ileri, Negatif = geri)",
            value=0, min=-730, max=730,
        )
        if not ok or gun == 0:
            return
        self._push_undo()
        delta = timedelta(days=gun)
        for task in self._is_list:
            for alan in ("baslangic", "bitis", "plan_bitis", "gercek_bitis"):
                val = task.get(alan)
                if val:
                    try:
                        d = date.fromisoformat(str(val))
                        task[alan] = (d + delta).isoformat()
                    except (ValueError, TypeError):
                        pass
        self._yukle_is_listesi()
        self._schedule_auto_cpm()
        self._status_label.setText(f"Tüm tarihler {gun:+d} gün kaydırıldı.")

    # ------------------------------------------------------------------
    # F2 Satır İçi Düzenleme
    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:
        if (
            event.key() == Qt.Key.Key_F2
            and self._is_table.hasFocus()
            and self._is_table.currentRow() >= 0
        ):
            row = self._is_table.currentRow()
            self._is_table.setEditTriggers(
                QTableWidget.EditTrigger.AllEditTriggers
            )
            self._is_table.editItem(self._is_table.item(row, 1))
        else:
            super().keyPressEvent(event)

    def _on_is_table_item_changed(self, item) -> None:
        """F2 ile düzenlenen hücreyi _is_list'e yaz ve auto-CPM tetikle."""
        self._is_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        row = item.row()
        col = item.column()
        if row < 0 or row >= len(self._is_list):
            return
        val = item.text().strip()
        if col == 1:  # İş Adı
            self._is_list[row]["ad"] = val
            self._status_label.setText(f"İş adı güncellendi: {val}")
        elif col == 2:  # Süre
            try:
                self._is_list[row]["sure"] = int(val)
                self._status_label.setText(f"Süre güncellendi: {val} gün")
            except ValueError:
                self._yukle_is_listesi()
                return
        self._schedule_auto_cpm()

    # ------------------------------------------------------------------
    # İlerleme Güncelleme
    # ------------------------------------------------------------------
    def _toplu_ilerleme_guncelle(self) -> None:
        if not self._is_list:
            QMessageBox.information(self, "Bilgi", "İş listesi boş.")
            return
        dlg = IlerlemeGuncellemeDialog(self._is_list, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._push_undo()
            updates = dlg.get_updates()
            for task in self._is_list:
                tid = task.get("id")
                if tid in updates:
                    task["tamamlanma_yuzdesi"] = updates[tid]
            self._yukle_is_listesi()
            self.guncelle_hakedis()
            self._status_label.setText("İlerleme yüzdeleri güncellendi.")

    # ------------------------------------------------------------------
    # Hakediş Metodları
    # ------------------------------------------------------------------
    def guncelle_hakedis(self) -> None:
        """Hakediş tablosunu ve KPI kartlarını güncelle."""
        if not self._engine or not self._is_list:
            QMessageBox.information(self, "Bilgi", "Önce iş listesi oluşturun ve CPM hesaplayın.")
            return

        # Engine tasks'larını güncel is_list ile doldur
        self._sync_engine_tasks()

        try:
            sonuc = self._engine.calculate_hakedis()
        except Exception as exc:
            logger.error("Hakediş hesaplama hatası: %s", exc)
            QMessageBox.critical(self, "Hata", f"Hakediş hesaplanamadı:\n{exc}")
            return

        # KPI kartları
        def fmt(v): return f"{v:,.2f} ₺"
        self._hak_kpi_toplam.property("value_label").setText(fmt(sonuc['toplam_butce']))
        self._hak_kpi_hakedis.property("value_label").setText(fmt(sonuc['toplam_hakedis']))
        self._hak_kpi_kalan.property("value_label").setText(fmt(sonuc['kalan_butce']))
        self._hak_kpi_yuzde.property("value_label").setText(
            f"%{sonuc['tamamlanma_yuzdesi']:.1f}"
        )

        # Tablo doldur
        self._hakedis_table.setRowCount(0)
        for kalem in sonuc['kalemler']:
            row = self._hakedis_table.rowCount()
            self._hakedis_table.insertRow(row)
            self._hakedis_table.setItem(row, 0, QTableWidgetItem(kalem.get('wbs_kodu', '')))
            self._hakedis_table.setItem(row, 1, QTableWidgetItem(kalem.get('ad', '')))
            self._hakedis_table.setItem(
                row, 2, QTableWidgetItem(f"%{kalem.get('ilerleme', 0):.1f}")
            )
            self._hakedis_table.setItem(
                row, 3, QTableWidgetItem(f"{kalem.get('butce', 0):,.2f}")
            )
            self._hakedis_table.setItem(
                row, 4, QTableWidgetItem(f"{kalem.get('hak_edilen', 0):,.2f}")
            )
            self._hakedis_table.setItem(
                row, 5, QTableWidgetItem(f"{kalem.get('kalan', 0):,.2f}")
            )
            ilerleme = kalem.get('ilerleme', 0)
            durum = "Tamamlandı" if ilerleme >= 100 else ("Devam Ediyor" if ilerleme > 0 else "Başlanmadı")
            durum_item = QTableWidgetItem(durum)
            if ilerleme >= 100:
                durum_item.setForeground(QColor("#388E3C"))
            elif ilerleme > 0:
                durum_item.setForeground(QColor("#1976D2"))
            self._hakedis_table.setItem(row, 6, durum_item)

            if kalem.get('kritik'):
                for col in range(7):
                    item = self._hakedis_table.item(row, col)
                    if item:
                        item.setBackground(QColor("#FFF3E0"))

        self._status_label.setText(
            f"Hakediş hesaplandı — Toplam: {sonuc['toplam_hakedis']:,.2f} ₺ "
            f"/ %{sonuc['tamamlanma_yuzdesi']:.1f} tamamlandı"
        )

    def _hakedis_excel_export(self) -> None:
        """Hakediş tablosunu Excel'e aktar."""
        if not _OPENPYXL_OK:
            QMessageBox.warning(self, "Uyarı", "openpyxl yüklü değil.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Hakediş Excel Kaydet", "hakedis.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Hakediş"
            basliklar = ["WBS", "İş Adı", "Tamamlanma%", "Bütçe (₺)",
                         "Hak Edilen (₺)", "Kalan (₺)", "Durum"]
            ws.append(basliklar)
            for row in range(self._hakedis_table.rowCount()):
                satirlar = []
                for col in range(self._hakedis_table.columnCount()):
                    item = self._hakedis_table.item(row, col)
                    satirlar.append(item.text() if item else "")
                ws.append(satirlar)
            wb.save(path)
            QMessageBox.information(self, "Başarılı", f"Hakediş Excel kaydedildi:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Excel kaydetme hatası:\n{exc}")

    # ------------------------------------------------------------------
    # Maliyet Takibi Metodları
    # ------------------------------------------------------------------
    def guncelle_maliyet_takibi(self) -> None:
        """EVM hesabını yap ve Maliyet Takibi sekmesini güncelle."""
        if not self._engine or not self._is_list:
            QMessageBox.information(self, "Bilgi", "Önce iş listesi oluşturun ve CPM hesaplayın.")
            return

        self._sync_engine_tasks()

        try:
            sonuc = self._engine.calculate_maliyet_performans()
        except Exception as exc:
            logger.error("Maliyet performans hatası: %s", exc)
            QMessageBox.critical(self, "Hata", f"Maliyet analizi yapılamadı:\n{exc}")
            return

        def fmt(v): return f"{v:,.2f} ₺"
        def fmt3(v): return f"{v:.3f}"

        # KPI kartları
        self._evm_bac.property("value_label").setText(fmt(sonuc['bac']))
        self._evm_pv.property("value_label").setText(fmt(sonuc['pv']))
        self._evm_ev.property("value_label").setText(fmt(sonuc['ev']))
        self._evm_ac.property("value_label").setText(fmt(sonuc['ac']))
        self._evm_cpi.property("value_label").setText(fmt3(sonuc['cpi']))
        self._evm_spi.property("value_label").setText(fmt3(sonuc['spi']))
        self._evm_eac.property("value_label").setText(fmt(sonuc['eac']))
        self._evm_etc.property("value_label").setText(fmt(sonuc['etc']))

        # CPI/SPI renklendir
        cpi = sonuc['cpi']
        cpi_lbl = self._evm_cpi.property("value_label")
        if cpi >= 1.0:
            cpi_lbl.setStyleSheet("color: #2E7D32; font-size: 18px; font-weight: bold;")
        elif cpi >= 0.9:
            cpi_lbl.setStyleSheet("color: #F57C00; font-size: 18px; font-weight: bold;")
        else:
            cpi_lbl.setStyleSheet("color: #C62828; font-size: 18px; font-weight: bold;")

        spi = sonuc['spi']
        spi_lbl = self._evm_spi.property("value_label")
        if spi >= 1.0:
            spi_lbl.setStyleSheet("color: #2E7D32; font-size: 18px; font-weight: bold;")
        elif spi >= 0.9:
            spi_lbl.setStyleSheet("color: #F57C00; font-size: 18px; font-weight: bold;")
        else:
            spi_lbl.setStyleSheet("color: #C62828; font-size: 18px; font-weight: bold;")

        # Durum etiketi
        durum = sonuc.get('durum', 'iyi')
        if durum == 'kritik':
            self._evm_durum_label.setStyleSheet(
                "padding: 6px; border-radius: 4px; font-weight: bold; "
                "background: #FFEBEE; color: #C62828;"
            )
            self._evm_durum_label.setText(
                f"UYARI: CPI={cpi:.3f} / SPI={spi:.3f} — Bütçe veya zaman aşımı riski!"
            )
        elif durum == 'uyari':
            self._evm_durum_label.setStyleSheet(
                "padding: 6px; border-radius: 4px; font-weight: bold; "
                "background: #FFF8E1; color: #E65100;"
            )
            self._evm_durum_label.setText(
                f"DİKKAT: CPI={cpi:.3f} / SPI={spi:.3f} — Performans izlenmeye değer."
            )
        else:
            self._evm_durum_label.setStyleSheet(
                "padding: 6px; border-radius: 4px; font-weight: bold; "
                "background: #E8F5E9; color: #2E7D32;"
            )
            self._evm_durum_label.setText(
                f"NORMAL: CPI={cpi:.3f} / SPI={spi:.3f} — Proje bütçe ve zaman içinde."
            )

        # Görev detay tablosu
        self._maliyet_table.setRowCount(0)
        for gorev in sonuc.get('gorev_detaylari', []):
            row = self._maliyet_table.rowCount()
            self._maliyet_table.insertRow(row)
            self._maliyet_table.setItem(row, 0, QTableWidgetItem(gorev.get('wbs_kodu', '')))
            self._maliyet_table.setItem(row, 1, QTableWidgetItem(gorev.get('ad', '')))
            self._maliyet_table.setItem(
                row, 2, QTableWidgetItem(f"{gorev.get('butce', 0):,.2f}")
            )
            self._maliyet_table.setItem(
                row, 3, QTableWidgetItem(f"{gorev.get('gercek_maliyet', 0):,.2f}")
            )
            self._maliyet_table.setItem(
                row, 4, QTableWidgetItem(f"{gorev.get('ev', 0):,.2f}")
            )
            cv = gorev.get('cv', 0)
            cv_item = QTableWidgetItem(f"{cv:+,.2f}")
            cv_item.setForeground(QColor("#2E7D32") if cv >= 0 else QColor("#C62828"))
            self._maliyet_table.setItem(row, 5, cv_item)

            if gorev.get('butce_durumu') == 'asim':
                for col in range(6):
                    item = self._maliyet_table.item(row, col)
                    if item:
                        item.setBackground(QColor("#FFEBEE"))

        self._status_label.setText(
            f"Maliyet analizi tamamlandı — CPI: {cpi:.3f} | SPI: {spi:.3f} | EAC: {sonuc['eac']:,.2f} ₺"
        )

    def _maliyet_excel_export(self) -> None:
        """Maliyet takip tablosunu Excel'e aktar."""
        if not _OPENPYXL_OK:
            QMessageBox.warning(self, "Uyarı", "openpyxl yüklü değil.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Maliyet Excel Kaydet", "maliyet_takip.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Maliyet Takibi"
            basliklar = ["WBS", "İş Adı", "Bütçe (₺)", "Gerçek Maliyet (₺)", "EV (₺)", "CV (₺) Sapma"]
            ws.append(basliklar)
            for row in range(self._maliyet_table.rowCount()):
                satirlar = []
                for col in range(self._maliyet_table.columnCount()):
                    item = self._maliyet_table.item(row, col)
                    satirlar.append(item.text() if item else "")
                ws.append(satirlar)
            wb.save(path)
            QMessageBox.information(self, "Başarılı", f"Maliyet Excel kaydedildi:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Excel kaydetme hatası:\n{exc}")

    # ------------------------------------------------------------------
    # Engine-Senkronizasyon (is_list → engine.tasks)
    # ------------------------------------------------------------------
    def _sync_engine_tasks(self) -> None:
        """_is_list'teki verileri GanttEngine.tasks'a aktar (bütçe/maliyet dahil)."""
        if not self._engine:
            return
        from app.core.gantt_engine import Task
        for item in self._is_list:
            task_id = item.get("id", 0)
            if task_id in self._engine.tasks:
                task = self._engine.tasks[task_id]
                task.butce = float(item.get("butce", 0))
                task.gercek_maliyet = float(item.get("gercek_maliyet", 0))
                task.birim_fiyat = float(item.get("birim_fiyat", 0))
                task.ilerleme = float(item.get("tamamlanma_yuzdesi", 0))

    def _create_bugun_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        if _BUGUN_PANEL_OK:
            self._bugun_panel = BugunPaneli()
            layout.addWidget(self._bugun_panel)
        else:
            layout.addWidget(QLabel(
                "Bugün paneli modülü yüklenemedi (app.ui.bugun_paneli)."
            ))
            layout.addStretch()

        self._tabs.addTab(tab, "📅 Bugün")

    # ------------------------------------------------------------------
    # Yardımcı widget oluşturucular
    # ------------------------------------------------------------------
    def _create_kpi_card(self, title: str, value: str, color: str) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            f"QFrame {{ background: {color}15; border: 1px solid {color}; "
            f"border-radius: 6px; padding: 6px; }}"
        )
        layout = QVBoxLayout(frame)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {color}; font-size: 10px;")
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: bold;"
        )
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)
        frame.setProperty("value_label", lbl_value)
        return frame

    def _add_renk_aciklama(self, layout: QHBoxLayout, color: str, label: str) -> None:
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        lbl = QLabel(label)
        layout.addWidget(dot)
        layout.addWidget(lbl)

    # ------------------------------------------------------------------
    # Proje yükleme
    # ------------------------------------------------------------------
    def _load_projeler(self) -> None:
        self._proje_combo.blockSignals(True)
        self._proje_combo.clear()
        self._proje_combo.addItem("— Proje Seçin —", None)

        if self._db:
            try:
                for p in self._db.get_all_projects():
                    self._proje_combo.addItem(
                        p.get("ad", f"Proje {p['id']}"), p.get("id")
                    )
            except Exception as exc:
                logger.error("Proje yükleme hatası: %s", exc)

        self._proje_combo.blockSignals(False)

    def on_proje_changed(self, index: int) -> None:
        project_id = self._proje_combo.itemData(index)
        self._current_project_id = project_id
        if project_id and self._engine:
            try:
                if hasattr(self._engine, "yukle_proje"):
                    self._engine.yukle_proje(project_id, self._db)
                self._is_list = self._engine.get_tasks() if hasattr(self._engine, "get_tasks") else []
                self._yukle_is_listesi()
                self._status_label.setText(
                    f"Proje yüklendi: {self._proje_combo.currentText()}"
                )
            except Exception as exc:
                logger.error("Proje yükleme: %s", exc)

    def _yukle_is_listesi(self) -> None:
        self._is_table.blockSignals(True)
        self._is_table.setRowCount(0)
        for task in self._is_list:
            row = self._is_table.rowCount()
            self._is_table.insertRow(row)
            self._is_table.setItem(row, 0, QTableWidgetItem(str(task.get("id", ""))))
            self._is_table.setItem(row, 1, QTableWidgetItem(task.get("ad", "")))
            self._is_table.setItem(row, 2, QTableWidgetItem(str(task.get("sure", ""))))
            miktar_val = task.get("miktar", 0)
            miktar_birim = task.get("miktar_birim", "m²")
            miktar_str = f"{miktar_val:.2f} {miktar_birim}" if miktar_val else "—"
            self._is_table.setItem(row, 3, QTableWidgetItem(miktar_str))
            self._is_table.setItem(row, 4, QTableWidgetItem(task.get("ekip_turu", "")))
            self._is_table.setItem(row, 5, QTableWidgetItem(task.get("kaynak", "")))
            self._is_table.setItem(
                row, 6, QTableWidgetItem("✓" if task.get("milestone") else "")
            )
            deps_detay = task.get("bagimliliklar_detay", [])
            if deps_detay:
                dep_str = ", ".join(
                    f"{d['id']}({d['tip']}"
                    + (f"+{d['lag']}g" if d.get('lag', 0) > 0 else
                       f"{d['lag']}g" if d.get('lag', 0) < 0 else "")
                    + ")"
                    for d in deps_detay
                )
            else:
                dep_str = ", ".join(str(b) for b in task.get("bagimliliklar", []))
            self._is_table.setItem(
                row, 7,
                QTableWidgetItem(dep_str)
            )
        self._is_table.blockSignals(False)

    # ------------------------------------------------------------------
    # İş CRUD
    # ------------------------------------------------------------------
    def ekle_is(self) -> None:
        self._push_undo()
        dlg = TaskDialog(tasks_list=self._is_list, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_task_data()
            new_id = max((t.get("id", 0) for t in self._is_list), default=0) + 1
            data["id"] = new_id
            # bagimliliklar ve bagimliliklar_detay TaskDialog'dan geliyor
            self._is_list.append(data)
            self._yukle_is_listesi()
            self._status_label.setText(f"İş eklendi: {data['ad']}")
            self._schedule_auto_cpm()

    def duzenle_is(self) -> None:
        row = self._is_table.currentRow()
        if row < 0:
            return
        self._push_undo()
        task = self._is_list[row]
        dlg = TaskDialog(task_data=task, tasks_list=self._is_list, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated = dlg.get_task_data()
            updated["id"] = task["id"]
            # bagimliliklar ve bagimliliklar_detay TaskDialog'dan geliyor;
            # eğer boşsa (tasks_list yoktu) eski değeri koru
            if not updated.get("bagimliliklar_detay") and not updated.get("bagimliliklar"):
                updated["bagimliliklar"] = task.get("bagimliliklar", [])
                updated["bagimliliklar_detay"] = task.get("bagimliliklar_detay", [])
            self._is_list[row] = updated
            self._yukle_is_listesi()
            self._status_label.setText(f"İş güncellendi: {updated['ad']}")
            self._schedule_auto_cpm()

    def sil_is(self) -> None:
        row = self._is_table.currentRow()
        if row < 0:
            return
        task = self._is_list[row]
        reply = QMessageBox.question(
            self, "Sil",
            f"'{task['ad']}' silinsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._push_undo()
            self._is_list.pop(row)
            self._yukle_is_listesi()
            self._status_label.setText(f"İş silindi: {task['ad']}")
            self._schedule_auto_cpm()

    def ekle_bagimliluk(self) -> None:
        row = self._is_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Bilgi", "Önce bir iş seçin.")
            return
        task = self._is_list[row]
        existing = task.get("bagimliliklar_detay", [])
        dlg = DependencyDialog(
            self._is_list, task["id"],
            existing_deps=existing, parent=self
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._push_undo()
            deps = dlg.get_selected_deps()
            task["bagimliliklar_detay"] = deps
            task["bagimliliklar"] = [d["id"] for d in deps]
            self._yukle_is_listesi()
            self._status_label.setText(
                f"Bağımlılıklar güncellendi: {task['ad']} — "
                f"{len(deps)} önceki iş"
            )

    # ------------------------------------------------------------------
    # CPM Hesaplama
    # ------------------------------------------------------------------
    def hesapla_program(self, silent: bool = False) -> None:
        if not self._is_list:
            if not silent:
                QMessageBox.information(self, "Bilgi", "Önce iş listesi oluşturun.")
            return
        try:
            try:
                proje_bas = datetime.strptime(
                    self._proje_baslangic_input.date().toString("yyyy-MM-dd"), "%Y-%m-%d"
                )
            except Exception:
                proje_bas = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            if self._engine:
                # is_list dict'lerini engine Task nesnelerine dönüştür
                self._engine.tasks.clear()
                for item in self._is_list:
                    try:
                        from app.core.gantt_engine import Task
                        t = Task(
                            task_id=item.get("id", 0),
                            ad=item.get("ad", ""),
                            sure_gun=item.get("sure", 5),
                            ilerleme=item.get("tamamlanma_yuzdesi", 0.0),
                            kaynak=item.get("kaynak", ""),
                            milestone=item.get("milestone", False),
                        )
                        t.butce = float(item.get("butce", 0) or 0)
                        self._engine.add_task(t)
                    except Exception:
                        pass
                # Bağımlılıkları aktar
                for item in self._is_list:
                    succ_id = item.get("id", 0)
                    for dep in item.get("bagimliliklar_detay", []):
                        try:
                            self._engine.add_dependency(
                                dep.get("id", 0), succ_id,
                                dep.get("tip", "FS"), dep.get("lag", 0)
                            )
                        except Exception:
                            pass
                    # Eski format (sadece ID listesi) uyumu
                    for pred_id in item.get("bagimliliklar", []):
                        if isinstance(pred_id, int) and not item.get("bagimliliklar_detay"):
                            try:
                                self._engine.add_dependency(pred_id, succ_id, "FS", 0)
                            except Exception:
                                pass
                eng_result = self._engine.calculate_schedule(proje_bas)
                # Sonuçları is_list'e yaz
                engine_task_map = {t.task_id: t for t in self._engine.tasks.values()}
                for item in self._is_list:
                    et = engine_task_map.get(item.get("id"))
                    if et:
                        item["es"] = et.early_start.strftime("%d.%m.%Y") if et.early_start else ""
                        item["ef"] = et.early_finish.strftime("%d.%m.%Y") if et.early_finish else ""
                        item["ls"] = et.late_start.strftime("%d.%m.%Y") if et.late_start else ""
                        item["lf"] = et.late_finish.strftime("%d.%m.%Y") if et.late_finish else ""
                        item["float"] = et.float_gun
                        item["kritik_yol"] = et.kritik
                        item["tamamlanma_yuzdesi"] = item.get("tamamlanma_yuzdesi", 0)
                # _yukle_tablo_goruntum / _yukle_kritik_yol için uyumlu dict
                pb = eng_result.get("proje_bitis")
                if pb and hasattr(pb, "strftime"):
                    proje_bitis_str = pb.strftime("%d.%m.%Y")
                else:
                    proje_bitis_str = str(pb) if pb else "—"
                result = {
                    "tasks": self._is_list,
                    "proje_bitis": proje_bitis_str,
                    "kritik_yol": eng_result.get("kritik_yol", []),
                }
            else:
                result = {"tasks": self._is_list, "proje_bitis": "—"}
            self._is_list = result.get("tasks", self._is_list)
            self._yukle_is_listesi()
            self._yukle_tablo_goruntum(result)
            self._yukle_kritik_yol(result)
            self._analiz_gecikme()
            self.refresh_visual_gantt()
            self.refresh_s_curve()
            self._refresh_whatif_gorevler()
            self._kaynak_guncelle_tablo()

            if hasattr(self._engine, "kontrol_uyarilar"):
                self._alerts = self._engine.kontrol_uyarilar()
            self._alerts_panel.set_alerts(self._alerts)
            self.guncelle_uyari_badge()

            if _BUGUN_PANEL_OK and hasattr(self, "_bugun_panel"):
                try:
                    self._bugun_panel.yenile(result)
                except Exception:
                    pass

            self._status_label.setText(
                f"CPM hesaplandı — Proje bitişi: {result.get('proje_bitis', '—')}"
            )
        except Exception as exc:
            logger.error("Hesaplama hatası: %s", exc)
            if not silent:
                QMessageBox.critical(self, "Hata", f"Hesaplama hatası:\n{exc}")

    def _yukle_tablo_goruntum(self, result: Dict) -> None:
        if not hasattr(self, "_tablo"):
            return
        self._tablo.blockSignals(True)
        self._tablo.setRowCount(0)
        for task in result.get("tasks", []):
            row = self._tablo.rowCount()
            self._tablo.insertRow(row)
            self._tablo.setItem(row, 0, QTableWidgetItem(task.get("ad", "")))
            self._tablo.setItem(row, 1, QTableWidgetItem(str(task.get("sure", ""))))
            self._tablo.setItem(row, 2, QTableWidgetItem(str(task.get("es", ""))))
            self._tablo.setItem(row, 3, QTableWidgetItem(str(task.get("ef", ""))))
            self._tablo.setItem(row, 4, QTableWidgetItem(str(task.get("ls", ""))))
            self._tablo.setItem(row, 5, QTableWidgetItem(str(task.get("lf", ""))))
            float_val = task.get("float", 0)
            float_item = QTableWidgetItem(str(float_val))
            if float_val == 0:
                float_item.setForeground(QColor("#F44336"))
                float_item.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            self._tablo.setItem(row, 6, float_item)
            kritik_item = QTableWidgetItem("✓" if task.get("kritik_yol") else "")
            if task.get("kritik_yol"):
                kritik_item.setForeground(QColor("#F44336"))
            self._tablo.setItem(row, 7, kritik_item)
            self._tablo.setItem(
                row, 8,
                QTableWidgetItem(f"{task.get('tamamlanma_yuzdesi', 0):.0f}%")
            )
        self._tablo.blockSignals(False)

    def _yukle_kritik_yol(self, result: Dict) -> None:
        self._kritik_table.setRowCount(0)
        tasks = result.get("tasks", [])
        kritik_sayisi = 0
        toplam_float = 0

        for task in tasks:
            kritik = task.get("kritik_yol", False) or task.get("kritik", False)
            row = self._kritik_table.rowCount()
            self._kritik_table.insertRow(row)
            self._kritik_table.setItem(row, 0, QTableWidgetItem(task.get("ad", "")))
            self._kritik_table.setItem(row, 1, QTableWidgetItem(str(task.get("es", ""))))
            self._kritik_table.setItem(row, 2, QTableWidgetItem(str(task.get("ef", ""))))
            self._kritik_table.setItem(row, 3, QTableWidgetItem(str(task.get("sure", ""))))
            deps = task.get("bagimliliklar_detay", [])
            dep_str = ", ".join(
                f"{d['id']}({d.get('tip','FS')})" for d in deps
            ) if deps else ", ".join(str(b) for b in task.get("bagimliliklar", []))
            self._kritik_table.setItem(row, 4, QTableWidgetItem(dep_str))

            if kritik:
                kritik_sayisi += 1
                for col in range(5):
                    item = self._kritik_table.item(row, col)
                    if item:
                        item.setBackground(QColor("#FFEBEE"))
                        item.setForeground(QColor("#B71C1C"))
            else:
                float_val = int(task.get("float", 0) or 0)
                toplam_float += float_val

        # KPI kartlarını güncelle
        proje_suresi = result.get("proje_suresi_gun", result.get("proje_suresi", len(tasks) * 5))
        try:
            lbl = self._kpi_proje_suresi.findChildren(QLabel)[-1]
            lbl.setText(f"{proje_suresi} gün" if isinstance(proje_suresi, int) else str(proje_suresi))
            lbl2 = self._kpi_kritik_sayisi.findChildren(QLabel)[-1]
            lbl2.setText(str(kritik_sayisi))
            lbl3 = self._kpi_toplam_float.findChildren(QLabel)[-1]
            lbl3.setText(f"{toplam_float} gün")
        except Exception:
            pass

    def _analiz_gecikme(self) -> None:
        """
        Gecikme analizi + 4735 sayılı K. Md.20 ceza hesabı.
        Gecikme cezası: günlük ‰5 (binde beş) — 4735/K.20 sabiti.
        Fesih eşiği: toplam ceza sözleşme bedelinin %30'unu aştığında.
        """
        self._gecikme_table.setRowCount(0)
        total_risk = 0
        toplam_gecikme_gun = 0  # Kritik yol toplam gecikme günü

        # Sözleşme bedeli: kullanıcı girişi veya Gantt bütçe toplamı
        sozlesme_bedeli = self._sozlesme_bedeli_spin.value()
        if sozlesme_bedeli <= 0:
            sozlesme_bedeli = sum(
                float(t.get("butce", 0) or 0) for t in self._is_list
            )

        CEZA_ORANI = 0.005  # ‰5 = 0.005 (4735 Md.20)
        FESIH_ESIGI = 0.30  # %30 fesih eşiği

        for task in self._is_list:
            plan_bitis = task.get("plan_bitis") or task.get("bitis")
            gercek_bitis = task.get("gercek_bitis") or task.get("bitis")
            if not plan_bitis or not gercek_bitis:
                continue
            try:
                p = date.fromisoformat(str(plan_bitis))
                g = date.fromisoformat(str(gercek_bitis))
                gecikme = (g - p).days
            except (ValueError, TypeError):
                continue

            if gecikme <= 0:
                continue

            row = self._gecikme_table.rowCount()
            self._gecikme_table.insertRow(row)
            self._gecikme_table.setItem(row, 0, QTableWidgetItem(task.get("ad", "")))
            self._gecikme_table.setItem(row, 1, QTableWidgetItem(str(plan_bitis)))
            self._gecikme_table.setItem(row, 2, QTableWidgetItem(str(gercek_bitis)))
            self._gecikme_table.setItem(row, 3, QTableWidgetItem(str(gecikme)))

            if task.get("kritik_yol"):
                gecikme_turu = "Kritik"
                risk = gecikme * 3
                toplam_gecikme_gun += gecikme  # Sadece kritik yol gecikmeleri ceza hesabında
            else:
                gecikme_turu = "Normal"
                risk = gecikme
            total_risk += risk

            self._gecikme_table.setItem(row, 4, QTableWidgetItem(gecikme_turu))
            risk_item = QTableWidgetItem(str(risk))
            if risk > 30:
                risk_item.setForeground(QColor("#F44336"))
            elif risk > 10:
                risk_item.setForeground(QColor("#F57C00"))
            self._gecikme_table.setItem(row, 5, risk_item)

            # Ceza hesabı (sadece kritik yol)
            if task.get("kritik_yol") and sozlesme_bedeli > 0:
                ceza = gecikme * CEZA_ORANI * sozlesme_bedeli
                ceza_item = QTableWidgetItem(f"{ceza:,.0f} ₺")
                ceza_item.setForeground(QColor("#F44336"))
                self._gecikme_table.setItem(row, 6, ceza_item)
                # 4735 K.20 durum sütunu
                ceza_orani = gecikme * CEZA_ORANI
                if ceza_orani >= FESIH_ESIGI:
                    durum = "FESIH ESIGI ASILDI"
                    durum_item = QTableWidgetItem(durum)
                    durum_item.setForeground(QColor("#B71C1C"))
                    durum_item.setFont(QFont("Arial", 8, QFont.Weight.Bold))
                elif ceza_orani >= 0.20:
                    durum = f"%{ceza_orani*100:.1f} - Kritik Risk"
                    durum_item = QTableWidgetItem(durum)
                    durum_item.setForeground(QColor("#E65100"))
                elif ceza_orani >= 0.10:
                    durum = f"%{ceza_orani*100:.1f} - Uyari"
                    durum_item = QTableWidgetItem(durum)
                    durum_item.setForeground(QColor("#F57C00"))
                else:
                    durum = f"%{ceza_orani*100:.1f} - Normal"
                    durum_item = QTableWidgetItem(durum)
                    durum_item.setForeground(QColor("#388E3C"))
                self._gecikme_table.setItem(row, 7, durum_item)
            else:
                self._gecikme_table.setItem(row, 6, QTableWidgetItem("—"))
                self._gecikme_table.setItem(row, 7, QTableWidgetItem("—"))

        # ── Risk skoru ─────────────────────────────────────────────────
        if total_risk > 100:
            self._risk_label.setStyleSheet("color: #F44336; font-weight: bold;")
        elif total_risk > 30:
            self._risk_label.setStyleSheet("color: #F57C00; font-weight: bold;")
        else:
            self._risk_label.setStyleSheet("color: #388E3C; font-weight: bold;")
        self._risk_label.setText(f"Risk Skoru: {total_risk}")

        # ── Toplam ceza hesabı ─────────────────────────────────────────
        if sozlesme_bedeli > 0 and toplam_gecikme_gun > 0:
            toplam_ceza = toplam_gecikme_gun * CEZA_ORANI * sozlesme_bedeli
            toplam_ceza_orani = toplam_gecikme_gun * CEZA_ORANI
            self._ceza_toplam_label.setText(f"Toplam Ceza: {toplam_ceza:,.0f} ₺")
            self._ceza_oran_label.setText(
                f"Ceza Orani: %{toplam_ceza_orani * 100:.1f}"
            )
            # 4735 K.20 uyarı paneli
            if toplam_ceza_orani >= FESIH_ESIGI:
                self._k20_uyari_label.setText(
                    "KRITIK UYARI — 4735 sayili Kanun Md.20:\n"
                    f"Toplam gecikme cezasi sozlesme bedelinin %30'unu ASTI "
                    f"(%{toplam_ceza_orani * 100:.1f}). "
                    f"Idare sozlesmeyi feshedebilir ve yuklenici kara listeye alinabilir!\n"
                    f"Toplam ceza: {toplam_ceza:,.0f} TL | "
                    f"Sozlesme bedeli: {sozlesme_bedeli:,.0f} TL | "
                    f"Gecikme: {toplam_gecikme_gun} gun"
                )
                self._k20_uyari_label.setStyleSheet(
                    "padding: 10px; border-radius: 6px; font-size: 12px; "
                    "background: #FFEBEE; color: #B71C1C; border: 2px solid #F44336;"
                )
                self._k20_uyari_label.setVisible(True)
                if toplam_ceza_orani >= FESIH_ESIGI:
                    self._alerts.append({
                        "seviye": "kritik",
                        "mesaj": (
                            f"4735 Md.20 FESIH ESIGI: Gecikme cezasi %"
                            f"{toplam_ceza_orani*100:.1f} — Sozlesme feshi riski!"
                        ),
                    })
            elif toplam_ceza_orani >= 0.20:
                self._k20_uyari_label.setText(
                    f"UYARI — 4735 Md.20: Gecikme cezasi %{toplam_ceza_orani*100:.1f} "
                    f"(Fesih esigi %30). "
                    f"Toplam ceza: {toplam_ceza:,.0f} TL. Hizlanma onlemleri alinmali!"
                )
                self._k20_uyari_label.setStyleSheet(
                    "padding: 10px; border-radius: 6px; font-size: 12px; "
                    "background: #FFF3E0; color: #E65100; border: 2px solid #FF9800;"
                )
                self._k20_uyari_label.setVisible(True)
            elif toplam_ceza_orani >= 0.10:
                self._k20_uyari_label.setText(
                    f"DIKKAT — 4735 Md.20: Gecikme cezasi %{toplam_ceza_orani*100:.1f}. "
                    f"Toplam ceza: {toplam_ceza:,.0f} TL."
                )
                self._k20_uyari_label.setStyleSheet(
                    "padding: 8px; border-radius: 4px; font-size: 12px; "
                    "background: #FFFDE7; color: #F9A825; border: 1px solid #FBC02D;"
                )
                self._k20_uyari_label.setVisible(True)
            else:
                self._k20_uyari_label.setVisible(False)
        else:
            self._ceza_toplam_label.setText("Toplam Ceza: —")
            self._ceza_oran_label.setText("Ceza Orani: —")
            self._k20_uyari_label.setVisible(False)

    # ------------------------------------------------------------------
    # Görsel Gantt
    # ------------------------------------------------------------------
    def refresh_visual_gantt(self) -> None:
        if not self._is_list:
            return
        start_dates, end_dates = [], []
        for t in self._is_list:
            try:
                if t.get("baslangic"):
                    start_dates.append(date.fromisoformat(str(t["baslangic"])))
                if t.get("bitis"):
                    end_dates.append(date.fromisoformat(str(t["bitis"])))
            except (ValueError, TypeError):
                pass
        if start_dates and end_dates:
            self._gantt_view.draw_gantt(self._is_list, min(start_dates), max(end_dates))

    def _zoom_in(self) -> None:
        self._gantt_view.zoom_in()

    def _zoom_out(self) -> None:
        self._gantt_view.zoom_out()

    def _zoom_fit(self) -> None:
        self._gantt_view.zoom_fit()

    def on_task_dragged(self, task_id: int, delta_days: float) -> None:
        """
        Drag & Drop görev taşıma.
        delta_days: sürükleme ile elde edilen gün farkı (int/float).
        move_task(task_id, yeni_baslangic: datetime) bekliyor — datetime hesaplanır.
        cascade_dependents(task_id, gun_farki: int) bekliyor — gun_farki iletilir.
        """
        if not self._drag_drop_enabled or not self._engine:
            return
        gun_farki = int(delta_days)
        if gun_farki == 0:
            return
        self._push_undo()
        try:
            # Mevcut görevin başlangıç tarihini bul
            mevcut_task = self._engine.tasks.get(task_id) if hasattr(self._engine, "tasks") else None
            if mevcut_task is None:
                return

            from datetime import timedelta
            yeni_baslangic = mevcut_task.early_start + timedelta(days=gun_farki)

            if hasattr(self._engine, "move_task"):
                self._engine.move_task(task_id, yeni_baslangic)
            if hasattr(self._engine, "cascade_dependents"):
                self._engine.cascade_dependents(task_id, gun_farki)
            if hasattr(self._engine, "get_tasks"):
                self._is_list = self._engine.get_tasks()
            self._yukle_is_listesi()
            self.refresh_visual_gantt()
            self._status_label.setText(f"İş taşındı: {gun_farki:+d} gün")
            self._schedule_auto_cpm()
        except Exception as exc:
            logger.error("Drag-drop hatası: %s", exc)

    # ------------------------------------------------------------------
    # S-Curve
    # ------------------------------------------------------------------
    def refresh_s_curve(self) -> None:
        if not self._engine or not self._is_list:
            return
        try:
            if hasattr(self._engine, "hesapla_s_curve"):
                data = self._engine.hesapla_s_curve()
                self._s_curve.set_data(data)
                evm = data.get("evm", {})
                for key, lbl in self._evm_labels.items():
                    val = evm.get(key, "—")
                    lbl.setText(
                        f"{val:.2f}" if isinstance(val, float) else str(val)
                    )
        except Exception as exc:
            logger.error("S-Curve hatası: %s", exc)

    # ------------------------------------------------------------------
    # What-If
    # ------------------------------------------------------------------
    def _refresh_whatif_gorevler(self) -> None:
        self._whatif_is_combo.clear()
        for t in self._is_list:
            self._whatif_is_combo.addItem(
                f"[{t['id']}] {t.get('ad', '')}", t["id"]
            )

    def calistir_what_if(self) -> None:
        if not self._engine or not self._is_list:
            return
        task_id = self._whatif_is_combo.currentData()
        delta = self._whatif_delta_spin.value()
        if task_id is None:
            return
        try:
            if hasattr(self._engine, "whatif_analiz"):
                original, scenario = self._engine.whatif_analiz(task_id, delta)
                dlg = WhatIfResultDialog(original, scenario, parent=self)
                dlg.exec()
            else:
                self._whatif_result_label.setText("What-If motoru mevcut değil.")
        except Exception as exc:
            logger.error("What-If hatası: %s", exc)
            self._whatif_result_label.setText(f"Hata: {exc}")

    # ------------------------------------------------------------------
    # Baseline
    # ------------------------------------------------------------------
    def kaydet_baseline(self) -> None:
        if not self._is_list:
            QMessageBox.information(self, "Bilgi", "Kaydedilecek iş yok.")
            return
        self._baseline_data = {
            "tarih": date.today().isoformat(),
            "tasks": copy.deepcopy(self._is_list),
        }
        if self._engine and hasattr(self._engine, 'save_baseline'):
            try:
                self._engine.save_baseline()
            except Exception:
                pass
        QMessageBox.information(
            self, "Baseline",
            f"Baseline kaydedildi: {self._baseline_data['tarih']}"
        )
        self._status_label.setText("Baseline kaydedildi.")

    def analiz_baseline(self) -> None:
        if not self._baseline_data and (not self._engine or not hasattr(self._engine, 'get_baseline_comparison')):
            QMessageBox.information(self, "Bilgi", "Önce 'Baseline Kaydet' ile referans plan oluşturun.")
            return

        self._baseline_table.setRowCount(0)

        # Engine baseline kullan
        if self._engine and hasattr(self._engine, 'get_baseline_comparison'):
            try:
                karsilastirma = self._engine.get_baseline_comparison()
                for item in karsilastirma:
                    row = self._baseline_table.rowCount()
                    self._baseline_table.insertRow(row)
                    self._baseline_table.setItem(row, 0, QTableWidgetItem(item.get("ad", "")))
                    plan = item.get("baseline_bitis", "")
                    gercek = item.get("bitis", "")
                    sapma = item.get("bitis_sapma", 0)
                    durum = "Zamanında" if sapma <= 0 else f"{sapma} gün gecikme"
                    self._baseline_table.setItem(row, 1, QTableWidgetItem(str(plan) if plan else "—"))
                    self._baseline_table.setItem(row, 2, QTableWidgetItem(str(gercek) if gercek else "—"))
                    sapma_item = QTableWidgetItem(str(sapma))
                    sapma_item.setForeground(QColor("#27ae60") if sapma <= 0 else QColor("#e74c3c"))
                    self._baseline_table.setItem(row, 3, sapma_item)
                    self._baseline_table.setItem(row, 4, QTableWidgetItem(durum))
                return
            except Exception:
                pass

        # Fallback: is_list vs baseline_data
        if not self._baseline_data:
            QMessageBox.information(self, "Bilgi", "Önce 'Baseline Kaydet' ile referans plan oluşturun.")
            return

        baseline_map = {t.get("id"): t for t in self._baseline_data.get("tasks", [])}
        for task in self._is_list:
            bl = baseline_map.get(task.get("id"), {})
            if not bl:
                continue
            row = self._baseline_table.rowCount()
            self._baseline_table.insertRow(row)
            self._baseline_table.setItem(row, 0, QTableWidgetItem(task.get("ad", "")))
            plan_bitis = bl.get("ef", bl.get("bitis_tarihi", bl.get("bitis", "—")))
            gercek_bitis = task.get("ef", task.get("bitis_tarihi", task.get("bitis", "—")))
            try:
                p = datetime.strptime(str(plan_bitis), "%d.%m.%Y")
                g = datetime.strptime(str(gercek_bitis), "%d.%m.%Y")
                sapma = (g - p).days
            except Exception:
                try:
                    p = date.fromisoformat(str(plan_bitis))
                    g = date.fromisoformat(str(gercek_bitis))
                    sapma = (g - p).days
                except Exception:
                    sapma = 0
            durum = "Zamanında" if sapma <= 0 else f"{sapma} gün gecikme"
            self._baseline_table.setItem(row, 1, QTableWidgetItem(str(plan_bitis)))
            self._baseline_table.setItem(row, 2, QTableWidgetItem(str(gercek_bitis)))
            sapma_item = QTableWidgetItem(str(sapma))
            sapma_item.setForeground(QColor("#27ae60") if sapma <= 0 else QColor("#e74c3c"))
            self._baseline_table.setItem(row, 3, sapma_item)
            self._baseline_table.setItem(row, 4, QTableWidgetItem(durum))

    # ------------------------------------------------------------------
    # Kaynaklar
    # ------------------------------------------------------------------
    def ekle_kaynak(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Kaynak Ekle")
        layout = QFormLayout(dlg)
        ad_input = QLineEdit()
        kapasite_input = QSpinBox()
        kapasite_input.setRange(1, 1000)
        layout.addRow("Kaynak Adı:", ad_input)
        layout.addRow("Kapasite:", kapasite_input)
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addRow(btn_box)

        if dlg.exec() == QDialog.DialogCode.Accepted and ad_input.text().strip():
            ad = ad_input.text().strip()
            kapasite = kapasite_input.value()
            if self._engine and hasattr(self._engine, 'add_kaynak'):
                try:
                    self._engine.add_kaynak(ad, kapasite)
                except Exception:
                    pass
            self._kaynak_guncelle_tablo()

    def yukle_kaynaklar(self, kaynaklar: List[Dict]) -> None:
        if not hasattr(self, "_kaynak_table"):
            return
        self._kaynak_table.setRowCount(0)
        for k in kaynaklar:
            row = self._kaynak_table.rowCount()
            self._kaynak_table.insertRow(row)
            self._kaynak_table.setItem(row, 0, QTableWidgetItem(k.get("ad", "")))
            self._kaynak_table.setItem(row, 1, QTableWidgetItem(str(k.get("kapasite", ""))))
            kullanim = k.get("kullanim", 0)
            self._kaynak_table.setItem(row, 2, QTableWidgetItem(f"{kullanim:.0f}"))
            durum = "Aşırı Yük" if kullanim > 100 else "Normal"
            durum_item = QTableWidgetItem(durum)
            if kullanim > 100:
                durum_item.setForeground(QColor("#F44336"))
            self._kaynak_table.setItem(row, 3, durum_item)

    def _kaynak_guncelle_tablo(self) -> None:
        if not hasattr(self, "_kaynak_table"):
            return
        self._kaynak_table.setRowCount(0)
        if not self._engine:
            return
        try:
            kaynaklar = getattr(self._engine, 'kaynaklar', {})
            yukleme = {}
            if hasattr(self._engine, 'get_kaynak_yukleme'):
                yukleme = self._engine.get_kaynak_yukleme() or {}
            for kaynak_ad, kaynak in (kaynaklar.items() if isinstance(kaynaklar, dict) else []):
                row = self._kaynak_table.rowCount()
                self._kaynak_table.insertRow(row)
                kapasite = getattr(kaynak, 'kapasite', 1) if hasattr(kaynak, 'kapasite') else kaynak.get('kapasite', 1) if isinstance(kaynak, dict) else 1
                kullanim = yukleme.get(kaynak_ad, {}).get('kullanim_yuzdesi', 0)
                durum = "Aşım" if kullanim > 100 else "Yoğun" if kullanim > 80 else "Normal"
                self._kaynak_table.setItem(row, 0, QTableWidgetItem(str(kaynak_ad)))
                self._kaynak_table.setItem(row, 1, QTableWidgetItem(str(kapasite)))
                self._kaynak_table.setItem(row, 2, QTableWidgetItem(f"{kullanim:.0f}%"))
                self._kaynak_table.setItem(row, 3, QTableWidgetItem(durum))
        except Exception as e:
            logger.warning(f"Kaynak tablo güncellenemedi: {e}")

    def kontrol_kaynak_cakisma(self) -> None:
        if not self._engine:
            QMessageBox.information(self, "Bilgi", "Kaynak çakışma motoru mevcut değil.")
            return
        metod = getattr(self._engine, 'check_kaynak_cakisma',
                getattr(self._engine, 'kontrol_kaynak_cakisma', None))
        if not metod:
            QMessageBox.information(self, "Bilgi", "Kaynak çakışma motoru mevcut değil.")
            return
        try:
            cakismalar = metod()
            if not cakismalar:
                QMessageBox.information(self, "Kaynak", "Kaynak çakışması yok.")
            else:
                msg = "\n".join(
                    f"• {c.get('kaynak')}: {c.get('mesaj', '')}" for c in cakismalar
                )
                QMessageBox.warning(self, "Kaynak Çakışması", msg)
        except Exception as exc:
            logger.error("Kaynak kontrol hatası: %s", exc)

    def otomatik_kaynak_dengele(self) -> None:
        if not self._engine or not hasattr(self._engine, "kaynak_dengele"):
            QMessageBox.information(self, "Bilgi", "Kaynak dengeleme motoru mevcut değil.")
            return
        self._push_undo()
        try:
            self._engine.kaynak_dengele()
            if hasattr(self._engine, "get_tasks"):
                self._is_list = self._engine.get_tasks()
            self._yukle_is_listesi()
            self.refresh_visual_gantt()
            QMessageBox.information(self, "Kaynak Dengele", "Kaynaklar otomatik dengelendi.")
        except Exception as exc:
            logger.error("Kaynak dengele hatası: %s", exc)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def goster_export_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("📊 Excel'e Aktar", self.export_excel)
        menu.addAction("📄 PDF'e Aktar", self.export_pdf)
        menu.addAction("🗂 JSON'a Aktar", self.export_json)
        menu.exec(self.mapToGlobal(self.rect().topRight()))

    def export_excel(self) -> None:
        if not _OPENPYXL_OK:
            QMessageBox.warning(self, "Hata", "openpyxl paketi yüklü değil.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Gantt"
            ws.append(["İş Adı", "Süre", "Başlangıç", "Bitiş", "Float", "Kritik", "Tamamlanma"])
            for task in self._is_list:
                ws.append([
                    task.get("ad", ""),
                    task.get("sure", ""),
                    str(task.get("baslangic", "")),
                    str(task.get("bitis", "")),
                    task.get("float", ""),
                    "Evet" if task.get("kritik_yol") else "Hayır",
                    f"{task.get('tamamlanma_yuzdesi', 0):.0f}%",
                ])
            wb.save(path)
            self._status_label.setText(f"Excel kaydedildi: {path}")
            QMessageBox.information(self, "Başarılı", f"Excel dosyası kaydedildi:\n{path}")
        except Exception as exc:
            logger.error("Excel export hatası: %s", exc)
            QMessageBox.critical(self, "Hata", str(exc))

    def export_pdf(self) -> None:
        if not _REPORTLAB_OK:
            QMessageBox.warning(self, "Hata", "reportlab paketi yüklü değil.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "PDF Kaydet", "", "PDF (*.pdf)")
        if not path:
            return
        try:
            doc = SimpleDocTemplate(path, pagesize=landscape(A4))
            styles = getSampleStyleSheet()
            elements = [
                Paragraph("Gantt İş Programı", styles["Title"]),
                Spacer(1, 0.4 * cm),
            ]
            headers = ["İş Adı", "Süre", "Başlangıç", "Bitiş", "Float", "Kritik", "Tamamlanma"]
            data = [headers]
            for task in self._is_list:
                data.append([
                    task.get("ad", ""),
                    str(task.get("sure", "")),
                    str(task.get("baslangic", "")),
                    str(task.get("bitis", "")),
                    str(task.get("float", "")),
                    "Evet" if task.get("kritik_yol") else "Hayır",
                    f"{task.get('tamamlanma_yuzdesi', 0):.0f}%",
                ])
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#1976D2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [rl_colors.white, rl_colors.HexColor("#E3F2FD")]),
                ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]))
            elements.append(table)
            doc.build(elements)
            self._status_label.setText(f"PDF kaydedildi: {path}")
            QMessageBox.information(self, "Başarılı", f"PDF kaydedildi:\n{path}")
        except Exception as exc:
            logger.error("PDF export hatası: %s", exc)
            QMessageBox.critical(self, "Hata", str(exc))

    def export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "JSON Kaydet", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {"versiyon": "2.0", "tarih": date.today().isoformat(), "tasks": self._is_list},
                    f, ensure_ascii=False, indent=2, default=str,
                )
            self._status_label.setText(f"JSON kaydedildi: {path}")
            QMessageBox.information(self, "Başarılı", f"JSON kaydedildi:\n{path}")
        except Exception as exc:
            logger.error("JSON export hatası: %s", exc)
            QMessageBox.critical(self, "Hata", str(exc))

    # ------------------------------------------------------------------
    # İçeri Aktar
    # ------------------------------------------------------------------
    def goster_iceri_aktar_menu(self) -> None:
        """İçeri aktarma format menüsünü gösterir."""
        menu = QMenu(self)
        menu.addAction("📊 Excel'den İçeri Aktar (.xlsx)", self._aktar_excel)
        menu.addAction("📄 CSV'den İçeri Aktar (.csv)", self._aktar_csv)
        menu.addAction("🗂 JSON'dan İçeri Aktar (.json)", self._aktar_json_dosya)
        menu.addSeparator()
        menu.addAction("📋 Boş Excel Şablonu İndir", self._sablon_excel_indir)
        menu.exec(self.mapToGlobal(self.rect().topRight()))

    def _sablon_excel_indir(self) -> None:
        """Kullanıcıya doldurabileceği boş bir Excel şablonu kaydeder."""
        if not _OPENPYXL_OK:
            QMessageBox.warning(self, "Uyarı", "openpyxl paketi yüklü değil. Şablon oluşturulamadı.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Gantt Şablonu Kaydet", "gantt_sablon.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Gantt Şablon"
            basliklar = [
                "İş Adı", "Süre (Gün)", "Başlangıç", "Bitiş",
                "Miktar", "Birim", "Kaynak/Ekip",
                "Öncüller (ID)", "Milestone (evet/hayır)",
                "Tamamlanma (%)", "Bütçe (TL)", "Açıklama",
            ]
            ws.append(basliklar)
            # Başlık stili
            from openpyxl.styles import Font, PatternFill, Alignment
            baslik_font = Font(bold=True, color="FFFFFF")
            baslik_doldur = PatternFill("solid", fgColor="1976D2")
            for cell in ws[1]:
                cell.font = baslik_font
                cell.fill = baslik_doldur
                cell.alignment = Alignment(horizontal="center")
            # Örnek satır
            ws.append([
                "Temel Kazısı", 5, "2026-04-01", "2026-04-05",
                850.0, "m³", "Hafriyatçı",
                "", "hayır", 0, 0, "Zemin: kil+kum",
            ])
            # Sütun genişlikleri
            for col, genislik in enumerate(
                [35, 12, 14, 14, 10, 8, 18, 14, 20, 14, 14, 30], start=1
            ):
                ws.column_dimensions[
                    openpyxl.utils.get_column_letter(col)
                ].width = genislik
            wb.save(path)
            self._status_label.setText(f"Şablon kaydedildi: {path}")
            QMessageBox.information(self, "Başarılı", f"Şablon kaydedildi:\n{path}\n\nDoldurup 'Excel'den İçeri Aktar' ile yükleyin.")
        except Exception as exc:
            logger.error("Şablon oluşturma hatası: %s", exc)
            QMessageBox.critical(self, "Hata", str(exc))

    # ── Ortak yardımcı ─────────────────────────────────────────────────
    @staticmethod
    def _sutun_indeksi(basliklar: list, adaylar: list) -> int:
        """Başlık listesinden aday isimlerden birini bulur; -1 döner bulamazsa."""
        basliklar_lower = [str(b).lower().strip() for b in basliklar]
        for aday in adaylar:
            try:
                return basliklar_lower.index(aday.lower())
            except ValueError:
                pass
        return -1

    def _satiri_goreve_donustur(self, satir: dict, gorev_id: int) -> Optional[Dict]:
        """Sözlük satırından Gantt görev dict'i oluşturur. None döner geçersizse."""
        ad = str(satir.get("ad", "")).strip()
        if not ad:
            return None
        try:
            sure = int(float(str(satir.get("sure", 1)) or 1))
        except (ValueError, TypeError):
            sure = 1
        sure = max(1, sure)

        baslangic_str = str(satir.get("baslangic", "")).strip()
        bitis_str = str(satir.get("bitis", "")).strip()

        # Tarih normalizasyonu
        def _tarih_cevir(s: str) -> str:
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    pass
            return ""

        baslangic = _tarih_cevir(baslangic_str) or date.today().isoformat()
        bitis = _tarih_cevir(bitis_str) or ""

        try:
            miktar = float(str(satir.get("miktar", 0)) or 0)
        except (ValueError, TypeError):
            miktar = 0.0

        oncul_str = str(satir.get("oncul", "")).strip()
        bagimliliklar = []
        if oncul_str:
            for p in oncul_str.replace(";", ",").split(","):
                p = p.strip()
                if p.isdigit():
                    bagimliliklar.append(int(p))

        milestone_raw = str(satir.get("milestone", "")).strip().lower()
        milestone = milestone_raw in ("evet", "1", "true", "yes", "✓")

        try:
            tamamlanma = int(float(str(satir.get("tamamlanma", 0)) or 0))
            tamamlanma = max(0, min(100, tamamlanma))
        except (ValueError, TypeError):
            tamamlanma = 0

        try:
            butce = float(str(satir.get("butce", 0)) or 0)
        except (ValueError, TypeError):
            butce = 0.0

        return {
            "id": gorev_id,
            "ad": ad,
            "sure": sure,
            "baslangic": baslangic,
            "bitis": bitis,
            "miktar": miktar,
            "miktar_birim": str(satir.get("birim", "m²")).strip() or "m²",
            "ekip_turu": str(satir.get("ekip", "")).strip(),
            "kaynak": str(satir.get("kaynak", "")).strip(),
            "bagimliliklar": bagimliliklar,
            "bagimliliklar_detay": [],
            "milestone": milestone,
            "tamamlanma_yuzdesi": tamamlanma,
            "butce": butce,
            "gercek_maliyet": 0.0,
            "birim_fiyat": 0.0,
            "aciklama": str(satir.get("aciklama", "")).strip(),
            "kritik_yol": False,
            "float": 0,
            "wbs_kodu": "",
        }

    def _gosterge_ve_yukle(self, yeni_gorevler: List[Dict], dosya_adi: str) -> None:
        """Import edilen görevleri mevcut listeye ekle/yenile sorusunu sorar ve yükler."""
        if not yeni_gorevler:
            QMessageBox.warning(self, "Uyarı", "İçeri aktarılacak geçerli görev bulunamadı.")
            return

        mod = QMessageBox.question(
            self,
            "İçeri Aktarma Modu",
            f"{len(yeni_gorevler)} görev bulundu.\n\n"
            "Mevcut iş programına EKLEMEK mi,\nyoksa SIFIRDAN YÜKLEMEK mi istersiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if mod == QMessageBox.StandardButton.Cancel:
            return

        if mod == QMessageBox.StandardButton.No:
            # Sıfırla
            self._undo_stack.append(copy.deepcopy(self._is_list))
            self._is_list = yeni_gorevler
        else:
            # Ekle — ID'leri mevcut maksimuma göre ötele
            self._undo_stack.append(copy.deepcopy(self._is_list))
            mevcut_max = max((t.get("id", 0) for t in self._is_list), default=0)
            for g in yeni_gorevler:
                eski_id = g.get("id", 0)
                g["id"] = mevcut_max + eski_id
                # Bağımlılıkları da ötele
                g["bagimliliklar"] = [mevcut_max + b for b in g.get("bagimliliklar", [])]
            self._is_list.extend(yeni_gorevler)

        if self._engine:
            self._engine.tasks = self._is_list
        self._yukle_is_listesi()
        self._status_label.setText(
            f"{len(yeni_gorevler)} görev içeri aktarıldı: {os.path.basename(dosya_adi)}"
        )
        QMessageBox.information(
            self, "Başarılı",
            f"{len(yeni_gorevler)} görev içeri aktarıldı.\n"
            f"Kaynak: {os.path.basename(dosya_adi)}\n\n"
            "Görevleri inceleyip 'Hesapla (CPM)' butonuna basın."
        )

    # ── Excel içeri aktarma ─────────────────────────────────────────────
    def _aktar_excel(self, dosya_yolu: str = "") -> None:
        """Excel (.xlsx) dosyasından Gantt görevlerini içeri aktarır."""
        if not _OPENPYXL_OK:
            QMessageBox.warning(self, "Uyarı", "openpyxl paketi yüklü değil.\npip install openpyxl")
            return
        if not dosya_yolu:
            dosya_yolu, _ = QFileDialog.getOpenFileName(
                self, "Excel Dosyası Seç", "", "Excel (*.xlsx *.xls)"
            )
        if not dosya_yolu:
            return
        try:
            wb = openpyxl.load_workbook(dosya_yolu, data_only=True)
            ws = wb.active

            # Başlık satırını bul
            basliklar = [str(c.value) if c.value is not None else "" for c in ws[1]]

            # Kolon eşleme
            KOLON_MAP = {
                "ad":         ["iş adı", "ad", "görev", "task name", "name", "iş"],
                "sure":       ["süre (gün)", "süre", "gün", "duration", "day"],
                "baslangic":  ["başlangıç", "başlangıç tarihi", "start", "bas"],
                "bitis":      ["bitiş", "bitiş tarihi", "finish", "end", "bit"],
                "miktar":     ["miktar", "quantity", "qty"],
                "birim":      ["birim", "unit"],
                "kaynak":     ["kaynak/ekip", "kaynak", "ekip", "resource"],
                "oncul":      ["öncüller (id)", "öncüller", "bağımlılıklar", "oncul", "predecessors"],
                "milestone":  ["milestone (evet/hayır)", "milestone"],
                "tamamlanma": ["tamamlanma (%)", "tamamlanma", "ilerleme", "progress"],
                "butce":      ["bütçe (tl)", "bütçe", "budget"],
                "aciklama":   ["açıklama", "notlar", "description", "notes"],
            }

            indeksler = {k: self._sutun_indeksi(basliklar, v) for k, v in KOLON_MAP.items()}

            gorevler = []
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=1):
                if all(v is None for v in row):
                    continue
                satir = {}
                for alan, idx in indeksler.items():
                    satir[alan] = row[idx] if idx >= 0 and idx < len(row) else ""
                gorev = self._satiri_goreve_donustur(satir, row_idx)
                if gorev:
                    gorevler.append(gorev)

            self._gosterge_ve_yukle(gorevler, dosya_yolu)

        except Exception as exc:
            logger.error("Excel içeri aktarma hatası: %s", exc)
            QMessageBox.critical(self, "Hata", f"Excel okuma hatası:\n{exc}")

    # ── CSV içeri aktarma ──────────────────────────────────────────────
    def _aktar_csv(self, dosya_yolu: str = "") -> None:
        """CSV dosyasından Gantt görevlerini içeri aktarır."""
        import csv as _csv
        if not dosya_yolu:
            dosya_yolu, _ = QFileDialog.getOpenFileName(
                self, "CSV Dosyası Seç", "", "CSV (*.csv *.txt)"
            )
        if not dosya_yolu:
            return
        try:
            gorevler = []
            with open(dosya_yolu, "r", encoding="utf-8-sig", newline="") as f:
                reader = _csv.DictReader(f)
                basliklar = reader.fieldnames or []

                KOLON_MAP = {
                    "ad":         ["iş adı", "ad", "görev", "task name", "name"],
                    "sure":       ["süre (gün)", "süre", "gün", "duration"],
                    "baslangic":  ["başlangıç", "başlangıç tarihi", "start"],
                    "bitis":      ["bitiş", "bitiş tarihi", "finish", "end"],
                    "miktar":     ["miktar", "quantity"],
                    "birim":      ["birim", "unit"],
                    "kaynak":     ["kaynak/ekip", "kaynak", "ekip", "resource"],
                    "oncul":      ["öncüller (id)", "öncüller", "bağımlılıklar"],
                    "milestone":  ["milestone (evet/hayır)", "milestone"],
                    "tamamlanma": ["tamamlanma (%)", "tamamlanma", "ilerleme"],
                    "butce":      ["bütçe (tl)", "bütçe", "budget"],
                    "aciklama":   ["açıklama", "notlar", "description"],
                }
                # CSV'de başlık adını doğrudan kullan (DictReader key = başlık)
                for row_idx, row in enumerate(reader, start=1):
                    satir = {}
                    row_lower = {k.lower().strip(): v for k, v in row.items()}
                    for alan, adaylar in KOLON_MAP.items():
                        satir[alan] = ""
                        for aday in adaylar:
                            if aday in row_lower:
                                satir[alan] = row_lower[aday]
                                break
                    gorev = self._satiri_goreve_donustur(satir, row_idx)
                    if gorev:
                        gorevler.append(gorev)

            self._gosterge_ve_yukle(gorevler, dosya_yolu)

        except Exception as exc:
            logger.error("CSV içeri aktarma hatası: %s", exc)
            QMessageBox.critical(self, "Hata", f"CSV okuma hatası:\n{exc}")

    # ── JSON içeri aktarma ─────────────────────────────────────────────
    def _aktar_json_dosya(self, dosya_yolu: str = "") -> None:
        """JSON dosyasından Gantt görevlerini içeri aktarır (versiyon 2.0 formatı)."""
        if not dosya_yolu:
            dosya_yolu, _ = QFileDialog.getOpenFileName(
                self, "JSON Dosyası Seç", "", "JSON (*.json)"
            )
        if not dosya_yolu:
            return
        try:
            with open(dosya_yolu, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Hem {"tasks": [...]} hem de direkt [...] formatını destekle
            if isinstance(data, list):
                gorev_listesi = data
            elif isinstance(data, dict):
                gorev_listesi = data.get("tasks", data.get("gorevler", []))
            else:
                gorev_listesi = []

            # Temel doğrulama — en az "ad" alanı olmalı
            gorevler = [g for g in gorev_listesi if isinstance(g, dict) and g.get("ad")]
            self._gosterge_ve_yukle(gorevler, dosya_yolu)

        except Exception as exc:
            logger.error("JSON içeri aktarma hatası: %s", exc)
            QMessageBox.critical(self, "Hata", f"JSON okuma hatası:\n{exc}")

    # ------------------------------------------------------------------
    # Kaydet / Yükle
    # ------------------------------------------------------------------
    def kaydet_program(self) -> None:
        if not self._engine or not self._is_list:
            QMessageBox.information(self, "Bilgi", "Kaydedilecek iş programı yok.")
            return
        try:
            if hasattr(self._engine, "kaydet_sqlite"):
                self._engine.kaydet_sqlite(self._current_project_id, self._db)
                self._status_label.setText("İş programı veritabanına kaydedildi.")
            else:
                self.export_json()
        except Exception as exc:
            logger.error("Kaydet hatası: %s", exc)
            QMessageBox.critical(self, "Hata", str(exc))

    def yukle_program(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Program Yükle", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._is_list = data.get("tasks", [])
            if self._engine:
                self._engine.tasks = self._is_list
            self._yukle_is_listesi()
            self._status_label.setText(f"Program yüklendi: {path}")
        except Exception as exc:
            logger.error("Program yükleme hatası: %s", exc)
            QMessageBox.critical(self, "Hata", str(exc))

    # ------------------------------------------------------------------
    # Şablon
    # ------------------------------------------------------------------
    def goster_sablon_dialog(self) -> None:
        if _SABLON_SIHIRBAZ_OK:
            self._goster_yeni_sablon_sihirbazi()
        else:
            self._goster_eski_sablon_dialog()

    def _goster_yeni_sablon_sihirbazi(self) -> None:
        try:
            dlg = SablonSihirbazi(parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                # get_secim() → {'sablon': ProjeSablonu, 'baslangic': datetime, ...}
                secim = dlg.get_secim()
                secilen = secim.get("sablon") if isinstance(secim, dict) else secim
                if secilen and _SABLON_YON_OK:
                    yon = SablonYoneticisi()
                    if hasattr(yon, "engine_yukle"):
                        yon.engine_yukle(self._engine, secilen)
                        if hasattr(self._engine, "get_tasks"):
                            self._is_list = self._engine.get_tasks()
                        self._yukle_is_listesi()
                        ad = getattr(secilen, "tip", "") or str(secilen)
                        self._status_label.setText(f"Şablon yüklendi: {ad}")
        except Exception as exc:
            logger.error("Şablon sihirbazı hatası: %s", exc)
            self._goster_eski_sablon_dialog()

    def _goster_eski_sablon_dialog(self) -> None:
        try:
            from app.data.gantt_templates import get_template_list
            templates = get_template_list()  # List[Dict] döndürür
        except Exception:
            templates = []

        if not templates:
            QMessageBox.information(self, "Şablon", "Yüklenecek şablon bulunamadı.")
            return

        dlg = TemplateDialog(templates, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = dlg.get_selected()
            if selected:
                self._push_undo()
                new_tasks = selected.get("isler", [])
                for i, t in enumerate(new_tasks):
                    t["id"] = i + 1
                    t.setdefault("bagimliliklar", [])
                self._is_list = new_tasks
                if self._engine:
                    self._engine.tasks = self._is_list
                self._yukle_is_listesi()
                self._status_label.setText(f"Şablon yüklendi: {selected.get('ad', '')}")

    # ------------------------------------------------------------------
    # Tatil & Uyarılar
    # ------------------------------------------------------------------
    def goster_tatil_dialog(self) -> None:
        dlg = TatilDialog(self._engine, parent=self)
        dlg.exec()

    def goster_uyarilar(self) -> None:
        if not self._alerts:
            QMessageBox.information(self, "Uyarılar", "Aktif uyarı yok.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Proje Uyarıları")
        dlg.setMinimumSize(500, 380)
        layout = QVBoxLayout(dlg)
        panel = AlertsPanel()
        panel.set_alerts(self._alerts)
        layout.addWidget(panel)
        btn = QPushButton("Kapat")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()

    def guncelle_uyari_badge(self) -> None:
        count = len(self._alerts)
        self._uyari_btn.setText(f"⚠ Uyarılar [{count}]")
        if count > 0:
            self._uyari_btn.setStyleSheet(
                "QPushButton { background: #F44336; color: white; "
                "border-radius: 4px; padding: 5px 10px; font-weight: bold; }"
            )
        else:
            self._uyari_btn.setStyleSheet(
                "QPushButton { color: white; background: #1976D2; border: none;"
                " border-radius: 4px; padding: 5px 10px; }"
            )

    # ------------------------------------------------------------------
    # Drag & Drop / Undo
    # ------------------------------------------------------------------
    def toggle_drag_drop(self, checked: bool) -> None:
        self._drag_drop_enabled = checked
        if checked:
            self._drag_btn.setText("🔀 Sürükle-Bırak: AÇIK")
            self._drag_btn.setStyleSheet(
                "QPushButton { background: #388E3C; color: white; "
                "border-radius: 4px; padding: 5px; }"
            )
        else:
            self._drag_btn.setText("🔀 Sürükle-Bırak: KAPALI")
            self._drag_btn.setStyleSheet("")

    def _push_undo(self) -> None:
        self._undo_stack.append(copy.deepcopy(self._is_list))
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)

    def _undo(self) -> None:
        if not self._undo_stack:
            self._status_label.setText("Geri alınacak işlem yok.")
            return
        self._is_list = self._undo_stack.pop()
        if self._engine:
            self._engine.tasks = self._is_list
        self._yukle_is_listesi()
        self.refresh_visual_gantt()
        self._status_label.setText("Geri alındı.")

    def keyPressEvent(self, event) -> None:
        if (
            event.key() == Qt.Key.Key_Z
            and event.modifiers() == Qt.KeyboardModifier.ControlModifier
        ):
            self._undo()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Metrajdan Görev Üretimi
    # ------------------------------------------------------------------
    def _metrajdan_gorev_uret(self) -> None:
        """Aktif projenin metraj kalemlerinden otomatik Gantt görevi üret."""
        if not self._db or not self._current_project_id:
            QMessageBox.warning(
                self, "Uyarı",
                "Önce bir proje seçin ve veritabanı bağlantısını kontrol edin."
            )
            return

        try:
            kalemler = self._db.get_project_metraj(self._current_project_id)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Metraj verileri alınamadı:\n{e}")
            return

        if not kalemler:
            QMessageBox.information(
                self, "Bilgi",
                "Bu projede metraj kalemi bulunamadı.\n"
                "Önce Metraj Cetveli sekmesinden kalemler ekleyin."
            )
            return

        # Kategori → Ekip türü mapping
        KATEGORI_EKIP = {
            "beton": "Betoncu", "kalıp": "Kalıpçı (Karma)", "demir": "Demirci (Bağlama/Bükme)",
            "sıva": "Sıvacı (İç)", "boya": "Boyacı (İç)", "seramik": "Fayansçı / Seramikçi",
            "fayans": "Fayansçı / Seramikçi", "parke": "Parke / Laminat Ustası",
            "mantolama": "Yalıtımcı (Mantolama)", "duvar": "Duvarçı (Tuğla)",
        }
        # CŞB verimlilik (m²/gün veya kg/gün, 1 usta)
        VERIMLILIK = {
            "Betoncu": 8.0, "Kalıpçı (Karma)": 4.0, "Demirci (Bağlama/Bükme)": 333.0,
            "Sıvacı (İç)": 25.0, "Boyacı (İç)": 45.0, "Fayansçı / Seramikçi": 8.0,
            "Parke / Laminat Ustası": 25.0, "Yalıtımcı (Mantolama)": 12.0,
            "Duvarçı (Tuğla)": 6.0,
        }
        VARSAYILAN_USTA = 3

        self._push_undo()
        eklenen = 0
        mevcut_max_id = max((t.get("id", 0) for t in self._is_list), default=0)

        for kalem in kalemler:
            tanim = kalem.get("tanim", "") or kalem.get("poz_no", "")
            miktar = float(kalem.get("miktar", 0) or 0)
            kategori = (kalem.get("kategori", "") or "").lower()
            birim_fiyat = float(kalem.get("birim_fiyat", 0) or 0)
            butce = float(kalem.get("toplam", 0) or miktar * birim_fiyat)

            # Ekip türü belirle
            ekip = "Genel İşçi"
            for anahtar, ekip_tur in KATEGORI_EKIP.items():
                if anahtar in kategori or anahtar in tanim.lower():
                    ekip = ekip_tur
                    break

            # Süre hesapla
            verimlilik = VERIMLILIK.get(ekip, 10.0)
            if miktar > 0 and verimlilik > 0:
                sure = max(1, math.ceil(miktar / (verimlilik * VARSAYILAN_USTA)))
            else:
                sure = 5  # varsayılan

            mevcut_max_id += 1
            yeni_is = {
                "id": mevcut_max_id,
                "ad": tanim[:60] if tanim else f"Kalem {mevcut_max_id}",
                "sure": min(sure, 365),
                "miktar": miktar,
                "ekip": ekip,
                "kaynak": ekip,
                "milestone": False,
                "bagimliliklar": [],
                "bagimliliklar_detay": [],
                "tamamlanma_yuzdesi": 0,
                "butce": butce,
            }
            self._is_list.append(yeni_is)
            eklenen += 1

        self._yukle_is_listesi()
        QMessageBox.information(
            self, "Tamamlandı",
            f"✅ {eklenen} görev oluşturuldu.\n\n"
            f"Bağımlılıkları eklemek için görevi seçip 'Bağımlılık Ekle' kullanın.\n"
            f"Ardından 'Hesapla' butonu ile CPM hesaplayın."
        )
