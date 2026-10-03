"""
Şablon Sihirbazı — 4 Adımlı Proje Şablonu Seçici
Teknik proje yönetimi bilgisi olmayan kullanıcılar için hazır program kurulumu

Adım 1: Kategori Seç
Adım 2: Alt Tip Seç
Adım 3: Proje Detayları (ad, tarih, şehir)
Adım 4: Özet ve Onay
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateEdit, QLineEdit, QWidget, QScrollArea, QFrame,
    QDialogButtonBox, QGridLayout, QSizePolicy, QStackedWidget,
    QGroupBox
)
from PyQt6.QtCore import Qt, QDate, QSize
from PyQt6.QtGui import QFont, QColor
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# ─── RENK PALETİ ─────────────────────────────────────────────────────────────
RENK_KONUT       = "#27ae60"
RENK_TICARI      = "#2980b9"
RENK_ENDUSTRIYEL = "#8e44ad"
RENK_ALTYAPI     = "#d35400"
RENK_YENILEME    = "#16a085"

KATEGORI_RENKLER = {
    "KONUT":        RENK_KONUT,
    "TİCARİ":       RENK_TICARI,
    "ENDÜSTRİYEL":  RENK_ENDUSTRIYEL,
    "ALTYAPI":      RENK_ALTYAPI,
    "YENİLEME":     RENK_YENILEME,
}

KATEGORI_ACIKLAMA = {
    "KONUT":        "Villa, Apartman, Toplu Konut\nMüstakil Ev",
    "TİCARİ":       "Dükkan, Ofis, Otel\nAlışveriş Merkezi",
    "ENDÜSTRİYEL":  "Fabrika, Depo\nSanayi Tesisi",
    "ALTYAPI":      "Yol, Köprü\nİstinat Duvarı",
    "YENİLEME":     "Tadilat, Mantolama\nRestorasyon",
}


# ─── BÜYÜK KATEGORİ BUTONU ──────────────────────────────────────────────────

class KategoriButon(QPushButton):
    def __init__(self, kategori: str, ikon: str, parent=None):
        super().__init__(parent)
        renk = KATEGORI_RENKLER.get(kategori, "#3498db")
        aciklama = KATEGORI_ACIKLAMA.get(kategori, "")

        self.setText(f"{ikon}\n{kategori}\n\n{aciklama}")
        self.setFixedWidth(150)
        self.setMinimumHeight(130)
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {renk}22;
                color: {renk};
                border: 2px solid {renk};
                border-radius: 10px;
                padding: 8px;
                text-align: center;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {renk}44;
            }}
            QPushButton:checked {{
                background-color: {renk};
                color: white;
            }}
        """)
        self.setCheckable(True)


# ─── TİP BUTONU ─────────────────────────────────────────────────────────────

class TipButon(QPushButton):
    def __init__(self, sablon, parent=None):
        super().__init__(parent)
        self._sablon = sablon
        self.setText(
            f"{sablon.ikon} {sablon.tip}\n"
            f"{len(sablon.gorevler)} iş kalemi\n"
            f"~{sablon.tahmini_sure_gun} gün"
        )
        renk = KATEGORI_RENKLER.get(sablon.kategori, "#3498db")
        self.setFixedSize(QSize(160, 90))
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {renk}11;
                color: #2c3e50;
                border: 2px solid {renk}66;
                border-radius: 8px;
                padding: 6px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {renk}33;
                border: 2px solid {renk};
            }}
            QPushButton:checked {{
                background-color: {renk};
                color: white;
                font-weight: bold;
            }}
        """)
        self.setCheckable(True)

    @property
    def sablon(self):
        return self._sablon


# ─── ŞABLON SİHİRBAZI ANA DİALOG ────────────────────────────────────────────

class SablonSihirbazi(QDialog):
    """
    4 Adımlı Proje Şablonu Sihirbazı.

    Neyi çözüyoruz?
    - Kullanıcı boş iş programı yerine hazır şablon ile başlasın.
    - CPM/WBS bilgisi gerektirmeden dakikalar içinde program kurulsun.

    Test:
    - sihirbaz = SablonSihirbazi(parent)
    - if sihirbaz.exec() == QDialog.DialogCode.Accepted:
    -     secim = sihirbaz.get_secim()
    -     # secim = {'sablon': ProjeSablonu, 'baslangic': datetime, 'sehir': str, 'proje_adi': str}
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🧩 Proje Şablonu Sihirbazı")
        self.setMinimumSize(620, 520)
        self.setModal(True)

        # Seçim durumu
        self._secili_kategori: Optional[str] = None
        self._secili_sablon = None
        self._kategori_butonlar: Dict[str, KategoriButon] = {}
        self._tip_butonlar: list = []

        try:
            from app.core.proje_sablonlari import SablonYoneticisi
            self._yonetici = SablonYoneticisi()
        except Exception as e:
            logger.error(f"SablonYoneticisi yüklenemedi: {e}")
            self._yonetici = None

        self._init_ui()

    # ── UI KURULUMU ──────────────────────────────────────────────

    def _init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(16, 16, 16, 12)
        main_layout.setSpacing(10)

        # Başlık
        baslik = QLabel("🧩 Proje Şablonu Sihirbazı")
        baslik.setStyleSheet("font-size: 16pt; font-weight: bold; color: #2c3e50; margin-bottom: 4px;")
        main_layout.addWidget(baslik)

        # Adım göstergesi
        self._adim_label = QLabel()
        self._adim_label.setStyleSheet("color: #7f8c8d; font-size: 10pt;")
        main_layout.addWidget(self._adim_label)

        # QStackedWidget ile 4 adım
        self._stack = QStackedWidget()
        self._stack.addWidget(self._adim1_widget())
        self._stack.addWidget(self._adim2_widget())
        self._stack.addWidget(self._adim3_widget())
        self._stack.addWidget(self._adim4_widget())
        main_layout.addWidget(self._stack, stretch=1)

        # Navigasyon butonları
        nav_layout = QHBoxLayout()
        self._geri_btn = QPushButton("◀ Geri")
        self._geri_btn.setEnabled(False)
        self._geri_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._geri_btn.clicked.connect(self._onceki_adim)

        self._ileri_btn = QPushButton("İleri ▶")
        self._ileri_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._ileri_btn.setStyleSheet(
            "background-color: #3498db; color: white; border-radius: 4px; padding: 5px;"
        )
        self._ileri_btn.clicked.connect(self._sonraki_adim)

        self._olustur_btn = QPushButton("✅ Programı Oluştur")
        self._olustur_btn.setStyleSheet(
            "background-color: #27ae60; color: white; border-radius: 4px; "
            "padding: 6px 16px; font-weight: bold; font-size: 11pt;"
        )
        self._olustur_btn.setVisible(False)
        self._olustur_btn.clicked.connect(self.accept)

        iptal_btn = QPushButton("İptal")
        iptal_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        iptal_btn.clicked.connect(self.reject)

        nav_layout.addWidget(iptal_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self._geri_btn)
        nav_layout.addWidget(self._ileri_btn)
        nav_layout.addWidget(self._olustur_btn)

        main_layout.addLayout(nav_layout)
        self.setLayout(main_layout)
        self._adim_goster(0)

    # ── ADIM 1: KATEGORİ SEÇ ────────────────────────────────────

    def _adim1_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        aciklama = QLabel("Projenizin türünü seçin:")
        aciklama.setStyleSheet("font-size: 12pt; color: #34495e; margin-bottom: 8px;")
        layout.addWidget(aciklama)

        grid = QGridLayout()
        grid.setSpacing(12)

        kategoriler = []
        if self._yonetici:
            kategoriler = self._yonetici.get_kategoriler()
        else:
            kategoriler = ["KONUT", "TİCARİ", "ENDÜSTRİYEL", "ALTYAPI", "YENİLEME"]

        ikonlar = {"KONUT": "🏠", "TİCARİ": "🏢", "ENDÜSTRİYEL": "🏭",
                   "ALTYAPI": "🛣", "YENİLEME": "🔨"}

        for i, kat in enumerate(kategoriler):
            btn = KategoriButon(kat, ikonlar.get(kat, "📋"))
            btn.clicked.connect(lambda checked, k=kat, b=btn: self._kategori_sec(k, b))
            self._kategori_butonlar[kat] = btn
            grid.addWidget(btn, i // 3, i % 3)

        layout.addLayout(grid)
        layout.addStretch()
        return widget

    # ── ADIM 2: TİP SEÇ ─────────────────────────────────────────

    def _adim2_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self._adim2_aciklama = QLabel("Alt tip seçin:")
        self._adim2_aciklama.setStyleSheet("font-size: 12pt; color: #34495e; margin-bottom: 8px;")
        layout.addWidget(self._adim2_aciklama)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        self._tip_container = QWidget()
        self._tip_grid = QGridLayout(self._tip_container)
        self._tip_grid.setSpacing(10)
        scroll.setWidget(self._tip_container)
        layout.addWidget(scroll)
        return widget

    # ── ADIM 3: PROJE DETAYLARI ─────────────────────────────────

    def _adim3_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        aciklama = QLabel("Proje bilgilerini girin:")
        aciklama.setStyleSheet("font-size: 12pt; color: #34495e;")
        layout.addWidget(aciklama)

        form_group = QGroupBox()
        form_group.setStyleSheet("QGroupBox { border: 1px solid #dee2e6; border-radius: 6px; padding: 12px; }")
        form_layout = QVBoxLayout(form_group)
        form_layout.setSpacing(12)

        # Proje Adı
        ad_layout = QHBoxLayout()
        ad_label = QLabel("Proje Adı:")
        ad_label.setMinimumWidth(230)
        ad_label.setStyleSheet("font-weight: bold;")
        self._proje_adi_input = QLineEdit()
        self._proje_adi_input.setPlaceholderText("Örn: Kaya Villası, Merkez Apartman...")
        self._proje_adi_input.setStyleSheet("padding: 6px; border: 1px solid #ced4da; border-radius: 4px;")
        ad_layout.addWidget(ad_label)
        ad_layout.addWidget(self._proje_adi_input)
        form_layout.addLayout(ad_layout)

        # Başlangıç Tarihi
        tarih_layout = QHBoxLayout()
        tarih_label = QLabel("Başlangıç Tarihi:")
        tarih_label.setMinimumWidth(230)
        tarih_label.setStyleSheet("font-weight: bold;")
        self._baslangic_date = QDateEdit()
        self._baslangic_date.setCalendarPopup(True)
        self._baslangic_date.setDate(QDate.currentDate())
        self._baslangic_date.setStyleSheet("padding: 4px; border: 1px solid #ced4da; border-radius: 4px;")
        tarih_layout.addWidget(tarih_label)
        tarih_layout.addWidget(self._baslangic_date)
        tarih_layout.addStretch()
        form_layout.addLayout(tarih_layout)

        # Şehir (opsiyonel)
        sehir_layout = QHBoxLayout()
        sehir_label = QLabel("Şehir (Opsiyonel):")
        sehir_label.setMinimumWidth(230)
        sehir_label.setStyleSheet("font-weight: bold;")
        self._sehir_input = QLineEdit()
        self._sehir_input.setPlaceholderText("Hava durumu entegrasyonu için (Ankara, İstanbul...)")
        self._sehir_input.setStyleSheet("padding: 6px; border: 1px solid #ced4da; border-radius: 4px;")
        sehir_layout.addWidget(sehir_label)
        sehir_layout.addWidget(self._sehir_input)
        form_layout.addLayout(sehir_layout)

        layout.addWidget(form_group)
        layout.addStretch()
        return widget

    # ── ADIM 4: ÖZET ─────────────────────────────────────────────

    def _adim4_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        baslik = QLabel("✅ Özet — Onaylıyor musunuz?")
        baslik.setStyleSheet("font-size: 13pt; font-weight: bold; color: #27ae60;")
        layout.addWidget(baslik)

        ozet_group = QGroupBox()
        ozet_group.setStyleSheet("""
            QGroupBox {
                background-color: #f8fff8;
                border: 2px solid #27ae60;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        ozet_layout = QVBoxLayout(ozet_group)
        ozet_layout.setSpacing(8)

        self._ozet_sablon_label = QLabel()
        self._ozet_sablon_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2c3e50;")
        ozet_layout.addWidget(self._ozet_sablon_label)

        self._ozet_detay_label = QLabel()
        self._ozet_detay_label.setStyleSheet("font-size: 10pt; color: #6c757d;")
        self._ozet_detay_label.setWordWrap(True)
        ozet_layout.addWidget(self._ozet_detay_label)

        self._ozet_proje_label = QLabel()
        self._ozet_proje_label.setStyleSheet("font-size: 11pt; color: #495057;")
        ozet_layout.addWidget(self._ozet_proje_label)

        # İlk 5 görev önizleme
        onizleme_baslik = QLabel("İlk 5 görev:")
        onizleme_baslik.setStyleSheet("font-weight: bold; color: #495057; margin-top: 8px;")
        ozet_layout.addWidget(onizleme_baslik)

        self._onizleme_label = QLabel()
        self._onizleme_label.setStyleSheet(
            "background-color: #f1f8f1; border: 1px solid #c3e6cb; "
            "border-radius: 4px; padding: 8px; color: #155724; font-size: 9pt;"
        )
        self._onizleme_label.setWordWrap(True)
        ozet_layout.addWidget(self._onizleme_label)

        layout.addWidget(ozet_group)
        layout.addStretch()
        return widget

    # ── NAVİGASYON ───────────────────────────────────────────────

    def _adim_goster(self, adim: int) -> None:
        self._stack.setCurrentIndex(adim)
        self._geri_btn.setEnabled(adim > 0)
        self._ileri_btn.setVisible(adim < 3)
        self._olustur_btn.setVisible(adim == 3)

        adim_metinleri = [
            "Adım 1/4 — Kategori Seçin",
            "Adım 2/4 — Alt Tip Seçin",
            "Adım 3/4 — Proje Bilgileri",
            "Adım 4/4 — Özet ve Onay",
        ]
        self._adim_label.setText(adim_metinleri[adim])

    def _sonraki_adim(self) -> None:
        adim = self._stack.currentIndex()

        if adim == 0:
            if not self._secili_kategori:
                self._adim_label.setStyleSheet("color: #e74c3c; font-size: 10pt;")
                self._adim_label.setText("⚠️  Lütfen bir kategori seçin!")
                return
            self._tip_listesini_yenile()
            self._adim_goster(1)

        elif adim == 1:
            if not self._secili_sablon:
                self._adim_label.setStyleSheet("color: #e74c3c; font-size: 10pt;")
                self._adim_label.setText("⚠️  Lütfen bir şablon seçin!")
                return
            self._adim_goster(2)

        elif adim == 2:
            self._ozet_guncelle()
            self._adim_goster(3)

        self._adim_label.setStyleSheet("color: #7f8c8d; font-size: 10pt;")

    def _onceki_adim(self) -> None:
        adim = self._stack.currentIndex()
        if adim > 0:
            self._adim_goster(adim - 1)

    # ── SEÇİM LOJİĞİ ────────────────────────────────────────────

    def _kategori_sec(self, kategori: str, btn: KategoriButon) -> None:
        """Kategori seç, diğer butonları kaldır"""
        for k, b in self._kategori_butonlar.items():
            b.setChecked(k == kategori)
        self._secili_kategori = kategori
        self._secili_sablon = None

    def _tip_listesini_yenile(self) -> None:
        """Seçilen kategoriye göre tip butonlarını oluştur"""
        # Temizle
        for btn in self._tip_butonlar:
            btn.deleteLater()
        self._tip_butonlar.clear()

        if not self._yonetici or not self._secili_kategori:
            return

        sablonlar = self._yonetici.get_sablonlar(self._secili_kategori)
        self._adim2_aciklama.setText(
            f"{self._secili_kategori} projeleri — alt tip seçin:"
        )

        for i, sablon in enumerate(sablonlar):
            btn = TipButon(sablon)
            btn.clicked.connect(lambda checked, s=sablon, b=btn: self._tip_sec(s, b))
            self._tip_grid.addWidget(btn, i // 3, i % 3)
            self._tip_butonlar.append(btn)

    def _tip_sec(self, sablon, btn: TipButon) -> None:
        """Tip seç, diğerlerini kaldır"""
        for b in self._tip_butonlar:
            b.setChecked(b == btn)
        self._secili_sablon = sablon

    def _ozet_guncelle(self) -> None:
        """Adım 4 özetini güncelle"""
        if not self._secili_sablon:
            return

        s = self._secili_sablon
        proje_adi = self._proje_adi_input.text().strip() or f"Yeni {s.tip} Projesi"
        tarih_q = self._baslangic_date.date()
        tarih_str = f"{tarih_q.day():02d}.{tarih_q.month():02d}.{tarih_q.year()}"
        sehir = self._sehir_input.text().strip()

        self._ozet_sablon_label.setText(f"{s.ikon}  {s.tip}")
        self._ozet_detay_label.setText(
            f"{s.aciklama}\n"
            f"{len(s.gorevler)} iş kalemi · ~{s.tahmini_sure_gun} iş günü"
        )
        self._ozet_proje_label.setText(
            f"📌 Proje: {proje_adi}   |   📅 Başlangıç: {tarih_str}"
            + (f"   |   📍 {sehir}" if sehir else "")
        )

        # İlk 5 görev
        onizleme_satirlari = []
        for i, gorev in enumerate(s.gorevler[:5]):
            dep_str = ""
            if gorev.bagimlilik_indexler:
                dep_str = f" (sonra: {gorev.bagimlilik_indexler})"
            onizleme_satirlari.append(
                f"  {i+1}. {gorev.ad} — {gorev.sure_gun} gün{dep_str}"
            )
        if len(s.gorevler) > 5:
            onizleme_satirlari.append(f"  ... ve {len(s.gorevler)-5} iş kalemi daha")
        self._onizleme_label.setText("\n".join(onizleme_satirlari))

    # ── SONUÇ ALMA ────────────────────────────────────────────────

    def get_secim(self) -> Optional[Dict[str, Any]]:
        """
        Dialog kabul edildikten sonra seçim bilgilerini döndür.

        Returns:
            {
              'sablon': ProjeSablonu,
              'baslangic': datetime,
              'sehir': str,
              'proje_adi': str
            }
            veya None (iptal / seçim yapılmadı)
        """
        if not self._secili_sablon:
            return None

        tarih_q = self._baslangic_date.date()
        baslangic = datetime(tarih_q.year(), tarih_q.month(), tarih_q.day())
        proje_adi = self._proje_adi_input.text().strip()
        if not proje_adi:
            proje_adi = f"Yeni {self._secili_sablon.tip} Projesi"

        return {
            'sablon': self._secili_sablon,
            'baslangic': baslangic,
            'sehir': self._sehir_input.text().strip(),
            'proje_adi': proje_adi,
        }
