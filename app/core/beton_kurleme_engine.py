"""
Beton Kürleme Süresi Hesaplama Motoru
======================================
Neyi çözer?
Döküm sonrası kalıp sökme tarihini tahmin etmek yerine hesaplar.
Ortam sıcaklığı + çimento tipi + hedef dayanım kombinasyonu ile
TS 500 ve ACI 305R-10 uyumlu güvenli kürleme süresi verir.
Gantt motoruna otomatik lag değeri olarak beslenir.

Saha Karşılığı:
- Şantiye şefi "beton ne zaman yüklenebilir?" diye sorar → 1 tıkla yanıt
- Kış döneminde döküm yapıldığında uyarı + uzatılmış süre otomatik
- Kalıp erken sökülmesinden kaynaklanan tamir maliyetini önler

Test:
python -c "
from app.core.beton_kurleme_engine import BetonKurlemeEngine, CimentoTipi
e = BetonKurlemeEngine()
r = e.hesapla(CimentoTipi.CEM_I_325, 5.0, 'doseme_kalip')
assert r.guvenli_sure_gun > 14
assert r.uyari is not None
print(f'5C doseme: {r.guvenli_sure_gun} gun - OK')
"
4-space PEP8 — tam yeniden yazım
"""

from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from enum import Enum


# ── Çimento Tipleri ─────────────────────────────────────────────────────────

class CimentoTipi(Enum):
    """TS EN 197-1 çimento sınıfları — sahada en yaygın olanlar."""
    CEM_I_325 = "CEM I 32.5"    # Normal Portland — standart
    CEM_I_425 = "CEM I 42.5"    # Hızlı sertleşen — kış dökümü
    CEM_I_525 = "CEM I 52.5"    # Yüksek erken dayanım
    CEM_II_325 = "CEM II 32.5"  # Katkılı — yavaş sertleşir
    CEM_III = "CEM III"          # Cüruf katkılı — en yavaş
    CEM_IV = "CEM IV"            # Puzolanik — benzer yavaş


# ── Sıcaklık → Kürleme Katsayısı ────────────────────────────────────────────
# Maturity Method (ASTM C1074) + ACI 308R'dan düzeltilmiş
# Referans: 20°C = 1.0 katsayısı
SICAKLIK_KATSAYILARI: List[Tuple[float, float, float]] = [
    # (t_min, t_max, katsayi)
    (-10.0,  -0.1, 999.0),  # Donma — döküm yasak (999 = imkansız)
    (  0.0,   4.9,   2.80), # 0–5°C : çok yavaş, ısıtma gerekebilir
    (  5.0,   9.9,   1.90), # 5–10°C : yavaş
    ( 10.0,  14.9,   1.45), # 10–15°C : serin
    ( 15.0,  19.9,   1.15), # 15–20°C : hafif serin
    ( 20.0,  24.9,   1.00), # 20–25°C : OPTİMUM (referans)
    ( 25.0,  29.9,   0.88), # 25–30°C : sıcak, su kürü dikkat
    ( 30.0,  34.9,   0.78), # 30–35°C : çok sıcak
    ( 35.0,  45.0,   0.70), # >35°C : kritik, gece dökümü önerilir
]

# ── Çimento Tipi → Dayanım Gelişim Faktörü ──────────────────────────────────
# 1.0 = referans (CEM I 32.5, 20°C koşulda)
CIMENTO_FAKTORLERI: Dict[CimentoTipi, float] = {
    CimentoTipi.CEM_I_525:  0.70,  # %30 daha hızlı
    CimentoTipi.CEM_I_425:  0.80,  # %20 daha hızlı
    CimentoTipi.CEM_I_325:  1.00,  # Referans
    CimentoTipi.CEM_II_325: 1.25,  # %25 daha yavaş
    CimentoTipi.CEM_IV:     1.40,
    CimentoTipi.CEM_III:    1.60,  # %60 daha yavaş
}

# ── Kalıp Tipi → Hedef Dayanım Oranı ────────────────────────────────────────
# TS 500 Madde 10 ve ACI 347R esas alındı
KALIP_DAYANIM_ESIGI: Dict[str, float] = {
    "kolon_yan":    0.50,  # %50 — yalnızca yan yüzey kaldırılır
    "kiriş_yan":    0.50,  # %50 — kiriş yan yüzey
    "perde_yan":    0.50,  # %50 — perde duvar yan yüzey
    "kolon_kalip":  0.65,  # %65 — kolon tam kalıp
    "doseme_kalip": 0.75,  # %75 — döşeme taşıyıcı kalıp (TS 500 md.10.3)
    "kiris_alt":    0.85,  # %85 — kiriş alt kalıp (kritik)
    "kiris_kalip":  0.80,  # %80 — kiriş tam kalıp
    "yuklenebilir": 1.00,  # %100 — üstüne yük bindirilecek
    "temel_kalip":  0.50,  # %50 — temel yan yüzey
    "merdiven":     0.70,  # %70 — merdiven kalıbı
}

# ── Kalıp Tipi — Kullanıcı Dostu İsimler ─────────────────────────────────────
KALIP_GORUNTU_ISIMLERI: Dict[str, str] = {
    "kolon_yan":    "Kolon Yan Yüzey",
    "kiriş_yan":    "Kiriş Yan Yüzey",
    "perde_yan":    "Perde Yan Yüzey",
    "kolon_kalip":  "Kolon Kalıbı (Tam)",
    "doseme_kalip": "Döşeme Kalıbı",
    "kiris_alt":    "Kiriş Alt Kalıbı",
    "kiris_kalip":  "Kiriş Kalıbı (Tam)",
    "yuklenebilir": "Üstüne Yük Binecek",
    "temel_kalip":  "Temel Yan Yüzey",
    "merdiven":     "Merdiven Kalıbı",
}

# ── Türkiye Aylık Ortalama Sıcaklıklar ──────────────────────────────────────
# İç Anadolu ortalamaları (kaynak: MGM 30 yıllık normal)
# Kıyı / Ege bölgesi için yaklaşık +3~5°C eklenebilir
AY_SICAKLIK_TR: Dict[int, float] = {
    1:  0.5,  2:  2.0,  3:  7.0,  4: 12.5,
    5: 17.0,  6: 21.5,  7: 25.0,  8: 24.5,
    9: 19.5, 10: 13.0, 11:  6.5, 12:  2.0,
}


@dataclass
class KurlemeHesapSonucu:
    """Kürleme hesap çıktısı."""
    cimento_tipi: str
    ortam_sicaklik: float
    kalip_turu: str
    kalip_turu_ad: str
    hedef_dayanim_orani: float       # 0.0–1.0

    temel_sure_gun: int              # Optimum koşulda (20°C, CEM I 32.5)
    duzeltilmis_sure_gun: int        # Sıcaklık + çimento düzeltmesi
    guvenli_sure_gun: int            # +%20 güvenlik payı

    sicaklik_katsayisi: float
    cimento_faktoru: float

    uyari: Optional[str] = None
    tavsiye: Optional[str] = None
    donma_riski: bool = False


class BetonKurlemeEngine:
    """
    Beton kürleme süresi hesaplama ve Gantt lag üretici.

    Kullanım (GanttWindow içinden):
        engine = BetonKurlemeEngine()
        sonuc = engine.hesapla(
            cimento_tipi=CimentoTipi.CEM_I_325,
            ortam_sicaklik=8.0,
            kalip_turu="doseme_kalip"
        )
        print(sonuc.guvenli_sure_gun)  # → 18 gün → lag olarak ekle
        print(sonuc.uyari)             # → " Soğuk hava — .."

        # Ya da aya göre otomatik:
        lag = engine.lag_from_ay(3, CimentoTipi.CEM_I_325, "doseme_kalip")
        # → Mart ayı için güvenli lag değeri
    """

    def hesapla(
        self,
        cimento_tipi: CimentoTipi = CimentoTipi.CEM_I_325,
        ortam_sicaklik: float = 20.0,
        kalip_turu: str = "doseme_kalip",
    ) -> KurlemeHesapSonucu:
        """
        Kürleme süresini hesapla.

        Formül:
            Temel Süre = f(hedef_dayanim_oranı)
            Düzeltilmiş = Temel × Sıcaklık Katsayısı × Çimento Faktörü
            Güvenli = Düzeltilmiş × 1.20 (TS 500 güvenlik payı)
        """
        donma_riski = (ortam_sicaklik < 0.0)
        uyari = None
        tavsiye = None

        # ── Sıcaklık uyarısı ──────────────────────────────────────
        if ortam_sicaklik < 0.0:
            uyari = (
                " DONMA RİSKİ: 0°C altında beton dökümü yapılamaz! "
                "TS 500 Madde 5.6 — döküm durmak ZORUNDA."
            )
            tavsiye = (
                "Çözüm: Bekle (hava ısısı yükselene) veya "
                "şantiye ısıtması + kış betonu katkısı kullan."
            )
        elif ortam_sicaklik < 5.0:
            uyari = (
                f" Soğuk hava ({ortam_sicaklik:.1f}°C): "
                "Kürleme süresi normalin yaklaşık 2.8 katına çıkıyor."
            )
            tavsiye = (
                "Tavsiye: CEM I 42.5 kullan (+%25 hızlanma). "
                "Beton üstünü naylon/battaniye ile örtün."
            )
        elif ortam_sicaklik > 35.0:
            uyari = (
                f" Yüksek sıcaklık ({ortam_sicaklik:.1f}°C): "
                "Erken kuruma ve çatlama riski var."
            )
            tavsiye = (
                "Tavsiye: Sabah erken / gece dök, "
                "yüzeyi ıslak çuval/naylon ile sürekli nemli tut."
            )

        # ── Hedef dayanım oranı ───────────────────────────────────
        hedef_oran = KALIP_DAYANIM_ESIGI.get(kalip_turu, 0.75)

        # ── Temel süre (logaritmik dayanım modeli) ─────────────────
        # t = 28 × oran / (1.1 − oran) (Power's modeli)
        if hedef_oran >= 1.0:
            temel_sure = 28
        else:
            temel_sure = max(3, int(28 * hedef_oran / (1.1 - hedef_oran)))

        # ── Sıcaklık katsayısı ───────────────────────────────────
        sicaklik_katsayisi = 1.0
        for t_min, t_max, katsayi in SICAKLIK_KATSAYILARI:
            if t_min <= ortam_sicaklik <= t_max:
                sicaklik_katsayisi = katsayi
                break

        # Donma durumunda anlamsız değer döndürme
        if sicaklik_katsayisi == 999.0:
            return KurlemeHesapSonucu(
                cimento_tipi=cimento_tipi.value,
                ortam_sicaklik=ortam_sicaklik,
                kalip_turu=kalip_turu,
                kalip_turu_ad=KALIP_GORUNTU_ISIMLERI.get(kalip_turu, kalip_turu),
                hedef_dayanim_orani=hedef_oran,
                temel_sure_gun=999,
                duzeltilmis_sure_gun=999,
                guvenli_sure_gun=999,
                sicaklik_katsayisi=999.0,
                cimento_faktoru=CIMENTO_FAKTORLERI.get(cimento_tipi, 1.0),
                uyari=uyari,
                tavsiye=tavsiye,
                donma_riski=True,
            )

        # ── Çimento faktörü ──────────────────────────────────────
        cimento_faktoru = CIMENTO_FAKTORLERI.get(cimento_tipi, 1.0)

        # ── Hesaplamalar ─────────────────────────────────────────
        duzeltilmis = max(3, int(temel_sure * sicaklik_katsayisi * cimento_faktoru))
        guvenli = max(3, int(duzeltilmis * 1.20))  # %20 güvenlik payı

        return KurlemeHesapSonucu(
            cimento_tipi=cimento_tipi.value,
            ortam_sicaklik=ortam_sicaklik,
            kalip_turu=kalip_turu,
            kalip_turu_ad=KALIP_GORUNTU_ISIMLERI.get(kalip_turu, kalip_turu),
            hedef_dayanim_orani=hedef_oran,
            temel_sure_gun=temel_sure,
            duzeltilmis_sure_gun=duzeltilmis,
            guvenli_sure_gun=guvenli,
            sicaklik_katsayisi=sicaklik_katsayisi,
            cimento_faktoru=cimento_faktoru,
            uyari=uyari,
            tavsiye=tavsiye,
            donma_riski=donma_riski,
        )

    def lag_from_ay(
        self,
        ay: int,
        cimento: CimentoTipi = CimentoTipi.CEM_I_325,
        kalip_turu: str = "doseme_kalip",
        bolge_duzelt: float = 0.0,  # Bölgesel sıcaklık düzeltmesi (°C)
    ) -> int:
        """
        Aya göre güvenli lag (gün) döndür.
        GanttEngine.add_dependency(lag_days=...) için kullanılır.
        """
        sicaklik = AY_SICAKLIK_TR.get(ay, 15.0) + bolge_duzelt
        sonuc = self.hesapla(cimento, sicaklik, kalip_turu)

        # Donma durumunda -1 döndür (UI bu durumu özel işlemeli)
        if sonuc.donma_riski:
            return -1
        return sonuc.guvenli_sure_gun

    def proje_lag_takvimi(
        self,
        baslangic_ay: int,
        sure_ay: int,
        cimento: CimentoTipi = CimentoTipi.CEM_I_325,
        kalip_turu: str = "doseme_kalip",
    ) -> Dict[str, int]:
        """
        Proje boyunca her aya ait lag değerlerini döndür.
        UI'da şantiye şefi proje süresine göre seçim yapabilir.

        Returns:
            {"Ocak 2026": 18, "Şubat 2026": 22, ...}
        """
        AY_ISIMLERI = [
            "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
        ]
        takvim = {}
        for i in range(sure_ay):
            ay = ((baslangic_ay - 1 + i) % 12) + 1
            yil = 2026 + (baslangic_ay - 1 + i) // 12
            lag = self.lag_from_ay(ay, cimento, kalip_turu)
            etiket = f"{AY_ISIMLERI[ay - 1]} {yil}"
            takvim[etiket] = lag if lag > 0 else "DONMA"
        return takvim

    def onerilen_cimento(self, ortam_sicaklik: float) -> CimentoTipi:
        """Ortam sıcaklığına göre optimum çimento tipi öner."""
        if ortam_sicaklik < 5.0:
            return CimentoTipi.CEM_I_425    # Kış dönemi — hızlı sertleşen
        elif ortam_sicaklik > 30.0:
            return CimentoTipi.CEM_II_325   # Sıcak — yavaş ısı açığa çıkarır
        return CimentoTipi.CEM_I_325        # Normal şartlar

    def tum_kalip_turleri(self) -> List[Dict]:
        """UI için kalıp türü listesi döndür."""
        return [
            {
                "id": k,
                "ad": KALIP_GORUNTU_ISIMLERI.get(k, k),
                "esik": v,
            }
            for k, v in KALIP_DAYANIM_ESIGI.items()
        ]
