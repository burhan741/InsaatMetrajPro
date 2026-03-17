"""
Gecikme Cezası ve Süre Uzatımı — UI Penceresi
===============================================
4735 sayılı Kamu İhale Sözleşmeleri Kanunu md.20
4-space PEP8 — tam yeniden yazım
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QDoubleSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFrame, QTextEdit, QDialog,
    QDialogButtonBox, QLineEdit, QCheckBox, QComboBox,
    QDateEdit,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from app.core.gecikme_ceza_engine import (
    GecikmeCezaEngine, GecikmeGunuKaydi, GecikmeCezaSonucu,
    MUCBIR_SEBEP_KATEGORILERI,
)

DARK_BG = "#1a1a2e"
CARD_BG = "#16213e"
ACCENT = "#00BFFF"
TEXT_WHITE = "#e0e0e0"
TEXT_GRAY = "#a0a0b0"
GREEN = "#27ae60"
RED = "#e74c3c"
YELLOW = "#f39c12"
ORANGE = "#e67e22"

BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {ACCENT};
        color: #000;
        border: none;
        border-radius: 4px;
        padding: 6px 16px;
        font-weight: bold;
    }}
    QPushButton:hover {{ background-color: #33d6ff; }}
"""

INPUT_STYLE = f"""
    QDoubleSpinBox, QLineEdit, QComboBox, QDateEdit {{
        background-color: #0f3460;
        color: {TEXT_WHITE};
        border: 1px solid #2a4a7f;
        border-radius: 4px;
        padding: 4px 8px;
    }}
    QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
        border: 1px solid {ACCENT};
    }}
    QComboBox QAbstractItemView {{
        background-color: #0f3460;
        color: {TEXT_WHITE};
        selection-background-color: {ACCENT};
    }}
"""


class KayitEkleDialog(QDialog):
    """Gecikme / Mücbir Sebep kaydı ekleme diyaloğu."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gecikme / Mücbir Sebep Kaydı Ekle")
        self.setMinimumWidth(420)
        self._build()
        self.setStyleSheet(f"""
            QDialog {{background-color: {DARK_BG}; color: {TEXT_WHITE};}}
            QLabel {{color: {TEXT_GRAY};}}
            {INPUT_STYLE}
            QCheckBox {{color: {TEXT_GRAY};}}
        """)

    def _build(self) -> None:
        layout = QFormLayout(self)
        layout.setSpacing(8)

        self.baslangic_edit = QDateEdit()
        self.baslangic_edit.setCalendarPopup(True)
        self.baslangic_edit.setDate(QDate.currentDate())
        layout.addRow("Başlangıç:", self.baslangic_edit)

        self.bitis_edit = QDateEdit()
        self.bitis_edit.setCalendarPopup(True)
        self.bitis_edit.setDate(QDate.currentDate())
        layout.addRow("Bitiş:", self.bitis_edit)

        self.sebep_edit = QLineEdit()
        self.sebep_edit.setPlaceholderText("Gecikme sebebini kısa yazın…")
        layout.addRow("Sebep:", self.sebep_edit)

        self.mucbir_check = QCheckBox("Mücbir Sebep (4735 md.10)")
        layout.addRow(self.mucbir_check)

        self.mucbir_kategori_combo = QComboBox()
        self.mucbir_kategori_combo.addItems(MUCBIR_SEBEP_KATEGORILERI)
        self.mucbir_kategori_combo.setEnabled(False)
        layout.addRow("Kategori:", self.mucbir_kategori_combo)

        self.mucbir_check.toggled.connect(self.mucbir_kategori_combo.setEnabled)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_kayit(self) -> GecikmeGunuKaydi:
        bas_q = self.baslangic_edit.date()
        bit_q = self.bitis_edit.date()
        sebep = self.sebep_edit.text().strip()
        if self.mucbir_check.isChecked():
            sebep += f" [{self.mucbir_kategori_combo.currentText()}]"
        return GecikmeGunuKaydi(
            baslangic=date(bas_q.year(), bas_q.month(), bas_q.day()),
            bitis=date(bit_q.year(), bit_q.month(), bit_q.day()),
            sebep=sebep,
            mucbir_sebep_mi=self.mucbir_check.isChecked(),
        )


class GecikmeCezaWindow(QWidget):
    """Gecikme Cezası ve Süre Uzatımı ana penceresi."""

    def __init__(self, db=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.engine = GecikmeCezaEngine()
        self._kayitlar: list[GecikmeGunuKaydi] = []
        self._son_sonuc: GecikmeCezaSonucu | None = None
        self._build_ui()
        self._apply_styles()

    # ------------------------------------------------------------------
    # UI oluşturma
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        baslik = QLabel(" Gecikme Cezası ve Süre Uzatımı")
        baslik.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        baslik.setStyleSheet(f"color: {ACCENT};")
        root.addWidget(baslik)

        alt_b = QLabel("4735 md.20 — Günlük ‰5 (%0.5, binde beş) | Fesih Eşiği %30")
        alt_b.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px;")
        root.addWidget(alt_b)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a4a7f;")
        root.addWidget(sep)

        ust = QHBoxLayout()
        ust.addWidget(self._build_form(), 1)
        ust.addWidget(self._build_ozet(), 1)
        root.addLayout(ust)

        root.addWidget(self._build_toolbar())

        kayit_lbl = QLabel("Gecikme / Mücbir Sebep Kayıtları")
        kayit_lbl.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 13px;")
        root.addWidget(kayit_lbl)

        self.kayit_table = QTableWidget(0, 5)
        self.kayit_table.setHorizontalHeaderLabels(
            ["Başlangıç", "Bitiş", "Gün", "Mücbir Sebep", "Açıklama"]
        )
        self.kayit_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        for c in range(4):
            self.kayit_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents
            )
        self.kayit_table.verticalHeader().setVisible(False)
        self.kayit_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.kayit_table.setAlternatingRowColors(True)
        root.addWidget(self.kayit_table)

        self.uyari_text = QTextEdit()
        self.uyari_text.setReadOnly(True)
        self.uyari_text.setMaximumHeight(70)
        self.uyari_text.setStyleSheet(
            f"background-color: {DARK_BG}; color: {YELLOW}; "
            "border: 1px solid #2a4a7f; font-size: 12px;"
        )
        root.addWidget(self.uyari_text)

    def _build_form(self) -> QGroupBox:
        grp = QGroupBox("Sözleşme Bilgileri")
        layout = QFormLayout(grp)

        self.sozlesme_spin = QDoubleSpinBox()
        self.sozlesme_spin.setRange(0, 99_999_999_999)
        self.sozlesme_spin.setDecimals(2)
        self.sozlesme_spin.setSuffix(" TL")
        self.sozlesme_spin.setSingleStep(100_000)
        layout.addRow("Sözleşme Bedeli:", self.sozlesme_spin)

        return grp

    def _build_ozet(self) -> QGroupBox:
        grp = QGroupBox("Hesap Özeti")
        layout = QFormLayout(grp)

        def lbl(renk=TEXT_WHITE, buyuk=False):
            l = QLabel("—")
            l.setFont(QFont("Segoe UI", 13 if buyuk else 12, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {renk};")
            return l

        self.toplam_gun_lbl = lbl()
        self.mucbir_gun_lbl = lbl(YELLOW)
        self.net_ceza_gun_lbl = lbl()
        self.gunluk_ceza_lbl = lbl()
        self.toplam_ceza_lbl = lbl(RED, True)
        self.fesih_esigi_lbl = lbl()
        self.sure_uzatim_lbl = lbl(GREEN)

        layout.addRow("Toplam Gecikme:", self.toplam_gun_lbl)
        layout.addRow("Mücbir Sebep:", self.mucbir_gun_lbl)
        layout.addRow("Net Ceza Günü:", self.net_ceza_gun_lbl)
        layout.addRow("Günlük Ceza:", self.gunluk_ceza_lbl)
        layout.addRow("TOPLAM CEZA:", self.toplam_ceza_lbl)
        layout.addRow("Fesih Eşiği:", self.fesih_esigi_lbl)
        layout.addRow("Süre Uzatım Hakkı:", self.sure_uzatim_lbl)

        return grp

    def _build_toolbar(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        btn_ekle = QPushButton(" Kayıt Ekle")
        btn_ekle.clicked.connect(self.kayit_ekle)
        btn_ekle.setStyleSheet(BUTTON_STYLE)

        btn_sil = QPushButton(" Sil")
        btn_sil.clicked.connect(self.kayit_sil)
        btn_sil.setStyleSheet(BUTTON_STYLE.replace(ACCENT, RED))

        btn_hesapla = QPushButton(" Hesapla")
        btn_hesapla.clicked.connect(self.hesapla)
        btn_hesapla.setStyleSheet(BUTTON_STYLE)

        btn_excel = QPushButton(" Excel")
        btn_excel.clicked.connect(self.export_excel)
        btn_excel.setStyleSheet(BUTTON_STYLE.replace(ACCENT, GREEN))

        layout.addWidget(btn_ekle)
        layout.addWidget(btn_sil)
        layout.addWidget(btn_hesapla)
        layout.addStretch()
        layout.addWidget(btn_excel)
        return w

    def _apply_styles(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_BG};
                color: {TEXT_WHITE};
                font-family: "Segoe UI", sans-serif;
            }}
            QGroupBox {{
                background-color: {CARD_BG};
                border: 1px solid #2a4a7f;
                border-radius: 6px;
                margin-top: 8px;
                padding: 8px;
                color: {TEXT_GRAY};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                color: {ACCENT};
                font-weight: bold;
            }}
            QTableWidget {{
                background-color: #0f1f3d;
                color: {TEXT_WHITE};
                gridline-color: #2a4a7f;
                border: 1px solid #2a4a7f;
                border-radius: 4px;
                font-size: 12px;
            }}
            QTableWidget::item:alternate {{ background-color: #142040; }}
            QHeaderView::section {{
                background-color: #0a1628;
                color: {ACCENT};
                border: none;
                padding: 5px;
                font-weight: bold;
            }}
            {INPUT_STYLE}
        """)

    # ------------------------------------------------------------------
    # İşlemler
    # ------------------------------------------------------------------

    def kayit_ekle(self) -> None:
        dlg = KayitEkleDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._kayitlar.append(dlg.get_kayit())
            self._tablo_guncelle()

    def kayit_sil(self) -> None:
        row = self.kayit_table.currentRow()
        if 0 <= row < len(self._kayitlar):
            self._kayitlar.pop(row)
            self._tablo_guncelle()

    def _tablo_guncelle(self) -> None:
        self.kayit_table.setRowCount(len(self._kayitlar))
        for r, k in enumerate(self._kayitlar):
            self.kayit_table.setItem(r, 0, QTableWidgetItem(str(k.baslangic)))
            self.kayit_table.setItem(r, 1, QTableWidgetItem(str(k.bitis)))
            self.kayit_table.setItem(r, 2, QTableWidgetItem(str(k.gun_sayisi)))
            mucbir_item = QTableWidgetItem("Evet" if k.mucbir_sebep_mi else "—")
            mucbir_item.setForeground(
                QColor(YELLOW) if k.mucbir_sebep_mi else QColor(TEXT_GRAY)
            )
            self.kayit_table.setItem(r, 3, mucbir_item)
            self.kayit_table.setItem(r, 4, QTableWidgetItem(k.sebep))

    def hesapla(self) -> None:
        if not self._kayitlar:
            QMessageBox.warning(self, "Uyarı", "Önce gecikme kaydı ekleyin.")
            return
        sonuc = self.engine.hesapla(
            sozlesme_bedeli=Decimal(str(self.sozlesme_spin.value())),
            kayitlar=self._kayitlar,
        )
        self._son_sonuc = sonuc

        self.toplam_gun_lbl.setText(f"{sonuc.toplam_gecikme_gun} gün")
        self.mucbir_gun_lbl.setText(f"{sonuc.mucbir_sebep_gun} gün")
        self.net_ceza_gun_lbl.setText(f"{sonuc.net_ceza_gun} gün")
        self.gunluk_ceza_lbl.setText(f"{float(sonuc.gunluk_ceza_tutari):,.2f} TL")
        self.toplam_ceza_lbl.setText(f"{float(sonuc.toplam_ceza):,.2f} TL")
        self.toplam_ceza_lbl.setStyleSheet(
            f"color: {RED}; font-weight: bold;" if sonuc.fesih_riski
            else f"color: {ORANGE}; font-weight: bold;"
        )
        self.fesih_esigi_lbl.setText(
            f"{float(sonuc.fesih_esigi_tutari):,.2f} TL "
            f"(%{float(sonuc.fesih_riski_pct):.1f} doldu)"
        )
        self.sure_uzatim_lbl.setText(f"{sonuc.sure_uzatim_hakki_gun} gün hak")
        self.uyari_text.setText("\n".join(sonuc.uyarilar) if sonuc.uyarilar else "")

    def export_excel(self) -> None:
        if not self._son_sonuc:
            QMessageBox.warning(self, "Uyarı", "Önce hesaplama yapın.")
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
            from PyQt6.QtWidgets import QFileDialog

            path, _ = QFileDialog.getSaveFileName(
                self, "Excel Kaydet", "gecikme_ceza.xlsx",
                "Excel Dosyası (*.xlsx)"
            )
            if not path:
                return

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Gecikme Cezası"

            ws.append(["GECİKME CEZA HESABI"])
            ws.append([
                f"Sözleşme: {float(self._son_sonuc.sozlesme_bedeli):,.2f} TL",
                f"Toplam Ceza: {float(self._son_sonuc.toplam_ceza):,.2f} TL",
                f"Net Ceza Günü: {self._son_sonuc.net_ceza_gun}",
            ])
            ws.append([])
            ws.append(["Başlangıç", "Bitiş", "Gün", "Mücbir Sebep", "Açıklama"])

            for k in self._kayitlar:
                ws.append([
                    str(k.baslangic), str(k.bitis),
                    k.gun_sayisi,
                    "Evet" if k.mucbir_sebep_mi else "Hayır",
                    k.sebep,
                ])

            wb.save(path)
            QMessageBox.information(self, "Başarılı", f"Kaydedildi:\n{path}")
        except ImportError:
            QMessageBox.warning(self, "Eksik", "pip install openpyxl")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
