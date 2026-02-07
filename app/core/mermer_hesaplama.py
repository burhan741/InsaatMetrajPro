"""
Mermer Isleri (Merdiven, Denizlik ve Harc) Hesaplama Modulu
============================================================
Merdiven tasi, denizlik ve harc sarfiyati hesabi.

Ozellikler:
- Merdiven tasi hesabi (basamak + riht + supurgelik + sahanlik)
- Denizlik hesabi (kulak payi + damlalik payi)
- Harc sarfiyati (yogun/ince)
- Asansor/hamaliye faktoru
- Yasli ekip hiz faktoru

Yazar: Insaat Metraj Pro
Versiyon: 1.0
"""

import math
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

try:
    import ezdxf
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False
    ezdxf = None

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

logger = logging.getLogger(__name__)


# ============================================================================
# SABITLER
# ============================================================================

# Merdiven Tasi Boyutlari (metre)
BASAMAK_DERINLIGI_M = 0.33      # Standart basamak derinligi
RIHT_YUKSEKLIGI_M = 0.16        # Standart riht (dikey kisim) yuksekligi
SUPURGELIK_ORANI = 0.20         # Basamak alaninin %20'si kadar supurgelik

# Harc Sarfiyat Oranlari (m2 basina)
# Merdiven: Kalin harcli is (kot ayari icin)
MERDIVEN_KUM_M3_PER_M2 = 0.05       # m3 kum / m2 merdiven
MERDIVEN_CIMENTO_TORBA_PER_M2 = 1.2  # torba / m2 merdiven

# Denizlik: Ince harcli is (duz yuzey)
DENIZLIK_KUM_M3_PER_M2 = 0.025      # m3 kum / m2 denizlik
DENIZLIK_CIMENTO_TORBA_PER_M2 = 0.5  # torba / m2 denizlik

# Denizlik Paylari (cm)
KULAK_PAYI_CM = 10               # Toplam (5 sag + 5 sol)
DAMLALIK_PAYI_CM = 5             # Disa tasma

# Iscilik Hizlari
class IscilikHizi:
    """Gunluk is kapasitesi"""
    # Asansorlu (normal tempo)
    ASANSORLU_BASAMAK_GUN = 25     # basamak/gun
    ASANSORLU_DENIZLIK_MTUL_GUN = 40  # mtul/gun

    # Asansorsuz (yavas tempo - hamaliye)
    ASANSORSUZ_BASAMAK_GUN = 15    # basamak/gun
    ASANSORSUZ_DENIZLIK_MTUL_GUN = 25  # mtul/gun

# Asansorsuz Faktorler
HAMALIYE_ISCILIK_CARPANI = 1.20    # %20 iscilik artisi
HAMALIYE_SURE_CARPANI = 1.30       # %30 sure uzamasi

# Varsayilan Fire Orani
VARSAYILAN_FIRE_ORANI = 0.10       # %10


@dataclass
class MerdivenBilgisi:
    """Merdiven parametreleri"""
    kat_sayisi: int
    kat_basi_basamak_sayisi: int = 17
    basamak_genisligi_cm: float = 120.0
    sahanlik_m2: float = 0.0

    @property
    def toplam_basamak_sayisi(self) -> int:
        """Toplam basamak adedi"""
        return self.kat_sayisi * self.kat_basi_basamak_sayisi

    @property
    def basamak_genisligi_m(self) -> float:
        """Basamak genisligi metre cinsinden"""
        return self.basamak_genisligi_cm / 100


@dataclass
class DenizlikBilgisi:
    """Tek bir denizlik (pencere) bilgisi"""
    pencere_en_cm: float
    duvar_kalinligi_cm: float
    adet: int = 1
    aciklama: str = ""

    @property
    def net_en_cm(self) -> float:
        """Kulak payi dahil en"""
        return self.pencere_en_cm + KULAK_PAYI_CM

    @property
    def net_derinlik_cm(self) -> float:
        """Damlalik payi dahil derinlik"""
        return self.duvar_kalinligi_cm + DAMLALIK_PAYI_CM

    @property
    def alan_m2(self) -> float:
        """Tek denizlik alani (m2)"""
        return (self.net_en_cm * self.net_derinlik_cm) / 10000

    @property
    def toplam_alan_m2(self) -> float:
        """Tum adetlerin toplam alani"""
        return self.alan_m2 * self.adet

    @property
    def uzunluk_mtul(self) -> float:
        """Tek denizlik uzunlugu (mtul)"""
        return self.net_en_cm / 100

    @property
    def toplam_uzunluk_mtul(self) -> float:
        """Toplam denizlik uzunlugu"""
        return self.uzunluk_mtul * self.adet


def hesapla_mermer_isleri_final(
    merdiven_bilgisi: Optional[Dict[str, Any]] = None,
    denizlik_listesi: Optional[List[Dict[str, Any]]] = None,
    mermer_m2_fiyat: float = 850.0,
    mermer_iscilik_basamak_fiyat: float = 150.0,
    mermer_iscilik_mtul_fiyat: float = 120.0,
    kum_m3_fiyat: float = 650.0,
    cimento_torba_fiyat: float = 180.0,
    asansor_aktif_mi: bool = True,
    fire_orani: float = VARSAYILAN_FIRE_ORANI
) -> Dict[str, Any]:
    """
    Mermer isleri (merdiven, denizlik, harc) hesaplama fonksiyonu.

    Merdiven Tasi Hesabi:
    - Basamak alani = (0.33 + 0.16) * genislik
    - Supurgelik = basamak alaninin %20'si
    - Sahanlik alani direkt eklenir

    Denizlik Hesabi:
    - Kulak payi: +10 cm (5 sag, 5 sol)
    - Damlalik payi: +5 cm (disa tasma)

    Harc Sarfiyati:
    - Merdiven (yogun): 0.05 m3 kum + 1.2 torba cimento / m2
    - Denizlik (ince): 0.025 m3 kum + 0.5 torba cimento / m2

    Args:
        merdiven_bilgisi: Merdiven parametreleri dict
        denizlik_listesi: Denizlik listesi
        mermer_m2_fiyat: Tas m2 birim fiyati
        mermer_iscilik_basamak_fiyat: Basamak basi iscilik
        mermer_iscilik_mtul_fiyat: Denizlik metresi iscilik
        kum_m3_fiyat: Kum m3 fiyati
        cimento_torba_fiyat: Cimento 50kg torba fiyati
        asansor_aktif_mi: Asansor kullanilabilir mi?
        fire_orani: Fire orani (varsayilan %10)

    Returns:
        Detayli hesaplama sonuclari
    """

    # ========================================================================
    # VALIDASYON VE HAZIRLIK
    # ========================================================================

    if fire_orani < 0 or fire_orani > 0.5:
        raise ValueError("Fire orani 0-0.5 arasinda olmalidir")

    # Merdiven objesi olustur
    merdiven = None
    if merdiven_bilgisi and merdiven_bilgisi.get('kat_sayisi', 0) > 0:
        merdiven = MerdivenBilgisi(
            kat_sayisi=int(merdiven_bilgisi.get('kat_sayisi', 0)),
            kat_basi_basamak_sayisi=int(merdiven_bilgisi.get('kat_basi_basamak_sayisi', 17)),
            basamak_genisligi_cm=float(merdiven_bilgisi.get('basamak_genisligi_cm', 120)),
            sahanlik_m2=float(merdiven_bilgisi.get('sahanlik_m2', 0))
        )

    # Denizlik objeleri olustur
    denizlikler = []
    if denizlik_listesi:
        for d in denizlik_listesi:
            if d.get('pencere_en_cm', 0) > 0 and d.get('duvar_kalinligi_cm', 0) > 0:
                denizlik = DenizlikBilgisi(
                    pencere_en_cm=float(d.get('pencere_en_cm', 0)),
                    duvar_kalinligi_cm=float(d.get('duvar_kalinligi_cm', 0)),
                    adet=int(d.get('adet', 1)),
                    aciklama=str(d.get('aciklama', ''))
                )
                denizlikler.append(denizlik)

    # ========================================================================
    # A. MERDIVEN TASI HESABI
    # ========================================================================

    merdiven_detay = {
        'kat_sayisi': 0,
        'kat_basi_basamak': 0,
        'toplam_basamak': 0,
        'basamak_genisligi_cm': 0,
        'basamak_alani_m2': 0.0,
        'supurgelik_alani_m2': 0.0,
        'sahanlik_alani_m2': 0.0,
        'toplam_merdiven_m2': 0.0
    }

    if merdiven:
        toplam_basamak = merdiven.toplam_basamak_sayisi
        genislik_m = merdiven.basamak_genisligi_m

        # Basamak + Riht alani (tek basamak)
        tek_basamak_m2 = (BASAMAK_DERINLIGI_M + RIHT_YUKSEKLIGI_M) * genislik_m
        basamak_alani_m2 = tek_basamak_m2 * toplam_basamak

        # Supurgelik (limonluk) - basamak alaninin %20'si
        supurgelik_alani_m2 = basamak_alani_m2 * SUPURGELIK_ORANI

        # Sahanlik
        sahanlik_alani_m2 = merdiven.sahanlik_m2

        # Toplam merdiven tasi
        toplam_merdiven_m2 = basamak_alani_m2 + supurgelik_alani_m2 + sahanlik_alani_m2

        merdiven_detay = {
            'kat_sayisi': merdiven.kat_sayisi,
            'kat_basi_basamak': merdiven.kat_basi_basamak_sayisi,
            'toplam_basamak': toplam_basamak,
            'basamak_genisligi_cm': merdiven.basamak_genisligi_cm,
            'tek_basamak_m2': round(tek_basamak_m2, 4),
            'basamak_alani_m2': round(basamak_alani_m2, 2),
            'supurgelik_alani_m2': round(supurgelik_alani_m2, 2),
            'sahanlik_alani_m2': round(sahanlik_alani_m2, 2),
            'toplam_merdiven_m2': round(toplam_merdiven_m2, 2)
        }
    else:
        toplam_basamak = 0
        toplam_merdiven_m2 = 0.0

    # ========================================================================
    # B. DENIZLIK HESABI
    # ========================================================================

    denizlik_detay = []
    toplam_denizlik_m2 = 0.0
    toplam_denizlik_mtul = 0.0
    toplam_denizlik_adet = 0

    for denizlik in denizlikler:
        detay = {
            'aciklama': denizlik.aciklama or f"{denizlik.pencere_en_cm:.0f}x{denizlik.duvar_kalinligi_cm:.0f} cm",
            'pencere_en_cm': denizlik.pencere_en_cm,
            'duvar_kalinligi_cm': denizlik.duvar_kalinligi_cm,
            'net_en_cm': denizlik.net_en_cm,
            'net_derinlik_cm': denizlik.net_derinlik_cm,
            'adet': denizlik.adet,
            'birim_alan_m2': round(denizlik.alan_m2, 4),
            'toplam_alan_m2': round(denizlik.toplam_alan_m2, 3),
            'birim_uzunluk_m': round(denizlik.uzunluk_mtul, 2),
            'toplam_uzunluk_m': round(denizlik.toplam_uzunluk_mtul, 2)
        }
        denizlik_detay.append(detay)

        toplam_denizlik_m2 += denizlik.toplam_alan_m2
        toplam_denizlik_mtul += denizlik.toplam_uzunluk_mtul
        toplam_denizlik_adet += denizlik.adet

    # ========================================================================
    # C. HARC SARFIYATI HESABI
    # ========================================================================

    # Merdiven harci (yogun)
    merdiven_kum_m3 = toplam_merdiven_m2 * MERDIVEN_KUM_M3_PER_M2
    merdiven_cimento_torba = toplam_merdiven_m2 * MERDIVEN_CIMENTO_TORBA_PER_M2

    # Denizlik harci (ince)
    denizlik_kum_m3 = toplam_denizlik_m2 * DENIZLIK_KUM_M3_PER_M2
    denizlik_cimento_torba = toplam_denizlik_m2 * DENIZLIK_CIMENTO_TORBA_PER_M2

    # Toplam harc
    toplam_kum_m3 = merdiven_kum_m3 + denizlik_kum_m3
    toplam_cimento_torba = merdiven_cimento_torba + denizlik_cimento_torba

    harc_detay = {
        'merdiven': {
            'alan_m2': round(toplam_merdiven_m2, 2),
            'kum_m3': round(merdiven_kum_m3, 3),
            'cimento_torba': round(merdiven_cimento_torba, 1),
            'tip': 'Yogun harc (kot ayari icin)'
        },
        'denizlik': {
            'alan_m2': round(toplam_denizlik_m2, 2),
            'kum_m3': round(denizlik_kum_m3, 3),
            'cimento_torba': round(denizlik_cimento_torba, 1),
            'tip': 'Ince harc (duz yuzey)'
        },
        'toplam_kum_m3': round(toplam_kum_m3, 3),
        'toplam_cimento_torba': round(toplam_cimento_torba, 1)
    }

    # ========================================================================
    # D. FIRE DAHIL MALZEME MIKTARLARI
    # ========================================================================

    fire_carpani = 1 + fire_orani

    # Mermer/tas
    toplam_tas_m2 = toplam_merdiven_m2 + toplam_denizlik_m2
    gereken_tas_m2 = toplam_tas_m2 * fire_carpani

    # Kum
    gereken_kum_m3 = toplam_kum_m3 * fire_carpani

    # Cimento (yuvarla)
    gereken_cimento_torba = math.ceil(toplam_cimento_torba * fire_carpani)

    # ========================================================================
    # E. ISCILIK VE SURE HESABI
    # ========================================================================

    # Iscilik baz hesabi
    iscilik_basamak = toplam_basamak * mermer_iscilik_basamak_fiyat
    iscilik_denizlik = toplam_denizlik_mtul * mermer_iscilik_mtul_fiyat
    iscilik_toplam_baz = iscilik_basamak + iscilik_denizlik

    # Sure hesabi (paralel calisma varsayilmaz - sirayla)
    if asansor_aktif_mi:
        basamak_hizi = IscilikHizi.ASANSORLU_BASAMAK_GUN
        denizlik_hizi = IscilikHizi.ASANSORLU_DENIZLIK_MTUL_GUN
        iscilik_carpani = 1.0
        sure_carpani = 1.0
        hamaliye_notu = "Asansor aktif - normal tempo"
    else:
        basamak_hizi = IscilikHizi.ASANSORSUZ_BASAMAK_GUN
        denizlik_hizi = IscilikHizi.ASANSORSUZ_DENIZLIK_MTUL_GUN
        iscilik_carpani = HAMALIYE_ISCILIK_CARPANI
        sure_carpani = HAMALIYE_SURE_CARPANI
        hamaliye_notu = f"Asansor YOK - Hamaliye faktoru: Iscilik x{iscilik_carpani}, Sure x{sure_carpani}"

    # Sure hesabi
    merdiven_gun = toplam_basamak / basamak_hizi if toplam_basamak > 0 else 0
    denizlik_gun = toplam_denizlik_mtul / denizlik_hizi if toplam_denizlik_mtul > 0 else 0

    # Toplam sure (sirayla calisma)
    toplam_sure_baz = merdiven_gun + denizlik_gun
    toplam_sure_gun = math.ceil(toplam_sure_baz * sure_carpani)
    toplam_sure_gun = max(1, toplam_sure_gun) if (toplam_basamak > 0 or toplam_denizlik_mtul > 0) else 0

    # Final iscilik
    iscilik_toplam = iscilik_toplam_baz * iscilik_carpani
    hamaliye_farki = iscilik_toplam - iscilik_toplam_baz

    iscilik_detay = {
        'basamak_sayisi': toplam_basamak,
        'basamak_birim_fiyat': mermer_iscilik_basamak_fiyat,
        'basamak_iscilik_tl': round(iscilik_basamak, 2),
        'denizlik_mtul': round(toplam_denizlik_mtul, 2),
        'denizlik_birim_fiyat': mermer_iscilik_mtul_fiyat,
        'denizlik_iscilik_tl': round(iscilik_denizlik, 2),
        'baz_toplam_tl': round(iscilik_toplam_baz, 2),
        'hamaliye_farki_tl': round(hamaliye_farki, 2),
        'final_toplam_tl': round(iscilik_toplam, 2),
        'asansor_aktif': asansor_aktif_mi,
        'hamaliye_notu': hamaliye_notu
    }

    sure_detay = {
        'merdiven_gun': round(merdiven_gun, 1),
        'denizlik_gun': round(denizlik_gun, 1),
        'baz_sure_gun': round(toplam_sure_baz, 1),
        'sure_carpani': sure_carpani,
        'final_sure_gun': toplam_sure_gun,
        'hiz_bilgisi': {
            'basamak_gun': basamak_hizi,
            'denizlik_mtul_gun': denizlik_hizi
        }
    }

    # ========================================================================
    # F. MALIYET HESABI
    # ========================================================================

    # Tas maliyeti
    tas_maliyeti = gereken_tas_m2 * mermer_m2_fiyat

    # Harc maliyeti
    kum_maliyeti = gereken_kum_m3 * kum_m3_fiyat
    cimento_maliyeti = gereken_cimento_torba * cimento_torba_fiyat
    harc_maliyeti = kum_maliyeti + cimento_maliyeti

    # Genel toplam
    genel_toplam = tas_maliyeti + harc_maliyeti + iscilik_toplam

    maliyet_detayi = {
        'tas_maliyeti_tl': round(tas_maliyeti, 2),
        'harc_maliyeti_tl': round(harc_maliyeti, 2),
        'kum_maliyeti_tl': round(kum_maliyeti, 2),
        'cimento_maliyeti_tl': round(cimento_maliyeti, 2),
        'iscilik_maliyeti_tl': round(iscilik_toplam, 2),
        'genel_toplam_tl': round(genel_toplam, 2)
    }

    # ========================================================================
    # G. SONUC RAPORU
    # ========================================================================

    return {
        # Ozet bilgiler
        'toplam_basamak_adet': toplam_basamak,
        'toplam_denizlik_adet': toplam_denizlik_adet,
        'toplam_denizlik_mtul': round(toplam_denizlik_mtul, 2),

        # Malzeme miktarlari (fire dahil - siparis icin)
        'gereken_mermer_m2': round(gereken_tas_m2, 2),
        'gereken_kum_m3': round(gereken_kum_m3, 3),
        'gereken_cimento_torba': gereken_cimento_torba,

        # Sure
        'tahmini_sure_gun': toplam_sure_gun,

        # Maliyet
        'maliyet_detayi': maliyet_detayi,

        # Detaylar
        'merdiven_detay': merdiven_detay,
        'denizlik_detay': denizlik_detay,
        'harc_detay': harc_detay,
        'iscilik_detay': iscilik_detay,
        'sure_detay': sure_detay,

        # Parametreler
        'parametreler': {
            'fire_orani': fire_orani,
            'mermer_m2_fiyat': mermer_m2_fiyat,
            'mermer_iscilik_basamak_fiyat': mermer_iscilik_basamak_fiyat,
            'mermer_iscilik_mtul_fiyat': mermer_iscilik_mtul_fiyat,
            'kum_m3_fiyat': kum_m3_fiyat,
            'cimento_torba_fiyat': cimento_torba_fiyat,
            'asansor_aktif_mi': asansor_aktif_mi
        }
    }


def get_standart_denizlik_boyutlari() -> List[Dict[str, Any]]:
    """Standart denizlik boyutlarini dondur"""
    return [
        {"ad": "Kucuk Pencere (80cm)", "pencere_en_cm": 80, "duvar_kalinligi_cm": 30},
        {"ad": "Standart Pencere (100cm)", "pencere_en_cm": 100, "duvar_kalinligi_cm": 30},
        {"ad": "Buyuk Pencere (120cm)", "pencere_en_cm": 120, "duvar_kalinligi_cm": 30},
        {"ad": "Genis Pencere (150cm)", "pencere_en_cm": 150, "duvar_kalinligi_cm": 30},
        {"ad": "Fransiz Pencere (180cm)", "pencere_en_cm": 180, "duvar_kalinligi_cm": 35},
        {"ad": "Balkon Kapisi (100cm)", "pencere_en_cm": 100, "duvar_kalinligi_cm": 35},
        {"ad": "Cift Kanat (200cm)", "pencere_en_cm": 200, "duvar_kalinligi_cm": 35},
    ]


def format_para(tutar: float) -> str:
    """Tutari Turk Lirasi formatinda goster"""
    return f"{tutar:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def rapor_olustur(sonuc: Dict[str, Any]) -> str:
    """Hesaplama sonucundan okunabilir rapor olusturur"""

    rapor = []
    rapor.append("=" * 70)
    rapor.append("         MERMER ISLERI HESAPLAMA RAPORU")
    rapor.append("         (Merdiven, Denizlik ve Harc)")
    rapor.append("=" * 70)
    rapor.append("")

    # 1. MERDIVEN BILGISI
    md = sonuc['merdiven_detay']
    if md['toplam_basamak'] > 0:
        rapor.append("1. MERDIVEN TASI HESABI")
        rapor.append("-" * 50)
        rapor.append(f"   Kat Sayisi          : {md['kat_sayisi']}")
        rapor.append(f"   Kat Basi Basamak    : {md['kat_basi_basamak']} adet")
        rapor.append(f"   Toplam Basamak      : {md['toplam_basamak']} adet")
        rapor.append(f"   Basamak Genisligi   : {md['basamak_genisligi_cm']:.0f} cm")
        rapor.append("")
        rapor.append(f"   Basamak+Riht Alani  : {md['basamak_alani_m2']:>10.2f} m2")
        rapor.append(f"   Supurgelik Alani    : {md['supurgelik_alani_m2']:>10.2f} m2")
        rapor.append(f"   Sahanlik Alani      : {md['sahanlik_alani_m2']:>10.2f} m2")
        rapor.append("-" * 50)
        rapor.append(f"   MERDIVEN TOPLAM     : {md['toplam_merdiven_m2']:>10.2f} m2")
        rapor.append("")

    # 2. DENIZLIK BILGISI
    dd = sonuc['denizlik_detay']
    if dd:
        rapor.append("2. DENIZLIK HESABI")
        rapor.append("-" * 50)
        rapor.append(f"   {'Aciklama':<25} {'Olcu':<15} {'Adet':>5} {'Alan':>10}")
        rapor.append("-" * 50)
        for d in dd:
            olcu = f"{d['net_en_cm']:.0f}x{d['net_derinlik_cm']:.0f}cm"
            rapor.append(f"   {d['aciklama']:<25} {olcu:<15} {d['adet']:>5} {d['toplam_alan_m2']:>8.3f} m2")
        rapor.append("-" * 50)
        rapor.append(f"   DENIZLIK TOPLAM: {sonuc['toplam_denizlik_adet']} adet, "
                    f"{sonuc['toplam_denizlik_mtul']:.2f} mtul")
        rapor.append("")

    # 3. HARC SARFIYATI
    hd = sonuc['harc_detay']
    rapor.append("3. HARC SARFIYATI")
    rapor.append("-" * 50)
    if hd['merdiven']['alan_m2'] > 0:
        rapor.append(f"   Merdiven ({hd['merdiven']['tip']})")
        rapor.append(f"     Kum: {hd['merdiven']['kum_m3']:.3f} m3, Cimento: {hd['merdiven']['cimento_torba']:.1f} torba")
    if hd['denizlik']['alan_m2'] > 0:
        rapor.append(f"   Denizlik ({hd['denizlik']['tip']})")
        rapor.append(f"     Kum: {hd['denizlik']['kum_m3']:.3f} m3, Cimento: {hd['denizlik']['cimento_torba']:.1f} torba")
    rapor.append("-" * 50)
    rapor.append(f"   TOPLAM: Kum {hd['toplam_kum_m3']:.3f} m3, Cimento {hd['toplam_cimento_torba']:.1f} torba")
    rapor.append("")

    # 4. SIPARIS MIKTARLARI (Fire Dahil)
    rapor.append("4. SIPARIS MIKTARLARI (Fire Dahil)")
    rapor.append("-" * 50)
    fire = sonuc['parametreler']['fire_orani']
    rapor.append(f"   Fire Orani: %{fire*100:.0f}")
    rapor.append(f"   Mermer/Tas : {sonuc['gereken_mermer_m2']:>10.2f} m2")
    rapor.append(f"   Kum        : {sonuc['gereken_kum_m3']:>10.3f} m3")
    rapor.append(f"   Cimento    : {sonuc['gereken_cimento_torba']:>10} torba")
    rapor.append("")

    # 5. ISCILIK VE SURE
    id = sonuc['iscilik_detay']
    sd = sonuc['sure_detay']
    rapor.append("5. ISCILIK VE SURE")
    rapor.append("-" * 50)
    rapor.append(f"   {id['hamaliye_notu']}")
    rapor.append("")
    if id['basamak_sayisi'] > 0:
        rapor.append(f"   Merdiven: {id['basamak_sayisi']} basamak x {format_para(id['basamak_birim_fiyat'])} = {format_para(id['basamak_iscilik_tl'])}")
    if id['denizlik_mtul'] > 0:
        rapor.append(f"   Denizlik: {id['denizlik_mtul']:.2f} mtul x {format_para(id['denizlik_birim_fiyat'])} = {format_para(id['denizlik_iscilik_tl'])}")
    if id['hamaliye_farki_tl'] > 0:
        rapor.append(f"   Hamaliye Farki (+%20): {format_para(id['hamaliye_farki_tl'])}")
    rapor.append(f"   ISCILIK TOPLAM: {format_para(id['final_toplam_tl'])}")
    rapor.append("")
    rapor.append(f"   Tahmini Sure: {sd['final_sure_gun']} is gunu")
    rapor.append(f"   (Merdiven: {sd['merdiven_gun']:.1f} gun, Denizlik: {sd['denizlik_gun']:.1f} gun)")
    rapor.append("")

    # 6. MALIYET OZETI
    m = sonuc['maliyet_detayi']
    rapor.append("6. MALIYET OZETI")
    rapor.append("-" * 50)
    rapor.append(f"   Tas Maliyeti     : {format_para(m['tas_maliyeti_tl']):>20}")
    rapor.append(f"   Harc Maliyeti    : {format_para(m['harc_maliyeti_tl']):>20}")
    rapor.append(f"     - Kum          : {format_para(m['kum_maliyeti_tl']):>20}")
    rapor.append(f"     - Cimento      : {format_para(m['cimento_maliyeti_tl']):>20}")
    rapor.append(f"   Iscilik Maliyeti : {format_para(m['iscilik_maliyeti_tl']):>20}")
    rapor.append("=" * 50)
    rapor.append(f"   GENEL TOPLAM     : {format_para(m['genel_toplam_tl']):>20}")
    rapor.append("=" * 70)

    return "\n".join(rapor)


# ============================================================================
# DXF TABANLI MERDİVEN MERMERİ METRAJ MODÜLÜ
# ============================================================================

def _shoelace_alan(noktalar: List[Tuple[float, float]]) -> float:
    """
    Shoelace (Gauss) formulu ile kapalı poligon alanı hesaplar.

    Args:
        noktalar: (x, y) koordinat listesi

    Returns:
        float: Mutlak alan degeri
    """
    n = len(noktalar)
    if n < 3:
        return 0.0
    alan = 0.0
    for i in range(n):
        j = (i + 1) % n
        alan += noktalar[i][0] * noktalar[j][1]
        alan -= noktalar[j][0] * noktalar[i][1]
    return abs(alan) / 2.0


def _cevre_hesapla(noktalar: List[Tuple[float, float]], kapali: bool = True) -> float:
    """
    Nokta listesinden cevre uzunlugu hesaplar.

    Args:
        noktalar: (x, y) koordinat listesi
        kapali: True ise son nokta-ilk nokta arasi da eklenir

    Returns:
        float: Cevre uzunlugu
    """
    if len(noktalar) < 2:
        return 0.0
    cevre = 0.0
    n = len(noktalar)
    segment_sayisi = n if kapali else n - 1
    for i in range(segment_sayisi):
        p1 = noktalar[i]
        p2 = noktalar[(i + 1) % n]
        cevre += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    return cevre


def _birim_cevirici(deger: float, kaynak_birim: str, hedef: str = "m") -> float:
    """
    Uzunluk birim donusumu.

    Args:
        deger: Donusturulecek deger
        kaynak_birim: 'm', 'cm' veya 'mm'
        hedef: Hedef birim (varsayilan 'm')

    Returns:
        float: Donusturulmus deger
    """
    # Once metreye cevir
    if kaynak_birim == "cm":
        metre = deger / 100.0
    elif kaynak_birim == "mm":
        metre = deger / 1000.0
    else:
        metre = deger

    if hedef == "m":
        return metre
    elif hedef == "cm":
        return metre * 100.0
    elif hedef == "mm":
        return metre * 1000.0
    return metre


def _alan_birim_cevirici(deger: float, kaynak_birim: str) -> float:
    """
    Alan birim donusumu (her zaman m2 ye cevirir).

    Args:
        deger: Ham alan degeri
        kaynak_birim: 'm', 'cm' veya 'mm'

    Returns:
        float: m2 cinsinden alan
    """
    if kaynak_birim == "cm":
        return deger / 10000.0
    elif kaynak_birim == "mm":
        return deger / 1000000.0
    return deger


def merdiven_mermer_metraj_dxf(
    dxf_path: str,
    layer_name: str = "A-MERMER",
    riht_yuksekligi: float = 0.16,
    basamak_genisligi: float = 0.30,
    limonluk_yuksekligi: float = 0.10,
    cizim_birimi: str = "cm",
    mermer_kalinligi: float = 0.02,
    tolerans: float = 0.20
) -> "pd.DataFrame":
    """
    DXF dosyasından merdiven mermer metrajını otomatik hesaplar.

    Algoritma:
    1. Belirtilen layer'daki LINE entity'lerini bulur -> her biri bir basamak kenarıdır.
       Cizgi uzunlugu = basamagin boyu (uzunlugu).
    2. Belirtilen layer'daki kapali LWPOLYLINE entity'lerini bulur -> sahanlik alanlari.
    3. Her basamak icin:
       - Basamak Alani (m2) = Cizgi Uzunlugu x basamak_genisligi
       - Riht Alani (m2)    = Cizgi Uzunlugu x riht_yuksekligi
       - Limonluk (mtul)    = basamak_genisligi + riht_yuksekligi (sag+sol = x2)
    4. Her sahanlik icin:
       - Alan (m2) = Kapalı polyline alani (Shoelace veya Shapely)
       - Cevre (m) = Polyline cevresi -> limonluk metraji

    Args:
        dxf_path: DXF dosya yolu
        layer_name: Merdiven mermer cizimlerinin bulundugu layer
        riht_yuksekligi: Riht (dikey kisim) yuksekligi metre cinsinden
        basamak_genisligi: Basamak genisligi metre cinsinden
        limonluk_yuksekligi: Supurgelik / limonluk yuksekligi metre cinsinden
        cizim_birimi: DXF cizim birimi ('m', 'cm', 'mm')
        mermer_kalinligi: Mermer plaka kalinligi metre cinsinden (hacim hesabi icin)
        tolerans: Acik polyline'larin kapatilma toleransi (metre)

    Returns:
        pd.DataFrame: Metraj sonuc tablosu
            Sutunlar: Tip, No, Uzunluk/Cevre (m), Basamak Alani (m2),
                      Riht Alani (m2), Toplam Alan (m2), Hacim (m3),
                      Limonluk (mtul)

    Raises:
        ImportError: ezdxf veya pandas yuklu degilse
        FileNotFoundError: DXF dosyasi bulunamazsa
        RuntimeError: DXF okuma hatasi
    """
    # ========================================================================
    # KUTUPLIANE KONTROLLERI
    # ========================================================================
    if not EZDXF_AVAILABLE:
        raise ImportError(
            "ezdxf kutuphanesi yuklu degil. Kurulum: pip install ezdxf"
        )
    if not PANDAS_AVAILABLE:
        raise ImportError(
            "pandas kutuphanesi yuklu degil. Kurulum: pip install pandas"
        )

    # ========================================================================
    # DOSYA YUKLEME
    # ========================================================================
    dosya = Path(dxf_path)
    if not dosya.exists():
        raise FileNotFoundError(f"DXF dosyasi bulunamadi: {dxf_path}")

    try:
        doc = ezdxf.readfile(str(dosya))
        msp = doc.modelspace()
        logger.info(f"DXF yuklendi: {dosya.name}")
    except Exception as e:
        raise RuntimeError(f"DXF dosyasi okunamadi: {e}")

    # Layer kontrolu
    mevcut_layerlar = [layer.dxf.name for layer in doc.layers]
    if layer_name not in mevcut_layerlar:
        logger.warning(
            f"'{layer_name}' layer'i bulunamadi. "
            f"Mevcut layer'lar: {mevcut_layerlar}"
        )

    # Birime gore tolerans ayarla
    if cizim_birimi == "cm":
        gercek_tolerans = tolerans * 100
    elif cizim_birimi == "mm":
        gercek_tolerans = tolerans * 1000
    else:
        gercek_tolerans = tolerans

    # ========================================================================
    # 1. BASAMAKLARI BUL (LINE ANALIZI)
    # ========================================================================
    satirlar = []  # Sonuc DataFrame satir listesi
    basamak_no = 0

    try:
        line_query = f'LINE[layer=="{layer_name}"]'
        line_entities = list(msp.query(line_query))
        logger.info(f"LINE entity sayisi (layer={layer_name}): {len(line_entities)}")
    except Exception as e:
        logger.error(f"LINE sorgusu hatasi: {e}")
        line_entities = []

    for idx, entity in enumerate(line_entities):
        try:
            start = entity.dxf.start
            end = entity.dxf.end

            # Ham cizgi uzunlugu (cizim biriminde)
            ham_uzunluk = math.hypot(end.x - start.x, end.y - start.y)

            # Metreye cevir
            uzunluk_m = _birim_cevirici(ham_uzunluk, cizim_birimi, "m")

            if uzunluk_m < 0.01:
                # 1 cm altindaki cizgileri atla (gurultu)
                continue

            basamak_no += 1

            # Basamak alani = cizgi uzunlugu x basamak genisligi
            basamak_alani = uzunluk_m * basamak_genisligi

            # Riht alani = cizgi uzunlugu x riht yuksekligi
            riht_alani = uzunluk_m * riht_yuksekligi

            # Toplam alan (basamak + riht)
            toplam_alan = basamak_alani + riht_alani

            # Hacim (opsiyonel)
            hacim = toplam_alan * mermer_kalinligi

            # Limonluk = (basamak_genisligi + riht_yuksekligi) x 2 (sag ve sol)
            limonluk_tek_taraf = basamak_genisligi + riht_yuksekligi
            limonluk_toplam = limonluk_tek_taraf * 2

            satirlar.append({
                "Tip": "Basamak",
                "No": basamak_no,
                "Uzunluk/Cevre (m)": round(uzunluk_m, 3),
                "Basamak Alani (m2)": round(basamak_alani, 4),
                "Riht Alani (m2)": round(riht_alani, 4),
                "Toplam Alan (m2)": round(toplam_alan, 4),
                "Hacim (m3)": round(hacim, 5),
                "Limonluk (mtul)": round(limonluk_toplam, 3)
            })

            logger.debug(
                f"Basamak #{basamak_no}: L={uzunluk_m:.3f}m, "
                f"Alan={toplam_alan:.4f}m2, Limonluk={limonluk_toplam:.3f}m"
            )

        except Exception as e:
            logger.warning(f"LINE #{idx+1} isleme hatasi: {e}")
            continue

    logger.info(f"Toplam {basamak_no} basamak bulundu")

    # ========================================================================
    # 2. SAHANLIKLARI BUL (LWPOLYLINE ANALIZI)
    # ========================================================================
    sahanlik_no = 0

    try:
        poly_query = f'LWPOLYLINE[layer=="{layer_name}"]'
        poly_entities = list(msp.query(poly_query))
        logger.info(f"LWPOLYLINE entity sayisi (layer={layer_name}): {len(poly_entities)}")
    except Exception as e:
        logger.error(f"LWPOLYLINE sorgusu hatasi: {e}")
        poly_entities = []

    for idx, entity in enumerate(poly_entities):
        try:
            is_closed = getattr(entity, 'is_closed', False)

            # Noktalari oku
            noktalar = None
            try:
                with entity.points("xy") as pts:
                    noktalar = list(pts)
            except (AttributeError, TypeError):
                try:
                    noktalar = [(v[0], v[1]) for v in entity.vertices]
                except Exception as e2:
                    logger.warning(f"LWPOLYLINE #{idx+1} nokta okuma hatasi: {e2}")
                    continue

            if not noktalar or len(noktalar) < 3:
                continue

            # Kapali mi kontrol et
            kapali = is_closed
            if not kapali:
                baslangic = noktalar[0]
                bitis = noktalar[-1]
                mesafe = math.hypot(
                    bitis[0] - baslangic[0],
                    bitis[1] - baslangic[1]
                )
                if mesafe <= gercek_tolerans:
                    kapali = True
                    logger.debug(
                        f"LWPOLYLINE #{idx+1} tolerans icinde kapatildi "
                        f"(mesafe={mesafe:.4f})"
                    )

            if not kapali:
                logger.debug(
                    f"LWPOLYLINE #{idx+1} acik, sahanlik olarak kabul edilmedi"
                )
                continue

            sahanlik_no += 1

            # Alan hesapla (Shoelace)
            ham_alan = _shoelace_alan(noktalar)
            alan_m2 = _alan_birim_cevirici(ham_alan, cizim_birimi)

            if alan_m2 < 0.01:
                # 0.01 m2 altindaki alanlari atla
                sahanlik_no -= 1
                continue

            # Cevre hesapla
            ham_cevre = _cevre_hesapla(noktalar, kapali=True)
            cevre_m = _birim_cevirici(ham_cevre, cizim_birimi, "m")

            # Hacim
            hacim = alan_m2 * mermer_kalinligi

            # Limonluk = cevre x limonluk yuksekligi (m2 cinsinden degil, mtul cinsinden)
            # Cevre zaten limonluk metraji olarak kullanilir
            limonluk_mtul = cevre_m

            satirlar.append({
                "Tip": "Sahanlik",
                "No": sahanlik_no,
                "Uzunluk/Cevre (m)": round(cevre_m, 3),
                "Basamak Alani (m2)": round(alan_m2, 4),
                "Riht Alani (m2)": 0.0,
                "Toplam Alan (m2)": round(alan_m2, 4),
                "Hacim (m3)": round(hacim, 5),
                "Limonluk (mtul)": round(limonluk_mtul, 3)
            })

            logger.debug(
                f"Sahanlik #{sahanlik_no}: Alan={alan_m2:.4f}m2, "
                f"Cevre={cevre_m:.3f}m"
            )

        except Exception as e:
            logger.warning(f"LWPOLYLINE #{idx+1} isleme hatasi: {e}")
            continue

    logger.info(f"Toplam {sahanlik_no} sahanlik bulundu")

    # ========================================================================
    # 3. DATAFRAME OLUSTUR
    # ========================================================================
    if not satirlar:
        logger.warning(
            f"'{layer_name}' layer'inda hicbir merdiven entity'si bulunamadi"
        )
        # Bos DataFrame dondur (sutunlar korunsun)
        return pd.DataFrame(columns=[
            "Tip", "No", "Uzunluk/Cevre (m)",
            "Basamak Alani (m2)", "Riht Alani (m2)",
            "Toplam Alan (m2)", "Hacim (m3)", "Limonluk (mtul)"
        ])

    df = pd.DataFrame(satirlar)

    # ========================================================================
    # 4. TOPLAM SATIRI EKLE
    # ========================================================================
    toplam = {
        "Tip": "TOPLAM",
        "No": "",
        "Uzunluk/Cevre (m)": round(df["Uzunluk/Cevre (m)"].sum(), 3),
        "Basamak Alani (m2)": round(df["Basamak Alani (m2)"].sum(), 4),
        "Riht Alani (m2)": round(df["Riht Alani (m2)"].sum(), 4),
        "Toplam Alan (m2)": round(df["Toplam Alan (m2)"].sum(), 4),
        "Hacim (m3)": round(df["Hacim (m3)"].sum(), 5),
        "Limonluk (mtul)": round(df["Limonluk (mtul)"].sum(), 3)
    }

    # Basamak ve sahanlik ayrı toplamlar
    basamak_df = df[df["Tip"] == "Basamak"]
    sahanlik_df = df[df["Tip"] == "Sahanlik"]

    toplam_basamak = {
        "Tip": "Basamak Toplam",
        "No": f"{len(basamak_df)} ad.",
        "Uzunluk/Cevre (m)": round(basamak_df["Uzunluk/Cevre (m)"].sum(), 3) if len(basamak_df) > 0 else 0,
        "Basamak Alani (m2)": round(basamak_df["Basamak Alani (m2)"].sum(), 4) if len(basamak_df) > 0 else 0,
        "Riht Alani (m2)": round(basamak_df["Riht Alani (m2)"].sum(), 4) if len(basamak_df) > 0 else 0,
        "Toplam Alan (m2)": round(basamak_df["Toplam Alan (m2)"].sum(), 4) if len(basamak_df) > 0 else 0,
        "Hacim (m3)": round(basamak_df["Hacim (m3)"].sum(), 5) if len(basamak_df) > 0 else 0,
        "Limonluk (mtul)": round(basamak_df["Limonluk (mtul)"].sum(), 3) if len(basamak_df) > 0 else 0
    }

    toplam_sahanlik = {
        "Tip": "Sahanlik Toplam",
        "No": f"{len(sahanlik_df)} ad.",
        "Uzunluk/Cevre (m)": round(sahanlik_df["Uzunluk/Cevre (m)"].sum(), 3) if len(sahanlik_df) > 0 else 0,
        "Basamak Alani (m2)": round(sahanlik_df["Basamak Alani (m2)"].sum(), 4) if len(sahanlik_df) > 0 else 0,
        "Riht Alani (m2)": round(sahanlik_df["Riht Alani (m2)"].sum(), 4) if len(sahanlik_df) > 0 else 0,
        "Toplam Alan (m2)": round(sahanlik_df["Toplam Alan (m2)"].sum(), 4) if len(sahanlik_df) > 0 else 0,
        "Hacim (m3)": round(sahanlik_df["Hacim (m3)"].sum(), 5) if len(sahanlik_df) > 0 else 0,
        "Limonluk (mtul)": round(sahanlik_df["Limonluk (mtul)"].sum(), 3) if len(sahanlik_df) > 0 else 0
    }

    # Ara toplam ve genel toplam satirlarini ekle
    toplam_rows = pd.DataFrame([toplam_basamak, toplam_sahanlik, toplam])
    df = pd.concat([df, toplam_rows], ignore_index=True)

    logger.info(
        f"Merdiven mermer metraji tamamlandi: "
        f"{basamak_no} basamak, {sahanlik_no} sahanlik, "
        f"Toplam Alan={toplam['Toplam Alan (m2)']} m2, "
        f"Limonluk={toplam['Limonluk (mtul)']} mtul"
    )

    return df


# Test
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("MERMER ISLERI HESAPLAMA TESTI")
    print("=" * 70)

    # Test verileri
    merdiven = {
        "kat_sayisi": 5,
        "kat_basi_basamak_sayisi": 17,
        "basamak_genisligi_cm": 120,
        "sahanlik_m2": 8.0  # 5 kat x ~1.6 m2 sahanlik
    }

    denizlikler = [
        {"pencere_en_cm": 120, "duvar_kalinligi_cm": 30, "adet": 20, "aciklama": "Standart Pencere"},
        {"pencere_en_cm": 150, "duvar_kalinligi_cm": 30, "adet": 8, "aciklama": "Genis Pencere"},
        {"pencere_en_cm": 80, "duvar_kalinligi_cm": 25, "adet": 10, "aciklama": "Banyo Penceresi"},
    ]

    # Asansorlu hesaplama
    print("\n>>> ASANSORLU HESAPLAMA:")
    sonuc1 = hesapla_mermer_isleri_final(
        merdiven_bilgisi=merdiven,
        denizlik_listesi=denizlikler,
        mermer_m2_fiyat=850.0,
        asansor_aktif_mi=True
    )
    print(rapor_olustur(sonuc1))

    # Asansorsuz hesaplama
    print("\n>>> ASANSORSUZ HESAPLAMA (Hamaliye Farkli):")
    sonuc2 = hesapla_mermer_isleri_final(
        merdiven_bilgisi=merdiven,
        denizlik_listesi=denizlikler,
        mermer_m2_fiyat=850.0,
        asansor_aktif_mi=False
    )
    print(f"Asansorsuz Toplam: {format_para(sonuc2['maliyet_detayi']['genel_toplam_tl'])}")
    print(f"Asansorsuz Sure: {sonuc2['tahmini_sure_gun']} gun")
    print(f"Fark: {format_para(sonuc2['maliyet_detayi']['genel_toplam_tl'] - sonuc1['maliyet_detayi']['genel_toplam_tl'])}")
