"""
ortak.py bicimleme/yedek, ana menu, vinc tasimasi ve gomulu JS kontrolu.

NASIL TEST EDERIZ: pytest test_ortak_ana_menu.py
"""
import os
import re
import shutil
import subprocess
import tempfile

import pytest

import app as app_modul
import ortak
import puantaj
from conftest import eski_app_yukle


# ---------------- ortak.py bicimleme ----------------
@pytest.mark.parametrize('deger, beklenen', [
    (1284500, '₺1.284.500'),
    (0, '₺0'),
    (None, '₺0'),
    (40625.5, '₺40.625,50'),
    (3250, '₺3.250'),
    (-500, '-₺500'),
    (999.999, '₺1.000'),
])
def test_para_tl(deger, beklenen):
    assert ortak.para_tl(deger) == beklenen


@pytest.mark.parametrize('deger, beklenen', [
    (12.5, '12,5'), (12.0, '12'), (1250.75, '1.250,75'), (0.125, '0,13'), (None, '0'),
])
def test_miktar_tr(deger, beklenen):
    assert ortak.miktar_tr(deger) == beklenen


def test_tarih_tr():
    assert ortak.tarih_tr('2026-11-04') == '04.11.2026'
    assert ortak.tarih_tr('2026-11-04 13:45:00') == '04.11.2026'
    assert ortak.tarih_tr('') == ''
    assert ortak.tarih_tr(None) == ''


def test_yedek_ilk_calistirmada_alinmaz_sonra_gunde_bir(tmp_path, monkeypatch):
    yol = str(tmp_path / 'puantaj.db')
    monkeypatch.setattr(ortak, 'DB_PATH', yol)
    monkeypatch.setattr(puantaj, 'DB_PATH', yol)
    ortak.veritabani_hazirla(app_modul.INIT_FONKSIYONLARI)
    assert not os.path.exists(str(tmp_path / 'backups'))
    ortak.veritabani_hazirla(app_modul.INIT_FONKSIYONLARI)
    ortak.veritabani_hazirla(app_modul.INIT_FONKSIYONLARI)
    assert len(os.listdir(str(tmp_path / 'backups'))) == 1


def test_mevcut_tablolar_ve_veri_korunur(tmp_path, monkeypatch):
    """Eski uygulamanin olusturdugu DB'de init tekrar calisinca veri aynen kalir."""
    eski = eski_app_yukle(str(tmp_path / 'eski'))
    c = eski.app.test_client()
    c.post('/api/isci', json={'ad_soyad': 'Ali', 'gunluk_ucret': 1500})
    c.post('/api/vinc/ekle', json={'tip': 'gelir', 'miktar': 5000, 'aciklama': 'Kira'})
    yol = str(tmp_path / 'eski' / 'puantaj.db')
    monkeypatch.setattr(ortak, 'DB_PATH', yol)
    monkeypatch.setattr(puantaj, 'DB_PATH', yol)
    ortak.veritabani_hazirla(app_modul.INIT_FONKSIYONLARI)
    y = app_modul.app.test_client()
    assert [i['ad_soyad'] for i in y.get('/api/isci').get_json()] == ['Ali']
    assert y.get('/api/vinc/liste').get_json()['net'] == 5000


# ---------------- vinc tasimasi ----------------
def _created_at_sil(cevap):
    for k in cevap['kayitlar']:
        k.pop('created_at', None)
    return cevap


def test_vinc_api_eski_ile_ayni(tmp_path, monkeypatch):
    eski = eski_app_yukle(str(tmp_path / 'eski'))
    ec = eski.app.test_client()
    yol = str(tmp_path / 'yeni.db')
    monkeypatch.setattr(ortak, 'DB_PATH', yol)
    monkeypatch.setattr(puantaj, 'DB_PATH', yol)
    ortak.veritabani_hazirla(app_modul.INIT_FONKSIYONLARI)
    yc = app_modul.app.test_client()
    istekler = [
        {'tip': 'gelir', 'miktar': 12000.5, 'aciklama': 'Kira', 'tarih': '2026-11-01'},
        {'tip': 'gider', 'miktar': '3500', 'aciklama': 'Yakit', 'tarih': '2026-11-02'},
        {'tip': 'gelir', 'miktar': 800},
        {'tip': 'xx', 'miktar': 5},
        {'tip': 'gider', 'miktar': 0},
        {'tip': 'gider', 'miktar': 'abc'},
    ]
    for d in istekler:
        r1, r2 = ec.post('/api/vinc/ekle', json=d), yc.post('/api/vinc/ekle', json=d)
        assert r1.status_code == r2.status_code
        assert r1.get_json() == r2.get_json()
    l1 = _created_at_sil(ec.get('/api/vinc/liste').get_json())
    l2 = _created_at_sil(yc.get('/api/vinc/liste').get_json())
    assert l1 == l2
    assert l2['net'] == 9300.5
    sil_id = l2['kayitlar'][0]['id']
    assert ec.post('/api/vinc/sil', json={'id': sil_id}).get_json() == \
        yc.post('/api/vinc/sil', json={'id': sil_id}).get_json()
    assert yc.post('/api/vinc/sil', json={}).status_code == 400
    assert _created_at_sil(ec.get('/api/vinc/liste').get_json()) == \
        _created_at_sil(yc.get('/api/vinc/liste').get_json())


# ---------------- ana menu ----------------
def test_ana_menu_dort_kart(istemci):
    istemci.post('/api/vinc/ekle', json={'tip': 'gelir', 'miktar': 15000})
    istemci.post('/api/vinc/ekle', json={'tip': 'gider', 'miktar': 2500})
    r = istemci.get('/')
    assert r.status_code == 200
    assert r.headers['Cache-Control'].startswith('no-store')
    html = r.get_data(as_text=True)
    for ad in ('Müteahhitler', 'Demirciler', 'Puantaj', 'Mobil Vinç'):
        assert ad in html
    assert 'href="/puantaj"' in html
    assert '₺12.500' in html
    assert 'viewport-fit=cover' in html
    assert 'yardimAc()' in html


def test_ana_menu_vinc_eksi_kirmizi(istemci):
    istemci.post('/api/vinc/ekle', json={'tip': 'gider', 'miktar': 700})
    html = istemci.get('/').get_data(as_text=True)
    assert 'tutar kirmizi">-₺700<' in html


def test_puantaj_api_adresleri_yerinde(istemci):
    kurallar = {r.rule for r in app_modul.app.url_map.iter_rules()}
    for adres in ('/', '/puantaj', '/api/isci', '/api/puantaj', '/api/ozet/haftalik',
                  '/api/pdf/aylik', '/api/vinc/liste', '/api/vinc/ekle', '/api/vinc/sil',
                  '/api/hatirlatma', '/api/admin/milat-temizle'):
        assert adres in kurallar, adres


# ---------------- gomulu JS sozdizimi ----------------
def _scriptler(html):
    return re.findall(r'<script>(.*?)</script>', html, re.S)


@pytest.mark.skipif(shutil.which('node') is None, reason='node yok')
def test_gomulu_js_node_check(istemci):
    sayfalar = {'ana_menu': istemci.get('/').get_data(as_text=True),
                'puantaj': istemci.get('/puantaj?v=1').get_data(as_text=True)}
    for ad, html in sayfalar.items():
        js_listesi = _scriptler(html)
        assert js_listesi, ad
        for i, js in enumerate(js_listesi):
            fd, yol = tempfile.mkstemp(suffix='.js')
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(js)
            try:
                p = subprocess.run(['node', '--check', yol], capture_output=True, text=True)
                assert p.returncode == 0, '%s #%d: %s' % (ad, i, p.stderr)
            finally:
                os.remove(yol)
