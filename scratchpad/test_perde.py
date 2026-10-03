"""Rev-143 Aşama 1 — Perde Beton+Kalıp: saf hesap + headless form."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox, QTabWidget  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical", "question"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))

from app.core.autocad_connector import perde_hesapla  # noqa: E402
import app.ui.metraj_analiz_window as maw  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad)


# ── Saf hesap ──
h = perde_hesapla(8.5, 12, 3.0)
kontrol("brief: 8.5×3.0 -> beton 25.5", h["beton_m3"] == 25.5)
kontrol("brief: 12×3.0 -> kalıp 36", h["kalip_m2"] == 36.0)
kontrol("brief örneği tutarsız -> kalınlık uyarısı (t≈1.42)",
        "tutarsız" in h["uyari"] and h["esdeger_kalinlik_m"] == 1.417)

# Gerçekçi U perde: 0.25 kalınlık, kollar 5+7+5 = 17 m eksen
h = perde_hesapla(4.25, 34.5, 3.0)
kontrol("gerçekçi U: beton 12.75", h["beton_m3"] == 12.75)
kontrol("gerçekçi U: kalıp 103.5", h["kalip_m2"] == 103.5)
kontrol("gerçekçi U: uyarı yok", h["uyari"] == "" and h["hata"] == "")
kontrol("gerçekçi U: eşdeğer kalınlık ~0.25", 0.24 < h["esdeger_kalinlik_m"] < 0.26)

# Dikdörtgen perde 0.30×4.00: A=1.2, Ç=8.6
h = perde_hesapla(1.2, 8.6, 2.85)
kontrol("dikdörtgen 0.30×4: beton 3.42", h["beton_m3"] == 3.42)
kontrol("dikdörtgen: uyarı yok", h["uyari"] == "")

# 1/50 ölçek felaketi: 4.25/2500 = 0.0017
h = perde_hesapla(0.0017, 34.5, 3.0)
kontrol("1/50 ölçek hatası -> uyarı (alan çok küçük)", "ölçek" in h["uyari"])
kontrol("yükseklik 300 -> cm uyarısı", "cm girilmiş" in perde_hesapla(4.25, 34.5, 300)["uyari"])
h = perde_hesapla(4.25, 0, 3.0)
kontrol("çevre 0 -> uyarı, beton yine hesaplı",
        "Çevre girilmedi" in h["uyari"] and h["beton_m3"] == 12.75 and h["kalip_m2"] == 0)
kontrol("alan 0 -> hata", perde_hesapla(0, 10, 3)["hata"] != "")
kontrol("yükseklik 0 -> hata", perde_hesapla(4, 10, 0)["hata"] != "")
kontrol("negatif çevre -> hata", perde_hesapla(4, -1, 3)["hata"] != "")
kontrol("metin -> hata", perde_hesapla("abc", 10, 3)["hata"] != "")

# ── Form ──
win = maw.MetrajAnalizWindow()
win.perde_doseme_otomatik_chk.setChecked(False)  # Rev-163: bu test döşemesiz (0) formu ölçüyor
win.perde_doseme_spin.setValue(0.0)  # elle moda geçince son otomatik değer (0.15) kalır
kardes = []
tip = ""
for tw in win.findChildren(QTabWidget):
    for i in range(tw.count()):
        if tw.tabText(i).strip() == "Perde":
            kardes = [tw.tabText(j).strip() for j in range(tw.count())]
            tip = tw.tabToolTip(i)
            tk_tip = tw.tabToolTip(kardes.index("Temel Kirişi"))
            radye_tip = tw.tabToolTip(kardes.index("Radye Temel"))
kontrol("Perde sekmesi Kaba İnşaat'a eklendi", "Radye Temel" in kardes)
kontrol("Perde ipucu doğru", "Perde" in tip)
kontrol("ipucu hatası düzeldi: SBH ipucu Temel Kirişi'nde", "SBH" in tk_tip)
kontrol("ipucu hatası düzeldi: Radye ipucu Radye'de", "Radye" in radye_tip and "SBH" not in radye_tip)

kontrol("başlangıç: girin uyarısı", "girin" in win.perde_uyari_label.text())
win.perde_yukseklik_spin.setValue(3.0)
win.perde_alan_spin.setValue(8.5)
kontrol("form beton 25.500", win.perde_beton_label.text() == "25.5 m³")
win.perde_cevre_spin.setValue(12)
kontrol("form kalıp 36.000", win.perde_kalip_label.text() == "36.0 m²")
kontrol("form tutarsızlık uyarısı görünür", "tutarsız" in win.perde_uyari_label.text())
win.perde_alan_spin.setValue(4.25)
win.perde_cevre_spin.setValue(34.5)
kontrol("gerçekçi değerde uyarı temizlendi", win.perde_uyari_label.text() == "")
kontrol("eşdeğer kalınlık gösterimi", win.perde_kalinlik_label.text() == "0.25 m")
win.perde_yukseklik_spin.setValue(2.80)
kontrol("yükseklik değişince İKİSİ güncellenir",
        win.perde_beton_label.text() == "11.9 m³" and win.perde_kalip_label.text() == "96.6 m²")
kontrol("sonuç satırı tek ondalık (Rev-165)", win.perde_sonuc_label.text() == "PERDE — Beton: 11.9 m³   |   Kalıp: 96.6 m²")
kontrol("alan girişi 2 ondalık", win.perde_alan_spin.decimals() == 2)

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
