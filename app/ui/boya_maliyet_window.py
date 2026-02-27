"""
Boya Maliyet Hesaplama Penceresi
Yüklenici modu için gelişmiş boya maliyet hesaplama arayüzü
"""

from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
 QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
 QGroupBox, QLabel, QLineEdit, QDoubleSpinBox, QSpinBox,
 QComboBox, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem,
 QMessageBox, QFrame, QScrollArea, QSplitter, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from app.core.material_calculator import hesapla_boya_maliyet_gelismis


class BoyaMaliyetWindow(QMainWindow):
 """Gelişmiş boya maliyet hesaplama penceresi"""

 hesaplama_tamamlandi = pyqtSignal(dict)

 def __init__(self, parent=None):
     super().__init__(parent)
 self.sonuc: Optional[Dict[str, Any]] = None
 self.son_hesaplama = None
 self.init_ui()

 def init_ui(self):
     """Arayüzü oluştur"""
 self.setWindowTitle("Boya Maliyet Hesaplama (Gelişmiş)")
 self.setGeometry(100, 100, 1100, 800)
 self.setMinimumSize(900, 700)

 # Ana widget
 central_widget = QWidget()
 self.setCentralWidget(central_widget)

 # Ana layout
 main_layout = QHBoxLayout(central_widget)
 main_layout.setContentsMargins(15, 15, 15, 15)
 main_layout.setSpacing(15)

 # Splitter ile sol-sağ ayırma
 splitter = QSplitter(Qt.Orientation.Horizontal)
 main_layout.addWidget(splitter)

 # =====================================================================
 # SOL PANEL - GİRDİ ALANLARI
 # =====================================================================
 left_widget = QWidget()
 left_layout = QVBoxLayout(left_widget)
 left_layout.setContentsMargins(0, 0, 0, 0)
 left_layout.setSpacing(10)

 # Scroll area (girdi paneli için)
 scroll = QScrollArea()
 scroll.setWidgetResizable(True)
 scroll.setFrameShape(QFrame.Shape.NoFrame)

 scroll_content = QWidget()
 scroll_layout = QVBoxLayout(scroll_content)
 scroll_layout.setSpacing(15)

 # -----------------------------------------------------------------
 # 1. ALAN BİLGİLERİ
 # -----------------------------------------------------------------
 alan_group = QGroupBox("Alan Bilgileri")
 alan_group.setStyleSheet("QGroupBox { font-weight: bold; }")
 alan_layout = QGridLayout()
 alan_layout.setSpacing(10)

 # Boyanacak alan
 alan_layout.addWidget(QLabel("Boyanacak Alan (m²):"), 0, 0)
 self.alan_spin = QDoubleSpinBox()
 self.alan_spin.setRange(0.01, 999999.99)
 self.alan_spin.setDecimals(2)
 self.alan_spin.setValue(100.0)
 self.alan_spin.setSuffix(" m²")
 self.alan_spin.setStyleSheet("font-size: 14px; padding: 5px;")
 alan_layout.addWidget(self.alan_spin, 0, 1)

 alan_group.setLayout(alan_layout)
 scroll_layout.addWidget(alan_group)

 # -----------------------------------------------------------------
 # 2. UYGULAMA AYARLARI
 # -----------------------------------------------------------------
 uygulama_group = QGroupBox("Uygulama Ayarları")
 uygulama_group.setStyleSheet("QGroupBox { font-weight: bold; }")
 uygulama_layout = QGridLayout()
 uygulama_layout.setSpacing(10)

 # Kat sayısı
 uygulama_layout.addWidget(QLabel("Kat Sayısı:"), 0, 0)
 self.kat_combo = QComboBox()
 self.kat_combo.addItems(["1 Kat", "2 Kat"])
 self.kat_combo.setCurrentIndex(1) # Varsayılan: 2 kat
 self.kat_combo.setStyleSheet("font-size: 13px; padding: 5px;")
 uygulama_layout.addWidget(self.kat_combo, 0, 1)

 # Bilgi etiketi
 kat_info = QLabel("1 kat seçilirse iş %50 daha hızlı tamamlanır")
 kat_info.setStyleSheet("color: #888; font-size: 11px;")
 uygulama_layout.addWidget(kat_info, 1, 0, 1, 2)

 # Astar durumu
 uygulama_layout.addWidget(QLabel("Astar Uygulaması:"), 2, 0)
 self.astar_check = QCheckBox("Astar yapılacak")
 self.astar_check.setChecked(True) # Varsayılan: Evet
 self.astar_check.stateChanged.connect(self.on_astar_changed)
 uygulama_layout.addWidget(self.astar_check, 2, 1)

 # Bilgi etiketi
 astar_info = QLabel("Astar yapılmazsa hız %10 artar")
 astar_info.setStyleSheet("color: #888; font-size: 11px;")
 uygulama_layout.addWidget(astar_info, 3, 0, 1, 2)

 uygulama_group.setLayout(uygulama_layout)
 scroll_layout.addWidget(uygulama_group)

 # -----------------------------------------------------------------
 # 3. FİYAT BİLGİLERİ
 # -----------------------------------------------------------------
 fiyat_group = QGroupBox("Fiyat Bilgileri (TL)")
 fiyat_group.setStyleSheet("QGroupBox { font-weight: bold; }")
 fiyat_layout = QGridLayout()
 fiyat_layout.setSpacing(10)

 # Boya kova fiyatı
 fiyat_layout.addWidget(QLabel("Boya Kovası (20 Kg):"), 0, 0)
 self.boya_fiyat_spin = QDoubleSpinBox()
 self.boya_fiyat_spin.setRange(0, 99999.99)
 self.boya_fiyat_spin.setDecimals(2)
 self.boya_fiyat_spin.setValue(1500.0)
 self.boya_fiyat_spin.setSuffix(" TL")
 self.boya_fiyat_spin.setStyleSheet("font-size: 13px; padding: 5px;")
 fiyat_layout.addWidget(self.boya_fiyat_spin, 0, 1)

 # Astar kova fiyatı
 fiyat_layout.addWidget(QLabel("Astar Kovası (20 Kg):"), 1, 0)
 self.astar_fiyat_spin = QDoubleSpinBox()
 self.astar_fiyat_spin.setRange(0, 99999.99)
 self.astar_fiyat_spin.setDecimals(2)
 self.astar_fiyat_spin.setValue(800.0)
 self.astar_fiyat_spin.setSuffix(" TL")
 self.astar_fiyat_spin.setStyleSheet("font-size: 13px; padding: 5px;")
 fiyat_layout.addWidget(self.astar_fiyat_spin, 1, 1)

 # Ekip günlük ücret
 fiyat_layout.addWidget(QLabel("Ekip Günlük Ücret:"), 2, 0)
 self.ekip_ucret_spin = QDoubleSpinBox()
 self.ekip_ucret_spin.setRange(0, 99999.99)
 self.ekip_ucret_spin.setDecimals(2)
 self.ekip_ucret_spin.setValue(3500.0)
 self.ekip_ucret_spin.setSuffix(" TL")
 self.ekip_ucret_spin.setStyleSheet("font-size: 13px; padding: 5px;")
 fiyat_layout.addWidget(self.ekip_ucret_spin, 2, 1)

 ekip_info = QLabel("1 Usta + 1 Yardımcı")
 ekip_info.setStyleSheet("color: #888; font-size: 11px;")
 fiyat_layout.addWidget(ekip_info, 3, 0, 1, 2)

 fiyat_group.setLayout(fiyat_layout)
 scroll_layout.addWidget(fiyat_group)

 # -----------------------------------------------------------------
 # 4. VERİM AYARLARI
 # -----------------------------------------------------------------
 verim_group = QGroupBox("Verim / Hız Ayarları")
 verim_group.setStyleSheet("QGroupBox { font-weight: bold; }")
 verim_layout = QGridLayout()
 verim_layout.setSpacing(10)

 # Verim kaynağı
 verim_layout.addWidget(QLabel("Verim Kaynağı:"), 0, 0)
 self.verim_combo = QComboBox()
 self.verim_combo.addItems([
 "Piyasa (90 m²/gün)",
 "ÇSB Resmi (45 m²/gün)",
 "Manuel"
 ])
 self.verim_combo.currentIndexChanged.connect(self.on_verim_changed)
 self.verim_combo.setStyleSheet("font-size: 13px; padding: 5px;")
 verim_layout.addWidget(self.verim_combo, 0, 1)

 # Manuel hız (başlangıçta gizli)
 verim_layout.addWidget(QLabel("Manuel Hız (m²/gün):"), 1, 0)
 self.manuel_hiz_spin = QDoubleSpinBox()
 self.manuel_hiz_spin.setRange(1, 500)
 self.manuel_hiz_spin.setDecimals(1)
 self.manuel_hiz_spin.setValue(90.0)
 self.manuel_hiz_spin.setSuffix(" m²/gün")
 self.manuel_hiz_spin.setEnabled(False)
 self.manuel_hiz_spin.setStyleSheet("font-size: 13px; padding: 5px;")
 verim_layout.addWidget(self.manuel_hiz_spin, 1, 1)

 # Fire oranı
 verim_layout.addWidget(QLabel("Fire Oranı (%):"), 2, 0)
 self.fire_spin = QDoubleSpinBox()
 self.fire_spin.setRange(0, 50)
 self.fire_spin.setDecimals(1)
 self.fire_spin.setValue(5.0)
 self.fire_spin.setSuffix(" %")
 self.fire_spin.setStyleSheet("font-size: 13px; padding: 5px;")
 verim_layout.addWidget(self.fire_spin, 2, 1)

 fire_info = QLabel("Malzeme kaybı için ek miktar")
 fire_info.setStyleSheet("color: #888; font-size: 11px;")
 verim_layout.addWidget(fire_info, 3, 0, 1, 2)

 verim_group.setLayout(verim_layout)
 scroll_layout.addWidget(verim_group)

 # -----------------------------------------------------------------
 # HESAPLA BUTONU
 # -----------------------------------------------------------------
 btn_layout = QHBoxLayout()

 self.hesapla_btn = QPushButton("HESAPLA")
 self.hesapla_btn.setStyleSheet("""
 QPushButton {
 background-color: #2196F3;
 color: white;
 font-size: 16px;
 font-weight: bold;
 padding: 15px 40px;
 border-radius: 8px;
 min-width: 200px;
 }
 QPushButton:hover {
 background-color: #1976D2;
 }
 QPushButton:pressed {
 background-color: #0D47A1;
 }
 """)
 self.hesapla_btn.clicked.connect(self.hesapla)
 btn_layout.addStretch()
 btn_layout.addWidget(self.hesapla_btn)
 btn_layout.addStretch()

 scroll_layout.addLayout(btn_layout)
 scroll_layout.addStretch()

 scroll.setWidget(scroll_content)
 left_layout.addWidget(scroll)

 splitter.addWidget(left_widget)

 # =====================================================================
 # SAĞ PANEL - SONUÇLAR
 # =====================================================================
 right_widget = QWidget()
 right_layout = QVBoxLayout(right_widget)
 right_layout.setContentsMargins(0, 0, 0, 0)
 right_layout.setSpacing(10)

 # Başlık
 sonuc_baslik = QLabel("HESAPLAMA SONUÇLARI")
 sonuc_baslik.setFont(QFont("Arial", 14, QFont.Weight.Bold))
 sonuc_baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
 sonuc_baslik.setStyleSheet("color: #2196F3; padding: 10px;")
 right_layout.addWidget(sonuc_baslik)

 # -----------------------------------------------------------------
 # ÖZET KARTLARI
 # -----------------------------------------------------------------
 cards_layout = QGridLayout()
 cards_layout.setSpacing(10)

 # Kart 1: Toplam Maliyet
 self.card_toplam = self._create_card("GENEL TOPLAM", "0.00 TL", "#4CAF50")
 cards_layout.addWidget(self.card_toplam, 0, 0)

 # Kart 2: İşçilik
 self.card_iscilik = self._create_card("İŞÇİLİK", "0.00 TL", "#FF9800")
 cards_layout.addWidget(self.card_iscilik, 0, 1)

 # Kart 3: Malzeme
 self.card_malzeme = self._create_card("MALZEME", "0.00 TL", "#2196F3")
 cards_layout.addWidget(self.card_malzeme, 1, 0)

 # Kart 4: Süre
 self.card_sure = self._create_card("TAHMİNİ SÜRE", "0 Gün", "#9C27B0")
 cards_layout.addWidget(self.card_sure, 1, 1)

 right_layout.addLayout(cards_layout)

 # -----------------------------------------------------------------
 # DETAY TABLOSU
 # -----------------------------------------------------------------
 detay_group = QGroupBox("Detaylı Hesaplama")
 detay_group.setStyleSheet("QGroupBox { font-weight: bold; }")
 detay_layout = QVBoxLayout()

 self.detay_table = QTableWidget()
 self.detay_table.setColumnCount(2)
 self.detay_table.setHorizontalHeaderLabels(["Kalem", "Değer"])
 self.detay_table.horizontalHeader().setStretchLastSection(True)
 self.detay_table.setAlternatingRowColors(True)
 self.detay_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
 self.detay_table.setStyleSheet("""
 QTableWidget {
 font-size: 12px;
 }
 QTableWidget::item {
 padding: 8px;
 }
 """)

 detay_layout.addWidget(self.detay_table)
 detay_group.setLayout(detay_layout)
 right_layout.addWidget(detay_group)

 # -----------------------------------------------------------------
 # FORMÜL AÇIKLAMASI
 # -----------------------------------------------------------------
 formul_group = QGroupBox("Hesaplama Formülleri")
 formul_group.setStyleSheet("QGroupBox { font-weight: bold; }")
 formul_layout = QVBoxLayout()

 self.formul_text = QTextEdit()
 self.formul_text.setReadOnly(True)
 self.formul_text.setMaximumHeight(150)
 self.formul_text.setStyleSheet("font-size: 11px; background-color: #f5f5f5;")
 self.formul_text.setPlainText(
 "Boya (kg) = Alan × Kat Sayısı × 0.150 × (1 + Fire)\n"
 "Astar (kg) = Alan × 0.150 × (1 + Fire)\n"
 "Kova Adet = Miktar (kg) / 20 (yukarı yuvarla)\n"
 "\n"
 "Hız Çarpanları:\n"
 "• 1 Kat seçilirse: Baz hız × 1.5\n"
 "• Astar yapılmazsa: Hız × 1.1\n"
 "\n"
 "Süre (gün) = Alan / Efektif Hız (yukarı yuvarla)"
 )
 formul_layout.addWidget(self.formul_text)
 formul_group.setLayout(formul_layout)
 right_layout.addWidget(formul_group)

 # Metraya Aktar butonu
 btn_metraya_aktar = QPushButton(" Metraya Aktar")
 btn_metraya_aktar.setStyleSheet("background-color: #FF6600; color: white; font-weight: bold; padding: 8px;")
 btn_metraya_aktar.clicked.connect(self._metraya_aktar)
 right_layout.addWidget(btn_metraya_aktar)

 splitter.addWidget(right_widget)

 # Splitter oranları
 splitter.setSizes([450, 650])

 # Durum çubuğu
 self.statusBar().showMessage("Hesaplama için değerleri girin ve HESAPLA butonuna tıklayın.")

 def _create_card(self, title: str, value: str, color: str) -> QFrame:
     """Özet kartı oluştur"""
 card = QFrame()
 card.setFrameShape(QFrame.Shape.StyledPanel)
 card.setStyleSheet(f"""
 QFrame {{
 background-color: {color};
 border-radius: 10px;
 padding: 15px;
 }}
 """)

 layout = QVBoxLayout(card)
 layout.setSpacing(5)

 title_label = QLabel(title)
 title_label.setFont(QFont("Arial", 10))
 title_label.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
 title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
 layout.addWidget(title_label)

 value_label = QLabel(value)
 value_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
 value_label.setStyleSheet("color: white;")
 value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
 value_label.setObjectName("value_label")
 layout.addWidget(value_label)

 return card

 def _update_card_value(self, card: QFrame, value: str):
     """Kart değerini güncelle"""
 value_label = card.findChild(QLabel, "value_label")
 if value_label:
     value_label.setText(value)

 def on_astar_changed(self, state: int):
     """Astar durumu değiştiğinde"""
 self.astar_fiyat_spin.setEnabled(state == Qt.CheckState.Checked.value)

 def on_verim_changed(self, index: int):
     """Verim kaynağı değiştiğinde"""
 # Manuel seçiliyse manuel hız alanını aktif et
 self.manuel_hiz_spin.setEnabled(index == 2)

 def hesapla(self):
     """Hesaplama yap"""
 try:
 # Değerleri al
     alan = self.alan_spin.value()
     kat_sayisi = 1 if self.kat_combo.currentIndex() == 0 else 2
     astar_yapilacak = self.astar_check.isChecked()
     boya_fiyat = self.boya_fiyat_spin.value()
     astar_fiyat = self.astar_fiyat_spin.value()
     ekip_ucret = self.ekip_ucret_spin.value()
     fire_orani = self.fire_spin.value() / 100.0

 # Verim kaynağı
     verim_index = self.verim_combo.currentIndex()
     if verim_index == 0:
         verim_kaynagi = 'piyasa'
     elif verim_index == 1:
         verim_kaynagi = 'csb_resmi'
     else:
         verim_kaynagi = 'manuel'

     manuel_hiz = self.manuel_hiz_spin.value() if verim_kaynagi == 'manuel' else None

 # Hesapla
     self.sonuc = hesapla_boya_maliyet_gelismis(
 boyanacak_alan_m2=alan,
 kat_sayisi=kat_sayisi,
 astar_yapilacak_mi=astar_yapilacak,
 kova_birim_fiyat=boya_fiyat,
 astar_kova_fiyat=astar_fiyat,
 ekip_gunluk_ucret=ekip_ucret,
 fire_orani=fire_orani,
 verim_kaynagi=verim_kaynagi,
 manuel_hiz=manuel_hiz
 )

 # Sonuçları göster
     self.son_hesaplama = self.sonuc
     self._goster_sonuclar()

     self.statusBar().showMessage("Hesaplama başarıyla tamamlandı.", 5000)

 except ValueError as e:
     QMessageBox.warning(self, "Uyarı", str(e))
 except Exception as e:
     QMessageBox.critical(self, "Hata", f"Hesaplama hatası: {str(e)}")

 def _goster_sonuclar(self):
     """Sonuçları arayüzde göster"""
 if not self.sonuc:
     return

 # Kartları güncelle
 self._update_card_value(
 self.card_toplam,
 f"{self.sonuc['genel_toplam_maliyet_tl']:,.2f} TL"
 )
 self._update_card_value(
 self.card_iscilik,
 f"{self.sonuc['toplam_iscilik_tl']:,.2f} TL"
 )
 self._update_card_value(
 self.card_malzeme,
 f"{self.sonuc['toplam_malzeme_tl']:,.2f} TL"
 )
 self._update_card_value(
 self.card_sure,
 f"{self.sonuc['tahmini_sure_gun']} Gün"
 )

 # Detay tablosunu doldur
 detaylar = [
 ("Boyanacak Alan", f"{self.sonuc['_detay']['boyanacak_alan_m2']:,.2f} m²"),
 ("Uygulanan Kat Sayısı", str(self.sonuc['uygulanan_kat_sayisi'])),
 ("Astar Durumu", "Evet" if self.sonuc['astar_durumu'] else "Hayır"),
 ("", ""), # Boş satır
 ("Toplam Boya Miktarı", f"{self.sonuc['toplam_boya_kg']:,.2f} kg"),
 ("Gereken Boya Kovası", f"{self.sonuc['gereken_boya_kova_adet']} adet"),
 ("Toplam Astar Miktarı", f"{self.sonuc['toplam_astar_kg']:,.2f} kg"),
 ("Gereken Astar Kovası", f"{self.sonuc['gereken_astar_kova_adet']} adet"),
 ("", ""), # Boş satır
 ("Fire Oranı", f"%{self.sonuc['_detay']['fire_orani'] * 100:.1f}"),
 ("Verim Kaynağı", self.sonuc['_detay']['verim_kaynagi'].upper()),
 ("Baz Hız", f"{self.sonuc['_detay']['baz_hiz_m2_gun']:.1f} m²/gün"),
 ("Hız Çarpanı", f"×{self.sonuc['_detay']['hiz_carpani']:.2f}"),
 ("Efektif Hız", f"{self.sonuc['_detay']['efektif_hiz_m2_gun']:.1f} m²/gün"),
 ("", ""), # Boş satır
 ("Tahmini Süre", f"{self.sonuc['tahmini_sure_gun']} gün"),
 ("", ""), # Boş satır
 ("Boya Maliyeti", f"{self.sonuc['_detay']['boya_maliyeti_tl']:,.2f} TL"),
 ("Astar Maliyeti", f"{self.sonuc['_detay']['astar_maliyeti_tl']:,.2f} TL"),
 ("Toplam Malzeme", f"{self.sonuc['toplam_malzeme_tl']:,.2f} TL"),
 ("Toplam İşçilik", f"{self.sonuc['toplam_iscilik_tl']:,.2f} TL"),
 ("", ""), # Boş satır
 ("GENEL TOPLAM", f"{self.sonuc['genel_toplam_maliyet_tl']:,.2f} TL"),
 ]

 self.detay_table.setRowCount(len(detaylar))

 for row, (kalem, deger) in enumerate(detaylar):
     kalem_item = QTableWidgetItem(kalem)
 deger_item = QTableWidgetItem(deger)

 # Genel toplam satırını vurgula
 if kalem == "GENEL TOPLAM":
     font = QFont()
 font.setBold(True)
 kalem_item.setFont(font)
 deger_item.setFont(font)
 kalem_item.setBackground(QColor("#E8F5E9"))
 deger_item.setBackground(QColor("#E8F5E9"))

 # Boş satırları grileştir
 if not kalem:
     kalem_item.setBackground(QColor("#f0f0f0"))
 deger_item.setBackground(QColor("#f0f0f0"))

 self.detay_table.setItem(row, 0, kalem_item)
 self.detay_table.setItem(row, 1, deger_item)

 self.detay_table.resizeColumnsToContents()

 def _metraya_aktar(self):
     """Hesaplama sonucunu metraj listesine aktar"""
 if self.son_hesaplama is None:
     from PyQt6.QtWidgets import QMessageBox
 QMessageBox.warning(self, "Uyarı", "Önce bir hesaplama yapın!")
 return
 self.hesaplama_tamamlandi.emit(self.son_hesaplama)


# Test için
if __name__ == "__main__":
 import sys
 from PyQt6.QtWidgets import QApplication

 app = QApplication(sys.argv)
 window = BoyaMaliyetWindow()
 window.show()
 sys.exit(app.exec())
