"""
Mobil Vinc modulu (2. adim): duzenleme, dogrulama, sayfa, ortak JS.

NASIL TEST EDERIZ: pytest test_vinc.py
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

import ortak


def _ekle(c, **d):
    r = c.post('/api/vinc/ekle', json=d)
    assert r.status_code == 200, r.get_json()


def _liste(c):
    return c.get('/api/vinc/liste').get_json()


def test_duzenleme_kaydi_ve_toplamlari_gunceller(istemci):
    _ekle(istemci, tip='gelir', miktar=10000, aciklama='Kira', tarih='2026-11-01')
    _ekle(istemci, tip='gider', miktar=2000, aciklama='Yakit', tarih='2026-11-02')
    yakit = [k for k in _liste(istemci)['kayitlar'] if k['aciklama'] == 'Yakit'][0]

    r = istemci.put('/api/vinc/%d' % yakit['id'], json={
        'tip': 'gider', 'miktar': '2500.5', 'aciklama': '  Yakit + yag ', 'tarih': '2026-11-03'})
    assert r.status_code == 200
    l = _liste(istemci)
    k = [x for x in l['kayitlar'] if x['id'] == yakit['id']][0]
    assert (k['miktar'], k['aciklama'], k['tarih'], k['tip']) == (2500.5, 'Yakit + yag', '2026-11-03', 'gider')
    assert l['toplam_gider'] == 2500.5
    assert l['net'] == 7499.5
    # Siralama yeniden eskiye: duzenlenen tarih en uste
    assert l['kayitlar'][0]['id'] == yakit['id']
    # Diger kayda dokunulmadi
    assert [x for x in l['kayitlar'] if x['aciklama'] == 'Kira'][0]['miktar'] == 10000


def test_duzenlemede_tur_degisimi_neti_iki_kat_etkiler(istemci):
    _ekle(istemci, tip='gider', miktar=1000, tarih='2026-11-01')
    kid = _liste(istemci)['kayitlar'][0]['id']
    istemci.put('/api/vinc/%d' % kid, json={'tip': 'gelir', 'miktar': 1000, 'tarih': '2026-11-01'})
    l = _liste(istemci)
    assert (l['toplam_gelir'], l['toplam_gider'], l['net']) == (1000, 0, 1000)


@pytest.mark.parametrize('govde, mesaj', [
    ({'tip': 'xx', 'miktar': 5, 'tarih': '2026-11-01'}, 'Gecersiz tip'),
    ({'tip': 'gelir', 'miktar': 0, 'tarih': '2026-11-01'}, 'Gecersiz miktar'),
    ({'tip': 'gelir', 'miktar': -5, 'tarih': '2026-11-01'}, 'Gecersiz miktar'),
    ({'tip': 'gelir', 'miktar': 'abc', 'tarih': '2026-11-01'}, 'Gecersiz miktar'),
    ({'tip': 'gelir', 'miktar': 'nan', 'tarih': '2026-11-01'}, 'Gecersiz miktar'),
    ({'tip': 'gelir', 'miktar': 5, 'tarih': '04.11.2026'}, 'Gecersiz tarih'),
    ({'tip': 'gelir', 'miktar': 5, 'tarih': '2026-02-30'}, 'Gecersiz tarih'),
])
def test_dogrulama_ekle_ve_duzenle(istemci, govde, mesaj):
    _ekle(istemci, tip='gelir', miktar=100, tarih='2026-11-01')
    kid = _liste(istemci)['kayitlar'][0]['id']
    for r in (istemci.post('/api/vinc/ekle', json=govde), istemci.put('/api/vinc/%d' % kid, json=govde)):
        assert r.status_code == 400
        assert r.get_json()['error'].startswith(mesaj)
    # Hatali istek veriyi bozmadi
    l = _liste(istemci)
    assert len(l['kayitlar']) == 1 and l['kayitlar'][0]['miktar'] == 100


def test_olmayan_kaydi_duzenleme_404(istemci):
    r = istemci.put('/api/vinc/999', json={'tip': 'gelir', 'miktar': 5, 'tarih': '2026-11-01'})
    assert r.status_code == 404


def test_tarihsiz_kayit_bugune_yazilir(istemci):
    from datetime import date
    _ekle(istemci, tip='gelir', miktar=50)
    assert _liste(istemci)['kayitlar'][0]['tarih'] == date.today().isoformat()


def test_sil_sadece_o_kaydi_siler(istemci):
    _ekle(istemci, tip='gelir', miktar=100, tarih='2026-11-01')
    _ekle(istemci, tip='gelir', miktar=200, tarih='2026-11-02')
    ilk = [k for k in _liste(istemci)['kayitlar'] if k['miktar'] == 100][0]
    assert istemci.post('/api/vinc/sil', json={'id': ilk['id']}).status_code == 200
    l = _liste(istemci)
    assert [k['miktar'] for k in l['kayitlar']] == [200]
    assert l['net'] == 200


def test_vinc_sayfasi(istemci):
    r = istemci.get('/vinc')
    assert r.status_code == 200
    assert r.headers['Cache-Control'].startswith('no-store')
    html = r.get_data(as_text=True)
    for parca in ('Mobil Vinç', 'href="/"', 'Gelir Ekle', 'Gider Ekle', "modalAc('yardim')",
                  'viewport-fit=cover', 'function kaydirmaKur', "'/api/vinc/' + DUZENLENEN",
                  'type="date"', 'inputmode="decimal"'):
        assert parca in html, parca
    assert '{{' not in html and '{%' not in html  # sablon tamamen islendi


def test_ana_menude_vinc_karti_acik(istemci):
    html = istemci.get('/').get_data(as_text=True)
    assert '<a class="satir-ic" href="/vinc">' in html


@pytest.mark.skipif(shutil.which('node') is None, reason='node yok')
def test_js_fmtTL_python_para_tl_ile_ayni():
    degerler = [0, 1284500, 40625.5, 3250, -500, 999.999, 12.345, 0.5, 1500.05, -0.004, 1e9]
    betik = ortak.ORTAK_JS + '\nconsole.log(JSON.stringify(%s.map(fmtTL)));' % json.dumps(degerler)
    betik += '\nconsole.log(JSON.stringify(["1.500","1500,50","1.500,50"," ₺2.000 ","","abc"].map(parseTLInput)));'
    fd, yol = tempfile.mkstemp(suffix='.js')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(betik)
    try:
        p = subprocess.run(['node', yol], capture_output=True, text=True, encoding='utf-8')
    finally:
        os.remove(yol)
    assert p.returncode == 0, p.stderr
    satirlar = p.stdout.strip().splitlines()
    assert json.loads(satirlar[0]) == [ortak.para_tl(d) for d in degerler]
    parse = json.loads(satirlar[1])
    assert parse[:4] == [1500, 1500.5, 1500.5, 2000]
    assert parse[4] is None and parse[5] is None  # NaN -> JSON null
