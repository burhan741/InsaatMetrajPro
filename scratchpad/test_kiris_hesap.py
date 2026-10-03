"""Rev-150 Aşama 1 — kiris_hesapla programsız test (brief T1-T5 + sınırlar)."""
import sys

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")
from app.core.autocad_connector import kiris_hesapla  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"  [{detay}]" if detay else ""))


def yakin(a, b):
    return abs(a - b) < 1e-9


r = kiris_hesapla(25, 50, 4.00, "İç", 12)
kontrol("T1 iç 25/50 L4 t12 beton 0.500", yakin(r["beton_m3"], 0.5), r["beton_m3"])
kontrol("T1 kalıp 4.04 (1.00 + 2×0.38×4)", yakin(r["toplam_kalip_m2"], 4.04), r["toplam_kalip_m2"])
kontrol("T1 alt 1.00 / yan 3.04", yakin(r["alt_kalip_m2"], 1.0) and yakin(r["yan_kalip_m2"], 3.04))
kontrol("T1 not yok", not r["hata"] and not r["uyari"] and not r["bilgi"])

r = kiris_hesapla(25, 50, 4.00, "Kenar", 12)
kontrol("T2 kenar beton 0.500", yakin(r["beton_m3"], 0.5))
kontrol("T2 kalıp 4.52", yakin(r["toplam_kalip_m2"], 4.52), r["toplam_kalip_m2"])
kontrol("T2 − T1 = t×L = 0.48", yakin(r["toplam_kalip_m2"] - 4.04, 0.12 * 4))

r = kiris_hesapla(25, 50, 4.00, "İç", 0)
kontrol("T3 döşemesiz kalıp 5.00", yakin(r["toplam_kalip_m2"], 5.0), r["toplam_kalip_m2"])
r = kiris_hesapla(25, 50, 4.00, "Kenar", 0)
kontrol("T3b t=0 kenar = iç (5.00)", yakin(r["toplam_kalip_m2"], 5.0))

r = kiris_hesapla(25, 12, 4.00, "İç", 12)
kontrol("T4 h=t reddedilir", "döşeme kalınlığından" in r["hata"], r["hata"])
kontrol("T4 hata varken beton 0", r["beton_m3"] == 0.0)
r = kiris_hesapla(25, 10, 4.00, "İç", 12)
kontrol("T4b h<t reddedilir", bool(r["hata"]))

r = kiris_hesapla(60, 30, 3.00, "İç", 12)
kontrol("T5 yassı beton 0.540", yakin(r["beton_m3"], 0.54), r["beton_m3"])
kontrol("T5 kalıp 2.88", yakin(r["toplam_kalip_m2"], 2.88), r["toplam_kalip_m2"])
kontrol("T5 bilgi notu var, hata yok", "Yassı" in r["bilgi"] and not r["hata"], r["bilgi"])

for b, h, l_m in ((0, 50, 4), (25, 0, 4), (25, 50, 0), (-25, 50, 4)):
    kontrol(f"sıfır/negatif reddedilir ({b},{h},{l_m})", bool(kiris_hesapla(b, h, l_m, "İç", 12)["hata"]))
kontrol("negatif t reddedilir", bool(kiris_hesapla(25, 50, 4, "İç", -1)["hata"]))
kontrol("geçersiz tip reddedilir", bool(kiris_hesapla(25, 50, 4, "Ters", 12)["hata"]))
kontrol("sayı olmayan reddedilir", bool(kiris_hesapla("a", 50, 4)["hata"]))

r = kiris_hesapla(25, 50, 16, "İç", 12)
kontrol("L=16 m uyarı, engellemez", "15 m" in r["uyari"] and not r["hata"] and r["beton_m3"] > 0)
kontrol("L=15 m uyarı yok (sınır dahil)", not kiris_hesapla(25, 50, 15, "İç", 12)["uyari"])

# Brief v3 uzunluk testleri (25/50, t=12) — iki kenar ayrı
r = kiris_hesapla(25, 50, 4.00, "İç", 12, 4.00)
kontrol("U1 iç düz 4/4 -> 0.500 / 4.04", yakin(r["beton_m3"], 0.5) and yakin(r["toplam_kalip_m2"], 4.04))
r = kiris_hesapla(25, 50, 1.00, "İç", 12, 1.50)
kontrol("U2 iç yamuk 1/1.5 -> beton 0.156", f"{r['beton_m3']:.3f}" == "0.156", r["beton_m3"])
kontrol("U2 kalıp 0.3125 + 0.38 + 0.57 = 1.2625",
        yakin(r["alt_kalip_m2"], 0.3125) and yakin(r["toplam_kalip_m2"], 1.2625), r["toplam_kalip_m2"])
r = kiris_hesapla(25, 50, 1.00, "Kenar", 12, 1.50)
kontrol("U3 kenar yamuk -> 0.3125 + 0.38 + 0.75 = 1.4425", yakin(r["toplam_kalip_m2"], 1.4425), r["toplam_kalip_m2"])
r2 = kiris_hesapla(25, 50, 1.50, "Kenar", 12, 1.00)
kontrol("L1/L2 sırası ters verilse de uzun kenar dış yüz", yakin(r2["toplam_kalip_m2"], 1.4425)
        and (r2["l1_m"], r2["l2_m"]) == (1.0, 1.5))
kontrol("L2=0 reddedilir", bool(kiris_hesapla(25, 50, 1.0, "İç", 12, 0)["hata"]))

print(f"\n{GECEN} PASS / {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
