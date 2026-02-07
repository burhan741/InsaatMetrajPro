"""
Tedarikçi Fiyat Karşılaştırma Sekmesi
Çeşitli tedarikçilerden fiyat karşılaştırma ve analiz
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QTextEdit, QMessageBox,
    QHeaderView, QDoubleSpinBox, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from typing import Optional, List, Dict
from datetime import datetime
import logging

from app.core.database import DatabaseManager
from app.core.tedarikci_engine import TedarikciEngine

logger = logging.getLogger(__name__)


class TedarikciWindow(QWidget):
    """Tedarikçi fiyat karşılaştırma widget'i"""

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.engine = TedarikciEngine()
        self.init_ui()
        self.load_tedarikci_listesi()

    def init_ui(self):
        """UI elementlerini oluştur"""
        layout = QVBoxLayout()

        # Başlık
        baslik = QLabel("🏪 Tedarikçi Fiyat Karşılaştırma")
        baslik.setStyleSheet("font-size: 18pt; font-weight: bold; margin: 10px;")
        layout.addWidget(baslik)

        # Arama formu
        form_group = self._create_arama_formu()
        layout.addWidget(form_group)

        # Karşılaştırma sonuçları tablosu
        sonuc_group = self._create_karsilastirma_tablosu()
        layout.addWidget(sonuc_group)

        # Tasarruf bilgisi
        tasarruf_group = self._create_tasarruf_alani()
        layout.addWidget(tasarruf_group)

        # Tedarikçi yönetimi
        yonetim_group = self._create_tedarikci_yonetimi()
        layout.addWidget(yonetim_group)

        self.setLayout(layout)

    def _create_arama_formu(self) -> QGroupBox:
        """Arama formu oluştur"""
        group = QGroupBox("Fiyat Karşılaştırma")
        layout = QFormLayout()

        # Malzeme kodu
        self.malzeme_kodu_input = QLineEdit()
        self.malzeme_kodu_input.setPlaceholderText("Örn: BETON-C30, DEMIR-S420")
        layout.addRow("Malzeme Kodu:", self.malzeme_kodu_input)

        # Miktar
        self.miktar_input = QDoubleSpinBox()
        self.miktar_input.setRange(1, 999999)
        self.miktar_input.setDecimals(2)
        self.miktar_input.setValue(10)
        layout.addRow("Miktar:", self.miktar_input)

        # Karşılaştır butonu
        karsilastir_btn = QPushButton("🔍 Fiyatları Karşılaştır")
        karsilastir_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                font-size: 14pt;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        karsilastir_btn.clicked.connect(self.karsilastir_fiyatlar)
        layout.addRow("", karsilastir_btn)

        group.setLayout(layout)
        return group

    def _create_karsilastirma_tablosu(self) -> QGroupBox:
        """Karşılaştırma sonuçları tablosu"""
        group = QGroupBox("Fiyat Karşılaştırma Sonuçları")
        layout = QVBoxLayout()

        self.karsilastirma_table = QTableWidget()
        self.karsilastirma_table.setColumnCount(9)
        self.karsilastirma_table.setHorizontalHeaderLabels([
            "Sıra", "Tedarikçi", "Birim Fiyat", "İndirim %",
            "İndirimli Fiyat", "KDV", "Genel Toplam",
            "Teslimat", "Durum"
        ])

        # Kolon genişliklerini ayarla
        header = self.karsilastirma_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.karsilastirma_table.setAlternatingRowColors(True)

        layout.addWidget(self.karsilastirma_table)

        # Export butonu
        export_btn = QPushButton("📤 Excel'e Aktar")
        export_btn.clicked.connect(self.export_karsilastirma)
        layout.addWidget(export_btn)

        group.setLayout(layout)
        return group

    def _create_tasarruf_alani(self) -> QGroupBox:
        """Tasarruf bilgisi alanı"""
        group = QGroupBox("💰 Tasarruf Analizi")
        layout = QVBoxLayout()

        self.tasarruf_text = QTextEdit()
        self.tasarruf_text.setReadOnly(True)
        self.tasarruf_text.setMaximumHeight(150)
        self.tasarruf_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #e0e0e0;
                border: 1px solid #3a3a4a;
                border-radius: 5px;
                padding: 10px;
                font-size: 11pt;
            }
        """)
        layout.addWidget(self.tasarruf_text)

        group.setLayout(layout)
        return group

    def _create_tedarikci_yonetimi(self) -> QGroupBox:
        """Tedarikçi yönetimi"""
        group = QGroupBox("Tedarikçi Listesi")
        layout = QVBoxLayout()

        self.tedarikci_table = QTableWidget()
        self.tedarikci_table.setColumnCount(4)
        self.tedarikci_table.setHorizontalHeaderLabels([
            "ID", "Tedarikçi Adı", "Durum", "İşlemler"
        ])
        self.tedarikci_table.setMaximumHeight(200)
        layout.addWidget(self.tedarikci_table)

        # Butonlar
        btn_layout = QHBoxLayout()

        yenile_btn = QPushButton("🔄 Listeyi Yenile")
        yenile_btn.clicked.connect(self.load_tedarikci_listesi)
        btn_layout.addWidget(yenile_btn)

        ekle_btn = QPushButton("➕ Tedarikçi Ekle")
        ekle_btn.clicked.connect(self.tedarikci_ekle)
        btn_layout.addWidget(ekle_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        group.setLayout(layout)
        return group

    def karsilastir_fiyatlar(self):
        """Fiyatları karşılaştır"""
        malzeme_kodu = self.malzeme_kodu_input.text().strip()
        miktar = self.miktar_input.value()

        if not malzeme_kodu:
            QMessageBox.warning(self, "Uyarı", "Lütfen malzeme kodu girin!")
            return

        try:
            # Fiyatları karşılaştır
            fiyatlar = self.engine.karsilastir_fiyatlar(malzeme_kodu, miktar)

            if not fiyatlar:
                QMessageBox.information(self, "Bilgi", "Fiyat bulunamadı!")
                return

            # Tabloyu doldur
            self._doldur_karsilastirma_tablosu(fiyatlar)

            # Tasarruf bilgisini göster
            tasarruf = self.engine.hesapla_tasarruf(malzeme_kodu, miktar)
            self._goster_tasarruf(tasarruf)

        except Exception as e:
            logger.error(f"Karşılaştırma hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Karşılaştırma sırasında hata:\n{str(e)}")

    def _doldur_karsilastirma_tablosu(self, fiyatlar: List[Dict]):
        """Karşılaştırma tablosunu doldur"""
        self.karsilastirma_table.setRowCount(len(fiyatlar))

        for row_idx, fiyat in enumerate(fiyatlar):
            # Sıra
            sira_item = QTableWidgetItem(str(row_idx + 1))
            sira_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.karsilastirma_table.setItem(row_idx, 0, sira_item)

            # Tedarikçi
            tedarikci_item = QTableWidgetItem(fiyat['tedarikci_ad'])
            if fiyat.get('en_ucuz'):
                tedarikci_item.setBackground(QColor(76, 175, 80, 50))  # Yeşil
                tedarikci_item.setText(f"⭐ {fiyat['tedarikci_ad']}")
            elif fiyat.get('en_pahali'):
                tedarikci_item.setBackground(QColor(244, 67, 54, 50))  # Kırmızı
            self.karsilastirma_table.setItem(row_idx, 1, tedarikci_item)

            # Birim fiyat
            self.karsilastirma_table.setItem(row_idx, 2,
                QTableWidgetItem(f"{fiyat['birim_fiyat']:,.2f} TL"))

            # İndirim
            self.karsilastirma_table.setItem(row_idx, 3,
                QTableWidgetItem(f"%{fiyat['indirim_orani']:.0f}"))

            # İndirimli fiyat
            self.karsilastirma_table.setItem(row_idx, 4,
                QTableWidgetItem(f"{fiyat['indirimli_birim_fiyat']:,.2f} TL"))

            # KDV
            self.karsilastirma_table.setItem(row_idx, 5,
                QTableWidgetItem(f"{fiyat['kdv']:,.2f} TL"))

            # Genel toplam
            toplam_item = QTableWidgetItem(f"{fiyat['genel_toplam']:,.2f} TL")
            toplam_item.setFont(toplam_item.font())
            font = toplam_item.font()
            font.setBold(True)
            toplam_item.setFont(font)
            self.karsilastirma_table.setItem(row_idx, 6, toplam_item)

            # Teslimat
            self.karsilastirma_table.setItem(row_idx, 7,
                QTableWidgetItem(fiyat['teslimat_suresi']))

            # Stok durumu
            stok_item = QTableWidgetItem(fiyat['stok_durumu'])
            if fiyat['stok_durumu'] == 'Stokta var':
                stok_item.setForeground(QColor(76, 175, 80))  # Yeşil
            self.karsilastirma_table.setItem(row_idx, 8, stok_item)

    def _goster_tasarruf(self, tasarruf: Dict):
        """Tasarruf bilgisini göster"""
        html = f"""
        <div style="font-family: 'Segoe UI', Arial; padding: 15px;">
            <h2 style="color: #4CAF50;">💰 Tasarruf Analizi</h2>

            <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                <tr style="background-color: #2a2a3a;">
                    <td style="padding: 8px; border: 1px solid #3a3a4a;"><b>En Ucuz Tedarikçi:</b></td>
                    <td style="padding: 8px; border: 1px solid #3a3a4a; color: #4CAF50;">
                        {tasarruf['en_ucuz_tedarikci']} - {tasarruf['en_ucuz_fiyat']:,.2f} TL
                    </td>
                </tr>
                <tr style="background-color: #1e1e2e;">
                    <td style="padding: 8px; border: 1px solid #3a3a4a;"><b>En Pahalı Tedarikçi:</b></td>
                    <td style="padding: 8px; border: 1px solid #3a3a4a; color: #F44336;">
                        {tasarruf['en_pahali_tedarikci']} - {tasarruf['en_pahali_fiyat']:,.2f} TL
                    </td>
                </tr>
                <tr style="background-color: #2a2a3a;">
                    <td style="padding: 8px; border: 1px solid #3a3a4a;"><b>Tasarruf Miktarı:</b></td>
                    <td style="padding: 8px; border: 1px solid #3a3a4a; color: #FF9800; font-size: 12pt;">
                        <b>{tasarruf['tasarruf']:,.2f} TL (%{tasarruf['tasarruf_yuzde']:.2f})</b>
                    </td>
                </tr>
            </table>

            <p style="margin-top: 15px; padding: 10px; background-color: #2196F3; border-radius: 5px; color: white;">
                <b>ℹ️ {tasarruf['mesaj']}</b>
            </p>
        </div>
        """
        self.tasarruf_text.setHtml(html)

    def load_tedarikci_listesi(self):
        """Tedarikçi listesini yükle"""
        try:
            tedarikci_listesi = self.engine.get_tedarikci_listesi()

            self.tedarikci_table.setRowCount(len(tedarikci_listesi))

            for row_idx, tedarikci in enumerate(tedarikci_listesi):
                self.tedarikci_table.setItem(row_idx, 0,
                    QTableWidgetItem(str(tedarikci['id'])))

                self.tedarikci_table.setItem(row_idx, 1,
                    QTableWidgetItem(tedarikci['ad']))

                durum = "✅ Aktif" if tedarikci['aktif'] else "❌ Pasif"
                durum_item = QTableWidgetItem(durum)
                if tedarikci['aktif']:
                    durum_item.setForeground(QColor(76, 175, 80))
                else:
                    durum_item.setForeground(QColor(244, 67, 54))
                self.tedarikci_table.setItem(row_idx, 2, durum_item)

                self.tedarikci_table.setItem(row_idx, 3,
                    QTableWidgetItem("🔧 Düzenle"))

        except Exception as e:
            logger.error(f"Tedarikçi listesi yükleme hatası: {e}")

    def tedarikci_ekle(self):
        """Yeni tedarikçi ekle"""
        QMessageBox.information(self, "Bilgi",
            "Tedarikçi ekleme özelliği yakında eklenecek!\n\n"
            "Şu an örnek tedarikçiler gösterilmektedir.")

    def export_karsilastirma(self):
        """Karşılaştırmayı Excel'e aktar"""
        QMessageBox.information(self, "Bilgi", "Excel export özelliği yakında eklenecek!")
