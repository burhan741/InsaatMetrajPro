"""
Teminat Yönetimi — UI Penceresi
=================================
4734 md.33 + 4735 md.13
Geçici teminat, kesin teminat, ek kesin teminat hesabı ve mektup takibi.

Rev-79 (2026-04-26): 1-space cascade indentation → 4-space PEP8 (tamamen yeniden yazıldı)
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QDoubleSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFrame, QTextEdit, QDialog,
    QDialogButtonBox, QLineEdit, QComboBox, QDateEdit,
    QTabWidget,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from app.core.teminat_engine import (
    TeminatEngine, TeminatHesapSonucu, TeminatMektubu,
    TEMINAT_TURLERI, IADE_KOSULLARI,
)

DARK_BG    = "#1a1a2e"
CARD_BG    = "#16213e"
ACCENT     = "#00BFFF"
TEXT_WHITE = "#e0e0e0"
TEXT_GRAY  = "#a0a0b0"
GREEN      = "#27ae60"
RED        = "#e74c3c"
YELLOW     = "#f39c12"
ORANGE     = "#e67e22"

_STIL = f"""
QWidget      {{ background-color: {DARK_BG}; color: {TEXT_WHITE};
               font-family: 'Segoe UI'; }}
QGroupBox    {{ background-color: {CARD_BG}; border: 1px solid #2a4a7f;
               border-radius: 6px; margin-top: 8px; padding: 8px; color: {TEXT_GRAY}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px;
                    color: {ACCENT}; font-weight: bold; }}
QDoubleSpinBox, QLineEdit, QComboBox, QDateEdit
             {{ background-color: #0f3460; color: {TEXT_WHITE};
               border: 1px solid #2a4a7f; border-radius: 4px; padding: 4px 8px; }}
QPushButton  {{ background-color: {ACCENT}; color: #000; border: none;
               border-radius: 4px; padding: 6px 18px; font-weight: bold; }}
QPushButton:hover {{ background-color: #33d6ff; }}
QTableWidget {{ background-color: #0f1f3d; color: {TEXT_WHITE};
               gridline-color: #2a4a7f; border: 1px solid #2a4a7f; font-size: 12px; }}
QTableWidget::item:alternate {{ background-color: #142040; }}
QHeaderView::section {{ background-color: #0a1628; color: {ACCENT};
                        border: none; padding: 5px; font-weight: bold; }}
QTabBar::tab {{ background-color: #0f3460; color: {TEXT_GRAY};
               padding: 6px 14px; border-top-left-radius: 4px;
               border-top-right-radius: 4px; }}
QTabBar::tab:selected {{ background-color: #003366; color: {ACCENT}; font-weight: bold; }}
"""


# ── Mektup Ekleme Diyalogu ─────────────────────────────────────────────────────

class MektupEkleDialog(QDialog):
    """Yeni teminat mektubu ekleme formu."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Teminat Mektubu Ekle")
        self.setMinimumWidth(420)
        self._build()
        self.setStyleSheet(_STIL)

    def _build(self) -> None:
        layout = QFormLayout(self)
        layout.setSpacing(8)

        self.tur_combo = QComboBox()
        self.tur_combo.addItems(["gecici", "kesin", "ek_kesin"])
        layout.addRow("Teminat Türü:", self.tur_combo)

        self.banka_edit = QLineEdit()
        layout.addRow("Banka Adı:", self.banka_edit)

        self.no_edit = QLineEdit()
        layout.addRow("Mektup No:", self.no_edit)

        self.tutar_spin = QDoubleSpinBox()
        self.tutar_spin.setRange(0, 99_999_999_999)
        self.tutar_spin.setDecimals(2)
        self.tutar_spin.setSuffix(" TL")
        layout.addRow("Tutar:", self.tutar_spin)

        self.vade_edit = QDateEdit()
        self.vade_edit.setCalendarPopup(True)
        self.vade_edit.setDate(QDate.currentDate().addYears(1))
        layout.addRow("Vade Tarihi:", self.vade_edit)

        self.notlar_edit = QLineEdit()
        layout.addRow("Notlar:", self.notlar_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_mektup(self) -> TeminatMektubu:
        v = self.vade_edit.date()
        return TeminatMektubu(
            tur        = self.tur_combo.currentText(),
            banka_adi  = self.banka_edit.text().strip(),
            mektup_no  = self.no_edit.text().strip(),
            tutar      = Decimal(str(self.tutar_spin.value())),
            vade_tarihi= date(v.year(), v.month(), v.day()),
            notlar     = self.notlar_edit.text().strip(),
        )


# ── Ana Pencere ───────────────────────────────────────────────────────────────

class TeminatWindow(QWidget):
    """Teminat yönetimi ana penceresi — iki sekme: Hesap + Mektup Takibi."""

    def __init__(self, db=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.db = db
        self.engine       = TeminatEngine()
        self._mektuplar:  List[TeminatMektubu] = []
        self._son_sonuc:  Optional[TeminatHesapSonucu] = None
        self._build_ui()
        self.setStyleSheet(_STIL)

    # ── UI İnşası ─────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        baslik = QLabel("Teminat Yönetimi")
        baslik.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        baslik.setStyleSheet(f"color: {ACCENT};")
        root.addWidget(baslik)

        alt_b = QLabel("4734 md.33 (Geçici) + 4735 md.13 (Kesin) + Mektup Takibi")
        alt_b.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px;")
        root.addWidget(alt_b)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a4a7f;")
        root.addWidget(sep)

        ic_tabs = QTabWidget()
        ic_tabs.addTab(self._build_hesap_tab(),  "Teminat Hesabı")
        ic_tabs.addTab(self._build_takip_tab(),  "Mektup Takibi")
        root.addWidget(ic_tabs)

    # ── Hesap Sekmesi ─────────────────────────────────────────────────────────

    def _build_hesap_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Giriş formu
        form_grp = QGroupBox("İhale ve Sözleşme Bilgileri")
        form = QFormLayout(form_grp)
        form.setSpacing(8)

        self.ihale_spin = QDoubleSpinBox()
        self.ihale_spin.setRange(0, 99_999_999_999)
        self.ihale_spin.setDecimals(2)
        self.ihale_spin.setSuffix(" TL")
        self.ihale_spin.setSingleStep(100_000)
        self.ihale_spin.setGroupSeparatorShown(True)
        self.ihale_spin.setToolTip("Yaklaşık maliyet (ihale bedeli)")
        form.addRow("İhale Bedeli (Yaklaşık Maliyet):", self.ihale_spin)

        self.sozlesme_spin = QDoubleSpinBox()
        self.sozlesme_spin.setRange(0, 99_999_999_999)
        self.sozlesme_spin.setDecimals(2)
        self.sozlesme_spin.setSuffix(" TL")
        self.sozlesme_spin.setSingleStep(100_000)
        self.sozlesme_spin.setGroupSeparatorShown(True)
        self.sozlesme_spin.setToolTip("Kabul edilen teklif bedeli")
        form.addRow("Sözleşme Bedeli (Teklif):", self.sozlesme_spin)

        self.asiri_dusuk_spin = QDoubleSpinBox()
        self.asiri_dusuk_spin.setRange(0, 99_999_999_999)
        self.asiri_dusuk_spin.setDecimals(2)
        self.asiri_dusuk_spin.setSuffix(" TL")
        self.asiri_dusuk_spin.setGroupSeparatorShown(True)
        self.asiri_dusuk_spin.setToolTip(
            "Teklif aşırı düşük ise: sınır değer ile teklif farkı\n"
            "Yoksa 0 bırakın."
        )
        form.addRow("Aşırı Düşük Teklif Farkı:", self.asiri_dusuk_spin)

        layout.addWidget(form_grp)

        btn_hesapla = QPushButton("Hesapla")
        btn_hesapla.setFixedHeight(36)
        btn_hesapla.clicked.connect(self.hesapla)
        layout.addWidget(btn_hesapla)

        # Sonuç grubu
        ozet_grp = QGroupBox("Teminat Tutarları")
        ozet = QFormLayout(ozet_grp)
        ozet.setSpacing(8)

        def _lbl(renk: str = TEXT_WHITE, buyuk: bool = False) -> QLabel:
            l = QLabel("—")
            l.setFont(QFont("Segoe UI", 13 if buyuk else 12, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {renk};")
            return l

        self.gecici_lbl   = _lbl(YELLOW, True)
        self.kesin_lbl    = _lbl(ACCENT, True)
        self.ek_kesin_lbl = _lbl(ORANGE)
        self.toplam_lbl   = _lbl(GREEN, True)

        ozet.addRow("Geçici Teminat (%3 × ihale bedeli):",    self.gecici_lbl)
        ozet.addRow("Kesin Teminat (%6 × sözleşme bedeli):",  self.kesin_lbl)
        ozet.addRow("Ek Kesin Teminat (%6 × aşırı düşük fark):", self.ek_kesin_lbl)
        ozet.addRow("TOPLAM ZORUNLU TEMİNAT:",                 self.toplam_lbl)
        layout.addWidget(ozet_grp)

        # İade koşulları
        iade_grp = QGroupBox("İade Koşulları")
        iade_layout = QVBoxLayout(iade_grp)
        iade_layout.setSpacing(4)
        for tur, kosul in IADE_KOSULLARI.items():
            lbl_i = QLabel(f"<b>{tur.replace('_', ' ').title()}:</b> {kosul}")
            lbl_i.setWordWrap(True)
            lbl_i.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px;")
            iade_layout.addWidget(lbl_i)
        layout.addWidget(iade_grp)

        # Uyarı alanı
        self.uyari_text = QTextEdit()
        self.uyari_text.setReadOnly(True)
        self.uyari_text.setMaximumHeight(60)
        self.uyari_text.setStyleSheet(
            f"background-color: {DARK_BG}; color: {YELLOW}; "
            "border: 1px solid #2a4a7f; font-size: 12px;"
        )
        layout.addWidget(self.uyari_text)
        layout.addStretch()
        return w

    # ── Takip Sekmesi ─────────────────────────────────────────────────────────

    def _build_takip_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Araç çubuğu
        toolbar = QHBoxLayout()

        btn_ekle = QPushButton("Mektup Ekle")
        btn_ekle.clicked.connect(self.mektup_ekle)

        btn_sil = QPushButton("Sil")
        btn_sil.setStyleSheet(btn_ekle.styleSheet().replace(ACCENT, RED))
        btn_sil.clicked.connect(self.mektup_sil)

        btn_iade = QPushButton("İade İşaretle")
        btn_iade.setStyleSheet(btn_ekle.styleSheet().replace(ACCENT, GREEN))
        btn_iade.clicked.connect(self.mektup_iade)

        btn_vade = QPushButton("Vade Kontrolü")
        btn_vade.setStyleSheet(btn_ekle.styleSheet().replace(ACCENT, YELLOW))
        btn_vade.clicked.connect(self.vade_kontrol)

        for btn in [btn_ekle, btn_sil, btn_iade, btn_vade]:
            toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Tablo
        self.mektup_table = QTableWidget(0, 7)
        self.mektup_table.setHorizontalHeaderLabels(
            ["Tür", "Banka", "Mektup No", "Tutar (TL)", "Vade", "Kalan Gün", "Durum"]
        )
        self.mektup_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.mektup_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        for c in [0, 3, 4, 5, 6]:
            self.mektup_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents
            )
        self.mektup_table.verticalHeader().setVisible(False)
        self.mektup_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.mektup_table.setAlternatingRowColors(True)
        layout.addWidget(self.mektup_table)
        return w

    # ── Hesap işlemleri ───────────────────────────────────────────────────────

    def hesapla(self) -> None:
        sonuc = self.engine.hesapla(
            ihale_bedeli     = Decimal(str(self.ihale_spin.value())),
            sozlesme_bedeli  = Decimal(str(self.sozlesme_spin.value())),
            asiri_dusuk_fark = Decimal(str(self.asiri_dusuk_spin.value())),
        )
        self._son_sonuc = sonuc
        self.gecici_lbl.setText(f"{float(sonuc.gecici_teminat):,.2f} TL")
        self.kesin_lbl.setText(f"{float(sonuc.kesin_teminat):,.2f} TL")
        self.ek_kesin_lbl.setText(f"{float(sonuc.ek_kesin_teminat):,.2f} TL")
        self.toplam_lbl.setText(f"{float(sonuc.toplam_zorunlu_teminat):,.2f} TL")
        self.uyari_text.setText(
            "\n".join(sonuc.uyarilar) if sonuc.uyarilar else ""
        )

    # ── Mektup işlemleri ──────────────────────────────────────────────────────

    def mektup_ekle(self) -> None:
        dlg = MektupEkleDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._mektuplar.append(dlg.get_mektup())
            self._mektup_tablo_guncelle()

    def mektup_sil(self) -> None:
        row = self.mektup_table.currentRow()
        if 0 <= row < len(self._mektuplar):
            self._mektuplar.pop(row)
            self._mektup_tablo_guncelle()

    def mektup_iade(self) -> None:
        row = self.mektup_table.currentRow()
        if 0 <= row < len(self._mektuplar):
            self._mektuplar[row].iade_tarihi = date.today()
            self._mektup_tablo_guncelle()

    def vade_kontrol(self) -> None:
        uyarilar = self.engine.vade_uyari_listesi(self._mektuplar, uyari_gun=45)
        if not uyarilar:
            QMessageBox.information(self, "Vade Kontrolü", "Kritik vade durumu yok.")
            return
        mesaj = "\n".join(
            f"{m.banka_adi} / {m.mektup_no} ({m.tur}): {u}"
            for m, u in uyarilar
        )
        QMessageBox.warning(self, "Vade Uyarısı", mesaj)

    def _mektup_tablo_guncelle(self) -> None:
        self.mektup_table.setRowCount(len(self._mektuplar))
        for r, m in enumerate(self._mektuplar):
            self.mektup_table.setItem(r, 0, QTableWidgetItem(m.tur))
            self.mektup_table.setItem(r, 1, QTableWidgetItem(m.banka_adi))
            self.mektup_table.setItem(r, 2, QTableWidgetItem(m.mektup_no))

            tutar_item = QTableWidgetItem(f"{float(m.tutar):,.2f}")
            tutar_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.mektup_table.setItem(r, 3, tutar_item)
            self.mektup_table.setItem(r, 4, QTableWidgetItem(str(m.vade_tarihi)))

            kg = m.kalan_gun
            kg_item = QTableWidgetItem(str(kg))
            kg_item.setForeground(
                QColor(RED) if kg < 0
                else QColor(YELLOW) if kg <= 30
                else QColor(GREEN)
            )
            kg_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.mektup_table.setItem(r, 5, kg_item)

            durum      = "İade Edildi" if m.iade_edildi_mi else "Aktif"
            durum_item = QTableWidgetItem(durum)
            durum_item.setForeground(
                QColor(TEXT_GRAY) if m.iade_edildi_mi else QColor(GREEN)
            )
            self.mektup_table.setItem(r, 6, durum_item)
