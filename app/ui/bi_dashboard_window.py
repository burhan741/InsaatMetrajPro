"""
Business Intelligence Dashboard Sekmesi
Grafikler, KPI kartları ve trend analizi ile profesyonel dashboard
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QScrollArea,
    QGridLayout, QComboBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from typing import Optional
import logging

from app.core.database import DatabaseManager
from app.core.bi_engine import BIEngine

logger = logging.getLogger(__name__)


class KPICard(QFrame):
    """KPI Kartı widget'i"""

    def __init__(self, baslik: str, deger: str, ikon: str = "📊", renk: str = "#2196F3"):
        super().__init__()
        self.init_ui(baslik, deger, ikon, renk)

    def init_ui(self, baslik: str, deger: str, ikon: str, renk: str):
        """KPI kartını oluştur"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {renk}, stop:1 #1a1a2e);
                border-radius: 10px;
                border: 2px solid {renk};
                padding: 15px;
            }}
        """)

        layout = QVBoxLayout()

        # İkon ve başlık
        header_layout = QHBoxLayout()

        ikon_label = QLabel(ikon)
        ikon_label.setStyleSheet("font-size: 28pt; border: none;")
        header_layout.addWidget(ikon_label)

        baslik_label = QLabel(baslik)
        baslik_label.setStyleSheet("""
            font-size: 11pt;
            font-weight: bold;
            color: #e0e0e0;
            border: none;
        """)
        header_layout.addWidget(baslik_label)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Değer
        self.deger_label = QLabel(deger)
        self.deger_label.setStyleSheet("""
            font-size: 24pt;
            font-weight: bold;
            color: white;
            margin-top: 10px;
            border: none;
        """)
        self.deger_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.deger_label)

        self.setLayout(layout)

    def update_deger(self, yeni_deger: str):
        """Değeri güncelle"""
        self.deger_label.setText(yeni_deger)


class BIDashboardWindow(QWidget):
    """Business Intelligence Dashboard widget'i"""

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.engine = BIEngine(db)
        self.current_proje_id = None
        self.init_ui()
        self.load_dashboard()

        # Otomatik yenileme (5 dakikada bir)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_dashboard)
        self.refresh_timer.start(300000)  # 5 dakika

    def init_ui(self):
        """UI elementlerini oluştur"""
        main_layout = QVBoxLayout()

        # Başlık ve proje seçici
        header_layout = QHBoxLayout()

        baslik = QLabel("📊 Business Intelligence Dashboard")
        baslik.setStyleSheet("font-size: 20pt; font-weight: bold; margin: 10px;")
        header_layout.addWidget(baslik)

        header_layout.addStretch()

        # Proje filtresi
        proje_label = QLabel("Proje:")
        header_layout.addWidget(proje_label)

        self.proje_combo = QComboBox()
        self.proje_combo.addItem("Tüm Projeler", None)
        self.load_projeler()
        self.proje_combo.currentIndexChanged.connect(self.on_proje_changed)
        header_layout.addWidget(self.proje_combo)

        # Yenile butonu
        yenile_btn = QPushButton("🔄 Yenile")
        yenile_btn.clicked.connect(self.load_dashboard)
        header_layout.addWidget(yenile_btn)

        main_layout.addLayout(header_layout)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        # Ana içerik
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # KPI Kartları
        kpi_group = self._create_kpi_cards()
        content_layout.addWidget(kpi_group)

        # Kategori dağılımı ve top kalemler
        charts_layout = QHBoxLayout()

        kategori_group = self._create_kategori_table()
        charts_layout.addWidget(kategori_group, 1)

        top_kalemler_group = self._create_top_kalemler_table()
        charts_layout.addWidget(top_kalemler_group, 1)

        content_layout.addLayout(charts_layout)

        # Taşeron karşılaştırma
        taseron_group = self._create_taseron_table()
        content_layout.addWidget(taseron_group)

        # Trend tablosu
        trend_group = self._create_trend_table()
        content_layout.addWidget(trend_group)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        self.setLayout(main_layout)

    def _create_kpi_cards(self) -> QGroupBox:
        """KPI kartlarını oluştur"""
        group = QGroupBox("Ana Göstergeler (KPI)")
        layout = QGridLayout()

        # Boş kartlar oluştur (veriler load_dashboard'da doldurulacak)
        self.kpi_proje = KPICard("Toplam Proje", "0", "📁", "#4CAF50")
        layout.addWidget(self.kpi_proje, 0, 0)

        self.kpi_maliyet = KPICard("Toplam Maliyet", "0 TL", "💰", "#2196F3")
        layout.addWidget(self.kpi_maliyet, 0, 1)

        self.kpi_kalem = KPICard("Toplam Kalem", "0", "📋", "#FF9800")
        layout.addWidget(self.kpi_kalem, 0, 2)

        self.kpi_ortalama = KPICard("Ortalama Maliyet", "0 TL", "📊", "#9C27B0")
        layout.addWidget(self.kpi_ortalama, 1, 0)

        self.kpi_taseron = KPICard("Taşeron Sayısı", "0", "👷", "#F44336")
        layout.addWidget(self.kpi_taseron, 1, 1)

        self.kpi_pahali_proje = KPICard("En Pahalı Proje", "N/A", "🏆", "#00BCD4")
        layout.addWidget(self.kpi_pahali_proje, 1, 2)

        group.setLayout(layout)
        return group

    def _create_kategori_table(self) -> QGroupBox:
        """Kategori dağılımı tablosu"""
        group = QGroupBox("📊 Kategori Bazında Maliyet Dağılımı")
        layout = QVBoxLayout()

        self.kategori_table = QTableWidget()
        self.kategori_table.setColumnCount(4)
        self.kategori_table.setHorizontalHeaderLabels([
            "Kategori", "Maliyet (TL)", "Kalem Sayısı", "Oran (%)"
        ])
        self.kategori_table.setAlternatingRowColors(True)
        self.kategori_table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.kategori_table)

        group.setLayout(layout)
        return group

    def _create_top_kalemler_table(self) -> QGroupBox:
        """En pahalı kalemler tablosu"""
        group = QGroupBox("🔝 En Pahalı 10 Kalem")
        layout = QVBoxLayout()

        self.top_kalemler_table = QTableWidget()
        self.top_kalemler_table.setColumnCount(4)
        self.top_kalemler_table.setHorizontalHeaderLabels([
            "Poz No", "Tanım", "Miktar", "Toplam (TL)"
        ])
        self.top_kalemler_table.setAlternatingRowColors(True)
        self.top_kalemler_table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.top_kalemler_table)

        group.setLayout(layout)
        return group

    def _create_taseron_table(self) -> QGroupBox:
        """Taşeron karşılaştırma tablosu"""
        group = QGroupBox("💼 Taşeron Performans Analizi")
        layout = QVBoxLayout()

        self.taseron_table = QTableWidget()
        self.taseron_table.setColumnCount(3)
        self.taseron_table.setHorizontalHeaderLabels([
            "Firma", "Ortalama Fiyat (TL)", "Teklif Sayısı"
        ])
        self.taseron_table.setAlternatingRowColors(True)
        self.taseron_table.horizontalHeader().setStretchLastSection(True)
        self.taseron_table.setMaximumHeight(250)

        layout.addWidget(self.taseron_table)

        group.setLayout(layout)
        return group

    def _create_trend_table(self) -> QGroupBox:
        """Aylık trend tablosu"""
        group = QGroupBox("📈 Aylık Trend Analizi (Son 12 Ay)")
        layout = QVBoxLayout()

        self.trend_table = QTableWidget()
        self.trend_table.setColumnCount(3)
        self.trend_table.setHorizontalHeaderLabels([
            "Ay", "Proje Sayısı", "Toplam Maliyet (TL)"
        ])
        self.trend_table.setAlternatingRowColors(True)
        self.trend_table.horizontalHeader().setStretchLastSection(True)
        self.trend_table.setMaximumHeight(300)

        layout.addWidget(self.trend_table)

        group.setLayout(layout)
        return group

    def load_projeler(self):
        """Projeleri combobox'a yükle"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, ad FROM projects WHERE durum = 'aktif' ORDER BY ad")
                rows = cursor.fetchall()

                for row in rows:
                    self.proje_combo.addItem(row['ad'], row['id'])

        except Exception as e:
            logger.error(f"Proje yükleme hatası: {e}")

    def on_proje_changed(self, index: int):
        """Proje değiştiğinde"""
        self.current_proje_id = self.proje_combo.itemData(index)
        self.load_dashboard()

    def load_dashboard(self):
        """Dashboard verilerini yükle"""
        try:
            # KPI'ları yükle
            kpis = self.engine.get_dashboard_kpis(self.current_proje_id)

            self.kpi_proje.update_deger(str(kpis['toplam_proje']))
            self.kpi_maliyet.update_deger(f"{kpis['toplam_maliyet']:,.2f} TL")
            self.kpi_kalem.update_deger(str(kpis['toplam_kalem']))
            self.kpi_ortalama.update_deger(f"{kpis['ortalama_maliyet']:,.2f} TL")
            self.kpi_taseron.update_deger(str(kpis['taseron_sayisi']))

            if kpis['en_pahali_proje'] != 'N/A':
                self.kpi_pahali_proje.update_deger(
                    f"{kpis['en_pahali_proje'][:15]}...\n{kpis['en_pahali_proje_maliyet']:,.0f} TL"
                )
            else:
                self.kpi_pahali_proje.update_deger("N/A")

            # Kategori dağılımını yükle
            self.load_kategori_dagilimi()

            # Top kalemleri yükle
            self.load_top_kalemler()

            # Taşeron karşılaştırmasını yükle
            self.load_taseron_karsilastirma()

            # Trend analizini yükle
            if not self.current_proje_id:  # Sadece tüm projeler için
                self.load_trend_analizi()

        except Exception as e:
            logger.error(f"Dashboard yükleme hatası: {e}")

    def load_kategori_dagilimi(self):
        """Kategori dağılımını yükle"""
        try:
            kategoriler = self.engine.get_kategori_dagilimi(self.current_proje_id)

            self.kategori_table.setRowCount(len(kategoriler))

            for row_idx, kat in enumerate(kategoriler):
                self.kategori_table.setItem(row_idx, 0, QTableWidgetItem(kat['kategori']))
                self.kategori_table.setItem(row_idx, 1, QTableWidgetItem(f"{kat['maliyet']:,.2f}"))
                self.kategori_table.setItem(row_idx, 2, QTableWidgetItem(str(kat['kalem_sayisi'])))

                oran_item = QTableWidgetItem(f"%{kat['oran']:.2f}")
                oran_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Yüksek oranlara renk ver
                if kat['oran'] > 30:
                    oran_item.setBackground(QColor(244, 67, 54, 100))  # Kırmızı
                elif kat['oran'] > 15:
                    oran_item.setBackground(QColor(255, 152, 0, 100))  # Turuncu
                else:
                    oran_item.setBackground(QColor(76, 175, 80, 100))  # Yeşil

                self.kategori_table.setItem(row_idx, 3, oran_item)

        except Exception as e:
            logger.error(f"Kategori dağılımı yükleme hatası: {e}")

    def load_top_kalemler(self):
        """En pahalı kalemleri yükle"""
        try:
            top_kalemler = self.engine.get_top_kalemler(self.current_proje_id, limit=10)

            self.top_kalemler_table.setRowCount(len(top_kalemler))

            for row_idx, kalem in enumerate(top_kalemler):
                self.top_kalemler_table.setItem(row_idx, 0, QTableWidgetItem(kalem['poz_no']))

                tanim = kalem['tanim'][:50] + "..." if len(kalem['tanim']) > 50 else kalem['tanim']
                self.top_kalemler_table.setItem(row_idx, 1, QTableWidgetItem(tanim))

                self.top_kalemler_table.setItem(row_idx, 2,
                    QTableWidgetItem(f"{kalem['miktar']} {kalem['birim']}"))

                toplam_item = QTableWidgetItem(f"{kalem['toplam']:,.2f}")
                toplam_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                self.top_kalemler_table.setItem(row_idx, 3, toplam_item)

        except Exception as e:
            logger.error(f"Top kalemler yükleme hatası: {e}")

    def load_taseron_karsilastirma(self):
        """Taşeron karşılaştırmasını yükle"""
        try:
            taseron_data = self.engine.get_taseron_karsilastirma(self.current_proje_id)

            self.taseron_table.setRowCount(len(taseron_data))

            for row_idx, taseron in enumerate(taseron_data):
                self.taseron_table.setItem(row_idx, 0, QTableWidgetItem(taseron['firma']))
                self.taseron_table.setItem(row_idx, 1, QTableWidgetItem(f"{taseron['ortalama_fiyat']:,.2f}"))
                self.taseron_table.setItem(row_idx, 2, QTableWidgetItem(str(taseron['teklif_sayisi'])))

                # En ucuza yeşil renk
                if row_idx == 0:
                    for col in range(3):
                        item = self.taseron_table.item(row_idx, col)
                        if item:
                            item.setBackground(QColor(76, 175, 80, 50))

        except Exception as e:
            logger.error(f"Taşeron karşılaştırma yükleme hatası: {e}")

    def load_trend_analizi(self):
        """Aylık trend analizini yükle"""
        try:
            trend_data = self.engine.get_aylik_trend(12)

            self.trend_table.setRowCount(len(trend_data))

            for row_idx, ay_data in enumerate(trend_data):
                self.trend_table.setItem(row_idx, 0, QTableWidgetItem(ay_data['ay']))
                self.trend_table.setItem(row_idx, 1, QTableWidgetItem(str(ay_data['proje_sayisi'])))
                self.trend_table.setItem(row_idx, 2, QTableWidgetItem(f"{ay_data['toplam_maliyet']:,.2f}"))

        except Exception as e:
            logger.error(f"Trend analizi yükleme hatası: {e}")
