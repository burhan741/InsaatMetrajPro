"""
Akıllı Metraj Analizi Penceresi
"""

import logging
import math
import re
from pathlib import Path
from typing import Optional, List, Dict
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QSplitter,
    QComboBox, QMessageBox, QHeaderView, QFrame, QFileDialog,
    QDialog, QListWidget, QListWidgetItem, QCheckBox, QDialogButtonBox,
    QTabWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

try:
    import ezdxf
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False
    ezdxf = None

# Shapely kutuphanesi (daha hassas geometrik islemler icin)
try:
    from shapely.geometry import Polygon as ShapelyPolygon, box as shapely_box
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    ShapelyPolygon = None

# Excel export icin pandas
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

# AutoCAD canlı bağlantı (COM Automation)
try:
    from app.core.autocad_connector import (
        AutoCADConnector, MetrajObjesi, DemirBilgisi, AcadColor
    )
    AUTOCAD_AVAILABLE = True
except ImportError:
    AUTOCAD_AVAILABLE = False
    AutoCADConnector = None
    MetrajObjesi = None
    DemirBilgisi = None

logger = logging.getLogger(__name__)


class SimplePolygon:
    """Shapely yerine basit dikdortgen sinifi (fallback)"""

    def __init__(self, coords):
        """coords: [(x1,y1), (x2,y2), (x3,y3), (x4,y4)] formatinda"""
        self.coords = coords
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        self.min_x = min(xs)
        self.max_x = max(xs)
        self.min_y = min(ys)
        self.max_y = max(ys)

    @property
    def bounds(self):
        return (self.min_x, self.min_y, self.max_x, self.max_y)

    @property
    def area(self):
        """Shoelace formuluyle alan hesapla"""
        n = len(self.coords)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.coords[i][0] * self.coords[j][1]
            area -= self.coords[j][0] * self.coords[i][1]
        return abs(area) / 2.0

    @property
    def length(self):
        """Cevre hesapla (tum kenarlarin toplami)"""
        n = len(self.coords)
        cevre = 0.0
        for i in range(n):
            j = (i + 1) % n
            dx = self.coords[j][0] - self.coords[i][0]
            dy = self.coords[j][1] - self.coords[i][1]
            cevre += math.sqrt(dx*dx + dy*dy)
        return cevre

    @property
    def centroid(self):
        class Point:
            def __init__(self, x, y):
                self.x = x
                self.y = y
        return Point((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)

    @property
    def exterior(self):
        class Exterior:
            def __init__(self, coords):
                self._coords = coords + [coords[0]]  # Close the polygon
            @property
            def xy(self):
                return ([c[0] for c in self._coords], [c[1] for c in self._coords])
        ext = Exterior(self.coords)
        return ext

    def intersects(self, other):
        """Basit AABB (Axis-Aligned Bounding Box) kesisim kontrolu"""
        # Iki dikdortgen kesisiyor mu?
        if self.max_x < other.min_x or other.max_x < self.min_x:
            return False
        if self.max_y < other.min_y or other.max_y < self.min_y:
            return False
        return True

    def contains(self, other):
        """Basit icerik kontrolu - other bu polygon icinde mi?"""
        return (self.min_x <= other.min_x and self.max_x >= other.max_x and
                self.min_y <= other.min_y and self.max_y >= other.max_y)


def create_polygon(coords):
    """Shapely varsa ShapelyPolygon, yoksa SimplePolygon olustur"""
    if SHAPELY_AVAILABLE:
        return ShapelyPolygon(coords)
    return SimplePolygon(coords)


def create_box(min_x, min_y, max_x, max_y):
    """Shapely varsa box, yoksa SimplePolygon olustur"""
    if SHAPELY_AVAILABLE:
        return shapely_box(min_x, min_y, max_x, max_y)
    return SimplePolygon([
        (min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)
    ])


# Varsayilan Polygon sinifi
Polygon = SimplePolygon


# --- DUVAR MALZEME SARFIYAT VERİTABANI ---
# Duvar cinsi ve kalınlığa göre m2 başına adet
# STANDART KALINLIKLAR: 10, 15, 20 cm (diğer değerler en yakın standarta yuvarlanır)
# Format: {duvar_cinsi: {kalinlik_cm: adet_m2}}
DUVAR_MALZEME_SARFIYAT = {
    "Tuğla": {
        10: 22,     # 10 cm tuğla: ~22 adet/m²
        15: 28,     # 15 cm tuğla: ~28 adet/m²
        20: 32,     # 20 cm tuğla: ~32 adet/m²
    },
    "Bims": {
        10: 12,     # 10 cm bims: ~12 adet/m²
        15: 13,     # 15 cm bims: ~13 adet/m²
        20: 13,     # 20 cm bims: ~13 adet/m²
    },
    "Ytong": {
        10: 6.25,   # 10 cm ytong: ~6.25 adet/m² (60x25 blok)
        15: 6.25,   # 15 cm ytong: ~6.25 adet/m²
        20: 6.25,   # 20 cm ytong: ~6.25 adet/m²
    },
    "Gazbeton": {
        10: 6.25,   # 10 cm gazbeton: ~6.25 adet/m² (60x25 blok)
        15: 6.25,   # 15 cm gazbeton: ~6.25 adet/m²
        20: 6.25,   # 20 cm gazbeton: ~6.25 adet/m²
    },
}

# Standart duvar kalınlıkları (yuvarlama için)
STANDART_DUVAR_KALINLIKLARI = [10, 15, 20]

# Duvar cinsi listesi (UI için)
DUVAR_CINSLERI = ["Tuğla", "Bims", "Ytong", "Gazbeton"]


def standart_kalinliga_yuvarla(kalinlik: int) -> int:
    """
    Duvar kalınlığını en yakın standart değere yuvarlar.

    Standart kalınlıklar: 10, 15, 20 cm
    Örnek:
        9 cm -> 10 cm
        12 cm -> 10 cm (10'a daha yakın)
        13 cm -> 15 cm (15'e daha yakın)
        18 cm -> 20 cm
        19 cm -> 20 cm

    Args:
        kalinlik: Bulunan kalınlık değeri (cm)

    Returns:
        int: Standart kalınlık (10, 15 veya 20)
    """
    # En yakın standart kalınlığı bul
    en_yakin = min(STANDART_DUVAR_KALINLIKLARI, key=lambda x: abs(x - kalinlik))
    return en_yakin

# --- SARFİYAT VERİTABANI (m2 başına tüketim) ---
# Format: "Malzeme Adı": [m2_basina_tuketim, paket_agirligi, paket_turu, malzeme_turu]
SARFIYATLAR = {
    # --- ALÇI GRUBU (DUVAR/TAVAN KATMANLARI) ---
    # 1. KAT: Kaba (Perlitli) Alçı
    "Kaba Alçı":          [10.0, 35, "Torba (35kg)", "Toz"],

    # 2. KAT: Karışık (Kırma) Katmanı (Yarı Yarıya karışım)
    "Karışık İçin Sıva":  [0.5, 35, "Torba (35kg)", "Toz"],
    "Karışık İçin Saten": [0.5, 30, "Torba (30kg)", "Toz"],

    # 3. KAT: Son Kat Saten (Macun)
    "Saten Alçı":         [0.3, 30, "Torba (30kg)", "Toz"],

    # --- SIVA & ŞAP GRUBU (KUM VE ÇİMENTO AYRILDI) ---
    # Duvar Sıvası (Kara Sıva - Islak Hacimler)
    "Sıva Çimentosu":     [10.0, 50, "Torba (Çimento)", "Kaba"],
    "Sıva Kumu":          [0.025, 1, "m3 (Kepçe)", "Kaba"],

    # Zemin Şapı
    "Şap Çimentosu":      [15.0, 50, "Torba (Çimento)", "Kaba"],
    "Şap Kumu":           [0.06, 1, "m3 (Kepçe)", "Kaba"],

    # --- BOYA GRUBU ---
    "Duvar Boyası":       [0.30, 15, "Kova (15L)", "Sıvı"],
    "Tavan Boyası":       [0.25, 17.5, "Kova (17.5kg)", "Sıvı"],

    # --- SERAMİK & YAPIŞTIRICI ---
    "Yer Fayansı + Derz":     [1.05, 1, "m2 (Fireli)", "Kaplama"],
    "Duvar Fayansı + Derz":   [1.05, 1, "m2 (Fireli)", "Kaplama"],
    "Fayans Yapıştırıcı":     [4.5, 25, "Torba (25kg)", "Toz"],
    "Derz Dolgu":             [0.5, 20, "Torba (20kg)", "Toz"],
    "Tezgah Arası Seramik":   [1.05, 1, "m2 (Fireli)", "Kaplama"],

    # --- PARKE GRUBU ---
    "Laminat Parke":      [1.05, 1.8, "Paket (1.8m2)", "Kaplama"],
    "Parke Altı Şilte":   [1.0, 10, "Top (10m2)", "Rulo"],

    # --- SÜPÜRGELİK ---
    "Seramik Süpürgelik":       [1.05, 1, "mtul (Fireli)", "Kaplama"],
    "Ahşap/Laminat Süpürgelik": [1.05, 2.4, "Paket (2.4m)", "Profil"],
}

# TEFRİŞ BLOK SÖZLÜĞÜ (DXF'den sayılacak objeler)
TEFRIS_SOZLUGU = {
    "KLOZET": "Asma Klozet (Set)",
    "WC": "Asma Klozet (Set)",
    "GOMME": "Gömme Rezervuar",
    "LAVABO": "Hilton Lavabo",
    "EVYE": "Mutfak Eviyesi",
    "DUS": "Duş Kabini",
    "KABIN": "Duş Kabini",
    "KUSET": "Küvet",
    "PRIZ": "Elektrik Prizi",
    "ANAHTAR": "Aydınlatma Anahtarı",
    "KOMBI": "Kombi",
    "RADYATOR": "Panel Radyatör",
    "SPLIT": "Klima İç Ünite",
}


# --- İMALAT REÇETELERİ (AKILLI SİSTEM) ---
def recete_getir(oda_ismi: str) -> Dict:
    """Oda ismine göre imalat reçetesi döndürür"""
    isim = oda_ismi.upper() if oda_ismi else ""

    # 1. ISLAK HACİMLER (Banyo, WC, Duş) -> Kara Sıva + Fayans
    if any(x in isim for x in ["BANYO", "WC", "DUS", "TUVALET", "EBEVEYN", "ISLAK"]):
        return {
            "TUR": "ISLAK",
            "RENK": "#3498db",  # Mavi
            "ZEMIN": ["Şap Çimentosu", "Şap Kumu", "Yer Fayansı + Derz", "Fayans Yapıştırıcı", "Derz Dolgu"],
            "DUVAR": ["Sıva Çimentosu", "Sıva Kumu", "Duvar Fayansı + Derz", "Fayans Yapıştırıcı", "Derz Dolgu"],
            "TAVAN": ["Asma Tavan (Yeşil Alçıpan + Profil)"],
            "SUPURGELIK": None,
            "EKSTRA": []
        }

    # 2. MUTFAK -> Alçı + Boya + Seramik Zemin
    elif "MUTFAK" in isim:
        return {
            "TUR": "MUTFAK",
            "RENK": "#e67e22",  # Turuncu
            "ZEMIN": ["Şap Çimentosu", "Şap Kumu", "Yer Fayansı + Derz", "Fayans Yapıştırıcı", "Derz Dolgu"],
            "DUVAR": ["Kaba Alçı", "Karışık İçin Sıva", "Karışık İçin Saten", "Saten Alçı", "Duvar Boyası"],
            "TAVAN": ["Kaba Alçı", "Karışık İçin Sıva", "Karışık İçin Saten", "Saten Alçı", "Tavan Boyası"],
            "SUPURGELIK": "Seramik Süpürgelik",
            "EKSTRA": ["Tezgah Arası Seramik"]
        }

    # 3. KORİDOR / ANTRE / HOL -> Alçı + Boya + Seramik Zemin
    elif any(x in isim for x in ["KORIDOR", "ANTRE", "HOL", "GIRIS"]):
        return {
            "TUR": "KORIDOR",
            "RENK": "#9b59b6",  # Mor
            "ZEMIN": ["Şap Çimentosu", "Şap Kumu", "Yer Fayansı + Derz", "Fayans Yapıştırıcı", "Derz Dolgu"],
            "DUVAR": ["Kaba Alçı", "Karışık İçin Sıva", "Karışık İçin Saten", "Saten Alçı", "Duvar Boyası"],
            "TAVAN": ["Kaba Alçı", "Karışık İçin Sıva", "Karışık İçin Saten", "Saten Alçı", "Tavan Boyası"],
            "SUPURGELIK": "Seramik Süpürgelik",
            "EKSTRA": []
        }

    # 4. KURU HACİMLER (Salon, Oda, Yatak Odası) -> Alçı + Boya + Parke
    else:
        return {
            "TUR": "KURU",
            "RENK": "#f1c40f",  # Sarı
            "ZEMIN": ["Şap Çimentosu", "Şap Kumu", "Parke Altı Şilte", "Laminat Parke"],
            "DUVAR": ["Kaba Alçı", "Karışık İçin Sıva", "Karışık İçin Saten", "Saten Alçı", "Duvar Boyası"],
            "TAVAN": ["Kaba Alçı", "Karışık İçin Sıva", "Karışık İçin Saten", "Saten Alçı", "Tavan Boyası"],
            "SUPURGELIK": "Ahşap/Laminat Süpürgelik",
            "EKSTRA": []
        }


class MatplotlibCanvas(FigureCanvas):
    """Matplotlib canvas for PyQt6 - Modern Dark Theme"""

    def __init__(self, parent=None, width=8, height=8, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.fig.patch.set_facecolor('#2b2b3d')  # Koyu lacivert-gri
        self.axes.set_facecolor('#2b2b3d')
        self.setStyleSheet("background-color: #2b2b3d;")


class MetrajAnalizWindow(QMainWindow):
    """Akilli Metraj Analizi Ana Penceresi"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Akıllı Metraj Analizi")
        self.setMinimumSize(1400, 900)

        # Veri listeleri
        self.kirisler: List[Dict] = []
        self.duvarlar: List[Dict] = []
        self.kolonlar: List[Dict] = []  # Kolonlar
        self.minhalar: List[Dict] = []  # Kapi/Pencere acikliklari
        self.oda_isimleri: List[Dict] = []  # Oda isimleri (TEXT/MTEXT)
        self.kat_isimleri: List[Dict] = []  # Kat isimleri (TEXT/MTEXT)
        self.m2_yazilari: List[Dict] = []  # M2 degerleri (TEXT/MTEXT) - Sap hesabi icin
        self.sonuc_duvarlar: List[Dict] = []
        self.sap_eslestirme: List[Dict] = []  # Oda-M2 eslestirmesi
        self.imalat_listesi: List[Dict] = []  # Mahal bazli imalat listesi
        self.tefrisler: List[Dict] = []  # DXF bloklarindan okunan tefrisler
        self.malzeme_ihtiyaclari: Dict = {}  # Toplam malzeme ve paket sayilari
        self.duvar_cinsi: str = "Tuğla"  # Secilen duvar malzeme cinsi (nalbur siparisi icin)

        # AutoCAD canlı bağlantı
        self.acad_connector: Optional['AutoCADConnector'] = None
        self.acad_metraj_objeleri: List = []  # AutoCAD'den alınan metraj objeleri

        # Demir metraj kat verileri
        # Format: {"kat_adi": str, "demirler": List[DemirBilgisi], "rapor": Dict}
        self.demir_kat_verileri: List[Dict] = []
        self.aktif_kat_adi: str = ""  # Şu an seçili kat

        self._setup_ui()
        self._load_demo_data()

    def _setup_ui(self):
        """Arayuzu olustur"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Sol panel - Kontroller
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)
        left_panel.setFixedWidth(500)

        # Genel ayarlar (sadece İnce İşler için görünür)
        self._create_settings_group(left_layout)

        # Gizli tablolar (DXF yukleme icin gerekli)
        self.kiris_table = QTableWidget()
        self.kiris_table.setColumnCount(3)
        self.kiris_table.setHorizontalHeaderLabels(["ID", "H (cm)", "Koordinatlar"])
        self.kiris_table.setVisible(False)

        self.duvar_table = QTableWidget()
        self.duvar_table.setColumnCount(3)
        self.duvar_table.setHorizontalHeaderLabels(["ID", "Kalinlik", "Koordinatlar"])
        self.duvar_table.setVisible(False)

        # Results table (gizli - arka planda kullanılıyor)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["ID", "Durum", "Formul", "Boyut", "Değer"])
        self.results_table.setVisible(False)

        # Hesaplama butonlari
        self._create_buttons(left_layout)

        left_layout.addStretch()

        # Sag panel - Gorsellestirme (sadece İnce İşler için görünür)
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)

        # Matplotlib canvas
        self.canvas = MatplotlibCanvas(self, width=8, height=8)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setStyleSheet("""
            QToolBar { background-color: #1a2a3a; border: none; }
            QToolButton { background-color: #2a4a6a; border: 1px solid #00BFFF; border-radius: 4px; padding: 4px; margin: 2px; }
            QToolButton:hover { background-color: #3a5a7a; }
        """)

        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)

        # Lejant
        legend_label = QLabel(
            "<b style='color:#00BFFF;'>LEJANT:</b> "
            "<span style='color:#636e72;'>■ Kolon</span> | "
            "<span style='color:#8B4513;'>■ Kapi</span> | "
            "<span style='color:#87CEEB;'>■ Pencere</span> | "
            "<span style='color:#ff6b6b;'>■ Duvar</span> | "
            "<span style='color:#2ecc71;'>● m2</span><br>"
            "<b>Mahal:</b> "
            "<span style='color:#f1c40f;'>Sari: KURU</span> | "
            "<span style='color:#3498db;'>Mavi: ISLAK</span> | "
            "<span style='color:#e67e22;'>Turuncu: MUTFAK</span> | "
            "<span style='color:#9b59b6;'>Mor: KORIDOR</span>"
        )
        legend_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        legend_label.setStyleSheet("background-color: #1a1a2a; padding: 10px; border-radius: 6px; border: 1px solid #00BFFF;")
        right_layout.addWidget(legend_label)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(self.right_panel, 1)

    def _create_settings_group(self, parent_layout):
        """Genel ayarlar grubu (İnce İşler için)"""
        self.settings_group = QGroupBox("Genel Ayarlar")
        layout = QGridLayout()

        # Kat yuksekligi
        layout.addWidget(QLabel("Kat Yuksekligi (cm):"), 0, 0)
        self.kat_yuksekligi_spin = QSpinBox()
        self.kat_yuksekligi_spin.setRange(200, 500)
        self.kat_yuksekligi_spin.setValue(300)
        self.kat_yuksekligi_spin.setSuffix(" cm")
        layout.addWidget(self.kat_yuksekligi_spin, 0, 1)

        # Standart doseme kalinligi
        layout.addWidget(QLabel("Doseme Kalinligi (cm):"), 1, 0)
        self.doseme_kalinligi_spin = QSpinBox()
        self.doseme_kalinligi_spin.setRange(10, 50)
        self.doseme_kalinligi_spin.setValue(15)
        self.doseme_kalinligi_spin.setSuffix(" cm")
        layout.addWidget(self.doseme_kalinligi_spin, 1, 1)

        self.settings_group.setLayout(layout)
        parent_layout.addWidget(self.settings_group)

    def _create_kiris_group(self, parent_layout):
        """Kiris ekleme grubu"""
        group = QGroupBox("Kiris Ekle")
        layout = QGridLayout()

        # Kiris ID
        layout.addWidget(QLabel("Kiris ID:"), 0, 0)
        self.kiris_id_edit = QLineEdit()
        self.kiris_id_edit.setPlaceholderText("Ornek: K101")
        layout.addWidget(self.kiris_id_edit, 0, 1)

        # Kiris yuksekligi (sarkma)
        layout.addWidget(QLabel("Kiris Yuksekligi (H):"), 1, 0)
        self.kiris_h_spin = QSpinBox()
        self.kiris_h_spin.setRange(20, 120)
        self.kiris_h_spin.setValue(60)
        self.kiris_h_spin.setSuffix(" cm")
        layout.addWidget(self.kiris_h_spin, 1, 1)

        # Koordinatlar
        layout.addWidget(QLabel("X1, Y1:"), 2, 0)
        coord1_layout = QHBoxLayout()
        self.kiris_x1 = QSpinBox()
        self.kiris_x1.setRange(0, 2000)
        self.kiris_x1.setValue(0)
        self.kiris_y1 = QSpinBox()
        self.kiris_y1.setRange(0, 2000)
        self.kiris_y1.setValue(400)
        coord1_layout.addWidget(self.kiris_x1)
        coord1_layout.addWidget(self.kiris_y1)
        layout.addLayout(coord1_layout, 2, 1)

        layout.addWidget(QLabel("X2, Y2:"), 3, 0)
        coord2_layout = QHBoxLayout()
        self.kiris_x2 = QSpinBox()
        self.kiris_x2.setRange(0, 2000)
        self.kiris_x2.setValue(400)
        self.kiris_y2 = QSpinBox()
        self.kiris_y2.setRange(0, 2000)
        self.kiris_y2.setValue(370)
        coord2_layout.addWidget(self.kiris_x2)
        coord2_layout.addWidget(self.kiris_y2)
        layout.addLayout(coord2_layout, 3, 1)

        # Ekle butonu
        btn_ekle = QPushButton("Kiris Ekle")
        btn_ekle.clicked.connect(self._add_kiris)
        btn_ekle.setStyleSheet("background-color: #2a5a3a; border-color: #4CAF50;")
        layout.addWidget(btn_ekle, 4, 0, 1, 2)

        # Kiris listesi
        self.kiris_table = QTableWidget()
        self.kiris_table.setColumnCount(3)
        self.kiris_table.setHorizontalHeaderLabels(["ID", "H (cm)", "Koordinatlar"])
        self.kiris_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.kiris_table.setMaximumHeight(120)
        layout.addWidget(self.kiris_table, 5, 0, 1, 2)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _create_duvar_group(self, parent_layout):
        """Duvar ekleme grubu"""
        group = QGroupBox("Duvar Ekle")
        layout = QGridLayout()

        # Duvar ID
        layout.addWidget(QLabel("Duvar ID:"), 0, 0)
        self.duvar_id_edit = QLineEdit()
        self.duvar_id_edit.setPlaceholderText("Ornek: D1")
        layout.addWidget(self.duvar_id_edit, 0, 1)

        # Duvar kalinligi
        layout.addWidget(QLabel("Duvar Kalinligi:"), 1, 0)
        self.duvar_kalinlik_combo = QComboBox()
        self.duvar_kalinlik_combo.addItems(["10 cm", "15 cm", "20 cm", "25 cm", "30 cm"])
        self.duvar_kalinlik_combo.setCurrentIndex(2)  # 20 cm default
        layout.addWidget(self.duvar_kalinlik_combo, 1, 1)

        # Koordinatlar
        layout.addWidget(QLabel("X1, Y1:"), 2, 0)
        coord1_layout = QHBoxLayout()
        self.duvar_x1 = QSpinBox()
        self.duvar_x1.setRange(0, 2000)
        self.duvar_x1.setValue(0)
        self.duvar_y1 = QSpinBox()
        self.duvar_y1.setRange(0, 2000)
        self.duvar_y1.setValue(390)
        coord1_layout.addWidget(self.duvar_x1)
        coord1_layout.addWidget(self.duvar_y1)
        layout.addLayout(coord1_layout, 2, 1)

        layout.addWidget(QLabel("X2, Y2:"), 3, 0)
        coord2_layout = QHBoxLayout()
        self.duvar_x2 = QSpinBox()
        self.duvar_x2.setRange(0, 2000)
        self.duvar_x2.setValue(380)
        self.duvar_y2 = QSpinBox()
        self.duvar_y2.setRange(0, 2000)
        self.duvar_y2.setValue(370)
        coord2_layout.addWidget(self.duvar_x2)
        coord2_layout.addWidget(self.duvar_y2)
        layout.addLayout(coord2_layout, 3, 1)

        # Ekle butonu
        btn_ekle = QPushButton("Duvar Ekle")
        btn_ekle.clicked.connect(self._add_duvar)
        btn_ekle.setStyleSheet("background-color: #5a2a3a; border-color: #e91e63;")
        layout.addWidget(btn_ekle, 4, 0, 1, 2)

        # Duvar listesi
        self.duvar_table = QTableWidget()
        self.duvar_table.setColumnCount(3)
        self.duvar_table.setHorizontalHeaderLabels(["ID", "Kalinlik", "Koordinatlar"])
        self.duvar_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.duvar_table.setMaximumHeight(120)
        layout.addWidget(self.duvar_table, 5, 0, 1, 2)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _create_buttons(self, parent_layout):
        """Hesaplama butonlari"""

        # ═══════════════════════════════════════════════════════════════════
        # AUTOCAD CANLI BAĞLANTI BÖLÜMÜ (SEKMELİ)
        # ═══════════════════════════════════════════════════════════════════
        acad_group = QGroupBox("🔗 AutoCAD Canlı Bağlantı")
        acad_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 10pt;
                border: 2px solid #ff6b00;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #ff6b00;
            }
        """)
        acad_main_layout = QVBoxLayout()

        # AutoCAD Bağlan butonu (her iki sekme için ortak)
        self.btn_acad_baglan = QPushButton("🔌 AutoCAD'e Bağlan")
        self.btn_acad_baglan.clicked.connect(self._autocad_baglan)
        self.btn_acad_baglan.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff6b00, stop:1 #cc5500);
                color: white;
                font-weight: bold;
                font-size: 11pt;
                padding: 10px;
                border: 2px solid #ff9933;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff8533, stop:1 #ff6b00);
            }
            QPushButton:disabled {
                background: #555;
                color: #888;
            }
        """)
        acad_main_layout.addWidget(self.btn_acad_baglan)

        # AutoCAD durum etiketi
        self.acad_status_label = QLabel("AutoCAD bağlı değil")
        self.acad_status_label.setStyleSheet("color: #888; font-style: italic; padding: 3px;")
        acad_main_layout.addWidget(self.acad_status_label)

        # ═══════════════════════════════════════════════════════════════════
        # SEKME YAPISI (TabWidget)
        # ═══════════════════════════════════════════════════════════════════
        self.acad_tab_widget = QTabWidget()
        self.acad_tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                background: #2b2b3d;
                border-radius: 3px;
            }
            QTabBar::tab {
                background: #3a3a4a;
                color: #aaa;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #4a4a5a;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background: #4a4a5a;
            }
        """)

        # ─────────────────────────────────────────────────────────────────
        # SEKME 1: İNCE İŞLER METRAJI
        # ─────────────────────────────────────────────────────────────────
        ince_isler_tab = QWidget()
        ince_isler_layout = QVBoxLayout(ince_isler_tab)
        ince_isler_layout.setContentsMargins(5, 10, 5, 5)

        # Seçim butonları
        acad_btn_layout = QHBoxLayout()

        self.btn_acad_sec = QPushButton("🖱️ Obje Seç")
        self.btn_acad_sec.clicked.connect(self._autocad_obje_sec)
        self.btn_acad_sec.setEnabled(False)
        self.btn_acad_sec.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2196F3, stop:1 #1976D2);
                color: white;
                font-weight: bold;
                padding: 8px;
                border: 2px solid #64B5F6;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #42A5F5, stop:1 #2196F3);
            }
            QPushButton:disabled {
                background: #444;
                color: #666;
            }
        """)
        acad_btn_layout.addWidget(self.btn_acad_sec)

        self.btn_acad_renk_geri = QPushButton("↩️ Renkleri Geri Al")
        self.btn_acad_renk_geri.clicked.connect(self._autocad_renkleri_geri_al)
        self.btn_acad_renk_geri.setEnabled(False)
        self.btn_acad_renk_geri.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #607D8B, stop:1 #455A64);
                color: white;
                font-weight: bold;
                padding: 8px;
                border: 2px solid #90A4AE;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #78909C, stop:1 #607D8B);
            }
            QPushButton:disabled {
                background: #444;
                color: #666;
            }
        """)
        acad_btn_layout.addWidget(self.btn_acad_renk_geri)

        ince_isler_layout.addLayout(acad_btn_layout)

        # Katmana göre seçim
        katman_layout = QHBoxLayout()
        katman_layout.addWidget(QLabel("Katman:"))
        self.acad_katman_combo = QComboBox()
        self.acad_katman_combo.setEnabled(False)
        self.acad_katman_combo.setMinimumWidth(120)
        katman_layout.addWidget(self.acad_katman_combo)

        self.btn_acad_katman_sec = QPushButton("Katmanı Seç")
        self.btn_acad_katman_sec.clicked.connect(self._autocad_katman_sec)
        self.btn_acad_katman_sec.setEnabled(False)
        katman_layout.addWidget(self.btn_acad_katman_sec)

        ince_isler_layout.addLayout(katman_layout)

        # Bilgi etiketi
        ince_info = QLabel("💡 Duvar, pencere, kapı vb. ince işler için")
        ince_info.setStyleSheet("color: #888; font-size: 9pt; padding: 5px;")
        ince_isler_layout.addWidget(ince_info)

        ince_isler_layout.addStretch()

        self.acad_tab_widget.addTab(ince_isler_tab, "🏗️ İnce İşler")

        # ─────────────────────────────────────────────────────────────────
        # SEKME 2: DEMİR METRAJI
        # ─────────────────────────────────────────────────────────────────
        demir_tab = QWidget()
        demir_layout = QVBoxLayout(demir_tab)
        demir_layout.setContentsMargins(5, 10, 5, 5)

        # Demir Metraj butonu
        self.btn_acad_demir = QPushButton("🔩 DEMİR METRAJİ AL")
        self.btn_acad_demir.clicked.connect(self._autocad_demir_metraj)
        self.btn_acad_demir.setEnabled(False)
        self.btn_acad_demir.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8B4513, stop:1 #654321);
                color: white;
                font-weight: bold;
                font-size: 12pt;
                padding: 12px;
                border: 2px solid #CD853F;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #A0522D, stop:1 #8B4513);
            }
            QPushButton:disabled {
                background: #444;
                color: #666;
            }
        """)
        demir_layout.addWidget(self.btn_acad_demir)

        # Kolon/Perde Birleşik Hesaplama butonu
        self.btn_kolon_grup = QPushButton("🏗️ KOLON/PERDE HESAPLA")
        self.btn_kolon_grup.clicked.connect(self._autocad_dusay_eleman_hesapla)
        self.btn_kolon_grup.setEnabled(False)
        self.btn_kolon_grup.setToolTip(
            "Akıllı Tekil/Grup Ayrımı:\n"
            "• TEKİL: Sadece başlık + donatı seç (PB055 + 2x8Ø12 L=420)\n"
            "• GRUP: Başlık + liste + donatı seç (SB17 + SB24,SB31 + 28Ø14 L=442)\n\n"
            "Perde 2x formatı desteklenir (2x8Ø12 = 16 adet)"
        )
        self.btn_kolon_grup.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2E8B57, stop:1 #228B22);
                color: white;
                font-weight: bold;
                font-size: 11pt;
                padding: 10px;
                border: 2px solid #3CB371;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3CB371, stop:1 #2E8B57);
            }
            QPushButton:disabled {
                background: #444;
                color: #666;
            }
        """)
        demir_layout.addWidget(self.btn_kolon_grup)

        # Demir birim seçimi
        demir_birim_layout = QHBoxLayout()
        demir_birim_layout.addWidget(QLabel("Boy Birimi:"))
        self.demir_birim_combo = QComboBox()
        self.demir_birim_combo.addItems(["cm", "m"])
        self.demir_birim_combo.setCurrentIndex(0)  # Varsayılan: cm
        self.demir_birim_combo.setEnabled(False)
        demir_birim_layout.addWidget(self.demir_birim_combo)

        self.btn_demir_renk_geri = QPushButton("↩️ Renkleri Geri Al")
        self.btn_demir_renk_geri.clicked.connect(self._autocad_renkleri_geri_al)
        self.btn_demir_renk_geri.setEnabled(False)
        self.btn_demir_renk_geri.setStyleSheet("""
            QPushButton {
                background: #555;
                color: white;
                padding: 5px 10px;
                border: 1px solid #777;
            }
            QPushButton:hover {
                background: #666;
            }
            QPushButton:disabled {
                background: #444;
                color: #666;
            }
        """)
        demir_birim_layout.addWidget(self.btn_demir_renk_geri)

        demir_layout.addLayout(demir_birim_layout)

        # ─────────────────────────────────────────────────────────────────
        # KAT İSMİ GİRİŞİ
        # ─────────────────────────────────────────────────────────────────
        kat_frame = QFrame()
        kat_frame.setStyleSheet("QFrame { border: 1px solid #555; border-radius: 4px; padding: 5px; }")
        kat_frame_layout = QVBoxLayout(kat_frame)
        kat_frame_layout.setContentsMargins(5, 5, 5, 5)
        kat_frame_layout.setSpacing(5)

        kat_label = QLabel("📋 Kat İsmi Girişi")
        kat_label.setStyleSheet("font-weight: bold; color: #CD853F; border: none;")
        kat_frame_layout.addWidget(kat_label)

        # Kat ismi input
        kat_input_layout = QHBoxLayout()
        self.demir_kat_input = QLineEdit()
        self.demir_kat_input.setPlaceholderText("Örn: Bodrum Kat, Zemin Kat, 1. Kat...")
        self.demir_kat_input.setStyleSheet("border: 1px solid #666; padding: 5px;")
        kat_input_layout.addWidget(self.demir_kat_input)

        self.btn_kat_ekle = QPushButton("+ Ekle")
        self.btn_kat_ekle.clicked.connect(self._demir_kat_ekle)
        self.btn_kat_ekle.setEnabled(False)
        self.btn_kat_ekle.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px 15px;
                border: none;
            }
            QPushButton:hover { background: #45a049; }
            QPushButton:disabled { background: #444; color: #666; }
        """)
        kat_input_layout.addWidget(self.btn_kat_ekle)

        kat_frame_layout.addLayout(kat_input_layout)

        # Kat listesi
        self.demir_kat_listesi = QListWidget()
        self.demir_kat_listesi.setMaximumHeight(100)
        self.demir_kat_listesi.setStyleSheet("""
            QListWidget {
                background: #2a2a3a;
                border: 1px solid #555;
                color: white;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background: #8B4513;
            }
        """)
        self.demir_kat_listesi.itemClicked.connect(self._demir_kat_secildi)
        kat_frame_layout.addWidget(self.demir_kat_listesi)

        # Kat silme butonu
        self.btn_kat_sil = QPushButton("🗑️ Seçili Katı Sil")
        self.btn_kat_sil.clicked.connect(self._demir_kat_sil)
        self.btn_kat_sil.setEnabled(False)
        self.btn_kat_sil.setStyleSheet("""
            QPushButton {
                background: #c0392b;
                color: white;
                padding: 3px 10px;
                border: none;
                font-size: 9pt;
            }
            QPushButton:hover { background: #e74c3c; }
            QPushButton:disabled { background: #444; color: #666; }
        """)
        kat_frame_layout.addWidget(self.btn_kat_sil)

        demir_layout.addWidget(kat_frame)

        # Bilgi etiketi
        demir_info = QLabel("💡 Önce kat ekleyin, sonra demir yazılarını seçin")
        demir_info.setStyleSheet("color: #888; font-size: 9pt; padding: 5px;")
        demir_layout.addWidget(demir_info)

        # Renk açıklaması
        renk_info = QLabel("✅ Geçerli = YEŞİL  |  ❌ Geçersiz = KIRMIZI")
        renk_info.setStyleSheet("color: #aaa; font-size: 8pt; padding: 3px;")
        demir_layout.addWidget(renk_info)

        # Demir Excel Export butonu
        self.btn_demir_excel = QPushButton("📊 DEMİR EXCEL'E AKTAR")
        self.btn_demir_excel.clicked.connect(self._demir_excel_export)
        self.btn_demir_excel.setEnabled(False)
        self.btn_demir_excel.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #1e8449);
                color: white;
                font-weight: bold;
                padding: 8px;
                border: 2px solid #2ecc71;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2ecc71, stop:1 #27ae60);
            }
            QPushButton:disabled {
                background: #444;
                color: #666;
            }
        """)
        demir_layout.addWidget(self.btn_demir_excel)

        self.acad_tab_widget.addTab(demir_tab, "🔩 Demir Metrajı")

        # Sekme değişikliği callback'i
        self.acad_tab_widget.currentChanged.connect(self._sekme_degisti)

        acad_main_layout.addWidget(self.acad_tab_widget)

        acad_group.setLayout(acad_main_layout)
        parent_layout.addWidget(acad_group)

        # ═══════════════════════════════════════════════════════════════════
        # DXF DOSYA YÜKLEME (Statik - Eski yöntem)
        # ═══════════════════════════════════════════════════════════════════
        dxf_layout = QHBoxLayout()
        btn_dxf = QPushButton("📁 DXF DOSYASI YUKLE (Statik)")
        btn_dxf.clicked.connect(self._load_dxf_file)
        btn_dxf.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9c27b0, stop:1 #7b1fa2);
                color: white;
                font-weight: bold;
                font-size: 10pt;
                padding: 8px;
                border: 2px solid #ce93d8;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ab47bc, stop:1 #9c27b0);
            }
        """)
        dxf_layout.addWidget(btn_dxf)
        parent_layout.addLayout(dxf_layout)

        # DXF durum etiketi
        self.dxf_status_label = QLabel("DXF dosyasi yuklenmedi")
        self.dxf_status_label.setStyleSheet("color: #888; font-style: italic; padding: 5px;")
        parent_layout.addWidget(self.dxf_status_label)

        # Hesaplama butonlari
        btn_layout = QHBoxLayout()

        btn_hesapla = QPushButton("HESAPLA VE GORSELLESTIR")
        btn_hesapla.clicked.connect(self._calculate_and_visualize)
        btn_hesapla.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00BFFF, stop:1 #0066cc);
                color: white;
                font-weight: bold;
                font-size: 12pt;
                padding: 12px;
                border: 2px solid #00DDFF;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00DDFF, stop:1 #00BFFF);
            }
        """)
        btn_layout.addWidget(btn_hesapla)

        btn_temizle = QPushButton("Temizle")
        btn_temizle.clicked.connect(self._clear_all)
        btn_temizle.setStyleSheet("background-color: #4a3a2a; border-color: #ff9800;")
        btn_layout.addWidget(btn_temizle)

        parent_layout.addLayout(btn_layout)

        # Excel export butonu
        export_layout = QHBoxLayout()
        btn_excel = QPushButton("📊 EXCEL'E AKTAR")
        btn_excel.clicked.connect(self._export_to_excel)
        btn_excel.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4CAF50, stop:1 #388E3C);
                color: white;
                font-weight: bold;
                font-size: 10pt;
                padding: 8px;
                border: 2px solid #81C784;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #66BB6A, stop:1 #4CAF50);
            }
        """)
        export_layout.addWidget(btn_excel)
        parent_layout.addLayout(export_layout)

    def _create_results_table(self, parent_layout):
        """Sonuc tablosu"""
        group = QGroupBox("Hesaplama Sonuclari")
        layout = QVBoxLayout()

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "Duvar ID", "Durum", "Formul", "Yukseklik (Kalinlik)", "Net Alan (m2)"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setMinimumHeight(150)
        layout.addWidget(self.results_table)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _add_kiris(self):
        """Kiris ekle"""
        kiris_id = self.kiris_id_edit.text().strip()
        if not kiris_id:
            QMessageBox.warning(self, "Uyari", "Kiris ID giriniz!")
            return

        h = self.kiris_h_spin.value()
        x1, y1 = self.kiris_x1.value(), self.kiris_y1.value()
        x2, y2 = self.kiris_x2.value(), self.kiris_y2.value()

        # Polygon olustur (dikdortgen)
        geo = Polygon([
            (x1, y1), (x2, y1), (x2, y2), (x1, y2)
        ])

        kiris = {
            "id": kiris_id,
            "layer": f"S_KIRIS_H{h}",
            "h": h,
            "geo": geo,
            "coords": f"({x1},{y1})-({x2},{y2})"
        }
        self.kirisler.append(kiris)

        # Tabloya ekle
        row = self.kiris_table.rowCount()
        self.kiris_table.insertRow(row)
        self.kiris_table.setItem(row, 0, QTableWidgetItem(kiris_id))
        self.kiris_table.setItem(row, 1, QTableWidgetItem(f"{h} cm"))
        self.kiris_table.setItem(row, 2, QTableWidgetItem(kiris["coords"]))

        # Alanları temizle
        self.kiris_id_edit.clear()
        logger.info(f"Kiris eklendi: {kiris_id}")

    def _add_duvar(self):
        """Duvar ekle"""
        duvar_id = self.duvar_id_edit.text().strip()
        if not duvar_id:
            QMessageBox.warning(self, "Uyari", "Duvar ID giriniz!")
            return

        kalinlik = self.duvar_kalinlik_combo.currentText()
        x1, y1 = self.duvar_x1.value(), self.duvar_y1.value()
        x2, y2 = self.duvar_x2.value(), self.duvar_y2.value()

        # Polygon olustur (dikdortgen)
        geo = Polygon([
            (x1, y1), (x2, y1), (x2, y2), (x1, y2)
        ])

        duvar = {
            "id": duvar_id,
            "layer": f"M_DUVAR_TUGLA_{kalinlik.split()[0]}",
            "kalinlik": kalinlik,
            "geo": geo,
            "coords": f"({x1},{y1})-({x2},{y2})"
        }
        self.duvarlar.append(duvar)

        # Tabloya ekle
        row = self.duvar_table.rowCount()
        self.duvar_table.insertRow(row)
        self.duvar_table.setItem(row, 0, QTableWidgetItem(duvar_id))
        self.duvar_table.setItem(row, 1, QTableWidgetItem(kalinlik))
        self.duvar_table.setItem(row, 2, QTableWidgetItem(duvar["coords"]))

        # Alanları temizle
        self.duvar_id_edit.clear()
        logger.info(f"Duvar eklendi: {duvar_id}")

    def _calculate_and_visualize(self):
        """Hesaplama ve gorsellestirme - Akilli Yukseklik ve Minha dusumu dahil"""
        if not self.duvarlar:
            QMessageBox.warning(self, "Uyari", "En az bir duvar eklemelisiniz!")
            return

        kat_yuksekligi = self.kat_yuksekligi_spin.value()
        doseme_kalinligi = self.doseme_kalinligi_spin.value()

        self.sonuc_duvarlar = []
        self.results_table.setRowCount(0)

        for duvar in self.duvarlar:
            duvar_geo = duvar['geo']
            cakisan_kiris_yuksekligi = 0
            cakisan_kiris_adi = None

            # Kiris kontrolu (Collision Detection)
            for kiris in self.kirisler:
                if kiris['geo'].intersects(duvar_geo):
                    h_val = kiris['h']
                    if h_val > cakisan_kiris_yuksekligi:
                        cakisan_kiris_yuksekligi = h_val
                        cakisan_kiris_adi = kiris['layer']

            # AKILLI YUKSEKLIK KARARI
            # 1. Oncelik: Duvar layer'indan okunan yukseklik (M_DUVAR_H270)
            # 2. Yoksa: Kat yuksekligi - Kiris/Doseme

            duvar_layer_h = duvar.get('h', 0)  # Layer'dan okunan yukseklik

            if duvar_layer_h > 0 and duvar_layer_h != 300:  # 300 varsayilan, layer'da vardi demek
                # Layer'dan okunan yuksekligi kullan
                net_h = duvar_layer_h
                if cakisan_kiris_yuksekligi > 0:
                    aciklama = f"Layer H:{duvar_layer_h} (Kiris: {cakisan_kiris_adi})"
                    formul = f"Layer: {duvar_layer_h}"
                    renk = '#ff6b6b'  # Kirmizi (kiris var)
                else:
                    aciklama = f"Layer H:{duvar_layer_h} (Doseme Alti)"
                    formul = f"Layer: {duvar_layer_h}"
                    renk = '#4dabf7'  # Mavi
            elif cakisan_kiris_yuksekligi > 0:
                # Kiris var, kat yuksekliginden dus
                net_h = kat_yuksekligi - cakisan_kiris_yuksekligi
                aciklama = f"Kiris Alti ({cakisan_kiris_adi})"
                formul = f"{kat_yuksekligi} - {cakisan_kiris_yuksekligi}"
                renk = '#ff6b6b'  # Kirmizi
            else:
                # Doseme alti (varsayilan)
                net_h = kat_yuksekligi - doseme_kalinligi
                aciklama = "Doseme Alti (Kirissiz)"
                formul = f"{kat_yuksekligi} - {doseme_kalinligi}"
                renk = '#4dabf7'  # Mavi

            # Duvar uzunlugunu hesapla (geometriden)
            if SHAPELY_AVAILABLE:
                cevre = duvar_geo.length
                alan_geo = duvar_geo.area
                # Uzunluk = Cevre / 2 (dikdortgen icin)
                uzunluk = (cevre / 2) / 100  # cm -> m
            else:
                bounds = duvar_geo.bounds
                uzunluk = max(bounds[2] - bounds[0], bounds[3] - bounds[1]) / 100  # cm -> m

            brut_alan = uzunluk * (net_h / 100)  # m2

            # B) MINHA DUSUMU (Hibrit mantik: geometriden genislik, layerdan yukseklik)
            toplam_minha_alani = 0.0
            minha_detay = []

            for minha in self.minhalar:
                if minha['geo'].intersects(duvar_geo):
                    # Kesisim alani hesapla
                    if SHAPELY_AVAILABLE:
                        try:
                            kesisim = minha['geo'].intersection(duvar_geo)
                            if not kesisim.is_empty:
                                # Kesisimden genislik al (duvar uzerindeki aciklik genisligi)
                                kesisim_bounds = kesisim.bounds
                                genislik_cm = max(kesisim_bounds[2] - kesisim_bounds[0],
                                                  kesisim_bounds[3] - kesisim_bounds[1])
                        except:
                            genislik_cm = minha.get('genislik', 100)
                    else:
                        genislik_cm = minha.get('genislik', 100)

                    # Yukseklik layerdan (minha['h'])
                    yukseklik_cm = minha['h']

                    # Alan: Genislik x Yukseklik
                    minha_alan_m2 = (genislik_cm * yukseklik_cm) / 10000

                    toplam_minha_alani += minha_alan_m2
                    minha_detay.append(f"{minha['layer']} ({int(genislik_cm)}x{yukseklik_cm})")

            # Net alan = Brut alan - Minha alani
            net_alan = brut_alan - toplam_minha_alani

            # Kalinlik bilgisi
            kalinlik_cm = duvar.get('kalinlik_cm', 20)

            sonuc = {
                "geo": duvar_geo,
                "net_h": net_h,
                "renk": renk,
                "id": duvar['id'],
                "layer": duvar.get('layer', ''),
                "aciklama": aciklama,
                "formul": formul,
                "brut_alan": brut_alan,
                "minha_alani": toplam_minha_alani,
                "minha_detay": minha_detay,
                "alan": net_alan,  # Net alan
                "uzunluk": uzunluk,
                "kalinlik_cm": kalinlik_cm
            }
            self.sonuc_duvarlar.append(sonuc)

            # Tabloya ekle
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            self.results_table.setItem(row, 0, QTableWidgetItem(duvar['id']))
            self.results_table.setItem(row, 1, QTableWidgetItem(aciklama))
            self.results_table.setItem(row, 2, QTableWidgetItem(formul))
            self.results_table.setItem(row, 3, QTableWidgetItem(f"{net_h} cm ({kalinlik_cm}cm)"))
            self.results_table.setItem(row, 4, QTableWidgetItem(f"{net_alan:.2f} m2"))

            # Renk ayarla
            if "Kiris" in aciklama:
                for col in range(5):
                    item = self.results_table.item(row, col)
                    if item:
                        item.setBackground(QColor(100, 50, 50))
            else:
                for col in range(5):
                    item = self.results_table.item(row, col)
                    if item:
                        item.setBackground(QColor(50, 50, 100))

        # Gorsellestir
        self._visualize()
        logger.info("Hesaplama tamamlandi")

    def _visualize(self):
        """Modern Gorsellestirme - Profesyonel Kat Plani Gorunumu"""
        import math
        from matplotlib.patches import Arc, FancyBboxPatch, Rectangle, Wedge
        from matplotlib.lines import Line2D
        import matplotlib.patheffects as pe

        ax = self.canvas.axes
        ax.clear()
        ax.set_facecolor('#2b2b3d')  # Koyu lacivert-gri arka plan
        ax.axis('off')

        # Tum koordinatlari topla (otomatik eksen limiti icin)
        all_x = []
        all_y = []

        # --- ODA ISIMLERINI M2 VERILERIYLE ESLESTIR ---
        oda_m2_map = {}
        for oda in self.oda_isimleri:
            en_yakin_m2 = None
            en_yakin_mesafe = float('inf')
            for m2 in self.m2_yazilari:
                dx = oda['x'] - m2['x']
                dy = oda['y'] - m2['y']
                mesafe = math.sqrt(dx*dx + dy*dy)
                if mesafe < en_yakin_mesafe:
                    en_yakin_mesafe = mesafe
                    en_yakin_m2 = m2
            if en_yakin_m2 and en_yakin_mesafe < 500:
                oda_m2_map[id(oda)] = en_yakin_m2['deger']

        # A) KIRISLERI CIZ (Hayalet Cizgi - ici bos)
        for kiris in self.kirisler:
            x, y = kiris['geo'].exterior.xy
            all_x.extend(x)
            all_y.extend(y)
            ax.fill(x, y, fc='none', ec='#4a5580', alpha=0.25, linestyle='--', linewidth=0.8)

        # B) DUVARLARI CIZ (Cyan/Turkuaz - Parlak Neon Efekti)
        for d in self.sonuc_duvarlar:
            x, y = d['geo'].exterior.xy
            all_x.extend(x)
            all_y.extend(y)

            # Tum duvarlar cyan/turkuaz renkte
            # Glow efekti icin once kalin yarim-saydam cizgi
            ax.fill(x, y, fc='#00e5ff', alpha=0.15, ec='none', zorder=4)
            ax.plot(list(x) + [x[0]], list(y) + [y[0]],
                    color='#00e5ff', linewidth=3.5, alpha=0.3, zorder=4,
                    solid_capstyle='round')
            # Ana duvar kenari
            ax.plot(list(x) + [x[0]], list(y) + [y[0]],
                    color='#00e5ff', linewidth=1.8, alpha=0.95, zorder=5,
                    solid_capstyle='round')

        # C) KOLONLARI CIZ (Beyaz Dolu Kareler)
        for kolon in self.kolonlar:
            x, y = kolon['geo'].exterior.xy
            all_x.extend(x)
            all_y.extend(y)

            ax.fill(x, y,
                    fc='white',
                    ec='#cccccc',
                    alpha=0.95,
                    linewidth=1.5,
                    zorder=15)

        # D) MINHALARI CIZ (Kapi/Pencere)
        for minha in self.minhalar:
            x, y = minha['geo'].exterior.xy
            all_x.extend(x)
            all_y.extend(y)

            min_x_m, max_x_m = min(x), max(x)
            min_y_m, max_y_m = min(y), max(y)
            genislik = max_x_m - min_x_m
            yukseklik = max_y_m - min_y_m

            minha_h = minha.get('h', 210)
            is_kapi = minha_h >= 180

            if is_kapi:
                # KAPI - Kahverengi dolgulu acilma yayi
                # Arka plan temizle (duvar uzerindeki bosluk)
                ax.fill(x, y, fc='#2b2b3d', ec='none', alpha=1.0, zorder=8)

                # Acilma yayi (dolu wedge seklinde)
                if genislik > yukseklik:
                    # Yatay kapi
                    arc_radius = genislik
                    arc_center = (min_x_m, min_y_m)
                    wedge = Wedge(arc_center, arc_radius, 0, 90,
                                  fc='#8B6914', ec='#6B4F12', alpha=0.45,
                                  linewidth=1.2, zorder=9)
                    ax.add_patch(wedge)
                    # Kapi kanadi cizgisi
                    ax.plot([min_x_m, min_x_m + genislik], [min_y_m, min_y_m],
                            color='#8B6914', linewidth=2, alpha=0.8, zorder=10)
                    ax.plot([min_x_m, min_x_m], [min_y_m, min_y_m + genislik],
                            color='#8B6914', linewidth=2, alpha=0.8, zorder=10)
                else:
                    # Dikey kapi
                    arc_radius = yukseklik
                    arc_center = (min_x_m, min_y_m)
                    wedge = Wedge(arc_center, arc_radius, 0, 90,
                                  fc='#8B6914', ec='#6B4F12', alpha=0.45,
                                  linewidth=1.2, zorder=9)
                    ax.add_patch(wedge)
                    ax.plot([min_x_m, min_x_m + yukseklik], [min_y_m, min_y_m],
                            color='#8B6914', linewidth=2, alpha=0.8, zorder=10)
                    ax.plot([min_x_m, min_x_m], [min_y_m, min_y_m + yukseklik],
                            color='#8B6914', linewidth=2, alpha=0.8, zorder=10)
            else:
                # PENCERE - Mavi dikdortgen (duvar uzerinde)
                ax.fill(x, y,
                        fc='#5599dd',
                        ec='#3377bb',
                        alpha=0.7,
                        linewidth=1.5,
                        zorder=10)
                # Ortada ayirici cizgi
                if genislik > yukseklik:
                    orta_y_m = (min_y_m + max_y_m) / 2
                    ax.plot([min_x_m, max_x_m], [orta_y_m, orta_y_m],
                            color='#3377bb', linewidth=1, alpha=0.8, zorder=11)
                else:
                    orta_x_m = (min_x_m + max_x_m) / 2
                    ax.plot([orta_x_m, orta_x_m], [min_y_m, max_y_m],
                            color='#3377bb', linewidth=1, alpha=0.8, zorder=11)

        # E) ODA ISIMLERINI CIZ (Isim + m2 birlikte, recete rengine gore)
        renk_map = {
            "KURU": {"fc": "#f1c40f", "ec": "#d4ac0d", "tc": "#1a1a2e"},
            "ISLAK": {"fc": "#9b59b6", "ec": "#8e44ad", "tc": "white"},
            "MUTFAK": {"fc": "#f1c40f", "ec": "#d4ac0d", "tc": "#1a1a2e"},
            "KORIDOR": {"fc": "#2ecc71", "ec": "#27ae60", "tc": "#1a1a2e"},
        }
        for oda in self.oda_isimleri:
            recete = recete_getir(oda['text'])
            tur = recete["TUR"]
            renkler = renk_map.get(tur, renk_map["KURU"])

            # m2 degerini ekle (eslestirildiyse)
            m2_val = oda_m2_map.get(id(oda))
            if m2_val is not None:
                etiket = f"{oda['text']}\n{m2_val:.1f} m\u00b2"
            else:
                etiket = oda['text']

            ax.text(
                oda['x'], oda['y'],
                etiket,
                ha='center', va='center', fontsize=8,
                color=renkler["tc"],
                fontweight='bold',
                zorder=20,
                bbox=dict(boxstyle='round,pad=0.4',
                          facecolor=renkler["fc"],
                          edgecolor=renkler["ec"],
                          alpha=0.92, linewidth=1.5)
            )

        # F) ESLESMEYEN M2 YAZILARINI CIZ (oda ile eslesmeyen m2 degerleri)
        eslesen_m2_ids = set()
        for oda in self.oda_isimleri:
            en_yakin_m2 = None
            en_yakin_mesafe = float('inf')
            for i, m2 in enumerate(self.m2_yazilari):
                dx = oda['x'] - m2['x']
                dy = oda['y'] - m2['y']
                mesafe = math.sqrt(dx*dx + dy*dy)
                if mesafe < en_yakin_mesafe:
                    en_yakin_mesafe = mesafe
                    en_yakin_m2 = i
            if en_yakin_m2 is not None and en_yakin_mesafe < 500:
                eslesen_m2_ids.add(en_yakin_m2)

        for i, m2 in enumerate(self.m2_yazilari):
            if i not in eslesen_m2_ids:
                ax.scatter(m2['x'], m2['y'], c='#f1c40f', s=40, zorder=18,
                           edgecolors='#d4ac0d', linewidths=1, marker='o')
                ax.text(
                    m2['x'], m2['y'] - 20,
                    f"{m2['deger']:.1f} m\u00b2",
                    ha='center', va='top', fontsize=8,
                    color='white', fontweight='bold', zorder=19,
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#2b2b3d',
                              edgecolor='#f1c40f', alpha=0.9)
                )

        # G) KAT ISIMLERINI CIZ
        for kat in self.kat_isimleri:
            ax.text(
                kat['x'], kat['y'],
                kat['text'],
                ha='center', va='center', fontsize=14,
                color='#00e5ff',
                fontweight='bold',
                zorder=20,
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#1a1a3e',
                          edgecolor='#00e5ff', alpha=0.8, linewidth=2)
            )

        # --- BASLIK (Sag Ust - Proje Bilgisi) ---
        toplam_m2 = sum(m['deger'] for m in self.m2_yazilari) if self.m2_yazilari else 0
        kat_adi = self.kat_isimleri[0]['text'] if self.kat_isimleri else "KAT"
        if toplam_m2 > 0:
            baslik = f"PROJE: {kat_adi} | TOPLAM ALAN: {toplam_m2:.1f} m\u00b2"
        else:
            baslik = f"PROJE: {kat_adi}"
        ax.set_title(baslik, color='white', fontsize=11, fontweight='bold',
                      pad=12, loc='right')

        # --- EKSEN AYARLARI ---
        if all_x and all_y:
            mn_x, mx_x = min(all_x), max(all_x)
            mn_y, mx_y = min(all_y), max(all_y)
            margin_x = (mx_x - mn_x) * 0.1 if mx_x != mn_x else 50
            margin_y = (mx_y - mn_y) * 0.1 if mx_y != mn_y else 50
            ax.set_xlim(mn_x - margin_x, mx_x + margin_x)
            ax.set_ylim(mn_y - margin_y, mx_y + margin_y)
        else:
            ax.set_xlim(-50, 500)
            ax.set_ylim(-50, 500)

        ax.set_aspect('equal', adjustable='box')

        # Grid (ince koyu cizgiler)
        ax.grid(True, linestyle='-', alpha=0.15, color='#555577', linewidth=0.5)
        ax.tick_params(colors='#2b2b3d', length=0)

        # --- ALT LEJANT CUBUGU ---
        kolon_sayisi = len(self.kolonlar)
        kapi_sayisi = sum(1 for m in self.minhalar if m.get('h', 210) >= 180)
        pencere_sayisi = len(self.minhalar) - kapi_sayisi

        legend_elements = []
        if kolon_sayisi > 0:
            legend_elements.append(Line2D([0], [0], marker='s', color='#2b2b3d',
                                          markerfacecolor='white', markeredgecolor='#ccc',
                                          markersize=8, label='Kolon'))
        if kapi_sayisi > 0:
            legend_elements.append(Line2D([0], [0], marker='s', color='#2b2b3d',
                                          markerfacecolor='#8B6914', markeredgecolor='#6B4F12',
                                          markersize=8, label='Kap\u0131'))
        if pencere_sayisi > 0:
            legend_elements.append(Line2D([0], [0], marker='s', color='#2b2b3d',
                                          markerfacecolor='#5599dd', markeredgecolor='#3377bb',
                                          markersize=8, label='Pencere'))
        if self.sonuc_duvarlar:
            legend_elements.append(Line2D([0], [0], marker='s', color='#2b2b3d',
                                          markerfacecolor='#00e5ff', markeredgecolor='#00b8d4',
                                          markersize=8, label='Duvar'))
        if self.m2_yazilari:
            legend_elements.append(Line2D([0], [0], marker='o', color='#2b2b3d',
                                          markerfacecolor='#f1c40f', markeredgecolor='#d4ac0d',
                                          markersize=8, label='m\u00b2'))

        # Oda turu renkleri lejanta ekle
        oda_turleri_mevcut = set()
        for oda in self.oda_isimleri:
            recete = recete_getir(oda['text'])
            oda_turleri_mevcut.add(recete["TUR"])

        tur_lejant = {
            "KURU": ("Sar\u0131: KURU HAC\u0130M", "#f1c40f"),
            "ISLAK": ("Mor: ISLAK HAC\u0130M", "#9b59b6"),
            "MUTFAK": ("Sar\u0131: MUTFAK", "#f1c40f"),
            "KORIDOR": ("Ye\u015fil: KOR\u0130DOR", "#2ecc71"),
        }
        for tur, (etiket, renk) in tur_lejant.items():
            if tur in oda_turleri_mevcut:
                legend_elements.append(Line2D([0], [0], marker='s', color='#2b2b3d',
                                              markerfacecolor=renk, markeredgecolor=renk,
                                              markersize=8, label=etiket))

        if legend_elements:
            leg = ax.legend(handles=legend_elements, loc='lower center',
                            ncol=min(len(legend_elements), 7),
                            fontsize=7, frameon=True,
                            facecolor='#1a1a2e', edgecolor='#555577',
                            labelcolor='white',
                            borderpad=0.6, columnspacing=1.0, handletextpad=0.4,
                            bbox_to_anchor=(0.5, -0.02))
            leg.get_frame().set_alpha(0.9)

        self.canvas.fig.tight_layout(pad=1.5)
        self.canvas.draw()

    def _clear_all(self):
        """Tum verileri temizle"""
        self.kirisler.clear()
        self.duvarlar.clear()
        self.kolonlar.clear()
        self.minhalar.clear()
        self.oda_isimleri.clear()
        self.kat_isimleri.clear()
        self.m2_yazilari.clear()
        self.sonuc_duvarlar.clear()
        self.sap_eslestirme.clear()
        self.imalat_listesi.clear()
        self.tefrisler.clear()
        self.malzeme_ihtiyaclari.clear()
        self.kiris_table.setRowCount(0)
        self.duvar_table.setRowCount(0)
        self.results_table.setRowCount(0)

        # DXF durum etiketini sifirla
        self.dxf_status_label.setText("DXF dosyasi yuklenmedi")
        self.dxf_status_label.setStyleSheet("color: #888; font-style: italic; padding: 5px;")

        # Canvas temizle
        self.canvas.axes.clear()
        self.canvas.axes.set_facecolor('#2b2b3d')
        self.canvas.axes.axis('off')
        self.canvas.draw()

        logger.info("Veriler temizlendi")

    # ═══════════════════════════════════════════════════════════════════════════
    # AUTOCAD CANLI BAĞLANTI METODLARI
    # ═══════════════════════════════════════════════════════════════════════════

    def _autocad_baglan(self):
        """AutoCAD'e COM üzerinden bağlan"""
        if not AUTOCAD_AVAILABLE:
            QMessageBox.critical(
                self, "Hata",
                "AutoCAD bağlantı modülü bulunamadı!\n\n"
                "Çözüm:\n"
                "1. pip install pywin32\n"
                "2. Uygulamayı yeniden başlatın"
            )
            return

        try:
            # Mevcut bağlantıyı kapat
            if self.acad_connector:
                self.acad_connector.baglantıyi_kes()

            # Yeni bağlantı kur
            self.acad_connector = AutoCADConnector()
            self.acad_connector.baglan()

            # UI güncelle
            cizim_adi = self.acad_connector.aktif_cizim.Name
            self.acad_status_label.setText(f"✅ Bağlı: {cizim_adi}")
            self.acad_status_label.setStyleSheet("color: #4CAF50; font-weight: bold; padding: 3px;")

            # Butonları etkinleştir
            self.btn_acad_sec.setEnabled(True)
            self.btn_acad_renk_geri.setEnabled(True)
            self.btn_acad_katman_sec.setEnabled(True)
            self.acad_katman_combo.setEnabled(True)
            self.btn_acad_demir.setEnabled(True)
            self.demir_birim_combo.setEnabled(True)
            self.btn_demir_renk_geri.setEnabled(True)
            self.btn_kolon_grup.setEnabled(True)
            self.btn_kat_ekle.setEnabled(True)

            # Katman listesini doldur
            katmanlar = self.acad_connector.katman_listesi_al()
            self.acad_katman_combo.clear()
            self.acad_katman_combo.addItems(katmanlar)

            # Bağlan butonunu güncelle
            self.btn_acad_baglan.setText("🔄 Yeniden Bağlan")

            logger.info(f"AutoCAD bağlantısı kuruldu: {cizim_adi}")

            QMessageBox.information(
                self, "AutoCAD Bağlantısı",
                f"AutoCAD'e başarıyla bağlanıldı!\n\n"
                f"Çizim: {cizim_adi}\n"
                f"Katman sayısı: {len(katmanlar)}"
            )

        except ConnectionError as e:
            self.acad_status_label.setText("❌ Bağlantı başarısız")
            self.acad_status_label.setStyleSheet("color: #f44336; font-style: italic; padding: 3px;")
            QMessageBox.warning(self, "AutoCAD Bağlantı Hatası", str(e))

        except Exception as e:
            logger.error(f"AutoCAD bağlantı hatası: {e}")
            self.acad_status_label.setText("❌ Hata oluştu")
            self.acad_status_label.setStyleSheet("color: #f44336; font-style: italic; padding: 3px;")
            QMessageBox.critical(
                self, "Hata",
                f"AutoCAD bağlantısı kurulamadı:\n{e}"
            )

    def _autocad_obje_sec(self):
        """AutoCAD ekranında kullanıcıdan obje seçimi al"""
        if not self.acad_connector or not self.acad_connector.bagli:
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return

        try:
            # Kullanıcıya bilgi ver
            QMessageBox.information(
                self, "Obje Seçimi",
                "AutoCAD penceresine geçin ve objeleri seçin.\n\n"
                "Seçimi tamamlamak için ENTER tuşuna basın.\n"
                "İptal için ESC tuşuna basın."
            )

            # Seçimi al
            objeler = self.acad_connector.kullanici_secimi_al(
                "Metraj alınacak objeleri seçin"
            )

            if not objeler:
                QMessageBox.information(self, "Bilgi", "Hiç obje seçilmedi.")
                return

            # Seçilen objeleri kaydet
            self.acad_metraj_objeleri.extend(objeler)

            # Özet hazırla
            tip_sayilari = {}
            toplam_uzunluk = 0.0
            toplam_alan = 0.0

            for obj in objeler:
                tip = obj.entity_type.replace("AcDb", "")
                tip_sayilari[tip] = tip_sayilari.get(tip, 0) + 1
                toplam_uzunluk += obj.uzunluk
                toplam_alan += obj.alan

            ozet = f"Seçilen Objeler ({len(objeler)} adet):\n\n"
            for tip, sayi in tip_sayilari.items():
                ozet += f"  • {tip}: {sayi} adet\n"

            if toplam_uzunluk > 0:
                ozet += f"\nToplam Uzunluk: {toplam_uzunluk:.2f} birim"
            if toplam_alan > 0:
                ozet += f"\nToplam Alan: {toplam_alan:.2f} birim²"

            ozet += "\n\n✅ Seçilen objeler YEŞİL ile işaretlendi."

            QMessageBox.information(self, "Metraj Alındı", ozet)

            # Sonuç tablosuna ekle
            self._autocad_sonuclari_tabloya_ekle(objeler)

        except Exception as e:
            logger.error(f"AutoCAD obje seçim hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Obje seçimi sırasında hata:\n{e}")

    def _autocad_katman_sec(self):
        """Seçili katmandaki tüm objeleri seç"""
        if not self.acad_connector or not self.acad_connector.bagli:
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return

        katman_adi = self.acad_katman_combo.currentText()
        if not katman_adi:
            QMessageBox.warning(self, "Uyarı", "Bir katman seçin!")
            return

        try:
            objeler = self.acad_connector.katmana_gore_sec(katman_adi)

            if not objeler:
                QMessageBox.information(
                    self, "Bilgi",
                    f"'{katman_adi}' katmanında obje bulunamadı."
                )
                return

            self.acad_metraj_objeleri.extend(objeler)

            # Özet
            QMessageBox.information(
                self, "Katman Seçildi",
                f"'{katman_adi}' katmanından {len(objeler)} obje seçildi\n"
                f"ve YEŞİL ile işaretlendi."
            )

            self._autocad_sonuclari_tabloya_ekle(objeler)

        except Exception as e:
            logger.error(f"Katman seçim hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Katman seçimi sırasında hata:\n{e}")

    def _autocad_renkleri_geri_al(self):
        """AutoCAD'de değiştirilen renkleri geri al"""
        if not self.acad_connector:
            return

        try:
            self.acad_connector.renkleri_geri_al()
            QMessageBox.information(
                self, "Bilgi",
                "Tüm obje renkleri orijinal haline döndürüldü."
            )
        except Exception as e:
            logger.error(f"Renk geri alma hatası: {e}")

    def _autocad_demir_metraj(self):
        """
        AutoCAD'den demir metrajı al.

        Kullanıcı demir yazılarını (örn: 10Ø12 L=250) tek tek tıklayarak seçer.
        ENTER'a basınca:
        - Sadece TEXT/MTEXT filtrelenir
        - Demir regex analizi yapılır
        - Geçerli olanlar YEŞİL, geçersizler KIRMIZI boyanır
        - Rapor oluşturulur
        """
        if not self.acad_connector or not self.acad_connector.bagli:
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return

        # Kat seçimi kontrolü
        if not self.aktif_kat_adi:
            QMessageBox.warning(
                self, "Kat Seçimi Gerekli",
                "Önce bir kat eklemeniz gerekiyor!\n\n"
                "1. 'Kat İsmi Girişi' bölümüne kat adını yazın\n"
                "   (Örn: Bodrum Kat, Zemin Kat, 1. Kat)\n"
                "2. '+ Ekle' butonuna tıklayın\n"
                "3. Sonra demir metrajı alabilirsiniz"
            )
            return

        try:
            # Kullanıcıya bilgi ver
            QMessageBox.information(
                self, f"Demir Metrajı - {self.aktif_kat_adi}",
                f"📋 Aktif Kat: {self.aktif_kat_adi}\n\n"
                "AutoCAD penceresine geçin ve DEMİR YAZILARINI seçin.\n\n"
                "Örnek formatlar:\n"
                "  • 10Ø12 L=250\n"
                "  • 5ø16 l=180\n"
                "  • 8Ø10 L=320 cm\n\n"
                "Tek tek tıklayın veya kutu çizin.\n"
                "Seçimi tamamlamak için ENTER tuşuna basın.\n"
                "İptal için ESC tuşuna basın.\n\n"
                "✅ Geçerli demirler YEŞİL\n"
                "❌ Format dışı metinler KIRMIZI olacak"
            )

            # Birim al
            birim = self.demir_birim_combo.currentText()

            # Demir raporunu al
            rapor = self.acad_connector.get_rebar_report_from_selection(
                birim=birim,
                mesaj="Demir yazılarını seçin (TEXT/MTEXT)"
            )

            # Sonuçları kontrol et
            if rapor["secim_sayisi"] == 0:
                QMessageBox.information(self, "Bilgi", "Hiç obje seçilmedi.")
                return

            if rapor["metin_sayisi"] == 0:
                QMessageBox.warning(
                    self, "Uyarı",
                    f"Seçilen {rapor['secim_sayisi']} objeden hiçbiri metin değil!\n"
                    "Lütfen demir yazılarını (TEXT/MTEXT) seçin."
                )
                return

            if not rapor["basarili"]:
                QMessageBox.warning(
                    self, "Format Hatası",
                    f"Seçilen {rapor['metin_sayisi']} metin objesi var,\n"
                    "ancak hiçbiri demir formatına uymuyor!\n\n"
                    "Beklenen format: AdedØÇap L=Boy\n"
                    "Örnek: 10Ø12 L=250"
                )
                return

            # Başarılı sonuç mesajı
            ozet = f"DEMİR METRAJ RAPORU\n"
            ozet += f"{'='*40}\n\n"
            ozet += f"Seçilen obje     : {rapor['secim_sayisi']}\n"
            ozet += f"Metin objesi     : {rapor['metin_sayisi']}\n"
            ozet += f"✅ Geçerli demir : {len(rapor['basarili'])}\n"
            ozet += f"❌ Format dışı   : {len(rapor['basarisiz'])}\n\n"
            ozet += f"{'─'*40}\n"
            ozet += f"TOPLAM DEMİR     : {rapor['toplam_adet']:,} adet\n"
            ozet += f"TOPLAM BOY       : {rapor['toplam_boy_m']:,.2f} m\n"
            ozet += f"TOPLAM AĞIRLIK   : {rapor['toplam_agirlik_kg']:,.2f} kg\n"
            ozet += f"                 : {rapor['toplam_agirlik_kg']/1000:,.3f} ton\n"
            ozet += f"{'─'*40}\n"
            # Çubuk adedi (1 çubuk = 12m) - yukarı yuvarla
            toplam_cubuk = rapor.get('toplam_cubuk', math.ceil(rapor['toplam_boy_m'] / 12.0))
            ozet += f"📦 ÇUBUK (12m)   : {int(toplam_cubuk):,} çubuk\n\n"

            # Çap bazlı özet
            ozet += f"ÇAP BAZLI DAĞILIM:\n"
            ozet += f"{'─'*40}\n"
            for cap in sorted(rapor["cap_ozeti"].keys()):
                data = rapor["cap_ozeti"][cap]
                cubuk = data.get('cubuk_adet', math.ceil(data['boy_m'] / 12.0))
                ozet += f"Ø{cap:2d}: {data['adet']:>5,} ad, "
                ozet += f"{data['boy_m']:>7,.1f} m, "
                ozet += f"{data['agirlik_kg']:>8,.1f} kg, "
                ozet += f"{int(cubuk):>5,} çubuk\n"

            QMessageBox.information(self, f"Demir Metraj - {self.aktif_kat_adi}", ozet)

            # Sonuçları aktif kata ekle
            for kat_data in self.demir_kat_verileri:
                if kat_data["kat_adi"] == self.aktif_kat_adi:
                    kat_data["demirler"].extend(rapor["basarili"])
                    kat_data["rapor"] = rapor
                    break

            # Kat listesini güncelle
            self._demir_kat_listesini_guncelle()

            # Excel butonunu etkinleştir
            self.btn_demir_excel.setEnabled(True)

            logger.info(f"'{self.aktif_kat_adi}' katına {len(rapor['basarili'])} demir eklendi")

        except Exception as e:
            logger.error(f"Demir metraj hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Demir metrajı alınırken hata:\n{e}")

    def _autocad_dusay_eleman_hesapla(self):
        """
        Birleşik Düşey Eleman (Kolon/Perde) Demir Hesaplama.

        Akıllı Tekil/Grup Ayrımı:
        - TEKİL MOD: Sadece başlık + donatı seçilirse (PB055 + 2x8Ø12 L=420)
        - GRUP MOD: Başlık + liste + donatı seçilirse (SB17 + SB24,SB31 + 28Ø14 L=442)

        Perde "2x" formatı desteklenir: 2x8Ø12 = 16 adet Ø12
        """
        if not self.acad_connector or not self.acad_connector.bagli:
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return

        # Kat seçimi kontrolü
        if not self.aktif_kat_adi:
            QMessageBox.warning(
                self, "Kat Seçimi Gerekli",
                "Önce bir kat eklemeniz gerekiyor!\n\n"
                "1. 'Kat İsmi Girişi' bölümüne kat adını yazın\n"
                "2. '+ Ekle' butonuna tıklayın\n"
                "3. Sonra hesaplama yapabilirsiniz"
            )
            return

        try:
            # Kullanıcıya bilgi ver
            QMessageBox.information(
                self, f"Kolon/Perde Hesaplama - {self.aktif_kat_adi}",
                f"📋 Aktif Kat: {self.aktif_kat_adi}\n\n"
                "AutoCAD'de metinleri seçin:\n\n"
                "🔷 GRUP MOD (Benzer elemanlar):\n"
                "   • BAŞLIK: 'SB17 (65/65) KOLON DETAYI'\n"
                "   • LİSTE: 'SB24,SB31,SB39' (virgüllü)\n"
                "   • DONATI: '28Ø14 L=442'\n\n"
                "🔶 TEKİL MOD (Tek perde/kolon):\n"
                "   • BAŞLIK: 'PB055' veya 'SB17'\n"
                "   • DONATI: '2x8Ø12 L=420' (çarpanlı da olur)\n\n"
                "Seçim sırası önemli DEĞİL!\n"
                "ENTER ile bitir, ESC ile iptal."
            )

            # ÖNEMLİ: Kullanıcının AutoCAD'e geçmesi için uyarı
            reply = QMessageBox.question(
                self, "AutoCAD'e Geçin",
                "⚠️ ŞİMDİ AUTOCAD PENCERESİNE GEÇİN!\n\n"
                "1. Bu mesajı okuduktan sonra 'Yes' tıklayın\n"
                "2. Hemen AutoCAD penceresine tıklayın\n"
                "3. Metinleri seçip ENTER'a basın\n\n"
                "AutoCAD'e geçmeye hazır mısınız?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )

            if reply == QMessageBox.StandardButton.No:
                return

            # Birim al
            birim = self.demir_birim_combo.currentText()

            # Birleşik hesaplama fonksiyonunu çağır
            sonuc = self.acad_connector.calculate_vertical_rebar_unified(birim=birim)

            # Hata kontrolü
            if sonuc["hata"]:
                QMessageBox.warning(
                    self, "Hesaplama Hatası",
                    f"Hesaplama yapılamadı:\n\n{sonuc['hata']}"
                )
                return

            if not sonuc["basarili"]:
                QMessageBox.warning(self, "Uyarı", "Hesaplama başarısız oldu.")
                return

            # Özet bilgiler
            ozet = sonuc["ozet"]
            gruplar = sonuc.get("gruplar", [])
            mod = sonuc["mod"]

            # Sonuç mesajı oluştur
            mesaj = f"DEMİR METRAJ RAPORU ({mod} MOD)\n"
            mesaj += f"{'='*50}\n\n"
            mesaj += f"📍 Kat: {self.aktif_kat_adi}\n\n"

            # Grup detayları göster
            mesaj += f"📋 SEÇİLEN ELEMANLAR ({len(gruplar)} grup):\n"
            mesaj += f"{'─'*50}\n"

            for i, grup in enumerate(gruplar, 1):
                lider = grup["lider"]
                tip = grup["tip"]
                benzerler = grup["benzerler"]
                donati_sayisi = len(grup["donatilar"])

                if benzerler:
                    mesaj += f"{i}. {lider} ({tip}) + {len(benzerler)} benzer\n"
                    mesaj += f"   Benzerler: {', '.join(benzerler[:5])}{'...' if len(benzerler)>5 else ''}\n"
                else:
                    mesaj += f"{i}. {lider} ({tip}) - TEKİL\n"
                mesaj += f"   Donatı: {donati_sayisi} satır\n\n"

            mesaj += f"{'─'*50}\n\n"

            mesaj += f"TOPLAM DEMİR     : {ozet['toplam_adet']:,} adet\n"
            mesaj += f"TOPLAM BOY       : {ozet['toplam_boy_m']:,.2f} m\n"
            mesaj += f"TOPLAM AĞIRLIK   : {ozet['toplam_agirlik_kg']:,.2f} kg\n"
            mesaj += f"                 : {ozet['toplam_agirlik_ton']:,.3f} ton\n"
            mesaj += f"{'─'*50}\n"

            # Çap bazlı çubuk adetleri
            mesaj += f"\n📦 ÇUBUK ADETLERİ (12m):\n"
            for cap in sorted(ozet["cap_ozeti"].keys()):
                cap_bilgi = ozet["cap_ozeti"][cap]
                mesaj += f"   Ø{cap}: {cap_bilgi['cubuk_adet']:,} çubuk\n"
            mesaj += f"\n   TOPLAM: {ozet['cubuk_adet']:,} çubuk\n"

            QMessageBox.information(self, f"Hesaplama - {self.aktif_kat_adi}", mesaj)

            # DemirBilgisi listesini aktif kata ekle
            demirler = sonuc["demirler"]

            for demir in demirler:
                # Aktif kata ekle
                for kat_data in self.demir_kat_verileri:
                    if kat_data["kat_adi"] == self.aktif_kat_adi:
                        kat_data["demirler"].append(demir)
                        break

            # Kat listesini güncelle
            self._demir_kat_listesini_guncelle()

            # Excel butonunu etkinleştir
            self.btn_demir_excel.setEnabled(True)

            elemanlar = sonuc.get("elemanlar", [])
            tip = sonuc.get("tip", "")
            logger.info(f"'{self.aktif_kat_adi}' katına {len(demirler)} demir eklendi ({mod} mod, {len(elemanlar)} {tip.lower()})")

        except Exception as e:
            logger.error(f"Düşey eleman hesaplama hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Hesaplama sırasında hata:\n{e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # SEKME VE KAT YÖNETİMİ METODLARI
    # ═══════════════════════════════════════════════════════════════════════════

    def _sekme_degisti(self, index: int):
        """Sekme değiştiğinde görünürlük ayarla"""
        # index 0 = İnce İşler, index 1 = Demir Metrajı
        ince_isler_aktif = (index == 0)

        # Genel Ayarlar sadece İnce İşler'de görünsün
        self.settings_group.setVisible(ince_isler_aktif)

        # Sağ panel (Matplotlib) sadece İnce İşler'de görünsün
        self.right_panel.setVisible(ince_isler_aktif)

    def _demir_kat_ekle(self):
        """Demir metrajı için yeni kat ekle"""
        kat_adi = self.demir_kat_input.text().strip()

        if not kat_adi:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir kat ismi girin!")
            return

        # Aynı isimde kat var mı kontrol et
        for kat_data in self.demir_kat_verileri:
            if kat_data["kat_adi"].lower() == kat_adi.lower():
                QMessageBox.warning(self, "Uyarı", f"'{kat_adi}' isimli kat zaten mevcut!")
                return

        # Yeni kat ekle
        yeni_kat = {
            "kat_adi": kat_adi,
            "demirler": [],
            "rapor": None
        }
        self.demir_kat_verileri.append(yeni_kat)

        # Listeye ekle
        self.demir_kat_listesi.addItem(f"📋 {kat_adi} (0 demir)")

        # Input'u temizle
        self.demir_kat_input.clear()

        # Yeni eklenen katı seç
        self.demir_kat_listesi.setCurrentRow(self.demir_kat_listesi.count() - 1)
        self.aktif_kat_adi = kat_adi

        # Silme butonunu etkinleştir
        self.btn_kat_sil.setEnabled(True)

        logger.info(f"Yeni kat eklendi: {kat_adi}")

    def _demir_kat_sil(self):
        """Seçili katı sil"""
        current_row = self.demir_kat_listesi.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz katı seçin!")
            return

        kat_adi = self.demir_kat_verileri[current_row]["kat_adi"]

        # Onay al
        reply = QMessageBox.question(
            self, "Kat Silme Onayı",
            f"'{kat_adi}' katını ve tüm demir verilerini silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Listeden sil
            self.demir_kat_listesi.takeItem(current_row)
            del self.demir_kat_verileri[current_row]

            # Aktif kat güncelle
            if self.demir_kat_verileri:
                self.demir_kat_listesi.setCurrentRow(0)
                self.aktif_kat_adi = self.demir_kat_verileri[0]["kat_adi"]
            else:
                self.aktif_kat_adi = ""
                self.btn_kat_sil.setEnabled(False)

            logger.info(f"Kat silindi: {kat_adi}")

    def _demir_kat_secildi(self, item):
        """Kat listesinden bir kat seçildi"""
        current_row = self.demir_kat_listesi.currentRow()
        if current_row >= 0 and current_row < len(self.demir_kat_verileri):
            self.aktif_kat_adi = self.demir_kat_verileri[current_row]["kat_adi"]
            self.btn_kat_sil.setEnabled(True)
            logger.info(f"Aktif kat değişti: {self.aktif_kat_adi}")

    def _demir_kat_listesini_guncelle(self):
        """Kat listesini güncelle (demir sayılarıyla)"""
        self.demir_kat_listesi.clear()
        for kat_data in self.demir_kat_verileri:
            demir_sayisi = len(kat_data["demirler"])
            toplam_agirlik = sum(d.toplam_agirlik for d in kat_data["demirler"]) if kat_data["demirler"] else 0
            self.demir_kat_listesi.addItem(
                f"📋 {kat_data['kat_adi']} ({demir_sayisi} demir, {toplam_agirlik:.1f} kg)"
            )

    def _demir_excel_export(self):
        """Demir metraj verilerini Excel'e aktar (her kat ayrı sayfa)"""
        if not self.demir_kat_verileri:
            QMessageBox.warning(self, "Uyarı", "Henüz demir metrajı alınmış kat yok!")
            return

        # Veri olan katları kontrol et
        veri_olan_katlar = [k for k in self.demir_kat_verileri if k["demirler"]]
        if not veri_olan_katlar:
            QMessageBox.warning(self, "Uyarı", "Hiçbir katta demir verisi yok!")
            return

        if not PANDAS_AVAILABLE:
            QMessageBox.warning(self, "Uyarı", "Excel export için pandas gerekli!")
            return

        # Dosya kaydetme dialogu
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Demir Metrajı Kaydet",
            "Demir_Metraji.xlsx",
            "Excel Dosyası (*.xlsx)"
        )

        if not file_path:
            return

        try:
            # Excel writer oluştur
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                genel_toplam_adet = 0
                genel_toplam_boy = 0.0
                genel_toplam_agirlik = 0.0

                for kat_data in self.demir_kat_verileri:
                    if not kat_data["demirler"]:
                        continue

                    kat_adi = kat_data["kat_adi"]
                    # Excel sayfa adı max 31 karakter
                    sayfa_adi = kat_adi[:31] if len(kat_adi) > 31 else kat_adi

                    # DataFrame oluştur (1 çubuk = 12m) - yukarı yuvarla
                    CUBUK_BOYU = 12.0
                    rows = []
                    for d in kat_data["demirler"]:
                        rows.append({
                            "Poz/Metin": d.orijinal_metin,
                            "Adet": d.adet,
                            "Çap (mm)": d.cap,
                            "Boy (cm)": d.boy,
                            "Toplam Boy (m)": d.toplam_boy,
                            "Birim Ağırlık (kg/m)": d.agirlik_birim,
                            "Toplam Ağırlık (kg)": d.toplam_agirlik,
                            "Çubuk Adedi (12m)": math.ceil(d.toplam_boy / CUBUK_BOYU),
                        })

                    df = pd.DataFrame(rows)

                    # Toplam satırı ekle
                    toplam_adet = sum(d.adet for d in kat_data["demirler"])
                    toplam_boy = sum(d.toplam_boy for d in kat_data["demirler"])
                    toplam_agirlik = sum(d.toplam_agirlik for d in kat_data["demirler"])
                    toplam_cubuk = math.ceil(toplam_boy / CUBUK_BOYU)

                    toplam_row = pd.DataFrame([{
                        "Poz/Metin": "TOPLAM",
                        "Adet": toplam_adet,
                        "Çap (mm)": "-",
                        "Boy (cm)": "-",
                        "Toplam Boy (m)": round(toplam_boy, 2),
                        "Birim Ağırlık (kg/m)": "-",
                        "Toplam Ağırlık (kg)": round(toplam_agirlik, 2),
                        "Çubuk Adedi (12m)": toplam_cubuk,
                    }])

                    df = pd.concat([df, toplam_row], ignore_index=True)

                    # Sayfaya yaz
                    df.to_excel(writer, sheet_name=sayfa_adi, index=False)

                    # Genel toplamlara ekle
                    genel_toplam_adet += toplam_adet
                    genel_toplam_boy += toplam_boy
                    genel_toplam_agirlik += toplam_agirlik

                # ÖZET sayfası ekle - çap bazlı çubuk adetleri
                # Önce tüm çapları topla
                tum_caplar = set()
                for kat_data in self.demir_kat_verileri:
                    for d in kat_data["demirler"]:
                        tum_caplar.add(d.cap)
                tum_caplar = sorted(tum_caplar)  # Küçükten büyüğe sırala

                # Genel çap bazlı toplamlar
                genel_cap_boy = {cap: 0.0 for cap in tum_caplar}

                ozet_rows = []
                for kat_data in self.demir_kat_verileri:
                    if not kat_data["demirler"]:
                        continue
                    toplam_adet = sum(d.adet for d in kat_data["demirler"])
                    toplam_boy = sum(d.toplam_boy for d in kat_data["demirler"])
                    toplam_agirlik = sum(d.toplam_agirlik for d in kat_data["demirler"])

                    # Çap bazlı boy hesapla (bu kat için)
                    cap_boy = {cap: 0.0 for cap in tum_caplar}
                    for d in kat_data["demirler"]:
                        cap_boy[d.cap] += d.toplam_boy
                        genel_cap_boy[d.cap] += d.toplam_boy

                    row_data = {
                        "Kat": kat_data["kat_adi"],
                        "Demir Adedi": toplam_adet,
                        "Toplam Boy (m)": round(toplam_boy, 2),
                        "Toplam Ağırlık (kg)": round(toplam_agirlik, 2),
                        "Toplam Ağırlık (ton)": round(toplam_agirlik / 1000, 3),
                    }
                    # Çap bazlı çubuk adetleri ekle
                    for cap in tum_caplar:
                        cubuk_adet = math.ceil(cap_boy[cap] / 12.0) if cap_boy[cap] > 0 else 0
                        row_data[f"Ø{cap} Çubuk"] = cubuk_adet

                    ozet_rows.append(row_data)

                # Genel toplam satırı
                genel_toplam_row = {
                    "Kat": "GENEL TOPLAM",
                    "Demir Adedi": genel_toplam_adet,
                    "Toplam Boy (m)": round(genel_toplam_boy, 2),
                    "Toplam Ağırlık (kg)": round(genel_toplam_agirlik, 2),
                    "Toplam Ağırlık (ton)": round(genel_toplam_agirlik / 1000, 3),
                }
                # Genel çap bazlı çubuk adetleri
                for cap in tum_caplar:
                    cubuk_adet = math.ceil(genel_cap_boy[cap] / 12.0) if genel_cap_boy[cap] > 0 else 0
                    genel_toplam_row[f"Ø{cap} Çubuk"] = cubuk_adet

                ozet_rows.append(genel_toplam_row)

                ozet_df = pd.DataFrame(ozet_rows)
                ozet_df.to_excel(writer, sheet_name="ÖZET", index=False)

            QMessageBox.information(
                self, "Başarılı",
                f"Demir metrajı Excel'e aktarıldı!\n\n"
                f"Dosya: {file_path}\n\n"
                f"Toplam {len(veri_olan_katlar)} kat + 1 özet sayfası"
            )

            logger.info(f"Demir metrajı Excel'e aktarıldı: {file_path}")

        except Exception as e:
            logger.error(f"Excel export hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Excel kaydedilirken hata:\n{e}")

    def _autocad_sonuclari_tabloya_ekle(self, objeler: list):
        """AutoCAD'den alınan objeleri sonuç tablosuna ekle"""
        for obj in objeler:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)

            # Obje tipi
            tip = obj.entity_type.replace("AcDb", "")
            self.results_table.setItem(row, 0, QTableWidgetItem(f"[CAD] {tip}"))

            # Katman
            self.results_table.setItem(row, 1, QTableWidgetItem(obj.layer))

            # Detay (blok adı, metin içeriği veya geometri)
            detay = ""
            if obj.blok_adi:
                detay = f"Blok: {obj.blok_adi}"
            elif obj.text_icerigi:
                detay = f"Metin: {obj.text_icerigi[:30]}"
            elif obj.uzunluk > 0:
                detay = f"Uzunluk: {obj.uzunluk:.2f}"
            self.results_table.setItem(row, 2, QTableWidgetItem(detay))

            # Boyut/Alan
            if obj.alan > 0:
                self.results_table.setItem(row, 3, QTableWidgetItem(f"{obj.alan:.2f}"))
            elif obj.uzunluk > 0:
                self.results_table.setItem(row, 3, QTableWidgetItem(f"{obj.uzunluk:.2f}"))
            else:
                self.results_table.setItem(row, 3, QTableWidgetItem("-"))

            # Handle (referans için)
            self.results_table.setItem(row, 4, QTableWidgetItem(obj.handle))

            # Satır rengini yeşil yap (metrajı alındığını göstermek için)
            for col in range(5):
                item = self.results_table.item(row, col)
                if item:
                    item.setBackground(QColor(46, 125, 50, 80))  # Yarı saydam yeşil

    def _load_demo_data(self):
        """Demo verilerini yukle"""
        # Demo kirisler
        demo_kirisler = [
            {"id": "K101", "h": 60, "x1": 0, "y1": 400, "x2": 400, "y2": 370},
            {"id": "K102", "h": 50, "x1": 370, "y1": 370, "x2": 400, "y2": 0}
        ]

        for k in demo_kirisler:
            geo = Polygon([
                (k["x1"], k["y1"]), (k["x2"], k["y1"]),
                (k["x2"], k["y2"]), (k["x1"], k["y2"])
            ])
            kiris = {
                "id": k["id"],
                "layer": f"S_KIRIS_H{k['h']}",
                "h": k["h"],
                "geo": geo,
                "coords": f"({k['x1']},{k['y1']})-({k['x2']},{k['y2']})"
            }
            self.kirisler.append(kiris)

            row = self.kiris_table.rowCount()
            self.kiris_table.insertRow(row)
            self.kiris_table.setItem(row, 0, QTableWidgetItem(k["id"]))
            self.kiris_table.setItem(row, 1, QTableWidgetItem(f"{k['h']} cm"))
            self.kiris_table.setItem(row, 2, QTableWidgetItem(kiris["coords"]))

        # Demo duvarlar
        demo_duvarlar = [
            {"id": "D1", "kalinlik": "20 cm", "x1": 0, "y1": 390, "x2": 380, "y2": 370},
            {"id": "D2", "kalinlik": "20 cm", "x1": 370, "y1": 370, "x2": 390, "y2": 10},
            {"id": "D3", "kalinlik": "20 cm", "x1": 0, "y1": 20, "x2": 370, "y2": 0}
        ]

        for d in demo_duvarlar:
            geo = Polygon([
                (d["x1"], d["y1"]), (d["x2"], d["y1"]),
                (d["x2"], d["y2"]), (d["x1"], d["y2"])
            ])
            duvar = {
                "id": d["id"],
                "layer": f"M_DUVAR_TUGLA_{d['kalinlik'].split()[0]}",
                "kalinlik": d["kalinlik"],
                "geo": geo,
                "coords": f"({d['x1']},{d['y1']})-({d['x2']},{d['y2']})"
            }
            self.duvarlar.append(duvar)

            row = self.duvar_table.rowCount()
            self.duvar_table.insertRow(row)
            self.duvar_table.setItem(row, 0, QTableWidgetItem(d["id"]))
            self.duvar_table.setItem(row, 1, QTableWidgetItem(d["kalinlik"]))
            self.duvar_table.setItem(row, 2, QTableWidgetItem(duvar["coords"]))

        # Otomatik hesapla
        self._calculate_and_visualize()

    def _load_dxf_file(self):
        """DXF dosyasi yukle ve kiris/duvar katmanlarini tespit et"""
        if not EZDXF_AVAILABLE:
            QMessageBox.critical(
                self, "Hata",
                "ezdxf kutuphanesi yuklu degil!\n\npip install ezdxf"
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "DXF Dosyasi Sec",
            "",
            "DXF Dosyalari (*.dxf);;Tum Dosyalar (*)"
        )

        if not file_path:
            return

        try:
            doc = ezdxf.readfile(file_path)
            msp = doc.modelspace()

            # Katmanlari listele
            katmanlar = [layer.dxf.name for layer in doc.layers]
            logger.info(f"DXF yuklendi: {file_path}, {len(katmanlar)} katman bulundu")

            # Kiris, duvar, kolon ve minha katmanlarini otomatik tespit et
            kiris_katmanlari = []
            duvar_katmanlari = []
            kolon_katmanlari = []
            minha_katmanlari = []

            kiris_patterns = ['kiris', 'kiri', 'beam', 's_kiris', 'struc.*beam', 'k-']
            duvar_patterns = ['duvar', 'wall', 'm_duvar', 'a-wall', 'mim.*duvar', 'd-']
            kolon_patterns = ['kolon', 'column', 's_kolon', 'col', 'struc.*col', 'c-', 'sutun']
            minha_patterns = ['minha', 'pencere', 'kapi', 'window', 'door', 'm_minha', 'aciklik']

            for katman in katmanlar:
                katman_lower = katman.lower()
                # Kiris kontrolu
                for pattern in kiris_patterns:
                    if re.search(pattern, katman_lower):
                        kiris_katmanlari.append(katman)
                        break
                # Duvar kontrolu
                for pattern in duvar_patterns:
                    if re.search(pattern, katman_lower):
                        duvar_katmanlari.append(katman)
                        break
                # Kolon kontrolu
                for pattern in kolon_patterns:
                    if re.search(pattern, katman_lower):
                        kolon_katmanlari.append(katman)
                        break
                # Minha (kapi/pencere) kontrolu
                for pattern in minha_patterns:
                    if re.search(pattern, katman_lower):
                        minha_katmanlari.append(katman)
                        break

            # Kolon katmanlarini sakla (dialog sonrasi yuklenecek)
            self._kolon_katmanlari_temp = kolon_katmanlari
            logger.info(f"Kolon katmanlari tespit edildi: {kolon_katmanlari}")

            # Text layerlarini tespit et (oda/kat/m2 isimleri icin)
            text_katmanlari = []
            oda_varsayilan = []
            kat_varsayilan = []
            m2_varsayilan = []

            oda_patterns = ['oda', 'room', 'mekan', 'a_oda', 'a-room']
            kat_patterns = ['kat', 'floor', 'a_kat', 'a-floor', 'storey']
            m2_patterns = ['m2', 'alan', 'area', 'sap', 'a_m2', 'a-m2', 'metrekare']

            # TEXT ve MTEXT iceren katmanlari bul
            text_katman_set = set()
            for entity in msp.query('TEXT MTEXT'):
                try:
                    text_katman_set.add(entity.dxf.layer)
                except:
                    pass
            text_katmanlari = sorted(list(text_katman_set))

            # Varsayilan oda/kat/m2 katmanlarini tespit et
            for katman in text_katmanlari:
                katman_lower = katman.lower()
                for pattern in oda_patterns:
                    if pattern in katman_lower:
                        oda_varsayilan.append(katman)
                        break
                for pattern in kat_patterns:
                    if pattern in katman_lower:
                        kat_varsayilan.append(katman)
                        break
                for pattern in m2_patterns:
                    if pattern in katman_lower:
                        m2_varsayilan.append(katman)
                        break

            # Katman secim dialogunu goster
            dialog = DXFKatmanSecimDialog(
                self, katmanlar, kiris_katmanlari, duvar_katmanlari, minha_katmanlari,
                text_katmanlari, oda_varsayilan, kat_varsayilan, m2_varsayilan
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                secilen_kiris = dialog.get_selected_kiris()
                secilen_duvar = dialog.get_selected_duvar()
                secilen_minha = dialog.get_selected_minha()
                secilen_oda = dialog.get_selected_oda()
                secilen_kat = dialog.get_selected_kat()
                secilen_m2 = dialog.get_selected_m2()
                cizim_birimi = dialog.get_cizim_birimi()
                use_hesap_siniri = dialog.get_use_hesap_siniri()

                # Duvar cinsini al ve sakla (nalbur siparisi icin)
                self.duvar_cinsi = dialog.get_duvar_cinsi()
                logger.info(f"Secilen duvar cinsi: {self.duvar_cinsi}")

                # HESAP_SINIRI katmanindan sinir kutusunu al
                hesap_kutusu = None
                if use_hesap_siniri:
                    hesap_kutusu = self._get_hesap_siniri(msp, cizim_birimi)
                    if hesap_kutusu:
                        logger.info("HESAP_SINIRI bulundu, sadece cerceve ici taranacak")
                    else:
                        logger.warning("HESAP_SINIRI bulunamadi, tum proje taranacak")

                # Mevcut verileri temizle
                self._clear_all()

                # DXF'den verileri yukle (HESAP_SINIRI filtresiyle)
                self._parse_dxf_kirisler(msp, secilen_kiris, cizim_birimi, hesap_kutusu)
                self._parse_dxf_duvarlar(msp, secilen_duvar, cizim_birimi, hesap_kutusu)
                self._parse_dxf_kolonlar(msp, self._kolon_katmanlari_temp, cizim_birimi, hesap_kutusu)  # Kolonlar
                self._parse_dxf_minhalar(msp, doc, secilen_minha, cizim_birimi, hesap_kutusu)
                self._parse_dxf_oda_isimleri(msp, secilen_oda, cizim_birimi, hesap_kutusu)
                self._parse_dxf_kat_isimleri(msp, secilen_kat, cizim_birimi, hesap_kutusu)
                self._parse_dxf_m2_yazilari(msp, secilen_m2, cizim_birimi, hesap_kutusu)

                # Tefris bloklarini tara
                self._parse_dxf_tefrisler(msp, cizim_birimi, hesap_kutusu)

                # M2-Oda eslestirmesi yap
                if self.m2_yazilari and self.oda_isimleri:
                    self._eslesitir_m2_oda()
                    # Imalat listesi ve malzeme ihtiyaclari olustur
                    self._hesapla_imalat_listesi()

                # Durum etiketini guncelle
                dosya_adi = Path(file_path).name
                sinir_durumu = " (HESAP_SINIRI aktif)" if hesap_kutusu else ""
                kolon_bilgi = f", {len(self.kolonlar)} kolon" if self.kolonlar else ""
                oda_bilgi = f", {len(self.oda_isimleri)} oda" if self.oda_isimleri else ""
                kat_bilgi = f", {len(self.kat_isimleri)} kat" if self.kat_isimleri else ""
                m2_bilgi = f", {len(self.m2_yazilari)} m2" if self.m2_yazilari else ""
                toplam_m2 = sum(m['deger'] for m in self.m2_yazilari) if self.m2_yazilari else 0
                m2_toplam = f" (Toplam: {toplam_m2:.1f}m²)" if toplam_m2 > 0 else ""

                self.dxf_status_label.setText(
                    f"✅ {dosya_adi} | "
                    f"{len(self.kirisler)} kiris, {len(self.duvarlar)} duvar{kolon_bilgi}, "
                    f"{len(self.minhalar)} minha{oda_bilgi}{kat_bilgi}{m2_bilgi}{m2_toplam}{sinir_durumu}"
                )
                self.dxf_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

                # Otomatik hesapla ve gorsellestir
                if self.duvarlar or self.m2_yazilari:
                    self._calculate_and_visualize()

                logger.info(f"DXF yukleme tamamlandi: {len(self.kirisler)} kiris, {len(self.duvarlar)} duvar, {len(self.kolonlar)} kolon, {len(self.minhalar)} minha, {len(self.oda_isimleri)} oda, {len(self.kat_isimleri)} kat, {len(self.m2_yazilari)} m2")

        except Exception as e:
            logger.error(f"DXF yukleme hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"DXF dosyasi yuklenemedi:\n{str(e)}")

    def _get_hesap_siniri(self, msp, birim: str = "cm"):
        """HESAP_SINIRI katmanindan sinir kutusunu al"""
        try:
            sinir_entities = list(msp.query('LWPOLYLINE[layer=="HESAP_SINIRI"]'))
            if not sinir_entities:
                return None

            # Ilk LWPOLYLINE'i al
            entity = sinir_entities[0]
            with entity.points("xy") as pts:
                noktalar = list(pts)

            if len(noktalar) < 3:
                return None

            # Bounding box hesapla
            xs = [p[0] for p in noktalar]
            ys = [p[1] for p in noktalar]
            min_x, min_y = min(xs), min(ys)
            max_x, max_y = max(xs), max(ys)

            # Birim donusumu
            if birim == "m":
                min_x, min_y = min_x * 100, min_y * 100
                max_x, max_y = max_x * 100, max_y * 100
            elif birim == "mm":
                min_x, min_y = min_x / 10, min_y / 10
                max_x, max_y = max_x / 10, max_y / 10

            # Sinir kutusu olustur
            return create_box(min_x, min_y, max_x, max_y)

        except Exception as e:
            logger.warning(f"HESAP_SINIRI okuma hatasi: {e}")
            return None

    def _is_inside_boundary(self, geo, hesap_kutusu) -> bool:
        """Geometri sinir kutusunun icinde mi?"""
        if hesap_kutusu is None:
            return True  # Sinir yok, hepsi gecerli

        try:
            if SHAPELY_AVAILABLE:
                return hesap_kutusu.contains(geo)
            else:
                # SimplePolygon icin basit kontrol
                return hesap_kutusu.contains(geo)
        except:
            return True  # Hata durumunda kabul et

    def _parse_dxf_kirisler(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den kiris verilerini parse et"""
        kiris_sayaci = 1

        for katman_adi in katman_listesi:
            # Kiris yuksekligini katman adından cikar
            h = self._extract_kiris_height(katman_adi)

            # LWPOLYLINE entity'lerini al
            for entity in msp.query(f'LWPOLYLINE[layer=="{katman_adi}"]'):
                try:
                    with entity.points("xy") as pts:
                        noktalar = list(pts)

                    if len(noktalar) < 2:
                        continue

                    # Bounding box hesapla
                    xs = [p[0] for p in noktalar]
                    ys = [p[1] for p in noktalar]
                    x1, y1 = min(xs), min(ys)
                    x2, y2 = max(xs), max(ys)

                    # Birim donusumu (metre'ye cevir, sonra gorsellestirme icin cm'ye)
                    if birim == "m":
                        x1, y1, x2, y2 = x1 * 100, y1 * 100, x2 * 100, y2 * 100
                    elif birim == "mm":
                        x1, y1, x2, y2 = x1 / 10, y1 / 10, x2 / 10, y2 / 10
                    # cm ise degisiklik yok

                    # Shapely varsa kullan, yoksa SimplePolygon
                    if SHAPELY_AVAILABLE:
                        geo = ShapelyPolygon([(p[0], p[1]) for p in noktalar])
                        # Birim donusumu uygula
                        if birim == "m":
                            geo = ShapelyPolygon([(p[0]*100, p[1]*100) for p in noktalar])
                        elif birim == "mm":
                            geo = ShapelyPolygon([(p[0]/10, p[1]/10) for p in noktalar])
                    else:
                        geo = Polygon([
                            (x1, y1), (x2, y1), (x2, y2), (x1, y2)
                        ])

                    # HESAP_SINIRI filtresi
                    if not self._is_inside_boundary(geo, hesap_kutusu):
                        continue

                    kiris = {
                        "id": f"K{kiris_sayaci:03d}",
                        "layer": katman_adi,
                        "h": h,
                        "geo": geo,
                        "coords": f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})"
                    }
                    self.kirisler.append(kiris)

                    # Tabloya ekle
                    row = self.kiris_table.rowCount()
                    self.kiris_table.insertRow(row)
                    self.kiris_table.setItem(row, 0, QTableWidgetItem(kiris["id"]))
                    self.kiris_table.setItem(row, 1, QTableWidgetItem(f"{h} cm"))
                    self.kiris_table.setItem(row, 2, QTableWidgetItem(kiris["coords"]))

                    kiris_sayaci += 1
                except Exception as e:
                    logger.warning(f"Kiris entity okuma hatasi: {e}")
                    continue

            # LINE entity'lerini de kontrol et
            for entity in msp.query(f'LINE[layer=="{katman_adi}"]'):
                try:
                    start = entity.dxf.start
                    end = entity.dxf.end

                    x1, y1 = start.x, start.y
                    x2, y2 = end.x, end.y

                    # Birim donusumu
                    if birim == "m":
                        x1, y1, x2, y2 = x1 * 100, y1 * 100, x2 * 100, y2 * 100
                    elif birim == "mm":
                        x1, y1, x2, y2 = x1 / 10, y1 / 10, x2 / 10, y2 / 10

                    # Kiris genisligi varsayilan 30cm
                    kiris_genislik = 30
                    geo = Polygon([
                        (x1, y1 - kiris_genislik/2), (x2, y1 - kiris_genislik/2),
                        (x2, y2 + kiris_genislik/2), (x1, y2 + kiris_genislik/2)
                    ])

                    kiris = {
                        "id": f"K{kiris_sayaci:03d}",
                        "layer": katman_adi,
                        "h": h,
                        "geo": geo,
                        "coords": f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})"
                    }
                    self.kirisler.append(kiris)

                    row = self.kiris_table.rowCount()
                    self.kiris_table.insertRow(row)
                    self.kiris_table.setItem(row, 0, QTableWidgetItem(kiris["id"]))
                    self.kiris_table.setItem(row, 1, QTableWidgetItem(f"{h} cm"))
                    self.kiris_table.setItem(row, 2, QTableWidgetItem(kiris["coords"]))

                    kiris_sayaci += 1
                except Exception as e:
                    logger.warning(f"Kiris LINE entity okuma hatasi: {e}")
                    continue

        logger.info(f"Toplam {len(self.kirisler)} kiris yuklendi")

    def _parse_dxf_duvarlar(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den duvar verilerini parse et - Akilli Yukseklik ve Kalinlik Hesabi"""
        duvar_sayaci = 1

        for katman_adi in katman_listesi:
            # LWPOLYLINE entity'lerini al
            for entity in msp.query(f'LWPOLYLINE[layer=="{katman_adi}"]'):
                try:
                    # Kapali olmayan veya bozuk cizgileri atla
                    if entity.closed is False and len(entity) < 3:
                        continue

                    with entity.points("xy") as pts:
                        noktalar = list(pts)

                    if len(noktalar) < 3:
                        continue

                    # Birim donusumu uygula
                    if birim == "m":
                        noktalar = [(p[0] * 100, p[1] * 100) for p in noktalar]
                    elif birim == "mm":
                        noktalar = [(p[0] / 10, p[1] / 10) for p in noktalar]

                    # Bounding box hesapla
                    xs = [p[0] for p in noktalar]
                    ys = [p[1] for p in noktalar]
                    x1, y1 = min(xs), min(ys)
                    x2, y2 = max(xs), max(ys)

                    # Geometri olustur
                    if SHAPELY_AVAILABLE:
                        geo = ShapelyPolygon(noktalar)
                        if not geo.is_valid:
                            geo = geo.buffer(0)  # Fix invalid geometry
                    else:
                        geo = Polygon(noktalar)

                    # HESAP_SINIRI filtresi
                    if not self._is_inside_boundary(geo, hesap_kutusu):
                        continue

                    # 1. YUKSEKLIK BULMA (Layer isminden: M_DUVAR_H270)
                    h = self._extract_duvar_yukseklik(katman_adi)

                    # 2. KALINLIK BULMA (Matematiksel: Alan / Uzunluk)
                    if SHAPELY_AVAILABLE:
                        alan = geo.area
                        cevre = geo.length
                    else:
                        alan = geo.area
                        cevre = sum(
                            ((noktalar[i][0] - noktalar[(i+1) % len(noktalar)][0]) ** 2 +
                             (noktalar[i][1] - noktalar[(i+1) % len(noktalar)][1]) ** 2) ** 0.5
                            for i in range(len(noktalar))
                        )

                    # Kalinlik = Alan / (Cevre / 2)  (Cevre/2 = uzunluk)
                    uzunluk = cevre / 2
                    kalinlik = round(alan / uzunluk) if uzunluk > 0 else 20

                    # Mantikli aralik kontrolu (5-50 cm)
                    if kalinlik < 5:
                        kalinlik = 10
                    elif kalinlik > 50:
                        kalinlik = 30

                    duvar = {
                        "id": f"D{duvar_sayaci}",
                        "layer": katman_adi,
                        "kalinlik": f"{kalinlik} cm",
                        "kalinlik_cm": kalinlik,
                        "h": h,  # Duvar yuksekligi (layer'dan)
                        "geo": geo,
                        "coords": f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})"
                    }
                    self.duvarlar.append(duvar)

                    row = self.duvar_table.rowCount()
                    self.duvar_table.insertRow(row)
                    self.duvar_table.setItem(row, 0, QTableWidgetItem(duvar["id"]))
                    self.duvar_table.setItem(row, 1, QTableWidgetItem(f"{kalinlik} cm (H:{h})"))
                    self.duvar_table.setItem(row, 2, QTableWidgetItem(duvar["coords"]))

                    duvar_sayaci += 1
                except Exception as e:
                    logger.warning(f"Duvar entity okuma hatasi: {e}")
                    continue

            # LINE entity'lerini de kontrol et (fallback)
            for entity in msp.query(f'LINE[layer=="{katman_adi}"]'):
                try:
                    start = entity.dxf.start
                    end = entity.dxf.end

                    x1, y1 = start.x, start.y
                    x2, y2 = end.x, end.y

                    # Birim donusumu
                    if birim == "m":
                        x1, y1, x2, y2 = x1 * 100, y1 * 100, x2 * 100, y2 * 100
                    elif birim == "mm":
                        x1, y1, x2, y2 = x1 / 10, y1 / 10, x2 / 10, y2 / 10

                    # Yukseklik layer'dan
                    h = self._extract_duvar_yukseklik(katman_adi)

                    # Kalinlik layer'dan (LINE icin geometri yok)
                    kalinlik = self._extract_duvar_kalinlik(katman_adi)

                    # Duvar kalinligi kadar buffer ekle
                    buffer = kalinlik / 2
                    geo = Polygon([
                        (x1, y1 - buffer), (x2, y1 - buffer),
                        (x2, y2 + buffer), (x1, y2 + buffer)
                    ])

                    duvar = {
                        "id": f"D{duvar_sayaci}",
                        "layer": katman_adi,
                        "kalinlik": f"{kalinlik} cm",
                        "kalinlik_cm": kalinlik,
                        "h": h,
                        "geo": geo,
                        "coords": f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})"
                    }
                    self.duvarlar.append(duvar)

                    row = self.duvar_table.rowCount()
                    self.duvar_table.insertRow(row)
                    self.duvar_table.setItem(row, 0, QTableWidgetItem(duvar["id"]))
                    self.duvar_table.setItem(row, 1, QTableWidgetItem(f"{kalinlik} cm (H:{h})"))
                    self.duvar_table.setItem(row, 2, QTableWidgetItem(duvar["coords"]))

                    duvar_sayaci += 1
                except Exception as e:
                    logger.warning(f"Duvar LINE entity okuma hatasi: {e}")
                    continue

        logger.info(f"Toplam {len(self.duvarlar)} duvar yuklendi")

    def _parse_dxf_kolonlar(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den kolon verilerini parse et"""
        kolon_sayaci = 1

        for katman_adi in katman_listesi:
            # LWPOLYLINE entity'lerini al (kapalı poligonlar)
            for entity in msp.query(f'LWPOLYLINE[layer=="{katman_adi}"]'):
                try:
                    with entity.points("xy") as pts:
                        noktalar = list(pts)

                    if len(noktalar) < 3:
                        continue

                    # Birim donusumu
                    if birim == "m":
                        noktalar = [(p[0] * 100, p[1] * 100) for p in noktalar]
                    elif birim == "mm":
                        noktalar = [(p[0] / 10, p[1] / 10) for p in noktalar]

                    # HESAP_SINIRI kontrolu
                    if hesap_kutusu:
                        merkez_x = sum(p[0] for p in noktalar) / len(noktalar)
                        merkez_y = sum(p[1] for p in noktalar) / len(noktalar)
                        if not (hesap_kutusu[0] <= merkez_x <= hesap_kutusu[2] and
                                hesap_kutusu[1] <= merkez_y <= hesap_kutusu[3]):
                            continue

                    # Geometri olustur
                    if SHAPELY_AVAILABLE:
                        geo = ShapelyPolygon(noktalar)
                    else:
                        geo = Polygon(noktalar)

                    # Kolon boyutlarini hesapla
                    xs = [p[0] for p in noktalar]
                    ys = [p[1] for p in noktalar]
                    genislik = max(xs) - min(xs)
                    derinlik = max(ys) - min(ys)

                    kolon = {
                        "id": f"C{kolon_sayaci:03d}",
                        "layer": katman_adi,
                        "geo": geo,
                        "genislik": genislik,
                        "derinlik": derinlik,
                        "coords": f"({min(xs):.0f},{min(ys):.0f})-({max(xs):.0f},{max(ys):.0f})"
                    }
                    self.kolonlar.append(kolon)
                    kolon_sayaci += 1
                except Exception as e:
                    logger.warning(f"Kolon LWPOLYLINE okuma hatasi: {e}")
                    continue

            # CIRCLE entity'lerini al (dairesel kolonlar)
            for entity in msp.query(f'CIRCLE[layer=="{katman_adi}"]'):
                try:
                    center = entity.dxf.center
                    radius = entity.dxf.radius

                    # Birim donusumu
                    if birim == "m":
                        cx, cy, r = center.x * 100, center.y * 100, radius * 100
                    elif birim == "mm":
                        cx, cy, r = center.x / 10, center.y / 10, radius / 10
                    else:
                        cx, cy, r = center.x, center.y, radius

                    # HESAP_SINIRI kontrolu
                    if hesap_kutusu:
                        if not (hesap_kutusu[0] <= cx <= hesap_kutusu[2] and
                                hesap_kutusu[1] <= cy <= hesap_kutusu[3]):
                            continue

                    # Dairesel kolon icin yaklasik poligon olustur (32 nokta)
                    import math
                    noktalar = [(cx + r * math.cos(2 * math.pi * i / 32),
                                 cy + r * math.sin(2 * math.pi * i / 32)) for i in range(32)]

                    if SHAPELY_AVAILABLE:
                        geo = ShapelyPolygon(noktalar)
                    else:
                        geo = Polygon(noktalar)

                    kolon = {
                        "id": f"C{kolon_sayaci:03d}",
                        "layer": katman_adi,
                        "geo": geo,
                        "genislik": r * 2,
                        "derinlik": r * 2,
                        "dairesel": True,
                        "yaricap": r,
                        "coords": f"Daire R:{r:.0f} @({cx:.0f},{cy:.0f})"
                    }
                    self.kolonlar.append(kolon)
                    kolon_sayaci += 1
                except Exception as e:
                    logger.warning(f"Kolon CIRCLE okuma hatasi: {e}")
                    continue

        logger.info(f"Toplam {len(self.kolonlar)} kolon yuklendi")

    def _parse_dxf_minhalar(self, msp, doc, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den minha (kapi/pencere) verilerini parse et - LWPOLYLINE ve INSERT (blok) destegi"""
        minha_sayaci = 1

        for katman_adi in katman_listesi:
            # Minha yuksekligini katman adindan cikar (varsayilan 210cm)
            h = self._extract_minha_height(katman_adi)

            # A) LWPOLYLINE entity'lerini al (elle cizilmis minhalar)
            for entity in msp.query(f'LWPOLYLINE[layer=="{katman_adi}"]'):
                try:
                    with entity.points("xy") as pts:
                        noktalar = list(pts)

                    if len(noktalar) < 3:
                        continue

                    # Bounding box hesapla
                    xs = [p[0] for p in noktalar]
                    ys = [p[1] for p in noktalar]
                    x1, y1 = min(xs), min(ys)
                    x2, y2 = max(xs), max(ys)

                    # Birim donusumu
                    if birim == "m":
                        x1, y1, x2, y2 = x1 * 100, y1 * 100, x2 * 100, y2 * 100
                    elif birim == "mm":
                        x1, y1, x2, y2 = x1 / 10, y1 / 10, x2 / 10, y2 / 10

                    # Geometri olustur
                    if SHAPELY_AVAILABLE:
                        geo = ShapelyPolygon([(p[0], p[1]) for p in noktalar])
                        if birim == "m":
                            geo = ShapelyPolygon([(p[0]*100, p[1]*100) for p in noktalar])
                        elif birim == "mm":
                            geo = ShapelyPolygon([(p[0]/10, p[1]/10) for p in noktalar])
                    else:
                        geo = Polygon([
                            (x1, y1), (x2, y1), (x2, y2), (x1, y2)
                        ])

                    # HESAP_SINIRI filtresi
                    if not self._is_inside_boundary(geo, hesap_kutusu):
                        continue

                    # Genislik hesapla (geometriden)
                    genislik = max(x2 - x1, y2 - y1)

                    minha = {
                        "id": f"M{minha_sayaci}",
                        "layer": katman_adi,
                        "h": h,
                        "genislik": genislik,
                        "geo": geo,
                        "tip": "Cizim",
                        "coords": f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})"
                    }
                    self.minhalar.append(minha)
                    minha_sayaci += 1

                except Exception as e:
                    logger.warning(f"Minha LWPOLYLINE okuma hatasi: {e}")
                    continue

            # B) INSERT (blok) entity'lerini al
            for entity in msp.query(f'INSERT[layer=="{katman_adi}"]'):
                try:
                    # Blogun bounding box'ini hesapla
                    try:
                        import ezdxf.bbox
                        bbox = ezdxf.bbox.extents([entity])
                        if not bbox.has_data:
                            continue
                        min_x, min_y, _ = bbox.extmin
                        max_x, max_y, _ = bbox.extmax
                    except:
                        # Alternatif yontem - insert noktasindan tahmini boyut
                        insert_point = entity.dxf.insert
                        min_x = insert_point.x - 50  # Tahmini genislik
                        max_x = insert_point.x + 50
                        min_y = insert_point.y - 50
                        max_y = insert_point.y + 50

                    # Birim donusumu
                    if birim == "m":
                        min_x, min_y = min_x * 100, min_y * 100
                        max_x, max_y = max_x * 100, max_y * 100
                    elif birim == "mm":
                        min_x, min_y = min_x / 10, min_y / 10
                        max_x, max_y = max_x / 10, max_y / 10

                    # Geometri olustur
                    if SHAPELY_AVAILABLE:
                        geo = shapely_box(min_x, min_y, max_x, max_y)
                    else:
                        geo = Polygon([
                            (min_x, min_y), (max_x, min_y),
                            (max_x, max_y), (min_x, max_y)
                        ])

                    # HESAP_SINIRI filtresi
                    if not self._is_inside_boundary(geo, hesap_kutusu):
                        continue

                    # Genislik hesapla
                    genislik = max(max_x - min_x, max_y - min_y)

                    minha = {
                        "id": f"M{minha_sayaci}",
                        "layer": katman_adi,
                        "h": h,
                        "genislik": genislik,
                        "geo": geo,
                        "tip": "Blok",
                        "coords": f"({min_x:.0f},{min_y:.0f})-({max_x:.0f},{max_y:.0f})"
                    }
                    self.minhalar.append(minha)
                    minha_sayaci += 1

                except Exception as e:
                    logger.warning(f"Minha INSERT okuma hatasi: {e}")
                    continue

        logger.info(f"Toplam {len(self.minhalar)} minha yuklendi")

    def _parse_dxf_oda_isimleri(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den oda isimlerini (TEXT/MTEXT) oku - Secilen katmanlardan"""

        if not katman_listesi:
            logger.info("Oda ismi katmani secilmedi")
            return

        # Hem TEXT hem MTEXT objelerini tara
        for entity in msp.query('TEXT MTEXT'):
            try:
                layer = entity.dxf.layer

                # Katman kontrolu - secilen katmanlardan biri mi?
                if layer not in katman_listesi:
                    continue

                # Icerik alma: TEXT ve MTEXT farki
                if entity.dxftype() == 'TEXT':
                    yazi_icerigi = entity.dxf.text
                else:  # MTEXT
                    yazi_icerigi = entity.text

                # MTEXT formatlarini temizle
                if yazi_icerigi:
                    import re
                    yazi_icerigi = re.sub(r'\\[A-Za-z][^;]*;', '', yazi_icerigi)
                    yazi_icerigi = re.sub(r'[{}\\]', '', yazi_icerigi)
                    yazi_icerigi = yazi_icerigi.strip()

                # Koordinatlari al
                x = entity.dxf.insert.x
                y = entity.dxf.insert.y

                # Birim donusumu
                if birim == "m":
                    x, y = x * 100, y * 100
                elif birim == "mm":
                    x, y = x / 10, y / 10

                # HESAP_SINIRI kontrolu
                if hesap_kutusu:
                    bounds = hesap_kutusu.bounds
                    min_x, min_y, max_x, max_y = bounds
                    if not (min_x <= x <= max_x and min_y <= y <= max_y):
                        continue  # Kutunun disindaysa atla

                # Bos degilse listeye ekle
                if yazi_icerigi and yazi_icerigi.strip():
                    self.oda_isimleri.append({
                        "text": yazi_icerigi.strip(),
                        "x": x,
                        "y": y,
                        "layer": layer
                    })

            except Exception as e:
                logger.warning(f"Oda ismi okuma hatasi: {e}")
                continue

        logger.info(f"Toplam {len(self.oda_isimleri)} oda ismi yuklendi")

    def _parse_dxf_kat_isimleri(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den kat isimlerini (TEXT/MTEXT) oku - Secilen katmanlardan"""

        if not katman_listesi:
            logger.info("Kat ismi katmani secilmedi")
            return

        # Hem TEXT hem MTEXT objelerini tara
        for entity in msp.query('TEXT MTEXT'):
            try:
                layer = entity.dxf.layer

                # Katman kontrolu - secilen katmanlardan biri mi?
                if layer not in katman_listesi:
                    continue

                # Icerik alma: TEXT ve MTEXT farki
                if entity.dxftype() == 'TEXT':
                    yazi_icerigi = entity.dxf.text
                else:  # MTEXT
                    yazi_icerigi = entity.text

                # MTEXT formatlarini temizle
                if yazi_icerigi:
                    import re
                    yazi_icerigi = re.sub(r'\\[A-Za-z][^;]*;', '', yazi_icerigi)
                    yazi_icerigi = re.sub(r'[{}\\]', '', yazi_icerigi)
                    yazi_icerigi = yazi_icerigi.strip()

                # Koordinatlari al
                x = entity.dxf.insert.x
                y = entity.dxf.insert.y

                # Birim donusumu
                if birim == "m":
                    x, y = x * 100, y * 100
                elif birim == "mm":
                    x, y = x / 10, y / 10

                # HESAP_SINIRI kontrolu
                if hesap_kutusu:
                    bounds = hesap_kutusu.bounds
                    min_x, min_y, max_x, max_y = bounds
                    if not (min_x <= x <= max_x and min_y <= y <= max_y):
                        continue  # Kutunun disindaysa atla

                # Bos degilse listeye ekle
                if yazi_icerigi and yazi_icerigi.strip():
                    self.kat_isimleri.append({
                        "text": yazi_icerigi.strip(),
                        "x": x,
                        "y": y,
                        "layer": layer
                    })

            except Exception as e:
                logger.warning(f"Kat ismi okuma hatasi: {e}")
                continue

        logger.info(f"Toplam {len(self.kat_isimleri)} kat ismi yuklendi")

    def _parse_dxf_m2_yazilari(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den m2 degerlerini (TEXT/MTEXT) oku - Sap metraji icin"""

        if not katman_listesi:
            logger.info("M2 katmani secilmedi")
            return

        # Hem TEXT hem MTEXT objelerini tara
        for entity in msp.query('TEXT MTEXT'):
            try:
                layer = entity.dxf.layer

                # Katman kontrolu - secilen katmanlardan biri mi?
                if layer not in katman_listesi:
                    continue

                # Icerik alma: TEXT ve MTEXT farki
                if entity.dxftype() == 'TEXT':
                    yazi_icerigi = entity.dxf.text
                else:  # MTEXT
                    yazi_icerigi = entity.text

                # MTEXT formatlarini temizle
                if yazi_icerigi:
                    yazi_icerigi = re.sub(r'\\[A-Za-z][^;]*;', '', yazi_icerigi)
                    yazi_icerigi = re.sub(r'[{}\\]', '', yazi_icerigi)
                    yazi_icerigi = yazi_icerigi.strip()

                # Sayiyi cikar (Ornek: "24.5 m2" -> 24.5)
                deger = self._sayi_cikar(yazi_icerigi)

                if deger <= 0:
                    continue  # 0 veya negatif degerleri atla

                # Koordinatlari al
                x = entity.dxf.insert.x
                y = entity.dxf.insert.y

                # Birim donusumu
                if birim == "m":
                    x, y = x * 100, y * 100
                elif birim == "mm":
                    x, y = x / 10, y / 10

                # HESAP_SINIRI kontrolu
                if hesap_kutusu:
                    bounds = hesap_kutusu.bounds
                    min_x, min_y, max_x, max_y = bounds
                    if not (min_x <= x <= max_x and min_y <= y <= max_y):
                        continue  # Kutunun disindaysa atla

                self.m2_yazilari.append({
                    "raw_text": yazi_icerigi,
                    "deger": deger,
                    "x": x,
                    "y": y,
                    "layer": layer
                })

            except Exception as e:
                logger.warning(f"M2 yazisi okuma hatasi: {e}")
                continue

        logger.info(f"Toplam {len(self.m2_yazilari)} m2 yazisi yuklendi")

    def _sayi_cikar(self, text: str) -> float:
        """Yazidan sayiyi cikar (Ornek: '24.5 m2' -> 24.5)"""
        try:
            # Icindeki sayilari bul
            bulunan = re.findall(r"[-+]?\d*[.,]\d+|\d+", text)
            if bulunan:
                # Virgulu noktaya cevir
                sayi_str = bulunan[0].replace(',', '.')
                return float(sayi_str)
            return 0.0
        except:
            return 0.0

    def _mesafe_hesapla(self, p1: tuple, p2: tuple) -> float:
        """Iki nokta arasi mesafe (Oklid)"""
        import math
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def _eslesitir_m2_oda(self):
        """M2 degerlerini en yakin oda isimleriyle esle (En Yakin Komsu)"""
        self.sap_eslestirme.clear()

        for m2 in self.m2_yazilari:
            en_yakin_isim = "TANIMSIZ"
            en_kisa_mesafe = float('inf')

            # Bu m2 yazisina en yakin oda ismini bul
            for oda in self.oda_isimleri:
                dist = self._mesafe_hesapla((m2['x'], m2['y']), (oda['x'], oda['y']))
                if dist < en_kisa_mesafe:
                    en_kisa_mesafe = dist
                    en_yakin_isim = oda['text']

            self.sap_eslestirme.append({
                "mahal_adi": en_yakin_isim,
                "okunan_yazi": m2['raw_text'],
                "deger": m2['deger'],
                "mesafe": en_kisa_mesafe,
                "x": m2['x'],
                "y": m2['y']
            })

        logger.info(f"Toplam {len(self.sap_eslestirme)} m2-oda eslestirmesi yapildi")

    def _hesapla_imalat_listesi(self):
        """Sap eslestirmesine göre imalat listesi ve malzeme ihtiyaçları olustur"""
        self.imalat_listesi.clear()
        self.malzeme_ihtiyaclari.clear()

        kat_h = self.kat_yuksekligi_spin.value()  # cm
        tezgah_arasi_h = 60  # cm (sabit)
        tezgah_uzunluk = 350  # cm (tahmini)

        def ekle_imalat(mahal, grup, imalat, miktar, birim):
            """Imalat ekle ve sarfiyat hesapla"""
            self.imalat_listesi.append({
                "Mahal": mahal, "Grup": grup, "İmalat": imalat,
                "Miktar": round(miktar, 2), "Birim": birim
            })

            # Sarfiyat hesabi (SARFIYATLAR veritabanindan)
            if imalat in SARFIYATLAR:
                veri = SARFIYATLAR[imalat]  # [oran, paket_kg, paket_tur, tur]
                tuketim = miktar * veri[0]  # Toplam Kg/Lt/m2
                paket_sayisi = tuketim / veri[1]

                if imalat not in self.malzeme_ihtiyaclari:
                    self.malzeme_ihtiyaclari[imalat] = {
                        "Toplam Tüketim": 0,
                        "Paket Sayısı": 0,
                        "Paket Tipi": veri[2],
                        "Malzeme Türü": veri[3]
                    }
                self.malzeme_ihtiyaclari[imalat]["Toplam Tüketim"] += tuketim
                self.malzeme_ihtiyaclari[imalat]["Paket Sayısı"] += paket_sayisi

        for sap in self.sap_eslestirme:
            mahal = sap["mahal_adi"]
            zemin_alan = sap["deger"]  # m2
            recete = recete_getir(mahal)

            # Net çevre tahmini (kare oda varsayimi: cevre = 4 * sqrt(alan))
            tahmini_cevre_m = 4 * math.sqrt(zemin_alan)
            duvar_alan = tahmini_cevre_m * (kat_h / 100)  # m2

            # A) ZEMİN İMALATLARI
            for kalem in recete["ZEMIN"]:
                ekle_imalat(mahal, "ZEMİN", kalem, zemin_alan, "m2")

            # B) TAVAN İMALATLARI
            for kalem in recete["TAVAN"]:
                ekle_imalat(mahal, "TAVAN", kalem, zemin_alan, "m2")

            # C) DUVAR İMALATLARI
            for kalem in recete["DUVAR"]:
                ekle_imalat(mahal, "DUVAR", kalem, duvar_alan, "m2")

            # D) SÜPÜRGELİK
            if recete["SUPURGELIK"]:
                ekle_imalat(mahal, "SÜPÜRGELİK", recete["SUPURGELIK"], tahmini_cevre_m, "mtul")

            # E) EKSTRALAR (Tezgah Arası vb.)
            for ekstra in recete["EKSTRA"]:
                miktar = 0
                birim = "m2"
                if ekstra == "Tezgah Arası Seramik":
                    miktar = (tezgah_uzunluk / 100) * (tezgah_arasi_h / 100)
                elif ekstra == "Fayans Yapıştırıcı":
                    miktar = (tezgah_uzunluk / 100) * (tezgah_arasi_h / 100)
                ekle_imalat(mahal, "EKSTRA", ekstra, miktar, birim)

            # F) TEFRİŞ SAYIMI (Bu odadaki tefrisler)
            for tefris in self.tefrisler:
                if self._nokta_odada_mi(tefris["x"], tefris["y"], sap):
                    self.imalat_listesi.append({
                        "Mahal": mahal, "Grup": "TEFRİŞAT", "İmalat": tefris["tur"],
                        "Miktar": 1, "Birim": "Adet"
                    })

        logger.info(f"Toplam {len(self.imalat_listesi)} imalat kalemi, {len(self.malzeme_ihtiyaclari)} malzeme türü")

    def _nokta_odada_mi(self, x: float, y: float, sap: Dict) -> bool:
        """Bir noktanin odaya yakin olup olmadigini kontrol et"""
        # Basit mesafe kontrolu (m2 noktasina yakinlik)
        mesafe = math.sqrt((x - sap["x"])**2 + (y - sap["y"])**2)
        return mesafe < 500  # 5 metre yaricap

    def _parse_dxf_tefrisler(self, msp, birim: str = "cm", hesap_kutusu=None):
        """DXF'den tefris bloklarini oku"""
        self.tefrisler.clear()

        birim_carpani = {"cm": 1, "m": 100, "mm": 0.1}.get(birim, 1)

        try:
            for entity in msp.query('INSERT'):
                try:
                    blok_adi = entity.dxf.name.upper()
                    insert = entity.dxf.insert
                    x = insert.x * birim_carpani
                    y = insert.y * birim_carpani

                    # HESAP_SINIRI kontrolu
                    if hesap_kutusu:
                        if not (hesap_kutusu[0] <= x <= hesap_kutusu[2] and
                                hesap_kutusu[1] <= y <= hesap_kutusu[3]):
                            continue

                    # Tefris sözlüğünde ara
                    for anahtar, tur in TEFRIS_SOZLUGU.items():
                        if anahtar in blok_adi:
                            self.tefrisler.append({
                                "tur": tur,
                                "blok": blok_adi,
                                "x": x,
                                "y": y
                            })
                            break
                except:
                    continue

            logger.info(f"Toplam {len(self.tefrisler)} tefris bloğu bulundu")
        except Exception as e:
            logger.error(f"Tefris okuma hatasi: {e}")

    def _extract_minha_height(self, katman_adi: str) -> int:
        """Katman adindan minha yuksekligini cikar"""
        # Pattern: M_MINHA_H210, PENCERE_H120, KAPI_H210 vs.
        patterns = [
            r'H(\d+)',      # H210, H120
            r'_(\d+)$',     # _210, _120
            r'(\d+)CM',     # 210CM
        ]

        katman_upper = katman_adi.upper()
        for pattern in patterns:
            match = re.search(pattern, katman_upper)
            if match:
                h = int(match.group(1))
                # Mantikli aralik kontrolu (50-300cm)
                if 50 <= h <= 300:
                    return h

        # Varsayilan minha yuksekligi (kapi icin 210cm)
        return 210

    def _extract_kiris_height(self, katman_adi: str) -> int:
        """Katman adindan kiris yuksekligini cikar"""
        # Pattern: S_KIRIS_H60, KIRIS_50, beam_h40 vs.
        patterns = [
            r'H(\d+)',      # H60, H50
            r'_(\d+)$',     # _60, _50
            r'(\d+)CM',     # 60CM
            r'(\d+)$',      # sadece rakam
        ]

        katman_upper = katman_adi.upper()
        for pattern in patterns:
            match = re.search(pattern, katman_upper)
            if match:
                h = int(match.group(1))
                # Mantikli aralik kontrolu (20-120cm)
                if 20 <= h <= 120:
                    return h

        # Varsayilan kiris yuksekligi
        return 60

    def _extract_duvar_kalinlik(self, katman_adi: str) -> int:
        """Katman adindan duvar kalinligini cikar"""
        # Pattern: M_DUVAR_TUGLA_20, DUVAR_15, wall_10 vs.
        patterns = [
            r'_(\d+)$',     # _20, _15
            r'_(\d+)_',     # _20_
            r'(\d+)CM',     # 20CM
            r'T(\d+)',      # T20 (tuğla 20)
        ]

        katman_upper = katman_adi.upper()
        for pattern in patterns:
            match = re.search(pattern, katman_upper)
            if match:
                k = int(match.group(1))
                # Mantikli aralik kontrolu (5-50cm)
                if 5 <= k <= 50:
                    return k

        # Varsayilan duvar kalinligi
        return 20

    def _extract_duvar_yukseklik(self, katman_adi: str) -> int:
        """Katman adindan duvar yuksekligini cikar (M_DUVAR_H270 gibi)"""
        # Pattern: M_DUVAR_H270, DUVAR_H300, wall_h250 vs.
        patterns = [
            r'_H(\d+)',     # _H270, _H300
            r'H(\d+)',      # H270
            r'_(\d{3})$',   # _270 (3 haneli, sonda)
            r'_(\d{3})_',   # _270_ (3 haneli, ortada)
        ]

        katman_upper = katman_adi.upper()
        for pattern in patterns:
            match = re.search(pattern, katman_upper)
            if match:
                h = int(match.group(1))
                # Mantikli aralik kontrolu (100-500cm)
                if 100 <= h <= 500:
                    return h

        # Varsayilan duvar yuksekligi (kat yuksekligi varsayilir)
        return 300

    def _hesapla_duvar_malzeme_siparis(self) -> List[Dict]:
        """
        Duvar sonuçlarından kalınlık bazında malzeme sipariş listesi oluştur.

        Seçilen duvar cinsine (Tuğla/Bims/Ytong/Gazbeton) göre
        her kalınlık için adet hesabı yapar.

        Returns:
            List[Dict]: Kalınlık bazında sipariş listesi
        """
        if not self.sonuc_duvarlar:
            return []

        # Kalınlık bazında alan toplamları
        kalinlik_alanlari: Dict[int, float] = {}

        for duvar in self.sonuc_duvarlar:
            # Kalınlık bilgisini al (kalinlik_cm veya kalinlik olabilir)
            kalinlik_ham = duvar.get("kalinlik_cm", duvar.get("kalinlik", 20))  # Varsayılan 20 cm

            # Eğer kalinlik string ise sayıya çevir (örn: "20 cm" -> 20)
            if isinstance(kalinlik_ham, str):
                kalinlik_match = re.search(r'(\d+)', kalinlik_ham)
                if kalinlik_match:
                    kalinlik_ham = int(kalinlik_match.group(1))
                else:
                    kalinlik_ham = 20
            else:
                kalinlik_ham = int(kalinlik_ham)

            # STANDART KALINLIĞA YUVARLA (9->10, 18->20, 19->20, vb.)
            kalinlik = standart_kalinliga_yuvarla(kalinlik_ham)

            # Net alan (m²)
            alan = duvar.get("alan", 0)

            # Kalınlık grubuna ekle
            if kalinlik not in kalinlik_alanlari:
                kalinlik_alanlari[kalinlik] = 0.0
            kalinlik_alanlari[kalinlik] += alan

        # Sarfiyat veritabanından adet hesabı
        sarfiyat_tablosu = DUVAR_MALZEME_SARFIYAT.get(self.duvar_cinsi, {})

        siparis_listesi = []
        toplam_adet = 0

        # Kalınlıklara göre sırala (10, 15, 20)
        for kalinlik in sorted(kalinlik_alanlari.keys()):
            alan = kalinlik_alanlari[kalinlik]

            # Sarfiyat değerini al (zaten standart kalınlıkta)
            adet_m2 = sarfiyat_tablosu.get(kalinlik, 32)  # Varsayılan 32 (tuğla 20cm)

            # Adet hesabı (%5 fire dahil)
            fire_katsayisi = 1.05
            toplam_adet_kalinlik = math.ceil(alan * adet_m2 * fire_katsayisi)
            toplam_adet += toplam_adet_kalinlik

            siparis_listesi.append({
                "Malzeme Cinsi": self.duvar_cinsi,
                "Kalınlık (cm)": kalinlik,
                "Toplam Alan (m²)": round(alan, 2),
                "Sarfiyat (adet/m²)": adet_m2,
                "Fire Oranı": "%5",
                "Gereken Adet": toplam_adet_kalinlik,
                "Açıklama": f"{kalinlik}'lik {self.duvar_cinsi}"
            })

        # Toplam satırı ekle
        if siparis_listesi:
            toplam_alan = sum(item["Toplam Alan (m²)"] for item in siparis_listesi)
            siparis_listesi.append({
                "Malzeme Cinsi": "TOPLAM",
                "Kalınlık (cm)": "-",
                "Toplam Alan (m²)": round(toplam_alan, 2),
                "Sarfiyat (adet/m²)": "-",
                "Fire Oranı": "-",
                "Gereken Adet": toplam_adet,
                "Açıklama": f"Toplam {self.duvar_cinsi} ihtiyacı"
            })

        logger.info(f"Duvar malzeme siparisi hesaplandi: {self.duvar_cinsi}, {len(siparis_listesi)-1} kalinlik, toplam {toplam_adet} adet")

        return siparis_listesi

    def _export_to_excel(self):
        """Sonuclari Excel'e aktar"""
        if not self.sonuc_duvarlar and not self.sap_eslestirme:
            QMessageBox.warning(self, "Uyari", "Once hesaplama yapiniz veya m2 verisi yukleyiniz!")
            return

        if not PANDAS_AVAILABLE:
            QMessageBox.critical(
                self, "Hata",
                "pandas kutuphanesi yuklu degil!\n\npip install pandas openpyxl"
            )
            return

        # Dosya kaydetme dialogu
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Excel Dosyasi Kaydet",
            "metraj_analiz_sonuc.xlsx",
            "Excel Dosyalari (*.xlsx);;Tum Dosyalar (*)"
        )

        if not file_path:
            return

        try:
            # Excel'e kaydet (birden fazla sayfa)
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sayfa 1: Duvar Metraji (eger varsa)
                if self.sonuc_duvarlar:
                    data = []
                    for d in self.sonuc_duvarlar:
                        data.append({
                            "Poz No": d["id"],
                            "Layer": d.get("layer", ""),
                            "Durum": d["aciklama"],
                            "Kalinlik (cm)": d.get("kalinlik_cm", 20),
                            "Yukseklik (cm)": d["net_h"],
                            "Uzunluk (m)": round(d.get("uzunluk", 0), 2),
                            "Brut Alan (m2)": round(d.get("brut_alan", d["alan"]), 2),
                            "Minha Dusumu (m2)": round(d.get("minha_alani", 0), 2),
                            "Minha Detay": ", ".join(d.get("minha_detay", [])),
                            "NET ALAN (m2)": round(d["alan"], 2)
                        })
                    df = pd.DataFrame(data)
                    df.to_excel(writer, index=False, sheet_name="Duvar Metraji")

                # Sayfa 2: Sap Metraji (m2 eslestirmesi)
                if self.sap_eslestirme:
                    sap_data = []
                    for s in self.sap_eslestirme:
                        sap_data.append({
                            "Mahal Adi": s["mahal_adi"],
                            "Okunan Yazi": s["okunan_yazi"],
                            "Alan (m2)": round(s["deger"], 2),
                            "Koordinat X": round(s["x"], 2),
                            "Koordinat Y": round(s["y"], 2)
                        })
                    df_sap = pd.DataFrame(sap_data)
                    df_sap.to_excel(writer, index=False, sheet_name="Sap Metraji")

                    # Sap ozet satiri ekle
                    toplam_sap = sum(s["deger"] for s in self.sap_eslestirme)
                    ozet_df = pd.DataFrame([{
                        "Mahal Adi": "TOPLAM",
                        "Okunan Yazi": "",
                        "Alan (m2)": round(toplam_sap, 2),
                        "Koordinat X": "",
                        "Koordinat Y": ""
                    }])
                    ozet_df.to_excel(
                        writer, index=False, sheet_name="Sap Metraji",
                        startrow=len(sap_data) + 2, header=False
                    )

                # Sayfa 3: Detayli Imalat Listesi
                if self.imalat_listesi:
                    df_imalat = pd.DataFrame(self.imalat_listesi)
                    df_imalat.to_excel(writer, index=False, sheet_name="Detayli Imalat")

                    # Sayfa 4: Malzeme Ozeti (Pivot)
                    ozet = df_imalat.groupby(["Grup", "İmalat", "Birim"])["Miktar"].sum().reset_index()
                    ozet = ozet.sort_values(["Grup", "İmalat"])
                    ozet.to_excel(writer, index=False, sheet_name="Malzeme Ozeti")

                # Sayfa 5: NALBUR SİPARİŞ LİSTESİ (Paket/Torba hesabı)
                if self.malzeme_ihtiyaclari:
                    siparis_listesi = []
                    for malz, detay in self.malzeme_ihtiyaclari.items():
                        siparis_listesi.append({
                            "Malzeme Adı": malz,
                            "Toplam İhtiyaç": round(detay["Toplam Tüketim"], 2),
                            "Gereken Paket": math.ceil(detay["Paket Sayısı"]),
                            "Paket Tipi": detay["Paket Tipi"],
                            "Malzeme Türü": detay["Malzeme Türü"]
                        })
                    df_siparis = pd.DataFrame(siparis_listesi)
                    df_siparis = df_siparis.sort_values("Malzeme Türü")
                    df_siparis.to_excel(writer, index=False, sheet_name="NALBUR SIPARIS")

                # Sayfa 6: DUVAR MALZEMESİ SİPARİŞ (Kalınlık bazında adet hesabı)
                if self.sonuc_duvarlar:
                    duvar_siparis = self._hesapla_duvar_malzeme_siparis()
                    if duvar_siparis:
                        df_duvar_siparis = pd.DataFrame(duvar_siparis)
                        df_duvar_siparis.to_excel(writer, index=False, sheet_name="DUVAR MALZEME SIPARIS")

            # Ozet bilgiler
            mesaj_parcalari = [f"Sonuclar kaydedildi:\n{file_path}"]

            if self.sonuc_duvarlar:
                toplam_brut = sum(d.get("brut_alan", d["alan"]) for d in self.sonuc_duvarlar)
                toplam_minha = sum(d.get("minha_alani", 0) for d in self.sonuc_duvarlar)
                toplam_net = sum(d["alan"] for d in self.sonuc_duvarlar)
                kiris_alti_alan = sum(d["alan"] for d in self.sonuc_duvarlar if "Kiris" in d["aciklama"])
                doseme_alti_alan = sum(d["alan"] for d in self.sonuc_duvarlar if "Doseme" in d["aciklama"])

                mesaj_parcalari.append(
                    f"\nDUVAR METRAJI:\n"
                    f"Toplam: {len(self.sonuc_duvarlar)} duvar\n"
                    f"Brut Alan: {toplam_brut:.2f} m2\n"
                    f"Minha Dusumu: {toplam_minha:.2f} m2\n"
                    f"NET ALAN: {toplam_net:.2f} m2\n"
                    f"  - Kiris Alti: {kiris_alti_alan:.2f} m2\n"
                    f"  - Doseme Alti: {doseme_alti_alan:.2f} m2"
                )

            if self.sap_eslestirme:
                toplam_sap = sum(s["deger"] for s in self.sap_eslestirme)
                mesaj_parcalari.append(
                    f"\nSAP METRAJI:\n"
                    f"Toplam: {len(self.sap_eslestirme)} mahal\n"
                    f"Toplam Sap Alani: {toplam_sap:.2f} m2"
                )

            if self.imalat_listesi:
                mesaj_parcalari.append(
                    f"\nİMALAT LİSTESİ:\n"
                    f"Toplam: {len(self.imalat_listesi)} kalem"
                )

            if self.malzeme_ihtiyaclari:
                mesaj_parcalari.append(
                    f"\nNALBUR SİPARİŞ:\n"
                    f"Toplam: {len(self.malzeme_ihtiyaclari)} malzeme türü"
                )

            # Duvar malzeme siparişi özeti
            if self.sonuc_duvarlar:
                duvar_siparis = self._hesapla_duvar_malzeme_siparis()
                if duvar_siparis and len(duvar_siparis) > 1:
                    toplam_satir = duvar_siparis[-1]  # Son satır toplam
                    mesaj_parcalari.append(
                        f"\nDUVAR MALZEMESİ ({self.duvar_cinsi}):\n"
                        f"Kalınlık türü: {len(duvar_siparis)-1} adet\n"
                        f"Toplam: {toplam_satir.get('Gereken Adet', 0):,} adet"
                    )

            QMessageBox.information(self, "Basarili", "\n".join(mesaj_parcalari))

            logger.info(f"Excel dosyasi kaydedildi: {file_path}")

        except Exception as e:
            logger.error(f"Excel kaydetme hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{str(e)}")


class DXFKatmanSecimDialog(QDialog):
    """DXF katman secim dialog'u - Minha (kapi/pencere) ve Oda/Kat isimleri destegi"""

    def __init__(self, parent, katmanlar: List[str],
                 varsayilan_kiris: List[str], varsayilan_duvar: List[str],
                 varsayilan_minha: List[str] = None,
                 text_katmanlari: List[str] = None,
                 varsayilan_oda: List[str] = None,
                 varsayilan_kat: List[str] = None,
                 varsayilan_m2: List[str] = None):
        super().__init__(parent)
        self.setWindowTitle("DXF Katman Secimi - Proje Kimligi")
        self.setMinimumSize(1000, 850)

        self.katmanlar = katmanlar
        # varsayilan_kiris artik kullanilmiyor
        self.varsayilan_duvar = varsayilan_duvar
        self.varsayilan_minha = varsayilan_minha or []
        self.text_katmanlari = text_katmanlari or []
        self.varsayilan_oda = varsayilan_oda or []
        self.varsayilan_kat = varsayilan_kat or []
        self.varsayilan_m2 = varsayilan_m2 or []
        self.secilen_duvar_cinsi = "Tuğla"  # Varsayılan duvar cinsi

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Üst satır: Birim ve Duvar Cinsi seçimi
        ust_ayarlar_layout = QHBoxLayout()

        # Birim secimi
        birim_group = QGroupBox("Cizim Birimi")
        birim_layout = QHBoxLayout()
        self.birim_combo = QComboBox()
        self.birim_combo.addItems(["cm (Santimetre)", "m (Metre)", "mm (Milimetre)"])
        self.birim_combo.setCurrentIndex(0)  # cm varsayilan
        birim_layout.addWidget(QLabel("DXF dosyasinin birimi:"))
        birim_layout.addWidget(self.birim_combo)
        birim_layout.addStretch()
        birim_group.setLayout(birim_layout)
        ust_ayarlar_layout.addWidget(birim_group)

        # DUVAR CİNSİ SEÇİMİ (YENİ)
        duvar_cinsi_group = QGroupBox("🧱 Duvar Malzeme Cinsi")
        duvar_cinsi_group.setStyleSheet("QGroupBox { border: 2px solid #e74c3c; font-weight: bold; }")
        duvar_cinsi_layout = QVBoxLayout()

        duvar_cinsi_aciklama = QLabel("Nalbur siparisinde kullanilacak malzeme:")
        duvar_cinsi_aciklama.setStyleSheet("color: #e74c3c; font-size: 10pt;")
        duvar_cinsi_layout.addWidget(duvar_cinsi_aciklama)

        self.duvar_cinsi_combo = QComboBox()
        self.duvar_cinsi_combo.addItems(DUVAR_CINSLERI)
        self.duvar_cinsi_combo.setCurrentIndex(0)  # Tuğla varsayilan
        self.duvar_cinsi_combo.currentTextChanged.connect(self._duvar_cinsi_degisti)
        self.duvar_cinsi_combo.setStyleSheet("""
            QComboBox {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 2px solid #e74c3c;
                padding: 8px;
                font-size: 12pt;
                font-weight: bold;
            }
            QComboBox:hover {
                border-color: #c0392b;
            }
        """)
        duvar_cinsi_layout.addWidget(self.duvar_cinsi_combo)

        # Sarfiyat bilgisi etiketi (10, 15, 20 cm standart kalınlıklar)
        self.sarfiyat_bilgi_label = QLabel("10cm: 22, 15cm: 28, 20cm: 32 adet/m²")
        self.sarfiyat_bilgi_label.setStyleSheet("color: #95a5a6; font-size: 9pt;")
        duvar_cinsi_layout.addWidget(self.sarfiyat_bilgi_label)

        duvar_cinsi_group.setLayout(duvar_cinsi_layout)
        ust_ayarlar_layout.addWidget(duvar_cinsi_group)

        layout.addLayout(ust_ayarlar_layout)

        # Ana icerik - yatay bolunmus (ust satir: Duvar, Minha)
        content_layout1 = QHBoxLayout()

        # Duvar katmanlari
        duvar_group = QGroupBox(f"Duvar Katmanlari ({len(self.varsayilan_duvar)} tespit edildi)")
        duvar_layout = QVBoxLayout()
        self.duvar_list = QListWidget()
        self.duvar_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for katman in self.katmanlar:
            item = QListWidgetItem(katman)
            self.duvar_list.addItem(item)
            if katman in self.varsayilan_duvar:
                item.setSelected(True)
        duvar_layout.addWidget(self.duvar_list)
        duvar_group.setLayout(duvar_layout)
        content_layout1.addWidget(duvar_group)

        # Minha (Kapi/Pencere) katmanlari
        minha_group = QGroupBox(f"Minha Katmanlari ({len(self.varsayilan_minha)} tespit edildi)")
        minha_layout = QVBoxLayout()
        self.minha_list = QListWidget()
        self.minha_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for katman in self.katmanlar:
            item = QListWidgetItem(katman)
            self.minha_list.addItem(item)
            if katman in self.varsayilan_minha:
                item.setSelected(True)
        minha_layout.addWidget(self.minha_list)
        minha_group.setLayout(minha_layout)
        content_layout1.addWidget(minha_group)

        layout.addLayout(content_layout1)

        # Alt satir: Oda ve Kat isimleri (PROJE KIMLIGI)
        kimlik_label = QLabel("📋 PROJE KIMLIGI (Oda ve Kat Isimleri)")
        kimlik_label.setStyleSheet("font-weight: bold; font-size: 12pt; color: #f1c40f; padding: 5px;")
        layout.addWidget(kimlik_label)

        content_layout2 = QHBoxLayout()

        # Oda Ismi Katmanlari (TEXT/MTEXT)
        oda_group = QGroupBox(f"Oda Ismi Katmanlari ({len(self.varsayilan_oda)} tespit edildi)")
        oda_group.setStyleSheet("QGroupBox { border: 2px solid #f1c40f; }")
        oda_layout = QVBoxLayout()
        self.oda_list = QListWidget()
        self.oda_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for katman in self.text_katmanlari:
            item = QListWidgetItem(katman)
            self.oda_list.addItem(item)
            if katman in self.varsayilan_oda:
                item.setSelected(True)
        oda_layout.addWidget(self.oda_list)
        oda_group.setLayout(oda_layout)
        content_layout2.addWidget(oda_group)

        # Kat Ismi Katmanlari (TEXT/MTEXT)
        kat_group = QGroupBox(f"Kat Ismi Katmanlari ({len(self.varsayilan_kat)} tespit edildi)")
        kat_group.setStyleSheet("QGroupBox { border: 2px solid #00bfff; }")
        kat_layout = QVBoxLayout()
        self.kat_list = QListWidget()
        self.kat_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for katman in self.text_katmanlari:
            item = QListWidgetItem(katman)
            self.kat_list.addItem(item)
            if katman in self.varsayilan_kat:
                item.setSelected(True)
        kat_layout.addWidget(self.kat_list)
        kat_group.setLayout(kat_layout)
        content_layout2.addWidget(kat_group)

        # M2 Yazilari Katmanlari (TEXT/MTEXT) - SAP HESABI
        m2_group = QGroupBox(f"M2 Yazilari Katmanlari ({len(self.varsayilan_m2)} tespit edildi)")
        m2_group.setStyleSheet("QGroupBox { border: 2px solid #2ecc71; }")
        m2_layout = QVBoxLayout()
        self.m2_list = QListWidget()
        self.m2_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for katman in self.text_katmanlari:
            item = QListWidgetItem(katman)
            self.m2_list.addItem(item)
            if katman in self.varsayilan_m2:
                item.setSelected(True)
        m2_layout.addWidget(self.m2_list)
        m2_group.setLayout(m2_layout)
        content_layout2.addWidget(m2_group)

        layout.addLayout(content_layout2)

        # HESAP_SINIRI checkbox
        self.hesap_siniri_checkbox = QCheckBox("HESAP_SINIRI katmanini kullan (sadece cerceve icini tara)")
        self.hesap_siniri_checkbox.setChecked("HESAP_SINIRI" in self.katmanlar)
        self.hesap_siniri_checkbox.setEnabled("HESAP_SINIRI" in self.katmanlar)
        if "HESAP_SINIRI" not in self.katmanlar:
            self.hesap_siniri_checkbox.setToolTip("DXF dosyasinda HESAP_SINIRI katmani bulunamadi")
        layout.addWidget(self.hesap_siniri_checkbox)

        # Bilgi etiketi
        info_label = QLabel(
            "💡 Duvar: Duvar cizgileri | Minha: Kapi/Pencere acikliklari\n"
            "📋 Oda Ismi: Salon, Mutfak vs. (Sari) | Kat Ismi: Zemin Kat, 1. Kat vs. (Mavi - Buyuk)\n"
            "📐 M2 Yazilari: Alan metrekare degerleri (Yesil) - Sap hesabi icin kullanilir\n"
            "HESAP_SINIRI katmani varsa sadece cerceve icindeki nesneler taranir."
        )
        info_label.setStyleSheet("color: #888; padding: 10px;")
        layout.addWidget(info_label)

        # Butonlar
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_kiris(self) -> List[str]:
        """Secilen kiris katmanlarini dondur (devre disi)"""
        return []

    def get_selected_duvar(self) -> List[str]:
        """Secilen duvar katmanlarini dondur"""
        return [item.text() for item in self.duvar_list.selectedItems()]

    def get_selected_minha(self) -> List[str]:
        """Secilen minha (kapi/pencere) katmanlarini dondur"""
        return [item.text() for item in self.minha_list.selectedItems()]

    def get_selected_oda(self) -> List[str]:
        """Secilen oda ismi katmanlarini dondur"""
        return [item.text() for item in self.oda_list.selectedItems()]

    def get_selected_kat(self) -> List[str]:
        """Secilen kat ismi katmanlarini dondur"""
        return [item.text() for item in self.kat_list.selectedItems()]

    def get_selected_m2(self) -> List[str]:
        """Secilen m2 yazisi katmanlarini dondur"""
        return [item.text() for item in self.m2_list.selectedItems()]

    def get_cizim_birimi(self) -> str:
        """Secilen cizim birimini dondur"""
        birim_text = self.birim_combo.currentText()
        if "cm" in birim_text:
            return "cm"
        elif "mm" in birim_text:
            return "mm"
        else:
            return "m"

    def get_use_hesap_siniri(self) -> bool:
        """HESAP_SINIRI kullanilacak mi?"""
        return self.hesap_siniri_checkbox.isChecked()

    def get_duvar_cinsi(self) -> str:
        """Secilen duvar cinsini dondur"""
        return self.duvar_cinsi_combo.currentText()

    def _duvar_cinsi_degisti(self, yeni_cins: str):
        """Duvar cinsi degistiginde sarfiyat bilgisini guncelle"""
        self.secilen_duvar_cinsi = yeni_cins
        # Sarfiyat bilgisini güncelle (10, 15, 20 cm standart kalınlıklar)
        sarfiyat = DUVAR_MALZEME_SARFIYAT.get(yeni_cins, {})
        if sarfiyat:
            s10 = sarfiyat.get(10, 0)
            s15 = sarfiyat.get(15, 0)
            s20 = sarfiyat.get(20, 0)
            self.sarfiyat_bilgi_label.setText(f"10cm: {s10}, 15cm: {s15}, 20cm: {s20} adet/m²")
