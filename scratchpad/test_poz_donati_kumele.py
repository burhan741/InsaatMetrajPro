"""AŞAMA 1 testi — Poza Göre Donatı Metraj Tablosu okuma aracının çekirdeği.

Sadece SAF fonksiyonları test eder (mtext_temizle, _oto_esik_bul, _1d_kumele,
tablo_hucrelerini_kumele) — AutoCAD/COM/PyQt bağımsız, sahte (text,x,y)
listeleriyle çalışır. get_poz_bazli_donati_tablosu() (gerçek AutoCAD metodu)
BURADA test EDİLMİYOR — o ancak gerçek AutoCAD ile denenebilir.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.autocad_connector import (
    mtext_temizle,
    _oto_esik_bul,
    _1d_kumele,
    tablo_hucrelerini_kumele,
)


# ─────────────────────────────────────────────────────────────────────────
# mtext_temizle
# ─────────────────────────────────────────────────────────────────────────

def test_mtext_temizle_duz_metin_degismez():
    assert mtext_temizle("POZ 1") == "POZ 1"
    assert mtext_temizle("5,30") == "5,30"
    assert mtext_temizle("") == ""
    assert mtext_temizle(None) is None
    print("PASS: duz metin degismiyor")


def test_mtext_temizle_format_kodlari():
    assert mtext_temizle("\\A1;5,30") == "5,30"
    assert mtext_temizle("\\H2.5x;POZ 1") == "POZ 1"
    assert mtext_temizle("{\\C1;POZ 1}") == "POZ 1"
    assert mtext_temizle("\\fArial|b0|i0;106,00") == "106,00"
    print("PASS: format kodlari temizleniyor")


def test_mtext_temizle_paragraf_ve_yigin():
    assert mtext_temizle("POZ 1\\PADET 20") == "POZ 1\nADET 20"
    assert mtext_temizle("\\S1^2;") == "1/2"
    print("PASS: paragraf/yigin kesir donusumu dogru")


# ─────────────────────────────────────────────────────────────────────────
# _oto_esik_bul / _1d_kumele
# ─────────────────────────────────────────────────────────────────────────

def test_oto_esik_net_ayrim():
    # 3 net grup: {0,0.1,0.2}, {50,50.1}, {100}
    degerler = [0.0, 0.1, 0.2, 50.0, 50.1, 100.0]
    esik = _oto_esik_bul(sorted(degerler))
    assert 0.2 < esik < 49.9, f"esik beklenen aralikta degil: {esik}"
    print(f"PASS: oto esik net ayrimda dogru bulundu ({esik:.3f})")


def test_1d_kumele_temel():
    # 3 satir, her satirda 2 hucre (yakin x/y), satirlar arasi buyuk bosluk
    veriler = [(0.0, 0), (0.05, 1), (40.0, 2), (40.1, 3), (80.0, 4), (79.9, 5)]
    kumeler = _1d_kumele(veriler)
    assert len(kumeler) == 3, f"3 kume beklenirdi, {len(kumeler)} geldi"
    assert set(kumeler[0]) == {0, 1}
    assert set(kumeler[1]) == {2, 3}
    assert set(kumeler[2]) == {4, 5}
    print("PASS: 1d kumele temel senaryo dogru")


def test_1d_kumele_egik_surukleme_yok():
    # Kademeli artan (egik) ama ayni "satir" icinde kalmasi gereken degerler:
    # merkez guncellemesi olmadan (sadece onceki komsuya bakan naif yontemle)
    # bu tur veriler yanlislikla ayri kumelere bolunebilir.
    veriler = [(0.0, 0), (0.3, 1), (0.6, 2), (0.9, 3), (50.0, 4)]
    kumeler = _1d_kumele(veriler, esik=2.0)
    assert len(kumeler) == 2
    assert set(kumeler[0]) == {0, 1, 2, 3}
    assert set(kumeler[1]) == {4}
    print("PASS: hafif egik veri tek kumede kaliyor (merkez guncellemesi calisiyor)")


# ─────────────────────────────────────────────────────────────────────────
# tablo_hucrelerini_kumele — ekran goruntusundeki tabloya benzer sentetik veri
# ─────────────────────────────────────────────────────────────────────────

def _jit(i, genlik=0.04):
    """Deterministik (rastgele DEGIL — tekrar uretilebilir olmali) kucuk
    sapma. Gercek AutoCAD'de ayni sutundaki farkli TEXT nesneleri (font
    baseline/ascent farklari, kullanicinin elle hizalamasi vb. yuzunden)
    piksel-mukemmel ayni X/Y'de OLMAZ — GetBoundingBox merkez X/Y'sinde
    onda/yuzde birim mertebesinde sapma normaldir. Bu sapmayi simule eder."""
    return ((i * 37) % 7 - 3) * genlik


def _ekran_goruntusu_tablosu(jitter=True):
    """5.png'deki tabloyu taklit eden sentetik (text,x,y) verisi.

    Sutunlar (soldan saga, X artan): POZ(x=0) ADET(x=100) CAP(x=200)
    BOY(x=300) SEKIL(x=400, kasitli BOS birakildi - ihmal edilecek)
    TOPLAM-O8(x=650) TOPLAM-O12(x=750) TOPLAM-O18(x=850)

    Satirlar (Y azalan - AutoCAD'de yukaridan asagi): baslik + 7 veri satiri,
    satir yuksekligi 60 birim.

    jitter=True (varsayilan, GERCEKCI durum): ayni sutun/satirdaki hucrelere
    kucuk (+-0.12 birime kadar) deterministik sapma eklenir — GetBoundingBox
    merkezleri farkli TEXT nesnelerinde asla bit-bit ozdes olmaz. Oto-esik
    algoritmasi (_oto_esik_bul) bu "gurultu" populasyonunu gercek sutun/satir
    ayracindan ayirt etmek icin dayanir (bkz. test_grid_mukemmel_hizali_*
    testindeki BILINEN SINIR notu — jitter=False ile CAGRILIRSA oto-esik
    yanilabilir, bu durumda x_esik/y_esik elle verilmelidir).
    """
    kolon_x = {"POZ": 0.0, "ADET": 100.0, "CAP": 200.0, "BOY": 300.0,
               "O8": 650.0, "O12": 750.0, "O18": 850.0}
    satirlar_veri = [
        # poz, adet, cap, boy,  {cap_kolon: toplam}
        (1, 20, 18, "5,30", {"O18": "106,00"}),
        (2, 16, 12, "5,25", {"O12": "84,00"}),
        (3, 20, 12, "4,40", {"O12": "88,00"}),
        (4, 38, 18, "4,40", {"O18": "167,20"}),
        (5, 14, 12, "2,90", {"O12": "40,60"}),
        (6, 12, 12, "2,90", {"O12": "34,80"}),
        (7, 24, 12, "2,90", {"O12": "69,60"}),
    ]

    hucreler = []
    i = 0

    def ekle(text, x, y):
        nonlocal i
        if jitter:
            x = x + _jit(i)
            y = y + _jit(i + 1)
        hucreler.append({"text": text, "x": x, "y": y})
        i += 1

    y = 700.0
    baslik_y = y
    for kolon, x in kolon_x.items():
        ekle(kolon, x, baslik_y)
    y -= 60.0

    for poz, adet, cap, boy, toplamlar in satirlar_veri:
        ekle(str(poz), kolon_x["POZ"], y)
        ekle(str(adet), kolon_x["ADET"], y)
        ekle(str(cap), kolon_x["CAP"], y)
        ekle(boy, kolon_x["BOY"], y)
        for kolon_adi, deger in toplamlar.items():
            ekle(deger, kolon_x[kolon_adi], y)
        y -= 60.0

    return hucreler, kolon_x


def test_grid_boyutu_ve_baslik_satiri():
    hucreler, kolon_x = _ekran_goruntusu_tablosu()
    grid = tablo_hucrelerini_kumele(hucreler)

    # 1 baslik + 7 veri = 8 satir
    assert len(grid) == 8, f"8 satir beklenirdi, {len(grid)} geldi"
    # 7 farkli X kumesi (SEKIL sutunu hic metin icermiyor, kume acilmaz)
    assert len(grid[0]) == 7, f"7 sutun beklenirdi, {len(grid[0])} geldi"

    baslik = [h['text'] if h else None for h in grid[0]]
    assert baslik == ["POZ", "ADET", "CAP", "BOY", "O8", "O12", "O18"], baslik
    print(f"PASS: grid boyutu dogru (8 satir x 7 sutun), baslik sirali: {baslik}")


def test_grid_veri_satirlari_dogru_hucrede():
    hucreler, kolon_x = _ekran_goruntusu_tablosu()
    grid = tablo_hucrelerini_kumele(hucreler)

    # Satir index 1 = Poz 1: 20 adet, cap 18, boy 5,30, sadece O18 dolu
    satir1 = [h['text'] if h else None for h in grid[1]]
    assert satir1 == ["1", "20", "18", "5,30", None, None, "106,00"], satir1

    # Satir index 2 = Poz 2: 16 adet, cap 12, boy 5,25, sadece O12 dolu
    satir2 = [h['text'] if h else None for h in grid[2]]
    assert satir2 == ["2", "16", "12", "5,25", None, "84,00", None], satir2

    # Son satir (Poz 7)
    satir7 = [h['text'] if h else None for h in grid[7]]
    assert satir7 == ["7", "24", "12", "2,90", None, "69,60", None], satir7

    print("PASS: veri satirlari dogru sutuna oturmus (bos hucreler dogru None)")


def test_grid_hafif_gurultulu_koordinatlar():
    """Gercek AutoCAD'de hucreler piksel-mukemmel hizali olmayabilir —
    kucuk rastgele sapmalarla (satir ici +-0.5, sutun ici +-0.3) kumeleme
    hala dogru calismali (bkz. 'Bilinen zorluklar' maddesi 1)."""
    hucreler, kolon_x = _ekran_goruntusu_tablosu()
    # Basit deterministik "gurultu" ekle (rastgelelik yerine sabit desen)
    for i, h in enumerate(hucreler):
        h['y'] += (0.4 if i % 2 == 0 else -0.4)
        h['x'] += (0.2 if i % 3 == 0 else -0.2)

    grid = tablo_hucrelerini_kumele(hucreler)
    assert len(grid) == 8, f"gurultuyle 8 satir beklenirdi, {len(grid)} geldi"
    assert len(grid[0]) == 7, f"gurultuyle 7 sutun beklenirdi, {len(grid[0])} geldi"
    satir1 = [h['text'] if h else None for h in grid[1]]
    assert satir1 == ["1", "20", "18", "5,30", None, None, "106,00"], satir1
    print("PASS: hafif gurultulu koordinatlarda da kumeleme dogru")


def test_bos_liste():
    assert tablo_hucrelerini_kumele([]) == []
    print("PASS: bos liste crash etmiyor")


def test_grid_mukemmel_hizali_koordinatlarda_bilinen_sinir():
    """BILINEN SINIR (dokumante edilen, gizlenmeyen davranis):

    Eger ayni sutundaki TUM hucreler piksel-mukemmel ozdes X'te ise (sifir
    jitter — gercek AutoCAD'de nadir ama imkansiz degil, ornegin bir LISP
    rutunuyle uretilmis tablo), oto-esik algoritmasi "gurultu" populasyonunu
    goremez ve esit araliklarla dizilmis sutunlari (POZ/ADET/CAP/BOY hepsi
    100 birim arayla) YANLISLIKLA TEK sutunda birlestirebilir. Bu, elbow
    yonteminin dogasi geregi: ayirt edici tek sinyal ("kucuk=gurultu,
    buyuk=gercek ayrac") sifir-jitter durumunda kaybolur.

    Mitigasyon: boyle bir durumda kullanici/cagiran x_esik'i ELLE (orn.
    gercek sutun araliginin yarisindan kucuk bir deger) vermeli — bu test
    hem sorunu gostermek hem de manuel esikle duzeldigini kanitlamak icin
    var (bkz. proje brief'i madde 4: "kumeleme toleransi ayarlanabilir
    olmali")."""
    hucreler, kolon_x = _ekran_goruntusu_tablosu(jitter=False)

    grid_oto = tablo_hucrelerini_kumele(hucreler)
    sutun_sayisi_oto = len(grid_oto[0]) if grid_oto else 0
    print(f"BILGI: sifir-jitter + oto-esik -> {sutun_sayisi_oto} sutun bulundu "
          f"(7 beklenirdi) — bu senaryoda ELLE esik gerekir, asagida dogrulaniyor.")

    # Manuel esik (gercek min sutun araligi 100'un yarisindan kucuk, orn. 40)
    # ile ayni veri dogru kumeleniyor mu?
    grid_manuel = tablo_hucrelerini_kumele(hucreler, y_esik=30.0, x_esik=40.0)
    assert len(grid_manuel) == 8, f"manuel esikle 8 satir beklenirdi, {len(grid_manuel)} geldi"
    assert len(grid_manuel[0]) == 7, f"manuel esikle 7 sutun beklenirdi, {len(grid_manuel[0])} geldi"
    satir1 = [h['text'] if h else None for h in grid_manuel[1]]
    assert satir1 == ["1", "20", "18", "5,30", None, None, "106,00"], satir1
    print("PASS: sifir-jitter durumunda ELLE esikle dogru sonuc aliniyor (mitigasyon calisiyor)")


if __name__ == "__main__":
    testler = [
        test_mtext_temizle_duz_metin_degismez,
        test_mtext_temizle_format_kodlari,
        test_mtext_temizle_paragraf_ve_yigin,
        test_oto_esik_net_ayrim,
        test_1d_kumele_temel,
        test_1d_kumele_egik_surukleme_yok,
        test_grid_boyutu_ve_baslik_satiri,
        test_grid_veri_satirlari_dogru_hucrede,
        test_grid_hafif_gurultulu_koordinatlar,
        test_bos_liste,
        test_grid_mukemmel_hizali_koordinatlarda_bilinen_sinir,
    ]
    for t in testler:
        t()
    print(f"\nTUM TESTLER PASS ({len(testler)}/{len(testler)})")
