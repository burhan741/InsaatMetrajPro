"""
QR Kod Bazlı Hakediş Sekmesi
QR kod ile iş takibi ve hakediş gerçekleşme girişi
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QTextEdit, QMessageBox, QHeaderView,
    QDoubleSpinBox, QDialog, QDialogButtonBox, QComboBox,
    QProgressBar, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage, QColor
from typing import Optional
from datetime import datetime
import logging

from app.core.database import DatabaseManager
from app.core.qr_hakedis_engine import QRHakedisEngine

logger = logging.getLogger(__name__)


class QRGosterDialog(QDialog):
    """QR kod gösterme dialog'u"""

    def __init__(self, qr_bytes: bytes, kalem_bilgi: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QR Kod")
        self.setModal(True)
        self.setMinimumSize(400, 500)

        layout = QVBoxLayout()

        # Başlık
        baslik = QLabel(f"📱 QR Kod - {kalem_bilgi.get('tanim', 'N/A')}")
        baslik.setStyleSheet("font-size: 14pt; font-weight: bold;")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(baslik)

        # QR kod resmi
        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Bytes'ı QPixmap'e çevir
        if qr_bytes:
            image = QImage()
            image.loadFromData(qr_bytes)
            pixmap = QPixmap.fromImage(image)
            pixmap = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
            qr_label.setPixmap(pixmap)
        else:
            qr_label.setText("QR kod oluşturulamadı")

        qr_label.setStyleSheet("""
            QLabel {
                background-color: white;
                padding: 20px;
                border: 2px solid #2196F3;
                border-radius: 10px;
            }
        """)
        layout.addWidget(qr_label)

        # Bilgi
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(150)
        info_text.setHtml(f"""
            <div style="font-family: 'Segoe UI'; padding: 10px;">
                <p><b>Poz No:</b> {kalem_bilgi.get('poz_no', 'N/A')}</p>
                <p><b>Tanım:</b> {kalem_bilgi.get('tanim', 'N/A')}</p>
                <p><b>Miktar:</b> {kalem_bilgi.get('miktar', 0)} {kalem_bilgi.get('birim', '')}</p>
                <p style="color: #2196F3;"><b>ℹ️ Mobil cihazınızla bu QR kodu okutarak gerçekleşme girişi yapabilirsiniz.</b></p>
            </div>
        """)
        layout.addWidget(info_text)

        # Kapat butonu
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.setLayout(layout)


class GerceklesmeDialog(QDialog):
    """Gerçekleşme girişi dialog'u"""

    def __init__(self, kalem_bilgi: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gerçekleşme Girişi")
        self.setModal(True)
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout()

        # Başlık
        baslik = QLabel(f"📝 Gerçekleşme Girişi\n{kalem_bilgi.get('tanim', 'N/A')}")
        baslik.setStyleSheet("font-size: 14pt; font-weight: bold;")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(baslik)

        # Form
        form_layout = QFormLayout()

        # Planlanan miktar (readonly)
        planlanan_label = QLabel(f"{kalem_bilgi.get('miktar', 0)} {kalem_bilgi.get('birim', '')}")
        planlanan_label.setStyleSheet("font-size: 12pt; color: #2196F3;")
        form_layout.addRow("Planlanan Miktar:", planlanan_label)

        # Gerçekleşen miktar
        self.gerceklesen_input = QDoubleSpinBox()
        self.gerceklesen_input.setRange(0, 999999)
        self.gerceklesen_input.setDecimals(2)
        self.gerceklesen_input.setSuffix(f" {kalem_bilgi.get('birim', '')}")
        self.gerceklesen_input.setValue(kalem_bilgi.get('miktar', 0))
        form_layout.addRow("Gerçekleşen Miktar:", self.gerceklesen_input)

        # Açıklama
        self.aciklama_input = QTextEdit()
        self.aciklama_input.setPlaceholderText("İş tamamlandı, kalite kontrolünden geçti.")
        self.aciklama_input.setMaximumHeight(100)
        form_layout.addRow("Açıklama:", self.aciklama_input)

        # Konum (placeholder)
        self.konum_input = QLineEdit()
        self.konum_input.setPlaceholderText("GPS: 41.0082, 28.9784 (Otomatik alınır)")
        self.konum_input.setReadOnly(True)
        form_layout.addRow("Konum:", self.konum_input)

        # Fotoğraf (placeholder)
        foto_layout = QHBoxLayout()
        self.foto_input = QLineEdit()
        self.foto_input.setPlaceholderText("Henüz fotoğraf eklenmedi")
        self.foto_input.setReadOnly(True)
        foto_layout.addWidget(self.foto_input)

        foto_btn = QPushButton("📷 Fotoğraf Ekle")
        foto_btn.clicked.connect(self.foto_ekle_placeholder)
        foto_layout.addWidget(foto_btn)

        form_layout.addRow("Fotoğraf:", foto_layout)

        layout.addLayout(form_layout)

        # Butonlar
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.setLayout(layout)

    def foto_ekle_placeholder(self):
        """Fotoğraf ekleme placeholder"""
        QMessageBox.information(
            self,
            "Bilgi",
            "Fotoğraf ekleme özelliği mobil uygulamada aktif olacaktır.\n\n"
            "Şu an için simüle edilmektedir."
        )
        self.foto_input.setText("foto_santiye_2026_01_11.jpg (Simüle)")

    def get_data(self) -> dict:
        """Form verilerini al"""
        return {
            'gerceklesen_miktar': self.gerceklesen_input.value(),
            'aciklama': self.aciklama_input.toPlainText(),
            'konum': self.konum_input.text() or None,
            'foto_path': self.foto_input.text() if self.foto_input.text() else None
        }


class QRHakedisWindow(QWidget):
    """QR Kod Bazlı Hakediş widget'i"""

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.engine = QRHakedisEngine(db)
        self.current_proje_id = None
        self.init_ui()
        self.load_projeler()

    def init_ui(self):
        """UI elementlerini oluştur"""
        layout = QVBoxLayout()

        # Başlık ve proje seçici
        header_layout = QHBoxLayout()

        baslik = QLabel("📱 QR Kod Bazlı Hakediş Sistemi")
        baslik.setStyleSheet("font-size: 18pt; font-weight: bold; margin: 10px;")
        header_layout.addWidget(baslik)

        header_layout.addStretch()

        # Proje seçimi
        proje_label = QLabel("Proje:")
        header_layout.addWidget(proje_label)

        self.proje_combo = QComboBox()
        self.proje_combo.currentIndexChanged.connect(self.on_proje_changed)
        header_layout.addWidget(self.proje_combo)

        layout.addLayout(header_layout)

        # Splitter (üst: durum özeti, alt: kalem listesi)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Hakediş durumu özeti
        durum_group = self._create_durum_ozeti()
        splitter.addWidget(durum_group)

        # İş kalemleri listesi
        kalemler_group = self._create_kalemler_tablosu()
        splitter.addWidget(kalemler_group)

        splitter.setSizes([200, 400])
        layout.addWidget(splitter)

        self.setLayout(layout)

    def _create_durum_ozeti(self) -> QGroupBox:
        """Hakediş durum özeti"""
        group = QGroupBox("📊 Hakediş Durum Özeti")
        layout = QVBoxLayout()

        # Özet bilgileri
        self.ozet_text = QTextEdit()
        self.ozet_text.setReadOnly(True)
        self.ozet_text.setMaximumHeight(150)
        layout.addWidget(self.ozet_text)

        # İlerleme çubuğu
        progress_layout = QFormLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #2196F3;
                border-radius: 5px;
                text-align: center;
                height: 30px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        progress_layout.addRow("Genel İlerleme:", self.progress_bar)

        layout.addLayout(progress_layout)

        group.setLayout(layout)
        return group

    def _create_kalemler_tablosu(self) -> QGroupBox:
        """İş kalemleri tablosu"""
        group = QGroupBox("📋 İş Kalemleri ve QR Kodları")
        layout = QVBoxLayout()

        self.kalemler_table = QTableWidget()
        self.kalemler_table.setColumnCount(8)
        self.kalemler_table.setHorizontalHeaderLabels([
            "Poz No", "Tanım", "Planlanan", "Gerçekleşen",
            "İlerleme %", "Birim Fiyat", "Toplam", "İşlemler"
        ])

        header = self.kalemler_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.kalemler_table.setAlternatingRowColors(True)

        layout.addWidget(self.kalemler_table)

        # Alt butonlar
        btn_layout = QHBoxLayout()

        yenile_btn = QPushButton("🔄 Yenile")
        yenile_btn.clicked.connect(self.load_kalemler)
        btn_layout.addWidget(yenile_btn)

        export_btn = QPushButton("📤 Hakediş Raporu")
        export_btn.clicked.connect(self.export_hakedis)
        btn_layout.addWidget(export_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        group.setLayout(layout)
        return group

    def load_projeler(self):
        """Projeleri yükle"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, ad FROM projects WHERE durum = 'aktif' ORDER BY ad")
                rows = cursor.fetchall()

                self.proje_combo.clear()
                for row in rows:
                    self.proje_combo.addItem(row['ad'], row['id'])

                if rows:
                    self.current_proje_id = rows[0]['id']
                    self.load_dashboard()

        except Exception as e:
            logger.error(f"Proje yükleme hatası: {e}")

    def on_proje_changed(self, index: int):
        """Proje değiştiğinde"""
        if index >= 0:
            self.current_proje_id = self.proje_combo.itemData(index)
            self.load_dashboard()

    def load_dashboard(self):
        """Dashboard'u yükle"""
        if not self.current_proje_id:
            return

        self.load_durum_ozeti()
        self.load_kalemler()

    def load_durum_ozeti(self):
        """Durum özetini yükle"""
        try:
            durum = self.engine.get_hakedis_durumu(self.current_proje_id)

            if not durum:
                return

            html = f"""
            <div style="font-family: 'Segoe UI'; padding: 10px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background-color: #2a2a3a;">
                        <td style="padding: 8px; border: 1px solid #3a3a4a;"><b>Toplam Kalem:</b></td>
                        <td style="padding: 8px; border: 1px solid #3a3a4a; text-align: right;">{durum['toplam_kalem']}</td>
                    </tr>
                    <tr style="background-color: #1e1e2e;">
                        <td style="padding: 8px; border: 1px solid #3a3a4a;"><b>Toplam Tutar:</b></td>
                        <td style="padding: 8px; border: 1px solid #3a3a4a; text-align: right; color: #2196F3;">{durum['toplam_tutar']:,.2f} TL</td>
                    </tr>
                    <tr style="background-color: #2a2a3a;">
                        <td style="padding: 8px; border: 1px solid #3a3a4a;"><b>Gerçekleşen:</b></td>
                        <td style="padding: 8px; border: 1px solid #3a3a4a; text-align: right; color: #4CAF50;">{durum['gerceklesen_tutar']:,.2f} TL</td>
                    </tr>
                    <tr style="background-color: #1e1e2e;">
                        <td style="padding: 8px; border: 1px solid #3a3a4a;"><b>Kalan:</b></td>
                        <td style="padding: 8px; border: 1px solid #3a3a4a; text-align: right; color: #FF9800;">{durum['kalan_tutar']:,.2f} TL</td>
                    </tr>
                </table>
            </div>
            """
            self.ozet_text.setHtml(html)

            # İlerleme çubuğu
            self.progress_bar.setValue(int(durum['gerceklesme_orani']))
            self.progress_bar.setFormat(f"%{durum['gerceklesme_orani']:.2f}")

        except Exception as e:
            logger.error(f"Durum özeti yükleme hatası: {e}")

    def load_kalemler(self):
        """Kalemleri yükle"""
        if not self.current_proje_id:
            return

        try:
            kalemler = self.engine.get_qr_kalemler(self.current_proje_id)

            self.kalemler_table.setRowCount(len(kalemler))

            for row_idx, kalem in enumerate(kalemler):
                # Poz No
                self.kalemler_table.setItem(row_idx, 0, QTableWidgetItem(kalem['poz_no']))

                # Tanım
                tanim = kalem['tanim'][:40] + "..." if len(kalem['tanim']) > 40 else kalem['tanim']
                self.kalemler_table.setItem(row_idx, 1, QTableWidgetItem(tanim))

                # Planlanan
                self.kalemler_table.setItem(row_idx, 2,
                    QTableWidgetItem(f"{kalem['miktar']} {kalem['birim']}"))

                # Gerçekleşen
                self.kalemler_table.setItem(row_idx, 3,
                    QTableWidgetItem(f"{kalem['gerceklesen']} {kalem['birim']}"))

                # İlerleme %
                ilerleme_item = QTableWidgetItem(f"%{kalem['gerceklesme_orani']:.1f}")
                ilerleme_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                if kalem['gerceklesme_orani'] >= 100:
                    ilerleme_item.setBackground(QColor(76, 175, 80, 100))  # Yeşil
                elif kalem['gerceklesme_orani'] >= 50:
                    ilerleme_item.setBackground(QColor(255, 152, 0, 100))  # Turuncu
                else:
                    ilerleme_item.setBackground(QColor(244, 67, 54, 100))  # Kırmızı

                self.kalemler_table.setItem(row_idx, 4, ilerleme_item)

                # Birim Fiyat
                self.kalemler_table.setItem(row_idx, 5,
                    QTableWidgetItem(f"{kalem['birim_fiyat']:,.2f}"))

                # Toplam
                self.kalemler_table.setItem(row_idx, 6,
                    QTableWidgetItem(f"{kalem['toplam']:,.2f}"))

                # İşlemler (butonlar)
                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(4, 4, 4, 4)

                qr_btn = QPushButton("QR")
                qr_btn.setMaximumWidth(50)
                qr_btn.clicked.connect(lambda checked, k=kalem: self.show_qr_code(k))
                btn_layout.addWidget(qr_btn)

                giris_btn = QPushButton("Giriş")
                giris_btn.setMaximumWidth(60)
                giris_btn.clicked.connect(lambda checked, k=kalem: self.gerceklesme_girisi(k))
                btn_layout.addWidget(giris_btn)

                self.kalemler_table.setCellWidget(row_idx, 7, btn_widget)

        except Exception as e:
            logger.error(f"Kalemler yükleme hatası: {e}")

    def show_qr_code(self, kalem: dict):
        """QR kodu göster"""
        try:
            # QR kod oluştur
            qr_bytes = self.engine.create_qr_code(
                proje_id=self.current_proje_id,
                metraj_kalem_id=kalem['id']
            )

            # Dialog göster
            dialog = QRGosterDialog(qr_bytes, kalem, self)
            dialog.exec()

        except Exception as e:
            logger.error(f"QR kod gösterme hatası: {e}")
            QMessageBox.critical(self, "Hata", f"QR kod oluşturulamadı:\n{str(e)}")

    def gerceklesme_girisi(self, kalem: dict):
        """Gerçekleşme girişi yap"""
        try:
            # Dialog göster
            dialog = GerceklesmeDialog(kalem, self)

            if dialog.exec():
                data = dialog.get_data()

                # Veritabanına kaydet
                kayit_id = self.engine.create_hakedis_gercekeleme(
                    proje_id=self.current_proje_id,
                    metraj_kalem_id=kalem['id'],
                    gerceklesen_miktar=data['gerceklesen_miktar'],
                    aciklama=data['aciklama'],
                    foto_path=data['foto_path'],
                    konum=data['konum']
                )

                if kayit_id > 0:
                    QMessageBox.information(self, "Başarılı",
                        f"Gerçekleşme kaydı oluşturuldu!\n\n"
                        f"Miktar: {data['gerceklesen_miktar']} {kalem['birim']}")

                    # Tabloyu yenile
                    self.load_dashboard()
                else:
                    QMessageBox.warning(self, "Hata", "Kayıt oluşturulamadı!")

        except Exception as e:
            logger.error(f"Gerçekleşme girişi hatası: {e}")
            QMessageBox.critical(self, "Hata", f"Gerçekleşme kaydedilemedi:\n{str(e)}")

    def export_hakedis(self):
        """Hakediş raporu export et"""
        QMessageBox.information(self, "Bilgi",
            "Hakediş raporu export özelliği yakında eklenecek!\n\n"
            "PDF ve Excel formatında detaylı hakediş raporu oluşturulacak.")
