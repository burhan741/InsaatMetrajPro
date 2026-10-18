"""
Akıllı Metraj Analizi Penceresi
"""

import copy
import dataclasses
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
    QTabWidget, QRadioButton, QButtonGroup, QScrollArea, QInputDialog, QToolBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QAction
from datetime import datetime

import webbrowser
import tempfile

from app.core.kesim_besleme import demirlerden_kesim_parcalari_uret
from app.ui.demir_hesaplama_window import DEMIR_BIRIM_AGIRLIK as _KESIM_DESTEKLENEN_CAPLAR

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

try:
    from app.core import metraj_proje_kayit as proje_kayit  # Rev-168
except Exception:
    proje_kayit = None
try:
    from app.core.excel_bicim import beton_kalip_sutunlari_tek_hane  # Rev-166
except Exception:
    def beton_kalip_sutunlari_tek_hane(ws, ara_satir=40):
        return []

# AutoCAD canlı bağlantı (COM Automation)
try:
    from app.core.autocad_connector import (
        AutoCADConnector, MetrajObjesi, DemirBilgisi, AcadColor,
        aralikli_donati_hesapla,
        temel_kirisi_hesapla, temel_kirisi_secim_degerlendir, temel_kirisi_secimi_ayir,
        radye_hesapla, cizim_uzunlugu_metreye_cevir, perde_hesapla,
        perde_secimi_degerlendir, perde_alan_supheli_mi, KatYukseklikAyari, BETON_ESASLARI,
        perde_zincir_uc_dus,
        doseme_hesapla, doseme_poligon_degerlendir, dikdortgen_koseleri, nokta_poligon_icinde_mi,
        bosluk_degerlendir, kiris_hesapla, KIRIS_TIPLERI,
        kiris_secim_degerlendir, kiris_mukerrer_bul, KIRIS_RENKLERI, kenar_eksik_secim_uyarisi,
        kolon_perde_hesapla, eleman_tipi_belirle, eleman_ad_normalize,
        ELEMAN_TIPLERI, ELEMAN_RENKLERI, OKUNAMAYAN_RENK, hakim_doseme_kalinligi_cm,
        SACAK_TIPI, SACAK_HALKA, SACAK_SERIT, SACAK_RENK, sacak_mi, sacak_halka_degerlendir,
        sacak_serit_degerlendir, sacak_mukerrer_bul,
    )
    AUTOCAD_AVAILABLE = True
except Exception:
    AUTOCAD_AVAILABLE = False
    AutoCADConnector = None
    MetrajObjesi = None
    DemirBilgisi = None
    aralikli_donati_hesapla = None
    temel_kirisi_hesapla = None
    temel_kirisi_secim_degerlendir = None
    temel_kirisi_secimi_ayir = None
    radye_hesapla = None
    cizim_uzunlugu_metreye_cevir = None
    perde_hesapla = None
    perde_secimi_degerlendir = None
    perde_alan_supheli_mi = None
    perde_zincir_uc_dus = None
    KatYukseklikAyari = None
    doseme_hesapla = None
    doseme_poligon_degerlendir = None
    dikdortgen_koseleri = None
    nokta_poligon_icinde_mi = None
    bosluk_degerlendir = None
    kiris_hesapla = None
    KIRIS_TIPLERI = ("İç", "Kenar")
    kiris_secim_degerlendir = None
    kiris_mukerrer_bul = None
    kenar_eksik_secim_uyarisi = None
    KIRIS_RENKLERI = {}
    BETON_ESASLARI = {"tam": "Tam kat", "net": "Net (kat − döşeme)"}
    kolon_perde_hesapla = None
    eleman_tipi_belirle = None
    ELEMAN_TIPLERI = ("Kolon", "Perde")
    ELEMAN_RENKLERI = {"Kolon": 3, "Perde": 4}
    OKUNAMAYAN_RENK = 1
    hakim_doseme_kalinligi_cm = None
    SACAK_TIPI, SACAK_HALKA, SACAK_SERIT, SACAK_RENK = "Saçak", "Halka", "Şerit", 40
    sacak_halka_degerlendir = sacak_serit_degerlendir = sacak_mukerrer_bul = None

    def sacak_mi(satir):
        return (satir or {}).get("tip") == "Saçak"

    def eleman_ad_normalize(ad):
        return "".join(str(ad or "").split()).upper()

# Kat bazlı beton + kalıp özeti (saf, bağımlılıksız)
try:
    from app.core.kat_ozeti import kat_ozeti_olustur, ozet_tablo_satirlari, TEMEL_KAT
except Exception:
    kat_ozeti_olustur = None
    ozet_tablo_satirlari = None
    TEMEL_KAT = "Temel"

# Rev-152: Merdiven (plak merdiven) beton + kalıp (saf, bağımlılıksız)
try:
    from app.core.merdiven_hesap import (
        merdiven_kol_hesapla, merdiven_sahanlik_hesapla, merdiven_toplam_kalip, kalip_esas_metni,
        MERDIVEN_TIP_KOL, MERDIVEN_TIP_SAHANLIK,
    )
except Exception:
    merdiven_kol_hesapla = None
    merdiven_sahanlik_hesapla = None
    merdiven_toplam_kalip = None
    kalip_esas_metni = None
    MERDIVEN_TIP_KOL, MERDIVEN_TIP_SAHANLIK = "Kol", "Sahanlık"

# Rev-153: Temel kirişi (SBH) demir — filiz + tevzi (tip bazlı parametre)
try:
    from app.core.temel_kirisi_demir import (
        temel_kirisi_demir_hesapla, temel_kirisi_kesim_parcalari, cap_bazli_topla,
        sbh_parametre_tamamla, sbh_parametre_dogrula, SBH_DEMIR_ALANLARI,
    )
except Exception:
    temel_kirisi_demir_hesapla = None
    temel_kirisi_kesim_parcalari = None
    cap_bazli_topla = None
    sbh_parametre_tamamla = None
    sbh_parametre_dogrula = None
    SBH_DEMIR_ALANLARI = []

# Rev-157: Radye kayıt listesi + Excel "Radye" sayfası (saf)
try:
    from app.core.radye_rapor import radye_kaydi_hesapla, radye_toplamlari, radye_sayfasi_yaz
except Exception:
    radye_kaydi_hesapla = None
    radye_toplamlari = None
    radye_sayfasi_yaz = None

# Kalıcı ayar dosyası (data/autocad_ayarlari.json) — merdiven kalıp esası burada saklanır
try:
    from app.core.autocad_connector import autocad_ayari_oku, autocad_ayari_yaz
except Exception:
    def autocad_ayari_oku(anahtar, varsayilan=None):
        return varsayilan

    def autocad_ayari_yaz(anahtar, deger):
        return None

logger = logging.getLogger(__name__)

def tek_hane(deger, binlik: bool = False) -> str:
    """Rev-165: beton / kalıp / sipariş GÖRÜNTÜSÜ tek ondalık, YARIM YUKARI (1.25 -> 1.3).
    Python'un format'ı yarımı çifte yuvarlar (1.25 -> 1.2) — sahada / Excel'de beklenen bu değil.
    Hesap ve kayıt tam hassasiyette kalır; sadece metin."""
    from decimal import Decimal, ROUND_HALF_UP
    try:
        d = Decimal(repr(float(deger))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    except (TypeError, ValueError, ArithmeticError):
        return str(deger)
    return f"{d:,}" if binlik else f"{d}"



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


class CapBazliTonajDialog(QDialog):
    """Toplanan demirleri çapa (mm) göre gruplayıp toplam boy/ağırlık/tonaj gösterir.

    Neyi çözüyoruz: Sahada demir siparişi verirken "kaç ton Ø12, kaç ton Ø16
    lazım" sorusuna tek bakışta yanıt — tüm katlardaki demirler çapa göre
    tek tabloda toplanır, TS 708 birim ağırlıklarıyla (DEMIR_BIRIM_AGIRLIK)
    kg ve tona çevrilir.
    Nasıl test ederiz: scratchpad/test_cap_bazli_tonaj.py — bilinen adet/boy
    değerleriyle sahte DemirBilgisi listesi üretilip toplamların elle
    hesaplanan değerlerle (adet, boy_m, agirlik_kg, ton, yüzde) eşleştiği
    doğrulanır; ayrıca boş liste ve tek-çap liste uç durumları kontrol edilir.
    """

    def __init__(self, demirler, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Çap Bazlı Demir Tonajı")
        self.setMinimumSize(560, 420)
        self.setStyleSheet(
        "QDialog { background: #252535; color: white; }"
        "QTableWidget { background: #1e1e2e; color: white; gridline-color: #444; }"
        "QHeaderView::section { background: #333345; color: white; font-weight: bold; padding: 4px; border: 1px solid #555; }"
        "QPushButton { background: #444; color: white; padding: 6px 14px; border: 1px solid #666; border-radius: 4px; }"
        "QPushButton:hover { background: #555; }"
        )
        self._ozet = self._hesapla(demirler)

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        lbl = QLabel(f" Toplam {len(demirler)} demir kalemi, çapa göre gruplandı:")
        lbl.setStyleSheet("color: #aaa; font-size: 9pt;")
        lay.addWidget(lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
        ["Çap (mm)", "Adet", "Toplam Boy (m)", "Birim Ağ. (kg/m)",
         "Toplam Ağırlık (kg)", "Toplam Ağırlık (ton)"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table)

        genel_lbl = QLabel()
        genel_lbl.setStyleSheet("color: #2ecc71; font-size: 11pt; font-weight: bold; padding: 6px;")
        g = self._ozet["genel"]
        genel_lbl.setText(
        f" GENEL TOPLAM: {g['adet']:,} adet | {g['boy_m']:,.2f} m | "
        f"{g['agirlik_kg']:,.1f} kg | {g['agirlik_kg']/1000:,.3f} ton"
        )
        lay.addWidget(genel_lbl)
        self._doldur()

        btn_bar = QHBoxLayout()
        btn_excel = QPushButton(" Excel'e Aktar")
        btn_excel.setStyleSheet(
        "QPushButton { background: #27ae60; color: white; font-weight: bold; padding: 6px 16px; border: 1px solid #2ecc71; border-radius: 4px; }"
        "QPushButton:hover { background: #2ecc71; }"
        )
        btn_excel.clicked.connect(self._excele_aktar)
        btn_bar.addWidget(btn_excel)
        btn_kapat = QPushButton("Kapat")
        btn_kapat.clicked.connect(self.accept)
        btn_bar.addWidget(btn_kapat)
        lay.addLayout(btn_bar)

    @staticmethod
    def _hesapla(demirler):
        """Demir listesini çapa göre gruplar. Dönen sözlük: {cap: {...}, "genel": {...}}"""
        cap_ozeti = {}
        for d in demirler:
            cap = d.cap
            if cap not in cap_ozeti:
                cap_ozeti[cap] = {"adet": 0, "boy_m": 0.0, "agirlik_kg": 0.0,
                                   "birim_agirlik": getattr(d, "agirlik_birim", 0.0)}
            cap_ozeti[cap]["adet"] += d.adet
            cap_ozeti[cap]["boy_m"] += d.toplam_boy
            cap_ozeti[cap]["agirlik_kg"] += d.toplam_agirlik
        genel = {
            "adet": sum(v["adet"] for v in cap_ozeti.values()),
            "boy_m": sum(v["boy_m"] for v in cap_ozeti.values()),
            "agirlik_kg": sum(v["agirlik_kg"] for v in cap_ozeti.values()),
        }
        return {"caplar": cap_ozeti, "genel": genel}

    def _doldur(self):
        caplar = sorted(self._ozet["caplar"].keys())
        genel_kg = self._ozet["genel"]["agirlik_kg"] or 1.0
        self.table.setRowCount(len(caplar))
        for row, cap in enumerate(caplar):
            v = self._ozet["caplar"][cap]
            degerler = [
                f"Ø{cap}", f"{v['adet']:,}", f"{v['boy_m']:,.2f}",
                f"{v['birim_agirlik']:.3f}", f"{v['agirlik_kg']:,.2f}",
                f"{v['agirlik_kg']/1000:,.4f}",
            ]
            for col, metin in enumerate(degerler):
                item = QTableWidgetItem(metin)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

    def _excele_aktar(self):
        if not PANDAS_AVAILABLE:
            QMessageBox.warning(self, "Uyarı", "Excel export için pandas gerekli!")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Çap Bazlı Tonaj Kaydet", "Cap_Bazli_Tonaj.xlsx", "Excel Dosyası (*.xlsx)"
        )
        if not file_path:
            return
        try:
            caplar = sorted(self._ozet["caplar"].keys())
            rows = []
            for cap in caplar:
                v = self._ozet["caplar"][cap]
                rows.append({
                    "Çap (mm)": cap, "Adet": v["adet"],
                    "Toplam Boy (m)": round(v["boy_m"], 2),
                    "Birim Ağırlık (kg/m)": v["birim_agirlik"],
                    "Toplam Ağırlık (kg)": round(v["agirlik_kg"], 2),
                    "Toplam Ağırlık (ton)": round(v["agirlik_kg"] / 1000, 4),
                })
            g = self._ozet["genel"]
            rows.append({"Çap (mm)": "TOPLAM", "Adet": g["adet"],
                         "Toplam Boy (m)": round(g["boy_m"], 2),
                         "Toplam Ağırlık (kg)": round(g["agirlik_kg"], 2),
                         "Toplam Ağırlık (ton)": round(g["agirlik_kg"] / 1000, 4)})
            pd.DataFrame(rows).to_excel(file_path, index=False)
            QMessageBox.information(self, "Başarılı", f"Excel'e aktarıldı!\n\n{file_path}")
        except Exception as e:
            logger.error(f"Çap bazlı tonaj Excel export hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Hata:\n{e}")


def _kapatma_sorusu(parent, adet: int, birim: str, hedef: str) -> str:
    """Rev-166: döngü paneli Esc / X ile kapatılırken toplanan veri varsa sorar.
    Dönüş: "evet" (ekle) | "hayir" (ekleme, renkleri geri al) | "vazgec" (pencere açık kalsın)."""
    S = QMessageBox.StandardButton
    cevap = QMessageBox.question(
        parent, "Henüz Eklenmedi",
        f"Toplanan {adet} {birim} henüz {hedef} EKLENMEDİ.\n\n"
        f"Evet: {hedef} ekle\n"
        "Hayır: ekleme, AutoCAD'deki renkleri geri al\n"
        "Vazgeç: pencere açık kalsın",
        S.Yes | S.No | S.Cancel, S.Yes)
    return {S.Yes: "evet", S.No: "hayir"}.get(cevap, "vazgec")


class AralikliDonatiDonguPaneli(QDialog):
    """Ø/aralık formatlı ("Ø14/20 L=500") donatıları TEK TEK, döngüsel
    seçimle toplayan panel — İhale Demir Metrajı, Aşama 3 güncelleme
    (bkz. CLAUDE.md Rev-136, "radye gibi dağınık donatı" senaryosu).

    Neyi çözüyoruz? Kutu seçimiyle toplu okuma, radye gibi dağınık
    donatıda "aynı demiri iki kez sayma / bir demiri atlama" riski
    taşıyor. Bu panel her turda kullanıcıya TEK bir AutoCAD yazısı
    seçtirir ("Demir Seç"), hemen mesafe sorar, objeyi YEŞİLE boyar ve
    listeye ekler — döngü "Bitti" ile kapanana kadar sürer. Aynı yazı
    (aynı handle) tekrar seçilirse UYARIR (mükerrer koruma — bkz. CLAUDE.md
    Rev-134 dersi). "Son Ekleneni Geri Al" son satırı siler ve rengi geri
    alır. "İptal" ile çıkılırsa bu oturumda boyanan TÜM renkler geri alınır
    (hiçbir şey kata eklenmediği için yeşil iz yanıltıcı olmasın).
    Nasıl test ederiz: sahte bir connector (aralikli_donati_tek_obje_sec
    her çağrıda önceden hazırlanmış bir sonuç döndürür) ile "Demir Seç" +
    mesafe girişi + "Son Ekleneni Geri Al" + mükerrer uyarısı senaryoları
    headless PyQt'de doğrulanır (bkz. scratchpad/test_aralikli_donati_ui.py).
    """

    # Bu değer ve üstü girilen mesafe (m) "cm mi girildi?" diye teyit edilir
    MESAFE_CM_SUPHE_M = 50.0
    KOLONLAR = ["Metin", "Çap (mm)", "Aralık (cm)", "Boy (cm)", "Mesafe (m)",
                "Adet", "Toplam Boy (m)", "Toplam Ağırlık (kg)", "Mesafe Kaynağı"]
    # Rev-142: dağılım mesafesi kaynağı
    MOD_OLCU = "AutoCAD ölçüsünden (DIMENSION)"
    MOD_ELLE = "Elle giriş"
    BIRIM_OTOMATIK = "Otomatik (INSUNITS)"
    _COMBO_STIL = (
        "QComboBox { background:#2a2a3a; color:white; border:1px solid #666; padding:4px; }"
        "QComboBox QAbstractItemView { background:#2a2a3a; color:white; }"
    )

    def __init__(self, connector, mevcut_handleler=None, parent=None):
        super().__init__(parent)
        self.connector = connector
        # Bu katta registry'de ZATEN kayıtlı handle'lar (önceki oturumlardan) —
        # kullanıcı bunları tekrar seçerse de mükerrer uyarısı göstermek için.
        self._mevcut_handleler = set(mevcut_handleler or ())
        self._satirlar: List[Dict] = []       # bu oturumda eklenen satırlar
        self._eklenen_handleler: set = set()  # bu oturumda boyanan handle'lar
        self._olcu_birimi: Optional[str] = None  # ölçü döngüsünde seçilen birim
        self._olcu_birim_teyitli = False         # ilk ölçü okuması teyit edildi mi

        self.setWindowTitle("İhale Demir Metrajı — Aralıklı Donatı (Tek Tek Seçim)")
        self.setMinimumSize(840, 460)
        self.setStyleSheet(
        "QDialog { background: #252535; color: white; }"
        "QTableWidget { background: #1e1e2e; color: white; gridline-color: #444; }"
        "QHeaderView::section { background: #333345; color: white; font-weight: bold; padding: 4px; border: 1px solid #555; }"
        "QPushButton { background: #444; color: white; padding: 6px 14px; border: 1px solid #666; border-radius: 4px; }"
        "QPushButton:hover { background: #555; }"
        )

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        bilgi = QLabel(
        " ÖLÇÜDEN modu: 'Demir Seç'e basın; AutoCAD'de donatı yazısını (Ø14/20 l=300) seçip "
        "ENTER, sonra dağılım ölçüsüne (DIMENSION) tıklayıp ENTER. Adet = ölçü ÷ aralık + 1. "
        "Döngü kendiliğinden devam eder; yazı seçiminde boş ENTER ile biter. Ölçü seçiminde "
        "boş ENTER = o demir için mesafeyi elle girersiniz.\n"
        " ELLE modu: her 'Demir Seç'te tek yazı seçilir, mesafe (m) sorulur."
        )
        bilgi.setStyleSheet("color: #d4a017; font-size: 9pt;")
        bilgi.setWordWrap(True)
        lay.addWidget(bilgi)

        mod_bar = QHBoxLayout()
        mod_bar.addWidget(QLabel("Mesafe:"))
        self.mod_combo = QComboBox()
        self.mod_combo.addItems([self.MOD_OLCU, self.MOD_ELLE])
        self.mod_combo.setToolTip(
            "Dağılım mesafesinin nereden alınacağı. Ölçü okunamazsa elle girişe düşülür."
        )
        self.mod_combo.setStyleSheet(self._COMBO_STIL)
        mod_bar.addWidget(self.mod_combo)
        mod_bar.addSpacing(12)
        mod_bar.addWidget(QLabel("Ölçü birimi:"))
        self.birim_combo = QComboBox()
        self.birim_combo.addItems([self.BIRIM_OTOMATIK, "cm", "mm", "m"])
        self.birim_combo.setToolTip(
            "Ölçü değeri bu birimde okunur ve metreye çevrilir (400 cm → 4 m). "
            "Otomatik = AutoCAD INSUNITS, tanımsızsa cm. Oturumdaki ilk ölçü ayrıca teyit edilir."
        )
        self.birim_combo.setStyleSheet(self._COMBO_STIL)
        mod_bar.addWidget(self.birim_combo)
        mod_bar.addStretch()
        self.mod_combo.currentTextChanged.connect(
            lambda t: self.birim_combo.setEnabled(t == self.MOD_OLCU))
        lay.addLayout(mod_bar)

        ust_btn_bar = QHBoxLayout()
        self.btn_sec = QPushButton(" Demir Seç (AutoCAD'e Geç)")
        self.btn_sec.setStyleSheet(
        "QPushButton { background: #b7950b; color: white; font-weight: bold; padding: 6px 16px; border: 1px solid #d4ac0d; border-radius: 4px; }"
        "QPushButton:hover { background: #d4ac0d; }"
        )
        self.btn_sec.clicked.connect(self._demir_sec)
        ust_btn_bar.addWidget(self.btn_sec)

        self.btn_geri_al = QPushButton(" Son Ekleneni Geri Al")
        self.btn_geri_al.clicked.connect(self._son_ekleneni_geri_al)
        self.btn_geri_al.setEnabled(False)
        ust_btn_bar.addWidget(self.btn_geri_al)
        lay.addLayout(ust_btn_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.KOLONLAR))
        self.table.setHorizontalHeaderLabels(self.KOLONLAR)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table)

        self.genel_lbl = QLabel()
        self.genel_lbl.setStyleSheet("color: #2ecc71; font-size: 11pt; font-weight: bold; padding: 6px;")
        lay.addWidget(self.genel_lbl)
        self._genel_toplam_guncelle()

        alt_btn_bar = QHBoxLayout()
        btn_bitti = QPushButton(" Bitti — Aktif Kata Ekle")
        btn_bitti.setStyleSheet(
        "QPushButton { background: #27ae60; color: white; font-weight: bold; padding: 6px 16px; border: 1px solid #2ecc71; border-radius: 4px; }"
        "QPushButton:hover { background: #2ecc71; }"
        )
        btn_bitti.clicked.connect(self._bitti)
        alt_btn_bar.addWidget(btn_bitti)
        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self._iptal)
        alt_btn_bar.addWidget(btn_iptal)
        lay.addLayout(alt_btn_bar)

    def _olcu_modu(self) -> bool:
        return self.mod_combo.currentText() == self.MOD_OLCU

    def _komut(self, metin: str) -> None:
        """Ölçü döngüsünde geri bildirim AutoCAD komut satırına (kullanıcı orada)."""
        yaz = getattr(self.connector, "komut_satiri_mesaj", None)
        if yaz is not None:
            try:
                yaz(metin)
            except Exception as e:
                logger.error(f"Aralıklı donatı komut satırı mesajı: {e}", exc_info=True)

    def _demir_sec(self):
        """'Demir Seç' butonu: ölçü modunda döngü (boş ENTER'a kadar), elle modda tek tur."""
        if not self._olcu_modu():
            self._tek_tur(olcu_modu=False)
            return
        birim = self._olcu_birimi_belirle()
        if birim is None:
            return
        self._olcu_birimi = birim
        self._komut("ARALIKLI DONATI: yazı seç + ENTER, sonra ölçü seç + ENTER. Bitirmek için boş ENTER.")
        while True:
            if self._tek_tur(olcu_modu=True) == "bitti":
                break
        self._komut(f"ARALIKLI DONATI: döngü bitti — {len(self._satirlar)} donatı listede.")

    def _olcu_birimi_belirle(self) -> Optional[str]:
        """Ölçü birimini bir kez sorar (varsayılan: combo / INSUNITS / cm)."""
        secim = self.birim_combo.currentText()
        varsayilan = secim
        if secim == self.BIRIM_OTOMATIK:
            varsayilan = None
            oku = getattr(self.connector, "cizim_birimi_oku", None)
            if oku is not None:
                try:
                    varsayilan = oku()
                except Exception as e:
                    logger.error(f"Aralıklı donatı INSUNITS okunamadı: {e}", exc_info=True)
            varsayilan = varsayilan or "cm"
        secenekler = ["cm", "mm", "m"]
        birim, tamam = QInputDialog.getItem(
            self, "Ölçü Birimi",
            "Dağılım ölçüleri (DIMENSION) hangi birimde?\n"
            "(Yanlışsa adetler 10/100 kat hatalı çıkar — ilk ölçüde ayrıca teyit edilir.)",
            secenekler, secenekler.index(varsayilan), False,
        )
        if not tamam:
            return None
        if birim != self._olcu_birimi:
            self._olcu_birim_teyitli = False
        return birim

    def _tek_tur(self, olcu_modu: bool) -> str:
        """Bir donatı: yazı seç -> mesafe (ölçü/elle) -> hesap -> satır + yeşil.

        Returns: "eklendi" | "atlandi" | "bitti" (yazı seçiminde boş ENTER).
        """
        try:
            sonuc = self.connector.aralikli_donati_tek_obje_sec()
        except Exception as e:
            logger.error(f"Aralıklı donatı yazı seçimi hatası: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"Seçim sırasında hata:\n{e}")
            return "bitti"

        durum = sonuc.get("durum")
        if durum == "bos_secim":
            if not olcu_modu:
                QMessageBox.information(
                self, "Bilgi",
                "Hiçbir şey seçilmedi. Tekrar deneyin veya bitirdiyseniz "
                "'Bitti — Aktif Kata Ekle'ye basın."
                )
            return "bitti"
        if durum in ("ilgisiz", "gecersiz"):
            mesaj = (sonuc.get("mesaj", "Geçersiz.") if durum == "gecersiz" else
                     "Seçilen yazı 'Ø.../aralık L=...' formatında değil. "
                     "Lütfen aralıklı donatı yazısını seçin.")
            if olcu_modu:
                self._komut(f"ATLANDI: {mesaj}")
            else:
                QMessageBox.warning(self, "Uyarı", mesaj)
            return "atlandi"

        d = sonuc["ayrisim"]
        handle = d["handle"]

        if handle in self._eklenen_handleler or handle in self._mevcut_handleler:
            tekrar = QMessageBox.question(
            self, "Bu Demir Zaten Eklendi",
            f"'{d.get('temiz_metin', '')}' bu oturumda (veya bu katta) "
            f"zaten eklenmiş. Mesafesini güncellemek için tekrar girmek "
            f"ister misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
            )
            if tekrar != QMessageBox.StandardButton.Yes:
                return "atlandi"
            # Aynı handle'ın satırı aşağıda GÜNCELLENİR, ayrı satır eklenmez.

        olcu_handle = None
        kaynak = "elle"
        mesafe_m = None
        if olcu_modu:
            olcu = self._olcu_ile_mesafe(d)
            if olcu is not None:
                mesafe_m, olcu_handle = olcu
                kaynak = "ölçü"
        if mesafe_m is None:
            mesafe_m = self._elle_mesafe(d)
            if mesafe_m is None:
                return "atlandi"  # iptal - obje boyanmadı, tekrar denenebilir

        # Rev-141 yedek güvenlik: çizimdeki cm değeri metre sanılırsa adet 100 kat şişer
        if mesafe_m >= self.MESAFE_CM_SUPHE_M:
            cevap = QMessageBox.question(
                self, "Mesafe Birimi",
                f"{mesafe_m:g} m — çok büyük.\n"
                f"Değer cm ise doğrusu {mesafe_m / 100:g} m olmalı.\n\n"
                f"{mesafe_m / 100:g} m kullanılsın mı?\n"
                f"(Hayır: {mesafe_m:g} m olarak kalır)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if cevap == QMessageBox.StandardButton.Yes:
                mesafe_m = mesafe_m / 100.0

        hesap = aralikli_donati_hesapla(
        cap=d["cap"], aralik_cm=d["aralik_cm"], boy_cm=d["boy_cm"], mesafe_m=mesafe_m
        )
        if hesap["hata"]:
            if olcu_modu:
                self._komut(f"HATA: {hesap['hata']}")
            else:
                QMessageBox.warning(self, "Hesap Hatası", hesap["hata"])
            return "atlandi"

        satir = dict(d)
        satir["mesafe_m"] = mesafe_m
        satir["mesafe_kaynagi"] = kaynak
        satir["olcu_handle"] = olcu_handle
        satir["adet"] = hesap["adet"]
        satir["boy_m"] = hesap["boy_m"]
        satir["toplam_boy_m"] = hesap["toplam_boy_m"]
        satir["agirlik_birim"] = hesap["agirlik_birim"]
        satir["toplam_agirlik_kg"] = hesap["toplam_agirlik_kg"]

        mevcut_index = next(
        (i for i, s in enumerate(self._satirlar) if s["handle"] == handle), None
        )
        if mevcut_index is not None:
            eski_olcu = self._satirlar[mevcut_index].get("olcu_handle")
            self._satirlar[mevcut_index] = satir
            self._tabloyu_yeniden_doldur()
            if eski_olcu and eski_olcu != olcu_handle:
                self._olcu_rengi_geri_al_kullanilmiyorsa(eski_olcu)
            durum_metni = "GÜNCELLENDİ"
        else:
            self._satirlar.append(satir)
            self._satir_ekle_tabloya(satir)
            self._eklenen_handleler.add(handle)
            self._isaretle(handle, hizli=olcu_modu)
            durum_metni = "EKLENDİ"
        if olcu_handle:
            self._isaretle(olcu_handle, hizli=True)

        self.btn_geri_al.setEnabled(bool(self._satirlar))
        self._genel_toplam_guncelle()
        if olcu_modu:
            self._komut(
                f"{d.get('temiz_metin', '')} {durum_metni}: mesafe {mesafe_m:.2f} m ({kaynak}) -> "
                f"{hesap['adet']} adet, {hesap['toplam_agirlik_kg']:.2f} kg"
            )
        return "eklendi"

    def _isaretle(self, handle: str, hizli: bool) -> None:
        """Yeşil boyama. Ölçü döngüsünde Regen'siz hızlı sürüm (takılma dersi, Rev-137)."""
        try:
            hizli_f = getattr(self.connector, "obje_isaretle_hizli", None) if hizli else None
            if hizli_f is not None:
                hizli_f(handle)
            else:
                self.connector.aralikli_donati_isaretle(handle)
        except Exception as e:
            logger.error(f"Aralıklı donatı işaretleme hatası ({handle}): {e}", exc_info=True)

    def _elle_mesafe(self, d: Dict) -> Optional[float]:
        mesafe_m, tamam = QInputDialog.getDouble(
        self, "Dağılım Mesafesi",
        f"{d.get('temiz_metin', '')}\nDağılım mesafesi (m):",
        4.0, 0.01, 500.0, 2,
        )
        return mesafe_m if tamam else None

    def _olcu_ile_mesafe(self, d: Dict):
        """Ölçü (DIMENSION) seçtirip metre cinsinden mesafe döner.

        Returns: (mesafe_m, olcu_handle) veya None (boş ENTER / okunamadı ->
        çağıran elle girişe düşer).
        """
        r = None
        for _ in range(3):
            self._komut(f"{d.get('temiz_metin', '')}: dağılım ÖLÇÜSÜNÜ seçin + ENTER "
                        f"(boş ENTER = elle gir)")
            try:
                r = self.connector.aralikli_donati_olcu_sec()
            except Exception as e:
                logger.error(f"Ölçü seçimi hatası: {e}", exc_info=True)
                self._komut(f"Ölçü seçilemedi ({e}) — mesafeyi elle girin.")
                return None
            if r["durum"] == "bulundu":
                break
            if r["durum"] == "bos_secim":
                return None
            self._komut(f"UYARI: {r.get('mesaj', '')} Tekrar seçin.")
        else:
            self._komut("3 denemede ölçü alınamadı — mesafeyi elle girin.")
            return None

        olcu = r["olcu"]
        deger = olcu["deger"]
        if olcu.get("override_farkli"):
            cevap = QMessageBox.question(
                self, "Ölçü Yazısı Değiştirilmiş",
                f"Ölçünün yazısı elle değiştirilmiş: yazıda {olcu['override_deger']:g}, "
                f"gerçek ölçü {deger:g}.\n\nYazıdaki {olcu['override_deger']:g} kullanılsın mı?\n"
                f"(Hayır: gerçek ölçü {deger:g})",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if cevap == QMessageBox.StandardButton.Yes:
                deger = olcu["override_deger"]

        birim = self._olcu_birimi or "cm"
        mesafe_m = cizim_uzunlugu_metreye_cevir(deger, birim)
        if not self._olcu_birim_teyitli:
            cevap = QMessageBox.question(
                self, "İlk Ölçü — Birim Teyidi",
                f"Ölçü {deger:g} {birim} okundu → {mesafe_m:.2f} m.\n"
                f"Aralık {d['aralik_cm']:g} cm ile "
                f"{aralikli_donati_hesapla(d['cap'], d['aralik_cm'], d['boy_cm'], mesafe_m)['adet']} "
                f"adet çıkacak.\n\nDoğru mu?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if cevap != QMessageBox.StandardButton.Yes:
                secenekler = ["cm", "mm", "m"]
                birim, tamam = QInputDialog.getItem(
                    self, "Ölçü Birimi", f"Ölçü değeri {deger:g} hangi birimde?",
                    secenekler, secenekler.index(birim), False,
                )
                if not tamam:
                    return None
                self._olcu_birimi = birim
                mesafe_m = cizim_uzunlugu_metreye_cevir(deger, birim)
            self._olcu_birim_teyitli = True
        return mesafe_m, r["handle"]

    def _olcu_rengi_geri_al_kullanilmiyorsa(self, olcu_handle: Optional[str]) -> None:
        """Aynı ölçü birden fazla ilavede kullanılabilir — rengi sadece hiçbir
        satır onu kullanmıyorsa geri al."""
        if not olcu_handle:
            return
        if any(s.get("olcu_handle") == olcu_handle for s in self._satirlar):
            return
        try:
            self.connector.aralikli_donati_isaret_geri_al(olcu_handle)
        except Exception as e:
            logger.error(f"Ölçü rengi geri alınamadı ({olcu_handle}): {e}", exc_info=True)

    def _satir_ekle_tabloya(self, satir: Dict):
        row = self.table.rowCount()
        self.table.insertRow(row)
        degerler = [
        satir.get("temiz_metin") or satir.get("ham_metin") or "",
        f"Ø{satir['cap']}", f"{satir['aralik_cm']:.0f}", f"{satir['boy_cm']:.0f}",
        f"{satir['mesafe_m']:.2f}", f"{satir['adet']}",
        f"{satir['toplam_boy_m']:.2f}", f"{satir['toplam_agirlik_kg']:.2f}",
        satir.get("mesafe_kaynagi", "elle"),
        ]
        for col, deger in enumerate(degerler):
            item = QTableWidgetItem(deger)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, col, item)

    def _tabloyu_yeniden_doldur(self):
        self.table.setRowCount(0)
        for satir in self._satirlar:
            self._satir_ekle_tabloya(satir)

    def _son_ekleneni_geri_al(self):
        if not self._satirlar:
            QMessageBox.warning(self, "Uyarı", "Geri alınacak bir satır yok.")
            return
        satir = self._satirlar.pop()
        handle = satir["handle"]
        self._eklenen_handleler.discard(handle)
        try:
            self.connector.aralikli_donati_isaret_geri_al(handle)
        except Exception as e:
            logger.debug(f"Aralıklı donatı geri alma hatası: {e}")
        self._olcu_rengi_geri_al_kullanilmiyorsa(satir.get("olcu_handle"))
        self._tabloyu_yeniden_doldur()
        self.btn_geri_al.setEnabled(bool(self._satirlar))
        self._genel_toplam_guncelle()

    def _genel_toplam_guncelle(self):
        toplam_kg = sum(s["toplam_agirlik_kg"] for s in self._satirlar)
        toplam_boy = sum(s["toplam_boy_m"] for s in self._satirlar)
        self.genel_lbl.setText(
        f" TOPLANAN: {len(self._satirlar)} donatı | "
        f"Toplam Boy: {toplam_boy:,.2f} m | Toplam Ağırlık: {toplam_kg:,.2f} kg"
        )

    def _bitti(self):
        if not self._satirlar:
            iptal_et = QMessageBox.question(
            self, "Hiç Donatı Eklenmedi",
            "Hiç donatı eklenmedi. Kapatılsın mı?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
            )
            if iptal_et != QMessageBox.StandardButton.Yes:
                return
            super().reject()
            return
        self.accept()

    def reject(self):
        """Rev-166: Esc / pencere X'i toplanan donatıları SESSİZCE atıyordu (Rev-162 perde dersi)."""
        if not self._satirlar:
            super().reject()
            return
        cevap = _kapatma_sorusu(self, len(self._satirlar), "donatı", "aktif kata")
        if cevap == "evet":
            self.accept()
        elif cevap == "hayir":
            self._renkleri_geri_al_ve_kapat()

    def _iptal(self):
        if self._satirlar:
            devam = QMessageBox.question(
            self, "İptal Edilsin Mi?",
            f"Toplanan {len(self._satirlar)} donatı aktif kata EKLENMEYECEK "
            f"ve bu oturumda boyanan renkler geri alınacak. İptal edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
            )
            if devam != QMessageBox.StandardButton.Yes:
                return
        self._renkleri_geri_al_ve_kapat()

    def _renkleri_geri_al_ve_kapat(self):
        # Hiçbir şey kata eklenmeyecek - yanıltıcı yeşil iz kalmasın diye
        # bu oturumda boyanan TÜM renkleri geri al.
        for handle in list(self._eklenen_handleler):
            try:
                self.connector.aralikli_donati_isaret_geri_al(handle)
            except Exception as e:
                logger.debug(f"Aralıklı donatı iptal-geri-alma hatası: {e}")
        for olcu_handle in {s.get("olcu_handle") for s in self._satirlar} - {None}:
            try:
                self.connector.aralikli_donati_isaret_geri_al(olcu_handle)
            except Exception as e:
                logger.error(f"Ölçü iptal-geri-alma hatası: {e}", exc_info=True)
        super().reject()

    def sonuclar(self) -> List[Dict]:
        """Toplanan (mesafesi girilmiş, hesaplanmış) tüm satırları döner."""
        return list(self._satirlar)


class TemelKirisiDonguPaneli(QDialog):
    """Temel kirişi (SBH) beton+kalıp — TOPLU MOD seçim paneli
    (Rev-137 Aşama 3b).

    Neyi çözüyoruz? Eski iki adımlı akış her yazı/çizgi seçiminde AutoCAD <->
    program arasında gidip geliyordu (takılma şikayeti). Toplu modda
    kullanıcı AutoCAD'de KALIR: her kiriş için SBH yazısı + 2 kenar çizgisi
    + ENTER; boş ENTER ile biter. Uzunluk = 2 çizginin ortalaması. Tüm geri
    bildirim (eklendi/güncellendi/hata/uyarı) AutoCAD komut satırına
    yazılır, çizgi okunamazsa uzunluk yine komut satırından (GetReal)
    istenir — döngü boyunca hiç Qt penceresi açılmaz.
    Mükerrer: aynı SBH yazısı (handle; oturumda veya tabloda) tekrar
    seçilirse kayıt GÜNCELLENİR (ayrı satır yok), komut satırında
    bildirilir. Undo/İptal panelde (döngü bittikten sonra).

    Nasıl test ederiz? scratchpad/test_temel_kirisi_ui.py — sahte connector
    (kiris_oku kuyruktan döner, mesajlar listeye yazılır) ile headless.
    """

    KOLONLAR = ["Ad", "Genişlik (cm)", "Yükseklik (cm)", "Uzunluk (m)",
                "Beton (m³)", "Kalıp (m²)", "Uzunluk Kaynağı"]

    def __init__(self, connector, birim: str, mevcut_kayitlar=None, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.birim = birim
        # Önceki oturumlardan kayıtlı kirişler: yazi_handle -> satır
        self._mevcut = dict(mevcut_kayitlar or {})
        self._satirlar: List[Dict] = []
        self.son_hata = ""

        self.setWindowTitle("Temel Kirişi (SBH) — Toplu Seçim")
        self.setMinimumSize(860, 480)
        self.setStyleSheet(
            "QDialog { background: #252535; color: white; }"
            "QLabel { color: white; }"
            "QTableWidget { background: #1e1e2e; color: white; gridline-color: #444; }"
            "QHeaderView::section { background: #333345; color: white; font-weight: bold;"
            " padding: 4px; border: 1px solid #555; }"
            "QPushButton { background: #444; color: white; padding: 6px 14px;"
            " border: 1px solid #666; border-radius: 4px; }"
            "QPushButton:hover { background: #555; }"
        )

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        bilgi = QLabel(
            f"AutoCAD'de her kiriş için: SBH yazısı → 2 kenar çizgisi (üst+alt) → ENTER. "
            f"Sonraki kirişe aynı şekilde devam edin; bitirmek için hiçbir şey seçmeden "
            f"ENTER. Uyarılar AutoCAD komut satırında görünür. Çizim birimi: {birim}."
        )
        bilgi.setStyleSheet("color: #d4a017; font-size: 9pt;")
        bilgi.setWordWrap(True)
        lay.addWidget(bilgi)

        self.durum_lbl = QLabel("Hazır.")
        self.durum_lbl.setStyleSheet(
            "color: #5dade2; font-size: 10pt; font-weight: bold; padding: 4px;"
        )
        self.durum_lbl.setWordWrap(True)
        lay.addWidget(self.durum_lbl)

        ust = QHBoxLayout()
        self.btn_basla = QPushButton(" Seçime Devam Et (AutoCAD)")
        self.btn_basla.setToolTip(
            "AutoCAD'e geçer ve toplu seçime kaldığı yerden devam eder. "
            "Boş ENTER ile buraya döner."
        )
        self.btn_basla.setStyleSheet(
            "QPushButton { background: #8e44ad; color: white; font-weight: bold;"
            " padding: 6px 16px; border: 1px solid #a569bd; border-radius: 4px; }"
            "QPushButton:hover { background: #a569bd; }"
        )
        self.btn_basla.clicked.connect(self._dongu)
        ust.addWidget(self.btn_basla)

        self.btn_geri_al = QPushButton(" Son Ekleneni Geri Al")
        self.btn_geri_al.setToolTip("Son kirişi listeden çıkarır, yazı+çizgi rengini geri alır.")
        self.btn_geri_al.clicked.connect(self._son_ekleneni_geri_al)
        self.btn_geri_al.setEnabled(False)
        ust.addWidget(self.btn_geri_al)
        lay.addLayout(ust)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.KOLONLAR))
        self.table.setHorizontalHeaderLabels(self.KOLONLAR)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table)

        self.uyari_lbl = QLabel()
        self.uyari_lbl.setStyleSheet("color: #f5b041; font-size: 9pt;")
        self.uyari_lbl.setWordWrap(True)
        lay.addWidget(self.uyari_lbl)

        self.toplam_lbl = QLabel()
        self.toplam_lbl.setStyleSheet(
            "color: #2ecc71; font-size: 11pt; font-weight: bold; padding: 6px;"
        )
        lay.addWidget(self.toplam_lbl)
        self._toplam_guncelle()

        alt = QHBoxLayout()
        btn_bitti = QPushButton(" TAMAMLANDI — Tabloya Ekle")
        btn_bitti.setStyleSheet(
            "QPushButton { background: #27ae60; color: white; font-weight: bold;"
            " padding: 6px 16px; border: 1px solid #2ecc71; border-radius: 4px; }"
            "QPushButton:hover { background: #2ecc71; }"
        )
        btn_bitti.clicked.connect(self._bitti)
        alt.addWidget(btn_bitti)
        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self._iptal)
        alt.addWidget(btn_iptal)
        lay.addLayout(alt)

    # ── yardımcılar ──
    def _soru(self, baslik: str, metin: str) -> bool:
        cevap = QMessageBox.question(
            self, baslik, metin,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return cevap == QMessageBox.StandardButton.Yes

    def _onceden_boyali(self) -> set:
        hs = set()
        for s in list(self._mevcut.values()) + self._satirlar:
            hs.add(s.get("yazi_handle"))
            hs.update(s.get("cizgi_handleler") or [])
        hs.discard(None)
        return hs

    def _boya(self, handle) -> bool:
        """Yeşile boyar; True -> bu oturumda YENİ boyandı (undo/iptal geri alır)."""
        if not handle or handle in self._onceden_boyali():
            return False
        try:
            self.connector.obje_isaretle_hizli(handle)
        except Exception as e:
            logger.error(f"[TEMEL KIRISI] TemelKirisiDonguPaneli._boya hata: {e}", exc_info=True)
        return True

    def _geri_boya(self, handle):
        try:
            self.connector.obje_isaret_geri_al(handle)
        except Exception as e:
            logger.error(f"[TEMEL KIRISI] TemelKirisiDonguPaneli._geri_boya hata: {e}", exc_info=True)

    def _cizgi_kullanan(self, cizgi_handle, yazi_handle):
        for s in list(self._mevcut.values()) + self._satirlar:
            if cizgi_handle in (s.get("cizgi_handleler") or []) and s.get("yazi_handle") != yazi_handle:
                return s.get("ad")
        return None

    # ── toplu döngü (kullanıcı AutoCAD'de) ──
    def _dongu(self):
        logger.info("[TEMEL KIRISI] toplu döngü BAŞLADI (Qt arayüzü bu sürede yanıt vermez)")
        self.son_hata = ""
        mesaj = self.connector.temel_kirisi_mesaj
        try:
            self.connector.temel_kirisi_toplu_baslat()
            mesaj(f"TEMEL KİRİŞİ TOPLU SEÇİM (birim: {self.birim}) — her kiriş: SBH yazısı + "
                  "iki kenarın TÜM çizgileri (kesişen kirişle bölünen kenarın bütün parçaları) "
                  "+ ENTER. Bitirmek için boş ENTER.")
            while True:
                okuma = self.connector.temel_kirisi_kiris_oku()
                if okuma.get("durum") == "bos_secim":
                    break
                # Tek ENTER'da birden fazla kiriş / üst üste çift obje olabilir
                ayrim = temel_kirisi_secimi_ayir(okuma)
                if ayrim["hata"]:
                    mesaj(f"HATA: {ayrim['hata']} — bu seçim ATLANDI, tekrar seçin.")
                    continue
                if len(ayrim["gruplar"]) > 1:
                    mesaj(f"Tek seçimde {len(ayrim['gruplar'])} kiriş bulundu — her yazı en "
                          "yakın 2 kenar çizgisiyle eşleştirildi.")
                for grup in ayrim["gruplar"]:
                    self._kirisi_isle(grup, mesaj)
            mesaj(f"TEMEL KİRİŞİ: seçim bitti — {len(self._satirlar)} kiriş. Programa dönün.")
        except Exception as e:
            logger.error(f"[TEMEL KIRISI] toplu döngü hata: {e}", exc_info=True)
            self.son_hata = str(e)
            QMessageBox.critical(self, "Hata", f"AutoCAD seçimi sırasında hata:\n{e}")
        logger.info(f"[TEMEL KIRISI] toplu döngü BİTTİ, toplanan: {len(self._satirlar)}")
        self.durum_lbl.setText(
            f"Seçim durdu — {len(self._satirlar)} kiriş. Devam için 'Seçime Devam Et', "
            "bitirmek için TAMAMLANDI."
        )
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

    def _kirisi_isle(self, okuma: Dict, mesaj) -> None:
        d = temel_kirisi_secim_degerlendir(okuma, self.birim)
        if not d["gecerli"]:
            mesaj(f"HATA: {d['hata']} — bu kiriş ATLANDI, tekrar seçin.")
            return
        ad = d["ad"]
        uzunluk_m = d["uzunluk_m"]
        kaynak = d["kaynak"]
        if d["elle_gerekli"]:
            uzunluk_m = self.connector.temel_kirisi_uzunluk_sor(
                f"{ad}: kenar çizgisi okunamadı/seçilmedi. Net (yüzden yüze) uzunluk (m) "
                "girin, vazgeçmek için ESC:"
            )
            if uzunluk_m is None:
                mesaj(f"{ad} ATLANDI (uzunluk girilmedi).")
                return

        yan_dolu = None if d["elle_gerekli"] else (list(d.get("yan_dolu_m") or []) or None)
        hesap = temel_kirisi_hesapla(d["genislik_cm"], d["yukseklik_cm"], uzunluk_m, yan_dolu)
        if hesap["hata"]:
            mesaj(f"HATA: {ad} — {hesap['hata']} — ATLANDI.")
            return
        uyarilar = list(d["uyarilar"])
        # Rev-158: kenar kapsamları 2b'den fazla farklı -> eksik parça şüphesi, kullanıcı karar verir
        yazi_handle = d["yazi_handle"]
        # Boyama soru ÖNCESİ (eksik parça çizimde görünsün) ve TEK sefer — tekrar
        # boyamak kayıtlı orijinal rengi yeşille ezer (Rev-143 tuzağı)
        yeni_boyanan = [h for h in [yazi_handle] + d["cizgi_handleler"] if self._boya(h)]
        if d.get("eksik_uyari"):
            if not self.connector.komut_satiri_evet_hayir(
                    f"{ad}: {d['eksik_uyari']}. Yine de alınsın mı?", varsayilan=False):
                for h in yeni_boyanan:
                    if not any(h in s.get("yeni_boyanan", []) for s in self._satirlar):
                        self._geri_boya(h)
                mesaj(f"{ad} ATLANDI (eksik parça şüphesi) — eksik kenar parçalarıyla tekrar seçin.")
                return
            uyarilar.append(d["eksik_uyari"])
        if hesap["uyari"] and hesap["uyari"] not in uyarilar and d["elle_gerekli"]:
            uyarilar.append(hesap["uyari"])

        for ch in d["cizgi_handleler"]:
            kullanan = self._cizgi_kullanan(ch, yazi_handle)
            if kullanan:
                uyarilar.append(f"çizgi {kullanan} kirişinde de kullanıldı")

        guncelleme = yazi_handle in self._mevcut or any(
            s["yazi_handle"] == yazi_handle for s in self._satirlar
        )

        satir = {
            "ad": ad,
            "genislik_cm": d["genislik_cm"],
            "yukseklik_cm": d["yukseklik_cm"],
            "uzunluk_m": hesap["uzunluk_m"],
            "beton_m3": hesap["beton_m3"],
            "kalip_m2": hesap["kalip_m2"],
            "kaynak": kaynak,
            "yazi_handle": yazi_handle,
            "cizgi_handleler": list(d["cizgi_handleler"]),
            "uyarilar": uyarilar,
            "yeni_boyanan": yeni_boyanan,
        }
        if yan_dolu:
            satir["yan_dolu_m"] = yan_dolu
            satir["kenar_kapsam_m"] = list(d.get("kenar_kapsam_m") or [])
        idx = next((i for i, s in enumerate(self._satirlar) if s["yazi_handle"] == yazi_handle), None)
        if idx is not None:
            eski = self._satirlar.pop(idx)
            # Güncellemede artık kullanılmayan eski (bu oturumda boyanmış) çizgiler
            for h in eski.get("yeni_boyanan", []):
                if h not in satir["cizgi_handleler"] and h != yazi_handle:
                    self._geri_boya(h)
                elif h not in yeni_boyanan:
                    satir["yeni_boyanan"].append(h)
        self._satirlar.append(satir)
        self._tabloyu_doldur()

        durum = "GÜNCELLENDİ" if guncelleme else "EKLENDİ"
        dolu_metni = (f", yan dolu {yan_dolu[0]:.2f}/{yan_dolu[1]:.2f} m" if yan_dolu else "")
        mesaj(f"{ad} {durum}: L={hesap['uzunluk_m']:.2f} m{dolu_metni}, beton={tek_hane(hesap['beton_m3'])} m3, "
              f"kalıp={tek_hane(hesap['kalip_m2'])} m2, {len(d['cizgi_handleler'])} çizgi "
              f"(toplam {len(self._satirlar)} kiriş)")
        for u in uyarilar:
            mesaj(f"  UYARI {ad}: {u}")

    def _tabloyu_doldur(self):
        self.table.setRowCount(0)
        for s in self._satirlar:
            row = self.table.rowCount()
            self.table.insertRow(row)
            degerler = [
                s["ad"], f"{s['genislik_cm']:g}", f"{s['yukseklik_cm']:g}",
                f"{s['uzunluk_m']:.2f}", f"{tek_hane(s['beton_m3'])}", f"{tek_hane(s['kalip_m2'])}",
                s["kaynak"],
            ]
            for col, deger in enumerate(degerler):
                item = QTableWidgetItem(deger)
                if s.get("uyarilar"):
                    item.setToolTip("\n".join(s["uyarilar"]))
                    item.setForeground(QColor("#f5b041"))
                self.table.setItem(row, col, item)
        uyarili = [f"{s['ad']}: {'; '.join(s['uyarilar'])}" for s in self._satirlar if s.get("uyarilar")]
        self.uyari_lbl.setText(("Uyarılar — " + " | ".join(uyarili)) if uyarili else "")
        self.btn_geri_al.setEnabled(bool(self._satirlar))
        self._toplam_guncelle()

    def _toplam_guncelle(self):
        beton = sum(s["beton_m3"] for s in self._satirlar)
        kalip = sum(s["kalip_m2"] for s in self._satirlar)
        self.toplam_lbl.setText(
            f" TOPLANAN: {len(self._satirlar)} kiriş | Beton: {tek_hane(beton, True)} m³ | "
            f"Kalıp: {tek_hane(kalip, True)} m²"
        )

    def _son_ekleneni_geri_al(self):
        if not self._satirlar:
            return
        satir = self._satirlar.pop()
        for h in satir.get("yeni_boyanan", []):
            self._geri_boya(h)
        self._tabloyu_doldur()

    def _bitti(self):
        if not self._satirlar:
            if self._soru("Hiç Kiriş Eklenmedi", "Hiç temel kirişi eklenmedi. Kapatılsın mı?"):
                super().reject()
            return
        self.accept()

    def reject(self):
        """Rev-166: Esc / pencere X'i toplanan temel kirişlerini SESSİZCE atıyordu (Rev-162 perde dersi)."""
        if not self._satirlar:
            super().reject()
            return
        cevap = _kapatma_sorusu(self, len(self._satirlar), "temel kirişi", "tabloya")
        if cevap == "evet":
            self.accept()
        elif cevap == "hayir":
            self._renkleri_geri_al_ve_kapat()

    def _iptal(self):
        if self._satirlar and not self._soru(
            "İptal Edilsin Mi?",
            f"Toplanan {len(self._satirlar)} kiriş tabloya EKLENMEYECEK ve bu "
            "oturumda boyanan renkler geri alınacak. İptal edilsin mi?"
        ):
            return
        self._renkleri_geri_al_ve_kapat()

    def _renkleri_geri_al_ve_kapat(self):
        satirlar, self._satirlar = self._satirlar, []
        for s in satirlar:
            for h in s.get("yeni_boyanan", []):
                self._geri_boya(h)
        super().reject()

    def sonuclar(self) -> List[Dict]:
        return list(self._satirlar)


class PerdeDonguPaneli(QDialog):
    """Perde beton+kalıp — TOPLU MOD seçim paneli (Rev-143 Aşama 3).

    Neyi çözüyoruz? Kullanıcı AutoCAD'de KALIR: her perde için kesit
    poligonu + (varsa) kolona/perdeye bitişen uç çizgileri + (varsa) ad
    yazısı + ENTER; boş ENTER ile biter. Alan/çevre poligondan, düşüm uç
    çizgilerinden (çevre üzerinde doğrulanmış). İlk perdede ve şüpheli
    alanda teyit komut satırından (Evet/Hayır) — ilk teyit reddedilirse
    döngü durur (birim/ölçek yanlış demektir). Mükerrer: aynı poligon
    (handle) tekrar seçilirse satır GÜNCELLENİR. Undo/İptal döngü sonrası.

    Nasıl test ederiz? scratchpad/test_perde_secim.py — sahte connector ile headless.
    """

    KOLONLAR = ["Ad", "Alan (m²)", "Çevre (m)", "Düşülen (m)", "Beton (m³)", "Kalıp (m²)"]

    def __init__(self, connector, birim: str, olcek_adi: str, olcek: float,
                 ayar: "KatYukseklikAyari", alan_teyitli: bool = False,
                 mevcut_kayitlar=None, parent=None, ad_kayitli=None, okunamayanlar=None):
        super().__init__(parent)
        self.connector = connector
        self.birim = birim
        self.olcek_adi = olcek_adi
        self.olcek = olcek
        self.ayar = ayar
        self.alan_teyitli = alan_teyitli
        # Önceki oturumlardan kayıtlı perdeler: poligon_handle -> satır
        self._mevcut = dict(mevcut_kayitlar or {})
        self._satirlar: List[Dict] = []
        self.son_hata = ""
        # Rev-160: ortak ad havuzu — kolon aracında bu katta kayıtlı ad mı? (callable(ad) -> bool)
        self._ad_kayitli = ad_kayitli
        okunamayanlar = list(okunamayanlar or [])

        self.setWindowTitle("Perde — Toplu Seçim")
        self.setMinimumSize(860, 480)
        self.setStyleSheet(
            "QDialog { background: #252535; color: white; }"
            "QLabel { color: white; }"
            "QTableWidget { background: #1e1e2e; color: white; gridline-color: #444; }"
            "QHeaderView::section { background: #333345; color: white; font-weight: bold;"
            " padding: 4px; border: 1px solid #555; }"
            "QPushButton { background: #444; color: white; padding: 6px 14px;"
            " border: 1px solid #666; border-radius: 4px; }"
            "QPushButton:hover { background: #555; }"
        )
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        bilgi = QLabel(
            "AutoCAD'de her perde için: kesit (kapalı polyline) + kolona / başka perdeye "
            "bitişen uç çizgileri (varsa) + perde adı yazısı (varsa) → ENTER. Bitirmek için "
            "hiçbir şey seçmeden ENTER. ideCAD: perde BLOĞU ya da patlatılmış kontur (her kenar ayrı "
            "çizgi) de seçilebilir — kontur kurulunca uç kenarlar ayrıca sorulur. "
            f"Birim: {birim}, ölçek: {olcek_adi}. "
            f"{ayar.esas_etiketi()} Alınan perde (kesit + ad yazısı) CAMGÖBEĞİ boyanır."
            + (f"\nKolon aracında okunamayanlar (bu araçla alın): {', '.join(okunamayanlar)}"
               if okunamayanlar else "")
        )
        bilgi.setStyleSheet("color: #d4a017; font-size: 9pt;")
        bilgi.setWordWrap(True)
        lay.addWidget(bilgi)

        self.durum_lbl = QLabel("Hazır.")
        self.durum_lbl.setStyleSheet("color: #5dade2; font-size: 10pt; font-weight: bold; padding: 4px;")
        self.durum_lbl.setWordWrap(True)
        lay.addWidget(self.durum_lbl)

        ust = QHBoxLayout()
        self.btn_basla = QPushButton(" Seçime Devam Et (AutoCAD)")
        self.btn_basla.setToolTip("AutoCAD'e geçer ve seçime kaldığı yerden devam eder. "
                                  "Boş ENTER ile buraya döner.")
        self.btn_basla.setStyleSheet(
            "QPushButton { background: #8e44ad; color: white; font-weight: bold;"
            " padding: 6px 16px; border: 1px solid #a569bd; border-radius: 4px; }"
            "QPushButton:hover { background: #a569bd; }"
        )
        self.btn_basla.clicked.connect(self._dongu)
        ust.addWidget(self.btn_basla)
        self.btn_geri_al = QPushButton(" Son Ekleneni Geri Al")
        self.btn_geri_al.setToolTip("Son perdeyi listeden çıkarır, çizimdeki yeşil rengi geri alır.")
        self.btn_geri_al.clicked.connect(self._son_ekleneni_geri_al)
        self.btn_geri_al.setEnabled(False)
        ust.addWidget(self.btn_geri_al)
        lay.addLayout(ust)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.KOLONLAR))
        self.table.setHorizontalHeaderLabels(self.KOLONLAR)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table)

        self.uyari_lbl = QLabel()
        self.uyari_lbl.setStyleSheet("color: #f5b041; font-size: 9pt;")
        self.uyari_lbl.setWordWrap(True)
        lay.addWidget(self.uyari_lbl)
        self.toplam_lbl = QLabel()
        self.toplam_lbl.setStyleSheet("color: #2ecc71; font-size: 11pt; font-weight: bold; padding: 6px;")
        lay.addWidget(self.toplam_lbl)
        self._toplam_guncelle()

        alt = QHBoxLayout()
        btn_bitti = QPushButton(" TAMAMLANDI — Tabloya Ekle")
        btn_bitti.setStyleSheet(
            "QPushButton { background: #27ae60; color: white; font-weight: bold;"
            " padding: 6px 16px; border: 1px solid #2ecc71; border-radius: 4px; }"
            "QPushButton:hover { background: #2ecc71; }"
        )
        btn_bitti.clicked.connect(self._bitti)
        alt.addWidget(btn_bitti)
        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self._iptal)
        alt.addWidget(btn_iptal)
        lay.addLayout(alt)

    # ── yardımcılar ──
    def _soru(self, baslik: str, metin: str) -> bool:
        cevap = QMessageBox.question(
            self, baslik, metin,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return cevap == QMessageBox.StandardButton.Yes

    def _kullanilan(self, haric_satir=None) -> set:
        """Kayıtlı/oturumdaki satırların kullandığı handle'lar (haric_satir hariç)."""
        hs = set()
        for s in list(self._mevcut.values()) + self._satirlar:
            if s is not haric_satir:
                hs.update(s.get("handleler") or [])
        hs.discard(None)
        return hs

    def _boya(self, handle, onceki_renkler: Dict) -> bool:
        """Perde rengine (CAMGÖBEĞİ, Rev-160) boyar; önceki program rengini
        (kolon aracının kırmızısı vb. ya da None=orijinal) onceki_renkler'e
        yazar. True -> bu oturumda YENİ boyandı (undo/iptal geri alır)."""
        if not handle or handle in self._kullanilan():
            return False
        try:
            onceki_renkler[handle] = self.connector.obje_rengi_ayarla(handle, ELEMAN_RENKLERI["Perde"])
        except Exception as e:
            logger.error(f"[PERDE] _boya hata: {e}", exc_info=True)
        return True

    def _geri_boya(self, handle, haric_satir=None, onceki=None):
        """Rengi bir önceki hâline döndürür (kırmızıysa kırmızı, orijinalse orijinal).
        Perde-perde birleşim çizgisi iki perdede kullanılabilir — başka satır
        hâlâ kullanıyorsa rengi geri alma."""
        if handle in self._kullanilan(haric_satir):
            return
        try:
            self.connector.obje_rengi_ayarla(handle, onceki)
        except Exception as e:
            logger.error(f"[PERDE] _geri_boya hata: {e}", exc_info=True)

    @staticmethod
    def _satir_renk_geri(satir: Dict, geri_boya) -> None:
        onceki = satir.get("onceki_renkler") or {}
        for h in reversed(satir.get("yeni_boyanan", [])):
            geri_boya(h, onceki=onceki.get(h))

    def _ad_mukerrer_mi(self, ad: str, anahtar) -> bool:
        """Ortak havuz (Rev-160): aynı katta bu ad başka bir kayıtta var mı?
        Bu oturumda AYNI poligonun yeniden seçimi soru sormaz (düzeltme)."""
        n = eleman_ad_normalize(ad)
        if not n:
            return False
        if any(eleman_ad_normalize(s.get("ad")) == n and s["poligon_handle"] != anahtar for s in self._satirlar):
            return True
        if anahtar in self._mevcut or any(eleman_ad_normalize(s.get("ad")) == n for s in self._mevcut.values()):
            return True
        return bool(self._ad_kayitli and self._ad_kayitli(n))

    def _hesap(self, s: Dict) -> Dict:
        return perde_hesapla(s["alan_m2"], s["cevre_m"], self.ayar.kat_yuksekligi_m,
                             self.ayar.doseme_kalinligi_m, self.ayar.beton_esasi, s["dusulen_m"])

    # ── toplu döngü (kullanıcı AutoCAD'de) ──
    def _dongu(self):
        logger.info("[PERDE] toplu döngü BAŞLADI")
        self.son_hata = ""
        mesaj = self.connector.komut_satiri_mesaj
        try:
            self.connector.perde_toplu_baslat()
            mesaj(f"PERDE TOPLU SEÇİM (birim {self.birim}, ölçek {self.olcek_adi}) — her perde: "
                  "kesit + [bitişik uç çizgileri] + [ad yazısı] + ENTER. Bitirmek için boş ENTER.")
            while True:
                okuma = self.connector.perde_oku()
                if okuma.get("durum") == "bos_secim":
                    break
                try:
                    d = perde_secimi_degerlendir(okuma["objeler"], self.birim, self.olcek)
                    if d.get("zincir") and not d["hata"]:
                        # Rev-155: patlatılmış kontur — kenarlar ayrı nesne, uç düşümü ikinci istemle
                        mesaj(f"Kontur kuruldu ({len(d['zincir_parcalari'])} kenar): alan {d['alan_m2']:.4f} m2, "
                              f"çevre {d['cevre_m']:.2f} m.")
                        d = perde_zincir_uc_dus(d, self.connector.perde_uc_sec())
                finally:
                    # Blok patlatmasından kalan geçici nesneler her turda silinir (hata olsa da)
                    temizle = getattr(self.connector, "perde_gecici_temizle", None)
                    if temizle:
                        temizle()
                if d["hata"]:
                    mesaj(f"HATA: {d['hata']} — bu seçim ATLANDI, tekrar seçin.")
                    continue
                if not self.alan_teyitli or perde_alan_supheli_mi(d["alan_m2"]):
                    ek = f" UYARI: {d['uyari']}." if d["uyari"] else ""
                    kabul = self.connector.komut_satiri_evet_hayir(
                        f"Alan {d['alan_m2']:.4f} m2, çevre {d['cevre_m']:.2f} m okundu (birim "
                        f"{self.birim}, ölçek {self.olcek_adi}).{ek} AREA ile kontrol edin, doğru mu?")
                    if not kabul:
                        if not self.alan_teyitli:
                            mesaj("Alan kabul edilmedi — döngü DURDURULDU. Programda birim/ölçeği "
                                  "düzeltip tekrar başlatın.")
                            break
                        mesaj("Alan kabul edilmedi — bu perde ATLANDI.")
                        continue
                    self.alan_teyitli = True
                self._perde_isle(d, mesaj)
            mesaj(f"PERDE: seçim bitti — {len(self._satirlar)} perde. Programa dönün.")
        except Exception as e:
            logger.error(f"[PERDE] toplu döngü hata: {e}", exc_info=True)
            self.son_hata = str(e)
            QMessageBox.critical(self, "Hata", f"AutoCAD seçimi sırasında hata:\n{e}")
        logger.info(f"[PERDE] toplu döngü BİTTİ, toplanan: {len(self._satirlar)}")
        self.durum_lbl.setText(f"Seçim durdu — {len(self._satirlar)} perde. Devam için "
                               "'Seçime Devam Et', bitirmek için TAMAMLANDI.")
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

    def _perde_isle(self, d: Dict, mesaj) -> None:
        anahtar = d["poligon_handle"]
        eski = self._mevcut.get(anahtar) or next(
            (s for s in self._satirlar if s["poligon_handle"] == anahtar), None)
        ad = d["ad"] or (eski["ad"] if eski else
                         f"Perde {len(self._mevcut) + len(self._satirlar) + 1}")
        satir = {
            "ad": ad, "poligon_handle": anahtar, "alan_m2": d["alan_m2"],
            "cevre_m": d["cevre_m"], "dusulen_m": d["dusulen_m"],
            "handleler": list(d["kullanilan_handleler"]),
            "uyari": d["uyari"], "yeni_boyanan": [], "onceki_renkler": {},
        }
        hesap = self._hesap(satir)
        if hesap["hata"]:
            mesaj(f"HATA: {ad} — {hesap['hata']} — ATLANDI.")
            return
        # Rev-160: aynı katta aynı ad (kolon aracından ya da başka paftadan) -> sor; Hayır'da renk değişmez
        if d["ad"] and self._ad_mukerrer_mi(d["ad"], anahtar):
            if not self.connector.komut_satiri_evet_hayir(f"{ad} bu katta zaten kayıtlı. Güncellensin mi?"):
                mesaj(f"{ad} değiştirilmedi — ATLANDI.")
                return
            eski = eski or True
            # Bu oturumda aynı adla başka poligondan alınmış satır -> yerini yenisi alır
            for s in [s for s in self._satirlar if eleman_ad_normalize(s.get("ad")) == eleman_ad_normalize(ad)
                      and s["poligon_handle"] != anahtar]:
                self._satirlar.remove(s)
                self._satir_renk_geri(s, self._geri_boya)
        idx = next((i for i, s in enumerate(self._satirlar) if s["poligon_handle"] == anahtar), None)
        if idx is not None:
            onceki = self._satirlar.pop(idx)
            # Güncellemede artık kullanılmayan (bu oturumda boyanmış) handle'lar
            for h in onceki.get("yeni_boyanan", []):
                if h in satir["handleler"]:
                    satir["yeni_boyanan"].append(h)
                    satir["onceki_renkler"][h] = (onceki.get("onceki_renkler") or {}).get(h)
                else:
                    self._geri_boya(h, onceki=(onceki.get("onceki_renkler") or {}).get(h))
        # Önceki seçimde zaten boyanmış olanı tekrar boyama (önceki renk kaydı ezilmesin)
        satir["yeni_boyanan"] += [h for h in satir["handleler"]
                                  if h not in satir["yeni_boyanan"] and self._boya(h, satir["onceki_renkler"])]
        self._satirlar.append(satir)
        self._tabloyu_doldur()

        durum = "GÜNCELLENDİ" if eski else "EKLENDİ"
        mesaj(f"{ad} {durum}: alan={satir['alan_m2']:.2f} m2, çevre={satir['cevre_m']:.2f} m "
              f"(düşülen {satir['dusulen_m']:.2f}), beton={tek_hane(hesap['beton_m3'])} m3, "
              f"kalıp={tek_hane(hesap['kalip_m2'])} m2 (toplam {len(self._satirlar)} perde)")
        uyarilar = "; ".join(u for u in (d["uyari"], hesap["uyari"]) if u)
        if uyarilar:
            mesaj(f"  UYARI {ad}: {uyarilar}")

    def _tabloyu_doldur(self):
        self.table.setRowCount(0)
        for s in self._satirlar:
            h = self._hesap(s)
            row = self.table.rowCount()
            self.table.insertRow(row)
            degerler = [s["ad"], f"{s['alan_m2']:.2f}", f"{s['cevre_m']:.2f}", f"{s['dusulen_m']:.2f}",
                        f"{tek_hane(h['beton_m3'])}", f"{tek_hane(h['kalip_m2'])}"]
            for col, deger in enumerate(degerler):
                item = QTableWidgetItem(deger)
                if s.get("uyari"):
                    item.setToolTip(s["uyari"])
                    item.setForeground(QColor("#f5b041"))
                self.table.setItem(row, col, item)
        uyarili = [f"{s['ad']}: {s['uyari']}" for s in self._satirlar if s.get("uyari")]
        self.uyari_lbl.setText(("Uyarılar — " + " | ".join(uyarili)) if uyarili else "")
        self.btn_geri_al.setEnabled(bool(self._satirlar))
        self._toplam_guncelle()

    def _toplam_guncelle(self):
        hesaplar = [self._hesap(s) for s in self._satirlar]
        beton = sum(h["beton_m3"] for h in hesaplar)
        kalip = sum(h["kalip_m2"] for h in hesaplar)
        self.toplam_lbl.setText(f" TOPLANAN: {len(self._satirlar)} perde | Beton: {tek_hane(beton, True)} m³ | "
                                f"Kalıp: {tek_hane(kalip, True)} m²")

    def _son_ekleneni_geri_al(self):
        if not self._satirlar:
            return
        satir = self._satirlar.pop()
        self._satir_renk_geri(satir, self._geri_boya)
        self._tabloyu_doldur()

    def _bitti(self):
        if not self._satirlar:
            if self._soru("Hiç Perde Eklenmedi", "Hiç perde eklenmedi. Kapatılsın mı?"):
                super().reject()
            return
        self.accept()

    def _iptal(self):
        if self._satirlar and not self._soru(
            "İptal Edilsin Mi?",
            f"Toplanan {len(self._satirlar)} perde tabloya EKLENMEYECEK ve bu oturumda "
            "boyanan renkler geri alınacak. İptal edilsin mi?"
        ):
            return
        self._renkleri_geri_al_ve_kapat()

    def _renkleri_geri_al_ve_kapat(self):
        satirlar, self._satirlar = self._satirlar, []
        for s in reversed(satirlar):
            self._satir_renk_geri(s, self._geri_boya)
        super().reject()

    def reject(self):
        """Rev-162: Esc / pencere X'i toplanan perdeleri SESSİZCE atıyordu (Kat Özeti'ne
        hiçbir şey gitmiyor, AutoCAD'de renkler boyalı kalıyordu). Artık sorulur:
        Evet = tabloya ekle, Hayır = ekleme + renkleri geri al, Vazgeç = panel açık kalsın."""
        if not self._satirlar:
            super().reject()
            return
        S = QMessageBox.StandardButton
        cevap = QMessageBox.question(
            self, "Perdeler Henüz Eklenmedi",
            f"Toplanan {len(self._satirlar)} perde henüz tabloya EKLENMEDİ.\n\n"
            "Evet: tabloya ekle (Kat Özeti'ne de geçer)\n"
            "Hayır: ekleme, AutoCAD'deki renkleri geri al\n"
            "Vazgeç: pencere açık kalsın",
            S.Yes | S.No | S.Cancel, S.Yes)
        if cevap == S.Yes:
            self.accept()
        elif cevap == S.No:
            self._renkleri_geri_al_ve_kapat()

    def sonuclar(self) -> List[Dict]:
        return list(self._satirlar)


class DosemeDonguPaneli(QDialog):
    """Döşeme — AutoCAD köşe tıklama döngüsü (Rev-144 Aşama 2).

    Neyi çözüyoruz? Kullanıcı AutoCAD'de KALIR: her döşeme için KİRİŞ İÇ
    YÜZÜ köşelerini sırayla tıklar (nokta sınırı yok), ENTER ile kapatır;
    program kapalı MACENTA poligonu METRAJ_DOSEME katmanına çizer, alanı
    tabloya ekler. Mod sorusu YOK (Rev-146: dikdörtgen modu kaldırıldı).
    1. köşede ENTER/ESC döngüyü bitirir; köşe alırken ESC o seçimi iptal eder. İlk döşemede (ve şüpheli
    alanda) teyit; ilk teyit reddedilirse döngü durur. Ağırlık merkezi
    kayıtlı bir döşemenin içine düşerse güncelleme sorulur. OSMODE döngü
    boyunca 33, nasıl biterse bitsin geri yüklenir.
    Geri al / iptal: çizilen poligon silinir, güncellenen satırın eski
    hali ve poligonu geri getirilir.

    Nasıl test ederiz? scratchpad/test_doseme_poligon.py (sahte connector).
    """

    KOLONLAR = ["Ad", "Brüt Alan (m²)", "Boşluk (m²)", "Çevre (m)", "Kalınlık (cm)", "Beton (m³)", "Kaynak"]

    def __init__(self, connector, birim: str, olcek_adi: str, olcek: float, kalinlik_cm: float,
                 alan_teyitli: bool = False, kayitlar=None, parent=None, hedef_idx: Optional[int] = None,
                 mod: str = "doseme", sacak_kalinlik_cm: float = 16.0):
        super().__init__(parent)
        # Rev-164: mod="sacak" -> panel SADECE saçak toplar ([H]alka / [Ş]erit)
        self.mod = mod
        self.sacak_kalinlik_cm = sacak_kalinlik_cm
        self.connector = connector
        self.birim = birim
        self.olcek_adi = olcek_adi
        self.olcek = olcek
        self.kalinlik_cm = kalinlik_cm
        self.alan_teyitli = alan_teyitli
        # Çalışma kopyası — TAMAMLANDI'da pencereye geçer, iptalde atılır
        # Derin kopya: boşluk listeleri pencere satırlarıyla paylaşılmasın (iptalde bozulmasın)
        self.kayitlar: List[Dict] = copy.deepcopy(list(kayitlar or []))
        self._eylemler: List[Dict] = []
        self.son_hata = ""
        # Rev-159: verilirse panel SADECE bu döşemeye boşluk ekler (formdaki "Boşluk Ekle")
        self.hedef_idx = hedef_idx if hedef_idx is not None and 0 <= hedef_idx < len(self.kayitlar) else None
        self._bosluk_ipucu_verildi = False

        self.setWindowTitle("Döşeme — AutoCAD Köşe Tıklama" if self.hedef_idx is None else
                            f"Döşeme {self.kayitlar[self.hedef_idx]['ad']} — AutoCAD'de Boşluk Ekle")
        self.setMinimumSize(820, 460)
        self.setStyleSheet(
            "QDialog { background: #252535; color: white; } QLabel { color: white; }"
            "QTableWidget { background: #1e1e2e; color: white; gridline-color: #444; }"
            "QHeaderView::section { background: #333345; color: white; font-weight: bold;"
            " padding: 4px; border: 1px solid #555; }"
            "QPushButton { background: #444; color: white; padding: 6px 14px;"
            " border: 1px solid #666; border-radius: 4px; } QPushButton:hover { background: #555; }"
        )
        lay = QVBoxLayout(self)
        bilgi = QLabel(
            "AutoCAD'de her döşeme için köşeleri KİRİŞ İÇ YÜZLERİNDEN sırayla tıklayın (akstan değil, "
            "nokta sınırı yok), ENTER ile kapatın. Döşeme MACENTA (mor-pembe) çizilir. "
            "Son döşemeye boşluk (merdiven/şaft/asansör) için 1. köşede B yazın — boşluk KIRMIZI çizilir. "
            "Bitirmek için 1. köşede ENTER. "
            f"Birim: {birim}, ölçek: {olcek_adi}, "
            f"kalınlık: {kalinlik_cm:g} cm."
            if self.hedef_idx is None else
            f"AutoCAD'de {self.kayitlar[self.hedef_idx]['ad']} döşemesinin İÇİNDE boşluk köşelerini sırayla "
            "tıklayın, ENTER ile kapatın; arka arkaya birden fazla boşluk eklenebilir. Bitirmek için 1. "
            f"köşede ENTER. Boşluk KIRMIZI çizilir. Birim: {birim}, ölçek: {olcek_adi}."
        )
        if self.mod == "sacak":
            self.setWindowTitle("Saçak — AutoCAD Köşe Tıklama")
            bilgi.setText(
                f"SAÇAK (kalınlık {sacak_kalinlik_cm:g} cm). AutoCAD'de önce tip seçin: "
                "[H]alka — saçak binayı tamamen sarıyor: önce saçak UCU dış köşeleri, sonra kenar kirişin "
                "DIŞ yüz köşeleri. [Ş]erit — saçak bazı cephelerde: önce kiriş DIŞ yüzü boyunca noktalar + "
                "ENTER (kiriş hattı), sonra saçak ucu boyunca noktalar + ENTER (uç hattı; yön önemsiz). "
                "Saçak KEHRİBAR (ACI 40) çizilir. Bitirmek için tip sorusunda ENTER. "
                f"Birim: {birim}, ölçek: {olcek_adi}.")
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("color: #d4a017; font-size: 9pt;")
        lay.addWidget(bilgi)
        self.durum_lbl = QLabel("Hazır.")
        self.durum_lbl.setWordWrap(True)
        self.durum_lbl.setStyleSheet("color: #5dade2; font-size: 10pt; font-weight: bold; padding: 4px;")
        lay.addWidget(self.durum_lbl)

        ust = QHBoxLayout()
        self.btn_basla = QPushButton(" Seçime Devam Et (AutoCAD)")
        self.btn_basla.setStyleSheet(
            "QPushButton { background: #8e44ad; color: white; font-weight: bold;"
            " padding: 6px 16px; border: 1px solid #a569bd; border-radius: 4px; }")
        self.btn_basla.clicked.connect(self._dongu)
        ust.addWidget(self.btn_basla)
        self.btn_geri_al = QPushButton(" Son Ekleneni Geri Al")
        self.btn_geri_al.setToolTip("Son eklenen/güncellenen döşemeyi geri alır, poligonunu çizimden siler.")
        self.btn_geri_al.clicked.connect(self._son_ekleneni_geri_al)
        ust.addWidget(self.btn_geri_al)
        lay.addLayout(ust)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.KOLONLAR))
        self.table.setHorizontalHeaderLabels(self.KOLONLAR)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table)
        self.toplam_lbl = QLabel()
        self.toplam_lbl.setStyleSheet("color: #2ecc71; font-size: 11pt; font-weight: bold; padding: 6px;")
        lay.addWidget(self.toplam_lbl)

        alt = QHBoxLayout()
        btn_bitti = QPushButton(" TAMAMLANDI — Tabloya Ekle")
        btn_bitti.setStyleSheet(
            "QPushButton { background: #27ae60; color: white; font-weight: bold;"
            " padding: 6px 16px; border: 1px solid #2ecc71; border-radius: 4px; }")
        btn_bitti.clicked.connect(self.accept)
        alt.addWidget(btn_bitti)
        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self._iptal)
        alt.addWidget(btn_iptal)
        lay.addLayout(alt)
        self._tabloyu_doldur()

    # ── döngü (kullanıcı AutoCAD'de) ──
    def _dongu(self):
        c = self.connector
        mesaj = c.komut_satiri_mesaj
        import threading
        logger.info(f"[DOSEME] köşe tıklama döngüsü BAŞLADI (thread {threading.current_thread().name}, "
                    f"{threading.get_ident()})")
        osmode_hata = ""
        try:
            c.doseme_toplu_baslat()
            try:
                if self.hedef_idx is None and self.mod != "sacak":
                    mesaj(f"DÖŞEME (birim {self.birim}, ölçek {self.olcek_adi}): köşeleri KİRİŞ İÇ "
                          "YÜZLERİNDEN sırayla tıklayın, akstan DEĞİL; ENTER ile kapatın. Son döşemeye "
                          "boşluk için 1. köşede B. Bitirmek için 1. köşede ENTER.")
                if self.hedef_idx is not None:
                    self._hedef_bosluk_dongusu(mesaj)
                elif self.mod == "sacak":
                    self._sacak_dongusu(mesaj)
                while self.hedef_idx is None and self.mod != "sacak":
                    koseler = self._poligon_al(mesaj)
                    if koseler == "bitti":
                        break
                    if koseler == "bosluk":
                        idx = self._son_doseme_idx()
                        if idx is None:
                            mesaj("Önce bir döşeme tıklayın — boşluk SON EKLENEN döşemeye bağlanır. Önceki "
                                  "döşemelere programdaki 'Boşluk Ekle' butonuyla ekleyin.")
                        else:
                            self._bosluk_ekle(idx, mesaj)
                        continue
                    if koseler is None:
                        mesaj("Seçim iptal edildi (ESC) — sonraki döşemeye geçin.")
                        continue
                    d = doseme_poligon_degerlendir(koseler, self.birim, self.olcek)
                    if d["hata"]:
                        mesaj(f"HATA: {d['hata']} — bu seçim ALINMADI.")
                        continue
                    if not self.alan_teyitli or d["supheli"]:
                        if not c.komut_satiri_evet_hayir(
                                f"Alan {d['alan_m2']:.2f} m2, çevre {d['cevre_m']:.2f} m (birim {self.birim}, "
                                f"ölçek {self.olcek_adi}). AREA ile kontrol edin, doğru mu?"):
                            if not self.alan_teyitli:
                                mesaj("Alan kabul edilmedi — döngü DURDURULDU. Programda birim/ölçeği "
                                      "düzeltip tekrar başlatın.")
                                break
                            mesaj("Alan kabul edilmedi — bu döşeme ALINMADI.")
                            continue
                        self.alan_teyitli = True
                    self._doseme_isle(d, mesaj)
            finally:
                osmode_hata = c.doseme_toplu_bitir() or ""
            mesaj(f"DÖŞEME: seçim bitti — {len(self._eylemler)} işlem. Programa dönün.")
        except Exception as e:
            logger.error(f"[DOSEME] döngü hatası: {e}", exc_info=True)
            self.son_hata = str(e)
            QMessageBox.critical(self, "Hata", f"AutoCAD seçimi sırasında hata:\n{e}")
        if osmode_hata:
            QMessageBox.warning(self, "Nesne Yakalama (OSMODE)", osmode_hata)
        self.durum_lbl.setText(f"Seçim durdu — bu oturumda {len(self._eylemler)} işlem. Devam için "
                               "'Seçime Devam Et', bitirmek için TAMAMLANDI.")
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

    BOSLUK_ANAHTAR = "Bosluk"   # AutoCAD anahtar kelimesi (ASCII) — "B" yazmak yeter

    def _poligon_al(self, mesaj, baslik: str = "DÖŞEME", en_az: int = 3):
        """Köşeleri sırayla alır (sınırsız). Dönüş: köşe listesi | None (ESC,
        bu poligon iptal) | "bitti" (1. köşede ENTER/ESC — döşemede döngü
        biter, boşlukta "boşluk yok") | "bosluk" (döşeme 1. köşesinde B —
        son döşemeye boşluk, Rev-159). en_az=2: açık hat (saçak şeridi, Rev-164)."""
        c = self.connector
        noktalar = []
        doseme = baslik == "DÖŞEME"
        sozcuk = "köşe" if en_az >= 3 else "nokta"
        while True:
            if not noktalar:
                istem = (f"DÖŞEME 1. köşe (kiriş İÇ YÜZÜ) veya [{self.BOSLUK_ANAHTAR}] (son döşemeye) "
                         "— bitirmek için ENTER:" if doseme
                         else f"{baslik} 1. {sozcuk} — vazgeçmek için ENTER:")
            else:
                ek = (" (bitirmek için ENTER)" if en_az < 3 else " (kapatmak için ENTER)") \
                    if len(noktalar) >= en_az else ""
                istem = f"{baslik} {len(noktalar) + 1}. {sozcuk}{ek}:"
            if doseme and not noktalar:
                durum, p = c.doseme_nokta_al(istem, None, anahtarlar=self.BOSLUK_ANAHTAR)
            else:
                durum, p = c.doseme_nokta_al(istem, noktalar[-1] if noktalar else None)
            if not noktalar and durum in ("enter", "esc"):
                return "bitti"
            if durum == "nokta":
                noktalar.append(p)
            elif durum == "enter":
                if len(noktalar) >= en_az:
                    return noktalar
                mesaj(f"En az {en_az} {sozcuk} gerekli ({len(noktalar)} var) — devam edin, vazgeçmek için ESC.")
            elif durum == "metin":
                if doseme and not noktalar and str(p).strip().casefold().startswith("b"):
                    return "bosluk"
                mesaj("Nokta tıklayın" + ("; son döşemeye boşluk için B" if doseme and not noktalar else "")
                      + "; kapatmak için ENTER, vazgeçmek için ESC.")
            else:
                return None

    def _yeni_ad(self, onek: str = "D") -> str:
        adlar = {s["ad"] for s in self.kayitlar}
        n = 1
        while f"{onek}{n}" in adlar:
            n += 1
        return f"{onek}{n}"

    def _satir_poligonlarini_sil(self, s: Dict):
        """Döşeme poligonunu ve bağlı boşluk poligonlarını (saçakta iç poligonu) çizimden siler."""
        c = self.connector
        c.obje_sil(s.get("handle"))
        if s.get("ic_handle"):
            c.obje_sil(s["ic_handle"])
        for b in s.get("bosluklar") or []:
            c.obje_sil(b.get("handle"))

    def _satir_poligonlarini_ciz(self, s: Dict):
        """Geri alınan satırın döşeme + boşluk poligonlarını yeniden çizer (yeni handle'lar).
        Saçak: kehribar dış/şerit poligonu + (halkada) iç poligon."""
        c = self.connector
        if sacak_mi(s):
            if s.get("koseler"):
                s["handle"] = c.doseme_poligon_ciz(s["koseler"], renk=SACAK_RENK)
            if s.get("ic_koseler"):
                s["ic_handle"] = c.doseme_poligon_ciz(s["ic_koseler"], renk=SACAK_RENK)
            return
        if s.get("koseler"):
            s["handle"] = c.doseme_poligon_ciz(s["koseler"])
        for b in s.get("bosluklar") or []:
            b["handle"] = c.doseme_poligon_ciz(b["koseler"], renk=int(AcadColor.RED))

    @staticmethod
    def _bosluk_toplamlarini_guncelle(s: Dict):
        bl = s.get("bosluklar") or []
        s["bosluk_alan_m2"] = round(sum(b["alan_m2"] for b in bl), 4)
        s["bosluk_cevre_m"] = round(sum(b["cevre_m"] for b in bl), 3)

    def _doseme_isle(self, d: Dict, mesaj) -> None:
        c = self.connector
        merkez = d["agirlik_merkezi"]
        # Saçak satırları hariç — halka saçağın dış poligonu bütün binayı kapsar (Rev-164)
        idx = next((i for i, s in enumerate(self.kayitlar)
                    if not sacak_mi(s) and s.get("koseler") and nokta_poligon_icinde_mi(merkez, s["koseler"])),
                   None)
        if idx is not None:
            eski = self.kayitlar[idx]
            if not c.komut_satiri_evet_hayir(f"Bu alan zaten {eski['ad']} olarak kayıtlı. Güncellensin mi?"):
                mesaj(f"{eski['ad']} değiştirilmedi — yeni alan eklenmedi.")
                return
        handle = c.doseme_poligon_ciz(d["koseler"])
        if idx is not None:
            onceki = copy.deepcopy(self.kayitlar[idx])
            self._satir_poligonlarini_sil(onceki)
            satir = copy.deepcopy(onceki)
            satir.update({"brut_alan_m2": d["alan_m2"], "cevre_m": d["cevre_m"], "koseler": d["koseler"],
                          "handle": handle, "kaynak": "Tıklama", "bosluklar": []})
            if onceki.get("bosluklar"):
                mesaj(f"{onceki['ad']}: eski boşluklar kaldırıldı — gerekiyorsa yeniden ekleyin.")
            self._bosluk_toplamlarini_guncelle(satir)
            self.kayitlar[idx] = satir
            self._eylemler.append({"tip": "guncelle", "idx": idx, "onceki": onceki})
            durum = "GÜNCELLENDİ"
        else:
            satir = {"ad": self._yeni_ad(), "brut_alan_m2": d["alan_m2"], "bosluk_alan_m2": 0.0,
                     "bosluk_cevre_m": 0.0, "serbest_kenar_m": 0.0, "kalinlik_cm": self.kalinlik_cm,
                     "kaynak": "Tıklama", "handle": handle, "koseler": d["koseler"], "cevre_m": d["cevre_m"],
                     "bosluklar": []}
            self.kayitlar.append(satir)
            idx = len(self.kayitlar) - 1
            self._eylemler.append({"tip": "ekle", "idx": idx})
            durum = "EKLENDİ"
        self._tabloyu_doldur()
        h = self._hesap(satir)
        if h["hata"]:
            mesaj(f"{satir['ad']} {durum} ama HESAP HATASI: {h['hata']} — tabloda düzeltin.")
        else:
            mesaj(f"{satir['ad']} {durum}: alan={d['alan_m2']:.2f} m2, çevre={d['cevre_m']:.2f} m, "
                  f"beton={tek_hane(h['beton_m3'])} m3 ({satir['kalinlik_cm']:g} cm)"
                  + (" — boşluk varsa 1. köşede B" if not self._bosluk_ipucu_verildi else ""))
        self._bosluk_ipucu_verildi = True

    def _son_doseme_idx(self) -> Optional[int]:
        """Bu oturumda son eklenen/güncellenen (veya boşluk eklenen) döşeme —
        eylem listesinden türetilir, geri almada kendiliğinden bir öncekine döner."""
        for e in reversed(self._eylemler):
            if 0 <= e.get("idx", -1) < len(self.kayitlar):
                return e["idx"]
        return None

    def _bosluk_ekle(self, idx: int, mesaj) -> str:
        """Hedef döşemeye TEK boşluk tıklatır (Rev-159 — soru yok; AutoCAD'de B
        veya formdan "Boşluk Ekle"). Kırmızı çizilir, satıra bağlanır, AYRI bir
        geri alma adımıdır. Dönüş: "eklendi" | "reddedildi" | "bitti" (1.
        köşede ENTER/ESC) | "iptal" (köşe alırken ESC)."""
        c = self.connector
        satir = self.kayitlar[idx]
        if sacak_mi(satir):
            mesaj(f"{satir['ad']} bir saçak — saçağa boşluk eklenmez.")
            return "bitti"
        koseler = self._poligon_al(mesaj, baslik=f"BOŞLUK ({satir['ad']})")
        if koseler == "bitti":
            return "bitti"
        if koseler is None:
            mesaj("Boşluk iptal edildi (ESC).")
            return "iptal"
        b = bosluk_degerlendir(satir.get("koseler") or [], koseler,
                               [x["koseler"] for x in satir.get("bosluklar") or []],
                               self.birim, self.olcek, satir["brut_alan_m2"])
        if b["hata"]:
            mesaj(f"HATA: {b['hata']} — boşluk ALINMADI.")
            return "reddedildi"
        handle = c.doseme_poligon_ciz(b["koseler"], renk=int(AcadColor.RED))
        satir.setdefault("bosluklar", []).append(
            {"koseler": b["koseler"], "alan_m2": b["alan_m2"], "cevre_m": b["cevre_m"], "handle": handle})
        self._bosluk_toplamlarini_guncelle(satir)
        self._eylemler.append({"tip": "bosluk", "idx": idx})
        self._tabloyu_doldur()
        h = self._hesap(satir)
        mesaj(f"{satir['ad']}: boşluk eklendi {b['alan_m2']:.2f} m2 (çevre {b['cevre_m']:.2f} m) — "
              f"net {h['net_alan_m2']:.2f} m2, beton {tek_hane(h['beton_m3'])} m3, "
              f"toplam kalıp {tek_hane(h['toplam_kalip_m2'])} m2")
        return "eklendi"

    @staticmethod
    def _hesap(s: Dict) -> Dict:
        return doseme_hesapla(s["brut_alan_m2"], s["kalinlik_cm"], s.get("bosluk_alan_m2", 0.0),
                              s.get("bosluk_cevre_m", 0.0), s.get("serbest_kenar_m", 0.0))

    def _tabloyu_doldur(self):
        self.table.setRowCount(0)
        beton = alan = 0.0
        for s in self.kayitlar:
            h = self._hesap(s)
            beton += h["beton_m3"]
            alan += h["net_alan_m2"]
            row = self.table.rowCount()
            self.table.insertRow(row)
            cevre = s.get("cevre_m")
            bosluk = s.get("bosluk_alan_m2") or 0.0
            for col, v in enumerate([s["ad"], f"{s['brut_alan_m2']:.2f}", f"{bosluk:.2f}",
                                     f"{cevre:.2f}" if cevre else "-", f"{s['kalinlik_cm']:g}",
                                     f"{tek_hane(h['beton_m3'])}", s.get("kaynak", "")]):
                self.table.setItem(row, col, QTableWidgetItem(v))
        self.btn_geri_al.setEnabled(bool(self._eylemler))
        n_sacak = sum(1 for s in self.kayitlar if sacak_mi(s))
        self.toplam_lbl.setText(f" {len(self.kayitlar) - n_sacak} döşeme"
                                + (f" + {n_sacak} saçak" if n_sacak else "")
                                + f" | Net alan: {alan:,.2f} m² | Beton: {tek_hane(beton, True)} m³")

    def _geri_al_bir(self):
        c = self.connector
        e = self._eylemler.pop()
        if e["tip"] == "ekle":
            self._satir_poligonlarini_sil(self.kayitlar.pop(e["idx"]))
        elif e["tip"] == "bosluk":
            s = self.kayitlar[e["idx"]]
            b = s["bosluklar"].pop()
            c.obje_sil(b.get("handle"))
            self._bosluk_toplamlarini_guncelle(s)
        else:  # guncelle: yeni poligonları sil, eski satırı ve poligonlarını geri getir
            self._satir_poligonlarini_sil(self.kayitlar[e["idx"]])
            onceki = copy.deepcopy(e["onceki"])
            self._satir_poligonlarini_ciz(onceki)
            self.kayitlar[e["idx"]] = onceki

    def _son_ekleneni_geri_al(self):
        if self._eylemler:
            self._geri_al_bir()
            self._tabloyu_doldur()

    def _hedef_bosluk_dongusu(self, mesaj) -> None:
        """Formdan "Boşluk Ekle" (Rev-159): seçili döşemeye arka arkaya boşluk
        tıklatır; 1. köşede ENTER biter. Kontroller AutoCAD'deki B ile aynı
        (_bosluk_ekle) — iki yol aynı sonucu verir."""
        ad = self.kayitlar[self.hedef_idx]["ad"]
        mesaj(f"BOŞLUK → {ad} (birim {self.birim}, ölçek {self.olcek_adi}): boşluk köşelerini sırayla "
              "tıklayın, ENTER ile kapatın. Bitirmek için 1. köşede ENTER.")
        while self._bosluk_ekle(self.hedef_idx, mesaj) != "bitti":
            pass

    # ── Rev-164: SAÇAK modu ──
    def _sacak_dongusu(self, mesaj) -> None:
        """Tip sorusu ([Halka]/[Serit]) -> tıklamalar -> değerlendirme -> kayıt; tip sorusunda ENTER biter."""
        c = self.connector
        mesaj(f"SAÇAK (kalınlık {self.sacak_kalinlik_cm:g} cm, birim {self.birim}, ölçek {self.olcek_adi}): "
              "H = binayı saran halka, S = bazı cephelerde şerit. Bitirmek için ENTER.")
        while True:
            secim = c.komut_satiri_secenek("SAÇAK tipi", "Halka Serit")
            if not secim:
                break
            if secim.strip().upper().startswith("H"):
                dis = self._poligon_al(mesaj, baslik="SAÇAK UCU (dış köşe)")
                if dis in ("bitti", None):
                    mesaj("Saçak iptal edildi.")
                    continue
                ic = self._poligon_al(mesaj, baslik="KENAR KİRİŞ DIŞ YÜZÜ (iç köşe)")
                if ic in ("bitti", None):
                    mesaj("Saçak iptal edildi (iç köşeler alınmadı).")
                    continue
                d = sacak_halka_degerlendir(dis, ic, self.birim, self.olcek)
                alt = SACAK_HALKA
            else:
                kiris = self._poligon_al(mesaj, baslik="KİRİŞ HATTI (kiriş dış yüzü)", en_az=2)
                if kiris in ("bitti", None):
                    mesaj("Saçak iptal edildi.")
                    continue
                uc = self._poligon_al(mesaj, baslik="SAÇAK UCU HATTI", en_az=2)
                if uc in ("bitti", None):
                    mesaj("Saçak iptal edildi (uç hattı alınmadı).")
                    continue
                d = sacak_serit_degerlendir(kiris, uc, self.birim, self.olcek)
                alt = SACAK_SERIT
            if d["hata"]:
                mesaj(f"HATA: {d['hata']}")
                continue
            if not self.alan_teyitli or d["supheli"]:
                if not c.komut_satiri_evet_hayir(
                        f"Saçak alanı {d['alan_m2']:.2f} m2, kalıp kenarı {d['kenar_m']:.2f} m (birim "
                        f"{self.birim}, ölçek {self.olcek_adi}). Doğru mu?"):
                    if not self.alan_teyitli:
                        mesaj("Alan kabul edilmedi — döngü DURDURULDU. Birim/ölçeği düzeltip tekrar başlatın.")
                        break
                    mesaj("Alan kabul edilmedi — saçak ALINMADI.")
                    continue
                self.alan_teyitli = True
            self._sacak_isle(d, alt, mesaj)

    def _sacak_isle(self, d: Dict, alt: str, mesaj) -> None:
        """Mükerrer (sadece saçak satırları arasında) -> çizim (kehribar) -> satır + eylem."""
        c = self.connector
        idx = sacak_mukerrer_bul(d, self.kayitlar)
        if idx is not None and not c.komut_satiri_evet_hayir(
                f"Bu saçak zaten {self.kayitlar[idx]['ad']} olarak kayıtlı. Güncellensin mi?"):
            mesaj(f"{self.kayitlar[idx]['ad']} değiştirilmedi — saçak ALINMADI.")
            return
        handle = c.doseme_poligon_ciz(d["koseler"], renk=SACAK_RENK)
        ic_handle = c.doseme_poligon_ciz(d["ic_koseler"], renk=SACAK_RENK) if d.get("ic_koseler") else None
        satir = {"tip": SACAK_TIPI, "sacak_tipi": alt, "brut_alan_m2": d["alan_m2"], "bosluk_alan_m2": 0.0,
                 "bosluk_cevre_m": 0.0, "serbest_kenar_m": d["kenar_m"], "kalinlik_cm": self.sacak_kalinlik_cm,
                 "kaynak": f"Saçak-{alt}", "handle": handle, "ic_handle": ic_handle, "koseler": d["koseler"],
                 "ic_koseler": d.get("ic_koseler") or [], "cevre_m": d["cevre_m"], "kiris_m": d["kiris_m"],
                 "bosluklar": []}
        if idx is not None:
            onceki = copy.deepcopy(self.kayitlar[idx])
            self._satir_poligonlarini_sil(onceki)
            satir["ad"] = onceki["ad"]
            satir["kalinlik_cm"] = onceki.get("kalinlik_cm", self.sacak_kalinlik_cm)
            self.kayitlar[idx] = satir
            self._eylemler.append({"tip": "guncelle", "idx": idx, "onceki": onceki})
            durum = "GÜNCELLENDİ"
        else:
            satir["ad"] = self._yeni_ad("SÇ")
            self.kayitlar.append(satir)
            self._eylemler.append({"tip": "ekle", "idx": len(self.kayitlar) - 1})
            durum = "EKLENDİ"
        self._tabloyu_doldur()
        h = self._hesap(satir)
        mesaj(f"{satir['ad']} ({alt}) {durum}: alan={d['alan_m2']:.2f} m2, kenar={d['kenar_m']:.2f} m, "
              f"beton={tek_hane(h['beton_m3'])} m3, toplam kalıp={tek_hane(h['toplam_kalip_m2'])} m2")

    def _iptal(self):
        if self._eylemler:
            cevap = QMessageBox.question(
                self, "İptal Edilsin Mi?",
                f"Bu oturumdaki {len(self._eylemler)} işlem geri alınacak ve çizilen poligonlar "
                "silinecek. İptal edilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if cevap != QMessageBox.StandardButton.Yes:
                return
        self.reject()

    def reject(self):
        # Pencere X ile kapatılsa bile çizimde sahipsiz poligon kalmasın
        while self._eylemler:
            self._geri_al_bir()
        super().reject()

    def sonuclar(self) -> List[Dict]:
        return list(self.kayitlar)


class KirisDonguPaneli(QDialog):
    """Kiriş beton+kalıp — AutoCAD toplu seçim paneli, MOD BAZLI (Rev-150 Aşama 2).

    Neyi çözüyoruz? Kullanıcı AutoCAD'de KALIR: seçilen modda (İç / Kenar)
    her kiriş için etiket yazısı + kenar çizgileri + ENTER; tip SORULMAZ.
    L = çizgi uzunlukları toplamı / 2. İç = TURUNCU, Kenar = MAVİ. Boş ENTER
    döngüyü bitirir; panelden diğer mod seçilip devam edilir (satırlar
    birikir). Panel ana tablonun ÇALIŞMA KOPYASI üzerinde çalışır: mükerrer
    (handle) seçim mevcut satırı günceller; İptal / X tüm eylemleri geri alır.
    Nasıl test ederiz? scratchpad/test_kiris_secim.py — sahte connector.
    """

    KOLONLAR = ["Ad", "b (cm)", "h (cm)", "L1 (m)", "L2 (m)", "Tip", "t (cm)", "Beton (m³)", "Kalıp (m²)"]
    MOD_METNI = {
        KIRIS_TIPLERI[0]: "KİRİŞ — İÇ KİRİŞ modu (iki tarafı döşeme)",
        KIRIS_TIPLERI[1]: "KİRİŞ — KENAR KİRİŞ modu (tek tarafı döşeme)",
    }

    def __init__(self, connector, birim: str, olcek_adi: str, olcek: float, t_cm: float,
                 mod: str, teyitli: bool = False, kayitlar=None, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.birim = birim
        self.olcek_adi = olcek_adi
        self.olcek = olcek
        self.t_cm = t_cm
        self.mod = mod
        self.teyitli = teyitli
        self.kayitlar: List[Dict] = copy.deepcopy(list(kayitlar or []))
        self._eylemler: List[Dict] = []
        self.son_hata = ""

        self.setWindowTitle("Kiriş — AutoCAD Toplu Seçim")
        self.setMinimumSize(900, 500)
        self.setStyleSheet(
            "QDialog { background: #252535; color: white; }"
            "QLabel { color: white; }"
            "QTableWidget { background: #1e1e2e; color: white; gridline-color: #444; }"
            "QHeaderView::section { background: #333345; color: white; font-weight: bold;"
            " padding: 4px; border: 1px solid #555; }"
            "QPushButton { background: #444; color: white; padding: 6px 14px;"
            " border: 1px solid #666; border-radius: 4px; }"
            "QPushButton:hover { background: #555; }"
        )
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        bilgi = QLabel(
            "AutoCAD'de her kiriş için: etiket yazısı (örn. K101 (25/50)) + iki kenar çizgisi → ENTER. "
            "Bitirmek için hiçbir şey seçmeden ENTER — sonra diğer modu seçip devam edebilirsiniz. "
            f"İç = turuncu, Kenar = mavi. Birim: {birim}, ölçek: {olcek_adi}, döşeme t = {t_cm:g} cm."
        )
        bilgi.setStyleSheet("color: #d4a017; font-size: 9pt;")
        bilgi.setWordWrap(True)
        lay.addWidget(bilgi)
        self.durum_lbl = QLabel("Hazır.")
        self.durum_lbl.setStyleSheet("color: #5dade2; font-size: 10pt; font-weight: bold; padding: 4px;")
        self.durum_lbl.setWordWrap(True)
        lay.addWidget(self.durum_lbl)

        ust = QHBoxLayout()
        self.btn_ic = QPushButton(" İç Kiriş Seç")
        self.btn_ic.setToolTip("İki tarafı döşemeli kirişler — turuncuya boyanır.")
        self.btn_ic.setStyleSheet("QPushButton { background: #e67e22; color: white; font-weight: bold; }")
        self.btn_ic.clicked.connect(lambda: self._dongu(KIRIS_TIPLERI[0]))
        ust.addWidget(self.btn_ic)
        self.btn_kenar = QPushButton(" Kenar Kiriş Seç")
        self.btn_kenar.setToolTip("Bir tarafında döşeme olmayan kirişler (cephe, boşluk kenarı) — maviye boyanır.")
        self.btn_kenar.setStyleSheet("QPushButton { background: #2471a3; color: white; font-weight: bold; }")
        self.btn_kenar.clicked.connect(lambda: self._dongu(KIRIS_TIPLERI[1]))
        ust.addWidget(self.btn_kenar)
        self.btn_geri_al = QPushButton(" Son Ekleneni Geri Al")
        self.btn_geri_al.setToolTip("Son eklemeyi / güncellemeyi geri alır, çizimdeki rengi de geri döndürür.")
        self.btn_geri_al.clicked.connect(self._son_ekleneni_geri_al)
        ust.addWidget(self.btn_geri_al)
        lay.addLayout(ust)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.KOLONLAR))
        self.table.setHorizontalHeaderLabels(self.KOLONLAR)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table)
        self.toplam_lbl = QLabel()
        self.toplam_lbl.setStyleSheet("color: #2ecc71; font-size: 11pt; font-weight: bold; padding: 6px;")
        lay.addWidget(self.toplam_lbl)

        alt = QHBoxLayout()
        btn_bitti = QPushButton(" TAMAMLANDI — Tabloya Aktar")
        btn_bitti.setStyleSheet("QPushButton { background: #27ae60; color: white; font-weight: bold; }")
        btn_bitti.clicked.connect(self.accept)
        alt.addWidget(btn_bitti)
        btn_iptal = QPushButton("İptal")
        btn_iptal.clicked.connect(self._iptal)
        alt.addWidget(btn_iptal)
        lay.addLayout(alt)
        self._tabloyu_doldur()

    # ── renk ──
    def _boya(self, handle, tip):
        try:
            self.connector.obje_renklendir_hizli(handle, KIRIS_RENKLERI[tip])
        except Exception as e:
            logger.error(f"[KIRIS] _boya hata: {e}", exc_info=True)

    def _geri_boya(self, handle):
        try:
            self.connector.obje_isaret_geri_al(handle)
        except Exception as e:
            logger.error(f"[KIRIS] _geri_boya hata: {e}", exc_info=True)

    # ── döngü (kullanıcı AutoCAD'de) ──
    def _dongu(self, mod: Optional[str] = None):
        if mod:
            self.mod = mod
        logger.info(f"[KIRIS] döngü BAŞLADI mod={self.mod}")
        self.son_hata = ""
        mesaj = self.connector.komut_satiri_mesaj
        try:
            self.connector.kiris_toplu_baslat()
            mesaj(self.MOD_METNI[self.mod])
            mesaj("Her kiriş: etiket yazısı + iki kenarın TÜM çizgileri (bölünen kenarın bütün "
                  "parçaları) + ENTER. Bitirmek için boş ENTER.")
            while True:
                okuma = self.connector.kiris_oku()
                if okuma.get("durum") == "bos_secim":
                    break
                if not self._kiris_isle(okuma, mesaj):
                    break
            mesaj(f"KİRİŞ: seçim bitti — tabloda {len(self.kayitlar)} kiriş. Programa dönün.")
        except Exception as e:
            logger.error(f"[KIRIS] döngü hata: {e}", exc_info=True)
            self.son_hata = str(e)
            QMessageBox.critical(self, "Hata", f"AutoCAD seçimi sırasında hata:\n{e}")
        self.durum_lbl.setText(
            f"Seçim durdu ({self.mod} modu) — {len(self.kayitlar)} kiriş. Diğer modla devam edebilir "
            "veya TAMAMLANDI ile tabloya aktarabilirsiniz.")
        self._tabloyu_doldur()
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

    def _kiris_isle(self, okuma: Dict, mesaj) -> bool:
        """Tek seçimi işler. False -> döngü durmalı (ilk teyit reddedildi)."""
        sor = self.connector.komut_satiri_evet_hayir
        d = kiris_secim_degerlendir(okuma, self.birim, self.olcek)
        if not d["gecerli"]:
            mesaj(f"HATA: {d['hata']} — seçim ALINMADI, tekrar seçin.")
            return True
        ad = d["ad"]
        b, h = d["b_cm"], d["h_cm"]
        if d["kesit_elle"]:
            b = self.connector.komut_satiri_sayi_sor(f"{ad}: yazıda kesit yok. Genişlik b (cm), ESC = vazgeç:")
            h = self.connector.komut_satiri_sayi_sor(f"{ad}: Yükseklik h (cm):") if b else None
            if not b or not h:
                mesaj(f"{ad} ALINMADI (kesit girilmedi).")
                return True
        handleler = [x for x in [d["yazi_handle"]] + d["cizgi_handleler"] if x]
        muk = kiris_mukerrer_bul(self.kayitlar, handleler)
        if muk["hata"]:
            mesaj(f"HATA: {muk['hata']} — seçim ALINMADI.")
            return True
        idx = muk["index"]
        eski = self.kayitlar[idx] if idx is not None else None
        # Rev-158: l1/l2 = kenar KAPSAMI (boşluk dahil), d1/d2 = DOLU (yan kalıp)
        satir = {"ad": ad, "b_cm": b, "h_cm": h, "l1_m": d["l1_m"], "l2_m": d["l2_m"],
                 "d1_m": d["d1_m"], "d2_m": d["d2_m"], "tip": self.mod,
                 "t_cm": eski["t_cm"] if eski else self.t_cm, "kaynak": "Çizim", "handleler": handleler}
        hesap = self._satir_hesap(satir)
        if hesap["hata"]:
            mesaj(f"HATA: {ad} — {hesap['hata']} — ALINMADI.")
            return True
        if not self.teyitli:
            if not sor(f"{ad}: {b:g}/{h:g}, L1 = {d['l1_m']:.2f} m, L2 = {d['l2_m']:.2f} m okundu "
                       f"(birim {self.birim}, ölçek {self.olcek_adi}). LIST ile kontrol edin, doğru mu?"):
                mesaj("Uzunluk kabul edilmedi — döngü DURDURULDU. Programda çizim birimi/ölçeğini "
                      "düzeltip tekrar başlatın.")
                return False
            self.teyitli = True
        eksik = kenar_eksik_secim_uyarisi(d["l1_m"], d["l2_m"], b) if kenar_eksik_secim_uyarisi else ""
        if eksik:
            # Parçalar soru sırasında boyalı olsun — eksik parça çizimde görünsün
            kayitli = {x for k in self.kayitlar for x in k.get("handleler") or []}
            for hnd in handleler:
                self._boya(hnd, self.mod)
            if not sor(f"{ad}: {eksik}. Yine de alınsın mı?"):
                for hnd in handleler:
                    if hnd not in kayitli:
                        self._geri_boya(hnd)
                    elif eski is not None:
                        self._boya(hnd, eski["tip"])
                mesaj(f"{ad} ALINMADI (eksik parça şüphesi) — eksik kenar parçalarıyla tekrar seçin.")
                return True
            d["notlar"].append(eksik)
        if eski is not None:
            soru = (f"Bu kiriş zaten {eski['ad']} olarak kayıtlı. Güncellensin mi?"
                    if eski["tip"] == self.mod else
                    f"{eski['ad']} {eski['tip'].upper()} olarak kayıtlı. {self.mod.upper()} olarak güncellensin mi?")
            if not sor(soru):
                mesaj(f"{ad} ALINMADI (kayıt değişmedi).")
                return True
            onceki = copy.deepcopy(eski)
            for hnd in onceki["handleler"]:
                if hnd not in handleler:
                    self._geri_boya(hnd)
            self.kayitlar[idx] = satir
            self._eylemler.append({"tip": "guncelle", "idx": idx, "onceki": onceki})
            durum = "GÜNCELLENDİ"
        else:
            self.kayitlar.append(satir)
            self._eylemler.append({"tip": "ekle", "idx": len(self.kayitlar) - 1})
            durum = "EKLENDİ"
        for hnd in handleler:
            self._boya(hnd, self.mod)
        self._tabloyu_doldur()
        dolu = ("" if (satir["d1_m"], satir["d2_m"]) == (satir["l1_m"], satir["l2_m"])
                else f" (yan dolu {satir['d1_m']:.2f}/{satir['d2_m']:.2f})")
        mesaj(f"{ad} {durum} ({self.mod}): {b:g}/{h:g}, L1={satir['l1_m']:.2f} L2={satir['l2_m']:.2f} m{dolu}, "
              f"beton={tek_hane(hesap['beton_m3'])} m3, kalıp={tek_hane(hesap['toplam_kalip_m2'])} m2, "
              f"{len(d['cizgi_handleler'])} çizgi")
        for n in d["notlar"] + [x for x in (hesap["uyari"], hesap["bilgi"]) if x]:
            mesaj(f"  NOT {ad}: {n}")
        return True

    @staticmethod
    def _satir_hesap(s: Dict) -> Dict:
        """Kayıt satırının hesabı — kapsam (l1/l2) + dolu (d1/d2; eski kayıtta yok -> kapsam)."""
        return kiris_hesapla(s["b_cm"], s["h_cm"], s["l1_m"], s["tip"], s["t_cm"], s["l2_m"],
                             s.get("d1_m"), s.get("d2_m"))

    # ── tablo / geri al ──
    def _tabloyu_doldur(self):
        self.table.setRowCount(0)
        beton = kalip = 0.0
        for s in self.kayitlar:
            h = self._satir_hesap(s)
            beton += h["beton_m3"]
            kalip += h["toplam_kalip_m2"]
            row = self.table.rowCount()
            self.table.insertRow(row)
            degerler = [s["ad"], f"{s['b_cm']:g}", f"{s['h_cm']:g}", f"{s['l1_m']:.2f}", f"{s['l2_m']:.2f}", s["tip"],
                        f"{s['t_cm']:g}", f"{tek_hane(h['beton_m3'])}", f"{tek_hane(h['toplam_kalip_m2'])}"]
            for col, deger in enumerate(degerler):
                self.table.setItem(row, col, QTableWidgetItem(deger))
        self.btn_geri_al.setEnabled(bool(self._eylemler))
        self.toplam_lbl.setText(f" TOPLAM: {len(self.kayitlar)} kiriş | Beton: {tek_hane(beton, True)} m³ | "
                                f"Kalıp: {tek_hane(kalip, True)} m²")

    def _geri_al_bir(self):
        e = self._eylemler.pop()
        yeni = self.kayitlar[e["idx"]]
        if e["tip"] == "ekle":
            for hnd in yeni["handleler"]:
                self._geri_boya(hnd)
            del self.kayitlar[e["idx"]]
            return
        onceki = e["onceki"]
        for hnd in yeni["handleler"]:
            if hnd not in onceki["handleler"]:
                self._geri_boya(hnd)
        for hnd in onceki["handleler"]:
            self._boya(hnd, onceki["tip"])
        self.kayitlar[e["idx"]] = onceki

    def _son_ekleneni_geri_al(self):
        if self._eylemler:
            self._geri_al_bir()
            self._tabloyu_doldur()

    def _iptal(self):
        if self._eylemler:
            cevap = QMessageBox.question(
                self, "İptal Edilsin Mi?",
                f"Bu oturumdaki {len(self._eylemler)} işlem geri alınacak, renkler eski haline dönecek. "
                "İptal edilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if cevap != QMessageBox.StandardButton.Yes:
                return
        self.reject()

    def reject(self):
        # X ile kapatma da iptal sayılır — çizimde yanıltıcı renk kalmasın
        while self._eylemler:
            self._geri_al_bir()
        super().reject()

    def sonuclar(self) -> List[Dict]:
        return list(self.kayitlar)


class SbhDemirTipDialog(QDialog):
    """Bir SBH tipinin demir parametreleri (Rev-153).

    Neyi çözüyoruz? Filiz/tevzi çapı, aralığı, boyu vb. SBH tipine göre değişir;
    tip başına BİR KEZ girilir, kalıcı saklanır. Tevzi sıra 0 = formülle hesapla.
    Nasıl test ederiz? scratchpad/test_temel_kirisi_demir_ui.py (headless).
    """

    TAM_SAYI_ALANLAR = ("filiz_cap", "filiz_yuz", "tevzi_cap", "tevzi_sira", "tevzi_yuz")

    def __init__(self, tip: str, parametre: Dict, yeni_tip: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{tip} — Demir Parametreleri")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        aciklama = QLabel(
            (f"'{tip}' tipi için kayıtlı demir parametresi yok — kesit detayından bir kez girin.\n"
             if yeni_tip else "") +
            "Filiz: düşey, kiriş boyunca her aralıkta bir. Tevzi: yatay, kiriş boyunca uzanır, "
            "yükseklik boyunca her aralıkta bir sıra. Tevzi sıra 0 = (y − 2·pas) ÷ aralık ile hesaplanır."
        )
        aciklama.setWordWrap(True)
        lay.addWidget(aciklama)
        form = QGridLayout()
        self.alanlar: Dict[str, QDoubleSpinBox] = {}
        p = sbh_parametre_tamamla(parametre) if sbh_parametre_tamamla else dict(parametre)
        for i, (anahtar, etiket, birim) in enumerate(SBH_DEMIR_ALANLARI):
            if anahtar in self.TAM_SAYI_ALANLAR:
                spin = QSpinBox()
                spin.setRange(0, 500)
            else:
                spin = QDoubleSpinBox()
                spin.setDecimals(2)
                spin.setRange(0.0, 5000.0)
            spin.setSuffix(f" {birim}")
            if anahtar == "tevzi_sira":
                spin.setSpecialValueText("Otomatik (formül)")
            spin.setValue(p.get(anahtar) or 0)
            form.addWidget(QLabel(etiket + ":"), i, 0)
            form.addWidget(spin, i, 1)
            self.alanlar[anahtar] = spin
        lay.addLayout(form)
        self.hata_label = QLabel()
        self.hata_label.setStyleSheet("color:#e74c3c; font-weight:bold;")
        lay.addWidget(self.hata_label)
        butonlar = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        butonlar.button(QDialogButtonBox.StandardButton.Ok).setText("Kaydet")
        butonlar.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        butonlar.accepted.connect(self._kaydet)
        butonlar.rejected.connect(self.reject)
        lay.addWidget(butonlar)

    def parametreler(self) -> Dict:
        p = {k: (int(s.value()) if k in self.TAM_SAYI_ALANLAR else float(s.value()))
             for k, s in self.alanlar.items()}
        p["tevzi_sira"] = p["tevzi_sira"] or None
        return p

    def _kaydet(self):
        hata = sbh_parametre_dogrula(sbh_parametre_tamamla(self.parametreler())) if sbh_parametre_dogrula else ""
        if hata:
            self.hata_label.setText(f"⚠ {hata}")
            return
        self.accept()


class MetrajAnalizWindow(QMainWindow):
    """Akilli Metraj Analizi Ana Penceresi"""

    # ── Rev-151: kiriş / döşeme kayıtları kat bazlı — property AKTİF katın listesi ──
    def _aktif_kat_anahtari(self) -> str:
        return getattr(self, "aktif_kat_adi", "") or ""

    @property
    def kiris_kayitlari(self) -> List[Dict]:
        return self._kiris_kat_kayitlari.setdefault(self._aktif_kat_anahtari(), [])

    @kiris_kayitlari.setter
    def kiris_kayitlari(self, deger: List[Dict]) -> None:
        self._kiris_kat_kayitlari[self._aktif_kat_anahtari()] = list(deger)

    @property
    def doseme_kayitlari(self) -> List[Dict]:
        return self._doseme_kat_kayitlari.setdefault(self._aktif_kat_anahtari(), [])

    @doseme_kayitlari.setter
    def doseme_kayitlari(self, deger: List[Dict]) -> None:
        self._doseme_kat_kayitlari[self._aktif_kat_anahtari()] = list(deger)

    @property
    def merdiven_kayitlari(self) -> List[Dict]:
        return self._merdiven_kat_kayitlari.setdefault(self._aktif_kat_anahtari(), [])

    @merdiven_kayitlari.setter
    def merdiven_kayitlari(self, deger: List[Dict]) -> None:
        self._merdiven_kat_kayitlari[self._aktif_kat_anahtari()] = list(deger)

    def __init__(self, parent=None, db=None, otomatik_kayit: Optional[bool] = None):
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
        # Demir Metrajı sekmesi gibi dikey içeriği yoğun sekmelerde sürekli
        # kaydırmayı azaltmak için pencere daha büyük açılır (minimum değil).
        self.resize(1000, 900)

        # Veri listeleri
        self.kirisler: List[Dict] = []
        self.duvarlar: List[Dict] = []
        # Rev-134 devam: Kolon Yazısından Toplu Oku mükerrer engelleme —
        # anahtar (kat_adi, kolon_adi) -> {en_m, boy_m, kat_yuk_m, beton, kalip}.
        # Aynı kat+kolon adı tekrar okunursa GÜNCELLENİR (üzerine yazılır),
        # tabloya ikinci kez EKLENMEZ; farklı kattaki aynı isim ayrı sayılır
        # (self.aktif_kat_adi Demir Metrajı ile PAYLAŞILAN aynı kat mekanizması).
        self.beton_kalip_kolon_kayitlari: Dict[tuple, Dict] = {}
        # Rev-160: kolon aracında boyutu çözümlenemeyen S/P adları (kat, ad) -> yazı handle'ı;
        # perde aracıyla alınınca listeden düşer
        self.okunamayan_elemanlar: Dict[tuple, Optional[str]] = {}
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

        # İhale Demir Metrajı — Aralıklı Donatı (Ø/aralık) dedup registry.
        # (kat_adi, handle) -> DemirBilgisi. Aynı yazı tekrar okunup/mesafesi
        # düzeltilirse ESKİ kaydın üzerine YAZAR (kolon betonundaki mükerrer
        # birikme bug'ının aynısı yaşanmasın diye, bkz. CLAUDE.md Rev-134).
        self.aralikli_donati_kayitlari: Dict[tuple, "DemirBilgisi"] = {}

        # Rev-137 Temel Kirişi (SBH) registry: yazi_handle -> satır dict.
        # Aynı SBH yazısı tekrar seçilirse kayıt GÜNCELLENİR (birikme yok).
        self.temel_kirisi_kayitlari: Dict[str, Dict] = {}

        # Rev-143 Perde registry: (kat_adi, poligon_handle) -> satır (ham
        # alan/çevre/düşüm; beton/kalıp her gösterimde o KATIN güncel
        # ayarıyla hesaplanır). Kat anahtarı şart: farklı DWG'lerde (katlarda)
        # aynı handle tekrar kullanılabilir.
        self.perde_kayitlari: Dict[tuple, Dict] = {}
        # Kat başına yükseklik esası — perde yazar, döşeme aracı okuyacak
        # (çift sayım kararı). yukseklik_ayari = AKTİF katınki.
        self.kat_yukseklik_ayarlari: Dict[str, "KatYukseklikAyari"] = {}
        self.yukseklik_ayari = KatYukseklikAyari() if KatYukseklikAyari else None

        # Rev-144 Döşeme / Rev-150 Kiriş satırları — ham girdiler; beton/kalıp
        # gösterimde hesaplanır. Rev-151: KAT BAZLI saklanır (kat -> liste);
        # `doseme_kayitlari` / `kiris_kayitlari` property'leri AKTİF katın
        # listesini verir (mükerrer handle kontrolü de kat içinde — handle
        # sadece bir DWG içinde benzersiz, bkz. Rev-143).
        self._doseme_kat_kayitlari: Dict[str, List[Dict]] = {}
        self._kiris_kat_kayitlari: Dict[str, List[Dict]] = {}
        # Rev-152 Merdiven kol / ara sahanlık satırları — kat bazlı, ham girdi
        self._merdiven_kat_kayitlari: Dict[str, List[Dict]] = {}

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
        self._proje_kayit_kur(parent, otomatik_kayit)

    # ══ Rev-168: PROJE KAYDET / AÇ + OTOMATİK KAYIT ══
    # Metraj kayıtları eskiden SADECE bellekteydi (program kapanınca / PC çökünce kayboluyordu).
    # Gerçek programda (ana pencereye bağlı açılınca) proje dosyası açılışta yüklenir, her
    # dakika değişiklik varsa ve pencere kapanırken kaydedilir. Testler (parent=None) gerçek
    # dosyaya DOKUNMAZ.
    PROJE_KAYIT_ARALIGI_MS = 60_000
    _PROJE_DURUM_ANAHTARLARI = (
        "demir_kat_verileri", "aralikli_donati_kayitlari", "beton_kalip_kolon_kayitlari",
        "okunamayan_elemanlar", "perde_kayitlari", "kat_yukseklik_ayarlari", "_doseme_kat_kayitlari",
        "_kiris_kat_kayitlari", "_merdiven_kat_kayitlari", "temel_kirisi_kayitlari", "radye_kayitlari",
    )

    def _proje_kayit_kur(self, parent, otomatik_kayit):
        self._otomatik_kayit_acik = (parent is not None) if otomatik_kayit is None else bool(otomatik_kayit)
        self._kayit_dosyasi = None
        self._son_kayit_imzasi = None
        self._proje_kayit_cubugu_olustur()
        if proje_kayit is None or not self._otomatik_kayit_acik:
            return
        try:
            self._kayit_dosyasi = proje_kayit.proje_dosyasi(self._kayit_proje_adi())
            if self._kayit_dosyasi.exists() or self._kayit_dosyasi.with_name(
                    self._kayit_dosyasi.stem + ".onceki.json").exists():
                self._proje_yukle(self._kayit_dosyasi, sessiz=True)
            else:
                self._kayit_durumu_yaz(f"Yeni proje — kayıtlar otomatik olarak {self._kayit_dosyasi.name} "
                                       "dosyasına yazılacak.")
        except Exception as e:
            logger.error(f"[PROJE KAYIT] açılış yüklemesi: {e}", exc_info=True)
            self._kayit_durumu_yaz(f"⚠ Kayıt yüklenemedi: {e}")
        self._otomatik_kayit_zamanlayici = QTimer(self)
        self._otomatik_kayit_zamanlayici.timeout.connect(self._otomatik_kaydet)
        self._otomatik_kayit_zamanlayici.start(self.PROJE_KAYIT_ARALIGI_MS)

    def _kayit_proje_adi(self) -> str:
        """Ana penceredeki aktif proje adı (soru SORMADAN); yoksa "Genel"."""
        try:
            ana = self.parent()
            pid = getattr(ana, "current_project_id", None)
            if pid and getattr(ana, "db", None) is not None:
                ad = ((ana.db.get_project(pid) or {}).get("ad") or "").strip()
                if ad:
                    return ad
        except Exception as e:
            logger.debug(f"[PROJE KAYIT] proje adı okunamadı: {e}")
        return "Genel"

    def _proje_kayit_cubugu_olustur(self):
        cubuk = QToolBar("Proje")
        cubuk.setMovable(False)
        cubuk.setStyleSheet(
            "QToolBar { background:#1f2a36; border-bottom:1px solid #2e86c1; spacing:6px; padding:3px; }"
            "QToolButton { color:white; background:#2e4053; border:1px solid #5d6d7e; border-radius:3px;"
            " padding:4px 10px; font-weight:bold; } QToolButton:hover { background:#3c5a73; }")
        for metin, ipucu, kisayol, fonk in (
                ("Kaydet", "Tüm metraj kayıtlarını (katlar, demir, kolon, perde, döşeme, saçak, kiriş, merdiven, "
                           "SBH, radye) proje dosyasına kaydeder. Ayrıca her dakika otomatik kaydedilir.",
                 "Ctrl+S", self._proje_kaydet),
                ("Farklı Kaydet…", "Projeyi seçtiğiniz bir dosyaya kaydeder (ör. başka bilgisayara taşımak için). "
                                   "Sonraki otomatik kayıtlar bu dosyaya yapılır.", None, self._proje_farkli_kaydet),
                ("Proje Aç…", "Daha önce kaydedilmiş bir metraj projesini açar (mevcut kayıtların yerine geçer).",
                 "Ctrl+O", self._proje_ac)):
            eylem = QAction(metin, self)
            eylem.setToolTip(ipucu)
            if kisayol:
                eylem.setShortcut(kisayol)
            eylem.triggered.connect(fonk)
            cubuk.addAction(eylem)
        self.proje_kayit_label = QLabel()
        self.proje_kayit_label.setStyleSheet("color:#aed6f1; padding-left:8px;")
        cubuk.addWidget(self.proje_kayit_label)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, cubuk)
        self._kayit_durumu_yaz("Kayıtlar otomatik saklanmıyor (test / bağımsız pencere) — 'Kaydet' ile kaydedin."
                               if not getattr(self, "_otomatik_kayit_acik", False) else "")

    def _kayit_durumu_yaz(self, metin: str):
        if hasattr(self, "proje_kayit_label"):
            self.proje_kayit_label.setText(metin)

    # ── durum topla / uygula ──
    def _proje_durumu_topla(self) -> Dict:
        d = {k: getattr(self, k, None) for k in self._PROJE_DURUM_ANAHTARLARI}
        d["aktif_kat_adi"] = self.aktif_kat_adi
        d["bk_elle_satirlar"] = self._bk_elle_satirlari_oku()
        ayar = {}
        for ad in ("kat_yuksekligi_spin", "perde_yukseklik_spin", "perde_doseme_spin", "doseme_varsayilan_h_spin",
                   "sacak_kalinlik_spin", "bk_fire_spin"):
            w = getattr(self, ad, None)
            if w is not None:
                ayar[ad] = w.value()
        if hasattr(self, "perde_esas_combo"):
            ayar["perde_esas"] = self.perde_esas_combo.currentData() or "tam"
        if hasattr(self, "perde_doseme_otomatik_chk"):
            ayar["perde_doseme_otomatik"] = self.perde_doseme_otomatik_chk.isChecked()
        ayar["sacak_kalinlik_elle"] = bool(getattr(self, "_sacak_kalinlik_elle", False))
        d["ayarlar"] = ayar
        return d

    def _bk_elle_satirlari_oku(self) -> List[Dict]:
        """Beton & Kalıp tablosunun ELLE eklenen satırları (kolon/perde araçlarının satırları
        registry'den yeniden kurulur, kaydedilmez)."""
        satirlar = []
        t = getattr(self, "beton_kalip_table", None)
        if t is None:
            return satirlar
        for row in range(t.rowCount()):
            ilk = t.item(row, 0)
            if ilk is not None and ilk.data(Qt.ItemDataRole.UserRole):
                continue
            satirlar.append({"metin": [t.item(row, c).text() if t.item(row, c) else "" for c in range(t.columnCount())],
                             "tam": {str(c): self._bk_hucre_degeri(row, c) for c in self.BK_SAYI_KOLONLARI}})
        return satirlar

    def _proje_durumu_uygula(self, d: Dict):
        varsayilan = {"demir_kat_verileri": [], "radye_kayitlari": []}
        for k in self._PROJE_DURUM_ANAHTARLARI:
            deger = d.get(k)
            if deger is None:
                deger = list(varsayilan[k]) if k in varsayilan else {}
            setattr(self, k, deger)
        katlar = [kd["kat_adi"] for kd in self.demir_kat_verileri]
        self.aktif_kat_adi = d.get("aktif_kat_adi") if d.get("aktif_kat_adi") in katlar else (katlar[0] if katlar else "")
        ayar = d.get("ayarlar") or {}
        for ad, deger in ayar.items():
            w = getattr(self, ad, None)
            if w is not None and hasattr(w, "setValue"):
                w.blockSignals(True)
                w.setValue(deger)
                w.blockSignals(False)
        if "perde_esas" in ayar and hasattr(self, "perde_esas_combo"):
            self.perde_esas_combo.blockSignals(True)
            self.perde_esas_combo.setCurrentIndex(max(0, self.perde_esas_combo.findData(ayar["perde_esas"])))
            self.perde_esas_combo.blockSignals(False)
        if "perde_doseme_otomatik" in ayar and hasattr(self, "perde_doseme_otomatik_chk"):
            self.perde_doseme_otomatik_chk.blockSignals(True)
            self.perde_doseme_otomatik_chk.setChecked(bool(ayar["perde_doseme_otomatik"]))
            self.perde_doseme_otomatik_chk.blockSignals(False)
        self._sacak_kalinlik_elle = bool(ayar.get("sacak_kalinlik_elle", False))
        # kat listesi
        self._demir_kat_listesini_guncelle()
        if self.aktif_kat_adi in katlar:
            self.demir_kat_listesi.setCurrentRow(katlar.index(self.aktif_kat_adi))
        for ad in ("btn_kat_sil",):
            if hasattr(self, ad):
                getattr(self, ad).setEnabled(bool(katlar))
        var_demir = any(kd.get("demirler") for kd in self.demir_kat_verileri)
        for ad in ("btn_demir_excel", "btn_kesime_aktar"):
            if hasattr(self, ad):
                getattr(self, ad).setEnabled(var_demir)
        # Beton & Kalıp tablosu: elle satırlar + kolon aracı satırları (perde satırları _perde_tablo_yenile'de)
        t = getattr(self, "beton_kalip_table", None)
        if t is not None:
            t.setRowCount(0)
            for satir in d.get("bk_elle_satirlar") or []:
                row = t.rowCount()
                t.insertRow(row)
                tam = satir.get("tam") or {}
                for col, metin in enumerate(satir.get("metin") or []):
                    item = QTableWidgetItem(metin)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if str(col) in tam:
                        item.setData(Qt.ItemDataRole.UserRole, float(tam[str(col)]))
                    t.setItem(row, col, item)
            for kat in dict.fromkeys(k for (k, _a) in self.beton_kalip_kolon_kayitlari):
                self._beton_kalip_kat_kolon_satirlarini_yeniden_olustur(kat)
        # Kata bağlı tüm sekmeler (perde ayarı + tablo, kiriş, döşeme, merdiven, kat özeti)
        self._aktif_kat_degisti()
        for fonk in ("_temel_kirisi_tablo_yenile", "_radye_degisti", "_beton_kalip_toplamlar_guncelle",
                     "_kat_ozeti_yenile"):
            if hasattr(self, fonk):
                try:
                    getattr(self, fonk)()
                except Exception as e:
                    logger.error(f"[PROJE KAYIT] {fonk}: {e}", exc_info=True)

    @staticmethod
    def _proje_siniflari() -> Dict:
        siniflar = {}
        if DemirBilgisi is not None:
            siniflar["DemirBilgisi"] = DemirBilgisi
        if KatYukseklikAyari is not None:
            siniflar["KatYukseklikAyari"] = KatYukseklikAyari
        return siniflar

    def _durum_imzasi(self, durum: Dict) -> str:
        import hashlib
        import json as _json
        return hashlib.sha1(_json.dumps(proje_kayit.serilestir(durum), ensure_ascii=False,
                                        sort_keys=True, default=str).encode("utf-8")).hexdigest()

    # ── kaydet / aç ──
    def _proje_dosyaya_yaz(self, yol, otomatik: bool = False) -> bool:
        if proje_kayit is None:
            return False
        try:
            durum = self._proje_durumu_topla()
            imza = self._durum_imzasi(durum)
            if otomatik and imza == self._son_kayit_imzasi:
                return False   # değişiklik yok
            proje_kayit.kaydet(yol, durum, self._kayit_proje_adi())
            self._son_kayit_imzasi = imza
            self._kayit_durumu_yaz(f"{'Otomatik kaydedildi' if otomatik else 'Kaydedildi'} "
                                   f"{datetime.now().strftime('%H:%M')} — {Path(yol).name} — "
                                   f"{proje_kayit.durum_ozeti(durum)}")
            logger.info(f"[PROJE KAYIT] {'otomatik ' if otomatik else ''}kaydedildi: {yol}")
            return True
        except Exception as e:
            logger.error(f"[PROJE KAYIT] kaydetme hatası ({yol}): {e}", exc_info=True)
            self._kayit_durumu_yaz(f"⚠ KAYDEDİLEMEDİ: {e}")
            if not otomatik:
                QMessageBox.critical(self, "Kaydetme Hatası", f"Proje kaydedilemedi:\n{e}")
            return False

    def _otomatik_kaydet(self):
        if self._otomatik_kayit_acik and self._kayit_dosyasi is not None:
            self._proje_dosyaya_yaz(self._kayit_dosyasi, otomatik=True)

    def _proje_kaydet(self):
        if proje_kayit is None:
            QMessageBox.warning(self, "Uyarı", "Kayıt modülü yüklenemedi.")
            return
        if self._kayit_dosyasi is None:
            self._kayit_dosyasi = proje_kayit.proje_dosyasi(self._kayit_proje_adi())
        if self._proje_dosyaya_yaz(self._kayit_dosyasi):
            self.statusBar().showMessage(f"Kaydedildi: {self._kayit_dosyasi}", 5000)

    def _proje_farkli_kaydet(self):
        if proje_kayit is None:
            return
        varsayilan = str(proje_kayit.proje_dosyasi(self._kayit_proje_adi()))
        yol, _ = QFileDialog.getSaveFileName(self, "Projeyi Farklı Kaydet", varsayilan,
                                             "Metraj Projesi (*.json)")
        if not yol:
            return
        if not yol.lower().endswith(".json"):
            yol += ".json"
        if self._proje_dosyaya_yaz(yol):
            self._kayit_dosyasi = Path(yol)

    def _proje_ac(self):
        if proje_kayit is None:
            return
        yol, _ = QFileDialog.getOpenFileName(self, "Metraj Projesi Aç", str(proje_kayit.metraj_kayit_klasoru()),
                                             "Metraj Projesi (*.json)")
        if not yol:
            return
        mevcut = self._proje_durumu_topla()
        if self._durum_imzasi(mevcut) != self._son_kayit_imzasi and proje_kayit.durum_ozeti(mevcut) != "Kat: 0":
            S = QMessageBox.StandardButton
            cevap = QMessageBox.question(
                self, "Proje Aç", "Açık projede kaydedilmemiş değişiklik olabilir. Önce kaydedilsin mi?",
                S.Yes | S.No | S.Cancel, S.Yes)
            if cevap == S.Cancel:
                return
            if cevap == S.Yes:
                self._proje_kaydet()
        if self._proje_yukle(yol):
            self._kayit_dosyasi = Path(yol)

    def _proje_yukle(self, yol, sessiz: bool = False) -> bool:
        try:
            veri = proje_kayit.yukle(yol, self._proje_siniflari())
            self._proje_durumu_uygula(veri["durum"])
            self._son_kayit_imzasi = self._durum_imzasi(self._proje_durumu_topla())
            zaman = (veri.get("kayit_zamani") or "").replace("T", " ")
            yedek = " (bozuk dosya yerine ÖNCEKİ sürüm)" if veri.get("yuklenen_dosya") != str(yol) else ""
            self._kayit_durumu_yaz(f"Yüklendi{yedek}: {Path(yol).name} ({zaman}) — "
                                   f"{proje_kayit.durum_ozeti(veri['durum'])}")
            logger.info(f"[PROJE KAYIT] yüklendi: {veri.get('yuklenen_dosya')}")
            return True
        except Exception as e:
            logger.error(f"[PROJE KAYIT] yükleme hatası ({yol}): {e}", exc_info=True)
            self._kayit_durumu_yaz(f"⚠ Yüklenemedi: {e}")
            if not sessiz:
                QMessageBox.critical(self, "Açma Hatası", f"Proje açılamadı:\n{e}")
            return False

    def closeEvent(self, event):
        # Rev-168: kapanırken son durum kaydedilir (otomatik kayıt açıksa)
        try:
            self._otomatik_kaydet()
        except Exception as e:
            logger.error(f"[PROJE KAYIT] kapanış kaydı: {e}", exc_info=True)
        super().closeEvent(event)

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

        # Sol paneli DIŞ bir QScrollArea içine al: içerik pencere boyundan
        # uzun olduğunda (Demir Metrajı sekmesi gibi kalemli bölümlerde sık
        # görülüyor) tek bir dış kaydırma çubuğuyla erişilebilsin — aksi
        # halde Qt, iç içe sabit-yükseklikli kutuları (acad_tab_widget'in
        # setMinimumHeight(600) değeri gibi) pencereye sığdırmak için
        # sessizce sıkıştırıyor ve alt taraftaki butonlar (DEMİR EXCEL'E
        # AKTAR, KESİM LİSTESİNE AKTAR vb.) hem görünmüyor hem de hangi iç
        # kutunun kaydırılması gerektiği belli olmuyordu (bkz. Rev-116).
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setWidget(left_panel)
        main_layout.addWidget(left_scroll, 1)

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
        # Rev-154: "Genel Ayarlar" arayüzden KALDIRILDI (kullanıcı isteği). Widget'lar
        # oluşturulmaya devam ediyor — kat_yuksekligi_spin (kolon okuma varsayılanı),
        # doseme_kalinligi_spin, rbtn_net/_alan_bilgi_label başka metodlarca okunuyor
        # (Rev-145 kuralı: erişilen self.x silinmez, sadece layout'a eklenmez).
        self.settings_group.setVisible(False)

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
        # Sekme kaldırıldı (sadece Kaba İnşaat aktif) — widget canlı tutuluyor ki
        # self.ince_toplam_label / self.ince_maliyet_label gibi child referanslar çökmesin.
        self._ince_isler_tab_gizli = ince_isler_tab

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

        # Eleman Tipi seçimi — izlenebilirlik icin (Kesim Listesi'nde "Not/Poz"
        # sutununda gorunur). Kesim optimizasyon algoritmasi TUM eleman
        # tiplerini ayni (sabit boy) muamele eder, bu secim kesim planini
        # ETKILEMEZ (bkz. CLAUDE.md Rev-117 karari, 2026-08-19).
        eleman_tipi_layout = QHBoxLayout()
        eleman_tipi_layout.addWidget(QLabel("Eleman Tipi:"))
        self.demir_eleman_tipi_combo = QComboBox()
        self.demir_eleman_tipi_combo.addItems(
            ["Kolon", "Perde", "Kiriş", "Döşeme", "Temel", "Diğer"]
        )
        self.demir_eleman_tipi_combo.setToolTip(
            "Şimdi seçeceğiniz demirlerin ait olduğu eleman tipi.\n"
            "Sadece izlenebilirlik/raporlama içindir — Kesim Listesi'nde\n"
            "'Not/Poz' sütununda görünür. Kesim optimizasyonunu (fire\n"
            "hesabını) ETKİLEMEZ, tüm tipler aynı şekilde kesilir.\n\n"
            "Her eleman tipi için ayrı ayrı seçip 'DEMİR METRAJI AL' ile aktarın."
        )
        eleman_tipi_layout.addWidget(self.demir_eleman_tipi_combo, 1)
        demir_layout.addLayout(eleman_tipi_layout)

        # Demir aksiyon butonları — dikey yığın yerine tek sırada (sayfa
        # yüksekliğini ~150px azaltır, kaydırma ihtiyacını düşürür).
        demir_btn_row = QHBoxLayout()
        demir_btn_row.setSpacing(6)

        # Demir Metraj butonu
        self.btn_acad_demir = QPushButton(" DEMİR METRAJİ AL")
        self.btn_acad_demir.clicked.connect(self._autocad_demir_metraj)
        self.btn_acad_demir.setEnabled(False)
        self.btn_acad_demir.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8B4513, stop:1 #654321);
        color: white;
        font-weight: bold;
        font-size: 10pt;
        padding: 8px 4px;
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
        demir_btn_row.addWidget(self.btn_acad_demir)

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
        font-size: 10pt;
        padding: 8px 4px;
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
        demir_btn_row.addWidget(self.btn_kolon_grup)

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
        font-size: 10pt;
        padding: 8px 4px;
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
        demir_btn_row.addWidget(self.btn_kolon_filizi)

        # İstinat Demir Hesabı — "Poza Göre Donatı Metraj Tablosu" okuma
        # butonu (bkz. CLAUDE.md Rev-128/129/130). Koordinat bazlı satır/
        # sütun kümelemesi + başlık tespiti + kg/ton hesabı yapar.
        self.btn_poz_donati = QPushButton(" İSTİNAT DEMİR HESABI")
        self.btn_poz_donati.clicked.connect(self._autocad_poz_donati_oku)
        self.btn_poz_donati.setEnabled(False)
        self.btn_poz_donati.setToolTip(
        "Poza Göre Donatı Metraj Tablosunu (POZ/ADET/ÇAP/BOY + çap bazlı\n"
        "TOPLAM sütunları) AutoCAD'den okur:\n"
        "• Tüm tabloyu kutu çizerek seçin (başlık satırı dahil)\n"
        "• Program POZ/ADET/ÇAP/BOY sütunlarını koordinata göre otomatik tanır\n"
        "• Çapa göre toplam ağırlık (kg/ton) hesaplar\n"
        "• Tablodaki hazır TOPLAM sütunuyla karşılaştırıp sapma varsa uyarır"
        )
        self.btn_poz_donati.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6c3483, stop:1 #512e5f);
        color: white;
        font-weight: bold;
        font-size: 10pt;
        padding: 8px 4px;
        border: 2px solid #8e44ad;
        }
        QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8e44ad, stop:1 #6c3483);
        }
        QPushButton:disabled {
        background: #444;
        color: #666;
        }
        """)
        demir_btn_row.addWidget(self.btn_poz_donati)

        demir_layout.addLayout(demir_btn_row)

        # ── İhale Demir Metrajı — Aralıklı Donatı (Ø/aralık) okuma ─────────
        # Adet yerine dağılım aralığıyla etiketlenen donatılar için ayrı
        # bölüm (bkz. CLAUDE.md Rev-136). Mevcut adetli demir okuma
        # araçlarından TAMAMEN AYRI bir format/akış olduğu için kendi
        # başlığı altında gösteriliyor.
        ihale_demir_baslik = QLabel("İhale Demir Metrajı")
        ihale_demir_baslik.setStyleSheet(
            "color:#d4a017; font-weight:bold; font-size:11pt; padding-top:6px;"
        )
        demir_layout.addWidget(ihale_demir_baslik)

        ihale_demir_row = QHBoxLayout()
        ihale_demir_row.setSpacing(6)

        self.btn_aralikli_donati = QPushButton(" ARALIKLI DONATI OKU (Ø/ARALIK)")
        self.btn_aralikli_donati.clicked.connect(self._autocad_aralikli_donati_oku)
        self.btn_aralikli_donati.setEnabled(False)
        self.btn_aralikli_donati.setToolTip(
            "Adet yerine dağılım aralığıyla etiketlenen donatıları okur:\n"
            "• Format: Ø14/20 L=500 (çap/aralık_cm L=çubuk_boyu_cm)\n"
            "• Format: Ø14/20 l=300 (küçük l) radye alt ilavesi de okunur\n"
            "• ÖLÇÜDEN (varsayılan): yazıyı seç + ENTER, dağılım ölçüsünü\n"
            "  (DIMENSION) seç + ENTER → adet = ölçü ÷ aralık + 1; döngü kendiliğinden\n"
            "  sürer, yazı seçiminde boş ENTER ile biter. Ölçü yoksa boş ENTER = elle gir\n"
            "• ELLE: her turda TEK yazı seçin, mesafeyi (m) yazın\n"
            "• Seçilen yazı ve ölçü YEŞİLE boyanır (hangileri alındı görünür)\n"
            "• 'Son Ekleneni Geri Al' ile yanlış girilen son demiri düzeltin\n"
            "• Döşeme iki yönlüyse her yönü AYRI okutun (program birleştirmez)"
        )
        self.btn_aralikli_donati.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #b7950b, stop:1 #7d6608);
        color: white;
        font-weight: bold;
        font-size: 10pt;
        padding: 8px 4px;
        border: 2px solid #d4ac0d;
        }
        QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #d4ac0d, stop:1 #b7950b);
        }
        QPushButton:disabled {
        background: #444;
        color: #666;
        }
        """)
        ihale_demir_row.addWidget(self.btn_aralikli_donati)
        ihale_demir_row.addStretch(1)

        demir_layout.addLayout(ihale_demir_row)

        # Demir birim — her zaman cm (L= değerleri projede cm cinsinden)
        demir_birim_layout = QHBoxLayout()
        demir_birim_layout.addWidget(QLabel("Boy Birimi: cm"))
        self.demir_birim_combo = QComboBox()
        self.demir_birim_combo.addItems(["cm"])
        self.demir_birim_combo.setCurrentIndex(0)
        self.demir_birim_combo.setEnabled(False)
        self.demir_birim_combo.setVisible(False)  # Tek seçenek, göstermeye gerek yok
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
        self.demir_kat_listesi.setMinimumHeight(120)
        self.demir_kat_listesi.setMaximumHeight(180)
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
        self.btn_demir_excel.setToolTip(
            "Bu ekranda topladığınız demir (çap/boy/adet/ağırlık) verisini\n"
            "kat kat ayrı sayfalar halinde Excel'e aktarır."
        )
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

        # Kesim Listesine Aktar butonu — Yapısal Demir Hesaplama penceresini
        # açar/öne getirir ve toplanan demirleri doğrudan Kesim Listesi'ne
        # aktarır (AutoCAD'e ikinci kez bağlanmaya veya Excel gidip-gelmeye
        # gerek kalmadan, bkz. Rev-114).
        self.btn_kesime_aktar = QPushButton(" KESİM LİSTESİNE AKTAR")
        self.btn_kesime_aktar.setToolTip(
            "Tüm katlarda toplanan demirleri, 'Yapısal Demir Hesaplama'\n"
            "penceresinin Kesim Listesi sekmesine doğrudan aktarır.\n"
            "Pencere açık değilse otomatik açılır."
        )
        self.btn_kesime_aktar.clicked.connect(self._kesim_listesine_aktar)
        self.btn_kesime_aktar.setEnabled(False)
        self.btn_kesime_aktar.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #d35400, stop:1 #a04000);
        color: white;
        font-weight: bold;
        padding: 8px;
        border: 2px solid #e67e22;
        }
        QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e67e22, stop:1 #d35400);
        }
        QPushButton:disabled {
        background: #444;
        color: #666;
        }
        """)
        demir_layout.addWidget(self.btn_kesime_aktar)

        # Çap Bazlı Tonaj butonu — tüm katlardaki demirleri çapa göre
        # gruplayıp toplam boy/ağırlık/tonaj gösterir (sipariş için).
        self.btn_cap_tonaj = QPushButton(" ÇAP BAZLI TONAJ")
        self.btn_cap_tonaj.setToolTip(
            "Tüm katlarda toplanan demirleri çapa (Ø8, Ø12, Ø16...) göre\n"
            "gruplayıp her çap için toplam boy, ağırlık ve tonajı gösterir."
        )
        self.btn_cap_tonaj.clicked.connect(self._cap_bazli_tonaj_goster)
        # DEMİR EXCEL'E AKTAR / KESİM LİSTESİNE AKTAR butonlarının aksine
        # kasıtlı olarak hep aktif — veri yoksa tıklayınca _cap_bazli_tonaj_goster
        # zaten anlaşılır bir uyarı gösteriyor (donuk/tıklanamaz buton yerine).
        self.btn_cap_tonaj.setEnabled(True)
        self.btn_cap_tonaj.setStyleSheet("""
        QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2980b9, stop:1 #1f618d);
        color: white;
        font-weight: bold;
        padding: 8px;
        border: 2px solid #3498db;
        }
        QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9);
        }
        QPushButton:disabled {
        background: #444;
        color: #666;
        }
        """)
        demir_layout.addWidget(self.btn_cap_tonaj)

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

        # Rev-134: Kolon boyutunu geometriden değil, boyut YAZISINDAN
        # ("SZ07 50/50") toplu okuyan buton — geometri (BoundingBox/Area)
        # 1/50 ölçek + mm birim belirsizliğinde güvenilmez çıktı (Rev-133).
        self.btn_bk_kolon_yazi = QPushButton(" Kolon Yazısından Toplu Oku")
        self.btn_bk_kolon_yazi.clicked.connect(self._beton_kalip_kolon_yazisindan_oku)
        self.btn_bk_kolon_yazi.setEnabled(False)
        self.btn_bk_kolon_yazi.setToolTip(
        "AutoCAD'de bir bölgeyi kutuyla seçin — içindeki TÜM boyut\n"
        "yazıları ('SZ07 50/50' gibi) okunur. İsmi S/P ile başlayanlar\n"
        "KOLON sayılır, K ile başlayanlar (kiriş) ve tanımsızlar atlanır."
        )
        self.btn_bk_kolon_yazi.setStyleSheet("""
        QPushButton {
        background: #4a1a5a;
        color: #ce93d8;
        font-weight: bold;
        padding: 6px 14px;
        border: 1px solid #ce93d8;
        border-radius: 4px;
        }
        QPushButton:hover {
        background: #6a2a7a;
        }
        QPushButton:disabled {
        background: #222;
        color: #555;
        border-color: #444;
        }
        """)
        bk_form_layout.addWidget(self.btn_bk_kolon_yazi, 4, 0, 1, 6)

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
        self.beton_kalip_table.setColumnCount(10)
        self.beton_kalip_table.setHorizontalHeaderLabels(
        ["Kat", "Eleman", "Adet", "Ölçü1 (m)", "Ölçü2 (m)", "Ölçü3 (m)",
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
        self._beton_kalip_tab_gizli = beton_kalip_tab

        # Rev-137: Temel Kirişi (SBH) Beton + Kalıp sekmesi
        _tk_idx = kaba_insaat_sub_tabs.addTab(self._temel_kirisi_sekmesi_olustur(), " Temel Kirişi")
        kaba_insaat_sub_tabs.setTabToolTip(
            _tk_idx,
            "SBH temel kirişleri: yazıdan kesit + kenar çizgisinden net uzunluk → "
            "beton m³ ve kalıp m² (sadece 2 yan yüz)."
        )
        # Rev-139: Radye Temel Beton + Kalıp sekmesi
        _radye_idx = kaba_insaat_sub_tabs.addTab(self._radye_sekmesi_olustur(), " Radye Temel")
        kaba_insaat_sub_tabs.setTabToolTip(
            _radye_idx, "Radye temel: net alan × kalınlık → beton, çevre × kalınlık → kalıp."
        )
        # Rev-143: Perde (L/T/U kesit) Beton + Kalıp sekmesi
        _perde_idx = kaba_insaat_sub_tabs.addTab(self._perde_sekmesi_olustur(), " Perde")
        kaba_insaat_sub_tabs.setTabToolTip(
            _perde_idx,
            "Perde (L/T/U kesit): kesit alanı × yükseklik → beton, "
            "kalıplanan kenarlar toplamı × yükseklik → kalıp."
        )
        # Rev-144: Döşeme (plak) Beton + Kalıp sekmesi
        _doseme_idx = kaba_insaat_sub_tabs.addTab(self._doseme_sekmesi_olustur(), " Döşeme")
        kaba_insaat_sub_tabs.setTabToolTip(
            _doseme_idx,
            "Plak döşeme: net alan × kalınlık → beton; alt kalıp + kenar kalıbı → kalıp. "
            "Alan kiriş iç yüzleri arasında."
        )
        # Rev-150: Kiriş (normal, döşeme altı) Beton + Kalıp sekmesi
        _kiris_idx = kaba_insaat_sub_tabs.addTab(self._kiris_sekmesi_olustur(), " Kiriş")
        kaba_insaat_sub_tabs.setTabToolTip(
            _kiris_idx,
            "Düz kiriş: b × h × L_net → beton; alt + yan yüzler (döşeme tarafında h − t) → kalıp. "
            "L_net kolon/perde yüzleri arası."
        )
        # Rev-152: Merdiven (plak merdiven kolu + ara sahanlık) Beton + Kalıp sekmesi
        _merdiven_idx = kaba_insaat_sub_tabs.addTab(self._merdiven_sekmesi_olustur(), " Merdiven")
        kaba_insaat_sub_tabs.setTabToolTip(
            _merdiven_idx,
            "Plak merdiven: kol (n, rıht, basamak, kol eni, plak kalınlığı) ve ARA sahanlık → beton m³, "
            "kalıp m² (alt yüz / rıht / yan / kenar). Kat sahanlığı Döşeme sekmesinde alınır."
        )
        # Rev-151: Kat bazlı beton + kalıp özeti (kolon/perde/kiriş/döşeme + Temel)
        _ozet_idx = kaba_insaat_sub_tabs.addTab(self._kat_ozeti_sekmesi_olustur(), " Kat Özeti")
        kaba_insaat_sub_tabs.setTabToolTip(
            _ozet_idx,
            "Tüm sekmelerdeki beton (m³) ve kalıp (m²) miktarları kat kat, tek tabloda. "
            "Radye ve temel kirişi 'Temel' satırında."
        )
        kaba_insaat_sub_tabs.currentChanged.connect(
            lambda i, idx=_ozet_idx: self._kat_ozeti_yenile() if i == idx else None)

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
        # Sekme kaldırıldı (sadece Demir Metrajı aktif) — widget canlı tutuluyor.
        self._hizli_kesif_tab_gizli = hizli_kesif_tab

        # Rev-133 (2026-09-06): "Beton & Kalıp" sekmesi LISP kat yüksekliği
        # bug fix'inin test edilebilmesi için tekrar görünür yapıldı — sekme
        # çubuğu artık gizlenmiyor (birden fazla alt sekme var).
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
        # Sekme kaldırıldı (sadece Kaba İnşaat aktif)
        self._coklu_kat_tab_gizli = coklu_kat_tab

        # (Kaba Yapı sekmesi → Kaba İnşaat > Hızlı Keşif alt sekmesine taşındı)

        # SEKME 4: LISP ARAÇLARI
        # Rev-133 (2026-09-06): kat yüksekliği bug fix'inin test edilebilmesi
        # için tekrar görünür yapıldı.
        lisp_tab = self._lisp_araclari_tab_olustur()
        self.acad_tab_widget.addTab(lisp_tab, " LISP Araçları")
        self._lisp_tab_gizli = lisp_tab

        # Sekme değişikliği callback'i
        self.acad_tab_widget.currentChanged.connect(self._sekme_degisti)

        self.acad_tab_widget.setMinimumHeight(600)
        acad_main_layout.addWidget(self.acad_tab_widget)

        acad_group.setLayout(acad_main_layout)
        parent_layout.addWidget(acad_group)

        # DXF yükle / HESAPLA / Temizle / Duvar-Kiriş Excel / Metraj Cetveline Aktar /
        # Tedarikçiye Teklif butonları kullanıcı isteğiyle arayüzden kaldırıldı (Rev-145).
        # Metotlar duruyor; _clear_all ve _load_dxf_file durum etiketine yazdığı için
        # etiket ekrana eklenmeden tutuluyor.
        self.dxf_status_label = QLabel("DXF dosyasi yuklenmedi")

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
            self.btn_poz_donati.setEnabled(True)
            self.btn_aralikli_donati.setEnabled(True)
            self.btn_kat_ekle.setEnabled(True)
            self.btn_bk_acad_olc.setEnabled(True)
            self.btn_bk_kolon_yazi.setEnabled(True)
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
            _secili_tip = self.demir_eleman_tipi_combo.currentText()
            QMessageBox.information(
                self, f"Demir Metrajı - {self.aktif_kat_adi}",
                f" Aktif Kat: {self.aktif_kat_adi}\n"
                f" Eleman Tipi: {_secili_tip}\n\n"
                "AutoCAD penceresine geçin ve SADECE bu eleman tipine ait\n"
                "DEMİR YAZILARINI seçin.\n\n"
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

            # Seçilen eleman tipini tüm başarılı demirlere etiketle
            secili_eleman_tipi = self.demir_eleman_tipi_combo.currentText()
            for _d in rapor["basarili"]:
                _d.eleman_tipi = secili_eleman_tipi

            # Başarılı sonuç mesajı
            ozet = f"DEMİR METRAJ RAPORU — {secili_eleman_tipi}\n"
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
            self.btn_kesime_aktar.setEnabled(True)

            logger.info(f"'{self.aktif_kat_adi}' katına {len(rapor['basarili'])} demir eklendi")

        except Exception as e:
            logger.error(f"Demir metraj hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Demir metrajı alınırken hata:\n{e}")

    def _aralikli_donati_kat_satirlarini_yeniden_olustur(self, kat_adi: str):
        """Belirtilen katın 'aralıklı donatı' kaynaklı demir satırlarını
        registry'den (self.aralikli_donati_kayitlari) yeniden inşa eder.

        Neyi çözüyoruz? Kullanıcı aynı yazıyı (aynı AutoCAD handle) tekrar
        okutup mesafeyi düzeltirse, ESKİ satır silinmeden yeni satır
        EKLENİRSE toplam sessizce büyür — kolon betonunda yaşanan mükerrer
        birikme bug'ının aynısı (bkz. CLAUDE.md Rev-134). Bu yüzden bu
        katın registry'de bilinen TÜM handle'larına ait eski satırlar
        önce silinir, sonra registry'deki güncel haliyle yeniden eklenir.
        Manuel eklenmiş veya başka araçlarla (Demir Metrajı Al, Kolon
        Filizi vb.) eklenmiş satırlara DOKUNULMAZ (onların handle'ı bu
        registry'de yok).
        """
        kat_data = next(
        (k for k in self.demir_kat_verileri if k["kat_adi"] == kat_adi), None
        )
        if kat_data is None:
            return
        bu_kat_handleleri = {
        h for (k, h) in self.aralikli_donati_kayitlari if k == kat_adi
        }
        kat_data["demirler"] = [
        d for d in kat_data["demirler"] if d.handle not in bu_kat_handleleri
        ]
        for (k, h), demir in self.aralikli_donati_kayitlari.items():
            if k == kat_adi:
                kat_data["demirler"].append(demir)

    def _autocad_aralikli_donati_oku(self):
        """Aralıklı donatı (Ø/aralık) yazılarını AutoCAD'den TEK TEK,
        döngüsel seçimle okur, her biri için hemen dağılım mesafesi alıp
        aktif kata ekler.

        İhale Demir Metrajı, Aşama 3 güncelleme (bkz. CLAUDE.md Rev-136 —
        "radye gibi dağınık donatı" senaryosu). Kutu ile toplu okuma yerine
        DÖNGÜSEL tek-obje seçimi kullanılıyor: her turda kullanıcı bir yazı
        seçer, hemen mesafe girer, obje YEŞİLE boyanır — böylece hangi
        demirlerin alındığı çizimde gözle görülür, aynı demiri iki kez
        sayma/atlama riski düşer (bkz. AralikliDonatiDonguPaneli). Mükerrer
        okuma, handle bazlı registry ile engellenir (bkz.
        _aralikli_donati_kat_satirlarini_yeniden_olustur).
        """
        try:
            if not self.acad_connector or not self.acad_connector.bagli:
                QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
                return

            if not self.aktif_kat_adi:
                QMessageBox.warning(self, "Uyarı", "Önce bir kat ekleyin ve seçin!")
                return

            QMessageBox.information(
            self, "İhale Demir Metrajı — Aralıklı Donatı Oku",
            "Adet yerine dağılım aralığıyla etiketlenen donatıları\n"
            "(örn. Ø14/20 L=500) TEK TEK okuyacaksınız.\n\n"
            "Açılacak panelde 'Demir Seç' butonuna basıp AutoCAD'de\n"
            "TEK bir yazı seçin — hemen dağılım mesafesi sorulacak,\n"
            "obje YEŞİLE boyanacak. Bitirince panelde 'Bitti — Aktif\n"
            "Kata Ekle'ye basın.\n\n"
            "Döşeme iki yönlüyse HER YÖNÜ AYRI okutun — program\n"
            "iki yönü otomatik birleştirmez."
            )

            mevcut_handleler = {
            h for (k, h) in self.aralikli_donati_kayitlari if k == self.aktif_kat_adi
            }
            panel = AralikliDonatiDonguPaneli(self.acad_connector, mevcut_handleler, self)
            if panel.exec() != QDialog.DialogCode.Accepted:
                return

            satirlar = panel.sonuclar()
            if not satirlar:
                QMessageBox.warning(
                self, "Uyarı",
                "Hiçbir donatı toplanmadığı için eklenecek veri yok."
                )
                return

            eleman_tipi = self.demir_eleman_tipi_combo.currentText()
            for s in satirlar:
                d = DemirBilgisi(
                handle=s.get("handle", ""),
                orijinal_metin=(
                f"Ø{s['cap']}/{s['aralik_cm']:.0f} L={s['boy_cm']:.0f}cm "
                f"(mesafe={s['mesafe_m']:.2f}m, adet={s['adet']})"
                ),
                katman=s.get("layer", ""),
                )
                d.adet = s["adet"]
                d.cap = s["cap"]
                d.boy = s["boy_cm"]
                d.toplam_boy = s["toplam_boy_m"]
                d.agirlik_birim = s["agirlik_birim"]
                d.toplam_agirlik = s["toplam_agirlik_kg"]
                d.gecerli = True
                d.eleman_tipi = eleman_tipi

                # Mükerrer engelleme: (kat, handle) anahtarıyla ESKİ kaydın
                # üzerine yaz — asla ayrı bir satır olarak biriktirme.
                self.aralikli_donati_kayitlari[(self.aktif_kat_adi, d.handle)] = d

            self._aralikli_donati_kat_satirlarini_yeniden_olustur(self.aktif_kat_adi)
            self._demir_kat_listesini_guncelle()
            self.btn_demir_excel.setEnabled(True)
            self.btn_kesime_aktar.setEnabled(True)

            QMessageBox.information(
            self, "İhale Demir Metrajı — Eklendi",
            f"'{self.aktif_kat_adi}' katına {len(satirlar)} aralıklı donatı eklendi.\n\n"
            f"(Aynı yazı tekrar okunursa mükerrer eklenmez, üzerine yazılır.)"
            )
            logger.info(
            f"'{self.aktif_kat_adi}' katına {len(satirlar)} aralıklı donatı eklendi"
            )

        except Exception as e:
            logger.error(f"Aralıklı donatı okuma hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Hata:\n{e}")

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
            self.btn_kesime_aktar.setEnabled(True)

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
            self.btn_kesime_aktar.setEnabled(True)
            logger.info(f"'{self.aktif_kat_adi}' katına {len(rapor['basarili'])} kolon filizi demiri eklendi")

        except Exception as e:
            logger.error(f"Kolon filizi okuma hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Kolon filizi okuma sırasında hata:\n{e}")

    def _poz_donati_tek_tablo_oku(self, tablo_no: int):
        """Tek bir 'Poza Göre Donatı Metraj Tablosu' seçtirip poz kayıtlarını
        döndürür (henüz hesap/DemirBilgisi'ye çevrim YOK — bu, birden fazla
        tabloyu tek tek toplayıp SONUNDA birlikte hesaplayabilmek için ayrı
        tutuldu, bkz. _autocad_poz_donati_oku).

        ÖNEMLİ: Birden fazla tablo AYNI ANDA (tek kutu ile) seçilirse
        koordinat kümelemesi tabloları birbirine karıştırır (kullanıcı
        gerçek testte bunu yaşadı — 770 obje 3 satır x 5 sütuna sıkıştı).
        Bu yüzden HER ÇAĞRIDA sadece TEK bir tablo seçtirilir; birden fazla
        tablo varsa çağıran (bkz. _autocad_poz_donati_oku) bu metodu birden
        çok kez çağırır.

        Returns:
            (poz_kayitlari_listesi, iptal_edildi_mi) — poz_kayitlari_listesi
            None ise o turda geçerli veri bulunamadı (hata mesajı zaten
            gösterildi); iptal_edildi_mi True ise kullanıcı tüm işlemi
            iptal etti (döngü tamamen durmalı).
        """
        rapor = self.acad_connector.get_poz_bazli_donati_tablosu(
            mesaj=f"Tablo {tablo_no}: Poza göre donatı metraj tablosunu kutu çizerek seçin "
                  f"(SADECE BU TABLOYU — başka tablo varsa dahil ETMEYİN)"
        )

        if rapor["secim_sayisi"] == 0:
            QMessageBox.information(self, "Bilgi", "Hiç obje seçilmedi.")
            return None, True

        poz_kayitlari = rapor.get("poz_kayitlari", {})

        # Başlık otomatik bulunamadıysa: kullanıcıya sütun sırasını sor
        # (bkz. proje brief'i — "Başlık YOKSA kullanıcıya sor"). AutoCAD'e
        # TEKRAR seçim yaptırmadan, zaten okunan grid_ham üzerinde tekrar
        # dener — bu yüzden pahalı bir ikinci seçim adımı gerekmez.
        if poz_kayitlari.get("sutun_tespiti") == "basarisiz":
            sutun_sayisi = len(rapor["grid_ham"][0]) if rapor["grid_ham"] else 0
            metin, ok = QInputDialog.getText(
                self, "Sütun Sırası Gerekli",
                f"Tablo {tablo_no}: Başlık satırı (ADET/ÇAP/BOY) otomatik tanınamadı.\n\n"
                f"Tabloda {sutun_sayisi} sütun bulundu. Soldan sağa sütun\n"
                f"sırasını virgülle ayırarak yazın:\n"
                f"(poz, adet, cap, boy, sekil, toplam, yoksay)\n\n"
                f"Örnek: poz,adet,cap,boy,sekil,toplam,toplam,toplam\n\n"
                f"NOT: {sutun_sayisi} sütun bulundu ama çok fazla/az geliyorsa\n"
                f"muhtemelen birden fazla tablo birlikte seçildi — İptal edip\n"
                f"sadece TEK bir tabloyu tekrar seçmeyi deneyin."
            )
            if not ok or not metin.strip():
                QMessageBox.information(self, "İptal", f"Tablo {tablo_no} için sütun sırası girilmedi, bu tablo atlandı.")
                return None, False
            sutun_sirasi = [s.strip().lower() for s in metin.split(",")]
            if len(sutun_sirasi) != sutun_sayisi:
                QMessageBox.critical(
                    self, "Hata",
                    f"Girilen sütun sayısı ({len(sutun_sirasi)}) tablodaki sütun "
                    f"sayısıyla ({sutun_sayisi}) uyuşmuyor. Bu tablo atlandı."
                )
                return None, False

            from app.core.autocad_connector import grid_den_poz_kayitlarini_cikar
            poz_kayitlari = grid_den_poz_kayitlarini_cikar(rapor["grid_ham"], sutun_sirasi=sutun_sirasi)

        if not poz_kayitlari.get("basarili"):
            QMessageBox.warning(self, "Uyarı", f"Tablo {tablo_no}'da geçerli poz verisi bulunamadı, atlandı.")
            return None, False

        # Poz numaralarını tablo no ile etiketle — birden fazla tabloda ayni
        # "Poz 1" gibi tekrar eden isimler sapma raporunda karışmasın.
        etiketli = []
        for kayit in poz_kayitlari["basarili"]:
            yeni = dict(kayit)
            yeni["poz_no"] = f"T{tablo_no}-{kayit['poz_no']}"
            etiketli.append(yeni)

        return etiketli, False

    def _autocad_poz_donati_oku(self):
        """AutoCAD'den bir veya birden fazla "Poza Göre Donatı Metraj
        Tablosu"nu (her biri AYRI seçilerek) okur (İstinat Demir Hesabı) —
        koordinat bazlı satır/sütun kümelemesi + başlık tespiti + kg/ton
        hesabı (bkz. CLAUDE.md Rev-128/129/130/132).

        Birden fazla tablo desteği (Rev-132): Kullanıcı gerçek projede
        birden fazla ayrı tablo olduğunu bildirdi ve hepsini tek işlemde
        eklemek istedi. Tabloları TEK BİR kutu ile birlikte seçmek koordinat
        kümelemesini bozduğu için (tablolar arası dev boşluk, tablo içi
        gerçek satır/sütun boşluğunu "gürültü" sanıp yutuyor — bkz.
        PROGRAM_OZELLIKLERI Rev-132), bunun yerine kullanıcı tabloları TEK
        TEK seçer, program her turdan sonra "başka tablo var mı?" diye sorar.
        """
        try:
            if not self.acad_connector or not self.acad_connector.bagli:
                QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
                return

            if not self.aktif_kat_adi:
                QMessageBox.warning(self, "Uyarı", "Önce bir kat ekleyin ve seçin!")
                return

            QMessageBox.information(
                self, "İstinat Demir Hesabı — Tablo Okuma",
                "AutoCAD'deki 'Poza Göre Donatı Metraj Tablosu'nu okuyacaksınız.\n\n"
                "1. SADECE TEK BİR tabloyu kutu çizerek seçin\n"
                " (POZ/ADET/ÇAP/BOY başlıkları dahil, başka tablo DAHİL ETMEYİN)\n"
                "2. Seçimi tamamlamak için ENTER'a basın\n\n"
                "Birden fazla tablonuz varsa merak etmeyin — bu tablo işlendikten\n"
                "sonra 'Başka tablo var mı?' diye soracağız, sırayla ekleyebilirsiniz.\n\n"
                "Program sütunları otomatik tanıyıp çapa göre toplam ağırlık\n"
                "(kg/ton) hesaplayacak ve tablodaki hazır TOPLAM sütunuyla\n"
                "karşılaştıracaktır."
            )

            tum_kayitlar = []
            tablo_no = 1
            while True:
                kayitlar, iptal = self._poz_donati_tek_tablo_oku(tablo_no)
                if iptal:
                    break
                if kayitlar:
                    tum_kayitlar.extend(kayitlar)
                    tablo_no += 1
                    devam = QMessageBox.question(
                        self, "Başka Tablo Var Mı?",
                        f"Tablo {tablo_no - 1} işlendi ({len(kayitlar)} poz bulundu, "
                        f"toplam birikmiş poz: {len(tum_kayitlar)}).\n\n"
                        f"Eklemek istediğiniz başka bir 'Poza Göre Donatı Metraj\n"
                        f"Tablosu' daha var mı?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if devam != QMessageBox.StandardButton.Yes:
                        break
                else:
                    # Bu tur atlandi (basarisiz/iptal) - yine de devam etmek
                    # isteyip istemedigini sor (toplam biriken varsa).
                    if not tum_kayitlar:
                        return
                    devam = QMessageBox.question(
                        self, "Devam Edilsin Mi?",
                        f"Bu tablo atlandı. Şimdiye kadar {len(tum_kayitlar)} poz\n"
                        f"toplandı. Başka bir tablo daha denemek ister misiniz?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if devam != QMessageBox.StandardButton.Yes:
                        break

            if not tum_kayitlar:
                QMessageBox.warning(self, "Uyarı", "Geçerli poz verisi bulunamadı.")
                return

            from app.core.autocad_connector import (
                poz_kayitlarindan_hesapla,
                poz_kayitlarini_demir_bilgisine_cevir,
            )
            hesap = poz_kayitlarindan_hesapla(tum_kayitlar)
            demirler = poz_kayitlarini_demir_bilgisine_cevir(tum_kayitlar)

            mesaj = f"İSTİNAT DEMİR HESABI\n{'='*40}\n\n"
            mesaj += f"Kat: {self.aktif_kat_adi}\n"
            mesaj += f"İşlenen tablo sayısı: {tablo_no - 1}\n\n"
            mesaj += f"Bulunan poz : {len(demirler)}\n"
            g = hesap["genel"]
            mesaj += f"Toplam Adet : {g['adet']:,}\n"
            mesaj += f"Toplam Boy : {g['boy_m']:,.2f} m\n"
            mesaj += f"Toplam Ağırlık : {g['agirlik_kg']:,.2f} kg\n"
            mesaj += f" : {g['agirlik_kg']/1000:,.3f} ton\n"
            mesaj += f"{chr(9472)*40}\n\n"
            mesaj += "ÇAP BAZLI DAĞILIM:\n"
            for cap in sorted(hesap["cap_ozeti"].keys()):
                ozet = hesap["cap_ozeti"][cap]
                mesaj += f" Ø{cap}: {ozet['adet']:,} adet, {ozet['boy_m']:,.2f}m, {ozet['agirlik_kg']:,.2f}kg\n"

            if hesap["sapma_var_mi"]:
                mesaj += f"\n⚠ {len(hesap['sapmalar'])} pozda tablodaki TOPLAM ile hesaplanan boy uyuşmuyor:\n"
                for s in hesap["sapmalar"][:10]:
                    mesaj += (f" Poz {s['poz_no']} (Ø{s['cap']}): hesaplanan={s['hesaplanan_boy']}m, "
                              f"tablo={s['tablo_boy']}m, fark={s['fark']}m\n")
                if len(hesap["sapmalar"]) > 10:
                    mesaj += f" ... ve {len(hesap['sapmalar']) - 10} poz daha\n"
            else:
                mesaj += "\n✓ Tüm pozlarda hesaplanan boy, tablodaki TOPLAM ile uyuşuyor.\n"

            QMessageBox.information(self, f"İstinat Demir Hesabı - {self.aktif_kat_adi}", mesaj)

            for kat_data in self.demir_kat_verileri:
                if kat_data["kat_adi"] == self.aktif_kat_adi:
                    kat_data["demirler"].extend(demirler)
                    break

            self._demir_kat_listesini_guncelle()
            self.btn_demir_excel.setEnabled(True)
            self.btn_kesime_aktar.setEnabled(True)
            logger.info(
                f"'{self.aktif_kat_adi}' katına {tablo_no - 1} tablodan toplam "
                f"{len(demirler)} istinat demir hesabı (poza göre donatı) poz eklendi"
            )

        except Exception as e:
            logger.error(f"İstinat demir hesabı okuma hatası: {e}")
            QMessageBox.critical(self, "Hata", f"İstinat demir hesabı okunurken hata:\n{e}")

    def _sekme_degisti(self, index: int):
        """Sekme değiştiğinde görünürlük ayarla.

        Not: İnce İşler / Çoklu Kat sekmeleri hâlâ kaldırılmış durumda.
        Kaba İnşaat (idx 0, alt sekmeler: Demir Metrajı/Beton & Kalıp) ve
        LISP Araçları (Rev-133'te tekrar açıldı) aktif. Genel Ayarlar
        artık hiç gösterilmiyor.
        """
        self.settings_group.setVisible(False)


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
        self._aktif_kat_degisti()

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
            self._aktif_kat_degisti()

    def _demir_kat_secildi(self, item):
        """Kat listesinden bir kat seçildi"""
        current_row = self.demir_kat_listesi.currentRow()
        if current_row >= 0 and current_row < len(self.demir_kat_verileri):
            self.aktif_kat_adi = self.demir_kat_verileri[current_row]["kat_adi"]
            self.btn_kat_sil.setEnabled(True)
            logger.info(f"Aktif kat değişti: {self.aktif_kat_adi}")
            self._aktif_kat_degisti()

    def _demir_kat_listesini_guncelle(self):
        """Kat listesini güncelle (demir sayılarıyla)"""
        self.demir_kat_listesi.clear()
        for kat_data in self.demir_kat_verileri:
            demir_sayisi = len(kat_data["demirler"])
            toplam_agirlik = sum(d.toplam_agirlik for d in kat_data["demirler"]) if kat_data["demirler"] else 0
            self.demir_kat_listesi.addItem(
            f" {kat_data['kat_adi']} ({demir_sayisi} demir, {toplam_agirlik:.1f} kg)"
            )

    def _excel_sayfa_adi_guvenli(self, kat_adi: str, kullanilan: set) -> str:
        """Kat adını Excel sayfa adı kurallarına uygun hale getirir.

        Excel sayfa adlarında \\ / ? * [ ] : karakterleri yasaktır ve 31
        karakteri geçemez; ayrıca aynı çalışma kitabında iki sayfa aynı
        isme sahip olamaz. Kullanıcının serbestçe girdiği kat adı (örn.
        "Bodrum Kat / Sığınak") doğrudan sayfa adı yapılırsa openpyxl
        ValueError fırlatır ve tüm dışa aktarım çöker.
        """
        temiz = re.sub(r'[\\/?*\[\]:]', '-', kat_adi).strip() or "Kat"
        temiz = temiz[:31]
        taban, sayac = temiz, 2
        while temiz in kullanilan:
            ek = f"_{sayac}"
            temiz = taban[:31 - len(ek)] + ek
            sayac += 1
        kullanilan.add(temiz)
        return temiz

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
            kullanilan_sayfalar = set()
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                g_adet = 0; g_boy = 0.0; g_agir = 0.0
                for kd in self.demir_kat_verileri:
                    if not kd["demirler"]: continue
                    sayfa = self._excel_sayfa_adi_guvenli(kd["kat_adi"], kullanilan_sayfalar)
                    rows = [{"Eleman Tipi": getattr(d, "eleman_tipi", "") or "-",
                             "Poz/Metin": d.orijinal_metin, "Adet": d.adet,
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

    def _kesim_listesine_aktar(self):
        """Toplanan demirleri 'Yapısal Demir Hesaplama' penceresinin
        Kesim Listesi sekmesine doğrudan aktarır (AutoCAD'e ikinci kez
        bağlanmaya veya Excel'e kaydedip geri okumaya gerek kalmadan)."""
        if not self.demir_kat_verileri:
            QMessageBox.warning(self, "Uyarı", "Henüz demir metrajı alınmış kat yok!")
            return
        tum_demirler = [d for kd in self.demir_kat_verileri for d in kd["demirler"]]
        if not tum_demirler:
            QMessageBox.warning(self, "Uyarı", "Hiçbir katta demir verisi yok!")
            return

        try:
            parcalar = demirlerden_kesim_parcalari_uret(
                tum_demirler, boy_bindirme_dahil=True, birim="cm"
            )
        except Exception as e:
            logger.error(f"Kesim listesine aktarim donusum hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Veri dönüştürülemedi:\n{e}")
            return

        self._kesim_penceresine_ekle(
            [(p.cap, p.boy_cm, p.adet, p.eleman_tipi or "") for p in parcalar], "Demir"
        )

    def _kesim_penceresine_ekle(self, kalemler: List[tuple], kaynak_adi: str) -> bool:
        """[(çap, boy_cm, adet, eleman_tipi)] kalemlerini Kesim Listesi'ne ekler.

        Rev-153: Demir Metrajı ve Temel Kirişi aktarımının ORTAK yolu (Rev-118
        singleton penceresi korunur — açıksa aynı pencereye eklenir).
        """
        desteklenmeyen_caplar = set()
        gecerli = []
        for k in kalemler:
            if k[0] in _KESIM_DESTEKLENEN_CAPLAR:
                gecerli.append(k)
            else:
                desteklenmeyen_caplar.add(k[0])

        if not gecerli:
            QMessageBox.warning(
                self, "Uyarı",
                "Aktarılabilecek demir bulunamadı (çaplar Kesim Listesi'nin\n"
                f"desteklediği aralık dışında: {sorted(_KESIM_DESTEKLENEN_CAPLAR)})."
            )
            return False

        ana_pencere = self.parent()
        if ana_pencere is None or not hasattr(ana_pencere, "open_demir_hesaplama"):
            QMessageBox.critical(
                self, "Hata",
                "Ana pencereye erişilemedi, Kesim Listesi penceresi açılamıyor."
            )
            return False

        demir_penceresi = getattr(ana_pencere, "demir_window", None)
        try:
            acik_mi = demir_penceresi is not None and demir_penceresi.isVisible()
        except RuntimeError:
            acik_mi = False  # Qt C++ nesnesi silinmiş (pencere kapatılmış)
        if not acik_mi:
            ana_pencere.open_demir_hesaplama()
            demir_penceresi = ana_pencere.demir_window

        for cap, boy_cm, adet, eleman in gecerli:
            demir_penceresi._kesim_satir_ekle_deger(cap, boy_cm, adet, eleman)

        demir_penceresi.tab_widget.setCurrentIndex(3)  # Kesim Listesi sekmesi
        demir_penceresi.show()
        demir_penceresi.raise_()
        demir_penceresi.activateWindow()

        mesaj = f"{kaynak_adi}: {len(gecerli)} kalem Kesim Listesi'ne aktarıldı."
        if desteklenmeyen_caplar:
            mesaj += (
                f"\n\n{len(desteklenmeyen_caplar)} kalem atlandı "
                f"(desteklenmeyen çap: {sorted(desteklenmeyen_caplar)})."
            )
        QMessageBox.information(self, "Aktarıldı", mesaj)
        logger.info(
            f"Kesim Listesine aktarim ({kaynak_adi}): {len(gecerli)} kalem "
            f"(atlanan cap: {sorted(desteklenmeyen_caplar) if desteklenmeyen_caplar else 'yok'})"
        )
        return True

    def _cap_bazli_tonaj_goster(self):
        """Tüm katlarda toplanan demirleri çapa göre gruplayıp toplam
        boy/ağırlık/tonaj tablosunu gösterir (bkz. CapBazliTonajDialog)."""
        if not self.demir_kat_verileri:
            QMessageBox.warning(self, "Uyarı", "Henüz demir metrajı alınmış kat yok!")
            return
        tum_demirler = [d for kd in self.demir_kat_verileri for d in kd["demirler"]]
        if not tum_demirler:
            QMessageBox.warning(self, "Uyarı", "Hiçbir katta demir verisi yok!")
            return
        dialog = CapBazliTonajDialog(tum_demirler, self)
        dialog.exec()

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


    def _beton_kalip_kolon_yazisindan_oku(self) -> None:
        """Rev-134 Aşama 2/3: kutu seçimiyle kolon boyut yazılarını toplu
        okur, kat yüksekliğini sorup beton/kalıp hesabını yapar, önizleme
        gösterir ve onay sonrası mevcut beton_kalip_table'a ekler.

        Neyi çözüyoruz?
        Geometriden (BoundingBox/Area) kolon boyutu okumak 1/50 ölçek + mm
        birim belirsizliğinde güvenilmez (Rev-133). Kullanıcı bir bölgeyi
        kutuyla seçer, program içindeki TÜM yazıları okuyup S/P ile
        başlayanları kolon sayar; K ile başlayanlar (kiriş) ve tanımsızlar
        güvenlik katmanı gereği atlanır. En/boy yazıdan (ölçekten bağımsız)
        geldiği için sadece KAT YÜKSEKLİĞİ eksik kalıyor — onu kullanıcıdan
        TEK SEFERDE (tüm kolonlar için ortak) alıp mevcut
        `_beton_kalip_hesapla_eleman("Kolon", ...)` formülüyle (Kalıp Alanı
        Analizi'ndeki Kolon formülüyle AYNI, yeniden yazılmadı) her kolonun
        beton m³/kalıp m²'sini hesaplıyoruz.

        Aktif kat + mükerrer engelleme (2026-09-07):
        Demir Metrajı sekmesindeki AYNI `self.aktif_kat_adi` mekanizması
        kullanılıyor — okuma öncesi bir kat seçili/eklenmiş olmalı. Her
        kolon `(aktif_kat_adi, kolon_adi)` anahtarıyla
        `self.beton_kalip_kolon_kayitlari` registry'sine YAZILIR (aynı
        anahtar zaten varsa GÜNCELLENİR, yeni satır olarak EKLENMEZ) —
        böylece aynı katın aynı kolonu birden fazla kez okunursa toplam
        BÜYÜMEZ. Farklı kattaki aynı isim ayrı anahtar olduğu için AYRI
        sayılır. Tablodaki "Kolon" satırları, onaydan sonra SADECE aktif
        kat için registry'den yeniden inşa edilir
        (`_beton_kalip_kat_kolon_satirlarini_yeniden_olustur`) — diğer
        katların satırlarına dokunulmaz.

        Nasıl test ederiz?
        `scratchpad/test_kolon_beton_hesap_asama2.py`: 12 kolon @ (50/50)
        "Zemin" katına h=4.60 -> toplam 13.80 m³; AYNI 12 kolonu TEKRAR
        "Zemin"e okursan toplam YİNE 13.80 (34.8 değil, mükerrer
        engellendi); aktif kat "1.Kat" yapılıp aynı 12 kolon okunursa
        toplam 27.60 (iki kat ayrı ayrı biriktiği için).
        """
        if not self.acad_connector or not self.acad_connector.bagli:
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return

        # Kat seçimi kontrolü — Demir Metrajı'ndaki AYNI kat mekanizması ve
        # AYNI uyarı deseni (bkz. `_autocad_demir_metraj_oku` benzeri
        # handler'lar) beton/kalıp için de zorunlu: hangi kata yazıldığı
        # bilinmeden mükerrer engelleme anahtarı (kat+kolon adı) kurulamaz.
        if not self.aktif_kat_adi:
            QMessageBox.warning(
                self, "Kat Seçimi Gerekli",
                "Önce bir kat eklemeniz/seçmeniz gerekiyor!\n\n"
                "1. Demir Metrajı sekmesindeki 'Kat İsmi Girişi' bölümüne\n"
                "   kat adını yazın (Örn: Zemin Kat, 1. Kat)\n"
                "2. '+ Ekle' butonuna tıklayın\n"
                "3. Sonra Beton & Kalıp kolon okumasını yapabilirsiniz\n\n"
                "(Aktif kat, Demir Metrajı ile PAYLAŞILAN aynı kattır.)"
            )
            return

        ret = QMessageBox.information(
            self, "Kolon Yazısından Toplu Oku",
            "AutoCAD penceresine geçin ve kolon (varsa kiriş) boyut\n"
            "yazılarının bulunduğu bölgeyi KUTU ile seçin, sonra ENTER'a basın.\n\n"
            "İsmi S/P ile başlayanlar alınır: uzun/kısa kenar ≥ 6 ise PERDE\n"
            "(camgöbeği), değilse KOLON (yeşil). K ile başlayanlar (kiriş),\n"
            "donatı yazıları ve tanımsızlar otomatik ATLANIR. Boyutu yazmayan\n"
            "S/P adları (L/T/U perde) KIRMIZI boyanır — perde aracıyla alın.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if ret == QMessageBox.StandardButton.Cancel:
            return

        try:
            sonuc = self.acad_connector.get_kolon_beton_yazidan()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"AutoCAD okuma hatası:\n{e}")
            return

        if sonuc["secim_sayisi"] == 0:
            QMessageBox.information(self, "Seçim Yok", "Hiç obje seçilmedi.")
            return

        kolonlar = sonuc["kolonlar"]
        aktif_kat = self.aktif_kat_adi
        # Zaten kayıtlı bir adın boyutsuz yazısı (ör. perde aracıyla alınmış S260) tekrar listelenmez
        okunamayanlar = [o for o in (sonuc.get("okunamayanlar") or [])
                         if self._kolon_kaydi_bul(aktif_kat, o["ad"]) is None
                         and self._perde_kaydi_bul(aktif_kat, o["ad"]) is None]
        if not kolonlar and not okunamayanlar:
            QMessageBox.warning(
                self, "Kolon Bulunamadı",
                f"{sonuc['ozet']}\n\nSeçimde S/P ile başlayan kolon / perde yazısı bulunamadı."
            )
            return

        # Rev-160 — 1) Mükerrer: ortak havuz (kat + ad; kolon aracı + perde aracı, farklı
        # pafta/handle olsa bile). Hayır denen eleman ALINMAZ ve rengi DEĞİŞMEZ.
        S = QMessageBox.StandardButton
        secilen: List[Dict] = []
        hepsi: Optional[bool] = None   # Tümüne Evet / Tümüne Hayır
        bu_okumada = set()
        for k in kolonlar:
            n = eleman_ad_normalize(k["ad"])
            if (n in bu_okumada or self._kolon_kaydi_bul(aktif_kat, n) is not None
                    or self._perde_kaydi_bul(aktif_kat, n) is not None):
                if hepsi is None:
                    cevap = QMessageBox.question(
                        self, "Kayıtlı Eleman", f"{k['ad']} bu katta zaten kayıtlı. Güncellensin mi?",
                        S.Yes | S.No | S.YesToAll | S.NoToAll, S.No)
                    if cevap in (S.YesToAll, S.NoToAll):
                        hepsi = cevap == S.YesToAll
                    evet = cevap in (S.Yes, S.YesToAll)
                else:
                    evet = hepsi
                if not evet:
                    continue
                secilen = [s for s in secilen if eleman_ad_normalize(s["ad"]) != n]
            bu_okumada.add(n)
            k = dict(k)
            k.setdefault("eleman_tipi", eleman_tipi_belirle(k["en_cm"], k["boy_cm"]))
            secilen.append(k)

        # 2) Boyama: Kolon yeşil, Perde camgöbeği, okunamayan kırmızı. Her boyamanın önceki
        # program rengi saklanır — İptal ters sırayla bir önceki hâle döndürür.
        renk_gecmisi: List[tuple] = []

        def boya(handle, renk):
            if handle:
                renk_gecmisi.append((handle, self._eleman_renk(handle, renk)))

        for k in secilen:
            boya(k.get("handle"), ELEMAN_RENKLERI[k["eleman_tipi"]])
        for o in okunamayanlar:
            boya(o.get("handle"), OKUNAMAYAN_RENK)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Kolon / Perde Yazısından Toplu Oku — {aktif_kat}")
        dlg.setMinimumSize(620, 540)
        dlg.setStyleSheet("background: #252535; color: white;")
        lay = QVBoxLayout(dlg)

        ozet_label = QLabel(f"Aktif Kat: {aktif_kat}\n{sonuc['ozet']}")
        ozet_label.setWordWrap(True)
        ozet_label.setStyleSheet(
            "color: #ce93d8; font-weight: bold; padding: 6px;"
            " border: 1px solid #ce93d8; border-radius: 4px; background: #1e1e2e;"
        )
        lay.addWidget(ozet_label)

        # Kat yüksekliği — "Genel Ayarlar" alanından öntanımlı, TEK SEFERDE (tüm elemanlar için ortak)
        yuk_satir = QHBoxLayout()
        yuk_satir.addWidget(QLabel("Kolon Kat Yüksekliği (m):"))
        yukseklik_spin = QDoubleSpinBox()
        yukseklik_spin.setRange(0.5, 20.0)
        yukseklik_spin.setSingleStep(0.05)
        yukseklik_spin.setDecimals(2)
        yukseklik_spin.setValue(round(self.kat_yuksekligi_spin.value() / 100.0, 2))
        yukseklik_spin.setToolTip("Sadece KOLONLAR için (tam kat). Perdeler Perde sekmesindeki kat ayarıyla "
                                  "hesaplanır.")
        yuk_satir.addWidget(yukseklik_spin)
        yuk_satir.addStretch()
        lay.addLayout(yuk_satir)
        # Rev-161: perdeler Perde sekmesinin kat ayarıyla (kalıp NET yükseklik) — iki araç aynı sonucu verir
        perde_ayar = self._perde_kat_ayari(aktif_kat)
        perde_esas_label = QLabel(f"Perdeler (Perde sekmesi kat ayarı): {perde_ayar.esas_etiketi()}")
        perde_esas_label.setWordWrap(True)
        perde_esas_label.setStyleSheet("color: #48c9b0; font-size: 9pt; padding: 2px 6px;")
        lay.addWidget(perde_esas_label)

        tablo = QTableWidget()
        tablo.setColumnCount(6)
        tablo.setHorizontalHeaderLabels(["Ad", "Tip", "Boyut (cm)", "Beton (m³)", "Kalıp (m²)", "Katman"])
        tablo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tablo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tablo.setToolTip("Tip otomatik: uzun/kısa kenar ≥ 6 ise Perde (TBDY 2018). Yanlışsa Tip "
                         "hücresinden değiştirin — AutoCAD'deki renk de güncellenir.")
        tablo.setRowCount(len(secilen))
        lay.addWidget(tablo, 1)
        self._kolon_tip_combolari = []

        toplam_label = QLabel()
        toplam_label.setStyleSheet("color: #f39c12; font-weight: bold; padding: 6px; font-size: 11pt;")
        lay.addWidget(toplam_label)

        def _tabloyu_hesapla_ve_doldur():
            kat_yuk_m = yukseklik_spin.value()
            beton_t = kalip_t = 0.0
            for row, k in enumerate(secilen):
                h = self._kolon_eleman_hesap(aktif_kat, k["en_cm"], k["boy_cm"], k["eleman_tipi"], kat_yuk_m)
                beton_t += h["beton_m3"]
                kalip_t += h["kalip_m2"]
                for col, v in ((0, str(k["ad"])), (2, f"{k['en_cm']:.0f}/{k['boy_cm']:.0f}"),
                               (3, f"{tek_hane(h['beton_m3'])}"), (4, f"{tek_hane(h['kalip_m2'])}"),
                               (5, str(k.get("layer", "")))):
                    tablo.setItem(row, col, QTableWidgetItem(v))
            perde = sum(1 for k in secilen if k["eleman_tipi"] == "Perde")
            toplam_label.setText(
                f"TOPLAM: {tek_hane(beton_t)} m³ beton  |  {tek_hane(kalip_t)} m² kalıp"
                f"  ({len(secilen) - perde} kolon, {perde} perde)"
            )

        def _tip_degisti(row, tip):
            k = secilen[row]
            if k["eleman_tipi"] == tip:
                return
            k["eleman_tipi"] = tip
            boya(k.get("handle"), ELEMAN_RENKLERI[tip])
            _tabloyu_hesapla_ve_doldur()

        for row, k in enumerate(secilen):
            combo = QComboBox()
            combo.addItems(list(ELEMAN_TIPLERI))
            combo.setCurrentText(k["eleman_tipi"])
            combo.currentTextChanged.connect(lambda t, r=row: _tip_degisti(r, t))
            tablo.setCellWidget(row, 1, combo)
            self._kolon_tip_combolari.append(combo)

        yukseklik_spin.valueChanged.connect(_tabloyu_hesapla_ve_doldur)
        _tabloyu_hesapla_ve_doldur()

        if okunamayanlar:
            ok_label = QLabel("Şu elemanlar okunamadı, perde aracıyla alın: "
                              + ", ".join(o["ad"] for o in okunamayanlar))
            ok_label.setWordWrap(True)
            ok_label.setStyleSheet("color: #ff6b6b; font-weight: bold; padding: 4px;")
            lay.addWidget(ok_label)
        atlanan_ad_listesi = ([k["ad"] or "?" for k in sonuc["kirisler_atlanan"]]
                              + [k["ad"] or "?" for k in sonuc["tanimsizlar"]])
        if atlanan_ad_listesi:
            atlanan_label = QLabel(
                "Atlanan yazılar (kiriş / tanımsız, hesaba katılmadı): " + ", ".join(atlanan_ad_listesi[:20])
                + (" ..." if len(atlanan_ad_listesi) > 20 else "")
            )
            atlanan_label.setWordWrap(True)
            atlanan_label.setStyleSheet("color: #aaa; font-size: 9pt; padding: 4px;")
            lay.addWidget(atlanan_label)

        info_label = QLabel(
            "Liste doğruysa \"Onayla ve Tabloya Ekle\"ye basın — aynı tip ve boyuttakiler TEK satırda "
            "gruplanır. Vazgeç: AutoCAD'deki renkler bir önceki hâline döner."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #f39c12; font-size: 9pt; font-style: italic;")
        lay.addWidget(info_label)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Onayla ve Tabloya Ekle")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            for handle, onceki in reversed(renk_gecmisi):
                self._eleman_renk(handle, onceki)
            return

        # Onaylandı: (kat, ad) anahtarıyla registry'ye YAZILIR — aynı ad varsa (kolon aracında
        # ya da perde aracında) yerini alır, mükerrer birikmez.
        kat_yuk_m = yukseklik_spin.value()
        yeni_sayisi = guncellenen_sayisi = 0
        perde_silindi = False
        for k in secilen:
            n = eleman_ad_normalize(k["ad"])
            eski = self._kolon_kaydi_bul(aktif_kat, n)
            p_eski = self._perde_kaydi_bul(aktif_kat, n)
            if eski:
                del self.beton_kalip_kolon_kayitlari[eski]
            if p_eski:
                del self.perde_kayitlari[p_eski]
                perde_silindi = True
            if eski or p_eski:
                guncellenen_sayisi += 1
            else:
                yeni_sayisi += 1
            h = self._kolon_eleman_hesap(aktif_kat, k["en_cm"], k["boy_cm"], k["eleman_tipi"], kat_yuk_m)
            # beton/kalip: kayıt anındaki değer (bilgi) — gösterim/özet _kolon_kayit_hesap ile GÜNCEL
            # kat ayarından hesaplanır (Perde sekmesinde döşeme değişince perdeler de güncellenir)
            self.beton_kalip_kolon_kayitlari[(aktif_kat, n)] = {
                "en_m": k["en_m"], "boy_m": k["boy_m"], "en_cm": k["en_cm"], "boy_cm": k["boy_cm"],
                "kat_yuk_m": kat_yuk_m, "beton": h["beton_m3"], "kalip": h["kalip_m2"],
                "tip": k["eleman_tipi"], "handle": k.get("handle"),
            }
            self.okunamayan_elemanlar.pop((aktif_kat, n), None)
        for o in okunamayanlar:
            self.okunamayan_elemanlar[(aktif_kat, o["ad"])] = o.get("handle")

        self._beton_kalip_kat_kolon_satirlarini_yeniden_olustur(aktif_kat)
        self._beton_kalip_toplamlar_guncelle()
        if perde_silindi:
            self._perde_tablo_yenile()

        kat_kayit = [self._kolon_kayit_hesap(kat, v)
                     for (kat, _ad), v in self.beton_kalip_kolon_kayitlari.items() if kat == aktif_kat]
        kat_beton = sum(h["beton_m3"] for h in kat_kayit)
        kat_kalip = sum(h["kalip_m2"] for h in kat_kayit)
        bekleyen = [ad for (kat, ad) in self.okunamayan_elemanlar if kat == aktif_kat]
        QMessageBox.information(
            self, "Eklendi",
            f"Aktif Kat: {aktif_kat}\n"
            f"{yeni_sayisi} eleman yeni eklendi, {guncellenen_sayisi} eleman güncellendi"
            f" (mükerrer okuma birikmedi).\n"
            f"Kolon kat yüksekliği (tam kat): {kat_yuk_m:.2f} m\n"
            f"Perdeler: {self._perde_kat_ayari(aktif_kat).esas_etiketi()}\n\n"
            f"'{aktif_kat}' katı toplamı (kolon + perde): {tek_hane(kat_beton)} m³ beton, {tek_hane(kat_kalip)} m² kalıp."
            + (f"\n\nŞu elemanlar okunamadı, perde aracıyla alın: {', '.join(bekleyen)}" if bekleyen else "")
        )

    def _beton_kalip_kat_kolon_satirlarini_yeniden_olustur(self, kat_adi: str) -> None:
        """Verilen kata ait "Kolon Yazısından Toplu Oku" kaynaklı satırları
        tablodan silip, `beton_kalip_kolon_kayitlari` registry'sindeki
        GÜNCEL (mükerrersiz) veriden aynı boyuttaki kolonları gruplayarak
        yeniden ekler.

        Neyi çözüyoruz?
        Registry mükerrer okumayı zaten engelliyor (aynı kat+kolon adı
        üzerine yazılıyor), ama GÖRÜNEN tabloyu da senkron tutmak gerekir
        — aksi halde eski (yanlış sayıda/yükseklikte) satır ekranda kalır.
        Sadece BU kata ait, "kolon_yazisi" kaynaklı satırlar silinir (bir
        cell'e `Qt.ItemDataRole.UserRole` ile etiketlenmiş) — manuel
        "+ Ekle" ile girilmiş satırlara ve DİĞER katların satırlarına
        dokunulmaz.

        Nasıl test ederiz?
        registry'de {("Zemin","SZ01"):.., ("Zemin","SZ02"):..} varken bu
        metod çağrılırsa tabloda "Zemin" + "Kolon" etiketli TEK (veya
        boyuta göre birden fazla) satır kalmalı, "1.Kat" satırları
        etkilenmemeli.
        """
        KOLON_YAZISI_ETIKETI = "kolon_yazisi"

        for row in reversed(range(self.beton_kalip_table.rowCount())):
            kat_item = self.beton_kalip_table.item(row, 0)
            if (
                kat_item is not None
                and kat_item.text() == kat_adi
                and kat_item.data(Qt.ItemDataRole.UserRole) == KOLON_YAZISI_ETIKETI
            ):
                self.beton_kalip_table.removeRow(row)

        # Rev-160: grup anahtarı (tip, en, boy) — Kolon ve Perde ayrı satır.
        # Rev-161: her kayıt _kolon_kayit_hesap ile — kolon tam kat, perde Perde sekmesi kat
        # ayarıyla (kalıp NET yükseklik); grup toplamı kayıtların toplamı.
        gruplar: Dict[tuple, Dict] = {}
        perde_ayar = self._perde_kat_ayari(kat_adi)
        for (kat, _kolon_adi), kayit in self.beton_kalip_kolon_kayitlari.items():
            if kat != kat_adi:
                continue
            tip = kayit.get("tip", "Kolon")
            anahtar = (tip, round(kayit["en_m"], 4), round(kayit["boy_m"], 4))
            g = gruplar.setdefault(anahtar, {"adet": 0, "beton": 0.0, "kalip": 0.0,
                                             "h": perde_ayar.kat_yuksekligi_m if tip == "Perde"
                                             else kayit["kat_yuk_m"]})
            h = self._kolon_kayit_hesap(kat, kayit)
            g["adet"] += 1
            g["beton"] += h["beton_m3"]
            g["kalip"] += h["kalip_m2"]

        fire_pct = self.bk_fire_spin.value()
        for (tip, en_m, boy_m), g in sorted(gruplar.items()):
            adet, kat_yuk_m = g["adet"], g["h"]
            beton, kalip = round(g["beton"], 4), round(g["kalip"], 4)
            siparis = round(beton * (1 + fire_pct / 100), 3)

            row = self.beton_kalip_table.rowCount()
            self.beton_kalip_table.insertRow(row)
            veriler = [
                kat_adi, tip, str(adet), f"{en_m:.2f}", f"{boy_m:.2f}", f"{kat_yuk_m:.2f}",
                f"{tek_hane(beton)}", f"{fire_pct:.1f}", f"{tek_hane(siparis)}", f"{tek_hane(kalip)}",
            ]
            for col, deger in enumerate(veriler):
                item = QTableWidgetItem(deger)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, KOLON_YAZISI_ETIKETI)
                if tip == "Perde":
                    item.setToolTip(f"Perde (kolon yazısından): {perde_ayar.esas_etiketi()}")
                self._bk_tam_deger(item, col, beton, siparis, kalip)
                self.beton_kalip_table.setItem(row, col, item)

    def _kolon_eleman_hesap(self, kat: str, en_cm: float, boy_cm: float, tip: str, kolon_h_m: float) -> Dict:
        """Rev-161: kolon aracındaki eleman — Kolon: tam kat (kolon_h_m); Perde: Perde sekmesinin
        kat ayarı (beton esası + kalıp NET yükseklik) — Perde sekmesiyle aynı sonuç."""
        if tip == "Perde":
            a = self._perde_kat_ayari(kat)
            return kolon_perde_hesapla(en_cm, boy_cm, a.kat_yuksekligi_m, "Perde",
                                       a.doseme_kalinligi_m, a.beton_esasi)
        return kolon_perde_hesapla(en_cm, boy_cm, kolon_h_m, "Kolon")

    def _kolon_kayit_hesap(self, kat: str, kayit: Dict) -> Dict:
        """Registry kaydını GÜNCEL ayarla hesaplar (eski kayıtta en_cm yoksa en_m'den)."""
        en_cm = kayit.get("en_cm", round(kayit["en_m"] * 100, 4))
        boy_cm = kayit.get("boy_cm", round(kayit["boy_m"] * 100, 4))
        return self._kolon_eleman_hesap(kat, en_cm, boy_cm, kayit.get("tip", "Kolon"), kayit["kat_yuk_m"])

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
        self.aktif_kat_adi or "-",
        eleman,
        str(adet),
        f"{dim1:.2f}",
        f"{dim2:.2f}",
        f"{dim3:.2f}",
        f"{tek_hane(beton)}",
        f"{fire_pct:.1f}",
        f"{tek_hane(siparis)}",
        f"{tek_hane(kalip)}",
        ]
        for col, deger in enumerate(veriler):
            item = QTableWidgetItem(deger)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._bk_tam_deger(item, col, beton, siparis, kalip)
            self.beton_kalip_table.setItem(row, col, item)

        self._beton_kalip_toplamlar_guncelle()

    # Rev-165: Beton & Kalıp tablosu beton / sipariş / kalıp hücreleri TEK HANE gösterir;
    # tam değer UserRole'de durur — toplam ve Excel tam değerden (yuvarlanmış metinden DEĞİL).
    BK_SAYI_KOLONLARI = (6, 8, 9)

    def _bk_tam_deger(self, item, col, beton, siparis, kalip):
        deger = {6: beton, 8: siparis, 9: kalip}.get(col)
        if deger is not None:
            item.setData(Qt.ItemDataRole.UserRole, float(deger))

    def _bk_hucre_degeri(self, row: int, col: int) -> float:
        item = self.beton_kalip_table.item(row, col)
        if item is None:
            return 0.0
        v = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
        try:
            return float(item.text().replace(",", ".")) if item.text() else 0.0
        except ValueError:
            return 0.0

    def _beton_kalip_toplamlar_guncelle(self):
        """Tablodaki tum satirlari okuyarak toplam etiketlerini guncelle.

        Tabloda "Kat" s\u00fctunu eklendi\u011finden (index 0), di\u011fer t\u00fcm s\u00fctunlar
        bir kayd\u0131r\u0131ld\u0131: Net Beton=6, Fire=7, Sipari\u015f=8, Kal\u0131p=9.
        M\u00fckerrer okuma birikmesi art\u0131k `beton_kalip_kolon_kayitlari`
        registry'sinde (kat+kolon ad\u0131 anahtar\u0131yla) engellendi\u011fi i\u00e7in, tablo
        sat\u0131rlar\u0131 zaten benzersiz \u2014 burada ek bir dedup gerekmiyor, sadece
        g\u00f6r\u00fcnen sat\u0131rlar\u0131 toplu.
        """
        toplam_beton = toplam_siparis = toplam_kalip = 0.0
        for row in range(self.beton_kalip_table.rowCount()):
            # Rev-165: hücre tek hane gösterir — toplam TAM değerden (UserRole)
            toplam_beton += self._bk_hucre_degeri(row, 6)
            toplam_siparis += self._bk_hucre_degeri(row, 8)
            toplam_kalip += self._bk_hucre_degeri(row, 9)
        self.bk_toplam_beton_label.setText(f"Net Beton: {tek_hane(toplam_beton)} m\u00b3")
        self.bk_toplam_siparis_label.setText(f"Sipari\u015f: {tek_hane(toplam_siparis)} m\u00b3")
        self.bk_toplam_kalip_label.setText(f"Toplam Kal\u0131p: {tek_hane(toplam_kalip)} m\u00b2")


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
            sutunlar = ["Kat", "Eleman", "Adet", "Olcu1(m)", "Olcu2(m)", "Olcu3(m)",
                        "Net Beton(m3)", "Fire(%)", "Siparis(m3)", "Kalip(m2)"]
            satirlar = []
            for row in range(self.beton_kalip_table.rowCount()):
                satir = []
                for col in range(self.beton_kalip_table.columnCount()):
                    item = self.beton_kalip_table.item(row, col)
                    if col in self.BK_SAYI_KOLONLARI:
                        satir.append(round(self._bk_hucre_degeri(row, col), 3))   # Excel'e tam değer
                    else:
                        satir.append(item.text() if item else "")
                satirlar.append(satir)

            df = pd.DataFrame(satirlar, columns=sutunlar)
            tb = df["Net Beton(m3)"].astype(float).sum()
            ts = df["Siparis(m3)"].astype(float).sum()
            tk = df["Kalip(m2)"].astype(float).sum()
            toplam = pd.DataFrame([[
                "", "TOPLAM", "", "", "", "",
                round(tb, 3), "", round(ts, 3), round(tk, 3)
            ]], columns=sutunlar)
            with pd.ExcelWriter(file_path, engine="openpyxl") as yazici:
                pd.concat([df, toplam], ignore_index=True).to_excel(
                    yazici, index=False, sheet_name="Beton Kalip"
                )
                beton_kalip_sutunlari_tek_hane(yazici.sheets["Beton Kalip"])   # Rev-166
            QMessageBox.information(self, "Basarili",
                f"Kaydedildi:\n{file_path}\nBeton: {tek_hane(tb)} m3 | Kalip: {tek_hane(tk)} m2")
            logger.info(f"Beton Kalip Excel: {file_path}")

        except Exception as e:
            logger.error(f"Beton Kalip Excel hatasi: {e}")
            QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{str(e)}")

    # ─────────────────────────────────────────────────────────────────────
    # Rev-137: TEMEL KİRİŞİ (SBH) — Beton + Kalıp
    # ─────────────────────────────────────────────────────────────────────
    TK_KOLONLAR = ["Ad", "Genişlik (cm)", "Yükseklik (cm)", "Uzunluk (m)",
                   "Beton (m³)", "Kalıp (m²)", "Uzunluk Kaynağı",
                   # Rev-153 demir sütunları (beton/kalıp sütun indeksleri DEĞİŞMEDİ)
                   "Filiz Adet", "Filiz Uzunluk (m)", "Filiz (kg)", "Tevzi Çubuk", "Tevzi Bindirme (k)",
                   "Tevzi Boy (m)", "Tevzi Uzunluk (m)", "Tevzi (kg)", "Toplam Demir (kg)"]
    TK_UZUNLUK_KOL = 3
    SBH_DEMIR_AYAR_ANAHTARI = "sbh_demir_tipleri"

    # ── Rev-139 / Rev-157: Radye Temel Beton + Kalıp (adlı kayıt listesi + Excel) ──
    _RADYE_SPIN_STIL = (
        "QDoubleSpinBox { background:#2a2a3a; color:white; border:1px solid #666;"
        " padding:4px; }"
    )
    RADYE_KOLONLAR = ["Radye", "Alan (m²)", "Kalınlık (cm)", "Beton (m³)",
                      "Dış Çevre (m)", "İç Boşluk Çevre (m)", "Kalıp (m²)"]
    _RADYE_TABLO_STIL = (
        "QTableWidget { background:#1e1e2e; color:#e0e0e0; gridline-color:#444; border:1px solid #555; }"
        "QHeaderView::section { background:#2d2d3d; color:#a569bd; font-weight:bold;"
        " padding:4px; border:1px solid #444; }"
        "QTableWidget::item:selected { background:#3a3a5a; }"
    )

    def _radye_spin(self, maks: float, ondalik: int, sonek: str, ipucu: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, maks)
        spin.setDecimals(ondalik)
        spin.setSuffix(sonek)
        spin.setToolTip(ipucu)
        spin.setStyleSheet(self._RADYE_SPIN_STIL)
        spin.setMinimumWidth(160)
        spin.valueChanged.connect(self._radye_hesapla_guncelle)
        return spin

    @staticmethod
    def _radye_buton(metin: str, renk: str, ipucu: str) -> QPushButton:
        btn = QPushButton(metin)
        btn.setToolTip(ipucu)
        btn.setStyleSheet(f"background:{renk}; color:white; font-weight:bold; padding:5px 12px;"
                          " border:none; border-radius:3px;")
        return btn

    def _radye_sekmesi_olustur(self) -> QWidget:
        """Radye Temel sekmesini kurar (Rev-139, Rev-157'de kayıt listesine çevrildi).

        Neyi çözüyoruz? Projedeki radye parçalarının (adlı) beton (alan ×
        kalınlık) ve kalıp ((dış çevre + iç boşluk çevreleri) × kalınlık)
        metrajı. Form bir radyeyi düzenler; "Radye Ekle" ile listeye girer,
        liste Kat Özeti'nin "Temel" grubuna ve Excel "Radye" sayfasına gider.
        Nasıl test ederiz? scratchpad/test_radye.py, test_radye_ozet_excel.py.
        """
        if not hasattr(self, "radye_kayitlari"):
            self.radye_kayitlari: List[Dict] = []
        tab = QWidget()
        dis = QVBoxLayout(tab)
        dis.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        icerik = QWidget()
        lay = QVBoxLayout(icerik)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        bilgi = QLabel(
            "Radye temel metrajı — Alanı AutoCAD'de AREA komutuyla ölçüp (iç boşluklar düşülmüş "
            "NET alan) girin. Kalınlık CM girilir, beton ve kalıpta ortak kullanılır. Kalıp = (dış çevre + "
            "iç boşluk çevreleri) × kalınlık — asansör/merdiven kuyusu gibi boşlukların yan yüzü de "
            "kalıplanır; alt yüz grobetona oturur. 'Radye Ekle'ye basmadan radye Kat Özeti'ne girmez."
        )
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("color:#d4a017; font-size:9pt;")
        lay.addWidget(bilgi)

        grup_stil = (
            "QGroupBox { color:#a569bd; font-weight:bold; border:1px solid #555;"
            " border-radius:4px; margin-top:10px; padding-top:8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left:8px; padding:0 4px; }"
            "QLabel { color:white; font-weight:normal; }"
        )

        beton_grup = QGroupBox("Beton")
        beton_grup.setStyleSheet(grup_stil)
        bg = QGridLayout(beton_grup)
        self.radye_ad_edit = QLineEdit()
        self.radye_ad_edit.setPlaceholderText("Boş bırakılırsa R1, R2 ...")
        self.radye_ad_edit.setToolTip("Radye adı (örn. 'Ana Blok', 'R1'). Excel ve özette bu adla görünür.")
        self.radye_ad_edit.setStyleSheet("background:#2a2a3a; color:white; border:1px solid #666; padding:4px;")
        self.radye_alan_spin = self._radye_spin(
            100000.0, 2, " m²", "Radyenin NET alanı (iç boşluklar düşülmüş) — AutoCAD'de AREA komutuyla ölçün.")
        self.radye_kalinlik_spin = self._radye_spin(
            1000.0, 1, " cm", "Radye kalınlığı SANTİMETRE (örn. 60). Beton ve kalıp hesabında ortak kullanılır.")
        self.radye_beton_label = QLabel("0.00 m³")
        bg.addWidget(QLabel("Radye Adı:"), 0, 0)
        bg.addWidget(self.radye_ad_edit, 0, 1)
        bg.addWidget(QLabel("Alan:"), 1, 0)
        bg.addWidget(self.radye_alan_spin, 1, 1)
        bg.addWidget(QLabel("Kalınlık:"), 2, 0)
        bg.addWidget(self.radye_kalinlik_spin, 2, 1)
        bg.addWidget(QLabel("Net Beton:"), 3, 0)
        bg.addWidget(self.radye_beton_label, 3, 1)
        bg.setColumnStretch(2, 1)
        lay.addWidget(beton_grup)

        kalip_grup = QGroupBox("Kalıp")
        kalip_grup.setStyleSheet(grup_stil)
        kg = QGridLayout(kalip_grup)
        self.radye_dis_cevre_spin = self._radye_spin(
            100000.0, 2, " m", "Radyenin dış çevre uzunluğu (metre).")
        kg.addWidget(QLabel("Dış Çevre:"), 0, 0)
        kg.addWidget(self.radye_dis_cevre_spin, 0, 1)

        self.radye_bosluk_table = QTableWidget(0, 2)
        self.radye_bosluk_table.setHorizontalHeaderLabels(["İç Boşluk Adı", "Çevre (m)"])
        self.radye_bosluk_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.radye_bosluk_table.setToolTip(
            "Asansör/merdiven kuyusu gibi iç boşluklar. Her biri ayrı satır; çevreleri kalıba EKLENİR. "
            "Hücreye çift tıklayıp düzenleyin.")
        self.radye_bosluk_table.setMaximumHeight(130)
        self.radye_bosluk_table.setStyleSheet(self._RADYE_TABLO_STIL)
        self.radye_bosluk_table.itemChanged.connect(self._radye_hesapla_guncelle)
        kg.addWidget(QLabel("İç Boşluklar:"), 1, 0, Qt.AlignmentFlag.AlignTop)
        kg.addWidget(self.radye_bosluk_table, 1, 1, 1, 2)
        bosluk_btn = QHBoxLayout()
        btn_b_ekle = self._radye_buton("+ Boşluk", "#5b2c6f", "Yeni iç boşluk satırı ekler.")
        btn_b_ekle.clicked.connect(lambda: self._radye_bosluk_satir_ekle())
        btn_b_sil = self._radye_buton("− Seçili Boşluk", "#7b241c", "Seçili iç boşluk satırını siler.")
        btn_b_sil.clicked.connect(self._radye_bosluk_sil)
        bosluk_btn.addWidget(btn_b_ekle)
        bosluk_btn.addWidget(btn_b_sil)
        bosluk_btn.addStretch()
        kg.addLayout(bosluk_btn, 2, 1, 1, 2)

        self.radye_toplam_cevre_label = QLabel("0.00 m")
        self.radye_kalip_label = QLabel("0.00 m²")
        kg.addWidget(QLabel("Toplam Çevre:"), 3, 0)
        kg.addWidget(self.radye_toplam_cevre_label, 3, 1)
        kg.addWidget(QLabel("Net Kalıp:"), 4, 0)
        kg.addWidget(self.radye_kalip_label, 4, 1)
        kg.setColumnStretch(2, 1)
        lay.addWidget(kalip_grup)

        self.radye_uyari_label = QLabel()
        self.radye_uyari_label.setWordWrap(True)
        self.radye_uyari_label.setStyleSheet("color:#e67e22; font-weight:bold;")
        lay.addWidget(self.radye_uyari_label)

        self.radye_sonuc_label = QLabel()
        self.radye_sonuc_label.setWordWrap(True)
        self.radye_sonuc_label.setStyleSheet(
            "color:#2ecc71; font-weight:bold; font-size:11pt; background:#2a2a3a;"
            " border:1px solid #a569bd; border-radius:4px; padding:8px;"
        )
        lay.addWidget(self.radye_sonuc_label)

        islem = QHBoxLayout()
        btn_ekle = self._radye_buton("Radye Ekle", "#8e44ad", "Formdaki radyeyi listeye ekler.")
        btn_ekle.clicked.connect(self._radye_ekle)
        btn_guncelle = self._radye_buton("Seçiliyi Güncelle", "#2471a3",
                                         "Listede seçili radyeyi formdaki değerlerle günceller.")
        btn_guncelle.clicked.connect(self._radye_guncelle)
        btn_sil = self._radye_buton("Seçiliyi Sil", "#922b21", "Listede seçili radyeyi siler.")
        btn_sil.clicked.connect(self._radye_sil)
        btn_excel = self._radye_buton(" Excel'e Aktar", "#1e8449",
                                      "Radye listesini 'Radye' sayfalı Excel dosyasına kaydeder (formüllü).")
        btn_excel.clicked.connect(self._radye_excel)
        for b in (btn_ekle, btn_guncelle, btn_sil):
            islem.addWidget(b)
        islem.addStretch()
        islem.addWidget(btn_excel)
        lay.addLayout(islem)

        self.radye_table = QTableWidget(0, len(self.RADYE_KOLONLAR))
        self.radye_table.setHorizontalHeaderLabels(self.RADYE_KOLONLAR)
        self.radye_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.radye_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.radye_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.radye_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.radye_table.setToolTip("Satıra tıklayınca radye forma yüklenir; düzeltip 'Seçiliyi Güncelle'.")
        self.radye_table.setMinimumHeight(150)
        self.radye_table.setStyleSheet(self._RADYE_TABLO_STIL)
        self.radye_table.currentCellChanged.connect(self._radye_satir_secildi)
        lay.addWidget(self.radye_table)

        self.radye_toplam_label = QLabel()
        self.radye_toplam_label.setStyleSheet(
            "color:#2ecc71; font-weight:bold; background:#2a2a3a; border:1px solid #a569bd;"
            " border-radius:4px; padding:6px;")
        lay.addWidget(self.radye_toplam_label)
        lay.addStretch()

        self._radye_hesapla_guncelle()
        self._radye_tablo_yenile()
        scroll.setWidget(icerik)
        dis.addWidget(scroll)
        return tab

    # -- iç boşluk tablosu --
    def _radye_bosluk_satir_ekle(self, ad: str = "", cevre: float = 0.0):
        tablo = self.radye_bosluk_table
        tablo.blockSignals(True)
        try:
            row = tablo.rowCount()
            tablo.insertRow(row)
            tablo.setItem(row, 0, QTableWidgetItem(ad or f"Boşluk {row + 1}"))
            item = QTableWidgetItem(f"{cevre:.2f}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            tablo.setItem(row, 1, item)
        finally:
            tablo.blockSignals(False)
        self._radye_hesapla_guncelle()

    def _radye_bosluk_sil(self):
        row = self.radye_bosluk_table.currentRow()
        if row < 0:
            row = self.radye_bosluk_table.rowCount() - 1
        if row >= 0:
            self.radye_bosluk_table.removeRow(row)
            self._radye_hesapla_guncelle()

    def _radye_bosluklar_oku(self) -> List[Dict]:
        bosluklar = []
        tablo = self.radye_bosluk_table
        for row in range(tablo.rowCount()):
            ad_item, cevre_item = tablo.item(row, 0), tablo.item(row, 1)
            try:
                cevre = float((cevre_item.text() if cevre_item else "0").replace(",", ".") or 0)
            except ValueError:
                cevre = -1.0  # radye_hesapla negatif çevreyi hata sayar -> kullanıcı görür
            bosluklar.append({"ad": (ad_item.text().strip() if ad_item else "") or f"Boşluk {row + 1}",
                              "cevre_m": cevre})
        return bosluklar

    # -- form <-> kayıt --
    def _radye_formdan_kayit(self) -> Dict:
        return {
            "ad": self.radye_ad_edit.text().strip(),
            "alan_m2": self.radye_alan_spin.value(),
            "kalinlik_cm": self.radye_kalinlik_spin.value(),
            "dis_cevre_m": self.radye_dis_cevre_spin.value(),
            "bosluklar": self._radye_bosluklar_oku(),
        }

    def _radye_forma_yukle(self, kayit: Dict):
        spinler = (self.radye_alan_spin, self.radye_kalinlik_spin, self.radye_dis_cevre_spin)
        for w in spinler:
            w.blockSignals(True)
        try:
            self.radye_ad_edit.setText(kayit.get("ad", ""))
            self.radye_alan_spin.setValue(kayit.get("alan_m2", 0.0))
            self.radye_kalinlik_spin.setValue(kayit.get("kalinlik_cm", 0.0))
            self.radye_dis_cevre_spin.setValue(kayit.get("dis_cevre_m", 0.0))
            self.radye_bosluk_table.blockSignals(True)
            self.radye_bosluk_table.setRowCount(0)
            self.radye_bosluk_table.blockSignals(False)
            for b in kayit.get("bosluklar", []):
                self._radye_bosluk_satir_ekle(b.get("ad", ""), b.get("cevre_m", 0.0))
        finally:
            for w in spinler:
                w.blockSignals(False)
        self._radye_hesapla_guncelle()

    def _radye_hesap(self) -> Dict:
        """Formdaki radyenin hesabı (UI'dan bağımsız test için ayrı)."""
        if radye_kaydi_hesapla is None:
            return {"hata": "Hesap modülü yüklenemedi", "uyari": "",
                    "beton_m3": 0.0, "kalip_m2": 0.0, "toplam_cevre_m": 0.0}
        return radye_kaydi_hesapla(self._radye_formdan_kayit())

    def _radye_hesapla_guncelle(self, *_):
        # Form kurulurken widget'lar tek tek oluşur — hepsi hazır olmadan hesaplama
        if not hasattr(self, "radye_sonuc_label"):
            return
        h = self._radye_hesap()
        self.radye_beton_label.setText(f"{tek_hane(h['beton_m3'])} m³")
        self.radye_toplam_cevre_label.setText(f"{h['toplam_cevre_m']:.2f} m")
        self.radye_kalip_label.setText(f"{tek_hane(h['kalip_m2'])} m²")
        if h["hata"]:
            self.radye_uyari_label.setText(
                "Alan ve kalınlık girin." if "sıfırdan büyük" in h["hata"] else f"⚠ {h['hata']}")
        else:
            self.radye_uyari_label.setText(f"⚠ {h['uyari']}" if h["uyari"] else "")
        self.radye_sonuc_label.setText(
            f"RADYE — Beton: {tek_hane(h['beton_m3'])} m³   |   Kalıp: {tek_hane(h['kalip_m2'])} m²"
        )

    # -- kayıt listesi --
    def _radye_listeye_yaz(self, satir: Optional[int]) -> bool:
        kayit = self._radye_formdan_kayit()
        h = radye_kaydi_hesapla(kayit) if radye_kaydi_hesapla else {"hata": "Hesap modülü yüklenemedi"}
        if h["hata"]:
            QMessageBox.warning(self, "Radye", f"Radye eklenemedi: {h['hata']}")
            return False
        if not kayit["ad"]:
            kayit["ad"] = (self.radye_kayitlari[satir]["ad"] if satir is not None
                           else f"R{len(self.radye_kayitlari) + 1}")
        if satir is None:
            self.radye_kayitlari.append(kayit)
            satir = len(self.radye_kayitlari) - 1
        else:
            self.radye_kayitlari[satir] = kayit
        self._radye_degisti(secili=satir)
        return True

    def _radye_ekle(self):
        if self._radye_listeye_yaz(None):
            self.radye_ad_edit.clear()

    def _radye_guncelle(self):
        satir = self.radye_table.currentRow()
        if not (0 <= satir < len(self.radye_kayitlari)):
            QMessageBox.information(self, "Radye", "Önce listeden güncellenecek radyeyi seçin.")
            return
        self._radye_listeye_yaz(satir)

    def _radye_sil(self):
        satir = self.radye_table.currentRow()
        if not (0 <= satir < len(self.radye_kayitlari)):
            QMessageBox.information(self, "Radye", "Önce listeden silinecek radyeyi seçin.")
            return
        del self.radye_kayitlari[satir]
        self._radye_degisti(secili=None)

    def _radye_degisti(self, secili: Optional[int] = None):
        """Radye listesi her değiştiğinde tek nokta: tablo + Kat Özeti."""
        self._radye_tablo_yenile(secili)
        if hasattr(self, "kat_ozeti_table"):
            self._kat_ozeti_yenile()

    def _radye_satir_secildi(self, satir: int, *_):
        if 0 <= satir < len(self.radye_kayitlari):
            self._radye_forma_yukle(self.radye_kayitlari[satir])

    def _radye_tablo_yenile(self, secili: Optional[int] = None):
        if not hasattr(self, "radye_table"):
            return
        tablo = self.radye_table
        tablo.blockSignals(True)
        try:
            tablo.setRowCount(0)
            for kayit in self.radye_kayitlari:
                h = radye_kaydi_hesapla(kayit)
                row = tablo.rowCount()
                tablo.insertRow(row)
                degerler = [kayit["ad"], f"{kayit['alan_m2']:.2f}", f"{kayit['kalinlik_cm']:.1f}",
                            f"{tek_hane(h['beton_m3'])}", f"{h['dis_cevre_m']:.2f}", f"{h['ic_cevre_m']:.2f}",
                            f"{tek_hane(h['kalip_m2'])}"]
                for col, metin in enumerate(degerler):
                    item = QTableWidgetItem(metin)
                    if col:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if col == 5 and kayit.get("bosluklar"):
                        item.setToolTip("\n".join(f"{b['ad']}: {b['cevre_m']:.2f} m" for b in kayit["bosluklar"]))
                    tablo.setItem(row, col, item)
            if secili is not None and 0 <= secili < tablo.rowCount():
                tablo.setCurrentCell(secili, 0)
        finally:
            tablo.blockSignals(False)
        t = radye_toplamlari(self.radye_kayitlari) if radye_toplamlari else None
        if t and t["adet"]:
            self.radye_toplam_label.setText(
                f"TOPLAM ({t['adet']} radye) — Beton: {tek_hane(t['beton_m3'], True)} m³ | Kalıp: {tek_hane(t['kalip_m2'], True)} m²")
        else:
            self.radye_toplam_label.setText("Henüz radye eklenmedi.")

    # -- Excel --
    def _rapor_proje_adi(self) -> str:
        """Ana penceredeki aktif projenin adı; yoksa bir kez sorulur (oturumda saklanır)."""
        if getattr(self, "_rapor_proje_adi_deger", None):
            return self._rapor_proje_adi_deger
        ad = ""
        ana = self.parent()
        try:
            pid = getattr(ana, "current_project_id", None)
            if pid and getattr(ana, "db", None) is not None:
                proje = ana.db.get_project(pid)
                ad = (proje or {}).get("ad", "") or ""
        except Exception as e:
            logger.debug(f"[RADYE] proje adı okunamadı: {e}")
        if not ad:
            metin, ok = QInputDialog.getText(self, "Proje Adı", "Excel başlığına yazılacak proje adı:")
            ad = metin.strip() if ok else ""
        self._rapor_proje_adi_deger = ad
        return ad

    def _radye_excel(self):
        if not any(not radye_kaydi_hesapla(k)["hata"] for k in self.radye_kayitlari):
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak radye yok — önce 'Radye Ekle'.")
            return
        if radye_sayfasi_yaz is None:
            QMessageBox.warning(self, "Uyarı", "Excel için openpyxl gerekli:\npip install openpyxl")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "radye_beton_kalip.xlsx",
                                                   "Excel (*.xlsx)")
        if not file_path:
            return
        try:
            from datetime import datetime
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Radye"
            radye_sayfasi_yaz(ws, self.radye_kayitlari, self._rapor_proje_adi(),
                              datetime.now().strftime("%d.%m.%Y"))
            wb.save(file_path)
            t = radye_toplamlari(self.radye_kayitlari)
            QMessageBox.information(
                self, "Başarılı",
                f"Kaydedildi:\n{file_path}\nBeton: {tek_hane(t['beton_m3'], True)} m³ | Kalıp: {tek_hane(t['kalip_m2'], True)} m²")
            logger.info(f"Radye Excel: {file_path}")
        except Exception as e:
            logger.error(f"[RADYE] Excel hatası: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{e}")

    # ── Rev-143: Perde Beton + Kalıp (Aşama 3/4 — kat ayarı + AutoCAD döngüsü + elle hesap) ──
    # Ölçek adı -> gerçek boy / çizim boyu çarpanı
    _PERDE_OLCEKLER = {"1:1": 1.0, "1:20": 20.0, "1:50": 50.0, "1:100": 100.0}
    PERDE_KOLONLAR = ["Ad", "Alan (m²)", "Çevre (m)", "Düşülen (m)", "Beton (m³)", "Kalıp (m²)"]

    def _perde_spin(self, maks: float, ondalik: int, sonek: str, ipucu: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, maks)
        spin.setDecimals(ondalik)
        spin.setSuffix(sonek)
        spin.setToolTip(ipucu)
        spin.setStyleSheet(self._RADYE_SPIN_STIL)
        spin.setMinimumWidth(160)
        spin.valueChanged.connect(self._perde_ayar_degisti)
        return spin

    def _perde_sekmesi_olustur(self) -> QWidget:
        """Perde sekmesini kurar (Rev-143).

        Neyi çözüyoruz? L/T/U kesitli perdelerin beton (alan × beton
        yüksekliği) ve kalıp ((çevre − bitişik uçlar) × net yükseklik)
        metrajı. Kat ayarı (kat yüksekliği, döşeme kalınlığı, beton esası)
        TEK yerde ve `self.yukseklik_ayari`'nda tutulur — döşeme aracı da
        buradan okuyacak. Perdeler AutoCAD döngüsüyle toplanır; tek perde
        için elle hesap formu yedek olarak durur.
        Nasıl test ederiz? scratchpad/test_perde.py (form),
        scratchpad/test_perde_secim.py (döngü + tablo).
        """
        tab = QWidget()
        dis = QVBoxLayout(tab)
        dis.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        icerik = QWidget()
        lay = QVBoxLayout(icerik)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        bilgi = QLabel(
            "Perde metrajı (L/T/U kesit) — Kat ayarlarını girin, \"AutoCAD'de Perdeleri Seç\" ile "
            "her perdenin kesitini (kapalı polyline) seçin. Kolona / başka perdeye bitişen uç "
            "çizgilerini de seçerseniz kalıptan düşülür; perde adı yazısını seçerseniz satır adı olur. "
            "Kalıp her zaman net yükseklikle (kat − döşeme) hesaplanır."
        )
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("color:#d4a017; font-size:9pt;")
        lay.addWidget(bilgi)

        grup_stil = (
            "QGroupBox { color:#a569bd; font-weight:bold; border:1px solid #555;"
            " border-radius:4px; margin-top:10px; padding-top:8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left:8px; padding:0 4px; }"
            "QLabel { color:white; font-weight:normal; }"
        )
        combo_stil = ("QComboBox { background:#2a2a3a; color:white; border:1px solid #666;"
                      " padding:4px; } QComboBox QAbstractItemView { background:#2a2a3a;"
                      " color:white; }")

        # ── Kat ayarları (ortak) ──
        ortak_grup = QGroupBox("Kat Ayarları")
        ortak_grup.setStyleSheet(grup_stil)
        og = QGridLayout(ortak_grup)
        self.perde_yukseklik_spin = self._perde_spin(
            50.0, 2, " m", "Kat yüksekliği (döşeme üstünden döşeme üstüne, metre).")
        self.perde_doseme_spin = self._perde_spin(
            5.0, 2, " m", "Döşeme kalınlığı (metre). Kalıp yüksekliği = kat − döşeme. "
            "Otomatik açıkken Döşeme sekmesinden gelir.")
        # Rev-163: döşeme kalınlığı Döşeme sekmesinden otomatik — perde kalıbından düşülür
        self.perde_doseme_otomatik_chk = QCheckBox("Döşeme sekmesinden otomatik")
        self.perde_doseme_otomatik_chk.setChecked(True)
        self.perde_doseme_otomatik_chk.setToolTip(
            "Açık: bu katın Döşeme sekmesindeki döşemelerden HAKİM kalınlık (en büyük alanlı) alınır; "
            "döşeme yoksa Döşeme sekmesinin varsayılan kalınlığı. Perde kalıbı = (kat − döşeme) × çevre. "
            "Beton etkilenmez (Beton Esası 'Tam kat' iken). Kapalı: elle girin.")
        self.perde_doseme_otomatik_chk.setStyleSheet("color:white;")
        self.perde_doseme_otomatik_chk.toggled.connect(self._perde_ayar_degisti)
        self.perde_doseme_kaynak_label = QLabel()
        self.perde_doseme_kaynak_label.setWordWrap(True)
        self.perde_doseme_kaynak_label.setStyleSheet("color:#48c9b0; font-size:9pt;")
        self.perde_esas_combo = QComboBox()
        for anahtar, ad in BETON_ESASLARI.items():
            self.perde_esas_combo.addItem(ad, anahtar)
        self.perde_esas_combo.setToolTip(
            "Tam kat: perde betonu kat yüksekliğiyle (kolon aracıyla aynı; döşeme kalınlığındaki "
            "beton döşemede de sayılırsa çift sayılır). Net: kat − döşeme (çift sayım yok).")
        self.perde_esas_combo.setStyleSheet(combo_stil)
        self.perde_esas_combo.currentIndexChanged.connect(self._perde_ayar_degisti)
        self.perde_birim_combo = QComboBox()
        self.perde_birim_combo.addItems(["Otomatik", "cm", "mm", "m"])
        self.perde_birim_combo.setToolTip(
            "Çizim birimi. Otomatik = AutoCAD INSUNITS, tanımsızsa cm. "
            "Yanlışsa alan 100 / 10.000 kat hatalı çıkar — ilk perdede ayrıca teyit edilir.")
        self.perde_birim_combo.setStyleSheet(combo_stil)
        self.perde_olcek_combo = QComboBox()
        self.perde_olcek_combo.addItems(list(self._PERDE_OLCEKLER))
        self.perde_olcek_combo.setToolTip(
            "Çizim gerçek boyutta (1:1) mi, küçültülerek mi çizildi? Çoğu çizim 1:1'dir. "
            "Emin değilseniz 1:1 bırakın ve ilk perdede AREA ile karşılaştırın.")
        self.perde_olcek_combo.setStyleSheet(combo_stil)
        for combo in (self.perde_birim_combo, self.perde_olcek_combo):
            combo.currentTextChanged.connect(self._perde_teyit_sifirla)
        satirlar = [("Kat Yüksekliği:", self.perde_yukseklik_spin),
                    ("Döşeme Kalınlığı:", self.perde_doseme_spin),
                    ("Beton Esası:", self.perde_esas_combo),
                    ("Çizim Birimi:", self.perde_birim_combo),
                    ("Çizim Ölçeği:", self.perde_olcek_combo)]
        for i, (etiket, w) in enumerate(satirlar):
            og.addWidget(QLabel(etiket), i, 0)
            og.addWidget(w, i, 1)
        og.addWidget(self.perde_doseme_otomatik_chk, 1, 2)
        og.addWidget(self.perde_doseme_kaynak_label, len(satirlar), 0, 1, 4)
        og.setColumnStretch(3, 1)
        lay.addWidget(ortak_grup)
        self._perde_alan_teyitli = False

        # ── AutoCAD döngüsü + tablo ──
        secim_grup = QGroupBox("Perdeler (AutoCAD'den)")
        secim_grup.setStyleSheet(grup_stil)
        sg = QVBoxLayout(secim_grup)
        btn_sec = QPushButton(" AutoCAD'de Perdeleri Seç")
        btn_sec.setToolTip("AutoCAD'e geçer; her perde: kesit + [bitişik uç çizgileri] + [ad yazısı] + "
                           "ENTER. Bitirmek için boş ENTER.")
        btn_sec.setStyleSheet(
            "background:#8e44ad; color:white; font-weight:bold; padding:6px 14px;"
            " border:none; border-radius:3px;"
        )
        btn_sec.clicked.connect(self._perde_sec)
        self.perde_aktif_kat_label = QLabel()
        self.perde_aktif_kat_label.setStyleSheet("color:#f5b041; font-weight:bold;")
        self.perde_aktif_kat_label.setToolTip(
            "Perdeler aktif kata yazılır. Kat, Demir Metrajı sekmesindeki kat listesinden eklenir/seçilir. "
            "Kat ayarları (yükseklik, döşeme, beton esası) her kat için ayrı saklanır.")
        sg.addWidget(self.perde_aktif_kat_label)
        sg.addWidget(btn_sec)
        self.perde_esas_label = QLabel()
        self.perde_esas_label.setWordWrap(True)
        self.perde_esas_label.setStyleSheet("color:#5dade2; font-weight:bold;")
        sg.addWidget(self.perde_esas_label)
        self.perde_table = QTableWidget()
        self.perde_table.setColumnCount(len(self.PERDE_KOLONLAR))
        self.perde_table.setHorizontalHeaderLabels(self.PERDE_KOLONLAR)
        self.perde_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.perde_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.perde_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.perde_table.setMinimumHeight(220)
        self.perde_table.setStyleSheet(
            "QTableWidget { background:#1e1e2e; color:#e0e0e0; gridline-color:#444;"
            " border:1px solid #555; }"
            "QHeaderView::section { background:#2d2d3d; color:#a569bd; font-weight:bold;"
            " padding:5px; border:1px solid #444; }"
            "QTableWidget::item:selected { background:#3a3a5a; }"
        )
        sg.addWidget(self.perde_table)
        alt = QHBoxLayout()
        btn_sil = QPushButton("Seçili Sil")
        btn_sil.setToolTip("Seçili perdeleri siler ve çizimdeki yeşil rengi geri alır.")
        btn_sil.setStyleSheet("background:#c0392b; color:white; font-weight:bold; padding:5px 12px;"
                              " border:none; border-radius:3px;")
        btn_sil.clicked.connect(self._perde_sil)
        alt.addWidget(btn_sil)
        btn_temizle = QPushButton("Temizle")
        btn_temizle.setToolTip("Tüm perdeleri siler ve yeşil renkleri geri alır.")
        btn_temizle.setStyleSheet("background:#7f8c8d; color:white; font-weight:bold; padding:5px 12px;"
                                  " border:none; border-radius:3px;")
        btn_temizle.clicked.connect(self._perde_temizle)
        alt.addWidget(btn_temizle)
        alt.addStretch()
        btn_excel = QPushButton(" PERDE EXCEL'E AKTAR")
        btn_excel.setToolTip("Tüm katların perdelerini, her katın hesap esasıyla birlikte Excel'e yazar.")
        btn_excel.setStyleSheet(
            "background:#1e8449; color:white; font-weight:bold; padding:5px 14px;"
            " border:2px solid #2ecc71; border-radius:3px;"
        )
        btn_excel.clicked.connect(self._perde_excel)
        alt.addWidget(btn_excel)
        sg.addLayout(alt)
        self.perde_toplam_label = QLabel()
        self.perde_toplam_label.setStyleSheet(
            "color:#2ecc71; font-weight:bold; font-size:10pt; background:#2a2a3a;"
            " border:1px solid #a569bd; border-radius:4px; padding:6px;"
        )
        sg.addWidget(self.perde_toplam_label)
        lay.addWidget(secim_grup)

        # ── Tek perde elle hesap (yedek) ──
        elle_grup = QGroupBox("Tek Perde — Elle Hesap (AREA ile ölçülen değerlerle)")
        elle_grup.setStyleSheet(grup_stil)
        eg = QGridLayout(elle_grup)
        self.perde_alan_spin = self._perde_spin(
            10000.0, 2, " m²", "Perde kesit alanı — AutoCAD'de AREA komutuyla ölçün.")
        self.perde_cevre_spin = self._perde_spin(
            100000.0, 2, " m", "Kesitin toplam çevresi (metre).")
        self.perde_dusulen_spin = self._perde_spin(
            100000.0, 2, " m", "Kolona / başka perdeye bitişen, kalıp kurulmayan uçların toplamı (metre).")
        self.perde_beton_label = QLabel("0.00 m³")
        self.perde_kalip_label = QLabel("0.00 m²")
        self.perde_kalinlik_label = QLabel("-")
        self.perde_kalinlik_label.setToolTip(
            "Eşdeğer kalınlık = 2 × Alan / Çevre. Perdede 0.15-0.60 m arası beklenir; "
            "dışındaysa alan veya çevre girişini kontrol edin.")
        elle = [("Kesit Alanı:", self.perde_alan_spin), ("Çevre:", self.perde_cevre_spin),
                ("Düşülen Uçlar:", self.perde_dusulen_spin), ("Beton:", self.perde_beton_label),
                ("Kalıp:", self.perde_kalip_label), ("Eşdeğer Kalınlık:", self.perde_kalinlik_label)]
        for i, (etiket, w) in enumerate(elle):
            eg.addWidget(QLabel(etiket), i, 0)
            eg.addWidget(w, i, 1)
        eg.setColumnStretch(2, 1)
        lay.addWidget(elle_grup)

        self.perde_uyari_label = QLabel()
        self.perde_uyari_label.setWordWrap(True)
        self.perde_uyari_label.setStyleSheet("color:#e67e22; font-weight:bold;")
        lay.addWidget(self.perde_uyari_label)
        self.perde_sonuc_label = QLabel()
        self.perde_sonuc_label.setWordWrap(True)
        self.perde_sonuc_label.setStyleSheet(
            "color:#2ecc71; font-weight:bold; font-size:11pt; background:#2a2a3a;"
            " border:1px solid #a569bd; border-radius:4px; padding:8px;"
        )
        lay.addWidget(self.perde_sonuc_label)
        lay.addStretch()

        self._perde_ayar_degisti()
        scroll.setWidget(icerik)
        dis.addWidget(scroll)
        return tab

    # ── kat ayarı (kat başına) ──
    def _perde_ayar_oku(self) -> "KatYukseklikAyari":
        doseme = self.perde_doseme_spin.value()
        if self._perde_doseme_otomatik_mi():
            doseme = self._perde_otomatik_doseme(self.aktif_kat_adi)[0]
        return KatYukseklikAyari(
            self.perde_yukseklik_spin.value(),
            doseme,
            self.perde_esas_combo.currentData() or "tam",
        )

    def _perde_kat_ayari(self, kat: str) -> "KatYukseklikAyari":
        """Katın kayıtlı ayarı; yoksa formdaki değerler. Rev-163: otomatik açıkken döşeme
        kalınlığı HER ZAMAN o katın güncel Döşeme sekmesi kayıtlarından gelir."""
        a = self.kat_yukseklik_ayarlari.get(kat) or self._perde_ayar_oku()
        if self._perde_doseme_otomatik_mi():
            a = dataclasses.replace(a, doseme_kalinligi_m=self._perde_otomatik_doseme(kat)[0])
        return a

    def _perde_doseme_otomatik_mi(self) -> bool:
        chk = getattr(self, "perde_doseme_otomatik_chk", None)
        return bool(chk is not None and chk.isChecked())

    def _perde_otomatik_doseme(self, kat: str):
        """(kalınlık_m, kaynak_metni): katın döşemelerinden hakim kalınlık; döşeme yoksa
        Döşeme sekmesinin varsayılan kalınlığı."""
        kayitlar = getattr(self, "_doseme_kat_kayitlari", {}).get(kat) or []
        t = hakim_doseme_kalinligi_cm(kayitlar) if hakim_doseme_kalinligi_cm else None
        if t is not None:
            farkli = sorted({float(s.get("kalinlik_cm") or 0) for s in kayitlar} - {0.0})
            ek = (f" (katta {', '.join(f'{x:g}' for x in farkli)} cm var — en büyük alanlı alındı)"
                  if len(farkli) > 1 else "")
            return round(t / 100.0, 4), f"Döşeme sekmesi: {len(kayitlar)} döşeme, {t:g} cm{ek}"
        spin = getattr(self, "doseme_varsayilan_h_spin", None)
        t = spin.value() if spin is not None else 15.0
        return round(t / 100.0, 4), f"Bu katta henüz döşeme yok — Döşeme sekmesi varsayılanı {t:g} cm"

    def _perde_doseme_otomatik_yenile(self, *_):
        """Döşeme kayıtları / varsayılan kalınlık değişince perde hesapları tazelensin."""
        if self._perde_doseme_otomatik_mi():
            self._perde_ayar_degisti()

    def _perde_ayar_degisti(self, *_):
        # Form kurulurken widget'lar tek tek oluşur — hepsi hazır olmadan hesaplama
        if not hasattr(self, "perde_sonuc_label") or KatYukseklikAyari is None:
            return
        # Rev-163: otomatik döşeme kalınlığını forma yansıt (spin salt okunur)
        otomatik = self._perde_doseme_otomatik_mi()
        self.perde_doseme_spin.setEnabled(not otomatik)
        if otomatik:
            deger, kaynak = self._perde_otomatik_doseme(self.aktif_kat_adi)
            self.perde_doseme_spin.blockSignals(True)
            self.perde_doseme_spin.setValue(deger)
            self.perde_doseme_spin.blockSignals(False)
            beton = ("beton etkilenmez (Beton Esası: Tam kat)"
                     if (self.perde_esas_combo.currentData() or "tam") == "tam"
                     else "Beton Esası 'Net' seçili — beton da net yükseklikle alınır")
            self.perde_doseme_kaynak_label.setText(
                f"Döşeme kalınlığı otomatik — {kaynak}. Perde kalıbından düşülür; {beton}.")
        else:
            self.perde_doseme_kaynak_label.setText("Döşeme kalınlığı elle girildi.")
        # Döşeme aracı da bu nesneleri okuyacak (beton esası: çift sayım kararı)
        self.yukseklik_ayari = self._perde_ayar_oku()
        if self.aktif_kat_adi:
            self.kat_yukseklik_ayarlari[self.aktif_kat_adi] = self.yukseklik_ayari
        self._perde_hesapla_guncelle()
        self._perde_tablo_yenile()
        self._doseme_esas_notu_guncelle()
        # Rev-161: kolon aracından gelen perdeler de bu kat ayarıyla hesaplanır
        if self.aktif_kat_adi and hasattr(self, "beton_kalip_table"):
            self._beton_kalip_kat_kolon_satirlarini_yeniden_olustur(self.aktif_kat_adi)
            self._beton_kalip_toplamlar_guncelle()

    def _aktif_kat_degisti(self):
        """Rev-151: aktif kat değişince kata bağlı TÜM sekmeleri o kata çevirir
        (perde ayarı + tablo, kiriş, döşeme) ve kat özetini tazeler."""
        self._perde_aktif_kat_yukle()
        kat = self.aktif_kat_adi or ""
        for edit in (getattr(self, "kiris_kat_edit", None), getattr(self, "doseme_kat_edit", None),
                     getattr(self, "merdiven_kat_edit", None)):
            if edit is not None:
                edit.setText(kat)
        if hasattr(self, "kiris_table"):
            self._kiris_tablo_yenile()
        if hasattr(self, "doseme_table"):
            self._doseme_tablo_yenile()
        if hasattr(self, "merdiven_table"):
            self._merdiven_tablo_yenile()
        if hasattr(self, "kat_ozeti_table"):
            self._kat_ozeti_yenile()

    def _perde_aktif_kat_yukle(self):
        """Aktif kat değişince o katın kayıtlı ayarını forma yükler (yoksa
        formdaki değerler yeni katın ayarı olur) ve tabloyu o kata göre gösterir."""
        if not hasattr(self, "perde_sonuc_label") or KatYukseklikAyari is None:
            return
        ayar = self.kat_yukseklik_ayarlari.get(self.aktif_kat_adi)
        if ayar is not None:
            widgetler = (self.perde_yukseklik_spin, self.perde_doseme_spin, self.perde_esas_combo)
            for w in widgetler:
                w.blockSignals(True)
            try:
                self.perde_yukseklik_spin.setValue(ayar.kat_yuksekligi_m)
                self.perde_doseme_spin.setValue(ayar.doseme_kalinligi_m)
                self.perde_esas_combo.setCurrentIndex(max(0, self.perde_esas_combo.findData(ayar.beton_esasi)))
            finally:
                for w in widgetler:
                    w.blockSignals(False)
        self._perde_ayar_degisti()

    def _perde_teyit_sifirla(self, *_):
        """Birim/ölçek değişince sonraki ilk perde yeniden teyit edilir."""
        self._perde_alan_teyitli = False

    def _perde_birim(self) -> str:
        secim = self.perde_birim_combo.currentText()
        if secim in ("mm", "cm", "m"):
            return secim
        birim = None
        try:
            birim = self.acad_connector.cizim_birimi_oku()
        except Exception as e:
            logger.error(f"[PERDE] INSUNITS okunamadı: {e}", exc_info=True)
        return birim or "cm"

    # ── AutoCAD döngüsü ──
    def _perde_sec(self):
        """Aktif katı ve kat ayarını doğrular, toplu seçim panelini açıp
        döngüyü başlatır, sonucu (kat, poligon) anahtarıyla registry'ye işler
        (aynı kat + aynı poligon -> güncelleme, farklı kat -> ayrı kayıt)."""
        if not self.acad_connector or not getattr(self.acad_connector, "bagli", False):
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return
        kat = self.aktif_kat_adi
        if not kat:
            QMessageBox.warning(
                self, "Kat Seçimi Gerekli",
                "Önce bir kat eklemeniz/seçmeniz gerekiyor!\n\n"
                "Demir Metrajı sekmesindeki 'Kat İsmi Girişi' bölümünden kat ekleyin veya "
                "listeden seçin — perdeler o kata yazılır.")
            return
        ayar = self._perde_ayar_oku()
        hata = ayar.dogrula()
        if hata:
            QMessageBox.warning(self, "Kat Ayarı", f"{hata}\n\nKat Ayarları bölümünü düzeltin.")
            return
        # Bu katın perdeleri bu ayarla hesaplanır — kata kilitle
        self.kat_yukseklik_ayarlari[kat] = ayar
        olcek_adi = self.perde_olcek_combo.currentText()
        mevcut ={h: s for (k, h), s in self.perde_kayitlari.items() if k == kat}
        panel = PerdeDonguPaneli(
            self.acad_connector, self._perde_birim(), olcek_adi, self._PERDE_OLCEKLER[olcek_adi],
            ayar, self._perde_alan_teyitli, mevcut, self,
            ad_kayitli=lambda ad: self._kolon_kaydi_bul(kat, ad) is not None,
            okunamayanlar=[ad for (k, ad) in self.okunamayan_elemanlar if k == kat],
        )
        QTimer.singleShot(0, panel._dongu)
        sonuc = panel.exec()
        self._perde_alan_teyitli = panel.alan_teyitli
        if sonuc != QDialog.DialogCode.Accepted:
            return
        for satir in panel.sonuclar():
            anahtar = (kat, satir["poligon_handle"])
            eski = self.perde_kayitlari.get(anahtar)
            kayit = dict(satir)
            kayit.pop("yeni_boyanan", None)
            kayit.pop("onceki_renkler", None)
            # Rev-160 ortak ad havuzu: aynı adlı kolon-aracı kaydı / başka poligonlu perde kaydı
            # bu kayıtla DEĞİŞTİRİLİR (mükerrer sorusu panelde soruldu); okunamayanlar listesinden düşer
            n = eleman_ad_normalize(satir.get("ad"))
            if n:
                kolon_anahtar = self._kolon_kaydi_bul(kat, n)
                if kolon_anahtar:
                    del self.beton_kalip_kolon_kayitlari[kolon_anahtar]
                for a in [a for a, s in self.perde_kayitlari.items()
                          if a[0] == kat and a != anahtar and eleman_ad_normalize(s.get("ad")) == n]:
                    del self.perde_kayitlari[a]
                self.okunamayan_elemanlar.pop((kat, n), None)
            self.perde_kayitlari[anahtar] = kayit
            if eski:
                # Güncellemede artık kullanılmayan eski handle'ların yeşilini sök
                for h in eski.get("handleler") or []:
                    if h not in self._perde_kullanilan_handleler(kat):
                        self._perde_renk_geri(h)
        # Kolon-aracı kaydı perdeye devredildiyse Beton & Kalıp tablosu da güncellensin
        self._beton_kalip_kat_kolon_satirlarini_yeniden_olustur(kat)
        self._beton_kalip_toplamlar_guncelle()
        self._perde_tablo_yenile()
        self._kat_ozeti_yenile()
        logger.info(f"[PERDE] {len(panel.sonuclar())} perde '{kat}' katına kaydedildi "
                    f"(katta toplam {sum(1 for a in self.perde_kayitlari if a[0] == kat)})")

    # ── Rev-160: kolon aracı + perde aracı ORTAK ad havuzu (kat + ad) ──
    def _kolon_kaydi_bul(self, kat: str, ad: str):
        """Kolon aracı registry'sinde bu katta bu ad (normalize) var mı? Anahtar | None."""
        n = eleman_ad_normalize(ad)
        return next((a for a in self.beton_kalip_kolon_kayitlari
                     if a[0] == kat and eleman_ad_normalize(a[1]) == n), None)

    def _perde_kaydi_bul(self, kat: str, ad: str):
        """Perde aracı registry'sinde bu katta bu ad var mı? Anahtar | None."""
        n = eleman_ad_normalize(ad)
        return next((a for a, s in self.perde_kayitlari.items()
                     if a[0] == kat and eleman_ad_normalize(s.get("ad")) == n), None)

    def _eleman_renk(self, handle, renk):
        """Program rengi ayarla; önceki program rengini döndür (None = orijinal)."""
        if not handle or not self.acad_connector:
            return None
        try:
            return self.acad_connector.obje_rengi_ayarla(handle, renk)
        except Exception as e:
            logger.error(f"[KOLON] renk ayarlanamadı ({handle}): {e}", exc_info=True)
            return None

    def _perde_kullanilan_handleler(self, kat: str) -> set:
        return {h for (k, _), s in self.perde_kayitlari.items() if k == kat
                for h in (s.get("handleler") or [])}

    def _perde_renk_geri(self, handle):
        if not handle or not self.acad_connector:
            return
        try:
            self.acad_connector.obje_isaret_geri_al(handle)
        except Exception as e:
            logger.error(f"[PERDE] renk geri alma hatası: {e}", exc_info=True)

    @staticmethod
    def _perde_satir_hesap(s: Dict, a: "KatYukseklikAyari") -> Dict:
        return perde_hesapla(s["alan_m2"], s["cevre_m"], a.kat_yuksekligi_m,
                             a.doseme_kalinligi_m, a.beton_esasi, s["dusulen_m"])

    def _perde_tablo_yenile(self):
        """Perde tablosu AKTİF katı, HER ZAMAN o katın güncel ayarıyla
        gösterir — başlıktaki esas ile satırlar asla çelişmez. Ardından genel
        Beton & Kalıp tablosu da senkronlanır."""
        if not hasattr(self, "perde_table"):
            return
        kat = self.aktif_kat_adi
        self.perde_aktif_kat_label.setText(
            f"Aktif Kat: {kat}" if kat else "Aktif Kat: — (Demir Metrajı sekmesinden kat ekleyin/seçin)")
        a = self.yukseklik_ayari
        ayar_hata = a.dogrula()
        self.perde_esas_label.setText(
            f"Hesap esası — {a.esas_etiketi()}" if not ayar_hata else f"⚠ Kat ayarı: {ayar_hata}")
        tablo = self.perde_table
        tablo.setRowCount(0)
        beton = kalip = 0.0
        for (k, handle), s in self.perde_kayitlari.items():
            if k != kat:
                continue
            h = self._perde_satir_hesap(s, a)
            beton += h["beton_m3"]
            kalip += h["kalip_m2"]
            row = tablo.rowCount()
            tablo.insertRow(row)
            degerler = [s["ad"], f"{s['alan_m2']:.2f}", f"{s['cevre_m']:.2f}", f"{s['dusulen_m']:.2f}",
                        f"{tek_hane(h['beton_m3'])}", f"{tek_hane(h['kalip_m2'])}"]
            for col, deger in enumerate(degerler):
                item = QTableWidgetItem(deger)
                if s.get("uyari"):
                    item.setToolTip(s["uyari"])
                    item.setForeground(QColor("#f5b041"))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, handle)
                tablo.setItem(row, col, item)
        g = self._perde_genel_toplam()
        self.perde_toplam_label.setText(
            f"{kat or '—'}: {tablo.rowCount()} perde | Beton: {tek_hane(beton, True)} m³ | Kalıp: {tek_hane(kalip, True)} m²"
            f"   —   TÜM KATLAR: {g['adet']} perde | Beton: {tek_hane(g['beton'], True)} m³ | Kalıp: {tek_hane(g['kalip'], True)} m²")
        self._perde_beton_kalip_senkronla()

    def _perde_genel_toplam(self) -> Dict:
        beton = kalip = 0.0
        for (k, _), s in self.perde_kayitlari.items():
            h = self._perde_satir_hesap(s, self._perde_kat_ayari(k))
            beton += h["beton_m3"]
            kalip += h["kalip_m2"]
        return {"adet": len(self.perde_kayitlari), "beton": round(beton, 3), "kalip": round(kalip, 3)}

    def _perde_sil(self):
        kat = self.aktif_kat_adi
        satirlar = sorted({i.row() for i in self.perde_table.selectedIndexes()})
        if not satirlar:
            QMessageBox.information(self, "Bilgi", "Silmek için tablodan perde seçin.")
            return
        for row in satirlar:
            item = self.perde_table.item(row, 0)
            handle = item.data(Qt.ItemDataRole.UserRole) if item else None
            kayit = self.perde_kayitlari.pop((kat, handle), None)
            if kayit:
                for h in kayit.get("handleler") or []:
                    if h not in self._perde_kullanilan_handleler(kat):
                        self._perde_renk_geri(h)
        self._perde_tablo_yenile()

    def _perde_temizle(self):
        """AKTİF katın perdelerini siler (diğer katlara dokunmaz)."""
        kat = self.aktif_kat_adi
        anahtarlar = [a for a in self.perde_kayitlari if a[0] == kat]
        if not anahtarlar:
            return
        cevap = QMessageBox.question(
            self, "Temizle", f"'{kat}' katının {len(anahtarlar)} perdesi silinecek ve yeşil renkler "
            "geri alınacak. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return
        handleler = self._perde_kullanilan_handleler(kat)
        for a in anahtarlar:
            del self.perde_kayitlari[a]
        for h in handleler:
            self._perde_renk_geri(h)
        self._perde_tablo_yenile()

    # ── Genel Beton & Kalıp tablosuna bağlama ──
    PERDE_BK_ETIKETI = "perde"

    def _perde_beton_kalip_senkronla(self):
        """Perdeleri genel Beton & Kalıp tablosuna yazar (Rev-143 Aşama 4).

        Neyi çözüyoruz? Kolon/kiriş/perde betonu tek toplamda görünsün. Kolon
        deseniyle aynı: "perde" etiketli satırlar silinip registry'den (her
        katın güncel ayarıyla) YENİDEN kurulur — mükerrer birikme olmaz,
        manuel ve kolon satırlarına dokunulmaz.
        Nasıl test ederiz? test_perde_kat_excel.py: 2 kat -> 2 satır, esas
        değişince satır güncellenir, silinince tablodan kalkar.
        """
        tablo = getattr(self, "beton_kalip_table", None)
        if tablo is None:
            return
        for row in reversed(range(tablo.rowCount())):
            item = tablo.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == self.PERDE_BK_ETIKETI:
                tablo.removeRow(row)
        fire_pct = self.bk_fire_spin.value() if hasattr(self, "bk_fire_spin") else 0.0
        for (k, _), s in self.perde_kayitlari.items():
            a = self._perde_kat_ayari(k)
            h = self._perde_satir_hesap(s, a)
            if h["hata"]:
                continue
            ad = s["ad"] if s["ad"].lower().startswith("perde") else f"Perde {s['ad']}"
            siparis = round(h["beton_m3"] * (1 + fire_pct / 100), 3)
            veriler = [k, ad, "1", "-", "-", f"{h['beton_yuksekligi_m']:.2f}",
                       f"{tek_hane(h['beton_m3'])}", f"{fire_pct:.1f}", f"{tek_hane(siparis)}", f"{tek_hane(h['kalip_m2'])}"]
            row = tablo.rowCount()
            tablo.insertRow(row)
            for col, deger in enumerate(veriler):
                item = QTableWidgetItem(deger)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, self.PERDE_BK_ETIKETI)
                    item.setToolTip(f"Perde sekmesinden (alan {s['alan_m2']:.2f} m², "
                                    f"{BETON_ESASLARI.get(a.beton_esasi, '')}). Düzeltme Perde sekmesinde yapılır.")
                self._bk_tam_deger(item, col, h["beton_m3"], siparis, h["kalip_m2"])
                tablo.setItem(row, col, item)
        if hasattr(self, "bk_toplam_beton_label"):
            self._beton_kalip_toplamlar_guncelle()

    # ── Excel ──
    PERDE_EXCEL_KOLONLAR = ["Kat", "Ad", "Alan (m²)", "Çevre (m)", "Düşülen (m)", "Beton Yük. (m)",
                            "Kalıp Yük. (m)", "Beton (m³)", "Kalıp (m²)"]

    def _perde_excel_verisi(self):
        """(başlık satırları, tablo satırları). Başlıkta her katın hesap esası
        yazar; satırlar kat kat, her katın sonunda ARA TOPLAM, en altta GENEL TOPLAM."""
        katlar = []
        for (k, _) in self.perde_kayitlari:
            if k not in katlar:
                katlar.append(k)
        basliklar = ["PERDE BETON + KALIP METRAJI", "Hesap esası (kat bazında):"]
        satirlar = []
        g_beton = g_kalip = 0.0
        for k in katlar:
            a = self._perde_kat_ayari(k)
            basliklar.append(f"  {k}: {a.esas_etiketi()}")
            k_beton = k_kalip = 0.0
            for (kk, _), s in self.perde_kayitlari.items():
                if kk != k:
                    continue
                h = self._perde_satir_hesap(s, a)
                k_beton += h["beton_m3"]
                k_kalip += h["kalip_m2"]
                satirlar.append([k, s["ad"], s["alan_m2"], s["cevre_m"], s["dusulen_m"],
                                 h["beton_yuksekligi_m"], h["net_yukseklik_m"], h["beton_m3"], h["kalip_m2"]])
            satirlar.append([k, "ARA TOPLAM", "", "", "", "", "", round(k_beton, 3), round(k_kalip, 3)])
            g_beton += k_beton
            g_kalip += k_kalip
        satirlar.append(["", "GENEL TOPLAM", "", "", "", "", "", round(g_beton, 3), round(g_kalip, 3)])
        basliklar.append("Kalıp her zaman net yükseklikle (kat − döşeme) × (çevre − bitişik uçlar) hesaplanır.")
        return basliklar, satirlar

    def _perde_excel(self):
        if not self.perde_kayitlari:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak perde yok.")
            return
        if not PANDAS_AVAILABLE:
            QMessageBox.warning(self, "Uyarı", "Excel için pandas+openpyxl gerekli:\npip install pandas openpyxl")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "perde_metraj.xlsx", "Excel (*.xlsx)")
        if not file_path:
            return
        try:
            basliklar, satirlar = self._perde_excel_verisi()
            df = pd.DataFrame(satirlar, columns=self.PERDE_EXCEL_KOLONLAR)
            with pd.ExcelWriter(file_path, engine="openpyxl") as yazici:
                df.to_excel(yazici, index=False, sheet_name="Perde", startrow=len(basliklar) + 1)
                sayfa = yazici.sheets["Perde"]
                for i, metin in enumerate(basliklar, start=1):
                    sayfa.cell(row=i, column=1, value=metin)
                beton_kalip_sutunlari_tek_hane(sayfa)   # Rev-166
            g = satirlar[-1]
            QMessageBox.information(self, "Başarılı",
                                    f"Kaydedildi:\n{file_path}\nBeton: {tek_hane(g[7])} m³ | Kalıp: {tek_hane(g[8])} m²")
            logger.info(f"Perde Excel: {file_path}")
        except Exception as e:
            logger.error(f"[PERDE] Excel hatası: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{e}")

    # ── tek perde elle hesap ──
    def _perde_hesap(self) -> Dict:
        """Formdaki değerlerle perde_hesapla sonucu (UI'dan bağımsız test için ayrı)."""
        if perde_hesapla is None:
            return {"hata": "Hesap modülü yüklenemedi", "uyari": "", "beton_m3": 0.0,
                    "kalip_m2": 0.0, "esdeger_kalinlik_m": 0.0}
        a = self.yukseklik_ayari
        return perde_hesapla(self.perde_alan_spin.value(), self.perde_cevre_spin.value(),
                             a.kat_yuksekligi_m, a.doseme_kalinligi_m, a.beton_esasi,
                             self.perde_dusulen_spin.value())

    def _perde_hesapla_guncelle(self, *_):
        h = self._perde_hesap()
        self.perde_beton_label.setText(f"{tek_hane(h['beton_m3'])} m³")
        self.perde_kalip_label.setText(f"{tek_hane(h['kalip_m2'])} m²")
        t = h["esdeger_kalinlik_m"]
        self.perde_kalinlik_label.setText(f"{t:.2f} m" if t > 0 else "-")
        if h["hata"]:
            yuk_hata = self.perde_yukseklik_spin.value() <= 0 or self.perde_alan_spin.value() <= 0
            self.perde_uyari_label.setText("Yükseklik ve kesit alanı girin." if yuk_hata else f"⚠ {h['hata']}")
        else:
            self.perde_uyari_label.setText(f"⚠ {h['uyari']}" if h["uyari"] else "")
        self.perde_sonuc_label.setText(
            f"PERDE — Beton: {tek_hane(h['beton_m3'])} m³   |   Kalıp: {tek_hane(h['kalip_m2'])} m²"
        )

    # ── Rev-144: Döşeme (Plak) Beton + Kalıp (Aşama 1/3 — elle giriş) ──
    DOSEME_KOLONLAR = ["No", "Döşeme Adı", "Brüt Alan (m²)", "Boşluk Alanı (m²)", "Net Alan (m²)",
                       "Kalınlık (cm)", "Beton (m³)", "Alt Kalıp (m²)", "Kenar Kalıbı (m²)",
                       "Toplam Kalıp (m²)", "Kaynak", "Handle", "Tip"]   # Rev-164: Tip SONDA (indeksler kaymasın)
    DOSEME_KALINLIK_KOL = 5

    def _doseme_spin(self, maks: float, ondalik: int, sonek: str, ipucu: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, maks)
        spin.setDecimals(ondalik)
        spin.setSuffix(sonek)
        spin.setToolTip(ipucu)
        spin.setStyleSheet(self._RADYE_SPIN_STIL)
        spin.setMinimumWidth(160)
        return spin

    def _doseme_sekmesi_olustur(self) -> QWidget:
        """Döşeme sekmesini kurar (Rev-144 Aşama 1).

        Neyi çözüyoruz? Kirişli dolu plak döşemenin beton (net alan × h) ve
        kalıp (alt kalıp = net alan + kenar kalıbı = (serbest kenar + boşluk
        çevresi) × h) metrajı. Alan kiriş İÇ YÜZLERİ arasında girilir.
        Aşama 1: elle giriş; AutoCAD köşe tıklama Aşama 2, boşluk Aşama 3.
        Nasıl test ederiz? scratchpad/test_doseme_hesap.py (programsız),
        scratchpad/test_doseme_ui.py (headless form + tablo).
        """
        tab = QWidget()
        dis = QVBoxLayout(tab)
        dis.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        icerik = QWidget()
        lay = QVBoxLayout(icerik)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        bilgi = QLabel(
            "Plak döşeme (kirişli, dolu) metrajı — ALAN KİRİŞ İÇ YÜZLERİ ARASINDA ölçülür, akstan "
            "DEĞİL (kiriş betonu tam yükseklikle sayıldığı için akstan ölçmek kesişimi iki kez sayar). "
            "Alt kalıp = net alan; kenar kalıbı = (serbest kenar + boşluk çevresi) × kalınlık. "
            "Serbest kenar: kirişe oturmayan kenar (konsol ucu, kirişsiz cephe)."
        )
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("color:#d4a017; font-size:9pt;")
        lay.addWidget(bilgi)

        self.doseme_esas_notu_label = QLabel()
        self.doseme_esas_notu_label.setWordWrap(True)
        self.doseme_esas_notu_label.setStyleSheet("color:#5dade2; font-size:9pt;")
        lay.addWidget(self.doseme_esas_notu_label)

        grup_stil = (
            "QGroupBox { color:#a569bd; font-weight:bold; border:1px solid #555;"
            " border-radius:4px; margin-top:10px; padding-top:8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left:8px; padding:0 4px; }"
            "QLabel { color:white; font-weight:normal; }"
        )
        edit_stil = "QLineEdit { background:#2a2a3a; color:white; border:1px solid #666; padding:4px; }"

        ayar_grup = QGroupBox("Ayarlar")
        ayar_grup.setStyleSheet(grup_stil)
        ag = QGridLayout(ayar_grup)
        self.doseme_kat_edit = QLineEdit(self.aktif_kat_adi or "")
        self.doseme_kat_edit.setReadOnly(True)
        self.doseme_kat_edit.setPlaceholderText("Kat seçilmedi")
        self.doseme_kat_edit.setToolTip(
            "Aktif kat — Demir Metrajı sekmesindeki kat listesinden seçilir. Döşemeler bu kata "
            "kaydedilir; tablo sadece bu katın döşemelerini gösterir.")
        self.doseme_kat_edit.setStyleSheet(edit_stil)
        self.doseme_kat_edit.setMinimumWidth(160)
        self.doseme_varsayilan_h_spin = self._doseme_spin(
            500.0, 1, " cm", "Varsayılan döşeme kalınlığı (CM). Her yeni satıra bu değer gelir; "
            "tabloda satır bazında değiştirilebilir.")
        self.doseme_varsayilan_h_spin.setValue(15.0)
        ag.addWidget(QLabel("Aktif Kat:"), 0, 0)
        ag.addWidget(self.doseme_kat_edit, 0, 1)
        ag.addWidget(QLabel("Varsayılan Kalınlık:"), 1, 0)
        ag.addWidget(self.doseme_varsayilan_h_spin, 1, 1)
        combo_stil = ("QComboBox { background:#2a2a3a; color:white; border:1px solid #666;"
                      " padding:4px; } QComboBox QAbstractItemView { background:#2a2a3a;"
                      " color:white; }")
        self.doseme_birim_combo = QComboBox()
        self.doseme_birim_combo.addItems(["Otomatik", "cm", "mm", "m"])
        self.doseme_birim_combo.setToolTip(
            "Çizim birimi. Otomatik = AutoCAD INSUNITS, tanımsızsa cm. İlk döşemede alan ayrıca teyit edilir.")
        self.doseme_birim_combo.setStyleSheet(combo_stil)
        self.doseme_olcek_combo = QComboBox()
        self.doseme_olcek_combo.addItems(list(self._PERDE_OLCEKLER))
        self.doseme_olcek_combo.setToolTip("Çizim ölçeği — çoğu çizim 1:1. İlk döşemede AREA ile karşılaştırın.")
        self.doseme_olcek_combo.setStyleSheet(combo_stil)
        for combo in (self.doseme_birim_combo, self.doseme_olcek_combo):
            combo.currentTextChanged.connect(self._doseme_teyit_sifirla)
        ag.addWidget(QLabel("Çizim Birimi:"), 2, 0)
        ag.addWidget(self.doseme_birim_combo, 2, 1)
        ag.addWidget(QLabel("Çizim Ölçeği:"), 3, 0)
        ag.addWidget(self.doseme_olcek_combo, 3, 1)
        btn_acad = QPushButton(" AutoCAD'de Döşeme Seç (köşe tıklama)")
        btn_acad.setToolTip(
            "AutoCAD'e geçer: her döşeme için köşeleri KİRİŞ İÇ YÜZLERİNDEN sırayla tıklayın "
            "(nokta sınırı yok), ENTER ile kapatın. Bitirmek için 1. köşede ENTER.")
        btn_acad.setStyleSheet(
            "background:#8e44ad; color:white; font-weight:bold; padding:6px 14px;"
            " border:none; border-radius:3px;"
        )
        btn_acad.clicked.connect(self._doseme_sec)
        ag.addWidget(btn_acad, 4, 0, 1, 2)
        # Rev-164: SAÇAK modu — kalınlık varsayılanı katın döşeme kalınlığından
        self.sacak_kalinlik_spin = self._doseme_spin(
            500.0, 1, " cm", "Saçak plağı kalınlığı (CM, sabit). Varsayılan: bu katın döşeme kalınlığı "
            "(Döşeme tablosundaki hakim kalınlık, yoksa varsayılan kalınlık). Elle değiştirirseniz korunur.")
        self._sacak_kalinlik_elle = False
        self.sacak_kalinlik_spin.valueChanged.connect(self._sacak_kalinlik_elle_degisti)
        ag.addWidget(QLabel("Saçak Kalınlığı:"), 5, 0)
        ag.addWidget(self.sacak_kalinlik_spin, 5, 1)
        btn_sacak = QPushButton(" AutoCAD'de Saçak Seç ([H]alka / [Ş]erit)")
        btn_sacak.setToolTip(
            "Saçak = kenar kirişin DIŞ yüzünden taşan konsol plak. Halka: önce saçak ucu dış köşeleri, sonra "
            "kiriş dış yüzü köşeleri (alan = dış − iç, kalıp kenarı = dış çevre). Şerit: kiriş hattı + ENTER, "
            "uç hattı + ENTER (kalıp kenarı = çevre − kiriş hattı). Beton = alan × kalınlık, alt kalıp = alan.")
        btn_sacak.setStyleSheet(
            "background:#b9770e; color:white; font-weight:bold; padding:6px 14px;"
            " border:none; border-radius:3px;"
        )
        btn_sacak.clicked.connect(self._sacak_sec)
        ag.addWidget(btn_sacak, 6, 0, 1, 2)
        ag.setColumnStretch(2, 1)
        lay.addWidget(ayar_grup)
        self._doseme_alan_teyitli = False

        ekle_grup = QGroupBox("Döşeme Ekle (elle)")
        ekle_grup.setStyleSheet(grup_stil)
        eg = QGridLayout(ekle_grup)
        self.doseme_ad_edit = QLineEdit()
        self.doseme_ad_edit.setPlaceholderText("boş bırakılırsa D1, D2…")
        self.doseme_ad_edit.setStyleSheet(edit_stil)
        self.doseme_brut_spin = self._doseme_spin(
            100000.0, 2, " m²", "Brüt alan — kiriş İÇ YÜZLERİ arasında (AutoCAD AREA ile).")
        self.doseme_bosluk_spin = self._doseme_spin(
            100000.0, 2, " m²", "Boşluk alanı (merdiven, şaft, asansör) — yoksa 0.")
        self.doseme_bosluk_cevre_spin = self._doseme_spin(
            100000.0, 2, " m", "Boşlukların toplam çevresi — kenar kalıbına eklenir. Yoksa 0.")
        self.doseme_serbest_spin = self._doseme_spin(
            100000.0, 2, " m", "Kirişe oturmayan kenar uzunluğu (konsol ucu, kirişsiz cephe). Yoksa 0.")
        self.doseme_h_spin = self._doseme_spin(500.0, 1, " cm", "Bu döşemenin kalınlığı (CM).")
        self.doseme_h_spin.setValue(self.doseme_varsayilan_h_spin.value())
        self.doseme_varsayilan_h_spin.valueChanged.connect(self.doseme_h_spin.setValue)
        self.doseme_varsayilan_h_spin.valueChanged.connect(self._perde_doseme_otomatik_yenile)
        alanlar = [("Döşeme Adı:", self.doseme_ad_edit), ("Brüt Alan:", self.doseme_brut_spin),
                   ("Boşluk Alanı:", self.doseme_bosluk_spin),
                   ("Boşluk Çevresi:", self.doseme_bosluk_cevre_spin),
                   ("Serbest Kenar:", self.doseme_serbest_spin), ("Kalınlık:", self.doseme_h_spin)]
        for i, (etiket, w) in enumerate(alanlar):
            eg.addWidget(QLabel(etiket), i, 0)
            eg.addWidget(w, i, 1)
        btn_ekle = QPushButton(" + Tabloya Ekle")
        btn_ekle.setStyleSheet(
            "background:#8e44ad; color:white; font-weight:bold; padding:6px 14px;"
            " border:none; border-radius:3px;"
        )
        btn_ekle.clicked.connect(self._doseme_elle_ekle)
        eg.addWidget(btn_ekle, len(alanlar), 1)
        eg.setColumnStretch(2, 1)
        lay.addWidget(ekle_grup)

        self.doseme_uyari_label = QLabel()
        self.doseme_uyari_label.setWordWrap(True)
        self.doseme_uyari_label.setStyleSheet("color:#e67e22; font-weight:bold;")
        lay.addWidget(self.doseme_uyari_label)

        self.doseme_table = QTableWidget()
        self.doseme_table.setColumnCount(len(self.DOSEME_KOLONLAR))
        self.doseme_table.setHorizontalHeaderLabels(self.DOSEME_KOLONLAR)
        self.doseme_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.doseme_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.doseme_table.setMinimumHeight(240)
        self.doseme_table.setToolTip("Kalınlık (cm) hücresine çift tıklayıp satır bazında değiştirebilirsiniz.")
        self.doseme_table.setStyleSheet(
            "QTableWidget { background:#1e1e2e; color:#e0e0e0; gridline-color:#444;"
            " border:1px solid #555; }"
            "QHeaderView::section { background:#2d2d3d; color:#a569bd; font-weight:bold;"
            " padding:5px; border:1px solid #444; }"
            "QTableWidget::item:selected { background:#3a3a5a; }"
        )
        self.doseme_table.itemChanged.connect(self._doseme_hucre_degisti)
        lay.addWidget(self.doseme_table)

        alt = QHBoxLayout()
        btn_sil = QPushButton("Seçili Sil")
        btn_sil.setStyleSheet("background:#c0392b; color:white; font-weight:bold; padding:5px 12px;"
                              " border:none; border-radius:3px;")
        btn_sil.clicked.connect(self._doseme_sil)
        alt.addWidget(btn_sil)
        btn_temizle = QPushButton("Temizle")
        btn_temizle.setStyleSheet("background:#7f8c8d; color:white; font-weight:bold; padding:5px 12px;"
                                  " border:none; border-radius:3px;")
        btn_temizle.clicked.connect(self._doseme_temizle)
        alt.addWidget(btn_temizle)
        btn_bosluk = QPushButton("Boşluk Ekle (AutoCAD)")
        btn_bosluk.setToolTip(
            "Tabloda AutoCAD'den tıklanmış bir döşeme seçin: AutoCAD'e geçer, o döşemenin içine "
            "merdiven/şaft/asansör boşluğunu köşe köşe tıklatır (birden fazla eklenebilir). "
            "Boşluk alanı net alandan düşülür, çevresi kenar kalıbına eklenir.")
        btn_bosluk.setStyleSheet("background:#a93226; color:white; font-weight:bold; padding:5px 12px;"
                                 " border:none; border-radius:3px;")
        btn_bosluk.clicked.connect(self._doseme_bosluk_ekle)
        alt.addWidget(btn_bosluk)
        alt.addStretch()
        lay.addLayout(alt)

        self.doseme_toplam_label = QLabel()
        self.doseme_toplam_label.setStyleSheet(
            "color:#2ecc71; font-weight:bold; font-size:10pt; background:#2a2a3a;"
            " border:1px solid #a569bd; border-radius:4px; padding:6px;"
        )
        lay.addWidget(self.doseme_toplam_label)
        lay.addStretch()

        self._doseme_tablo_yenile()
        self._doseme_esas_notu_guncelle()
        scroll.setWidget(icerik)
        dis.addWidget(scroll)
        return tab

    # ── Döşeme AutoCAD köşe tıklama (Aşama 2) ──
    def _cizim_birimi_coz(self, combo) -> str:
        """Birim combosu: mm/cm/m aynen; 'Otomatik' -> INSUNITS, tanımsızsa cm."""
        secim = combo.currentText()
        if secim in ("mm", "cm", "m"):
            return secim
        birim = None
        try:
            birim = self.acad_connector.cizim_birimi_oku()
        except Exception as e:
            logger.error(f"INSUNITS okunamadı: {e}", exc_info=True)
        return birim or "cm"

    def _doseme_teyit_sifirla(self, *_):
        self._doseme_alan_teyitli = False

    def _doseme_sec(self):
        """Köşe tıklama döngüsünü açar; TAMAMLANDI'da çalışma kopyası tabloya geçer."""
        if not self.acad_connector or not getattr(self.acad_connector, "bagli", False):
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return
        h_cm = self.doseme_varsayilan_h_spin.value()
        if h_cm <= 0:
            QMessageBox.warning(self, "Kalınlık", "Önce varsayılan kalınlığı (cm) girin.")
            return
        olcek_adi = self.doseme_olcek_combo.currentText()
        panel = DosemeDonguPaneli(
            self.acad_connector, self._cizim_birimi_coz(self.doseme_birim_combo), olcek_adi,
            self._PERDE_OLCEKLER[olcek_adi], h_cm, self._doseme_alan_teyitli, self.doseme_kayitlari, self,
        )
        QTimer.singleShot(0, panel._dongu)
        sonuc = panel.exec()
        self._doseme_alan_teyitli = panel.alan_teyitli
        if sonuc != QDialog.DialogCode.Accepted:
            return
        self.doseme_kayitlari = panel.sonuclar()
        self._doseme_tablo_yenile()

    # ── Rev-164: Saçak ──
    def _sacak_kalinlik_elle_degisti(self, *_):
        if not getattr(self, "_sacak_kalinlik_programatik", False):
            self._sacak_kalinlik_elle = True

    def _sacak_kalinlik_varsayilan_guncelle(self):
        """Kullanıcı elle değiştirmediyse saçak kalınlığı = katın döşeme kalınlığı (hakim)."""
        spin = getattr(self, "sacak_kalinlik_spin", None)
        if spin is None or self._sacak_kalinlik_elle:
            return
        t = hakim_doseme_kalinligi_cm(self.doseme_kayitlari) if hakim_doseme_kalinligi_cm else None
        self._sacak_kalinlik_programatik = True
        try:
            spin.setValue(t if t is not None else self.doseme_varsayilan_h_spin.value())
        finally:
            self._sacak_kalinlik_programatik = False

    def _sacak_sec(self):
        """Saçak modunda DosemeDonguPaneli — satırlar döşeme listesine "tip": "Saçak" ile eklenir;
        mükerrer / geri al / iptal döşemedeki gibi."""
        if not self.acad_connector or not getattr(self.acad_connector, "bagli", False):
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return
        t = self.sacak_kalinlik_spin.value()
        if t <= 0:
            QMessageBox.warning(self, "Kalınlık", "Önce saçak kalınlığını (cm) girin.")
            return
        olcek_adi = self.doseme_olcek_combo.currentText()
        panel = DosemeDonguPaneli(
            self.acad_connector, self._cizim_birimi_coz(self.doseme_birim_combo), olcek_adi,
            self._PERDE_OLCEKLER[olcek_adi], t, self._doseme_alan_teyitli, self.doseme_kayitlari, self,
            mod="sacak", sacak_kalinlik_cm=t,
        )
        QTimer.singleShot(0, panel._dongu)
        sonuc = panel.exec()
        self._doseme_alan_teyitli = panel.alan_teyitli
        if sonuc != QDialog.DialogCode.Accepted:
            return
        self.doseme_kayitlari = panel.sonuclar()
        self._doseme_tablo_yenile()

    def _doseme_bosluk_ekle(self):
        """Seçili (AutoCAD'den tıklanmış) döşemeye sonradan boşluk ekler (Rev-159).
        Aynı DosemeDonguPaneli hedef modunda açılır — kontroller, kırmızı çizim,
        geri al / iptal AutoCAD'deki B yoluyla birebir aynı."""
        if not self.acad_connector or not getattr(self.acad_connector, "bagli", False):
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return
        satirlar = sorted({i.row() for i in self.doseme_table.selectedIndexes()})
        row = satirlar[0] if satirlar else self.doseme_table.currentRow()
        kayitlar = self.doseme_kayitlari
        if not (0 <= row < len(kayitlar)):
            QMessageBox.warning(self, "Boşluk Ekle", "Önce tabloda boşluk eklenecek döşemeyi seçin.")
            return
        if sacak_mi(kayitlar[row]):
            QMessageBox.warning(self, "Boşluk Ekle", f"{kayitlar[row]['ad']} bir saçak — saçağa boşluk eklenmez.")
            return
        if not kayitlar[row].get("koseler"):
            QMessageBox.warning(
                self, "Boşluk Ekle",
                f"{kayitlar[row]['ad']} elle girilmiş — çizimde poligonu yok, boşluğun içinde olup olmadığı "
                "denetlenemez.\n\nElle satırda boşluğu 'Döşeme Ekle (elle)' formundaki 'Boşluk Alanı' ve "
                "'Boşluk Çevresi' alanlarıyla girin ya da döşemeyi AutoCAD'den tıklayın.")
            return
        olcek_adi = self.doseme_olcek_combo.currentText()
        panel = DosemeDonguPaneli(
            self.acad_connector, self._cizim_birimi_coz(self.doseme_birim_combo), olcek_adi,
            self._PERDE_OLCEKLER[olcek_adi], self.doseme_varsayilan_h_spin.value(), True, kayitlar, self,
            hedef_idx=row,
        )
        QTimer.singleShot(0, panel._dongu)
        if panel.exec() != QDialog.DialogCode.Accepted:
            return
        self.doseme_kayitlari = panel.sonuclar()
        self._doseme_tablo_yenile()

    def _doseme_poligon_sil(self, s: Dict):
        """Satırın AutoCAD poligonunu siler (bağlı değilse sessizce geçer)."""
        handleler = ([s.get("handle"), s.get("ic_handle")]
                     + [b.get("handle") for b in s.get("bosluklar") or []])
        if any(handleler) and self.acad_connector and getattr(self.acad_connector, "bagli", False):
            try:
                for h in handleler:
                    if h:
                        self.acad_connector.obje_sil(h)
            except Exception as e:
                logger.error(f"[DOSEME] poligon silinemedi: {e}", exc_info=True)

    def _doseme_esas_notu_guncelle(self):
        """Perdede "Net" beton esası seçilmiş kat varsa kesişim betonu notu."""
        if not hasattr(self, "doseme_esas_notu_label"):
            return
        net_katlar = [k for k, a in getattr(self, "kat_yukseklik_ayarlari", {}).items()
                      if getattr(a, "beton_esasi", "") == "net"]
        self.doseme_esas_notu_label.setText(
            f"ℹ Perde betonu şu katlarda NET yükseklikle hesaplandı: {', '.join(net_katlar)} — "
            "döşeme kalınlığındaki perde kesişim betonu hiçbir araçta sayılmıyor olabilir."
            if net_katlar else "")

    def _doseme_yeni_ad(self) -> str:
        adlar = {s["ad"] for s in self.doseme_kayitlari}
        n = 1
        while f"D{n}" in adlar:
            n += 1
        return f"D{n}"

    def _doseme_elle_ekle(self):
        """Formdaki değerlerle döşeme satırı ekler; geçersizse reddeder."""
        h = doseme_hesapla(self.doseme_brut_spin.value(), self.doseme_h_spin.value(),
                           self.doseme_bosluk_spin.value(), self.doseme_bosluk_cevre_spin.value(),
                           self.doseme_serbest_spin.value())
        if h["hata"]:
            self.doseme_uyari_label.setText(f"⚠ Eklenmedi: {h['hata']}")
            QMessageBox.warning(self, "Döşeme Eklenmedi", h["hata"])
            return
        ad = self.doseme_ad_edit.text().strip() or self._doseme_yeni_ad()
        self.doseme_kayitlari.append({
            "ad": ad,
            "brut_alan_m2": h["brut_alan_m2"],
            "bosluk_alan_m2": h["bosluk_alan_m2"],
            "bosluk_cevre_m": h["bosluk_cevre_m"],
            "serbest_kenar_m": h["serbest_kenar_m"],
            "kalinlik_cm": h["kalinlik_cm"],
            "kaynak": "Elle",
            "handle": "",
        })
        self.doseme_uyari_label.setText(f"⚠ {ad}: {h['uyari']}" if h["uyari"] else "")
        self.doseme_ad_edit.clear()
        for spin in (self.doseme_brut_spin, self.doseme_bosluk_spin,
                     self.doseme_bosluk_cevre_spin, self.doseme_serbest_spin):
            spin.setValue(0.0)
        self.doseme_h_spin.setValue(self.doseme_varsayilan_h_spin.value())
        self._doseme_tablo_yenile()

    @staticmethod
    def _doseme_satir_hesap(s: Dict) -> Dict:
        return doseme_hesapla(s["brut_alan_m2"], s["kalinlik_cm"], s["bosluk_alan_m2"],
                              s["bosluk_cevre_m"], s["serbest_kenar_m"])

    def _doseme_tablo_yenile(self):
        tablo = self.doseme_table
        tablo.blockSignals(True)
        net = beton = kalip = 0.0
        sc = {"adet": 0, "alan": 0.0, "beton": 0.0, "kalip": 0.0}
        try:
            tablo.setRowCount(0)
            for i, s in enumerate(self.doseme_kayitlari):
                h = self._doseme_satir_hesap(s)
                sacak = sacak_mi(s)
                if sacak:
                    sc["adet"] += 1
                    sc["alan"] += h["net_alan_m2"]
                    sc["beton"] += h["beton_m3"]
                    sc["kalip"] += h["toplam_kalip_m2"]
                else:
                    net += h["net_alan_m2"]
                    beton += h["beton_m3"]
                    kalip += h["toplam_kalip_m2"]
                tablo.insertRow(i)
                tip = f"Saçak ({s.get('sacak_tipi', '')})" if sacak else "Döşeme"
                degerler = [str(i + 1), s["ad"], f"{h['brut_alan_m2']:.2f}", f"{h['bosluk_alan_m2']:.2f}",
                            f"{h['net_alan_m2']:.2f}", f"{s['kalinlik_cm']:g}", f"{tek_hane(h['beton_m3'])}",
                            f"{tek_hane(h['alt_kalip_m2'])}", f"{tek_hane(h['kenar_kalip_m2'])}",
                            f"{tek_hane(h['toplam_kalip_m2'])}", s["kaynak"], s.get("handle", ""), tip]
                ipucu = ((f"Saçak ({s.get('sacak_tipi', '')}): kalıba giren kenar {s['serbest_kenar_m']:g} m "
                          f"(kiriş tarafı {s.get('kiris_m', 0):g} m hariç)") if sacak else
                         f"Boşluk çevresi {s['bosluk_cevre_m']:g} m, serbest kenar {s['serbest_kenar_m']:g} m") \
                    + (f"\n⚠ {h['uyari']}" if h["uyari"] else "")
                for col, deger in enumerate(degerler):
                    item = QTableWidgetItem(deger)
                    if col != self.DOSEME_KALINLIK_KOL:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setToolTip(ipucu)
                    if sacak:
                        item.setBackground(QColor("#3d3214"))
                    if h["uyari"]:
                        item.setForeground(QColor("#f5b041"))
                    tablo.setItem(i, col, item)
        finally:
            tablo.blockSignals(False)
        self.doseme_toplam_label.setText(
            f"{self.aktif_kat_adi or 'Kat seçilmedi'} — DÖŞEME: {len(self.doseme_kayitlari) - sc['adet']} adet | "
            f"Net Alan: {net:,.2f} m² | Beton: {tek_hane(beton, True)} m³ | Toplam Kalıp: {tek_hane(kalip, True)} m²"
            + (f"\nSAÇAK: {sc['adet']} adet | Alan: {sc['alan']:,.2f} m² | Beton: {tek_hane(sc['beton'], True)} m³ | "
               f"Toplam Kalıp: {tek_hane(sc['kalip'], True)} m²" if sc["adet"] else ""))
        self._sacak_kalinlik_varsayilan_guncelle()
        # Rev-163: perde kalıbındaki otomatik döşeme kalınlığı bu katın döşemelerinden gelir
        self._perde_doseme_otomatik_yenile()

    def _doseme_hucre_degisti(self, item):
        """Satır bazında kalınlık düzeltme — geçersizse eski değere döner."""
        if item.column() != self.DOSEME_KALINLIK_KOL:
            return
        row = item.row()
        if not (0 <= row < len(self.doseme_kayitlari)):
            return
        s = self.doseme_kayitlari[row]
        try:
            yeni = float(item.text().replace(",", ".").replace("cm", "").strip())
        except ValueError:
            yeni = None
        h = doseme_hesapla(s["brut_alan_m2"], yeni, s["bosluk_alan_m2"],
                           s["bosluk_cevre_m"], s["serbest_kenar_m"]) if yeni is not None else None
        if h is None or h["hata"]:
            self.doseme_uyari_label.setText(
                f"⚠ {s['ad']}: geçersiz kalınlık '{item.text()}' — eski değer ({s['kalinlik_cm']:g} cm) korundu.")
        else:
            s["kalinlik_cm"] = yeni
            self.doseme_uyari_label.setText(f"⚠ {s['ad']}: {h['uyari']}" if h["uyari"] else "")
        self._doseme_tablo_yenile()

    def _doseme_sil(self):
        satirlar = sorted({i.row() for i in self.doseme_table.selectedIndexes()}, reverse=True)
        if not satirlar:
            QMessageBox.information(self, "Bilgi", "Silmek için tablodan döşeme seçin.")
            return
        for row in satirlar:
            if 0 <= row < len(self.doseme_kayitlari):
                self._doseme_poligon_sil(self.doseme_kayitlari[row])
                del self.doseme_kayitlari[row]
        self._doseme_tablo_yenile()

    def _doseme_temizle(self):
        if not self.doseme_kayitlari:
            return
        cevap = QMessageBox.question(
            self, "Temizle", f"{len(self.doseme_kayitlari)} döşeme silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap == QMessageBox.StandardButton.Yes:
            for s in self.doseme_kayitlari:
                self._doseme_poligon_sil(s)
            self.doseme_kayitlari.clear()
            self._doseme_tablo_yenile()

    # ── Rev-150: Kiriş (normal) Beton + Kalıp (Aşama 1/2 — elle giriş) ──
    KIRIS_KOLONLAR = ["No", "Kiriş Adı", "b (cm)", "h (cm)", "L1 (m)", "L2 (m)", "Tip", "t (cm)",
                      "Beton (m³)", "Kalıp (m²)", "Kaynak", "Handle'lar"]
    KIRIS_TIP_KOL = 6
    KIRIS_T_KOL = 7

    def _kiris_sekmesi_olustur(self) -> QWidget:
        """Kiriş sekmesini kurar (Rev-150 Aşama 1).

        Neyi çözüyoruz? Döşeme altı düz kirişin beton (b×h×L_net, h TAM) ve
        kalıp (alt + yanlar; döşeme tarafında h−t) metrajı. İç kiriş iki
        tarafı döşemeli, kenar kiriş bir tarafı döşemesiz. Aşama 2 = AutoCAD'den
        yazı + kenar çizgileri (temel kirişi toplu modu gibi).
        Nasıl test ederiz? scratchpad/test_kiris_hesap.py (programsız),
        scratchpad/test_kiris_ui.py (headless form + tablo).
        """
        tab = QWidget()
        dis = QVBoxLayout(tab)
        dis.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        icerik = QWidget()
        lay = QVBoxLayout(icerik)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        bilgi = QLabel(
            "Döşeme altı düz kiriş metrajı — h TAM kiriş yüksekliğidir (döşeme DÜŞÜLMEZ; döşeme alanı "
            "kiriş iç yüzlerinden ölçüldüğü için kesişim betonu yalnız kirişte sayılır). L_net kolon/perde "
            "yüzleri arasıdır (düğüm betonu kolonda sayılır). Kalıp: alt yüz + döşeme tarafındaki yan "
            "(h − t) + döşemesiz yan (h). İç kiriş: iki tarafı döşemeli. Kenar kiriş: cephe / boşluk kenarı."
        )
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("color:#d4a017; font-size:9pt;")
        lay.addWidget(bilgi)

        grup_stil = (
            "QGroupBox { color:#16a085; font-weight:bold; border:1px solid #555;"
            " border-radius:4px; margin-top:10px; padding-top:8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left:8px; padding:0 4px; }"
            "QLabel { color:white; font-weight:normal; }"
        )
        edit_stil = "QLineEdit { background:#2a2a3a; color:white; border:1px solid #666; padding:4px; }"
        combo_stil = ("QComboBox { background:#2a2a3a; color:white; border:1px solid #666;"
                      " padding:4px; } QComboBox QAbstractItemView { background:#2a2a3a;"
                      " color:white; }")

        ayar_grup = QGroupBox("Ayarlar")
        ayar_grup.setStyleSheet(grup_stil)
        ag = QGridLayout(ayar_grup)
        self.kiris_kat_edit = QLineEdit(self.aktif_kat_adi or "")
        self.kiris_kat_edit.setReadOnly(True)
        self.kiris_kat_edit.setPlaceholderText("Kat seçilmedi")
        self.kiris_kat_edit.setToolTip(
            "Aktif kat — Demir Metrajı sekmesindeki kat listesinden seçilir. Kirişler bu kata "
            "kaydedilir; tablo sadece bu katın kirişlerini gösterir.")
        self.kiris_kat_edit.setStyleSheet(edit_stil)
        self.kiris_kat_edit.setMinimumWidth(160)
        self.kiris_varsayilan_t_spin = self._doseme_spin(
            100.0, 1, " cm", "Varsayılan döşeme kalınlığı t (CM). Her yeni satıra gelir, tabloda "
            "satır bazında değiştirilebilir. 0 = döşemesiz kiriş (yan yüzler tam h).")
        self.kiris_varsayilan_t_spin.setValue(12.0)
        ag.addWidget(QLabel("Aktif Kat:"), 0, 0)
        ag.addWidget(self.kiris_kat_edit, 0, 1)
        ag.addWidget(QLabel("Varsayılan Döşeme Kalınlığı t:"), 1, 0)
        ag.addWidget(self.kiris_varsayilan_t_spin, 1, 1)
        self.kiris_birim_combo = QComboBox()
        self.kiris_birim_combo.addItems(["Otomatik", "cm", "mm", "m"])
        self.kiris_birim_combo.setToolTip(
            "Çizim birimi. Otomatik = AutoCAD INSUNITS, tanımsızsa cm. İlk kirişte uzunluk ayrıca teyit edilir.")
        self.kiris_birim_combo.setStyleSheet(combo_stil)
        self.kiris_olcek_combo = QComboBox()
        self.kiris_olcek_combo.addItems(list(self._PERDE_OLCEKLER))
        self.kiris_olcek_combo.setToolTip("Çizim ölçeği — çoğu çizim 1:1. İlk kirişte LIST ile karşılaştırın.")
        self.kiris_olcek_combo.setStyleSheet(combo_stil)
        for combo in (self.kiris_birim_combo, self.kiris_olcek_combo):
            combo.currentTextChanged.connect(self._kiris_teyit_sifirla)
        ag.addWidget(QLabel("Çizim Birimi:"), 2, 0)
        ag.addWidget(self.kiris_birim_combo, 2, 1)
        ag.addWidget(QLabel("Çizim Ölçeği:"), 3, 0)
        ag.addWidget(self.kiris_olcek_combo, 3, 1)
        butonlar = QHBoxLayout()
        for metin, tip, renk, ipucu in (
                (" İç Kiriş Seç", KIRIS_TIPLERI[0], "#e67e22", "İki tarafı döşemeli kirişler — turuncuya boyanır."),
                (" Kenar Kiriş Seç", KIRIS_TIPLERI[1], "#2471a3",
                 "Bir tarafında döşeme olmayan kirişler (cephe, boşluk kenarı) — maviye boyanır.")):
            btn = QPushButton(metin)
            btn.setToolTip("AutoCAD'e geçer: her kiriş için etiket yazısı + iki kenar çizgisi + ENTER. "
                           "Bitirmek için boş ENTER. " + ipucu)
            btn.setStyleSheet(f"background:{renk}; color:white; font-weight:bold; padding:6px 14px;"
                              " border:none; border-radius:3px;")
            btn.clicked.connect(lambda _=False, t=tip: self._kiris_sec(t))
            butonlar.addWidget(btn)
        ag.addLayout(butonlar, 4, 0, 1, 2)
        ag.setColumnStretch(2, 1)
        lay.addWidget(ayar_grup)
        self._kiris_teyitli = False

        ekle_grup = QGroupBox("Kiriş Ekle (elle)")
        ekle_grup.setStyleSheet(grup_stil)
        eg = QGridLayout(ekle_grup)
        self.kiris_ad_edit = QLineEdit()
        self.kiris_ad_edit.setPlaceholderText("örn. K101 — boş bırakılırsa K1, K2…")
        self.kiris_ad_edit.setStyleSheet(edit_stil)
        self.kiris_b_spin = self._doseme_spin(500.0, 1, " cm", "Kiriş genişliği b (CM).")
        self.kiris_h_spin = self._doseme_spin(500.0, 1, " cm", "Kiriş TAM yüksekliği h (CM) — döşeme düşülmez.")
        self.kiris_l_spin = self._doseme_spin(
            1000.0, 2, " m", "Net uzunluk L_net (METRE) — kolon/perde yüzleri arası.")
        self.kiris_tip_combo = QComboBox()
        self.kiris_tip_combo.addItems(list(KIRIS_TIPLERI))
        self.kiris_tip_combo.setToolTip(
            "İç: iki tarafı döşemeli. Kenar: bir tarafında döşeme yok (cephe, boşluk kenarı).")
        self.kiris_tip_combo.setStyleSheet(combo_stil)
        self.kiris_t_spin = self._doseme_spin(100.0, 1, " cm", "Bu kirişe bitişik döşeme kalınlığı t (CM).")
        self.kiris_t_spin.setValue(self.kiris_varsayilan_t_spin.value())
        self.kiris_varsayilan_t_spin.valueChanged.connect(self.kiris_t_spin.setValue)
        alanlar = [("Kiriş Adı:", self.kiris_ad_edit), ("Genişlik b:", self.kiris_b_spin),
                   ("Yükseklik h:", self.kiris_h_spin), ("Net Uzunluk L_net:", self.kiris_l_spin),
                   ("Tip:", self.kiris_tip_combo), ("Döşeme Kalınlığı t:", self.kiris_t_spin)]
        for i, (etiket, w) in enumerate(alanlar):
            eg.addWidget(QLabel(etiket), i, 0)
            eg.addWidget(w, i, 1)
        btn_ekle = QPushButton(" + Tabloya Ekle")
        btn_ekle.setStyleSheet(
            "background:#16a085; color:white; font-weight:bold; padding:6px 14px;"
            " border:none; border-radius:3px;"
        )
        btn_ekle.clicked.connect(self._kiris_elle_ekle)
        eg.addWidget(btn_ekle, len(alanlar), 1)
        eg.setColumnStretch(2, 1)
        lay.addWidget(ekle_grup)

        self.kiris_uyari_label = QLabel()
        self.kiris_uyari_label.setWordWrap(True)
        self.kiris_uyari_label.setStyleSheet("color:#e67e22; font-weight:bold;")
        lay.addWidget(self.kiris_uyari_label)

        self.kiris_table = QTableWidget()
        self.kiris_table.setColumnCount(len(self.KIRIS_KOLONLAR))
        self.kiris_table.setHorizontalHeaderLabels(self.KIRIS_KOLONLAR)
        self.kiris_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.kiris_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.kiris_table.setMinimumHeight(240)
        self.kiris_table.setToolTip(
            "Tip (İç / Kenar) ve t (cm) hücrelerine çift tıklayıp satır bazında değiştirebilirsiniz.")
        self.kiris_table.setStyleSheet(
            "QTableWidget { background:#1e1e2e; color:#e0e0e0; gridline-color:#444;"
            " border:1px solid #555; }"
            "QHeaderView::section { background:#2d2d3d; color:#16a085; font-weight:bold;"
            " padding:5px; border:1px solid #444; }"
            "QTableWidget::item:selected { background:#3a3a5a; }"
        )
        self.kiris_table.itemChanged.connect(self._kiris_hucre_degisti)
        lay.addWidget(self.kiris_table)

        alt = QHBoxLayout()
        btn_sil = QPushButton("Seçili Sil")
        btn_sil.setStyleSheet("background:#c0392b; color:white; font-weight:bold; padding:5px 12px;"
                              " border:none; border-radius:3px;")
        btn_sil.clicked.connect(self._kiris_sil)
        alt.addWidget(btn_sil)
        btn_temizle = QPushButton("Temizle")
        btn_temizle.setStyleSheet("background:#7f8c8d; color:white; font-weight:bold; padding:5px 12px;"
                                  " border:none; border-radius:3px;")
        btn_temizle.clicked.connect(self._kiris_temizle)
        alt.addWidget(btn_temizle)
        alt.addStretch()
        lay.addLayout(alt)

        self.kiris_toplam_label = QLabel()
        self.kiris_toplam_label.setStyleSheet(
            "color:#2ecc71; font-weight:bold; font-size:10pt; background:#2a2a3a;"
            " border:1px solid #16a085; border-radius:4px; padding:6px;"
        )
        lay.addWidget(self.kiris_toplam_label)
        lay.addStretch()

        self._kiris_tablo_yenile()
        scroll.setWidget(icerik)
        dis.addWidget(scroll)
        return tab

    def _kiris_teyit_sifirla(self, *_):
        self._kiris_teyitli = False

    def _kiris_sec(self, mod: str):
        """Mod bazlı AutoCAD döngüsünü açar; TAMAMLANDI'da çalışma kopyası tabloya geçer."""
        if not self.acad_connector or not getattr(self.acad_connector, "bagli", False):
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return
        olcek_adi = self.kiris_olcek_combo.currentText()
        panel = KirisDonguPaneli(
            self.acad_connector, self._cizim_birimi_coz(self.kiris_birim_combo), olcek_adi,
            self._PERDE_OLCEKLER[olcek_adi], self.kiris_varsayilan_t_spin.value(), mod,
            self._kiris_teyitli, self.kiris_kayitlari, self,
        )
        QTimer.singleShot(0, panel._dongu)
        sonuc = panel.exec()
        self._kiris_teyitli = panel.teyitli
        if sonuc != QDialog.DialogCode.Accepted:
            return
        self.kiris_kayitlari = panel.sonuclar()
        self._kiris_tablo_yenile()

    def _kiris_renk_islemi(self, s: Dict, geri_al: bool = False):
        """Satırın çizim nesnelerini tipine göre boyar veya eski rengine döndürür
        (bağlı değilse / elle satırsa sessizce geçer)."""
        handleler = s.get("handleler") or []
        if not handleler or not self.acad_connector or not getattr(self.acad_connector, "bagli", False):
            return
        for hnd in handleler:
            try:
                if geri_al:
                    self.acad_connector.obje_isaret_geri_al(hnd)
                else:
                    self.acad_connector.obje_renklendir_hizli(hnd, KIRIS_RENKLERI[s["tip"]])
            except Exception as e:
                logger.error(f"[KIRIS] renk işlemi hata ({hnd}): {e}", exc_info=True)

    def _kiris_yeni_ad(self) -> str:
        adlar = {s["ad"] for s in self.kiris_kayitlari}
        n = 1
        while f"K{n}" in adlar:
            n += 1
        return f"K{n}"

    @staticmethod
    def _kiris_satir_hesap(s: Dict) -> Dict:
        # Rev-158: d1/d2 = bölünmüş kenarın dolu uzunluğu (yan kalıp); elle/eski kayıtta yok -> kapsam
        return kiris_hesapla(s["b_cm"], s["h_cm"], s["l1_m"], s["tip"], s["t_cm"], s["l2_m"],
                             s.get("d1_m"), s.get("d2_m"))

    @staticmethod
    def _kiris_not_metni(ad: str, h: Dict) -> str:
        notlar = [n for n in (h["uyari"], h["bilgi"]) if n]
        return f"⚠ {ad}: " + " | ".join(notlar) if notlar else ""

    def _kiris_elle_ekle(self):
        """Formdaki değerlerle kiriş satırı ekler; geçersizse reddeder."""
        tip = self.kiris_tip_combo.currentText()
        h = kiris_hesapla(self.kiris_b_spin.value(), self.kiris_h_spin.value(),
                          self.kiris_l_spin.value(), tip, self.kiris_t_spin.value())
        if h["hata"]:
            self.kiris_uyari_label.setText(f"⚠ Eklenmedi: {h['hata']}")
            QMessageBox.warning(self, "Kiriş Eklenmedi", h["hata"])
            return
        ad = self.kiris_ad_edit.text().strip() or self._kiris_yeni_ad()
        self.kiris_kayitlari.append({
            "ad": ad, "b_cm": h["b_cm"], "h_cm": h["h_cm"], "l1_m": h["l1_m"], "l2_m": h["l2_m"],
            "tip": tip, "t_cm": h["t_cm"], "kaynak": "Elle", "handleler": [],
        })
        self.kiris_uyari_label.setText(self._kiris_not_metni(ad, h))
        self.kiris_ad_edit.clear()
        self.kiris_l_spin.setValue(0.0)
        self.kiris_t_spin.setValue(self.kiris_varsayilan_t_spin.value())
        self._kiris_tablo_yenile()

    def _kiris_tablo_yenile(self):
        tablo = self.kiris_table
        tablo.blockSignals(True)
        l_top = beton = kalip = 0.0
        try:
            tablo.setRowCount(0)
            for i, s in enumerate(self.kiris_kayitlari):
                h = self._kiris_satir_hesap(s)
                l_top += h["l_net_m"]
                beton += h["beton_m3"]
                kalip += h["toplam_kalip_m2"]
                tablo.insertRow(i)
                degerler = [str(i + 1), s["ad"], f"{s['b_cm']:g}", f"{s['h_cm']:g}",
                            f"{h['l1_m']:.2f}", f"{h['l2_m']:.2f}", s["tip"], f"{s['t_cm']:g}",
                            f"{tek_hane(h['beton_m3'])}", f"{tek_hane(h['toplam_kalip_m2'])}", s["kaynak"],
                            ", ".join(s.get("handleler") or [])]
                notlar = self._kiris_not_metni(s["ad"], h)
                ipucu = (f"Alt kalıp {tek_hane(h['alt_kalip_m2'])} m² + yan kalıp {tek_hane(h['yan_kalip_m2'])} m²"
                         + (f"\n{notlar}" if notlar else ""))
                for col, deger in enumerate(degerler):
                    item = QTableWidgetItem(deger)
                    if col not in (self.KIRIS_TIP_KOL, self.KIRIS_T_KOL):
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setToolTip(ipucu)
                    if h["uyari"] or h["bilgi"]:
                        item.setForeground(QColor("#f5b041"))
                    tablo.setItem(i, col, item)
        finally:
            tablo.blockSignals(False)
        self.kiris_toplam_label.setText(
            f"{self.aktif_kat_adi or 'Kat seçilmedi'} — TOPLAM: {len(self.kiris_kayitlari)} kiriş | "
            f"L_ort: {l_top:,.2f} m | "
            f"Beton: {tek_hane(beton, True)} m³ | Kalıp: {tek_hane(kalip, True)} m²")

    def _kiris_hucre_degisti(self, item):
        """Satır bazında Tip / t düzeltme — geçersizse eski değer korunur."""
        col, row = item.column(), item.row()
        if col not in (self.KIRIS_TIP_KOL, self.KIRIS_T_KOL) or not (0 <= row < len(self.kiris_kayitlari)):
            return
        s = self.kiris_kayitlari[row]
        yeni = dict(s)
        metin = item.text().strip()
        if col == self.KIRIS_TIP_KOL:
            ilk = metin[:1].lower()
            yeni["tip"] = (KIRIS_TIPLERI[0] if ilk in ("i", "ı", "İ".lower())
                           else KIRIS_TIPLERI[1] if ilk == "k" else metin)
        else:
            try:
                yeni["t_cm"] = float(metin.replace(",", ".").replace("cm", "").strip())
            except ValueError:
                yeni["t_cm"] = None
        h = self._kiris_satir_hesap(yeni) if yeni["t_cm"] is not None else {"hata": "sayı değil"}
        if h["hata"]:
            self.kiris_uyari_label.setText(
                f"⚠ {s['ad']}: geçersiz değer '{metin}' ({h['hata']}) — eski değer korundu.")
        else:
            tip_degisti = yeni["tip"] != s["tip"]
            s.update(tip=yeni["tip"], t_cm=yeni["t_cm"])
            self.kiris_uyari_label.setText(self._kiris_not_metni(s["ad"], h))
            if tip_degisti:
                self._kiris_renk_islemi(s)
        self._kiris_tablo_yenile()

    def _kiris_sil(self):
        satirlar = sorted({i.row() for i in self.kiris_table.selectedIndexes()}, reverse=True)
        if not satirlar:
            QMessageBox.information(self, "Bilgi", "Silmek için tablodan kiriş seçin.")
            return
        for row in satirlar:
            if 0 <= row < len(self.kiris_kayitlari):
                self._kiris_renk_islemi(self.kiris_kayitlari.pop(row), geri_al=True)
        self._kiris_tablo_yenile()

    def _kiris_temizle(self):
        if not self.kiris_kayitlari:
            return
        cevap = QMessageBox.question(
            self, "Temizle", f"{len(self.kiris_kayitlari)} kiriş silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap == QMessageBox.StandardButton.Yes:
            for s in self.kiris_kayitlari:
                self._kiris_renk_islemi(s, geri_al=True)
            self.kiris_kayitlari.clear()
            self._kiris_tablo_yenile()

    # ── Rev-152: Merdiven (plak merdiven kolu + ara sahanlık) Beton + Kalıp ──
    MERDIVEN_KOLONLAR = ["No", "Tip", "Ad", "n", "h (cm)", "a (cm)", "L (m)", "H (m)", "s (m)", "B / En (m)",
                         "Boy (m)", "t (cm)", "Yan Taraf", "Beton (m³)", "Alt Yüz (m²)", "Rıht (m²)",
                         "Yan (m²)", "Kenar (m²)", "Toplam Kalıp (m²)"]
    MERDIVEN_T_KOL = 11
    MERDIVEN_YAN_KOL = 12
    MERDIVEN_AYAR_ANAHTARI = "merdiven_kalip_esasi"

    def _merdiven_sekmesi_olustur(self) -> QWidget:
        """Merdiven sekmesi (Rev-152, tek aşama — elle giriş).

        Neyi çözüyoruz? Plak merdiven kolu ve ARA sahanlığın beton + kalıp
        metrajı; girdiler merdiven detayında yazılı. Kalıp kalemleri ayrı
        sütunlarda; rıht/yan kalıbının toplama katılması idareye göre seçilir.
        Nasıl test ederiz? scratchpad/test_merdiven_hesap.py (programsız, brief M1-M7),
        scratchpad/test_merdiven_ui.py (headless form + tablo + kat özeti).
        """
        tab = QWidget()
        dis = QVBoxLayout(tab)
        dis.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        icerik = QWidget()
        lay = QVBoxLayout(icerik)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        bilgi = QLabel(
            "Plak (eğik plaklı) merdiven: kol + ARA sahanlık. Girdiler merdiven detayından okunur. "
            "Kol profili = eğik plak (s × t, t plağa DİK) + basamak üçgenleri. "
            "Konsol basamaklı / zigzag merdiven ve merdiven demiri bu araçta yok."
        )
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("color:#d4a017; font-size:9pt;")
        lay.addWidget(bilgi)
        not_lbl = QLabel("⚠ Kat sahanlığını DÖŞEME aracında alın; burada yalnızca ARA sahanlık girin.")
        not_lbl.setWordWrap(True)
        not_lbl.setStyleSheet("color:#e74c3c; font-weight:bold; font-size:10pt; padding:4px;"
                              " border:1px solid #e74c3c; border-radius:4px;")
        lay.addWidget(not_lbl)

        grup_stil = (
            "QGroupBox { color:#16a085; font-weight:bold; border:1px solid #555;"
            " border-radius:4px; margin-top:10px; padding-top:8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left:8px; padding:0 4px; }"
            "QLabel { color:white; font-weight:normal; } QCheckBox { color:white; }"
        )
        edit_stil = "QLineEdit { background:#2a2a3a; color:white; border:1px solid #666; padding:4px; }"
        combo_stil = ("QComboBox { background:#2a2a3a; color:white; border:1px solid #666;"
                      " padding:4px; } QComboBox QAbstractItemView { background:#2a2a3a;"
                      " color:white; }")

        # ── Ayarlar ──
        ayar_grup = QGroupBox("Ayarlar")
        ayar_grup.setStyleSheet(grup_stil)
        ag = QGridLayout(ayar_grup)
        self.merdiven_kat_edit = QLineEdit(self.aktif_kat_adi or "")
        self.merdiven_kat_edit.setReadOnly(True)
        self.merdiven_kat_edit.setPlaceholderText("Kat seçilmedi")
        self.merdiven_kat_edit.setToolTip(
            "Aktif kat — Demir Metrajı sekmesindeki kat listesinden seçilir. Merdivenler bu kata kaydedilir.")
        self.merdiven_kat_edit.setStyleSheet(edit_stil)
        self.merdiven_kat_edit.setMinimumWidth(160)
        ag.addWidget(QLabel("Aktif Kat:"), 0, 0)
        ag.addWidget(self.merdiven_kat_edit, 0, 1)
        kayitli = autocad_ayari_oku(self.MERDIVEN_AYAR_ANAHTARI, {}) or {}
        self.merdiven_riht_check = QCheckBox("Rıht kalıbını toplama kat")
        self.merdiven_riht_check.setChecked(bool(kayitli.get("riht", True)))
        self.merdiven_riht_check.setToolTip(
            "Bazı idareler merdiven kalıbında yalnız alt yüzü sayar — işareti kaldırırsanız rıht kalıbı "
            "tabloda görünür ama toplama katılmaz. Seçim kalıcı olarak saklanır.")
        self.merdiven_yan_check = QCheckBox("Yan kalıbı toplama kat")
        self.merdiven_yan_check.setChecked(bool(kayitli.get("yan", True)))
        self.merdiven_yan_check.setToolTip(
            "İşareti kaldırırsanız kolun yan (profil) kalıbı toplama katılmaz. Seçim kalıcı olarak saklanır.")
        for chk in (self.merdiven_riht_check, self.merdiven_yan_check):
            chk.toggled.connect(self._merdiven_kalip_secimi_degisti)
        ag.addWidget(self.merdiven_riht_check, 1, 0, 1, 2)
        ag.addWidget(self.merdiven_yan_check, 2, 0, 1, 2)
        ag.setColumnStretch(2, 1)
        lay.addWidget(ayar_grup)

        # ── Kol ekle ──
        kol_grup = QGroupBox("Merdiven Kolu Ekle")
        kol_grup.setStyleSheet(grup_stil)
        kg = QGridLayout(kol_grup)
        self.merdiven_kol_ad_edit = QLineEdit()
        self.merdiven_kol_ad_edit.setPlaceholderText("örn. Kol-1 — boş bırakılırsa otomatik")
        self.merdiven_kol_ad_edit.setStyleSheet(edit_stil)
        self.merdiven_n_spin = QSpinBox()
        self.merdiven_n_spin.setRange(0, 200)
        self.merdiven_n_spin.setSuffix(" adet")
        self.merdiven_n_spin.setToolTip("Basamak (rıht) sayısı — detaydaki rıht adedi.")
        self.merdiven_n_spin.setStyleSheet(self._RADYE_SPIN_STIL)
        self.merdiven_n_spin.setMinimumWidth(160)
        self.merdiven_h_spin = self._doseme_spin(500.0, 1, " cm", "Rıht yüksekliği h (CM) — olağan 12–22 cm.")
        self.merdiven_a_spin = self._doseme_spin(500.0, 1, " cm", "Basamak genişliği a (CM) — olağan 22–35 cm.")
        self.merdiven_b_spin = self._doseme_spin(20.0, 2, " m", "Kol genişliği B (METRE) — planda kolun eni.")
        self.merdiven_t_spin = self._doseme_spin(
            100.0, 1, " cm", "Plak kalınlığı t (CM) — plağa DİK ölçü (detayda eğik plağın kalınlığı).")
        self.merdiven_t_spin.setValue(15.0)
        self.merdiven_yan_combo = QComboBox()
        self.merdiven_yan_combo.addItems(["2", "1", "0"])
        self.merdiven_yan_combo.setToolTip(
            "Yan kalıp taraf sayısı: iki tarafı boşta 2, bir tarafı perdeye/duvara dayanıyorsa 1, "
            "iki tarafı da dayanıyorsa 0.")
        self.merdiven_yan_combo.setStyleSheet(combo_stil)
        self.merdiven_lh_elle_check = QCheckBox("L ve H'yi elle düzelt")
        self.merdiven_lh_elle_check.setToolTip(
            "Detaydaki yatay izdüşüm / kot farkı n × a, n × h'den farklıysa (örn. son rıht sahanlığa "
            "çıkıyorsa) işaretleyip L ve H'yi detaydan girin.")
        self.merdiven_l_spin = self._doseme_spin(100.0, 2, " m", "Yatay izdüşüm L (METRE) — varsayılan n × a.")
        self.merdiven_hkot_spin = self._doseme_spin(50.0, 2, " m", "Kot farkı H (METRE) — varsayılan n × h.")
        alanlar = [("Kol Adı:", self.merdiven_kol_ad_edit), ("Basamak sayısı n:", self.merdiven_n_spin),
                   ("Rıht h:", self.merdiven_h_spin), ("Basamak a:", self.merdiven_a_spin),
                   ("Kol eni B:", self.merdiven_b_spin), ("Plak kalınlığı t:", self.merdiven_t_spin),
                   ("Yan kalıp taraf sayısı:", self.merdiven_yan_combo),
                   ("", self.merdiven_lh_elle_check),
                   ("Yatay izdüşüm L:", self.merdiven_l_spin), ("Kot farkı H:", self.merdiven_hkot_spin)]
        for i, (etiket, w) in enumerate(alanlar):
            kg.addWidget(QLabel(etiket), i, 0)
            kg.addWidget(w, i, 1)
        self.merdiven_kol_onizleme_label = QLabel()
        self.merdiven_kol_onizleme_label.setWordWrap(True)
        self.merdiven_kol_onizleme_label.setStyleSheet("color:#5dade2; font-weight:bold;")
        kg.addWidget(self.merdiven_kol_onizleme_label, len(alanlar), 0, 1, 3)
        btn_kol = QPushButton(" + Kolu Tabloya Ekle")
        btn_kol.setStyleSheet("background:#16a085; color:white; font-weight:bold; padding:6px 14px;"
                              " border:none; border-radius:3px;")
        btn_kol.clicked.connect(self._merdiven_kol_ekle)
        kg.addWidget(btn_kol, len(alanlar) + 1, 1)
        kg.setColumnStretch(2, 1)
        lay.addWidget(kol_grup)
        for spin in (self.merdiven_n_spin, self.merdiven_h_spin, self.merdiven_a_spin):
            spin.valueChanged.connect(self._merdiven_lh_otomatik)
        for spin in (self.merdiven_b_spin, self.merdiven_t_spin, self.merdiven_l_spin, self.merdiven_hkot_spin):
            spin.valueChanged.connect(self._merdiven_kol_onizle)
        self.merdiven_yan_combo.currentTextChanged.connect(self._merdiven_kol_onizle)
        self.merdiven_lh_elle_check.toggled.connect(self._merdiven_lh_elle_degisti)

        # ── Ara sahanlık ekle ──
        sah_grup = QGroupBox("Ara Sahanlık Ekle")
        sah_grup.setStyleSheet(grup_stil)
        sg = QGridLayout(sah_grup)
        self.merdiven_sah_ad_edit = QLineEdit()
        self.merdiven_sah_ad_edit.setPlaceholderText("örn. Sahanlık-1 — boş bırakılırsa otomatik")
        self.merdiven_sah_ad_edit.setStyleSheet(edit_stil)
        self.merdiven_sah_en_spin = self._doseme_spin(50.0, 2, " m", "Sahanlık eni (METRE).")
        self.merdiven_sah_boy_spin = self._doseme_spin(50.0, 2, " m", "Sahanlık boyu (METRE).")
        self.merdiven_sah_t_spin = self._doseme_spin(100.0, 1, " cm", "Sahanlık plak kalınlığı (CM).")
        self.merdiven_sah_t_spin.setValue(15.0)
        self.merdiven_sah_serbest_spin = self._doseme_spin(
            100.0, 2, " m", "Serbest kenar (METRE) — perdeye/kirişe dayanmayan, kenar kalıbı gereken uzunluk.")
        s_alanlar = [("Sahanlık Adı:", self.merdiven_sah_ad_edit), ("En:", self.merdiven_sah_en_spin),
                     ("Boy:", self.merdiven_sah_boy_spin), ("Kalınlık:", self.merdiven_sah_t_spin),
                     ("Serbest kenar:", self.merdiven_sah_serbest_spin)]
        for i, (etiket, w) in enumerate(s_alanlar):
            sg.addWidget(QLabel(etiket), i, 0)
            sg.addWidget(w, i, 1)
        btn_sah = QPushButton(" + Sahanlığı Tabloya Ekle")
        btn_sah.setStyleSheet("background:#16a085; color:white; font-weight:bold; padding:6px 14px;"
                              " border:none; border-radius:3px;")
        btn_sah.clicked.connect(self._merdiven_sahanlik_ekle)
        sg.addWidget(btn_sah, len(s_alanlar), 1)
        sg.setColumnStretch(2, 1)
        lay.addWidget(sah_grup)

        self.merdiven_uyari_label = QLabel()
        self.merdiven_uyari_label.setWordWrap(True)
        self.merdiven_uyari_label.setStyleSheet("color:#e67e22; font-weight:bold;")
        lay.addWidget(self.merdiven_uyari_label)

        self.merdiven_esas_label = QLabel()
        self.merdiven_esas_label.setStyleSheet("color:#f39c12; font-weight:bold;")
        lay.addWidget(self.merdiven_esas_label)

        self.merdiven_table = QTableWidget()
        self.merdiven_table.setColumnCount(len(self.MERDIVEN_KOLONLAR))
        self.merdiven_table.setHorizontalHeaderLabels(self.MERDIVEN_KOLONLAR)
        self.merdiven_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.merdiven_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.merdiven_table.setMinimumHeight(240)
        self.merdiven_table.setToolTip(
            "t (cm) ve Yan Taraf (kol) hücrelerine çift tıklayıp satır bazında değiştirebilirsiniz.")
        self.merdiven_table.setStyleSheet(
            "QTableWidget { background:#1e1e2e; color:#e0e0e0; gridline-color:#444; border:1px solid #555; }"
            "QHeaderView::section { background:#2d2d3d; color:#16a085; font-weight:bold;"
            " padding:5px; border:1px solid #444; }"
            "QTableWidget::item:selected { background:#3a3a5a; }"
        )
        self.merdiven_table.itemChanged.connect(self._merdiven_hucre_degisti)
        lay.addWidget(self.merdiven_table)

        alt = QHBoxLayout()
        btn_sil = QPushButton("Seçili Sil")
        btn_sil.setStyleSheet("background:#c0392b; color:white; font-weight:bold; padding:5px 12px;"
                              " border:none; border-radius:3px;")
        btn_sil.clicked.connect(self._merdiven_sil)
        alt.addWidget(btn_sil)
        btn_temizle = QPushButton("Temizle")
        btn_temizle.setToolTip("Aktif katın merdiven satırlarını siler (diğer katlara dokunmaz).")
        btn_temizle.setStyleSheet("background:#7f8c8d; color:white; font-weight:bold; padding:5px 12px;"
                                  " border:none; border-radius:3px;")
        btn_temizle.clicked.connect(self._merdiven_temizle)
        alt.addWidget(btn_temizle)
        alt.addStretch()
        lay.addLayout(alt)

        self.merdiven_toplam_label = QLabel()
        self.merdiven_toplam_label.setStyleSheet(
            "color:#2ecc71; font-weight:bold; font-size:10pt; background:#2a2a3a;"
            " border:1px solid #16a085; border-radius:4px; padding:6px;")
        lay.addWidget(self.merdiven_toplam_label)
        lay.addStretch()

        self._merdiven_lh_elle_degisti(False)
        self._merdiven_tablo_yenile()
        scroll.setWidget(icerik)
        dis.addWidget(scroll)
        return tab

    # ── merdiven: form yardımcıları ──
    def _merdiven_kalip_secimi(self):
        """(rıht dahil, yan dahil) — sekme kurulmadıysa kayıtlı ayar."""
        if hasattr(self, "merdiven_riht_check"):
            return self.merdiven_riht_check.isChecked(), self.merdiven_yan_check.isChecked()
        kayitli = autocad_ayari_oku(self.MERDIVEN_AYAR_ANAHTARI, {}) or {}
        return bool(kayitli.get("riht", True)), bool(kayitli.get("yan", True))

    def _merdiven_kalip_secimi_degisti(self, *_):
        riht, yan = self._merdiven_kalip_secimi()
        autocad_ayari_yaz(self.MERDIVEN_AYAR_ANAHTARI, {"riht": riht, "yan": yan})
        self._merdiven_tablo_yenile()

    def _merdiven_lh_elle_degisti(self, elle: bool):
        self.merdiven_l_spin.setEnabled(elle)
        self.merdiven_hkot_spin.setEnabled(elle)
        self._merdiven_lh_otomatik()

    def _merdiven_lh_otomatik(self, *_):
        """Elle modu kapalıyken L = n×a, H = n×h."""
        if not self.merdiven_lh_elle_check.isChecked():
            n = self.merdiven_n_spin.value()
            for spin, deger in ((self.merdiven_l_spin, n * self.merdiven_a_spin.value() / 100.0),
                                (self.merdiven_hkot_spin, n * self.merdiven_h_spin.value() / 100.0)):
                spin.blockSignals(True)
                spin.setValue(deger)
                spin.blockSignals(False)
        self._merdiven_kol_onizle()

    def _merdiven_form_kol_hesap(self) -> Dict:
        elle = self.merdiven_lh_elle_check.isChecked()
        return merdiven_kol_hesapla(
            self.merdiven_n_spin.value(), self.merdiven_h_spin.value(), self.merdiven_a_spin.value(),
            self.merdiven_b_spin.value(), self.merdiven_t_spin.value(), int(self.merdiven_yan_combo.currentText()),
            self.merdiven_l_spin.value() if elle else None, self.merdiven_hkot_spin.value() if elle else None)

    def _merdiven_kol_onizle(self, *_):
        if not hasattr(self, "merdiven_kol_onizleme_label") or merdiven_kol_hesapla is None:
            return
        h = self._merdiven_form_kol_hesap()
        if h["hata"]:
            self.merdiven_kol_onizleme_label.setText("Önizleme: n, h, a, B ve t girin.")
            return
        riht, yan = self._merdiven_kalip_secimi()
        self.merdiven_kol_onizleme_label.setText(
            f"L = {h['L_m']:.2f} m · H = {h['H_m']:.2f} m · s = {h['s_m']:.3f} m · profil = {h['profil_m2']:.3f} m² "
            f"→ Beton {tek_hane(h['beton_m3'])} m³ · Kalıp {tek_hane(merdiven_toplam_kalip(h, riht, yan))} m²"
            + (f"\n⚠ {h['uyari']}" if h["uyari"] else ""))

    def _merdiven_yeni_ad(self, onek: str) -> str:
        adlar = {s["ad"] for s in self.merdiven_kayitlari}
        n = 1
        while f"{onek}-{n}" in adlar:
            n += 1
        return f"{onek}-{n}"

    @staticmethod
    def _merdiven_satir_hesap(s: Dict) -> Dict:
        if s["tip"] == MERDIVEN_TIP_SAHANLIK:
            return merdiven_sahanlik_hesapla(s["en_m"], s["boy_m"], s["t_cm"], s["serbest_m"])
        return merdiven_kol_hesapla(s["n"], s["h_cm"], s["a_cm"], s["b_m"], s["t_cm"], s["yan"],
                                    s.get("l_m"), s.get("h_kot_m"))

    def _merdiven_kol_ekle(self):
        h = self._merdiven_form_kol_hesap()
        if h["hata"]:
            self.merdiven_uyari_label.setText(f"⚠ Eklenmedi: {h['hata']}")
            QMessageBox.warning(self, "Kol Eklenmedi", h["hata"])
            return
        elle = self.merdiven_lh_elle_check.isChecked()
        ad = self.merdiven_kol_ad_edit.text().strip() or self._merdiven_yeni_ad("Kol")
        self.merdiven_kayitlari.append({
            "tip": MERDIVEN_TIP_KOL, "ad": ad, "n": self.merdiven_n_spin.value(),
            "h_cm": self.merdiven_h_spin.value(), "a_cm": self.merdiven_a_spin.value(),
            "b_m": self.merdiven_b_spin.value(), "t_cm": self.merdiven_t_spin.value(),
            "yan": int(self.merdiven_yan_combo.currentText()),
            "l_m": self.merdiven_l_spin.value() if elle else None,
            "h_kot_m": self.merdiven_hkot_spin.value() if elle else None,
        })
        self.merdiven_uyari_label.setText(f"⚠ {ad}: {h['uyari']}" if h["uyari"] else "")
        self.merdiven_kol_ad_edit.clear()
        self._merdiven_tablo_yenile()

    def _merdiven_sahanlik_ekle(self):
        h = merdiven_sahanlik_hesapla(self.merdiven_sah_en_spin.value(), self.merdiven_sah_boy_spin.value(),
                                      self.merdiven_sah_t_spin.value(), self.merdiven_sah_serbest_spin.value())
        if h["hata"]:
            self.merdiven_uyari_label.setText(f"⚠ Eklenmedi: {h['hata']}")
            QMessageBox.warning(self, "Sahanlık Eklenmedi", h["hata"])
            return
        ad = self.merdiven_sah_ad_edit.text().strip() or self._merdiven_yeni_ad("Sahanlık")
        self.merdiven_kayitlari.append({
            "tip": MERDIVEN_TIP_SAHANLIK, "ad": ad, "en_m": self.merdiven_sah_en_spin.value(),
            "boy_m": self.merdiven_sah_boy_spin.value(), "t_cm": self.merdiven_sah_t_spin.value(),
            "serbest_m": self.merdiven_sah_serbest_spin.value(),
        })
        self.merdiven_uyari_label.setText(f"⚠ {ad}: {h['uyari']}" if h["uyari"] else "")
        self.merdiven_sah_ad_edit.clear()
        self._merdiven_tablo_yenile()

    def _merdiven_tablo_yenile(self):
        if not hasattr(self, "merdiven_table") or merdiven_kol_hesapla is None:
            return
        riht, yan = self._merdiven_kalip_secimi()
        esas = kalip_esas_metni(riht, yan)
        self.merdiven_esas_label.setText(esas)
        tablo = self.merdiven_table
        tablo.blockSignals(True)
        beton = kalip = 0.0
        try:
            tablo.setRowCount(0)
            for i, s in enumerate(self.merdiven_kayitlari):
                h = self._merdiven_satir_hesap(s)
                toplam = merdiven_toplam_kalip(h, riht, yan)
                beton += h["beton_m3"]
                kalip += toplam
                kol = s["tip"] == MERDIVEN_TIP_KOL
                degerler = [
                    str(i + 1), s["tip"], s["ad"],
                    str(s["n"]) if kol else "", f"{s['h_cm']:g}" if kol else "", f"{s['a_cm']:g}" if kol else "",
                    f"{h['L_m']:.2f}" if kol else "", f"{h['H_m']:.2f}" if kol else "",
                    f"{h['s_m']:.3f}" if kol else "",
                    f"{s['b_m']:.2f}" if kol else f"{s['en_m']:.2f}", "" if kol else f"{s['boy_m']:.2f}",
                    f"{s['t_cm']:g}", str(s["yan"]) if kol else "",
                    f"{tek_hane(h['beton_m3'])}", f"{tek_hane(h['alt_m2'])}",
                    f"{tek_hane(h['riht_m2'])}" if kol else "", f"{tek_hane(h['yan_m2'])}" if kol else "",
                    "" if kol else f"{tek_hane(h['kenar_m2'])}", f"{tek_hane(toplam)}",
                ]
                ipucu = (f"Profil alanı {h['profil_m2']:.4f} m²" + (" (L/H elle)" if s.get("l_m") else "")
                         if kol else f"Serbest kenar {s['serbest_m']:g} m")
                if h["uyari"]:
                    ipucu += f"\n⚠ {h['uyari']}"
                tablo.insertRow(i)
                for col, deger in enumerate(degerler):
                    item = QTableWidgetItem(deger)
                    duzenlenir = col == self.MERDIVEN_T_KOL or (kol and col == self.MERDIVEN_YAN_KOL)
                    if not duzenlenir:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setToolTip(ipucu)
                    if h["uyari"]:
                        item.setForeground(QColor("#f5b041"))
                    tablo.setItem(i, col, item)
        finally:
            tablo.blockSignals(False)
        self.merdiven_toplam_label.setText(
            f"{self.aktif_kat_adi or 'Kat seçilmedi'} — TOPLAM: {len(self.merdiven_kayitlari)} satır | "
            f"Beton: {tek_hane(beton, True)} m³ | Toplam Kalıp: {tek_hane(kalip, True)} m²   ({esas})")

    def _merdiven_hucre_degisti(self, item):
        """Satır bazında t (cm) / yan taraf düzeltme — geçersizse eski değer korunur."""
        col, row = item.column(), item.row()
        if col not in (self.MERDIVEN_T_KOL, self.MERDIVEN_YAN_KOL) or not (0 <= row < len(self.merdiven_kayitlari)):
            return
        s = self.merdiven_kayitlari[row]
        yeni = dict(s)
        metin = item.text().strip()
        try:
            deger = float(metin.replace(",", ".").replace("cm", "").strip())
        except ValueError:
            deger = None
        if deger is not None:
            if col == self.MERDIVEN_T_KOL:
                yeni["t_cm"] = deger
            else:
                yeni["yan"] = int(deger) if deger == int(deger) else deger
        h = self._merdiven_satir_hesap(yeni) if deger is not None else {"hata": "sayı değil"}
        if h["hata"]:
            self.merdiven_uyari_label.setText(
                f"⚠ {s['ad']}: geçersiz değer '{metin}' ({h['hata']}) — eski değer korundu.")
        else:
            s.update(yeni)
            self.merdiven_uyari_label.setText(f"⚠ {s['ad']}: {h['uyari']}" if h["uyari"] else "")
        self._merdiven_tablo_yenile()

    def _merdiven_sil(self):
        satirlar = sorted({i.row() for i in self.merdiven_table.selectedIndexes()}, reverse=True)
        if not satirlar:
            QMessageBox.information(self, "Bilgi", "Silmek için tablodan satır seçin.")
            return
        for row in satirlar:
            if 0 <= row < len(self.merdiven_kayitlari):
                del self.merdiven_kayitlari[row]
        self._merdiven_tablo_yenile()

    def _merdiven_temizle(self):
        if not self.merdiven_kayitlari:
            return
        cevap = QMessageBox.question(
            self, "Temizle",
            f"'{self.aktif_kat_adi or 'Kat seçilmedi'}' katının {len(self.merdiven_kayitlari)} merdiven satırı "
            "silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap == QMessageBox.StandardButton.Yes:
            self.merdiven_kayitlari.clear()
            self._merdiven_tablo_yenile()

    # ── Rev-151: Kat Özeti (kat bazlı beton + kalıp) ──
    KAT_OZETI_KOLONLAR = ["Kat", "Eleman", "Adet", "Beton (m³)", "Kalıp (m²)"]

    def _kat_ozeti_sekmesi_olustur(self) -> QWidget:
        """Kat Özeti sekmesi.

        Neyi çözüyoruz? Beton/kalıp sekmelerde dağınık; müteahhit kat kat
        tek tabloda görmek, betonu kat bazında sipariş etmek ister. Değerler
        her sekmenin KENDİ formülünden gelir, burada sadece toplanır.
        Nasıl test ederiz? scratchpad/test_kat_ozeti.py (saf çekirdek + headless pencere).
        """
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(6, 6, 6, 6)
        bilgi = QLabel(
            "Kolon, Perde, Kiriş, Döşeme ve Merdiven sekmelerindeki kayıtlar kat kat toplanır; radye ve temel "
            "kirişi 'Temel' satırındadır. Beton & Kalıp sekmesine elle eklenen satırlar '(elle)' "
            "ekiyle ayrıca görünür. Değerler NET betondur (fire hariç). Sekme her açıldığında güncellenir."
        )
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("color:#d4a017; font-size:9pt;")
        lay.addWidget(bilgi)

        self.kat_ozeti_table = QTableWidget()
        self.kat_ozeti_table.setColumnCount(len(self.KAT_OZETI_KOLONLAR))
        self.kat_ozeti_table.setHorizontalHeaderLabels(self.KAT_OZETI_KOLONLAR)
        self.kat_ozeti_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.kat_ozeti_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.kat_ozeti_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.kat_ozeti_table.setMinimumHeight(300)
        self.kat_ozeti_table.setStyleSheet(
            "QTableWidget { background:#1e1e2e; color:#e0e0e0; gridline-color:#444; border:1px solid #555; }"
            "QHeaderView::section { background:#2d2d3d; color:#f39c12; font-weight:bold;"
            " padding:5px; border:1px solid #444; }"
            "QTableWidget::item:selected { background:#3a3a5a; }"
        )
        lay.addWidget(self.kat_ozeti_table)

        alt = QHBoxLayout()
        btn_yenile = QPushButton("Yenile")
        btn_yenile.setToolTip("Tüm sekmelerdeki güncel kayıtlarla özeti yeniden oluşturur.")
        btn_yenile.setStyleSheet("background:#2471a3; color:white; font-weight:bold; padding:5px 14px;"
                                 " border:none; border-radius:3px;")
        btn_yenile.clicked.connect(self._kat_ozeti_yenile)
        alt.addWidget(btn_yenile)
        alt.addStretch()
        btn_excel = QPushButton(" Excel'e Aktar")
        btn_excel.setToolTip("Kat özetini Excel dosyasına kaydeder (kat satırları + eleman toplamları).")
        btn_excel.setStyleSheet("background:#1e8449; color:white; font-weight:bold; padding:5px 14px;"
                                " border:none; border-radius:3px;")
        btn_excel.clicked.connect(self._kat_ozeti_excel)
        alt.addWidget(btn_excel)
        lay.addLayout(alt)

        self.kat_ozeti_toplam_label = QLabel()
        self.kat_ozeti_toplam_label.setStyleSheet(
            "color:#2ecc71; font-weight:bold; font-size:10pt; background:#2a2a3a;"
            " border:1px solid #f39c12; border-radius:4px; padding:6px;")
        lay.addWidget(self.kat_ozeti_toplam_label)
        self._kat_ozeti_yenile()
        return tab

    def _kat_ozeti_kalemleri(self) -> List[Dict]:
        """Tüm sekmelerden ham kalemler: {kat, eleman, adet, beton_m3, kalip_m2}.
        Hesap her sekmenin kendi fonksiyonuyla yapılır (tek formül kaynağı)."""
        kalemler: List[Dict] = []
        for (kat, _ad), k in getattr(self, "beton_kalip_kolon_kayitlari", {}).items():
            # Rev-160: kolon aracında oranla (≥6) Perde sınıflanan eleman Perde satırına gider;
            # Rev-161: güncel kat ayarıyla (perde kalıbı net yükseklik)
            h = self._kolon_kayit_hesap(kat, k)
            if not h.get("hata"):
                kalemler.append({"kat": kat, "eleman": k.get("tip", "Kolon"), "adet": 1,
                                 "beton_m3": h["beton_m3"], "kalip_m2": h["kalip_m2"]})
        for (kat, _h), s in getattr(self, "perde_kayitlari", {}).items():
            h = self._perde_satir_hesap(s, self._perde_kat_ayari(kat))
            if not h.get("hata"):
                kalemler.append({"kat": kat, "eleman": "Perde", "adet": 1,
                                 "beton_m3": h["beton_m3"], "kalip_m2": h["kalip_m2"]})
        if kiris_hesapla is not None:
            for kat, liste in self._kiris_kat_kayitlari.items():
                for s in liste:
                    h = self._kiris_satir_hesap(s)
                    if not h["hata"]:
                        kalemler.append({"kat": kat, "eleman": "Kiriş", "adet": 1,
                                         "beton_m3": h["beton_m3"], "kalip_m2": h["toplam_kalip_m2"]})
        if doseme_hesapla is not None:
            for kat, liste in self._doseme_kat_kayitlari.items():
                for s in liste:
                    h = self._doseme_satir_hesap(s)
                    if not h["hata"]:
                        # Rev-164: saçak ayrı "Saçak" satırına
                        kalemler.append({"kat": kat, "eleman": SACAK_TIPI if sacak_mi(s) else "Döşeme", "adet": 1,
                                         "beton_m3": h["beton_m3"], "kalip_m2": h["toplam_kalip_m2"]})
        for s in getattr(self, "temel_kirisi_kayitlari", {}).values():
            kalemler.append({"kat": TEMEL_KAT, "eleman": "Temel Kirişi", "adet": 1,
                             "beton_m3": s.get("beton_m3", 0.0), "kalip_m2": s.get("kalip_m2", 0.0)})
        if merdiven_kol_hesapla is not None:
            riht, yan = self._merdiven_kalip_secimi()
            for kat, liste in self._merdiven_kat_kayitlari.items():
                for s in liste:
                    h = self._merdiven_satir_hesap(s)
                    if not h["hata"]:
                        kalemler.append({"kat": kat, "eleman": "Merdiven", "adet": 1, "beton_m3": h["beton_m3"],
                                         "kalip_m2": merdiven_toplam_kalip(h, riht, yan)})
        # Rev-157: radye kayıt listesi (katsız -> Temel grubu, SBH ile aynı grup)
        if radye_kaydi_hesapla is not None:
            for s in getattr(self, "radye_kayitlari", []):
                h = radye_kaydi_hesapla(s)
                if not h["hata"]:
                    kalemler.append({"kat": TEMEL_KAT, "eleman": "Radye", "adet": 1,
                                     "beton_m3": h["beton_m3"], "kalip_m2": h["kalip_m2"]})
        # Beton & Kalıp sekmesine elle eklenen satırlar (etiketsiz olanlar)
        tablo = getattr(self, "beton_kalip_table", None)
        if tablo is not None:
            for row in range(tablo.rowCount()):
                ilk = tablo.item(row, 0)
                if ilk is None or ilk.data(Qt.ItemDataRole.UserRole):
                    continue
                try:
                    kat = ilk.text().strip()
                    kalemler.append({
                        "kat": "" if kat == "-" else kat,
                        "eleman": f"{tablo.item(row, 1).text()} (elle)",
                        "adet": float(tablo.item(row, 2).text()),
                        "beton_m3": float(tablo.item(row, 6).text()),
                        "kalip_m2": float(tablo.item(row, 9).text()),
                    })
                except (AttributeError, ValueError):
                    continue
        return kalemler

    def _kat_ozeti_hesapla(self) -> Optional[Dict]:
        if kat_ozeti_olustur is None:
            return None
        kat_sirasi = [k["kat_adi"] for k in getattr(self, "demir_kat_verileri", [])]
        return kat_ozeti_olustur(self._kat_ozeti_kalemleri(), kat_sirasi)

    def _kat_ozeti_yenile(self, *_):
        if not hasattr(self, "kat_ozeti_table"):
            return
        ozet = self._kat_ozeti_hesapla()
        tablo = self.kat_ozeti_table
        tablo.setRowCount(0)
        if ozet is None:
            self.kat_ozeti_toplam_label.setText("Özet modülü yüklenemedi.")
            return
        renkler = {"ara": ("#2a2a3a", "#f39c12"), "eleman": ("#1f2d3a", "#5dade2"),
                   "genel": ("#1e3a24", "#2ecc71")}
        kalin = QFont()
        kalin.setBold(True)
        for satir in ozet_tablo_satirlari(ozet):
            tur = satir[5]
            row = tablo.rowCount()
            tablo.insertRow(row)
            for col, deger in enumerate(satir[:5]):
                metin = f"{tek_hane(deger, True)}" if isinstance(deger, float) else str(deger)   # Rev-165: tek hane
                item = QTableWidgetItem(metin)
                if col >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if tur in renkler:
                    zemin, yazi = renkler[tur]
                    item.setBackground(QColor(zemin))
                    item.setForeground(QColor(yazi))
                    item.setFont(kalin)
                tablo.setItem(row, col, item)
        if ozet["katlar"]:
            self.kat_ozeti_toplam_label.setText(
                f"GENEL TOPLAM ({len(ozet['katlar'])} kat/bölüm) — Beton: {tek_hane(ozet['beton_m3'], True)} m³ | "
                f"Kalıp: {tek_hane(ozet['kalip_m2'], True)} m²")
        else:
            self.kat_ozeti_toplam_label.setText(
                "Henüz kayıt yok — Kolon, Perde, Kiriş, Döşeme veya temel sekmelerinden eleman ekleyin.")

    def _kat_ozeti_excel(self):
        ozet = self._kat_ozeti_hesapla()
        if not ozet or not ozet["katlar"]:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak kayıt yok.")
            return
        if not PANDAS_AVAILABLE:
            QMessageBox.warning(self, "Uyarı", "Excel için pandas+openpyxl gerekli:\npip install pandas openpyxl")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "kat_ozeti_beton_kalip.xlsx",
                                                   "Excel (*.xlsx)")
        if not file_path:
            return
        try:
            satirlar = [s[:5] for s in ozet_tablo_satirlari(ozet)]
            df = pd.DataFrame(satirlar, columns=self.KAT_OZETI_KOLONLAR)
            basliklar = ["KAT BAZLI BETON + KALIP ÖZETİ",
                         "Beton değerleri NET (fire hariç). Radye ve temel kirişi 'Temel' satırında."]
            if kalip_esas_metni is not None and any(self._merdiven_kat_kayitlari.values()):
                basliklar.append("Merdiven " + kalip_esas_metni(*self._merdiven_kalip_secimi()).lower())
            with pd.ExcelWriter(file_path, engine="openpyxl") as yazici:
                df.to_excel(yazici, index=False, sheet_name="Kat Özeti", startrow=len(basliklar) + 1)
                sayfa = yazici.sheets["Kat Özeti"]
                for i, metin in enumerate(basliklar, start=1):
                    sayfa.cell(row=i, column=1, value=metin)
                beton_kalip_sutunlari_tek_hane(sayfa)   # Rev-166
                # Rev-157: radye varsa aynı dosyada ayrıntılı "Radye" sayfası (formüllü)
                radyeler = [k for k in getattr(self, "radye_kayitlari", [])
                            if radye_kaydi_hesapla is not None and not radye_kaydi_hesapla(k)["hata"]]
                if radyeler and radye_sayfasi_yaz is not None:
                    from datetime import datetime
                    radye_sayfasi_yaz(yazici.book.create_sheet("Radye"), radyeler,
                                      self._rapor_proje_adi(), datetime.now().strftime("%d.%m.%Y"))
            QMessageBox.information(
                self, "Başarılı",
                f"Kaydedildi:\n{file_path}\nBeton: {tek_hane(ozet['beton_m3'], True)} m³ | Kalıp: {tek_hane(ozet['kalip_m2'], True)} m²")
            logger.info(f"Kat özeti Excel: {file_path}")
        except Exception as e:
            logger.error(f"[KAT_OZETI] Excel hatası: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{e}")

    def _temel_kirisi_sekmesi_olustur(self) -> QWidget:
        """Temel Kirişi sekmesini kurar (Rev-137).

        Neyi çözüyoruz? SBH temel kirişlerinin beton (g×y×L) ve kalıp
        (2×y×L, alt yüz yok) metrajı ayrı bir tabloda toplanır; uzunluk kenar
        çizgisinden otomatik okunur, tablodan elle düzeltilebilir.
        Nasıl test ederiz? scratchpad/test_temel_kirisi_ui.py (headless).
        """
        tab = QWidget()
        dis = QVBoxLayout(tab)
        dis.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        icerik = QWidget()
        lay = QVBoxLayout(icerik)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        bilgi = QLabel(
            "Temel kirişi (SBH) metrajı — TOPLU SEÇİM: butona basın, birimi seçin, "
            "AutoCAD'de her kiriş için 'SBH-1 (20/165)' yazısı + iki kenarın TÜM çizgileri (kesişen "
            "kirişle bölünen kenarın bütün parçaları) + ENTER. Uzunluk = iki kenarın baştan sona "
            "kapsamının ortalaması (boşluklar dahil); yan kalıp her yüzün dolu (parça toplamı) "
            "uzunluğuyla. Kenarlar 2×genişlikten fazla farklıysa 'eksik parça' sorulur. Bitirmek için "
            "boş ENTER. Kalıp sadece 2 yan yüz (alt yüz grobetona oturur). Uzunluk hücresine çift "
            "tıklayıp düzeltebilirsiniz (elle düzeltmede kalıp 2 × yükseklik × L olur).\n"
            "DEMİR: aynı satırdan filiz (düşey, her aralıkta bir, 2 yüz) + tevzi (yatay, kiriş boyunca, "
            "12 m'yi aşarsa bindirmeli) hesaplanır. Parametreler SBH TİPİ başına bir kez girilir "
            "(yeni tip seçilince pencere açılır; sonradan 'SBH Demir Parametreleri' ile düzenlenir)."
        )
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("color:#d4a017; font-size:9pt;")
        lay.addWidget(bilgi)

        ust = QHBoxLayout()
        lbl_birim = QLabel("Çizim Birimi:")
        lbl_birim.setStyleSheet("color:white;")
        ust.addWidget(lbl_birim)
        self.tk_birim_combo = QComboBox()
        self.tk_birim_combo.addItems(["Otomatik (INSUNITS)", "mm", "cm", "m"])
        self.tk_birim_combo.setToolTip(
            "Kenar çizgisi uzunluğu çizim biriminde okunur. Seçim başında birim bir kez "
            "sorulur; buradaki değer (Otomatik = AutoCAD INSUNITS) o sorunun varsayılanıdır."
        )
        self.tk_birim_combo.setStyleSheet(
            "QComboBox { background:#2a2a3a; color:white; border:1px solid #666; padding:4px; }"
            "QComboBox QAbstractItemView { background:#2a2a3a; color:white; }"
        )
        ust.addWidget(self.tk_birim_combo)
        ust.addStretch()
        self.btn_tk_sec = QPushButton(" TEMEL KİRİŞİ SEÇ (AutoCAD)")
        self.btn_tk_sec.setToolTip("Yazı + kenar çizgisi ile döngüsel temel kirişi seçimini başlatır.")
        self.btn_tk_sec.setStyleSheet(
            "QPushButton { background:#8e44ad; color:white; font-weight:bold; padding:8px 16px;"
            " border:2px solid #a569bd; border-radius:4px; }"
            "QPushButton:hover { background:#a569bd; }"
        )
        self.btn_tk_sec.clicked.connect(self._temel_kirisi_sec)
        ust.addWidget(self.btn_tk_sec)
        lay.addLayout(ust)

        self.temel_kirisi_table = QTableWidget()
        self.temel_kirisi_table.setColumnCount(len(self.TK_KOLONLAR))
        self.temel_kirisi_table.setHorizontalHeaderLabels(self.TK_KOLONLAR)
        self.temel_kirisi_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.temel_kirisi_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.temel_kirisi_table.setMinimumHeight(260)
        self.temel_kirisi_table.setStyleSheet(
            "QTableWidget { background:#1e1e2e; color:#e0e0e0; gridline-color:#444;"
            " border:1px solid #555; }"
            "QHeaderView::section { background:#2d2d3d; color:#a569bd; font-weight:bold;"
            " padding:5px; border:1px solid #444; }"
            "QTableWidget::item:selected { background:#3a3a5a; }"
        )
        self.temel_kirisi_table.itemChanged.connect(self._temel_kirisi_hucre_degisti)
        lay.addWidget(self.temel_kirisi_table)

        alt = QHBoxLayout()
        btn_sil = QPushButton("Seçili Sil")
        btn_sil.setToolTip("Seçili kirişleri siler ve çizimdeki yeşil rengi geri alır.")
        btn_sil.setStyleSheet(
            "background:#c0392b; color:white; font-weight:bold; padding:5px 12px;"
            " border:none; border-radius:3px;"
        )
        btn_sil.clicked.connect(self._temel_kirisi_sil)
        alt.addWidget(btn_sil)
        btn_temizle = QPushButton("Temizle")
        btn_temizle.setStyleSheet(
            "background:#7f8c8d; color:white; font-weight:bold; padding:5px 12px;"
            " border:none; border-radius:3px;"
        )
        btn_temizle.clicked.connect(self._temel_kirisi_temizle)
        alt.addWidget(btn_temizle)
        btn_tk_param = QPushButton("SBH Demir Parametreleri")
        btn_tk_param.setToolTip("Bir SBH tipinin filiz/tevzi parametrelerini düzenler; o tipteki tüm "
                                "satırların demiri yeniden hesaplanır.")
        btn_tk_param.setStyleSheet("background:#2471a3; color:white; font-weight:bold; padding:5px 12px;"
                                   " border:none; border-radius:3px;")
        btn_tk_param.clicked.connect(self._temel_kirisi_parametre_duzenle)
        alt.addWidget(btn_tk_param)
        alt.addStretch()
        btn_tk_kesim = QPushButton(" DEMİRİ KESİM LİSTESİNE AKTAR")
        btn_tk_kesim.setToolTip(
            "Filiz ve tevzi parçalarını Kesim Listesi'ne aktarır. 12 m'yi aşan tevzi çubuğu bindirmeli "
            "boyuyla stok boyuna bölünür (kesim aracı bindirme eklemez — bindirme bir kez sayılır).")
        btn_tk_kesim.setStyleSheet("background:#b9770e; color:white; font-weight:bold; padding:5px 14px;"
                                   " border:none; border-radius:3px;")
        btn_tk_kesim.clicked.connect(self._temel_kirisi_kesime_aktar)
        alt.addWidget(btn_tk_kesim)
        btn_excel = QPushButton(" TEMEL KİRİŞİ EXCEL'E AKTAR")
        btn_excel.setStyleSheet(
            "background:#1e8449; color:white; font-weight:bold; padding:5px 14px;"
            " border:2px solid #2ecc71; border-radius:3px;"
        )
        btn_excel.clicked.connect(self._temel_kirisi_excel)
        alt.addWidget(btn_excel)
        lay.addLayout(alt)

        self.tk_toplam_label = QLabel()
        self.tk_toplam_label.setStyleSheet(
            "color:#2ecc71; font-weight:bold; font-size:10pt; background:#2a2a3a;"
            " border:1px solid #a569bd; border-radius:4px; padding:6px;"
        )
        lay.addWidget(self.tk_toplam_label)
        self.tk_demir_label = QLabel()
        self.tk_demir_label.setWordWrap(True)
        self.tk_demir_label.setStyleSheet(
            "color:#f5b041; font-weight:bold; font-size:10pt; background:#2a2a3a;"
            " border:1px solid #b9770e; border-radius:4px; padding:6px;"
        )
        lay.addWidget(self.tk_demir_label)
        self._temel_kirisi_tablo_yenile()

        scroll.setWidget(icerik)
        dis.addWidget(scroll)
        return tab

    def _temel_kirisi_birim(self) -> str:
        secim = self.tk_birim_combo.currentText()
        if secim in ("mm", "cm", "m"):
            return secim
        birim = None
        try:
            birim = self.acad_connector.cizim_birimi_oku()
        except Exception as e:
            logger.error(f"[TEMEL KIRISI] _temel_kirisi_birim hata: {e}", exc_info=True)
        logger.info(f"[TEMEL KIRISI] kullanılan çizim birimi: {birim or 'cm'} "
                    f"(combo={secim}, INSUNITS={birim})")
        return birim or "cm"

    def _temel_kirisi_birim_sor(self) -> Optional[str]:
        """Birim seçim başında BİR KEZ sorulur (her kirişte teyit yok)."""
        varsayilan = self._temel_kirisi_birim()
        secenekler = ["cm", "mm", "m"]
        birim, tamam = QInputDialog.getItem(
            self, "Çizim Birimi",
            "Kenar çizgisi uzunlukları hangi birimde çizildi?\n"
            "(Bu seçim tüm kirişlerde kullanılır — yanlışsa uzunluklar 10/100 kat hatalı çıkar.)",
            secenekler, secenekler.index(varsayilan), False,
        )
        if not tamam:
            return None
        self.tk_birim_combo.setCurrentText(birim)
        logger.info(f"[TEMEL KIRISI] kullanıcının seçtiği birim: {birim}")
        return birim

    def _temel_kirisi_sec(self):
        """Birimi bir kez sorar, toplu seçim panelini açıp döngüyü hemen
        başlatır (kullanıcı doğrudan AutoCAD'e geçer), sonucu registry'ye işler."""
        if not self.acad_connector or not getattr(self.acad_connector, "bagli", False):
            QMessageBox.warning(self, "Uyarı", "Önce AutoCAD'e bağlanın!")
            return
        birim = self._temel_kirisi_birim_sor()
        if birim is None:
            return
        panel = TemelKirisiDonguPaneli(
            self.acad_connector, birim, self.temel_kirisi_kayitlari, self
        )
        # Panel görünür olur olmaz toplu döngü başlar — ekstra tıklama yok
        QTimer.singleShot(0, panel._dongu)
        if panel.exec() != QDialog.DialogCode.Accepted:
            return
        for satir in panel.sonuclar():
            eski = self.temel_kirisi_kayitlari.get(satir["yazi_handle"])
            if eski:
                # Güncellemede artık kullanılmayan eski çizgilerin yeşilini sök
                for h in eski.get("cizgi_handleler") or []:
                    if h not in satir["cizgi_handleler"]:
                        self._temel_kirisi_renk_geri(h)
            kayit = dict(satir)
            kayit.pop("yeni_boyanan", None)
            self.temel_kirisi_kayitlari[satir["yazi_handle"]] = kayit
        # Rev-153: parametresi olmayan yeni SBH tipleri — döngü BİTTİKTEN sonra, tip başına
        # bir kez sorulur (döngü içinde Qt penceresi açmak AutoCAD↔program geçişi = takılma, Rev-137)
        for tip in dict.fromkeys(s["ad"] for s in panel.sonuclar()):
            if tip not in self._tk_demir_tipleri():
                self._temel_kirisi_tip_parametresi_sor(tip, yeni_tip=True)
        self._temel_kirisi_tablo_yenile()

    # ── Rev-153: SBH demir tip parametreleri ──
    def _tk_demir_tipleri(self) -> Dict[str, Dict]:
        """Kayıtlı tip parametreleri (kalıcı dosyadan, oturumda önbellekli)."""
        if not hasattr(self, "_tk_demir_tip_onbellek"):
            self._tk_demir_tip_onbellek = dict(autocad_ayari_oku(self.SBH_DEMIR_AYAR_ANAHTARI, {}) or {})
        return self._tk_demir_tip_onbellek

    def _tk_tip_parametresi(self, tip: str) -> Dict:
        return self._tk_demir_tipleri().get(tip) or {}

    def _temel_kirisi_tip_parametresi_sor(self, tip: str, yeni_tip: bool = False) -> bool:
        """Parametre penceresi; Kaydet -> kalıcı yazar. Vazgeç -> bu oturumda varsayılanlar
        (kalıcı yazılmaz, sonraki seçimde tekrar sorulur)."""
        dialog = SbhDemirTipDialog(tip, self._tk_tip_parametresi(tip), yeni_tip, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._tk_demir_tipleri()[tip] = dialog.parametreler()
            autocad_ayari_yaz(self.SBH_DEMIR_AYAR_ANAHTARI, self._tk_demir_tipleri())
            logger.info(f"[TEMEL KIRISI] {tip} demir parametreleri kaydedildi: {dialog.parametreler()}")
            return True
        self._tk_demir_tipleri().setdefault(tip, {})
        return False

    def _temel_kirisi_parametre_duzenle(self):
        tipler = list(dict.fromkeys(
            [s["ad"] for s in self.temel_kirisi_kayitlari.values()] + list(self._tk_demir_tipleri())))
        if not tipler:
            QMessageBox.information(self, "Bilgi", "Henüz SBH tipi yok — önce temel kirişi seçin.")
            return
        tip, tamam = QInputDialog.getItem(self, "SBH Demir Parametreleri",
                                          "Düzenlenecek SBH tipi:", tipler, 0, False)
        if tamam and tip and self._temel_kirisi_tip_parametresi_sor(tip):
            self._temel_kirisi_tablo_yenile()

    def _temel_kirisi_demir(self, s: Dict) -> Dict:
        """Satırın demiri — her gösterimde güncel tip parametresiyle (düzenleme anında yansır)."""
        if temel_kirisi_demir_hesapla is None:
            return {"hata": "Demir modülü yüklenemedi"}
        return temel_kirisi_demir_hesapla(s["uzunluk_m"], s["yukseklik_cm"], self._tk_tip_parametresi(s["ad"]))

    def _temel_kirisi_kesime_aktar(self):
        if not self.temel_kirisi_kayitlari:
            QMessageBox.information(self, "Bilgi", "Aktarılacak temel kirişi yok.")
            return
        toplu: Dict[tuple, int] = {}
        for s in self.temel_kirisi_kayitlari.values():
            d = self._temel_kirisi_demir(s)
            for cap, boy_cm, adet in temel_kirisi_kesim_parcalari(d, self._tk_tip_parametresi(s["ad"])):
                toplu[(cap, boy_cm)] = toplu.get((cap, boy_cm), 0) + adet
        kalemler = [(cap, boy, adet, "Temel") for (cap, boy), adet in sorted(toplu.items())]
        self._kesim_penceresine_ekle(kalemler, "Temel kirişi demiri")

    def _temel_kirisi_renk_geri(self, handle):
        if not handle or not self.acad_connector:
            return
        try:
            self.acad_connector.obje_isaret_geri_al(handle)
        except Exception as e:
            logger.error(f"[TEMEL KIRISI] _temel_kirisi_renk_geri hata: {e}", exc_info=True)
            logger.debug(f"Temel kirişi renk geri alma hatası: {e}")

    def _temel_kirisi_tablo_yenile(self):
        tablo = self.temel_kirisi_table
        tablo.blockSignals(True)
        try:
            tablo.setRowCount(0)
            demirler = []
            for handle, s in self.temel_kirisi_kayitlari.items():
                row = tablo.rowCount()
                tablo.insertRow(row)
                d = self._temel_kirisi_demir(s)
                demirler.append(d)
                degerler = [
                    s["ad"], f"{s['genislik_cm']:g}", f"{s['yukseklik_cm']:g}",
                    f"{s['uzunluk_m']:.2f}", f"{tek_hane(s['beton_m3'])}",
                    f"{tek_hane(s['kalip_m2'])}", s.get("kaynak", ""),
                ]
                if d.get("hata"):
                    degerler += ["⚠"] + [""] * 8
                else:
                    degerler += [str(d["filiz_adet"]), f"{d['filiz_uzunluk_m']:.2f}", f"{d['filiz_kg']:.2f}",
                                 str(d["tevzi_cubuk"]), str(d["tevzi_k"]), f"{d['tevzi_boy_m']:.2f}",
                                 f"{d['tevzi_uzunluk_m']:.2f}", f"{d['tevzi_kg']:.2f}", f"{d['toplam_kg']:.2f}"]
                ipucu = (f"⚠ Demir hesaplanamadı: {d['hata']}" if d.get("hata") else
                         f"Filiz {d['filiz_yuz_adet']}/yüz · tevzi {d['tevzi_sira']} sıra/yüz, "
                         f"ham boy {d['tevzi_ham_boy_m']:.2f} m")
                for col, deger in enumerate(degerler):
                    item = QTableWidgetItem(deger)
                    if col != self.TK_UZUNLUK_KOL:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col == 0:
                        item.setData(Qt.ItemDataRole.UserRole, handle)
                    if col >= 7:
                        item.setToolTip(ipucu)
                        if d.get("hata"):
                            item.setForeground(QColor("#e74c3c"))
                    tablo.setItem(row, col, item)
        finally:
            tablo.blockSignals(False)
        beton = sum(s["beton_m3"] for s in self.temel_kirisi_kayitlari.values())
        kalip = sum(s["kalip_m2"] for s in self.temel_kirisi_kayitlari.values())
        self.tk_toplam_label.setText(
            f"TOPLAM: {len(self.temel_kirisi_kayitlari)} temel kirişi | "
            f"Beton: {tek_hane(beton, True)} m³ | Kalıp: {tek_hane(kalip, True)} m²"
        )
        if hasattr(self, "tk_demir_label"):
            gecerli = [d for d in demirler if not d.get("hata")]
            caplar = cap_bazli_topla(gecerli) if cap_bazli_topla else {}
            metin = (f"DEMİR — Filiz: {sum(d['filiz_kg'] for d in gecerli):,.2f} kg | "
                     f"Tevzi: {sum(d['tevzi_kg'] for d in gecerli):,.2f} kg | "
                     f"Toplam: {sum(d['toplam_kg'] for d in gecerli):,.2f} kg   —   ÇAP BAZLI: "
                     + (" | ".join(f"Ø{c}: {kg:,.2f} kg" for c, kg in caplar.items()) or "-"))
            hatali = len(demirler) - len(gecerli)
            if hatali:
                metin += f"\n⚠ {hatali} satırın demiri hesaplanamadı (hücre ipucuna bakın) — toplama katılmadı."
            self.tk_demir_label.setText(metin)

    def _temel_kirisi_handle(self, row: int):
        item = self.temel_kirisi_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _temel_kirisi_hucre_degisti(self, item):
        """Uzunluk hücresi elle düzeltilince beton/kalıp yeniden hesaplanır."""
        if item.column() != self.TK_UZUNLUK_KOL:
            return
        handle = self._temel_kirisi_handle(item.row())
        kayit = self.temel_kirisi_kayitlari.get(handle)
        if kayit is None:
            return
        try:
            yeni_l = float(item.text().replace(",", "."))
        except ValueError as e:
            logger.error(f"[TEMEL KIRISI] _temel_kirisi_hucre_degisti hata: {e}", exc_info=True)
            yeni_l = -1
        hesap = temel_kirisi_hesapla(kayit["genislik_cm"], kayit["yukseklik_cm"], yeni_l)
        if hesap["hata"]:
            QMessageBox.warning(self, "Geçersiz Uzunluk", "Uzunluk pozitif bir sayı olmalı (m).")
        else:
            if hesap["uyari"]:
                QMessageBox.warning(self, "Uzunluk Kontrolü", hesap["uyari"])
            # Rev-158: elle düzeltilen L ile çizimden okunan yan dolu uzunluklar artık
            # tutarsız -> düşülür, kalıp 2 × y × L (iki tam yan yüz)
            kayit.pop("yan_dolu_m", None)
            kayit.pop("kenar_kapsam_m", None)
            kayit.update({
                "uzunluk_m": hesap["uzunluk_m"],
                "beton_m3": hesap["beton_m3"],
                "kalip_m2": hesap["kalip_m2"],
                "kaynak": "Elle (düzeltildi)",
            })
        self._temel_kirisi_tablo_yenile()

    def _temel_kirisi_sil(self):
        satirlar = sorted({i.row() for i in self.temel_kirisi_table.selectedIndexes()})
        if not satirlar:
            QMessageBox.information(self, "Bilgi", "Silmek için satır seçin.")
            return
        for row in satirlar:
            handle = self._temel_kirisi_handle(row)
            kayit = self.temel_kirisi_kayitlari.pop(handle, None)
            if kayit:
                for h in [kayit.get("yazi_handle")] + (kayit.get("cizgi_handleler") or []):
                    self._temel_kirisi_renk_geri(h)
        self._temel_kirisi_tablo_yenile()

    def _temel_kirisi_temizle(self):
        if not self.temel_kirisi_kayitlari:
            return
        cevap = QMessageBox.question(
            self, "Temizle",
            "Tüm temel kirişi satırları silinecek ve çizimdeki yeşil renkler geri "
            "alınacak. Devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return
        for kayit in self.temel_kirisi_kayitlari.values():
            for h in [kayit.get("yazi_handle")] + (kayit.get("cizgi_handleler") or []):
                self._temel_kirisi_renk_geri(h)
        self.temel_kirisi_kayitlari.clear()
        self._temel_kirisi_tablo_yenile()

    def _temel_kirisi_excel(self):
        if not self.temel_kirisi_kayitlari:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak temel kirişi yok.")
            return
        if not PANDAS_AVAILABLE:
            QMessageBox.warning(self, "Uyarı",
                                "Excel için pandas+openpyxl gerekli:\npip install pandas openpyxl")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Kaydet", "temel_kirisi_metraj.xlsx", "Excel (*.xlsx)"
        )
        if not file_path:
            return
        try:
            df = pd.DataFrame(
                self._temel_kirisi_excel_satirlari(), columns=self.TK_KOLONLAR
            )
            caplar = cap_bazli_topla([self._temel_kirisi_demir(s)
                                      for s in self.temel_kirisi_kayitlari.values()]) if cap_bazli_topla else {}
            cap_df = pd.DataFrame([[f"Ø{c}", kg, round(kg / 1000, 4)] for c, kg in caplar.items()]
                                  + [["TOPLAM", round(sum(caplar.values()), 3), round(sum(caplar.values()) / 1000, 4)]],
                                  columns=["Çap", "Ağırlık (kg)", "Ağırlık (ton)"])
            with pd.ExcelWriter(file_path, engine="openpyxl") as yazici:
                df.to_excel(yazici, index=False, sheet_name="Temel Kirisi")
                beton_kalip_sutunlari_tek_hane(yazici.sheets["Temel Kirisi"])   # Rev-166
                cap_df.to_excel(yazici, index=False, sheet_name="Demir Cap Ozeti")
            QMessageBox.information(self, "Başarılı", f"Kaydedildi:\n{file_path}")
            logger.info(f"Temel kirişi Excel: {file_path}")
        except Exception as e:
            logger.error(f"[TEMEL KIRISI] _temel_kirisi_excel hata: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{e}")

    def _temel_kirisi_excel_satirlari(self) -> List[list]:
        """Excel satırları (sayısal değerler float) + en altta TOPLAM satırı."""
        satirlar = []
        for s in self.temel_kirisi_kayitlari.values():
            d = self._temel_kirisi_demir(s)
            demir = ([""] * 9 if d.get("hata") else
                     [d["filiz_adet"], d["filiz_uzunluk_m"], d["filiz_kg"], d["tevzi_cubuk"], d["tevzi_k"],
                      d["tevzi_boy_m"], d["tevzi_uzunluk_m"], d["tevzi_kg"], d["toplam_kg"]])
            satirlar.append([s["ad"], s["genislik_cm"], s["yukseklik_cm"], s["uzunluk_m"],
                             s["beton_m3"], s["kalip_m2"], s.get("kaynak", "")] + demir)

        def _topla(i):
            return round(sum(r[i] for r in satirlar if isinstance(r[i], (int, float))), 3)

        satirlar.append(["TOPLAM", "", "", "", _topla(4), _topla(5), "",
                         _topla(7), _topla(8), _topla(9), _topla(10), "", "", _topla(13), _topla(14), _topla(15)])
        return satirlar


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

            import os as _os
            import sys as _sys
            if getattr(_sys, 'frozen', False):
                _lisp_dir = _os.path.join(_sys._MEIPASS, "app", "lisp")
            else:
                _lisp_dir = _os.path.join(
                    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                    "lisp",
                )
            lsp_yolu = _os.path.join(_lisp_dir, f"{tur}.lsp")

            if not _os.path.exists(lsp_yolu):
                QMessageBox.critical(
                    self, "LISP Dosyası Bulunamadı",
                    f"LISP dosyası bulunamadı:\n{lsp_yolu}"
                )
                return

            try:
                # Kat yüksekliği LISP'in *IMP_KAT_YUKSEKLIGI* globaline SAYI
                # olarak (tırnaksız) yazılıyor — aksi halde LISP tarafında
                # 3.0 varsayılanı sessizce kullanılır (bkz. CLAUDE.md Rev-133 bug).
                self.acad_connector.sayisal_degisken_set(
                    {"*IMP_KAT_YUKSEKLIGI*": kat_yuk}
                )
                basarili = self.acad_connector.lisp_calistir(lsp_yolu, bekle=1.0)
                if not basarili:
                    QMessageBox.critical(
                        self, "LISP Hatası",
                        "LISP komutu AutoCAD'e gönderilemedi.\n"
                        "AutoCAD bağlantısını kontrol edin (detay: error_log.txt)."
                    )
                    return
                QMessageBox.information(
                    self, "LISP Gönderildi",
                    f"'{tur}' komutu AutoCAD'e gönderildi "
                    f"(Kat Yüksekliği: {kat_yuk:.2f} m).\n\n"
                    "Şimdi AutoCAD penceresine geçip seçim/istemleri "
                    "tamamlayın, ardından buraya dönüp "
                    "'Sonucu Oku' butonuna tıklayın."
                )
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
                f" TOPLAM HACIM: {tek_hane(sonuc.get('toplam_hacim', 0))} m3",
            ]
            atlanan = sonuc.get('atlanan_sayisi', 0)
            if atlanan:
                satirlar.append(
                    f" UYARI: {atlanan} obje alan=0 nedeniyle atlandi "
                    f"(Closed=Yes olmayabilir, AutoCAD komut satirina bakin)"
                )
        elif tur == "kiris_hacim":
            satirlar += [
                f" Toplam Uzunluk : {sonuc.get('toplam_uzunluk', 0):.3f} m",
                f" Kesit bxh : {sonuc.get('kiris_b', 0):.3f}x{sonuc.get('kiris_h', 0):.3f} m",
                f" TOPLAM HACIM : {tek_hane(sonuc.get('toplam_hacim', 0))} m3",
            ]
        elif tur == "kalip_alan":
            satirlar += [
                f" Kolon Kalip : {tek_hane(sonuc.get('kolon_kalip', 0))} m2",
                f" Kiris Kalip : {tek_hane(sonuc.get('kiris_kalip', 0))} m2",
                f" Doseme Kalip : {tek_hane(sonuc.get('doseme_kalip', 0))} m2",
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
