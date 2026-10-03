"""
Teminat Yönetimi — Engine
===========================
4734 sayılı Kamu İhale Kanunu + 4735 Kamu İhale Sözleşmeleri Kanunu

Teminat türleri:
  Geçici Teminat   : ihale bedelinin %3'ü   (4734 md.33)
  Kesin Teminat    : sözleşme bedelinin %6'sı (4735 md.13)
  Ek Kesin Teminat : aşırı düşük teklif farkının %6'sı

Rev-79 (2026-04-26): 1-space cascade indentation → 4-space PEP8 (tamamen yeniden yazıldı)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Optional, List, Tuple


GECICI_TEMINAT_ORANI = Decimal("0.03")    # %3
KESIN_TEMINAT_ORANI  = Decimal("0.06")    # %6

TEMINAT_TURLERI = ["Teminat Mektubu", "Nakit", "Devlet Tahvili", "Hazine Bonosu"]

IADE_KOSULLARI = {
    "gecici":   "İhalenin kesinleşmesinden sonra iadeye esas karar verilir (4734 md.33).",
    "kesin":    "Kesin kabulden sonra iade edilir. Eksik imalat / ceza yoksa tam iade (4735 md.13).",
    "ek_kesin": "Kesin kabulden sonra, diğer kesin teminata eklenerek iade edilir.",
}


# ── Veri sınıfları ────────────────────────────────────────────────────────────

@dataclass
class TeminatMektubu:
    """Takip edilen bir teminat mektubu kaydı."""
    tur:             str                # "gecici" | "kesin" | "ek_kesin"
    banka_adi:       str
    mektup_no:       str
    tutar:           Decimal
    vade_tarihi:     date
    verilme_tarihi:  date = field(default_factory=date.today)
    iade_tarihi:     Optional[date] = None
    notlar:          str = ""

    @property
    def iade_edildi_mi(self) -> bool:
        return self.iade_tarihi is not None

    @property
    def kalan_gun(self) -> int:
        """Vadeye kaç gün kaldı (negatif = vadesi geçmiş)."""
        return (self.vade_tarihi - date.today()).days


@dataclass
class TeminatHesapSonucu:
    """Teminat hesabı çıktıları."""
    ihale_bedeli:           Decimal = Decimal("0")
    sozlesme_bedeli:        Decimal = Decimal("0")
    asiri_dusuk_fark:       Decimal = Decimal("0")

    gecici_teminat:         Decimal = Decimal("0")
    kesin_teminat:          Decimal = Decimal("0")
    ek_kesin_teminat:       Decimal = Decimal("0")
    toplam_zorunlu_teminat: Decimal = Decimal("0")

    uyarilar: List[str] = field(default_factory=list)


# ── Motor ─────────────────────────────────────────────────────────────────────

class TeminatEngine:
    """
    Teminat hesabı ve takip yönetimi.

    Kullanım:
        engine = TeminatEngine()
        sonuc = engine.hesapla(
            ihale_bedeli    = Decimal("15_000_000"),
            sozlesme_bedeli = Decimal("12_000_000"),
            asiri_dusuk_fark= Decimal("2_500_000"),
        )
    """

    @staticmethod
    def _round2(v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # ── Teminat hesabı ────────────────────────────────────────────────────────

    def hesapla(
        self,
        ihale_bedeli:     Decimal,
        sozlesme_bedeli:  Decimal,
        asiri_dusuk_fark: Decimal = Decimal("0"),
    ) -> TeminatHesapSonucu:
        """
        Geçici, kesin ve ek kesin teminat tutarlarını hesaplar.
        """
        sonuc = TeminatHesapSonucu(
            ihale_bedeli    = ihale_bedeli,
            sozlesme_bedeli = sozlesme_bedeli,
            asiri_dusuk_fark= asiri_dusuk_fark,
        )

        sonuc.gecici_teminat    = self._round2(ihale_bedeli * GECICI_TEMINAT_ORANI)
        sonuc.kesin_teminat     = self._round2(sozlesme_bedeli * KESIN_TEMINAT_ORANI)
        sonuc.ek_kesin_teminat  = self._round2(asiri_dusuk_fark * KESIN_TEMINAT_ORANI)
        sonuc.toplam_zorunlu_teminat = self._round2(
            sonuc.kesin_teminat + sonuc.ek_kesin_teminat
        )

        self._ekle_uyarilar(sonuc)
        return sonuc

    def _ekle_uyarilar(self, sonuc: TeminatHesapSonucu) -> None:
        if sonuc.ek_kesin_teminat > 0:
            sonuc.uyarilar.append(
                f"Ek kesin teminat uygulanıyor: "
                f"{float(sonuc.ek_kesin_teminat):,.2f} TL "
                "(Aşırı düşük teklif farkının %6'sı — 4735 md.13/3)."
            )
        if (sonuc.sozlesme_bedeli > 0
                and sonuc.sozlesme_bedeli < sonuc.ihale_bedeli * Decimal("0.80")):
            sonuc.uyarilar.append(
                "Sözleşme bedeli yaklaşık maliyetin %80'inin altında. "
                "Aşırı düşük teklif incelemesi yapıldığından emin olun (4734 md.38)."
            )

    # ── Vade kontrolü ─────────────────────────────────────────────────────────

    def vade_uyari_listesi(
        self,
        mektuplar: List[TeminatMektubu],
        uyari_gun: int = 30,
    ) -> List[Tuple[TeminatMektubu, str]]:
        """
        Vadesi uyari_gun içinde dolacak veya geçmiş mektupları döner.
        Returns: [(mektup, uyarı_mesajı), ...]
        """
        uyarilar = []
        for m in mektuplar:
            if m.iade_edildi_mi:
                continue
            kg = m.kalan_gun
            if kg < 0:
                uyarilar.append((m, f"Vadesi {abs(kg)} gün ÖNCE geçti!"))
            elif kg <= uyari_gun:
                uyarilar.append((m, f"Vadeye {kg} gün kaldı."))
        return uyarilar

    # ── Rapor yardımcısı ──────────────────────────────────────────────────────

    def ozet_dict(self, sonuc: TeminatHesapSonucu) -> dict:
        return {
            "ihale_bedeli":     float(sonuc.ihale_bedeli),
            "sozlesme_bedeli":  float(sonuc.sozlesme_bedeli),
            "gecici_teminat":   float(sonuc.gecici_teminat),
            "kesin_teminat":    float(sonuc.kesin_teminat),
            "ek_kesin_teminat": float(sonuc.ek_kesin_teminat),
            "toplam_zorunlu":   float(sonuc.toplam_zorunlu_teminat),
            "iade_kosullari":   IADE_KOSULLARI,
            "uyarilar":         sonuc.uyarilar,
        }

    @staticmethod
    def teminat_turleri() -> List[str]:
        return TEMINAT_TURLERI
