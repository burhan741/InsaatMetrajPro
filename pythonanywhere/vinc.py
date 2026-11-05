"""
vinc.py - Mobil Vinc gelir-gider defteri (Blueprint).

NEYI COZUYORUZ: Mobil vinc isi, isci/puantaj/hakedis hesaplarindan
BAGIMSIZ kendi gelir-gider defteri. Eskiden puantaj sayfasinda bir sekmeydi;
ana programda ayri bir kart oldu (/vinc). vinc_defter tablosu disinda hicbir
tabloya dokunmaz. Tablo ve veri AYNEN korunur (tasima gerekmez).
Eski davranis (ekle / liste / sil) korunur; DUZENLEME eklendi (2. adim).

NASIL TEST EDERIZ: test_ortak_ana_menu.py (eski app.py ile ayni liste/toplam)
+ test_vinc.py (duzenleme, dogrulama, sayfa, toplamlar).
"""

from datetime import date

from flask import Blueprint, jsonify, make_response, render_template_string, request

import ortak

bp = Blueprint('vinc', __name__)


def init_db():
    conn = ortak.baglan()
    # Eski app.py'deki tanimin aynisi (CREATE TABLE IF NOT EXISTS: mevcut
    # tabloya ve verisine dokunmaz).
    conn.execute('''CREATE TABLE IF NOT EXISTS vinc_defter (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarih DATE DEFAULT CURRENT_DATE,
        tip TEXT NOT NULL,
        aciklama TEXT,
        miktar REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()


def vinc_ozet(conn):
    """Toplam gelir / gider / net. Liste, sayfa ve ana menu ayni fonksiyonu kullanir."""
    row = conn.execute('''SELECT
        COALESCE(SUM(CASE WHEN tip='gelir' THEN miktar END), 0) AS gelir,
        COALESCE(SUM(CASE WHEN tip='gider' THEN miktar END), 0) AS gider
        FROM vinc_defter''').fetchone()
    gelir = row[0] or 0
    gider = row[1] or 0
    return {
        'toplam_gelir': round(gelir, 2),
        'toplam_gider': round(gider, 2),
        'net': round(gelir - gider, 2),
    }


def _kayit_dogrula(d):
    """Ekle ve duzenle icin ortak dogrulama. (hata_mesaji, temiz_veri) doner."""
    tip = d.get('tip')
    if tip not in ('gelir', 'gider'):
        return 'Gecersiz tip', None
    miktar = ortak.tutar_oku(d.get('miktar', 0))
    if miktar is None:
        return 'Gecersiz miktar', None
    tarih = d.get('tarih') or date.today().isoformat()
    if not ortak.iso_tarih_mi(tarih):
        return 'Gecersiz tarih (YYYY-AA-GG olmali)', None
    aciklama = (d.get('aciklama') or '').strip()
    return None, {'tip': tip, 'miktar': miktar, 'tarih': tarih, 'aciklama': aciklama}


@bp.route('/api/vinc/ekle', methods=['POST'])
def api_vinc_ekle():
    hata, v = _kayit_dogrula(request.json or {})
    if hata:
        return jsonify({'error': hata}), 400
    conn = ortak.baglan()
    conn.execute('INSERT INTO vinc_defter (tarih, tip, aciklama, miktar) VALUES (?,?,?,?)',
                 (v['tarih'], v['tip'], v['aciklama'], v['miktar']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@bp.route('/api/vinc/<int:kayit_id>', methods=['PUT'])
def api_vinc_guncelle(kayit_id):
    """Yeni (2. adim): bir kaydin turunu, tarihini, aciklamasini, tutarini degistirir."""
    hata, v = _kayit_dogrula(request.json or {})
    if hata:
        return jsonify({'error': hata}), 400
    conn = ortak.baglan()
    cur = conn.execute('UPDATE vinc_defter SET tarih=?, tip=?, aciklama=?, miktar=? WHERE id=?',
                       (v['tarih'], v['tip'], v['aciklama'], v['miktar'], kayit_id))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({'error': 'Kayit bulunamadi'}), 404
    return jsonify({'success': True})


@bp.route('/api/vinc/liste')
def api_vinc_liste():
    conn = ortak.baglan()
    rows = [dict(r) for r in conn.execute(
        'SELECT * FROM vinc_defter ORDER BY tarih DESC, id DESC').fetchall()]
    ozet = vinc_ozet(conn)
    conn.close()
    ozet['kayitlar'] = rows
    return jsonify(ozet)


@bp.route('/api/vinc/sil', methods=['POST'])
def api_vinc_sil():
    d = request.json or {}
    vinc_id = d.get('id')
    if not vinc_id:
        return jsonify({'error': 'id gerekli'}), 400
    conn = ortak.baglan()
    conn.execute('DELETE FROM vinc_defter WHERE id=?', (vinc_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ====================================================================
# SAYFA (/vinc) — Kurumsal tema (TASARIM_KURALLARI.md)
# ====================================================================
VINC_HTML = r'''<!DOCTYPE html>
<html lang="tr">
<head>
{{ ortak_head|safe }}
<title>Mobil Vinç</title>
<style>{{ ortak_css|safe }}</style>
</head>
<body>
<header class="bant">
  <div class="bant-ust">
    <a href="/" class="bant-geri">{{ ikon.geri|safe }}Ana Menü</a>
    <div class="bant-btnlar">
      <button class="bant-btn yuvarlak" onclick="modalAc('yardim')" aria-label="Yardım" title="Yardım">?</button>
    </div>
  </div>
  <h1>Mobil Vinç</h1>
</header>

<main class="icerik">
  <div class="yuzen">
    <div class="ozet2">
      <div title="Tüm zamanların toplam geliri"><div class="ozet-e">Gelir</div><div class="ozet-d renk-alacak" id="o-gelir">-</div></div>
      <div title="Tüm zamanların toplam gideri"><div class="ozet-e">Gider</div><div class="ozet-d renk-borc" id="o-gider">-</div></div>
    </div>
    <div class="ozet-tam" title="Gelir eksi gider">
      <div class="ozet-e">Net</div>
      <div><div class="ozet-d" id="o-net">-</div><div class="ozet-not" id="o-net-not"></div></div>
    </div>
  </div>

  <div class="bolum btn-satir">
    <button class="btn" onclick="yeniKayit('gelir')">{{ ikon.arti|safe }}Gelir Ekle</button>
    <button class="btn btn-ikincil" onclick="yeniKayit('gider')">{{ ikon.arti|safe }}Gider Ekle</button>
  </div>

  <div id="liste"><div class="bos">Yükleniyor…</div></div>
  <div class="ipucu" id="ipucu" style="display:none">Düzeltmek için kayda dokunun · Düzenle / Sil için sola kaydırın</div>
</main>

<!-- Kayit formu -->
<div class="panel" id="form" role="dialog" aria-modal="true" aria-labelledby="f-baslik">
  <header class="bant kisa">
    <div class="bant-ust"><button class="bant-geri" onclick="modalKapat('form')">Vazgeç</button></div>
    <h1 id="f-baslik">Kayıt</h1>
  </header>
  <div class="icerik">
    <div class="secim">
      <button id="f-tip-gelir" onclick="tipSec('gelir')">Gelir</button>
      <button id="f-tip-gider" onclick="tipSec('gider')">Gider</button>
    </div>
    <div class="alan"><label for="f-tarih">Tarih</label><input type="date" id="f-tarih"></div>
    <div class="alan"><label for="f-acik">Açıklama</label><input type="text" id="f-acik" autocomplete="off"></div>
    <div class="alan"><label for="f-tutar">Tutar (₺)</label><input type="text" id="f-tutar" inputmode="decimal" placeholder="0" autocomplete="off"></div>
    <div class="bilgi">Tutarı 1.500 ya da 1500,50 gibi yazabilirsiniz.</div>
    <button class="btn" id="f-kaydet" onclick="kaydet()">Kaydet</button>
    <button class="btn btn-ikincil" id="f-sil" onclick="formdanSil()"><span class="sil-ikon">{{ ikon.sil|safe }}</span>Bu kaydı sil</button>
  </div>
</div>

<!-- Yardim -->
<div class="panel" id="yardim" role="dialog" aria-modal="true" aria-labelledby="yardim-b">
  <header class="bant kisa">
    <div class="bant-ust"><button class="bant-geri" onclick="modalKapat('yardim')">{{ ikon.geri|safe }}Kapat</button></div>
    <h1 id="yardim-b">Mobil Vinç — Nasıl kullanılır?</h1>
  </header>
  <div class="icerik yardim">
    <ol>
      <li><b>Gelir Ekle:</b> Vinç kirası, hizmet bedeli gibi aldığınız paraları yazın.</li>
      <li><b>Gider Ekle:</b> Yakıt, bakım, tamir, operatör gibi harcamaları yazın.</li>
      <li>Tarih, açıklama ve tutarı girip <b>Kaydet</b>'e dokunun. Tutarı <b>1.500</b> ya da <b>1500,50</b> gibi yazabilirsiniz.</li>
      <li><b>Düzeltmek için:</b> kayda dokunun ya da kaydı sola kaydırıp <b>Düzenle</b>'ye basın.</li>
      <li><b>Silmek için:</b> kaydı sola kaydırıp <b>Sil</b>'e basın; onay sorulur.</li>
    </ol>
    <p>Üstteki kart tüm zamanların toplamıdır: <b>Net = Gelir − Gider</b>. Kayıtlar aylara göre gruplanır, en yenisi en üstte; ay başlığında o ayın neti yazar.</p>
    <p>Vinç defteri puantajdan bağımsızdır; işçi hesaplarını etkilemez.</p>
    <button class="btn" onclick="modalKapat('yardim')">Anladım</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>{{ ortak_js|safe }}</script>
<script>
var KAYITLAR = {};
var DUZENLENEN = null;   // null = yeni kayit
var FORM_TIP = 'gelir';

function netSunum(net) {
  if (net > 0) return {sinif: 'renk-alacak', etiket: 'kâr'};
  if (net < 0) return {sinif: 'renk-borc', etiket: 'zarar'};
  return {sinif: 'renk-soluk', etiket: ''};
}

function yukle() {
  apiFetch('/api/vinc/liste').then(function(r) {
    el('o-gelir').textContent = fmtTL(r.toplam_gelir);
    el('o-gider').textContent = fmtTL(r.toplam_gider);
    var n = netSunum(r.net);
    el('o-net').textContent = fmtTL(Math.abs(r.net));
    el('o-net').className = 'ozet-d ' + n.sinif;
    el('o-net-not').textContent = n.etiket;
    el('o-net-not').className = 'ozet-not ' + n.sinif;
    ciz(r.kayitlar);
  }).catch(function(e) {
    el('liste').innerHTML = '<div class="bos renk-borc">Yüklenemedi: ' + escHtml(e.message) + '</div>';
  });
}

function ciz(kayitlar) {
  var y = window.scrollY;
  KAYITLAR = {};
  if (!kayitlar.length) {
    el('liste').innerHTML = '<div class="bos">Henüz kayıt yok. Yukarıdaki butonlarla ilk kaydı ekleyin.</div>';
    el('ipucu').style.display = 'none';
    return;
  }
  // Aylara gore grupla (liste zaten yeniden eskiye sirali gelir)
  var gruplar = [], sonAy = null;
  for (var i = 0; i < kayitlar.length; i++) {
    var k = kayitlar[i];
    KAYITLAR[k.id] = k;
    var ay = String(k.tarih || '').substring(0, 7);
    if (ay !== sonAy) { gruplar.push({ay: ay, net: 0, kayitlar: []}); sonAy = ay; }
    var g = gruplar[gruplar.length - 1];
    g.kayitlar.push(k);
    g.net += (k.tip === 'gelir' ? 1 : -1) * Number(k.miktar || 0);
  }
  var html = '';
  for (var j = 0; j < gruplar.length; j++) {
    var gr = gruplar[j], ns = netSunum(gr.net);
    html += '<div class="bolum"><div class="bolum-baslik"><span>' + escHtml(ayBaslik(gr.ay)) + '</span>' +
      '<span class="tutar ' + ns.sinif + '">Net ' + fmtTL(Math.abs(gr.net)) + (ns.etiket ? ' ' + ns.etiket : '') + '</span></div>';
    for (var m = 0; m < gr.kayitlar.length; m++) {
      var kk = gr.kayitlar[m];
      var gelir = kk.tip === 'gelir';
      var ic = satirIcerik(gelir ? 'yukari' : 'asagi', kk.aciklama || (gelir ? 'Gelir' : 'Gider'),
        tarihTR(kk.tarih) + ' · ' + (gelir ? 'Gelir' : 'Gider'),
        tutarHtml((gelir ? '+' : '−') + fmtTL(kk.miktar), gelir ? 'renk-alacak' : 'renk-borc', gelir ? 'gelir' : 'gider'));
      html += satirHtml(kk.id, ic);
    }
    html += '</div>';
  }
  el('liste').innerHTML = html;
  el('ipucu').style.display = 'block';
  window.scrollTo(0, y);
}

function tipSec(tip) {
  FORM_TIP = tip;
  el('f-tip-gelir').className = tip === 'gelir' ? 'aktif' : '';
  el('f-tip-gider').className = tip === 'gider' ? 'aktif' : '';
  el('f-acik').placeholder = tip === 'gelir' ? 'Vinç kirası, hizmet bedeli…' : 'Yakıt, bakım, tamir…';
}

function yeniKayit(tip) {
  DUZENLENEN = null;
  el('f-baslik').textContent = tip === 'gelir' ? 'Gelir Ekle' : 'Gider Ekle';
  el('f-tarih').value = bugunISO();
  el('f-acik').value = '';
  el('f-tutar').value = '';
  el('f-sil').style.display = 'none';
  tipSec(tip);
  modalAc('form');
}

function duzenle(id) {
  var k = KAYITLAR[id];
  if (!k) return;
  DUZENLENEN = id;
  el('f-baslik').textContent = 'Kaydı Düzenle';
  el('f-tarih').value = String(k.tarih || '').substring(0, 10);
  el('f-acik').value = k.aciklama || '';
  el('f-tutar').value = tlInputYaz(k.miktar);
  el('f-sil').style.display = 'flex';
  tipSec(k.tip === 'gider' ? 'gider' : 'gelir');
  modalAc('form');
}

function kaydet() {
  var tutar = parseTLInput(el('f-tutar').value);
  if (isNaN(tutar) || tutar <= 0) { toast('Geçerli bir tutar girin'); return; }
  var tarih = el('f-tarih').value;
  if (!tarih) { toast('Tarih seçin'); return; }
  var veri = {tip: FORM_TIP, tarih: tarih, aciklama: el('f-acik').value.trim(), miktar: tutar};
  var istek = DUZENLENEN === null ? jsonGonder('/api/vinc/ekle', 'POST', veri)
                                  : jsonGonder('/api/vinc/' + DUZENLENEN, 'PUT', veri);
  var btn = el('f-kaydet');
  btn.disabled = true;
  istek.then(function() {
    modalKapat('form');
    toast(DUZENLENEN === null ? 'Kaydedildi' : 'Güncellendi');
    yukle();
  }).catch(function(e) { toast('Hata: ' + e.message); })
    .then(function() { btn.disabled = false; });
}

function sil(id) {
  var k = KAYITLAR[id];
  if (!k) return;
  var ad = (k.aciklama || (k.tip === 'gelir' ? 'Gelir' : 'Gider')) + ' (' + tarihTR(k.tarih) + ', ' + fmtTL(k.miktar) + ')';
  onayIste('Silinsin mi?', ad + ' silinecek.', 'Sil').then(function(evet) {
    if (!evet) { satirKapat(); return; }
    jsonGonder('/api/vinc/sil', 'POST', {id: id}).then(function() {
      ACIK_SATIR = null;
      modalKapat('form');
      toast('Silindi');
      yukle();
    }).catch(function(e) { toast('Hata: ' + e.message); });
  });
}

function formdanSil() { if (DUZENLENEN !== null) sil(DUZENLENEN); }

kaydirmaKur(el('liste'), duzenle, duzenle, sil);
yukle();
</script>
</body>
</html>'''


@bp.route('/vinc')
def vinc_sayfa():
    html = render_template_string(VINC_HTML, ortak_head=ortak.ORTAK_HEAD, ortak_css=ortak.ORTAK_CSS,
                                  ortak_js=ortak.ORTAK_JS, ikon={ad: ortak.svg(ad) for ad in ortak.IKONLAR})
    return ortak.onbelleksiz(make_response(html))
