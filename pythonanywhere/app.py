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
        .header { background: var(--card); padding: 20px 16px; position: sticky; top: 0; z-index: 100; }
        .header h1 { font-size: 22px; }
        .header h1::before { content: "👷 "; }
        .date-row { margin-top: 12px; display: flex; gap: 10px; }
        .date-row input { flex: 1; padding: 12px; border: none; border-radius: 10px; background: var(--input); color: var(--text); font-size: 16px; }
        .date-row button { width: 44px; height: 44px; border: none; border-radius: 10px; background: var(--input); color: var(--text); font-size: 18px; }
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; padding: 16px; }
        .stat { background: var(--card); border-radius: 12px; padding: 14px; text-align: center; }
        .stat .num { font-size: 26px; font-weight: 700; color: var(--primary); }
        .stat .lbl { font-size: 11px; color: #a0a0a0; }
        .stat.s .num { color: var(--success); }
        .stat.w .num { color: var(--warning); }
        .tabs { display: flex; padding: 0 16px; gap: 8px; }
        .tab { padding: 10px 20px; border: none; border-radius: 20px; background: var(--card); color: #a0a0a0; font-size: 14px; }
        .tab.active { background: var(--primary); color: white; }
        .section { display: none; padding: 16px; }
        .section.active { display: block; }
        .card { background: var(--card); border-radius: 14px; padding: 14px; margin-bottom: 10px; display: flex; align-items: center; gap: 12px; }
        .avatar { width: 46px; height: 46px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), #c73e54); display: flex; align-items: center; justify-content: center; font-weight: 700; }
        .info { flex: 1; }
        .name { font-weight: 600; }
        .role { font-size: 13px; color: #a0a0a0; }
        .btns { display: flex; gap: 6px; }
        .sbtn { width: 38px; height: 38px; border: none; border-radius: 10px; font-size: 16px; }
        .sbtn.t { background: var(--success); }
        .sbtn.y { background: var(--warning); }
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
        <button class="tab active" onclick="showSec('puantaj',this)">Puantaj</button>
        <button class="tab" onclick="showSec('isci',this)">İşçiler</button>
        <button class="tab" onclick="showSec('ozet',this)">Özet</button>
        <button class="tab" onclick="showSec('gider',this)">Giderler</button>
    </div>
    <div class="section active" id="sec-puantaj"><div id="pList" class="empty">Yükleniyor...</div></div>
    <div class="section" id="sec-isci">
        <div class="form">
            <h3>➕ Yeni İşçi</h3>
            <div class="field"><label>Ad Soyad</label><input type="text" id="iAd" placeholder="Ahmet Yılmaz"></div>
            <div class="field"><label>Ustalık</label>
                <select id="iUst"><option>Düz İşçi</option><option>Kalıpçı</option><option>Demirci</option><option>Usta</option><option>Operatör</option></select>
            </div>
            <div class="field"><label>Günlük Ücret</label><input type="number" id="iUcret" placeholder="1500"></div>
            <button class="btn" onclick="addIsci()">Ekle</button>
        </div>
        <div id="iList"></div>
    </div>
    <div class="section" id="sec-ozet">
        <div class="form"><h3>📊 Haftalık Özet</h3><div id="ozetTbl"></div></div>
    </div>
    <div class="section" id="sec-gider">
        <div class="form">
            <h3>💸 Ek Gider Ekle</h3>
            <div class="field"><label>Gider Adı</label><input type="text" id="gAd" placeholder="Yakıt, Yemek, Malzeme..."></div>
            <div class="field"><label>Tutar (TL)</label><input type="number" id="gTutar" placeholder="500"></div>
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
        <button class="nav-item active" onclick="showSec('puantaj',this)"><span class="icon">📋</span>Puantaj</button>
        <button class="nav-item" onclick="showSec('isci',this)"><span class="icon">👷</span>İşçiler</button>
        <button class="nav-item" onclick="showSec('ozet',this)"><span class="icon">📊</span>Özet</button>
        <button class="nav-item" onclick="showSec('gider',this)"><span class="icon">💸</span>Giderler</button>
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
                <select id="mDurum"><option value="tam_gun">Tam Gün</option><option value="yarim_gun">Yarım Gün</option><option value="izinli">İzinli/Gelmedi</option></select>
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
            document.getElementById('pList').innerHTML = is.map(i => {
                const p = pm[i.id];
                const s = p?.calisma_durumu || '';
                const ini = i.ad_soyad.split(' ').map(n=>n[0]).join('').substring(0,2);
                return `<div class="card" onclick="openModal(${i.id},'${i.ad_soyad}','${s}','${p?.giris_saati||'08:00'}','${p?.cikis_saati||'17:00'}',${p?.mesai_saat||0},'${p?.yapilan_is||''}')">
                    <div class="avatar">${ini}</div>
                    <div class="info"><div class="name">${i.ad_soyad}</div><div class="role">${i.ustalik||'İşçi'}${s?' • '+({'tam_gun':'Tam','yarim_gun':'Yarım','izinli':'Yok'}[s]||s):''}</div></div>
                    <div class="btns">
                        <button class="sbtn t ${s==='tam_gun'?'sel':''}" onclick="event.stopPropagation();qp(${i.id},'tam_gun')">✓</button>
                        <button class="sbtn y ${s==='yarim_gun'?'sel':''}" onclick="event.stopPropagation();qp(${i.id},'yarim_gun')">½</button>
                        <button class="sbtn x ${s==='izinli'?'sel':''}" onclick="event.stopPropagation();qp(${i.id},'izinli')">✗</button>
                    </div>
                </div>`;
            }).join('');
        }

        document.getElementById('iList').innerHTML = is.map(i => {
            const ini = i.ad_soyad.split(' ').map(n=>n[0]).join('').substring(0,2);
            return `<div class="card"><div class="avatar">${ini}</div><div class="info"><div class="name">${i.ad_soyad}</div><div class="role">${i.ustalik} • ${i.gunluk_ucret||0} TL</div></div></div>`;
        }).join('');

        loadOzet();
    } catch(e) { console.error(e); }
}

async function qp(id, dur) {
    const t = document.getElementById('tarih').value;
    await fetch('/api/puantaj', {
        method: 'POST', headers: h(),
        body: JSON.stringify({isci_id:id, tarih:t, calisma_durumu:dur, giris_saati:dur==='tam_gun'?'08:00':'08:00', cikis_saati:dur==='tam_gun'?'17:00':'12:00'})
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
        body: JSON.stringify({ad_soyad:ad, ustalik:document.getElementById('iUst').value, gunluk_ucret:parseFloat(document.getElementById('iUcret').value)||0})
    });
    document.getElementById('iAd').value = '';
    document.getElementById('iUcret').value = '';
    toast('İşçi eklendi');
    load();
}

async function loadOzet() {
    const r = await fetch('/api/ozet/haftalik', {headers:h()}).then(r=>r.json());
    let html = '<table style="width:100%;font-size:13px;"><tr style="color:#a0a0a0"><td>İşçi</td><td>Gün</td><td>Toplam</td></tr>';
    r.isciler.forEach(i => {
        html += `<tr><td>${i.ad_soyad}</td><td>${i.yevmiye}</td><td style="color:#00d26a">${i.hakedis.toLocaleString()} ₺</td></tr>`;
    });
    html += '</table>';
    document.getElementById('ozetTbl').innerHTML = html;
}

function showSec(name, el) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.tab,.nav-item').forEach(t => t.classList.remove('active'));
    document.getElementById('sec-'+name).classList.add('active');
    if(el) el.classList.add('active');
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
        body: JSON.stringify({ad:ad, tutar:parseFloat(tutar), ay:ay, aciklama:document.getElementById('gAcik').value})
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
    c.execute('SELECT COUNT(DISTINCT isci_id) FROM puantaj WHERE tarih=?', (tarih,))
    gelen = c.fetchone()[0]
    c.execute('SELECT SUM(mesai_saat) FROM puantaj WHERE tarih=?', (tarih,))
    mesai = c.fetchone()[0] or 0
    conn.close()
    return jsonify({'gelen_isci': gelen, 'gelmeyen_isci': toplam-gelen, 'toplam_mesai_saat': mesai})

@app.route('/api/ozet/haftalik')
@require_auth
def api_haftalik():
    bitis = datetime.strptime(request.args.get('bitis', date.today().isoformat()), '%Y-%m-%d').date()
    baslangic = bitis - timedelta(days=6)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''SELECT i.id, i.ad_soyad, i.gunluk_ucret,
                 SUM(CASE WHEN p.calisma_durumu='tam_gun' THEN 1 WHEN p.calisma_durumu='yarim_gun' THEN 0.5 ELSE 0 END) as yevmiye
                 FROM isci i LEFT JOIN puantaj p ON i.id=p.isci_id AND p.tarih BETWEEN ? AND ?
                 WHERE i.aktif=1 GROUP BY i.id''', (baslangic.isoformat(), bitis.isoformat()))
    isciler = []
    for r in c.fetchall():
        yev = r['yevmiye'] or 0
        isciler.append({'ad_soyad': r['ad_soyad'], 'yevmiye': yev, 'hakedis': yev * (r['gunluk_ucret'] or 0)})
    conn.close()
    return jsonify({'isciler': isciler})

@app.route('/api/gider', methods=['GET', 'POST'])
@require_auth
def api_gider():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == 'POST':
        d = request.json
        ay = d.get('ay', date.today().strftime('%Y-%m'))
        c.execute('INSERT INTO ek_gider (ad, tutar, ay, aciklama) VALUES (?,?,?,?)',
                  (d.get('ad'), d.get('tutar',0), ay, d.get('aciklama')))
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

if __name__ == '__main__':
    app.run(debug=True)
