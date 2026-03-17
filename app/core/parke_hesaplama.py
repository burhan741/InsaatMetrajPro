"""
Laminat Parke ve Supurgelik Hesaplama Modulu
============================================
Oda bazli parke, supurgelik ve silte hesabi.
Kapi dusumlu supurgelik hesaplama ozelligi.

Yazar: Insaat Metraj Pro
Tarih: 2025
"""

import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


# ============================================================================
# SABITLER
# ============================================================================

# Standart kapi genisligi (cm)
STANDART_KAPI_GENISLIGI_CM = 90

# Supurgelik fire orani (kose kesimleri - gonye icin)
SUPURGELIK_FIRE_ORANI = 0.07  # %7

# Iscilik hizi (m2/gun) - 1 Usta + 1 Yardimci
VERIMLILIK_VERITABANI = {
    "piyasa": {
        "hiz_m2_gun": 90,  # 80-100 arasi ortalama
        "aciklama": "Piyasa ortalamasi (1 Usta + 1 Yardimci)"
    },
    "hizli_ekip": {
        "hiz_m2_gun": 100,
        "aciklama": "Deneyimli hizli ekip"
    },
    "yavas_ekip": {
        "hiz_m2_gun": 70,
        "aciklama": "Yavas/yasli ekip veya zor zemin"
    }
}

# Standart parke kutu boyutlari (referans)
STANDART_PARKE_KUTULARI = [
    {"ad": "Kucuk Kutu (1.84 m2)", "m2": 1.84},
    {"ad": "Orta Kutu (2.22 m2)", "m2": 2.22},
    {"ad": "Buyuk Kutu (2.94 m2)", "m2": 2.94},
]

# Standart supurgelik boylari (referans)
STANDART_SUPURGELIK_BOYLARI = [
    {"ad": "Kisa Boy (240 cm)", "cm": 240},
    {"ad": "Standart Boy (280 cm)", "cm": 280},
    {"ad": "Uzun Boy (300 cm)", "cm": 300},
]


@dataclass
class OdaSonuc:
    """Tek bir oda icin hesaplama sonucu"""
    oda_adi: str
    en_cm: float
    boy_cm: float
    kapi_sayisi: int

    # Alan
    net_alan_m2: float = 0.0
    fireli_alan_m2: float = 0.0

    # Supurgelik
    brut_cevre_cm: float = 0.0
    kapi_dusumu_cm: float = 0.0
    net_supurgelik_cm: float = 0.0
    fireli_supurgelik_cm: float = 0.0


@dataclass
class ParkeHesaplamaSonuc:
    """Tum hesaplama sonucu"""
    oda_detaylari: List[OdaSonuc] = field(default_factory=list)

    # Parke toplamlari
    toplam_net_alan_m2: float = 0.0
    toplam_fireli_alan_m2: float = 0.0
    gereken_parke_kutu_adet: int = 0

    # Supurgelik toplamlari
    toplam_brut_cevre_m: float = 0.0
    toplam_kapi_dusumu_m: float = 0.0
    toplam_net_supurgelik_m: float = 0.0
    toplam_fireli_supurgelik_m: float = 0.0
    gereken_supurgelik_boy_adet: int = 0

    # Silte
    gereken_silte_m2: float = 0.0

    # Sure
    tahmini_sure_gun: int = 0
    kullanilan_hiz_m2_gun: float = 0.0

    # Maliyetler
    toplam_parke_maliyet: float = 0.0
    toplam_supurgelik_maliyet: float = 0.0
    toplam_silte_maliyet: float = 0.0
    toplam_iscilik_tl: float = 0.0
    genel_toplam_maliyet_tl: float = 0.0

    # Birim maliyetler
    birim_maliyet_m2: float = 0.0


def hesapla_parke_supurgelik_detayli(
    odalar_listesi: List[Dict[str, Any]],
    parke_kutu_m2: float = 1.84,
    supurgelik_boy_uzunlugu_cm: float = 280,
    parke_kutu_fiyat: float = 850.0,
    supurgelik_boy_fiyat: float = 120.0,
    silte_m2_fiyat: float = 25.0,
    ekip_gunluk_ucret: float = 3500.0,
    fire_orani: float = 0.05,
    verim_kaynagi: str = "piyasa",
    manuel_hiz: Optional[float] = None
) -> Dict[str, Any]:
    """
    Laminat parke ve supurgelik maliyet hesaplama fonksiyonu.

    Oda bazli hesaplama yapar, kapi dusumlu supurgelik hesabi.
    Toplu siparis mantigi ile kutu ve boy adetleri hesaplar.

    Args:
        odalar_listesi: Oda listesi (her eleman sozluk yapisinda)
            - oda_adi: str
            - en_cm: float (Odanin eni - cm)
            - boy_cm: float (Odanin boyu - cm)
            - kapi_sayisi: int (Supurgelik dusumu icin)
        parke_kutu_m2: Bir kutunun kaplayacagi alan (m2)
        supurgelik_boy_uzunlugu_cm: Bir boy supurgelik uzunlugu (cm)
        parke_kutu_fiyat: Parke kutu fiyati (TL)
        supurgelik_boy_fiyat: Supurgelik boy fiyati (TL)
        silte_m2_fiyat: Silte (kapron/kopuk) m2 fiyati (TL)
        ekip_gunluk_ucret: Ekip gunluk ucreti (TL)
        fire_orani: Parke fire orani (Varsayilan: 0.05 = %5)
        verim_kaynagi: Verimlilik kaynagi ("piyasa" veya "manuel")
        manuel_hiz: Manuel verimlilik degeri (m2/gun)

    Returns:
        Detayli hesaplama sonucu sozlugu
    """

    # ========================================================================
    # VALIDASYON
    # ========================================================================
    if not odalar_listesi:
        raise ValueError("En az bir oda girilmelidir")

    if parke_kutu_m2 <= 0:
        raise ValueError("Parke kutu m2 degeri 0'dan buyuk olmalidir")

    if supurgelik_boy_uzunlugu_cm <= 0:
        raise ValueError("Supurgelik boy uzunlugu 0'dan buyuk olmalidir")

    if fire_orani < 0 or fire_orani > 0.3:
        raise ValueError("Fire orani 0 ile 0.3 arasinda olmalidir")

    if verim_kaynagi == "manuel" and (manuel_hiz is None or manuel_hiz <= 0):
        raise ValueError("Manuel verim kaynagi secildiginde gecerli bir hiz girilmelidir")

    # ========================================================================
    # ODA BAZLI HESAPLAMA
    # ========================================================================
    oda_sonuclari = []

    toplam_net_alan = 0.0
    toplam_fireli_alan = 0.0
    toplam_brut_cevre = 0.0
    toplam_kapi_dusumu = 0.0
    toplam_net_supurgelik = 0.0
    toplam_fireli_supurgelik = 0.0

    for oda_dict in odalar_listesi:
        oda_adi = oda_dict.get("oda_adi", "Oda")
        en_cm = float(oda_dict.get("en_cm", 0))
        boy_cm = float(oda_dict.get("boy_cm", 0))
        kapi_sayisi = int(oda_dict.get("kapi_sayisi", 0))

        if en_cm <= 0 or boy_cm <= 0:
            continue

        # --- PARKE HESABI ---
        # Net alan (m2)
        net_alan_m2 = (en_cm * boy_cm) / 10000

        # Fireli alan
        fireli_alan_m2 = net_alan_m2 * (1 + fire_orani)

        # --- SUPURGELIK HESABI ---
        # Brut cevre (cm)
        brut_cevre_cm = 2 * (en_cm + boy_cm)

        # Kapi dusumu (cm)
        kapi_dusumu_cm = kapi_sayisi * STANDART_KAPI_GENISLIGI_CM

        # Net supurgelik (cm)
        net_supurgelik_cm = brut_cevre_cm - kapi_dusumu_cm

        # Fireli supurgelik (kose kesimleri icin %7 fire)
        fireli_supurgelik_cm = net_supurgelik_cm * (1 + SUPURGELIK_FIRE_ORANI)

        # Sonucu kaydet
        oda_sonuc = OdaSonuc(
            oda_adi=oda_adi,
            en_cm=en_cm,
            boy_cm=boy_cm,
            kapi_sayisi=kapi_sayisi,
            net_alan_m2=net_alan_m2,
            fireli_alan_m2=fireli_alan_m2,
            brut_cevre_cm=brut_cevre_cm,
            kapi_dusumu_cm=kapi_dusumu_cm,
            net_supurgelik_cm=net_supurgelik_cm,
            fireli_supurgelik_cm=fireli_supurgelik_cm
        )
        oda_sonuclari.append(oda_sonuc)

        # Toplamlara ekle
        toplam_net_alan += net_alan_m2
        toplam_fireli_alan += fireli_alan_m2
        toplam_brut_cevre += brut_cevre_cm
        toplam_kapi_dusumu += kapi_dusumu_cm
        toplam_net_supurgelik += net_supurgelik_cm
        toplam_fireli_supurgelik += fireli_supurgelik_cm

    # ========================================================================
    # TOPLU SIPARIS HESABI
    # ========================================================================

    # Parke kutu adedi (yukari yuvarla - yarim kutu satilmaz)
    gereken_parke_kutu = math.ceil(toplam_fireli_alan / parke_kutu_m2)

    # Supurgelik boy adedi (yukari yuvarla)
    toplam_fireli_supurgelik_m = toplam_fireli_supurgelik / 100  # cm -> m
    gereken_supurgelik_boy = math.ceil(toplam_fireli_supurgelik / supurgelik_boy_uzunlugu_cm)

    # Silte (parke ile ayni m2 - fireli)
    gereken_silte_m2 = toplam_fireli_alan

    # ========================================================================
    # SURE HESABI
    # ========================================================================
    if verim_kaynagi == "manuel":
        kullanilan_hiz = manuel_hiz
    else:
        kullanilan_hiz = VERIMLILIK_VERITABANI.get(verim_kaynagi, VERIMLILIK_VERITABANI["piyasa"])["hiz_m2_gun"]

    tahmini_sure_gun = math.ceil(toplam_net_alan / kullanilan_hiz) if toplam_net_alan > 0 else 1
    tahmini_sure_gun = max(1, tahmini_sure_gun)

    # ========================================================================
    # MALIYET HESABI
    # ========================================================================

    # Malzeme maliyetleri
    toplam_parke_maliyet = gereken_parke_kutu * parke_kutu_fiyat
    toplam_supurgelik_maliyet = gereken_supurgelik_boy * supurgelik_boy_fiyat
    toplam_silte_maliyet = gereken_silte_m2 * silte_m2_fiyat

    toplam_malzeme_maliyet = toplam_parke_maliyet + toplam_supurgelik_maliyet + toplam_silte_maliyet

    # Iscilik maliyeti
    toplam_iscilik = tahmini_sure_gun * ekip_gunluk_ucret

    # Genel toplam
    genel_toplam = toplam_malzeme_maliyet + toplam_iscilik

    # Birim maliyet
    birim_maliyet_m2 = genel_toplam / toplam_net_alan if toplam_net_alan > 0 else 0

    # ========================================================================
    # SONUC SOZLUGU
    # ========================================================================

    return {
        # Oda detaylari
        "oda_detaylari": [
            {
                "oda_adi": s.oda_adi,
                "en_cm": s.en_cm,
                "boy_cm": s.boy_cm,
                "kapi_sayisi": s.kapi_sayisi,
                "net_alan_m2": round(s.net_alan_m2, 2),
                "fireli_alan_m2": round(s.fireli_alan_m2, 2),
                "brut_cevre_m": round(s.brut_cevre_cm / 100, 2),
                "kapi_dusumu_m": round(s.kapi_dusumu_cm / 100, 2),
                "net_supurgelik_m": round(s.net_supurgelik_cm / 100, 2),
                "fireli_supurgelik_m": round(s.fireli_supurgelik_cm / 100, 2),
            }
            for s in oda_sonuclari
        ],

        # Parke toplamlari
        "toplam_net_alan_m2": round(toplam_net_alan, 2),
        "toplam_fireli_alan_m2": round(toplam_fireli_alan, 2),
        "gereken_parke_kutu_adet": gereken_parke_kutu,
        "parke_kutu_m2": parke_kutu_m2,

        # Supurgelik toplamlari
        "toplam_brut_cevre_m": round(toplam_brut_cevre / 100, 2),
        "toplam_kapi_dusumu_m": round(toplam_kapi_dusumu / 100, 2),
        "toplam_net_supurgelik_m": round(toplam_net_supurgelik / 100, 2),
        "toplam_fireli_supurgelik_m": round(toplam_fireli_supurgelik_m, 2),
        "gereken_supurgelik_boy_adet": gereken_supurgelik_boy,
        "supurgelik_boy_uzunlugu_cm": supurgelik_boy_uzunlugu_cm,

        # Silte
        "gereken_silte_m2": round(gereken_silte_m2, 2),

        # Sure ve verimlilik
        "tahmini_sure_gun": tahmini_sure_gun,
        "kullanilan_hiz_m2_gun": kullanilan_hiz,
        "verim_kaynagi": verim_kaynagi,

        # Fire bilgileri
        "parke_fire_orani_yuzde": round(fire_orani * 100, 1),
        "supurgelik_fire_orani_yuzde": round(SUPURGELIK_FIRE_ORANI * 100, 1),

        # Malzeme maliyetleri
        "toplam_parke_maliyet": round(toplam_parke_maliyet, 2),
        "toplam_supurgelik_maliyet": round(toplam_supurgelik_maliyet, 2),
        "toplam_silte_maliyet": round(toplam_silte_maliyet, 2),
        "toplam_malzeme_maliyet": round(toplam_malzeme_maliyet, 2),

        # Iscilik
        "toplam_iscilik_tl": round(toplam_iscilik, 2),

        # Genel toplam
        "genel_toplam_maliyet_tl": round(genel_toplam, 2),
        "birim_maliyet_m2": round(birim_maliyet_m2, 2),

        # Giris parametreleri (referans)
        "giris_parametreleri": {
            "parke_kutu_fiyat": parke_kutu_fiyat,
            "supurgelik_boy_fiyat": supurgelik_boy_fiyat,
            "silte_m2_fiyat": silte_m2_fiyat,
            "ekip_gunluk_ucret": ekip_gunluk_ucret
        }
    }


def hesapla_sadece_supurgelik(
    toplam_cevre_m: float,
    kapi_sayisi: int,
    supurgelik_boy_uzunlugu_cm: float = 280,
    supurgelik_boy_fiyat: float = 120.0
) -> Dict[str, Any]:
    """
    Sadece supurgelik hesabi (hizli hesaplama).

    Args:
        toplam_cevre_m: Toplam cevre (metre)
        kapi_sayisi: Toplam kapi sayisi
        supurgelik_boy_uzunlugu_cm: Bir boy supurgelik uzunlugu
        supurgelik_boy_fiyat: Boy fiyati

    Returns:
        Supurgelik hesaplama sonucu
    """
    toplam_cevre_cm = toplam_cevre_m * 100

    # Kapi dusumu
    kapi_dusumu_cm = kapi_sayisi * STANDART_KAPI_GENISLIGI_CM

    # Net supurgelik
    net_supurgelik_cm = toplam_cevre_cm - kapi_dusumu_cm

    # Fireli supurgelik
    fireli_supurgelik_cm = net_supurgelik_cm * (1 + SUPURGELIK_FIRE_ORANI)

    # Boy adedi
    gereken_boy = math.ceil(fireli_supurgelik_cm / supurgelik_boy_uzunlugu_cm)

    # Maliyet
    toplam_maliyet = gereken_boy * supurgelik_boy_fiyat

    return {
        "brut_cevre_m": toplam_cevre_m,
        "kapi_dusumu_m": round(kapi_dusumu_cm / 100, 2),
        "net_supurgelik_m": round(net_supurgelik_cm / 100, 2),
        "fireli_supurgelik_m": round(fireli_supurgelik_cm / 100, 2),
        "gereken_boy_adet": gereken_boy,
        "toplam_maliyet": round(toplam_maliyet, 2)
    }


# Test
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("LAMINAT PARKE VE SUPURGELIK HESAPLAMA TESTI")
    print("=" * 70)

    # Test odalari
    odalar = [
        {"oda_adi": "Salon", "en_cm": 500, "boy_cm": 700, "kapi_sayisi": 2},
        {"oda_adi": "Yatak Odasi 1", "en_cm": 400, "boy_cm": 450, "kapi_sayisi": 1},
        {"oda_adi": "Yatak Odasi 2", "en_cm": 350, "boy_cm": 400, "kapi_sayisi": 1},
        {"oda_adi": "Cocuk Odasi", "en_cm": 300, "boy_cm": 350, "kapi_sayisi": 1},
        {"oda_adi": "Koridor", "en_cm": 120, "boy_cm": 600, "kapi_sayisi": 0},
    ]

    print("\nTest Odalari:")
    for oda in odalar:
        alan = (oda["en_cm"] * oda["boy_cm"]) / 10000
        cevre = 2 * (oda["en_cm"] + oda["boy_cm"]) / 100
        print(f"  {oda['oda_adi']}: {oda['en_cm']}x{oda['boy_cm']} cm = {alan:.2f} m2, Cevre: {cevre:.2f} m, Kapi: {oda['kapi_sayisi']}")

    # Hesaplama
    sonuc = hesapla_parke_supurgelik_detayli(
        odalar_listesi=odalar,
        parke_kutu_m2=1.84,
        supurgelik_boy_uzunlugu_cm=280,
        parke_kutu_fiyat=850,
        supurgelik_boy_fiyat=120,
        silte_m2_fiyat=25,
        ekip_gunluk_ucret=3500,
        fire_orani=0.05
    )

    print("\n" + "-" * 50)
    print("ODA DETAYLARI")
    print("-" * 50)

    for oda in sonuc["oda_detaylari"]:
        print(f"\n{oda['oda_adi']}:")
        print(f"  Alan: {oda['net_alan_m2']} m2 (Fireli: {oda['fireli_alan_m2']} m2)")
        print(f"  Cevre: {oda['brut_cevre_m']} m - Kapi: {oda['kapi_dusumu_m']} m = {oda['net_supurgelik_m']} m")
        print(f"  Supurgelik (Fireli): {oda['fireli_supurgelik_m']} m")

    print("\n" + "-" * 50)
    print("GENEL TOPLAM")
    print("-" * 50)

    print(f"\nPARKE:")
    print(f"  Net Alan: {sonuc['toplam_net_alan_m2']} m2")
    print(f"  Fireli Alan: {sonuc['toplam_fireli_alan_m2']} m2")
    print(f"  Gereken Kutu: {sonuc['gereken_parke_kutu_adet']} adet ({sonuc['parke_kutu_m2']} m2/kutu)")
    print(f"  Parke Maliyeti: {sonuc['toplam_parke_maliyet']:,.2f} TL")

    print(f"\nSUPURGELIK:")
    print(f"  Brut Cevre: {sonuc['toplam_brut_cevre_m']} m")
    print(f"  Kapi Dusumu: {sonuc['toplam_kapi_dusumu_m']} m")
    print(f"  Net Supurgelik: {sonuc['toplam_net_supurgelik_m']} m")
    print(f"  Fireli Supurgelik: {sonuc['toplam_fireli_supurgelik_m']} m (+%7 gonye)")
    print(f"  Gereken Boy: {sonuc['gereken_supurgelik_boy_adet']} adet ({sonuc['supurgelik_boy_uzunlugu_cm']} cm/boy)")
    print(f"  Supurgelik Maliyeti: {sonuc['toplam_supurgelik_maliyet']:,.2f} TL")

    print(f"\nSILTE:")
    print(f"  Gereken: {sonuc['gereken_silte_m2']} m2")
    print(f"  Silte Maliyeti: {sonuc['toplam_silte_maliyet']:,.2f} TL")

    print(f"\nISCILIK:")
    print(f"  Sure: {sonuc['tahmini_sure_gun']} gun ({sonuc['kullanilan_hiz_m2_gun']} m2/gun)")
    print(f"  Iscilik Maliyeti: {sonuc['toplam_iscilik_tl']:,.2f} TL")

    print("\n" + "-" * 50)
    print("MALIYET OZETI")
    print("-" * 50)
    print(f"  Parke: {sonuc['toplam_parke_maliyet']:,.2f} TL")
    print(f"  Supurgelik: {sonuc['toplam_supurgelik_maliyet']:,.2f} TL")
    print(f"  Silte: {sonuc['toplam_silte_maliyet']:,.2f} TL")
    print(f"  Malzeme Toplam: {sonuc['toplam_malzeme_maliyet']:,.2f} TL")
    print(f"  Iscilik: {sonuc['toplam_iscilik_tl']:,.2f} TL")
    print(f"  GENEL TOPLAM: {sonuc['genel_toplam_maliyet_tl']:,.2f} TL")
    print(f"  Birim Maliyet: {sonuc['birim_maliyet_m2']:.2f} TL/m2")
