"""Rev-137 Aşama 3b — toplu mod COM katmanı (sahte COM): kiris_oku / toplu_baslat /
mesaj / uzunluk_sor / obje_isaretle_hizli / cizim_birimi_oku + teşhis logları."""
import logging
import sys

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")
from app.core.autocad_connector import AutoCADConnector, com_error  # noqa: E402

KAYIT = []


class H(logging.Handler):
    def emit(self, r):
        KAYIT.append((r.levelname, r.getMessage(), r.exc_info is not None))


logging.getLogger().addHandler(H())
logging.getLogger().setLevel(logging.DEBUG)
GECEN = KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad)


def log_var(parca, seviye=None, exc=None):
    return any(parca in m and (seviye is None or s == seviye) and (exc is None or e == exc)
               for s, m, e in KAYIT)


class Ent:
    def __init__(self, obj, handle, text=None, length=None, length_hata=None,
                 bas=(0.0, 0.0, 0.0), son=(100.0, 0.0, 0.0), bbox=((0, 0, 0), (10, 4, 0))):
        self.ObjectName = obj
        self.Handle = handle
        self.Layer = "0"
        self.Color = 256
        self._l, self._lh = length, length_hata
        self.guncellendi = 0
        self._bbox = bbox
        if text is not None:
            self.TextString = text
        if obj == "AcDbLine":
            self.StartPoint, self.EndPoint = bas, son
        elif obj == "AcDbPolyline":
            self.Coordinates = (bas[0], bas[1], 50.0, 0.0, son[0], son[1])

    def GetBoundingBox(self):
        return self._bbox

    @property
    def Length(self):
        if self._lh:
            raise self._lh
        return self._l

    def Update(self):
        self.guncellendi += 1


class SS:
    def __init__(self, kuyruk, ad):
        self.kuyruk = kuyruk
        self.Name = ad
        self.o = []
        self.secim_sayisi = 0
        self.mesgul_kalan = 0  # >0 ise SelectOnScreen isim çözümlemesi reddedilir

    @property
    def Count(self):
        return len(self.o)

    def Item(self, i):
        return self.o[i]

    def Clear(self):
        self.o = []

    def __getattribute__(self, ad):
        # pywin32 dinamik dispatch davranışı: AutoCAD meşgulken GetIDsOfNames
        # reddedilir -> AttributeError("Add.SelectOnScreen")
        if ad == "SelectOnScreen" and object.__getattribute__(self, "mesgul_kalan") > 0:
            self.mesgul_kalan -= 1
            raise AttributeError("Add.SelectOnScreen")
        return object.__getattribute__(self, ad)

    def SelectOnScreen(self):
        self.secim_sayisi += 1
        self.o = self.kuyruk.pop(0) if self.kuyruk else []


class SSler:
    def __init__(self, kuyruk):
        self.kuyruk = kuyruk
        self.add_sayisi = 0
        self.add_mesgul = 0
        self.son = None

    def Item(self, ad):
        raise Exception("set yok")

    def Add(self, ad):
        self.add_sayisi += 1
        if self.add_mesgul > 0:
            self.add_mesgul -= 1
            raise com_error(-2147418111, "Call was rejected by callee.", None, None)
        self.son = SS(self.kuyruk, ad)
        return self.son


class AcadApp:
    def __init__(self, window_state=3):
        self.Visible = True
        self._ws = window_state
        self.ws_yazma = []

    @property
    def WindowState(self):
        return self._ws

    @WindowState.setter
    def WindowState(self, v):
        self.ws_yazma.append(v)
        self._ws = v


class Util:
    def __init__(self):
        self.promptlar = []
        self.getreal = []

    def Prompt(self, s):
        self.promptlar.append(s)

    def GetReal(self, s):
        v = self.getreal.pop(0)
        if v is None:
            raise com_error(-2147352567, "User input is a keyword", None, None)
        return v


class Cizim:
    def Activate(self):
        pass

    def __init__(self, kuyruk, insunits=5):
        self.SelectionSets = SSler(kuyruk)
        self.Utility = Util()
        self.insunits = insunits
        self.nesneler = {}
        self.regen_sayisi = 0

    def GetVariable(self, ad):
        return self.insunits

    def HandleToObject(self, h):
        return self.nesneler.setdefault(h, Ent("AcDbLine", h, length=1))

    def Regen(self, x):
        self.regen_sayisi += 1

    class Layers:
        @staticmethod
        def Item(ad):
            class L:
                Lock = False
            return L()


def yeni(kuyruk, insunits=5, window_state=3):
    c = AutoCADConnector.__new__(AutoCADConnector)
    c._bagli = True
    c.acad_app = AcadApp(window_state)
    c.aktif_cizim = Cizim(kuyruk, insunits)
    c.selection_set = None
    c._orijinal_renkler = {}
    c._metraj_alinan_objeler = []
    c.one_getir_sayisi = 0
    c.tam_one_getir_sayisi = 0

    def _win32():
        c.one_getir_sayisi += 1

    def _tam():
        c.tam_one_getir_sayisi += 1
    c._win32_pencere_one_getir = _win32
    c._autocad_one_getir = _tam  # tam (ağır) sürüm toplu modda ÇAĞRILMAMALI
    return c


# ── Bug 1: "Add.SelectOnScreen" AttributeError (AutoCAD meşgul) -> retry ──
import time as _t  # noqa: E402
c = yeni([[Ent("AcDbText", "Y1", text="SBH-1 (20/165)")]])
c.aktif_cizim.SelectionSets.add_mesgul = 1
c.temel_kirisi_toplu_baslat()
kontrol("Add meşgul (RPC reddi) -> retry ile set kuruldu", c.selection_set is c.aktif_cizim.SelectionSets.son)
kontrol("selection_set gerçek set nesnesi (Name doğru)", c.selection_set.Name.startswith("TemelKirisiToplu_"))
c.selection_set.mesgul_kalan = 2
KAYIT.clear()
r = c.temel_kirisi_kiris_oku()
kontrol("'Add.SelectOnScreen' 2 kez -> 3. denemede seçim yapıldı",
        r["durum"] == "okundu" and [y["ad"] for y in r["yazilar"]] == ["SBH-1"])
kontrol("MESGUL_RETRY logları", log_var("[MESGUL_RETRY] SelectOnScreen: deneme 2/8", "WARNING")
        and log_var("SelectOnScreen: 3. denemede BAŞARILI"))

c = yeni([[Ent("AcDbText", "Y1", text="SBH-1 (20/165)")]])
c.temel_kirisi_toplu_baslat()
c.selection_set.mesgul_kalan = 99
try:
    c.temel_kirisi_kiris_oku()
    vazgecti = False
except AttributeError:
    vazgecti = True
kontrol("sürekli meşgul -> 8 denemede vazgeçip hatayı üste iletir (sonsuz döngü yok)", vazgecti)

# ── Bug 2: hafif öne getirme ──
c = yeni([], window_state=3)
t0 = _t.time()
c.temel_kirisi_toplu_baslat()
kontrol("maximize pencerede WindowState'e dokunulmadı", c.acad_app.ws_yazma == [])
kontrol("hafif öne getirme < 0.1 sn", _t.time() - t0 < 0.1)
kontrol("ağır _autocad_one_getir çağrılmadı", c.tam_one_getir_sayisi == 0)
c = yeni([], window_state=2)
c.temel_kirisi_toplu_baslat()
kontrol("simge durumundaki pencere acMax yapıldı", c.acad_app.ws_yazma == [3])
c = yeni([[], []], window_state=3)
c.acad_app.Visible = False
c.temel_kirisi_toplu_baslat()
kontrol("görünmez AutoCAD Visible=True yapıldı", c.acad_app.Visible is True)

kuyruk = [
    [Ent("AcDbMText", "Y1", text=r"{\C1;SBH-1 (20/165)}"), Ent("AcDbLine", "A1", length=500.0),
     Ent("AcDbPolyline", "B1", length=510.0), Ent("AcDbCircle", "K1")],
    [Ent("AcDbText", "Y2", text="SBH-2 (0/150)"), Ent("AcDbText", "Y3", text="SZ07 (50/50)"),
     Ent("AcDbLine", "L0", length_hata=RuntimeError("Length patladı"))],
    [],
]
c = yeni(kuyruk)
c.temel_kirisi_toplu_baslat()
kontrol("öne getirme 1 kez + set 1 kez", c.one_getir_sayisi == 1 and c.aktif_cizim.SelectionSets.add_sayisi == 1)

r = c.temel_kirisi_kiris_oku()
kontrol("kiriş 1: yazı SBH-1", r["durum"] == "okundu" and [y["ad"] for y in r["yazilar"]] == ["SBH-1"]
        and r["yazilar"][0]["handle"] == "Y1")
kontrol("kiriş 1: 2 çizgi uzunluk", [(x["handle"], x["uzunluk_birim"]) for x in r["cizgiler"]]
        == [("A1", 500.0), ("B1", 510.0)])
kontrol("kiriş 1: daire diğer", r["diger_sayisi"] == 1)
kontrol("LINE uçları okundu", r["cizgiler"][0]["bas"] == (0.0, 0.0) and r["cizgiler"][0]["son"] == (100.0, 0.0))
kontrol("POLYLINE uçları (ilk/son köşe)", r["cizgiler"][1]["bas"] == (0.0, 0.0)
        and r["cizgiler"][1]["son"] == (100.0, 0.0))
kontrol("yazı merkezi (bbox)", r["yazilar"][0]["konum"] == (5.0, 2.0))

KAYIT.clear()
r = c.temel_kirisi_kiris_oku()
kontrol("kiriş 2: 0/150 geçersiz yazılar'da", len(r["gecersiz_yazilar"]) == 1 and r["yazilar"] == [])
kontrol("kiriş 2: kolon yazısı diğer", r["diger_sayisi"] == 1)
kontrol("kiriş 2: Length hatası çizgi.hata'da", r["cizgiler"][0]["hata"].startswith("uzunluk okunamadı"))
kontrol("Length hatası ERROR+traceback log", log_var("temel_kirisi_kiris_oku/Length hata", "ERROR", True))
kontrol("TIMING logu YOK (teşhis temizlendi)", not log_var("[TIMING]"))

r = c.temel_kirisi_kiris_oku()
kontrol("boş ENTER -> bos_secim", r["durum"] == "bos_secim")
kontrol("döngüde tekrar öne getirme YOK (3 seçimde 1 kez)",
        c.one_getir_sayisi == 1 and c.tam_one_getir_sayisi == 0)
kontrol("teşhis bayrağı kapandı", c._tk_aktif() is False)

c.temel_kirisi_mesaj("SBH-1 EKLENDİ")
kontrol("mesaj komut satırına", any("SBH-1 EKLENDİ" in p for p in c.aktif_cizim.Utility.promptlar))

c.aktif_cizim.Utility.getreal = [4.25, None, 0.0]
kontrol("GetReal 4.25", c.temel_kirisi_uzunluk_sor("Uzunluk:") == 4.25)
kontrol("GetReal ESC -> None", c.temel_kirisi_uzunluk_sor("Uzunluk:") is None)
kontrol("GetReal 0 -> None", c.temel_kirisi_uzunluk_sor("Uzunluk:") is None)

c.obje_isaretle_hizli("A1")
ent = c.aktif_cizim.nesneler["A1"]
kontrol("hızlı boyama yeşil (3)", ent.Color == 3)
kontrol("hızlı boyama Regen YOK, Update var", c.aktif_cizim.regen_sayisi == 0 and ent.guncellendi == 1)
c.obje_isaret_geri_al("A1")
kontrol("geri al orijinal renk", ent.Color == 256)

kontrol("INSUNITS 5 -> cm", c.cizim_birimi_oku() == "cm")
c.aktif_cizim.insunits = 4
kontrol("INSUNITS 4 -> mm", c.cizim_birimi_oku() == "mm")

# _com_retry RPC logu (tüm araçlarda)
KAYIT.clear()
n = {"i": 0}


def mesgul():
    n["i"] += 1
    if n["i"] < 3:
        raise com_error(-2147418111, "Call was rejected by callee.", None, None)
    return "ok"


kontrol("retry ok + deneme logları", c._com_retry(mesgul, bekleme=0.001) == "ok"
        and log_var("[COM_RETRY] deneme 2/5", "WARNING") and log_var("3. denemede BAŞARILI"))

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
