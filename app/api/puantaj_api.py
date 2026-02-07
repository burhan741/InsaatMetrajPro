"""
Puantaj API - Flask REST API
iOS ve diğer cihazlardan erişim için
"""

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from functools import wraps
from datetime import datetime, date
import sqlite3
import os
import json
import secrets
import logging

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Güvenlik - Basit token authentication
API_TOKEN = None  # Uygulama başlatılınca generate edilecek
API_USERNAME = "santiye"
API_PASSWORD = "2024"  # Kullanıcı değiştirebilir

# Veritabanı yolu
DB_PATH = None

def get_db_path():
    """Veritabanı yolunu al"""
    global DB_PATH
    if DB_PATH is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        DB_PATH = os.path.join(base_dir, "data", "metraj.db")
    return DB_PATH

def init_puantaj_tables():
    """Puantaj tablolarını oluştur"""
    db_path = get_db_path()

    # data klasörü yoksa oluştur
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # İşçi tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS isci (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            tc_no TEXT UNIQUE,
            telefon TEXT,
            ustalik TEXT DEFAULT 'Duz Isci',
            gunluk_ucret REAL DEFAULT 0,
            ekip TEXT,
            aktif INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Puantaj tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS puantaj (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isci_id INTEGER NOT NULL,
            proje_id INTEGER,
            tarih DATE NOT NULL,
            giris_saati TIME,
            cikis_saati TIME,
            calisma_durumu TEXT DEFAULT 'tam_gun',
            mesai_saat REAL DEFAULT 0,
            yapilan_is TEXT,
            notlar TEXT,
            konum_lat REAL,
            konum_lng REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            FOREIGN KEY (isci_id) REFERENCES isci(id)
        )
    ''')

    # Avans tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isci_id INTEGER NOT NULL,
            tarih DATE NOT NULL,
            miktar REAL NOT NULL,
            aciklama TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (isci_id) REFERENCES isci(id)
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("Puantaj tabloları hazır")

def require_auth(f):
    """Basit authentication decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        token = request.headers.get('X-API-Token')

        # Token ile auth
        if token and token == API_TOKEN:
            return f(*args, **kwargs)

        # Basic auth
        if auth and auth.username == API_USERNAME and auth.password == API_PASSWORD:
            return f(*args, **kwargs)

        return jsonify({'error': 'Yetkisiz erişim'}), 401
    return decorated

# ==================== ANA SAYFA (PWA) ====================

@app.route('/')
def index():
    """Ana sayfa - PWA"""
    return render_template('puantaj_mobile.html')

@app.route('/manifest.json')
def manifest():
    """PWA manifest dosyası"""
    return jsonify({
        "name": "Şantiye Puantaj",
        "short_name": "Puantaj",
        "description": "İşçi puantaj takip sistemi",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1a1a2e",
        "theme_color": "#e94560",
        "icons": [
            {
                "src": "/static/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    })

@app.route('/sw.js')
def service_worker():
    """Service worker for offline support"""
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

# ==================== İŞÇİ API ====================

@app.route('/api/isci', methods=['GET'])
@require_auth
def get_isciler():
    """Tüm işçileri getir"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    aktif = request.args.get('aktif', '1')
    cursor.execute('SELECT * FROM isci WHERE aktif = ? ORDER BY ad_soyad', (aktif,))
    isciler = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify(isciler)

@app.route('/api/isci', methods=['POST'])
@require_auth
def add_isci():
    """Yeni işçi ekle"""
    data = request.json

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO isci (ad_soyad, tc_no, telefon, ustalik, gunluk_ucret, ekip)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data.get('ad_soyad'),
            data.get('tc_no'),
            data.get('telefon'),
            data.get('ustalik', 'Duz Isci'),
            data.get('gunluk_ucret', 0),
            data.get('ekip')
        ))
        conn.commit()
        isci_id = cursor.lastrowid
        conn.close()

        return jsonify({'success': True, 'id': isci_id, 'message': 'İşçi eklendi'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Bu TC no zaten kayıtlı'}), 400
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/isci/<int:isci_id>', methods=['PUT'])
@require_auth
def update_isci(isci_id):
    """İşçi güncelle"""
    data = request.json

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE isci SET ad_soyad=?, telefon=?, ustalik=?, gunluk_ucret=?, ekip=?, aktif=?
        WHERE id=?
    ''', (
        data.get('ad_soyad'),
        data.get('telefon'),
        data.get('ustalik'),
        data.get('gunluk_ucret'),
        data.get('ekip'),
        data.get('aktif', 1),
        isci_id
    ))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'İşçi güncellendi'})

# ==================== PUANTAJ API ====================

@app.route('/api/puantaj', methods=['GET'])
@require_auth
def get_puantaj():
    """Puantaj kayıtlarını getir"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tarih = request.args.get('tarih', date.today().isoformat())
    isci_id = request.args.get('isci_id')

    if isci_id:
        cursor.execute('''
            SELECT p.*, i.ad_soyad, i.ustalik
            FROM puantaj p
            JOIN isci i ON p.isci_id = i.id
            WHERE p.tarih = ? AND p.isci_id = ?
            ORDER BY p.created_at DESC
        ''', (tarih, isci_id))
    else:
        cursor.execute('''
            SELECT p.*, i.ad_soyad, i.ustalik
            FROM puantaj p
            JOIN isci i ON p.isci_id = i.id
            WHERE p.tarih = ?
            ORDER BY i.ad_soyad
        ''', (tarih,))

    puantajlar = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(puantajlar)

@app.route('/api/puantaj', methods=['POST'])
@require_auth
def add_puantaj():
    """Puantaj kaydı ekle"""
    data = request.json

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Aynı gün için kayıt var mı kontrol et
    cursor.execute('''
        SELECT id FROM puantaj WHERE isci_id = ? AND tarih = ?
    ''', (data.get('isci_id'), data.get('tarih', date.today().isoformat())))

    existing = cursor.fetchone()

    if existing:
        # Güncelle
        cursor.execute('''
            UPDATE puantaj SET
                giris_saati=?, cikis_saati=?, calisma_durumu=?,
                mesai_saat=?, yapilan_is=?, notlar=?, konum_lat=?, konum_lng=?
            WHERE id=?
        ''', (
            data.get('giris_saati'),
            data.get('cikis_saati'),
            data.get('calisma_durumu', 'tam_gun'),
            data.get('mesai_saat', 0),
            data.get('yapilan_is'),
            data.get('notlar'),
            data.get('konum_lat'),
            data.get('konum_lng'),
            existing[0]
        ))
        msg = 'Puantaj güncellendi'
    else:
        # Yeni ekle
        cursor.execute('''
            INSERT INTO puantaj (isci_id, proje_id, tarih, giris_saati, cikis_saati,
                                 calisma_durumu, mesai_saat, yapilan_is, notlar,
                                 konum_lat, konum_lng, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('isci_id'),
            data.get('proje_id'),
            data.get('tarih', date.today().isoformat()),
            data.get('giris_saati'),
            data.get('cikis_saati'),
            data.get('calisma_durumu', 'tam_gun'),
            data.get('mesai_saat', 0),
            data.get('yapilan_is'),
            data.get('notlar'),
            data.get('konum_lat'),
            data.get('konum_lng'),
            data.get('created_by', 'mobile')
        ))
        msg = 'Puantaj eklendi'

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': msg})

@app.route('/api/puantaj/toplu', methods=['POST'])
@require_auth
def add_toplu_puantaj():
    """Toplu puantaj girişi (tüm ekip için)"""
    data = request.json
    tarih = data.get('tarih', date.today().isoformat())
    isci_listesi = data.get('isciler', [])

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    eklenen = 0
    for isci in isci_listesi:
        if not isci.get('katildi', True):
            continue

        cursor.execute('''
            INSERT OR REPLACE INTO puantaj (isci_id, tarih, giris_saati, cikis_saati,
                                           calisma_durumu, mesai_saat, yapilan_is, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            isci.get('isci_id'),
            tarih,
            isci.get('giris_saati', '08:00'),
            isci.get('cikis_saati', '17:00'),
            isci.get('calisma_durumu', 'tam_gun'),
            isci.get('mesai_saat', 0),
            isci.get('yapilan_is'),
            'mobile_toplu'
        ))
        eklenen += 1

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': f'{eklenen} işçi puantajı kaydedildi'})

@app.route('/api/puantaj/<int:puantaj_id>', methods=['DELETE'])
@require_auth
def delete_puantaj(puantaj_id):
    """Puantaj kaydı sil"""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('DELETE FROM puantaj WHERE id = ?', (puantaj_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Puantaj silindi'})

# ==================== ÖZET API ====================

@app.route('/api/ozet/gunluk', methods=['GET'])
@require_auth
def get_gunluk_ozet():
    """Günlük özet"""
    tarih = request.args.get('tarih', date.today().isoformat())

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Toplam işçi sayısı
    cursor.execute('SELECT COUNT(*) as toplam FROM isci WHERE aktif = 1')
    toplam_isci = cursor.fetchone()['toplam']

    # Bugün gelen işçi sayısı
    cursor.execute('''
        SELECT COUNT(DISTINCT isci_id) as gelen
        FROM puantaj WHERE tarih = ?
    ''', (tarih,))
    gelen_isci = cursor.fetchone()['gelen']

    # Çalışma durumu dağılımı
    cursor.execute('''
        SELECT calisma_durumu, COUNT(*) as sayi
        FROM puantaj WHERE tarih = ?
        GROUP BY calisma_durumu
    ''', (tarih,))
    durum_dagilimi = {row['calisma_durumu']: row['sayi'] for row in cursor.fetchall()}

    # Toplam mesai
    cursor.execute('''
        SELECT SUM(mesai_saat) as toplam_mesai
        FROM puantaj WHERE tarih = ?
    ''', (tarih,))
    toplam_mesai = cursor.fetchone()['toplam_mesai'] or 0

    conn.close()

    return jsonify({
        'tarih': tarih,
        'toplam_isci': toplam_isci,
        'gelen_isci': gelen_isci,
        'gelmeyen_isci': toplam_isci - gelen_isci,
        'devam_orani': round((gelen_isci / toplam_isci * 100) if toplam_isci > 0 else 0, 1),
        'durum_dagilimi': durum_dagilimi,
        'toplam_mesai_saat': toplam_mesai
    })

@app.route('/api/ozet/haftalik', methods=['GET'])
@require_auth
def get_haftalik_ozet():
    """Haftalık özet - işçi bazında"""
    from datetime import timedelta

    bitis = request.args.get('bitis', date.today().isoformat())
    bitis_date = datetime.strptime(bitis, '%Y-%m-%d').date()
    baslangic_date = bitis_date - timedelta(days=6)

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT i.id, i.ad_soyad, i.ustalik, i.gunluk_ucret,
               COUNT(p.id) as calisilan_gun,
               SUM(CASE WHEN p.calisma_durumu = 'tam_gun' THEN 1
                        WHEN p.calisma_durumu = 'yarim_gun' THEN 0.5
                        ELSE 0 END) as yevmiye,
               SUM(p.mesai_saat) as toplam_mesai
        FROM isci i
        LEFT JOIN puantaj p ON i.id = p.isci_id AND p.tarih BETWEEN ? AND ?
        WHERE i.aktif = 1
        GROUP BY i.id
        ORDER BY i.ad_soyad
    ''', (baslangic_date.isoformat(), bitis_date.isoformat()))

    isci_ozet = []
    for row in cursor.fetchall():
        yevmiye = row['yevmiye'] or 0
        ucret = row['gunluk_ucret'] or 0
        isci_ozet.append({
            'id': row['id'],
            'ad_soyad': row['ad_soyad'],
            'ustalik': row['ustalik'],
            'calisilan_gun': row['calisilan_gun'] or 0,
            'yevmiye': yevmiye,
            'mesai_saat': row['toplam_mesai'] or 0,
            'hakedis': yevmiye * ucret
        })

    conn.close()

    return jsonify({
        'baslangic': baslangic_date.isoformat(),
        'bitis': bitis_date.isoformat(),
        'isciler': isci_ozet
    })

# ==================== AVANS API ====================

@app.route('/api/avans', methods=['GET'])
@require_auth
def get_avanslar():
    """Avans kayıtlarını getir"""
    isci_id = request.args.get('isci_id')

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if isci_id:
        cursor.execute('''
            SELECT a.*, i.ad_soyad
            FROM avans a JOIN isci i ON a.isci_id = i.id
            WHERE a.isci_id = ?
            ORDER BY a.tarih DESC
        ''', (isci_id,))
    else:
        cursor.execute('''
            SELECT a.*, i.ad_soyad
            FROM avans a JOIN isci i ON a.isci_id = i.id
            ORDER BY a.tarih DESC LIMIT 50
        ''')

    avanslar = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(avanslar)

@app.route('/api/avans', methods=['POST'])
@require_auth
def add_avans():
    """Avans ekle"""
    data = request.json

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO avans (isci_id, tarih, miktar, aciklama)
        VALUES (?, ?, ?, ?)
    ''', (
        data.get('isci_id'),
        data.get('tarih', date.today().isoformat()),
        data.get('miktar'),
        data.get('aciklama')
    ))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Avans kaydedildi'})

# ==================== SUNUCU BAŞLATMA ====================

def generate_token():
    """Güvenli token oluştur"""
    global API_TOKEN
    API_TOKEN = secrets.token_urlsafe(32)
    return API_TOKEN

def run_server(host='0.0.0.0', port=5000, debug=False):
    """Sunucuyu başlat"""
    init_puantaj_tables()
    token = generate_token()

    print("\n" + "="*50)
    print("  PUANTAJ API SUNUCUSU")
    print("="*50)
    print(f"\n  Yerel: http://localhost:{port}")
    print(f"  Ağ:    http://{get_local_ip()}:{port}")
    print(f"\n  Kullanıcı: {API_USERNAME}")
    print(f"  Şifre:     {API_PASSWORD}")
    print(f"\n  API Token: {token[:20]}...")
    print("\n" + "="*50 + "\n")

    app.run(host=host, port=port, debug=debug)

def get_local_ip():
    """Yerel IP adresini al"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

if __name__ == '__main__':
    run_server(debug=True)
