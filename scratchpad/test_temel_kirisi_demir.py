"""Rev-153 — SBH demir hesabı, brief S1..S5c + kesim parçaları (programsız)."""
import sys

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")
from app.core.temel_kirisi_demir import (  # noqa: E402
    temel_kirisi_demir_hesapla, temel_kirisi_kesim_parcalari, cap_bazli_topla, VARSAYILAN_SBH_DEMIR,
)
from app.core.autocad_connector import aralikli_donati_adet_hesapla  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"  [{detay}]" if detay else ""))


def yakin(a, b, tol=0.06):
    return abs(a - b) <= tol


def goster(ad, d):
    print(f"{ad}: filiz {d['filiz_yuz_adet']}×2={d['filiz_adet']} adet, {d['filiz_uzunluk_m']} m, "
          f"{d['filiz_kg']} kg | tevzi sıra {d['tevzi_sira']} → {d['tevzi_cubuk']} çubuk, k={d['tevzi_k']}, "
          f"boy {d['tevzi_boy_m']} m, {d['tevzi_uzunluk_m']} m, {d['tevzi_kg']} kg | toplam {d['toplam_kg']} kg")


s1 = temel_kirisi_demir_hesapla(10.00, 165)
goster("S1", s1)
kontrol("S1 filiz 51×2=102 adet, 285.6 m, 253.6 kg",
        (s1["filiz_yuz_adet"], s1["filiz_adet"], s1["filiz_uzunluk_m"]) == (51, 102, 285.6)
        and yakin(s1["filiz_kg"], 253.6))
kontrol("S1 tevzi 9×2=18 çubuk, boy 10.00, 180.0 m, 111.1 kg",
        (s1["tevzi_sira"], s1["tevzi_cubuk"], s1["tevzi_k"], s1["tevzi_boy_m"], s1["tevzi_uzunluk_m"])
        == (9, 18, 0, 10.0, 180.0) and yakin(s1["tevzi_kg"], 111.1))
kontrol("S1 çap bazlı Ø12 253.6 / Ø10 111.1", yakin(s1["cap_kg"][12], 253.6) and yakin(s1["cap_kg"][10], 111.1))

s2 = temel_kirisi_demir_hesapla(10.00, 165, {"tevzi_sira": 9})
kontrol("S2 sıra elle 9 -> S1 ile aynı", {k: s2[k] for k in s2 if k != "cap_kg"} == {k: s1[k] for k in s1 if k != "cap_kg"})

s3 = temel_kirisi_demir_hesapla(10.10, 165)
kontrol("S3 L=10.10 -> filiz yüz başına 52", s3["filiz_yuz_adet"] == 52)
kontrol("S3 aralıklı donatı kuralıyla aynı", s3["filiz_yuz_adet"] == aralikli_donati_adet_hesapla(20, 10.10))

s4 = temel_kirisi_demir_hesapla(10.00, 165, {"tevzi_ek_boy_cm": 80})
goster("S4", s4)
kontrol("S4 ek boy 80 -> boy 10.80, 194.4 m, 119.9 kg",
        (s4["tevzi_boy_m"], s4["tevzi_uzunluk_m"]) == (10.8, 194.4) and yakin(s4["tevzi_kg"], 119.9))

s5 = temel_kirisi_demir_hesapla(14.00, 165)
goster("S5", s5)
kontrol("S5 L=14 -> k=1, boy 14.50, 261.0 m, 161.0 kg",
        (s5["tevzi_k"], s5["tevzi_boy_m"], s5["tevzi_uzunluk_m"]) == (1, 14.5, 261.0) and yakin(s5["tevzi_kg"], 161.0))
s5b = temel_kirisi_demir_hesapla(25.00, 165)
goster("S5b", s5b)
kontrol("S5b L=25 -> k=2, boy 26.00, 468.0 m, 288.8 kg",
        (s5b["tevzi_k"], s5b["tevzi_boy_m"], s5b["tevzi_uzunluk_m"]) == (2, 26.0, 468.0)
        and yakin(s5b["tevzi_kg"], 288.8))
s5c = temel_kirisi_demir_hesapla(12.00, 165)
kontrol("S5c L=12 -> k=0, boy 12.00", (s5c["tevzi_k"], s5c["tevzi_boy_m"]) == (0, 12.0))
kontrol("S5d L=23.50 (tam 2. sınır: 12 + 11.5) -> k=1, boy 24.00",
        (lambda d: (d["tevzi_k"], d["tevzi_boy_m"]))(temel_kirisi_demir_hesapla(23.50, 165)) == (1, 24.0))

# S7 parametre değişimi: filiz boyu 260
s7 = temel_kirisi_demir_hesapla(10.00, 165, {"filiz_boy_cm": 260})
kontrol("S7 filiz boyu 260 -> 265.2 m", s7["filiz_uzunluk_m"] == 265.2 and s7["filiz_kg"] < s1["filiz_kg"])

# Hatalar
kontrol("pas payı ≥ y/2 -> hata", bool(temel_kirisi_demir_hesapla(10, 10, {"pas_payi_cm": 5})["hata"]))
kontrol("tabloda olmayan çap Ø11 -> hata", "Ø11" in temel_kirisi_demir_hesapla(10, 165, {"filiz_cap": 11})["hata"])
kontrol("bindirme ≥ stok -> hata", bool(temel_kirisi_demir_hesapla(10, 165, {"tevzi_bindirme_cm": 1200})["hata"]))
kontrol("L=0 -> hata", bool(temel_kirisi_demir_hesapla(0, 165)["hata"]))
kontrol("varsayılanlar brief tablosuyla aynı",
        VARSAYILAN_SBH_DEMIR == {"filiz_cap": 12, "filiz_aralik_cm": 20.0, "filiz_boy_cm": 280.0, "filiz_yuz": 2,
                                 "tevzi_cap": 10, "tevzi_aralik_cm": 20.0, "tevzi_sira": None, "tevzi_yuz": 2,
                                 "tevzi_ek_boy_cm": 0.0, "tevzi_bindirme_cm": 50.0, "stok_boy_m": 12.0,
                                 "pas_payi_cm": 5.0})

# Kesim parçaları: bindirme bir kez, hiçbir parça stok boyu aşmaz
p1 = temel_kirisi_kesim_parcalari(s1)
kontrol("S1 kesim: filiz 280×102, tevzi 1000×18", p1 == [(12, 280.0, 102), (10, 1000.0, 18)], p1)
p5 = temel_kirisi_kesim_parcalari(s5)
kontrol("S5 kesim: tevzi 1200×18 + 250×18 (toplam 261 m)", p5[1:] == [(10, 1200.0, 18), (10, 250.0, 18)], p5)
p5b = temel_kirisi_kesim_parcalari(s5b)
kontrol("S5b kesim: tevzi 1200×36 + 200×18 (toplam 468 m)", p5b[1:] == [(10, 1200.0, 36), (10, 200.0, 18)], p5b)
for ad, d, par in (("S1", s1, p1), ("S5", s5, p5), ("S5b", s5b, p5b)):
    tevzi_m = sum(b * a for c, b, a in par if c == 10) / 100
    kontrol(f"{ad} kesim tevzi uzunluğu = metraj ({d['tevzi_uzunluk_m']} m), parça ≤ 1200 cm",
            abs(tevzi_m - d["tevzi_uzunluk_m"]) < 0.01 and all(b <= 1200 for _, b, _ in par))

toplam = cap_bazli_topla([s1, s5, {"hata": "x"}])
kontrol("çap bazlı toplam (hatalı satır atlanır)",
        yakin(toplam[12], s1["cap_kg"][12] + s5["cap_kg"][12], 0.01) and list(toplam) == [10, 12], toplam)

print(f"\n{GECEN} PASS / {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
