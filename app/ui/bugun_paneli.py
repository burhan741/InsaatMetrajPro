"""
Bugün Paneli — "Bugün Ne Yapmalıyım?"
Trafik ışığı bazlı günlük iş özeti ve hava durumu entegrasyonu

Özellikler:
- Aktif görevler: erken_başlangıç <= bugün <= erken_bitiş ve ilerleme < 100
- DİKKAT: float <= 3 gün veya hava uyarısı
- KRİTİK: kritik yolda + gecikmiş veya hava kritik uyarısı
- 7 günlük hava durumu tablosu (Open-Meteo)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QGroupBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QBrush
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# ─── RENKLER ────────────────────────────────────────────────────────────────
RENK_YAPILACAK = "#27ae60"    # Yeşil
RENK_DIKKAT    = "#f39c12"    # Turuncu
RENK_KRITIK    = "#e74c3c"    # Kırmızı
RENK_PANEL_BG  = "#f8f9fa"
RENK_BASLIK_BG = "#2c3e50"

# ─── HAVA ÇEKME THREAD ──────────────────────────────────────────────────────

class HavaThread(QThread):
    """Hava durumunu arka planda çek, UI donmasın"""
    veri_hazir = pyqtSignal(object, object)   # (tahminler, uyarilar) veya (None, None)
    hata = pyqtSignal(str)

    def __init__(self, sehir_adi: str):
        super().__init__()
        self.sehir_adi = sehir_adi

    def run(self):
        try:
            from app.core.hava_durumu import HavaDurumuServisi
            servis = HavaDurumuServisi()
            konum = servis.sehir_ara(self.sehir_adi)
            if not konum:
                self.hata.emit(f"'{self.sehir_adi}' şehri bulunamadı.")
                self.veri_hazir.emit(None, None)
                return
            tahminler = servis.tahmin_al(konum['lat'], konum['lon'])
            uyarilar = servis.insaat_uyarilari_al(tahminler)
            self.veri_hazir.emit(tahminler, uyarilar)
        except Exception as e:
            self.hata.emit(str(e))
            self.veri_hazir.emit(None, None)


# ─── GÖREV SATIRI WIDGET ────────────────────────────────────────────────────

class GorevSatiri(QFrame):
    """Tek görev satırı — renkli chip ile"""

    def __init__(self, gorev_bilgi: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                margin: 2px 4px;
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Renk chip (durum göstergesi)
        seviye = gorev_bilgi.get('seviye', 'YAPILACAK')
        chip_renk = {
            'YAPILACAK': RENK_YAPILACAK,
            'DİKKAT':    RENK_DIKKAT,
            'KRİTİK':    RENK_KRITIK,
        }.get(seviye, RENK_YAPILACAK)

        chip = QLabel(seviye)
        chip.setFixedWidth(72)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setStyleSheet(f"""
            QLabel {{
                background-color: {chip_renk};
                color: white;
                border-radius: 4px;
                padding: 2px 4px;
                font-size: 9pt;
                font-weight: bold;
            }}
        """)
        layout.addWidget(chip)

        # İş adı
        ad_label = QLabel(gorev_bilgi.get('ad', ''))
        ad_label.setFont(QFont("Segoe UI", 10))
        ad_label.setWordWrap(True)
        layout.addWidget(ad_label, stretch=2)

        # Kaynak
        kaynak = gorev_bilgi.get('kaynak', '')
        if kaynak:
            kaynak_label = QLabel(f"👷 {kaynak}")
            kaynak_label.setStyleSheet("color: #6c757d; font-size: 9pt;")
            kaynak_label.setMaximumWidth(140)
            layout.addWidget(kaynak_label)

        # Süre
        sure = gorev_bilgi.get('sure_gun', 0)
        bitis = gorev_bilgi.get('bitis_str', '')
        sure_label = QLabel(f"⏱ {sure} gün\n📅 {bitis}")
        sure_label.setStyleSheet("color: #495057; font-size: 9pt;")
        sure_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(sure_label)

        # İlerleme
        ilerleme = gorev_bilgi.get('ilerleme', 0)
        ilerleme_label = QLabel(f"%{ilerleme:.0f}")
        ilerleme_label.setStyleSheet(f"color: {chip_renk}; font-weight: bold; font-size: 10pt;")
        ilerleme_label.setFixedWidth(40)
        ilerleme_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(ilerleme_label)

        self.setLayout(layout)


# ─── BUGÜN PANELİ ANA WIDGET ────────────────────────────────────────────────

class BugunPaneli(QWidget):
    """
    "Bugün Ne Yapmalıyım?" Paneli

    Neyi çözüyoruz?
    - Müteahhit/şantiye şefi her sabah 30 saniyede günlük iş planını görsün.
    - Hava uyarıları ve kritik iş gecikmeleri öne çıkartılsın.

    Test:
    - panel = BugunPaneli()
    - panel.guncelle(engine)   # GanttEngine geçilir
    - panel.show()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._engine = None
        self._hava_thread: Optional[HavaThread] = None
        self._tahminler = None
        self._hava_uyarilari: List[Dict] = []
        self._init_ui()

    # ── UI KURULUMU ──────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Başlık çubuğu ─────────────────────────────────────
        baslik_frame = QFrame()
        baslik_frame.setStyleSheet(f"background-color: {RENK_BASLIK_BG}; border-radius: 8px;")
        baslik_layout = QHBoxLayout(baslik_frame)
        baslik_layout.setContentsMargins(12, 8, 12, 8)

        bugun_str = datetime.now().strftime("📅  %d %B %Y, %A")
        self._baslik_label = QLabel(bugun_str)
        self._baslik_label.setStyleSheet("color: white; font-size: 13pt; font-weight: bold;")
        baslik_layout.addWidget(self._baslik_label)
        baslik_layout.addStretch()

        self._yenile_btn = QPushButton("🔄 Yenile")
        self._yenile_btn.setStyleSheet(
            "background-color: #3498db; color: white; "
            "border-radius: 4px; padding: 4px 10px; font-size: 9pt;"
        )
        self._yenile_btn.clicked.connect(self._yenile)
        baslik_layout.addWidget(self._yenile_btn)

        layout.addWidget(baslik_frame)

        # ── İstatistik satırı ─────────────────────────────────
        self._istat_frame = self._istat_satiri_olustur(0, 0, 0)
        layout.addWidget(self._istat_frame)

        # ── Görevler scroll alanı ─────────────────────────────
        gorev_group = QGroupBox("📋 Aktif Görevler")
        gorev_group.setStyleSheet("""
            QGroupBox {
                font-size: 11pt;
                font-weight: bold;
                color: #2c3e50;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        gorev_v = QVBoxLayout(gorev_group)

        self._gorev_scroll = QScrollArea()
        self._gorev_scroll.setWidgetResizable(True)
        self._gorev_scroll.setMinimumHeight(180)
        self._gorev_scroll.setMaximumHeight(280)
        self._gorev_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._gorev_container = QWidget()
        self._gorev_layout = QVBoxLayout(self._gorev_container)
        self._gorev_layout.setContentsMargins(0, 0, 0, 0)
        self._gorev_layout.setSpacing(2)
        self._gorev_layout.addStretch()
        self._gorev_scroll.setWidget(self._gorev_container)
        gorev_v.addWidget(self._gorev_scroll)
        layout.addWidget(gorev_group)

        # ── Hava durumu grubu ─────────────────────────────────
        hava_group = QGroupBox("🌤 Hava Durumu (7 Gün) — İnşaat Koşulları")
        hava_group.setStyleSheet(gorev_group.styleSheet())
        hava_v = QVBoxLayout(hava_group)
        hava_v.setSpacing(4)

        # Şehir giriş satırı
        sehir_layout = QHBoxLayout()
        sehir_layout.setSpacing(6)
        sehir_label = QLabel("Şehir:")
        sehir_label.setStyleSheet("font-weight: bold;")
        self._sehir_input = QLineEdit()
        self._sehir_input.setPlaceholderText("Örn: Ankara, İstanbul, İzmir...")
        self._sehir_input.setMaximumWidth(240)
        self._sehir_input.returnPressed.connect(self._hava_al)

        self._hava_btn = QPushButton("🌐 Hava Durumunu Al")
        self._hava_btn.setStyleSheet(
            "background-color: #3498db; color: white; "
            "border-radius: 4px; padding: 4px 10px;"
        )
        self._hava_btn.clicked.connect(self._hava_al)

        self._hava_durum_label = QLabel("")
        self._hava_durum_label.setStyleSheet("color: #6c757d; font-size: 9pt;")

        sehir_layout.addWidget(sehir_label)
        sehir_layout.addWidget(self._sehir_input)
        sehir_layout.addWidget(self._hava_btn)
        sehir_layout.addWidget(self._hava_durum_label)
        sehir_layout.addStretch()
        hava_v.addLayout(sehir_layout)

        # Hava durumu tablosu
        self._hava_tablo = QTableWidget()
        self._hava_tablo.setColumnCount(6)
        self._hava_tablo.setHorizontalHeaderLabels([
            "Tarih", "Max °C", "Min °C", "Yağış mm", "Rüzgar km/s", "İnşaat Durumu"
        ])
        self._hava_tablo.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._hava_tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._hava_tablo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hava_tablo.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._hava_tablo.setAlternatingRowColors(True)
        self._hava_tablo.setMaximumHeight(230)
        self._hava_tablo.setMinimumHeight(160)
        hava_v.addWidget(self._hava_tablo)

        layout.addWidget(hava_group)
        layout.addStretch()
        self.setLayout(layout)

        # Tarih güncelleme timer (her dakika)
        timer = QTimer(self)
        timer.timeout.connect(self._tarih_guncelle)
        timer.start(60000)

    def _istat_satiri_olustur(self, yapilacak: int, dikkat: int, kritik: int) -> QFrame:
        """İstatistik özet çubuğu"""
        frame = QFrame()
        frame.setStyleSheet(f"background-color: {RENK_PANEL_BG}; border-radius: 6px;")
        hlayout = QHBoxLayout(frame)
        hlayout.setContentsMargins(12, 8, 12, 8)

        for renk, ikon, etiket, sayi in [
            (RENK_YAPILACAK, "✅", "YAPILACAK",  yapilacak),
            (RENK_DIKKAT,    "⚠️", "DİKKAT",     dikkat),
            (RENK_KRITIK,    "🔴", "KRİTİK",     kritik),
        ]:
            kutu = QFrame()
            kutu.setStyleSheet(f"""
                QFrame {{
                    background-color: {renk}22;
                    border: 2px solid {renk};
                    border-radius: 8px;
                    padding: 4px;
                }}
            """)
            kutu_layout = QVBoxLayout(kutu)
            kutu_layout.setContentsMargins(12, 6, 12, 6)
            kutu_layout.setSpacing(2)

            sayi_label = QLabel(str(sayi))
            sayi_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sayi_label.setStyleSheet(f"color: {renk}; font-size: 22pt; font-weight: bold; background: transparent;")

            etiket_label = QLabel(f"{ikon} {etiket}")
            etiket_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            etiket_label.setStyleSheet(f"color: {renk}; font-size: 9pt; font-weight: bold; background: transparent;")

            kutu_layout.addWidget(sayi_label)
            kutu_layout.addWidget(etiket_label)
            hlayout.addWidget(kutu, stretch=1)

        return frame

    # ── VERİ GÜNCELLEME ──────────────────────────────────────────

    def guncelle(self, engine) -> None:
        """
        GanttEngine'den bugünkü görevleri çek ve paneli güncelle.

        Args:
            engine: GanttEngine instance (tasks dict'i okunur)
        """
        self._engine = engine
        self._gorev_listesi_doldur(engine)

    def _gorev_listesi_doldur(self, engine) -> None:
        """Engine task'larından bugünkü görev listesini oluştur"""
        bugun = date.today()

        yapilacaklar: List[Dict] = []
        dikkat_listesi: List[Dict] = []
        kritikler: List[Dict] = []

        if not engine or not engine.tasks:
            self._gorev_paneli_goster([], [], [])
            self._istat_guncelle(0, 0, 0)
            return

        for task in engine.tasks.values():
            # Tamamlanmış görevleri atla
            if task.ilerleme >= 100:
                continue

            # Tarih bilgisi varsa
            es = task.early_start
            ef = task.early_finish
            es_date = es.date() if es else None
            ef_date = ef.date() if ef else None

            # Bugün aktif mi?
            aktif = False
            if es_date and ef_date:
                aktif = (es_date <= bugun <= ef_date)
            elif es_date:
                aktif = (es_date <= bugun)

            if not aktif:
                continue

            bitis_str = ef.strftime('%d.%m.%Y') if ef else '?'
            bilgi = {
                'ad': task.ad,
                'kaynak': task.kaynak or '',
                'sure_gun': task.sure_gun,
                'ilerleme': task.ilerleme,
                'bitis_str': bitis_str,
                'float_gun': task.float_gun,
                'kritik': task.kritik,
                'gecikmis': (task.get_durum() == 'gecikmis'),
            }

            # Sınıflandırma
            if (task.kritik and bilgi['gecikmis']) or \
               any(u['seviye'] == 'KRİTİK' for u in self._hava_uyarilari):
                bilgi['seviye'] = 'KRİTİK'
                kritikler.append(bilgi)
            elif task.float_gun <= 3 or \
                 any(u['seviye'] == 'UYARI' for u in self._hava_uyarilari):
                bilgi['seviye'] = 'DİKKAT'
                dikkat_listesi.append(bilgi)
            else:
                bilgi['seviye'] = 'YAPILACAK'
                yapilacaklar.append(bilgi)

        self._gorev_paneli_goster(yapilacaklar, dikkat_listesi, kritikler)
        self._istat_guncelle(len(yapilacaklar), len(dikkat_listesi), len(kritikler))

    def _gorev_paneli_goster(
        self,
        yapilacaklar: List[Dict],
        dikkat: List[Dict],
        kritikler: List[Dict]
    ) -> None:
        """Görev scroll alanını temizleyip yeniden doldur"""
        # Mevcut widget'ları temizle
        while self._gorev_layout.count() > 1:
            item = self._gorev_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        toplam = len(yapilacaklar) + len(dikkat) + len(kritikler)
        if toplam == 0:
            bos_label = QLabel("✅  Bugün için aktif iş kalemi bulunamadı.\nİş programını hesapladıktan sonra görevler burada görünür.")
            bos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bos_label.setStyleSheet("color: #6c757d; font-size: 10pt; padding: 20px;")
            self._gorev_layout.insertWidget(0, bos_label)
            return

        # Kritikler önce
        for bilgi in kritikler:
            satir = GorevSatiri(bilgi)
            self._gorev_layout.insertWidget(0, satir)

        # Dikkat
        ins = len(kritikler)
        for bilgi in dikkat:
            satir = GorevSatiri(bilgi)
            self._gorev_layout.insertWidget(ins, satir)
            ins += 1

        # Yapılacaklar
        for bilgi in yapilacaklar:
            satir = GorevSatiri(bilgi)
            self._gorev_layout.insertWidget(ins, satir)
            ins += 1

    def _istat_guncelle(self, yapilacak: int, dikkat: int, kritik: int) -> None:
        """İstatistik çubuğunu güncelle"""
        yeni = self._istat_satiri_olustur(yapilacak, dikkat, kritik)
        layout = self.layout()
        # Mevcut istatistik frame'ini değiştir (index 1)
        eski = layout.itemAt(1)
        if eski and eski.widget():
            layout.replaceWidget(eski.widget(), yeni)
            eski.widget().deleteLater()
        self._istat_frame = yeni

    # ── HAVA DURUMU ──────────────────────────────────────────────

    def _hava_al(self) -> None:
        """Şehir adına göre hava durumu çek"""
        sehir = self._sehir_input.text().strip()
        if not sehir:
            return

        # Önceki thread varsa iptal et
        if self._hava_thread and self._hava_thread.isRunning():
            self._hava_thread.quit()

        self._hava_btn.setEnabled(False)
        self._hava_btn.setText("⏳ Alınıyor...")
        self._hava_durum_label.setText("")

        self._hava_thread = HavaThread(sehir)
        self._hava_thread.veri_hazir.connect(self._hava_veri_geldi)
        self._hava_thread.hata.connect(self._hava_hata)
        self._hava_thread.start()

    def _hava_veri_geldi(self, tahminler, uyarilar) -> None:
        """Hava verisi hazır — tabloyu doldur"""
        self._hava_btn.setEnabled(True)
        self._hava_btn.setText("🌐 Hava Durumunu Al")
        self._tahminler = tahminler
        self._hava_uyarilari = uyarilar or []

        if not tahminler:
            self._hava_durum_label.setText("❌ Veri alınamadı")
            self._hava_durum_label.setStyleSheet("color: #e74c3c;")
            return

        self._hava_tabloyu_doldur(tahminler)
        kritik_say = sum(1 for u in self._hava_uyarilari if u.get('seviye') == 'KRİTİK')
        uyari_say = sum(1 for u in self._hava_uyarilari if u.get('seviye') == 'UYARI')

        if kritik_say:
            self._hava_durum_label.setText(f"🔴 {kritik_say} kritik, {uyari_say} uyarı var!")
            self._hava_durum_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        elif uyari_say:
            self._hava_durum_label.setText(f"⚠️ {uyari_say} uyarı var")
            self._hava_durum_label.setStyleSheet("color: #f39c12; font-weight: bold;")
        else:
            self._hava_durum_label.setText("✅ İnşaat koşulları uygun")
            self._hava_durum_label.setStyleSheet("color: #27ae60; font-weight: bold;")

        # Görev listesini hava uyarısı bilgisiyle de yenile
        if self._engine:
            self._gorev_listesi_doldur(self._engine)

    def _hava_hata(self, mesaj: str) -> None:
        self._hava_btn.setEnabled(True)
        self._hava_btn.setText("🌐 Hava Durumunu Al")
        self._hava_durum_label.setText(f"❌ {mesaj}")
        self._hava_durum_label.setStyleSheet("color: #e74c3c;")

    def _hava_tabloyu_doldur(self, tahminler) -> None:
        """7 günlük hava tablosunu doldur"""
        self._hava_tablo.setRowCount(0)

        for hava in tahminler:
            row = self._hava_tablo.rowCount()
            self._hava_tablo.insertRow(row)

            tarih_str = hava.tarih.strftime('%d.%m %a')
            self._hava_tablo.setItem(row, 0, QTableWidgetItem(tarih_str))
            self._hava_tablo.setItem(row, 1, QTableWidgetItem(f"{hava.max_sicaklik:.1f}"))
            self._hava_tablo.setItem(row, 2, QTableWidgetItem(f"{hava.min_sicaklik:.1f}"))
            self._hava_tablo.setItem(row, 3, QTableWidgetItem(f"{hava.yagis_mm:.1f}"))
            self._hava_tablo.setItem(row, 4, QTableWidgetItem(f"{hava.ruzgar_kmh:.0f}"))

            # İnşaat durumu hücresi
            uyarilar_bugun = [
                u for u in self._hava_uyarilari
                if u.get('tarih_dt') == hava.tarih
            ]
            if uyarilar_bugun:
                kritik_var = any(u['seviye'] == 'KRİTİK' for u in uyarilar_bugun)
                ozet = " | ".join(u['mesaj'][:40] for u in uyarilar_bugun[:2])
                durum_item = QTableWidgetItem(ozet)
                bg = QColor("#ffe0e0") if kritik_var else QColor("#fff3cd")
                fg = QColor("#c0392b") if kritik_var else QColor("#856404")
                durum_item.setBackground(QBrush(bg))
                durum_item.setForeground(QBrush(fg))
                durum_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            else:
                durum_item = QTableWidgetItem("✅ Uygun")
                durum_item.setForeground(QBrush(QColor("#27ae60")))

            self._hava_tablo.setItem(row, 5, durum_item)

            # Bugünü vurgula
            if hava.tarih == date.today():
                for col in range(6):
                    item = self._hava_tablo.item(row, col)
                    if item:
                        item.setBackground(QBrush(QColor("#e8f4f8")))
                        item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))

    def _tarih_guncelle(self) -> None:
        bugun_str = datetime.now().strftime("📅  %d %B %Y, %A")
        self._baslik_label.setText(bugun_str)

    def _yenile(self) -> None:
        """Manuel yenile"""
        if self._engine:
            self._gorev_listesi_doldur(self._engine)
        self._tarih_guncelle()

    def set_sehir(self, sehir: str) -> None:
        """Dışarıdan şehir adı ayarla ve hava çek"""
        if sehir:
            self._sehir_input.setText(sehir)
            self._hava_al()
