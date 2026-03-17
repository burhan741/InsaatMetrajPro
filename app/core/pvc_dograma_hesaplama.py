"""
PVC Dograma (Pencere ve Kapi) Hesaplama Modulu
===============================================
Profil, cam, aksesuar ve montaj maliyet hesabi.

Ozellikler:
- Sabit, tek acilir, cift acilir, balkon kapisi tipleri
- Profil metraj hesabi (fire dahil)
- Cam alani hesabi (%15 profil payi)
- Aksesuar ve sineklik hesabi
- Vasistas (cift acilim) destegi

Yazar: Insaat Metraj Pro
Versiyon: 1.0
"""

import math
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class DogramaTipi(Enum):
    """PVC dograma tipleri"""
    SABIT = "sabit"
    TEK_ACILIR = "tek_acilir"
    CIFT_ACILIR_ORTA_KAYITLI = "cift_acilir_orta_kayitli"
    BALKON_KAPISI = "balkon_kapisi"


class ProfilRengi(Enum):
    """Profil renk secenekleri"""
    BEYAZ = "Beyaz"
    AGAC_DESENLI = "Agac Desenli"
    ANTRASIT = "Antrasit"
    KAHVERENGI = "Kahverengi"


class CamTipi(Enum):
    """Cam tipi secenekleri"""
    TEK_CAM = "Tek Cam (4mm)"
    CIFT_CAM = "Cift Cam (4+12+4)"
    ISI_CAMLI = "Isi Camli (Low-E)"
    LAMINE = "Lamine Cam"


# Fire Oranlari (Kesim paylari)
FIRE_PENCERE = 1.15  # %15
FIRE_KAPI = 1.20     # %20

# Cam icin profil payi
CAM_PROFIL_PAYI = 0.15  # %15 profil kaplama alani

# Varsayilan fiyatlar (2025)
VARSAYILAN_FIYATLAR = {
    'profil_mtul_fiyat': 450.0,     # TL/mtul
    'cam_m2_fiyat': 650.0,          # TL/m2 (cift cam)
    'aksesuar_set_fiyat': 850.0,    # TL/set (kol, mentese, ispanyolet)
    'sineklik_birim_fiyat': 350.0,  # TL/adet
    'iscilik_montaj_bedeli': 500.0, # TL/adet pencere
}

# Verimlilik (montaj hizi)
VERIMLILIK = {
    'piyasa': {
        'pencere_gun': 8,  # adet/gun
        'kapi_gun': 4,     # adet/gun
    },
    'resmi': {
        'pencere_gun': 5,
        'kapi_gun': 3,
    }
}


@dataclass
class DogramaBilgisi:
    """Tek bir dograma bilgisi"""
    en_cm: float
    boy_cm: float
    adet: int
    tip: str
    aciklama: str = ""
    cift_acilim_aksesuar: bool = False  # Vasistas
    sineklik_var_mi: bool = False

    @property
    def brut_alan_m2(self) -> float:
        """Brut alan (m2)"""
        return (self.en_cm * self.boy_cm) / 10000

    @property
    def net_cam_m2(self) -> float:
        """Net cam alani (%15 profil payi dusulmus)"""
        return self.brut_alan_m2 * (1 - CAM_PROFIL_PAYI)

    @property
    def cevre_cm(self) -> float:
        """Dograma cevresi (cm)"""
        return 2 * (self.en_cm + self.boy_cm)


def hesapla_pvc_dograma_detayli(
    dograma_listesi: List[Dict[str, Any]],
    profil_rengi: str = "Beyaz",
    cam_tipi: str = "Cift Cam (4+12+4)",
    profil_mtul_fiyat: float = VARSAYILAN_FIYATLAR['profil_mtul_fiyat'],
    cam_m2_fiyat: float = VARSAYILAN_FIYATLAR['cam_m2_fiyat'],
    aksesuar_set_fiyat: float = VARSAYILAN_FIYATLAR['aksesuar_set_fiyat'],
    sineklik_birim_fiyat: float = VARSAYILAN_FIYATLAR['sineklik_birim_fiyat'],
    iscilik_montaj_bedeli: float = VARSAYILAN_FIYATLAR['iscilik_montaj_bedeli'],
    verim_kaynagi: str = 'piyasa'
) -> Dict[str, Any]:
    """
    PVC Pencere ve Kapi maliyetlerini hesaplar.
    Fiyatlar tamamen manuel girilen verilere dayanir.

    Profil Metraj Hesabi:
    - Sabit: Kasa cevresi x fire
    - Tek Acilir: Kasa + Kanat cevresi x fire
    - Cift Acilir: Kasa + Orta kayit + 2 Kanat cevresi x fire
    - Balkon Kapisi: Kasa + Kanat cevresi x fire (yuksek fire)

    Cam Alani:
    - Net alan = Brut alan x 0.85 (%15 profil payi)

    Args:
        dograma_listesi: Dograma listesi
        profil_rengi: Profil rengi (bilgi amacli)
        cam_tipi: Cam tipi (bilgi amacli)
        profil_mtul_fiyat: Profil metre fiyati
        cam_m2_fiyat: Cam m2 fiyati
        aksesuar_set_fiyat: Aksesuar set fiyati
        sineklik_birim_fiyat: Sineklik birim fiyati
        iscilik_montaj_bedeli: Montaj birim fiyati
        verim_kaynagi: 'piyasa' veya 'resmi'

    Returns:
        Detayli hesaplama sonuclari
    """

    # Toplam degiskenler
    toplam_pencere_adet = 0
    toplam_kapi_adet = 0
    toplam_profil_mtul = 0.0
    toplam_net_cam_m2 = 0.0
    toplam_aksesuar_maliyeti = 0.0
    toplam_sineklik_adet = 0
    toplam_montaj_bedeli = 0.0

    # Detay listesi
    dograma_detay = []

    for dograma in dograma_listesi:
        en = float(dograma.get('en_cm', 0))
        boy = float(dograma.get('boy_cm', 0))
        adet = int(dograma.get('adet', 1))
        tip = dograma.get('tip', 'sabit')
        aciklama = dograma.get('aciklama', f"{en:.0f}x{boy:.0f} cm {tip}")
        vasistas_var_mi = dograma.get('cift_acilim_aksesuar', False)
        sineklik_var_mi = dograma.get('sineklik_var_mi', False)

        if en <= 0 or boy <= 0 or adet <= 0:
            continue

        # Tip kontrolu
        is_kapi = (tip == 'balkon_kapisi')

        if is_kapi:
            toplam_kapi_adet += adet
        else:
            toplam_pencere_adet += adet

        # A. Profil Metraji Hesabi
        birim_profil_cm = 0.0
        aksesuar_sayisi = 0
        fire = FIRE_KAPI if is_kapi else FIRE_PENCERE

        if tip == 'sabit':
            # Sadece kasa
            birim_profil_cm = (2 * (en + boy)) * fire
            aksesuar_sayisi = 0

        elif tip == 'tek_acilir':
            # Kasa + 1 kanat
            kasa_cevre = 2 * (en + boy)
            kanat_cevre = 2 * ((en - 10) + (boy - 10))  # -10cm kasa payi
            birim_profil_cm = (kasa_cevre + kanat_cevre) * fire
            aksesuar_sayisi = 1

        elif tip == 'cift_acilir_orta_kayitli':
            # Kasa + orta kayit + 2 kanat
            kasa_cevre = 2 * (en + boy)
            orta_kayit = boy
            # Her kanat yarim genislikte
            kanat_cevre = 2 * (2 * ((en / 2) + boy))
            birim_profil_cm = (kasa_cevre + orta_kayit + kanat_cevre) * fire
            aksesuar_sayisi = 2

        elif tip == 'balkon_kapisi':
            # Kasa + 1 buyuk kanat
            kasa_cevre = 2 * (en + boy)
            kanat_cevre = 2 * (en + boy)
            birim_profil_cm = (kasa_cevre + kanat_cevre) * fire
            aksesuar_sayisi = 1

        birim_profil_mtul = birim_profil_cm / 100
        toplam_profil_mtul += birim_profil_mtul * adet

        # B. Cam Alani (%15 profil payi dusulur)
        brut_alan_m2 = (en * boy) / 10000
        net_cam_m2 = brut_alan_m2 * (1 - CAM_PROFIL_PAYI)
        toplam_net_cam_m2 += net_cam_m2 * adet

        # C. Aksesuar Hesabi
        birim_aksesuar_tutar = 0.0
        if aksesuar_sayisi > 0:
            base_cost = aksesuar_set_fiyat * aksesuar_sayisi
            # Vasistas varsa %50 artis
            if vasistas_var_mi:
                birim_aksesuar_tutar = base_cost * 1.5
            else:
                birim_aksesuar_tutar = base_cost

        toplam_aksesuar_maliyeti += birim_aksesuar_tutar * adet

        # D. Sineklik
        if sineklik_var_mi:
            toplam_sineklik_adet += adet

        # E. Montaj
        toplam_montaj_bedeli += iscilik_montaj_bedeli * adet

        # Detay kaydi
        detay = {
            'aciklama': aciklama,
            'en_cm': en,
            'boy_cm': boy,
            'adet': adet,
            'tip': tip,
            'tip_aciklama': get_tip_aciklama(tip),
            'brut_alan_m2': round(brut_alan_m2, 3),
            'net_cam_m2': round(net_cam_m2, 3),
            'profil_mtul': round(birim_profil_mtul, 2),
            'aksesuar_sayisi': aksesuar_sayisi,
            'vasistas': vasistas_var_mi,
            'sineklik': sineklik_var_mi,
            'birim_aksesuar_tl': round(birim_aksesuar_tutar, 2),
            'birim_montaj_tl': iscilik_montaj_bedeli
        }
        dograma_detay.append(detay)

    # Maliyet hesaplamalari
    profil_maliyeti = toplam_profil_mtul * profil_mtul_fiyat
    cam_maliyeti = toplam_net_cam_m2 * cam_m2_fiyat
    sineklik_maliyeti = toplam_sineklik_adet * sineklik_birim_fiyat

    genel_toplam = (
        profil_maliyeti +
        cam_maliyeti +
        toplam_aksesuar_maliyeti +
        sineklik_maliyeti +
        toplam_montaj_bedeli
    )

    # Sure hesabi
    verim = VERIMLILIK.get(verim_kaynagi, VERIMLILIK['piyasa'])
    pencere_gun = toplam_pencere_adet / verim['pencere_gun'] if toplam_pencere_adet > 0 else 0
    kapi_gun = toplam_kapi_adet / verim['kapi_gun'] if toplam_kapi_adet > 0 else 0
    toplam_sure_gun = math.ceil(pencere_gun + kapi_gun)
    toplam_sure_gun = max(1, toplam_sure_gun) if (toplam_pencere_adet + toplam_kapi_adet) > 0 else 0

    return {
        # Ozet bilgiler
        "ozet_bilgi": f"{profil_rengi} Profil - {cam_tipi}",
        "profil_rengi": profil_rengi,
        "cam_tipi": cam_tipi,

        # Adetler
        "toplam_pencere_adet": toplam_pencere_adet,
        "toplam_kapi_adet": toplam_kapi_adet,
        "toplam_dograma_adet": toplam_pencere_adet + toplam_kapi_adet,

        # Hesaplanan miktarlar
        "hesaplanan_toplam_profil_mtul": round(toplam_profil_mtul, 2),
        "hesaplanan_net_cam_m2": round(toplam_net_cam_m2, 2),
        "gereken_aksesuar_takim_bedeli_tl": round(toplam_aksesuar_maliyeti, 2),
        "gereken_sineklik_adet": toplam_sineklik_adet,

        # Sure
        "tahmini_sure_gun": toplam_sure_gun,
        "sure_detay": {
            "pencere_gun": round(pencere_gun, 1),
            "kapi_gun": round(kapi_gun, 1),
            "verim_kaynagi": verim_kaynagi
        },

        # Maliyet detayi
        "maliyet_detayi": {
            "profil_tl": round(profil_maliyeti, 2),
            "cam_tl": round(cam_maliyeti, 2),
            "aksesuar_tl": round(toplam_aksesuar_maliyeti, 2),
            "sineklik_tl": round(sineklik_maliyeti, 2),
            "montaj_tl": round(toplam_montaj_bedeli, 2)
        },

        "genel_toplam_maliyet_tl": round(genel_toplam, 2),

        # Detay listesi
        "dograma_detay": dograma_detay,

        # Parametreler
        "parametreler": {
            "profil_mtul_fiyat": profil_mtul_fiyat,
            "cam_m2_fiyat": cam_m2_fiyat,
            "aksesuar_set_fiyat": aksesuar_set_fiyat,
            "sineklik_birim_fiyat": sineklik_birim_fiyat,
            "iscilik_montaj_bedeli": iscilik_montaj_bedeli
        }
    }


def get_tip_aciklama(tip: str) -> str:
    """Tip kodundan aciklama dondur"""
    tip_aciklamalar = {
        'sabit': 'Sabit (Acilmaz)',
        'tek_acilir': 'Tek Acilir',
        'cift_acilir_orta_kayitli': 'Cift Acilir (Orta Kayitli)',
        'balkon_kapisi': 'Balkon Kapisi'
    }
    return tip_aciklamalar.get(tip, tip)


def get_standart_pencere_boyutlari() -> List[Dict[str, Any]]:
    """Standart pencere boyutlarini dondur"""
    return [
        {"ad": "Kucuk Pencere", "en_cm": 80, "boy_cm": 100, "tip": "tek_acilir"},
        {"ad": "Standart Pencere", "en_cm": 100, "boy_cm": 120, "tip": "tek_acilir"},
        {"ad": "Buyuk Pencere", "en_cm": 120, "boy_cm": 150, "tip": "cift_acilir_orta_kayitli"},
        {"ad": "Genis Pencere", "en_cm": 150, "boy_cm": 150, "tip": "cift_acilir_orta_kayitli"},
        {"ad": "Fransiz Pencere", "en_cm": 180, "boy_cm": 220, "tip": "cift_acilir_orta_kayitli"},
        {"ad": "Balkon Kapisi", "en_cm": 100, "boy_cm": 220, "tip": "balkon_kapisi"},
        {"ad": "Cift Kanat Balkon", "en_cm": 180, "boy_cm": 220, "tip": "balkon_kapisi"},
        {"ad": "Banyo Penceresi", "en_cm": 60, "boy_cm": 60, "tip": "sabit"},
        {"ad": "WC Penceresi", "en_cm": 50, "boy_cm": 50, "tip": "sabit"},
    ]


def format_para(tutar: float) -> str:
    """Tutari Turk Lirasi formatinda goster"""
    return f"{tutar:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def rapor_olustur(sonuc: Dict[str, Any]) -> str:
    """Hesaplama sonucundan okunabilir rapor olusturur"""

    rapor = []
    rapor.append("=" * 70)
    rapor.append(" PVC DOGRAMA HESAPLAMA RAPORU")
    rapor.append("=" * 70)
    rapor.append("")
    rapor.append(f"Profil: {sonuc['profil_rengi']}")
    rapor.append(f"Cam: {sonuc['cam_tipi']}")
    rapor.append("")

    # Ozet
    rapor.append("OZET")
    rapor.append("-" * 50)
    rapor.append(f"  Toplam Pencere  : {sonuc['toplam_pencere_adet']} adet")
    rapor.append(f"  Toplam Kapi     : {sonuc['toplam_kapi_adet']} adet")
    rapor.append(f"  Profil Metraji  : {sonuc['hesaplanan_toplam_profil_mtul']:.2f} mtul")
    rapor.append(f"  Net Cam Alani   : {sonuc['hesaplanan_net_cam_m2']:.2f} m2")
    rapor.append(f"  Sineklik        : {sonuc['gereken_sineklik_adet']} adet")
    rapor.append(f"  Tahmini Sure    : {sonuc['tahmini_sure_gun']} is gunu")
    rapor.append("")

    # Detay
    rapor.append("DOGRAMA DETAYI")
    rapor.append("-" * 50)
    for d in sonuc['dograma_detay']:
        rapor.append(f"  {d['aciklama']}")
        rapor.append(f"  Tip: {d['tip_aciklama']}, Adet: {d['adet']}")
        rapor.append(f"  Profil: {d['profil_mtul']:.2f} mtul, Cam: {d['net_cam_m2']:.3f} m2")
        if d['vasistas']:
            rapor.append(f"  [Vasistas Mekanizmali]")
        if d['sineklik']:
            rapor.append(f"  [Sineklik Var]")
        rapor.append("")

    # Maliyet
    m = sonuc['maliyet_detayi']
    rapor.append("MALIYET DETAYI")
    rapor.append("-" * 50)
    rapor.append(f"  Profil Maliyeti    : {format_para(m['profil_tl']):>18}")
    rapor.append(f"  Cam Maliyeti       : {format_para(m['cam_tl']):>18}")
    rapor.append(f"  Aksesuar Maliyeti  : {format_para(m['aksesuar_tl']):>18}")
    rapor.append(f"  Sineklik Maliyeti  : {format_para(m['sineklik_tl']):>18}")
    rapor.append(f"  Montaj Maliyeti    : {format_para(m['montaj_tl']):>18}")
    rapor.append("=" * 50)
    rapor.append(f"  GENEL TOPLAM       : {format_para(sonuc['genel_toplam_maliyet_tl']):>18}")
    rapor.append("=" * 70)

    return "\n".join(rapor)


# Test
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("PVC DOGRAMA HESAPLAMA TESTI")
    print("=" * 70)

    dograma_listesi = [
        {"en_cm": 120, "boy_cm": 150, "adet": 10, "tip": "cift_acilir_orta_kayitli",
         "aciklama": "Salon Penceresi", "cift_acilim_aksesuar": True, "sineklik_var_mi": True},
        {"en_cm": 80, "boy_cm": 100, "adet": 8, "tip": "tek_acilir",
         "aciklama": "Oda Penceresi", "sineklik_var_mi": True},
        {"en_cm": 100, "boy_cm": 220, "adet": 4, "tip": "balkon_kapisi",
         "aciklama": "Balkon Kapisi", "sineklik_var_mi": False},
        {"en_cm": 50, "boy_cm": 50, "adet": 6, "tip": "sabit",
         "aciklama": "Banyo Penceresi"},
    ]

    sonuc = hesapla_pvc_dograma_detayli(
        dograma_listesi=dograma_listesi,
        profil_rengi="Beyaz",
        cam_tipi="Cift Cam (4+12+4)",
        profil_mtul_fiyat=450.0,
        cam_m2_fiyat=650.0,
        aksesuar_set_fiyat=850.0,
        sineklik_birim_fiyat=350.0,
        iscilik_montaj_bedeli=500.0
    )

    print(rapor_olustur(sonuc))
