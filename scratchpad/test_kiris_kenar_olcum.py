"""Rev-158 — SBH + K ortak kenar ölçümü: sınırsız çizgi, bölünmüş kenar (kapsam / dolu), eksik seçim uyarısı."""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QUANTIX_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical", "question"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))

from app.core.autocad_connector import (  # noqa: E402
    kiris_kenarlari_olc, kenar_eksik_secim_uyarisi, kiris_hesapla, kiris_secim_degerlendir,
    temel_kirisi_secim_degerlendir, temel_kirisi_hesapla, AcadColor,
)
import app.ui.metraj_analiz_window as maw  # noqa: E402

maw.SbhDemirTipDialog.exec = lambda self: QDialog.DialogCode.Accepted
GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + ("" if kosul else f"   -> {detay}"))


def cz(h, x1, x2, y, birim_carpani=100.0):
    """x ekseninde yatay çizgi; koordinatlar metre verilir, çizim birimi cm."""
    b, s = (x1 * birim_carpani, y * birim_carpani), (x2 * birim_carpani, y * birim_carpani)
    return {"handle": h, "uzunluk_birim": abs(s[0] - b[0]), "bas": b, "son": s, "hata": "",
            "obje_tipi": "AcDbLine"}


CM = 0.01  # cm -> m çarpanı
# Brief: üst 12.45 tek parça; alt 7.75 + 3.80. Brief "0.75 boşluk" diyor ama
# 7.75 + 0.75 + 3.80 = 12.30 ≠ 12.45 — L_beton 12.45 için boşluk 0.90 olmalı.
UST = cz("U1", 0, 12.45, 0.30)
ALT_A = cz("A1", 0, 7.75, 0)
ALT_B_090 = cz("A2", 8.65, 12.45, 0)     # boşluk 0.90 -> alt kapsam 12.45
ALT_B_075 = cz("A2", 8.50, 12.30, 0)     # boşluk 0.75 (brief metni) -> alt kapsam 12.30

# ── 1. Ortak ölçüm ──
o = kiris_kenarlari_olc([UST, ALT_A, ALT_B_090], CM)
kontrol("3 çizgi kabul (sınır yok), iki kenar", o["hata"] == "" and len(o["kenarlar"]) == 2, o)
kontrol("L_beton = 12.45 (boşluk 0.90)", o["l_beton_m"] == 12.45, o["l_beton_m"])
alt = min(o["kenarlar"], key=lambda k: k["dolu_m"])
kontrol("alt yüz dolu 11.55, kapsam 12.45, 2 parça", (alt["dolu_m"], alt["kapsam_m"], alt["parca"]) == (11.55, 12.45, 2), alt)
kontrol("tüm parça handle'ları", set(o["handleler"]) == {"U1", "A1", "A2"})
kontrol("bölünmüş kenar notu", any("bölünmüş kenar" in n for n in o["notlar"]))
o75 = kiris_kenarlari_olc([UST, ALT_A, ALT_B_075], CM)
kontrol("brief metnindeki 0.75 boşlukla L_beton = (12.45+12.30)/2 = 12.375", o75["l_beton_m"] == 12.375, o75["l_beton_m"])
kontrol("0.75 boşlukla dolu yine 11.55", min(k["dolu_m"] for k in o75["kenarlar"]) == 11.55)
kontrol("0.15 m fark < 2b (b=20) -> uyarı yok", kenar_eksik_secim_uyarisi(12.30, 12.45, 20) == "")

# Eksik parça: alt kenarın yalnız 7.75'i
oe = kiris_kenarlari_olc([UST, ALT_A], CM)
u = kenar_eksik_secim_uyarisi(oe["kenarlar"][0]["kapsam_m"], oe["kenarlar"][1]["kapsam_m"], 20)
kontrol("yalnız 7.75 seçilince uyarı", "parçası seçilmemiş" in u, u)
kontrol("2b sınırı: fark tam 2b -> uyarı yok", kenar_eksik_secim_uyarisi(4.0, 4.5, 25) == "")

# Hatalar
kontrol("tek çizgi -> en az 2", "en az 2" in kiris_kenarlari_olc([UST], CM)["hata"])
dik = {"handle": "D1", "uzunluk_birim": 30, "bas": (1245, 0), "son": (1245, 30), "hata": ""}
kontrol("dik uç çizgisi -> iki kenara ayrılamadı + neden",
        "ayrılamadı" in kiris_kenarlari_olc([UST, ALT_A, ALT_B_090, dik], CM)["hata"])
kontrol("üst üste çift parça tekilleşir", kiris_kenarlari_olc([UST, ALT_A, dict(ALT_A, handle="A9"), ALT_B_090], CM)
        ["kenarlar"][0]["dolu_m"] == 11.55)

# ── 2. SBH ──
def sbh_okuma(cizgiler, g=20, y=165):
    return {"yazilar": [{"ad": "SBH-1", "genislik_cm": g, "yukseklik_cm": y, "handle": "Y1", "uyari": ""}],
            "gecersiz_yazilar": [], "cizgiler": cizgiler, "notlar": []}


d = temel_kirisi_secim_degerlendir(sbh_okuma([UST, ALT_A, ALT_B_090]), "cm")
kontrol("SBH 3 çizgi geçerli, L = 12.45", d["gecerli"] and d["uzunluk_m"] == 12.45, d)
kontrol("SBH yan dolu [11.55, 12.45]", sorted(d["yan_dolu_m"]) == [11.55, 12.45], d["yan_dolu_m"])
h = temel_kirisi_hesapla(20, 165, d["uzunluk_m"], d["yan_dolu_m"])
kontrol("SBH beton 0.2×1.65×12.45 = 4.109", h["beton_m3"] == round(0.2 * 1.65 * 12.45, 3), h)
kontrol("SBH kalıp 1.65×(12.45+11.55) = 39.6", h["kalip_m2"] == 39.6, h)
kontrol("SBH eksik uyarısı yok", d["eksik_uyari"] == "")
de = temel_kirisi_secim_degerlendir(sbh_okuma([UST, ALT_A]), "cm")
kontrol("SBH yalnız 7.75 -> eksik_uyari", "parçası seçilmemiş" in de["eksik_uyari"], de)
kontrol("SBH tek çizgi -> hata (en az 2)", "en az 2" in temel_kirisi_secim_degerlendir(sbh_okuma([UST]), "cm")["hata"])
kontrol("SBH çizgisiz -> elle yolu korunur", temel_kirisi_secim_degerlendir(sbh_okuma([]), "cm")["elle_gerekli"])
# Düz kiriş değişmedi (koordinatsız 2 çizgi = eski test verisi)
dd = temel_kirisi_secim_degerlendir(sbh_okuma([{"handle": "A", "uzunluk_birim": 500, "hata": ""},
                                              {"handle": "B", "uzunluk_birim": 510, "hata": ""}]), "cm")
hd = temel_kirisi_hesapla(20, 165, dd["uzunluk_m"], dd["yan_dolu_m"])
kontrol("SBH düz 500/510 -> L 5.05, beton 1.667, kalıp 16.665 (eskiyle aynı)",
        (dd["uzunluk_m"], hd["beton_m3"], hd["kalip_m2"]) == (5.05, 1.667, 16.665), (dd, hd))
kontrol("SBH düz kaynak metni eski biçim", dd["kaynak"] == "Çizgi ort. (5.00/5.10)", dd["kaynak"])
kontrol("temel_kirisi_hesapla yan verilmezse 2yL", temel_kirisi_hesapla(20, 165, 5.0)["kalip_m2"] == 16.5)

# ── 3. K (normal kiriş) ──
def k_okuma(cizgiler):
    return {"yazilar": [{"handle": "Y1", "metin": "K101 (25/50)"}], "cizgiler": cizgiler}


ust = cz("U1", 0, 12.45, 0.25)
dk = kiris_secim_degerlendir(k_okuma([ust, ALT_A, ALT_B_090]), "cm", 1.0)
kontrol("K: L1/L2 kapsam 12.45/12.45, d 11.55/12.45",
        (dk["l1_m"], dk["l2_m"], dk["d1_m"], dk["d2_m"]) == (12.45, 12.45, 11.55, 12.45), dk)
hk = kiris_hesapla(25, 50, dk["l1_m"], "İç", 12, dk["l2_m"], dk["d1_m"], dk["d2_m"])
kontrol("K beton 0.25×0.5×12.45 = 1.5563", hk["beton_m3"] == round(0.25 * 0.5 * 12.45, 4), hk)
kontrol("K yan (0.38)×(11.55+12.45) = 9.12", hk["yan_kalip_m2"] == 9.12, hk)
kontrol("K alt 0.25×12.45", hk["alt_kalip_m2"] == round(0.25 * 12.45, 4))
# Yamuk 1.00 / 1.50 değişmedi
y1, y2 = cz("P", 0, 1.0, 0), cz("Q", -0.25, 1.25, 0.25)
dy = kiris_secim_degerlendir(k_okuma([y1, y2]), "cm", 1.0)
hy = kiris_hesapla(25, 50, dy["l1_m"], "İç", 12, dy["l2_m"], dy["d1_m"], dy["d2_m"])
eski = kiris_hesapla(25, 50, 1.0, "İç", 12, 1.5)
kontrol("yamuk 1.00/1.50 sonuç eskiyle aynı (beton/alt/yan)",
        (dy["l1_m"], dy["l2_m"]) == (1.0, 1.5) and all(hy[k] == eski[k] for k in
                                                      ("beton_m3", "alt_kalip_m2", "yan_kalip_m2")), (hy, eski))
kontrol("yamuk fark 0.5 = 2b -> uyarı yok", dy["eksik_uyari"] == "")
dz = kiris_secim_degerlendir(k_okuma([cz("P", 0, 4, 0), cz("Q", 0, 4, 0.25)]), "cm", 1.0)
kontrol("düz kiriş 4/4 -> 0.500 / 4.04 (değişmedi)",
        kiris_hesapla(25, 50, dz["l1_m"], "İç", 12, dz["l2_m"], dz["d1_m"], dz["d2_m"])["toplam_kalip_m2"] == 4.04)
kontrol("kenar kiriş: dolu uzun kenarı izler", kiris_hesapla(25, 50, 12.45, "Kenar", 12, 12.0, 11.55, 12.0)
        ["yan_kalip_m2"] == round(0.38 * 12.0 + 0.5 * 11.55, 4))
kontrol("dolu > kapsam -> hata", kiris_hesapla(25, 50, 4, "İç", 12, 4, 5, 4)["hata"] != "")


# ── 4. SBH paneli: eksik uyarısı Evet/Hayır, tüm parçalar boyanır ──
class SbhCon:
    bagli = True

    def __init__(self, okumalar, cevaplar):
        self.okumalar, self.cevaplar, self.yesil, self.mesajlar = list(okumalar), list(cevaplar), set(), []
        self.sorular = []

    def temel_kirisi_toplu_baslat(self):
        pass

    def temel_kirisi_kiris_oku(self):
        return self.okumalar.pop(0) if self.okumalar else {"durum": "bos_secim"}

    def temel_kirisi_mesaj(self, m):
        self.mesajlar.append(m)

    def komut_satiri_evet_hayir(self, istem, varsayilan=None):
        self.sorular.append((istem, set(self.yesil)))
        return self.cevaplar.pop(0)

    def obje_isaretle_hizli(self, h):
        self.yesil.add(h)

    def obje_isaret_geri_al(self, h):
        self.yesil.discard(h)


def sbh(cizgiler, yh="Y1"):
    r = sbh_okuma(cizgiler)
    r["yazilar"][0]["handle"] = yh
    r["durum"] = "okundu"
    r["diger_sayisi"] = 0
    return r


c = SbhCon([sbh([UST, ALT_A, ALT_B_090])], [])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
s = p.sonuclar()
kontrol("panel: 3 çizgili SBH eklendi, soru yok", len(s) == 1 and c.sorular == [], (s, c.sorular))
kontrol("panel: L 12.45, kalıp 39.6", s[0]["uzunluk_m"] == 12.45 and s[0]["kalip_m2"] == 39.6, s[0])
kontrol("panel: 3 parça + yazı yeşil, hepsi satırda", c.yesil == {"Y1", "U1", "A1", "A2"}
        and set(s[0]["cizgi_handleler"]) == {"U1", "A1", "A2"})
kontrol("panel: satırda yan dolu kayıtlı", sorted(s[0]["yan_dolu_m"]) == [11.55, 12.45])

c = SbhCon([sbh([UST, ALT_A])], [False])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
kontrol("eksik: soru soruldu, sırada parçalar yeşildi",
        len(c.sorular) == 1 and {"U1", "A1"} <= c.sorular[0][1], c.sorular)
kontrol("eksik + Hayır -> atlandı, yeşil geri alındı", p.sonuclar() == [] and c.yesil == set(), c.yesil)
c = SbhCon([sbh([UST, ALT_A])], [True])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
s = p.sonuclar()
kontrol("eksik + Evet -> alındı, uyarı satırda", len(s) == 1 and any("seçilmemiş" in u for u in s[0]["uyarilar"]), s)

# Mükerrer / güncelleme: aynı yazı, eksik parça sonradan eklenir -> tek satır, A2 de satırda
c = SbhCon([sbh([UST, ALT_A]), sbh([UST, ALT_A, ALT_B_090])], [True])
p = maw.TemelKirisiDonguPaneli(c, "cm")
p._dongu()
s = p.sonuclar()
kontrol("aynı yazı yeniden seçilince satır güncellenir (tek satır, 3 parça)",
        len(s) == 1 and set(s[0]["cizgi_handleler"]) == {"U1", "A1", "A2"} and s[0]["uzunluk_m"] == 12.45, s)

# Pencere: elle L düzeltmesi yan dolu bilgisini düşürür
win = maw.MetrajAnalizWindow()
kayit = dict(s[0])
kayit.pop("yeni_boyanan", None)
win.temel_kirisi_kayitlari["Y1"] = kayit
win._temel_kirisi_tablo_yenile()
item = win.temel_kirisi_table.item(0, win.TK_UZUNLUK_KOL)
item.setText("10")   # itemChanged -> _temel_kirisi_hucre_degisti (tablo yenilenir)
k = win.temel_kirisi_kayitlari["Y1"]
kontrol("elle L=10 -> kalıp 2×1.65×10 = 33, yan dolu düşüldü", k["kalip_m2"] == 33.0 and "yan_dolu_m" not in k, k)
dem = win._temel_kirisi_demir(dict(kayit, uzunluk_m=12.45))
kontrol("SBH demiri L_beton ile (tevzi uzunluğu L'ye bağlı)", not dem.get("hata"), dem)


# ── 5. K paneli ──
class KCon:
    bagli = True

    def __init__(self, okumalar, cevaplar):
        self.kuyruk, self.cevaplar, self.mesajlar, self.renk, self.orijinal = list(okumalar), list(cevaplar), [], {}, {}

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
        return None

    def obje_renklendir_hizli(self, h, renk):
        self.orijinal.setdefault(h, 7)
        self.renk[h] = int(renk)

    def obje_isaret_geri_al(self, h):
        if h in self.orijinal:
            self.renk[h] = self.orijinal.pop(h)


def ksec(cizgiler):
    r = k_okuma(cizgiler)
    r["durum"] = "okundu"
    return r


kc = KCon([ksec([ust, ALT_A, ALT_B_090])], [True])   # ilk teyit
kp = maw.KirisDonguPaneli(kc, "cm", "1:1", 1.0, 12.0, "İç", False, [], None)
kp._dongu()
kontrol("K panel: 3 çizgili kiriş eklendi", len(kp.kayitlar) == 1 and set(kp.kayitlar[0]["handleler"]) == {"Y1", "U1", "A1", "A2"})
kontrol("K panel: tablo kalıp = 0.25×12.45 + 9.12 = 12.23", kp.table.item(0, 8).text() == "12.2", kp.table.item(0, 8).text())
kontrol("K panel: tüm parçalar turuncu", all(kc.renk.get(x) == int(AcadColor.ORANGE) for x in ("U1", "A1", "A2")))

kc = KCon([ksec([ust, ALT_A])], [True, False])        # teyit Evet, eksik Hayır
kp = maw.KirisDonguPaneli(kc, "cm", "1:1", 1.0, 12.0, "İç", False, [], None)
kp._dongu()
kontrol("K eksik + Hayır -> alınmadı, renk geri", kp.kayitlar == [] and not any(
    v == int(AcadColor.ORANGE) for v in kc.renk.values()), (kp.kayitlar, kc.renk))
kontrol("K eksik sorusu soruldu", any("seçilmemiş" in m for m in kc.mesajlar))

win.kiris_kayitlari = [dict(kayit_k) for kayit_k in [{"ad": "K1", "b_cm": 25, "h_cm": 50, "l1_m": 12.45, "l2_m": 12.45,
                                                     "d1_m": 11.55, "d2_m": 12.45, "tip": "İç", "t_cm": 12,
                                                     "kaynak": "Çizim", "handleler": []}]]
hs = win._kiris_satir_hesap(win.kiris_kayitlari[0])
kontrol("pencere/Kat Özeti hesabı da dolu uzunluğu kullanır", hs["yan_kalip_m2"] == 9.12, hs)

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
