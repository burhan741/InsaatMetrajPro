"""Rev-137 Aşama 1/2 — Temel Kirişi (SBH) regex + hesap çekirdeği testi (AutoCAD'siz)."""
import sys

sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")
from app.core.autocad_connector import (  # noqa: E402
    temel_kirisi_ayristir, temel_kirisi_hesapla,
    kolon_yazisini_ayristir, kolon_yazilarini_toplu_ayristir,
)

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


# ── Aşama 1: regex ──
r = temel_kirisi_ayristir("SBH-1 (20/165)")
kontrol("SBH-1 basarili", r["basarili"] and r["ad"] == "SBH-1")
kontrol("SBH-1 g=20 y=165", r["genislik_cm"] == 20 and r["yukseklik_cm"] == 165)
kontrol("SBH-1 uyari yok", r["uyari"] == "")

r = temel_kirisi_ayristir("SBH-2 (25/150)")
kontrol("SBH-2 g=25 y=150", r["basarili"] and r["genislik_cm"] == 25 and r["yukseklik_cm"] == 150)

for m in ["SZ07 (50/50)", "KB110 (25/60)", "bozuk", "", "28Ø14 L=442", "Ø14/20 L=500"]:
    r = temel_kirisi_ayristir(m)
    kontrol(f"'{m}' ilgisiz", not r["basarili"] and r["ilgisiz"])

kontrol("XSBH-1 (başka kelime içinde) ilgisiz", temel_kirisi_ayristir("XSBH-1 (20/165)")["ilgisiz"])
kontrol("küçük harf sbh-5 kabul", temel_kirisi_ayristir("sbh-5 (30/120)")["ad"] == "SBH-5")
kontrol("SBH1 (tiresiz) kabul", temel_kirisi_ayristir("SBH1 (20/165)")["basarili"])
kontrol("boşluklu SBH-1(20 / 165)", temel_kirisi_ayristir("SBH-1(20 / 165)")["yukseklik_cm"] == 165)
kontrol("MTEXT kodlu", temel_kirisi_ayristir(r"{\C1;SBH-7 (20/165)}")["ad"] == "SBH-7")
r = temel_kirisi_ayristir("SBH-3 (0/150)")
kontrol("0 boyut -> hata, ilgisiz degil", not r["basarili"] and not r["ilgisiz"] and r["hata"])
kontrol("ters sira uyarisi", temel_kirisi_ayristir("SBH-4 (180/20)")["uyari"] != "")

# ── Kolon aracı SBH'yi ALMAMALI ──
kontrol("kolon: SBH1 kolon sayilmaz", kolon_yazisini_ayristir("SBH1 (20/165)")["tip"] == "temel_kirisi")
kontrol("kolon: SBH-1 kolon sayilmaz", kolon_yazisini_ayristir("SBH-1 (20/165)")["tip"] != "kolon")
kontrol("kolon: SB12 hala kolon", kolon_yazisini_ayristir("SB12 (50/50)")["tip"] == "kolon")
kontrol("kolon: SZ07 hala kolon", kolon_yazisini_ayristir("SZ07 (50/50)")["tip"] == "kolon")
t = kolon_yazilarini_toplu_ayristir(["SZ07 (50/50)", "SBH1 (20/165)", "SBH-2 (25/150)", "KB110 (25/60)"])
kontrol("toplu: sadece 1 kolon", len(t["kolonlar"]) == 1)

# ── Aşama 2: hesap ──
h = temel_kirisi_hesapla(20, 165, 5.0)
kontrol("beton 1.65 m3 (1650 degil)", h["beton_m3"] == 1.65)
kontrol("kalip 16.5 m2", h["kalip_m2"] == 16.5)
kontrol("metre donusum", h["genislik_m"] == 0.2 and h["yukseklik_m"] == 1.65)
kontrol("uyari yok", h["uyari"] == "" and h["hata"] == "")
h = temel_kirisi_hesapla(25, 150, 12.4)
kontrol("SBH-2 L=12.4 beton 4.65", h["beton_m3"] == round(0.25 * 1.5 * 12.4, 3))
kontrol("SBH-2 L=12.4 kalip 37.2", h["kalip_m2"] == round(2 * 1.5 * 12.4, 3))
h = temel_kirisi_hesapla(20, 165, 500)
kontrol("L=500 -> cm uyarisi", h["uyari"] != "" and h["beton_m3"] == 165.0)
for args in [(20, 165, 0), (0, 165, 5), (20, -1, 5), ("x", 165, 5)]:
    h = temel_kirisi_hesapla(*args)
    kontrol(f"gecersiz {args} -> hata", h["hata"] != "" and h["beton_m3"] == 0)

# ── Aşama 3b: toplu mod seçim değerlendirme (saf) ──
from app.core.autocad_connector import temel_kirisi_secim_degerlendir as deg  # noqa: E402


def yz(ad="SBH-1", g=20, y=165, h="Y1", uyari=""):
    return {"ad": ad, "genislik_cm": g, "yukseklik_cm": y, "handle": h, "uyari": uyari, "basarili": True}


def cz(uz, h, hata=""):
    return {"handle": h, "uzunluk_birim": uz, "obje_tipi": "AcDbLine", "hata": hata}


d = deg({"yazilar": [yz()], "cizgiler": [cz(500, "C1"), cz(510, "C2")]}, "cm")
kontrol("2 çizgi ortalama 5.05", d["gecerli"] and d["uzunluk_m"] == 5.05)
kontrol("2 çizgi handle", d["cizgi_handleler"] == ["C1", "C2"] and d["yazi_handle"] == "Y1")
kontrol("%2 fark -> uyarı yok", d["uyarilar"] == [])
h = temel_kirisi_hesapla(d["genislik_cm"], d["yukseklik_cm"], d["uzunluk_m"])
kontrol("ortalama ile beton 1.667 kalıp 16.665", h["beton_m3"] == 1.667 and h["kalip_m2"] == 16.665)
d = deg({"yazilar": [yz()], "cizgiler": [cz(5000, "C1"), cz(5000, "C2")]}, "mm")
kontrol("mm birim 5000 -> 5.0", d["uzunluk_m"] == 5.0)
d = deg({"yazilar": [yz()], "cizgiler": [cz(500, "C1"), cz(400, "C2")]}, "cm")
kontrol("Rev-158: 1.00 m fark > 2b (0.40) -> eksik_uyari", "seçilmemiş" in d["eksik_uyari"])
d = deg({"yazilar": [yz()], "cizgiler": [cz(500, "C1")]}, "cm")
kontrol("Rev-158: tek çizgi -> hata (en az 2)", not d["gecerli"] and "en az 2" in d["hata"])
d = deg({"yazilar": [yz()], "cizgiler": []}, "cm")
kontrol("çizgi yok -> elle_gerekli", d["gecerli"] and d["elle_gerekli"] and d["uzunluk_m"] is None)
d = deg({"yazilar": [yz()], "cizgiler": [cz(0, "C1", "uzunluk okunamadı")]}, "cm")
kontrol("okunamayan çizgi -> elle + uyarı", d["elle_gerekli"] and d["uyarilar"])
d = deg({"yazilar": [yz()], "cizgiler": [cz(500, "C1"), cz(500, "C2"), cz(500, "C3")]}, "cm")
kontrol("Rev-158: koordinatsız 3 çizgi -> kenarlara ayrılamadı hatası", not d["gecerli"] and "ayrılamadı" in d["hata"])
d = deg({"yazilar": [], "cizgiler": [cz(500, "C1")]}, "cm")
kontrol("yazı yok -> hata", not d["gecerli"] and "SBH yazısı seçilmedi" in d["hata"])
d = deg({"yazilar": [yz(), yz("SBH-2", h="Y2")], "cizgiler": []}, "cm")
kontrol("2 yazı -> hata", not d["gecerli"] and "Birden fazla" in d["hata"])
d = deg({"yazilar": [], "gecersiz_yazilar": [{"hata": "Geçersiz boyut: 0/150"}], "cizgiler": []}, "cm")
kontrol("geçersiz yazı -> hata mesajı", "0/150" in d["hata"])
d = deg({"yazilar": [yz()], "cizgiler": [cz(5100, "C1"), cz(5100, "C2")]}, "cm")
kontrol("51 m -> birim uyarısı", any("olağan dışı" in u for u in d["uyarilar"]))
d = deg({"yazilar": [yz(uyari="ters")], "cizgiler": [cz(500, "C1"), cz(500, "C2")]}, "cm")
kontrol("ters kesit uyarısı taşınır", "ters" in d["uyarilar"])

# ── Rev-137 gerçek log: tek seçimde 2 SBH-1 + 4 çizgi (290 cm) ──
from app.core.autocad_connector import temel_kirisi_secimi_ayir as ayir  # noqa: E402


def yzk(ad, h, konum):
    d = yz(ad, h=h)
    d["konum"] = konum
    return d


def czk(h, bas, son, uz=290.0):
    return {"handle": h, "uzunluk_birim": uz, "obje_tipi": "AcDbLine", "hata": "", "bas": bas, "son": son}


# (b) iki ayrı kiriş: A y=0/20, B y=100/120; yazılar ortada. Çizgi sırası karışık (loga benzer)
okuma = {"yazilar": [yzk("SBH-1", "T2", (145, 110)), yzk("SBH-1", "T1", (145, 10))],
         "cizgiler": [czk("C494E8", (0, 100), (290, 100)), czk("C490F2", (0, 0), (290, 0)),
                      czk("C494E9", (290, 120), (0, 120)), czk("C490F4", (0, 20), (290, 20))]}
a = ayir(okuma)
kontrol("2 kiriş tek seçim -> 2 grup", a["hata"] == "" and len(a["gruplar"]) == 2)
g = {gr["yazilar"][0]["handle"]: sorted(c["handle"] for c in gr["cizgiler"]) for gr in a["gruplar"]}
kontrol("T1 <- C490F2/C490F4 (alttaki kiriş)", g["T1"] == ["C490F2", "C490F4"])
kontrol("T2 <- C494E8/C494E9 (üstteki kiriş)", g["T2"] == ["C494E8", "C494E9"])
dd = [deg(gr, "cm") for gr in a["gruplar"]]
kontrol("her grup geçerli, L=2.90, uyarısız", all(x["gecerli"] and x["uzunluk_m"] == 2.9 and not x["uyarilar"] for x in dd))

# (a) üst üste çift obje: aynı yazı aynı yerde + çizgiler aynı uçlarda
okuma = {"yazilar": [yzk("SBH-1", "T1", (145, 10)), yzk("SBH-1", "T9", (145, 10))],
         "cizgiler": [czk("A", (0, 0), (290, 0)), czk("A2", (290, 0), (0, 0)),
                      czk("B", (0, 20), (290, 20)), czk("B2", (0, 20), (290, 20))]}
a = ayir(okuma)
kontrol("çift obje -> 1 grup, 2 çizgi", len(a["gruplar"]) == 1 and len(a["gruplar"][0]["cizgiler"]) == 2)
x = deg(a["gruplar"][0], "cm")
kontrol("çift obje -> geçerli L=2.90 + tekilleştirme notu",
        x["gecerli"] and x["uzunluk_m"] == 2.9 and any("tekilleştirildi" in u for u in x["uyarilar"]))

# sayı uyuşmazlığı
a = ayir({"yazilar": [yzk("SBH-1", "T1", (0, 10)), yzk("SBH-2", "T2", (0, 110))],
          "cizgiler": [czk("A", (0, 0), (290, 0)), czk("B", (0, 20), (290, 20)), czk("C", (0, 100), (290, 100))]})
kontrol("2 yazı + 3 çizgi -> açık hata", a["hata"] and "4 çizgi" in a["hata"] and not a["gruplar"])

# konum yok
a = ayir({"yazilar": [yz(h="T1"), yz(h="T2")],
          "cizgiler": [cz(500, "A"), cz(500, "B"), cz(500, "C"), cz(500, "D")]})
kontrol("konum okunamadı -> tek tek seçin hatası", "konumlar okunamadı" in a["hata"])

# tek yazı: dokunmadan geçer (eski davranış)
a = ayir({"yazilar": [yz()], "cizgiler": [cz(500, "C1"), cz(510, "C2")]})
kontrol("tek yazı -> 1 grup, çizgiler aynen", len(a["gruplar"]) == 1 and len(a["gruplar"][0]["cizgiler"]) == 2)

# paralel olmayan eşleşme notu
a = ayir({"yazilar": [yzk("SBH-1", "T1", (5, 5)), yzk("SBH-2", "T2", (500, 500))],
          "cizgiler": [czk("A", (0, 0), (290, 0)), czk("B", (0, 0), (0, 290)),
                       czk("C", (480, 480), (770, 480)), czk("D", (480, 500), (770, 500))]})
kontrol("paralel olmayan çizgiler -> not",
        any("paralel değil" in n for gr in a["gruplar"] for n in gr["notlar"]))

print(f"\n{GECEN}/{GECEN + KALAN} PASS")
sys.exit(1 if KALAN else 0)
