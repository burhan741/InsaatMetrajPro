"""AŞAMA 2 testi — başlık tespiti + sütun->alan eşleme + çap normalizasyonu.

Sadece SAF fonksiyonları test eder (cap_normalize_et, _baslik_normalize,
_baslik_satirini_bul, grid_den_poz_kayitlarini_cikar) — AutoCAD bağımsız.
Aşama 1'in tablo_hucrelerini_kumele() çıktısı (grid) üzerinde çalışır.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.autocad_connector import (
    tablo_hucrelerini_kumele,
    cap_normalize_et,
    _baslik_normalize,
    grid_den_poz_kayitlarini_cikar,
)


# ─────────────────────────────────────────────────────────────────────────
# cap_normalize_et
# ─────────────────────────────────────────────────────────────────────────

def test_cap_normalize_sembol_varyasyonlari():
    assert cap_normalize_et("18") == 18
    assert cap_normalize_et("Ø18") == 18
    assert cap_normalize_et("ø18") == 18
    assert cap_normalize_et("φ18") == 18  # phi
    assert cap_normalize_et("Q18") == 18
    assert cap_normalize_et("D18") == 18
    assert cap_normalize_et("ø 18 mm") == 18
    assert cap_normalize_et("Ø8") == 8
    print("PASS: cap normalize sembol varyasyonlari dogru")


def test_cap_normalize_sayisiz_metin():
    assert cap_normalize_et("-") is None
    assert cap_normalize_et("") is None
    assert cap_normalize_et(None) is None
    assert cap_normalize_et("ABC") is None
    print("PASS: sayisiz metin None donuyor")


# ─────────────────────────────────────────────────────────────────────────
# _baslik_normalize
# ─────────────────────────────────────────────────────────────────────────

def test_baslik_normalize():
    assert _baslik_normalize("ÇAP(mm)") == "CAP"
    assert _baslik_normalize("Boy (m)") == "BOY"
    assert _baslik_normalize("Poz No") == "POZNO"
    assert _baslik_normalize("ADET") == "ADET"
    assert _baslik_normalize("ŞEKİL") == "SEKIL"
    assert _baslik_normalize("") == ""
    print("PASS: baslik normalize dogru (turkce karakter + parantez temizligi)")


# ─────────────────────────────────────────────────────────────────────────
# Sentetik tablo — ekran goruntusundeki 7 satirlik tabloya benzer
# ─────────────────────────────────────────────────────────────────────────

def _jit(i, genlik=0.04):
    return ((i * 37) % 7 - 3) * genlik


def _ornek_grid(baslikli=True):
    """POZ|ADET|CAP(mm)|BOY(m)|SEKIL|O8|O12|O18 sutunlu, 7 veri satirli grid.
    baslikli=False ise baslik satiri hic eklenmez (manuel sutun_sirasi testi icin)."""
    kolon_x = {"POZ": 0.0, "ADET": 100.0, "CAP": 200.0, "BOY": 300.0,
               "SEKIL": 400.0, "O8": 650.0, "O12": 750.0, "O18": 850.0}
    baslik_metni = {"POZ": "POZ", "ADET": "ADET", "CAP": "ÇAP(mm)", "BOY": "BOY(m)",
                    "SEKIL": "ŞEKİL", "O8": "Ø8", "O12": "Ø12", "O18": "Ø18"}
    satirlar_veri = [
        (1, 20, 18, "5,30", {"O18": "106,00"}),
        (2, 16, 12, "5,25", {"O12": "84,00"}),
        (3, 20, 12, "4,40", {"O12": "88,00"}),
        (4, 38, 18, "4,40", {"O18": "167,20"}),
        (5, 14, 12, "2,90", {"O12": "40,60"}),
        (6, 12, 12, "2,90", {"O12": "34,80"}),
        (7, 24, 12, "2,90", {"O12": "69,60"}),
    ]

    hucreler = []
    i = 0

    def ekle(text, x, y):
        nonlocal i
        hucreler.append({"text": text, "x": x + _jit(i), "y": y + _jit(i + 1)})
        i += 1

    y = 700.0
    if baslikli:
        for kolon, x in kolon_x.items():
            ekle(baslik_metni[kolon], x, y)
        y -= 60.0

    for poz, adet, cap, boy, toplamlar in satirlar_veri:
        ekle(str(poz), kolon_x["POZ"], y)
        ekle(str(adet), kolon_x["ADET"], y)
        ekle(str(cap), kolon_x["CAP"], y)
        ekle(boy, kolon_x["BOY"], y)
        for kolon_adi, deger in toplamlar.items():
            ekle(deger, kolon_x[kolon_adi], y)
        y -= 60.0

    return tablo_hucrelerini_kumele(hucreler)


def test_otomatik_baslik_tespiti_ve_kayitlar():
    grid = _ornek_grid(baslikli=True)
    sonuc = grid_den_poz_kayitlarini_cikar(grid)

    assert sonuc["sutun_tespiti"] == "otomatik", sonuc["sutun_tespiti"]
    assert sonuc["baslik_satir_index"] == 0

    alanlar = set(sonuc["sutun_alan_haritasi"].values())
    assert {"poz", "adet", "cap", "boy", "sekil"}.issubset(alanlar), alanlar

    assert len(sonuc["basarili"]) == 7, f"7 poz beklenirdi, {len(sonuc['basarili'])} geldi"

    poz1 = sonuc["basarili"][0]
    assert poz1["poz_no"] == "1"
    assert poz1["adet"] == 20
    assert poz1["cap"] == 18
    assert abs(poz1["boy"] - 5.30) < 1e-9
    assert poz1["tablo_toplamlari"] == {18: 106.0}, poz1["tablo_toplamlari"]

    poz2 = sonuc["basarili"][1]
    assert poz2["adet"] == 16 and poz2["cap"] == 12
    assert poz2["tablo_toplamlari"] == {12: 84.0}, poz2["tablo_toplamlari"]

    print(f"PASS: otomatik baslik tespiti + 7 poz kaydi dogru "
          f"(sutun haritasi: {sonuc['sutun_alan_haritasi']})")


def test_toplam_kolon_cap_haritasi_dogru():
    grid = _ornek_grid(baslikli=True)
    sonuc = grid_den_poz_kayitlarini_cikar(grid)

    # O8 sutunu hicbir satirda dolu degil (bu ornekte) -> cap None (bos sutun)
    # O12 sutunu satir 2,3,5,6,7'de dolu, hepsi cap=12 -> 12
    # O18 sutunu satir 1,4'te dolu, hepsi cap=18 -> 18
    cap_harita = sonuc["toplam_kolon_cap_haritasi"]
    degerler = list(cap_harita.values())
    assert 12 in degerler and 18 in degerler, cap_harita
    assert sonuc["belirsiz_toplam_kolonlari"] == []
    print(f"PASS: toplam kolon cap haritasi dogru: {cap_harita}")


def test_manuel_sutun_sirasi_baslik_yokken():
    grid = _ornek_grid(baslikli=False)
    # NOT: baslikli=False oldugunda SEKIL(x=400) ve O8(x=650) sutunlarinda
    # HICBIR veri satirinda hucre yok (bu ornek verisinde), bu yuzden
    # tablo_hucrelerini_kumele onlari ayri birer sutun olarak ACMAZ - grid
    # sadece FIILEN kullanilan 6 sutunu icerir: POZ,ADET,CAP,BOY,O12,O18.
    sutun_sayisi = len(grid[0])
    assert sutun_sayisi == 6, f"bu ornekte 6 sutun beklenirdi, {sutun_sayisi} geldi"
    sutun_sirasi = ["poz", "adet", "cap", "boy", "toplam", "toplam"]
    sonuc = grid_den_poz_kayitlarini_cikar(grid, sutun_sirasi=sutun_sirasi)

    assert sonuc["sutun_tespiti"] == "manuel", sonuc["sutun_tespiti"]
    assert sonuc["baslik_satir_index"] is None
    assert len(sonuc["basarili"]) == 7, f"7 poz beklenirdi, {len(sonuc['basarili'])} geldi"
    poz1 = sonuc["basarili"][0]
    assert poz1["adet"] == 20 and poz1["cap"] == 18
    assert poz1["tablo_toplamlari"] == {18: 106.0}
    print("PASS: basliksiz tabloda manuel sutun_sirasi ile ayni sonuc")


def test_baslik_da_sutun_sirasi_da_yoksa_basarisiz_ama_crash_yok():
    grid = _ornek_grid(baslikli=False)
    sonuc = grid_den_poz_kayitlarini_cikar(grid)  # sutun_sirasi verilmedi
    assert sonuc["sutun_tespiti"] == "basarisiz"
    assert sonuc["basarili"] == []
    print("PASS: baslik yok + sutun_sirasi yok -> temiz 'basarisiz' (crash yok)")


def test_bos_grid():
    sonuc = grid_den_poz_kayitlarini_cikar([])
    assert sonuc["sutun_tespiti"] == "basarisiz"
    assert sonuc["basarili"] == []
    print("PASS: bos grid crash etmiyor")


def test_belirsiz_toplam_kolonu_tespit_ediliyor():
    """Bir 'toplam' sutunu, FARKLI caplardaki satirlarda dolu ise (veri
    girisi hatasi ya da sutun kaymasi belirtisi) 'belirsiz' olarak
    isaretlenmeli — sessizce yanlis capa atanmamali."""
    kolon_x = {"POZ": 0.0, "ADET": 100.0, "CAP": 200.0, "BOY": 300.0, "KARISIK": 650.0}
    baslik_metni = {"POZ": "POZ", "ADET": "ADET", "CAP": "ÇAP", "BOY": "BOY", "KARISIK": "TOPLAM"}
    hucreler = []
    i = 0

    def ekle(text, x, y):
        nonlocal i
        hucreler.append({"text": text, "x": x + _jit(i), "y": y + _jit(i + 1)})
        i += 1

    y = 100.0
    for kolon, x in kolon_x.items():
        ekle(baslik_metni[kolon], x, y)
    y -= 60.0
    # Satir 1: cap=12, KARISIK dolu (50,00)
    for kolon, deger in [("POZ", "1"), ("ADET", "10"), ("CAP", "12"), ("BOY", "5,00"), ("KARISIK", "50,00")]:
        ekle(deger, kolon_x[kolon], y)
    y -= 60.0
    # Satir 2: cap=16 (FARKLI), KARISIK yine dolu -> ayni sutun iki farkli capla eslesiyor
    for kolon, deger in [("POZ", "2"), ("ADET", "8"), ("CAP", "16"), ("BOY", "3,00"), ("KARISIK", "24,00")]:
        ekle(deger, kolon_x[kolon], y)

    grid = tablo_hucrelerini_kumele(hucreler)
    sonuc = grid_den_poz_kayitlarini_cikar(grid)

    assert sonuc["sutun_tespiti"] == "otomatik"
    assert len(sonuc["belirsiz_toplam_kolonlari"]) == 1, sonuc["belirsiz_toplam_kolonlari"]
    karisik_col = sonuc["belirsiz_toplam_kolonlari"][0]
    assert sonuc["toplam_kolon_cap_haritasi"][karisik_col] is None
    print("PASS: karma capli toplam sutunu 'belirsiz' olarak isaretlendi (sessizce yanlis atanmadi)")


if __name__ == "__main__":
    testler = [
        test_cap_normalize_sembol_varyasyonlari,
        test_cap_normalize_sayisiz_metin,
        test_baslik_normalize,
        test_otomatik_baslik_tespiti_ve_kayitlar,
        test_toplam_kolon_cap_haritasi_dogru,
        test_manuel_sutun_sirasi_baslik_yokken,
        test_baslik_da_sutun_sirasi_da_yoksa_basarisiz_ama_crash_yok,
        test_bos_grid,
        test_belirsiz_toplam_kolonu_tespit_ediliyor,
    ]
    for t in testler:
        t()
    print(f"\nTUM TESTLER PASS ({len(testler)}/{len(testler)})")
