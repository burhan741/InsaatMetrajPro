"""
cari.py - Muteahhit + Demirci cari hesap motoru (Blueprint).

NEYI COZUYORUZ: Santiyede iki yonlu para takibi:
  - Muteahhit: dokulen beton (m³ x birim fiyat) + giderler = hakedis;
    muteahhitten alinan para dusulur. Kalan = ALACAGIM.
  - Demirci: demircinin isi (ton x birim fiyat) + giderler = hakedis;
    demirciye odedigim para dusulur. Kalan = BORCUM.
Iki tur AYNI kodu kullanir ('tur' alani); bir ozellik bir kez yazilir.

Kurallar (ANA_PROGRAM_PLANI.md, kullanici onayli):
  - Birim fiyat satira KILITLI: yeni is satirinda fiyat sunucuda kalemin o
    anki fiyatindan alinir; kalem fiyati sonradan degisse gecmis satirlar
    degismez. Satir duzenlenirken kullanici fiyati bilerek degistirebilir.
  - hakedis = SUM(tutar: is + gider), odenen = SUM(tutar: odeme),
    kalan = hakedis - odenen. TEK fonksiyon: firma_bakiye(). Liste, firma
    sayfasi, ana menu, PDF hepsi bunu cagirir.
  - Kalan eksiye duserse sifirlanmaz -> "Fazla odeme".
  - Firma silinince hareketleri ve kalemleri tek transaction'da silinir.

NASIL TEST EDERIZ: test_cari.py (bakiye, fiyat kilidi, kaskad silme, fazla
odeme, dogrulama, devirli dokum, sayfalar, PDF, gomulu JS).
"""

import re
from datetime import date, timedelta
from io import BytesIO

from flask import Blueprint, abort, jsonify, make_response, render_template_string, request, send_file

import ortak

bp = Blueprint('cari', __name__)

# Ekranda / PDF'te ture gore degisen her sey burada. Yeni metin = sadece buraya.
TURLER = {
    'muteahhit': {
        'tur': 'muteahhit', 'baslik': 'Müteahhitler', 'tekil': 'Müteahhit',
        'ekle_btn': '+ Müteahhit Ekle', 'is_sekme': 'Beton', 'is_adi': 'Beton',
        'birim': 'm³', 'gider_sekme': 'Gider', 'odeme_sekme': 'Alınan para',
        'odeme_kolon': 'Alınan', 'odeme_fiil': 'Alınan',
        'kalan_etiket': 'Kalan alacak', 'toplam_etiket': 'Toplam alacak',
        'kalem_ornek': 'Gro beton', 'kalem_ipucu': 'Örn: Gro beton, Temel betonu, Normal katlar',
        'yon_aciklama': 'Kalan = müteahhitten alacağınız.',
        'gider_ornek': 'Pompa, nakliye, katkı…',
        'gider_yardim': 'Pompa, nakliye gibi beton dışı masrafları yazın. Giderler hakedişe eklenir (alacağınızı artırır).',
        'gun_odeme_etiket': 'Günün tahsilatı',
    },
    'demirci': {
        'tur': 'demirci', 'baslik': 'Demirciler', 'tekil': 'Demirci',
        'ekle_btn': '+ Demirci Ekle', 'is_sekme': 'İş', 'is_adi': 'İş',
        'birim': 'ton', 'gider_sekme': 'Gider', 'odeme_sekme': 'Ödenen para',
        'odeme_kolon': 'Ödenen', 'odeme_fiil': 'Ödenen',
        'kalan_etiket': 'Kalan borcum', 'toplam_etiket': 'Toplam borç',
        'kalem_ornek': 'Temel demiri', 'kalem_ipucu': 'Örn: Temel demiri, Normal kat demiri',
        'yon_aciklama': 'Kalan = demirciye borcunuz.',
        'gider_ornek': 'Nakliye, bağ teli, vinç…',
        'gider_yardim': 'Nakliye, bağ teli gibi işe ait ek masrafları yazın. Giderler hakedişe eklenir (borcunuzu artırır).',
        'gun_odeme_etiket': 'Günün ödemesi',
    },
}
AKTIF_TURLER = ('muteahhit', 'demirci')

ONCEKI_GOSTERIM = 8  # defterde acik gosterilen son satir sayisi


class CariHata(Exception):
    def __init__(self, mesaj, kod=400):
        super().__init__(mesaj)
        self.mesaj = mesaj
        self.kod = kod


@bp.errorhandler(CariHata)
def _cari_hata(e):
    return jsonify({'error': e.mesaj}), e.kod


def init_db():
    conn = ortak.baglan()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS cari_firma (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tur TEXT NOT NULL CHECK (tur IN ('muteahhit','demirci')),
        ad TEXT NOT NULL,
        olusturma TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS cari_fiyat_kalemi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        firma_id INTEGER NOT NULL REFERENCES cari_firma(id),
        ad TEXT NOT NULL,
        birim_fiyat REAL NOT NULL,
        sira INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS cari_hareket (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        firma_id INTEGER NOT NULL REFERENCES cari_firma(id),
        tarih DATE NOT NULL,
        tip TEXT NOT NULL CHECK (tip IN ('is','gider','odeme')),
        kalem_id INTEGER,
        kalem_adi TEXT,
        miktar REAL,
        birim_fiyat REAL,
        tutar REAL NOT NULL,
        aciklama TEXT,
        olusturma TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS cari_ayar (
        anahtar TEXT PRIMARY KEY,
        deger TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_cari_hareket_firma ON cari_hareket(firma_id, tarih);
    CREATE INDEX IF NOT EXISTS ix_cari_hareket_tarih ON cari_hareket(tarih);
    CREATE INDEX IF NOT EXISTS ix_cari_kalem_firma ON cari_fiyat_kalemi(firma_id);
    ''')
    conn.commit()
    conn.close()


# ====================================================================
# MOTOR (saf fonksiyonlar: conn alir, Flask'tan bagimsiz test edilir)
# ====================================================================
def _para(x):
    """Kurus duzeyinde yarim-yukari yuvarlanmis float."""
    return float(ortak._yuvarla(x, 2))


def firma_bakiye(conn, firma_id, bas=None, bit=None):
    """Firmanin bakiyesi. bas/bit verilirse sadece o tarih araligi (dahil).

    Neyi cozuyoruz: Bakiye hesabi TEK yerde. Gider hakedise eklenir.
    Nasil test ederiz: test_cari.py::test_bakiye_*.
    """
    row = conn.execute('''SELECT
        COALESCE(SUM(CASE WHEN tip IN ('is','gider') THEN tutar END), 0),
        COALESCE(SUM(CASE WHEN tip = 'odeme' THEN tutar END), 0),
        COALESCE(SUM(CASE WHEN tip = 'is' THEN miktar END), 0),
        COALESCE(SUM(CASE WHEN tip = 'gider' THEN tutar END), 0)
        FROM cari_hareket
        WHERE firma_id = ? AND (? IS NULL OR tarih >= ?) AND (? IS NULL OR tarih <= ?)''',
        (firma_id, bas, bas, bit, bit)).fetchone()
    hakedis, odenen = _para(row[0]), _para(row[1])
    kalan = _para(hakedis - odenen)
    return {
        'hakedis': hakedis,
        'odenen': odenen,
        'kalan': kalan,
        'is_miktar': round(row[2] or 0, 3),
        'gider': _para(row[3]),
        'fazla_odeme': kalan < 0,
    }


def firma_getir(conn, firma_id, tur=None):
    f = conn.execute('SELECT * FROM cari_firma WHERE id = ?', (firma_id,)).fetchone()
    if f is None or f['tur'] not in AKTIF_TURLER or (tur and f['tur'] != tur):
        raise CariHata('Firma bulunamadi', 404)
    return dict(f)


def kalemleri_getir(conn, firma_id):
    return [dict(r) for r in conn.execute(
        'SELECT id, ad, birim_fiyat, sira FROM cari_fiyat_kalemi WHERE firma_id = ? ORDER BY sira, id',
        (firma_id,))]


def _son_hareket(conn, firma_id):
    r = conn.execute('''SELECT tarih, tip, kalem_adi, miktar, tutar, aciklama FROM cari_hareket
                        WHERE firma_id = ? ORDER BY tarih DESC, id DESC LIMIT 1''', (firma_id,)).fetchone()
    return dict(r) if r else None


def firma_listesi(conn, tur):
    """Firmalar + bakiyeleri + son hareket. Son hareketi en yeni olan ustte."""
    firmalar = []
    for f in conn.execute('SELECT id, ad FROM cari_firma WHERE tur = ?', (tur,)):
        firmalar.append({
            'id': f['id'], 'ad': f['ad'],
            'bakiye': firma_bakiye(conn, f['id']),
            'son_hareket': _son_hareket(conn, f['id']),
        })
    firmalar.sort(key=lambda x: ortak.tr_kucuk(x['ad']))
    firmalar.sort(key=lambda x: x['son_hareket']['tarih'] if x['son_hareket'] else '', reverse=True)
    return firmalar


def tur_toplam_kalan(conn, tur):
    """Ana menu: o turdeki tum firmalarin kalanlari toplami (fazla odemeler dahil, net)."""
    ids = [r[0] for r in conn.execute('SELECT id FROM cari_firma WHERE tur = ?', (tur,))]
    return _para(sum(firma_bakiye(conn, i)['kalan'] for i in ids))


def _kalemleri_dogrula(kalemler):
    temiz, gorulen = [], set()
    for k in kalemler or []:
        ad = str(k.get('ad') or '').strip()
        fiyat_ham = k.get('birim_fiyat')
        if not ad and fiyat_ham in (None, ''):
            continue  # tamamen bos satir
        if not ad:
            raise CariHata('Fiyat kaleminin adı boş')
        fiyat = ortak.tutar_oku(fiyat_ham)
        if fiyat is None:
            raise CariHata('"%s" için geçerli bir birim fiyat girin' % ad)
        if ortak.tr_kucuk(ad) in gorulen:
            raise CariHata('"%s" kalemi iki kez yazılmış' % ad)
        gorulen.add(ortak.tr_kucuk(ad))
        try:
            kid = int(k.get('id')) if k.get('id') not in (None, '') else None
        except (TypeError, ValueError):
            kid = None
        temiz.append({'id': kid, 'ad': ad, 'birim_fiyat': fiyat})
    return temiz


def firma_kaydet(conn, tur, ad, kalemler, firma_id=None):
    """Yeni firma (firma_id=None) ya da guncelleme. Kalemler: gelen liste = son durum.

    Gelen listede olmayan eski kalemler silinir; o kaleme ait gecmis satirlar
    kalem_adi + kilitli fiyatla AYNEN kalir.
    """
    ad = str(ad or '').strip()
    if not ad:
        raise CariHata('Firma adını yazın')
    temiz = _kalemleri_dogrula(kalemler)
    ad = ' '.join(ad.split())
    anahtar = ortak.tr_kucuk(ad)
    ayni = [r for r in conn.execute('SELECT id, ad FROM cari_firma WHERE tur = ? AND id IS NOT ?', (tur, firma_id))
            if ortak.tr_kucuk(r['ad']) == anahtar]
    if ayni:
        raise CariHata('Bu adla bir %s zaten var' % TURLER[tur]['tekil'].lower())
    with conn:
        if firma_id is None:
            firma_id = conn.execute('INSERT INTO cari_firma (tur, ad) VALUES (?, ?)', (tur, ad)).lastrowid
            mevcut = set()
        else:
            conn.execute('UPDATE cari_firma SET ad = ? WHERE id = ?', (ad, firma_id))
            mevcut = {r[0] for r in conn.execute('SELECT id FROM cari_fiyat_kalemi WHERE firma_id = ?', (firma_id,))}
        kalan_idler = set()
        for sira, k in enumerate(temiz):
            if k['id'] in mevcut:
                conn.execute('UPDATE cari_fiyat_kalemi SET ad = ?, birim_fiyat = ?, sira = ? WHERE id = ?',
                             (k['ad'], k['birim_fiyat'], sira, k['id']))
                kalan_idler.add(k['id'])
            else:
                conn.execute('INSERT INTO cari_fiyat_kalemi (firma_id, ad, birim_fiyat, sira) VALUES (?,?,?,?)',
                             (firma_id, k['ad'], k['birim_fiyat'], sira))
        for silinecek in mevcut - kalan_idler:
            conn.execute('DELETE FROM cari_fiyat_kalemi WHERE id = ?', (silinecek,))
    return firma_id


def firma_sil(conn, firma_id):
    """Firma + tum hareketleri + kalemleri, tek transaction (yarim silme olmaz)."""
    with conn:
        conn.execute('DELETE FROM cari_hareket WHERE firma_id = ?', (firma_id,))
        conn.execute('DELETE FROM cari_fiyat_kalemi WHERE firma_id = ?', (firma_id,))
        conn.execute('DELETE FROM cari_firma WHERE id = ?', (firma_id,))


def hareket_kaydet(conn, firma_id, d, hareket_id=None):
    """Yeni hareket ya da duzenleme. Satirin tipi duzenlemede degismez."""
    eski = None
    if hareket_id is not None:
        eski = conn.execute('SELECT * FROM cari_hareket WHERE id = ?', (hareket_id,)).fetchone()
        if eski is None:
            raise CariHata('Kayit bulunamadi', 404)
        tip = eski['tip']
    else:
        tip = d.get('tip')
        if tip not in ('is', 'gider', 'odeme'):
            raise CariHata('Gecersiz kayit tipi')
    tarih = d.get('tarih') or ortak.bugun_tr()
    if not ortak.iso_tarih_mi(tarih):
        raise CariHata('Geçersiz tarih')
    aciklama = str(d.get('aciklama') or '').strip()
    kalem_id = kalem_adi = miktar = birim_fiyat = None

    if tip == 'is':
        miktar = ortak.tutar_oku(d.get('miktar'))
        if miktar is None:
            raise CariHata('Geçerli bir miktar girin')
        kid = d.get('kalem_id')
        kalem = None
        if kid not in (None, ''):
            try:
                kid = int(kid)
            except (TypeError, ValueError):
                raise CariHata('Fiyat kalemi seçin')
            kalem = conn.execute('SELECT * FROM cari_fiyat_kalemi WHERE id = ? AND firma_id = ?',
                                 (int(kid), firma_id)).fetchone()
        if eski is None:
            if kalem is None:
                raise CariHata('Fiyat kalemi seçin')
            birim_fiyat = kalem['birim_fiyat']   # FIYAT KILIDI: sunucudaki guncel fiyat
            kalem_id, kalem_adi = kalem['id'], kalem['ad']
        else:
            birim_fiyat = ortak.tutar_oku(d.get('birim_fiyat'))
            if birim_fiyat is None:
                raise CariHata('Geçerli bir birim fiyat girin')
            if kalem is not None:
                kalem_id, kalem_adi = kalem['id'], kalem['ad']
            elif kid not in (None, '') and eski['kalem_id'] is not None and int(kid) == eski['kalem_id']:
                kalem_id, kalem_adi = eski['kalem_id'], eski['kalem_adi']  # kalem silinmis, ad korunur
            else:
                raise CariHata('Fiyat kalemi bulunamadi')
        tutar = _para(miktar * birim_fiyat)
    else:
        tutar = ortak.tutar_oku(d.get('tutar'))
        if tutar is None:
            raise CariHata('Geçerli bir tutar girin')
        tutar = _para(tutar)

    with conn:
        if eski is None:
            hareket_id = conn.execute(
                '''INSERT INTO cari_hareket (firma_id, tarih, tip, kalem_id, kalem_adi, miktar,
                   birim_fiyat, tutar, aciklama) VALUES (?,?,?,?,?,?,?,?,?)''',
                (firma_id, tarih, tip, kalem_id, kalem_adi, miktar, birim_fiyat, tutar, aciklama)).lastrowid
        else:
            conn.execute('''UPDATE cari_hareket SET tarih=?, kalem_id=?, kalem_adi=?, miktar=?,
                            birim_fiyat=?, tutar=?, aciklama=? WHERE id=?''',
                         (tarih, kalem_id, kalem_adi, miktar, birim_fiyat, tutar, aciklama, hareket_id))
    return hareket_id


def defter(conn, firma_id, bas=None, bit=None):
    """Eskiden yeniye hareketler (tarih, sonra giris sirasi)."""
    return [dict(r) for r in conn.execute(
        '''SELECT id, tarih, tip, kalem_id, kalem_adi, miktar, birim_fiyat, tutar, aciklama
           FROM cari_hareket WHERE firma_id = ? AND (? IS NULL OR tarih >= ?) AND (? IS NULL OR tarih <= ?)
           ORDER BY tarih, id''', (firma_id, bas, bas, bit, bit))]


def hareket_aciklama(h, ayar):
    """Defter/PDF'teki aciklama: ust satir + alt satir (12 m³ × ₺3.250)."""
    if h['tip'] == 'is':
        ust = h['kalem_adi'] or ayar['is_adi']
        alt = '%s %s × %s' % (ortak.miktar_tr(h['miktar'], 3), ayar['birim'], ortak.para_tl(h['birim_fiyat']))
        if h['aciklama']:
            alt += ' · ' + h['aciklama']
        return ust, alt
    if h['tip'] == 'gider':
        return (h['aciklama'] or 'Gider'), 'Gider'
    return (h['aciklama'] or ayar['odeme_fiil']), ayar['odeme_fiil'] + ' para'


def dokum_verisi(conn, firma_id, bas=None, bit=None):
    """Hesap dokumu (PDF) icin veri. Aralik secilirse oncesi 'devir' olur ve
    KALAN = bit tarihindeki gercek bakiye (devir + donem hakedis - donem odenen)."""
    firma = firma_getir(conn, firma_id)
    devir = None
    if bas:
        onceki_gun = (date.fromisoformat(bas) - timedelta(days=1)).isoformat()
        devir = firma_bakiye(conn, firma_id, bit=onceki_gun)['kalan']
    return {
        'firma': firma,
        'ayar': TURLER[firma['tur']],
        'bas': bas, 'bit': bit,
        'devir': devir,
        'satirlar': defter(conn, firma_id, bas, bit),
        'donem': firma_bakiye(conn, firma_id, bas, bit),
        'kalan': firma_bakiye(conn, firma_id, bit=bit)['kalan'],
    }


def gun_sonu_verisi(conn, tur, tarih, firma_id=None):
    """Gun sonu raporu (ekran + A4 PDF ayni veriyi kullanir).

    Neyi cozuyoruz: Santiyede gun bitince "bugun kime ne kadar beton dokuldu,
    kimden ne kadar para alindi, herkesin son durumu ne" sorusu tek sayfada.
    Kalan = o GUNUN SONUNDAKI bakiye (gecmis gunun raporu tekrar alininca
    ayni rakam cikar; bugunun raporunda guncel kalanla aynidir).
    Nasil test ederiz: test_gun_sonu.py.
    """
    if firma_id is not None:
        f = firma_getir(conn, firma_id, tur)
        firmalar = [(f['id'], f['ad'])]
    else:
        firmalar = [(r['id'], r['ad']) for r in conn.execute('SELECT id, ad FROM cari_firma WHERE tur = ?', (tur,))]
    firmalar.sort(key=lambda x: ortak.tr_kucuk(x[1]))
    ad_map = dict(firmalar)

    hareketler = []
    if firmalar:
        yer = ','.join('?' * len(firmalar))
        for r in conn.execute(
                'SELECT * FROM cari_hareket WHERE tarih = ? AND firma_id IN (%s) ORDER BY id' % yer,
                [tarih] + [f[0] for f in firmalar]):
            h = dict(r)
            h['firma_adi'] = ad_map[h['firma_id']]
            hareketler.append(h)
    hareketler.sort(key=lambda h: (ortak.tr_kucuk(h['firma_adi']), h['id']))

    hareketli = {h['firma_id'] for h in hareketler}
    satirlar = []
    toplam_kalan = 0.0
    for fid, ad in firmalar:
        kalan = firma_bakiye(conn, fid, bit=tarih)['kalan']
        toplam_kalan += kalan
        if fid in hareketli:
            gun = firma_bakiye(conn, fid, bas=tarih, bit=tarih)
            satirlar.append({'id': fid, 'ad': ad, 'miktar': gun['is_miktar'], 'hakedis': gun['hakedis'],
                             'odenen': gun['odenen'], 'kalan': kalan})
    return {
        'tarih': tarih,
        'tur': tur,
        'ayar': TURLER[tur],
        'kapsam': ad_map[firma_id] if firma_id is not None else 'Tümü',
        'firma_id': firma_id,
        'firmalar': satirlar,
        'hareketler': hareketler,
        'ozet': {
            'miktar': round(sum(s['miktar'] for s in satirlar), 3),
            'hakedis': _para(sum(s['hakedis'] for s in satirlar)),
            'odenen': _para(sum(s['odenen'] for s in satirlar)),
            'toplam_kalan': _para(toplam_kalan),
            'firma_sayisi': len(satirlar),
        },
    }


AYAR_VARSAYILAN = {'rapor_basligi': '[FİRMA ADI]'}


def ayar_oku(conn, anahtar):
    r = conn.execute('SELECT deger FROM cari_ayar WHERE anahtar = ?', (anahtar,)).fetchone()
    return r['deger'] if r and r['deger'] else AYAR_VARSAYILAN.get(anahtar, '')


def ayar_yaz(conn, anahtar, deger):
    if anahtar not in AYAR_VARSAYILAN:
        raise CariHata('Bilinmeyen ayar')
    deger = ' '.join(str(deger or '').split())[:120]
    with conn:
        conn.execute('INSERT OR REPLACE INTO cari_ayar (anahtar, deger) VALUES (?, ?)', (anahtar, deger))


# ====================================================================
# API
# ====================================================================
def _tur_kontrol(tur):
    if tur not in AKTIF_TURLER:
        abort(404)
    return TURLER[tur]


def _tarih_param(ad):
    t = (request.args.get(ad) or '').strip() or None
    if t and not ortak.iso_tarih_mi(t):
        raise CariHata('Geçersiz tarih: ' + t)
    return t


@bp.route('/api/cari/<tur>/firmalar', methods=['GET', 'POST'])
def api_firmalar(tur):
    _tur_kontrol(tur)
    conn = ortak.baglan()
    try:
        if request.method == 'POST':
            d = request.json or {}
            fid = firma_kaydet(conn, tur, d.get('ad'), d.get('kalemler'))
            return jsonify({'success': True, 'id': fid})
        return jsonify({'firmalar': firma_listesi(conn, tur), 'toplam_kalan': tur_toplam_kalan(conn, tur)})
    finally:
        conn.close()


@bp.route('/api/cari/firma/<int:firma_id>', methods=['GET', 'PUT', 'DELETE'])
def api_firma(firma_id):
    conn = ortak.baglan()
    try:
        firma = firma_getir(conn, firma_id)
        if request.method == 'PUT':
            d = request.json or {}
            firma_kaydet(conn, firma['tur'], d.get('ad'), d.get('kalemler'), firma_id=firma_id)
            return jsonify({'success': True, 'id': firma_id})
        if request.method == 'DELETE':
            firma_sil(conn, firma_id)
            return jsonify({'success': True})
        return jsonify({
            'firma': firma,
            'kalemler': kalemleri_getir(conn, firma_id),
            'bakiye': firma_bakiye(conn, firma_id),
            'defter': defter(conn, firma_id),
        })
    finally:
        conn.close()


@bp.route('/api/cari/firma/<int:firma_id>/hareket', methods=['POST'])
def api_hareket_ekle(firma_id):
    conn = ortak.baglan()
    try:
        firma_getir(conn, firma_id)
        hid = hareket_kaydet(conn, firma_id, request.json or {})
        return jsonify({'success': True, 'id': hid})
    finally:
        conn.close()


@bp.route('/api/cari/hareket/<int:hareket_id>', methods=['PUT', 'DELETE'])
def api_hareket(hareket_id):
    conn = ortak.baglan()
    try:
        h = conn.execute('SELECT firma_id FROM cari_hareket WHERE id = ?', (hareket_id,)).fetchone()
        if h is None:
            raise CariHata('Kayit bulunamadi', 404)
        firma_getir(conn, h['firma_id'])
        if request.method == 'DELETE':
            with conn:
                conn.execute('DELETE FROM cari_hareket WHERE id = ?', (hareket_id,))
            return jsonify({'success': True})
        hareket_kaydet(conn, h['firma_id'], request.json or {}, hareket_id=hareket_id)
        return jsonify({'success': True, 'id': hareket_id})
    finally:
        conn.close()


def _gun_sonu_param(tur):
    tarih = _tarih_param('tarih') or ortak.bugun_tr()
    fid = (request.args.get('firma_id') or '').strip()
    try:
        fid = int(fid) if fid else None
    except ValueError:
        raise CariHata('Geçersiz firma')
    return tarih, fid


@bp.route('/api/cari/<tur>/gun-sonu')
def api_gun_sonu(tur):
    _tur_kontrol(tur)
    tarih, fid = _gun_sonu_param(tur)
    conn = ortak.baglan()
    try:
        v = gun_sonu_verisi(conn, tur, tarih, fid)
        v['rapor_basligi'] = ayar_oku(conn, 'rapor_basligi')
        return jsonify(v)
    finally:
        conn.close()


@bp.route('/api/cari/ayar', methods=['GET', 'POST'])
def api_ayar():
    conn = ortak.baglan()
    try:
        if request.method == 'POST':
            for k, v in (request.json or {}).items():
                ayar_yaz(conn, k, v)
            return jsonify({'success': True})
        return jsonify({k: ayar_oku(conn, k) for k in AYAR_VARSAYILAN})
    finally:
        conn.close()


# ====================================================================
# PDF - FIRMA HESAP DOKUMU
# ====================================================================
def _dosya_adi(metin):
    tablo = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')
    return re.sub(r'[^A-Za-z0-9]+', '_', metin.translate(tablo)).strip('_') or 'firma'


def pdf_para(deger, font_adi):
    """DejaVu/Arial fontunda ₺ isareti var; Helvetica yedeginde yok -> 'TL' yazilir."""
    metin = ortak.para_tl(deger)
    return metin if not font_adi.startswith('Helvetica') else metin.replace('₺', '') + ' TL'


@bp.route('/api/cari/firma/<int:firma_id>/pdf')
def api_firma_pdf(firma_id):
    try:
        from xml.sax.saxutils import escape
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return jsonify({'error': 'PDF icin reportlab kurulu degil'}), 503

    bas, bit = _tarih_param('bas'), _tarih_param('bit')
    if bas and bit and bas > bit:
        raise CariHata('Başlangıç tarihi bitişten sonra olamaz')
    conn = ortak.baglan()
    try:
        v = dokum_verisi(conn, firma_id, bas, bit)
    finally:
        conn.close()
    ayar, firma = v['ayar'], v['firma']

    font_n, font_b = ortak._pdf_font_hazirla(pdfmetrics, TTFont)
    if not font_n.startswith('Helvetica'):
        # Paragraph icindeki <b> etiketi kalin fonta gitsin
        pdfmetrics.registerFontFamily(font_n, normal=font_n, bold=font_b, italic=font_n, boldItalic=font_b)

    def tl(x):
        return pdf_para(x, font_n)

    stiller = getSampleStyleSheet()
    s_baslik = ParagraphStyle('CdBaslik', parent=stiller['Title'], fontName=font_b, fontSize=17,
                              alignment=0, spaceAfter=2)
    s_alt = ParagraphStyle('CdAlt', parent=stiller['Normal'], fontName=font_n, fontSize=9.5,
                           textColor=colors.HexColor('#555555'))
    s_hucre = ParagraphStyle('CdHucre', parent=stiller['Normal'], fontName=font_n, fontSize=8.5, leading=10.5)
    s_hucre_alt = ParagraphStyle('CdHucreAlt', parent=s_hucre, fontSize=7.5, leading=9,
                                 textColor=colors.HexColor('#666666'))

    aralik = 'Tüm kayıtlar'
    if bas or bit:
        aralik = '%s – %s' % (ortak.tarih_tr(bas) if bas else 'başlangıç', ortak.tarih_tr(bit) if bit else 'bugün')

    el = [
        Paragraph(escape(firma['ad']), s_baslik),
        Paragraph('%s hesap dökümü · Tarih aralığı: %s' % (ayar['tekil'], escape(aralik)), s_alt),
        Spacer(1, 10),
    ]
    if v['devir'] is not None:
        el.append(Paragraph('<b>Devreden bakiye</b> (%s öncesi): %s' % (ortak.tarih_tr(bas), tl(v['devir'])), s_hucre))
        el.append(Spacer(1, 6))

    tablo = [['Tarih', 'Açıklama', 'Miktar', 'Birim fiyat', 'Hakediş', ayar['odeme_kolon']]]
    for h in v['satirlar']:
        ust, alt = hareket_aciklama(h, ayar)
        aciklama = [Paragraph(escape(ust), s_hucre)]
        if h['tip'] != 'is' and alt:
            aciklama.append(Paragraph(escape(alt), s_hucre_alt))
        elif h['tip'] == 'is' and h['aciklama']:
            aciklama.append(Paragraph(escape(h['aciklama']), s_hucre_alt))
        odeme = h['tip'] == 'odeme'
        tablo.append([
            ortak.tarih_tr(h['tarih']),
            aciklama,
            ('%s %s' % (ortak.miktar_tr(h['miktar'], 3), ayar['birim'])) if h['tip'] == 'is' else '',
            tl(h['birim_fiyat']) if h['tip'] == 'is' else '',
            '' if odeme else tl(h['tutar']),
            tl(h['tutar']) if odeme else '',
        ])
    if len(tablo) == 1:
        tablo.append(['', 'Bu aralıkta kayıt yok', '', '', '', ''])
    tablo.append(['', 'Toplam', ('%s %s' % (ortak.miktar_tr(v['donem']['is_miktar'], 3), ayar['birim'])),
                  '', tl(v['donem']['hakedis']), tl(v['donem']['odenen'])])

    t = Table(tablo, repeatRows=1, colWidths=[2.0 * cm, 6.2 * cm, 2.1 * cm, 2.5 * cm, 2.6 * cm, 2.6 * cm])
    stil = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#14161a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), font_b),
        ('FONTNAME', (0, 1), (-1, -1), font_n),
        ('FONTNAME', (0, -1), (-1, -1), font_b),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 0), (-1, -2), 0.4, colors.HexColor('#dddddd')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#14161a')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f2f3f5')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    t.setStyle(TableStyle(stil))
    el.append(t)
    el.append(Spacer(1, 12))

    kalan = v['kalan']
    etiket = 'FAZLA ÖDEME' if kalan < 0 else ayar['kalan_etiket'].upper()
    if bit:
        etiket += ' (%s itibarıyla)' % ortak.tarih_tr(bit)
    ozet = [[etiket, tl(abs(kalan))]]
    o = Table(ozet, colWidths=[12.4 * cm, 5.6 * cm])
    o.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_b),
        ('FONTSIZE', (0, 0), (-1, -1), 13),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#14161a')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    el.append(o)
    el.append(Spacer(1, 14))
    el.append(Paragraph('Oluşturma: ' + ortak.simdi_tr().strftime('%d.%m.%Y %H:%M'), s_alt))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            leftMargin=1.5 * cm - 6, rightMargin=1.5 * cm - 6,
                            title='%s - Hesap Dokumu' % firma['ad'])
    doc.build(el)
    buf.seek(0)
    ad = 'dokum_%s_%s.pdf' % (_dosya_adi(firma['ad']), ortak.bugun_tr())
    # Satir ici: Safari PDF'i acar, kullanici Paylas menusunden WhatsApp/Mail'e gonderir.
    return send_file(buf, mimetype='application/pdf', as_attachment=False, download_name=ad)


# ====================================================================
# PDF - GUN SONU RAPORU (A4)
# ====================================================================
@bp.route('/api/cari/<tur>/gun-sonu/pdf')
def api_gun_sonu_pdf(tur):
    try:
        from xml.sax.saxutils import escape
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return jsonify({'error': 'PDF icin reportlab kurulu degil'}), 503

    ayar = _tur_kontrol(tur)
    tarih, fid = _gun_sonu_param(tur)
    conn = ortak.baglan()
    try:
        v = gun_sonu_verisi(conn, tur, tarih, fid)
        baslik = ayar_oku(conn, 'rapor_basligi')
    finally:
        conn.close()

    font_n, font_b = ortak._pdf_font_hazirla(pdfmetrics, TTFont)
    if not font_n.startswith('Helvetica'):
        pdfmetrics.registerFontFamily(font_n, normal=font_n, bold=font_b, italic=font_n, boldItalic=font_b)

    def tl(x):
        return pdf_para(x, font_n)

    koyu = colors.HexColor('#14161a')
    soluk = colors.HexColor('#666666')
    cizgi = colors.HexColor('#dddddd')
    stiller = getSampleStyleSheet()
    s_firma = ParagraphStyle('GsFirma', parent=stiller['Normal'], fontName=font_b, fontSize=18, leading=22)
    s_rapor = ParagraphStyle('GsRapor', parent=stiller['Normal'], fontName=font_b, fontSize=11, leading=14,
                             alignment=2)
    s_rapor_alt = ParagraphStyle('GsRaporAlt', parent=s_rapor, fontName=font_n, fontSize=10, textColor=soluk)
    s_alt = ParagraphStyle('GsAlt', parent=stiller['Normal'], fontName=font_n, fontSize=9, textColor=soluk)
    s_bolum = ParagraphStyle('GsBolum', parent=stiller['Normal'], fontName=font_b, fontSize=11.5, leading=14,
                             spaceBefore=4, spaceAfter=5)
    s_hucre = ParagraphStyle('GsHucre', parent=stiller['Normal'], fontName=font_n, fontSize=8.5, leading=10.5)
    s_hucre_alt = ParagraphStyle('GsHucreAlt', parent=s_hucre, fontSize=7.5, leading=9, textColor=soluk)
    s_kutu_e = ParagraphStyle('GsKutuE', parent=stiller['Normal'], fontName=font_n, fontSize=8, textColor=soluk,
                              leading=10)
    s_kutu_d = ParagraphStyle('GsKutuD', parent=stiller['Normal'], fontName=font_b, fontSize=13, leading=16)

    tam = 18 * cm
    el = []
    # --- Baslik: solda rapor basligi (firma adiniz), sagda rapor adi + tarih
    ust = Table([[Paragraph(escape(baslik), s_firma),
                  [Paragraph('GÜN SONU RAPORU', s_rapor),
                   Paragraph(ortak.tarih_tr(tarih), s_rapor_alt)]]],
                colWidths=[11 * cm, 7 * cm])
    ust.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                             ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                             ('LINEBELOW', (0, 0), (-1, 0), 1.5, koyu), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
    el += [ust, Spacer(1, 6),
           Paragraph('%s · Kapsam: %s' % (escape(ayar['baslik']), escape(v['kapsam'])), s_alt), Spacer(1, 10)]

    # --- Ozet kutulari
    o = v['ozet']
    kutular = [
        ('Toplam miktar', '%s %s' % (ortak.miktar_tr(o['miktar'], 3), ayar['birim'])),
        ('Günün hakedişi', tl(o['hakedis'])),
        (ayar['gun_odeme_etiket'], tl(o['odenen'])),
        (('Gün sonu ' + ayar['toplam_etiket'].lower()) if o['toplam_kalan'] >= 0 else 'Gün sonu fazla ödeme',
         tl(abs(o['toplam_kalan']))),
    ]
    kt = Table([[[Paragraph(escape(e), s_kutu_e), Paragraph(escape(d), s_kutu_d)] for e, d in kutular]],
               colWidths=[tam / 4] * 4)
    kt.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.8, cizgi), ('INNERGRID', (0, 0), (-1, -1), 0.8, cizgi),
                            ('BACKGROUND', (3, 0), (3, 0), colors.HexColor('#f2f3f5')),
                            ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                            ('LEFTPADDING', (0, 0), (-1, -1), 8), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    el += [kt, Spacer(1, 14)]

    tablo_stili = [
        ('BACKGROUND', (0, 0), (-1, 0), koyu), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), font_b), ('FONTNAME', (0, 1), (-1, -1), font_n),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5), ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LINEBELOW', (0, 0), (-1, -1), 0.4, cizgi),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]

    if not v['firmalar']:
        el.append(Paragraph('Bu tarihte kayıt yok.', s_hucre))
    else:
        # --- Firma ozet tablosu + toplam
        el.append(Paragraph('Firma özeti', s_bolum))
        ft = [['Firma', 'Miktar', 'Hakediş', ayar['odeme_kolon'], 'Gün sonu kalan']]
        for s in v['firmalar']:
            ft.append([Paragraph(escape(s['ad']), s_hucre),
                       ('%s %s' % (ortak.miktar_tr(s['miktar'], 3), ayar['birim'])) if s['miktar'] else '',
                       tl(s['hakedis']) if s['hakedis'] else '', tl(s['odenen']) if s['odenen'] else '',
                       tl(s['kalan'])])
        ft.append(['Toplam', '%s %s' % (ortak.miktar_tr(o['miktar'], 3), ayar['birim']), tl(o['hakedis']),
                   tl(o['odenen']), ''])
        t = Table(ft, repeatRows=1, colWidths=[6.6 * cm, 2.4 * cm, 3 * cm, 3 * cm, 3 * cm])
        t.setStyle(TableStyle(tablo_stili + [
            ('FONTNAME', (0, -1), (-1, -1), font_b), ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f2f3f5')),
            ('LINEABOVE', (0, -1), (-1, -1), 1, koyu)]))
        el += [t, Spacer(1, 4)]
        if any(s['kalan'] < 0 for s in v['firmalar']):
            el.append(Paragraph('Eksi kalan = fazla ödeme.', s_alt))
        el.append(Spacer(1, 12))

        # --- Gunun hareketleri
        el.append(Paragraph('Günün hareketleri', s_bolum))
        ht = [['Firma', 'Açıklama', 'Hakediş', ayar['odeme_kolon']]]
        for h in v['hareketler']:
            ust_m, alt_m = hareket_aciklama(h, ayar)
            odeme = h['tip'] == 'odeme'
            ht.append([Paragraph(escape(h['firma_adi']), s_hucre),
                       [Paragraph(escape(ust_m), s_hucre), Paragraph(escape(alt_m), s_hucre_alt)],
                       '' if odeme else tl(h['tutar']), tl(h['tutar']) if odeme else ''])
        t2 = Table(ht, repeatRows=1, colWidths=[5 * cm, 7 * cm, 3 * cm, 3 * cm])
        t2.setStyle(TableStyle(tablo_stili + [('ALIGN', (1, 0), (1, -1), 'LEFT')]))
        el.append(t2)

    # --- Olusturma zamani + imza alani
    el += [Spacer(1, 26)]
    imza = Table([['Hazırlayan', '', 'Kontrol eden / Teslim alan'],
                  ['Ad Soyad / İmza', '', 'Ad Soyad / İmza']],
                 colWidths=[7.5 * cm, 3 * cm, 7.5 * cm], rowHeights=[16, 40])
    imza.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, 0), font_b), ('FONTNAME', (0, 1), (-1, 1), font_n),
                              ('FONTSIZE', (0, 0), (-1, -1), 8.5), ('TEXTCOLOR', (0, 1), (-1, 1), soluk),
                              ('VALIGN', (0, 1), (-1, 1), 'BOTTOM'),
                              ('LINEBELOW', (0, 1), (0, 1), 0.8, koyu), ('LINEBELOW', (2, 1), (2, 1), 0.8, koyu),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    el += [imza, Spacer(1, 14), Paragraph('Oluşturma: ' + ortak.simdi_tr().strftime('%d.%m.%Y %H:%M'), s_alt)]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            leftMargin=1.5 * cm - 6, rightMargin=1.5 * cm - 6,
                            title='Gun Sonu Raporu %s' % ortak.tarih_tr(tarih))
    doc.build(el)
    buf.seek(0)
    ek = ('_' + _dosya_adi(v['kapsam'])) if fid is not None else ''
    ad = 'gun_sonu_%s%s_%s.pdf' % (tur, ek, tarih)
    return send_file(buf, mimetype='application/pdf', as_attachment=False, download_name=ad)


# ====================================================================
# SAYFALAR
# ====================================================================
CARI_CSS = r'''
body.alt-butonlu{padding-bottom:calc(96px + env(safe-area-inset-bottom))}
.alt-baslik{font-size:14px;color:var(--soluk);margin-top:2px}
.ust-btnlar{display:flex;gap:8px;align-items:center;flex-shrink:0}
.hap-btn{height:36px;padding:0 14px;border-radius:18px;border:1px solid var(--cizgi);background:var(--kart);color:var(--tx);display:flex;align-items:center;font-size:14px;font-weight:600;text-decoration:none;white-space:nowrap}
.alan select{background:#fff}
.gs-satir{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:11px 14px;border-bottom:1px solid var(--cizgi);text-decoration:none;color:var(--tx)}
.gs-satir:last-child{border-bottom:none}
.gs-satir .sol{min-width:0}
.gs-satir .ad{font-size:15px;font-weight:600;overflow-wrap:anywhere}
.gs-satir .alt{font-size:12px;color:var(--soluk);margin-top:2px}
.gs-satir .sag{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.gs-satir .sag .t{font-size:14px;font-weight:700}
.gs-satir .sag .n{font-size:11px;color:var(--soluk)}
.alt-baslik b{font-variant-numeric:tabular-nums}
.arama{width:100%;padding:11px 12px;border:1px solid var(--cizgi);border-radius:10px;background:#fff;color:var(--tx);font-size:16px;margin-bottom:12px;-webkit-appearance:none;appearance:none}
.alt-sabit{position:fixed;left:0;right:0;bottom:0;padding:10px 16px calc(10px + env(safe-area-inset-bottom));background:linear-gradient(to top,var(--bg) 70%,#f4f5f700);z-index:5}
.firma-kalan{text-align:right;white-space:nowrap}
.firma-kalan .tutar{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums}
.firma-kalan .not{font-size:11px;color:var(--soluk)}
.kalem-satir{display:grid;grid-template-columns:minmax(0,1fr) 110px 36px;gap:6px;margin-bottom:6px}
.kalem-satir input{width:100%;padding:11px 10px;border:1px solid var(--cizgi);border-radius:10px;background:#fff;color:var(--tx);font-size:16px;-webkit-appearance:none;appearance:none}
.kalem-satir .k-sil{border:none;background:var(--bg);border-radius:10px;font-size:20px;color:var(--soluk);cursor:pointer}
.bilgi{font-size:12px;color:var(--soluk);margin:4px 0 12px;line-height:1.4}
.btn-link{background:none;border:none;color:var(--tx);font-size:15px;font-weight:600;padding:8px 0;cursor:pointer;text-decoration:underline}
.siyah-ust{background:#14161a;color:#fff;margin:calc(-12px - env(safe-area-inset-top)) calc(-16px - env(safe-area-inset-right)) 14px calc(-16px - env(safe-area-inset-left));
  padding:calc(12px + env(safe-area-inset-top)) calc(16px + env(safe-area-inset-right)) 18px calc(16px + env(safe-area-inset-left))}
.su-ust{display:flex;justify-content:space-between;align-items:center}
.su-geri{color:#c9ccd1;text-decoration:none;font-size:15px;padding:4px 0}
.su-btnlar{display:flex;gap:8px}
.su-btn{height:34px;padding:0 12px;border-radius:17px;border:1px solid #ffffff33;background:#ffffff14;color:#fff;font-size:13px;font-weight:600;cursor:pointer}
.su-btn.yuvarlak{width:34px;padding:0}
.su-ad{font-size:22px;font-weight:700;margin-top:10px;overflow-wrap:anywhere}
.su-etiket{font-size:13px;color:#c9ccd1;margin-top:12px}
.su-kalan{font-size:32px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.5px}
.su-kalan.fazla{color:#ffb4a9}
.su-ozet{font-size:12px;color:#c9ccd1;margin-top:4px}
.kart-kutu{background:var(--kart);border:1px solid var(--cizgi);border-radius:14px;padding:12px;margin-bottom:14px}
.kart-kutu .secim{margin-bottom:10px}
.iki-alan{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.onizleme{font-size:13px;color:var(--soluk);margin:-4px 0 10px;min-height:18px}
.onizleme b{color:var(--tx)}
.cipler{display:flex;gap:6px;margin:-4px 0 12px}
.cip{border:1px solid var(--cizgi);background:#fff;border-radius:16px;padding:6px 12px;font-size:13px;color:var(--tx);cursor:pointer}
.defter-baslik{display:flex;justify-content:space-between;align-items:baseline;margin:4px 4px 6px}
.defter-baslik h2{font-size:16px}
.d-grid{display:grid;grid-template-columns:66px minmax(0,1fr) 76px 76px;gap:6px;align-items:center;width:100%}
.d-bas{padding:8px 12px;font-size:11px;font-weight:700;color:var(--soluk);text-transform:uppercase;letter-spacing:.3px;border-bottom:1px solid var(--cizgi);background:#fafafa}
.defter .satir-ic{padding:10px 12px}
.defter .satir-sol{flex:1}
.d-tarih{font-size:12px;color:var(--soluk);font-variant-numeric:tabular-nums}
.d-acik .u{font-size:14px;font-weight:600;overflow-wrap:anywhere}
.d-acik .a{font-size:12px;color:var(--soluk);margin-top:1px;overflow-wrap:anywhere}
.d-tutar{font-size:13px;font-weight:600;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.d-sag{text-align:right}
.onceki{padding:11px 12px;border-bottom:1px solid var(--cizgi);background:#fafafa;cursor:pointer;-webkit-tap-highlight-color:transparent}
.onceki .d-acik .u{font-weight:600;color:var(--soluk)}
.d-toplam{padding:10px 12px;border-top:2px solid var(--tx);font-weight:700}
.d-toplam .d-tutar{font-weight:700}
.d-kalan{display:flex;justify-content:space-between;align-items:center;padding:14px 12px;background:#14161a;color:#fff}
.d-kalan .e{font-size:14px;font-weight:700;letter-spacing:.3px;text-transform:uppercase}
.d-kalan .t{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums}
.d-kalan.fazla .t{color:#ffb4a9}
'''

# Firma ekle/duzenle formu: liste sayfasinda ve firma sayfasinda AYNI.
FIRMA_FORM_HTML = r'''
<div class="modal-arka gizli" id="firma-form" onclick="arkaTik(event, 'firma-form')">
  <div class="modal">
    <div class="modal-ust"><h2 id="ff-baslik">Firma</h2><button class="kapat" onclick="modalKapat('firma-form')" aria-label="Kapat">&times;</button></div>
    <div class="alan"><label for="ff-ad">Firma adı</label><input type="text" id="ff-ad" autocomplete="off"></div>
    <label style="display:block;font-size:12px;color:var(--soluk);margin-bottom:4px" id="ff-kalem-etiket">Birim fiyat kalemleri</label>
    <div id="ff-kalemler"></div>
    <button type="button" class="btn-link" onclick="kalemSatiriEkle()">+ Yeni kalem ekle</button>
    <div class="bilgi" id="ff-bilgi"></div>
    <button class="btn" id="ff-kaydet" onclick="firmaKaydet()">Kaydet</button>
  </div>
</div>
'''

FIRMA_FORM_JS = r'''
function el(id) { return document.getElementById(id); }
var FF_ID = null;
function firmaFormAc(firma, kalemler) {
  FF_ID = firma ? firma.id : null;
  el('ff-baslik').textContent = firma ? AYAR.tekil + ' Düzenle' : 'Yeni ' + AYAR.tekil;
  el('ff-ad').value = firma ? firma.ad : '';
  el('ff-ad').placeholder = AYAR.tekil + ' adı';
  el('ff-kalem-etiket').textContent = 'Birim fiyat kalemleri (₺/' + AYAR.birim + ')';
  el('ff-bilgi').textContent = AYAR.kalem_ipucu + '. Fiyatı değiştirmek geçmiş kayıtları değiştirmez; ' +
    'silinen kalemin eski satırları defterde aynen kalır.';
  el('ff-kalemler').innerHTML = '';
  var liste = (kalemler && kalemler.length) ? kalemler : [{}];
  for (var i = 0; i < liste.length; i++) kalemSatiriEkle(liste[i]);
  modalAc('firma-form');
}
function kalemSatiriEkle(k) {
  k = k || {};
  var div = document.createElement('div');
  div.className = 'kalem-satir';
  if (k.id) div.setAttribute('data-id', k.id);
  div.innerHTML = '<input type="text" class="k-ad" autocomplete="off" placeholder="' + escHtml(AYAR.kalem_ornek) + '" value="' + escHtml(k.ad || '') + '">' +
    '<input type="text" class="k-fiyat" inputmode="decimal" autocomplete="off" placeholder="₺/' + escHtml(AYAR.birim) + '" value="' + (k.birim_fiyat ? tlInputYaz(k.birim_fiyat) : '') + '">' +
    '<button type="button" class="k-sil" aria-label="Kalemi sil" title="Kalemi sil">&times;</button>';
  div.querySelector('.k-sil').onclick = function() { div.parentNode.removeChild(div); };
  el('ff-kalemler').appendChild(div);
}
function firmaKaydet() {
  var ad = el('ff-ad').value.trim();
  if (!ad) { toast('Firma adını yazın'); return; }
  var satirlar = el('ff-kalemler').querySelectorAll('.kalem-satir');
  var kalemler = [];
  for (var i = 0; i < satirlar.length; i++) {
    var kad = satirlar[i].querySelector('.k-ad').value.trim();
    var fstr = satirlar[i].querySelector('.k-fiyat').value.trim();
    if (!kad && !fstr) continue;
    var f = parseTLInput(fstr);
    if (!kad) { toast('Kalem adı boş'); return; }
    if (isNaN(f) || f <= 0) { toast('"' + kad + '" için birim fiyat girin'); return; }
    var kid = satirlar[i].getAttribute('data-id');
    kalemler.push({id: kid ? Number(kid) : null, ad: kad, birim_fiyat: f});
  }
  var veri = {ad: ad, kalemler: kalemler};
  var istek = FF_ID === null ? jsonGonder('/api/cari/' + AYAR.tur + '/firmalar', 'POST', veri)
                             : jsonGonder('/api/cari/firma/' + FF_ID, 'PUT', veri);
  var btn = el('ff-kaydet');
  btn.disabled = true;
  istek.then(function(r) {
    modalKapat('firma-form');
    if (FF_ID === null) { location.href = '/' + AYAR.tur + '/' + r.id; return; }
    toast('Kaydedildi');
    firmaKaydedildi();
  }).catch(function(e) { toast(e.message); })
    .then(function() { btn.disabled = false; });
}
'''

LISTE_HTML = r'''<!DOCTYPE html>
<html lang="tr">
<head>
{{ ortak_head|safe }}
<title>{{ ayar.baslik }}</title>
<style>{{ ortak_css|safe }}{{ cari_css|safe }}</style>
</head>
<body class="alt-butonlu">
<a href="/" class="geri">&#8249; Ana Menü</a>
<div class="ust">
  <div>
    <h1>{{ ayar.baslik }}</h1>
    <div class="alt-baslik" id="toplam">&nbsp;</div>
  </div>
  <div class="ust-btnlar">
    <a class="hap-btn" href="/{{ ayar.tur }}/gun-sonu" title="Günün özeti ve A4 PDF raporu">Gün Sonu</a>
    <button class="yardim-btn" onclick="modalAc('yardim')" aria-label="Yardım" title="Yardım">?</button>
  </div>
</div>
<input type="search" class="arama" id="arama" placeholder="Firma ara…" oninput="ciz()" autocomplete="off">
<div id="liste"><div class="bos">Yükleniyor…</div></div>
<div class="ipucu" id="ipucu" style="display:none">Açmak için dokunun · Düzenle / Sil için sola kaydırın</div>
<div class="alt-sabit"><button class="btn" onclick="firmaFormAc(null, null)">{{ ayar.ekle_btn }}</button></div>

{{ firma_form_html|safe }}

<div class="modal-arka gizli" id="yardim" onclick="arkaTik(event, 'yardim')">
  <div class="modal yardim">
    <div class="modal-ust"><h2>{{ ayar.baslik }} — Nasıl kullanılır?</h2><button class="kapat" onclick="modalKapat('yardim')" aria-label="Kapat">&times;</button></div>
    <ol>
      <li><b>{{ ayar.ekle_btn }}</b> ile firmayı ekleyin: firma adı ve birim fiyat kalemleri (ör. {{ ayar.kalem_ornek }} — ₺/{{ ayar.birim }}).</li>
      <li>Firmaya dokunun; açılan sayfada <b>{{ ayar.is_sekme }}</b>, <b>Gider</b> ve <b>{{ ayar.odeme_sekme }}</b> satırlarını girin.</li>
      <li>Firmanın adını veya fiyatlarını değiştirmek için satırı <b>sola kaydırıp Düzenle</b>'ye basın.</li>
      <li><b>Sil</b> firmayı ve tüm kayıtlarını kalıcı olarak siler; onay sorulur.</li>
      <li><b>Gün Sonu</b> (sağ üstte): seçtiğiniz günün özeti ve imzalı A4 PDF raporu.</li>
    </ol>
    <p>Listede her firmanın güncel kalanı görünür. {{ ayar.yon_aciklama }} Eksi çıkarsa <b>Fazla ödeme</b> yazar.</p>
    <button class="btn" style="margin-top:14px" onclick="modalKapat('yardim')">Anladım</button>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>{{ ortak_js|safe }}</script>
<script>
var AYAR = {{ ayar|tojson }};
var FIRMALAR = [];
var FIRMA_MAP = {};
{{ firma_form_js|safe }}

function sonHareketMetni(h) {
  if (!h) return 'Henüz kayıt yok';
  var t = tarihTR(h.tarih) + ' · ';
  if (h.tip === 'is') return t + miktarTR(h.miktar) + ' ' + AYAR.birim + ' ' + (h.kalem_adi || AYAR.is_adi);
  if (h.tip === 'gider') return t + 'Gider ' + fmtTL(h.tutar);
  return t + AYAR.odeme_fiil + ' ' + fmtTL(h.tutar);
}
function miktarTR(n) { return Number(n || 0).toLocaleString('tr-TR', {maximumFractionDigits: 3}); }

function yukle() {
  apiFetch('/api/cari/' + AYAR.tur + '/firmalar').then(function(r) {
    FIRMALAR = r.firmalar;
    FIRMA_MAP = {};
    for (var i = 0; i < FIRMALAR.length; i++) FIRMA_MAP[FIRMALAR[i].id] = FIRMALAR[i];
    var t = r.toplam_kalan;
    el('toplam').innerHTML = FIRMALAR.length ? (AYAR.toplam_etiket + ': <b class="' + (t < 0 ? 'kirmizi' : '') + '">' + fmtTL(t) + '</b>') : '&nbsp;';
    ciz();
  }).catch(function(e) {
    el('liste').innerHTML = '<div class="bos kirmizi">Yüklenemedi: ' + escHtml(e.message) + '</div>';
  });
}

function ciz() {
  var y = window.scrollY;
  var q = el('arama').value.trim().toLocaleLowerCase('tr');
  var html = '', adet = 0;
  for (var i = 0; i < FIRMALAR.length; i++) {
    var f = FIRMALAR[i];
    if (q && f.ad.toLocaleLowerCase('tr').indexOf(q) < 0) continue;
    adet++;
    var k = f.bakiye.kalan;
    var sol = '<div class="baslik">' + escHtml(f.ad) + '</div><div class="alt">' + escHtml(sonHareketMetni(f.son_hareket)) + '</div>';
    var sag = '<div class="firma-kalan"><div class="tutar' + (k < 0 ? ' kirmizi' : '') + '">' + fmtTL(Math.abs(k)) + '</div>' +
              '<div class="not">' + (k < 0 ? 'Fazla ödeme' : AYAR.kalan_etiket) + '</div></div>';
    html += satirHtml(f.id, sol, sag);
  }
  if (!FIRMALAR.length) {
    html = '<div class="liste"><div class="bos">Henüz ' + escHtml(AYAR.tekil.toLocaleLowerCase('tr')) + ' yok.<br>Alttaki butonla ilk firmayı ekleyin.</div></div>';
  } else if (!adet) {
    html = '<div class="liste"><div class="bos">Aramayla eşleşen firma yok.</div></div>';
  } else {
    html = '<div class="liste">' + html + '</div>';
  }
  el('liste').innerHTML = html;
  el('ipucu').style.display = adet ? 'block' : 'none';
  window.scrollTo(0, y);
}

function firmaAc(id) { location.href = '/' + AYAR.tur + '/' + id; }
function firmaDuzenle(id) {
  apiFetch('/api/cari/firma/' + id).then(function(r) { firmaFormAc(r.firma, r.kalemler); })
    .catch(function(e) { toast(e.message); });
}
function firmaSil(id) {
  var f = FIRMA_MAP[id];
  if (!f) return;
  if (!onayla(f.ad + ' ve tüm kayıtları silinecek. Bu işlem geri alınamaz. Emin misiniz?')) { satirKapat(); return; }
  apiFetch('/api/cari/firma/' + id, {method: 'DELETE'}).then(function() {
    ACIK_SATIR = null;
    toast('Silindi');
    yukle();
  }).catch(function(e) { toast(e.message); });
}
function firmaKaydedildi() { yukle(); }

kaydirmaKur(el('liste'), firmaAc, firmaDuzenle, firmaSil);
yukle();
</script>
</body>
</html>'''

FIRMA_HTML = r'''<!DOCTYPE html>
<html lang="tr">
<head>
{{ ortak_head|safe }}
<title>{{ firma.ad }} — {{ ayar.tekil }}</title>
<style>{{ ortak_css|safe }}{{ cari_css|safe }}</style>
</head>
<body>
<div class="siyah-ust">
  <div class="su-ust">
    <a href="/{{ ayar.tur }}" class="su-geri">&#8249; {{ ayar.baslik }}</a>
    <div class="su-btnlar">
      <button class="su-btn" onclick="firmaDuzenleAc()" title="Firma adı ve birim fiyatlar">Düzenle</button>
      <button class="su-btn" onclick="pdfAc()" title="Hesap dökümü PDF">PDF</button>
      <button class="su-btn yuvarlak" onclick="modalAc('yardim')" aria-label="Yardım" title="Yardım">?</button>
    </div>
  </div>
  <div class="su-ad" id="su-ad">{{ firma.ad }}</div>
  <div class="su-etiket" id="su-etiket">{{ ayar.kalan_etiket }}</div>
  <div class="su-kalan" id="su-kalan">…</div>
  <div class="su-ozet" id="su-ozet"></div>
</div>

<!-- Giris formu -->
<div class="kart-kutu" id="giris">
  <div class="secim">
    <button id="s-is" onclick="sekmeSec('is')">{{ ayar.is_sekme }}</button>
    <button id="s-gider" onclick="sekmeSec('gider')">Gider</button>
    <button id="s-odeme" onclick="sekmeSec('odeme')">{{ ayar.odeme_sekme }}</button>
  </div>
  <div class="alan"><label for="g-tarih">Tarih</label><input type="date" id="g-tarih"></div>
  <div id="g-is">
    <div id="g-kalem-yok" class="bilgi" style="display:none">Bu firmaya henüz birim fiyat kalemi eklenmemiş.
      <button class="btn-link" onclick="firmaDuzenleAc()">Fiyat kalemi ekle</button></div>
    <div id="g-kalem-var">
      <div class="alan"><label for="g-kalem">Kalem</label><select id="g-kalem" onchange="onizle()"></select></div>
      <div class="alan"><label for="g-miktar">Miktar ({{ ayar.birim }})</label><input type="text" id="g-miktar" inputmode="decimal" placeholder="0" autocomplete="off" oninput="onizle()"></div>
      <div class="onizleme" id="g-onizleme"></div>
    </div>
  </div>
  <div id="g-gider">
    <div class="alan"><label for="g-gacik">Açıklama</label><input type="text" id="g-gacik" placeholder="{{ ayar.gider_ornek }}" autocomplete="off"></div>
  </div>
  <div id="g-tutar-alan" class="alan"><label for="g-tutar">Tutar (₺)</label><input type="text" id="g-tutar" inputmode="decimal" placeholder="0" autocomplete="off"></div>
  <div id="g-odeme">
    <div class="alan" style="margin-bottom:6px"><label for="g-not">Not</label><input type="text" id="g-not" placeholder="Nakit, çek, havale…" autocomplete="off"></div>
    <div class="cipler"><button class="cip" onclick="notSec('Nakit')">Nakit</button><button class="cip" onclick="notSec('Çek')">Çek</button><button class="cip" onclick="notSec('Havale')">Havale</button></div>
  </div>
  <button class="btn" id="g-ekle" onclick="satirEkle()">Satırı Ekle</button>
</div>

<div class="defter-baslik"><h2>Defter</h2><span class="alt-baslik" id="d-adet"></span></div>
<div class="liste defter" id="defter"><div class="bos">Yükleniyor…</div></div>
<div class="ipucu" id="ipucu" style="display:none">Düzeltmek için satıra dokunun · Sil için sola kaydırın</div>

<!-- Hareket duzenle -->
<div class="modal-arka gizli" id="h-form" onclick="arkaTik(event, 'h-form')">
  <div class="modal">
    <div class="modal-ust"><h2 id="h-baslik">Satırı Düzenle</h2><button class="kapat" onclick="modalKapat('h-form')" aria-label="Kapat">&times;</button></div>
    <div class="alan"><label for="h-tarih">Tarih</label><input type="date" id="h-tarih"></div>
    <div id="h-is">
      <div class="alan"><label for="h-kalem">Kalem</label><select id="h-kalem" onchange="hKalemDegisti()"></select></div>
      <div class="iki-alan">
        <div class="alan"><label for="h-miktar">Miktar ({{ ayar.birim }})</label><input type="text" id="h-miktar" inputmode="decimal" autocomplete="off" oninput="hOnizle()"></div>
        <div class="alan"><label for="h-fiyat">Birim fiyat (₺)</label><input type="text" id="h-fiyat" inputmode="decimal" autocomplete="off" oninput="hOnizle()"></div>
      </div>
      <div class="onizleme" id="h-onizleme"></div>
      <div class="bilgi">Birim fiyat bu satıra kilitlidir. Burada değiştirirseniz sadece bu satır değişir.</div>
    </div>
    <div id="h-tutar-alan" class="alan"><label for="h-tutar">Tutar (₺)</label><input type="text" id="h-tutar" inputmode="decimal" autocomplete="off"></div>
    <div class="alan"><label for="h-acik" id="h-acik-etiket">Açıklama</label><input type="text" id="h-acik" autocomplete="off"></div>
    <button class="btn" id="h-kaydet" onclick="hKaydet()">Kaydet</button>
    <button class="btn btn-acik kirmizi" onclick="hFormdanSil()">Bu satırı sil</button>
  </div>
</div>

<!-- PDF -->
<div class="modal-arka gizli" id="pdf-form" onclick="arkaTik(event, 'pdf-form')">
  <div class="modal">
    <div class="modal-ust"><h2>Hesap Dökümü (PDF)</h2><button class="kapat" onclick="modalKapat('pdf-form')" aria-label="Kapat">&times;</button></div>
    <div class="iki-alan">
      <div class="alan"><label for="p-bas">Başlangıç</label><input type="date" id="p-bas"></div>
      <div class="alan"><label for="p-bit">Bitiş</label><input type="date" id="p-bit"></div>
    </div>
    <div class="bilgi">Tarihleri boş bırakırsanız tüm kayıtlar alınır. Başlangıç seçerseniz öncesi "Devreden bakiye" olarak yazılır.
      PDF açılınca Paylaş menüsünden WhatsApp veya Mail ile gönderebilirsiniz.</div>
    <button class="btn" onclick="pdfOlustur()">PDF Oluştur</button>
  </div>
</div>

{{ firma_form_html|safe }}

<div class="modal-arka gizli" id="yardim" onclick="arkaTik(event, 'yardim')">
  <div class="modal yardim">
    <div class="modal-ust"><h2>Firma sayfası — Nasıl kullanılır?</h2><button class="kapat" onclick="modalKapat('yardim')" aria-label="Kapat">&times;</button></div>
    <ol>
      <li><b>{{ ayar.is_sekme }}:</b> Tarihi ve kalemi seçin, miktarı ({{ ayar.birim }}) yazın. Hakediş kendiliğinden hesaplanır (miktar × birim fiyat). <b>Satırı Ekle</b>'ye basın.</li>
      <li><b>Gider:</b> {{ ayar.gider_yardim }}</li>
      <li><b>{{ ayar.odeme_sekme }}:</b> Tutarı ve notu (nakit/çek/havale) yazın. Kalandan düşülür.</li>
      <li><b>Düzeltmek için</b> defterdeki satıra dokunun. <b>Silmek için</b> satırı sola kaydırın; onay sorulur.</li>
      <li><b>Düzenle</b> (üstte): firma adı ve birim fiyatlar. Fiyat değişikliği geçmiş satırları değiştirmez.</li>
      <li><b>PDF</b>: hesap dökümü; isterseniz tarih aralığı seçin.</li>
    </ol>
    <p>Defter eskiden yeniye sıralıdır; çok kayıt varsa eskiler <b>Önceki kayıtlar</b> satırında toplanır, dokununca açılır. {{ ayar.yon_aciklama }}</p>
    <button class="btn" style="margin-top:14px" onclick="modalKapat('yardim')">Anladım</button>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>{{ ortak_js|safe }}</script>
<script>
var AYAR = {{ ayar|tojson }};
var FIRMA_ID = {{ firma.id|tojson }};
var ONCEKI_GOSTERIM = {{ onceki_gosterim|tojson }};
var VERI = null;           // son /api/cari/firma/<id> cevabi
var HAREKETLER = {};
var SEKME = 'is';
var ONCEKI_ACIK = false;
var DUZENLENEN = null;
{{ firma_form_js|safe }}

function miktarOku(s) {
  // Miktarda virgul varsa TR (nokta binlik); yoksa nokta ondalik ("12.5" -> 12,5)
  s = String(s || '').trim().replace(/\s/g, '');
  if (s === '') return NaN;
  if (s.indexOf(',') >= 0) s = s.replace(/\./g, '').replace(',', '.');
  return Number(s);
}
function miktarTR(n) { return Number(n || 0).toLocaleString('tr-TR', {maximumFractionDigits: 3}); }
function yuvarla2(x) { return Math.round(x * 100 + (x >= 0 ? 1e-7 : -1e-7)) / 100; }

function yukle() {
  return apiFetch('/api/cari/firma/' + FIRMA_ID).then(function(r) {
    VERI = r;
    el('su-ad').textContent = r.firma.ad;
    document.title = r.firma.ad + ' — ' + AYAR.tekil;
    var k = r.bakiye.kalan;
    el('su-etiket').textContent = k < 0 ? 'Fazla ödeme' : AYAR.kalan_etiket;
    el('su-kalan').textContent = fmtTL(Math.abs(k));
    el('su-kalan').className = 'su-kalan' + (k < 0 ? ' fazla' : '');
    el('su-ozet').textContent = 'Hakediş ' + fmtTL(r.bakiye.hakedis) + ' · ' + AYAR.odeme_fiil + ' ' + fmtTL(r.bakiye.odenen);
    kalemSecimiDoldur(el('g-kalem'), r.kalemler, el('g-kalem').value);
    el('g-kalem-yok').style.display = r.kalemler.length ? 'none' : 'block';
    el('g-kalem-var').style.display = r.kalemler.length ? 'block' : 'none';
    onizle();
    defterCiz();
  }).catch(function(e) {
    el('defter').innerHTML = '<div class="bos kirmizi">Yüklenemedi: ' + escHtml(e.message) + '</div>';
  });
}

function kalemSecimiDoldur(sel, kalemler, secili, ekstra) {
  var html = '';
  for (var i = 0; i < kalemler.length; i++) {
    var k = kalemler[i];
    html += '<option value="' + k.id + '">' + escHtml(k.ad) + ' — ' + fmtTL(k.birim_fiyat) + '/' + escHtml(AYAR.birim) + '</option>';
  }
  if (ekstra) html += '<option value="' + ekstra.id + '">' + escHtml(ekstra.ad) + ' (silinmiş kalem)</option>';
  sel.innerHTML = html;
  if (secili) sel.value = String(secili);
  if (!sel.value && sel.options.length) sel.selectedIndex = 0;
}
function kalemBul(id) {
  if (!VERI) return null;
  for (var i = 0; i < VERI.kalemler.length; i++) if (VERI.kalemler[i].id === Number(id)) return VERI.kalemler[i];
  return null;
}

// ---- Giris formu ----
function sekmeSec(s) {
  SEKME = s;
  el('s-is').className = s === 'is' ? 'aktif' : '';
  el('s-gider').className = s === 'gider' ? 'aktif' : '';
  el('s-odeme').className = s === 'odeme' ? 'aktif' : '';
  el('g-is').style.display = s === 'is' ? 'block' : 'none';
  el('g-gider').style.display = s === 'gider' ? 'block' : 'none';
  el('g-odeme').style.display = s === 'odeme' ? 'block' : 'none';
  el('g-tutar-alan').style.display = s === 'is' ? 'none' : 'block';
  el('g-ekle').className = 'btn' + (s === 'odeme' ? ' btn-yesil' : '');
}
function onizle() {
  var k = kalemBul(el('g-kalem').value);
  var m = miktarOku(el('g-miktar').value);
  if (!k || isNaN(m) || m <= 0) { el('g-onizleme').innerHTML = k ? 'Birim fiyat: ' + fmtTL(k.birim_fiyat) + '/' + escHtml(AYAR.birim) : ''; return; }
  el('g-onizleme').innerHTML = miktarTR(m) + ' ' + escHtml(AYAR.birim) + ' × ' + fmtTL(k.birim_fiyat) + ' = Hakediş <b>' + fmtTL(yuvarla2(m * k.birim_fiyat)) + '</b>';
}
function notSec(n) { el('g-not').value = n; }

function satirEkle() {
  var veri = {tip: SEKME, tarih: el('g-tarih').value};
  if (!veri.tarih) { toast('Tarih seçin'); return; }
  if (SEKME === 'is') {
    if (!VERI || !VERI.kalemler.length) { toast('Önce fiyat kalemi ekleyin'); return; }
    veri.kalem_id = Number(el('g-kalem').value);
    veri.miktar = miktarOku(el('g-miktar').value);
    if (isNaN(veri.miktar) || veri.miktar <= 0) { toast('Geçerli bir miktar girin'); return; }
  } else {
    veri.tutar = parseTLInput(el('g-tutar').value);
    if (isNaN(veri.tutar) || veri.tutar <= 0) { toast('Geçerli bir tutar girin'); return; }
    veri.aciklama = (SEKME === 'gider' ? el('g-gacik') : el('g-not')).value.trim();
  }
  var btn = el('g-ekle');
  btn.disabled = true;
  jsonGonder('/api/cari/firma/' + FIRMA_ID + '/hareket', 'POST', veri).then(function() {
    el('g-miktar').value = ''; el('g-tutar').value = ''; el('g-gacik').value = ''; el('g-not').value = '';
    toast('Eklendi');
    return yukle();
  }).catch(function(e) { toast(e.message); })
    .then(function() { btn.disabled = false; });
}

// ---- Defter ----
function hucreler(h) {
  var ust, alt;
  if (h.tip === 'is') {
    ust = h.kalem_adi || AYAR.is_adi;
    alt = miktarTR(h.miktar) + ' ' + AYAR.birim + ' × ' + fmtTL(h.birim_fiyat) + (h.aciklama ? ' · ' + h.aciklama : '');
  } else if (h.tip === 'gider') {
    ust = h.aciklama || 'Gider'; alt = 'Gider';
  } else {
    ust = h.aciklama || AYAR.odeme_fiil; alt = AYAR.odeme_fiil + ' para';
  }
  var odeme = h.tip === 'odeme';
  return '<div class="d-grid"><div class="d-tarih">' + tarihTR(h.tarih) + '</div>' +
    '<div class="d-acik"><div class="u">' + escHtml(ust) + '</div><div class="a">' + escHtml(alt) + '</div></div>' +
    '<div class="d-tutar">' + (odeme ? '' : fmtTL(h.tutar)) + '</div>' +
    '<div class="d-tutar yesil">' + (odeme ? fmtTL(h.tutar) : '') + '</div></div>';
}
function defterCiz() {
  var y = window.scrollY;
  var satirlar = VERI.defter;
  HAREKETLER = {};
  el('d-adet').textContent = satirlar.length ? satirlar.length + ' satır' : '';
  var html = '<div class="d-bas"><div class="d-grid"><div>Tarih</div><div>Açıklama</div><div class="d-sag">Hakediş</div><div class="d-sag">' + escHtml(AYAR.odeme_kolon) + '</div></div></div>';
  if (!satirlar.length) {
    html += '<div class="bos">Henüz kayıt yok. Yukarıdaki formdan ilk satırı ekleyin.</div>';
  }
  var gizli = (!ONCEKI_ACIK && satirlar.length > ONCEKI_GOSTERIM) ? satirlar.length - ONCEKI_GOSTERIM : 0;
  if (gizli) {
    var ph = 0, po = 0;
    for (var i = 0; i < gizli; i++) { if (satirlar[i].tip === 'odeme') po += satirlar[i].tutar; else ph += satirlar[i].tutar; }
    html += '<div class="onceki" onclick="oncekiAc()"><div class="d-grid"><div class="d-tarih">▸</div>' +
      '<div class="d-acik"><div class="u">Önceki kayıtlar (' + gizli + ')</div><div class="a">Görmek için dokunun</div></div>' +
      '<div class="d-tutar">' + (ph ? fmtTL(ph) : '') + '</div><div class="d-tutar yesil">' + (po ? fmtTL(po) : '') + '</div></div></div>';
  }
  for (var j = 0; j < satirlar.length; j++) {
    HAREKETLER[satirlar[j].id] = satirlar[j];
    if (j < gizli) continue;
    html += satirHtml(satirlar[j].id, hucreler(satirlar[j]), '');
  }
  if (satirlar.length) {
    var b = VERI.bakiye;
    html += '<div class="d-toplam"><div class="d-grid"><div></div><div>Toplam</div><div class="d-tutar">' + fmtTL(b.hakedis) +
      '</div><div class="d-tutar yesil">' + fmtTL(b.odenen) + '</div></div></div>';
    html += '<div class="d-kalan' + (b.kalan < 0 ? ' fazla' : '') + '"><span class="e">' + (b.kalan < 0 ? 'Fazla ödeme' : escHtml(AYAR.kalan_etiket)) +
      '</span><span class="t">' + fmtTL(Math.abs(b.kalan)) + '</span></div>';
  }
  el('defter').innerHTML = html;
  el('ipucu').style.display = satirlar.length ? 'block' : 'none';
  window.scrollTo(0, y);
}
function oncekiAc() { ONCEKI_ACIK = true; defterCiz(); }

// ---- Satir duzenle / sil ----
function hDuzenle(id) {
  var h = HAREKETLER[id];
  if (!h) return;
  DUZENLENEN = id;
  var isMi = h.tip === 'is';
  el('h-baslik').textContent = isMi ? AYAR.is_adi + ' satırı' : (h.tip === 'gider' ? 'Gider satırı' : AYAR.odeme_sekme);
  el('h-tarih').value = h.tarih;
  el('h-is').style.display = isMi ? 'block' : 'none';
  el('h-tutar-alan').style.display = isMi ? 'none' : 'block';
  el('h-acik-etiket').textContent = isMi ? 'Not (isteğe bağlı)' : (h.tip === 'gider' ? 'Açıklama' : 'Not');
  el('h-acik').value = h.aciklama || '';
  if (isMi) {
    var ekstra = (h.kalem_id && !kalemBul(h.kalem_id)) ? {id: h.kalem_id, ad: h.kalem_adi || AYAR.is_adi} : null;
    kalemSecimiDoldur(el('h-kalem'), VERI.kalemler, h.kalem_id, ekstra);
    el('h-miktar').value = miktarTR(h.miktar);
    el('h-fiyat').value = tlInputYaz(h.birim_fiyat);
    hOnizle();
  } else {
    el('h-tutar').value = tlInputYaz(h.tutar);
  }
  modalAc('h-form');
}
function hKalemDegisti() {
  var k = kalemBul(el('h-kalem').value);
  if (k) el('h-fiyat').value = tlInputYaz(k.birim_fiyat);  // yeni kalemin guncel fiyati
  hOnizle();
}
function hOnizle() {
  var m = miktarOku(el('h-miktar').value), f = parseTLInput(el('h-fiyat').value);
  el('h-onizleme').innerHTML = (isNaN(m) || isNaN(f) || m <= 0 || f <= 0) ? '' : 'Hakediş <b>' + fmtTL(yuvarla2(m * f)) + '</b>';
}
function hKaydet() {
  var h = HAREKETLER[DUZENLENEN];
  if (!h) return;
  var veri = {tarih: el('h-tarih').value, aciklama: el('h-acik').value.trim()};
  if (!veri.tarih) { toast('Tarih seçin'); return; }
  if (h.tip === 'is') {
    veri.kalem_id = Number(el('h-kalem').value);
    veri.miktar = miktarOku(el('h-miktar').value);
    veri.birim_fiyat = parseTLInput(el('h-fiyat').value);
    if (isNaN(veri.miktar) || veri.miktar <= 0) { toast('Geçerli bir miktar girin'); return; }
    if (isNaN(veri.birim_fiyat) || veri.birim_fiyat <= 0) { toast('Geçerli bir birim fiyat girin'); return; }
  } else {
    veri.tutar = parseTLInput(el('h-tutar').value);
    if (isNaN(veri.tutar) || veri.tutar <= 0) { toast('Geçerli bir tutar girin'); return; }
  }
  var btn = el('h-kaydet');
  btn.disabled = true;
  jsonGonder('/api/cari/hareket/' + DUZENLENEN, 'PUT', veri).then(function() {
    modalKapat('h-form');
    toast('Güncellendi');
    return yukle();
  }).catch(function(e) { toast(e.message); })
    .then(function() { btn.disabled = false; });
}
function hSil(id) {
  var h = HAREKETLER[id];
  if (!h) return;
  var ad = h.tip === 'is' ? (h.kalem_adi || AYAR.is_adi) + ' ' + miktarTR(h.miktar) + ' ' + AYAR.birim
                          : (h.aciklama || (h.tip === 'gider' ? 'Gider' : AYAR.odeme_fiil));
  if (!onayla(tarihTR(h.tarih) + ' · ' + ad + ' (' + fmtTL(h.tutar) + ') silinecek. Emin misiniz?')) { satirKapat(); return; }
  apiFetch('/api/cari/hareket/' + id, {method: 'DELETE'}).then(function() {
    ACIK_SATIR = null;
    modalKapat('h-form');
    toast('Silindi');
    return yukle();
  }).catch(function(e) { toast(e.message); });
}
function hFormdanSil() { if (DUZENLENEN !== null) hSil(DUZENLENEN); }

// ---- Firma duzenle / PDF ----
function firmaDuzenleAc() { if (VERI) firmaFormAc(VERI.firma, VERI.kalemler); }
function firmaKaydedildi() { yukle(); }
function pdfAc() { modalAc('pdf-form'); }
function pdfOlustur() {
  var bas = el('p-bas').value, bit = el('p-bit').value;
  if (bas && bit && bas > bit) { toast('Başlangıç bitişten sonra olamaz'); return; }
  var url = '/api/cari/firma/' + FIRMA_ID + '/pdf?bas=' + encodeURIComponent(bas) + '&bit=' + encodeURIComponent(bit);
  modalKapat('pdf-form');
  window.open(url, '_blank');
}

kaydirmaKur(el('defter'), hDuzenle, hDuzenle, hSil);
el('g-tarih').value = bugunISO();
sekmeSec('is');
yukle();
</script>
</body>
</html>'''


GUN_SONU_HTML = r'''<!DOCTYPE html>
<html lang="tr">
<head>
{{ ortak_head|safe }}
<title>Gün Sonu — {{ ayar.baslik }}</title>
<style>{{ ortak_css|safe }}{{ cari_css|safe }}</style>
</head>
<body class="alt-butonlu">
<a href="/{{ ayar.tur }}" class="geri">&#8249; {{ ayar.baslik }}</a>
<div class="ust">
  <div>
    <h1>Gün Sonu Raporu</h1>
    <div class="alt-baslik">{{ ayar.baslik }}</div>
  </div>
  <button class="yardim-btn" onclick="modalAc('yardim')" aria-label="Yardım" title="Yardım">?</button>
</div>

<div class="iki-alan">
  <div class="alan"><label for="r-tarih">Tarih</label><input type="date" id="r-tarih" onchange="yukle()"></div>
  <div class="alan"><label for="r-kapsam">Kapsam</label>
    <select id="r-kapsam" onchange="yukle()" title="Tüm firmalar ya da tek firma">
      <option value="">Tümü</option>
      {% for f in firmalar %}<option value="{{ f.id }}">{{ f.ad }}</option>{% endfor %}
    </select></div>
</div>

<div class="ozet">
  <div class="ozet-kutu" title="O gün girilen iş miktarı"><div class="deger" id="o-miktar">-</div><div class="etiket">Toplam miktar</div></div>
  <div class="ozet-kutu" title="O günün iş + gider tutarı"><div class="deger" id="o-hakedis">-</div><div class="etiket">Günün hakedişi</div></div>
  <div class="ozet-kutu"><div class="deger yesil" id="o-odenen">-</div><div class="etiket">{{ ayar.gun_odeme_etiket }}</div></div>
  <div class="ozet-kutu" title="O gün kaydı olan firma sayısı"><div class="deger" id="o-firma">-</div><div class="etiket">Hareketli firma</div></div>
  <div class="ozet-kutu genis" title="Kapsamdaki tüm firmaların o günün sonundaki toplam kalanı">
    <div class="etiket" id="o-kalan-etiket">Gün sonu {{ ayar.toplam_etiket|lower }}</div><div class="deger" id="o-kalan">-</div></div>
</div>

<div class="grup-baslik"><span>Firmalar</span><span>Gün sonu kalan</span></div>
<div class="liste" id="r-firmalar"><div class="bos">Yükleniyor…</div></div>
<div class="grup-baslik"><span>Günün hareketleri</span></div>
<div class="liste" id="r-hareketler"><div class="bos">Yükleniyor…</div></div>
<div class="bilgi" style="margin-top:12px">PDF başlığı: <b id="r-baslik"></b> — değiştirmek için Ana Menü → Ayarlar.</div>

<div class="alt-sabit"><button class="btn" onclick="pdfOlustur()">PDF Oluştur</button></div>

<div class="modal-arka gizli" id="yardim" onclick="arkaTik(event, 'yardim')">
  <div class="modal yardim">
    <div class="modal-ust"><h2>Gün Sonu Raporu — Nasıl kullanılır?</h2><button class="kapat" onclick="modalKapat('yardim')" aria-label="Kapat">&times;</button></div>
    <ol>
      <li><b>Tarih</b> seçin (açılışta bugün gelir).</li>
      <li><b>Kapsam:</b> tüm firmalar ya da tek bir firma.</li>
      <li>Üstte günün toplamları, altta o gün kaydı olan firmalar ve tek tek hareketler görünür. Firmaya dokununca firma sayfası açılır.</li>
      <li><b>PDF Oluştur</b>: A4 rapor açılır (başlıkta firmanızın adı, özet, firma tablosu, hareketler, imza alanı). Paylaş menüsünden WhatsApp veya Mail ile gönderin.</li>
    </ol>
    <p><b>Gün sonu kalan</b>, seçilen günün sonundaki bakiyedir; geçmiş bir günün raporu her alındığında aynı çıkar. Eksi tutar fazla ödemedir.</p>
    <p>PDF başlığındaki firma adınızı <b>Ana Menü → Ayarlar</b>'dan değiştirebilirsiniz.</p>
    <button class="btn" style="margin-top:14px" onclick="modalKapat('yardim')">Anladım</button>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>{{ ortak_js|safe }}</script>
<script>
var AYAR = {{ ayar|tojson }};
function el(id) { return document.getElementById(id); }
function miktarTR(n) { return Number(n || 0).toLocaleString('tr-TR', {maximumFractionDigits: 3}); }

function yukle() {
  var t = el('r-tarih').value;
  if (!t) return;
  var url = '/api/cari/' + AYAR.tur + '/gun-sonu?tarih=' + encodeURIComponent(t) +
            '&firma_id=' + encodeURIComponent(el('r-kapsam').value);
  apiFetch(url).then(ciz).catch(function(e) {
    el('r-firmalar').innerHTML = '<div class="bos kirmizi">Yüklenemedi: ' + escHtml(e.message) + '</div>';
    el('r-hareketler').innerHTML = '';
  });
}

function ciz(v) {
  var o = v.ozet;
  el('o-miktar').textContent = miktarTR(o.miktar) + ' ' + AYAR.birim;
  el('o-hakedis').textContent = fmtTL(o.hakedis);
  el('o-odenen').textContent = fmtTL(o.odenen);
  el('o-firma').textContent = o.firma_sayisi;
  el('o-kalan-etiket').textContent = o.toplam_kalan < 0 ? 'Gün sonu fazla ödeme' : 'Gün sonu ' + AYAR.toplam_etiket.toLocaleLowerCase('tr');
  el('o-kalan').textContent = fmtTL(Math.abs(o.toplam_kalan));
  el('o-kalan').className = 'deger' + (o.toplam_kalan < 0 ? ' kirmizi' : '');
  el('r-baslik').textContent = v.rapor_basligi;

  var fh = '';
  for (var i = 0; i < v.firmalar.length; i++) {
    var f = v.firmalar[i];
    var parca = [];
    if (f.miktar) parca.push(miktarTR(f.miktar) + ' ' + AYAR.birim);
    if (f.hakedis) parca.push('Hakediş ' + fmtTL(f.hakedis));
    if (f.odenen) parca.push(AYAR.odeme_fiil + ' ' + fmtTL(f.odenen));
    fh += '<a class="gs-satir" href="/' + AYAR.tur + '/' + f.id + '"><div class="sol"><div class="ad">' + escHtml(f.ad) + '</div>' +
      '<div class="alt">' + escHtml(parca.join(' · ')) + '</div></div>' +
      '<div class="sag"><div class="t' + (f.kalan < 0 ? ' kirmizi' : '') + '">' + fmtTL(Math.abs(f.kalan)) + '</div>' +
      '<div class="n">' + (f.kalan < 0 ? 'Fazla ödeme' : escHtml(AYAR.kalan_etiket)) + '</div></div></a>';
  }
  el('r-firmalar').innerHTML = fh || '<div class="bos">Bu tarihte kayıt yok.</div>';

  var hh = '';
  for (var j = 0; j < v.hareketler.length; j++) {
    var h = v.hareketler[j], ust, alt;
    if (h.tip === 'is') {
      ust = h.kalem_adi || AYAR.is_adi;
      alt = miktarTR(h.miktar) + ' ' + AYAR.birim + ' × ' + fmtTL(h.birim_fiyat);
    } else if (h.tip === 'gider') { ust = h.aciklama || 'Gider'; alt = 'Gider'; }
    else { ust = h.aciklama || AYAR.odeme_fiil; alt = AYAR.odeme_fiil + ' para'; }
    var odeme = h.tip === 'odeme';
    hh += '<a class="gs-satir" href="/' + AYAR.tur + '/' + h.firma_id + '"><div class="sol"><div class="ad">' + escHtml(h.firma_adi) + '</div>' +
      '<div class="alt">' + escHtml(ust) + ' · ' + escHtml(alt) + '</div></div>' +
      '<div class="sag"><div class="t' + (odeme ? ' yesil' : '') + '">' + fmtTL(h.tutar) + '</div>' +
      '<div class="n">' + (odeme ? escHtml(AYAR.odeme_kolon) : 'Hakediş') + '</div></div></a>';
  }
  el('r-hareketler').innerHTML = hh || '<div class="bos">Hareket yok.</div>';
}

function pdfOlustur() {
  var t = el('r-tarih').value;
  if (!t) { toast('Tarih seçin'); return; }
  window.open('/api/cari/' + AYAR.tur + '/gun-sonu/pdf?tarih=' + encodeURIComponent(t) +
              '&firma_id=' + encodeURIComponent(el('r-kapsam').value), '_blank');
}

el('r-tarih').value = bugunISO();
yukle();
</script>
</body>
</html>'''


def _sayfa(sablon, **kw):
    html = render_template_string(
        sablon, ortak_head=ortak.ORTAK_HEAD, ortak_css=ortak.ORTAK_CSS, ortak_js=ortak.ORTAK_JS,
        cari_css=CARI_CSS, firma_form_html=FIRMA_FORM_HTML, firma_form_js=FIRMA_FORM_JS, **kw)
    return ortak.onbelleksiz(make_response(html))


def _liste_sayfasi(tur):
    return _sayfa(LISTE_HTML, ayar=_tur_kontrol(tur))


def _firma_sayfasi(tur, firma_id):
    ayar = _tur_kontrol(tur)
    conn = ortak.baglan()
    try:
        try:
            firma = firma_getir(conn, firma_id, tur)
        except CariHata:
            abort(404)
    finally:
        conn.close()
    return _sayfa(FIRMA_HTML, ayar=ayar, firma=firma, onceki_gosterim=ONCEKI_GOSTERIM)


def _gun_sonu_sayfasi(tur):
    ayar = _tur_kontrol(tur)
    conn = ortak.baglan()
    try:
        firmalar = [dict(r) for r in conn.execute('SELECT id, ad FROM cari_firma WHERE tur = ?', (tur,))]
    finally:
        conn.close()
    firmalar.sort(key=lambda f: ortak.tr_kucuk(f['ad']))
    return _sayfa(GUN_SONU_HTML, ayar=ayar, firmalar=firmalar)


# Sayfa adresleri ture gore acik acik kaydedilir (/<tur> gibi genel bir
# kural /puantaj, /vinc ile karisabilirdi).
for _tur in TURLER:
    bp.add_url_rule('/' + _tur, 'liste_' + _tur, (lambda t: lambda: _liste_sayfasi(t))(_tur))
    bp.add_url_rule('/' + _tur + '/gun-sonu', 'gun_sonu_' + _tur, (lambda t: lambda: _gun_sonu_sayfasi(t))(_tur))
    bp.add_url_rule('/' + _tur + '/<int:firma_id>', 'firma_' + _tur,
                    (lambda t: lambda firma_id: _firma_sayfasi(t, firma_id))(_tur))
