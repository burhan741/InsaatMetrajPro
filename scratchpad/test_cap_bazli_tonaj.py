"""CapBazliTonajDialog._hesapla() icin izole test.

QApplication olusturmadan sadece hesaplama mantigini (staticmethod) test eder.
Gercek DemirBilgisi sinifi yerine ayni alanlara sahip basit bir sahte sinif
kullanilir - boylece PyQt/AutoCAD bagimliligi olmadan calisir.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class SahteDemir:
    def __init__(self, cap, adet, boy_cm, agirlik_birim):
        self.cap = cap
        self.adet = adet
        self.boy = boy_cm
        self.toplam_boy = adet * (boy_cm / 100.0)
        self.agirlik_birim = agirlik_birim
        self.toplam_agirlik = self.toplam_boy * agirlik_birim


def test_bos_liste():
    from app.ui.metraj_analiz_window import CapBazliTonajDialog
    sonuc = CapBazliTonajDialog._hesapla([])
    assert sonuc["caplar"] == {}
    assert sonuc["genel"]["adet"] == 0
    assert sonuc["genel"]["boy_m"] == 0.0
    assert sonuc["genel"]["agirlik_kg"] == 0.0
    print("PASS: bos liste")


def test_tek_cap():
    from app.ui.metraj_analiz_window import CapBazliTonajDialog
    # Ø12, 0.888 kg/m, 10 adet x 500cm = 50m -> 44.4 kg
    demirler = [SahteDemir(12, 10, 500, 0.888)]
    sonuc = CapBazliTonajDialog._hesapla(demirler)
    v = sonuc["caplar"][12]
    assert v["adet"] == 10
    assert abs(v["boy_m"] - 50.0) < 1e-9
    assert abs(v["agirlik_kg"] - 44.4) < 1e-6
    assert abs(sonuc["genel"]["agirlik_kg"] - 44.4) < 1e-6
    print("PASS: tek cap")


def test_coklu_cap_toplam():
    from app.ui.metraj_analiz_window import CapBazliTonajDialog
    demirler = [
        SahteDemir(12, 10, 500, 0.888),   # 50m  -> 44.4 kg
        SahteDemir(12, 5, 300, 0.888),    # 15m  -> 13.32 kg  (ayni cap, biriktirilmeli)
        SahteDemir(16, 4, 420, 1.578),    # 16.8m -> 26.5104 kg
        SahteDemir(8, 100, 30, 0.395),    # 30m  -> 11.85 kg
    ]
    sonuc = CapBazliTonajDialog._hesapla(demirler)

    assert set(sonuc["caplar"].keys()) == {8, 12, 16}

    v12 = sonuc["caplar"][12]
    assert v12["adet"] == 15
    assert abs(v12["boy_m"] - 65.0) < 1e-9
    assert abs(v12["agirlik_kg"] - (44.4 + 13.32)) < 1e-6

    v16 = sonuc["caplar"][16]
    assert v16["adet"] == 4
    assert abs(v16["boy_m"] - 16.8) < 1e-9
    assert abs(v16["agirlik_kg"] - 26.5104) < 1e-4

    v8 = sonuc["caplar"][8]
    assert v8["adet"] == 100
    assert abs(v8["boy_m"] - 30.0) < 1e-9
    assert abs(v8["agirlik_kg"] - 11.85) < 1e-6

    genel = sonuc["genel"]
    beklenen_adet = 10 + 5 + 4 + 100
    beklenen_boy = 50.0 + 15.0 + 16.8 + 30.0
    beklenen_agirlik = 44.4 + 13.32 + 26.5104 + 11.85
    assert genel["adet"] == beklenen_adet
    assert abs(genel["boy_m"] - beklenen_boy) < 1e-6
    assert abs(genel["agirlik_kg"] - beklenen_agirlik) < 1e-4

    beklenen_ton = beklenen_agirlik / 1000
    print(f"PASS: coklu cap toplam (genel agirlik={genel['agirlik_kg']:.4f} kg = {beklenen_ton:.4f} ton)")


if __name__ == "__main__":
    test_bos_liste()
    test_tek_cap()
    test_coklu_cap_toplam()
    print("\nTUM TESTLER PASS (3/3)")
