"""Rev-139 Aşama 1 — Radye Temel: saf hesap + headless form."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox, QTabWidget  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical", "question"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))

from app.core.autocad_connector import radye_hesapla  # noqa: E402
import app.ui.metraj_analiz_window as maw  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad)


# ── Saf hesap ──
h = radye_hesapla(450, 0.60, 90)
kontrol("brief: 450×0.60 -> beton 270", h["beton_m3"] == 270.0)
kontrol("brief: 90×0.60 -> kalıp 54", h["kalip_m2"] == 54.0)
kontrol("uyarı yok", h["uyari"] == "" and h["hata"] == "")
h = radye_hesapla(450, 0.60, 90, [12, 8])
kontrol("iç boşluk EKLENİR: toplam çevre 110", h["toplam_cevre_m"] == 110.0)
kontrol("iç boşluk EKLENİR: kalıp 66", h["kalip_m2"] == 66.0)
kontrol("iç boşluk betonu değiştirmez", h["beton_m3"] == 270.0)
h = radye_hesapla(450, 60, 90)
kontrol("kalınlık 60 -> cm uyarısı", "cm girilmiş" in h["uyari"])
h = radye_hesapla(450, 0.60, 0)
kontrol("dış çevre 0 -> uyarı, beton yine hesaplı", "Dış çevre" in h["uyari"] and h["beton_m3"] == 270.0)
kontrol("alan 0 -> hata", radye_hesapla(0, 0.6, 90)["hata"] != "")
kontrol("kalınlık 0 -> hata", radye_hesapla(450, 0, 90)["hata"] != "")
kontrol("negatif çevre -> hata", radye_hesapla(450, 0.6, -5)["hata"] != "")
kontrol("metin -> hata", radye_hesapla("abc", 0.6, 90)["hata"] != "")
kontrol("ondalık: 123.45×0.55", radye_hesapla(123.45, 0.55, 50)["beton_m3"] == 67.898)

# ── Form ──
win = maw.MetrajAnalizWindow()
bulundu = False
for tw in win.findChildren(QTabWidget):
    for i in range(tw.count()):
        if tw.tabText(i).strip() == "Radye Temel":
            bulundu = True
            kardes = [tw.tabText(j).strip() for j in range(tw.count())]
kontrol("Radye Temel sekmesi eklendi", bulundu)
kontrol("Temel Kirişi'nin yanında", bulundu and "Temel Kirişi" in kardes)

kontrol("başlangıç: alan/kalınlık girin", "girin" in win.radye_uyari_label.text())
win.radye_alan_spin.setValue(450)
win.radye_kalinlik_spin.setValue(60)  # Rev-157: cm
kontrol("form beton 270.00", win.radye_beton_label.text() == "270.0 m³")
kontrol("çevre yokken uyarı", "Dış çevre" in win.radye_uyari_label.text())
win.radye_dis_cevre_spin.setValue(90)
kontrol("form toplam çevre 90.00", win.radye_toplam_cevre_label.text() == "90.00 m")
kontrol("form kalıp 54.00", win.radye_kalip_label.text() == "54.0 m²")
kontrol("uyarı temizlendi", win.radye_uyari_label.text() == "")
kontrol("sonuç satırı", "270.0 m³" in win.radye_sonuc_label.text()
        and "54.0 m²" in win.radye_sonuc_label.text())
win.radye_kalinlik_spin.setValue(80)
kontrol("kalınlık değişince İKİSİ de güncellenir",
        win.radye_beton_label.text() == "360.0 m³" and win.radye_kalip_label.text() == "72.0 m²")

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
