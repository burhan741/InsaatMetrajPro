"""Temel kirişi (SBH) demir hesabı — filiz + tevzi (saf Python, PyQt bağımsız).

Neyi çözüyoruz?
    SBH kesit detayında yalnız iki poz var (ihale idaresiyle teyitli):
      Filiz  Øf/a  l=...  düşey, kiriş boyunca her a cm'de bir, 2 yüz
      Tevzi  Øt/a        yatay, kiriş boyunca uzanır, yükseklik boyunca her a cm'de bir sıra, 2 yüz
    Değerler SBH TİPİNE göre değişir -> hepsi tip parametresi. Beton/kalıp
    satırındaki L (m) ve y (cm) kullanılır; ayrı seçim yok.

    Filiz adet: aralıklı donatı aracıyla AYNI kural (ceil(L/a)+1) — aynı fonksiyon çağrılır.
    Tevzi bindirme: ham boy > stok ise k = ceil((ham − stok) / (stok − bindirme)),
    çubuk boyu = ham + k × bindirme. Kesim listesine bindirmeli boy STOK BOYUNA
    BÖLÜNEREK gider (kesim çekirdeği bindirme eklemiyor, 12 m üstünü "standart dışı" sayıyor).

Nasıl test ederiz?
    scratchpad/test_temel_kirisi_demir.py — brief S1..S7 (programsız).
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from app.core.autocad_connector import DEMIR_AGIRLIK_TABLOSU, aralikli_donati_adet_hesapla

VARSAYILAN_SBH_DEMIR: Dict[str, Any] = {
    "filiz_cap": 12,
    "filiz_aralik_cm": 20.0,
    "filiz_boy_cm": 280.0,
    "filiz_yuz": 2,
    "tevzi_cap": 10,
    "tevzi_aralik_cm": 20.0,
    "tevzi_sira": None,          # None/0 -> formül: ceil((y − 2·pas) / aralık) + 1
    "tevzi_yuz": 2,
    "tevzi_ek_boy_cm": 0.0,
    "tevzi_bindirme_cm": 50.0,
    "stok_boy_m": 12.0,
    "pas_payi_cm": 5.0,
}

# Parametre formunda gösterim sırası: (anahtar, etiket, birim)
SBH_DEMIR_ALANLARI: List[Tuple[str, str, str]] = [
    ("filiz_cap", "Filiz Ø", "mm"),
    ("filiz_aralik_cm", "Filiz aralık", "cm"),
    ("filiz_boy_cm", "Filiz boy (l)", "cm"),
    ("filiz_yuz", "Filiz yüz sayısı", "adet"),
    ("tevzi_cap", "Tevzi Ø", "mm"),
    ("tevzi_aralik_cm", "Tevzi aralık", "cm"),
    ("tevzi_sira", "Tevzi sıra sayısı (yüz başına)", "adet"),
    ("tevzi_yuz", "Tevzi yüz sayısı", "adet"),
    ("tevzi_ek_boy_cm", "Tevzi ek boy (ankraj/kanca)", "cm"),
    ("tevzi_bindirme_cm", "Tevzi bindirme", "cm"),
    ("stok_boy_m", "Stok çubuk boyu", "m"),
    ("pas_payi_cm", "Pas payı", "cm"),
]


def _tavan(x: float) -> int:
    """Kayan nokta güvenli tavan (9 hane) — 11.0000000001 -> 11."""
    return math.ceil(round(x, 9))


def sbh_parametre_tamamla(p: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Eksik anahtarları varsayılanla doldurur (kayıtlı eski parametreler bozulmasın)."""
    tam = dict(VARSAYILAN_SBH_DEMIR)
    for k, v in (p or {}).items():
        if k in tam:
            tam[k] = v
    if not tam["tevzi_sira"]:
        tam["tevzi_sira"] = None
    return tam


def sbh_parametre_dogrula(p: Dict[str, Any]) -> str:
    """Hata metni; geçerliyse boş."""
    for anahtar in ("filiz_cap", "tevzi_cap"):
        if int(p[anahtar]) not in DEMIR_AGIRLIK_TABLOSU:
            return f"{anahtar.split('_')[0].capitalize()} çapı Ø{p[anahtar]} birim ağırlık tablosunda yok"
    for anahtar, ad in (("filiz_aralik_cm", "Filiz aralığı"), ("filiz_boy_cm", "Filiz boyu"),
                        ("tevzi_aralik_cm", "Tevzi aralığı"), ("stok_boy_m", "Stok boy")):
        if float(p[anahtar]) <= 0:
            return f"{ad} sıfırdan büyük olmalı"
    for anahtar, ad in (("filiz_yuz", "Filiz yüz sayısı"), ("tevzi_yuz", "Tevzi yüz sayısı")):
        if int(p[anahtar]) < 0:
            return f"{ad} negatif olamaz"
    if float(p["tevzi_bindirme_cm"]) < 0 or float(p["tevzi_ek_boy_cm"]) < 0 or float(p["pas_payi_cm"]) < 0:
        return "Bindirme, ek boy ve pas payı negatif olamaz"
    if float(p["tevzi_bindirme_cm"]) / 100.0 >= float(p["stok_boy_m"]):
        return "Bindirme stok çubuk boyundan kısa olmalı"
    return ""


def tevzi_bindirme_sayisi(ham_boy_m: float, stok_boy_m: float, bindirme_cm: float) -> int:
    """k: ham boy stok boyu aşıyorsa gereken bindirme adedi."""
    if ham_boy_m <= stok_boy_m + 1e-9:
        return 0
    return _tavan((ham_boy_m - stok_boy_m) / (stok_boy_m - bindirme_cm / 100.0))


def temel_kirisi_demir_hesapla(uzunluk_m: float, yukseklik_cm: float,
                               parametre: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tek SBH satırının filiz + tevzi demiri.

    Returns:
        dict: filiz_yuz_adet, filiz_adet, filiz_uzunluk_m, filiz_kg, tevzi_sira,
              tevzi_cubuk, tevzi_ham_boy_m, tevzi_k, tevzi_boy_m, tevzi_uzunluk_m,
              tevzi_kg, toplam_kg, cap_kg {çap: kg}, hata.
    """
    sonuc: Dict[str, Any] = {
        "filiz_yuz_adet": 0, "filiz_adet": 0, "filiz_uzunluk_m": 0.0, "filiz_kg": 0.0,
        "tevzi_sira": 0, "tevzi_cubuk": 0, "tevzi_ham_boy_m": 0.0, "tevzi_k": 0,
        "tevzi_boy_m": 0.0, "tevzi_uzunluk_m": 0.0, "tevzi_kg": 0.0, "toplam_kg": 0.0,
        "cap_kg": {}, "hata": "",
    }
    p = sbh_parametre_tamamla(parametre)
    try:
        L = float(uzunluk_m)
        y = float(yukseklik_cm)
        hata = sbh_parametre_dogrula(p)
    except (TypeError, ValueError, KeyError) as e:
        sonuc["hata"] = f"Parametre sayı değil: {e}"
        return sonuc
    if hata:
        sonuc["hata"] = hata
        return sonuc
    if L <= 0 or y <= 0:
        sonuc["hata"] = "Uzunluk ve yükseklik sıfırdan büyük olmalı"
        return sonuc

    # ── Filiz (düşey, kiriş boyunca) ──
    f_cap = int(p["filiz_cap"])
    f_yuz_adet = aralikli_donati_adet_hesapla(float(p["filiz_aralik_cm"]), L)
    f_adet = f_yuz_adet * int(p["filiz_yuz"])
    f_uz = f_adet * float(p["filiz_boy_cm"]) / 100.0
    f_kg = f_uz * DEMIR_AGIRLIK_TABLOSU[f_cap]

    # ── Tevzi (yatay, kiriş boyunca uzanır) ──
    t_cap = int(p["tevzi_cap"])
    if p["tevzi_sira"]:
        sira = int(p["tevzi_sira"])
    else:
        net_y = y - 2.0 * float(p["pas_payi_cm"])
        if net_y <= 0:
            sonuc["hata"] = f"Yükseklik {y:g} cm pas paylarından (2 × {float(p['pas_payi_cm']):g}) küçük"
            return sonuc
        sira = _tavan(net_y / float(p["tevzi_aralik_cm"])) + 1
    cubuk = sira * int(p["tevzi_yuz"])
    stok = float(p["stok_boy_m"])
    bind_cm = float(p["tevzi_bindirme_cm"])
    ham = L + float(p["tevzi_ek_boy_cm"]) / 100.0
    k = tevzi_bindirme_sayisi(ham, stok, bind_cm)
    boy = ham + k * bind_cm / 100.0
    t_uz = cubuk * boy
    t_kg = t_uz * DEMIR_AGIRLIK_TABLOSU[t_cap]

    cap_kg: Dict[int, float] = {}
    cap_kg[f_cap] = cap_kg.get(f_cap, 0.0) + f_kg
    cap_kg[t_cap] = cap_kg.get(t_cap, 0.0) + t_kg
    sonuc.update({
        "filiz_yuz_adet": f_yuz_adet, "filiz_adet": f_adet,
        "filiz_uzunluk_m": round(f_uz, 3), "filiz_kg": round(f_kg, 3),
        "tevzi_sira": sira, "tevzi_cubuk": cubuk, "tevzi_ham_boy_m": round(ham, 4), "tevzi_k": k,
        "tevzi_boy_m": round(boy, 4), "tevzi_uzunluk_m": round(t_uz, 3), "tevzi_kg": round(t_kg, 3),
        "toplam_kg": round(f_kg + t_kg, 3),
        "cap_kg": {c: round(v, 3) for c, v in cap_kg.items()},
    })
    return sonuc


def temel_kirisi_kesim_parcalari(sonuc: Dict[str, Any], parametre: Optional[Dict[str, Any]] = None
                                 ) -> List[Tuple[int, float, int]]:
    """Kesim listesine gidecek parçalar [(çap, boy_cm, adet)].

    Filiz: l boyunda tek parça. Tevzi: bindirmeli çubuk boyu STOK boyuna bölünür
    (k tam stok + kalan) — kesim çekirdeği bindirme eklemediği için bindirme
    burada BİR KEZ sayılır, 12 m'yi aşan parça "standart dışı" düşmez.
    """
    if sonuc.get("hata"):
        return []
    p = sbh_parametre_tamamla(parametre)
    parcalar: List[Tuple[int, float, int]] = []
    if sonuc["filiz_adet"] > 0:
        parcalar.append((int(p["filiz_cap"]), round(float(p["filiz_boy_cm"]), 1), sonuc["filiz_adet"]))
    cubuk = sonuc["tevzi_cubuk"]
    if cubuk > 0:
        stok_cm = float(p["stok_boy_m"]) * 100.0
        k = sonuc["tevzi_k"]
        kalan_cm = round(sonuc["tevzi_boy_m"] * 100.0 - k * stok_cm, 1)
        if k:
            parcalar.append((int(p["tevzi_cap"]), round(stok_cm, 1), k * cubuk))
        if kalan_cm > 0:
            parcalar.append((int(p["tevzi_cap"]), kalan_cm, cubuk))
    return parcalar


def cap_bazli_topla(sonuclar: List[Dict[str, Any]]) -> Dict[int, float]:
    """Satır sonuçlarından çap bazlı toplam kg (hakediş çap bazlı ister)."""
    toplam: Dict[int, float] = {}
    for s in sonuclar:
        if s.get("hata"):
            continue
        for cap, kg in s["cap_kg"].items():
            toplam[cap] = toplam.get(cap, 0.0) + kg
    return {c: round(v, 3) for c, v in sorted(toplam.items())}
