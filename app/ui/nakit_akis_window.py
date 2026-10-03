"""
Nakit Akis Projeksiyonu Penceresi
Gantt planlamasindan aylik nakit giris/cikis gorsellestirmesi

Kullanim:
  w = NakitAkisWindow(gantt_engine=ge, parent=main_window)
  w.show()
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Optional, List

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QFormLayout,
    QLabel, QPushButton, QDoubleSpinBox, QSpinBox, QComboBox,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QTabWidget, QMessageBox, QFileDialog,
    QListWidget, QListWidgetItem, QCheckBox, QFrame,
    QSizePolicy,
)

logger = logging.getLogger(__name__)

try:
    from app.core.nakit_akis_engine import NakitAkisEngine, NakitAkisParametreleri, AylikAkis
    _ENGINE_OK = True
except Exception as e:
    logger.error("NakitAkisEngine yuklenemedi: %s", e)
    _ENGINE_OK = False

try:
    import matplotlib
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    _MATPLOT_OK = True
except Exception:
    _MATPLOT_OK = False


# ─── HESAP THREAD ────────────────────────────────────────────────────────────

class HesapThread(QThread):
    """Agir hesaplari arka planda yap."""
    tamamlandi = pyqtSignal(object)  # list[AylikAkis]
    hata = pyqtSignal(str)

    def __init__(self, engine: 'NakitAkisEngine'):
        super().__init__()
        self.engine = engine

    def run(self):
        try:
            akislar = self.engine.proje_akisi()
            self.tamamlandi.emit(akislar)
        except Exception as e:
            self.hata.emit(str(e))


# ─── GRAFIK WIDGET ───────────────────────────────────────────────────────────

class NakitGrafikWidget(QWidget):
    """matplotlib bar + line grafikler."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)

        if not _MATPLOT_OK:
            lyt.addWidget(QLabel('Grafik: matplotlib kurulu degil.'))
            self.canvas = None
            return

        self.fig = Figure(figsize=(10, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.fig)
        lyt.addWidget(self.canvas)

    def guncelle(self, akislar: List[AylikAkis]):
        if not _MATPLOT_OK or not self.canvas or not akislar:
            return

        self.fig.clear()
        axlar = self.fig.subplots(2, 1)

        aylar = [a.ay_str for a in akislar]
        gelirler = [float(a.net_hakedis_gelir) / 1e6 for a in akislar]
        giderler = [float(a.toplam_cikis) / 1e6 for a in akislar]
        kumulatif = [float(a.kumulatif) / 1e6 for a in akislar]

        # Ust: bar chart
        ax1 = axlar[0]
        x = range(len(aylar))
        ax1.bar([i - 0.2 for i in x], gelirler, 0.35, label='Net Hakedis Geliri', color='#27ae60')
        ax1.bar([i + 0.2 for i in x], giderler, 0.35, label='Toplam Gider', color='#e74c3c')
        ax1.set_xticks(list(x))
        ax1.set_xticklabels(aylar, rotation=45, ha='right', fontsize=7)
        ax1.set_ylabel('Milyon TL')
        ax1.set_title('Aylik Nakit Giris / Cikis')
        ax1.legend(fontsize=8)
        ax1.grid(axis='y', linestyle='--', alpha=0.5)

        # Alt: kumulatif line chart
        ax2 = axlar[1]
        renkler = ['#e74c3c' if k < 0 else '#2980b9' for k in kumulatif]
        ax2.plot(list(x), kumulatif, color='#2980b9', linewidth=2, marker='o', markersize=4)
        ax2.fill_between(
            list(x), kumulatif, 0,
            where=[k < 0 for k in kumulatif], alpha=0.3, color='#e74c3c', label='Negatif bolge'
        )
        ax2.fill_between(
            list(x), kumulatif, 0,
            where=[k >= 0 for k in kumulatif], alpha=0.2, color='#27ae60'
        )
        ax2.axhline(0, color='black', linewidth=0.8, linestyle='--')
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(aylar, rotation=45, ha='right', fontsize=7)
        ax2.set_ylabel('Milyon TL')
        ax2.set_title('Kumulatif Nakit Pozisyonu')
        ax2.legend(fontsize=8)
        ax2.grid(axis='y', linestyle='--', alpha=0.5)

        self.canvas.draw()


# ─── ANA PENCERE ─────────────────────────────────────────────────────────────

class NakitAkisWindow(QDialog):
    """
    Nakit Akis Projeksiyonu ana penceresi.
    Sol: parametreler + ozet
    Sag: tablo / grafik sekmesi + uyarilar
    """

    def __init__(self, gantt_engine=None, parent=None):
        super().__init__(parent)
        self.gantt_engine = gantt_engine
        self._akislar: List[AylikAkis] = []
        self._hesap_thread: Optional[HesapThread] = None

        if not _ENGINE_OK:
            QMessageBox.critical(self, 'Hata', 'Nakit Akis motoru yuklenemedi.')
            QTimer.singleShot(0, self.close)
            return

        self.setWindowTitle('Nakit Akis Projeksiyonu')
        self.resize(1200, 740)
        self.setModal(False)
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        ana_lyt = QVBoxLayout(self)
        ana_lyt.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Sol Panel: Parametreler ──
        sol = QWidget()
        sol.setFixedWidth(300)
        sol_lyt = QVBoxLayout(sol)
        sol_lyt.setSpacing(8)

        # Sozlesme bilgileri
        sb_grup = QGroupBox('Sozlesme Bilgileri')
        sb_form = QFormLayout(sb_grup)

        self.sozlesme_spin = QDoubleSpinBox()
        self.sozlesme_spin.setRange(0, 999_999_999_999)
        self.sozlesme_spin.setDecimals(0)
        self.sozlesme_spin.setSuffix(' TL')
        self.sozlesme_spin.setSingleStep(100_000)
        self.sozlesme_spin.setValue(10_000_000)
        sb_form.addRow('Sozlesme Bedeli:', self.sozlesme_spin)

        self.periyot_combo = QComboBox()
        self.periyot_combo.addItems(['Aylik', '15 Gunluk'])
        sb_form.addRow('Hakedis Periyotu:', self.periyot_combo)

        self.odeme_gecikme_spin = QSpinBox()
        self.odeme_gecikme_spin.setRange(0, 180)
        self.odeme_gecikme_spin.setValue(30)
        self.odeme_gecikme_spin.setSuffix(' gun')
        sb_form.addRow('Odeme Gecikmesi:', self.odeme_gecikme_spin)
        sol_lyt.addWidget(sb_grup)

        # Kesintiler
        kes_grup = QGroupBox('Kesintiler')
        kes_lyt = QVBoxLayout(kes_grup)
        self.chk_kesin_teminat = QCheckBox('Kesin Teminat (%6)')
        self.chk_kesin_teminat.setChecked(True)
        self.chk_sgk = QCheckBox('SGK Prim (%1)')
        self.chk_sgk.setChecked(True)
        self.chk_gv = QCheckBox('GV Stopaj (%3)')
        self.chk_gv.setChecked(True)

        self.kdv_spin = QDoubleSpinBox()
        self.kdv_spin.setRange(0, 50)
        self.kdv_spin.setValue(20)
        self.kdv_spin.setSuffix('%')
        kdv_lyt = QHBoxLayout()
        kdv_lyt.addWidget(QLabel('KDV:'))
        kdv_lyt.addWidget(self.kdv_spin)

        kes_lyt.addWidget(self.chk_kesin_teminat)
        kes_lyt.addWidget(self.chk_sgk)
        kes_lyt.addWidget(self.chk_gv)
        kes_lyt.addLayout(kdv_lyt)
        sol_lyt.addWidget(kes_grup)

        # Gider oranlari
        gider_grup = QGroupBox('Gider Oranlari (Toplam %100)')
        gider_form = QFormLayout(gider_grup)

        def oran_spin(deger):
            sp = QDoubleSpinBox()
            sp.setRange(0, 100)
            sp.setDecimals(1)
            sp.setSuffix('%')
            sp.setValue(deger)
            return sp

        self.iscilik_oran_spin = oran_spin(30)
        self.malzeme_oran_spin = oran_spin(45)
        self.taseron_oran_spin = oran_spin(15)
        gider_form.addRow('Iscilik:', self.iscilik_oran_spin)
        gider_form.addRow('Malzeme:', self.malzeme_oran_spin)
        gider_form.addRow('Taseron:', self.taseron_oran_spin)
        sol_lyt.addWidget(gider_grup)

        # Vade
        vade_grup = QGroupBox('Odeme Vadeleri')
        vade_form = QFormLayout(vade_grup)

        self.mal_vade_spin = QSpinBox()
        self.mal_vade_spin.setRange(0, 180)
        self.mal_vade_spin.setValue(30)
        self.mal_vade_spin.setSuffix(' gun')
        self.tas_vade_spin = QSpinBox()
        self.tas_vade_spin.setRange(0, 180)
        self.tas_vade_spin.setValue(30)
        self.tas_vade_spin.setSuffix(' gun')
        vade_form.addRow('Malzeme Vadesi:', self.mal_vade_spin)
        vade_form.addRow('Taseron Vadesi:', self.tas_vade_spin)
        sol_lyt.addWidget(vade_grup)

        # Hesapla
        hesapla_btn = QPushButton('HESAPLA')
        hesapla_btn.setStyleSheet(
            'QPushButton { background:#2980b9; color:white; font-weight:bold; '
            'padding:10px; border-radius:5px; font-size:13px; }'
            'QPushButton:hover { background:#1f6391; }'
        )
        hesapla_btn.clicked.connect(self._hesapla)
        sol_lyt.addWidget(hesapla_btn)

        # Ozet kutusu
        self.ozet_grup = QGroupBox('Ozet')
        ozet_form = QFormLayout(self.ozet_grup)
        self.lbl_toplam_gelir = QLabel('-')
        self.lbl_toplam_gider = QLabel('-')
        self.lbl_net = QLabel('-')
        self.lbl_min_kumulatif = QLabel('-')
        self.lbl_kritik_ay = QLabel('-')
        ozet_form.addRow('Toplam Gelir:', self.lbl_toplam_gelir)
        ozet_form.addRow('Toplam Gider:', self.lbl_toplam_gider)
        ozet_form.addRow('Net Pozisyon:', self.lbl_net)
        ozet_form.addRow('En Dusuk Nakit:', self.lbl_min_kumulatif)
        ozet_form.addRow('Kritik Ay Sayisi:', self.lbl_kritik_ay)
        sol_lyt.addWidget(self.ozet_grup)
        sol_lyt.addStretch()
        splitter.addWidget(sol)

        # ── Sag Panel ──
        sag = QWidget()
        sag_lyt = QVBoxLayout(sag)
        sag_lyt.setContentsMargins(4, 4, 4, 4)

        self.tab_widget = QTabWidget()

        # Tablo sekmesi
        tablo_widget = QWidget()
        tablo_lyt = QVBoxLayout(tablo_widget)
        self.tablo = QTableWidget(0, 9)
        self.tablo.setHorizontalHeaderLabels([
            'Ay', 'Is Bedeli (TL)', 'Net Hakedis Gelir',
            'Iscilik Cikis', 'Malzeme Cikis', 'Taseron Cikis',
            'Toplam Cikis', 'Aylik Net', 'Kumulatif (TL)',
        ])
        self.tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.tablo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tablo_lyt.addWidget(self.tablo)
        self.tab_widget.addTab(tablo_widget, 'Tablo')

        # Grafik sekmesi
        self.grafik_widget = NakitGrafikWidget()
        self.tab_widget.addTab(self.grafik_widget, 'Grafik')

        sag_lyt.addWidget(self.tab_widget, stretch=1)

        # Uyarilar listesi
        uyari_grup = QGroupBox('Kritik Nakit Acigi Olan Aylar')
        uyari_lyt = QVBoxLayout(uyari_grup)
        self.uyari_liste = QListWidget()
        self.uyari_liste.setFixedHeight(100)
        uyari_lyt.addWidget(self.uyari_liste)
        sag_lyt.addWidget(uyari_grup)

        splitter.addWidget(sag)
        splitter.setSizes([300, 900])
        ana_lyt.addWidget(splitter)

        # Alt butonlar
        alt_lyt = QHBoxLayout()
        csv_btn = QPushButton('CSV / Excel Aktar')
        csv_btn.clicked.connect(self._csv_aktar)
        pdf_btn = QPushButton('PDF Rapor')
        pdf_btn.setStyleSheet(
            'QPushButton { background:#2c3e50; color:white; padding:6px 14px; '
            'border-radius:4px; }'
        )
        pdf_btn.clicked.connect(self._pdf_aktar)
        kapat_btn = QPushButton('Kapat')
        kapat_btn.clicked.connect(self.close)
        alt_lyt.addWidget(csv_btn)
        alt_lyt.addWidget(pdf_btn)
        alt_lyt.addStretch()
        alt_lyt.addWidget(kapat_btn)
        ana_lyt.addLayout(alt_lyt)

    # ── HESAP ────────────────────────────────────────────────────────────────

    def _parametreler_al(self) -> NakitAkisParametreleri:
        return NakitAkisParametreleri(
            sozlesme_bedeli=Decimal(str(int(self.sozlesme_spin.value()))),
            hakedis_periyodu='aylik' if self.periyot_combo.currentIndex() == 0 else '15gun',
            odeme_gecikme_gun=self.odeme_gecikme_spin.value(),
            kdv_orani=Decimal(str(self.kdv_spin.value() / 100)),
            kesin_teminat_aktif=self.chk_kesin_teminat.isChecked(),
            sgk_kesinti_aktif=self.chk_sgk.isChecked(),
            gv_stopaj_aktif=self.chk_gv.isChecked(),
            iscilik_oran=Decimal(str(self.iscilik_oran_spin.value() / 100)),
            malzeme_oran=Decimal(str(self.malzeme_oran_spin.value() / 100)),
            taseron_oran=Decimal(str(self.taseron_oran_spin.value() / 100)),
            malzeme_odeme_gecikme=self.mal_vade_spin.value(),
            taseron_odeme_gecikme=self.tas_vade_spin.value(),
        )

    def _hesapla(self):
        if not self.gantt_engine:
            QMessageBox.warning(
                self, 'Uyari',
                'Gantt motoru bagli degil.\n'
                'Once Gantt sekmesini acin ve is programini kaydedin.'
            )
            return

        p = self._parametreler_al()
        engine = NakitAkisEngine(gantt_engine=self.gantt_engine, parametreler=p)

        # Kontrol: Gantt'ta tarihli task var mi?
        dagitim = engine.aylik_is_dagilimi()
        if not dagitim:
            QMessageBox.warning(
                self, 'Uyari',
                'Gantt planinda tarihlendirilmis is kalemi bulunamadi.\n'
                'Gantt sekmesinde "Is Programini Hesapla" butonuna basin.'
            )
            return

        self._engine = engine
        self._hesap_thread = HesapThread(engine)
        self._hesap_thread.tamamlandi.connect(self._hesap_tamamlandi)
        self._hesap_thread.hata.connect(self._hesap_hata)
        self._hesap_thread.start()

    def _hesap_tamamlandi(self, akislar: List[AylikAkis]):
        self._akislar = akislar
        self._tablo_doldur(akislar)
        self.grafik_widget.guncelle(akislar)
        self._ozet_guncelle(akislar)
        self._uyarilar_guncelle(akislar)

    def _hesap_hata(self, mesaj: str):
        logger.error("Hesap hatasi: %s", mesaj)
        QMessageBox.critical(self, 'Hesap Hatasi', f'Hesaplama basarisiz:\n{mesaj}')

    # ── TABLO ────────────────────────────────────────────────────────────────

    def _tablo_doldur(self, akislar: List[AylikAkis]):
        self.tablo.blockSignals(True)
        self.tablo.setRowCount(0)

        for akis in akislar:
            row = self.tablo.rowCount()
            self.tablo.insertRow(row)

            sutunlar = [
                akis.ay_str,
                f'{float(akis.is_bedeli_brut):,.0f}',
                f'{float(akis.net_hakedis_gelir):,.0f}',
                f'{float(akis.iscilik_cikis):,.0f}',
                f'{float(akis.malzeme_cikis):,.0f}',
                f'{float(akis.taseron_cikis):,.0f}',
                f'{float(akis.toplam_cikis):,.0f}',
                f'{float(akis.aylik_net):,.0f}',
                f'{float(akis.kumulatif):,.0f}',
            ]

            for col, deger in enumerate(sutunlar):
                item = QTableWidgetItem(deger)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if col > 0 else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                # Kumulatif negatifse kirmizi
                if col == 8 and akis.kumulatif < 0:
                    item.setBackground(QColor('#FFCCCC'))
                # Aylik net negatifse turuncu
                elif col == 7 and akis.aylik_net < 0:
                    item.setBackground(QColor('#FFE0B2'))
                self.tablo.setItem(row, col, item)

        self.tablo.blockSignals(False)

    # ── OZET ─────────────────────────────────────────────────────────────────

    def _ozet_guncelle(self, akislar: List[AylikAkis]):
        if not akislar or not hasattr(self, '_engine'):
            return
        ozet = self._engine.ozet_istatistik(akislar)

        def fmt(v):
            return f'{float(v):,.0f} TL'

        self.lbl_toplam_gelir.setText(fmt(ozet.get('toplam_gelir', 0)))
        self.lbl_toplam_gider.setText(fmt(ozet.get('toplam_gider', 0)))
        net = ozet.get('net_pozisyon', Decimal('0'))
        self.lbl_net.setText(fmt(net))
        self.lbl_net.setStyleSheet(
            'color: #e74c3c; font-weight:bold;' if net < 0
            else 'color: #27ae60; font-weight:bold;'
        )
        self.lbl_min_kumulatif.setText(fmt(ozet.get('min_kumulatif', 0)))
        self.lbl_kritik_ay.setText(str(ozet.get('kritik_ay_sayisi', 0)))

    def _uyarilar_guncelle(self, akislar: List[AylikAkis]):
        self.uyari_liste.clear()
        if not hasattr(self, '_engine'):
            return
        aciklar = self._engine.kritik_aciklar(akislar)
        if not aciklar:
            item = QListWidgetItem('Nakit acigi yok - proje mali dengede.')
            item.setForeground(QColor('#27ae60'))
            self.uyari_liste.addItem(item)
        else:
            for ay, tutar, mesaj in aciklar:
                item = QListWidgetItem(mesaj)
                item.setForeground(QColor('#e74c3c'))
                self.uyari_liste.addItem(item)

    # ── EXPORT ───────────────────────────────────────────────────────────────

    def _csv_aktar(self):
        if not self._akislar:
            QMessageBox.information(self, 'Bilgi', 'Once hesaplama yapin.')
            return
        dosya, _ = QFileDialog.getSaveFileName(
            self, 'CSV Kaydet', 'nakit_akis.csv', 'CSV (*.csv)'
        )
        if not dosya:
            return
        if not hasattr(self, '_engine'):
            return
        if self._engine.excel_export(self._akislar, dosya):
            QMessageBox.information(self, 'Hazir', f'CSV kaydedildi:\n{dosya}')
        else:
            QMessageBox.warning(self, 'Hata', 'CSV kaydedilemedi.')

    def _pdf_aktar(self):
        if not self._akislar:
            QMessageBox.information(self, 'Bilgi', 'Once hesaplama yapin.')
            return
        dosya, _ = QFileDialog.getSaveFileName(
            self, 'PDF Kaydet', 'nakit_akis.pdf', 'PDF (*.pdf)'
        )
        if not dosya:
            return
        if not hasattr(self, '_engine'):
            return
        if self._engine.pdf_export(self._akislar, dosya):
            QMessageBox.information(self, 'Hazir', f'PDF olusturuldu:\n{dosya}')
        else:
            QMessageBox.warning(self, 'Hata', 'PDF olusturulamadi. reportlab kontrol edin.')
