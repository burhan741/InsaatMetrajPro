"""
PERT (Program Evaluation and Review Technique) Motoru
======================================================
Neyi cozer?
Tek nokta sure tahmini yerine 3 nokta tahmin (iyimser / olasilikli / kotumser)
kullanarak proje bitis tarihini olasiliksal dagilim ile hesaplar.
CPM'in deterministik yapisina karsi PERT, belirsizligi sayisallastirir.

Algoritma (Beta Dagilimi yaklasimi):
t_e = (t_o + 4*t_m + t_p) / 6 -- Beklenen sure (Malcolm, 1959)
sigma = (t_p - t_o) / 6 -- Standart sapma
sigma^2 = sigma^2 -- Varyans
Proje_sigma = sqrt(sum(sigma^2_kritik)) -- Merkezi Limit Teoremi (CLT)

Olasilik esik degerleri (Standart Normal Dagilim):
P50 = z=0.000 (Beklenen sure)
P80 = z=0.842
P90 = z=1.282
P95 = z=1.645

Teknik Referanslar:
- Malcolm, D.G. et al. (1959). "Application of a Technique for Research and
Development Program Evaluation." Operations Research, 7(5), 646-669.
- PMBOK Guide 7th Edition (PMI, 2021) -- Three-Point Estimating
- TS ISO 21500:2022 -- Proje yonetimi kilavuzu
- Moder & Phillips (1983). "Project Management with CPM, PERT and PDM"

Test:
python -c "
from app.core.pert_engine import PertEngine, PertGorev
from datetime import datetime
g = [PertGorev(1, 'Temel Hafriyati', 20, 28, 45, '1.1', True, datetime(2026,3,1))]
r = PertEngine().hesapla(g, datetime(2026,3,1))
assert abs(r.toplam_pert_sure - 29.5) < 0.01 # (20+4*28+45)/6
assert abs(r.proje_sapma - 4.167) < 0.01 # (45-20)/6
print(f'PERT OK: {r.toplam_pert_sure:.1f} gun, sigma={r.proje_sapma:.3f}')
"
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Z degerleri (Standart Normal Dagilim -- tek kuyruklu)
# ---------------------------------------------------------------------------
Z_P50 = 0.000
Z_P80 = 0.842
Z_P90 = 1.282
Z_P95 = 1.645


# ===========================================================================
# VERI MODELLERI
# ===========================================================================

@dataclass
class PertGorev:
    """
    Tek bir is kalemi icin 3 nokta tahmin verisi.

    Alanlar:
    gorev_id : Benzersiz gorev kimlik numarasi
    ad : Is kaleminin adi (WBS etiketiyle es anlami)
    iyimser_gun : t_o -- Her kos durumda minimum sure
    olasi_gun : t_m -- Gercekci, en olasilikli sure
    kotumser_gun : t_p -- Murphy Kanunu devrede; maksimum sure
    wbs_kodu : WBS hiyerarsisi (ornek: "1.2.3")
    kritik : CPM kritik yolunda yer alip almadigi
    baslangic : Planlanan baslangic tarihi (CPM'den beslenir)
    """
    gorev_id: int
    ad: str
    iyimser_gun: float # t_o
    olasi_gun: float # t_m
    kotumser_gun: float # t_p
    wbs_kodu: str = ""
    kritik: bool = False
    baslangic: Optional[datetime] = None


@dataclass
class PertGorevSonucu:
    """
    Tek is kalemi icin PERT hesap sonuclari.

    Formul kaynaklari:
    t_e = (t_o + 4*t_m + t_p) / 6 [Malcolm 1959]
    sigma = (t_p - t_o) / 6
    sigma2 = sigma^2
    """
    gorev_id: int
    ad: str
    wbs_kodu: str
    kritik: bool

    # -- Cekirdek istatistikler --
    pert_sure: float # t_e -- beklenen sure (gun)
    standart_sapma: float # sigma
    varyans: float # sigma^2

    # -- Olasiliksal bitis tarihleri --
    bitis_p0: datetime # En erken (iyimser)
    bitis_p50: datetime # Beklenen (medyan)
    bitis_p80: datetime # Yuzde 80 olasilik
    bitis_p90: datetime # Yuzde 90 olasilik
    bitis_p95: datetime # Yuzde 95 olasilik

    # -- Yorum --
    yorum: str = ""


@dataclass
class PertProjeSonucu:
    """
    Proje duzeyi PERT analiz sonuclari.

    Proje sigma, CLT (Merkezi Limit Teoremi) ile kritik yoldaki
    gorevlerin varyanslarinin toplaminin karekokundur.
    Bu yaklasim, gorevlerin bagimsiz oldugu varsayimini gerektirir.
    """
    # -- Proje istatistikleri --
    toplam_pert_sure: float # Kritik yolun beklenen toplam suresi (gun)
    proje_sapma: float # Proje sigma
    proje_varyans: float # Proje sigma^2

    # -- Proje bitis tarihleri --
    proje_bitis_p0: datetime # Iyimser
    proje_bitis_p50: datetime # Beklenen
    proje_bitis_p80: datetime # P80
    proje_bitis_p90: datetime # P90
    proje_bitis_p95: datetime # P95

    # -- Gorev detaylari --
    gorev_sonuclari: List[PertGorevSonucu] = field(default_factory=list)

    # -- Uyari ve sozlesme bilgileri --
    uyari_listesi: List[str] = field(default_factory=list)
    sozlesme_asim_gun: Optional[int] = None # Pozitif = asim, None = sozlesme yok


# ===========================================================================
# MOTOR
# ===========================================================================

class PertEngine:
    """
    PERT 3 nokta tahmin motoru.

    Kullanim:
    engine = PertEngine()
    gorevler = [PertGorev(1, "Kaba Insaat", 30, 45, 80, "1.1", True)]
    sonuc = engine.hesapla(gorevler, proje_baslangic=datetime(2026, 3, 1))
    print(f"P80 bitis: {sonuc.proje_bitis_p80.strftime('%d.%m.%Y')}")

    Uyari:
    Kritik gorev yoksa (kritik=False) proje sigma = 0 doner.
    Bu durumda P80/90/95 tarihleri P50 ile ayni olur.
    Gercek projede en az 1 kritik gorev isaretlenmelidir.
    """

    # Minimum guvenilir iyimser sure: 0.5 gun
    MIN_IYIMSER = 0.5

    def hesapla(
    self,
    gorevler: List[PertGorev],
    proje_baslangic: datetime,
    sozlesme_bitis: Optional[datetime] = None,
    ) -> PertProjeSonucu:
        """
    Gorev listesi icin tam PERT analizi gerceklestirir.

    Args:
    gorevler : PertGorev nesnelerinin listesi
    proje_baslangic : Projenin fiili baslangic tarihi
    sozlesme_bitis : Ihale / sozlesme bitis tarihi (opsiyonel).
    Verilirse, P50 tarihiyle karsilastirilarak
    asim gunleri hesaplanir.

    Returns:
    PertProjeSonucu: Proje ve gorev bazli tum istatistikler.
    """
    if not gorevler:
        logger.warning("PERT: Bos gorev listesi. Hesaplama atlanadi.")
        bos_tarih = proje_baslangic
        return PertProjeSonucu(
        toplam_pert_sure=0.0,
        proje_sapma=0.0,
        proje_varyans=0.0,
        proje_bitis_p0=bos_tarih,
        proje_bitis_p50=bos_tarih,
        proje_bitis_p80=bos_tarih,
        proje_bitis_p90=bos_tarih,
        proje_bitis_p95=bos_tarih,
        uyari_listesi=["Gorev listesi bos; analiz yapilamadi."],
        )

        logger.info(
        f"PERT analizi baslatildi: {len(gorevler)} is kalemi, "
        f"baslangic={proje_baslangic.strftime('%d.%m.%Y')}"
        )

        uyarilar: List[str] = []
        gorev_sonuclari: List[PertGorevSonucu] = []

        # ── Gorev bazli hesaplamalar ────────────────────────────────────────
        for g in gorevler:
            gs = self._gorev_hesapla(g, proje_baslangic)
            gorev_sonuclari.append(gs)

            # Veri kalitesi kontrolleri
            if g.iyimser_gun <= 0:
                uyarilar.append(
                f"'{g.ad}': Iyimser sure <= 0 -- "
                f"minimum {self.MIN_IYIMSER} gun olarak duzeltildi."
                )
                if g.kotumser_gun < g.olasi_gun:
                    uyarilar.append(
                    f"'{g.ad}': Kotumser sure ({g.kotumser_gun}g) < "
                    f"Olasilikli sure ({g.olasi_gun}g). Deger mantigi kontrolu."
                    )
                    if g.olasi_gun < g.iyimser_gun:
                        uyarilar.append(
                        f"'{g.ad}': Olasilikli sure ({g.olasi_gun}g) < "
                        f"Iyimser sure ({g.iyimser_gun}g). Veri hatasi."
                        )
                        if gs.standart_sapma > gs.pert_sure * 0.5:
                            uyarilar.append(
                            f"'{g.ad}': Yuksek belirsizlik -- sigma/t_e = "
                            f"{gs.standart_sapma/gs.pert_sure:.1%}. "
                            "Kapsam tanimi gozden gecirilmeli."
                            )

                            # ── Proje istatistikleri (CLT -- sadece kritik gorevler) ────────────
                            kritik_gorevler = [gs for gs in gorev_sonuclari if gs.kritik]

                            if not kritik_gorevler:
                                # Kritik gorev isaretlenmemisse tum gorevleri kullan
                                kritik_gorevler = gorev_sonuclari
                                uyarilar.append(
                                "Kritik gorev isaretlenmedi. Tum gorevler uzerinden "
                                "proje sigma hesaplandi. CPM sonrasi kritik yol isaretini kontrol edin."
                                )

                                toplam_pert = sum(gs.pert_sure for gs in kritik_gorevler)
                                toplam_varyans = sum(gs.varyans for gs in kritik_gorevler)
                                proje_sigma = math.sqrt(toplam_varyans) if toplam_varyans > 0 else 0.0

                                # ── Proje bitis tarihleri ────────────────────────────────────────────
                                p_bas = proje_baslangic

                                # P0: Kritik gorevlerin iyimser surelerinin toplami
                                iyimser_toplam = sum(
                                g.iyimser_gun for g in gorevler
                                if any(gs.gorev_id == g.gorev_id and gs.kritik for gs in kritik_gorevler)
                                )
                                proje_bitis_p0 = p_bas + timedelta(days=iyimser_toplam or toplam_pert * 0.8)
                                proje_bitis_p50 = p_bas + timedelta(days=toplam_pert)
                                proje_bitis_p80 = p_bas + timedelta(days=toplam_pert + Z_P80 * proje_sigma)
                                proje_bitis_p90 = p_bas + timedelta(days=toplam_pert + Z_P90 * proje_sigma)
                                proje_bitis_p95 = p_bas + timedelta(days=toplam_pert + Z_P95 * proje_sigma)

                                # ── Sozlesme karsilastirmasi ────────────────────────────────────────
                                sozlesme_asim: Optional[int] = None
                                if sozlesme_bitis:
                                    asim_gun = (proje_bitis_p50 - sozlesme_bitis).days
                                    sozlesme_asim = asim_gun
                                    if asim_gun > 0:
                                        uyarilar.append(
                                        f"SOZLESME ASILMASI RISKI: Beklenen bitis "
                                        f"({proje_bitis_p50.strftime('%d.%m.%Y')}) sozlesme "
                                        f"tarihini ({sozlesme_bitis.strftime('%d.%m.%Y')}) "
                                        f"{asim_gun} gun asiyor. "
                                        f"P95 senaryosunda asim: "
                                        f"{(proje_bitis_p95 - sozlesme_bitis).days} gun."
                                        )
                                        logger.warning(
                                        f"SOZLESME ASILMASI: {asim_gun} gun asim bekleniyor "
                                        f"(P50={proje_bitis_p50.strftime('%d.%m.%Y')}, "
                                        f"Sozlesme={sozlesme_bitis.strftime('%d.%m.%Y')})"
                                        )
                                    elif asim_gun > -7:
                                        uyarilar.append(
                                        f"Sozlesme tarihi icin tampon dusuk: {abs(asim_gun)} gun. "
                                        "P80 senaryosunda asim riski var."
                                        )

                                        logger.info(
                                        f"PERT tamamlandi: toplam_t_e={toplam_pert:.1f} gun, "
                                        f"sigma={proje_sigma:.2f} gun, "
                                        f"P80={proje_bitis_p80.strftime('%d.%m.%Y')}"
                                        )

                                        return PertProjeSonucu(
                                        toplam_pert_sure=round(toplam_pert, 2),
                                        proje_sapma=round(proje_sigma, 3),
                                        proje_varyans=round(toplam_varyans, 3),
                                        proje_bitis_p0=proje_bitis_p0,
                                        proje_bitis_p50=proje_bitis_p50,
                                        proje_bitis_p80=proje_bitis_p80,
                                        proje_bitis_p90=proje_bitis_p90,
                                        proje_bitis_p95=proje_bitis_p95,
                                        gorev_sonuclari=gorev_sonuclari,
                                        uyari_listesi=uyarilar,
                                        sozlesme_asim_gun=sozlesme_asim,
                                        )

                                        def _gorev_hesapla(
                                        self,
                                        g: PertGorev,
                                        proje_bas: datetime,
                                        ) -> PertGorevSonucu:
                                            """
                                        Tek bir is kalemi icin PERT istatistiklerini hesaplar.

                                        Formul (Malcolm 1959 / PMBOK 7):
                                        t_e = (t_o + 4 * t_m + t_p) / 6
                                        sigma = (t_p - t_o) / 6
                                        sigma2 = sigma^2

                                        Args:
                                        g : Hesaplanacak PertGorev nesnesi
                                        proje_bas : Proje veya gorev baslangic tarihi

                                        Returns:
                                        PertGorevSonucu: Gorev bazli tum istatistikler ve tarihler.
                                        """
                                        # Veri sanitetizasyonu
                                        t_o = max(self.MIN_IYIMSER, float(g.iyimser_gun))
                                        t_m = max(t_o, float(g.olasi_gun))
                                        t_p = max(t_m, float(g.kotumser_gun))

                                        # PERT beklenen suresi
                                        t_e = (t_o + 4.0 * t_m + t_p) / 6.0

                                        # Standart sapma ve varyans
                                        sigma = (t_p - t_o) / 6.0
                                        sigma2 = sigma ** 2

                                        # Baslangic tarihi: gorev icin verilmisse o, yoksa proje baslangici
                                        bas = g.baslangic or proje_bas

                                        # Bitis tarihleri
                                        bitis_p0 = bas + timedelta(days=t_o)
                                        bitis_p50 = bas + timedelta(days=t_e)
                                        bitis_p80 = bas + timedelta(days=t_e + Z_P80 * sigma)
                                        bitis_p90 = bas + timedelta(days=t_e + Z_P90 * sigma)
                                        bitis_p95 = bas + timedelta(days=t_e + Z_P95 * sigma)

                                        # Yorum uretimi
                                        yorum = self._yorum_uret(g, t_e, sigma)

                                        return PertGorevSonucu(
                                        gorev_id=g.gorev_id,
                                        ad=g.ad,
                                        wbs_kodu=g.wbs_kodu,
                                        kritik=g.kritik,
                                        pert_sure=round(t_e, 2),
                                        standart_sapma=round(sigma, 3),
                                        varyans=round(sigma2, 4),
                                        bitis_p0=bitis_p0,
                                        bitis_p50=bitis_p50,
                                        bitis_p80=bitis_p80,
                                        bitis_p90=bitis_p90,
                                        bitis_p95=bitis_p95,
                                        yorum=yorum,
                                        )

                                        @staticmethod
                                        def _yorum_uret(g: PertGorev, t_e: float, sigma: float) -> str:
                                            """
                                            Is kalemi icin insanca okunabilir risk yorumu uretir.

                                            Belirsizlik orani = sigma / t_e (CV - Degisim Katsayisi)
                                            """
                                            if t_e <= 0:
                                                return "Gecersiz sure verisi."

                                                cv = sigma / t_e # Degisim katsayisi

                                                if cv < 0.10:
                                                    risk = "Dusuk belirsizlik — sure tahmini guvenilir."
                                                elif cv < 0.20:
                                                    risk = "Orta belirsizlik — tampon gun planlamasi onerilir."
                                                elif cv < 0.35:
                                                    risk = "Yuksek belirsizlik — kapsamli risk plani olusturun."
                                                else:
                                                    risk = "Kritik belirsizlik — is tanimi yeniden yapilmali."

                                                    asim = g.kotumser_gun - t_e
                                                    return (
                                                    f"Beklenen: {t_e:.1f} gun (sigma={sigma:.2f}g). "
                                                    f"Kotumser senaryoda +{asim:.1f} gun ek sure. {risk}"
                                                    )
