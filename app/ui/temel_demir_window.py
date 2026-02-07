"""
Temel Demir Metraj Modülü UI
DXF'den otomatik temel demir hesaplama arayüzü
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QFileDialog, QMessageBox, QTabWidget,
    QHeaderView, QComboBox, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from pathlib import Path
import csv

from app.core.database import DatabaseManager
from app.core.temel_demir_engine import TemelDemirEngine


class TemelDemirWindow(QWidget):
    """Temel Demir Metraj penceresi"""

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.engine = TemelDemirEngine(db)
        self.current_proje_id = None
        self.init_ui()

    def init_ui(self):
        """Arayüzü oluştur"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Başlık
        baslik = QLabel("📊 TEMEL DEMİR METRAJ MODÜLÜ")
        baslik.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
                background-color: #ecf0f1;
                border-radius: 5px;
            }
        """)
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(baslik)

        # Üst kontroller
        kontrol_layout = self._create_kontrol_panel()
        layout.addLayout(kontrol_layout)

        # Sekmeler
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background: white;
            }
            QTabBar::tab {
                background: #ecf0f1;
                color: #2c3e50;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
            }
        """)

        # Sekme 1: Detaylı Liste
        self.detay_table = self._create_detay_table()
        self.tabs.addTab(self.detay_table, "📋 Detaylı Liste")

        # Sekme 2: Özet (Çapa Göre)
        self.ozet_table = self._create_ozet_table()
        self.tabs.addTab(self.ozet_table, "📊 Özet (Çapa Göre)")

        # Sekme 3: Temel Tipi Özeti
        self.tip_ozet_table = self._create_tip_ozet_table()
        self.tabs.addTab(self.tip_ozet_table, "🏗️ Temel Tipi Özeti")

        layout.addWidget(self.tabs)

        # Alt butonlar
        alt_butonlar = self._create_alt_butonlar()
        layout.addLayout(alt_butonlar)

        self.setLayout(layout)

    def _create_kontrol_panel(self) -> QHBoxLayout:
        """Üst kontrol paneli oluştur"""
        layout = QHBoxLayout()

        # DXF Yükle butonu
        self.dxf_yukle_btn = QPushButton("📁 DXF Dosyası Yükle")
        self.dxf_yukle_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.dxf_yukle_btn.clicked.connect(self.dxf_yukle)
        layout.addWidget(self.dxf_yukle_btn)

        # Dosya adı label
        self.dosya_label = QLabel("Dosya seçilmedi")
        self.dosya_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        layout.addWidget(self.dosya_label)

        layout.addStretch()

        # Filtre: Temel tipi
        filtre_group = QGroupBox("Filtrele")
        filtre_layout = QHBoxLayout()

        self.filtre_combo = QComboBox()
        self.filtre_combo.addItems(["Tümü", "Radye", "Bağ Kirişi", "Kolon Filizi"])
        self.filtre_combo.currentTextChanged.connect(self.filtre_uygula)
        filtre_layout.addWidget(QLabel("Temel Tipi:"))
        filtre_layout.addWidget(self.filtre_combo)

        filtre_group.setLayout(filtre_layout)
        layout.addWidget(filtre_group)

        return layout

    def _create_detay_table(self) -> QTableWidget:
        """Detaylı liste tablosu oluştur"""
        table = QTableWidget()
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels([
            "Temel Tipi", "Temel Adı", "Poz No", "Donatı Tipi",
            "Çap", "Uzunluk (cm)", "Adet", "Toplam (m)",
            "Birim Ağırlık (kg/m)", "Toplam Ağırlık (kg)"
        ])

        # Kolon genişlikleri
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)

        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                background-color: white;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:alternate {
                background-color: #f8f9fa;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 8px;
                font-weight: bold;
                border: none;
            }
        """)

        return table

    def _create_ozet_table(self) -> QTableWidget:
        """Özet (çapa göre) tablosu oluştur"""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "Demir Çapı", "Toplam Uzunluk (m)", "Toplam Ağırlık (kg)",
            "Toplam Ağırlık (ton)", "Adet Sayısı"
        ])

        header = table.horizontalHeader()
        for i in range(5):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                background-color: white;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:alternate {
                background-color: #f8f9fa;
            }
            QHeaderView::section {
                background-color: #27ae60;
                color: white;
                padding: 10px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }
        """)

        return table

    def _create_tip_ozet_table(self) -> QTableWidget:
        """Temel tipi özet tablosu oluştur"""
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels([
            "Temel Tipi", "Adet Sayısı", "Toplam Ağırlık (kg)", "Toplam Ağırlık (ton)"
        ])

        header = table.horizontalHeader()
        for i in range(4):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                background-color: white;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:alternate {
                background-color: #f8f9fa;
            }
            QHeaderView::section {
                background-color: #e67e22;
                color: white;
                padding: 10px;
                font-weight: bold;
                font-size: 13px;
                border: none;
            }
        """)

        return table

    def _create_alt_butonlar(self) -> QHBoxLayout:
        """Alt butonları oluştur"""
        layout = QHBoxLayout()

        # Excel'e Aktar
        excel_btn = QPushButton("📊 Excel'e Aktar")
        excel_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        excel_btn.clicked.connect(self.excel_export)
        layout.addWidget(excel_btn)

        layout.addStretch()

        # Temizle
        temizle_btn = QPushButton("🗑️ Temizle")
        temizle_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        temizle_btn.clicked.connect(self.temizle)
        layout.addWidget(temizle_btn)

        return layout

    def dxf_yukle(self):
        """DXF dosyası yükle ve parse et"""
        dosya_adi, _ = QFileDialog.getOpenFileName(
            self,
            "DXF Dosyası Seç",
            "",
            "DXF Dosyaları (*.dxf);;Tüm Dosyalar (*.*)"
        )

        if not dosya_adi:
            return

        try:
            # DXF oku
            sonuc = self.engine.dxf_oku(dosya_adi)

            # Proje oluştur
            dosya_ismi = Path(dosya_adi).stem
            self.current_proje_id = self.db.create_project(
                f"Temel Demir - {dosya_ismi}",
                f"DXF: {dosya_adi}"
            )

            # Veritabanına kaydet
            kayit_sayisi = self.engine.veritabanina_kaydet(self.current_proje_id)

            # Dosya adını göster
            self.dosya_label.setText(f"✓ {dosya_ismi}")
            self.dosya_label.setStyleSheet("color: #27ae60; font-weight: bold;")

            # Tabloları güncelle
            self.tablolari_guncelle()

            # Başarı mesajı
            QMessageBox.information(
                self,
                "Başarılı",
                f"DXF dosyası başarıyla okundu!\n\n"
                f"Toplam: {kayit_sayisi} adet donatı kaydı\n"
                f"Toplam Ağırlık: {sonuc['toplam_agirlik_kg']:.2f} kg ({sonuc['toplam_agirlik_kg']/1000:.3f} ton)\n\n"
                f"Radye: {len(sonuc['radye'])} kayıt\n"
                f"Bağ Kirişi: {len(sonuc['bag_kirisi'])} kayıt\n"
                f"Kolon Filizi (Boyuna): {len(sonuc['kolon_filizi'])} kayıt\n"
                f"Kolon Etriye: {len(sonuc['kolon_etriye'])} kayıt"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Hata",
                f"DXF dosyası okunamadı:\n\n{str(e)}"
            )

    def tablolari_guncelle(self):
        """Tüm tabloları güncelle"""
        if not self.current_proje_id:
            return

        self.detay_table_guncelle()
        self.ozet_table_guncelle()
        self.tip_ozet_table_guncelle()

    def detay_table_guncelle(self, filtre_tipi: str = None):
        """Detaylı listeyi güncelle"""
        if not self.current_proje_id:
            return

        # Filtreyi uygula
        if filtre_tipi and filtre_tipi != "Tümü":
            tipler = {
                "Radye": "RADYE",
                "Bağ Kirişi": "BAG_KIRISI",
                "Kolon Filizi": "KOLON_FILIZI"
            }
            filtre = tipler.get(filtre_tipi)
        else:
            filtre = None

        detaylar = self.engine.get_detay_liste(self.current_proje_id, filtre)

        self.detay_table.setRowCount(len(detaylar))

        for row, demir in enumerate(detaylar):
            # Temel tipi
            tip_map = {
                "RADYE": "Radye",
                "BAG_KIRISI": "Bağ Kirişi",
                "KOLON_FILIZI": "Kolon Filizi"
            }
            self.detay_table.setItem(row, 0, QTableWidgetItem(tip_map.get(demir['temel_tipi'], demir['temel_tipi'])))

            # Temel adı
            self.detay_table.setItem(row, 1, QTableWidgetItem(demir['temel_adi'] or ''))

            # Poz no
            self.detay_table.setItem(row, 2, QTableWidgetItem(demir['pozisyon_no'] or '-'))

            # Donatı tipi
            self.detay_table.setItem(row, 3, QTableWidgetItem(demir['donati_tipi']))

            # Çap
            cap_item = QTableWidgetItem(f"Ø{demir['cap']}")
            cap_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detay_table.setItem(row, 4, cap_item)

            # Uzunluk
            uzunluk_item = QTableWidgetItem(f"{demir['uzunluk_cm']:.0f}")
            uzunluk_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.detay_table.setItem(row, 5, uzunluk_item)

            # Adet
            adet_item = QTableWidgetItem(f"{demir['adet']}")
            adet_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detay_table.setItem(row, 6, adet_item)

            # Toplam m
            toplam_m_item = QTableWidgetItem(f"{demir['toplam_uzunluk_m']:.2f}")
            toplam_m_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.detay_table.setItem(row, 7, toplam_m_item)

            # Birim ağırlık
            birim_item = QTableWidgetItem(f"{demir['birim_agirlik_kg_m']:.3f}")
            birim_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.detay_table.setItem(row, 8, birim_item)

            # Toplam ağırlık
            agirlik_item = QTableWidgetItem(f"{demir['toplam_agirlik_kg']:.2f}")
            agirlik_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            agirlik_item.setBackground(QColor(255, 248, 220))  # Açık sarı
            self.detay_table.setItem(row, 9, agirlik_item)

    def ozet_table_guncelle(self):
        """Özet tablosunu güncelle"""
        if not self.current_proje_id:
            return

        ozetler = self.engine.get_ozet(self.current_proje_id)

        self.ozet_table.setRowCount(len(ozetler) + 1)  # +1 TOPLAM satırı için

        toplam_uzunluk = 0
        toplam_agirlik_kg = 0
        toplam_adet = 0

        for row, ozet in enumerate(ozetler):
            # Çap
            cap_item = QTableWidgetItem(f"Ø{ozet['cap']}")
            cap_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cap_item.setFont(cap_item.font())
            font = cap_item.font()
            font.setPointSize(12)
            font.setBold(True)
            cap_item.setFont(font)
            self.ozet_table.setItem(row, 0, cap_item)

            # Toplam uzunluk
            uzunluk_item = QTableWidgetItem(f"{ozet['toplam_uzunluk_m']:.2f}")
            uzunluk_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.ozet_table.setItem(row, 1, uzunluk_item)

            # Toplam ağırlık kg
            kg_item = QTableWidgetItem(f"{ozet['toplam_agirlik_kg']:.2f}")
            kg_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.ozet_table.setItem(row, 2, kg_item)

            # Toplam ağırlık ton
            ton_item = QTableWidgetItem(f"{ozet['toplam_agirlik_ton']:.3f}")
            ton_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            ton_item.setBackground(QColor(144, 238, 144))  # Açık yeşil
            self.ozet_table.setItem(row, 3, ton_item)

            # Adet
            adet_item = QTableWidgetItem(f"{ozet['adet_sayisi']}")
            adet_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ozet_table.setItem(row, 4, adet_item)

            toplam_uzunluk += ozet['toplam_uzunluk_m']
            toplam_agirlik_kg += ozet['toplam_agirlik_kg']
            toplam_adet += ozet['adet_sayisi']

        # TOPLAM satırı
        row = len(ozetler)
        toplam_item = QTableWidgetItem("TOPLAM")
        toplam_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        toplam_item.setBackground(QColor(52, 152, 219))  # Mavi
        toplam_item.setForeground(QColor(255, 255, 255))  # Beyaz yazı
        font = toplam_item.font()
        font.setBold(True)
        font.setPointSize(13)
        toplam_item.setFont(font)
        self.ozet_table.setItem(row, 0, toplam_item)

        for col in range(1, 5):
            item = QTableWidgetItem()
            item.setBackground(QColor(52, 152, 219))
            item.setForeground(QColor(255, 255, 255))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter if col < 4 else Qt.AlignmentFlag.AlignCenter)

            if col == 1:
                item.setText(f"{toplam_uzunluk:.2f}")
            elif col == 2:
                item.setText(f"{toplam_agirlik_kg:.2f}")
            elif col == 3:
                item.setText(f"{toplam_agirlik_kg/1000:.3f}")
            elif col == 4:
                item.setText(f"{toplam_adet}")

            self.ozet_table.setItem(row, col, item)

    def tip_ozet_table_guncelle(self):
        """Temel tipi özet tablosunu güncelle"""
        if not self.current_proje_id:
            return

        # Her temel tipi için özet
        tipler = ['RADYE', 'BAG_KIRISI', 'KOLON_FILIZI']
        tip_adlar = ['Radye Temel', 'Bağ Kirişi', 'Kolon Filizi']

        self.tip_ozet_table.setRowCount(len(tipler) + 1)  # +1 TOPLAM için

        genel_toplam_adet = 0
        genel_toplam_kg = 0

        for row, (tip, tip_adi) in enumerate(zip(tipler, tip_adlar)):
            detaylar = self.engine.get_detay_liste(self.current_proje_id, tip)

            adet = len(detaylar)
            toplam_kg = sum(d['toplam_agirlik_kg'] for d in detaylar)
            toplam_ton = toplam_kg / 1000.0

            # Temel tipi
            self.tip_ozet_table.setItem(row, 0, QTableWidgetItem(tip_adi))

            # Adet
            adet_item = QTableWidgetItem(f"{adet}")
            adet_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tip_ozet_table.setItem(row, 1, adet_item)

            # Ağırlık kg
            kg_item = QTableWidgetItem(f"{toplam_kg:.2f}")
            kg_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tip_ozet_table.setItem(row, 2, kg_item)

            # Ağırlık ton
            ton_item = QTableWidgetItem(f"{toplam_ton:.3f}")
            ton_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            ton_item.setBackground(QColor(255, 218, 185))  # Açık turuncu
            self.tip_ozet_table.setItem(row, 3, ton_item)

            genel_toplam_adet += adet
            genel_toplam_kg += toplam_kg

        # TOPLAM satırı
        row = len(tipler)
        toplam_item = QTableWidgetItem("GENEL TOPLAM")
        toplam_item.setBackground(QColor(230, 126, 34))  # Turuncu
        toplam_item.setForeground(QColor(255, 255, 255))
        font = toplam_item.font()
        font.setBold(True)
        font.setPointSize(13)
        toplam_item.setFont(font)
        self.tip_ozet_table.setItem(row, 0, toplam_item)

        for col in range(1, 4):
            item = QTableWidgetItem()
            item.setBackground(QColor(230, 126, 34))
            item.setForeground(QColor(255, 255, 255))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter if col > 1 else Qt.AlignmentFlag.AlignCenter)

            if col == 1:
                item.setText(f"{genel_toplam_adet}")
            elif col == 2:
                item.setText(f"{genel_toplam_kg:.2f}")
            elif col == 3:
                item.setText(f"{genel_toplam_kg/1000:.3f}")

            self.tip_ozet_table.setItem(row, col, item)

    def filtre_uygula(self, filtre_tipi: str):
        """Filtre uygula"""
        self.detay_table_guncelle(filtre_tipi)

    def excel_export(self):
        """Excel (CSV) formatında export et"""
        if not self.current_proje_id:
            QMessageBox.warning(self, "Uyarı", "Önce bir DXF dosyası yükleyin!")
            return

        dosya_adi, _ = QFileDialog.getSaveFileName(
            self,
            "CSV Olarak Kaydet",
            "temel_demir_metraj.csv",
            "CSV Dosyaları (*.csv)"
        )

        if not dosya_adi:
            return

        try:
            with open(dosya_adi, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)

                # Başlık
                writer.writerow(["TEMEL DEMİR METRAJ LİSTESİ"])
                writer.writerow([])

                # Detaylı liste
                writer.writerow(["DETAYLI LİSTE"])
                writer.writerow([
                    "Temel Tipi", "Temel Adı", "Poz No", "Donatı Tipi",
                    "Çap", "Uzunluk (cm)", "Adet", "Toplam (m)",
                    "Birim Ağırlık (kg/m)", "Toplam Ağırlık (kg)"
                ])

                detaylar = self.engine.get_detay_liste(self.current_proje_id)
                for demir in detaylar:
                    tip_map = {
                        "RADYE": "Radye",
                        "BAG_KIRISI": "Bağ Kirişi",
                        "KOLON_FILIZI": "Kolon Filizi"
                    }
                    writer.writerow([
                        tip_map.get(demir['temel_tipi'], demir['temel_tipi']),
                        demir['temel_adi'],
                        demir['pozisyon_no'] or '-',
                        demir['donati_tipi'],
                        f"Ø{demir['cap']}",
                        demir['uzunluk_cm'],
                        demir['adet'],
                        f"{demir['toplam_uzunluk_m']:.2f}",
                        f"{demir['birim_agirlik_kg_m']:.3f}",
                        f"{demir['toplam_agirlik_kg']:.2f}"
                    ])

                writer.writerow([])
                writer.writerow([])

                # Özet
                writer.writerow(["ÖZET (ÇAPA GÖRE)"])
                writer.writerow([
                    "Demir Çapı", "Toplam Uzunluk (m)", "Toplam Ağırlık (kg)",
                    "Toplam Ağırlık (ton)", "Adet Sayısı"
                ])

                ozetler = self.engine.get_ozet(self.current_proje_id)
                for ozet in ozetler:
                    writer.writerow([
                        f"Ø{ozet['cap']}",
                        f"{ozet['toplam_uzunluk_m']:.2f}",
                        f"{ozet['toplam_agirlik_kg']:.2f}",
                        f"{ozet['toplam_agirlik_ton']:.3f}",
                        ozet['adet_sayisi']
                    ])

            QMessageBox.information(self, "Başarılı", f"Dosya kaydedildi:\n{dosya_adi}")

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{str(e)}")

    def temizle(self):
        """Tabloları temizle"""
        self.detay_table.setRowCount(0)
        self.ozet_table.setRowCount(0)
        self.tip_ozet_table.setRowCount(0)
        self.current_proje_id = None
        self.dosya_label.setText("Dosya seçilmedi")
        self.dosya_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
