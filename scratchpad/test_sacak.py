"""Rev-164 — Döşeme aracında SAÇAK modu ([H]alka / [Ş]erit).

1) Programsız (brief): Halka dış 13.6×11.6, iç 12×10, t=16 -> 37.76 / 6.042 / 45.82;
   Şerit kiriş 12 m, uç 12 m (0.80 dışarı), t=16 -> 9.60 / 1.536 / 11.78; uç ters -> aynı;
   iç dışa taşarsa uyarı
2) Panel (sahte connector): H ve S akışı, kehribar çizim, mükerrer sorusu, geri al, iptal
3) Pencere: Tip sütunu, Kat Özeti "Saçak" satırı, kalınlık varsayılanı, perde döşemesine karışmaz
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QUANTIX_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from app.core.autocad_connector import (  # noqa: E402
    sacak_halka_degerlendir, sacak_serit_degerlendir, sacak_hesapla, hakim_doseme_kalinligi_cm, SACAK_RENK,
)

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"   [{detay}]" if detay else ""))


def dik(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


# ── 1) Programsız ──
DIS, IC = dik(0, 0, 1360, 1160), dik(80, 80, 1280, 1080)   # cm
h = sacak_halka_degerlendir(DIS, IC, "cm")
r = sacak_hesapla(h["alan_m2"], 16, h["kenar_m"])
kontrol("Halka: alan 37.76, kenar = dış çevre 50.4 (iç çevre 44 kalıba girmez)",
        h["alan_m2"] == 37.76 and h["kenar_m"] == 50.4 and h["kiris_m"] == 44.0, str(h["alan_m2"]))
kontrol("Halka t=16: beton 6.042, alt kalıp 37.76, toplam kalıp 37.76 + 50.4×0.16 = 45.82",
        r["beton_m3"] == 6.042 and r["alt_kalip_m2"] == 37.76 and round(r["toplam_kalip_m2"], 2) == 45.82, str(r))
h2 = sacak_halka_degerlendir(DIS, dik(80, 80, 1400, 1080), "cm")
kontrol("Halka: iç poligon dışa taşarsa uyarı, ALINMAZ", "İÇİNDE olmalı" in h2["hata"], h2["hata"])
kontrol("Halka: iç ile dış yer değiştirirse (iç büyük) de reddedilir",
        bool(sacak_halka_degerlendir(IC, DIS, "cm")["hata"]))
h50 = sacak_halka_degerlendir([(x * 10 / 50, y * 10 / 50) for x, y in DIS],
                              [(x * 10 / 50, y * 10 / 50) for x, y in IC], "mm", 50)
kontrol("Halka 1/50 mm çizim: aynı 37.76 / 50.4", h50["alan_m2"] == 37.76 and h50["kenar_m"] == 50.4)

K, U = [(0, 0), (1200, 0)], [(0, -80), (1200, -80)]
s = sacak_serit_degerlendir(K, U, "cm")
r = sacak_hesapla(s["alan_m2"], 16, s["kenar_m"])
kontrol("Şerit: alan 9.60, kenar = 12 + 0.80 + 0.80 = 13.60, kiriş hattı 12",
        s["alan_m2"] == 9.6 and s["kenar_m"] == 13.6 and s["kiris_m"] == 12.0, str(s))
kontrol("Şerit t=16: beton 1.536, toplam kalıp 9.60 + 13.6×0.16 = 11.78",
        r["beton_m3"] == 1.536 and round(r["toplam_kalip_m2"], 2) == 11.78, str(r))
s2 = sacak_serit_degerlendir(K, list(reversed(U)), "cm")
kontrol("Şerit: uç hattı TERS tıklanınca aynı sonuç (papyon yok)",
        (s2["alan_m2"], s2["kenar_m"], s2["hata"]) == (9.6, 13.6, ""), str(s2))
s3 = sacak_serit_degerlendir(list(reversed(K)), U, "cm")
kontrol("Şerit: kiriş hattı ters tıklanınca da aynı", (s3["alan_m2"], s3["kenar_m"]) == (9.6, 13.6))
# L şerit: iki cephe (kiriş 12 + 10, uç 0.80 dışarıda)
KL = [(0, 1000), (0, 0), (1200, 0)]
UL = [(-80, 1000), (-80, -80), (1200, -80)]
sl = sacak_serit_degerlendir(KL, UL, "cm")
kontrol("L şerit (iki cephe): alan 12×0.8 + 10×0.8 + 0.8×0.8 = 18.24, kenar = uç hattı (12.8 + 10.8) + 2×0.8 = 25.2",
        abs(sl["alan_m2"] - 18.24) < 1e-9 and abs(sl["kenar_m"] - 25.2) < 1e-9, str((sl["alan_m2"], sl["kenar_m"])))
kontrol("Şerit: tek noktalı hat -> hata", bool(sacak_serit_degerlendir([(0, 0)], U, "cm")["hata"]))
kontrol("hakim döşeme kalınlığı saçak satırını SAYMAZ",
        hakim_doseme_kalinligi_cm([{"kalinlik_cm": 16, "brut_alan_m2": 50},
                                   {"tip": "Saçak", "kalinlik_cm": 12, "brut_alan_m2": 500}]) == 16)

# ── 2) Panel ──
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
import app.ui.metraj_analiz_window as maw  # noqa: E402

maw.QTimer.singleShot = staticmethod(lambda *a, **k: None)
E = ("enter", None)


def N(x, y):
    return ("nokta", (x, y))


def poli(koseler):
    return [N(*p) for p in koseler] + [E]


class Sahte:
    bagli = True

    def __init__(self):
        self.noktalar, self.secenekler, self.cevaplar = [], [], []
        self.mesajlar, self.cizilen, self.silinen, self._n = [], [], [], 0

    def komut_satiri_mesaj(self, m):
        self.mesajlar.append(m)

    def doseme_toplu_baslat(self):
        pass

    def doseme_toplu_bitir(self):
        return ""

    def doseme_nokta_al(self, istem, baz=None, anahtarlar=""):
        return self.noktalar.pop(0) if self.noktalar else E

    def komut_satiri_secenek(self, istem, anahtarlar):
        return self.secenekler.pop(0) if self.secenekler else None

    def komut_satiri_evet_hayir(self, istem, varsayilan=None):
        self.mesajlar.append("SORU: " + istem)
        return self.cevaplar.pop(0) if self.cevaplar else True

    def doseme_poligon_ciz(self, koseler, renk=None):
        self._n += 1
        self.cizilen.append((f"H{self._n}", renk))
        return f"H{self._n}"

    def obje_sil(self, h):
        self.silinen.append(h)
        return True


DOSEME = {"ad": "D1", "brut_alan_m2": 120.0, "bosluk_alan_m2": 0, "bosluk_cevre_m": 0, "serbest_kenar_m": 0,
          "kalinlik_cm": 16.0, "kaynak": "Tıklama", "handle": "DH", "koseler": IC, "cevre_m": 44, "bosluklar": []}
sc = Sahte()
p = maw.DosemeDonguPaneli(sc, "cm", "1:1", 1.0, 16.0, True, [DOSEME], mod="sacak", sacak_kalinlik_cm=16.0)
sc.secenekler = ["Halka", "Serit"]
sc.noktalar = poli(DIS) + poli(IC) + [N(*K[0]), N(*K[1]), E] + [N(*U[1]), N(*U[0]), E]
p._dongu()
k = p.kayitlar
kontrol("panel: D1 + SÇ1 (Halka) + SÇ2 (Şerit), tip Saçak",
        [s["ad"] for s in k] == ["D1", "SÇ1", "SÇ2"] and k[1]["tip"] == "Saçak" and k[2]["sacak_tipi"] == "Şerit",
        str([s["ad"] for s in k]))
kontrol("panel: halka saçak D1 için 'zaten kayıtlı' sorusu SORMADI (döşeme mükerrerine karışmaz)",
        not any("kayıtlı" in m for m in sc.mesajlar))
kontrol("panel: kehribar (ACI 40) çizildi — halkada dış + iç, şeritte tek poligon",
        [r for _, r in sc.cizilen] == [SACAK_RENK] * 3 and k[1]["ic_handle"] == "H2")
h1, h2 = p._hesap(k[1]), p._hesap(k[2])
kontrol("panel: SÇ1 beton 6.042 / kalıp 45.82, SÇ2 beton 1.536 / kalıp 11.78",
        h1["beton_m3"] == 6.042 and round(h1["toplam_kalip_m2"], 2) == 45.82
        and h2["beton_m3"] == 1.536 and round(h2["toplam_kalip_m2"], 2) == 11.78)
kontrol("panel tablosu Kaynak 'Saçak-Halka'", p.table.item(1, 6).text() == "Saçak-Halka")

# Mükerrer: aynı halka tekrar -> soru; Hayır -> çizim yok
sc.secenekler, sc.cevaplar = ["H"], [False]
sc.noktalar = poli(DIS) + poli(IC)
n = len(sc.cizilen)
p._dongu()
kontrol("mükerrer halka -> 'Bu saçak zaten SÇ1 olarak kayıtlı. Güncellensin mi?', Hayır -> çizim yok",
        any("zaten SÇ1 olarak kayıtlı" in m for m in sc.mesajlar) and len(sc.cizilen) == n and len(k) == 3)
# Evet -> güncellenir (eski poligonlar silinir), ad korunur
sc.secenekler, sc.cevaplar = ["H"], [True]
sc.noktalar = poli(DIS) + poli(IC)
p._dongu()
kontrol("mükerrer Evet -> SÇ1 güncellendi, eski H1/H2 silindi, satır sayısı aynı",
        len(p.kayitlar) == 3 and p.kayitlar[1]["ad"] == "SÇ1" and {"H1", "H2"} <= set(sc.silinen))
# Şerit mükerrer: uç ters yönde aynı şerit
sc.secenekler, sc.cevaplar = ["S"], [False]
sc.noktalar = [N(*K[0]), N(*K[1]), E] + [N(*U[0]), N(*U[1]), E]
p._dongu()
kontrol("aynı şerit tekrar -> SÇ2 için soru", any("zaten SÇ2 olarak kayıtlı" in m for m in sc.mesajlar))
# İç dışa taşan halka -> uyarı, kayıt yok
sc.secenekler = ["H"]
sc.noktalar = poli(DIS) + poli(dik(80, 80, 1400, 1080))
p._dongu()
kontrol("panel: iç taşan halka -> komut satırında uyarı, kayıt yok",
        any("İÇİNDE olmalı" in m for m in sc.mesajlar) and len(p.kayitlar) == 3)
# Geri al: güncellemeyi geri al -> eski SÇ1 yeniden çizilir (kehribar)
p._son_ekleneni_geri_al()
kontrol("geri al (güncelleme): eski SÇ1 kehribar yeniden çizildi (dış + iç)",
        sc.cizilen[-2:][0][1] == SACAK_RENK and sc.cizilen[-1][1] == SACAK_RENK and p.kayitlar[1]["ad"] == "SÇ1")
p._son_ekleneni_geri_al()
kontrol("geri al (şerit ekleme): SÇ2 ve poligonu gitti", len(p.kayitlar) == 2 and "H3" in sc.silinen)
p._iptal()
kontrol("iptal: oturumun tüm saçakları gitti, D1 (önceki oturum) duruyor",
        [s["ad"] for s in p.kayitlar] == ["D1"])

# Döşeme modunda B ile saçağa boşluk eklenmez
sc2 = Sahte()
p2 = maw.DosemeDonguPaneli(sc2, "cm", "1:1", 1.0, 16.0, True, [dict(DOSEME), {
    "tip": "Saçak", "ad": "SÇ1", "brut_alan_m2": 9.6, "bosluk_alan_m2": 0, "bosluk_cevre_m": 0,
    "serbest_kenar_m": 13.6, "kalinlik_cm": 16, "kaynak": "Saçak-Şerit", "koseler": dik(0, -80, 1200, 0),
    "bosluklar": []}])
kontrol("_bosluk_ekle saçak satırına -> 'saçağa boşluk eklenmez'",
        p2._bosluk_ekle(1, sc2.komut_satiri_mesaj) == "bitti" and any("boşluk eklenmez" in m for m in sc2.mesajlar))

# ── 3) Pencere ──
win = maw.MetrajAnalizWindow()
win.demir_kat_input.setText("1. Kat")
win._demir_kat_ekle()
win.doseme_birim_combo.setCurrentText("cm")
win.doseme_kayitlari = [dict(DOSEME)]
win._doseme_tablo_yenile()
kontrol("saçak kalınlığı varsayılanı katın döşeme kalınlığı (16 cm)", win.sacak_kalinlik_spin.value() == 16.0)
sc3 = Sahte()
sc3.secenekler = ["Halka"]
sc3.noktalar = poli(DIS) + poli(IC)
win.acad_connector = sc3
maw.DosemeDonguPaneli.exec = lambda self: (self._dongu(), self.accept(), self.result())[2]
win._sacak_sec()
t = win.doseme_table
kontrol("Döşeme tablosu: 2 satır, Tip sütunu 'Döşeme' / 'Saçak (Halka)'",
        t.rowCount() == 2 and t.item(0, 12).text() == "Döşeme" and t.item(1, 12).text() == "Saçak (Halka)")
kontrol("tablo: saçak beton 6.04, toplam kalıp 45.82",
        t.item(1, 6).text() == "6.0" and t.item(1, 9).text() == "45.8")
kontrol("toplam etiketinde ayrı SAÇAK satırı", "SAÇAK: 1 adet" in win.doseme_toplam_label.text())
oz = {k["eleman"]: k for k in win._kat_ozeti_kalemleri() if k["kat"] == "1. Kat"}
kontrol("Kat Özeti: ayrı 'Saçak' kalemi 6.042 / 45.824, Döşeme ayrı",
        "Saçak" in oz and oz["Saçak"]["beton_m3"] == 6.042 and abs(oz["Saçak"]["kalip_m2"] - 45.824) < 1e-9
        and "Döşeme" in oz)
win._kat_ozeti_yenile()
kt = win.kat_ozeti_table
satirlar = [kt.item(r, 1).text() for r in range(kt.rowCount()) if kt.item(r, 0) and kt.item(r, 0).text() == "1. Kat"]
kontrol("Kat Özeti tablosunda Döşeme'den sonra 'Saçak' satırı",
        "Saçak" in satirlar and satirlar.index("Saçak") == satirlar.index("Döşeme") + 1, str(satirlar))
kontrol("perde otomatik döşeme kalınlığı saçaktan etkilenmez (16 cm D1)",
        win._perde_otomatik_doseme("1. Kat")[0] == 0.16)
win.sacak_kalinlik_spin.setValue(12.0)
win._doseme_tablo_yenile()
kontrol("saçak kalınlığı elle 12 yapılınca tablo yenilense de korunur", win.sacak_kalinlik_spin.value() == 12.0)
win.doseme_table.selectRow(1)
win.acad_connector = sc3
win._doseme_sil()
kontrol("saçak satırı silinince dış + iç poligon silinir", {"H1", "H2"} <= set(sc3.silinen))

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
