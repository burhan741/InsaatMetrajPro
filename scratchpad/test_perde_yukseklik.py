"""Rev-143 Aşama 3 — Perde yükseklik esası + uç düşümü: PROGRAMSIZ saf hesap testi.

Çalıştırma: python scratchpad/test_perde_yukseklik.py  (Qt/AutoCAD gerekmez)
"""
import sys

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from app.core.autocad_connector import KatYukseklikAyari, perde_hesapla  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad)


# ── Kullanıcının örneği: çevre 12, düşüm 1.0, net 2.8 -> kalıp 30.8 ──
h = perde_hesapla(4.25, 12, 3.0, doseme_kalinligi_m=0.2, dusulen_m=1.0)
kontrol("örnek: net yükseklik 2.8", h["net_yukseklik_m"] == 2.8)
kontrol("örnek: kalıp çevresi 11", h["kalip_cevre_m"] == 11.0)
kontrol("örnek: kalıp (12−1)×2.8 = 30.8 m²", h["kalip_m2"] == 30.8)

# ── Beton esası: tam / net ──
kontrol("tam kat (varsayılan): beton 4.25×3.0 = 12.75", h["beton_m3"] == 12.75 and h["beton_esasi"] == "tam")
h = perde_hesapla(4.25, 12, 3.0, 0.2, "net", 1.0)
kontrol("net: beton 4.25×2.8 = 11.9", h["beton_m3"] == 11.9)
kontrol("net: kalıp esastan bağımsız 30.8", h["kalip_m2"] == 30.8)

# ── Döşeme = 0: iki esas birebir aynı, eski davranış korunur ──
t = perde_hesapla(8.5, 12, 3.0)
n = perde_hesapla(8.5, 12, 3.0, 0.0, "net")
kontrol("döşeme 0: tam = net beton 25.5", t["beton_m3"] == n["beton_m3"] == 25.5)
kontrol("döşeme 0: kalıp 36 (Aşama 1 ile aynı)", t["kalip_m2"] == n["kalip_m2"] == 36.0)

# ── Düşüm sınırları ──
kontrol("düşüm = çevre -> hata", perde_hesapla(4.25, 12, 3.0, dusulen_m=12)["hata"] != "")
kontrol("düşüm > çevre -> hata", perde_hesapla(4.25, 12, 3.0, dusulen_m=13)["hata"] != "")
kontrol("negatif düşüm -> hata", perde_hesapla(4.25, 12, 3.0, dusulen_m=-1)["hata"] != "")
kontrol("çevre 0 + düşüm -> hata", perde_hesapla(4.25, 0, 3.0, dusulen_m=1)["hata"] != "")
kontrol("eşdeğer kalınlık TAM çevreyle (düşümden etkilenmez)",
        perde_hesapla(4.25, 34.5, 3.0, dusulen_m=2)["esdeger_kalinlik_m"]
        == perde_hesapla(4.25, 34.5, 3.0)["esdeger_kalinlik_m"])

# ── Kat ayarı doğrulama ──
kontrol("döşeme >= kat -> hata", perde_hesapla(4.25, 12, 3.0, 3.0)["hata"] != "")
kontrol("negatif döşeme -> hata", perde_hesapla(4.25, 12, 3.0, -0.1)["hata"] != "")
kontrol("bilinmeyen esas -> hata", perde_hesapla(4.25, 12, 3.0, 0.2, "brut")["hata"] != "")
a = KatYukseklikAyari(3.0, 0.2, "tam")
kontrol("ayar: net 2.8, beton yüksekliği 3.0", a.net_yukseklik_m == 2.8 and a.beton_yuksekligi_m == 3.0)
kontrol("ayar: etiket esası yazar", "Tam kat" in a.esas_etiketi() and "2.80" in a.esas_etiketi())
kontrol("ayar net: beton yüksekliği 2.8", KatYukseklikAyari(3.0, 0.2, "net").beton_yuksekligi_m == 2.8)
kontrol("ayar geçerli -> boş hata", a.dogrula() == "")
kontrol("ayar kat 0 -> hata", KatYukseklikAyari(0, 0).dogrula() != "")

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
