# -*- coding: utf-8 -*-
"""
Kesim Optimizasyonu Cekirdegi
==============================
Saf Python. PyQt/AutoCAD/DemirBilgisi/KesimParcasi bagimliligi YOKTUR.
FFD (First Fit Decreasing) mantigi app/ui/demir_hesaplama_window.py
icindeki _ffd_algoritma ile BIREBIR AYNIDIR (bkz. ffd_yerlestir) -
uzerine fire siniflandirmasi (kullanilabilir artik / cop fire) ve
desen gruplama eklenmistir.

Yazar: INSAAT METRAJ PRO
Tarih: 2026
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class CubukPlani:
    """Tek bir standart cubuktan kesilen parcalarin plani."""
    parcalar: List[float]      # cm, kesilen parca boylari
    kullanilan_cm: float
    artik_cm: float
    kullanilabilir_mi: bool    # artik_cm >= esik_cm
    standart_disi: bool = False  # tek parca standart boydan uzun (kesim yapilamadi)


@dataclass
class DesenGrubu:
    """Ayni kesim desenine (parca kombinasyonuna) sahip cubuklarin grubu."""
    desen: Tuple[float, ...]   # kesilen parcalar, azalan sirali (karsilastirma anahtari)
    artik_cm: float
    adet: int
    kullanilabilir_mi: bool
    standart_disi: bool = False  # True ise: tek parca standart boydan uzun,
    # sahada TEK cubuktan kesilemez - birden fazla cubuk + TS 500 bindirme
    # eki gerekir. "Durum" kolonunda cop/SAKLA yerine ayri uyari gosterilmeli.


@dataclass
class CapSonucu:
    """Tek bir cap icin kesim optimizasyonu sonucu."""
    cap: int                   # mm - sadece raporlama icin tasinir, hesaba katilmaz
    standart_boy_cm: float
    esik_cm: float
    cubuklar: List[CubukPlani]
    desenler: List[DesenGrubu]
    parca_sayisi: int
    cubuk_adedi: int
    toplam_kullanilan_cm: float
    toplam_kapasite_cm: float
    toplam_fire_cm: float
    fire_yuzde: float
    kullanilabilir_artik_cm: float
    cop_fire_cm: float
    standart_disi_adet: int = 0        # standart boyu asan cubuk (parca) sayisi
    standart_disi_boylar: Tuple[float, ...] = ()  # asan parcalarin boylari (tekil, azalan sirali)


def ffd_yerlestir(boylar: List[float], standart_boy: float) -> List[List[float]]:
    """
    First Fit Decreasing: parcalari azalan sirayla standart boy cubuklara yerlestirir.

    _ffd_algoritma (demir_hesaplama_window.py, satir ~976) ile BIREBIR AYNI
    mantik - degistirilmedi, sadece bagimsiz dosyaya tasindi.

    Donus: [[parca_boy, ...], ...] - her ic liste bir cubugun kesimleridir.
    """
    sirali = sorted(boylar, reverse=True)
    cubuklar: List[List[float]] = []
    for parca in sirali:
        if parca > standart_boy:
            # Standart boyu asan parca - tek cubuk, kesim yapilamaz
            cubuklar.append([parca])
            continue
        yerlestirildi = False
        for cubuk in cubuklar:
            kalan = standart_boy - sum(cubuk)
            if kalan >= parca:
                cubuk.append(parca)
                yerlestirildi = True
                break
        if not yerlestirildi:
            cubuklar.append([parca])
    return cubuklar


def kesim_plani_hesapla(
    boylar: List[float],
    cap: int,
    standart_boy_cm: float,
    esik_cm: float,
) -> CapSonucu:
    """
    Tek bir cap icin FFD kesim plani + fire siniflandirmasi + desen gruplama uretir.

    Args:
        boylar: kesilecek parca boylari (cm), adetler ACILMIS halde
                (5 adet 250cm -> [250.0]*5, tek eleman = tek parca)
        cap: demir capi (mm) - sadece raporlamada tasinir
        standart_boy_cm: piyasa cubuk boyu (cm)
        esik_cm: bu deger VE USTU artik "kullanilabilir" sayilir, ALTI "cop fire"

    Returns:
        CapSonucu

    Not (standart_disi cubuk): Bir parca standart_boy_cm'den uzunsa (kesim
    yapilamaz, tek basina bir "cubuk" olarak yerlesir), o cubugun artigi
    hesaplanamaz (negatif cikar) - bu durumda artik_cm=0.0 ve
    standart_disi=True isaretlenir, kullanilabilir_mi=False sayilir.
    Bu cubuk sayisini (cubuk_adedi) ETKILEMEZ, sadece fire toplamina
    negatif deger karismasini onler. SAHADA bu, TEK cubuktan kesilemeyen,
    birden fazla cubugun TS 500 bindirme ekiyle birlestirilmesi gereken
    bir parca demektir - "cop fire" DEGILDIR. Cagiran kod (UI katmani)
    CapSonucu.standart_disi_adet > 0 oldugunda kullaniciyi ACIKCA uyarmali
    (bkz. Rev-124, demir_hesaplama_window.py _kesim_hesapla).
    """
    if not boylar:
        raise ValueError("boylar listesi bos olamaz")
    if standart_boy_cm <= 0:
        raise ValueError("standart_boy_cm pozitif olmali")
    if esik_cm < 0:
        raise ValueError("esik_cm negatif olamaz")

    cubuklar_ham = ffd_yerlestir(boylar, standart_boy_cm)

    cubuklar: List[CubukPlani] = []
    for cubuk in cubuklar_ham:
        kullanilan = sum(cubuk)
        standart_disi = kullanilan > standart_boy_cm
        artik = 0.0 if standart_disi else (standart_boy_cm - kullanilan)
        cubuklar.append(CubukPlani(
            parcalar=cubuk,
            kullanilan_cm=kullanilan,
            artik_cm=artik,
            kullanilabilir_mi=(not standart_disi) and artik >= esik_cm,
            standart_disi=standart_disi,
        ))

    # --- Desen gruplama: ayni parca kombinasyonuna sahip cubuklari birlestir ---
    desen_map: Dict[Tuple[float, ...], Dict] = {}
    for cp in cubuklar:
        desen_key = tuple(sorted(cp.parcalar, reverse=True))
        if desen_key not in desen_map:
            desen_map[desen_key] = {
                "artik_cm": cp.artik_cm,
                "adet": 0,
                "kullanilabilir_mi": cp.kullanilabilir_mi,
                "standart_disi": cp.standart_disi,
            }
        desen_map[desen_key]["adet"] += 1

    desenler = [
        DesenGrubu(
            desen=desen,
            artik_cm=v["artik_cm"],
            adet=v["adet"],
            kullanilabilir_mi=v["kullanilabilir_mi"],
            standart_disi=v["standart_disi"],
        )
        for desen, v in desen_map.items()
    ]
    desenler.sort(key=lambda d: d.adet, reverse=True)

    standart_disi_cubuklar = [cp for cp in cubuklar if cp.standart_disi]
    standart_disi_adet = len(standart_disi_cubuklar)
    standart_disi_boylar = tuple(sorted(
        {cp.parcalar[0] for cp in standart_disi_cubuklar}, reverse=True
    ))

    toplam_kullanilan = sum(cp.kullanilan_cm for cp in cubuklar)
    toplam_kapasite = standart_boy_cm * len(cubuklar)
    toplam_fire = sum(cp.artik_cm for cp in cubuklar)
    fire_yuzde = (toplam_fire / toplam_kapasite * 100.0) if toplam_kapasite > 0 else 0.0

    kullanilabilir_artik = sum(cp.artik_cm for cp in cubuklar if cp.kullanilabilir_mi)
    cop_fire = sum(
        cp.artik_cm for cp in cubuklar
        if not cp.kullanilabilir_mi and not cp.standart_disi
    )

    return CapSonucu(
        cap=cap,
        standart_boy_cm=standart_boy_cm,
        esik_cm=esik_cm,
        cubuklar=cubuklar,
        desenler=desenler,
        parca_sayisi=len(boylar),
        cubuk_adedi=len(cubuklar),
        toplam_kullanilan_cm=toplam_kullanilan,
        toplam_kapasite_cm=toplam_kapasite,
        toplam_fire_cm=toplam_fire,
        fire_yuzde=fire_yuzde,
        kullanilabilir_artik_cm=kullanilabilir_artik,
        cop_fire_cm=cop_fire,
        standart_disi_adet=standart_disi_adet,
        standart_disi_boylar=standart_disi_boylar,
    )


def coklu_cap_kesim_plani_hesapla(
    cap_parcalari: Dict[int, List[float]],
    standart_boy_cm: float,
    esik_cm: float,
) -> Dict[int, CapSonucu]:
    """Birden fazla cap icin kesim_plani_hesapla'yi cap bazinda calistirir."""
    return {
        cap: kesim_plani_hesapla(boylar, cap, standart_boy_cm, esik_cm)
        for cap, boylar in cap_parcalari.items()
        if boylar
    }
