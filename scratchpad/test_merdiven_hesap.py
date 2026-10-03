"""Rev-152 — Merdiven hesap çekirdeği, brief M1..M7 (programsız)."""
import sys

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")
from app.core.merdiven_hesap import (  # noqa: E402
    merdiven_kol_hesapla, merdiven_sahanlik_hesapla, merdiven_toplam_kalip, kalip_esas_metni,
)

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"  [{detay}]" if detay else ""))


def yakin(a, b, tol=0.0006):
    return abs(a - b) <= tol


m1 = merdiven_kol_hesapla(10, 15, 30, 1.20, 15, 2)
print("M1:", {k: m1[k] for k in ("L_m", "H_m", "s_m", "profil_m2", "beton_m3", "alt_m2", "riht_m2", "yan_m2")})
kontrol("M1 L=3.00 H=1.50", (m1["L_m"], m1["H_m"]) == (3.0, 1.5))
kontrol("M1 s=3.354", yakin(m1["s_m"], 3.354))
kontrol("M1 profil=0.728", yakin(m1["profil_m2"], 0.728))
kontrol("M1 beton=0.874", yakin(m1["beton_m3"], 0.874))
kontrol("M1 alt=4.025 rıht=1.800 yan=1.456",
        yakin(m1["alt_m2"], 4.025) and yakin(m1["riht_m2"], 1.8) and yakin(m1["yan_m2"], 1.456))
kontrol("M1 toplam kalıp=7.281", yakin(merdiven_toplam_kalip(m1), 7.281))
kontrol("M1 uyarı yok (olağan değerler)", m1["uyari"] == "" and m1["hata"] == "", m1["uyari"])

m2 = merdiven_kol_hesapla(10, 15, 30, 1.20, 15, 0)
kontrol("M2 yansız: beton 0.874, toplam 5.825",
        yakin(m2["beton_m3"], 0.874) and yakin(merdiven_toplam_kalip(m2), 5.825), merdiven_toplam_kalip(m2))

kontrol("M3 rıht+yan kapalı: 4.025", yakin(merdiven_toplam_kalip(m1, False, False), 4.025))
kontrol("M3 sadece rıht kapalı: 5.481", yakin(merdiven_toplam_kalip(m1, False, True), 5.481))
kontrol("esas metni", kalip_esas_metni(True, False).startswith("Kalıp: alt yüz + rıht")
        and "yan" not in kalip_esas_metni(True, False).split("(")[0])

m4 = merdiven_sahanlik_hesapla(1.20, 2.50, 15, 2.50)
print("M4:", {k: m4[k] for k in ("beton_m3", "alt_m2", "kenar_m2")}, "toplam", merdiven_toplam_kalip(m4))
kontrol("M4 beton=0.450 alt=3.000 kenar=0.375",
        yakin(m4["beton_m3"], 0.45) and yakin(m4["alt_m2"], 3.0) and yakin(m4["kenar_m2"], 0.375))
kontrol("M4 toplam 3.375 (onay kutularından etkilenmez)",
        yakin(merdiven_toplam_kalip(m4), 3.375) and yakin(merdiven_toplam_kalip(m4, False, False), 3.375))

m5 = merdiven_kol_hesapla(10, 15, 30, 1.20, 15, 2, l_m=2.70)
print("M5:", {k: m5[k] for k in ("L_m", "s_m", "profil_m2", "beton_m3")}, m5["uyari"])
kontrol("M5 s=3.089 profil=0.666 beton=0.799",
        yakin(m5["s_m"], 3.089) and yakin(m5["profil_m2"], 0.666) and yakin(m5["beton_m3"], 0.799))
kontrol("M5 %10 fark -> L uyarısı YOK", "L elle" not in m5["uyari"])
m5b = merdiven_kol_hesapla(10, 15, 30, 1.20, 15, 2, l_m=2.0)
kontrol("M5b %33 fark -> L uyarısı", "L elle" in m5b["uyari"] and m5b["hata"] == "", m5b["uyari"])

m6 = merdiven_kol_hesapla(0, 15, 30, 1.20, 15, 2)
kontrol("M6 n=0 reddedildi", bool(m6["hata"]) and m6["beton_m3"] == 0, m6["hata"])
kontrol("M6b n=2.5 reddedildi", bool(merdiven_kol_hesapla(2.5, 15, 30, 1.2, 15, 2)["hata"]))
kontrol("M6c yan=3 reddedildi", "0, 1 veya 2" in merdiven_kol_hesapla(10, 15, 30, 1.2, 15, 3)["hata"])
kontrol("M6d B=0 reddedildi", bool(merdiven_kol_hesapla(10, 15, 30, 0, 15, 2)["hata"]))
kontrol("M6e sahanlık en=0 reddedildi", bool(merdiven_sahanlik_hesapla(0, 2.5, 15)["hata"]))
kontrol("M6f metin girdi reddedildi", bool(merdiven_kol_hesapla("on", 15, 30, 1.2, 15, 2)["hata"]))

m7 = merdiven_kol_hesapla(10, 165, 30, 1.20, 15, 2)
kontrol("M7 h=165 uyarı + hesap engellenmedi",
        "cm cinsinden" in m7["uyari"] and m7["hata"] == "" and m7["beton_m3"] > 0, m7["uyari"])
kontrol("M7b a=300 uyarı", "Basamak" in merdiven_kol_hesapla(10, 15, 300, 1.2, 15, 2)["uyari"])
kontrol("M7c t=40 uyarı", "Plak t" in merdiven_kol_hesapla(10, 15, 30, 1.2, 40, 2)["uyari"])

print(f"\n{GECEN} PASS / {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
