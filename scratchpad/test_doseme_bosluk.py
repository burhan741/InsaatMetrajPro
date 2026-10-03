"""Rev-149 Aşama 3 — Döşeme boşluk düşme.

1) PROGRAMSIZ saf hesap (koordinatlardan): 6×5 döşeme + 2×2.5 boşluk, h=15 -> T3 ile aynı sonuç
2) Doğrulama: taşan / L iç köşesinden taşan / çakışan / brüt'ü aşan boşluk reddedilir
3) Döngü paneli (sahte connector): soru, kırmızı çizim, geri al, güncelleme, iptal
4) Evet/Hayır <Hayir> varsayılanı (sahte COM)
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QUANTIX_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from app.core import autocad_connector as ac  # noqa: E402
from app.core.autocad_connector import bosluk_degerlendir, doseme_hesapla, doseme_poligon_degerlendir  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"   [{detay}]" if detay else ""))


def dik(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


# ── 1) Programsız: koordinatlardan T3 ──
DOS = dik(0, 0, 600, 500)                       # cm: 6×5 m
d = doseme_poligon_degerlendir(DOS, "cm")
b = bosluk_degerlendir(DOS, dik(100, 100, 300, 350), [], "cm", 1.0, d["alan_m2"])   # 2×2.5 m
h = doseme_hesapla(d["alan_m2"], 15, b["alan_m2"], b["cevre_m"])
kontrol("koordinat: brüt 30, boşluk 5, boşluk çevresi 9", d["alan_m2"] == 30 and b["alan_m2"] == 5
        and b["cevre_m"] == 9 and not b["hata"])
kontrol("T3 koordinattan: net 25, beton 3.75, kenar 1.35, toplam kalıp 26.35",
        h["net_alan_m2"] == 25 and h["beton_m3"] == 3.75 and h["kenar_kalip_m2"] == 1.35
        and h["toplam_kalip_m2"] == 26.35,
        f"net {h['net_alan_m2']}, beton {h['beton_m3']}, kenar {h['kenar_kalip_m2']}, toplam {h['toplam_kalip_m2']}")
b50 = bosluk_degerlendir([(x / 50 * 10, y / 50 * 10) for x, y in DOS],
                         [(x / 50 * 10, y / 50 * 10) for x, y in dik(100, 100, 300, 350)], [], "mm", 50)
kontrol("1/50 mm çizimde aynı boşluk 5 m², çevre 9 m", b50["alan_m2"] == 5 and b50["cevre_m"] == 9, str(b50))

# ── 2) Reddedilenler ──
kontrol("kısmen dışarı taşan boşluk -> reddedilir",
        "İÇİNDE değil" in bosluk_degerlendir(DOS, dik(500, 100, 700, 300), [], "cm")["hata"])
L = [(0, 0), (600, 0), (600, 300), (300, 300), (300, 500), (0, 500)]
kontrol("L iç köşesinden taşan (köşeler içeride, kenar dışarıda) -> reddedilir",
        "İÇİNDE değil" in bosluk_degerlendir(L, [(250, 250), (550, 250), (550, 280), (250, 450)], [], "cm")["hata"])
kontrol("L içinde düzgün boşluk -> kabul", bosluk_degerlendir(L, dik(50, 50, 250, 250), [], "cm")["alan_m2"] == 4)
mevcut = [dik(100, 100, 300, 350)]
kontrol("mevcut boşlukla çakışan -> reddedilir",
        "çakışıyor" in bosluk_degerlendir(DOS, dik(200, 200, 400, 400), mevcut, "cm")["hata"])
kontrol("mevcut boşluğun İÇİNE çizilen -> reddedilir",
        "çakışıyor" in bosluk_degerlendir(DOS, dik(150, 150, 200, 200), mevcut, "cm")["hata"])
kontrol("mevcut boşluğu SARAN -> reddedilir",
        "çakışıyor" in bosluk_degerlendir(DOS, dik(50, 50, 350, 400), mevcut, "cm")["hata"])
kontrol("ayrı ikinci boşluk -> kabul (1×1)",
        bosluk_degerlendir(DOS, dik(400, 100, 500, 200), mevcut, "cm", 1.0, 30)["alan_m2"] == 1)
kontrol("toplam boşluk brüt'ü aşarsa -> reddedilir",
        "geçemez" in bosluk_degerlendir(DOS, dik(400, 100, 500, 200), mevcut, "cm", 1.0, 5.5)["hata"])
kontrol("kendini kesen boşluk -> reddedilir",
        "kendini kesiyor" in bosluk_degerlendir(DOS, [(100, 100), (200, 200), (200, 100), (100, 200)], [], "cm")["hata"])
kontrol("döşeme poligonu yok (elle satır) -> hata", "Döşeme poligonu yok" in bosluk_degerlendir([], dik(1, 1, 2, 2), [], "cm")["hata"])

# ── 3) Döngü paneli ──
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
import app.ui.metraj_analiz_window as maw  # noqa: E402
maw.QTimer.singleShot = staticmethod(lambda *a, **k: None)


class Sahte:
    bagli = True

    def __init__(self):
        self.noktalar, self.cevaplar, self.mesajlar, self.cizilen, self.silinen = [], [], [], [], []
        self.istemler = []
        self._n = 0

    def komut_satiri_mesaj(self, m):
        self.mesajlar.append(m)

    def doseme_toplu_baslat(self):
        pass

    def doseme_toplu_bitir(self):
        return ""

    def doseme_nokta_al(self, istem, baz=None, anahtarlar=""):
        self.istemler.append((istem, anahtarlar))
        return self.noktalar.pop(0) if self.noktalar else ("enter", None)

    def komut_satiri_evet_hayir(self, istem, varsayilan=None):
        self.mesajlar.append("SORU: " + istem)
        return self.cevaplar.pop(0) if self.cevaplar else bool(varsayilan)

    def doseme_poligon_ciz(self, koseler, renk=None):
        self._n += 1
        h = f"H{self._n}"
        self.cizilen.append((h, renk))
        return h

    def obje_sil(self, h):
        self.silinen.append(h)
        return True


E = ("enter", None)


def N(x, y):
    return ("nokta", (x, y))


def tik(x1, y1, x2, y2):
    return [N(x1, y1), N(x2, y1), N(x2, y2), N(x1, y2), E]


B = ("metin", "Bosluk")   # AutoCAD anahtar kelimesi: kullanıcı "B" yazar, GetInput "Bosluk" döner

# B önce döşeme yokken -> uyarı, hiçbir şey olmaz
sc = Sahte()
p = maw.DosemeDonguPaneli(sc, "cm", "1:1", 1.0, 15.0, True, [])
sc.noktalar = [B, E]
p._dongu()
kontrol("B (döşeme yok) -> 'Önce bir döşeme tıklayın', eylem yok",
        any("Önce bir döşeme" in m for m in sc.mesajlar) and not p._eylemler)
kontrol("1. köşe istemi [Bosluk] anahtarlı", "[Bosluk]" in sc.istemler[0][0] and sc.istemler[0][1] == "Bosluk")

# T3 — yol 1 (AutoCAD B): sadece D1 + B + 2×2.5 boşluk
sc = Sahte()
p = maw.DosemeDonguPaneli(sc, "cm", "1:1", 1.0, 15.0, True, [])
sc.noktalar = tik(0, 0, 600, 500) + [B] + tik(100, 100, 300, 350) + [E]
p._dongu()
h1 = p._hesap(p.kayitlar[0])
kontrol("SORU YOK: hiç Evet/Hayır sorulmadı", not any(m.startswith("SORU") for m in sc.mesajlar))
kontrol("T3 yol 1 (B): net 25, beton 3.75, toplam kalıp 26.35",
        h1["net_alan_m2"] == 25 and h1["beton_m3"] == 3.75 and h1["toplam_kalip_m2"] == 26.35, str(h1))

# Küçük harf "b" de çalışır; 1. köşede ENTER boşluktan vazgeçer, döngü devam eder
sc = Sahte()
p = maw.DosemeDonguPaneli(sc, "cm", "1:1", 1.0, 15.0, True, [])
sc.noktalar = tik(0, 0, 600, 500) + [("metin", "b"), E] + [E]
p._dongu()
kontrol("'b' + 1. köşede ENTER -> boşluk yok, D1 duruyor, döngü normal bitti",
        len(p.kayitlar) == 1 and not p.kayitlar[0]["bosluklar"] and len(p._eylemler) == 1)

# Arka arkaya B: taşan (red) + 5 m² + 1 m²; sonra D2 ve B -> D2'ye bağlanır
sc = Sahte()
p = maw.DosemeDonguPaneli(sc, "cm", "1:1", 1.0, 15.0, True, [])
sc.noktalar = (tik(0, 0, 600, 500)              # D1
               + [B] + tik(500, 100, 700, 300)  # taşan -> reddedilir
               + [B] + tik(100, 100, 300, 350)  # 5 m²
               + [B] + tik(400, 100, 500, 200)  # 1 m²
               + tik(1000, 0, 1400, 400)        # D2 4×4
               + [B] + tik(1100, 100, 1200, 200)  # D2'ye 1 m²
               + [E])
p._dongu()
s = p.kayitlar[0]
kontrol("panel: taşan boşluk ALINMADI", any("İÇİNDE değil" in m for m in sc.mesajlar))
kontrol("panel: B son döşemeye bağlandı (D2'de 1 boşluk, 1 m²)",
        len(p.kayitlar[1]["bosluklar"]) == 1 and p.kayitlar[1]["bosluk_alan_m2"] == 1)
p._son_ekleneni_geri_al()   # D2 boşluğu
p._son_ekleneni_geri_al()   # D2
kontrol("panel: 2 boşluk bağlandı, toplam 6 m², çevre 9+4 = 13 m",
        len(s["bosluklar"]) == 2 and s["bosluk_alan_m2"] == 6 and s["bosluk_cevre_m"] == 13)
kontrol("panel: boşluklar KIRMIZI (1), döşeme macenta (renk=None -> DOSEME_RENK)",
        [r for _, r in sc.cizilen[:3]] == [None, 1, 1])
kontrol("geri al sonrası B hedefi D1'e döner", p._son_doseme_idx() == 0)
hh = p._hesap(s)
kontrol("panel: net 24, beton 3.60, kenar 13×0.15 = 1.95, toplam kalıp 25.95",
        hh["net_alan_m2"] == 24 and hh["beton_m3"] == 3.6 and hh["kenar_kalip_m2"] == 1.95
        and hh["toplam_kalip_m2"] == 25.95)
kontrol("panel tablosu boşluk sütunu 6.00", p.table.item(0, 2).text() == "6.00")
p._son_ekleneni_geri_al()
kontrol("geri al #1: son boşluk (H3) silindi, toplam 5 m²", "H3" in sc.silinen and s["bosluk_alan_m2"] == 5)
p._son_ekleneni_geri_al()
p._son_ekleneni_geri_al()
kontrol("geri al #3: satır + poligon gitti", not p.kayitlar and "H1" in sc.silinen)

# Güncelleme: eski boşluklar kaldırılır; geri alınca eski satır + boşlukları yeniden çizilir
sc = Sahte()
p = maw.DosemeDonguPaneli(sc, "cm", "1:1", 1.0, 15.0, True, [])
sc.noktalar = tik(0, 0, 600, 500) + [B] + tik(100, 100, 300, 350) + tik(10, 10, 590, 490) + [E]
#            D1  B (boşluk)  | güncelle? E
sc.cevaplar = [True]
p._dongu()
s = p.kayitlar[0]
kontrol("güncelleme: eski döşeme + eski boşluk silindi, yeni satırda boşluk yok",
        {"H1", "H2"} <= set(sc.silinen) and s["bosluklar"] == [] and s["bosluk_alan_m2"] == 0)
kontrol("güncelleme mesajı: eski boşluklar kaldırıldı", any("eski boşluklar kaldırıldı" in m for m in sc.mesajlar))
p._son_ekleneni_geri_al()
s = p.kayitlar[0]
kontrol("güncellemeyi geri al: eski satır boşluğuyla geri geldi, ikisi yeniden çizildi",
        s["brut_alan_m2"] == 30 and s["bosluk_alan_m2"] == 5 and s["handle"] == "H4"
        and s["bosluklar"][0]["handle"] == "H5" and sc.cizilen[-1][1] == 1)

# Önceki oturum satırı + iptal: pencere listesi bozulmaz
onceki = [dict(p.kayitlar[0])]
onceki[0]["bosluklar"] = [dict(x) for x in p.kayitlar[0]["bosluklar"]]
sc = Sahte()
p2 = maw.DosemeDonguPaneli(sc, "cm", "1:1", 1.0, 15.0, True, onceki)
sc.noktalar = [E]
p2._dongu()
p2.kayitlar[0]["bosluklar"].append({"x": 1})
kontrol("çalışma kopyası DERİN: panelde boşluk eklemek pencere satırını değiştirmez",
        len(onceki[0]["bosluklar"]) == 1)

# ── 4) Pencere: satır silinince boşluk poligonları da silinir ──
win = maw.MetrajAnalizWindow()
sc = Sahte()
win.acad_connector = sc
win.doseme_kayitlari = [{"ad": "D1", "brut_alan_m2": 30, "bosluk_alan_m2": 5, "bosluk_cevre_m": 9,
                         "serbest_kenar_m": 0, "kalinlik_cm": 15, "kaynak": "Tıklama", "handle": "A",
                         "koseler": DOS, "bosluklar": [{"handle": "B", "koseler": [], "alan_m2": 5, "cevre_m": 9}]}]
win._doseme_tablo_yenile()
kontrol("pencere tablosu: boşluk 5.00, net 25.00, toplam kalıp 26.35",
        win.doseme_table.item(0, 3).text() == "5.00" and win.doseme_table.item(0, 4).text() == "25.00"
        and win.doseme_table.item(0, 9).text() == "26.4")
win.doseme_table.selectRow(0)
win._doseme_sil()
kontrol("pencere: satır silinince döşeme (A) + boşluk (B) poligonu silindi", {"A", "B"} <= set(sc.silinen))

# T3 — yol 2 (formdan "Boşluk Ekle"): tıklanmış D1 (boşluksuz) seçili -> AutoCAD'de 2×2.5 boşluk
maw.DosemeDonguPaneli.exec = lambda self: (self._dongu(), self.accept(), self.result())[2]
sc = Sahte()
win.acad_connector = sc
win.doseme_birim_combo.setCurrentText("cm")
win.doseme_olcek_combo.setCurrentText("1:1")
win.doseme_kayitlari = [{"ad": "D1", "brut_alan_m2": 30, "bosluk_alan_m2": 0, "bosluk_cevre_m": 0,
                         "serbest_kenar_m": 0, "kalinlik_cm": 15, "kaynak": "Tıklama", "handle": "A",
                         "koseler": DOS, "cevre_m": 22, "bosluklar": []},
                        {"ad": "D2", "brut_alan_m2": 12, "bosluk_alan_m2": 0, "bosluk_cevre_m": 0,
                         "serbest_kenar_m": 0, "kalinlik_cm": 15, "kaynak": "Elle", "handle": ""}]
win._doseme_tablo_yenile()
win.doseme_table.selectRow(0)
sc.noktalar = tik(500, 100, 700, 300) + tik(100, 100, 300, 350) + [E]   # taşan red + T3 boşluk
win._doseme_bosluk_ekle()
h2 = win._doseme_satir_hesap(win.doseme_kayitlari[0])
kontrol("T3 yol 2 (form): net 25, beton 3.75, toplam kalıp 26.35 — yol 1 ile aynı",
        h2["net_alan_m2"] == h1["net_alan_m2"] == 25 and h2["beton_m3"] == h1["beton_m3"] == 3.75
        and h2["toplam_kalip_m2"] == h1["toplam_kalip_m2"] == 26.35, str(h2))
kontrol("form yolu: taşan boşluk reddedildi, boşluk KIRMIZI çizildi, soru yok",
        any("İÇİNDE değil" in m for m in sc.mesajlar) and sc.cizilen == [("H1", 1)]
        and not any(m.startswith("SORU") for m in sc.mesajlar))
kontrol("form tablosu: net 25.00, toplam kalıp 26.35",
        win.doseme_table.item(0, 4).text() == "25.00" and win.doseme_table.item(0, 9).text() == "26.4")
# İptal: hiçbir şey değişmez, çizilen boşluk silinir
maw.DosemeDonguPaneli.exec = lambda self: (self._dongu(), self.reject(), self.result())[2]
sc.noktalar = tik(400, 100, 500, 200) + [E]
win.doseme_table.selectRow(0)
win._doseme_bosluk_ekle()
kontrol("form yolu iptal: satır değişmedi (1 boşluk), çizilen boşluk silindi",
        len(win.doseme_kayitlari[0]["bosluklar"]) == 1 and "H2" in sc.silinen)
# Elle satır -> uyarı, AutoCAD'e gidilmez
uyarilar = []
QMessageBox.warning = staticmethod(lambda *a, **k: uyarilar.append(a[2]))
n = len(sc.istemler)
win.doseme_table.selectRow(1)
win._doseme_bosluk_ekle()
kontrol("elle satır seçiliyken uyarı, AutoCAD'e geçilmedi", uyarilar and "elle girilmiş" in uyarilar[-1]
        and len(sc.istemler) == n)
win.doseme_table.clearSelection()
win.doseme_table.setCurrentCell(-1, -1)
win._doseme_bosluk_ekle()
kontrol("seçim yokken uyarı", "seçin" in uyarilar[-1])


# ── 5) Evet/Hayır <Hayir> varsayılanı — sahte COM ──
import pywintypes  # noqa: E402


class U:
    def __init__(self):
        self.k, self.son_istem, self.bit = [], "", None

    def InitializeUserInput(self, bit, kw):
        self.bit = bit

    def GetKeyword(self, istem):
        self.son_istem = istem
        x = self.k.pop(0)
        if isinstance(x, Exception):
            raise x
        return x


class D:
    def __init__(self):
        self.Utility = U()


c = ac.AutoCADConnector.__new__(ac.AutoCADConnector)
c._bagli, c.acad_app, c.aktif_cizim = True, object(), D()
u = c.aktif_cizim.Utility
u.k = [""]
kontrol("varsayılan Hayır: boş ENTER -> False, istemde <Hayir>, boş girdiye izin (bit 0)",
        c.komut_satiri_evet_hayir("Boşluk ekle?", varsayilan=False) is False and "<Hayir>" in u.son_istem
        and u.bit == 0)
u.k = ["Evet"]
kontrol("varsayılan Hayır: 'Evet' -> True", c.komut_satiri_evet_hayir("?", varsayilan=False) is True)
u.k = [pywintypes.com_error(-2145320928, "keyword", None, None)]
kontrol("boş ENTER hata koduyla gelirse -> varsayılan", c.komut_satiri_evet_hayir("?", varsayilan=False) is False)
u.k = [pywintypes.com_error(-2147352567, "esc", None, None)]
kontrol("ESC -> False", c.komut_satiri_evet_hayir("?", varsayilan=True) is False)
u.k = ["Evet"]
kontrol("varsayılansız (perde) davranışı aynı: cevap zorunlu (bit 1)",
        c.komut_satiri_evet_hayir("?") is True and u.bit == 1 and "<" not in u.son_istem)


# ── 6) Connector: GetPoint'te "Bosluk" anahtar kelimesi (sahte COM) ──
class U2:
    def __init__(self):
        self.kw, self.girdi = None, ""

    def InitializeUserInput(self, bit, kw):
        self.kw = (bit, kw)

    def Prompt(self, m):
        pass

    def GetPoint(self, *a):
        raise pywintypes.com_error(-2145320928, "keyword", None, None)

    def GetInput(self):
        return self.girdi


c.aktif_cizim.Utility = U2()
c.aktif_cizim.Utility.girdi = "Bosluk"
kontrol("connector: anahtarlı GetPoint -> InitializeUserInput(128,'Bosluk'), sonuç ('metin','Bosluk')",
        c.doseme_nokta_al("x", None, anahtarlar="Bosluk") == ("metin", "Bosluk")
        and c.aktif_cizim.Utility.kw == (128, "Bosluk"))
c.aktif_cizim.Utility.girdi = ""
kontrol("connector: anahtarsız boş ENTER yine 'enter', anahtar listesi boş",
        c.doseme_nokta_al("x") == ("enter", None) and c.aktif_cizim.Utility.kw == (128, ""))

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
