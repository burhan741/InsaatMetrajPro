"""Rev-156 — baglan(): AutoCAD kalıcı meşgulken (açık iletişim kutusu) hızlı + açık mesajla dur."""
import sys
import time

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")
import pywintypes  # noqa: E402
from app.core import autocad_connector as ac  # noqa: E402
from app.core import com_mesaj_filtresi as cf  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"  [{detay}]" if detay else ""))


# ── 1) Filtre kararı: kısa bekleme ──
kontrol("normal: 29 sn -> tekrar dene", cf.retry_kararı(2, 29000) == cf.YENIDEN_DENEME_MS)
with cf.kisa_bekleme(3000):
    kontrol("kısa bekleme: 2.9 sn -> tekrar dene", cf.retry_kararı(2, 2900) == cf.YENIDEN_DENEME_MS)
    kontrol("kısa bekleme: 3.0 sn -> VAZGEÇ", cf.retry_kararı(2, 3000) == cf.VAZGEC)
kontrol("blok bitince 30 sn'ye döndü", cf.retry_kararı(2, 3000) == cf.YENIDEN_DENEME_MS and cf._azami_ms == 30000)
once = cf.vazgecme_sayisi()
cf._retry_rejected_call(None, None, 31000, 2)
kontrol("vazgeçince sayaç artar", cf.vazgecme_sayisi() == once + 1)


# ── 2) baglan() sahte AutoCAD ──
AZAMI_GOZLEM = []


class Doc:
    Name = "ide.dwg"
    FullName = r"C:\x\ide.dwg"
    ModelSpace = object()


class App:
    def __init__(self, mod):
        self.mod = mod
        self.cagri = 0

    def __setattr__(self, ad, deger):
        if ad == "Visible" and self.mod.startswith("mesgul"):
            self._reddet()
        object.__setattr__(self, ad, deger)

    def _reddet(self):
        AZAMI_GOZLEM.append(cf._azami_ms)
        if self.mod == "mesgul_filtre":
            cf._vazgecme_sayaci += 1            # filtre 3 sn sonra vazgeçti
            raise AttributeError("<unknown>.ActiveDocument")   # pywin32 reddi AttributeError'a çevirir
        raise pywintypes.com_error(ac.AutoCADConnector.RPC_E_CALL_REJECTED, "Arama reddedildi", None, None)

    @property
    def ActiveDocument(self):
        object.__setattr__(self, "cagri", self.cagri + 1)
        AZAMI_GOZLEM.append(cf._azami_ms)
        if self.mod.startswith("mesgul"):
            self._reddet()
        if self.mod == "genpy" and self.cagri == 1:
            raise AttributeError("<unknown>.ActiveDocument")   # gen_py uyuşmazlığı: retry ile geçer
        if self.mod == "cizimsiz":
            return None
        return Doc()


def baglan(mod):
    ac.win32com.client.GetActiveObject = lambda prog_id, _m=mod: App(_m)
    c = ac.AutoCADConnector.__new__(ac.AutoCADConnector)
    c._bagli = False
    t0 = time.time()
    try:
        c.baglan()
        return c, None, time.time() - t0
    except Exception as e:
        return c, e, time.time() - t0


for mod in ("mesgul_filtre", "mesgul_kod"):
    AZAMI_GOZLEM.clear()
    c, e, sure = baglan(mod)
    kontrol(f"{mod}: ConnectionError + açık mesaj (Proxy / SHX / ESC)",
            isinstance(e, ConnectionError) and "meşgul" in str(e) and "Proxy" in str(e) and "ESC" in str(e), repr(e))
    kontrol(f"{mod}: 5×0.5 sn retry döngüsüne girmeden durdu ({sure:.2f} sn)", sure < 0.4)
    kontrol(f"{mod}: bağlanırken bekleme 3 sn idi", AZAMI_GOZLEM and set(AZAMI_GOZLEM) == {3000}, AZAMI_GOZLEM)
    kontrol(f"{mod}: sonra 30 sn'ye geri döndü", cf._azami_ms == 30000)
    kontrol(f"{mod}: bağlı değil", not c._bagli)

AZAMI_GOZLEM.clear()
c, e, sure = baglan("genpy")
kontrol("gen_py AttributeError (meşgul değil): retry ile bağlandı", e is None and c._bagli, repr(e))
kontrol("normal bağlantı sonrası bekleme 30 sn", cf._azami_ms == 30000)

c, e, sure = baglan("normal")
kontrol("normal bağlantı", e is None and c._bagli and cf._azami_ms == 30000)

c, e, sure = baglan("cizimsiz")
kontrol("açık çizim yok -> eski mesaj, bekleme geri alındı",
        isinstance(e, ConnectionError) and "açık bir çizim yok" in str(e) and cf._azami_ms == 30000, repr(e))

print(f"\n{GECEN} PASS / {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
