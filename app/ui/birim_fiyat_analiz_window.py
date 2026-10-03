"""
Birim Fiyat Analiz Cetveli — UI Penceresi
==========================================
Poz başına: malzeme + işçilik + makine + taşıma + genel gider/kâr

Rev-79 (2026-04-26): 1-space cascade → 4-space PEP8 (tümden yeniden yazıldı)
"""
from __future__ import annotations

from decimal import Decimal

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QDoubleSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFrame, QDialog, QDialogButtonBox,
    QLineEdit, QComboBox, QSplitter,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from app.core.birim_fiyat_analiz_engine import (
    BirimFiyatAnalizEngine, PozAnalizi, AnalizSatiri,
    PozAnalizSonucu, GENEL_GIDER_KAR_ORANI
)

DARK_BG = "#1a1a2e"
CARD_BG = "#16213e"
ACCENT = "#00BFFF"
TEXT_WHITE = "#e0e0e0"
TEXT_GRAY = "#a0a0b0"
GREEN = "#27ae60"
RED = "#e74c3c"

BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {ACCENT};
        color: #000;
        border: none;
        border-radius: 4px;
        padding: 6px 16px;
        font-weight: bold;
        font-size: 13px;
    }}
    QPushButton:hover {{ background-color: #33d6ff; }}
"""

INPUT_STYLE = f"""
    QDoubleSpinBox, QLineEdit, QComboBox {{
        background-color: #0f3460;
        color: {TEXT_WHITE};
        border: 1px solid #2a4a7f;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 12px;
    }}
    QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {{
        border: 1px solid {ACCENT};
    }}
    QComboBox QAbstractItemView {{
        background-color: #0f3460;
        color: {TEXT_WHITE};
        selection-background-color: {ACCENT};
    }}
"""

TIP_RENKLERI = {
    "malzeme": "#1a4a7f",
    "iscilik": "#1a5a2a",
    "makine": "#4a3a1a",
    "tasima": "#4a1a4a",
}


# ---------------------------------------------------------------------------
# Bileşen Ekleme Diyalogu
# ---------------------------------------------------------------------------

class BilesenEkleDialog(QDialog):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Analiz Bileşeni Ekle")
        self.setMinimumWidth(400)
        self._build()
        self.setStyleSheet(f"""
            QDialog {{background-color: {DARK_BG}; color: {TEXT_WHITE};}}
            QLabel {{color: {TEXT_GRAY};}}
            {INPUT_STYLE}
        """)

    def _build(self) -> None:
        layout = QFormLayout(self)
        layout.setSpacing(8)

        self.tip_combo = QComboBox()
        self.tip_combo.addItems(["malzeme", "iscilik", "makine", "tasima"])
        layout.addRow("Bileşen Tipi:", self.tip_combo)

        self.tanim_edit = QLineEdit()
        layout.addRow("Tanım:", self.tanim_edit)

        self.birim_edit = QLineEdit()
        self.birim_edit.setPlaceholderText("m³, ton, adam-saat, saat …")
        layout.addRow("Birim:", self.birim_edit)

        self.miktar_spin = QDoubleSpinBox()
        self.miktar_spin.setRange(0, 999_999)
        self.miktar_spin.setDecimals(4)
        self.miktar_spin.setValue(1.0)
        layout.addRow("Miktar:", self.miktar_spin)

        self.birim_fiyat_spin = QDoubleSpinBox()
        self.birim_fiyat_spin.setRange(0, 999_999_999)
        self.birim_fiyat_spin.setDecimals(2)
        self.birim_fiyat_spin.setSuffix(" TL")
        layout.addRow("Birim Fiyat:", self.birim_fiyat_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_satir(self) -> AnalizSatiri:
        return AnalizSatiri(
            tip=self.tip_combo.currentText(),
            tanim=self.tanim_edit.text().strip(),
            birim=self.birim_edit.text().strip(),
            miktar=Decimal(str(self.miktar_spin.value())),
            birim_fiyat=Decimal(str(self.birim_fiyat_spin.value())),
        )


# ---------------------------------------------------------------------------
# Poz Oluşturma Diyalogu
# ---------------------------------------------------------------------------

class YeniPozDialog(QDialog):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Yeni Poz")
        self.setMinimumWidth(340)
        self._build()
        self.setStyleSheet(f"""
            QDialog {{background-color: {DARK_BG}; color: {TEXT_WHITE};}}
            QLabel {{color: {TEXT_GRAY};}}
            {INPUT_STYLE}
        """)

    def _build(self) -> None:
        layout = QFormLayout(self)

        self.poz_kodu_edit = QLineEdit()
        self.poz_tanimi_edit = QLineEdit()
        self.poz_birim_edit = QLineEdit()
        self.poz_birim_edit.setPlaceholderText("m³, m², adet …")

        self.ggk_spin = QDoubleSpinBox()
        self.ggk_spin.setRange(0, 100)
        self.ggk_spin.setDecimals(1)
        self.ggk_spin.setSuffix(" %")
        self.ggk_spin.setValue(float(GENEL_GIDER_KAR_ORANI * 100))

        layout.addRow("Poz Kodu:", self.poz_kodu_edit)
        layout.addRow("Poz Tanımı:", self.poz_tanimi_edit)
        layout.addRow("Birim:", self.poz_birim_edit)
        layout.addRow("Genel Gider & Kâr:", self.ggk_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_poz(self) -> PozAnalizi:
        return PozAnalizi(
            poz_kodu=self.poz_kodu_edit.text().strip(),
            poz_tanimi=self.poz_tanimi_edit.text().strip(),
            birim=self.poz_birim_edit.text().strip(),
            genel_gider_kar_orani=Decimal(str(self.ggk_spin.value() / 100)),
        )


# ---------------------------------------------------------------------------
# Ana Pencere
# ---------------------------------------------------------------------------

class BirimFiyatAnalizWindow(QWidget):
    """Birim fiyat analiz cetveli ana penceresi."""

    def __init__(self, db=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.engine = BirimFiyatAnalizEngine()
        self._pozlar: list[PozAnalizi] = []
        self._aktif_poz_idx: int = -1
        self._build_ui()
        self._apply_styles()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        baslik = QLabel("  Birim Fiyat Analiz Cetveli")
        baslik.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        baslik.setStyleSheet(f"color: {ACCENT};")
        root.addWidget(baslik)

        alt_b = QLabel("Malzeme + İşçilik + Makine + Taşıma + Genel Gider/Kâr")
        alt_b.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px;")
        root.addWidget(alt_b)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a4a7f;")
        root.addWidget(sep)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_poz_panel())
        splitter.addWidget(self._build_analiz_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter)

        root.addWidget(self._build_toolbar())

    def _build_poz_panel(self) -> QGroupBox:
        grp = QGroupBox("Poz Listesi")
        layout = QVBoxLayout(grp)

        btn_yeni = QPushButton("+ Yeni Poz")
        btn_yeni.clicked.connect(self.yeni_poz)
        btn_yeni.setStyleSheet(BUTTON_STYLE)
        layout.addWidget(btn_yeni)

        btn_sil = QPushButton("Sil")
        btn_sil.clicked.connect(self.poz_sil)
        btn_sil.setStyleSheet(BUTTON_STYLE.replace(ACCENT, RED))
        layout.addWidget(btn_sil)

        self.poz_list = QTableWidget(0, 2)
        self.poz_list.setHorizontalHeaderLabels(["Poz Kodu", "Birim Fiyat"])
        self.poz_list.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.poz_list.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.poz_list.verticalHeader().setVisible(False)
        self.poz_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.poz_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.poz_list.clicked.connect(self._poz_secildi)
        layout.addWidget(self.poz_list)

        return grp

    def _build_analiz_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        self.poz_baslik_lbl = QLabel("← Soldan bir poz seçin")
        self.poz_baslik_lbl.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 13px;")
        layout.addWidget(self.poz_baslik_lbl)

        bilesen_toolbar = QHBoxLayout()
        btn_bilesen_ekle = QPushButton("+ Bileşen Ekle")
        btn_bilesen_ekle.clicked.connect(self.bilesen_ekle)
        btn_bilesen_ekle.setStyleSheet(BUTTON_STYLE)
        btn_bilesen_sil = QPushButton("Sil")
        btn_bilesen_sil.clicked.connect(self.bilesen_sil)
        btn_bilesen_sil.setStyleSheet(BUTTON_STYLE.replace(ACCENT, RED))
        bilesen_toolbar.addWidget(btn_bilesen_ekle)
        bilesen_toolbar.addWidget(btn_bilesen_sil)
        bilesen_toolbar.addStretch()
        layout.addLayout(bilesen_toolbar)

        self.bilesen_table = QTableWidget(0, 6)
        self.bilesen_table.setHorizontalHeaderLabels(
            ["Tip", "Tanım", "Birim", "Miktar", "Birim Fiyat (TL)", "Tutar (TL)"]
        )
        self.bilesen_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        for c in [0, 2, 3, 4, 5]:
            self.bilesen_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents
            )
        self.bilesen_table.verticalHeader().setVisible(False)
        self.bilesen_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bilesen_table.setAlternatingRowColors(True)
        layout.addWidget(self.bilesen_table)

        ozet_grp = QGroupBox("Analiz Özeti")
        ozet_layout = QFormLayout(ozet_grp)

        def lbl(renk=TEXT_WHITE):
            l = QLabel("—")
            l.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {renk};")
            return l

        self.malzeme_lbl = lbl()
        self.iscilik_lbl = lbl()
        self.makine_lbl = lbl()
        self.tasima_lbl = lbl()
        self.direkt_lbl = lbl(ACCENT)
        self.ggk_lbl = lbl()
        self.birim_fiyat_lbl = lbl(GREEN)

        ozet_layout.addRow("Malzeme:", self.malzeme_lbl)
        ozet_layout.addRow("İşçilik:", self.iscilik_lbl)
        ozet_layout.addRow("Makine:", self.makine_lbl)
        ozet_layout.addRow("Taşıma:", self.tasima_lbl)
        ozet_layout.addRow("Direkt Toplam:", self.direkt_lbl)
        ozet_layout.addRow("Genel Gider & Kâr:", self.ggk_lbl)
        ozet_layout.addRow("BİRİM FİYAT:", self.birim_fiyat_lbl)

        layout.addWidget(ozet_grp)
        return w

    def _build_toolbar(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        btn_hesapla = QPushButton("Hesapla")
        btn_hesapla.clicked.connect(self.hesapla)
        btn_hesapla.setStyleSheet(BUTTON_STYLE)

        btn_excel = QPushButton("Excel Aktar")
        btn_excel.clicked.connect(self.export_excel)
        btn_excel.setStyleSheet(BUTTON_STYLE.replace(ACCENT, GREEN))

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
            QSplitter::handle {{ background-color: #2a4a7f; }}
            {INPUT_STYLE}
        """)

    # ------------------------------------------------------------------
    # İşlevler
    # ------------------------------------------------------------------

    def yeni_poz(self) -> None:
        dlg = YeniPozDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._pozlar.append(dlg.get_poz())
            self._poz_list_guncelle()

    def poz_sil(self) -> None:
        row = self.poz_list.currentRow()
        if 0 <= row < len(self._pozlar):
            self._pozlar.pop(row)
            self._aktif_poz_idx = -1
            self._poz_list_guncelle()
            self.bilesen_table.setRowCount(0)

    def _poz_list_guncelle(self) -> None:
        self.poz_list.setRowCount(len(self._pozlar))
        for r, p in enumerate(self._pozlar):
            self.poz_list.setItem(r, 0, QTableWidgetItem(p.poz_kodu or p.poz_tanimi))
            self.poz_list.setItem(r, 1, QTableWidgetItem("—"))

    def _poz_secildi(self, idx) -> None:
        row = self.poz_list.currentRow()
        if 0 <= row < len(self._pozlar):
            self._aktif_poz_idx = row
            poz = self._pozlar[row]
            self.poz_baslik_lbl.setText(
                f"  {poz.poz_kodu} — {poz.poz_tanimi} [{poz.birim}]"
            )
            self._bilesen_table_guncelle(poz)

    def _bilesen_table_guncelle(self, poz: PozAnalizi) -> None:
        self.bilesen_table.setRowCount(len(poz.satirlar))
        for r, s in enumerate(poz.satirlar):
            self.bilesen_table.setItem(r, 0, QTableWidgetItem(s.tip))
            self.bilesen_table.setItem(r, 1, QTableWidgetItem(s.tanim))
            self.bilesen_table.setItem(r, 2, QTableWidgetItem(s.birim))
            self._num(r, 3, float(s.miktar))
            self._num(r, 4, float(s.birim_fiyat))
            self._num(r, 5, float(s.tutar))

            bg = TIP_RENKLERI.get(s.tip, CARD_BG)
            for c in range(6):
                item = self.bilesen_table.item(r, c)
                if item:
                    item.setBackground(QColor(bg))

    def _num(self, row: int, col: int, val: float) -> None:
        item = QTableWidgetItem(f"{val:,.4f}" if col == 3 else f"{val:,.2f}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.bilesen_table.setItem(row, col, item)

    def bilesen_ekle(self) -> None:
        if self._aktif_poz_idx < 0:
            QMessageBox.warning(self, "Uyarı", "Önce bir poz seçin.")
            return
        dlg = BilesenEkleDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._pozlar[self._aktif_poz_idx].satirlar.append(dlg.get_satir())
            self._bilesen_table_guncelle(self._pozlar[self._aktif_poz_idx])

    def bilesen_sil(self) -> None:
        if self._aktif_poz_idx < 0:
            return
        row = self.bilesen_table.currentRow()
        satirlar = self._pozlar[self._aktif_poz_idx].satirlar
        if 0 <= row < len(satirlar):
            satirlar.pop(row)
            self._bilesen_table_guncelle(self._pozlar[self._aktif_poz_idx])

    def hesapla(self) -> None:
        if self._aktif_poz_idx < 0:
            QMessageBox.warning(self, "Uyarı", "Önce bir poz seçin.")
            return
        poz = self._pozlar[self._aktif_poz_idx]
        sonuc = self.engine.hesapla_poz(poz)

        self.malzeme_lbl.setText(f"{float(sonuc.malzeme_toplam):,.2f} TL")
        self.iscilik_lbl.setText(f"{float(sonuc.iscilik_toplam):,.2f} TL")
        self.makine_lbl.setText(f"{float(sonuc.makine_toplam):,.2f} TL")
        self.tasima_lbl.setText(f"{float(sonuc.tasima_toplam):,.2f} TL")
        self.direkt_lbl.setText(f"{float(sonuc.direkt_toplam):,.2f} TL")
        self.ggk_lbl.setText(f"{float(sonuc.genel_gider_kar):,.2f} TL")
        self.birim_fiyat_lbl.setText(f"{float(sonuc.birim_fiyat):,.2f} TL / {poz.birim}")

        item = self.poz_list.item(self._aktif_poz_idx, 1)
        if item:
            item.setText(f"{float(sonuc.birim_fiyat):,.2f}")

    def export_excel(self) -> None:
        if not self._pozlar:
            QMessageBox.warning(self, "Uyarı", "Analiz edilecek poz yok.")
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from PyQt6.QtWidgets import QFileDialog

            path, _ = QFileDialog.getSaveFileName(
                self, "Excel Kaydet", "birim_fiyat_analiz.xlsx",
                "Excel Dosyası (*.xlsx)"
            )
            if not path:
                return

            wb = openpyxl.Workbook()
            first = True
            for poz in self._pozlar:
                sonuc = self.engine.hesapla_poz(poz)
                if first:
                    ws = wb.active
                    ws.title = poz.poz_kodu or "Analiz"
                    first = False
                else:
                    ws = wb.create_sheet(poz.poz_kodu or "Analiz")

                ws.merge_cells("A1:F1")
                ws["A1"] = f"BİRİM FİYAT ANALİZ CETVELİ — {poz.poz_kodu} {poz.poz_tanimi}"
                ws["A1"].font = Font(bold=True, size=12, color="FFFFFF")
                ws["A1"].fill = PatternFill("solid", fgColor="003366")
                ws["A1"].alignment = Alignment(horizontal="center")

                ws.append(["Tip", "Tanım", "Birim", "Miktar", "Birim Fiyat (TL)", "Tutar (TL)"])
                for s in poz.satirlar:
                    ws.append([
                        s.tip, s.tanim, s.birim,
                        float(s.miktar), float(s.birim_fiyat), float(s.tutar)
                    ])

                ws.append([])
                ws.append(["", "", "", "", "Direkt Toplam:", float(sonuc.direkt_toplam)])
                ws.append(["", "", "", "", "Genel Gider & Kâr:", float(sonuc.genel_gider_kar)])
                ws.append(["", "", "", "", "BİRİM FİYAT (TL):", float(sonuc.birim_fiyat)])
                for r_off in [-2, -1, 0]:
                    r = ws.max_row + r_off
                    ws.cell(r, 5).font = Font(bold=True)
                    ws.cell(r, 6).font = Font(bold=True)

                for col in ["A", "B", "C", "D", "E", "F"]:
                    ws.column_dimensions[col].width = 18

            wb.save(path)
            QMessageBox.information(self, "Başarılı", f"Excel kaydedildi:\n{path}")

        except ImportError:
            QMessageBox.warning(self, "Eksik", "pip install openpyxl")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
