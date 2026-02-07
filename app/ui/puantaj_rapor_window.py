"""
Puantaj Rapor Penceresi - Günlük/Haftalık/Aylık Özet
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QDateEdit,
    QComboBox, QHeaderView, QMessageBox, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont
from datetime import datetime, timedelta
import sqlite3
import os


class PuantajRaporWindow(QWidget):
    """Puantaj rapor penceresi"""

    def __init__(self, db=None):
        super().__init__()
        self.db = db
        self.db_path = self._get_db_path()
        self.init_ui()
        self.load_data()

    def _get_db_path(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, "data", "metraj.db")

    def init_ui(self):
        self.setWindowTitle("Puantaj Raporu")
        self.setMinimumSize(900, 600)

        layout = QVBoxLayout()

        # Başlık
        title = QLabel("📊 Puantaj Raporu")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        # Filtreler
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Dönem:"))
        self.period_combo = QComboBox()
        self.period_combo.addItems(["Günlük", "Haftalık", "Aylık"])
        self.period_combo.currentIndexChanged.connect(self.load_data)
        filter_layout.addWidget(self.period_combo)

        filter_layout.addWidget(QLabel("Tarih:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(self.load_data)
        filter_layout.addWidget(self.date_edit)

        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.clicked.connect(self.load_data)
        filter_layout.addWidget(refresh_btn)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Özet kartlar
        self.cards_layout = QHBoxLayout()
        self.card_isci = self._create_card("👷 Toplam İşçi", "0", "#3498db")
        self.card_gun = self._create_card("📅 Çalışılan Gün", "0", "#27ae60")
        self.card_mesai = self._create_card("⏰ Mesai Saat", "0", "#e67e22")
        self.card_toplam = self._create_card("💰 Toplam Ödeme", "0 ₺", "#9b59b6")

        self.cards_layout.addWidget(self.card_isci)
        self.cards_layout.addWidget(self.card_gun)
        self.cards_layout.addWidget(self.card_mesai)
        self.cards_layout.addWidget(self.card_toplam)
        layout.addLayout(self.cards_layout)

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "İşçi", "Ustalık", "Gün", "Yevmiye", "Mesai", "Günlük Ücret", "Toplam"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("alternate-background-color: #f5f5f5;")
        layout.addWidget(self.table)

        self.setLayout(layout)

    def _create_card(self, title, value, color):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 10px;
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout()

        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-size: 12px;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet("color: white; font-size: 22px; font-weight: bold;")
        layout.addWidget(value_label)

        frame.setLayout(layout)
        return frame

    def _update_card(self, card, value):
        label = card.findChild(QLabel, "value")
        if label:
            label.setText(str(value))

    def load_data(self):
        period = self.period_combo.currentText()
        selected_date = self.date_edit.date().toPyDate()

        # Tarih aralığını hesapla
        if period == "Günlük":
            start_date = selected_date
            end_date = selected_date
        elif period == "Haftalık":
            start_date = selected_date - timedelta(days=selected_date.weekday())
            end_date = start_date + timedelta(days=6)
        else:  # Aylık
            start_date = selected_date.replace(day=1)
            next_month = start_date.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT i.id, i.ad_soyad, i.ustalik, i.gunluk_ucret,
                       COUNT(p.id) as gun_sayisi,
                       SUM(CASE
                           WHEN p.calisma_durumu = 'tam_gun' THEN 1
                           WHEN p.calisma_durumu = 'yarim_gun' THEN 0.5
                           ELSE 0 END) as yevmiye,
                       SUM(COALESCE(p.mesai_saat, 0)) as mesai
                FROM isci i
                LEFT JOIN puantaj p ON i.id = p.isci_id
                    AND p.tarih BETWEEN ? AND ?
                WHERE i.aktif = 1
                GROUP BY i.id
                ORDER BY i.ad_soyad
            ''', (start_date.isoformat(), end_date.isoformat()))

            rows = cursor.fetchall()
            conn.close()

            # Tabloyu doldur
            self.table.setRowCount(len(rows))

            toplam_isci = 0
            toplam_gun = 0
            toplam_mesai = 0
            toplam_odeme = 0

            for i, row in enumerate(rows):
                yevmiye = row['yevmiye'] or 0
                mesai = row['mesai'] or 0
                ucret = row['gunluk_ucret'] or 0
                mesai_ucret = ucret / 8 * 1.5  # Mesai 1.5 kat
                satir_toplam = (yevmiye * ucret) + (mesai * mesai_ucret)

                self.table.setItem(i, 0, QTableWidgetItem(row['ad_soyad']))
                self.table.setItem(i, 1, QTableWidgetItem(row['ustalik'] or '-'))
                self.table.setItem(i, 2, QTableWidgetItem(str(row['gun_sayisi'] or 0)))
                self.table.setItem(i, 3, QTableWidgetItem(str(yevmiye)))
                self.table.setItem(i, 4, QTableWidgetItem(f"{mesai:.1f} saat"))
                self.table.setItem(i, 5, QTableWidgetItem(f"{ucret:,.0f} ₺"))

                toplam_item = QTableWidgetItem(f"{satir_toplam:,.0f} ₺")
                toplam_item.setForeground(QColor("#27ae60"))
                toplam_item.setFont(QFont("", -1, QFont.Weight.Bold))
                self.table.setItem(i, 6, toplam_item)

                if yevmiye > 0:
                    toplam_isci += 1
                toplam_gun += yevmiye
                toplam_mesai += mesai
                toplam_odeme += satir_toplam

            # Kartları güncelle
            self._update_card(self.card_isci, toplam_isci)
            self._update_card(self.card_gun, f"{toplam_gun:.1f}")
            self._update_card(self.card_mesai, f"{toplam_mesai:.1f}")
            self._update_card(self.card_toplam, f"{toplam_odeme:,.0f} ₺")

        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Veri yüklenemedi: {e}")
