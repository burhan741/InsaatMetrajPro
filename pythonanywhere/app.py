"""
app.py - Santiye ana programi (PythonAnywhere giris noktasi).

NEYI COZUYORUZ: Puantaj, Mobil Vinc, Muteahhitler ve Demirciler tek bir
programda, tek veritabaninda (puantaj.db) toplanir. Bu dosya sadece Flask
uygulamasini kurar, modulleri (Blueprint) kaydeder, tablolari hazirlar ve
ana menuyu (/) gosterir. Is mantigi modullerdedir:
    ortak.py   - veritabani yolu, gunluk yedek, bicimleme, PDF yardimcilari
    puantaj.py - mevcut puantaj (aynen; adres /puantaj)
    vinc.py    - mobil vinc defteri (/vinc)

PythonAnywhere WSGI dosyasi degismez: `from app import app`.

NASIL TEST EDERIZ: test_ana_menu.py - / ana menunun 4 karti gosterdigi,
vinc net tutarinin dogru bicimlendigi; test_puantaj_regresyon.py -
puantaj endpoint'lerinin eski app.py ile birebir ayni cevap verdigi.
"""

from flask import Flask, make_response, render_template_string

import ortak
import puantaj
import vinc

app = Flask(__name__)
app.register_blueprint(puantaj.bp)
app.register_blueprint(vinc.bp)

# Tablolari olustur (CREATE TABLE IF NOT EXISTS - mevcut veriye dokunmaz),
# sonra gunde bir otomatik yedek al (eski davranisin aynisi).
INIT_FONKSIYONLARI = [puantaj.init_db, vinc.init_db]
ortak.veritabani_hazirla(INIT_FONKSIYONLARI)


# ====================================================================
# ANA MENU
# ====================================================================
# Kartlar veri olarak tutulur: sonraki adimlarda bir modul hazir oldugunda
# sadece 'aktif' ve 'ozet' doldurulur, HTML'e dokunulmaz.
def ana_menu_kartlari():
    conn = ortak.baglan()
    vinc_net = vinc.vinc_ozet(conn)['net']
    conn.close()
    return [
        {'baslik': 'Müteahhitler', 'ikon': '&#x1F3E2;', 'adres': '/muteahhit',
         'aktif': False, 'ozet_etiket': 'Toplam alacak', 'ozet': '',
         'renk': 'yesil', 'not': 'Hazırlanıyor'},
        {'baslik': 'Demirciler', 'ikon': '&#x1F529;', 'adres': '/demirci',
         'aktif': False, 'ozet_etiket': 'Toplam borç', 'ozet': '',
         'renk': 'kirmizi', 'not': 'Hazırlanıyor'},
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
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Şantiye">
<meta name="theme-color" content="#f4f5f7">
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
</style>
</head>
<body>
<div class="ust">
  <div>
    <h1>Şantiye Defteri</h1>
    <div class="alt">Bir bölüm seçin</div>
  </div>
  <button class="yardim-btn" onclick="yardimAc()" aria-label="Yardım">?</button>
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
    <p>Her ekranın üstündeki <b>‹ Ana Menü</b> bağlantısı buraya döner.</p>
    <p>Telefonda uygulama gibi açmak için Safari'de <b>Paylaş → Ana Ekrana Ekle</b>'ye dokunun.</p>
    <button onclick="yardimKapat()">Anladım</button>
  </div>
</div>

<script>
function yardimAc() { document.getElementById('yardim').className = 'modal-arka'; }
function yardimKapat(e) {
  if (e && e.target !== document.getElementById('yardim')) return;
  document.getElementById('yardim').className = 'modal-arka gizli';
}
</script>
</body>
</html>'''


@app.route('/')
def ana_menu():
    # Ozet tutarlari her acilista guncel olsun (iOS ana ekran onbellegi).
    return ortak.onbelleksiz(make_response(
        render_template_string(ANA_MENU_HTML, kartlar=ana_menu_kartlari())))


if __name__ == '__main__':
    app.run(debug=True)
