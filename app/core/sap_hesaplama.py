"""
Sap (Tesviye Betonu) Maliyet Hesaplama Modulu
=============================================
300 Dozaj sap icin malzeme, iscilik ve maliyet hesabi.

Yazar: Insaat Metraj Pro
Tarih: 2025
"""

import math
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class UygulamaYontemi(Enum):
    """Uygulama yontemi enum"""
    ELLE_KARA_USULU = "elle_kara_usulu"
    MAKINELI_POMPA_HELIKOPTER = "makineli_pompa_helikopter"


class VerimKaynagi(Enum):
    """Verim kaynagi enum"""
    PIYASA = "piyasa"
    CSB_RESMI = "csb_resmi"
    MANUEL = "manuel"


# ============================================================================
# SABITLER - MALZEME KARISIM ORANLARI (300 Dozaj Sap)
# ============================================================================

# Kum sarfiyati: 1 m3 sikismis sap icin ~1.1 m3 kum
KUM_SARFIYAT_M3_PER_M3 = 1.1

# Cimento sarfiyati: 1 m3 sap icin 350 kg (7 torba x 50kg)
CIMENTO_KG_PER_M3 = 350
CIMENTO_TORBA_KG = 50
CIMENTO_TORBA_PER_M3 = CIMENTO_KG_PER_M3 / CIMENTO_TORBA_KG  # 7 torba

# ============================================================================
# SABITLER - ISCILIK HIZI (M2/GUN)
# ============================================================================

# Verimlilik veritabani - yontem ve kaynaga gore
VERIMLILIK_VERITABANI = {
    "elle_kara_usulu": {
        "piyasa": 32.5,   # Gercekci piyasa (30-35 arasi ortalama)
        "csb_resmi": 25.0,  # Bakanlik resmi analizi (daha konservatif)
        "aciklama": "Harc yerde karilir, el arabasiyla tasinir, mastarlanir. Yorucu is."
    },
    "makineli_pompa_helikopter": {
        "piyasa": 225.0,  # Gercekci piyasa (200-250 arasi ortalama)
        "csb_resmi": 200.0,
        "aciklama": "Hazir harc pompalidir, helikopter perdah makinesiyle duzlenir. Hizli ve kaliteli."
    }
}


@dataclass
class SapHesaplamaSonuc:
    """Sap hesaplama sonuc veri sinifi"""
    # Hacim ve malzeme
    dokulen_hacim_m3: float
    gereken_kum_m3: float
    gereken_cimento_kg: float
    gereken_cimento_torba: int

    # Sure
    tahmini_sure_gun: int
    kullanilan_hiz_m2_gun: float

    # Bilgiler
    uygulama_turu: str
    uygulama_aciklama: str
    verim_kaynagi: str

    # Maliyetler
    kum_maliyet_tl: float
    cimento_maliyet_tl: float
    toplam_malzeme_tl: float
    toplam_iscilik_tl: float
    toplam_makine_kira_tl: float
    genel_toplam_maliyet_tl: float

    # Birim maliyetler
    birim_maliyet_m2: float
    birim_maliyet_m3: float


def hesapla_sap_maliyet_detayli(
    uygulama_alani_m2: float,
    ortalama_kalinlik_cm: float = 5.0,
    uygulama_yontemi: str = "elle_kara_usulu",
    kum_m3_fiyat: float = 450.0,
    cimento_torba_fiyat: float = 180.0,
    ekip_gunluk_ucret: float = 4000.0,
    pompa_gunluk_kira: float = 3500.0,
    fire_orani: float = 0.05,
    verim_kaynagi: str = "piyasa",
    manuel_hiz: Optional[float] = None
) -> Dict[str, Any]:
    """
    Sap (Tesviye Betonu) maliyet hesaplama fonksiyonu.

    300 Dozaj sap icin malzeme, iscilik ve toplam maliyet hesabi yapar.
    Elle ve makineli yontemler icin farkli verimlilik degerleri kullanir.

    Args:
        uygulama_alani_m2: Sap dokulecek alan (m2)
        ortalama_kalinlik_cm: Ortalama sap kalinligi (cm) - Varsayilan: 5.0
        uygulama_yontemi: Uygulama yontemi
            - "elle_kara_usulu": Manuel uygulama (30-35 m2/gun)
            - "makineli_pompa_helikopter": Pompali + helikopter (200-250 m2/gun)
        kum_m3_fiyat: Kum m3 fiyati (TL)
        cimento_torba_fiyat: Cimento torba fiyati (50kg) (TL)
        ekip_gunluk_ucret: Ekip gunluk ucreti (TL)
        pompa_gunluk_kira: Pompa gunluk kira bedeli (TL) - Sadece makineli icin
        fire_orani: Fire orani (Ornek: 0.05 = %5)
        verim_kaynagi: Verimlilik kaynagi
            - "piyasa": Gercekci piyasa degerleri
            - "csb_resmi": CSB Bakanlik resmi analiz degerleri
            - "manuel": Kullanicinin girdigi deger
        manuel_hiz: Manuel verimlilik degeri (m2/gun) - Sadece verim_kaynagi="manuel" ise

    Returns:
        Detayli hesaplama sonucu sozlugu

    Raises:
        ValueError: Gecersiz parametre degerleri icin
    """

    # ========================================================================
    # VALIDASYON
    # ========================================================================
    if uygulama_alani_m2 <= 0:
        raise ValueError("Uygulama alani 0'dan buyuk olmalidir")

    if ortalama_kalinlik_cm <= 0:
        raise ValueError("Kalinlik 0'dan buyuk olmalidir")

    if uygulama_yontemi not in ["elle_kara_usulu", "makineli_pompa_helikopter"]:
        raise ValueError(f"Gecersiz uygulama yontemi: {uygulama_yontemi}")

    if verim_kaynagi not in ["piyasa", "csb_resmi", "manuel"]:
        raise ValueError(f"Gecersiz verim kaynagi: {verim_kaynagi}")

    if verim_kaynagi == "manuel" and (manuel_hiz is None or manuel_hiz <= 0):
        raise ValueError("Manuel verim kaynagi secildiginde gecerli bir hiz girilmelidir")

    if fire_orani < 0 or fire_orani > 0.5:
        raise ValueError("Fire orani 0 ile 0.5 arasinda olmalidir")

    # ========================================================================
    # ADIM 1: HACIM VE MALZEME HESABI
    # ========================================================================

    # Toplam hacim (m3)
    dokulen_hacim_m3 = uygulama_alani_m2 * (ortalama_kalinlik_cm / 100)

    # Fire dahil hacim
    hacim_fireli = dokulen_hacim_m3 * (1 + fire_orani)

    # Kum ihtiyaci (m3) - 1 m3 sap = 1.1 m3 kum
    gereken_kum_m3 = hacim_fireli * KUM_SARFIYAT_M3_PER_M3

    # Cimento ihtiyaci - 1 m3 sap = 7 torba (350 kg)
    gereken_cimento_kg = hacim_fireli * CIMENTO_KG_PER_M3
    gereken_cimento_torba = math.ceil(hacim_fireli * CIMENTO_TORBA_PER_M3)

    # ========================================================================
    # ADIM 2: SURE HESABI
    # ========================================================================

    # Verimlilik degerini al
    if verim_kaynagi == "manuel":
        kullanilan_hiz = manuel_hiz
    else:
        kullanilan_hiz = VERIMLILIK_VERITABANI[uygulama_yontemi][verim_kaynagi]

    # Sure hesabi (gun) - yukari yuvarla
    tahmini_sure_gun = math.ceil(uygulama_alani_m2 / kullanilan_hiz)

    # Minimum 1 gun
    tahmini_sure_gun = max(1, tahmini_sure_gun)

    # ========================================================================
    # ADIM 3: MALIYET HESABI
    # ========================================================================

    # Malzeme maliyetleri
    kum_maliyet = gereken_kum_m3 * kum_m3_fiyat
    cimento_maliyet = gereken_cimento_torba * cimento_torba_fiyat
    toplam_malzeme = kum_maliyet + cimento_maliyet

    # Iscilik maliyeti
    toplam_iscilik = tahmini_sure_gun * ekip_gunluk_ucret

    # Makine kira maliyeti (sadece makineli yontem icin)
    if uygulama_yontemi == "makineli_pompa_helikopter":
        toplam_makine_kira = tahmini_sure_gun * pompa_gunluk_kira
    else:
        toplam_makine_kira = 0.0

    # Genel toplam
    genel_toplam = toplam_malzeme + toplam_iscilik + toplam_makine_kira

    # Birim maliyetler
    birim_maliyet_m2 = genel_toplam / uygulama_alani_m2 if uygulama_alani_m2 > 0 else 0
    birim_maliyet_m3 = genel_toplam / dokulen_hacim_m3 if dokulen_hacim_m3 > 0 else 0

    # ========================================================================
    # ADIM 4: UYGULAMA BILGILERI
    # ========================================================================

    # Uygulama turu adi
    uygulama_turleri = {
        "elle_kara_usulu": "Elle Kara Usulu (Manuel)",
        "makineli_pompa_helikopter": "Makineli Pompa + Helikopter Perdah"
    }
    uygulama_turu = uygulama_turleri.get(uygulama_yontemi, uygulama_yontemi)

    # Uygulama aciklamasi
    uygulama_aciklama = VERIMLILIK_VERITABANI[uygulama_yontemi]["aciklama"]

    # Verim kaynagi adi
    verim_kaynagi_adlari = {
        "piyasa": "Piyasa (Gercekci)",
        "csb_resmi": "CSB Resmi Analiz",
        "manuel": "Manuel Giris"
    }
    verim_kaynagi_adi = verim_kaynagi_adlari.get(verim_kaynagi, verim_kaynagi)

    # ========================================================================
    # SONUC SOZLUGU
    # ========================================================================

    return {
        # Hacim ve malzeme
        "dokulen_hacim_m3": round(dokulen_hacim_m3, 3),
        "hacim_fireli_m3": round(hacim_fireli, 3),
        "gereken_kum_m3": round(gereken_kum_m3, 2),
        "gereken_cimento_kg": round(gereken_cimento_kg, 1),
        "gereken_cimento_torba": gereken_cimento_torba,

        # Sure ve verimlilik
        "tahmini_sure_gun": tahmini_sure_gun,
        "kullanilan_hiz_m2_gun": kullanilan_hiz,

        # Bilgiler
        "uygulama_yontemi": uygulama_yontemi,
        "uygulama_turu": uygulama_turu,
        "uygulama_aciklama": uygulama_aciklama,
        "verim_kaynagi": verim_kaynagi,
        "verim_kaynagi_adi": verim_kaynagi_adi,
        "fire_orani_yuzde": round(fire_orani * 100, 1),

        # Malzeme maliyetleri
        "kum_maliyet_tl": round(kum_maliyet, 2),
        "cimento_maliyet_tl": round(cimento_maliyet, 2),
        "toplam_malzeme_tl": round(toplam_malzeme, 2),

        # Diger maliyetler
        "toplam_iscilik_tl": round(toplam_iscilik, 2),
        "toplam_makine_kira_tl": round(toplam_makine_kira, 2),

        # Toplam
        "genel_toplam_maliyet_tl": round(genel_toplam, 2),

        # Birim maliyetler
        "birim_maliyet_m2": round(birim_maliyet_m2, 2),
        "birim_maliyet_m3": round(birim_maliyet_m3, 2),

        # Giris parametreleri (referans icin)
        "giris_parametreleri": {
            "uygulama_alani_m2": uygulama_alani_m2,
            "ortalama_kalinlik_cm": ortalama_kalinlik_cm,
            "kum_m3_fiyat": kum_m3_fiyat,
            "cimento_torba_fiyat": cimento_torba_fiyat,
            "ekip_gunluk_ucret": ekip_gunluk_ucret,
            "pompa_gunluk_kira": pompa_gunluk_kira
        }
    }


def karsilastir_yontemler(
    uygulama_alani_m2: float,
    ortalama_kalinlik_cm: float = 5.0,
    kum_m3_fiyat: float = 450.0,
    cimento_torba_fiyat: float = 180.0,
    ekip_gunluk_ucret: float = 4000.0,
    pompa_gunluk_kira: float = 3500.0,
    fire_orani: float = 0.05
) -> Dict[str, Any]:
    """
    Elle ve makineli yontemleri karsilastir.

    Args:
        uygulama_alani_m2: Uygulama alani
        ortalama_kalinlik_cm: Ortalama kalinlik
        kum_m3_fiyat: Kum fiyati
        cimento_torba_fiyat: Cimento fiyati
        ekip_gunluk_ucret: Ekip ucreti
        pompa_gunluk_kira: Pompa kirasi
        fire_orani: Fire orani

    Returns:
        Karsilastirma sonucu
    """
    # Elle hesapla
    elle_sonuc = hesapla_sap_maliyet_detayli(
        uygulama_alani_m2=uygulama_alani_m2,
        ortalama_kalinlik_cm=ortalama_kalinlik_cm,
        uygulama_yontemi="elle_kara_usulu",
        kum_m3_fiyat=kum_m3_fiyat,
        cimento_torba_fiyat=cimento_torba_fiyat,
        ekip_gunluk_ucret=ekip_gunluk_ucret,
        pompa_gunluk_kira=0,
        fire_orani=fire_orani
    )

    # Makineli hesapla
    makineli_sonuc = hesapla_sap_maliyet_detayli(
        uygulama_alani_m2=uygulama_alani_m2,
        ortalama_kalinlik_cm=ortalama_kalinlik_cm,
        uygulama_yontemi="makineli_pompa_helikopter",
        kum_m3_fiyat=kum_m3_fiyat,
        cimento_torba_fiyat=cimento_torba_fiyat,
        ekip_gunluk_ucret=ekip_gunluk_ucret,
        pompa_gunluk_kira=pompa_gunluk_kira,
        fire_orani=fire_orani
    )

    # Fark hesapla
    maliyet_farki = elle_sonuc["genel_toplam_maliyet_tl"] - makineli_sonuc["genel_toplam_maliyet_tl"]
    sure_farki = elle_sonuc["tahmini_sure_gun"] - makineli_sonuc["tahmini_sure_gun"]

    # Tavsiye
    if maliyet_farki > 0:
        tavsiye = "makineli"
        tavsiye_aciklama = f"Makineli yontem {abs(maliyet_farki):,.0f} TL daha ucuz ve {abs(sure_farki)} gun daha hizli."
    elif maliyet_farki < 0:
        tavsiye = "elle"
        tavsiye_aciklama = f"Elle yontem {abs(maliyet_farki):,.0f} TL daha ucuz ama {abs(sure_farki)} gun daha yavas."
    else:
        tavsiye = "makineli"
        tavsiye_aciklama = f"Maliyetler esit, makineli yontem {abs(sure_farki)} gun daha hizli."

    # Buyuk alanlarda makineli her zaman tavsiye edilir
    if uygulama_alani_m2 > 200:
        tavsiye = "makineli"
        tavsiye_aciklama += " Buyuk alanlar icin makineli yontem kesinlikle onerilir."

    return {
        "elle": elle_sonuc,
        "makineli": makineli_sonuc,
        "maliyet_farki_tl": round(maliyet_farki, 2),
        "sure_farki_gun": sure_farki,
        "tavsiye_edilen": tavsiye,
        "tavsiye_aciklama": tavsiye_aciklama
    }


# Test
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("SAP (TESVIYE BETONU) MALIYET HESAPLAMA TESTI")
    print("=" * 70)

    # Test parametreleri
    alan = 150  # m2
    kalinlik = 5  # cm

    print(f"\nTest Parametreleri:")
    print(f"  Alan: {alan} m2")
    print(f"  Kalinlik: {kalinlik} cm")
    print(f"  Hacim: {alan * kalinlik / 100:.2f} m3")

    # Elle yontem
    print("\n" + "-" * 50)
    print("1. ELLE KARA USULU")
    print("-" * 50)

    elle = hesapla_sap_maliyet_detayli(
        uygulama_alani_m2=alan,
        ortalama_kalinlik_cm=kalinlik,
        uygulama_yontemi="elle_kara_usulu"
    )

    print(f"  Hacim: {elle['dokulen_hacim_m3']} m3")
    print(f"  Kum: {elle['gereken_kum_m3']} m3")
    print(f"  Cimento: {elle['gereken_cimento_torba']} torba")
    print(f"  Sure: {elle['tahmini_sure_gun']} gun ({elle['kullanilan_hiz_m2_gun']} m2/gun)")
    print(f"  Malzeme: {elle['toplam_malzeme_tl']:,.2f} TL")
    print(f"  Iscilik: {elle['toplam_iscilik_tl']:,.2f} TL")
    print(f"  TOPLAM: {elle['genel_toplam_maliyet_tl']:,.2f} TL")
    print(f"  Birim: {elle['birim_maliyet_m2']:.2f} TL/m2")

    # Makineli yontem
    print("\n" + "-" * 50)
    print("2. MAKINELI POMPA + HELIKOPTER")
    print("-" * 50)

    makineli = hesapla_sap_maliyet_detayli(
        uygulama_alani_m2=alan,
        ortalama_kalinlik_cm=kalinlik,
        uygulama_yontemi="makineli_pompa_helikopter"
    )

    print(f"  Hacim: {makineli['dokulen_hacim_m3']} m3")
    print(f"  Kum: {makineli['gereken_kum_m3']} m3")
    print(f"  Cimento: {makineli['gereken_cimento_torba']} torba")
    print(f"  Sure: {makineli['tahmini_sure_gun']} gun ({makineli['kullanilan_hiz_m2_gun']} m2/gun)")
    print(f"  Malzeme: {makineli['toplam_malzeme_tl']:,.2f} TL")
    print(f"  Iscilik: {makineli['toplam_iscilik_tl']:,.2f} TL")
    print(f"  Makine Kira: {makineli['toplam_makine_kira_tl']:,.2f} TL")
    print(f"  TOPLAM: {makineli['genel_toplam_maliyet_tl']:,.2f} TL")
    print(f"  Birim: {makineli['birim_maliyet_m2']:.2f} TL/m2")

    # Karsilastirma
    print("\n" + "-" * 50)
    print("3. KARSILASTIRMA")
    print("-" * 50)

    karsilastirma = karsilastir_yontemler(alan, kalinlik)
    print(f"  Maliyet Farki: {karsilastirma['maliyet_farki_tl']:,.2f} TL")
    print(f"  Sure Farki: {karsilastirma['sure_farki_gun']} gun")
    print(f"  Tavsiye: {karsilastirma['tavsiye_edilen'].upper()}")
    print(f"  Aciklama: {karsilastirma['tavsiye_aciklama']}")
