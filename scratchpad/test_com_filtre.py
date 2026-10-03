"""Rev-148 — COM mesaj filtresi + döşeme COM retry + OSMODE geri yükleme: PROGRAMSIZ test.

Çalıştırma: python scratchpad/test_com_filtre.py   (AutoCAD / Qt gerekmez)
Sahte COM, gerçek pywintypes.com_error(RPC_E_CALL_REJECTED) fırlatır.
"""
import ctypes
import logging
import os
import sys
import tempfile

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")
os.environ["QUANTIX_DATA_DIR"] = tempfile.mkdtemp()   # ayar dosyası izole

import pythoncom  # noqa: E402
import pywintypes  # noqa: E402

LOG = []


class Yakala(logging.Handler):
    def emit(self, r):
        LOG.append(r.getMessage())


logging.getLogger().addHandler(Yakala())
logging.getLogger().setLevel(logging.INFO)

from app.core import com_mesaj_filtresi as cf  # noqa: E402
from app.core import autocad_connector as ac  # noqa: E402

ac.time.sleep = lambda s: None  # retry beklemelerini atla
GECEN = KALAN = 0
REDDEDILDI = -2147418111


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"   [{detay}]" if detay else ""))


def red():
    return pywintypes.com_error(REDDEDILDI, "Arama aranan tarafından kabul edilmedi.", None, None)


# ── 1) Mesaj filtresi (gerçek ole32 kaydı + vtable) ──
pythoncom.CoInitialize()
kontrol("filtre STA thread'de kaydedildi (HRESULT S_OK)", cf.mesaj_filtresi_kaydet())
kontrol("log: [COM_FILTRE] kaydedildi", any("[COM_FILTRE] kaydedildi" in m for m in LOG))
LOG.clear()
kontrol("ikinci kayıt çağrısı zararsız (thread başına bir kez)", cf.mesaj_filtresi_kaydet() and not LOG)

adres, vt = cf.vtable_nesnesi()
this = ctypes.c_void_p(adres)
kontrol("RetryRejectedCall meşgul (tip 2, 500 ms) -> 150 ms sonra tekrar",
        vt.RetryRejectedCall(this, None, 500, 2) == 150)
kontrol("log: '[COM_FILTRE] reddedildi, yeniden deneniyor'",
        any("[COM_FILTRE] reddedildi, yeniden deneniyor" in m for m in LOG), LOG[-1] if LOG else "")
kontrol("30 sn aşıldı -> vazgeç (0xFFFFFFFF)", vt.RetryRejectedCall(this, None, 31000, 2) == 0xFFFFFFFF)
kontrol("kesin red (tip 1) -> vazgeç", vt.RetryRejectedCall(this, None, 10, 1) == 0xFFFFFFFF)
ppv = ctypes.c_void_p()
kontrol("QueryInterface(IID_IMessageFilter) -> S_OK, kendisi",
        vt.QueryInterface(this, ctypes.byref(cf.IID_IMessageFilter), ctypes.byref(ppv)) == 0
        and ppv.value == adres)
kontrol("QueryInterface(başka IID) -> E_NOINTERFACE",
        vt.QueryInterface(this, ctypes.byref(cf._guid(0x12345678)), ctypes.byref(ppv)) == cf.E_NOINTERFACE)
kontrol("HandleInComingCall -> SERVERCALL_ISHANDLED", vt.HandleInComingCall(this, 0, None, 0, None) == 0)


# ── 2) Sahte AutoCAD: belirli sayıda RED sonra başarı ──
class Utility:
    def __init__(self, doc):
        self.doc = doc

    def InitializeUserInput(self, *a):
        self.doc.cagri("InitializeUserInput")

    def Prompt(self, m):
        self.doc.cagri("Prompt")

    def GetPoint(self, *a):
        self.doc.cagri("GetPoint")
        x = self.doc.nokta_kuyrugu.pop(0)
        if isinstance(x, Exception):
            raise x
        return x

    def GetInput(self):
        return ""

    def GetKeyword(self, *a):
        self.doc.cagri("GetKeyword")
        return "Evet"


class Doc:
    def __init__(self, osmode=4133):
        self.vars = {"OSMODE": osmode}
        self.red_sayaci = {}      # çağrı adı -> kaç kez daha reddedilecek
        self.nokta_kuyrugu = []
        self.yazilanlar = []
        doc = self

        class Layers:
            def Add(self, ad):
                doc.cagri("Layers.Add")
        self.Layers = Layers()

    def cagri(self, ad):
        if self.red_sayaci.get(ad, 0) > 0:
            self.red_sayaci[ad] -= 1
            raise red()

    @property
    def Utility(self):
        self.cagri("Utility")   # zincirin ARA adımı da reddedilebilir
        return Utility(self)

    def GetVariable(self, ad):
        self.cagri("GetVariable")
        return self.vars[ad]

    def SetVariable(self, ad, v):
        self.cagri("SetVariable")
        self.vars[ad] = int(v)
        self.yazilanlar.append(int(v))


def baglanti(doc):
    c = ac.AutoCADConnector.__new__(ac.AutoCADConnector)
    c._orijinal_renkler = {}
    c._bagli = True
    c.acad_app = object()
    c.aktif_cizim = doc
    c._autocad_one_getir_hafif = lambda: None
    return c


doc = Doc()
c = baglanti(doc)
doc.nokta_kuyrugu = [(1.0, 2.0, 0.0)]
doc.red_sayaci = {"Utility": 2, "Prompt": 1, "GetPoint": 2}
kontrol("GetPoint: Utility/Prompt/GetPoint reddedildi -> retry ile nokta alındı",
        c.doseme_nokta_al("x") == ("nokta", (1.0, 2.0)))
kontrol("red ESC SAYILMADI (log'da iptal yok)", not any("girdi iptal (ESC)" in m for m in LOG))
doc.nokta_kuyrugu = [pywintypes.com_error(-2145320928, "keyword", None, None)]
kontrol("ENTER hâlâ enter", c.doseme_nokta_al("x", (0, 0)) == ("enter", None))
doc.nokta_kuyrugu = [pywintypes.com_error(-2147352567, "iptal", None, None)]
kontrol("ESC hâlâ esc", c.doseme_nokta_al("x") == ("esc", None))
doc.red_sayaci = {"GetPoint": 99}
doc.nokta_kuyrugu = [(0, 0, 0)] * 10
try:
    c.doseme_nokta_al("x")
    kontrol("sürekli red -> hata yükselir (ESC'ye dönüşmez)", False)
except pywintypes.com_error as e:
    kontrol("sürekli red -> hata yükselir (ESC'ye dönüşmez)", e.hresult == REDDEDILDI)
doc.red_sayaci = {"Utility": 1, "GetKeyword": 2}
kontrol("Evet/Hayır: red sonrası cevap alındı", c.komut_satiri_evet_hayir("?") is True)

# ── 3) OSMODE kuralı ──
kontrol("saf: (4133, yok) -> 4133", ac.osmode_orijinal_belirle(4133, None) == 4133)
kontrol("saf: (33, kayıtlı 4133) -> 4133 (33 orijinal SAYILMAZ)", ac.osmode_orijinal_belirle(33, 4133) == 4133)
kontrol("saf: (33, yok) -> 33", ac.osmode_orijinal_belirle(33, None) == 33)
kontrol("saf: (511, kayıtlı 4133) -> 511 (kullanıcı değiştirmiş)", ac.osmode_orijinal_belirle(511, 4133) == 511)
kontrol("saf: bozuk kayıt -> okunan", ac.osmode_orijinal_belirle(33, "abc") == 33)

doc = Doc(osmode=4133)
c = baglanti(doc)
doc.red_sayaci = {"GetVariable": 2, "SetVariable": 2}
c.doseme_toplu_baslat()
kontrol("başlat: red'e rağmen OSMODE 33 yapıldı", doc.vars["OSMODE"] == 33)
kontrol("başlat: orijinal 4133 ayar dosyasına yazıldı", ac.autocad_ayari_oku("osmode_orijinal") == 4133)
doc.red_sayaci = {"SetVariable": 3}
kontrol("bitir: red'e rağmen 4133 geri yüklendi, mesaj yok",
        c.doseme_toplu_bitir() == "" and doc.vars["OSMODE"] == 4133)
doc.vars["OSMODE"] = 1   # kullanıcı arada değiştirmiş olsa da ...
c.doseme_toplu_baslat()
kontrol("aynı oturumda ikinci döngü: orijinal yeniden OKUNMAZ (4133 kalır)", c._osmode_orijinal == 4133)
doc.red_sayaci = {"SetVariable": 99}
mesaj = c.doseme_toplu_bitir()
kontrol("bitir sürekli red: kullanıcı mesajı GERÇEK değeri (4133) içeriyor", "4133" in mesaj and "OSMODE" in mesaj,
        mesaj.replace("\n", " "))

# Önceki oturum geri yükleyemeden kapandı: AutoCAD'de 33 kaldı, dosyada 4133 var
doc2 = Doc(osmode=33)
c2 = baglanti(doc2)
c2.doseme_toplu_baslat()
kontrol("yeni oturum: okunan 33 + kayıtlı 4133 -> orijinal 4133", c2._osmode_orijinal == 4133)
kontrol("yeni oturum: dosyadaki 4133 33 ile EZİLMEDİ", ac.autocad_ayari_oku("osmode_orijinal") == 4133)
c2.doseme_toplu_bitir()
kontrol("yeni oturum bitiş: kullanıcının gerçek 4133'ü geri geldi", doc2.vars["OSMODE"] == 4133)

# Döngü içinde hata olsa da finally geri yükler
doc3 = Doc(osmode=695)
c3 = baglanti(doc3)
ac.autocad_ayari_yaz("osmode_orijinal", 695)
try:
    c3.doseme_toplu_baslat()
    try:
        raise RuntimeError("döngüde hata")
    finally:
        c3.doseme_toplu_bitir()
except RuntimeError:
    pass
kontrol("döngü hatası + finally: OSMODE 695'e döndü", doc3.vars["OSMODE"] == 695)

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
