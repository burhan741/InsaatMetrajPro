"""AŞAMA 3 testi — kg/ton hesabı + tablodaki hazır TOPLAM ile karşılaştırma.

Sadece SAF fonksiyonu test eder (poz_kayitlarindan_hesapla) — AutoCAD
bağımsız, elle kurulmuş poz kayıt listeleriyle çalışır.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.autocad_connector import (
    poz_kayitlarindan_hesapla,
    poz_kayitlarini_demir_bilgisine_cevir,
    DEMIR_AGIRLIK_TABLOSU,
)


def _kayit(poz_no, adet, cap, boy, tablo_boy=None):
    tablo_toplamlari = {}
    if tablo_boy is not None:
        tablo_toplamlari[cap] = tablo_boy
    return {"poz_no": poz_no, "adet": adet, "cap": cap, "boy": boy,
            "tablo_toplamlari": tablo_toplamlari}


# Gerçek AutoCAD testinde kullanıcının onayladığı 7 satırlık örnek (ekran
# görüntüsü + gerçek doğrulama ile birebir aynı poz 1-7 verisi).
GERCEK_ORNEK = [
    _kayit("1", 20, 18, 5.30, tablo_boy=106.00),
    _kayit("2", 16, 12, 5.25, tablo_boy=84.00),
    _kayit("3", 20, 12, 4.40, tablo_boy=88.00),
    _kayit("4", 38, 18, 4.40, tablo_boy=167.20),
    _kayit("5", 14, 12, 2.90, tablo_boy=40.60),
    _kayit("6", 12, 12, 2.90, tablo_boy=34.80),
    _kayit("7", 24, 12, 2.90, tablo_boy=69.60),
]


def test_cap_ozeti_dogru():
    sonuc = poz_kayitlarindan_hesapla(GERCEK_ORNEK)

    assert set(sonuc["cap_ozeti"].keys()) == {12, 18}

    # Ø18: poz1(20x5.30=106.0) + poz4(38x4.40=167.2) = 273.2 m
    v18 = sonuc["cap_ozeti"][18]
    assert v18["adet"] == 20 + 38
    assert abs(v18["boy_m"] - (106.0 + 167.2)) < 1e-6
    beklenen_agirlik_18 = (106.0 + 167.2) * DEMIR_AGIRLIK_TABLOSU[18]
    assert abs(v18["agirlik_kg"] - beklenen_agirlik_18) < 1e-4

    # Ø12: poz2(84.0)+poz3(88.0)+poz5(40.6)+poz6(34.8)+poz7(69.6) = 317.0 m
    v12 = sonuc["cap_ozeti"][12]
    assert v12["adet"] == 16 + 20 + 14 + 12 + 24
    assert abs(v12["boy_m"] - 317.0) < 1e-6

    print(f"PASS: cap ozeti dogru (O18={v18['boy_m']}m/{v18['agirlik_kg']:.2f}kg, "
          f"O12={v12['boy_m']}m/{v12['agirlik_kg']:.2f}kg)")


def test_genel_toplam_dogru():
    sonuc = poz_kayitlarindan_hesapla(GERCEK_ORNEK)
    g = sonuc["genel"]
    beklenen_boy = 106.0 + 167.2 + 317.0
    assert abs(g["boy_m"] - beklenen_boy) < 1e-6
    beklenen_agirlik = (106.0 + 167.2) * DEMIR_AGIRLIK_TABLOSU[18] + 317.0 * DEMIR_AGIRLIK_TABLOSU[12]
    assert abs(g["agirlik_kg"] - beklenen_agirlik) < 1e-4
    print(f"PASS: genel toplam dogru ({g['agirlik_kg']:.2f} kg = {g['agirlik_kg']/1000:.4f} ton)")


def test_sapma_yok_gercek_tabloda():
    """Gercek AutoCAD tablosundaki her poz icin tablo_boy tam olarak
    adet*boy'a esit oldugundan (kullanici onaylanmis veri) HICBIR sapma
    cikmamali."""
    sonuc = poz_kayitlarindan_hesapla(GERCEK_ORNEK)
    assert sonuc["sapma_var_mi"] is False
    assert sonuc["sapmalar"] == []
    print("PASS: gercek (dogrulanmis) tabloda sapma yok")


def test_kucuk_yuvarlama_farki_yanlis_alarm_vermiyor():
    """Tabloda 2 ondalikli yuvarlanmis bir deger (orn. gercek 8.041 iken
    tabloda 8.04 yazmasi) YANLIS ALARM olusturmamali — tolerans buna gore."""
    kayitlar = [_kayit("13", 6, 12, 1.3402, tablo_boy=8.04)]  # 6*1.3402=8.0412
    sonuc = poz_kayitlarindan_hesapla(kayitlar)
    assert sonuc["sapma_var_mi"] is False, sonuc["sapmalar"]
    print("PASS: kucuk yuvarlama farki (0.0012m) yanlis alarm vermiyor")


def test_gercek_sapma_yakalaniyor():
    """Tabloyu ciZen kisi bir satirda adet/boy/toplami tutarsiz girmisse
    (orn. asagida 20x5.30=106 olmasi gerekirken tabloda yanlislikla 90
    yazilmis), bu YAKALANMALI."""
    kayitlar = [_kayit("1", 20, 18, 5.30, tablo_boy=90.0)]  # gercek: 106.0
    sonuc = poz_kayitlarindan_hesapla(kayitlar)
    assert sonuc["sapma_var_mi"] is True
    assert len(sonuc["sapmalar"]) == 1
    s = sonuc["sapmalar"][0]
    assert s["poz_no"] == "1"
    assert s["cap"] == 18
    assert abs(s["hesaplanan_boy"] - 106.0) < 1e-6
    assert s["tablo_boy"] == 90.0
    print(f"PASS: gercek sapma yakalandi (fark={s['fark']}m)")


def test_tablo_toplami_yoksa_sapma_kontrolu_atlanir():
    """tablo_toplamlari bos ise (tabloda hazir TOPLAM sutunu yoksa ya da
    o pozun sutunu bos ise) crash etmemeli, sadece hesap yapip sapma
    kontrolunu atlamali."""
    kayitlar = [_kayit("1", 10, 12, 2.0)]  # tablo_boy verilmedi
    sonuc = poz_kayitlarindan_hesapla(kayitlar)
    assert sonuc["sapma_var_mi"] is False
    assert sonuc["cap_ozeti"][12]["boy_m"] == 20.0
    print("PASS: tablo toplami olmayan pozlarda sapma kontrolu sessizce atlaniyor")


def test_cubuk_adedi_dogru():
    sonuc = poz_kayitlarindan_hesapla(GERCEK_ORNEK)
    import math
    for cap, v in sonuc["cap_ozeti"].items():
        assert v["cubuk_adet"] == math.ceil(v["boy_m"] / 12.0)
    print("PASS: cubuk adedi (12m) dogru")


def test_demir_bilgisine_cevirme():
    """DemirBilgisi'ye cevrilen liste, mevcut 'Demir Metrajı' kat akisinin
    (Excel export 'Boy (cm)' basligi, Kesim Listesi birim='cm' beklentisi)
    varsayimlarina uymali: .boy CM, .toplam_boy METRE olmali."""
    demirler = poz_kayitlarini_demir_bilgisine_cevir(GERCEK_ORNEK)
    assert len(demirler) == 7

    d1 = demirler[0]  # Poz 1: 20 adet Ø18 x 5.30m
    assert d1.adet == 20
    assert d1.cap == 18
    assert abs(d1.boy - 530.0) < 1e-6  # 5.30m -> 530cm
    assert abs(d1.toplam_boy - 106.0) < 1e-6  # 20*5.30m
    beklenen_agirlik = 106.0 * DEMIR_AGIRLIK_TABLOSU[18]
    assert abs(d1.toplam_agirlik - beklenen_agirlik) < 1e-4
    assert d1.gecerli is True
    assert d1.eleman_tipi == "İstinat Demir Hesabı"

    toplam_agirlik_tumu = sum(d.toplam_agirlik for d in demirler)
    hesap = poz_kayitlarindan_hesapla(GERCEK_ORNEK)
    assert abs(toplam_agirlik_tumu - hesap["genel"]["agirlik_kg"]) < 1e-4, (
        "DemirBilgisi listesinin toplami, hesap fonksiyonunun genel toplamiyla eslesmeli"
    )
    print(f"PASS: DemirBilgisi donusumu dogru (cm/m birimleri, {len(demirler)} kayit, "
          f"toplam agirlik tutarli: {toplam_agirlik_tumu:.2f} kg)")


def test_bos_liste():
    sonuc = poz_kayitlarindan_hesapla([])
    assert sonuc["cap_ozeti"] == {}
    assert sonuc["genel"]["adet"] == 0
    assert sonuc["sapma_var_mi"] is False
    print("PASS: bos liste crash etmiyor")


if __name__ == "__main__":
    testler = [
        test_cap_ozeti_dogru,
        test_genel_toplam_dogru,
        test_sapma_yok_gercek_tabloda,
        test_kucuk_yuvarlama_farki_yanlis_alarm_vermiyor,
        test_gercek_sapma_yakalaniyor,
        test_tablo_toplami_yoksa_sapma_kontrolu_atlanir,
        test_cubuk_adedi_dogru,
        test_demir_bilgisine_cevirme,
        test_bos_liste,
    ]
    for t in testler:
        t()
    print(f"\nTUM TESTLER PASS ({len(testler)}/{len(testler)})")
