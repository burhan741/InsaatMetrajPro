"""
Fatura ve Tahsilat Takibi — UI Penceresi
==========================================
Serbest piyasa özel müşteri fatura ve tahsilat yönetimi.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QDoubleSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFrame, QTextEdit, QLineEdit,
    QComboBox, QDateEdit, QTabWidget, QDialog,
    QDialogButtonBox, QSplitter, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QFont, QColor

from app.core.fatura_engine import (
    FaturaEngine, FaturaBilgisi, OdemeKaydi,
    FATURA_DURUMLARI, ODEME_YONTEMLERI, FATURA_TURLERI,
)

# Stil sabitleri
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
    QDoubleSpinBox, QLineEdit, QComboBox, QDateEdit, QTextEdit {{
        background-color: #0f3460;
        color: {TEXT_WHITE};
        border: 1px solid #2a4a7f;
        border-radius: 4px;
        padding: 4px 8px;
    }}
"""

DURUM_RENKLERI = {
    "Bekliyor": "#f39c12",
    "Kısmen Ödendi": "#00BFFF",
    "Tamamlandı": "#27ae60",
    "Gecikti": "#e74c3c",
    "İptal": "#7f8c8d",
}


class OdemeDialog(QDialog):
    def __init__(self, fatura_no: str, kalan: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Ödeme Ekle — {fatura_no}")
        self.setMinimumWidth(380)
        self._build(kalan)
        self.setStyleSheet(f"""
            QDialog {{background-color:{DARK_BG}; color:{TEXT_WHITE};}}
            QLabel {{color:{TEXT_GRAY};}}
            {INPUT_STYLE}
        """)

    def _build(self, kalan: float):
        lay = QFormLayout(self)
        lay.setSpacing(8)

        self.tarih_edit = QDateEdit()
        self.tarih_edit.setCalendarPopup(True)
        self.tarih_edit.setDate(QDate.currentDate())

        self.tutar_spin = QDoubleSpinBox()
        self.tutar_spin.setRange(0.01, 999_999_999)
        self.tutar_spin.setDecimals(2)
        self.tutar_spin.setValue(kalan)
        self.tutar_spin.setSuffix(" ₺")

        self.yontem_combo = QComboBox()
        self.yontem_combo.addItems(ODEME_YONTEMLERI)
        self.yontem_combo.setCurrentText("Banka Havalesi / EFT")

        self.aciklama_edit = QLineEdit()
        self.aciklama_edit.setPlaceholderText("İsteğe bağlı not…")

        lay.addRow("Ödeme Tarihi:", self.tarih_edit)
        lay.addRow("Tutar:", self.tutar_spin)
        lay.addRow("Yöntem:", self.yontem_combo)
        lay.addRow("Açıklama:", self.aciklama_edit)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addRow(btns)

    def get_odeme(self) -> OdemeKaydi:
        q = self.tarih_edit.date()
        return OdemeKaydi(
            tarih=date(q.year(), q.month(), q.day()),
            tutar=Decimal(str(self.tutar_spin.value())),
            yontem=self.yontem_combo.currentText(),
            aciklama=self.aciklama_edit.text().strip(),
        )


class YeniFaturaDialog(QDialog):
    def __init__(self, engine: FaturaEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("Yeni Fatura Oluştur")
        self.setMinimumWidth(480)
        self._build()
        self.setStyleSheet(f"""
            QDialog {{background-color:{DARK_BG}; color:{TEXT_WHITE};}}
            QLabel {{color:{TEXT_GRAY};}}
            {INPUT_STYLE}
        """)
        self._kdv_hesapla()

    def _build(self):
        lay = QFormLayout(self)
        lay.setSpacing(8)

        self.musteri_edit = QLineEdit()
        self.musteri_edit.setPlaceholderText("Müşteri Adı / Firma")
        self.tel_edit = QLineEdit()
        self.tel_edit.setPlaceholderText("0 5xx xxx xx xx")
        self.proje_edit = QLineEdit()
        self.proje_edit.setPlaceholderText("Proje / İş tanımı")
        self.tur_combo = QComboBox()
        self.tur_combo.addItems(FATURA_TURLERI)

        sira = self.engine.son_fatura_sira()
        bugun = date.today()
        self.no_edit = QLineEdit(self.engine.fatura_no_uret(bugun.year, sira))
        self.no_edit.setReadOnly(True)

        self.tarih_edit = QDateEdit()
        self.tarih_edit.setCalendarPopup(True)
        self.tarih_edit.setDate(QDate.currentDate())

        self.vade_edit = QDateEdit()
        self.vade_edit.setCalendarPopup(True)
        vade = self.engine.vade_tarihi_hesapla(bugun)
        self.vade_edit.setDate(QDate(vade.year, vade.month, vade.day))

        self.kdv_haric_spin = QDoubleSpinBox()
        self.kdv_haric_spin.setRange(0, 999_999_999)
        self.kdv_haric_spin.setDecimals(2)
        self.kdv_haric_spin.setSuffix(" ₺")
        self.kdv_haric_spin.valueChanged.connect(self._kdv_hesapla)

        self.kdv_lbl = QLabel("0,00 ₺")
        self.toplam_lbl = QLabel("0,00 ₺")
        self.toplam_lbl.setStyleSheet(f"color:{ACCENT}; font-weight:bold;")

        self.aciklama_edit = QLineEdit()
        self.notlar_edit = QTextEdit()
        self.notlar_edit.setMaximumHeight(60)

        lay.addRow("Müşteri:", self.musteri_edit)
        lay.addRow("Telefon:", self.tel_edit)
        lay.addRow("Proje:", self.proje_edit)
        lay.addRow("Fatura Türü:", self.tur_combo)
        lay.addRow("Fatura No:", self.no_edit)
        lay.addRow("Fatura Tarihi:", self.tarih_edit)
        lay.addRow("Vade Tarihi:", self.vade_edit)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#2a4a7f;")
        lay.addRow(sep)

        lay.addRow("KDV Hariç Tutar:", self.kdv_haric_spin)
        lay.addRow("KDV (%20):", self.kdv_lbl)
        lay.addRow("GENEL TOPLAM:", self.toplam_lbl)
        lay.addRow("Açıklama:", self.aciklama_edit)
        lay.addRow("Notlar:", self.notlar_edit)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._dogrula)
        btns.rejected.connect(self.reject)
        lay.addRow(btns)

    def _kdv_hesapla(self):
        haric = Decimal(str(self.kdv_haric_spin.value()))
        kdv, toplam = self.engine.kdv_hesapla(haric)
        self.kdv_lbl.setText(f"{float(kdv):,.2f} ₺")
        self.toplam_lbl.setText(f"{float(toplam):,.2f} ₺")

    def _dogrula(self):
        if not self.musteri_edit.text().strip():
            QMessageBox.warning(self, "Uyarı", "Müşteri adı boş olamaz.")
            return
        if self.kdv_haric_spin.value() <= 0:
            QMessageBox.warning(self, "Uyarı", "Tutar sıfır olamaz.")
            return
        self.accept()

    def get_bilgi(self) -> FaturaBilgisi:
        haric = Decimal(str(self.kdv_haric_spin.value()))
        kdv, toplam = self.engine.kdv_hesapla(haric)
        qt = self.tarih_edit.date()
        qv = self.vade_edit.date()
        return FaturaBilgisi(
            musteri_adi=self.musteri_edit.text().strip(),
            musteri_tel=self.tel_edit.text().strip(),
            proje_adi=self.proje_edit.text().strip(),
            fatura_turu=self.tur_combo.currentText(),
            fatura_no=self.no_edit.text(),
            fatura_tarihi=date(qt.year(), qt.month(), qt.day()),
            vade_tarihi=date(qv.year(), qv.month(), qv.day()),
            kdv_haric_tutar=haric,
            kdv_tutari=kdv,
            genel_toplam=toplam,
            aciklama=self.aciklama_edit.text().strip(),
            notlar=self.notlar_edit.toPlainText().strip(),
        )


class FaturaWindow(QWidget):
    """Fatura ve tahsilat takibi ana penceresi."""

    def __init__(self, db=None, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.engine = FaturaEngine(db)
        self._build_ui()
        self._apply_styles()
        self._yenile()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._vade_kontrol)
        self._timer.start(60_000)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        baslik = QLabel(" Fatura ve Tahsilat Takibi")
        baslik.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        baslik.setStyleSheet(f"color:{ACCENT};")
        root.addWidget(baslik)

        alt = QLabel("Serbest Piyasa — Özel müşteri fatura, ödeme ve alacak yönetimi")
        alt.setStyleSheet(f"color:{TEXT_GRAY}; font-size:11px;")
        root.addWidget(alt)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#2a4a7f;")
        root.addWidget(sep)

        root.addWidget(self._build_kpi_satiri())
        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_filtreler())

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_fatura_tablo())
        splitter.addWidget(self._build_odeme_tablo())
        splitter.setSizes([350, 150])
        root.addWidget(splitter)

    def _build_kpi_satiri(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        def kpi(baslik, renk):
            grp = QGroupBox(baslik)
            grp.setStyleSheet(f"""
                QGroupBox {{background-color:{CARD_BG}; border:1px solid {renk};
                border-radius:6px; margin-top:8px; padding:8px;}}
                QGroupBox::title {{color:{renk}; font-weight:bold;}}
            """)
            lbl = QLabel("—")
            lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color:{renk};")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            QVBoxLayout(grp).addWidget(lbl)
            return grp, lbl

        self.kpi_toplam_grp, self.kpi_toplam = kpi("Toplam Alacak", ACCENT)
        self.kpi_tahsil_grp, self.kpi_tahsil = kpi("Tahsil Edilen", GREEN)
        self.kpi_bekleyen_grp, self.kpi_bekleyen = kpi("Bekleyen", YELLOW)
        self.kpi_gecikti_grp, self.kpi_gecikti = kpi("Vadesi Geçmiş", RED)

        for g, _ in [(self.kpi_toplam_grp, None), (self.kpi_tahsil_grp, None),
                     (self.kpi_bekleyen_grp, None), (self.kpi_gecikti_grp, None)]:
            lay.addWidget(g)
        return w

    def _build_toolbar(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        def btn(label, color=ACCENT, slot=None):
            b = QPushButton(label)
            b.setStyleSheet(BUTTON_STYLE.replace(ACCENT, color))
            if slot:
                b.clicked.connect(slot)
            return b

        lay.addWidget(btn(" Yeni Fatura", slot=self.yeni_fatura))
        lay.addWidget(btn(" Ödeme Ekle", GREEN, slot=self.odeme_ekle))
        lay.addWidget(btn(" Fatura İptal", RED, slot=self.fatura_iptal))
        lay.addWidget(btn(" Yenile", ORANGE, slot=self._yenile))
        lay.addStretch()
        lay.addWidget(btn(" Excel", GREEN, slot=self.export_excel))
        return w

    def _build_filtreler(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 4)

        lay.addWidget(QLabel("Durum:"))
        self.durum_combo = QComboBox()
        self.durum_combo.addItem("Tümü")
        self.durum_combo.addItems(FATURA_DURUMLARI)
        self.durum_combo.currentTextChanged.connect(self._yenile)
        lay.addWidget(self.durum_combo)

        lay.addWidget(QLabel("Müşteri:"))
        self.musteri_filtre = QLineEdit()
        self.musteri_filtre.setPlaceholderText("Müşteri ara…")
        self.musteri_filtre.setMaximumWidth(200)
        self.musteri_filtre.returnPressed.connect(self._yenile)
        lay.addWidget(self.musteri_filtre)

        btn_filtre = QPushButton("")
        btn_filtre.setFixedWidth(36)
        btn_filtre.clicked.connect(self._yenile)
        btn_filtre.setStyleSheet(BUTTON_STYLE)
        lay.addWidget(btn_filtre)
        lay.addStretch()

        self.durum_sayac_lbl = QLabel("")
        self.durum_sayac_lbl.setStyleSheet(f"color:{TEXT_GRAY}; font-size:11px;")
        lay.addWidget(self.durum_sayac_lbl)
        return w

    def _build_fatura_tablo(self) -> QGroupBox:
        grp = QGroupBox("Faturalar")
        lay = QVBoxLayout(grp)

        self.fatura_tablo = QTableWidget(0, 9)
        self.fatura_tablo.setHorizontalHeaderLabels([
            "ID", "Fatura No", "Müşteri", "Proje",
            "Toplam ₺", "Ödenen ₺", "Kalan ₺", "Vade", "Durum"
        ])
        hdr = self.fatura_tablo.horizontalHeader()
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for c in [0, 1, 4, 5, 6, 7, 8]:
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.fatura_tablo.verticalHeader().setVisible(False)
        self.fatura_tablo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.fatura_tablo.setAlternatingRowColors(True)
        self.fatura_tablo.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.fatura_tablo.itemSelectionChanged.connect(self._fatura_secildi)
        lay.addWidget(self.fatura_tablo)
        return grp

    def _build_odeme_tablo(self) -> QGroupBox:
        grp = QGroupBox("Seçili Fatura — Ödeme Geçmişi")
        lay = QVBoxLayout(grp)

        self.odeme_tablo = QTableWidget(0, 5)
        self.odeme_tablo.setHorizontalHeaderLabels([
            "Tarih", "Tutar ₺", "Yöntem", "Açıklama", "Kayıt"
        ])
        hdr = self.odeme_tablo.horizontalHeader()
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for c in [0, 1, 2, 4]:
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.odeme_tablo.verticalHeader().setVisible(False)
        self.odeme_tablo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.odeme_tablo.setAlternatingRowColors(True)
        lay.addWidget(self.odeme_tablo)
        return grp

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color:{DARK_BG};
                color:{TEXT_WHITE};
                font-family:"Segoe UI", sans-serif;
            }}
            QGroupBox {{
                background-color:{CARD_BG};
                border:1px solid #2a4a7f;
                border-radius:6px;
                margin-top:8px;
                padding:8px;
                color:{TEXT_GRAY};
            }}
            QGroupBox::title {{
                subcontrol-origin:margin;
                left:8px;
                color:{ACCENT};
                font-weight:bold;
            }}
            QTableWidget {{
                background-color:#0f1f3d;
                color:{TEXT_WHITE};
                gridline-color:#2a4a7f;
                border:1px solid #2a4a7f;
                border-radius:4px;
                font-size:12px;
            }}
            QHeaderView::section {{
                background-color:#0a1628;
                color:{ACCENT};
                border:none;
                padding:5px;
                font-weight:bold;
            }}
            {INPUT_STYLE}
        """)

    def yeni_fatura(self):
        dlg = YeniFaturaDialog(self.engine, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                bilgi = dlg.get_bilgi()
                self.engine.fatura_olustur(bilgi)
                self._yenile()
                QMessageBox.information(
                    self, "Başarılı",
                    f"Fatura oluşturuldu: {bilgi.fatura_no}\n"
                    f"Toplam: {float(bilgi.genel_toplam):,.2f} ₺"
                )
            except Exception as e:
                QMessageBox.critical(self, "Hata", str(e))

    def odeme_ekle(self):
        fatura_id, fatura_no, kalan = self._secili_fatura_bilgi()
        if fatura_id is None:
            QMessageBox.warning(self, "Uyarı", "Önce bir fatura seçin.")
            return
        if kalan <= 0:
            QMessageBox.information(self, "Bilgi", "Bu fatura zaten tamamlandı.")
            return

        dlg = OdemeDialog(fatura_no, kalan, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                odeme = dlg.get_odeme()
                self.engine.odeme_kaydet(fatura_id, odeme)
                self._yenile()
                self._odeme_tablosu_guncelle(fatura_id)
                QMessageBox.information(
                    self, "Başarılı",
                    f"Ödeme kaydedildi: {float(odeme.tutar):,.2f} ₺"
                )
            except Exception as e:
                QMessageBox.critical(self, "Hata", str(e))

    def fatura_iptal(self):
        fatura_id, fatura_no, _ = self._secili_fatura_bilgi()
        if fatura_id is None:
            QMessageBox.warning(self, "Uyarı", "Önce bir fatura seçin.")
            return
        cevap = QMessageBox.question(
            self, "İptal", f"{fatura_no} faturası iptal edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap == QMessageBox.StandardButton.Yes:
            self.engine.fatura_iptal(fatura_id)
            self._yenile()

    def _secili_fatura_bilgi(self) -> tuple:
        row = self.fatura_tablo.currentRow()
        if row < 0:
            return None, None, 0
        id_item = self.fatura_tablo.item(row, 0)
        no_item = self.fatura_tablo.item(row, 1)
        kal_item = self.fatura_tablo.item(row, 6)
        if not id_item:
            return None, None, 0
        try:
            kalan = float(kal_item.text().replace(",", "").replace(" ₺", "")) if kal_item else 0
        except ValueError:
            kalan = 0
        return int(id_item.text()), no_item.text() if no_item else "", kalan

    def _yenile(self):
        self.engine.gecikti_durumlari_guncelle()
        durum = self.durum_combo.currentText()
        musteri = self.musteri_filtre.text().strip()
        faturalar = self.engine.tum_faturalar(durum, musteri)
        self._fatura_tablo_doldur(faturalar)
        self._kpi_guncelle()
        self.durum_sayac_lbl.setText(f"{len(faturalar)} fatura")

    def _fatura_tablo_doldur(self, faturalar):
        self.fatura_tablo.setRowCount(len(faturalar))
        for r, f in enumerate(faturalar):
            toplam = float(f.get("genel_toplam") or 0)
            odened = float(f.get("odenen_toplam") or 0)
            kalan = toplam - odened

            self.fatura_tablo.setItem(r, 0, QTableWidgetItem(str(f["id"])))
            self.fatura_tablo.setItem(r, 1, QTableWidgetItem(f.get("fatura_no", "")))
            self.fatura_tablo.setItem(r, 2, QTableWidgetItem(f.get("musteri_adi", "")))
            self.fatura_tablo.setItem(r, 3, QTableWidgetItem(f.get("proje_adi", "")))
            self.fatura_tablo.setItem(r, 4, QTableWidgetItem(f"{toplam:,.2f}"))
            self.fatura_tablo.setItem(r, 5, QTableWidgetItem(f"{odened:,.2f}"))
            self.fatura_tablo.setItem(r, 6, QTableWidgetItem(f"{kalan:,.2f}"))
            self.fatura_tablo.setItem(r, 7, QTableWidgetItem(str(f.get("vade_tarihi") or "—")))
            durum = f.get("durum", "Bekliyor")
            durum_item = QTableWidgetItem(durum)
            renk = DURUM_RENKLERI.get(durum, TEXT_GRAY)
            durum_item.setForeground(QColor(renk))
            self.fatura_tablo.setItem(r, 8, durum_item)

            if durum == "Gecikti":
                for c in range(9):
                    it = self.fatura_tablo.item(r, c)
                    if it:
                        it.setBackground(QColor("#2d1010"))

    def _fatura_secildi(self):
        fatura_id, _, _ = self._secili_fatura_bilgi()
        if fatura_id:
            self._odeme_tablosu_guncelle(fatura_id)

    def _odeme_tablosu_guncelle(self, fatura_id: int):
        try:
            odemeler = self.engine.fatura_odemeleri(fatura_id)
            self.odeme_tablo.setRowCount(len(odemeler))
            for r, o in enumerate(odemeler):
                self.odeme_tablo.setItem(r, 0, QTableWidgetItem(str(o.get("tarih", ""))))
                tutar_item = QTableWidgetItem(f"{float(o.get('tutar', 0)):,.2f} ₺")
                tutar_item.setForeground(QColor(GREEN))
                self.odeme_tablo.setItem(r, 1, tutar_item)
                self.odeme_tablo.setItem(r, 2, QTableWidgetItem(o.get("yontem", "")))
                self.odeme_tablo.setItem(r, 3, QTableWidgetItem(o.get("aciklama", "")))
                self.odeme_tablo.setItem(r, 4, QTableWidgetItem(str(o.get("kayit_tarihi", ""))))
        except Exception:
            pass

    def _kpi_guncelle(self):
        try:
            ozet = self.engine.tahsilat_ozeti()
            def para(v): return f"{float(v):,.0f} ₺"
            self.kpi_toplam.setText(para(ozet.toplam_alacak))
            self.kpi_tahsil.setText(para(ozet.tahsil_edilen))
            self.kpi_bekleyen.setText(para(ozet.bekleyen))
            self.kpi_gecikti.setText(para(ozet.vadesi_gecmis))
        except Exception:
            pass

    def _vade_kontrol(self):
        try:
            guncellenen = self.engine.gecikti_durumlari_guncelle()
            if guncellenen > 0:
                self._yenile()
        except Exception:
            pass

    def export_excel(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel Kaydet", "fatura_listesi.xlsx",
            "Excel Dosyası (*.xlsx)"
        )
        if not path:
            return
        try:
            import openpyxl
            durum = self.durum_combo.currentText()
            musteri = self.musteri_filtre.text().strip()
            faturalar = self.engine.tum_faturalar(durum, musteri)

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Faturalar"

            basliklar = ["ID", "Fatura No", "Müşteri", "Proje", "Tür",
                         "Tarihi", "Vade", "Toplam ₺", "Ödenen ₺",
                         "Kalan ₺", "Durum"]
            ws.append(basliklar)
            from openpyxl.styles import Font
            for cell in ws[1]:
                cell.font = Font(bold=True)

            for f in faturalar:
                toplam = float(f.get("genel_toplam") or 0)
                odened = float(f.get("odenen_toplam") or 0)
                ws.append([
                    f["id"], f.get("fatura_no"), f.get("musteri_adi"),
                    f.get("proje_adi"), f.get("fatura_turu"),
                    f.get("fatura_tarihi"), f.get("vade_tarihi"),
                    toplam, odened, toplam - odened, f.get("durum"),
                ])

            wb.save(path)
            QMessageBox.information(self, "Başarılı", f"Excel kaydedildi:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
