"""
Enflasyon ve Fiyat Farkı Hesaplama Sekmesi
TÜFE/ÜFE bazlı fiyat farkı hesaplama ve raporlama
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QDateEdit, QTextEdit, QMessageBox,
    QHeaderView, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor
from typing import Optional
from datetime import datetime
import logging

from app.core.database import DatabaseManager
from app.core.enflasyon_engine import EnflasyonEngine

logger = logging.getLogger(__name__)


class EnflasyonWindow(QWidget):
    """Enflasyon ve fiyat farkı hesaplama widget'i"""

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        # Kaydedilmiş API anahtarını yükle
        saved_key = self.db.get_ayar("tcmb_api_key")
        self.engine = EnflasyonEngine(api_key=saved_key if saved_key else None)
        self.init_ui()

    def init_ui(self):
        """UI elementlerini oluştur"""
        layout = QVBoxLayout()

        # Başlık
        baslik = QLabel(" Enflasyon ve Fiyat Farkı Hesaplama")
        baslik.setStyleSheet("font-size: 18pt; font-weight: bold; margin: 10px;")
        layout.addWidget(baslik)

        # TCMB API Anahtarı ayar alanı
        api_group = self._create_api_key_alani()
        layout.addWidget(api_group)

        # Hesaplama formu
        form_group = self._create_hesaplama_formu()
        layout.addWidget(form_group)

        # Sonuç tablosu
        sonuc_group = self._create_sonuc_alani()
        layout.addWidget(sonuc_group)

        # Geçmiş hesaplamalar tablosu
        gecmis_group = self._create_gecmis_tablosu()
        layout.addWidget(gecmis_group)

        self.setLayout(layout)

    def _create_api_key_alani(self) -> QGroupBox:
        """TCMB API anahtarı giriş alanı"""
        group = QGroupBox("TCMB EVDS API Ayarları")
        layout = QHBoxLayout()

        layout.addWidget(QLabel("API Anahtarı:"))

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("TCMB EVDS API anahtarınızı giriniz...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        saved_key = self.db.get_ayar("tcmb_api_key")
        if saved_key:
            self.api_key_input.setText(saved_key)
        layout.addWidget(self.api_key_input)

        # Göster/Gizle butonu
        self.api_show_btn = QPushButton("Göster")
        self.api_show_btn.setFixedWidth(60)
        self.api_show_btn.clicked.connect(self._toggle_api_key_visibility)
        layout.addWidget(self.api_show_btn)

        # Kaydet butonu
        save_btn = QPushButton("Kaydet")
        save_btn.setFixedWidth(80)
        save_btn.clicked.connect(self._save_api_key)
        layout.addWidget(save_btn)

        # Durum etiketi
        self.api_status_label = QLabel()
        if saved_key:
            self.api_status_label.setText("Bağlı")
            self.api_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.api_status_label.setText("Bağlı değil (örnek veri kullanılıyor)")
            self.api_status_label.setStyleSheet("color: #FF9800; font-weight: bold;")
        layout.addWidget(self.api_status_label)

        info_btn = QPushButton("?")
        info_btn.setFixedWidth(30)
        info_btn.setToolTip("API anahtarı nasıl alınır?")
        info_btn.clicked.connect(self._show_api_help)
        layout.addWidget(info_btn)

        group.setLayout(layout)
        return group

    def _toggle_api_key_visibility(self):
        """API anahtarını göster/gizle"""
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.api_show_btn.setText("Gizle")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.api_show_btn.setText("Göster")

    def _save_api_key(self):
        """API anahtarını kaydet ve motoru güncelle"""
        key = self.api_key_input.text().strip()
        self.db.save_ayar("tcmb_api_key", key)

        if key:
            self.engine = EnflasyonEngine(api_key=key)
            self.api_status_label.setText("Bağlı")
            self.api_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            QMessageBox.information(self, "Başarılı", "API anahtarı kaydedildi.\nArtık gerçek TCMB verileri kullanılacak.")
        else:
            self.engine = EnflasyonEngine()
            self.api_status_label.setText("Bağlı değil (örnek veri kullanılıyor)")
            self.api_status_label.setStyleSheet("color: #FF9800; font-weight: bold;")

    def _show_api_help(self):
        """API anahtarı alma rehberi"""
        QMessageBox.information(
            self, "TCMB EVDS API Anahtarı",
            "TCMB EVDS API anahtarı almak için:\n\n"
            "1. https://evds2.tcmb.gov.tr/ adresine gidin\n"
            "2. 'Kayıt Ol' butonuna tıklayın\n"
            "3. E-posta ve bilgilerinizi girin\n"
            "4. Hesabınız onaylandıktan sonra giriş yapın\n"
            "5. Profil sayfanızdan API anahtarınızı kopyalayın\n\n"
            "API anahtarı ile gerçek TÜFE/ÜFE verileri\n"
            "TCMB'den otomatik olarak çekilecektir."
        )

    def _create_hesaplama_formu(self) -> QGroupBox:
        """Hesaplama formu oluştur"""
        group = QGroupBox("Fiyat Farkı Hesaplama")
        layout = QFormLayout()

        # Başlangıç fiyatı
        self.baslangic_fiyat_input = QDoubleSpinBox()
        self.baslangic_fiyat_input.setRange(0, 999999999)
        self.baslangic_fiyat_input.setDecimals(2)
        self.baslangic_fiyat_input.setSuffix(" TL")
        self.baslangic_fiyat_input.setValue(100000)
        layout.addRow("Başlangıç Fiyatı:", self.baslangic_fiyat_input)

        # Başlangıç tarihi
        self.baslangic_tarih_input = QDateEdit()
        self.baslangic_tarih_input.setDate(QDate(2024, 1, 1))
        self.baslangic_tarih_input.setCalendarPopup(True)
        self.baslangic_tarih_input.setDisplayFormat("dd-MM-yyyy")
        layout.addRow("Başlangıç Tarihi:", self.baslangic_tarih_input)

        # Bitiş tarihi
        self.bitis_tarih_input = QDateEdit()
        self.bitis_tarih_input.setDate(QDate.currentDate())
        self.bitis_tarih_input.setCalendarPopup(True)
        self.bitis_tarih_input.setDisplayFormat("dd-MM-yyyy")
        layout.addRow("Bitiş Tarihi:", self.bitis_tarih_input)

        # Endeks tipi
        self.endeks_combo = QComboBox()
        self.endeks_combo.addItems(["TÜFE (Tüketici Fiyat Endeksi)", "ÜFE (Üretici Fiyat Endeksi)"])
        layout.addRow("Endeks Tipi:", self.endeks_combo)

        # Hesapla butonu
        hesapla_btn = QPushButton("Hesapla")
        hesapla_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 10px;
                font-size: 14pt;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        hesapla_btn.clicked.connect(self.hesapla_fiyat_farki)
        layout.addRow("", hesapla_btn)

        group.setLayout(layout)
        return group

    def _create_sonuc_alani(self) -> QGroupBox:
        """Sonuç alanı oluştur"""
        group = QGroupBox("Hesaplama Sonuçları")
        layout = QVBoxLayout()

        # Sonuç metni
        self.sonuc_text = QTextEdit()
        self.sonuc_text.setReadOnly(True)
        self.sonuc_text.setMaximumHeight(200)
        self.sonuc_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #e0e0e0;
                border: 1px solid #3a3a4a;
                border-radius: 5px;
                padding: 10px;
                font-size: 11pt;
            }
        """)
        layout.addWidget(self.sonuc_text)

        # Kaydet ve export butonları
        btn_layout = QHBoxLayout()

        kaydet_btn = QPushButton(" Kaydet")
        kaydet_btn.clicked.connect(self.kaydet_hesaplama)
        btn_layout.addWidget(kaydet_btn)

        export_btn = QPushButton(" Excel'e Aktar")
        export_btn.clicked.connect(self.export_excel)
        btn_layout.addWidget(export_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        group.setLayout(layout)
        return group

    def _create_gecmis_tablosu(self) -> QGroupBox:
        """Geçmiş hesaplamalar tablosu"""
        group = QGroupBox("Geçmiş Hesaplamalar")
        layout = QVBoxLayout()

        self.gecmis_table = QTableWidget()
        self.gecmis_table.setColumnCount(8)
        self.gecmis_table.setHorizontalHeaderLabels([
            "Tarih", "Başlangıç Fiyat", "Başlangıç Tarihi",
            "Bitiş Tarihi", "Endeks", "Enflasyon %",
            "Güncel Fiyat", "Fark"
        ])
        self.gecmis_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.gecmis_table)

        # Yenile butonu
        yenile_btn = QPushButton(" Geçmişi Yenile")
        yenile_btn.clicked.connect(self.load_gecmis)
        layout.addWidget(yenile_btn)

        group.setLayout(layout)
        return group

    def hesapla_fiyat_farki(self):
        """Fiyat farkını hesapla ve göster"""
        try:
            # Değerleri al
            baslangic_fiyat = self.baslangic_fiyat_input.value()
            baslangic_tarihi = self.baslangic_tarih_input.date().toString("dd-MM-yyyy")
            bitis_tarihi = self.bitis_tarih_input.date().toString("dd-MM-yyyy")
            endeks_tipi = "TUFE" if self.endeks_combo.currentIndex() == 0 else "UFE"

            # Hesapla
            sonuc = self.engine.hesapla_fiyat_farki(
                baslangic_fiyat=baslangic_fiyat,
                baslangic_tarihi=baslangic_tarihi,
                bitis_tarihi=bitis_tarihi,
                endeks_tipi=endeks_tipi
            )

            # Sonucu göster
            self._goster_sonuc(sonuc)

            # Sonucu kaydet (geçici olarak self'e)
            self.son_hesaplama = sonuc

        except Exception as e:
            logger.error(f"Hesaplama hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Hesaplama sırasında hata oluştu:\n{str(e)}")

    def _goster_sonuc(self, sonuc: dict):
        """Sonucu formatla ve göster"""
        hata_msg = sonuc.get('hata', '')
        bilgi_notu = ""
        if hata_msg:
            bilgi_notu = f"""
<p style="margin-top: 20px; padding: 10px; background-color: #F44336; border-radius: 5px; color: white;">
<b>Uyarı:</b> {hata_msg} — Sonuçlar tahmini olabilir.
</p>"""
        elif not self.engine.api_key:
            bilgi_notu = """
<p style="margin-top: 20px; padding: 10px; background-color: #1976D2; border-radius: 5px; color: white;">
<b>Bilgi:</b> Bu hesaplama örnek verilerle yapılmıştır.
TCMB API anahtarı ile gerçek enflasyon verileri kullanılabilir.
</p>"""

        html = f"""
<div style="font-family: 'Segoe UI', Arial; padding: 10px;">
<h2 style="color: #4CAF50;">Fiyat Farki Hesaplama Sonucu</h2>

<table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
<tr style="background-color: #2a2a3a;">
<td style="padding: 10px; border: 1px solid #3a3a4a;"><b>Baslangic Fiyati:</b></td>
<td style="padding: 10px; border: 1px solid #3a3a4a; text-align: right;">
<span style="font-size: 14pt; color: #90CAF9;">{sonuc.get('baslangic_fiyat', 0):,.2f} TL</span>
</td>
</tr>
<tr style="background-color: #1e1e2e;">
<td style="padding: 10px; border: 1px solid #3a3a4a;"><b>Guncel Fiyat:</b></td>
<td style="padding: 10px; border: 1px solid #3a3a4a; text-align: right;">
<span style="font-size: 14pt; color: #4CAF50;">{sonuc.get('guncel_fiyat', 0):,.2f} TL</span>
</td>
</tr>
<tr style="background-color: #2a2a3a;">
<td style="padding: 10px; border: 1px solid #3a3a4a;"><b>Fark (Tutar):</b></td>
<td style="padding: 10px; border: 1px solid #3a3a4a; text-align: right;">
<span style="font-size: 14pt; color: #FF9800;">{sonuc.get('fark', 0):,.2f} TL</span>
</td>
</tr>
<tr style="background-color: #1e1e2e;">
<td style="padding: 10px; border: 1px solid #3a3a4a;"><b>Fark (Yuzde):</b></td>
<td style="padding: 10px; border: 1px solid #3a3a4a; text-align: right;">
<span style="font-size: 14pt; color: #FF9800;">%{sonuc.get('fark_yuzde', 0):.2f}</span>
</td>
</tr>
<tr style="background-color: #2a2a3a;">
<td style="padding: 10px; border: 1px solid #3a3a4a;"><b>Enflasyon Orani:</b></td>
<td style="padding: 10px; border: 1px solid #3a3a4a; text-align: right;">
<span style="font-size: 14pt; color: #F44336;">%{sonuc.get('enflasyon_orani', 0):.2f}</span>
</td>
</tr>
<tr style="background-color: #1e1e2e;">
<td style="padding: 10px; border: 1px solid #3a3a4a;"><b>Donem:</b></td>
<td style="padding: 10px; border: 1px solid #3a3a4a; text-align: right;">
{sonuc.get('baslangic_tarihi', '-')} &rarr; {sonuc.get('bitis_tarihi', '-')}
</td>
</tr>
<tr style="background-color: #2a2a3a;">
<td style="padding: 10px; border: 1px solid #3a3a4a;"><b>Endeks Tipi:</b></td>
<td style="padding: 10px; border: 1px solid #3a3a4a; text-align: right;">
{sonuc.get('endeks_tipi', '-')}
</td>
</tr>
</table>
{bilgi_notu}
</div>
"""
        self.sonuc_text.setHtml(html)

    def kaydet_hesaplama(self):
        """Hesaplamayı veritabanına kaydet"""
        if not hasattr(self, 'son_hesaplama'):
            QMessageBox.warning(self, "Uyarı", "Önce bir hesaplama yapın!")
            return

        try:
            sonuc = self.son_hesaplama

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO fiyat_farki_hesaplamalari
                    (proje_id, baslangic_fiyat, baslangic_tarihi, bitis_tarihi,
                    endeks_tipi, enflasyon_orani, guncel_fiyat, fark, fark_yuzde,
                    olusturma_tarihi)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    None,  # Proje ID (opsiyonel)
                    sonuc['baslangic_fiyat'],
                    sonuc['baslangic_tarihi'],
                    sonuc['bitis_tarihi'],
                    sonuc['endeks_tipi'],
                    sonuc['enflasyon_orani'],
                    sonuc['guncel_fiyat'],
                    sonuc['fark'],
                    sonuc['fark_yuzde'],
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))

            QMessageBox.information(self, "Başarılı", "Hesaplama kaydedildi!")
            self.load_gecmis()

        except Exception as e:
            logger.error(f"Kaydetme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Kaydetme sırasında hata:\n{str(e)}")

    def load_gecmis(self):
        """Geçmiş hesaplamaları yükle"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM fiyat_farki_hesaplamalari
                    ORDER BY olusturma_tarihi DESC
                    LIMIT 50
                """)
                rows = cursor.fetchall()

            self.gecmis_table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                self.gecmis_table.setItem(row_idx, 0, QTableWidgetItem(row['olusturma_tarihi']))
                self.gecmis_table.setItem(row_idx, 1, QTableWidgetItem(f"{row['baslangic_fiyat']:,.2f} TL"))
                self.gecmis_table.setItem(row_idx, 2, QTableWidgetItem(row['baslangic_tarihi']))
                self.gecmis_table.setItem(row_idx, 3, QTableWidgetItem(row['bitis_tarihi']))
                self.gecmis_table.setItem(row_idx, 4, QTableWidgetItem(row['endeks_tipi']))
                self.gecmis_table.setItem(row_idx, 5, QTableWidgetItem(f"%{row['enflasyon_orani']:.2f}"))
                self.gecmis_table.setItem(row_idx, 6, QTableWidgetItem(f"{row['guncel_fiyat']:,.2f} TL"))
                self.gecmis_table.setItem(row_idx, 7, QTableWidgetItem(f"{row['fark']:,.2f} TL"))

        except Exception as e:
            logger.error(f"Geçmiş yükleme hatası: {e}")

    def export_excel(self):
        """Sonucu Excel'e aktar"""
        QMessageBox.information(self, "Bilgi", "Excel export özelliği yakında eklenecek!")
