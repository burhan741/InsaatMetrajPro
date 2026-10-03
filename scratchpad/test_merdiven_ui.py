"""Rev-152 — Merdiven sekmesi: headless form + tablo + kalıcı ayar + kat özeti."""
import json
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
GECICI = tempfile.mkdtemp()
os.environ["QUANTIX_DATA_DIR"] = GECICI          # gerçek ayar dosyası kirlenmesin
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
W = maw.MetrajAnalizWindow
kardes = []
for tw in win.findChildren(QTabWidget):
    adlar = [tw.tabText(j).strip() for j in range(tw.count())]
    if "Merdiven" in adlar:
        kardes = adlar
kontrol("Merdiven sekmesi Kiriş ile Kat Özeti arasında",
        kardes and kardes.index("Merdiven") == kardes.index("Kiriş") + 1
        and kardes.index("Kat Özeti") == kardes.index("Merdiven") + 1, kardes)
kontrol("tablo 19 sütun", win.merdiven_table.columnCount() == 19)
kontrol("onay kutuları varsayılan işaretli",
        win.merdiven_riht_check.isChecked() and win.merdiven_yan_check.isChecked())

win.demir_kat_input.setText("1. Kat")
win._demir_kat_ekle()


def kol(n=10, h=15, a=30, b=1.20, t=15, yan="2", L=None, H=None, ad=""):
    win.merdiven_kol_ad_edit.setText(ad)
    win.merdiven_lh_elle_check.setChecked(L is not None or H is not None)
    win.merdiven_n_spin.setValue(n)
    win.merdiven_h_spin.setValue(h)
    win.merdiven_a_spin.setValue(a)
    win.merdiven_b_spin.setValue(b)
    win.merdiven_t_spin.setValue(t)
    win.merdiven_yan_combo.setCurrentText(yan)
    if L is not None:
        win.merdiven_l_spin.setValue(L)
    if H is not None:
        win.merdiven_hkot_spin.setValue(H)
    win._merdiven_kol_ekle()


def hucre(r, c):
    return win.merdiven_table.item(r, c).text()


BET, ALT, RIHT, YAN, KEN, TOP = 13, 14, 15, 16, 17, 18
win.merdiven_n_spin.setValue(10)
win.merdiven_h_spin.setValue(15)
win.merdiven_a_spin.setValue(30)
kontrol("L/H otomatik n×a, n×h", (win.merdiven_l_spin.value(), win.merdiven_hkot_spin.value()) == (3.0, 1.5)
        and not win.merdiven_l_spin.isEnabled())
kol()                                          # M1
kontrol("M1 satırı: L 3.00 H 1.50 s 3.354", (hucre(0, 6), hucre(0, 7), hucre(0, 8)) == ("3.00", "1.50", "3.354"))
kontrol("M1 beton 0.874, alt 4.025, rıht 1.800, yan 1.456, toplam 7.281",
        (hucre(0, BET), hucre(0, ALT), hucre(0, RIHT), hucre(0, YAN), hucre(0, TOP))
        == ("0.9", "4.0", "1.8", "1.5", "7.3"))
kontrol("otomatik ad Kol-1, tip Kol", (hucre(0, 2), hucre(0, 1)) == ("Kol-1", "Kol"))
kontrol("kol satırında Boy/Kenar boş", hucre(0, 10) == "" and hucre(0, KEN) == "")
kol(yan="0")                                   # M2
kontrol("M2 yansız toplam 5.825", hucre(1, TOP) == "5.8", hucre(1, TOP))

# M4 sahanlık
win.merdiven_sah_en_spin.setValue(1.20)
win.merdiven_sah_boy_spin.setValue(2.50)
win.merdiven_sah_t_spin.setValue(15)
win.merdiven_sah_serbest_spin.setValue(2.50)
win._merdiven_sahanlik_ekle()
kontrol("M4 sahanlık 0.450 / alt 3.000 / kenar 0.375 / toplam 3.375",
        (hucre(2, BET), hucre(2, ALT), hucre(2, KEN), hucre(2, TOP)) == ("0.5", "3.0", "0.4", "3.4"))
kontrol("sahanlık satırında n/rıht/yan boş", hucre(2, 3) == "" and hucre(2, RIHT) == "" and hucre(2, YAN) == "")

# M3 onay kutuları + kalıcı ayar
win.merdiven_riht_check.setChecked(False)
win.merdiven_yan_check.setChecked(False)
kontrol("M3 rıht+yan kapalı -> M1 toplam 4.025 (sütunlar görünür kalır)",
        hucre(0, TOP) == "4.0" and hucre(0, RIHT) == "1.8")
kontrol("başlık esası 'Kalıp: alt yüz' ", win.merdiven_esas_label.text().startswith("Kalıp: alt yüz (")
        and "rıht" not in win.merdiven_esas_label.text(), win.merdiven_esas_label.text())
with open(os.path.join(GECICI, "autocad_ayarlari.json"), encoding="utf-8") as f:
    kayit = json.load(f).get("merdiven_kalip_esasi")
kontrol("seçim ayar dosyasına yazıldı", kayit == {"riht": False, "yan": False}, kayit)
win2 = maw.MetrajAnalizWindow()
kontrol("yeni pencere kayıtlı seçimi yükledi",
        not win2.merdiven_riht_check.isChecked() and not win2.merdiven_yan_check.isChecked())
win.merdiven_riht_check.setChecked(True)
win.merdiven_yan_check.setChecked(True)

# M5 L elle
kol(L=2.70, H=1.50)
kontrol("M5 L elle: s 3.089 beton 0.799", (hucre(3, 8), hucre(3, BET)) == ("3.089", "0.8"),
        (hucre(3, 8), hucre(3, BET)))
kontrol("M5 %10 fark uyarı yok", "L elle" not in win.merdiven_uyari_label.text())
kol(L=2.0, H=1.5)
kontrol("L %33 fark -> uyarı ama eklendi", "L elle" in win.merdiven_uyari_label.text()
        and win.merdiven_table.rowCount() == 5)
win.merdiven_table.selectRow(4)
win._merdiven_sil()
kontrol("seçili sil", win.merdiven_table.rowCount() == 4)

# M6 hatalı
n_once = len(win.merdiven_kayitlari)
kol(n=0)
kontrol("M6 n=0 reddedildi + uyarı penceresi", len(win.merdiven_kayitlari) == n_once
        and MESAJ and MESAJ[-1][0] == "warning")
# M7 uyarı
kol(h=165)
kontrol("M7 h=165 eklendi + 'cm cinsinden' uyarısı", "cm cinsinden" in win.merdiven_uyari_label.text()
        and len(win.merdiven_kayitlari) == n_once + 1)
win.merdiven_table.selectRow(win.merdiven_table.rowCount() - 1)
win._merdiven_sil()

# Hücre düzenleme
win.merdiven_table.item(0, W.MERDIVEN_YAN_KOL).setText("1")
kontrol("yan 2->1: yan kalıp 0.728", hucre(0, YAN) == "0.7", hucre(0, YAN))
win.merdiven_table.item(0, W.MERDIVEN_YAN_KOL).setText("3")
kontrol("yan=3 reddedildi", hucre(0, 12) == "1" and "eski değer" in win.merdiven_uyari_label.text())
win.merdiven_table.item(0, W.MERDIVEN_T_KOL).setText("20")
kontrol("t 15->20: beton arttı", float(hucre(0, BET)) > 0.874)
win.merdiven_table.item(0, W.MERDIVEN_T_KOL).setText("15")
win.merdiven_table.item(0, W.MERDIVEN_YAN_KOL).setText("2")
kontrol("geri alınca M1 değerleri", (hucre(0, BET), hucre(0, TOP)) == ("0.9", "7.3"))
kontrol("beton hücresi düzenlenemez",
        not (win.merdiven_table.item(0, BET).flags() & maw.Qt.ItemFlag.ItemIsEditable))
kontrol("sahanlıkta yan taraf hücresi düzenlenemez",
        not (win.merdiven_table.item(2, W.MERDIVEN_YAN_KOL).flags() & maw.Qt.ItemFlag.ItemIsEditable))

# Kat özeti: Merdiven satırı
oz = win._kat_ozeti_hesapla()
m = [e for k in oz["katlar"] if k["kat"] == "1. Kat" for e in k["elemanlar"] if e["eleman"] == "Merdiven"]
beklenen_b = round(0.8737 + 0.8737 + 0.45 + 0.799, 3)
kontrol("özette 1. Kat Merdiven: 4 satır", m and m[0]["adet"] == 4.0, m)
kontrol("özet beton = tablo toplamı", m and abs(m[0]["beton_m3"] - beklenen_b) < 0.002, (m, beklenen_b))
kontrol("toplam etiketinde esas + kat", win.merdiven_toplam_label.text().startswith("1. Kat")
        and "Kalıp: alt yüz + rıht + yan" in win.merdiven_toplam_label.text())

# Kat bazlı
win.demir_kat_input.setText("2. Kat")
win._demir_kat_ekle()
kontrol("2. Kat'ta merdiven tablosu boş", win.merdiven_table.rowCount() == 0
        and win.merdiven_kat_edit.text() == "2. Kat")
win._merdiven_temizle()
win.demir_kat_listesi.setCurrentRow(0)
win._demir_kat_secildi(None)
kontrol("1. Kat'a dönünce 4 satır", win.merdiven_table.rowCount() == 4)

print(f"\n{GECEN} PASS / {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
