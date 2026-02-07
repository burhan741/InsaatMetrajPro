"""
Kiriş Demiri Metraj Window
DXF dosyalarından kiriş donatı bilgilerini okur ve gösterir
"""

import logging
import os
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QTabWidget,
    QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from app.core.database import DatabaseManager
from app.core.kiris_demiri_engine import KirisDemiriEngine

logger = logging.getLogger(__name__)


class KirisDemiriWindow(QWidget):
    """Kiriş demiri metraj penceresi"""

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.engine = KirisDemiriEngine()
        self.kiris_verileri = None
        self.dosya_yolu = ""

        self.init_ui()

    def init_ui(self):
        """UI'ı oluştur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Başlık
        layout.addWidget(self._create_title())

        # Dosya seçimi
        layout.addWidget(self._create_file_selection())

        # Sonuç tabları
        self.result_tabs = self._create_result_tabs()
        layout.addWidget(self.result_tabs)

        # Aksiyon butonları
        layout.addWidget(self._create_action_buttons())

    def _create_title(self) -> QLabel:
        """Başlık oluştur"""
        title = QLabel("🏗️ Kiriş Demiri Metraj (DXF)")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: #00BFFF;
                padding: 15px;
                background-color: #1a1a2e;
                border-radius: 8px;
            }
        """)
        return title

    def _create_file_selection(self) -> QGroupBox:
        """Dosya seçimi grubu oluştur"""
        group = QGroupBox("DXF Dosyası Seçimi")
        group.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        group.setStyleSheet("""
            QGroupBox {
                background-color: #16213e;
                border: 2px solid #00BFFF;
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
                color: #00BFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        layout = QHBoxLayout()

        # Dosya yolu input
        self.dosya_input = QLineEdit()
        self.dosya_input.setPlaceholderText("DXF dosyası seçin...")
        self.dosya_input.setReadOnly(True)
        self.dosya_input.setMinimumHeight(40)
        self.dosya_input.setStyleSheet("""
            QLineEdit {
                background-color: #0f1419;
                color: white;
                border: 1px solid #00BFFF;
                border-radius: 5px;
                padding: 8px;
                font-size: 11pt;
            }
        """)
        layout.addWidget(self.dosya_input, 3)

        # Dosya seç butonu
        dosya_sec_btn = QPushButton("📁 Dosya Seç")
        dosya_sec_btn.setMinimumHeight(40)
        dosya_sec_btn.setMinimumWidth(120)
        dosya_sec_btn.clicked.connect(self.dosya_sec)
        dosya_sec_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
        """)
        layout.addWidget(dosya_sec_btn)

        # Oku butonu
        self.oku_btn = QPushButton("📊 DXF Oku")
        self.oku_btn.setMinimumHeight(40)
        self.oku_btn.setMinimumWidth(120)
        self.oku_btn.setEnabled(False)
        self.oku_btn.clicked.connect(self.dxf_oku)
        self.oku_btn.setStyleSheet("""
            QPushButton {
                background-color: #00cc66;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00a352;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        layout.addWidget(self.oku_btn)

        group.setLayout(layout)
        return group

    def _create_result_tabs(self) -> QTabWidget:
        """Sonuç tablarını oluştur"""
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #00BFFF;
                border-radius: 5px;
                background-color: #16213e;
            }
            QTabBar::tab {
                background-color: #1a1a2e;
                color: white;
                border: 1px solid #00BFFF;
                padding: 10px 20px;
                margin-right: 2px;
                font-size: 11pt;
            }
            QTabBar::tab:selected {
                background-color: #00BFFF;
                color: #1a1a2e;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #0088cc;
            }
        """)

        # Tab 1: Detaylı Liste
        self.detay_table = self._create_table([
            "Kiriş Adı", "Donatı Tipi", "Adet", "Çap (mm)",
            "Aralık (cm)", "Uzunluk (cm)", "Toplam Boy (m)", "Ağırlık (kg)"
        ])
        tabs.addTab(self.detay_table, "📋 Detaylı Liste")

        # Tab 2: Çap Bazında Özet
        self.cap_table = self._create_table([
            "Çap", "Adet", "Toplam Boy (m)", "Birim Ağırlık (kg/m)", "Toplam Ağırlık (kg)"
        ])
        tabs.addTab(self.cap_table, "📊 Çap Bazında Özet")

        # Tab 3: Kiriş Bazında Özet
        self.kiris_table = self._create_table([
            "Kiriş Adı", "Boyuna Donatı", "Etriye", "Toplam Ağırlık (kg)"
        ])
        tabs.addTab(self.kiris_table, "🏗️ Kiriş Bazında Özet")

        return tabs

    def _create_table(self, headers: list) -> QTableWidget:
        """Tablo oluştur"""
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setStyleSheet("""
            QTableWidget {
                background-color: #0f1419;
                color: white;
                gridline-color: #00BFFF;
                border: none;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #00BFFF;
                color: #1a1a2e;
            }
            QHeaderView::section {
                background-color: #1a1a2e;
                color: #00BFFF;
                padding: 10px;
                border: 1px solid #00BFFF;
                font-weight: bold;
                font-size: 11pt;
            }
            QTableWidget::item:alternate {
                background-color: #16213e;
            }
        """)
        return table

    def _create_action_buttons(self) -> QGroupBox:
        """Aksiyon butonları oluştur"""
        group = QGroupBox("İşlemler")
        group.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        group.setStyleSheet("""
            QGroupBox {
                background-color: #16213e;
                border: 2px solid #00BFFF;
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
                color: #00BFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        layout = QHBoxLayout()

        # Excel export butonu
        self.excel_btn = QPushButton("📊 Excel'e Aktar")
        self.excel_btn.setMinimumHeight(40)
        self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self.excel_aktar)
        self.excel_btn.setStyleSheet(self._get_button_style("#00aa44"))
        layout.addWidget(self.excel_btn)

        # Veritabanına kaydet butonu
        self.kaydet_btn = QPushButton("💾 Veritabanına Kaydet")
        self.kaydet_btn.setMinimumHeight(40)
        self.kaydet_btn.setEnabled(False)
        self.kaydet_btn.clicked.connect(self.veritabanina_kaydet)
        self.kaydet_btn.setStyleSheet(self._get_button_style("#0066cc"))
        layout.addWidget(self.kaydet_btn)

        group.setLayout(layout)
        return group

    def _get_button_style(self, color: str) -> str:
        """Buton stili döndür"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
            QPushButton:disabled {{
                background-color: #555;
            }}
        """

    def dosya_sec(self):
        """DXF dosyası seç"""
        dosya, _ = QFileDialog.getOpenFileName(
            self,
            "DXF Dosyası Seç",
            "",
            "DXF Dosyaları (*.dxf);;Tüm Dosyalar (*.*)"
        )

        if dosya:
            self.dosya_yolu = dosya
            self.dosya_input.setText(dosya)
            self.oku_btn.setEnabled(True)
            logger.info(f"Dosya seçildi: {dosya}")

    def dxf_oku(self):
        """DXF dosyasını oku ve parse et"""
        if not self.dosya_yolu or not os.path.exists(self.dosya_yolu):
            QMessageBox.warning(self, "Uyarı", "Lütfen geçerli bir DXF dosyası seçin")
            return

        try:
            # İşlemi başlat
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            logger.info(f"DXF okunuyor: {self.dosya_yolu}")
            sonuc = self.engine.dxf_oku(self.dosya_yolu)

            QApplication.restoreOverrideCursor()

            if sonuc['status'] == 'error':
                QMessageBox.critical(self, "Hata", sonuc['error'])
                return

            if sonuc['status'] == 'warning':
                QMessageBox.warning(self, "Uyarı", sonuc.get('message', 'Kiriş bulunamadı'))
                return

            # Verileri sakla
            self.kiris_verileri = sonuc

            # Tabloları doldur
            self._fill_detayli_tablo(sonuc['kirisler'])
            self._fill_cap_ozeti(sonuc['ozet_cap_bazinda'])
            self._fill_kiris_ozeti(sonuc['ozet_kiris_bazinda'])

            # Butonları aktif et
            self.excel_btn.setEnabled(True)
            self.kaydet_btn.setEnabled(True)

            # Başarı mesajı
            QMessageBox.information(
                self,
                "Başarılı",
                f"{sonuc['message']}\n\n"
                f"Toplam Ağırlık: {sonuc['toplam_agirlik_kg']:.2f} kg\n"
                f"Toplam Adet: {sonuc['toplam_adet']}"
            )

        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.exception("DXF okuma hatası")
            QMessageBox.critical(self, "Hata", f"DXF okuma hatası:\n{str(e)}")

    def _fill_detayli_tablo(self, kirisler: list):
        """Detaylı tabloyu doldur"""
        self.detay_table.setRowCount(0)

        # Donatı tipi Türkçe çevirisi
        tip_map = {
            'ust_montaj': 'Üst Montaj',
            'ust_ilave': 'Üst İlave',
            'govde': 'Gövde',
            'pilye': 'Pilye',
            'alt_montaj': 'Alt Montaj',
            'alt_ilave': 'Alt İlave',
            'etriye': 'Etriye'
        }

        for kiris in kirisler:
            kiris_adi = kiris.get('ad', '')

            # Tüm donatı tiplerini işle
            donati_tipleri = ['ust_montaj', 'ust_ilave', 'govde', 'pilye',
                            'alt_montaj', 'alt_ilave', 'etriyeler']

            for tip_key in donati_tipleri:
                donatilar = kiris.get(tip_key, [])

                for donati in donatilar:
                    row = self.detay_table.rowCount()
                    self.detay_table.insertRow(row)

                    # Kiriş adı
                    self.detay_table.setItem(row, 0, QTableWidgetItem(kiris_adi))

                    # Donatı tipi (etriyeler -> etriye)
                    tip_display = tip_key.replace('ler', '')
                    tip_str = tip_map.get(tip_display, tip_display)
                    self.detay_table.setItem(row, 1, QTableWidgetItem(tip_str))

                    # Adet
                    adet = donati.get('adet', 0)
                    self.detay_table.setItem(row, 2, QTableWidgetItem(str(adet)))

                    # Çap
                    cap = donati.get('cap', 0)
                    self.detay_table.setItem(row, 3, QTableWidgetItem(f"ø{cap}"))

                    # Aralık
                    aralik = donati.get('aralik_cm', 0)
                    aralik_str = str(aralik) if aralik > 0 else "-"
                    self.detay_table.setItem(row, 4, QTableWidgetItem(aralik_str))

                    # Uzunluk
                    uzunluk = donati.get('uzunluk_cm', 0)
                    uzunluk_str = str(uzunluk) if uzunluk > 0 else "-"
                    self.detay_table.setItem(row, 5, QTableWidgetItem(uzunluk_str))

                    # Toplam boy (metre)
                    if uzunluk > 0:
                        toplam_boy = (adet * uzunluk) / 100.0
                        boy_str = f"{toplam_boy:.2f}"
                    else:
                        boy_str = "-"
                    self.detay_table.setItem(row, 6, QTableWidgetItem(boy_str))

                    # Ağırlık
                    agirlik = donati.get('toplam_agirlik_kg', 0)
                    agirlik_str = f"{agirlik:.2f}" if agirlik > 0 else "-"
                    self.detay_table.setItem(row, 7, QTableWidgetItem(agirlik_str))

        logger.info(f"Detaylı tablo dolduruldu: {self.detay_table.rowCount()} satır")

    def _fill_cap_ozeti(self, ozet: dict):
        """Çap bazında özet tablosunu doldur"""
        self.cap_table.setRowCount(0)

        # Çap numarasına göre sırala
        sorted_items = sorted(ozet.items(), key=lambda x: x[1]['cap'])

        for cap_key, veri in sorted_items:
            row = self.cap_table.rowCount()
            self.cap_table.insertRow(row)

            # Çap
            self.cap_table.setItem(row, 0, QTableWidgetItem(f"ø{veri['cap']}"))

            # Adet
            self.cap_table.setItem(row, 1, QTableWidgetItem(str(veri['adet'])))

            # Toplam boy
            self.cap_table.setItem(row, 2, QTableWidgetItem(f"{veri['toplam_boy_m']:.2f}"))

            # Birim ağırlık
            birim_agirlik = self.engine.DEMIR_ORANLAR.get(veri['cap'], 0)
            self.cap_table.setItem(row, 3, QTableWidgetItem(f"{birim_agirlik:.3f}"))

            # Toplam ağırlık
            self.cap_table.setItem(row, 4, QTableWidgetItem(f"{veri['agirlik_kg']:.2f}"))

        logger.info(f"Çap özeti dolduruldu: {self.cap_table.rowCount()} çap")

    def _fill_kiris_ozeti(self, ozet: list):
        """Kiriş bazında özet tablosunu doldur"""
        self.kiris_table.setRowCount(0)

        for kiris_data in ozet:
            row = self.kiris_table.rowCount()
            self.kiris_table.insertRow(row)

            # Kiriş adı
            self.kiris_table.setItem(row, 0, QTableWidgetItem(kiris_data['kiris_adi']))

            # Boyuna donatı
            self.kiris_table.setItem(row, 1, QTableWidgetItem(kiris_data['boyuna']))

            # Etriye
            self.kiris_table.setItem(row, 2, QTableWidgetItem(kiris_data['etriye']))

            # Toplam ağırlık
            self.kiris_table.setItem(row, 3, QTableWidgetItem(f"{kiris_data['toplam_agirlik_kg']:.2f}"))

        logger.info(f"Kiriş özeti dolduruldu: {self.kiris_table.rowCount()} kiriş")

    def excel_aktar(self):
        """Excel'e aktar"""
        if not self.kiris_verileri:
            QMessageBox.warning(self, "Uyarı", "Önce DXF dosyasını okuyun")
            return

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill

            # Dosya adı sor
            dosya, _ = QFileDialog.getSaveFileName(
                self,
                "Excel Dosyası Kaydet",
                "kiris_demiri_metraj.xlsx",
                "Excel Dosyaları (*.xlsx)"
            )

            if not dosya:
                return

            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            # Workbook oluştur
            wb = Workbook()
            wb.remove(wb.active)  # Varsayılan sheet'i sil

            # Sheet 1: Detaylı Liste
            ws1 = wb.create_sheet("Detaylı Liste")
            headers1 = ["Kiriş", "Tip", "Adet", "Çap", "Aralık", "Uzunluk", "Boy (m)", "Ağırlık (kg)"]
            ws1.append(headers1)

            tip_map = {
                'ust_montaj': 'Üst Montaj',
                'ust_ilave': 'Üst İlave',
                'govde': 'Gövde',
                'pilye': 'Pilye',
                'alt_montaj': 'Alt Montaj',
                'alt_ilave': 'Alt İlave',
                'etriye': 'Etriye'
            }

            for kiris in self.kiris_verileri['kirisler']:
                kiris_adi = kiris.get('ad', '')
                donati_tipleri = ['ust_montaj', 'ust_ilave', 'govde', 'pilye',
                                'alt_montaj', 'alt_ilave', 'etriyeler']

                for tip_key in donati_tipleri:
                    donatilar = kiris.get(tip_key, [])
                    for donati in donatilar:
                        adet = donati.get('adet', 0)
                        cap = donati.get('cap', 0)
                        aralik = donati.get('aralik_cm', 0)
                        uzunluk = donati.get('uzunluk_cm', 0)
                        agirlik = donati.get('toplam_agirlik_kg', 0)

                        tip_display = tip_key.replace('ler', '')
                        tip_str = tip_map.get(tip_display, tip_display)

                        toplam_boy = (adet * uzunluk) / 100.0 if uzunluk > 0 else 0

                        ws1.append([
                            kiris_adi,
                            tip_str,
                            adet,
                            cap,
                            aralik if aralik > 0 else "-",
                            uzunluk if uzunluk > 0 else "-",
                            f"{toplam_boy:.2f}" if uzunluk > 0 else "-",
                            f"{agirlik:.2f}" if agirlik > 0 else "-"
                        ])

            # Sheet 2: Çap Özeti
            ws2 = wb.create_sheet("Çap Özeti")
            headers2 = ["Çap", "Adet", "Toplam Boy (m)", "Birim Ağırlık (kg/m)", "Ağırlık (kg)"]
            ws2.append(headers2)

            for cap_key, veri in sorted(self.kiris_verileri['ozet_cap_bazinda'].items(), key=lambda x: x[1]['cap']):
                birim = self.engine.DEMIR_ORANLAR.get(veri['cap'], 0)
                ws2.append([
                    f"ø{veri['cap']}",
                    veri['adet'],
                    f"{veri['toplam_boy_m']:.2f}",
                    f"{birim:.3f}",
                    f"{veri['agirlik_kg']:.2f}"
                ])

            # Sheet 3: Kiriş Özeti
            ws3 = wb.create_sheet("Kiriş Özeti")
            headers3 = ["Kiriş", "Boyuna", "Etriye", "Ağırlık (kg)"]
            ws3.append(headers3)

            for kiris_data in self.kiris_verileri['ozet_kiris_bazinda']:
                ws3.append([
                    kiris_data['kiris_adi'],
                    kiris_data['boyuna'],
                    kiris_data['etriye'],
                    f"{kiris_data['toplam_agirlik_kg']:.2f}"
                ])

            # Formatla
            header_fill = PatternFill(start_color="00BFFF", end_color="00BFFF", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")

            for ws in [ws1, ws2, ws3]:
                for cell in ws[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")

                for column in ws.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(cell.value)
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    ws.column_dimensions[column_letter].width = adjusted_width

            # Kaydet
            wb.save(dosya)

            QApplication.restoreOverrideCursor()

            QMessageBox.information(self, "Başarılı", f"Excel dosyası oluşturuldu:\n{dosya}")
            logger.info(f"Excel dosyası oluşturuldu: {dosya}")

        except ImportError:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(
                self,
                "Kütüphane Eksik",
                "openpyxl kütüphanesi bulunamadı.\n\n"
                "Kurulum için:\npip install openpyxl"
            )
        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.exception("Excel export hatası")
            QMessageBox.critical(self, "Hata", f"Excel export hatası:\n{str(e)}")

    def veritabanina_kaydet(self):
        """Veritabanına kaydet"""
        if not self.kiris_verileri:
            QMessageBox.warning(self, "Uyarı", "Önce DXF dosyasını okuyun")
            return

        try:
            # Proje seçimi (basit dialog)
            from PyQt5.QtWidgets import QInputDialog

            proje_id, ok = QInputDialog.getInt(
                self,
                "Proje Seçimi",
                "Proje ID giriniz:",
                1, 1, 9999, 1
            )

            if not ok:
                return

            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            # Her kiriş için metraj kalemi oluştur
            kayit_sayisi = 0

            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                for kiris_ozet in self.kiris_verileri['ozet_kiris_bazinda']:
                    poz_no = kiris_ozet['kiris_adi']
                    tanim = f"{kiris_ozet['kiris_adi']} - Boyuna: {kiris_ozet['boyuna']}, Etriye: {kiris_ozet['etriye']}"
                    toplam_kg = kiris_ozet['toplam_agirlik_kg']

                    cursor.execute("""
                        INSERT INTO metraj_kalemleri
                        (proje_id, poz_no, tanim, miktar, birim, toplam, kategori, notlar)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        proje_id,
                        poz_no,
                        tanim,
                        toplam_kg,
                        'kg',
                        toplam_kg,  # Birim fiyat yok, sadece miktar
                        'Kiriş Demiri',
                        f'DXF: {os.path.basename(self.dosya_yolu)}'
                    ))
                    kayit_sayisi += 1

            QApplication.restoreOverrideCursor()

            QMessageBox.information(
                self,
                "Başarılı",
                f"{kayit_sayisi} kiriş kalemi veritabanına kaydedildi.\n"
                f"Proje ID: {proje_id}"
            )
            logger.info(f"{kayit_sayisi} kiriş kalemi kaydedildi (Proje: {proje_id})")

        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.exception("Veritabanı kayıt hatası")
            QMessageBox.critical(self, "Hata", f"Veritabanı kayıt hatası:\n{str(e)}")


# Test
if __name__ == "__main__":
    import sys
    from app.core.database import DatabaseManager

    app = QApplication(sys.argv)

    # Dark theme
    app.setStyle("Fusion")

    db = DatabaseManager()
    window = KirisDemiriWindow(db)
    window.setGeometry(100, 100, 1200, 800)
    window.setWindowTitle("Kiriş Demiri Metraj - Test")
    window.show()

    sys.exit(app.exec_())
