"""
Santiye Gunluk Rapor Penceresi
Takvim bazli kayit + form + PDF santiye defteri

Kullanim:
  w = SantiyeGunlukWindow(db=main_window.db, proje_id=1, parent=main_window)
  w.show()
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    Qt, QDate, QThread, pyqtSignal, QTimer,
)
from PyQt6.QtGui import QColor, QTextCharFormat, QFont, QBrush
from PyQt6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QFormLayout,
    QSplitter, QLabel, QPushButton, QDateEdit, QSpinBox,
    QDoubleSpinBox, QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QComboBox, QCalendarWidget,
    QListWidget, QListWidgetItem, QMessageBox, QFileDialog,
    QScrollArea, QFrame, QSizePolicy, QAbstractItemView,
    QDialog as _QDialog, QDialogButtonBox,
)

logger = logging.getLogger(__name__)

try:
    from app.core.santiye_gunluk_engine import (
        SantiyeGunlukEngine, SantiyeGunlukKayit, MalzemeKalemi,
    )
    _ENGINE_OK = True
except Exception as e:
    logger.error("SantiyeGunlukEngine yuklenemedi: %s", e)
    _ENGINE_OK = False


# ─── HAVA OTO-DOLDUR THREAD ─────────────────────────────────────────────────

class HavaOtoDoldurThread(QThread):
    """Bugunun havasini arka planda cek, form alanlarina doldur."""
    veri_hazir = pyqtSignal(object)   # HavaDurumu nesnesi veya None

    def __init__(self, sehir: str, hedef_tarih: date):
        super().__init__()
        self.sehir = sehir
        self.hedef_tarih = hedef_tarih

    def run(self):
        try:
            from app.core.hava_durumu import HavaDurumuServisi
            servis = HavaDurumuServisi()
            konum = servis.sehir_ara(self.sehir)
            if not konum:
                self.veri_hazir.emit(None)
                return
            tahminler = servis.tahmin_al(konum['lat'], konum['lon'])
            if not tahminler:
                self.veri_hazir.emit(None)
                return
            for hava in tahminler:
                if hava.tarih == self.hedef_tarih:
                    self.veri_hazir.emit(hava)
                    return
            # Hedef tarih 7 gunluk oncekide yoksa ilk gunun verisini kullan
            self.veri_hazir.emit(tahminler[0] if tahminler else None)
        except Exception as e:
            logger.warning("Hava verisi alinamadi: %s", e)
            self.veri_hazir.emit(None)


# ─── PDF TARIH ARALIK DİYALOĞU ──────────────────────────────────────────────

class TarihAralikDialog(_QDialog):
    """PDF icin baslangic/bitis tarih secimi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF Tarih Aralik Sec")
        self.setModal(True)
        self.resize(320, 150)

        layout = QFormLayout(self)

        self.bas_edit = QDateEdit()
        self.bas_edit.setCalendarPopup(True)
        self.bas_edit.setDate(QDate.currentDate().addDays(-30))
        self.bas_edit.setDisplayFormat('dd.MM.yyyy')

        self.bit_edit = QDateEdit()
        self.bit_edit.setCalendarPopup(True)
        self.bit_edit.setDate(QDate.currentDate())
        self.bit_edit.setDisplayFormat('dd.MM.yyyy')

        layout.addRow('Baslangic:', self.bas_edit)
        layout.addRow('Bitis:', self.bit_edit)

        butonlar = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        butonlar.accepted.connect(self.accept)
        butonlar.rejected.connect(self.reject)
        layout.addRow(butonlar)

    def tarihler(self):
        """(baslangic: date, bitis: date) demeti dondur."""
        qb = self.bas_edit.date()
        qe = self.bit_edit.date()
        return (
            date(qb.year(), qb.month(), qb.day()),
            date(qe.year(), qe.month(), qe.day()),
        )


# ─── ANA PENCERE ────────────────────────────────────────────────────────────

class SantiyeGunlukWindow(QDialog):
    """
    Santiye Gunluk Rapor ana penceresi.
    Sol: proje + takvim + kayit listesi
    Sag: kayit formu
    """

    def __init__(self, db=None, proje_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.aktif_proje_id: int = proje_id or 0
        self.aktif_kayit_id: Optional[int] = None
        self._hava_thread: Optional[HavaOtoDoldurThread] = None
        self._sehir = 'Ankara'   # Varsayilan; projeden gelirse guncellenir

        if not _ENGINE_OK:
            QMessageBox.critical(self, 'Hata', 'Santiye Gunluk motoru yuklenemedi.')
            QTimer.singleShot(0, self.close)
            return

        self.engine = SantiyeGunlukEngine()

        self.setWindowTitle('Santiye Gunluk Rapor - Santiye Defteri')
        self.resize(1100, 720)
        self.setModal(False)

        self._build_ui()
        self._proje_combo_doldur()
        self._takvim_guncelle()

    # ── UI KURULUM ───────────────────────────────────────────────────────────

    def _build_ui(self):
        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Sol Panel ──
        sol = QWidget()
        sol.setFixedWidth(290)
        sol_layout = QVBoxLayout(sol)
        sol_layout.setContentsMargins(4, 4, 4, 4)
        sol_layout.setSpacing(6)

        # Proje secimi
        proje_grup = QGroupBox('Proje')
        proje_lyt = QVBoxLayout(proje_grup)
        self.proje_combo = QComboBox()
        self.proje_combo.currentIndexChanged.connect(self._proje_degisti)
        proje_lyt.addWidget(self.proje_combo)
        sol_layout.addWidget(proje_grup)

        # Takvim
        takvim_grup = QGroupBox('Takvim (Yesil = Kayitli Gun)')
        takvim_lyt = QVBoxLayout(takvim_grup)
        self.takvim = QCalendarWidget()
        self.takvim.setGridVisible(True)
        self.takvim.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self.takvim.selectionChanged.connect(self._takvim_tarih_secildi)
        takvim_lyt.addWidget(self.takvim)
        sol_layout.addWidget(takvim_grup)

        # Kayit listesi
        liste_grup = QGroupBox('Bu Ayin Kayitlari')
        liste_lyt = QVBoxLayout(liste_grup)
        self.kayit_liste = QListWidget()
        self.kayit_liste.setMaximumHeight(160)
        self.kayit_liste.itemClicked.connect(self._listeden_kayit_sec)
        liste_lyt.addWidget(self.kayit_liste)
        sol_layout.addWidget(liste_grup)

        splitter.addWidget(sol)

        # ── Sag Panel: Form ──
        sag = QWidget()
        sag_layout = QVBoxLayout(sag)
        sag_layout.setContentsMargins(4, 4, 4, 4)
        sag_layout.setSpacing(6)

        # Scroll area form icin
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(8)

        # Tarih
        tarih_grup = QGroupBox('Tarih')
        tarih_lyt = QHBoxLayout(tarih_grup)
        self.tarih_edit = QDateEdit()
        self.tarih_edit.setCalendarPopup(True)
        self.tarih_edit.setDate(QDate.currentDate())
        self.tarih_edit.setDisplayFormat('dd.MM.yyyy')
        self.tarih_edit.dateChanged.connect(self._tarih_degisti)
        tarih_lyt.addWidget(self.tarih_edit)
        tarih_lyt.addStretch()
        yeni_btn = QPushButton('Yeni Kayit')
        yeni_btn.clicked.connect(self._yeni_kayit)
        tarih_lyt.addWidget(yeni_btn)
        form_layout.addWidget(tarih_grup)

        # Hava durumu
        hava_grup = QGroupBox('Hava Durumu')
        hava_lyt = QFormLayout(hava_grup)

        hava_ust = QHBoxLayout()
        self.hava_max_spin = QDoubleSpinBox()
        self.hava_max_spin.setRange(-50, 60)
        self.hava_max_spin.setSuffix(' C')
        self.hava_max_spin.setDecimals(1)
        self.hava_max_spin.setValue(20)
        self.hava_min_spin = QDoubleSpinBox()
        self.hava_min_spin.setRange(-50, 60)
        self.hava_min_spin.setSuffix(' C')
        self.hava_min_spin.setDecimals(1)
        self.hava_min_spin.setValue(10)
        self.hava_durum_edit = QComboBox()
        self.hava_durum_edit.addItems([
            'Acik', 'Parcali Bulutlu', 'Kapali', 'Yagmurlu',
            'Karli', 'Sisli', 'Firtinayi',
        ])
        self.hava_durum_edit.setEditable(True)
        self.hava_yagis_spin = QDoubleSpinBox()
        self.hava_yagis_spin.setRange(0, 999)
        self.hava_yagis_spin.setSuffix(' mm')
        self.hava_yagis_spin.setDecimals(1)

        hava_ust.addWidget(QLabel('Max:'))
        hava_ust.addWidget(self.hava_max_spin)
        hava_ust.addWidget(QLabel('Min:'))
        hava_ust.addWidget(self.hava_min_spin)
        hava_ust.addStretch()

        self.hava_otodoldur_btn = QPushButton('Otomatik Doldur')
        self.hava_otodoldur_btn.setToolTip('Bugunun havasini internetten cek')
        self.hava_otodoldur_btn.clicked.connect(self._hava_otodoldur)
        hava_ust.addWidget(self.hava_otodoldur_btn)

        hava_lyt.addRow('Sicaklik:', hava_ust)
        hava_lyt.addRow('Durum:', self.hava_durum_edit)
        hava_lyt.addRow('Yagis:', self.hava_yagis_spin)
        form_layout.addWidget(hava_grup)

        # Ekip
        ekip_grup = QGroupBox('Calisma Ekibi')
        ekip_lyt = QHBoxLayout(ekip_grup)

        def _spin(label):
            w = QWidget()
            lyt = QVBoxLayout(w)
            lyt.setContentsMargins(2, 2, 2, 2)
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sp = QSpinBox()
            sp.setRange(0, 999)
            sp.setMinimumWidth(70)
            lyt.addWidget(lbl)
            lyt.addWidget(sp)
            return w, sp

        w, self.usta_spin = _spin('Usta')
        ekip_lyt.addWidget(w)
        w, self.yardimci_spin = _spin('Yardimci')
        ekip_lyt.addWidget(w)
        w, self.sef_spin = _spin('Santiye Sefi')
        ekip_lyt.addWidget(w)
        w, self.taseron_spin = _spin('Taseron')
        ekip_lyt.addWidget(w)
        ekip_lyt.addStretch()
        form_layout.addWidget(ekip_grup)

        # Yapilan isler
        isler_grup = QGroupBox('Yapilan Isler')
        isler_lyt = QVBoxLayout(isler_grup)
        self.isler_edit = QPlainTextEdit()
        self.isler_edit.setPlaceholderText(
            'Ornek: 3. kat kolon beton dokumu yapildi. Zemin kat siva devam ediyor...'
        )
        self.isler_edit.setFixedHeight(100)
        isler_lyt.addWidget(self.isler_edit)
        form_layout.addWidget(isler_grup)

        # Kullanilan malzeme
        malzeme_grup = QGroupBox('Kullanilan Malzeme')
        malzeme_lyt = QVBoxLayout(malzeme_grup)

        self.malzeme_tablo = QTableWidget(0, 3)
        self.malzeme_tablo.setHorizontalHeaderLabels(['Malzeme Adi', 'Miktar', 'Birim'])
        self.malzeme_tablo.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.malzeme_tablo.setFixedHeight(130)
        self.malzeme_tablo.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        malzeme_lyt.addWidget(self.malzeme_tablo)

        mal_btn_lyt = QHBoxLayout()
        mal_ekle_btn = QPushButton('+ Satir Ekle')
        mal_ekle_btn.clicked.connect(self._malzeme_satirı_ekle)
        mal_sil_btn = QPushButton('- Satir Sil')
        mal_sil_btn.clicked.connect(self._malzeme_satirı_sil)
        mal_btn_lyt.addWidget(mal_ekle_btn)
        mal_btn_lyt.addWidget(mal_sil_btn)
        mal_btn_lyt.addStretch()
        malzeme_lyt.addLayout(mal_btn_lyt)
        form_layout.addWidget(malzeme_grup)

        # Notlar
        notlar_grup = QGroupBox('Notlar / Ozel Durumlar')
        notlar_lyt = QVBoxLayout(notlar_grup)
        self.notlar_edit = QPlainTextEdit()
        self.notlar_edit.setFixedHeight(70)
        self.notlar_edit.setPlaceholderText(
            'Isg ihlali, is kazasi, onemli gelismeler...'
        )
        notlar_lyt.addWidget(self.notlar_edit)
        form_layout.addWidget(notlar_grup)

        # Ziyaretciler
        ziy_grup = QGroupBox('Ziyaretciler / Denetciler')
        ziy_lyt = QVBoxLayout(ziy_grup)
        self.ziy_edit = QPlainTextEdit()
        self.ziy_edit.setFixedHeight(60)
        self.ziy_edit.setPlaceholderText('Ad Soyad, Kurum, Ziyaret Amaci...')
        ziy_lyt.addWidget(self.ziy_edit)
        form_layout.addWidget(ziy_grup)

        form_layout.addStretch()
        scroll.setWidget(form_widget)
        sag_layout.addWidget(scroll)

        # Form alt butonlar
        form_alt_lyt = QHBoxLayout()
        self.kaydet_btn = QPushButton('Kaydet')
        self.kaydet_btn.setStyleSheet(
            'QPushButton { background:#27ae60; color:white; font-weight:bold; '
            'padding:6px 18px; border-radius:4px; }'
            'QPushButton:hover { background:#219a52; }'
        )
        self.kaydet_btn.clicked.connect(self._kaydet)

        self.sil_btn = QPushButton('Kaydi Sil')
        self.sil_btn.setStyleSheet(
            'QPushButton { background:#e74c3c; color:white; padding:6px 14px; '
            'border-radius:4px; }'
            'QPushButton:hover { background:#c0392b; }'
        )
        self.sil_btn.clicked.connect(self._sil)
        self.sil_btn.setEnabled(False)

        self.temizle_btn = QPushButton('Temizle')
        self.temizle_btn.clicked.connect(self._yeni_kayit)

        form_alt_lyt.addWidget(self.kaydet_btn)
        form_alt_lyt.addWidget(self.sil_btn)
        form_alt_lyt.addWidget(self.temizle_btn)
        form_alt_lyt.addStretch()

        sag_layout.addLayout(form_alt_lyt)
        splitter.addWidget(sag)
        splitter.setSizes([290, 810])

        ana_layout.addWidget(splitter)

        # Alt buton bari
        alt_lyt = QHBoxLayout()
        pdf_btn = QPushButton('PDF Santiye Defteri Uret')
        pdf_btn.setStyleSheet(
            'QPushButton { background:#2980b9; color:white; font-weight:bold; '
            'padding:6px 16px; border-radius:4px; }'
            'QPushButton:hover { background:#1f6391; }'
        )
        pdf_btn.clicked.connect(self._pdf_uret)

        kapat_btn = QPushButton('Kapat')
        kapat_btn.clicked.connect(self.close)

        alt_lyt.addWidget(pdf_btn)
        alt_lyt.addStretch()
        alt_lyt.addWidget(kapat_btn)
        ana_layout.addLayout(alt_lyt)

    # ── PROJE YONETIMI ───────────────────────────────────────────────────────

    def _proje_combo_doldur(self):
        self.proje_combo.blockSignals(True)
        self.proje_combo.clear()

        if self.db:
            try:
                projeler = self.db.get_all_projects()
                for p in projeler:
                    pid = p.get('id') or p.get('proje_id') or 0
                    padi = p.get('proje_adi') or p.get('isim') or f'Proje {pid}'
                    self.proje_combo.addItem(padi, pid)
                if self.aktif_proje_id:
                    for i in range(self.proje_combo.count()):
                        if self.proje_combo.itemData(i) == self.aktif_proje_id:
                            self.proje_combo.setCurrentIndex(i)
                            break
            except Exception as e:
                logger.warning("Proje listesi alinamadi: %s", e)
                self.proje_combo.addItem('Varsayilan Proje', 1)

        if self.proje_combo.count() == 0:
            self.proje_combo.addItem('Proje 1', 1)

        self.aktif_proje_id = self.proje_combo.currentData() or 1
        self.proje_combo.blockSignals(False)

    def _proje_degisti(self):
        self.aktif_proje_id = self.proje_combo.currentData() or 1
        self._takvim_guncelle()
        self._yeni_kayit()

    # ── TAKVİM ───────────────────────────────────────────────────────────────

    def _takvim_guncelle(self):
        """Kayitli gunleri takvimde yesil olarak isaretler."""
        # Tum ozel formatlari temizle
        self.takvim.setDateTextFormat(QDate(), QTextCharFormat())

        try:
            tarihler = self.engine.kayitli_tarihler(self.aktif_proje_id)
        except Exception:
            tarihler = []

        yesil = QTextCharFormat()
        yesil.setBackground(QBrush(QColor('#27ae60')))
        yesil.setForeground(QBrush(QColor('white')))
        yesil.setFontWeight(QFont.Weight.Bold)

        for t in tarihler:
            qd = QDate(t.year, t.month, t.day)
            self.takvim.setDateTextFormat(qd, yesil)

        self._liste_guncelle()

    def _takvim_tarih_secildi(self):
        qd = self.takvim.selectedDate()
        secilen = date(qd.year(), qd.month(), qd.day())

        # Varsa yukle
        kayit = self.engine.tarih_ile_getir(self.aktif_proje_id, secilen)
        if kayit:
            self._form_doldur(kayit)
        else:
            self._yeni_kayit()
            self.tarih_edit.setDate(qd)

        self._liste_guncelle()

    def _liste_guncelle(self):
        """Mevcut ayin kayitlarini listele."""
        qd = self.takvim.selectedDate()
        try:
            from datetime import date as _date
            bas = _date(qd.year(), qd.month(), 1)
            import calendar
            son_gun = calendar.monthrange(qd.year(), qd.month())[1]
            bit = _date(qd.year(), qd.month(), son_gun)
            kayitlar = self.engine.kayitlari_listele(self.aktif_proje_id, bas, bit)
        except Exception:
            kayitlar = []

        self.kayit_liste.blockSignals(True)
        self.kayit_liste.clear()
        for k in kayitlar:
            metin = (
                k.tarih.strftime('%d.%m.%Y') +
                f' | Isci: {k.toplam_isci} | ' +
                (k.yapilan_isler[:30] + '...' if len(k.yapilan_isler) > 30
                 else k.yapilan_isler)
            )
            item = QListWidgetItem(metin)
            item.setData(Qt.ItemDataRole.UserRole, k.id)
            self.kayit_liste.addItem(item)
        self.kayit_liste.blockSignals(False)

    def _listeden_kayit_sec(self, item: QListWidgetItem):
        kayit_id = item.data(Qt.ItemDataRole.UserRole)
        if kayit_id:
            kayit = self.engine.kayit_getir(kayit_id)
            if kayit:
                self._form_doldur(kayit)

    # ── FORM ─────────────────────────────────────────────────────────────────

    def _form_doldur(self, kayit: SantiyeGunlukKayit):
        """Kayit verilerini forma yukle."""
        self.aktif_kayit_id = kayit.id
        self.sil_btn.setEnabled(True)

        qd = QDate(kayit.tarih.year, kayit.tarih.month, kayit.tarih.day)
        self.tarih_edit.blockSignals(True)
        self.tarih_edit.setDate(qd)
        self.tarih_edit.blockSignals(False)

        self.hava_max_spin.setValue(kayit.hava_max if kayit.hava_max is not None else 20.0)
        self.hava_min_spin.setValue(kayit.hava_min if kayit.hava_min is not None else 10.0)
        idx = self.hava_durum_edit.findText(kayit.hava_durum)
        if idx >= 0:
            self.hava_durum_edit.setCurrentIndex(idx)
        else:
            self.hava_durum_edit.setCurrentText(kayit.hava_durum)
        self.hava_yagis_spin.setValue(kayit.hava_yagis_mm if kayit.hava_yagis_mm is not None else 0.0)

        self.usta_spin.setValue(kayit.usta_sayi)
        self.yardimci_spin.setValue(kayit.yardimci_sayi)
        self.sef_spin.setValue(kayit.sef_sayi)
        self.taseron_spin.setValue(kayit.taseron_sayi)

        self.isler_edit.setPlainText(kayit.yapilan_isler)
        self.notlar_edit.setPlainText(kayit.notlar)
        self.ziy_edit.setPlainText(kayit.ziyaretciler)

        # Malzeme tablosu
        self.malzeme_tablo.setRowCount(0)
        for m in kayit.malzemeler:
            self._malzeme_satiri_ekle_veri(m.ad, m.miktar, m.birim)

    def _form_kayit_al(self) -> SantiyeGunlukKayit:
        """Form alanlarindan SantiyeGunlukKayit nesnesi olustur."""
        qd = self.tarih_edit.date()
        tarih = date(qd.year(), qd.month(), qd.day())

        malzemeler = []
        for row in range(self.malzeme_tablo.rowCount()):
            ad_item = self.malzeme_tablo.item(row, 0)
            mik_item = self.malzeme_tablo.item(row, 1)
            bir_item = self.malzeme_tablo.item(row, 2)
            if ad_item and ad_item.text().strip():
                try:
                    mik = float(mik_item.text()) if mik_item else 0.0
                except ValueError:
                    mik = 0.0
                malzemeler.append(MalzemeKalemi(
                    ad=ad_item.text().strip(),
                    miktar=mik,
                    birim=bir_item.text().strip() if bir_item else '',
                ))

        return SantiyeGunlukKayit(
            id=self.aktif_kayit_id,
            proje_id=self.aktif_proje_id,
            tarih=tarih,
            hava_max=self.hava_max_spin.value(),
            hava_min=self.hava_min_spin.value(),
            hava_durum=self.hava_durum_edit.currentText(),
            hava_yagis_mm=self.hava_yagis_spin.value(),
            usta_sayi=self.usta_spin.value(),
            yardimci_sayi=self.yardimci_spin.value(),
            sef_sayi=self.sef_spin.value(),
            taseron_sayi=self.taseron_spin.value(),
            yapilan_isler=self.isler_edit.toPlainText().strip(),
            malzemeler=malzemeler,
            notlar=self.notlar_edit.toPlainText().strip(),
            ziyaretciler=self.ziy_edit.toPlainText().strip(),
        )

    def _yeni_kayit(self):
        """Formu temizle, yeni kayit moduna al."""
        self.aktif_kayit_id = None
        self.sil_btn.setEnabled(False)
        self.tarih_edit.setDate(QDate.currentDate())
        self.hava_max_spin.setValue(20.0)
        self.hava_min_spin.setValue(10.0)
        self.hava_durum_edit.setCurrentIndex(0)
        self.hava_yagis_spin.setValue(0.0)
        self.usta_spin.setValue(0)
        self.yardimci_spin.setValue(0)
        self.sef_spin.setValue(0)
        self.taseron_spin.setValue(0)
        self.isler_edit.clear()
        self.malzeme_tablo.setRowCount(0)
        self.notlar_edit.clear()
        self.ziy_edit.clear()

    def _tarih_degisti(self):
        """Tarih degisince mevcut kaydi ara, varsa yukle."""
        qd = self.tarih_edit.date()
        tarih = date(qd.year(), qd.month(), qd.day())
        kayit = self.engine.tarih_ile_getir(self.aktif_proje_id, tarih)
        if kayit:
            self._form_doldur(kayit)
        else:
            self.aktif_kayit_id = None
            self.sil_btn.setEnabled(False)

    # ── MALZEME TABLO ────────────────────────────────────────────────────────

    def _malzeme_satirı_ekle(self):
        self._malzeme_satiri_ekle_veri('', 0.0, '')

    def _malzeme_satiri_ekle_veri(self, ad: str, miktar: float, birim: str):
        row = self.malzeme_tablo.rowCount()
        self.malzeme_tablo.insertRow(row)
        self.malzeme_tablo.setItem(row, 0, QTableWidgetItem(ad))
        self.malzeme_tablo.setItem(row, 1, QTableWidgetItem(str(miktar)))
        self.malzeme_tablo.setItem(row, 2, QTableWidgetItem(birim))

    def _malzeme_satirı_sil(self):
        row = self.malzeme_tablo.currentRow()
        if row >= 0:
            self.malzeme_tablo.removeRow(row)

    # ── HAVA OTO-DOLDUR ──────────────────────────────────────────────────────

    def _hava_otodoldur(self):
        """Bugunun havasini arka planda cek."""
        self.hava_otodoldur_btn.setEnabled(False)
        self.hava_otodoldur_btn.setText('Cekiliyor...')

        qd = self.tarih_edit.date()
        hedef = date(qd.year(), qd.month(), qd.day())

        # Proje sehrine gore: db'den varsa cek, yoksa varsayilan
        sehir = self._sehir_bul()

        self._hava_thread = HavaOtoDoldurThread(sehir, hedef)
        self._hava_thread.veri_hazir.connect(self._hava_veri_geldi)
        self._hava_thread.start()

    def _sehir_bul(self) -> str:
        """Projeye bagli sehri bul; bulamazsa varsayilan."""
        if self.db and self.aktif_proje_id:
            try:
                proje = self.db.get_project(self.aktif_proje_id)
                if proje:
                    sehir = (
                        proje.get('sehir') or
                        proje.get('il') or
                        proje.get('konum') or ''
                    )
                    if sehir:
                        return sehir
            except Exception:
                pass
        return self._sehir

    def _hava_veri_geldi(self, hava):
        self.hava_otodoldur_btn.setEnabled(True)
        self.hava_otodoldur_btn.setText('Otomatik Doldur')

        if hava is None:
            QMessageBox.warning(
                self, 'Hava Verisi',
                'Hava durumu alinamadi. Manuel giriniz.'
            )
            return

        self.hava_max_spin.setValue(hava.max_sicaklik)
        self.hava_min_spin.setValue(hava.min_sicaklik)
        self.hava_yagis_spin.setValue(hava.yagis_mm)
        self.hava_durum_edit.setCurrentText(hava.durum_aciklama)
        logger.info("Hava durumu otomatik dolduruldu: %s", hava.durum_aciklama)

    # ── KAYDET / SIL ─────────────────────────────────────────────────────────

    def _kaydet(self):
        kayit = self._form_kayit_al()

        if not kayit.yapilan_isler and kayit.toplam_isci == 0:
            cevap = QMessageBox.question(
                self, 'Bos Kayit',
                'Yapilan isler ve isci sayisi bos. Yine de kaydet?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if cevap != QMessageBox.StandardButton.Yes:
                return

        try:
            if self.aktif_kayit_id:
                self.engine.kayit_guncelle(self.aktif_kayit_id, kayit)
                QMessageBox.information(self, 'Basarili', 'Kayit guncellendi.')
            else:
                # Ayni gun kaydi varsa guncelle
                mevcut = self.engine.tarih_ile_getir(
                    self.aktif_proje_id, kayit.tarih
                )
                if mevcut:
                    self.engine.kayit_guncelle(mevcut.id, kayit)
                    self.aktif_kayit_id = mevcut.id
                    QMessageBox.information(
                        self, 'Basarili',
                        'Bu gun icin kayit zaten vardi; guncellendi.'
                    )
                else:
                    yeni_id = self.engine.kayit_ekle(kayit)
                    self.aktif_kayit_id = yeni_id
                    QMessageBox.information(self, 'Basarili', 'Kayit eklendi.')

            self.sil_btn.setEnabled(True)
            self._takvim_guncelle()
        except Exception as e:
            logger.error("Kayit hatasi: %s", e)
            QMessageBox.critical(self, 'Hata', f'Kayit basarisiz:\n{e}')

    def _sil(self):
        if not self.aktif_kayit_id:
            return
        cevap = QMessageBox.question(
            self, 'Kaydi Sil',
            'Bu gunluk kaydı kalıcı olarak silmek istiyor musunuz?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return

        try:
            self.engine.kayit_sil(self.aktif_kayit_id)
            self._yeni_kayit()
            self._takvim_guncelle()
            QMessageBox.information(self, 'Silindi', 'Kayit silindi.')
        except Exception as e:
            logger.error("Silme hatasi: %s", e)
            QMessageBox.critical(self, 'Hata', f'Silme basarisiz:\n{e}')

    # ── PDF ──────────────────────────────────────────────────────────────────

    def _pdf_uret(self):
        dialog = TarihAralikDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        baslangic, bitis = dialog.tarihler()

        cikti, _ = QFileDialog.getSaveFileName(
            self, 'PDF Kaydet',
            f'santiye_defteri_{baslangic.strftime("%Y%m%d")}_{bitis.strftime("%Y%m%d")}.pdf',
            'PDF Dosyalari (*.pdf)',
        )
        if not cikti:
            return

        proje_adi = self.proje_combo.currentText()
        basarili = self.engine.pdf_uret(
            proje_id=self.aktif_proje_id,
            baslangic=baslangic,
            bitis=bitis,
            cikti_yolu=cikti,
            proje_adi=proje_adi,
            imza_alani=True,
        )

        if basarili:
            QMessageBox.information(
                self, 'PDF Hazir',
                f'Santiye defteri PDF olusturuldu:\n{cikti}'
            )
        else:
            QMessageBox.warning(
                self, 'Uyari',
                'PDF olusturulamadi. Secilen tarih araliginda kayit olmayabilir '
                'veya reportlab kurulu degil.'
            )
