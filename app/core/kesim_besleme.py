# -*- coding: utf-8 -*-
"""
Kesim Besleme Adaptoru (AutoCAD -> Kesim Optimizasyonu Kopru Katmani)
======================================================================
Bu dosya, autocad_connector.py'nin urettigi DemirBilgisi kayitlarini
kesim_optimizasyon.py'nin bekledigi duz List[KesimParcasi] formatina
cevirir. Cekirdek (kesim_optimizasyon.py) bu dosyaya veya
autocad_connector.py'ye HICBIR bagimlilik icermez - sadece
KesimParcasi tuketir.

Yazar: INSAAT METRAJ PRO
Tarih: 2026
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any

from app.core.autocad_connector import DemirBilgisi
from app.core.kesim_optimizasyon import coklu_cap_kesim_plani_hesapla, CapSonucu

logger = logging.getLogger(__name__)


@dataclass
class KesimParcasi:
    """Kesim optimizasyonuna girecek tek bir demir parcasi."""
    cap: int             # mm, ciplak sayi (orn. 12) - "Ø12" veya "12" DEGIL
    boy_cm: float         # cm, DAIMA santimetre (adapter normalize eder)
    adet: int
    eleman_tipi: str = ""  # Kolon/Perde/Kiris/Doseme/Temel (esnek/sabit boy kurali icin, opsiyonel)
    kaynak_handle: str = ""  # AutoCAD handle - hata ayiklama/iz surme icin, opsiyonel


def demirlerden_kesim_parcalari_uret(
    demirler: List[DemirBilgisi],
    boy_bindirme_dahil: bool,
    birim: str = "cm",
) -> List[KesimParcasi]:
    """
    DemirBilgisi listesini KesimParcasi listesine cevirir.

    Args:
        demirler: get_rebar_report_from_selection()["basarili"] veya
                   calculate_vertical_rebar_unified()["demirler"] listesi.
        boy_bindirme_dahil: DemirBilgisi.boy degerinin bindirme/filiz payi
            icerip icermedigine dair ACIK beyan. Kod bunu METINDEN
            AYIRT EDEMEZ (AutoCAD'deki L= degeri oldugu gibi okunuyor,
            uzerine hicbir ekleme/cikarma yapilmiyor) - bu yuzden
            varsayilan deger YOK, caller'in cizim standardina gore
            bilerek gecmesi zorunlu. Su an bu bayrak kesim hesabini
            DEGISTIRMEZ (sadece iz surme/log icin tasinir) - bindirme
            payini kesim planina dahil etme mantigi kesim_optimizasyon.py
            tarafinda, eleman_tipi'ne gore (Rev-96 karari) uygulanmali.
        birim: demirler listesindeki DemirBilgisi.boy alaninin hangi
            birimde uretildigi ("cm" veya "m") - autocad_connector
            fonksiyonlarina gecirilen 'birim' parametresiyle AYNI olmali.

    Returns:
        List[KesimParcasi] - cap bazinda gruplama YAPILMAZ (cekirdek
        tarafinda yapilir), gecersiz (gecerli=False) demirler atlanir.
    """
    if birim.lower() not in ("cm", "m"):
        raise ValueError(f"Desteklenmeyen birim: {birim!r} (cm veya m olmali)")

    parcalar: List[KesimParcasi] = []
    for demir in demirler:
        if not demir.gecerli:
            continue
        if demir.cap <= 0 or demir.boy <= 0 or demir.adet <= 0:
            logger.warning(
                f"Gecersiz demir atlandi (handle={demir.handle}): "
                f"cap={demir.cap}, boy={demir.boy}, adet={demir.adet}"
            )
            continue

        boy_cm = demir.boy if birim.lower() == "cm" else demir.boy * 100.0

        parcalar.append(KesimParcasi(
            cap=demir.cap,
            boy_cm=boy_cm,
            adet=demir.adet,
            eleman_tipi=demir.eleman_tipi,
            kaynak_handle=demir.handle,
        ))

    logger.info(
        f"Kesim besleme: {len(demirler)} demir kaydindan {len(parcalar)} "
        f"gecerli KesimParcasi uretildi (boy_bindirme_dahil={boy_bindirme_dahil})"
    )
    return parcalar


def rapordan_kesim_parcalari_uret(
    rapor: Dict[str, Any],
    boy_bindirme_dahil: bool,
    birim: str = "cm",
) -> List[KesimParcasi]:
    """
    get_rebar_report_from_selection() veya calculate_vertical_rebar_unified()
    doner degerini dogrudan kabul eder, ilgili DemirBilgisi listesini
    otomatik tespit edip demirlerden_kesim_parcalari_uret()'e devreder.

    Tespit kurali:
        - "basarili" anahtari varsa -> get_rebar_report_from_selection ciktisi
        - "demirler" anahtari varsa -> calculate_vertical_rebar_unified ciktisi
    """
    if "basarili" in rapor and isinstance(rapor["basarili"], list):
        demirler = rapor["basarili"]
    elif "demirler" in rapor and isinstance(rapor["demirler"], list):
        demirler = rapor["demirler"]
    else:
        raise ValueError(
            "Rapor formati taninmadi: 'basarili' veya 'demirler' anahtari bulunamadi"
        )

    return demirlerden_kesim_parcalari_uret(demirler, boy_bindirme_dahil, birim)


def kesim_parcalarini_capa_gore_grupla(
    parcalar: List[KesimParcasi],
) -> Dict[int, List[float]]:
    """
    List[KesimParcasi]'yi kesim_optimizasyon.coklu_cap_kesim_plani_hesapla()'nin
    bekledigi {cap: [boy_cm, boy_cm, ...]} formatina cevirir (adet -> boy_cm
    tekrarlanarak acilir, tipki UI'nin manuel giris yolundaki cap_parcalari
    ile ayni format).
    """
    cap_parcalari: Dict[int, List[float]] = {}
    for p in parcalar:
        cap_parcalari.setdefault(p.cap, []).extend([p.boy_cm] * p.adet)
    return cap_parcalari


def autocad_secimden_kesim_plani_uret(
    rapor: Dict[str, Any],
    boy_bindirme_dahil: bool,
    standart_boy_cm: float,
    esik_cm: float,
    birim: str = "cm",
) -> Dict[int, CapSonucu]:
    """
    Ucdan uca kopru: AutoCAD rapor sozlugunden (get_rebar_report_from_selection
    veya calculate_vertical_rebar_unified ciktisi) dogrudan cap bazinda
    kesim_optimizasyon sonucu uretir.

    rapor -> [KesimParcasi] -> {cap: [boy_cm,...]} -> {cap: CapSonucu}
    """
    parcalar = rapordan_kesim_parcalari_uret(rapor, boy_bindirme_dahil, birim)
    if not parcalar:
        return {}
    cap_parcalari = kesim_parcalarini_capa_gore_grupla(parcalar)
    return coklu_cap_kesim_plani_hesapla(cap_parcalari, standart_boy_cm, esik_cm)
