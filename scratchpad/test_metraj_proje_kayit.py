"""Rev-168 — Metraj projesi kaydet / aç + otomatik kayıt.

1) Saf: tuple/int anahtarlı sözlük, tuple köşeler, DemirBilgisi, KatYukseklikAyari gidiş-dönüş birebir;
   atomik yazma + bozuk dosyada .onceki.json'a düşme
2) Pencere: her sekmeye veri -> kaydet -> YENİ pencere -> aç -> registry'ler, tablolar, Kat Özeti,
   Beton & Kalıp elle satırı (tam değer), kat listesi ve ayarlar aynı
3) Otomatik kayıt: parent'lı (gerçek program) pencere açılışta yükler, kapanırken kaydeder;
   değişiklik yoksa yazmaz; parent'sız (test) pencere gerçek dosyaya dokunmaz
"""
import json
import os
import sys
import tempfile
from pathlib import Path

VERI = tempfile.mkdtemp()
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QUANTIX_DATA_DIR"] = VERI
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

from app.core import metraj_proje_kayit as pk  # noqa: E402
from app.core.autocad_connector import DemirBilgisi, KatYukseklikAyari  # noqa: E402

GECEN = KALAN = 0


def kontrol(ad, kosul, detay=""):
    global GECEN, KALAN
    GECEN, KALAN = (GECEN + 1, KALAN) if kosul else (GECEN, KALAN + 1)
    print(("PASS  " if kosul else "FAIL  ") + ad + (f"   [{detay}]" if detay else ""))


SINIF = {"DemirBilgisi": DemirBilgisi, "KatYukseklikAyari": KatYukseklikAyari}
d = DemirBilgisi(handle="A1", orijinal_metin="8Ø12 L=300", adet=8, cap=12, boy=300.0, toplam_boy=24.0,
                 agirlik_birim=0.888, toplam_agirlik=21.3, gecerli=True)
durum = {
    "tuple_anahtar": {("1. Kat", "S259"): {"en_m": 2.1, "tip": "Perde"}},
    "int_anahtar": {12: {"adet": 8}, 14: {"adet": 2}},
    "koseler": [(0.0, 0.0), (600.0, 0.0), (600.0, 500.0)],
    "demir": [d], "ayar": {"Zemin": KatYukseklikAyari(3.0, 0.2, "tam")},
    "none": None, "bos": {}, "turkce": "Döşeme / Saçak ığüşöç",
}
geri = pk.coz(json.loads(json.dumps(pk.serilestir(durum))), SINIF)
kontrol("gidiş-dönüş BİREBİR (tuple/int anahtar, tuple köşe, dataclass, Türkçe)", geri == durum, str(geri)[:200])
kontrol("dataclass türü korunur", isinstance(geri["demir"][0], DemirBilgisi)
        and isinstance(geri["ayar"]["Zemin"], KatYukseklikAyari))

yol = Path(VERI) / "dene.json"
pk.kaydet(yol, {"a": 1})
pk.kaydet(yol, {"a": 2})
kontrol("ikinci kayıtta eskisi .onceki.json", json.load(open(yol.with_name("dene.onceki.json"),
                                                           encoding="utf-8"))["durum"] == {"a": 1})
yol.write_text("{bozuk json", encoding="utf-8")
v = pk.yukle(yol)
kontrol("ana dosya bozuksa ÖNCEKİ sürüm yüklenir (veri kaybolmaz)", v["durum"] == {"a": 1}
        and v["yuklenen_dosya"].endswith(".onceki.json"))
kontrol("güvenli dosya adı", pk.guvenli_dosya_adi('Yurt / A:Blok*') == "Yurt - A - Blok")

# ── 2) Pencere ──
from PyQt6.QtWidgets import QApplication, QMessageBox, QMainWindow, QFileDialog  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
for ad in ("warning", "information", "critical"):
    setattr(QMessageBox, ad, staticmethod(lambda *a, **k: None))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
import app.ui.metraj_analiz_window as maw  # noqa: E402

maw.QTimer.singleShot = staticmethod(lambda *a, **k: None)


def doldur(w):
    for kat in ("1. Kat", "2. Kat"):
        w.demir_kat_input.setText(kat)
        w._demir_kat_ekle()
    w.demir_kat_verileri[0]["demirler"].append(d)
    w.aralikli_donati_kayitlari[("1. Kat", "A1")] = d
    w.perde_doseme_otomatik_chk.setChecked(False)
    w.perde_yukseklik_spin.setValue(3.0)
    w.perde_doseme_spin.setValue(0.2)
    w.aktif_kat_adi = "1. Kat"
    w._aktif_kat_degisti()
    w._perde_ayar_degisti()
    w.beton_kalip_kolon_kayitlari[("1. Kat", "S259")] = {"en_m": 2.1, "boy_m": 0.3, "en_cm": 210, "boy_cm": 30,
                                                         "kat_yuk_m": 3.0, "beton": 0, "kalip": 0, "tip": "Perde"}
    w.beton_kalip_kolon_kayitlari[("1. Kat", "SZ07")] = {"en_m": 0.5, "boy_m": 0.5, "kat_yuk_m": 3.0,
                                                         "beton": 0, "kalip": 0, "tip": "Kolon"}
    w.okunamayan_elemanlar[("1. Kat", "S260")] = "Y4"
    w.perde_kayitlari[("1. Kat", "P1")] = {"ad": "P1", "poligon_handle": "P1", "alan_m2": 1.0, "cevre_m": 8.5,
                                            "dusulen_m": 0.0, "handleler": ["P1"], "uyari": ""}
    w.doseme_kayitlari = [
        {"ad": "D1", "brut_alan_m2": 30.0, "bosluk_alan_m2": 5.0, "bosluk_cevre_m": 9.0, "serbest_kenar_m": 0,
         "kalinlik_cm": 15.0, "kaynak": "Tıklama", "handle": "H1", "koseler": [(0, 0), (600, 0), (600, 500), (0, 500)],
         "bosluklar": [{"koseler": [(100, 100), (300, 100), (300, 350), (100, 350)], "alan_m2": 5.0,
                        "cevre_m": 9.0, "handle": "H2"}]},
        {"tip": "Saçak", "sacak_tipi": "Şerit", "ad": "SÇ1", "brut_alan_m2": 9.6, "bosluk_alan_m2": 0,
         "bosluk_cevre_m": 0, "serbest_kenar_m": 13.6, "kalinlik_cm": 16.0, "kaynak": "Saçak-Şerit",
         "handle": "H3", "ic_handle": None, "koseler": [(0, 0), (1200, 0), (1200, -80), (0, -80)],
         "ic_koseler": [], "cevre_m": 25.6, "kiris_m": 12.0, "bosluklar": []}]
    w._doseme_tablo_yenile()
    w.kiris_ad_edit.setText("K101")
    w.kiris_b_spin.setValue(25)
    w.kiris_h_spin.setValue(50)
    w.kiris_l_spin.setValue(4.0)
    w.kiris_t_spin.setValue(15)
    w._kiris_elle_ekle()
    w.merdiven_kol_ad_edit.setText("M1")
    w.merdiven_n_spin.setValue(10)
    w.merdiven_h_spin.setValue(15)
    w.merdiven_a_spin.setValue(30)
    w.merdiven_b_spin.setValue(120)
    w.merdiven_t_spin.setValue(15)
    w._merdiven_kol_ekle()
    w.temel_kirisi_kayitlari["T1"] = {"ad": "SBH-1", "genislik_cm": 20, "yukseklik_cm": 100, "uzunluk_m": 5,
                                      "beton_m3": 1.0, "kalip_m2": 10.0}
    w.radye_ad_edit.setText("Ana Blok")
    w.radye_alan_spin.setValue(250)
    w.radye_kalinlik_spin.setValue(60)
    w.radye_dis_cevre_spin.setValue(70)
    w._radye_ekle()
    w.bk_eleman_combo.setCurrentText("Kolon")
    w.bk_fire_spin.setValue(5.0)
    for spin, v in ((w.bk_adet_spin, 1), (w.bk_dim1_spin, 0.5), (w.bk_dim2_spin, 0.5), (w.bk_dim3_spin, 1.0)):
        spin.setValue(v)
    w._beton_kalip_kalem_ekle()
    w._beton_kalip_kat_kolon_satirlarini_yeniden_olustur("1. Kat")
    w._perde_tablo_yenile()
    w._beton_kalip_toplamlar_guncelle()
    w.sacak_kalinlik_spin.setValue(18.0)


def tablo(t):
    return [[t.item(r, c).text() if t.item(r, c) else "" for c in range(t.columnCount())] for r in range(t.rowCount())]


def ozet(w):
    w._kat_ozeti_yenile()
    return tablo(w.kat_ozeti_table)


w1 = maw.MetrajAnalizWindow()
kontrol("test penceresi (parent yok) otomatik kayıt KAPALI", not w1._otomatik_kayit_acik)
doldur(w1)
ozet1, bk1, dos1, kiris1, mer1 = ozet(w1), tablo(w1.beton_kalip_table), tablo(w1.doseme_table), \
    tablo(w1.kiris_table), tablo(w1.merdiven_table)
toplam1 = (w1.bk_toplam_beton_label.text(), w1.bk_toplam_kalip_label.text())
kayit_yolu = Path(VERI) / "metraj_projeleri" / "test_proje.json"
kontrol("kaydet", w1._proje_dosyaya_yaz(kayit_yolu) and kayit_yolu.exists())

w2 = maw.MetrajAnalizWindow()
kontrol("yeni pencere boş", not w2.demir_kat_verileri and w2.beton_kalip_table.rowCount() == 0)
kontrol("aç", w2._proje_yukle(kayit_yolu))
kontrol("kat listesi + aktif kat geri geldi", [k["kat_adi"] for k in w2.demir_kat_verileri] == ["1. Kat", "2. Kat"]
        and w2.aktif_kat_adi == "1. Kat" and w2.demir_kat_listesi.count() == 2)
kontrol("demir (DemirBilgisi) + aralıklı donatı registry", isinstance(w2.demir_kat_verileri[0]["demirler"][0], DemirBilgisi)
        and w2.demir_kat_verileri[0]["demirler"][0].toplam_agirlik == 21.3
        and ("1. Kat", "A1") in w2.aralikli_donati_kayitlari)
for ad in ("beton_kalip_kolon_kayitlari", "okunamayan_elemanlar", "perde_kayitlari", "_doseme_kat_kayitlari",
           "_kiris_kat_kayitlari", "_merdiven_kat_kayitlari", "temel_kirisi_kayitlari", "radye_kayitlari"):
    kontrol(f"registry birebir: {ad}", getattr(w2, ad) == getattr(w1, ad), str(getattr(w2, ad))[:120])
kontrol("kat ayarı (KatYukseklikAyari) aynı", w2.kat_yukseklik_ayarlari == w1.kat_yukseklik_ayarlari)
kontrol("Kat Özeti tablosu birebir aynı", ozet(w2) == ozet1, str(ozet(w2))[:200])
kontrol("Beton & Kalıp tablosu (elle + kolon/perde satırları) aynı", sorted(tablo(w2.beton_kalip_table)) == sorted(bk1))
kontrol("Beton & Kalıp toplamları aynı (elle satırın TAM değeri korundu)",
        (w2.bk_toplam_beton_label.text(), w2.bk_toplam_kalip_label.text()) == toplam1, str(toplam1))
kontrol("Döşeme + Saçak, Kiriş, Merdiven tabloları aynı",
        tablo(w2.doseme_table) == dos1 and tablo(w2.kiris_table) == kiris1 and tablo(w2.merdiven_table) == mer1)
kontrol("ayarlar ilk penceredekiyle aynı (perde otomatik KAPALI, perde döşemesi, saçak 18 elle)",
        (w2.perde_doseme_otomatik_chk.isChecked(), w2.perde_doseme_spin.value(), w2.sacak_kalinlik_spin.value(),
         w2._sacak_kalinlik_elle) == (False, w1.perde_doseme_spin.value(), 18.0, True))
kontrol("SBH ve radye tabloları dolu", w2.temel_kirisi_table.rowCount() >= 1 and len(w2.radye_kayitlari) == 1)
kontrol("durum çubuğunda özet", "Yüklendi" in w2.proje_kayit_label.text() and "kiriş 1" in w2.proje_kayit_label.text(),
        w2.proje_kayit_label.text())

# ── 3) Otomatik kayıt (gerçek program gibi: parent'lı) ──
ana = QMainWindow()
w3 = maw.MetrajAnalizWindow(ana)
kontrol("parent'lı pencere: otomatik kayıt AÇIK, dosya 'Genel.json'",
        w3._otomatik_kayit_acik and w3._kayit_dosyasi.name == "Genel.json")
doldur(w3)
w3._otomatik_kaydet()
genel = Path(VERI) / "metraj_projeleri" / "Genel.json"
kontrol("otomatik kayıt yazıldı", genel.exists())
mtime = genel.stat().st_mtime_ns
w3._otomatik_kaydet()
kontrol("değişiklik yoksa tekrar yazmaz", genel.stat().st_mtime_ns == mtime)
w3.okunamayan_elemanlar[("2. Kat", "S999")] = None
w3.close()
kontrol("pencere kapanırken son değişiklik kaydedildi",
        ("2. Kat", "S999") in pk.yukle(genel, SINIF)["durum"]["okunamayan_elemanlar"])
mtime_kapanis = genel.stat().st_mtime_ns
ana4 = QMainWindow()
w4 = maw.MetrajAnalizWindow(ana4)
kontrol("PC çökmesi / yeniden açılış: yeni pencere AÇILIŞTA otomatik yükledi (soru yok), Kat Özeti aynı",
        ("2. Kat", "S999") in w4.okunamayan_elemanlar and ozet(w4) == ozet1, str(ozet(w4))[:150])
w4._otomatik_kaydet()
kontrol("açılış yüklemesinden sonra değişiklik yoksa dosyaya yeniden yazılmaz",
        genel.stat().st_mtime_ns == mtime_kapanis)
w5 = maw.MetrajAnalizWindow()
w5._otomatik_kaydet()
kontrol("parent'sız pencere otomatik kayıt yapmaz (Genel.json'a dokunmaz)",
        ("2. Kat", "S999") in pk.yukle(genel, SINIF)["durum"]["okunamayan_elemanlar"])

# Proje Aç / Farklı Kaydet akışları (dosya diyaloğu yamalı)
farkli = Path(VERI) / "baska_yer" / "kopya.json"
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(farkli.with_suffix("")), ""))
w2._proje_farkli_kaydet()
kontrol("Farklı Kaydet: .json eklendi, sonraki kayıtlar bu dosyaya", farkli.exists() and w2._kayit_dosyasi == farkli)
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(farkli), ""))
w6 = maw.MetrajAnalizWindow()
w6._proje_ac()
kontrol("Proje Aç: kopyadan açıldı", w6.radye_kayitlari == w1.radye_kayitlari and w6._kayit_dosyasi == farkli)
kontrol("araç çubuğu: Kaydet / Farklı Kaydet… / Proje Aç…", [a.text() for a in w6.findChildren(maw.QAction)
                                                           if a.text() in ("Kaydet", "Farklı Kaydet…", "Proje Aç…")]
        == ["Kaydet", "Farklı Kaydet…", "Proje Aç…"])

print(f"\nSONUÇ: {GECEN} PASS, {KALAN} FAIL")
sys.exit(1 if KALAN else 0)
