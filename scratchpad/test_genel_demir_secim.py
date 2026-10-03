"""Rev-140 — Genel demir metrajı (get_rebar_report_from_selection) sahte COM uçtan uca.

Neyi çözüyoruz? Teşhis print'leri temizlendikten sonra: (1) metin + blok
yolu aynı sonucu üretiyor mu, (2) konsolda DEBUG listesi / obje başına
teşhis satırı kalmadı mı, (3) kullanıcı özeti ve hata sinyali duruyor mu.
"""
import io
import logging
import sys
from contextlib import redirect_stdout

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")
from app.core import autocad_connector as ac  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad)


class Ent:
    def __init__(self, ad, h, metin=None, blok=None):
        self.ObjectName = ad
        self.Handle = h
        self.Color = 7
        self.Layer = "DONATI"
        if metin is not None:
            self.TextString = metin
        if blok is not None:
            self.Name = blok


class SS:
    def __init__(self, objeler):
        self.o = objeler
        self.Count = len(objeler)

    def Item(self, i):
        return self.o[i]

    def Clear(self):
        pass

    def Delete(self):
        pass


class Katmanlar:
    def Item(self, ad):
        class K:
            Lock = False
        return K()


class Doc:
    def __init__(self, objeler):
        self.ss = SS(objeler)
        self.Layers = Katmanlar()
        doc = self

        class Setler:
            def Item(self, ad):
                raise KeyError(ad)

            def Add(self, ad):
                return doc.ss
        self.SelectionSets = Setler()

    def HandleToObject(self, h):
        return next(o for o in self.ss.o if o.Handle == h)

    def Regen(self, x):
        pass


objeler = [
    Ent("AcDbText", "T1", metin="10Ø12 L=250"),
    Ent("AcDbMText", "T2", metin="2x8Ø12 L=420"),
    Ent("AcDbText", "T3", metin="KOLON AKS A"),
    Ent("AcDbBlockReference", "B1", blok="DEMIR_POZ"),
    Ent("AcDbBlockReference", "B2", blok="BOZUK_POZ"),
]
BLOK_ATTR = {
    "B1": {"ADET": "5", "CAP": "16", "BOY": "300"},
    "B2": {"NOT": "yazı"},
}

c = ac.AutoCADConnector.__new__(ac.AutoCADConnector)
c._orijinal_renkler = {}
c._bagli = True
c.acad_app = object()
c.aktif_cizim = Doc(objeler)
c.selection_set = None
c._autocad_one_getir = lambda *a, **k: None
c._guvenli_select_on_screen = lambda ss: None
c._blok_attributes_oku = lambda ent: BLOK_ATTR.get(ent.Handle, {})

kayit = []


class H(logging.Handler):
    def emit(self, r):
        kayit.append((r.levelno, r.getMessage()))


ac.logger.addHandler(H())
ac.logger.setLevel(logging.DEBUG)

buf = io.StringIO()
with redirect_stdout(buf):
    sonuc = c.get_rebar_report_from_selection(birim="cm")
konsol = buf.getvalue()

adetler = sorted(d.adet for d in sonuc["basarili"])
kontrol("3 geçerli demir (2 metin + 1 blok)", len(sonuc["basarili"]) == 3)
kontrol("adetler 5/10/16 (2x8 çarpanı dahil)", adetler == [5, 10, 16])
kontrol("2 format dışı (metin + bozuk blok)", len(sonuc["basarisiz"]) == 2)
kontrol("toplam adet 31", sonuc["toplam_adet"] == 31)
kontrol("toplam ağırlık > 0", sonuc["toplam_agirlik_kg"] > 0)
kontrol("geçerliler YEŞİL", all(o.Color == int(ac.AcadColor.GREEN) for o in objeler if o.Handle in ("T1", "T2", "B1")))
kontrol("format dışılar KIRMIZI", all(o.Color == int(ac.AcadColor.RED) for o in objeler if o.Handle in ("T3", "B2")))

kontrol("konsolda '(DEBUG)' yok", "DEBUG" not in konsol)
kontrol("konsolda seçilen metin listesi yok", "SEÇİLEN METİNLER" not in konsol)
kontrol("konsolda obje başına BLOK/Blok OK/Faz2 yok",
        not any(s in konsol for s in ("BLOK [", "Blok OK", "Faz2", "Blok parse edilemedi")))
kontrol("kullanıcı özeti: 'N metin objesi bulundu' duruyor", "3 metin objesi bulundu" in konsol)
kontrol("kullanıcı özeti: DEMİR METRAJ RAPORU duruyor", "DEMİR METRAJ RAPORU" in konsol)
kontrol("kullanıcı özeti: Geçerli demir sayısı", "Geçerli demir : 3 adet" in konsol)
kontrol("kullanıcı özeti: FORMAT DIŞI listesi duruyor", "FORMAT DIŞI METİNLER" in konsol)
kontrol("bozuk blok WARNING logunda", any(lv == logging.WARNING and "Blok parse edilemedi [BOZUK_POZ]" in m
                                          for lv, m in kayit))
kontrol("blok ayrıntısı DEBUG logunda", any(lv == logging.DEBUG and "BLOK [DEMIR_POZ]" in m for lv, m in kayit))

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
