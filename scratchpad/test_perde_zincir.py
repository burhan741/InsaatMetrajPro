"""Rev-155 — Perde kontur zincirleme (ideCAD patlatılmış perde + blok): saf + sahte COM + panel."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

from app.core import autocad_connector as ac  # noqa: E402
from app.core.autocad_connector import (  # noqa: E402
    perde_secimi_degerlendir, perde_zincir_uc_dus, kontur_zincirle, KatYukseklikAyari)
import app.ui.metraj_analiz_window as maw  # noqa: E402

maw.QTimer.singleShot = staticmethod(lambda *a, **k: None)
GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"  [{detay}]" if detay else ""))


def acik(h, *kose, tip="AcDbPolyline", **ek):
    uz = sum(((kose[i][0] - kose[i + 1][0]) ** 2 + (kose[i][1] - kose[i + 1][1]) ** 2) ** 0.5
             for i in range(len(kose) - 1))
    o = {"handle": h, "obje_tipi": tip, "alan_birim": 0.0, "kapali": False, "uzunluk_birim": uz,
         "koseler": list(kose), "metin": "", "hata": "", "bulge_var": False}
    o.update(ek)
    return o


def cizgi(h, a, b, **ek):
    return acik(h, a, b, tip="AcDbLine", **ek)


def yazi(h, m, **ek):
    o = {"handle": h, "obje_tipi": "AcDbText", "alan_birim": 0.0, "kapali": False, "uzunluk_birim": 0.0,
         "koseler": [], "metin": m, "hata": ""}
    o.update(ek)
    return o


# 100×35 dikdörtgen (cm), 4 AÇIK parça, karışık yön ve sıra (ideCAD 35+100+100+35)
DIKD = [acik("E1", (0, 0), (100, 0)), acik("E3", (0, 35), (100, 35)),     # üst kenar ters yönde
        acik("E2", (100, 0), (100, 35)), acik("E4", (0, 35), (0, 0))]

# ── 1) Saf: brief testleri ──
d = perde_secimi_degerlendir(DIKD, "cm")
kontrol("4 parçalı 100×35: alan 0.35 m² (3500 cm²), çevre 2.70 m",
        d["alan_m2"] == 0.35 and d["cevre_m"] == 2.7 and not d["hata"] and d["zincir"], (d["alan_m2"], d["cevre_m"], d["hata"]))
kontrol("zincir: parça uzunlukları kayıtlı, düşüm henüz 0",
        d["zincir_parcalari"] == {"E1": 100.0, "E3": 100.0, "E2": 35.0, "E4": 35.0} and d["dusulen_m"] == 0)
kontrol("mükerrer anahtarı parça handle'larından (sıralı)", d["poligon_handle"] == "ZINCIR:E1+E2+E3+E4")
kontrol("boyanacaklar = 4 kenar", sorted(d["kullanilan_handleler"]) == ["E1", "E2", "E3", "E4"])
u = perde_zincir_uc_dus(d, ["E4"])
kontrol("35'lik uç düşülünce net çevre 2.35", u["dusulen_m"] == 0.35 and round(u["cevre_m"] - u["dusulen_m"], 3) == 2.35
        and u["dusulen_handleler"] == ["E4"] and not u["hata"])
u = perde_zincir_uc_dus(d, ["E4", "E4", "E2"])
kontrol("iki uç (aynısı iki kez seçilse de bir kez) -> 0.70", u["dusulen_m"] == 0.7)
u = perde_zincir_uc_dus(d, ["X9"])
kontrol("kontura ait olmayan seçim düşülmez + uyarı", u["dusulen_m"] == 0 and "parçası değil" in u["uyari"])
u = perde_zincir_uc_dus(d, ["E1", "E2", "E3", "E4"])
kontrol("düşüm çevreye eşit -> hata", "geçemez" in u["hata"])
kontrol("boş uç seçimi -> düşüm 0", perde_zincir_uc_dus(d, [])["dusulen_m"] == 0)

L = [cizgi("L1", (0, 0), (200, 0)), cizgi("L2", (200, 25), (200, 0)), cizgi("L3", (200, 25), (25, 25)),
     cizgi("L4", (25, 25), (25, 150)), cizgi("L5", (0, 150), (25, 150)), cizgi("L6", (0, 150), (0, 0))]
d = perde_secimi_degerlendir([L[3], L[0], L[5], L[2], L[4], L[1]], "cm")
kontrol("6 parçalı L perde: alan 200×25 + 25×125 = 8125 cm² = 0.8125 m², çevre 7.00",
        d["alan_m2"] == 0.8125 and d["cevre_m"] == 7.0, (d["alan_m2"], d["cevre_m"], d["hata"]))

bosluklu = [acik("E1", (0, 0), (100, 0)), acik("E2", (100, 0), (100, 35)),
            acik("E3", (100, 35), (5, 35)), acik("E4", (0, 35), (0, 0))]
d = perde_secimi_degerlendir(bosluklu, "cm")
kontrol("köşede 5 cm boşluk -> 'kontur kapanmıyor: ... boşluk'",
        "kontur kapanmıyor" in d["hata"] and "boşluk" in d["hata"] and "(5.00, 35.00)" in d["hata"], d["hata"])

ikinci = [acik("F1", (0, 100), (100, 100)), acik("F2", (100, 100), (100, 135)),
          acik("F3", (100, 135), (0, 135)), acik("F4", (0, 135), (0, 100))]
d = perde_secimi_degerlendir(DIKD + ikinci, "cm")
kontrol("iki dikdörtgenin 8 parçası -> 'seçimde 2 perde var, tek tek seçin'",
        d["hata"] == "seçimde 2 perde var, tek tek seçin", d["hata"])

# ── 2) Saf: ek durumlar ──
d = perde_secimi_degerlendir(DIKD + [cizgi("X1", (100, 0), (150, 0))], "cm")
kontrol("dallanma (bir düğümde 3 kenar) -> hata", "dallanıyor" in d["hata"], d["hata"])
d = perde_secimi_degerlendir(DIKD + [cizgi("K1", (100, 35), (0, 35))], "cm")
kontrol("üst üste kopya kenar bir kez sayılır + uyarı",
        d["alan_m2"] == 0.35 and d["cevre_m"] == 2.7 and "kopya" in d["uyari"], (d["hata"], d["uyari"]))
d = perde_secimi_degerlendir([acik("E1", (0, 0), (100, 0), (100, 35)), cizgi("E3", (100, 35), (0, 35)),
                              cizgi("E4", (0, 35), (0, 0))], "cm")
kontrol("çok köşeli açık polyline + çizgiler karışık -> 0.35 / 2.70", d["alan_m2"] == 0.35 and d["cevre_m"] == 2.7)
d = perde_secimi_degerlendir([acik("E1", (0, 0), (100, 0.3)), acik("E2", (100, 0), (100, 35)),
                              acik("E3", (100, 35), (0, 35)), acik("E4", (0, 35), (0.2, 0))], "cm")
kontrol("≤5 mm uç kayması tolerans içinde -> kapanır", not d["hata"], d["hata"])
d = perde_secimi_degerlendir([acik("E1", (0, 0), (100, 1.0))] + DIKD[1:], "cm")
kontrol("1 cm kayma -> boşluk hatası", "boşluk" in d["hata"])
d = perde_secimi_degerlendir([acik("E1", (0, 0), (100, 0), bulge_var=True)] + DIKD[1:], "cm")
kontrol("bulge (yay) -> açık mesajla red", "yay" in d["hata"] and "desteklenmiyor" in d["hata"])
arc = {"handle": "A1", "obje_tipi": "AcDbArc", "hata": ""}
kontrol("kontur kapanıyor ama seçimde ARC var -> red",
        "yay" in perde_secimi_degerlendir(DIKD + [arc], "cm")["hata"])
d = perde_secimi_degerlendir([acik("P", (0, 0), (100, 0), (100, 35), (0, 35))], "cm")
kontrol("tek açık polyline kapanmıyor -> 'KAPALI DEĞİL' (eski mesaj korunur)", "KAPALI DEĞİL" in d["hata"])
d = perde_secimi_degerlendir([acik("P", (0, 0), (100, 0), (100, 35), (0, 35), (0, 0))], "cm")
kontrol("tek açık polyline uçları çakışık -> kontur kabul (0.35)", d["alan_m2"] == 0.35 and not d["hata"])
mm = [acik("M1", (0, 0), (1000, 0)), acik("M2", (1000, 0), (1000, 350)),
      acik("M3", (1000, 350), (0, 350)), acik("M4", (0, 350), (0, 0))]
kontrol("mm çizim 1000×350 -> 0.35 m²", perde_secimi_degerlendir(mm, "mm")["alan_m2"] == 0.35)
d = perde_secimi_degerlendir(DIKD + [yazi("T1", "P12")], "cm")
kontrol("yazı perde adı olur", d["ad"] == "P12" and "T1" in d["kullanilan_handleler"])
k = kontur_zincirle([{"handle": "a", "koseler": [(0, 0), (10, 0)]}], 0.5)
kontrol("kontur_zincirle tek çizgi -> hata", bool(k["hata"]))

# ── 3) Saf: blok içeriği (geçici patlatılmış nesneler) ──
G = dict(gecici=True, blok_handle="B1")
blok_dikd = [acik("t1", (0, 0), (100, 0), **G), acik("t2", (100, 0), (100, 35), **G),
             acik("t3", (100, 35), (0, 35), **G), acik("t4", (0, 35), (0, 0), **G)]
d = perde_secimi_degerlendir(blok_dikd, "cm")
kontrol("blok (zincir): anahtar + boyama ORİJİNAL blok handle'ı",
        d["poligon_handle"] == "B1" and d["kullanilan_handleler"] == ["B1"] and d["alan_m2"] == 0.35,
        (d["poligon_handle"], d["kullanilan_handleler"], d["hata"]))
u = perde_zincir_uc_dus(d, ["t4"])
kontrol("blok: geçici kenar seçilince düşülür, boyama yine sadece B1",
        u["dusulen_m"] == 0.35 and u["kullanilan_handleler"] == ["B1"])
d = perde_secimi_degerlendir(blok_dikd + [acik("u1", (0, 0), (100, 0), gecici=True, blok_handle="B2"),
                                          acik("u2", (100, 0), (100, 35), gecici=True, blok_handle="B2")], "cm")
kontrol("iki blok birlikte -> hata", d["hata"] != "", d["hata"])
kapali_blok = [{"handle": "t9", "obje_tipi": "AcDbPolyline", "alan_birim": 3500.0, "kapali": True,
                "uzunluk_birim": 270.0, "koseler": [(0, 0), (100, 0), (100, 35), (0, 35)], "metin": "",
                "hata": "", "gecici": True, "blok_handle": "B3"},
               cizgi("t8", (0, 0), (0, 35), gecici=True, blok_handle="B3")]
d = perde_secimi_degerlendir(kapali_blok, "cm")
kontrol("blok içinde kapalı polyline -> BUGÜNKÜ yol, anahtar B3, blok içi çizgi uç sayılmaz",
        d["poligon_handle"] == "B3" and d["kullanilan_handleler"] == ["B3"] and d["dusulen_m"] == 0
        and not d.get("zincir"), (d["poligon_handle"], d["kullanilan_handleler"], d["dusulen_m"]))
d = perde_secimi_degerlendir(kapali_blok + [cizgi("R1", (0, 0), (0, 35))], "cm")
kontrol("blok + kullanıcının seçtiği gerçek uç çizgisi düşülür", d["dusulen_m"] == 0.35
        and d["kullanilan_handleler"] == ["B3", "R1"])

# ── 4) Kapalı polyline yolu değişmedi ──
poli = {"handle": "P1", "obje_tipi": "AcDbPolyline", "alan_birim": 10000, "kapali": True, "uzunluk_birim": 850,
        "koseler": [(0, 0), (400, 0), (400, 25), (0, 25)], "metin": "", "hata": ""}
d = perde_secimi_degerlendir([poli, cizgi("L1", (0, 0), (0, 25))], "cm")
kontrol("kapalı polyline + uç çizgisi: eski sonuç (1.0 / 8.5 / 0.25), zincir değil",
        (d["alan_m2"], d["cevre_m"], d["dusulen_m"], d["poligon_handle"]) == (1.0, 8.5, 0.25, "P1")
        and not d.get("zincir"))


# ── 5) Sahte COM: blok patlatma (iç içe) + geçici silme + bulge ──
class Ent:
    def __init__(self, tip, h, **k):
        self.ObjectName, self.Handle = tip, h
        self.silindi = False
        for a, v in k.items():
            setattr(self, a, v)

    def Explode(self):
        return tuple(self.icerik)

    def Delete(self):
        self.silindi = True

    def GetBulge(self, i):
        return (getattr(self, "bulgeler", None) or [0.0] * 10)[i]


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

        class Util:
            def Prompt(self, m):
                pass
        self.Utility = Util()


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


def pl(h, *k, bulgeler=None):
    duz = tuple(v for p in k for v in p)
    return Ent("AcDbPolyline", h, Closed=False, Length=0.0, Area=0.0, Coordinates=duz, bulgeler=bulgeler)


ic_blok = Ent("AcDbBlockReference", "IC", icerik=[pl("g3", (100, 35), (0, 35)), pl("g4", (0, 35), (0, 0))])
dis_blok = Ent("AcDbBlockReference", "BLK1", icerik=[pl("g1", (0, 0), (100, 0)), pl("g2", (100, 0), (100, 35)),
                                                   ic_blok, Ent("AcDbText", "g5", TextString="P7")])
SECIM[:] = [[dis_blok]]
r = c.perde_oku()
objeler = r["objeler"]
kontrol("COM: iç içe blok çözüldü -> 4 kenar + yazı, hepsi geçici + blok_handle BLK1",
        sorted(o["handle"] for o in objeler) == ["g1", "g2", "g3", "g4", "g5"]
        and all(o.get("gecici") and o.get("blok_handle") == "BLK1" for o in objeler))
kontrol("COM: orijinal blok SİLİNMEDİ", not dis_blok.silindi)
d = perde_secimi_degerlendir(objeler, "cm")
kontrol("COM -> değerlendirme: P7, 0.35 m², anahtar BLK1", (d["ad"], d["alan_m2"], d["poligon_handle"])
        == ("P7", 0.35, "BLK1"), (d["ad"], d["alan_m2"], d["poligon_handle"], d["hata"]))
gecici = list(c._perde_gecici)
kontrol("COM: geçici listede 4 kenar + iç blok + yazı (6)", len(gecici) == 6)
c.perde_gecici_temizle()
kontrol("COM: temizle -> tüm geçiciler silindi, liste boş", all(e.silindi for e in gecici) and not c._perde_gecici)

SECIM[:] = [[pl("b1", (0, 0), (100, 0), bulgeler=[0.4, 0.0])]]
kontrol("COM: açık polyline bulge tespit edildi", c.perde_oku()["objeler"][0]["bulge_var"])
SECIM[:] = [[Ent("AcDbLine", "U1"), Ent("AcDbLine", "U2")]]
kontrol("COM: perde_uc_sec handle listesi", c.perde_uc_sec() == ["U1", "U2"])
SECIM[:] = [[]]
kontrol("COM: perde_uc_sec boş ENTER -> []", c.perde_uc_sec() == [])


# ── 6) Panel: zincir akışı ──
class SahteConnector:
    bagli = True

    def __init__(self):
        self.okumalar, self.uclar, self.mesajlar = [], [], []
        self.boyanan, self.geri = [], []
        self.temizle_sayisi = 0

    def perde_toplu_baslat(self):
        pass

    def perde_oku(self):
        return self.okumalar.pop(0) if self.okumalar else {"durum": "bos_secim", "objeler": []}

    def perde_uc_sec(self):
        return self.uclar.pop(0) if self.uclar else []

    def perde_gecici_temizle(self):
        self.temizle_sayisi += 1

    def komut_satiri_mesaj(self, m):
        self.mesajlar.append(m)

    def komut_satiri_evet_hayir(self, istem):
        self.mesajlar.append("SORU: " + istem)
        return True

    def obje_rengi_ayarla(self, h, renk):  # Rev-160: perde rengi + önceki renk
        (self.geri if renk is None else self.boyanan).append(h)
        return None

    def obje_isaretle_hizli(self, h):
        self.boyanan.append(h)

    def obje_isaret_geri_al(self, h):
        self.geri.append(h)


def ok(*o):
    return {"durum": "okundu", "objeler": list(o)}


AYAR = KatYukseklikAyari(3.0, 0.2, "tam")
sc = SahteConnector()
p = maw.PerdeDonguPaneli(sc, "cm", "1:1", 1.0, AYAR, False, {})
sc.okumalar = [ok(*DIKD), ok(*bosluklu), ok(*DIKD), ok(*blok_dikd)]
sc.uclar = [["E4"], ["E4", "E2"], []]
p._dongu()
s = p.sonuclar()
kontrol("panel: 2 perde (dikdörtgen güncellendi + blok)", len(s) == 2, [x["poligon_handle"] for x in s])
dikd = next(x for x in s if x["poligon_handle"] == "ZINCIR:E1+E2+E3+E4")
kontrol("panel: aynı kontur tekrar -> GÜNCELLENDİ, düşüm 0.70", dikd["dusulen_m"] == 0.7
        and any("GÜNCELLENDİ" in m for m in sc.mesajlar))
kontrol("panel: boşluklu kontur ATLANDI mesajı", any("kontur kapanmıyor" in m and "ATLANDI" in m for m in sc.mesajlar))
kontrol("panel: uç istemi sadece geçerli konturda (3 kez)", not sc.uclar)
kontrol("panel: her turda geçici temizlendi (4 tur)", sc.temizle_sayisi == 4)
kontrol("panel: blok perdede sadece B1 boyandı", "B1" in sc.boyanan and not any(h.startswith("t") for h in sc.boyanan))
kontrol("panel: kenarlar bir kez boyandı", sorted(sc.boyanan) == ["B1", "E1", "E2", "E3", "E4"], sc.boyanan)
h = p._hesap(dikd)
kontrol("panel: kalıp (2.70 − 0.70) × 2.8 = 5.6", h["kalip_m2"] == 5.6, h)

print(f"\n{GECEN} PASS / {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
