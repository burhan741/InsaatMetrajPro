"""
Saha Demiri Modülü (V5.0)
DXF dosyalarından MIKNATIS/PROXIMITY mantığıyla donatı hesabı yapar
- Kiriş kutularındaki kolon filizlerini mesafe bazlı tanır
- ETR/İLA/GÖV anahtar kelimelerini kontrol eder
- GÖRSEL TEYİT: Matplotlib ile interaktif düzenleme
- Kat bazlı rapor ve özet çıkarır
"""

import os
import re
import math
import ezdxf
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
    QGroupBox, QHeaderView, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QSplitter, QTextEdit, QTabWidget, QDoubleSpinBox, QComboBox, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


# =============================================================================
# SHAPELY OLMADAN GEOMETRİ İŞLEMLERİ (Ray Casting Algorithm)
# =============================================================================

class Point:
    """Basit nokta sınıfı"""
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Polygon:
    """Shapely olmadan çalışan Polygon sınıfı"""
    def __init__(self, points):
        self.points = points
        self.n = len(points)

    def contains(self, point):
        """Ray casting algoritması ile nokta polygon içinde mi kontrol et"""
        x, y = point.x, point.y
        inside = False
        j = self.n - 1
        for i in range(self.n):
            xi, yi = self.points[i]
            xj, yj = self.points[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 0.0000001) + xi):
                inside = not inside
            j = i
        return inside


# =============================================================================
# SAHA DEMİRİ MODÜLÜ (V5.0) - MIKNATIS + GÖRSEL TEYİT
# =============================================================================

DEFAULT_LAYERS = {
    "KAT_SINIRI": "H_KAT",
    "KAT_ISMI": "A_KAT_ISMI",
    "TEMEL": "H_TEMEL",
    "KOLON": "H_KOLON",
    "KIRIS": "H_KIRIS",
    "PERDE": "H_PERDE",
    "DOSEME": "H_DOSEME",
    "TABLO": "H_TABLO",
}

LAYER_COLORS = {
    "KAT_SINIRI": "#3498db",
    "KAT_ISMI": "#9b59b6",
    "TEMEL": "#e74c3c",
    "KOLON": "#2ecc71",
    "KIRIS": "#f39c12",
    "PERDE": "#1abc9c",
    "DOSEME": "#e67e22",
    "TABLO": "#95a5a6",
}

AGIRLIKLAR = {
    8: 0.395, 10: 0.617, 12: 0.888, 14: 1.208,
    16: 1.578, 18: 1.998, 20: 2.466, 22: 2.980,
    24: 3.550, 25: 3.850, 26: 4.168, 28: 4.834,
    30: 5.549, 32: 6.313
}

# Regex: P01 8Ƒ12/40 L=310 veya 12Ø14 L=225 formatlarını yakalar
# Ƒ, Ø, ø, Φ, φ, /, N, n karakterlerini destekler
REGEX_DEMIR = r"(?:P\d+\s+)?(\d+)\s*[ØøΦφƑƒ/Nn]?\s*(\d+)(?:/\d+)?\s*L\s*=\s*(\d+)"
REGEX_KOLON_ISMI = r"\b(S|SZ)\d+\b"
# Kiriş/Temel isimleri (T19, K1, MK5 vb.)
REGEX_KIRIS_ISMI = r"\b(T|K|MK|TK)\d+\b"
DEFAULT_MIKNATIS_MESAFESI = 75.0

# Donatı tipi kısaltmaları ve anahtar kelimeleri
DONATI_TIPLERI = {
    "ETRIYE": ["ETR", "ETRIYE", "ETRİYE", "ETRY"],
    "ILAVE": ["ILA", "İLA", "ILAVE", "İLAVE"],
    "GOVDE": ["GOV", "GÖV", "GOVDE", "GÖVDE"],
    "DAGITMA": ["DAG", "DAĞ", "DAGITMA", "DAĞITMA"],
    "MONTAJ": ["MON", "MONTAJ", "ALT"],
    "PILYE": ["PIL", "PİL", "PILYE", "PİLYE", "UST", "ÜST"],
}


def donati_tipi_bul(metin):
    """
    Metin içindeki kısaltmalardan donatı tipini belirler.
    Döndürür: (tip_kodu, tip_aciklama)
    """
    metin_upper = metin.upper()

    for tip_kodu, anahtar_kelimeler in DONATI_TIPLERI.items():
        for kelime in anahtar_kelimeler:
            # Kelimeyi noktalı veya noktasız ara (ila. veya ila)
            if kelime in metin_upper or f"{kelime}." in metin_upper:
                aciklamalar = {
                    "ETRIYE": "Etriye (etr)",
                    "ILAVE": "İlave (ila)",
                    "GOVDE": "Gövde (göv)",
                    "DAGITMA": "Dağıtma (dağ)",
                    "MONTAJ": "Montaj (mon)",
                    "PILYE": "Pilye (üst)",
                }
                return tip_kodu, aciklamalar.get(tip_kodu, tip_kodu)

    return None, None


def geometri_olustur(polyline_entity):
    """LWPOLYLINE'dan Polygon oluştur"""
    try:
        pts = list(polyline_entity.get_points())
        if not pts or len(pts) < 3:
            return None
        return Polygon([(p[0], p[1]) for p in pts])
    except Exception:
        return None


def mesafe_hesapla(p1, p2):
    """İki nokta arasındaki mesafeyi ölçer"""
    return math.sqrt((p2.x - p1.x)**2 + (p2.y - p1.y)**2)


# =============================================================================
# GELİŞMİŞ GÖRSEL EDİTÖR - ELEMAN BAZLI KONTROL PANELİ
# =============================================================================

class DonatiKarti(QWidget):
    """Tek bir donatı için tıklanabilir kart widget'ı"""

    def __init__(self, demir_data, index, parent_editor=None):
        super().__init__()
        self.demir = demir_data
        self.index = index
        self.parent_editor = parent_editor
        self.init_ui()

    def init_ui(self):
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_style()

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)

        # Renk ikonu
        self.lbl_icon = QLabel(self._get_icon())
        self.lbl_icon.setFixedWidth(30)
        self.lbl_icon.setStyleSheet("font-size: 18px;")
        layout.addWidget(self.lbl_icon)

        # Poz bilgisi
        poz = self.demir.get('Poz', '').split()[0] if self.demir.get('Poz') else 'P?'
        self.lbl_poz = QLabel(poz)
        self.lbl_poz.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.lbl_poz.setFixedWidth(60)
        layout.addWidget(self.lbl_poz)

        # Çap
        cap = self.demir.get('Çap', 'Ø?')
        self.lbl_cap = QLabel(cap)
        self.lbl_cap.setStyleSheet("color: #2c3e50; font-size: 12px;")
        self.lbl_cap.setFixedWidth(50)
        layout.addWidget(self.lbl_cap)

        # Boy
        boy = self.demir.get('Boy (cm)', 0)
        self.lbl_boy = QLabel(f"L={boy}")
        self.lbl_boy.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        self.lbl_boy.setFixedWidth(70)
        layout.addWidget(self.lbl_boy)

        # Detay
        detay = self.demir.get('Detay', '')
        self.lbl_detay = QLabel(f"({detay[:20]})" if detay else "")
        self.lbl_detay.setStyleSheet("color: #95a5a6; font-size: 11px; font-style: italic;")
        layout.addWidget(self.lbl_detay, 1)

        # Ağırlık
        agirlik = self.demir.get('Ağırlık (kg)', 0)
        self.lbl_agirlik = QLabel(f"{agirlik:.2f} kg")
        self.lbl_agirlik.setStyleSheet("color: #27ae60; font-weight: bold;")
        layout.addWidget(self.lbl_agirlik)

        self.setLayout(layout)

    def _get_icon(self):
        tip = self.demir.get('Tip', '')
        detay = str(self.demir.get('Detay', '')).lower()
        if "FİLİZ" in tip or "FILIZ" in tip.upper():
            return "🔴"
        elif "etr" in detay:
            return "🟢"
        elif any(x in detay for x in ["ila", "İlave", "dağ", "göv", "gov"]):
            return "🟠"
        elif any(x in detay for x in ["mon", "pil", "üst", "ust"]):
            return "🔵"
        return "🔵"

    def _get_color(self):
        tip = self.demir.get('Tip', '')
        detay = str(self.demir.get('Detay', '')).lower()
        if "FİLİZ" in tip or "FILIZ" in tip.upper():
            return "#ffebee"  # Kırmızı açık
        elif "etr" in detay:
            return "#e8f5e9"  # Yeşil açık
        elif any(x in detay for x in ["ila", "İlave", "dağ", "göv", "gov"]):
            return "#fff3e0"  # Turuncu açık
        elif any(x in detay for x in ["mon", "pil", "üst", "ust"]):
            return "#e3f2fd"  # Mavi açık
        return "#e3f2fd"  # Mavi açık (varsayılan)

    def update_style(self):
        color = self._get_color()
        self.setStyleSheet(f"""
            DonatiKarti {{
                background-color: {color};
                border: 2px solid #bdc3c7;
                border-radius: 8px;
            }}
            DonatiKarti:hover {{
                border: 2px solid #3498db;
                background-color: #ecf0f1;
            }}
        """)

    def mousePressEvent(self, event):
        """Tıklama ile tip değiştir"""
        detay = str(self.demir.get('Detay', '')).lower()

        # Etriyelere dokunma
        if "etr" in detay:
            QMessageBox.warning(self, "Uyarı", "Etriyeler değiştirilemez!")
            return

        # Toggle: Filiz <-> Kiriş
        eski_tip = self.demir['Tip']
        if "FİLİZ" in eski_tip or "FILIZ" in eski_tip.upper():
            self.demir['Tip'] = "KİRİŞ DONATISI"
            self.demir['Eleman'] = "KİRİŞ"
            self.demir['Detay'] = "Manuel (Kiriş Yapıldı)"
        else:
            self.demir['Tip'] = "KOLON FİLİZİ"
            self.demir['Eleman'] = "KOLON FİLİZİ"
            self.demir['Detay'] = "Manuel (Filiz Yapıldı)"

        # UI güncelle
        self.lbl_icon.setText(self._get_icon())
        self.lbl_detay.setText(f"({self.demir.get('Detay', '')[:20]})")
        self.update_style()

        if self.parent_editor:
            self.parent_editor.log_degisiklik(self.demir, eski_tip)


class DemirGorselEditor(QWidget):
    """Gelişmiş Görsel Demir Editörü - Eleman Bazlı Kontrol Paneli"""

    def __init__(self, demir_listesi, parent=None):
        super().__init__(parent)
        self.demirler = demir_listesi
        self.parent_window = parent
        self.secili_eleman = None
        self.degisiklik_sayisi = 0
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)

        # ========== ÜST BAR ==========
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2c3e50, stop:1 #34495e);
                border-radius: 8px;
            }
        """)
        header_layout = QHBoxLayout()

        title = QLabel("🏗️ DEMİR METRAJ KONTROL")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold; padding: 10px;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Eleman seçici
        lbl_eleman = QLabel("🧱 Eleman:")
        lbl_eleman.setStyleSheet("color: white; font-weight: bold;")
        header_layout.addWidget(lbl_eleman)
        self.cmb_eleman = self._create_combo()
        self.cmb_eleman.currentTextChanged.connect(self.eleman_degisti)
        header_layout.addWidget(self.cmb_eleman)

        header.setLayout(header_layout)
        main_layout.addWidget(header)

        # ========== ANA İÇERİK ==========
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # SOL PANEL - Plan ve Kesit
        left_panel = self._create_left_panel()
        content_splitter.addWidget(left_panel)

        # SAĞ PANEL - Donatı Listesi
        right_panel = self._create_right_panel()
        content_splitter.addWidget(right_panel)

        content_splitter.setSizes([400, 600])
        main_layout.addWidget(content_splitter, 1)

        # ========== ALT BİLGİ ==========
        info_bar = QLabel("ℹ️ Hatalı bir donatı tipini (🔴/🔵) üzerine tıklayarak değiştirebilirsiniz. Etriyeler (🟢) değiştirilemez.")
        info_bar.setStyleSheet("""
            QLabel {
                background-color: #ecf0f1;
                padding: 10px;
                border-radius: 5px;
                color: #7f8c8d;
                font-style: italic;
            }
        """)
        info_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(info_bar)

        # ========== BUTONLAR ==========
        btn_layout = QHBoxLayout()

        self.lbl_degisiklik = QLabel("Değişiklik: 0")
        self.lbl_degisiklik.setStyleSheet("color: #7f8c8d; padding: 5px;")
        btn_layout.addWidget(self.lbl_degisiklik)

        btn_layout.addStretch()

        btn_iptal = QPushButton("❌ İPTAL")
        btn_iptal.clicked.connect(self.iptal)
        btn_iptal.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 12px 30px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        btn_layout.addWidget(btn_iptal)

        btn_kaydet = QPushButton("✅ KAYDET VE UYGULA")
        btn_kaydet.clicked.connect(self.kaydet_ve_uygula)
        btn_kaydet.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 12px 30px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #229954; }
        """)
        btn_layout.addWidget(btn_kaydet)

        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

        # Elemanları yükle
        self._yukle_elemanlar()

    def _create_combo(self):
        combo = QComboBox()
        combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                padding: 8px 15px;
                border: 2px solid #3498db;
                border-radius: 5px;
                min-width: 200px;
                font-weight: bold;
            }
            QComboBox:hover { border-color: #2980b9; }
            QComboBox::drop-down { border: none; padding-right: 10px; }
        """)
        return combo

    def _create_left_panel(self):
        """Sol panel - Plan görünümü ve lejant"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Plan başlığı
        plan_title = QLabel(".:: ELEMAN PLANI VE KESİTİ ::.")
        plan_title.setStyleSheet("font-weight: bold; color: #2c3e50; padding: 5px;")
        plan_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(plan_title)

        # Matplotlib canvas (basit plan çizimi)
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(5, 4), facecolor='#fafafa')
            self.canvas = FigureCanvas(self.figure)
            self.ax = self.figure.add_subplot(111)
            layout.addWidget(self.canvas, 1)
        else:
            placeholder = QLabel("Matplotlib yüklü değil\nPlan görünümü için:\npip install matplotlib")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: #95a5a6; padding: 50px;")
            layout.addWidget(placeholder, 1)

        # Lejant
        lejant = QGroupBox("DONATI LEJANTI")
        lejant.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 10px;
                padding: 10px;
            }
        """)
        lejant_layout = QVBoxLayout()

        lejant_items = [
            ("🔴", "FİLİZ (Kolon/Perde)", "#e74c3c"),
            ("🔵", "ÜST/PİLYE (Üst Donatı)", "#3498db"),
            ("🔵", "MONTAJ (Alt Donatı)", "#2980b9"),
            ("🟠", "GÖVDE/DAĞITMA", "#e67e22"),
            ("🟠", "İLAVE (Ek Donatı)", "#f39c12"),
            ("🟢", "ETRİYE (Sargı)", "#27ae60"),
        ]

        for icon, text, color in lejant_items:
            row = QHBoxLayout()
            lbl_icon = QLabel(icon)
            lbl_icon.setFixedWidth(25)
            row.addWidget(lbl_icon)
            lbl_text = QLabel(text)
            lbl_text.setStyleSheet(f"color: {color}; font-weight: bold;")
            row.addWidget(lbl_text)
            row.addStretch()
            lejant_layout.addLayout(row)

        lejant.setLayout(lejant_layout)
        layout.addWidget(lejant)

        panel.setLayout(layout)
        return panel

    def _create_right_panel(self):
        """Sağ panel - Kategorize donatı listesi"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Başlık
        list_title = QLabel(".:: DONATI AÇILIMLARI ::.")
        list_title.setStyleSheet("font-weight: bold; color: #2c3e50; padding: 5px;")
        list_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(list_title)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: #fafafa;
            }
        """)

        self.donati_container = QWidget()
        self.donati_layout = QVBoxLayout()
        self.donati_layout.setSpacing(5)
        self.donati_container.setLayout(self.donati_layout)

        scroll.setWidget(self.donati_container)
        layout.addWidget(scroll, 1)

        # Özet
        self.lbl_ozet = QLabel("Toplam: 0 adet | 0.00 kg")
        self.lbl_ozet.setStyleSheet("""
            QLabel {
                background-color: #3498db;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
        """)
        self.lbl_ozet.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_ozet)

        panel.setLayout(layout)
        return panel

    def _yukle_elemanlar(self):
        """Benzersiz eleman isimlerini combo'ya yükle"""
        elemanlar = set()
        for d in self.demirler:
            eleman = d.get('Kiriş/Temel', 'GENEL')
            if eleman:
                elemanlar.add(eleman)

        # Sayısal sırala
        def siralama_key(x):
            match = re.match(r"([A-Za-z]+)(\d+)", str(x))
            if match:
                return (match.group(1), int(match.group(2)))
            return (x, 0)

        sirali = sorted(elemanlar, key=siralama_key)

        self.cmb_eleman.clear()
        self.cmb_eleman.addItem("-- Tüm Elemanlar --")
        for e in sirali:
            self.cmb_eleman.addItem(e)

        if sirali:
            self.cmb_eleman.setCurrentIndex(1)  # İlk elemanı seç

    def eleman_degisti(self, eleman_ismi):
        """Eleman seçildiğinde donatıları güncelle"""
        self.secili_eleman = eleman_ismi if eleman_ismi != "-- Tüm Elemanlar --" else None
        self._goster_donatilari()
        self._ciz_plan()

    def _goster_donatilari(self):
        """Seçili elemana ait donatıları kategorize göster"""
        # Eski kartları temizle
        while self.donati_layout.count():
            item = self.donati_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Filtrele
        if self.secili_eleman:
            filtreli = [d for d in self.demirler if d.get('Kiriş/Temel') == self.secili_eleman]
        else:
            filtreli = self.demirler

        if not filtreli:
            empty_label = QLabel("Bu elemana ait donatı bulunamadı.")
            empty_label.setStyleSheet("color: #95a5a6; padding: 20px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.donati_layout.addWidget(empty_label)
            self.lbl_ozet.setText("Toplam: 0 adet | 0.00 kg")
            return

        # Kategorize et (detaylı)
        kategoriler = {
            "🔴 FİLİZLER (Kolon/Perde)": [],
            "🔵 ÜST DONATILAR (Pilye)": [],
            "🔵 MONTAJ DONATILARI (Alt)": [],
            "🟠 GÖVDE / DAĞITMA": [],
            "🟠 İLAVE DONATILAR": [],
            "🟢 ETRİYELER": [],
            "🔵 DİĞER KİRİŞ DONATILARI": [],
        }

        for i, d in enumerate(self.demirler):
            if self.secili_eleman and d.get('Kiriş/Temel') != self.secili_eleman:
                continue

            tip = d.get('Tip', '')
            detay = str(d.get('Detay', '')).lower()

            if "FİLİZ" in tip or "FILIZ" in tip.upper():
                kategoriler["🔴 FİLİZLER (Kolon/Perde)"].append((i, d))
            elif "etr" in detay:
                kategoriler["🟢 ETRİYELER"].append((i, d))
            elif any(x in detay for x in ["pil", "üst", "ust"]):
                kategoriler["🔵 ÜST DONATILAR (Pilye)"].append((i, d))
            elif "mon" in detay or "alt" in detay:
                kategoriler["🔵 MONTAJ DONATILARI (Alt)"].append((i, d))
            elif any(x in detay for x in ["göv", "gov", "dağ", "dag"]):
                kategoriler["🟠 GÖVDE / DAĞITMA"].append((i, d))
            elif any(x in detay for x in ["ila", "İlave"]):
                kategoriler["🟠 İLAVE DONATILAR"].append((i, d))
            else:
                kategoriler["🔵 DİĞER KİRİŞ DONATILARI"].append((i, d))

        # Göster
        toplam_adet = 0
        toplam_agirlik = 0

        for kategori, items in kategoriler.items():
            if not items:
                continue

            # Kategori başlığı
            header = QLabel(f"{kategori} ({len(items)} adet)")
            header.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    color: #2c3e50;
                    padding: 8px;
                    background-color: #ecf0f1;
                    border-radius: 5px;
                    margin-top: 5px;
                }
            """)
            self.donati_layout.addWidget(header)

            # Donatı kartları
            for idx, demir in items:
                kart = DonatiKarti(demir, idx, self)
                self.donati_layout.addWidget(kart)
                toplam_adet += demir.get('Adet', 1)
                toplam_agirlik += demir.get('Ağırlık (kg)', 0)

        self.donati_layout.addStretch()
        self.lbl_ozet.setText(f"Toplam: {toplam_adet} adet | {toplam_agirlik:.2f} kg")

    def _ciz_plan(self):
        """Basit plan görünümü çiz"""
        if not MATPLOTLIB_AVAILABLE:
            return

        self.ax.clear()
        self.ax.set_facecolor('#fafafa')
        self.ax.set_aspect('equal')

        # Filtrele
        if self.secili_eleman:
            filtreli = [d for d in self.demirler if d.get('Kiriş/Temel') == self.secili_eleman and 'p' in d]
        else:
            filtreli = [d for d in self.demirler if 'p' in d]

        if not filtreli:
            self.ax.text(0.5, 0.5, "Veri yok", ha='center', va='center', transform=self.ax.transAxes)
            self.canvas.draw()
            return

        # Koordinatları topla
        colors = []
        xs = []
        ys = []
        labels = []

        for d in filtreli:
            xs.append(d['p'].x)
            ys.append(d['p'].y)

            tip = d.get('Tip', '')
            detay = str(d.get('Detay', '')).lower()

            if "FİLİZ" in tip or "FILIZ" in tip.upper():
                colors.append('red')
            elif "etr" in detay:
                colors.append('green')
            elif "ila" in detay:
                colors.append('orange')
            else:
                colors.append('blue')

            poz = d.get('Poz', '').split()[0] if d.get('Poz') else ''
            labels.append(poz)

        # Scatter plot
        self.ax.scatter(xs, ys, c=colors, s=100, alpha=0.8, edgecolors='black', zorder=5)

        # Etiketler
        for x, y, label in zip(xs, ys, labels):
            self.ax.annotate(label, (x, y), textcoords="offset points",
                           xytext=(0, 8), ha='center', fontsize=8)

        # Başlık
        title = self.secili_eleman if self.secili_eleman else "Tüm Elemanlar"
        self.ax.set_title(title, fontsize=11, fontweight='bold')
        self.ax.grid(True, linestyle=':', alpha=0.5)

        self.figure.tight_layout()
        self.canvas.draw()

    def log_degisiklik(self, demir, eski_tip):
        """Değişikliği logla"""
        self.degisiklik_sayisi += 1
        self.lbl_degisiklik.setText(f"Değişiklik: {self.degisiklik_sayisi}")
        self.lbl_degisiklik.setStyleSheet("color: #e74c3c; font-weight: bold; padding: 5px;")

        if self.parent_window:
            poz = demir.get('Poz', '').split()[0] if demir.get('Poz') else '?'
            self.parent_window.log(f"Değiştirildi: {poz} | {eski_tip} -> {demir['Tip']}", "success")

    def iptal(self):
        """Değişiklikleri iptal et"""
        if self.degisiklik_sayisi > 0:
            cevap = QMessageBox.question(
                self, "İptal",
                f"{self.degisiklik_sayisi} değişiklik iptal edilecek. Emin misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if cevap != QMessageBox.StandardButton.Yes:
                return

        if self.parent_window:
            self.parent_window.log("Değişiklikler iptal edildi.", "warning")

        # Yeniden yükle (orijinal verilere dön)
        self.degisiklik_sayisi = 0
        self.lbl_degisiklik.setText("Değişiklik: 0")
        self.lbl_degisiklik.setStyleSheet("color: #7f8c8d; padding: 5px;")

    def kaydet_ve_uygula(self):
        """Değişiklikleri kaydet ve uygula"""
        if self.parent_window:
            self.parent_window.demir_verileri = self.demirler
            self.parent_window.sonuclari_goster()
            self.parent_window.log(f"✅ {self.degisiklik_sayisi} değişiklik uygulandı!", "success")

        QMessageBox.information(
            self, "Başarılı",
            f"{self.degisiklik_sayisi} değişiklik tablolara uygulandı!\n\n"
            "Excel'e aktararak son halini kaydedebilirsiniz."
        )

        self.degisiklik_sayisi = 0
        self.lbl_degisiklik.setText("Değişiklik: 0")
        self.lbl_degisiklik.setStyleSheet("color: #27ae60; padding: 5px;")


# =============================================================================
# ANA PENCERE
# =============================================================================

class SahaDemiriWindow(QWidget):
    """Saha Demiri - V5.0 Mıknatıs + Görsel Teyit Penceresi"""

    def __init__(self, db=None):
        super().__init__()
        self.db = db
        self.dxf_dosya_yolu = None
        self.doc = None
        self.layer_ayarlari = DEFAULT_LAYERS.copy()
        self.bulunan_layerlar = []
        self.demir_verileri = []
        self.df_detay = None
        self.df_ozet = None
        self.gorsel_editor = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)

        layout.addWidget(self._create_title())
        layout.addWidget(self._create_file_section())

        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self._create_settings_tab(), "Ayarlar & Layer Analizi")
        self.tab_widget.addTab(self._create_results_tab(), "Demir Hesap Sonuçları")

        # Görsel Editör Sekmesi (Matplotlib varsa)
        if MATPLOTLIB_AVAILABLE:
            self.gorsel_tab = QWidget()
            self.gorsel_tab_layout = QVBoxLayout()
            placeholder = QLabel("Önce 'DEMİR HESAPLA' yapın, sonra 'GÖRSEL KONTROL' açılacak.")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: #7f8c8d; font-style: italic; padding: 50px;")
            self.gorsel_tab_layout.addWidget(placeholder)
            self.gorsel_tab.setLayout(self.gorsel_tab_layout)
            self.tab_widget.addTab(self.gorsel_tab, "Görsel Kontrol")

        layout.addWidget(self.tab_widget, 1)
        layout.addWidget(self._create_log_section())

        self.setLayout(layout)

    def _create_title(self) -> QLabel:
        title = QLabel("SAHA DEMİRİ HESABI (V5.0 - MIKNATIS + GÖRSEL TEYİT)")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: white;
                padding: 12px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e74c3c, stop:1 #c0392b);
                border-radius: 6px;
            }
        """)
        return title

    def _create_file_section(self) -> QGroupBox:
        group = QGroupBox("DXF Dosyası ve İşlemler")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        layout = QHBoxLayout()

        self.txt_dosya = QLineEdit()
        self.txt_dosya.setPlaceholderText("DXF dosyası seçin...")
        self.txt_dosya.setReadOnly(True)

        btn_sec = QPushButton("Dosya Seç")
        btn_sec.clicked.connect(self.dosya_sec)
        btn_sec.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)

        self.btn_tara = QPushButton("Layerları Tara")
        self.btn_tara.clicked.connect(self.layerlari_tara)
        self.btn_tara.setEnabled(False)
        self.btn_tara.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)

        self.btn_hesapla = QPushButton("DEMİR HESAPLA")
        self.btn_hesapla.clicked.connect(self.demir_hesapla_baslat)
        self.btn_hesapla.setEnabled(False)
        self.btn_hesapla.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 8px 25px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)

        self.btn_excel = QPushButton("Excel'e Aktar")
        self.btn_excel.clicked.connect(self.excel_aktar)
        self.btn_excel.setEnabled(False)
        self.btn_excel.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)

        layout.addWidget(QLabel("Dosya:"))
        layout.addWidget(self.txt_dosya, 1)
        layout.addWidget(btn_sec)
        layout.addWidget(self.btn_tara)
        layout.addWidget(self.btn_hesapla)
        layout.addWidget(self.btn_excel)

        group.setLayout(layout)
        return group

    def _create_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout()

        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self._create_layer_settings())
        left_layout.addWidget(self._create_miknatis_settings())
        left_widget.setLayout(left_layout)

        right_widget = self._create_analysis_section()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])

        layout.addWidget(splitter)
        widget.setLayout(layout)
        return widget

    def _create_miknatis_settings(self) -> QGroupBox:
        group = QGroupBox("Mıknatıs Ayarları (Kolon Filizi Tespiti)")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e74c3c;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)

        layout = QVBoxLayout()

        info = QLabel("Bir demir yazısı, kolon ismine bu mesafeden yakınsa FİLİZ sayılır:")
        info.setStyleSheet("color: #7f8c8d; font-style: italic;")
        info.setWordWrap(True)
        layout.addWidget(info)

        row = QHBoxLayout()
        row.addWidget(QLabel("Mıknatıs Mesafesi (cm):"))

        self.spin_miknatis = QDoubleSpinBox()
        self.spin_miknatis.setRange(10.0, 500.0)
        self.spin_miknatis.setValue(DEFAULT_MIKNATIS_MESAFESI)
        self.spin_miknatis.setSuffix(" cm")
        self.spin_miknatis.setDecimals(1)
        row.addWidget(self.spin_miknatis)
        row.addStretch()

        layout.addLayout(row)

        # Bağımlılık uyarısı
        if not PANDAS_AVAILABLE:
            warn = QLabel("Eksik: pandas (pip install pandas openpyxl)")
            warn.setStyleSheet("color: #e74c3c; font-weight: bold;")
            layout.addWidget(warn)

        if not MATPLOTLIB_AVAILABLE:
            warn2 = QLabel("Görsel editör için: pip install matplotlib")
            warn2.setStyleSheet("color: #f39c12;")
            layout.addWidget(warn2)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def _create_layer_settings(self) -> QGroupBox:
        group = QGroupBox("Layer Protokolü (Eşleştirme)")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #9b59b6;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)

        layout = QVBoxLayout()

        info = QLabel("DXF'teki hangi layer'ın ne anlama geldiğini belirleyin:")
        info.setStyleSheet("color: #7f8c8d; font-style: italic;")
        layout.addWidget(info)

        self.layer_inputs = {}

        for key, default_value in DEFAULT_LAYERS.items():
            row = QHBoxLayout()
            color_label = QLabel("●")
            color_label.setStyleSheet(f"color: {LAYER_COLORS.get(key, '#333')}; font-size: 16px;")
            row.addWidget(color_label)

            label = QLabel(f"{key}:")
            label.setFixedWidth(100)
            label.setStyleSheet("font-weight: bold;")
            row.addWidget(label)

            input_field = QLineEdit(default_value)
            input_field.setPlaceholderText(f"Örn: {default_value}")
            self.layer_inputs[key] = input_field
            row.addWidget(input_field, 1)

            layout.addLayout(row)

        btn_uygula = QPushButton("Ayarları Uygula")
        btn_uygula.clicked.connect(self.ayarlari_uygula)
        btn_uygula.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                padding: 10px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover { background-color: #8e44ad; }
        """)
        layout.addWidget(btn_uygula)

        group.setLayout(layout)
        return group

    def _create_analysis_section(self) -> QGroupBox:
        group = QGroupBox("DXF Layer Analizi")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #27ae60;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)

        layout = QVBoxLayout()

        self.tree_layers = QTreeWidget()
        self.tree_layers.setHeaderLabels(["Layer Adı", "Nesne Sayısı", "Durum"])
        self.tree_layers.setAlternatingRowColors(True)
        self.tree_layers.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_layers.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        layout.addWidget(self.tree_layers, 1)

        stats_layout = QHBoxLayout()
        self.lbl_toplam_layer = QLabel("Toplam Layer: 0")
        self.lbl_eslesen = QLabel("Eşleşen: 0")
        self.lbl_nesne = QLabel("Toplam Nesne: 0")

        for lbl in [self.lbl_toplam_layer, self.lbl_eslesen, self.lbl_nesne]:
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #ecf0f1;
                    padding: 8px 15px;
                    border-radius: 4px;
                    font-weight: bold;
                }
            """)
            stats_layout.addWidget(lbl)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        group.setLayout(layout)
        return group

    def _create_results_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        stats_group = QGroupBox("Özet İstatistikler")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        stats_layout = QHBoxLayout()

        self.lbl_toplam_demir = QLabel("Toplam Demir: 0 kg")
        self.lbl_kiris_donati = QLabel("Kiriş Donatısı: 0 kg")
        self.lbl_kolon_filizi = QLabel("Kolon Filizi: 0 kg")
        self.lbl_poz_sayisi = QLabel("Poz Sayısı: 0")

        for lbl in [self.lbl_toplam_demir, self.lbl_kiris_donati, self.lbl_kolon_filizi, self.lbl_poz_sayisi]:
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #ecf0f1;
                    padding: 10px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 12px;
                }
            """)
            stats_layout.addWidget(lbl)

        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        splitter = QSplitter(Qt.Orientation.Vertical)

        detay_group = QGroupBox("Detay Listesi")
        detay_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #27ae60;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        detay_layout = QVBoxLayout()

        self.tbl_detay = QTableWidget()
        self.tbl_detay.setColumnCount(10)
        self.tbl_detay.setHorizontalHeaderLabels([
            "Kat", "Kiriş/Temel", "Eleman", "Tip", "Detay", "Poz", "Çap", "Adet", "Boy (cm)", "Ağırlık (kg)"
        ])
        self.tbl_detay.setAlternatingRowColors(True)
        self.tbl_detay.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        detay_layout.addWidget(self.tbl_detay)
        detay_group.setLayout(detay_layout)
        splitter.addWidget(detay_group)

        ozet_group = QGroupBox("Özet (Kat/Eleman/Tip Bazlı)")
        ozet_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #f39c12;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        ozet_layout = QVBoxLayout()

        self.tbl_ozet = QTableWidget()
        self.tbl_ozet.setAlternatingRowColors(True)
        self.tbl_ozet.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        ozet_layout.addWidget(self.tbl_ozet)
        ozet_group.setLayout(ozet_layout)
        splitter.addWidget(ozet_group)

        splitter.setSizes([400, 300])
        layout.addWidget(splitter, 1)

        widget.setLayout(layout)
        return widget

    def _create_log_section(self) -> QGroupBox:
        group = QGroupBox("İşlem Günlüğü")
        layout = QVBoxLayout()

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(120)
        self.txt_log.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #2ecc71;
                font-family: Consolas, monospace;
                font-size: 11px;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.txt_log)

        group.setLayout(layout)
        return group

    def log(self, mesaj: str, tip: str = "info"):
        renk = {
            "info": "#2ecc71",
            "warning": "#f39c12",
            "error": "#e74c3c",
            "success": "#3498db"
        }.get(tip, "#2ecc71")
        self.txt_log.append(f'<span style="color: {renk};">[{tip.upper()}] {mesaj}</span>')

    def dosya_sec(self):
        dosya, _ = QFileDialog.getOpenFileName(
            self, "DXF Dosyası Seç", "", "DXF Dosyaları (*.dxf);;Tüm Dosyalar (*.*)"
        )
        if dosya:
            self.dxf_dosya_yolu = dosya
            self.txt_dosya.setText(dosya)
            self.btn_tara.setEnabled(True)
            self.log(f"Dosya seçildi: {os.path.basename(dosya)}", "info")

    def ayarlari_uygula(self):
        for key, input_field in self.layer_inputs.items():
            self.layer_ayarlari[key] = input_field.text().strip()
        self.log("Layer protokolü güncellendi", "success")
        if self.doc:
            self.analiz_yap()

    def layerlari_tara(self):
        if not self.dxf_dosya_yolu:
            QMessageBox.warning(self, "Uyarı", "Önce bir DXF dosyası seçin!")
            return
        try:
            self.log("DXF dosyası okunuyor...", "info")
            self.doc = ezdxf.readfile(self.dxf_dosya_yolu)
            self.log("Dosya başarıyla okundu", "success")
            self.analiz_yap()
            self.btn_hesapla.setEnabled(True)
        except Exception as e:
            self.log(f"Dosya okuma hatası: {str(e)}", "error")
            QMessageBox.critical(self, "Hata", f"DXF dosyası okunamadı:\n{str(e)}")

    def analiz_yap(self):
        if not self.doc:
            return
        self.tree_layers.clear()
        self.bulunan_layerlar = []
        msp = self.doc.modelspace()

        layer_stats = {}
        for entity in msp:
            layer_name = entity.dxf.layer
            if layer_name not in layer_stats:
                layer_stats[layer_name] = {'count': 0, 'types': set()}
            layer_stats[layer_name]['count'] += 1
            layer_stats[layer_name]['types'].add(entity.dxftype())

        eslesen_sayisi = 0
        toplam_nesne = 0

        matched_root = QTreeWidgetItem(self.tree_layers, ["EŞLEŞTİRİLEN LAYERLAR", "", ""])
        matched_root.setExpanded(True)
        matched_root.setBackground(0, QColor("#d5f5e3"))

        other_root = QTreeWidgetItem(self.tree_layers, ["DİĞER LAYERLAR", "", ""])
        other_root.setExpanded(True)
        other_root.setBackground(0, QColor("#fdebd0"))

        for layer_name, stats in sorted(layer_stats.items()):
            toplam_nesne += stats['count']
            eslesme = None
            for key, value in self.layer_ayarlari.items():
                if value.upper() == layer_name.upper():
                    eslesme = key
                    eslesen_sayisi += 1
                    break

            if eslesme:
                parent = matched_root
                durum = f"✓ {eslesme}"
                item = QTreeWidgetItem(parent, [layer_name, str(stats['count']), durum])
                item.setForeground(2, QColor("#27ae60"))
                item.setBackground(0, QColor("#eafaf1"))
            else:
                parent = other_root
                durum = "-"
                item = QTreeWidgetItem(parent, [layer_name, str(stats['count']), durum])

            for entity_type in sorted(stats['types']):
                type_item = QTreeWidgetItem(item, [f"  └ {entity_type}", "", ""])
                type_item.setForeground(0, QColor("#7f8c8d"))

            self.bulunan_layerlar.append(layer_name)

        self.lbl_toplam_layer.setText(f"Toplam Layer: {len(layer_stats)}")
        self.lbl_eslesen.setText(f"Eşleşen: {eslesen_sayisi}")
        self.lbl_nesne.setText(f"Toplam Nesne: {toplam_nesne}")
        self.log(f"Analiz tamamlandı: {len(layer_stats)} layer, {eslesen_sayisi} eşleşme", "success")

    def demir_hesapla_baslat(self):
        if not self.doc:
            QMessageBox.warning(self, "Uyarı", "Önce bir DXF dosyası yükleyin!")
            return

        if not PANDAS_AVAILABLE:
            QMessageBox.critical(self, "Hata", "Pandas kütüphanesi yüklü değil!\npip install pandas openpyxl")
            return

        try:
            self.log("Mıknatıs mantığıyla demir hesabı başlatılıyor...", "info")
            self.demir_hesapla()
            self.sonuclari_goster()
            self.gorsel_editor_olustur()
            self.btn_excel.setEnabled(True)
            self.tab_widget.setCurrentIndex(1)
            self.log("Demir hesabı tamamlandı!", "success")
        except Exception as e:
            self.log(f"Hesaplama hatası: {str(e)}", "error")
            QMessageBox.critical(self, "Hata", f"Demir hesabı yapılamadı:\n{str(e)}")

    def demir_hesapla(self):
        """V5.0 - MIKNATIS/PROXIMITY MANTIĞIYLA DEMİR HESAPLAMA"""
        msp = self.doc.modelspace()
        miknatis_mesafesi = self.spin_miknatis.value()
        self.demir_verileri = []

        # 1. BÖLGELERİ TARA
        self.log("1/3: Kiriş kutuları ve Katlar taranıyor...", "info")
        kat_kutulari = []
        kiris_kutulari = []

        kat_layer = self.layer_ayarlari.get("KAT_SINIRI", "H_KAT")
        for e in msp.query(f'LWPOLYLINE[layer=="{kat_layer}"]'):
            p = geometri_olustur(e)
            if p:
                kat_kutulari.append({'poly': p, 'isim': 'TANIMSIZ'})

        kat_ismi_layer = self.layer_ayarlari.get("KAT_ISMI", "A_KAT_ISMI")
        for e in msp.query(f'TEXT MTEXT[layer=="{kat_ismi_layer}"]'):
            t = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            pt = Point(e.dxf.insert.x, e.dxf.insert.y)
            for kat in kat_kutulari:
                if kat['poly'].contains(pt):
                    kat['isim'] = t.strip().upper()
                    break

        kiris_layer = self.layer_ayarlari.get("KIRIS", "H_KIRIS")
        for e in msp.query(f'LWPOLYLINE[layer=="{kiris_layer}"]'):
            p = geometri_olustur(e)
            if p:
                kiris_kutulari.append({'poly': p, 'kolonlar': [], 'isim': 'TANIMSIZ'})

        self.log(f"Bulunan: {len(kat_kutulari)} kat, {len(kiris_kutulari)} kiriş kutusu", "info")

        # 2. KOLON VE KİRİŞ İSİMLERİNİ BUL
        self.log("2/3: Kolon (S/SZ) ve Kiriş/Temel (T/K) isimleri bulunuyor...", "info")
        tum_yazilar = []
        tum_kiris_isimleri = []  # Tüm kiriş/temel isimleri ve koordinatları

        for e in msp.query('TEXT MTEXT'):
            txt = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            txt_clean = txt.upper().replace("\n", " ").strip()
            pt = Point(e.dxf.insert.x, e.dxf.insert.y)

            # Kolon ismi mi? (SZ16, S1 vb.)
            if re.search(REGEX_KOLON_ISMI, txt_clean):
                for kiris in kiris_kutulari:
                    if kiris['poly'].contains(pt):
                        kiris['kolonlar'].append({'isim': txt_clean, 'p': pt})
                        break

            # Kiriş/Temel ismi mi? (T19, K1, MK5 vb.)
            elif re.search(REGEX_KIRIS_ISMI, txt_clean):
                kiris_ismi = re.search(REGEX_KIRIS_ISMI, txt_clean).group(0)
                # Tüm kiriş isimlerini listeye ekle (koordinatlarıyla)
                tum_kiris_isimleri.append({'isim': kiris_ismi, 'p': pt, 'tam_yazi': txt_clean})
                # Ayrıca kutulara da ata
                for kiris in kiris_kutulari:
                    if kiris['poly'].contains(pt):
                        kiris['isim'] = kiris_ismi
                        break
            else:
                tum_yazilar.append({'text': txt_clean, 'p': pt})

        kolon_sayisi = sum(len(k['kolonlar']) for k in kiris_kutulari)
        self.log(f"Bulunan: {kolon_sayisi} kolon, {len(tum_kiris_isimleri)} kiriş/temel ismi, {len(tum_yazilar)} potansiyel demir", "info")

        # 3. DEMİRLERİ ANALİZ ET
        self.log("3/3: Demirler analiz ediliyor (Mıknatıs + ETR Koruması)...", "info")

        for veri in tum_yazilar:
            match = re.search(REGEX_DEMIR, veri['text'])
            if match:
                adet = int(match.group(1))
                cap = int(match.group(2))
                boy = int(match.group(3))

                if cap not in AGIRLIKLAR:
                    continue

                p_demir = veri['p']
                txt = veri['text']

                aktif_kiris = None
                kiris_ismi = "GENEL"
                for kiris in kiris_kutulari:
                    if kiris['poly'].contains(p_demir):
                        aktif_kiris = kiris
                        kiris_ismi = kiris.get('isim', 'TANIMSIZ')
                        break

                kat_adi = "GENEL"
                for kat in kat_kutulari:
                    if kat['poly'].contains(p_demir):
                        kat_adi = kat['isim']
                        break

                # En yakın kiriş/temel ismini bul (mesafe bazlı)
                if kiris_ismi == "TANIMSIZ" or kiris_ismi == "GENEL":
                    en_yakin_kiris_mesafe = 99999
                    en_yakin_kiris_ismi = None
                    for ki in tum_kiris_isimleri:
                        mesafe = mesafe_hesapla(p_demir, ki['p'])
                        if mesafe < en_yakin_kiris_mesafe:
                            en_yakin_kiris_mesafe = mesafe
                            en_yakin_kiris_ismi = ki['isim']

                    # Belirli bir mesafe içindeyse (2000 birim = DXF ölçeğinde yaklaşık 20m) o kirişe ata
                    if en_yakin_kiris_ismi and en_yakin_kiris_mesafe < 2000:
                        kiris_ismi = en_yakin_kiris_ismi
                    elif "TEMEL" in kat_adi:
                        kiris_ismi = "TEMEL (Genel)"
                    else:
                        kiris_ismi = "KİRİŞ (Genel)"

                # Varsayılan değerler
                tip = "KİRİŞ DONATISI"
                detay = "Genel Donatı"

                # Yeni gelişmiş tip algılama
                tip_kodu, tip_aciklama = donati_tipi_bul(txt)

                if tip_kodu == "ETRIYE":
                    tip, detay = "KİRİŞ DONATISI", tip_aciklama
                elif tip_kodu == "ILAVE":
                    tip, detay = "KİRİŞ DONATISI", tip_aciklama
                elif tip_kodu == "GOVDE":
                    tip, detay = "KİRİŞ DONATISI", tip_aciklama
                elif tip_kodu == "DAGITMA":
                    tip, detay = "KİRİŞ DONATISI", tip_aciklama
                elif tip_kodu == "MONTAJ":
                    tip, detay = "KİRİŞ DONATISI", tip_aciklama
                elif tip_kodu == "PILYE":
                    tip, detay = "KİRİŞ DONATISI", tip_aciklama
                elif aktif_kiris:
                    # Mıknatıs Kontrolü (sadece kiriş kutusundaysa)
                    detay = "Montaj/Pilye"
                    en_yakin = 99999
                    for kolon in aktif_kiris['kolonlar']:
                        mesafe = mesafe_hesapla(p_demir, kolon['p'])
                        if mesafe < en_yakin:
                            en_yakin = mesafe

                    if en_yakin <= miknatis_mesafesi:
                        tip = "KOLON FİLİZİ"
                        detay = f"Mıknatıs ({int(en_yakin)}cm)"

                # Eleman ismi belirle
                if "TEMEL" in kat_adi:
                    eleman = "TEMEL DONATISI"
                elif tip == "KOLON FİLİZİ":
                    eleman = "KOLON FİLİZİ"
                else:
                    eleman = "KİRİŞ"

                # Ağırlık hesapla ve kaydet
                agirlik = (adet * boy / 100) * AGIRLIKLAR[cap]
                self.demir_verileri.append({
                    "Kat": kat_adi,
                    "Kiriş/Temel": kiris_ismi,
                    "Eleman": eleman,
                    "Tip": tip,
                    "Detay": detay,
                    "Poz": txt,
                    "Çap": f"Ø{cap}",
                    "Adet": adet,
                    "Boy (cm)": boy,
                    "Ağırlık (kg)": round(agirlik, 2),
                    "p": p_demir  # Görsel editör için
                })

        # Bulunan kiriş isimlerini say
        kiris_isimleri_set = set(d["Kiriş/Temel"] for d in self.demir_verileri)
        self.log(f"Hesaplama tamamlandı: {len(self.demir_verileri)} demir kaydı, {len(kiris_isimleri_set)} farklı kiriş/temel", "success")
        self.log(f"Bulunan kiriş/temel isimleri: {', '.join(sorted(kiris_isimleri_set)[:10])}{'...' if len(kiris_isimleri_set) > 10 else ''}", "info")

    def gorsel_editor_olustur(self):
        """Görsel editör sekmesini oluştur"""
        if not MATPLOTLIB_AVAILABLE:
            return
        if not self.demir_verileri:
            return

        # Eski widget'ları temizle
        while self.gorsel_tab_layout.count():
            item = self.gorsel_tab_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Yeni editör oluştur
        self.gorsel_editor = DemirGorselEditor(self.demir_verileri, parent=self)
        self.gorsel_tab_layout.addWidget(self.gorsel_editor)

    def sonuclari_goster(self):
        if not self.demir_verileri:
            self.log("Gösterilecek demir verisi yok!", "warning")
            return

        # DataFrame için 'p' sütununu çıkar
        df_data = [{k: v for k, v in d.items() if k != 'p'} for d in self.demir_verileri]
        self.df_detay = pd.DataFrame(df_data)

        # Kiriş/Temel ismine göre sayısal sırala (T1, T2, T10, T19, T20 şeklinde)
        def siralama_key(x):
            kiris = x["Kiriş/Temel"]
            match = re.match(r"([A-Za-z]+)(\d+)", str(kiris))
            if match:
                return (x["Kat"], match.group(1), int(match.group(2)), x["Poz"])
            return (x["Kat"], kiris, 0, x["Poz"])

        sirali_veriler = sorted(self.demir_verileri, key=siralama_key)

        self.tbl_detay.setRowCount(len(sirali_veriler))
        for row, veri in enumerate(sirali_veriler):
            self.tbl_detay.setItem(row, 0, QTableWidgetItem(str(veri["Kat"])))
            self.tbl_detay.setItem(row, 1, QTableWidgetItem(str(veri["Kiriş/Temel"])))
            self.tbl_detay.setItem(row, 2, QTableWidgetItem(str(veri["Eleman"])))
            self.tbl_detay.setItem(row, 3, QTableWidgetItem(str(veri["Tip"])))
            self.tbl_detay.setItem(row, 4, QTableWidgetItem(str(veri["Detay"])))
            self.tbl_detay.setItem(row, 5, QTableWidgetItem(str(veri["Poz"])))
            self.tbl_detay.setItem(row, 6, QTableWidgetItem(str(veri["Çap"])))
            self.tbl_detay.setItem(row, 7, QTableWidgetItem(str(veri["Adet"])))
            self.tbl_detay.setItem(row, 8, QTableWidgetItem(str(veri["Boy (cm)"])))
            self.tbl_detay.setItem(row, 9, QTableWidgetItem(f"{veri['Ağırlık (kg)']:.2f}"))

            # Renklendirme
            if veri["Tip"] == "KOLON FİLİZİ":
                for col in range(10):
                    item = self.tbl_detay.item(row, col)
                    if item:
                        item.setBackground(QColor("#d5f5e3"))
            elif "Etriye" in veri.get("Detay", ""):
                for col in range(10):
                    item = self.tbl_detay.item(row, col)
                    if item:
                        item.setBackground(QColor("#e8f8f5"))

        try:
            self.df_ozet = self.df_detay.pivot_table(
                index=["Kat", "Kiriş/Temel", "Tip"],
                columns="Çap",
                values="Ağırlık (kg)",
                aggfunc="sum",
                fill_value=0,
                margins=True,
                margins_name="TOPLAM"
            )

            self.tbl_ozet.clear()
            self.tbl_ozet.setRowCount(len(self.df_ozet))
            self.tbl_ozet.setColumnCount(len(self.df_ozet.columns) + 1)

            headers = ["Kat / Eleman / Tip"] + [str(col) for col in self.df_ozet.columns]
            self.tbl_ozet.setHorizontalHeaderLabels(headers)

            for row, (idx, values) in enumerate(self.df_ozet.iterrows()):
                if isinstance(idx, tuple):
                    idx_str = " / ".join(str(x) for x in idx)
                else:
                    idx_str = str(idx)
                self.tbl_ozet.setItem(row, 0, QTableWidgetItem(idx_str))

                for col, val in enumerate(values):
                    item = QTableWidgetItem(f"{val:.2f}")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.tbl_ozet.setItem(row, col + 1, item)

                if "TOPLAM" in idx_str:
                    for col in range(self.tbl_ozet.columnCount()):
                        item = self.tbl_ozet.item(row, col)
                        if item:
                            item.setBackground(QColor("#f39c12"))
                            item.setForeground(QColor("white"))

        except Exception as e:
            self.log(f"Özet tablo hatası: {e}", "warning")

        toplam = self.df_detay["Ağırlık (kg)"].sum()
        kiris = self.df_detay[self.df_detay["Tip"] == "KİRİŞ DONATISI"]["Ağırlık (kg)"].sum()
        filiz = self.df_detay[self.df_detay["Tip"] == "KOLON FİLİZİ"]["Ağırlık (kg)"].sum()

        self.lbl_toplam_demir.setText(f"Toplam Demir: {toplam:,.2f} kg")
        self.lbl_kiris_donati.setText(f"Kiriş Donatısı: {kiris:,.2f} kg")
        self.lbl_kolon_filizi.setText(f"Kolon Filizi: {filiz:,.2f} kg")
        self.lbl_poz_sayisi.setText(f"Poz Sayısı: {len(self.demir_verileri)}")

    def _kiris_siralama_anahtari(self, kiris_ismi):
        """T1, T2, T10, T19 şeklinde doğru sayısal sıralama için anahtar"""
        import re
        match = re.match(r"([A-Za-z]+)(\d+)", str(kiris_ismi))
        if match:
            harf = match.group(1)
            sayi = int(match.group(2))
            return (harf, sayi)
        return (kiris_ismi, 0)

    def excel_aktar(self):
        if self.df_detay is None or len(self.df_detay) == 0:
            QMessageBox.warning(self, "Uyarı", "Aktarılacak veri yok!")
            return

        varsayilan_ad = "SAHA_DEMIRI_RAPORU.xlsx"
        if self.dxf_dosya_yolu:
            base = os.path.splitext(os.path.basename(self.dxf_dosya_yolu))[0]
            varsayilan_ad = f"{base}_SAHA_DEMIRI.xlsx"

        dosya, _ = QFileDialog.getSaveFileName(
            self, "Excel Dosyası Kaydet", varsayilan_ad, "Excel Dosyaları (*.xlsx)"
        )

        if not dosya:
            return

        try:
            with pd.ExcelWriter(dosya, engine='openpyxl') as writer:
                # 1. KİRİŞ BAZLI DETAY SAYFASI (Gruplanmış, Sayısal Sıralı)
                # Sayısal sıralama anahtarı ekle
                df_copy = self.df_detay.copy()
                df_copy['_siralama'] = df_copy['Kiriş/Temel'].apply(self._kiris_siralama_anahtari)
                df_sorted = df_copy.sort_values(by=["Kat", "_siralama", "Poz"])
                df_sorted = df_sorted.drop(columns=['_siralama'])
                df_sorted.to_excel(writer, sheet_name="Kiriş Bazlı Detay", index=False)

                # 2. KİRİŞ BAZLI ÖZET (Her kiriş için toplam)
                kiris_ozet = self.df_detay.groupby(["Kat", "Kiriş/Temel"]).agg({
                    "Ağırlık (kg)": "sum",
                    "Poz": "count"
                }).reset_index()
                kiris_ozet.columns = ["Kat", "Kiriş/Temel", "Toplam Ağırlık (kg)", "Poz Sayısı"]
                kiris_ozet = kiris_ozet.sort_values(by=["Kat", "Kiriş/Temel"])
                kiris_ozet.to_excel(writer, sheet_name="Kiriş Özet", index=False)

                # 3. ÇAP BAZLI PİVOT ÖZET
                if self.df_ozet is not None:
                    self.df_ozet.to_excel(writer, sheet_name="Çap Bazlı Özet")

                # 4. GENEL ÖZET
                genel_ozet = pd.DataFrame({
                    "Açıklama": [
                        "Toplam Demir Ağırlığı",
                        "Kiriş Donatısı",
                        "Kolon Filizi",
                        "Toplam Poz Sayısı",
                        "Kiriş/Temel Sayısı"
                    ],
                    "Değer": [
                        f"{self.df_detay['Ağırlık (kg)'].sum():,.2f} kg",
                        f"{self.df_detay[self.df_detay['Tip'] == 'KİRİŞ DONATISI']['Ağırlık (kg)'].sum():,.2f} kg",
                        f"{self.df_detay[self.df_detay['Tip'] == 'KOLON FİLİZİ']['Ağırlık (kg)'].sum():,.2f} kg",
                        len(self.df_detay),
                        self.df_detay["Kiriş/Temel"].nunique()
                    ]
                })
                genel_ozet.to_excel(writer, sheet_name="Genel Özet", index=False)

            self.log(f"Excel kaydedildi: {dosya}", "success")
            QMessageBox.information(self, "Başarılı",
                f"Rapor kaydedildi:\n{dosya}\n\n"
                f"Sayfalar:\n"
                f"1. Kiriş Bazlı Detay\n"
                f"2. Kiriş Özet\n"
                f"3. Çap Bazlı Özet\n"
                f"4. Genel Özet")

        except Exception as e:
            self.log(f"Excel hatası: {str(e)}", "error")
            QMessageBox.critical(self, "Hata", f"Excel kaydedilemedi:\n{str(e)}")
