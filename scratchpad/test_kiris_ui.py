"""Rev-150 Aşama 1 — Kiriş sekmesi: headless form + tablo testi."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox, QTabWidget  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
MESAJ = []
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, _ad=ad, **k: MESAJ.append((_ad, a[2]))))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

import app.ui.metraj_analiz_window as maw  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"  [{detay}]" if detay else ""))


win = maw.MetrajAnalizWindow()
kardes, tip_ipucu = [], ""
for tw in win.findChildren(QTabWidget):
    for i in range(tw.count()):
        if tw.tabText(i).strip() == "Kiriş":
            kardes = [tw.tabText(j).strip() for j in range(tw.count())]
            tip_ipucu = tw.tabToolTip(i)
kontrol("Kiriş sekmesi Döşeme'nin yanında", "Döşeme" in kardes
        and kardes.index("Kiriş") == kardes.index("Döşeme") + 1, kardes)
kontrol("sekme ipucu kendi sekmesinde (L_net)", "L_net" in tip_ipucu)
kontrol("tablo 12 sütun, L1/L2 başlıkları", win.kiris_table.columnCount() == 12
        and (win.kiris_table.horizontalHeaderItem(4).text(), win.kiris_table.horizontalHeaderItem(5).text())
        == ("L1 (m)", "L2 (m)"))
TIP, T, BET, KAL, KAY = 6, 7, 8, 9, 10
kontrol("varsayılan t 12 -> satır t 12", win.kiris_t_spin.value() == 12.0)
win.kiris_varsayilan_t_spin.setValue(15)
kontrol("varsayılan t değişince satır t izler", win.kiris_t_spin.value() == 15.0)
win.kiris_varsayilan_t_spin.setValue(12)


def ekle(b, h, l_m, tip="İç", t=None, ad=""):
    win.kiris_ad_edit.setText(ad)
    win.kiris_b_spin.setValue(b)
    win.kiris_h_spin.setValue(h)
    win.kiris_l_spin.setValue(l_m)
    win.kiris_tip_combo.setCurrentText(tip)
    if t is not None:
        win.kiris_t_spin.setValue(t)
    win._kiris_elle_ekle()


def hucre(r, c):
    return win.kiris_table.item(r, c).text()


ekle(25, 50, 4, ad="K101")               # T1
ekle(25, 50, 4, "Kenar")                 # T2
ekle(25, 50, 4, t=0)                     # T3
n_once = len(win.kiris_kayitlari)
ekle(25, 12, 4, t=12)                    # T4
kontrol("T4 h≤t eklenmedi + uyarı", len(win.kiris_kayitlari) == n_once
        and MESAJ and MESAJ[-1][0] == "warning" and "döşeme kalınlığından" in MESAJ[-1][1])
ekle(60, 30, 3)                          # T5
kontrol("T5 yassı bilgi notu gösterildi", "Yassı" in win.kiris_uyari_label.text())

kontrol("4 satır", win.kiris_table.rowCount() == 4)
kontrol("T1 ad K101, L1=L2=4.00, beton 0.500, kalıp 4.04",
        (hucre(0, 1), hucre(0, 4), hucre(0, 5), hucre(0, BET), hucre(0, KAL))
        == ("K101", "4.00", "4.00", "0.5", "4.0"))
kontrol("T2 otomatik ad K1, kenar kalıp 4.52", (hucre(1, 1), hucre(1, TIP), hucre(1, KAL)) == ("K1", "Kenar", "4.5"))
kontrol("T3 döşemesiz 5.00", hucre(2, KAL) == "5.0" and hucre(2, T) == "0")
kontrol("T5 0.540 / 2.88", (hucre(3, BET), hucre(3, KAL)) == ("0.5", "2.9"))
kontrol("kaynak Elle", hucre(0, KAY) == "Elle")
kontrol("toplam: L 15.00, beton 2.040, kalıp 16.44",
        all(x in win.kiris_toplam_label.text() for x in ("15.00", "2.0", "16.4")),
        win.kiris_toplam_label.text())

# Satırda tip değiştir: T1 -> Kenar
win.kiris_table.item(0, maw.MetrajAnalizWindow.KIRIS_TIP_KOL).setText("k")
kontrol("tip 'k' -> Kenar, kalıp 4.52", (hucre(0, TIP), hucre(0, KAL)) == ("Kenar", "4.5"))
win.kiris_table.item(0, maw.MetrajAnalizWindow.KIRIS_TIP_KOL).setText("İç")
kontrol("tip 'İç' geri, kalıp 4.04", (hucre(0, TIP), hucre(0, KAL)) == ("İç", "4.0"))
win.kiris_table.item(0, maw.MetrajAnalizWindow.KIRIS_TIP_KOL).setText("ters")
kontrol("geçersiz tip reddedildi", hucre(0, TIP) == "İç" and "eski değer" in win.kiris_uyari_label.text())
# Satırda t değiştir
win.kiris_table.item(0, maw.MetrajAnalizWindow.KIRIS_T_KOL).setText("0")
kontrol("t=0 -> kalıp 5.00", hucre(0, KAL) == "5.0")
win.kiris_table.item(0, maw.MetrajAnalizWindow.KIRIS_T_KOL).setText("60")
kontrol("t=60 (≥h) reddedildi", hucre(0, T) == "0" and "eski değer" in win.kiris_uyari_label.text())
win.kiris_table.item(0, maw.MetrajAnalizWindow.KIRIS_T_KOL).setText("12,0")
kontrol("t '12,0' virgül kabul", hucre(0, T) == "12" and hucre(0, KAL) == "4.0")
kontrol("beton hücresi düzenlenemez",
        not (win.kiris_table.item(0, BET).flags() & maw.Qt.ItemFlag.ItemIsEditable))

ekle(25, 50, 16)
kontrol("L=16 uyarı ama eklendi", len(win.kiris_kayitlari) == 5 and "15 m" in win.kiris_uyari_label.text())

win.kiris_table.selectRow(4)
win._kiris_sil()
kontrol("seçili sil", len(win.kiris_kayitlari) == 4)
win._kiris_temizle()
kontrol("temizle", win.kiris_table.rowCount() == 0 and "0 kiriş" in win.kiris_toplam_label.text())

print(f"\n{GECEN} PASS / {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
