"""Rev-144 Aşama 2 — Döşeme köşe tıklama: geometri + sahte COM + döngü paneli + pencere."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
import tempfile  # noqa: E402
os.environ["QUANTIX_DATA_DIR"] = tempfile.mkdtemp()  # OSMODE ayar dosyası gerçek data/'ya yazılmasın
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

from app.core import autocad_connector as ac  # noqa: E402
from app.core.autocad_connector import (  # noqa: E402
    doseme_poligon_degerlendir, dikdortgen_koseleri, poligon_kendini_kesiyor_mu,
    nokta_poligon_icinde_mi, poligon_agirlik_merkezi)
import app.ui.metraj_analiz_window as maw  # noqa: E402

maw.QTimer.singleShot = staticmethod(lambda *a, **k: None)

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"   [{detay}]" if detay else ""))


# ── 1) Saf geometri ──
d = doseme_poligon_degerlendir(dikdortgen_koseleri((10, 20), (130, 120)), "mm", 50)
kontrol("1/50 mm dikdörtgen 120×100 birim -> 6×5 m: alan 30, çevre 22",
        d["alan_m2"] == 30.0 and d["cevre_m"] == 22.0 and not d["hata"], f"{d['alan_m2']} m², {d['cevre_m']} m")
d2 = doseme_poligon_degerlendir(dikdortgen_koseleri((130, 120), (10, 20)), "mm", 50)
kontrol("ters yönde tıklanan köşeler aynı sonuç", d2["alan_m2"] == 30.0 and d2["cevre_m"] == 22.0)
L = [(0, 0), (600, 0), (600, 300), (300, 300), (300, 500), (0, 500)]
d = doseme_poligon_degerlendir(L, "cm")
kontrol("L poligon (cm): alan 24, çevre 22", d["alan_m2"] == 24.0 and d["cevre_m"] == 22.0,
        f"{d['alan_m2']} m², {d['cevre_m']} m")
kontrol("L saat yönü tersi aynı alan", doseme_poligon_degerlendir(L[::-1], "cm")["alan_m2"] == 24.0)
d = doseme_poligon_degerlendir(L + [(0, 0)], "cm")
kontrol("kapanış tekrarı (son = ilk) temizlenir", d["alan_m2"] == 24.0 and len(d["koseler"]) == 6)
d = doseme_poligon_degerlendir([(0, 0), (0, 0), (600, 0), (600, 500), (0, 500)], "cm")
kontrol("çift tıklama temizlenir", d["alan_m2"] == 30.0 and len(d["koseler"]) == 4)
papyon = [(0, 0), (100, 100), (100, 0), (0, 100)]
kontrol("papyon kendini kesiyor", poligon_kendini_kesiyor_mu(papyon))
kontrol("papyon -> reddedilir", "kendini kesiyor" in doseme_poligon_degerlendir(papyon, "cm")["hata"])
kontrol("L kendini kesmiyor", not poligon_kendini_kesiyor_mu(L))
kontrol("2 nokta -> hata", "En az 3" in doseme_poligon_degerlendir([(0, 0), (1, 1)], "cm")["hata"])
kontrol("doğrusal 3 nokta -> hata", "sıfır" in doseme_poligon_degerlendir([(0, 0), (1, 0), (2, 0)], "cm")["hata"])
kontrol("1/50 unutulursa -> şüpheli (teyit)",
        doseme_poligon_degerlendir(dikdortgen_koseleri((0, 0), (120, 100)), "mm")["supheli"])
kontrol("L ağırlık merkezi L'nin içinde", nokta_poligon_icinde_mi(poligon_agirlik_merkezi(L), L))
kontrol("L'nin boş köşesi (450,400) dışarıda", not nokta_poligon_icinde_mi((450, 400), L))


# ── 2) Sahte COM: ENTER/ESC ayrımı, OSMODE, çizim ──
class ComHata(Exception):
    def __init__(self, hresult, excepinfo=None):
        super().__init__(hresult)
        self.hresult = hresult
        self.excepinfo = excepinfo


class Utility:
    def __init__(self):
        self.kuyruk, self.promptlar, self.girdi = [], [], ""

    def InitializeUserInput(self, bit, kw):
        pass

    def Prompt(self, m):
        self.promptlar.append(m)

    def _al(self, *a):
        x = self.kuyruk.pop(0)
        if isinstance(x, Exception):
            raise x
        return x

    GetPoint = GetCorner = GetKeyword = _al

    def GetInput(self):
        return self.girdi


class PL:
    def __init__(self, v):
        self.v, self.Handle, self.Closed, self.Layer, self.Color = v, "PL1", False, "0", 7

    def Update(self):
        pass


class MS:
    def __init__(self):
        self.cizilen = []

    def AddLightWeightPolyline(self, v):
        pl = PL(v)
        self.cizilen.append(pl)
        return pl


class Doc:
    def __init__(self):
        self.Utility, self.ModelSpace, self.vars = Utility(), MS(), {"OSMODE": 4133}
        self.katmanlar = []
        doc = self

        class Layers:
            def Add(self, ad):
                doc.katmanlar.append(ad)
        self.Layers = Layers()

    def GetVariable(self, ad):
        return self.vars[ad]

    def SetVariable(self, ad, v):
        self.vars[ad] = int(v)


c = ac.AutoCADConnector.__new__(ac.AutoCADConnector)
c._orijinal_renkler = {}
c._bagli = True
c.acad_app = object()
c.aktif_cizim = Doc()
c._autocad_one_getir_hafif = lambda: None
u = c.aktif_cizim.Utility

u.kuyruk = [(1.0, 2.0, 0.0)]
kontrol("GetPoint nokta", c.doseme_nokta_al("x") == ("nokta", (1.0, 2.0)))
u.kuyruk, u.girdi = [ComHata(-2145320928)], ""
kontrol("ENTER (anahtar girdi kodu, boş GetInput) -> enter", c.doseme_nokta_al("x", (0, 0)) == ("enter", None))
u.kuyruk = [ComHata(-2147352567, (0, "AutoCAD", "err", None, 0, -2145320928))]
kontrol("ENTER kodu excepinfo içinde -> enter", c.doseme_nokta_al("x")[0] == "enter")
u.kuyruk, u.girdi = [ComHata(-2145320928)], "K"
kontrol("yazı girişi -> metin", c.doseme_nokta_al("x") == ("metin", "K"))
u.kuyruk = [ComHata(-2147352567)]
kontrol("ESC (diğer kod) -> esc", c.doseme_nokta_al("x") == ("esc", None))
u.kuyruk = [(5.0, 6.0, 0.0)]
kontrol("GetCorner nokta", c.doseme_kose_al((0, 0), "y") == ("nokta", (5.0, 6.0)))
u.kuyruk = ["Poligon"]
kontrol("mod: Poligon -> P", c.doseme_mod_sor() == "P")
u.kuyruk = ["Dikdortgen"]
kontrol("mod: Dikdortgen -> D", c.doseme_mod_sor() == "D")
u.kuyruk = [""]
kontrol("mod: boş ENTER -> bitti", c.doseme_mod_sor() == "bitti")
u.kuyruk = [ComHata(-2145320928)]
kontrol("mod: ENTER hata koduyla -> bitti", c.doseme_mod_sor() == "bitti")
u.kuyruk = [ComHata(-2147352567)]
kontrol("mod: ESC -> esc", c.doseme_mod_sor() == "esc")

c.doseme_toplu_baslat()
kontrol("başlat: OSMODE 33, katman oluşturuldu",
        c.aktif_cizim.vars["OSMODE"] == 33 and "METRAJ_DOSEME" in c.aktif_cizim.katmanlar)
try:
    try:
        raise RuntimeError("döngü içinde hata")
    finally:
        c.doseme_toplu_bitir()
except RuntimeError:
    pass
kontrol("hata olsa da OSMODE eski değere (4133) döndü", c.aktif_cizim.vars["OSMODE"] == 4133)
h = c.doseme_poligon_ciz([(0, 0), (10, 0), (10, 5)])
pl = c.aktif_cizim.ModelSpace.cizilen[-1]
kontrol("poligon: kapalı, METRAJ_DOSEME, MACENTA (6) — yeşil DEĞİL, koordinat düz liste",
        h == "PL1" and pl.Closed and pl.Layer == "METRAJ_DOSEME" and pl.Color == 6
        and list(pl.v.value) == [0, 0, 10, 0, 10, 5])


# ── 3) Döngü paneli — sahte connector ──
class SahteConnector:
    bagli = True

    def __init__(self):
        self.modlar, self.noktalar, self.cevaplar, self.mesajlar = [], [], [], []
        self.cizilen, self.silinen, self.bitir = [], [], 0
        self.istemler = []
        self._n = 0

    def komut_satiri_mesaj(self, m):
        self.mesajlar.append(m)

    def doseme_toplu_baslat(self):
        pass

    def doseme_toplu_bitir(self):
        self.bitir += 1

    def doseme_mod_sor(self):
        return self.modlar.pop(0) if self.modlar else "bitti"

    def doseme_nokta_al(self, istem, baz=None, anahtarlar=""):
        self.istemler.append(istem)
        return self.noktalar.pop(0) if self.noktalar else ("enter", None)

    def doseme_kose_al(self, baz, istem):
        return self.noktalar.pop(0)

    def komut_satiri_evet_hayir(self, istem, varsayilan=None):
        self.mesajlar.append("SORU: " + istem)
        if "oşluk" in istem:          # Aşama 3 boşluk sorusu: bu testte hep ENTER (Hayır)
            return bool(varsayilan)
        return self.cevaplar.pop(0)

    def doseme_poligon_ciz(self, koseler, renk=None):
        self._n += 1
        h = f"H{self._n}"
        self.cizilen.append((h, list(koseler)))
        return h

    def obje_sil(self, h):
        self.silinen.append(h)
        return True

    def cizim_birimi_oku(self):
        return "cm"


def N(x, y):
    return ("nokta", (x, y))


E = ("enter", None)


def dik(x1, y1, x2, y2):
    return [N(x1, y1), N(x2, y1), N(x2, y2), N(x1, y2), E]


# İlk teyit reddi -> döngü durur, hiçbir şey çizilmez, OSMODE geri
sc = SahteConnector()
p = maw.DosemeDonguPaneli(sc, "cm", "1:1", 1.0, 15.0, False, [])
sc.noktalar = dik(0, 0, 600, 500) + dik(0, 0, 600, 500)
sc.cevaplar = [False]
p._dongu()
kontrol("panel: ilk teyit reddi -> DURDURULDU, çizim yok, OSMODE geri",
        "DURDURULDU" in " ".join(sc.mesajlar) and not sc.cizilen and not p.kayitlar and sc.bitir == 1)

# Tam akış
sc = SahteConnector()
p = maw.DosemeDonguPaneli(sc, "cm", "1:1", 1.0, 15.0, False, [])
sc.noktalar = (dik(0, 0, 600, 500)                                      # D1 6×5
               + [N(700, 0), N(1300, 0), E, N(1300, 300),              # 2 köşede ENTER -> uyarı, devam
                  N(1000, 300), N(1000, 500), N(700, 500), E]          # D2 L = 24 m² (6 köşe)
               + [N(0, 0), ("esc", None)]                              # ESC -> bu seçim iptal
               + [N(0, 0), N(100, 100), N(100, 0), N(0, 100), E]       # papyon -> reddedilir
               + dik(50, 50, 550, 450)                                 # D1 içine -> güncelleme? HAYIR
               + dik(10, 10, 590, 490)                                 # D1 içine -> güncelleme EVET
               + [E])                                                  # 1. köşede ENTER -> bitti
sc.cevaplar = [True, False, True]
p._dongu()
k = p.kayitlar
kontrol("panel: mod sorusu yok, 1. köşe istemi 'bitirmek için ENTER'",
        not sc.modlar and "bitirmek için ENTER" in sc.istemler[0])
kontrol("panel: 2 döşeme D1/D2", [s["ad"] for s in k] == ["D1", "D2"], str([s["ad"] for s in k]))
kontrol("panel: tek alan teyidi sorusu", sum("doğru mu" in m for m in sc.mesajlar) == 1)
kontrol("panel: poligonda 3 köşe altı ENTER -> uyarı, devam", any("En az 3 köşe" in m for m in sc.mesajlar))
kontrol("panel: L alanı 24, çevre 22", k[1]["brut_alan_m2"] == 24.0 and k[1]["cevre_m"] == 22.0)
kontrol("panel: ESC -> seçim iptal mesajı, döngü devam", any("iptal edildi (ESC)" in m for m in sc.mesajlar))
kontrol("panel: papyon ALINMADI", any("kendini kesiyor" in m for m in sc.mesajlar))
kontrol("panel: mükerrer sorusu D1 adıyla", sum("zaten D1 olarak kayıtlı" in m for m in sc.mesajlar) == 2)
kontrol("panel: güncelleme EVET -> D1 alanı 5.8×4.8 = 27.84, eski poligon silindi",
        k[0]["brut_alan_m2"] == 27.84 and "H1" in sc.silinen and k[0]["handle"] == "H3")
kontrol("panel: HAYIR -> çizim yapılmadı (toplam 3 poligon)", len(sc.cizilen) == 3)
kontrol("panel: kaynak Tıklama, kalınlık 15", k[0]["kaynak"] == "Tıklama" and k[1]["kalinlik_cm"] == 15.0)
kontrol("panel: OSMODE geri yüklendi", sc.bitir == 1)

# Geri al: güncellemeyi geri al -> H3 silinir, eski D1 (6×5) yeniden çizilir
p._son_ekleneni_geri_al()
kontrol("geri al (güncelleme): D1 eski alan 30, yeni poligon silindi, eski yeniden çizildi",
        k[0]["brut_alan_m2"] == 30.0 and "H3" in sc.silinen and k[0]["handle"] == "H4")
p._son_ekleneni_geri_al()
kontrol("geri al (ekleme): D2 ve poligonu gitti", len(p.kayitlar) == 1 and "H2" in sc.silinen)
p._iptal()
kontrol("iptal: kalan eylem geri alındı, liste boş, D1 poligonu silindi",
        not p.kayitlar and "H4" in sc.silinen)

# Kayıtlı (önceki oturum) döşeme ile mükerrer + X ile kapatma
onceki = [{"ad": "D1", "brut_alan_m2": 30.0, "bosluk_alan_m2": 0, "bosluk_cevre_m": 0, "serbest_kenar_m": 0,
           "kalinlik_cm": 18.0, "kaynak": "Tıklama", "handle": "ESKI",
           "koseler": dikdortgen_koseleri((0, 0), (600, 500)), "cevre_m": 22.0}]
sc = SahteConnector()
p = maw.DosemeDonguPaneli(sc, "cm", "1:1", 1.0, 15.0, True, onceki)
sc.noktalar = dik(20, 20, 580, 480)
sc.cevaplar = [True]
p._dongu()
kontrol("önceki oturum döşemesi güncellendi, kalınlık (18) korundu",
        p.kayitlar[0]["kalinlik_cm"] == 18.0 and "ESKI" in sc.silinen and len(p.kayitlar) == 1)
kontrol("pencereden gelen liste bozulmadı (çalışma kopyası)", onceki[0]["handle"] == "ESKI")
# 1. köşede ESC de döngüyü bitirir; 10 köşeli poligon kabul
sc2 = SahteConnector()
p2 = maw.DosemeDonguPaneli(sc2, "cm", "1:1", 1.0, 15.0, True, [])
on_kose = [N(0, 0), N(100, 0), N(100, 100), N(200, 100), N(200, 0), N(300, 0), N(300, 200),
           N(150, 250), N(0, 200), N(0, 100), E]
sc2.noktalar = on_kose + [("esc", None)]
p2._dongu()
kontrol("10 köşeli poligon alındı, sonra 1. köşede ESC -> döngü bitti",
        len(p2.kayitlar) == 1 and len(p2.kayitlar[0]["koseler"]) == 10 and sc2.bitir == 1,
        f"alan {p2.kayitlar[0]['brut_alan_m2'] if p2.kayitlar else '-'} m²")
p.reject()
kontrol("X ile kapatma = iptal: yeni poligon silindi, eski yeniden çizildi",
        "H1" in sc.silinen and p.kayitlar[0]["handle"] == "H2")


# ── 4) Pencere entegrasyonu ──
def exec_yerine(self):
    self._dongu()
    self.accept()
    return self.result()


maw.DosemeDonguPaneli.exec = exec_yerine
win = maw.MetrajAnalizWindow()
kontrol("pencere: birim/ölçek combo + AutoCAD butonu",
        win.doseme_birim_combo.count() == 4 and win.doseme_olcek_combo.findText("1:50") >= 0)
sc = SahteConnector()
win.acad_connector = sc
win.doseme_varsayilan_h_spin.setValue(20.0)
win.doseme_birim_combo.setCurrentText("cm")
sc.noktalar = dik(0, 0, 600, 500)
sc.cevaplar = [True]
win._doseme_sec()
kontrol("pencere: satır eklendi, beton 30×0.20 = 6.00, handle H1, kaynak Tıklama",
        win.doseme_table.item(0, 6).text() == "6.0" and win.doseme_table.item(0, 11).text() == "H1"
        and win.doseme_table.item(0, 10).text() == "Tıklama")
kontrol("pencere: teyit durumu taşındı", win._doseme_alan_teyitli)
win.doseme_olcek_combo.setCurrentText("1:50")
kontrol("pencere: ölçek değişince teyit sıfırlandı", not win._doseme_alan_teyitli)
win.doseme_table.selectRow(0)
win._doseme_sil()
kontrol("pencere: satır silinince poligon da silindi", "H1" in sc.silinen and not win.doseme_kayitlari)

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
