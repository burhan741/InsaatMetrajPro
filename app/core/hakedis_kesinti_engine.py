"""
Hakediş Kesinti ve Mahsup Hesabı — Engine
==========================================
4734 Kamu İhale Kanunu + 4735 Kamu İhale Sözleşmeleri Kanunu

Kesinti kalemleri:
1. Avans mahsubu — sözleşme/hakediş avans oranı × brüt hakediş
2. Kesin teminat kesintisi — %6 (sözleşme bedelinin tamamlanana dek)
3. Damga vergisi — %0.948 (488 sayılı DVK IV/1 Cetvel)
4. Gelir vergisi stopajı — %3 (GVK Geçici md.67 kapsam dışı yapım işi)
5. SGK prim kesintisi — %1 (5510 md.85 — asgari işçilik fark primi)
6. Gecikme cezası mahsubu — sözleşme bedeli × ‰5 (%0.5) × gün sayısı
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List
from datetime import date

logger = logging.getLogger(__name__)

try:
    from app.utils.font_utils import get_fonts as _get_fonts
    _PDF_FONT, _PDF_FONT_BOLD = _get_fonts()
except Exception:
    _PDF_FONT, _PDF_FONT_BOLD = _PDF_FONT, _PDF_FONT_BOLD

# ---------------------------------------------------------------------------
# Sabitler (mevzuat kaynakları)
# ---------------------------------------------------------------------------

KESIN_TEMINAT_ORANI = Decimal("0.06")       # 4735 md.13
DAMGA_VERGISI_ORANI = Decimal("0.00948")    # 488 sayılı DVK — yapım işi
GELIR_VERGISI_STOPAJ = Decimal("0.03")      # GVK Geçici md.67
SGK_PRIM_KESINTI_ORANI = Decimal("0.01")    # 5510 md.85 — asgari işçilik
GUNLUK_GECIKME_ORANI = Decimal("0.005")     # 4735 md.20 — binde beş (%0.5) günlük
FESIH_ESIGI_ORANI = Decimal("0.30")         # toplam ceza %30'u aşarsa fesih


# ---------------------------------------------------------------------------
# Veri sınıfları
# ---------------------------------------------------------------------------

@dataclass
class HakedisKesintiBilgisi:
    """Tekil bir hakediş dönemine ait tüm bilgiler."""

    # Genel bilgiler
    sozlesme_bedeli: Decimal = Decimal("0")
    hakedis_no: int = 1
    hakedis_tarihi: Optional[date] = None

    # Brüt hakediş (imalat bedeli)
    brut_hakedis: Decimal = Decimal("0")

    # Önceki dönemlere ait birikimli hakediş
    onceki_hakedis_toplami: Decimal = Decimal("0")

    # Avans bilgileri
    avans_orani: Decimal = Decimal("0.30")      # sözleşme bedelinin %30'u tipik
    verilen_avans: Decimal = Decimal("0")        # nakit ödenen avans tutarı
    onceki_avans_mahsubu: Decimal = Decimal("0")  # önceki hakedişlerde kesilen avans

    # Kesin teminat — sözleşme bedelinin %6'sı tamamlanana kadar kesilir
    kesin_teminat_tamamlandi: bool = False       # limit dolmuşsa daha fazla kesilmez

    # Gecikme
    gecikme_gun: int = 0

    # SGK prim kesintisi aktif mi?
    sgk_kesinti_aktif: bool = True

    # GV stopaj aktif mi? (bazı kamu yapım işlerinde muafiyet var)
    gv_stopaj_aktif: bool = True


@dataclass
class HakedisKesintleri:
    """Hesaplama sonucu — her kalem ayrıştırılmış."""

    brut_hakedis: Decimal = Decimal("0")

    avans_mahsubu: Decimal = Decimal("0")
    kesin_teminat: Decimal = Decimal("0")
    damga_vergisi: Decimal = Decimal("0")
    gelir_vergisi: Decimal = Decimal("0")
    sgk_prim: Decimal = Decimal("0")
    gecikme_cezasi: Decimal = Decimal("0")

    toplam_kesinti: Decimal = Decimal("0")
    net_odeme: Decimal = Decimal("0")

    # Uyarı mesajları
    uyarilar: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ana engine
# ---------------------------------------------------------------------------

class HakedisKesintEngine:
    """
    Kamu yapım işi hakediş kesintilerini hesaplar.

    Kullanım:
        engine = HakedisKesintEngine()
        bilgi = HakedisKesintiBilgisi(
            sozlesme_bedeli=Decimal("10_000_000"),
            brut_hakedis=Decimal("1_500_000"),
            verilen_avans=Decimal("3_000_000"),
            gecikme_gun=0,
        )
        sonuc = engine.hesapla(bilgi)
        print(sonuc.net_odeme)
    """

    # ------------------------------------------------------------------
    # Yardımcı — yuvarlama
    # ------------------------------------------------------------------

    def _round2(self, val: Decimal) -> Decimal:
        """2 ondalık basamağa yuvarla (ROUND_HALF_UP)."""
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # ------------------------------------------------------------------
    # Ana hesap
    # ------------------------------------------------------------------

    def hesapla(self, bilgi: HakedisKesintiBilgisi) -> HakedisKesintleri:
        """Tüm kesintileri hesaplayıp HakedisKesintleri döner."""
        sonuc = HakedisKesintleri(brut_hakedis=bilgi.brut_hakedis)
        brut = bilgi.brut_hakedis

        # 1. Avans mahsubu
        sonuc.avans_mahsubu = self._hesapla_avans_mahsubu(bilgi)

        # 2. Kesin teminat
        sonuc.kesin_teminat = self._hesapla_kesin_teminat(bilgi)

        # 3. Damga vergisi (brüt hakediş üzerinden)
        sonuc.damga_vergisi = self._round2(brut * DAMGA_VERGISI_ORANI)

        # 4. Gelir vergisi stopajı
        if bilgi.gv_stopaj_aktif:
            sonuc.gelir_vergisi = self._round2(brut * GELIR_VERGISI_STOPAJ)
        else:
            sonuc.gelir_vergisi = Decimal("0")
            sonuc.uyarilar.append("Gelir vergisi stopajı muafiyet kapsamında uygulanmadı.")

        # 5. SGK prim kesintisi
        if bilgi.sgk_kesinti_aktif:
            sonuc.sgk_prim = self._round2(brut * SGK_PRIM_KESINTI_ORANI)
        else:
            sonuc.sgk_prim = Decimal("0")

        # 6. Gecikme cezası
        sonuc.gecikme_cezasi = self._hesapla_gecikme(bilgi)

        # Toplam ve net
        toplam = (
            sonuc.avans_mahsubu
            + sonuc.kesin_teminat
            + sonuc.damga_vergisi
            + sonuc.gelir_vergisi
            + sonuc.sgk_prim
            + sonuc.gecikme_cezasi
        )
        sonuc.toplam_kesinti = self._round2(toplam)
        sonuc.net_odeme = self._round2(brut - toplam)

        # Uyarılar
        self._ekle_uyarilar(bilgi, sonuc)

        return sonuc

    # ------------------------------------------------------------------
    # Alt hesaplar
    # ------------------------------------------------------------------

    def _hesapla_avans_mahsubu(self, bilgi: HakedisKesintiBilgisi) -> Decimal:
        """
        Avans mahsup oranı = (verilen avans) / (sözleşme bedeli).
        Her hakediş döneminde bu oran × brüt hakediş kadar mahsup edilir.
        Kalan avans = verilen avans − önceki mahsuplar.
        """
        if bilgi.verilen_avans <= 0:
            return Decimal("0")

        kalan_avans = bilgi.verilen_avans - bilgi.onceki_avans_mahsubu
        if kalan_avans <= 0:
            return Decimal("0")

        # Oran bazlı mahsup (avans oranı doğrudan kullanılır)
        mahsup = self._round2(bilgi.brut_hakedis * bilgi.avans_orani)

        # Kalan avansı aşamaz
        mahsup = min(mahsup, kalan_avans)
        return mahsup

    def _hesapla_kesin_teminat(self, bilgi: HakedisKesintiBilgisi) -> Decimal:
        """
        4735 md.13: Her hakediş döneminde %6 oranında kesin teminat kesilir.
        Toplam kesilen kesin teminat sözleşme bedelinin %6'sına ulaşınca
        daha fazla kesilmez.
        """
        if bilgi.kesin_teminat_tamamlandi:
            return Decimal("0")
        return self._round2(bilgi.brut_hakedis * KESIN_TEMINAT_ORANI)

    def _hesapla_gecikme(self, bilgi: HakedisKesintiBilgisi) -> Decimal:
        """4735 md.20: günlük ‰5 (%0.5, binde beş) gecikme cezası."""
        if bilgi.gecikme_gun <= 0:
            return Decimal("0")
        ceza = self._round2(
            bilgi.sozlesme_bedeli
            * GUNLUK_GECIKME_ORANI
            * Decimal(str(bilgi.gecikme_gun))
        )
        return ceza

    def _ekle_uyarilar(
        self, bilgi: HakedisKesintiBilgisi, sonuc: HakedisKesintleri
    ) -> None:
        """Sonuca uyarı mesajları ekler."""
        # Net ödeme negatifse uyar
        if sonuc.net_odeme < 0:
            sonuc.uyarilar.append(
                f"Net ödeme negatif ({float(sonuc.net_odeme):,.2f} TL). "
                "Kesintiler brüt hakediş tutarını aşıyor."
            )

        # Gecikme cezası fesih eşiğine yaklaşıyorsa uyar
        if bilgi.gecikme_gun > 0:
            gecikme_toplam_oran = (
                GUNLUK_GECIKME_ORANI * Decimal(str(bilgi.gecikme_gun))
            )
            if gecikme_toplam_oran >= FESIH_ESIGI_ORANI * Decimal("0.80"):
                sonuc.uyarilar.append(
                    f"Gecikme cezası sözleşme bedelinin %30 fesih eşiğine "
                    f"yaklaşıyor ({float(gecikme_toplam_oran * 100):.1f}%)."
                )
            if gecikme_toplam_oran >= FESIH_ESIGI_ORANI:
                sonuc.uyarilar.append(
                    "DİKKAT: Gecikme cezası %30 fesih eşiğini AŞTI! "
                    "4735 md.20 gereği sözleşme feshedilebilir."
                )

    # ------------------------------------------------------------------
    # Raporlama yardımcıları
    # ------------------------------------------------------------------

    def ozet_dict(
        self, bilgi: HakedisKesintiBilgisi, sonuc: HakedisKesintleri
    ) -> dict:
        """Excel/PDF için düz sözlük (satır listesi dahil)."""
        return {
            "hakedis_no": bilgi.hakedis_no,
            "tarih": str(bilgi.hakedis_tarihi or ""),
            "sozlesme_bedeli": float(bilgi.sozlesme_bedeli),
            "brut_hakedis": float(sonuc.brut_hakedis),
            "avans_mahsubu": float(sonuc.avans_mahsubu),
            "kesin_teminat": float(sonuc.kesin_teminat),
            "damga_vergisi": float(sonuc.damga_vergisi),
            "gelir_vergisi": float(sonuc.gelir_vergisi),
            "sgk_prim": float(sonuc.sgk_prim),
            "gecikme_cezasi": float(sonuc.gecikme_cezasi),
            "toplam_kesinti": float(sonuc.toplam_kesinti),
            "net_odeme": float(sonuc.net_odeme),
            "uyarilar": sonuc.uyarilar,
            "satirlar": [
                ("Brüt Hakediş Tutarı", float(sonuc.brut_hakedis), ""),
                ("(–) Avans Mahsubu", -float(sonuc.avans_mahsubu), ""),
                ("(–) Kesin Teminat Kesintisi", -float(sonuc.kesin_teminat), "%6"),
                ("(–) Damga Vergisi", -float(sonuc.damga_vergisi), "%0.948"),
                ("(–) Gelir Vergisi Stopajı", -float(sonuc.gelir_vergisi), "%3"),
                ("(–) SGK Prim Kesintisi", -float(sonuc.sgk_prim), "%1"),
                (
                    "(–) Gecikme Cezası",
                    -float(sonuc.gecikme_cezasi),
                    f"{bilgi.gecikme_gun} gün",
                ),
                ("NET ÖDENECEKLERİ MİKTAR", float(sonuc.net_odeme), ""),
            ],
        }

    def to_excel_rows(
        self, bilgi: HakedisKesintiBilgisi, sonuc: HakedisKesintleri
    ) -> list:
        """Excel tablosu için satır listesi."""
        return self.ozet_dict(bilgi, sonuc)["satirlar"]

    # ------------------------------------------------------------------
    # Kesin teminat limit kontrolü (harici çağrı)
    # ------------------------------------------------------------------

    def kesin_teminat_limit_doldu_mu(
        self, sozlesme_bedeli: Decimal, toplam_kesilen_kt: Decimal
    ) -> bool:
        """
        Önceki hakedişlerde kesilen toplam kesin teminat,
        sözleşme bedelinin %6'sına ulaştıysa True döner.
        """
        limit = self._round2(sozlesme_bedeli * KESIN_TEMINAT_ORANI)
        return toplam_kesilen_kt >= limit

    # ------------------------------------------------------------------
    # PDF belgesi üretimi
    # ------------------------------------------------------------------

    def pdf_hakedis_belgesi_uret(
        self,
        bilgi: HakedisKesintiBilgisi,
        sonuc: HakedisKesintleri,
        dosya_yolu: str,
        proje_adi: str = "",
        idare_adi: str = "",
        firma_adi: str = "",
        sozlesme_no: str = "",
        imalat_satirlari: Optional[list] = None,
    ) -> bool:
        """
        reportlab ile resmi hakediş belgesi PDF'i üretir.
        Başarılıysa True, hata varsa False döner.
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        except ImportError:
            logger.error("reportlab kurulu değil — PDF üretilemedi.")
            return False

        try:
            styles = getSampleStyleSheet()
            baslik_stili = ParagraphStyle(
                "Baslik",
                parent=styles["Heading1"],
                alignment=TA_CENTER,
                fontSize=14,
                spaceAfter=6,
            )
            alt_baslik_stili = ParagraphStyle(
                "AltBaslik",
                parent=styles["Normal"],
                alignment=TA_CENTER,
                fontSize=11,
                spaceAfter=4,
            )
            normal = styles["Normal"]
            normal.fontSize = 9

            doc = SimpleDocTemplate(
                dosya_yolu,
                pagesize=A4,
                rightMargin=1.5 * cm,
                leftMargin=1.5 * cm,
                topMargin=2 * cm,
                bottomMargin=2 * cm,
            )
            story = []

            # Başlık
            story.append(Paragraph("KAMU YAPIM İŞİ HAKEDİŞ BELGESİ", baslik_stili))
            tarih_str = (
                bilgi.hakedis_tarihi.strftime("%d/%m/%Y")
                if bilgi.hakedis_tarihi
                else "—"
            )
            story.append(
                Paragraph(
                    f"Hakediş No: {bilgi.hakedis_no}   |   Tarih: {tarih_str}",
                    alt_baslik_stili,
                )
            )
            story.append(Spacer(1, 0.4 * cm))

            # Proje / İdare / Firma bilgileri
            bilgi_data = [
                ["Proje Adı", proje_adi or "—"],
                ["Sözleşme No", sozlesme_no or "—"],
                ["İdare Adı", idare_adi or "—"],
                ["Müteahhit / Firma", firma_adi or "—"],
                [
                    "Sözleşme Bedeli (TL)",
                    f"{float(bilgi.sozlesme_bedeli):,.2f}",
                ],
            ]
            bilgi_tablo = Table(bilgi_data, colWidths=[5 * cm, 12 * cm])
            bilgi_tablo.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), _PDF_FONT),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("FONTNAME", (0, 0), (0, -1), _PDF_FONT_BOLD),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ROWBACKGROUND", (0, 0), (-1, -1), [colors.white, colors.whitesmoke]),
                    ]
                )
            )
            story.append(bilgi_tablo)
            story.append(Spacer(1, 0.5 * cm))

            # İmalat kalemleri tablosu
            if imalat_satirlari:
                story.append(Paragraph("İMALAT KALEMLERİ", styles["Heading2"]))
                im_baslik = [
                    "Sıra", "Poz No", "Tanım", "Birim",
                    "Sözl. Miktar", "Gerç. Miktar", "B.Fiyat (TL)", "Tutar (TL)",
                ]
                im_data = [im_baslik] + imalat_satirlari
                im_tablo = Table(
                    im_data,
                    colWidths=[0.8*cm, 1.5*cm, 5.5*cm, 1.2*cm, 1.8*cm, 1.8*cm, 2*cm, 2.4*cm],
                )
                im_tablo.setStyle(
                    TableStyle(
                        [
                            ("FONTNAME", (0, 0), (-1, 0), _PDF_FONT_BOLD),
                            ("FONTNAME", (0, 1), (-1, -1), _PDF_FONT),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
                            ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.white, colors.whitesmoke]),
                        ]
                    )
                )
                story.append(im_tablo)
                story.append(Spacer(1, 0.5 * cm))

            # Kesinti cetveli
            story.append(Paragraph("KESİNTİ CETVELİ", styles["Heading2"]))
            kesinti_data = [
                ["Kesinti Kalemi", "Oran / Gün", "Tutar (TL)"],
                ["Brüt Hakediş Tutarı", "—", f"{float(sonuc.brut_hakedis):,.2f}"],
                ["(–) Avans Mahsubu", f"%{float(bilgi.avans_orani * 100):.0f}", f"-{float(sonuc.avans_mahsubu):,.2f}"],
                ["(–) Kesin Teminat Kesintisi", "%6", f"-{float(sonuc.kesin_teminat):,.2f}"],
                ["(–) Damga Vergisi", "%0.948", f"-{float(sonuc.damga_vergisi):,.2f}"],
                ["(–) Gelir Vergisi Stopajı", "%3", f"-{float(sonuc.gelir_vergisi):,.2f}"],
                ["(–) SGK Prim Kesintisi", "%1", f"-{float(sonuc.sgk_prim):,.2f}"],
                [
                    "(–) Gecikme Cezası",
                    f"{bilgi.gecikme_gun} gün × ‰5",
                    f"-{float(sonuc.gecikme_cezasi):,.2f}",
                ],
                ["TOPLAM KESİNTİ", "—", f"-{float(sonuc.toplam_kesinti):,.2f}"],
                ["NET ÖDEME", "—", f"{float(sonuc.net_odeme):,.2f}"],
            ]
            kesinti_tablo = Table(kesinti_data, colWidths=[8 * cm, 4 * cm, 5 * cm])
            kesinti_tablo.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, 0), _PDF_FONT_BOLD),
                        ("FONTNAME", (0, 1), (-1, -2), _PDF_FONT),
                        ("FONTNAME", (0, -1), (-1, -1), _PDF_FONT_BOLD),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#27ae60")),
                        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
                        ("BACKGROUND", (0, -2), (-1, -2), colors.HexColor("#e74c3c")),
                        ("TEXTCOLOR", (0, -2), (-1, -2), colors.white),
                        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                        ("ROWBACKGROUND", (0, 1), (-1, -3), [colors.white, colors.whitesmoke]),
                    ]
                )
            )
            story.append(kesinti_tablo)
            story.append(Spacer(1, 1 * cm))

            # Uyarılar
            if sonuc.uyarilar:
                story.append(Paragraph("UYARILAR", styles["Heading3"]))
                for uyari in sonuc.uyarilar:
                    story.append(Paragraph(f"• {uyari}", normal))
                story.append(Spacer(1, 0.5 * cm))

            # İmza bölümü
            imza_data = [
                ["İdare Yetkilisi", "Kontrol Mühendisi", "Müteahhit / Firma"],
                ["", "", ""],
                ["Ad Soyad / İmza / Tarih", "Ad Soyad / İmza / Tarih", "Ad Soyad / İmza / Tarih"],
            ]
            imza_tablo = Table(imza_data, colWidths=[5.5 * cm, 5.5 * cm, 6 * cm])
            imza_tablo.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), _PDF_FONT),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("FONTNAME", (0, 0), (-1, 0), _PDF_FONT_BOLD),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("ROWHEIGHT", (0, 1), (0, 1), 60),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(imza_tablo)

            doc.build(story)
            logger.info("PDF belgesi üretildi: %s", dosya_yolu)
            return True

        except Exception as exc:
            logger.error("PDF üretim hatası: %s", exc)
            return False
