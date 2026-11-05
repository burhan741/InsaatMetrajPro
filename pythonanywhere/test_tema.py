"""
"Kurumsal" tema (TASARIM_KURALLARI.md) denetimleri.

NASIL TEST EDERIZ: pytest test_tema.py
Kapsam: renk paleti birebir, renkler tek noktadan (sayfalarda sabit renk kodu
yok), Manrope + tabular-nums, 12px alti yazi yok, PWA meta (theme-color,
black-translucent), kalan renk/yazi kurali (Python = JS), tarayici confirm()
yerine kendi onay penceresi, ikon lacivert zemin.
"""
import base64
import io
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

import ortak
from test_cari import firma_ekle, hareket, kalem_id
from test_demirci import demirci_ekle

BEKLENEN_TEMA = {
    'lacivert': '#1E3A8A', 'lacivert-koyu': '#172E6E', 'lacivert-acik': '#EEF2FF', 'lacivert-cizgi': '#C7D2FE',
    'zemin': '#FFFFFF', 'zemin-2': '#F8FAFC', 'cizgi': '#E2E8F0', 'metin': '#0F172A', 'metin-soluk': '#475569',
    'ikon-soluk': '#64748B', 'alacak': '#15803D', 'borc': '#B91C1C', 'odeme': '#1E40AF', 'uyari': '#B45309',
}


def _sayfalar(c):
    fid = firma_ekle(c)
    hareket(c, fid, tip='is', tarih='2026-11-01', kalem_id=kalem_id(c, fid, 'Gro beton'), miktar=2)
    did = demirci_ekle(c)
    return ['/', '/vinc', '/muteahhit', '/muteahhit/%d' % fid, '/muteahhit/gun-sonu',
            '/demirci', '/demirci/%d' % did, '/demirci/gun-sonu']


def test_palet_birebir():
    assert ortak.TEMA == BEKLENEN_TEMA
    for ad, kod in BEKLENEN_TEMA.items():
        assert '--%s:%s;' % (ad, kod) in ortak.ORTAK_CSS
    assert 'color-scheme:light' in ortak.ORTAK_CSS


def test_sayfalarda_sabit_renk_kodu_yok(istemci):
    """Renkler sadece :root degiskenlerinde ve theme-color meta'sinda gecer."""
    for adres in _sayfalar(istemci):
        html = istemci.get(adres).get_data(as_text=True)
        govde = html.replace(ortak.ORTAK_CSS.split('\n', 1)[0], '')        # :root satiri
        govde = govde.replace('content="%s"' % ortak.TEMA['lacivert'], '')  # theme-color
        kodlar = re.findall(r'(?<![&\w])#[0-9A-Fa-f]{3,8}\b', govde)
        assert kodlar == [], (adres, kodlar[:5])


def test_yazi_tipi_ve_rakam_hizasi(istemci):
    assert 'family=Manrope:wght@500;600;700;800' in ortak.ORTAK_HEAD
    assert "--yazi:'Manrope',system-ui,-apple-system,sans-serif" in ortak.ORTAK_CSS
    assert 'font-variant-numeric:tabular-nums' in ortak.ORTAK_CSS
    for adres in _sayfalar(istemci):
        assert 'fonts.googleapis.com/css2?family=Manrope' in istemci.get(adres).get_data(as_text=True), adres


def test_hicbir_yazi_12px_alti_degil():
    import cari
    css = ortak.ORTAK_CSS + cari.CARI_CSS
    boyutlar = [float(x) for x in re.findall(r'font-size:(\d+(?:\.\d+)?)px', css)]
    assert boyutlar and min(boyutlar) >= 12, sorted(boyutlar)[:5]


def test_olculer_ve_dokunma_hedefleri():
    css = ortak.ORTAK_CSS
    assert '.btn{' in css and 'height:52px' in css.split('.btn{', 1)[1].split('}', 1)[0]      # ana buton 52px
    assert 'border-radius:18px' in css.split('.yuzen{', 1)[1].split('}', 1)[0]                 # buyuk kart
    assert '0 8px 24px rgba(15,23,42,.12)' in css                                              # tek golge
    assert 'margin-top:-44px' in css and '64px' in css.split('.bant{', 1)[1].split('}', 1)[0]  # bant/yuzen bindirme
    assert 'height:48px' in css.split('.alan input,.alan select,.girdi{', 1)[1].split('}', 1)[0]
    for sinif in ('.bant-btn{', '.secim button{', '.btn-metin{', '.cip{'):
        govde = css.split(sinif, 1)[1].split('}', 1)[0]
        assert '44px' in govde, sinif
    assert 'env(safe-area-inset-top)' in css and 'env(safe-area-inset-bottom)' in css


def test_pwa_meta(istemci):
    html = istemci.get('/').get_data(as_text=True)
    assert '<meta name="theme-color" content="#1E3A8A">' in html
    assert 'apple-mobile-web-app-status-bar-style" content="black-translucent"' in html
    assert 'apple-mobile-web-app-title" content="Şantiye Defteri"' in html
    m = json.loads(istemci.get('/manifest.webmanifest').get_data(as_text=True))
    assert m['theme_color'] == '#1E3A8A' and m['name'] == 'Şantiye Defteri'


def test_ikon_lacivert_zemin_beyaz_cizgi(istemci):
    from PIL import Image
    img = Image.open(io.BytesIO(istemci.get('/apple-touch-icon.png').data)).convert('RGB')
    assert img.size == (180, 180)
    assert img.getpixel((2, 2)) == (0x1E, 0x3A, 0x8A)
    renkler = {img.getpixel((x, y)) for x in range(0, 180, 3) for y in range(0, 180, 3)}
    assert (255, 255, 255) in renkler


@pytest.mark.parametrize('kalan, yon, sinif, etiket, tutar', [
    (325000, 'alacak', 'renk-alacak', 'alacak', '₺325.000'),
    (45000, 'borc', 'renk-borc', 'borç', '₺45.000'),
    (0, 'alacak', 'renk-soluk', 'alacak', '₺0'),
    (0, 'borc', 'renk-soluk', 'borç', '₺0'),
    (-500, 'alacak', 'renk-uyari', 'fazla ödeme', '₺500'),
    (-500, 'borc', 'renk-uyari', 'fazla ödeme', '₺500'),
])
def test_kalan_sunum(kalan, yon, sinif, etiket, tutar):
    assert ortak.kalan_sunum(kalan, yon) == {'sinif': sinif, 'etiket': etiket, 'tutar': tutar}


@pytest.mark.skipif(shutil.which('node') is None, reason='node yok')
def test_js_kalanSunum_python_ile_ayni():
    girdiler = [(325000, 'alacak'), (45000, 'borc'), (0, 'alacak'), (-500, 'borc'), (1500.5, 'alacak')]
    betik = ortak.ORTAK_JS + '\nconsole.log(JSON.stringify(%s.map(function(g){return kalanSunum(g[0], g[1]);})));' \
        % json.dumps(girdiler)
    fd, yol = tempfile.mkstemp(suffix='.js')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(betik)
    try:
        p = subprocess.run(['node', yol], capture_output=True, text=True, encoding='utf-8')
    finally:
        os.remove(yol)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout) == [ortak.kalan_sunum(k, y) for k, y in girdiler]


def test_tarayici_confirm_yerine_onay_penceresi(istemci):
    sayfalar = _sayfalar(istemci)
    for adres in sayfalar:
        html = istemci.get(adres).get_data(as_text=True)
        assert 'confirm(' not in html, adres
    for adres in ('/vinc', '/muteahhit', sayfalar[6]):          # vinc, firma listesi, demirci firma sayfasi
        r = istemci.get(adres)
        assert r.status_code == 200, adres
        assert "onayIste('Silinsin mi?'" in r.get_data(as_text=True), adres
    assert "'Vazgeç'" in ortak.ORTAK_JS or '>Vazgeç<' in ortak.ORTAK_JS
    assert 'btn btn-tehlike' in ortak.ORTAK_JS


def test_her_sayfada_bant_ve_ikonlar(istemci):
    for adres in _sayfalar(istemci):
        html = istemci.get(adres).get_data(as_text=True)
        assert '<header class="bant' in html, adres
        assert 'stroke-width="1.9"' in html or 'IKON' in html, adres
    ana = istemci.get('/').get_data(as_text=True)
    for ikon in ('bina', 'izgara', 'liste', 'vinc'):
        assert ortak.IKONLAR[ikon] in ana, ikon


def test_pdf_renk_yardimcisi():
    import cari
    from reportlab.lib import colors
    renk = cari._pdf_renk(colors)
    assert renk['lacivert'].hexval().upper() == '0X1E3A8A'
    assert cari._pdf_kalan_rengi(renk, 10, 'alacak') == renk['alacak']
    assert cari._pdf_kalan_rengi(renk, 10, 'borc') == renk['borc']
    assert cari._pdf_kalan_rengi(renk, -1, 'borc') == renk['uyari']
    assert cari._pdf_kalan_rengi(renk, 0, 'alacak') == renk['metin-soluk']
