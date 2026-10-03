"""
Ince Isler Hizli Hesap Penceresi
Net alan + is tipleri secimi -> malzeme + iscilik maliyet + PDF / CSV / Metraj aktarimi

Kullanim:
  w = InceIslerHizliWindow(db=main_window.db, parent=main_window)
  w.show()
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QCheckBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

logger = logging.getLogger(__name__)

try:
    from app.core.ince_isler_hizli_engine import (
        GUNLUK_UCRET_VARSAYILAN, IS_TIPLERI,
        InceIslerHizliEngine, IscilikKalemi, MalzemeKalemi,
    )
    _ENGINE_OK = True
except Exception as e:
    logger.error("InceIslerHizliEngine yuklenemedi: %s", e)
    _ENGINE_OK = False


class InceIslerHizliWindow(QDialog):
    """
    Ince Isler Hizli Hesap ana penceresi.
    Alan + is tipi secimi -> malzeme + iscilik tablosu -> PDF / CSV / Metraj aktarimi
    """

    # Malzeme kalemlerini metraj modulune iletmek icin sinyal
    metraj_aktarim_istegi = pyqtSignal(list)   # List[dict]

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db
        self._kalemler: List[MalzemeKalemi] = []
        self._iscilik_kalemleri: List[IscilikKalemi] = []
        self._engine: Optional[InceIslerHizliEngine] = None

        if not _ENGINE_OK:
            QMessageBox.critical(self, 'Hata', 'Ince Isler Hizli motoru yuklenemedi.')
            return

        self._engine = InceIslerHizliEngine(db=db)
        self.setWindowTitle('İnce İşler Hızlı Maliyet Hesabı')
        self.resize(980, 720)
        self.setModal(False)
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        ana_lyt = QVBoxLayout(self)
        ana_lyt.setContentsMargins(10, 10, 10, 10)
        ana_lyt.setSpacing(10)

        ust_lyt = QHBoxLayout()

        # ── Alan ve İşçilik Girişi ────────────────────────────────────────
        alan_grup = QGroupBox('Alan ve İşçilik Girişi')
        alan_grup.setMaximumWidth(370)
        alan_form = QFormLayout(alan_grup)
        alan_form.setSpacing(8)

        self.net_alan_spin = QDoubleSpinBox()
        self.net_alan_spin.setRange(0, 99999)
        self.net_alan_spin.setDecimals(2)
        self.net_alan_spin.setSuffix(' m²')
        self.net_alan_spin.setValue(0)
        self.net_alan_spin.setMinimumWidth(130)
        alan_form.addRow('Net Alan:', self.net_alan_spin)

        kapi_lyt = QHBoxLayout()
        self.kapi_sayi_spin = QSpinBox()
        self.kapi_sayi_spin.setRange(0, 99)
        self.kapi_sayi_spin.setValue(0)
        self.kapi_sayi_spin.setMaximumWidth(60)
        self.kapi_alan_spin = QDoubleSpinBox()
        self.kapi_alan_spin.setRange(0, 20)
        self.kapi_alan_spin.setValue(2.0)
        self.kapi_alan_spin.setSuffix(' m²')
        self.kapi_alan_spin.setDecimals(2)
        self.kapi_alan_spin.setMaximumWidth(80)
        kapi_lyt.addWidget(self.kapi_sayi_spin)
        kapi_lyt.addWidget(QLabel('adet ×'))
        kapi_lyt.addWidget(self.kapi_alan_spin)
        alan_form.addRow('Kapı:', kapi_lyt)

        pencere_lyt = QHBoxLayout()
        self.pencere_sayi_spin = QSpinBox()
        self.pencere_sayi_spin.setRange(0, 99)
        self.pencere_sayi_spin.setValue(0)
        self.pencere_sayi_spin.setMaximumWidth(60)
        self.pencere_alan_spin = QDoubleSpinBox()
        self.pencere_alan_spin.setRange(0, 20)
        self.pencere_alan_spin.setValue(1.5)
        self.pencere_alan_spin.setSuffix(' m²')
        self.pencere_alan_spin.setDecimals(2)
        self.pencere_alan_spin.setMaximumWidth(80)
        pencere_lyt.addWidget(self.pencere_sayi_spin)
        pencere_lyt.addWidget(QLabel('adet ×'))
        pencere_lyt.addWidget(self.pencere_alan_spin)
        alan_form.addRow('Pencere:', pencere_lyt)

        self.efektif_lbl = QLabel('<b>Efektif Alan: 0.00 m²</b>')
        self.efektif_lbl.setStyleSheet('color:#2980b9; font-size:11px;')
        alan_form.addRow('', self.efektif_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        alan_form.addRow(sep)

        self.gunluk_ucret_spin = QDoubleSpinBox()
        self.gunluk_ucret_spin.setRange(0, 99999)
        self.gunluk_ucret_spin.setDecimals(0)
        self.gunluk_ucret_spin.setSuffix(' TL/gün')
        self.gunluk_ucret_spin.setValue(float(GUNLUK_UCRET_VARSAYILAN))
        self.gunluk_ucret_spin.setMinimumWidth(150)
        alan_form.addRow('Usta Günlüğü:', self.gunluk_ucret_spin)

        ucret_not = QLabel('(2026 CŞB norm ortalaması)')
        ucret_not.setStyleSheet('color:#888; font-size:9px;')
        alan_form.addRow('', ucret_not)

        for sp in [self.net_alan_spin, self.kapi_alan_spin, self.pencere_alan_spin]:
            sp.valueChanged.connect(self._efektif_guncelle)
        self.kapi_sayi_spin.valueChanged.connect(self._efektif_guncelle)
        self.pencere_sayi_spin.valueChanged.connect(self._efektif_guncelle)

        ust_lyt.addWidget(alan_grup)

        # ── İş Tipi Seçimi ───────────────────────────────────────────────
        is_grup = QGroupBox('İş Tipi Seçimi')
        is_grup.setMaximumWidth(280)
        is_lyt = QVBoxLayout(is_grup)
        is_lyt.setSpacing(6)

        self.is_checkboxes: dict = {}
        for kod, etiket in IS_TIPLERI.items():
            chk = QCheckBox(etiket)
            chk.setChecked(kod in ('ic_siva', 'alci'))
            is_lyt.addWidget(chk)
            self.is_checkboxes[kod] = chk

        is_lyt.addStretch()
        ust_lyt.addWidget(is_grup)

        # ── CŞB Normları ─────────────────────────────────────────────────
        bilgi_grup = QGroupBox('CŞB Normları')
        bilgi_lyt = QVBoxLayout(bilgi_grup)
        bilgi_lyt.setSpacing(2)
        normlar = [
            ('─ MALZEME ─',                         True),
            ('1 m² iç sıva → 15 kg kum + 3 kg çimento', False),
            ('1 m² alçı → 5 kg alçı tozu (25 kg/torba)',False),
            ('1 m² astar → 0.15 lt',                False),
            ('1 m² iç boya (2 kat) → 0.25 lt',      False),
            ('1 m² dış sıva → 18 kg kum + 4 kg çim.',False),
            ('1 m² dış boya → 0.35 lt',             False),
            ('',                                     False),
            ('─ İŞÇİLİK (m²/gün/usta) ─',           True),
            ('İç Sıva: 25  |  Dış Sıva: 20',         False),
            ('Alçı: 20  |  Astar: 40',               False),
            ('İç Boya: 45  |  Dış Boya: 30',         False),
        ]
        for metin, baslik in normlar:
            lbl = QLabel(metin)
            lbl.setStyleSheet(
                'font-size:9px; color:#2980b9; font-weight:bold;' if baslik
                else 'font-size:9px; color:#555;'
            )
            bilgi_lyt.addWidget(lbl)
        bilgi_lyt.addStretch()
        ust_lyt.addWidget(bilgi_grup)

        ana_lyt.addLayout(ust_lyt)

        # ── Hesapla butonu ────────────────────────────────────────────────
        hesapla_btn = QPushButton('HESAPLA')
        hesapla_btn.setStyleSheet(
            'QPushButton { background:#27ae60; color:white; font-weight:bold; '
            'padding:10px; border-radius:5px; font-size:14px; }'
            'QPushButton:hover { background:#219a52; }'
        )
        hesapla_btn.clicked.connect(self._hesapla)
        ana_lyt.addWidget(hesapla_btn)

        # ── Sonuç Tablosu ────────────────────────────────────────────────
        tablo_grup = QGroupBox('Malzeme ve İşçilik Maliyeti')
        tablo_lyt = QVBoxLayout(tablo_grup)

        self.tablo = QTableWidget(0, 6)
        self.tablo.setHorizontalHeaderLabels([
            'İş Tipi', 'Kalem', 'Miktar / Süre', 'Birim',
            'Birim Fiyat (TL)', 'Toplam (TL)',
        ])
        self.tablo.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        for col in [0, 2, 3, 4, 5]:
            self.tablo.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.tablo.itemChanged.connect(self._fiyat_degisti)
        tablo_lyt.addWidget(self.tablo)

        # Özet satırı
        ozet_lyt = QHBoxLayout()
        self.malzeme_toplam_lbl = QLabel('Malzeme: 0,00 TL')
        self.malzeme_toplam_lbl.setStyleSheet('color:#27ae60; font-size:11px; font-weight:bold;')
        self.iscilik_toplam_lbl = QLabel('İşçilik: 0,00 TL')
        self.iscilik_toplam_lbl.setStyleSheet('color:#1a5276; font-size:11px; font-weight:bold;')
        self.toplam_lbl = QLabel('<b>GENEL TOPLAM: 0,00 TL</b>')
        self.toplam_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.toplam_lbl.setStyleSheet('font-size:14px; color:#2c3e50; padding:4px;')
        ozet_lyt.addWidget(self.malzeme_toplam_lbl)
        ozet_lyt.addSpacing(20)
        ozet_lyt.addWidget(self.iscilik_toplam_lbl)
        ozet_lyt.addStretch()
        ozet_lyt.addWidget(self.toplam_lbl)
        tablo_lyt.addLayout(ozet_lyt)
        ana_lyt.addWidget(tablo_grup)

        # ── Not ──────────────────────────────────────────────────────────
        not_lbl = QLabel(
            'Not: Malzeme birim fiyatlar tedarikçi veritabanından otomatik çekilir. '
            'Sarı hücre = fiyat bulunamadı, çift tıklayarak manuel girin. '
            'İşçilik günlüğünü değiştirip yeniden HESAPLA\'ya basın.'
        )
        not_lbl.setStyleSheet('color:#888; font-size:9px;')
        not_lbl.setWordWrap(True)
        ana_lyt.addWidget(not_lbl)

        # ── Alt Butonlar ─────────────────────────────────────────────────
        alt_lyt = QHBoxLayout()

        pdf_btn = QPushButton('PDF Rapor')
        pdf_btn.setStyleSheet(
            'QPushButton { background:#2980b9; color:white; padding:6px 14px; border-radius:4px; }'
            'QPushButton:hover { background:#1a6fa8; }'
        )
        pdf_btn.clicked.connect(self._pdf_aktar)

        csv_btn = QPushButton('CSV / Excel')
        csv_btn.setStyleSheet(
            'QPushButton { background:#8e44ad; color:white; padding:6px 14px; border-radius:4px; }'
            'QPushButton:hover { background:#7d3c98; }'
        )
        csv_btn.setToolTip('Hesap sonuçlarını CSV olarak kaydet (Excel ile açılabilir)')
        csv_btn.clicked.connect(self._csv_aktar)

        metraj_btn = QPushButton('Metraj Aktarım')
        metraj_btn.setStyleSheet(
            'QPushButton { background:#e67e22; color:white; padding:6px 14px; border-radius:4px; }'
            'QPushButton:hover { background:#ca6f1e; }'
        )
        metraj_btn.setToolTip('Malzeme kalemlerini panoya kopyalar — Excel/Metraj modülüne Ctrl+V ile yapıştırın')
        metraj_btn.clicked.connect(self._metraj_aktar)

        temizle_btn = QPushButton('Temizle')
        temizle_btn.clicked.connect(self._temizle)

        kapat_btn = QPushButton('Kapat')
        kapat_btn.clicked.connect(self.close)

        alt_lyt.addWidget(pdf_btn)
        alt_lyt.addWidget(csv_btn)
        alt_lyt.addWidget(metraj_btn)
        alt_lyt.addWidget(temizle_btn)
        alt_lyt.addStretch()
        alt_lyt.addWidget(kapat_btn)
        ana_lyt.addLayout(alt_lyt)

    # ── Yardımcı ─────────────────────────────────────────────────────────────

    def _efektif_guncelle(self):
        if not self._engine:
            return
        eff = self._engine.efektif_alan(
            self.net_alan_spin.value(),
            self.kapi_sayi_spin.value(),
            self.kapi_alan_spin.value(),
            self.pencere_sayi_spin.value(),
            self.pencere_alan_spin.value(),
        )
        self.efektif_lbl.setText(f'<b>Efektif Alan: {eff:.2f} m²</b>')

    def _secili_is_tipleri(self) -> List[str]:
        return [kod for kod, chk in self.is_checkboxes.items() if chk.isChecked()]

    # ── Hesaplama ────────────────────────────────────────────────────────────

    def _hesapla(self):
        if not self._engine:
            return
        alan = self.net_alan_spin.value()
        if alan <= 0:
            QMessageBox.warning(self, 'Uyarı', 'Lütfen geçerli bir alan değeri girin.')
            return
        is_tipleri = self._secili_is_tipleri()
        if not is_tipleri:
            QMessageBox.warning(self, 'Uyarı', 'En az bir iş tipi seçin.')
            return

        gunluk_ucret = Decimal(str(int(self.gunluk_ucret_spin.value())))

        self._kalemler = self._engine.hesapla_kombo(
            alan=alan,
            is_tipleri=is_tipleri,
            kapi_sayisi=self.kapi_sayi_spin.value(),
            kapi_alan=self.kapi_alan_spin.value(),
            pencere_sayisi=self.pencere_sayi_spin.value(),
            pencere_alan=self.pencere_alan_spin.value(),
        )

        eff_alan = self._engine.efektif_alan(
            alan,
            self.kapi_sayi_spin.value(),
            self.kapi_alan_spin.value(),
            self.pencere_sayi_spin.value(),
            self.pencere_alan_spin.value(),
        )
        self._iscilik_kalemleri = self._engine.hesapla_iscilik(
            is_tipleri=is_tipleri,
            alan=eff_alan,
            gunluk_ucret=gunluk_ucret,
        )

        self._tablo_doldur()

    def _tablo_doldur(self):
        self.tablo.blockSignals(True)
        self.tablo.setRowCount(0)

        # ── Malzeme satırları ──
        for k in self._kalemler:
            row = self.tablo.rowCount()
            self.tablo.insertRow(row)

            miktar_str = f'{k.miktar:.2f}'
            if k.torba_sayisi is not None:
                miktar_str = f'{k.miktar:.2f} ({k.torba_sayisi} torba)'

            sutunlar = [
                IS_TIPLERI.get(k.is_tipi, k.is_tipi),
                k.malzeme_adi,
                miktar_str,
                k.birim,
                f'{float(k.birim_fiyat):.2f}',
                f'{float(k.toplam):.2f}',
            ]
            for col, deger in enumerate(sutunlar):
                item = QTableWidgetItem(deger)
                if col != 4:   # Sadece fiyat sütunu (col=4) düzenlenebilir
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if col in (2, 4, 5)
                    else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                if col == 4 and k.birim_fiyat == 0:
                    item.setBackground(QColor('#FFF9C4'))  # Sari: fiyat yok
                self.tablo.setItem(row, col, item)

        # ── İşçilik satırları (mavi ton) ──
        ISC_BG = QColor('#D6EAF8')
        ISC_BG_ALT = QColor('#EBF5FB')
        for i, k in enumerate(self._iscilik_kalemleri):
            row = self.tablo.rowCount()
            self.tablo.insertRow(row)
            bg = ISC_BG if i % 2 == 0 else ISC_BG_ALT
            sutunlar = [
                k.is_tipi_ad,
                'İşçilik (CŞB norm)',
                f'{k.gerekli_gun:.2f} usta.gün',
                '—',
                f'{float(k.gunluk_ucret):.2f}',
                f'{float(k.toplam):.2f}',
            ]
            for col, deger in enumerate(sutunlar):
                item = QTableWidgetItem(deger)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setBackground(bg)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if col in (2, 4, 5)
                    else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                self.tablo.setItem(row, col, item)

        self.tablo.blockSignals(False)
        self._toplam_guncelle()

    def _fiyat_degisti(self, item: QTableWidgetItem):
        """Fiyat sutunu (col=4) duzenlenince toplami guncelle — sadece malzeme satirlari."""
        if item.column() != 4:
            return
        row = item.row()
        if row >= len(self._kalemler):  # Iscilik satirlari duzenlenemez
            return
        try:
            yeni_fiyat = Decimal(item.text().replace(',', '.'))
        except Exception:
            return
        self._engine.fiyat_manuel_guncelle(self._kalemler, row, yeni_fiyat)
        toplam_item = self.tablo.item(row, 5)
        if toplam_item:
            self.tablo.blockSignals(True)
            toplam_item.setText(f'{float(self._kalemler[row].toplam):.2f}')
            self.tablo.blockSignals(False)
        self._toplam_guncelle()

    def _toplam_guncelle(self):
        if not self._engine or not self._kalemler:
            self.malzeme_toplam_lbl.setText('Malzeme: 0,00 TL')
            self.iscilik_toplam_lbl.setText('İşçilik: 0,00 TL')
            self.toplam_lbl.setText('<b>GENEL TOPLAM: 0,00 TL</b>')
            return
        mal_t = self._engine.malzeme_toplam(self._kalemler)
        isc_t = self._engine.iscilik_toplam(self._iscilik_kalemleri)
        genel = self._engine.genel_toplam(self._kalemler, self._iscilik_kalemleri)
        self.malzeme_toplam_lbl.setText(f'Malzeme: {float(mal_t):,.2f} TL')
        self.iscilik_toplam_lbl.setText(f'İşçilik: {float(isc_t):,.2f} TL')
        self.toplam_lbl.setText(f'<b>GENEL TOPLAM: {float(genel):,.2f} TL</b>')

    def _temizle(self):
        self._kalemler = []
        self._iscilik_kalemleri = []
        self.tablo.setRowCount(0)
        self.net_alan_spin.setValue(0)
        self.kapi_sayi_spin.setValue(0)
        self.pencere_sayi_spin.setValue(0)
        self.efektif_lbl.setText('<b>Efektif Alan: 0.00 m²</b>')
        self.malzeme_toplam_lbl.setText('Malzeme: 0,00 TL')
        self.iscilik_toplam_lbl.setText('İşçilik: 0,00 TL')
        self.toplam_lbl.setText('<b>GENEL TOPLAM: 0,00 TL</b>')

    # ── Dışa aktarım ─────────────────────────────────────────────────────────

    def _pdf_aktar(self):
        if not self._kalemler:
            QMessageBox.information(self, 'Bilgi', 'Önce hesaplama yapın.')
            return
        dosya, _ = QFileDialog.getSaveFileName(
            self, 'PDF Kaydet', 'ince_isler_hesap.pdf', 'PDF (*.pdf)'
        )
        if not dosya:
            return
        basarili = self._engine.pdf_rapor(
            kalemler=self._kalemler,
            alan=self.net_alan_spin.value(),
            is_tipleri=self._secili_is_tipleri(),
            cikti_yolu=dosya,
            iscilik_kalemleri=self._iscilik_kalemleri or None,
        )
        if basarili:
            QMessageBox.information(self, 'Hazır', f'PDF oluşturuldu:\n{dosya}')
        else:
            QMessageBox.warning(self, 'Hata', 'PDF oluşturulamadı.')

    def _csv_aktar(self):
        if not self._kalemler:
            QMessageBox.information(self, 'Bilgi', 'Önce hesaplama yapın.')
            return
        dosya, _ = QFileDialog.getSaveFileName(
            self, 'CSV Kaydet', 'ince_isler_hesap.csv', 'CSV Dosyası (*.csv)'
        )
        if not dosya:
            return
        basarili = self._engine.csv_disari_aktar(
            kalemler=self._kalemler,
            iscilik_kalemleri=self._iscilik_kalemleri or None,
            dosya_yolu=dosya,
        )
        if basarili:
            QMessageBox.information(
                self, 'Hazır',
                f'CSV oluşturuldu:\n{dosya}\n\nExcel ile doğrudan açabilirsiniz.'
            )
        else:
            QMessageBox.warning(self, 'Hata', 'CSV oluşturulamadı.')

    def _metraj_aktar(self):
        """
        Malzeme kalemlerini iki yolla ilet:
        1. metraj_aktarim_istegi sinyali (main_window bağlıysa metraj modülüne gider)
        2. Panoya tab-separated kopyala (Excel/LibreOffice Calc'a yapıştırılabilir)
        """
        if not self._kalemler:
            QMessageBox.information(self, 'Bilgi', 'Önce hesaplama yapın.')
            return

        payload = [
            {
                'ad': k.malzeme_adi,
                'miktar': k.miktar,
                'birim': k.birim,
                'birim_fiyat': float(k.birim_fiyat),
                'toplam': float(k.toplam),
                'is_tipi': IS_TIPLERI.get(k.is_tipi, k.is_tipi),
            }
            for k in self._kalemler
        ]
        self.metraj_aktarim_istegi.emit(payload)

        # Panoya kopyala (tab-separated → Excel uyumlu)
        satirlar = ['İş Tipi\tMalzeme\tMiktar\tBirim\tBirim Fiyat (TL)\tToplam (TL)']
        for k in self._kalemler:
            satirlar.append(
                f'{IS_TIPLERI.get(k.is_tipi, k.is_tipi)}\t'
                f'{k.malzeme_adi}\t'
                f'{k.miktar:.2f}\t'
                f'{k.birim}\t'
                f'{float(k.birim_fiyat):.2f}\t'
                f'{float(k.toplam):.2f}'
            )
        clipboard = QGuiApplication.clipboard()
        clipboard.setText('\n'.join(satirlar))

        QMessageBox.information(
            self, 'Metraj Aktarım',
            f'{len(self._kalemler)} malzeme kalemi panoya kopyalandı.\n\n'
            'Excel veya Metraj modülüne Ctrl+V ile yapıştırabilirsiniz.'
        )
