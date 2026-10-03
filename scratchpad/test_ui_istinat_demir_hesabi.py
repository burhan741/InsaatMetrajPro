"""Headless PyQt testi — "İSTİNAT DEMİR HESABI" butonu (Aşama 4 UI entegrasyonu).

Gerçek AutoCAD'e bağlanmadan, self.acad_connector'ı sahte (mock) bir
nesneyle değiştirip _autocad_poz_donati_oku()'nun uçtan uca doğru
çalıştığını (kat verisine ekleme, buton enable, mesaj kutusu akışı) ve
başlık bulunamayan tablo için manuel sütun sırası diyaloğu yolunun da
çalıştığını doğrular.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog
from app.ui.metraj_analiz_window import MetrajAnalizWindow
from app.core.autocad_connector import (
    tablo_hucrelerini_kumele,
    grid_den_poz_kayitlarini_cikar,
    poz_kayitlarindan_hesapla,
    poz_kayitlarini_demir_bilgisine_cevir,
)

QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: None)

# "Başka tablo var mı?" sorusuna verilecek yanıt sırası - test bunu
# doldurup bosaltir; bos kalırsa varsayılan No (dongu biter).
_SORU_YANITLARI = []


def _mock_question(*a, **k):
    if _SORU_YANITLARI:
        return _SORU_YANITLARI.pop(0)
    return QMessageBox.StandardButton.No


QMessageBox.question = staticmethod(_mock_question)


def _jit(i, genlik=0.04):
    return ((i * 37) % 7 - 3) * genlik


def _grid_baslikli():
    kolon_x = {"POZ": 0.0, "ADET": 100.0, "CAP": 200.0, "BOY": 300.0, "O12": 750.0, "O18": 850.0}
    baslik = {"POZ": "POZ", "ADET": "ADET", "CAP": "ÇAP", "BOY": "BOY", "O12": "Ø12", "O18": "Ø18"}
    satirlar = [(1, 20, 18, "5,30", "O18", "106,00"), (2, 16, 12, "5,25", "O12", "84,00")]
    hucreler = []
    i = 0

    def ekle(t, x, y):
        nonlocal i
        hucreler.append({"text": t, "x": x + _jit(i), "y": y + _jit(i + 1)})
        i += 1

    y = 500.0
    for k, x in kolon_x.items():
        ekle(baslik[k], x, y)
    y -= 60.0
    for poz, adet, cap, boy, kolon, toplam in satirlar:
        ekle(str(poz), kolon_x["POZ"], y)
        ekle(str(adet), kolon_x["ADET"], y)
        ekle(str(cap), kolon_x["CAP"], y)
        ekle(boy, kolon_x["BOY"], y)
        ekle(toplam, kolon_x[kolon], y)
        y -= 60.0
    return tablo_hucrelerini_kumele(hucreler)


def _grid_baslikSIZ():
    """Ayni veri ama baslik satiri yok - manuel sutun sirasi yolu icin.

    NOT: En az 2 veri satiri gerekli - tek satirla Y-ekseni kumelemesinin
    "gurultu vs gercek satir araligi" ayrimi icin sinyali olmuyor (bkz.
    CLAUDE.md Rev-128 "BILINEN SINIR" - ayni sinirin Y-ekseni versiyonu,
    tek-satirlik veride de ayni sekilde ortaya cikiyor). Gercek basliksiz
    tablolarda zaten cogunlukla birden fazla satir olur, bu yuzden production
    kodu icin degil sadece bu test fixture'i icin gecerli bir duzeltme.
    """
    kolon_x = {"POZ": 0.0, "ADET": 100.0, "CAP": 200.0, "BOY": 300.0, "O12": 750.0}
    satirlar = [(1, 10, 12, "2,00", "50,00"), (2, 5, 12, "1,00", "5,00")]
    hucreler = []
    i = 0

    def ekle(t, x, y):
        nonlocal i
        hucreler.append({"text": t, "x": x + _jit(i), "y": y + _jit(i + 1)})
        i += 1

    y = 100.0
    for poz, adet, cap, boy, toplam in satirlar:
        ekle(str(poz), kolon_x["POZ"], y)
        ekle(str(adet), kolon_x["ADET"], y)
        ekle(str(cap), kolon_x["CAP"], y)
        ekle(boy, kolon_x["BOY"], y)
        ekle(toplam, kolon_x["O12"], y)
        y -= 60.0
    return tablo_hucrelerini_kumele(hucreler)


class SahteConnector:
    """grid_ham tek bir grid ise HER cagride ayni grid'i dondurur (tek
    tablo testleri). Bir LISTE verilirse her cagride SIRADAKI grid'i
    dondurur (cok-tablo dongusu testi icin - her tur farkli bir tablo)."""

    def __init__(self, grid_ham):
        self.bagli = True
        if isinstance(grid_ham, list) and grid_ham and isinstance(grid_ham[0], list) and grid_ham[0] and isinstance(grid_ham[0][0], list):
            self._grid_kuyrugu = list(grid_ham)
            self._tekli_grid = None
        else:
            self._grid_kuyrugu = None
            self._tekli_grid = grid_ham

    def get_poz_bazli_donati_tablosu(self, **kwargs):
        if self._grid_kuyrugu is not None:
            grid_ham = self._grid_kuyrugu.pop(0) if self._grid_kuyrugu else []
        else:
            grid_ham = self._tekli_grid
        if not grid_ham:
            return {
                "secim_sayisi": 0, "metin_sayisi": 0, "grid": [], "grid_ham": [],
                "poz_kayitlari": {}, "hesap": {}, "basarili": [], "basarisiz": [],
                "toplam_adet": 0, "toplam_boy_m": 0.0, "toplam_agirlik_kg": 0.0, "cap_ozeti": {},
            }
        poz_kayitlari = grid_den_poz_kayitlarini_cikar(grid_ham)
        rapor = {
            "secim_sayisi": 99, "metin_sayisi": 50,
            "grid": [], "grid_ham": grid_ham,
            "poz_kayitlari": poz_kayitlari, "hesap": {},
            "basarili": [], "basarisiz": [], "toplam_adet": 0,
            "toplam_boy_m": 0.0, "toplam_agirlik_kg": 0.0, "cap_ozeti": {},
        }
        if poz_kayitlari["basarili"]:
            hesap = poz_kayitlarindan_hesapla(poz_kayitlari["basarili"])
            rapor["hesap"] = hesap
            rapor["basarili"] = poz_kayitlarini_demir_bilgisine_cevir(poz_kayitlari["basarili"])
            rapor["cap_ozeti"] = hesap["cap_ozeti"]
            rapor["toplam_adet"] = hesap["genel"]["adet"]
            rapor["toplam_boy_m"] = hesap["genel"]["boy_m"]
            rapor["toplam_agirlik_kg"] = hesap["genel"]["agirlik_kg"]
        return rapor


def test_buton_baslangicta_disabled():
    _SORU_YANITLARI.clear()
    app = QApplication.instance() or QApplication(sys.argv)
    win = MetrajAnalizWindow(db=None)
    assert win.btn_poz_donati.isEnabled() is False
    print("PASS: buton baslangicta disabled (AutoCAD baglantisi yok)")


def test_baslikli_tablo_uctan_uca():
    _SORU_YANITLARI.clear()
    app = QApplication.instance() or QApplication(sys.argv)
    win = MetrajAnalizWindow(db=None)
    win.acad_connector = SahteConnector(_grid_baslikli())
    win.demir_kat_verileri.append({"kat_adi": "Test Kat", "demirler": [], "rapor": None})
    win.aktif_kat_adi = "Test Kat"

    win._autocad_poz_donati_oku()

    kat = win.demir_kat_verileri[0]
    assert len(kat["demirler"]) == 2, f"2 poz beklenirdi, {len(kat['demirler'])} geldi"
    d1 = kat["demirler"][0]
    assert d1.adet == 20 and d1.cap == 18
    assert abs(d1.toplam_boy - 106.0) < 1e-6
    assert win.btn_demir_excel.isEnabled() is True
    assert win.btn_kesime_aktar.isEnabled() is True
    print(f"PASS: basliklit tablo uctan uca calisti ({len(kat['demirler'])} poz kata eklendi)")


def test_basliksiz_tablo_manuel_sutun_sirasi():
    _SORU_YANITLARI.clear()
    app = QApplication.instance() or QApplication(sys.argv)
    win = MetrajAnalizWindow(db=None)
    win.acad_connector = SahteConnector(_grid_baslikSIZ())
    win.demir_kat_verileri.append({"kat_adi": "Test Kat 2", "demirler": [], "rapor": None})
    win.aktif_kat_adi = "Test Kat 2"

    # QInputDialog.getText'i, gercek dialogu acmadan sabit bir yanit donecek
    # sekilde mock'la (grid 5 sutunlu: poz,adet,cap,boy,toplam).
    orijinal_gettext = QInputDialog.getText
    QInputDialog.getText = staticmethod(lambda *a, **k: ("poz,adet,cap,boy,toplam", True))
    try:
        win._autocad_poz_donati_oku()
    finally:
        QInputDialog.getText = orijinal_gettext

    kat = win.demir_kat_verileri[0]
    assert len(kat["demirler"]) == 2, f"2 poz beklenirdi, {len(kat['demirler'])} geldi"
    d1 = kat["demirler"][0]
    assert d1.adet == 10 and d1.cap == 12
    assert abs(d1.toplam_boy - 20.0) < 1e-6  # 10*2.00m
    d2 = kat["demirler"][1]
    assert d2.adet == 5 and d2.cap == 12
    assert abs(d2.toplam_boy - 5.0) < 1e-6  # 5*1.00m
    print("PASS: basliksiz tablo + manuel sutun sirasi diyalogu uctan uca calisti")


def test_coklu_tablo_dongusu():
    """Rev-132: kullanici gercek projede birden fazla ayri tablo oldugunu
    bildirdi (770 obje tek seciminde 6 tablo karisip 3x5 grid'e sikismisti).
    Cozum: kullanici tablolari TEK TEK secer, program her turdan sonra
    'baska tablo var mi?' diye sorar. Bu test 2 AYRI tabloyu (2. tablo
    farkli capta: Ø16) sirayla isleyip TEK bir kat'a dogru birikip
    birikmedigini dogrular."""
    _SORU_YANITLARI.clear()
    app = QApplication.instance() or QApplication(sys.argv)
    win = MetrajAnalizWindow(db=None)

    def _grid_tablo_b():
        kolon_x = {"POZ": 0.0, "ADET": 100.0, "CAP": 200.0, "BOY": 300.0, "O16": 750.0}
        baslik = {"POZ": "POZ", "ADET": "ADET", "CAP": "ÇAP", "BOY": "BOY", "O16": "Ø16"}
        hucreler, i = [], 0

        def ekle(t, x, y):
            nonlocal i
            hucreler.append({"text": t, "x": x + _jit(i), "y": y + _jit(i + 1)})
            i += 1

        y = 500.0
        for k, x in kolon_x.items():
            ekle(baslik[k], x, y)
        y -= 60.0
        for poz, adet, cap, boy, toplam in [(1, 8, 16, "3,00", "24,00"), (2, 4, 16, "2,00", "8,00")]:
            ekle(str(poz), kolon_x["POZ"], y)
            ekle(str(adet), kolon_x["ADET"], y)
            ekle(str(cap), kolon_x["CAP"], y)
            ekle(boy, kolon_x["BOY"], y)
            ekle(toplam, kolon_x["O16"], y)
            y -= 60.0
        return tablo_hucrelerini_kumele(hucreler)

    # Tablo A (2 poz: Ø18,Ø12) + Tablo B (2 poz: Ø16) sirayla dondurulecek.
    win.acad_connector = SahteConnector([_grid_baslikli(), _grid_tablo_b()])
    win.demir_kat_verileri.append({"kat_adi": "Coklu Kat", "demirler": [], "rapor": None})
    win.aktif_kat_adi = "Coklu Kat"

    # 1. tablo islendikten sonra "baska tablo var mi?" -> EVET, 2. tablo
    # islendikten sonra -> HAYIR (dongu bitsin).
    _SORU_YANITLARI.extend([QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No])

    win._autocad_poz_donati_oku()

    kat = win.demir_kat_verileri[0]
    assert len(kat["demirler"]) == 4, f"4 poz (2+2) beklenirdi, {len(kat['demirler'])} geldi"

    capler = sorted(d.cap for d in kat["demirler"])
    assert capler == [12, 16, 16, 18], capler

    # Poz numaralari tablo no ile etiketlenmis olmali (T1-.../T2-...) - ayni
    # "Poz 1" isminin iki tablodan gelmesi karismasin diye.
    assert any("T1-" in d.orijinal_metin for d in kat["demirler"])
    assert any("T2-" in d.orijinal_metin for d in kat["demirler"])

    assert win.btn_demir_excel.isEnabled() is True
    print(f"PASS: coklu tablo dongusu dogru calisti (2 tablo, toplam {len(kat['demirler'])} poz, "
          f"capler={capler})")


if __name__ == "__main__":
    test_buton_baslangicta_disabled()
    test_baslikli_tablo_uctan_uca()
    test_basliksiz_tablo_manuel_sutun_sirasi()
    test_coklu_tablo_dongusu()
    print("\nTUM UI TESTLERI PASS (4/4)")
