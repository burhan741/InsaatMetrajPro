"""
Ince Isler Hizli Hesap Motoru
Duvar/siva/alci/astar/boya malzeme miktari + iscilik maliyet hesabi, CSV export

CŞB normlari (malzeme):
  1 m² ic siva  -> 15 kg kum + 3 kg cimento
  1 m² alci     -> 5 kg alci tozu (1 torba 25 kg = 5 m²)
  1 m² astar    -> 0.15 lt
  1 m² ic boya  -> 0.25 lt (2 kat)

CŞB normlari (iscilik verimlilik):
  Ic siva: 25 m²/gun | Dis siva: 20 | Alci: 20 | Astar: 40
  Ic boya: 45 m²/gun | Dis boya: 30

Test:
  engine = InceIslerHizliEngine()
  kalemler = engine.hesapla_kombo(20.0, ['ic_siva', 'alci', 'ic_boya'])
  iscilik = engine.hesapla_iscilik(['ic_siva', 'alci', 'ic_boya'], 20.0, Decimal('1800'))
  for k in kalemler: print(k)
  for i in iscilik: print(i)
"""

from __future__ import annotations

import csv
import logging
import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from app.utils.font_utils import get_fonts as _get_fonts
    _PDF_FONT, _PDF_FONT_BOLD = _get_fonts()
except Exception:
    _PDF_FONT, _PDF_FONT_BOLD = "Helvetica", "Helvetica-Bold"


R2 = lambda v: Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# ─── CŞB MALZEME KATSAYILARI ─────────────────────────────────────────────────
# kaynak: CŞB birim fiyat analizleri

KATSAYILAR: Dict[str, List[dict]] = {
    'ic_siva': [
        {'ad': 'Kum (ince)',     'katsayi': 15.0, 'birim': 'kg', 'anahtar': ['kum', 'ince agrega', 'kum ince']},
        {'ad': 'Cimento',        'katsayi': 3.0,  'birim': 'kg', 'anahtar': ['cimento', 'cement', 'portland']},
    ],
    'alci': [
        {'ad': 'Alci Tozu',      'katsayi': 5.0,  'birim': 'kg', 'anahtar': ['alci', 'alcı', 'alci tozu'],
         'torba_kg': 25.0},
    ],
    'astar': [
        {'ad': 'Astar (ic)',     'katsayi': 0.15, 'birim': 'lt', 'anahtar': ['astar', 'ic astar', 'primer']},
    ],
    'ic_boya': [
        {'ad': 'Ic Cephe Boya',  'katsayi': 0.25, 'birim': 'lt', 'anahtar': ['ic boya', 'iç boya', 'lateks', 'boya ic']},
    ],
    'dis_siva': [
        {'ad': 'Kum (iri)',      'katsayi': 18.0, 'birim': 'kg', 'anahtar': ['kum', 'kum iri', 'agrega iri']},
        {'ad': 'Cimento',        'katsayi': 4.0,  'birim': 'kg', 'anahtar': ['cimento', 'cement']},
    ],
    'dis_boya': [
        {'ad': 'Dis Cephe Boya', 'katsayi': 0.35, 'birim': 'lt', 'anahtar': ['dis boya', 'dış boya', 'silikonlu boya', 'fasad']},
    ],
}

IS_TIPLERI = {
    'ic_siva':  'İç Sıva (kum-çimento)',
    'alci':     'Alçı Sıva',
    'astar':    'Astar',
    'ic_boya':  'İç Boya (2 kat)',
    'dis_siva': 'Dış Sıva',
    'dis_boya': 'Dış Boya',
}

# ─── CŞB İŞÇİLİK VERİMLİLİK NORMLARI ───────────────────────────────────────
# kaynak: CLAUDE.md verimlilik tablosu (CŞB birim fiyat analizleri)
ISCILIK_VERIMLILIK: Dict[str, float] = {
    'ic_siva':  25.0,
    'dis_siva': 20.0,
    'alci':     20.0,
    'astar':    40.0,
    'ic_boya':  45.0,
    'dis_boya': 30.0,
}

GUNLUK_UCRET_VARSAYILAN = Decimal('1800')   # 2026 ortalama usta günlüğü (TL)


# ─── VERİ MODELLERİ ──────────────────────────────────────────────────────────

@dataclass
class MalzemeKalemi:
    """Malzeme hesap satiri."""
    is_tipi: str
    malzeme_adi: str
    miktar: float
    birim: str
    birim_fiyat: Decimal
    toplam: Decimal
    kaynak: str           # 'tedarikci' | 'manuel' | 'yok'
    torba_sayisi: Optional[int] = None

    def __str__(self):
        return (
            f'{self.malzeme_adi}: {self.miktar:.2f} {self.birim} '
            f'x {float(self.birim_fiyat):.2f} TL = {float(self.toplam):.2f} TL'
        )


@dataclass
class IscilikKalemi:
    """Iscilik maliyet satiri (CŞB normuna gore)."""
    is_tipi: str
    is_tipi_ad: str
    verimlilik_m2_gun: float   # CŞB normu
    gerekli_gun: float          # alan / verimlilik
    gunluk_ucret: Decimal
    toplam: Decimal

    def __str__(self):
        return (
            f'{self.is_tipi_ad}: {self.gerekli_gun:.2f} usta.gun '
            f'x {float(self.gunluk_ucret):.2f} TL = {float(self.toplam):.2f} TL'
        )


# ─── ENGINE ──────────────────────────────────────────────────────────────────

class InceIslerHizliEngine:
    """
    Ince isler hizli hesap motoru.
    Tedarikci engine opsiyonel — yoksa malzeme fiyatlari 0 birakilir.
    """

    def __init__(self, db=None):
        self.db = db
        self._fiyat_cache: Dict[str, Decimal] = {}
        self._tedarikci_listesi: Optional[List[dict]] = None

    # ── Tedarikci fiyat çekme ────────────────────────────────────────────────

    def _tedarikci_fiyat_cek(self, anahtar_listesi: List[str]) -> Decimal:
        """Tedarikci DB'den fuzzy keyword esleme ile en dusuk fiyati dondur."""
        if not self.db:
            return Decimal('0')

        anahtar_key = '|'.join(sorted(anahtar_listesi))
        if anahtar_key in self._fiyat_cache:
            return self._fiyat_cache[anahtar_key]

        try:
            if self._tedarikci_listesi is None:
                kayitlar = self.db.get_tedarikci_fiyatlari()
                self._tedarikci_listesi = kayitlar if kayitlar else []

            en_dusuk = Decimal('0')
            for kayit in self._tedarikci_listesi:
                mal_adi = (kayit.get('malzeme_adi') or '').lower()
                mal_kodu = (kayit.get('malzeme_kodu') or '').lower()
                arama = mal_adi + ' ' + mal_kodu

                for anahtar in anahtar_listesi:
                    if anahtar.lower() in arama:
                        fiyat_ham = kayit.get('birim_fiyat') or 0
                        indirim = kayit.get('indirim_orani') or 0
                        fiyat = Decimal(str(fiyat_ham)) * (1 - Decimal(str(indirim)) / 100)
                        if en_dusuk == 0 or fiyat < en_dusuk:
                            en_dusuk = fiyat
                        break

            self._fiyat_cache[anahtar_key] = en_dusuk
            return en_dusuk

        except Exception as e:
            logger.warning("Tedarikci fiyat cekilemedi: %s", e)
            return Decimal('0')

    # ── Alan hesabı ─────────────────────────────────────────────────────────

    def efektif_alan(
        self,
        net_alan: float,
        kapi_sayisi: int = 0,
        kapi_alan: float = 2.0,
        pencere_sayisi: int = 0,
        pencere_alan: float = 1.5,
    ) -> float:
        """Net boyama/siva alanini hesapla (kapi+pencere dusilur)."""
        dusilecek = kapi_sayisi * kapi_alan + pencere_sayisi * pencere_alan
        return max(0.0, net_alan - dusilecek)

    # ── Malzeme hesabı ───────────────────────────────────────────────────────

    def hesapla_is_tipi(self, is_tipi: str, alan: float) -> List[MalzemeKalemi]:
        """Tek is tipi icin malzeme listesi."""
        if is_tipi not in KATSAYILAR or alan <= 0:
            return []

        kalemler = []
        for malzeme in KATSAYILAR[is_tipi]:
            miktar = alan * malzeme['katsayi']
            torba_sayisi = None
            if 'torba_kg' in malzeme:
                torba_sayisi = math.ceil(miktar / malzeme['torba_kg'])

            fiyat = self._tedarikci_fiyat_cek(malzeme['anahtar'])
            kaynak = 'tedarikci' if fiyat > 0 else 'yok'
            toplam = R2(Decimal(str(miktar)) * fiyat)

            kalemler.append(MalzemeKalemi(
                is_tipi=is_tipi,
                malzeme_adi=malzeme['ad'],
                miktar=round(miktar, 2),
                birim=malzeme['birim'],
                birim_fiyat=fiyat,
                toplam=toplam,
                kaynak=kaynak,
                torba_sayisi=torba_sayisi,
            ))
        return kalemler

    def hesapla_kombo(
        self,
        alan: float,
        is_tipleri: List[str],
        kapi_sayisi: int = 0,
        kapi_alan: float = 2.0,
        pencere_sayisi: int = 0,
        pencere_alan: float = 1.5,
    ) -> List[MalzemeKalemi]:
        """Birden fazla is tipi icin toplam malzeme listesi."""
        eff_alan = self.efektif_alan(alan, kapi_sayisi, kapi_alan, pencere_sayisi, pencere_alan)
        tum: List[MalzemeKalemi] = []
        for it in is_tipleri:
            tum.extend(self.hesapla_is_tipi(it, eff_alan))
        return tum

    # ── İşçilik hesabı ───────────────────────────────────────────────────────

    def hesapla_iscilik(
        self,
        is_tipleri: List[str],
        alan: float,
        gunluk_ucret: Decimal = GUNLUK_UCRET_VARSAYILAN,
    ) -> List[IscilikKalemi]:
        """
        CŞB verimlilik normlarına göre işçilik maliyeti hesapla.
        alan: efektif alan (kapi/pencere dusilmus)
        gunluk_ucret: usta gunluk ucreti TL
        """
        if alan <= 0:
            return []

        kalemler: List[IscilikKalemi] = []
        for it in is_tipleri:
            verimlilik = ISCILIK_VERIMLILIK.get(it)
            if not verimlilik:
                continue
            gerekli_gun = alan / verimlilik
            toplam = R2(Decimal(str(gerekli_gun)) * gunluk_ucret)
            kalemler.append(IscilikKalemi(
                is_tipi=it,
                is_tipi_ad=IS_TIPLERI.get(it, it),
                verimlilik_m2_gun=verimlilik,
                gerekli_gun=round(gerekli_gun, 2),
                gunluk_ucret=gunluk_ucret,
                toplam=toplam,
            ))
        return kalemler

    # ── Fiyat güncelleme ─────────────────────────────────────────────────────

    def fiyat_manuel_guncelle(
        self, kalemler: List[MalzemeKalemi], idx: int, yeni_fiyat: Decimal
    ) -> None:
        k = kalemler[idx]
        k.birim_fiyat = yeni_fiyat
        k.toplam = R2(Decimal(str(k.miktar)) * yeni_fiyat)
        k.kaynak = 'manuel'

    # ── Toplamlar ────────────────────────────────────────────────────────────

    def malzeme_toplam(self, kalemler: List[MalzemeKalemi]) -> Decimal:
        return R2(sum(k.toplam for k in kalemler))

    def iscilik_toplam(self, iscilik_kalemleri: List[IscilikKalemi]) -> Decimal:
        return R2(sum(k.toplam for k in iscilik_kalemleri))

    def genel_toplam(
        self,
        kalemler: List[MalzemeKalemi],
        iscilik_kalemleri: Optional[List[IscilikKalemi]] = None,
    ) -> Decimal:
        mal = self.malzeme_toplam(kalemler)
        isc = self.iscilik_toplam(iscilik_kalemleri) if iscilik_kalemleri else Decimal('0')
        return R2(mal + isc)

    # ── CSV dışa aktarım ─────────────────────────────────────────────────────

    def csv_disari_aktar(
        self,
        kalemler: List[MalzemeKalemi],
        iscilik_kalemleri: Optional[List[IscilikKalemi]],
        dosya_yolu: str,
    ) -> bool:
        """Hesap sonuclarini CSV olarak kaydet (utf-8-sig → Excel uyumlu)."""
        try:
            with open(dosya_yolu, 'w', newline='', encoding='utf-8-sig') as f:
                yazar = csv.writer(f)

                # ── Malzeme ──
                yazar.writerow(['MALZEME', '', '', '', '', ''])
                yazar.writerow(['Is Tipi', 'Malzeme', 'Miktar', 'Birim',
                                'Birim Fiyat (TL)', 'Toplam (TL)'])
                for k in kalemler:
                    is_ad = IS_TIPLERI.get(k.is_tipi, k.is_tipi)
                    miktar_str = f'{k.miktar:.2f}'
                    if k.torba_sayisi:
                        miktar_str += f' ({k.torba_sayisi} torba)'
                    yazar.writerow([
                        is_ad, k.malzeme_adi, miktar_str, k.birim,
                        f'{float(k.birim_fiyat):.2f}', f'{float(k.toplam):.2f}',
                    ])
                mal_t = self.malzeme_toplam(kalemler)
                yazar.writerow(['', '', '', '', 'MALZEME TOPLAMI', f'{float(mal_t):.2f}'])

                # ── İşçilik ──
                if iscilik_kalemleri:
                    yazar.writerow([])
                    yazar.writerow(['ISCILIK', '', '', '', '', ''])
                    yazar.writerow(['Is Tipi', 'Verimlilik (m2/gun)',
                                    'Gerekli Gun', 'Gunluk Ucret (TL)', '', 'Toplam (TL)'])
                    for k in iscilik_kalemleri:
                        yazar.writerow([
                            k.is_tipi_ad,
                            f'{k.verimlilik_m2_gun:.1f}',
                            f'{k.gerekli_gun:.2f}',
                            f'{float(k.gunluk_ucret):.2f}',
                            '',
                            f'{float(k.toplam):.2f}',
                        ])
                    isc_t = self.iscilik_toplam(iscilik_kalemleri)
                    yazar.writerow(['', '', '', '', 'ISCILIK TOPLAMI', f'{float(isc_t):.2f}'])

                # ── Genel toplam ──
                genel = self.genel_toplam(kalemler, iscilik_kalemleri)
                yazar.writerow([])
                yazar.writerow(['', '', '', '', 'GENEL TOPLAM', f'{float(genel):.2f}'])

            logger.info("CSV uretildi: %s", dosya_yolu)
            return True
        except Exception as e:
            logger.error("CSV export hatasi: %s", e)
            return False

    # ── PDF rapor ────────────────────────────────────────────────────────────

    def pdf_rapor(
        self,
        kalemler: List[MalzemeKalemi],
        alan: float,
        is_tipleri: List[str],
        cikti_yolu: str,
        iscilik_kalemleri: Optional[List[IscilikKalemi]] = None,
    ) -> bool:
        """Hesap sonucunu PDF olarak kaydet (malzeme + iscilik + genel toplam)."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, HRFlowable,
            )
        except ImportError:
            logger.error("pdf_rapor: reportlab kurulu degil.")
            return False

        try:
            from datetime import datetime
            doc = SimpleDocTemplate(
                str(cikti_yolu),
                pagesize=A4,
                leftMargin=2.0 * cm, rightMargin=2.0 * cm,
                topMargin=1.5 * cm, bottomMargin=2.0 * cm,
            )
            genislik = A4[0] - 4.0 * cm

            stiller = getSampleStyleSheet()
            s_baslik = ParagraphStyle(
                'Baslik', parent=stiller['Heading1'],
                fontSize=13, leading=16, alignment=1, spaceAfter=4,
            )
            s_normal = ParagraphStyle(
                'Normal2', parent=stiller['Normal'], fontSize=8, leading=11,
            )
            s_bold = ParagraphStyle(
                'Bold2', parent=stiller['Normal'],
                fontSize=8, leading=11, fontName=_PDF_FONT_BOLD,
            )
            s_section = ParagraphStyle(
                'Section', parent=stiller['Normal'],
                fontSize=9, leading=12, fontName=_PDF_FONT_BOLD,
                textColor=colors.HexColor('#2C3E50'),
            )

            tarih_str = datetime.now().strftime('%d.%m.%Y %H:%M')
            is_tipleri_str = ', '.join(IS_TIPLERI.get(it, it) for it in is_tipleri)

            hikaye = []
            hikaye.append(Paragraph('INCE ISLER HIZLI MALIYET HESABI', s_baslik))
            hikaye.append(Paragraph(
                f'Tarih: {tarih_str}  |  Alan: {alan:.2f} m2  |  Is Tipleri: {is_tipleri_str}',
                s_normal
            ))
            hikaye.append(HRFlowable(width='100%', thickness=1, color=colors.black))
            hikaye.append(Spacer(1, 0.3 * cm))

            col_w6 = [
                genislik * 0.28, genislik * 0.10, genislik * 0.08,
                genislik * 0.17, genislik * 0.17, genislik * 0.20,
            ]

            # ── Malzeme tablosu ──
            hikaye.append(Paragraph('MALZEME', s_section))
            hikaye.append(Spacer(1, 0.15 * cm))

            mal_header = [[
                Paragraph('<b>Malzeme</b>', s_bold),
                Paragraph('<b>Miktar</b>', s_bold),
                Paragraph('<b>Birim</b>', s_bold),
                Paragraph('<b>Birim Fiyat (TL)</b>', s_bold),
                Paragraph('<b>Toplam (TL)</b>', s_bold),
                Paragraph('<b>Kaynak</b>', s_bold),
            ]]
            mal_satirlar = []
            for k in kalemler:
                miktar_str = str(k.miktar)
                if k.torba_sayisi:
                    miktar_str = f'{k.miktar} ({k.torba_sayisi} torba)'
                mal_satirlar.append([
                    Paragraph(k.malzeme_adi, s_normal),
                    Paragraph(miktar_str, s_normal),
                    Paragraph(k.birim, s_normal),
                    Paragraph(f'{float(k.birim_fiyat):,.2f}', s_normal),
                    Paragraph(f'{float(k.toplam):,.2f}', s_normal),
                    Paragraph(k.kaynak, s_normal),
                ])
            mal_t = self.malzeme_toplam(kalemler)
            mal_satirlar.append([
                Paragraph('<b>MALZEME TOPLAMI</b>', s_bold), '', '', '',
                Paragraph(f'<b>{float(mal_t):,.2f}</b>', s_bold), '',
            ])

            mal_tablo = Table(mal_header + mal_satirlar, colWidths=col_w6)
            mal_tablo.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ECF0F1')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8F9FA')]),
            ]))
            hikaye.append(mal_tablo)
            hikaye.append(Spacer(1, 0.3 * cm))

            # ── İşçilik tablosu ──
            if iscilik_kalemleri:
                hikaye.append(Paragraph('ISCILIK', s_section))
                hikaye.append(Spacer(1, 0.15 * cm))

                isc_col_w = [
                    genislik * 0.30, genislik * 0.15, genislik * 0.13,
                    genislik * 0.22, genislik * 0.20,
                ]
                isc_header = [[
                    Paragraph('<b>Is Tipi</b>', s_bold),
                    Paragraph('<b>Verimlilik (m2/gun)</b>', s_bold),
                    Paragraph('<b>Gerekli Gun</b>', s_bold),
                    Paragraph('<b>Gunluk Ucret (TL)</b>', s_bold),
                    Paragraph('<b>Toplam (TL)</b>', s_bold),
                ]]
                isc_satirlar = []
                for k in iscilik_kalemleri:
                    isc_satirlar.append([
                        Paragraph(k.is_tipi_ad, s_normal),
                        Paragraph(f'{k.verimlilik_m2_gun:.1f}', s_normal),
                        Paragraph(f'{k.gerekli_gun:.2f}', s_normal),
                        Paragraph(f'{float(k.gunluk_ucret):,.2f}', s_normal),
                        Paragraph(f'{float(k.toplam):,.2f}', s_normal),
                    ])
                isc_t = self.iscilik_toplam(iscilik_kalemleri)
                isc_satirlar.append([
                    Paragraph('<b>ISCILIK TOPLAMI</b>', s_bold), '', '',
                    '',
                    Paragraph(f'<b>{float(isc_t):,.2f}</b>', s_bold),
                ])

                isc_tablo = Table(isc_header + isc_satirlar, colWidths=isc_col_w)
                isc_tablo.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A5276')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#D6EAF8')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#EBF5FB')]),
                ]))
                hikaye.append(isc_tablo)
                hikaye.append(Spacer(1, 0.3 * cm))

            # ── Genel toplam satiri ──
            genel = self.genel_toplam(kalemler, iscilik_kalemleri)
            genel_data = [[
                Paragraph(f'<b>GENEL TOPLAM: {float(genel):,.2f} TL</b>', s_bold),
            ]]
            genel_tablo = Table(genel_data, colWidths=[genislik])
            genel_tablo.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2C3E50')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ]))
            hikaye.append(genel_tablo)

            doc.build(hikaye)
            logger.info("Ince isler PDF uretildi: %s", cikti_yolu)
            return True
        except Exception as e:
            logger.error("PDF uretim hatasi: %s", e)
            return False
