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
    QTabWidget, QRadioButton, QButtonGroup, QScrollArea, QInputDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

import webbrowser
import tempfile

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# 3D Görselleştirme modülü
try:
    from app.ui.ince_isler_3d_widget import InceIsler3DPanel
    _3D_MODUL_OK = True
except ImportError:
    _3D_MODUL_OK = False
    InceIsler3DPanel = None


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
except Exception:
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
        10: 22,   # 10 cm tuğla: ~22 adet/m²
        15: 28,   # 15 cm tuğla: ~28 adet/m²
        20: 32,   # 20 cm tuğla: ~32 adet/m²
    },
    "Bims": {
        10: 12,   # 10 cm bims: ~12 adet/m²
        15: 13,   # 15 cm bims: ~13 adet/m²
        20: 13,   # 20 cm bims: ~13 adet/m²
    },
    "Ytong": {
        10: 6.25,  # 10 cm ytong: ~6.25 adet/m² (60x25 blok)
        15: 6.25,  # 15 cm ytong: ~6.25 adet/m²
        20: 6.25,  # 20 cm ytong: ~6.25 adet/m²
    },
    "Gazbeton": {
        10: 6.25,  # 10 cm gazbeton: ~6.25 adet/m² (60x25 blok)
        15: 6.25,  # 15 cm gazbeton: ~6.25 adet/m²
        20: 6.25,  # 20 cm gazbeton: ~6.25 adet/m²
    },
}

# Standart duvar kalınlıkları (yuvarlama için)
STANDART_DUVAR_KALINLIKLARI = [10, 15, 20]

# Duvar cinsi listesi (UI için)
DUVAR_CINSLERI = ["Tuğla", "Bims", "Ytong", "Gazbeton"]


# --- ANORMALLİK TESPİT ARALIКЛARI (Özellik 4) ---
# m² zemin alanı başına beklenen sarfiyat katsayıları (min, max)
# Değer bu aralığın dışındaysa uyarı verilir.
NORMAL_ARALIKLAR = {
    "Kaba Alçı": (8.0, 14.0), # kg / m² zemin
    "Saten Alçı": (0.25, 0.45), # kg / m²
    "Duvar Boyası": (0.20, 0.45), # lt / m²
    "Tavan Boyası": (0.18, 0.35), # lt / m²
    "Yer Fayansı + Derz": (1.00, 1.15), # m² / m² (fire dahil)
    "Duvar Fayansı + Derz": (1.00, 1.15), # m² / m²
    "Laminat Parke": (1.00, 1.15), # m² / m²
    "Şap Çimentosu": (12.0, 20.0), # kg / m²
    "Şap Kumu": (0.04, 0.08), # m³ / m²
    "Fayans Yapıştırıcı": (3.50, 6.00), # kg / m²
    "Derz Dolgu": (0.40, 0.70), # kg / m²
    "Sıva Çimentosu": (8.0, 14.0), # kg / m²
}


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
    "Kaba Alçı": [10.0, 35, "Torba (35kg)", "Toz"],

    # 2. KAT: Karışık (Kırma) Katmanı (Yarı Yarıya karışım)
    "Karışık İçin Sıva": [0.5, 35, "Torba (35kg)", "Toz"],
    "Karışık İçin Saten": [0.5, 30, "Torba (30kg)", "Toz"],

    # 3. KAT: Son Kat Saten (Macun)
    "Saten Alçı": [0.3, 30, "Torba (30kg)", "Toz"],

    # --- SIVA & ŞAP GRUBU (KUM VE ÇİMENTO AYRILDI) ---
    # Duvar Sıvası (Kara Sıva - Islak Hacimler)
    "Sıva Çimentosu": [10.0, 50, "Torba (Çimento)", "Kaba"],
    "Sıva Kumu": [0.025, 1, "m3 (Kepçe)", "Kaba"],

    # Zemin Şapı
    "Şap Çimentosu": [15.0, 50, "Torba (Çimento)", "Kaba"],
    "Şap Kumu": [0.06, 1, "m3 (Kepçe)", "Kaba"],

    # --- BOYA GRUBU ---
    "Duvar Boyası": [0.30, 15, "Kova (15L)", "Sıvı"],
    "Tavan Boyası": [0.25, 17.5, "Kova (17.5kg)", "Sıvı"],

    # --- SERAMİK & YAPIŞTIRICI ---
    "Yer Fayansı + Derz": [1.05, 1, "m2 (Fireli)", "Kaplama"],
    "Duvar Fayansı + Derz": [1.05, 1, "m2 (Fireli)", "Kaplama"],
    "Fayans Yapıştırıcı": [4.5, 25, "Torba (25kg)", "Toz"],
    "Derz Dolgu": [0.5, 20, "Torba (20kg)", "Toz"],
    "Tezgah Arası Seramik": [1.05, 1, "m2 (Fireli)", "Kaplama"],

    # --- PARKE GRUBU ---
    "Laminat Parke": [1.05, 1.8, "Paket (1.8m2)", "Kaplama"],
    "Parke Altı Şilte": [1.0, 10, "Top (10m2)", "Rulo"],

    # --- SÜPÜRGELİK ---
    "Seramik Süpürgelik": [1.05, 1, "mtul (Fireli)", "Kaplama"],
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


class SarfiyatAyarlariDialog(QDialog):
    """Sarfiyat ayarlarını düzenlemek için dialog"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sarfiyat Ayarları")
        self.setMinimumSize(700, 450)
        self.setStyleSheet(
        "QDialog { background: #252535; color: white; }"
        "QTableWidget { background: #1e1e2e; color: white; gridline-color: #444; }"
        "QHeaderView::section { background: #333345; color: white; font-weight: bold; padding: 4px; border: 1px solid #555; }"
        "QPushButton { background: #444; color: white; padding: 6px 14px; border: 1px solid #666; border-radius: 4px; }"
        "QPushButton:hover { background: #555; }"
        )
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        lbl = QLabel("Malzeme başına tüketim değerlerini düzenleyin:")
        lbl.setStyleSheet("color: #aaa; font-size: 9pt;")
        lay.addWidget(lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
        ["Malzeme", "Tük./m²", "Paket Mkt.", "Paket Tipi", "M.Türü"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        lay.addWidget(self.table)

        self._doldur()

        btn_bar = QHBoxLayout()
        btn_kaydet = QPushButton(" Kaydet")
        btn_kaydet.setStyleSheet(
        "QPushButton { background: #27ae60; color: white; font-weight: bold; padding: 6px 16px; border: 1px solid #2ecc71; border-radius: 4px; }"
        "QPushButton:hover { background: #2ecc71; }"
        )
        btn_kaydet.clicked.connect(self._kaydet)
        btn_bar.addWidget(btn_kaydet)

        btn_fabrika = QPushButton(" Fabrika Değerleri")
        btn_fabrika.clicked.connect(self._fabrika_degerlerine_don)
        btn_bar.addWidget(btn_fabrika)

        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self.reject)
        btn_bar.addWidget(btn_iptal)
        lay.addLayout(btn_bar)

    def _doldur(self):
        """Tabloyu parent'ın sarfiyatlar_ozel ile doldur"""
        sarfiyatlar = self.parent().sarfiyatlar_ozel if self.parent() and hasattr(self.parent(), 'sarfiyatlar_ozel') else SARFIYATLAR
        self.table.setRowCount(len(sarfiyatlar))
        for row, (ad, veri) in enumerate(sarfiyatlar.items()):
            ad_item = QTableWidgetItem(ad)
            ad_item.setFlags(ad_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, ad_item)
            for col, val in enumerate(veri[:4], start=1):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    def _kaydet(self):
        """Değerleri parent.sarfiyatlar_ozel'e kaydet"""
        parent = self.parent()
        if not parent:
            self.accept()
            return
        for row in range(self.table.rowCount()):
            ad = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
            try:
                tuk = float(self.table.item(row, 1).text())
                paket_mkt = float(self.table.item(row, 2).text())
                paket_tip = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
                m_turu = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
                if ad and ad in parent.sarfiyatlar_ozel:
                    parent.sarfiyatlar_ozel[ad] = [tuk, paket_mkt, paket_tip, m_turu]
            except (ValueError, AttributeError):
                pass
        QMessageBox.information(self, "Kaydedildi", "Sarfiyat değerleri güncellendi.")
        self.accept()

    def _fabrika_degerlerine_don(self):
        """Orijinal SARFIYATLAR değerlerine dön"""
        parent = self.parent()
        if parent and hasattr(parent, 'sarfiyatlar_ozel'):
            parent.sarfiyatlar_ozel = dict(SARFIYATLAR)
            self._doldur()
            QMessageBox.information(self, "Sıfırlandı", "Fabrika değerleri yüklendi.")


class MetrajAnalizWindow(QMainWindow):
    """Akilli Metraj Analizi Ana Penceresi"""

    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        # Veritabanı bağlantısı (AI öğrenme için)
        if db is not None:
            self.db = db
        elif parent is not None and hasattr(parent, 'db'):
            self.db = parent.db
        else:
            self.db = None
        self.setWindowTitle("Akıllı Metraj Analizi")
        self.setMinimumSize(700, 700)

        # Veri listeleri
        self.kirisler: List[Dict] = []
        self.duvarlar: List[Dict] = []
        self.kolonlar: List[Dict] = [] # Kolonlar
        self.minhalar: List[Dict] = [] # Kapi/Pencere acikliklari
        self.oda_isimleri: List[Dict] = [] # Oda isimleri (TEXT/MTEXT)
        self.kat_isimleri: List[Dict] = [] # Kat isimleri (TEXT/MTEXT)
        self.m2_yazilari: List[Dict] = [] # M2 degerleri (TEXT/MTEXT) - Sap hesabi icin
        self.sonuc_duvarlar: List[Dict] = []
        self.sap_eslestirme: List[Dict] = [] # Oda-M2 eslestirmesi
        self.imalat_listesi: List[Dict] = [] # Mahal bazli imalat listesi
        self.tefrisler: List[Dict] = [] # DXF bloklarindan okunan tefrisler
        self.malzeme_ihtiyaclari: Dict = {} # Toplam malzeme ve paket sayilari
        self.duvar_cinsi: str = "Tuğla" # Secilen duvar malzeme cinsi (nalbur siparisi icin)

        # AutoCAD canlı bağlantı
        self.acad_connector: Optional['AutoCADConnector'] = None
        self.acad_metraj_objeleri: List = [] # AutoCAD'den alınan metraj objeleri

        # 3D panel referansı (İnce İşler sekmesine eklenir)
        self._3d_panel: Optional['InceIsler3DPanel'] = None

        # Demir metraj kat verileri
        # Format: {"kat_adi": str, "demirler": List[DemirBilgisi], "rapor": Dict}
        self.demir_kat_verileri: List[Dict] = []
        self.aktif_kat_adi: str = "" # Şu an seçili kat

        # --- YENİ VERİ YAPILARI (6 Özellik için) ---
        # Özellik 1: Net / Brüt Alan Ayrımı
        self.alan_turu: str = "net" # "net" | "brut"

        # Özellik 2: Çoklu Kat / Çoklu DXF
        # Format: {"kat_adi": str, "imalat": List[Dict]} → AutoCAD COM tabanlı ölçüm
        self.mimari_katlar: List[Dict] = []

        # Özellik 4: Anormallik Uyarı Listesi
        self.uyari_listesi: List[str] = []

        # Kullanıcı özel sarfiyat kopyası (D geliştirmesi)
        self.sarfiyatlar_ozel: dict = dict(SARFIYATLAR)

        # LISP araçları son sonucu (None = henüz çalıştırılmadı)
        self._lisp_son_sonuc: Optional[Dict] = None

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
        left_panel.setMinimumWidth(520)

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

        main_layout.addWidget(left_panel, 1)

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

        # Özellik 1 — Alan Türü seçimi
        layout.addWidget(QLabel("Alan Türü:"), 2, 0)
        alan_turu_widget = QWidget()
        alan_turu_row = QHBoxLayout(alan_turu_widget)
        alan_turu_row.setContentsMargins(0, 0, 0, 0)
        self.rbtn_net = QRadioButton("Net Alan")
        self.rbtn_net.setChecked(True)
        self.rbtn_net.setToolTip("Yalnızca iç net kullanım alanı (duvar kalınlıkları çıkarılmış)")
        self.rbtn_brut = QRadioButton("Brüt Alan")
        self.rbtn_brut.setToolTip("Duvar kalınlıkları dahil toplam ölçülen alan")
        self._alan_btn_grp = QButtonGroup(self)
        self._alan_btn_grp.addButton(self.rbtn_net, 0)
        self._alan_btn_grp.addButton(self.rbtn_brut, 1)
        self.rbtn_net.toggled.connect(self._alan_turu_degistir)
        alan_turu_row.addWidget(self.rbtn_net)
        alan_turu_row.addWidget(self.rbtn_brut)
        alan_turu_row.addStretch()
        layout.addWidget(alan_turu_widget, 2, 1)

        # Alan katsayısı bilgi etiketi
        self._alan_bilgi_label = QLabel("ℹ Net Alan — %12 azaltma uygulanıyor (katsayı: 0.88)")
        self._alan_bilgi_label.setStyleSheet("color: #ffaa00; font-size: 10px; padding: 2px;")
        layout.addWidget(self._alan_bilgi_label, 3, 1)

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
        self.duvar_kalinlik_combo.setCurrentIndex(2) # 20 cm default
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
        acad_group = QGroupBox(" AutoCAD Canlı Bağlantı")
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
        self.btn_acad_baglan = QPushButton(" AutoCAD'e Bağlan")
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
        # SEKME 1: İNCE İŞLER METRAJI (İç Cephe + Dış Cephe)
        # ─────────────────────────────────────────────────────────────────
        ince_isler_tab = QWidget()
        _ince_outer_layout = QVBoxLayout(ince_isler_tab)
        _ince_outer_layout.setContentsMargins(0, 0, 0, 0)
        _ince_outer_layout.setSpacing(0)

        # QScrollArea: duvar_group ve menha_group her zaman erişilebilir olsun
        _ince_scroll = QScrollArea()
        _ince_scroll.setWidgetResizable(True)
        _ince_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _ince_scroll.setStyleSheet(
        "QScrollArea { border: none; background: transparent; }"
        "QScrollBar:vertical { background:#1a1a2e; width:8px; border-radius:4px; }"
        "QScrollBar::handle:vertical { background:#555; border-radius:4px; min-height:20px; }"
        )
        _ince_content = QWidget()
        ince_isler_layout = QVBoxLayout(_ince_content)
        ince_isler_layout.setContentsMargins(5, 5, 5, 5)
        ince_isler_layout.setSpacing(5)

        # Üst butonlar (Renk Geri Al + Katman Seçimi)
        ince_ust_layout = QHBoxLayout()

        self.btn_acad_sec = QPushButton(" Obje Seç")
        self.btn_acad_sec.clicked.connect(self._autocad_obje_sec)
        self.btn_acad_sec.setEnabled(False)
        self.btn_acad_sec.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2196F3, stop:1 #1976D2);
        color: white; font-weight: bold; padding: 6px; border: 2px solid #64B5F6;
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #42A5F5, stop:1 #2196F3); }
        QPushButton:disabled { background: #444; color: #666; }
        """)
        ince_ust_layout.addWidget(self.btn_acad_sec)

        self.btn_acad_renk_geri = QPushButton("↩ Renkleri Geri Al")
        self.btn_acad_renk_geri.clicked.connect(self._autocad_renkleri_geri_al)
        self.btn_acad_renk_geri.setEnabled(False)
        self.btn_acad_renk_geri.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #607D8B, stop:1 #455A64);
        color: white; font-weight: bold; padding: 6px; border: 2px solid #90A4AE;
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #78909C, stop:1 #607D8B); }
        QPushButton:disabled { background: #444; color: #666; }
        """)
        ince_ust_layout.addWidget(self.btn_acad_renk_geri)

        ince_isler_layout.addLayout(ince_ust_layout)

        # Katman seçim satırı
        katman_layout = QHBoxLayout()
        katman_layout.addWidget(QLabel("Katman:"))
        self.acad_katman_combo = QComboBox()
        self.acad_katman_combo.setEnabled(False)
        self.acad_katman_combo.setMinimumWidth(100)
        katman_layout.addWidget(self.acad_katman_combo)
        self.btn_acad_katman_sec = QPushButton("Katmanı Seç")
        self.btn_acad_katman_sec.clicked.connect(self._autocad_katman_sec)
        self.btn_acad_katman_sec.setEnabled(False)
        katman_layout.addWidget(self.btn_acad_katman_sec)
        ince_isler_layout.addLayout(katman_layout)

        # Katman değiştiğinde AI önerisini güncelle
        self.acad_katman_combo.currentTextChanged.connect(self._ai_katman_oneri_guncelle)

        # ──── AI ÖNERİ PANELİ ────────────────────────────────────────────
        self.ai_oneri_group = QGroupBox(" AI Önerisi")
        self.ai_oneri_group.setStyleSheet("""
        QGroupBox {
        color: #FFD700; font-weight: bold; font-size: 9pt;
        border: 2px solid #FFD700; border-radius: 4px;
        margin-top: 6px; padding-top: 14px;
        background-color: rgba(255, 215, 0, 15);
        }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        """)
        ai_inner = QHBoxLayout(self.ai_oneri_group)
        ai_inner.setContentsMargins(8, 4, 8, 4)
        ai_inner.setSpacing(12)
        self.ai_oneri_label = QLabel("—")
        self.ai_oneri_label.setStyleSheet("color: #e0e0e0; font-size: 10pt;")
        ai_inner.addWidget(self.ai_oneri_label, 1)
        btn_ai_uygula = QPushButton(" Öneriyi Uygula")
        btn_ai_uygula.setStyleSheet(
        "background-color: #FFD700; color: #000; font-weight: bold; padding: 5px 12px;"
        )
        btn_ai_uygula.clicked.connect(self._ai_oneri_uygula)
        ai_inner.addWidget(btn_ai_uygula)
        self.ai_oneri_group.setVisible(False)
        ince_isler_layout.addWidget(self.ai_oneri_group)

        # ──── DUVAR HESAPLAMA PANELİ ────
        duvar_group = QGroupBox("Duvar Hesaplama")
        duvar_group.setStyleSheet("""
        QGroupBox {
        color: #FFD700; font-weight: bold; font-size: 9pt;
        border: 1px solid #555; border-radius: 4px;
        margin-top: 6px; padding-top: 14px;
        }
        QGroupBox::title {
        subcontrol-origin: margin; left: 10px; padding: 0 4px;
        }
        """)
        duvar_inner = QHBoxLayout(duvar_group)
        duvar_inner.setContentsMargins(8, 4, 8, 4)
        duvar_inner.setSpacing(12)

        # Duvar Kalınlığı
        duvar_inner.addWidget(QLabel("Kalınlık:"))
        self.duvar_kalinlik_combo = QComboBox()
        self.duvar_kalinlik_combo.addItems(["10 cm", "15 cm", "20 cm"])
        self.duvar_kalinlik_combo.setCurrentIndex(1) # varsayılan 15 cm
        self.duvar_kalinlik_combo.setFixedWidth(80)
        self.duvar_kalinlik_combo.setToolTip("Duvar kalınlığı (tuğla/blok ölçüsü)")
        duvar_inner.addWidget(self.duvar_kalinlik_combo)

        # Ayırıcı
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("color: #555;")
        duvar_inner.addWidget(sep1)

        # Duvar Yüksekliği
        duvar_inner.addWidget(QLabel("Yükseklik:"))
        self.duvar_yukseklik_spin = QDoubleSpinBox()
        self.duvar_yukseklik_spin.setRange(0.50, 10.00)
        self.duvar_yukseklik_spin.setValue(2.80)
        self.duvar_yukseklik_spin.setSingleStep(0.10)
        self.duvar_yukseklik_spin.setDecimals(2)
        self.duvar_yukseklik_spin.setSuffix(" m")
        self.duvar_yukseklik_spin.setFixedWidth(90)
        self.duvar_yukseklik_spin.setToolTip("Duvar yüksekliği (metre)")
        duvar_inner.addWidget(self.duvar_yukseklik_spin)

        # Ayırıcı
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("color: #555;")
        duvar_inner.addWidget(sep2)

        # Duvar modu checkbox
        self.chk_duvar_modu = QCheckBox("Duvar Modu")
        self.chk_duvar_modu.setToolTip(
        "Aktifken: Polyline uzunluğu x duvar yüksekliği = duvar alanı\n"
        "Pasifken: Polyline ile kapalı alan hesaplanır"
        )
        self.chk_duvar_modu.setStyleSheet("color: #4FC3F7; font-weight: bold;")
        duvar_inner.addWidget(self.chk_duvar_modu)

        duvar_inner.addStretch()

        # Formül açıklaması
        self.duvar_formul_label = QLabel("Duvar m² = Uzunluk × Yükseklik")
        self.duvar_formul_label.setStyleSheet("color: #888; font-size: 8pt; font-style: italic;")
        duvar_inner.addWidget(self.duvar_formul_label)

        ince_isler_layout.addWidget(duvar_group)

        # ──── MENHA DÜŞÜMÜ ────
        menha_group = QGroupBox(" Menha Düşümü (Pencere / Kapı)")
        menha_group.setStyleSheet(
        "QGroupBox { font-weight: bold; color: #e67e22; border: 1px solid #e67e22; "
        "border-radius: 4px; margin-top: 8px; padding-top: 8px; }"
        "QGroupBox::title { subcontrol-origin: margin; left: 8px; }"
        )
        menha_main = QHBoxLayout(menha_group)
        menha_main.setSpacing(8)

        # Sol: form
        menha_form = QGridLayout()
        menha_form.setSpacing(4)

        menha_form.addWidget(QLabel("Eleman:"), 0, 0)
        self.menha_tip_combo = QComboBox()
        self.menha_tip_combo.addItems(["İç Kapı", "Dış Kapı", "Pencere", "Balkon Kapısı"])
        menha_form.addWidget(self.menha_tip_combo, 0, 1)

        menha_form.addWidget(QLabel("Genişlik (m):"), 1, 0)
        self.menha_gen_spin = QDoubleSpinBox()
        self.menha_gen_spin.setRange(0.1, 5.0)
        self.menha_gen_spin.setValue(0.90)
        self.menha_gen_spin.setSingleStep(0.05)
        self.menha_gen_spin.setDecimals(2)
        menha_form.addWidget(self.menha_gen_spin, 1, 1)

        menha_form.addWidget(QLabel("Yükseklik (m):"), 2, 0)
        self.menha_yuk_spin = QDoubleSpinBox()
        self.menha_yuk_spin.setRange(0.1, 4.0)
        self.menha_yuk_spin.setValue(2.10)
        self.menha_yuk_spin.setSingleStep(0.05)
        self.menha_yuk_spin.setDecimals(2)
        menha_form.addWidget(self.menha_yuk_spin, 2, 1)

        menha_form.addWidget(QLabel("Adet:"), 3, 0)
        self.menha_adet_spin = QSpinBox()
        self.menha_adet_spin.setRange(1, 999)
        self.menha_adet_spin.setValue(1)
        menha_form.addWidget(self.menha_adet_spin, 3, 1)

        btn_menha_ekle = QPushButton(" Ekle")
        btn_menha_ekle.setStyleSheet(
        "QPushButton { background: #27ae60; color: white; padding: 5px; border-radius: 3px; font-weight: bold; }"
        "QPushButton:hover { background: #2ecc71; }"
        )
        btn_menha_ekle.clicked.connect(self._menha_ekle)
        menha_form.addWidget(btn_menha_ekle, 4, 0, 1, 2)

        menha_main.addLayout(menha_form)

        # Sağ: tablo
        menha_sag = QVBoxLayout()
        self.menha_table = QTableWidget()
        self.menha_table.setColumnCount(5)
        self.menha_table.setHorizontalHeaderLabels(["Eleman", "Gen.(m)", "Yük.(m)", "Adet", "Alan(m²)"])
        self.menha_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.menha_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.menha_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.menha_table.setMinimumHeight(280)
        self.menha_table.setMaximumHeight(400)
        self.menha_table.setStyleSheet(
        "QTableWidget { background: #252535; color: white; gridline-color: #444; }"
        "QHeaderView::section { background: #333345; color: white; font-weight: bold; padding: 3px; border: 1px solid #555; }"
        )
        menha_sag.addWidget(self.menha_table)

        menha_alt = QHBoxLayout()
        self.menha_toplam_label = QLabel("Toplam Menha: 0.00 m²")
        self.menha_toplam_label.setStyleSheet("color: #e67e22; font-weight: bold;")
        menha_alt.addWidget(self.menha_toplam_label, 1)

        btn_menha_sil = QPushButton(" Seçili Sil")
        btn_menha_sil.setStyleSheet(
        "QPushButton { background: #c0392b; color: white; padding: 4px 8px; border-radius: 3px; }"
        "QPushButton:hover { background: #e74c3c; }"
        )
        btn_menha_sil.clicked.connect(self._menha_sil)
        menha_alt.addWidget(btn_menha_sil)

        btn_menha_uygula = QPushButton(" Duvar Kalemlerine Uygula")
        btn_menha_uygula.setStyleSheet(
        "QPushButton { background: #e67e22; color: white; padding: 4px 8px; border-radius: 3px; font-weight: bold; }"
        "QPushButton:hover { background: #f39c12; }"
        )
        btn_menha_uygula.clicked.connect(self._menha_uygula)
        menha_alt.addWidget(btn_menha_uygula)
        menha_sag.addLayout(menha_alt)

        menha_main.addLayout(menha_sag)
        ince_isler_layout.addWidget(menha_group)

        # ──── İÇ / DIŞ CEPHE ALT SEKMELERİ ────
        self.ince_sub_tabs = QTabWidget()
        self.ince_sub_tabs.setStyleSheet("""
        QTabWidget::pane { border: 1px solid #444; background: #252535; border-radius: 3px; }
        QTabBar::tab {
        background: #333345; color: #aaa; padding: 6px 12px;
        margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px;
        }
        QTabBar::tab:selected { background: #444460; color: white; font-weight: bold; }
        QTabBar::tab:hover { background: #444460; }
        """)

        # İç Cephe malzeme tanımları: (ad, birim, mod)
        # mod: "alan" = AutoCAD'den alan seç, "adet" = AutoCAD'den blok say
        self._ic_cephe_kalemleri = [
        ("Duvar Boyası", "m²", "alan"),
        ("Tavan Boyası", "m²", "alan"),
        ("Zemin Seramiği", "m²", "alan"),
        ("Duvar Seramiği", "m²", "alan"),
        ("Parke / Laminat", "m²", "alan"),
        ("İç Sıva", "m²", "alan"),
        ("Alçı Sıva", "m²", "alan"),
        ("Kartonpiyer", "m", "alan"),
        ("Süpürgelik", "m", "alan"),
        ("İç Kapı", "Adet", "adet"),
        ("Pencere", "Adet", "adet"),
        ("Lavabo", "Adet", "adet"),
        ("Klozet", "Adet", "adet"),
        ("Duş / Küvet", "Adet", "adet"),
        ("Mutfak Tezgahı", "m", "alan"),
        ]

        self._dis_cephe_kalemleri = [
        ("Mantolama", "m²", "alan"),
        ("Cephe Boyası", "m²", "alan"),
        ("Dekoratif Sıva", "m²", "alan"),
        ("Dış Cephe Kaplaması", "m²", "alan"),
        ("Denizlik", "m", "alan"),
        ("Parapet", "m", "alan"),
        ("Çatı Örtüsü", "m²", "alan"),
        ("Yağmur Oluğu", "m", "alan"),
        ("Balkon Korkuluğu", "m", "alan"),
        ("Dış Kapı", "Adet", "adet"),
        ("Garaj Kapısı", "Adet", "adet"),
        ]

        # İç Cephe sekmesi
        ic_tab = QWidget()
        ic_layout = QVBoxLayout(ic_tab)
        ic_layout.setContentsMargins(3, 3, 3, 3)
        self.ic_cephe_table = self._create_ince_isler_table(self._ic_cephe_kalemleri, "ic")
        ic_layout.addWidget(self.ic_cephe_table)
        btn_ic_ozel = QPushButton("+ Özel Kalem Ekle")
        btn_ic_ozel.setStyleSheet(
        "QPushButton { background: #444; color: #aaa; padding: 3px 8px; border: 1px solid #666; border-radius: 3px; font-size: 9pt; }"
        "QPushButton:hover { background: #555; color: white; }"
        )
        btn_ic_ozel.clicked.connect(lambda: self._ozel_kalem_ekle("ic"))
        ic_layout.addWidget(btn_ic_ozel, 0, Qt.AlignmentFlag.AlignRight)
        self.ince_sub_tabs.addTab(ic_tab, " İç Cephe")

        # Dış Cephe sekmesi
        dis_tab = QWidget()
        dis_layout = QVBoxLayout(dis_tab)
        dis_layout.setContentsMargins(3, 3, 3, 3)
        self.dis_cephe_table = self._create_ince_isler_table(self._dis_cephe_kalemleri, "dis")
        dis_layout.addWidget(self.dis_cephe_table)
        btn_dis_ozel = QPushButton("+ Özel Kalem Ekle")
        btn_dis_ozel.setStyleSheet(
        "QPushButton { background: #444; color: #aaa; padding: 3px 8px; border: 1px solid #666; border-radius: 3px; font-size: 9pt; }"
        "QPushButton:hover { background: #555; color: white; }"
        )
        btn_dis_ozel.clicked.connect(lambda: self._ozel_kalem_ekle("dis"))
        dis_layout.addWidget(btn_dis_ozel, 0, Qt.AlignmentFlag.AlignRight)
        self.ince_sub_tabs.addTab(dis_tab, " Dış Cephe")

        # ── Mahaller Sekmesi ──
        mahal_tab = QWidget()
        mahal_layout = QVBoxLayout(mahal_tab)
        mahal_layout.setContentsMargins(5, 5, 5, 5)
        mahal_layout.setSpacing(6)

        mahal_ekle_group = QGroupBox("Mahal Ekle")
        mahal_ekle_group.setStyleSheet(
        "QGroupBox { font-weight: bold; color: #9b59b6; border: 1px solid #9b59b6; "
        "border-radius: 4px; margin-top: 8px; padding-top: 8px; }"
        "QGroupBox::title { subcontrol-origin: margin; left: 8px; }"
        )
        mahal_ekle_inner = QGridLayout(mahal_ekle_group)
        mahal_ekle_inner.setSpacing(4)

        mahal_ekle_inner.addWidget(QLabel("Mahal Adı:"), 0, 0)
        self.mahal_ad_input = QLineEdit()
        self.mahal_ad_input.setPlaceholderText("Salon, Yatak Odası...")
        mahal_ekle_inner.addWidget(self.mahal_ad_input, 0, 1, 1, 2)

        mahal_ekle_inner.addWidget(QLabel("Tip:"), 1, 0)
        self.mahal_tip_combo = QComboBox()
        self.mahal_tip_combo.addItems(["Salon", "Yatak Odası", "Mutfak", "Banyo", "WC", "Koridor", "Diğer"])
        mahal_ekle_inner.addWidget(self.mahal_tip_combo, 1, 1)

        mahal_ekle_inner.addWidget(QLabel("Alan (m²):"), 2, 0)
        self.mahal_alan_spin = QDoubleSpinBox()
        self.mahal_alan_spin.setRange(0.5, 5000.0)
        self.mahal_alan_spin.setValue(20.0)
        self.mahal_alan_spin.setSingleStep(0.5)
        self.mahal_alan_spin.setDecimals(2)
        mahal_ekle_inner.addWidget(self.mahal_alan_spin, 2, 1)

        mahal_ekle_inner.addWidget(QLabel("Çevre (m):"), 3, 0)
        self.mahal_cevre_spin = QDoubleSpinBox()
        self.mahal_cevre_spin.setRange(0.0, 500.0)
        self.mahal_cevre_spin.setValue(0.0)
        self.mahal_cevre_spin.setSingleStep(0.1)
        self.mahal_cevre_spin.setDecimals(2)
        self.mahal_cevre_spin.setSpecialValueText("Oto-hesapla")
        self.mahal_cevre_spin.setToolTip("0 bırakılırsa alan'dan otomatik hesaplanır (kare oda tahmini)")
        mahal_ekle_inner.addWidget(self.mahal_cevre_spin, 3, 1)

        btn_mahal_ekle = QPushButton(" Ekle")
        btn_mahal_ekle.setStyleSheet(
        "QPushButton { background: #9b59b6; color: white; padding: 5px; border-radius: 3px; font-weight: bold; }"
        "QPushButton:hover { background: #8e44ad; }"
        )
        btn_mahal_ekle.clicked.connect(self._mahal_ekle)
        mahal_ekle_inner.addWidget(btn_mahal_ekle, 4, 0, 1, 3)

        mahal_layout.addWidget(mahal_ekle_group)

        self.mahal_table = QTableWidget()
        self.mahal_table.setColumnCount(5)
        self.mahal_table.setHorizontalHeaderLabels(["Mahal Adı", "Tip", "Alan (m²)", "Çevre (m)", "Hes. Çevre"])
        self.mahal_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.mahal_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.mahal_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.mahal_table.setStyleSheet(
        "QTableWidget { background: #252535; color: white; gridline-color: #444; }"
        "QHeaderView::section { background: #333345; color: white; font-weight: bold; padding: 3px; border: 1px solid #555; }"
        )
        mahal_layout.addWidget(self.mahal_table, 1)

        mahal_alt = QHBoxLayout()
        self.mahal_ozet_label = QLabel("Toplam Alan: 0.00 m² | Ort. Çevre: 0.00 m")
        self.mahal_ozet_label.setStyleSheet("color: #9b59b6; font-weight: bold;")
        mahal_alt.addWidget(self.mahal_ozet_label, 1)

        btn_mahal_sil = QPushButton(" Seçili Sil")
        btn_mahal_sil.setStyleSheet(
        "QPushButton { background: #c0392b; color: white; padding: 4px 8px; border-radius: 3px; }"
        "QPushButton:hover { background: #e74c3c; }"
        )
        btn_mahal_sil.clicked.connect(self._mahal_sil)
        mahal_alt.addWidget(btn_mahal_sil)

        btn_mahal_aktar = QPushButton(" İmalat Tablolarına Aktar")
        btn_mahal_aktar.setStyleSheet(
        "QPushButton { background: #e67e22; color: white; padding: 4px 8px; border-radius: 3px; font-weight: bold; }"
        "QPushButton:hover { background: #f39c12; }"
        )
        btn_mahal_aktar.clicked.connect(self._mahal_tablolara_aktar)
        mahal_alt.addWidget(btn_mahal_aktar)
        mahal_layout.addLayout(mahal_alt)

        self.ince_sub_tabs.addTab(mahal_tab, " Mahaller")

        # ──── 3D ÖNİZLEME ALT SEKMESİ ────────────────────────────────
        if _3D_MODUL_OK and InceIsler3DPanel is not None:
            self._3d_panel = InceIsler3DPanel(self)
            self.ince_sub_tabs.addTab(self._3d_panel, " 3D Önizleme")
        else:
            _3d_placeholder = QWidget()
            _3d_lbl = QLabel(
                " 3D modülü yüklenemedi.\n\n"
                "pip install matplotlib\n"
                "pip install pyopengl"
            )
            _3d_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _3d_lbl.setStyleSheet("color: #666; font-size: 11pt;")
            QVBoxLayout(_3d_placeholder).addWidget(_3d_lbl)
            self.ince_sub_tabs.addTab(_3d_placeholder, " 3D Önizleme")

        ince_isler_layout.addWidget(self.ince_sub_tabs, 1)

        # Alt toplam satırı
        self.ince_toplam_label = QLabel("Toplam: 0.00 m² / 0 Adet")
        self.ince_toplam_label.setStyleSheet(
        "color: #4CAF50; font-weight: bold; font-size: 10pt; padding: 5px;"
        "background: #1a2a1a; border-radius: 4px;"
        )
        self.ince_toplam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ince_isler_layout.addWidget(self.ince_toplam_label)

        # Maliyet + Araç Butonları satırı
        alt_bar = QHBoxLayout()

        self.ince_maliyet_label = QLabel("Tahmini Maliyet: 0.00 ₺")
        self.ince_maliyet_label.setStyleSheet(
        "color: #f39c12; font-weight: bold; font-size: 10pt; padding: 5px;"
        "background: #2a1f0a; border-radius: 4px;"
        )
        self.ince_maliyet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        alt_bar.addWidget(self.ince_maliyet_label, 1)

        btn_sarfiyat = QPushButton(" Sarfiyat Ayarları")
        btn_sarfiyat.setStyleSheet(
        "QPushButton { background: #444; color: #ccc; padding: 5px 10px; border: 1px solid #666; border-radius: 4px; }"
        "QPushButton:hover { background: #555; }"
        )
        btn_sarfiyat.clicked.connect(self._sarfiyat_ayarlari_ac)
        alt_bar.addWidget(btn_sarfiyat)

        btn_pdf = QPushButton(" PDF Rapor")
        btn_pdf.setStyleSheet(
        "QPushButton { background: #c0392b; color: white; padding: 5px 10px; border: 1px solid #e74c3c; border-radius: 4px; font-weight: bold; }"
        "QPushButton:hover { background: #e74c3c; }"
        )
        btn_pdf.clicked.connect(self._pdf_raporu_olustur)
        alt_bar.addWidget(btn_pdf)

        ince_isler_layout.addLayout(alt_bar)

        # Scroll area içeriği bağla ve tab'a ekle
        _ince_scroll.setWidget(_ince_content)
        _ince_outer_layout.addWidget(_ince_scroll)
        self.acad_tab_widget.addTab(ince_isler_tab, " İnce İşler")

        # ─────────────────────────────────────────────────────────────────
        # SEKME 2: DEMİR METRAJI
        # ─────────────────────────────────────────────────────────────────
        demir_tab = QWidget()
        _demir_outer = QVBoxLayout(demir_tab)
        _demir_outer.setContentsMargins(0, 0, 0, 0)
        _demir_outer.setSpacing(0)
        _demir_scroll = QScrollArea()
        _demir_scroll.setWidgetResizable(True)
        _demir_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _demir_scroll.setStyleSheet(
        "QScrollArea { border: none; background: transparent; }"
        "QScrollBar:vertical { background:#1a1a2e; width:8px; border-radius:4px; }"
        "QScrollBar::handle:vertical { background:#555; border-radius:4px; min-height:20px; }"
        )
        _demir_content = QWidget()
        demir_layout = QVBoxLayout(_demir_content)
        demir_layout.setContentsMargins(5, 10, 5, 5)

        # Demir Metraj butonu
        self.btn_acad_demir = QPushButton(" DEMİR METRAJİ AL")
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
        self.btn_kolon_grup = QPushButton(" KOLON/PERDE HESAPLA")
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

        # Kolon Filizi Tablo Okuma butonu
        self.btn_kolon_filizi = QPushButton(" KOLON FİLİZİ OKU")
        self.btn_kolon_filizi.clicked.connect(self._autocad_kolon_filizi_oku)
        self.btn_kolon_filizi.setEnabled(False)
        self.btn_kolon_filizi.setToolTip(
        "Kolon filizi tablosunu AutoCAD'den okur:\n"
        "• Tüm tabloyu kutu çizerek seçin\n"
        "• Program KOLON, DONATI, BOY sütunlarını otomatik tanır\n"
        "• Örnek: SB01 | P84-28Ø14 | 135"
        )
        self.btn_kolon_filizi.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8B4513, stop:1 #A0522D);
        color: white;
        font-weight: bold;
        font-size: 11pt;
        padding: 10px;
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
        demir_layout.addWidget(self.btn_kolon_filizi)

        # Demir birim seçimi
        demir_birim_layout = QHBoxLayout()
        demir_birim_layout.addWidget(QLabel("Boy Birimi:"))
        self.demir_birim_combo = QComboBox()
        self.demir_birim_combo.addItems(["cm", "m"])
        self.demir_birim_combo.setCurrentIndex(0) # Varsayılan: cm
        self.demir_birim_combo.setEnabled(False)
        demir_birim_layout.addWidget(self.demir_birim_combo)

        self.btn_demir_renk_geri = QPushButton("↩ Renkleri Geri Al")
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

        kat_label = QLabel(" Kat İsmi Girişi")
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
        self.demir_kat_listesi.setMinimumHeight(200)
        self.demir_kat_listesi.setMaximumHeight(350)
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
        self.btn_kat_sil = QPushButton(" Seçili Katı Sil")
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
        demir_info = QLabel(" Önce kat ekleyin, sonra demir yazılarını seçin")
        demir_info.setStyleSheet("color: #888; font-size: 9pt; padding: 5px;")
        demir_layout.addWidget(demir_info)

        # Renk açıklaması
        renk_info = QLabel(" Geçerli = YEŞİL | Geçersiz = KIRMIZI")
        renk_info.setStyleSheet("color: #aaa; font-size: 8pt; padding: 3px;")
        demir_layout.addWidget(renk_info)

        # Demir Excel Export butonu
        self.btn_demir_excel = QPushButton(" DEMİR EXCEL'E AKTAR")
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

        # ─────────────────────────────────────────────────────────────────
        # SEKME 2: KABA İNŞAAT (Demir Metrajı + Beton & Kalıp alt sekmeleri)
        # ─────────────────────────────────────────────────────────────────
        kaba_insaat_tab = QWidget()
        kaba_insaat_layout = QVBoxLayout(kaba_insaat_tab)
        kaba_insaat_layout.setContentsMargins(0, 0, 0, 0)
        kaba_insaat_layout.setSpacing(0)

        kaba_insaat_sub_tabs = QTabWidget()
        kaba_insaat_sub_tabs.setStyleSheet("""
        QTabWidget::pane {
        border: 1px solid #444;
        background: #1e1e2e;
        }
        QTabBar::tab {
        background: #2a2a3a;
        color: #ccc;
        padding: 6px 14px;
        border: 1px solid #444;
        border-bottom: none;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
        background: #1e1e2e;
        color: #fff;
        font-weight: bold;
        border-top: 2px solid #f39c12;
        }
        QTabBar::tab:hover {
        background: #333355;
        }
        """)

        # Alt sekme 0: Mevcut Demir Metrajı içeriği
        _demir_scroll.setWidget(_demir_content)
        _demir_outer.addWidget(_demir_scroll)
        kaba_insaat_sub_tabs.addTab(demir_tab, " Demir Metrajı")

        # Alt sekme 1: Beton & Kalıp
        beton_kalip_tab = QWidget()
        _bk_outer = QVBoxLayout(beton_kalip_tab)
        _bk_outer.setContentsMargins(0, 0, 0, 0)
        _bk_outer.setSpacing(0)
        _bk_scroll = QScrollArea()
        _bk_scroll.setWidgetResizable(True)
        _bk_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _bk_scroll.setStyleSheet(
        "QScrollArea { border: none; background: transparent; }"
        "QScrollBar:vertical { background:#1a1a2e; width:8px; border-radius:4px; }"
        "QScrollBar::handle:vertical { background:#555; border-radius:4px; min-height:20px; }"
        )
        _bk_content = QWidget()
        bk_layout = QVBoxLayout(_bk_content)
        bk_layout.setContentsMargins(6, 6, 6, 6)
        bk_layout.setSpacing(6)

        # --- Eleman ekleme formu ---
        bk_form_group = QGroupBox("Eleman Ekle")
        bk_form_group.setStyleSheet("""
        QGroupBox {
        color: #f39c12;
        font-weight: bold;
        border: 1px solid #f39c12;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 6px;
        }
        QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px;
        }
        """)
        bk_form_layout = QGridLayout(bk_form_group)
        bk_form_layout.setSpacing(6)

        # Eleman türü combo
        bk_form_layout.addWidget(QLabel("Eleman Türü:"), 0, 0)
        self.bk_eleman_combo = QComboBox()
        self.bk_eleman_combo.addItems(
        ["Kolon", "Kiriş", "Döşeme", "Temel", "Perde Duvar"]
        )
        self.bk_eleman_combo.setStyleSheet(
        "background:#2a2a3a; color:white; border:1px solid #666; padding:4px;"
        )
        self.bk_eleman_combo.currentTextChanged.connect(self._beton_kalip_eleman_degisti)
        bk_form_layout.addWidget(self.bk_eleman_combo, 0, 1)

        # Adet spin
        bk_form_layout.addWidget(QLabel("Adet:"), 0, 2)
        self.bk_adet_spin = QSpinBox()
        self.bk_adet_spin.setRange(1, 9999)
        self.bk_adet_spin.setValue(1)
        self.bk_adet_spin.setStyleSheet(
        "background:#2a2a3a; color:white; border:1px solid #666; padding:4px;"
        )
        bk_form_layout.addWidget(self.bk_adet_spin, 0, 3)

        # Boyut 1
        self.bk_dim1_label = QLabel("Boy (m):")
        bk_form_layout.addWidget(self.bk_dim1_label, 1, 0)
        self.bk_dim1_spin = QDoubleSpinBox()
        self.bk_dim1_spin.setRange(0.01, 999.0)
        self.bk_dim1_spin.setValue(0.50)
        self.bk_dim1_spin.setSingleStep(0.05)
        self.bk_dim1_spin.setDecimals(2)
        self.bk_dim1_spin.setStyleSheet(
        "background:#2a2a3a; color:white; border:1px solid #666; padding:4px;"
        )
        bk_form_layout.addWidget(self.bk_dim1_spin, 1, 1)

        # Boyut 2
        self.bk_dim2_label = QLabel("En (m):")
        bk_form_layout.addWidget(self.bk_dim2_label, 1, 2)
        self.bk_dim2_spin = QDoubleSpinBox()
        self.bk_dim2_spin.setRange(0.01, 999.0)
        self.bk_dim2_spin.setValue(0.50)
        self.bk_dim2_spin.setSingleStep(0.05)
        self.bk_dim2_spin.setDecimals(2)
        self.bk_dim2_spin.setStyleSheet(
        "background:#2a2a3a; color:white; border:1px solid #666; padding:4px;"
        )
        bk_form_layout.addWidget(self.bk_dim2_spin, 1, 3)

        # Boyut 3
        self.bk_dim3_label = QLabel("Yükseklik (m):")
        bk_form_layout.addWidget(self.bk_dim3_label, 1, 4)
        self.bk_dim3_spin = QDoubleSpinBox()
        self.bk_dim3_spin.setRange(0.01, 999.0)
        self.bk_dim3_spin.setValue(3.00)
        self.bk_dim3_spin.setSingleStep(0.05)
        self.bk_dim3_spin.setDecimals(2)
        self.bk_dim3_spin.setStyleSheet(
        "background:#2a2a3a; color:white; border:1px solid #666; padding:4px;"
        )
        bk_form_layout.addWidget(self.bk_dim3_spin, 1, 5)

        # Fire katsayısı (satır 2)
        self.bk_fire_label = QLabel("Fire Payı (%):")
        self.bk_fire_label.setStyleSheet("color:#f39c12; font-weight:bold;")
        bk_form_layout.addWidget(self.bk_fire_label, 2, 0)

        self.bk_fire_spin = QDoubleSpinBox()
        self.bk_fire_spin.setRange(0.0, 20.0)
        self.bk_fire_spin.setValue(5.0)
        self.bk_fire_spin.setSingleStep(0.5)
        self.bk_fire_spin.setDecimals(1)
        self.bk_fire_spin.setSuffix(" %")
        self.bk_fire_spin.setToolTip(
        "Döküm kaybı, kalıp sızıntısı ve işçilik firesini kapsar.\n"
        "Kolon/Kiriş: %3–5 | Döşeme: %2–3 | Temel: %5–8"
        )
        self.bk_fire_spin.setStyleSheet(
        "background:#2a2a3a; color:#f39c12; border:1px solid #f39c12;"
        " padding:4px; font-weight:bold;"
        )
        bk_form_layout.addWidget(self.bk_fire_spin, 2, 1)

        self.bk_fire_oneri_label = QLabel("(Kolon için önerilen: %5)")
        self.bk_fire_oneri_label.setStyleSheet(
        "color:#aaa; font-size:8pt; font-style:italic; border:none;"
        )
        bk_form_layout.addWidget(self.bk_fire_oneri_label, 2, 2, 1, 4)

        # AutoCAD ölçüm satırı (satır 3)
        lbl_acad_birim = QLabel("AutoCAD Birimi:")
        lbl_acad_birim.setStyleSheet("color:#4fc3f7;")
        bk_form_layout.addWidget(lbl_acad_birim, 3, 0)

        self.bk_acad_birim_combo = QComboBox()
        self.bk_acad_birim_combo.addItems(["cm", "mm", "m"])
        self.bk_acad_birim_combo.setToolTip(
        "Çizimdeki ölçü birimi:\n"
        "cm → çoğu mimari/statik plan\n"
        "mm → detay ve kalıp planı\n"
        "m → 1:1 ölçekli sayısal çizimler"
        )
        self.bk_acad_birim_combo.setStyleSheet(
        "background:#2a2a3a; color:#4fc3f7; border:1px solid #4fc3f7; padding:4px;"
        )
        bk_form_layout.addWidget(self.bk_acad_birim_combo, 3, 1)

        self.btn_bk_acad_olc = QPushButton(" AutoCAD'den Ölç")
        self.btn_bk_acad_olc.clicked.connect(self._beton_kalip_acad_olc)
        self.btn_bk_acad_olc.setEnabled(False)
        self.btn_bk_acad_olc.setToolTip(
        "AutoCAD'e bağlandıktan sonra aktif olur.\n"
        "Kolon/Kiriş: kesit polyline'ını tıklayın\n"
        "Döşeme/Temel: kapalı alanı tıklayın\n"
        "Perde Duvar: eksen çizgisini tıklayın"
        )
        self.btn_bk_acad_olc.setStyleSheet("""
        QPushButton {
        background: #1a3a4a;
        color: #4fc3f7;
        font-weight: bold;
        padding: 6px 14px;
        border: 1px solid #4fc3f7;
        border-radius: 4px;
        }
        QPushButton:hover {
        background: #1e5a7a;
        }
        QPushButton:disabled {
        background: #222;
        color: #555;
        border-color: #444;
        }
        """)
        bk_form_layout.addWidget(self.btn_bk_acad_olc, 3, 2, 1, 4)

        # Ekle butonu
        btn_bk_ekle = QPushButton("+ Ekle")
        btn_bk_ekle.clicked.connect(self._beton_kalip_kalem_ekle)
        btn_bk_ekle.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #f39c12, stop:1 #d68910);
        color: #1a1a1a;
        font-weight: bold;
        padding: 6px 16px;
        border: none;
        border-radius: 4px;
        }
        QPushButton:hover {
        background: #f5b942;
        }
        """)
        bk_form_layout.addWidget(btn_bk_ekle, 0, 4, 1, 2)

        bk_layout.addWidget(bk_form_group)

        # --- Tablo ---
        self.beton_kalip_table = QTableWidget()
        self.beton_kalip_table.setColumnCount(9)
        self.beton_kalip_table.setHorizontalHeaderLabels(
        ["Eleman", "Adet", "Ölçü1 (m)", "Ölçü2 (m)", "Ölçü3 (m)",
        "Net Beton (m³)", "Fire (%)", "Sipariş (m³)", "Kalıp (m²)"]
        )
        self.beton_kalip_table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.Stretch
        )
        self.beton_kalip_table.setSelectionBehavior(
        QTableWidget.SelectionBehavior.SelectRows
        )
        self.beton_kalip_table.setEditTriggers(
        QTableWidget.EditTrigger.NoEditTriggers
        )
        self.beton_kalip_table.setStyleSheet("""
        QTableWidget {
        background: #1e1e2e;
        color: #e0e0e0;
        gridline-color: #444;
        border: 1px solid #555;
        }
        QHeaderView::section {
        background: #2d2d3d;
        color: #f39c12;
        font-weight: bold;
        padding: 5px;
        border: 1px solid #444;
        }
        QTableWidget::item:selected {
        background: #3a3a5a;
        }
        """)
        bk_layout.addWidget(self.beton_kalip_table)

        # --- Alt butonlar ---
        bk_btn_layout = QHBoxLayout()
        btn_bk_sil = QPushButton("Seçili Sil")
        btn_bk_sil.clicked.connect(self._beton_kalip_satir_sil)
        btn_bk_sil.setStyleSheet(
        "background:#c0392b; color:white; font-weight:bold;"
        " padding:5px 12px; border:none; border-radius:3px;"
        )
        bk_btn_layout.addWidget(btn_bk_sil)

        btn_bk_temizle = QPushButton("Temizle")
        btn_bk_temizle.clicked.connect(lambda: (
        self.beton_kalip_table.setRowCount(0),
        self._beton_kalip_toplamlar_guncelle()
        ))
        btn_bk_temizle.setStyleSheet(
        "background:#7f8c8d; color:white; font-weight:bold;"
        " padding:5px 12px; border:none; border-radius:3px;"
        )
        bk_btn_layout.addWidget(btn_bk_temizle)

        bk_btn_layout.addStretch()

        btn_bk_excel = QPushButton(" Excel")
        btn_bk_excel.clicked.connect(self._beton_kalip_excel)
        btn_bk_excel.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #27ae60, stop:1 #1e8449);
        color: white;
        font-weight: bold;
        padding: 5px 14px;
        border: 2px solid #2ecc71;
        border-radius: 3px;
        }
        QPushButton:hover {
        background: #2ecc71;
        }
        """)
        bk_btn_layout.addWidget(btn_bk_excel)
        bk_layout.addLayout(bk_btn_layout)

        # --- Toplam bar ---
        bk_toplam_frame = QFrame()
        bk_toplam_frame.setFrameShape(QFrame.Shape.StyledPanel)
        bk_toplam_frame.setStyleSheet(
        "QFrame { background:#2a2a3a; border:1px solid #f39c12;"
        " border-radius:4px; padding:4px; }"
        )
        bk_toplam_layout = QHBoxLayout(bk_toplam_frame)
        bk_toplam_layout.setContentsMargins(8, 4, 8, 4)

        self.bk_toplam_beton_label = QLabel("Net Beton: 0.000 m³")
        self.bk_toplam_beton_label.setStyleSheet(
        "color:#3498db; font-weight:bold; font-size:10pt; border:none;"
        )
        bk_toplam_layout.addWidget(self.bk_toplam_beton_label)

        bk_toplam_layout.addStretch()

        self.bk_toplam_siparis_label = QLabel("Sipariş: 0.000 m³")
        self.bk_toplam_siparis_label.setStyleSheet(
        "color:#f39c12; font-weight:bold; font-size:10pt; border:none;"
        )
        bk_toplam_layout.addWidget(self.bk_toplam_siparis_label)

        bk_toplam_layout.addStretch()

        self.bk_toplam_kalip_label = QLabel("Toplam Kalıp: 0.000 m²")
        self.bk_toplam_kalip_label.setStyleSheet(
        "color:#e74c3c; font-weight:bold; font-size:10pt; border:none;"
        )
        bk_toplam_layout.addWidget(self.bk_toplam_kalip_label)

        bk_layout.addWidget(bk_toplam_frame)

        _bk_scroll.setWidget(_bk_content)
        _bk_outer.addWidget(_bk_scroll)
        kaba_insaat_sub_tabs.addTab(beton_kalip_tab, " Beton & Kalıp")

        # ─────────────────────────────────────────────────────────────────
        # Alt sekme 2: Hızlı Keşif (eski "Kaba Yapı" sekmesi buraya taşındı)
        # DXF olmadan katsayı tabanlı yaklaşık metraj hesabı
        # ─────────────────────────────────────────────────────────────────
        hizli_kesif_tab = QWidget()
        _kesif_outer = QVBoxLayout(hizli_kesif_tab)
        _kesif_outer.setContentsMargins(0, 0, 0, 0)
        _kesif_outer.setSpacing(0)
        _kesif_scroll = QScrollArea()
        _kesif_scroll.setWidgetResizable(True)
        _kesif_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _kesif_scroll.setStyleSheet(
        "QScrollArea { border: none; background: transparent; }"
        "QScrollBar:vertical { background:#1a1a2e; width:8px; border-radius:4px; }"
        "QScrollBar::handle:vertical { background:#555; border-radius:4px; min-height:20px; }"
        )
        _kesif_content = QWidget()
        hizli_kesif_layout = QVBoxLayout(_kesif_content)
        hizli_kesif_layout.setContentsMargins(8, 8, 8, 8)
        hizli_kesif_layout.setSpacing(8)

        kesif_info = QLabel(
        "DXF olmadan hızlı yaklaşık keşif.\n"
        "Alan + kat sayısı girerek beton / kalıp / demir miktarlarını tahmin edin.\n"
        "Detaylı hesap için üstteki 'Demir Metrajı' ve 'Beton & Kalıp' sekmelerini kullanın."
        )
        kesif_info.setStyleSheet(
        "color: #aaa; font-size: 9pt; padding: 6px;"
        " border: 1px solid #444; border-radius: 4px; background: #1a1a2e;"
        )
        kesif_info.setWordWrap(True)
        hizli_kesif_layout.addWidget(kesif_info)

        kaba_grid = QGridLayout()
        kaba_grid.setSpacing(6)

        kaba_grid.addWidget(QLabel("Toplam İnşaat Alanı (m²):"), 0, 0)
        self.kaba_alan_spin = QDoubleSpinBox()
        self.kaba_alan_spin.setRange(0, 999999)
        self.kaba_alan_spin.setValue(0)
        self.kaba_alan_spin.setDecimals(2)
        self.kaba_alan_spin.setSuffix(" m²")
        self.kaba_alan_spin.setStyleSheet(
        "background:#2a2a3a; color:white; border:1px solid #666; padding:4px;"
        )
        kaba_grid.addWidget(self.kaba_alan_spin, 0, 1)

        kaba_grid.addWidget(QLabel("Kat Sayısı:"), 1, 0)
        self.kaba_kat_sayi_spin = QSpinBox()
        self.kaba_kat_sayi_spin.setRange(1, 50)
        self.kaba_kat_sayi_spin.setValue(3)
        self.kaba_kat_sayi_spin.setStyleSheet(
        "background:#2a2a3a; color:white; border:1px solid #666; padding:4px;"
        )
        kaba_grid.addWidget(self.kaba_kat_sayi_spin, 1, 1)

        kaba_grid.addWidget(QLabel("Kat Yüksekliği (m):"), 2, 0)
        self.kaba_kat_yuk_spin = QDoubleSpinBox()
        self.kaba_kat_yuk_spin.setRange(2.0, 10.0)
        self.kaba_kat_yuk_spin.setValue(3.0)
        self.kaba_kat_yuk_spin.setSingleStep(0.1)
        self.kaba_kat_yuk_spin.setSuffix(" m")
        self.kaba_kat_yuk_spin.setStyleSheet(
        "background:#2a2a3a; color:white; border:1px solid #666; padding:4px;"
        )
        kaba_grid.addWidget(self.kaba_kat_yuk_spin, 2, 1)

        kaba_grid.addWidget(QLabel("Yapı Sistemi:"), 3, 0)
        self.kaba_sistem_combo = QComboBox()
        self.kaba_sistem_combo.addItems([
        "Betonarme Çerçeve",
        "Betonarme Perde+Çerçeve",
        "Yığma Tuğla",
        "Çelik Konstrüksiyon",
        ])
        self.kaba_sistem_combo.setStyleSheet(
        "background:#2a2a3a; color:white; border:1px solid #666; padding:4px;"
        )
        kaba_grid.addWidget(self.kaba_sistem_combo, 3, 1)

        hizli_kesif_layout.addLayout(kaba_grid)

        btn_kaba_hesapla = QPushButton(" HIZLI KEŞİF HESAPLA")
        btn_kaba_hesapla.clicked.connect(self._kaba_yapi_hesapla)
        btn_kaba_hesapla.setStyleSheet(
        "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #e67e22,stop:1 #d35400);"
        "color:white; font-weight:bold; font-size:11pt; padding:10px;"
        "border:2px solid #f39c12; border-radius:4px;"
        )
        hizli_kesif_layout.addWidget(btn_kaba_hesapla)

        self.kaba_yapi_table = QTableWidget()
        self.kaba_yapi_table.setColumnCount(3)
        self.kaba_yapi_table.setHorizontalHeaderLabels(["İmalat Kalemi", "Miktar", "Birim"])
        self.kaba_yapi_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.kaba_yapi_table.setMinimumHeight(200)
        self.kaba_yapi_table.setStyleSheet(
        "QTableWidget { background:#1e1e2e; border:1px solid #555; }"
        "QHeaderView::section { background:#333; color:#FFD700; font-weight:bold; padding:4px; }"
        )
        hizli_kesif_layout.addWidget(self.kaba_yapi_table)

        _kesif_scroll.setWidget(_kesif_content)
        _kesif_outer.addWidget(_kesif_scroll)
        kaba_insaat_sub_tabs.addTab(hizli_kesif_tab, " Hızlı Keşif")

        kaba_insaat_layout.addWidget(kaba_insaat_sub_tabs)
        self.acad_tab_widget.addTab(kaba_insaat_tab, " Kaba İnşaat")

        # ─────────────────────────────────────────────────────────────────
        # SEKME 3: ÇOKLU KAT YÖNETİMİ — AutoCAD tabanlı kat bazlı metraj
        # ─────────────────────────────────────────────────────────────────
        coklu_kat_tab = QWidget()
        _ck_outer = QVBoxLayout(coklu_kat_tab)
        _ck_outer.setContentsMargins(0, 0, 0, 0)
        _ck_outer.setSpacing(0)
        _ck_scroll = QScrollArea()
        _ck_scroll.setWidgetResizable(True)
        _ck_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _ck_scroll.setStyleSheet(
        "QScrollArea { border: none; background: transparent; }"
        "QScrollBar:vertical { background:#1a1a2e; width:8px; border-radius:4px; }"
        "QScrollBar::handle:vertical { background:#555; border-radius:4px; min-height:20px; }"
        )
        _ck_content = QWidget()
        coklu_kat_layout = QVBoxLayout(_ck_content)
        coklu_kat_layout.setContentsMargins(6, 6, 6, 6)
        coklu_kat_layout.setSpacing(6)

        # ── AutoCAD bağlan butonu ──────────────────────────────────────
        self.btn_ck_baglan = QPushButton(" AutoCAD'e Bağlan")
        self.btn_ck_baglan.clicked.connect(self._autocad_baglan)
        self.btn_ck_baglan.setStyleSheet(
        "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #6a1b9a,stop:1 #4a148c);"
        "color:white; font-weight:bold; font-size:10pt; padding:8px;"
        "border:2px solid #9c27b0; border-radius:4px;"
        )
        coklu_kat_layout.addWidget(self.btn_ck_baglan)

        # ── Kat listesi ────────────────────────────────────────────────
        ck_list_label = QLabel(" Kat Listesi")
        ck_list_label.setStyleSheet("color:#ce93d8; font-weight:bold; font-size:9pt;")
        coklu_kat_layout.addWidget(ck_list_label)

        ck_ekle_layout = QHBoxLayout()
        self.coklu_kat_input = QLineEdit()
        self.coklu_kat_input.setPlaceholderText("Kat adı: Bodrum, Zemin, 1. Kat...")
        self.coklu_kat_input.setStyleSheet("border:1px solid #666; padding:4px; background:#2a2a3a; color:white;")
        self.coklu_kat_input.returnPressed.connect(self._coklu_kat_ekle)
        ck_ekle_layout.addWidget(self.coklu_kat_input)

        btn_ck_ekle = QPushButton("+ Kat Ekle")
        btn_ck_ekle.clicked.connect(self._coklu_kat_ekle)
        btn_ck_ekle.setStyleSheet(
        "background:#7b1fa2; color:white; font-weight:bold; padding:5px 12px; border:none; border-radius:3px;"
        )
        ck_ekle_layout.addWidget(btn_ck_ekle)
        coklu_kat_layout.addLayout(ck_ekle_layout)

        self.coklu_kat_listesi = QListWidget()
        self.coklu_kat_listesi.setMaximumHeight(110)
        self.coklu_kat_listesi.setStyleSheet(
        "QListWidget { background:#2a2a3a; border:1px solid #555; color:white; }"
        "QListWidget::item { padding:5px; border-bottom:1px solid #3a3a4a; }"
        "QListWidget::item:selected { background:#6a1b9a; }"
        )
        self.coklu_kat_listesi.currentRowChanged.connect(self._coklu_kat_aktif_degisti)
        coklu_kat_layout.addWidget(self.coklu_kat_listesi)

        btn_ck_sil = QPushButton(" Seçili Katı Sil")
        btn_ck_sil.clicked.connect(self._coklu_kat_sil)
        btn_ck_sil.setStyleSheet(
        "background:#c0392b; color:white; padding:3px 8px; border:none; font-size:9pt;"
        )
        coklu_kat_layout.addWidget(btn_ck_sil)

        # ── Ayırıcı ────────────────────────────────────────────────────
        ck_sep = QFrame()
        ck_sep.setFrameShape(QFrame.Shape.HLine)
        ck_sep.setStyleSheet("color:#555; background:#555; margin:4px 0;")
        coklu_kat_layout.addWidget(ck_sep)

        # ── Aktif kat ölçüm paneli ─────────────────────────────────────
        self.ck_aktif_label = QLabel(" Aktif Kat: — (Listeden kat seçin)")
        self.ck_aktif_label.setStyleSheet(
        "color:#ce93d8; font-weight:bold; font-size:10pt; padding:3px;"
        "background:#2a1a3a; border-radius:3px;"
        )
        coklu_kat_layout.addWidget(self.ck_aktif_label)

        # Ölçüm adı + birim satırı
        ck_olcum_form = QHBoxLayout()
        self.ck_olcum_adi_input = QLineEdit()
        self.ck_olcum_adi_input.setPlaceholderText("Ölçüm adı: Döşeme, Dış Duvar, Kolon...")
        self.ck_olcum_adi_input.setStyleSheet(
        "border:1px solid #666; padding:4px; background:#2a2a3a; color:white;"
        )
        ck_olcum_form.addWidget(self.ck_olcum_adi_input, 3)

        self.ck_olcum_birim_combo = QComboBox()
        self.ck_olcum_birim_combo.addItems(["m²", "m", "adet", "m³", "kg"])
        self.ck_olcum_birim_combo.setStyleSheet(
        "background:#2a2a3a; color:white; border:1px solid #666; padding:4px;"
        )
        ck_olcum_form.addWidget(self.ck_olcum_birim_combo, 1)
        coklu_kat_layout.addLayout(ck_olcum_form)

        # AutoCAD ölçüm butonları
        ck_acad_btn_layout = QHBoxLayout()
        ck_acad_btn_layout.setSpacing(4)

        self.btn_ck_polyline = QPushButton(" Polyline Çiz")
        self.btn_ck_polyline.clicked.connect(self._coklu_kat_olcum_polyline)
        self.btn_ck_polyline.setToolTip(
        "AutoCAD'de polyline çizerek alan (m²) veya uzunluk (m) ölçer.\n"
        "Kapalı çizim → alan, açık çizim → uzunluk."
        )
        self.btn_ck_polyline.setStyleSheet(
        "background:#4a148c; color:white; font-weight:bold; padding:7px 4px; border:1px solid #9c27b0; border-radius:3px;"
        )
        ck_acad_btn_layout.addWidget(self.btn_ck_polyline)

        self.btn_ck_obje = QPushButton(" Obje Seç")
        self.btn_ck_obje.clicked.connect(self._coklu_kat_olcum_obje)
        self.btn_ck_obje.setToolTip(
        "AutoCAD'de obje(ler) seçerek ölçüm alır.\n"
        "Alan ölçümleri için kapalı polyline/hatch seçin."
        )
        self.btn_ck_obje.setStyleSheet(
        "background:#4a148c; color:white; font-weight:bold; padding:7px 4px; border:1px solid #9c27b0; border-radius:3px;"
        )
        ck_acad_btn_layout.addWidget(self.btn_ck_obje)

        self.btn_ck_katman = QPushButton(" Katmandan")
        self.btn_ck_katman.clicked.connect(self._coklu_kat_olcum_katman)
        self.btn_ck_katman.setToolTip(
        "Seçtiğiniz AutoCAD katmanındaki tüm objelerin\n"
        "toplam alan veya uzunluğunu alır."
        )
        self.btn_ck_katman.setStyleSheet(
        "background:#4a148c; color:white; font-weight:bold; padding:7px 4px; border:1px solid #9c27b0; border-radius:3px;"
        )
        ck_acad_btn_layout.addWidget(self.btn_ck_katman)

        self.btn_ck_manuel = QPushButton(" Manuel")
        self.btn_ck_manuel.clicked.connect(self._coklu_kat_olcum_manuel)
        self.btn_ck_manuel.setToolTip("AutoCAD olmadan değer gir.")
        self.btn_ck_manuel.setStyleSheet(
        "background:#37474f; color:white; font-weight:bold; padding:7px 4px; border:1px solid #607d8b; border-radius:3px;"
        )
        ck_acad_btn_layout.addWidget(self.btn_ck_manuel)
        coklu_kat_layout.addLayout(ck_acad_btn_layout)

        # Bu katın ölçümleri tablosu
        ck_tablo_label = QLabel("Bu Katın Ölçümleri:")
        ck_tablo_label.setStyleSheet("color:#aaa; font-size:9pt; margin-top:4px;")
        coklu_kat_layout.addWidget(ck_tablo_label)

        self.ck_olcum_table = QTableWidget()
        self.ck_olcum_table.setColumnCount(3)
        self.ck_olcum_table.setHorizontalHeaderLabels(["Ölçüm Adı", "Miktar", "Birim"])
        self.ck_olcum_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.ck_olcum_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.ck_olcum_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.ck_olcum_table.setMinimumHeight(150)
        self.ck_olcum_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ck_olcum_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.ck_olcum_table.setStyleSheet(
        "QTableWidget { background:#1e1e2e; border:1px solid #555; color:white; }"
        "QHeaderView::section { background:#333; color:#ce93d8; font-weight:bold; padding:4px; }"
        "QTableWidget::item:selected { background:#4a148c; }"
        )
        coklu_kat_layout.addWidget(self.ck_olcum_table)

        btn_ck_olcum_sil = QPushButton(" Seçili Ölçümü Sil")
        btn_ck_olcum_sil.clicked.connect(self._coklu_kat_olcum_sil)
        btn_ck_olcum_sil.setStyleSheet(
        "background:#7f0000; color:white; padding:3px 8px; border:none; font-size:9pt;"
        )
        coklu_kat_layout.addWidget(btn_ck_olcum_sil)

        # ── Ayırıcı ────────────────────────────────────────────────────
        ck_sep2 = QFrame()
        ck_sep2.setFrameShape(QFrame.Shape.HLine)
        ck_sep2.setStyleSheet("color:#555; background:#555; margin:4px 0;")
        coklu_kat_layout.addWidget(ck_sep2)

        # Özet etiketi
        self.coklu_kat_ozet_label = QLabel("Kat: 0 | Toplam ölçüm: 0")
        self.coklu_kat_ozet_label.setStyleSheet(
        "color:#ce93d8; font-weight:bold; padding:4px;"
        "background:#2a1a3a; border-radius:4px;"
        )
        self.coklu_kat_ozet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        coklu_kat_layout.addWidget(self.coklu_kat_ozet_label)

        # Alt butonlar
        ck_alt_layout = QHBoxLayout()
        btn_ck_hesapla = QPushButton(" Tüm Katları Topla")
        btn_ck_hesapla.clicked.connect(self._coklu_kat_hesapla)
        btn_ck_hesapla.setStyleSheet(
        "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #9c27b0,stop:1 #7b1fa2);"
        "color:white; font-weight:bold; padding:8px; border:2px solid #ce93d8; border-radius:3px;"
        )
        ck_alt_layout.addWidget(btn_ck_hesapla)

        btn_ck_aktar = QPushButton(" Metraja Aktar")
        btn_ck_aktar.clicked.connect(self._coklu_kat_metraja_aktar)
        btn_ck_aktar.setStyleSheet(
        "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1b5e20,stop:1 #2e7d32);"
        "color:white; font-weight:bold; padding:8px; border:2px solid #4caf50; border-radius:3px;"
        )
        ck_alt_layout.addWidget(btn_ck_aktar)
        coklu_kat_layout.addLayout(ck_alt_layout)

        _ck_scroll.setWidget(_ck_content)
        _ck_outer.addWidget(_ck_scroll)
        self.acad_tab_widget.addTab(coklu_kat_tab, " Çoklu Kat")

        # (Kaba Yapı sekmesi → Kaba İnşaat > Hızlı Keşif alt sekmesine taşındı)

        # SEKME 4: LISP ARAÇLARI
        lisp_tab = self._lisp_araclari_tab_olustur()
        self.acad_tab_widget.addTab(lisp_tab, " LISP Araçları")

        # Sekme değişikliği callback'i
        self.acad_tab_widget.currentChanged.connect(self._sekme_degisti)

        self.acad_tab_widget.setMinimumHeight(600)
        acad_main_layout.addWidget(self.acad_tab_widget)

        acad_group.setLayout(acad_main_layout)
        parent_layout.addWidget(acad_group)

        # ═══════════════════════════════════════════════════════════════════
        # DXF DOSYA YÜKLEME (Mimari)
        # ═══════════════════════════════════════════════════════════════════
        dxf_layout = QHBoxLayout()
        btn_dxf = QPushButton(" DXF DOSYASI YUKLE (Mimari)")
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

        btn_hesapla = QPushButton("HESAPLA")
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
        btn_excel = QPushButton(" EXCEL'E AKTAR")
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

        # ─────────────────────────────────────────────────────────────────
        # Özellik 3 — Metraj Cetvelı'ne Tek Tuşla Aktarım
        # ─────────────────────────────────────────────────────────────────
        btn_metraj_aktar = QPushButton(" METRAJ CETVELİNE AKTAR")
        btn_metraj_aktar.clicked.connect(self._metraj_cetvelne_aktar)
        btn_metraj_aktar.setToolTip(
        "Hesaplanan tüm imalat kalemlerini\n"
        "Ana Ekran → Metraj Cetveli'ne otomatik ekler."
        )
        btn_metraj_aktar.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #00897B, stop:1 #00695C);
        color: white;
        font-weight: bold;
        font-size: 10pt;
        padding: 8px;
        border: 2px solid #4DB6AC;
        }
        QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #26A69A, stop:1 #00897B);
        }
        """)
        parent_layout.addWidget(btn_metraj_aktar)

        # ─────────────────────────────────────────────────────────────────
        # Özellik 6 — Tedarikçi Entegrasyonu
        # ─────────────────────────────────────────────────────────────────
        btn_tedarikci = QPushButton(" TEDARİKÇİYE TEKLİF İSTE")
        btn_tedarikci.clicked.connect(self._tedarikci_gonder)
        btn_tedarikci.setToolTip(
        "Malzeme listesini tedarikçi teklif formatında\n"
        "panoya kopyalar veya metin dosyasına kaydeder."
        )
        btn_tedarikci.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1565C0, stop:1 #0D47A1);
        color: white;
        font-weight: bold;
        font-size: 10pt;
        padding: 8px;
        border: 2px solid #42A5F5;
        }
        QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1976D2, stop:1 #1565C0);
        }
        """)
        parent_layout.addWidget(btn_tedarikci)

        # ─────────────────────────────────────────────────────────────────
        # Özellik 4 — Anormallik Uyarı Paneli
        # ─────────────────────────────────────────────────────────────────
        self.uyari_group = QGroupBox(" Anormallik Uyarıları")
        self.uyari_group.setStyleSheet("""
        QGroupBox {
        color: #FFA500;
        font-weight: bold;
        font-size: 9pt;
        border: 2px solid #FFA500;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 12px;
        }
        QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
        }
        """)
        uyari_inner = QVBoxLayout()
        self.uyari_listesi_widget = QListWidget()
        self.uyari_listesi_widget.setMaximumHeight(90)
        self.uyari_listesi_widget.setStyleSheet(
        "QListWidget { background:#1a1a2e; border:none; color:#FFA500; font-size:9pt; }"
        "QListWidget::item { padding:2px 4px; }"
        )
        uyari_inner.addWidget(self.uyari_listesi_widget)
        self.uyari_group.setLayout(uyari_inner)
        self.uyari_group.setVisible(False) # Başlangıçta gizli; uyarı varsa göster
        parent_layout.addWidget(self.uyari_group)

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
        has_any_data = (self.duvarlar or self.kolonlar or self.kirisler or self.sap_eslestirme)
        if not has_any_data:
            QMessageBox.warning(self, "Uyari", "Hicbir veri bulunamadi!")
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

            # AKILLI YUKSEKLIK KARARI (for kiris dongusu SONRASINDA)
            duvar_layer_h = duvar.get('h', 0)
            if duvar_layer_h > 0 and duvar_layer_h != 300:
                net_h = duvar_layer_h
                if cakisan_kiris_yuksekligi > 0:
                    aciklama = f"Layer H:{duvar_layer_h} (Kiris: {cakisan_kiris_adi})"
                    formul = f"Layer: {duvar_layer_h}"
                    renk = '#ff6b6b'
                else:
                    aciklama = f"Layer H:{duvar_layer_h} (Doseme Alti)"
                    formul = f"Layer: {duvar_layer_h}"
                    renk = '#4dabf7'
            elif cakisan_kiris_yuksekligi > 0:
                net_h = kat_yuksekligi - cakisan_kiris_yuksekligi
                aciklama = f"Kiris Alti ({cakisan_kiris_adi})"
                formul = f"{kat_yuksekligi} - {cakisan_kiris_yuksekligi}"
                renk = '#ff6b6b'
            else:
                net_h = kat_yuksekligi - doseme_kalinligi
                aciklama = "Doseme Alti (Kirissiz)"
                formul = f"{kat_yuksekligi} - {doseme_kalinligi}"
                renk = '#4dabf7'

            # Duvar uzunlugunu hesapla (geometriden)
            if SHAPELY_AVAILABLE:
                cevre = duvar_geo.length
                alan_geo = duvar_geo.area
                uzunluk = (cevre / 2) / 100
            else:
                bounds = duvar_geo.bounds
                uzunluk = max(bounds[2] - bounds[0], bounds[3] - bounds[1]) / 100

            brut_alan = uzunluk * (net_h / 100)

            # MINHA DUSUMU
            toplam_minha_alani = 0.0
            minha_detay = []
            for minha in self.minhalar:
                if minha['geo'].intersects(duvar_geo):
                    if SHAPELY_AVAILABLE:
                        try:
                            kesisim = minha['geo'].intersection(duvar_geo)
                            if not kesisim.is_empty:
                                kesisim_bounds = kesisim.bounds
                                genislik_cm = max(kesisim_bounds[2] - kesisim_bounds[0],
                                                  kesisim_bounds[3] - kesisim_bounds[1])
                            else:
                                genislik_cm = minha.get('genislik', 100)
                        except Exception:
                            genislik_cm = minha.get('genislik', 100)
                    else:
                        genislik_cm = minha.get('genislik', 100)
                    yukseklik_cm = minha['h']
                    minha_alan_m2 = (genislik_cm * yukseklik_cm) / 10000
                    toplam_minha_alani += minha_alan_m2
                    minha_detay.append(f"{minha['layer']} ({int(genislik_cm)}x{yukseklik_cm})")

            net_alan = brut_alan - toplam_minha_alani
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
                "alan": net_alan,
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

        logger.info("Hesaplama tamamlandi")

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
            self.acad_status_label.setText(f" Bağlı: {cizim_adi}")
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
            self.btn_kolon_filizi.setEnabled(True)
            self.btn_kat_ekle.setEnabled(True)
            self.btn_bk_acad_olc.setEnabled(True)
            # İnce işler tablolarındaki AutoCAD butonlarını etkinleştir
            self._ince_isler_butonlari_etkinlestir(True)
            # Katman listesini doldur
            katmanlar = self.acad_connector.katman_listesi_al()
            self.acad_katman_combo.clear()
            self.acad_katman_combo.addItems(katmanlar)
            # Bağlan butonlarını güncelle (İnce İşler + Çoklu Kat)
            self.btn_acad_baglan.setText(" Yeniden Bağlan")
            self.btn_ck_baglan.setText(" AutoCAD Bağlı — Yeniden Bağlan")
            self.btn_ck_baglan.setStyleSheet(
                "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1b5e20,stop:1 #2e7d32);"
                "color:white; font-weight:bold; font-size:10pt; padding:8px;"
                "border:2px solid #4caf50; border-radius:4px;"
            )
            logger.info(f"AutoCAD bağlantısı kuruldu: {cizim_adi}")
            QMessageBox.information(
                self, "AutoCAD Bağlantısı",
                f"AutoCAD'e başarıyla bağlanıldı!\n\n"
                f"Çizim: {cizim_adi}\n"
                f"Katman sayısı: {len(katmanlar)}"
            )
        except ConnectionError as e:
            self.acad_status_label.setText(" Bağlantı başarısız")
            self.acad_status_label.setStyleSheet("color: #f44336; font-style: italic; padding: 3px;")
            QMessageBox.warning(self, "AutoCAD Bağlantı Hatası", str(e))
        except Exception as e:
            logger.error(f"AutoCAD bağlantı hatası: {e}")
            self.acad_status_label.setText(" Hata oluştu")
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
                ozet += f" • {tip}: {sayi} adet\n"
            if toplam_uzunluk > 0:
                ozet += f"\nToplam Uzunluk: {toplam_uzunluk:.2f} birim"
            if toplam_alan > 0:
                ozet += f"\nToplam Alan: {toplam_alan:.2f} birim²"
            ozet += "\n\n Seçilen objeler YEŞİL ile işaretlendi."
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

    def _ai_katman_oneri_guncelle(self, katman_adi: str) -> None:
        """Katman adı değiştiğinde AI önerisini DB'den çek ve paneli göster/gizle"""
        if not hasattr(self, 'ai_oneri_group'):
            return
        if not katman_adi or not self.db:
            self.ai_oneri_group.setVisible(False)
            return
        try:
            ai_veri = self.db.get_ai_learning(katman_adi)
            if ai_veri:
                yukseklik = ai_veri.get('duvar_yuksekligi', '?')
                cins = ai_veri.get('duvar_cinsi', '?') or '?'
                kalinlik = ai_veri.get('duvar_kalinligi', '?')
                kullanim = ai_veri.get('kullanim_sayisi', 1)
                self.ai_oneri_label.setText(
                    f"Yükseklik: <b>{yukseklik} m</b> | "
                    f"Cins: <b>{cins}</b> | "
                    f"Kalınlık: <b>{kalinlik} cm</b> "
                    f"<span style='color:#888; font-size:9pt;'>(Kullanım: {kullanim}×)</span>"
                )
                self.ai_oneri_label.setTextFormat(Qt.TextFormat.RichText)
                self._ai_son_veri = ai_veri
                self.ai_oneri_group.setVisible(True)
            else:
                self.ai_oneri_group.setVisible(False)
                self._ai_son_veri = None
        except Exception as e:
            logger.debug(f"AI öneri alma hatası: {e}")
            self.ai_oneri_group.setVisible(False)

    def _ai_oneri_uygula(self) -> None:
        """AI önerisindeki değerleri duvar hesaplama alanlarına ata"""
        if not hasattr(self, '_ai_son_veri') or not self._ai_son_veri:
            return
        ai_veri = self._ai_son_veri
        try:
            # Yükseklik spinbox'a ata
            yukseklik = ai_veri.get('duvar_yuksekligi')
            if yukseklik and hasattr(self, 'duvar_yukseklik_spin'):
                self.duvar_yukseklik_spin.setValue(float(yukseklik))
            # Kalınlık combo'ya ata
            kalinlik = ai_veri.get('duvar_kalinligi')
            if kalinlik and hasattr(self, 'duvar_kalinlik_combo'):
                kalinlik_str = f"{int(kalinlik)} cm"
                idx = self.duvar_kalinlik_combo.findText(kalinlik_str)
                if idx >= 0:
                    self.duvar_kalinlik_combo.setCurrentIndex(idx)
            # Duvar cinsi combo'ya ata (varsa)
            cins = ai_veri.get('duvar_cinsi')
            if cins and hasattr(self, 'duvar_cinsi_combo'):
                idx = self.duvar_cinsi_combo.findText(cins)
                if idx >= 0:
                    self.duvar_cinsi_combo.setCurrentIndex(idx)
            self.statusBar().showMessage("AI önerisi uygulandı.")
        except Exception as e:
            logger.error(f"AI öneri uygulama hatası: {e}")

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

        # ═══════════════════════════════════════════════════════════════════════════
        # İNCE İŞLER - İÇ/DIŞ CEPHE TABLO VE AUTOCAD METODLARI
        # ═══════════════════════════════════════════════════════════════════════════

    def _create_ince_isler_table(self, kalemler, prefix: str) -> QTableWidget:
        """İnce işler malzeme tablosu oluştur.

        Sütunlar: Malzeme Adı | Birim | Miktar | AutoCAD | Toplam | B.Fiyat | Tutar
        """
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(["Malzeme Adı", "Birim", "Miktar", "AutoCAD", "Toplam", "B.Fiyat (₺)", "Tutar (₺)"])
        table.setRowCount(len(kalemler))
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        table.setStyleSheet("""
        QTableWidget {
        background: #252535;
        gridline-color: #444;
        color: white;
        font-size: 10pt;
        }
        QTableWidget::item { padding: 4px; }
        QHeaderView::section {
        background: #333345;
        color: white;
        font-weight: bold;
        padding: 5px;
        border: 1px solid #555;
        }
        """)

        btn_style_alan = """
        QPushButton {
        background: #2196F3; color: white; font-weight: bold;
        padding: 4px 8px; border: 1px solid #64B5F6; border-radius: 3px; font-size: 9pt;
        }
        QPushButton:hover { background: #42A5F5; }
        QPushButton:disabled { background: #444; color: #666; }
        """
        btn_style_adet = """
        QPushButton {
        background: #FF9800; color: white; font-weight: bold;
        padding: 4px 8px; border: 1px solid #FFB74D; border-radius: 3px; font-size: 9pt;
        }
        QPushButton:hover { background: #FFA726; }
        QPushButton:disabled { background: #444; color: #666; }
        """

        for row, (ad, birim, mod) in enumerate(kalemler):
            # Malzeme adı (salt okunur)
            ad_item = QTableWidgetItem(ad)
            ad_item.setFlags(ad_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 0, ad_item)

            # Birim (salt okunur)
            birim_item = QTableWidgetItem(birim)
            birim_item.setFlags(birim_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            birim_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 1, birim_item)

            # Miktar (kullanıcı düzenleyebilir)
            miktar_item = QTableWidgetItem("0")
            miktar_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 2, miktar_item)

            # AutoCAD butonu
            if mod == "alan":
                btn = QPushButton(" Polyline Çiz")
                btn.setStyleSheet(btn_style_alan)
                btn.setToolTip("AutoCAD'de polyline çizerek alan/uzunluk hesapla")
            else:
                btn = QPushButton(" Blok Say")
                btn.setStyleSheet(btn_style_adet)
                btn.setToolTip("AutoCAD'den blok seçerek adet say")
            btn.setEnabled(False)
            btn.setProperty("row", row)
            btn.setProperty("prefix", prefix)
            btn.setProperty("mod", mod)
            btn.setProperty("birim", birim)
            btn.setProperty("malzeme", ad)
            btn.clicked.connect(lambda checked, b=btn: self._ince_isler_autocad_sec(b))
            table.setCellWidget(row, 3, btn)
            # Toplam (salt okunur)
            toplam_item = QTableWidgetItem("0")
            toplam_item.setFlags(toplam_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            toplam_item.setForeground(QColor("#4CAF50"))
            table.setItem(row, 4, toplam_item)
            # Birim Fiyat (kullanıcı düzenleyebilir) - sarı
            bf_item = QTableWidgetItem("0.00")
            bf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            bf_item.setForeground(QColor("#f39c12"))
            bf_item.setBackground(QColor("#2a1a00"))
            table.setItem(row, 5, bf_item)
            # Tutar (salt okunur) - yeşil
            tutar_item = QTableWidgetItem("0.00")
            tutar_item.setFlags(tutar_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            tutar_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tutar_item.setForeground(QColor("#27ae60"))
            table.setItem(row, 6, tutar_item)
        # Miktar değiştiğinde toplamı güncelle
        table.cellChanged.connect(lambda r, c: self._ince_isler_miktar_guncelle(table, r, c))

        table.setColumnWidth(1, 60)
        table.setColumnWidth(2, 80)
        table.setColumnWidth(3, 100)
        table.setColumnWidth(5, 90)
        table.setColumnWidth(6, 90)

        return table

    def _ince_isler_autocad_sec(self, btn):
        """İnce işler tablosundaki AutoCAD butonuna tıklandığında"""
        if not self.acad_connector or not self.acad_connector.bagli:
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return
        row = btn.property("row")
        prefix = btn.property("prefix")
        mod = btn.property("mod")
        birim = btn.property("birim")
        malzeme = btn.property("malzeme")
        table = self.ic_cephe_table if prefix == "ic" else self.dis_cephe_table
        try:
            if mod == "alan":
                # ── POLYLINE ÇİZİMİ (AutoCAD PLINE komutu) ──
                duvar_modu = self.chk_duvar_modu.isChecked()
                alan_icin_kapat = not (duvar_modu and birim == "m²") and birim != "m"
                sonuc = self.acad_connector.polyline_cizdir(
                    f"{malzeme} için polyline çizin",
                    kapat=alan_icin_kapat
                )
                if sonuc.get("iptal", True):
                    QMessageBox.information(
                        self, "Bilgi",
                        "Çizim iptal edildi veya yeterli nokta girilmedi."
                    )
                    return
                # ── Değer hesapla ──
                uzunluk_ham = sonuc["uzunluk"]
                if uzunluk_ham > 10000:  # mm → m
                    uzunluk_m = uzunluk_ham / 1000.0
                elif uzunluk_ham > 100:  # cm → m
                    uzunluk_m = uzunluk_ham / 100.0
                else:  # zaten m
                    uzunluk_m = uzunluk_ham
                if duvar_modu and birim == "m²":
                    # ── DUVAR MODU ──
                    yukseklik = self.duvar_yukseklik_spin.value()
                    kalinlik = self.duvar_kalinlik_combo.currentText()
                    deger = uzunluk_m * yukseklik
                    detay_str = (
                        f"Duvar Kalınlığı: {kalinlik}\n"
                        f"Duvar Yüksekliği: {yukseklik:.2f} m\n"
                        f"Çizilen Uzunluk: {uzunluk_m:.2f} m\n"
                        f"Duvar Alanı: {uzunluk_m:.2f} x {yukseklik:.2f} = {deger:.2f} m²"
                    )
                elif birim == "m":
                    # ── UZUNLUK MODU ──
                    deger = uzunluk_m
                    detay_str = (
                        f"Çizilen Polyline: {sonuc['nokta_sayisi']} nokta\n"
                        f"Toplam Uzunluk: {deger:.2f} m"
                    )
                else:
                    # ── ALAN MODU (kapalı polyline alanı) ──
                    alan_ham = sonuc["alan"]
                    if alan_ham > 1_000_000_000:  # mm² → m²
                        deger = alan_ham / 1_000_000
                    elif alan_ham > 10_000:  # cm² → m²
                        deger = alan_ham / 10_000
                    else:  # zaten m²
                        deger = alan_ham
                    detay_str = (
                        f"Çizilen Polyline: {sonuc['nokta_sayisi']} nokta\n"
                        f"Alan: {deger:.2f} m²"
                    )
            else:
                # ── BLOK SAYIM MODU ──
                QMessageBox.information(
                    self, f"Blok Sayımı - {malzeme}",
                    f"AutoCAD'e geçin ve {malzeme} bloklarını seçin.\n\n"
                    "Seçimi tamamlamak için ENTER,\n"
                    "İptal için ESC tuşuna basın."
                )
                sonuc = self.acad_connector.blok_sayimi_al(
                    f"{malzeme} bloklarını seçin"
                )
                if sonuc["toplam_adet"] == 0:
                    QMessageBox.information(self, "Bilgi", "Blok bulunamadı.")
                    return
                deger = sonuc["toplam_adet"]
                detay_str = f"Toplam: {deger} adet"
                if sonuc["bloklar"]:
                    for blok_ad, sayi in sonuc["bloklar"].items():
                        detay_str += f"\n {blok_ad}: {sayi} adet"
            # Mevcut değere ekle
            mevcut = table.item(row, 2)
            mevcut_val = float(mevcut.text()) if mevcut and mevcut.text() else 0.0
            yeni_val = mevcut_val + deger
            if birim == "Adet":
                table.item(row, 2).setText(str(int(yeni_val)))
                table.item(row, 4).setText(str(int(yeni_val)))
            else:
                table.item(row, 2).setText(f"{yeni_val:.2f}")
                table.item(row, 4).setText(f"{yeni_val:.2f}")
            self._ince_isler_toplam_guncelle()
            QMessageBox.information(
                self, f"{malzeme} - Sonuç",
                f"{detay_str}\n\n"
                f"Eklenen: +{deger:.2f} {birim}\n"
                f"Yeni Toplam: {yeni_val:.2f} {birim}\n\n"
                f"Çizilen polyline yeşil ile işaretlendi."
            )
        except Exception as e:
            logger.error(f"İnce işler AutoCAD seçim hatası: {e}")
            QMessageBox.critical(self, "Hata", f"AutoCAD seçimi sırasında hata:\n{e}")

    def _ince_isler_miktar_guncelle(self, table, row, col):
        """Miktar (col2) veya Birim Fiyat (col5) değiştiğinde toplamı ve tutarı güncelle"""
        if col not in (2, 5):
            return
        try:
            miktar = float(table.item(row, 2).text()) if table.item(row, 2) else 0.0
            if col == 2:
                table.item(row, 4).setText(f"{miktar:.2f}" if miktar != int(miktar) else str(int(miktar)))
            bf = float(table.item(row, 5).text()) if table.item(row, 5) else 0.0
            tutar = miktar * bf
            if table.item(row, 6):
                table.item(row, 6).setText(f"{tutar:.2f}")
        except (ValueError, AttributeError):
            pass
        self._ince_isler_toplam_guncelle()
        self._ince_isler_maliyet_guncelle()

    def _ince_isler_toplam_guncelle(self):
        """İnce işler toplam etiketini güncelle"""
        toplam_alan = 0.0
        toplam_adet = 0
        for table, kalemler in [(self.ic_cephe_table, self._ic_cephe_kalemleri),
                                 (self.dis_cephe_table, self._dis_cephe_kalemleri)]:
            for row in range(table.rowCount()):
                birim = kalemler[row][1] if row < len(kalemler) else "m²"
                try:
                    val = float(table.item(row, 4).text())
                except (ValueError, AttributeError):
                    val = 0.0
                if birim == "Adet":
                    toplam_adet += int(val)
                else:
                    toplam_alan += val
        self.ince_toplam_label.setText(
            f"Toplam: {toplam_alan:,.2f} m² / {toplam_adet} Adet"
        )
        self._ince_isler_maliyet_guncelle()

    def _ince_isler_maliyet_guncelle(self):
        """İç ve Dış cephe tablolarındaki Tutar sütununu toplayarak maliyet etiketini güncelle"""
        toplam = 0.0
        for table in [self.ic_cephe_table, self.dis_cephe_table]:
            for row in range(table.rowCount()):
                try:
                    val = float(table.item(row, 6).text()) if table.item(row, 6) else 0.0
                    toplam += val
                except (ValueError, AttributeError):
                    pass
        if hasattr(self, 'ince_maliyet_label'):
            self.ince_maliyet_label.setText(f"Tahmini Maliyet: {toplam:,.2f} ₺")

            # ─── B: Menha Düşümü metodları ───────────────────────────────────────────

    def _menha_ekle(self):
        """Menha tablosuna yeni pencere/kapı ekle"""
        tip = self.menha_tip_combo.currentText()
        gen = self.menha_gen_spin.value()
        yuk = self.menha_yuk_spin.value()
        adet = self.menha_adet_spin.value()
        alan = round(gen * yuk * adet, 4)

        row = self.menha_table.rowCount()
        self.menha_table.insertRow(row)
        for col, val in enumerate([tip, f"{gen:.2f}", f"{yuk:.2f}", str(int(adet)), f"{alan:.4f}"]):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.menha_table.setItem(row, col, item)
        self._menha_toplam_guncelle()

    def _menha_sil(self):
        """Seçili menha satırını sil"""
        rows = sorted(set(idx.row() for idx in self.menha_table.selectedIndexes()), reverse=True)
        for r in rows:
            self.menha_table.removeRow(r)
        self._menha_toplam_guncelle()

    def _menha_toplam_guncelle(self):
        """Toplam menha alanını hesapla ve etiketi güncelle"""
        toplam = 0.0
        for r in range(self.menha_table.rowCount()):
            try:
                toplam += float(self.menha_table.item(r, 4).text())
            except (ValueError, AttributeError):
                pass
        self.menha_toplam_label.setText(f"Toplam Menha: {toplam:.2f} m²")

    def _menha_uygula(self):
        """Menha alanını iç cephe tablo kalemlerine düş"""
        menha_alani = 0.0
        for r in range(self.menha_table.rowCount()):
            try:
                menha_alani += float(self.menha_table.item(r, 4).text())
            except (ValueError, AttributeError):
                pass
        if menha_alani <= 0:
            QMessageBox.warning(self, "Uyarı", "Önce menha tablosuna eleman ekleyin!")
            return
        etkilenen_satirlar = []
        for ad, row_idx in [("Duvar Boyası", 0), ("Duvar Seramiği", 3), ("İç Sıva", 5), ("Alçı Sıva", 6)]:
            try:
                item = self.ic_cephe_table.item(row_idx, 2)
                if item:
                    mevcut = float(item.text())
                    yeni = max(0.0, mevcut - menha_alani)
                    item.setText(f"{yeni:.2f}")
                    etkilenen_satirlar.append(ad)
            except (ValueError, AttributeError):
                pass
        self._ince_isler_toplam_guncelle()
        QMessageBox.information(
            self, "Menha Uygulandı",
            f"{menha_alani:.2f} m² düşüldü.\n"
            f"Etkilenen kalemler: {', '.join(etkilenen_satirlar)}"
        )

        # ─── C: Mahal Yöneticisi metodları ──────────────────────────────────────

    def _mahal_ekle(self):
        """Mahal tablosuna yeni mahal ekle"""
        ad = self.mahal_ad_input.text().strip()
        if not ad:
            QMessageBox.warning(self, "Uyarı", "Mahal adı boş olamaz!")
            return
        tip = self.mahal_tip_combo.currentText()
        alan = self.mahal_alan_spin.value()
        cevre_girilen = self.mahal_cevre_spin.value()
        if cevre_girilen <= 0:
            cevre = round(4 * math.sqrt(alan), 2)
            hes_cevre = f"{cevre:.2f} (oto)"
        else:
            cevre = cevre_girilen
            hes_cevre = "-"
        row = self.mahal_table.rowCount()
        self.mahal_table.insertRow(row)
        for col, val in enumerate([ad, tip, f"{alan:.2f}", f"{cevre:.2f}", hes_cevre]):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.mahal_table.setItem(row, col, item)
        self.mahal_ad_input.clear()
        self._mahal_ozet_guncelle()

    def _mahal_sil(self):
        """Seçili mahal satırını sil"""
        rows = sorted(set(idx.row() for idx in self.mahal_table.selectedIndexes()), reverse=True)
        for r in rows:
            self.mahal_table.removeRow(r)
        self._mahal_ozet_guncelle()

    def _mahal_ozet_guncelle(self):
        """Toplam alan ve ortalama çevre etiketini güncelle"""
        toplam_alan = 0.0
        toplam_cevre = 0.0
        count = self.mahal_table.rowCount()
        for r in range(count):
            try:
                toplam_alan += float(self.mahal_table.item(r, 2).text())
                toplam_cevre += float(self.mahal_table.item(r, 3).text())
            except (ValueError, AttributeError):
                pass
        ort_cevre = toplam_cevre / count if count > 0 else 0.0
        self.mahal_ozet_label.setText(
            f"Toplam Alan: {toplam_alan:.2f} m² | Ort. Çevre: {ort_cevre:.2f} m"
        )

    def _mahal_tablolara_aktar(self):
        """Mahal verilerini iç cephe imalat tablolarına aktar"""
        count = self.mahal_table.rowCount()
        if count == 0:
            QMessageBox.warning(self, "Uyarı", "Önce mahal ekleyin!")
            return

        kat_h_cm = self.kat_yuksekligi_spin.value()
        kat_h_m = kat_h_cm / 100.0

        toplam_alan = 0.0
        toplam_duvar_alan = 0.0
        toplam_cevre = 0.0

        for r in range(count):
            try:
                alan = float(self.mahal_table.item(r, 2).text())
                cevre = float(self.mahal_table.item(r, 3).text())
                toplam_alan += alan
                toplam_duvar_alan += cevre * kat_h_m
                toplam_cevre += cevre
            except (ValueError, AttributeError):
                pass

        # Hedef satırları: (kalem_adı, ic_cephe_table_row, değer)
        hedefler = [
            (0, toplam_duvar_alan),  # Duvar Boyası
            (1, toplam_alan),        # Tavan Boyası
            (2, toplam_alan),        # Zemin Seramiği
            (3, toplam_duvar_alan),  # Duvar Seramiği
            (4, toplam_alan),        # Parke / Laminat
            (5, toplam_duvar_alan),  # İç Sıva
            (6, toplam_duvar_alan),  # Alçı Sıva
            (7, toplam_cevre),       # Kartonpiyer
            (8, toplam_cevre),       # Süpürgelik
        ]

        for row_idx, deger in hedefler:
            item = self.ic_cephe_table.item(row_idx, 2)
            if item:
                item.setText(f"{deger:.2f}")

        self._ince_isler_toplam_guncelle()
        QMessageBox.information(
            self, "Aktarım Tamamlandı",
            f"{count} mahal aktarıldı.\n"
            f"Toplam Alan: {toplam_alan:.2f} m²\n"
            f"Toplam Duvar Alanı: {toplam_duvar_alan:.2f} m²\n"
            f"Toplam Çevre: {toplam_cevre:.2f} m"
        )

                # ─── D: Sarfiyat Ayarları metodları ─────────────────────────────────────

    def _sarfiyat_ayarlari_ac(self):
        """Sarfiyat Ayarları dialogunu aç"""
        dlg = SarfiyatAyarlariDialog(self)
        dlg.exec()

        # ─── E: Özel Kalem Ekleme metodları ─────────────────────────────────────

    def _ozel_kalem_ekle(self, prefix: str):
        """İç veya dış cephe tablosuna özel kalem ekle"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Özel Kalem Ekle")
        dlg.setMinimumWidth(300)
        dlg.setStyleSheet("background: #252535; color: white;")
        lay = QVBoxLayout(dlg)

        frm = QGridLayout()
        frm.addWidget(QLabel("Kalem Adı:"), 0, 0)
        ad_input = QLineEdit()
        ad_input.setPlaceholderText("Örn: Epoksi Zemin Kaplama")
        frm.addWidget(ad_input, 0, 1)

        frm.addWidget(QLabel("Birim:"), 1, 0)
        birim_combo = QComboBox()
        birim_combo.addItems(["m²", "m", "Adet", "adet"])
        frm.addWidget(birim_combo, 1, 1)

        frm.addWidget(QLabel("AutoCAD Modu:"), 2, 0)
        mod_combo = QComboBox()
        mod_combo.addItems(["Polyline / Alan", "Blok Say"])
        frm.addWidget(mod_combo, 2, 1)

        lay.addLayout(frm)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        ad = ad_input.text().strip()
        if not ad:
            QMessageBox.warning(self, "Uyarı", "Kalem adı boş olamaz!")
            return

        birim = birim_combo.currentText()
        mod_txt = mod_combo.currentText()
        mod = "alan" if "Polyline" in mod_txt else "adet"

        # Kalemler listesine ekle
        if prefix == "ic":
            self._ic_cephe_kalemleri.append((ad, birim, mod))
            table = self.ic_cephe_table
        else:
            self._dis_cephe_kalemleri.append((ad, birim, mod))
            table = self.dis_cephe_table

        row = table.rowCount()
        table.insertRow(row)

        # Malzeme adı
        ad_item = QTableWidgetItem(ad)
        ad_item.setFlags(ad_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row, 0, ad_item)
        # Birim
        birim_item = QTableWidgetItem(birim)
        birim_item.setFlags(birim_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        birim_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 1, birim_item)
        # Miktar
        miktar_item = QTableWidgetItem("0")
        miktar_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 2, miktar_item)
        # AutoCAD butonu
        acad_available = self.acad_connector is not None and self.acad_connector.bagli if self.acad_connector else False
        if mod == "alan":
            btn = QPushButton(" Polyline Çiz")
            btn.setStyleSheet("QPushButton { background: #2196F3; color: white; font-weight: bold; padding: 4px 8px; border: 1px solid #64B5F6; border-radius: 3px; font-size: 9pt; } QPushButton:disabled { background: #444; color: #666; }")
        else:
            btn = QPushButton(" Blok Say")
            btn.setStyleSheet("QPushButton { background: #FF9800; color: white; font-weight: bold; padding: 4px 8px; border: 1px solid #FFB74D; border-radius: 3px; font-size: 9pt; } QPushButton:disabled { background: #444; color: #666; }")
        btn.setEnabled(acad_available)
        btn.setProperty("row", row)
        btn.setProperty("prefix", prefix)
        btn.setProperty("mod", mod)
        btn.setProperty("birim", birim)
        btn.setProperty("malzeme", ad)
        btn.clicked.connect(lambda checked, b=btn: self._ince_isler_autocad_sec(b))
        table.setCellWidget(row, 3, btn)
        # Toplam
        toplam_item = QTableWidgetItem("0")
        toplam_item.setFlags(toplam_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        toplam_item.setForeground(QColor("#4CAF50"))
        table.setItem(row, 4, toplam_item)
        # Birim Fiyat
        bf_item = QTableWidgetItem("0.00")
        bf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        bf_item.setForeground(QColor("#f39c12"))
        bf_item.setBackground(QColor("#2a1a00"))
        table.setItem(row, 5, bf_item)
        # Tutar
        tutar_item = QTableWidgetItem("0.00")
        tutar_item.setFlags(tutar_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        tutar_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        tutar_item.setForeground(QColor("#27ae60"))
        table.setItem(row, 6, tutar_item)

        # ─── F: PDF / HTML Rapor metodları ──────────────────────────────────────

    def _pdf_raporu_olustur(self):
        """İnce işler PDF veya HTML raporu oluştur"""
        # Proje bilgisi dialog
        info_dlg = QDialog(self)
        info_dlg.setWindowTitle("Rapor Bilgileri")
        info_dlg.setMinimumWidth(320)
        info_dlg.setStyleSheet("background: #252535; color: white;")
        info_lay = QVBoxLayout(info_dlg)

        frm = QGridLayout()
        frm.addWidget(QLabel("Proje Adı:"), 0, 0)
        proje_input = QLineEdit("Yeni Proje")
        frm.addWidget(proje_input, 0, 1)
        frm.addWidget(QLabel("Müteahhit:"), 1, 0)
        muteahhit_input = QLineEdit()
        frm.addWidget(muteahhit_input, 1, 1)
        frm.addWidget(QLabel("Tarih:"), 2, 0)
        from datetime import date as _date
        tarih_input = QLineEdit(_date.today().strftime("%d.%m.%Y"))
        frm.addWidget(tarih_input, 2, 1)
        info_lay.addLayout(frm)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(info_dlg.accept)
        btns.rejected.connect(info_dlg.reject)
        info_lay.addWidget(btns)

        if info_dlg.exec() != QDialog.DialogCode.Accepted:
            return

        proje_adi = proje_input.text().strip() or "Proje"
        muteahhit = muteahhit_input.text().strip() or "-"
        tarih = tarih_input.text().strip()

        if REPORTLAB_AVAILABLE:
            self._pdf_raporu_reportlab(proje_adi, muteahhit, tarih)
        else:
            self._pdf_raporu_html(proje_adi, muteahhit, tarih)

    def _tablo_satirlari_al(self, table, kalemler):
        """Tablodan satır verilerini oku"""
        satirlar = []
        for row in range(table.rowCount()):
            try:
                ad = table.item(row, 0).text() if table.item(row, 0) else ""
                birim = table.item(row, 1).text() if table.item(row, 1) else ""
                miktar = table.item(row, 2).text() if table.item(row, 2) else "0"
                bf = table.item(row, 5).text() if table.item(row, 5) else "0.00"
                tutar = table.item(row, 6).text() if table.item(row, 6) else "0.00"
                if float(miktar) > 0 or float(tutar) > 0:
                    satirlar.append([ad, birim, miktar, bf, tutar])
            except (ValueError, AttributeError):
                pass
        return satirlar

    def _pdf_raporu_reportlab(self, proje_adi, muteahhit, tarih):
        """reportlab ile PDF oluştur"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors as rl_colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import cm

            dosya, _ = QFileDialog.getSaveFileName(
                self, "PDF Kaydet", f"{proje_adi}_ince_isler.pdf", "PDF (*.pdf)"
            )
            if not dosya:
                return

            doc = SimpleDocTemplate(
                dosya, pagesize=A4,
                rightMargin=1.5*cm, leftMargin=1.5*cm,
                topMargin=2*cm, bottomMargin=2*cm
            )
            styles = getSampleStyleSheet()
            elements = []

            # Başlık
            elements.append(Paragraph("<b>İNCE İŞLER METRAJ RAPORU</b>", styles['Title']))
            elements.append(Spacer(1, 0.3*cm))
            elements.append(Paragraph(f"Proje: {proje_adi} | Müteahhit: {muteahhit} | Tarih: {tarih}", styles['Normal']))
            elements.append(Spacer(1, 0.5*cm))

            col_w = [5*cm, 1.8*cm, 2.5*cm, 2.5*cm, 3.5*cm]
            header = [["Malzeme Adı", "Birim", "Miktar", "B.Fiyat (₺)", "Tutar (₺)"]]
            tbl_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor('#333345')),
                ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.HexColor('#f5f5f5'), rl_colors.white]),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ])

            # İç Cephe tablosu
            ic_satirlar = self._tablo_satirlari_al(self.ic_cephe_table, self._ic_cephe_kalemleri)
            if ic_satirlar:
                elements.append(Paragraph("<b>İÇ CEPHE</b>", styles['Heading2']))
                data = header + ic_satirlar
                t = Table(data, colWidths=col_w)
                t.setStyle(tbl_style)
                elements.append(t)
                elements.append(Spacer(1, 0.5*cm))

            # Dış Cephe tablosu
            dis_satirlar = self._tablo_satirlari_al(self.dis_cephe_table, self._dis_cephe_kalemleri)
            if dis_satirlar:
                elements.append(Paragraph("<b>DIŞ CEPHE</b>", styles['Heading2']))
                data = header + dis_satirlar
                t = Table(data, colWidths=col_w)
                t.setStyle(tbl_style)
                elements.append(t)
                elements.append(Spacer(1, 0.5*cm))

            # Mahal özeti
            if hasattr(self, 'mahal_table') and self.mahal_table.rowCount() > 0:
                elements.append(Paragraph("<b>MAHAL ÖZETİ</b>", styles['Heading2']))
                mh_data = [["Mahal Adı", "Tip", "Alan (m²)", "Çevre (m)"]]
                for r in range(self.mahal_table.rowCount()):
                    row_data = []
                    for c in range(4):
                        row_data.append(self.mahal_table.item(r, c).text() if self.mahal_table.item(r, c) else "")
                    mh_data.append(row_data)
                mh_t = Table(mh_data, colWidths=[6*cm, 3*cm, 2.5*cm, 2.5*cm])
                mh_t.setStyle(tbl_style)
                elements.append(mh_t)
                elements.append(Spacer(1, 0.5*cm))

            # Toplam maliyet
            maliyet_txt = self.ince_maliyet_label.text() if hasattr(self, 'ince_maliyet_label') else ""
            elements.append(Paragraph(f"<b>{maliyet_txt}</b>", styles['Heading2']))
            elements.append(Spacer(1, 1*cm))
            elements.append(Paragraph(f"Tarih: {tarih} | İmza: ___________________", styles['Normal']))

            doc.build(elements)
            QMessageBox.information(self, "PDF Oluşturuldu", f"Rapor kaydedildi:\n{dosya}")

        except Exception as e:
            logger.error(f"PDF oluşturma hatası: {e}")
            QMessageBox.critical(self, "Hata", f"PDF oluşturulamadı:\n{e}")

    def _pdf_raporu_html(self, proje_adi, muteahhit, tarih):
        """HTML olarak rapor oluştur (reportlab yoksa fallback)"""
        try:
            def satirlari_html(table, kalemler):
                html = ""
                for row in range(table.rowCount()):
                    try:
                        ad = table.item(row, 0).text() if table.item(row, 0) else ""
                        birim = table.item(row, 1).text() if table.item(row, 1) else ""
                        miktar = table.item(row, 2).text() if table.item(row, 2) else "0"
                        bf = table.item(row, 5).text() if table.item(row, 5) else "0.00"
                        tutar = table.item(row, 6).text() if table.item(row, 6) else "0.00"
                        if float(miktar) > 0 or float(tutar) > 0:
                            html += f"<tr><td>{ad}</td><td>{birim}</td><td>{miktar}</td><td>{bf}</td><td>{tutar}</td></tr>\n"
                    except (ValueError, AttributeError):
                        pass
                return html

            ic_html = satirlari_html(self.ic_cephe_table, self._ic_cephe_kalemleri)
            dis_html = satirlari_html(self.dis_cephe_table, self._dis_cephe_kalemleri)
            maliyet_txt = self.ince_maliyet_label.text() if hasattr(self, 'ince_maliyet_label') else ""

            html_content = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>İnce İşler Metraj Raporu</title>
<style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    h1 {{ color: #333345; }}
    h2 {{ color: #444460; border-bottom: 1px solid #ccc; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
    th {{ background: #333345; color: white; padding: 8px; text-align: left; }}
    td {{ padding: 6px 8px; border: 1px solid #ccc; }}
    tr:nth-child(even) {{ background: #f5f5f5; }}
    .maliyet {{ font-size: 14pt; font-weight: bold; color: #27ae60; background: #f0fff4; padding: 10px; border-radius: 4px; }}
    .footer {{ margin-top: 40px; color: #666; }}
</style>
</head>
<body>
<h1>İNCE İŞLER METRAJ RAPORU</h1>
<p><b>Proje:</b> {proje_adi} &nbsp;|&nbsp; <b>Müteahhit:</b> {muteahhit} &nbsp;|&nbsp; <b>Tarih:</b> {tarih}</p>

<h2>İÇ CEPHE</h2>
<table>
<tr><th>Malzeme Adı</th><th>Birim</th><th>Miktar</th><th>B.Fiyat (₺)</th><th>Tutar (₺)</th></tr>
{ic_html}
</table>

<h2>DIŞ CEPHE</h2>
<table>
<tr><th>Malzeme Adı</th><th>Birim</th><th>Miktar</th><th>B.Fiyat (₺)</th><th>Tutar (₺)</th></tr>
{dis_html}
</table>

<div class="maliyet">{maliyet_txt}</div>

<div class="footer">
    <p>Tarih: {tarih} &nbsp;&nbsp; İmza: ___________________</p>
    <p><i>Bu rapor İnşaat Metraj Pro tarafından oluşturulmuştur. Tarayıcıdan Ctrl+P ile PDF olarak yazdırabilirsiniz.</i></p>
</div>
</body>
</html>"""

            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False,
                                             encoding='utf-8') as f:
                f.write(html_content)
                tmp_path = f.name

            webbrowser.open(f"file:///{tmp_path.replace(chr(92), '/')}")
            QMessageBox.information(
                self, "Rapor Açıldı",
                "Rapor tarayıcıda açıldı.\nCtrl+P ile PDF olarak yazdırabilirsiniz."
            )

        except Exception as e:
            logger.error(f"HTML rapor hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Rapor oluşturulamadı:\n{e}")

    def _ince_isler_butonlari_etkinlestir(self, enabled: bool):
        """İnce işler tablolarındaki AutoCAD butonlarını etkinleştir/devre dışı bırak"""
        for table in [self.ic_cephe_table, self.dis_cephe_table]:
            for row in range(table.rowCount()):
                btn = table.cellWidget(row, 3)
                if btn:
                    btn.setEnabled(enabled)

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
                " (Örn: Bodrum Kat, Zemin Kat, 1. Kat)\n"
                "2. '+ Ekle' butonuna tıklayın\n"
                "3. Sonra demir metrajı alabilirsiniz"
            )
            return

        try:
            # Kullanıcıya bilgi ver
            QMessageBox.information(
                self, f"Demir Metrajı - {self.aktif_kat_adi}",
                f" Aktif Kat: {self.aktif_kat_adi}\n\n"
                "AutoCAD penceresine geçin ve DEMİR YAZILARINI seçin.\n\n"
                "Örnek formatlar:\n"
                " • 10Ø12 L=250\n"
                " • 5ø16 l=180\n"
                " • 8Ø10 L=320 cm\n\n"
                "Tek tek tıklayın veya kutu çizin.\n"
                "Seçimi tamamlamak için ENTER tuşuna basın.\n"
                "İptal için ESC tuşuna basın.\n\n"
                " Geçerli demirler YEŞİL\n"
                " Format dışı metinler KIRMIZI olacak"
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
            ozet = "DEMİR METRAJ RAPORU\n"
            ozet += f"{'='*40}\n\n"
            ozet += f"Seçilen obje : {rapor['secim_sayisi']}\n"
            ozet += f"Metin objesi : {rapor['metin_sayisi']}\n"
            ozet += f" Geçerli demir : {len(rapor['basarili'])}\n"
            ozet += f" Format dışı : {len(rapor['basarisiz'])}\n\n"
            ozet += f"{'─'*40}\n"
            ozet += f"TOPLAM DEMİR : {rapor['toplam_adet']:,} adet\n"
            ozet += f"TOPLAM BOY : {rapor['toplam_boy_m']:,.2f} m\n"
            ozet += f"TOPLAM AĞIRLIK : {rapor['toplam_agirlik_kg']:,.2f} kg\n"
            ozet += f" : {rapor['toplam_agirlik_kg']/1000:,.3f} ton\n"
            ozet += f"{'─'*40}\n"
            # Çubuk adedi (1 çubuk = 12m) - yukarı yuvarla
            toplam_cubuk = rapor.get('toplam_cubuk', math.ceil(rapor['toplam_boy_m'] / 12.0))
            ozet += f" ÇUBUK (12m) : {int(toplam_cubuk):,} çubuk\n\n"

            # Çap bazlı özet
            ozet += "ÇAP BAZLI DAĞILIM:\n"
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
            QMessageBox.information(
                self, f"Kolon/Perde Hesaplama - {self.aktif_kat_adi}",
                f" Aktif Kat: {self.aktif_kat_adi}\n\n"
                "AutoCAD'de metinleri seçin:\n\n"
                " GRUP MOD (Benzer elemanlar):\n"
                " \u2022 BAŞLIK: 'SB17 (65/65) KOLON DETAYI'\n"
                " \u2022 LİSTE: 'SB24,SB31,SB39' (virgüllü)\n"
                " \u2022 DONATI: '28Ø14 L=442'\n\n"
                " TEKİL MOD (Tek perde/kolon):\n"
                " \u2022 BAŞLIK: 'PB055' veya 'SB17'\n"
                " \u2022 DONATI: '2x8Ø12 L=420' (çarpanlı da olur)\n\n"
                "Seçim sırası önemli DEĞİL!\n"
                "ENTER ile bitir, ESC ile iptal."
            )

            reply = QMessageBox.question(
                self, "AutoCAD'e Geçin",
                " ŞİMDİ AUTOCAD PENCERESİNE GEÇİN!\n\n"
                "1. Bu mesajı okuduktan sonra 'Yes' tıklayın\n"
                "2. Hemen AutoCAD penceresine tıklayın\n"
                "3. Metinleri seçip ENTER'a basın\n\n"
                "AutoCAD'e geçmeye hazır mısınız?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )

            if reply == QMessageBox.StandardButton.No:
                return

            birim = self.demir_birim_combo.currentText()
            sonuc = self.acad_connector.calculate_vertical_rebar_unified(birim=birim)

            if sonuc["hata"]:
                QMessageBox.warning(
                    self, "Hesaplama Hatası",
                    f"Hesaplama yapılamadı:\n\n{sonuc['hata']}"
                )
                return

            if not sonuc["basarili"]:
                QMessageBox.warning(self, "Uyarı", "Hesaplama başarısız oldu.")
                return

            ozet = sonuc["ozet"]
            gruplar = sonuc.get("gruplar", [])
            mod = sonuc["mod"]

            mesaj = f"DEMİR METRAJ RAPORU ({mod} MOD)\n"
            mesaj += f"{'='*50}\n\n"
            mesaj += f" Kat: {self.aktif_kat_adi}\n\n"
            mesaj += f" SEÇİLEN ELEMANLAR ({len(gruplar)} grup):\n"
            mesaj += f"{chr(9472)*50}\n"

            for idx, grup in enumerate(gruplar, 1):
                lider = grup["lider"]
                tip_g = grup["tip"]
                benzerler = grup["benzerler"]
                donati_sayisi = len(grup["donatilar"])
                if benzerler:
                    mesaj += f"{idx}. {lider} ({tip_g}) + {len(benzerler)} benzer\n"
                    mesaj += f" Benzerler: {', '.join(benzerler[:5])}{'...' if len(benzerler)>5 else ''}\n"
                else:
                    mesaj += f"{idx}. {lider} ({tip_g}) - TEKİL\n"
                mesaj += f" Donatı: {donati_sayisi} satır\n\n"

            mesaj += f"{chr(9472)*50}\n\n"
            mesaj += f"TOPLAM DEMİR : {ozet['toplam_adet']:,} adet\n"
            mesaj += f"TOPLAM BOY : {ozet['toplam_boy_m']:,.2f} m\n"
            mesaj += f"TOPLAM AĞIRLIK : {ozet['toplam_agirlik_kg']:,.2f} kg\n"
            mesaj += f" : {ozet['toplam_agirlik_ton']:,.3f} ton\n"
            mesaj += f"{chr(9472)*50}\n"
            mesaj += "\n ÇUBUK ADETLERİ (12m):\n"
            for cap in sorted(ozet["cap_ozeti"].keys()):
                cap_bilgi = ozet["cap_ozeti"][cap]
                mesaj += f" Ø{cap}: {cap_bilgi['cubuk_adet']:,} çubuk\n"
            mesaj += f"\n TOPLAM: {ozet['cubuk_adet']:,} çubuk\n"

            QMessageBox.information(self, f"Hesaplama - {self.aktif_kat_adi}", mesaj)

            demirler = sonuc["demirler"]
            for demir in demirler:
                for kat_data in self.demir_kat_verileri:
                    if kat_data["kat_adi"] == self.aktif_kat_adi:
                        kat_data["demirler"].append(demir)
                        break

            self._demir_kat_listesini_guncelle()
            self.btn_demir_excel.setEnabled(True)

            elemanlar = sonuc.get("elemanlar", [])
            tip = sonuc.get("tip", "")
            logger.info(
                f"'{self.aktif_kat_adi}' katına {len(demirler)} demir eklendi "
                f"({mod} mod, {len(elemanlar)} {tip.lower()})"
            )

        except Exception as e:
            logger.error(f"Düşey eleman hesaplama hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Hesaplama sırasında hata:\n{e}")

    def _autocad_kolon_filizi_oku(self):
        """AutoCAD'den kolon filizi tablosunu oku."""
        try:
            if not self.acad_connector or not self.acad_connector.bagli:
                QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
                return

            if not self.aktif_kat_adi:
                QMessageBox.warning(self, "Uyarı", "Önce bir kat ekleyin ve seçin!")
                return

            QMessageBox.information(
                self, "Kolon Filizi Tablo Okuma",
                "AutoCAD'deki kolon filizi tablosunu okuyacaksınız.\n\n"
                "1. Tüm tabloyu kutu çizerek seçin\n"
                " (KOLON, DONATI, BOY başlıkları dahil)\n"
                "2. Seçimi tamamlamak için ENTER'a basın\n\n"
                "Program tabloyu otomatik tanıyacaktır."
            )

            birim = self.demir_birim_combo.currentText()
            rapor = self.acad_connector.get_kolon_filizi_from_table(
                birim=birim,
                mesaj="Kolon filizi tablosunu kutu çizerek seçin"
            )

            if rapor["secim_sayisi"] == 0:
                QMessageBox.information(self, "Bilgi", "Hiç obje seçilmedi.")
                return

            if not rapor["basarili"]:
                basarisiz_count = len(rapor["basarisiz"])
                QMessageBox.warning(
                    self, "Uyarı",
                    f"Geçerli demir verisi bulunamadı!\n"
                    f"Toplam seçim: {rapor['secim_sayisi']}\n"
                    f"Metin objesi: {rapor['metin_sayisi']}\n"
                    f"Format dışı: {basarisiz_count}"
                )
                return

            mesaj = f"KOLON FİLİZİ RAPORU\n{'='*40}\n\n"
            mesaj += f"Kat: {self.aktif_kat_adi}\n\n"
            mesaj += f"Geçerli demir : {len(rapor['basarili'])} satır\n"
            mesaj += f"Toplam Adet : {rapor['toplam_adet']:,}\n"
            mesaj += f"Toplam Boy : {rapor['toplam_boy_m']:,.2f} m\n"
            mesaj += f"Toplam Ağırlık : {rapor['toplam_agirlik_kg']:,.2f} kg\n"
            mesaj += f" : {rapor['toplam_agirlik_kg']/1000:,.3f} ton\n"
            mesaj += f"{chr(9472)*40}\n\n"
            mesaj += "ÇAP BAZLI DAĞILIM:\n"
            for cap in sorted(rapor["cap_ozeti"].keys()):
                ozet = rapor["cap_ozeti"][cap]
                mesaj += f" Ø{cap}: {ozet['adet']:,} adet, {ozet['boy_m']:,.2f}m, {ozet['agirlik_kg']:,.2f}kg\n"

            if rapor.get("toplam_cubuk"):
                mesaj += f"\nÇubuk Adedi (12m): {rapor['toplam_cubuk']:,}\n"

            QMessageBox.information(self, f"Kolon Filizi - {self.aktif_kat_adi}", mesaj)

            for kat_data in self.demir_kat_verileri:
                if kat_data["kat_adi"] == self.aktif_kat_adi:
                    kat_data["demirler"].extend(rapor["basarili"])
                    break

            self._demir_kat_listesini_guncelle()
            self.btn_demir_excel.setEnabled(True)
            logger.info(f"'{self.aktif_kat_adi}' katına {len(rapor['basarili'])} kolon filizi demiri eklendi")

        except Exception as e:
            logger.error(f"Kolon filizi okuma hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Kolon filizi okuma sırasında hata:\n{e}")

    def _sekme_degisti(self, index: int):
        """Sekme değiştiğinde görünürlük ayarla.

        idx 0 = İnce İşler
        idx 1 = Kaba İnşaat (Demir Metrajı + Beton & Kalıp + Hızlı Keşif)
        idx 2 = Çoklu Kat
        """
        ince_isler_aktif = (index == 0)

        # Genel Ayarlar: yalnızca İnce İşler sekmesinde görünsün
        self.settings_group.setVisible(ince_isler_aktif)


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
        self.demir_kat_listesi.addItem(f" {kat_adi} (0 demir)")

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
        reply = QMessageBox.question(
            self, "Kat Silme Onayı",
            f"'{kat_adi}' katını ve tüm demir verilerini silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.demir_kat_listesi.takeItem(current_row)
            del self.demir_kat_verileri[current_row]
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
            f" {kat_data['kat_adi']} ({demir_sayisi} demir, {toplam_agirlik:.1f} kg)"
            )

    def _demir_excel_export(self):
        """Demir metraj verilerini Excel'e aktar"""
        if not self.demir_kat_verileri:
            QMessageBox.warning(self, "Uyarı", "Henüz demir metrajı alınmış kat yok!")
            return
        veri_olan_katlar = [k for k in self.demir_kat_verileri if k["demirler"]]
        if not veri_olan_katlar:
            QMessageBox.warning(self, "Uyarı", "Hiçbir katta demir verisi yok!")
            return
        if not PANDAS_AVAILABLE:
            QMessageBox.warning(self, "Uyarı", "Excel export için pandas gerekli!")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Demir Metrajı Kaydet", "Demir_Metraji.xlsx", "Excel Dosyası (*.xlsx)"
        )
        if not file_path:
            return
        try:
            CUBUK_BOYU = 12.0
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                g_adet = 0; g_boy = 0.0; g_agir = 0.0
                for kd in self.demir_kat_verileri:
                    if not kd["demirler"]: continue
                    sayfa = kd["kat_adi"][:31]
                    rows = [{"Poz/Metin": d.orijinal_metin, "Adet": d.adet,
                             "Cap (mm)": d.cap, "Boy (cm)": d.boy,
                             "Toplam Boy (m)": d.toplam_boy,
                             "Birim Agirlik (kg/m)": d.agirlik_birim,
                             "Toplam Agirlik (kg)": round(d.toplam_agirlik, 3),
                             "Cubuk Adedi (12m)": math.ceil(d.toplam_boy / CUBUK_BOYU)}
                            for d in kd["demirler"]]
                    t_a = sum(d.adet for d in kd["demirler"])
                    t_b = sum(d.toplam_boy for d in kd["demirler"])
                    t_g = sum(d.toplam_agirlik for d in kd["demirler"])
                    rows.append({"Poz/Metin": "TOPLAM", "Adet": t_a,
                                 "Toplam Boy (m)": round(t_b, 2),
                                 "Toplam Agirlik (kg)": round(t_g, 2)})
                    pd.DataFrame(rows).to_excel(writer, sheet_name=sayfa, index=False)
                    g_adet += t_a; g_boy += t_b; g_agir += t_g
            QMessageBox.information(self, "Basarili",
                f"Excel'e aktarildi!\n\nDosya: {file_path}\n{len(veri_olan_katlar)} kat")
            logger.info(f"Demir metraji Excel: {file_path}")
        except Exception as e:
            logger.error(f"Excel export hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Hata:\n{e}")

    def _autocad_sonuclari_tabloya_ekle(self, objeler: list):
        """AutoCAD'den alinan objeleri sonuc tablosuna ekle"""
        for obj in objeler:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            tip = obj.entity_type.replace("AcDb", "")
            self.results_table.setItem(row, 0, QTableWidgetItem(f"[CAD] {tip}"))
            self.results_table.setItem(row, 1, QTableWidgetItem(obj.layer))
            detay = ""
            if obj.blok_adi:
                detay = f"Blok: {obj.blok_adi}"
            elif obj.text_icerigi:
                detay = f"Metin: {obj.text_icerigi[:30]}"
            elif obj.uzunluk > 0:
                detay = f"Uzunluk: {obj.uzunluk:.2f}"
            self.results_table.setItem(row, 2, QTableWidgetItem(detay))
            if obj.alan > 0:
                self.results_table.setItem(row, 3, QTableWidgetItem(f"{obj.alan:.2f}"))
            elif obj.uzunluk > 0:
                self.results_table.setItem(row, 3, QTableWidgetItem(f"{obj.uzunluk:.2f}"))
            else:
                self.results_table.setItem(row, 3, QTableWidgetItem("-"))
            self.results_table.setItem(row, 4, QTableWidgetItem(obj.handle))
            for col in range(5):
                item = self.results_table.item(row, col)
                if item:
                    item.setBackground(QColor(46, 125, 50, 80))

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
        """DXF dosyasi yukle"""
        if not EZDXF_AVAILABLE:
            QMessageBox.critical(self, "Hata", "ezdxf yuklu degil!\n\npip install ezdxf")
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "DXF Dosyasi Sec", "", "DXF Dosyalari (*.dxf);;Tum Dosyalar (*)"
        )
        if not file_path:
            return
        try:
            doc = ezdxf.readfile(file_path)
            msp = doc.modelspace()
            katmanlar = [layer.dxf.name for layer in doc.layers]
            kiris_p = ['kiris','kiri','beam','s_kiris','k-','kr[-_]','krs','s[-_]kr']
            duvar_p = ['duvar','wall','m_duvar','a-wall','d-','dv[-_]','partition']
            kolon_p = ['kolon','column','s_kolon','col','c-','sutun','s[-_]col','p[-_]col']
            minha_p = ['minha','pencere','kapi','window','door','m_minha','aciklik','opening']
            k_list=[]; d_list=[]; ko_list=[]; m_list=[]
            for katman in katmanlar:
                kl = katman.lower(); matched = False
                for p in kolon_p:
                    if re.search(p, kl): ko_list.append(katman); matched=True; break
                if matched: continue
                for p in kiris_p:
                    if re.search(p, kl): k_list.append(katman); matched=True; break
                if matched: continue
                for p in duvar_p:
                    if re.search(p, kl): d_list.append(katman); matched=True; break
                if matched: continue
                for p in minha_p:
                    if re.search(p, kl): m_list.append(katman); break
            self._kolon_katmanlari_temp = ko_list
            oda_p=['oda','room','mekan']; kat_p=['kat','floor','storey']; m2_p=['m2','alan','area']
            txt_set=set()
            for ent in msp.query('TEXT MTEXT'):
                try: txt_set.add(ent.dxf.layer)
                except: pass
            txt_list = sorted(txt_set)
            oda_v=[k for k in txt_list if any(p in k.lower() for p in oda_p)]
            kat_v=[k for k in txt_list if any(p in k.lower() for p in kat_p)]
            m2_v=[k for k in txt_list if any(p in k.lower() for p in m2_p)]
            dialog = DXFKatmanSecimDialog(
                self, katmanlar, k_list, d_list, m_list,
                txt_list, oda_v, kat_v, m2_v, varsayilan_kolon=ko_list,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                sk=dialog.get_selected_kiris(); sd=dialog.get_selected_duvar()
                sm=dialog.get_selected_minha(); sko=dialog.get_selected_kolon()
                so=dialog.get_selected_oda(); skat=dialog.get_selected_kat()
                sm2=dialog.get_selected_m2(); cb=dialog.get_cizim_birimi()
                uhs=dialog.get_use_hesap_siniri()
                self.duvar_cinsi=dialog.get_duvar_cinsi()
                hk=None
                if uhs:
                    hk=self._get_hesap_siniri(msp, cb)
                self._clear_all()
                self._parse_dxf_kirisler(msp, sk, cb, hk)
                self._parse_dxf_duvarlar(msp, sd, cb, hk)
                self._parse_dxf_kolonlar(msp, sko, cb, hk)
                self._parse_dxf_minhalar(msp, doc, sm, cb, hk)
                self._parse_dxf_oda_isimleri(msp, so, cb, hk)
                self._parse_dxf_kat_isimleri(msp, skat, cb, hk)
                self._parse_dxf_m2_yazilari(msp, sm2, cb, hk)
                self._parse_dxf_tefrisler(msp, cb, hk)
                if self.m2_yazilari and self.oda_isimleri:
                    self._eslesitir_m2_oda()
                self._hesapla_imalat_listesi()
                self._3d_onizle_guncelle()
                dosya_adi = Path(file_path).name
                self.dxf_status_label.setText(
                    f" {dosya_adi} | {len(self.kirisler)} kiris, {len(self.duvarlar)} duvar"
                )
                self.dxf_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                if self.duvarlar or self.kolonlar or self.kirisler:
                    self._calculate_and_visualize()
        except Exception as e:
            logger.error(f"DXF yukleme hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"DXF yuklenemedi:\n{str(e)}")

    def _get_hesap_siniri(self, msp, birim: str = "cm"):
        """HESAP_SINIRI katmanindan sinir kutusunu al"""
        try:
            sinir_entities = list(msp.query('LWPOLYLINE[layer=="HESAP_SINIRI"]'))
            if not sinir_entities:
                return None
            entity = sinir_entities[0]
            with entity.points("xy") as pts:
                noktalar = list(pts)
            if len(noktalar) < 3:
                return None
            xs = [p[0] for p in noktalar]
            ys = [p[1] for p in noktalar]
            min_x, min_y = min(xs), min(ys)
            max_x, max_y = max(xs), max(ys)
            if birim == "m":
                min_x, min_y = min_x * 100, min_y * 100
                max_x, max_y = max_x * 100, max_y * 100
            elif birim == "mm":
                min_x, min_y = min_x / 10, min_y / 10
                max_x, max_y = max_x / 10, max_y / 10
            return create_box(min_x, min_y, max_x, max_y)
        except Exception as e:
            logger.warning(f"HESAP_SINIRI okuma hatasi: {e}")
            return None

    def _is_inside_boundary(self, geo, hesap_kutusu) -> bool:
        """Geometri sinir kutusunun icinde mi?"""
        if hesap_kutusu is None:
            return True
        try:
            return hesap_kutusu.contains(geo)
        except:
            return True

    def _parse_dxf_kirisler(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den kiris verilerini parse et"""
        kiris_sayaci = 1
        for katman_adi in katman_listesi:
            h = self._extract_kiris_height(katman_adi)
            for entity in msp.query(f'LWPOLYLINE[layer=="{katman_adi}"]'):
                try:
                    with entity.points("xy") as pts:
                        noktalar = list(pts)
                    if len(noktalar) < 2:
                        continue
                    xs = [p[0] for p in noktalar]
                    ys = [p[1] for p in noktalar]
                    x1, y1 = min(xs), min(ys)
                    x2, y2 = max(xs), max(ys)
                    if birim == "m":
                        x1, y1, x2, y2 = x1*100, y1*100, x2*100, y2*100
                    elif birim == "mm":
                        x1, y1, x2, y2 = x1/10, y1/10, x2/10, y2/10
                    if SHAPELY_AVAILABLE:
                        if birim == "m":
                            geo = ShapelyPolygon([(p[0]*100, p[1]*100) for p in noktalar])
                        elif birim == "mm":
                            geo = ShapelyPolygon([(p[0]/10, p[1]/10) for p in noktalar])
                        else:
                            geo = ShapelyPolygon([(p[0], p[1]) for p in noktalar])
                    else:
                        geo = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
                    if not self._is_inside_boundary(geo, hesap_kutusu):
                        continue
                    kiris = {"id": f"K{kiris_sayaci:03d}", "layer": katman_adi,
                             "h": h, "geo": geo,
                             "coords": f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})"}
                    self.kirisler.append(kiris)
                    row = self.kiris_table.rowCount()
                    self.kiris_table.insertRow(row)
                    self.kiris_table.setItem(row, 0, QTableWidgetItem(kiris["id"]))
                    self.kiris_table.setItem(row, 1, QTableWidgetItem(f"{h} cm"))
                    self.kiris_table.setItem(row, 2, QTableWidgetItem(kiris["coords"]))
                    kiris_sayaci += 1
                except Exception as e:
                    logger.warning(f"Kiris LWPOLYLINE okuma hatasi: {e}")
            for entity in msp.query(f'LINE[layer=="{katman_adi}"]'):
                try:
                    start = entity.dxf.start
                    end = entity.dxf.end
                    x1, y1 = start.x, start.y
                    x2, y2 = end.x, end.y
                    if birim == "m":
                        x1, y1, x2, y2 = x1*100, y1*100, x2*100, y2*100
                    elif birim == "mm":
                        x1, y1, x2, y2 = x1/10, y1/10, x2/10, y2/10
                    w = 30
                    geo = Polygon([(x1, y1-w/2), (x2, y1-w/2), (x2, y2+w/2), (x1, y2+w/2)])
                    if not self._is_inside_boundary(geo, hesap_kutusu):
                        continue
                    kiris = {"id": f"K{kiris_sayaci:03d}", "layer": katman_adi,
                             "h": h, "geo": geo,
                             "coords": f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})"}
                    self.kirisler.append(kiris)
                    row = self.kiris_table.rowCount()
                    self.kiris_table.insertRow(row)
                    self.kiris_table.setItem(row, 0, QTableWidgetItem(kiris["id"]))
                    self.kiris_table.setItem(row, 1, QTableWidgetItem(f"{h} cm"))
                    self.kiris_table.setItem(row, 2, QTableWidgetItem(kiris["coords"]))
                    kiris_sayaci += 1
                except Exception as e:
                    logger.warning(f"Kiris LINE okuma hatasi: {e}")
        logger.info(f"Toplam {len(self.kirisler)} kiris yuklendi")

    def _parse_dxf_duvarlar(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den duvar verilerini parse et"""
        duvar_sayaci = 1
        for katman_adi in katman_listesi:
            kalinlik = self._extract_duvar_kalinlik(katman_adi)
            for entity in msp.query(f'LWPOLYLINE[layer=="{katman_adi}"]'):
                try:
                    if entity.closed is False and len(entity) < 3:
                        continue
                    with entity.points("xy") as pts:
                        noktalar = list(pts)
                    if len(noktalar) < 3:
                        continue
                    xs = [p[0] for p in noktalar]
                    ys = [p[1] for p in noktalar]
                    x1, y1 = min(xs), min(ys)
                    x2, y2 = max(xs), max(ys)
                    if birim == "m":
                        x1, y1, x2, y2 = x1*100, y1*100, x2*100, y2*100
                    elif birim == "mm":
                        x1, y1, x2, y2 = x1/10, y1/10, x2/10, y2/10
                    if SHAPELY_AVAILABLE:
                        if birim == "m":
                            geo = ShapelyPolygon([(p[0]*100, p[1]*100) for p in noktalar])
                        elif birim == "mm":
                            geo = ShapelyPolygon([(p[0]/10, p[1]/10) for p in noktalar])
                        else:
                            geo = ShapelyPolygon([(p[0], p[1]) for p in noktalar])
                    else:
                        geo = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
                    if not self._is_inside_boundary(geo, hesap_kutusu):
                        continue
                    w = x2 - x1
                    h_wall = y2 - y1
                    if kalinlik <= 0:
                        kalinlik = int(min(w, h_wall)) if min(w, h_wall) > 10 else 20
                    if kalinlik > 50:
                        yukseklik = self.kat_yuksekligi_spin.value()
                    else:
                        yukseklik = self.kat_yuksekligi_spin.value()
                    duvar = {"id": f"D{duvar_sayaci:03d}", "layer": katman_adi,
                             "kalinlik": f"{kalinlik} cm", "yukseklik": yukseklik,
                             "geo": geo,
                             "coords": f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})"}
                    self.duvarlar.append(duvar)
                    row = self.duvar_table.rowCount()
                    self.duvar_table.insertRow(row)
                    self.duvar_table.setItem(row, 0, QTableWidgetItem(duvar["id"]))
                    self.duvar_table.setItem(row, 1, QTableWidgetItem(duvar["kalinlik"]))
                    self.duvar_table.setItem(row, 2, QTableWidgetItem(duvar["coords"]))
                    duvar_sayaci += 1
                except Exception as e:
                    logger.warning(f"Duvar okuma hatasi: {e}")
        logger.info(f"Toplam {len(self.duvarlar)} duvar yuklendi")

    def _parse_dxf_kolonlar(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den kolon verilerini parse et"""
        kolon_sayaci = 1
        for katman_adi in katman_listesi:
            for entity in msp.query(f'LWPOLYLINE[layer=="{katman_adi}"]'):
                try:
                    with entity.points("xy") as pts:
                        noktalar = list(pts)
                    if len(noktalar) < 3:
                        continue
                    xs = [p[0] for p in noktalar]
                    ys = [p[1] for p in noktalar]
                    x1, y1 = min(xs), min(ys)
                    x2, y2 = max(xs), max(ys)
                    if birim == "m":
                        x1, y1, x2, y2 = x1*100, y1*100, x2*100, y2*100
                    elif birim == "mm":
                        x1, y1, x2, y2 = x1/10, y1/10, x2/10, y2/10
                    if SHAPELY_AVAILABLE:
                        if birim == "m":
                            geo = ShapelyPolygon([(p[0]*100, p[1]*100) for p in noktalar])
                        elif birim == "mm":
                            geo = ShapelyPolygon([(p[0]/10, p[1]/10) for p in noktalar])
                        else:
                            geo = ShapelyPolygon([(p[0], p[1]) for p in noktalar])
                    else:
                        geo = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
                    if not self._is_inside_boundary(geo, hesap_kutusu):
                        continue
                    b = round(x2 - x1)
                    h = round(y2 - y1)
                    kolon = {"id": f"C{kolon_sayaci:03d}", "layer": katman_adi,
                             "b": b, "h": h, "geo": geo,
                             "coords": f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})"}
                    self.kolonlar.append(kolon)
                    kolon_sayaci += 1
                except Exception as e:
                    logger.warning(f"Kolon okuma hatasi: {e}")
        logger.info(f"Toplam {len(self.kolonlar)} kolon yuklendi")

    def _parse_dxf_minhalar(self, msp, doc, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den minha (kapi/pencere) verilerini parse et"""
        minha_sayaci = 1
        for katman_adi in katman_listesi:
            h = self._extract_minha_height(katman_adi)
            for entity in msp.query(f'LWPOLYLINE[layer=="{katman_adi}"]'):
                try:
                    with entity.points("xy") as pts:
                        noktalar = list(pts)
                    if len(noktalar) < 3:
                        continue
                    xs = [p[0] for p in noktalar]
                    ys = [p[1] for p in noktalar]
                    x1, y1 = min(xs), min(ys)
                    x2, y2 = max(xs), max(ys)
                    if birim == "m":
                        x1, y1, x2, y2 = x1*100, y1*100, x2*100, y2*100
                    elif birim == "mm":
                        x1, y1, x2, y2 = x1/10, y1/10, x2/10, y2/10
                    if SHAPELY_AVAILABLE:
                        if birim == "m":
                            geo = ShapelyPolygon([(p[0]*100, p[1]*100) for p in noktalar])
                        elif birim == "mm":
                            geo = ShapelyPolygon([(p[0]/10, p[1]/10) for p in noktalar])
                        else:
                            geo = ShapelyPolygon([(p[0], p[1]) for p in noktalar])
                    else:
                        geo = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
                    if not self._is_inside_boundary(geo, hesap_kutusu):
                        continue
                    genislik = max(x2-x1, y2-y1)
                    self.minhalar.append({"id": f"M{minha_sayaci}", "layer": katman_adi,
                                         "h": h, "genislik": genislik, "geo": geo,
                                         "tip": "Cizim",
                                         "coords": f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})"})
                    minha_sayaci += 1
                except Exception as e:
                    logger.warning(f"Minha LWPOLYLINE okuma hatasi: {e}")
            for entity in msp.query(f'INSERT[layer=="{katman_adi}"]'):
                try:
                    try:
                        import ezdxf.bbox
                        bbox = ezdxf.bbox.extents([entity])
                        if not bbox.has_data:
                            continue
                        min_x, min_y, _ = bbox.extmin
                        max_x, max_y, _ = bbox.extmax
                    except:
                        ip = entity.dxf.insert
                        min_x, max_x = ip.x-50, ip.x+50
                        min_y, max_y = ip.y-50, ip.y+50
                    if birim == "m":
                        min_x, min_y = min_x*100, min_y*100
                        max_x, max_y = max_x*100, max_y*100
                    elif birim == "mm":
                        min_x, min_y = min_x/10, min_y/10
                        max_x, max_y = max_x/10, max_y/10
                    if SHAPELY_AVAILABLE:
                        geo = shapely_box(min_x, min_y, max_x, max_y)
                    else:
                        geo = Polygon([(min_x, min_y), (max_x, min_y),
                                       (max_x, max_y), (min_x, max_y)])
                    if not self._is_inside_boundary(geo, hesap_kutusu):
                        continue
                    genislik = max(max_x-min_x, max_y-min_y)
                    self.minhalar.append({"id": f"M{minha_sayaci}", "layer": katman_adi,
                                         "h": h, "genislik": genislik, "geo": geo,
                                         "tip": "Blok",
                                         "coords": f"({min_x:.0f},{min_y:.0f})-({max_x:.0f},{max_y:.0f})"})
                    minha_sayaci += 1
                except Exception as e:
                    logger.warning(f"Minha INSERT okuma hatasi: {e}")
        logger.info(f"Toplam {len(self.minhalar)} minha yuklendi")

    def _parse_dxf_oda_isimleri(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den oda isimlerini (TEXT/MTEXT) oku"""
        if not katman_listesi:
            return
        for entity in msp.query('TEXT MTEXT'):
            try:
                layer = entity.dxf.layer
                if layer not in katman_listesi:
                    continue
                if entity.dxftype() == 'TEXT':
                    yazi = entity.dxf.text
                else:
                    yazi = entity.text
                if yazi:
                    yazi = re.sub(r'\[A-Za-z][^;]*;', '', yazi)
                    yazi = re.sub(r'[{}\]', '', yazi).strip()
                x = entity.dxf.insert.x
                y = entity.dxf.insert.y
                if birim == "m":
                    x, y = x*100, y*100
                elif birim == "mm":
                    x, y = x/10, y/10
                if hesap_kutusu:
                    try:
                        bounds = hesap_kutusu.bounds
                        if not (bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]):
                            continue
                    except:
                        pass
                if yazi and yazi.strip():
                    self.oda_isimleri.append({"text": yazi.strip(), "x": x, "y": y, "layer": layer})
            except Exception as e:
                logger.warning(f"Oda ismi okuma hatasi: {e}")
        logger.info(f"Toplam {len(self.oda_isimleri)} oda ismi yuklendi")

    def _parse_dxf_kat_isimleri(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den kat isimlerini (TEXT/MTEXT) oku"""
        if not katman_listesi:
            return
        for entity in msp.query('TEXT MTEXT'):
            try:
                layer = entity.dxf.layer
                if layer not in katman_listesi:
                    continue
                if entity.dxftype() == 'TEXT':
                    yazi = entity.dxf.text
                else:
                    yazi = entity.text
                if yazi:
                    yazi = re.sub(r'\[A-Za-z][^;]*;', '', yazi)
                    yazi = re.sub(r'[{}\]', '', yazi).strip()
                x = entity.dxf.insert.x
                y = entity.dxf.insert.y
                if birim == "m":
                    x, y = x*100, y*100
                elif birim == "mm":
                    x, y = x/10, y/10
                if hesap_kutusu:
                    try:
                        bounds = hesap_kutusu.bounds
                        if not (bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]):
                            continue
                    except:
                        pass
                if yazi and yazi.strip():
                    self.kat_isimleri.append({"text": yazi.strip(), "x": x, "y": y, "layer": layer})
            except Exception as e:
                logger.warning(f"Kat ismi okuma hatasi: {e}")
        logger.info(f"Toplam {len(self.kat_isimleri)} kat ismi yuklendi")

    def _parse_dxf_m2_yazilari(self, msp, katman_listesi: List[str], birim: str = "cm", hesap_kutusu=None):
        """DXF'den m2 degerlerini (TEXT/MTEXT) oku"""
        if not katman_listesi:
            return
        for entity in msp.query('TEXT MTEXT'):
            try:
                layer = entity.dxf.layer
                if layer not in katman_listesi:
                    continue
                if entity.dxftype() == 'TEXT':
                    yazi = entity.dxf.text
                else:
                    yazi = entity.text
                if yazi:
                    yazi = re.sub(r'\[A-Za-z][^;]*;', '', yazi)
                    yazi = re.sub(r'[{}\]', '', yazi).strip()
                deger = self._sayi_cikar(yazi)
                if deger <= 0:
                    continue
                x = entity.dxf.insert.x
                y = entity.dxf.insert.y
                if birim == "m":
                    x, y = x*100, y*100
                elif birim == "mm":
                    x, y = x/10, y/10
                if hesap_kutusu:
                    try:
                        bounds = hesap_kutusu.bounds
                        if not (bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]):
                            continue
                    except:
                        pass
                self.m2_yazilari.append({"raw_text": yazi, "deger": deger,
                                         "x": x, "y": y, "layer": layer})
            except Exception as e:
                logger.warning(f"M2 yazisi okuma hatasi: {e}")
        logger.info(f"Toplam {len(self.m2_yazilari)} m2 yazisi yuklendi")


    def _sayi_cikar(self, text: str) -> float:
        """Yazidan sayiyi cikar (Ornek: '24.5 m2' -> 24.5)"""
        try:
            bulunan = re.findall(r"[-+]?\d*[.,]\d+|\d+", text)
            if bulunan:
                return float(bulunan[0].replace(',', '.'))
            return 0.0
        except:
            return 0.0

    def _mesafe_hesapla(self, p1: tuple, p2: tuple) -> float:
        """Iki nokta arasi mesafe (Oklid)"""
        import math
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def _3d_onizle_guncelle(self):
        """sap_eslestirme verisini 3D onizleme paneline aktar."""
        if self._3d_panel is None or not self.sap_eslestirme:
            return
        try:
            kat_h = getattr(self, 'kat_yuksekligi_spin', None)
            yukseklik = kat_h.value() if kat_h else 2.80
            self._3d_panel.load_from_sap(self.sap_eslestirme, yukseklik)
            logger.info(f"3D panel guncellendi: {len(self.sap_eslestirme)} oda, h={yukseklik:.2f}m")
        except Exception as exc:
            logger.error(f"3D panel guncelleme hatasi: {exc}")

    def _eslesitir_m2_oda(self):
        """M2 degerlerini en yakin oda isimleriyle esle"""
        self.sap_eslestirme.clear()
        for m2 in self.m2_yazilari:
            en_yakin_isim = "TANIMSIZ"
            en_kisa_mesafe = float('inf')
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
        """Sap eslestirmesine gore imalat listesi olustur"""
        self.imalat_listesi.clear()
        self.malzeme_ihtiyaclari.clear()

        kat_h = self.kat_yuksekligi_spin.value()  # cm
        tezgah_arasi_h = 60
        tezgah_uzunluk = 350

        def ekle_imalat(mahal, grup, imalat, miktar, birim):
            self.imalat_listesi.append({
                "Mahal": mahal, "Grup": grup, "Imalat": imalat,
                "Miktar": round(miktar, 2), "Birim": birim
            })
            sarfiyat_db = getattr(self, 'sarfiyatlar_ozel', SARFIYATLAR)
            if imalat in sarfiyat_db:
                veri = sarfiyat_db[imalat]
                tuketim = miktar * veri[0]
                paket_sayisi = tuketim / veri[1]
                if imalat not in self.malzeme_ihtiyaclari:
                    self.malzeme_ihtiyaclari[imalat] = {
                        "Toplam Tuketim": 0, "Paket Sayisi": 0,
                        "Paket Tipi": veri[2], "Malzeme Turu": veri[3]
                    }
                self.malzeme_ihtiyaclari[imalat]["Toplam Tuketim"] += tuketim
                self.malzeme_ihtiyaclari[imalat]["Paket Sayisi"] += paket_sayisi

        katsayi = self._alan_katsayisi()
        for sap in self.sap_eslestirme:
            mahal = sap["mahal_adi"]
            brut_alan = sap["deger"]  # m2 (DXF'den okunan brut değer)
            zemin_alan = brut_alan * katsayi  # katsayı uygulanmış alan
            recete = recete_getir(mahal)
            tahmini_cevre_m = 4 * math.sqrt(max(zemin_alan, 0.01))
            duvar_alan = tahmini_cevre_m * (kat_h / 100)  # m2

            for kalem in recete["ZEMIN"]:
                ekle_imalat(mahal, "ZEMIN", kalem, zemin_alan, "m2")
            for kalem in recete["TAVAN"]:
                ekle_imalat(mahal, "TAVAN", kalem, zemin_alan, "m2")
            for kalem in recete["DUVAR"]:
                ekle_imalat(mahal, "DUVAR", kalem, duvar_alan, "m2")
            if recete["SUPURGELIK"]:
                ekle_imalat(mahal, "SUPURGELIK", recete["SUPURGELIK"], tahmini_cevre_m, "mtul")
            for ekstra in recete["EKSTRA"]:
                miktar = 0
                birim = "m2"
                if ekstra == "Tezgah Arasi Seramik":
                    miktar = (tezgah_uzunluk / 100) * (tezgah_arasi_h / 100)
                elif ekstra == "Fayans Yapistirici":
                    miktar = (tezgah_uzunluk / 100) * (tezgah_arasi_h / 100)
                ekle_imalat(mahal, "EKSTRA", ekstra, miktar, birim)

            for tefris in self.tefrisler:
                if self._nokta_odada_mi(tefris["x"], tefris["y"], sap):
                    self.imalat_listesi.append({
                        "Mahal": mahal, "Grup": "TEFRISAT", "Imalat": tefris["tur"],
                        "Miktar": 1, "Birim": "Adet"
                    })

        logger.info(f"Toplam {len(self.imalat_listesi)} imalat kalemi, {len(self.malzeme_ihtiyaclari)} malzeme turu")
        toplam_m2 = sum(s.get("deger", 0) for s in self.sap_eslestirme) if self.sap_eslestirme else 0
        if toplam_m2 > 0:
            self._anomali_tespit(toplam_m2)

    def _nokta_odada_mi(self, x: float, y: float, sap: Dict) -> bool:
        """Bir noktanin odaya yakin olup olmadigini kontrol et"""
        # Basit mesafe kontrolu (m2 noktasina yakinlik)
        mesafe = math.sqrt((x - sap["x"])**2 + (y - sap["y"])**2)
        return mesafe < 500 # 5 metre yaricap

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
                    if hesap_kutusu:
                        try:
                            bounds = hesap_kutusu.bounds
                            if not (bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]):
                                continue
                        except:
                            pass
                    for anahtar, tur in TEFRIS_SOZLUGU.items():
                        if anahtar in blok_adi:
                            self.tefrisler.append({"tur": tur, "blok": blok_adi, "x": x, "y": y})
                            break
                except:
                    continue
            logger.info(f"Toplam {len(self.tefrisler)} tefris blogu bulundu")
        except Exception as e:
            logger.error(f"Tefris okuma hatasi: {e}")

    def _extract_minha_height(self, katman_adi: str) -> int:
        """Katman adindan minha yuksekligini cikar"""
        # Pattern: M_MINHA_H210, PENCERE_H120, KAPI_H210 vs.
        patterns = [
        r'H(\d+)', # H210, H120
        r'_(\d+)$', # _210, _120
        r'(\d+)CM', # 210CM
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
        r'H(\d+)', # H60, H50
        r'_(\d+)$', # _60, _50
        r'(\d+)CM', # 60CM
        r'(\d+)$', # sadece rakam
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
        r'_(\d+)$', # _20, _15
        r'_(\d+)_', # _20_
        r'(\d+)CM', # 20CM
        r'T(\d+)', # T20 (tuğla 20)
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
        r'_H(\d+)', # _H270, _H300
        r'H(\d+)', # H270
        r'_(\d{3})$', # _270 (3 haneli, sonda)
        r'_(\d{3})_', # _270_ (3 haneli, ortada)
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
            kalinlik_alanlari[kalinlik] += alan  # döngü içinde, if dışında

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

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Dosyasi Kaydet", "metraj_analiz_sonuc.xlsx",
            "Excel Dosyalari (*.xlsx);;Tum Dosyalar (*)"
        )
        if not file_path:
            return

        try:
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                if self.sonuc_duvarlar:
                    data = []
                    for d in self.sonuc_duvarlar:
                        data.append({
                            "Poz No": d["id"], "Layer": d.get("layer", ""),
                            "Durum": d["aciklama"], "Kalinlik (cm)": d.get("kalinlik_cm", 20),
                            "Yukseklik (cm)": d["net_h"], "Uzunluk (m)": round(d.get("uzunluk", 0), 2),
                            "Brut Alan (m2)": round(d.get("brut_alan", d["alan"]), 2),
                            "Minha Dusumu (m2)": round(d.get("minha_alani", 0), 2),
                            "Minha Detay": ", ".join(d.get("minha_detay", [])),
                            "NET ALAN (m2)": round(d["alan"], 2)
                        })
                    pd.DataFrame(data).to_excel(writer, index=False, sheet_name="Duvar Metraji")

                if self.sap_eslestirme:
                    sap_data = [{"Mahal Adi": s["mahal_adi"], "Okunan Yazi": s["okunan_yazi"],
                                 "Alan (m2)": round(s["deger"], 2),
                                 "Koordinat X": round(s["x"], 2), "Koordinat Y": round(s["y"], 2)}
                                for s in self.sap_eslestirme]
                    pd.DataFrame(sap_data).to_excel(writer, index=False, sheet_name="Sap Metraji")

                if self.imalat_listesi:
                    df_imalat = pd.DataFrame(self.imalat_listesi)
                    df_imalat.to_excel(writer, index=False, sheet_name="Detayli Imalat")
                    ozet = df_imalat.groupby(["Grup", "\u0130malat", "Birim"])["Miktar"].sum().reset_index()
                    ozet.sort_values(["Grup", "\u0130malat"]).to_excel(writer, index=False, sheet_name="Malzeme Ozeti")

                if self.malzeme_ihtiyaclari:
                    sp = [{"Malzeme": m, "Toplam": round(d["Toplam T\xfcketim"], 2),
                           "Paket": math.ceil(d["Paket Say\u0131s\u0131"]), "Tip": d["Paket Tipi"]}
                          for m, d in self.malzeme_ihtiyaclari.items()]
                    pd.DataFrame(sp).to_excel(writer, index=False, sheet_name="NALBUR SIPARIS")

                if self.sonuc_duvarlar:
                    ds = self._hesapla_duvar_malzeme_siparis()
                    if ds:
                        pd.DataFrame(ds).to_excel(writer, index=False, sheet_name="DUVAR MALZEME SIPARIS")

            mesaj = [f"Sonuclar kaydedildi:\n{file_path}"]
            if self.sonuc_duvarlar:
                net = sum(d["alan"] for d in self.sonuc_duvarlar)
                mesaj.append(f"\nDUVAR: {len(self.sonuc_duvarlar)} adet, NET {net:.2f} m2")
            if self.sap_eslestirme:
                mesaj.append(f"\nSAP: {len(self.sap_eslestirme)} mahal")
            if self.imalat_listesi:
                mesaj.append(f"\n\u0130MALAT: {len(self.imalat_listesi)} kalem")
            QMessageBox.information(self, "Basarili", "\n".join(mesaj))
            logger.info(f"Excel kaydedildi: {file_path}")

        except Exception as e:
            logger.error(f"Excel kaydetme hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{str(e)}")


    def _beton_kalip_acad_olc(self):
        """AutoCAD'den secilen objenin geometrik boyutlarini okuyup formlari doldur."""
        if not self.acad_connector or not self.acad_connector.bagli:
            QMessageBox.warning(self, "Uyari", "Once AutoCAD'e baglanin!")
            return

        eleman = self.bk_eleman_combo.currentText()
        birim = self.bk_acad_birim_combo.currentText()
        dolacak_harita = {
            "Kolon": "Boy ve En (Yuksekligi kendiniz girin)",
            "Kiris": "Boy ve Genislik (Derinligi kendiniz girin)",
            "Doseme": "Uzunluk ve Genislik (Kalinligi kendiniz girin)",
            "Temel": "Boy ve En (Derinligi kendiniz girin)",
            "Perde Duvar": "Uzunluk (Kalinlik ve Yuksekligi kendiniz girin)",
        }
        bilgi = dolacak_harita.get(eleman, "Boyutlar")

        ret = QMessageBox.information(
            self, f"AutoCAD Olcumu - {eleman}",
            f"AutoCAD penceresine gecin ve uygun objeyi secin.\n\n"
            f"Eleman: {eleman} | Birim: {birim}\nDolacak: {bilgi}\n\n"
            f"ENTER=Onayla, ESC=Iptal",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if ret == QMessageBox.StandardButton.Cancel:
            return

        try:
            sonuc = self.acad_connector.get_beton_kalip_boyutlar(eleman_turu=eleman, birim=birim)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"AutoCAD okuma hatasi:\n{str(e)}")
            return

        if sonuc["iptal"]:
            QMessageBox.information(self, "Iptal", "Secim iptal edildi.")
            return

        if sonuc["hata"] and sonuc["dim1"] == 0.0:
            QMessageBox.warning(self, "Okuma Hatasi",
                f"Boyut okunamadi:\n{sonuc['hata']}\n\n"
                "Kolon/Kiris icin kapali dikdortgen polyline secin.")
            return

        dim1 = sonuc["dim1"]
        dim2 = sonuc["dim2"]
        if dim1 > 0:
            self.bk_dim1_spin.setValue(dim1)
            if dim2 > 0:
                self.bk_dim2_spin.setValue(dim2)

        if eleman == "Perde Duvar":
            boyut_ozet = f"Uzunluk: {dim1:.3f} m"
        else:
            boyut_ozet = f"Boyut 1: {dim1:.3f} m | Boyut 2: {dim2:.3f} m"

        hata_notu = f"\n\nUyari: {sonuc['hata']}" if sonuc["hata"] else ""
        QMessageBox.information(
            self, "Boyutlar Okundu",
            f"Eleman: {eleman}\nKatman: {sonuc['katman']}\nObje: {sonuc['entity_type']}\n\n"
            f"{boyut_ozet}\n\nYukseklik/Derinlik/Kalinligi kendiniz girin, ardindan '+ Ekle'ye basin.{hata_notu}"
        )


    def _beton_kalip_eleman_degisti(self, eleman: str):
        """Eleman türü değişince boyut etiketlerini dinamik güncelle.

        Neyi çözüyoruz?
        Her eleman türünün (kolon, kiriş vb.) boyutları farklı anlam taşır.
        Kullanıcının doğru değer girmesi için etiketler canlı güncellenir.

        Nasıl test ederiz?
        _beton_kalip_eleman_degisti("Kiriş") çağrılınca
        bk_dim2_label.text() == "Genişlik (m):" olmalı.
        """
        etiket_haritasi = {
        "Kolon": ("Boy (m):", "En (m):", "Yükseklik (m):"),
        "Kiriş": ("Boy (m):", "Genişlik (m):", "Derinlik (m):"),
        "Döşeme": ("Uzunluk (m):", "Genişlik (m):", "Kalınlık (m):"),
        "Temel": ("Boy (m):", "En (m):", "Derinlik (m):"),
        "Perde Duvar": ("Uzunluk (m):", "Kalınlık (m):", "Yükseklik (m):"),
        }
        d1, d2, d3 = etiket_haritasi.get(eleman, ("Ölçü1:", "Ölçü2:", "Ölçü3:"))
        self.bk_dim1_label.setText(d1)
        self.bk_dim2_label.setText(d2)
        self.bk_dim3_label.setText(d3)

        # Eleman türüne göre önerilen fire katsayısını otomatik ayarla
        fire_onerisi = {
        "Kolon": 5.0, # Kalıp sızdırmazlığı iyi → düşük fire
        "Kiriş": 5.0,
        "Döşeme": 3.0, # Geniş alan, döküm kolay → en düşük fire
        "Temel": 7.0, # Zemin şartları belirsiz → yüksek fire
        "Perde Duvar": 5.0,
        }
        oneri = fire_onerisi.get(eleman, 5.0)
        self.bk_fire_spin.setValue(oneri)
        self.bk_fire_oneri_label.setText(
        f"({eleman} için önerilen: %{oneri:.0f})"
        )

    def _beton_kalip_hesapla_eleman(
        self, eleman: str, adet: int, b: float, e: float, y: float
    ) -> tuple[float, float]:
        """Elemana gore beton hacmi ve kalip alani hesapla."""
        n = adet
        beton = b * e * y * n

        if eleman == "Kolon":
            kalip = 2 * (b + e) * y * n
        elif eleman == "Kiri\u015f":
            kalip = (2 * y + e) * b * n
        elif eleman == "D\xf6\u015feme":
            kalip = b * e * n
        elif eleman == "Temel":
            kalip = (2 * (b + e) * y + b * e) * n
        elif eleman == "Perde Duvar":
            kalip = 2 * b * y * n
        else:
            kalip = 0.0

        return round(beton, 4), round(kalip, 4)


    def _beton_kalip_kalem_ekle(self):
        """Form değerlerinden yeni bir satır tabloya ekle ve toplamları güncelle.

        Neyi çözüyoruz?
        Kullanıcının girdiği eleman bilgisini alıp formüle uygular,
        hesaplanan beton/kalıp değerleriyle tabloya ekler.

        Nasıl test ederiz?
        bk_eleman_combo = "Kolon", adet=2, dim1=0.5, dim2=0.5, dim3=3.0, fire=%5
        → net beton = 1.500 m³, sipariş = 1.575 m³, kalıp = 12.000 m²
        """
        eleman = self.bk_eleman_combo.currentText()
        adet = self.bk_adet_spin.value()
        dim1 = self.bk_dim1_spin.value()
        dim2 = self.bk_dim2_spin.value()
        dim3 = self.bk_dim3_spin.value()
        fire_pct = self.bk_fire_spin.value()

        beton, kalip = self._beton_kalip_hesapla_eleman(eleman, adet, dim1, dim2, dim3)
        siparis = round(beton * (1 + fire_pct / 100), 3)

        row = self.beton_kalip_table.rowCount()
        self.beton_kalip_table.insertRow(row)

        veriler = [
        eleman,
        str(adet),
        f"{dim1:.2f}",
        f"{dim2:.2f}",
        f"{dim3:.2f}",
        f"{beton:.3f}",
        f"{fire_pct:.1f}",
        f"{siparis:.3f}",
        f"{kalip:.3f}",
        ]
        for col, deger in enumerate(veriler):
            item = QTableWidgetItem(deger)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.beton_kalip_table.setItem(row, col, item)

            self._beton_kalip_toplamlar_guncelle()

    def _beton_kalip_toplamlar_guncelle(self):
        """Tablodaki tum satirlari okuyarak toplam etiketlerini guncelle."""
        toplam_beton = toplam_siparis = toplam_kalip = 0.0
        for row in range(self.beton_kalip_table.rowCount()):
            def _val(col):
                item = self.beton_kalip_table.item(row, col)
                return float(item.text()) if item else 0.0
            toplam_beton += _val(5)
            toplam_siparis += _val(7)
            toplam_kalip += _val(8)
        self.bk_toplam_beton_label.setText(f"Net Beton: {toplam_beton:.3f} m\u00b3")
        self.bk_toplam_siparis_label.setText(f"Sipari\u015f: {toplam_siparis:.3f} m\u00b3")
        self.bk_toplam_kalip_label.setText(f"Toplam Kal\u0131p: {toplam_kalip:.3f} m\u00b2")


    def _beton_kalip_satir_sil(self):
        """Secili satiri tablodan sil ve toplamlari guncelle."""
        selected_rows = self.beton_kalip_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Bilgi", "Silmek icin bir satir secin.")
            return
        for index in sorted(selected_rows, reverse=True):
            self.beton_kalip_table.removeRow(index.row())
        self._beton_kalip_toplamlar_guncelle()


    def _beton_kalip_excel(self):
        """Beton & Kalip tablosunu Excel dosyasi olarak disa aktar."""
        if not PANDAS_AVAILABLE:
            QMessageBox.warning(self, "Uyari",
                "Excel icin pandas+openpyxl gerekli:\npip install pandas openpyxl")
            return

        if self.beton_kalip_table.rowCount() == 0:
            QMessageBox.information(self, "Bilgi", "Disa aktarilacak veri yok.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Kaydet", "beton_kalip_metraj.xlsx", "Excel (*.xlsx)"
        )
        if not file_path:
            return

        try:
            sutunlar = ["Eleman", "Adet", "Olcu1(m)", "Olcu2(m)", "Olcu3(m)",
                        "Net Beton(m3)", "Fire(%)", "Siparis(m3)", "Kalip(m2)"]
            satirlar = []
            for row in range(self.beton_kalip_table.rowCount()):
                satir = []
                for col in range(self.beton_kalip_table.columnCount()):
                    item = self.beton_kalip_table.item(row, col)
                    satir.append(item.text() if item else "")
                satirlar.append(satir)

            df = pd.DataFrame(satirlar, columns=sutunlar)
            tb = df["Net Beton(m3)"].astype(float).sum()
            ts = df["Siparis(m3)"].astype(float).sum()
            tk = df["Kalip(m2)"].astype(float).sum()
            toplam = pd.DataFrame([[
                "TOPLAM", "", "", "", "",
                f"{tb:.3f}", "", f"{ts:.3f}", f"{tk:.3f}"
            ]], columns=sutunlar)
            pd.concat([df, toplam], ignore_index=True).to_excel(
                file_path, index=False, sheet_name="Beton Kalip"
            )
            QMessageBox.information(self, "Basarili",
                f"Kaydedildi:\n{file_path}\nBeton: {tb:.3f} m3 | Kalip: {tk:.3f} m2")
            logger.info(f"Beton Kalip Excel: {file_path}")

        except Exception as e:
            logger.error(f"Beton Kalip Excel hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{str(e)}")


    def _alan_turu_degistir(self, net_secili: bool):
        """Kullanıcı Net / Brüt seçtiğinde alan türünü güncelle ve yeniden hesapla."""
        self.alan_turu = "net" if net_secili else "brut"
        logger.info(f"Alan türü değiştirildi: {self.alan_turu}")

        # Bilgi etiketini güncelle
        if hasattr(self, '_alan_bilgi_label'):
            if self.alan_turu == "net":
                self._alan_bilgi_label.setText("ℹ Net Alan — %12 azaltma uygulanıyor (katsayı: 0.88)")
                self._alan_bilgi_label.setStyleSheet("color: #ffaa00; font-size: 10px; padding: 2px;")
            else:
                self._alan_bilgi_label.setText("ℹ Brüt Alan — katsayı uygulanmıyor (katsayı: 1.00)")
                self._alan_bilgi_label.setStyleSheet("color: #aaaaaa; font-size: 10px; padding: 2px;")

        # sap_eslestirme doluysa yeniden hesapla
        if self.sap_eslestirme:
            self._hesapla_imalat_listesi()
            self._3d_onizle_guncelle()
            logger.info(
                f"İmalat listesi yeniden hesaplandı: katsayı={self._alan_katsayisi()}, "
                f"{len(self.imalat_listesi)} kalem"
            )

    def _alan_katsayisi(self) -> float:
        """Net alan katsayısını döndür.

        Brüt modda: DXF'deki ölçüler olduğu gibi kullanılır (katsayı = 1.0)
        Net modda: Duvar kalınlıkları düşülerek yaklaşık net alan alınır
        (tipik kayıp %10-15 → varsayılan %12 kesinti).
        """
        return 1.0 if self.alan_turu == "brut" else 0.88

        # ═══════════════════════════════════════════════════════════════════════════
        # ÖZELLİK 2 — Çoklu Kat / Çoklu DXF
        # ═══════════════════════════════════════════════════════════════════════════

        # ─────────────────────────────────────────────────────────────────────────
        # ÇOKLU KAT — AutoCAD Tabanlı Kat Bazlı Metraj
        # ─────────────────────────────────────────────────────────────────────────

    def _coklu_acad_bagli_mi(self) -> bool:
        """AutoCAD bağlantısını kontrol et, bağlı değilse kullanıcıyı uyar."""
        if self.acad_connector is None or not getattr(self.acad_connector, '_bagli', False):
            QMessageBox.warning(
                self, "AutoCAD Bağlantısı Yok",
                "Önce ' AutoCAD'e Bağlan' butonuna basın!\n\n"
                "AutoCAD açık ve bir çizim yüklü olmalıdır."
            )
            return False
        return True

    def _coklu_kat_aktif_al(self):
        """Şu an listede seçili olan kat sözlüğünü döndür; yoksa None."""
        row = self.coklu_kat_listesi.currentRow()
        if row < 0 or row >= len(self.mimari_katlar):
            return None
        return self.mimari_katlar[row]

    def _coklu_kat_ekle(self):
        """Listeye yeni bir kat ekle (ölçüm AutoCAD ile yapılacak)."""
        kat_adi = self.coklu_kat_input.text().strip()
        if not kat_adi:
            QMessageBox.warning(self, "Uyarı", "Kat adı girin!")
            return
        for k in self.mimari_katlar:
            if k["kat_adi"].lower() == kat_adi.lower():
                QMessageBox.warning(self, "Uyarı", f"'{kat_adi}' zaten mevcut!")
                return
        self.mimari_katlar.append({"kat_adi": kat_adi, "imalat": []})
        self.coklu_kat_listesi.addItem(f" {kat_adi} | 0 ölçüm")
        self.coklu_kat_input.clear()
        self.coklu_kat_listesi.setCurrentRow(len(self.mimari_katlar) - 1)
        self._coklu_kat_ozet_guncelle()
        logger.info(f"Çoklu kat eklendi: {kat_adi}")

    def _coklu_kat_aktif_degisti(self, row: int):
        """Listede farklı kat seçildiğinde ölçüm panelini güncelle."""
        self._coklu_kat_aktif_panel_guncelle()

    def _coklu_kat_sil(self):
        """Seçili katı ve tüm ölçümlerini sil."""
        row = self.coklu_kat_listesi.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Silinecek katı seçin!")
            return
        kat_adi = self.mimari_katlar[row]["kat_adi"]
        reply = QMessageBox.question(
            self, "Onayla",
            f"'{kat_adi}' katını ve tüm ölçümlerini silmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.mimari_katlar.pop(row)
            self.coklu_kat_listesi.takeItem(row)
            self._coklu_kat_aktif_panel_guncelle()
            self._coklu_kat_ozet_guncelle()

    def _coklu_kat_olcum_polyline(self):
        """Aktif kat icin AutoCAD'de polyline cizerek alan veya uzunluk olc."""
        if not self._coklu_acad_bagli_mi():
            return
        aktif_kat = self._coklu_kat_aktif_al()
        if aktif_kat is None:
            QMessageBox.warning(self, "Uyari", "Once listeden bir kat secin!")
            return
        tanim = self.ck_olcum_adi_input.text().strip() or "Polyline Olcumu"
        birim = self.ck_olcum_birim_combo.currentText()
        try:
            sonuc = self.acad_connector.polyline_cizdir(
                f"'{aktif_kat['kat_adi']}' - alani cizin, ENTER ile bitirin",
                kapat=True
            )
            if sonuc.get("iptal"):
                return
            miktar = round(
                sonuc.get("alan", 0) if birim == "m\u00b2" else sonuc.get("uzunluk", 0), 4
            )
            if miktar <= 0:
                QMessageBox.warning(self, "Uyari", "Gecerli olcum alinamadi.")
                return
            aktif_kat["imalat"].append({"tanim": tanim, "miktar": miktar, "birim": birim})
            self._coklu_kat_aktif_panel_guncelle()
            self._coklu_kat_list_item_guncelle()
            self._coklu_kat_ozet_guncelle()
            self.ck_olcum_adi_input.clear()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))


    def _coklu_kat_olcum_obje(self):
        """Aktif kat icin AutoCAD'den obje secerek olcum al."""
        if not self._coklu_acad_bagli_mi():
            return
        aktif_kat = self._coklu_kat_aktif_al()
        if aktif_kat is None:
            QMessageBox.warning(self, "Uyari", "Once listeden bir kat secin!")
            return
        tanim = self.ck_olcum_adi_input.text().strip() or "Obje Secimi"
        birim = self.ck_olcum_birim_combo.currentText()
        try:
            objeler = self.acad_connector.kullanici_secimi_al(
                f"'{aktif_kat['kat_adi']}' - objeleri secin, ENTER ile bitirin"
            )
            if not objeler:
                return
            if birim == "m\u00b2":
                miktar = round(sum(getattr(o, 'alan', 0) for o in objeler), 4)
            elif birim == "m":
                miktar = round(sum(getattr(o, 'uzunluk', 0) for o in objeler), 4)
            elif birim == "adet":
                miktar = float(len(objeler))
            else:
                miktar = round(sum(getattr(o, 'alan', 0) for o in objeler), 4)
            if miktar <= 0:
                miktar = float(len(objeler))
                birim = "adet"
            aktif_kat["imalat"].append({"tanim": tanim, "miktar": miktar, "birim": birim})
            self._coklu_kat_aktif_panel_guncelle()
            self._coklu_kat_list_item_guncelle()
            self._coklu_kat_ozet_guncelle()
            self.ck_olcum_adi_input.clear()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))


    def _coklu_kat_olcum_katman(self):
        """Aktif kat icin AutoCAD katmanina gore olcum al."""
        if not self._coklu_acad_bagli_mi():
            return
        aktif_kat = self._coklu_kat_aktif_al()
        if aktif_kat is None:
            QMessageBox.warning(self, "Uyari", "Once listeden bir kat secin!")
            return
        katmanlar = self.acad_connector.katman_listesi_al()
        if not katmanlar:
            QMessageBox.warning(self, "Uyari", "AutoCAD'de katman bulunamadi!")
            return
        katman, ok = QInputDialog.getItem(
            self, "Katman Sec",
            f"'{aktif_kat['kat_adi']}' icin katman secin:",
            katmanlar, 0, False
        )
        if not ok:
            return
        tanim = self.ck_olcum_adi_input.text().strip() or f"Katman: {katman}"
        birim = self.ck_olcum_birim_combo.currentText()
        try:
            objeler = self.acad_connector.katmana_gore_sec(katman)
            if not objeler:
                QMessageBox.information(self, "Bilgi", f"'{katman}' katmaninda olcum bulunamadi.")
                return
            if birim == "m\u00b2":
                miktar = round(sum(getattr(o, 'alan', 0) for o in objeler), 4)
            elif birim == "m":
                miktar = round(sum(getattr(o, 'uzunluk', 0) for o in objeler), 4)
            else:
                miktar = float(len(objeler))
                birim = "adet"
            aktif_kat["imalat"].append({"tanim": tanim, "miktar": miktar, "birim": birim})
            self._coklu_kat_aktif_panel_guncelle()
            self._coklu_kat_list_item_guncelle()
            self._coklu_kat_ozet_guncelle()
            self.ck_olcum_adi_input.clear()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))


    def _coklu_kat_olcum_manuel(self):
        """Aktif kata manuel değer gir (AutoCAD gerektirmez)."""
        aktif_kat = self._coklu_kat_aktif_al()
        if aktif_kat is None:
            QMessageBox.warning(self, "Uyarı", "Önce listeden bir kat seçin!")
            return
        tanim = self.ck_olcum_adi_input.text().strip()
        if not tanim:
            QMessageBox.warning(self, "Uyarı", "Ölçüm adı girin!")
            return
        birim = self.ck_olcum_birim_combo.currentText()
        deger, ok = QInputDialog.getDouble(
            self, "Manuel Değer",
            f"'{tanim}' için {birim} değerini girin:",
            0.0, 0.0, 9999999.0, 4
        )
        if not ok:
            return
        aktif_kat["imalat"].append({"tanim": tanim, "miktar": deger, "birim": birim})
        self._coklu_kat_aktif_panel_guncelle()
        self._coklu_kat_list_item_guncelle()
        self._coklu_kat_ozet_guncelle()
        self.ck_olcum_adi_input.clear()

    def _coklu_kat_olcum_sil(self):
        """Aktif katın ölçüm tablosundan seçili satırı sil."""
        aktif_kat = self._coklu_kat_aktif_al()
        if aktif_kat is None:
            return
        row = self.ck_olcum_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Silinecek ölçümü seçin!")
            return
        aktif_kat["imalat"].pop(row)
        self._coklu_kat_aktif_panel_guncelle()
        self._coklu_kat_list_item_guncelle()
        self._coklu_kat_ozet_guncelle()

    def _coklu_kat_aktif_panel_guncelle(self):
        """Aktif kat panelini (başlık + tablo) güncelle."""
        aktif_kat = self._coklu_kat_aktif_al()
        if aktif_kat is None:
            self.ck_aktif_label.setText(" Aktif Kat: — (Listeden bir kat seçin)")
            self.ck_olcum_table.setRowCount(0)
            return
        self.ck_aktif_label.setText(f" Aktif Kat: {aktif_kat['kat_adi']}")
        imalat = aktif_kat["imalat"]
        self.ck_olcum_table.setRowCount(len(imalat))
        for i, olcum in enumerate(imalat):
            self.ck_olcum_table.setItem(i, 0, QTableWidgetItem(olcum["tanim"]))
            self.ck_olcum_table.setItem(i, 1, QTableWidgetItem(f"{olcum['miktar']:.4f}"))
            self.ck_olcum_table.setItem(i, 2, QTableWidgetItem(olcum["birim"]))

    def _coklu_kat_list_item_guncelle(self):
        """Kat listesindeki aktif satırın metnini güncelle."""
        row = self.coklu_kat_listesi.currentRow()
        if row < 0 or row >= len(self.mimari_katlar):
            return
        kat = self.mimari_katlar[row]
        n = len(kat["imalat"])
        self.coklu_kat_listesi.item(row).setText(f" {kat['kat_adi']} | {n} ölçüm")

    def _coklu_kat_hesapla(self):
        """Tüm katların ölçümlerini birim bazında topla, özet diyalog göster."""
        if not self.mimari_katlar:
            QMessageBox.information(self, "Bilgi", "Henüz kat eklenmedi.")
            return
        from collections import defaultdict
        birim_topla = defaultdict(float)
        satirlar = [f"{'─'*55}"]
        for kat in self.mimari_katlar:
            satirlar.append(f" {kat['kat_adi']}")
            if not kat["imalat"]:
                satirlar.append(" (ölçüm yok)")
            for olcum in kat["imalat"]:
                satirlar.append(
                    f" {olcum['tanim']:<26} {olcum['miktar']:>10.2f} {olcum['birim']}"
                )
                birim_topla[olcum["birim"]] += olcum["miktar"]
            satirlar.append(f"{'─'*55}")
        satirlar.append(" GENEL TOPLAM:")
        for birim, toplam in sorted(birim_topla.items()):
            satirlar.append(f" {birim:<10} {toplam:>12.2f}")
        QMessageBox.information(self, "Çoklu Kat — Özet", "\n".join(satirlar))
        self._coklu_kat_ozet_guncelle()

    def _coklu_kat_metraja_aktar(self):
        """Tum kat olcumlerini ana pencerenin Metraj Cetveli'ne aktar."""
        pw = self.parent()
        if pw is None or not hasattr(pw, 'current_project_id'):
            QMessageBox.warning(self, "Uyari", "Ana pencere baglantisi kurulamadi!")
            return
        if not pw.current_project_id:
            QMessageBox.warning(self, "Uyari", "Metraja aktarmak icin once bir proje secin!")
            return
        toplam = 0
        for kat in self.mimari_katlar:
            for olcum in kat["imalat"]:
                try:
                    pw.db.add_metraj_kalem(
                        proje_id=pw.current_project_id,
                        tanim=f"[{kat['kat_adi']}] {olcum['tanim']}",
                        miktar=olcum["miktar"], birim=olcum["birim"],
                        birim_fiyat=0, poz_no="", kategori="Coklu Kat"
                    )
                    toplam += 1
                except Exception as e:
                    logger.warning(f"Metraj aktarim hatasi: {e}")
        if toplam:
            if hasattr(pw, 'load_metraj_data'):
                pw.load_metraj_data()
            QMessageBox.information(self, "Basarili", f"{toplam} olcum Metraj Cetveli'ne aktarildi.")
        else:
            QMessageBox.warning(self, "Uyari", "Aktarilacak olcum yok. Once olcum ekleyin.")


    def _coklu_kat_ozet_guncelle(self):
        """Özet etiketini güncelle."""
        n_kat = len(self.mimari_katlar)
        n_olcum = sum(len(k["imalat"]) for k in self.mimari_katlar)
        self.coklu_kat_ozet_label.setText(f"Kat: {n_kat} | Toplam ölçüm: {n_olcum}")

        # ═══════════════════════════════════════════════════════════════════════════
        # ÖZELLİK 3 — Metraj Cetvelı'ne Tek Tuşla Aktarım
        # ═══════════════════════════════════════════════════════════════════════════

    def _metraj_cetvelne_aktar(self):
        """Imalat listesini ana pencerenin Metraj Cetveli'ne aktar."""
        if not self.imalat_listesi:
            QMessageBox.information(self, "Bilgi",
                "Aktarilacak imalat listesi bos.\nOnce DXF yukleyip hesaplama yapin.")
            return

        ana_pencere = self.parent()
        db = getattr(ana_pencere, "db", None)
        proje_id = getattr(ana_pencere, "current_project_id", None) if db is not None else None

        eklenen = 0
        hatalar = []
        for kalem in self.imalat_listesi:
            tanim = kalem.get("tanim", "")
            miktar = kalem.get("miktar", 0)
            birim = kalem.get("birim", "m\u00b2")
            kategori = kalem.get("kategori", "\u0130nce \u0130\u015fler")
            if not tanim or miktar <= 0:
                continue
            if db is not None and proje_id is not None:
                try:
                    db.add_metraj_kalem(
                        proje_id=proje_id, tanim=tanim,
                        miktar=round(miktar, 3), birim=birim,
                        birim_fiyat=0.0, poz_no="", kategori=kategori,
                    )
                    eklenen += 1
                except Exception as e:
                    hatalar.append(f"{tanim}: {e}")
            else:
                eklenen += 1

        if db is None or proje_id is None:
            QMessageBox.information(self, "Uyari",
                f"{eklenen} kalem hazir ancak aktif proje bulunamadi.\n"
                "Ana ekranda bir proje secip tekrar deneyin.")
            return

        msg = f"{eklenen} imalat kalemi Metraj Cetveli'ne aktarildi."
        if hatalar:
            msg += f"\n\n{len(hatalar)} hata:\n" + "\n".join(hatalar[:5])
        QMessageBox.information(self, "Aktarim Tamamlandi", msg)
        if hasattr(ana_pencere, "load_metraj_data"):
            ana_pencere.load_metraj_data()


    def _anomali_tespit(self, alan_m2: float):
        """Hesaplanan imalat kalemlerini NORMAL_ARALIKLAR ile karsilastir."""
        self.uyari_listesi.clear()
        self.uyari_listesi_widget.clear()
        if alan_m2 <= 0:
            return
        for kalem in self.imalat_listesi:
            tanim = kalem.get("tanim", "")
            miktar = kalem.get("miktar", 0)
            birim = kalem.get("birim", "")
            if tanim not in NORMAL_ARALIKLAR:
                continue
            min_k, max_k = NORMAL_ARALIKLAR[tanim]
            katsayi = miktar / alan_m2
            if katsayi < min_k:
                uyari = f" {tanim}: {miktar:.2f} {birim} (min {min_k*alan_m2:.2f}) - Dusuk"
                self.uyari_listesi.append(uyari)
                item = QListWidgetItem(uyari)
                item.setForeground(QColor("#FFA500"))
                self.uyari_listesi_widget.addItem(item)
            elif katsayi > max_k:
                uyari = f" {tanim}: {miktar:.2f} {birim} (max {max_k*alan_m2:.2f}) - Yuksek"
                self.uyari_listesi.append(uyari)
                item = QListWidgetItem(uyari)
                item.setForeground(QColor("#FF4444"))
                self.uyari_listesi_widget.addItem(item)
        self.uyari_group.setVisible(bool(self.uyari_listesi))
        if self.uyari_listesi:
            logger.warning(f"Anormallik tespiti: {len(self.uyari_listesi)} uyari")


    def _kaba_yapi_hesapla(self):
        """Kaba Yapı sekmesinden girilen verilerle keşif hesabı yap.

        Neyi çözüyoruz?
        Müteahhit, DXF olmadan yalnızca inşaat alanı ve kat sayısını
        girerek yaklaşık beton/kalıp/demir miktarını öğrenir.

        Hesap Mantığı (Betonarme Çerçeve için tipik katsayılar):
            - Beton: 0.35 m³ / m² (kolon+kiriş+döşeme ortalama)
            - Kalıp: 2.20 m² / m² (döşeme + perde + kolon yan)
            - Demir: 95 kg / m² (TS 500 ortalama)
            - Temel: 0.50 m³ / m² (radye/tekil temel ortalama)
            """
        alan = self.kaba_alan_spin.value()
        n_kat = self.kaba_kat_sayi_spin.value()
        sistem = self.kaba_sistem_combo.currentText()

        if alan <= 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen geçerli bir inşaat alanı girin!")
            return

        toplam_alan = alan * n_kat

        # Yapı sistemine göre katsayılar
        katsayilar = {
            "Betonarme Çerçeve": {"beton": 0.35, "kalip": 2.20, "demir": 95, "temel_beton": 0.50},
            "Betonarme Perde+Çerçeve": {"beton": 0.42, "kalip": 2.80, "demir": 120, "temel_beton": 0.60},
            "Yığma Tuğla": {"beton": 0.10, "kalip": 0.50, "demir": 20, "temel_beton": 0.30},
            "Çelik Konstrüksiyon": {"beton": 0.15, "kalip": 0.80, "demir": 50, "temel_beton": 0.40},
        }
        k = katsayilar.get(sistem, katsayilar["Betonarme Çerçeve"])

        satirlar = [
            ("Beton (Döşeme+Kolon+Kiriş)", round(toplam_alan * k["beton"], 2), "m³"),
            ("Kalıp Alanı", round(toplam_alan * k["kalip"], 2), "m²"),
            ("Demir (Donatı)", round(toplam_alan * k["demir"], 2), "kg"),
            ("Temel Beton", round(alan * k["temel_beton"], 2), "m³"),
            ("Hazır Beton (Pompajlı)", round(toplam_alan * k["beton"] + alan * k["temel_beton"], 2), "m³"),
            ("Toplam İnşaat Alanı", round(toplam_alan, 2), "m²"),
        ]

        self.kaba_yapi_table.setRowCount(0)
        for tanim, miktar, birim in satirlar:
            row = self.kaba_yapi_table.rowCount()
            self.kaba_yapi_table.insertRow(row)
            self.kaba_yapi_table.setItem(row, 0, QTableWidgetItem(tanim))
            item_miktar = QTableWidgetItem(f"{miktar:,.2f}")
            item_miktar.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.kaba_yapi_table.setItem(row, 1, item_miktar)
            self.kaba_yapi_table.setItem(row, 2, QTableWidgetItem(birim))

        # Son satırı vurgula
        son_row = self.kaba_yapi_table.rowCount() - 1
        for col in range(3):
            if self.kaba_yapi_table.item(son_row, col):
                self.kaba_yapi_table.item(son_row, col).setBackground(QColor("#1a3a1a"))
                self.kaba_yapi_table.item(son_row, col).setForeground(QColor("#4CAF50"))

        logger.info(
            f"Kaba yapı hesabı: {alan:.0f} m² × {n_kat} kat = {toplam_alan:.0f} m² — {sistem}"
        )

                        # ═══════════════════════════════════════════════════════════════════════════
                        # ÖZELLİK 6 — Tedarikçi Entegrasyonu
                        # ═══════════════════════════════════════════════════════════════════════════

    def _tedarikci_gonder(self):
        """Malzeme listesini tedarikci teklif formatina cevir ve kullaniciya sun."""
        if not self.malzeme_ihtiyaclari and not self.imalat_listesi:
            QMessageBox.information(self, "Bilgi",
                "Tedarikci teklif listesi bos.\nOnce DXF yukleyip hesaplama yapin.")
            return

        from datetime import date
        bugun = date.today().strftime("%d.%m.%Y")
        satirlar = [
            "=" * 60, " TEDARIKCI TEKLIF TALEP FORMU", "=" * 60,
            f"Tarih: {bugun}", "Proje: (Proje adini buraya yazin)",
            "Hazirlayan: Insaat Metraj Pro", "",
            "Sayın Tedarikci, asagidaki malzemeler icin fiyat teklifi talep edilmektedir.", "",
            "{:<5} {:<35} {:>10} {:<12} Fiyat".format("Sira", "Malzeme Adi", "Miktar", "Birim"),
            "-" * 80,
        ]
        sira = 1
        if self.malzeme_ihtiyaclari:
            for malzeme, detay in self.malzeme_ihtiyaclari.items():
                if isinstance(detay, dict):
                    miktar = detay.get("paket_sayisi", detay.get("toplam", 0))
                    birim = detay.get("paket_turu", "Adet")
                else:
                    miktar = detay
                    birim = "Adet"
                satirlar.append(f"{sira:<5} {malzeme:<35} {miktar:>10.0f} {birim:<12} __________ TL")
                sira += 1
        elif self.imalat_listesi:
            for kalem in self.imalat_listesi:
                tanim = kalem.get("tanim", "")
                miktar = kalem.get("miktar", 0)
                birim = kalem.get("birim", "m2")
                satirlar.append(f"{sira:<5} {tanim:<35} {miktar:>10.2f} {birim:<12} __________ TL")
                sira += 1

        satirlar += [
            "-" * 80, "", "Teslimat Adresi: (Santiye adresi)",
            "Teslimat Tarihi: (Teslim tarihi)", "Odeme: (30 gun vadeli / Nakit)",
            "", "Teklifinizi bekliyoruz.", "Saygilarimizla,", "", "=" * 60,
        ]
        metin = "\n".join(satirlar)

        msg = QMessageBox(self)
        msg.setWindowTitle("Tedarikci Teklif Formu")
        msg.setText(f"{sira - 1} kalem malzeme teklif formuna aktarildi.")
        msg.setDetailedText(metin)
        btn_kopyala = msg.addButton("Panoya Kopyala", QMessageBox.ButtonRole.AcceptRole)
        btn_kaydet = msg.addButton("TXT Kaydet", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("Kapat", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == btn_kopyala:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(metin)
            QMessageBox.information(self, "Kopyalandi", "Teklif formu panoya kopyalandi.")
        elif clicked == btn_kaydet:
            path, _ = QFileDialog.getSaveFileName(
                self, "Teklif Formunu Kaydet", "tedarikci_teklif.txt", "Metin (*.txt)"
            )
            if path:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(metin)
                    QMessageBox.information(self, "Kaydedildi", f"Dosya kaydedildi:\n{path}")
                except Exception as e:
                    QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{e}")


    def _lisp_araclari_tab_olustur(self) -> QWidget:
        """LISP Araçları sekmesi içeriğini oluşturur ve QWidget döndürür."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # ── Komut türü seçimi ────────────────────────────────────────────────
        tur_form = QHBoxLayout()
        tur_label = QLabel("LISP Komut Türü:")
        tur_label.setStyleSheet("color: #ce93d8; font-weight: bold;")
        tur_form.addWidget(tur_label)

        self._lisp_tur_combo = QComboBox()
        self._lisp_tur_combo.setStyleSheet(
            "background: #2a2a3a; color: white; border: 1px solid #666; padding: 4px;"
        )
        self._lisp_tur_combo.addItem("Duvar Alanı (Net)", "duvar_alan")
        self._lisp_tur_combo.addItem("Oda Bazlı Alan", "oda_alan")
        self._lisp_tur_combo.addItem("Süpürgelik Uzunluğu", "supurgelik")
        self._lisp_tur_combo.addItem("Kolon Beton Hacmi", "kolon_hacim")
        self._lisp_tur_combo.addItem("Kiriş Beton Hacmi", "kiris_hacim")
        self._lisp_tur_combo.addItem("Kalıp Alanı", "kalip_alan")
        self._lisp_tur_combo.setToolTip("Çalıştırılacak LISP komutunun türünü seçin")
        tur_form.addWidget(self._lisp_tur_combo, 1)
        layout.addLayout(tur_form)

        # ── Kat yüksekliği (opsiyonel — kolon/kiriş hesapları için) ─────────
        kat_form = QHBoxLayout()
        kat_label = QLabel("Kat Yüksekliği (m):")
        kat_label.setStyleSheet("color: #aaa;")
        kat_form.addWidget(kat_label)

        self._lisp_kat_yuk_spin = QDoubleSpinBox()
        self._lisp_kat_yuk_spin.setRange(1.0, 10.0)
        self._lisp_kat_yuk_spin.setValue(2.80)
        self._lisp_kat_yuk_spin.setSingleStep(0.05)
        self._lisp_kat_yuk_spin.setDecimals(2)
        self._lisp_kat_yuk_spin.setStyleSheet(
            "background: #2a2a3a; color: white; border: 1px solid #666; padding: 4px;"
        )
        self._lisp_kat_yuk_spin.setToolTip(
            "Kolon/Kiriş hacim hesabı için kat yüksekliği (m).\n"
            "Diğer komut türlerinde bu değer dikkate alınmaz."
        )
        kat_form.addWidget(self._lisp_kat_yuk_spin)
        kat_form.addStretch()
        layout.addLayout(kat_form)

        # ── Aksiyon butonları ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        btn_calistir = QPushButton("LISP Komutunu Çalıştır")
        btn_calistir.setStyleSheet(
            "background: #1565c0; color: white; font-weight: bold; "
            "padding: 8px 12px; border: 1px solid #1976d2; border-radius: 4px;"
        )
        btn_calistir.setToolTip(
            "Seçili LISP komutunu AutoCAD'de çalıştırır.\n"
            "AutoCAD açık ve bağlı olmalıdır."
        )

        def _lisp_calistir_clicked():
            tur = self._lisp_tur_combo.currentData()
            kat_yuk = self._lisp_kat_yuk_spin.value()
            if not AUTOCAD_AVAILABLE:
                QMessageBox.warning(
                    self, "AutoCAD Bağlantısı Yok",
                    "AutoCAD COM bağlantısı mevcut değil.\n"
                    "autocad_connector modülü yüklenemedi."
                )
                return
            if not self.acad_connector or not self.acad_connector.bagli:
                QMessageBox.warning(
                    self, "Bağlantı Yok",
                    "AutoCAD'e bağlı değilsiniz.\n"
                    "Önce 'AutoCAD'e Bağlan' butonuna tıklayın."
                )
                return
            try:
                self.acad_connector.lisp_calistir(tur, {"kat_yuksekligi": kat_yuk})
            except Exception as e:
                QMessageBox.critical(self, "LISP Hatası", f"LISP komutu çalıştırılamadı:\n{e}")

        btn_calistir.clicked.connect(_lisp_calistir_clicked)
        btn_row.addWidget(btn_calistir)

        btn_oku = QPushButton("Sonucu Oku")
        btn_oku.setStyleSheet(
            "background: #2e7d32; color: white; font-weight: bold; "
            "padding: 8px 12px; border: 1px solid #388e3c; border-radius: 4px;"
        )
        btn_oku.setToolTip(
            "AutoCAD LISP komutunun yazdığı sonucu okur.\n"
            "(%TEMP%\\imp_metraj.txt veya doğrudan COM)"
        )
        btn_oku.clicked.connect(self._lisp_sonuc_oku)
        btn_row.addWidget(btn_oku)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Ayraç ────────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #555; background: #555; margin: 4px 0;")
        layout.addWidget(sep)

        # ── Sonuç alanı ──────────────────────────────────────────────────────
        sonuc_baslik = QLabel("Sonuç:")
        sonuc_baslik.setStyleSheet("color: #ce93d8; font-weight: bold;")
        layout.addWidget(sonuc_baslik)

        self._lisp_sonuc_label = QLabel("Henüz bir LISP komutu çalıştırılmadı.")
        self._lisp_sonuc_label.setWordWrap(True)
        self._lisp_sonuc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._lisp_sonuc_label.setMinimumHeight(120)
        self._lisp_sonuc_label.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 10pt; "
            "background: #1e1e2e; padding: 10px; border-radius: 4px; "
            "color: #aaa; border: 1px solid #444;"
        )
        layout.addWidget(self._lisp_sonuc_label, 1)

        # ── Metraya aktar butonu ──────────────────────────────────────────────
        self._btn_lisp_metraya = QPushButton("Metraya Aktar")
        self._btn_lisp_metraya.setEnabled(False)
        self._btn_lisp_metraya.setStyleSheet(
            "background: #e65100; color: white; font-weight: bold; "
            "padding: 8px 14px; border: 1px solid #f4511e; border-radius: 4px;"
        )
        self._btn_lisp_metraya.setToolTip(
            "Okunan LISP sonucunu metraj cetveline iş kalemi olarak ekler.\n"
            "Önce 'Sonucu Oku' işlemi yapılmış olmalıdır."
        )
        self._btn_lisp_metraya.clicked.connect(self._lisp_metraya_aktar)
        layout.addWidget(self._btn_lisp_metraya)

        return widget


    def _lisp_sonuc_oku(self) -> None:
        """%TEMP%/imp_metraj.txt dosyasindan LISP sonucunu okur ve gosterir."""
        if AUTOCAD_AVAILABLE and self.acad_connector and self.acad_connector.bagli:
            sonuc = self.acad_connector.lisp_sonuc_oku()
        else:
            import os
            import json as _json
            yol = os.path.join(os.environ.get("TEMP", ""), "imp_metraj.txt")
            if not os.path.exists(yol):
                QMessageBox.warning(self, "Sonuc Yok",
                    "imp_metraj.txt bulunamadi.\nOnce bir LISP komutu calistirin.")
                return
            try:
                with open(yol, encoding="utf-8") as f:
                    sonuc = _json.loads(f.read())
            except Exception as e:
                sonuc = {"hata": str(e)}

        self._lisp_son_sonuc = sonuc
        self._lisp_sonuc_goster(sonuc)
        self._btn_lisp_metraya.setEnabled("hata" not in sonuc)


    def _lisp_sonuc_goster(self, sonuc: Dict) -> None:
        """LISP sonucunu kullaniciya okunabilir sekilde gosterir."""
        if "hata" in sonuc:
            self._lisp_sonuc_label.setText(f" Hata: {sonuc['hata']}")
            self._lisp_sonuc_label.setStyleSheet(
                "font-family: Consolas, monospace; font-size: 10pt; "
                "background: #FFEBEE; padding: 10px; border-radius: 4px; color: #B71C1C;"
            )
            return

        tur = sonuc.get("tur", "bilinmiyor")
        satirlar = [f" Tur: {tur}"]

        if tur == "duvar_alan":
            satirlar += [
                f" Brut Alan : {sonuc.get('brut', 0):.3f} m2",
                f" Menha : {sonuc.get('bosluk', 0):.3f} m2",
                f" NET Alan : {sonuc.get('net', 0):.3f} m2",
            ]
        elif tur == "oda_alan":
            odalar = sonuc.get("odalar", [])
            satirlar.append(f" Oda Sayisi : {len(odalar)}")
            for oda in odalar[:10]:
                satirlar.append(f" * {oda.get('isim','?')}: {oda.get('alan',0):.2f} m2")
            if len(odalar) > 10:
                satirlar.append(f" ... +{len(odalar)-10} oda daha")
            satirlar.append(f" TOPLAM : {sonuc.get('toplam', 0):.3f} m2")
        elif tur == "supurgelik":
            satirlar += [
                f" Brut Cevre : {sonuc.get('brut', 0):.3f} m",
                f" Kapi Menha : {sonuc.get('kapi_menha', 0):.3f} m",
                f" NET Uzunluk: {sonuc.get('net', 0):.3f} m",
            ]
        elif tur == "kolon_hacim":
            satirlar += [
                f" Kolon Sayisi : {sonuc.get('kolon_sayisi', 0)}",
                f" Kat Yuk. : {sonuc.get('kat_yuksekligi', 0):.2f} m",
                f" TOPLAM HACIM: {sonuc.get('toplam_hacim', 0):.3f} m3",
            ]
        elif tur == "kiris_hacim":
            satirlar += [
                f" Toplam Uzunluk : {sonuc.get('toplam_uzunluk', 0):.3f} m",
                f" Kesit bxh : {sonuc.get('kiris_b', 0):.3f}x{sonuc.get('kiris_h', 0):.3f} m",
                f" TOPLAM HACIM : {sonuc.get('toplam_hacim', 0):.3f} m3",
            ]
        elif tur == "kalip_alan":
            satirlar += [
                f" Kolon Kalip : {sonuc.get('kolon_kalip', 0):.3f} m2",
                f" Kiris Kalip : {sonuc.get('kiris_kalip', 0):.3f} m2",
                f" Doseme Kalip : {sonuc.get('doseme_kalip', 0):.3f} m2",
                f" TOPLAM KALIP : {sonuc.get('toplam', 0):.3f} m2",
            ]
        else:
            for k, v in sonuc.items():
                if k not in ("tur", "aciklama", "birim"):
                    satirlar.append(f" {k}: {v}")

        if sonuc.get("aciklama"):
            satirlar.append(f"INFO: {sonuc['aciklama']}")

        self._lisp_sonuc_label.setText("\n".join(satirlar))
        self._lisp_sonuc_label.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 10pt; "
            "background: #E8F5E9; padding: 10px; border-radius: 4px; color: #1B5E20;"
        )


    def _lisp_metraya_aktar(self) -> None:
        """LISP sonucunu metraj cetveline kalem olarak ekler."""
        if not self._lisp_son_sonuc or "hata" in self._lisp_son_sonuc:
            QMessageBox.warning(self, "Sonuc Yok",
                "Once bir LISP komutu calistirin ve sonucu okuyun.")
            return

        sonuc = self._lisp_son_sonuc
        tur = sonuc.get("tur", "lisp")
        birim = sonuc.get("birim", "m\u00b2")
        tur_map = {
            "duvar_alan": (sonuc.get("net", 0), "Net Duvar Alani (LISP)", "m\u00b2"),
            "oda_alan": (sonuc.get("toplam", 0), "Oda Bazli Net Alan (LISP)", "m\u00b2"),
            "supurgelik": (sonuc.get("net", 0), "Supurgelik Uzunlugu (LISP)", "m"),
            "kolon_hacim": (sonuc.get("toplam_hacim", 0), "Kolon Beton Hacmi (LISP)", "m\u00b3"),
            "kiris_hacim": (sonuc.get("toplam_hacim", 0), "Kiris Beton Hacmi (LISP)", "m\u00b3"),
            "kalip_alan": (sonuc.get("toplam", 0), "Kalip Alani (LISP)", "m\u00b2"),
        }
        miktar, tanim, birim = tur_map.get(tur, (0, f"LISP: {tur}", birim))

        if miktar <= 0:
            QMessageBox.warning(self, "Gecersiz Deger",
                "Miktar sifir veya negatif, metraj cetveline eklenmedi.")
            return

        pw = self.parent()
        if pw is None or not hasattr(pw, 'current_project_id'):
            QMessageBox.warning(self, "Uyari",
                f"Ana pencere baglantisi kurulamadi!\nHesaplanan: {miktar:.3f} {birim}")
            return
        if not pw.current_project_id:
            QMessageBox.warning(self, "Proje Secilmedi",
                f"Metraya aktarmak icin once ana pencerede bir proje secin!\n{miktar:.3f} {birim}")
            return

        try:
            pw.db.add_metraj_kalem(
                proje_id=pw.current_project_id, tanim=tanim,
                miktar=miktar, birim=birim,
                birim_fiyat=0, poz_no="", kategori="LISP Metraj",
            )
            QMessageBox.information(self, "Eklendi",
                f"Metraj cetveline eklendi:\n{tanim}\n{miktar:.3f} {birim}")
        except Exception as e:
            logger.error(f"LISP metraya aktar hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Metraj cetveline eklenemedi:\n{e}")


class DXFKatmanSecimDialog(QDialog):
    """DXF katman secim dialog'u - Minha (kapi/pencere) ve Oda/Kat isimleri destegi"""

    def __init__(self, parent, katmanlar: List[str],
    varsayilan_kiris: List[str], varsayilan_duvar: List[str],
    varsayilan_minha: List[str] = None,
    text_katmanlari: List[str] = None,
    varsayilan_oda: List[str] = None,
    varsayilan_kat: List[str] = None,
    varsayilan_m2: List[str] = None,
    varsayilan_kolon: List[str] = None):
        super().__init__(parent)
        self.setWindowTitle("DXF Katman Secimi - Proje Kimligi")
        self.setMinimumSize(1000, 850)

        self.katmanlar = katmanlar
        self.varsayilan_kiris = varsayilan_kiris or []
        self.varsayilan_kolon = varsayilan_kolon or []
        self.varsayilan_duvar = varsayilan_duvar
        self.varsayilan_minha = varsayilan_minha or []
        self.text_katmanlari = text_katmanlari or []
        self.varsayilan_oda = varsayilan_oda or []
        self.varsayilan_kat = varsayilan_kat or []
        self.varsayilan_m2 = varsayilan_m2 or []
        self.secilen_duvar_cinsi = "Tuğla" # Varsayılan duvar cinsi

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
        self.birim_combo.setCurrentIndex(0) # cm varsayilan
        birim_layout.addWidget(QLabel("DXF dosyasinin birimi:"))
        birim_layout.addWidget(self.birim_combo)
        birim_layout.addStretch()
        birim_group.setLayout(birim_layout)
        ust_ayarlar_layout.addWidget(birim_group)

        # DUVAR CİNSİ SEÇİMİ (YENİ)
        duvar_cinsi_group = QGroupBox(" Duvar Malzeme Cinsi")
        duvar_cinsi_group.setStyleSheet("QGroupBox { border: 2px solid #e74c3c; font-weight: bold; }")
        duvar_cinsi_layout = QVBoxLayout()

        duvar_cinsi_aciklama = QLabel("Nalbur siparisinde kullanilacak malzeme:")
        duvar_cinsi_aciklama.setStyleSheet("color: #e74c3c; font-size: 10pt;")
        duvar_cinsi_layout.addWidget(duvar_cinsi_aciklama)

        self.duvar_cinsi_combo = QComboBox()
        self.duvar_cinsi_combo.addItems(DUVAR_CINSLERI)
        self.duvar_cinsi_combo.setCurrentIndex(0) # Tuğla varsayilan
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

        # Ana icerik - yatay bolunmus (ust satir: Duvar, Kiris, Kolon, Minha)
        content_layout1 = QHBoxLayout()

        # Duvar katmanlari
        duvar_group = QGroupBox(f"Duvar ({len(self.varsayilan_duvar)})")
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

        # Kiris katmanlari
        kiris_group = QGroupBox(f"Kiris ({len(self.varsayilan_kiris)})")
        kiris_group.setStyleSheet("QGroupBox { border: 2px solid #e67e22; }")
        kiris_layout = QVBoxLayout()
        self.kiris_list = QListWidget()
        self.kiris_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for katman in self.katmanlar:
            item = QListWidgetItem(katman)
            self.kiris_list.addItem(item)
            if katman in self.varsayilan_kiris:
                item.setSelected(True)
        kiris_layout.addWidget(self.kiris_list)
        kiris_group.setLayout(kiris_layout)
        content_layout1.addWidget(kiris_group)

        # Kolon katmanlari
        kolon_group = QGroupBox(f"Kolon ({len(self.varsayilan_kolon)})")
        kolon_group.setStyleSheet("QGroupBox { border: 2px solid #e74c3c; }")
        kolon_layout = QVBoxLayout()
        self.kolon_list = QListWidget()
        self.kolon_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for katman in self.katmanlar:
            item = QListWidgetItem(katman)
            self.kolon_list.addItem(item)
            if katman in self.varsayilan_kolon:
                item.setSelected(True)
        kolon_layout.addWidget(self.kolon_list)
        kolon_group.setLayout(kolon_layout)
        content_layout1.addWidget(kolon_group)

        # Minha (Kapi/Pencere) katmanlari
        minha_group = QGroupBox(f"Minha ({len(self.varsayilan_minha)})")
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
        kimlik_label = QLabel(" PROJE KIMLIGI (Oda ve Kat Isimleri)")
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
            " Duvar: Duvar cizgileri | Minha: Kapi/Pencere acikliklari\n"
            " Oda Ismi: Salon, Mutfak vs. (Sari) | Kat Ismi: Zemin Kat, 1. Kat vs. (Mavi - Buyuk)\n"
            " M2 Yazilari: Alan metrekare degerleri (Yesil) - Sap hesabi icin kullanilir\n"
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
        """Secilen kiris katmanlarini dondur"""
        return [item.text() for item in self.kiris_list.selectedItems()]

    def get_selected_kolon(self) -> List[str]:
        """Secilen kolon katmanlarini dondur"""
        return [item.text() for item in self.kolon_list.selectedItems()]

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
