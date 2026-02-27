"""
Gecikme Cezası ve Süre Uzatımı — Engine
==========================================
4735 sayılı Kamu İhale Sözleşmeleri Kanunu md.20

Günlük gecikme cezası = sözleşme bedeli × %0.5 (binde beş — ‰5)
Fesih eşiği = sözleşme bedelinin %30'u (md.20-b)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import Optional


GUNLUK_GECIKME_ORANI = Decimal("0.005") # binde beş (%0.5) günlük — 4735 md.20 / Yapım İşleri Genel Şartnamesi
FESIH_ESIGI_ORANI = Decimal("0.30") # %30 toplam → fesih

# Mücbir sebep kategorileri (4735 md.10)
MUCBIR_SEBEP_KATEGORILERI = [
"Doğal afet (deprem, sel, heyelan, çığ)",
"Salgın hastalık (pandemi, karantina)",
"Savaş, seferberlik, terör olayı",
"Genel grev, lokavt",
"Kanun değişikliği / idare kararı",
"Beklenemeyen kamu altyapı kesintisi",
"Diğer (açıklama gerektirir)",
]


@dataclass
class GecikmeGunuKaydi:
    """Tek bir gecikme/mücbir sebep dönemi"""
    baslangic: date
    bitis: date
    sebep: str = ""
    mucbir_sebep_mi: bool = False

    @property
    def gun_sayisi(self) -> int:
        return max((self.bitis - self.baslangic).days + 1, 0)


@dataclass
class GecikmeCezaSonucu:
    sozlesme_bedeli: Decimal = Decimal("0")

    toplam_gecikme_gun: int = 0
    mucbir_sebep_gun: int = 0
    net_ceza_gun: int = 0

    gunluk_ceza_tutari: Decimal = Decimal("0")
    toplam_ceza: Decimal = Decimal("0")

    fesih_esigi_tutari: Decimal = Decimal("0")
    fesih_riski: bool = False
    fesih_riski_pct: Decimal = Decimal("0")

    sure_uzatim_hakki_gun: int = 0
    uyarilar: list[str] = field(default_factory=list)


class GecikmeCezaEngine:
    """
    Kamu yapım işi gecikme cezası ve süre uzatım hakkı hesabı.

    Kullanım:
    engine = GecikmeCezaEngine()
    kayitlar = [
    GecikmeGunuKaydi(date(2025,10,1), date(2025,10,15), "İş durdu"),
    GecikmeGunuKaydi(date(2025,11,1), date(2025,11,7),
    "Deprem", mucbir_sebep_mi=True),
    ]
    sonuc = engine.hesapla(sozlesme_bedeli=Decimal("10_000_000"),
    kayitlar=kayitlar)
    """

    def _round2(self, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        def hesapla(
        self,
        sozlesme_bedeli: Decimal,
        kayitlar: list[GecikmeGunuKaydi],
        ) -> GecikmeCezaSonucu:
            sonuc = GecikmeCezaSonucu(sozlesme_bedeli=sozlesme_bedeli)

        toplam = sum(k.gun_sayisi for k in kayitlar)
        mucbir = sum(k.gun_sayisi for k in kayitlar if k.mucbir_sebep_mi)
        net = max(toplam - mucbir, 0)

        sonuc.toplam_gecikme_gun = toplam
        sonuc.mucbir_sebep_gun = mucbir
        sonuc.net_ceza_gun = net
        sonuc.sure_uzatim_hakki_gun = mucbir

        gunluk = self._round2(sozlesme_bedeli * GUNLUK_GECIKME_ORANI)
        sonuc.gunluk_ceza_tutari = gunluk
        sonuc.toplam_ceza = self._round2(gunluk * Decimal(net))

        fesih_esigi = self._round2(sozlesme_bedeli * FESIH_ESIGI_ORANI)
        sonuc.fesih_esigi_tutari = fesih_esigi

        if sozlesme_bedeli > 0:
            pct = self._round2(
            (sonuc.toplam_ceza / sozlesme_bedeli) * Decimal("100")
            )
            sonuc.fesih_riski_pct = pct
            sonuc.fesih_riski = pct >= Decimal("30")

            self._ekle_uyarilar(sonuc)
            return sonuc

            def _ekle_uyarilar(self, sonuc: GecikmeCezaSonucu) -> None:
                if sonuc.fesih_riski:
                    sonuc.uyarilar.append(
                    f" Toplam ceza sözleşme bedelinin %30'una ulaştı "
                    f"({float(sonuc.fesih_riski_pct):.1f}%). "
                    "İdare sözleşmeyi feshedebilir (4735 md.20-b)."
                    )
                elif sonuc.fesih_riski_pct >= Decimal("20"):
                    sonuc.uyarilar.append(
                    f" Gecikme cezası %{float(sonuc.fesih_riski_pct):.1f} düzeyinde. "
                    "Fesih eşiğine (%30) yaklaşılıyor."
                    )
                    if sonuc.mucbir_sebep_gun > 0:
                        sonuc.uyarilar.append(
                        f"ℹ {sonuc.mucbir_sebep_gun} gün mücbir sebep olarak tespit edildi. "
                        "Süre uzatım talebi yapılabilir (4735 md.10)."
                        )

                        def ozet_dict(self, sonuc: GecikmeCezaSonucu) -> dict:
                            return {
                            "sozlesme_bedeli": float(sonuc.sozlesme_bedeli),
                            "toplam_gecikme_gun": sonuc.toplam_gecikme_gun,
                            "mucbir_sebep_gun": sonuc.mucbir_sebep_gun,
                            "net_ceza_gun": sonuc.net_ceza_gun,
                            "gunluk_ceza": float(sonuc.gunluk_ceza_tutari),
                            "toplam_ceza": float(sonuc.toplam_ceza),
                            "fesih_esigi": float(sonuc.fesih_esigi_tutari),
                            "fesih_riski": sonuc.fesih_riski,
                            "fesih_riski_pct": float(sonuc.fesih_riski_pct),
                            "sure_uzatim_gun": sonuc.sure_uzatim_hakki_gun,
                            "uyarilar": sonuc.uyarilar,
                            }
