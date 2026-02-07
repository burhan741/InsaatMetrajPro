"""
Kolon Demiri Metraj Window
STA4CAD DXF dosyalarından kolon donatı bilgilerini gösterir
"""

import logging
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
    QTabWidget, QHeaderView, QLineEdit, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from app.core.kolon_demiri_engine import KolonDemiriEngine
from app.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class KolonDemiriWindow(QWidget):
    """Kolon Demiri Metraj penceresi"""

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.engine = KolonDemiriEngine()
        self.kolon_verileri = None
        self.dxf_dosya_yolu = None
        self.init_ui()

    def init_ui(self):
        """UI bileşenlerini oluştur"""
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Başlık
        title = self._create_title()
        layout.addWidget(title)

        # Dosya seçimi
        file_group = self._create_file_selection()
        layout.addWidget(file_group)

        # Sonuç tabloları (3 tab)
        self.tab_widget = self._create_result_tabs()
        layout.addWidget(self.tab_widget)

        # Alt butonlar
        button_layout = self._create_action_buttons()
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _create_title(self) -> QLabel:
        """Başlık oluştur"""
        title = QLabel("📊 Kolon Demiri Metraj (DXF)")
        font = QFont()
        font.setPointSize(16)
        font.setWeight(QFont.Weight.Bold)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #2c3e50; padding: 10px;")
        return title

    def _create_file_selection(self) -> QGroupBox:
        """Dosya seçim alanı"""
        group = QGroupBox("DXF Dosyası")
        layout = QHBoxLayout()

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("DXF dosyası seçin...")
        self.file_path_edit.setReadOnly(True)

        btn_select = QPushButton("📁 Dosya Seç")
        btn_select.clicked.connect(self.dosya_sec)
        btn_select.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)

        btn_read = QPushButton("📖 Oku")
        btn_read.clicked.connect(self.dxf_oku)
        btn_read.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)

        layout.addWidget(QLabel("Dosya:"))
        layout.addWidget(self.file_path_edit, 1)
        layout.addWidget(btn_select)
        layout.addWidget(btn_read)

        group.setLayout(layout)
        return group

    def _create_result_tabs(self) -> QTabWidget:
        """Sonuç tabloları için 3 tab oluştur"""
        tabs = QTabWidget()

        # Tab 1: Detaylı Liste
        self.table_detayli = QTableWidget()
        self.table_detayli.setColumnCount(7)
        self.table_detayli.setHorizontalHeaderLabels([
            "Kat", "Kolon", "Tip", "Adet", "Çap (mm)", "Uzunluk (cm)", "Ağırlık (kg)"
        ])
        self.table_detayli.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_detayli.horizontalHeader().setStretchLastSection(True)
        self.table_detayli.setAlternatingRowColors(True)
        tabs.addTab(self.table_detayli, "📋 Detaylı Liste")

        # Tab 2: Çap Bazında Özet
        self.table_cap_ozeti = QTableWidget()
        self.table_cap_ozeti.setColumnCount(4)
        self.table_cap_ozeti.setHorizontalHeaderLabels([
            "Çap (mm)", "Toplam Adet", "Toplam Boy (m)", "Ağırlık (kg)"
        ])
        self.table_cap_ozeti.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_cap_ozeti.horizontalHeader().setStretchLastSection(True)
        self.table_cap_ozeti.setAlternatingRowColors(True)
        tabs.addTab(self.table_cap_ozeti, "📊 Çap Bazında Özet")

        # Tab 3: Kolon Bazında Özet
        self.table_kolon_ozeti = QTableWidget()
        self.table_kolon_ozeti.setColumnCount(5)
        self.table_kolon_ozeti.setHorizontalHeaderLabels([
            "Kat", "Kolon", "Boyuna", "Çiroz", "Ağırlık (kg)"
        ])
        self.table_kolon_ozeti.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_kolon_ozeti.horizontalHeader().setStretchLastSection(True)
        self.table_kolon_ozeti.setAlternatingRowColors(True)
        tabs.addTab(self.table_kolon_ozeti, "🏛️ Kolon Bazında Özet")

        return tabs

    def _create_action_buttons(self) -> QHBoxLayout:
        """Alt butonlar"""
        layout = QHBoxLayout()
        layout.addStretch()

        btn_excel = QPushButton("📊 Excel'e Aktar")
        btn_excel.clicked.connect(self.excel_aktar)
        btn_excel.setStyleSheet("""
            QPushButton {
                background-color: #16a085;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138f75;
            }
        """)

        btn_pdf = QPushButton("📄 PDF Rapor")
        btn_pdf.clicked.connect(self.pdf_olustur)
        btn_pdf.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)

        btn_save = QPushButton("💾 Veritabanına Kaydet")
        btn_save.clicked.connect(self.veritabanina_kaydet)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)

        layout.addWidget(btn_excel)
        layout.addWidget(btn_pdf)
        layout.addWidget(btn_save)

        return layout

    def dosya_sec(self):
        """DXF dosyası seç"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "DXF Dosyası Seç",
            "",
            "DXF Dosyaları (*.dxf);;Tüm Dosyalar (*.*)"
        )

        if file_path:
            self.dxf_dosya_yolu = file_path
            self.file_path_edit.setText(file_path)
            logger.info(f"DXF dosyası seçildi: {file_path}")

    def dxf_oku(self):
        """DXF dosyasını oku ve tabloları doldur"""
        if not self.dxf_dosya_yolu:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir DXF dosyası seçin!")
            return

        if not os.path.exists(self.dxf_dosya_yolu):
            QMessageBox.critical(self, "Hata", "Seçilen dosya bulunamadı!")
            return

        try:
            self.setCursor(Qt.CursorShape.WaitCursor)
            logger.info(f"DXF okunuyor: {self.dxf_dosya_yolu}")

            # Engine ile oku
            sonuc = self.engine.dxf_oku(self.dxf_dosya_yolu)

            if sonuc['status'] == 'error':
                QMessageBox.critical(self, "Hata", sonuc.get('error', 'Bilinmeyen hata'))
                return

            if sonuc['status'] == 'warning':
                QMessageBox.warning(self, "Uyarı", sonuc.get('message', 'Veri bulunamadı'))
                return

            # Başarılı
            self.kolon_verileri = sonuc
            self._fill_detayli_tablo(sonuc['katlar'])
            self._fill_cap_ozeti(sonuc['ozet_cap_bazinda'])
            self._fill_kolon_ozeti(sonuc['ozet_kolon_bazinda'])

            QMessageBox.information(
                self,
                "Başarılı",
                f"{len(sonuc['katlar'])} kat kolon verisi okundu.\n"
                f"Toplam Ağırlık: {sonuc['toplam_agirlik_kg']:.2f} kg"
            )

            logger.info(f"DXF başarıyla okundu: {len(sonuc['katlar'])} kat")

        except Exception as e:
            logger.exception("DXF okuma hatası")
            QMessageBox.critical(self, "Hata", f"Beklenmeyen hata:\n{str(e)}")

        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def _fill_detayli_tablo(self, katlar):
        """Detaylı tablo doldur"""
        self.table_detayli.setRowCount(0)

        row = 0
        for kat in katlar:
            # Kolonlardaki donatılar
            for kolon in kat.kolonlar:
                # Boyuna donatılar
                for donati in kolon.boyuna_donatilar:
                    self.table_detayli.insertRow(row)

                    birim_agirlik = self.engine.DEMIR_ORANLAR.get(donati.cap, 0)
                    agirlik = donati.hesapla_agirlik_kg(birim_agirlik)

                    self.table_detayli.setItem(row, 0, QTableWidgetItem(kat.kat_adi))
                    self.table_detayli.setItem(row, 1, QTableWidgetItem(kolon.kolon_adi))
                    self.table_detayli.setItem(row, 2, QTableWidgetItem("Boyuna"))
                    self.table_detayli.setItem(row, 3, QTableWidgetItem(str(donati.adet)))
                    self.table_detayli.setItem(row, 4, QTableWidgetItem(f"ƒ{donati.cap}"))
                    self.table_detayli.setItem(row, 5, QTableWidgetItem(str(donati.uzunluk)))
                    self.table_detayli.setItem(row, 6, QTableWidgetItem(f"{agirlik:.2f}"))

                    # Boyuna satırlarını mavi yap
                    for col in range(7):
                        self.table_detayli.item(row, col).setBackground(QColor("#e3f2fd"))

                    row += 1

                # Çiroz donatılar
                for donati in kolon.ciroz_donatilar:
                    self.table_detayli.insertRow(row)

                    birim_agirlik = self.engine.DEMIR_ORANLAR.get(donati.cap, 0)
                    agirlik = donati.hesapla_agirlik_kg(birim_agirlik)

                    self.table_detayli.setItem(row, 0, QTableWidgetItem(kat.kat_adi))
                    self.table_detayli.setItem(row, 1, QTableWidgetItem(kolon.kolon_adi))
                    self.table_detayli.setItem(row, 2, QTableWidgetItem("Çiroz"))
                    self.table_detayli.setItem(row, 3, QTableWidgetItem(str(donati.adet)))
                    self.table_detayli.setItem(row, 4, QTableWidgetItem(f"ƒ{donati.cap}"))
                    self.table_detayli.setItem(row, 5, QTableWidgetItem(str(donati.uzunluk)))
                    self.table_detayli.setItem(row, 6, QTableWidgetItem(f"{agirlik:.2f}"))

                    # Çiroz satırlarını yeşil yap
                    for col in range(7):
                        self.table_detayli.item(row, col).setBackground(QColor("#e8f5e9"))

                    row += 1

            # Etriyeler (toplu)
            for etriye in kat.etriyeler:
                self.table_detayli.insertRow(row)

                birim_agirlik = self.engine.DEMIR_ORANLAR.get(etriye.cap, 0)
                agirlik = etriye.hesapla_agirlik_kg(birim_agirlik)

                self.table_detayli.setItem(row, 0, QTableWidgetItem(kat.kat_adi))
                self.table_detayli.setItem(row, 1, QTableWidgetItem("(Toplu)"))
                self.table_detayli.setItem(row, 2, QTableWidgetItem("Etriye"))
                self.table_detayli.setItem(row, 3, QTableWidgetItem(str(etriye.adet)))
                self.table_detayli.setItem(row, 4, QTableWidgetItem(f"ƒ{etriye.cap}"))
                self.table_detayli.setItem(row, 5, QTableWidgetItem(str(etriye.uzunluk)))
                self.table_detayli.setItem(row, 6, QTableWidgetItem(f"{agirlik:.2f}"))

                # Etriye satırlarını sarı yap
                for col in range(7):
                    self.table_detayli.item(row, col).setBackground(QColor("#fff9c4"))

                row += 1

        # Sütun genişliklerini ayarla
        header = self.table_detayli.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

    def _fill_cap_ozeti(self, ozet_cap):
        """Çap bazında özet doldur"""
        self.table_cap_ozeti.setRowCount(0)

        row = 0
        for cap_key in sorted(ozet_cap.keys(), key=lambda x: ozet_cap[x]['cap']):
            veri = ozet_cap[cap_key]

            self.table_cap_ozeti.insertRow(row)
            self.table_cap_ozeti.setItem(row, 0, QTableWidgetItem(f"ƒ{veri['cap']}"))
            self.table_cap_ozeti.setItem(row, 1, QTableWidgetItem(str(veri['adet'])))
            self.table_cap_ozeti.setItem(row, 2, QTableWidgetItem(f"{veri['toplam_boy_m']:.2f}"))
            self.table_cap_ozeti.setItem(row, 3, QTableWidgetItem(f"{veri['agirlik_kg']:.2f}"))

            # Ortala
            for col in range(4):
                self.table_cap_ozeti.item(row, col).setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

            row += 1

        # Son satır: Toplam
        if ozet_cap:
            self.table_cap_ozeti.insertRow(row)
            toplam_adet = sum(v['adet'] for v in ozet_cap.values())
            toplam_boy = sum(v['toplam_boy_m'] for v in ozet_cap.values())
            toplam_agirlik = sum(v['agirlik_kg'] for v in ozet_cap.values())

            item_toplam = QTableWidgetItem("TOPLAM")
            item_toplam.setBackground(QColor("#f1c40f"))
            font = QFont()
            font.setWeight(QFont.Weight.Bold)
            item_toplam.setFont(font)

            self.table_cap_ozeti.setItem(row, 0, item_toplam)
            self.table_cap_ozeti.setItem(row, 1, QTableWidgetItem(str(toplam_adet)))
            self.table_cap_ozeti.setItem(row, 2, QTableWidgetItem(f"{toplam_boy:.2f}"))
            self.table_cap_ozeti.setItem(row, 3, QTableWidgetItem(f"{toplam_agirlik:.2f}"))

            for col in range(1, 4):
                self.table_cap_ozeti.item(row, col).setBackground(QColor("#f1c40f"))
                self.table_cap_ozeti.item(row, col).setFont(font)
                self.table_cap_ozeti.item(row, col).setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

        # Sütun genişliklerini ayarla
        header = self.table_cap_ozeti.horizontalHeader()
        for i in range(4):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

    def _fill_kolon_ozeti(self, ozet_kolon):
        """Kolon bazında özet doldur"""
        self.table_kolon_ozeti.setRowCount(0)

        row = 0
        for kolon_veri in ozet_kolon:
            self.table_kolon_ozeti.insertRow(row)
            self.table_kolon_ozeti.setItem(row, 0, QTableWidgetItem(kolon_veri['kat_adi']))
            self.table_kolon_ozeti.setItem(row, 1, QTableWidgetItem(kolon_veri['kolon_adi']))
            self.table_kolon_ozeti.setItem(row, 2, QTableWidgetItem(kolon_veri['boyuna']))
            self.table_kolon_ozeti.setItem(row, 3, QTableWidgetItem(kolon_veri['ciroz']))
            self.table_kolon_ozeti.setItem(row, 4, QTableWidgetItem(
                f"{kolon_veri['toplam_agirlik_kg']:.2f}"
            ))

            # Ortala
            for col in range(5):
                self.table_kolon_ozeti.item(row, col).setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

            row += 1

        # Sütun genişliklerini ayarla
        header = self.table_kolon_ozeti.horizontalHeader()
        for i in range(5):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

    def excel_aktar(self):
        """Excel'e aktar"""
        if not self.kolon_verileri:
            QMessageBox.warning(self, "Uyarı", "Önce DXF dosyasını okuyun!")
            return

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill

            # Dosya adı sor
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Excel Dosyası Kaydet",
                f"kolon_metraj_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "Excel Dosyaları (*.xlsx)"
            )

            if not file_path:
                return

            self.setCursor(Qt.CursorShape.WaitCursor)

            wb = Workbook()

            # Sheet 1: Detaylı Liste
            ws1 = wb.active
            ws1.title = "Detaylı Liste"

            headers = ["Kat", "Kolon", "Tip", "Adet", "Çap (mm)", "Uzunluk (cm)", "Ağırlık (kg)"]
            ws1.append(headers)

            # Başlık formatı
            for cell in ws1[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="2c3e50", end_color="2c3e50", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")

            # Verileri ekle
            for kat in self.kolon_verileri['katlar']:
                for kolon in kat.kolonlar:
                    for donati in kolon.boyuna_donatilar:
                        birim_agirlik = self.engine.DEMIR_ORANLAR.get(donati.cap, 0)
                        agirlik = donati.hesapla_agirlik_kg(birim_agirlik)
                        ws1.append([
                            kat.kat_adi, kolon.kolon_adi, "Boyuna",
                            donati.adet, donati.cap, donati.uzunluk, round(agirlik, 2)
                        ])

                    for donati in kolon.ciroz_donatilar:
                        birim_agirlik = self.engine.DEMIR_ORANLAR.get(donati.cap, 0)
                        agirlik = donati.hesapla_agirlik_kg(birim_agirlik)
                        ws1.append([
                            kat.kat_adi, kolon.kolon_adi, "Çiroz",
                            donati.adet, donati.cap, donati.uzunluk, round(agirlik, 2)
                        ])

                for etriye in kat.etriyeler:
                    birim_agirlik = self.engine.DEMIR_ORANLAR.get(etriye.cap, 0)
                    agirlik = etriye.hesapla_agirlik_kg(birim_agirlik)
                    ws1.append([
                        kat.kat_adi, "(Toplu)", "Etriye",
                        etriye.adet, etriye.cap, etriye.uzunluk, round(agirlik, 2)
                    ])

            # Sheet 2: Çap Özeti
            ws2 = wb.create_sheet("Çap Bazında Özet")
            ws2.append(["Çap (mm)", "Toplam Adet", "Toplam Boy (m)", "Ağırlık (kg)"])

            for cell in ws2[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="2c3e50", end_color="2c3e50", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")

            for cap_key in sorted(self.kolon_verileri['ozet_cap_bazinda'].keys(),
                                key=lambda x: self.kolon_verileri['ozet_cap_bazinda'][x]['cap']):
                veri = self.kolon_verileri['ozet_cap_bazinda'][cap_key]
                ws2.append([
                    f"ƒ{veri['cap']}", veri['adet'],
                    round(veri['toplam_boy_m'], 2), round(veri['agirlik_kg'], 2)
                ])

            # Sheet 3: Kolon Özeti
            ws3 = wb.create_sheet("Kolon Bazında Özet")
            ws3.append(["Kat", "Kolon", "Boyuna", "Çiroz", "Ağırlık (kg)"])

            for cell in ws3[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="2c3e50", end_color="2c3e50", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")

            for kolon_veri in self.kolon_verileri['ozet_kolon_bazinda']:
                ws3.append([
                    kolon_veri['kat_adi'], kolon_veri['kolon_adi'],
                    kolon_veri['boyuna'], kolon_veri['ciroz'],
                    round(kolon_veri['toplam_agirlik_kg'], 2)
                ])

            # Kaydet
            wb.save(file_path)

            QMessageBox.information(self, "Başarılı", f"Excel dosyası oluşturuldu:\n{file_path}")
            logger.info(f"Excel dosyası oluşturuldu: {file_path}")

        except ImportError:
            QMessageBox.critical(
                self, "Hata",
                "openpyxl kütüphanesi bulunamadı.\n\n"
                "Lütfen 'pip install openpyxl' komutunu çalıştırın."
            )

        except Exception as e:
            logger.exception("Excel export hatası")
            QMessageBox.critical(self, "Hata", f"Excel oluşturulurken hata:\n{str(e)}")

        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def pdf_olustur(self):
        """PDF rapor oluştur"""
        QMessageBox.information(
            self,
            "Bilgi",
            "PDF rapor özelliği henüz geliştirilmemiştir."
        )

    def veritabanina_kaydet(self):
        """Veritabanına kaydet"""
        if not self.kolon_verileri:
            QMessageBox.warning(self, "Uyarı", "Önce DXF dosyasını okuyun!")
            return

        try:
            self.setCursor(Qt.CursorShape.WaitCursor)

            kayit_sayisi = 0

            for kat in self.kolon_verileri['katlar']:
                for kolon in kat.kolonlar:
                    # Boyuna donatılar
                    for donati in kolon.boyuna_donatilar:
                        birim_agirlik = self.engine.DEMIR_ORANLAR.get(donati.cap, 0)
                        agirlik = donati.hesapla_agirlik_kg(birim_agirlik)

                        aciklama = (
                            f"{kat.kat_adi} - {kolon.kolon_adi} - Boyuna - "
                            f"{donati.adet}ƒ{donati.cap} l={donati.uzunluk}cm"
                        )

                        self.db.execute_query("""
                            INSERT INTO metraj_kalemleri
                            (poz_no, tanim, birim, miktar, birim_fiyat, tutar, aciklama)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            f"KOLON-{kolon.kolon_adi}",
                            f"Kolon Boyuna Donatı ƒ{donati.cap}",
                            "kg",
                            round(agirlik, 2),
                            0,
                            0,
                            aciklama
                        ))
                        kayit_sayisi += 1

                    # Çiroz donatılar
                    for donati in kolon.ciroz_donatilar:
                        birim_agirlik = self.engine.DEMIR_ORANLAR.get(donati.cap, 0)
                        agirlik = donati.hesapla_agirlik_kg(birim_agirlik)

                        aciklama = (
                            f"{kat.kat_adi} - {kolon.kolon_adi} - Çiroz - "
                            f"{donati.adet}ƒ{donati.cap} l={donati.uzunluk}cm"
                        )

                        self.db.execute_query("""
                            INSERT INTO metraj_kalemleri
                            (poz_no, tanim, birim, miktar, birim_fiyat, tutar, aciklama)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            f"KOLON-{kolon.kolon_adi}",
                            f"Kolon Çiroz ƒ{donati.cap}",
                            "kg",
                            round(agirlik, 2),
                            0,
                            0,
                            aciklama
                        ))
                        kayit_sayisi += 1

                # Etriyeler
                for etriye in kat.etriyeler:
                    birim_agirlik = self.engine.DEMIR_ORANLAR.get(etriye.cap, 0)
                    agirlik = etriye.hesapla_agirlik_kg(birim_agirlik)

                    aciklama = (
                        f"{kat.kat_adi} - Etriye (Toplu) - "
                        f"{etriye.adet}ƒ{etriye.cap} l={etriye.uzunluk}cm"
                    )

                    self.db.execute_query("""
                        INSERT INTO metraj_kalemleri
                        (poz_no, tanim, birim, miktar, birim_fiyat, tutar, aciklama)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        f"KOLON-ETRIYE",
                        f"Kolon Etriye ƒ{etriye.cap}",
                        "kg",
                        round(agirlik, 2),
                        0,
                        0,
                        aciklama
                    ))
                    kayit_sayisi += 1

            QMessageBox.information(
                self,
                "Başarılı",
                f"{kayit_sayisi} adet kayıt veritabanına eklendi."
            )
            logger.info(f"{kayit_sayisi} adet kolon donatı kaydı eklendi")

        except Exception as e:
            logger.exception("Veritabanı kayıt hatası")
            QMessageBox.critical(self, "Hata", f"Veritabanına kaydedilemedi:\n{str(e)}")

        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)
