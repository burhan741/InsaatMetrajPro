"""Rev-143 Aşama 4 — Perde: kat bazlı kayıt + kat başına ayar + Excel + genel Beton & Kalıp tablosu."""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
MESAJ = []
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, _ad=ad, **k: MESAJ.append((_ad, a[2]))))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

import app.ui.metraj_analiz_window as maw  # noqa: E402

maw.QTimer.singleShot = staticmethod(lambda *a, **k: None)

GECEN = KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad)


KOSE = [(0, 0), (400, 0), (400, 25), (0, 25)]  # cm: alan 1.0 m², çevre 8.5 m


def poli(h="P1"):
    return {"handle": h, "obje_tipi": "AcDbPolyline", "alan_birim": 10000, "kapali": True,
            "uzunluk_birim": 850, "koseler": KOSE, "metin": "", "hata": ""}


def uc(h="L1"):
    return {"handle": h, "obje_tipi": "AcDbLine", "alan_birim": 0.0, "kapali": False,
            "uzunluk_birim": 25, "koseler": [(0, 0), (0, 25)], "metin": "", "hata": ""}


def yazi(metin, h="T1"):
    return {"handle": h, "obje_tipi": "AcDbText", "alan_birim": 0.0, "kapali": False,
            "uzunluk_birim": 0.0, "koseler": [], "metin": metin, "hata": ""}


class SahteConnector:
    bagli = True

    def __init__(self):
        self.okumalar, self.mesajlar, self.geri = [], [], []

    def perde_toplu_baslat(self):
        pass

    def perde_oku(self):
        return self.okumalar.pop(0) if self.okumalar else {"durum": "bos_secim", "objeler": []}

    def komut_satiri_mesaj(self, m):
        self.mesajlar.append(m)

    def komut_satiri_evet_hayir(self, istem):
        return True

    def obje_rengi_ayarla(self, h, renk):  # Rev-160: perde rengi + önceki renk
        if renk is None:
            self.geri.append(h)
        return None

    def obje_isaretle_hizli(self, h):
        pass

    def obje_isaret_geri_al(self, h):
        self.geri.append(h)

    def cizim_birimi_oku(self):
        return "cm"


def exec_yerine(self):
    self._dongu()
    self._bitti()
    return self.result()


maw.PerdeDonguPaneli.exec = exec_yerine


def ok(*o):
    return {"durum": "okundu", "objeler": list(o)}


win = maw.MetrajAnalizWindow()
win.perde_doseme_otomatik_chk.setChecked(False)  # Rev-163: bu test döşemeyi ELLE giriyor
sc = SahteConnector()
win.acad_connector = sc


def perde_satirlari():
    t = win.beton_kalip_table
    return [[t.item(r, c).text() for c in range(t.columnCount())] for r in range(t.rowCount())
            if t.item(r, 0) and t.item(r, 0).data(Qt.ItemDataRole.UserRole) == "perde"]


# ── Kat yokken seçim reddedilir ──
win.aktif_kat_adi = ""
win._perde_aktif_kat_yukle()
sc.okumalar = [ok(poli())]
MESAJ.clear()
win._perde_sec()
kontrol("kat yok -> uyarı, AutoCAD okunmadı", any("kat" in m for _, m in MESAJ) and len(sc.okumalar) == 1)
kontrol("kat yok -> etikette yönlendirme", "Demir Metrajı" in win.perde_aktif_kat_label.text())

# ── Zemin: 3.00 / 0.20 / Tam kat (gerçek kat ekleme akışıyla) ──
win.demir_kat_input.setText("Zemin")
win._demir_kat_ekle()
kontrol("kat ekleme perde sekmesini güncelledi", "Zemin" in win.perde_aktif_kat_label.text())
win.perde_yukseklik_spin.setValue(3.0)
win.perde_doseme_spin.setValue(0.2)
sc.okumalar = [ok(poli(), uc(), yazi("S339"))]
win._perde_sec()
kontrol("Zemin: 1 perde, anahtar (Zemin, P1)", list(win.perde_kayitlari) == [("Zemin", "P1")])

# ── 1.Kat: 2.85 / 0.15 / Net — AYNI handle P1 (başka DWG) ayrı kayıt ──
win.demir_kat_input.setText("1.Kat")
win._demir_kat_ekle()
kontrol("yeni kat önceki formu devraldı (3.00)", win.perde_yukseklik_spin.value() == 3.0)
win.perde_yukseklik_spin.setValue(2.85)
win.perde_doseme_spin.setValue(0.15)
win.perde_esas_combo.setCurrentIndex(win.perde_esas_combo.findData("net"))
kontrol("1.Kat tablosu boş (Zemin perdesi görünmez)", win.perde_table.rowCount() == 0)
sc.okumalar = [ok(poli(), uc(), yazi("S339"))]
win._perde_sec()
kontrol("aynı handle farklı katta -> 2 ayrı kayıt", len(win.perde_kayitlari) == 2)
h = win._perde_satir_hesap(win.perde_kayitlari[("1.Kat", "P1")], win.kat_yukseklik_ayarlari["1.Kat"])
kontrol("1.Kat: beton 1.0×2.70 = 2.70, kalıp 8.25×2.70 = 22.275",
        win.perde_table.item(0, 4).text() == "2.7" and h["kalip_m2"] == 22.275)

# ── Aynı katta tekrar seçim -> güncelleme (birikme yok) ──
sc.okumalar = [ok(poli(), yazi("S339"))]
win._perde_sec()
kontrol("1.Kat tekrar seçim -> hâlâ 2 kayıt, düşüm 0", len(win.perde_kayitlari) == 2
        and win.perde_kayitlari[("1.Kat", "P1")]["dusulen_m"] == 0)
sc.okumalar = [ok(poli(), uc(), yazi("S339"))]
win._perde_sec()

# ── Kat değişince ayar forma geri yüklenir ──
win.demir_kat_listesi.setCurrentRow(0)
win._demir_kat_secildi(None)
kontrol("Zemin seçilince form 3.00 / 0.20 / Tam",
        win.perde_yukseklik_spin.value() == 3.0 and win.perde_doseme_spin.value() == 0.2
        and win.perde_esas_combo.currentData() == "tam")
kontrol("Zemin tablosu: beton 3.00, kalıp 23.10",
        win.perde_table.item(0, 4).text() == "3.0" and win.perde_table.item(0, 5).text() == "23.1")
kontrol("kat ayarları ayrı saklanıyor (döşeme aracı okuyacak)",
        win.kat_yukseklik_ayarlari["1.Kat"].beton_esasi == "net"
        and win.kat_yukseklik_ayarlari["Zemin"].beton_esasi == "tam")
kontrol("tüm katlar toplamı etikette (beton 5.70)", "5.7 m³" in win.perde_toplam_label.text())

# ── Genel Beton & Kalıp tablosu ──
win.bk_fire_spin.setValue(5.0)
win._perde_tablo_yenile()
ps = perde_satirlari()
kontrol("genel tabloda 2 perde satırı", len(ps) == 2)
zemin = next(r for r in ps if r[0] == "Zemin")
kontrol("genel tablo Zemin: 'Perde S339', beton 3.000, kalıp 23.100, sipariş 3.150",
        zemin[1] == "Perde S339" and zemin[6] == "3.0" and zemin[9] == "23.1" and zemin[8] == "3.2")
kontrol("genel toplam etiketi perdeleri içeriyor (5.700)", "5.7 m" in win.bk_toplam_beton_label.text())
# Manuel satır korunur
t = win.beton_kalip_table
r = t.rowCount()
t.insertRow(r)
for c, v in enumerate(["Zemin", "Kolon", "1", "0.50", "0.50", "3.00", "0.8", "5.0", "0.8", "6.0"]):
    t.setItem(r, c, maw.QTableWidgetItem(v))
win.perde_esas_combo.setCurrentIndex(win.perde_esas_combo.findData("net"))
ps = perde_satirlari()
kontrol("Zemin esası net -> genel tablo 2.800, satır sayısı artmadı",
        next(r for r in ps if r[0] == "Zemin")[6] == "2.8" and len(ps) == 2)
kontrol("manuel kolon satırı korundu", any(t.item(i, 1).text() == "Kolon" for i in range(t.rowCount())))
kontrol("genel toplam: 2.8 + 2.7 + 0.75 = 6.250", "6.3 m" in win.bk_toplam_beton_label.text())
win.perde_esas_combo.setCurrentIndex(win.perde_esas_combo.findData("tam"))

# ── Excel ──
yol = os.path.join(tempfile.mkdtemp(), "perde.xlsx")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (yol, ""))
MESAJ.clear()
win._perde_excel()
kontrol("Excel dosyası yazıldı", os.path.exists(yol) and any(t == "information" for t, _ in MESAJ))
from openpyxl import load_workbook  # noqa: E402
ws = load_workbook(yol)["Perde"]
hucreler = [[c.value for c in row] for row in ws.iter_rows()]
duz = " | ".join(str(v) for row in hucreler for v in row if v is not None)
kontrol("Excel başlığı: Zemin esası (Tam kat 3.00)", "Zemin: Beton: Tam kat (3.00 m)" in duz)
kontrol("Excel başlığı: 1.Kat esası (Net 2.70)", "1.Kat: Beton: Net (kat − döşeme) (2.70 m)" in duz)
kontrol("Excel: kolon başlıkları", "Kalıp Yük. (m)" in duz and "Beton (m³)" in duz)
genel = next(row for row in hucreler if row[1] == "GENEL TOPLAM")
kontrol("Excel GENEL TOPLAM: beton 5.7, kalıp 23.1+22.275 = 45.375",
        abs(genel[7] - 5.7) < 1e-9 and abs(genel[8] - 45.375) < 1e-9)
kontrol("Excel: 2 ARA TOPLAM", sum(1 for row in hucreler if row[1] == "ARA TOPLAM") == 2)

# ── Sil: aktif kattan kalkar, genel tablodan da ──
win.perde_table.selectRow(0)
win._perde_sil()
kontrol("Zemin perdesi silindi, 1.Kat duruyor", list(win.perde_kayitlari) == [("1.Kat", "P1")])
kontrol("genel tabloda tek perde satırı kaldı", [r[0] for r in perde_satirlari()] == ["1.Kat"])
kontrol("Zemin renkleri geri alındı", {"P1", "L1", "T1"} <= set(sc.geri))
win._perde_temizle()
kontrol("Temizle sadece aktif katı siler (Zemin boştu, 1.Kat kaldı)", len(win.perde_kayitlari) == 1)

# ── Boş Excel ──
win.perde_kayitlari.clear()
MESAJ.clear()
win._perde_excel()
kontrol("perde yokken Excel -> bilgi mesajı", any("perde yok" in m for _, m in MESAJ))

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
