"""Rev-144 Aşama 1 — Döşeme (plak) beton/kalıp: PROGRAMSIZ saf hesap testi.

Çalıştırma: python scratchpad/test_doseme_hesap.py  (Qt/AutoCAD gerekmez)
"""
import sys

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from app.core.autocad_connector import doseme_hesapla  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"   [{detay}]" if detay else ""))


def ozet(h):
    return (f"net {h['net_alan_m2']:.2f} m², beton {h['beton_m3']:.2f} m³, alt {h['alt_kalip_m2']:.2f}, "
            f"kenar {h['kenar_kalip_m2']:.2f}, toplam kalıp {h['toplam_kalip_m2']:.2f} m²")


h = doseme_hesapla(20, 15)
kontrol("T1 Basit: brüt 20, h=15 -> beton 3.00, alt 20, kenar 0, toplam 20",
        h["beton_m3"] == 3.0 and h["alt_kalip_m2"] == 20 and h["kenar_kalip_m2"] == 0
        and h["toplam_kalip_m2"] == 20 and not h["hata"] and not h["uyari"], ozet(h))

h = doseme_hesapla(20, 15, serbest_kenar_m=5)
kontrol("T2 Serbest kenar 5 -> kenar 0.75, toplam 20.75",
        h["kenar_kalip_m2"] == 0.75 and h["toplam_kalip_m2"] == 20.75, ozet(h))

h = doseme_hesapla(30, 15, bosluk_alan_m2=5, bosluk_cevre_m=9)
kontrol("T3 Boşluk 2×2.5: net 25, beton 3.75, alt 25, kenar 1.35, toplam 26.35",
        h["net_alan_m2"] == 25 and h["beton_m3"] == 3.75 and h["alt_kalip_m2"] == 25
        and h["kenar_kalip_m2"] == 1.35 and h["toplam_kalip_m2"] == 26.35, ozet(h))

h = doseme_hesapla(30, 15, bosluk_alan_m2=30)
kontrol("T4 Boşluk 30 = brüt 30 -> reddedilir", h["hata"] != "" and h["beton_m3"] == 0, h["hata"])

h = doseme_hesapla(20, 0)
kontrol("T5 h=0 -> reddedilir", h["hata"] != "" and h["beton_m3"] == 0, h["hata"])

# Ek doğrulamalar
kontrol("brüt 0 -> hata", doseme_hesapla(0, 15)["hata"] != "")
kontrol("negatif boşluk -> hata", doseme_hesapla(20, 15, bosluk_alan_m2=-1)["hata"] != "")
kontrol("negatif serbest kenar -> hata", doseme_hesapla(20, 15, serbest_kenar_m=-1)["hata"] != "")
kontrol("metin -> hata", doseme_hesapla("abc", 15)["hata"] != "")
h = doseme_hesapla(20, 0.15)
kontrol("h=0.15 (metre girilmiş) -> hesaplanır ama UYARI", "cm girdiğinizden" in h["uyari"]
        and h["beton_m3"] == 0.03, h["uyari"])
kontrol("h=60 -> uyarı", doseme_hesapla(20, 60)["uyari"] != "")
kontrol("h=5 ve h=50 sınırda -> uyarı yok",
        doseme_hesapla(20, 5)["uyari"] == "" and doseme_hesapla(20, 50)["uyari"] == "")
h = doseme_hesapla(30, 15, 5, 9, 5)
kontrol("boşluk + serbest kenar birlikte: kenar (5+9)×0.15 = 2.10", h["kenar_kalip_m2"] == 2.1, ozet(h))

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
