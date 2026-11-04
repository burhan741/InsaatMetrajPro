"""
Demirciler (4. adim): ayni cari motoru, farkli etiket/birim/para yonu.

NASIL TEST EDERIZ: pytest test_demirci.py
Kapsam: demirci etiketleri (ton, Is, Odenen, Kalan borcum, Toplam borc),
muteahhit/demirci ayrimi (listeler, sayfalar, ayni ad iki turde), bakiye ve
fiyat kilidi ayni motorla, ton kusuratli miktar, ana menu karti, PDF.
"""
import pytest

import cari
import ortak
from test_cari import firma, firma_ekle, hareket, kalem_id

DEMIR_KALEMLER = [{'ad': 'Temel demiri', 'birim_fiyat': 4500}, {'ad': 'Normal kat demiri', 'birim_fiyat': 5200}]


def demirci_ekle(c, ad='Usta Demir'):
    return firma_ekle(c, ad, kalemler=DEMIR_KALEMLER, tur='demirci')


def test_demirci_bakiye_borc(istemci):
    fid = demirci_ekle(istemci)
    kid = kalem_id(istemci, fid, 'Temel demiri')
    hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kid, miktar=12.350)   # 55.575
    hareket(istemci, fid, tip='gider', tarih='2026-11-02', tutar=3000, aciklama='Nakliye')
    hareket(istemci, fid, tip='odeme', tarih='2026-11-03', tutar=40000, aciklama='Nakit')
    b = firma(istemci, fid)['bakiye']
    assert (b['hakedis'], b['odenen'], b['kalan']) == (58575, 40000, 18575)
    assert b['is_miktar'] == 12.35


def test_demirci_fiyat_kilidi(istemci):
    fid = demirci_ekle(istemci)
    f = firma(istemci, fid)
    kid = kalem_id(istemci, fid, 'Normal kat demiri')
    h1 = hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kid, miktar=2)
    kalemler = [dict(k, birim_fiyat=5600 if k['id'] == kid else k['birim_fiyat']) for k in f['kalemler']]
    istemci.put('/api/cari/firma/%d' % fid, json={'ad': f['firma']['ad'], 'kalemler': kalemler})
    h2 = hareket(istemci, fid, tip='is', tarih='2026-11-02', kalem_id=kid, miktar=2)
    d = {h['id']: h for h in firma(istemci, fid)['defter']}
    assert (d[h1]['tutar'], d[h2]['tutar']) == (10400, 11200)


def test_fazla_odeme_demircide(istemci):
    fid = demirci_ekle(istemci)
    hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kalem_id(istemci, fid, 'Temel demiri'), miktar=1)
    hareket(istemci, fid, tip='odeme', tarih='2026-11-02', tutar=5000)
    b = firma(istemci, fid)['bakiye']
    assert b['kalan'] == -500 and b['fazla_odeme'] is True


def test_turler_birbirine_karismaz(istemci):
    m = firma_ekle(istemci, 'Ortak Ad')
    d = firma_ekle(istemci, 'Ortak Ad', kalemler=DEMIR_KALEMLER, tur='demirci')  # ayni ad iki turde serbest
    assert m != d
    hareket(istemci, m, tip='odeme', tarih='2026-11-01', tutar=100)
    hareket(istemci, d, tip='odeme', tarih='2026-11-01', tutar=7)
    lm = istemci.get('/api/cari/muteahhit/firmalar').get_json()
    ld = istemci.get('/api/cari/demirci/firmalar').get_json()
    assert [f['id'] for f in lm['firmalar']] == [m]
    assert [f['id'] for f in ld['firmalar']] == [d]
    assert (lm['toplam_kalan'], ld['toplam_kalan']) == (-100, -7)
    # Sayfa adresi turle uyusmali
    assert istemci.get('/demirci/%d' % d).status_code == 200
    assert istemci.get('/demirci/%d' % m).status_code == 404
    assert istemci.get('/muteahhit/%d' % d).status_code == 404
    # Ayni turde ayni ad yine reddedilir
    r = istemci.post('/api/cari/demirci/firmalar', json={'ad': 'ORTAK AD', 'kalemler': []})
    assert r.status_code == 400 and 'demirci zaten var' in r.get_json()['error']


def test_demirci_silme_muteahhide_dokunmaz(istemci):
    m = firma_ekle(istemci, 'M')
    d = demirci_ekle(istemci, 'D')
    hareket(istemci, m, tip='odeme', tarih='2026-11-01', tutar=100)
    hareket(istemci, d, tip='odeme', tarih='2026-11-01', tutar=100)
    assert istemci.delete('/api/cari/firma/%d' % d).status_code == 200
    assert firma(istemci, m)['bakiye']['odenen'] == 100
    assert istemci.get('/api/cari/demirci/firmalar').get_json()['firmalar'] == []


def test_ana_menu_demirci_karti(istemci):
    fid = demirci_ekle(istemci)
    hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kalem_id(istemci, fid, 'Temel demiri'), miktar=10)
    html = istemci.get('/').get_data(as_text=True)
    i = html.index('href="/demirci"')
    kart = html[html.rfind('<a class="kart', 0, i):html.index('</a>', i)]
    assert 'pasif' not in kart and 'Hazırlanıyor' not in kart
    assert 'Toplam borç' in kart
    assert 'tutar kirmizi">₺45.000<' in kart
    # Artik hicbir kart "Hazirlaniyor" degil
    assert 'Hazırlanıyor' not in html and 'kart pasif' not in html


@pytest.mark.parametrize('adres', ['/demirci', '/demirci/{fid}'])
def test_demirci_sayfa_etiketleri(istemci, adres):
    fid = demirci_ekle(istemci)
    html = istemci.get(adres.format(fid=fid)).get_data(as_text=True)
    assert '{{' not in html and '{%' not in html
    if adres == '/demirci':
        for p in ('Demirciler', '+ Demirci Ekle', 'Kalan = demirciye borcunuz.'):
            assert p in html, p
    else:
        for p in ('Kalan borcum', '>İş<', 'Ödenen para', 'Miktar (ton)', 'Nakliye, bağ teli',
                  'borcunuzu artırır', 'href="/demirci"'):
            assert p in html, p
        for yasak in ('Beton', 'Pompa', 'm³', 'Alınan para', 'Kalan alacak'):
            assert yasak not in html, yasak


def test_muteahhit_sayfasinda_demirci_metni_yok(istemci):
    fid = firma_ekle(istemci)
    html = istemci.get('/muteahhit/%d' % fid).get_data(as_text=True)
    for yasak in ('Kalan borcum', 'Ödenen para', 'Miktar (ton)', 'bağ teli'):
        assert yasak not in html, yasak
    assert 'Pompa, nakliye, katkı' in html


def test_demirci_dokum_etiketleri_ve_pdf(istemci):
    fid = demirci_ekle(istemci, 'Çelik Usta')
    kid = kalem_id(istemci, fid, 'Temel demiri')
    hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kid, miktar=2.5)
    hareket(istemci, fid, tip='odeme', tarih='2026-11-02', tutar=5000, aciklama='Havale')
    conn = ortak.baglan()
    try:
        v = cari.dokum_verisi(conn, fid)
    finally:
        conn.close()
    assert v['ayar']['kalan_etiket'] == 'Kalan borcum' and v['ayar']['odeme_kolon'] == 'Ödenen'
    assert v['kalan'] == 6250
    ust, alt = cari.hareket_aciklama(v['satirlar'][0], v['ayar'])
    assert (ust, alt) == ('Temel demiri', '2,5 ton × ₺4.500')
    assert cari.hareket_aciklama(v['satirlar'][1], v['ayar']) == ('Havale', 'Ödenen para')
    r = istemci.get('/api/cari/firma/%d/pdf' % fid)
    assert r.status_code == 200 and r.data[:4] == b'%PDF'
    assert 'dokum_Celik_Usta_' in r.headers['Content-Disposition']


def test_ton_miktari_uc_ondalik(istemci):
    fid = demirci_ekle(istemci)
    hid = hareket(istemci, fid, tip='is', tarih='2026-11-01', kalem_id=kalem_id(istemci, fid, 'Temel demiri'),
                  miktar=0.125)
    h = [x for x in firma(istemci, fid)['defter'] if x['id'] == hid][0]
    assert (h['miktar'], h['tutar']) == (0.125, 562.5)
    assert ortak.miktar_tr(h['miktar'], 3) == '0,125'
