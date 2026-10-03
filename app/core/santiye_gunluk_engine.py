"""
Santiye Gunluk Rapor Motoru
SQLite CRUD + PDF santiye defteri uretimi

Neyi cozuyoruz?
- Her insaat projesinde yasal zorunluluk olan santiye defterini dijital ortamda tut
- Hava durumu hava_durumu.py uzerinden otomatik doldurulur
- PDF santiye defteri: 4735 kapsaminda denetim ve arsivleme icin

Test:
  engine = SantiyeGunlukEngine()
  kayit = SantiyeGunlukKayit(proje_id=1, tarih=date.today(), usta_sayi=4)
  engine.kayit_ekle(kayit)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    from app.utils.font_utils import get_fonts as _get_fonts
    _PDF_FONT, _PDF_FONT_BOLD = _get_fonts()
except Exception:
    _PDF_FONT, _PDF_FONT_BOLD = "Helvetica", "Helvetica-Bold"


# ─── DB YOLU ────────────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    _data_dir = Path(os.environ.get(
        'QUANTIX_DATA_DIR',
        str(Path.home() / 'QuantixPro' / 'data')
    ))
else:
    _data_dir = Path(__file__).parent.parent.parent / 'data'

_data_dir.mkdir(parents=True, exist_ok=True)
VARSAYILAN_DB = _data_dir / 'santiye_gunluk.db'


# ─── VERİ MODELI ────────────────────────────────────────────────────────────

@dataclass
class MalzemeKalemi:
    """Kullanilan malzeme satirini temsil eder."""
    ad: str
    miktar: float
    birim: str

    def to_dict(self) -> dict:
        return {'ad': self.ad, 'miktar': self.miktar, 'birim': self.birim}

    @staticmethod
    def from_dict(d: dict) -> 'MalzemeKalemi':
        return MalzemeKalemi(
            ad=d.get('ad', ''),
            miktar=float(d.get('miktar', 0)),
            birim=d.get('birim', '')
        )


@dataclass
class SantiyeGunlukKayit:
    """Tek gunluk santiye defteri kaydi."""
    proje_id: int
    tarih: date
    # Hava
    hava_max: Optional[float] = None
    hava_min: Optional[float] = None
    hava_durum: str = ''
    hava_yagis_mm: Optional[float] = None
    # Ekip
    usta_sayi: int = 0
    yardimci_sayi: int = 0
    sef_sayi: int = 0
    taseron_sayi: int = 0
    # Is ve malzeme
    yapilan_isler: str = ''
    malzemeler: List[MalzemeKalemi] = field(default_factory=list)
    # Diger
    notlar: str = ''
    ziyaretciler: str = ''
    # Sistem
    id: Optional[int] = None
    olusturma_zamani: Optional[datetime] = None

    @property
    def toplam_isci(self) -> int:
        return self.usta_sayi + self.yardimci_sayi + self.sef_sayi + self.taseron_sayi

    def malzeme_json(self) -> str:
        return json.dumps([m.to_dict() for m in self.malzemeler], ensure_ascii=False)

    @staticmethod
    def malzeme_parse(json_str: str) -> List[MalzemeKalemi]:
        if not json_str:
            return []
        try:
            return [MalzemeKalemi.from_dict(d) for d in json.loads(json_str)]
        except Exception:
            return []


# ─── ENGINE ─────────────────────────────────────────────────────────────────

class SantiyeGunlukEngine:
    """
    Santiye gunluk kayit motoru.
    database.py'den bagimsiz ayri SQLite kullanir.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS santiye_gunluk (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        proje_id             INTEGER NOT NULL,
        tarih                TEXT NOT NULL,
        hava_max             REAL,
        hava_min             REAL,
        hava_durum           TEXT,
        hava_yagis_mm        REAL,
        usta_sayi            INTEGER DEFAULT 0,
        yardimci_sayi        INTEGER DEFAULT 0,
        sef_sayi             INTEGER DEFAULT 0,
        taseron_sayi         INTEGER DEFAULT 0,
        yapilan_isler        TEXT,
        malzeme_json         TEXT,
        notlar               TEXT,
        ziyaretciler         TEXT,
        olusturma_zamani     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(proje_id, tarih)
    );
    CREATE INDEX IF NOT EXISTS idx_sg_proje_tarih
        ON santiye_gunluk(proje_id, tarih);
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else VARSAYILAN_DB
        self._init_schema()

    def _baglanti(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._baglanti() as conn:
            for stmt in self.SCHEMA.split(';'):
                s = stmt.strip()
                if s:
                    conn.execute(s)
            conn.commit()

    # ── CRUD ────────────────────────────────────────────────────────────────

    def kayit_ekle(self, kayit: SantiyeGunlukKayit) -> int:
        """Yeni kayit ekle. Ayni (proje_id, tarih) varsa IntegrityError firlatir."""
        sql = """
            INSERT INTO santiye_gunluk (
                proje_id, tarih, hava_max, hava_min, hava_durum, hava_yagis_mm,
                usta_sayi, yardimci_sayi, sef_sayi, taseron_sayi,
                yapilan_isler, malzeme_json, notlar, ziyaretciler
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        params = (
            kayit.proje_id,
            kayit.tarih.isoformat(),
            kayit.hava_max, kayit.hava_min, kayit.hava_durum, kayit.hava_yagis_mm,
            kayit.usta_sayi, kayit.yardimci_sayi, kayit.sef_sayi, kayit.taseron_sayi,
            kayit.yapilan_isler, kayit.malzeme_json(), kayit.notlar, kayit.ziyaretciler,
        )
        with self._baglanti() as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid

    def kayit_guncelle(self, kayit_id: int, kayit: SantiyeGunlukKayit) -> None:
        """Mevcut kaydi guncelle."""
        sql = """
            UPDATE santiye_gunluk SET
                tarih=?, hava_max=?, hava_min=?, hava_durum=?, hava_yagis_mm=?,
                usta_sayi=?, yardimci_sayi=?, sef_sayi=?, taseron_sayi=?,
                yapilan_isler=?, malzeme_json=?, notlar=?, ziyaretciler=?
            WHERE id=?
        """
        params = (
            kayit.tarih.isoformat(),
            kayit.hava_max, kayit.hava_min, kayit.hava_durum, kayit.hava_yagis_mm,
            kayit.usta_sayi, kayit.yardimci_sayi, kayit.sef_sayi, kayit.taseron_sayi,
            kayit.yapilan_isler, kayit.malzeme_json(), kayit.notlar, kayit.ziyaretciler,
            kayit_id,
        )
        with self._baglanti() as conn:
            conn.execute(sql, params)
            conn.commit()

    def kayit_sil(self, kayit_id: int) -> None:
        with self._baglanti() as conn:
            conn.execute('DELETE FROM santiye_gunluk WHERE id=?', (kayit_id,))
            conn.commit()

    def kayit_getir(self, kayit_id: int) -> Optional[SantiyeGunlukKayit]:
        with self._baglanti() as conn:
            row = conn.execute(
                'SELECT * FROM santiye_gunluk WHERE id=?', (kayit_id,)
            ).fetchone()
        return self._row_to_kayit(row) if row else None

    def tarih_ile_getir(self, proje_id: int, tarih: date) -> Optional[SantiyeGunlukKayit]:
        with self._baglanti() as conn:
            row = conn.execute(
                'SELECT * FROM santiye_gunluk WHERE proje_id=? AND tarih=?',
                (proje_id, tarih.isoformat())
            ).fetchone()
        return self._row_to_kayit(row) if row else None

    def kayitlari_listele(
        self,
        proje_id: int,
        baslangic: Optional[date] = None,
        bitis: Optional[date] = None,
    ) -> List[SantiyeGunlukKayit]:
        sql = 'SELECT * FROM santiye_gunluk WHERE proje_id=?'
        params: list = [proje_id]
        if baslangic:
            sql += ' AND tarih >= ?'
            params.append(baslangic.isoformat())
        if bitis:
            sql += ' AND tarih <= ?'
            params.append(bitis.isoformat())
        sql += ' ORDER BY tarih DESC'
        with self._baglanti() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_kayit(r) for r in rows]

    def kayit_var_mi(self, proje_id: int, tarih: date) -> bool:
        with self._baglanti() as conn:
            row = conn.execute(
                'SELECT 1 FROM santiye_gunluk WHERE proje_id=? AND tarih=?',
                (proje_id, tarih.isoformat())
            ).fetchone()
        return row is not None

    def kayitli_tarihler(self, proje_id: int) -> List[date]:
        """Bir projedeki tum kayitli tarihleri dondur."""
        with self._baglanti() as conn:
            rows = conn.execute(
                'SELECT tarih FROM santiye_gunluk WHERE proje_id=? ORDER BY tarih',
                (proje_id,)
            ).fetchall()
        return [date.fromisoformat(r['tarih']) for r in rows]

    def _row_to_kayit(self, row: sqlite3.Row) -> SantiyeGunlukKayit:
        return SantiyeGunlukKayit(
            id=row['id'],
            proje_id=row['proje_id'],
            tarih=date.fromisoformat(row['tarih']),
            hava_max=row['hava_max'],
            hava_min=row['hava_min'],
            hava_durum=row['hava_durum'] or '',
            hava_yagis_mm=row['hava_yagis_mm'],
            usta_sayi=row['usta_sayi'] or 0,
            yardimci_sayi=row['yardimci_sayi'] or 0,
            sef_sayi=row['sef_sayi'] or 0,
            taseron_sayi=row['taseron_sayi'] or 0,
            yapilan_isler=row['yapilan_isler'] or '',
            malzemeler=SantiyeGunlukKayit.malzeme_parse(row['malzeme_json'] or ''),
            notlar=row['notlar'] or '',
            ziyaretciler=row['ziyaretciler'] or '',
            olusturma_zamani=datetime.fromisoformat(row['olusturma_zamani'])
            if row['olusturma_zamani'] else None,
        )

    # ── PDF URETIMI ─────────────────────────────────────────────────────────

    def pdf_uret(
        self,
        proje_id: int,
        baslangic: date,
        bitis: date,
        cikti_yolu: str,
        proje_adi: str = 'Proje',
        imza_alani: bool = True,
    ) -> bool:
        """
        Tarih araligindaki kayitlar icin PDF santiye defteri uret.
        Her gun ayri sayfa. Alt kisimda uc imza alani.
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, HRFlowable, PageBreak,
            )
        except ImportError:
            logger.error("pdf_uret: reportlab kurulu degil.")
            return False

        kayitlar = self.kayitlari_listele(proje_id, baslangic, bitis)
        if not kayitlar:
            logger.warning("pdf_uret: Belirtilen tarih araliginda kayit yok.")
            return False

        # Tarih artan sira
        kayitlar = list(reversed(kayitlar))

        try:
            doc = SimpleDocTemplate(
                str(cikti_yolu),
                pagesize=A4,
                leftMargin=2.0 * cm,
                rightMargin=2.0 * cm,
                topMargin=1.5 * cm,
                bottomMargin=2.0 * cm,
            )
            genislik = A4[0] - 4.0 * cm

            stiller = getSampleStyleSheet()
            s_baslik = ParagraphStyle(
                'SBaslik', parent=stiller['Heading1'],
                fontSize=13, leading=16, alignment=1, spaceAfter=2,
            )
            s_alt_baslik = ParagraphStyle(
                'SAltBaslik', parent=stiller['Normal'],
                fontSize=9, leading=11, alignment=1, spaceAfter=6,
            )
            s_normal = ParagraphStyle(
                'SNormal', parent=stiller['Normal'],
                fontSize=8, leading=11,
            )
            s_bold = ParagraphStyle(
                'SBold', parent=stiller['Normal'],
                fontSize=8, leading=11, fontName=_PDF_FONT_BOLD,
            )

            hikaye = []

            for i, kayit in enumerate(kayitlar):
                # Sayfa baslik
                hikaye.append(Paragraph('SANTIYE GUNLUK RAPOR', s_baslik))
                hikaye.append(Paragraph(
                    f'Proje: {proje_adi} | '
                    'Tarih: ' + kayit.tarih.strftime('%d.%m.%Y') +
                    f' | Toplam Isci: {kayit.toplam_isci} kisi',
                    s_alt_baslik
                ))
                hikaye.append(HRFlowable(width='100%', thickness=1, color=colors.black))
                hikaye.append(Spacer(1, 0.3 * cm))

                # Hava durumu
                hava_satirlar = [
                    [
                        Paragraph('<b>HAVA DURUMU</b>', s_bold),
                        Paragraph(
                            f'Max: {kayit.hava_max:.1f} C  |  Min: {kayit.hava_min:.1f} C  |  '
                            f'Durum: {kayit.hava_durum}  |  '
                            f'Yagis: {kayit.hava_yagis_mm:.1f} mm'
                            if kayit.hava_max is not None else 'Girilmemis',
                            s_normal
                        ),
                    ]
                ]
                hava_tablo = Table(hava_satirlar, colWidths=[genislik * 0.25, genislik * 0.75])
                hava_tablo.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F4FD')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                hikaye.append(hava_tablo)
                hikaye.append(Spacer(1, 0.2 * cm))

                # Ekip cizelgesi
                ekip_data = [
                    [
                        Paragraph('<b>EKIP</b>', s_bold),
                        Paragraph(
                            f'Usta: {kayit.usta_sayi}  |  Yardimci: {kayit.yardimci_sayi}  |  '
                            f'Sef: {kayit.sef_sayi}  |  Taseron: {kayit.taseron_sayi}  |  '
                            f'TOPLAM: {kayit.toplam_isci}',
                            s_normal
                        ),
                    ]
                ]
                ekip_tablo = Table(ekip_data, colWidths=[genislik * 0.25, genislik * 0.75])
                ekip_tablo.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F8E8')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                hikaye.append(ekip_tablo)
                hikaye.append(Spacer(1, 0.2 * cm))

                # Yapilan isler
                is_data = [
                    [Paragraph('<b>YAPILAN ISLER</b>', s_bold)],
                    [Paragraph(kayit.yapilan_isler or '(Girilmemis)', s_normal)],
                ]
                is_tablo = Table(is_data, colWidths=[genislik])
                is_tablo.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5F5F5')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('MINROWHEIGHT', (0, 1), (-1, 1), 2.0 * cm),
                ]))
                hikaye.append(is_tablo)
                hikaye.append(Spacer(1, 0.2 * cm))

                # Kullanilan malzeme
                if kayit.malzemeler:
                    mal_header = [[
                        Paragraph('<b>Malzeme</b>', s_bold),
                        Paragraph('<b>Miktar</b>', s_bold),
                        Paragraph('<b>Birim</b>', s_bold),
                    ]]
                    mal_rows = [
                        [
                            Paragraph(m.ad, s_normal),
                            Paragraph(str(m.miktar), s_normal),
                            Paragraph(m.birim, s_normal),
                        ]
                        for m in kayit.malzemeler
                    ]
                    mal_data = mal_header + mal_rows
                    mal_tablo = Table(
                        mal_data,
                        colWidths=[genislik * 0.6, genislik * 0.2, genislik * 0.2]
                    )
                    mal_tablo.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5F5F5')),
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ]))
                    hikaye.append(Paragraph('<b>KULLANILAN MALZEME</b>', s_bold))
                    hikaye.append(Spacer(1, 0.1 * cm))
                    hikaye.append(mal_tablo)
                    hikaye.append(Spacer(1, 0.2 * cm))

                # Notlar ve ziyaretciler
                for etiket, icerik in [('NOTLAR', kayit.notlar), ('ZIYARETCILER', kayit.ziyaretciler)]:
                    if icerik:
                        ek_data = [
                            [Paragraph(f'<b>{etiket}</b>', s_bold)],
                            [Paragraph(icerik, s_normal)],
                        ]
                        ek_tablo = Table(ek_data, colWidths=[genislik])
                        ek_tablo.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5F5F5')),
                            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                            ('TOPPADDING', (0, 0), (-1, -1), 4),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                            ('LEFTPADDING', (0, 0), (-1, -1), 6),
                        ]))
                        hikaye.append(ek_tablo)
                        hikaye.append(Spacer(1, 0.2 * cm))

                # Imza alanlari
                if imza_alani:
                    hikaye.append(Spacer(1, 0.5 * cm))
                    imza_data = [[
                        Paragraph(
                            '<b>Santiye Sefi</b><br/><br/><br/>'
                            '________________________<br/>Ad Soyad / Imza',
                            s_normal
                        ),
                        Paragraph(
                            '<b>Muteahhit</b><br/><br/><br/>'
                            '________________________<br/>Ad Soyad / Imza / Kase',
                            s_normal
                        ),
                        Paragraph(
                            '<b>Kontrol Muhendisi</b><br/><br/><br/>'
                            '________________________<br/>Ad Soyad / Imza',
                            s_normal
                        ),
                    ]]
                    imza_tablo = Table(
                        imza_data,
                        colWidths=[genislik / 3, genislik / 3, genislik / 3]
                    )
                    imza_tablo.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ]))
                    hikaye.append(imza_tablo)

                # Son kayit degilse sayfa sonu
                if i < len(kayitlar) - 1:
                    hikaye.append(PageBreak())

            doc.build(hikaye)
            logger.info("PDF santiye defteri uretildi: %s (%d gun)", cikti_yolu, len(kayitlar))
            return True

        except Exception as e:
            logger.error("PDF uretim hatasi: %s", e)
            return False
