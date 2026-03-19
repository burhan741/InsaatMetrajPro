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
API_TOKEN = None # Uygulama başlatılınca generate edilecek
API_USERNAME = "santiye"
API_PASSWORD = "2024" # Kullanıcı değiştirebilir

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

# ==================== METRAJ & GANTT API ====================
# Ana veritabani: insaat_metraj.db (puantaj api'deki metraj.db'den farkli)

def get_main_db_path():
    """Ana proje veritabani (insaat_metraj.db) yolunu dondur."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "data", "insaat_metraj.db")


def init_gantt_metraj_tables():
    """Gantt gorevleri tablosunu olustur (yoksa)."""
    path = get_main_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gantt_gorevleri (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            proje_id      INTEGER NOT NULL DEFAULT 0,
            poz_no        TEXT,
            is_kalemi     TEXT NOT NULL,
            metraj        REAL  DEFAULT 0,
            birim         TEXT  DEFAULT 'adet',
            calisan       TEXT,
            sure_gun      INTEGER DEFAULT 1,
            oncul_ids     TEXT  DEFAULT '[]',
            baslangic_gun INTEGER DEFAULT 0,
            ekip          TEXT,
            kaynak        TEXT,
            milestone     INTEGER DEFAULT 0,
            tamamlanma    REAL  DEFAULT 0,
            butce         REAL  DEFAULT 0,
            olusturma_tarihi TEXT,
            FOREIGN KEY (proje_id) REFERENCES projeler(id)
        )
    """)
    conn.commit()
    conn.close()


# ── /metraj ──────────────────────────────────────────────────────────────────

@app.route('/metraj/kalem-ekle', methods=['POST'])
@require_auth
def metraj_kalem_ekle():
    """
    Tek metraj kalemi ekle.

    Body (JSON):
        poz_no       : str   — poz numarasi (opsiyonel)
        is_kalemi    : str   — kalem tanimi (zorunlu)
        miktar       : float — miktar
        birim        : str   — m2, m3, kg, adet, goturu ...
        birim_fiyat  : float — TL
        kategori     : str   — hafriyat, temel, kolon, doseme ... (opsiyonel)
        proje_id     : int   — hedef proje (varsayilan 0 = aktif proje)

    Returns:
        { success, id, toplam }
    """
    data = request.get_json(force=True, silent=True) or {}
    is_kalemi = (data.get("is_kalemi") or "").strip()
    if not is_kalemi:
        return jsonify({"error": "is_kalemi alani zorunludur"}), 400

    miktar     = float(data.get("miktar", 0) or 0)
    birim_fiyat = float(data.get("birim_fiyat", 0) or 0)
    toplam     = round(miktar * birim_fiyat, 2)
    now        = datetime.now().isoformat()

    try:
        conn = sqlite3.connect(get_main_db_path())
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO metraj_kalemleri
                (proje_id, poz_no, tanim, miktar, birim, birim_fiyat, toplam, kategori, olusturma_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(data.get("proje_id", 0)),
            data.get("poz_no", ""),
            is_kalemi,
            miktar,
            data.get("birim", "adet"),
            birim_fiyat,
            toplam,
            data.get("kategori", ""),
            now,
        ))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return jsonify({"success": True, "id": new_id, "toplam": toplam}), 201
    except Exception as exc:
        logger.error("metraj_kalem_ekle hata: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route('/metraj/toplu-ekle', methods=['POST'])
@require_auth
def metraj_toplu_ekle():
    """
    Birden fazla metraj kalemi tek seferde ekle (AI asistan / Excel import).

    Body (JSON):
        proje_id : int                — hedef proje
        kalemler : list[dict]         — her dict, /metraj/kalem-ekle ile ayni alanlari icerir

    Returns:
        { success, eklenen, hatalar: [...] }
    """
    data = request.get_json(force=True, silent=True) or {}
    proje_id = int(data.get("proje_id", 0))
    kalemler = data.get("kalemler", [])
    if not kalemler:
        return jsonify({"error": "kalemler listesi bos"}), 400

    eklenen = 0
    hatalar = []
    now = datetime.now().isoformat()

    try:
        conn = sqlite3.connect(get_main_db_path())
        cursor = conn.cursor()
        for k in kalemler:
            is_kalemi = (k.get("is_kalemi") or "").strip()
            if not is_kalemi:
                hatalar.append({"kalem": k, "hata": "is_kalemi eksik"})
                continue
            miktar      = float(k.get("miktar", 0) or 0)
            birim_fiyat = float(k.get("birim_fiyat", 0) or 0)
            try:
                cursor.execute("""
                    INSERT INTO metraj_kalemleri
                        (proje_id, poz_no, tanim, miktar, birim, birim_fiyat, toplam, kategori, olusturma_tarihi)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(k.get("proje_id", proje_id)),
                    k.get("poz_no", ""),
                    is_kalemi,
                    miktar,
                    k.get("birim", "adet"),
                    birim_fiyat,
                    round(miktar * birim_fiyat, 2),
                    k.get("kategori", ""),
                    now,
                ))
                eklenen += 1
            except Exception as exc:
                hatalar.append({"kalem": is_kalemi, "hata": str(exc)})
        conn.commit()
        conn.close()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"success": True, "eklenen": eklenen, "hatalar": hatalar}), 201


@app.route('/metraj/kalemler', methods=['GET'])
@require_auth
def metraj_kalemler_listele():
    """
    Proje metraj kalemlerini listele.

    Query params:
        proje_id : int  (zorunlu)
        kategori : str  (opsiyonel filtre)
    """
    proje_id = request.args.get("proje_id")
    if not proje_id:
        return jsonify({"error": "proje_id gerekli"}), 400

    kategori = request.args.get("kategori")
    try:
        conn = sqlite3.connect(get_main_db_path())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if kategori:
            cursor.execute(
                "SELECT * FROM metraj_kalemleri WHERE proje_id=? AND kategori=? ORDER BY id",
                (int(proje_id), kategori)
            )
        else:
            cursor.execute(
                "SELECT * FROM metraj_kalemleri WHERE proje_id=? ORDER BY id",
                (int(proje_id),)
            )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({"proje_id": int(proje_id), "toplam": len(rows), "kalemler": rows})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── /gantt ───────────────────────────────────────────────────────────────────

@app.route('/gantt/gorev-ekle', methods=['POST'])
@require_auth
def gantt_gorev_ekle():
    """
    Tek Gantt gorevi ekle.

    Body (JSON):
        poz_no       : str   — metraj poz numarasiyla eslestirme (opsiyonel)
        is_kalemi    : str   — gorev adi (zorunlu)
        metraj       : float — miktar (sure hesabinda kullanilir)
        birim        : str   — m2, m3, kg ...
        calisan      : str   — ekip / kaynak tanimi
        sure         : int   — gun (0 ise CŞB verimliliginden otomatik hesaplanir)
        oncul        : list[int] — oncul gorev ID listesi (FS bagimliliklari)
        baslangic_gun: int   — proje baslangicina gore ofset gun
        proje_id     : int   — hedef proje
        butce        : float — TL (opsiyonel)
        milestone    : bool  — kilometre tasi mi?

    Returns:
        { success, id, sure_gun }
    """
    data = request.get_json(force=True, silent=True) or {}
    is_kalemi = (data.get("is_kalemi") or "").strip()
    if not is_kalemi:
        return jsonify({"error": "is_kalemi alani zorunludur"}), 400

    oncul = data.get("oncul", [])
    if isinstance(oncul, str):
        try:
            oncul = json.loads(oncul)
        except Exception:
            oncul = []

    sure = int(data.get("sure", 0) or 0)
    metraj = float(data.get("metraj", 0) or 0)

    # Surey 0 ise CŞB verimliliginden otomatik tahmin
    if sure <= 0 and metraj > 0:
        birim = (data.get("birim") or "").lower()
        t = is_kalemi.lower()
        import math as _math
        VERIMLILIK_MAP = {
            "kalip":    {"m2": 2.86}, "kolon_kalip": {"m2": 1.82},
            "doseme_kalip": {"m2": 4.0}, "demir":    {"kg": 333.0},
            "beton":    {"m3": 15.0},  "siva":       {"m2": 25.0},
            "boya":     {"m2": 45.0},  "seramik":    {"m2": 8.0},
            "tugla":    {"m2": 6.0},   "hafriyat":   {"m3": 120.0},
        }
        v = 10.0  # varsayilan
        for anahtar, tablo in VERIMLILIK_MAP.items():
            if anahtar in t:
                v = tablo.get(birim, list(tablo.values())[0])
                break
        sure = max(1, _math.ceil(metraj / (v * 3)))  # 3 usta

    now = datetime.now().isoformat()
    try:
        conn = sqlite3.connect(get_main_db_path())
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO gantt_gorevleri
                (proje_id, poz_no, is_kalemi, metraj, birim, calisan,
                 sure_gun, oncul_ids, baslangic_gun, butce, milestone, olusturma_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(data.get("proje_id", 0)),
            data.get("poz_no", ""),
            is_kalemi,
            metraj,
            data.get("birim", "adet"),
            data.get("calisan", ""),
            sure,
            json.dumps(oncul, ensure_ascii=False),
            int(data.get("baslangic_gun", 0) or 0),
            float(data.get("butce", 0) or 0),
            1 if data.get("milestone") else 0,
            now,
        ))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return jsonify({"success": True, "id": new_id, "sure_gun": sure}), 201
    except Exception as exc:
        logger.error("gantt_gorev_ekle hata: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route('/gantt/toplu-ekle', methods=['POST'])
@require_auth
def gantt_toplu_ekle():
    """
    Birden fazla Gantt gorevi tek seferde ekle (AI asistan / Excel import).

    Body (JSON):
        proje_id : int
        gorevler : list[dict]  — her dict, /gantt/gorev-ekle ile ayni alanlari icerir

    Returns:
        { success, eklenen, hatalar }
    """
    data = request.get_json(force=True, silent=True) or {}
    proje_id = int(data.get("proje_id", 0))
    gorevler = data.get("gorevler", [])
    if not gorevler:
        return jsonify({"error": "gorevler listesi bos"}), 400

    import math as _math
    eklenen = 0
    hatalar = []
    now = datetime.now().isoformat()

    VERIMLILIK_MAP = {
        "kalip": 2.86, "demir": 333.0, "beton": 15.0,
        "siva": 25.0, "boya": 45.0, "seramik": 8.0,
        "tugla": 6.0, "hafriyat": 120.0,
    }

    try:
        conn = sqlite3.connect(get_main_db_path())
        cursor = conn.cursor()
        for g in gorevler:
            is_kalemi = (g.get("is_kalemi") or "").strip()
            if not is_kalemi:
                hatalar.append({"gorev": g, "hata": "is_kalemi eksik"})
                continue

            oncul = g.get("oncul", [])
            if isinstance(oncul, str):
                try:
                    oncul = json.loads(oncul)
                except Exception:
                    oncul = []

            sure = int(g.get("sure", 0) or 0)
            metraj = float(g.get("metraj", 0) or 0)
            if sure <= 0 and metraj > 0:
                t = is_kalemi.lower()
                v = next((v for k, v in VERIMLILIK_MAP.items() if k in t), 10.0)
                sure = max(1, _math.ceil(metraj / (v * 3)))

            try:
                cursor.execute("""
                    INSERT INTO gantt_gorevleri
                        (proje_id, poz_no, is_kalemi, metraj, birim, calisan,
                         sure_gun, oncul_ids, baslangic_gun, butce, milestone, olusturma_tarihi)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(g.get("proje_id", proje_id)),
                    g.get("poz_no", ""),
                    is_kalemi,
                    metraj,
                    g.get("birim", "adet"),
                    g.get("calisan", ""),
                    sure,
                    json.dumps(oncul, ensure_ascii=False),
                    int(g.get("baslangic_gun", 0) or 0),
                    float(g.get("butce", 0) or 0),
                    1 if g.get("milestone") else 0,
                    now,
                ))
                eklenen += 1
            except Exception as exc:
                hatalar.append({"gorev": is_kalemi, "hata": str(exc)})
        conn.commit()
        conn.close()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"success": True, "eklenen": eklenen, "hatalar": hatalar}), 201


@app.route('/gantt/gorevler', methods=['GET'])
@require_auth
def gantt_gorevler_listele():
    """
    Proje Gantt gorevlerini listele.

    Query params:
        proje_id : int  (zorunlu)
    """
    proje_id = request.args.get("proje_id")
    if not proje_id:
        return jsonify({"error": "proje_id gerekli"}), 400
    try:
        conn = sqlite3.connect(get_main_db_path())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM gantt_gorevleri WHERE proje_id=? ORDER BY id",
            (int(proje_id),)
        )
        rows = []
        for r in cursor.fetchall():
            d = dict(r)
            try:
                d["oncul_ids"] = json.loads(d.get("oncul_ids") or "[]")
            except Exception:
                d["oncul_ids"] = []
            rows.append(d)
        conn.close()
        return jsonify({"proje_id": int(proje_id), "toplam": len(rows), "gorevler": rows})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route('/gantt/gorev/<int:gorev_id>', methods=['DELETE'])
@require_auth
def gantt_gorev_sil(gorev_id):
    """Gantt gorevi sil."""
    try:
        conn = sqlite3.connect(get_main_db_path())
        cursor = conn.cursor()
        cursor.execute("DELETE FROM gantt_gorevleri WHERE id=?", (gorev_id,))
        conn.commit()
        silinen = cursor.rowcount
        conn.close()
        if silinen:
            return jsonify({"success": True, "message": f"Gorev {gorev_id} silindi"})
        return jsonify({"error": "Gorev bulunamadi"}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ==================== SUNUCU BAŞLATMA ====================

def generate_token():
    """Güvenli token oluştur"""
    global API_TOKEN
    API_TOKEN = secrets.token_urlsafe(32)
    return API_TOKEN

def run_server(host='0.0.0.0', port=5000, debug=False):
    """Sunucuyu başlat"""
    init_puantaj_tables()
    init_gantt_metraj_tables()
    token = generate_token()

    ip = get_local_ip()
    base = f"http://{ip}:{port}"
    print("\n" + "="*60)
    print(" INSAAT METRAJ PRO — API SUNUCUSU")
    print("="*60)
    print(f"\n Yerel : http://localhost:{port}")
    print(f" Ag    : {base}")
    print(f"\n Kullanici : {API_USERNAME}")
    print(f" Sifre     : {API_PASSWORD}")
    print(f"\n API Token : {token[:20]}...")
    print("\n --- METRAJ ENDPOINT'LERI ---")
    print(f"  GET  {base}/metraj/kalemler?proje_id=<id>")
    print(f"  POST {base}/metraj/kalem-ekle")
    print(f"  POST {base}/metraj/toplu-ekle")
    print("\n --- GANTT ENDPOINT'LERI ---")
    print(f"  GET  {base}/gantt/gorevler?proje_id=<id>")
    print(f"  POST {base}/gantt/gorev-ekle")
    print(f"  POST {base}/gantt/toplu-ekle")
    print(f"  DEL  {base}/gantt/gorev/<id>")
    print("\n --- PUANTAJ ENDPOINT'LERI ---")
    print(f"  GET/POST {base}/api/isci")
    print(f"  GET/POST {base}/api/puantaj")
    print(f"  GET/POST {base}/api/avans")
    print("\n" + "="*60 + "\n")

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
