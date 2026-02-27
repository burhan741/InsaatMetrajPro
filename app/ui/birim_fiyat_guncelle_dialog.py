"""
Birim Fiyat Excel Toplu Güncelleme Dialog
Excel dosyasından birim_fiyatlar tablosunu toplu olarak günceller.

Excel Formatı:
 A: Poz No | B: Yeni Fiyat (TL) | C: Tarih (YYYY-MM-DD, opsiyonel)
"""

from PyQt6.QtWidgets import (
 QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
 QLabel, QTableWidget, QTableWidgetItem, QFileDialog,
 QMessageBox, QHeaderView, QGroupBox, QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BirimFiyatGuncelleDialog(QDialog):
 """Excel'den birim fiyat toplu güncelleme dialogu"""

 def __init__(self, parent=None, db=None):
 super().__init__(parent)
 self.db = db
 self._veri = [] # Parse edilmiş Excel satırları
 self._basari = 0
 self._hata = 0
 self.setWindowTitle(" Birim Fiyat Excel Toplu Güncelleme")
 self.setMinimumSize(750, 550)
 self._init_ui()

 # ------------------------------------------------------------------
 def _init_ui(self):
 layout = QVBoxLayout(self)

 # Başlık
 baslik = QLabel(" BİRİM FİYAT EXCEL TOPLU GÜNCELLEME")
 baslik.setFont(QFont("Arial", 13, QFont.Weight.Bold))
 baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
 baslik.setStyleSheet("color: #2196F3; padding: 8px;")
 layout.addWidget(baslik)

 # Excel format açıklaması
 format_group = QGroupBox("Excel Dosyası Formatı")
 format_layout = QVBoxLayout(format_group)
 format_label = QLabel(
 "• Sütun A: Poz No (örn: 23.001)\n"
 "• Sütun B: Yeni Fiyat TL (örn: 1250.50)\n"
 "• Sütun C: Tarih (YYYY-MM-DD, opsiyonel — boş bırakılırsa bugün kullanılır)\n"
 "• Birinci satır başlık satırı olabilir (otomatik algılanır)"
 )
 format_label.setStyleSheet("color: #555; font-size: 11px;")
 format_layout.addWidget(format_label)
 layout.addWidget(format_group)

 # Dosya seçme butonu
 dosya_layout = QHBoxLayout()
 self.lbl_dosya = QLabel("Henüz dosya seçilmedi")
 self.lbl_dosya.setStyleSheet("color: #888; font-style: italic;")
 btn_sec = QPushButton(" Excel Dosyası Seç")
 btn_sec.setStyleSheet(
 "background-color: #2196F3; color: white; font-weight: bold; padding: 8px 16px;"
 )
 btn_sec.clicked.connect(self._dosya_sec)
 dosya_layout.addWidget(self.lbl_dosya, 1)
 dosya_layout.addWidget(btn_sec)
 layout.addLayout(dosya_layout)

 # Önizleme tablosu
 onizleme_group = QGroupBox("Önizleme (İlk 100 Satır)")
 onizleme_layout = QVBoxLayout(onizleme_group)
 self.table = QTableWidget()
 self.table.setColumnCount(3)
 self.table.setHorizontalHeaderLabels(["Poz No", "Yeni Fiyat (TL)", "Tarih"])
 self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
 self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
 self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
 self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
 self.table.setAlternatingRowColors(True)
 onizleme_layout.addWidget(self.table)
 layout.addWidget(onizleme_group, 1)

 # İlerleme çubuğu
 self.progress = QProgressBar()
 self.progress.setVisible(False)
 layout.addWidget(self.progress)

 # Durum etiketi
 self.lbl_durum = QLabel("")
 self.lbl_durum.setAlignment(Qt.AlignmentFlag.AlignCenter)
 layout.addWidget(self.lbl_durum)

 # Butonlar
 btn_layout = QHBoxLayout()
 self.btn_guncelle = QPushButton(" Fiyatları Güncelle")
 self.btn_guncelle.setEnabled(False)
 self.btn_guncelle.setStyleSheet(
 "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px 20px;"
 )
 self.btn_guncelle.clicked.connect(self._guncelle)
 btn_kapat = QPushButton("Kapat")
 btn_kapat.setStyleSheet("padding: 10px 20px;")
 btn_kapat.clicked.connect(self.close)
 btn_layout.addStretch()
 btn_layout.addWidget(self.btn_guncelle)
 btn_layout.addWidget(btn_kapat)
 layout.addLayout(btn_layout)

 # ------------------------------------------------------------------
 def _dosya_sec(self):
 """Excel dosyası seç ve parse et"""
 dosya, _ = QFileDialog.getOpenFileName(
 self, "Excel Dosyası Seç", "",
 "Excel Dosyaları (*.xlsx *.xls);;Tüm Dosyalar (*)"
 )
 if not dosya:
 return

 try:
 import pandas as pd
 except ImportError:
 QMessageBox.critical(
 self, "Hata",
 "pandas kütüphanesi yüklü değil!\n"
 "Kurulum: pip install pandas openpyxl"
 )
 return

 try:
 df = pd.read_excel(dosya, header=None, dtype=str)
 self.lbl_dosya.setText(dosya)
 self._veri = []
 self.table.setRowCount(0)

 bugun = datetime.now().strftime("%Y-%m-%d")
 satirlar_eklendi = 0

 for idx, row in df.iterrows():
 # İlk sütun poz_no, ikinci fiyat olmalı
 poz_no = str(row.iloc[0]).strip() if len(row) > 0 else ""
 fiyat_str = str(row.iloc[1]).strip() if len(row) > 1 else ""
 tarih_str = str(row.iloc[2]).strip() if len(row) > 2 else ""

 # Başlık satırını atla (sayısal olmayan fiyat)
 if not poz_no or poz_no.lower() in ("poz no", "poz_no", "nan", "none"):
 continue
 try:
 fiyat = float(fiyat_str.replace(",", "."))
 except (ValueError, AttributeError):
 continue

 # Tarih kontrolü
 if not tarih_str or tarih_str.lower() in ("nan", "none", "tarih"):
 tarih = bugun
 else:
 tarih = tarih_str[:10] # İlk 10 karakter al (YYYY-MM-DD)

 self._veri.append({"poz_no": poz_no, "fiyat": fiyat, "tarih": tarih})

 # Tabloya ekle (max 100 satır göster)
 if satirlar_eklendi < 100:
 row_idx = self.table.rowCount()
 self.table.insertRow(row_idx)
 self.table.setItem(row_idx, 0, QTableWidgetItem(poz_no))
 fiyat_item = QTableWidgetItem(f"{fiyat:,.2f}")
 fiyat_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
 self.table.setItem(row_idx, 1, fiyat_item)
 self.table.setItem(row_idx, 2, QTableWidgetItem(tarih))
 satirlar_eklendi += 1

 toplam = len(self._veri)
 if toplam == 0:
 QMessageBox.warning(
 self, "Uyarı",
 "Excel dosyasında geçerli veri bulunamadı.\n"
 "Lütfen dosya formatını kontrol edin."
 )
 self.btn_guncelle.setEnabled(False)
 else:
 self.lbl_durum.setText(f"{toplam} satır okundu — Güncellemeye hazır")
 self.lbl_durum.setStyleSheet("color: #4CAF50; font-weight: bold;")
 self.btn_guncelle.setEnabled(True)

 except Exception as e:
 logger.error(f"Excel okuma hatası: {e}")
 QMessageBox.critical(self, "Hata", f"Excel dosyası okunamadı:\n{str(e)}")

 # ------------------------------------------------------------------
 def _guncelle(self):
 """DB'ye toplu güncelleme yap"""
 if not self._veri:
 return

 if not self.db:
 QMessageBox.critical(self, "Hata", "Veritabanı bağlantısı yok!")
 return

 toplam = len(self._veri)
 self._basari = 0
 self._hata = 0

 self.progress.setMaximum(toplam)
 self.progress.setValue(0)
 self.progress.setVisible(True)
 self.btn_guncelle.setEnabled(False)

 for i, kayit in enumerate(self._veri):
 try:
 self.db.add_birim_fiyat(
 poz_no=kayit["poz_no"],
 birim_fiyat=kayit["fiyat"],
 tarih=kayit["tarih"],
 kaynak="excel",
 aktif=True
 )
 self._basari += 1
 # Tablodaki satırı yeşile boyar
 if i < self.table.rowCount():
 for col in range(3):
 item = self.table.item(i, col)
 if item:
 item.setBackground(QColor("#c8e6c9"))
 except Exception as e:
 logger.error(f"Fiyat güncellenemedi ({kayit['poz_no']}): {e}")
 self._hata += 1
 if i < self.table.rowCount():
 for col in range(3):
 item = self.table.item(i, col)
 if item:
 item.setBackground(QColor("#ffcdd2"))

 self.progress.setValue(i + 1)

 self.progress.setVisible(False)
 self.btn_guncelle.setEnabled(True)

 # Özet mesaj
 ozet = (
 f"Güncelleme Tamamlandı\n\n"
 f" Başarılı: {self._basari} kayıt\n"
 f" Hatalı: {self._hata} kayıt\n"
 f" Toplam: {toplam} kayıt"
 )
 self.lbl_durum.setText(f"Tamamlandı — {self._basari} başarılı / {self._hata} hatalı")
 if self._hata == 0:
 self.lbl_durum.setStyleSheet("color: #4CAF50; font-weight: bold;")
 QMessageBox.information(self, "Başarılı", ozet)
 else:
 self.lbl_durum.setStyleSheet("color: #FF6600; font-weight: bold;")
 QMessageBox.warning(self, "Kısmen Başarılı", ozet)
