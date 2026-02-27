"""
Birim Fiyat Analiz Cetveli — Engine
=====================================
Bayındırlık İşleri Genel Şartnamesi + ÇŞB Analiz Formatı

Bileşenler (her poz için):
Malzeme — miktar × birim fiyat
İşçilik — süre (adam-saat) × adam-saat ücreti
Makine — saat × makine saatlik bedeli
Taşıma — mesafe (km) × birim nakliye bedeli
Genel Gider & Kâr — (Malzeme+İşçilik+Makine+Taşıma) × oran
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


# ---------------------------------------------------------------------------
# Varsayılan genel gider & kâr oranı (ÇŞB 2025 standart)
# ---------------------------------------------------------------------------

GENEL_GIDER_KAR_ORANI = Decimal("0.25") # %25 (değiştirilebilir)

# Nakliye birim fiyatı (TL/ton-km) — KGM 2025 tarifesi
NAKLIYE_BIRIM_FIYAT_TL_TON_KM = Decimal("12.50")


# ---------------------------------------------------------------------------
# Alt bileşen satırı
# ---------------------------------------------------------------------------

@dataclass
class AnalizSatiri:
    """Analiz cetvelinin tek bir bileşen satırı"""

    tip: str # "malzeme" | "iscilik" | "makine" | "tasima"
    tanim: str # açıklama
    birim: str # m³, ton, adam-saat, saat, km vb.
    miktar: Decimal # kullanım miktarı
    birim_fiyat: Decimal # TL/birim

    @property
    def tutar(self) -> Decimal:
        return (self.miktar * self.birim_fiyat).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
        )


# ---------------------------------------------------------------------------
# Poz analizi
# ---------------------------------------------------------------------------

@dataclass
class PozAnalizi:
    """Tek bir poz için tüm analiz kalemleri"""

    poz_kodu: str = ""
    poz_tanimi: str = ""
    birim: str = ""

    satirlar: list[AnalizSatiri] = field(default_factory=list)
    genel_gider_kar_orani: Decimal = field(
    default_factory=lambda: GENEL_GIDER_KAR_ORANI
    )


@dataclass
class PozAnalizSonucu:
    """Poz analiz hesap çıktısı"""

    poz_kodu: str = ""
    poz_tanimi: str = ""
    birim: str = ""

    malzeme_toplam: Decimal = Decimal("0")
    iscilik_toplam: Decimal = Decimal("0")
    makine_toplam: Decimal = Decimal("0")
    tasima_toplam: Decimal = Decimal("0")

    direkt_toplam: Decimal = Decimal("0")
    genel_gider_kar: Decimal = Decimal("0")
    birim_fiyat: Decimal = Decimal("0") # direkt + genel gider/kâr

    uyarilar: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class BirimFiyatAnalizEngine:
    """
    Birim fiyat analiz cetveli hesabı.

    Kullanım:
    engine = BirimFiyatAnalizEngine()
    poz = PozAnalizi(
    poz_kodu="21.011",
    poz_tanimi="C25/30 Beton (hazır beton)",
    birim="m³")
    poz.satirlar.append(AnalizSatiri("malzeme","Hazır Beton","m³",
    Decimal("1.05"), Decimal("4200")))
    poz.satirlar.append(AnalizSatiri("iscilik","Beton İşçiliği","adam-saat",
    Decimal("0.5"), Decimal("380")))
    sonuc = engine.hesapla_poz(poz)
    """

    def _round2(self, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        def hesapla_poz(self, poz: PozAnalizi) -> PozAnalizSonucu:
            sonuc = PozAnalizSonucu(
            poz_kodu=poz.poz_kodu,
            poz_tanimi=poz.poz_tanimi,
            birim=poz.birim,
            )

            for satir in poz.satirlar:
                t = satir.tutar
                if satir.tip == "malzeme":
                    sonuc.malzeme_toplam += t
                elif satir.tip == "iscilik":
                    sonuc.iscilik_toplam += t
                elif satir.tip == "makine":
                    sonuc.makine_toplam += t
                elif satir.tip == "tasima":
                    sonuc.tasima_toplam += t

                    sonuc.malzeme_toplam = self._round2(sonuc.malzeme_toplam)
                    sonuc.iscilik_toplam = self._round2(sonuc.iscilik_toplam)
                    sonuc.makine_toplam = self._round2(sonuc.makine_toplam)
                    sonuc.tasima_toplam = self._round2(sonuc.tasima_toplam)

                    sonuc.direkt_toplam = self._round2(
                    sonuc.malzeme_toplam + sonuc.iscilik_toplam
                    + sonuc.makine_toplam + sonuc.tasima_toplam
                    )

                    sonuc.genel_gider_kar = self._round2(
                    sonuc.direkt_toplam * poz.genel_gider_kar_orani
                    )

                    sonuc.birim_fiyat = self._round2(
                    sonuc.direkt_toplam + sonuc.genel_gider_kar
                    )

                    return sonuc

                    def hesapla_liste(self, pozlar: list[PozAnalizi]) -> list[PozAnalizSonucu]:
                        return [self.hesapla_poz(p) for p in pozlar]

                        # ------------------------------------------------------------------
                        # Nakliye hesabı yardımcı
                        # ------------------------------------------------------------------

                        def hesapla_nakliye_tutari(
                        self,
                        ton: Decimal,
                        km: Decimal,
                        birim_fiyat: Decimal = NAKLIYE_BIRIM_FIYAT_TL_TON_KM,
                        ) -> Decimal:
                            """ton × km × TL/ton-km"""
                        return self._round2(ton * km * birim_fiyat)

                        # ------------------------------------------------------------------
                        # Rapor
                        # ------------------------------------------------------------------

                        def ozet_dict(self, poz: PozAnalizi, sonuc: PozAnalizSonucu) -> dict:
                            return {
                            "poz_kodu": sonuc.poz_kodu,
                            "poz_tanimi": sonuc.poz_tanimi,
                            "birim": sonuc.birim,
                            "malzeme": float(sonuc.malzeme_toplam),
                            "iscilik": float(sonuc.iscilik_toplam),
                            "makine": float(sonuc.makine_toplam),
                            "tasima": float(sonuc.tasima_toplam),
                            "direkt": float(sonuc.direkt_toplam),
                            "genel_gider_kar": float(sonuc.genel_gider_kar),
                            "birim_fiyat": float(sonuc.birim_fiyat),
                            "satirlar": [
                            {
                            "tip": s.tip,
                            "tanim": s.tanim,
                            "birim": s.birim,
                            "miktar": float(s.miktar),
                            "birim_fiyat": float(s.birim_fiyat),
                            "tutar": float(s.tutar),
                            }
                            for s in poz.satirlar
                            ],
                            }
