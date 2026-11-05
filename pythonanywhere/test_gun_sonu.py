"""
Gun sonu raporu (5. adim) + Ayarlar + PWA ikon/manifest (6. adim).

NASIL TEST EDERIZ: pytest test_gun_sonu.py
"""
import json
from datetime import date

import pytest

import cari
import ortak
from test_cari import firma_ekle, hareket, kalem_id
from test_demirci import demirci_ekle

GUN = '2026-11-04'


def _kur(c):
    """A: onceki gun + rapor gunu + sonraki gun hareketi; B: sadece rapor gunu; C: hic o gun yok."""
    a = firma_ekle(c, 'Aydın Yapı')
    b = firma_ekle(c, 'Bora İnşaat')
    cc = firma_ekle(c, 'Ceylan Konut')
    ka = kalem_id(c, a, 'Normal katlar')     # 3250
    kb = kalem_id(c, b, 'Gro beton')         # 2800
    hareket(c, a, tip='is', tarih='2026-11-03', kalem_id=ka, miktar=10)    # 32.500 (devir)
    hareket(c, a, tip='is', tarih=GUN, kalem_id=ka, miktar=12)             # 39.000
    hareket(c, a, tip='odeme', tarih=GUN, tutar=20000, aciklama='Havale')
    hareket(c, a, tip='is', tarih='2026-11-05', kalem_id=ka, miktar=100)   # ertesi gun: rapora girmez
    hareket(c, b, tip='is', tarih=GUN, kalem_id=kb, miktar=2.5)            # 7.000
    hareket(c, b, tip='gider', tarih=GUN, tutar=1500, aciklama='Pompa')
    hareket(c, cc, tip='odeme', tarih='2026-11-01', tutar=4000)            # C: -4.000, o gun hareketsiz
    return a, b, cc


def test_gun_sonu_verisi_tumu(istemci):
    a, b, cc = _kur(istemci)
    conn = ortak.baglan()
    try:
        v = cari.gun_sonu_verisi(conn, 'muteahhit', GUN)
    finally:
        conn.close()
    assert [f['ad'] for f in v['firmalar']] == ['Aydın Yapı', 'Bora İnşaat']   # C o gun hareketsiz
    fa, fb = v['firmalar']
    assert (fa['miktar'], fa['hakedis'], fa['odenen']) == (12, 39000, 20000)
    assert fa['kalan'] == 32500 + 39000 - 20000            # ertesi gunun 325.000'i YOK
    assert (fb['miktar'], fb['hakedis'], fb['odenen'], fb['kalan']) == (2.5, 8500, 0, 8500)
    o = v['ozet']
    assert (o['miktar'], o['hakedis'], o['odenen'], o['firma_sayisi']) == (14.5, 47500, 20000, 2)
    # Gun sonu toplam kalan: kapsamdaki TUM firmalar (C'nin -4.000'i dahil)
    assert o['toplam_kalan'] == 51500 + 8500 - 4000
    assert len(v['hareketler']) == 4
    assert [h['firma_adi'] for h in v['hareketler']] == ['Aydın Yapı', 'Aydın Yapı', 'Bora İnşaat', 'Bora İnşaat']
    assert v['kapsam'] == 'Tümü'


def test_gun_sonu_tek_firma_ve_bos_gun(istemci):
    a, b, cc = _kur(istemci)
    r = istemci.get('/api/cari/muteahhit/gun-sonu?tarih=%s&firma_id=%d' % (GUN, b)).get_json()
    assert r['kapsam'] == 'Bora İnşaat'
    assert [f['id'] for f in r['firmalar']] == [b]
    assert r['ozet']['toplam_kalan'] == 8500
    bos = istemci.get('/api/cari/muteahhit/gun-sonu?tarih=2026-10-01').get_json()
    assert bos['firmalar'] == [] and bos['hareketler'] == []
    assert bos['ozet']['toplam_kalan'] == 0


def test_gun_sonu_turler_ayri(istemci):
    _kur(istemci)
    d = demirci_ekle(istemci)
    hareket(istemci, d, tip='is', tarih=GUN, kalem_id=kalem_id(istemci, d, 'Temel demiri'), miktar=1)
    m = istemci.get('/api/cari/muteahhit/gun-sonu?tarih=' + GUN).get_json()
    dm = istemci.get('/api/cari/demirci/gun-sonu?tarih=' + GUN).get_json()
    assert 'Usta Demir' not in [f['ad'] for f in m['firmalar']]
    assert [f['ad'] for f in dm['firmalar']] == ['Usta Demir']
    assert dm['ozet']['hakedis'] == 4500
    # Baska turun firmasi kapsam olarak verilemez
    assert istemci.get('/api/cari/demirci/gun-sonu?tarih=%s&firma_id=%d' % (GUN, m['firmalar'][0]['id'])).status_code == 404


@pytest.mark.parametrize('qs, kod', [('tarih=04.11.2026', 400), ('tarih=%s&firma_id=abc' % GUN, 400),
                                     ('tarih=%s&firma_id=9999' % GUN, 404)])
def test_gun_sonu_hatali_parametre(istemci, qs, kod):
    assert istemci.get('/api/cari/muteahhit/gun-sonu?' + qs).status_code == kod


def test_gun_sonu_varsayilan_bugun(istemci):
    r = istemci.get('/api/cari/muteahhit/gun-sonu').get_json()
    assert r['tarih'] == ortak.bugun_tr()


def test_gun_sonu_pdf(istemci):
    a, b, cc = _kur(istemci)
    istemci.post('/api/cari/ayar', json={'rapor_basligi': 'Örnek Hazır Beton A.Ş.'})
    for qs in ('tarih=' + GUN, 'tarih=%s&firma_id=%d' % (GUN, a), 'tarih=2026-10-01', ''):
        r = istemci.get('/api/cari/muteahhit/gun-sonu/pdf?' + qs)
        assert r.status_code == 200, qs
        assert r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF'
        assert 'inline' in r.headers['Content-Disposition']
    r = istemci.get('/api/cari/muteahhit/gun-sonu/pdf?tarih=%s&firma_id=%d' % (GUN, a))
    assert 'gun_sonu_muteahhit_Aydin_Yapi_%s.pdf' % GUN in r.headers['Content-Disposition']
    assert istemci.get('/api/cari/demirci/gun-sonu/pdf?tarih=' + GUN).status_code == 200
    assert istemci.get('/api/cari/taseron/gun-sonu/pdf').status_code == 404


# ---------------- Ayarlar ----------------
def test_ayar_varsayilan_kaydet_ve_puantaja_dokunmaz(istemci):
    once = istemci.get('/api/ayarlar').get_json()           # puantaj ayarlari
    assert istemci.get('/api/cari/ayar').get_json() == {'rapor_basligi': '[FİRMA ADI]'}
    assert istemci.post('/api/cari/ayar', json={'rapor_basligi': '  Yılmaz   Beton  '}).status_code == 200
    assert istemci.get('/api/cari/ayar').get_json() == {'rapor_basligi': 'Yılmaz Beton'}
    assert istemci.post('/api/cari/ayar', json={'baska': 'x'}).status_code == 400
    assert istemci.get('/api/ayarlar').get_json() == once     # puantaj ayarlari aynen
    html = istemci.get('/').get_data(as_text=True)
    assert 'value="Yılmaz Beton"' in html and "modalAc('ayarlar')" in html
    # Bos kaydedilirse varsayilana doner
    istemci.post('/api/cari/ayar', json={'rapor_basligi': ''})
    assert istemci.get('/api/cari/ayar').get_json()['rapor_basligi'] == '[FİRMA ADI]'


def test_ayar_html_kacislanir(istemci):
    istemci.post('/api/cari/ayar', json={'rapor_basligi': '"><script>x</script>'})
    html = istemci.get('/').get_data(as_text=True)
    assert '<script>x</script>' not in html


# ---------------- Sayfalar ----------------
@pytest.mark.parametrize('tur, etiket', [('muteahhit', 'Günün tahsilatı'), ('demirci', 'Günün ödemesi')])
def test_gun_sonu_sayfasi(istemci, tur, etiket):
    if tur == 'muteahhit':
        firma_ekle(istemci, 'Kapsam <Firma>')
    else:
        demirci_ekle(istemci, 'Kapsam <Firma>')
    r = istemci.get('/%s/gun-sonu' % tur)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    for p in ('Gün Sonu Raporu', 'PDF Oluştur', etiket, 'Kapsam &lt;Firma&gt;', "modalAc('yardim')",
              'href="/%s"' % tur, 'Tümü'):
        assert p in html, p
    assert '{{' not in html and '{%' not in html
    liste = istemci.get('/' + tur).get_data(as_text=True)
    assert 'href="/%s/gun-sonu"' % tur in liste


# ---------------- PWA ----------------
def test_pwa_ikon_ve_manifest(istemci):
    for adres in ('/apple-touch-icon.png', '/apple-touch-icon-precomposed.png', '/ikon-512.png'):
        r = istemci.get(adres)
        assert r.status_code == 200 and r.mimetype == 'image/png'
        assert r.data[:8] == b'\x89PNG\r\n\x1a\n'
    m = istemci.get('/manifest.webmanifest')
    assert m.status_code == 200 and m.mimetype == 'application/manifest+json'
    veri = json.loads(m.get_data(as_text=True))
    assert veri['start_url'] == '/' and veri['display'] == 'standalone'
    assert {i['sizes'] for i in veri['icons']} == {'180x180', '512x512'}


def test_yeni_sayfalarda_pwa_basligi(istemci):
    fid = firma_ekle(istemci)
    for adres in ('/', '/vinc', '/muteahhit', '/muteahhit/%d' % fid, '/muteahhit/gun-sonu', '/demirci'):
        html = istemci.get(adres).get_data(as_text=True)
        for p in ('rel="apple-touch-icon"', 'rel="manifest"', 'viewport-fit=cover',
                  'apple-mobile-web-app-capable'):
            assert p in html, (adres, p)


def test_her_yeni_ekranda_yardim_var(istemci):
    fid = firma_ekle(istemci)
    did = demirci_ekle(istemci)
    for adres in ('/', '/vinc', '/muteahhit', '/muteahhit/%d' % fid, '/muteahhit/gun-sonu',
                  '/demirci', '/demirci/%d' % did, '/demirci/gun-sonu'):
        html = istemci.get(adres).get_data(as_text=True)
        assert 'aria-label="Yardım"' in html, adres
        assert 'Nasıl kullanılır?' in html, adres
