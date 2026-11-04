"""
app.py - Santiye ana programi (PythonAnywhere giris noktasi).

NEYI COZUYORUZ: Puantaj, Mobil Vinc, Muteahhitler ve Demirciler tek bir
programda, tek veritabaninda (puantaj.db) toplanir. Bu dosya sadece Flask
uygulamasini kurar, modulleri (Blueprint) kaydeder, tablolari hazirlar ve
ana menuyu (/) gosterir. Is mantigi modullerdedir:
    ortak.py   - veritabani yolu, gunluk yedek, bicimleme, PDF yardimcilari
    puantaj.py - mevcut puantaj (aynen; adres /puantaj)
    vinc.py    - mobil vinc defteri (/vinc)
    cari.py    - muteahhit / demirci cari hesap (/muteahhit, /demirci)

PythonAnywhere WSGI dosyasi degismez: `from app import app`.

NASIL TEST EDERIZ: test_ana_menu.py - / ana menunun 4 karti gosterdigi,
vinc net tutarinin dogru bicimlendigi; test_puantaj_regresyon.py -
puantaj endpoint'lerinin eski app.py ile birebir ayni cevap verdigi.
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
# Kartlar veri olarak tutulur: sonraki adimlarda bir modul hazir oldugunda
# sadece 'aktif' ve 'ozet' doldurulur, HTML'e dokunulmaz.
def ana_menu_kartlari():
    conn = ortak.baglan()
    vinc_net = vinc.vinc_ozet(conn)['net']
    alacak = cari.tur_toplam_kalan(conn, 'muteahhit')
    borc = cari.tur_toplam_kalan(conn, 'demirci')
    conn.close()
    return [
        {'baslik': 'Müteahhitler', 'ikon': '&#x1F3E2;', 'adres': '/muteahhit',
         'aktif': True, 'ozet_etiket': 'Toplam alacak', 'ozet': ortak.para_tl(alacak),
         'renk': 'yesil' if alacak >= 0 else 'kirmizi', 'not': ''},
        {'baslik': 'Demirciler', 'ikon': '&#x1F529;', 'adres': '/demirci',
         'aktif': True, 'ozet_etiket': 'Toplam borç', 'ozet': ortak.para_tl(borc),
         # Borc odenecek para -> kirmizi; eksi (fazla odeme, demirci bana borclu) -> yesil
         'renk': 'kirmizi' if borc > 0 else ('yesil' if borc < 0 else ''), 'not': ''},
        {'baslik': 'Puantaj', 'ikon': '&#x1F477;', 'adres': '/puantaj',
         'aktif': True, 'ozet_etiket': 'İşçi yoklama, ödeme, bordro', 'ozet': '',
         'renk': '', 'not': ''},
        {'baslik': 'Mobil Vinç', 'ikon': '&#x1F3D7;', 'adres': '/vinc',
         'aktif': True, 'ozet_etiket': 'Net', 'ozet': ortak.para_tl(vinc_net),
         'renk': 'yesil' if vinc_net >= 0 else 'kirmizi', 'not': ''},
    ]


ANA_MENU_HTML = r'''<!DOCTYPE html>
<html lang="tr">
<head>
{{ ortak_head|safe }}
<title>Şantiye Defteri</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#f4f5f7;--kart:#ffffff;--tx:#14161a;--soluk:#6b7280;--cizgi:#e5e7eb;--yesil:#0f8a4b;--kirmizi:#c62828;--vurgu:#14161a}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;background:var(--bg);color:var(--tx);min-height:100vh;
  padding:calc(16px + env(safe-area-inset-top)) calc(16px + env(safe-area-inset-right)) calc(24px + env(safe-area-inset-bottom)) calc(16px + env(safe-area-inset-left))}
.ust{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}
.ust h1{font-size:24px;font-weight:700;letter-spacing:-.3px}
.ust .alt{font-size:13px;color:var(--soluk);margin-top:2px}
.yardim-btn{width:36px;height:36px;border-radius:50%;border:1px solid var(--cizgi);background:var(--kart);color:var(--tx);font-size:17px;font-weight:700;cursor:pointer}
.kartlar{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.kart{display:flex;flex-direction:column;justify-content:space-between;min-height:150px;background:var(--kart);border:1px solid var(--cizgi);border-radius:16px;
  padding:16px;color:var(--tx);text-decoration:none;-webkit-tap-highlight-color:transparent}
.kart:active{transform:scale(.98)}
.kart .ikon{font-size:30px;line-height:1}
.kart .ad{font-size:17px;font-weight:700;margin-top:10px}
.kart .etiket{font-size:12px;color:var(--soluk);margin-top:6px}
.kart .tutar{font-size:18px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums}
.kart .tutar.yesil{color:var(--yesil)}
.kart .tutar.kirmizi{color:var(--kirmizi)}
.kart.pasif{opacity:.55;pointer-events:none}
.kart .rozet{display:inline-block;margin-top:8px;font-size:11px;font-weight:600;color:var(--soluk);background:var(--bg);border-radius:6px;padding:2px 8px;align-self:flex-start}
.modal-arka{position:fixed;inset:0;background:#00000066;display:flex;align-items:flex-end;z-index:10}
.modal-arka.gizli{display:none}
.modal{background:var(--kart);color:var(--tx);width:100%;max-height:85vh;overflow-y:auto;border-radius:18px 18px 0 0;padding:20px 18px calc(24px + env(safe-area-inset-bottom))}
.modal h2{font-size:18px;margin-bottom:12px}
.modal p,.modal li{font-size:14px;line-height:1.5;color:#374151}
.modal ol{padding-left:20px;margin:8px 0}
.modal button{width:100%;margin-top:14px;padding:12px;border:none;border-radius:10px;background:var(--vurgu);color:#fff;font-size:15px;font-weight:600}
.ust-btnlar{display:flex;gap:8px;align-items:center}
.hap-btn{height:36px;padding:0 14px;border-radius:18px;border:1px solid var(--cizgi);background:var(--kart);color:var(--tx);font-size:14px;font-weight:600;cursor:pointer}
.alan{margin:4px 0 4px}
.alan label{display:block;font-size:12px;color:var(--soluk);margin-bottom:4px}
.alan input{width:100%;padding:12px;border:1px solid var(--cizgi);border-radius:10px;background:#fff;color:var(--tx);font-size:16px;-webkit-appearance:none;appearance:none}
.modal .ipucu{font-size:12px;color:var(--soluk);margin-top:6px}
.toast{position:fixed;left:50%;bottom:calc(28px + env(safe-area-inset-bottom));transform:translateX(-50%);background:#14161a;color:#fff;padding:10px 18px;border-radius:10px;font-size:14px;opacity:0;transition:opacity .25s;pointer-events:none;z-index:20;white-space:nowrap}
.toast.goster{opacity:1}
</style>
</head>
<body>
<div class="ust">
  <div>
    <h1>Şantiye Defteri</h1>
    <div class="alt">Bir bölüm seçin</div>
  </div>
  <div class="ust-btnlar">
    <button class="hap-btn" onclick="ayarAc()" title="Rapor başlığı (firmanızın adı)">Ayarlar</button>
    <button class="yardim-btn" onclick="yardimAc()" aria-label="Yardım" title="Yardım">?</button>
  </div>
</div>

<div class="kartlar">
{% for k in kartlar %}
  <a class="kart{% if not k.aktif %} pasif{% endif %}" href="{{ k.adres }}">
    <div>
      <div class="ikon">{{ k.ikon|safe }}</div>
      <div class="ad">{{ k.baslik }}</div>
    </div>
    <div>
      <div class="etiket">{{ k.ozet_etiket }}</div>
      {% if k.ozet %}<div class="tutar {{ k.renk }}">{{ k.ozet }}</div>{% endif %}
      {% if k.not %}<span class="rozet">{{ k.not }}</span>{% endif %}
    </div>
  </a>
{% endfor %}
</div>

<div class="modal-arka gizli" id="yardim" onclick="yardimKapat(event)">
  <div class="modal">
    <h2>Nasıl kullanılır?</h2>
    <ol>
      <li><b>Müteahhitler:</b> Döktüğünüz beton ve giderler hakedişe yazılır, aldığınız para düşülür. Kalan = alacağınız.</li>
      <li><b>Demirciler:</b> Demircinin yaptığı iş ve giderler hakedişe yazılır, ödediğiniz para düşülür. Kalan = borcunuz.</li>
      <li><b>Puantaj:</b> İşçi yoklaması, ödemeler ve bordro. Önceki uygulamanın aynısıdır.</li>
      <li><b>Mobil Vinç:</b> Vinç gelir ve giderleri, net kâr/zarar.</li>
    </ol>
    <p>Kartlardaki tutarlar o bölümün güncel toplamıdır: Müteahhitlerde alacağınız, Demircilerde borcunuz, Vinçte net kâr/zarar.</p>
    <p>Her ekranın üstündeki <b>‹ Ana Menü</b> bağlantısı buraya döner. Her ekranda sağ üstteki <b>?</b> o ekranın kılavuzunu açar.</p>
    <p><b>Ayarlar:</b> Gün sonu PDF raporunun başlığına yazılacak firmanızın adı.</p>
    <p>Telefonda uygulama gibi açmak için Safari'de <b>Paylaş → Ana Ekrana Ekle</b>'ye dokunun.</p>
    <button onclick="yardimKapat()">Anladım</button>
  </div>
</div>

<div class="modal-arka gizli" id="ayarlar" onclick="ayarKapat(event)">
  <div class="modal">
    <h2>Ayarlar</h2>
    <div class="alan">
      <label for="a-baslik">Rapor başlığı (firmanızın adı)</label>
      <input type="text" id="a-baslik" maxlength="120" autocomplete="off" value="{{ rapor_basligi }}">
    </div>
    <div class="ipucu">Gün sonu PDF raporunun en üstünde yazar.</div>
    <button id="a-kaydet" onclick="ayarKaydet()">Kaydet</button>
    <h2 style="margin-top:22px">Yedek</h2>
    <div class="ipucu">Müteahhit, demirci, vinç ve puantajın tamamı tek dosyada (.db) indirilir. Sunucu ayrıca her gün kendiliğinden yedek alır (son 14 gün).</div>
    <button style="background:#fff;color:var(--tx);border:1px solid var(--cizgi)" onclick="window.open('/api/yedek/indir')">Tüm Verileri İndir</button>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
function yardimAc() { document.getElementById('yardim').className = 'modal-arka'; }
function yardimKapat(e) {
  if (e && e.target !== document.getElementById('yardim')) return;
  document.getElementById('yardim').className = 'modal-arka gizli';
}
function ayarAc() { document.getElementById('ayarlar').className = 'modal-arka'; }
function ayarKapat(e) {
  if (e && e.target !== document.getElementById('ayarlar')) return;
  document.getElementById('ayarlar').className = 'modal-arka gizli';
}
function toast(m) {
  var el = document.getElementById('toast');
  el.textContent = m;
  el.className = 'toast goster';
  clearTimeout(el._t);
  el._t = setTimeout(function() { el.className = 'toast'; }, 2200);
}
function ayarKaydet() {
  var deger = document.getElementById('a-baslik').value.trim();
  if (!deger) { toast('Firma adını yazın'); return; }
  fetch('/api/cari/ayar', {method: 'POST', headers: {'Content-Type': 'application/json'},
                           body: JSON.stringify({rapor_basligi: deger})})
    .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); ayarKapat(); toast('Kaydedildi'); })
    .catch(function(e) { toast('Kaydedilemedi: ' + e.message); });
}
</script>
</body>
</html>'''


@app.route('/')
def ana_menu():
    conn = ortak.baglan()
    try:
        rapor_basligi = cari.ayar_oku(conn, 'rapor_basligi')
    finally:
        conn.close()
    # Ozet tutarlari her acilista guncel olsun (iOS ana ekran onbellegi).
    return ortak.onbelleksiz(make_response(render_template_string(
        ANA_MENU_HTML, kartlar=ana_menu_kartlari(), ortak_head=ortak.ORTAK_HEAD,
        rapor_basligi=rapor_basligi)))


# ====================================================================
# PWA: ana ekran ikonu + manifest
# iOS, sayfada <link> olmasa da kokteki /apple-touch-icon.png'yi arar;
# boylece degismeyen puantaj sayfasindan eklenince de ikon gelir.
# ====================================================================
def _png(b64):
    resp = Response(base64.b64decode(b64), mimetype='image/png')
    resp.headers['Cache-Control'] = 'public, max-age=604800'
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
        'short_name': 'Şantiye',
        'lang': 'tr',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'background_color': '#f4f5f7',
        'theme_color': '#f4f5f7',
        'icons': [
            {'src': '/apple-touch-icon.png', 'sizes': '180x180', 'type': 'image/png'},
            {'src': '/ikon-512.png', 'sizes': '512x512', 'type': 'image/png'},
        ],
    }
    return Response(json.dumps(veri, ensure_ascii=False), mimetype='application/manifest+json')


if __name__ == '__main__':
    app.run(debug=True)
