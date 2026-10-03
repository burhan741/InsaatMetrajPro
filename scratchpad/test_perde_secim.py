"""Rev-143 Aşama 3 — Perde: seçim değerlendirme + sahte COM + döngü paneli + ana tablo."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

from app.core import autocad_connector as ac  # noqa: E402
from app.core.autocad_connector import (  # noqa: E402
    perde_secimi_degerlendir, cizim_alani_m2ye_cevir, KatYukseklikAyari)
import app.ui.metraj_analiz_window as maw  # noqa: E402

maw.QTimer.singleShot = staticmethod(lambda *a, **k: None)  # döngü elle çağrılacak

GECEN = KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad)


# cm çizim: 25×400 perde -> alan 1.0 m², çevre 8.5 m
KOSE = [(0, 0), (400, 0), (400, 25), (0, 25)]


def poli(h="P1", kose=KOSE, kapali=True, alan=10000, uz=850, tip="AcDbPolyline"):
    return {"handle": h, "obje_tipi": tip, "alan_birim": alan, "kapali": kapali,
            "uzunluk_birim": uz, "koseler": kose, "metin": "", "hata": ""}


def cizgi(h, a, b, tip="AcDbLine"):
    uz = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
    return {"handle": h, "obje_tipi": tip, "alan_birim": 0.0, "kapali": False,
            "uzunluk_birim": uz, "koseler": [a, b], "metin": "", "hata": ""}


def tarama(h, alan):
    return {"handle": h, "obje_tipi": "AcDbHatch", "alan_birim": alan, "kapali": False,
            "uzunluk_birim": 0.0, "koseler": [], "metin": "", "hata": ""}


def yazi(h, metin):
    return {"handle": h, "obje_tipi": "AcDbMText", "alan_birim": 0.0, "kapali": False,
            "uzunluk_birim": 0.0, "koseler": [], "metin": metin, "hata": ""}


# ── 1) Saf seçim değerlendirme ──
d = perde_secimi_degerlendir([poli()], "cm")
kontrol("kapalı poligon: alan 1.0, çevre 8.5", d["alan_m2"] == 1.0 and d["cevre_m"] == 8.5 and not d["hata"])
d = perde_secimi_degerlendir([poli(), cizgi("L1", (0, 0), (0, 25))], "cm")
kontrol("uç çizgisi (kolona bitişik) düşülür 0.25", d["dusulen_m"] == 0.25 and d["dusulen_handleler"] == ["L1"])
d = perde_secimi_degerlendir([poli(), cizgi("L1", (0, 0), (0, 25)), cizgi("L2", (400, 0), (400, 25))], "cm")
kontrol("iki uç düşülür 0.50", d["dusulen_m"] == 0.5)
d = perde_secimi_degerlendir([poli(), cizgi("E1", (0, -50), (400, -50))], "cm")
kontrol("çevre dışı eksen çizgisi düşülMEZ + uyarı",
        d["dusulen_m"] == 0 and "çevre üzerinde değil" in d["uyari"] and not d["hata"])
d = perde_secimi_degerlendir([poli(), cizgi("K1", (100, 0), (100, 25))], "cm")
kontrol("kesitin içinden geçen çizgi (uçları çevrede, ortası değil) düşülMEZ", d["dusulen_m"] == 0)
d = perde_secimi_degerlendir([poli(), cizgi("T1", (0, 0.8), (0, 25.5))], "cm")
kontrol("tolerans içi (≤2 cm) sapma kabul", d["dusulen_m"] > 0)
d = perde_secimi_degerlendir([poli(), cizgi("A1", (0, 0), (0, 25), tip="AcDbPolyline")], "cm")
kontrol("açık polyline uç çizgisi olarak kabul", d["dusulen_m"] == 0.25)
d = perde_secimi_degerlendir([poli(kapali=False)], "cm")
kontrol("açık polyline kesit -> REDDEDİLİR", "KAPALI DEĞİL" in d["hata"])
d = perde_secimi_degerlendir([poli("P1"), poli("P2", kose=[(0, 100), (400, 100), (400, 125), (0, 125)])], "cm")
kontrol("iki kapalı poligon -> hata", "2 kapalı poligon" in d["hata"])
d = perde_secimi_degerlendir([poli(), tarama("H1", 10000.2)], "cm")
kontrol("tarama + sınır -> tek sayım", d["alan_m2"] == 1.0 and not d["hata"])
d = perde_secimi_degerlendir([poli(), tarama("H1", 5000)], "cm")
kontrol("farklı alanlı tarama -> hata (ikinci perde)", d["hata"] != "")
d = perde_secimi_degerlendir([tarama("H1", 10000)], "cm")
kontrol("sadece tarama -> hata (sınır çizgisi iste)", "tarama" in d["hata"])
d = perde_secimi_degerlendir([], "cm")
kontrol("boş -> hata", d["hata"] != "")
# Düşüm çevreyi geçemez: kare 10×10 çevre 40, 4 kenar + fazladan kopya kenar
kare = [(0, 0), (10, 0), (10, 10), (0, 10)]
kenarlar = [cizgi(f"K{i}", kare[i], kare[(i + 1) % 4]) for i in range(4)]
d = perde_secimi_degerlendir([poli(kose=kare, alan=100, uz=40)] + kenarlar, "cm")
kontrol("tüm kenarlar düşülürse (düşüm = çevre) -> hata", "geçemez" in d["hata"])
d = perde_secimi_degerlendir([poli(), yazi("T1", "{\\fArial|b0;S339}")], "cm")
kontrol("tek yazı -> perde adı S339", d["ad"] == "S339" and "T1" in d["kullanilan_handleler"])
d = perde_secimi_degerlendir([poli(), yazi("T1", "S339"), yazi("T2", "S340")], "cm")
kontrol("iki yazı -> ad yok + uyarı", d["ad"] == "" and "yazı" in d["uyari"])
d = perde_secimi_degerlendir([poli(kose=[(x / 50, y / 50) for x, y in KOSE], alan=10000 / 2500, uz=850 / 50)], "cm")
kontrol("1/50 ölçek unutulursa -> çok küçük uyarısı", "çok küçük" in d["uyari"])
d = perde_secimi_degerlendir([poli(kose=[(x / 50, y / 50) for x, y in KOSE], alan=10000 / 2500, uz=850 / 50),
                              cizgi("L1", (0, 0), (0, 0.5))], "cm", 50)
kontrol("1/50 doğru ölçek: alan 1.0, çevre 8.5, düşüm 0.25",
        d["alan_m2"] == 1.0 and d["cevre_m"] == 8.5 and d["dusulen_m"] == 0.25)
kontrol("2dPolyline da kesit sayılır", perde_secimi_degerlendir([poli(tip="AcDb2dPolyline")], "cm")["alan_m2"] == 1.0)
kontrol("cizim_alani_m2ye_cevir 1/50 mm", cizim_alani_m2ye_cevir(1700, "mm", 50) == 4.25)


# ── 2) Sahte COM: perde_oku ──
class Ent:
    def __init__(self, tip, h, **k):
        self.ObjectName, self.Handle = tip, h
        for a, v in k.items():
            setattr(self, a, v)


class SS:
    def __init__(self):
        self.o = []

    @property
    def Count(self):
        return len(self.o)

    def Item(self, i):
        return self.o[i]

    def Clear(self):
        pass


class Doc:
    def __init__(self):
        self.ss = SS()
        doc = self

        class Setler:
            def Item(self, ad):
                raise KeyError(ad)

            def Add(self, ad):
                return doc.ss
        self.SelectionSets = Setler()


c = ac.AutoCADConnector.__new__(ac.AutoCADConnector)
c._orijinal_renkler = {}
c._bagli = True
c.acad_app = object()
c.aktif_cizim = Doc()
c.selection_set = None
c._autocad_one_getir_hafif = lambda: None
c._selection_set_temizle = lambda: None
SECIM = []
c._guvenli_select_on_screen = lambda ss: setattr(ss, "o", SECIM.pop(0))
c.perde_toplu_baslat()
SECIM[:] = [[Ent("AcDbPolyline", "P1", Closed=True, Length=850.0, Area=10000.0,
                 Coordinates=(0, 0, 400, 0, 400, 25, 0, 25)),
             Ent("AcDbLine", "L1", Length=25.0, StartPoint=(0, 0, 0), EndPoint=(0, 25, 0)),
             Ent("AcDbMText", "T1", TextString="S339"),
             Ent("AcDbRotatedDimension", "D1")]]
r = c.perde_oku()
kontrol("COM: 4 obje okundu", r["durum"] == "okundu" and len(r["objeler"]) == 4)
kontrol("COM: poligon köşeleri 4", r["objeler"][0]["koseler"] == KOSE)
d = perde_secimi_degerlendir(r["objeler"], "cm")
kontrol("COM -> değerlendirme: S339, alan 1.0, düşüm 0.25",
        d["ad"] == "S339" and d["alan_m2"] == 1.0 and d["dusulen_m"] == 0.25)
SECIM[:] = [[Ent("AcDb2dPolyline", "P2", Closed=True, Length=850.0, Area=10000.0,
                 Coordinates=(0, 0, 0, 400, 0, 0, 400, 25, 0, 0, 25, 0))]]
kontrol("COM: 2dPolyline 3B koordinat -> 4 köşe", c.perde_oku()["objeler"][0]["koseler"] == KOSE)
SECIM[:] = [[]]
kontrol("COM: boş ENTER -> bos_secim", c.perde_oku()["durum"] == "bos_secim")


# ── 3) Döngü paneli — sahte connector ──
class SahteConnector:
    bagli = True

    def __init__(self):
        self.okumalar, self.cevaplar, self.mesajlar = [], [], []
        self.boyanan, self.geri = [], []

    def perde_toplu_baslat(self):
        pass

    def perde_oku(self):
        return self.okumalar.pop(0) if self.okumalar else {"durum": "bos_secim", "objeler": []}

    def komut_satiri_mesaj(self, m):
        self.mesajlar.append(m)

    def komut_satiri_evet_hayir(self, istem):
        self.mesajlar.append("SORU: " + istem)
        return self.cevaplar.pop(0)

    def obje_rengi_ayarla(self, h, renk):  # Rev-160: perde rengi + önceki renk
        (self.geri if renk is None else self.boyanan).append(h)
        return None

    def obje_isaretle_hizli(self, h):
        self.boyanan.append(h)

    def obje_isaret_geri_al(self, h):
        self.geri.append(h)

    def cizim_birimi_oku(self):
        return "cm"


def ok(*o):
    return {"durum": "okundu", "objeler": list(o)}


AYAR = KatYukseklikAyari(3.0, 0.2, "tam")
sc = SahteConnector()

# İlk perde teyidi REDDEDİLİR -> döngü durur, hiçbir şey eklenmez
p = maw.PerdeDonguPaneli(sc, "cm", "1:1", 1.0, AYAR, False, {})
sc.okumalar = [ok(poli()), ok(poli("P9"))]
sc.cevaplar = [False]
p._dongu()
kontrol("panel: ilk teyit reddi -> döngü DURDU", "DURDURULDU" in " ".join(sc.mesajlar)
        and not p.sonuclar() and len(sc.okumalar) == 1)

# Onaylı akış
sc = SahteConnector()
p = maw.PerdeDonguPaneli(sc, "cm", "1:1", 1.0, AYAR, False, {})
sc.okumalar = [ok(poli(), cizgi("L1", (0, 0), (0, 25)), yazi("T1", "S339")),
               ok(poli("P2", kose=[(0, 100), (400, 100), (400, 125), (0, 125)])),
               ok(poli(kapali=False)),
               ok(poli(), cizgi("L1", (0, 0), (0, 25)), cizgi("L2", (400, 0), (400, 25)), yazi("T1", "S339"))]
sc.cevaplar = [True]
p._dongu()
s = p.sonuclar()
kontrol("panel: tek teyit sorusu (sonrakiler sorulmadı)",
        sum(m.startswith("SORU") for m in sc.mesajlar) == 1 and p.alan_teyitli)
kontrol("panel: açık polyline ATLANDI mesajı", any("KAPALI DEĞİL" in m for m in sc.mesajlar))
kontrol("panel: aynı poligon tekrar -> GÜNCELLENDİ, 2 satır", len(s) == 2
        and any("S339 GÜNCELLENDİ" in m for m in sc.mesajlar))
s339 = next(x for x in s if x["ad"] == "S339")
kontrol("panel: güncel satır düşüm 0.50", s339["dusulen_m"] == 0.5)
kontrol("panel: isimsiz perde 'Perde 2'", any(x["ad"] == "Perde 2" for x in s))
kontrol("panel: tekrar boyama yok (P1 bir kez)", sc.boyanan.count("P1") == 1)
kontrol("panel: L2 yeni boyandı", "L2" in sc.boyanan)
h = p._hesap(s339)
kontrol("panel: beton tam kat 1.0×3.0 = 3.0", h["beton_m3"] == 3.0)
kontrol("panel: kalıp (8.5−0.5)×2.8 = 22.4", h["kalip_m2"] == 22.4)
kontrol("panel: toplam etiketi", "2 perde" in p.toplam_lbl.text())
p._son_ekleneni_geri_al()
kontrol("panel: geri al -> 1 satır, renk geri", len(p.sonuclar()) == 1 and "P1" in sc.geri)

# Şüpheli alan teyitli oturumda da sorulur
sc = SahteConnector()
p = maw.PerdeDonguPaneli(sc, "cm", "1:1", 1.0, AYAR, True, {})
sc.okumalar = [ok(poli(alan=4, uz=850))]
sc.cevaplar = [False]
p._dongu()
kontrol("panel: şüpheli alan teyitli oturumda soruldu, red -> atlandı",
        any(m.startswith("SORU") for m in sc.mesajlar) and not p.sonuclar())

# Perde-perde birleşim çizgisi iki perdede: geri alınca diğeri hâlâ kullanıyorsa renk kalır
sc = SahteConnector()
p = maw.PerdeDonguPaneli(sc, "cm", "1:1", 1.0, AYAR, True, {})
kose2 = [(0, 25), (0, 225), (25, 225), (25, 25)]
sc.okumalar = [ok(poli(), cizgi("J", (0, 25), (25, 25))),
               ok(poli("P2", kose=kose2, alan=5000, uz=450), cizgi("J", (0, 25), (25, 25)))]
p._dongu()
kontrol("birleşim: iki perdede de düşüldü",
        all(x["dusulen_m"] == 0.25 for x in p.sonuclar()))
p._son_ekleneni_geri_al()
kontrol("birleşim: geri alınca ortak çizgi rengi KORUNDU", "J" not in sc.geri)
p._iptal()
kontrol("iptal: tüm boyananlar geri alındı", "P1" in sc.geri and "J" in sc.geri)


# ── 4) Ana pencere: registry + tablo + esas başlığı ──
win = maw.MetrajAnalizWindow()
win.perde_doseme_otomatik_chk.setChecked(False)  # Rev-163: bu test döşemeyi ELLE giriyor
kontrol("pencere: ortak ayar nesnesi var", isinstance(win.yukseklik_ayari, KatYukseklikAyari))
win.perde_yukseklik_spin.setValue(3.0)
win.perde_doseme_spin.setValue(0.2)
sc = SahteConnector()
win.acad_connector = sc
win.aktif_kat_adi = "Zemin"
win._perde_aktif_kat_yukle()
sc.okumalar = [ok(poli(), cizgi("L1", (0, 0), (0, 25)), yazi("T1", "S339"))]
sc.cevaplar = [True]


def exec_yerine(self):
    self._dongu()
    self._bitti()
    return self.result()


maw.PerdeDonguPaneli.exec = exec_yerine
win._perde_sec()
kontrol("pencere: registry 1 perde", len(win.perde_kayitlari) == 1)
kontrol("pencere: teyit durumu pencereye taşındı", win._perde_alan_teyitli)
kontrol("pencere: tablo beton 3.00 / kalıp (8.5−0.25)×2.8 = 23.10",
        win.perde_table.item(0, 4).text() == "3.0" and win.perde_table.item(0, 5).text() == "23.1")
kontrol("pencere: başlıkta esas yazıyor", "Tam kat" in win.perde_esas_label.text())
win.perde_esas_combo.setCurrentIndex(win.perde_esas_combo.findData("net"))
kontrol("pencere: esas net -> tablo beton 2.80, kalıp değişmez",
        win.perde_table.item(0, 4).text() == "2.8" and win.perde_table.item(0, 5).text() == "23.1")
kontrol("pencere: ayar nesnesi güncellendi (döşeme aracı okuyacak)", win.yukseklik_ayari.beton_esasi == "net")
kontrol("pencere: başlık Net", "Net" in win.perde_esas_label.text())
win.perde_doseme_spin.setValue(3.0)
kontrol("pencere: geçersiz ayar başlıkta uyarı", "⚠" in win.perde_esas_label.text())
sc.okumalar = [ok(poli())]
MESAJ = []
QMessageBox.warning = staticmethod(lambda *a, **k: MESAJ.append(a[2]))
win._perde_sec()
kontrol("pencere: geçersiz ayarla seçim başlamaz", MESAJ and len(sc.okumalar) == 1)
win.perde_doseme_spin.setValue(0.2)
win.perde_table.selectRow(0)
win._perde_sil()
kontrol("pencere: seçili sil -> boş + renkler geri",
        not win.perde_kayitlari and {"P1", "L1", "T1"} <= set(sc.geri))

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
