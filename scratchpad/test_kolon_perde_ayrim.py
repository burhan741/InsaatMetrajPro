"""Rev-160 — Kolon aracında Kolon/Perde ayrımı (oran >= 6), Tip sütunu, okunamayanlar,
kolon + perde ORTAK ad havuzu, tipe göre renk ve renk geçmişi (geri al / iptal).

1) Programsız: S259 (210/30) H=3 -> Perde, 1.890 m³, 14.40 m²; SZ07 (50/50) Kolon (sonuç
   değişmedi); S300 (120/30) Kolon; sınıflandırma (donatı yazıları yok sayılır, S260 okunamadı)
2) Connector obje_rengi_ayarla (sahte COM): önceki program rengi döner, None -> orijinal
3) Kolon aracı (sahte connector): renkler, Tip sütunu, mükerrer sorusu, Hayır'da renk değişmez,
   Vazgeç'te renkler geri, kat özeti Kolon / Perde satırları
4) Perde aracı: S260 alınınca okunamayanlardan düşer, kırmızı -> camgöbeği; geri al -> kırmızı;
   kolon aracında kayıtlı S259 perde aracında -> soru
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QUANTIX_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from app.core import autocad_connector as ac  # noqa: E402
from app.core.autocad_connector import (  # noqa: E402
    kolon_perde_hesapla, eleman_tipi_belirle, kolon_secimi_siniflandir, perde_secimi_degerlendir,
)

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"   [{detay}]" if detay else ""))


# ── 1) Programsız ──
h = kolon_perde_hesapla(210, 30, 3.0)
kontrol("S259 (210/30) H=3.00 -> Perde, beton 1.890, kalıp 14.40",
        h["tip"] == "Perde" and h["beton_m3"] == 1.89 and h["kalip_m2"] == 14.4, str(h))
h = kolon_perde_hesapla(210, 30, 3.0, "Perde", 0.20, "tam")
kontrol("Rev-161: S259 perde, kat 3.00, döşeme 0.20, tam -> beton 1.890, kalıp 4.80×2.80 = 13.44",
        h["beton_m3"] == 1.89 and h["kalip_m2"] == 13.44, str(h))
h = kolon_perde_hesapla(210, 30, 3.0, "Perde", 0.20, "net")
kontrol("Rev-161: esas net -> beton 0.63×2.80 = 1.764, kalıp 13.44", h["beton_m3"] == 1.764 and h["kalip_m2"] == 13.44)
p = ac.perde_hesapla(0.63, 4.8, 3.0, 0.20, "tam", 0.0)
kontrol("Rev-161: Perde sekmesiyle birebir aynı (perde_hesapla 0.63 m², 4.80 m)",
        (p["beton_m3"], p["kalip_m2"]) == (1.89, 13.44), str((p["beton_m3"], p["kalip_m2"])))
h = kolon_perde_hesapla(50, 50, 3.0)
kontrol("SZ07 (50/50) H=3.00 -> Kolon, beton 0.750, kalıp 6.00 (eski formülle aynı)",
        h["tip"] == "Kolon" and h["beton_m3"] == 0.75 and h["kalip_m2"] == 6.0, str(h))
h = kolon_perde_hesapla(50, 50, 3.0, "Kolon", 0.20)
kontrol("Rev-161: kolon döşemeden ETKİLENMEZ (tam kat) -> 0.75 / 6.00", h["kalip_m2"] == 6.0 and h["beton_m3"] == 0.75)
kontrol("S300 (120/30) oran 4 -> Kolon", eleman_tipi_belirle(120, 30) == "Kolon")
kontrol("tam 6 (180/30) -> Perde; 30/180 sırası önemsiz", eleman_tipi_belirle(180, 30) == "Perde"
        and eleman_tipi_belirle(30, 180) == "Perde")
kontrol("5.99 oran (179.7/30) -> Kolon", eleman_tipi_belirle(179.7, 30) == "Kolon")

YAZILAR = [
    {"metin": "S259 (210/30)", "handle": "Y1"}, {"metin": "SZ07 (50/50)", "handle": "Y2"},
    {"metin": "S300 (120/30)", "handle": "Y3"}, {"metin": "S260", "handle": "Y4"},
    {"metin": "6%%c16", "handle": "D1"}, {"metin": "Etr. Ø10/20/[20]", "handle": "D2"},
    {"metin": "6Ø16", "handle": "D3"}, {"metin": "K101 (25/50)", "handle": "K1"},
    {"metin": "SBH-1", "handle": "D4"}, {"metin": "{\\C1;S261}", "handle": "Y5"},
]
s = kolon_secimi_siniflandir(YAZILAR)
tipler = {k["ad"]: k["eleman_tipi"] for k in s["kolonlar"]}
kontrol("sınıflandırma: S259 Perde, SZ07 Kolon, S300 Kolon",
        tipler == {"S259": "Perde", "SZ07": "Kolon", "S300": "Kolon"}, str(tipler))
kontrol("boyutsuz S260 + MTEXT S261 -> okunamayanlar",
        [o["ad"] for o in s["okunamayanlar"]] == ["S260", "S261"], str(s["okunamayanlar"]))
kontrol("donatı yazıları (6Ø16, Etr. Ø10/20/[20], %%c) + SBH-1 hatasız yok sayıldı",
        s["ilgisiz_sayisi"] == 4 and not s["basarisizlar"], str(s["ilgisiz_sayisi"]))
kontrol("kiriş K101 atlandı", [k["ad"] for k in s["kirisler_atlanan"]] == ["K101"])
kontrol("özet: '2 kolon, 1 perde' + okunamadı", "2 kolon, 1 perde" in s["ozet"] and "okunamadı" in s["ozet"],
        s["ozet"])

# Perde aracı ad yazısı: donatı yazısı da seçime girse S/P adı seçilir
KOSE = [(0, 0), (400, 0), (400, 25), (0, 25)]


def poli(h="P1"):
    return {"handle": h, "obje_tipi": "AcDbPolyline", "alan_birim": 10000, "kapali": True,
            "uzunluk_birim": 850, "koseler": KOSE, "metin": "", "hata": ""}


def yazi(metin, h):
    return {"handle": h, "obje_tipi": "AcDbText", "alan_birim": 0.0, "kapali": False,
            "uzunluk_birim": 0.0, "koseler": [], "metin": metin, "hata": ""}


d = perde_secimi_degerlendir([poli(), yazi("S260", "Y4"), yazi("6Ø16", "D3")], "cm")
kontrol("perde: ad yazısı + donatı yazısı -> ad S260, yazı handle'ı boyanacaklarda, donatı değil",
        d["ad"] == "S260" and "Y4" in d["kullanilan_handleler"] and "D3" not in d["kullanilan_handleler"],
        str((d["ad"], d["kullanilan_handleler"])))
d = perde_secimi_degerlendir([poli(), yazi("S259 (210/30)", "Y1")], "cm")
kontrol("perde: boyutlu yazı seçilse de ad 'S259' (havuz anahtarı)", d["ad"] == "S259")

# ── 2) Connector obje_rengi_ayarla — sahte COM ──


class Ent:
    def __init__(self, h, renk):
        self.Handle, self.Color, self.Layer, self.guncelleme = h, renk, "0", 0

    def Update(self):
        self.guncelleme += 1


class Lay:
    Lock = False


class Doc:
    def __init__(self):
        self.ent = {"Y4": Ent("Y4", 256)}
        self.Layers = type("L", (), {"Item": staticmethod(lambda ad: Lay())})()

    def HandleToObject(self, h):
        return self.ent[h]


c = ac.AutoCADConnector.__new__(ac.AutoCADConnector)
c._bagli, c.acad_app, c.aktif_cizim = True, object(), Doc()
c._orijinal_renkler, c._metraj_alinan_objeler = {}, []
e = c.aktif_cizim.ent["Y4"]
r1 = c.obje_rengi_ayarla("Y4", 1)
r2 = c.obje_rengi_ayarla("Y4", 4)
kontrol("connector: kırmızı (önceki None) -> camgöbeği (önceki 1)", r1 is None and r2 == 1 and e.Color == 4)
c.obje_rengi_ayarla("Y4", r2)
kontrol("connector: geri al -> kırmızıya döndü (orijinale değil)", e.Color == 1)
c.obje_rengi_ayarla("Y4", None)
kontrol("connector: None -> orijinal (ByLayer 256), Regen yok, Update var", e.Color == 256 and e.guncelleme >= 4)

# ── 3) Kolon aracı ──
from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
MESAJ, SORULAR = [], []
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, _ad=ad, **k: MESAJ.append((_ad, a[2]))))
CEVAP = [QMessageBox.StandardButton.Yes]


def soru(*a, **k):
    SORULAR.append(a[2])
    return CEVAP[0]


QMessageBox.question = staticmethod(soru)
import app.ui.metraj_analiz_window as maw  # noqa: E402

maw.QTimer.singleShot = staticmethod(lambda *a, **k: None)
DIALOG = {"sonuc": QDialog.DialogCode.Accepted, "eylem": None}


def dialog_exec(self):
    if DIALOG["eylem"]:
        DIALOG["eylem"](self)
    return DIALOG["sonuc"]


QDialog.exec = dialog_exec


class Sahte:
    bagli = True

    def __init__(self):
        self.yazilar, self.renk, self.cagri, self.okumalar, self.mesajlar, self.cevaplar = [], {}, [], [], [], []

    def get_kolon_beton_yazidan(self, mesaj=""):
        s = kolon_secimi_siniflandir(self.yazilar)
        s.update(secim_sayisi=len(self.yazilar), metin_sayisi=len(self.yazilar))
        return s

    def obje_rengi_ayarla(self, h, renk):
        onceki = self.renk.get(h)
        if renk is None:
            self.renk.pop(h, None)
        else:
            self.renk[h] = renk
        self.cagri.append((h, renk))
        return onceki

    # perde aracı
    def perde_toplu_baslat(self):
        pass

    def perde_oku(self):
        return self.okumalar.pop(0) if self.okumalar else {"durum": "bos_secim", "objeler": []}

    def komut_satiri_mesaj(self, m):
        self.mesajlar.append(m)

    def komut_satiri_evet_hayir(self, istem, varsayilan=None):
        self.mesajlar.append("SORU: " + istem)
        return self.cevaplar.pop(0) if self.cevaplar else True

    def obje_isaret_geri_al(self, h):
        self.renk.pop(h, None)

    def cizim_birimi_oku(self):
        return "cm"


win = maw.MetrajAnalizWindow()
win.perde_doseme_otomatik_chk.setChecked(False)  # Rev-163: bu test döşemeyi ELLE giriyor
sc = Sahte()
win.acad_connector = sc
win.demir_kat_input.setText("Zemin")
win._demir_kat_ekle()
win.kat_yuksekligi_spin.setValue(300)
win.perde_yukseklik_spin.setValue(3.0)
win.perde_doseme_spin.setValue(0.20)
win.perde_esas_combo.setCurrentIndex(win.perde_esas_combo.findData("tam"))
sc.yazilar = YAZILAR
win._beton_kalip_kolon_yazisindan_oku()
kayit = {ad: v for (k, ad), v in win.beton_kalip_kolon_kayitlari.items()}
kontrol("registry: S259 Perde 1.890 / 13.44 (net kalıp), SZ07 Kolon 0.75/6.00 (tam kat), S300 Kolon",
        kayit["S259"]["tip"] == "Perde" and kayit["S259"]["beton"] == 1.89 and kayit["S259"]["kalip"] == 13.44
        and kayit["SZ07"]["tip"] == "Kolon" and kayit["SZ07"]["beton"] == 0.75 and kayit["SZ07"]["kalip"] == 6.0
        and kayit["S300"]["tip"] == "Kolon", str(kayit["S259"]))
t = win.beton_kalip_table
perde_satir = [r for r in range(t.rowCount()) if t.item(r, 1) and t.item(r, 1).text() == "Perde"]
kontrol("Beton & Kalıp tablosunda perde satırı: beton 1.890, kalıp 13.440, H 3.00",
        perde_satir and t.item(perde_satir[0], 6).text() == "1.9" and t.item(perde_satir[0], 9).text() == "13.4"
        and t.item(perde_satir[0], 5).text() == "3.00")
oz = {k["eleman"]: k for k in win._kat_ozeti_kalemleri() if k["kat"] == "Zemin"}
kontrol("Kat Özeti perde kalemi 13.44 m² kalıp", abs(oz["Perde"]["kalip_m2"] - 13.44) < 1e-9)
# Perde sekmesinde döşeme 0.25 yapılınca kolon aracından gelen perde de güncellenir, kolon değişmez
win.perde_doseme_spin.setValue(0.25)
oz = {(k["eleman"], round(k["kalip_m2"], 4)) for k in win._kat_ozeti_kalemleri() if k["kat"] == "Zemin"}
kontrol("döşeme 0.25 -> perde kalıbı 4.80×2.75 = 13.20, kolonlar 6.00 / 4.50 aynı",
        ("Perde", 13.2) in oz and ("Kolon", 6.0) in oz and abs(float(t.item(perde_satir[0], 9).text()) - 13.2) < 1e-9,
        str(oz))
win.perde_doseme_spin.setValue(0.20)
kontrol("renkler: S259 camgöbeği 4, SZ07/S300 yeşil 3, S260/S261 kırmızı 1",
        sc.renk == {"Y1": 4, "Y2": 3, "Y3": 3, "Y4": 1, "Y5": 1}, str(sc.renk))
kontrol("donatı ve kiriş yazıları boyanmadı", not {"D1", "D2", "D3", "D4", "K1"} & set(sc.renk))
kontrol("okunamayanlar kayıtlı: S260, S261", set(win.okunamayan_elemanlar) == {("Zemin", "S260"), ("Zemin", "S261")})
kontrol("mesajda 'Şu elemanlar okunamadı, perde aracıyla alın: S260, S261'",
        any("perde aracıyla alın: S260, S261" in m for _, m in MESAJ))
t = win.beton_kalip_table
elemanlar = sorted((t.item(r, 1).text(), t.item(r, 2).text()) for r in range(t.rowCount()) if t.item(r, 0))
kontrol("Beton & Kalıp tablosu: Kolon ve Perde ayrı satır", ("Perde", "1") in elemanlar
        and ("Kolon", "1") in elemanlar and len(elemanlar) == 3, str(elemanlar))
oz = {(k["eleman"]) for k in win._kat_ozeti_kalemleri() if k["kat"] == "Zemin"}
kontrol("kat özeti kalemleri: Kolon + Perde", {"Kolon", "Perde"} <= oz, str(oz))

# Tip elle değişir -> renk güncellenir (S300'ü Perde yap)


def tip_degistir(dlg):
    win._kolon_tip_combolari[0].setCurrentText("Perde")   # tek satır: S300


SORULAR.clear()
sc.yazilar = [{"metin": "S300 (120/30)", "handle": "Y3"}]
DIALOG["eylem"] = tip_degistir
win._beton_kalip_kolon_yazisindan_oku()
DIALOG["eylem"] = None
kontrol("aynı ad tekrar okununca soru: 'S300 bu katta zaten kayıtlı. Güncellensin mi?'",
        SORULAR == ["S300 bu katta zaten kayıtlı. Güncellensin mi?"], str(SORULAR))
kontrol("Tip elle Perde yapıldı -> kayıt Perde, renk camgöbeği",
        win.beton_kalip_kolon_kayitlari[("Zemin", "S300")]["tip"] == "Perde" and sc.renk["Y3"] == 4)

# S259 iki kez (farklı pafta, farklı handle) -> soru; Hayır -> renk değişmez, kayıt aynı
SORULAR.clear()
CEVAP[0] = QMessageBox.StandardButton.No
n_cagri = len(sc.cagri)
sc.yazilar = [{"metin": "S259 (210/30)", "handle": "Y9"}]
eski = dict(win.beton_kalip_kolon_kayitlari[("Zemin", "S259")])
win._beton_kalip_kolon_yazisindan_oku()
kontrol("farklı handle'lı S259 -> güncelleme sorusu", SORULAR == ["S259 bu katta zaten kayıtlı. Güncellensin mi?"])
kontrol("Hayır -> Y9 boyanmadı, kayıt (handle Y1) değişmedi",
        len(sc.cagri) == n_cagri and "Y9" not in sc.renk
        and win.beton_kalip_kolon_kayitlari[("Zemin", "S259")] == eski)

# Vazgeç -> bu okumada boyananlar bir önceki hâline döner
CEVAP[0] = QMessageBox.StandardButton.Yes
DIALOG["sonuc"] = QDialog.DialogCode.Rejected
sc.yazilar = [{"metin": "S259 (210/30)", "handle": "Y1"}, {"metin": "S400 (40/40)", "handle": "Y8"},
              {"metin": "S262", "handle": "Y7"}]
win._beton_kalip_kolon_yazisindan_oku()
DIALOG["sonuc"] = QDialog.DialogCode.Accepted
kontrol("Vazgeç: S259 camgöbeğinde kaldı (önceki hâli), S400/S262 boyanmamış hâle döndü, kayıt yok",
        sc.renk.get("Y1") == 4 and "Y8" not in sc.renk and "Y7" not in sc.renk
        and ("Zemin", "S400") not in win.beton_kalip_kolon_kayitlari
        and ("Zemin", "S262") not in win.okunamayan_elemanlar, str(sc.renk))

# ── 4) Perde aracı: S260 ──


def perde_exec(self):
    self._dongu()
    self._bitti()
    return self.result()


maw.PerdeDonguPaneli.exec = perde_exec
win.perde_yukseklik_spin.setValue(3.0)
win.perde_doseme_spin.setValue(0.2)
n_soru = sum(m.startswith("SORU") and "kayıtlı" in m for m in sc.mesajlar)
sc.okumalar = [{"durum": "okundu", "objeler": [poli("P1"), yazi("S260", "Y4"), yazi("6Ø16", "D3")]}]
PANEL = {}
_eski_init = maw.PerdeDonguPaneli.__init__


def init_yakala(self, *a, **k):
    _eski_init(self, *a, **k)
    PANEL["p"] = self


maw.PerdeDonguPaneli.__init__ = init_yakala
win._perde_sec()
p = PANEL["p"]
kontrol("perde aracı: S260 kaydedildi (ad S260), soru yok (kayıtlı değildi)",
        [s["ad"] for s in win.perde_kayitlari.values()] == ["S260"]
        and sum(m.startswith("SORU") and "kayıtlı" in m for m in sc.mesajlar) == n_soru)
kontrol("S260 okunamayanlar listesinden düştü", ("Zemin", "S260") not in win.okunamayan_elemanlar
        and ("Zemin", "S261") in win.okunamayan_elemanlar)
kontrol("kesit (P1) + ad yazısı (Y4) camgöbeği, donatı yazısı boyanmadı",
        sc.renk.get("P1") == 4 and sc.renk.get("Y4") == 4 and "D3" not in sc.renk)
kontrol("panel bilgisinde okunamayanlar listelendi", "S260" in p.findChildren(maw.QLabel)[0].text())

# Geri al (yeni oturum) -> kırmızıya döner
sc.okumalar = [{"durum": "okundu", "objeler": [poli("P5"), yazi("S261", "Y5")]}]
maw.PerdeDonguPaneli.exec = lambda self: (self._dongu(), self._son_ekleneni_geri_al(), self.reject(),
                                          self.result())[3]
win._perde_sec()
kontrol("Son Ekleneni Geri Al: S261 yazısı KIRMIZIYA döndü, kesit orijinale",
        sc.renk.get("Y5") == 1 and "P5" not in sc.renk and ("Zemin", "S261") in win.okunamayan_elemanlar)
# İptal de aynı
sc.okumalar = [{"durum": "okundu", "objeler": [poli("P6"), yazi("S261", "Y5")]}]
maw.PerdeDonguPaneli.exec = lambda self: (self._dongu(), self._iptal(), self.result())[2]
win._perde_sec()
kontrol("İptal: S261 kırmızıya, kesit orijinale döndü", sc.renk.get("Y5") == 1 and "P6" not in sc.renk)

# Kolon aracında kayıtlı S259'u perde aracında al -> soru; Hayır -> renk değişmez
sc.cevaplar = [False]
sc.okumalar = [{"durum": "okundu", "objeler": [poli("P7"), yazi("S259", "Y6")]}]
maw.PerdeDonguPaneli.exec = perde_exec
win._perde_sec()
kontrol("perde aracı: kolon aracındaki S259 -> 'S259 bu katta zaten kayıtlı. Güncellensin mi?'",
        any("S259 bu katta zaten kayıtlı" in m for m in sc.mesajlar))
kontrol("Hayır -> P7/Y6 boyanmadı, S259 kolon kaydında kaldı",
        "P7" not in sc.renk and "Y6" not in sc.renk and ("Zemin", "S259") in win.beton_kalip_kolon_kayitlari)
# Evet -> perde kaydına devredilir, kolon kaydı silinir (çift sayım yok)
sc.cevaplar = [True]
sc.okumalar = [{"durum": "okundu", "objeler": [poli("P7"), yazi("S259", "Y6")]}]
win._perde_sec()
kontrol("Evet -> S259 perde aracına devredildi, kolon kaydı silindi (tek kayıt)",
        ("Zemin", "S259") not in win.beton_kalip_kolon_kayitlari
        and sum(s["ad"] == "S259" for s in win.perde_kayitlari.values()) == 1 and sc.renk.get("P7") == 4)
# Kolon aracında S260 tekrar okunursa (perde aracında kayıtlı) -> soru
SORULAR.clear()
sc.yazilar = [{"metin": "S260", "handle": "Y4"}]
win._beton_kalip_kolon_yazisindan_oku()
kontrol("perde aracında kayıtlı S260 kolon aracında tekrar okunamadı listesine girmez, kırmızı olmaz",
        ("Zemin", "S260") not in win.okunamayan_elemanlar and sc.renk.get("Y4") == 4)

# ── 5) Rev-162: Esc / X perdeleri sessizce atmasın ──
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402


def esc_exec(self):
    self._dongu()
    QTest.keyClick(self, Qt.Key.Key_Escape)
    return self.result()


maw.PerdeDonguPaneli.exec = esc_exec
for cevap, beklenen, ad in ((QMessageBox.StandardButton.Yes, True, "Evet"),
                            (QMessageBox.StandardButton.No, False, "Hayır")):
    CEVAP[0] = cevap
    SORULAR.clear()
    h = f"PE{ad}"
    sc.okumalar = [{"durum": "okundu", "objeler": [poli(h)]}]
    win._perde_sec()
    kayitli = ("Zemin", h) in win.perde_kayitlari
    kontrol(f"Esc + '{ad}' -> soru soruldu, kayıt {'EKLENDİ' if beklenen else 'eklenmedi'}"
            + ("" if beklenen else ", renk geri alındı"),
            any("henüz tabloya EKLENMEDİ" in s_ for s_ in SORULAR) and kayitli == beklenen
            and (beklenen or h not in sc.renk))
oz = [k for k in win._kat_ozeti_kalemleri() if k["eleman"] == "Perde"]
kontrol("Esc + Evet ile alınan perde Kat Özeti'nde", len(oz) == sum(1 for a in win.perde_kayitlari) + sum(
    1 for v in win.beton_kalip_kolon_kayitlari.values() if v.get("tip") == "Perde"))
# Vazgeç -> panel açık kalır (reject edilmez), sonra TAMAMLANDI
CEVAP[0] = QMessageBox.StandardButton.Cancel
sc.okumalar = [{"durum": "okundu", "objeler": [poli("PEV")]}]
maw.PerdeDonguPaneli.exec = lambda self: (self._dongu(), QTest.keyClick(self, Qt.Key.Key_Escape),
                                          self._bitti(), self.result())[3]
win._perde_sec()
kontrol("Esc + 'Vazgeç' -> pencere açık kaldı, ardından TAMAMLANDI ile kaydedildi",
        ("Zemin", "PEV") in win.perde_kayitlari)
CEVAP[0] = QMessageBox.StandardButton.Yes

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
