"""Kat bazlı beton + kalıp özeti (saf Python — PyQt/AutoCAD bağımsız).

Neyi çözüyoruz?
    Kolon, perde, kiriş, döşeme ve temel elemanları ayrı sekmelerde
    hesaplanıyor; müteahhit/hakediş için bunların KAT KAT beton (m³) ve
    kalıp (m²) toplamı tek tabloda gerekiyor. Bu modül ham kalemleri
    (kat, eleman, adet, beton, kalıp) alıp kat + eleman bazında gruplar,
    kat ara toplamları, eleman toplamları ve genel toplamı üretir.
    Hesap YAPMAZ — değerler her sekmenin kendi formülünden gelir, burada
    sadece toplanır (çift formül = sapma riski).

Nasıl test ederiz?
    scratchpad/test_kat_ozeti.py: 2 kat + temel, aynı kat+eleman birleşir,
    kat sırası korunur, Temel en üstte, katsız kalemler en altta, toplamlar
    kalemlerin toplamına eşit.
"""

from typing import Any, Dict, Iterable, List, Optional

TEMEL_KAT = "Temel"
KATSIZ_ETIKET = "Kat belirtilmemiş"

# Kat içinde elemanların gösterim sırası (listede olmayanlar sona, geliş sırasıyla)
ELEMAN_SIRASI = ("Radye", "Temel Kirişi", "Kolon", "Perde", "Kiriş", "Döşeme", "Saçak", "Merdiven")


def _sayi(deger: Any) -> float:
    try:
        return float(deger)
    except (TypeError, ValueError):
        return 0.0


def kat_ozeti_olustur(kalemler: Iterable[Dict[str, Any]],
                      kat_sirasi: Optional[List[str]] = None) -> Dict[str, Any]:
    """Kalemleri kat + eleman bazında gruplar.

    Args:
        kalemler: her biri {"kat", "eleman", "adet", "beton_m3", "kalip_m2"}.
            Boş kat -> KATSIZ_ETIKET. Beton ve kalıp ikisi de 0 olan kalem atlanır.
        kat_sirasi: katların gösterim sırası (Demir Metrajı kat listesi).
            Temel her zaman en üstte, listede olmayan katlar geliş sırasıyla
            sonra, katsız kalemler en altta.

    Returns:
        {"katlar": [{"kat", "elemanlar": [{"eleman","adet","beton_m3","kalip_m2"}],
                     "beton_m3", "kalip_m2"}],
         "eleman_toplamlari": [{"eleman","adet","beton_m3","kalip_m2"}],
         "beton_m3", "kalip_m2"}  — tüm değerler 3 haneye yuvarlanmış.
    """
    gruplar: Dict[str, Dict[str, Dict[str, float]]] = {}
    gelis_sirasi: List[str] = []
    eleman_gelis: List[str] = []
    for k in kalemler:
        beton = _sayi(k.get("beton_m3"))
        kalip = _sayi(k.get("kalip_m2"))
        if beton == 0 and kalip == 0:
            continue
        kat = (k.get("kat") or "").strip() or KATSIZ_ETIKET
        eleman = (k.get("eleman") or "").strip() or "Diğer"
        if kat not in gruplar:
            gruplar[kat] = {}
            gelis_sirasi.append(kat)
        if eleman not in eleman_gelis:
            eleman_gelis.append(eleman)
        g = gruplar[kat].setdefault(eleman, {"adet": 0.0, "beton_m3": 0.0, "kalip_m2": 0.0})
        g["adet"] += _sayi(k.get("adet", 1))
        g["beton_m3"] += beton
        g["kalip_m2"] += kalip

    sira: List[str] = []
    if TEMEL_KAT in gruplar:
        sira.append(TEMEL_KAT)
    for kat in (kat_sirasi or []):
        if kat in gruplar and kat not in sira:
            sira.append(kat)
    for kat in gelis_sirasi:
        if kat not in sira and kat != KATSIZ_ETIKET:
            sira.append(kat)
    if KATSIZ_ETIKET in gruplar:
        sira.append(KATSIZ_ETIKET)

    def _eleman_anahtari(ad: str):
        return (ELEMAN_SIRASI.index(ad) if ad in ELEMAN_SIRASI else len(ELEMAN_SIRASI),
                eleman_gelis.index(ad))

    katlar = []
    eleman_top: Dict[str, Dict[str, float]] = {}
    g_beton = g_kalip = 0.0
    for kat in sira:
        elemanlar = []
        k_beton = k_kalip = 0.0
        for eleman in sorted(gruplar[kat], key=_eleman_anahtari):
            d = gruplar[kat][eleman]
            elemanlar.append({"eleman": eleman, "adet": d["adet"],
                              "beton_m3": round(d["beton_m3"], 3), "kalip_m2": round(d["kalip_m2"], 3)})
            k_beton += d["beton_m3"]
            k_kalip += d["kalip_m2"]
            t = eleman_top.setdefault(eleman, {"adet": 0.0, "beton_m3": 0.0, "kalip_m2": 0.0})
            for alan in ("adet", "beton_m3", "kalip_m2"):
                t[alan] += d[alan]
        katlar.append({"kat": kat, "elemanlar": elemanlar,
                       "beton_m3": round(k_beton, 3), "kalip_m2": round(k_kalip, 3)})
        g_beton += k_beton
        g_kalip += k_kalip

    eleman_toplamlari = [
        {"eleman": e, "adet": eleman_top[e]["adet"],
         "beton_m3": round(eleman_top[e]["beton_m3"], 3), "kalip_m2": round(eleman_top[e]["kalip_m2"], 3)}
        for e in sorted(eleman_top, key=_eleman_anahtari)
    ]
    return {"katlar": katlar, "eleman_toplamlari": eleman_toplamlari,
            "beton_m3": round(g_beton, 3), "kalip_m2": round(g_kalip, 3)}


def adet_metni(adet: float) -> str:
    """12.0 -> "12", 2.5 -> "2.5" (radye gibi adetsiz kalemlerde 1)."""
    return f"{adet:g}"


def ozet_tablo_satirlari(ozet: Dict[str, Any]) -> List[List[Any]]:
    """Ekran ve Excel için düz satırlar: [Kat, Eleman, Adet, Beton, Kalıp, tür].

    tür: "kalem" | "ara" (kat toplamı) | "eleman" (eleman toplamı) | "genel".
    """
    satirlar: List[List[Any]] = []
    for k in ozet["katlar"]:
        for e in k["elemanlar"]:
            satirlar.append([k["kat"], e["eleman"], adet_metni(e["adet"]), e["beton_m3"], e["kalip_m2"], "kalem"])
        etiket = "TEMEL TOPLAMI" if k["kat"] == TEMEL_KAT else "KAT TOPLAMI"
        satirlar.append([k["kat"], etiket, "", k["beton_m3"], k["kalip_m2"], "ara"])
    for e in ozet["eleman_toplamlari"]:
        satirlar.append(["TÜM KATLAR", e["eleman"], adet_metni(e["adet"]), e["beton_m3"], e["kalip_m2"], "eleman"])
    satirlar.append(["", "GENEL TOPLAM", "", ozet["beton_m3"], ozet["kalip_m2"], "genel"])
    return satirlar
