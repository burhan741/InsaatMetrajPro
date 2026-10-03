"""Rev-153 — SBH demir: sekme sütunları, yeni tip penceresi (S6), tip düzenleme (S7),
çap özeti, Excel satırları, kesim listesine aktarım (headless, sahte connector)."""
import json
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
GECICI = tempfile.mkdtemp()
os.environ["QUANTIX_DATA_DIR"] = GECICI
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog, QDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
MESAJ = []
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, _ad=ad, **k: MESAJ.append((_ad, a[2] if len(a) > 2 else ""))))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
SECIM = {"birim": "cm", "tip": "SBH-1"}
QInputDialog.getItem = staticmethod(
    lambda parent, baslik, *a, **k: (SECIM["birim"] if "Birim" in baslik else SECIM["tip"], True))

import app.ui.metraj_analiz_window as maw  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"  [{detay}]" if detay else ""))


# Parametre penceresi: açılış sayısını say, istenen değerleri formdan gir
ACILAN = []
FORM_DEGER = {}


def _dialog_exec(self):
    ACILAN.append(self.windowTitle())
    for k, v in FORM_DEGER.items():
        self.alanlar[k].setValue(v)
    self._kaydet()
    return QDialog.DialogCode.Accepted if self.result() == QDialog.DialogCode.Accepted else QDialog.DialogCode.Rejected


maw.SbhDemirTipDialog.exec = _dialog_exec
maw.QTimer.singleShot = staticmethod(lambda ms, f: None)


def _panel_exec(self):
    self._dongu()
    return QDialog.DialogCode.Accepted


maw.TemelKirisiDonguPaneli.exec = _panel_exec


def yz(ad, g, y, h):
    return {"ad": ad, "genislik_cm": g, "yukseklik_cm": y, "handle": h, "uyari": "", "basarili": True}


def cz(uz, h):
    return {"handle": h, "uzunluk_birim": uz, "obje_tipi": "AcDbLine", "hata": ""}


def kiris(y, c):
    return {"durum": "okundu", "yazilar": y, "gecersiz_yazilar": [], "cizgiler": c, "diger_sayisi": 0}


class SahteConnector:
    bagli = True

    def __init__(self, okumalar):
        self.okumalar = list(okumalar)

    def temel_kirisi_toplu_baslat(self):
        pass

    def temel_kirisi_kiris_oku(self):
        return self.okumalar.pop(0) if self.okumalar else {"durum": "bos_secim"}

    def temel_kirisi_mesaj(self, m):
        pass

    def temel_kirisi_uzunluk_sor(self, istem):
        return None

    def obje_isaretle_hizli(self, h):
        pass

    def obje_isaret_geri_al(self, h):
        pass


win = maw.MetrajAnalizWindow()
kontrol("tablo 16 sütun, beton/kalıp indeksleri değişmedi",
        win.temel_kirisi_table.columnCount() == 16
        and win.temel_kirisi_table.horizontalHeaderItem(4).text() == "Beton (m³)"
        and win.temel_kirisi_table.horizontalHeaderItem(15).text() == "Toplam Demir (kg)")

# S1 + S6: iki SBH-1 (L=10, L=14) + bir SBH-2 -> iki yeni tip, pencere tip başına BİR kez
win.acad_connector = SahteConnector([
    kiris([yz("SBH-1", 30, 165, "Y1")], [cz(1000, "A1"), cz(1000, "B1")]),
    kiris([yz("SBH-1", 30, 165, "Y2")], [cz(1400, "A2"), cz(1400, "B2")]),
    kiris([yz("SBH-2", 30, 165, "Y3")], [cz(1000, "A3"), cz(1000, "B3")]),
])
win._temel_kirisi_sec()
kontrol("S6 yeni tipler için pencere tip başına 1 kez (SBH-1, SBH-2)",
        ACILAN == ["SBH-1 — Demir Parametreleri", "SBH-2 — Demir Parametreleri"], ACILAN)
with open(os.path.join(GECICI, "autocad_ayarlari.json"), encoding="utf-8") as f:
    kayit = json.load(f)["sbh_demir_tipleri"]
kontrol("parametreler kalıcı dosyaya yazıldı", set(kayit) == {"SBH-1", "SBH-2"}
        and kayit["SBH-1"]["filiz_boy_cm"] == 280.0 and kayit["SBH-1"]["tevzi_sira"] is None)


def satir(handle):
    t = win.temel_kirisi_table
    r = next(r for r in range(t.rowCount()) if win._temel_kirisi_handle(r) == handle)
    return [t.item(r, c).text() for c in range(t.columnCount())]


s = satir("Y1")
kontrol("S1 satırı: filiz 102 / 285.60 m / 253.61 kg, tevzi 18 k=0 10.00 / 180.00 / 111.06 kg",
        s[7:15] == ["102", "285.60", "253.61", "18", "0", "10.00", "180.00", "111.06"], s[7:])
s = satir("Y2")
kontrol("S5 satırı: k=1, boy 14.50, 261.00 m, 161.04 kg", s[11:15] == ["1", "14.50", "261.00", "161.04"], s[11:])
kontrol("beton/kalıp değişmedi (30/165/10 -> 4.950 / 33.000)", satir("Y1")[4:6] == ["5.0", "33.0"])
kontrol("çap bazlı özet etiketi Ø10 + Ø12", "Ø10:" in win.tk_demir_label.text() and "Ø12:" in win.tk_demir_label.text(),
        win.tk_demir_label.text())

# Tekrar seçim: SBH-1 artık kayıtlı -> pencere AÇILMAZ
ACILAN.clear()
win.acad_connector.okumalar = [kiris([yz("SBH-1", 30, 165, "Y4")], [cz(1200, "A4"), cz(1200, "B4")])]
win._temel_kirisi_sec()
kontrol("kayıtlı tip tekrar seçilince pencere açılmaz", ACILAN == [])
kontrol("S5c satırı L=12 -> k=0, boy 12.00", satir("Y4")[11:13] == ["0", "12.00"])

# Yeni pencere (program yeniden açıldı) kayıtlı tipleri dosyadan okur
win_b = maw.MetrajAnalizWindow()
kontrol("yeniden açılışta tipler dosyadan yüklendi", set(win_b._tk_demir_tipleri()) == {"SBH-1", "SBH-2"})

# S7: SBH-1 filiz boyu 280 -> 260 -> SBH-1 satırları güncellenir, SBH-2 değişmez
sbh2_once = satir("Y3")[7:]
SECIM["tip"] = "SBH-1"
FORM_DEGER.clear()
FORM_DEGER["filiz_boy_cm"] = 260
win._temel_kirisi_parametre_duzenle()
kontrol("S7 SBH-1 Y1 filiz uzunluk 265.20 m", satir("Y1")[8] == "265.20", satir("Y1")[8])
kontrol("S7 SBH-1 Y2 de güncellendi (142×2.6=369.20)", satir("Y2")[8] == "369.20", satir("Y2")[8])
kontrol("S7 SBH-2 değişmedi", satir("Y3")[7:] == sbh2_once)

# Geçersiz parametre -> pencere kaydetmez (Vazgeç sayılır), eski değer korunur
FORM_DEGER.clear()
FORM_DEGER["tevzi_bindirme_cm"] = 1500
ACILAN.clear()
kaydedildi = win._temel_kirisi_tip_parametresi_sor("SBH-1")
kontrol("bindirme ≥ stok -> kaydedilmedi, eski parametre korundu",
        not kaydedildi and win._tk_tip_parametresi("SBH-1")["tevzi_bindirme_cm"] == 50.0)
FORM_DEGER.clear()

# Tevzi sıra elle (S2) — SBH-2'ye 9 gir: sonuç değişmez
FORM_DEGER["tevzi_sira"] = 9
SECIM["tip"] = "SBH-2"
win._temel_kirisi_parametre_duzenle()
kontrol("S2 SBH-2 sıra elle 9 -> satır aynı", satir("Y3")[7:] == sbh2_once)
FORM_DEGER.clear()

# Excel satırları
es = win._temel_kirisi_excel_satirlari()
kontrol("Excel satırları 16 sütun + TOPLAM son satır", all(len(r) == 16 for r in es) and es[-1][0] == "TOPLAM")
kontrol("Excel TOPLAM demir = satırların toplamı",
        abs(es[-1][15] - sum(r[15] for r in es[:-1])) < 0.01, es[-1][15])

# Kesim listesine aktarım: sahte ana pencere + demir penceresi


class SahteDemirPenceresi:
    def __init__(self):
        self.satirlar = []

        class _Tab:
            def setCurrentIndex(self, i):
                pass
        self.tab_widget = _Tab()

    def _kesim_satir_ekle_deger(self, cap, boy_cm, adet, eleman):
        self.satirlar.append((cap, boy_cm, adet, eleman))

    def isVisible(self):
        return True

    def show(self):
        pass

    def raise_(self):
        pass

    def activateWindow(self):
        pass


class SahteAna:
    def __init__(self):
        self.demir_window = SahteDemirPenceresi()

    def open_demir_hesaplama(self):
        pass


ana = SahteAna()
win.parent = lambda: ana
win._temel_kirisi_kesime_aktar()
satirlar = ana.demir_window.satirlar
kontrol("kesim: hiçbir parça 1200 cm'yi aşmıyor", satirlar and all(b <= 1200 for _, b, _, _ in satirlar), satirlar)
tevzi_kesim_m = sum(b * a for c, b, a, _ in satirlar if c == 10) / 100
tevzi_metraj_m = sum(win._temel_kirisi_demir(s)["tevzi_uzunluk_m"] for s in win.temel_kirisi_kayitlari.values())
kontrol("kesim tevzi uzunluğu = metraj (bindirme bir kez)", abs(tevzi_kesim_m - tevzi_metraj_m) < 0.01,
        (tevzi_kesim_m, tevzi_metraj_m))
kontrol("aynı çap+boy birleşti, eleman tipi Temel",
        len({(c, b) for c, b, _, _ in satirlar}) == len(satirlar) and all(e == "Temel" for *_, e in satirlar))
kontrol("bilgi mesajı", MESAJ and MESAJ[-1][0] == "information" and "Temel kirişi demiri" in MESAJ[-1][1])

print(f"\n{GECEN} PASS / {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
