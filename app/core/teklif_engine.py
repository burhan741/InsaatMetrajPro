"""
Profesyonel Teklif Hazırlama — Engine
=======================================
Serbest Piyasa / Özel Müşteri Teklifi

KDV oranı : %20 (2023 sonrası yapım işi)
Stopaj : %3 (gerçek kişi müşteri — GVK md.94)
Kar marjı : Kullanıcı tanımlı (varsayılan %20)

Neyi çözüyoruz?
Müteahhidin özel müşteriye vereceği teklifin
maliyet + kar + KDV zincirini hatasız ve
profesyonel PDF/Excel çıktısıyla yönetiyoruz.

Nasıl test ederiz?
engine = TeklifEngine()
kalem = TeklifKalemi(tanim="Briket Duvar", miktar=Decimal("150"),
birim="m²", birim_fiyat=Decimal("850"))
bilgi = TeklifBilgisi(musteri_adi="Ali Yılmaz",
kar_marji_orani=Decimal("0.20"))
bilgi.kalemler = [engine.hesapla_kalem(kalem)]
sonuc = engine.hesapla(bilgi)
assert sonuc.genel_toplam == Decimal("217800.00")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

KDV_ORANI = Decimal("0.20") # Yapım işi KDV — 2023+
STOPAJ_ORANI = Decimal("0.03") # GVK md.94 — gerçek kişi
VARSAYILAN_KAR = Decimal("0.20") # %20 kar marjı
GECERLILIK_SURESI = 30 # Teklifin kaç gün geçerli olacağı

PROJE_TURLERI = [
"Konut (Yeni Yapı)",
"Konut Tadilat / Renovasyon",
"Villa / Müstakil",
"Ticari (Ofis/Dükkan)",
"Endüstriyel",
"İç Mimari / İnce İş",
"Dış Cephe",
"Altyapı / Bahçe",
"Diğer",
]

ODEME_PLANLARI = [
"Peşin (teslimde)",
"%30 Avans — %40 Kaba Yapı — %30 Teslim",
"%50 Avans — %50 Teslim",
"Aylık Hakediş",
"Özel Plan",
]


# ---------------------------------------------------------------------------
# Veri sınıfları
# ---------------------------------------------------------------------------

@dataclass
class TeklifKalemi:
    """Teklifte tek bir iş kalemi satırı."""
    sira_no: int = 0
    poz_no: str = ""
    tanim: str = ""
    birim: str = ""
    miktar: Decimal = Decimal("0")
    birim_fiyat: Decimal = Decimal("0")
    toplam: Decimal = Decimal("0")
    notlar: str = ""


@dataclass
class TeklifBilgisi:
    """Tüm teklif bilgilerini taşıyan veri yapısı."""

    # Müşteri
    musteri_adi: str = ""
    musteri_telefon: str = ""
    musteri_adres: str = ""
    musteri_tc_vkn: str = "" # TC / Vergi Kimlik No

    # Proje
    proje_adi: str = ""
    proje_adresi: str = ""
    proje_turu: str = "Konut (Yeni Yapı)"

    # Teklif kimlik
    teklif_no: str = ""
    teklif_tarihi: Optional[date] = None
    gecerlilik_tarihi: Optional[date] = None

    # Finansal parametreler
    kar_marji_orani: Decimal = VARSAYILAN_KAR
    avans_orani: Decimal = Decimal("0.30")
    stopaj_var_mi: bool = False # Gerçek kişi müşteri?
    kdv_haric_mi: bool = False # KDV hariç teklif?

    # Ödeme ve notlar
    odeme_plani: str = "%30 Avans — %40 Kaba Yapı — %30 Teslim"
    notlar: str = ""
    firma_adi: str = ""

    # İş kalemleri
    kalemler: list[TeklifKalemi] = field(default_factory=list)


@dataclass
class TeklifSonucu:
    """Hesaplama çıktısı."""
    ara_toplam: Decimal = Decimal("0") # Kalemlerin toplamı (kar öncesi)
    kar_tutari: Decimal = Decimal("0") # Kar marjı tutarı
    kdv_matrah: Decimal = Decimal("0") # Ara toplam + kar
    kdv_tutari: Decimal = Decimal("0") # KDV matrahının %20'si
    stopaj_tutari: Decimal = Decimal("0") # Varsa %3 stopaj
    genel_toplam: Decimal = Decimal("0") # KDV matrahı + KDV
    net_odenecek: Decimal = Decimal("0") # Genel toplam − stopaj
    avans_tutari: Decimal = Decimal("0") # Net ödenecek × avans oranı


# ---------------------------------------------------------------------------
# Ana engine
# ---------------------------------------------------------------------------

class TeklifEngine:
    """
    Özel müşteri teklifi hesaplama motoru.

    Hesap zinciri:
    Ara Toplam = Σ (miktar × birim_fiyat)
    Kar Tutarı = Ara Toplam × kar_marji_oranı
    KDV Matrahı = Ara Toplam + Kar Tutarı
    KDV = KDV Matrahı × 0.20
    Genel Toplam = KDV Matrahı + KDV
    Stopaj = KDV Matrahı × 0.03 (gerçek kişi varsa)
    Net Ödenecek = Genel Toplam − Stopaj
    """

    def _round2(self, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        def hesapla_kalem(self, kalem: TeklifKalemi) -> TeklifKalemi:
            """Tek kalemin satır toplamını hesapla."""
            kalem.toplam = self._round2(kalem.miktar * kalem.birim_fiyat)
            return kalem

            def hesapla(self, bilgi: TeklifBilgisi) -> TeklifSonucu:
                """Tüm teklif finansal özetini hesapla."""
                sonuc = TeklifSonucu()

                # Kalemleri güncelle
                for k in bilgi.kalemler:
                    self.hesapla_kalem(k)

                    # Ara toplam
                    sonuc.ara_toplam = self._round2(
                    sum(k.toplam for k in bilgi.kalemler)
                    )

                    # Kar marjı
                    sonuc.kar_tutari = self._round2(
                    sonuc.ara_toplam * bilgi.kar_marji_orani
                    )

                    # KDV matrahı = maliyet + kar
                    sonuc.kdv_matrah = self._round2(sonuc.ara_toplam + sonuc.kar_tutari)

                    # KDV
                    if not bilgi.kdv_haric_mi:
                        sonuc.kdv_tutari = self._round2(sonuc.kdv_matrah * KDV_ORANI)

                        # Genel toplam
                        sonuc.genel_toplam = self._round2(sonuc.kdv_matrah + sonuc.kdv_tutari)

                        # Stopaj (gerçek kişi müşteriye — matrah üzerinden)
                        if bilgi.stopaj_var_mi:
                            sonuc.stopaj_tutari = self._round2(sonuc.kdv_matrah * STOPAJ_ORANI)

                            # Net ödenecek
                            sonuc.net_odenecek = self._round2(
                            sonuc.genel_toplam - sonuc.stopaj_tutari
                            )

                            # Avans tutarı
                            sonuc.avans_tutari = self._round2(
                            sonuc.net_odenecek * bilgi.avans_orani
                            )

                            return sonuc

                            def teklif_no_uret(self, yil: int, sira: int) -> str:
                                """TKL-2026-0001 formatında teklif numarası üret."""
                                return f"TKL-{yil}-{sira:04d}"

                                def gecerlilik_tarihi_hesapla(
                                self, baslangic: date, gun: int = GECERLILIK_SURESI
                                ) -> date:
                                    return baslangic + timedelta(days=gun)

                                def kar_marji_orani_onerileri(self) -> dict[str, Decimal]:
                                    """Sektörde yaygın kar marjı bantları."""
                                    return {
                                    "Düşük risk (basit tadilat)": Decimal("0.15"),
                                    "Standart (konut yapım)": Decimal("0.20"),
                                    "Yüksek risk (özel/ticari):": Decimal("0.25"),
                                    "Anahtar teslim premium": Decimal("0.30"),
                                    }

                                    def ozet_dict(
                                    self, bilgi: TeklifBilgisi, sonuc: TeklifSonucu
                                    ) -> dict:
                                        return {
                                    "teklif_no": bilgi.teklif_no,
                                    "musteri": bilgi.musteri_adi,
                                    "proje": bilgi.proje_adi,
                                    "kalem_sayisi": len(bilgi.kalemler),
                                    "ara_toplam": float(sonuc.ara_toplam),
                                    "kar_tutari": float(sonuc.kar_tutari),
                                    "kar_orani_pct": float(bilgi.kar_marji_orani * 100),
                                    "kdv_matrah": float(sonuc.kdv_matrah),
                                    "kdv_tutari": float(sonuc.kdv_tutari),
                                    "stopaj_tutari": float(sonuc.stopaj_tutari),
                                    "genel_toplam": float(sonuc.genel_toplam),
                                    "net_odenecek": float(sonuc.net_odenecek),
                                    "avans_tutari": float(sonuc.avans_tutari),
                                    }
