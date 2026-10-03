"""
Yaklaşık Maliyet ve Keşif Özeti Motoru
=======================================
4734 Sayılı Kamu İhale Kanunu kapsamında yaklaşık maliyet hesabı.

Desteklenen kurum fiyat listeleri:
- ÇŞB : Çevre, Şehircilik ve İklim Bakanlığı (Yapım işleri)  — CSBPozEngine
- DSİ : Devlet Su İşleri
- KGM : Karayolları Genel Müdürlüğü
- İLBANK: İller Bankası (Belediye altyapısı)

Hesaplanan değerler:
- Poz bazlı tutar (miktar × birim fiyat)
- Toplam yapım bedeli
- KDV tutarı
- Genel toplam (KDV dahil)
- Aşırı düşük teklif sınır değeri (KİK md.38)
- Resmi keşif özeti formatında export (JSON / Excel satırları)
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
import logging

from app.core.csb_poz_engine import CSBPozEngine

logger = logging.getLogger(__name__)

try:
    from app.utils.font_utils import get_fonts as _get_fonts
    _PDF_FONT, _PDF_FONT_BOLD = _get_fonts()
except Exception:
    _PDF_FONT, _PDF_FONT_BOLD = _PDF_FONT, _PDF_FONT_BOLD


# ============================================================
# KURUM FİYAT LİSTESİ TANIMLARI
# ============================================================

KURUM_LISTESI: Dict[str, str] = {
    'csb': 'ÇŞB — Çevre, Şehircilik ve İklim Bakanlığı',
    'dsi': 'DSİ — Devlet Su İşleri',
    'kgm': 'KGM — Karayolları Genel Müdürlüğü',
    'ilbank': 'İLBANK — İller Bankası',
    'ozel': 'Özel / Piyasa Fiyatı',
}

# KDV oranları (%)
KDV_ORANLARI: Dict[str, Decimal] = {
    'standard': Decimal('20'),   # Genel KDV oranı (2023 sonrası)
    'insaat': Decimal('20'),     # İnşaat KDV oranı
    'muaf': Decimal('0'),        # KDV muaf (bazı kamu ihaleleri)
}

# 4734 KİK md.38: Sınır değer = ortalama × 0.80
ASIRI_DUSUK_KATSAYI = Decimal('0.80')

# Kategori etiketleri (poz_kodu prefix → kategori adı)
KATEGORI_MAP: Dict[str, str] = {
    '16': 'Toprak İşleri',
    '21': 'Beton ve Betonarme',
    '22': 'Duvar İşleri',
    '23': 'Sıva İşleri',
    '24': 'Boya İşleri',
    '25': 'Döşeme İşleri',
    '26': 'Yalıtım',
    '27': 'Çatı İşleri',
    '30': 'Elektrik Tesisatı',
    '31': 'Mekanik Tesisat',
    '33': 'Kapı/Pencere',
    '34': 'Çelik Yapı',
}


# ============================================================
# KALEM SINIFI
# ============================================================

class YaklasikMaliyetKalemi:
    """
    Keşif / yaklaşık maliyet cetveli tek satırı.

    Her satır bir poz kalemini temsil eder:
    sira_no | poz_no | tanim | birim | miktar | birim_fiyat → tutar
    """

    def __init__(
        self,
        sira_no: int,
        poz_no: str,
        tanim: str,
        birim: str,
        miktar: Decimal,
        birim_fiyat: Decimal,
        kurum: str = 'csb',
        aciklama: str = '',
    ):
        self.sira_no = sira_no
        self.poz_no = poz_no
        self.tanim = tanim
        self.birim = birim
        self.miktar = miktar
        self.birim_fiyat = birim_fiyat
        self.kurum = kurum
        self.aciklama = aciklama

    # ------------------------------------------------------------------
    # HESAPLANAN PROPERTY
    # ------------------------------------------------------------------

    @property
    def tutar(self) -> Decimal:
        """Kalem tutarı = miktar × birim fiyat (2 ondalık hassasiyet)."""
        return (self.miktar * self.birim_fiyat).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    # ------------------------------------------------------------------
    # SERİLEŞTİRME
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Kalem verisini JSON-uyumlu dict olarak döndür."""
        return {
            'sira_no': self.sira_no,
            'poz_no': self.poz_no,
            'tanim': self.tanim,
            'birim': self.birim,
            'miktar': float(self.miktar),
            'birim_fiyat': float(self.birim_fiyat),
            'tutar': float(self.tutar),
            'kurum': self.kurum,
            'aciklama': self.aciklama,
        }

    def __repr__(self) -> str:
        return (
            f"YaklasikMaliyetKalemi("
            f"sira={self.sira_no}, poz={self.poz_no!r}, "
            f"miktar={float(self.miktar)}, tutar={float(self.tutar):,.2f} TL)"
        )


# ============================================================
# MOTOR SINIFI
# ============================================================

class YaklasikMaliyetEngine:
    """
    Yaklaşık maliyet hesaplama motoru.

    Neyi çözüyoruz:
    4734 KİK kapsamında müteahhitin ihaleye girmeden önce kendi keşfini
    yapması ve teklifini doğru konumlandırması. Aşırı düşük sınırın
    tespiti teklif reddini önler.

    Nasıl test ederiz:
    - Bilinen poz + miktar girişiyle beklenen toplam doğrula
    - KDV tutarı = toplam × kdv_orani / 100 kontrolü
    - Aşırı düşük sınır = yaklaşık maliyet × 0.80 kontrolü
    - asiri_dusuk_analizi ile n>=5 teklif listesinde uç değer eleme
    """

    def __init__(self):
        self.kalemler: List[YaklasikMaliyetKalemi] = []
        self.proje_adi: str = ''
        self.ihale_no: str = ''
        self.idare: str = ''
        self.kurum: str = 'csb'            # Varsayılan fiyat listesi
        self.kdv_orani: Decimal = KDV_ORANLARI['standard']
        self.olusturma_tarihi: datetime = datetime.now()
        self._sira_sayac: int = 0
        self._poz_engine: CSBPozEngine = CSBPozEngine()

    # ==================================================================
    # KALEM YÖNETİMİ
    # ==================================================================

    def kalem_ekle(
        self,
        poz_no: str,
        miktar: float,
        birim_fiyat: Optional[float] = None,
        tanim: Optional[str] = None,
        birim: Optional[str] = None,
        aciklama: str = '',
    ) -> YaklasikMaliyetKalemi:
        """
        Keşif cetveline yeni kalem ekle.

        Poz no CSBPozEngine'de varsa tanım, birim ve fiyat otomatik
        doldurulur. birim_fiyat, tanim veya birim override için
        açıkça geçilebilir.

        Args:
            poz_no      : Resmi poz numarası (örn: '21.003')
            miktar      : Metraj miktarı
            birim_fiyat : Opsiyonel override; yoksa CSBPozEngine'den alınır
            tanim       : Opsiyonel override; yoksa CSBPozEngine'den alınır
            birim       : Opsiyonel override; yoksa CSBPozEngine'den alınır
            aciklama    : Serbest not alanı

        Returns:
            Eklenen YaklasikMaliyetKalemi nesnesi
        """
        self._sira_sayac += 1

        # CSBPozEngine'den resmi veriyi çek
        resmi = self._poz_engine.poz_ara(poz_no) or {}

        _tanim = tanim or resmi.get('aciklama', 'Tanımsız Kalem')
        _birim = birim or resmi.get('birim', 'adet')

        if birim_fiyat is not None:
            _fiyat = Decimal(str(birim_fiyat))
        elif resmi.get('birim_fiyat') is not None:
            _fiyat = Decimal(str(resmi['birim_fiyat']))
        else:
            _fiyat = Decimal('0')

        kalem = YaklasikMaliyetKalemi(
            sira_no=self._sira_sayac,
            poz_no=poz_no,
            tanim=_tanim,
            birim=_birim,
            miktar=Decimal(str(miktar)),
            birim_fiyat=_fiyat,
            kurum=self.kurum,
            aciklama=aciklama,
        )
        self.kalemler.append(kalem)
        logger.debug(
            "Kalem eklendi: %s — %s — %.2f TL",
            poz_no, kalem.tanim, float(kalem.tutar),
        )
        return kalem

    def kalem_sil(self, sira_no: int) -> bool:
        """
        Sıra numarasına göre kalem sil.

        Returns:
            True: kalem bulunup silindi; False: kalem bulunamadı
        """
        onceki = len(self.kalemler)
        self.kalemler = [k for k in self.kalemler if k.sira_no != sira_no]
        silindi = len(self.kalemler) < onceki
        if silindi:
            logger.debug("Kalem silindi: sira_no=%d", sira_no)
        else:
            logger.warning("Silinecek kalem bulunamadı: sira_no=%d", sira_no)
        return silindi

    def kalem_guncelle(
        self,
        sira_no: int,
        miktar: Optional[float] = None,
        birim_fiyat: Optional[float] = None,
    ) -> bool:
        """
        Miktar veya birim fiyatı güncelle.

        Returns:
            True: kalem bulunup güncellendi; False: kalem bulunamadı
        """
        for kalem in self.kalemler:
            if kalem.sira_no == sira_no:
                if miktar is not None:
                    kalem.miktar = Decimal(str(miktar))
                if birim_fiyat is not None:
                    kalem.birim_fiyat = Decimal(str(birim_fiyat))
                logger.debug("Kalem güncellendi: sira_no=%d", sira_no)
                return True
        logger.warning("Güncellenecek kalem bulunamadı: sira_no=%d", sira_no)
        return False

    # ==================================================================
    # POZ ARAMA — CSBPozEngine'e DELEGE
    # ==================================================================

    def poz_ara(self, poz_kodu: str) -> Optional[Dict[str, Any]]:
        """
        Poz koduna göre tam eşleşme ara (CSBPozEngine'e delege).

        Returns:
            Poz bilgisi dict'i veya None
        """
        return self._poz_engine.poz_ara(poz_kodu)

    def poz_metin_ara(
        self,
        metin: str,
        kategori: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Tanım veya poz kodu içinde metin arama (CSBPozEngine'e delege).

        Args:
            metin    : Aranacak kelime/poz kodu
            kategori : Opsiyonel kategori filtresi
            limit    : Maksimum sonuç sayısı

        Returns:
            Eşleşen poz kayıtlarının listesi
        """
        return self._poz_engine.metin_ara(metin, kategori=kategori, limit=limit)

    # ==================================================================
    # ANA HESAPLAMALAR
    # ==================================================================

    def toplam_hesapla(self) -> Decimal:
        """
        Tüm kalemlerin KDV hariç tutarı toplamı.

        Returns:
            Decimal (2 ondalık hassasiyet)
        """
        toplam = sum((k.tutar for k in self.kalemler), Decimal('0'))
        return toplam.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def kdv_hesapla(self) -> Decimal:
        """
        KDV tutarı = toplam × kdv_orani / 100.

        Returns:
            Decimal (2 ondalık hassasiyet)
        """
        return (self.toplam_hesapla() * self.kdv_orani / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    def genel_toplam(self) -> Decimal:
        """
        KDV dahil genel toplam.

        Returns:
            Decimal (2 ondalık hassasiyet)
        """
        return (self.toplam_hesapla() + self.kdv_hesapla()).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    def asiri_dusuk_siniri(self) -> Decimal:
        """
        Yaklaşık maliyetin aşırı düşük sınırı (KİK md.38).

        Formül: yaklaşık maliyet × 0.80

        Returns:
            Decimal (2 ondalık hassasiyet)
        """
        return (self.toplam_hesapla() * ASIRI_DUSUK_KATSAYI).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    def asiri_dusuk_analizi(
        self,
        teklif_listesi: List[float],
    ) -> Dict[str, Any]:
        """
        Çok teklifli ihalede aşırı düşük sınır değeri hesabı.

        4734 KİK md.38 tam formülü:
        - N >= 5 teklif: en yüksek + en düşük çıkar, kalan N-2 ortalama × 0.80
        - N < 5  teklif: tüm tekliflerin ortalaması × 0.80

        Args:
            teklif_listesi: Geçerli teklif tutarları (TL, KDV hariç)

        Returns:
            {
              'sinir_deger': Decimal,
              'ortalama': Decimal,
              'asiri_dusuk_teklifler': List[float],
              'gecerli_teklifler': List[float],
            }
        """
        n = len(teklif_listesi)
        if n < 2:
            return {
                'sinir_deger': Decimal('0'),
                'ortalama': Decimal('0'),
                'asiri_dusuk_teklifler': [],
                'gecerli_teklifler': list(teklif_listesi),
                'uyari': 'Yetersiz teklif sayısı (minimum 2 gerekli)',
                'katilimci_sayisi': n,
            }

        teklifler = sorted(Decimal(str(t)) for t in teklif_listesi)

        # Uç değer eleme: N >= 5 ise en düşük ve en yüksek çıkar
        if n >= 5:
            hesap_listesi = teklifler[1:-1]
        else:
            hesap_listesi = teklifler

        ortalama = sum(hesap_listesi) / Decimal(len(hesap_listesi))
        ortalama = ortalama.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        sinir_deger = (ortalama * ASIRI_DUSUK_KATSAYI).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        asiri_dusuk = [float(t) for t in teklifler if t < sinir_deger]
        gecerli = [float(t) for t in teklifler if t >= sinir_deger]

        return {
            'sinir_deger': sinir_deger,
            'ortalama': ortalama,
            'asiri_dusuk_teklifler': asiri_dusuk,
            'gecerli_teklifler': gecerli,
            'katilimci_sayisi': n,
            'elenen_uct_deger': n >= 5,
        }

    # ==================================================================
    # KATEGORİ ÖZETİ
    # ==================================================================

    def kategori_ozeti(self) -> List[Dict[str, Any]]:
        """
        Poz numarası prefix'ine göre kategori bazlı özet.

        Returns:
            [{'kategori': str, 'tutar': float, 'yuzde': float}, ...]
            Tutara göre azalan sıralı
        """
        kategori_tutarlar: Dict[str, Decimal] = {}
        for kalem in self.kalemler:
            prefix = kalem.poz_no.split('.')[0]
            kategori = KATEGORI_MAP.get(prefix, f'Diğer ({prefix})')
            kategori_tutarlar[kategori] = (
                kategori_tutarlar.get(kategori, Decimal('0')) + kalem.tutar
            )

        toplam = sum(kategori_tutarlar.values()) or Decimal('1')
        return [
            {
                'kategori': kat,
                'tutar': float(tutar),
                'yuzde': float(
                    (tutar / toplam * 100).quantize(Decimal('0.1'))
                ),
            }
            for kat, tutar in sorted(
                kategori_tutarlar.items(), key=lambda x: x[1], reverse=True
            )
        ]

    # ==================================================================
    # EXPORT / IMPORT
    # ==================================================================

    def export_json(self) -> Dict[str, Any]:
        """
        Tüm keşif verisini JSON-uyumlu dict olarak serialize et.

        Kullanım alanı: dosyaya kaydetme, API yanıtı, Excel export.

        Returns:
            Tam keşif özeti dict'i
        """
        toplam = self.toplam_hesapla()
        kdv = self.kdv_hesapla()
        genel = self.genel_toplam()
        sinir = self.asiri_dusuk_siniri()

        return {
            'baslik': {
                'idare': self.idare or 'İdare Adı Girilmedi',
                'proje_adi': self.proje_adi or 'Proje Adı Girilmedi',
                'ihale_no': self.ihale_no or '---',
                'fiyat_listesi': KURUM_LISTESI.get(self.kurum, self.kurum),
                'tarih': self.olusturma_tarihi.strftime('%d.%m.%Y'),
                'yil': self.olusturma_tarihi.year,
            },
            'kalemler': [k.to_dict() for k in self.kalemler],
            'ozet': {
                'kalem_sayisi': len(self.kalemler),
                'toplam_yapim_bedeli': float(toplam),
                'kdv_orani': float(self.kdv_orani),
                'kdv_tutari': float(kdv),
                'genel_toplam': float(genel),
                'asiri_dusuk_siniri': float(sinir),
            },
            'kategori_dagilimi': self.kategori_ozeti(),
        }

    def import_json(self, data: Dict[str, Any]) -> None:
        """
        export_json() ile oluşturulmuş dict'ten keşif verisini yükle.

        Mevcut kalemler temizlenir, yeni verilerle doldurulur.

        Args:
            data: export_json() formatında dict
        """
        self.kalemler.clear()
        self._sira_sayac = 0

        baslik = data.get('baslik', {})
        self.proje_adi = baslik.get('proje_adi', '')
        self.ihale_no = baslik.get('ihale_no', '')
        self.idare = baslik.get('idare', '')

        ozet = data.get('ozet', {})
        kdv_orani_val = ozet.get('kdv_orani', 20.0)
        self.kdv_orani = Decimal(str(kdv_orani_val))

        for k in data.get('kalemler', []):
            self._sira_sayac += 1
            kalem = YaklasikMaliyetKalemi(
                sira_no=k.get('sira_no', self._sira_sayac),
                poz_no=k.get('poz_no', ''),
                tanim=k.get('tanim', ''),
                birim=k.get('birim', 'adet'),
                miktar=Decimal(str(k.get('miktar', 0))),
                birim_fiyat=Decimal(str(k.get('birim_fiyat', 0))),
                kurum=k.get('kurum', self.kurum),
                aciklama=k.get('aciklama', ''),
            )
            self.kalemler.append(kalem)

        logger.info(
            "import_json: %d kalem yüklendi (%s)",
            len(self.kalemler), self.proje_adi,
        )

    def to_excel_rows(self) -> List[List[Any]]:
        """
        Excel export için satır listesi döndür.

        Her satır: [Sıra, Poz No, Tanım, Birim, Miktar, Birim Fiyat, Tutar]

        Returns:
            List[List[Any]]
        """
        return [
            [
                k.sira_no,
                k.poz_no,
                k.tanim,
                k.birim,
                float(k.miktar),
                float(k.birim_fiyat),
                float(k.tutar),
            ]
            for k in self.kalemler
        ]

    # ==================================================================
    # PDF EXPORT
    # ==================================================================

    def pdf_kesif_ozeti_uret(self, dosya_yolu: str) -> bool:
        """
        4734 uyumlu resmi keşif özeti PDF üretir.

        Neyi çözüyoruz:
            İhale dosyasına eklenecek resmi keşif özeti belgesi.
            Word/Excel yerine PDF — onay zincirinde kurumsal görünüm.

        Nasıl test ederiz:
            Birkaç kalem ekle, dosya_yolu ver, True dönmeli ve PDF açılmalı.

        Args:
            dosya_yolu: Kaydedilecek PDF'in tam yolu (.pdf uzantılı)

        Returns:
            True  — PDF başarıyla oluşturuldu
            False — reportlab yoksa veya yazma hatası oluştu
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import cm
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, HRFlowable,
            )
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        except Exception:
            logger.error("reportlab kütüphanesi bulunamadı — PDF üretilemiyor")
            return False

        try:
            # ------------------------------------------------------------------
            # DEĞERLER
            # ------------------------------------------------------------------
            toplam    = self.toplam_hesapla()
            kdv       = self.kdv_hesapla()
            genel     = self.genel_toplam()
            sinir     = self.asiri_dusuk_siniri()
            tarih_str = datetime.now().strftime("%d.%m.%Y")

            def _para(d: Decimal) -> str:
                """Türk lirası formatı: 1.234.567,89 TL"""
                s = f"{float(d):,.2f} TL"
                return s.replace(",", "X").replace(".", ",").replace("X", ".")

            # ------------------------------------------------------------------
            # SAYFA AYARI
            # ------------------------------------------------------------------
            doc = SimpleDocTemplate(
                dosya_yolu,
                pagesize=A4,
                rightMargin=1.8 * cm,
                leftMargin=1.8 * cm,
                topMargin=1.5 * cm,
                bottomMargin=1.5 * cm,
            )

            styles = getSampleStyleSheet()

            st_baslik = ParagraphStyle(
                "Baslik",
                parent=styles["Normal"],
                fontSize=14,
                fontName=_PDF_FONT_BOLD,
                alignment=TA_CENTER,
                spaceAfter=4,
            )
            st_alt_baslik = ParagraphStyle(
                "AltBaslik",
                parent=styles["Normal"],
                fontSize=10,
                fontName=_PDF_FONT,
                alignment=TA_CENTER,
                spaceAfter=2,
            )
            st_meta_sol = ParagraphStyle(
                "MetaSol",
                parent=styles["Normal"],
                fontSize=9,
                fontName=_PDF_FONT,
                alignment=TA_LEFT,
            )
            st_meta_sag = ParagraphStyle(
                "MetaSag",
                parent=styles["Normal"],
                fontSize=9,
                fontName=_PDF_FONT,
                alignment=TA_RIGHT,
            )
            st_not = ParagraphStyle(
                "Not",
                parent=styles["Normal"],
                fontSize=8,
                fontName=_PDF_FONT,
                textColor=colors.HexColor("#555555"),
                alignment=TA_LEFT,
            )
            st_imza = ParagraphStyle(
                "Imza",
                parent=styles["Normal"],
                fontSize=9,
                fontName=_PDF_FONT,
                alignment=TA_RIGHT,
            )

            # ------------------------------------------------------------------
            # BAŞLIK BLOĞU
            # ------------------------------------------------------------------
            story = []

            idare_str   = self.idare or "İdare Adı Girilmedi"
            proje_str   = self.proje_adi or "Proje Adı Girilmedi"
            ihale_str   = self.ihale_no or "—"

            # Üst satır: idare (sol) — tarih (sağ)
            ust_data = [[
                Paragraph(idare_str, st_meta_sol),
                Paragraph("Tarih: " + tarih_str, st_meta_sag),
            ]]
            ust_tablo = Table(ust_data, colWidths=[9 * cm, 8.14 * cm])
            ust_tablo.setStyle(TableStyle([
                ("VALIGN",     (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(ust_tablo)
            story.append(Spacer(1, 0.3 * cm))

            story.append(Paragraph("YAKLAŞIK MALİYET (KEŞİF ÖZETİ)", st_baslik))
            story.append(Paragraph(proje_str, st_alt_baslik))

            # Alt başlık: ihale no
            if ihale_str != "—":
                story.append(Paragraph("İhale No: " + ihale_str, st_alt_baslik))

            story.append(Spacer(1, 0.4 * cm))
            story.append(HRFlowable(width="100%", thickness=1,
                                    color=colors.HexColor("#003366")))
            story.append(Spacer(1, 0.4 * cm))

            # ------------------------------------------------------------------
            # KALEM TABLOSU
            # ------------------------------------------------------------------
            sayfa_genislik = A4[0] - 3.6 * cm   # iki kenar margin
            col_widths = [
                1.0 * cm,   # Sıra No
                2.2 * cm,   # Poz No
                6.5 * cm,   # Tanım
                1.4 * cm,   # Birim
                2.0 * cm,   # Miktar
                3.2 * cm,   # Birim Fiyat
                3.2 * cm,   # Tutar
            ]

            tablo_data = []

            # Başlık satırı
            baslik_satir = [
                Paragraph("<b>Sıra\nNo</b>",    ParagraphStyle("th", parent=styles["Normal"], fontSize=8, fontName=_PDF_FONT_BOLD, alignment=TA_CENTER)),
                Paragraph("<b>Poz No</b>",       ParagraphStyle("th", parent=styles["Normal"], fontSize=8, fontName=_PDF_FONT_BOLD, alignment=TA_CENTER)),
                Paragraph("<b>Tanım</b>",         ParagraphStyle("th", parent=styles["Normal"], fontSize=8, fontName=_PDF_FONT_BOLD, alignment=TA_LEFT)),
                Paragraph("<b>Birim</b>",         ParagraphStyle("th", parent=styles["Normal"], fontSize=8, fontName=_PDF_FONT_BOLD, alignment=TA_CENTER)),
                Paragraph("<b>Miktar</b>",        ParagraphStyle("th", parent=styles["Normal"], fontSize=8, fontName=_PDF_FONT_BOLD, alignment=TA_RIGHT)),
                Paragraph("<b>Birim\nFiyat (TL)</b>", ParagraphStyle("th", parent=styles["Normal"], fontSize=8, fontName=_PDF_FONT_BOLD, alignment=TA_RIGHT)),
                Paragraph("<b>Tutar (TL)</b>",   ParagraphStyle("th", parent=styles["Normal"], fontSize=8, fontName=_PDF_FONT_BOLD, alignment=TA_RIGHT)),
            ]
            tablo_data.append(baslik_satir)

            # Kalem satırları
            st_td = ParagraphStyle("td", parent=styles["Normal"], fontSize=8, fontName=_PDF_FONT)
            st_td_r = ParagraphStyle("td_r", parent=styles["Normal"], fontSize=8, fontName=_PDF_FONT, alignment=TA_RIGHT)
            st_td_c = ParagraphStyle("td_c", parent=styles["Normal"], fontSize=8, fontName=_PDF_FONT, alignment=TA_CENTER)

            for k in self.kalemler:
                tutar_val = float(k.tutar)
                satir = [
                    Paragraph(str(k.sira_no), st_td_c),
                    Paragraph(k.poz_no, st_td_c),
                    Paragraph(k.tanim, st_td),
                    Paragraph(k.birim, st_td_c),
                    Paragraph(f"{float(k.miktar):,.3f}".replace(",", "X").replace(".", ",").replace("X", "."), st_td_r),
                    Paragraph(_para(k.birim_fiyat), st_td_r),
                    Paragraph(_para(k.tutar), st_td_r),
                ]
                tablo_data.append(satir)

            # Özet satırları
            st_ozet_etiket = ParagraphStyle("ozet_e", parent=styles["Normal"], fontSize=9, fontName=_PDF_FONT_BOLD, alignment=TA_RIGHT)
            st_ozet_deger  = ParagraphStyle("ozet_d", parent=styles["Normal"], fontSize=9, fontName=_PDF_FONT_BOLD, alignment=TA_RIGHT)
            st_ozet_deger_buyuk = ParagraphStyle("ozet_db", parent=styles["Normal"], fontSize=10, fontName=_PDF_FONT_BOLD, alignment=TA_RIGHT)
            st_ozet_kirmizi = ParagraphStyle("ozet_k", parent=styles["Normal"], fontSize=9, fontName=_PDF_FONT_BOLD, alignment=TA_RIGHT, textColor=colors.HexColor("#cc0000"))

            ozet_satirlar = [
                # [birleştirme metni, tutar, stil]
                ("TOPLAM YAPIM BEDELİ",                 _para(toplam),  st_ozet_deger),
                (f"KDV (%{int(self.kdv_orani)})",        _para(kdv),     st_ozet_deger),
                ("GENEL TOPLAM (KDV DAHİL)",             _para(genel),   st_ozet_deger_buyuk),
                ("KİK md.38 AŞIRI DÜŞÜK SINIR (%80)",   _para(sinir),   st_ozet_kirmizi),
            ]

            for etiket, deger, stil in ozet_satirlar:
                satir = [
                    "",
                    Paragraph(etiket, st_ozet_etiket),
                    Paragraph(deger, stil),
                ]
                tablo_data.append(satir)

            # Tablo oluştur — özet satırları için SPAN (ilk 5 sütun birleşir)
            n_kalem = len(self.kalemler)
            n_total = len(tablo_data)

            kalem_tablosu = Table(tablo_data, colWidths=col_widths, repeatRows=1)

            tablo_stili_cmds = [
                # Genel
                ("FONTNAME",    (0, 0), (-1, 0),           _PDF_FONT_BOLD),
                ("FONTSIZE",    (0, 0), (-1, -1),          8),
                ("BACKGROUND",  (0, 0), (-1, 0),           colors.HexColor("#003366")),
                ("TEXTCOLOR",   (0, 0), (-1, 0),           colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, n_kalem),
                 [colors.HexColor("#f2f6ff"), colors.white]),
                ("GRID",        (0, 0), (-1, n_kalem),     0.4, colors.HexColor("#cccccc")),
                ("VALIGN",      (0, 0), (-1, -1),          "MIDDLE"),
                ("TOPPADDING",  (0, 0), (-1, -1),          3),
                ("BOTTOMPADDING", (0, 0), (-1, -1),        3),
                # Özet satırları (n_kalem+1 → son)
                ("BACKGROUND",  (0, n_kalem + 1), (-1, -1), colors.HexColor("#eef2f8")),
                ("LINEABOVE",   (0, n_kalem + 1), (-1, n_kalem + 1), 1, colors.HexColor("#003366")),
                ("LINEBELOW",   (0, -1), (-1, -1),         1, colors.HexColor("#003366")),
            ]

            # Özet satırlarında ilk 5 sütunu birleştir
            for i, idx in enumerate(range(n_kalem + 1, n_total)):
                tablo_stili_cmds.append(("SPAN", (0, idx), (4, idx)))

            kalem_tablosu.setStyle(TableStyle(tablo_stili_cmds))
            story.append(kalem_tablosu)
            story.append(Spacer(1, 0.6 * cm))

            # ------------------------------------------------------------------
            # ALT NOTLAR
            # ------------------------------------------------------------------
            story.append(HRFlowable(width="100%", thickness=0.5,
                                    color=colors.HexColor("#aaaaaa")))
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph(
                "Bu keşif özeti 4734 sayılı Kamu İhale Kanunu kapsamında hazırlanmıştır.",
                st_not,
            ))
            story.append(Paragraph(
                "Fiyatlar yaklaşık olup ihale öncesi güncellenmelidir.",
                st_not,
            ))
            story.append(Spacer(1, 1.0 * cm))

            # İmza satırı
            imza_data = [[
                Paragraph("", st_imza),
                Paragraph("İdare Yetkilisi\n\n\n_________________________", st_imza),
            ]]
            imza_tablo = Table(imza_data, colWidths=[10 * cm, 7.14 * cm])
            imza_tablo.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(imza_tablo)

            # ------------------------------------------------------------------
            # PDF OLUŞTUR
            # ------------------------------------------------------------------
            doc.build(story)
            logger.info("PDF keşif özeti oluşturuldu: %s", dosya_yolu)
            return True

        except Exception as exc:
            logger.error("PDF üretim hatası: %s", exc, exc_info=True)
            return False

    # ==================================================================
    # YARDIMCI
    # ==================================================================

    def __repr__(self) -> str:
        return (
            f"YaklasikMaliyetEngine("
            f"kalem={len(self.kalemler)}, "
            f"toplam={float(self.toplam_hesapla()):,.2f} TL, "
            f"genel={float(self.genel_toplam()):,.2f} TL)"
        )
