"""
Puantaj API - PythonAnywhere versiyonu
Tek dosya, bagimsiz calisir
"""

from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, date, timedelta
import sqlite3
import os

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'puantaj.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS isci (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad_soyad TEXT NOT NULL,
        ustalik TEXT DEFAULT 'Duz Isci',
        gunluk_ucret REAL DEFAULT 0,
        telefon TEXT,
        aktif INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS puantaj (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        isci_id INTEGER,
        tarih DATE,
        giris_saati TIME,
        cikis_saati TIME,
        calisma_durumu TEXT DEFAULT 'tam_gun',
        mesai_saat REAL DEFAULT 0,
        yapilan_is TEXT,
        gunluk_ucret REAL
    )''')
    try:
        c.execute('ALTER TABLE puantaj ADD COLUMN gunluk_ucret REAL')
        conn.commit()
    except Exception:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS ek_gider (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT NOT NULL,
        tutar REAL DEFAULT 0,
        ay TEXT,
        tarih DATE DEFAULT CURRENT_DATE,
        aciklama TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS odeme (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        isci_id INTEGER,
        hafta_bitis DATE,
        miktar REAL DEFAULT 0,
        tarih DATE DEFAULT CURRENT_DATE,
        aciklama TEXT,
        FOREIGN KEY (isci_id) REFERENCES isci(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ayarlar (
        anahtar TEXT PRIMARY KEY,
        deger TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS beton_hakedis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarih DATE DEFAULT CURRENT_DATE,
        miktar_m3 REAL DEFAULT 0,
        birim_fiyat REAL DEFAULT 0,
        aciklama TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS yemek_odeme (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        miktar REAL DEFAULT 0,
        tarih DATE DEFAULT CURRENT_DATE,
        aciklama TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS civi_gider (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        miktar REAL DEFAULT 0,
        tarih DATE DEFAULT CURRENT_DATE,
        aciklama TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS civi_odeme (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        miktar REAL DEFAULT 0,
        tarih DATE DEFAULT CURRENT_DATE,
        aciklama TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS odeme_hatirlatma (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT NOT NULL,
        tarih DATE NOT NULL,
        aciklama TEXT DEFAULT ''
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS yemek_fiyat_gecmisi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fiyat REAL NOT NULL,
        gecerli_tarih DATE NOT NULL UNIQUE
    )''')
    conn.commit()
    conn.close()

init_db()


HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>Santiye Puantaj v5</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--pr:#e94560;--bg:#1a1a2e;--card:#16213e;--inp:#0f3460;--tx:#eaeaea;--ok:#00d26a;--wr:#ffc107;--er:#ff6b6b}
body{font-family:-apple-system,Arial,sans-serif;background:var(--bg);color:var(--tx);min-height:100vh;padding-bottom:90px}
.hdr{background:var(--card);padding:12px 8px;position:sticky;top:0;z-index:100;border-bottom:1px solid #ffffff18}
.hdr h1{font-size:20px;font-weight:700}
.drow{margin-top:10px;display:flex;gap:8px;align-items:center}
.drow input[type=date]{flex:1;padding:10px 12px;border:none;border-radius:10px;background:var(--inp);color:var(--tx);font-size:16px}
.drow button{width:42px;height:42px;border:none;border-radius:10px;background:var(--inp);color:var(--tx);font-size:18px;cursor:pointer}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:10px 8px}
.stat{background:var(--card);border-radius:12px;padding:14px 8px;text-align:center}
.stat .num{font-size:24px;font-weight:700;color:var(--pr)}
.stat .lbl{font-size:11px;color:#a0a0a0;margin-top:2px}
.stat.ok .num{color:var(--ok)}
.stat.wr .num{color:var(--wr)}
.tabs{display:flex;padding:0 8px;gap:6px;overflow-x:auto;-webkit-overflow-scrolling:touch}
.tab{padding:8px 14px;border:none;border-radius:10px;background:var(--card);color:#a0a0a0;font-size:13px;white-space:nowrap;cursor:pointer;-webkit-tap-highlight-color:transparent}
.tab.aktif{background:var(--pr);color:#fff;font-weight:600}
.panel{display:none;padding:10px 8px}
.panel.aktif{display:block}
.kart{background:var(--card);border-radius:14px;margin-bottom:10px;overflow:hidden}
.kart-ust{display:flex;align-items:center;padding:12px 14px;gap:10px;cursor:pointer;-webkit-tap-highlight-color:transparent}
.avt{width:40px;height:40px;border-radius:50%;background:var(--pr);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;flex-shrink:0}
.kart-bilgi{flex:1;min-width:0}
.kart-bilgi .ad{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kart-bilgi .alt{font-size:12px;color:#a0a0a0;margin-top:2px}
.kart-detay{padding:0 14px 14px}
.form-row{margin-bottom:10px}
.form-row label{font-size:12px;color:#a0a0a0;display:block;margin-bottom:4px}
.form-row select,.form-row input[type=text],.form-row input[type=time],.form-row input[type=number]{width:100%;padding:10px 12px;border:none;border-radius:10px;background:var(--inp);color:var(--tx);font-size:15px}
.form-row textarea{width:100%;padding:10px 12px;border:none;border-radius:10px;background:var(--inp);color:var(--tx);font-size:14px;resize:none;min-height:60px}
.btn{display:block;width:100%;padding:12px;border:none;border-radius:10px;font-size:15px;font-weight:600;cursor:pointer;margin-top:8px;-webkit-tap-highlight-color:transparent}
.btn-ok{background:var(--ok);color:#000}
.btn-pr{background:var(--pr);color:#fff}
.btn-wr{background:var(--wr);color:#000}
.btn-er{background:var(--er);color:#fff}
.btn-gray{background:#2a2a4a;color:#a0a0a0}
.empty{text-align:center;padding:30px;color:#a0a0a0;font-size:14px}
.ozet-kart{background:var(--card);border-radius:14px;padding:14px;margin-bottom:10px}
.ozet-kart h3{font-size:14px;color:#a0a0a0;margin-bottom:10px}
.ozet-row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #ffffff0a;font-size:14px}
.ozet-row:last-child{border-bottom:none;font-weight:700;font-size:15px}
.ozet-row .tutar{color:var(--ok)}
.ozet-row .tutar.er{color:var(--er)}
.badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600}
.badge-ok{background:#00d26a22;color:var(--ok)}
.badge-er{background:#ff6b6b22;color:var(--er)}
.badge-wr{background:#ffc10722;color:var(--wr)}
.isci-ozet-kart{background:var(--card);border-radius:12px;padding:12px;margin-bottom:8px}
.isci-ozet-kart .ad{font-size:14px;font-weight:600;margin-bottom:6px}
.isci-ozet-kart .satirlar{display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;font-size:13px}
.isci-ozet-kart .satirlar span{color:#a0a0a0}
.ode-btn{margin-top:8px;padding:8px 12px;background:var(--ok);color:#000;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;width:100%}
.geri-btn{margin-top:4px;padding:6px 12px;background:#2a2a4a;color:#a0a0a0;border:none;border-radius:8px;font-size:12px;cursor:pointer;width:100%}
.modal-arka{position:fixed;top:0;left:0;right:0;bottom:0;background:#000000bb;z-index:200;display:flex;align-items:flex-end}
.modal-arka.gizli{display:none}
.modal{background:var(--card);border-radius:20px 20px 0 0;padding:20px 16px 30px;width:100%;max-height:85vh;overflow-y:auto}
.modal h2{font-size:18px;font-weight:700;margin-bottom:16px}
.kapanis-btn{float:right;background:none;border:none;color:#a0a0a0;font-size:22px;cursor:pointer;padding:0 4px}
.toast{position:fixed;bottom:100px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 20px;border-radius:10px;font-size:14px;z-index:300;opacity:0;transition:opacity .3s;pointer-events:none;white-space:nowrap}
.toast.goster{opacity:1}
.nav{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid #ffffff18;display:flex;padding:6px 0 calc(6px + env(safe-area-inset-bottom))}
.nav-btn{flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;padding:6px 2px;border:none;background:none;color:#a0a0a0;font-size:10px;cursor:pointer;-webkit-tap-highlight-color:transparent}
.nav-btn.aktif{color:var(--pr)}
.nav-btn .ico{font-size:22px}
input[type=date]::-webkit-calendar-picker-indicator{filter:invert(1)}
.hiz-btn{width:40px;height:40px;border:none;border-radius:10px;background:#2a2a4a;color:#a0a0a0;font-size:17px;font-weight:700;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:background .15s,color .15s;flex-shrink:0}
.hiz-btn.hiz-er{background:var(--er);color:#fff}
.hiz-btn.hiz-wr{background:var(--wr);color:#000}
.hiz-btn.hiz-ok{background:var(--ok);color:#000}
.hiz-btn.hiz-bl{background:#3498db;color:#fff}
.gun-grid{display:flex;gap:3px;overflow-x:auto;-webkit-overflow-scrolling:touch;padding:8px 0 2px;margin-top:6px}
.gun-kare{min-width:22px;height:22px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;background:#1e1e3a;color:#555;flex-shrink:0}
.gun-kare.g-ok{background:var(--ok);color:#000}
.gun-kare.g-wr{background:var(--wr);color:#000}
.gun-kare.g-bl{background:#3498db;color:#fff}
.gun-kare.g-er{background:var(--er);color:#fff}
.hatbanner{background:#ff980018;border-left:4px solid #ff9800;padding:10px 14px;margin:8px 8px 0;border-radius:8px}
.hatbanner-hdr{display:flex;justify-content:space-between;align-items:center;font-weight:700;color:#ff9800;font-size:14px;margin-bottom:4px}
.hatbanner-satir{font-size:13px;padding:2px 0;color:var(--tx)}
.hatbanner-gizli{display:none}
</style>
</head>
<body>

<div class="hdr">
  <h1>&#x1F477; Santiye Puantaj</h1>
  <div class="drow">
    <input type="date" id="tarih" onchange="load()">
    <button onclick="gunGec(-1)">&#8592;</button>
    <button onclick="gunGec(1)">&#8594;</button>
    <button onclick="bugun()">&#128197;</button>
  </div>
</div>

<div id="hat-banner" class="hatbanner-gizli"></div>

<div class="stats">
  <div class="stat ok"><div class="num" id="s-gelen">-</div><div class="lbl">Gelen</div></div>
  <div class="stat er"><div class="num" id="s-gelmeyen">-</div><div class="lbl">Gelmeyen</div></div>
  <div class="stat wr"><div class="num" id="s-mesai">-</div><div class="lbl">Mesai Saat</div></div>
</div>

<div class="tabs">
  <button class="tab aktif" onclick="sekme('puantaj',this)">Puantaj</button>
  <button class="tab" onclick="sekme('ozet',this)">Ozet</button>
  <button class="tab" onclick="sekme('aylik',this)">Aylik</button>
  <button class="tab" onclick="sekme('gider',this)">Giderler</button>
  <button class="tab" onclick="sekme('isciler',this)">Isciler</button>
  <button class="tab" onclick="sekme('ayarlar',this)">Ayarlar</button>
  <button class="tab" onclick="sekme('hakedis',this)">Hakedis</button>
</div>

<!-- PUANTAJ PANELİ -->
<div id="panel-puantaj" class="panel aktif">
  <div id="pList"><div class="empty">Yukleniyor...</div></div>
</div>

<!-- ÖZET PANELİ -->
<div id="panel-ozet" class="panel">
  <div id="ozetList"><div class="empty">Yukleniyor...</div></div>
</div>

<!-- AYLIK PANELİ -->
<div id="panel-aylik" class="panel">
  <div style="padding:0 0 10px;display:flex;gap:8px;align-items:center">
    <input type="month" id="aylikAy" style="flex:1;padding:10px;border:none;border-radius:10px;background:var(--inp);color:var(--tx);font-size:15px">
    <button class="btn btn-pr" style="width:auto;padding:10px 16px;margin:0" onclick="loadAylik()">Goster</button>
  </div>
  <div id="aylikList"><div class="empty">Ay secin</div></div>
</div>

<!-- GİDER PANELİ -->
<div id="panel-gider" class="panel">
  <button class="btn btn-pr" onclick="giderEkleModal()">+ Gider Ekle</button>
  <div id="giderList" style="margin-top:10px"><div class="empty">Yukleniyor...</div></div>
</div>

<!-- İŞÇİLER PANELİ -->
<div id="panel-isciler" class="panel">
  <button class="btn btn-pr" onclick="isciEkleModal()">+ Isci Ekle</button>
  <div id="isciList" style="margin-top:10px"><div class="empty">Yukleniyor...</div></div>
</div>

<!-- AYARLAR PANELİ -->
<div id="panel-ayarlar" class="panel">
  <div class="ozet-kart">
    <h3>Genel Ayarlar</h3>
    <div class="form-row">
      <label>Yemek Fiyati (TL/kisi/gun)</label>
      <input type="number" id="ay-yemek" placeholder="0" step="1">
    </div>
    <button class="btn btn-ok" onclick="ayarKaydet()">Kaydet</button>
  </div>
  <div class="ozet-kart" style="margin-top:10px">
    <h3>Odeme Hatirlatmalari</h3>
    <p style="font-size:12px;color:#a0a0a0;margin-bottom:10px">Odeme tarihine 7 gun kalinca uygulama aciliginda uyari gosterilir.</p>
    <button class="btn btn-pr" onclick="hatirlatmaEkleModal()" style="margin-bottom:10px">+ Hatirlatma Ekle</button>
    <div id="hatirlatma-list"></div>
  </div>
  <div class="ozet-kart" style="margin-top:10px">
    <h3>Donem Yonetimi</h3>
    <p style="font-size:13px;color:#a0a0a0;margin-bottom:12px">Yeni donem baslatmak tum odemeler listesini sifirlar. Puantaj ve hakedis verileri silinmez.</p>
    <button class="btn btn-er" onclick="yeniDonem()">Yeni Donem Baslat</button>
  </div>
</div>

<!-- HAKEDİŞ PANELİ -->
<div id="panel-hakedis" class="panel">
  <div style="padding:0 0 10px;display:flex;gap:8px;align-items:center">
    <input type="month" id="hakedisAy" style="flex:1;padding:10px;border:none;border-radius:10px;background:var(--inp);color:var(--tx);font-size:15px">
    <button class="btn btn-pr" style="width:auto;padding:10px 16px;margin:0" onclick="loadHakedis()">Goster</button>
  </div>
  <button class="btn btn-pr" onclick="hakedisEkleModal()">+ Dokum Ekle</button>
  <div id="hakedisOzet" style="margin-top:10px"></div>
  <div id="hakedisList" style="margin-top:10px"><div class="empty">Ay secin</div></div>
</div>

<!-- NAVİGASYON -->
<div class="nav">
  <button class="nav-btn aktif" onclick="sekme('puantaj',this)" id="nav-puantaj">
    <span class="ico">&#128203;</span><span>Puantaj</span>
  </button>
  <button class="nav-btn" onclick="sekme('ozet',this)" id="nav-ozet">
    <span class="ico">&#128176;</span><span>Ozet</span>
  </button>
  <button class="nav-btn" onclick="sekme('aylik',this)" id="nav-aylik">
    <span class="ico">&#128197;</span><span>Aylik</span>
  </button>
  <button class="nav-btn" onclick="sekme('gider',this)" id="nav-gider">
    <span class="ico">&#128181;</span><span>Giderler</span>
  </button>
  <button class="nav-btn" onclick="sekme('isciler',this)" id="nav-isciler">
    <span class="ico">&#128104;</span><span>Isciler</span>
  </button>
  <button class="nav-btn" onclick="sekme('hakedis',this)" id="nav-hakedis">
    <span class="ico">&#128220;</span><span>Hakedis</span>
  </button>
</div>

<!-- MODALS -->
<div class="modal-arka gizli" id="modal-arka" onclick="modalKapat(event)">
  <div class="modal" id="modal-ici"></div>
</div>

<div class="toast" id="toast"></div>

<script>
// ====== DURUM ======
var IS_LIST = [];
var PU_MAP = {};
var ACIK_KART = null;
var AKTIF_SEKME = 'puantaj';
var ISCI_AD_MAP = {};
var DURUM_ISIMLER = ['gelmedi', 'yarim_gun', 'tam_gun', 'bir_bucuk_gun'];
var DURUM_KODLARI = {gelmedi: 0, izinli: 0, yarim_gun: 1, tam_gun: 2, bir_bucuk_gun: 3};
var AYLIK_GUNLER = {};

// ====== YARDIMCI ======
function fmt(n) {
  if (n === null || n === undefined) return '0';
  return Number(n).toLocaleString('tr-TR');
}
function fmtTL(n) {
  if (n === null || n === undefined) return '0 TL';
  return Number(n).toLocaleString('tr-TR') + ' TL';
}
function toast(m, t) {
  var el = document.getElementById('toast');
  el.textContent = m;
  el.className = 'toast goster';
  clearTimeout(el._t);
  el._t = setTimeout(function() { el.className = 'toast'; }, t || 2500);
}
function durdur(e) { e.stopPropagation(); }

// ====== TARİH ======
function bugun() {
  var d = new Date();
  var ay = d.getMonth() + 1;
  var gun = d.getDate();
  document.getElementById('tarih').value = d.getFullYear() + '-' +
    (ay < 10 ? '0' + ay : ay) + '-' +
    (gun < 10 ? '0' + gun : gun);
  load();
}
function gunGec(d) {
  var t = document.getElementById('tarih').value;
  if (!t) { bugun(); return; }
  var p = t.split('-');
  var dt = new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
  dt.setDate(dt.getDate() + d);
  var ay = dt.getMonth() + 1;
  var gun = dt.getDate();
  document.getElementById('tarih').value = dt.getFullYear() + '-' +
    (ay < 10 ? '0' + ay : ay) + '-' +
    (gun < 10 ? '0' + gun : gun);
  load();
}

// ====== SEKME ======
function sekme(id, btn) {
  AKTIF_SEKME = id;
  var paneller = document.querySelectorAll('.panel');
  for (var i = 0; i < paneller.length; i++) {
    paneller[i].className = 'panel';
  }
  document.getElementById('panel-' + id).className = 'panel aktif';

  var tablar = document.querySelectorAll('.tab');
  for (var j = 0; j < tablar.length; j++) {
    tablar[j].className = 'tab';
  }
  var navlar = document.querySelectorAll('.nav-btn');
  for (var k = 0; k < navlar.length; k++) {
    navlar[k].className = 'nav-btn';
  }
  if (btn) {
    if (btn.classList.contains('tab')) btn.className = 'tab aktif';
    if (btn.classList.contains('nav-btn')) btn.className = 'nav-btn aktif';
    var navEl = document.getElementById('nav-' + id);
    if (navEl) navEl.className = 'nav-btn aktif';
  }

  if (id === 'ozet') loadOzet();
  if (id === 'aylik') loadAylik();
  if (id === 'gider') loadGider();
  if (id === 'isciler') loadIsciler();
  if (id === 'ayarlar') loadAyarlar();
  if (id === 'hakedis') loadHakedis();
}

// ====== API ======
function apiFetch(url, opts) {
  return fetch(url, opts).then(function(r) {
    if (!r.ok) {
      return r.text().then(function(txt) {
        throw new Error('HTTP ' + r.status + ': ' + txt.substring(0, 100));
      });
    }
    return r.json();
  });
}

// ====== LOAD ======
function load() {
  var t = document.getElementById('tarih').value;
  if (!t) return;
  document.getElementById('pList').innerHTML = '<div class="empty">Yukleniyor...</div>';
  document.getElementById('s-gelen').textContent = '-';
  document.getElementById('s-gelmeyen').textContent = '-';
  document.getElementById('s-mesai').textContent = '-';

  Promise.all([
    apiFetch('/api/ozet/gunluk?tarih=' + t),
    apiFetch('/api/isci'),
    apiFetch('/api/puantaj?tarih=' + t)
  ]).then(function(r) {
    var st = r[0];
    var iscilar = r[1];
    var pu = r[2];
    IS_LIST = iscilar;
    PU_MAP = {};
    for (var x = 0; x < pu.length; x++) {
      PU_MAP[pu[x].isci_id] = pu[x];
    }
    document.getElementById('s-gelen').textContent = st.gelen_isci || 0;
    document.getElementById('s-gelmeyen').textContent = st.gelmeyen_isci || 0;
    document.getElementById('s-mesai').textContent = st.toplam_mesai_saat || 0;
    renderPuantaj(t);
  }).catch(function(e) {
    document.getElementById('pList').innerHTML =
      '<div class="empty" style="color:var(--er)">Hata: ' + e.message + '</div>';
  });
}

// ====== PUANTAJ RENDER ======
function renderPuantaj(t) {
  if (!IS_LIST.length) {
    document.getElementById('pList').innerHTML = '<div class="empty">Hic isci yok. Once isci ekleyin.</div>';
    return;
  }
  var html = '';
  for (var i = 0; i < IS_LIST.length; i++) {
    var isc = IS_LIST[i];
    var p = PU_MAP[isc.id];
    var durum = p ? (p.calisma_durumu || '') : '';
    var dk = (durum && DURUM_KODLARI[durum] !== undefined) ? DURUM_KODLARI[durum] : -1;
    var giris = p ? (p.giris_saati || '08:00') : '08:00';
    var cikis = p ? (p.cikis_saati || '17:00') : '17:00';
    var mesai = p ? (p.mesai_saat || 0) : 0;
    var yis = p ? (p.yapilan_is || '') : '';
    var ilk = isc.ad_soyad ? isc.ad_soyad.charAt(0).toUpperCase() : '?';

    html += '<div class="kart" style="margin-bottom:8px">';
    // Kart üst: avatar + isim + hızlı butonlar
    html += '<div style="display:flex;align-items:center;gap:10px;padding:12px 14px">';
    html += '<div class="avt" style="cursor:pointer" onclick="kartAc(' + isc.id + ')">' + ilk + '</div>';
    html += '<div style="flex:1;min-width:0;cursor:pointer" onclick="kartAc(' + isc.id + ')">';
    html += '<div style="font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + isc.ad_soyad + '</div>';
    html += '<div style="font-size:12px;color:#a0a0a0">' + (isc.ustalik || '') + ' &bull; ' + fmtTL(isc.gunluk_ucret) + '/gun</div>';
    html += '</div>';
    // Hızlı durum butonları
    html += '<div style="display:flex;gap:4px">';
    html += '<button class="hiz-btn' + (dk === 0 ? ' hiz-er' : '') + '" onclick="anindaKaydet(' + isc.id + ',0)">&#10005;</button>';
    html += '<button class="hiz-btn' + (dk === 1 ? ' hiz-wr' : '') + '" onclick="anindaKaydet(' + isc.id + ',1)">&#189;</button>';
    html += '<button class="hiz-btn' + (dk === 2 ? ' hiz-ok' : '') + '" onclick="anindaKaydet(' + isc.id + ',2)">1</button>';
    html += '<button class="hiz-btn' + (dk === 3 ? ' hiz-bl' : '') + '" onclick="anindaKaydet(' + isc.id + ',3)">1&#189;</button>';
    html += '</div>';
    html += '</div>';
    // Detay alanı (genişleyebilir — mesai/notlar için)
    html += '<div class="kart-detay" id="kdet-' + isc.id + '" style="display:none">';
    html += '<div style="display:flex;gap:8px">';
    html += '<div class="form-row" style="flex:1"><label>Giris</label><input type="time" id="gir-' + isc.id + '" value="' + giris + '"></div>';
    html += '<div class="form-row" style="flex:1"><label>Cikis</label><input type="time" id="cik-' + isc.id + '" value="' + cikis + '"></div>';
    html += '</div>';
    html += '<div class="form-row"><label>Mesai (Saat)</label><input type="number" id="mes-' + isc.id + '" value="' + mesai + '" step="0.5" min="0" max="12"></div>';
    html += '<div class="form-row"><label>Yapilan Is</label><textarea id="yis-' + isc.id + '">' + yis + '</textarea></div>';
    html += '<button class="btn btn-ok" onclick="kaydet(' + isc.id + ')">Saat / Not Kaydet</button>';
    if (p) {
      html += '<button class="btn btn-er" style="margin-top:6px" onclick="puSil(' + isc.id + ')">Kaydi Sil</button>';
    }
    html += '</div>';
    html += '</div>';
  }
  document.getElementById('pList').innerHTML = html;
}

function updateDurumButonlari(isciId, aktifKod) {
  var kdet = document.getElementById('kdet-' + isciId);
  if (!kdet) return;
  var butonlar = kdet.parentElement.querySelectorAll('.hiz-btn');
  var renkler = ['hiz-er', 'hiz-wr', 'hiz-ok', 'hiz-bl'];
  for (var i = 0; i < butonlar.length; i++) {
    butonlar[i].className = 'hiz-btn' + (i === aktifKod ? ' ' + renkler[i] : '');
  }
}

function updateStats() {
  var gelen = 0, mesai = 0;
  for (var id in PU_MAP) {
    var p = PU_MAP[id];
    var d = p.calisma_durumu;
    if (d && d !== 'gelmedi' && d !== 'izinli') gelen++;
    mesai += Number(p.mesai_saat) || 0;
  }
  document.getElementById('s-gelen').textContent = gelen;
  document.getElementById('s-gelmeyen').textContent = Math.max(0, IS_LIST.length - gelen);
  document.getElementById('s-mesai').textContent = mesai;
}

function anindaKaydet(isciId, durumKod) {
  var durum = DURUM_ISIMLER[durumKod];
  var tarih = document.getElementById('tarih').value;
  if (!tarih) { toast('Lutfen tarih secin'); return; }
  var girEl = document.getElementById('gir-' + isciId);
  var cikEl = document.getElementById('cik-' + isciId);
  var veri = {
    isci_id: isciId,
    tarih: tarih,
    calisma_durumu: durum,
    giris_saati: girEl ? girEl.value : '08:00',
    cikis_saati: cikEl ? cikEl.value : '17:00',
    mesai_saat: 0,
    yapilan_is: ''
  };
  apiFetch('/api/puantaj', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(veri)
  }).then(function() {
    if (!PU_MAP[isciId]) PU_MAP[isciId] = {isci_id: isciId, mesai_saat: 0};
    PU_MAP[isciId].calisma_durumu = durum;
    updateDurumButonlari(isciId, durumKod);
    updateStats();
  }).catch(function(e) { toast('Hata: ' + e.message); });
}

function kartAc(id) {
  if (ACIK_KART === id) {
    document.getElementById('kdet-' + id).style.display = 'none';
    ACIK_KART = null;
  } else {
    if (ACIK_KART !== null) {
      var eski = document.getElementById('kdet-' + ACIK_KART);
      if (eski) eski.style.display = 'none';
    }
    document.getElementById('kdet-' + id).style.display = 'block';
    ACIK_KART = id;
  }
}

function kaydet(isciId) {
  var tarih = document.getElementById('tarih').value;
  var p = PU_MAP[isciId];
  var dur = p ? p.calisma_durumu : '';
  if (!dur) { toast('Once durum secin (&#10005; / &#189; / 1 / 1&#189;)'); return; }
  var veri = {
    isci_id: isciId,
    tarih: tarih,
    calisma_durumu: dur,
    giris_saati: document.getElementById('gir-' + isciId).value,
    cikis_saati: document.getElementById('cik-' + isciId).value,
    mesai_saat: parseFloat(document.getElementById('mes-' + isciId).value) || 0,
    yapilan_is: document.getElementById('yis-' + isciId).value
  };
  apiFetch('/api/puantaj', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(veri)
  }).then(function() {
    toast('Kaydedildi!');
    ACIK_KART = null;
    load();
  }).catch(function(e) { toast('Hata: ' + e.message); });
}

function puSil(isciId) {
  var tarih = document.getElementById('tarih').value;
  if (!confirm('Bu kaydi sil?')) return;
  apiFetch('/api/puantaj/sil?isci_id=' + isciId + '&tarih=' + tarih, {method: 'DELETE'})
    .then(function() {
      delete PU_MAP[isciId];
      updateDurumButonlari(isciId, -1);
      var kdet = document.getElementById('kdet-' + isciId);
      if (kdet) {
        var silBtn = kdet.querySelector('.btn-er');
        if (silBtn) silBtn.style.display = 'none';
      }
      updateStats();
      toast('Silindi');
    })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

// ====== ÖZET ======
var _OZET_SCROLL = 0;

function loadOzet(koruyScroll) {
  if (koruyScroll) _OZET_SCROLL = window.scrollY;
  document.getElementById('ozetList').innerHTML = '<div class="empty">Yukleniyor...</div>';
  apiFetch('/api/ozet/haftalik').then(function(d) {
    var html = '';

    // Kümülatif özet kartı
    html += '<div class="ozet-kart">';
    html += '<h3>Donem Ozeti</h3>';
    html += '<div class="ozet-row"><span>Toplam Kalan</span><span class="tutar">' + fmtTL(d.toplam_kalan) + '</span></div>';
    var yNet = d.yemek_fiyati > 0 ? Math.round((d.yemek_maliyeti - d.yemek_odenen) * 100) / 100 : 0;
    if (d.yemek_fiyati > 0) {
      if (yNet > 0) {
        html += '<div class="ozet-row"><span>Yemek Kalan</span><span class="tutar er">' + fmtTL(yNet) + '</span></div>';
      } else if (yNet < 0) {
        html += '<div class="ozet-row"><span>Yemek Fazla Odendi</span><span class="tutar ok">' + fmtTL(-yNet) + '</span></div>';
      } else {
        html += '<div class="ozet-row"><span>Yemek</span><span class="tutar ok">Odendi</span></div>';
      }
    }
    if (d.civi_toplam > 0) {
      html += '<div class="ozet-row"><span>Civi Alimi</span><span class="tutar ' + (d.civi_kalan > 0 ? 'er' : 'ok') + '">' + fmtTL(d.civi_kalan) + ' kalan / ' + fmtTL(d.civi_toplam) + ' toplam</span></div>';
    }
    var buHaftaToplam = (d.toplam_kalan || 0) + Math.max(yNet, 0) + (d.civi_kalan || 0);
    html += '<div class="ozet-row" style="border-top:2px solid #ffffff25;margin-top:6px;padding-top:8px"><span><strong>Bu Haftaki Toplam</strong></span><span style="color:var(--pr);font-weight:700;font-size:16px">' + fmtTL(buHaftaToplam) + '</span></div>';
    html += '</div>';

    // Yemek butonları
    if (d.yemek_fiyati > 0) {
      html += '<div style="display:flex;gap:8px;margin-bottom:10px">';
      if (yNet > 0) {
        html += '<button class="ode-btn" style="flex:1" onclick="yemekOde(' + yNet + ')">Yemek Ode (' + fmtTL(yNet) + ')</button>';
      }
      if (d.son_yemek_odeme_id) {
        html += '<button class="geri-btn" style="flex:1" onclick="yemekOdemeGeri(' + d.son_yemek_odeme_id + ',' + d.son_yemek_odeme_miktar + ')">Son Yemek Geri Al (' + fmtTL(d.son_yemek_odeme_miktar) + ')</button>';
      }
      html += '</div>';
    }

    // Çivi butonları
    html += '<div style="display:flex;gap:8px;margin-bottom:10px">';
    html += '<button class="ode-btn" style="flex:1;background:#3498db" onclick="civiGiderEkle()">+ Civi Gideri Gir</button>';
    if (d.civi_kalan > 0) {
      html += '<button class="ode-btn" style="flex:1;background:var(--wr);color:#000" onclick="civiOde(' + d.civi_kalan + ')">Civi Ode (' + fmtTL(d.civi_kalan) + ')</button>';
    }
    html += '</div>';
    if (d.son_civi_odeme_id || d.son_civi_gider_id) {
      html += '<div style="display:flex;gap:8px;margin-bottom:10px">';
      if (d.son_civi_odeme_id) {
        html += '<button class="geri-btn" style="flex:1" onclick="civiOdemeGeri(' + d.son_civi_odeme_id + ',' + d.son_civi_odeme_miktar + ')">Son Civi Odeme Geri Al (' + fmtTL(d.son_civi_odeme_miktar) + ')</button>';
      }
      if (d.son_civi_gider_id) {
        html += '<button class="geri-btn" style="flex:1" onclick="civiGiderSil(' + d.son_civi_gider_id + ',' + d.son_civi_gider_miktar + ')">Son Civi Giderini Sil (' + fmtTL(d.son_civi_gider_miktar) + ')</button>';
      }
      html += '</div>';
    }

    // İşçi bazlı
    ISCI_AD_MAP = {};
    for (var j = 0; j < d.isciler.length; j++) {
      var isc = d.isciler[j];
      ISCI_AD_MAP[isc.id] = isc.ad_soyad;
      html += '<div class="isci-ozet-kart">';
      html += '<div class="ad">' + isc.ad_soyad + '</div>';
      html += '<div class="satirlar">';
      html += '<span>Kalan Yevmiye</span><strong>' + (isc.kalan_yevmiye || 0) + ' gun</strong>';
      html += '<span>Kalan Odeme</span><strong>' + fmtTL(isc.kalan) + '</strong>';
      html += '</div>';
      if (isc.kalan > 0) {
        html += '<button class="ode-btn" onclick="odemeYap(' + isc.id + ',' + isc.kalan + ')">Odeme Yap</button>';
      }
      if (isc.son_odeme_id) {
        html += '<button class="geri-btn" onclick="odemeGeri(' + isc.son_odeme_id + ',' + isc.son_odeme_miktar + ')">Son Odemeyi Geri Al (' + fmtTL(isc.son_odeme_miktar) + ')</button>';
      }
      html += '</div>';
    }

    document.getElementById('ozetList').innerHTML = html;
    if (koruyScroll) {
      setTimeout(function() { window.scrollTo(0, _OZET_SCROLL); }, 60);
    }
  }).catch(function(e) {
    document.getElementById('ozetList').innerHTML = '<div class="empty" style="color:var(--er)">Hata: ' + e.message + '</div>';
  });
}

function odemeYap(isciId, kalan) {
  var ad = ISCI_AD_MAP[isciId] || 'Isci';
  var miktar = prompt(ad + ' icin odeme miktari (TL):', Math.round(kalan));
  if (!miktar) return;
  miktar = parseFloat(miktar);
  if (isNaN(miktar) || miktar <= 0) { toast('Gecersiz miktar'); return; }
  apiFetch('/api/odeme', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({isci_id: isciId, miktar: miktar, aciklama: 'Manuel odeme'})
  }).then(function() { toast('Odeme kaydedildi!'); loadOzet(true); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function odemeGeri(odemeId, miktar) {
  if (!confirm(fmtTL(miktar) + ' tutarindaki odemeyi geri al?')) return;
  apiFetch('/api/odeme/' + odemeId, {method: 'DELETE'})
    .then(function() { toast('Odeme geri alindi'); loadOzet(true); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function yemekOde(kalan) {
  var miktar = prompt('Yemek odemesi miktari (TL):', Math.round(kalan));
  if (!miktar) return;
  miktar = parseFloat(miktar);
  if (isNaN(miktar) || miktar <= 0) { toast('Gecersiz miktar'); return; }
  apiFetch('/api/yemek/ode', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({miktar: miktar, aciklama: 'Yemek odemesi'})
  }).then(function() { toast('Yemek odemesi kaydedildi!'); loadOzet(true); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function yemekOdemeGeri(odemeId, miktar) {
  if (!confirm(fmtTL(miktar) + ' tutarindaki yemek odemesini geri al?')) return;
  apiFetch('/api/yemek/odeme/' + odemeId, {method: 'DELETE'})
    .then(function() { toast('Yemek odemesi geri alindi'); loadOzet(true); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function civiGiderEkle() {
  var miktar = prompt('Bu haftaki civi alimi miktari (TL):', '');
  if (!miktar) return;
  miktar = parseFloat(miktar);
  if (isNaN(miktar) || miktar <= 0) { toast('Gecersiz miktar'); return; }
  apiFetch('/api/civi/gider', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({miktar: miktar, aciklama: 'Civi alimi'})
  }).then(function() { toast('Civi gideri eklendi!'); loadOzet(true); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function civiOde(kalan) {
  var miktar = prompt('Civi odemesi miktari (TL):', Math.round(kalan));
  if (!miktar) return;
  miktar = parseFloat(miktar);
  if (isNaN(miktar) || miktar <= 0) { toast('Gecersiz miktar'); return; }
  apiFetch('/api/civi/ode', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({miktar: miktar, aciklama: 'Civi odemesi'})
  }).then(function() { toast('Civi odemesi kaydedildi!'); loadOzet(true); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function civiOdemeGeri(odemeId, miktar) {
  if (!confirm(fmtTL(miktar) + ' tutarindaki civi odemesini geri al?')) return;
  apiFetch('/api/civi/odeme/' + odemeId, {method: 'DELETE'})
    .then(function() { toast('Civi odemesi geri alindi'); loadOzet(true); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function civiGiderSil(giderId, miktar) {
  if (!confirm(fmtTL(miktar) + ' tutarindaki civi giderini sil?')) return;
  apiFetch('/api/civi/gider/' + giderId, {method: 'DELETE'})
    .then(function() { toast('Civi gideri silindi'); loadOzet(true); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

// ====== AYLIK ======
function loadAylik() {
  var ay = document.getElementById('aylikAy').value;
  if (!ay) { toast('Ay secin'); return; }
  document.getElementById('aylikList').innerHTML = '<div class="empty">Yukleniyor...</div>';
  apiFetch('/api/ozet/aylik?ay=' + ay).then(function(d) {
    if (d.toplam_hakedis === 0 && d.isciler.length === 0) {
      document.getElementById('aylikList').innerHTML = '<div class="empty">Bu ay icin puantaj kaydi bulunamadi.</div>';
      return;
    }
    var html = '<div class="ozet-kart">';
    html += '<h3>' + ay + ' Aylik Ozet</h3>';
    html += '<div class="ozet-row"><span>Toplam Hakedis</span><span class="tutar">' + fmtTL(d.toplam_hakedis) + '</span></div>';
    if (d.yemek_maliyeti > 0) {
      html += '<div class="ozet-row"><span>Yemek Maliyeti</span><span class="tutar er">' + fmtTL(d.yemek_maliyeti) + '</span></div>';
    }
    if (d.civi_maliyeti > 0) {
      html += '<div class="ozet-row"><span>Civi Alimi</span><span class="tutar er">' + fmtTL(d.civi_maliyeti) + '</span></div>';
    }
    html += '</div>';
    var ayPar = ay.split('-');
    var ayGunSayisi = new Date(parseInt(ayPar[0]), parseInt(ayPar[1]), 0).getDate();

    AYLIK_GUNLER = {};
    var veriOlanlar = 0;
    for (var i = 0; i < d.isciler.length; i++) {
      var isc = d.isciler[i];
      if (isc.aylik_yevmiye === 0 && isc.aylik_hakedis === 0) continue;
      veriOlanlar++;
      AYLIK_GUNLER[isc.id] = isc.gunler || {};
      ISCI_AD_MAP[isc.id] = isc.ad_soyad;
      html += '<div class="isci-ozet-kart" style="cursor:pointer" onclick="takvimGoster(' + isc.id + ',' + ayGunSayisi + ')">';
      html += '<div class="ad">' + isc.ad_soyad + ' <small style="color:#a0a0a0;font-weight:400">' + (isc.ustalik || '') + '</small>';
      html += ' <small style="color:#3498db;font-size:10px">&#128197; Devam goster</small></div>';
      html += '<div class="satirlar">';
      html += '<span>Yevmiye</span><strong>' + isc.aylik_yevmiye + ' gun</strong>';
      html += '<span>Hakedis</span><strong>' + fmtTL(isc.aylik_hakedis) + '</strong>';
      html += '</div>';
      html += '</div>';
    }
    if (veriOlanlar === 0) {
      html += '<div class="empty">Bu ay icin puantaj kaydi bulunamadi.</div>';
    }
    document.getElementById('aylikList').innerHTML = html;
  }).catch(function(e) {
    document.getElementById('aylikList').innerHTML = '<div class="empty" style="color:var(--er)">Hata: ' + e.message + '</div>';
  });
}

function takvimGoster(isciId, ayGunSayisi) {
  var gunler = AYLIK_GUNLER[isciId] || {};
  var ad = ISCI_AD_MAP[isciId] || 'Isci';
  var ay = document.getElementById('aylikAy').value;
  var siniflar = {tam_gun: 'g-ok', yarim_gun: 'g-wr', bir_bucuk_gun: 'g-bl', gelmedi: 'g-er', izinli: 'g-er'};
  var etiketler = {tam_gun: '1', yarim_gun: '&#189;', bir_bucuk_gun: '1&#189;', gelmedi: '&#10005;', izinli: '&#10005;'};

  var grid = '<div class="gun-grid" style="flex-wrap:wrap">';
  for (var g = 1; g <= ayGunSayisi; g++) {
    var dur = gunler[String(g)] || '';
    var sinif = siniflar[dur] || '';
    var ust = dur ? etiketler[dur] : String(g);
    var alt = dur ? String(g) : '';
    grid += '<div class="gun-kare ' + sinif + '" style="height:32px;flex-direction:column;gap:1px">';
    grid += '<span style="font-size:8px;opacity:.7">' + (dur ? String(g) : g) + '</span>';
    grid += (dur ? '<span>' + etiketler[dur] + '</span>' : '');
    grid += '</div>';
  }
  grid += '</div>';

  var aciklama = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;font-size:11px;color:#a0a0a0">';
  aciklama += '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:var(--ok);margin-right:3px"></span>Tam Gun</span>';
  aciklama += '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:var(--wr);margin-right:3px"></span>Yarim Gun</span>';
  aciklama += '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#3498db;margin-right:3px"></span>1.5 Gun</span>';
  aciklama += '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:var(--er);margin-right:3px"></span>Gelmedi</span>';
  aciklama += '</div>';

  document.getElementById('modal-ici').innerHTML =
    '<button class="kapanis-btn" onclick="modalKapat()">&#10005;</button>' +
    '<h2 style="font-size:16px">' + ad + '</h2>' +
    '<p style="font-size:12px;color:#a0a0a0;margin-bottom:10px">' + ay + ' Devam Takvimi</p>' +
    grid + aciklama;
  document.getElementById('modal-arka').className = 'modal-arka';
}

// ====== GİDERLER ======
function loadGider() {
  var t = document.getElementById('tarih').value;
  var ay = t ? t.substring(0, 7) : new Date().toISOString().substring(0, 7);
  document.getElementById('giderList').innerHTML = '<div class="empty">Yukleniyor...</div>';
  apiFetch('/api/gider?ay=' + ay).then(function(rows) {
    if (!rows.length) {
      document.getElementById('giderList').innerHTML = '<div class="empty">Bu ay gider yok</div>';
      return;
    }
    var toplam = 0;
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var g = rows[i];
      toplam += g.tutar || 0;
      html += '<div class="kart" style="padding:12px 14px;display:flex;justify-content:space-between;align-items:center">';
      html += '<div><div style="font-weight:600">' + g.ad + '</div><div style="font-size:12px;color:#a0a0a0">' + (g.tarih || '') + '</div></div>';
      html += '<div style="display:flex;align-items:center;gap:8px">';
      html += '<span style="font-weight:700;color:var(--er)">' + fmtTL(g.tutar) + '</span>';
      html += '<button onclick="giderSil(' + g.id + ')" style="background:none;border:none;color:var(--er);font-size:18px;cursor:pointer">&#128465;</button>';
      html += '</div></div>';
    }
    html += '<div class="ozet-kart" style="margin-top:8px"><div class="ozet-row"><span>Toplam Gider</span><span class="tutar er">' + fmtTL(toplam) + '</span></div></div>';
    document.getElementById('giderList').innerHTML = html;
  }).catch(function(e) {
    document.getElementById('giderList').innerHTML = '<div class="empty" style="color:var(--er)">Hata: ' + e.message + '</div>';
  });
}

function giderEkleModal() {
  var t = document.getElementById('tarih').value || new Date().toISOString().substring(0, 10);
  document.getElementById('modal-ici').innerHTML =
    '<button class="kapanis-btn" onclick="modalKapat()">&#10005;</button>' +
    '<h2>Gider Ekle</h2>' +
    '<div class="form-row"><label>Gider Adi</label><input type="text" id="g-ad" placeholder="Malzeme, Nakliye..."></div>' +
    '<div class="form-row"><label>Tutar (TL)</label><input type="number" id="g-tutar" placeholder="0" step="1"></div>' +
    '<div class="form-row"><label>Tarih</label><input type="text" id="g-tarih" value="' + t + '" placeholder="YYYY-MM-DD"></div>' +
    '<div class="form-row"><label>Aciklama</label><textarea id="g-acik" placeholder="Opsiyonel..."></textarea></div>' +
    '<button class="btn btn-ok" onclick="giderKaydet()">Kaydet</button>';
  document.getElementById('modal-arka').className = 'modal-arka';
}

function giderKaydet() {
  var ad = document.getElementById('g-ad').value.trim();
  var tutar = parseFloat(document.getElementById('g-tutar').value);
  if (!ad || isNaN(tutar)) { toast('Ad ve tutar gerekli'); return; }
  var tarih = document.getElementById('g-tarih').value || new Date().toISOString().substring(0, 10);
  apiFetch('/api/gider', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ad: ad, tutar: tutar, tarih: tarih, ay: tarih.substring(0, 7), aciklama: document.getElementById('g-acik').value})
  }).then(function() { modalKapat(); toast('Gider eklendi'); loadGider(); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function giderSil(id) {
  if (!confirm('Bu gideri sil?')) return;
  apiFetch('/api/gider/' + id, {method: 'DELETE'})
    .then(function() { toast('Silindi'); loadGider(); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

// ====== İŞÇİLER ======
function loadIsciler() {
  document.getElementById('isciList').innerHTML = '<div class="empty">Yukleniyor...</div>';
  apiFetch('/api/isci').then(function(rows) {
    if (!rows.length) {
      document.getElementById('isciList').innerHTML = '<div class="empty">Hic isci yok</div>';
      return;
    }
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var isc = rows[i];
      var ilk = isc.ad_soyad ? isc.ad_soyad.charAt(0).toUpperCase() : '?';
      html += '<div class="kart">';
      html += '<div class="kart-ust" onclick="isciDetay(' + isc.id + ')">';
      html += '<div class="avt">' + ilk + '</div>';
      html += '<div class="kart-bilgi">';
      html += '<div class="ad">' + isc.ad_soyad + '</div>';
      html += '<div class="alt">' + (isc.ustalik || '') + ' &bull; ' + fmtTL(isc.gunluk_ucret) + '/gun</div>';
      html += '</div><span style="color:#a0a0a0">&#9998;</span></div>';
      html += '<div class="kart-detay" id="idet-' + isc.id + '" style="display:none">';
      html += '<div class="form-row"><label>Ad Soyad</label><input type="text" id="iad-' + isc.id + '" value="' + isc.ad_soyad + '"></div>';
      html += '<div class="form-row"><label>Ustalik</label><select id="iust-' + isc.id + '">';
      var ustaliklar = ['Usta','Yamak','Duz Isci','Kalipci','Demirci','Siva Ustasi','Boya Ustasi','Elektrikci','Tesisatci','Forklift Operatoru','Vinccu'];
      for (var u = 0; u < ustaliklar.length; u++) {
        html += '<option value="' + ustaliklar[u] + '"' + (isc.ustalik === ustaliklar[u] ? ' selected' : '') + '>' + ustaliklar[u] + '</option>';
      }
      html += '</select></div>';
      html += '<div class="form-row"><label>Gunluk Ucret (TL)</label><input type="number" id="iucr-' + isc.id + '" value="' + (isc.gunluk_ucret || 0) + '" step="50"></div>';
      html += '<div class="form-row"><label>Telefon</label><input type="text" id="itel-' + isc.id + '" value="' + (isc.telefon || '') + '"></div>';
      html += '<button class="btn btn-ok" onclick="isciGuncelle(' + isc.id + ')">Guncelle</button>';
      html += '<button class="btn btn-er" style="margin-top:6px" onclick="isciSil(' + isc.id + ')">Sil</button>';
      html += '</div></div>';
    }
    document.getElementById('isciList').innerHTML = html;
  }).catch(function(e) {
    document.getElementById('isciList').innerHTML = '<div class="empty" style="color:var(--er)">Hata: ' + e.message + '</div>';
  });
}

function isciDetay(id) {
  var el = document.getElementById('idet-' + id);
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

function isciEkleModal() {
  var ustaliklar = ['Usta','Yamak','Duz Isci','Kalipci','Demirci','Siva Ustasi','Boya Ustasi','Elektrikci','Tesisatci','Forklift Operatoru','Vinccu'];
  var opts = '';
  for (var u = 0; u < ustaliklar.length; u++) {
    opts += '<option value="' + ustaliklar[u] + '">' + ustaliklar[u] + '</option>';
  }
  document.getElementById('modal-ici').innerHTML =
    '<button class="kapanis-btn" onclick="modalKapat()">&#10005;</button>' +
    '<h2>Isci Ekle</h2>' +
    '<div class="form-row"><label>Ad Soyad</label><input type="text" id="ni-ad" placeholder="Ad Soyad"></div>' +
    '<div class="form-row"><label>Ustalik</label><select id="ni-ust">' + opts + '</select></div>' +
    '<div class="form-row"><label>Gunluk Ucret (TL)</label><input type="number" id="ni-ucr" placeholder="0" step="50"></div>' +
    '<div class="form-row"><label>Telefon</label><input type="text" id="ni-tel" placeholder="05xx..."></div>' +
    '<button class="btn btn-ok" onclick="isciEkle()">Ekle</button>';
  document.getElementById('modal-arka').className = 'modal-arka';
}

function isciEkle() {
  var ad = document.getElementById('ni-ad').value.trim();
  if (!ad) { toast('Ad gerekli'); return; }
  apiFetch('/api/isci', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      ad_soyad: ad,
      ustalik: document.getElementById('ni-ust').value,
      gunluk_ucret: parseFloat(document.getElementById('ni-ucr').value) || 0,
      telefon: document.getElementById('ni-tel').value
    })
  }).then(function() { modalKapat(); toast('Isci eklendi'); loadIsciler(); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function isciGuncelle(id) {
  apiFetch('/api/isci/' + id, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      ad_soyad: document.getElementById('iad-' + id).value,
      ustalik: document.getElementById('iust-' + id).value,
      gunluk_ucret: parseFloat(document.getElementById('iucr-' + id).value) || 0,
      telefon: document.getElementById('itel-' + id).value
    })
  }).then(function() { toast('Guncellendi'); loadIsciler(); load(); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function isciSil(id) {
  if (!confirm('Bu isciyi ve tum puantaj kayitlarini sil?')) return;
  apiFetch('/api/isci/' + id, {method: 'DELETE'})
    .then(function() { toast('Silindi'); loadIsciler(); load(); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

// ====== AYARLAR ======
function loadAyarlar() {
  apiFetch('/api/ayarlar').then(function(d) {
    document.getElementById('ay-yemek').value = d.yemek_fiyati || '';
  }).catch(function(e) { toast('Hata: ' + e.message); });
  loadHatirlatmalar();
}

// ====== HATIRLATMA ======
function kapatBanner() {
  var b = document.getElementById('hat-banner');
  if (b) b.className = 'hatbanner-gizli';
}

function checkReminders() {
  apiFetch('/api/hatirlatma').then(function(list) {
    var bugun = new Date(); bugun.setHours(0,0,0,0);
    var yakin = [];
    for (var i = 0; i < list.length; i++) {
      var p = list[i].tarih.split('-');
      var dt = new Date(parseInt(p[0]), parseInt(p[1])-1, parseInt(p[2]));
      var fark = Math.ceil((dt - bugun) / 86400000);
      if (fark >= 0 && fark <= 7) {
        yakin.push({ad: list[i].ad, fark: fark, aciklama: list[i].aciklama || ''});
      }
    }
    var banner = document.getElementById('hat-banner');
    if (yakin.length) {
      var bhtml = '<div class="hatbanner-hdr">&#9888; Odeme Hatirlatmasi <button onclick="kapatBanner()" style="background:none;border:none;color:#ff9800;font-size:18px;cursor:pointer;padding:0">&#10005;</button></div>';
      for (var j = 0; j < yakin.length; j++) {
        var msg = yakin[j].fark === 0 ? 'BUGUN - ' : yakin[j].fark + ' gun kaldi: ';
        bhtml += '<div class="hatbanner-satir">' + msg + '<strong>' + yakin[j].ad + '</strong>' + (yakin[j].aciklama ? ' (' + yakin[j].aciklama + ')' : '') + '</div>';
      }
      banner.innerHTML = bhtml;
      banner.className = 'hatbanner';
    } else {
      banner.className = 'hatbanner-gizli';
    }
  }).catch(function() {});
}

function loadHatirlatmalar() {
  var el = document.getElementById('hatirlatma-list');
  if (!el) return;
  apiFetch('/api/hatirlatma').then(function(list) {
    if (!list.length) {
      el.innerHTML = '<div style="font-size:13px;color:#a0a0a0;text-align:center;padding:8px">Hatirlatma eklenmemis</div>';
      return;
    }
    var bugun = new Date(); bugun.setHours(0,0,0,0);
    var html = '';
    for (var i = 0; i < list.length; i++) {
      var p = list[i].tarih.split('-');
      var dt = new Date(parseInt(p[0]), parseInt(p[1])-1, parseInt(p[2]));
      var fark = Math.ceil((dt - bugun) / 86400000);
      var renk = fark < 0 ? 'var(--er)' : fark <= 7 ? 'var(--wr)' : 'var(--ok)';
      var etiket = fark < 0 ? 'Gecti' : fark === 0 ? 'Bugun' : fark + ' gun kaldi';
      html += '<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #ffffff0a">';
      html += '<div><div style="font-size:14px;font-weight:600">' + list[i].ad + '</div>';
      html += '<div style="font-size:12px;color:#a0a0a0">' + list[i].tarih + (list[i].aciklama ? ' - ' + list[i].aciklama : '') + '</div></div>';
      html += '<div style="display:flex;align-items:center;gap:8px">';
      html += '<span style="font-size:12px;font-weight:700;color:' + renk + '">' + etiket + '</span>';
      html += '<button onclick="hatirlatmaSil(' + list[i].id + ')" style="background:none;border:none;color:var(--er);font-size:16px;cursor:pointer">&#128465;</button>';
      html += '</div></div>';
    }
    el.innerHTML = html;
  }).catch(function(e) {
    if (el) el.innerHTML = '<div style="color:var(--er);font-size:13px">Yuklenemedi: ' + e.message + '</div>';
  });
}

function hatirlatmaEkleModal() {
  var t = new Date().toISOString().substring(0, 10);
  document.getElementById('modal-ici').innerHTML =
    '<button class="kapanis-btn" onclick="modalKapat()">&#10005;</button>' +
    '<h2>Hatirlatma Ekle</h2>' +
    '<div class="form-row"><label>Hatirlatma Adi</label><input type="text" id="hr-ad" placeholder="Isci Maasi, Kira, vb."></div>' +
    '<div class="form-row"><label>Odeme Tarihi</label><input type="date" id="hr-tarih" value="' + t + '" style="width:100%;padding:10px;border:none;border-radius:10px;background:var(--inp);color:var(--tx);font-size:15px"></div>' +
    '<div class="form-row"><label>Aciklama (Opsiyonel)</label><textarea id="hr-acik" placeholder="Notlar..."></textarea></div>' +
    '<button class="btn btn-ok" onclick="hatirlatmaKaydet()">Kaydet</button>';
  document.getElementById('modal-arka').className = 'modal-arka';
}

function hatirlatmaKaydet() {
  var ad = document.getElementById('hr-ad').value.trim();
  var tarih = document.getElementById('hr-tarih').value;
  if (!ad || !tarih) { toast('Ad ve tarih gerekli'); return; }
  apiFetch('/api/hatirlatma', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ad: ad, tarih: tarih, aciklama: document.getElementById('hr-acik').value})
  }).then(function() {
    modalKapat();
    toast('Hatirlatma eklendi!');
    loadHatirlatmalar();
    checkReminders();
  }).catch(function(e) { toast('Hata: ' + e.message); });
}

function hatirlatmaSil(id) {
  if (!confirm('Bu hatirlatmayi sil?')) return;
  apiFetch('/api/hatirlatma/' + id, {method: 'DELETE'})
    .then(function() { toast('Silindi'); loadHatirlatmalar(); checkReminders(); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function ayarKaydet() {
  var yf = parseFloat(document.getElementById('ay-yemek').value) || 0;
  apiFetch('/api/ayarlar', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({yemek_fiyati: yf})
  }).then(function() { toast('Ayarlar kaydedildi'); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

function yeniDonem() {
  if (!confirm('Tum odemeler sifirlanacak ve yeni donem baslatilacak. Emin misiniz?')) return;
  apiFetch('/api/odeme/tumunu-sil', {method: 'DELETE'})
    .then(function() { toast('Yeni donem baslatildi!'); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

// ====== MODAL ======
function modalKapat(e) {
  if (e && e.target !== document.getElementById('modal-arka')) return;
  document.getElementById('modal-arka').className = 'modal-arka gizli';
}

// ====== HAKEDİŞ ======
function loadHakedis() {
  var ay = document.getElementById('hakedisAy').value;
  if (!ay) { toast('Ay secin'); return; }
  document.getElementById('hakedisList').innerHTML = '<div class="empty">Yukleniyor...</div>';
  document.getElementById('hakedisOzet').innerHTML = '';
  apiFetch('/api/hakedis?ay=' + ay).then(function(d) {
    if (!d.kayitlar.length) {
      document.getElementById('hakedisList').innerHTML = '<div class="empty">Bu ay dokum kaydi bulunamadi.</div>';
      return;
    }
    var ozHtml = '<div class="ozet-kart">';
    ozHtml += '<h3>' + ay + ' Beton Ozeti</h3>';
    ozHtml += '<div class="ozet-row"><span>Toplam Beton</span><span class="tutar">' + fmt(d.toplam_m3) + ' m³</span></div>';
    ozHtml += '<div class="ozet-row"><span>Toplam Tutar</span><span class="tutar">' + fmtTL(d.toplam_tutar) + '</span></div>';
    ozHtml += '</div>';
    document.getElementById('hakedisOzet').innerHTML = ozHtml;
    var html = '';
    for (var i = 0; i < d.kayitlar.length; i++) {
      var k = d.kayitlar[i];
      var toplam = k.miktar_m3 * k.birim_fiyat;
      html += '<div class="kart" style="padding:12px 14px;margin-bottom:8px">';
      html += '<div style="display:flex;justify-content:space-between;align-items:center">';
      html += '<div style="flex:1">';
      html += '<div style="font-size:12px;color:#a0a0a0;margin-bottom:6px">' + k.tarih + (k.aciklama ? ' &bull; ' + k.aciklama : '') + '</div>';
      html += '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:15px">';
      html += '<strong style="color:var(--ok)">' + fmt(k.miktar_m3) + ' m³</strong>';
      html += '<span style="color:#a0a0a0">&times;</span>';
      html += '<strong>' + fmtTL(k.birim_fiyat) + '/m³</strong>';
      html += '<span style="color:#a0a0a0">=</span>';
      html += '<strong style="color:var(--pr);font-size:16px">' + fmtTL(toplam) + '</strong>';
      html += '</div></div>';
      html += '<button onclick="hakedisSil(' + k.id + ')" style="background:none;border:none;color:var(--er);font-size:20px;cursor:pointer;padding:4px;flex-shrink:0">&#128465;</button>';
      html += '</div></div>';
    }
    document.getElementById('hakedisList').innerHTML = html;
  }).catch(function(e) {
    document.getElementById('hakedisList').innerHTML = '<div class="empty" style="color:var(--er)">Hata: ' + e.message + '</div>';
  });
}

function hakedisEkleModal() {
  var t = document.getElementById('tarih').value || new Date().toISOString().substring(0, 10);
  document.getElementById('modal-ici').innerHTML =
    '<button class="kapanis-btn" onclick="modalKapat()">&#10005;</button>' +
    '<h2>Beton Dokumu Ekle</h2>' +
    '<div class="form-row"><label>Tarih</label><input type="text" id="hk-tarih" value="' + t + '" placeholder="YYYY-MM-DD"></div>' +
    '<div class="form-row"><label>Miktar (m³)</label><input type="number" id="hk-m3" placeholder="0.00" step="0.5" min="0"></div>' +
    '<div class="form-row"><label>Birim Fiyat (TL/m³)</label><input type="number" id="hk-fiyat" placeholder="0" step="50"></div>' +
    '<div class="form-row"><label>Aciklama (Opsiyonel)</label><textarea id="hk-acik" placeholder="Notlar..."></textarea></div>' +
    '<button class="btn btn-ok" onclick="hakedisKaydet()">Kaydet</button>';
  document.getElementById('modal-arka').className = 'modal-arka';
}

function hakedisKaydet() {
  var tarih = document.getElementById('hk-tarih').value;
  var m3 = parseFloat(document.getElementById('hk-m3').value);
  var fiyat = parseFloat(document.getElementById('hk-fiyat').value);
  if (!tarih || isNaN(m3) || m3 <= 0 || isNaN(fiyat) || fiyat <= 0) {
    toast('Tarih, miktar ve birim fiyat gerekli');
    return;
  }
  apiFetch('/api/hakedis', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      tarih: tarih,
      miktar_m3: m3,
      birim_fiyat: fiyat,
      aciklama: document.getElementById('hk-acik').value
    })
  }).then(function() {
    modalKapat();
    toast('Kaydedildi!');
    document.getElementById('hakedisAy').value = tarih.substring(0, 7);
    loadHakedis();
  }).catch(function(e) { toast('Hata: ' + e.message); });
}

function hakedisSil(id) {
  if (!confirm('Bu kaydi sil?')) return;
  apiFetch('/api/hakedis/' + id, {method: 'DELETE'})
    .then(function() { toast('Silindi'); loadHakedis(); })
    .catch(function(e) { toast('Hata: ' + e.message); });
}

// ====== BASLANGIC ======
bugun();
checkReminders();
var simdi = new Date();
var yil = simdi.getFullYear();
var ay = simdi.getMonth() + 1;
document.getElementById('aylikAy').value = yil + '-' + (ay < 10 ? '0' + ay : ay);
</script>
</body>
</html>'''


# ===== ROUTES =====
@app.route('/')
def index():
    import time
    if 'v' not in request.args:
        from flask import redirect
        return redirect('/?v=' + str(int(time.time())))
    from flask import make_response
    resp = make_response(render_template_string(HTML_TEMPLATE))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/api/isci', methods=['GET', 'POST'])
def api_isci():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == 'POST':
        d = request.json
        c.execute('INSERT INTO isci (ad_soyad, ustalik, gunluk_ucret, telefon) VALUES (?,?,?,?)',
                  (d.get('ad_soyad'), d.get('ustalik','Duz Isci'), d.get('gunluk_ucret',0), d.get('telefon')))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

    c.execute('SELECT * FROM isci WHERE aktif=1 ORDER BY gunluk_ucret DESC, ad_soyad')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/isci/<int:isci_id>', methods=['PUT'])
def update_isci(isci_id):
    d = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE isci SET ad_soyad=?, ustalik=?, gunluk_ucret=?, telefon=? WHERE id=?',
              (d.get('ad_soyad'), d.get('ustalik'), d.get('gunluk_ucret', 0), d.get('telefon', ''), isci_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Isci guncellendi'})

@app.route('/api/isci/<int:isci_id>', methods=['DELETE'])
def delete_isci(isci_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM puantaj WHERE isci_id=?', (isci_id,))
    c.execute('DELETE FROM odeme WHERE isci_id=?', (isci_id,))
    c.execute('DELETE FROM isci WHERE id=?', (isci_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Isci silindi'})

@app.route('/api/odeme', methods=['GET', 'POST'])
def api_odeme():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == 'POST':
        d = request.json
        c.execute('INSERT INTO odeme (isci_id, hafta_bitis, miktar, aciklama) VALUES (?,?,?,?)',
                  (d.get('isci_id'), date.today().isoformat(), d.get('miktar', 0), d.get('aciklama', '')))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Odeme kaydedildi'})

    hafta_bitis = request.args.get('hafta_bitis')
    if hafta_bitis:
        c.execute('SELECT * FROM odeme WHERE hafta_bitis=?', (hafta_bitis,))
    else:
        c.execute('SELECT * FROM odeme ORDER BY tarih DESC LIMIT 50')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/odeme/<int:odeme_id>', methods=['DELETE'])
def delete_odeme(odeme_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM odeme WHERE id=?', (odeme_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Odeme silindi'})

@app.route('/api/odeme/tumunu-sil', methods=['DELETE'])
def delete_all_odemeler():
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?,?)',
              ('donem_baslangici', today))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Yeni donem baslatildi'})

@app.route('/api/puantaj', methods=['GET', 'POST'])
def api_puantaj():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == 'POST':
        d = request.json
        tarih = d.get('tarih', date.today().isoformat())
        c.execute('SELECT id FROM puantaj WHERE isci_id=? AND tarih=?', (d.get('isci_id'), tarih))
        ex = c.fetchone()
        if ex:
            c.execute('UPDATE puantaj SET giris_saati=?, cikis_saati=?, calisma_durumu=?, mesai_saat=?, yapilan_is=? WHERE id=?',
                      (d.get('giris_saati'), d.get('cikis_saati'), d.get('calisma_durumu','tam_gun'), d.get('mesai_saat',0), d.get('yapilan_is'), ex['id']))
        else:
            c.execute('INSERT INTO puantaj (isci_id, tarih, giris_saati, cikis_saati, calisma_durumu, mesai_saat, yapilan_is) VALUES (?,?,?,?,?,?,?)',
                      (d.get('isci_id'), tarih, d.get('giris_saati'), d.get('cikis_saati'), d.get('calisma_durumu','tam_gun'), d.get('mesai_saat',0), d.get('yapilan_is')))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Kaydedildi'})

    tarih = request.args.get('tarih', date.today().isoformat())
    c.execute('SELECT p.*, i.ad_soyad, i.ustalik FROM puantaj p JOIN isci i ON p.isci_id=i.id WHERE p.tarih=?', (tarih,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/puantaj/sil', methods=['DELETE'])
def api_puantaj_sil():
    isci_id = request.args.get('isci_id')
    tarih = request.args.get('tarih')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM puantaj WHERE isci_id=? AND tarih=?', (isci_id, tarih))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/ayarlar', methods=['GET', 'POST'])
def api_ayarlar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if request.method == 'POST':
        d = request.json
        for k, v in d.items():
            c.execute('INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?,?)', (k, str(v)))
            if k == 'yemek_fiyati':
                try:
                    fiyat = float(v)
                    if fiyat > 0:
                        today = date.today().isoformat()
                        c.execute('INSERT OR REPLACE INTO yemek_fiyat_gecmisi (fiyat, gecerli_tarih) VALUES (?,?)',
                                  (fiyat, today))
                except (ValueError, TypeError):
                    pass
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    c.execute('SELECT * FROM ayarlar')
    rows = {r['anahtar']: r['deger'] for r in c.fetchall()}
    conn.close()
    return jsonify(rows)

@app.route('/api/ozet/gunluk')
def api_gunluk():
    tarih = request.args.get('tarih', date.today().isoformat())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM isci WHERE aktif=1')
    toplam = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT isci_id) FROM puantaj WHERE tarih=? AND calisma_durumu NOT IN ('izinli','gelmedi')", (tarih,))
    gelen = c.fetchone()[0]
    c.execute('SELECT SUM(mesai_saat) FROM puantaj WHERE tarih=?', (tarih,))
    mesai = c.fetchone()[0] or 0
    conn.close()
    return jsonify({'gelen_isci': gelen, 'gelmeyen_isci': toplam-gelen, 'toplam_mesai_saat': mesai})

@app.route('/api/ozet/haftalik')
def api_haftalik():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT deger FROM ayarlar WHERE anahtar='donem_baslangici'")
    db_row = c.fetchone()
    donem_bas = db_row['deger'] if db_row and db_row['deger'] else '2000-01-01'
    c.execute('''SELECT i.id, i.ad_soyad, i.gunluk_ucret,
                 SUM(CASE WHEN p.calisma_durumu='bir_bucuk_gun' THEN 1.5 WHEN p.calisma_durumu='tam_gun' THEN 1 WHEN p.calisma_durumu='yarim_gun' THEN 0.5 ELSE 0 END) as tum_yevmiye,
                 SUM(COALESCE(p.mesai_saat, 0)) as tum_mesai
                 FROM isci i LEFT JOIN puantaj p ON i.id=p.isci_id AND p.tarih >= ?
                 WHERE i.aktif=1 GROUP BY i.id ORDER BY i.gunluk_ucret DESC''', (donem_bas,))
    rows = c.fetchall()
    c.execute('''SELECT isci_id, SUM(miktar) as toplam_odeme FROM odeme WHERE tarih >= ? GROUP BY isci_id''', (donem_bas,))
    odeme_map = {r['isci_id']: r['toplam_odeme'] for r in c.fetchall()}
    c.execute('''SELECT o1.id, o1.isci_id, o1.miktar FROM odeme o1
                 INNER JOIN (SELECT isci_id, MAX(id) as max_id FROM odeme WHERE tarih >= ? GROUP BY isci_id) o2
                 ON o1.id = o2.max_id''', (donem_bas,))
    son_odeme_map = {r['isci_id']: {'id': r['id'], 'miktar': r['miktar']} for r in c.fetchall()}
    c.execute("SELECT deger FROM ayarlar WHERE anahtar='yemek_fiyati'")
    yf_row = c.fetchone()
    yemek_fiyati = float(yf_row['deger']) if yf_row and yf_row['deger'] else 0
    c.execute("""
        SELECT p.tarih,
               (SELECT fiyat FROM yemek_fiyat_gecmisi
                WHERE gecerli_tarih <= p.tarih
                ORDER BY gecerli_tarih DESC LIMIT 1) as gun_fiyati
        FROM puantaj p
        WHERE p.calisma_durumu IN ('tam_gun','bir_bucuk_gun','yarim_gun')
        AND p.tarih >= ?
    """, (donem_bas,))
    gun_rows = c.fetchall()
    kisi_gun = len(gun_rows)
    yemek_maliyeti_detay = round(sum((r['gun_fiyati'] or yemek_fiyati) for r in gun_rows), 2)
    c.execute("SELECT COALESCE(SUM(miktar),0) as toplam FROM yemek_odeme WHERE tarih >= ?", (donem_bas,))
    yemek_odenen = float(c.fetchone()['toplam'] or 0)
    c.execute("SELECT id, miktar FROM yemek_odeme WHERE tarih >= ? ORDER BY id DESC LIMIT 1", (donem_bas,))
    son_yo = c.fetchone()
    c.execute("SELECT COALESCE(SUM(miktar),0) as toplam FROM civi_gider WHERE tarih >= ?", (donem_bas,))
    civi_toplam = float(c.fetchone()['toplam'] or 0)
    c.execute("SELECT COALESCE(SUM(miktar),0) as toplam FROM civi_odeme WHERE tarih >= ?", (donem_bas,))
    civi_odenen = float(c.fetchone()['toplam'] or 0)
    c.execute("SELECT id, miktar FROM civi_odeme WHERE tarih >= ? ORDER BY id DESC LIMIT 1", (donem_bas,))
    son_co = c.fetchone()
    c.execute("SELECT id, miktar FROM civi_gider WHERE tarih >= ? ORDER BY id DESC LIMIT 1", (donem_bas,))
    son_cg = c.fetchone()
    conn.close()
    isciler = []
    toplam_kalan = 0
    for r in rows:
        ucret = r['gunluk_ucret'] or 0
        yev = r['tum_yevmiye'] or 0
        mes = r['tum_mesai'] or 0
        mesai_ucret = (ucret / 8 * 1.5) * mes if ucret > 0 else 0
        hakedis = (yev * ucret) + mesai_ucret
        odenen = odeme_map.get(r['id'], 0) or 0
        kalan = max(round(hakedis - odenen, 2), 0)
        toplam_kalan += kalan
        son = son_odeme_map.get(r['id'])
        kalan_yevmiye = round(kalan / ucret, 1) if ucret > 0 and kalan > 0 else 0
        isciler.append({
            'id': r['id'],
            'ad_soyad': r['ad_soyad'],
            'kalan_yevmiye': kalan_yevmiye,
            'kalan': kalan,
            'son_odeme_id': son['id'] if son else None,
            'son_odeme_miktar': son['miktar'] if son else 0
        })
    yemek_maliyeti = yemek_maliyeti_detay
    return jsonify({
        'isciler': isciler,
        'toplam_kalan': round(toplam_kalan, 2),
        'yemek_fiyati': yemek_fiyati,
        'yemek_kisi_gun': kisi_gun,
        'yemek_maliyeti': yemek_maliyeti,
        'yemek_odenen': round(yemek_odenen, 2),
        'yemek_kalan': round(max(yemek_maliyeti - yemek_odenen, 0), 2),
        'son_yemek_odeme_id': son_yo['id'] if son_yo else None,
        'son_yemek_odeme_miktar': son_yo['miktar'] if son_yo else 0,
        'civi_toplam': round(civi_toplam, 2),
        'civi_odenen': round(civi_odenen, 2),
        'civi_kalan': round(max(civi_toplam - civi_odenen, 0), 2),
        'son_civi_odeme_id': son_co['id'] if son_co else None,
        'son_civi_odeme_miktar': son_co['miktar'] if son_co else 0,
        'son_civi_gider_id': son_cg['id'] if son_cg else None,
        'son_civi_gider_miktar': son_cg['miktar'] if son_cg else 0
    })

@app.route('/api/ozet/aylik')
def api_aylik():
    ay = request.args.get('ay', date.today().strftime('%Y-%m'))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('SELECT * FROM isci WHERE aktif=1 ORDER BY gunluk_ucret DESC, ad_soyad')
    isciler = [dict(r) for r in c.fetchall()]

    c.execute('''SELECT isci_id,
                 SUM(CASE WHEN calisma_durumu='bir_bucuk_gun' THEN 1.5
                          WHEN calisma_durumu='tam_gun' THEN 1
                          WHEN calisma_durumu='yarim_gun' THEN 0.5 ELSE 0 END) as aylik_yevmiye,
                 SUM(COALESCE(mesai_saat, 0)) as aylik_mesai
                 FROM puantaj WHERE strftime('%Y-%m', tarih)=?
                 GROUP BY isci_id''', (ay,))
    puantaj_map = {r['isci_id']: {'yevmiye': r['aylik_yevmiye'] or 0, 'mesai': r['aylik_mesai'] or 0}
                   for r in c.fetchall()}

    c.execute("SELECT isci_id, tarih, calisma_durumu FROM puantaj WHERE strftime('%Y-%m', tarih)=?", (ay,))
    gun_map = {}
    for row in c.fetchall():
        iid = row['isci_id']
        gun = int(row['tarih'].split('-')[2])
        if iid not in gun_map:
            gun_map[iid] = {}
        gun_map[iid][str(gun)] = row['calisma_durumu']

    c.execute("SELECT deger FROM ayarlar WHERE anahtar='yemek_fiyati'")
    yf_row = c.fetchone()
    yemek_fiyati = float(yf_row['deger']) if yf_row and yf_row['deger'] else 0
    c.execute("""SELECT COUNT(*) as t FROM puantaj
                 WHERE calisma_durumu IN ('tam_gun','bir_bucuk_gun','yarim_gun')
                 AND strftime('%Y-%m', tarih)=?""", (ay,))
    aylik_kisi_gun = c.fetchone()['t'] or 0
    c.execute("SELECT COALESCE(SUM(miktar),0) as toplam FROM civi_gider WHERE strftime('%Y-%m', tarih)=?", (ay,))
    aylik_civi = float(c.fetchone()['toplam'] or 0)
    conn.close()

    isci_list = []
    toplam_hakedis = 0.0

    for i in isciler:
        isci_id = i['id']
        ucret = i['gunluk_ucret'] or 0
        p = puantaj_map.get(isci_id, {'yevmiye': 0, 'mesai': 0})
        yev = p['yevmiye']
        mes = p['mesai']
        mesai_ucret = (ucret / 8 * 1.5) * mes if ucret > 0 else 0
        hakedis = round((yev * ucret) + mesai_ucret, 2)
        toplam_hakedis += hakedis
        isci_list.append({
            'id': isci_id,
            'ad_soyad': i['ad_soyad'],
            'ustalik': i['ustalik'] or 'Isci',
            'gunluk_ucret': ucret,
            'aylik_yevmiye': round(yev, 1),
            'aylik_hakedis': hakedis,
            'gunler': gun_map.get(isci_id, {})
        })

    return jsonify({
        'ay': ay,
        'isciler': isci_list,
        'toplam_hakedis': round(toplam_hakedis, 2),
        'yemek_fiyati': yemek_fiyati,
        'yemek_kisi_gun': aylik_kisi_gun,
        'yemek_maliyeti': round(aylik_kisi_gun * yemek_fiyati, 2),
        'civi_maliyeti': round(aylik_civi, 2)
    })

@app.route('/api/gider', methods=['GET', 'POST'])
def api_gider():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == 'POST':
        d = request.json
        ay = d.get('ay', date.today().strftime('%Y-%m'))
        tarih = d.get('tarih', date.today().isoformat())
        c.execute('INSERT INTO ek_gider (ad, tutar, ay, tarih, aciklama) VALUES (?,?,?,?,?)',
                  (d.get('ad'), d.get('tutar',0), ay, tarih, d.get('aciklama')))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

    ay = request.args.get('ay', date.today().strftime('%Y-%m'))
    c.execute('SELECT * FROM ek_gider WHERE ay=? ORDER BY tarih DESC', (ay,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/gider/<int:gider_id>', methods=['DELETE'])
def api_gider_sil(gider_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM ek_gider WHERE id=?', (gider_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/yemek/ode', methods=['POST'])
def api_yemek_ode():
    d = request.json
    miktar = float(d.get('miktar', 0))
    if miktar <= 0:
        return jsonify({'error': 'Gecersiz miktar'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO yemek_odeme (miktar, tarih, aciklama) VALUES (?,?,?)',
              (miktar, date.today().isoformat(), d.get('aciklama', 'Yemek odemesi')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/yemek/odeme/<int:odeme_id>', methods=['DELETE'])
def api_yemek_odeme_sil(odeme_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM yemek_odeme WHERE id=?', (odeme_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/civi/gider', methods=['GET', 'POST'])
def api_civi_gider():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if request.method == 'POST':
        d = request.json
        miktar = float(d.get('miktar', 0))
        if miktar <= 0:
            conn.close()
            return jsonify({'error': 'Gecersiz miktar'}), 400
        c.execute('INSERT INTO civi_gider (miktar, tarih, aciklama) VALUES (?,?,?)',
                  (miktar, date.today().isoformat(), d.get('aciklama', 'Civi alimi')))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    ay = request.args.get('ay', date.today().strftime('%Y-%m'))
    c.execute("SELECT * FROM civi_gider WHERE strftime('%Y-%m', tarih)=? ORDER BY tarih DESC", (ay,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/civi/gider/<int:gider_id>', methods=['DELETE'])
def api_civi_gider_sil(gider_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM civi_gider WHERE id=?', (gider_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/civi/ode', methods=['POST'])
def api_civi_ode():
    d = request.json
    miktar = float(d.get('miktar', 0))
    if miktar <= 0:
        return jsonify({'error': 'Gecersiz miktar'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO civi_odeme (miktar, tarih, aciklama) VALUES (?,?,?)',
              (miktar, date.today().isoformat(), d.get('aciklama', 'Civi odemesi')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/civi/odeme/<int:odeme_id>', methods=['DELETE'])
def api_civi_odeme_sil(odeme_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM civi_odeme WHERE id=?', (odeme_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/rapor/haftalik')
def api_rapor_haftalik():
    hafta = request.args.get('hafta', '')
    if not hafta:
        return jsonify({'error': 'Hafta parametresi gerekli'}), 400
    try:
        pzt = datetime.strptime(hafta + '-1', '%G-W%V-%u').date()
    except ValueError:
        return jsonify({'error': 'Gecersiz hafta formati'}), 400
    paz = pzt + timedelta(days=6)
    gunler = [pzt + timedelta(days=i) for i in range(7)]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('SELECT * FROM isci WHERE aktif=1 ORDER BY gunluk_ucret DESC, ad_soyad')
    isciler = [dict(r) for r in c.fetchall()]

    c.execute('SELECT * FROM puantaj WHERE tarih >= ? AND tarih <= ?', (pzt.isoformat(), paz.isoformat()))
    puantaj_rows = c.fetchall()
    pmap = {}
    for p in puantaj_rows:
        pmap[(p['isci_id'], p['tarih'])] = p['calisma_durumu']

    c.execute('''SELECT i.id,
                 SUM(CASE WHEN p.calisma_durumu='bir_bucuk_gun' THEN 1.5 WHEN p.calisma_durumu='tam_gun' THEN 1 WHEN p.calisma_durumu='yarim_gun' THEN 0.5 ELSE 0 END) as tum_yevmiye,
                 SUM(COALESCE(p.mesai_saat, 0)) as tum_mesai
                 FROM isci i LEFT JOIN puantaj p ON i.id=p.isci_id
                 WHERE i.aktif=1 GROUP BY i.id''')
    hakedis_map = {r['id']: {'yevmiye': r['tum_yevmiye'] or 0, 'mesai': r['tum_mesai'] or 0} for r in c.fetchall()}

    c.execute('SELECT isci_id, SUM(miktar) as toplam FROM odeme GROUP BY isci_id')
    odeme_map = {r['isci_id']: r['toplam'] or 0 for r in c.fetchall()}

    c.execute('SELECT * FROM ek_gider WHERE tarih >= ? AND tarih <= ? ORDER BY tarih', (pzt.isoformat(), paz.isoformat()))
    giderler = [dict(r) for r in c.fetchall()]
    conn.close()

    isci_list = []
    for i in isciler:
        isci_id = i['id']
        ucret = i['gunluk_ucret'] or 0
        gun_durumlari = [pmap.get((isci_id, g.isoformat()), None) for g in gunler]
        haftalik_yev = sum(
            1.5 if d == 'bir_bucuk_gun' else 1.0 if d == 'tam_gun' else 0.5 if d == 'yarim_gun' else 0
            for d in gun_durumlari if d
        )
        hk = hakedis_map.get(isci_id, {'yevmiye': 0, 'mesai': 0})
        mesai_ucret = (ucret / 8 * 1.5) * hk['mesai'] if ucret > 0 else 0
        toplam_hakedis = (hk['yevmiye'] * ucret) + mesai_ucret
        odenen = odeme_map.get(isci_id, 0)
        kalan = max(round(toplam_hakedis - odenen, 2), 0)
        isci_list.append({
            'id': isci_id,
            'ad_soyad': i['ad_soyad'],
            'ustalik': i['ustalik'] or 'Isci',
            'gunluk_ucret': ucret,
            'gunler': [d if d else '-' for d in gun_durumlari],
            'haftalik_yevmiye': round(haftalik_yev, 1),
            'haftalik_hakedis': round(haftalik_yev * ucret, 2),
            'toplam_odenen': round(odenen, 2),
            'toplam_kalan': kalan
        })

    toplam_gider = round(sum(g['tutar'] for g in giderler), 2)
    return jsonify({
        'hafta_baslangic': pzt.strftime('%d.%m.%Y'),
        'hafta_bitis': paz.strftime('%d.%m.%Y'),
        'isciler': isci_list,
        'haftalik_giderler': giderler,
        'toplam_gider': toplam_gider
    })


@app.route('/api/hakedis', methods=['GET', 'POST'])
def api_hakedis():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == 'POST':
        d = request.json
        c.execute(
            'INSERT INTO beton_hakedis (tarih, miktar_m3, birim_fiyat, aciklama) VALUES (?,?,?,?)',
            (d.get('tarih', date.today().isoformat()), d.get('miktar_m3', 0),
             d.get('birim_fiyat', 0), d.get('aciklama', ''))
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True})

    ay = request.args.get('ay', date.today().strftime('%Y-%m'))
    c.execute("SELECT * FROM beton_hakedis WHERE strftime('%Y-%m', tarih)=? ORDER BY tarih", (ay,))
    kayitlar = [dict(r) for r in c.fetchall()]
    conn.close()

    toplam_m3 = round(sum(k['miktar_m3'] for k in kayitlar), 2)
    toplam_tutar = round(sum(k['miktar_m3'] * k['birim_fiyat'] for k in kayitlar), 2)

    return jsonify({
        'ay': ay,
        'kayitlar': kayitlar,
        'toplam_m3': toplam_m3,
        'toplam_tutar': toplam_tutar
    })


@app.route('/api/hakedis/<int:hakedis_id>', methods=['DELETE'])
def api_hakedis_sil(hakedis_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM beton_hakedis WHERE id=?', (hakedis_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/hatirlatma', methods=['GET', 'POST'])
def api_hatirlatma():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if request.method == 'POST':
        d = request.json
        ad = d.get('ad', '').strip()
        tarih = d.get('tarih', '')
        if not ad or not tarih:
            conn.close()
            return jsonify({'error': 'Ad ve tarih gerekli'}), 400
        c.execute('INSERT INTO odeme_hatirlatma (ad, tarih, aciklama) VALUES (?,?,?)',
                  (ad, tarih, d.get('aciklama', '')))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    c.execute('SELECT * FROM odeme_hatirlatma ORDER BY tarih ASC')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route('/api/hatirlatma/<int:hat_id>', methods=['DELETE'])
def api_hatirlatma_sil(hat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM odeme_hatirlatma WHERE id=?', (hat_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True)
