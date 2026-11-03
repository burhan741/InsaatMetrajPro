"""Rev-170 — Kopuk COM referansı (RPC_E_DISCONNECTED) otomatik tazeleme testi (AutoCAD'siz)."""
import sys

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")
from app.core.autocad_connector import AutoCADConnector, com_error  # noqa: E402

KOPUK = -2147417848
RED = -2147418111
GECEN = 0
KALAN = 0


def kontrol(ad, kosul):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"PASS  {ad}")
    else:
        KALAN += 1
        print(f"FAIL  {ad}")


class Cizim:
    def __init__(self, ad, olu=False):
        self._ad = ad
        self.olu = olu
        self.ModelSpace_ = f"MS-{ad}"

    @property
    def FullName(self):
        if self.olu:
            raise com_error(KOPUK, "çağrılan nesne istemcilerinden ayrılmış.", None, None)
        return self._ad

    @property
    def ModelSpace(self):
        if self.olu:
            raise com_error(KOPUK, "ayrılmış", None, None)
        return self.ModelSpace_


class App:
    def __init__(self, doc=None, hata=None):
        self.doc = doc
        self.hata = hata

    @property
    def ActiveDocument(self):
        if self.hata is not None:
            raise self.hata
        return self.doc


def yeni(app, cizim):
    c = AutoCADConnector.__new__(AutoCADConnector)
    c._bagli = True
    c.acad_app = app
    c.aktif_cizim = cizim
    c.model_space = "MS-eski"
    c.selection_set = "SS-eski"
    return c


# 1) gerçek log: eski çizim ölü, AutoCAD'de yeni çizim açık
yeni_doc = Cizim("B.dwg")
c = yeni(App(yeni_doc), Cizim("A.dwg", olu=True))
kontrol("ölü çizim -> tazelendi", c.cizim_baglantisini_tazele() is True)
kontrol("ölü çizim -> yeni doc + ModelSpace", c.aktif_cizim is yeni_doc and c.model_space == "MS-B.dwg")
kontrol("ölü çizim -> eski seçim seti bırakıldı", c.selection_set is None)

# 2) kullanıcı başka açık DWG'ye geçti (eski canlı)
c = yeni(App(Cizim("B.dwg")), Cizim("A.dwg"))
kontrol("farklı çizim -> tazelendi", c.cizim_baglantisini_tazele() and c.aktif_cizim.FullName == "B.dwg")

# 3) aynı çizim -> dokunma
eski = Cizim("A.dwg")
c = yeni(App(Cizim("A.dwg")), eski)
kontrol("aynı çizim -> değişmedi", c.cizim_baglantisini_tazele() is False and c.aktif_cizim is eski
        and c.selection_set == "SS-eski")

# 4) AutoCAD meşgul -> dokunma, hata yok
c = yeni(App(hata=com_error(RED, "rejected", None, None)), eski)
kontrol("meşgul -> eski referans", c.cizim_baglantisini_tazele() is False and c.aktif_cizim is eski)
c = yeni(App(hata=AttributeError("<unknown>.ActiveDocument")), eski)
kontrol("AttributeError -> eski referans", c.cizim_baglantisini_tazele() is False)

# 5) uygulama nesnesi ölü -> baglan() çağrılır
c = yeni(App(hata=com_error(KOPUK, "ayrılmış", None, None)), eski)
cagri = []


def sahte_baglan():
    cagri.append(1)
    c._bagli = True
    c.acad_app = App(Cizim("C.dwg"))
    c.aktif_cizim = c.acad_app.doc
    return True


c.baglan = sahte_baglan
kontrol("ölü uygulama -> baglan()", c.cizim_baglantisini_tazele() is True and cagri == [1]
        and c.aktif_cizim.FullName == "C.dwg")

# 6) ölü uygulama + AutoCAD kapalı -> anlaşılır ConnectionError
c = yeni(App(hata=com_error(KOPUK, "ayrılmış", None, None)), eski)


def kapali():
    raise ConnectionError("AutoCAD açık değil")


c.baglan = kapali
try:
    c.cizim_baglantisini_tazele()
    kontrol("AutoCAD kapalı -> ConnectionError", False)
except ConnectionError as e:
    kontrol("AutoCAD kapalı -> ConnectionError", "AutoCAD" in str(e))

# 7) açık çizim yok
c = yeni(App(None), eski)
try:
    c.cizim_baglantisini_tazele()
    kontrol("çizim yok -> ConnectionError", False)
except ConnectionError as e:
    kontrol("çizim yok -> ConnectionError", "DWG" in str(e))

# 8) yeni çizimin ModelSpace'i de ölü -> açık mesaj
c = yeni(App(Cizim("B.dwg", olu=True)), Cizim("A.dwg", olu=True))
try:
    c.cizim_baglantisini_tazele()
    kontrol("ModelSpace alınamadı -> ConnectionError", False)
except ConnectionError as e:
    kontrol("ModelSpace alınamadı -> ConnectionError", "koptu" in str(e))

# 9) bağlı değil -> hiçbir şey
c = yeni(App(Cizim("B.dwg")), eski)
c._bagli = False
kontrol("bağlı değil -> False", c.cizim_baglantisini_tazele() is False and c.aktif_cizim is eski)

print(f"\n{GECEN}/{GECEN + KALAN} PASS")
sys.exit(1 if KALAN else 0)
