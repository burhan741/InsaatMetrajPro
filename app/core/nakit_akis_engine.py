"""
Nakit Akis Projeksiyonu Motoru
Gantt planlamasindan aylik nakit giris/cikis tahmini

Neyi cozuyoruz?
- Mutteahit icin kritik soru: "Hangi ay ne kadar nakite ihtiyacim var?"
- Gantt is takviminden aylik is yogunlugu cikar
- Hakedis gecikmeli odeme + kesintiler uygular
- Iscilik/malzeme/taseron cikislari vade farkiyla hesaplar

Test:
  engine = NakitAkisEngine(gantt_engine, HakedisKesintEngine())
  engine.sozlesme_bedeli = Decimal("10_000_000")
  akislar = engine.proje_akisi()
"""

from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from app.utils.font_utils import get_fonts as _get_fonts
    _PDF_FONT, _PDF_FONT_BOLD = _get_fonts()
except Exception:
    _PDF_FONT, _PDF_FONT_BOLD = "Helvetica", "Helvetica-Bold"


ROUND2 = lambda v: Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ─── PARAMETRELER ───────────────────────────────────────────────────────────

@dataclass
class NakitAkisParametreleri:
    """Nakit akis hesap parametreleri — kullanici tarafindan girilir."""

    sozlesme_bedeli: Decimal = Decimal('0')
    hakedis_periyodu: str = 'aylik'      # 'aylik' veya '15gun'
    odeme_gecikme_gun: int = 30          # Hakedisin onaydan sonra odenmesi
    kdv_orani: Decimal = Decimal('0.20')

    # Kesintiler
    kesin_teminat_aktif: bool = True
    sgk_kesinti_aktif: bool = True
    gv_stopaj_aktif: bool = True
    avans_orani: Decimal = Decimal('0')  # 0 = avans yok

    # Gider oranlari (sozlesme bedelinin yuzdesi olarak)
    iscilik_oran: Decimal = Decimal('0.30')    # %30 iscilik
    malzeme_oran: Decimal = Decimal('0.45')    # %45 malzeme
    taseron_oran: Decimal = Decimal('0.15')    # %15 taseron

    # Odeme vadeleri (gun)
    iscilik_odeme_gecikme: int = 0     # Ayni ay odenir
    malzeme_odeme_gecikme: int = 30    # 1 ay sonra
    taseron_odeme_gecikme: int = 30    # 1 ay sonra


# ─── AYLIK AKIS ─────────────────────────────────────────────────────────────

@dataclass
class AylikAkis:
    """Tek aylik nakit akis verisi."""
    ay: date                                  # Ayin ilk gunu
    is_yogunlugu_oran: Decimal = Decimal('0') # Toplam iscilik icindeki pay (0-1)
    is_bedeli_brut: Decimal = Decimal('0')    # Hakedisin brut tutari
    hakedis_odeme_tarihi: Optional[date] = None
    net_hakedis_gelir: Decimal = Decimal('0')  # KDV dahil net giris
    iscilik_cikis: Decimal = Decimal('0')
    malzeme_cikis: Decimal = Decimal('0')
    taseron_cikis: Decimal = Decimal('0')
    toplam_cikis: Decimal = Decimal('0')
    aylik_net: Decimal = Decimal('0')
    kumulatif: Decimal = Decimal('0')

    @property
    def ay_str(self) -> str:
        return self.ay.strftime('%B %Y')


# ─── ENGINE ─────────────────────────────────────────────────────────────────

class NakitAkisEngine:
    """
    Nakit akis projeksiyonu.
    GanttEngine'den is takvimini okur, kesintileri HakedisKesintEngine ile hesaplar.
    """

    def __init__(
        self,
        gantt_engine=None,
        parametreler: Optional[NakitAkisParametreleri] = None,
    ):
        self.gantt_engine = gantt_engine
        self.p = parametreler or NakitAkisParametreleri()

    def aylik_is_dagilimi(self) -> Dict[date, Decimal]:
        """
        Gantt'tan her ayin toplam is gununu hesapla (ay ilk gunu → is gun sayisi).
        Task'larda maliyet alani yok; toplam calisma gunu bazinda oranlama yapilir.
        """
        if not self.gantt_engine or not self.gantt_engine.tasks:
            return {}

        ay_gun: Dict[date, int] = {}

        for task in self.gantt_engine.tasks.values():
            bas = task.early_start or task.baslangic_tarihi
            bit = task.early_finish or task.bitis_tarihi
            if not bas or not bit:
                continue

            # Gun gun git, her is gununu ilgili aya ekle
            tarih = bas
            while tarih <= bit:
                if self._is_gunu_mu(tarih):
                    ay_bas = date(tarih.year, tarih.month, 1)
                    ay_gun[ay_bas] = ay_gun.get(ay_bas, 0) + 1
                tarih += timedelta(days=1)

        if not ay_gun:
            return {}

        toplam = sum(ay_gun.values())
        return {
            ay: ROUND2(Decimal(gun) / Decimal(toplam))
            for ay, gun in sorted(ay_gun.items())
        }

    def _is_gunu_mu(self, tarih: date) -> bool:
        """Hafta sonu degil mi? Tatil motoru varsa kullan."""
        if tarih.weekday() >= 5:  # Cumartesi=5, Pazar=6
            return False
        if self.gantt_engine and hasattr(self.gantt_engine, 'tatil_yoneticisi'):
            try:
                if self.gantt_engine.tatil_yoneticisi.tatil_mi(tarih):
                    return False
            except Exception:
                pass
        return True

    def proje_suresi(self) -> Tuple[Optional[date], Optional[date]]:
        """Gantt'tan proje baslangic ve bitis tarihlerini al."""
        if not self.gantt_engine:
            return None, None
        bas = getattr(self.gantt_engine, 'proje_baslangic', None)
        bit = getattr(self.gantt_engine, 'proje_bitis', None)
        # datetime → date donusumu
        if isinstance(bas, datetime):
            bas = bas.date()
        if isinstance(bit, datetime):
            bit = bit.date()
        return bas, bit

    def proje_akisi(self) -> List[AylikAkis]:
        """
        Tam proje nakit akis listesi.
        Sozlesme bedeli yoksa bos liste doner.
        """
        if self.p.sozlesme_bedeli <= 0:
            logger.warning("Sozlesme bedeli girilmemis, hesaplama yapilamaz.")
            return []

        dagitim = self.aylik_is_dagilimi()
        if not dagitim:
            logger.warning("Gantt'ta tarihli task yok, nakit akis hesaplanamaz.")
            return []

        # Hakedis periyoduna gore grupla
        hakedis_donemler = self._hakedis_gruplama(dagitim)

        # Her donem icin brut hakedis hesapla
        donem_hakedis: Dict[date, Decimal] = {}
        birikmis_hakedis = Decimal('0')
        for donem_ay, oran in hakedis_donemler.items():
            brut = ROUND2(self.p.sozlesme_bedeli * oran)
            donem_hakedis[donem_ay] = brut
            birikmis_hakedis += brut

        # Aylik gider dagilimi (sozlesme bedelinin yuzde dagitimi × oran)
        toplam_gider_oran = self.p.iscilik_oran + self.p.malzeme_oran + self.p.taseron_oran

        # Tum aylarin listesi
        aylar = sorted(dagitim.keys())
        akislar: List[AylikAkis] = []

        # Kumulatif kesinti takibi (kesin teminat limiti)
        kesin_teminat_toplam = Decimal('0')
        kesin_teminat_limit = ROUND2(self.p.sozlesme_bedeli * Decimal('0.06'))

        birikmis_kumulatif = Decimal('0')

        for ay in aylar:
            oran = dagitim.get(ay, Decimal('0'))
            akis = AylikAkis(ay=ay, is_yogunlugu_oran=oran)
            akis.is_bedeli_brut = ROUND2(self.p.sozlesme_bedeli * oran)

            # ── Gelir: hakedis bu ayda mi?
            if ay in donem_hakedis:
                brut_hakedis = donem_hakedis[ay]
                # Odeme tarihi
                ay_sonu = date(ay.year, ay.month, calendar.monthrange(ay.year, ay.month)[1])
                akis.hakedis_odeme_tarihi = ay_sonu + timedelta(days=self.p.odeme_gecikme_gun)

                # Kesintiler
                kesin_tam = kesin_teminat_toplam >= kesin_teminat_limit
                net_hakedis = self._net_hakedis_hesapla(
                    brut_hakedis,
                    kesin_tam,
                    birikmis_kumulatif,
                )
                if not kesin_tam:
                    kt_kesinti = ROUND2(brut_hakedis * Decimal('0.06'))
                    kesin_teminat_toplam = min(
                        kesin_teminat_toplam + kt_kesinti,
                        kesin_teminat_limit,
                    )
                # KDV dahil gelir
                akis.net_hakedis_gelir = ROUND2(net_hakedis * (1 + self.p.kdv_orani))
            else:
                akis.net_hakedis_gelir = Decimal('0')

            # ── Giderler (vade farkiyla ileriki aya kaydirma sonraki adimda yapilir)
            akis.iscilik_cikis = ROUND2(akis.is_bedeli_brut * self.p.iscilik_oran / toplam_gider_oran * toplam_gider_oran)
            akis.malzeme_cikis = Decimal('0')   # Vade sonrasi ayin maliyeti
            akis.taseron_cikis = Decimal('0')

            akislar.append(akis)

        # ── Malzeme ve taseron vade kaydir
        for i, akis in enumerate(akislar):
            brut = akis.is_bedeli_brut
            # Iscilik: ayni ay
            akis.iscilik_cikis = ROUND2(brut * self.p.iscilik_oran)
            # Malzeme: N gun sonra → hangi ayda?
            akis.malzeme_cikis = self._vade_ekle(
                akislar, i, ROUND2(brut * self.p.malzeme_oran),
                self.p.malzeme_odeme_gecikme, 'malzeme_cikis'
            )
            # Taseron: N gun sonra
            akis.taseron_cikis = self._vade_ekle(
                akislar, i, ROUND2(brut * self.p.taseron_oran),
                self.p.taseron_odeme_gecikme, 'taseron_cikis'
            )

        # ── Toplam + kumulatif
        kumulatif = Decimal('0')
        for akis in akislar:
            akis.toplam_cikis = ROUND2(
                akis.iscilik_cikis + akis.malzeme_cikis + akis.taseron_cikis
            )
            akis.aylik_net = ROUND2(akis.net_hakedis_gelir - akis.toplam_cikis)
            kumulatif += akis.aylik_net
            akis.kumulatif = kumulatif

        return akislar

    def _hakedis_gruplama(self, dagitim: Dict[date, Decimal]) -> Dict[date, Decimal]:
        """
        Hakedis periyoduna gore aylari grupla.
        'aylik': her ay ayri donem.
        '15gun': ayda iki donem (ay baslangiclari).
        Su an 'aylik' yeterli; '15gun' genisleme icin yer birakildi.
        """
        return dict(dagitim)

    def _net_hakedis_hesapla(
        self,
        brut: Decimal,
        kesin_tam: bool,
        birikmis: Decimal,
    ) -> Decimal:
        """Kesintileri uygulayarak net hakodis hesapla."""
        net = brut
        # Kesin teminat %6
        if self.p.kesin_teminat_aktif and not kesin_tam:
            net -= ROUND2(brut * Decimal('0.06'))
        # Damga Vergisi %0.948
        net -= ROUND2(brut * Decimal('0.00948'))
        # GV Stopaj %3
        if self.p.gv_stopaj_aktif:
            net -= ROUND2(brut * Decimal('0.03'))
        # SGK Prim %1
        if self.p.sgk_kesinti_aktif:
            net -= ROUND2(brut * Decimal('0.01'))
        return max(net, Decimal('0'))

    def _vade_ekle(
        self,
        akislar: List[AylikAkis],
        kaynak_idx: int,
        tutar: Decimal,
        gecikme_gun: int,
        alan: str,
    ) -> Decimal:
        """
        Vade uygulanarak tutari dogru aya ekle.
        Gecikme 0 ise ayni aya yaz ve dondur.
        Baska aya geciyorsa o ayin alanina ekle, bu ay 0 dondur.
        """
        if gecikme_gun == 0:
            return tutar

        kaynak_ay = akislar[kaynak_idx].ay
        hedef_tarih = date(
            kaynak_ay.year, kaynak_ay.month,
            calendar.monthrange(kaynak_ay.year, kaynak_ay.month)[1]
        ) + timedelta(days=gecikme_gun)
        hedef_ay = date(hedef_tarih.year, hedef_tarih.month, 1)

        for akis in akislar:
            if akis.ay == hedef_ay:
                setattr(akis, alan, getattr(akis, alan) + tutar)
                return Decimal('0')

        # Hedef ay proje disindaysa son aya ekle
        if akislar:
            son = akislar[-1]
            setattr(son, alan, getattr(son, alan) + tutar)
        return Decimal('0')

    def kritik_aciklar(self, akislar: List[AylikAkis]) -> List[Tuple[date, Decimal, str]]:
        """
        Kumulatif nakit pozisyonunun negatife dustugu aylari dondur.
        [(ay, acik_tutar, aciklama), ...]
        """
        sonuc = []
        for akis in akislar:
            if akis.kumulatif < 0:
                sonuc.append((
                    akis.ay,
                    abs(akis.kumulatif),
                    f'{akis.ay_str}: {float(abs(akis.kumulatif)):,.0f} TL nakit acigi'
                ))
        return sonuc

    def ozet_istatistik(self, akislar: List[AylikAkis]) -> Dict:
        """Ozet rakamlar."""
        if not akislar:
            return {}
        toplam_gelir = sum(a.net_hakedis_gelir for a in akislar)
        toplam_gider = sum(a.toplam_cikis for a in akislar)
        max_acik_ay = min(akislar, key=lambda a: a.kumulatif)
        return {
            'toplam_gelir': toplam_gelir,
            'toplam_gider': toplam_gider,
            'net_pozisyon': toplam_gelir - toplam_gider,
            'max_kumulatif': max(a.kumulatif for a in akislar),
            'min_kumulatif': min(a.kumulatif for a in akislar),
            'kritik_ay_sayisi': len(self.kritik_aciklar(akislar)),
            'proje_ay_sayisi': len(akislar),
        }

    def excel_export(self, akislar: List[AylikAkis], cikti_yolu: str) -> bool:
        """Akis tablosunu Excel/CSV olarak kaydet."""
        try:
            import csv
            satirlar = [
                ['Ay', 'Is Bedeli (Brut)', 'Net Hakedis Gelir',
                 'Iscilik Cikis', 'Malzeme Cikis', 'Taseron Cikis',
                 'Toplam Cikis', 'Aylik Net', 'Kumulatif Pozisyon']
            ]
            for a in akislar:
                satirlar.append([
                    a.ay_str,
                    float(a.is_bedeli_brut),
                    float(a.net_hakedis_gelir),
                    float(a.iscilik_cikis),
                    float(a.malzeme_cikis),
                    float(a.taseron_cikis),
                    float(a.toplam_cikis),
                    float(a.aylik_net),
                    float(a.kumulatif),
                ])
            with open(cikti_yolu, 'w', newline='', encoding='utf-8-sig') as f:
                csv.writer(f).writerows(satirlar)
            return True
        except Exception as e:
            logger.error("Excel export hatasi: %s", e)
            return False

    def pdf_export(self, akislar: List[AylikAkis], cikti_yolu: str, proje_adi: str = '') -> bool:
        """Nakit akis tablosunu PDF olarak kaydet."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, HRFlowable,
            )
        except ImportError:
            logger.error("pdf_export: reportlab kurulu degil.")
            return False

        if not akislar:
            return False

        try:
            doc = SimpleDocTemplate(
                str(cikti_yolu),
                pagesize=landscape(A4),
                leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                topMargin=1.5 * cm, bottomMargin=1.5 * cm,
            )
            genislik = landscape(A4)[0] - 3.0 * cm

            stiller = getSampleStyleSheet()
            s_baslik = ParagraphStyle(
                'Baslik', parent=stiller['Heading1'],
                fontSize=12, leading=16, alignment=1, spaceAfter=4,
            )
            s_normal = ParagraphStyle(
                'Normal2', parent=stiller['Normal'],
                fontSize=7, leading=9,
            )
            s_bold = ParagraphStyle(
                'Bold2', parent=stiller['Normal'],
                fontSize=7, leading=9, fontName=_PDF_FONT_BOLD,
            )

            hikaye = []
            tarih_str = datetime.now().strftime('%d.%m.%Y')
            hikaye.append(Paragraph('NAKIT AKIS PROJEKSIYONU', s_baslik))
            hikaye.append(Paragraph(
                f'Proje: {proje_adi}  |  Sozlesme Bedeli: {float(self.p.sozlesme_bedeli):,.0f} TL  |  '
                f'Uretim Tarihi: {tarih_str}', s_normal
            ))
            hikaye.append(HRFlowable(width='100%', thickness=1, color=colors.black))
            hikaye.append(Spacer(1, 0.3 * cm))

            # Tablo
            sutun_gen = genislik / 9
            header = [
                Paragraph('<b>Ay</b>', s_bold),
                Paragraph('<b>Is Bedeli</b>', s_bold),
                Paragraph('<b>Net Hakedis</b>', s_bold),
                Paragraph('<b>Iscilik Cikis</b>', s_bold),
                Paragraph('<b>Malzeme Cikis</b>', s_bold),
                Paragraph('<b>Taseron Cikis</b>', s_bold),
                Paragraph('<b>Toplam Cikis</b>', s_bold),
                Paragraph('<b>Aylik Net</b>', s_bold),
                Paragraph('<b>Kumulatif</b>', s_bold),
            ]
            data = [header]
            for a in akislar:
                renk = '#FFCCCC' if a.kumulatif < 0 else '#FFFFFF'
                satir = [
                    Paragraph(a.ay_str, s_normal),
                    Paragraph(f'{float(a.is_bedeli_brut):,.0f}', s_normal),
                    Paragraph(f'{float(a.net_hakedis_gelir):,.0f}', s_normal),
                    Paragraph(f'{float(a.iscilik_cikis):,.0f}', s_normal),
                    Paragraph(f'{float(a.malzeme_cikis):,.0f}', s_normal),
                    Paragraph(f'{float(a.taseron_cikis):,.0f}', s_normal),
                    Paragraph(f'{float(a.toplam_cikis):,.0f}', s_normal),
                    Paragraph(f'{float(a.aylik_net):,.0f}', s_normal),
                    Paragraph(f'{float(a.kumulatif):,.0f}', s_normal),
                ]
                data.append(satir)

            tablo = Table(data, colWidths=[sutun_gen] * 9)
            ts = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
            ])
            for i, a in enumerate(akislar, 1):
                if a.kumulatif < 0:
                    ts.add('BACKGROUND', (8, i), (8, i), colors.HexColor('#FFCCCC'))
            tablo.setStyle(ts)
            hikaye.append(tablo)

            doc.build(hikaye)
            logger.info("Nakit akis PDF uretildi: %s", cikti_yolu)
            return True
        except Exception as e:
            logger.error("PDF uretim hatasi: %s", e)
            return False
