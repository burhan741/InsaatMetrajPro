"""Rev-157 — Radye kayıt listesi -> Kat Özeti (Temel grubu) + Excel "Radye" sayfası (formüllü).

Brief: 250 m², 60 cm, dış çevre 70, iç boşluklar 9 + 6 -> beton 150.00, kalıp (70+15)×0.60 = 51.00.
"""
import os
import re
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QUANTIX_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical", "question"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))
GECICI = tempfile.mkdtemp()
_dosya = {"yol": ""}
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (_dosya["yol"], "Excel (*.xlsx)"))
QInputDialog.getText = staticmethod(lambda *a, **k: ("Deneme Konut", True))

from openpyxl import load_workbook  # noqa: E402
from app.core.radye_rapor import radye_kaydi_hesapla, radye_toplamlari  # noqa: E402
import app.ui.metraj_analiz_window as maw  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + ("" if kosul else f"   -> {detay}"))


def degerlendir(ws, ref, derinlik=0):
    """Basit formül değerlendirici: =SUM(...), + - * / ve hücre referansları."""
    v = ws[ref].value
    if not (isinstance(v, str) and v.startswith("=")):
        return float(v or 0) if not isinstance(v, str) else v
    ifade = v[1:]

    def _sum(m):
        toplam = 0.0
        for parca in m.group(1).split(","):
            if ":" in parca:
                a, b = parca.split(":")
                sut, r1, r2 = a[0], int(a[1:]), int(b[1:])
                toplam += sum(degerlendir(ws, f"{sut}{r}", derinlik + 1) for r in range(r1, r2 + 1))
            else:
                toplam += degerlendir(ws, parca, derinlik + 1)
        return repr(toplam)

    ifade = re.sub(r"SUM\(([^)]*)\)", _sum, ifade)
    ifade = re.sub(r"\b([A-G])(\d+)\b", lambda m: repr(degerlendir(ws, m.group(0), derinlik + 1)), ifade)
    return eval(ifade)  # noqa: S307 - sadece test, kendi ürettiğimiz formül


BRIEF = {"ad": "Ana Blok", "alan_m2": 250, "kalinlik_cm": 60, "dis_cevre_m": 70,
         "bosluklar": [{"ad": "Asansör", "cevre_m": 9}, {"ad": "Merdiven", "cevre_m": 6}]}

# ── 1. Saf çekirdek ──
h = radye_kaydi_hesapla(BRIEF)
kontrol("brief beton 150.00", h["beton_m3"] == 150.0, h)
kontrol("brief iç boşluk toplamı 15", h["ic_cevre_m"] == 15.0, h)
kontrol("brief kalıp (70+15)×0.60 = 51.00", h["kalip_m2"] == 51.0, h)
kontrol("brief uyarı yok", h["uyari"] == "" and h["hata"] == "", h)
kontrol("0.60 girilirse (metre) uyarı", "metre girilmiş" in radye_kaydi_hesapla({**BRIEF, "kalinlik_cm": 0.6})["uyari"])
kontrol("kalınlık 0 -> hata", radye_kaydi_hesapla({**BRIEF, "kalinlik_cm": 0})["hata"] != "")
kontrol("negatif boşluk çevresi -> hata",
        radye_kaydi_hesapla({**BRIEF, "bosluklar": [{"ad": "x", "cevre_m": -1}]})["hata"] != "")
t = radye_toplamlari([BRIEF, {"ad": "R2", "alan_m2": 10, "kalinlik_cm": 50, "dis_cevre_m": 14, "bosluklar": []},
                      {"ad": "bozuk", "alan_m2": 0, "kalinlik_cm": 50, "dis_cevre_m": 1}])
kontrol("toplamlar hatalıyı atlar: 2 radye, 155 m³, 58 m²",
        (t["adet"], t["beton_m3"], t["kalip_m2"]) == (2, 155.0, 58.0), t)

# ── 2. Pencere: form -> liste -> Kat Özeti ──
win = maw.MetrajAnalizWindow()
win.temel_kirisi_kayitlari["H1"] = {"ad": "SBH-1", "genislik_cm": 20, "yukseklik_cm": 100,
                                    "uzunluk_m": 5, "beton_m3": 1.0, "kalip_m2": 10.0}
win.radye_ad_edit.setText("Ana Blok")
win.radye_alan_spin.setValue(250)
win.radye_kalinlik_spin.setValue(60)
win.radye_dis_cevre_spin.setValue(70)
win._radye_bosluk_satir_ekle("Asansör", 9)
win._radye_bosluk_satir_ekle("Merdiven", 6)
kontrol("form canlı: beton 150.00 / kalıp 51.00",
        win.radye_beton_label.text() == "150.0 m³" and win.radye_kalip_label.text() == "51.0 m²",
        (win.radye_beton_label.text(), win.radye_kalip_label.text()))
kontrol("form toplam çevre 85.00", win.radye_toplam_cevre_label.text() == "85.00 m")
kontrol("Ekle'den önce özette radye yok", "Radye" not in str(win._kat_ozeti_kalemleri()))
win._radye_ekle()
kontrol("listeye 1 radye girdi", len(win.radye_kayitlari) == 1 and win.radye_table.rowCount() == 1)
satir = [win.radye_table.item(0, c).text() for c in range(7)]
kontrol("liste satırı", satir == ["Ana Blok", "250.00", "60.0", "150.0", "70.00", "15.00", "51.0"], satir)


def temel():
    oz = win._kat_ozeti_hesapla()
    return oz, {x["kat"]: x for x in oz["katlar"]}


oz, katlar = temel()
el = {e["eleman"]: e for e in katlar["Temel"]["elemanlar"]}
kontrol("özet Temel grubunda Radye 150 / 51", (el["Radye"]["beton_m3"], el["Radye"]["kalip_m2"]) == (150.0, 51.0), el)
kontrol("SBH aynı grupta, Radye önce", [e["eleman"] for e in katlar["Temel"]["elemanlar"]] == ["Radye", "Temel Kirişi"])
kontrol("Temel ara toplamı radyeyi içerir 151 / 61",
        (katlar["Temel"]["beton_m3"], katlar["Temel"]["kalip_m2"]) == (151.0, 61.0), katlar["Temel"])
kontrol("genel toplam radyeyi içerir", (oz["beton_m3"], oz["kalip_m2"]) == (151.0, 61.0), oz)
ekran = [[win.kat_ozeti_table.item(r, c).text() if win.kat_ozeti_table.item(r, c) else ""
          for c in range(5)] for r in range(win.kat_ozeti_table.rowCount())]
kontrol("ekran özeti otomatik güncellendi (Yenile'ye basmadan)",
        ["Temel", "Radye", "1", "150.0", "51.0"] in ekran, ekran)
kontrol("ara toplam etiketi TEMEL TOPLAMI", any(s[1] == "TEMEL TOPLAMI" for s in ekran), ekran)

# Düzenleme: satırı seç, kalınlığı 80 yap, güncelle -> özet otomatik
win.radye_table.setCurrentCell(0, 0)
win._radye_satir_secildi(0)
kontrol("satır seçilince boşluklar forma yüklendi", win.radye_bosluk_table.rowCount() == 2)
win.radye_kalinlik_spin.setValue(80)
win._radye_guncelle()
_, katlar = temel()
el = {e["eleman"]: e for e in katlar["Temel"]["elemanlar"]}
kontrol("güncelleme özete yansıdı: 200 / 68", (el["Radye"]["beton_m3"], el["Radye"]["kalip_m2"]) == (200.0, 68.0), el)
kontrol("güncelleme ad/kayıt sayısını korur", len(win.radye_kayitlari) == 1 and win.radye_kayitlari[0]["ad"] == "Ana Blok")
win.radye_kalinlik_spin.setValue(60)
win._radye_guncelle()

# İkinci radye (adsız -> R2), sonra silme
win.radye_ad_edit.clear()
win.radye_alan_spin.setValue(10)
win.radye_kalinlik_spin.setValue(50)
win.radye_dis_cevre_spin.setValue(14)
win.radye_bosluk_table.setRowCount(0)
win._radye_ekle()
kontrol("adsız ikinci radye R2", win.radye_kayitlari[-1]["ad"] == "R2", [k["ad"] for k in win.radye_kayitlari])
_, katlar = temel()
el = {e["eleman"]: e for e in katlar["Temel"]["elemanlar"]}
kontrol("özet: 2 radye birleşik 155 / 58", (el["Radye"]["adet"], el["Radye"]["beton_m3"], el["Radye"]["kalip_m2"])
        == (2.0, 155.0, 58.0), el)

# ── 3. Excel: Radye sekmesinden ──
_dosya["yol"] = os.path.join(GECICI, "radye.xlsx")
win._radye_excel()
kontrol("Radye Excel dosyası oluştu", os.path.exists(_dosya["yol"]))
ws = load_workbook(_dosya["yol"])["Radye"]
hucreler = [ws.cell(row=r, column=1).value or "" for r in range(1, 15)]
kontrol("başlıkta proje adı", "Proje: Deneme Konut" in hucreler, hucreler)
kontrol("başlıkta tarih", any(str(h).startswith("Tarih: ") for h in hucreler))
kontrol("kabullerde kalınlık birimi + iç boşluk eklenir",
        any("santimetre" in str(h) for h in hucreler) and any("EKLENİR" in str(h) for h in hucreler))
bas = next(r for r in range(1, 30) if ws.cell(row=r, column=1).value == "Radye adı")
basliklar = [ws.cell(row=bas, column=c).value for c in range(1, 8)]
kontrol("sütunlar brief sırasıyla", basliklar == ["Radye adı", "Alan (m²)", "Kalınlık (cm)", "Beton (m³)",
                                                  "Dış çevre (m)", "İç boşluk çevreleri toplamı (m)", "Kalıp (m²)"],
        basliklar)
r = bas + 1
kontrol("ana satır Ana Blok", ws.cell(row=r, column=1).value == "Ana Blok")
alt = [(ws.cell(row=r + i, column=1).value, ws.cell(row=r + i, column=6).value) for i in (1, 2)]
kontrol("boşluklar ayrı alt satırda (ad + çevre)",
        "Asansör" in alt[0][0] and alt[0][1] == 9 and "Merdiven" in alt[1][0] and alt[1][1] == 6, alt)
kontrol("Excel beton = 150.00 (formül)", str(ws[f"D{r}"].value).startswith("=")
        and abs(degerlendir(ws, f"D{r}") - 150.0) < 1e-9, ws[f"D{r}"].value)
kontrol("Excel iç boşluk toplamı = 15", abs(degerlendir(ws, f"F{r}") - 15.0) < 1e-9, ws[f"F{r}"].value)
kontrol("Excel kalıp = 51.00 (formül)", abs(degerlendir(ws, f"G{r}") - 51.0) < 1e-9, ws[f"G{r}"].value)
r2 = r + 3
kontrol("R2 alt satırı yok, hemen sonra", ws.cell(row=r2, column=1).value == "R2")
top = r2 + 1
kontrol("TOPLAM satırı", ws.cell(row=top, column=1).value == "TOPLAM")
kontrol("toplamlar SUM formülü", all(str(ws.cell(row=top, column=c).value).startswith("=SUM(") for c in (2, 4, 5, 6, 7)),
        [ws.cell(row=top, column=c).value for c in range(1, 8)])
kontrol("Excel toplam beton 155 / kalıp 58 / iç çevre 15 (alt satırlar çift sayılmaz)",
        (degerlendir(ws, f"D{top}"), degerlendir(ws, f"G{top}"), degerlendir(ws, f"F{top}")) == (155.0, 58.0, 15.0))
# Elle düzeltme simülasyonu: alan 250 -> 300 -> beton ve toplam formülle değişir
ws[f"B{r}"] = 300
kontrol("elle düzeltme: beton formülü 180, toplam 185",
        (degerlendir(ws, f"D{r}"), degerlendir(ws, f"D{top}")) == (180.0, 185.0))

# ── 4. Kat Özeti Excel: Temel'de Radye satırı + ayrı Radye sayfası ──
_dosya["yol"] = os.path.join(GECICI, "ozet.xlsx")
win._kat_ozeti_excel()
wb = load_workbook(_dosya["yol"])
kontrol("özet dosyasında Kat Özeti + Radye sayfaları", wb.sheetnames == ["Kat Özeti", "Radye"], wb.sheetnames)
oz_ws = wb["Kat Özeti"]
satirlar = [[c.value for c in row] for row in oz_ws.iter_rows()]
kontrol("özet Excel Temel/Radye satırı 155 / 58",
        any(s[:2] == ["Temel", "Radye"] and s[3] == 155.0 and s[4] == 58.0 for s in satirlar), satirlar)
kontrol("özet Excel TEMEL TOPLAMI 156 / 68",
        any(s[1] == "TEMEL TOPLAMI" and s[3] == 156.0 and s[4] == 68.0 for s in satirlar))
kontrol("özet dosyasındaki Radye sayfası da 155", abs(degerlendir(wb["Radye"], f"D{top}") - 155.0) < 1e-9)

# Silme -> özet otomatik
win.radye_table.setCurrentCell(1, 0)
win._radye_sil()
_, katlar = temel()
el = {e["eleman"]: e for e in katlar["Temel"]["elemanlar"]}
kontrol("silme özete yansıdı: 150 / 51", (el["Radye"]["beton_m3"], el["Radye"]["kalip_m2"]) == (150.0, 51.0), el)

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
