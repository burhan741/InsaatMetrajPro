"""
Puantaj API - PythonAnywhere versiyonu
Tek dosya, bağımsız çalışır
"""

from flask import Flask, request, jsonify, render_template_string
from functools import wraps
from datetime import datetime, date, timedelta
import sqlite3
import os
import secrets

app = Flask(__name__)

# Ayarlar - KENDİ ŞİFRENİ YAZ
API_USERNAME = "santiye"
API_PASSWORD = "2024"  # Değiştir!

# Veritabanı
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
        yapilan_is TEXT
    )''')
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
    conn.commit()
    conn.close()

init_db()

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if auth and auth.username == API_USERNAME and auth.password == API_PASSWORD:
            return f(*args, **kwargs)
        return jsonify({'error': 'Yetkisiz'}), 401
    return decorated

# ===== HTML ŞABLONU =====
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <title>Şantiye Puantaj</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --primary: #e94560; --bg: #1a1a2e; --card: #16213e;
            --input: #0f3460; --text: #eaeaea; --success: #00d26a;
            --warning: #ffc107; --danger: #ff6b6b;
        }
        body { font-family: -apple-system, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; padding-bottom: 80px; }
        .header { background: var(--card); padding: 14px 6px; position: sticky; top: 0; z-index: 100; }
        .header h1 { font-size: 22px; }
        .header h1::before { content: "👷 "; }
        .date-row { margin-top: 12px; display: flex; gap: 10px; }
        .date-row input { flex: 1; padding: 12px; border: none; border-radius: 10px; background: var(--input); color: var(--text); font-size: 16px; }
        .date-row button { width: 44px; height: 44px; border: none; border-radius: 10px; background: var(--input); color: var(--text); font-size: 18px; }
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding: 10px 6px; }
        .stat { background: var(--card); border-radius: 12px; padding: 14px; text-align: center; }
        .stat .num { font-size: 26px; font-weight: 700; color: var(--primary); }
        .stat .lbl { font-size: 11px; color: #a0a0a0; }
        .stat.s .num { color: var(--success); }
        .stat.w .num { color: var(--warning); }
        .tabs { display: flex; padding: 0 6px; gap: 6px; }
        .tab { padding: 10px 20px; border: none; border-radius: 20px; background: var(--card); color: #a0a0a0; font-size: 14px; }
        .tab.active { background: var(--primary); color: white; }
        .section { display: none; padding: 6px 0; }
        .section.active { display: block; }
        .section-pad { padding: 6px 6px; }
        .card { background: var(--card); border-radius: 10px; padding: 12px 8px; margin: 0 0 5px 0; display: flex; align-items: center; gap: 8px; width: 100%; }
        .info { flex: 1; min-width: 0; }
        .name { font-weight: 700; font-size: 17px; }
        .role { font-size: 12px; color: #a0a0a0; }
        .btns { display: flex; gap: 5px; flex-shrink: 0; }
        .sbtn { width: 44px; height: 44px; border: none; border-radius: 12px; font-size: 18px; flex-shrink: 0; }
        .sbtn.t { background: var(--success); }
        .sbtn.ob { background: #4dc9f6; font-size: 14px; font-weight: 700; }
        .sbtn.y { background: var(--warning); font-size: 14px; font-weight: 700; }
        .sbtn.x { background: var(--danger); }
        .sbtn.sel { transform: scale(1.15); box-shadow: 0 0 0 3px rgba(255,255,255,0.3); }
        .form { background: var(--card); border-radius: 16px; padding: 20px; margin-bottom: 16px; }
        .form h3 { margin-bottom: 16px; }
        .field { margin-bottom: 14px; }
        .field label { display: block; font-size: 13px; color: #a0a0a0; margin-bottom: 6px; }
        .field input, .field select { width: 100%; padding: 14px; border: none; border-radius: 10px; background: var(--input); color: var(--text); font-size: 16px; }
        .btn { width: 100%; padding: 16px; border: none; border-radius: 12px; font-size: 16px; font-weight: 600; background: linear-gradient(135deg, var(--primary), #c73e54); color: white; }
        .nav { position: fixed; bottom: 0; left: 0; right: 0; background: var(--card); display: flex; justify-content: space-around; padding: 10px 0 25px; }
        .nav-item { display: flex; flex-direction: column; align-items: center; gap: 4px; background: none; border: none; color: #a0a0a0; font-size: 11px; }
        .nav-item.active { color: var(--primary); }
        .nav-item .icon { font-size: 22px; }
        .toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%) translateY(-100px); background: var(--card); padding: 14px 24px; border-radius: 10px; z-index: 300; transition: transform 0.3s; border-left: 4px solid var(--success); }
        .toast.show { transform: translateX(-50%) translateY(0); }
        .empty { text-align: center; padding: 40px; color: #a0a0a0; }
        .rapor-tbl { width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 10px; }
        .rapor-tbl th { background: #0f3460; color: #eaeaea; padding: 6px 4px; text-align: center; border: 1px solid #333; }
        .rapor-tbl td { padding: 6px 4px; text-align: center; border: 1px solid #2a2a4a; }
        .rapor-tbl tr:nth-child(even) td { background: #12183a; }
        .rapor-tbl .isci-ad { text-align: left; font-weight: 600; white-space: nowrap; }
        .rapor-tbl .kalan-col { color: #e94560; font-weight: bold; }
        .rapor-tbl .gider-row td { color: #ffc107; }
        .d-tam { color: #00d26a; font-weight: bold; }
        .d-15 { color: #4dc9f6; font-weight: bold; }
        .d-05 { color: #ffc107; }
        .d-izin { color: #ff6b6b; }
        .d-yok { color: #555; }
        .rapor-baslik { font-size: 15px; font-weight: 700; margin-bottom: 4px; }
        .rapor-alt { font-size: 12px; color: #a0a0a0; margin-bottom: 12px; }
        @media print {
            body { background: white !important; color: black !important; padding: 0 !important; }
            .header, .stats, .tabs, .nav, .toast, #modal, #isciModal { display: none !important; }
            .section { display: none !important; }
            #sec-rapor { display: block !important; padding: 0 !important; }
            .no-print { display: none !important; }
            .rapor-tbl th { background: #333 !important; color: white !important; }
            .rapor-tbl td { border: 1px solid #999 !important; color: black !important; }
            .rapor-tbl tr:nth-child(even) td { background: #f5f5f5 !important; }
            .rapor-tbl .kalan-col { color: #c00 !important; }
            .rapor-baslik { color: black !important; }
            .rapor-alt { color: #555 !important; }
            .d-tam { color: #006600 !important; }
            .d-15 { color: #004499 !important; }
            .d-05 { color: #886600 !important; }
            .d-izin { color: #cc0000 !important; }
            .d-yok { color: #999 !important; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Şantiye Puantaj</h1>
        <div class="date-row">
            <input type="date" id="tarih" onchange="load()">
            <button onclick="chgDate(-1)">◀</button>
            <button onclick="chgDate(1)">▶</button>
        </div>
    </div>
    <div class="stats">
        <div class="stat s"><div class="num" id="sGelen">-</div><div class="lbl">Gelen</div></div>
        <div class="stat w"><div class="num" id="sYok">-</div><div class="lbl">Gelmeyen</div></div>
        <div class="stat"><div class="num" id="sMesai">-</div><div class="lbl">Mesai</div></div>
    </div>
    <div class="tabs">
        <button class="tab active" data-sec="puantaj" onclick="showSec('puantaj')">Puantaj</button>
        <button class="tab" data-sec="isci" onclick="showSec('isci')">İşçiler</button>
        <button class="tab" data-sec="ozet" onclick="showSec('ozet')">Özet</button>
        <button class="tab" data-sec="gider" onclick="showSec('gider')">Giderler</button>
        <button class="tab" data-sec="rapor" onclick="showSec('rapor')">Rapor</button>
    </div>
    <div class="section active" id="sec-puantaj"><div id="pList" class="empty" style="padding:0 4px;">Yükleniyor...</div></div>
    <div class="section section-pad" id="sec-isci">
        <div class="form">
            <h3>➕ Yeni İşçi</h3>
            <div class="field"><label>Ad Soyad</label><input type="text" id="iAd" placeholder="Ahmet Yılmaz"></div>
            <div class="field"><label>Ustalık</label>
                <select id="iUst"><option>Düz İşçi</option><option>Kalıpçı</option><option>Demirci</option><option>Usta</option><option>Operatör</option><option>Elektrikçi</option><option>Tesisatçı</option></select>
            </div>
            <div class="field"><label>Günlük Ücret</label><input type="number" id="iUcret" placeholder="1500"></div>
            <div class="field"><label>Telefon</label><input type="tel" id="iTel" placeholder="05XX XXX XX XX"></div>
            <button class="btn" onclick="addIsci()">Ekle</button>
        </div>
        <div id="iList"></div>
    </div>
    <!-- İşçi Düzenle Modal -->
    <div id="isciModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);z-index:200;align-items:flex-end;">
        <div style="background:#1a1a2e;width:100%;border-radius:20px 20px 0 0;padding:20px;max-height:80vh;overflow-y:auto;">
            <div style="display:flex;justify-content:space-between;margin-bottom:20px;">
                <h3>✏️ İşçi Düzenle</h3>
                <button onclick="closeIsciModal()" style="width:36px;height:36px;border:none;border-radius:50%;background:#0f3460;color:#eaeaea;font-size:20px;">×</button>
            </div>
            <input type="hidden" id="editIsciId">
            <div class="field"><label>Ad Soyad</label><input type="text" id="editAd"></div>
            <div class="field"><label>Ustalık</label>
                <select id="editUst"><option>Düz İşçi</option><option>Kalıpçı</option><option>Demirci</option><option>Usta</option><option>Operatör</option><option>Elektrikçi</option><option>Tesisatçı</option></select>
            </div>
            <div class="field"><label>Günlük Ücret (TL)</label><input type="number" id="editUcret"></div>
            <div class="field"><label>Telefon</label><input type="tel" id="editTel"></div>
            <button class="btn" onclick="saveIsci()">Kaydet</button>
            <button onclick="deleteIsci()" style="width:100%;padding:14px;border:none;border-radius:12px;background:#ff6b6b;color:white;font-size:15px;font-weight:600;margin-top:10px;">🗑️ İşçiyi Sil</button>
        </div>
    </div>
    <div class="section section-pad" id="sec-ozet">
        <div class="form" style="text-align:center;">
            <h3>💰 Toplam Ödenecek</h3>
            <div id="genelKalan" style="font-size:32px;font-weight:bold;color:#e94560;margin:10px 0;">0 ₺</div>
            <div style="font-size:12px;color:#a0a0a0;">Tüm işçilerin kümülatif bakiyesi</div>
        </div>
        <div class="form">
            <div id="ozetTbl"></div>
        </div>
        <div style="text-align:center;margin-top:20px;">
            <button onclick="resetOdemeler()" style="background:#ff6b6b;border:none;color:white;padding:10px 20px;border-radius:10px;font-size:13px;">Tüm Ödemeleri Sıfırla</button>
        </div>
    </div>
    <div class="section section-pad" id="sec-gider">
        <div class="form">
            <h3>💸 Ek Gider Ekle</h3>
            <div class="field"><label>Gider Adı</label><input type="text" id="gAd" placeholder="Yakıt, Yemek, Malzeme..."></div>
            <div class="field"><label>Tutar (TL)</label><input type="number" id="gTutar" placeholder="500"></div>
            <div class="field"><label>Tarih</label><input type="date" id="gTarih"></div>
            <div class="field"><label>Açıklama</label><input type="text" id="gAcik" placeholder="Opsiyonel"></div>
            <button class="btn" onclick="addGider()">Gider Ekle</button>
        </div>
        <div class="form">
            <h3>📅 Aylık Giderler</h3>
            <div class="field"><label>Ay Seç</label>
                <input type="month" id="gAy" onchange="loadGiderler()">
            </div>
            <div id="gList"></div>
            <div style="margin-top:15px;padding-top:15px;border-top:1px solid #333;display:flex;justify-content:space-between;">
                <span style="font-weight:bold;">TOPLAM:</span>
                <span id="gToplam" style="color:#e94560;font-weight:bold;font-size:18px;">0 ₺</span>
            </div>
        </div>
    </div>
    <div class="nav">
        <button class="nav-item active" data-sec="puantaj" onclick="showSec('puantaj')"><span class="icon">📋</span>Puantaj</button>
        <button class="nav-item" data-sec="isci" onclick="showSec('isci')"><span class="icon">👷</span>İşçiler</button>
        <button class="nav-item" data-sec="ozet" onclick="showSec('ozet')"><span class="icon">📊</span>Özet</button>
        <button class="nav-item" data-sec="gider" onclick="showSec('gider')"><span class="icon">💸</span>Giderler</button>
        <button class="nav-item" data-sec="rapor" onclick="showSec('rapor')"><span class="icon">📄</span>Rapor</button>
    </div>
    <div class="section section-pad" id="sec-rapor">
        <div class="form no-print">
            <h3>📄 Haftalık Rapor</h3>
            <div class="field" style="margin-top:12px;">
                <label>Hafta Seç</label>
                <input type="week" id="rHafta" style="width:100%;padding:12px;border:none;border-radius:10px;background:#0f3460;color:#eaeaea;font-size:16px;">
            </div>
            <button class="btn" onclick="loadRapor()" style="margin-bottom:10px;">Raporu Getir</button>
            <button onclick="printRapor()" style="width:100%;padding:14px;border:none;border-radius:12px;background:#0f3460;color:#eaeaea;font-size:15px;font-weight:600;">🖨️ Yazdır / PDF Kaydet</button>
        </div>
        <div id="raporArea"></div>
    </div>
    <div class="toast" id="toast"></div>
    <div id="modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);z-index:200;align-items:flex-end;">
        <div style="background:#1a1a2e;width:100%;border-radius:20px 20px 0 0;padding:20px;max-height:80vh;overflow-y:auto;">
            <div style="display:flex;justify-content:space-between;margin-bottom:20px;">
                <h3 id="mTitle">Puantaj Düzenle</h3>
                <button onclick="closeModal()" style="width:36px;height:36px;border:none;border-radius:50%;background:#0f3460;color:#eaeaea;font-size:20px;">×</button>
            </div>
            <input type="hidden" id="mIsciId">
            <div class="field"><label>Çalışma Durumu</label>
                <select id="mDurum"><option value="tam_gun">Tam Gün</option><option value="bir_bucuk_gun">1.5 Gün</option><option value="yarim_gun">Yarım Gün</option><option value="izinli">İzinli/Gelmedi</option></select>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                <div class="field"><label>Giriş</label><input type="time" id="mGiris" value="08:00"></div>
                <div class="field"><label>Çıkış</label><input type="time" id="mCikis" value="17:00"></div>
            </div>
            <div class="field"><label>Mesai (Saat)</label><input type="number" id="mMesai" value="0" min="0" max="8"></div>
            <div class="field"><label>Yapılan İş</label><input type="text" id="mIs" placeholder="Bugün yapılan iş..."></div>
            <button class="btn" onclick="savePuantaj()">Kaydet</button>
            <button onclick="delPuantaj()" style="width:100%;padding:14px;border:none;border-radius:12px;background:#ff6b6b;color:white;font-size:15px;margin-top:10px;">🗑️ Bu Günü Sil</button>
        </div>
    </div>
<script>
const h = () => ({ 'Content-Type': 'application/json', 'Authorization': 'Basic ' + btoa('{{ username }}:{{ password }}') });
document.getElementById('tarih').value = new Date().toISOString().split('T')[0];
document.getElementById('gAy').value = new Date().toISOString().slice(0,7);
document.getElementById('gTarih').value = new Date().toISOString().split('T')[0];
load();
loadGiderler();

function chgDate(d) {
    const i = document.getElementById('tarih');
    const dt = new Date(i.value);
    dt.setDate(dt.getDate() + d);
    i.value = dt.toISOString().split('T')[0];
    load();
}

async function load() {
    const t = document.getElementById('tarih').value;
    try {
        const [st, is, pu] = await Promise.all([
            fetch('/api/ozet/gunluk?tarih='+t, {headers:h()}).then(r=>r.json()),
            fetch('/api/isci', {headers:h()}).then(r=>r.json()),
            fetch('/api/puantaj?tarih='+t, {headers:h()}).then(r=>r.json())
        ]);
        document.getElementById('sGelen').textContent = st.gelen_isci||0;
        document.getElementById('sYok').textContent = st.gelmeyen_isci||0;
        document.getElementById('sMesai').textContent = st.toplam_mesai_saat||0;

        const pm = {};
        pu.forEach(p => pm[p.isci_id] = p);

        if(is.length === 0) {
            document.getElementById('pList').innerHTML = '<div class="empty">👷 Henüz işçi yok</div>';
        } else {
            is.sort((a,b) => (b.gunluk_ucret||0) - (a.gunluk_ucret||0));
            document.getElementById('pList').innerHTML = is.map(i => {
                const p = pm[i.id];
                const s = p?.calisma_durumu || '';
                return `<div class="card" onclick="openModal(${i.id},'${i.ad_soyad}','${s}','${p?.giris_saati||'08:00'}','${p?.cikis_saati||'17:00'}',${p?.mesai_saat||0},'${p?.yapilan_is||''}')">
                    <div class="info"><div class="name">${i.ad_soyad}</div><div class="role">${i.ustalik||'İşçi'} • ${i.gunluk_ucret||0} TL</div></div>
                    <div class="btns">
                        <button class="sbtn t ${s==='tam_gun'?'sel':''}" onclick="event.stopPropagation();qp(${i.id},'tam_gun')">✓</button>
                        <button class="sbtn ob ${s==='bir_bucuk_gun'?'sel':''}" onclick="event.stopPropagation();qp(${i.id},'bir_bucuk_gun')">1.5</button>
                        <button class="sbtn y ${s==='yarim_gun'?'sel':''}" onclick="event.stopPropagation();qp(${i.id},'yarim_gun')">0.5</button>
                        <button class="sbtn x ${s==='izinli'?'sel':''}" onclick="event.stopPropagation();qp(${i.id},'izinli')">✗</button>
                    </div>
                </div>`;
            }).join('');
        }

        document.getElementById('iList').innerHTML = is.map(i => {
            return `<div class="card" onclick="openIsciModal(${i.id},'${i.ad_soyad.replace(/'/g,"\\\\'")}','${i.ustalik||'Düz İşçi'}',${i.gunluk_ucret||0},'${i.telefon||''}')">
                <div class="info"><div class="name">${i.ad_soyad}</div><div class="role">${i.ustalik} • ${i.gunluk_ucret||0} TL${i.telefon?' • '+i.telefon:''}</div></div>
                <div style="color:#a0a0a0;font-size:18px;">✏️</div>
            </div>`;
        }).join('');

        loadOzet();
    } catch(e) { console.error(e); }
}

async function qp(id, dur) {
    const t = document.getElementById('tarih').value;
    await fetch('/api/puantaj', {
        method: 'POST', headers: h(),
        body: JSON.stringify({isci_id:id, tarih:t, calisma_durumu:dur, giris_saati:dur!=='izinli'?'08:00':null, cikis_saati:dur==='tam_gun'?'17:00':dur==='bir_bucuk_gun'?'21:00':dur==='yarim_gun'?'12:00':null})
    });
    toast('Kaydedildi');
    load();
}

function openModal(id, ad, durum, giris, cikis, mesai, is) {
    document.getElementById('mIsciId').value = id;
    document.getElementById('mTitle').textContent = ad + ' - Düzenle';
    document.getElementById('mDurum').value = durum || 'tam_gun';
    document.getElementById('mGiris').value = giris || '08:00';
    document.getElementById('mCikis').value = cikis || '17:00';
    document.getElementById('mMesai').value = mesai || 0;
    document.getElementById('mIs').value = is || '';
    document.getElementById('modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

async function savePuantaj() {
    const id = document.getElementById('mIsciId').value;
    const t = document.getElementById('tarih').value;
    await fetch('/api/puantaj', {
        method: 'POST', headers: h(),
        body: JSON.stringify({
            isci_id: parseInt(id),
            tarih: t,
            calisma_durumu: document.getElementById('mDurum').value,
            giris_saati: document.getElementById('mGiris').value,
            cikis_saati: document.getElementById('mCikis').value,
            mesai_saat: parseFloat(document.getElementById('mMesai').value) || 0,
            yapilan_is: document.getElementById('mIs').value
        })
    });
    toast('Kaydedildi');
    closeModal();
    load();
}

async function delPuantaj() {
    if(!confirm('Bu günün puantajını silmek istediğinize emin misiniz?')) return;
    const id = document.getElementById('mIsciId').value;
    const t = document.getElementById('tarih').value;
    await fetch('/api/puantaj/sil?isci_id='+id+'&tarih='+t, {method:'DELETE', headers:h()});
    toast('Silindi');
    closeModal();
    load();
}

async function addIsci() {
    const ad = document.getElementById('iAd').value.trim();
    if(!ad) { toast('Ad gerekli',1); return; }
    await fetch('/api/isci', {
        method: 'POST', headers: h(),
        body: JSON.stringify({ad_soyad:ad, ustalik:document.getElementById('iUst').value, gunluk_ucret:parseFloat(document.getElementById('iUcret').value)||0, telefon:document.getElementById('iTel').value})
    });
    document.getElementById('iAd').value = '';
    document.getElementById('iUcret').value = '';
    document.getElementById('iTel').value = '';
    toast('İşçi eklendi');
    load();
}

function openIsciModal(id, ad, ust, ucret, tel) {
    document.getElementById('editIsciId').value = id;
    document.getElementById('editAd').value = ad;
    document.getElementById('editUst').value = ust;
    document.getElementById('editUcret').value = ucret;
    document.getElementById('editTel').value = tel;
    document.getElementById('isciModal').style.display = 'flex';
}

function closeIsciModal() {
    document.getElementById('isciModal').style.display = 'none';
}

async function saveIsci() {
    const id = document.getElementById('editIsciId').value;
    const ad = document.getElementById('editAd').value.trim();
    if(!ad) { toast('Ad gerekli',1); return; }
    await fetch('/api/isci/'+id, {
        method: 'PUT', headers: h(),
        body: JSON.stringify({
            ad_soyad: ad,
            ustalik: document.getElementById('editUst').value,
            gunluk_ucret: parseFloat(document.getElementById('editUcret').value)||0,
            telefon: document.getElementById('editTel').value
        })
    });
    toast('İşçi güncellendi');
    closeIsciModal();
    load();
}

async function deleteIsci() {
    if(!confirm('Bu işçiyi silmek istediğinize emin misiniz? Tüm puantaj kayıtları da silinecek!')) return;
    const id = document.getElementById('editIsciId').value;
    await fetch('/api/isci/'+id, {method:'DELETE', headers:h()});
    toast('İşçi silindi');
    closeIsciModal();
    load();
}

async function loadOzet() {
    const r = await fetch('/api/ozet/haftalik', {headers:h()}).then(r=>r.json());
    document.getElementById('genelKalan').textContent = r.toplam_kalan.toLocaleString() + ' ₺';
    let html = '<table style="width:100%;font-size:13px;border-collapse:collapse;">';
    html += '<tr style="color:#a0a0a0;border-bottom:1px solid #333"><td style="padding:8px 4px">İşçi</td><td style="padding:8px 4px">Yevmiye</td><td style="padding:8px 4px">Kalan</td><td style="padding:8px 4px"></td></tr>';
    r.isciler.forEach(i => {
        html += `<tr style="border-bottom:1px solid #222">
            <td style="padding:8px 4px">${i.ad_soyad}</td>
            <td style="padding:8px 4px;font-weight:bold">${i.kalan_yevmiye}</td>
            <td style="padding:8px 4px;color:${i.kalan>0?'#e94560':'#00d26a'};font-weight:bold">${i.kalan.toLocaleString()} ₺</td>
            <td style="padding:8px 4px">
                <button onclick="odemeYap(${i.id},'${i.ad_soyad.replace(/'/g,"\\\\'")}',${i.kalan})" style="background:#0f3460;border:none;color:#eaeaea;padding:6px 10px;border-radius:8px;font-size:12px;">💰</button>${i.son_odeme_id ? ' <button onclick="delOdeme('+i.son_odeme_id+')" style="background:none;border:none;color:#ff6b6b;font-size:14px;cursor:pointer;" title="Son odemeyi geri al ('+i.son_odeme_miktar.toLocaleString()+' TL)">↩</button>' : ''}
            </td>
        </tr>`;
    });
    html += '</table>';
    document.getElementById('ozetTbl').innerHTML = html;
}

async function odemeYap(isciId, isciAd, kalan) {
    const miktar = prompt(isciAd + ' - Kalan: ' + kalan.toLocaleString() + ' ₺\\nÖdeme miktarını girin:', kalan);
    if(miktar === null) return;
    const m = parseFloat(miktar);
    if(isNaN(m) || m <= 0) { toast('Geçerli bir miktar girin',1); return; }
    await fetch('/api/odeme', {
        method: 'POST', headers: h(),
        body: JSON.stringify({isci_id: isciId, miktar: m, aciklama: 'Odeme'})
    });
    toast(isciAd + ' - ' + m.toLocaleString() + ' ₺ ödeme kaydedildi');
    loadOzet();
}

async function delOdeme(id) {
    if(!confirm('Bu ödemeyi geri almak istediğinize emin misiniz?')) return;
    await fetch('/api/odeme/'+id, {method:'DELETE', headers:h()});
    toast('Ödeme geri alındı');
    loadOzet();
}

async function resetOdemeler() {
    if(!confirm('TÜM ödemeler silinecek. Emin misiniz?')) return;
    try {
        const resp = await fetch('/api/odeme/tumunu-sil', {method:'DELETE', headers:h()});
        if (!resp.ok) { toast('Sıfırlama başarısız: ' + resp.status, 1); return; }
        toast('Tüm ödemeler sıfırlandı');
        await loadOzet();
    } catch(e) {
        toast('Bağlantı hatası', 1);
    }
}

function showSec(name) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.tab,.nav-item').forEach(t => t.classList.remove('active'));
    document.getElementById('sec-'+name).classList.add('active');
    document.querySelectorAll('[data-sec="'+name+'"]').forEach(el => el.classList.add('active'));
}

function toast(msg, err) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.style.borderLeftColor = err ? '#ff6b6b' : '#00d26a';
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2500);
}

async function loadGiderler() {
    const ay = document.getElementById('gAy').value;
    try {
        const r = await fetch('/api/gider?ay='+ay, {headers:h()}).then(r=>r.json());
        let toplam = 0;
        if(r.length === 0) {
            document.getElementById('gList').innerHTML = '<div class="empty">Bu ay gider yok</div>';
        } else {
            document.getElementById('gList').innerHTML = r.map(g => {
                toplam += g.tutar;
                return `<div class="card">
                    <div class="info">
                        <div class="name">${g.ad}</div>
                        <div class="role">${g.aciklama||''} • ${g.tarih}</div>
                    </div>
                    <div style="font-weight:bold;color:#e94560">${g.tutar.toLocaleString()} ₺</div>
                    <button onclick="delGider(${g.id})" style="background:#ff6b6b;border:none;color:white;padding:8px 12px;border-radius:8px;">✗</button>
                </div>`;
            }).join('');
        }
        document.getElementById('gToplam').textContent = toplam.toLocaleString() + ' ₺';
    } catch(e) { console.error(e); }
}

async function addGider() {
    const ad = document.getElementById('gAd').value.trim();
    const tutar = document.getElementById('gTutar').value;
    if(!ad || !tutar) { toast('Ad ve tutar gerekli',1); return; }
    const ay = document.getElementById('gAy').value;
    await fetch('/api/gider', {
        method: 'POST', headers: h(),
        body: JSON.stringify({ad:ad, tutar:parseFloat(tutar), ay:ay, tarih:document.getElementById('gTarih').value, aciklama:document.getElementById('gAcik').value})
    });
    document.getElementById('gAd').value = '';
    document.getElementById('gTutar').value = '';
    document.getElementById('gAcik').value = '';
    toast('Gider eklendi');
    loadGiderler();
}

async function delGider(id) {
    if(!confirm('Silmek istediğinize emin misiniz?')) return;
    await fetch('/api/gider/'+id, {method:'DELETE', headers:h()});
    toast('Silindi');
    loadGiderler();
}

// Bugünkü haftayı varsayılan olarak seç
(function() {
    const now = new Date();
    const y = now.getFullYear();
    const start = new Date(y, 0, 1);
    const diff = now - start + ((start.getDay() || 7) - 1) * 86400000;
    const week = Math.ceil(diff / (7 * 86400000));
    document.getElementById('rHafta').value = y + '-W' + String(week).padStart(2,'0');
})();

async function loadRapor() {
    const hafta = document.getElementById('rHafta').value;
    if(!hafta) { toast('Hafta seçiniz', 1); return; }
    document.getElementById('raporArea').innerHTML = '<div class="empty">Yükleniyor...</div>';
    try {
        const r = await fetch('/api/rapor/haftalik?hafta=' + hafta, {headers:h()}).then(r=>r.json());
        if(r.error) { toast(r.error, 1); return; }
        const gunKisalt = ['Pzt','Sal','Çar','Per','Cum','Cmt','Paz'];
        const durumLabel = (d) => {
            if(!d || d==='-') return '<span class="d-yok">-</span>';
            if(d==='tam_gun') return '<span class="d-tam">✓</span>';
            if(d==='bir_bucuk_gun') return '<span class="d-15">1.5</span>';
            if(d==='yarim_gun') return '<span class="d-05">0.5</span>';
            if(d==='izinli') return '<span class="d-izin">✗</span>';
            return '<span class="d-yok">-</span>';
        };
        let html = '<div style="padding:4px">';
        html += '<div class="rapor-baslik">Şantiye Haftalık Raporu</div>';
        html += '<div class="rapor-alt">' + r.hafta_baslangic + ' — ' + r.hafta_bitis + '</div>';
        html += '<div style="overflow-x:auto"><table class="rapor-tbl">';
        html += '<tr><th class="isci-ad">İşçi / Usta</th>';
        gunKisalt.forEach(g => html += '<th>' + g + '</th>');
        html += '<th>Yev.</th><th>Hakediş</th><th>Ödenen</th><th class="kalan-col">Kalan</th></tr>';
        r.isciler.forEach(i => {
            html += '<tr>';
            html += '<td class="isci-ad">' + i.ad_soyad + '<br><span style="font-size:10px;color:#a0a0a0">' + i.ustalik + ' • ' + (i.gunluk_ucret||0).toLocaleString() + '₺</span></td>';
            i.gunler.forEach(d => html += '<td>' + durumLabel(d) + '</td>');
            html += '<td style="font-weight:bold">' + (i.haftalik_yevmiye||0) + '</td>';
            html += '<td>' + (i.haftalik_hakedis||0).toLocaleString() + '₺</td>';
            html += '<td style="color:#00d26a">' + (i.toplam_odenen||0).toLocaleString() + '₺</td>';
            html += '<td class="kalan-col">' + (i.toplam_kalan||0).toLocaleString() + '₺</td>';
            html += '</tr>';
        });
        // İşçilik toplam satırı
        const toplamKalan = r.isciler.reduce((s,i)=>s+(i.toplam_kalan||0),0);
        const toplamHakedis = r.isciler.reduce((s,i)=>s+(i.haftalik_hakedis||0),0);
        html += '<tr style="border-top:2px solid #444;font-weight:bold">';
        html += '<td class="isci-ad" colspan="8">HAFTALIK İŞÇİLİK TOPLAMI</td>';
        html += '<td></td><td>' + toplamHakedis.toLocaleString() + '₺</td><td></td>';
        html += '<td class="kalan-col">' + toplamKalan.toLocaleString() + '₺</td></tr>';
        html += '</table></div>';
        // Giderler
        if(r.haftalik_giderler && r.haftalik_giderler.length > 0) {
            html += '<div style="margin-top:16px;font-weight:700;font-size:13px">📦 Haftalık Giderler</div>';
            html += '<table class="rapor-tbl" style="margin-top:6px"><tr><th>Gider</th><th>Açıklama</th><th>Tarih</th><th>Tutar</th></tr>';
            r.haftalik_giderler.forEach(g => {
                html += '<tr class="gider-row"><td style="text-align:left">' + g.ad + '</td><td>' + (g.aciklama||'-') + '</td><td>' + g.tarih + '</td><td>' + (g.tutar||0).toLocaleString() + '₺</td></tr>';
            });
            html += '<tr style="font-weight:bold"><td colspan="3" style="text-align:right">Toplam Gider:</td><td style="color:#ffc107">' + (r.toplam_gider||0).toLocaleString() + '₺</td></tr>';
            html += '</table>';
        } else {
            html += '<div style="margin-top:12px;font-size:12px;color:#a0a0a0">Bu hafta ek gider girilmemiş.</div>';
        }
        // Genel toplam
        const genelToplam = toplamKalan + (r.toplam_gider||0);
        html += '<div style="margin-top:16px;background:#0f3460;border-radius:10px;padding:14px;display:flex;justify-content:space-between;align-items:center">';
        html += '<span style="font-weight:700">GENEL TOPLAM ÖDENECEK</span>';
        html += '<span style="font-size:20px;font-weight:700;color:#e94560">' + genelToplam.toLocaleString() + ' ₺</span></div>';
        html += '<div style="margin-top:8px;font-size:10px;color:#555;text-align:right">Oluşturma: ' + new Date().toLocaleDateString('tr-TR') + '</div>';
        html += '</div>';
        document.getElementById('raporArea').innerHTML = html;
    } catch(e) {
        toast('Rapor yüklenemedi', 1);
        document.getElementById('raporArea').innerHTML = '';
    }
}

function printRapor() {
    if(!document.getElementById('raporArea').innerHTML) {
        toast('Önce raporu getirin', 1);
        return;
    }
    window.print();
}
</script>
</body>
</html>
'''

# ===== ROUTES =====
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, username=API_USERNAME, password=API_PASSWORD)

@app.route('/api/isci', methods=['GET', 'POST'])
@require_auth
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

    c.execute('SELECT * FROM isci WHERE aktif=1 ORDER BY ad_soyad')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/isci/<int:isci_id>', methods=['PUT'])
@require_auth
def update_isci(isci_id):
    d = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE isci SET ad_soyad=?, ustalik=?, gunluk_ucret=?, telefon=? WHERE id=?',
              (d.get('ad_soyad'), d.get('ustalik'), d.get('gunluk_ucret', 0), d.get('telefon', ''), isci_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'İşçi güncellendi'})

@app.route('/api/isci/<int:isci_id>', methods=['DELETE'])
@require_auth
def delete_isci(isci_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM puantaj WHERE isci_id=?', (isci_id,))
    c.execute('DELETE FROM odeme WHERE isci_id=?', (isci_id,))
    c.execute('DELETE FROM isci WHERE id=?', (isci_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'İşçi silindi'})

@app.route('/api/odeme', methods=['GET', 'POST'])
@require_auth
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
        return jsonify({'success': True, 'message': 'Ödeme kaydedildi'})

    hafta_bitis = request.args.get('hafta_bitis')
    if hafta_bitis:
        c.execute('SELECT * FROM odeme WHERE hafta_bitis=?', (hafta_bitis,))
    else:
        c.execute('SELECT * FROM odeme ORDER BY tarih DESC LIMIT 50')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/odeme/<int:odeme_id>', methods=['DELETE'])
@require_auth
def delete_odeme(odeme_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM odeme WHERE id=?', (odeme_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Ödeme silindi'})

@app.route('/api/odeme/tumunu-sil', methods=['DELETE'])
@require_auth
def delete_all_odemeler():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM odeme')
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Tüm ödemeler silindi'})

@app.route('/api/puantaj', methods=['GET', 'POST'])
@require_auth
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
@require_auth
def api_puantaj_sil():
    isci_id = request.args.get('isci_id')
    tarih = request.args.get('tarih')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM puantaj WHERE isci_id=? AND tarih=?', (isci_id, tarih))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/ozet/gunluk')
@require_auth
def api_gunluk():
    tarih = request.args.get('tarih', date.today().isoformat())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM isci WHERE aktif=1')
    toplam = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT isci_id) FROM puantaj WHERE tarih=? AND calisma_durumu NOT IN ('izinli')", (tarih,))
    gelen = c.fetchone()[0]
    c.execute('SELECT SUM(mesai_saat) FROM puantaj WHERE tarih=?', (tarih,))
    mesai = c.fetchone()[0] or 0
    conn.close()
    return jsonify({'gelen_isci': gelen, 'gelmeyen_isci': toplam-gelen, 'toplam_mesai_saat': mesai})

@app.route('/api/ozet/haftalik')
@require_auth
def api_haftalik():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Tüm zamanlar hakediş (kümülatif)
    c.execute('''SELECT i.id, i.ad_soyad, i.gunluk_ucret,
                 SUM(CASE WHEN p.calisma_durumu='bir_bucuk_gun' THEN 1.5 WHEN p.calisma_durumu='tam_gun' THEN 1 WHEN p.calisma_durumu='yarim_gun' THEN 0.5 ELSE 0 END) as tum_yevmiye,
                 SUM(COALESCE(p.mesai_saat, 0)) as tum_mesai
                 FROM isci i LEFT JOIN puantaj p ON i.id=p.isci_id
                 WHERE i.aktif=1 GROUP BY i.id''')
    rows = c.fetchall()
    # Tüm zamanlar ödemeler
    c.execute('''SELECT isci_id, SUM(miktar) as toplam_odeme FROM odeme GROUP BY isci_id''')
    odeme_map = {r['isci_id']: r['toplam_odeme'] for r in c.fetchall()}
    # Son ödeme bilgisi (geri alma için)
    c.execute('''SELECT o1.id, o1.isci_id, o1.miktar FROM odeme o1
                 INNER JOIN (SELECT isci_id, MAX(id) as max_id FROM odeme GROUP BY isci_id) o2
                 ON o1.id = o2.max_id''')
    son_odeme_map = {r['isci_id']: {'id': r['id'], 'miktar': r['miktar']} for r in c.fetchall()}
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
    return jsonify({'isciler': isciler, 'toplam_kalan': round(toplam_kalan, 2)})

@app.route('/api/gider', methods=['GET', 'POST'])
@require_auth
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
@require_auth
def api_gider_sil(gider_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM ek_gider WHERE id=?', (gider_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/rapor/haftalik')
@require_auth
def api_rapor_haftalik():
    hafta = request.args.get('hafta', '')
    if not hafta:
        return jsonify({'error': 'Hafta parametresi gerekli (örn: 2026-W11)'}), 400
    try:
        pzt = datetime.strptime(hafta + '-1', '%G-W%V-%u').date()
    except ValueError:
        return jsonify({'error': 'Geçersiz hafta formatı'}), 400
    paz = pzt + timedelta(days=6)
    gunler = [pzt + timedelta(days=i) for i in range(7)]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Tüm aktif işçiler
    c.execute('SELECT * FROM isci WHERE aktif=1 ORDER BY ad_soyad')
    isciler = [dict(r) for r in c.fetchall()]

    # Haftalık puantaj kayıtları
    c.execute('SELECT * FROM puantaj WHERE tarih >= ? AND tarih <= ?', (pzt.isoformat(), paz.isoformat()))
    puantaj_rows = c.fetchall()
    # isci_id + tarih → durum
    pmap = {}
    for p in puantaj_rows:
        pmap[(p['isci_id'], p['tarih'])] = p['calisma_durumu']

    # Tüm zamanlar hakediş (kümülatif) ve ödemeler
    c.execute('''SELECT i.id,
                 SUM(CASE WHEN p.calisma_durumu='bir_bucuk_gun' THEN 1.5 WHEN p.calisma_durumu='tam_gun' THEN 1 WHEN p.calisma_durumu='yarim_gun' THEN 0.5 ELSE 0 END) as tum_yevmiye,
                 SUM(COALESCE(p.mesai_saat, 0)) as tum_mesai
                 FROM isci i LEFT JOIN puantaj p ON i.id=p.isci_id
                 WHERE i.aktif=1 GROUP BY i.id''')
    hakedis_map = {r['id']: {'yevmiye': r['tum_yevmiye'] or 0, 'mesai': r['tum_mesai'] or 0} for r in c.fetchall()}

    c.execute('SELECT isci_id, SUM(miktar) as toplam FROM odeme GROUP BY isci_id')
    odeme_map = {r['isci_id']: r['toplam'] or 0 for r in c.fetchall()}

    # Haftalık giderler
    c.execute('SELECT * FROM ek_gider WHERE tarih >= ? AND tarih <= ? ORDER BY tarih', (pzt.isoformat(), paz.isoformat()))
    giderler = [dict(r) for r in c.fetchall()]
    conn.close()

    isci_list = []
    for i in isciler:
        isci_id = i['id']
        ucret = i['gunluk_ucret'] or 0
        # Bu haftaki günlük durumlar
        gun_durumlari = [pmap.get((isci_id, g.isoformat()), None) for g in gunler]
        # Haftalık yevmiye (sadece bu hafta)
        haftalik_yev = sum(
            1.5 if d == 'bir_bucuk_gun' else 1.0 if d == 'tam_gun' else 0.5 if d == 'yarim_gun' else 0
            for d in gun_durumlari if d
        )
        # Kümülatif hakediş
        hk = hakedis_map.get(isci_id, {'yevmiye': 0, 'mesai': 0})
        mesai_ucret = (ucret / 8 * 1.5) * hk['mesai'] if ucret > 0 else 0
        toplam_hakedis = (hk['yevmiye'] * ucret) + mesai_ucret
        odenen = odeme_map.get(isci_id, 0)
        kalan = max(round(toplam_hakedis - odenen, 2), 0)
        isci_list.append({
            'id': isci_id,
            'ad_soyad': i['ad_soyad'],
            'ustalik': i['ustalik'] or 'İşçi',
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


if __name__ == '__main__':
    app.run(debug=True)
