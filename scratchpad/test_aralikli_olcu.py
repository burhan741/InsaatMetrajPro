"""Rev-142 — Aralıklı donatı: dağılım mesafesini AutoCAD ölçüsünden (DIMENSION) okuma.

1) Saf çekirdek olcu_mesafesi_ayikla
2) Connector aralikli_donati_olcu_sec — sahte COM
3) AralikliDonatiDonguPaneli ölçü döngüsü — sahte connector (headless)
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import autocad_connector as ac  # noqa: E402
from app.core.autocad_connector import olcu_mesafesi_ayikla, aralikli_donati_ayristir  # noqa: E402
import app.ui.metraj_analiz_window as maw  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad)


# ── 1) Saf çekirdek ──
kontrol("Measurement 400 -> 400", olcu_mesafesi_ayikla(400)["deger"] == 400)
kontrol("ölçekli çizim: 8 × DIMLFAC 50 -> görünen 400", olcu_mesafesi_ayikla(8, 50)["deger"] == 400)
kontrol("override '<> cm' -> gerçek ölçü, fark yok",
        not olcu_mesafesi_ayikla(400, 1, "<> cm")["override_farkli"])
r = olcu_mesafesi_ayikla(400, 1, "450")
kontrol("override '450' farklı -> işaretlenir", r["override_farkli"] and r["override_deger"] == 450)
kontrol("override '400' aynı -> fark yok", not olcu_mesafesi_ayikla(400, 1, "400")["override_farkli"])
kontrol("MTEXT override '{\\fArial;450}' -> 450",
        olcu_mesafesi_ayikla(400, 1, "{\\fArial|b0;450}")["override_deger"] == 450)
kontrol("override metin 'EŞİT' -> sayı yok, yok sayılır",
        olcu_mesafesi_ayikla(400, 1, "EŞİT")["override_deger"] is None)
kontrol("Measurement 0 -> hata", olcu_mesafesi_ayikla(0)["hata"] != "")
kontrol("Measurement 'abc' -> hata", olcu_mesafesi_ayikla("abc")["hata"] != "")
kontrol("ölçek None -> 1 kabul", olcu_mesafesi_ayikla(400, None)["deger"] == 400)


# ── 2) Connector — sahte COM ──
class Ent:
    def __init__(self, tip, h, olcu=None, override="", olcek=1.0, bozuk=False):
        self.ObjectName, self.Handle, self.Color, self.Layer = tip, h, 7, "OLCU"
        self._olcu, self._bozuk = olcu, bozuk
        self.TextOverride, self.LinearScaleFactor = override, olcek

    @property
    def Measurement(self):
        if self._bozuk:
            raise RuntimeError("Measurement okunamadı")
        return self._olcu


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

    def Delete(self):
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
SECIMLER = []
c._guvenli_select_on_screen = lambda ss: setattr(ss, "o", SECIMLER.pop(0))

SECIMLER[:] = [[Ent("AcDbRotatedDimension", "D1", 400)]]
r = c.aralikli_donati_olcu_sec()
kontrol("COM: RotatedDimension 400 -> bulundu", r["durum"] == "bulundu" and r["olcu"]["deger"] == 400
        and r["handle"] == "D1")
SECIMLER[:] = [[Ent("AcDbAlignedDimension", "D2", 8, olcek=50)]]
kontrol("COM: Aligned ölçekli -> 400", c.aralikli_donati_olcu_sec()["olcu"]["deger"] == 400)
SECIMLER[:] = [[Ent("AcDbLine", "L1"), Ent("AcDbRotatedDimension", "D3", 300)]]
kontrol("COM: çizgi + ölçü birlikte -> ölçü bulunur", c.aralikli_donati_olcu_sec()["handle"] == "D3")
SECIMLER[:] = [[Ent("AcDbLine", "L1")]]
r = c.aralikli_donati_olcu_sec()
kontrol("COM: sadece çizgi -> olcu_degil", r["durum"] == "olcu_degil" and "DIMENSION" in r["mesaj"])
SECIMLER[:] = [[Ent("AcDb2LineAngularDimension", "A1", 1.57)]]
r = c.aralikli_donati_olcu_sec()
kontrol("COM: açısal ölçü -> olcu_degil (açı mesajı)", r["durum"] == "olcu_degil" and "açı" in r["mesaj"])
SECIMLER[:] = [[]]
kontrol("COM: boş ENTER -> bos_secim", c.aralikli_donati_olcu_sec()["durum"] == "bos_secim")
SECIMLER[:] = [[Ent("AcDbRotatedDimension", "D4", bozuk=True)]]
kontrol("COM: Measurement hatası -> okunamadi", c.aralikli_donati_olcu_sec()["durum"] == "okunamadi")


# ── 3) Panel ──
SORULAR, CEVAPLAR, GIRIS, BIRIM_SEC = [], [], [], []
Y, N = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No


def _soru(*a, **k):
    SORULAR.append(a[1] if len(a) > 1 else "")
    return CEVAPLAR.pop(0) if CEVAPLAR else Y


QMessageBox.question = staticmethod(_soru)
for _ad in ("warning", "information", "critical"):
    setattr(QMessageBox, _ad, staticmethod(lambda *a, **k: SORULAR.append("UYARI")))
QInputDialog.getDouble = staticmethod(lambda *a, **k: (GIRIS.pop(0), True) if GIRIS else (0, False))
QInputDialog.getItem = staticmethod(lambda *a, **k: (BIRIM_SEC.pop(0), True) if BIRIM_SEC else ("cm", True))


def yazi(metin, h):
    d = aralikli_donati_ayristir(metin)
    d["handle"], d["layer"] = h, "DONATI"
    return {"durum": "bulundu", "ayrisim": d}


def olcu(h, deger, override=""):
    return {"durum": "bulundu", "handle": h, "obje_tipi": "AcDbRotatedDimension",
            "olcu": olcu_mesafesi_ayikla(deger, 1, override)}


BOS = {"durum": "bos_secim"}


class SahteConn:
    def __init__(self, yazilar, olculer, insunits="cm"):
        self.yazilar, self.olculer = list(yazilar), list(olculer)
        self.yesil, self.hizli, self.mesajlar = set(), [], []
        self.insunits = insunits

    def aralikli_donati_tek_obje_sec(self):
        return self.yazilar.pop(0)

    def aralikli_donati_olcu_sec(self):
        return self.olculer.pop(0)

    def obje_isaretle_hizli(self, h):
        self.hizli.append(h)
        self.yesil.add(h)

    def aralikli_donati_isaretle(self, h):
        self.yesil.add(h)

    def aralikli_donati_isaret_geri_al(self, h):
        self.yesil.discard(h)

    def komut_satiri_mesaj(self, m):
        self.mesajlar.append(m)

    def cizim_birimi_oku(self):
        return self.insunits


def m_var(conn, parca):
    return any(parca in m for m in conn.mesajlar)


# Senaryo A: brief — Measurement 400, aralık 20 -> 21 adet; döngü; yanlış obje; elle yedek
conn = SahteConn(
    yazilar=[yazi("Ø14/20 l=300", "T1"), yazi("Ø12/15 l=320", "T2"), yazi("Ø14/20 L=500", "T3"), BOS],
    olculer=[olcu("D1", 400),
             {"durum": "olcu_degil", "mesaj": "Seçilen nesne ölçü (DIMENSION) değil."}, olcu("D2", 300),
             BOS],
)
p = maw.AralikliDonatiDonguPaneli(conn)
kontrol("panel: varsayılan mod = ölçüden", p._olcu_modu())
SORULAR.clear()
BIRIM_SEC[:] = ["cm"]
CEVAPLAR[:] = [Y]       # ilk ölçü teyidi
GIRIS[:] = [2.0]        # T3: ölçü seçiminde boş ENTER -> elle 2 m
p._demir_sec()
s = p.sonuclar()
kontrol("A: 3 satır (boş ENTER'a kadar döngü)", len(s) == 3)
kontrol("A: BRIEF — ölçü 400 cm, aralık 20 -> 4.00 m, 21 adet",
        s[0]["mesafe_m"] == 4.0 and s[0]["adet"] == 21 and s[0]["mesafe_kaynagi"] == "ölçü")
kontrol("A: Ø14/20 l=300 × 21 -> 76.10 kg", abs(s[0]["toplam_agirlik_kg"] - 76.104) < 0.01)
kontrol("A: ilk ölçüde birim teyidi soruldu (1 kez)", SORULAR.count("İlk Ölçü — Birim Teyidi") == 1)
kontrol("A: yanlış obje -> uyar + tekrar iste -> 300 cm -> 3 m, 21 adet (300/15+1)",
        s[1]["mesafe_m"] == 3.0 and s[1]["adet"] == 21 and m_var(conn, "değil. Tekrar seçin"))
kontrol("A: ölçüde boş ENTER -> elle yedek 2 m, 11 adet",
        s[2]["mesafe_m"] == 2.0 and s[2]["adet"] == 11 and s[2]["mesafe_kaynagi"] == "elle")
kontrol("A: yazı + ölçü yeşil (T1,D1,T2,D2,T3)", conn.yesil == {"T1", "D1", "T2", "D2", "T3"})
kontrol("A: ölçü döngüsünde hızlı boyama (Regen'siz)", set(conn.hizli) == {"T1", "D1", "T2", "D2", "T3"})
kontrol("A: komut satırı EKLENDİ mesajı", m_var(conn, "EKLENDİ: mesafe 4.00 m (ölçü) -> 21 adet"))
kontrol("A: döngü sonunda bitti mesajı", m_var(conn, "döngü bitti — 3 donatı"))
kontrol("A: tablo 9 sütun, kaynak sütunu dolu",
        p.table.columnCount() == 9 and p.table.item(0, 8).text() == "ölçü")

# Undo: T3 (elle) geri al -> T3 rengi gider; T2+D2 geri al -> ikisi gider
p._son_ekleneni_geri_al()
p._son_ekleneni_geri_al()
kontrol("undo: donatı + ölçü yeşili geri alındı", conn.yesil == {"T1", "D1"} and len(p.sonuclar()) == 1)

# Senaryo B: aynı ölçü iki ilavede ortak; birini geri alınca ölçü yeşil KALIR
conn = SahteConn(yazilar=[yazi("Ø14/20 l=300", "T1"), yazi("Ø12/20 l=300", "T2"), BOS],
                 olculer=[olcu("D9", 400), olcu("D9", 400)])
p = maw.AralikliDonatiDonguPaneli(conn)
BIRIM_SEC[:] = ["cm"]
CEVAPLAR[:] = [Y]
p._demir_sec()
p._son_ekleneni_geri_al()
kontrol("B: ortak ölçü, bir satır geri alındı -> ölçü hâlâ yeşil", "D9" in conn.yesil and "T2" not in conn.yesil)
p._son_ekleneni_geri_al()
kontrol("B: son kullanan da gidince ölçü rengi geri", "D9" not in conn.yesil)

# Senaryo C: mükerrer yazı -> güncelle (ayrı satır YOK), eski ölçü rengi geri
conn = SahteConn(yazilar=[yazi("Ø14/20 l=300", "T1"), yazi("Ø14/20 l=300", "T1"), BOS],
                 olculer=[olcu("D1", 400), olcu("D2", 600)])
p = maw.AralikliDonatiDonguPaneli(conn)
BIRIM_SEC[:] = ["cm"]
CEVAPLAR[:] = [Y, Y]     # teyit, "güncellensin mi"
p._demir_sec()
s = p.sonuclar()
kontrol("C: mükerrer -> 1 satır, güncellendi (6 m -> 31 adet)", len(s) == 1 and s[0]["adet"] == 31)
kontrol("C: eski ölçü D1 rengi geri, yeni D2 yeşil", "D1" not in conn.yesil and "D2" in conn.yesil)
kontrol("C: komut satırı GÜNCELLENDİ", m_var(conn, "GÜNCELLENDİ"))

# Senaryo D: mm birim (INSUNITS) 4000 -> 4 m; override farklı -> yazı değeri seçilebilir
conn = SahteConn(yazilar=[yazi("Ø14/20 l=300", "T1"), yazi("Ø14/20 l=300", "T2"), BOS],
                 olculer=[olcu("D1", 4000), olcu("D2", 4000, override="5000")], insunits="mm")
p = maw.AralikliDonatiDonguPaneli(conn)
BIRIM_SEC[:] = ["mm"]
SORULAR.clear()
CEVAPLAR[:] = [Y, Y]      # teyit, override'daki 5000 kullanılsın
p._demir_sec()
s = p.sonuclar()
kontrol("D: mm 4000 -> 4 m, 21 adet", s[0]["mesafe_m"] == 4.0 and s[0]["adet"] == 21)
kontrol("D: override farklı -> soruldu, 5000 mm -> 5 m, 26 adet",
        "Ölçü Yazısı Değiştirilmiş" in SORULAR and s[1]["mesafe_m"] == 5.0 and s[1]["adet"] == 26)

# Senaryo E: teyitte Hayır -> birim yeniden seçilir (m sanıldı, aslında cm)
conn = SahteConn(yazilar=[yazi("Ø14/20 l=300", "T1"), BOS], olculer=[olcu("D1", 400)])
p = maw.AralikliDonatiDonguPaneli(conn)
BIRIM_SEC[:] = ["m", "cm"]  # başta m (yanlış), teyitte Hayır -> cm
CEVAPLAR[:] = [N]
p._demir_sec()
kontrol("E: teyit Hayır -> cm'ye düzeltildi, 4 m / 21 adet", p.sonuclar()[0]["adet"] == 21)

# Senaryo F: yedek güvenlik — birim teyidi atlatılsa bile 50 m üstü sorulur
conn = SahteConn(yazilar=[yazi("Ø14/20 l=300", "T1"), BOS], olculer=[olcu("D1", 400)])
p = maw.AralikliDonatiDonguPaneli(conn)
p._olcu_birim_teyitli = True   # teyit zaten yapılmış varsay
BIRIM_SEC[:] = ["m"]
SORULAR.clear()
CEVAPLAR[:] = [Y]
p._olcu_birimi = "m"
p._demir_sec()
kontrol("F: 400 m -> 50 m uyarısı -> 4 m", "Mesafe Birimi" in SORULAR and p.sonuclar()[0]["mesafe_m"] == 4.0)

# Senaryo G: İptal -> tüm yazı + ölçü renkleri geri
conn = SahteConn(yazilar=[yazi("Ø14/20 l=300", "T1"), yazi("Ø12/15 l=320", "T2"), BOS],
                 olculer=[olcu("D1", 400), olcu("D2", 300)])
p = maw.AralikliDonatiDonguPaneli(conn)
BIRIM_SEC[:] = ["cm"]
CEVAPLAR[:] = [Y]
p._demir_sec()
CEVAPLAR[:] = [Y]
p._iptal()
kontrol("G: iptal -> hiç yeşil kalmadı", conn.yesil == set())

# Senaryo H: ELLE mod bozulmadı (tek tur, soru getDouble, komut satırı yok)
conn = SahteConn(yazilar=[yazi("Ø14/20 l=300", "T1")], olculer=[])
p = maw.AralikliDonatiDonguPaneli(conn)
p.mod_combo.setCurrentText(p.MOD_ELLE)
GIRIS[:] = [4.0]
p._demir_sec()
s = p.sonuclar()
kontrol("H: elle mod 4 m -> 21 adet, kaynak elle, ölçü seçilmedi",
        len(s) == 1 and s[0]["adet"] == 21 and s[0]["mesafe_kaynagi"] == "elle" and not conn.mesajlar)
kontrol("H: elle modda birim combo pasif", not p.birim_combo.isEnabled())

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
