"""
AI Asistan Paneli
Claude AI destekli inşaat danışmanı arayüzü
"""
import logging
from typing import Optional, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QGroupBox, QFormLayout, QComboBox,
    QSplitter, QApplication, QDialog, QDialogButtonBox, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

logger = logging.getLogger(__name__)


class ApiAyarDialog(QDialog):
    """Claude API anahtarı ayarlama penceresi"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("Claude API Ayarları")
        self.setMinimumWidth(520)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a2e; color: #e0e0e0; }
            QLabel { color: #e0e0e0; }
            QLineEdit { background-color: #16213e; color: #e0e0e0;
                        border: 1px solid #0f3460; padding: 6px; border-radius: 4px; }
            QComboBox { background-color: #16213e; color: #e0e0e0;
                        border: 1px solid #0f3460; padding: 6px; border-radius: 4px; }
            QPushButton { background-color: #0f3460; color: white;
                          padding: 8px 16px; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #00BFFF; color: #0d0d0d; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        baslik = QLabel("🤖 Claude API Ayarları")
        baslik.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        baslik.setStyleSheet("color: #00BFFF;")
        layout.addWidget(baslik)

        bilgi = QLabel(
            "API anahtarınızı <b>console.anthropic.com</b> adresinden alabilirsiniz.\n"
            "Anahtar 'sk-ant-' ile başlamalıdır."
        )
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        layout.addWidget(bilgi)

        form = QFormLayout()
        form.setSpacing(10)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-ant-api03-...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        if engine.api_key:
            self.api_key_input.setText(engine.api_key)
        form.addRow("API Anahtarı:", self.api_key_input)

        self.model_combo = QComboBox()
        for model_id, model_ad in engine.DESTEKLENEN_MODELLER:
            self.model_combo.addItem(model_ad, model_id)
        for i, (mid, _) in enumerate(engine.DESTEKLENEN_MODELLER):
            if mid == engine.model:
                self.model_combo.setCurrentIndex(i)
                break
        form.addRow("Model:", self.model_combo)

        layout.addLayout(form)

        self.goster_btn = QPushButton("🔑 Anahtarı Göster")
        self.goster_btn.setCheckable(True)
        self.goster_btn.toggled.connect(self._toggle_gizli)
        layout.addWidget(self.goster_btn)

        btn_layout = QHBoxLayout()
        self.kaydet_btn = QPushButton("💾 Kaydet")
        self.kaydet_btn.setStyleSheet(
            "background-color: #00BFFF; color: #0d0d0d; font-weight: bold;"
        )
        self.kaydet_btn.clicked.connect(self._kaydet)
        self.iptal_btn = QPushButton("İptal")
        self.iptal_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.kaydet_btn)
        btn_layout.addWidget(self.iptal_btn)
        layout.addLayout(btn_layout)

    def _toggle_gizli(self, goster: bool):
        mode = QLineEdit.EchoMode.Normal if goster else QLineEdit.EchoMode.Password
        self.api_key_input.setEchoMode(mode)
        self.goster_btn.setText("🙈 Anahtarı Gizle" if goster else "🔑 Anahtarı Göster")

    def _kaydet(self):
        anahtar = self.api_key_input.text().strip()
        if not anahtar:
            QMessageBox.warning(self, "Uyarı", "API anahtarı boş olamaz.")
            return
        if not anahtar.startswith("sk-ant-"):
            QMessageBox.warning(
                self, "Uyarı",
                "Geçersiz API anahtarı formatı.\n'sk-ant-' ile başlamalıdır."
            )
            return
        model = self.model_combo.currentData()
        self.engine.kaydet_config(anahtar, model)
        self.accept()


class AsistanPanel(QWidget):
    """Claude AI destekli inşaat danışmanı paneli"""

    HIZLI_SORULAR = [
        "Günlük gecikme cezası hesabı nasıl yapılır?",
        "Kesin teminat ne zaman iade edilir?",
        "Hakedişten yapılan kesintiler nelerdir?",
        "Betonarme kalıp verimlilik değerleri nedir?",
        "Demirci (bağlama/bükme) verimlilik değeri nedir?",
        "SGK asgari işçilik oranı nasıl hesaplanır?",
        "Fiyat farkı hesabında TÜFE endeksi nasıl kullanılır?",
        "Serbest piyasa ile kamu ihalesi farkları nelerdir?",
        "Yaklaşık maliyet hesabında nelere dikkat edilmeli?",
        "İnşaat ataşmanı nedir, nasıl düzenlenir?",
    ]

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.proje_id: Optional[int] = None
        self._current_thread = None
        self._asistan_yanit_buffer = ""

        try:
            from app.core.claude_engine import ClaudeEngine
            self.engine = ClaudeEngine()
            self._engine_ok = True
        except Exception as e:
            logger.error(f"ClaudeEngine yüklenemedi: {e}")
            self._engine_ok = False
            self.engine = None

        self._ui_olustur()
        self._api_durumu_guncelle()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _ui_olustur(self):
        self.setStyleSheet("""
            QWidget { background-color: #1a1a2e; color: #e0e0e0; }
            QGroupBox { border: 1px solid #0f3460; border-radius: 6px;
                        margin-top: 10px; padding-top: 8px; color: #00BFFF;
                        font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QTextEdit { background-color: #0d1117; color: #e0e0e0;
                        border: 1px solid #0f3460; border-radius: 4px; }
            QLineEdit { background-color: #16213e; color: #e0e0e0;
                        border: 1px solid #0f3460; padding: 6px; border-radius: 4px; }
            QPushButton { background-color: #0f3460; color: white;
                          padding: 7px 14px; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #1a5276; }
            QPushButton:disabled { background-color: #2c2c2c; color: #666; }
        """)

        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(10, 10, 10, 10)
        ana_layout.setSpacing(8)

        # Başlık + API durum satırı
        ust = QHBoxLayout()
        baslik = QLabel("🤖 AI İnşaat Danışmanı")
        baslik.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        baslik.setStyleSheet("color: #00BFFF;")
        ust.addWidget(baslik)
        ust.addStretch()
        self.api_durum_label = QLabel("⚪ API bağlantısı yok")
        self.api_durum_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        ust.addWidget(self.api_durum_label)
        self.ayar_btn = QPushButton("⚙️ API Ayarları")
        self.ayar_btn.clicked.connect(self._api_ayarla)
        ust.addWidget(self.ayar_btn)
        ana_layout.addLayout(ust)

        # Ana splitter: sol=sohbet, sağ=hızlı sorular
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sol panel
        sol = QWidget()
        sol_layout = QVBoxLayout(sol)
        sol_layout.setContentsMargins(0, 0, 0, 0)
        sol_layout.setSpacing(6)

        self.sohbet_alani = QTextEdit()
        self.sohbet_alani.setReadOnly(True)
        self.sohbet_alani.setFont(QFont("Consolas", 10))
        self.sohbet_alani.setPlaceholderText(
            "İnşaat sorularınızı buraya yazın...\n\n"
            "Örnek sorular:\n"
            "  • 'Gecikme cezası nasıl hesaplanır?'\n"
            "  • 'Betonarme perde duvar kalıbı verimliği nedir?'\n"
            "  • 'Kesin teminatı geri almak için şartlar nelerdir?'"
        )
        sol_layout.addWidget(self.sohbet_alani, stretch=4)

        # Yazma grubu
        yaz_group = QGroupBox("Mesajınız")
        yaz_layout = QVBoxLayout(yaz_group)

        self.mesaj_input = QTextEdit()
        self.mesaj_input.setMaximumHeight(85)
        self.mesaj_input.setPlaceholderText("Sorunuzu yazın... (Ctrl+Enter ile gönder)")
        self.mesaj_input.setFont(QFont("Arial", 11))
        self.mesaj_input.keyPressEvent = self._input_key_press
        yaz_layout.addWidget(self.mesaj_input)

        btn_satiri = QHBoxLayout()

        self.gonder_btn = QPushButton("📤 Gönder (Ctrl+Enter)")
        self.gonder_btn.setStyleSheet(
            "background-color: #00BFFF; color: #0d0d0d; font-weight: bold;"
        )
        self.gonder_btn.clicked.connect(self._mesaj_gonder)
        btn_satiri.addWidget(self.gonder_btn)

        self.iptal_btn = QPushButton("⏹ Durdur")
        self.iptal_btn.setEnabled(False)
        self.iptal_btn.clicked.connect(self._istegi_durdur)
        btn_satiri.addWidget(self.iptal_btn)

        self.temizle_btn = QPushButton("🗑 Geçmişi Temizle")
        self.temizle_btn.clicked.connect(self._gecmisi_temizle)
        btn_satiri.addWidget(self.temizle_btn)

        self.kopyala_btn = QPushButton("📋 Kopyala")
        self.kopyala_btn.clicked.connect(self._sohbeti_kopyala)
        btn_satiri.addWidget(self.kopyala_btn)

        yaz_layout.addLayout(btn_satiri)
        sol_layout.addWidget(yaz_group)
        splitter.addWidget(sol)

        # Sağ panel
        sag = QWidget()
        sag_layout = QVBoxLayout(sag)
        sag_layout.setContentsMargins(0, 0, 0, 0)
        sag_layout.setSpacing(8)

        hizli_group = QGroupBox("⚡ Hızlı Sorular")
        hizli_layout = QVBoxLayout(hizli_group)
        for soru in self.HIZLI_SORULAR:
            btn = QPushButton(soru)
            btn.setStyleSheet("""
                QPushButton { background-color: #16213e; text-align: left;
                              padding: 5px 8px; font-size: 10px; border-radius: 3px; }
                QPushButton:hover { background-color: #1a5276; }
            """)
            btn.clicked.connect(lambda checked, s=soru: self._hizli_soru_sor(s))
            hizli_layout.addWidget(btn)
        hizli_layout.addStretch()
        sag_layout.addWidget(hizli_group)

        # Proje bağlamı
        baglam_group = QGroupBox("📂 Proje Bağlamı")
        baglam_layout = QVBoxLayout(baglam_group)
        self.baglam_label = QLabel("Aktif proje: Yok")
        self.baglam_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        self.baglam_label.setWordWrap(True)
        baglam_layout.addWidget(self.baglam_label)
        self.baglam_kullan_btn = QPushButton("✅ Proje Bağlamını Kullan")
        self.baglam_kullan_btn.setCheckable(True)
        self.baglam_kullan_btn.setChecked(True)
        baglam_layout.addWidget(self.baglam_kullan_btn)
        sag_layout.addWidget(baglam_group)
        sag_layout.addStretch()

        splitter.addWidget(sag)
        splitter.setSizes([720, 280])
        ana_layout.addWidget(splitter)

        self.durum_label = QLabel("Hazır. API anahtarınızı ayarlayın.")
        self.durum_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        ana_layout.addWidget(self.durum_label)

    # ── Yardımcılar ───────────────────────────────────────────────────────────

    def _input_key_press(self, event):
        from PyQt6.QtCore import Qt as QtCore
        if (event.key() == QtCore.Key.Key_Return and
                event.modifiers() == QtCore.KeyboardModifier.ControlModifier):
            self._mesaj_gonder()
        else:
            QTextEdit.keyPressEvent(self.mesaj_input, event)

    def _api_durumu_guncelle(self):
        if not self._engine_ok or not self.engine:
            self.api_durum_label.setText("❌ Engine yüklenemedi")
            self.gonder_btn.setEnabled(False)
            return
        if self.engine.api_key_gecerli():
            model_kisa = self.engine.model.split("-")[1].capitalize()
            self.api_durum_label.setText(f"✅ API bağlı — {model_kisa}")
            self.api_durum_label.setStyleSheet("color: #00ff88; font-size: 11px;")
            self.gonder_btn.setEnabled(True)
            self.durum_label.setText(
                "Hazır. Sorunuzu yazıp Ctrl+Enter ile gönderebilirsiniz."
            )
        else:
            self.api_durum_label.setText("⚪ API anahtarı girilmedi")
            self.api_durum_label.setStyleSheet("color: #ffaa00; font-size: 11px;")
            self.gonder_btn.setEnabled(False)
            self.durum_label.setText(
                "API anahtarı girilmemiş. ⚙️ API Ayarları butonuna tıklayın."
            )

    def _sohbete_ekle(self, rol: str, icerik: str):
        renk_map = {
            "kullanici": "#00BFFF",
            "asistan":   "#00ff88",
            "sistem":    "#ffaa00",
            "hata":      "#ff4444",
        }
        ad_map = {
            "kullanici": "Siz",
            "asistan":   "AI Asistan",
            "sistem":    "Sistem",
            "hata":      "Hata",
        }
        renk = renk_map.get(rol, "#e0e0e0")
        ad = ad_map.get(rol, rol)

        cursor = self.sohbet_alani.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt_baslik = QTextCharFormat()
        fmt_baslik.setForeground(QColor(renk))
        fmt_baslik.setFontWeight(QFont.Weight.Bold)
        cursor.insertText(f"\n{'─' * 50}\n▶ {ad}\n", fmt_baslik)

        fmt_icerik = QTextCharFormat()
        fmt_icerik.setForeground(QColor("#e0e0e0"))
        fmt_icerik.setFontWeight(QFont.Weight.Normal)
        cursor.insertText(icerik + "\n", fmt_icerik)

        self.sohbet_alani.setTextCursor(cursor)
        self.sohbet_alani.ensureCursorVisible()

    def _asistan_yazmaya_basla(self):
        cursor = self.sohbet_alani.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#00ff88"))
        fmt.setFontWeight(QFont.Weight.Bold)
        cursor.insertText(f"\n{'─' * 50}\n▶ AI Asistan\n", fmt)
        self.sohbet_alani.setTextCursor(cursor)
        self._asistan_yanit_buffer = ""

    def proje_guncelle(self, proje_id: Optional[int], proje_adi: str = ""):
        """Ana pencereden proje değiştiğinde çağrılır"""
        self.proje_id = proje_id
        if proje_id and proje_adi:
            self.baglam_label.setText(f"Aktif proje:\n{proje_adi}")
            self.baglam_label.setStyleSheet("color: #00ff88; font-size: 10px;")
        else:
            self.baglam_label.setText("Aktif proje: Yok")
            self.baglam_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")

    # ── Slotlar ───────────────────────────────────────────────────────────────

    def _api_ayarla(self):
        if not self._engine_ok:
            QMessageBox.critical(self, "Hata", "Engine yüklenemedi.")
            return
        dialog = ApiAyarDialog(self.engine, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._api_durumu_guncelle()
            self._sohbete_ekle(
                "sistem", "✅ API ayarları güncellendi. Artık soru sorabilirsiniz."
            )

    def _mesaj_gonder(self):
        if not self._engine_ok or not self.engine:
            return
        if not self.engine.api_key_gecerli():
            QMessageBox.warning(
                self, "API Anahtarı Yok",
                "Önce API anahtarınızı girin.\n⚙️ API Ayarları butonuna tıklayın."
            )
            return

        mesaj = self.mesaj_input.toPlainText().strip()
        if not mesaj:
            return

        gorsel_mesaj = mesaj
        self.mesaj_input.clear()

        # Proje bağlamı
        if self.baglam_kullan_btn.isChecked() and self.proje_id and self.db:
            try:
                proje = self.db.get_project(self.proje_id)
                if proje:
                    kalemler = self.db.get_metraj_kalemleri(self.proje_id)
                    proje_data = {
                        "ad": proje.get("ad", ""),
                        "toplam_maliyet": sum(
                            (k.get("miktar", 0) or 0) * (k.get("birim_fiyat", 0) or 0)
                            for k in (kalemler or [])
                        ),
                        "kalem_sayisi": len(kalemler or []),
                        "durum": proje.get("durum", ""),
                        "notlar": proje.get("notlar", ""),
                    }
                    baglam = self.engine.proje_baglam_olustur(proje_data)
                    mesaj = f"{baglam}\n\nSoru: {mesaj}"
            except Exception as e:
                logger.warning(f"Proje bağlamı alınamadı: {e}")

        self.engine.mesaj_ekle_kullanici(mesaj)
        self._sohbete_ekle("kullanici", gorsel_mesaj)

        thread = self.engine.sorgu_thread_olustur()
        if not thread:
            self._sohbete_ekle("hata", "Thread oluşturulamadı.")
            return

        self._current_thread = thread
        thread.yanit_parcasi.connect(self._yanit_parcasi_geldi)
        thread.hata_olustu.connect(self._hata_geldi)
        thread.islem_bitti.connect(self._islem_bitti)

        self._asistan_yazmaya_basla()
        self.gonder_btn.setEnabled(False)
        self.iptal_btn.setEnabled(True)
        self.durum_label.setText("⏳ Yanıt alınıyor...")
        thread.start()

    @pyqtSlot(str)
    def _yanit_parcasi_geldi(self, parca: str):
        cursor = self.sohbet_alani.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#e0e0e0"))
        cursor.insertText(parca, fmt)
        self.sohbet_alani.setTextCursor(cursor)
        self.sohbet_alani.ensureCursorVisible()
        self._asistan_yanit_buffer += parca

    @pyqtSlot(str)
    def _hata_geldi(self, hata: str):
        self._sohbete_ekle("hata", f"API Hatası: {hata}")
        self.durum_label.setText(f"❌ Hata: {hata[:100]}")

    @pyqtSlot()
    def _islem_bitti(self):
        if self._asistan_yanit_buffer:
            self.engine.mesaj_ekle_asistan(self._asistan_yanit_buffer)
            self._asistan_yanit_buffer = ""
        gecerli = self.engine.api_key_gecerli() if self.engine else False
        self.gonder_btn.setEnabled(gecerli)
        self.iptal_btn.setEnabled(False)
        self.durum_label.setText("✅ Yanıt alındı. Yeni soru yazabilirsiniz.")
        self._current_thread = None

    def _istegi_durdur(self):
        if self.engine:
            self.engine.aktif_istegi_iptal_et()
        self.iptal_btn.setEnabled(False)
        self.durum_label.setText("⏹ Durduruldu.")

    def _gecmisi_temizle(self):
        if self.engine:
            self.engine.gecmis_temizle()
        self.sohbet_alani.clear()
        self.durum_label.setText("Geçmiş temizlendi.")

    def _sohbeti_kopyala(self):
        metin = self.sohbet_alani.toPlainText()
        if metin:
            QApplication.clipboard().setText(metin)
            self.durum_label.setText("✅ Sohbet panoya kopyalandı.")

    def _hizli_soru_sor(self, soru: str):
        self.mesaj_input.setPlainText(soru)
        self._mesaj_gonder()
