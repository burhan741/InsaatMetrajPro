"""
Gantt Chart ve CPM UI
İş programı, kritik yol analizi ve zaman yönetimi arayüzü

Yeni Özellikler:
- Görsel Gantt Chart (çubuk grafik)
- Resmi tatil yönetimi
- Baseline karşılaştırma
- WBS hiyerarşisi
- Kaynak çakışma kontrolü
- PDF/Excel export
"""

from PyQt6.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
 QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
 QLineEdit, QComboBox, QDateEdit, QTextEdit, QMessageBox,
 QHeaderView, QDoubleSpinBox, QTabWidget, QProgressBar,
 QSpinBox, QCheckBox, QScrollArea, QFrame, QDialog,
 QDialogButtonBox, QListWidget, QListWidgetItem, QSplitter,
 QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
 QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsPathItem,
 QFileDialog, QColorDialog, QTreeWidget, QTreeWidgetItem,
 QCalendarWidget, QMenu, QToolButton, QGridLayout
)
from PyQt6.QtCore import Qt, QDate, QTimer, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QBrush, QPen, QPainter, QLinearGradient, QPainterPath
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import logging
import os

from app.core.database import DatabaseManager
from app.core.gantt_engine import GanttEngine, Task

logger = logging.getLogger(__name__)


# ==================== GÖRSEL GANTT CHART ====================

class DraggableTaskBar(QGraphicsRectItem):
 """Sürüklenebilir görev çubuğu"""

 def __init__(self, x, y, width, height, task_id, gantt_view):
 super().__init__(x, y, width, height)
 self.task_id = task_id
 self.gantt_view = gantt_view
 self.original_x = x
 self.original_y = y # FIX: mouseMoveEvent'te her zaman erişilebilir
 self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
 self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
 self.setCursor(Qt.CursorShape.OpenHandCursor)

 def mousePressEvent(self, event):
 self.setCursor(Qt.CursorShape.ClosedHandCursor)
 self.original_x = self.x()
 super().mousePressEvent(event)

 def mouseMoveEvent(self, event):
 # Sadece yatay hareket: Y koordinatı sabit tutulur
 super().mouseMoveEvent(event)
 current_pos = self.pos()
 self.setPos(current_pos.x(), 0) # Y offset sıfır, __init__'teki y scene koordinatıyla sabit

 def mouseReleaseEvent(self, event):
 self.setCursor(Qt.CursorShape.OpenHandCursor)
 new_x = self.x()

 # Hareket varsa
 if abs(new_x - self.original_x) > 5:
 # Yeni tarihi hesapla
 gun_farki = int((new_x - self.original_x) / self.gantt_view.day_width)

 if gun_farki != 0 and self.gantt_view.on_task_moved:
 self.gantt_view.on_task_moved(self.task_id, gun_farki)

 super().mouseReleaseEvent(event)


class GanttChartView(QGraphicsView):
 """Görsel Gantt Chart widget'ı"""

 # Signal for task moved
 taskMoved = pyqtSignal(int, int) # task_id, gun_farki

 def __init__(self, parent=None):
 super().__init__(parent)
 self.scene = QGraphicsScene()
 self.setScene(self.scene)
 self.setRenderHint(QPainter.RenderHint.Antialiasing)
 self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
 self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

 # Ayarlar
 self.row_height = 30
 self.day_width = 25
 self.header_height = 60
 self.task_name_width = 200
 self.show_baseline = True
 self.show_progress = True
 self.show_critical = True

 # Drag & Drop
 self.drag_enabled = True
 self.on_task_moved = None # Callback function
 self.task_bars = {} # task_id -> DraggableTaskBar

 def draw_gantt(self, data: Dict[str, Any]):
 """Gantt chart'ı çiz"""
 self.scene.clear()

 if 'error' in data:
 return

 cubuklar = data.get('cubuklar', [])
 gunler = data.get('gunler', [])
 aylar = data.get('aylar', [])
 tatil_gunleri = data.get('tatil_gunleri', [])

 if not cubuklar or not gunler:
 return

 toplam_gun = len(gunler)
 toplam_gorev = len(cubuklar)

 # Canvas boyutu
 canvas_width = self.task_name_width + (toplam_gun * self.day_width) + 50
 canvas_height = self.header_height + (toplam_gorev * self.row_height) + 50

 # Arka plan
 self.scene.setSceneRect(0, 0, canvas_width, canvas_height)

 # Ay başlıkları
 self._draw_month_headers(aylar, toplam_gun)

 # Gün çizgileri ve tatiller
 self._draw_day_grid(gunler, tatil_gunleri, toplam_gorev)

 # Görev çubukları
 self._draw_task_bars(cubuklar, data.get('baseline_var', False))

 # Bugün çizgisi
 self._draw_today_line(data.get('proje_baslangic'), toplam_gorev)

 def _draw_month_headers(self, aylar: List, toplam_gun: int):
 """Ay başlıklarını çiz"""
 for i, ay in enumerate(aylar):
 x = self.task_name_width + (ay['baslangic_index'] * self.day_width)

 # Sonraki ay'ın başlangıcına kadar genişlik
 if i + 1 < len(aylar):
 width = (aylar[i + 1]['baslangic_index'] - ay['baslangic_index']) * self.day_width
 else:
 width = (toplam_gun - ay['baslangic_index']) * self.day_width

 # Ay kutusu
 rect = QGraphicsRectItem(x, 0, width, 30)
 rect.setBrush(QBrush(QColor("#34495e")))
 rect.setPen(QPen(QColor("#2c3e50")))
 self.scene.addItem(rect)

 # Ay adı
 text = QGraphicsTextItem(ay['ad'])
 text.setDefaultTextColor(QColor("white"))
 text.setFont(QFont("Arial", 9, QFont.Weight.Bold))
 text.setPos(x + 5, 5)
 self.scene.addItem(text)

 def _draw_day_grid(self, gunler: List, tatil_gunleri: List, toplam_gorev: int):
 """Gün çizgilerini ve tatilleri çiz"""
 tatil_indeksleri = {t['index'] for t in tatil_gunleri}

 for i, gun in enumerate(gunler):
 x = self.task_name_width + (i * self.day_width)

 # Tatil arkaplanı
 if i in tatil_indeksleri:
 rect = QGraphicsRectItem(x, self.header_height, self.day_width,
 toplam_gorev * self.row_height)
 rect.setBrush(QBrush(QColor("#ffebee"))) # Açık kırmızı
 rect.setPen(QPen(Qt.PenStyle.NoPen))
 self.scene.addItem(rect)

 # Hafta sonu arkaplanı
 elif gun.weekday() >= 5:
 rect = QGraphicsRectItem(x, self.header_height, self.day_width,
 toplam_gorev * self.row_height)
 rect.setBrush(QBrush(QColor("#f5f5f5"))) # Açık gri
 rect.setPen(QPen(Qt.PenStyle.NoPen))
 self.scene.addItem(rect)

 # Dikey çizgi
 line_color = "#ddd" if gun.weekday() == 0 else "#eee"
 pen = QPen(QColor(line_color))
 self.scene.addLine(x, self.header_height, x,
 self.header_height + toplam_gorev * self.row_height, pen)

 # Gün numarası (sadece Pazartesi)
 if gun.weekday() == 0:
 text = QGraphicsTextItem(str(gun.day))
 text.setDefaultTextColor(QColor("#666"))
 text.setFont(QFont("Arial", 7))
 text.setPos(x + 2, 35)
 self.scene.addItem(text)

 def _draw_task_bars(self, cubuklar: List, baseline_var: bool):
 """Görev çubuklarını çiz"""
 self.task_bars.clear()

 for row, cubuk in enumerate(cubuklar):
 y = self.header_height + (row * self.row_height) + 5

 # Görev adı (solda)
 indent = " " * cubuk.get('seviye', 0)
 ad = f"{indent}{cubuk.get('wbs_kodu', '')} {cubuk['ad']}"
 if len(ad) > 25:
 ad = ad[:22] + "..."

 text = QGraphicsTextItem(ad)
 text.setDefaultTextColor(QColor("#2c3e50"))
 text.setFont(QFont("Arial", 8))
 text.setPos(5, y)
 self.scene.addItem(text)

 # Çubuk pozisyonu
 x = self.task_name_width + (cubuk['baslangic_index'] * self.day_width)
 width = cubuk['uzunluk'] * self.day_width
 bar_height = self.row_height - 12
 task_id = cubuk.get('task_id')

 # Baseline çubuğu (varsa ve açıksa)
 if baseline_var and self.show_baseline and cubuk.get('baseline_baslangic_index') is not None:
 baseline_x = self.task_name_width + (cubuk['baseline_baslangic_index'] * self.day_width)
 baseline_width = (cubuk['baseline_bitis_index'] - cubuk['baseline_baslangic_index'] + 1) * self.day_width

 baseline_rect = QGraphicsRectItem(baseline_x, y + bar_height - 4, baseline_width, 4)
 baseline_rect.setBrush(QBrush(QColor("#bdc3c7")))
 baseline_rect.setPen(QPen(Qt.PenStyle.NoPen))
 self.scene.addItem(baseline_rect)

 # Milestone ise elmas şekli (büyük ve belirgin)
 if cubuk.get('milestone'):
 # Elmas çiz (QPainterPath ile daha iyi görünüm)
 diamond_size = 14
 diamond_path = QPainterPath()
 cx = x + 5 # merkez x
 cy = y + bar_height / 2 # merkez y
 diamond_path.moveTo(cx, cy - diamond_size/2) # üst
 diamond_path.lineTo(cx + diamond_size/2, cy) # sağ
 diamond_path.lineTo(cx, cy + diamond_size/2) # alt
 diamond_path.lineTo(cx - diamond_size/2, cy) # sol
 diamond_path.closeSubpath()

 diamond = QGraphicsPathItem(diamond_path)
 gradient = QLinearGradient(cx, cy - diamond_size/2, cx, cy + diamond_size/2)
 gradient.setColorAt(0, QColor("#9b59b6").lighter(130))
 gradient.setColorAt(1, QColor("#9b59b6"))
 diamond.setBrush(QBrush(gradient))
 diamond.setPen(QPen(QColor("#6c3483"), 2))
 diamond.setToolTip(f"Milestone: {cubuk['ad']}")
 self.scene.addItem(diamond)

 # Milestone adı (sağında)
 ms_text = QGraphicsTextItem(cubuk['ad'][:20])
 ms_text.setDefaultTextColor(QColor("#6c3483"))
 ms_text.setFont(QFont("Arial", 8, QFont.Weight.Bold))
 ms_text.setPos(cx + diamond_size/2 + 3, cy - 8)
 self.scene.addItem(ms_text)
 else:
 # Drag & Drop etkinse sürüklenebilir çubuk kullan
 if self.drag_enabled and task_id and not cubuk.get('kritik'):
 rect = DraggableTaskBar(x, y, width, bar_height, task_id, self)
 rect.original_y = y
 else:
 rect = QGraphicsRectItem(x, y, width, bar_height)

 # Gradient dolgu
 gradient = QLinearGradient(x, y, x, y + bar_height)
 base_color = QColor(cubuk['renk'])
 gradient.setColorAt(0, base_color.lighter(120))
 gradient.setColorAt(1, base_color)
 rect.setBrush(QBrush(gradient))

 # Kritik çubuk için kalın kenar
 if cubuk.get('kritik') and self.show_critical:
 rect.setPen(QPen(QColor("#c0392b"), 2))
 else:
 rect.setPen(QPen(base_color.darker(120), 1))

 # Tooltip ekle
 if task_id:
 tooltip = f"{cubuk['ad']}\nBaşlangıç: {cubuk.get('baslangic_index', 0)}. gün\nSüre: {cubuk.get('uzunluk', 0)} gün"
 if cubuk.get('float_gun', 0) > 0:
 tooltip += f"\nFloat: {cubuk['float_gun']} gün"
 rect.setToolTip(tooltip)

 self.scene.addItem(rect)

 # Task bar'ı kaydet
 if task_id:
 self.task_bars[task_id] = rect

 # İlerleme çubuğu
 if self.show_progress and cubuk.get('ilerleme', 0) > 0:
 progress_width = width * (cubuk['ilerleme'] / 100)
 progress_rect = QGraphicsRectItem(x, y + bar_height - 6, progress_width, 4)
 progress_rect.setBrush(QBrush(QColor("#2ecc71")))
 progress_rect.setPen(QPen(Qt.PenStyle.NoPen))
 self.scene.addItem(progress_rect)

 # Float göstergesi (kritik değilse)
 if not cubuk.get('kritik') and cubuk.get('float_gun', 0) > 0:
 float_x = x + width
 float_width = cubuk['float_gun'] * self.day_width
 float_rect = QGraphicsRectItem(float_x, y + 8, float_width, bar_height - 16)
 float_rect.setBrush(QBrush(QColor(200, 200, 200, 100)))
 float_rect.setPen(QPen(QColor("#bdc3c7"), 1, Qt.PenStyle.DashLine))
 self.scene.addItem(float_rect)

 def _draw_today_line(self, proje_baslangic: datetime, toplam_gorev: int):
 """Bugün çizgisini çiz"""
 if not proje_baslangic:
 return

 bugun = datetime.now()
 if bugun < proje_baslangic:
 return

 gun_farki = (bugun - proje_baslangic).days
 x = self.task_name_width + (gun_farki * self.day_width)

 # Dikey kırmızı çizgi
 pen = QPen(QColor("#e74c3c"), 2)
 self.scene.addLine(x, 0, x, self.header_height + toplam_gorev * self.row_height, pen)

 # "Bugün" etiketi
 text = QGraphicsTextItem("Bugün")
 text.setDefaultTextColor(QColor("#e74c3c"))
 text.setFont(QFont("Arial", 8, QFont.Weight.Bold))
 text.setPos(x + 2, 45)
 self.scene.addItem(text)

 def zoom_in(self):
 """Yakınlaştır"""
 self.day_width = min(50, self.day_width + 5)
 self.row_height = min(50, self.row_height + 3)

 def zoom_out(self):
 """Uzaklaştır"""
 self.day_width = max(10, self.day_width - 5)
 self.row_height = max(20, self.row_height - 3)

 def set_zoom_preset(self, preset: str):
 """Zoom preset ayarla (Haftalık/Aylık/Yıllık)"""
 presets = {
 'weekly': {'day_width': 40, 'row_height': 35}, # Haftalık - detaylı
 'monthly': {'day_width': 20, 'row_height': 28}, # Aylık - orta
 'quarterly': {'day_width': 8, 'row_height': 22}, # Çeyreklik - geniş
 'yearly': {'day_width': 4, 'row_height': 18}, # Yıllık - çok geniş
 }
 if preset in presets:
 self.day_width = presets[preset]['day_width']
 self.row_height = presets[preset]['row_height']


# ==================== S-CURVE WİDGET ====================

class SCurveWidget(QGraphicsView):
 """S-Curve (S Eğrisi) görselleştirme widget'ı"""

 def __init__(self, parent=None):
 super().__init__(parent)
 self.scene = QGraphicsScene()
 self.setScene(self.scene)
 self.setRenderHint(QPainter.RenderHint.Antialiasing)
 self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
 self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

 # Grafik ayarları
 self.margin_left = 60
 self.margin_right = 30
 self.margin_top = 30
 self.margin_bottom = 50
 self.chart_width = 700
 self.chart_height = 400

 def draw_s_curve(self, data: Dict[str, Any]):
 """S-Curve grafiğini çiz"""
 self.scene.clear()

 if 'error' in data:
 text = QGraphicsTextItem(f"Hata: {data['error']}")
 text.setPos(50, 50)
 self.scene.addItem(text)
 return

 tarihler = data.get('tarihler', [])
 planlanan = data.get('planlanan', [])
 gerceklesen = data.get('gerceklesen', [])

 if not tarihler or not planlanan:
 return

 # Canvas boyutu
 total_width = self.margin_left + self.chart_width + self.margin_right
 total_height = self.margin_top + self.chart_height + self.margin_bottom
 self.scene.setSceneRect(0, 0, total_width, total_height)

 # Arka plan
 bg = QGraphicsRectItem(0, 0, total_width, total_height)
 bg.setBrush(QBrush(QColor("white")))
 bg.setPen(QPen(Qt.PenStyle.NoPen))
 self.scene.addItem(bg)

 # Grafik alanı
 chart_rect = QGraphicsRectItem(
 self.margin_left, self.margin_top,
 self.chart_width, self.chart_height
 )
 chart_rect.setBrush(QBrush(QColor("#f9f9f9")))
 chart_rect.setPen(QPen(QColor("#ddd")))
 self.scene.addItem(chart_rect)

 # Y ekseni çizgileri ve etiketleri (0%, 25%, 50%, 75%, 100%)
 for i in range(5):
 y_val = i * 25
 y_pos = self.margin_top + self.chart_height - (y_val / 100 * self.chart_height)

 # Yatay çizgi
 line = QGraphicsLineItem(
 self.margin_left, y_pos,
 self.margin_left + self.chart_width, y_pos
 )
 line.setPen(QPen(QColor("#e0e0e0"), 1, Qt.PenStyle.DotLine))
 self.scene.addItem(line)

 # Etiket
 label = QGraphicsTextItem(f"{y_val}%")
 label.setDefaultTextColor(QColor("#666"))
 label.setFont(QFont("Arial", 8))
 label.setPos(self.margin_left - 35, y_pos - 8)
 self.scene.addItem(label)

 # X ekseni etiketleri (ay bazlı)
 if len(tarihler) > 10:
 ay_sayisi = len(tarihler) // 30 + 1
 step = len(tarihler) // min(10, ay_sayisi)
 else:
 step = 1

 for i in range(0, len(tarihler), max(1, step)):
 x_pos = self.margin_left + (i / len(tarihler) * self.chart_width)
 tarih = tarihler[i]

 label = QGraphicsTextItem(tarih.strftime("%d.%m"))
 label.setDefaultTextColor(QColor("#666"))
 label.setFont(QFont("Arial", 7))
 label.setPos(x_pos - 15, self.margin_top + self.chart_height + 5)
 self.scene.addItem(label)

 # Planlanan eğri (Mavi)
 self._draw_curve(tarihler, planlanan, QColor("#3498db"), "Planlanan")

 # Gerçekleşen eğri (Yeşil)
 gercek_values = [v for v in gerceklesen if v is not None]
 if gercek_values:
 self._draw_curve(tarihler[:len(gercek_values)], gercek_values, QColor("#27ae60"), "Gerçekleşen")

 # Bugün çizgisi
 bugun = data.get('bugun')
 proje_baslangic = data.get('proje_baslangic')
 if bugun and proje_baslangic and tarihler:
 bugun_index = min((bugun - proje_baslangic).days, len(tarihler) - 1)
 if 0 <= bugun_index < len(tarihler):
 x_pos = self.margin_left + (bugun_index / len(tarihler) * self.chart_width)
 line = QGraphicsLineItem(
 x_pos, self.margin_top,
 x_pos, self.margin_top + self.chart_height
 )
 line.setPen(QPen(QColor("#e74c3c"), 2, Qt.PenStyle.DashLine))
 self.scene.addItem(line)

 label = QGraphicsTextItem("Bugün")
 label.setDefaultTextColor(QColor("#e74c3c"))
 label.setFont(QFont("Arial", 8, QFont.Weight.Bold))
 label.setPos(x_pos + 5, self.margin_top + 5)
 self.scene.addItem(label)

 # Lejant
 self._draw_legend()

 def _draw_curve(self, tarihler: List, values: List, color: QColor, label: str):
 """Eğri çiz"""
 if len(tarihler) < 2 or len(values) < 2:
 return

 path = QPainterPath()
 first_point = True

 for i, (tarih, val) in enumerate(zip(tarihler, values)):
 if val is None:
 continue

 x = self.margin_left + (i / len(tarihler) * self.chart_width)
 y = self.margin_top + self.chart_height - (val / 100 * self.chart_height)

 if first_point:
 path.moveTo(x, y)
 first_point = False
 else:
 path.lineTo(x, y)

 path_item = QGraphicsPathItem(path)
 path_item.setPen(QPen(color, 2.5))
 self.scene.addItem(path_item)

 def _draw_legend(self):
 """Lejant çiz"""
 legend_x = self.margin_left + self.chart_width - 150
 legend_y = self.margin_top + 10

 # Arka plan
 legend_bg = QGraphicsRectItem(legend_x - 5, legend_y - 5, 140, 50)
 legend_bg.setBrush(QBrush(QColor(255, 255, 255, 220)))
 legend_bg.setPen(QPen(QColor("#ccc")))
 self.scene.addItem(legend_bg)

 # Planlanan
 line1 = QGraphicsLineItem(legend_x, legend_y + 8, legend_x + 20, legend_y + 8)
 line1.setPen(QPen(QColor("#3498db"), 2.5))
 self.scene.addItem(line1)

 text1 = QGraphicsTextItem("Planlanan")
 text1.setDefaultTextColor(QColor("#333"))
 text1.setFont(QFont("Arial", 9))
 text1.setPos(legend_x + 25, legend_y)
 self.scene.addItem(text1)

 # Gerçekleşen
 line2 = QGraphicsLineItem(legend_x, legend_y + 28, legend_x + 20, legend_y + 28)
 line2.setPen(QPen(QColor("#27ae60"), 2.5))
 self.scene.addItem(line2)

 text2 = QGraphicsTextItem("Gerçekleşen")
 text2.setDefaultTextColor(QColor("#333"))
 text2.setFont(QFont("Arial", 9))
 text2.setPos(legend_x + 25, legend_y + 20)
 self.scene.addItem(text2)


# ==================== ŞABLON SEÇİM DİALOG ====================

class TemplateDialog(QDialog):
 """Görev şablonu seçim dialog'u"""

 def __init__(self, parent=None):
 super().__init__(parent)
 self.setWindowTitle("Görev Şablonu Ekle")
 self.setModal(True)
 self.resize(600, 500)
 self.selected_template_id = None
 self.init_ui()

 def init_ui(self):
 layout = QVBoxLayout()

 # Başlık
 baslik = QLabel("Hazır İş Paketi Şablonları")
 baslik.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2c3e50;")
 layout.addWidget(baslik)

 aciklama = QLabel("Aşağıdaki şablonlardan birini seçerek hazır görev seti ekleyebilirsiniz.")
 aciklama.setWordWrap(True)
 aciklama.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
 layout.addWidget(aciklama)

 # Şablon listesi
 self.template_list = QListWidget()
 self.template_list.setStyleSheet("""
 QListWidget {
 border: 1px solid #ddd;
 border-radius: 5px;
 background-color: white;
 }
 QListWidget::item {
 padding: 10px;
 border-bottom: 1px solid #eee;
 }
 QListWidget::item:selected {
 background-color: #3498db;
 color: white;
 }
 QListWidget::item:hover {
 background-color: #ecf0f1;
 }
 """)
 self.template_list.itemClicked.connect(self.on_template_selected)
 self.template_list.itemDoubleClicked.connect(self.accept)
 layout.addWidget(self.template_list)

 # Şablonları yükle
 self._load_templates()

 # Başlangıç tarihi
 tarih_layout = QHBoxLayout()
 tarih_layout.addWidget(QLabel("Başlangıç Tarihi:"))
 self.baslangic_date = QDateEdit()
 self.baslangic_date.setDate(QDate.currentDate())
 self.baslangic_date.setCalendarPopup(True)
 self.baslangic_date.setDisplayFormat("dd-MM-yyyy")
 tarih_layout.addWidget(self.baslangic_date)
 tarih_layout.addStretch()
 layout.addLayout(tarih_layout)

 # Seçili şablon bilgisi
 self.info_group = QGroupBox("Şablon Detayları")
 info_layout = QVBoxLayout()
 self.info_label = QLabel("Bir şablon seçin...")
 self.info_label.setWordWrap(True)
 info_layout.addWidget(self.info_label)
 self.info_group.setLayout(info_layout)
 layout.addWidget(self.info_group)

 # Butonlar
 buttons = QDialogButtonBox(
 QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
 )
 buttons.accepted.connect(self.accept)
 buttons.rejected.connect(self.reject)
 layout.addWidget(buttons)

 self.setLayout(layout)

 def _load_templates(self):
 """Şablonları yükle"""
 try:
 from app.data.gantt_templates import get_template_list
 templates = get_template_list()

 for tmpl in templates:
 item = QListWidgetItem()
 item.setText(f"{tmpl['ad']} ({tmpl['gorev_sayisi']} görev)")
 item.setData(Qt.ItemDataRole.UserRole, tmpl['id'])
 item.setToolTip(tmpl['aciklama'])

 # Renk göstergesi
 self.template_list.addItem(item)

 except ImportError:
 item = QListWidgetItem("Şablon modülü yüklenemedi")
 self.template_list.addItem(item)

 def on_template_selected(self, item):
 """Şablon seçildiğinde"""
 self.selected_template_id = item.data(Qt.ItemDataRole.UserRole)

 try:
 from app.data.gantt_templates import get_template
 template = get_template(self.selected_template_id)

 if template:
 gorevler = template.get('gorevler', [])
 toplam_sure = sum(g['sure'] for g in gorevler)
 info_text = f"""
<b>{template['ad']}</b><br>
<b>Kategori:</b> {template['kategori']}<br>
<b>Açıklama:</b> {template['aciklama']}<br>
<b>Görev Sayısı:</b> {len(gorevler)}<br>
<b>Toplam Süre:</b> ~{toplam_sure} iş günü
 """
 self.info_label.setText(info_text)
 except Exception as e:
 self.info_label.setText(f"Hata: {e}")

 def get_selected_template(self) -> Optional[str]:
 """Seçilen şablon ID'sini döndür"""
 return self.selected_template_id

 def get_start_date(self) -> datetime:
 """Başlangıç tarihini döndür"""
 qdate = self.baslangic_date.date()
 return datetime(qdate.year(), qdate.month(), qdate.day())


# ==================== WHAT-IF ANALİZ DİALOG ====================

class WhatIfResultDialog(QDialog):
 """What-If analiz sonuç dialog'u"""

 def __init__(self, parent=None, sonuc: Dict[str, Any] = None):
 super().__init__(parent)
 self.sonuc = sonuc or {}
 self.setWindowTitle("What-If Analiz Sonucu")
 self.setModal(True)
 self.resize(700, 500)
 self.init_ui()

 def init_ui(self):
 layout = QVBoxLayout()

 # Başlık
 baslik = QLabel(f" Senaryo: {self.sonuc.get('geciktirilen_gorev', '-')} - {self.sonuc.get('gecikme_gun', 0)} Gün Gecikme")
 baslik.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2c3e50;")
 layout.addWidget(baslik)

 # Özet kartlar
 kart_layout = QHBoxLayout()

 # Proje gecikme
 proje_gecikme = self.sonuc.get('proje_gecikme_gun', 0)
 gecikme_renk = '#e74c3c' if proje_gecikme > 0 else '#27ae60'
 kart_layout.addWidget(self._create_card(
 " Proje Gecikmesi",
 f"{proje_gecikme} gün",
 gecikme_renk
 ))

 # Etkilenen görev
 etkilenen = self.sonuc.get('etkilenen_gorev_sayisi', 0)
 kart_layout.addWidget(self._create_card(
 " Etkilenen Görev",
 str(etkilenen),
 '#e67e22'
 ))

 # Kritik yol
 kritik_degisti = self.sonuc.get('kritik_yol_degisti', False)
 kritik_text = "Değişti" if kritik_degisti else "Aynı"
 kritik_renk = '#e74c3c' if kritik_degisti else '#27ae60'
 kart_layout.addWidget(self._create_card(
 " Kritik Yol",
 kritik_text,
 kritik_renk
 ))

 layout.addLayout(kart_layout)

 # Tarih bilgileri
 tarih_group = QGroupBox(" Proje Tarihleri")
 tarih_layout = QFormLayout()
 tarih_layout.addRow("Eski Bitiş:", QLabel(self.sonuc.get('eski_proje_bitis', '-')))
 tarih_layout.addRow("Yeni Bitiş:", QLabel(f"<b style='color: {gecikme_renk}'>{self.sonuc.get('yeni_proje_bitis', '-')}</b>"))
 tarih_group.setLayout(tarih_layout)
 layout.addWidget(tarih_group)

 # Etkilenen görevler tablosu
 tablo_group = QGroupBox(" Etkilenen Görevler")
 tablo_layout = QVBoxLayout()

 self.etkilenen_table = QTableWidget()
 self.etkilenen_table.setColumnCount(5)
 self.etkilenen_table.setHorizontalHeaderLabels([
 "Görev", "Eski Başlangıç", "Yeni Başlangıç", "Eski Bitiş", "Yeni Bitiş"
 ])
 self.etkilenen_table.horizontalHeader().setStretchLastSection(True)

 for gorev in self.sonuc.get('etkilenen_gorevler', []):
 row = self.etkilenen_table.rowCount()
 self.etkilenen_table.insertRow(row)
 self.etkilenen_table.setItem(row, 0, QTableWidgetItem(gorev['ad']))
 self.etkilenen_table.setItem(row, 1, QTableWidgetItem(gorev['eski_baslangic']))
 self.etkilenen_table.setItem(row, 2, QTableWidgetItem(gorev['yeni_baslangic']))
 self.etkilenen_table.setItem(row, 3, QTableWidgetItem(gorev['eski_bitis']))
 self.etkilenen_table.setItem(row, 4, QTableWidgetItem(gorev['yeni_bitis']))

 tablo_layout.addWidget(self.etkilenen_table)
 tablo_group.setLayout(tablo_layout)
 layout.addWidget(tablo_group)

 # Butonlar
 btn_layout = QHBoxLayout()
 btn_layout.addStretch()

 kapat_btn = QPushButton("Kapat")
 kapat_btn.clicked.connect(self.reject)
 btn_layout.addWidget(kapat_btn)

 layout.addLayout(btn_layout)
 self.setLayout(layout)

 def _create_card(self, baslik: str, deger: str, renk: str) -> QFrame:
 """Mini kart oluştur"""
 card = QFrame()
 card.setFixedHeight(80)
 card.setStyleSheet(f"""
 QFrame {{
 background-color: {renk};
 border-radius: 8px;
 padding: 10px;
 }}
 """)

 layout = QVBoxLayout()

 baslik_label = QLabel(baslik)
 baslik_label.setStyleSheet("color: white; font-size: 10pt;")
 baslik_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
 layout.addWidget(baslik_label)

 deger_label = QLabel(deger)
 deger_label.setStyleSheet("color: white; font-size: 16pt; font-weight: bold;")
 deger_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
 layout.addWidget(deger_label)

 card.setLayout(layout)
 return card


# ==================== UYARILAR PANELİ ====================

class AlertsPanel(QDialog):
 """Uyarılar/Bildirimler paneli"""

 def __init__(self, parent=None, alerts: List[Dict] = None):
 super().__init__(parent)
 self.alerts = alerts or []
 self.setWindowTitle(" Uyarılar ve Bildirimler")
 self.setModal(False) # Modal olmayan
 self.resize(500, 400)
 self.init_ui()

 def init_ui(self):
 layout = QVBoxLayout()

 # Özet
 ozet_layout = QHBoxLayout()

 kritik = sum(1 for a in self.alerts if a['tip'] == 'KRITIK')
 uyari = sum(1 for a in self.alerts if a['tip'] == 'UYARI')
 bilgi = sum(1 for a in self.alerts if a['tip'] == 'BILGI')
 kaynak = sum(1 for a in self.alerts if a['tip'] == 'KAYNAK')

 if kritik > 0:
 ozet_layout.addWidget(QLabel(f" {kritik} Kritik"))
 if uyari > 0:
 ozet_layout.addWidget(QLabel(f" {uyari} Uyarı"))
 if bilgi > 0:
 ozet_layout.addWidget(QLabel(f" {bilgi} Bilgi"))
 if kaynak > 0:
 ozet_layout.addWidget(QLabel(f" {kaynak} Kaynak"))

 ozet_layout.addStretch()
 layout.addLayout(ozet_layout)

 # Uyarı listesi
 scroll = QScrollArea()
 scroll.setWidgetResizable(True)

 container = QWidget()
 container_layout = QVBoxLayout()

 for alert in self.alerts:
 alert_widget = self._create_alert_widget(alert)
 container_layout.addWidget(alert_widget)

 container_layout.addStretch()
 container.setLayout(container_layout)
 scroll.setWidget(container)

 layout.addWidget(scroll)

 # Kapat butonu
 kapat_btn = QPushButton("Kapat")
 kapat_btn.clicked.connect(self.close)
 layout.addWidget(kapat_btn)

 self.setLayout(layout)

 def _create_alert_widget(self, alert: Dict) -> QFrame:
 """Tek bir uyarı widget'ı oluştur"""
 frame = QFrame()
 frame.setStyleSheet(f"""
 QFrame {{
 background-color: white;
 border-left: 4px solid {alert['renk']};
 border-radius: 5px;
 padding: 10px;
 margin: 5px 0;
 }}
 """)

 layout = QVBoxLayout()

 # Başlık
 baslik_layout = QHBoxLayout()
 icon = QLabel(alert['icon'])
 icon.setStyleSheet("font-size: 16pt;")
 baslik_layout.addWidget(icon)

 baslik = QLabel(alert['baslik'])
 baslik.setStyleSheet("font-weight: bold; font-size: 11pt;")
 baslik_layout.addWidget(baslik)
 baslik_layout.addStretch()

 tip = QLabel(alert['tip'])
 tip.setStyleSheet(f"color: {alert['renk']}; font-size: 9pt;")
 baslik_layout.addWidget(tip)

 layout.addLayout(baslik_layout)

 # Açıklama
 aciklama = QLabel(alert['aciklama'])
 aciklama.setStyleSheet("color: #666; font-size: 10pt;")
 aciklama.setWordWrap(True)
 layout.addWidget(aciklama)

 frame.setLayout(layout)
 return frame


# ==================== TATİL YÖNETİMİ DİALOG ====================

class TatilDialog(QDialog):
 """Tatil yönetimi dialog'u"""

 def __init__(self, parent=None, tatil_yoneticisi=None):
 super().__init__(parent)
 self.tatil_yoneticisi = tatil_yoneticisi
 self.setWindowTitle("Tatil Yönetimi")
 self.setModal(True)
 self.resize(600, 500)
 self.init_ui()
 self.yukle_tatiller()

 def init_ui(self):
 layout = QVBoxLayout()

 # Ayarlar
 ayarlar_group = QGroupBox("Çalışma Ayarları")
 ayarlar_layout = QFormLayout()

 self.cumartesi_check = QCheckBox("Cumartesi çalışılsın")
 self.cumartesi_check.stateChanged.connect(self.on_cumartesi_changed)
 ayarlar_layout.addRow("Hafta sonu:", self.cumartesi_check)

 ayarlar_group.setLayout(ayarlar_layout)
 layout.addWidget(ayarlar_group)

 # Resmi tatiller listesi
 resmi_group = QGroupBox("Resmi Tatiller (Yıl Bazlı)")
 resmi_layout = QVBoxLayout()

 self.yil_combo = QComboBox()
 for yil in range(2024, 2031):
 self.yil_combo.addItem(str(yil), yil)
 self.yil_combo.setCurrentText(str(datetime.now().year))
 self.yil_combo.currentIndexChanged.connect(self.yukle_tatiller)
 resmi_layout.addWidget(self.yil_combo)

 self.resmi_table = QTableWidget()
 self.resmi_table.setColumnCount(3)
 self.resmi_table.setHorizontalHeaderLabels(["Tarih", "Gün", "Açıklama"])
 self.resmi_table.horizontalHeader().setStretchLastSection(True)
 resmi_layout.addWidget(self.resmi_table)

 resmi_group.setLayout(resmi_layout)
 layout.addWidget(resmi_group)

 # Özel tatil ekleme
 ozel_group = QGroupBox("Özel Tatil Ekle")
 ozel_layout = QHBoxLayout()

 self.ozel_tarih = QDateEdit()
 self.ozel_tarih.setDate(QDate.currentDate())
 self.ozel_tarih.setCalendarPopup(True)
 ozel_layout.addWidget(QLabel("Tarih:"))
 ozel_layout.addWidget(self.ozel_tarih)

 self.ozel_aciklama = QLineEdit()
 self.ozel_aciklama.setPlaceholderText("Tatil açıklaması")
 ozel_layout.addWidget(QLabel("Açıklama:"))
 ozel_layout.addWidget(self.ozel_aciklama)

 ekle_btn = QPushButton(" Ekle")
 ekle_btn.clicked.connect(self.ekle_ozel_tatil)
 ozel_layout.addWidget(ekle_btn)

 ozel_group.setLayout(ozel_layout)
 layout.addWidget(ozel_group)

 # Özel tatiller listesi
 self.ozel_table = QTableWidget()
 self.ozel_table.setColumnCount(3)
 self.ozel_table.setHorizontalHeaderLabels(["Tarih", "Açıklama", "Sil"])
 self.ozel_table.horizontalHeader().setStretchLastSection(True)
 layout.addWidget(self.ozel_table)

 # Butonlar
 buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
 buttons.accepted.connect(self.accept)
 layout.addWidget(buttons)

 self.setLayout(layout)

 def yukle_tatiller(self):
 """Resmi tatilleri yükle"""
 if not self.tatil_yoneticisi:
 return

 yil = self.yil_combo.currentData()
 tatiller = self.tatil_yoneticisi.get_yil_tatilleri(yil)

 self.resmi_table.setRowCount(0)

 gun_isimleri = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']

 for tarih, aciklama in tatiller:
 row = self.resmi_table.rowCount()
 self.resmi_table.insertRow(row)

 self.resmi_table.setItem(row, 0, QTableWidgetItem(tarih.strftime('%d.%m.%Y')))
 self.resmi_table.setItem(row, 1, QTableWidgetItem(gun_isimleri[tarih.weekday()]))
 self.resmi_table.setItem(row, 2, QTableWidgetItem(aciklama))

 # Özel tatilleri yükle
 self.ozel_table.setRowCount(0)
 for tarih, aciklama in self.tatil_yoneticisi.ozel_tatiller:
 row = self.ozel_table.rowCount()
 self.ozel_table.insertRow(row)

 self.ozel_table.setItem(row, 0, QTableWidgetItem(tarih.strftime('%d.%m.%Y')))
 self.ozel_table.setItem(row, 1, QTableWidgetItem(aciklama))

 sil_btn = QPushButton("")
 sil_btn.clicked.connect(lambda checked, t=tarih: self.sil_ozel_tatil(t))
 self.ozel_table.setCellWidget(row, 2, sil_btn)

 # Cumartesi ayarı
 self.cumartesi_check.setChecked(self.tatil_yoneticisi.hafta_sonu_calisma)

 def on_cumartesi_changed(self, state):
 if self.tatil_yoneticisi:
 self.tatil_yoneticisi.hafta_sonu_calisma = state == Qt.CheckState.Checked.value

 def ekle_ozel_tatil(self):
 if not self.tatil_yoneticisi:
 return

 qdate = self.ozel_tarih.date()
 tarih = datetime(qdate.year(), qdate.month(), qdate.day())
 aciklama = self.ozel_aciklama.text() or "Özel Tatil"

 self.tatil_yoneticisi.ekle_ozel_tatil(tarih, aciklama)
 self.ozel_aciklama.clear()
 self.yukle_tatiller()

 def sil_ozel_tatil(self, tarih):
 if self.tatil_yoneticisi:
 self.tatil_yoneticisi.sil_ozel_tatil(tarih)
 self.yukle_tatiller()


class TaskDialog(QDialog):
 """İş kalemi ekleme/düzenleme dialog'u"""

 RENK_SECENEKLERI = [
 ("#3498db", "Mavi"),
 ("#2ecc71", "Yeşil"),
 ("#e74c3c", "Kırmızı"),
 ("#f39c12", "Turuncu"),
 ("#9b59b6", "Mor"),
 ("#1abc9c", "Turkuaz"),
 ("#34495e", "Koyu Gri"),
 ("#e67e22", "Koyu Turuncu"),
 ]

 def __init__(self, parent=None, task: Optional[Task] = None, db: Optional[DatabaseManager] = None,
 parent_tasks: Optional[Dict[int, Task]] = None):
 super().__init__(parent)
 self.task = task
 self.db = db
 self.parent_tasks = parent_tasks or {}
 self.selected_color = "#3498db"
 self.setWindowTitle("İş Kalemi Ekle/Düzenle")
 self.setModal(True)
 self.resize(550, 500)
 self.init_ui()

 if task:
 self.load_task_data()

 def init_ui(self):
 layout = QVBoxLayout()

 # Form
 form_layout = QFormLayout()

 # İş adı
 self.ad_input = QLineEdit()
 self.ad_input.setPlaceholderText("Örn: Temel kazısı")
 form_layout.addRow("İş Adı:", self.ad_input)

 # Süre
 self.sure_input = QSpinBox()
 self.sure_input.setRange(1, 365)
 self.sure_input.setValue(5)
 self.sure_input.setSuffix(" gün")
 form_layout.addRow("Süre (İş Günü):", self.sure_input)

 # Üst Görev (WBS için)
 self.parent_combo = QComboBox()
 self.parent_combo.addItem("Ana Görev (Üst yok)", None)
 for tid, t in self.parent_tasks.items():
 self.parent_combo.addItem(f"{t.wbs_kodu} - {t.ad}", tid)
 form_layout.addRow("Üst Görev (WBS):", self.parent_combo)

 # Kaynak/Ekip
 self.kaynak_input = QLineEdit()
 self.kaynak_input.setPlaceholderText("Örn: Ekip 1, Taşeron A")
 form_layout.addRow("Kaynak/Ekip:", self.kaynak_input)

 # Renk seçimi
 renk_layout = QHBoxLayout()
 self.renk_combo = QComboBox()
 for renk, ad in self.RENK_SECENEKLERI:
 self.renk_combo.addItem(ad, renk)
 self.renk_combo.currentIndexChanged.connect(self.on_renk_changed)
 renk_layout.addWidget(self.renk_combo)

 self.renk_preview = QLabel(" ")
 self.renk_preview.setFixedSize(30, 20)
 self.renk_preview.setStyleSheet(f"background-color: {self.selected_color}; border: 1px solid #ccc;")
 renk_layout.addWidget(self.renk_preview)

 ozel_renk_btn = QPushButton("")
 ozel_renk_btn.setFixedWidth(30)
 ozel_renk_btn.clicked.connect(self.sec_ozel_renk)
 renk_layout.addWidget(ozel_renk_btn)
 renk_layout.addStretch()

 form_layout.addRow("Çubuk Rengi:", renk_layout)

 # Milestone
 self.milestone_check = QCheckBox("Bu iş bir milestone (kilometre taşı)")
 form_layout.addRow("", self.milestone_check)

 # Metraj kalemi bağlantısı
 self.metraj_combo = QComboBox()
 self.metraj_combo.addItem("Bağlantı yok", None)
 self._yukle_metraj_kalemleri()
 form_layout.addRow("Metraj Kalemi:", self.metraj_combo)

 # Açıklama
 self.aciklama_input = QTextEdit()
 self.aciklama_input.setMaximumHeight(80)
 self.aciklama_input.setPlaceholderText("Opsiyonel açıklama...")
 form_layout.addRow("Açıklama:", self.aciklama_input)

 layout.addLayout(form_layout)

 # Butonlar
 buttons = QDialogButtonBox(
 QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
 )
 buttons.accepted.connect(self.accept)
 buttons.rejected.connect(self.reject)
 layout.addWidget(buttons)

 self.setLayout(layout)

 def _yukle_metraj_kalemleri(self):
 """Metraj kalemlerini yükle"""
 if not self.db:
 return
 try:
 with self.db.get_connection() as conn:
 cursor = conn.cursor()
 cursor.execute("SELECT id, is_kalemi FROM metraj_kalemleri ORDER BY id DESC LIMIT 100")
 kalemler = cursor.fetchall()
 for kalem in kalemler:
 self.metraj_combo.addItem(f"{kalem['id']} - {kalem['is_kalemi'][:30]}", kalem['id'])
 except Exception as e:
 logger.debug(f"Metraj kalemleri yüklenemedi: {e}")

 def on_renk_changed(self, index):
 self.selected_color = self.renk_combo.currentData()
 self.renk_preview.setStyleSheet(f"background-color: {self.selected_color}; border: 1px solid #ccc;")

 def sec_ozel_renk(self):
 color = QColorDialog.getColor(QColor(self.selected_color), self, "Renk Seç")
 if color.isValid():
 self.selected_color = color.name()
 self.renk_preview.setStyleSheet(f"background-color: {self.selected_color}; border: 1px solid #ccc;")

 def load_task_data(self):
 """Task verilerini form'a yükle"""
 if not self.task:
 return

 self.ad_input.setText(self.task.ad)
 self.sure_input.setValue(self.task.sure_gun)
 self.kaynak_input.setText(self.task.kaynak)
 self.milestone_check.setChecked(self.task.milestone)
 self.aciklama_input.setPlainText(self.task.aciklama)
 self.selected_color = self.task.renk or "#3498db"
 self.renk_preview.setStyleSheet(f"background-color: {self.selected_color}; border: 1px solid #ccc;")

 # Parent seçimi
 if self.task.parent_id:
 for i in range(self.parent_combo.count()):
 if self.parent_combo.itemData(i) == self.task.parent_id:
 self.parent_combo.setCurrentIndex(i)
 break

 def get_task_data(self) -> Dict[str, Any]:
 """Form'dan task verilerini al"""
 return {
 'ad': self.ad_input.text(),
 'sure_gun': self.sure_input.value(),
 'kaynak': self.kaynak_input.text(),
 'milestone': self.milestone_check.isChecked(),
 'aciklama': self.aciklama_input.toPlainText(),
 'metraj_kalem_id': self.metraj_combo.currentData(),
 'parent_id': self.parent_combo.currentData(),
 'renk': self.selected_color
 }


class DependencyDialog(QDialog):
 """Bağımlılık ekleme dialog'u"""

 def __init__(self, parent=None, tasks: Dict[int, Task] = None):
 super().__init__(parent)
 self.tasks = tasks or {}
 self.setWindowTitle("Bağımlılık Ekle")
 self.setModal(True)
 self.resize(400, 250)
 self.init_ui()

 def init_ui(self):
 layout = QVBoxLayout()

 # Form
 form_layout = QFormLayout()

 # Önceki iş
 self.onceki_combo = QComboBox()
 for task_id, task in self.tasks.items():
 self.onceki_combo.addItem(f"{task.ad} ({task.sure_gun} gün)", task_id)
 form_layout.addRow("Önceki İş:", self.onceki_combo)

 # Sonraki iş
 self.sonraki_combo = QComboBox()
 for task_id, task in self.tasks.items():
 self.sonraki_combo.addItem(f"{task.ad} ({task.sure_gun} gün)", task_id)
 form_layout.addRow("Sonraki İş:", self.sonraki_combo)

 # Bağımlılık tipi
 self.tip_combo = QComboBox()
 self.tip_combo.addItem("Finish-to-Start (FS) - En yaygın", "FS")
 self.tip_combo.addItem("Start-to-Start (SS)", "SS")
 self.tip_combo.addItem("Finish-to-Finish (FF)", "FF")
 self.tip_combo.addItem("Start-to-Finish (SF)", "SF")
 form_layout.addRow("Bağımlılık Tipi:", self.tip_combo)

 # Lag (gecikme)
 self.lag_input = QSpinBox()
 self.lag_input.setRange(-30, 30)
 self.lag_input.setValue(0)
 self.lag_input.setSuffix(" gün")
 form_layout.addRow("Gecikme/Öne Alma:", self.lag_input)

 # Açıklama
 aciklama_label = QLabel("""
 <b>Bağımlılık Tipleri:</b><br>
 <b>FS:</b> Önceki iş bitsin, sonraki başlasın<br>
 <b>SS:</b> Önceki iş başlasın, sonraki de başlasın<br>
 <b>FF:</b> Önceki iş bitsin, sonraki de bitsin<br>
 <b>SF:</b> Önceki iş başlasın, sonraki bitsin
 """)
 aciklama_label.setWordWrap(True)
 aciklama_label.setStyleSheet("background-color: #ecf0f1; padding: 10px; border-radius: 5px;")
 layout.addWidget(aciklama_label)

 layout.addLayout(form_layout)

 # Butonlar
 buttons = QDialogButtonBox(
 QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
 )
 buttons.accepted.connect(self.accept)
 buttons.rejected.connect(self.reject)
 layout.addWidget(buttons)

 self.setLayout(layout)

 def get_dependency_data(self) -> Dict[str, Any]:
 """Bağımlılık verilerini al"""
 return {
 'onceki_id': self.onceki_combo.currentData(),
 'sonraki_id': self.sonraki_combo.currentData(),
 'tip': self.tip_combo.currentData(),
 'lag': self.lag_input.value()
 }


class GanttWindow(QWidget):
 """Gantt Chart ve CPM widget'i"""

 def __init__(self, db: DatabaseManager):
 super().__init__()
 self.db = db
 self.engine = GanttEngine(db)
 self.current_project_id: Optional[int] = None
 self.next_task_id = 1
 self.init_ui()
 self.load_projeler()

 def init_ui(self):
 """UI elementlerini oluştur"""
 layout = QVBoxLayout()

 # Başlık
 baslik = QLabel("Gantt Chart ve İş Programı (Gelişmiş)")
 baslik.setStyleSheet("font-size: 20pt; font-weight: bold; margin: 10px; color: #2c3e50;")
 layout.addWidget(baslik)

 # Proje seçimi ve kontroller
 kontrol_layout = QHBoxLayout()

 proje_label = QLabel("Proje:")
 proje_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
 self.proje_combo = QComboBox()
 self.proje_combo.currentIndexChanged.connect(self.on_proje_changed)
 kontrol_layout.addWidget(proje_label)
 kontrol_layout.addWidget(self.proje_combo)

 kontrol_layout.addStretch()

 # Tatil Yönetimi butonu
 tatil_btn = QPushButton(" Tatiller")
 tatil_btn.setStyleSheet("background-color: #9b59b6; color: white; padding: 5px 10px; border-radius: 3px;")
 tatil_btn.clicked.connect(self.goster_tatil_dialog)
 kontrol_layout.addWidget(tatil_btn)

 # Baseline butonu
 baseline_btn = QPushButton(" Baseline Kaydet")
 baseline_btn.setStyleSheet("background-color: #e67e22; color: white; padding: 5px 10px; border-radius: 3px;")
 baseline_btn.clicked.connect(self.kaydet_baseline)
 kontrol_layout.addWidget(baseline_btn)

 # Yükle butonu
 yukle_btn = QPushButton(" Yükle")
 yukle_btn.clicked.connect(self.yukle_program)
 kontrol_layout.addWidget(yukle_btn)

 # Kaydet butonu
 kaydet_btn = QPushButton(" Kaydet")
 kaydet_btn.clicked.connect(self.kaydet_program)
 kontrol_layout.addWidget(kaydet_btn)

 # Export butonu
 export_btn = QPushButton(" Export")
 export_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 5px 10px; border-radius: 3px;")
 export_btn.clicked.connect(self.goster_export_menu)
 kontrol_layout.addWidget(export_btn)

 # Şablon Ekle butonu
 sablon_btn = QPushButton(" Şablon Ekle")
 sablon_btn.setStyleSheet("background-color: #1abc9c; color: white; padding: 5px 10px; border-radius: 3px;")
 sablon_btn.clicked.connect(self.goster_sablon_dialog)
 kontrol_layout.addWidget(sablon_btn)

 # Uyarılar butonu
 self.alerts_btn = QPushButton(" Uyarılar")
 self.alerts_btn.setStyleSheet("background-color: #f39c12; color: white; padding: 5px 10px; border-radius: 3px;")
 self.alerts_btn.clicked.connect(self.goster_uyarilar)
 kontrol_layout.addWidget(self.alerts_btn)

 layout.addLayout(kontrol_layout)

 # Sekmeler
 self.tab_widget = QTabWidget()
 self.tab_widget.setStyleSheet("""
 QTabWidget::pane {
 border: 1px solid #ccc;
 border-radius: 5px;
 background-color: white;
 }
 QTabBar::tab {
 background-color: #ecf0f1;
 padding: 10px 15px;
 margin-right: 2px;
 border-top-left-radius: 5px;
 border-top-right-radius: 5px;
 }
 QTabBar::tab:selected {
 background-color: #3498db;
 color: white;
 font-weight: bold;
 }
 """)

 # Sekmeler oluştur
 self.tab_widget.addTab(self._create_program_tab(), " İş Programı")
 self.tab_widget.addTab(self._create_visual_gantt_tab(), " Görsel Gantt")
 self.tab_widget.addTab(self._create_gantt_tab(), " Tablo Görünüm")
 self.tab_widget.addTab(self._create_kritik_tab(), " Kritik Yol")
 self.tab_widget.addTab(self._create_s_curve_tab(), " S-Curve")
 self.tab_widget.addTab(self._create_what_if_tab(), " What-If")
 self.tab_widget.addTab(self._create_baseline_tab(), " Baseline")
 self.tab_widget.addTab(self._create_kaynak_tab(), " Kaynaklar")
 self.tab_widget.addTab(self._create_gecikme_tab(), " Gecikme")

 layout.addWidget(self.tab_widget)
 self.setLayout(layout)

 def _create_visual_gantt_tab(self) -> QWidget:
 """Görsel Gantt Chart sekmesi"""
 widget = QWidget()
 layout = QVBoxLayout()

 # Kontrol butonları
 kontrol_layout = QHBoxLayout()

 # Zoom preset butonları
 zoom_label = QLabel("Görünüm:")
 zoom_label.setStyleSheet("font-weight: bold;")
 kontrol_layout.addWidget(zoom_label)

 zoom_weekly_btn = QPushButton("Haftalık")
 zoom_weekly_btn.setStyleSheet("padding: 3px 8px;")
 zoom_weekly_btn.clicked.connect(lambda: self.set_zoom_preset('weekly'))
 kontrol_layout.addWidget(zoom_weekly_btn)

 zoom_monthly_btn = QPushButton("Aylık")
 zoom_monthly_btn.setStyleSheet("padding: 3px 8px;")
 zoom_monthly_btn.clicked.connect(lambda: self.set_zoom_preset('monthly'))
 kontrol_layout.addWidget(zoom_monthly_btn)

 zoom_quarterly_btn = QPushButton("3 Aylık")
 zoom_quarterly_btn.setStyleSheet("padding: 3px 8px;")
 zoom_quarterly_btn.clicked.connect(lambda: self.set_zoom_preset('quarterly'))
 kontrol_layout.addWidget(zoom_quarterly_btn)

 zoom_yearly_btn = QPushButton("Yıllık")
 zoom_yearly_btn.setStyleSheet("padding: 3px 8px;")
 zoom_yearly_btn.clicked.connect(lambda: self.set_zoom_preset('yearly'))
 kontrol_layout.addWidget(zoom_yearly_btn)

 kontrol_layout.addWidget(QLabel("|"))

 zoom_in_btn = QPushButton("+")
 zoom_in_btn.setFixedWidth(35)
 zoom_in_btn.clicked.connect(self.zoom_in_gantt)
 kontrol_layout.addWidget(zoom_in_btn)

 zoom_out_btn = QPushButton("-")
 zoom_out_btn.setFixedWidth(35)
 zoom_out_btn.clicked.connect(self.zoom_out_gantt)
 kontrol_layout.addWidget(zoom_out_btn)

 kontrol_layout.addStretch()

 # Görünüm seçenekleri
 self.show_baseline_check = QCheckBox("Baseline Göster")
 self.show_baseline_check.setChecked(True)
 self.show_baseline_check.stateChanged.connect(self.refresh_visual_gantt)
 kontrol_layout.addWidget(self.show_baseline_check)

 self.show_progress_check = QCheckBox("İlerleme Göster")
 self.show_progress_check.setChecked(True)
 self.show_progress_check.stateChanged.connect(self.refresh_visual_gantt)
 kontrol_layout.addWidget(self.show_progress_check)

 self.show_critical_check = QCheckBox("Kritik Vurgula")
 self.show_critical_check.setChecked(True)
 self.show_critical_check.stateChanged.connect(self.refresh_visual_gantt)
 kontrol_layout.addWidget(self.show_critical_check)

 # Drag & Drop seçeneği
 self.drag_drop_check = QCheckBox("Drag & Drop")
 self.drag_drop_check.setChecked(True)
 self.drag_drop_check.setToolTip("Görevleri sürükleyerek tarih değiştir (sadece kritik olmayan görevler)")
 self.drag_drop_check.stateChanged.connect(self.toggle_drag_drop)
 kontrol_layout.addWidget(self.drag_drop_check)

 # Otomatik cascade seçeneği
 self.cascade_check = QCheckBox("Otomatik Kaydır")
 self.cascade_check.setChecked(True)
 self.cascade_check.setToolTip("Görev taşındığında bağımlı görevleri de otomatik kaydır")
 kontrol_layout.addWidget(self.cascade_check)

 yenile_btn = QPushButton(" Yenile")
 yenile_btn.clicked.connect(self.refresh_visual_gantt)
 kontrol_layout.addWidget(yenile_btn)

 layout.addLayout(kontrol_layout)

 # Gantt Chart görünümü
 self.gantt_view = GanttChartView()
 self.gantt_view.on_task_moved = self.on_task_dragged # Drag callback
 layout.addWidget(self.gantt_view)

 # Renk açıklamaları
 renk_layout = QHBoxLayout()
 renk_layout.addWidget(QLabel("Renkler:"))

 self._add_renk_aciklama(renk_layout, "#3498db", "Normal")
 self._add_renk_aciklama(renk_layout, "#e74c3c", "Kritik")
 self._add_renk_aciklama(renk_layout, "#27ae60", "Tamamlandı")
 self._add_renk_aciklama(renk_layout, "#9b59b6", "Milestone")
 self._add_renk_aciklama(renk_layout, "#bdc3c7", "Baseline")
 self._add_renk_aciklama(renk_layout, "#ffebee", "Tatil")

 renk_layout.addStretch()
 layout.addLayout(renk_layout)

 widget.setLayout(layout)
 return widget

 def _create_baseline_tab(self) -> QWidget:
 """Baseline karşılaştırma sekmesi"""
 widget = QWidget()
 layout = QVBoxLayout()

 # Özet kartlar
 kart_layout = QHBoxLayout()

 self.baseline_tarih_kart = self._create_kpi_card(
 " Baseline Tarihi",
 "Kayıtlı Değil",
 "#9b59b6",
 "İlk plan tarihi"
 )
 kart_layout.addWidget(self.baseline_tarih_kart)

 self.geciken_gorev_kart = self._create_kpi_card(
 " Geciken Görev",
 "0",
 "#e74c3c",
 "Baseline'dan geç"
 )
 kart_layout.addWidget(self.geciken_gorev_kart)

 self.proje_sapma_kart = self._create_kpi_card(
 " Proje Sapması",
 "0 gün",
 "#e67e22",
 "Toplam gecikme"
 )
 kart_layout.addWidget(self.proje_sapma_kart)

 self.zamaninda_kart = self._create_kpi_card(
 " Zamanında",
 "0",
 "#27ae60",
 "Plana uygun"
 )
 kart_layout.addWidget(self.zamaninda_kart)

 layout.addLayout(kart_layout)

 # Karşılaştırma tablosu
 baseline_group = QGroupBox(" Baseline vs Mevcut Durum Karşılaştırması")
 baseline_layout = QVBoxLayout()

 analiz_btn = QPushButton(" Baseline Analizi Yap")
 analiz_btn.setStyleSheet("""
 QPushButton {
 background-color: #9b59b6;
 color: white;
 padding: 10px;
 font-size: 12pt;
 font-weight: bold;
 border-radius: 5px;
 }
 QPushButton:hover { background-color: #8e44ad; }
 """)
 analiz_btn.clicked.connect(self.analiz_baseline)
 baseline_layout.addWidget(analiz_btn)

 self.baseline_table = QTableWidget()
 self.baseline_table.setColumnCount(9)
 self.baseline_table.setHorizontalHeaderLabels([
 "WBS", "İş Adı", "Baseline Başlangıç", "Mevcut Başlangıç", "Başlangıç Sapma",
 "Baseline Bitiş", "Mevcut Bitiş", "Bitiş Sapma", "Durum"
 ])
 self.baseline_table.horizontalHeader().setStretchLastSection(True)
 baseline_layout.addWidget(self.baseline_table)

 baseline_group.setLayout(baseline_layout)
 layout.addWidget(baseline_group)

 widget.setLayout(layout)
 return widget

 def _create_kaynak_tab(self) -> QWidget:
 """Kaynak yönetimi ve çakışma kontrolü sekmesi"""
 widget = QWidget()
 layout = QVBoxLayout()

 # Kaynak ekleme
 ekle_group = QGroupBox(" Kaynak Ekle")
 ekle_layout = QHBoxLayout()

 self.kaynak_ad_input = QLineEdit()
 self.kaynak_ad_input.setPlaceholderText("Kaynak adı (Ekip 1, Usta Ali, vb.)")
 ekle_layout.addWidget(self.kaynak_ad_input)

 self.kaynak_kapasite_input = QSpinBox()
 self.kaynak_kapasite_input.setRange(1, 10)
 self.kaynak_kapasite_input.setValue(1)
 self.kaynak_kapasite_input.setPrefix("Kapasite: ")
 ekle_layout.addWidget(self.kaynak_kapasite_input)

 kaynak_ekle_btn = QPushButton(" Ekle")
 kaynak_ekle_btn.clicked.connect(self.ekle_kaynak)
 ekle_layout.addWidget(kaynak_ekle_btn)

 ekle_group.setLayout(ekle_layout)
 layout.addWidget(ekle_group)

 # Kaynak listesi
 kaynak_group = QGroupBox(" Kaynaklar")
 kaynak_layout = QVBoxLayout()

 self.kaynak_table = QTableWidget()
 self.kaynak_table.setColumnCount(4)
 self.kaynak_table.setHorizontalHeaderLabels(["Kaynak Adı", "Kapasite", "Atama Sayısı", "Durum"])
 self.kaynak_table.horizontalHeader().setStretchLastSection(True)
 kaynak_layout.addWidget(self.kaynak_table)

 kaynak_group.setLayout(kaynak_layout)
 layout.addWidget(kaynak_group)

 # Çakışma kontrolü
 cakisma_group = QGroupBox(" Kaynak Çakışmaları")
 cakisma_layout = QVBoxLayout()

 # Butonlar yan yana
 btn_layout = QHBoxLayout()

 cakisma_btn = QPushButton(" Çakışma Kontrolü Yap")
 cakisma_btn.setStyleSheet("""
 QPushButton {
 background-color: #e74c3c;
 color: white;
 padding: 10px;
 font-size: 12pt;
 font-weight: bold;
 border-radius: 5px;
 }
 QPushButton:hover { background-color: #c0392b; }
 """)
 cakisma_btn.clicked.connect(self.kontrol_kaynak_cakisma)
 btn_layout.addWidget(cakisma_btn)

 # Otomatik Dengeleme butonu
 dengele_btn = QPushButton(" Otomatik Dengele")
 dengele_btn.setStyleSheet("""
 QPushButton {
 background-color: #27ae60;
 color: white;
 padding: 10px;
 font-size: 12pt;
 font-weight: bold;
 border-radius: 5px;
 }
 QPushButton:hover { background-color: #219a52; }
 """)
 dengele_btn.clicked.connect(self.otomatik_kaynak_dengele)
 btn_layout.addWidget(dengele_btn)

 cakisma_layout.addLayout(btn_layout)

 self.cakisma_table = QTableWidget()
 self.cakisma_table.setColumnCount(5)
 self.cakisma_table.setHorizontalHeaderLabels(["Kaynak", "Tarih", "Görev Sayısı", "Kapasite", "Çakışan Görevler"])
 self.cakisma_table.horizontalHeader().setStretchLastSection(True)
 cakisma_layout.addWidget(self.cakisma_table)

 cakisma_group.setLayout(cakisma_layout)
 layout.addWidget(cakisma_group)

 widget.setLayout(layout)
 return widget

 # Yeni metodlar
 def goster_tatil_dialog(self):
 """Tatil yönetimi dialog'unu göster"""
 dialog = TatilDialog(self, self.engine.tatil_yoneticisi)
 dialog.exec()
 # Tatil değişikliklerinden sonra yeniden hesapla
 if self.engine.tasks:
 self.hesapla_program()

 def kaydet_baseline(self):
 """Mevcut planı baseline olarak kaydet"""
 if not self.engine.tasks:
 QMessageBox.warning(self, "Uyarı", "Önce iş programı oluşturun")
 return

 if not self.engine.proje_baslangic:
 QMessageBox.warning(self, "Uyarı", "Önce iş programını hesaplayın")
 return

 reply = QMessageBox.question(
 self, "Baseline Kaydet",
 "Mevcut plan baseline olarak kaydedilecek.\nEski baseline varsa üzerine yazılacak.\n\nDevam edilsin mi?",
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
 )

 if reply == QMessageBox.StandardButton.Yes:
 sonuc = self.engine.save_baseline()
 if sonuc['success']:
 QMessageBox.information(
 self, "Başarılı",
 f"Baseline kaydedildi!\nTarih: {sonuc['tarih'].strftime('%d.%m.%Y %H:%M')}\nGörev: {sonuc['gorev_sayisi']}"
 )
 self.refresh_visual_gantt()
 else:
 QMessageBox.critical(self, "Hata", sonuc.get('error', 'Bilinmeyen hata'))

 def goster_export_menu(self):
 """Export menüsünü göster"""
 menu = QMenu(self)

 excel_action = menu.addAction(" Excel'e Aktar")
 excel_action.triggered.connect(self.export_excel)

 pdf_action = menu.addAction(" PDF'e Aktar")
 pdf_action.triggered.connect(self.export_pdf)

 menu.addSeparator()

 json_action = menu.addAction(" JSON'a Aktar")
 json_action.triggered.connect(self.export_json)

 # Butona göre menüyü göster
 sender = self.sender()
 if sender:
 menu.exec(sender.mapToGlobal(sender.rect().bottomLeft()))

 def export_excel(self):
 """Excel'e aktar"""
 if not self.engine.tasks:
 QMessageBox.warning(self, "Uyarı", "Dışa aktarılacak veri yok")
 return

 dosya_yolu, _ = QFileDialog.getSaveFileName(
 self, "Excel Kaydet", "", "Excel Dosyası (*.xlsx)"
 )

 if dosya_yolu:
 try:
 import openpyxl
 from openpyxl.styles import Font, PatternFill, Alignment

 wb = openpyxl.Workbook()
 ws = wb.active
 ws.title = "İş Programı"

 # Başlıklar
 basliklar = ["WBS", "İş Adı", "Süre", "Başlangıç", "Bitiş", "İlerleme", "Float", "Kritik", "Kaynak"]
 for col, baslik in enumerate(basliklar, 1):
 cell = ws.cell(row=1, column=col, value=baslik)
 cell.font = Font(bold=True, color="FFFFFF")
 cell.fill = PatternFill(start_color="3498DB", end_color="3498DB", fill_type="solid")

 # Veriler
 data = self.engine.export_to_excel_data()
 for row_idx, row_data in enumerate(data, 2):
 ws.cell(row=row_idx, column=1, value=row_data['WBS'])
 ws.cell(row=row_idx, column=2, value=row_data['İş Adı'])
 ws.cell(row=row_idx, column=3, value=row_data['Süre (Gün)'])
 ws.cell(row=row_idx, column=4, value=row_data['Başlangıç'])
 ws.cell(row=row_idx, column=5, value=row_data['Bitiş'])
 ws.cell(row=row_idx, column=6, value=row_data['İlerleme (%)'])
 ws.cell(row=row_idx, column=7, value=row_data['Float (Gün)'])
 ws.cell(row=row_idx, column=8, value=row_data['Kritik'])
 ws.cell(row=row_idx, column=9, value=row_data['Kaynak'])

 # Kritik satırları vurgula
 if row_data['Kritik'] == 'Evet':
 for col in range(1, 10):
 ws.cell(row=row_idx, column=col).fill = PatternFill(
 start_color="FFEBEE", end_color="FFEBEE", fill_type="solid"
 )

 # Sütun genişlikleri
 ws.column_dimensions['A'].width = 10
 ws.column_dimensions['B'].width = 30
 ws.column_dimensions['C'].width = 10
 ws.column_dimensions['D'].width = 12
 ws.column_dimensions['E'].width = 12
 ws.column_dimensions['I'].width = 15

 wb.save(dosya_yolu)
 QMessageBox.information(self, "Başarılı", f"Excel dosyası kaydedildi:\n{dosya_yolu}")

 except ImportError:
 QMessageBox.critical(self, "Hata", "openpyxl kütüphanesi yüklü değil.\npip install openpyxl")
 except Exception as e:
 QMessageBox.critical(self, "Hata", f"Export hatası: {e}")

 def export_pdf(self):
 """PDF'e aktar"""
 if not self.engine.tasks:
 QMessageBox.warning(self, "Uyarı", "Dışa aktarılacak veri yok")
 return

 dosya_yolu, _ = QFileDialog.getSaveFileName(
 self, "PDF Kaydet", "", "PDF Dosyası (*.pdf)"
 )

 if dosya_yolu:
 try:
 from reportlab.lib.pagesizes import A4, landscape
 from reportlab.lib import colors
 from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
 from reportlab.lib.styles import getSampleStyleSheet

 doc = SimpleDocTemplate(dosya_yolu, pagesize=landscape(A4))
 elements = []
 styles = getSampleStyleSheet()

 # Başlık
 elements.append(Paragraph("İŞ PROGRAMI RAPORU", styles['Heading1']))
 elements.append(Spacer(1, 20))

 # Proje bilgileri
 if self.engine.proje_baslangic and self.engine.proje_bitis:
 info_text = f"""
 Proje Başlangıç: {self.engine.proje_baslangic.strftime('%d.%m.%Y')}<br/>
 Proje Bitiş: {self.engine.proje_bitis.strftime('%d.%m.%Y')}<br/>
 Toplam Görev: {len(self.engine.tasks)}<br/>
 Kritik Görev: {len(self.engine.kritik_yol)}
 """
 elements.append(Paragraph(info_text, styles['Normal']))
 elements.append(Spacer(1, 20))

 # Tablo
 data = [["WBS", "İş Adı", "Süre", "Başlangıç", "Bitiş", "İlerleme", "Kritik"]]

 for row_data in self.engine.export_to_excel_data():
 data.append([
 row_data['WBS'],
 row_data['İş Adı'][:25],
 str(row_data['Süre (Gün)']),
 row_data['Başlangıç'],
 row_data['Bitiş'],
 f"{row_data['İlerleme (%)']}%",
 row_data['Kritik']
 ])

 table = Table(data)
 table.setStyle(TableStyle([
 ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
 ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
 ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
 ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
 ('FONTSIZE', (0, 0), (-1, 0), 10),
 ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
 ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
 ('GRID', (0, 0), (-1, -1), 1, colors.black)
 ]))

 elements.append(table)
 doc.build(elements)

 QMessageBox.information(self, "Başarılı", f"PDF dosyası kaydedildi:\n{dosya_yolu}")

 except ImportError:
 QMessageBox.critical(self, "Hata", "reportlab kütüphanesi yüklü değil.\npip install reportlab")
 except Exception as e:
 QMessageBox.critical(self, "Hata", f"Export hatası: {e}")

 def export_json(self):
 """JSON'a aktar"""
 if not self.engine.tasks:
 QMessageBox.warning(self, "Uyarı", "Dışa aktarılacak veri yok")
 return

 dosya_yolu, _ = QFileDialog.getSaveFileName(
 self, "JSON Kaydet", "", "JSON Dosyası (*.json)"
 )

 if dosya_yolu:
 try:
 import json
 data = self.engine.export_to_dict()

 with open(dosya_yolu, 'w', encoding='utf-8') as f:
 json.dump(data, f, ensure_ascii=False, indent=2, default=str)

 QMessageBox.information(self, "Başarılı", f"JSON dosyası kaydedildi:\n{dosya_yolu}")

 except Exception as e:
 QMessageBox.critical(self, "Hata", f"Export hatası: {e}")

 def zoom_in_gantt(self):
 """Gantt chart yakınlaştır"""
 self.gantt_view.zoom_in()
 self.refresh_visual_gantt()

 def zoom_out_gantt(self):
 """Gantt chart uzaklaştır"""
 self.gantt_view.zoom_out()
 self.refresh_visual_gantt()

 def set_zoom_preset(self, preset: str):
 """Zoom preset ayarla"""
 self.gantt_view.set_zoom_preset(preset)
 self.refresh_visual_gantt()

 def refresh_visual_gantt(self):
 """Görsel Gantt chart'ı yenile"""
 self.gantt_view.show_baseline = self.show_baseline_check.isChecked()
 self.gantt_view.show_progress = self.show_progress_check.isChecked()
 self.gantt_view.show_critical = self.show_critical_check.isChecked()

 data = self.engine.get_gantt_chart_data()
 self.gantt_view.draw_gantt(data)

 def analiz_baseline(self):
 """Baseline analizi yap"""
 if not self.engine.baseline_kayitli:
 QMessageBox.warning(self, "Uyarı", "Önce baseline kaydedin")
 return

 ozet = self.engine.get_baseline_summary()
 karsilastirma = self.engine.get_baseline_comparison()

 # KPI kartları güncelle
 deger_label = self.baseline_tarih_kart.findChild(QLabel, "deger_label")
 if deger_label and ozet.get('baseline_tarihi'):
 deger_label.setText(ozet['baseline_tarihi'].strftime('%d.%m.%Y'))

 deger_label = self.geciken_gorev_kart.findChild(QLabel, "deger_label")
 if deger_label:
 deger_label.setText(str(ozet.get('geciken_gorev', 0)))

 deger_label = self.proje_sapma_kart.findChild(QLabel, "deger_label")
 if deger_label:
 sapma = ozet.get('proje_sapmasi', 0)
 deger_label.setText(f"{'+' if sapma > 0 else ''}{sapma} gün")

 deger_label = self.zamaninda_kart.findChild(QLabel, "deger_label")
 if deger_label:
 deger_label.setText(str(ozet.get('zamaninda_gorev', 0)))

 # Tablo güncelle
 self.baseline_table.setRowCount(0)

 for item in karsilastirma:
 row = self.baseline_table.rowCount()
 self.baseline_table.insertRow(row)

 self.baseline_table.setItem(row, 0, QTableWidgetItem(item['wbs_kodu'] or ''))
 self.baseline_table.setItem(row, 1, QTableWidgetItem(item['ad']))
 self.baseline_table.setItem(row, 2, QTableWidgetItem(
 item['baseline_baslangic'].strftime('%d.%m.%Y') if item['baseline_baslangic'] else '-'))
 self.baseline_table.setItem(row, 3, QTableWidgetItem(
 item['mevcut_baslangic'].strftime('%d.%m.%Y') if item['mevcut_baslangic'] else '-'))

 # Başlangıç sapma
 sapma_item = QTableWidgetItem(f"{item['baslangic_sapma']:+d} gün")
 if item['baslangic_sapma'] > 0:
 sapma_item.setBackground(QBrush(QColor("#ffebee")))
 self.baseline_table.setItem(row, 4, sapma_item)

 self.baseline_table.setItem(row, 5, QTableWidgetItem(
 item['baseline_bitis'].strftime('%d.%m.%Y') if item['baseline_bitis'] else '-'))
 self.baseline_table.setItem(row, 6, QTableWidgetItem(
 item['mevcut_bitis'].strftime('%d.%m.%Y') if item['mevcut_bitis'] else '-'))

 # Bitiş sapma
 sapma_item = QTableWidgetItem(f"{item['bitis_sapma']:+d} gün")
 if item['bitis_sapma'] > 0:
 sapma_item.setBackground(QBrush(QColor("#ffebee")))
 self.baseline_table.setItem(row, 7, sapma_item)

 # Durum
 if item['gecikme_var']:
 durum = " Gecikme"
 renk = QColor("#e74c3c")
 else:
 durum = " Zamanında"
 renk = QColor("#27ae60")

 durum_item = QTableWidgetItem(durum)
 durum_item.setForeground(QBrush(renk))
 self.baseline_table.setItem(row, 8, durum_item)

 def ekle_kaynak(self):
 """Yeni kaynak ekle"""
 ad = self.kaynak_ad_input.text().strip()
 if not ad:
 QMessageBox.warning(self, "Uyarı", "Kaynak adı girin")
 return

 kapasite = self.kaynak_kapasite_input.value()
 self.engine.add_kaynak(ad, kapasite)

 self.kaynak_ad_input.clear()
 self.yukle_kaynaklar()
 QMessageBox.information(self, "Başarılı", f"Kaynak eklendi: {ad}")

 def yukle_kaynaklar(self):
 """Kaynak listesini yükle"""
 self.kaynak_table.setRowCount(0)

 for kaynak_adi, bilgi in self.engine.kaynaklar.items():
 row = self.kaynak_table.rowCount()
 self.kaynak_table.insertRow(row)

 self.kaynak_table.setItem(row, 0, QTableWidgetItem(kaynak_adi))
 self.kaynak_table.setItem(row, 1, QTableWidgetItem(str(bilgi['kapasite'])))
 self.kaynak_table.setItem(row, 2, QTableWidgetItem(str(len(bilgi['atamalar']))))

 # Durum
 atama = len(bilgi['atamalar'])
 if atama == 0:
 durum = "Boşta"
 renk = "#95a5a6"
 elif atama <= bilgi['kapasite']:
 durum = "Normal"
 renk = "#27ae60"
 else:
 durum = "Aşırı Yük"
 renk = "#e74c3c"

 durum_item = QTableWidgetItem(durum)
 durum_item.setForeground(QBrush(QColor(renk)))
 self.kaynak_table.setItem(row, 3, durum_item)

 def kontrol_kaynak_cakisma(self):
 """Kaynak çakışmalarını kontrol et"""
 cakismalar = self.engine.check_kaynak_cakisma()

 self.cakisma_table.setRowCount(0)

 if not cakismalar:
 QMessageBox.information(self, "Sonuç", "Kaynak çakışması bulunamadı! ")
 return

 for cakisma in cakismalar:
 row = self.cakisma_table.rowCount()
 self.cakisma_table.insertRow(row)

 self.cakisma_table.setItem(row, 0, QTableWidgetItem(cakisma['kaynak']))
 self.cakisma_table.setItem(row, 1, QTableWidgetItem(cakisma['tarih']))
 self.cakisma_table.setItem(row, 2, QTableWidgetItem(str(cakisma['gorev_sayisi'])))
 self.cakisma_table.setItem(row, 3, QTableWidgetItem(str(cakisma['kapasite'])))
 self.cakisma_table.setItem(row, 4, QTableWidgetItem(", ".join(cakisma['gorevler'])))

 QMessageBox.warning(self, "Uyarı", f"{len(cakismalar)} adet kaynak çakışması tespit edildi!")

 def _create_program_tab(self) -> QWidget:
 """İş programı oluşturma sekmesi"""
 widget = QWidget()
 layout = QVBoxLayout()

 # Proje ayarları
 ayarlar_group = QGroupBox("Proje Ayarları")
 ayarlar_layout = QFormLayout()

 # Başlangıç tarihi
 self.baslangic_date = QDateEdit()
 self.baslangic_date.setDate(QDate.currentDate())
 self.baslangic_date.setCalendarPopup(True)
 self.baslangic_date.setDisplayFormat("dd-MM-yyyy")
 ayarlar_layout.addRow("Proje Başlangıç Tarihi:", self.baslangic_date)

 # Hesapla butonu
 hesapla_btn = QPushButton(" İş Programını Hesapla (CPM)")
 hesapla_btn.setStyleSheet("""
 QPushButton {
 background-color: #e67e22;
 color: white;
 padding: 10px;
 font-size: 12pt;
 font-weight: bold;
 border-radius: 5px;
 }
 QPushButton:hover {
 background-color: #d35400;
 }
 """)
 hesapla_btn.clicked.connect(self.hesapla_program)
 ayarlar_layout.addRow("", hesapla_btn)

 ayarlar_group.setLayout(ayarlar_layout)
 layout.addWidget(ayarlar_group)

 # İş listesi ve işlemler
 is_group = QGroupBox("İş Kalemleri")
 is_layout = QVBoxLayout()

 # Butonlar
 btn_layout = QHBoxLayout()

 ekle_btn = QPushButton(" İş Ekle")
 ekle_btn.clicked.connect(self.ekle_is)
 btn_layout.addWidget(ekle_btn)

 duzenle_btn = QPushButton(" Düzenle")
 duzenle_btn.clicked.connect(self.duzenle_is)
 btn_layout.addWidget(duzenle_btn)

 sil_btn = QPushButton(" Sil")
 sil_btn.clicked.connect(self.sil_is)
 btn_layout.addWidget(sil_btn)

 btn_layout.addStretch()

 bagimlilk_btn = QPushButton(" Bağımlılık Ekle")
 bagimlilk_btn.clicked.connect(self.ekle_bagimliluk)
 btn_layout.addWidget(bagimlilk_btn)

 is_layout.addLayout(btn_layout)

 # İş tablosu
 self.is_table = QTableWidget()
 self.is_table.setColumnCount(6)
 self.is_table.setHorizontalHeaderLabels([
 "ID", "İş Adı", "Süre (Gün)", "Kaynak", "Milestone", "Bağımlılıklar"
 ])
 self.is_table.horizontalHeader().setStretchLastSection(True)
 self.is_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
 is_layout.addWidget(self.is_table)

 is_group.setLayout(is_layout)
 layout.addWidget(is_group)

 widget.setLayout(layout)
 return widget

 def _create_gantt_tab(self) -> QWidget:
 """Gantt chart görünüm sekmesi"""
 widget = QWidget()
 layout = QVBoxLayout()

 # Özet bilgiler
 ozet_layout = QHBoxLayout()

 self.toplam_sure_label = QLabel("Toplam Süre: - gün")
 self.toplam_sure_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
 ozet_layout.addWidget(self.toplam_sure_label)

 self.baslangic_label = QLabel("Başlangıç: -")
 ozet_layout.addWidget(self.baslangic_label)

 self.bitis_label = QLabel("Bitiş: -")
 ozet_layout.addWidget(self.bitis_label)

 ozet_layout.addStretch()

 layout.addLayout(ozet_layout)

 # Gantt tablosu
 self.gantt_table = QTableWidget()
 self.gantt_table.setColumnCount(8)
 self.gantt_table.setHorizontalHeaderLabels([
 "İş Adı", "Başlangıç", "Bitiş", "Süre", "İlerleme", "Float", "Durum", "Kritik"
 ])
 self.gantt_table.horizontalHeader().setStretchLastSection(True)
 layout.addWidget(self.gantt_table)

 # Renk açıklamaları
 renk_layout = QHBoxLayout()
 renk_layout.addWidget(QLabel("Renkler:"))

 self._add_renk_aciklama(renk_layout, "#27ae60", "Tamamlandı")
 self._add_renk_aciklama(renk_layout, "#3498db", "Devam Ediyor")
 self._add_renk_aciklama(renk_layout, "#e74c3c", "Gecikmeli")
 self._add_renk_aciklama(renk_layout, "#95a5a6", "Başlanmadı")
 self._add_renk_aciklama(renk_layout, "#f39c12", "Kritik Yol")

 renk_layout.addStretch()
 layout.addLayout(renk_layout)

 widget.setLayout(layout)
 return widget

 def _create_kritik_tab(self) -> QWidget:
 """Kritik yol analizi sekmesi"""
 widget = QWidget()
 layout = QVBoxLayout()

 # Özet kartlar
 kart_layout = QHBoxLayout()

 self.kritik_sure_kart = self._create_kpi_card(
 " Kritik Yol Süresi",
 "0 gün",
 "#e74c3c",
 "Minimum proje süresi"
 )
 kart_layout.addWidget(self.kritik_sure_kart)

 self.kritik_is_kart = self._create_kpi_card(
 " Kritik İş Sayısı",
 "0",
 "#e67e22",
 "Float = 0 olan işler"
 )
 kart_layout.addWidget(self.kritik_is_kart)

 self.kritik_yuzde_kart = self._create_kpi_card(
 " Kritik Oran",
 "0%",
 "#3498db",
 "Toplam içinde"
 )
 kart_layout.addWidget(self.kritik_yuzde_kart)

 layout.addLayout(kart_layout)

 # Kritik yol listesi
 kritik_group = QGroupBox(" Kritik Yol İşleri (Float = 0)")
 kritik_layout = QVBoxLayout()

 self.kritik_table = QTableWidget()
 self.kritik_table.setColumnCount(6)
 self.kritik_table.setHorizontalHeaderLabels([
 "İş Adı", "Başlangıç", "Bitiş", "Süre (Gün)", "İlerleme (%)", "Durum"
 ])
 self.kritik_table.horizontalHeader().setStretchLastSection(True)
 kritik_layout.addWidget(self.kritik_table)

 kritik_group.setLayout(kritik_layout)
 layout.addWidget(kritik_group)

 # Esneklik (Float) analizi
 float_group = QGroupBox(" Esneklik (Float) Analizi")
 float_layout = QVBoxLayout()

 self.float_table = QTableWidget()
 self.float_table.setColumnCount(7)
 self.float_table.setHorizontalHeaderLabels([
 "İş Adı", "Early Start", "Late Start", "Early Finish", "Late Finish", "Float (Gün)", "Kritik"
 ])
 self.float_table.horizontalHeader().setStretchLastSection(True)
 float_layout.addWidget(self.float_table)

 float_group.setLayout(float_layout)
 layout.addWidget(float_group)

 widget.setLayout(layout)
 return widget

 def _create_gecikme_tab(self) -> QWidget:
 """Gecikme analizi sekmesi"""
 widget = QWidget()
 layout = QVBoxLayout()

 # Durum kartları
 durum_layout = QHBoxLayout()

 self.gecikmis_kart = self._create_kpi_card(
 " Gecikmiş İşler",
 "0",
 "#e74c3c",
 "Beklenen ilerleme < Gerçek"
 )
 durum_layout.addWidget(self.gecikmis_kart)

 self.riskli_kart = self._create_kpi_card(
 " Riskli İşler",
 "0",
 "#e67e22",
 "Kritik yolda, başlamamış"
 )
 durum_layout.addWidget(self.riskli_kart)

 self.durum_kart = self._create_kpi_card(
 " Genel Durum",
 "Normal",
 "#27ae60",
 "Proje sağlığı"
 )
 durum_layout.addWidget(self.durum_kart)

 layout.addLayout(durum_layout)

 # Analiz butonu
 analiz_btn = QPushButton(" Gecikme Analizi Yap")
 analiz_btn.setStyleSheet("""
 QPushButton {
 background-color: #e74c3c;
 color: white;
 padding: 10px;
 font-size: 12pt;
 font-weight: bold;
 border-radius: 5px;
 }
 QPushButton:hover {
 background-color: #c0392b;
 }
 """)
 analiz_btn.clicked.connect(self.analiz_gecikme)
 layout.addWidget(analiz_btn)

 # Gecikmiş işler
 gecikmis_group = QGroupBox(" Gecikmiş İşler")
 gecikmis_layout = QVBoxLayout()

 self.gecikmis_table = QTableWidget()
 self.gecikmis_table.setColumnCount(5)
 self.gecikmis_table.setHorizontalHeaderLabels([
 "İş Adı", "Beklenen İlerleme (%)", "Gerçek İlerleme (%)", "Fark (%)", "Kritik"
 ])
 self.gecikmis_table.horizontalHeader().setStretchLastSection(True)
 gecikmis_layout.addWidget(self.gecikmis_table)

 gecikmis_group.setLayout(gecikmis_layout)
 layout.addWidget(gecikmis_group)

 # Riskli işler
 riskli_group = QGroupBox(" Riskli İşler (Kritik Yolda)")
 riskli_layout = QVBoxLayout()

 self.riskli_table = QTableWidget()
 self.riskli_table.setColumnCount(3)
 self.riskli_table.setHorizontalHeaderLabels([
 "İş Adı", "Başlaması Gereken", "Gecikme (Gün)"
 ])
 self.riskli_table.horizontalHeader().setStretchLastSection(True)
 riskli_layout.addWidget(self.riskli_table)

 riskli_group.setLayout(riskli_layout)
 layout.addWidget(riskli_group)

 widget.setLayout(layout)
 return widget

 def _create_kpi_card(self, baslik: str, deger: str, renk: str, alt_metin: str) -> QFrame:
 """KPI kartı oluştur"""
 card = QFrame()
 card.setFrameShape(QFrame.Shape.StyledPanel)
 card.setStyleSheet(f"""
 QFrame {{
 background-color: {renk};
 border-radius: 10px;
 padding: 15px;
 }}
 """)

 layout = QVBoxLayout()

 # Başlık
 baslik_label = QLabel(baslik)
 baslik_label.setStyleSheet("color: white; font-size: 11pt; font-weight: bold;")
 baslik_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
 layout.addWidget(baslik_label)

 # Değer
 deger_label = QLabel(deger)
 deger_label.setObjectName("deger_label")
 deger_label.setStyleSheet("color: white; font-size: 22pt; font-weight: bold;")
 deger_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
 layout.addWidget(deger_label)

 # Alt metin
 alt_label = QLabel(alt_metin)
 alt_label.setObjectName("alt_label")
 alt_label.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 9pt;")
 alt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
 layout.addWidget(alt_label)

 card.setLayout(layout)
 return card

 def _add_renk_aciklama(self, layout: QHBoxLayout, renk: str, metin: str):
 """Renk açıklama kutusu ekle"""
 box = QLabel(" ")
 box.setStyleSheet(f"background-color: {renk}; border: 1px solid #ccc; border-radius: 3px;")
 box.setFixedSize(20, 20)
 layout.addWidget(box)

 label = QLabel(metin)
 layout.addWidget(label)

 # Veri yükleme metodları

 def load_projeler(self):
 """Projeleri yükle"""
 try:
 with self.db.get_connection() as conn:
 cursor = conn.cursor()
 cursor.execute("SELECT id, ad FROM projects ORDER BY id DESC")
 projeler = cursor.fetchall()

 self.proje_combo.clear()
 for proje in projeler:
 self.proje_combo.addItem(proje['ad'], proje['id'])

 except Exception as e:
 logger.error(f"Proje yükleme hatası: {e}")
 QMessageBox.warning(self, "Hata", f"Projeler yüklenemedi: {e}")

 def on_proje_changed(self, index: int):
 """Proje değiştiğinde"""
 if index >= 0:
 self.current_project_id = self.proje_combo.itemData(index)

 def yukle_is_listesi(self):
 """İş listesini tabloya yükle"""
 self.is_table.setRowCount(0)

 for task_id, task in self.engine.tasks.items():
 row = self.is_table.rowCount()
 self.is_table.insertRow(row)

 self.is_table.setItem(row, 0, QTableWidgetItem(str(task_id)))
 self.is_table.setItem(row, 1, QTableWidgetItem(task.ad))
 self.is_table.setItem(row, 2, QTableWidgetItem(str(task.sure_gun)))
 self.is_table.setItem(row, 3, QTableWidgetItem(task.kaynak))
 self.is_table.setItem(row, 4, QTableWidgetItem("" if task.milestone else ""))

 # Bağımlılıklar
 deps = []
 for pred_id, dep_type, lag in task.predecessors:
 pred_name = self.engine.tasks[pred_id].ad if pred_id in self.engine.tasks else f"#{pred_id}"
 deps.append(f"{pred_name} ({dep_type})")

 self.is_table.setItem(row, 5, QTableWidgetItem(", ".join(deps) if deps else "-"))

 # İş işlemleri

 def ekle_is(self):
 """Yeni iş ekle"""
 dialog = TaskDialog(self, db=self.db)

 if dialog.exec() == QDialog.DialogCode.Accepted:
 data = dialog.get_task_data()

 task = Task(
 task_id=self.next_task_id,
 ad=data['ad'],
 sure_gun=data['sure_gun'],
 kaynak=data['kaynak'],
 milestone=data['milestone'],
 aciklama=data['aciklama'],
 metraj_kalem_id=data['metraj_kalem_id']
 )

 self.engine.add_task(task)
 self.next_task_id += 1
 self.yukle_is_listesi()

 QMessageBox.information(self, "Başarılı", f"İş eklendi: {task.ad}")

 def duzenle_is(self):
 """Seçili işi düzenle"""
 selected = self.is_table.selectedItems()
 if not selected:
 QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek için bir iş seçin")
 return

 row = selected[0].row()
 task_id = int(self.is_table.item(row, 0).text())

 if task_id not in self.engine.tasks:
 QMessageBox.warning(self, "Hata", "İş bulunamadı")
 return

 task = self.engine.tasks[task_id]
 dialog = TaskDialog(self, task=task, db=self.db)

 if dialog.exec() == QDialog.DialogCode.Accepted:
 data = dialog.get_task_data()

 task.ad = data['ad']
 task.sure_gun = data['sure_gun']
 task.kaynak = data['kaynak']
 task.milestone = data['milestone']
 task.aciklama = data['aciklama']
 task.metraj_kalem_id = data['metraj_kalem_id']

 self.yukle_is_listesi()
 QMessageBox.information(self, "Başarılı", "İş güncellendi")

 def sil_is(self):
 """Seçili işi sil"""
 selected = self.is_table.selectedItems()
 if not selected:
 QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir iş seçin")
 return

 row = selected[0].row()
 task_id = int(self.is_table.item(row, 0).text())

 reply = QMessageBox.question(
 self, "Onay",
 f"'{self.engine.tasks[task_id].ad}' işini silmek istediğinizden emin misiniz?",
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
 )

 if reply == QMessageBox.StandardButton.Yes:
 if task_id in self.engine.tasks:
 del self.engine.tasks[task_id]
 self.yukle_is_listesi()
 QMessageBox.information(self, "Başarılı", "İş silindi")

 def ekle_bagimliluk(self):
 """Bağımlılık ekle"""
 if len(self.engine.tasks) < 2:
 QMessageBox.warning(self, "Uyarı", "Bağımlılık eklemek için en az 2 iş gerekli")
 return

 dialog = DependencyDialog(self, self.engine.tasks)

 if dialog.exec() == QDialog.DialogCode.Accepted:
 data = dialog.get_dependency_data()

 success = self.engine.add_dependency(
 data['onceki_id'],
 data['sonraki_id'],
 data['tip'],
 data['lag']
 )

 if success:
 self.yukle_is_listesi()
 QMessageBox.information(self, "Başarılı", "Bağımlılık eklendi")
 else:
 QMessageBox.warning(self, "Hata", "Bağımlılık eklenemedi (döngüsel bağımlılık olabilir)")

 def hesapla_program(self):
 """İş programını hesapla (CPM)"""
 if not self.engine.tasks:
 QMessageBox.warning(self, "Uyarı", "Hesaplamak için en az bir iş ekleyin")
 return

 # Başlangıç tarihi al
 baslangic_qdate = self.baslangic_date.date()
 baslangic = datetime(baslangic_qdate.year(), baslangic_qdate.month(), baslangic_qdate.day())

 # CPM hesapla
 sonuc = self.engine.calculate_schedule(baslangic)

 if 'error' in sonuc:
 QMessageBox.critical(self, "Hata", sonuc['error'])
 return

 # Sonuçları göster
 QMessageBox.information(
 self, "Hesaplama Başarılı",
 f"""
İş programı hesaplandı!

Toplam Süre: {sonuc['toplam_sure_gun']} iş günü
Başlangıç: {sonuc['proje_baslangic'].strftime('%d.%m.%Y')}
Bitiş: {sonuc['proje_bitis'].strftime('%d.%m.%Y')}

Toplam İş: {sonuc['toplam_is']}
Kritik İş: {sonuc['kritik_is_sayisi']} (%{sonuc['kritik_yuzde']})
Ortalama Float: {sonuc['ortalama_float']} gün
 """
 )

 # Tabloları güncelle
 self.yukle_gantt_chart()
 self.yukle_kritik_yol()
 self.refresh_visual_gantt()

 # What-If görev listesini güncelle
 self.refresh_whatif_gorevler()

 # Uyarı badge'ini güncelle
 self.guncelle_uyari_badge()

 def yukle_gantt_chart(self):
 """Gantt chart tablosunu yükle"""
 timeline = self.engine.get_timeline_data()

 self.gantt_table.setRowCount(0)

 for item in timeline:
 row = self.gantt_table.rowCount()
 self.gantt_table.insertRow(row)

 # İş adı
 ad_item = QTableWidgetItem(item['ad'])
 if item['kritik']:
 ad_item.setBackground(QBrush(QColor("#f39c12")))
 ad_item.setForeground(QBrush(QColor("white")))
 self.gantt_table.setItem(row, 0, ad_item)

 # Tarihler
 self.gantt_table.setItem(row, 1, QTableWidgetItem(item['baslangic'].strftime('%d.%m.%Y')))
 self.gantt_table.setItem(row, 2, QTableWidgetItem(item['bitis'].strftime('%d.%m.%Y')))

 # Süre
 self.gantt_table.setItem(row, 3, QTableWidgetItem(f"{item['sure_gun']} gün"))

 # İlerleme
 ilerleme_item = QTableWidgetItem(f"{item['ilerleme']:.0f}%")
 self.gantt_table.setItem(row, 4, ilerleme_item)

 # Float
 float_item = QTableWidgetItem(f"{item['float_gun']} gün")
 if item['float_gun'] == 0:
 float_item.setBackground(QBrush(QColor("#e74c3c")))
 float_item.setForeground(QBrush(QColor("white")))
 self.gantt_table.setItem(row, 5, float_item)

 # Durum
 durum_item = QTableWidgetItem(item['durum'].replace('_', ' ').title())
 durum_item.setBackground(QBrush(QColor(item['renk'])))
 durum_item.setForeground(QBrush(QColor("white")))
 self.gantt_table.setItem(row, 6, durum_item)

 # Kritik
 kritik_item = QTableWidgetItem(" Kritik" if item['kritik'] else "")
 self.gantt_table.setItem(row, 7, kritik_item)

 # Özet bilgileri güncelle
 if self.engine.proje_baslangic and self.engine.proje_bitis:
 self.toplam_sure_label.setText(
 f"Toplam Süre: {self.engine._calculate_working_days(self.engine.proje_baslangic, self.engine.proje_bitis)} gün"
 )
 self.baslangic_label.setText(f"Başlangıç: {self.engine.proje_baslangic.strftime('%d.%m.%Y')}")
 self.bitis_label.setText(f"Bitiş: {self.engine.proje_bitis.strftime('%d.%m.%Y')}")

 def yukle_kritik_yol(self):
 """Kritik yol analizini yükle"""
 kritik_info = self.engine.get_critical_path_info()

 if 'error' in kritik_info:
 return

 # KPI kartları güncelle
 deger_label = self.kritik_sure_kart.findChild(QLabel, "deger_label")
 if deger_label:
 deger_label.setText(f"{kritik_info['toplam_sure_gun']} gün")

 deger_label = self.kritik_is_kart.findChild(QLabel, "deger_label")
 if deger_label:
 deger_label.setText(str(kritik_info['toplam_is']))

 toplam_is = len(self.engine.tasks)
 yuzde = (kritik_info['toplam_is'] / toplam_is * 100) if toplam_is > 0 else 0
 deger_label = self.kritik_yuzde_kart.findChild(QLabel, "deger_label")
 if deger_label:
 deger_label.setText(f"{yuzde:.1f}%")

 # Kritik yol tablosu
 self.kritik_table.setRowCount(0)

 for task_data in kritik_info['tasks']:
 row = self.kritik_table.rowCount()
 self.kritik_table.insertRow(row)

 self.kritik_table.setItem(row, 0, QTableWidgetItem(task_data['ad']))
 self.kritik_table.setItem(row, 1, QTableWidgetItem(task_data['baslangic'].strftime('%d.%m.%Y')))
 self.kritik_table.setItem(row, 2, QTableWidgetItem(task_data['bitis'].strftime('%d.%m.%Y')))
 self.kritik_table.setItem(row, 3, QTableWidgetItem(str(task_data['sure_gun'])))
 self.kritik_table.setItem(row, 4, QTableWidgetItem(f"{task_data['ilerleme']:.0f}"))

 durum = "Tamamlandı" if task_data['ilerleme'] >= 100 else \
 "Devam Ediyor" if task_data['ilerleme'] > 0 else "Başlanmadı"
 self.kritik_table.setItem(row, 5, QTableWidgetItem(durum))

 # Float analiz tablosu
 self.float_table.setRowCount(0)

 for task in sorted(self.engine.tasks.values(), key=lambda t: t.float_gun):
 row = self.float_table.rowCount()
 self.float_table.insertRow(row)

 self.float_table.setItem(row, 0, QTableWidgetItem(task.ad))
 self.float_table.setItem(row, 1, QTableWidgetItem(task.early_start.strftime('%d.%m.%Y') if task.early_start else '-'))
 self.float_table.setItem(row, 2, QTableWidgetItem(task.late_start.strftime('%d.%m.%Y') if task.late_start else '-'))
 self.float_table.setItem(row, 3, QTableWidgetItem(task.early_finish.strftime('%d.%m.%Y') if task.early_finish else '-'))
 self.float_table.setItem(row, 4, QTableWidgetItem(task.late_finish.strftime('%d.%m.%Y') if task.late_finish else '-'))

 float_item = QTableWidgetItem(f"{task.float_gun} gün")
 if task.float_gun == 0:
 float_item.setBackground(QBrush(QColor("#e74c3c")))
 float_item.setForeground(QBrush(QColor("white")))
 self.float_table.setItem(row, 5, float_item)

 self.float_table.setItem(row, 6, QTableWidgetItem("" if task.kritik else ""))

 def analiz_gecikme(self):
 """Gecikme analizi yap"""
 analiz = self.engine.analyze_delays()

 # KPI kartları güncelle
 deger_label = self.gecikmis_kart.findChild(QLabel, "deger_label")
 if deger_label:
 deger_label.setText(str(analiz['gecikmis_is_sayisi']))

 deger_label = self.riskli_kart.findChild(QLabel, "deger_label")
 if deger_label:
 deger_label.setText(str(analiz['riskli_is_sayisi']))

 deger_label = self.durum_kart.findChild(QLabel, "deger_label")
 alt_label = self.durum_kart.findChild(QLabel, "alt_label")
 if deger_label and alt_label:
 durum = analiz['genel_durum'].title()
 deger_label.setText(durum)

 # Renk değiştir
 renk = {
 'Kritik': '#e74c3c',
 'Dikkat': '#e67e22',
 'Normal': '#27ae60'
 }.get(durum, '#27ae60')

 self.durum_kart.setStyleSheet(f"""
 QFrame {{
 background-color: {renk};
 border-radius: 10px;
 padding: 15px;
 }}
 """)

 # Gecikmiş işler tablosu
 self.gecikmis_table.setRowCount(0)

 for task in analiz['gecikmis_tasks']:
 row = self.gecikmis_table.rowCount()
 self.gecikmis_table.insertRow(row)

 self.gecikmis_table.setItem(row, 0, QTableWidgetItem(task['ad']))
 self.gecikmis_table.setItem(row, 1, QTableWidgetItem(f"{task['beklenen_ilerleme']:.1f}"))
 self.gecikmis_table.setItem(row, 2, QTableWidgetItem(f"{task['gercek_ilerleme']:.1f}"))
 self.gecikmis_table.setItem(row, 3, QTableWidgetItem(f"{task['fark']:.1f}"))

 kritik_item = QTableWidgetItem(" Kritik" if task['kritik'] else "")
 if task['kritik']:
 kritik_item.setBackground(QBrush(QColor("#e74c3c")))
 kritik_item.setForeground(QBrush(QColor("white")))
 self.gecikmis_table.setItem(row, 4, kritik_item)

 # Riskli işler tablosu
 self.riskli_table.setRowCount(0)

 for task in analiz['riskli_tasks']:
 row = self.riskli_table.rowCount()
 self.riskli_table.insertRow(row)

 self.riskli_table.setItem(row, 0, QTableWidgetItem(task['ad']))
 self.riskli_table.setItem(row, 1, QTableWidgetItem(task['baslamali'].strftime('%d.%m.%Y')))
 self.riskli_table.setItem(row, 2, QTableWidgetItem(f"{task['gecikme_gun']} gün"))

 QMessageBox.information(
 self, "Gecikme Analizi",
 f"""
Analiz tarihi: {analiz['bugun'].strftime('%d.%m.%Y')}

Gecikmiş İş: {analiz['gecikmis_is_sayisi']}
Riskli İş: {analiz['riskli_is_sayisi']}

Genel Durum: {analiz['genel_durum'].upper()}
 """
 )

 # ==================== S-CURVE SEKMESİ ====================

 def _create_s_curve_tab(self) -> QWidget:
 """S-Curve (S Eğrisi) sekmesi"""
 widget = QWidget()
 layout = QVBoxLayout()

 # Başlık ve açıklama
 baslik = QLabel(" S-Curve (S Eğrisi) Analizi")
 baslik.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2c3e50;")
 layout.addWidget(baslik)

 aciklama = QLabel("Planlanan (PV) vs Gerçekleşen (EV) ilerleme karşılaştırması")
 aciklama.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
 layout.addWidget(aciklama)

 # Kontrol butonları
 kontrol_layout = QHBoxLayout()

 yenile_btn = QPushButton(" S-Curve Güncelle")
 yenile_btn.setStyleSheet("""
 QPushButton {
 background-color: #3498db;
 color: white;
 padding: 10px 20px;
 font-size: 11pt;
 font-weight: bold;
 border-radius: 5px;
 }
 QPushButton:hover { background-color: #2980b9; }
 """)
 yenile_btn.clicked.connect(self.refresh_s_curve)
 kontrol_layout.addWidget(yenile_btn)

 kontrol_layout.addStretch()
 layout.addLayout(kontrol_layout)

 # S-Curve Widget
 self.s_curve_widget = SCurveWidget()
 self.s_curve_widget.setMinimumHeight(400)
 layout.addWidget(self.s_curve_widget)

 # Özet bilgiler
 ozet_group = QGroupBox(" Özet")
 ozet_layout = QHBoxLayout()

 self.scurve_planlanan_label = QLabel("Planlanan: -%")
 self.scurve_planlanan_label.setStyleSheet("font-size: 12pt; color: #3498db;")
 ozet_layout.addWidget(self.scurve_planlanan_label)

 self.scurve_gerceklesen_label = QLabel("Gerçekleşen: -%")
 self.scurve_gerceklesen_label.setStyleSheet("font-size: 12pt; color: #27ae60;")
 ozet_layout.addWidget(self.scurve_gerceklesen_label)

 self.scurve_fark_label = QLabel("Fark: -%")
 self.scurve_fark_label.setStyleSheet("font-size: 12pt; color: #e74c3c;")
 ozet_layout.addWidget(self.scurve_fark_label)

 ozet_layout.addStretch()
 ozet_group.setLayout(ozet_layout)
 layout.addWidget(ozet_group)

 widget.setLayout(layout)
 return widget

 def refresh_s_curve(self):
 """S-Curve grafiğini güncelle"""
 if not self.engine.tasks:
 QMessageBox.warning(self, "Uyarı", "Önce iş programını oluşturun ve hesaplayın")
 return

 data = self.engine.get_s_curve_data()

 if 'error' in data:
 QMessageBox.warning(self, "Uyarı", data['error'])
 return

 self.s_curve_widget.draw_s_curve(data)

 # Özet bilgileri güncelle
 planlanan = data.get('planlanan', [])
 gerceklesen = data.get('gerceklesen', [])

 if planlanan:
 # Bugüne kadarki planlanan
 bugun_idx = min(len(planlanan) - 1, (datetime.now() - data['proje_baslangic']).days)
 if 0 <= bugun_idx < len(planlanan):
 planlanan_yuzde = planlanan[bugun_idx]
 self.scurve_planlanan_label.setText(f"Planlanan: %{planlanan_yuzde:.1f}")

 if gerceklesen:
 gercek_values = [v for v in gerceklesen if v is not None]
 if gercek_values:
 gercek_yuzde = gercek_values[-1]
 self.scurve_gerceklesen_label.setText(f"Gerçekleşen: %{gercek_yuzde:.1f}")

 # Fark
 if planlanan and 0 <= bugun_idx < len(planlanan):
 fark = gercek_yuzde - planlanan[bugun_idx]
 renk = '#27ae60' if fark >= 0 else '#e74c3c'
 self.scurve_fark_label.setText(f"Fark: %{fark:+.1f}")
 self.scurve_fark_label.setStyleSheet(f"font-size: 12pt; color: {renk};")

 # ==================== WHAT-IF SEKMESİ ====================

 def _create_what_if_tab(self) -> QWidget:
 """What-If Analizi sekmesi"""
 widget = QWidget()
 layout = QVBoxLayout()

 # Başlık
 baslik = QLabel(" What-If Senaryo Analizi")
 baslik.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2c3e50;")
 layout.addWidget(baslik)

 aciklama = QLabel("\"Ya şu görev X gün gecikirse?\" simülasyonu yapın.")
 aciklama.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
 layout.addWidget(aciklama)

 # Senaryo oluşturma
 senaryo_group = QGroupBox(" Senaryo Oluştur")
 senaryo_layout = QFormLayout()

 # Görev seçimi
 self.whatif_gorev_combo = QComboBox()
 self.whatif_gorev_combo.setMinimumWidth(300)
 senaryo_layout.addRow("Görev Seç:", self.whatif_gorev_combo)

 # Gecikme gün sayısı
 self.whatif_gecikme_spin = QSpinBox()
 self.whatif_gecikme_spin.setRange(1, 365)
 self.whatif_gecikme_spin.setValue(5)
 self.whatif_gecikme_spin.setSuffix(" gün")
 senaryo_layout.addRow("Gecikme Süresi:", self.whatif_gecikme_spin)

 # Simüle et butonu
 simule_btn = QPushButton(" Simüle Et")
 simule_btn.setStyleSheet("""
 QPushButton {
 background-color: #9b59b6;
 color: white;
 padding: 10px 20px;
 font-size: 11pt;
 font-weight: bold;
 border-radius: 5px;
 }
 QPushButton:hover { background-color: #8e44ad; }
 """)
 simule_btn.clicked.connect(self.calistir_what_if)
 senaryo_layout.addRow("", simule_btn)

 senaryo_group.setLayout(senaryo_layout)
 layout.addWidget(senaryo_group)

 # Son senaryo sonucu
 sonuc_group = QGroupBox(" Son Senaryo Sonucu")
 sonuc_layout = QVBoxLayout()

 self.whatif_sonuc_label = QLabel("Henüz bir senaryo simüle edilmedi.")
 self.whatif_sonuc_label.setWordWrap(True)
 self.whatif_sonuc_label.setStyleSheet("font-size: 11pt; padding: 10px; background-color: #f9f9f9; border-radius: 5px;")
 sonuc_layout.addWidget(self.whatif_sonuc_label)

 # Etkilenen görevler tablosu
 self.whatif_table = QTableWidget()
 self.whatif_table.setColumnCount(5)
 self.whatif_table.setHorizontalHeaderLabels([
 "Görev", "Eski Başlangıç", "Yeni Başlangıç", "Eski Bitiş", "Yeni Bitiş"
 ])
 self.whatif_table.horizontalHeader().setStretchLastSection(True)
 sonuc_layout.addWidget(self.whatif_table)

 sonuc_group.setLayout(sonuc_layout)
 layout.addWidget(sonuc_group)

 widget.setLayout(layout)
 return widget

 def refresh_whatif_gorevler(self):
 """What-If görev listesini güncelle"""
 self.whatif_gorev_combo.clear()

 for task_id, task in self.engine.tasks.items():
 label = f"{task.ad}"
 if task.kritik:
 label += " "
 self.whatif_gorev_combo.addItem(label, task_id)

 def calistir_what_if(self):
 """What-If analizini çalıştır"""
 if not self.engine.tasks:
 QMessageBox.warning(self, "Uyarı", "Önce iş programını oluşturun")
 return

 task_id = self.whatif_gorev_combo.currentData()
 if task_id is None:
 QMessageBox.warning(self, "Uyarı", "Lütfen bir görev seçin")
 return

 gecikme_gun = self.whatif_gecikme_spin.value()

 # Analizi çalıştır
 sonuc = self.engine.what_if_analysis(task_id, gecikme_gun)

 if 'error' in sonuc:
 QMessageBox.warning(self, "Hata", sonuc['error'])
 return

 # Sonucu göster
 self._goster_whatif_sonuc(sonuc)

 def _goster_whatif_sonuc(self, sonuc: Dict[str, Any]):
 """What-If sonucunu göster"""
 # Özet metin
 proje_gecikme = sonuc.get('proje_gecikme_gun', 0)
 kritik_degisti = sonuc.get('kritik_yol_degisti', False)

 renk = '#e74c3c' if proje_gecikme > 0 else '#27ae60'
 kritik_text = '<span style="color: #e74c3c">EVET</span>' if kritik_degisti else '<span style="color: #27ae60">HAYIR</span>'

 ozet_html = f"""
<b>Senaryo:</b> {sonuc.get('geciktirilen_gorev', '-')} görevinin {sonuc.get('gecikme_gun', 0)} gün gecikmesi<br><br>
<b>Proje Bitiş:</b> {sonuc.get('eski_proje_bitis', '-')} → <span style="color: {renk}">{sonuc.get('yeni_proje_bitis', '-')}</span><br>
<b>Proje Gecikmesi:</b> <span style="color: {renk}">{proje_gecikme} gün</span><br>
<b>Etkilenen Görev:</b> {sonuc.get('etkilenen_gorev_sayisi', 0)}<br>
<b>Kritik Yol Değişti:</b> {kritik_text}
 """
 self.whatif_sonuc_label.setText(ozet_html)

 # Tablo güncelle
 self.whatif_table.setRowCount(0)

 for gorev in sonuc.get('etkilenen_gorevler', []):
 row = self.whatif_table.rowCount()
 self.whatif_table.insertRow(row)

 self.whatif_table.setItem(row, 0, QTableWidgetItem(gorev['ad']))
 self.whatif_table.setItem(row, 1, QTableWidgetItem(gorev['eski_baslangic']))
 self.whatif_table.setItem(row, 2, QTableWidgetItem(gorev['yeni_baslangic']))
 self.whatif_table.setItem(row, 3, QTableWidgetItem(gorev['eski_bitis']))
 self.whatif_table.setItem(row, 4, QTableWidgetItem(gorev['yeni_bitis']))

 # Detaylı sonuç dialog'u
 dialog = WhatIfResultDialog(self, sonuc)
 dialog.exec()

 # ==================== ŞABLON VE UYARI METODLARI ====================

 def goster_sablon_dialog(self):
 """Şablon seçim dialog'unu göster"""
 dialog = TemplateDialog(self)

 if dialog.exec() == QDialog.DialogCode.Accepted:
 template_id = dialog.get_selected_template()
 start_date = dialog.get_start_date()

 if template_id:
 sonuc = self.engine.load_template(template_id, start_date)

 if sonuc.get('success'):
 self.yukle_is_listesi()
 # Task ID'leri güncelle
 if self.engine.tasks:
 self.next_task_id = max(self.engine.tasks.keys()) + 1
 QMessageBox.information(
 self, "Başarılı",
 f"{sonuc.get('sablon_adi', 'Şablon')} eklendi.\n{sonuc.get('eklenen_gorev', 0)} görev eklendi."
 )
 else:
 QMessageBox.warning(self, "Hata", sonuc.get('error', 'Bilinmeyen hata'))

 def goster_uyarilar(self):
 """Uyarılar panelini göster"""
 alerts = self.engine.get_alerts()

 if not alerts:
 QMessageBox.information(self, "Bilgi", "Aktif uyarı bulunmuyor. ")
 return

 # Uyarı sayısını buton üzerinde göster
 ozet = self.engine.get_alert_summary()
 toplam = ozet.get('toplam', 0)
 if toplam > 0:
 self.alerts_btn.setText(f" Uyarılar ({toplam})")
 else:
 self.alerts_btn.setText(" Uyarılar")

 # Panel göster
 panel = AlertsPanel(self, alerts)
 panel.show()

 def guncelle_uyari_badge(self):
 """Uyarı badge'ini güncelle"""
 if hasattr(self, 'alerts_btn'):
 ozet = self.engine.get_alert_summary()
 toplam = ozet.get('toplam', 0)
 kritik = ozet.get('kritik', 0)

 if kritik > 0:
 self.alerts_btn.setText(f" Uyarılar ({toplam}) ")
 self.alerts_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 5px 10px; border-radius: 3px;")
 elif toplam > 0:
 self.alerts_btn.setText(f" Uyarılar ({toplam})")
 self.alerts_btn.setStyleSheet("background-color: #f39c12; color: white; padding: 5px 10px; border-radius: 3px;")
 else:
 self.alerts_btn.setText(" Uyarılar")
 self.alerts_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 5px 10px; border-radius: 3px;")

 # ==================== DRAG & DROP ====================

 def toggle_drag_drop(self, state):
 """Drag & Drop'u aç/kapat"""
 if hasattr(self, 'gantt_view'):
 self.gantt_view.drag_enabled = (state == Qt.CheckState.Checked.value)
 self.refresh_visual_gantt()

 def on_task_dragged(self, task_id: int, gun_farki: int):
 """Görev sürüklendiğinde çağrılır"""
 if task_id not in self.engine.tasks:
 return

 task = self.engine.tasks[task_id]

 # Yeni tarih hesapla
 if not task.early_start:
 return

 yeni_baslangic = task.early_start + timedelta(days=gun_farki)
 cascade_aktif = self.cascade_check.isChecked()

 # Onay dialog'u
 cascade_mesaj = "\n\nOtomatik Kaydır: AÇIK - Bağımlı görevler de kaydırılacak." if cascade_aktif else ""
 reply = QMessageBox.question(
 self, "Görev Taşı",
 f"'{task.ad}' görevini {gun_farki:+d} gün kaydırmak istediğinizden emin misiniz?\n\n"
 f"Eski başlangıç: {task.early_start.strftime('%d.%m.%Y')}\n"
 f"Yeni başlangıç: {yeni_baslangic.strftime('%d.%m.%Y')}"
 f"{cascade_mesaj}",
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
 )

 if reply == QMessageBox.StandardButton.Yes:
 # Engine'deki move_task metodunu kullan
 sonuc = self.engine.move_task(task_id, yeni_baslangic)

 if sonuc.get('success'):
 # Uyarı varsa göster
 if sonuc.get('uyari'):
 QMessageBox.warning(self, "Uyarı", sonuc['uyari'])

 # Otomatik cascade aktifse bağımlı görevleri de kaydır
 cascade_bilgi = ""
 if cascade_aktif:
 cascade_sonuc = self.engine.cascade_dependents(task_id, gun_farki)
 if cascade_sonuc.get('success') and cascade_sonuc.get('kaydirilan_sayisi', 0) > 0:
 cascade_bilgi = f"\n\nOtomatik kaydırılan görevler ({cascade_sonuc['kaydirilan_sayisi']}):\n"
 for g in cascade_sonuc['kaydirilan_gorevler'][:5]: # İlk 5'i göster
 cascade_bilgi += f" - {g['ad']}\n"
 if cascade_sonuc['kaydirilan_sayisi'] > 5:
 cascade_bilgi += f" ... ve {cascade_sonuc['kaydirilan_sayisi'] - 5} görev daha"

 # Görünümleri güncelle
 self.refresh_visual_gantt()
 self.yukle_gantt_chart()

 QMessageBox.information(
 self, "Başarılı",
 f"Görev taşındı.\n"
 f"Yeni başlangıç: {sonuc['yeni_baslangic'].strftime('%d.%m.%Y')}\n"
 f"Kalan float: {sonuc['yeni_float']} gün"
 f"{cascade_bilgi}"
 )
 else:
 QMessageBox.warning(self, "Hata", sonuc.get('error', 'Taşıma başarısız'))
 self.refresh_visual_gantt() # Geri al
 else:
 # İptal edildi, görünümü yenile
 self.refresh_visual_gantt()

 # ==================== KAYNAK DENGELEME ====================

 def otomatik_kaynak_dengele(self):
 """Otomatik kaynak dengeleme"""
 if not self.engine.tasks:
 QMessageBox.warning(self, "Uyarı", "Önce iş programını oluşturun")
 return

 # Önce mevcut çakışmaları kontrol et
 cakismalar = self.engine.check_kaynak_cakisma()

 if not cakismalar:
 QMessageBox.information(self, "Bilgi", "Kaynak çakışması bulunmuyor. ")
 return

 # Onay al
 reply = QMessageBox.question(
 self, "Kaynak Dengeleme",
 f"{len(cakismalar)} adet kaynak çakışması tespit edildi.\n\n"
 "Otomatik dengeleme yapılsın mı?\n"
 "(Kritik olmayan görevler float aralığında kaydırılacak)",
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
 )

 if reply == QMessageBox.StandardButton.Yes:
 sonuc = self.engine.resource_leveling()

 if sonuc.get('success'):
 # Sonuç dialog'u
 mesaj = f"""
Kaynak Dengeleme Tamamlandı!

 Çözülen Çakışma: {sonuc.get('cozulen_cakisma', 0)}
 Kalan Çakışma: {sonuc.get('kalan_cakisma', 0)}

Yapılan Değişiklikler:
"""
 for deg in sonuc.get('degisiklikler', [])[:5]: # İlk 5
 mesaj += f"\n• {deg['ad']}: {deg['eski_baslangic']} → {deg['yeni_baslangic']}"

 if len(sonuc.get('degisiklikler', [])) > 5:
 mesaj += f"\n... ve {len(sonuc['degisiklikler']) - 5} değişiklik daha"

 QMessageBox.information(self, "Sonuç", mesaj)

 # Görünümleri güncelle
 self.refresh_visual_gantt()
 self.yukle_gantt_chart()
 self.kontrol_kaynak_cakisma()
 else:
 QMessageBox.warning(self, "Hata", sonuc.get('error', 'Dengeleme başarısız'))

 def kaydet_program(self):
 """İş programını kaydet"""
 if not self.current_project_id:
 QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
 return

 if not self.engine.tasks:
 QMessageBox.warning(self, "Uyarı", "Kaydedilecek iş yok")
 return

 sonuc = self.engine.save_to_database(self.current_project_id)

 if sonuc['success']:
 QMessageBox.information(self, "Başarılı", "İş programı kaydedildi")
 else:
 QMessageBox.critical(self, "Hata", f"Kayıt başarısız: {sonuc['error']}")

 def yukle_program(self):
 """İş programını yükle"""
 if not self.current_project_id:
 QMessageBox.warning(self, "Uyarı", "Lütfen önce bir proje seçin")
 return

 sonuc = self.engine.load_from_database(self.current_project_id)

 if sonuc['success']:
 self.yukle_is_listesi()
 self.yukle_gantt_chart()
 self.yukle_kritik_yol()
 QMessageBox.information(self, "Başarılı", f"İş programı yüklendi ({sonuc['toplam_is']} iş)")
 else:
 QMessageBox.warning(self, "Bilgi", sonuc['error'])
