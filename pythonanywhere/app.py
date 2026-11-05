"""
app.py - Santiye ana programi (PythonAnywhere giris noktasi).

NEYI COZUYORUZ: Puantaj, Mobil Vinc, Muteahhitler ve Demirciler tek bir
programda, tek veritabaninda (puantaj.db) toplanir. Bu dosya sadece Flask
uygulamasini kurar, modulleri (Blueprint) kaydeder, tablolari hazirlar ve
ana menuyu (/) gosterir. Is mantigi modullerdedir:
    ortak.py   - veritabani yolu, gunluk yedek, bicimleme, TEMA (renk/CSS/ikon), PDF yardimcilari
    puantaj.py - mevcut puantaj (aynen; adres /puantaj)
    vinc.py    - mobil vinc defteri (/vinc)
    cari.py    - muteahhit / demirci cari hesap (/muteahhit, /demirci)

PythonAnywhere WSGI dosyasi degismez: `from app import app`.

NASIL TEST EDERIZ: test_ortak_ana_menu.py + test_tema.py - ana menunun 4
satiri ve toplam alacak/borc karti; test_puantaj_regresyon.py - puantaj
endpoint'lerinin eski app.py ile birebir ayni cevap verdigi.
"""

import base64
import json

from flask import Flask, Response, make_response, render_template_string

import cari
import ortak
import puantaj
import vinc

app = Flask(__name__)
app.register_blueprint(puantaj.bp)
app.register_blueprint(vinc.bp)
app.register_blueprint(cari.bp)

# Tablolari olustur (CREATE TABLE IF NOT EXISTS - mevcut veriye dokunmaz),
# sonra gunde bir otomatik yedek al (eski davranisin aynisi).
INIT_FONKSIYONLARI = [puantaj.init_db, vinc.init_db, cari.init_db]
ortak.veritabani_hazirla(INIT_FONKSIYONLARI)


# ====================================================================
# ANA MENU
# ====================================================================
def ana_menu_verisi():
    """Ana menudeki toplamlar ve 4 bolum satiri (veri; HTML'den ayri)."""
    conn = ortak.baglan()
    try:
        vinc_net = vinc.vinc_ozet(conn)['net']
        alacak = cari.tur_toplam_kalan(conn, 'muteahhit')
        borc = cari.tur_toplam_kalan(conn, 'demirci')
        m_adet = cari.firma_sayisi(conn, 'muteahhit')
        d_adet = cari.firma_sayisi(conn, 'demirci')
        rapor_basligi = cari.ayar_oku(conn, 'rapor_basligi')
    finally:
        conn.close()

    def adet(n):
        return '%d firma' % n if n else 'Henüz firma yok'

    net_metin = ('Net kâr ' if vinc_net >= 0 else 'Net zarar ') + ortak.para_tl(abs(vinc_net))
    return {
        'alacak': ortak.kalan_sunum(alacak, 'alacak'),
        'borc': ortak.kalan_sunum(borc, 'borc'),
        'rapor_basligi': rapor_basligi,
        'satirlar': [
            {'baslik': 'Müteahhitler', 'ikon': 'bina', 'adres': '/muteahhit',
             'alt': adet(m_adet) + ' · beton hakedişi ve tahsilat'},
            {'baslik': 'Demirciler', 'ikon': 'izgara', 'adres': '/demirci',
             'alt': adet(d_adet) + ' · demir işi ve ödemeler'},
            {'baslik': 'Puantaj', 'ikon': 'liste', 'adres': '/puantaj',
             'alt': 'İşçi yoklama, ödeme, bordro'},
            {'baslik': 'Mobil Vinç', 'ikon': 'vinc', 'adres': '/vinc', 'alt': net_metin},
        ],
    }


def tarih_metni():
    """Sunucu tarafi yedek metin; sayfada JS telefon saatine gore yeniler."""
    s = ortak.simdi_tr()
    ay = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül',
          'Ekim', 'Kasım', 'Aralık'][s.month - 1]
    return '%d %s %d' % (s.day, ay, s.year)


ANA_MENU_HTML = r'''<!DOCTYPE html>
<html lang="tr">
<head>
{{ ortak_head|safe }}
<title>Şantiye Defteri</title>
<style>{{ ortak_css|safe }}</style>
</head>
<body>
<header class="bant">
  <div class="bant-ust">
    <span class="bant-soluk" id="selam">{{ tarih }}</span>
    <div class="bant-btnlar">
      <button class="bant-btn yuvarlak" onclick="modalAc('ayarlar')" aria-label="Ayarlar" title="Ayarlar: rapor başlığı ve yedek">{{ ikon.ayar|safe }}</button>
      <button class="bant-btn yuvarlak" onclick="modalAc('yardim')" aria-label="Yardım" title="Yardım">?</button>
    </div>
  </div>
  <h1>Şantiye Defteri</h1>
</header>

<main class="icerik">
  <div class="yuzen">
    <div class="ozet2">
      <div title="Tüm müteahhitlerin kalanı: size ödenecek para">
        <div class="ozet-e">Toplam alacak</div>
        <div class="ozet-d {{ v.alacak.sinif }}">{{ v.alacak.tutar }}</div>
        <div class="ozet-not {{ v.alacak.sinif }}">{{ v.alacak.etiket }}</div>
      </div>
      <div title="Tüm demircilerin kalanı: sizin ödeyeceğiniz para">
        <div class="ozet-e">Toplam borç</div>
        <div class="ozet-d {{ v.borc.sinif }}">{{ v.borc.tutar }}</div>
        <div class="ozet-not {{ v.borc.sinif }}">{{ v.borc.etiket }}</div>
      </div>
    </div>
  </div>

  <nav class="bolum" aria-label="Bölümler">
    {% for s in v.satirlar %}
    <div class="satir"><a class="satir-ic" href="{{ s.adres }}">
      <span class="ikon-daire">{{ ikon[s.ikon]|safe }}</span>
      <span class="satir-orta"><span class="satir-baslik">{{ s.baslik }}</span><span class="satir-alt">{{ s.alt }}</span></span>
      <span class="satir-sag ok">{{ ikon.ok|safe }}</span>
    </a></div>
    {% endfor %}
  </nav>
</main>

<div class="panel" id="yardim" role="dialog" aria-modal="true" aria-labelledby="yardim-b">
  <header class="bant kisa">
    <div class="bant-ust"><button class="bant-geri" onclick="modalKapat('yardim')">{{ ikon.geri|safe }}Kapat</button></div>
    <h1 id="yardim-b">Nasıl kullanılır?</h1>
  </header>
  <div class="icerik yardim">
    <ol>
      <li><b>Müteahhitler:</b> Döktüğünüz beton ve giderler hakedişe yazılır, aldığınız para düşülür. Kalan = <b>alacağınız</b> (yeşil).</li>
      <li><b>Demirciler:</b> Demircinin yaptığı iş ve giderler hakedişe yazılır, ödediğiniz para düşülür. Kalan = <b>borcunuz</b> (kırmızı).</li>
      <li><b>Puantaj:</b> İşçi yoklaması, ödemeler ve bordro. Önceki uygulamanın aynısıdır.</li>
      <li><b>Mobil Vinç:</b> Vinç gelir ve giderleri, net kâr/zarar.</li>
    </ol>
    <p>Üstteki kart tüm firmaların toplamıdır. Eksiye düşen bir toplam turuncu renkte <b>fazla ödeme</b> olarak yazar.</p>
    <p>Her ekranda sol üstteki <b>‹</b> geri götürür, sağ üstteki <b>?</b> o ekranın kılavuzunu açar.</p>
    <p><b>Ayarlar</b> (sağ üstteki düğme): gün sonu PDF'inin başlığına yazılacak firmanızın adı ve tüm verilerin yedeği.</p>
    <p>Telefonda uygulama gibi açmak için Safari'de <b>Paylaş → Ana Ekrana Ekle</b>'ye dokunun.</p>
    <button class="btn" onclick="modalKapat('yardim')">Anladım</button>
  </div>
</div>

<div class="panel" id="ayarlar" role="dialog" aria-modal="true" aria-labelledby="ayar-b">
  <header class="bant kisa">
    <div class="bant-ust"><button class="bant-geri" onclick="modalKapat('ayarlar')">Vazgeç</button></div>
    <h1 id="ayar-b">Ayarlar</h1>
  </header>
  <div class="icerik">
    <div class="alan">
      <label for="a-baslik">Rapor başlığı (firmanızın adı)</label>
      <input type="text" id="a-baslik" maxlength="120" autocomplete="off" value="{{ v.rapor_basligi }}">
    </div>
    <div class="bilgi">Gün sonu PDF raporunun en üstünde yazar.</div>
    <button class="btn" id="a-kaydet" onclick="ayarKaydet()">Kaydet</button>
    <div class="bolum">
      <div class="bolum-baslik">Yedek</div>
      <p class="bilgi" style="margin-top:6px">Müteahhit, demirci, vinç ve puantajın tamamı tek dosyada (.db) indirilir. Sunucu ayrıca her gün kendiliğinden yedek alır (son 14 gün).</p>
      <button class="btn btn-ikincil" onclick="window.open('/api/yedek/indir')">Tüm Verileri İndir</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>{{ ortak_js|safe }}</script>
<script>
(function selamYaz() {
  var d = new Date(), s = d.getHours();
  var selam = s < 12 ? 'Günaydın' : (s < 18 ? 'İyi günler' : 'İyi akşamlar');
  el('selam').textContent = selam + ' · ' + d.getDate() + ' ' + AY_ADLARI[d.getMonth()] + ' ' + d.getFullYear();
})();
function ayarKaydet() {
  var deger = el('a-baslik').value.trim();
  if (!deger) { toast('Firma adını yazın'); return; }
  jsonGonder('/api/cari/ayar', 'POST', {rapor_basligi: deger})
    .then(function() { modalKapat('ayarlar'); toast('Kaydedildi'); })
    .catch(function(e) { toast('Kaydedilemedi: ' + e.message); });
}
</script>
</body>
</html>'''


@app.route('/')
def ana_menu():
    ikonlar = {ad: ortak.svg(ad) for ad in ortak.IKONLAR}
    # Ozet tutarlari her acilista guncel olsun (iOS ana ekran onbellegi).
    return ortak.onbelleksiz(make_response(render_template_string(
        ANA_MENU_HTML, v=ana_menu_verisi(), tarih=tarih_metni(), ikon=ikonlar,
        ortak_head=ortak.ORTAK_HEAD, ortak_css=ortak.ORTAK_CSS, ortak_js=ortak.ORTAK_JS)))


# ====================================================================
# PWA: ana ekran ikonu + manifest
# iOS, sayfada <link> olmasa da kokteki /apple-touch-icon.png'yi arar;
# boylece degismeyen puantaj sayfasindan eklenince de ikon gelir.
# ====================================================================
def _png(b64):
    resp = Response(base64.b64decode(b64), mimetype='image/png')
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@app.route('/apple-touch-icon.png')
@app.route('/apple-touch-icon-precomposed.png')
def ikon_180():
    return _png(ortak.IKON_180_B64)


@app.route('/ikon-512.png')
def ikon_512():
    return _png(ortak.IKON_512_B64)


@app.route('/manifest.webmanifest')
def manifest():
    veri = {
        'name': 'Şantiye Defteri',
        'short_name': 'Şantiye Defteri',
        'lang': 'tr',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'background_color': ortak.TEMA['zemin'],
        'theme_color': ortak.TEMA['lacivert'],
        'icons': [
            {'src': '/apple-touch-icon.png', 'sizes': '180x180', 'type': 'image/png'},
            {'src': '/ikon-512.png', 'sizes': '512x512', 'type': 'image/png'},
        ],
    }
    return Response(json.dumps(veri, ensure_ascii=False), mimetype='application/manifest+json')


if __name__ == '__main__':
    app.run(debug=True)
