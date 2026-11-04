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
# SAYFA (/vinc)
# ====================================================================
VINC_HTML = r'''<!DOCTYPE html>
<html lang="tr">
<head>
{{ ortak_head|safe }}
<title>Mobil Vinç</title>
<style>{{ ortak_css|safe }}</style>
</head>
<body>
<a href="/" class="geri">&#8249; Ana Menü</a>
<div class="ust">
  <h1>Mobil Vinç</h1>
  <button class="yardim-btn" onclick="modalAc('yardim')" aria-label="Yardım" title="Yardım">?</button>
</div>

<div class="ozet">
  <div class="ozet-kutu" title="Tüm zamanların toplam geliri"><div class="deger yesil" id="o-gelir">-</div><div class="etiket">Gelir</div></div>
  <div class="ozet-kutu" title="Tüm zamanların toplam gideri"><div class="deger kirmizi" id="o-gider">-</div><div class="etiket">Gider</div></div>
  <div class="ozet-kutu genis" title="Gelir eksi gider"><div class="etiket">Net kâr / zarar</div><div class="deger" id="o-net">-</div></div>
</div>

<div class="btn-satir">
  <button class="btn btn-yesil" onclick="yeniKayit('gelir')">+ Gelir Ekle</button>
  <button class="btn btn-kirmizi" onclick="yeniKayit('gider')">+ Gider Ekle</button>
</div>

<div id="liste"><div class="bos">Yükleniyor…</div></div>
<div class="ipucu" id="ipucu" style="display:none">Düzenlemek için kayda dokunun ya da sola kaydırın.</div>

<!-- Kayit formu -->
<div class="modal-arka gizli" id="form" onclick="arkaTik(event, 'form')">
  <div class="modal">
    <div class="modal-ust"><h2 id="f-baslik">Kayıt</h2><button class="kapat" onclick="modalKapat('form')" aria-label="Kapat">&times;</button></div>
    <div class="secim">
      <button id="f-tip-gelir" onclick="tipSec('gelir')">Gelir</button>
      <button id="f-tip-gider" onclick="tipSec('gider')">Gider</button>
    </div>
    <div class="alan"><label for="f-tarih">Tarih</label><input type="date" id="f-tarih"></div>
    <div class="alan"><label for="f-acik">Açıklama</label><input type="text" id="f-acik" autocomplete="off"></div>
    <div class="alan"><label for="f-tutar">Tutar (₺)</label><input type="text" id="f-tutar" inputmode="decimal" placeholder="0" autocomplete="off"></div>
    <button class="btn" id="f-kaydet" onclick="kaydet()">Kaydet</button>
    <button class="btn btn-acik kirmizi" id="f-sil" onclick="formdanSil()">Bu kaydı sil</button>
  </div>
</div>

<!-- Yardim -->
<div class="modal-arka gizli" id="yardim" onclick="arkaTik(event, 'yardim')">
  <div class="modal yardim">
    <div class="modal-ust"><h2>Mobil Vinç — Nasıl kullanılır?</h2><button class="kapat" onclick="modalKapat('yardim')" aria-label="Kapat">&times;</button></div>
    <ol>
      <li><b>+ Gelir Ekle:</b> Vinç kirası, hizmet bedeli gibi aldığınız paraları yazın.</li>
      <li><b>+ Gider Ekle:</b> Yakıt, bakım, tamir, operatör gibi harcamaları yazın.</li>
      <li>Tarih, açıklama ve tutarı girip <b>Kaydet</b>'e dokunun. Tutarı <b>1.500</b> ya da <b>1500,50</b> gibi yazabilirsiniz.</li>
      <li><b>Düzeltmek için:</b> kayda dokunun ya da kaydı sola kaydırıp <b>Düzenle</b>'ye basın.</li>
      <li><b>Silmek için:</b> kaydı sola kaydırıp <b>Sil</b>'e basın; onay sorulur.</li>
    </ol>
    <p>Üstteki kutular tüm zamanların toplamıdır: <b>Net = Gelir − Gider</b>. Kayıtlar aylara göre gruplanır, en yenisi en üstte.</p>
    <p>Vinç defteri puantajdan bağımsızdır; işçi hesaplarını etkilemez.</p>
    <button class="btn" style="margin-top:14px" onclick="modalKapat('yardim')">Anladım</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>{{ ortak_js|safe }}</script>
<script>
var KAYITLAR = {};
var DUZENLENEN = null;   // null = yeni kayit
var FORM_TIP = 'gelir';

function yukle() {
  apiFetch('/api/vinc/liste').then(function(r) {
    document.getElementById('o-gelir').textContent = fmtTL(r.toplam_gelir);
    document.getElementById('o-gider').textContent = fmtTL(r.toplam_gider);
    var net = document.getElementById('o-net');
    net.textContent = fmtTL(r.net);
    net.className = 'deger ' + (r.net >= 0 ? 'yesil' : 'kirmizi');
    ciz(r.kayitlar);
  }).catch(function(e) {
    document.getElementById('liste').innerHTML = '<div class="bos kirmizi">Yüklenemedi: ' + escHtml(e.message) + '</div>';
  });
}

function ciz(kayitlar) {
  var y = window.scrollY;
  KAYITLAR = {};
  var kap = document.getElementById('liste');
  if (!kayitlar.length) {
    kap.innerHTML = '<div class="liste"><div class="bos">Henüz kayıt yok. Yukarıdaki butonlarla ilk kaydı ekleyin.</div></div>';
    document.getElementById('ipucu').style.display = 'none';
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
    var gr = gruplar[j];
    html += '<div class="grup-baslik"><span>' + escHtml(ayBaslik(gr.ay)) + '</span><span class="' +
      (gr.net >= 0 ? 'yesil' : 'kirmizi') + '">Net ' + fmtTL(gr.net) + '</span></div><div class="liste">';
    for (var m = 0; m < gr.kayitlar.length; m++) {
      var kk = gr.kayitlar[m];
      var gelir = kk.tip === 'gelir';
      var sol = '<div class="baslik">' + escHtml(kk.aciklama || (gelir ? 'Gelir' : 'Gider')) + '</div>' +
                '<div class="alt">' + tarihTR(kk.tarih) + ' · ' + (gelir ? 'Gelir' : 'Gider') + '</div>';
      var sag = '<div class="satir-tutar ' + (gelir ? 'yesil' : 'kirmizi') + '">' + (gelir ? '+' : '−') + fmtTL(kk.miktar) + '</div>';
      html += satirHtml(kk.id, sol, sag);
    }
    html += '</div>';
  }
  kap.innerHTML = html;
  document.getElementById('ipucu').style.display = 'block';
  window.scrollTo(0, y);
}

function tipSec(tip) {
  FORM_TIP = tip;
  document.getElementById('f-tip-gelir').className = tip === 'gelir' ? 'aktif' : '';
  document.getElementById('f-tip-gider').className = tip === 'gider' ? 'aktif' : '';
  document.getElementById('f-acik').placeholder = tip === 'gelir' ? 'Vinç kirası, hizmet bedeli…' : 'Yakıt, bakım, tamir…';
  document.getElementById('f-kaydet').className = 'btn ' + (tip === 'gelir' ? 'btn-yesil' : 'btn-kirmizi');
}

function yeniKayit(tip) {
  DUZENLENEN = null;
  document.getElementById('f-baslik').textContent = tip === 'gelir' ? 'Gelir Ekle' : 'Gider Ekle';
  document.getElementById('f-tarih').value = bugunISO();
  document.getElementById('f-acik').value = '';
  document.getElementById('f-tutar').value = '';
  document.getElementById('f-sil').style.display = 'none';
  tipSec(tip);
  modalAc('form');
}

function duzenle(id) {
  var k = KAYITLAR[id];
  if (!k) return;
  DUZENLENEN = id;
  document.getElementById('f-baslik').textContent = 'Kaydı Düzenle';
  document.getElementById('f-tarih').value = String(k.tarih || '').substring(0, 10);
  document.getElementById('f-acik').value = k.aciklama || '';
  document.getElementById('f-tutar').value = tlInputYaz(k.miktar);
  document.getElementById('f-sil').style.display = 'block';
  tipSec(k.tip === 'gider' ? 'gider' : 'gelir');
  modalAc('form');
}

function kaydet() {
  var tutar = parseTLInput(document.getElementById('f-tutar').value);
  if (isNaN(tutar) || tutar <= 0) { toast('Geçerli bir tutar girin'); return; }
  var tarih = document.getElementById('f-tarih').value;
  if (!tarih) { toast('Tarih seçin'); return; }
  var veri = {tip: FORM_TIP, tarih: tarih, aciklama: document.getElementById('f-acik').value.trim(), miktar: tutar};
  var istek = DUZENLENEN === null ? jsonGonder('/api/vinc/ekle', 'POST', veri)
                                  : jsonGonder('/api/vinc/' + DUZENLENEN, 'PUT', veri);
  var btn = document.getElementById('f-kaydet');
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
  var metin = (k.aciklama || (k.tip === 'gelir' ? 'Gelir' : 'Gider')) + ' (' + tarihTR(k.tarih) + ', ' + fmtTL(k.miktar) + ')';
  if (!onayla(metin + ' silinecek. Emin misiniz?')) { satirKapat(); return; }
  jsonGonder('/api/vinc/sil', 'POST', {id: id}).then(function() {
    ACIK_SATIR = null;
    modalKapat('form');
    toast('Silindi');
    yukle();
  }).catch(function(e) { toast('Hata: ' + e.message); });
}

function formdanSil() { if (DUZENLENEN !== null) sil(DUZENLENEN); }

kaydirmaKur(document.getElementById('liste'), duzenle, duzenle, sil);
yukle();
</script>
</body>
</html>'''


@bp.route('/vinc')
def vinc_sayfa():
    html = render_template_string(VINC_HTML, ortak_head=ortak.ORTAK_HEAD,
                                  ortak_css=ortak.ORTAK_CSS, ortak_js=ortak.ORTAK_JS)
    return ortak.onbelleksiz(make_response(html))
