"""
Cari motoru + Muteahhitler (3. adim).

NASIL TEST EDERIZ: pytest test_cari.py
Kapsam: bakiye (gider hakedise eklenir), fiyat kilidi, satir duzenlemede fiyat,
kalem silme/yeniden adlandirma, firma silme kaskadi, fazla odeme, dogrulamalar,
devirli hesap dokumu, sayfalar, PDF, demircinin bu adimda kapali olmasi.
"""
import sqlite3

import pytest

import cari
import ortak


# ---------------- yardimcilar ----------------
def firma_ekle(c, ad='Yılmaz İnşaat', kalemler=None, tur='muteahhit'):
    if kalemler is None:
        kalemler = [{'ad': 'Gro beton', 'birim_fiyat': 2800}, {'ad': 'Normal katlar', 'birim_fiyat': 3250}]
    r = c.post('/api/cari/%s/firmalar' % tur, json={'ad': ad, 'kalemler': kalemler})
    assert r.status_code == 200, r.get_json()
    return r.get_json()['id']


def firma(c, fid):
    r = c.get('/api/cari/firma/%d' % fid)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def kalem_id(c, fid, ad):
    return [k['id'] for k in firma(c, fid)['kalemler'] if k['ad'] == ad][0]


def hareket(c, fid, **d):
    r = c.post('/api/cari/firma/%d/hareket' % fid, json=d)
    assert r.status_code == 200, r.get_json()
    return r.get_json()['id']


# ---------------- bakiye ----------------
def test_bakiye_beton_gider_odeme(istemci):
    fid = firma_ekle(istemci)
    kid = kalem_id(istemci, fid, 'Normal katlar')
    hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kid, miktar=12)        # 39.000
    hareket(istemci, fid, tip='is', tarih='2026-11-02', kalem_id=kid, miktar=12.5)      # 40.625
    hareket(istemci, fid, tip='gider', tarih='2026-11-02', tutar=5000, aciklama='Pompa')
    hareket(istemci, fid, tip='odeme', tarih='2026-11-03', tutar=50000, aciklama='Havale')
    b = firma(istemci, fid)['bakiye']
    assert b['hakedis'] == 39000 + 40625 + 5000   # gider hakedise EKLENIR
    assert b['odenen'] == 50000
    assert b['kalan'] == 34625
    assert b['is_miktar'] == 24.5
    assert b['fazla_odeme'] is False


def test_tutar_kurus_yarim_yukari(istemci):
    fid = firma_ekle(istemci, kalemler=[{'ad': 'K', 'birim_fiyat': 0.5}])
    hid = hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kalem_id(istemci, fid, 'K'), miktar=0.25)
    h = [x for x in firma(istemci, fid)['defter'] if x['id'] == hid][0]
    assert h['tutar'] == 0.13   # 0.125 -> 0.13 (round() 0.12 verirdi)


def test_fazla_odeme_sifirlanmaz(istemci):
    fid = firma_ekle(istemci)
    hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kalem_id(istemci, fid, 'Gro beton'), miktar=10)
    hareket(istemci, fid, tip='odeme', tarih='2026-11-02', tutar=30000)
    b = firma(istemci, fid)['bakiye']
    assert b['kalan'] == -2000
    assert b['fazla_odeme'] is True
    liste = istemci.get('/api/cari/muteahhit/firmalar').get_json()
    assert liste['toplam_kalan'] == -2000


# ---------------- fiyat kilidi ----------------
def test_fiyat_degisimi_gecmis_satiri_degistirmez(istemci):
    fid = firma_ekle(istemci)
    f = firma(istemci, fid)
    kid = kalem_id(istemci, fid, 'Normal katlar')
    eski = hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kid, miktar=10)
    # Fiyat 3250 -> 3500 (ayni kalem id'si ile guncelle)
    kalemler = [dict(k, birim_fiyat=3500 if k['id'] == kid else k['birim_fiyat']) for k in f['kalemler']]
    assert istemci.put('/api/cari/firma/%d' % fid, json={'ad': f['firma']['ad'], 'kalemler': kalemler}).status_code == 200
    yeni = hareket(istemci, fid, tip='is', tarih='2026-11-02', kalem_id=kid, miktar=10)
    d = {h['id']: h for h in firma(istemci, fid)['defter']}
    assert (d[eski]['birim_fiyat'], d[eski]['tutar']) == (3250, 32500)
    assert (d[yeni]['birim_fiyat'], d[yeni]['tutar']) == (3500, 35000)


def test_istemci_fiyat_gonderse_de_yeni_satir_kalem_fiyatini_alir(istemci):
    fid = firma_ekle(istemci)
    kid = kalem_id(istemci, fid, 'Gro beton')
    hid = hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kid, miktar=2, birim_fiyat=1, tutar=1)
    h = [x for x in firma(istemci, fid)['defter'] if x['id'] == hid][0]
    assert (h['birim_fiyat'], h['tutar']) == (2800, 5600)


def test_satir_duzenlemede_fiyat_bilerek_degisir_sadece_o_satir(istemci):
    fid = firma_ekle(istemci)
    kid = kalem_id(istemci, fid, 'Gro beton')
    h1 = hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kid, miktar=10)
    h2 = hareket(istemci, fid, tip='is', tarih='2026-11-02', kalem_id=kid, miktar=10)
    r = istemci.put('/api/cari/hareket/%d' % h1, json={'tarih': '2026-11-01', 'kalem_id': kid,
                                                      'miktar': 8, 'birim_fiyat': 2900})
    assert r.status_code == 200
    d = {h['id']: h for h in firma(istemci, fid)['defter']}
    assert (d[h1]['miktar'], d[h1]['birim_fiyat'], d[h1]['tutar']) == (8, 2900, 23200)
    assert d[h2]['tutar'] == 28000
    # Kalemin kendi fiyati degismedi
    assert [k['birim_fiyat'] for k in firma(istemci, fid)['kalemler'] if k['id'] == kid] == [2800]


def test_kalem_yeniden_adlandirma_ve_silme_gecmisi_bozmaz(istemci):
    fid = firma_ekle(istemci)
    kid = kalem_id(istemci, fid, 'Gro beton')
    hid = hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kid, miktar=3)
    # Kalemi sil (listeden cikar)
    f = firma(istemci, fid)
    kalan = [k for k in f['kalemler'] if k['id'] != kid]
    istemci.put('/api/cari/firma/%d' % fid, json={'ad': f['firma']['ad'], 'kalemler': kalan})
    h = [x for x in firma(istemci, fid)['defter'] if x['id'] == hid][0]
    assert (h['kalem_adi'], h['tutar']) == ('Gro beton', 8400)
    # Silinmis kalemli satir duzenlenebilir (ayni kalem_id ile), ad korunur
    r = istemci.put('/api/cari/hareket/%d' % hid, json={'tarih': '2026-11-01', 'kalem_id': kid,
                                                       'miktar': 4, 'birim_fiyat': 2800})
    assert r.status_code == 200
    h = [x for x in firma(istemci, fid)['defter'] if x['id'] == hid][0]
    assert (h['kalem_adi'], h['tutar']) == ('Gro beton', 11200)


def test_baska_firmanin_kalemi_kullanilamaz(istemci):
    f1 = firma_ekle(istemci, 'A')
    f2 = firma_ekle(istemci, 'B')
    r = istemci.post('/api/cari/firma/%d/hareket' % f1,
                     json={'tip': 'is', 'tarih': '2026-11-01', 'kalem_id': kalem_id(istemci, f2, 'Gro beton'), 'miktar': 1})
    assert r.status_code == 400


# ---------------- silme ----------------
def test_firma_silme_kaskad_ve_diger_firma_korunur(istemci, yeni_db):
    f1 = firma_ekle(istemci, 'Silinecek')
    f2 = firma_ekle(istemci, 'Kalacak')
    for fid in (f1, f2):
        hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kalem_id(istemci, fid, 'Gro beton'), miktar=5)
        hareket(istemci, fid, tip='odeme', tarih='2026-11-02', tutar=1000)
    assert istemci.delete('/api/cari/firma/%d' % f1).status_code == 200
    conn = sqlite3.connect(yeni_db)
    for tablo, kolon in (('cari_firma', 'id'), ('cari_hareket', 'firma_id'), ('cari_fiyat_kalemi', 'firma_id')):
        assert conn.execute('SELECT COUNT(*) FROM %s WHERE %s=?' % (tablo, kolon), (f1,)).fetchone()[0] == 0
    assert conn.execute('SELECT COUNT(*) FROM cari_hareket WHERE firma_id=?', (f2,)).fetchone()[0] == 2
    conn.close()
    assert istemci.get('/api/cari/firma/%d' % f1).status_code == 404
    assert istemci.get('/muteahhit/%d' % f1).status_code == 404


def test_hareket_sil_ve_404(istemci):
    fid = firma_ekle(istemci)
    hid = hareket(istemci, fid, tip='gider', tarih='2026-11-01', tutar=700)
    assert istemci.delete('/api/cari/hareket/%d' % hid).status_code == 200
    assert firma(istemci, fid)['bakiye']['hakedis'] == 0
    assert istemci.delete('/api/cari/hareket/%d' % hid).status_code == 404
    assert istemci.put('/api/cari/hareket/999', json={'tarih': '2026-11-01', 'tutar': 5}).status_code == 404


def test_duzenlemede_tip_degismez(istemci):
    fid = firma_ekle(istemci)
    hid = hareket(istemci, fid, tip='odeme', tarih='2026-11-01', tutar=1000)
    istemci.put('/api/cari/hareket/%d' % hid, json={'tip': 'gider', 'tarih': '2026-11-01', 'tutar': 1500})
    h = firma(istemci, fid)['defter'][0]
    assert (h['tip'], h['tutar']) == ('odeme', 1500)


# ---------------- dogrulama ----------------
@pytest.mark.parametrize('govde, parca', [
    ({'ad': '', 'kalemler': []}, 'Firma adını'),
    ({'ad': 'X', 'kalemler': [{'ad': 'Gro', 'birim_fiyat': 0}]}, 'birim fiyat'),
    ({'ad': 'X', 'kalemler': [{'ad': 'Gro', 'birim_fiyat': 'abc'}]}, 'birim fiyat'),
    ({'ad': 'X', 'kalemler': [{'ad': '', 'birim_fiyat': 100}]}, 'adı boş'),
    ({'ad': 'X', 'kalemler': [{'ad': 'Gro', 'birim_fiyat': 1}, {'ad': 'gro', 'birim_fiyat': 2}]}, 'iki kez'),
])
def test_firma_dogrulama(istemci, govde, parca):
    r = istemci.post('/api/cari/muteahhit/firmalar', json=govde)
    assert r.status_code == 400
    assert parca in r.get_json()['error']


def test_bos_kalem_satirlari_atlanir_ve_kalemsiz_firma_olur(istemci):
    fid = firma_ekle(istemci, kalemler=[{'ad': '', 'birim_fiyat': ''}, {}])
    assert firma(istemci, fid)['kalemler'] == []
    r = istemci.post('/api/cari/firma/%d/hareket' % fid, json={'tip': 'is', 'tarih': '2026-11-01', 'miktar': 1})
    assert r.status_code == 400 and 'kalemi' in r.get_json()['error']


def test_ayni_adli_firma_reddedilir_duzenlemede_kendisi_serbest(istemci):
    fid = firma_ekle(istemci, 'Yılmaz İnşaat')
    for ayni in ('Yılmaz İnşaat', 'YILMAZ İNŞAAT', 'yılmaz  inşaat ', '  Yılmaz İnşaat'):
        r = istemci.post('/api/cari/muteahhit/firmalar', json={'ad': ayni, 'kalemler': []})
        assert r.status_code == 400, ayni
        assert 'zaten var' in r.get_json()['error']
    # Farkli ad serbest; duzenlemede kendi adi serbest
    assert istemci.post('/api/cari/muteahhit/firmalar', json={'ad': 'Yilmaz Insaat', 'kalemler': []}).status_code == 200
    assert istemci.put('/api/cari/firma/%d' % fid, json={'ad': 'YILMAZ İNŞAAT', 'kalemler': []}).status_code == 200
    # Kalem adlarinda da Turkce kurali
    r = istemci.post('/api/cari/muteahhit/firmalar', json={'ad': 'Z', 'kalemler': [
        {'ad': 'Islak beton', 'birim_fiyat': 1}, {'ad': 'ıslak BETON', 'birim_fiyat': 2}]})
    assert r.status_code == 400 and 'iki kez' in r.get_json()['error']


def test_tr_kucuk():
    assert ortak.tr_kucuk('YILMAZ İNŞAAT') == ortak.tr_kucuk('Yılmaz  İnşaat') == 'yılmaz inşaat'
    assert ortak.tr_kucuk('Yilmaz') != ortak.tr_kucuk('Yılmaz')


@pytest.mark.parametrize('govde', [
    {'tip': 'xx', 'tarih': '2026-11-01', 'tutar': 5},
    {'tip': 'gider', 'tarih': '2026-11-01', 'tutar': 0},
    {'tip': 'odeme', 'tarih': '2026-11-01', 'tutar': -5},
    {'tip': 'odeme', 'tarih': '01.11.2026', 'tutar': 5},
    {'tip': 'is', 'tarih': '2026-11-01', 'kalem_id': 'abc', 'miktar': 5},
    {'tip': 'is', 'tarih': '2026-11-01', 'kalem_id': None, 'miktar': 0},
])
def test_hareket_dogrulama(istemci, govde):
    fid = firma_ekle(istemci)
    r = istemci.post('/api/cari/firma/%d/hareket' % fid, json=govde)
    assert r.status_code == 400
    assert firma(istemci, fid)['defter'] == []


# ---------------- liste / ana menu ----------------
def test_liste_son_hareket_ve_siralama(istemci):
    a = firma_ekle(istemci, 'Aaa')
    b = firma_ekle(istemci, 'Bbb')
    firma_ekle(istemci, 'Ccc')  # hareketsiz -> en sonda
    hareket(istemci, a, tip='odeme', tarih='2026-10-01', tutar=10)
    hareket(istemci, b, tip='is', tarih='2026-11-01', kalem_id=kalem_id(istemci, b, 'Gro beton'), miktar=2)
    l = istemci.get('/api/cari/muteahhit/firmalar').get_json()
    assert [f['ad'] for f in l['firmalar']] == ['Bbb', 'Aaa', 'Ccc']
    assert l['firmalar'][0]['son_hareket']['kalem_adi'] == 'Gro beton'
    assert l['firmalar'][2]['son_hareket'] is None
    assert l['toplam_kalan'] == 5600 - 10


def test_ana_menu_toplam_alacak(istemci):
    fid = firma_ekle(istemci)
    hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kalem_id(istemci, fid, 'Normal katlar'), miktar=100)
    html = istemci.get('/').get_data(as_text=True)
    # Yuzen kart: Toplam alacak yesil + yaninda "alacak" yazisi (renk tek basina anlam tasimaz)
    assert 'ozet-d renk-alacak">₺325.000<' in html
    assert 'ozet-not renk-alacak">alacak<' in html
    assert 'href="/muteahhit"' in html and '1 firma' in html


def test_tanimsiz_tur_404(istemci):
    assert istemci.get('/api/cari/taseron/firmalar').status_code == 404
    assert istemci.post('/api/cari/taseron/firmalar', json={'ad': 'X'}).status_code == 404


# ---------------- dokum / PDF ----------------
def _dokum_kur(istemci):
    fid = firma_ekle(istemci)
    kid = kalem_id(istemci, fid, 'Normal katlar')
    hareket(istemci, fid, tip='is', tarih='2026-10-10', kalem_id=kid, miktar=10)     # 32.500
    hareket(istemci, fid, tip='odeme', tarih='2026-10-20', tutar=20000)
    hareket(istemci, fid, tip='is', tarih='2026-11-05', kalem_id=kid, miktar=4)      # 13.000
    hareket(istemci, fid, tip='gider', tarih='2026-11-06', tutar=1000)
    hareket(istemci, fid, tip='odeme', tarih='2026-11-07', tutar=5000)
    hareket(istemci, fid, tip='is', tarih='2026-12-01', kalem_id=kid, miktar=1)      # 3.250
    return fid


def test_dokum_devir_ve_kalan(istemci):
    fid = _dokum_kur(istemci)
    conn = ortak.baglan()
    try:
        tum = cari.dokum_verisi(conn, fid)
        kasim = cari.dokum_verisi(conn, fid, '2026-11-01', '2026-11-30')
    finally:
        conn.close()
    assert tum['devir'] is None and len(tum['satirlar']) == 6
    assert tum['kalan'] == 32500 + 13000 + 1000 + 3250 - 25000
    assert kasim['devir'] == 12500
    assert [s['tarih'] for s in kasim['satirlar']] == ['2026-11-05', '2026-11-06', '2026-11-07']
    assert (kasim['donem']['hakedis'], kasim['donem']['odenen']) == (14000, 5000)
    # KALAN = 30.11 itibariyla gercek bakiye = devir + donem
    assert kasim['kalan'] == 12500 + 14000 - 5000 == 21500


def test_pdf_tum_ve_aralik(istemci):
    fid = _dokum_kur(istemci)
    for qs in ('', '?bas=2026-11-01&bit=2026-11-30', '?bas=&bit=', '?bas=2026-11-01'):
        r = istemci.get('/api/cari/firma/%d/pdf%s' % (fid, qs))
        assert r.status_code == 200, (qs, r.data[:200])
        assert r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF'
        assert 'inline' in r.headers['Content-Disposition']
        assert 'dokum_Yilmaz_Insaat_' in r.headers['Content-Disposition']
    assert istemci.get('/api/cari/firma/%d/pdf?bas=2026-12-01&bit=2026-11-01' % fid).status_code == 400
    assert istemci.get('/api/cari/firma/%d/pdf?bas=xx' % fid).status_code == 400


def test_pdf_ozel_karakterli_firma_adi(istemci):
    fid = firma_ekle(istemci, 'A & B <Yapı> Ltd. Şti.')
    hareket(istemci, fid, tip='gider', tarih='2026-11-01', tutar=10, aciklama='<b>katkı</b> & su')
    r = istemci.get('/api/cari/firma/%d/pdf' % fid)
    assert r.status_code == 200 and r.data[:4] == b'%PDF'


def test_hareket_aciklama_metni():
    ayar = cari.TURLER['muteahhit']
    ust, alt = cari.hareket_aciklama({'tip': 'is', 'kalem_adi': 'Gro beton', 'miktar': 12, 'birim_fiyat': 3250,
                                      'aciklama': ''}, ayar)
    assert (ust, alt) == ('Gro beton', '12 m³ × ₺3.250')
    assert cari.hareket_aciklama({'tip': 'odeme', 'aciklama': ''}, ayar) == ('Alınan', 'Alınan para')


# ---------------- sayfalar ----------------
def test_liste_sayfasi(istemci):
    r = istemci.get('/muteahhit')
    assert r.status_code == 200 and r.headers['Cache-Control'].startswith('no-store')
    html = r.get_data(as_text=True)
    for p in ('Müteahhitler', '+ Müteahhit Ekle', 'href="/"', "modalAc('yardim')", 'Firma ara',
              'function firmaKaydet', 'kaydirmaKur(el(\'liste\')', 'Birim fiyat kalemleri'):
        assert p in html, p
    assert '{{' not in html and '{%' not in html


def test_firma_sayfasi(istemci):
    fid = firma_ekle(istemci, 'Yılmaz <İnşaat>')
    r = istemci.get('/muteahhit/%d' % fid)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    for p in ('Kalan alacak', 'Beton', 'Alınan para', 'Satırı Ekle', 'Önceki kayıtlar', 'PDF Oluştur',
              'Yılmaz &lt;İnşaat&gt;', 'href="/muteahhit"', 'var FIRMA_ID = %d;' % fid):
        assert p in html, p
    assert '<İnşaat>' not in html  # firma adi kacislandi
    assert '{{' not in html and '{%' not in html
    assert istemci.get('/muteahhit/99999').status_code == 404
