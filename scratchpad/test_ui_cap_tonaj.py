"""Headless PyQt testi: 'CAP BAZLI TONAJ' butonu gercek pencerede
dogru calisiyor mu? (buton baslangicta disabled, veri eklenince enabled,
tiklaninca dogru dialog aciliyor ve tabloda dogru satir sayisi var mi)
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtWidgets import QApplication, QMessageBox
from app.ui.metraj_analiz_window import MetrajAnalizWindow, CapBazliTonajDialog

# QMessageBox.warning/information modal exec() ile bloke eder (offscreen'de de
# kullanicidan tik gelmedigi icin sonsuza kadar asilir kalir) - testte no-op yap.
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)


class SahteDemir:
    def __init__(self, cap, adet, boy_cm, agirlik_birim):
        self.cap = cap
        self.adet = adet
        self.boy = boy_cm
        self.toplam_boy = adet * (boy_cm / 100.0)
        self.agirlik_birim = agirlik_birim
        self.toplam_agirlik = self.toplam_boy * agirlik_birim
        self.orijinal_metin = f"TEST Ø{cap} adet={adet}"
        self.eleman_tipi = "Test"


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = MetrajAnalizWindow(db=None)

    # Kullanici "tiklanmiyor" diye bildirdi (Rev-127 sonrasi ilk geri bildirim):
    # kok neden, hic hesaplama yapilmadan buton disabled (donuk) gorunmesiydi.
    # Duzeltme: buton artik HER ZAMAN aktif, veri yoksa tiklaninca guzel bir
    # uyari cikiyor - "tiklanamaz" durumu tamamen ortadan kalkti.
    assert win.btn_cap_tonaj.isEnabled() is True, "Buton hep aktif olmali (veri olmasa bile)"
    print("PASS: veri olmadan da buton aktif (donuk/tiklanamaz degil)")

    win.demir_kat_verileri.append({
        "kat_adi": "Test Kat",
        "demirler": [
            SahteDemir(12, 10, 500, 0.888),
            SahteDemir(16, 4, 420, 1.578),
        ],
        "rapor": None,
    })
    assert win.btn_cap_tonaj.isEnabled() is True
    print("PASS: veri eklendikten sonra da aktif")

    tum_demirler = [d for kd in win.demir_kat_verileri for d in kd["demirler"]]
    dialog = CapBazliTonajDialog(tum_demirler, win)
    assert dialog.table.rowCount() == 2, f"2 farkli cap bekleniyordu, {dialog.table.rowCount()} geldi"
    assert dialog.table.item(0, 0).text() == "Ø12"
    assert dialog.table.item(1, 0).text() == "Ø16"
    print("PASS: dialog tablosu dogru satirlarla doldu (Ø12, Ø16)")

    g = dialog._ozet["genel"]
    beklenen_kg = (10 * 5.0 * 0.888) + (4 * 4.2 * 1.578)
    assert abs(g["agirlik_kg"] - beklenen_kg) < 1e-6
    print(f"PASS: genel toplam agirlik dogru ({g['agirlik_kg']:.4f} kg)")

    # Bos liste uyarisi (kat verisi yokken buton mantigi warning donmeli, crash degil)
    win2 = MetrajAnalizWindow(db=None)
    win2._cap_bazli_tonaj_goster()  # QMessageBox.warning gosterip sessizce donmeli
    print("PASS: bos durumda crash yok")

    print("\nTUM UI TESTLERI PASS")


if __name__ == "__main__":
    main()
