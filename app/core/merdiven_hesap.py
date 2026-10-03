"""Plak (eğik plaklı) merdiven beton + kalıp hesabı (saf Python, PyQt/AutoCAD bağımsız).

Neyi çözüyoruz?
    Merdiven kolu ve ARA sahanlığın beton (m³) ve kalıp (m²) metrajı; girdiler
    merdiven detayında yazılı (n, rıht h, basamak a, kol eni B, plak kalınlığı t).
    Kat sahanlığı döşeme aracında sayılır — burada sayılmaz (çift sayım).

    Kol profili (yan görünüş kesit alanı):
        s = √(L² + H²)                    eğik uzunluk
        profil = s·t + L·H / (2n)         eğik plak + n adet basamak üçgeni
    Beton = B × profil; alt yüz = s × B; rıht = H × B (n·h·B); yan = taraf × profil.

Nasıl test ederiz?
    scratchpad/test_merdiven_hesap.py — brief M1..M7 (programsız).
"""

import math
from typing import Any, Dict, Optional

MERDIVEN_TIP_KOL = "Kol"
MERDIVEN_TIP_SAHANLIK = "Sahanlık"

RIHT_ARALIK_CM = (12.0, 22.0)
BASAMAK_ARALIK_CM = (22.0, 35.0)
KALINLIK_ARALIK_CM = (8.0, 30.0)
ELLE_SAPMA_ESIK = 0.25   # L/H elle girildiyse n×a / n×h'den bu oranı aşan fark -> uyarı


def _bos_kol() -> Dict[str, Any]:
    return {"tip": MERDIVEN_TIP_KOL, "L_m": 0.0, "H_m": 0.0, "s_m": 0.0, "profil_m2": 0.0,
            "beton_m3": 0.0, "alt_m2": 0.0, "riht_m2": 0.0, "yan_m2": 0.0, "kenar_m2": 0.0,
            "uyari": "", "hata": ""}


def _aralik_uyarisi(ad: str, deger: float, aralik, ek: str = "") -> Optional[str]:
    alt, ust = aralik
    if deger < alt or deger > ust:
        return f"{ad} {deger:g} cm — olağan aralık {alt:g}–{ust:g} cm{ek}"
    return None


def merdiven_kol_hesapla(n: Any, h_cm: Any, a_cm: Any, b_m: Any, t_cm: Any, yan_taraf: Any,
                         l_m: Optional[float] = None, h_kot_m: Optional[float] = None) -> Dict[str, Any]:
    """Tek merdiven kolu.

    Args:
        n: basamak (rıht) sayısı, tam sayı ≥ 1.
        h_cm, a_cm: rıht yüksekliği / basamak genişliği (CM).
        b_m: kol genişliği (METRE).
        t_cm: plağa DİK plak kalınlığı (CM).
        yan_taraf: yan kalıp taraf sayısı 0/1/2 (perdeye dayanan tarafta kalıp yok).
        l_m, h_kot_m: elle düzeltilmiş yatay izdüşüm / kot farkı (METRE); None -> n×a, n×h.

    Returns:
        dict: L_m, H_m, s_m, profil_m2, beton_m3, alt_m2, riht_m2, yan_m2, kenar_m2 (=0), uyari, hata.
    """
    sonuc = _bos_kol()
    try:
        n_f = float(n)
        h = float(h_cm)
        a = float(a_cm)
        b = float(b_m)
        t = float(t_cm)
        yan_f = float(yan_taraf)
        l_elle = None if l_m is None else float(l_m)
        h_elle = None if h_kot_m is None else float(h_kot_m)
    except (TypeError, ValueError):
        sonuc["hata"] = "Değerler sayı değil"
        return sonuc
    if n_f <= 0 or n_f != int(n_f):
        sonuc["hata"] = "Basamak sayısı (n) pozitif tam sayı olmalı"
        return sonuc
    if h <= 0 or a <= 0 or b <= 0 or t <= 0:
        sonuc["hata"] = "Rıht (h), basamak (a), kol eni (B) ve plak kalınlığı (t) sıfırdan büyük olmalı"
        return sonuc
    if yan_f not in (0.0, 1.0, 2.0):
        sonuc["hata"] = "Yan kalıp taraf sayısı 0, 1 veya 2 olmalı"
        return sonuc
    if (l_elle is not None and l_elle <= 0) or (h_elle is not None and h_elle <= 0):
        sonuc["hata"] = "Elle girilen L ve H sıfırdan büyük olmalı"
        return sonuc

    n_i = int(n_f)
    l_oto = n_i * a / 100.0
    h_oto = n_i * h / 100.0
    L = l_oto if l_elle is None else l_elle
    H = h_oto if h_elle is None else h_elle
    t_m = t / 100.0
    s = math.hypot(L, H)
    profil = s * t_m + L * H / (2.0 * n_i)

    uyarilar = []
    for u in (_aralik_uyarisi("Rıht h", h, RIHT_ARALIK_CM, " — değer cm cinsinden mi?"),
              _aralik_uyarisi("Basamak a", a, BASAMAK_ARALIK_CM, " — değer cm cinsinden mi?"),
              _aralik_uyarisi("Plak t", t, KALINLIK_ARALIK_CM)):
        if u:
            uyarilar.append(u)
    if l_elle is not None and abs(L - l_oto) > ELLE_SAPMA_ESIK * l_oto:
        uyarilar.append(f"L elle {L:.2f} m — n×a = {l_oto:.2f} m'den %{abs(L - l_oto) / l_oto * 100:.0f} farklı")
    if h_elle is not None and abs(H - h_oto) > ELLE_SAPMA_ESIK * h_oto:
        uyarilar.append(f"H elle {H:.2f} m — n×h = {h_oto:.2f} m'den %{abs(H - h_oto) / h_oto * 100:.0f} farklı")

    sonuc.update({
        "L_m": round(L, 4), "H_m": round(H, 4), "s_m": round(s, 4),
        "profil_m2": round(profil, 4),
        "beton_m3": round(b * profil, 4),
        "alt_m2": round(s * b, 4),
        "riht_m2": round(H * b, 4),
        "yan_m2": round(yan_f * profil, 4),
        "uyari": "; ".join(uyarilar),
    })
    return sonuc


def merdiven_sahanlik_hesapla(en_m: Any, boy_m: Any, t_cm: Any, serbest_kenar_m: Any = 0.0) -> Dict[str, Any]:
    """ARA sahanlık: beton = en×boy×t, alt kalıp = en×boy, kenar = serbest kenar × t."""
    sonuc = {"tip": MERDIVEN_TIP_SAHANLIK, "beton_m3": 0.0, "alt_m2": 0.0, "riht_m2": 0.0,
             "yan_m2": 0.0, "kenar_m2": 0.0, "uyari": "", "hata": ""}
    try:
        en = float(en_m)
        boy = float(boy_m)
        t = float(t_cm)
        serbest = float(serbest_kenar_m or 0.0)
    except (TypeError, ValueError):
        sonuc["hata"] = "Değerler sayı değil"
        return sonuc
    if en <= 0 or boy <= 0 or t <= 0:
        sonuc["hata"] = "En, boy ve kalınlık sıfırdan büyük olmalı"
        return sonuc
    if serbest < 0:
        sonuc["hata"] = "Serbest kenar negatif olamaz"
        return sonuc
    t_m = t / 100.0
    sonuc.update({
        "beton_m3": round(en * boy * t_m, 4),
        "alt_m2": round(en * boy, 4),
        "kenar_m2": round(serbest * t_m, 4),
        "uyari": _aralik_uyarisi("Kalınlık", t, KALINLIK_ARALIK_CM) or "",
    })
    return sonuc


def merdiven_toplam_kalip(sonuc: Dict[str, Any], riht_dahil: bool = True, yan_dahil: bool = True) -> float:
    """Toplam kalıp = alt yüz + kenar + (seçiliyse) rıht + (seçiliyse) yan."""
    toplam = sonuc.get("alt_m2", 0.0) + sonuc.get("kenar_m2", 0.0)
    if riht_dahil:
        toplam += sonuc.get("riht_m2", 0.0)
    if yan_dahil:
        toplam += sonuc.get("yan_m2", 0.0)
    return round(toplam, 4)


def kalip_esas_metni(riht_dahil: bool, yan_dahil: bool) -> str:
    """Rapor/tablo başlığı: "Kalıp: alt yüz + rıht + yan" gibi."""
    parcalar = ["alt yüz"]
    if riht_dahil:
        parcalar.append("rıht")
    if yan_dahil:
        parcalar.append("yan")
    return "Kalıp: " + " + ".join(parcalar) + " (+ sahanlık kenarı)"
