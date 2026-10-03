"""Rev-144 Aşama 1 — Döşeme sekmesi: headless form + tablo testi."""
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
from app.core.autocad_connector import KatYukseklikAyari  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad)


win = maw.MetrajAnalizWindow()
kardes = []
for tw in win.findChildren(QTabWidget):
    for i in range(tw.count()):
        if tw.tabText(i).strip() == "Döşeme":
            kardes = [tw.tabText(j).strip() for j in range(tw.count())]
            tip = tw.tabToolTip(i)
kontrol("Döşeme sekmesi Kaba İnşaat'ta, Perde'nin yanında",
        "Perde" in kardes and kardes.index("Döşeme") == kardes.index("Perde") + 1)
kontrol("sekme ipucu iç yüz kuralını söylüyor", "iç yüz" in tip)
kontrol("tablo 13 sütun (Rev-164: sonda Tip), başlıklar", win.doseme_table.columnCount() == 13
        and win.doseme_table.horizontalHeaderItem(5).text() == "Kalınlık (cm)"
        and win.doseme_table.horizontalHeaderItem(12).text() == "Tip")
kontrol("varsayılan kalınlık 15 cm -> satır kalınlığı 15", win.doseme_h_spin.value() == 15.0)


def ekle(brut, bosluk=0.0, cevre=0.0, serbest=0.0, h=None, ad=""):
    win.doseme_ad_edit.setText(ad)
    win.doseme_brut_spin.setValue(brut)
    win.doseme_bosluk_spin.setValue(bosluk)
    win.doseme_bosluk_cevre_spin.setValue(cevre)
    win.doseme_serbest_spin.setValue(serbest)
    if h is not None:
        win.doseme_h_spin.setValue(h)
    win._doseme_elle_ekle()


def hucre(r, c):
    return win.doseme_table.item(r, c).text()


ekle(20)                                  # T1
ekle(20, serbest=5)                       # T2
ekle(30, bosluk=5, cevre=9, ad="Salon")   # T3
kontrol("3 satır, otomatik adlar D1/D2 + elle 'Salon'",
        [hucre(r, 1) for r in range(3)] == ["D1", "D2", "Salon"])
kontrol("T1 satırı: beton 3.00, alt 20.00, kenar 0.00, toplam 20.00",
        [hucre(0, c) for c in (6, 7, 8, 9)] == ["3.0", "20.0", "0.0", "20.0"])
kontrol("T2 satırı: kenar 0.75, toplam 20.75", [hucre(1, c) for c in (8, 9)] == ["0.8", "20.8"])
kontrol("T3 satırı: net 25.00, beton 3.75, kenar 1.35, toplam 26.35",
        [hucre(2, c) for c in (4, 6, 8, 9)] == ["25.00", "3.8", "1.4", "26.4"])
kontrol("kaynak 'Elle', handle boş", hucre(0, 10) == "Elle" and hucre(0, 11) == "")
kontrol("toplam satırı: net 65, beton 9.75, kalıp 67.10",
        "65.00 m²" in win.doseme_toplam_label.text() and "9.8 m³" in win.doseme_toplam_label.text()
        and "67.1 m²" in win.doseme_toplam_label.text())
kontrol("ekleme sonrası form sıfırlandı", win.doseme_brut_spin.value() == 0 and win.doseme_ad_edit.text() == "")

# Reddedilenler
MESAJ.clear()
ekle(30, bosluk=30)                       # T4
kontrol("T4 boşluk = brüt -> reddedildi, satır eklenmedi",
        len(win.doseme_kayitlari) == 3 and any("küçük olmalı" in m for _, m in MESAJ))
ekle(20, h=0)                             # T5
kontrol("T5 h=0 -> reddedildi", len(win.doseme_kayitlari) == 3 and "Kalınlık" in win.doseme_uyari_label.text())
ekle(0)
kontrol("alan 0 -> reddedildi", len(win.doseme_kayitlari) == 3)

# Olağan dışı kalınlık: eklenir ama uyarır
ekle(10, h=0.2)
kontrol("h=0.2 cm -> EKLENDİ + uyarı", len(win.doseme_kayitlari) == 4
        and "cm girdiğinizden" in win.doseme_uyari_label.text())
kontrol("sonraki ekleme için kalınlık varsayılana döndü", win.doseme_h_spin.value() == 15.0)

# Satırda kalınlık düzeltme
win.doseme_table.item(3, 5).setText("20")
kontrol("satırda kalınlık 20 -> beton 10×0.20 = 2.00", hucre(3, 6) == "2.0" and hucre(3, 5) == "20")
win.doseme_table.item(3, 5).setText("abc")
kontrol("geçersiz kalınlık -> eski değer (20) korundu", hucre(3, 5) == "20"
        and "korundu" in win.doseme_uyari_label.text())
win.doseme_table.item(3, 5).setText("0")
kontrol("kalınlık 0 -> reddedildi, 20 korundu", hucre(3, 5) == "20")
win.doseme_table.item(3, 5).setText("12,5")
kontrol("virgüllü '12,5' kabul -> beton 1.25", hucre(3, 6) == "1.3")

# Varsayılan kalınlık değişince yeni satırlar
win.doseme_varsayilan_h_spin.setValue(18.0)
kontrol("varsayılan 18 -> form kalınlığı 18", win.doseme_h_spin.value() == 18.0)

# Silme + yeni ad boşluğu doldurur
win.doseme_table.selectRow(0)
win._doseme_sil()
kontrol("D1 silindi, 3 satır", len(win.doseme_kayitlari) == 3 and hucre(0, 1) == "D2")
ekle(12)
kontrol("yeni otomatik ad boşta kalan D1", win.doseme_kayitlari[-1]["ad"] == "D1")
kontrol("numaralar yeniden sıralı", [hucre(r, 0) for r in range(4)] == ["1", "2", "3", "4"])

# Perde "Net" notu
kontrol("net kat yokken not boş", win.doseme_esas_notu_label.text() == "")
win.kat_yukseklik_ayarlari["1.Kat"] = KatYukseklikAyari(3.0, 0.2, "net")
win._doseme_esas_notu_guncelle()
kontrol("perdede Net seçili kat -> kesişim notu", "1.Kat" in win.doseme_esas_notu_label.text())
win.aktif_kat_adi = "Zemin"
win._perde_aktif_kat_yukle()
win.perde_esas_combo.setCurrentIndex(win.perde_esas_combo.findData("net"))
kontrol("perde sekmesinde esas değişince not kendiliğinden güncellendi",
        "Zemin" in win.doseme_esas_notu_label.text())

# Rev-151: döşemeler kat bazlı — "Zemin" katında kayıt yok, katsız ("") katta 4 döşeme var
kontrol("Rev-151: Zemin katı listesi boş (kayıtlar katsız bölümde)", not win.doseme_kayitlari)
win.aktif_kat_adi = ""
kontrol("Rev-151: katsız bölümde 4 döşeme duruyor", len(win.doseme_kayitlari) == 4)
win._doseme_temizle()
kontrol("Temizle -> boş, toplam 0", not win.doseme_kayitlari and "DÖŞEME: 0 adet" in win.doseme_toplam_label.text())

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
