"""
Başlangıç Ekranı — Modüler Paket Seçimi
QUANTIX PRO v2.0 — Ticari Lisans Modeli

Eski "Yüklenici / Alt Yüklenici" seçimi KALDIRILDI.
Yeni yapı: Kullanıcı 4 lisans paketinden birini seçer,
seçilen paket hangi modüllerin aktif olacağını belirler.
"""

from PyQt6.QtWidgets import (
QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
QLabel, QScrollArea, QWidget, QFrame, QSizePolicy,
QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPixmap, QColor, QCursor
from pathlib import Path


# ─── Paket Tanımları ────────────────────────────────────────────────────────

PACKAGES = [
{
'id': 'baslangic',
'name': 'BAŞLANGIÇ',
'price': '299₺',
'period': '/ ay',
'target': 'Usta · Küçük Taşeron\nYeni Başlayan Müteahhit',
'icon': '',
'color': '#27ae60',
'color_hover': '#2ecc71',
'modules': [
('', 'Metraj & Keşif (Temel)'),
('', '16 Maliyet Hesaplayıcı'),
('', '100+ Poz Veritabanı'),
('', '150+ Fire Oranı'),
('', '2026 Q1 Birim Fiyatlar'),
('', 'Proje Oluşturma & Yönetimi'),
('', 'Excel / PDF Export'),
('', 'Şablon Sistemi'),
('—', 'Demir Metraj & Donatım'),
('—', 'CAD & 3D Görselleştirme'),
('—', 'Gantt & İş Programı'),
('—', 'Teklif & Fatura'),
('—', 'Devlet İhalesi Araçları'),
('—', 'Saha & Puantaj API'),
('—', 'BI Dashboard & Analitik'),
],
},
{
'id': 'profesyonel',
'name': 'PROFESYONEL',
'price': '699₺',
'period': '/ ay',
'target': 'Orta Ölçekli Müteahhit\nTeknik Büro · Serbest Müh.',
'icon': '',
'color': '#2980b9',
'color_hover': '#3498db',
'badge': 'EN POPÜLER',
'modules': [
('', 'Başlangıç Paketi (Tamamı)'),
('', 'Metraj & Keşif (Gelişmiş)'),
('', 'Demir Metraj (5 Motor)'),
('', 'DXF Otomatik Metraj'),
('', 'AutoCAD COM + 6 LISP Rutini'),
('', '3D Görselleştirme (OpenGL)'),
('', 'Net / Brüt Alan Ayrımı'),
('', 'Çoklu Kat Yönetimi'),
('', 'Teklif Hazırlama'),
('', 'Fatura & Tahsilat Takibi'),
('', 'Gantt Chart + CPM'),
('', 'Serbest Piyasa Modu (90+ Öneri)'),
('—', 'Devlet İhalesi (4734/4735)'),
('—', 'Saha & Puantaj REST API'),
('—', 'BI Dashboard & Analitik'),
],
},
{
'id': 'ihale',
'name': 'İHALE',
'price': '1.099₺',
'period': '/ ay',
'target': 'Kamu İhalesi Firmaları\nBelediye · Bakanlık Müteahhitleri',
'icon': '',
'color': '#d35400',
'color_hover': '#e67e22',
'modules': [
('', 'Profesyonel Paket (Tamamı)'),
('', 'Yaklaşık Maliyet & Keşif'),
('', 'Hakediş Kesinti & Mahsup'),
('', 'SGK Asgari İşçilik'),
('', 'Fiyat Farkı (TÜİK D1/D2/D3)'),
('', 'Birim Fiyat Analiz Cetveli'),
('', 'Gecikme Cezası & Süre Uzatımı'),
('', 'Teminat Yönetimi (%3/%6)'),
('', 'Saha & Puantaj REST API'),
('', 'QR Hakediş Doğrulama'),
('', 'GPS Konum Kaydı'),
('', 'Mobil Erişim (PythonAnywhere)'),
('—', 'BI Dashboard & Analitik'),
('—', 'Sürdürülebilirlik & LEED'),
('—', 'CRM & Nakit Akış'),
],
},
{
'id': 'kurumsal',
'name': 'KURUMSAL',
'price': '1.799₺',
'period': '/ ay',
'target': 'Yapı Şirketi · Çok Projeli Firma\nYapı Denetim Kuruluşu',
'icon': '',
'color': '#6c3483',
'color_hover': '#8e44ad',
'badge': 'TAM PAKET',
'modules': [
('', 'İhale Paketi (Tamamı)'),
('', 'BI Dashboard (KPI + Trend)'),
('', 'Enflasyon Analizi (TCMB API)'),
('', 'Tedarikçi Yönetimi'),
('', 'Sürdürülebilirlik & LEED'),
('', 'Müşteri İlişkileri (CRM)'),
('', 'Nakit Akış Planlayıcısı'),
('', 'Proje Kâr/Zarar Analizi'),
('', 'Stok & Ekipman Takibi'),
('', 'Fotoğraflı İlerleme Raporu'),
('', 'Sözleşme Şablon Yöneticisi'),
('', 'Anomali & Hata Uyarı Sistemi'),
('', 'Öncelikli Teknik Destek'),
('', 'Yeni Modüllere Erken Erişim'),
('', 'Özel Rapor Formatı'),
],
},
]

# Hangi pakette hangi modüller aktif — MainWindow bu listeyi kullanır
MODULE_RIGHTS: dict[str, list[str]] = {
'baslangic': [
'metraj_temel',
'maliyet',
],
'profesyonel': [
'metraj_temel', 'metraj_gelismis',
'maliyet',
'demir',
'cad_3d',
'teklif_fatura',
'gantt',
'serbest_piyasa',
],
'ihale': [
'metraj_temel', 'metraj_gelismis',
'maliyet',
'demir',
'cad_3d',
'teklif_fatura',
'gantt',
'serbest_piyasa',
'devlet_ihalesi',
'saha_puantaj',
],
'kurumsal': [
'metraj_temel', 'metraj_gelismis',
'maliyet',
'demir',
'cad_3d',
'teklif_fatura',
'gantt',
'serbest_piyasa',
'devlet_ihalesi',
'saha_puantaj',
'analitik',
'crm_tam',
],
}


# ─── Paket Kartı Bileşeni ────────────────────────────────────────────────────

class PackageCard(QFrame):
    """
    Tek bir lisans paketini temsil eden kart bileşeni.

    Neyi çözer?
    4 paket kartını bağımsız, yeniden kullanılabilir widget olarak
    kapsüller; seçim durumu (selected / unselected / hover) görsel
    olarak enterEvent / leaveEvent ile yönetilir.

    Nasıl test edilir?
    card = PackageCard(PACKAGES[0])
    card.set_selected(True) → border rengi yeşile dönmeli
    card.set_selected(False) → border koyu griye dönmeli
    """

    def __init__(self, pkg: dict, parent=None):
        super().__init__(parent)
        self.pkg = pkg
        self.pkg_id = pkg['id']
        self.color = pkg['color']
        self.color_hov = pkg['color_hover']
        self._selected = False

        self.setObjectName("pkg_card")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._build_ui()
        self._refresh_style()

        # ── Yapı ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Üst renk şeridi
        stripe = QFrame()
        stripe.setFixedHeight(6)
        stripe.setObjectName("stripe")
        stripe.setStyleSheet(
            f"QFrame#stripe {{ background-color: {self.color}; border: none; border-radius: 0; }}"
        )
        root.addWidget(stripe)

        # İçerik
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(8)

        # Badge (varsa) veya boş placeholder
        if 'badge' in self.pkg:
            badge = QLabel(self.pkg['badge'])
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedHeight(22)
            badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {self.color};
                    color: #ffffff;
                    border-radius: 4px;
                    font-size: 8pt;
                    font-weight: bold;
                    padding: 2px 6px;
                }}
            """)
            cl.addWidget(badge)
        else:
            ph = QLabel()
            ph.setFixedHeight(22)
            ph.setStyleSheet("background: transparent;")
            cl.addWidget(ph)

        # İkon
        icon_lbl = QLabel(self.pkg['icon'])
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 30))
        icon_lbl.setStyleSheet("background: transparent; color: white;")
        cl.addWidget(icon_lbl)

        # Paket adı
        name_lbl = QLabel(self.pkg['name'])
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {self.color}; background: transparent;")
        cl.addWidget(name_lbl)

        # Fiyat satırı
        price_row = QWidget()
        price_row.setStyleSheet("background: transparent;")
        pr_layout = QHBoxLayout(price_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        pr_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        price_lbl = QLabel(self.pkg['price'])
        price_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        price_lbl.setStyleSheet(f"color: {self.color}; background: transparent;")

        period_lbl = QLabel(" " + self.pkg['period'])
        period_lbl.setFont(QFont("Segoe UI", 9))
        period_lbl.setStyleSheet("color: #888; background: transparent;")
        period_lbl.setAlignment(Qt.AlignmentFlag.AlignBottom)

        pr_layout.addWidget(price_lbl)
        pr_layout.addWidget(period_lbl)
        cl.addWidget(price_row)

        # Hedef kitle
        target_lbl = QLabel(self.pkg['target'])
        target_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        target_lbl.setFont(QFont("Segoe UI", 8))
        target_lbl.setStyleSheet("color: #777; background: transparent;")
        target_lbl.setWordWrap(True)
        cl.addWidget(target_lbl)

        # Ayırıcı
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"border: 1px solid {self.color}; margin: 2px 0;")
        cl.addWidget(sep)

        # Modül listesi — kaydırılabilir
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QWidget { background: transparent; }
            QScrollBar:vertical { background: #1a1a2e; width: 5px; border: none; }
            QScrollBar::handle:vertical { background: #3a3a5a; border-radius: 2px; min-height: 20px; }
        """)

        mod_widget = QWidget()
        mod_widget.setStyleSheet("background: transparent;")
        mod_layout = QVBoxLayout(mod_widget)
        mod_layout.setContentsMargins(2, 0, 2, 0)
        mod_layout.setSpacing(3)

        for ico, text in self.pkg['modules']:
            row_lbl = QLabel(f" {ico} {text}")
            row_lbl.setFont(QFont("Segoe UI", 8))
            if ico in ('✅', '🔒'):
                row_lbl.setStyleSheet("color: #cccccc; background: transparent;")
            else:
                row_lbl.setStyleSheet("color: #444466; background: transparent;")
            mod_layout.addWidget(row_lbl)

        mod_layout.addStretch()
        scroll.setWidget(mod_widget)
        scroll.setMinimumHeight(250)
        cl.addWidget(scroll)

        # SEÇ butonu
        self.btn_select = QPushButton(f" {self.pkg['icon']} BU PAKETİ SEÇ")
        self.btn_select.setFixedHeight(40)
        self.btn_select.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_select.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        cl.addWidget(self.btn_select)

        root.addWidget(content)

        # ── Stil Yönetimi ─────────────────────────────────────────────────────────

    def _refresh_style(self, hover: bool = False):
        """Kart çerçeve + buton stilini duruma göre güncelle."""
        if self._selected:
            self.setStyleSheet(f"""
            QFrame#pkg_card {{
            background-color: #1e2a3e;
            border: 2px solid {self.color};
            border-radius: 12px;
            }}
            """)
            self.btn_select.setStyleSheet(f"""
            QPushButton {{
            background-color: {self.color};
            color: #ffffff;
            border: 2px solid {self.color};
            border-radius: 8px;
            font-weight: bold;
            }}
            QPushButton:hover {{
            background-color: {self.color_hov};
            }}
            """)
            self.btn_select.setText(" SEÇİLDİ")
        elif hover:
            self.setStyleSheet(f"""
            QFrame#pkg_card {{
            background-color: #1a2540;
            border: 2px solid {self.color};
            border-radius: 12px;
            }}
            """)
        else:
            self.setStyleSheet("""
            QFrame#pkg_card {
            background-color: #16213e;
            border: 2px solid #2a3a5a;
            border-radius: 12px;
            }
            """)
            self.btn_select.setStyleSheet(f"""
            QPushButton {{
            background-color: transparent;
            color: {self.color};
            border: 2px solid {self.color};
            border-radius: 8px;
            font-weight: bold;
            }}
            QPushButton:hover {{
            background-color: {self.color};
            color: #ffffff;
            }}
            """)
            self.btn_select.setText(f" {self.pkg['icon']} BU PAKETİ SEÇ")

    def set_selected(self, state: bool):
        """Seçim durumunu dışarıdan güncelle."""
        self._selected = state
        self._refresh_style()

        # Gölge efekti: seçiliyse belirginleştir
        if state:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(28)
            shadow.setColor(QColor(self.color))
            shadow.setOffset(0, 0)
            self.setGraphicsEffect(shadow)
        else:
            self.setGraphicsEffect(None)

            # ── Hover Olayları ────────────────────────────────────────────────────────

    def enterEvent(self, event):
        if not self._selected:
            self._refresh_style(hover=True)
            super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._selected:
            self._refresh_style(hover=False)
            super().leaveEvent(event)


# ─── Ana Dialog ──────────────────────────────────────────────────────────────

class StartupDialog(QDialog):
    """
    Uygulama başlangıç ekranı — 4 lisans paketinden seçim.

    Döndürdüğü değerler:
    selected_package : str — 'baslangic' | 'profesyonel' | 'ihale' | 'kurumsal'
    enabled_modules : list[str] — aktif modül ID listesi (MODULE_RIGHTS'tan)

    Neyi çözer?
    Eski "Yüklenici / Alt Yüklenici" seçiminin yerini alır.
    Kullanıcı kendi işine uygun paketi görsel olarak seçer;
    program bu seçime göre hangi sekme/araçların açık olacağını belirler.

    Nasıl test edilir?
    dialog = StartupDialog()
    result = dialog.exec()
    # result == 1 → kullanıcı devam etti
    print(dialog.selected_package) # 'ihale'
    print(dialog.enabled_modules) # ['metraj_temel', 'devlet_ihalesi', ...]
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_package: str = 'kurumsal'
        self.enabled_modules: list = MODULE_RIGHTS['kurumsal']
        self._cards: dict = {}
        self._init_ui()

        # ── Yapı ─────────────────────────────────────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle("QUANTIX PRO — Lisans Paketi Seçimi")
        self.setMinimumSize(1240, 820)
        self.setStyleSheet("""
        QDialog {
        background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #0d1117,
        stop:0.5 #1a1a2e,
        stop:1 #0d1117
        );
        }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(18)

        self._build_header(root)
        self._build_cards(root)
        self._build_footer(root)

        # Varsayılan seçim: Kurumsal
        self._on_select('kurumsal')

    def _build_header(self, parent: QVBoxLayout):
        """Logo + Başlık + Alt başlık"""
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Logo (varsa)
        logo_path = Path(__file__).parent.parent.parent / "assets" / "quantix_logo.png"
        if logo_path.exists():
            lbl = QLabel()
            px = QPixmap(str(logo_path)).scaled(
                180, 72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            lbl.setPixmap(px)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("background: transparent;")
            layout.addWidget(lbl)

        # Ana başlık
        title = QLabel("QUANTIX PRO")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setStyleSheet(
            "color: #00BFFF; background: transparent; letter-spacing: 5px;"
        )
        layout.addWidget(title)

        # Alt başlık
        subtitle = QLabel("İnşaat Metraj & Maliyet Yönetim Platformu")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet("color: #777777; background: transparent;")
        layout.addWidget(subtitle)

        # Yönlendirme
        guide = QLabel("Lisans paketinizi seçin ve uygulamayı başlatın")
        guide.setAlignment(Qt.AlignmentFlag.AlignCenter)
        guide.setFont(QFont("Segoe UI", 9))
        guide.setStyleSheet("color: #444466; background: transparent;")
        layout.addWidget(guide)

        parent.addWidget(wrapper)

    def _build_cards(self, parent: QVBoxLayout):
        """4 paket kartını yan yana yerleştir"""
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(wrapper)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 0, 0, 0)

        for pkg in PACKAGES:
            card = PackageCard(pkg)
            card.btn_select.clicked.connect(
                lambda _, pid=pkg['id']: self._on_select(pid)
            )
            layout.addWidget(card)
            self._cards[pkg['id']] = card

        parent.addWidget(wrapper)

    def _build_footer(self, parent: QVBoxLayout):
        """Alt çubuk: seçim bilgisi + Çıkış + Başlat"""
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Seçilen paket etiketi
        self._lbl_selection = QLabel()
        self._lbl_selection.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._lbl_selection.setStyleSheet("background: transparent;")
        layout.addWidget(self._lbl_selection, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch()

        # Çıkış
        btn_exit = QPushButton("Çıkış")
        btn_exit.setFixedSize(100, 42)
        btn_exit.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_exit.setFont(QFont("Segoe UI", 10))
        btn_exit.setStyleSheet("""
        QPushButton {
        background: transparent;
        color: #777777;
        border: 1px solid #3a3a5a;
        border-radius: 8px;
        }
        QPushButton:hover {
        background: #2a2a3a;
        color: #bbbbbb;
        border: 1px solid #555577;
        }
        """)
        btn_exit.clicked.connect(self.reject)
        layout.addWidget(btn_exit)

        # Başlat
        self._btn_start = QPushButton(" ▶ UYGULAMAYI BAŞLAT")
        self._btn_start.setFixedSize(230, 42)
        self._btn_start.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_start.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._btn_start.clicked.connect(self.accept)
        layout.addWidget(self._btn_start)

        parent.addWidget(wrapper)

        # ── Mantık ───────────────────────────────────────────────────────────────

    def _on_select(self, pkg_id: str):
        """
        Kart seçildiğinde:
        1. Tüm kartları güncelle (seçili / seçili değil)
        2. selected_package ve enabled_modules'u güncelle
        3. Alt çubuktaki etiket + butonu güncelle
        """
        self.selected_package = pkg_id
        self.enabled_modules = MODULE_RIGHTS[pkg_id]

        for cid, card in self._cards.items():
            card.set_selected(cid == pkg_id)

        # Seçilen paketi bul
        pkg = next(p for p in PACKAGES if p['id'] == pkg_id)

        # Seçim etiketi
        self._lbl_selection.setText(
            f"Seçilen Paket: {pkg['icon']} {pkg['name']} — "
            f"{pkg['price']} {pkg['period']}"
        )
        self._lbl_selection.setStyleSheet(
            f"color: {pkg['color']}; background: transparent; font-weight: bold; font-size: 10pt;"
        )

        # Başlat butonu rengi
        self._btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: {pkg['color']};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {pkg['color_hover']};
            }}
            QPushButton:pressed {{
                background-color: {pkg['color']};
                opacity: 0.8;
            }}
        """)
