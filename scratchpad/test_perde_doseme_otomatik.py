"""Rev-163 — Perde kalıbında döşeme kalınlığı OTOMATİK (Döşeme sekmesinden), beton aynı.

1) Programsız: hakim_doseme_kalinligi_cm (en büyük alanlı kalınlık, eşitlikte ince)
2) Pencere: döşeme yokken varsayılan kalınlık; döşeme eklenince hakim kalınlık; beton (tam kat)
   değişmez, kalıp net; kolon aracından gelen perde + Kat Özeti de güncellenir; elle moda dönüş
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QUANTIX_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from app.core.autocad_connector import hakim_doseme_kalinligi_cm  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"   [{detay}]" if detay else ""))


def d(t, a):
    return {"kalinlik_cm": t, "brut_alan_m2": a}


kontrol("hakim: 15 cm 120 m² + 12 cm 30 m² -> 15", hakim_doseme_kalinligi_cm([d(15, 100), d(12, 30), d(15, 20)]) == 15)
kontrol("hakim: eşit alanda İNCE (15/20, 50+50) -> 15", hakim_doseme_kalinligi_cm([d(20, 50), d(15, 50)]) == 15)
kontrol("hakim: kayıt yok -> None", hakim_doseme_kalinligi_cm([]) is None)
kontrol("hakim: 0 / geçersiz kalınlık yok sayılır", hakim_doseme_kalinligi_cm([d(0, 500), d("x", 9), d(18, 1)]) == 18)

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
import app.ui.metraj_analiz_window as maw  # noqa: E402

maw.QTimer.singleShot = staticmethod(lambda *a, **k: None)

win = maw.MetrajAnalizWindow()
kontrol("otomatik varsayılan AÇIK, döşeme kutusu salt (pasif)",
        win.perde_doseme_otomatik_chk.isChecked() and not win.perde_doseme_spin.isEnabled())
win.demir_kat_input.setText("1. Kat")
win._demir_kat_ekle()
win.perde_yukseklik_spin.setValue(3.0)
win.doseme_varsayilan_h_spin.setValue(15.0)
kontrol("döşeme yokken varsayılan 15 cm -> 0.15 m, kaynak yazısı",
        win.perde_doseme_spin.value() == 0.15 and "henüz döşeme yok" in win.perde_doseme_kaynak_label.text(),
        win.perde_doseme_kaynak_label.text())

# Perde (Perde sekmesi kaydı): alan 1.0 m², çevre 8.5 m
win.perde_kayitlari[("1. Kat", "P1")] = {"ad": "P1", "poligon_handle": "P1", "alan_m2": 1.0, "cevre_m": 8.5,
                                          "dusulen_m": 0.0, "handleler": ["P1"], "uyari": ""}
# Kolon aracından gelen perde S259 (210/30)
win.beton_kalip_kolon_kayitlari[("1. Kat", "S259")] = {"en_m": 2.1, "boy_m": 0.3, "en_cm": 210, "boy_cm": 30,
                                                       "kat_yuk_m": 3.0, "beton": 0, "kalip": 0, "tip": "Perde"}
win._perde_ayar_degisti()


def ozet():
    return {(k["eleman"], k["beton_m3"], round(k["kalip_m2"], 4)) for k in win._kat_ozeti_kalemleri()}


kontrol("varsayılan 15 cm: P1 beton 3.00 (tam kat), kalıp 8.5×2.85 = 24.225; S259 1.89 / 4.8×2.85 = 13.68",
        ("Perde", 3.0, 24.225) in ozet() and ("Perde", 1.89, 13.68) in ozet(), str(ozet()))

# Döşeme sekmesine döşemeler eklenir: 20 cm 100 m², 12 cm 20 m² -> hakim 20 cm
win.doseme_kayitlari = [
    {"ad": "D1", "brut_alan_m2": 100.0, "bosluk_alan_m2": 0, "bosluk_cevre_m": 0, "serbest_kenar_m": 0,
     "kalinlik_cm": 20.0, "kaynak": "Elle", "handle": ""},
    {"ad": "D2", "brut_alan_m2": 20.0, "bosluk_alan_m2": 0, "bosluk_cevre_m": 0, "serbest_kenar_m": 0,
     "kalinlik_cm": 12.0, "kaynak": "Elle", "handle": ""},
]
win._doseme_tablo_yenile()
kontrol("döşeme eklenince OTOMATİK 0.20 m (hakim), kaynakta iki kalınlık belirtilir",
        win.perde_doseme_spin.value() == 0.2 and "12, 20 cm" in win.perde_doseme_kaynak_label.text(),
        win.perde_doseme_kaynak_label.text())
kontrol("BETON AYNI (3.00 / 1.89), kalıp net 2.80: P1 8.5×2.8 = 23.80, S259 4.8×2.8 = 13.44",
        ("Perde", 3.0, 23.8) in ozet() and ("Perde", 1.89, 13.44) in ozet(), str(ozet()))
t = win.perde_table
kontrol("Perde sekmesi tablosu: beton 3.00, kalıp 23.80", t.item(0, 4).text() == "3.0" and t.item(0, 5).text() == "23.8")
bt = win.beton_kalip_table
perde_kolon = [r for r in range(bt.rowCount()) if bt.item(r, 1) and bt.item(r, 1).text() == "Perde"
               and bt.item(r, 3).text() == "2.10"]
kontrol("Beton & Kalıp tablosunda kolon aracı perdesi kalıp 13.440", perde_kolon
        and bt.item(perde_kolon[0], 9).text() == "13.4")

# Döşeme kalınlığı tabloda değişince (20 -> 18) perde de güncellenir
win.doseme_kayitlari[0]["kalinlik_cm"] = 18.0
win._doseme_tablo_yenile()
kontrol("döşeme 18 cm'e düzeltilince perde kalıbı 8.5×2.82 = 23.97", ("Perde", 3.0, 23.97) in ozet(), str(ozet()))

# Başka katta döşeme yok -> o katın perdesi varsayılan 15 cm ile
win.perde_kayitlari[("2. Kat", "P2")] = {"ad": "P2", "poligon_handle": "P2", "alan_m2": 1.0, "cevre_m": 8.5,
                                          "dusulen_m": 0.0, "handleler": ["P2"], "uyari": ""}
win.kat_yukseklik_ayarlari["2. Kat"] = maw.KatYukseklikAyari(3.0, 0.0, "tam")
k2 = [k for k in win._kat_ozeti_kalemleri() if k["kat"] == "2. Kat"]
kontrol("2. Kat (döşemesiz, kayıtlı ayarda 0) -> otomatik varsayılan 15 cm: kalıp 24.225",
        k2 and round(k2[0]["kalip_m2"], 4) == 24.225, str(k2))

# Elle moda dönüş: spin açılır, elle değer kullanılır
win.perde_doseme_otomatik_chk.setChecked(False)
win.perde_doseme_spin.setValue(0.10)
kontrol("otomatik kapalı -> elle 0.10: kalıp 8.5×2.9 = 24.65, kutu düzenlenebilir",
        win.perde_doseme_spin.isEnabled() and ("Perde", 3.0, 24.65) in ozet(), str(ozet()))

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
