"""
Business Intelligence Dashboard
3 matplotlib grafik + KPI kartları + tablolar — tamamen dark temalı

Neyi çözer?
 Eski tablo-tabanlı BI Dashboard yerine görsel grafik tabanlı analiz sunar.
 Müteahhide tek bakışta proje durumunu okuma imkânı verir.

Grafikler:
 1. Donut Chart — Kategori bazlı maliyet dağılımı
 2. HBar Chart — En pahalı 5 iş kalemi
 3. Line Chart — Son 12 aylık maliyet trendi (alan dolgulu)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QScrollArea,
    QGridLayout, QComboBox, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from typing import Optional
import logging

from app.core.database import DatabaseManager
from app.core.bi_engine import BIEngine

logger = logging.getLogger(__name__)

# ── Dark Tema Sabitleri ────────────────────────────────────────────────────────
_BG = '#1a1a2e'     # Figure / canvas arka planı
_AX = '#16213e'     # Axes arka planı
_TEXT = '#d4d4d4'   # Genel metin rengi
_TITLE = '#e0e0e0'  # Başlık rengi
_GRID = '#2a3a5a'   # Grid ve spine rengi
_ACCENT = '#00BFFF' # Ana vurgu rengi (cyan)

# Grafik renk paleti (10 renk — fazla kategori için döngüsel)
_COLORS = [
    '#00BFFF', '#4CAF50', '#FF9800', '#E91E63',
    '#9C27B0', '#F44336', '#2196F3', '#FFC107',
    '#00BCD4', '#8BC34A',
]


# ── Yardımcı: Dark Figure Oluşturucu ─────────────────────────────────────────

def _make_dark_canvas(figsize=(6, 3.5)):
    """
    Dark temalı Figure + Axes + FigureCanvasQTAgg üçlüsü döndürür.

    Neyi çözer?
    Her grafik için tekrar eden dark tema kodunu tek yerde toplar.

    Nasıl test edilir?
    fig, ax, canvas = _make_dark_canvas()
    assert fig.get_facecolor() != (1,1,1,1) # beyaz değil
    """
    try:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        fig = Figure(figsize=figsize, facecolor=_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(_AX)
        ax.tick_params(colors=_TEXT, labelsize=8)
        ax.title.set_color(_TITLE)
        ax.xaxis.label.set_color(_TEXT)
        ax.yaxis.label.set_color(_TEXT)
        for spine in ax.spines.values():
            spine.set_edgecolor(_GRID)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setStyleSheet(
            f"background-color: {_BG}; border-radius: 8px; border: 1px solid {_GRID};"
        )
        return fig, ax, canvas

    except ImportError:
        return None, None, None


def _reset_ax(fig, ax):
    """Axes'i temizleyip dark temayı yeniden uygula."""
    ax.clear()
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_AX)
    ax.tick_params(colors=_TEXT, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(_GRID)


# ── KPI Kartı ────────────────────────────────────────────────────────────────

class KPICard(QFrame):
    """Renk kodlu KPI kartı bileşeni."""

    def __init__(self, baslik: str, deger: str, ikon: str = "", renk: str = "#2196F3"):
        super().__init__()
        self._build(baslik, deger, ikon, renk)

    def _build(self, baslik: str, deger: str, ikon: str, renk: str):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMinimumHeight(110)
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {renk}55, stop:1 #1a1a2e);
                border-radius: 10px;
                border: 1px solid {renk};
                padding: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        ikon_lbl = QLabel(ikon)
        ikon_lbl.setStyleSheet("font-size: 22pt; border: none; background: transparent;")
        header.addWidget(ikon_lbl)

        baslik_lbl = QLabel(baslik)
        baslik_lbl.setStyleSheet(
            "font-size: 9pt; font-weight: bold; color: #aaaaaa; border: none; background: transparent;"
        )
        baslik_lbl.setWordWrap(True)
        header.addWidget(baslik_lbl, 1)
        layout.addLayout(header)

        self.deger_lbl = QLabel(deger)
        self.deger_lbl.setStyleSheet(
            f"font-size: 18pt; font-weight: bold; color: {renk};"
            " border: none; background: transparent;"
        )
        self.deger_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.deger_lbl)

    def update_deger(self, yeni: str):
        self.deger_lbl.setText(yeni)


# ── Ana Dashboard ─────────────────────────────────────────────────────────────

class BIDashboardWindow(QWidget):
    """
    Business Intelligence Dashboard — grafik tabanlı versiyon.

    Layout (yukarıdan aşağıya):
    1. Başlık çubuğu + proje filtresi
    2. KPI kartları (6 adet, 2×3)
    3. Donut Chart (sol) | HBar Chart (sağ)
    4. Line Chart (tam genişlik — aylık trend)
    5. Taşeron tablosu (kompakt)

    Nasıl test edilir?
    window = BIDashboardWindow(db)
    window.show()
    # → Grafikler boş ama hata vermemeli
    window.load_dashboard()
    # → Grafikler verilerle dolmalı
    """

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.engine = BIEngine(db)
        self.current_proje_id: Optional[int] = None

        # Grafik referansları (matplotlib yoksa None)
        self.donut_fig = self.donut_ax = self.donut_canvas = None
        self.bar_fig = self.bar_ax = self.bar_canvas = None
        self.line_fig = self.line_ax = self.line_canvas = None

        self._init_ui()
        self.load_dashboard()

        # 5 dakikada bir otomatik yenileme
        self._timer = QTimer()
        self._timer.timeout.connect(self.load_dashboard)
        self._timer.start(300_000)

    # ── UI Kurulumu ───────────────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        root.addWidget(self._build_header())

        # Kaydırılabilir içerik
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setSpacing(12)
        cl.setContentsMargins(0, 0, 0, 0)

        cl.addWidget(self._build_kpi_group())       # Satır 1: KPI kartları
        cl.addLayout(self._build_charts_row())      # Satır 2: Donut + HBar
        cl.addWidget(self._build_trend_group())     # Satır 3: Line chart
        cl.addWidget(self._build_taseron_group())   # Satır 4: Taşeron tablosu

        scroll.setWidget(content)
        root.addWidget(scroll)

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel(" Business Intelligence Dashboard")
        title.setStyleSheet(
            "font-size: 16pt; font-weight: bold; color: #00BFFF; background: transparent;"
        )
        layout.addWidget(title)
        layout.addStretch()

        layout.addWidget(QLabel("Proje:"))

        self.proje_combo = QComboBox()
        self.proje_combo.addItem("Tüm Projeler", None)
        self._load_projeler()
        self.proje_combo.currentIndexChanged.connect(self._on_proje_changed)
        layout.addWidget(self.proje_combo)

        btn = QPushButton(" Yenile")
        btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        btn.clicked.connect(self.load_dashboard)
        layout.addWidget(btn)

        return w

    def _build_kpi_group(self) -> QGroupBox:
        group = QGroupBox("Ana Göstergeler")
        grid = QGridLayout(group)
        grid.setSpacing(10)

        self.kpi_proje = KPICard("Toplam Proje", "—", "", "#4CAF50")
        self.kpi_maliyet = KPICard("Toplam Maliyet", "—", "", "#2196F3")
        self.kpi_kalem = KPICard("Toplam Kalem", "—", "", "#FF9800")
        self.kpi_ort = KPICard("Ort. Maliyet", "—", "", "#9C27B0")
        self.kpi_taseron = KPICard("Taşeron Sayısı", "—", "", "#F44336")
        self.kpi_pahali = KPICard("En Pahalı Proje", "N/A", "", "#00BCD4")

        for col, card in enumerate([self.kpi_proje, self.kpi_maliyet, self.kpi_kalem]):
            grid.addWidget(card, 0, col)
        for col, card in enumerate([self.kpi_ort, self.kpi_taseron, self.kpi_pahali]):
            grid.addWidget(card, 1, col)

        return group

    def _build_charts_row(self) -> QHBoxLayout:
        """Donut (sol) + HBar (sağ) yan yana."""
        layout = QHBoxLayout()
        layout.setSpacing(12)

        # — Donut: Kategori Dağılımı —
        donut_group = QGroupBox(" Kategori Bazlı Maliyet Dağılımı")
        donut_layout = QVBoxLayout(donut_group)

        self.donut_fig, self.donut_ax, self.donut_canvas = _make_dark_canvas(figsize=(5, 3.8))
        if self.donut_canvas:
            self.donut_canvas.setMinimumHeight(280)
            donut_layout.addWidget(self.donut_canvas)
        else:
            donut_layout.addWidget(QLabel(" Matplotlib bulunamadı."))

        layout.addWidget(donut_group, 5)

        # — HBar: En Pahalı 5 Kalem —
        bar_group = QGroupBox(" En Pahalı 5 İş Kalemi")
        bar_layout = QVBoxLayout(bar_group)

        self.bar_fig, self.bar_ax, self.bar_canvas = _make_dark_canvas(figsize=(5, 3.8))
        if self.bar_canvas:
            self.bar_canvas.setMinimumHeight(280)
            bar_layout.addWidget(self.bar_canvas)
        else:
            bar_layout.addWidget(QLabel(" Matplotlib bulunamadı."))

        layout.addWidget(bar_group, 5)

        return layout

    def _build_trend_group(self) -> QGroupBox:
        """Tam genişlik aylık trend çizgi grafiği."""
        group = QGroupBox(" Aylık Maliyet Trendi (Son 12 Ay)")
        layout = QVBoxLayout(group)

        self.line_fig, self.line_ax, self.line_canvas = _make_dark_canvas(figsize=(12, 3.2))
        if self.line_canvas:
            self.line_canvas.setMinimumHeight(220)
            layout.addWidget(self.line_canvas)
        else:
            layout.addWidget(QLabel(" Matplotlib bulunamadı."))

        return group

    def _build_taseron_group(self) -> QGroupBox:
        """Kompakt taşeron performans tablosu."""
        group = QGroupBox(" Taşeron Performans Analizi")
        layout = QVBoxLayout(group)

        self.taseron_table = QTableWidget()
        self.taseron_table.setColumnCount(3)
        self.taseron_table.setHorizontalHeaderLabels(["Firma", "Ort. Teklif (₺)", "Teklif Sayısı"])
        self.taseron_table.setAlternatingRowColors(True)
        self.taseron_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.taseron_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.taseron_table.horizontalHeader().setStretchLastSection(True)
        self.taseron_table.setMaximumHeight(200)
        layout.addWidget(self.taseron_table)

        return group

    # ── Veri Yükleme ──────────────────────────────────────────────────────────

    def _load_projeler(self):
        try:
            with self.db.get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, ad FROM projects WHERE durum='aktif' ORDER BY ad"
                ).fetchall()
                for r in rows:
                    self.proje_combo.addItem(r['ad'], r['id'])
        except Exception as e:
            logger.error(f"Proje combo yükleme hatası: {e}")

    def _on_proje_changed(self, index: int):
        self.current_proje_id = self.proje_combo.itemData(index)
        self.load_dashboard()

    def load_dashboard(self):
        """Tüm grafik ve tabloları güncelle."""
        try:
            kpis = self.engine.get_dashboard_kpis(self.current_proje_id)
            self.kpi_proje.update_deger(str(kpis['toplam_proje']))
            self.kpi_maliyet.update_deger(f"{kpis['toplam_maliyet']:,.0f} ₺")
            self.kpi_kalem.update_deger(str(kpis['toplam_kalem']))
            self.kpi_ort.update_deger(f"{kpis['ortalama_maliyet']:,.0f} ₺")
            self.kpi_taseron.update_deger(str(kpis['taseron_sayisi']))

            if kpis['en_pahali_proje'] != 'N/A':
                ad = kpis['en_pahali_proje']
                kisalt = ad[:18] + ('…' if len(ad) > 18 else '')
                self.kpi_pahali.update_deger(
                    f"{kisalt}\n{kpis['en_pahali_proje_maliyet']:,.0f} ₺"
                )
            else:
                self.kpi_pahali.update_deger("N/A")

            # Grafikleri güncelle
            kat_data = self.engine.get_kategori_dagilimi(self.current_proje_id)
            self._draw_donut(kat_data)

            top_data = self.engine.get_top_kalemler(self.current_proje_id, limit=5)
            self._draw_hbar(top_data)

            trend_data = self.engine.get_aylik_trend(12, proje_id=self.current_proje_id)
            self._draw_line(trend_data)

            self._load_taseron()

        except Exception as e:
            logger.error(f"Dashboard yükleme hatası: {e}")

    # ── Grafik Çizim Metodları ────────────────────────────────────────────────

    def _draw_donut(self, data: list):
        """
        Donut (halka) grafiği — kategori bazlı maliyet dağılımı.

        Neyi çözer?
        Müteahhide paranın hangi kategoriye gittiğini
        tek bakışta gösterir (Beton %42, Duvar %18 gibi).
        """
        if not self.donut_canvas or not data:
            return
        try:
            _reset_ax(self.donut_fig, self.donut_ax)

            # Maksimum 8 dilim — fazlasını "Diğer" olarak topla
            sorted_data = sorted(data, key=lambda x: x['maliyet'], reverse=True)
            if len(sorted_data) > 8:
                top = sorted_data[:7]
                diger = sum(d['maliyet'] for d in sorted_data[7:])
                labels = [d['kategori'] for d in top] + ['Diğer']
                vals = [d['maliyet'] for d in top] + [diger]
            else:
                labels = [d['kategori'] for d in sorted_data]
                vals = [d['maliyet'] for d in sorted_data]

            renk_list = (_COLORS * 3)[:len(labels)]

            wedges, texts, autotexts = self.donut_ax.pie(
                vals,
                labels=None,  # etiketler legend'da
                autopct='%1.1f%%',
                colors=renk_list,
                startangle=90,
                pctdistance=0.75,
                wedgeprops=dict(width=0.55, edgecolor=_BG, linewidth=1.5)
            )

            # Yüzde metinleri
            for at in autotexts:
                at.set_color('white')
                at.set_fontsize(7)
                at.set_fontweight('bold')

            # Merkez metin: toplam tutar
            toplam = sum(vals)
            self.donut_ax.text(
                0, 0,
                f"Toplam\n{toplam:,.0f}₺",
                ha='center', va='center',
                fontsize=8, fontweight='bold',
                color=_TITLE
            )

            # Legend (sağ tarafta)
            self.donut_ax.legend(
                wedges, labels,
                loc='center left',
                bbox_to_anchor=(1.02, 0.5),
                fontsize=7,
                frameon=True,
                framealpha=0.15,
                facecolor=_AX,
                edgecolor=_GRID,
                labelcolor=_TEXT
            )

            self.donut_ax.set_title(
                'Maliyet Kategorileri', fontsize=10,
                fontweight='bold', color=_TITLE, pad=8
            )

            self.donut_fig.tight_layout(pad=1.0)
            self.donut_canvas.draw()

        except Exception as e:
            logger.error(f"Donut çizim hatası: {e}")

    def _draw_hbar(self, data: list):
        """
        Yatay çubuk grafik — en pahalı 5 iş kalemi.

        Neyi çözer?
        Bütçeyi en çok tüketen kalemleri vurgular.
        Müteahhit bu kalemlerde pazarlık yapacağını bilir.
        """
        if not self.bar_canvas or not data:
            return
        try:
            _reset_ax(self.bar_fig, self.bar_ax)

            items = data[:5]
            isimler = [
                (d.get('tanim') or '')[:28] + ('…' if len(d.get('tanim', '')) > 28 else '')
                for d in items
            ]
            toplamlar = [d.get('toplam', 0) for d in items]

            # Cyan → koyu mavi gradyan
            bar_colors = ['#00BFFF', '#0099cc', '#007799', '#005566', '#003344']
            bars = self.bar_ax.barh(
                isimler[::-1], toplamlar[::-1],
                color=bar_colors[:len(items)],
                height=0.55,
                edgecolor=_BG, linewidth=0.8
            )

            # Değer etiketleri
            max_val = max(toplamlar) if toplamlar else 1
            for bar, val in zip(bars, toplamlar[::-1]):
                offset = max_val * 0.01
                self.bar_ax.text(
                    bar.get_width() + offset,
                    bar.get_y() + bar.get_height() / 2,
                    f'{val:,.0f} ₺',
                    va='center', ha='left',
                    fontsize=7, fontweight='bold', color=_TEXT
                )

            self.bar_ax.set_xlabel('Toplam Maliyet (₺)', fontsize=8, color='#888888')
            self.bar_ax.set_title(
                'En Pahalı 5 İş Kalemi', fontsize=10,
                fontweight='bold', color=_TITLE, pad=8
            )
            self.bar_ax.tick_params(colors=_TEXT, labelsize=7)
            self.bar_ax.grid(axis='x', alpha=0.12, color=_GRID, linestyle='--')
            for spine in self.bar_ax.spines.values():
                spine.set_edgecolor(_GRID)
            # X eksenini düzelt — etiketler için yer bırak
            self.bar_ax.set_xlim(0, max_val * 1.22)

            self.bar_fig.tight_layout(pad=1.0)
            self.bar_canvas.draw()

        except Exception as e:
            logger.error(f"HBar çizim hatası: {e}")

    def _draw_line(self, data: list):
        """
        Alan dolgulu çizgi grafik — aylık maliyet trendi.

        Neyi çözer?
        İşin büyüdüğünü mü küçüldüğünü mü görsel olarak kanıtlar.
        Yatırımcıya veya bankaya gösterilebilir profesyonel trend grafiği.

        Nasıl test edilir?
        12 aylık veri ile çağrıldığında çizgi + dolgu alanı görünmeli.
        Veri yoksa "Veri bekleniyor..." mesajı görünmeli.
        """
        if not self.line_canvas:
            return
        try:
            _reset_ax(self.line_fig, self.line_ax)

            if not data:
                self.line_ax.text(
                    0.5, 0.5, 'Trend verisi bekleniyor…',
                    ha='center', va='center', transform=self.line_ax.transAxes,
                    fontsize=11, color='#555577'
                )
                self.line_canvas.draw()
                return

            aylar = [d['ay'] for d in data]
            maliyetler = [d['toplam_maliyet'] for d in data]

            # Çizgi + alan dolgu
            self.line_ax.plot(
                aylar, maliyetler,
                color=_ACCENT, linewidth=2.2,
                marker='o', markersize=5,
                markerfacecolor=_ACCENT, markeredgecolor=_BG,
                markeredgewidth=1.5,
                zorder=3
            )
            self.line_ax.fill_between(
                aylar, maliyetler,
                color=_ACCENT, alpha=0.12
            )

            # Değer etiketleri (her noktanın üstüne)
            for i, (ay, mal) in enumerate(zip(aylar, maliyetler)):
                if mal > 0:
                    self.line_ax.annotate(
                        f'{mal:,.0f}₺',
                        (ay, mal),
                        textcoords='offset points', xytext=(0, 8),
                        ha='center', fontsize=6.5, color=_TEXT, fontweight='bold'
                    )

            # Eksen stilleri
            self.line_ax.set_ylabel('Toplam Maliyet (₺)', fontsize=8, color='#888888')
            self.line_ax.set_title(
                'Aylık Maliyet Trendi — Son 12 Ay',
                fontsize=10, fontweight='bold', color=_TITLE, pad=8
            )
            self.line_ax.tick_params(
                axis='x', rotation=35, colors=_TEXT, labelsize=7
            )
            self.line_ax.tick_params(axis='y', colors=_TEXT, labelsize=7)
            self.line_ax.grid(
                axis='y', alpha=0.12, color=_GRID, linestyle='--'
            )
            for spine in self.line_ax.spines.values():
                spine.set_edgecolor(_GRID)

            # Sıfır değerleri gösterme
            max_y = max(maliyetler) if maliyetler else 1
            self.line_ax.set_ylim(bottom=0, top=max_y * 1.25)

            self.line_fig.tight_layout(pad=1.0)
            self.line_canvas.draw()

        except Exception as e:
            logger.error(f"Line chart çizim hatası: {e}")

    def _load_taseron(self):
        """Taşeron performans tablosunu doldur."""
        try:
            data = self.engine.get_taseron_karsilastirma(self.current_proje_id)
            self.taseron_table.setRowCount(len(data))
            for i, t in enumerate(data):
                self.taseron_table.setItem(i, 0, QTableWidgetItem(t['firma']))
                fiyat_item = QTableWidgetItem(f"{t['ortalama_fiyat']:,.2f}")
                fiyat_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.taseron_table.setItem(i, 1, fiyat_item)
                self.taseron_table.setItem(i, 2, QTableWidgetItem(str(t['teklif_sayisi'])))

                # En ucuz taşeron → yeşil vurgu
                if i == 0:
                    for col in range(3):
                        item = self.taseron_table.item(i, col)
                        if item:
                            item.setBackground(QColor(76, 175, 80, 40))
        except Exception as e:
            logger.error(f"Taşeron tablo yükleme hatası: {e}")
