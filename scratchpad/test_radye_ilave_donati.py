"""Rev-141 — Radye alt ilave donatısı ("Ø14/20 l=300", küçük l) aralıklı donatı aracında okunuyor mu?"""
import sys

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")
from app.core.autocad_connector import (  # noqa: E402
    aralikli_donati_ayristir, aralikli_donati_hesapla, aralikli_donati_adet_hesapla,
    DEMIR_AGIRLIK_TABLOSU,
)

GECEN = KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad)


print(f"{'Metin':<26}{'başarılı':<10}{'çap':<6}{'aralık':<8}{'boy':<8}hata")
beklenen = [
    ("Ø14/20 l=300", 14, 20, 300),
    ("Ø14/20 L=500", 14, 20, 500),
    ("Ø12/15 l=320", 12, 15, 320),
    ("Ø26/20 l=250", 26, 20, 250),
    # AutoCAD'de gerçekte gelebilecek varyasyonlar
    ("%%c14/20 l=300", 14, 20, 300),
    ("ø14/20 l = 300", 14, 20, 300),
    ("{\\fArial|b0;Ø14/20 l=300}", 14, 20, 300),
    ("Ø14/20 l=300 (alt ilave)", 14, 20, 300),
]
for metin, cap, aralik, boy in beklenen:
    r = aralikli_donati_ayristir(metin)
    print(f"{metin:<26}{str(r['basarili']):<10}{r['cap']:<6}{r['aralik_cm']:<8g}{r['boy_cm']:<8g}{r['hata']}")
    kontrol(f"{metin!r} -> Ø{cap}/{aralik} L={boy}",
            r["basarili"] and r["cap"] == cap and r["aralik_cm"] == aralik and r["boy_cm"] == boy)

kontrol("adetli eski format ('28Ø14 l=442') aralıklı SAYILMAZ",
        not aralikli_donati_ayristir("28Ø14 l=442")["basarili"])

print()
kontrol("dağılım 400 cm = 4 m, aralık 20 -> adet 21", aralikli_donati_adet_hesapla(20, 4.0) == 21)
h = aralikli_donati_hesapla(14, 20, 300, 4.0)
print(f"Ø14/20 l=300, mesafe 4 m -> adet={h['adet']}, toplam boy={h['toplam_boy_m']} m, "
      f"ağırlık={h['toplam_agirlik_kg']} kg, hata={h['hata']!r}")
kontrol("Ø14/20 l=300 @4m -> 21 adet × 3 m = 63 m", h["adet"] == 21 and h["toplam_boy_m"] == 63.0)
kontrol("ağırlık = 63 × 1.208 = 76.10 kg", abs(h["toplam_agirlik_kg"] - 63 * 1.208) < 0.05)
kontrol("Ø12/15 @4m -> 400/15=26.67 -> ceil 27 +1 = 28", aralikli_donati_adet_hesapla(15, 4.0) == 28)
h26 = aralikli_donati_hesapla(26, 20, 250, 4.0)
print(f"Ø26 tabloda: {26 in DEMIR_AGIRLIK_TABLOSU} -> ağırlık={h26['toplam_agirlik_kg']} hata={h26['hata']!r}")
kontrol("Ø26 ağırlığı hesaplanıyor (tabloda var)", h26["toplam_agirlik_kg"] > 0 and not h26["hata"])

# ── Panel: mesafe birimi teyidi (Rev-141) ──
import os  # noqa: E402
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog  # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
import app.ui.metraj_analiz_window as maw  # noqa: E402

GIRIS = []
CEVAP = []
SORULAR = []
QInputDialog.getDouble = staticmethod(lambda *a, **k: (GIRIS.pop(0), True))


def _soru(*a, **k):
    SORULAR.append(a[2] if len(a) > 2 else "")
    return CEVAP.pop(0)


QMessageBox.question = staticmethod(_soru)
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))


class SahteConn:
    def __init__(self):
        self.n = 0

    def aralikli_donati_tek_obje_sec(self):
        self.n += 1
        d = aralikli_donati_ayristir("Ø14/20 l=300")
        d["handle"] = f"H{self.n}"
        return {"durum": "basarili", "ayrisim": d}

    def aralikli_donati_isaretle(self, h):
        pass

    def aralikli_donati_isaret_geri_al(self, h):
        pass


Y, N = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
p = maw.AralikliDonatiDonguPaneli(SahteConn())
p.mod_combo.setCurrentText(p.MOD_ELLE)  # Rev-142: varsayılan artık ölçüden

GIRIS[:] = [4.0]
p._demir_sec()
kontrol("panel: 4 m -> 21 adet, soru YOK", p.sonuclar()[-1]["adet"] == 21 and not SORULAR)

GIRIS[:] = [400.0]
CEVAP[:] = [Y]
p._demir_sec()
kontrol("panel: 400 girildi -> teyit soruldu", len(SORULAR) == 1 and "4 m" in SORULAR[0])
kontrol("panel: Evet -> 4 m, 21 adet", p.sonuclar()[-1]["mesafe_m"] == 4.0 and p.sonuclar()[-1]["adet"] == 21)

GIRIS[:] = [60.0]
CEVAP[:] = [N]
p._demir_sec()
kontrol("panel: 60 m + Hayır -> 60 m kalır (301 adet)",
        p.sonuclar()[-1]["mesafe_m"] == 60.0 and p.sonuclar()[-1]["adet"] == 301)

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
