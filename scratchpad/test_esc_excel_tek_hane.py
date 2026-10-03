"""Rev-166 — (1) Excel çıktılarında beton/kalıp tek ondalık BİÇİM (değer tam kalır),
(2) Temel Kirişi + Aralıklı Donatı panellerinde Esc / X koruması."""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QUANTIX_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

import openpyxl  # noqa: E402
from app.core.excel_bicim import beton_kalip_sutunlari_tek_hane, TEK_HANE_BICIMI  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"   [{detay}]" if detay else ""))


# ── 1) Saf biçim yardımcısı ──
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["PERDE BETON + KALIP METRAJI"])          # başlık metni: tek eşleşme -> tablo başlığı sayılmaz
ws.append([])
ws.append(["Kat", "Ad", "Alan (m²)", "Beton Yük. (m)", "Kalıp Yük. (m)", "Beton (m³)", "Kalıp (m²)"])
ws.append(["Zemin", "P1", 1.25, 3.0, 2.8, 3.75, 23.1])
ws.append(["", "GENEL TOPLAM", "", "", "", 3.75, 23.1])
sutun = beton_kalip_sutunlari_tek_hane(ws)
kontrol("başlık satırı bulundu; sadece Beton (m³) + Kalıp (m²) sütunları (yükseklikler hariç)", sutun == [6, 7], str(sutun))
kontrol("beton/kalıp hücreleri '#,##0.0', değer TAM (3.75)",
        ws["F4"].number_format == TEK_HANE_BICIMI and ws["F4"].value == 3.75 and ws["G5"].number_format == TEK_HANE_BICIMI)
kontrol("alan ve yükseklik sütunlarına dokunulmadı", ws["C4"].number_format == "General" and ws["D4"].number_format == "General")

# ── 2) Pencere Excel çıktıları ──
from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))
CEVAP = [QMessageBox.StandardButton.Yes]
SORULAR = []


def soru(*a, **k):
    SORULAR.append(a[2])
    return CEVAP[0]


QMessageBox.question = staticmethod(soru)
import app.ui.metraj_analiz_window as maw  # noqa: E402

maw.QTimer.singleShot = staticmethod(lambda *a, **k: None)
KLASOR = tempfile.mkdtemp()
YOL = {"p": ""}
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (YOL["p"], ""))

win = maw.MetrajAnalizWindow()
win.demir_kat_input.setText("1. Kat")
win._demir_kat_ekle()
win.bk_eleman_combo.setCurrentText("Kolon")
win.bk_fire_spin.setValue(5.0)
win.bk_adet_spin.setValue(1)
win.bk_dim1_spin.setValue(0.5)
win.bk_dim2_spin.setValue(0.5)
win.bk_dim3_spin.setValue(1.0)
win._beton_kalip_kalem_ekle()          # beton 0.25, sipariş 0.2625, kalıp 2.0
YOL["p"] = os.path.join(KLASOR, "bk.xlsx")
win._beton_kalip_excel()
ws = openpyxl.load_workbook(YOL["p"]).active
basl = [c.value for c in ws[1]]
b, s, k = basl.index("Net Beton(m3)") + 1, basl.index("Siparis(m3)") + 1, basl.index("Kalip(m2)") + 1
kontrol("Beton & Kalıp Excel: değer TAM (0.25 / sipariş 0.263 — hesapta 3 hane), biçim tek hane",
        ws.cell(2, b).value == 0.25 and ws.cell(2, s).value == 0.263
        and all(ws.cell(2, c).number_format == TEK_HANE_BICIMI for c in (b, s, k)),
        str((ws.cell(2, b).value, ws.cell(2, s).value, ws.cell(2, b).number_format)))
kontrol("Beton & Kalıp Excel TOPLAM satırı sayı + tek hane biçimi",
        isinstance(ws.cell(3, b).value, float) and ws.cell(3, b).number_format == TEK_HANE_BICIMI)

win.doseme_kayitlari = [{"ad": "D1", "brut_alan_m2": 30.0, "bosluk_alan_m2": 0, "bosluk_cevre_m": 0,
                         "serbest_kenar_m": 0, "kalinlik_cm": 15.0, "kaynak": "Elle", "handle": ""}]
YOL["p"] = os.path.join(KLASOR, "ozet.xlsx")
win._kat_ozeti_excel()
ws = openpyxl.load_workbook(YOL["p"])["Kat Özeti"]
hucreler = [c for satir in ws.iter_rows() for c in satir if isinstance(c.value, float)]
kontrol("Kat Özeti Excel: tüm beton/kalıp sayıları tek hane biçimli", hucreler
        and all(c.number_format == TEK_HANE_BICIMI for c in hucreler), str(len(hucreler)))

win.perde_doseme_otomatik_chk.setChecked(False)
win.perde_yukseklik_spin.setValue(3.0)
win.perde_doseme_spin.setValue(0.2)
win.perde_kayitlari[("1. Kat", "P1")] = {"ad": "P1", "poligon_handle": "P1", "alan_m2": 1.0, "cevre_m": 8.5,
                                          "dusulen_m": 0.0, "handleler": ["P1"], "uyari": ""}
YOL["p"] = os.path.join(KLASOR, "perde.xlsx")
win._perde_excel()
ws = openpyxl.load_workbook(YOL["p"])["Perde"]
basl_satir = next(r for r in range(1, 15) if ws.cell(r, 1).value == "Kat")
kontrol("Perde Excel: Beton/Kalıp tek hane, 'Beton Yük. (m)' yükseklik sütunu dokunulmadı",
        ws.cell(basl_satir + 1, 8).number_format == TEK_HANE_BICIMI
        and ws.cell(basl_satir + 1, 9).number_format == TEK_HANE_BICIMI
        and ws.cell(basl_satir + 1, 6).number_format != TEK_HANE_BICIMI)

from app.core.radye_rapor import radye_sayfasi_yaz  # noqa: E402
wb = openpyxl.Workbook()
bilgi = radye_sayfasi_yaz(wb.active, [{"ad": "R1", "alan_m2": 250.0, "kalinlik_cm": 60.0, "dis_cevre_m": 70.0,
                                       "bosluklar": []}], "Test", "03.10.2026")
r = bilgi["ana_satirlar"][0]
t = bilgi["toplam_satiri"]
kontrol("Radye Excel: beton (D) ve kalıp (G) formülleri tek hane biçimi, alan (B) 2 hane",
        wb.active[f"D{r}"].number_format == TEK_HANE_BICIMI and wb.active[f"G{t}"].number_format == TEK_HANE_BICIMI
        and wb.active[f"B{r}"].number_format == "0.00")

# ── 3) Esc / X koruması ──
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402


class Sahte:
    bagli = True

    def __init__(self):
        self.geri = []

    def obje_isaret_geri_al(self, h):
        self.geri.append(h)

    def aralikli_donati_isaret_geri_al(self, h):
        self.geri.append(h)


def tk_panel():
    sc = Sahte()
    p = maw.TemelKirisiDonguPaneli(sc, "cm")
    p._satirlar = [{"ad": "SBH-1", "yeni_boyanan": ["Y1", "C1"]}]
    return sc, p


for cevap, ad in ((QMessageBox.StandardButton.Yes, "Evet"), (QMessageBox.StandardButton.No, "Hayır"),
                  (QMessageBox.StandardButton.Cancel, "Vazgeç")):
    CEVAP[0] = cevap
    SORULAR.clear()
    sc, p = tk_panel()
    p.show()
    QTest.keyClick(p, Qt.Key.Key_Escape)
    sonuc = p.result()
    beklenen = {"Evet": (1, []), "Hayır": (0, ["Y1", "C1"]), "Vazgeç": (None, [])}[ad]
    acik = p.isVisible()
    kontrol(f"Temel Kirişi Esc + {ad}: soru soruldu; "
            + {"Evet": "kabul edildi (tabloya eklenecek)", "Hayır": "reddedildi + renkler geri",
               "Vazgeç": "pencere açık kaldı"}[ad],
            any("henüz tabloya EKLENMEDİ" in s for s in SORULAR)
            and (acik if ad == "Vazgeç" else (sonuc == beklenen[0] and sc.geri == beklenen[1])),
            str((sonuc, sc.geri, acik)))
    p.hide()

CEVAP[0] = QMessageBox.StandardButton.No
sc = Sahte()
p = maw.AralikliDonatiDonguPaneli(sc)
p._satirlar = [{"handle": "A1", "olcu_handle": "O1", "toplam_agirlik_kg": 1.0, "toplam_boy_m": 1.0}]
p._eklenen_handleler = {"A1"}
SORULAR.clear()
p.show()
QTest.keyClick(p, Qt.Key.Key_Escape)
kontrol("Aralıklı Donatı Esc + Hayır: soru + reddedildi + yazı ve ölçü rengi geri",
        any("henüz aktif kata EKLENMEDİ" in s for s in SORULAR) and p.result() == 0 and set(sc.geri) == {"A1", "O1"},
        str(sc.geri))
CEVAP[0] = QMessageBox.StandardButton.Yes
sc = Sahte()
p = maw.AralikliDonatiDonguPaneli(sc)
p._satirlar = [{"handle": "A1", "toplam_agirlik_kg": 1.0, "toplam_boy_m": 1.0}]
p.show()
QTest.keyClick(p, Qt.Key.Key_Escape)
kontrol("Aralıklı Donatı Esc + Evet: kabul edildi, renkler korunur", p.result() == 1 and not sc.geri)
sc = Sahte()
p = maw.AralikliDonatiDonguPaneli(sc)
SORULAR.clear()
p.show()
QTest.keyClick(p, Qt.Key.Key_Escape)
kontrol("boş panel Esc -> soru sormadan kapanır", not SORULAR and p.result() == 0)

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
