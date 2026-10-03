"""
Yaklaşık Maliyet ve Keşif Özeti Penceresi
==========================================
4734 Sayılı Kamu İhale Kanunu kapsamında keşif cetveli hazırlama arayüzü.

Sekmeler:
  1. Keşif Cetveli   — Poz arama + kalem ekleme + tablo
  2. Özet & KDV      — Toplam, KDV, genel toplam, aşırı düşük sınır
  3. Kategori Dağılımı — Kategorilere göre özet tablo
  4. Aşırı Düşük Analizi — Rakip teklif girişi, KİK md.38 formülü, görsel sonuç
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QMessageBox, QHeaderView, QDoubleSpinBox,
    QTabWidget, QSplitter, QFrame, QDialog, QDialogButtonBox,
    QFileDialog, QCompleter, QAbstractItemView, QSpinBox,
    QStatusBar, QGridLayout, QTextEdit, QScrollArea, QInputDialog
)
from PyQt6.QtCore import Qt, QStringListModel, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush
from decimal import Decimal
from typing import Optional, List
import logging
import csv
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Engine importları (hata toleranslı) ─────────────────────────────────────
try:
    from app.core.yaklasik_maliyet_engine import (
        YaklasikMaliyetEngine, KURUM_LISTESI, KDV_ORANLARI
    )
    _ENGINE_OK = True
except Exception as e:
    logger.error(f"yaklasik_maliyet_engine import hatası: {e}")
    _ENGINE_OK = False

try:
    from app.core.csb_poz_engine import CSBPozEngine
    _CSB_OK = True
except Exception as e:
    logger.warning(f"csb_poz_engine import hatası: {e}")
    _CSB_OK = False

# ── Renk şeması ─────────────────────────────────────────────────────────────
DARK_BG   = "#1a1a2e"
CARD_BG   = "#16213e"
ACCENT    = "#00BFFF"
TEXT_WHITE = "#e0e0e0"
TEXT_GRAY  = "#a0a0b0"
GREEN     = "#27ae60"
RED       = "#e74c3c"
ORANGE    = "#f39c12"

# ── Fallback sabitler (engine yoksa) ────────────────────────────────────────
if not _ENGINE_OK:
    KURUM_LISTESI  = {"csb": "ÇŞB", "ozel": "Özel"}
    KDV_ORANLARI   = {"standard": Decimal("20"), "muaf": Decimal("0")}
    CSB_BIRIM_FIYATLARI_2025 = {}

    class YaklasikMaliyetEngine:  # type: ignore[no-redef]
        def __init__(self):
            self.kalemler       = []
            self.proje_adi      = ""
            self.ihale_no       = ""
            self.idare          = ""
            self.kurum          = "csb"
            self.kdv_orani      = Decimal("20")
            self._sira_sayac    = 0

        def hesapla(self):
            return {}

        def kategori_ozeti(self):
            return []

        def kalem_ekle(self, *args, **kwargs):
            pass

        def kalem_sil(self, sira_no):
            return False


# ════════════════════════════════════════════════════════════════════════════
# YARDIMCI: Biçimli para etiketi
# ════════════════════════════════════════════════════════════════════════════

def _para_str(deger: float) -> str:
    """Türk lirası formatı: 1.234.567,89 TL"""
    return f"{deger:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


# ════════════════════════════════════════════════════════════════════════════
# STIL YARDIMCILARI
# ════════════════════════════════════════════════════════════════════════════

def _tablo_stili() -> str:
    return f"""
        QTableWidget {{
            background-color: {CARD_BG};
            color: {TEXT_WHITE};
            gridline-color: #2a2a4a;
            border: 1px solid #2a2a4a;
            font-size: 12px;
        }}
        QHeaderView::section {{
            background-color: #0f3460;
            color: {TEXT_WHITE};
            padding: 6px;
            border: none;
            font-weight: bold;
        }}
        QTableWidget::item:selected {{
            background-color: #1a5276;
        }}
    """


def _btn_stili(renk: str = ACCENT) -> str:
    return f"""
        QPushButton {{
            background-color: {renk};
            color: #000000;
            border: none;
            border-radius: 4px;
            padding: 6px 14px;
            font-weight: bold;
            font-size: 12px;
        }}
        QPushButton:hover {{ background-color: #33ccff; }}
        QPushButton:pressed {{ background-color: #0088bb; }}
    """


def _input_stili() -> str:
    return f"""
        QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
            background-color: {CARD_BG};
            color: {TEXT_WHITE};
            border: 1px solid #2a2a4a;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 12px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {CARD_BG};
            color: {TEXT_WHITE};
        }}
    """


# ════════════════════════════════════════════════════════════════════════════
# SEKME 1 — Keşif Cetveli
# ════════════════════════════════════════════════════════════════════════════

class _KesifCetveliSekmesi(QWidget):
    kalem_eklendi  = pyqtSignal()
    durum_guncelle = pyqtSignal(str)

    def __init__(self, engine: YaklasikMaliyetEngine, db=None, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._db     = db
        self._csb    = CSBPozEngine() if _CSB_OK else None
        self._setup_ui()
        self._kategorileri_yukle()

    # ── Arayüz ───────────────────────────────────────────────────────────

    def _setup_ui(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(8, 8, 8, 8)
        ana.setSpacing(8)

        # Proje bilgileri formu
        ana.addWidget(self._proje_formu())

        # Splitter: Sol=Poz arama  /  Sağ=Keşif tablosu
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._poz_panel())
        splitter.addWidget(self._kesif_panel())
        splitter.setSizes([380, 620])
        ana.addWidget(splitter, 1)

        # Alt toolbar
        ana.addWidget(self._alt_toolbar())

    def _proje_formu(self) -> QGroupBox:
        grup = QGroupBox("Proje Bilgileri")
        grup.setStyleSheet(f"QGroupBox {{ color:{TEXT_WHITE}; border:1px solid #2a2a4a; "
                           f"border-radius:4px; margin-top:8px; }} "
                           f"QGroupBox::title {{ color:{ACCENT}; }}")
        lay = QHBoxLayout(grup)
        lay.setSpacing(12)

        self._proje_adi_input   = QLineEdit(); self._proje_adi_input.setPlaceholderText("Proje Adı")
        self._ihale_no_input    = QLineEdit(); self._ihale_no_input.setPlaceholderText("İhale No")
        self._idare_input       = QLineEdit(); self._idare_input.setPlaceholderText("İdare / Kurum")
        self._kdv_combo         = QComboBox()
        self._kurum_combo       = QComboBox()

        self._kdv_combo.addItem("%20 — Standart",  "standard")
        self._kdv_combo.addItem("%0  — KDV Muaf",  "muaf")

        for kod, ad in KURUM_LISTESI.items():
            self._kurum_combo.addItem(ad, kod)

        for w in (self._proje_adi_input, self._ihale_no_input, self._idare_input,
                  self._kdv_combo, self._kurum_combo):
            w.setStyleSheet(_input_stili())

        # Etiket + widget çiftleri
        pairs = [
            ("Proje Adı:", self._proje_adi_input),
            ("İhale No:",  self._ihale_no_input),
            ("İdare:",     self._idare_input),
            ("KDV:",       self._kdv_combo),
            ("Kurum:",     self._kurum_combo),
        ]
        for etiket, widget in pairs:
            lbl = QLabel(etiket)
            lbl.setStyleSheet(f"color:{TEXT_GRAY};")
            lay.addWidget(lbl)
            lay.addWidget(widget)

        # Proje bilgileri değişince engine'i güncelle
        self._proje_adi_input.textChanged.connect(self._proje_bilgilerini_guncelle)
        self._ihale_no_input.textChanged.connect(self._proje_bilgilerini_guncelle)
        self._idare_input.textChanged.connect(self._proje_bilgilerini_guncelle)
        self._kdv_combo.currentIndexChanged.connect(self._proje_bilgilerini_guncelle)
        self._kurum_combo.currentIndexChanged.connect(self._proje_bilgilerini_guncelle)

        return grup

    def _poz_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(6)

        baslik = QLabel("Poz Listesi (CŞB)")
        baslik.setStyleSheet(f"color:{ACCENT}; font-weight:bold; font-size:13px;")
        lay.addWidget(baslik)

        # Kategori filtre
        self._kat_combo = QComboBox()
        self._kat_combo.addItem("-- Tüm Kategoriler --", None)
        self._kat_combo.setStyleSheet(_input_stili())
        self._kat_combo.currentIndexChanged.connect(self._poz_listele)
        lay.addWidget(self._kat_combo)

        # Arama satırı
        ara_lay = QHBoxLayout()
        self._arama_input = QLineEdit()
        self._arama_input.setPlaceholderText("Poz kodu veya tanım ara...")
        self._arama_input.setStyleSheet(_input_stili())
        self._arama_input.returnPressed.connect(self._poz_ara)
        ara_btn = QPushButton("Ara")
        ara_btn.setStyleSheet(_btn_stili())
        ara_btn.clicked.connect(self._poz_ara)
        ara_lay.addWidget(self._arama_input)
        ara_lay.addWidget(ara_btn)
        lay.addLayout(ara_lay)

        # Poz tablosu
        self._poz_tablo = QTableWidget(0, 4)
        self._poz_tablo.setHorizontalHeaderLabels(["Kod", "Tanım", "Birim", "Fiyat (TL)"])
        self._poz_tablo.setStyleSheet(_tablo_stili())
        self._poz_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._poz_tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._poz_tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._poz_tablo.verticalHeader().setVisible(False)
        self._poz_tablo.setAlternatingRowColors(True)
        self._poz_tablo.doubleClicked.connect(self._secili_poz_ekle)
        lay.addWidget(self._poz_tablo, 1)

        return w

    def _kesif_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 0, 0, 0)
        lay.setSpacing(6)

        baslik = QLabel("Keşif Cetveli")
        baslik.setStyleSheet(f"color:{ACCENT}; font-weight:bold; font-size:13px;")
        lay.addWidget(baslik)

        self._kesif_tablo = QTableWidget(0, 7)
        self._kesif_tablo.setHorizontalHeaderLabels(
            ["Sıra", "Poz No", "Tanım", "Birim", "Miktar", "Birim Fiyat (TL)", "Tutar (TL)"]
        )
        self._kesif_tablo.setStyleSheet(_tablo_stili())
        self._kesif_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._kesif_tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._kesif_tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._kesif_tablo.verticalHeader().setVisible(False)
        self._kesif_tablo.setAlternatingRowColors(True)
        lay.addWidget(self._kesif_tablo, 1)

        return w

    def _alt_toolbar(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        ekle_btn   = QPushButton("+ Seçili Poz'u Ekle")
        sil_btn    = QPushButton("Kalem Sil")
        csv_btn    = QPushButton("CSV Dışa Aktar")
        gunc_btn   = QPushButton("CŞB Listesini Güncelle (CSV)")
        metraj_btn = QPushButton("Metrajdan Aktar")
        yardim_btn = QPushButton("?  Yardım")

        ekle_btn.setStyleSheet(_btn_stili(GREEN))
        sil_btn.setStyleSheet(_btn_stili(RED))
        csv_btn.setStyleSheet(_btn_stili(ORANGE))
        gunc_btn.setStyleSheet(_btn_stili(TEXT_GRAY))
        metraj_btn.setStyleSheet(_btn_stili("#8e44ad"))
        yardim_btn.setStyleSheet(_btn_stili("#0f3460"))
        metraj_btn.setToolTip("Mevcut projelerden metraj kalemlerini keşif cetveline aktar")
        yardim_btn.setToolTip("Kullanım kılavuzunu göster")

        ekle_btn.clicked.connect(self._secili_poz_ekle)
        sil_btn.clicked.connect(self._kalem_sil)
        csv_btn.clicked.connect(self._csv_disari_aktar)
        gunc_btn.clicked.connect(self._csv_import)
        metraj_btn.clicked.connect(self._metrajdan_aktar)
        yardim_btn.clicked.connect(self._yardim_goster)

        for btn in (ekle_btn, sil_btn, csv_btn, gunc_btn, metraj_btn):
            lay.addWidget(btn)
        lay.addStretch()
        lay.addWidget(yardim_btn)
        return w

    def _yardim_goster(self) -> None:
        metin = """
<h2 style="color:#00BFFF;">Yaklaşık Maliyet ve Keşif Cetveli — Kullanım Kılavuzu</h2>
<p style="color:#a0a0b0;">4734 Sayılı Kamu İhale Kanunu kapsamında ihale öncesi keşif cetveli hazırlama aracı.</p>

<hr style="border-color:#2a4a7f;">

<h3 style="color:#00BFFF;">Sekme 1 — Keşif Cetveli</h3>

<b style="color:#e0e0e0;">Sol Panel — Poz Listesi (CŞB)</b>
<ul style="color:#e0e0e0;">
  <li><b>Kategori Filtresi:</b> Açılır listeden (ör. "Beton İşleri", "Kalıp İşleri") bir kategori seçin. Poz listesi otomatik filtrelenir.</li>
  <li><b>Arama Kutusu:</b> Poz kodu (ör. <i>21.002</i>) veya tanım kelimesi yazarak anlık arama yapın. "Ara" butonuna basmak gerekmez — yazarken filtre çalışır.</li>
  <li><b>Poz Seçme:</b> Listeden bir satıra tıklayın, ardından <b>"+ Seçili Poz'u Ekle"</b> butonuna basın. Keşif cetveline miktar giriş ekranı açılır.</li>
</ul>

<b style="color:#e0e0e0;">Sağ Panel — Keşif Cetveli</b>
<ul style="color:#e0e0e0;">
  <li>Eklediğiniz poz kalemleri sıra numarasıyla burada listelenir.</li>
  <li>Satıra çift tıklayarak <b>miktar</b> ve <b>not</b> alanını düzenleyebilirsiniz.</li>
  <li><b>Kalem Sil:</b> Sağ panelde bir satır seçin, ardından "Kalem Sil" butonuna basın.</li>
</ul>

<b style="color:#e0e0e0;">Alt Toolbar Butonları</b>
<table style="color:#e0e0e0; width:100%;">
  <tr><td style="color:#27ae60;"><b>+ Seçili Poz'u Ekle</b></td><td>Sol panelde seçili CŞB pozunu keşif cetveline ekler. Miktar giriş penceresi açılır.</td></tr>
  <tr><td style="color:#e74c3c;"><b>Kalem Sil</b></td><td>Keşif cetvelinde seçili satırı siler (geri alınamaz).</td></tr>
  <tr><td style="color:#f39c12;"><b>CSV Dışa Aktar</b></td><td>Keşif cetvelini .csv formatında dışa aktarır (Excel ile açılabilir).</td></tr>
  <tr><td style="color:#a0a0b0;"><b>CŞB Listesini Güncelle (CSV)</b></td><td>Çevre Şehircilik Bakanlığı güncel birim fiyat listesini CSV formatında içeri aktarır. CŞB resmi sitesinden indirilen CSV doğrudan yüklenebilir.</td></tr>
  <tr><td style="color:#8e44ad;"><b>Metrajdan Aktar</b></td><td>Programın metraj modülünden hesaplanan miktarları otomatik olarak keşif cetveline aktarır. Çift veri girişini önler.</td></tr>
</table>

<hr style="border-color:#2a4a7f;">

<h3 style="color:#00BFFF;">Sekme 2 — Özet KDV</h3>
<ul style="color:#e0e0e0;">
  <li>Keşif cetvelindeki tüm kalemlerin toplam tutarı, KDV tutarı ve genel toplamı gösterir.</li>
  <li>KDV oranı bu sekmeden değiştirilebilir (%0 — Muaf, %20 — Standart).</li>
  <li><b>Aşırı Düşük Sınır (KİK md.38):</b> Genel toplamın %80'i — bu değerin altındaki teklifler aşırı düşük sayılır ve inceleme yapılır.</li>
</ul>

<h3 style="color:#00BFFF;">Sekme 3 — Kategori Dağılımı</h3>
<ul style="color:#e0e0e0;">
  <li>Keşif cetvelindeki kalemleri kategorilere göre gruplandırır (Hafriyat, Beton, Kalıp, Demir vb.).</li>
  <li>Her kategorinin toplam tutarını ve genel toplama oranını gösterir.</li>
  <li>İhale hazırlık sürecinde maliyet dağılımını analiz etmek için kullanılır.</li>
</ul>

<h3 style="color:#00BFFF;">Sekme 4 — Aşırı Düşük Analizi</h3>
<ul style="color:#e0e0e0;">
  <li>Rakip teklif tutarlarını girin. Program, KİK md.38 formülüne göre <b>eşik değer</b> hesaplar.</li>
  <li>Teklifin eşik değerin altında kalıp kalmadığı görsel olarak gösterilir.</li>
  <li>İhale öncesi kendi teklifinizin güvenli bölgede olup olmadığını test etmek için kullanın.</li>
</ul>

<hr style="border-color:#2a4a7f;">

<h3 style="color:#00BFFF;">İpuçları</h3>
<ul style="color:#e0e0e0;">
  <li>CŞB poz kodları <b>16.xxx</b> = Hafriyat, <b>21.xxx</b> = Beton/Kalıp/Demir, <b>22.xxx</b> = Duvar/Sıva kategorisindedir.</li>
  <li>Birim fiyatlar 2026 CŞB listesine göre ayarlanmıştır. Güncel fiyat için "CŞB Listesini Güncelle" kullanın.</li>
  <li>Proje Adı ve İhale No alanlarını doldurun — PDF raporuna otomatik aktarılır.</li>
  <li>Metraj modülünden aktarım yapıldığında miktarlar otomatik hesaplanır, sadece kontrol edin.</li>
</ul>
"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Yaklaşık Maliyet — Kullanım Kılavuzu")
        dlg.setMinimumSize(700, 550)
        dlg.setStyleSheet(f"background-color: {DARK_BG}; color: {TEXT_WHITE};")
        lay = QVBoxLayout(dlg)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        icerik = QLabel(metin)
        icerik.setWordWrap(True)
        icerik.setTextFormat(Qt.TextFormat.RichText)
        icerik.setStyleSheet(f"background-color: {CARD_BG}; padding: 16px; border-radius: 6px;")
        scroll.setWidget(icerik)
        lay.addWidget(scroll)

        kapat = QPushButton("Kapat")
        kapat.setStyleSheet(_btn_stili(ACCENT))
        kapat.clicked.connect(dlg.accept)
        lay.addWidget(kapat)
        dlg.exec()

    # ── İş mantığı ───────────────────────────────────────────────────────

    def _kategorileri_yukle(self):
        if not self._csb:
            return
        try:
            kategoriler = self._csb.kategoriler()
            self._kat_combo.blockSignals(True)
            for kat in kategoriler:
                self._kat_combo.addItem(kat, kat)
            self._kat_combo.blockSignals(False)
        except Exception as e:
            logger.error(f"Kategori yükleme hatası: {e}")
        self._poz_listele()

    def _poz_listele(self):
        kat = self._kat_combo.currentData()
        if self._csb:
            try:
                pozlar = self._csb.tum_pozlar(kategori=kat)
            except Exception as e:
                logger.error(f"Poz listeleme hatası: {e}")
                pozlar = []
        else:
            # Fallback: engine sabit listesi
            pozlar = [
                {"poz_kodu": k, "aciklama": v["tanim"],
                 "birim": v["birim"], "birim_fiyat": float(v["fiyat"])}
                for k, v in CSB_BIRIM_FIYATLARI_2025.items()
            ]
        self._poz_tablo_doldur(pozlar)

    def _poz_ara(self):
        metin = self._arama_input.text().strip()
        if not metin:
            self._poz_listele()
            return
        kat = self._kat_combo.currentData()
        if self._csb:
            try:
                pozlar = self._csb.metin_ara(metin, kategori=kat)
            except Exception as e:
                logger.error(f"Arama hatası: {e}")
                pozlar = []
        else:
            metin_lower = metin.lower()
            pozlar = [
                {"poz_kodu": k, "aciklama": v["tanim"],
                 "birim": v["birim"], "birim_fiyat": float(v["fiyat"])}
                for k, v in CSB_BIRIM_FIYATLARI_2025.items()
                if metin_lower in k.lower() or metin_lower in v["tanim"].lower()
            ]
        self._poz_tablo_doldur(pozlar)
        self.durum_guncelle.emit(f"{len(pozlar)} poz bulundu")

    def _poz_tablo_doldur(self, pozlar: list):
        self._poz_tablo.blockSignals(True)
        self._poz_tablo.setRowCount(0)
        for poz in pozlar:
            r = self._poz_tablo.rowCount()
            self._poz_tablo.insertRow(r)
            kod   = poz.get("poz_kodu", "")
            tanim = poz.get("aciklama", "")
            birim = poz.get("birim", "")
            fiyat = float(poz.get("birim_fiyat", 0))
            self._poz_tablo.setItem(r, 0, QTableWidgetItem(kod))
            self._poz_tablo.setItem(r, 1, QTableWidgetItem(tanim))
            self._poz_tablo.setItem(r, 2, QTableWidgetItem(birim))
            item = QTableWidgetItem(f"{fiyat:,.2f}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._poz_tablo.setItem(r, 3, item)
        self._poz_tablo.blockSignals(False)

    def _secili_poz_ekle(self):
        satirlar = self._poz_tablo.selectedItems()
        if not satirlar:
            QMessageBox.warning(self, "Uyarı", "Lütfen poz listesinden bir kalem seçin.")
            return
        satir = self._poz_tablo.currentRow()
        poz_no  = self._poz_tablo.item(satir, 0).text()
        tanim   = self._poz_tablo.item(satir, 1).text()
        birim   = self._poz_tablo.item(satir, 2).text()
        fiyat_t = self._poz_tablo.item(satir, 3).text().replace(",", "")
        try:
            birim_fiyat = float(fiyat_t)
        except ValueError:
            birim_fiyat = 0.0

        miktar, ok = QInputDialog.getDouble(
            self, "Miktar Gir",
            f"{poz_no} — {tanim}\nBirim: {birim}\nMiktar:",
            1.0, 0.001, 9_999_999, 3
        )
        if not ok:
            return

        try:
            self._engine.kalem_ekle(
                poz_no=poz_no,
                miktar=miktar,
                birim_fiyat=birim_fiyat,
                tanim=tanim,
                birim=birim,
            )
        except Exception as e:
            logger.error(f"Kalem ekleme hatası: {e}")
            # Manuel ekle
            from decimal import Decimal
            self._engine._sira_sayac += 1
            from app.core.yaklasik_maliyet_engine import YaklasikMaliyetKalemi
            kalem = YaklasikMaliyetKalemi(
                sira_no=self._engine._sira_sayac,
                poz_no=poz_no, tanim=tanim, birim=birim,
                miktar=Decimal(str(miktar)),
                birim_fiyat=Decimal(str(birim_fiyat)),
            )
            self._engine.kalemler.append(kalem)

        self._kesif_tablo_yenile()
        self.kalem_eklendi.emit()

    def _kesif_tablo_yenile(self):
        self._kesif_tablo.blockSignals(True)
        self._kesif_tablo.setRowCount(0)
        toplam = 0.0
        for kalem in self._engine.kalemler:
            r = self._kesif_tablo.rowCount()
            self._kesif_tablo.insertRow(r)
            tutar = float(kalem.tutar) if hasattr(kalem, "tutar") else 0.0
            toplam += tutar
            degerler = [
                str(kalem.sira_no), kalem.poz_no, kalem.tanim,
                kalem.birim,
                f"{float(kalem.miktar):,.3f}",
                f"{float(kalem.birim_fiyat):,.2f}",
                f"{tutar:,.2f}",
            ]
            for col, val in enumerate(degerler):
                item = QTableWidgetItem(val)
                if col in (4, 5, 6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._kesif_tablo.setItem(r, col, item)
        self._kesif_tablo.blockSignals(False)
        self.durum_guncelle.emit(
            f"{len(self._engine.kalemler)} kalem  |  Toplam: {_para_str(toplam)}"
        )

    def _kalem_sil(self):
        satir = self._kesif_tablo.currentRow()
        if satir < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz kalemi seçin.")
            return
        sira_item = self._kesif_tablo.item(satir, 0)
        if sira_item is None:
            return
        try:
            sira_no = int(sira_item.text())
            self._engine.kalem_sil(sira_no)
        except Exception as e:
            logger.error(f"Kalem silme hatası: {e}")
        self._kesif_tablo_yenile()
        self.kalem_eklendi.emit()

    def _csv_disari_aktar(self):
        yol, _ = QFileDialog.getSaveFileName(
            self, "CSV Kaydet", "kesif_cetveli.csv", "CSV Dosyası (*.csv)"
        )
        if not yol:
            return
        try:
            with open(yol, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Sıra", "Poz No", "Tanım", "Birim", "Miktar",
                                 "Birim Fiyat (TL)", "Tutar (TL)"])
                for kalem in self._engine.kalemler:
                    writer.writerow([
                        kalem.sira_no, kalem.poz_no, kalem.tanim, kalem.birim,
                        float(kalem.miktar), float(kalem.birim_fiyat),
                        float(kalem.tutar) if hasattr(kalem, "tutar") else 0
                    ])
            QMessageBox.information(self, "Başarılı", f"CSV dışa aktarıldı:\n{yol}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"CSV yazma hatası:\n{e}")

    def _csv_import(self):
        yol, _ = QFileDialog.getOpenFileName(
            self, "CŞB Poz Listesi CSV Yükle", "", "CSV Dosyası (*.csv)"
        )
        if not yol or not self._csb:
            if not self._csb:
                QMessageBox.warning(self, "Uyarı", "CŞB poz motoru yüklü değil.")
            return
        try:
            with open(yol, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                eklenen = self._csb.toplu_aktar(list(reader))
            QMessageBox.information(self, "İçe Aktarma", f"{eklenen} poz güncellendi.")
            self._kategorileri_yukle()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"CSV içe aktarma hatası:\n{e}")

    def _metrajdan_aktar(self):
        if self._db is None:
            QMessageBox.warning(
                self, "Veritabanı Bağlantısı Yok",
                "Bu pencere veritabanına bağlı değil.\n"
                "Lütfen Araçlar menüsünden 'Yaklaşık Maliyet & Keşif Cetveli' ile açın."
            )
            return
        dlg = _MetrajAktarDialog(self._db, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        kalemler = dlg.secilen_kalemler()
        if not kalemler:
            return
        eklenen = 0
        for kal in kalemler:
            try:
                self._engine.kalem_ekle(
                    poz_no=kal.get("poz_no") or "",
                    miktar=float(kal.get("miktar") or 0),
                    birim_fiyat=float(kal.get("birim_fiyat") or 0),
                    tanim=kal.get("tanim") or "",
                    birim=kal.get("birim") or "adet",
                )
                eklenen += 1
            except Exception as e:
                logger.error(f"Metraj aktarım kalemi eklenemedi: {e}")
        self._kesif_tablo_yenile()
        self.kalem_eklendi.emit()
        self.durum_guncelle.emit(f"{eklenen} metraj kalemi keşif cetvelne aktarıldı.")

    def _proje_bilgilerini_guncelle(self):
        self._engine.proje_adi  = self._proje_adi_input.text().strip()
        self._engine.ihale_no   = self._ihale_no_input.text().strip()
        self._engine.idare      = self._idare_input.text().strip()
        kdv_key = self._kdv_combo.currentData() or "standard"
        self._engine.kdv_orani  = KDV_ORANLARI.get(kdv_key, Decimal("20"))
        self._engine.kurum      = self._kurum_combo.currentData() or "csb"


# ════════════════════════════════════════════════════════════════════════════
# SEKME 2 — Özet & KDV
# ════════════════════════════════════════════════════════════════════════════

class _OzetKdvSekmesi(QWidget):
    def __init__(self, engine: YaklasikMaliyetEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._setup_ui()

    def _setup_ui(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(16, 16, 16, 16)
        ana.setSpacing(12)

        baslik = QLabel("Yaklaşık Maliyet Özeti")
        baslik.setStyleSheet(f"color:{ACCENT}; font-size:16px; font-weight:bold;")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ana.addWidget(baslik)

        # Özet kartı
        ozet_grup = QGroupBox("Proje Özeti")
        ozet_grup.setStyleSheet(f"QGroupBox {{ color:{TEXT_WHITE}; border:1px solid #2a2a4a; "
                                f"border-radius:4px; margin-top:8px; }} "
                                f"QGroupBox::title {{ color:{ACCENT}; }}")
        ozet_lay = QFormLayout(ozet_grup)
        self._ozet_proje  = QLabel("—")
        self._ozet_ihale  = QLabel("—")
        self._ozet_idare  = QLabel("—")
        self._ozet_tarih  = QLabel("—")
        for lbl in (self._ozet_proje, self._ozet_ihale, self._ozet_idare, self._ozet_tarih):
            lbl.setStyleSheet(f"color:{TEXT_WHITE};")
        ozet_lay.addRow("Proje Adı:", self._ozet_proje)
        ozet_lay.addRow("İhale No:",  self._ozet_ihale)
        ozet_lay.addRow("İdare:",     self._ozet_idare)
        ozet_lay.addRow("Tarih:",     self._ozet_tarih)
        ana.addWidget(ozet_grup)

        # Hesaplama kutucukları (grid)
        hesap_grup = QGroupBox("Maliyet Hesabı")
        hesap_grup.setStyleSheet(ozet_grup.styleSheet())
        grid = QGridLayout(hesap_grup)

        self._lbl_toplam  = self._para_lbl("—")
        self._lbl_kdv     = self._para_lbl("—")
        self._lbl_genel   = self._para_lbl("—", buyuk=True)
        self._lbl_sinir   = self._para_lbl("—", renk=RED)
        self._lbl_kdv_oran = QLabel("—")
        self._lbl_kdv_oran.setStyleSheet(f"color:{TEXT_GRAY};")

        pairs = [
            ("Yapım Bedeli (KDV hariç):",       self._lbl_toplam,  None),
            ("KDV:",                             self._lbl_kdv,     self._lbl_kdv_oran),
            ("Genel Toplam (KDV dahil):",        self._lbl_genel,   None),
            ("Aşırı Düşük Sınır (KİK %80):",   self._lbl_sinir,   None),
        ]
        for i, (metin, widget, ekstra) in enumerate(pairs):
            lbl = QLabel(metin)
            lbl.setStyleSheet(f"color:{TEXT_GRAY}; font-weight:bold;")
            grid.addWidget(lbl, i, 0)
            grid.addWidget(widget, i, 1)
            if ekstra:
                grid.addWidget(ekstra, i, 2)

        ana.addWidget(hesap_grup)
        ana.addStretch()

        # Butonlar
        btn_lay = QHBoxLayout()
        rapor_btn = QPushButton("PDF Keşif Ozeti Uret")
        rapor_btn.setStyleSheet(_btn_stili(ORANGE))
        rapor_btn.clicked.connect(self._rapor_goster)
        btn_lay.addStretch()
        btn_lay.addWidget(rapor_btn)
        ana.addLayout(btn_lay)

    def _para_lbl(self, metin: str, buyuk: bool = False, renk: str = GREEN) -> QLabel:
        lbl = QLabel(metin)
        boyut = "18px" if buyuk else "14px"
        lbl.setStyleSheet(f"color:{renk}; font-size:{boyut}; font-weight:bold;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return lbl

    def yenile(self):
        if not self._engine.kalemler:
            for lbl in (self._lbl_toplam, self._lbl_kdv, self._lbl_genel, self._lbl_sinir):
                lbl.setText("—")
            return
        try:
            sonuc = self._engine.hesapla()
        except Exception as e:
            logger.error(f"Hesaplama hatası: {e}")
            return

        self._ozet_proje.setText(sonuc.get("proje_adi") or "—")
        self._ozet_ihale.setText(sonuc.get("ihale_no")  or "—")
        self._ozet_idare.setText(sonuc.get("idare")     or "—")
        self._ozet_tarih.setText(sonuc.get("tarih")     or "—")

        self._lbl_toplam.setText(_para_str(sonuc.get("toplam_yapim", 0)))
        self._lbl_kdv.setText(_para_str(sonuc.get("kdv_tutari", 0)))
        self._lbl_kdv_oran.setText(f"(%{sonuc.get('kdv_orani', 0):.0f})")
        self._lbl_genel.setText(_para_str(sonuc.get("genel_toplam", 0)))
        self._lbl_sinir.setText(_para_str(sonuc.get("asiri_dusuk_sinir", 0)))

    def _rapor_goster(self):
        """4734 uyumlu keşif özeti PDF üret ve kaydet."""
        if not self._engine.kalemler:
            QMessageBox.warning(
                self, "Uyarı",
                "Keşif cetvelinde hiç kalem yok.\n"
                "Önce 'Keşif Cetveli' sekmesinden kalem ekleyin."
            )
            return

        proje_adi = (self._engine.proje_adi or "kesif_ozeti").replace(" ", "_")
        varsayilan_ad = f"{proje_adi}_kesif.pdf"

        dosya_yolu, _ = QFileDialog.getSaveFileName(
            self, "PDF Keşif Özeti Kaydet",
            varsayilan_ad,
            "PDF Dosyası (*.pdf)"
        )
        if not dosya_yolu:
            return

        if not dosya_yolu.lower().endswith(".pdf"):
            dosya_yolu += ".pdf"

        try:
            basarili = self._engine.pdf_kesif_ozeti_uret(dosya_yolu)
        except Exception as exc:
            QMessageBox.warning(
                self, "PDF Hatası",
                f"PDF oluşturulurken hata oluştu:\n{exc}"
            )
            return

        if basarili:
            QMessageBox.information(
                self, "PDF Oluşturuldu",
                f"Keşif özeti PDF olarak kaydedildi:\n{dosya_yolu}"
            )
        else:
            QMessageBox.warning(
                self, "PDF Hatası",
                "PDF oluşturulamadı.\n"
                "reportlab kütüphanesi yüklü olmayabilir.\n"
                "Yüklemek için: pip install reportlab"
            )


# ════════════════════════════════════════════════════════════════════════════
# SEKME 3 — Kategori Dağılımı
# ════════════════════════════════════════════════════════════════════════════

class _KategoriSekmesi(QWidget):
    def __init__(self, engine: YaklasikMaliyetEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._setup_ui()

    def _setup_ui(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(16, 16, 16, 16)
        ana.setSpacing(8)

        baslik = QLabel("Kategori Bazında Maliyet Dağılımı")
        baslik.setStyleSheet(f"color:{ACCENT}; font-size:14px; font-weight:bold;")
        ana.addWidget(baslik)

        self._tablo = QTableWidget(0, 4)
        self._tablo.setHorizontalHeaderLabels(["Kategori", "Kalem Sayısı", "Toplam Tutar (TL)", "Oran (%)"])
        self._tablo.setStyleSheet(_tablo_stili())
        self._tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tablo.verticalHeader().setVisible(False)
        self._tablo.setAlternatingRowColors(True)
        ana.addWidget(self._tablo, 1)

    def yenile(self):
        self._tablo.blockSignals(True)
        self._tablo.setRowCount(0)
        try:
            ozet = self._engine.kategori_ozeti()
        except Exception as e:
            logger.error(f"Kategori özeti hatası: {e}")
            self._tablo.blockSignals(False)
            return
        for kat_bilgi in ozet:
            r = self._tablo.rowCount()
            self._tablo.insertRow(r)
            kalem_sayisi = kat_bilgi.get("kalem_sayisi", 0)
            tutar        = float(kat_bilgi.get("toplam_tutar", 0))
            oran         = float(kat_bilgi.get("oran_yuzde", 0))
            kat_ad       = kat_bilgi.get("kategori", "—")
            self._tablo.setItem(r, 0, QTableWidgetItem(kat_ad))
            item_sayi = QTableWidgetItem(str(kalem_sayisi))
            item_sayi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_tutar = QTableWidgetItem(f"{tutar:,.2f}")
            item_tutar.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_oran = QTableWidgetItem(f"%{oran:.1f}")
            item_oran.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tablo.setItem(r, 1, item_sayi)
            self._tablo.setItem(r, 2, item_tutar)
            self._tablo.setItem(r, 3, item_oran)
        self._tablo.blockSignals(False)


# ════════════════════════════════════════════════════════════════════════════
# SEKME 4 — Aşırı Düşük Analizi
# ════════════════════════════════════════════════════════════════════════════

class _AsiriDusukSekmesi(QWidget):
    def __init__(self, engine: YaklasikMaliyetEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._setup_ui()

    def _setup_ui(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(16, 16, 16, 16)
        ana.setSpacing(10)

        # Yaklaşık maliyet bilgisi
        bilgi_grup = QGroupBox("Yaklaşık Maliyet Bilgisi")
        bilgi_grup.setStyleSheet(f"QGroupBox {{ color:{TEXT_WHITE}; border:1px solid #2a2a4a; "
                                 f"border-radius:4px; margin-top:8px; }} "
                                 f"QGroupBox::title {{ color:{ACCENT}; }}")
        bilgi_lay = QHBoxLayout(bilgi_grup)
        self._lbl_ym = QLabel("—")
        self._lbl_ym.setStyleSheet(f"color:{ORANGE}; font-size:16px; font-weight:bold;")
        self._lbl_kik = QLabel("—")
        self._lbl_kik.setStyleSheet(f"color:{RED}; font-size:14px; font-weight:bold;")
        bilgi_lay.addWidget(QLabel("Yaklaşık Maliyet:").setStyleSheet if False else QLabel("Yaklaşık Maliyet:"))
        bilgi_lay.addWidget(self._lbl_ym)
        bilgi_lay.addSpacing(30)
        bilgi_lay.addWidget(QLabel("KİK Sınır (%80):"))
        bilgi_lay.addWidget(self._lbl_kik)
        bilgi_lay.addStretch()
        for lbl in bilgi_grup.findChildren(QLabel):
            if lbl not in (self._lbl_ym, self._lbl_kik):
                lbl.setStyleSheet(f"color:{TEXT_GRAY}; font-weight:bold;")
        ana.addWidget(bilgi_grup)

        # Teklif giriş paneli
        teklif_grup = QGroupBox("Teklif Girişi")
        teklif_grup.setStyleSheet(bilgi_grup.styleSheet())
        teklif_lay = QVBoxLayout(teklif_grup)

        # Teklif tablosu
        self._teklif_tablo = QTableWidget(0, 4)
        self._teklif_tablo.setHorizontalHeaderLabels(
            ["Sıra", "Firma Adı", "Teklif Tutarı (TL)", "Durum"]
        )
        self._teklif_tablo.setStyleSheet(_tablo_stili())
        self._teklif_tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._teklif_tablo.verticalHeader().setVisible(False)
        self._teklif_tablo.setAlternatingRowColors(True)
        teklif_lay.addWidget(self._teklif_tablo)

        # Teklif formu
        form_lay = QHBoxLayout()
        self._firma_input = QLineEdit()
        self._firma_input.setPlaceholderText("Firma adı")
        self._firma_input.setStyleSheet(_input_stili())
        self._tutar_input = QDoubleSpinBox()
        self._tutar_input.setRange(0, 999_999_999_999)
        self._tutar_input.setDecimals(2)
        self._tutar_input.setSingleStep(10000)
        self._tutar_input.setStyleSheet(_input_stili())
        self._tutar_input.setPrefix("₺ ")
        ekle_btn = QPushButton("Teklif Ekle")
        ekle_btn.setStyleSheet(_btn_stili(GREEN))
        ekle_btn.clicked.connect(self._teklif_ekle)
        sil_btn = QPushButton("Teklif Sil")
        sil_btn.setStyleSheet(_btn_stili(RED))
        sil_btn.clicked.connect(self._teklif_sil)
        form_lay.addWidget(QLabel("Firma:"))
        form_lay.addWidget(self._firma_input, 2)
        form_lay.addWidget(QLabel("Tutar:"))
        form_lay.addWidget(self._tutar_input, 2)
        form_lay.addWidget(ekle_btn)
        form_lay.addWidget(sil_btn)
        for lbl in (form_lay.itemAt(0).widget(), form_lay.itemAt(2).widget()):
            if isinstance(lbl, QLabel):
                lbl.setStyleSheet(f"color:{TEXT_GRAY};")
        teklif_lay.addLayout(form_lay)
        ana.addWidget(teklif_grup)

        # Analiz butonu + sonuç
        hesap_btn = QPushButton("Analizi Hesapla (KİK md.38)")
        hesap_btn.setStyleSheet(_btn_stili(ACCENT))
        hesap_btn.clicked.connect(self._analizi_hesapla)
        ana.addWidget(hesap_btn)

        self._sonuc_text = QTextEdit()
        self._sonuc_text.setReadOnly(True)
        self._sonuc_text.setStyleSheet(f"background-color:{CARD_BG}; color:{TEXT_WHITE}; "
                                       f"border:1px solid #2a2a4a; font-size:12px;")
        self._sonuc_text.setMaximumHeight(160)
        ana.addWidget(self._sonuc_text)

        not_lbl = QLabel("Not: 4734 sayılı KİK Madde 38 kapsamında hesaplanmaktadır. "
                         "Kesin sınır için KİK mevzuatını esas alın.")
        not_lbl.setStyleSheet(f"color:{TEXT_GRAY}; font-size:11px; font-style:italic;")
        not_lbl.setWordWrap(True)
        ana.addWidget(not_lbl)

    def yenile(self):
        try:
            sonuc = self._engine.hesapla()
        except Exception:
            return
        ym = sonuc.get("toplam_yapim", 0)
        sinir = sonuc.get("asiri_dusuk_sinir", 0)
        self._lbl_ym.setText(_para_str(ym))
        self._lbl_kik.setText(_para_str(sinir))

    def _teklif_ekle(self):
        firma = self._firma_input.text().strip()
        tutar = self._tutar_input.value()
        if not firma:
            QMessageBox.warning(self, "Uyarı", "Firma adı girin.")
            return
        if tutar <= 0:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir teklif tutarı girin.")
            return
        r = self._teklif_tablo.rowCount()
        self._teklif_tablo.insertRow(r)
        self._teklif_tablo.setItem(r, 0, QTableWidgetItem(str(r + 1)))
        self._teklif_tablo.setItem(r, 1, QTableWidgetItem(firma))
        item = QTableWidgetItem(f"{tutar:,.2f}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._teklif_tablo.setItem(r, 2, item)
        self._teklif_tablo.setItem(r, 3, QTableWidgetItem("Bekliyor"))
        self._firma_input.clear()
        self._tutar_input.setValue(0)

    def _teklif_sil(self):
        satir = self._teklif_tablo.currentRow()
        if satir < 0:
            return
        self._teklif_tablo.removeRow(satir)
        # Sıra numaralarını güncelle
        for i in range(self._teklif_tablo.rowCount()):
            self._teklif_tablo.setItem(i, 0, QTableWidgetItem(str(i + 1)))

    def _analizi_hesapla(self):
        n = self._teklif_tablo.rowCount()
        if n < 3:
            QMessageBox.warning(self, "Yetersiz Veri",
                                "KİK md.38 analizi için en az 3 teklif gereklidir.")
            return
        try:
            sonuc = self._engine.hesapla()
        except Exception:
            sonuc = {}
        ym    = sonuc.get("toplam_yapim", 0)

        tutarlar = []
        firmalar = []
        for i in range(n):
            item_firma = self._teklif_tablo.item(i, 1)
            item_tutar = self._teklif_tablo.item(i, 2)
            if item_firma and item_tutar:
                firmalar.append(item_firma.text())
                try:
                    tutarlar.append(float(item_tutar.text().replace(",", "")))
                except ValueError:
                    tutarlar.append(0.0)

        tutarlar_sirali = sorted(tutarlar)
        en_dusuk  = tutarlar_sirali[0]
        en_yuksek = tutarlar_sirali[-1]
        kalan     = tutarlar_sirali[1:-1]
        ortalama  = sum(kalan) / len(kalan) if kalan else 0
        kik_sinir = ortalama * 0.80

        # Tablo renklendir
        for i in range(n):
            item_tutar = self._teklif_tablo.item(i, 2)
            item_durum = self._teklif_tablo.item(i, 3)
            if item_tutar is None:
                continue
            try:
                t = float(item_tutar.text().replace(",", ""))
            except ValueError:
                continue
            if t < kik_sinir:
                durum = "Aşırı Düşük"
                renk  = QColor(RED)
            else:
                durum = "Geçerli"
                renk  = QColor(GREEN)
            if item_durum:
                item_durum.setText(durum)
                item_durum.setForeground(QBrush(renk))
            item_tutar.setForeground(QBrush(renk))

        # Sonuç metni
        lines = [
            "=" * 55,
            f"  KİK Madde 38 — Aşırı Düşük Teklif Analizi",
            "=" * 55,
            f"  Yaklaşık Maliyet        : {_para_str(ym)}",
            f"  Toplam Teklif Sayısı    : {n}",
            f"  En Düşük Teklif         : {_para_str(en_dusuk)}",
            f"  En Yüksek Teklif        : {_para_str(en_yuksek)}",
            f"  Kalan {n - 2} Teklif Ortalaması: {_para_str(ortalama)}",
            f"  KİK Sınır (Ort × 0.80) : {_para_str(kik_sinir)}",
            "-" * 55,
            f"  Sınırın altındaki teklifler → Aşırı Düşük",
        ]
        self._sonuc_text.setPlainText("\n".join(lines))


# ════════════════════════════════════════════════════════════════════════════
# YARDIMCI: Metraj → Keşif Aktarım Diyaloğu
# ════════════════════════════════════════════════════════════════════════════

class _MetrajAktarDialog(QDialog):
    """Mevcut projelerdeki metraj kalemlerini keşif cetveline aktarma diyaloğu."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self._db = db
        self._secilen = []
        self.setWindowTitle("Metrajdan Keşif Cetveline Aktar")
        self.setMinimumSize(860, 580)
        self.setStyleSheet(f"background-color:{DARK_BG}; color:{TEXT_WHITE};")
        self._setup_ui()
        self._projeleri_yukle()

    def _setup_ui(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(12, 12, 12, 12)
        ana.setSpacing(8)

        # Proje seçimi
        proje_lay = QHBoxLayout()
        lbl = QLabel("Proje:")
        lbl.setStyleSheet(f"color:{TEXT_GRAY}; font-weight:bold;")
        self._proje_combo = QComboBox()
        self._proje_combo.setStyleSheet(_input_stili())
        self._proje_combo.currentIndexChanged.connect(self._proje_degisti)
        proje_lay.addWidget(lbl)
        proje_lay.addWidget(self._proje_combo, 1)
        ana.addLayout(proje_lay)

        self._bilgi_lbl = QLabel("Proje seçin — metraj kalemleri yüklenecek.")
        self._bilgi_lbl.setStyleSheet(f"color:{TEXT_GRAY}; font-size:11px;")
        ana.addWidget(self._bilgi_lbl)

        # Kalemler tablosu
        self._tablo = QTableWidget(0, 6)
        self._tablo.setHorizontalHeaderLabels(
            ["✓", "Poz No", "Tanım", "Birim", "Miktar", "Birim Fiyat (TL)"]
        )
        self._tablo.setStyleSheet(_tablo_stili())
        self._tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tablo.verticalHeader().setVisible(False)
        self._tablo.setAlternatingRowColors(True)
        self._tablo.setColumnWidth(0, 32)
        self._tablo.cellClicked.connect(self._checkbox_toggle)
        ana.addWidget(self._tablo, 1)

        # Alt araç çubuğu
        arac_lay = QHBoxLayout()
        tumunu_btn = QPushButton("Tümünü Seç")
        tumunu_btn.setStyleSheet(_btn_stili(TEXT_GRAY))
        tumunu_btn.clicked.connect(self._tumunu_sec)
        kaldır_btn = QPushButton("Seçimi Kaldır")
        kaldır_btn.setStyleSheet(_btn_stili(TEXT_GRAY))
        kaldır_btn.clicked.connect(self._secimi_kaldir)
        arac_lay.addWidget(tumunu_btn)
        arac_lay.addWidget(kaldır_btn)
        arac_lay.addStretch()
        self._secim_lbl = QLabel("0 kalem seçildi")
        self._secim_lbl.setStyleSheet(f"color:{ACCENT}; font-weight:bold;")
        arac_lay.addWidget(self._secim_lbl)
        ana.addLayout(arac_lay)

        not_lbl = QLabel(
            "Not: Birim fiyatı 0 olan kalemler de aktarılabilir; "
            "fiyatı keşif cetvelinde manuel girebilirsiniz."
        )
        not_lbl.setStyleSheet(f"color:{TEXT_GRAY}; font-size:11px; font-style:italic;")
        not_lbl.setWordWrap(True)
        ana.addWidget(not_lbl)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Aktar")
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("İptal")
        btn_box.accepted.connect(self._aktarimi_onayla)
        btn_box.rejected.connect(self.reject)
        btn_box.setStyleSheet(f"color:{TEXT_WHITE};")
        ana.addWidget(btn_box)

    def _projeleri_yukle(self):
        try:
            projeler = self._db.get_all_projects()
        except Exception as e:
            logger.error(f"Proje listesi alınamadı: {e}")
            projeler = []
        self._proje_combo.blockSignals(True)
        self._proje_combo.clear()
        self._proje_combo.addItem("-- Proje Seçin --", None)
        for p in projeler:
            ad = p.get("ad") or p.get("name") or f"Proje #{p.get('id', '?')}"
            self._proje_combo.addItem(ad, p.get("id"))
        self._proje_combo.blockSignals(False)

    def _proje_degisti(self):
        proje_id = self._proje_combo.currentData()
        if proje_id is None:
            self._tablo.setRowCount(0)
            self._bilgi_lbl.setText("Proje seçin — metraj kalemleri yüklenecek.")
            return
        try:
            with self._db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, poz_no, tanim, birim, miktar, birim_fiyat, kategori "
                    "FROM metraj_kalemleri WHERE proje_id = ? ORDER BY id",
                    (proje_id,)
                )
                kalemler = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Metraj kalem sorgusu hatası: {e}")
            kalemler = []

        self._tablo.blockSignals(True)
        self._tablo.setRowCount(0)
        for kal in kalemler:
            r = self._tablo.rowCount()
            self._tablo.insertRow(r)
            chk = QTableWidgetItem("☐")
            chk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            chk.setForeground(QBrush(QColor(ACCENT)))
            chk.setData(Qt.ItemDataRole.UserRole, kal)
            self._tablo.setItem(r, 0, chk)
            self._tablo.setItem(r, 1, QTableWidgetItem(kal.get("poz_no") or ""))
            self._tablo.setItem(r, 2, QTableWidgetItem(kal.get("tanim") or ""))
            self._tablo.setItem(r, 3, QTableWidgetItem(kal.get("birim") or ""))
            m_item = QTableWidgetItem(f"{float(kal.get('miktar') or 0):,.3f}")
            m_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._tablo.setItem(r, 4, m_item)
            f_item = QTableWidgetItem(f"{float(kal.get('birim_fiyat') or 0):,.2f}")
            f_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._tablo.setItem(r, 5, f_item)
        self._tablo.blockSignals(False)
        self._bilgi_lbl.setText(
            f"{len(kalemler)} metraj kalemi yüklendi — aktarmak istediklerinizi seçin."
        )
        self._secim_sayisi_guncelle()

    def _checkbox_toggle(self, row, col):
        if col != 0:
            return
        item = self._tablo.item(row, 0)
        if item is None:
            return
        if item.text() == "☐":
            item.setText("☑")
            item.setForeground(QBrush(QColor(GREEN)))
        else:
            item.setText("☐")
            item.setForeground(QBrush(QColor(ACCENT)))
        self._secim_sayisi_guncelle()

    def _tumunu_sec(self):
        for r in range(self._tablo.rowCount()):
            item = self._tablo.item(r, 0)
            if item:
                item.setText("☑")
                item.setForeground(QBrush(QColor(GREEN)))
        self._secim_sayisi_guncelle()

    def _secimi_kaldir(self):
        for r in range(self._tablo.rowCount()):
            item = self._tablo.item(r, 0)
            if item:
                item.setText("☐")
                item.setForeground(QBrush(QColor(ACCENT)))
        self._secim_sayisi_guncelle()

    def _secim_sayisi_guncelle(self):
        n = sum(
            1 for r in range(self._tablo.rowCount())
            if self._tablo.item(r, 0) and self._tablo.item(r, 0).text() == "☑"
        )
        self._secim_lbl.setText(f"{n} kalem seçildi")

    def _aktarimi_onayla(self):
        self._secilen = []
        for r in range(self._tablo.rowCount()):
            item = self._tablo.item(r, 0)
            if item and item.text() == "☑":
                kal = item.data(Qt.ItemDataRole.UserRole)
                if kal:
                    self._secilen.append(kal)
        if not self._secilen:
            QMessageBox.warning(self, "Uyarı", "En az bir kalem seçin.")
            return
        self.accept()

    def secilen_kalemler(self) -> list:
        return self._secilen


# ════════════════════════════════════════════════════════════════════════════
# ANA PENCERE
# ════════════════════════════════════════════════════════════════════════════

class YaklasikMaliyetWindow(QWidget):
    """
    Yaklaşık Maliyet ve Keşif Özeti ana penceresi.

    4734 KİK kapsamında keşif cetveli hazırlama, poz arama,
    KDV hesaplama ve aşırı düşük teklif analizi.
    """

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yaklaşık Maliyet & Keşif Cetveli")
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(f"background-color:{DARK_BG}; color:{TEXT_WHITE};")

        self._db = db
        self._engine = YaklasikMaliyetEngine()
        self._setup_ui()

    # ── Arayüz ───────────────────────────────────────────────────────────

    def _setup_ui(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(8, 8, 8, 4)
        ana.setSpacing(4)

        # Başlık
        baslik = QLabel("Yaklaşık Maliyet & Keşif Cetveli")
        baslik.setStyleSheet(f"color:{ACCENT}; font-size:18px; font-weight:bold;")
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ana.addWidget(baslik)

        # Sekmeler
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid #2a2a4a;
                background-color: {DARK_BG};
            }}
            QTabBar::tab {{
                background-color: {CARD_BG};
                color: {TEXT_GRAY};
                padding: 8px 20px;
                border: 1px solid #2a2a4a;
            }}
            QTabBar::tab:selected {{
                background-color: #0f3460;
                color: {TEXT_WHITE};
                font-weight: bold;
            }}
        """)

        self._sekme_kesif    = _KesifCetveliSekmesi(self._engine, db=self._db)
        self._sekme_ozet     = _OzetKdvSekmesi(self._engine)
        self._sekme_kategori = _KategoriSekmesi(self._engine)
        self._sekme_analiz   = _AsiriDusukSekmesi(self._engine)

        self._tabs.addTab(self._sekme_kesif,    "Keşif Cetveli")
        self._tabs.addTab(self._sekme_ozet,     "Özet & KDV")
        self._tabs.addTab(self._sekme_kategori, "Kategori Dağılımı")
        self._tabs.addTab(self._sekme_analiz,   "Aşırı Düşük Analizi")

        self._sekme_kesif.kalem_eklendi.connect(self._tum_sekmeleri_guncelle)
        self._tabs.currentChanged.connect(self._sekme_degisti)

        ana.addWidget(self._tabs, 1)

        # Durum çubuğu
        self._durum = QStatusBar()
        self._durum.setStyleSheet(f"background-color:{CARD_BG}; color:{TEXT_GRAY}; font-size:11px;")
        self._sekme_kesif.durum_guncelle.connect(self._durum.showMessage)
        ana.addWidget(self._durum)

        # İlk yükleme
        self._sekme_kesif._poz_listele()
        self._durum.showMessage("Hazır — Poz listesinden kalem seçin, miktar girerek keşif cetvelini oluşturun.")

    def _sekme_degisti(self, index: int):
        if index == 1:
            self._sekme_ozet.yenile()
        elif index == 2:
            self._sekme_kategori.yenile()
        elif index == 3:
            self._sekme_analiz.yenile()

    def _tum_sekmeleri_guncelle(self):
        self._sekme_ozet.yenile()
        self._sekme_kategori.yenile()
        self._sekme_analiz.yenile()
