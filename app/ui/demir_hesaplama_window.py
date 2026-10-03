"""
Demir Hesaplama Penceresi
Insaat demiri (betonarme celik) agirlik ve maliyet hesaplama arayuzu.
Standart TS 708 nervurlu celik cubuk birim agirlik tablosuna gore hesaplama yapar.
"""

import logging
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView,
    QFormLayout, QMessageBox, QFrame, QGridLayout,
    QScrollArea, QTabWidget, QAbstractItemView, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from app.core.kesim_optimizasyon import coklu_cap_kesim_plani_hesapla

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Standart TS 708 nervurlu celik cubuk birim agirlik tablosu (kg/m)
# Formul: w = 0.006165 * cap^2  (cap mm cinsinden)
# ---------------------------------------------------------------------------
DEMIR_BIRIM_AGIRLIK = {
    8:  0.395,
    10: 0.617,
    12: 0.888,
    14: 1.208,
    16: 1.578,
    18: 2.000,
    20: 2.466,
    22: 2.984,
    25: 3.854,
    32: 6.313,
}

# Standart piyasa boyu (cm) — depo satisi 12 m / 1200 cm
STANDART_BOY_CM = 1200

# Yaklasik piyasa fiyati (TL/ton) — kullanici guncelleyebilir
VARSAYILAN_FIYAT_TON = 45_000.0

YARDIM_METNI = """
DEMIR HESAPLAMA — KULLANIM KILAVUZU
=====================================

[Temel Demir Hesabi Sekmesi]
* Cap      : Acilir listeden demir capini secin (mm).
* Boy      : Tek bir demir cubugunun uzunlugunu cm cinsinden girin.
* Adet     : Kac adet demir kullanilacagini girin.
* Birim Agirlik: Secilen cap icin TS 708 tablosundan otomatik gelir (kg/m).
* "Hesapla" butonuna basin -> Toplam agirlik (kg) ve tahmini maliyet gorunur.

[Toplu Hesap Sekmesi]
* "Satir Ekle" ile tabloya yeni demir kalemi ekleyin.
* Her satirda Cap, Boy (cm), Adet ve ihtiyari Not girin.
* "Toplam Hesapla" butonuna basin -> Her satirin agirligiyla genel toplam hesaplanir.
* "Secili Satiri Sil" ile istenmeyen satiri kaldirin.
* "Tabloyu Temizle" ile tum satirlari silin.
* "CSV'ye Aktar" ile sonuclari .csv dosyasina kaydedebilirsiniz.

[Birim Fiyat Ayari]
* Sag ust kosedeki "Birim Fiyat (TL/ton)" alanindan guncel piyasa fiyatini girin.
* Fiyat degistiginde mevcut hesaplama otomatik guncellenir.

[Kesim Listesi Sekmesi]
* "Toplu Hesap'tan Aktar" butonuyla mevcut demir listesini buraya aktar.
* Ya da "+ Satir Ekle" ile parcalari tek tek gir.
* "Standart Cubuk Boyu" alanina depodan alacaginiz cubuk boyunu girin (varsayilan 1200 cm = 12 m).
* "Kesim Plani Hesapla" butonuna basin.
  - Program, minimum fire birakmak icin optimum kesim siralamasi yapar (FFD algoritm.).
  - "Kesim Plani" sekmesi: hangi cubuktan hangi parcalarin kesilecegini gosterir.
  - "Siparis Formu" sekmesi: cap bazinda kac cubuk siparis edilecegini gosterir.
* Yesil satir: fire < %%5 (verimli). Turuncu satir: fire > %%15 (alternatif kesim deneyin).
* "CSV Aktar" ile kesim listesini Excel'de acabilirsiniz.

[Notlar]
* Hesaplamalar TS 708 standardina uygun birim agirlik tablosuna dayanir.
* Fire payi dahil degildir; sahada %3-5 fire eklemeniz onerilir.
* Agirlik formulu: W = (boy_m x birim_agirlik_kg_m x adet)
* Maliyet formulu: Maliyet = (W_kg / 1000) x fiyat_TL_ton
"""


# ---------------------------------------------------------------------------
# Yardimci: Salt okunabilir tablo hucresi
# ---------------------------------------------------------------------------
class _ReadOnlyItem(QTableWidgetItem):
    def __init__(self, text=""):
        super().__init__(str(text))
        self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)


# ---------------------------------------------------------------------------
# Ana pencere
# ---------------------------------------------------------------------------
class DemirHesaplamaWindow(QMainWindow):
    """
    Insaat demiri agirlik ve maliyet hesaplama penceresi.

    Neyi cozuyoruz?
      Sahadaki ustabasi veya muhendis; farkli cap ve boyda demirlerin toplam
      agirligini ve yaklasik maliyetini hizlica hesaplamak ister.
      Bu pencere hem tekil hem toplu hesaplama imkani sunar.

    Nasil test ederiz?
      >>> from app.ui.demir_hesaplama_window import DemirHesaplamaWindow
      >>> # PyQt6 QApplication gerektirir
      >>> win = DemirHesaplamaWindow()
      >>> assert win.windowTitle() == "Demir Hesaplama"
    """

    hesaplama_tamamlandi = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._birim_fiyat = VARSAYILAN_FIYAT_TON
        self._init_ui()

    # ------------------------------------------------------------------
    # UI kurulumu
    # ------------------------------------------------------------------
    def _init_ui(self):
        self.setWindowTitle("Demir Hesaplama")
        self.setGeometry(150, 150, 1050, 720)
        self.setMinimumSize(800, 560)

        merkez = QWidget()
        self.setCentralWidget(merkez)
        ana_layout = QVBoxLayout(merkez)
        ana_layout.setContentsMargins(10, 8, 10, 8)
        ana_layout.setSpacing(8)

        ana_layout.addWidget(self._ust_panel())

        # durum_label once olusturulmali: _toplu_hesap_sekmesi icindeki
        # _ornek_satirlar_ekle -> _toplu_satir_ekle bu label'i kullanir
        self.durum_label = QLabel("Hazir.")
        self.durum_label.setStyleSheet(
            "color: #555; font-size: 11px; padding: 2px 4px;"
        )

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        ana_layout.addWidget(self.tab_widget, stretch=1)

        self.tab_widget.addTab(self._temel_hesap_sekmesi(), "  Temel Demir Hesabi  ")
        self.tab_widget.addTab(self._toplu_hesap_sekmesi(), "  Toplu Hesap  ")
        self.tab_widget.addTab(self._referans_tablo_sekmesi(), "  Birim Agirlik Tablosu  ")
        self.tab_widget.addTab(self._kesim_listesi_sekmesi(), "  Kesim Listesi  ")

        ana_layout.addWidget(self.durum_label)

        self._uygula_stil()

    def _ust_panel(self) -> QWidget:
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 4)

        baslik = QLabel("Demir Hesaplama")
        baslik.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        baslik.setStyleSheet("color: #1a3a5c;")
        layout.addWidget(baslik)

        layout.addStretch()

        layout.addWidget(QLabel("Birim Fiyat (TL/ton):"))
        self.fiyat_input = QDoubleSpinBox()
        self.fiyat_input.setRange(1.0, 9_999_999.0)
        self.fiyat_input.setDecimals(0)
        self.fiyat_input.setSingleStep(1000.0)
        self.fiyat_input.setValue(VARSAYILAN_FIYAT_TON)
        self.fiyat_input.setGroupSeparatorShown(True)
        self.fiyat_input.setToolTip(
            "Guncel demir birim fiyatini TL/ton cinsinden girin"
        )
        self.fiyat_input.setFixedWidth(130)
        self.fiyat_input.valueChanged.connect(self._fiyat_degisti)
        layout.addWidget(self.fiyat_input)

        layout.addSpacing(16)

        yardim_btn = QPushButton("? Yardim")
        yardim_btn.setToolTip("Kullanim kilavuzunu goster")
        yardim_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        yardim_btn.clicked.connect(self._yardim_goster)
        layout.addWidget(yardim_btn)

        return panel

    # ------------------------------------------------------------------
    # Sekme 1: Temel Demir Hesabi
    # ------------------------------------------------------------------
    def _temel_hesap_sekmesi(self) -> QWidget:
        sekme = QWidget()
        dis_layout = QHBoxLayout(sekme)
        dis_layout.setContentsMargins(12, 12, 12, 12)
        dis_layout.setSpacing(16)

        # Sol: Giris formu
        giris_group = QGroupBox("Demir Ozellikleri")
        giris_group.setMinimumWidth(340)
        form = QFormLayout(giris_group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
        form.setContentsMargins(16, 20, 16, 16)

        self.cap_combo = QComboBox()
        for cap in sorted(DEMIR_BIRIM_AGIRLIK.keys()):
            self.cap_combo.addItem(f"O{cap} mm", cap)
        self.cap_combo.setCurrentIndex(2)  # O12 varsayilan
        self.cap_combo.currentIndexChanged.connect(self._cap_degisti)
        self.cap_combo.setToolTip("Demir capini secin")
        form.addRow("Cap:", self.cap_combo)

        self.birim_agirlik_label = QLabel()
        self.birim_agirlik_label.setStyleSheet(
            "font-weight: bold; color: #1a5276; background: #eaf4fb;"
            "border: 1px solid #aed6f1; border-radius: 3px; padding: 3px 8px;"
        )
        form.addRow("Birim Agirlik (kg/m):", self.birim_agirlik_label)

        self.boy_input = QDoubleSpinBox()
        self.boy_input.setRange(1.0, 99_999.0)
        self.boy_input.setDecimals(1)
        self.boy_input.setSuffix(" cm")
        self.boy_input.setValue(STANDART_BOY_CM)
        self.boy_input.setToolTip("Tek bir demir cubugunun uzunlugu (cm)")
        form.addRow("Boy:", self.boy_input)

        self.adet_input = QSpinBox()
        self.adet_input.setRange(1, 999_999)
        self.adet_input.setValue(1)
        self.adet_input.setToolTip("Kac adet demir")
        form.addRow("Adet:", self.adet_input)

        hesapla_btn = QPushButton("Hesapla")
        hesapla_btn.setObjectName("primaryBtn")
        hesapla_btn.setFixedHeight(38)
        hesapla_btn.setToolTip("Agirlik ve maliyet hesapla")
        hesapla_btn.clicked.connect(self._temel_hesapla)
        form.addRow("", hesapla_btn)

        dis_layout.addWidget(giris_group)

        # Sag: Sonuclar
        sonuc_group = QGroupBox("Hesap Sonuclari")
        sonuc_layout = QVBoxLayout(sonuc_group)
        sonuc_layout.setContentsMargins(16, 20, 16, 16)
        sonuc_layout.setSpacing(12)

        self.sonuc_grid = QGridLayout()
        self.sonuc_grid.setColumnStretch(1, 1)
        self.sonuc_grid.setVerticalSpacing(10)

        self._sonuc_satirlari = {}
        satir_tanimlari = [
            ("cap_goster",       "Secilen Cap",           "--"),
            ("boy_m",            "Boy (m)",                "--"),
            ("adet_goster",      "Adet",                   "--"),
            ("birim_agirlik",    "Birim Agirlik (kg/m)",   "--"),
            ("toplam_uzunluk",   "Toplam Uzunluk (m)",     "--"),
            ("toplam_agirlik",   "Toplam Agirlik (kg)",    "--"),
            ("toplam_ton",       "Toplam Agirlik (ton)",   "--"),
            ("yaklasik_maliyet", "Yaklasik Maliyet (TL)",  "--"),
        ]

        vurgulu = {"toplam_agirlik", "toplam_ton", "yaklasik_maliyet"}

        for i, (anahtar, etiket, varsayilan) in enumerate(satir_tanimlari):
            et_label = QLabel(etiket + ":")
            et_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            deger_label = QLabel(varsayilan)
            deger_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            if anahtar in vurgulu:
                deger_label.setStyleSheet(
                    "font-weight: bold; font-size: 14px; color: #1a5276;"
                    "background: #eaf4fb; border: 1px solid #aed6f1;"
                    "border-radius: 3px; padding: 2px 8px;"
                )
            else:
                deger_label.setStyleSheet(
                    "font-weight: bold; font-size: 13px;"
                )
            self.sonuc_grid.addWidget(et_label, i, 0)
            self.sonuc_grid.addWidget(deger_label, i, 1)
            self._sonuc_satirlari[anahtar] = deger_label

        sonuc_layout.addLayout(self.sonuc_grid)
        sonuc_layout.addStretch()

        not_frame = QFrame()
        not_frame.setStyleSheet(
            "background: #fef9e7; border: 1px solid #f9e79f; border-radius: 4px;"
        )
        not_layout = QVBoxLayout(not_frame)
        not_layout.setContentsMargins(10, 8, 10, 8)
        not_label = QLabel(
            "Not: Fire payi dahil degildir.\n"
            "Sahada %%3-5 fire eklemeniz onerilir."
        )
        not_label.setStyleSheet("color: #7d6608; font-size: 11px;")
        not_label.setWordWrap(True)
        not_layout.addWidget(not_label)
        sonuc_layout.addWidget(not_frame)

        dis_layout.addWidget(sonuc_group, stretch=1)

        # Cap degisti sinyali baslangicta tetikle
        self._cap_degisti()
        return sekme

    # ------------------------------------------------------------------
    # Sekme 2: Toplu Hesap
    # ------------------------------------------------------------------
    def _toplu_hesap_sekmesi(self) -> QWidget:
        sekme = QWidget()
        layout = QVBoxLayout(sekme)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        btn_layout = QHBoxLayout()

        ekle_btn = QPushButton("+ Satir Ekle")
        ekle_btn.setObjectName("primaryBtn")
        ekle_btn.setToolTip("Tabloya yeni demir kalemi ekle")
        ekle_btn.clicked.connect(self._toplu_satir_ekle)
        btn_layout.addWidget(ekle_btn)

        sil_btn = QPushButton("Secili Satiri Sil")
        sil_btn.setToolTip("Secili satiri tablodan kaldir")
        sil_btn.clicked.connect(self._toplu_satir_sil)
        btn_layout.addWidget(sil_btn)

        temizle_btn = QPushButton("Tabloyu Temizle")
        temizle_btn.setToolTip("Tum satirlari sil")
        temizle_btn.clicked.connect(self._toplu_temizle)
        btn_layout.addWidget(temizle_btn)

        btn_layout.addStretch()

        hesapla_btn = QPushButton("Toplam Hesapla")
        hesapla_btn.setObjectName("primaryBtn")
        hesapla_btn.setToolTip("Tum satirlarin agirligini ve maliyetini hesapla")
        hesapla_btn.clicked.connect(self._toplu_hesapla)
        btn_layout.addWidget(hesapla_btn)

        aktar_btn = QPushButton("CSV'ye Aktar")
        aktar_btn.setToolTip("Hesap sonuclarini CSV dosyasina kaydet")
        aktar_btn.clicked.connect(self._csv_aktar)
        btn_layout.addWidget(aktar_btn)

        layout.addLayout(btn_layout)

        # Sutunlar: Sira | Cap | Boy (cm) | Adet | Not | Uzunluk (m) | Agirlik (kg) | Maliyet (TL)
        self.toplu_tablo = QTableWidget(0, 8)
        self.toplu_tablo.setHorizontalHeaderLabels([
            "Sira", "Cap (mm)", "Boy (cm)", "Adet", "Not / Poz",
            "Uzunluk (m)", "Agirlik (kg)", "Maliyet (TL)"
        ])
        self.toplu_tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.toplu_tablo.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.toplu_tablo.setColumnWidth(0, 48)
        self.toplu_tablo.verticalHeader().setVisible(False)
        self.toplu_tablo.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.toplu_tablo.setAlternatingRowColors(True)
        self.toplu_tablo.setToolTip(
            "Cap, Boy ve Adet sutunlarina tiklayarak degerleri duzenleyin"
        )
        layout.addWidget(self.toplu_tablo, stretch=1)

        # Alt ozet panel
        ozet_frame = QFrame()
        ozet_frame.setStyleSheet(
            "background: #eaf4fb; border: 1px solid #aed6f1; border-radius: 4px;"
        )
        ozet_h = QHBoxLayout(ozet_frame)
        ozet_h.setContentsMargins(16, 8, 16, 8)
        ozet_h.setSpacing(32)

        self.toplu_toplam_uzunluk = self._ozet_cift("Toplam Uzunluk:", "-- m")
        self.toplu_toplam_agirlik = self._ozet_cift("Toplam Agirlik:", "-- kg")
        self.toplu_toplam_ton     = self._ozet_cift("Toplam (ton):",    "-- ton")
        self.toplu_toplam_maliyet = self._ozet_cift("Toplam Maliyet:", "-- TL")

        for baslik_l, deger_l in [
            self.toplu_toplam_uzunluk,
            self.toplu_toplam_agirlik,
            self.toplu_toplam_ton,
            self.toplu_toplam_maliyet,
        ]:
            ozet_h.addWidget(baslik_l)
            ozet_h.addWidget(deger_l)

        ozet_h.addStretch()
        layout.addWidget(ozet_frame)

        self._ornek_satirlar_ekle()
        return sekme

    def _ozet_cift(self, baslik: str, deger: str):
        b_label = QLabel(baslik)
        b_label.setStyleSheet("color: #1a3a5c; font-weight: bold;")
        d_label = QLabel(deger)
        d_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #154360; min-width: 100px;"
        )
        return b_label, d_label

    # ------------------------------------------------------------------
    # Sekme 3: Referans Birim Agirlik Tablosu
    # ------------------------------------------------------------------
    def _referans_tablo_sekmesi(self) -> QWidget:
        sekme = QWidget()
        layout = QVBoxLayout(sekme)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        aciklama = QLabel(
            "TS 708 standardina gore nervurlu celik cubuk (S420) birim agirlik tablosu.\n"
            "Formul: W (kg/m) = 0.006165 x d^2  (d = cap, mm)"
        )
        aciklama.setStyleSheet("color: #444; font-size: 12px;")
        aciklama.setWordWrap(True)
        layout.addWidget(aciklama)

        ref_tablo = QTableWidget(len(DEMIR_BIRIM_AGIRLIK), 4)
        ref_tablo.setHorizontalHeaderLabels([
            "Cap (mm)", "Birim Agirlik (kg/m)", "Kesit Alani (cm2)", "1 Ton = ? m"
        ])
        ref_tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        ref_tablo.verticalHeader().setVisible(False)
        ref_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        ref_tablo.setAlternatingRowColors(True)

        for satir, (cap, agirlik) in enumerate(sorted(DEMIR_BIRIM_AGIRLIK.items())):
            kesit = round(3.14159265 * (cap / 20.0) ** 2, 4)
            bin_kg_m = round(1000.0 / agirlik, 1)
            ref_tablo.setItem(satir, 0, _ReadOnlyItem(f"O{cap}"))
            ref_tablo.setItem(satir, 1, _ReadOnlyItem(f"{agirlik:.3f}"))
            ref_tablo.setItem(satir, 2, _ReadOnlyItem(f"{kesit:.4f}"))
            ref_tablo.setItem(satir, 3, _ReadOnlyItem(f"{bin_kg_m:.1f} m"))

        layout.addWidget(ref_tablo)

        kaynak = QLabel(
            "Kaynak: TS 708 — Betonarme Celikleri icin Nervurlu Celik Cubuklar standardi"
        )
        kaynak.setStyleSheet(
            "color: #888; font-size: 10px; font-style: italic;"
        )
        layout.addWidget(kaynak)
        return sekme

    # ------------------------------------------------------------------
    # Slotlar: Temel hesap
    # ------------------------------------------------------------------
    def _cap_degisti(self):
        cap = self.cap_combo.currentData()
        agirlik = DEMIR_BIRIM_AGIRLIK.get(cap, 0.0)
        self.birim_agirlik_label.setText(f"{agirlik:.3f} kg/m")

    def _temel_hesapla(self):
        cap = self.cap_combo.currentData()
        boy_cm = self.boy_input.value()
        adet = self.adet_input.value()
        birim_agirlik = DEMIR_BIRIM_AGIRLIK.get(cap, 0.0)
        boy_m = boy_cm / 100.0
        toplam_uzunluk_m = boy_m * adet
        toplam_agirlik_kg = toplam_uzunluk_m * birim_agirlik
        toplam_ton = toplam_agirlik_kg / 1000.0
        maliyet_tl = toplam_ton * self._birim_fiyat

        guncelleme = {
            "cap_goster":       f"O{cap} mm",
            "boy_m":            f"{boy_m:.2f} m",
            "adet_goster":      str(adet),
            "birim_agirlik":    f"{birim_agirlik:.3f} kg/m",
            "toplam_uzunluk":   f"{toplam_uzunluk_m:.2f} m",
            "toplam_agirlik":   f"{toplam_agirlik_kg:.2f} kg",
            "toplam_ton":       f"{toplam_ton:.4f} ton",
            "yaklasik_maliyet": f"{maliyet_tl:.2f} TL",
        }

        for anahtar, metin in guncelleme.items():
            self._sonuc_satirlari[anahtar].setText(metin)

        self.durum_label.setText(
            f"Temel hesap tamamlandi -- "
            f"O{cap} x {adet} adet x {boy_cm} cm = {toplam_agirlik_kg:.2f} kg"
        )

        sonuc = {
            "cap_mm": cap,
            "boy_cm": boy_cm,
            "adet": adet,
            "birim_agirlik_kg_m": birim_agirlik,
            "toplam_uzunluk_m": toplam_uzunluk_m,
            "toplam_agirlik_kg": toplam_agirlik_kg,
            "toplam_ton": toplam_ton,
            "maliyet_tl": maliyet_tl,
        }
        self.hesaplama_tamamlandi.emit(sonuc)
        logger.info(
            "Temel demir hesap: cap=%d boy=%.1fcm adet=%d agirlik=%.2fkg maliyet=%.2fTL",
            cap, boy_cm, adet, toplam_agirlik_kg, maliyet_tl
        )

    # ------------------------------------------------------------------
    # Slotlar: Toplu hesap
    # ------------------------------------------------------------------
    def _toplu_satir_ekle(self):
        satir = self.toplu_tablo.rowCount()
        self.toplu_tablo.insertRow(satir)

        self.toplu_tablo.setItem(satir, 0, _ReadOnlyItem(str(satir + 1)))

        cap_combo = QComboBox()
        for cap_d in sorted(DEMIR_BIRIM_AGIRLIK.keys()):
            cap_combo.addItem(f"O{cap_d}", cap_d)
        cap_combo.setCurrentIndex(2)  # Varsayilan O12
        self.toplu_tablo.setCellWidget(satir, 1, cap_combo)

        boy_item = QTableWidgetItem("1200")
        boy_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toplu_tablo.setItem(satir, 2, boy_item)

        adet_item = QTableWidgetItem("1")
        adet_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toplu_tablo.setItem(satir, 3, adet_item)

        self.toplu_tablo.setItem(satir, 4, QTableWidgetItem(""))

        for kolon in (5, 6, 7):
            self.toplu_tablo.setItem(satir, kolon, _ReadOnlyItem("--"))

        self.toplu_tablo.scrollToBottom()
        self.durum_label.setText(
            f"{satir + 1}. satir eklendi. 'Toplam Hesapla' butonuna basin."
        )

    def _toplu_satir_sil(self):
        secili = self.toplu_tablo.currentRow()
        if secili < 0:
            QMessageBox.information(
                self, "Bilgi", "Silmek icin once bir satir secin."
            )
            return
        self.toplu_tablo.removeRow(secili)
        for i in range(self.toplu_tablo.rowCount()):
            item = self.toplu_tablo.item(i, 0)
            if item:
                item.setText(str(i + 1))
        self.durum_label.setText("Satir silindi.")

    def _toplu_temizle(self):
        cevap = QMessageBox.question(
            self, "Onay",
            "Tablodaki tum satirlar silinecek. Devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if cevap == QMessageBox.StandardButton.Yes:
            self.toplu_tablo.setRowCount(0)
            self._ozet_sifirla()
            self.durum_label.setText("Tablo temizlendi.")

    def _toplu_hesapla(self):
        toplam_uzunluk = 0.0
        toplam_agirlik = 0.0
        hatali_satirlar = []

        for satir in range(self.toplu_tablo.rowCount()):
            try:
                cap_widget = self.toplu_tablo.cellWidget(satir, 1)
                if cap_widget is None:
                    raise ValueError("Cap widget bulunamadi")
                cap = cap_widget.currentData()

                boy_item = self.toplu_tablo.item(satir, 2)
                boy_cm = (
                    float(boy_item.text().replace(",", "."))
                    if boy_item else 0.0
                )

                adet_item = self.toplu_tablo.item(satir, 3)
                adet = (
                    int(float(adet_item.text().replace(",", ".")))
                    if adet_item else 0
                )

                if boy_cm <= 0 or adet <= 0:
                    raise ValueError(
                        f"Satir {satir + 1}: Boy veya adet sifir/negatif"
                    )

                birim_ag = DEMIR_BIRIM_AGIRLIK.get(cap, 0.0)
                boy_m = boy_cm / 100.0
                uzunluk = boy_m * adet
                agirlik = uzunluk * birim_ag
                maliyet = (agirlik / 1000.0) * self._birim_fiyat

                toplam_uzunluk += uzunluk
                toplam_agirlik += agirlik

                self.toplu_tablo.setItem(
                    satir, 5, _ReadOnlyItem(f"{uzunluk:.2f}")
                )
                self.toplu_tablo.setItem(
                    satir, 6, _ReadOnlyItem(f"{agirlik:.3f}")
                )
                self.toplu_tablo.setItem(
                    satir, 7, _ReadOnlyItem(f"{maliyet:.2f}")
                )

                renk = (
                    QColor("#d5f5e3") if agirlik > 500
                    else QColor("#ffffff")
                )
                for k in range(8):
                    item = self.toplu_tablo.item(satir, k)
                    if item:
                        item.setBackground(renk)

            except (ValueError, AttributeError, TypeError) as hata:
                hatali_satirlar.append(satir + 1)
                logger.warning(
                    "Toplu hesap satir %d hatasi: %s", satir + 1, hata
                )

        toplam_ton = toplam_agirlik / 1000.0
        toplam_maliyet = toplam_ton * self._birim_fiyat

        _, ul_deger = self.toplu_toplam_uzunluk
        _, ag_deger = self.toplu_toplam_agirlik
        _, ton_deger = self.toplu_toplam_ton
        _, mal_deger = self.toplu_toplam_maliyet

        ul_deger.setText(f"{toplam_uzunluk:.2f} m")
        ag_deger.setText(f"{toplam_agirlik:.3f} kg")
        ton_deger.setText(f"{toplam_ton:.4f} ton")
        mal_deger.setText(f"{toplam_maliyet:.2f} TL")

        durum = (
            f"Toplu hesap tamamlandi -- "
            f"{self.toplu_tablo.rowCount()} kalem, "
            f"{toplam_agirlik:.2f} kg, "
            f"{toplam_maliyet:.2f} TL"
        )
        if hatali_satirlar:
            durum += f"  Hatali satirlar: {hatali_satirlar}"
        self.durum_label.setText(durum)

        sonuc = {
            "toplam_uzunluk_m": toplam_uzunluk,
            "toplam_agirlik_kg": toplam_agirlik,
            "toplam_ton": toplam_ton,
            "maliyet_tl": toplam_maliyet,
        }
        self.hesaplama_tamamlandi.emit(sonuc)
        logger.info(
            "Toplu hesap: %d satir, %.2f kg, %.2f TL",
            self.toplu_tablo.rowCount(), toplam_agirlik, toplam_maliyet
        )

    def _ozet_sifirla(self):
        for _, deger_l in [
            self.toplu_toplam_uzunluk,
            self.toplu_toplam_agirlik,
            self.toplu_toplam_ton,
            self.toplu_toplam_maliyet,
        ]:
            deger_l.setText("--")

    def _ornek_satirlar_ekle(self):
        ornekler = [
            (12, 1200, 50),
            (16, 600,  30),
            (10, 300,  20),
        ]
        for cap_d, boy, adet in ornekler:
            self._toplu_satir_ekle()
            son_satir = self.toplu_tablo.rowCount() - 1
            cap_widget = self.toplu_tablo.cellWidget(son_satir, 1)
            for idx in range(cap_widget.count()):
                if cap_widget.itemData(idx) == cap_d:
                    cap_widget.setCurrentIndex(idx)
                    break
            self.toplu_tablo.item(son_satir, 2).setText(str(boy))
            self.toplu_tablo.item(son_satir, 3).setText(str(adet))

    # ------------------------------------------------------------------
    # Sekme 4: Kesim Listesi
    # ------------------------------------------------------------------
    def _kesim_listesi_sekmesi(self) -> QWidget:
        sekme = QWidget()
        layout = QVBoxLayout(sekme)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # --- Ust buton bari: TEK satirda 9 kontrol sigmadigi icin (dar
        # pencerede metinler klipleniyordu, bkz. CLAUDE.md Rev-120) iki
        # satira bolundu: 1) satir islemleri, 2) ayarlar + hesapla/aktar ---
        satir_bar = QHBoxLayout()

        aktar_btn = QPushButton("↓ Toplu Hesap'tan Aktar")
        aktar_btn.setObjectName("primaryBtn")
        aktar_btn.setToolTip("Toplu Hesap tablosundaki kalemleri buraya aktar")
        aktar_btn.clicked.connect(self._kesim_aktar)
        satir_bar.addWidget(aktar_btn)

        ekle_btn = QPushButton("+ Satir Ekle")
        ekle_btn.setToolTip("Yeni parca kalemi ekle")
        ekle_btn.clicked.connect(self._kesim_satir_ekle)
        satir_bar.addWidget(ekle_btn)

        sil_btn = QPushButton("Secili Sil")
        sil_btn.setToolTip("Secili satiri sil")
        sil_btn.clicked.connect(self._kesim_satir_sil)
        satir_bar.addWidget(sil_btn)

        temizle_btn = QPushButton("Temizle")
        temizle_btn.setToolTip("Tum girdi satirlarini temizle")
        temizle_btn.clicked.connect(self._kesim_temizle)
        satir_bar.addWidget(temizle_btn)

        satir_bar.addStretch()
        layout.addLayout(satir_bar)

        ayar_bar = QHBoxLayout()

        ayar_bar.addWidget(QLabel("Standart Cubuk Boyu:"))
        self.kesim_standart_boy = QSpinBox()
        self.kesim_standart_boy.setRange(100, 1800)
        self.kesim_standart_boy.setValue(STANDART_BOY_CM)
        self.kesim_standart_boy.setSuffix(" cm")
        self.kesim_standart_boy.setFixedWidth(100)
        self.kesim_standart_boy.setToolTip(
            "Piyasadan alinan standart cubuk boyu (cm). Varsayilan: 1200 cm = 12 m"
        )
        ayar_bar.addWidget(self.kesim_standart_boy)

        ayar_bar.addSpacing(12)

        ayar_bar.addWidget(QLabel("Kullanilabilir Artik Esigi:"))
        self.kesim_artik_esigi = QSpinBox()
        self.kesim_artik_esigi.setRange(0, 200)
        self.kesim_artik_esigi.setValue(50)
        self.kesim_artik_esigi.setSuffix(" cm")
        self.kesim_artik_esigi.setFixedWidth(100)
        self.kesim_artik_esigi.setToolTip(
            "Bu deger VE USTUNDEKI artiklar 'kullanilabilir' (saklanir) sayilir, "
            "ALTINDAKILER 'cop fire' sayilir. Proje bazinda ayarlanabilir."
        )
        ayar_bar.addWidget(self.kesim_artik_esigi)

        ayar_bar.addStretch()

        hesapla_btn = QPushButton("Kesim Plani Hesapla")
        hesapla_btn.setObjectName("primaryBtn")
        hesapla_btn.setFixedHeight(34)
        hesapla_btn.setToolTip("Minimum fire algoritmasiyla kesim planini olustur")
        hesapla_btn.clicked.connect(self._kesim_hesapla)
        ayar_bar.addWidget(hesapla_btn)

        csv_btn = QPushButton("CSV Aktar")
        csv_btn.setToolTip("Kesim planini CSV olarak kaydet")
        csv_btn.clicked.connect(self._kesim_csv_aktar)
        ayar_bar.addWidget(csv_btn)

        layout.addLayout(ayar_bar)

        # --- Girdi tablosu ---
        giris_label = QLabel("Kesilecek Parcalar:")
        giris_label.setStyleSheet("font-weight: bold; color: #1a3a5c;")
        layout.addWidget(giris_label)

        self.kesim_girdi_tablo = QTableWidget(0, 4)
        self.kesim_girdi_tablo.setHorizontalHeaderLabels([
            "Cap (mm)", "Boy (cm)", "Adet", "Not / Poz"
        ])
        self.kesim_girdi_tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.kesim_girdi_tablo.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.kesim_girdi_tablo.setColumnWidth(0, 90)
        self.kesim_girdi_tablo.verticalHeader().setVisible(False)
        self.kesim_girdi_tablo.setAlternatingRowColors(True)
        self.kesim_girdi_tablo.setMaximumHeight(180)
        layout.addWidget(self.kesim_girdi_tablo)

        # --- Standart-disi parca uyari bari (Rev-124) ---
        self.kesim_uyari_label = QLabel("")
        self.kesim_uyari_label.setWordWrap(True)
        self.kesim_uyari_label.setStyleSheet(
            "background: #fdecea; color: #922b21; border: 1px solid #e6b0aa; "
            "border-radius: 4px; padding: 8px; font-weight: bold;"
        )
        self.kesim_uyari_label.setVisible(False)
        layout.addWidget(self.kesim_uyari_label)

        # --- Sonuc alt sekmeleri ---
        self.kesim_sonuc_tabs = QTabWidget()
        self.kesim_sonuc_tabs.setDocumentMode(True)

        # -- Kesim Plani sekmesi --
        plan_widget = QWidget()
        plan_layout = QVBoxLayout(plan_widget)
        plan_layout.setContentsMargins(4, 4, 4, 4)

        plan_aciklama = QLabel(
            "Ayni kesim desenine (parca kombinasyonuna) sahip cubuklar tek satirda "
            "gruplanir. 'Durum': artik esigin USTUNDEYSE SAKLA (kullanilabilir), "
            "ALTINDAYSA cop fire. Kirmizi 'STANDART DISI' satirlar, standart cubuk "
            "boyunu asan ve TEK cubuktan kesilemeyen parcalari gosterir — bunlar "
            "birden fazla cubuk + TS 500 bindirme eki ile sahada birlestirilmelidir."
        )
        plan_aciklama.setStyleSheet("color: #666; font-size: 11px;")
        plan_aciklama.setWordWrap(True)
        plan_layout.addWidget(plan_aciklama)

        self.kesim_plan_tablo = QTableWidget(0, 8)
        self.kesim_plan_tablo.setHorizontalHeaderLabels([
            "Desen No", "Cap (mm)", "Kesilen Parcalar (cm)", "Cubuk Adedi",
            "Kullanilan (cm)", "Artik (cm)", "Artik %", "Durum"
        ])
        self.kesim_plan_tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        for col in (0, 1, 3, 4, 5, 6, 7):
            self.kesim_plan_tablo.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.Fixed
            )
        self.kesim_plan_tablo.setColumnWidth(0, 72)
        self.kesim_plan_tablo.setColumnWidth(1, 72)
        self.kesim_plan_tablo.setColumnWidth(3, 88)
        self.kesim_plan_tablo.setColumnWidth(4, 100)
        self.kesim_plan_tablo.setColumnWidth(5, 80)
        self.kesim_plan_tablo.setColumnWidth(6, 64)
        self.kesim_plan_tablo.setColumnWidth(7, 80)
        self.kesim_plan_tablo.verticalHeader().setVisible(False)
        self.kesim_plan_tablo.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.kesim_plan_tablo.setAlternatingRowColors(True)
        plan_layout.addWidget(self.kesim_plan_tablo)
        self.kesim_sonuc_tabs.addTab(plan_widget, "  Kesim Plani  ")

        # -- Siparis Formu sekmesi --
        siparis_widget = QWidget()
        siparis_layout = QVBoxLayout(siparis_widget)
        siparis_layout.setContentsMargins(4, 4, 4, 4)

        siparis_aciklama = QLabel(
            "Cap bazinda siparis edilmesi gereken cubuk adedi, agirlik ve maliyet ozeti."
        )
        siparis_aciklama.setStyleSheet("color: #666; font-size: 11px;")
        siparis_layout.addWidget(siparis_aciklama)

        self.siparis_tablo = QTableWidget(0, 9)
        self.siparis_tablo.setHorizontalHeaderLabels([
            "Cap (mm)", "Parca Sayisi", "Cubuk Adedi",
            "Kullanilabilir Artik (m)", "Cop Fire (m)",
            "Toplam Fire (cm)", "Fire %",
            "Siparis (kg)", "Siparis (ton)"
        ])
        self.siparis_tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.siparis_tablo.verticalHeader().setVisible(False)
        self.siparis_tablo.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.siparis_tablo.setAlternatingRowColors(True)
        siparis_layout.addWidget(self.siparis_tablo)
        self.kesim_sonuc_tabs.addTab(siparis_widget, "  Siparis Formu  ")

        layout.addWidget(self.kesim_sonuc_tabs, stretch=1)

        # --- Alt ozet bari ---
        ozet_frame = QFrame()
        ozet_frame.setStyleSheet(
            "background: #eaf4fb; border: 1px solid #aed6f1; border-radius: 4px;"
        )
        ozet_h = QHBoxLayout(ozet_frame)
        ozet_h.setContentsMargins(16, 8, 16, 8)
        ozet_h.setSpacing(32)

        self.kesim_ozet_toplam_cubuk = self._ozet_cift("Toplam Cubuk:", "--")
        self.kesim_ozet_kullanilabilir_artik = self._ozet_cift("Kullanilabilir Artik:", "--")
        self.kesim_ozet_cop_fire     = self._ozet_cift("Cop Fire:", "--")
        self.kesim_ozet_fire_yuzde   = self._ozet_cift("Ortalama Fire %:", "--")
        self.kesim_ozet_toplam_kg    = self._ozet_cift("Siparis (kg):", "--")
        self.kesim_ozet_toplam_ton   = self._ozet_cift("Siparis (ton):", "--")
        self.kesim_ozet_maliyet      = self._ozet_cift("Tahmini Maliyet:", "--")

        for baslik_l, deger_l in [
            self.kesim_ozet_toplam_cubuk,
            self.kesim_ozet_kullanilabilir_artik,
            self.kesim_ozet_cop_fire,
            self.kesim_ozet_fire_yuzde,
            self.kesim_ozet_toplam_kg,
            self.kesim_ozet_toplam_ton,
            self.kesim_ozet_maliyet,
        ]:
            ozet_h.addWidget(baslik_l)
            ozet_h.addWidget(deger_l)

        ozet_h.addStretch()
        layout.addWidget(ozet_frame)

        return sekme

    # ------------------------------------------------------------------
    # Slotlar: Kesim Listesi
    # ------------------------------------------------------------------
    def _kesim_aktar(self):
        """Toplu Hesap tablosundaki kalemleri Kesim Listesi giris tablosuna aktar."""
        kaynak = self.toplu_tablo
        if kaynak.rowCount() == 0:
            QMessageBox.information(
                self, "Bilgi",
                "Toplu Hesap sekmesinde oncelikle demir kalemleri ekleyin."
            )
            return

        self.kesim_girdi_tablo.setRowCount(0)
        aktarilan = 0
        for satir in range(kaynak.rowCount()):
            cap_widget = kaynak.cellWidget(satir, 1)
            boy_item   = kaynak.item(satir, 2)
            adet_item  = kaynak.item(satir, 3)
            not_item   = kaynak.item(satir, 4)

            if cap_widget is None or boy_item is None or adet_item is None:
                continue
            try:
                cap  = cap_widget.currentData()
                boy  = float(boy_item.text().replace(",", "."))
                adet = int(float(adet_item.text().replace(",", ".")))
                not_str = not_item.text() if not_item else ""
            except (ValueError, AttributeError):
                continue

            self._kesim_satir_ekle_deger(cap, boy, adet, not_str)
            aktarilan += 1

        self.durum_label.setText(
            f"Kesim Listesi: {aktarilan} kalem aktarildi. "
            "'Kesim Plani Hesapla' butonuna basin."
        )

    def _kesim_satir_ekle(self):
        self._kesim_satir_ekle_deger(12, 1200.0, 1, "")

    def _kesim_satir_ekle_deger(self, cap_d: int, boy: float, adet: int, not_str: str):
        satir = self.kesim_girdi_tablo.rowCount()
        self.kesim_girdi_tablo.insertRow(satir)

        cap_combo = QComboBox()
        for c in sorted(DEMIR_BIRIM_AGIRLIK.keys()):
            cap_combo.addItem(f"O{c}", c)
        for idx in range(cap_combo.count()):
            if cap_combo.itemData(idx) == cap_d:
                cap_combo.setCurrentIndex(idx)
                break
        self.kesim_girdi_tablo.setCellWidget(satir, 0, cap_combo)

        boy_item = QTableWidgetItem(str(int(boy) if boy == int(boy) else boy))
        boy_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.kesim_girdi_tablo.setItem(satir, 1, boy_item)

        adet_item = QTableWidgetItem(str(adet))
        adet_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.kesim_girdi_tablo.setItem(satir, 2, adet_item)

        self.kesim_girdi_tablo.setItem(satir, 3, QTableWidgetItem(not_str))

    def _kesim_satir_sil(self):
        secili = self.kesim_girdi_tablo.currentRow()
        if secili < 0:
            QMessageBox.information(self, "Bilgi", "Silmek icin bir satir secin.")
            return
        self.kesim_girdi_tablo.removeRow(secili)

    def _kesim_temizle(self):
        self.kesim_girdi_tablo.setRowCount(0)
        self.kesim_plan_tablo.setRowCount(0)
        self.siparis_tablo.setRowCount(0)
        self.kesim_uyari_label.setVisible(False)
        self.kesim_uyari_label.setText("")
        for _, d in [
            self.kesim_ozet_toplam_cubuk,        self.kesim_ozet_kullanilabilir_artik,
            self.kesim_ozet_cop_fire,            self.kesim_ozet_fire_yuzde,
            self.kesim_ozet_toplam_kg,            self.kesim_ozet_toplam_ton,
            self.kesim_ozet_maliyet,
        ]:
            d.setText("--")
        self.durum_label.setText("Kesim Listesi temizlendi.")

    def _ffd_algoritma(self, boylar: list, standart_boy: float) -> list:
        """
        First Fit Decreasing algoritmasiyla kesim plani olusturur.
        Donus: [[parca_boy, ...], ...]  — her alt liste bir cubugun kesimlerini gosterir.
        """
        sirali = sorted(boylar, reverse=True)
        cubuklar: list = []
        for parca in sirali:
            if parca > standart_boy:
                # Standart boyu asan parca — tek cubuk, fire olmaz (kesim yapilamaz)
                cubuklar.append([parca])
                continue
            yerlestirildi = False
            for cubuk in cubuklar:
                kalan = standart_boy - sum(cubuk)
                if kalan >= parca:
                    cubuk.append(parca)
                    yerlestirildi = True
                    break
            if not yerlestirildi:
                cubuklar.append([parca])
        return cubuklar

    def _kesim_hesapla(self):
        girdi = self.kesim_girdi_tablo
        if girdi.rowCount() == 0:
            QMessageBox.information(
                self, "Bilgi", "Once kesilecek parcelari ekleyin."
            )
            return

        standart_boy = float(self.kesim_standart_boy.value())
        esik_cm = float(self.kesim_artik_esigi.value())

        # Cap bazinda parcelari grupla
        cap_parcalari: dict = {}  # {cap: [boy, boy, ...]}
        for satir in range(girdi.rowCount()):
            cap_widget = girdi.cellWidget(satir, 0)
            boy_item   = girdi.item(satir, 1)
            adet_item  = girdi.item(satir, 2)
            if cap_widget is None:
                continue
            try:
                cap  = cap_widget.currentData()
                boy  = float(boy_item.text().replace(",", ".")) if boy_item else 0.0
                adet = int(float(adet_item.text().replace(",", "."))) if adet_item else 0
            except (ValueError, AttributeError):
                continue
            if boy <= 0 or adet <= 0:
                continue
            cap_parcalari.setdefault(cap, []).extend([boy] * adet)

        if not cap_parcalari:
            QMessageBox.warning(self, "Uyari", "Gecerli parca bulunamadi.")
            return

        try:
            cap_sonuclari = coklu_cap_kesim_plani_hesapla(cap_parcalari, standart_boy, esik_cm)
        except ValueError as e:
            QMessageBox.warning(self, "Uyari", str(e))
            return

        # Hesapla ve tablolari doldur
        self.kesim_plan_tablo.setRowCount(0)
        self.siparis_tablo.setRowCount(0)

        genel_cubuk = 0
        genel_kullanilabilir_artik_cm = 0.0
        genel_cop_fire_cm = 0.0
        genel_siparis_kg = 0.0
        genel_standart_disi_adet = 0
        genel_standart_disi_detay: list = []   # ["O12: 400cm", ...]

        desen_no_sayac = 1
        yuksek_fire_renk    = QColor("#ffe0cc")   # >%15 artik — turuncu
        dusuk_fire_renk     = QColor("#d5f5e3")   # <%5 artik — yesil
        saklanabilir_renk   = QColor("#d6eaf8")   # kullanilabilir artik — mavi
        standart_disi_renk  = QColor("#f5b7b1")   # standart boyu asan parca — kirmizi
        normal_renk         = QColor("#ffffff")

        for cap in sorted(cap_sonuclari.keys()):
            sonuc = cap_sonuclari[cap]

            birim_ag = DEMIR_BIRIM_AGIRLIK.get(cap, 0.0)
            siparis_kg  = (standart_boy / 100.0) * birim_ag * sonuc.cubuk_adedi
            siparis_ton = siparis_kg / 1000.0

            genel_cubuk                   += sonuc.cubuk_adedi
            genel_kullanilabilir_artik_cm += sonuc.kullanilabilir_artik_cm
            genel_cop_fire_cm             += sonuc.cop_fire_cm
            genel_siparis_kg              += siparis_kg
            genel_standart_disi_adet      += sonuc.standart_disi_adet
            for boy in sonuc.standart_disi_boylar:
                genel_standart_disi_detay.append(
                    f"O{cap}: {boy:.0f}cm ({boy / standart_boy:.1f}x standart)"
                )

            # Kesim Plani tablosunu DESEN bazinda doldur (ayni desen -> tek satir)
            for desen in sonuc.desenler:
                f_yuzde = (desen.artik_cm / standart_boy * 100.0) if standart_boy > 0 else 0.0
                parcalar_str = " + ".join(
                    f"{int(p) if p == int(p) else p}" for p in desen.desen
                )
                if desen.standart_disi:
                    durum_str = "⚠ STANDART DISI"
                else:
                    durum_str = "SAKLA" if desen.kullanilabilir_mi else "cop"

                plan_satir = self.kesim_plan_tablo.rowCount()
                self.kesim_plan_tablo.insertRow(plan_satir)

                self.kesim_plan_tablo.setItem(plan_satir, 0, _ReadOnlyItem(str(desen_no_sayac)))
                self.kesim_plan_tablo.setItem(plan_satir, 1, _ReadOnlyItem(f"O{cap}"))
                self.kesim_plan_tablo.setItem(plan_satir, 2, _ReadOnlyItem(parcalar_str))
                self.kesim_plan_tablo.setItem(plan_satir, 3, _ReadOnlyItem(str(desen.adet)))
                if desen.standart_disi:
                    # "Kullanilan"/"Artik" kavrami gecersiz - tek cubuktan kesilemedi.
                    # Gercek parca boyunu goster, artik/yuzde alanlarina "-" koy.
                    self.kesim_plan_tablo.setItem(
                        plan_satir, 4, _ReadOnlyItem(f"{desen.desen[0]:.0f}")
                    )
                    self.kesim_plan_tablo.setItem(plan_satir, 5, _ReadOnlyItem("-"))
                    self.kesim_plan_tablo.setItem(plan_satir, 6, _ReadOnlyItem("-"))
                else:
                    self.kesim_plan_tablo.setItem(
                        plan_satir, 4, _ReadOnlyItem(f"{standart_boy - desen.artik_cm:.0f}")
                    )
                    self.kesim_plan_tablo.setItem(plan_satir, 5, _ReadOnlyItem(f"{desen.artik_cm:.0f}"))
                    self.kesim_plan_tablo.setItem(plan_satir, 6, _ReadOnlyItem(f"{f_yuzde:.1f}%"))
                self.kesim_plan_tablo.setItem(plan_satir, 7, _ReadOnlyItem(durum_str))

                if desen.standart_disi:
                    renk = standart_disi_renk
                elif desen.kullanilabilir_mi:
                    renk = saklanabilir_renk
                elif f_yuzde > 15:
                    renk = yuksek_fire_renk
                elif f_yuzde < 5:
                    renk = dusuk_fire_renk
                else:
                    renk = normal_renk

                for k in range(8):
                    item = self.kesim_plan_tablo.item(plan_satir, k)
                    if item:
                        item.setBackground(renk)

                desen_no_sayac += 1

            # Siparis tablosunu doldur
            sp_satir = self.siparis_tablo.rowCount()
            self.siparis_tablo.insertRow(sp_satir)
            self.siparis_tablo.setItem(sp_satir, 0, _ReadOnlyItem(f"O{cap}"))
            self.siparis_tablo.setItem(sp_satir, 1, _ReadOnlyItem(str(sonuc.parca_sayisi)))
            self.siparis_tablo.setItem(sp_satir, 2, _ReadOnlyItem(str(sonuc.cubuk_adedi)))
            self.siparis_tablo.setItem(
                sp_satir, 3, _ReadOnlyItem(f"{sonuc.kullanilabilir_artik_cm / 100.0:.2f}")
            )
            self.siparis_tablo.setItem(
                sp_satir, 4, _ReadOnlyItem(f"{sonuc.cop_fire_cm / 100.0:.2f}")
            )
            self.siparis_tablo.setItem(sp_satir, 5, _ReadOnlyItem(f"{sonuc.toplam_fire_cm:.0f} cm"))
            self.siparis_tablo.setItem(sp_satir, 6, _ReadOnlyItem(f"{sonuc.fire_yuzde:.1f}%"))
            self.siparis_tablo.setItem(sp_satir, 7, _ReadOnlyItem(f"{siparis_kg:.2f}"))
            self.siparis_tablo.setItem(sp_satir, 8, _ReadOnlyItem(f"{siparis_ton:.4f}"))

            if sonuc.fire_yuzde > 15:
                for k in range(9):
                    item = self.siparis_tablo.item(sp_satir, k)
                    if item:
                        item.setBackground(yuksek_fire_renk)

        # Ozet guncelle
        genel_toplam_fire_cm = genel_kullanilabilir_artik_cm + genel_cop_fire_cm
        genel_kapasite = standart_boy * genel_cubuk
        genel_fire_yuzde = (
            genel_toplam_fire_cm / genel_kapasite * 100.0
        ) if genel_kapasite > 0 else 0.0
        genel_ton = genel_siparis_kg / 1000.0
        maliyet = genel_ton * self._birim_fiyat

        _, d = self.kesim_ozet_toplam_cubuk;         d.setText(f"{genel_cubuk} adet")
        _, d = self.kesim_ozet_kullanilabilir_artik;  d.setText(f"{genel_kullanilabilir_artik_cm / 100.0:.2f} m")
        _, d = self.kesim_ozet_cop_fire;              d.setText(f"{genel_cop_fire_cm / 100.0:.2f} m")
        _, d = self.kesim_ozet_fire_yuzde;            d.setText(f"{genel_fire_yuzde:.1f}%")
        _, d = self.kesim_ozet_toplam_kg;             d.setText(f"{genel_siparis_kg:.2f} kg")
        _, d = self.kesim_ozet_toplam_ton;            d.setText(f"{genel_ton:.4f} ton")
        _, d = self.kesim_ozet_maliyet;               d.setText(f"{maliyet:.2f} TL")

        # Standart-disi parca uyarisi (Rev-124) — sahada TEK cubuktan
        # kesilemeyen, birden fazla cubuk + TS 500 bindirme eki gerektiren
        # parcalar. "cop fire" ile KARISTIRILMAMALI, ayri ve belirgin uyari.
        if genel_standart_disi_adet > 0:
            ornekler = ", ".join(genel_standart_disi_detay[:5])
            fazla = len(genel_standart_disi_detay) - 5
            if fazla > 0:
                ornekler += f" (+{fazla} farkli boy daha)"
            self.kesim_uyari_label.setText(
                f"⚠️ {genel_standart_disi_adet} adet parca standart cubuk boyunu "
                f"({standart_boy:.0f} cm) asiyor — SAHADA TEK cubuktan kesilemez, "
                f"birden fazla cubuk + TS 500 bindirme eki ile birlestirilmelidir. "
                f"Kesim Plani tablosunda kirmizi renkli 'STANDART DISI' satirlar "
                f"bu parcalari gosterir. Ornekler: {ornekler}. "
                f"Bu parcalar siparis (kg/ton) hesabina standart boy uzerinden "
                f"dahil edildi — bindirme fazlasi icin manuel kontrol/ek miktar gerekir."
            )
            self.kesim_uyari_label.setVisible(True)
            logger.warning(
                "Kesim plani: %d adet standart-disi parca tespit edildi (esik: %.0fcm) - %s",
                genel_standart_disi_adet, standart_boy, ornekler
            )
        else:
            self.kesim_uyari_label.setVisible(False)
            self.kesim_uyari_label.setText("")

        # Sonuc sekmesini Kesim Plani'na al
        self.kesim_sonuc_tabs.setCurrentIndex(0)

        self.durum_label.setText(
            f"Kesim plani olusturuldu: {genel_cubuk} cubuk, "
            f"kullanilabilir artik={genel_kullanilabilir_artik_cm / 100.0:.2f}m, "
            f"cop fire={genel_cop_fire_cm / 100.0:.2f}m, "
            f"siparis={genel_ton:.3f} ton"
            + (f", ⚠ {genel_standart_disi_adet} standart-disi parca" if genel_standart_disi_adet > 0 else "")
        )
        logger.info(
            "Kesim plani: %d cubuk, kullanilabilir_artik=%.2fm, cop_fire=%.2fm, %.3f ton, standart_disi=%d",
            genel_cubuk, genel_kullanilabilir_artik_cm / 100.0,
            genel_cop_fire_cm / 100.0, genel_ton, genel_standart_disi_adet
        )

    def _kesim_csv_aktar(self):
        try:
            from PyQt6.QtWidgets import QFileDialog
            import csv
            import datetime

            dosya_yolu, _ = QFileDialog.getSaveFileName(
                self, "Kesim Listesi CSV Kaydet", "",
                "CSV Dosyasi (*.csv);;Tum Dosyalar (*)"
            )
            if not dosya_yolu:
                return

            with open(dosya_yolu, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["INSAAT METRAJ PRO -- Demir Kesim Listesi"])
                w.writerow(["Tarih:", datetime.date.today().strftime("%d/%m/%Y")])
                w.writerow(["Standart Cubuk Boyu (cm):", self.kesim_standart_boy.value()])
                w.writerow(["Kullanilabilir Artik Esigi (cm):", self.kesim_artik_esigi.value()])
                if self.kesim_uyari_label.isVisible():
                    w.writerow([])
                    w.writerow(["UYARI:", self.kesim_uyari_label.text()])
                w.writerow([])

                w.writerow(["=== KESIM PLANI (Desen Bazinda) ==="])
                w.writerow([
                    "Desen No", "Cap (mm)", "Kesilen Parcalar (cm)", "Cubuk Adedi",
                    "Kullanilan (cm)", "Artik (cm)", "Artik %", "Durum"
                ])
                for satir in range(self.kesim_plan_tablo.rowCount()):
                    satir_v = []
                    for k in range(8):
                        item = self.kesim_plan_tablo.item(satir, k)
                        satir_v.append(item.text() if item else "")
                    w.writerow(satir_v)

                w.writerow([])
                w.writerow(["=== SIPARIS FORMU ==="])
                w.writerow([
                    "Cap (mm)", "Parca Sayisi", "Cubuk Adedi",
                    "Kullanilabilir Artik (m)", "Cop Fire (m)",
                    "Toplam Fire (cm)", "Fire %", "Siparis (kg)", "Siparis (ton)"
                ])
                for satir in range(self.siparis_tablo.rowCount()):
                    satir_v = []
                    for k in range(9):
                        item = self.siparis_tablo.item(satir, k)
                        satir_v.append(item.text() if item else "")
                    w.writerow(satir_v)

                w.writerow([])
                _, d = self.kesim_ozet_toplam_cubuk
                w.writerow(["Toplam Cubuk:", d.text()])
                _, d = self.kesim_ozet_kullanilabilir_artik
                w.writerow(["Kullanilabilir Artik:", d.text()])
                _, d = self.kesim_ozet_cop_fire
                w.writerow(["Cop Fire:", d.text()])
                _, d = self.kesim_ozet_fire_yuzde
                w.writerow(["Ort. Fire %:", d.text()])
                _, d = self.kesim_ozet_toplam_kg
                w.writerow(["Siparis (kg):", d.text()])
                _, d = self.kesim_ozet_toplam_ton
                w.writerow(["Siparis (ton):", d.text()])
                _, d = self.kesim_ozet_maliyet
                w.writerow(["Tahmini Maliyet:", d.text()])

            QMessageBox.information(self, "Basarili", f"Dosya kaydedildi:\n{dosya_yolu}")
            self.durum_label.setText(f"Kesim Listesi CSV aktarildi: {dosya_yolu}")
            logger.info("Kesim listesi CSV: %s", dosya_yolu)

        except Exception as hata:
            QMessageBox.critical(self, "Hata", f"Disa aktarma basarisiz:\n{hata}")
            logger.error("Kesim listesi CSV hatasi: %s", hata)

    # ------------------------------------------------------------------
    # Slotlar: Fiyat, CSV, Yardim
    # ------------------------------------------------------------------
    def _fiyat_degisti(self, yeni_fiyat: float):
        self._birim_fiyat = yeni_fiyat
        self.durum_label.setText(
            f"Birim fiyat guncellendi: {yeni_fiyat:.0f} TL/ton. "
            "Guncel maliyetler icin tekrar hesaplayin."
        )

    def _csv_aktar(self):
        try:
            from PyQt6.QtWidgets import QFileDialog
            import csv
            import datetime

            dosya_yolu, _ = QFileDialog.getSaveFileName(
                self, "CSV Olarak Kaydet", "",
                "CSV Dosyasi (*.csv);;Tum Dosyalar (*)"
            )
            if not dosya_yolu:
                return

            basliklar = [
                "Sira", "Cap (mm)", "Boy (cm)", "Adet", "Not",
                "Uzunluk (m)", "Agirlik (kg)", "Maliyet (TL)"
            ]

            with open(
                dosya_yolu, "w", newline="", encoding="utf-8-sig"
            ) as csv_dosyasi:
                yazar = csv.writer(csv_dosyasi, delimiter=";")
                yazar.writerow(
                    ["INSAAT METRAJ PRO -- Demir Hesaplama Raporu"]
                )
                yazar.writerow(
                    ["Tarih:", datetime.date.today().strftime("%d/%m/%Y")]
                )
                yazar.writerow(
                    ["Birim Fiyat (TL/ton):", f"{self._birim_fiyat:.0f}"]
                )
                yazar.writerow([])
                yazar.writerow(basliklar)

                for satir in range(self.toplu_tablo.rowCount()):
                    satir_verisi = []
                    for kolon in range(8):
                        widget = self.toplu_tablo.cellWidget(satir, kolon)
                        if widget is not None and hasattr(widget, "currentText"):
                            satir_verisi.append(widget.currentText())
                        else:
                            item = self.toplu_tablo.item(satir, kolon)
                            satir_verisi.append(item.text() if item else "")
                    yazar.writerow(satir_verisi)

                yazar.writerow([])
                _, ul_v = self.toplu_toplam_uzunluk
                _, ag_v = self.toplu_toplam_agirlik
                _, ton_v = self.toplu_toplam_ton
                _, mal_v = self.toplu_toplam_maliyet
                yazar.writerow(["TOPLAM UZUNLUK:", ul_v.text()])
                yazar.writerow(["TOPLAM AGIRLIK:", ag_v.text()])
                yazar.writerow(["TOPLAM TON:", ton_v.text()])
                yazar.writerow(["TOPLAM MALIYET:", mal_v.text()])

            QMessageBox.information(
                self, "Basarili", f"Dosya kaydedildi:\n{dosya_yolu}"
            )
            self.durum_label.setText(f"CSV disa aktarildi: {dosya_yolu}")
            logger.info("CSV aktar: %s", dosya_yolu)

        except Exception as hata:
            QMessageBox.critical(
                self, "Hata", f"Disa aktarma basarisiz:\n{hata}"
            )
            logger.error("CSV aktar hatasi: %s", hata)

    def _yardim_goster(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Demir Hesaplama -- Yardim")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(YARDIM_METNI)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    # ------------------------------------------------------------------
    # Stil
    # ------------------------------------------------------------------
    def _uygula_stil(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f7fa;
            }
            QTabWidget::pane {
                border: 1px solid #c8d6e5;
                border-radius: 4px;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #dce8f5;
                color: #1a3a5c;
                padding: 7px 18px;
                border: 1px solid #c8d6e5;
                border-bottom: none;
                border-radius: 4px 4px 0 0;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0d2137;
            }
            QGroupBox {
                font-weight: bold;
                color: #1a3a5c;
                border: 1px solid #c8d6e5;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                left: 12px;
            }
            QPushButton {
                background-color: #5d8aa8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a7a96;
            }
            QPushButton:pressed {
                background-color: #3a6a86;
            }
            QPushButton#primaryBtn {
                background-color: #1a6b3a;
            }
            QPushButton#primaryBtn:hover {
                background-color: #145a2f;
            }
            QTableWidget {
                gridline-color: #d5e8f0;
                selection-background-color: #b3d1e8;
            }
            QHeaderView::section {
                background-color: #1a3a5c;
                color: white;
                padding: 5px;
                font-weight: bold;
                border: none;
            }
            QDoubleSpinBox, QSpinBox, QComboBox {
                padding: 4px 6px;
                border: 1px solid #b0c4d8;
                border-radius: 3px;
                background: white;
                color: #1a3a5c;
            }
            QComboBox QAbstractItemView {
                background: white;
                color: #1a3a5c;
                selection-background-color: #aed6f1;
                selection-color: #0d2137;
            }
        """)
