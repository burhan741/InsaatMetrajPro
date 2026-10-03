"""
AI Asistan Paneli — Gelişmiş Sürüm
Claude AI destekli inşaat danışmanı arayüzü

Modlar:
  0 - Sohbet        : Genel sorular, streaming yanıt
  1 - Hesap Asist.  : Tool use (verimlilik, kaba yapı, metraj listesi)
  2 - Proje Analizi : Aktif projenin risk + maliyet analizi
  3 - Gantt Planlama: AI iş programı oluşturma ve Gantt'a aktarım
"""
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QGroupBox, QSplitter, QApplication, QDialog,
    QMessageBox, QTabWidget, QFileDialog,
    QScrollArea, QFrame, QListWidget, QListWidgetItem, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

logger = logging.getLogger(__name__)

# ── Hızlı Soru Kategorileri ───────────────────────────────────────────────

HIZLI_SORULAR: Dict[str, List[str]] = {
    "⏱️ Verimlilik": [
        "Verimlilik süresi: Kalıp Döşeme, 500 m², 4 usta",
        "Verimlilik süresi: Demir Bağlama, 20000 kg, 8 usta",
        "Verimlilik süresi: İç Sıva, 1200 m², 6 usta",
        "Verimlilik süresi: Fayans/Seramik, 300 m², 3 usta",
        "Verimlilik süresi: Dış Boya, 800 m², 5 usta",
        "Verimlilik süresi: Nervürlü Soğuk Demir, 15000 kg, 6 usta",
    ],
    "💰 Maliyet": [
        "Kaba yapı maliyeti: 1000 m², Betonarme Çerçeve",
        "Kaba yapı maliyeti: 750 m², Betonarme Perde+Çerçeve",
        "Kaba yapı maliyeti: 400 m², Yığma Tuğla",
        "Kaba yapı maliyeti: 600 m², Çelik Konstrüksiyon",
        "Bu projenin metraj kalemlerini listele ve analiz et",
        "2026 temel malzeme birim fiyatlarını listele",
    ],
    "📋 Mevzuat": [
        "SGK asgari işçilik oranı nasıl hesaplanır?",
        "İnşaat ataşmanı nedir, nasıl düzenlenir?",
        "Yaklaşık maliyet hesabında nelere dikkat edilmeli?",
        "Fiyat farkı hesabında TÜFE endeksi nasıl kullanılır?",
        "Serbest piyasa ile kamu ihalesi farkları nelerdir?",
        "İş artışı ve iş eksilişi nasıl uygulanır?",
    ],
    "🏗️ Teknik": [
        "C25/30 beton karışım oranları nelerdir?",
        "Kalıp sökme süreleri ne kadardır? (TS 500)",
        "Perde beton döküm hızı ne olmalı?",
        "Donatı bindirme boyu nasıl hesaplanır?",
        "Sıva yapılabilmesi için yüzey kaç gün beklemeli?",
        "Betonarme perdede max demir aralığı nedir?",
    ],
    "🔍 Saha Sorunları": [
        "Perde betonunda segregasyon (bal peteği) var — tamir talimatı ver",
        "Slump 185mm çıktı — kabul et ya da reddet, gerekçe ver",
        "C25 beton 28 günlük numune 19 MPa — karot alayım mı?",
        "Kalıp söküldü, demir pası ve örtü eksikliği var — tamir adımları",
        "Çatlak genişliği yaklaşık 0.4mm, dış cephede — hangi yöntem?",
        "Döşeme kalıbı 14 gün doldu, sökebilir miyim? (TS EN 13670)",
        "Beton yüzeyinde çimento sütyeni var — nasıl giderilir?",
        "Soğuk derz oluştu, yeni dökümden önce ne yapmalıyım?",
    ],
}

# Araç adları Türkçe haritası
ARAC_ADLARI = {
    "verimlilik_sure_hesapla":  "Verimlilik Süresi Hesabı (CŞB)",
    "kaba_yapi_maliyet":        "Kaba Yapı Maliyet Tahmini",
    "proje_metraj_listesi":     "Proje Metraj Listesi",
    "gantt_gorevleri_getir":    "Gantt İş Programı Görevleri",
    "hakedis_hesapla":          "Hakediş Hesabı (KİK 4734/4735)",
    "gecikme_ceza_hesapla":     "Gecikme Cezası Hesabı (md.20)",
    "saha_sorun_tani":          "Saha Sorun Teşhisi (Yönetmelik Analizi)",
    "malzeme_test_degerlendir": "Malzeme Test Değerlendirmesi (TS/EN)",
    "isg_risk_degerlendirme":   "İSG Risk Değerlendirmesi (6331)",
}


# ── API Ayar Penceresi ─────────────────────────────────────────────────────

class ApiAyarDialog(QDialog):
    """Claude API anahtarı ve model seçim penceresi."""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("Claude API Ayarları")
        self.setMinimumWidth(520)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a2e; color: #e0e0e0; }
            QLabel { color: #e0e0e0; }
            QLineEdit, QComboBox {
                background-color: #16213e; color: #e0e0e0;
                border: 1px solid #0f3460; padding: 6px; border-radius: 4px;
            }
            QPushButton {
                background-color: #0f3460; color: white;
                padding: 8px 16px; border-radius: 4px; border: none;
            }
            QPushButton:hover { background-color: #00BFFF; color: #0d0d0d; }
        """)

        from PyQt6.QtWidgets import QFormLayout, QLineEdit, QComboBox
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
        for i, (mid, _) in enumerate(engine.DESTEKLENED_MODELLER
                                     if hasattr(engine, 'DESTEKLENED_MODELLER')
                                     else engine.DESTEKLENEN_MODELLER):
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
        from PyQt6.QtWidgets import QLineEdit
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


# ── Ana Panel ──────────────────────────────────────────────────────────────

class AsistanPanel(QWidget):
    """
    Claude AI destekli inşaat danışmanı paneli.

    4 mod:
      0 - Sohbet        (streaming)
      1 - Hesap Asist.  (tool use)
      2 - Proje Analizi (tool use + yapılandırılmış prompt)
      3 - Gantt Planlama (tool use + Gantt entegrasyonu)
    """

    # Gantt window'un dinleyeceği sinyal
    gantt_guncellendi = pyqtSignal()
    # Ana pencereye Gantt sekmesini aç isteği
    gantt_ac_istegi = pyqtSignal()

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.proje_id: Optional[int] = None
        self._aktif_mod: int = 0          # 0=Sohbet, 1=Hesap, 2=Analiz, 3=Gantt
        self._current_thread = None
        self._asistan_yanit_buffer = ""
        self._son_yanit = ""              # Tool use nihai yanıt (Gantt parse için)
        self._parsed_gantt_tasks: List[Dict] = []
        self._gantt_engine = None
        self._gantt_window = None       # GanttWindow referansı
        self._ekli_dosya_yolu: Optional[str] = None

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
        if self._engine_ok and self.engine:
            self._gecmis_paneli_yenile()

    # ── UI Oluşturma ────────────────────────────────────────────────────────

    def _ui_olustur(self):
        self.setStyleSheet("""
            QWidget { background-color: #1a1a2e; color: #e0e0e0; }
            QGroupBox {
                border: 1px solid #0f3460; border-radius: 6px;
                margin-top: 10px; padding-top: 8px;
                color: #00BFFF; font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 4px;
            }
            QTextEdit {
                background-color: #0d1117; color: #e0e0e0;
                border: 1px solid #0f3460; border-radius: 4px;
            }
            QLineEdit {
                background-color: #16213e; color: #e0e0e0;
                border: 1px solid #0f3460; padding: 6px; border-radius: 4px;
            }
            QPushButton {
                background-color: #0f3460; color: white;
                padding: 7px 14px; border-radius: 4px; border: none;
            }
            QPushButton:hover { background-color: #1a5276; }
            QPushButton:disabled { background-color: #2c2c2c; color: #666; }
            QPushButton:checked { background-color: #00BFFF; color: #0d0d0d; }
            QTabWidget::pane {
                border: 1px solid #0f3460; background-color: #16213e;
            }
            QTabBar::tab {
                background-color: #0f3460; color: #e0e0e0;
                padding: 5px 10px; border-radius: 3px; margin-right: 2px;
            }
            QTabBar::tab:selected { background-color: #00BFFF; color: #0d0d0d; }
        """)

        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(10, 10, 10, 10)
        ana_layout.setSpacing(6)

        # ── Üst satır: Başlık + API durumu + Ayar ──
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

        # ── Mod Seçici Buton Çubuğu ──────────────────────────────────────────
        mod_satiri = QHBoxLayout()
        mod_satiri.setSpacing(2)
        self._mod_butonlari = []
        _MODLAR = [
            (0, "💬 Sohbet"),
            (1, "🔢 Hesap"),
            (2, "📊 Analiz"),
            (3, "📅 Gantt"),
            (4, "💰 Hakediş"),
            (6, "🔍 Saha"),
        ]
        _AKTIF_MOD_STYLE = (
            "QPushButton { background-color: #1a6b2a; color: white; "
            "font-size: 10px; padding: 4px 8px; border-radius: 3px; font-weight: bold; }"
        )
        _PASIF_MOD_STYLE = (
            "QPushButton { background-color: #16213e; color: #aaaaaa; "
            "font-size: 10px; padding: 4px 8px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #1a3a5c; color: white; }"
        )
        for _idx, _etiket in _MODLAR:
            _btn = QPushButton(_etiket)
            _btn.setStyleSheet(_AKTIF_MOD_STYLE if _idx == 0 else _PASIF_MOD_STYLE)
            _btn.clicked.connect(lambda checked=False, i=_idx: self._mod_sec(i))
            mod_satiri.addWidget(_btn)
            self._mod_butonlari.append(_btn)
        ana_layout.addLayout(mod_satiri)

        # ── Ana Splitter: Sol=Sohbet, Sağ=Araçlar ──
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Sol Panel ──
        sol = QWidget()
        sol_layout = QVBoxLayout(sol)
        sol_layout.setContentsMargins(0, 0, 4, 0)
        sol_layout.setSpacing(6)

        # Sohbet alanı
        self.sohbet_alani = QTextEdit()
        self.sohbet_alani.setReadOnly(True)
        self.sohbet_alani.setFont(QFont("Consolas", 10))
        self.sohbet_alani.setPlaceholderText(
            "Asistana isteğinizi yazın...\n\n"
            "Örnekler:\n"
            "  • '4 katlı 800 m² konut — tüm kaba yapı metrajını çıkar'\n"
            "  • '500 m² kalıp döşeme, 4 usta, kaç gün sürer?'\n"
            "  • 'Sözleşme bedeli 5.000.000 TL, %35 tamamlandı, hakediş hesapla'\n"
            "  • 'Perde betonunda bal peteği var — tamir talimatı ver'\n"
            "  • 'Ankara yapım işi ihale ara'\n"
            "  • 'Kadıköy 3+1 120 m² daire değerle'"
        )
        sol_layout.addWidget(self.sohbet_alani, stretch=4)

        # Mod-özel butonlar
        self.analiz_basla_btn = QPushButton("📊 Proje Analizini Başlat")
        self.analiz_basla_btn.setStyleSheet(
            "background-color: #8e44ad; color: white; font-weight: bold; padding: 8px;"
        )
        self.analiz_basla_btn.clicked.connect(self._proje_analizi_baslat)
        self.analiz_basla_btn.setVisible(False)
        sol_layout.addWidget(self.analiz_basla_btn)

        self.gantt_plan_basla_btn = QPushButton("📅 Gantt Planı Oluştur")
        self.gantt_plan_basla_btn.setStyleSheet(
            "background-color: #1a6b2a; color: white; font-weight: bold; padding: 8px;"
        )
        self.gantt_plan_basla_btn.clicked.connect(self._gantt_plani_baslat)
        self.gantt_plan_basla_btn.setVisible(False)
        sol_layout.addWidget(self.gantt_plan_basla_btn)

        self.hakedis_basla_btn = QPushButton("💰 Hakediş / Ceza Hesabı Başlat")
        self.hakedis_basla_btn.setStyleSheet(
            "background-color: #b7770d; color: white; font-weight: bold; padding: 8px;"
        )
        self.hakedis_basla_btn.clicked.connect(self._hakedis_baslat)
        self.hakedis_basla_btn.setVisible(False)
        sol_layout.addWidget(self.hakedis_basla_btn)

        self.saha_cozum_basla_btn = QPushButton("🔍 Saha Sorun Analizi Başlat")
        self.saha_cozum_basla_btn.setStyleSheet(
            "background-color: #5d2e8c; color: white; font-weight: bold; padding: 8px;"
        )
        self.saha_cozum_basla_btn.clicked.connect(self._saha_cozum_baslat)
        self.saha_cozum_basla_btn.setVisible(False)
        sol_layout.addWidget(self.saha_cozum_basla_btn)

        self.fotograf_analiz_btn = QPushButton(
            "📷 Fotoğraf ile Analiz Et  (PNG / JPG)"
        )
        self.fotograf_analiz_btn.setStyleSheet(
            "background-color: #1a3a5c; color: #00BFFF; "
            "font-weight: bold; padding: 8px; border: 1px solid #00BFFF; "
            "border-radius: 4px;"
        )
        self.fotograf_analiz_btn.setToolTip(
            "Çatlak, beton hatası, demir sorunu, İSG ihlali gibi\n"
            "fotoğrafları yükleyin — yönetmelik bazlı analiz yapılır."
        )
        self.fotograf_analiz_btn.clicked.connect(self._fotograf_analiz_sec)
        self.fotograf_analiz_btn.setVisible(False)
        sol_layout.addWidget(self.fotograf_analiz_btn)

        self.gantt_aktar_btn = QPushButton("🗂 Gantt'a Aktar (Görevler Hazır)")
        self.gantt_aktar_btn.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold; padding: 8px;"
        )
        self.gantt_aktar_btn.clicked.connect(self._gantt_aktar)
        self.gantt_aktar_btn.setVisible(False)
        sol_layout.addWidget(self.gantt_aktar_btn)

        # Mesaj yazma grubu
        yaz_group = QGroupBox("Mesajınız")
        yaz_layout = QVBoxLayout(yaz_group)
        yaz_layout.setSpacing(6)

        self.mesaj_input = QTextEdit()
        self.mesaj_input.setObjectName("mesaj_input")
        self.mesaj_input.setMaximumHeight(80)
        self.mesaj_input.setPlaceholderText("Sorunuzu yazın... (Ctrl+Enter ile gönder)")
        self.mesaj_input.setFont(QFont("Arial", 11))
        self.mesaj_input.keyPressEvent = self._input_key_press
        yaz_layout.addWidget(self.mesaj_input)

        # Dosya ekleme satırı
        dosya_satiri = QHBoxLayout()
        dosya_satiri.setSpacing(4)

        self.dosya_ekle_btn = QPushButton("📎 Dosya Ekle")
        self.dosya_ekle_btn.setToolTip("Excel (.xlsx), Görsel (PNG/JPG), PDF veya DXF ekle")
        self.dosya_ekle_btn.setStyleSheet(
            "QPushButton { background-color: #16213e; color: #aaaaaa; "
            "padding: 3px 8px; font-size: 10px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #1a5276; color: white; }"
        )
        self.dosya_ekle_btn.clicked.connect(self._dosya_sec)
        dosya_satiri.addWidget(self.dosya_ekle_btn)

        self.dosya_adi_label = QLabel("")
        self.dosya_adi_label.setStyleSheet(
            "color: #00BFFF; font-size: 10px; padding: 2px 4px;"
        )
        self.dosya_adi_label.setVisible(False)
        dosya_satiri.addWidget(self.dosya_adi_label)

        self.dosya_kaldir_btn = QPushButton("✕")
        self.dosya_kaldir_btn.setFixedWidth(24)
        self.dosya_kaldir_btn.setStyleSheet(
            "QPushButton { background-color: #8b0000; color: white; "
            "font-weight: bold; font-size: 10px; border-radius: 3px; padding: 2px; }"
            "QPushButton:hover { background-color: #c0392b; }"
        )
        self.dosya_kaldir_btn.setVisible(False)
        self.dosya_kaldir_btn.clicked.connect(self._dosya_kaldir)
        dosya_satiri.addWidget(self.dosya_kaldir_btn)
        dosya_satiri.addStretch()

        yaz_layout.addLayout(dosya_satiri)

        btn_satiri = QHBoxLayout()
        btn_satiri.setSpacing(4)

        self.gonder_btn = QPushButton("📤 Gönder")
        self.gonder_btn.setStyleSheet(
            "background-color: #00BFFF; color: #0d0d0d; font-weight: bold;"
        )
        self.gonder_btn.clicked.connect(self._mesaj_gonder)
        btn_satiri.addWidget(self.gonder_btn)

        self.iptal_btn = QPushButton("⏹ Durdur")
        self.iptal_btn.setEnabled(False)
        self.iptal_btn.clicked.connect(self._istegi_durdur)
        btn_satiri.addWidget(self.iptal_btn)

        self.temizle_btn = QPushButton("🗑 Temizle")
        self.temizle_btn.clicked.connect(self._gecmisi_temizle)
        btn_satiri.addWidget(self.temizle_btn)

        self.kopyala_btn = QPushButton("📋 Kopyala")
        self.kopyala_btn.clicked.connect(self._sohbeti_kopyala)
        btn_satiri.addWidget(self.kopyala_btn)

        self.kaydet_btn = QPushButton("💾 TXT Kaydet")
        self.kaydet_btn.clicked.connect(self._sohbeti_txt_kaydet)
        btn_satiri.addWidget(self.kaydet_btn)

        yaz_layout.addLayout(btn_satiri)
        sol_layout.addWidget(yaz_group)
        splitter.addWidget(sol)

        # ── Sağ Panel ──
        sag = QWidget()
        sag_layout = QVBoxLayout(sag)
        sag_layout.setContentsMargins(4, 0, 0, 0)
        sag_layout.setSpacing(8)

        # ── Geçmiş Sohbetler ──
        gecmis_group = QGroupBox("📜 Geçmiş Sohbetler")
        gecmis_group.setStyleSheet("""
            QListWidget {
                background-color: #0d1117; color: #e0e0e0;
                border: 1px solid #0f3460; border-radius: 3px;
                font-size: 10px;
            }
            QListWidget::item:selected { background-color: #0f3460; }
            QListWidget::item:hover { background-color: #16213e; }
        """)
        gecmis_ic = QVBoxLayout(gecmis_group)
        gecmis_ic.setContentsMargins(4, 8, 4, 4)
        gecmis_ic.setSpacing(4)

        self.gecmis_listesi_widget = QListWidget()
        self.gecmis_listesi_widget.setMaximumHeight(180)
        self.gecmis_listesi_widget.setToolTip("Kayıtlı konuşmalarınız")
        gecmis_ic.addWidget(self.gecmis_listesi_widget)

        gecmis_btn_satiri = QHBoxLayout()
        gecmis_btn_satiri.setSpacing(4)

        self.gecmis_yukle_btn = QPushButton("📂 Yükle")
        self.gecmis_yukle_btn.setToolTip("Seçili konuşmayı yükle")
        self.gecmis_yukle_btn.setStyleSheet(
            "QPushButton { background-color: #16213e; color: #e0e0e0; "
            "padding: 4px 8px; font-size: 10px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #1a5276; }"
        )
        self.gecmis_yukle_btn.clicked.connect(self._gecmis_yukle)
        gecmis_btn_satiri.addWidget(self.gecmis_yukle_btn)

        self.gecmis_sil_btn = QPushButton("🗑 Sil")
        self.gecmis_sil_btn.setToolTip("Seçili konuşmayı sil")
        self.gecmis_sil_btn.setStyleSheet(
            "QPushButton { background-color: #2c1010; color: #e0e0e0; "
            "padding: 4px 8px; font-size: 10px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #8b0000; }"
        )
        self.gecmis_sil_btn.clicked.connect(self._gecmis_sil)
        gecmis_btn_satiri.addWidget(self.gecmis_sil_btn)
        gecmis_ic.addLayout(gecmis_btn_satiri)

        self.yeni_sohbet_btn = QPushButton("➕ Yeni Sohbet")
        self.yeni_sohbet_btn.setStyleSheet(
            "QPushButton { background-color: #0f3460; color: #00BFFF; "
            "padding: 5px; font-size: 10px; border-radius: 3px; font-weight: bold; }"
            "QPushButton:hover { background-color: #1a5276; }"
        )
        self.yeni_sohbet_btn.clicked.connect(self._yeni_sohbet_baslat)
        gecmis_ic.addWidget(self.yeni_sohbet_btn)

        sag_layout.addWidget(gecmis_group)

        # Hızlı Sorular paneli kaldırıldı — kullanıcı isteği doğrudan yazar

        # Proje bağlamı
        baglam_group = QGroupBox("📂 Proje Bağlamı")
        baglam_ic = QVBoxLayout(baglam_group)
        baglam_ic.setSpacing(6)

        self.baglam_label = QLabel("Aktif proje: Yok")
        self.baglam_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        self.baglam_label.setWordWrap(True)
        baglam_ic.addWidget(self.baglam_label)

        self.baglam_kullan_btn = QPushButton("✅ Proje Bağlamını Kullan")
        self.baglam_kullan_btn.setCheckable(True)
        self.baglam_kullan_btn.setChecked(True)
        baglam_ic.addWidget(self.baglam_kullan_btn)

        self.metraj_dahil_btn = QPushButton("📋 Metraj Kalemlerini Dahil Et")
        self.metraj_dahil_btn.setCheckable(True)
        self.metraj_dahil_btn.setChecked(True)
        baglam_ic.addWidget(self.metraj_dahil_btn)

        self.gantt_durum_label = QLabel("Gantt: Bağlı değil")
        self.gantt_durum_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        baglam_ic.addWidget(self.gantt_durum_label)

        sag_layout.addWidget(baglam_group)
        sag_layout.addStretch()

        splitter.addWidget(sag)
        splitter.setSizes([700, 300])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        ana_layout.addWidget(splitter, stretch=1)

        # Durum etiketi
        self.durum_label = QLabel("Hazır. API anahtarınızı ayarlayın.")
        self.durum_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        ana_layout.addWidget(self.durum_label, stretch=0)

    # ── Mod Yönetimi ────────────────────────────────────────────────────────

    def _mod_sec(self, mod_index: int):
        """Buton çubuğundan mod seçimi — aktif butonu vurgula, modu güncelle."""
        _AKTIF = (
            "QPushButton { background-color: #1a6b2a; color: white; "
            "font-size: 10px; padding: 4px 8px; border-radius: 3px; font-weight: bold; }"
        )
        _PASIF = (
            "QPushButton { background-color: #16213e; color: #aaaaaa; "
            "font-size: 10px; padding: 4px 8px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #1a3a5c; color: white; }"
        )
        for i, btn in enumerate(self._mod_butonlari):
            btn.setStyleSheet(_AKTIF if i == mod_index else _PASIF)
        self._mod_degisti(mod_index)

    def _mod_degisti(self, mod_index: int):
        self._aktif_mod = mod_index

        # Mod-özel butonlar
        self.analiz_basla_btn.setVisible(mod_index == 2)
        self.gantt_plan_basla_btn.setVisible(mod_index == 3)
        self.gantt_aktar_btn.setVisible(
            mod_index == 3 and bool(self._parsed_gantt_tasks)
        )
        self.hakedis_basla_btn.setVisible(mod_index == 4)
        self.saha_cozum_basla_btn.setVisible(mod_index == 6)
        self.fotograf_analiz_btn.setVisible(mod_index == 6)

        # Placeholder metni moda göre güncelle
        if mod_index == 6:
            self.mesaj_input.setPlaceholderText(
                "Saha sorununu yazın veya 📷 ile fotoğraf yükleyin...\n\n"
                "Örnekler:\n"
                "  • 'Perde betonunda segregasyon var' → tamir malzeme + adım adım\n"
                "  • 'Slump 190mm çıktı' → kabul/red kararı\n"
                "  • 'C25 numune 19 MPa' → karot gerekli mi?\n"
                "  • Fotoğraf yükle → sorun tespit + tamir talimatı"
            )
        else:
            self.mesaj_input.setPlaceholderText(
                "Sorunuzu yazın... (Ctrl+Enter ile gönder)"
            )

        mesajlar = {
            0: "Sohbet modu — Genel inşaat sorularınızı yanıtlarım.",
            1: "Hesap Asistanı — Verimlilik ve maliyet hesabı için araçlar aktif.",
            2: "Proje Analizi — 'Analizi Başlat' veya doğrudan soru sorun.",
            3: "Gantt Planlama — 'Planı Oluştur' ile AI iş programı hazırlayın.",
            4: "Hakediş Asistanı — Hakediş ve gecikme cezası hesabı yapın.",
            6: (
                "Saha Çözüm Danışmanı — Beton hatası, çatlak, test sonucu, tamir talimatı. "
                "Fotoğraf yükle → malzeme + adım adım uygulama talimatı."
            ),
        }
        self.durum_label.setText(mesajlar.get(mod_index, ""))

    # ── Mesaj Gönderme ──────────────────────────────────────────────────────

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

        # Ekli dosya varsa görsel mesaja dosya adını ekle
        if self._ekli_dosya_yolu:
            gorsel_mesaj = f"{mesaj}\n[Ek: 📎 {os.path.basename(self._ekli_dosya_yolu)}]"
        else:
            gorsel_mesaj = mesaj
        self.mesaj_input.clear()

        # Proje bağlamını mesaja ekle
        if self.baglam_kullan_btn.isChecked() and self.proje_id and self.db:
            try:
                proje = self.db.get_project(self.proje_id)
                kalemler = (
                    self.db.get_project_metraj(self.proje_id)
                    if self.metraj_dahil_btn.isChecked()
                    else []
                )
                # Kategori dağılımı
                kat_dagilim: Dict[str, float] = {}
                for k in (kalemler or []):
                    kat = k.get("kategori", "Diğer") or "Diğer"
                    tutar = float(k.get("miktar") or 0) * float(k.get("birim_fiyat") or 0)
                    kat_dagilim[kat] = kat_dagilim.get(kat, 0.0) + tutar

                proje_data: Dict[str, Any] = {
                    "ad": proje.get("ad", "") if proje else "",
                    "toplam_maliyet": sum(
                        float(k.get("miktar") or 0) * float(k.get("birim_fiyat") or 0)
                        for k in (kalemler or [])
                    ),
                    "kalem_sayisi": len(kalemler or []),
                    "durum": proje.get("durum", "") if proje else "",
                    "notlar": proje.get("notlar", "") if proje else "",
                    "kategori_dagilimi": kat_dagilim,
                    "kalemler": kalemler or [],
                }
                baglam = self.engine.proje_baglam_olustur(proje_data)
                mesaj = f"{baglam}\n\nSoru: {mesaj}"
            except Exception as e:
                logger.warning(f"Proje bağlamı alınamadı: {e}")

        if self._ekli_dosya_yolu:
            ekli_dosya = self._ekli_dosya_yolu
            self._dosya_kaldir()  # UI'ı hemen temizle
            try:
                self.engine.mesaj_ekle_dosyali(mesaj, ekli_dosya)
            except Exception as e:
                self._sohbete_ekle("hata", f"Dosya işleme hatası: {e}")
                return
        else:
            self.engine.mesaj_ekle_kullanici(mesaj)
        self._sohbete_ekle("kullanici", gorsel_mesaj)

        self._aracli_basla()

    # ── Yeni Mod Başlatıcıları ──────────────────────────────────────────────

    def _hakedis_baslat(self):
        """Hakediş Asistanı modu — yönlendirme promptu gönder."""
        if not self._engine_ok or not self.engine:
            return
        if not self.engine.api_key_gecerli():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "API Anahtarı Yok",
                "Önce API anahtarınızı girin.\n⚙️ API Ayarları butonuna tıklayın."
            )
            return
        prompt = (
            "Hakediş Asistanı moduna geçildi.\n\n"
            "Aşağıdaki hesaplamalar için hazırım:\n"
            "1. **Hakediş Hesabı** — Sözleşme bedeli ve tamamlanma yüzdesi girin.\n"
            "   Örnek: 'Sözleşme bedeli 5.000.000 TL, %35 tamamlandı, hakediş hesapla'\n\n"
            "2. **Gecikme Cezası** — 4735 md.20 günlük ‰5 oranı.\n"
            "   Örnek: 'Sözleşme bedeli 3.000.000 TL, 45 gün gecikme cezası hesapla'\n\n"
            "Bilgilerinizi yazın, hakedis_hesapla ve gecikme_ceza_hesapla "
            "araçlarını kullanarak kesin sonuç üreteyim."
        )
        self.engine.mesaj_ekle_kullanici(prompt)
        self._sohbete_ekle("sistem", "Hakediş Asistanı başlatıldı.")
        self._aracli_basla()

    def _fotograf_analiz_sec(self):
        """Saha Çözüm modu — fotoğraf seç ve yapılandırılmış analiz gönder."""
        if not self._engine_ok or not self.engine:
            return
        if not self.engine.api_key_gecerli():
            QMessageBox.warning(
                self, "API Anahtarı Yok",
                "Önce API anahtarınızı girin.\n⚙️ API Ayarları butonuna tıklayın."
            )
            return

        from PyQt6.QtWidgets import QFileDialog, QInputDialog
        dosya, _ = QFileDialog.getOpenFileName(
            self,
            "Saha Fotoğrafı Seç",
            "",
            "Görseller (*.png *.jpg *.jpeg *.webp);;Tüm Dosyalar (*)",
        )
        if not dosya:
            return

        # Boyut kontrolü (5MB limit)
        import os as _os
        if _os.path.getsize(dosya) > 5 * 1024 * 1024:
            QMessageBox.warning(
                self, "Dosya Çok Büyük",
                "Görsel 5MB'dan küçük olmalıdır.\n"
                "Lütfen görseli sıkıştırın ve tekrar deneyin."
            )
            return

        # Kullanıcıdan ek açıklama al (opsiyonel)
        aciklama, tamam = QInputDialog.getText(
            self,
            "Fotoğraf Açıklaması",
            "Fotoğraf hakkında kısa açıklama yazın (opsiyonel):\n"
            "Örn: 'Zemin katta perde betonu', 'Kolon-kiriş birleşimi çatlak'",
        )
        if not tamam:
            aciklama = ""

        try:
            gorsel_mesaj = self.engine.mesaj_ekle_saha_gorseli(dosya, aciklama)
            self._sohbete_ekle("kullanici", gorsel_mesaj)
            self._saha_cozum_aracli_basla()
        except Exception as e:
            self._sohbete_ekle("hata", f"Görsel yüklenemedi: {e}")

    def _saha_cozum_baslat(self):
        """Saha Çözüm modu — yönlendirme promptu gönder."""
        if not self._engine_ok or not self.engine:
            return
        if not self.engine.api_key_gecerli():
            QMessageBox.warning(
                self, "API Anahtarı Yok",
                "Önce API anahtarınızı girin.\n⚙️ API Ayarları butonuna tıklayın."
            )
            return
        prompt = (
            "Saha Çözüm Danışmanı moduna geçildi.\n\n"
            "Şantiyede karşılaştığınız teknik sorunları, test sonuçlarını veya "
            "İSG durumlarını yazın.\n\n"
            "Örnekler:\n"
            "  • 'Perde betonunda segregasyon oluştu, ne yapmalıyım?'\n"
            "  • 'C25 beton numunesi 28 günde 19 MPa çıktı, karar?'\n"
            "  • '2.5m derinlik hafriyat, iksa yok, risk değerlendirmesi'\n"
            "  • 'Demir filizi paslandı, örtü 15mm, betonarme kiriş'\n"
            "  • 'Çatıda 8m yükseklikte çelik montaj — İSG gereklilikleri'\n\n"
            "Her sorun için: Teşhis → Kök Neden → Yönetmelik (TBDY/TS/İSG) "
            "→ Çözüm Adımları → Maliyet Etkisi → Risk Seviyesi formatında yanıt alırsınız."
        )
        self.engine.mesaj_ekle_kullanici(prompt)
        self._sohbete_ekle("sistem", "Saha Çözüm Danışmanı başlatıldı.")
        self._saha_cozum_aracli_basla()

    def _saha_cozum_aracli_basla(self):
        """Saha Çözüm modu — uzmanlaşmış sistem promptuyla tool use thread başlat."""
        self.engine.set_proje_baglam(self.db, self.proje_id)
        try:
            thread = self.engine.sorgu_saha_cozum_thread_olustur()
        except AttributeError:
            # Geriye dönük uyumluluk: eski engine'de metot yoksa standart araçlı thread
            thread = self.engine.sorgu_aracli_thread_olustur()
        if not thread:
            self._sohbete_ekle("hata", "Saha Çözüm thread'i oluşturulamadı.")
            return

        self._current_thread = thread
        thread.yanit_tamamlandi.connect(self._aracli_yanit_geldi)
        thread.arac_cagrildi.connect(self._arac_sonucu_goster)
        thread.hata_olustu.connect(self._hata_geldi)
        thread.islem_bitti.connect(self._islem_bitti_aracli)

        self._ui_mesgul_yap(True)
        self.durum_label.setText(
            "⏳ Saha analizi yapılıyor — yönetmelikler kontrol ediliyor..."
        )
        thread.start()

    def _streaming_basla(self):
        """Sohbet modu — streaming thread başlat."""
        thread = self.engine.sorgu_thread_olustur()
        if not thread:
            self._sohbete_ekle("hata", "Thread oluşturulamadı.")
            return

        self._current_thread = thread
        thread.yanit_parcasi.connect(self._yanit_parcasi_geldi)
        thread.hata_olustu.connect(self._hata_geldi)
        thread.islem_bitti.connect(self._islem_bitti_streaming)

        self._asistan_yazmaya_basla()
        self._ui_mesgul_yap(True)
        self.durum_label.setText("⏳ Yanıt alınıyor...")
        thread.start()

    def _aracli_basla(self):
        """Hesap / Analiz / Gantt modu — tool use thread başlat."""
        self.engine.set_proje_baglam(self.db, self.proje_id)
        if self._gantt_engine:
            self.engine.set_gantt_engine(self._gantt_engine)
        if self._gantt_window:
            self.engine.set_gantt_window(self._gantt_window)

        thread = self.engine.sorgu_aracli_thread_olustur()
        if not thread:
            self._sohbete_ekle("hata", "Araçlı thread oluşturulamadı.")
            return

        self._current_thread = thread
        thread.yanit_tamamlandi.connect(self._aracli_yanit_geldi)
        thread.arac_cagrildi.connect(self._arac_sonucu_goster)
        thread.hata_olustu.connect(self._hata_geldi)
        thread.islem_bitti.connect(self._islem_bitti_aracli)

        self._ui_mesgul_yap(True)
        self.durum_label.setText("⏳ Araçlar çalışıyor, yanıt hazırlanıyor...")
        thread.start()

    # ── Özel Mod Başlatıcıları ──────────────────────────────────────────────

    def _proje_analizi_baslat(self):
        """Proje Analizi modu — yapılandırılmış prompt gönder."""
        if not self._engine_ok or not self.engine:
            return
        if not self.proje_id or not self.db:
            QMessageBox.warning(
                self, "Proje Yok",
                "Analiz için aktif bir proje seçilmelidir."
            )
            return

        try:
            from app.core.claude_engine import PROJE_ANALIZ_PROMPT
            proje = self.db.get_project(self.proje_id)
            kalemler = self.db.get_project_metraj(self.proje_id) or []
            kat_dagilim: Dict[str, float] = {}
            for k in kalemler:
                kat = k.get("kategori", "Diğer") or "Diğer"
                tutar = float(k.get("miktar") or 0) * float(k.get("birim_fiyat") or 0)
                kat_dagilim[kat] = kat_dagilim.get(kat, 0.0) + tutar

            proje_data = {
                "ad": proje.get("ad", "") if proje else "",
                "toplam_maliyet": sum(
                    float(k.get("miktar") or 0) * float(k.get("birim_fiyat") or 0)
                    for k in kalemler
                ),
                "kalem_sayisi": len(kalemler),
                "durum": proje.get("durum", "") if proje else "",
                "notlar": proje.get("notlar", "") if proje else "",
                "kategori_dagilimi": kat_dagilim,
                "kalemler": kalemler,
            }
            baglam = self.engine.proje_baglam_olustur(proje_data)
            prompt = PROJE_ANALIZ_PROMPT.format(proje_baglam=baglam)
        except Exception as e:
            self._sohbete_ekle("hata", f"Proje verisi alınamadı: {e}")
            return

        self.engine.mesaj_ekle_kullanici(prompt)
        self._sohbete_ekle("sistem", "Proje analizi başlatılıyor...")
        self._aracli_basla()

    def _gantt_plani_baslat(self):
        """Gantt Planlama modu — iş programı oluşturma promptu gönder."""
        if not self._engine_ok or not self.engine:
            return

        # Gantt bağlantısı yoksa sekmeyi aç ve bekle
        if not self._gantt_engine:
            self._sohbete_ekle(
                "sistem",
                "⚙️ Gantt sekmesi açılıyor, lütfen bekleyin...\n"
                "Sekme yüklendikten sonra tekrar 'Gantt Planla' butonuna tıklayın.",
            )
            self.gantt_ac_istegi.emit()
            return

        try:
            from app.core.claude_engine import GANTT_PLAN_PROMPT
        except Exception as e:
            self._sohbete_ekle("hata", f"Gantt promptu yüklenemedi: {e}")
            return

        # Proje bağlamı hazırla
        baglam = "Proje bilgisi mevcut değil."
        if self.proje_id and self.db:
            try:
                proje = self.db.get_project(self.proje_id)
                kalemler = self.db.get_project_metraj(self.proje_id) or []
                proje_data = {
                    "ad": proje.get("ad", "") if proje else "",
                    "toplam_maliyet": sum(
                        float(k.get("miktar") or 0) * float(k.get("birim_fiyat") or 0)
                        for k in kalemler
                    ),
                    "kalem_sayisi": len(kalemler),
                    "durum": proje.get("durum", "") if proje else "",
                    "kalemler": kalemler,
                    "kategori_dagilimi": {},
                }
                baglam = self.engine.proje_baglam_olustur(proje_data)
            except Exception as e:
                logger.warning(f"Proje bağlamı alınamadı: {e}")

        prompt = GANTT_PLAN_PROMPT.format(proje_baglam=baglam)
        self.engine.mesaj_ekle_kullanici(prompt)
        self._sohbete_ekle("sistem", "Gantt iş programı oluşturuluyor...")
        self.engine.set_proje_baglam(self.db, self.proje_id)
        if self._gantt_engine:
            self.engine.set_gantt_engine(self._gantt_engine)
        if self._gantt_window:
            self.engine.set_gantt_window(self._gantt_window)
        self._aracli_basla()

    # ── Signal Slotları ─────────────────────────────────────────────────────

    @pyqtSlot(str)
    def _yanit_parcasi_geldi(self, parca: str):
        """Streaming modda her yanıt parçası geldiğinde."""
        cursor = self.sohbet_alani.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#e0e0e0"))
        cursor.insertText(parca, fmt)
        self.sohbet_alani.setTextCursor(cursor)
        self.sohbet_alani.ensureCursorVisible()
        self._asistan_yanit_buffer += parca

    @pyqtSlot(str, str)
    def _arac_sonucu_goster(self, arac_adi: str, sonuc: str):
        """Araç çağrısı sonucunu turuncu renkte göster."""
        arac_ad_tr = ARAC_ADLARI.get(arac_adi, arac_adi)
        cursor = self.sohbet_alani.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt_baslik = QTextCharFormat()
        fmt_baslik.setForeground(QColor("#FFA500"))
        fmt_baslik.setFontWeight(QFont.Weight.Bold)
        separator = "─" * 45
        cursor.insertText(f"\n{separator}\n", fmt_baslik)
        cursor.insertText(f"🔧 {arac_ad_tr}\n", fmt_baslik)

        fmt_icerik = QTextCharFormat()
        fmt_icerik.setForeground(QColor("#FFD580"))
        fmt_icerik.setFontWeight(QFont.Weight.Normal)
        cursor.insertText(sonuc + "\n", fmt_icerik)

        fmt_alt = QTextCharFormat()
        fmt_alt.setForeground(QColor("#FFA500"))
        fmt_alt.setFontWeight(QFont.Weight.Bold)
        cursor.insertText(f"{separator}\n", fmt_alt)

        self.sohbet_alani.setTextCursor(cursor)
        self.sohbet_alani.ensureCursorVisible()

    @pyqtSlot(str)
    def _aracli_yanit_geldi(self, metin: str):
        """Araçlı modda nihai yanıt geldiğinde."""
        self._sohbete_ekle("asistan", metin)
        if self.engine:
            self.engine.mesaj_ekle_asistan(metin)
        self._son_yanit = metin

        # Gantt modunda parse dene
        if self._aktif_mod == 3:
            self._gantt_parse_dene(metin)

    @pyqtSlot(str)
    def _hata_geldi(self, hata: str):
        self._sohbete_ekle("hata", f"API Hatası: {hata}")
        self.durum_label.setText(f"Hata: {hata[:120]}")

    @pyqtSlot()
    def _islem_bitti_streaming(self):
        """Streaming thread bitti."""
        if self._asistan_yanit_buffer:
            if self.engine:
                self.engine.mesaj_ekle_asistan(self._asistan_yanit_buffer)
            self._asistan_yanit_buffer = ""
        self._ui_mesgul_yap(False)
        self.durum_label.setText("Yanıt alındı. Yeni soru yazabilirsiniz.")
        self._current_thread = None
        self._gecmis_paneli_yenile()

    @pyqtSlot()
    def _islem_bitti_aracli(self):
        """Araçlı thread bitti."""
        self._ui_mesgul_yap(False)
        self.durum_label.setText("Yanıt tamamlandı.")
        self._current_thread = None
        self._gecmis_paneli_yenile()
        # Gantt modundaysa veya Gantt araçları çağrıldıysa görsel yenile
        if self._aktif_mod == 3 or self._gantt_window is not None:
            self.gantt_guncellendi.emit()

    # ── Gantt Parse ve Aktarım ──────────────────────────────────────────────

    def _gantt_parse_dene(self, metin: str):
        """Claude yanıtından Gantt görev listesini parse et."""
        try:
            bas = metin.find("GANTT_PLAN_BASLANGIC")
            bit = metin.find("GANTT_PLAN_BITIS")
            if bas == -1 or bit == -1:
                return

            blok = metin[bas + len("GANTT_PLAN_BASLANGIC"):bit].strip()
            satirlar = [s.strip() for s in blok.splitlines() if s.strip()]

            # Header satırını atla
            if satirlar and "sıra" in satirlar[0].lower():
                satirlar = satirlar[1:]

            gorevler = []
            for satir in satirlar:
                parcalar = [p.strip() for p in satir.split("|")]
                if len(parcalar) < 4:
                    continue
                try:
                    gorev = {
                        "sira":       int(parcalar[0]),
                        "ad":         parcalar[1],
                        "sure":       int(parcalar[2]),
                        "kaynak":     parcalar[3] if len(parcalar) > 3 else "",
                        "bagimlilik": parcalar[4] if len(parcalar) > 4 else "Yok",
                    }
                    gorevler.append(gorev)
                except (ValueError, IndexError):
                    continue

            if gorevler:
                self._parsed_gantt_tasks = gorevler
                self.gantt_aktar_btn.setVisible(True)
                self.durum_label.setText(
                    f"{len(gorevler)} görev parse edildi. 'Gantt'a Aktar' ile ekleyebilirsiniz."
                )
        except Exception as e:
            logger.warning(f"Gantt parse hatası: {e}")

    def _gantt_aktar(self):
        """Parse edilmiş görevleri Gantt engine'e ekle."""
        if not self._parsed_gantt_tasks:
            QMessageBox.warning(self, "Görev Yok", "Aktarılacak Gantt görevi bulunamadı.")
            return
        if not self._gantt_engine:
            QMessageBox.warning(
                self, "Gantt Bağlantısı Yok",
                "Gantt iş programına bağlantı kurulamadı.\n"
                "Ana pencereden Gantt sekmesini açın."
            )
            return

        # Onay dialogu
        gorev_listesi = "\n".join(
            f"  {g['sira']:2d}. {g['ad']} — {g['sure']} gün | {g['kaynak']}"
            for g in self._parsed_gantt_tasks
        )
        cevap = QMessageBox.question(
            self,
            "Gantt'a Aktar",
            f"Aşağıdaki {len(self._parsed_gantt_tasks)} görev Gantt'a eklenecek:\n\n"
            f"{gorev_listesi}\n\nDevam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return

        try:
            from app.core.gantt_engine import Task

            baslangic = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
            mevcut_idler = list(self._gantt_engine.tasks.keys())
            max_id = max(mevcut_idler, default=0)

            sira_to_id: Dict[int, int] = {}

            for gorev in self._parsed_gantt_tasks:
                task_id = max_id + gorev["sira"]
                task = Task(
                    task_id=task_id,
                    ad=gorev["ad"],
                    sure_gun=gorev["sure"],
                    baslangic_tarihi=baslangic,
                    kaynak=gorev.get("kaynak", ""),
                )
                task.bitis_tarihi = task.hesapla_bitis_tarihi()
                self._gantt_engine.add_task_with_wbs(task)
                sira_to_id[gorev["sira"]] = task_id

            # Bağımlılıkları ekle
            for gorev in self._parsed_gantt_tasks:
                bag_str = str(gorev.get("bagimlilik", "Yok")).strip()
                if bag_str and bag_str.lower() != "yok":
                    for b in bag_str.split(","):
                        b = b.strip()
                        if b.isdigit():
                            onceki_sira = int(b)
                            if (onceki_sira in sira_to_id
                                    and gorev["sira"] in sira_to_id):
                                try:
                                    self._gantt_engine.add_dependency(
                                        sira_to_id[onceki_sira],
                                        sira_to_id[gorev["sira"]],
                                        "FS",
                                    )
                                except Exception:
                                    pass

            # CPM hesapla
            try:
                self._gantt_engine.calculate_cpm()
            except Exception:
                pass

            # Gantt'ı yenile
            self.gantt_guncellendi.emit()

            eklenen = len(self._parsed_gantt_tasks)
            self._parsed_gantt_tasks = []
            self.gantt_aktar_btn.setVisible(False)
            self._sohbete_ekle(
                "sistem",
                f"{eklenen} görev Gantt iş programına eklendi. Gantt sekmesinden görüntüleyebilirsiniz."
            )
            self.durum_label.setText(f"{eklenen} görev Gantt'a aktarıldı.")

        except Exception as e:
            QMessageBox.critical(self, "Aktarım Hatası", f"Gantt aktarımı başarısız:\n{e}")
            logger.error(f"Gantt aktarım hatası: {e}")

    # ── Yardımcı UI Metodları ───────────────────────────────────────────────

    def _input_key_press(self, event):
        from PyQt6.QtCore import Qt as Qt_
        if (event.key() == Qt_.Key.Key_Return and
                event.modifiers() == Qt_.KeyboardModifier.ControlModifier):
            self._mesaj_gonder()
        else:
            QTextEdit.keyPressEvent(self.mesaj_input, event)

    def _api_durumu_guncelle(self):
        if not self._engine_ok or not self.engine:
            self.api_durum_label.setText("Engine yüklenemedi")
            self.gonder_btn.setEnabled(False)
            return
        if self.engine.api_key_gecerli():
            model_kisa = self.engine.model.split("-")[1].capitalize()
            self.api_durum_label.setText(f"API bağlı — {model_kisa}")
            self.api_durum_label.setStyleSheet("color: #00ff88; font-size: 11px;")
            self.gonder_btn.setEnabled(True)
            self.durum_label.setText("Hazır. Sorunuzu yazıp Ctrl+Enter ile gönderin.")
        else:
            self.api_durum_label.setText("API anahtarı girilmedi")
            self.api_durum_label.setStyleSheet("color: #ffaa00; font-size: 11px;")
            self.gonder_btn.setEnabled(False)
            self.durum_label.setText("API anahtarı girilmemiş. API Ayarları butonuna tıklayın.")

    def _ui_mesgul_yap(self, mesgul: bool):
        self.gonder_btn.setEnabled(not mesgul and (self.engine.api_key_gecerli() if self.engine else False))
        self.iptal_btn.setEnabled(mesgul)
        self.analiz_basla_btn.setEnabled(not mesgul)
        self.gantt_plan_basla_btn.setEnabled(not mesgul)
        self.hakedis_basla_btn.setEnabled(not mesgul)

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
        cursor.insertText(f"\n{'─' * 50}\n{ad}\n", fmt_baslik)

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
        cursor.insertText(f"\n{'─' * 50}\nAI Asistan\n", fmt)
        self.sohbet_alani.setTextCursor(cursor)
        self._asistan_yanit_buffer = ""

    # ── Dışarıdan Çağrılan Metodlar ────────────────────────────────────────

    def proje_guncelle(self, proje_id: Optional[int], proje_adi: str = ""):
        """Ana pencereden proje değiştiğinde çağrılır."""
        self.proje_id = proje_id
        if self.engine:
            self.engine.set_proje_baglam(self.db, proje_id)
        if proje_id and proje_adi:
            self.baglam_label.setText(f"Proje:\n{proje_adi}")
            self.baglam_label.setStyleSheet("color: #00ff88; font-size: 10px;")
        else:
            self.baglam_label.setText("Aktif proje: Yok")
            self.baglam_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")

    def set_gantt_engine(self, gantt_engine):
        """Ana pencereden Gantt engine referansı iletilir."""
        self._gantt_engine = gantt_engine
        if self.engine:
            self.engine.set_gantt_engine(gantt_engine)
        if gantt_engine is not None:
            task_sayisi = len(getattr(gantt_engine, "tasks", {}))
            self.gantt_durum_label.setText(
                f"Gantt: Bağlı ({task_sayisi} görev)"
            )
            self.gantt_durum_label.setStyleSheet("color: #00ff88; font-size: 10px;")
        else:
            self.gantt_durum_label.setText("Gantt: Bağlı değil")
            self.gantt_durum_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")

    def set_gantt_window(self, gantt_window):
        """GanttWindow referansını sakla ve ClaudeEngine'e ilet."""
        self._gantt_window = gantt_window
        if self.engine:
            self.engine.set_gantt_window(gantt_window)

    # ── Buton Slotları ──────────────────────────────────────────────────────

    def _api_ayarla(self):
        if not self._engine_ok:
            QMessageBox.critical(self, "Hata", "Engine yüklenemedi.")
            return
        dialog = ApiAyarDialog(self.engine, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._api_durumu_guncelle()
            self._sohbete_ekle("sistem", "API ayarları güncellendi. Artık soru sorabilirsiniz.")

    def _istegi_durdur(self):
        if self.engine:
            self.engine.aktif_istegi_iptal_et()
        self.iptal_btn.setEnabled(False)
        self.durum_label.setText("Durduruldu.")

    def _dosya_sec(self):
        """Dosya seç (Excel, görsel, PDF veya DXF) ve ek olarak kaydet."""
        from PyQt6.QtWidgets import QFileDialog
        dosya, _ = QFileDialog.getOpenFileName(
            self,
            "Dosya Seç",
            "",
            "Desteklenen Dosyalar (*.xlsx *.xls *.png *.jpg *.jpeg *.webp *.pdf *.dxf);;"
            "Excel Dosyaları (*.xlsx *.xls);;"
            "Görseller (*.png *.jpg *.jpeg *.webp);;"
            "PDF Dosyaları (*.pdf);;"
            "AutoCAD DXF (*.dxf);;"
            "Tüm Dosyalar (*)",
        )
        if not dosya:
            return
        uzanti = os.path.splitext(dosya)[1].lower()
        if uzanti in (".png", ".jpg", ".jpeg", ".webp"):
            max_boyut = 5 * 1024 * 1024
        elif uzanti == ".pdf":
            max_boyut = 20 * 1024 * 1024
        else:
            max_boyut = 10 * 1024 * 1024
        boyut = os.path.getsize(dosya)
        if boyut > max_boyut:
            QMessageBox.warning(
                self, "Dosya Çok Büyük",
                f"Maksimum izin verilen: {max_boyut // (1024 * 1024)} MB\n"
                f"Seçilen dosya: {boyut / (1024 * 1024):.1f} MB",
            )
            return
        self._ekli_dosya_yolu = dosya
        self.dosya_adi_label.setText("📎 " + os.path.basename(dosya))
        self.dosya_adi_label.setVisible(True)
        self.dosya_kaldir_btn.setVisible(True)

    def _dosya_kaldir(self):
        """Seçili dosya ekini kaldır ve UI'ı sıfırla."""
        self._ekli_dosya_yolu = None
        self.dosya_adi_label.setText("")
        self.dosya_adi_label.setVisible(False)
        self.dosya_kaldir_btn.setVisible(False)

    def _gecmisi_temizle(self):
        if self.engine:
            self.engine.gecmis_temizle()
        self.sohbet_alani.clear()
        self._parsed_gantt_tasks = []
        self.gantt_aktar_btn.setVisible(False)
        self._dosya_kaldir()
        self.durum_label.setText("Geçmiş temizlendi.")
        self._gecmis_paneli_yenile()

    def _sohbeti_kopyala(self):
        metin = self.sohbet_alani.toPlainText()
        if metin:
            QApplication.clipboard().setText(metin)
            self.durum_label.setText("Sohbet panoya kopyalandı.")

    def _sohbeti_txt_kaydet(self):
        """Sohbet geçmişini TXT dosyasına kaydet."""
        metin = self.sohbet_alani.toPlainText()
        if not metin.strip():
            QMessageBox.information(self, "Boş Sohbet", "Kaydedilecek sohbet içeriği yok.")
            return
        tarih_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        dosya, _ = QFileDialog.getSaveFileName(
            self,
            "Sohbeti Kaydet",
            f"insaat_asistan_{tarih_str}.txt",
            "Metin Dosyası (*.txt);;Tüm Dosyalar (*)",
        )
        if dosya:
            try:
                with open(dosya, "w", encoding="utf-8") as f:
                    baslik = "İnşaat Metraj Pro — AI Asistan Sohbet Kaydı\n"
                    tarih = "Tarih: " + datetime.now().strftime("%d.%m.%Y %H:%M") + "\n"
                    f.write(baslik)
                    f.write(tarih)
                    f.write("=" * 60 + "\n\n")
                    f.write(metin)
                self.durum_label.setText(f"Kaydedildi: {dosya}")
            except Exception as e:
                QMessageBox.critical(self, "Kayıt Hatası", f"Dosya kaydedilemedi:\n{e}")

    # ── Geçmiş Sohbet Paneli Metodları ─────────────────────────────────────

    def _gecmis_paneli_yenile(self):
        """gecmis_listesi_widget'ı engine'den güncelle. Her item UserRole'da id saklar."""
        if not self._engine_ok or not self.engine:
            return
        try:
            liste = self.engine.gecmis_listesi()
            self.gecmis_listesi_widget.clear()
            aktif_id = getattr(self.engine, "_aktif_konusma_id", "")
            for kayit in liste:
                kid = kayit.get("id", "")
                baslik = kayit.get("baslik", "Konuşma")
                tarih = kayit.get("tarih", "")
                msay = kayit.get("mesaj_sayisi", 0)
                etiket = f"{baslik[:28]}  [{msay} msg]  {tarih}"
                item = QListWidgetItem(etiket)
                item.setData(Qt.ItemDataRole.UserRole, kid)
                # Aktif konuşmayı vurgula
                if kid == aktif_id:
                    item.setForeground(QColor("#00BFFF"))
                self.gecmis_listesi_widget.addItem(item)
        except Exception as e:
            logger.warning(f"Geçmiş paneli yenileme hatası: {e}")

    def _gecmis_yukle(self):
        """Seçili konuşmayı yükle ve sohbet_alani'nı yeniden çiz."""
        if not self._engine_ok or not self.engine:
            return
        item = self.gecmis_listesi_widget.currentItem()
        if not item:
            self.durum_label.setText("Yüklenecek konuşmayı seçin.")
            return
        kid = item.data(Qt.ItemDataRole.UserRole)
        basarili = self.engine.gecmis_yukle(kid)
        if not basarili:
            QMessageBox.warning(self, "Yükleme Hatası", "Konuşma yüklenemedi.")
            return
        # Sohbet alanını temizle ve geçmişi yeniden çiz
        self.sohbet_alani.clear()
        for msg in self.engine.gecmis:
            rol = msg.get("role", "")
            icerik = msg.get("content", "")
            if isinstance(icerik, list):
                # Çoklu content blokları (görsel vb.) → metin bloklarını al
                metin_parcalar = []
                for blok in icerik:
                    if isinstance(blok, dict) and blok.get("type") == "text":
                        metin_parcalar.append(str(blok.get("text", "")))
                icerik = " ".join(metin_parcalar)
            if rol == "user":
                self._sohbete_ekle("kullanici", str(icerik))
            elif rol == "assistant":
                self._sohbete_ekle("asistan", str(icerik))
        baslik = item.text().split("[")[0].strip()
        self.durum_label.setText(f"Konuşma yüklendi: {baslik}")
        self._gecmis_paneli_yenile()

    def _gecmis_sil(self):
        """Seçili konuşmayı sil ve listeyi güncelle."""
        if not self._engine_ok or not self.engine:
            return
        item = self.gecmis_listesi_widget.currentItem()
        if not item:
            self.durum_label.setText("Silinecek konuşmayı seçin.")
            return
        kid = item.data(Qt.ItemDataRole.UserRole)
        baslik = item.text().split("[")[0].strip()
        cevap = QMessageBox.question(
            self,
            "Konuşmayı Sil",
            f"'{baslik}' konuşması silinecek.\nEmin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return
        basarili = self.engine.gecmis_sil(kid)
        if basarili:
            self.durum_label.setText(f"Konuşma silindi: {baslik}")
        else:
            QMessageBox.warning(self, "Silme Hatası", "Konuşma silinemedi.")
        self._gecmis_paneli_yenile()

    def _yeni_sohbet_baslat(self):
        """Mevcut konuşmayı temizle, yeni boş sohbet başlat."""
        self._gecmisi_temizle()
        self.durum_label.setText("Yeni sohbet başlatıldı. Sorunuzu yazın.")

    def _hizli_soru_sor(self, soru: str):
        """Hızlı soru butonuna tıklandığında."""
        self.mesaj_input.setPlainText(soru)
        self._mesaj_gonder()
