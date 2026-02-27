"""
Fiyat Farkı Hesabı — Engine
=============================
4735 sayılı Kamu İhale Sözleşmeleri Kanunu md.8
Kamu İhale Genel Tebliği (2012/1) — Fiyat farkı esasları

TÜİK endeks katsayıları:
D1 — Akaryakıt (ÜFE alt grup)
D2 — Çelik, demir (ÜFE alt grup)
D3 — Diğer malzeme (ÜFE genel)
A — Asgari ücret (AGİ dahil)

Formül (tek poz):
Fiyat Farkı = Kalem Bedeli × (Pn/P0 − 1)
Pn = uygulama dönemi endeksi
P0 = temel endeks (sözleşme tarihi öncesi son açıklanan)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


# ---------------------------------------------------------------------------
# Endeks tipleri
# ---------------------------------------------------------------------------

ENDEKS_TIPLERI: dict[str, str] = {
"D1": "TÜİK ÜFE — Akaryakıt",
"D2": "TÜİK ÜFE — Çelik / Demir",
"D3": "TÜİK ÜFE — Diğer Malzeme (Genel)",
"A": "Asgari Ücret Artış Oranı",
"I": "TÜİK ÜFE — Genel (4735/8-a yöntemi)",
}


# ---------------------------------------------------------------------------
# Veri sınıfları
# ---------------------------------------------------------------------------

@dataclass
class EndeksKatsayi:
    """Bir poza ait endeks ağırlıkları (toplam 1.00 olmalı)"""

    poz_kodu: str = ""
    poz_tanimi: str = ""

    # Endeks ağırlık katsayıları
    d1_katsayi: Decimal = Decimal("0") # akaryakıt
    d2_katsayi: Decimal = Decimal("0") # çelik/demir
    d3_katsayi: Decimal = Decimal("0") # diğer malzeme
    a_katsayi: Decimal = Decimal("0") # işçilik/ücret
    # Sabit kısım = 1 − (d1+d2+d3+a); fiyat farkı uygulanmaz

    # Endeks değerleri
    temel_d1: Decimal = Decimal("100")
    temel_d2: Decimal = Decimal("100")
    temel_d3: Decimal = Decimal("100")
    temel_a: Decimal = Decimal("100")

    uygulama_d1: Decimal = Decimal("100")
    uygulama_d2: Decimal = Decimal("100")
    uygulama_d3: Decimal = Decimal("100")
    uygulama_a: Decimal = Decimal("100")

    # İmalat bedeli (KDV hariç)
    imalat_bedeli: Decimal = Decimal("0")


@dataclass
class FiyatFarkiKalemi:
    """Tek poz için fiyat farkı hesap sonucu"""

    poz_kodu: str = ""
    poz_tanimi: str = ""
    imalat_bedeli: Decimal = Decimal("0")

    ff_d1: Decimal = Decimal("0")
    ff_d2: Decimal = Decimal("0")
    ff_d3: Decimal = Decimal("0")
    ff_a: Decimal = Decimal("0")
    toplam_ff: Decimal = Decimal("0")

    degisim_orani: Decimal = Decimal("0") # %


@dataclass
class FiyatFarkiSonucu:
    """Tüm pozların toplam fiyat farkı"""

    kalemler: list[FiyatFarkiKalemi] = field(default_factory=list)
    toplam_imalat: Decimal = Decimal("0")
    toplam_fiyat_farki: Decimal = Decimal("0")
    uyarilar: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ana engine
# ---------------------------------------------------------------------------

class FiyatFarkiEngine:
    """
    Poz bazlı fiyat farkı hesabı.

    Kullanım:
    engine = FiyatFarkiEngine()
    kalem = EndeksKatsayi(
    poz_kodu="22.001",
    d3_katsayi=Decimal("0.60"),
    a_katsayi=Decimal("0.30"),
    temel_d3=Decimal("1200"),
    uygulama_d3=Decimal("1350"),
    temel_a=Decimal("100"),
    uygulama_a=Decimal("118"),
    imalat_bedeli=Decimal("500_000")
    )
    sonuc = engine.hesapla([kalem])
    """

    def _round2(self, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # ------------------------------------------------------------------
        # Tek kalem hesabı
        # ------------------------------------------------------------------

        def _hesapla_kalem(self, k: EndeksKatsayi) -> FiyatFarkiKalemi:
            """
            FF_d1 = Bedel × d1_katsayi × (uygulama_d1/temel_d1 − 1)
            FF_d2 = Bedel × d2_katsayi × (uygulama_d2/temel_d2 − 1)
            ...
            """
            B = k.imalat_bedeli

            def oran(uyg: Decimal, temel: Decimal) -> Decimal:
                if temel == 0:
                    return Decimal("0")
                    return (uyg / temel) - Decimal("1")

                    ff_d1 = self._round2(B * k.d1_katsayi * oran(k.uygulama_d1, k.temel_d1))
                    ff_d2 = self._round2(B * k.d2_katsayi * oran(k.uygulama_d2, k.temel_d2))
                    ff_d3 = self._round2(B * k.d3_katsayi * oran(k.uygulama_d3, k.temel_d3))
                    ff_a = self._round2(B * k.a_katsayi * oran(k.uygulama_a, k.temel_a))

                    toplam = ff_d1 + ff_d2 + ff_d3 + ff_a

                    degisim = self._round2(
                    (toplam / B * Decimal("100")) if B != 0 else Decimal("0")
                    )

                    return FiyatFarkiKalemi(
                    poz_kodu = k.poz_kodu,
                    poz_tanimi = k.poz_tanimi,
                    imalat_bedeli = B,
                    ff_d1 = ff_d1,
                    ff_d2 = ff_d2,
                    ff_d3 = ff_d3,
                    ff_a = ff_a,
                    toplam_ff = toplam,
                    degisim_orani = degisim,
                    )

                    # ------------------------------------------------------------------
                    # Çoklu kalem hesabı
                    # ------------------------------------------------------------------

                    def hesapla(self, kalemler: list[EndeksKatsayi]) -> FiyatFarkiSonucu:
                        sonuc = FiyatFarkiSonucu()
                        for k in kalemler:
                            hk = self._hesapla_kalem(k)
                            sonuc.kalemler.append(hk)
                            sonuc.toplam_imalat += k.imalat_bedeli
                            sonuc.toplam_fiyat_farki += hk.toplam_ff

                            sonuc.toplam_imalat = self._round2(sonuc.toplam_imalat)
                            sonuc.toplam_fiyat_farki = self._round2(sonuc.toplam_fiyat_farki)

                            # Uyarılar
                            if sonuc.toplam_fiyat_farki < 0:
                                sonuc.uyarilar.append(
                                " Toplam fiyat farkı negatif — yüklenici aleyhine (kesinti yapılacak)."
                                )

                                return sonuc

                                # ------------------------------------------------------------------
                                # Tek endeks yöntemi (4735/8-a — basit ÜFE genel)
                                # ------------------------------------------------------------------

                                def hesapla_tek_endeks(
                                self,
                                imalat_bedeli: Decimal,
                                temel_endeks: Decimal,
                                uygulama_endeksi: Decimal,
                                sabit_katsayi: Decimal = Decimal("0.15"), # sabit kısım (fiyat farkı uygulanmaz)
                                ) -> Decimal:
                                    """
                                Basit tek endeks yöntemi (küçük ihaleler):
                                FF = Bedel × (1 − sabit) × (Pn/P0 − 1)
                                """
                                if temel_endeks == 0:
                                    return Decimal("0")
                                    return self._round2(
                                    imalat_bedeli * (Decimal("1") - sabit_katsayi)
                                    * ((uygulama_endeksi / temel_endeks) - Decimal("1"))
                                    )

                                    # ------------------------------------------------------------------
                                    # Rapor yardımcıları
                                    # ------------------------------------------------------------------

                                    def ozet_dict(self, sonuc: FiyatFarkiSonucu) -> dict:
                                        return {
                                        "toplam_imalat": float(sonuc.toplam_imalat),
                                        "toplam_fiyat_farki": float(sonuc.toplam_fiyat_farki),
                                        "uyarilar": sonuc.uyarilar,
                                        "kalemler": [
                                        {
                                        "poz_kodu": k.poz_kodu,
                                        "poz_tanimi": k.poz_tanimi,
                                        "imalat_bedeli": float(k.imalat_bedeli),
                                        "ff_d1": float(k.ff_d1),
                                        "ff_d2": float(k.ff_d2),
                                        "ff_d3": float(k.ff_d3),
                                        "ff_a": float(k.ff_a),
                                        "toplam_ff": float(k.toplam_ff),
                                        "degisim_pct": float(k.degisim_orani),
                                        }
                                        for k in sonuc.kalemler
                                        ],
                                        }

                                        @staticmethod
                                        def endeks_tipleri() -> dict[str, str]:
                                            return ENDEKS_TIPLERI
