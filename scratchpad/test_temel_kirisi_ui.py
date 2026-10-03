"""Rev-137 Aşama 3b — Temel Kirişi TOPLU MOD paneli + sekme (headless, sahte connector)."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
import tempfile  # noqa: E402
os.environ["QUANTIX_DATA_DIR"] = tempfile.mkdtemp()   # Rev-153: SBH demir parametreleri gerçek dosyaya yazılmasın
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog, QDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

import app.ui.metraj_analiz_window as maw  # noqa: E402

# Rev-153: yeni SBH tipi -> demir parametre penceresi; headless'ta modal exec bloke eder
maw.SbhDemirTipDialog.exec = lambda self: QDialog.DialogCode.Accepted

GECEN = KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad)


SORU = []
QT_UYARI = []
BIRIM_CEVAP = ["cm"]


def _soru(*a, **k):
    return QMessageBox.StandardButton.Yes if (SORU.pop(0) if SORU else False) else QMessageBox.StandardButton.No


QMessageBox.question = staticmethod(_soru)
QMessageBox.warning = staticmethod(lambda *a, **k: QT_UYARI.append(a[2] if len(a) > 2 else ""))
QMessageBox.information = staticmethod(lambda *a, **k: QT_UYARI.append(a[2] if len(a) > 2 else ""))
QMessageBox.critical = staticmethod(lambda *a, **k: QT_UYARI.append(a[2] if len(a) > 2 else ""))
QInputDialog.getItem = staticmethod(lambda *a, **k: (BIRIM_CEVAP[0], BIRIM_CEVAP[0] is not None))
QInputDialog.getDouble = staticmethod(lambda *a, **k: (_ for _ in ()).throw(AssertionError("Qt getDouble açılmamalı")))


def yz(ad, g, y, h):
    return {"ad": ad, "genislik_cm": g, "yukseklik_cm": y, "handle": h, "uyari": "", "basarili": True}


def cz(uz, h):
    return {"handle": h, "uzunluk_birim": uz, "obje_tipi": "AcDbLine", "hata": ""}


def kiris(yazilar, cizgiler):
    return {"durum": "okundu", "yazilar": yazilar, "gecersiz_yazilar": [], "cizgiler": cizgiler,
            "diger_sayisi": 0}


class SahteConnector:
    bagli = True

    def __init__(self, okumalar, elle=None):
        self.okumalar = list(okumalar)
        self.elle = list(elle or [])
        self.yesil = set()
        self.mesajlar = []
        self.baslat_sayisi = 0

    def temel_kirisi_toplu_baslat(self):
        self.baslat_sayisi += 1

    def temel_kirisi_kiris_oku(self):
        return self.okumalar.pop(0) if self.okumalar else {"durum": "bos_secim"}

    def temel_kirisi_mesaj(self, m):
        self.mesajlar.append(m)

    def temel_kirisi_uzunluk_sor(self, istem):
        self.mesajlar.append("SORU: " + istem)
        return self.elle.pop(0) if self.elle else None

    def obje_isaretle_hizli(self, h):
        self.yesil.add(h)

    def obje_isaret_geri_al(self, h):
        self.yesil.discard(h)

    def cizim_birimi_oku(self):
        return "cm"

    def komut_satiri_evet_hayir(self, istem, varsayilan=None):  # Rev-158 eksik parça sorusu
        self.mesajlar.append("SORU: " + istem)
        return True


def m_var(c, parca):
    return any(parca in m for m in c.mesajlar)


# 1) Normal toplu akış: 2 kiriş, her biri yazı + 2 çizgi, tek başlatma
c = SahteConnector([
    kiris([yz("SBH-1", 20, 165, "Y1")], [cz(500, "A1"), cz(500, "B1")]),
    kiris([yz("SBH-2", 25, 150, "Y2")], [cz(1240, "A2"), cz(1240, "B2")]),
])
QT_UYARI.clear()
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
s = p.sonuclar()
kontrol("2 kiriş toplandı", len(s) == 2)
kontrol("SBH-1 1.65 m³ / 16.5 m²", s[0]["beton_m3"] == 1.65 and s[0]["kalip_m2"] == 16.5)
kontrol("SBH-2 4.65 / 37.2", s[1]["beton_m3"] == 4.65 and s[1]["kalip_m2"] == 37.2)
kontrol("yazı + 2 çizgi x2 = 6 obje yeşil", c.yesil == {"Y1", "A1", "B1", "Y2", "A2", "B2"})
kontrol("AutoCAD öne getirme TEK sefer", c.baslat_sayisi == 1)
kontrol("döngü boyunca Qt mesaj kutusu açılmadı", QT_UYARI == [])
kontrol("komut satırı EKLENDİ mesajı", m_var(c, "SBH-1 EKLENDİ") and m_var(c, "toplam 2 kiriş"))
kontrol("kaynak ortalama", s[0]["kaynak"].startswith("Çizgi ort."))

# 2) Ortalama: farklı üst/alt çizgi
c = SahteConnector([kiris([yz("SBH-3", 20, 100, "Y3")], [cz(480, "A3"), cz(520, "B3")])])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
kontrol("ortalama 5.00", p.sonuclar()[0]["uzunluk_m"] == 5.0)

# 3) Undo: son kiriş, yazı + 2 çizgi rengi geri
c = SahteConnector([
    kiris([yz("SBH-1", 20, 165, "Y1")], [cz(500, "A1"), cz(500, "B1")]),
    kiris([yz("SBH-2", 25, 150, "Y2")], [cz(600, "A2"), cz(600, "B2")]),
])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
p._son_ekleneni_geri_al()
kontrol("undo -> 1 satır", len(p.sonuclar()) == 1)
kontrol("undo -> Y2/A2/B2 yeşili gitti", c.yesil == {"Y1", "A1", "B1"})

# 4) Hatalı seçim (yazı yok / 2 yazı / 3 çizgi) -> komut satırı HATA, atlanır, döngü devam
c = SahteConnector([
    kiris([], [cz(500, "A1"), cz(500, "B1")]),
    kiris([yz("SBH-1", 20, 165, "Y1"), yz("SBH-2", 20, 165, "Y2")], []),
    kiris([yz("SBH-1", 20, 165, "Y1")], [cz(500, "A"), cz(500, "B"), cz(500, "C")]),
    kiris([yz("SBH-4", 20, 165, "Y4")], [cz(500, "A4"), cz(500, "B4")]),
])
QT_UYARI.clear()
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
kontrol("3 hatalı atlandı, 1 eklendi", len(p.sonuclar()) == 1 and p.sonuclar()[0]["ad"] == "SBH-4")
kontrol("komut satırında 3 HATA", sum("HATA" in m for m in c.mesajlar) == 3)
kontrol("hatalı kirişler boyanmadı", c.yesil == {"Y4", "A4", "B4"})
kontrol("hatada Qt kutusu yok", QT_UYARI == [])

# 5) Çizgi yok -> AutoCAD komut satırından elle uzunluk (GetReal yedeği)
c = SahteConnector([kiris([yz("SBH-5", 20, 100, "Y5")], [])], elle=[3.5])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
r = p.sonuclar()[0]
kontrol("elle 3.5, kaynak Elle", r["uzunluk_m"] == 3.5 and r["kaynak"] == "Elle")
kontrol("elle sorusu komut satırında + net uyarısı", m_var(c, "SORU: SBH-5") and m_var(c, "Net (yüzden yüze)"))
kontrol("elle yolda sadece yazı yeşil", c.yesil == {"Y5"})

# 6) Elle ESC -> kiriş atlanır, boyanmaz, döngü devam
c = SahteConnector([kiris([yz("SBH-6", 20, 100, "Y6")], []),
                    kiris([yz("SBH-7", 20, 100, "Y7")], [cz(500, "A7"), cz(500, "B7")])], elle=[None])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
kontrol("ESC -> SBH-6 atlandı, SBH-7 eklendi", [x["ad"] for x in p.sonuclar()] == ["SBH-7"])
kontrol("SBH-6 boyanmadı", "Y6" not in c.yesil)

# 7) Mükerrer (aynı oturum): aynı yazı tekrar -> GÜNCELLENİR, tek satır, eski çizgiler geri
c = SahteConnector([
    kiris([yz("SBH-1", 20, 165, "Y1")], [cz(500, "A1"), cz(500, "B1")]),
    kiris([yz("SBH-1", 20, 165, "Y1")], [cz(600, "A9"), cz(600, "B9")]),
])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
kontrol("mükerrer -> tek satır", len(p.sonuclar()) == 1)
kontrol("mükerrer -> L=6 güncel", p.sonuclar()[0]["uzunluk_m"] == 6.0)
kontrol("GÜNCELLENDİ mesajı", m_var(c, "SBH-1 GÜNCELLENDİ"))
kontrol("eski çizgiler A1/B1 yeşili söküldü", c.yesil == {"Y1", "A9", "B9"})
p._son_ekleneni_geri_al()
kontrol("güncellenmiş satır undo -> tüm yeşiller gitti", c.yesil == set())

# 8) Mükerrer (önceki oturum / tablo) -> GÜNCELLENDİ, yazı yeniden boyanmaz
mevcut = {"Y1": {"ad": "SBH-1", "yazi_handle": "Y1", "cizgi_handleler": ["A1", "B1"]}}
c = SahteConnector([kiris([yz("SBH-1", 20, 165, "Y1")], [cz(700, "A1"), cz(700, "B1")])])
p = maw.TemelKirisiDonguPaneli(c, "cm", mevcut)
p._dongu()
kontrol("tablodaki kiriş GÜNCELLENDİ", m_var(c, "SBH-1 GÜNCELLENDİ") and p.sonuclar()[0]["uzunluk_m"] == 7.0)
kontrol("önceden boyalı objeler yeni_boyanan'a girmedi", p.sonuclar()[0]["yeni_boyanan"] == [])

# 9) İptal -> tüm oturum renkleri geri
c = SahteConnector([kiris([yz("SBH-1", 20, 165, "Y1")], [cz(500, "A1"), cz(500, "B1")])])
SORU[:] = [True]
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
p._iptal()
kontrol("iptal -> renk yok", c.yesil == set())

# 10) Uyarılar komut satırında + panelde (Rev-158: fark > 2b -> eksik parça sorusu, Evet)
c = SahteConnector([kiris([yz("SBH-1", 20, 165, "Y1")], [cz(500, "A1"), cz(400, "B1")])])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
kontrol("eksik sorusu + uyarı komut satırında", m_var(c, "SORU: SBH-1") and m_var(c, "UYARI SBH-1"))
kontrol("fark uyarısı panel etiketinde", "SBH-1" in p.uyari_lbl.text())

# 11) COM hatası -> döngü durur, Qt hata + log, toplananlar korunur
class PatlayanConnector(SahteConnector):
    def temel_kirisi_kiris_oku(self):
        if self.okumalar:
            return self.okumalar.pop(0)
        raise RuntimeError("COM koptu")


c = PatlayanConnector([kiris([yz("SBH-1", 20, 165, "Y1")], [cz(500, "A1"), cz(500, "B1")])])
QT_UYARI.clear()
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
kontrol("COM hatası -> 1 kiriş korundu + hata gösterildi", len(p.sonuclar()) == 1 and QT_UYARI)

# 12) Gerçek log senaryosu: tek ENTER'da 2 SBH-1 + 4 çizgi -> 2 ayrı kiriş
def yzk(ad, h, konum):
    d = yz(ad, 20, 165, h)
    d["konum"] = konum
    return d


def czk(h, bas, son):
    return {"handle": h, "uzunluk_birim": 290.0, "obje_tipi": "AcDbLine", "hata": "", "bas": bas, "son": son}


c = SahteConnector([kiris(
    [yzk("SBH-1", "T2", (145, 110)), yzk("SBH-1", "T1", (145, 10))],
    [czk("C494E8", (0, 100), (290, 100)), czk("C490F2", (0, 0), (290, 0)),
     czk("C494E9", (290, 120), (0, 120)), czk("C490F4", (0, 20), (290, 20))])])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
s = p.sonuclar()
kontrol("log senaryosu -> 2 kiriş eklendi", len(s) == 2 and all(x["uzunluk_m"] == 2.9 for x in s))
kontrol("log senaryosu -> 'Tek seçimde 2 kiriş' mesajı", m_var(c, "Tek seçimde 2 kiriş"))
kontrol("log senaryosu -> 6 obje yeşil", len(c.yesil) == 6)
kontrol("SBH-1 beton 0.2×1.65×2.9=0.957", s[0]["beton_m3"] == 0.957)
p._son_ekleneni_geri_al()
kontrol("undo tek kirişi geri alır (diğeri kalır)", len(p.sonuclar()) == 1 and len(c.yesil) == 3)

c = SahteConnector([kiris([yzk("SBH-1", "T1", (0, 10)), yzk("SBH-2", "T2", (0, 110))],
                          [czk("A", (0, 0), (290, 0)), czk("B", (0, 20), (290, 20)),
                           czk("C", (0, 100), (290, 100))])])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
kontrol("2 yazı + 3 çizgi -> HATA, hiçbir şey eklenmedi", not p.sonuclar() and m_var(c, "HATA"))

# ── Pencere sekmesi entegrasyonu ──
win = maw.MetrajAnalizWindow()
orijinal_exec = maw.TemelKirisiDonguPaneli.exec
maw.QTimer.singleShot = staticmethod(lambda ms, f: None)


def _exec(self):
    self._dongu()
    return QDialog.DialogCode.Accepted


maw.TemelKirisiDonguPaneli.exec = _exec
c = SahteConnector([
    kiris([yz("SBH-1", 20, 165, "Y1")], [cz(500, "A1"), cz(500, "B1")]),
    kiris([yz("SBH-2", 25, 150, "Y2")], [cz(1240, "A2"), cz(1240, "B2")]),
])
win.acad_connector = c
BIRIM_CEVAP[0] = "cm"
win._temel_kirisi_sec()
kontrol("sekme 2 satır", win.temel_kirisi_table.rowCount() == 2)
kontrol("toplam 6.300 m³ / 53.700 m²",
        "6.3 m³" in win.tk_toplam_label.text() and "53.7 m²" in win.tk_toplam_label.text())
kontrol("birim combo 'cm' oldu", win.tk_birim_combo.currentText() == "cm")

# Birim diyaloğu iptal -> hiçbir şey olmaz
BIRIM_CEVAP[0] = None
c.okumalar = [kiris([yz("SBH-9", 20, 165, "Y9")], [cz(500, "A"), cz(500, "B")])]
win._temel_kirisi_sec()
kontrol("birim iptal -> seçim başlamadı", len(c.okumalar) == 1)

# Tekrar okuma birikmez; yeni çizgiler, eski çizgilerin yeşili sökülür
BIRIM_CEVAP[0] = "cm"
c.okumalar = [kiris([yz("SBH-1", 20, 165, "Y1")], [cz(600, "A8"), cz(600, "B8")])]
win._temel_kirisi_sec()
kontrol("tekrar okuma -> hâlâ 2 satır", win.temel_kirisi_table.rowCount() == 2)
kontrol("SBH-1 güncellendi 1.98", win.temel_kirisi_kayitlari["Y1"]["beton_m3"] == 1.98)
kontrol("eski A1/B1 yeşili söküldü", "A1" not in c.yesil and "B1" not in c.yesil and "A8" in c.yesil)

# mm birim
BIRIM_CEVAP[0] = "mm"
c.okumalar = [kiris([yz("SBH-3", 30, 120, "Y3")], [cz(4000, "A3"), cz(4000, "B3")])]
win._temel_kirisi_sec()
kontrol("mm: 4000 -> 4 m, beton 1.44", win.temel_kirisi_kayitlari["Y3"]["beton_m3"] == 1.44)

# Uzunluk hücresi elle düzeltme
row = next(r for r in range(win.temel_kirisi_table.rowCount()) if win._temel_kirisi_handle(r) == "Y1")
win.temel_kirisi_table.item(row, 3).setText("10")
kontrol("elle düzeltme L=10 -> 3.3", win.temel_kirisi_kayitlari["Y1"]["beton_m3"] == 3.3)

es = win._temel_kirisi_excel_satirlari()
kontrol("Excel TOPLAM", es[-1][0] == "TOPLAM" and es[-1][4] == round(3.3 + 4.65 + 1.44, 3))

# Seçili sil -> yazı + 2 çizgi yeşili gider
win.temel_kirisi_table.selectRow(row)
win._temel_kirisi_sil()
kontrol("sil -> Y1/A8/B8 yeşili gitti", not ({"Y1", "A8", "B8"} & c.yesil))

win.acad_connector = None
QT_UYARI.clear()
win._temel_kirisi_sec()
kontrol("bağlantı yok uyarısı", any("AutoCAD" in u for u in QT_UYARI))

maw.TemelKirisiDonguPaneli.exec = orijinal_exec
print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
