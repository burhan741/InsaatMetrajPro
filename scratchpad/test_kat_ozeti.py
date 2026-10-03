"""Rev-151 — Kat bazlı beton + kalıp özeti: saf çekirdek + headless pencere testi."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from app.core.kat_ozeti import kat_ozeti_olustur, ozet_tablo_satirlari, KATSIZ_ETIKET  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"  [{detay}]" if detay else ""))


# ── 1) Saf çekirdek ──
kalemler = [
    {"kat": "2. Kat", "eleman": "Kiriş", "adet": 1, "beton_m3": 0.5, "kalip_m2": 4.04},
    {"kat": "1. Kat", "eleman": "Döşeme", "adet": 1, "beton_m3": 3.0, "kalip_m2": 20.0},
    {"kat": "1. Kat", "eleman": "Kolon", "adet": 1, "beton_m3": 0.75, "kalip_m2": 6.0},
    {"kat": "1. Kat", "eleman": "Kolon", "adet": 1, "beton_m3": 0.75, "kalip_m2": 6.0},
    {"kat": "Temel", "eleman": "Radye", "adet": 1, "beton_m3": 50.0, "kalip_m2": 20.0},
    {"kat": "", "eleman": "Kolon (elle)", "adet": 2, "beton_m3": 1.5, "kalip_m2": 12.0},
    {"kat": "1. Kat", "eleman": "Perde", "adet": 1, "beton_m3": 0.0, "kalip_m2": 0.0},  # boş -> atla
]
oz = kat_ozeti_olustur(kalemler, ["1. Kat", "2. Kat"])
katlar = [k["kat"] for k in oz["katlar"]]
kontrol("sıra: Temel, 1. Kat, 2. Kat, katsız en sonda", katlar == ["Temel", "1. Kat", "2. Kat", KATSIZ_ETIKET], katlar)
k1 = oz["katlar"][1]
kontrol("1. Kat: Kolon önce Döşeme sonra (eleman sırası)",
        [e["eleman"] for e in k1["elemanlar"]] == ["Kolon", "Döşeme"])
kontrol("aynı kat+eleman birleşti: 2 kolon 1.5 m³ / 12 m²",
        k1["elemanlar"][0] == {"eleman": "Kolon", "adet": 2.0, "beton_m3": 1.5, "kalip_m2": 12.0})
kontrol("sıfır kalem (Perde) atlandı", all(e["eleman"] != "Perde" for e in k1["elemanlar"]))
kontrol("1. Kat toplamı 4.5 / 32", (k1["beton_m3"], k1["kalip_m2"]) == (4.5, 32.0))
kontrol("genel toplam = kalemlerin toplamı 56.5 / 68.04", (oz["beton_m3"], oz["kalip_m2"]) == (56.5, 68.04),
        (oz["beton_m3"], oz["kalip_m2"]))
et = {e["eleman"]: e for e in oz["eleman_toplamlari"]}
kontrol("eleman toplamları: Kolon 1.5, Radye 50", et["Kolon"]["beton_m3"] == 1.5 and et["Radye"]["beton_m3"] == 50.0)
satirlar = ozet_tablo_satirlari(oz)
kontrol("tablo satırı son = GENEL TOPLAM", satirlar[-1][1] == "GENEL TOPLAM" and satirlar[-1][5] == "genel")
kontrol("her kat için KAT TOPLAMI satırı", sum(1 for s in satirlar if s[5] == "ara") == 4)
kontrol("boş girdi -> boş özet", kat_ozeti_olustur([])["katlar"] == [])
kontrol("float yuvarlama: 0.1+0.2 -> 0.3",
        kat_ozeti_olustur([{"kat": "A", "eleman": "Kiriş", "beton_m3": 0.1, "kalip_m2": 0},
                           {"kat": "A", "eleman": "Kiriş", "beton_m3": 0.2, "kalip_m2": 0}])["beton_m3"] == 0.3)

# ── 2) Headless pencere: kat bazlı kiriş/döşeme + özet ──
from PyQt6.QtWidgets import QApplication, QMessageBox, QTabWidget  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

import app.ui.metraj_analiz_window as maw  # noqa: E402

win = maw.MetrajAnalizWindow()
kardes = []
for tw in win.findChildren(QTabWidget):
    adlar = [tw.tabText(j).strip() for j in range(tw.count())]
    if "Kat Özeti" in adlar:
        kardes = adlar
kontrol("Kat Özeti sekmesi en sonda (Rev-152: Merdiven'den sonra)", kardes and kardes[-1] == "Kat Özeti", kardes)


def kat_ekle(ad):
    win.demir_kat_input.setText(ad)
    win._demir_kat_ekle()


def kiris_ekle(b, h, l_m):
    win.kiris_b_spin.setValue(b)
    win.kiris_h_spin.setValue(h)
    win.kiris_l_spin.setValue(l_m)
    win.kiris_tip_combo.setCurrentText("İç")
    win.kiris_t_spin.setValue(12)
    win._kiris_elle_ekle()


kat_ekle("1. Kat")
kontrol("aktif kat kiriş sekmesinde görünür", win.kiris_kat_edit.text() == "1. Kat" and win.kiris_kat_edit.isReadOnly())
kiris_ekle(25, 50, 4)
kiris_ekle(25, 50, 4)
kat_ekle("2. Kat")
kontrol("2. Kat'a geçince kiriş tablosu boş", win.kiris_table.rowCount() == 0, win.kiris_table.rowCount())
kiris_ekle(30, 60, 6)
win.doseme_brut_spin.setValue(20)
win.doseme_h_spin.setValue(15)
win._doseme_elle_ekle()
kontrol("2. Kat: 1 kiriş + 1 döşeme", win.kiris_table.rowCount() == 1 and win.doseme_table.rowCount() == 1)
kontrol("kiriş toplam etiketinde kat adı", win.kiris_toplam_label.text().startswith("2. Kat"))
# 1. Kat'ı seç
win.demir_kat_listesi.setCurrentRow(0)
win._demir_kat_secildi(None)
kontrol("1. Kat'a dönünce 2 kiriş, döşeme yok",
        win.kiris_table.rowCount() == 2 and win.doseme_table.rowCount() == 0)
kontrol("otomatik ad kat içinde: K1, K2", [s["ad"] for s in win.kiris_kayitlari] == ["K1", "K2"])

# Kolon registry + temel kirişi + radye
win.beton_kalip_kolon_kayitlari[("1. Kat", "S1")] = {"en_m": .5, "boy_m": .5, "kat_yuk_m": 3.0,
                                                     "beton": 0.75, "kalip": 6.0}
win.temel_kirisi_kayitlari["H1"] = {"ad": "SBH-1", "genislik_cm": 20, "yukseklik_cm": 100,
                                    "uzunluk_m": 5, "beton_m3": 1.0, "kalip_m2": 10.0}
win.radye_alan_spin.setValue(100)
win.radye_kalinlik_spin.setValue(50)
win.radye_dis_cevre_spin.setValue(40)
radye = win._radye_hesap()
win._radye_ekle()

win._kat_ozeti_yenile()
oz = win._kat_ozeti_hesapla()
kat_adlari = [k["kat"] for k in oz["katlar"]]
kontrol("özet katları: Temel, 1. Kat, 2. Kat", kat_adlari == ["Temel", "1. Kat", "2. Kat"], kat_adlari)
k = {x["kat"]: {e["eleman"]: e for e in x["elemanlar"]} for x in oz["katlar"]}
kontrol("1. Kat kiriş: 2 adet, 1.000 m³, 8.08 m²",
        (k["1. Kat"]["Kiriş"]["adet"], k["1. Kat"]["Kiriş"]["beton_m3"], k["1. Kat"]["Kiriş"]["kalip_m2"])
        == (2.0, 1.0, 8.08), k["1. Kat"]["Kiriş"])
kontrol("1. Kat kolon 0.75 / 6", k["1. Kat"]["Kolon"]["beton_m3"] == 0.75)
dos = maw.doseme_hesapla(20, 15, 0, 0, 0)
kontrol("2. Kat döşeme = sekme formülü", k["2. Kat"]["Döşeme"]["beton_m3"] == round(dos["beton_m3"], 3))
kontrol("2. Kat kiriş 30/60 L6 t12 -> 1.08 / 7.56",
        (k["2. Kat"]["Kiriş"]["beton_m3"], k["2. Kat"]["Kiriş"]["kalip_m2"]) == (1.08, 7.56))
kontrol("Temel: radye + temel kirişi",
        k["Temel"]["Radye"]["beton_m3"] == round(radye["beton_m3"], 3) and k["Temel"]["Temel Kirişi"]["beton_m3"] == 1.0)
beklenen = round(1.0 + 0.75 + dos["beton_m3"] + 1.08 + radye["beton_m3"] + 1.0, 3)
kontrol("genel beton toplamı tutarlı", oz["beton_m3"] == beklenen, (oz["beton_m3"], beklenen))
kontrol("ekran tablosu dolu, son satır GENEL TOPLAM",
        win.kat_ozeti_table.rowCount() > 0
        and win.kat_ozeti_table.item(win.kat_ozeti_table.rowCount() - 1, 1).text() == "GENEL TOPLAM")
kontrol("toplam etiketi", "GENEL TOPLAM" in win.kat_ozeti_toplam_label.text())

# Beton & Kalıp elle satırı özete (elle) ekiyle girer
win.bk_adet_spin.setValue(2)
win.bk_dim1_spin.setValue(0.5)
win.bk_dim2_spin.setValue(0.5)
win.bk_dim3_spin.setValue(3.0)
win._beton_kalip_kalem_ekle()
oz2 = win._kat_ozeti_hesapla()
elle = [e for x in oz2["katlar"] for e in x["elemanlar"] if e["eleman"].endswith("(elle)")]
kontrol("elle satır '(elle)' ekiyle 1. Kat'ta", len(elle) == 1 and elle[0]["adet"] == 2.0, elle)

# Temizle sadece aktif katı siler
win._kiris_temizle()
kontrol("1. Kat temizlendi, 2. Kat kirişi duruyor",
        win._kiris_kat_kayitlari.get("1. Kat") == [] and len(win._kiris_kat_kayitlari["2. Kat"]) == 1)

print(f"\n{GECEN} PASS / {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
