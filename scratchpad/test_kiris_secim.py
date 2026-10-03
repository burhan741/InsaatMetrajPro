"""Rev-150 Aşama 2 — Kiriş AutoCAD seçimi: saf karar + sahte COM okuma + panel + ana tablo."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
MESAJ = []
for _ad in ("warning", "information", "critical"):
    setattr(QMessageBox, _ad, staticmethod(lambda *a, _ad=_ad, **k: MESAJ.append((_ad, a[2]))))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

import app.ui.metraj_analiz_window as maw  # noqa: E402
from app.core.autocad_connector import (  # noqa: E402
    AcadColor, AutoCADConnector, kiris_mukerrer_bul, kiris_secim_degerlendir, kiris_yazisi_ayristir,
)

maw.QTimer.singleShot = staticmethod(lambda *a, **k: None)
GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"  [{detay}]" if detay else ""))


# ── 1. Yazı ayrıştırma ──
for metin, beklenen in (("K101 (25/50)", ("K101", 25, 50)), ("K 101(25/50)", ("K 101", 25, 50)),
                        ("K101 25/50", ("K101", 25, 50)), ("KB-12 ( 30 / 60 )", ("KB-12", 30, 60)),
                        ("\\A1;{\\fArial;K7 (20/45)}", ("K7", 20, 45)), ("SBH-1 (20/165)", ("SBH-1", 20, 165))):
    a = kiris_yazisi_ayristir(metin)
    kontrol(f"ayrıştır {metin!r}", a["kesitli"] and (a["ad"], a["b_cm"], a["h_cm"]) == beklenen,
            (a["ad"], a["b_cm"], a["h_cm"]))
a = kiris_yazisi_ayristir("K105")
kontrol("kesitsiz yazı -> ad K105, kesitli=False", a["ad"] == "K105" and not a["kesitli"] and not a["hata"])
kontrol("0/50 -> hata", bool(kiris_yazisi_ayristir("K1 (0/50)")["hata"]))


# ── 2. Seçim değerlendirme ──
def cizgi(h, uz, x0=0.0, y=0.0):
    return {"handle": h, "uzunluk_birim": uz, "bas": (x0, y), "son": (x0 + uz, y), "hata": ""}


def okuma(yazilar, cizgiler):
    return {"yazilar": [{"handle": f"Y{i}", "metin": m} for i, m in enumerate(yazilar)], "cizgiler": cizgiler}


d = kiris_secim_degerlendir(okuma(["K101 (25/50)"], [cizgi("C1", 404), cizgi("C2", 400, y=25)]), "cm")
kontrol("404/400 cm -> L1 4.00 (kısa), L2 4.04", d["gecerli"] and (d["l1_m"], d["l2_m"]) == (4.0, 4.04),
        (d["l1_m"], d["l2_m"]))
kontrol("handle'lar", d["yazi_handle"] == "Y0" and d["cizgi_handleler"] == ["C1", "C2"])
d = kiris_secim_degerlendir(okuma(["K1 (25/50)"], [cizgi("A", 200), cizgi("B", 200, x0=200),
                                                 cizgi("C", 400, y=25)]), "cm")
kontrol("bölünmüş kenar (200+200) / 400 -> 4.00 / 4.00", d["gecerli"] and (d["l1_m"], d["l2_m"]) == (4.0, 4.0))
d = kiris_secim_degerlendir(okuma(["K1 (25/50)"], [cizgi("A", 150, y=25), cizgi("B", 100)]), "cm")
kontrol("yamuk 100/150 -> L1 1.00, L2 1.50, soru yok", d["gecerli"] and (d["l1_m"], d["l2_m"]) == (1.0, 1.5))
d = kiris_secim_degerlendir(okuma(["K1 (25/50)"], [cizgi("A", 4000), cizgi("B", 4000, y=250)]), "mm")
kontrol("mm birim 4000 -> 4.00", (d["l1_m"], d["l2_m"]) == (4.0, 4.0))
d = kiris_secim_degerlendir(okuma(["K1 (25/50)"], [cizgi("A", 8), cizgi("B", 8, y=0.5)]), "cm", 50)
kontrol("1:50 cm çizim 8 (b=0.5 birim) -> 4.00 / 4.00", d["gecerli"] and (d["l1_m"], d["l2_m"]) == (4.0, 4.0),
        d["hata"])
d = kiris_secim_degerlendir(okuma(["K1 (25/50)"], [cizgi("A", 400), cizgi("B", 400, y=25),
                                                 cizgi("C", 400, y=50)]), "cm")
kontrol("üç ayrı kenar -> hata", not d["gecerli"] and "3 ayrı kenar" in d["hata"], d["hata"])
dik = {"handle": "U", "uzunluk_birim": 25, "bas": (0.0, 0.0), "son": (0.0, 25.0), "hata": ""}
d = kiris_secim_degerlendir(okuma(["K1 (25/50)"], [cizgi("A", 400), dik]), "cm")
kontrol("kenar + dik uç çizgisi -> paralel değil hatası", not d["gecerli"] and "paralel değil" in d["hata"])
kors = [{"handle": h, "uzunluk_birim": u, "hata": ""} for h, u in (("A", 400), ("B", 404))]
d = kiris_secim_degerlendir(okuma(["K1 (25/50)"], kors), "cm")
kontrol("koordinatsız 2 çizgi -> her biri bir kenar", d["gecerli"] and (d["l1_m"], d["l2_m"]) == (4.0, 4.04))
d = kiris_secim_degerlendir(okuma(["K1 (25/50)"], kors + [{"handle": "C", "uzunluk_birim": 5, "hata": ""}]), "cm")
kontrol("koordinatsız 3 çizgi -> hata", not d["gecerli"] and "koordinat" in d["hata"])
d = kiris_secim_degerlendir(okuma(["K1 (25/50)"], [cizgi("A", 400)]), "cm")
kontrol("tek çizgi -> hata", not d["gecerli"] and "en az 2" in d["hata"])
d = kiris_secim_degerlendir(okuma(["K1 (25/50)"], [cizgi("A", 400), cizgi("B", 400)]), "cm")
kontrol("üst üste çift çizgi tekilleşir -> tek çizgi hatası", not d["gecerli"] and "tekilleştirildi" in d["notlar"][0])
d = kiris_secim_degerlendir(okuma(["K1 (25/50)", "K2 (25/50)"], [cizgi("A", 400), cizgi("B", 400, y=25)]), "cm")
kontrol("iki etiket -> hata", not d["gecerli"] and "Birden fazla" in d["hata"])
d = kiris_secim_degerlendir(okuma([], [cizgi("A", 400), cizgi("B", 400, y=25)]), "cm")
kontrol("yazısız -> hata", not d["gecerli"] and "seçilmedi" in d["hata"])
d = kiris_secim_degerlendir(okuma(["K105"], [cizgi("A", 400), cizgi("B", 400, y=25)]), "cm")
kontrol("kesitsiz yazı -> kesit_elle", d["gecerli"] and d["kesit_elle"] and d["ad"] == "K105")
d = kiris_secim_degerlendir(okuma(["K1 (25/50)", "not"], [cizgi("A", 400), cizgi("B", 400, y=25)]), "cm")
kontrol("kesitli + ilgisiz yazı -> kesitli alınır", d["gecerli"] and d["ad"] == "K1" and not d["kesit_elle"])

kayit = [{"ad": "K1", "handleler": ["Y1", "C1", "C2"]}, {"ad": "K2", "handleler": ["Y2", "C3", "C4"]}]
kontrol("mükerrer: çizgi eşleşmesi", kiris_mukerrer_bul(kayit, ["YX", "C2", "C9"])["index"] == 0)
kontrol("mükerrer yok (aynı ad farklı handle)", kiris_mukerrer_bul(kayit, ["Y9", "C8", "C9"])["index"] is None)
kontrol("iki kayıtla çakışma -> hata", bool(kiris_mukerrer_bul(kayit, ["C1", "C3"])["hata"]))


# ── 3. Sahte COM: connector.kiris_oku ──
class SahteEnt:
    def __init__(self, tip, handle, uz=0.0, metin="", y=0.0):
        self.ObjectName, self.Handle, self.Length, self.metin, self.y = tip, handle, uz, metin, y
        self.StartPoint, self.EndPoint = (0.0, 0.0, 0.0), (uz, 0.0, 0.0)


class SahteSS:
    def __init__(self, objeler):
        self.objeler = objeler

    @property
    def Count(self):
        return len(self.objeler)

    def Item(self, i):
        return self.objeler[i]

    def Clear(self):
        pass


con = AutoCADConnector()
con.selection_set = SahteSS([SahteEnt("AcDbMText", "Y1", metin="K101 (25/50)"),
                             SahteEnt("AcDbLine", "C1", 400), SahteEnt("AcDbPolyline", "C2", 404, y=25),
                             SahteEnt("AcDbCircle", "Z1")])
con._guvenli_select_on_screen = lambda ss: None
con._read_entity_props = lambda e: {"handle": e.Handle, "text": e.metin, "layer": "0"}
con._tk_cizgi_uclari = lambda e, t: ((0.0, e.y), (e.Length, e.y))
o = con.kiris_oku()
kontrol("kiris_oku: 1 yazı, 2 çizgi, 1 diğer", (len(o["yazilar"]), len(o["cizgiler"]), o["diger_sayisi"]) == (1, 2, 1))
d = kiris_secim_degerlendir(o, "cm")
kontrol("kiris_oku -> değerlendirme L1 4.00 / L2 4.04", (d["l1_m"], d["l2_m"]) == (4.0, 4.04))
con.selection_set = SahteSS([])
kontrol("boş ENTER -> bos_secim", con.kiris_oku()["durum"] == "bos_secim")


# ── 4. Panel (sahte connector) ──
class SahteConnector:
    bagli = True

    def __init__(self):
        self.kuyruk, self.cevaplar, self.sayilar = [], [], []
        self.mesajlar, self.renk, self.orijinal = [], {}, {}

    def kiris_toplu_baslat(self):
        pass

    def kiris_oku(self):
        return self.kuyruk.pop(0) if self.kuyruk else {"durum": "bos_secim"}

    def komut_satiri_mesaj(self, m):
        self.mesajlar.append(m)

    def komut_satiri_evet_hayir(self, istem, varsayilan=None):
        self.mesajlar.append("SORU " + istem)
        return self.cevaplar.pop(0) if self.cevaplar else True

    def komut_satiri_sayi_sor(self, istem):
        return self.sayilar.pop(0) if self.sayilar else None

    def obje_renklendir_hizli(self, h, renk):
        self.orijinal.setdefault(h, 7)
        self.renk[h] = int(renk)

    def obje_isaret_geri_al(self, h):
        if h in self.orijinal:
            self.renk[h] = self.orijinal.pop(h)


def secim(yazi, h1, h2, yh, uz1=400, uz2=400):
    r = okuma([yazi], [cizgi(h1, uz1), cizgi(h2, uz2, y=25)])
    r["yazilar"][0]["handle"] = yh
    r["durum"] = "okundu"
    return r


YESIL, MAVI = int(AcadColor.ORANGE), int(AcadColor.BLUE)  # iç kiriş artık turuncu
sc = SahteConnector()
p = maw.KirisDonguPaneli(sc, "cm", "1:1", 1.0, 12.0, "İç", False, [], None)
sc.kuyruk = [secim("K101 (25/50)", "C1", "C2", "Y1"), secim("K102 (25/50)", "C3", "C4", "Y2")]
p._dongu()
kontrol("mod mesajı İÇ", any("İÇ KİRİŞ modu" in m for m in sc.mesajlar))
kontrol("ilk kirişte teyit sorusu (1 kez)", sum("LIST ile kontrol" in m for m in sc.mesajlar) == 1 and p.teyitli)
kontrol("2 iç kiriş, L1/L2 4.00, beton 0.500, kalıp 4.04", len(p.kayitlar) == 2
        and p.table.item(0, 3).text() == "4.00" and p.table.item(0, 4).text() == "4.00"
        and p.table.item(0, 7).text() == "0.5" and p.table.item(0, 8).text() == "4.0")
kontrol("iç -> yeşil", all(sc.renk[h] == YESIL for h in ("Y1", "C1", "C2", "Y2")))
kontrol("kaynak Çizim + handle'lar", p.kayitlar[0]["kaynak"] == "Çizim" and p.kayitlar[0]["handleler"] == ["Y1", "C1", "C2"])

sc.kuyruk = [secim("K201 (25/50)", "C5", "C6", "Y3")]
p._dongu("Kenar")
kontrol("mod mesajı KENAR + tablo birikti (3)", any("KENAR KİRİŞ modu" in m for m in sc.mesajlar) and len(p.kayitlar) == 3)
kontrol("kenar kalıp 4.52 (= iç + t×L 0.48), mavi", p.table.item(2, 8).text() == "4.5" and sc.renk["C5"] == MAVI)
kontrol("teyit tekrar sorulmadı", sum("LIST ile kontrol" in m for m in sc.mesajlar) == 1)

# Aynı kiriş aynı modda (Kenar) -> güncelleme sorusu
sc.kuyruk = [secim("K201 (25/50)", "C5", "C6", "Y3", 500, 500)]
p._dongu("Kenar")
kontrol("aynı mod: 'zaten K201 olarak kayıtlı'", any("zaten K201 olarak kayıtlı" in m for m in sc.mesajlar))
kontrol("güncellendi, yeni satır yok, L1 5.00", len(p.kayitlar) == 3 and p.kayitlar[2]["l1_m"] == 5.0)

# İç kirişi Kenar modunda seç -> tip değiştirme sorusu, E
sc.kuyruk = [secim("K101 (25/50)", "C1", "C2", "Y1")]
p._dongu("Kenar")
kontrol("diğer mod sorusu 'İÇ olarak kayıtlı. KENAR'", any("K101 İÇ olarak kayıtlı. KENAR olarak" in m for m in sc.mesajlar))
kontrol("E -> tip Kenar, satır sayısı aynı, mavi", p.kayitlar[0]["tip"] == "Kenar" and len(p.kayitlar) == 3
        and sc.renk["C1"] == MAVI)
# H cevabı -> değişmez
sc.kuyruk, sc.cevaplar = [secim("K102 (25/50)", "C3", "C4", "Y2")], [False]
p._dongu("Kenar")
kontrol("H -> K102 İç kaldı, yeşil", p.kayitlar[1]["tip"] == "İç" and sc.renk["C3"] == YESIL)

# Uyarı senaryoları
n = len(p.kayitlar)
sc.kuyruk = [{"durum": "okundu", **okuma(["K9 (25/50)", "K8 (25/50)"], [cizgi("D1", 400), cizgi("D2", 400, y=25)])},
             {"durum": "okundu", **okuma(["K9 (25/50)"], [cizgi("D1", 400)])}]
p._dongu("İç")
kontrol("iki etiket / tek çizgi -> uyarı, alınmadı", len(p.kayitlar) == n
        and sum("ALINMADI" in m for m in sc.mesajlar[-4:]) == 2 and "D1" not in sc.renk)
# Yamuk (100/150): soru SORULMAZ, U2 değerleri
soru_once = sum(m.startswith("SORU") for m in sc.mesajlar)
sc.kuyruk = [secim("K9 (25/50)", "D1", "D2", "Y9", 150, 100)]
p._dongu("İç")
kontrol("yamuk: soru yok, L1 1.00 / L2 1.50, kalıp 1.26 (1.2625)",
        sum(m.startswith("SORU") for m in sc.mesajlar) == soru_once
        and (p.kayitlar[-1]["l1_m"], p.kayitlar[-1]["l2_m"]) == (1.0, 1.5)
        and p.table.item(len(p.kayitlar) - 1, 8).text() == "1.3")
p._son_ekleneni_geri_al()
kontrol("yamuk geri alındı", len(p.kayitlar) == n and sc.renk["D1"] == 7)
# Kesitsiz yazı -> b/h sorulur
sc.kuyruk, sc.sayilar = [secim("K30", "E1", "E2", "Y30")], [30.0, 60.0]
p._dongu("İç")
kontrol("kesitsiz yazı -> elle 30/60 eklendi", p.kayitlar[-1]["ad"] == "K30" and p.kayitlar[-1]["h_cm"] == 60.0)

# Geri al: son ekleme (K30) -> satır silinir, renk geri
p._son_ekleneni_geri_al()
kontrol("geri al ekleme -> satır yok, renk orijinal", p.kayitlar[-1]["ad"] != "K30" and sc.renk["E1"] == 7)
# Geri al: K101 tip güncellemesi -> İç, yeşil
p._son_ekleneni_geri_al()
kontrol("geri al güncelleme -> K101 İç + yeşil", p.kayitlar[0]["tip"] == "İç" and sc.renk["C1"] == YESIL)

# İptal (reject) -> tüm eylemler geri
p.reject()
kontrol("iptal -> tüm renkler orijinal", all(v == 7 for v in sc.renk.values()) and not p.kayitlar)

# İlk teyit reddi -> döngü durur
sc2 = SahteConnector()
p2 = maw.KirisDonguPaneli(sc2, "cm", "1:1", 1.0, 12.0, "İç", False, [], None)
sc2.kuyruk, sc2.cevaplar = [secim("K1 (25/50)", "C1", "C2", "Y1"), secim("K2 (25/50)", "C3", "C4", "Y2")], [False]
p2._dongu()
kontrol("ilk teyit Hayır -> döngü DURDU, satır yok", not p2.kayitlar and len(sc2.kuyruk) == 1
        and any("DURDURULDU" in m for m in sc2.mesajlar))

# ── 5. Ana pencere: panel sonucu + tablodan tip değişimi rengi günceller ──
win = maw.MetrajAnalizWindow()
sc3 = SahteConnector()
win.acad_connector = sc3
ORJ_EXEC = maw.KirisDonguPaneli.exec


def sahte_exec(self):
    self.connector.kuyruk = [secim("K101 (25/50)", "C1", "C2", "Y1")]
    self._dongu()
    return maw.QDialog.DialogCode.Accepted


maw.KirisDonguPaneli.exec = sahte_exec
win._kiris_sec("İç")
kontrol("ana tablo: 1 satır, Kaynak Çizim, Handle'lar", win.kiris_table.rowCount() == 1
        and win.kiris_table.item(0, 10).text() == "Çizim" and win.kiris_table.item(0, 11).text() == "Y1, C1, C2")
kontrol("teyit bayrağı pencereye taşındı", win._kiris_teyitli)
win.kiris_table.item(0, maw.MetrajAnalizWindow.KIRIS_TIP_KOL).setText("Kenar")
kontrol("tablodan tip Kenar -> kalıp 4.52 + mavi", win.kiris_table.item(0, 9).text() == "4.5" and sc3.renk["C1"] == MAVI)
win.kiris_olcek_combo.setCurrentText("1:50")
kontrol("ölçek değişince teyit sıfırlanır", not win._kiris_teyitli)
win.kiris_table.selectRow(0)
win._kiris_sil()
kontrol("satır silinince renk orijinal", sc3.renk["C1"] == 7 and not win.kiris_kayitlari)
maw.KirisDonguPaneli.exec = ORJ_EXEC

print(f"\n{GECEN} PASS / {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
