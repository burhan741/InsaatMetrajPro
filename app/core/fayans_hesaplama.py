"""
Oda Bazli Dinamik Fayans Hesaplama Modulu
=========================================
Grid yontemi ile gercek fire hesaplama, malzeme sarfiyati ve iscilik hesabi.

Yazar: Insaat Metraj Pro
Tarih: 2025
4-space PEP8 — tam yeniden yazım
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class OdaTuru(Enum):
    """Oda turu enum"""
    KURU_ZEMIN = "kuru_zemin"
    ISLAK_ZEMIN = "islak_zemin"


class VerimKaynagi(Enum):
    """Verim kaynagi enum"""
    PIYASA = "piyasa"
    MANUEL = "manuel"


@dataclass
class OdaGirdi:
    """Tek bir oda icin girdi verisi"""
    oda_adi: str
    en_cm: float
    boy_cm: float
    fayans_en_cm: float
    fayans_boy_cm: float
    oda_turu: str = "kuru_zemin"

    @property
    def oda_alan_m2(self) -> float:
        """Oda alanini m2 olarak hesapla"""
        return (self.en_cm * self.boy_cm) / 10000

    @property
    def fayans_alan_cm2(self) -> float:
        """Tek fayans alanini cm2 olarak hesapla"""
        return self.fayans_en_cm * self.fayans_boy_cm

    @property
    def fayans_alan_m2(self) -> float:
        """Tek fayans alanini m2 olarak hesapla"""
        return self.fayans_alan_cm2 / 10000


@dataclass
class OdaSonuc:
    """Tek bir oda icin hesaplama sonucu"""
    oda_adi: str
    oda_en_cm: float
    oda_boy_cm: float
    fayans_en_cm: float
    fayans_boy_cm: float
    oda_turu: str

    # Alan hesaplari
    net_alan_m2: float = 0.0
    brut_alan_m2: float = 0.0

    # Fayans adetleri
    satir_sayisi: int = 0
    sutun_sayisi: int = 0
    gereken_fayans_adet: int = 0

    # Fire hesabi
    fire_orani_yuzde: float = 0.0
    fire_alan_m2: float = 0.0

    # Optimal doseme
    optimal_yon: str = "normal"  # "normal" veya "dondurulmus"
    alternatif_adet: int = 0
    tasarruf_adet: int = 0

    # Malzeme sarfiyati
    yapistirici_kg: float = 0.0
    derz_kg: float = 0.0

    # Iscilik
    gunluk_verim_m2: float = 0.0
    tahmini_sure_gun: float = 0.0


@dataclass
class FayansHesaplamaSonuc:
    """Tum hesaplama sonucu"""
    oda_detaylari: List[OdaSonuc] = field(default_factory=list)

    # Genel toplamlar
    toplam_net_alan_m2: float = 0.0
    toplam_brut_alan_m2: float = 0.0
    toplam_gereken_fayans_adet: int = 0
    toplam_gereken_kutu: int = 0
    hesaplanan_ortalama_fire_yuzdesi: float = 0.0

    # Malzeme toplamlari
    toplam_yapistirici_kg: float = 0.0
    toplam_yapistirici_torba: int = 0  # 25 kg
    toplam_derz_kg: float = 0.0
    toplam_derz_torba: int = 0  # 20 kg

    # Iscilik
    tahmini_toplam_sure_gun: float = 0.0

    # Maliyet ozeti
    maliyet_ozeti: Dict[str, float] = field(default_factory=dict)


class FayansHesaplayici:
    """
    Oda bazli dinamik fayans hesaplama sinifi.

    Grid yontemi ile gercek fire hesaplama:
    - Satir Sayisi: Math.ceil(oda_boy / fayans_boy)
    - Sutun Sayisi: Math.ceil(oda_en / fayans_en)
    - Gereken Adet: Satir * Sutun
    """

    # Sabit degerler
    YAPISTIRICI_ISLAK_KG_M2 = 6.0   # Islak zeminlerde m2'ye 6 kg
    YAPISTIRICI_KURU_KG_M2 = 5.0    # Kuru zeminlerde m2'ye 5 kg
    DERZ_KUCUK_EBAT_KG_M2 = 0.6    # Kucuk ebat (<2000cm2) icin m2'ye 0.6 kg
    DERZ_BUYUK_EBAT_KG_M2 = 0.4    # Buyuk ebat (>=2000cm2) icin m2'ye 0.4 kg

    YAPISTIRICI_TORBA_KG = 25.0     # 1 torba yapistirici
    DERZ_TORBA_KG = 20.0            # 1 torba derz

    # Iscilik hizi (m2/gun) - 1 Usta + 1 Yardimci, tecrubelr ekip
    VERIM_BUYUK_EBAT = 15.0         # Buyuk ebat (60x120 vb.) - Agir malzeme
    VERIM_KUCUK_EBAT = 22.0         # Kucuk ebat (30x60 vb.)
    VERIM_ISLAK_ZEMIN = 10.0        # Islak zemin (banyo) - Cok kesim

    # Ebat sinirlari
    BUYUK_EBAT_ESIK_CM2 = 5000      # 50x100 ve uzeri buyuk ebat sayilir
    KUCUK_EBAT_ESIK_CM2 = 2000      # Derz hesabi icin kucuk/buyuk siniri

    def __init__(
        self,
        fayans_kutu_m2: float = 1.44,
        fayans_m2_fiyat: float = 150.0,
        ekip_gunluk_ucret: float = 3500.0,
        verim_kaynagi: str = "piyasa",
        manuel_verim_m2_gun: Optional[float] = None,
    ):
        """
        Hesaplayiciyi baslat.

        Args:
            fayans_kutu_m2: Bir kutuda kac m2 fayans var (siparis icin)
            fayans_m2_fiyat: Fayans m2 fiyati (TL)
            ekip_gunluk_ucret: Ekip gunluk ucreti (1 Usta + 1 Yardimci)
            verim_kaynagi: Verim kaynagi ("piyasa" veya "manuel")
            manuel_verim_m2_gun: Manuel verim degeri (m2/gun)
        """
        self.fayans_kutu_m2 = fayans_kutu_m2
        self.fayans_m2_fiyat = fayans_m2_fiyat
        self.ekip_gunluk_ucret = ekip_gunluk_ucret
        self.verim_kaynagi = verim_kaynagi
        self.manuel_verim_m2_gun = manuel_verim_m2_gun

    def _hesapla_grid_yontemi(
        self,
        oda_en: float,
        oda_boy: float,
        fayans_en: float,
        fayans_boy: float,
    ) -> Tuple[int, int, int]:
        """
        Grid yontemi ile fayans adedi hesapla.

        Returns:
            (satir_sayisi, sutun_sayisi, toplam_adet)
        """
        satir_sayisi = math.ceil(oda_boy / fayans_boy)
        sutun_sayisi = math.ceil(oda_en / fayans_en)
        toplam_adet = satir_sayisi * sutun_sayisi
        return satir_sayisi, sutun_sayisi, toplam_adet

    def _hesapla_optimal_doseme(
        self,
        oda_en: float,
        oda_boy: float,
        fayans_en: float,
        fayans_boy: float,
    ) -> Dict[str, Any]:
        """
        Alternatif doseme yonu kontrolu yaparak optimal yonu bul.

        Fayans en/boy yer degistirerek tekrar hesaplar,
        hangisinde daha az fayans gidiyorsa onu baz alir.
        """
        # Normal doseme
        _, _, normal_adet = self._hesapla_grid_yontemi(
            oda_en, oda_boy, fayans_en, fayans_boy
        )

        # Dondurulmus doseme (fayans 90 derece cevirilmis)
        satir_d, sutun_d, dondurulmus_adet = self._hesapla_grid_yontemi(
            oda_en, oda_boy, fayans_boy, fayans_en  # en ve boy yer degistirdi
        )

        if dondurulmus_adet < normal_adet:
            return {
                "optimal_yon": "dondurulmus",
                "optimal_adet": dondurulmus_adet,
                "alternatif_adet": normal_adet,
                "tasarruf_adet": normal_adet - dondurulmus_adet,
                "kullanilan_fayans_en": fayans_boy,
                "kullanilan_fayans_boy": fayans_en,
            }
        else:
            return {
                "optimal_yon": "normal",
                "optimal_adet": normal_adet,
                "alternatif_adet": dondurulmus_adet,
                "tasarruf_adet": max(0, dondurulmus_adet - normal_adet),
                "kullanilan_fayans_en": fayans_en,
                "kullanilan_fayans_boy": fayans_boy,
            }

    def _hesapla_malzeme_sarfiyati(
        self,
        alan_m2: float,
        fayans_alan_cm2: float,
        oda_turu: str,
    ) -> Dict[str, float]:
        """
        Malzeme sarfiyatini hesapla.

        Args:
            alan_m2: Toplam alan (m2)
            fayans_alan_cm2: Tek fayans alani (cm2)
            oda_turu: Oda turu ("kuru_zemin" veya "islak_zemin")

        Returns:
            Malzeme sarfiyati sözlüğü
        """
        if oda_turu == "islak_zemin":
            yapistirici_kg = alan_m2 * self.YAPISTIRICI_ISLAK_KG_M2
        else:
            yapistirici_kg = alan_m2 * self.YAPISTIRICI_KURU_KG_M2

        if fayans_alan_cm2 < self.KUCUK_EBAT_ESIK_CM2:
            derz_kg = alan_m2 * self.DERZ_KUCUK_EBAT_KG_M2
        else:
            derz_kg = alan_m2 * self.DERZ_BUYUK_EBAT_KG_M2

        return {
            "yapistirici_kg": yapistirici_kg,
            "derz_kg": derz_kg,
        }

    def _hesapla_iscilik_hizi(
        self,
        fayans_alan_cm2: float,
        oda_turu: str,
    ) -> float:
        """
        Iscilik hizini hesapla (m2/gun).

        Kriter:
        - Buyuk Ebat (60x120 vb.): Agir malzeme, gunluk 15 m2
        - Kucuk Ebat (30x60 vb.): Gunluk 22 m2
        - Islak Zemin (Banyo): Cok kesim ve detay, gunluk 10 m2

        Returns:
            Gunluk verim (m2/gun)
        """
        if self.verim_kaynagi == "manuel" and self.manuel_verim_m2_gun:
            return self.manuel_verim_m2_gun

        if oda_turu == "islak_zemin":
            return self.VERIM_ISLAK_ZEMIN

        if fayans_alan_cm2 >= self.BUYUK_EBAT_ESIK_CM2:
            return self.VERIM_BUYUK_EBAT

        return self.VERIM_KUCUK_EBAT

    def _hesapla_tek_oda(self, oda: OdaGirdi) -> OdaSonuc:
        """
        Tek bir oda icin hesaplama yap.

        Args:
            oda: Oda girdi verisi

        Returns:
            Oda hesaplama sonucu
        """
        net_alan_m2 = oda.oda_alan_m2
        fayans_alan_cm2 = oda.fayans_alan_cm2
        fayans_alan_m2 = oda.fayans_alan_m2

        optimal = self._hesapla_optimal_doseme(
            oda.en_cm, oda.boy_cm,
            oda.fayans_en_cm, oda.fayans_boy_cm,
        )

        kullanilan_fayans_en = optimal["kullanilan_fayans_en"]
        kullanilan_fayans_boy = optimal["kullanilan_fayans_boy"]

        satir_sayisi, sutun_sayisi, gereken_adet = self._hesapla_grid_yontemi(
            oda.en_cm, oda.boy_cm,
            kullanilan_fayans_en, kullanilan_fayans_boy,
        )

        brut_alan_m2 = gereken_adet * fayans_alan_m2

        fire_alan_m2 = brut_alan_m2 - net_alan_m2
        if net_alan_m2 > 0:
            fire_orani_yuzde = (fire_alan_m2 / net_alan_m2) * 100
        else:
            fire_orani_yuzde = 0.0

        malzeme = self._hesapla_malzeme_sarfiyati(brut_alan_m2, fayans_alan_cm2, oda.oda_turu)

        gunluk_verim = self._hesapla_iscilik_hizi(fayans_alan_cm2, oda.oda_turu)
        tahmini_sure_gun = net_alan_m2 / gunluk_verim if gunluk_verim > 0 else 0.0

        return OdaSonuc(
            oda_adi=oda.oda_adi,
            oda_en_cm=oda.en_cm,
            oda_boy_cm=oda.boy_cm,
            fayans_en_cm=oda.fayans_en_cm,
            fayans_boy_cm=oda.fayans_boy_cm,
            oda_turu=oda.oda_turu,
            net_alan_m2=net_alan_m2,
            brut_alan_m2=brut_alan_m2,
            satir_sayisi=satir_sayisi,
            sutun_sayisi=sutun_sayisi,
            gereken_fayans_adet=gereken_adet,
            fire_orani_yuzde=round(fire_orani_yuzde, 2),
            fire_alan_m2=round(fire_alan_m2, 4),
            optimal_yon=optimal["optimal_yon"],
            alternatif_adet=optimal["alternatif_adet"],
            tasarruf_adet=optimal["tasarruf_adet"],
            yapistirici_kg=round(malzeme["yapistirici_kg"], 2),
            derz_kg=round(malzeme["derz_kg"], 2),
            gunluk_verim_m2=gunluk_verim,
            tahmini_sure_gun=round(tahmini_sure_gun, 2),
        )

    def hesapla_fayans_oda_detayli(
        self,
        odalar_listesi: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Oda bazli dinamik fayans hesaplama ana fonksiyonu.

        Her odayi kendi icinde simule ederek gercek malzeme
        ve iscilik ihtiyacini cikarir.

        Args:
            odalar_listesi: Oda listesi (her eleman sozluk yapısında)
                - oda_adi: str
                - en_cm: float
                - boy_cm: float
                - fayans_en_cm: float
                - fayans_boy_cm: float
                - oda_turu: str ("kuru_zemin" veya "islak_zemin")

        Returns:
            Detayli rapor sozlugu
        """
        odalar = []
        for oda_dict in odalar_listesi:
            oda = OdaGirdi(
                oda_adi=oda_dict.get("oda_adi", "Oda"),
                en_cm=float(oda_dict.get("en_cm", 0)),
                boy_cm=float(oda_dict.get("boy_cm", 0)),
                fayans_en_cm=float(oda_dict.get("fayans_en_cm", 60)),
                fayans_boy_cm=float(oda_dict.get("fayans_boy_cm", 60)),
                oda_turu=oda_dict.get("oda_turu", "kuru_zemin"),
            )
            odalar.append(oda)

        oda_sonuclari = []
        toplam_net_alan = 0.0
        toplam_brut_alan = 0.0
        toplam_fayans_adet = 0
        toplam_yapistirici = 0.0
        toplam_derz = 0.0
        toplam_sure = 0.0
        toplam_fire_alan = 0.0

        for oda in odalar:
            sonuc = self._hesapla_tek_oda(oda)
            oda_sonuclari.append(sonuc)

            toplam_net_alan += sonuc.net_alan_m2
            toplam_brut_alan += sonuc.brut_alan_m2
            toplam_fayans_adet += sonuc.gereken_fayans_adet
            toplam_yapistirici += sonuc.yapistirici_kg
            toplam_derz += sonuc.derz_kg
            toplam_sure += sonuc.tahmini_sure_gun
            toplam_fire_alan += sonuc.fire_alan_m2

        if toplam_net_alan > 0:
            ortalama_fire_yuzdesi = (toplam_fire_alan / toplam_net_alan) * 100
        else:
            ortalama_fire_yuzdesi = 0.0

        toplam_kutu = (
            math.ceil(toplam_brut_alan / self.fayans_kutu_m2)
            if self.fayans_kutu_m2 > 0 else 0
        )

        yapistirici_torba = math.ceil(toplam_yapistirici / self.YAPISTIRICI_TORBA_KG)
        derz_torba = math.ceil(toplam_derz / self.DERZ_TORBA_KG)

        fayans_maliyeti = toplam_brut_alan * self.fayans_m2_fiyat
        iscilik_maliyeti = math.ceil(toplam_sure) * self.ekip_gunluk_ucret

        yapistirici_torba_fiyat = 180.0   # TL/torba (25kg)
        derz_torba_fiyat = 120.0          # TL/torba (20kg)

        yapistirici_maliyeti = yapistirici_torba * yapistirici_torba_fiyat
        derz_maliyeti = derz_torba * derz_torba_fiyat

        toplam_malzeme_maliyeti = fayans_maliyeti + yapistirici_maliyeti + derz_maliyeti
        genel_toplam = toplam_malzeme_maliyeti + iscilik_maliyeti

        return {
            "oda_detaylari": [
                {
                    "oda_adi": s.oda_adi,
                    "oda_en_cm": s.oda_en_cm,
                    "oda_boy_cm": s.oda_boy_cm,
                    "fayans_en_cm": s.fayans_en_cm,
                    "fayans_boy_cm": s.fayans_boy_cm,
                    "oda_turu": s.oda_turu,
                    "net_alan_m2": round(s.net_alan_m2, 2),
                    "brut_alan_m2": round(s.brut_alan_m2, 2),
                    "satir_sayisi": s.satir_sayisi,
                    "sutun_sayisi": s.sutun_sayisi,
                    "gereken_fayans_adet": s.gereken_fayans_adet,
                    "fire_orani_yuzde": s.fire_orani_yuzde,
                    "fire_alan_m2": s.fire_alan_m2,
                    "optimal_yon": s.optimal_yon,
                    "alternatif_adet": s.alternatif_adet,
                    "tasarruf_adet": s.tasarruf_adet,
                    "yapistirici_kg": s.yapistirici_kg,
                    "derz_kg": s.derz_kg,
                    "gunluk_verim_m2": s.gunluk_verim_m2,
                    "tahmini_sure_gun": s.tahmini_sure_gun,
                }
                for s in oda_sonuclari
            ],
            "toplam_net_alan_m2": round(toplam_net_alan, 2),
            "toplam_brut_alan_m2": round(toplam_brut_alan, 2),
            "toplam_gereken_fayans_adet": toplam_fayans_adet,
            "toplam_gereken_kutu": toplam_kutu,
            "hesaplanan_ortalama_fire_yuzdesi": round(ortalama_fire_yuzdesi, 2),
            "toplam_yapistirici_kg": round(toplam_yapistirici, 2),
            "toplam_yapistirici_torba": yapistirici_torba,
            "toplam_derz_kg": round(toplam_derz, 2),
            "toplam_derz_torba": derz_torba,
            "tahmini_toplam_sure_gun": math.ceil(toplam_sure),
            "maliyet_ozeti": {
                "fayans_maliyeti": round(fayans_maliyeti, 2),
                "yapistirici_maliyeti": round(yapistirici_maliyeti, 2),
                "derz_maliyeti": round(derz_maliyeti, 2),
                "toplam_malzeme_maliyeti": round(toplam_malzeme_maliyeti, 2),
                "iscilik_maliyeti": round(iscilik_maliyeti, 2),
                "genel_toplam": round(genel_toplam, 2),
            },
        }


def hesapla_fayans_oda_detayli(
    odalar_listesi: List[Dict[str, Any]],
    fayans_kutu_m2: float = 1.44,
    fayans_m2_fiyat: float = 150.0,
    ekip_gunluk_ucret: float = 3500.0,
    verim_kaynagi: str = "piyasa",
    manuel_verim_m2_gun: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Oda bazli dinamik fayans hesaplama fonksiyonu.

    Grid yontemi ile gercek fire hesaplama yaparak her odanin
    malzeme ve iscilik ihtiyacini cikarir.

    Args:
        odalar_listesi: Oda listesi (her eleman sozluk yapisinda)
            - oda_adi: str (Ornek: "Salon", "Mutfak")
            - en_cm: float (Odanin eni - cm cinsinden)
            - boy_cm: float (Odanin boyu - cm cinsinden)
            - fayans_en_cm: float (Secilen fayans eni - Ornek: 60)
            - fayans_boy_cm: float (Secilen fayans boyu - Ornek: 120)
            - oda_turu: str ("kuru_zemin" veya "islak_zemin")
        fayans_kutu_m2: Bir kutuda kac m2 fayans var (siparis icin)
        fayans_m2_fiyat: Fayans m2 fiyati (TL)
        ekip_gunluk_ucret: Ekip gunluk ucreti (1 Usta + 1 Yardimci)
        verim_kaynagi: Verim kaynagi ("piyasa" veya "manuel")
        manuel_verim_m2_gun: Manuel verim degeri (m2/gun)

    Returns:
        Detayli rapor sozlugu
    """
    hesaplayici = FayansHesaplayici(
        fayans_kutu_m2=fayans_kutu_m2,
        fayans_m2_fiyat=fayans_m2_fiyat,
        ekip_gunluk_ucret=ekip_gunluk_ucret,
        verim_kaynagi=verim_kaynagi,
        manuel_verim_m2_gun=manuel_verim_m2_gun,
    )
    return hesaplayici.hesapla_fayans_oda_detayli(odalar_listesi)


# Hazir fayans ebatlari
STANDART_FAYANS_EBATLARI = [
    {"ad": "20x20 cm", "en": 20, "boy": 20},
    {"ad": "25x40 cm", "en": 25, "boy": 40},
    {"ad": "30x30 cm", "en": 30, "boy": 30},
    {"ad": "30x60 cm", "en": 30, "boy": 60},
    {"ad": "33x33 cm", "en": 33, "boy": 33},
    {"ad": "40x40 cm", "en": 40, "boy": 40},
    {"ad": "45x45 cm", "en": 45, "boy": 45},
    {"ad": "50x50 cm", "en": 50, "boy": 50},
    {"ad": "60x60 cm", "en": 60, "boy": 60},
    {"ad": "60x120 cm", "en": 60, "boy": 120},
    {"ad": "80x80 cm", "en": 80, "boy": 80},
    {"ad": "100x100 cm", "en": 100, "boy": 100},
    {"ad": "120x120 cm", "en": 120, "boy": 120},
]


if __name__ == "__main__":
    # Test
    odalar = [
        {
            "oda_adi": "Salon",
            "en_cm": 500,
            "boy_cm": 700,
            "fayans_en_cm": 60,
            "fayans_boy_cm": 120,
            "oda_turu": "kuru_zemin",
        },
        {
            "oda_adi": "Mutfak",
            "en_cm": 350,
            "boy_cm": 400,
            "fayans_en_cm": 60,
            "fayans_boy_cm": 60,
            "oda_turu": "kuru_zemin",
        },
        {
            "oda_adi": "Banyo",
            "en_cm": 250,
            "boy_cm": 300,
            "fayans_en_cm": 30,
            "fayans_boy_cm": 60,
            "oda_turu": "islak_zemin",
        },
    ]

    sonuc = hesapla_fayans_oda_detayli(
        odalar_listesi=odalar,
        fayans_kutu_m2=1.44,
        fayans_m2_fiyat=180.0,
        ekip_gunluk_ucret=3500.0,
    )

    print("\n" + "=" * 60)
    print("FAYANS HESAPLAMA RAPORU")
    print("=" * 60)

    for oda in sonuc["oda_detaylari"]:
        print(f"\n--- {oda['oda_adi']} ---")
        print(f"  Boyutlar: {oda['oda_en_cm']}x{oda['oda_boy_cm']} cm")
        print(f"  Fayans: {oda['fayans_en_cm']}x{oda['fayans_boy_cm']} cm")
        print(f"  Net Alan: {oda['net_alan_m2']:.2f} m2")
        print(f"  Grid: {oda['satir_sayisi']} satir x {oda['sutun_sayisi']} sutun")
        print(f"  Gereken Fayans: {oda['gereken_fayans_adet']} adet")
        print(f"  Fire Orani: %{oda['fire_orani_yuzde']:.1f}")
        print(f"  Optimal Yon: {oda['optimal_yon']}")
        if oda["tasarruf_adet"] > 0:
            print(f"  Tasarruf: {oda['tasarruf_adet']} adet")
        print(f"  Yapistirici: {oda['yapistirici_kg']:.1f} kg")
        print(f"  Derz: {oda['derz_kg']:.1f} kg")
        print(f"  Tahmini Sure: {oda['tahmini_sure_gun']:.1f} gun")

    print("\n" + "=" * 60)
    print("GENEL TOPLAM")
    print("=" * 60)
    print(f"Toplam Net Alan: {sonuc['toplam_net_alan_m2']:.2f} m2")
    print(f"Toplam Fayans Adedi: {sonuc['toplam_gereken_fayans_adet']} adet")
    print(f"Gerekli Kutu: {sonuc['toplam_gereken_kutu']} kutu")
    print(f"Ortalama Fire: %{sonuc['hesaplanan_ortalama_fire_yuzdesi']:.1f}")
    print(f"Yapistirici: {sonuc['toplam_yapistirici_torba']} torba (25kg)")
    print(f"Derz: {sonuc['toplam_derz_torba']} torba (20kg)")
    print(f"Tahmini Sure: {sonuc['tahmini_toplam_sure_gun']} gun")

    print("\n--- Maliyet Ozeti ---")
    m = sonuc["maliyet_ozeti"]
    print(f"  Fayans: {m['fayans_maliyeti']:,.2f} TL")
    print(f"  Yapistirici: {m['yapistirici_maliyeti']:,.2f} TL")
    print(f"  Derz: {m['derz_maliyeti']:,.2f} TL")
    print(f"  Malzeme Toplam: {m['toplam_malzeme_maliyeti']:,.2f} TL")
    print(f"  Iscilik: {m['iscilik_maliyeti']:,.2f} TL")
    print(f"  GENEL TOPLAM: {m['genel_toplam']:,.2f} TL")
