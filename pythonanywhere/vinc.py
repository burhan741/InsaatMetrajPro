"""
vinc.py - Mobil Vinc gelir-gider defteri (Blueprint).

NEYI COZUYORUZ: Mobil vinc isi, isci/puantaj/hakedis hesaplarindan
BAGIMSIZ kendi gelir-gider defteri. Eskiden puantaj sayfasinda bir sekmeydi;
ana programda ayri bir kart oldu. vinc_defter tablosu disinda hicbir
tabloya dokunmaz. Tablo ve veri AYNEN korunur (tasima gerekmez).

1. ADIM: Tablo + mevcut /api/vinc/ekle, /liste, /sil route'lari eski
app.py'den davranis degismeden tasindi. /vinc sayfasi ve duzenleme 2. adimda.

NASIL TEST EDERIZ: test_vinc.py - eski app.py ile bu modulun ayni
veritabaninda ayni liste/toplam cevabini verdigi, ekle/sil'in calistigi.
"""

from datetime import date

from flask import Blueprint, jsonify, request

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
    """Toplam gelir / gider / net. Liste ve ana menu ayni fonksiyonu kullanir."""
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


@bp.route('/api/vinc/ekle', methods=['POST'])
def api_vinc_ekle():
    d = request.json or {}
    tip = d.get('tip')
    if tip not in ('gelir', 'gider'):
        return jsonify({'error': 'Gecersiz tip'}), 400
    try:
        miktar = float(d.get('miktar', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'Gecersiz miktar'}), 400
    if miktar <= 0:
        return jsonify({'error': 'Gecersiz miktar'}), 400
    tarih = d.get('tarih') or date.today().isoformat()
    conn = ortak.baglan()
    conn.execute('INSERT INTO vinc_defter (tarih, tip, aciklama, miktar) VALUES (?,?,?,?)',
                 (tarih, tip, d.get('aciklama', ''), miktar))
    conn.commit()
    conn.close()
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
