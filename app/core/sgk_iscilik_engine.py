"""
SGK Asgari İşçilik Hesabı — Engine
====================================
5510 sayılı Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu
md.85 — Asgari işçilik uygulaması

İşleyiş:
  sözleşme bedeli × asgari işçilik oranı = zorunlu işçilik tutarı
  zorunlu işçilik tutarı / aylık brüt ücret = zorunlu sigortalı ay
  zorunlu sigortalı ay × 30 = zorunlu sigortalı gün

Rev-79 (2026-04-26): 1-space cascade → 4-space PEP8 (tümden yeniden yazıldı)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# İş kolu oranları (5510 md.85 + SGK Genelgeleri 2024)
# ---------------------------------------------------------------------------

IS_KOLU_ORANLARI: dict[str, dict] = {
    "45": {
        "aciklama": "İnşaat — Genel Yapı",
        "oran": Decimal("0.0650"),   # %6.50
    },
    "42": {
        "aciklama": "Altyapı — Yol, Köprü, Tünel",
        "oran": Decimal("0.0575"),   # %5.75
    },
    "41": {
        "aciklama": "Su Yapıları (DSİ, Kanal, Baraj)",
        "oran": Decimal("0.0525"),   # %5.25
    },
    "43": {
        "aciklama": "Elektrik, Mekanik Tesisat",
        "oran": Decimal("0.0450"),   # %4.50
    },
    "74": {
        "aciklama": "Temizlik, Güvenlik, Hizmet",
        "oran": Decimal("0.0300"),   # %3.00
    },
    "ozel": {
        "aciklama": "Özel Oran (Manuel)",
        "oran": Decimal("0.0650"),
    },
}

# 2025 yılı asgari ücret (aylık brüt)
ASGARI_UCRET_AYLIK_2025 = Decimal("26_005.50")

# SGK prime esas kazanç sınırları
PRIM_ESAS_ALT = ASGARI_UCRET_AYLIK_2025
PRIM_ESAS_UST = ASGARI_UCRET_AYLIK_2025 * Decimal("7.5")

# İşveren SGK prim oranları
ISVEREN_SGK_ORANI        = Decimal("0.205")   # %20.5 (normal)
ISVEREN_SGK_ORANI_TESVIK = Decimal("0.155")   # %15.5 (5510/81-ı teşvikli)


# ---------------------------------------------------------------------------
# Veri sınıfları
# ---------------------------------------------------------------------------

@dataclass
class SgkIscilkBilgisi:
    """Hesaplama girdileri."""

    sozlesme_bedeli:  Decimal = Decimal("0")
    is_kolu_kodu:     str     = "45"        # bkz. IS_KOLU_ORANLARI
    ozel_oran:        Optional[Decimal] = None  # is_kolu="ozel" ise kullanılır

    baslangic_tarihi: date = field(default_factory=date.today)
    bitis_tarihi:     date = field(default_factory=date.today)

    aylik_brut_ucret: Decimal = field(
        default_factory=lambda: ASGARI_UCRET_AYLIK_2025
    )

    tesvik_aktif:   bool = False
    kdv_haric_bedel: bool = True   # True → KDV hariç sözleşme bedeli girildi


@dataclass
class SgkIscilkSonucu:
    """Hesaplama çıktıları."""

    is_kolu_aciklama:       str     = ""
    uygulanan_oran:         Decimal = Decimal("0")

    zorunlu_iscilik_tutari: Decimal = Decimal("0")
    zorunlu_sigortalı_ay:   Decimal = Decimal("0")
    zorunlu_sigortalı_gun:  int     = 0

    toplam_is_suresi_gun:    int     = 0
    aylik_sigortalı_sayisi:  Decimal = Decimal("0")

    prim_esas_kazanc_alt:   Decimal = Decimal("0")
    prim_esas_kazanc_ust:   Decimal = Decimal("0")

    isveren_sgk_tutari:     Decimal = Decimal("0")
    uygulanan_sgk_orani:    Decimal = Decimal("0")

    uylik_prim_takvimi: list = field(default_factory=list)
    uyarilar:           list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ana engine
# ---------------------------------------------------------------------------

class SgkIscilkEngine:
    """
    SGK Asgari İşçilik hesabı.

    Kullanım:
        engine = SgkIscilkEngine()
        bilgi  = SgkIscilkBilgisi(
            sozlesme_bedeli  = Decimal("5_000_000"),
            is_kolu_kodu     = "45",
            baslangic_tarihi = date(2025, 3, 1),
            bitis_tarihi     = date(2026, 2, 28),
        )
        sonuc = engine.hesapla(bilgi)
    """

    # ── Yardımcılar ───────────────────────────────────────────────────────────

    def _round2(self, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _round0(self, v: Decimal) -> int:
        return int(v.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    # ── Ana hesap ─────────────────────────────────────────────────────────────

    def hesapla(self, bilgi: SgkIscilkBilgisi) -> SgkIscilkSonucu:
        sonuc = SgkIscilkSonucu()

        # İş kolu oranı
        kol = IS_KOLU_ORANLARI.get(bilgi.is_kolu_kodu, IS_KOLU_ORANLARI["45"])
        sonuc.is_kolu_aciklama = kol["aciklama"]
        oran = (
            bilgi.ozel_oran
            if bilgi.is_kolu_kodu == "ozel" and bilgi.ozel_oran
            else kol["oran"]
        )
        sonuc.uygulanan_oran = oran

        # Zorunlu işçilik tutarı
        zorunlu = self._round2(bilgi.sozlesme_bedeli * oran)
        sonuc.zorunlu_iscilik_tutari = zorunlu

        # Aylık ücret
        aylik_ucret = bilgi.aylik_brut_ucret
        if aylik_ucret <= 0:
            aylik_ucret = ASGARI_UCRET_AYLIK_2025

        # Zorunlu sigortalı ay / gün
        zorunlu_ay = self._round2(zorunlu / aylik_ucret)
        sonuc.zorunlu_sigortalı_ay = zorunlu_ay
        sonuc.zorunlu_sigortalı_gun = self._round0(zorunlu_ay * Decimal("30"))

        # İş süresi
        delta = (bilgi.bitis_tarihi - bilgi.baslangic_tarihi).days + 1
        sonuc.toplam_is_suresi_gun = max(delta, 1)

        # Ortalama aylık işçi sayısı
        ay_sayisi = Decimal(str(sonuc.toplam_is_suresi_gun)) / Decimal("30")
        if ay_sayisi > 0:
            sonuc.aylik_sigortalı_sayisi = self._round2(zorunlu_ay / ay_sayisi)

        # Prime esas kazanç sınırları
        sonuc.prim_esas_kazanc_alt = PRIM_ESAS_ALT
        sonuc.prim_esas_kazanc_ust = PRIM_ESAS_UST

        # İşveren SGK prim tutarı
        sgk_orani = ISVEREN_SGK_ORANI_TESVIK if bilgi.tesvik_aktif else ISVEREN_SGK_ORANI
        sonuc.uygulanan_sgk_orani = sgk_orani
        gunluk_prim_baz = self._round2(aylik_ucret / Decimal("30"))
        toplam_prim = self._round2(
            gunluk_prim_baz * Decimal(sonuc.zorunlu_sigortalı_gun) * sgk_orani
        )
        sonuc.isveren_sgk_tutari = toplam_prim

        # Aylık prim takvimi
        sonuc.uylik_prim_takvimi = self._olustur_takvim(
            bilgi, zorunlu_ay, aylik_ucret, sgk_orani
        )

        # Uyarılar
        self._ekle_uyarilar(bilgi, sonuc)

        return sonuc

    # ── Aylık prim takvimi ────────────────────────────────────────────────────

    def _olustur_takvim(
        self,
        bilgi: SgkIscilkBilgisi,
        zorunlu_ay: Decimal,
        aylik_ucret: Decimal,
        sgk_orani: Decimal,
    ) -> list[dict]:
        """İş süresi boyunca aylık zorunlu sigortalı gün ve prim dağılımı."""
        takvim = []
        baslangic = bilgi.baslangic_tarihi
        bitis     = bilgi.bitis_tarihi

        ay_sayisi = 0
        cur = date(baslangic.year, baslangic.month, 1)
        while cur <= bitis:
            ay_sayisi += 1
            cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)

        if ay_sayisi == 0:
            return takvim

        aylik_zorunlu_ay = self._round2(zorunlu_ay / Decimal(str(ay_sayisi)))
        aylik_gun  = self._round0(aylik_zorunlu_ay * Decimal("30"))
        aylik_prim = self._round2(
            (aylik_ucret / Decimal("30")) * Decimal(str(aylik_gun)) * sgk_orani
        )

        cur = date(baslangic.year, baslangic.month, 1)
        for _ in range(ay_sayisi):
            takvim.append({
                "yil":          cur.year,
                "ay":           cur.month,
                "ay_adi":       self._ay_adi(cur.month),
                "zorunlu_gun":  aylik_gun,
                "zorunlu_ay":   float(aylik_zorunlu_ay),
                "isveren_prim": float(aylik_prim),
            })
            cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)

        return takvim

    def _ay_adi(self, ay: int) -> str:
        AYLAR = [
            "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
        ]
        return AYLAR[ay] if 1 <= ay <= 12 else str(ay)

    # ── Uyarılar ──────────────────────────────────────────────────────────────

    def _ekle_uyarilar(self, bilgi: SgkIscilkBilgisi, sonuc: SgkIscilkSonucu) -> None:
        if bilgi.aylik_brut_ucret < ASGARI_UCRET_AYLIK_2025:
            sonuc.uyarilar.append(
                f"Girilen aylık ücret ({float(bilgi.aylik_brut_ucret):,.2f} TL) "
                f"2025 asgari ücretinin ({float(ASGARI_UCRET_AYLIK_2025):,.2f} TL) altında."
            )
        if bilgi.bitis_tarihi < bilgi.baslangic_tarihi:
            sonuc.uyarilar.append("Bitiş tarihi başlangıç tarihinden önce.")

    # ── Raporlama ─────────────────────────────────────────────────────────────

    def ozet_dict(self, bilgi: SgkIscilkBilgisi, sonuc: SgkIscilkSonucu) -> dict:
        return {
            "sozlesme_bedeli":        float(bilgi.sozlesme_bedeli),
            "is_kolu":                sonuc.is_kolu_aciklama,
            "uygulanan_oran_pct":     float(sonuc.uygulanan_oran * 100),
            "zorunlu_iscilik_tutari": float(sonuc.zorunlu_iscilik_tutari),
            "zorunlu_sigortalı_ay":   float(sonuc.zorunlu_sigortalı_ay),
            "zorunlu_sigortalı_gun":  sonuc.zorunlu_sigortalı_gun,
            "ortalama_aylik_isci":    float(sonuc.aylik_sigortalı_sayisi),
            "isveren_sgk_tutari":     float(sonuc.isveren_sgk_tutari),
            "prim_esas_alt":          float(sonuc.prim_esas_kazanc_alt),
            "prim_esas_ust":          float(sonuc.prim_esas_kazanc_ust),
            "takvim":                 sonuc.uylik_prim_takvimi,
            "uyarilar":               sonuc.uyarilar,
        }

    @staticmethod
    def is_kolu_secenekleri() -> list[tuple[str, str]]:
        """ComboBox için (kod, açıklama) listesi."""
        return [
            (
                kod,
                f"{kod} — {bilgi['aciklama']} (%{float(bilgi['oran'] * 100):.2f})",
            )
            for kod, bilgi in IS_KOLU_ORANLARI.items()
        ]
