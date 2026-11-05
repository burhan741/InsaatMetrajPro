"""
Puantaj regresyon testi.

NEYI COZUYORUZ: Puantaj modulu Blueprint'e tasinirken hicbir hesap/endpoint
degismemeli. Eski tek dosyalik app.py (eski/app_tek_dosya.py) ile yeni
program AYNI baslangic veritabaninda AYNI islem sirasini calistirir; her
adimdan sonra tum okuma endpoint'lerinin JSON cevabi birebir karsilastirilir.

NASIL TEST EDERIZ: pytest test_puantaj_regresyon.py
Gercek veriyle denemek icin: sunucudan indirilen puantaj.db'nin yolunu
GERCEK_DB ortam degiskenine verin (yoksa klasordeki yerel puantaj.db,
o da yoksa o test atlanir). Gercek dosyanin KOPYASI kullanilir.
"""
import hashlib
import os
import re
import shutil
import sqlite3
from datetime import date, timedelta

import pytest

import app as app_modul
from conftest import KLASOR, YEREL_GERCEK_DB, db_yonlendir, eski_app_yukle

BUGUN = date.today().isoformat()
DUN = (date.today() - timedelta(days=1)).isoformat()
BU_AY = date.today().strftime('%Y-%m')


class Ikiz:
    """Ayni istegi eski ve yeni uygulamaya gonderip cevaplari karsilastirir."""

    def __init__(self, eski_istemci, yeni_istemci):
        self.eski = eski_istemci
        self.yeni = yeni_istemci

    def yaz(self, metod, url, json=None):
        r1 = getattr(self.eski, metod)(url, json=json)
        r2 = getattr(self.yeni, metod)(url, json=json)
        assert r1.status_code == r2.status_code, url
        assert r1.get_json() == r2.get_json(), url
        return r2.get_json()

    def oku(self, url):
        r1 = self.eski.get(url)
        r2 = self.yeni.get(url)
        assert r1.status_code == r2.status_code == 200, url
        assert r1.get_json() == r2.get_json(), 'FARK: ' + url
        return r2.get_json()

    def tum_okumalari_karsilastir(self, aylar=(BU_AY,), tarihler=(BUGUN, DUN)):
        isciler = self.oku('/api/isci')
        for isc in isciler:
            self.oku('/api/isci/%d/detay' % isc['id'])
        for t in tarihler:
            self.oku('/api/puantaj?tarih=' + t)
            self.oku('/api/ozet/gunluk?tarih=' + t)
        for ay in aylar:
            self.oku('/api/ozet/aylik?ay=' + ay)
            self.oku('/api/gider?ay=' + ay)
            self.oku('/api/civi/gider?ay=' + ay)
        self.oku('/api/odeme')
        self.oku('/api/ayarlar')
        self.oku('/api/ozet/haftalik')
        self.oku('/api/hatirlatma')
        self.oku('/api/yedek/json')
        return isciler


@pytest.fixture
def ikiz(tmp_path, monkeypatch):
    eski = eski_app_yukle(str(tmp_path / 'eski'))
    yeni_yol = str(tmp_path / 'yeni' / 'puantaj.db')
    os.makedirs(os.path.dirname(yeni_yol))
    db_yonlendir(monkeypatch, yeni_yol)
    app_modul.ortak.veritabani_hazirla(app_modul.INIT_FONKSIYONLARI)
    app_modul.app.config['TESTING'] = True
    return Ikiz(eski.app.test_client(), app_modul.app.test_client())


def _id_bul(isciler, ad):
    return [i['id'] for i in isciler if i['ad_soyad'] == ad][0]


def test_islem_sirasi_eski_ile_birebir(ikiz):
    ikiz.yaz('post', '/api/isci', {'ad_soyad': 'Ali Usta', 'ustalik': 'Usta',
                                   'gunluk_ucret': 1500, 'telefon': '555'})
    ikiz.yaz('post', '/api/isci', {'ad_soyad': 'Veli', 'ustalik': 'Duz Isci', 'gunluk_ucret': 1000})
    isciler = ikiz.tum_okumalari_karsilastir()
    ali, veli = _id_bul(isciler, 'Ali Usta'), _id_bul(isciler, 'Veli')

    ikiz.yaz('post', '/api/ayarlar', {'yemek_fiyati': 150})
    ikiz.yaz('post', '/api/puantaj', {'isci_id': ali, 'tarih': BUGUN,
                                      'calisma_durumu': 'tam_gun', 'mesai_saat': 2})
    ikiz.yaz('post', '/api/puantaj', {'isci_id': ali, 'tarih': DUN, 'calisma_durumu': 'bir_bucuk_gun'})
    ikiz.yaz('post', '/api/puantaj', {'isci_id': veli, 'tarih': BUGUN, 'calisma_durumu': 'yarim_gun'})
    ikiz.yaz('post', '/api/puantaj', {'isci_id': veli, 'tarih': '2026-07-01', 'calisma_durumu': 'tam_gun'})
    ikiz.yaz('post', '/api/puantaj', {'isci_id': 9999, 'tarih': BUGUN})  # 404 de ayni olmali
    ikiz.tum_okumalari_karsilastir(aylar=(BU_AY, '2026-07'))

    # Ucret degisimi gecmisi etkilememeli (Rev-107) - iki tarafta da ayni
    ikiz.yaz('put', '/api/isci/%d' % ali, {'ad_soyad': 'Ali Usta', 'ustalik': 'Usta',
                                          'gunluk_ucret': 1800, 'telefon': '555'})
    ikiz.yaz('post', '/api/puantaj', {'isci_id': ali, 'tarih': BUGUN,
                                      'calisma_durumu': 'tam_gun', 'mesai_saat': 3})
    ikiz.yaz('post', '/api/odeme', {'isci_id': ali, 'miktar': 2000, 'aciklama': 'avans'})
    ikiz.yaz('post', '/api/odeme', {'isci_id': veli, 'miktar': 100})
    ikiz.yaz('post', '/api/gider', {'ad': 'Su', 'tutar': 300})
    ikiz.yaz('post', '/api/yemek/ode', {'miktar': 200})
    ikiz.yaz('post', '/api/civi/gider', {'miktar': 500})
    ikiz.yaz('post', '/api/civi/ode', {'miktar': 100})
    ikiz.yaz('post', '/api/hatirlatma', {'ad': 'Kira', 'tarih': '2026-12-01'})
    ikiz.yaz('post', '/api/hatirlatma', {'ad': '', 'tarih': ''})  # 400
    ikiz.yaz('post', '/api/yemek/ode', {'miktar': 0})  # 400
    ikiz.tum_okumalari_karsilastir(aylar=(BU_AY, '2026-07'))

    # Silmeler
    odemeler = ikiz.oku('/api/odeme')
    veli_odeme = [o['id'] for o in odemeler if o['isci_id'] == veli][0]
    ikiz.yaz('delete', '/api/odeme/%d' % veli_odeme)
    ikiz.yaz('delete', '/api/puantaj/sil?isci_id=%d&tarih=%s' % (veli, BUGUN))
    haftalik = ikiz.oku('/api/ozet/haftalik')
    ikiz.yaz('delete', '/api/yemek/odeme/%d' % haftalik['son_yemek_odeme_id'])
    ikiz.yaz('delete', '/api/civi/odeme/%d' % haftalik['son_civi_odeme_id'])
    ikiz.yaz('delete', '/api/civi/gider/%d' % haftalik['son_civi_gider_id'])
    hat = ikiz.oku('/api/hatirlatma')
    ikiz.yaz('delete', '/api/hatirlatma/%d' % hat[0]['id'])
    gider = ikiz.oku('/api/gider?ay=' + BU_AY)
    ikiz.yaz('delete', '/api/gider/%d' % gider[0]['id'])
    ikiz.tum_okumalari_karsilastir(aylar=(BU_AY, '2026-07'))

    # Milat temizligi: onaysiz 400, onayli ayni sonuc
    ikiz.yaz('post', '/api/admin/milat-temizle')
    ikiz.yaz('post', '/api/admin/milat-temizle?onay=EVET-SIL')
    ikiz.tum_okumalari_karsilastir(aylar=(BU_AY, '2026-07'))

    ikiz.yaz('delete', '/api/isci/%d' % veli)
    ikiz.tum_okumalari_karsilastir()


def test_pdf_ve_yedek_indirme_calisiyor(ikiz):
    ikiz.yaz('post', '/api/isci', {'ad_soyad': 'Ali', 'gunluk_ucret': 1500})
    for url in ('/api/pdf/aylik?ay=' + BU_AY, '/api/pdf/haftalik'):
        r = ikiz.yeni.get(url)
        assert r.status_code == 200, url
        assert r.mimetype == 'application/pdf'
        assert r.data[:4] == b'%PDF'
    r = ikiz.yeni.get('/api/yedek/indir')
    assert r.status_code == 200
    assert r.data[:15] == b'SQLite format 3'


def test_puantaj_adresi_ve_cache_bust(istemci):
    r = istemci.get('/puantaj')
    assert r.status_code == 302
    assert re.match(r'^/puantaj\?v=\d+$', r.headers['Location'].replace('http://localhost', ''))
    r = istemci.get('/puantaj?v=1')
    assert r.status_code == 200
    assert r.headers['Cache-Control'].startswith('no-store')


def _head_sil(html):
    return re.sub(r'<head>.*?</head>', '<head></head>', html, flags=re.S)


def test_html_sadece_izinli_degisiklikler(tmp_path, istemci):
    """Yeni puantaj HTML'i = eski HTML - vinc + Ana Menu baglantisi (+ <head>'de sadece tema/yazi tipi)."""
    eski = eski_app_yukle(str(tmp_path / 'eski'))
    eski_html = eski.app.test_client().get('/?v=1').get_data(as_text=True)
    yeni_html = istemci.get('/puantaj?v=1').get_data(as_text=True)

    # <head> disinda (gorunur sayfa + JS) eklenen tek satir: Ana Menu baglantisi
    eski_satirlar = set(_head_sil(eski_html).splitlines())
    eklenen = [s for s in _head_sil(yeni_html).splitlines() if s not in eski_satirlar]
    assert len(eklenen) == 1, eklenen
    assert 'href="/"' in eklenen[0] and 'Ana Men' in eklenen[0]
    # <head>'de meta etiketleri ve baslik aynen duruyor
    eski_head = re.search(r'<head>(.*?)<style>', eski_html, re.S).group(1)
    for satir in eski_head.strip().splitlines():
        assert satir in yeni_html, satir

    for yasak in ('panel-vinc', 'loadVinc', '/api/vinc', 'nav-vinc', "sekme('vinc'"):
        assert yasak in eski_html
        assert yasak not in yeni_html
    # Puantaj'in kendi bolumleri yerinde
    for kalan in ('panel-puantaj', 'panel-ozet', 'panel-aylik', 'panel-isciler',
                  'panel-ayarlar', '/api/pdf/haftalik', 'Vinccu'):
        assert kalan in yeni_html


# Rev-178 (puantaj renk uyumu) oncesi alinan parmak izleri. Puantajda yalniz
# <head> icindeki stil/yazi tipi degisebilir; JS ve gorunur govde KILITLI.
# Bilerek puantaj JS/HTML'i degistirilirse bu degerler bilincli guncellenir.
PUANTAJ_JS_SHA256 = '2b25515df2c4349060ccfeac63367595d6203ef8c3ce2b1944e41d03c9a1fd14'
PUANTAJ_GOVDE_SHA256 = '49adc5f799633dc3504c318e04b2285dfaa83768339e3036e32d5452526d0b65'


def test_puantaj_js_ve_govde_kilitli(istemci):
    h = istemci.get('/puantaj?v=1').get_data(as_text=True)
    js = ''.join(re.findall(r'<script>(.*?)</script>', h, re.S))
    govde = re.sub(r'<script>.*?</script>', '', re.sub(r'<head>.*?</head>', '', h, flags=re.S), flags=re.S)
    assert hashlib.sha256(js.encode()).hexdigest() == PUANTAJ_JS_SHA256
    assert hashlib.sha256(govde.encode()).hexdigest() == PUANTAJ_GOVDE_SHA256


def test_puantaj_tema_renkleri(istemci):
    import ortak
    h = istemci.get('/puantaj?v=1').get_data(as_text=True)
    stil = re.search(r'<style>(.*?)</style>', h, re.S).group(1)
    assert ortak.KOK_CSS in stil                       # renkler ortak.TEMA'dan
    assert '--pr:var(--lacivert)' in stil and 'font-family:var(--yazi)' in stil
    assert 'family=Manrope' in h
    # Eski koyu tema renkleri stilde kalmadi
    for eski in ('#e94560', '#1a1a2e', '#16213e', '#0f3460', '#2a2a4a', '#1e1e3a', '#a0a0a0;', '#333'):
        govde_kurallari = re.sub(r'\[style\*="[^"]*"\]', '', stil)   # JS satir ici eslemeleri haric
        assert eski not in govde_kurallari, eski


def _gercek_db_yolu():
    yol = os.environ.get('GERCEK_DB') or YEREL_GERCEK_DB
    return yol if os.path.exists(yol) else None


@pytest.mark.skipif(_gercek_db_yolu() is None, reason='Gercek puantaj.db kopyasi yok')
def test_gercek_veritabani_kopyasiyla_birebir(tmp_path, monkeypatch):
    kaynak = _gercek_db_yolu()
    eski = eski_app_yukle(str(tmp_path / 'eski'), kaynak_db=kaynak)
    yeni_yol = str(tmp_path / 'yeni' / 'puantaj.db')
    os.makedirs(os.path.dirname(yeni_yol))
    shutil.copy2(kaynak, yeni_yol)
    db_yonlendir(monkeypatch, yeni_yol)
    app_modul.ortak.veritabani_hazirla(app_modul.INIT_FONKSIYONLARI)
    ikiz = Ikiz(eski.app.test_client(), app_modul.app.test_client())

    conn = sqlite3.connect(yeni_yol)
    aylar = sorted({r[0] for r in conn.execute(
        "SELECT DISTINCT strftime('%Y-%m', tarih) FROM puantaj WHERE tarih IS NOT NULL")} | {BU_AY})
    tarihler = [r[0] for r in conn.execute(
        'SELECT DISTINCT tarih FROM puantaj ORDER BY tarih DESC LIMIT 20')] + [BUGUN]
    puantaj_sayisi = conn.execute('SELECT COUNT(*) FROM puantaj').fetchone()[0]
    conn.close()

    isciler = ikiz.tum_okumalari_karsilastir(aylar=aylar, tarihler=tarihler)
    print('\nGercek DB: %d isci, %d puantaj satiri, %d ay karsilastirildi'
          % (len(isciler), puantaj_sayisi, len(aylar)))
    # Vinc verisi yeni modulden ayni okunuyor
    assert ikiz.eski.get('/api/vinc/liste').get_json() == ikiz.yeni.get('/api/vinc/liste').get_json()
    # Gercek dosyanin kendisi degismedi (sadece kopya kullanildi)
    assert os.path.getsize(kaynak) > 0
