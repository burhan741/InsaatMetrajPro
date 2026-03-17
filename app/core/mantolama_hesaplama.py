"""
Dis Cephe Mantolama Minha Hesaplama Modulu
==========================================
Yonetmeliklere uygun bosluk dusme (Minha) hesabi.
EPS Karbonlu ve Tas Yunu sistemleri icin malzeme ve iscilik hesabi.

Yazar: Insaat Metraj Pro
Tarih: 2025
"""

import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


# ============================================================================
# SABITLER
# ============================================================================

class LevhaTipi(Enum):
    """Izolasyon levha tipi"""
    EPS_KARBONLU = "eps_karbonlu"
    TAS_YUNU = "tas_yunu"


# Minha (Bosluk Dusme) Limiti - Varsayilan 3 m2
# Bu degerden kucuk bosluklar dusulmez
VARSAYILAN_MINHA_LIMITI_M2 = 3.0

# Denizlik donus derinligi (cm) - Pencere icleri icin
DENIZLIK_DONUS_DERINLIGI_CM = 20

# Dubel sayisi - Deprem yonetmeligi geregi
DUBEL_ADET_PER_M2 = 8

# Malzeme sarfiyatlari (m2 basina)
MALZEME_SARFIYAT = {
"eps_karbonlu": {
"levha_m2": 1.03,
"yapistirici_kg": 5.0,
"siva_kg": 4.0,
"file_m2": 1.15,
"astar_kg": 0.25,
"son_kat_boya_kg": 0.35,
"dubel_adet": DUBEL_ADET_PER_M2,
"kose_profili_m": 0.0,
"levha_kalinlik_cm": 5,
"aciklama": "EPS Karbonlu (Grafit Katkilı) - Yuksek izolasyon"
},
"tas_yunu": {
"levha_m2": 1.03,
"yapistirici_kg": 6.0,
"siva_kg": 5.0,
"file_m2": 1.15,
"astar_kg": 0.25,
"son_kat_boya_kg": 0.35,
"dubel_adet": DUBEL_ADET_PER_M2,
"kose_profili_m": 0.0,
"levha_kalinlik_cm": 5,
"aciklama": "Tas Yunu - Yangin dayanimi yuksek (A1 sinifi)"
}
}

# Varsayilan birim fiyatlar (TL) - 2025 guncel
VARSAYILAN_FIYATLAR = {
"eps_karbonlu": {
"levha_m2": 180.0,
"yapistirici_torba": 450.0,
"siva_torba": 420.0,
"file_m2": 35.0,
"astar_kg": 85.0,
"son_kat_boya_kg": 120.0,
"dubel_adet": 3.5,
"kose_profili_m": 18.0,
"denizlik_profili_m": 45.0,
},
"tas_yunu": {
"levha_m2": 280.0,
"yapistirici_torba": 480.0,
"siva_torba": 450.0,
"file_m2": 35.0,
"astar_kg": 85.0,
"son_kat_boya_kg": 120.0,
"dubel_adet": 4.0,
"kose_profili_m": 18.0,
"denizlik_profili_m": 45.0,
}
}

# Torba agirliklari
YAPISTIRICI_TORBA_KG = 25
SIVA_TORBA_KG = 25

# Iscilik hizi (m2/gun) - 2 kisilik ekip
VERIMLILIK = {
"eps_karbonlu": {
"piyasa": 25,
"csb_resmi": 18,
},
"tas_yunu": {
"piyasa": 20,
"csb_resmi": 15,
}
}

# Iskele kirasi
ISKELE_GUNLUK_KIRA_M2 = 8.0


@dataclass
class BoslukBilgisi:
    """Tek bir bosluk (pencere/kapi) bilgisi"""
    en_cm: float
    boy_cm: float
    adet: int = 1
    denizlik_donulecek_mi: bool = True
    aciklama: str = ""

    @property
    def alan_m2(self) -> float:
        """Tek bosluk alani (m2)"""
        return (self.en_cm * self.boy_cm) / 10000

    @property
    def toplam_alan_m2(self) -> float:
        """Tum bosluk alani (adet dahil)"""
        return self.alan_m2 * self.adet

    @property
    def cevre_m(self) -> float:
        """Tek bosluk cevresi (m)"""
        return 2 * (self.en_cm + self.boy_cm) / 100

    @property
    def denizlik_donus_m(self) -> float:
        """Denizlik donus uzunlugu (yanlar + ust) (m)"""
        return (2 * self.boy_cm + self.en_cm) / 100


@dataclass
class MinhaAnalizi:
    """Minha (bosluk dusme) analiz sonucu"""
    bosluk_aciklama: str
    tek_alan_m2: float
    adet: int
    toplam_alan_m2: float
    minha_limiti_m2: float
    dusuldu_mu: bool
    dusulen_alan_m2: float
    denizlik_donusu_m2: float
    denizlik_donus_uzunlugu_m: float
    net_etki_m2: float


@dataclass
class MalzemeKalemi:
    """Malzeme kalemi"""
    ad: str
    miktar: float
    birim: str
    birim_fiyat: float
    toplam_fiyat: float


def hesapla_mantolama_minhali(
    brut_cephe_alani_m2: float,
    bosluklar_listesi: List[Dict[str, Any]],
    levha_tipi: str = "eps_karbonlu",
    malzeme_fiyatlari: Optional[Dict[str, float]] = None,
    ekip_gunluk_ucret: float = 4500.0,
    iskele_dahil: bool = True,
    minha_limiti_m2: float = VARSAYILAN_MINHA_LIMITI_M2,
    bina_kat_sayisi: int = 4,
    verim_kaynagi: str = "piyasa",
    manuel_hiz: Optional[float] = None
) -> Dict[str, Any]:
    """
    Dis cephe mantolama minha hesaplama fonksiyonu.

    Yonetmeliklere uygun bosluk dusme (Minha) kurallari uygulanir.
    minha_limiti_m2 altindaki bosluklar dusulmez.

    Args:
        brut_cephe_alani_m2: Binanin distan disa toplam duvar alani
        bosluklar_listesi: Pencere/kapi listesi
        levha_tipi: "eps_karbonlu" veya "tas_yunu"
        malzeme_fiyatlari: Ozel fiyatlar (None ise varsayilan)
        ekip_gunluk_ucret: Ekip gunluk ucreti (TL)
        iskele_dahil: Iskele maliyeti dahil edilsin mi
        minha_limiti_m2: Bu degerden kucuk bosluklar dusulmez
        bina_kat_sayisi: Bina kat sayisi (iskele hesabi icin)
        verim_kaynagi: "piyasa" veya "manuel"
        manuel_hiz: Manuel verimlilik degeri (m2/gun)

    Returns:
        Detayli hesaplama sonucu sozlugu
    """
    # ========================================================================
    # VALIDASYON (sequential - not nested)
    # ========================================================================
    if brut_cephe_alani_m2 <= 0:
        raise ValueError("Brut cephe alani 0'dan buyuk olmalidir")
    if levha_tipi not in ["eps_karbonlu", "tas_yunu"]:
        raise ValueError(f"Gecersiz levha tipi: {levha_tipi}")
    if minha_limiti_m2 < 0:
        raise ValueError("Minha limiti negatif olamaz")

    # Fiyatlari ayarla
    if malzeme_fiyatlari is None:
        fiyatlar = VARSAYILAN_FIYATLAR[levha_tipi].copy()
    else:
        fiyatlar = VARSAYILAN_FIYATLAR[levha_tipi].copy()
        fiyatlar.update(malzeme_fiyatlari)

    sarfiyat = MALZEME_SARFIYAT[levha_tipi]

    # ========================================================================
    # ADIM 1: BOSLUK ANALIZI (MINHA KURALI)
    # ========================================================================
    minha_analizleri = []
    toplam_dusulen_alan = 0.0
    toplam_eklenen_denizlik = 0.0
    toplam_denizlik_uzunlugu = 0.0
    toplam_pencere_kapi_sayisi = 0
    toplam_kose_profil_uzunlugu = 0.0
    dusulmeyen_bosluk_sayisi = 0
    dusulmeyen_toplam_alan = 0.0

    for bosluk_dict in bosluklar_listesi:
        en_cm = float(bosluk_dict.get("en_cm", 0))
        boy_cm = float(bosluk_dict.get("boy_cm", 0))
        adet = int(bosluk_dict.get("adet", 1))
        denizlik_donulecek = bosluk_dict.get("denizlik_donulecek_mi", True)
        aciklama = bosluk_dict.get("aciklama", f"{en_cm}x{boy_cm} cm")

        if en_cm <= 0 or boy_cm <= 0 or adet <= 0:
            continue

        bosluk = BoslukBilgisi(
            en_cm=en_cm,
            boy_cm=boy_cm,
            adet=adet,
            denizlik_donulecek_mi=denizlik_donulecek,
            aciklama=aciklama
        )

        toplam_pencere_kapi_sayisi += adet
        tek_alan = bosluk.alan_m2
        toplam_alan = bosluk.toplam_alan_m2

        if tek_alan < minha_limiti_m2:
            # KUCUK BOSLUK - Dusulmez
            dusuldu_mu = False
            dusulen_alan = 0.0
            denizlik_donus_m2 = 0.0
            denizlik_uzunluk = 0.0
            net_etki = 0.0
            dusulmeyen_bosluk_sayisi += adet
            dusulmeyen_toplam_alan += toplam_alan
            toplam_kose_profil_uzunlugu += bosluk.cevre_m * adet
        else:
            # BUYUK BOSLUK - Dusulur
            dusuldu_mu = True
            dusulen_alan = toplam_alan
            toplam_dusulen_alan += dusulen_alan
            if denizlik_donulecek:
                donus_uzunlugu_tek = bosluk.denizlik_donus_m
                donus_uzunlugu_toplam = donus_uzunlugu_tek * adet
                donus_alani = donus_uzunlugu_toplam * (DENIZLIK_DONUS_DERINLIGI_CM / 100)
                denizlik_donus_m2 = donus_alani
                denizlik_uzunluk = donus_uzunlugu_toplam
                toplam_eklenen_denizlik += denizlik_donus_m2
                toplam_denizlik_uzunlugu += denizlik_uzunluk
            else:
                denizlik_donus_m2 = 0.0
                denizlik_uzunluk = 0.0
            net_etki = dusulen_alan - denizlik_donus_m2
            toplam_kose_profil_uzunlugu += bosluk.cevre_m * adet

        analiz = MinhaAnalizi(
            bosluk_aciklama=aciklama,
            tek_alan_m2=round(tek_alan, 3),
            adet=adet,
            toplam_alan_m2=round(toplam_alan, 2),
            minha_limiti_m2=minha_limiti_m2,
            dusuldu_mu=dusuldu_mu,
            dusulen_alan_m2=round(dusulen_alan, 2),
            denizlik_donusu_m2=round(denizlik_donus_m2, 2),
            denizlik_donus_uzunlugu_m=round(denizlik_uzunluk, 2),
            net_etki_m2=round(net_etki, 2)
        )
        minha_analizleri.append(analiz)

    # ========================================================================
    # ADIM 2: NET ALAN HESABI
    # ========================================================================
    uygulamaya_esas_net_alan = (
        brut_cephe_alani_m2 - toplam_dusulen_alan + toplam_eklenen_denizlik
    )

    # ========================================================================
    # ADIM 3: MALZEME HESABI
    # ========================================================================
    malzeme_listesi = []

    # Levha
    levha_m2 = uygulamaya_esas_net_alan * sarfiyat["levha_m2"]
    malzeme_listesi.append(MalzemeKalemi(
        ad=f"Izolasyon Levhasi ({sarfiyat['levha_kalinlik_cm']}cm {levha_tipi.replace('_', ' ').title()})",
        miktar=round(levha_m2, 2),
        birim="m2",
        birim_fiyat=fiyatlar["levha_m2"],
        toplam_fiyat=round(levha_m2 * fiyatlar["levha_m2"], 2)
    ))

    # Yapistirici
    yapistirici_kg = uygulamaya_esas_net_alan * sarfiyat["yapistirici_kg"]
    yapistirici_torba = math.ceil(yapistirici_kg / YAPISTIRICI_TORBA_KG)
    malzeme_listesi.append(MalzemeKalemi(
        ad="Yapistirici Harci",
        miktar=yapistirici_torba,
        birim="torba (25kg)",
        birim_fiyat=fiyatlar["yapistirici_torba"],
        toplam_fiyat=round(yapistirici_torba * fiyatlar["yapistirici_torba"], 2)
    ))

    # Siva
    siva_kg = uygulamaya_esas_net_alan * sarfiyat["siva_kg"]
    siva_torba = math.ceil(siva_kg / SIVA_TORBA_KG)
    malzeme_listesi.append(MalzemeKalemi(
        ad="Mantolama Sivasi",
        miktar=siva_torba,
        birim="torba (25kg)",
        birim_fiyat=fiyatlar["siva_torba"],
        toplam_fiyat=round(siva_torba * fiyatlar["siva_torba"], 2)
    ))

    # File
    file_m2 = uygulamaya_esas_net_alan * sarfiyat["file_m2"]
    malzeme_listesi.append(MalzemeKalemi(
        ad="Dograma Filesi (160gr)",
        miktar=round(file_m2, 2),
        birim="m2",
        birim_fiyat=fiyatlar["file_m2"],
        toplam_fiyat=round(file_m2 * fiyatlar["file_m2"], 2)
    ))

    # Dubel
    dubel_adet = math.ceil(uygulamaya_esas_net_alan * sarfiyat["dubel_adet"])
    malzeme_listesi.append(MalzemeKalemi(
        ad="Plastik Dubel (8 adet/m2 - Deprem Yon.)",
        miktar=dubel_adet,
        birim="adet",
        birim_fiyat=fiyatlar["dubel_adet"],
        toplam_fiyat=round(dubel_adet * fiyatlar["dubel_adet"], 2)
    ))

    # Astar
    astar_kg = uygulamaya_esas_net_alan * sarfiyat["astar_kg"]
    malzeme_listesi.append(MalzemeKalemi(
        ad="Astar (Silikonlu)",
        miktar=round(astar_kg, 2),
        birim="kg",
        birim_fiyat=fiyatlar["astar_kg"],
        toplam_fiyat=round(astar_kg * fiyatlar["astar_kg"], 2)
    ))

    # Son kat boya
    boya_kg = uygulamaya_esas_net_alan * sarfiyat["son_kat_boya_kg"]
    malzeme_listesi.append(MalzemeKalemi(
        ad="Son Kat Boya (Silikonlu Dis Cephe)",
        miktar=round(boya_kg, 2),
        birim="kg",
        birim_fiyat=fiyatlar["son_kat_boya_kg"],
        toplam_fiyat=round(boya_kg * fiyatlar["son_kat_boya_kg"], 2)
    ))

    # Kose profili
    malzeme_listesi.append(MalzemeKalemi(
        ad="Kose Profili (PVC + File)",
        miktar=round(toplam_kose_profil_uzunlugu, 2),
        birim="m",
        birim_fiyat=fiyatlar["kose_profili_m"],
        toplam_fiyat=round(toplam_kose_profil_uzunlugu * fiyatlar["kose_profili_m"], 2)
    ))

    # Denizlik profili (aluminyum)
    if toplam_denizlik_uzunlugu > 0:
        malzeme_listesi.append(MalzemeKalemi(
            ad="Denizlik Profili (Aluminyum)",
            miktar=round(toplam_denizlik_uzunlugu, 2),
            birim="m",
            birim_fiyat=fiyatlar["denizlik_profili_m"],
            toplam_fiyat=round(toplam_denizlik_uzunlugu * fiyatlar["denizlik_profili_m"], 2)
        ))

    # Toplam malzeme maliyeti
    toplam_malzeme_maliyet = sum(m.toplam_fiyat for m in malzeme_listesi)

    # ========================================================================
    # ADIM 4: ISCILIK HESABI
    # ========================================================================
    if verim_kaynagi == "manuel" and manuel_hiz:
        kullanilan_hiz = manuel_hiz
    else:
        kullanilan_hiz = VERIMLILIK[levha_tipi].get(
            verim_kaynagi, VERIMLILIK[levha_tipi]["piyasa"]
        )

    tahmini_sure_gun = math.ceil(uygulamaya_esas_net_alan / kullanilan_hiz)
    tahmini_sure_gun = max(1, tahmini_sure_gun)
    toplam_iscilik = tahmini_sure_gun * ekip_gunluk_ucret

    # ========================================================================
    # ADIM 5: ISKELE HESABI
    # ========================================================================
    if iskele_dahil:
        iskele_alani = brut_cephe_alani_m2 * 0.8
        iskele_gun = tahmini_sure_gun + 5
        iskele_maliyet = iskele_alani * iskele_gun * ISKELE_GUNLUK_KIRA_M2
    else:
        iskele_alani = 0
        iskele_gun = 0
        iskele_maliyet = 0

    # ========================================================================
    # ADIM 6: GENEL TOPLAM
    # ========================================================================
    genel_toplam = toplam_malzeme_maliyet + toplam_iscilik + iskele_maliyet
    birim_maliyet_m2 = (
        genel_toplam / uygulamaya_esas_net_alan
        if uygulamaya_esas_net_alan > 0 else 0
    )

    # ========================================================================
    # SONUC SOZLUGU
    # ========================================================================
    return {
        # Giris bilgileri
        "girilen_brut_alan_m2": round(brut_cephe_alani_m2, 2),
        "levha_tipi": levha_tipi,
        "levha_aciklama": sarfiyat["aciklama"],
        "minha_limiti_m2": minha_limiti_m2,

        # Minha analizi
        "minha_analizleri": [
            {
                "aciklama": a.bosluk_aciklama,
                "tek_alan_m2": a.tek_alan_m2,
                "adet": a.adet,
                "toplam_alan_m2": a.toplam_alan_m2,
                "minha_limiti_m2": a.minha_limiti_m2,
                "dusuldu_mu": a.dusuldu_mu,
                "dusulen_alan_m2": a.dusulen_alan_m2,
                "denizlik_donusu_m2": a.denizlik_donusu_m2,
                "denizlik_donus_uzunlugu_m": a.denizlik_donus_uzunlugu_m,
                "net_etki_m2": a.net_etki_m2
            }
            for a in minha_analizleri
        ],

        # Bosluk ozeti
        "toplam_pencere_kapi_sayisi": toplam_pencere_kapi_sayisi,
        "dusulmeyen_bosluk_sayisi": dusulmeyen_bosluk_sayisi,
        "dusulmeyen_toplam_alan_m2": round(dusulmeyen_toplam_alan, 2),
        "dusulen_bosluk_alani_m2": round(toplam_dusulen_alan, 2),
        "eklenen_denizlik_donus_m2": round(toplam_eklenen_denizlik, 2),

        # Net alan
        "uygulamaya_esas_net_alan_m2": round(uygulamaya_esas_net_alan, 2),
        "net_alan_formulu": (
            f"{brut_cephe_alani_m2:.2f} - {toplam_dusulen_alan:.2f} "
            f"+ {toplam_eklenen_denizlik:.2f} = {uygulamaya_esas_net_alan:.2f}"
        ),

        # Malzeme listesi
        "malzeme_listesi": [
            {
                "ad": m.ad,
                "miktar": m.miktar,
                "birim": m.birim,
                "birim_fiyat": m.birim_fiyat,
                "toplam_fiyat": m.toplam_fiyat
            }
            for m in malzeme_listesi
        ],

        # Sure ve verimlilik
        "tahmini_sure_gun": tahmini_sure_gun,
        "kullanilan_hiz_m2_gun": kullanilan_hiz,
        "verim_kaynagi": verim_kaynagi,

        # Maliyet ozeti
        "maliyet_ozeti": {
            "toplam_malzeme_tl": round(toplam_malzeme_maliyet, 2),
            "toplam_iscilik_tl": round(toplam_iscilik, 2),
            "iskele_maliyet_tl": round(iskele_maliyet, 2),
            "genel_toplam_tl": round(genel_toplam, 2),
            "birim_maliyet_m2": round(birim_maliyet_m2, 2)
        },

        # Iskele bilgisi
        "iskele_bilgisi": {
            "dahil_mi": iskele_dahil,
            "iskele_alani_m2": round(iskele_alani, 2),
            "iskele_gun": iskele_gun,
            "gunluk_kira_m2": ISKELE_GUNLUK_KIRA_M2
        }
    }


def get_standart_bosluklar() -> List[Dict[str, Any]]:
    """Standart pencere/kapi boyutlarini dondur (referans icin)"""
    return [
        {"ad": "Standart Pencere (100x120)", "en_cm": 100, "boy_cm": 120, "alan_m2": 1.20},
        {"ad": "Buyuk Pencere (120x150)", "en_cm": 120, "boy_cm": 150, "alan_m2": 1.80},
        {"ad": "Fransiz Pencere (150x220)", "en_cm": 150, "boy_cm": 220, "alan_m2": 3.30},
        {"ad": "Balkon Kapisi (100x220)", "en_cm": 100, "boy_cm": 220, "alan_m2": 2.20},
        {"ad": "Cift Kanat Balkon (200x220)", "en_cm": 200, "boy_cm": 220, "alan_m2": 4.40},
        {"ad": "Giris Kapisi (100x210)", "en_cm": 100, "boy_cm": 210, "alan_m2": 2.10},
        {"ad": "Kucuk Pencere (60x60)", "en_cm": 60, "boy_cm": 60, "alan_m2": 0.36},
        {"ad": "Banyo Penceresi (50x50)", "en_cm": 50, "boy_cm": 50, "alan_m2": 0.25},
    ]


# Test
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("DIS CEPHE MANTOLAMA MINHA HESAPLAMA TESTI")
    print("=" * 70)

    bosluklar = [
        {"en_cm": 120, "boy_cm": 150, "adet": 8, "denizlik_donulecek_mi": True, "aciklama": "Salon/Oda Pencereleri"},
        {"en_cm": 200, "boy_cm": 220, "adet": 4, "denizlik_donulecek_mi": True, "aciklama": "Balkon Kapilari"},
        {"en_cm": 60, "boy_cm": 60, "adet": 4, "denizlik_donulecek_mi": True, "aciklama": "Banyo Pencereleri"},
        {"en_cm": 100, "boy_cm": 210, "adet": 1, "denizlik_donulecek_mi": False, "aciklama": "Bina Giris Kapisi"},
    ]

    sonuc = hesapla_mantolama_minhali(
        brut_cephe_alani_m2=450,
        bosluklar_listesi=bosluklar,
        levha_tipi="eps_karbonlu",
        minha_limiti_m2=3.0
    )

    print(f"\nNet Alan: {sonuc['uygulamaya_esas_net_alan_m2']} m2")
    print(f"Genel Toplam: {sonuc['maliyet_ozeti']['genel_toplam_tl']} TL")
