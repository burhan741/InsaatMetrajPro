"""Rev-165 — Beton / kalıp sonuçları tek ondalık (yarım yukarı), toplamlar TAM değerden."""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QUANTIX_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))
import app.ui.metraj_analiz_window as maw  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"   [{detay}]" if detay else ""))


t = maw.tek_hane
kontrol("yarım YUKARI: 1.25 -> 1.3, 2.25 -> 2.3, 0.75 -> 0.8 (Python format 1.2 / 2.2 verirdi)",
        (t(1.25), t(2.25), t(0.75)) == ("1.3", "2.3", "0.8"))
kontrol("26.35 -> 26.4, 13.44 -> 13.4, 0 -> 0.0", (t(26.35), t(13.44), t(0.0)) == ("26.4", "13.4", "0.0"))
kontrol("binlik ayraç: 1234.56 -> 1,234.6", t(1234.56, True) == "1,234.6")

win = maw.MetrajAnalizWindow()
win.aktif_kat_adi = "Zemin"
# 3 elle kolon: 0.5 × 0.5 × 1.0 = 0.25 m³ (ekranda 0.3) — toplam 0.75 -> 0.8 (0.9 DEĞİL)
win.bk_eleman_combo.setCurrentText("Kolon")
win.bk_fire_spin.setValue(0.0)
for _ in range(3):
    win.bk_adet_spin.setValue(1)
    win.bk_dim1_spin.setValue(0.5)
    win.bk_dim2_spin.setValue(0.5)
    win.bk_dim3_spin.setValue(1.0)
    win._beton_kalip_kalem_ekle()
tb = win.beton_kalip_table
kontrol("Beton & Kalıp hücresi tek hane: 0.25 -> '0.3'", tb.item(0, 6).text() == "0.3", tb.item(0, 6).text())
kontrol("toplam TAM değerden: 3 × 0.25 = 0.75 -> 'Net Beton: 0.8' (yuvarlanmış 0.3×3 = 0.9 DEĞİL)",
        win.bk_toplam_beton_label.text().startswith("Net Beton: 0.8"), win.bk_toplam_beton_label.text())
kontrol("hücrenin arkasında tam değer 0.25", win._bk_hucre_degeri(0, 6) == 0.25)

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
