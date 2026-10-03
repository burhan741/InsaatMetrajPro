"""
atasaman_window.py — Ataşman Belgesi Penceresi
===============================================
4735 sayılı KİK kapsamında şantiye saha ölçüm tutanağı yönetimi.
3 sekme: Belgeler | Ölçü Cetveli | Özet & Çıktı
Rev-78 (2026-04-26)
"""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QBrush, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QListWidget, QListWidgetItem, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox,
    QDoubleSpinBox, QSpinBox, QGridLayout, QFrame, QMessageBox,
    QFileDialog, QToolBar, QSizePolicy, QAbstractItemView,
    QTabWidget, QTextEdit, QGroupBox, QScrollArea, QDateEdit,
    QProgressBar,
)
from PyQt6.QtCore import QDate

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Renk şeması (BFA ile tutarlı)
# ──────────────────────────────────────────────────────────────────────────────
DARK_BG    = "#1a1a2e"
CARD_BG    = "#16213e"
ACCENT     = "#00BFFF"
TEXT_WHITE = "#e0e0e0"
TEXT_GRAY  = "#a0a0b0"
GREEN      = "#27ae60"
RED        = "#e74c3c"
ORANGE     = "#f39c12"
BLUE       = "#2980b9"

# ──────────────────────────────────────────────────────────────────────────────
# Engine import — hata toleranslı
# ──────────────────────────────────────────────────────────────────────────────
try:
    from app.core.atasaman_engine import (
        AtasamanEngine, ELEMAN_TIPLERI, DESTEKLENEN_BIRIMLER,
    )
    _ENGINE_OK = True
except Exception as _e:
    logger.error("AtasamanEngine import hatası: %s", _e)
    _ENGINE_OK = False
    ELEMAN_TIPLERI = [
        "Kolon", "Kiriş", "Döşeme", "Perde", "Temel",
        "Merdiven", "Rampa", "Hatıl", "Lento", "Serbest",
    ]
    DESTEKLENEN_BIRIMLER = ["m³", "m²", "m", "adet"]

    class AtasamanEngine:  # type: ignore[no-redef]
        def belge_olustur(self, **kw) -> int:
            return -1
        def belge_guncelle(self, *a, **kw) -> bool:
            return False
        def belge_sil(self, *a) -> bool:
            return False
        def tum_belgeler(self, *a) -> list:
            return []
        def belge_getir(self, *a):
            return None
        def kalem_ekle(self, *a, **kw) -> int:
            return -1
        def kalem_guncelle(self, *a, **kw) -> bool:
            return False
        def kalem_sil(self, *a) -> bool:
            return False
        def foto_ekle(self, *a, **kw) -> bool:
            return False
        def toplam_hesapla(self, *a) -> dict:
            return {"m³": 0.0, "m²": 0.0, "m": 0.0, "adet": 0.0,
                    "kalem_sayisi": 0, "brut_toplam": 0.0, "net_toplam": 0.0}
        def pdf_atasaman_belgesi_uret(self, *a) -> bool:
            return False
        def excel_disari_aktar(self, *a) -> bool:
            return False


def _btn(metin: str, renk: str = ACCENT, bold: bool = False) -> QPushButton:
    """Stil uygulanmış buton yardımcısı."""
    btn = QPushButton(metin)
    agirlik = "bold" if bold else "normal"
    btn.setStyleSheet(
        f"QPushButton {{ background:{renk}; color:#fff; font-weight:{agirlik};"
        f"border-radius:5px; padding:5px 12px; }}"
        f"QPushButton:hover {{ background:{renk}dd; }}"
        f"QPushButton:disabled {{ background:#555; color:#999; }}"
    )
    return btn


def _label(metin: str, kalin: bool = False, renk: str = TEXT_WHITE) -> QLabel:
    lbl = QLabel(metin)
    lbl.setStyleSheet(
        f"color:{renk}; font-weight:{'bold' if kalin else 'normal'};"
    )
    return lbl


def _ayirici() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background:{TEXT_GRAY}; max-height:1px;")
    return f


# ──────────────────────────────────────────────────────────────────────────────
# Vision API Thread
# ──────────────────────────────────────────────────────────────────────────────
class _VisionThread(QThread):
    """Claude Vision API ile fotoğraftan boyut çıkarımı."""
    tamamlandi = pyqtSignal(str)   # sonuç metni
    hata = pyqtSignal(str)

    def __init__(self, foto_yolu: str, parent=None):
        super().__init__(parent)
        self._foto_yolu = foto_yolu

    def run(self):
        try:
            import anthropic
        except ImportError:
            self.hata.emit("anthropic paketi kurulu değil (pip install anthropic)")
            return

        try:
            with open(self._foto_yolu, "rb") as f:
                veri = f.read()
            b64 = base64.standard_b64encode(veri).decode("ascii")

            # MIME tipi tespiti
            uzanti = Path(self._foto_yolu).suffix.lower()
            mime_harita = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }
            mime = mime_harita.get(uzanti, "image/jpeg")

            client = anthropic.Anthropic()
            yanit = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime,
                                    "data": b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Bu fotoğraf bir inşaat şantiyesindeki yapı elemanının ölçümünü gösteriyor. "
                                    "Fotoğraftaki boyutları veya ölçü bandı değerlerini oku. "
                                    "Yanıtını şu JSON formatında ver (başka açıklama ekleme):\n"
                                    "{\n"
                                    '  "eleman_tipi": "Kolon/Kiriş/Döşeme/Perde/vb",\n'
                                    '  "tanim": "kısa açıklama",\n'
                                    '  "en_m": 0.00,\n'
                                    '  "boy_m": 0.00,\n'
                                    '  "yukseklik_m": 0.00,\n'
                                    '  "adet": 1,\n'
                                    '  "birim": "m³/m²/m/adet",\n'
                                    '  "notlar": "gözlem notları"\n'
                                    "}\n"
                                    "Ölçü değerleri fotoğrafta görünmüyorsa 0 yaz. "
                                    "Sadece JSON döndür, başka metin ekleme."
                                ),
                            },
                        ],
                    }
                ],
            )
            metin = yanit.content[0].text.strip()
            self.tamamlandi.emit(metin)
        except Exception as e:
            self.hata.emit(str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Yeni Belge / Düzenle Dialog
# ──────────────────────────────────────────────────────────────────────────────
class _YeniBelgeDialog(QDialog):
    def __init__(self, parent=None, belge: Optional[Dict] = None):
        super().__init__(parent)
        self._duzenleme = belge is not None
        baslik = "Belgeyi Düzenle" if self._duzenleme else "Yeni Ataşman Belgesi"
        self.setWindowTitle(baslik)
        self.setMinimumWidth(520)
        self.setStyleSheet(
            f"QDialog {{ background:{DARK_BG}; color:{TEXT_WHITE}; }}"
            f"QLineEdit, QDateEdit, QTextEdit {{ background:{CARD_BG}; color:{TEXT_WHITE};"
            f"border:1px solid #444; border-radius:4px; padding:4px; }}"
            f"QLabel {{ color:{TEXT_WHITE}; }}"
            f"QFormLayout {{ spacing:8px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        self._belge_no = QLineEdit()
        self._belge_no.setPlaceholderText("AT-2026-001")

        self._belge_tarihi = QDateEdit()
        self._belge_tarihi.setCalendarPopup(True)
        self._belge_tarihi.setDate(QDate.currentDate())
        self._belge_tarihi.setDisplayFormat("dd.MM.yyyy")

        self._yuklenci = QLineEdit()
        self._yuklenci.setPlaceholderText("ABC İnşaat A.Ş.")

        self._idare = QLineEdit()
        self._idare.setPlaceholderText("Ankara Büyükşehir Belediyesi")

        self._kontrol_muh = QLineEdit()
        self._kontrol_muh.setPlaceholderText("İnş. Müh. Ahmet Yılmaz (Sicil: 12345)")

        self._yapim_tarihi = QLineEdit()
        self._yapim_tarihi.setPlaceholderText("Nisan 2026 / 10.04.2026 - 25.04.2026")

        self._aciklama = QTextEdit()
        self._aciklama.setMaximumHeight(70)
        self._aciklama.setPlaceholderText("Proje adı veya serbest açıklama...")

        form.addRow("Belge No *:", self._belge_no)
        form.addRow("Belge Tarihi:", self._belge_tarihi)
        form.addRow("Yüklenici:", self._yuklenci)
        form.addRow("İdare:", self._idare)
        form.addRow("Kontrol Müh.:", self._kontrol_muh)
        form.addRow("Yapım Tarihi/Dönemi:", self._yapim_tarihi)
        form.addRow("Açıklama:", self._aciklama)

        layout.addLayout(form)

        butonlar = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        butonlar.button(QDialogButtonBox.StandardButton.Ok).setText("Kaydet")
        butonlar.button(QDialogButtonBox.StandardButton.Cancel).setText("İptal")
        butonlar.accepted.connect(self._kabul_et)
        butonlar.rejected.connect(self.reject)
        butonlar.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:#fff; border-radius:4px;"
            f"padding:5px 14px; }}"
            f"QPushButton:hover {{ background:{ACCENT}cc; }}"
        )
        layout.addWidget(butonlar)

        if belge:
            self._doldur(belge)

    def _doldur(self, belge: Dict) -> None:
        self._belge_no.setText(belge.get("belge_no", ""))
        tarih_str = belge.get("belge_tarihi", "")
        if tarih_str:
            try:
                t = datetime.strptime(tarih_str, "%Y-%m-%d")
                self._belge_tarihi.setDate(QDate(t.year, t.month, t.day))
            except Exception:
                pass
        self._yuklenci.setText(belge.get("yuklenci", ""))
        self._idare.setText(belge.get("idare", ""))
        self._kontrol_muh.setText(belge.get("kontrol_muhendisi", ""))
        self._yapim_tarihi.setText(belge.get("yapim_tarihi", ""))
        self._aciklama.setPlainText(belge.get("aciklama", ""))

    def _kabul_et(self) -> None:
        if not self._belge_no.text().strip():
            QMessageBox.warning(self, "Uyarı", "Belge No zorunludur.")
            return
        self.accept()

    def deger(self) -> Dict[str, Any]:
        q_tarih = self._belge_tarihi.date()
        return {
            "belge_no": self._belge_no.text().strip(),
            "belge_tarihi": f"{q_tarih.year():04d}-{q_tarih.month():02d}-{q_tarih.day():02d}",
            "yuklenci": self._yuklenci.text().strip(),
            "idare": self._idare.text().strip(),
            "kontrol_muhendisi": self._kontrol_muh.text().strip(),
            "yapim_tarihi": self._yapim_tarihi.text().strip(),
            "aciklama": self._aciklama.toPlainText().strip(),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Kalem Ekle / Düzenle Dialog
# ──────────────────────────────────────────────────────────────────────────────
class _KalemDialog(QDialog):
    def __init__(self, parent=None, kalem: Optional[Dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Kalem Düzenle" if kalem else "Yeni Ölçüm Kalemi")
        self.setMinimumWidth(480)
        self.setStyleSheet(
            f"QDialog {{ background:{DARK_BG}; color:{TEXT_WHITE}; }}"
            f"QLineEdit, QComboBox, QDoubleSpinBox {{ background:{CARD_BG}; color:{TEXT_WHITE};"
            f"border:1px solid #444; border-radius:4px; padding:4px; }}"
            f"QComboBox::drop-down {{ border:none; }}"
            f"QLabel {{ color:{TEXT_WHITE}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self._eleman = QComboBox()
        self._eleman.addItems(ELEMAN_TIPLERI)

        self._tanim = QLineEdit()
        self._tanim.setPlaceholderText("Zemin kat B aksı kolonları")

        self._poz_no = QLineEdit()
        self._poz_no.setPlaceholderText("21.003")

        self._birim = QComboBox()
        self._birim.addItems(DESTEKLENEN_BIRIMLER)
        self._birim.currentTextChanged.connect(self._birim_degisti)

        boyut_widget = QWidget()
        boyut_widget.setStyleSheet("background:transparent;")
        boyut_layout = QGridLayout(boyut_widget)
        boyut_layout.setContentsMargins(0, 0, 0, 0)
        boyut_layout.setSpacing(6)

        self._en = QDoubleSpinBox()
        self._en.setRange(0, 9999)
        self._en.setDecimals(3)
        self._en.setSuffix(" m")

        self._boy = QDoubleSpinBox()
        self._boy.setRange(0, 9999)
        self._boy.setDecimals(3)
        self._boy.setSuffix(" m")

        self._yukseklik = QDoubleSpinBox()
        self._yukseklik.setRange(0, 9999)
        self._yukseklik.setDecimals(3)
        self._yukseklik.setSuffix(" m")

        self._adet = QDoubleSpinBox()
        self._adet.setRange(0, 9999)
        self._adet.setDecimals(2)
        self._adet.setValue(1.0)

        self._cikarilan = QDoubleSpinBox()
        self._cikarilan.setRange(0, 99999)
        self._cikarilan.setDecimals(4)

        self._lbl_en = QLabel("En (m):")
        self._lbl_yukseklik = QLabel("Yükseklik (m):")

        boyut_layout.addWidget(self._lbl_en, 0, 0)
        boyut_layout.addWidget(self._en, 0, 1)
        boyut_layout.addWidget(QLabel("Boy (m):"), 0, 2)
        boyut_layout.addWidget(self._boy, 0, 3)
        boyut_layout.addWidget(self._lbl_yukseklik, 1, 0)
        boyut_layout.addWidget(self._yukseklik, 1, 1)
        boyut_layout.addWidget(QLabel("Adet:"), 1, 2)
        boyut_layout.addWidget(self._adet, 1, 3)

        self._notlar = QLineEdit()
        self._notlar.setPlaceholderText("Serbest not...")

        form.addRow("Eleman Tipi:", self._eleman)
        form.addRow("Tanım:", self._tanim)
        form.addRow("Poz No:", self._poz_no)
        form.addRow("Birim:", self._birim)
        form.addRow("Boyutlar:", boyut_widget)
        form.addRow("Çıkarılan:", self._cikarilan)
        form.addRow("Notlar:", self._notlar)

        layout.addLayout(form)

        # Anlık hesap göstergesi
        self._hesap_lbl = QLabel("Brüt: 0.0000 | Net: 0.0000")
        self._hesap_lbl.setStyleSheet(
            f"color:{GREEN}; font-weight:bold; font-size:13px;"
            f"background:{CARD_BG}; padding:6px; border-radius:4px;"
        )
        self._hesap_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hesap_lbl)

        for spin in [self._en, self._boy, self._yukseklik, self._adet, self._cikarilan]:
            spin.valueChanged.connect(self._hesap_guncelle)
        self._birim.currentTextChanged.connect(self._hesap_guncelle)

        butonlar = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        butonlar.button(QDialogButtonBox.StandardButton.Ok).setText("Kaydet")
        butonlar.button(QDialogButtonBox.StandardButton.Cancel).setText("İptal")
        butonlar.accepted.connect(self.accept)
        butonlar.rejected.connect(self.reject)
        butonlar.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:#fff; border-radius:4px;"
            f"padding:5px 14px; }}"
        )
        layout.addWidget(butonlar)

        if kalem:
            self._doldur(kalem)
        self._birim_degisti(self._birim.currentText())
        self._hesap_guncelle()

    def _birim_degisti(self, birim: str) -> None:
        """Birime göre boyut alanlarını göster/gizle."""
        goster_en = birim in ("m³", "m²")
        goster_yukseklik = birim == "m³"
        self._lbl_en.setVisible(goster_en)
        self._en.setVisible(goster_en)
        self._lbl_yukseklik.setVisible(goster_yukseklik)
        self._yukseklik.setVisible(goster_yukseklik)

    def _hesap_guncelle(self) -> None:
        """Anlık brüt/net hesapla ve göster."""
        en = self._en.value()
        boy = self._boy.value()
        yukseklik = self._yukseklik.value()
        adet = self._adet.value()
        cikarilan = self._cikarilan.value()
        birim = self._birim.currentText()

        if birim == "m³":
            brut = en * boy * yukseklik * adet
        elif birim == "m²":
            brut = en * boy * adet
        elif birim == "m":
            brut = boy * adet
        else:
            brut = adet

        brut = max(0.0, round(brut, 4))
        net = max(0.0, round(brut - cikarilan, 4))
        self._hesap_lbl.setText(
            f"Brüt: {brut:.4f} {birim}  |  Net: {net:.4f} {birim}"
        )

    def _doldur(self, kalem: Dict) -> None:
        idx = self._eleman.findText(kalem.get("eleman_tipi", "Serbest"))
        if idx >= 0:
            self._eleman.setCurrentIndex(idx)
        self._tanim.setText(kalem.get("tanim", ""))
        self._poz_no.setText(kalem.get("poz_no", ""))
        birim_idx = self._birim.findText(kalem.get("birim", "m³"))
        if birim_idx >= 0:
            self._birim.setCurrentIndex(birim_idx)
        self._en.setValue(float(kalem.get("en", 0.0)))
        self._boy.setValue(float(kalem.get("boy", 0.0)))
        self._yukseklik.setValue(float(kalem.get("yukseklik", 0.0)))
        self._adet.setValue(float(kalem.get("adet", 1.0)))
        self._cikarilan.setValue(float(kalem.get("cikarilan", 0.0)))
        self._notlar.setText(kalem.get("notlar", ""))

    def deger(self) -> Dict[str, Any]:
        return {
            "eleman_tipi": self._eleman.currentText(),
            "tanim": self._tanim.text().strip(),
            "poz_no": self._poz_no.text().strip(),
            "birim": self._birim.currentText(),
            "en": self._en.value(),
            "boy": self._boy.value(),
            "yukseklik": self._yukseklik.value(),
            "adet": self._adet.value(),
            "cikarilan": self._cikarilan.value(),
            "notlar": self._notlar.text().strip(),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Yapay Zeka Boyut Dialog (Vision API)
# ──────────────────────────────────────────────────────────────────────────────
class _YapayZekaBoyutDialog(QDialog):
    """Claude Vision ile fotoğraftan boyut çıkarımı."""

    boyutlar_belirlendi = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yapay Zeka — Fotoğraftan Boyut Çıkar")
        self.setMinimumWidth(580)
        self.setMinimumHeight(480)
        self.setStyleSheet(
            f"QDialog {{ background:{DARK_BG}; color:{TEXT_WHITE}; }}"
            f"QTextEdit {{ background:{CARD_BG}; color:{TEXT_WHITE};"
            f"border:1px solid #444; border-radius:4px; }}"
            f"QLabel {{ color:{TEXT_WHITE}; }}"
        )

        self._foto_yolu: Optional[str] = None
        self._thread: Optional[_VisionThread] = None
        self._sonuc_json: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Açıklama
        aciklama = QLabel(
            "Şantiye fotoğrafı yükleyin. Claude Vision ölçü bandı veya "
            "görünür boyutları otomatik okur."
        )
        aciklama.setWordWrap(True)
        aciklama.setStyleSheet(f"color:{TEXT_GRAY}; font-size:12px;")
        layout.addWidget(aciklama)

        # Fotoğraf seçme
        foto_layout = QHBoxLayout()
        self._foto_lbl = QLabel("Fotoğraf seçilmedi")
        self._foto_lbl.setStyleSheet(
            f"color:{TEXT_GRAY}; background:{CARD_BG}; padding:6px;"
            f"border:1px solid #444; border-radius:4px;"
        )
        self._foto_lbl.setWordWrap(True)
        foto_sec_btn = _btn("Fotoğraf Seç", BLUE)
        foto_sec_btn.clicked.connect(self._foto_sec)
        foto_layout.addWidget(self._foto_lbl, 1)
        foto_layout.addWidget(foto_sec_btn)
        layout.addLayout(foto_layout)

        # Fotoğraf önizleme
        self._onizleme = QLabel()
        self._onizleme.setFixedHeight(160)
        self._onizleme.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._onizleme.setStyleSheet(
            f"background:{CARD_BG}; border:1px solid #333; border-radius:4px;"
        )
        self._onizleme.setText("Önizleme görünecek")
        layout.addWidget(self._onizleme)

        # Analiz butonu + progress
        analiz_layout = QHBoxLayout()
        self._analiz_btn = _btn("Yapay Zeka ile Analiz Et", GREEN, bold=True)
        self._analiz_btn.setEnabled(False)
        self._analiz_btn.clicked.connect(self._analiz_baslat)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setStyleSheet(
            "QProgressBar { border:none; background:#333; border-radius:3px; }"
            f"QProgressBar::chunk {{ background:{ACCENT}; border-radius:3px; }}"
        )
        analiz_layout.addWidget(self._analiz_btn)
        analiz_layout.addWidget(self._progress)
        layout.addLayout(analiz_layout)

        # Sonuç
        self._sonuc_edit = QTextEdit()
        self._sonuc_edit.setPlaceholderText(
            "Analiz sonucu burada görünecek (JSON formatında)..."
        )
        self._sonuc_edit.setMaximumHeight(120)
        layout.addWidget(QLabel("Analiz Sonucu:"))
        layout.addWidget(self._sonuc_edit)

        # Butonlar
        butonlar = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._tamam_btn = butonlar.button(QDialogButtonBox.StandardButton.Ok)
        self._tamam_btn.setText("Kaleme Uygula")
        self._tamam_btn.setEnabled(False)
        butonlar.button(QDialogButtonBox.StandardButton.Cancel).setText("İptal")
        butonlar.accepted.connect(self._uygula)
        butonlar.rejected.connect(self.reject)
        butonlar.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:#fff; border-radius:4px;"
            f"padding:5px 14px; }}"
            f"QPushButton:disabled {{ background:#555; color:#999; }}"
        )
        layout.addWidget(butonlar)

    def _foto_sec(self) -> None:
        yol, _ = QFileDialog.getOpenFileName(
            self, "Fotoğraf Seç", "",
            "Görüntü Dosyaları (*.jpg *.jpeg *.png *.webp *.gif)"
        )
        if not yol:
            return
        self._foto_yolu = yol
        self._foto_lbl.setText(Path(yol).name)
        pix = QPixmap(yol)
        if not pix.isNull():
            self._onizleme.setPixmap(
                pix.scaled(
                    self._onizleme.width(), self._onizleme.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._analiz_btn.setEnabled(True)

    def _analiz_baslat(self) -> None:
        if not self._foto_yolu:
            return
        self._analiz_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._sonuc_edit.setPlainText("Analiz ediliyor...")

        self._thread = _VisionThread(self._foto_yolu, self)
        self._thread.tamamlandi.connect(self._analiz_tamamlandi)
        self._thread.hata.connect(self._analiz_hata)
        self._thread.start()

    def _analiz_tamamlandi(self, sonuc: str) -> None:
        self._progress.setVisible(False)
        self._analiz_btn.setEnabled(True)
        self._sonuc_json = sonuc
        self._sonuc_edit.setPlainText(sonuc)
        self._tamam_btn.setEnabled(True)

    def _analiz_hata(self, hata: str) -> None:
        self._progress.setVisible(False)
        self._analiz_btn.setEnabled(True)
        self._sonuc_edit.setPlainText(f"HATA: {hata}")
        QMessageBox.warning(self, "Analiz Hatası", hata)

    def _uygula(self) -> None:
        if not self._sonuc_json:
            self.accept()
            return
        import json
        try:
            # JSON bloğu temizle
            metin = self._sonuc_json.strip()
            if "```" in metin:
                metin = metin.split("```")[1]
                if metin.startswith("json"):
                    metin = metin[4:]
            veri = json.loads(metin.strip())
            self.boyutlar_belirlendi.emit(veri)
        except Exception as e:
            QMessageBox.warning(
                self, "Parse Hatası",
                f"JSON parse hatası: {e}\nSonucu manuel düzenleyin."
            )
        self.accept()

    def foto_yolu(self) -> Optional[str]:
        return self._foto_yolu


# ──────────────────────────────────────────────────────────────────────────────
# Sekme 1: Belgeler
# ──────────────────────────────────────────────────────────────────────────────
class _BelgelerSekmesi(QWidget):
    belge_secildi = pyqtSignal(int)  # belge_id

    def __init__(self, engine: AtasamanEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._secili_belge_id: Optional[int] = None
        self._kur_ui()
        self.yenile()

    def _kur_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Sol panel — belge listesi
        sol = QWidget()
        sol_layout = QVBoxLayout(sol)
        sol_layout.setContentsMargins(0, 0, 0, 0)
        sol_layout.setSpacing(6)

        sol_baslik = _label("Ataşman Belgeleri", kalin=True)
        sol_layout.addWidget(sol_baslik)
        sol_layout.addWidget(_ayirici())

        self._belge_listesi = QListWidget()
        self._belge_listesi.setStyleSheet(
            f"QListWidget {{ background:{CARD_BG}; color:{TEXT_WHITE};"
            f"border:1px solid #333; border-radius:4px; }}"
            f"QListWidget::item:selected {{ background:{ACCENT}; color:#fff; }}"
            f"QListWidget::item:hover {{ background:#2c3e50; }}"
        )
        self._belge_listesi.currentRowChanged.connect(self._secim_degisti)
        sol_layout.addWidget(self._belge_listesi, 1)

        btn_layout = QHBoxLayout()
        self._yeni_btn = _btn("+ Yeni Belge", GREEN)
        self._sil_btn = _btn("Sil", RED)
        self._sil_btn.setEnabled(False)
        self._yeni_btn.clicked.connect(self._yeni_belge)
        self._sil_btn.clicked.connect(self._sil_belge)
        btn_layout.addWidget(self._yeni_btn)
        btn_layout.addWidget(self._sil_btn)
        sol_layout.addLayout(btn_layout)

        sol.setFixedWidth(280)
        layout.addWidget(sol)

        # Sağ panel — belge detayları
        sag = QWidget()
        sag_layout = QVBoxLayout(sag)
        sag_layout.setContentsMargins(0, 0, 0, 0)
        sag_layout.setSpacing(8)

        sag_baslik_layout = QHBoxLayout()
        self._detay_baslik = _label("Belge Detayları", kalin=True)
        self._duzenle_btn = _btn("Düzenle", ORANGE)
        self._duzenle_btn.setEnabled(False)
        self._duzenle_btn.clicked.connect(self._duzenle_belge)
        sag_baslik_layout.addWidget(self._detay_baslik)
        sag_baslik_layout.addStretch()
        sag_baslik_layout.addWidget(self._duzenle_btn)
        sag_layout.addLayout(sag_baslik_layout)
        sag_layout.addWidget(_ayirici())

        # Detay grid
        kart = QFrame()
        kart.setStyleSheet(
            f"QFrame {{ background:{CARD_BG}; border-radius:8px; padding:12px; }}"
            f"QLabel {{ color:{TEXT_WHITE}; }}"
        )
        kart_layout = QGridLayout(kart)
        kart_layout.setSpacing(8)

        etiketler = [
            "Belge No:", "Belge Tarihi:", "Yüklenici:", "İdare:",
            "Kontrol Mühendisi:", "Yapım Tarihi/Dönemi:", "Oluşturma Tarihi:",
            "Kalem Sayısı:", "Açıklama:",
        ]
        self._detay_degerler: List[QLabel] = []
        for i, etiket in enumerate(etiketler):
            satir = i // 2
            sutun_baz = (i % 2) * 2
            e_lbl = QLabel(etiket)
            e_lbl.setStyleSheet(f"color:{TEXT_GRAY}; font-weight:bold;")
            d_lbl = QLabel("—")
            d_lbl.setWordWrap(True)
            kart_layout.addWidget(e_lbl, satir, sutun_baz)
            kart_layout.addWidget(d_lbl, satir, sutun_baz + 1)
            self._detay_degerler.append(d_lbl)

        sag_layout.addWidget(kart)
        sag_layout.addStretch()
        layout.addWidget(sag, 1)

    def yenile(self) -> None:
        self._belge_listesi.clear()
        belgeler = self._engine.tum_belgeler()
        for belge in belgeler:
            no = belge.get("belge_no", "—")
            tarih = belge.get("belge_tarihi", "")
            kalem = belge.get("kalem_sayisi", 0)
            item = QListWidgetItem(f"  {no}  |  {tarih}  ({kalem} kalem)")
            item.setData(Qt.ItemDataRole.UserRole, belge["id"])
            self._belge_listesi.addItem(item)
        if self._belge_listesi.count() > 0:
            self._belge_listesi.setCurrentRow(0)

    def _secim_degisti(self, satir: int) -> None:
        item = self._belge_listesi.item(satir)
        if item is None:
            self._secili_belge_id = None
            self._sil_btn.setEnabled(False)
            self._duzenle_btn.setEnabled(False)
            self._detay_temizle()
            return
        belge_id = item.data(Qt.ItemDataRole.UserRole)
        self._secili_belge_id = belge_id
        self._sil_btn.setEnabled(True)
        self._duzenle_btn.setEnabled(True)
        self._detay_doldur(belge_id)
        self.belge_secildi.emit(belge_id)

    def _detay_temizle(self) -> None:
        for lbl in self._detay_degerler:
            lbl.setText("—")

    def _detay_doldur(self, belge_id: int) -> None:
        belge = self._engine.belge_getir(belge_id)
        if belge is None:
            self._detay_temizle()
            return
        kalemler = belge.get("kalemler", [])
        degerler = [
            belge.get("belge_no", "—"),
            belge.get("belge_tarihi", "—"),
            belge.get("yuklenci", "—") or "—",
            belge.get("idare", "—") or "—",
            belge.get("kontrol_muhendisi", "—") or "—",
            belge.get("yapim_tarihi", "—") or "—",
            belge.get("olusturma_tarihi", "—") or "—",
            str(len(kalemler)),
            belge.get("aciklama", "—") or "—",
        ]
        for lbl, deger in zip(self._detay_degerler, degerler):
            lbl.setText(deger)

    def _yeni_belge(self) -> None:
        dlg = _YeniBelgeDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        veri = dlg.deger()
        try:
            belge_id = self._engine.belge_olustur(**veri)
            if belge_id > 0:
                self.yenile()
                # Yeni belgeyi seç
                for i in range(self._belge_listesi.count()):
                    item = self._belge_listesi.item(i)
                    if item and item.data(Qt.ItemDataRole.UserRole) == belge_id:
                        self._belge_listesi.setCurrentRow(i)
                        break
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Belge oluşturulamadı:\n{e}")

    def _sil_belge(self) -> None:
        if self._secili_belge_id is None:
            return
        cevap = QMessageBox.question(
            self, "Belgeyi Sil",
            "Bu belge ve tüm kalemleri silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return
        self._engine.belge_sil(self._secili_belge_id)
        self._secili_belge_id = None
        self.yenile()

    def _duzenle_belge(self) -> None:
        if self._secili_belge_id is None:
            return
        belge = self._engine.belge_getir(self._secili_belge_id)
        if belge is None:
            return
        dlg = _YeniBelgeDialog(self, belge=belge)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        veri = dlg.deger()
        self._engine.belge_guncelle(self._secili_belge_id, **veri)
        self.yenile()
        self._detay_doldur(self._secili_belge_id)

    def secili_belge_id(self) -> Optional[int]:
        return self._secili_belge_id


# ──────────────────────────────────────────────────────────────────────────────
# Sekme 2: Ölçü Cetveli
# ──────────────────────────────────────────────────────────────────────────────
class _OlcuCetveliSekmesi(QWidget):
    def __init__(self, engine: AtasamanEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._belge_id: Optional[int] = None
        self._kur_ui()

    def _kur_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Başlık
        baslik_layout = QHBoxLayout()
        self._baslik_lbl = _label("Belge seçilmedi — Belgeler sekmesinden seçin", kalin=True, renk=TEXT_GRAY)
        baslik_layout.addWidget(self._baslik_lbl)
        baslik_layout.addStretch()
        layout.addLayout(baslik_layout)
        layout.addWidget(_ayirici())

        # Araç çubuğu
        arac = QHBoxLayout()
        self._ekle_btn = _btn("+ Kalem Ekle", GREEN)
        self._duzenle_btn = _btn("Düzenle", ORANGE)
        self._sil_btn = _btn("Sil", RED)
        self._foto_btn = _btn("Fotoğraf Ekle", BLUE)
        self._ai_btn = _btn("AI Boyut Analizi", "#8e44ad")

        self._ekle_btn.setEnabled(False)
        self._duzenle_btn.setEnabled(False)
        self._sil_btn.setEnabled(False)
        self._foto_btn.setEnabled(False)
        self._ai_btn.setEnabled(False)

        self._ekle_btn.clicked.connect(self._kalem_ekle)
        self._duzenle_btn.clicked.connect(self._kalem_duzenle)
        self._sil_btn.clicked.connect(self._kalem_sil)
        self._foto_btn.clicked.connect(self._foto_ekle)
        self._ai_btn.clicked.connect(self._ai_analiz)

        for btn in [self._ekle_btn, self._duzenle_btn, self._sil_btn,
                    self._foto_btn, self._ai_btn]:
            arac.addWidget(btn)
        arac.addStretch()
        layout.addLayout(arac)

        # Tablo
        basliklar = [
            "Sıra", "Eleman Tipi", "Tanım", "Poz No",
            "Birim", "En (m)", "Boy (m)", "Yük. (m)",
            "Adet", "Brüt", "Çıkarılan", "Net Miktar", "Notlar", "Foto",
        ]
        self._tablo = QTableWidget(0, len(basliklar))
        self._tablo.setHorizontalHeaderLabels(basliklar)
        self._tablo.setStyleSheet(
            f"QTableWidget {{ background:{CARD_BG}; color:{TEXT_WHITE};"
            f"gridline-color:#333; border:none; }}"
            f"QHeaderView::section {{ background:#2c3e50; color:{TEXT_WHITE};"
            f"padding:4px; border:none; font-weight:bold; }}"
            f"QTableWidget::item:selected {{ background:{ACCENT}55; }}"
        )
        self._tablo.setAlternatingRowColors(True)
        self._tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tablo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tablo.verticalHeader().setVisible(False)
        self._tablo.setShowGrid(True)
        self._tablo.currentCellChanged.connect(
            lambda row, col, prow, pcol: self._secim_degisti(row)
        )
        layout.addWidget(self._tablo, 1)

        # Alt özet çubuğu
        ozet_layout = QHBoxLayout()
        self._ozet_lbl = QLabel("Seçili belge yok")
        self._ozet_lbl.setStyleSheet(
            f"color:{GREEN}; font-weight:bold; font-size:12px;"
            f"background:{CARD_BG}; padding:4px 8px; border-radius:4px;"
        )
        ozet_layout.addWidget(self._ozet_lbl)
        ozet_layout.addStretch()
        layout.addLayout(ozet_layout)

    def belge_yukle(self, belge_id: int) -> None:
        self._belge_id = belge_id
        belge = self._engine.belge_getir(belge_id)
        if belge:
            no = belge.get("belge_no", "—")
            self._baslik_lbl.setText(f"Ölçü Cetveli — {no}")
            self._baslik_lbl.setStyleSheet(
                f"color:{TEXT_WHITE}; font-weight:bold;"
            )
        for btn in [self._ekle_btn, self._ai_btn]:
            btn.setEnabled(True)
        self.yenile()

    def yenile(self) -> None:
        if self._belge_id is None:
            return
        belge = self._engine.belge_getir(self._belge_id)
        kalemler = belge.get("kalemler", []) if belge else []

        self._tablo.setRowCount(0)
        self._tablo.blockSignals(True)
        for idx, kalem in enumerate(kalemler, start=1):
            satir = self._tablo.rowCount()
            self._tablo.insertRow(satir)
            foto_var = "✓" if kalem.get("foto_yolu") else ""
            degerler = [
                str(idx),
                kalem.get("eleman_tipi", ""),
                kalem.get("tanim", ""),
                kalem.get("poz_no", ""),
                kalem.get("birim", "m³"),
                f"{kalem.get('en', 0):.3f}",
                f"{kalem.get('boy', 0):.3f}",
                f"{kalem.get('yukseklik', 0):.3f}",
                f"{kalem.get('adet', 1):.2f}",
                f"{kalem.get('brut_miktar', 0):.4f}",
                f"{kalem.get('cikarilan', 0):.4f}",
                f"{kalem.get('net_miktar', 0):.4f}",
                kalem.get("notlar", ""),
                foto_var,
            ]
            for col, deger in enumerate(degerler):
                item = QTableWidgetItem(deger)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 11:  # Net Miktar — yeşil
                    item.setForeground(QBrush(QColor(GREEN)))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                item.setData(Qt.ItemDataRole.UserRole, kalem["id"])
                self._tablo.setItem(satir, col, item)

        self._tablo.blockSignals(False)
        self._ozet_guncelle(kalemler)

    def _ozet_guncelle(self, kalemler: List) -> None:
        if not kalemler:
            self._ozet_lbl.setText("Kalem yok")
            return
        toplamlar = self._engine.toplam_hesapla(self._belge_id)
        parcalar = []
        for birim in DESTEKLENED_BIRIMLER if False else DESTEKLENEN_BIRIMLER:
            val = toplamlar.get(birim, 0.0)
            if val > 0:
                parcalar.append(f"{val:.3f} {birim}")
        ozet = "  |  ".join(parcalar) if parcalar else "0"
        self._ozet_lbl.setText(
            f"Toplam Kalem: {len(kalemler)}  |  Net: {ozet}"
        )

    def _secim_degisti(self, satir: int) -> None:
        var = satir >= 0
        self._duzenle_btn.setEnabled(var)
        self._sil_btn.setEnabled(var)
        self._foto_btn.setEnabled(var)

    def _secili_kalem_id(self) -> Optional[int]:
        satir = self._tablo.currentRow()
        if satir < 0:
            return None
        item = self._tablo.item(satir, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _kalem_ekle(self) -> None:
        if self._belge_id is None:
            return
        dlg = _KalemDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        veri = dlg.deger()
        try:
            self._engine.kalem_ekle(belge_id=self._belge_id, **veri)
            self.yenile()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kalem eklenemedi:\n{e}")

    def _kalem_duzenle(self) -> None:
        kalem_id = self._secili_kalem_id()
        if kalem_id is None:
            return
        from app.core.atasaman_engine import AtasamanEngine as _Eng
        kalem = self._engine._kalem_getir(kalem_id)
        if kalem is None:
            return
        dlg = _KalemDialog(self, kalem=kalem)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        veri = dlg.deger()
        self._engine.kalem_guncelle(kalem_id, **veri)
        self.yenile()

    def _kalem_sil(self) -> None:
        kalem_id = self._secili_kalem_id()
        if kalem_id is None:
            return
        cevap = QMessageBox.question(
            self, "Kalemi Sil", "Bu ölçüm kalemi silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return
        self._engine.kalem_sil(kalem_id)
        self.yenile()

    def _foto_ekle(self) -> None:
        kalem_id = self._secili_kalem_id()
        if kalem_id is None:
            return
        yol, _ = QFileDialog.getOpenFileName(
            self, "Fotoğraf Seç", "",
            "Görüntü Dosyaları (*.jpg *.jpeg *.png *.webp *.gif)"
        )
        if not yol:
            return
        self._engine.foto_ekle(kalem_id, yol)
        self.yenile()

    def _ai_analiz(self) -> None:
        if self._belge_id is None:
            return
        dlg = _YapayZekaBoyutDialog(self)
        dlg.boyutlar_belirlendi.connect(self._ai_boyutlari_uygula)
        dlg.exec()

    def _ai_boyutlari_uygula(self, veri: dict) -> None:
        """Vision API sonucunu kalem diyaloğuna aktar."""
        kalem_on_deger = {
            "eleman_tipi": veri.get("eleman_tipi", "Serbest"),
            "tanim": veri.get("tanim", ""),
            "poz_no": "",
            "birim": veri.get("birim", "m³"),
            "en": float(veri.get("en_m", 0.0)),
            "boy": float(veri.get("boy_m", 0.0)),
            "yukseklik": float(veri.get("yukseklik_m", 0.0)),
            "adet": float(veri.get("adet", 1.0)),
            "cikarilan": 0.0,
            "notlar": veri.get("notlar", ""),
        }
        dlg = _KalemDialog(self, kalem=kalem_on_deger)
        dlg.setWindowTitle("Yapay Zeka Tahmini — Düzenle ve Kaydet")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            deger = dlg.deger()
            try:
                self._engine.kalem_ekle(belge_id=self._belge_id, **deger)
                self.yenile()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kalem eklenemedi:\n{e}")


# ──────────────────────────────────────────────────────────────────────────────
# Sekme 3: Özet & Çıktı
# ──────────────────────────────────────────────────────────────────────────────
class _OzetCiktiSekmesi(QWidget):
    def __init__(self, engine: AtasamanEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._belge_id: Optional[int] = None
        self._kur_ui()

    def _kur_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Başlık
        self._baslik_lbl = _label("Belge seçilmedi", kalin=True, renk=TEXT_GRAY)
        layout.addWidget(self._baslik_lbl)
        layout.addWidget(_ayirici())

        # Özet kartlar grid
        kart_layout = QGridLayout()
        kart_layout.setSpacing(12)

        self._kartlar: Dict[str, QLabel] = {}
        birimler = [
            ("m³", "Hacim (Beton/Dolgu)", "#2980b9"),
            ("m²", "Alan (Kalıp/Kaplama)", "#27ae60"),
            ("m", "Uzunluk (Hatıl/Lento)", "#f39c12"),
            ("adet", "Adet", "#8e44ad"),
        ]

        for i, (birim, aciklama, renk) in enumerate(birimler):
            kart = QFrame()
            kart.setStyleSheet(
                f"QFrame {{ background:{CARD_BG}; border-radius:10px;"
                f"border-left:4px solid {renk}; }}"
            )
            kart_ic = QVBoxLayout(kart)
            kart_ic.setContentsMargins(16, 12, 16, 12)
            kart_ic.setSpacing(4)

            birim_lbl = QLabel(birim)
            birim_lbl.setStyleSheet(
                f"color:{renk}; font-size:18px; font-weight:bold;"
            )
            acik_lbl = QLabel(aciklama)
            acik_lbl.setStyleSheet(f"color:{TEXT_GRAY}; font-size:11px;")
            deger_lbl = QLabel("—")
            deger_lbl.setStyleSheet(
                f"color:{TEXT_WHITE}; font-size:22px; font-weight:bold;"
            )

            kart_ic.addWidget(birim_lbl)
            kart_ic.addWidget(acik_lbl)
            kart_ic.addWidget(deger_lbl)
            kart_layout.addWidget(kart, i // 2, i % 2)
            self._kartlar[birim] = deger_lbl

        layout.addLayout(kart_layout)

        # Özet tablo
        self._ozet_grp = QGroupBox("Kalem Özeti")
        self._ozet_grp.setStyleSheet(
            f"QGroupBox {{ color:{TEXT_WHITE}; border:1px solid #444;"
            f"border-radius:6px; margin-top:8px; padding-top:8px; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; padding:0 6px; }}"
        )
        ozet_ic = QVBoxLayout(self._ozet_grp)

        self._ozet_tablo = QTableWidget(0, 5)
        self._ozet_tablo.setHorizontalHeaderLabels(
            ["Eleman Tipi", "Kalem Sayısı", "Brüt Toplam", "Net Toplam", "Birim"]
        )
        self._ozet_tablo.setStyleSheet(
            f"QTableWidget {{ background:{CARD_BG}; color:{TEXT_WHITE};"
            f"gridline-color:#333; border:none; }}"
            f"QHeaderView::section {{ background:#2c3e50; color:{TEXT_WHITE};"
            f"padding:4px; border:none; font-weight:bold; }}"
        )
        self._ozet_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._ozet_tablo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._ozet_tablo.verticalHeader().setVisible(False)
        ozet_ic.addWidget(self._ozet_tablo)
        layout.addWidget(self._ozet_grp)

        # Çıktı butonları
        cikti_grp = QGroupBox("Çıktı Alma")
        cikti_grp.setStyleSheet(
            f"QGroupBox {{ color:{TEXT_WHITE}; border:1px solid #444;"
            f"border-radius:6px; margin-top:8px; padding-top:8px; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; padding:0 6px; }}"
        )
        cikti_ic = QHBoxLayout(cikti_grp)
        cikti_ic.setSpacing(12)

        self._pdf_btn = _btn("PDF Ataşman Belgesi Üret", RED, bold=True)
        self._excel_btn = _btn("Excel / CSV Aktar", GREEN, bold=True)
        self._pdf_btn.setEnabled(False)
        self._excel_btn.setEnabled(False)
        self._pdf_btn.clicked.connect(self._pdf_uret)
        self._excel_btn.clicked.connect(self._excel_aktar)

        cikti_ic.addWidget(self._pdf_btn)
        cikti_ic.addWidget(self._excel_btn)
        cikti_ic.addStretch()
        layout.addWidget(cikti_grp)

        layout.addStretch()

    def belge_yukle(self, belge_id: int) -> None:
        self._belge_id = belge_id
        self.yenile()

    def yenile(self) -> None:
        if self._belge_id is None:
            return
        belge = self._engine.belge_getir(self._belge_id)
        if not belge:
            return

        no = belge.get("belge_no", "—")
        self._baslik_lbl.setText(f"Özet & Çıktı — {no}")
        self._baslik_lbl.setStyleSheet(f"color:{TEXT_WHITE}; font-weight:bold;")

        toplamlar = self._engine.toplam_hesapla(self._belge_id)

        for birim, lbl in self._kartlar.items():
            deger = toplamlar.get(birim, 0.0)
            lbl.setText(f"{deger:.3f} {birim}" if deger > 0 else "—")

        # Özet tablo — eleman tipi bazında grupla
        kalemler = belge.get("kalemler", [])
        from collections import defaultdict
        gruplar: dict = defaultdict(lambda: {"adet": 0, "brut": 0.0, "net": 0.0, "birim": set()})
        for kalem in kalemler:
            et = kalem.get("eleman_tipi", "Serbest")
            gruplar[et]["adet"] += 1
            gruplar[et]["brut"] += kalem.get("brut_miktar", 0.0)
            gruplar[et]["net"] += kalem.get("net_miktar", 0.0)
            gruplar[et]["birim"].add(kalem.get("birim", "m³"))

        self._ozet_tablo.setRowCount(0)
        for eleman, veri in sorted(gruplar.items()):
            satir = self._ozet_tablo.rowCount()
            self._ozet_tablo.insertRow(satir)
            birimler_str = "/".join(sorted(veri["birim"]))
            for col, deger in enumerate([
                eleman,
                str(veri["adet"]),
                f"{veri['brut']:.4f}",
                f"{veri['net']:.4f}",
                birimler_str,
            ]):
                item = QTableWidgetItem(deger)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._ozet_tablo.setItem(satir, col, item)

        self._pdf_btn.setEnabled(True)
        self._excel_btn.setEnabled(True)

    def _pdf_uret(self) -> None:
        if self._belge_id is None:
            return
        belge = self._engine.belge_getir(self._belge_id)
        no = belge.get("belge_no", "atasaman").replace("/", "-") if belge else "atasaman"
        varsayilan = str(Path.home() / "Desktop" / f"Atasaman_{no}.pdf")
        yol, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", varsayilan, "PDF Dosyaları (*.pdf)"
        )
        if not yol:
            return
        if self._engine.pdf_atasaman_belgesi_uret(self._belge_id, yol):
            QMessageBox.information(self, "Başarılı", f"PDF oluşturuldu:\n{yol}")
        else:
            QMessageBox.warning(
                self, "Hata",
                "PDF oluşturulamadı. reportlab kurulu mu?\n(pip install reportlab)"
            )

    def _excel_aktar(self) -> None:
        if self._belge_id is None:
            return
        belge = self._engine.belge_getir(self._belge_id)
        no = belge.get("belge_no", "atasaman").replace("/", "-") if belge else "atasaman"
        varsayilan = str(Path.home() / "Desktop" / f"Atasaman_{no}.xlsx")
        yol, _ = QFileDialog.getSaveFileName(
            self, "Excel/CSV Kaydet", varsayilan,
            "Excel Dosyaları (*.xlsx);;CSV Dosyaları (*.csv)"
        )
        if not yol:
            return
        if self._engine.excel_disari_aktar(self._belge_id, yol):
            QMessageBox.information(self, "Başarılı", f"Dosya aktarıldı:\n{yol}")
        else:
            QMessageBox.warning(self, "Hata", "Dosya aktarılamadı.")


# ──────────────────────────────────────────────────────────────────────────────
# Ana Pencere
# ──────────────────────────────────────────────────────────────────────────────
class AtasamanWindow(QWidget):
    """
    Ataşman Belgesi Ana Penceresi.
    3 sekme: Belgeler | Ölçü Cetveli | Özet & Çıktı
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ataşman Belgesi — Saha Ölçüm Tutanağı")
        self.resize(1200, 750)
        self.setStyleSheet(
            f"QWidget {{ background:{DARK_BG}; color:{TEXT_WHITE}; }}"
            f"QTabWidget::pane {{ border:none; }}"
            f"QTabBar::tab {{ background:{CARD_BG}; color:{TEXT_GRAY};"
            f"padding:8px 18px; border-top-left-radius:6px;"
            f"border-top-right-radius:6px; margin-right:2px; }}"
            f"QTabBar::tab:selected {{ background:{ACCENT}; color:#fff; }}"
            f"QTabBar::tab:hover {{ background:#2c3e50; }}"
            f"QScrollBar:vertical {{ background:{CARD_BG}; width:8px; border-radius:4px; }}"
            f"QScrollBar::handle:vertical {{ background:{ACCENT}; border-radius:4px; }}"
        )

        if not _ENGINE_OK:
            hata_layout = QVBoxLayout(self)
            hata_lbl = QLabel(
                "AtasamanEngine yüklenemedi.\n"
                "Lütfen uygulama günlüğünü kontrol edin."
            )
            hata_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hata_lbl.setStyleSheet(f"color:{RED}; font-size:16px;")
            hata_layout.addWidget(hata_lbl)
            return

        self._engine = AtasamanEngine()
        self._kur_ui()

    def _kur_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Üst başlık bandı
        baslik_bant = QFrame()
        baslik_bant.setStyleSheet(
            f"QFrame {{ background:{CARD_BG}; border-bottom:2px solid {ACCENT}; }}"
        )
        baslik_bant.setFixedHeight(52)
        bant_layout = QHBoxLayout(baslik_bant)
        bant_layout.setContentsMargins(16, 0, 16, 0)

        ana_baslik = QLabel("ATAŞMAN BELGESİ YÖNETİMİ")
        ana_baslik.setStyleSheet(
            f"color:{ACCENT}; font-size:16px; font-weight:bold;"
        )
        alt_baslik = QLabel("4735 Sayılı KİK — Saha Ölçüm Tutanağı")
        alt_baslik.setStyleSheet(f"color:{TEXT_GRAY}; font-size:11px;")

        yardim_btn = _btn("? Yardım", TEXT_GRAY)
        yardim_btn.clicked.connect(self._yardim_goster)

        bant_layout.addWidget(ana_baslik)
        bant_layout.addSpacing(20)
        bant_layout.addWidget(alt_baslik)
        bant_layout.addStretch()
        bant_layout.addWidget(yardim_btn)
        layout.addWidget(baslik_bant)

        # Sekmeler
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._belgeler_tab = _BelgelerSekmesi(self._engine)
        self._olcu_tab = _OlcuCetveliSekmesi(self._engine)
        self._ozet_tab = _OzetCiktiSekmesi(self._engine)

        self._tabs.addTab(self._belgeler_tab, "Belgeler")
        self._tabs.addTab(self._olcu_tab, "Ölçü Cetveli")
        self._tabs.addTab(self._ozet_tab, "Özet & Çıktı")

        self._belgeler_tab.belge_secildi.connect(self._belge_secildi)
        self._tabs.currentChanged.connect(self._sekme_degisti)

        layout.addWidget(self._tabs, 1)

    def _belge_secildi(self, belge_id: int) -> None:
        self._olcu_tab.belge_yukle(belge_id)
        self._ozet_tab.belge_yukle(belge_id)

    def _sekme_degisti(self, idx: int) -> None:
        belge_id = self._belgeler_tab.secili_belge_id()
        if belge_id is None:
            return
        try:
            if idx == 1:
                self._olcu_tab.yenile()
            elif idx == 2:
                self._ozet_tab.yenile()
        except Exception as e:
            logger.error("Sekme yenileme hatası: %s", e)

    def _yardim_goster(self) -> None:
        yardim = QDialog(self)
        yardim.setWindowTitle("Ataşman Belgesi — Yardım")
        yardim.setMinimumSize(560, 500)
        yardim.setStyleSheet(
            f"QDialog {{ background:{DARK_BG}; color:{TEXT_WHITE}; }}"
            f"QTextEdit {{ background:{CARD_BG}; color:{TEXT_WHITE}; border:none; }}"
        )
        layout = QVBoxLayout(yardim)
        metin = QTextEdit()
        metin.setReadOnly(True)
        metin.setHtml(f"""
        <style>
            body {{ color:{TEXT_WHITE}; font-family:Arial; font-size:13px; }}
            h2 {{ color:{ACCENT}; }}
            h3 {{ color:{ORANGE}; }}
            li {{ margin:4px 0; }}
            b {{ color:{GREEN}; }}
        </style>
        <h2>Ataşman Belgesi Nedir?</h2>
        <p>Ataşman; şantiyede yapılan imalatın, imalat başlamadan önce ve bittikten sonra
        ölçülerek kayıt altına alındığı resmi belgedir. <b>4735 Sayılı KİK</b> ve
        <b>Yapım İşleri Genel Şartnamesi md. 33</b> kapsamında hakedişin dayanağını oluşturur.</p>

        <h3>Sekmeler</h3>
        <ul>
            <li><b>Belgeler:</b> Proje bazında ataşman belgelerini oluştur, listele, düzenle, sil.</li>
            <li><b>Ölçü Cetveli:</b> Seçili belgeye eleman bazında ölçüm kalemleri ekle. Brüt/net otomatik hesaplanır.</li>
            <li><b>Özet & Çıktı:</b> Toplam miktarları görüntüle. Resmi PDF veya Excel al.</li>
        </ul>

        <h3>Hızlı Kullanım</h3>
        <ol>
            <li><b>Belgeler</b> sekmesinde "Yeni Belge" ile ataşman başlat (belge no zorunlu).</li>
            <li><b>Ölçü Cetveli</b> sekmesine geç → "Kalem Ekle" ile ölçüm gir.</li>
            <li>Her kalemde: Eleman Tipi, Birim, En/Boy/Yükseklik/Adet gir → Net otomatik hesaplanır.</li>
            <li>Fotoğraf ekleyebilir, "AI Boyut Analizi" ile ölçü bandı okunabilir.</li>
            <li><b>Özet & Çıktı</b> sekmesinden resmi PDF belgesi üret.</li>
        </ol>

        <h3>AI Boyut Analizi (Vision API)</h3>
        <p>Şantiye fotoğrafı yükleyin. Claude claude-opus-4-7 modeli ölçü bandı veya
        görünür boyutları okuyarak kalemi önceden doldurur. Sonuçları kontrol ederek
        kaydedin. <b>ANTHROPIC_API_KEY</b> env var gereklidir.</p>

        <h3>Boyut Formülleri</h3>
        <ul>
            <li>m³ → En × Boy × Yükseklik × Adet</li>
            <li>m² → En × Boy × Adet</li>
            <li>m  → Boy × Adet</li>
            <li>adet → Adet</li>
        </ul>
        <p>Net = Brüt − Çıkarılan (kapı/pencere boşlukları, açıklıklar)</p>
        """)
        layout.addWidget(metin)
        kapat = _btn("Kapat", ACCENT)
        kapat.clicked.connect(yardim.accept)
        layout.addWidget(kapat)
        yardim.exec()
