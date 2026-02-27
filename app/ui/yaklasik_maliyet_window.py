"""
Yaklaşık Maliyet ve Keşif Özeti Penceresi
4734 Sayılı Kamu İhale Kanunu kapsamında keşif cetveli hazırlama arayüzü.

Sekmeler:
 1. Keşif Cetveli — Kalem ekleme, düzenleme, poz arama
 2. Özet & KDV — Toplam, KDV, aşırı düşük sınır
 3. Kategori Dağılımı — Pasta grafik benzeri özet
 4. Aşırı Düşük Analizi — Rakip tekliflerle karşılaştırma
"""

from PyQt6.QtWidgets import (
 QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
 QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
 QLineEdit, QComboBox, QMessageBox, QHeaderView, QDoubleSpinBox,
 QTabWidget, QSplitter, QFrame, QDialog, QDialogButtonBox,
 QFileDialog, QCompleter, QAbstractItemView, QSpinBox,
 QStatusBar, QGridLayout, QTextEdit
)
from PyQt6.QtCore import Qt, QStringListModel, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush
from decimal import Decimal
from typing import Optional, List
import logging
import os

from app.core.yaklasik_maliyet_engine import (
 YaklasikMaliyetEngine, KURUM_LISTESI, KDV_ORANLARI,
 CSB_BIRIM_FIYATLARI_2025
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# KALEM EKLEME DİYALOGU
# ──────────────────────────────────────────────

class KalemEkleDialog(QDialog):
 """Keşif cetveline yeni poz kalemi ekleme diyalogu."""

 def __init__(self, parent=None):
 super().__init__(parent)
 self.setWindowTitle("Kalem Ekle")
 self.setMinimumWidth(540)
 self.setModal(True)
 self._setup_ui()

 def _setup_ui(self):
 layout = QVBoxLayout(self)
 layout.setSpacing(10)

 form = QFormLayout()
 form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

 # Poz No + arama butonu
 poz_row = QHBoxLayout()
 self.poz_no_input = QLineEdit()
 self.poz_no_input.setPlaceholderText("Örn: 21.003")
 self.poz_no_input.textChanged.connect(self._poz_degisti)

 self.poz_ara_btn = QPushButton(" Ara")
 self.poz_ara_btn.setMinimumWidth(75)
 self.poz_ara_btn.clicked.connect(self._poz_ara)
 poz_row.addWidget(self.poz_no_input)
 poz_row.addWidget(self.poz_ara_btn)
 form.addRow("Poz No:", poz_row)

 # Tanım
 self.tanim_input = QLineEdit()
 self.tanim_input.setPlaceholderText("Poz seçildiğinde otomatik dolar")
 form.addRow("Tanım:", self.tanim_input)

 # Birim
 self.birim_input = QLineEdit()
 self.birim_input.setPlaceholderText("m², m³, adet, kg ...")
 self.birim_input.setFixedWidth(100)
 form.addRow("Birim:", self.birim_input)

 # Miktar
 self.miktar_spin = QDoubleSpinBox()
 self.miktar_spin.setRange(0.001, 9_999_999)
 self.miktar_spin.setDecimals(3)
 self.miktar_spin.setValue(1.0)
 self.miktar_spin.setSuffix(" ")
 form.addRow("Miktar:", self.miktar_spin)

 # Birim Fiyat
 self.fiyat_spin = QDoubleSpinBox()
 self.fiyat_spin.setRange(0.01, 99_999_999)
 self.fiyat_spin.setDecimals(2)
 self.fiyat_spin.setValue(0.0)
 self.fiyat_spin.setSuffix(" TL")
 self.fiyat_spin.valueChanged.connect(self._tutar_guncelle)
 self.miktar_spin.valueChanged.connect(self._tutar_guncelle)
 form.addRow("Birim Fiyat:", self.fiyat_spin)

 # Tutar (salt okunur)
 self.tutar_label = QLabel("0,00 TL")
 self.tutar_label.setStyleSheet("font-weight: bold; color: #00BFFF; font-size: 13px;")
 form.addRow("Tutar:", self.tutar_label)

 # Açıklama
 self.aciklama_input = QLineEdit()
 self.aciklama_input.setPlaceholderText("Opsiyonel not...")
 form.addRow("Açıklama:", self.aciklama_input)

 layout.addLayout(form)

 # Butonlar
 btn_box = QDialogButtonBox(
 QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
 )
 btn_box.accepted.connect(self._kabul)
 btn_box.rejected.connect(self.reject)
 layout.addWidget(btn_box)

 def _poz_degisti(self, poz_no: str):
 """Poz no yazılınca resmi listeden otomatik doldur."""
 bilgi = CSB_BIRIM_FIYATLARI_2025.get(poz_no.strip(), {})
 if bilgi:
 self.tanim_input.setText(bilgi['tanim'])
 self.birim_input.setText(bilgi['birim'])
 self.fiyat_spin.setValue(float(bilgi['fiyat']))

 def _poz_ara(self):
 """Poz arama diyalogu aç."""
 arama = self.poz_no_input.text().strip()
 engine = YaklasikMaliyetEngine()
 sonuclar = engine.poz_ara(arama)
 if not sonuclar:
 QMessageBox.information(self, "Sonuç Yok", f"'{arama}' için sonuç bulunamadı.")
 return

 dialog = PozAramaDialog(sonuclar, self)
 if dialog.exec() == QDialog.DialogCode.Accepted and dialog.secilen:
 self.poz_no_input.setText(dialog.secilen['poz_no'])

 def _tutar_guncelle(self):
 tutar = self.miktar_spin.value() * self.fiyat_spin.value()
 self.tutar_label.setText(f"{tutar:,.2f} TL")

 def _kabul(self):
 if not self.poz_no_input.text().strip():
 QMessageBox.warning(self, "Eksik Alan", "Poz No boş bırakılamaz.")
 return
 if self.fiyat_spin.value() <= 0:
 QMessageBox.warning(self, "Geçersiz Fiyat", "Birim fiyat sıfırdan büyük olmalı.")
 return
 self.accept()

 def get_degerler(self) -> dict:
 return {
 'poz_no': self.poz_no_input.text().strip(),
 'tanim': self.tanim_input.text().strip(),
 'birim': self.birim_input.text().strip() or 'adet',
 'miktar': self.miktar_spin.value(),
 'birim_fiyat': self.fiyat_spin.value(),
 'aciklama': self.aciklama_input.text().strip(),
 }


class PozAramaDialog(QDialog):
 """Resmi poz listesinde arama sonuçlarını göster, seçim yap."""

 def __init__(self, sonuclar: list, parent=None):
 super().__init__(parent)
 self.setWindowTitle("Poz Seç")
 self.setMinimumSize(600, 350)
 self.secilen = None
 self._setup_ui(sonuclar)

 def _setup_ui(self, sonuclar):
 layout = QVBoxLayout(self)

 self.tablo = QTableWidget(len(sonuclar), 4)
 self.tablo.setHorizontalHeaderLabels(["Poz No", "Tanım", "Birim", "Fiyat (TL)"])
 self.tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
 self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
 self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
 self.tablo.doubleClicked.connect(self._sec)

 for row, s in enumerate(sonuclar):
 self.tablo.setItem(row, 0, QTableWidgetItem(s['poz_no']))
 self.tablo.setItem(row, 1, QTableWidgetItem(s['tanim']))
 self.tablo.setItem(row, 2, QTableWidgetItem(s['birim']))
 fiyat_item = QTableWidgetItem(f"{s['fiyat']:,.2f}")
 fiyat_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
 self.tablo.setItem(row, 3, fiyat_item)

 layout.addWidget(self.tablo)

 btn_box = QDialogButtonBox(
 QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
 )
 btn_box.accepted.connect(self._sec)
 btn_box.rejected.connect(self.reject)
 layout.addWidget(btn_box)

 self._sonuclar = sonuclar

 def _sec(self):
 row = self.tablo.currentRow()
 if row >= 0:
 self.secilen = self._sonuclar[row]
 self.accept()


# ──────────────────────────────────────────────
# ANA PENCERE
# ──────────────────────────────────────────────

class YaklasikMaliyetWindow(QWidget):
 """
 Yaklaşık Maliyet ve Keşif Özeti penceresi.

 Devlet İhalesi → Araç 1
 """

 def __init__(self, db_manager=None, parent=None):
 super().__init__(parent)
 self.db = db_manager
 self.engine = YaklasikMaliyetEngine()
 self._setup_ui()
 self._apply_style()

 # ── KURULUM ────────────────────────────────

 def _setup_ui(self):
 main_layout = QVBoxLayout(self)
 main_layout.setContentsMargins(12, 12, 12, 8)
 main_layout.setSpacing(8)

 # ---- Başlık & Proje Bilgileri ----
 main_layout.addWidget(self._build_proje_bilgi_grubu())

 # ---- Araç Çubuğu ----
 main_layout.addWidget(self._build_toolbar())

 # ---- Sekmeler ----
 self.tabs = QTabWidget()
 self.tabs.addTab(self._build_kesif_tab(), "Keşif Cetveli")
 self.tabs.addTab(self._build_ozet_tab(), "Özet & KDV")
 self.tabs.addTab(self._build_kategori_tab(), "Kategori Dağılımı")
 self.tabs.addTab(self._build_asiri_dusuk_tab(), "Aşırı Düşük Analizi")
 main_layout.addWidget(self.tabs)

 # ---- Durum Çubuğu ----
 self.durum_label = QLabel("Hazır")
 self.durum_label.setStyleSheet("color: #aaa; font-size: 11px; padding: 2px 4px;")
 main_layout.addWidget(self.durum_label)

 def _build_proje_bilgi_grubu(self) -> QGroupBox:
 grp = QGroupBox("Proje / İhale Bilgileri")
 layout = QGridLayout(grp)
 layout.setSpacing(6)

 self.idare_input = QLineEdit()
 self.idare_input.setPlaceholderText("Örn: Ankara Büyükşehir Belediyesi")
 self.idare_input.textChanged.connect(
 lambda t: setattr(self.engine, 'idare', t)
 )

 self.proje_adi_input = QLineEdit()
 self.proje_adi_input.setPlaceholderText("Örn: Kapalı Spor Salonu Yapımı")
 self.proje_adi_input.textChanged.connect(
 lambda t: setattr(self.engine, 'proje_adi', t)
 )

 self.ihale_no_input = QLineEdit()
 self.ihale_no_input.setPlaceholderText("Örn: 2025/123456")
 self.ihale_no_input.textChanged.connect(
 lambda t: setattr(self.engine, 'ihale_no', t)
 )

 self.kurum_combo = QComboBox()
 for key, ad in KURUM_LISTESI.items():
 self.kurum_combo.addItem(ad, key)
 self.kurum_combo.currentIndexChanged.connect(self._kurum_degisti)

 self.kdv_combo = QComboBox()
 self.kdv_combo.addItem("%20 — Standart KDV", '20')
 self.kdv_combo.addItem("%0 — KDV Muaf", '0')
 self.kdv_combo.currentIndexChanged.connect(self._kdv_degisti)

 layout.addWidget(QLabel("İdare:"), 0, 0)
 layout.addWidget(self.idare_input, 0, 1)
 layout.addWidget(QLabel("Proje Adı:"), 0, 2)
 layout.addWidget(self.proje_adi_input, 0, 3)
 layout.addWidget(QLabel("İhale No:"), 1, 0)
 layout.addWidget(self.ihale_no_input, 1, 1)
 layout.addWidget(QLabel("Fiyat Listesi:"), 1, 2)
 layout.addWidget(self.kurum_combo, 1, 3)
 layout.addWidget(QLabel("KDV Oranı:"), 2, 0)
 layout.addWidget(self.kdv_combo, 2, 1)

 return grp

 def _build_toolbar(self) -> QWidget:
 frame = QFrame()
 layout = QHBoxLayout(frame)
 layout.setContentsMargins(0, 0, 0, 0)
 layout.setSpacing(8)

 btn_ekle = QPushButton(" Kalem Ekle")
 btn_ekle.clicked.connect(self._kalem_ekle)

 btn_sil = QPushButton(" Sil")
 btn_sil.clicked.connect(self._kalem_sil)

 btn_hesapla = QPushButton(" Hesapla")
 btn_hesapla.setStyleSheet(
 "background-color: #0078d4; color: white; font-weight: bold;"
 "padding: 6px 16px; font-size: 12px;"
 )
 btn_hesapla.clicked.connect(self._hesapla)

 btn_excel = QPushButton(" Excel")
 btn_excel.clicked.connect(self._export_excel)

 btn_pdf = QPushButton(" PDF")
 btn_pdf.clicked.connect(self._export_pdf)

 btn_temizle = QPushButton(" Temizle")
 btn_temizle.clicked.connect(self._temizle)

 for btn in [btn_ekle, btn_sil, btn_hesapla, btn_excel, btn_pdf, btn_temizle]:
 layout.addWidget(btn)

 layout.addStretch()
 return frame

 def _build_kesif_tab(self) -> QWidget:
 widget = QWidget()
 layout = QVBoxLayout(widget)

 self.kesif_tablo = QTableWidget(0, 7)
 self.kesif_tablo.setHorizontalHeaderLabels([
 "Sıra", "Poz No", "Tanım", "Birim", "Miktar", "Birim Fiyat (TL)", "Tutar (TL)"
 ])
 hdr = self.kesif_tablo.horizontalHeader()
 hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
 hdr.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
 self.kesif_tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
 self.kesif_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
 self.kesif_tablo.verticalHeader().setVisible(False)
 layout.addWidget(self.kesif_tablo)

 return widget

 def _build_ozet_tab(self) -> QWidget:
 widget = QWidget()
 layout = QVBoxLayout(widget)
 layout.setAlignment(Qt.AlignmentFlag.AlignTop)

 grp = QGroupBox("Hesap Özeti")
 grp_layout = QFormLayout(grp)
 grp_layout.setSpacing(12)

 def ozet_label(stil='normal'):
 lbl = QLabel("---")
 if stil == 'buyuk':
 lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #00BFFF;")
 elif stil == 'uyari':
 lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #f39c12;")
 else:
 lbl.setStyleSheet("font-size: 13px; color: #ccc;")
 return lbl

 self.lbl_kalem_sayisi = ozet_label()
 self.lbl_toplam_yapim = ozet_label('buyuk')
 self.lbl_kdv_orani = ozet_label()
 self.lbl_kdv_tutari = ozet_label()
 self.lbl_genel_toplam = ozet_label('buyuk')
 self.lbl_asiri_dusuk = ozet_label('uyari')

 grp_layout.addRow("Kalem Sayısı:", self.lbl_kalem_sayisi)
 grp_layout.addRow("Toplam Yapım Bedeli (KDV Hariç):", self.lbl_toplam_yapim)
 grp_layout.addRow("KDV Oranı:", self.lbl_kdv_orani)
 grp_layout.addRow("KDV Tutarı:", self.lbl_kdv_tutari)
 grp_layout.addRow("Genel Toplam (KDV Dahil):", self.lbl_genel_toplam)

 ayrac = QFrame()
 ayrac.setFrameShape(QFrame.Shape.HLine)
 ayrac.setStyleSheet("color: #444;")
 grp_layout.addRow(ayrac)

 grp_layout.addRow("Aşırı Düşük Teklif Sınırı (%80):", self.lbl_asiri_dusuk)

 bilgi = QLabel(
 " Teklifiniz bu değerin altındaysa KİK md.38 kapsamında\n"
 " aşırı düşük sorgusu açılabilir. Açıklamanızı hazır bulundurun."
 )
 bilgi.setStyleSheet("color: #f39c12; font-size: 11px; padding: 8px;")
 bilgi.setWordWrap(True)

 layout.addWidget(grp)
 layout.addWidget(bilgi)
 layout.addStretch()
 return widget

 def _build_kategori_tab(self) -> QWidget:
 widget = QWidget()
 layout = QVBoxLayout(widget)

 self.kategori_tablo = QTableWidget(0, 3)
 self.kategori_tablo.setHorizontalHeaderLabels(["Kategori", "Tutar (TL)", "Oran (%)"])
 self.kategori_tablo.horizontalHeader().setSectionResizeMode(
 0, QHeaderView.ResizeMode.Stretch
 )
 self.kategori_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
 self.kategori_tablo.verticalHeader().setVisible(False)
 layout.addWidget(self.kategori_tablo)

 return widget

 def _build_asiri_dusuk_tab(self) -> QWidget:
 widget = QWidget()
 layout = QVBoxLayout(widget)

 bilgi = QLabel(
 "Rakip teklifleri girerek aşırı düşük sınır değerini hesaplayın.\n"
 "5+ teklif varsa en yüksek ve en düşük çıkarılarak hesaplanır (KİK md.38)."
 )
 bilgi.setWordWrap(True)
 bilgi.setStyleSheet("color: #aaa; font-size: 11px; padding: 4px;")
 layout.addWidget(bilgi)

 teklif_grp = QGroupBox("Teklif Girişi (KDV Hariç, TL)")
 teklif_layout = QVBoxLayout(teklif_grp)

 self.teklif_text = QTextEdit()
 self.teklif_text.setPlaceholderText(
 "Her satıra bir teklif tutarı girin:\n"
 "1250000\n"
 "980000\n"
 "1100000\n"
 "..."
 )
 self.teklif_text.setMaximumHeight(150)
 teklif_layout.addWidget(self.teklif_text)

 btn_hesapla_ad = QPushButton(" Aşırı Düşük Teklif Analizi")
 btn_hesapla_ad.setStyleSheet(
 "background-color: #0078d4; color: white; font-weight: bold;"
 "padding: 8px 20px; font-size: 12px;"
 )
 btn_hesapla_ad.clicked.connect(self._asiri_dusuk_hesapla)
 teklif_layout.addWidget(btn_hesapla_ad)

 layout.addWidget(teklif_grp)

 self.ad_sonuc_tablo = QTableWidget(0, 4)
 self.ad_sonuc_tablo.setHorizontalHeaderLabels([
 "Sıra", "Teklif (TL)", "Sınırın %'si", "Durum"
 ])
 self.ad_sonuc_tablo.horizontalHeader().setSectionResizeMode(
 1, QHeaderView.ResizeMode.Stretch
 )
 self.ad_sonuc_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
 self.ad_sonuc_tablo.verticalHeader().setVisible(False)
 layout.addWidget(self.ad_sonuc_tablo)

 self.ad_sinir_label = QLabel("")
 self.ad_sinir_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #f39c12; padding: 6px;")
 layout.addWidget(self.ad_sinir_label)

 return widget

 # ── OLAYLAR ────────────────────────────────

 def _kurum_degisti(self, idx: int):
 self.engine.kurum = self.kurum_combo.currentData()

 def _kdv_degisti(self, idx: int):
 oran_str = self.kdv_combo.currentData()
 self.engine.kdv_orani = Decimal(oran_str)

 def _kalem_ekle(self):
 dialog = KalemEkleDialog(self)
 if dialog.exec() == QDialog.DialogCode.Accepted:
 degerler = dialog.get_degerler()
 self.engine.kalem_ekle(**degerler)
 self._tablo_yenile()
 self._durum_guncelle(f"Kalem eklendi: {degerler['poz_no']} — {degerler['tanim'][:40]}")

 def _kalem_sil(self):
 row = self.kesif_tablo.currentRow()
 if row < 0:
 QMessageBox.warning(self, "Seçim Yok", "Lütfen silinecek kalemi seçin.")
 return
 sira_no = int(self.kesif_tablo.item(row, 0).text())
 self.engine.kalem_sil(sira_no)
 self._tablo_yenile()
 self._durum_guncelle("Kalem silindi.")

 def _hesapla(self):
 sonuc = self.engine.hesapla()
 if 'hata' in sonuc:
 QMessageBox.warning(self, "Hata", sonuc['hata'])
 return

 # Özet sekmesini güncelle
 self.lbl_kalem_sayisi.setText(str(sonuc['kalem_sayisi']))
 self.lbl_toplam_yapim.setText(f"{sonuc['toplam_yapim']:,.2f} TL")
 self.lbl_kdv_orani.setText(f"%{sonuc['kdv_orani']:.0f}")
 self.lbl_kdv_tutari.setText(f"{sonuc['kdv_tutari']:,.2f} TL")
 self.lbl_genel_toplam.setText(f"{sonuc['genel_toplam']:,.2f} TL")
 self.lbl_asiri_dusuk.setText(f"{sonuc['asiri_dusuk_sinir']:,.2f} TL")

 # Kategori sekmesini güncelle
 self._kategori_guncelle()

 self.tabs.setCurrentIndex(1) # Özet sekmesine geç
 self._durum_guncelle(
 f"Hesaplandı — Toplam: {sonuc['genel_toplam']:,.2f} TL | "
 f"Aşırı Düşük Sınırı: {sonuc['asiri_dusuk_sinir']:,.2f} TL"
 )

 def _kategori_guncelle(self):
 kategoriler = self.engine.kategori_ozeti()
 self.kategori_tablo.setRowCount(len(kategoriler))
 renkler = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12',
 '#9b59b6', '#1abc9c', '#e67e22', '#95a5a6']
 for row, kat in enumerate(kategoriler):
 self.kategori_tablo.setItem(row, 0, QTableWidgetItem(kat['kategori']))

 tutar_item = QTableWidgetItem(f"{kat['tutar']:,.2f}")
 tutar_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
 self.kategori_tablo.setItem(row, 1, tutar_item)

 yuzde_item = QTableWidgetItem(f"%{kat['yuzde']:.1f}")
 yuzde_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
 renk = QColor(renkler[row % len(renkler)])
 renk.setAlpha(60)
 yuzde_item.setBackground(QBrush(renk))
 self.kategori_tablo.setItem(row, 2, yuzde_item)

 def _asiri_dusuk_hesapla(self):
 metin = self.teklif_text.toPlainText().strip()
 if not metin:
 QMessageBox.warning(self, "Boş", "Lütfen teklif tutarlarını girin.")
 return

 teklifler = []
 for satir in metin.splitlines():
 satir = satir.strip().replace(',', '').replace('.', '', satir.count('.') - 1)
 try:
 teklifler.append(float(satir))
 except ValueError:
 pass

 if not teklifler:
 QMessageBox.warning(self, "Geçersiz Giriş", "Geçerli teklif bulunamadı.")
 return

 sonuc = self.engine.asiri_dusuk_analiz(teklifler)

 if sonuc.get('sinir_deger') is None:
 self.ad_sinir_label.setText(sonuc['durum'])
 return

 self.ad_sonuc_tablo.setRowCount(len(sonuc['teklifler']))
 for row, t in enumerate(sonuc['teklifler']):
 self.ad_sonuc_tablo.setItem(row, 0, QTableWidgetItem(str(t['sira'])))

 tutar_item = QTableWidgetItem(f"{t['teklif']:,.2f}")
 tutar_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
 self.ad_sonuc_tablo.setItem(row, 1, tutar_item)

 yuzde_item = QTableWidgetItem(f"%{t['sinirin_yuzdesi']:.1f}")
 yuzde_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
 self.ad_sonuc_tablo.setItem(row, 2, yuzde_item)

 durum_item = QTableWidgetItem(t['durum'])
 durum_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
 if t['durum'] == 'Aşırı Düşük':
 durum_item.setForeground(QBrush(QColor('#e74c3c')))
 durum_item.setFont(QFont('Arial', 9, QFont.Weight.Bold))
 else:
 durum_item.setForeground(QBrush(QColor('#2ecc71')))
 self.ad_sonuc_tablo.setItem(row, 3, durum_item)

 self.ad_sinir_label.setText(
 f"Sınır Değer: {sonuc['sinir_deger']:,.2f} TL | "
 f"Aşırı Düşük: {sonuc['asiri_dusuk_sayisi']} teklif | "
 f"Ortalama: {sonuc['ortalama_teklif']:,.2f} TL"
 )

 def _tablo_yenile(self):
 self.kesif_tablo.setRowCount(len(self.engine.kalemler))
 for row, kalem in enumerate(self.engine.kalemler):
 def item(text, align=Qt.AlignmentFlag.AlignLeft):
 it = QTableWidgetItem(str(text))
 it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
 return it

 right = Qt.AlignmentFlag.AlignRight
 self.kesif_tablo.setItem(row, 0, item(kalem.sira_no, right))
 self.kesif_tablo.setItem(row, 1, item(kalem.poz_no))
 self.kesif_tablo.setItem(row, 2, item(kalem.tanim))
 self.kesif_tablo.setItem(row, 3, item(kalem.birim, Qt.AlignmentFlag.AlignCenter))
 self.kesif_tablo.setItem(row, 4, item(f"{float(kalem.miktar):,.3f}", right))
 self.kesif_tablo.setItem(row, 5, item(f"{float(kalem.birim_fiyat):,.2f}", right))

 tutar_item = item(f"{float(kalem.tutar):,.2f}", right)
 tutar_item.setForeground(QBrush(QColor('#00BFFF')))
 tutar_item.setFont(QFont('Arial', 9, QFont.Weight.Bold))
 self.kesif_tablo.setItem(row, 6, tutar_item)

 def _export_excel(self):
 try:
 import openpyxl
 from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

 veri = self.engine.export_kesif_ozeti_dict()
 if 'hata' in veri:
 QMessageBox.warning(self, "Hata", veri['hata'])
 return

 yol, _ = QFileDialog.getSaveFileName(
 self, "Excel Kaydet", f"kesif_ozeti_{veri['baslik']['ihale_no'].replace('/', '-')}.xlsx",
 "Excel (*.xlsx)"
 )
 if not yol:
 return

 wb = openpyxl.Workbook()
 ws = wb.active
 ws.title = "Keşif Özeti"

 # Başlık bloğu
 baslik = veri['baslik']
 ws['A1'] = "KEŞİF ÖZETİ / YAKIN MALİYET CETVELİ"
 ws['A1'].font = Font(size=14, bold=True)
 ws.merge_cells('A1:G1')
 ws['A1'].alignment = Alignment(horizontal='center')

 ws['A2'] = f"İdare: {baslik['idare']}"
 ws['A3'] = f"Proje: {baslik['proje_adi']}"
 ws['A4'] = f"İhale No: {baslik['ihale_no']}"
 ws['A5'] = f"Fiyat Listesi: {baslik['fiyat_listesi']} | Tarih: {baslik['tarih']}"
 ws.merge_cells('A2:G2')
 ws.merge_cells('A3:G3')
 ws.merge_cells('A4:G4')
 ws.merge_cells('A5:G5')

 # Tablo başlığı
 basliklar = ["Sıra", "Poz No", "Tanım", "Birim", "Miktar", "Birim Fiyat (TL)", "Tutar (TL)"]
 for col, bas in enumerate(basliklar, 1):
 hucre = ws.cell(row=7, column=col, value=bas)
 hucre.font = Font(bold=True, color='FFFFFF')
 hucre.fill = PatternFill('solid', fgColor='1a1a6e')
 hucre.alignment = Alignment(horizontal='center')

 # Kalemler
 for r_idx, kalem in enumerate(veri['kalemler'], 8):
 ws.cell(r_idx, 1, kalem['sira_no'])
 ws.cell(r_idx, 2, kalem['poz_no'])
 ws.cell(r_idx, 3, kalem['tanim'])
 ws.cell(r_idx, 4, kalem['birim'])
 ws.cell(r_idx, 5, kalem['miktar'])
 ws.cell(r_idx, 6, kalem['birim_fiyat'])
 tutar_h = ws.cell(r_idx, 7, kalem['tutar'])
 tutar_h.font = Font(bold=True)

 # Özet satırları
 ozet_row = 8 + len(veri['kalemler']) + 1
 ozet = veri['ozet']
 ozet_satirlar = [
 ("Toplam Yapım Bedeli (KDV Hariç):", ozet['toplam_yapim_bedeli']),
 (f"KDV (%{ozet['kdv_orani']:.0f}):", ozet['kdv_tutari']),
 ("GENEL TOPLAM (KDV Dahil):", ozet['genel_toplam']),
 ("Aşırı Düşük Teklif Sınırı (%80):", ozet['asiri_dusuk_sinir']),
 ]
 for i, (etiket, deger) in enumerate(ozet_satirlar):
 ws.cell(ozet_row + i, 5, etiket).font = Font(bold=True)
 hucre = ws.cell(ozet_row + i, 7, deger)
 hucre.font = Font(bold=True)
 hucre.number_format = '#,##0.00'

 # Kolon genişlikleri
 ws.column_dimensions['A'].width = 6
 ws.column_dimensions['B'].width = 12
 ws.column_dimensions['C'].width = 50
 ws.column_dimensions['D'].width = 8
 ws.column_dimensions['E'].width = 12
 ws.column_dimensions['F'].width = 18
 ws.column_dimensions['G'].width = 18

 wb.save(yol)
 QMessageBox.information(self, "Başarılı", f"Excel kaydedildi:\n{yol}")
 self._durum_guncelle(f"Excel export: {os.path.basename(yol)}")

 except ImportError:
 QMessageBox.critical(self, "Hata", "openpyxl paketi bulunamadı.")
 except Exception as e:
 QMessageBox.critical(self, "Hata", f"Excel export hatası:\n{e}")
 logger.exception("Excel export hatası")

 def _export_pdf(self):
 try:
 from reportlab.lib.pagesizes import A4
 from reportlab.lib.units import cm
 from reportlab.platypus import (
 SimpleDocTemplate, Table, TableStyle, Paragraph,
 Spacer, HRFlowable
 )
 from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
 from reportlab.lib import colors

 veri = self.engine.export_kesif_ozeti_dict()
 if 'hata' in veri:
 QMessageBox.warning(self, "Hata", veri['hata'])
 return

 yol, _ = QFileDialog.getSaveFileName(
 self, "PDF Kaydet", "kesif_ozeti.pdf", "PDF (*.pdf)"
 )
 if not yol:
 return

 doc = SimpleDocTemplate(yol, pagesize=A4,
 leftMargin=1.5*cm, rightMargin=1.5*cm,
 topMargin=2*cm, bottomMargin=2*cm)
 styles = getSampleStyleSheet()
 baslik_stil = ParagraphStyle('Baslik', parent=styles['Title'], fontSize=14, spaceAfter=6)
 kucuk_stil = ParagraphStyle('Kucuk', parent=styles['Normal'], fontSize=9)

 hikaye = []
 baslik = veri['baslik']

 hikaye.append(Paragraph("KEŞİF ÖZETİ — YAKIN MALİYET CETVELİ", baslik_stil))
 hikaye.append(Paragraph(f"<b>İdare:</b> {baslik['idare']}", kucuk_stil))
 hikaye.append(Paragraph(f"<b>Proje:</b> {baslik['proje_adi']}", kucuk_stil))
 hikaye.append(Paragraph(
 f"<b>İhale No:</b> {baslik['ihale_no']} | "
 f"<b>Fiyat Listesi:</b> {baslik['fiyat_listesi']} | "
 f"<b>Tarih:</b> {baslik['tarih']}", kucuk_stil
 ))
 hikaye.append(Spacer(1, 0.4*cm))

 # Kalemler tablosu
 tablo_verisi = [["Sıra", "Poz No", "Tanım", "Birim", "Miktar", "Birim Fiyat", "Tutar (TL)"]]
 for k in veri['kalemler']:
 tablo_verisi.append([
 str(k['sira_no']), k['poz_no'], k['tanim'][:45], k['birim'],
 f"{k['miktar']:,.3f}", f"{k['birim_fiyat']:,.2f}", f"{k['tutar']:,.2f}"
 ])

 # Özet satırları
 ozet = veri['ozet']
 tablo_verisi += [
 ["", "", "", "", "", "Toplam (KDV Hariç):", f"{ozet['toplam_yapim_bedeli']:,.2f}"],
 ["", "", "", "", "", f"KDV (%{ozet['kdv_orani']:.0f}):", f"{ozet['kdv_tutari']:,.2f}"],
 ["", "", "", "", "", "GENEL TOPLAM:", f"{ozet['genel_toplam']:,.2f}"],
 ["", "", "", "", "", "Aşırı Düşük Sınırı:", f"{ozet['asiri_dusuk_sinir']:,.2f}"],
 ]

 t = Table(tablo_verisi, colWidths=[1.2*cm, 1.8*cm, 7*cm, 1.2*cm, 1.5*cm, 2.5*cm, 2.5*cm])
 t.setStyle(TableStyle([
 ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a6e')),
 ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
 ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
 ('FONTSIZE', (0, 0), (-1, -1), 7.5),
 ('ROWBACKGROUNDS', (0, 1), (-1, -5), [colors.white, colors.HexColor('#f0f4ff')]),
 ('FONTNAME', (0, -4), (-1, -1), 'Helvetica-Bold'),
 ('GRID', (0, 0), (-1, -5), 0.3, colors.grey),
 ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
 ]))
 hikaye.append(t)

 doc.build(hikaye)
 QMessageBox.information(self, "Başarılı", f"PDF kaydedildi:\n{yol}")
 self._durum_guncelle(f"PDF export: {os.path.basename(yol)}")

 except ImportError:
 QMessageBox.critical(self, "Hata", "reportlab paketi bulunamadı.")
 except Exception as e:
 QMessageBox.critical(self, "Hata", f"PDF export hatası:\n{e}")
 logger.exception("PDF export hatası")

 def _temizle(self):
 cevap = QMessageBox.question(
 self, "Onay", "Tüm kalemler silinecek. Emin misiniz?",
 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
 )
 if cevap == QMessageBox.StandardButton.Yes:
 self.engine = YaklasikMaliyetEngine()
 self._tablo_yenile()
 self._durum_guncelle("Cetvel temizlendi.")

 def _durum_guncelle(self, mesaj: str):
 self.durum_label.setText(mesaj)

 def _apply_style(self):
 self.setStyleSheet("""
 QGroupBox {
 border: 1px solid #333;
 border-radius: 4px;
 margin-top: 8px;
 padding-top: 4px;
 color: #ccc;
 font-weight: bold;
 }
 QTableWidget {
 background-color: #1e1e2e;
 color: #ddd;
 gridline-color: #333;
 border: 1px solid #333;
 }
 QTableWidget::item:selected {
 background-color: #0078d4;
 }
 QHeaderView::section {
 background-color: #1a1a4e;
 color: white;
 font-weight: bold;
 padding: 4px;
 border: 1px solid #333;
 }
 QPushButton {
 background-color: #2d2d4e;
 color: #ddd;
 border: 1px solid #444;
 border-radius: 4px;
 padding: 6px 16px;
 font-size: 12px;
 font-weight: bold;
 }
 QPushButton:hover { background-color: #3d3d6e; }
 QLineEdit, QComboBox, QDoubleSpinBox {
 background-color: #1e1e2e;
 color: #ddd;
 border: 1px solid #444;
 border-radius: 3px;
 padding: 4px;
 }
 """)
