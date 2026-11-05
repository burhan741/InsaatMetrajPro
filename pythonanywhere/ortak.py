"""
ortak.py - Tum modullerin (puantaj, vinc, cari) paylastigi altyapi.

NEYI COZUYORUZ: Program tek dosyadan (eski app.py) moduler yapiya gecti.
Veritabani yolu, gunluk otomatik yedek, para/tarih bicimleme ve PDF font
yardimcilari TEK yerde durur; her modul bunlari buradan alir. Boylece
ornegin para bicimi bir kez duzeltilir, her ekrana ve PDF'e yansir.

NASIL TEST EDERIZ: test_ortak.py - para_tl/tarih_tr/miktar_tr bicimleri,
veritabani_hazirla'nin ilk calistirmada yedek almamasi, sonrakinde gunde
tek yedek almasi gecici klasorde dogrulanir.
"""

import glob
import json
import os
import shutil
import sqlite3
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

# Sunucuda: /home/burhan852/puantaj.db (app.py ile ayni klasor).
# Testlerde PUANTAJ_DB_PATH ortam degiskeni gecici bir dosyaya yonlendirilir;
# gercek puantaj.db'ye asla dokunulmaz.
DB_PATH = os.environ.get('PUANTAJ_DB_PATH') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'puantaj.db')


def baglan(satir_sozluk=True):
    """Yeni modullerin (vinc, cari) veritabani baglantisi.

    Neyi cozuyoruz: Her route'ta tekrar eden connect + row_factory satirlari.
    ortak.DB_PATH'i cagri aninda okur (testte degistirilebilir).
    """
    conn = sqlite3.connect(DB_PATH)
    if satir_sozluk:
        conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


# ====================================================================
# GUNLUK OTOMATIK YEDEK (eski app.py'den aynen tasindi)
# ====================================================================
def gunluk_otomatik_yedek(db_yolu=None):
    # NEYI COZUYORUZ: puantaj.db'nin hicbir yedegi yoktu, tek bir dosya
    # bozulursa/silinirse TUM veri kaybolurdu. Uygulama her basladiginda
    # (gunde en fazla 1 kez, ayni gun tekrar tetiklenmez) backups/ altina
    # tarihli bir kopya alinir, en fazla son 14 gun tutulur.
    # Tek veritabani oldugu icin puantaj + vinc + cari hepsi yedeklenir.
    db_yolu = db_yolu or DB_PATH
    backup_dir = os.path.join(os.path.dirname(db_yolu), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    hedef = os.path.join(backup_dir, 'puantaj_' + date.today().isoformat() + '.db')
    if not os.path.exists(hedef):
        shutil.copy2(db_yolu, hedef)
    yedekler = sorted(glob.glob(os.path.join(backup_dir, 'puantaj_*.db')))
    fazla = len(yedekler) - 14
    for eski in yedekler[:max(fazla, 0)]:
        try:
            os.remove(eski)
        except OSError:
            pass


def veritabani_hazirla(init_fonksiyonlari):
    """Tum modullerin tablolarini olusturur, sonra gunluk yedegi alir.

    Eski davranis aynen: veritabani dosyasi ilk kez olusturuluyorsa
    yedek alinmaz; var olan veritabaninda gunde bir yedek alinir.
    """
    ilk_calistirma = not os.path.exists(DB_PATH)
    for fonk in init_fonksiyonlari:
        fonk()
    if not ilk_calistirma:
        gunluk_otomatik_yedek()


# ====================================================================
# BICIMLEME (yeni modullerin ekran ve PDF'leri icin)
# ====================================================================
def _yuvarla(deger, hane):
    """Yarim-yukari yuvarlama (CLAUDE.md: round()/format yarimi cifte yuvarlar,
    0.125 -> 0.12 olur). repr uzerinden Decimal: 0.125 -> 0.13."""
    adim = Decimal(1).scaleb(-hane)
    return Decimal(repr(float(deger or 0))).quantize(adim, rounding=ROUND_HALF_UP)


def para_tl(deger):
    """1284500 -> '₺1.284.500' ; 40625.5 -> '₺40.625,50' ; -500 -> '-₺500'.

    Kurus yoksa ondalik gosterilmez (santiyede tutarlar cogunlukla tam).
    """
    deger = _yuvarla(deger, 2)
    isaret = '-' if deger < 0 else ''
    deger = abs(deger)
    if deger == deger.to_integral_value():
        metin = '{:,.0f}'.format(deger)
    else:
        metin = '{:,.2f}'.format(deger)
    metin = metin.replace(',', '#').replace('.', ',').replace('#', '.')
    return isaret + '₺' + metin


def miktar_tr(deger, hane=2):
    """12.5 -> '12,5' ; 12.0 -> '12' ; 1250.75 -> '1.250,75'."""
    deger = _yuvarla(deger, hane)
    metin = ('{:,.' + str(hane) + 'f}').format(deger)
    if '.' in metin:
        metin = metin.rstrip('0').rstrip('.')
    return metin.replace(',', '#').replace('.', ',').replace('#', '.')


def tr_kucuk(metin):
    """Turkce kurallı kucuk harf + bosluk sadelestirme (ayni ad denetimi icin).
    'YILMAZ' ve 'Yılmaz' -> 'yılmaz'; 'İNŞAAT' -> 'inşaat'. (lower/casefold
    I'yi i yapar, Turkcede yanlis.)"""
    metin = ' '.join(str(metin or '').split())
    return metin.replace('I', 'ı').replace('İ', 'i').lower()


def tarih_tr(iso):
    """'2026-11-04' -> '04.11.2026'. Bos/bozuk deger oldugu gibi doner."""
    if not iso:
        return ''
    parca = str(iso)[:10].split('-')
    if len(parca) != 3:
        return str(iso)
    return parca[2] + '.' + parca[1] + '.' + parca[0]


def simdi_tr():
    """Turkiye saati (UTC+3). PythonAnywhere sunucusu UTC calisir; PDF'e
    yazilan olusturma zamani ve varsayilan 'bugun' 3 saat geri kalmasin."""
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=3)))


def bugun_tr():
    return simdi_tr().date().isoformat()


def iso_tarih_mi(metin):
    """'2026-11-04' gecerli bir takvim gunu mu? (bozuk tarih siralamayi bozar)"""
    from datetime import datetime
    try:
        datetime.strptime(str(metin), '%Y-%m-%d')
        return True
    except (TypeError, ValueError):
        return False


def tutar_oku(deger):
    """JSON'dan gelen tutari float'a cevirir; gecersiz/<=0 ise None."""
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return None
    if sayi != sayi or sayi <= 0:  # NaN veya sifir/eksi
        return None
    return sayi


def onbelleksiz(resp):
    """iOS ana ekran uygulamasi eski sayfayi gostermesin."""
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


# ====================================================================
# ORTAK ARAYUZ — "Kurumsal" tema (beyaz + lacivert), TASARIM_KURALLARI.md
# NEYI COZUYORUZ: Ana menu, Vinc, Muteahhit, Demirci ayni gorunur ve ayni
# davranir. Renkler TEK yerde (TEMA): CSS :root degiskenleri ve PDF renkleri
# bu sozlukten uretilir; hicbir modul kendi renk kodunu yazmaz.
# Sablonlara {{ ortak_head|safe }}, {{ ortak_css|safe }}, {{ ortak_js|safe }}
# olarak eklenir (degisken degeri Jinja'da islenmez).
# NASIL TEST EDERIZ: test_tema.py (renk degiskenleri, font, ikonlar, PWA
# meta, onay penceresi) + her sayfa testinde node --check.
# ====================================================================
TEMA = {
    'lacivert': '#1E3A8A',
    'lacivert-koyu': '#172E6E',
    'lacivert-acik': '#EEF2FF',
    'lacivert-cizgi': '#C7D2FE',
    'zemin': '#FFFFFF',
    'zemin-2': '#F8FAFC',
    'cizgi': '#E2E8F0',
    'metin': '#0F172A',
    'metin-soluk': '#475569',
    'ikon-soluk': '#64748B',
    'alacak': '#15803D',
    'borc': '#B91C1C',
    'odeme': '#1E40AF',
    'uyari': '#B45309',
}

# Sade cizgi ikonlar (24x24, stroke 1.9, yuvarlak uclar). Sadece path icerigi.
IKONLAR = {
    'bina': '<path d="M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16"/><path d="M15 9h4a1 1 0 0 1 1 1v11"/>'
            '<path d="M2.5 21h19"/><path d="M8 8h3M8 12h3M8 16h3"/>',
    'izgara': '<rect x="4" y="4" width="16" height="16" rx="1.5"/><path d="M4 9.3h16M4 14.7h16M9.3 4v16M14.7 4v16"/>',
    'liste': '<path d="M10 6h10M10 12h10M10 18h10"/><path d="M3.5 6l1.6 1.6L7.8 5"/>'
             '<path d="M3.5 12l1.6 1.6 2.7-2.6"/><path d="M3.5 18l1.6 1.6 2.7-2.6"/>',
    'vinc': '<path d="M6 21V4"/><path d="M3 21h7"/><path d="M6 4h14"/><path d="M6 8.5L10.5 4"/>'
            '<path d="M17 4v6"/><path d="M15.5 10h3v2.2a1.5 1.5 0 0 1-3 0"/>',
    'ok': '<path d="M9 5l7 7-7 7"/>',
    'geri': '<path d="M15 5l-7 7 7 7"/>',
    'duzenle': '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    'sil': '<path d="M4 7h16"/><path d="M10 11v6M14 11v6"/><path d="M6 7l1 13h10l1-13"/><path d="M9 7V4h6v3"/>',
    'belge': '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5"/>'
             '<path d="M9 13h6M9 17h6"/>',
    'takvim': '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    'ayar': '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    'arama': '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
    'arti': '<path d="M12 5v14M5 12h14"/>',
    'yukari': '<path d="M12 19V5"/><path d="M6 11l6-6 6 6"/>',
    'asagi': '<path d="M12 5v14"/><path d="M6 13l6 6 6-6"/>',
    'kapat': '<path d="M6 6l12 12M18 6L6 18"/>',
    'para': '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.6"/><path d="M6 9.5v5M18 9.5v5"/>',
}


def svg(ad):
    """Satir ici SVG ikon (renk: currentColor)."""
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">%s</svg>' % IKONLAR[ad])


def kalan_sunum(kalan, yon):
    """Kalanin rengi + yanindaki yazi (renk tek basina anlam tasimaz).

    yon: 'alacak' (muteahhit, para bana gelecek) | 'borc' (demirci, benim borcum).
    Doner: {'sinif', 'etiket', 'tutar'} — tutar her zaman pozitif gosterilir.
    """
    kalan = float(kalan or 0)
    if kalan < 0:
        return {'sinif': 'renk-uyari', 'etiket': 'fazla ödeme', 'tutar': para_tl(-kalan)}
    etiket = 'alacak' if yon == 'alacak' else 'borç'
    if kalan == 0:
        return {'sinif': 'renk-soluk', 'etiket': etiket, 'tutar': para_tl(0)}
    return {'sinif': 'renk-alacak' if yon == 'alacak' else 'renk-borc', 'etiket': etiket, 'tutar': para_tl(kalan)}


FONT_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
             '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
             '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap">')

ORTAK_HEAD = '''<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Şantiye Defteri">
<meta name="theme-color" content="%s">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
''' % TEMA['lacivert'] + FONT_LINK

_KOK_CSS = (':root{color-scheme:light;' + ''.join('--%s:%s;' % kv for kv in TEMA.items()) +
            "--yazi:'Manrope',system-ui,-apple-system,sans-serif}")

KOK_CSS = _KOK_CSS  # puantaj da ayni renk kokunu kullanir (Rev-178)

_SECIM_OKU = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
              "stroke='%2364748B' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E"
              "%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")")

ORTAK_CSS = _KOK_CSS + r'''
*{margin:0;padding:0;box-sizing:border-box}
html{background:var(--zemin)}
body{font-family:var(--yazi);font-size:15px;font-weight:500;line-height:1.45;color:var(--metin);background:var(--zemin);
  min-height:100vh;-webkit-text-size-adjust:100%;padding-bottom:calc(32px + env(safe-area-inset-bottom))}
body.alt-butonlu{padding-bottom:calc(108px + env(safe-area-inset-bottom))}
body.kilit{overflow:hidden}
button,input,select{font-family:inherit;color:inherit}
button{cursor:pointer;-webkit-tap-highlight-color:transparent}
a{color:inherit;-webkit-tap-highlight-color:transparent}
svg{display:block;pointer-events:none;flex-shrink:0}
.sayi,.tutar,.ozet-d,.d-tutar{font-variant-numeric:tabular-nums}
.renk-alacak{color:var(--alacak)}.renk-borc{color:var(--borc)}.renk-uyari{color:var(--uyari)}
.renk-soluk{color:var(--metin-soluk)}.renk-odeme{color:var(--odeme)}.renk-metin{color:var(--metin)}
/* --- baslik bandi --- */
.bant{background:var(--lacivert);color:var(--zemin);padding:calc(6px + env(safe-area-inset-top)) calc(20px + env(safe-area-inset-right)) 64px calc(20px + env(safe-area-inset-left))}
.bant.kisa{padding-bottom:24px}
.bant-ust{display:flex;justify-content:space-between;align-items:center;gap:8px;min-height:48px}
.bant-soluk{color:var(--lacivert-cizgi);font-size:13px;font-weight:600}
.bant-geri{display:inline-flex;align-items:center;gap:2px;min-height:44px;padding:0 8px 0 0;background:none;border:none;
  color:var(--lacivert-cizgi);font-size:15px;font-weight:600;text-decoration:none}
.bant-geri svg{width:20px;height:20px;margin-left:-5px}
.bant-btnlar{display:flex;gap:8px;flex-shrink:0}
.bant-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:44px;min-width:44px;padding:0 14px;
  border:none;border-radius:22px;background:rgba(255,255,255,.15);color:var(--zemin);font-size:15px;font-weight:700;text-decoration:none}
.bant-btn:active{background:rgba(255,255,255,.25)}
.bant-btn svg{width:20px;height:20px}
.bant-btn.yuvarlak{width:44px;padding:0;font-size:18px}
.bant h1{font-size:28px;font-weight:800;line-height:1.2;letter-spacing:-.4px;margin-top:4px;overflow-wrap:anywhere}
.bant-alt{color:var(--lacivert-cizgi);font-size:13px;font-weight:600;margin-top:6px}
.bant-alt b{color:var(--zemin);font-weight:700}
.bant-filtre{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:16px}
.bant-filtre label{display:block;color:var(--lacivert-cizgi);font-size:12px;font-weight:600;margin-bottom:6px}
/* --- icerik / yuzen kart --- */
.icerik{padding:0 calc(20px + env(safe-area-inset-right)) 0 calc(20px + env(safe-area-inset-left))}
.yuzen{position:relative;margin-top:-44px;background:var(--zemin);border-radius:18px;box-shadow:0 8px 24px rgba(15,23,42,.12)}
.ozet2{display:grid;grid-template-columns:1fr 1fr}
.ozet2+.ozet2{border-top:1px solid var(--cizgi)}
.ozet2>div{padding:14px 16px;min-width:0}
.ozet2>div+div{border-left:1px solid var(--cizgi)}
.ozet-e{font-size:12px;font-weight:600;color:var(--metin-soluk)}
.ozet-d{font-size:20px;font-weight:800;line-height:1.25;margin-top:2px;white-space:nowrap}
.ozet-not{font-size:12px;font-weight:600;margin-top:1px}
.ozet-tam{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 16px;border-top:1px solid var(--cizgi)}
.ozet-tam .ozet-d{font-size:24px;text-align:right}
.ozet-tam .ozet-not{text-align:right}
.yuzen-arama{display:flex;align-items:center;gap:10px;height:56px;padding:0 16px}
.yuzen-arama svg{width:20px;height:20px;color:var(--ikon-soluk)}
.yuzen-arama input{flex:1;min-width:0;height:56px;border:none;background:none;font-size:16px;font-weight:500;outline:none;-webkit-appearance:none;appearance:none}
.bolum{margin-top:24px}
.bolum-baslik{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font-size:12px;font-weight:600;
  letter-spacing:.5px;text-transform:uppercase;color:var(--metin-soluk);margin-bottom:4px}
.bolum-baslik .tutar{letter-spacing:0;text-transform:none;font-weight:700}
/* --- liste satiri (+ sola kaydir) --- */
.satir{position:relative;overflow:hidden;border-bottom:1px solid var(--cizgi)}
.satir-aksiyon{position:absolute;top:0;right:0;bottom:0;display:flex}
.satir-aksiyon button{width:76px;border:none;color:var(--zemin);font-size:12px;font-weight:700;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px}
.satir-aksiyon svg{width:22px;height:22px}
.aks-duzenle{background:var(--lacivert)}.aks-sil{background:var(--borc)}
.satir-ic{position:relative;display:flex;align-items:center;gap:12px;min-height:72px;padding:12px 0;background:var(--zemin);
  color:var(--metin);text-decoration:none;cursor:pointer;transition:transform .2s;-webkit-tap-highlight-color:transparent}
.satir-ic.surukle{transition:none}
.ikon-daire{width:48px;height:48px;border-radius:50%;background:var(--lacivert-acik);color:var(--lacivert);display:flex;align-items:center;justify-content:center;flex-shrink:0}
.ikon-daire svg{width:24px;height:24px}
.satir-orta{flex:1;min-width:0}
.satir-baslik{display:block;font-size:17px;font-weight:700;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.satir-alt{display:block;font-size:13px;color:var(--metin-soluk);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.satir-sag{display:flex;align-items:center;gap:6px;flex-shrink:0;text-align:right}
.satir-sag .tutar{display:block;font-size:17px;font-weight:700;white-space:nowrap}
.satir-sag .tutar-etiket{display:block;font-size:12px;font-weight:600}
.ok{width:20px;height:20px;color:var(--ikon-soluk)}
.bos{padding:32px 8px;text-align:center;color:var(--metin-soluk);font-size:15px}
.ipucu{font-size:13px;color:var(--metin-soluk);text-align:center;margin-top:12px}
/* --- butonlar --- */
.btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;height:52px;padding:0 16px;border:1px solid transparent;
  border-radius:12px;background:var(--lacivert);color:var(--zemin);font-size:16px;font-weight:700;text-decoration:none}
.btn:active{background:var(--lacivert-koyu)}
.btn:disabled{opacity:.6}
.btn svg{width:20px;height:20px}
.btn+.btn{margin-top:10px}
.btn-ikincil{background:var(--zemin);color:var(--metin);border-color:var(--cizgi)}
.btn-ikincil:active{background:var(--zemin-2)}
.btn-ikincil .sil-ikon{color:var(--borc)}
.btn-tehlike{background:var(--borc);color:var(--zemin)}
.btn-tehlike:active{background:var(--borc);opacity:.85}
.btn-metin{display:inline-flex;align-items:center;gap:6px;min-height:44px;padding:0;background:none;border:none;color:var(--lacivert);font-size:15px;font-weight:700}
.btn-metin svg{width:20px;height:20px}
.btn-satir{display:flex;gap:10px}
.btn-satir .btn{flex:1}
.btn-satir .btn+.btn{margin-top:0}
.alt-sabit{position:fixed;left:0;right:0;bottom:0;z-index:5;background:linear-gradient(to top,var(--zemin) 72%,rgba(255,255,255,0));
  padding:14px calc(20px + env(safe-area-inset-right)) calc(12px + env(safe-area-inset-bottom)) calc(20px + env(safe-area-inset-left))}
/* --- kart / segment / form --- */
.kart{border:1px solid var(--cizgi);border-radius:18px;background:var(--zemin);padding:16px}
.secim{display:flex;gap:4px;padding:4px;margin-bottom:16px;background:var(--zemin-2);border:1px solid var(--cizgi);border-radius:12px}
.secim button{flex:1;min-height:44px;padding:0 4px;border:none;border-radius:9px;background:none;font-size:15px;font-weight:600;color:var(--metin-soluk)}
.secim button.aktif{background:var(--zemin);color:var(--lacivert);box-shadow:0 1px 3px rgba(15,23,42,.12)}
.alan{margin-bottom:14px}
.alan label,.etiket{display:block;font-size:12px;font-weight:600;color:var(--metin-soluk);margin-bottom:6px}
.alan input,.alan select,.girdi{display:block;width:100%;height:48px;padding:0 14px;border:1px solid var(--cizgi);border-radius:12px;
  background:var(--zemin-2);color:var(--metin);font-size:16px;font-weight:500;-webkit-appearance:none;appearance:none}
.alan select,select.girdi{padding-right:40px;background-image:''' + _SECIM_OKU + r''';background-repeat:no-repeat;background-position:right 14px center;background-size:18px}
.alan input:focus,.alan select:focus,.girdi:focus{outline:none;border:2px solid var(--lacivert);padding-left:13px}
.alan input[type=date]{min-width:0;line-height:48px}
.bant-filtre input,.bant-filtre select{background-color:var(--zemin);border-color:transparent}
.bant-filtre .alan label{color:var(--lacivert-cizgi)}
.iki-alan{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.hesap-kutu{display:flex;justify-content:space-between;align-items:center;gap:10px;min-height:48px;padding:10px 14px;margin-bottom:14px;
  border-radius:12px;background:var(--lacivert-acik);color:var(--lacivert);font-size:13px;font-weight:600}
.hesap-kutu b{font-size:17px;font-weight:800;white-space:nowrap;font-variant-numeric:tabular-nums}
.bilgi{font-size:13px;line-height:1.45;color:var(--metin-soluk);margin:-4px 0 14px}
.cipler{display:flex;flex-wrap:wrap;gap:8px;margin:-6px 0 14px}
.cip{min-height:44px;padding:0 16px;border:1px solid var(--cizgi);border-radius:22px;background:var(--zemin);font-size:13px;font-weight:600}
.cip:active{background:var(--lacivert-acik)}
/* --- tam ekran panel (formlar, yardim) --- */
.panel{position:fixed;inset:0;z-index:30;display:none;background:var(--zemin);overflow-y:auto;-webkit-overflow-scrolling:touch}
.panel.acik{display:block}
.panel .icerik{padding-top:24px;padding-bottom:calc(32px + env(safe-area-inset-bottom))}
.yardim ol{padding-left:22px;margin-bottom:14px}
.yardim li,.yardim p{font-size:15px;line-height:1.55;margin-bottom:10px}
/* --- onay penceresi --- */
.onay-arka{position:fixed;inset:0;z-index:40;display:flex;align-items:center;justify-content:center;padding:20px;background:rgba(15,23,42,.45)}
.onay-arka.gizli{display:none}
.onay-kart{width:100%;max-width:360px;padding:24px 18px 18px;border-radius:18px;background:var(--zemin);text-align:center}
.onay-kart h3{font-size:17px;font-weight:700;margin-bottom:6px}
.onay-kart p{font-size:15px;color:var(--metin-soluk);margin-bottom:20px;overflow-wrap:anywhere}
/* --- bildirim --- */
.toast{position:fixed;left:50%;bottom:calc(100px + env(safe-area-inset-bottom));z-index:50;transform:translateX(-50%);max-width:90vw;
  padding:12px 18px;border-radius:12px;background:var(--metin);color:var(--zemin);font-size:15px;font-weight:600;text-align:center;
  opacity:0;transition:opacity .25s;pointer-events:none}
.toast.goster{opacity:1}
/* --- defter tablosu --- */
.defter{border:1px solid var(--cizgi);border-radius:18px;overflow:hidden;background:var(--zemin)}
.defter .satir:last-of-type{border-bottom:none}
.d-grid{display:grid;grid-template-columns:62px minmax(0,1fr) 80px 80px;gap:6px;align-items:center;width:100%}
.d-bas{padding:10px 12px;background:var(--lacivert-acik);color:var(--lacivert);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.3px}
.defter .satir-ic{min-height:0;padding:10px 12px}
.d-tarih{font-size:12px;font-weight:600;color:var(--metin-soluk)}
.d-acik .u{font-size:15px;font-weight:600;line-height:1.3;overflow-wrap:anywhere}
.d-acik .a{font-size:12px;color:var(--metin-soluk);overflow-wrap:anywhere}
.d-tutar{font-size:13px;font-weight:700;text-align:right;white-space:nowrap}
.d-sag{text-align:right}
.onceki{padding:12px;border-bottom:1px solid var(--cizgi);cursor:pointer;-webkit-tap-highlight-color:transparent}
.onceki .u{color:var(--lacivert)}
.d-toplam{padding:12px;border-top:1px solid var(--cizgi);background:var(--zemin-2);font-weight:700}
.d-kalan{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 16px;background:var(--lacivert);color:var(--zemin)}
.d-kalan .e{font-size:15px;font-weight:800;letter-spacing:.6px}
.d-kalan .t{font-size:20px;font-weight:800;text-align:right;font-variant-numeric:tabular-nums}
.d-kalan .n{font-size:12px;font-weight:600;color:var(--lacivert-cizgi);text-align:right}
/* --- fiyat kalemi satiri --- */
.kalem-satir{display:grid;grid-template-columns:minmax(0,1fr) 116px 48px;gap:8px;margin-bottom:8px}
.kalem-sil{height:48px;border:1px solid var(--cizgi);border-radius:12px;background:var(--zemin);color:var(--ikon-soluk);display:flex;align-items:center;justify-content:center}
.kalem-sil svg{width:20px;height:20px}
'''

ORTAK_JS = 'var IKON = ' + json.dumps({ad: svg(ad) for ad in IKONLAR}, ensure_ascii=False) + ';\n' + r'''
function el(id) { return document.getElementById(id); }
function escHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
// ortak.para_tl ile ayni: 1284500 -> "₺1.284.500", 40625.5 -> "₺40.625,50"
function fmtTL(n) {
  n = Number(n || 0);
  var yuvarli = Math.round(Math.abs(n) * 100 + 1e-7) / 100;
  var kurus = Math.abs(yuvarli - Math.round(yuvarli)) > 1e-9;
  var metin = yuvarli.toLocaleString('tr-TR', {minimumFractionDigits: kurus ? 2 : 0, maximumFractionDigits: 2});
  return (n < 0 && yuvarli > 0 ? '-' : '') + '₺' + metin;
}
// ortak.kalan_sunum ile ayni: renk + yanindaki yazi (alacak / borç / fazla ödeme)
function kalanSunum(kalan, yon) {
  kalan = Number(kalan || 0);
  if (kalan < 0) return {sinif: 'renk-uyari', etiket: 'fazla ödeme', tutar: fmtTL(-kalan)};
  var etiket = yon === 'alacak' ? 'alacak' : 'borç';
  if (kalan === 0) return {sinif: 'renk-soluk', etiket: etiket, tutar: fmtTL(0)};
  return {sinif: yon === 'alacak' ? 'renk-alacak' : 'renk-borc', etiket: etiket, tutar: fmtTL(kalan)};
}
// "1.500" -> 1500 | "1500,50" -> 1500.5 | "1.500,50" -> 1500.5 (TR: nokta binlik, virgul ondalik)
function parseTLInput(s) {
  if (s === null || s === undefined) return NaN;
  s = String(s).trim().replace(/\s/g, '').replace(/₺/g, '');
  if (s === '') return NaN;
  s = s.replace(/\./g, '').replace(',', '.');
  return Number(s);
}
function tlInputYaz(n) {
  return Number(n || 0).toLocaleString('tr-TR', {maximumFractionDigits: 2});
}
function tarihTR(iso) {
  if (!iso) return '';
  var p = String(iso).substring(0, 10).split('-');
  return p.length === 3 ? p[2] + '.' + p[1] + '.' + p[0] : String(iso);
}
var AY_ADLARI = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık'];
function ayBaslik(iso) {
  var p = String(iso || '').split('-');
  if (p.length < 2) return '';
  return AY_ADLARI[Number(p[1]) - 1] + ' ' + p[0];
}
function bugunISO() {
  var d = new Date();
  var a = d.getMonth() + 1, g = d.getDate();
  return d.getFullYear() + '-' + (a < 10 ? '0' + a : a) + '-' + (g < 10 ? '0' + g : g);
}
function toast(m) {
  var t = el('toast');
  t.textContent = m;
  t.className = 'toast goster';
  clearTimeout(t._t);
  t._t = setTimeout(function() { t.className = 'toast'; }, 2400);
}
function apiFetch(url, opts) {
  return fetch(url, opts).then(function(r) {
    return r.text().then(function(txt) {
      var veri = null;
      try { veri = txt ? JSON.parse(txt) : null; } catch (e) { veri = null; }
      if (!r.ok) throw new Error((veri && veri.error) ? veri.error : ('HTTP ' + r.status));
      return veri;
    });
  });
}
function jsonGonder(url, metod, veri) {
  return apiFetch(url, {method: metod, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(veri)});
}
// ---- Tam ekran paneller (formlar, yardim) ----
function modalAc(id) {
  var p = el(id);
  p.className = 'panel acik';
  p.scrollTop = 0;
  document.body.classList.add('kilit');
}
function modalKapat(id) {
  el(id).className = 'panel';
  if (!document.querySelector('.panel.acik')) document.body.classList.remove('kilit');
}
// ---- Onay penceresi: onayIste('Silinsin mi?', 'X silinecek.', 'Sil').then(function(evet) {...}) ----
function onayIste(baslik, metin, evetYazi) {
  return new Promise(function(coz) {
    var a = el('onay');
    if (!a) {
      a = document.createElement('div');
      a.id = 'onay';
      document.body.appendChild(a);
    }
    a.innerHTML = '<div class="onay-kart" role="alertdialog" aria-modal="true" aria-labelledby="onay-b">' +
      '<h3 id="onay-b">' + escHtml(baslik) + '</h3><p>' + escHtml(metin) + '</p>' +
      '<div class="btn-satir"><button class="btn btn-ikincil" data-cevap="0">Vazgeç</button>' +
      '<button class="btn btn-tehlike" data-cevap="1">' + escHtml(evetYazi || 'Sil') + '</button></div></div>';
    a.className = 'onay-arka';
    a.onclick = function(e) {
      var b = e.target.closest('[data-cevap]');
      if (!b && e.target !== a) return;
      a.className = 'onay-arka gizli';
      coz(!!b && b.getAttribute('data-cevap') === '1');
    };
  });
}
// ---- Liste satiri ----
function satirIcerik(ikonAd, baslik, alt, sagHtml) {
  return '<span class="ikon-daire">' + IKON[ikonAd] + '</span>' +
    '<span class="satir-orta"><span class="satir-baslik">' + escHtml(baslik) + '</span>' +
    '<span class="satir-alt">' + escHtml(alt) + '</span></span>' +
    '<span class="satir-sag">' + sagHtml + '</span>';
}
function tutarHtml(tutar, sinif, etiket) {
  return '<span><span class="tutar ' + (sinif || '') + '">' + tutar + '</span>' +
    (etiket ? '<span class="tutar-etiket ' + (sinif || '') + '">' + escHtml(etiket) + '</span>' : '') + '</span>';
}
// ---- Sola kaydir -> Duzenle / Sil ----
// Kullanim: kap.innerHTML = satirHtml(id, icHtml)...; kaydirmaKur(kap, dokununca(id), duzenle(id), sil(id))
var ACIK_SATIR = null;
var AKSIYON_GENISLIK = 152;
function satirKapat() {
  if (ACIK_SATIR) { ACIK_SATIR.style.transform = ''; ACIK_SATIR = null; }
}
function satirHtml(id, icHtml) {
  return '<div class="satir" data-id="' + id + '">' +
    '<div class="satir-aksiyon"><button class="aks-duzenle" data-aks="duzenle">' + IKON.duzenle + 'Düzenle</button>' +
    '<button class="aks-sil" data-aks="sil">' + IKON.sil + 'Sil</button></div>' +
    '<div class="satir-ic">' + icHtml + '</div></div>';
}
function kaydirmaKur(kap, dokununca, duzenle, sil) {
  var bas = null, ic = null, dx = 0, yatay = null;
  kap.addEventListener('touchstart', function(e) {
    var hedef = e.target.closest('.satir-ic');
    if (!hedef || !hedef.parentNode.querySelector('.satir-aksiyon')) return;
    if (ACIK_SATIR && ACIK_SATIR !== hedef) satirKapat();
    ic = hedef; dx = 0; yatay = null;
    bas = {x: e.touches[0].clientX, y: e.touches[0].clientY, acik: ACIK_SATIR === hedef};
  }, {passive: true});
  kap.addEventListener('touchmove', function(e) {
    if (!ic || !bas) return;
    var mx = e.touches[0].clientX - bas.x, my = e.touches[0].clientY - bas.y;
    if (yatay === null && (Math.abs(mx) > 6 || Math.abs(my) > 6)) yatay = Math.abs(mx) > Math.abs(my);
    if (!yatay) return;
    dx = Math.max(-AKSIYON_GENISLIK, Math.min(0, mx + (bas.acik ? -AKSIYON_GENISLIK : 0)));
    ic.className = 'satir-ic surukle';
    ic.style.transform = 'translateX(' + dx + 'px)';
  }, {passive: true});
  kap.addEventListener('touchend', function() {
    if (!ic || !yatay) { bas = null; return; }
    ic.className = 'satir-ic';
    if (dx < -AKSIYON_GENISLIK / 3) {
      ic.style.transform = 'translateX(-' + AKSIYON_GENISLIK + 'px)';
      ACIK_SATIR = ic;
    } else {
      ic.style.transform = '';
      if (ACIK_SATIR === ic) ACIK_SATIR = null;
    }
    ic._kaydirildi = true;
    setTimeout(function(x) { return function() { x._kaydirildi = false; }; }(ic), 350);
    bas = null;
  });
  kap.addEventListener('click', function(e) {
    var satir = e.target.closest('.satir[data-id]');
    if (!satir) return;
    var id = Number(satir.getAttribute('data-id'));
    var aksBtn = e.target.closest('[data-aks]');
    if (aksBtn) {
      var aks = aksBtn.getAttribute('data-aks');
      if (aks === 'duzenle') { satirKapat(); duzenle(id); return; }
      if (aks === 'sil') { sil(id); return; }
    }
    var hedef = e.target.closest('.satir-ic');
    if (hedef && hedef._kaydirildi) return;
    if (ACIK_SATIR) { satirKapat(); return; }
    dokununca(id);
  });
}
'''


# ====================================================================
# PDF YARDIMCILARI (eski app.py'den aynen tasindi)
#
# KRITIK KURAL (Rev-109'un cokertme hatasindan sonra, ASLA TEKRARLAMA):
# reportlab importlari dosya TEPESINE KONULMAZ. Her PDF endpoint'inin
# ICINDE, try/except ImportError ile yapilir. Bu fonksiyonlar reportlab
# nesnelerini parametre olarak alir ya da kendi icinde import eder.
# ====================================================================
_PDF_FONT_CACHE = {}


def _pdf_font_hazirla(pdfmetrics, TTFont):
    if 'font' in _PDF_FONT_CACHE:
        return _PDF_FONT_CACHE['font']
    normal_yol = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    kalin_yol = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    win_normal = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'arial.ttf')
    win_kalin = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'arialbd.ttf')
    if os.path.exists(normal_yol) and os.path.exists(kalin_yol):
        pdfmetrics.registerFont(TTFont('DejaVu', normal_yol))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', kalin_yol))
        sonuc = ('DejaVu', 'DejaVu-Bold')
    elif os.path.exists(win_normal) and os.path.exists(win_kalin):
        # Yerel Windows gelistirme/test: Turkce karakterli gercek ciktiyi gormek icin.
        # (Sunucuda DejaVu var; bu dal orada hic calismaz.)
        pdfmetrics.registerFont(TTFont('ArialTR', win_normal))
        pdfmetrics.registerFont(TTFont('ArialTR-Bold', win_kalin))
        sonuc = ('ArialTR', 'ArialTR-Bold')
    else:
        # Font dosyasi yoksa (ornegin yerel Windows gelistirme ortami)
        # Helvetica'ya duser - Turkce Ş/Ğ/İ/ı bu fallback'te duzgun
        # gorunmez, ama uygulama en azindan CALISMAYA devam eder.
        sonuc = ('Helvetica', 'Helvetica-Bold')
    _PDF_FONT_CACHE['font'] = sonuc
    return sonuc


def _pdf_tl(deger):
    return '{:,.0f} TL'.format(deger or 0).replace(',', '.')


def _pdf_tablo_stili(font_n, font_b, satir_sayisi):
    from reportlab.lib import colors
    stil = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e94560')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), font_b),
        ('FONTNAME', (0, 1), (-1, -1), font_n),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    for satir_no in range(1, satir_sayisi):
        if satir_no % 2 == 0:
            stil.append(('BACKGROUND', (0, satir_no), (-1, satir_no), colors.HexColor('#f5f5f5')))
    return stil


# ====================================================================
# PWA IKONU (ana ekrana ekle). Ayri dosya yuklemek gerekmesin diye gomulu.
# Uretim: lacivert zemin + beyaz sade bina cizgi ikonu (180 ve 512 px), TASARIM_KURALLARI 8.
# ====================================================================
IKON_180_B64 = (
    'iVBORw0KGgoAAAANSUhEUgAAALQAAAC0CAIAAACyr5FlAAAK4UlEQVR42u2de4wdVR3Hz++cMzP3fe8uS5elrG2BlpDdlkLbFAkg'
    'BpFigzwK5emjxqgh0URCDRJjoiGgYDRqJKgoaoDyDIhpEYsBLeKDrZSljRYW0gfQUrb7uLt79z7mnJ9/DNs00u7ee7e7c3f2+8n8'
    'OfdmMvOZM79zzu/8Dn3knLsEAEdC4hYAyAEgB4AcAHIAyAEgB4AcAHIAyAEgBwCQA0AOADkA5ACQA0AOADkA5ACQA0AOACAHgBwA'
    'cgDIASAHgBwAcgDIASAHgBwAQA4AOQDkAJADQA4AOQDkAJADQA4AOQDkAAByAMgBIAeYSnRjXhYJIRWRoEa+d5bZWoYc09uaERnL'
    '+XzR923j3jkSnqOTCVcIZoYc02OGpFLJd1195aqOjoVzhBBEjdV+BC4YY/+2dc9LW/d4rpZSRNIP3WhtRqnkZzOx3/3w6hVL5jb4'
    'vbtFiAee3Hbz7ZviMQctxxS30yQMs+Ooh358zZkdbb5vGzvkECTEjVcsLZXN+jv/mEt7JnLxh26oZiM/VLx6dWdghtaN3pNiZmP5'
    'M1cs/eWGl3e/O+C5OmLRh2ykloN8YzsXtTJzg7cZhy6YhHBddcr85nLZSBIY55hafMONFoFOiIloh1Y23us4824iCYGAVIQ+6CQ4'
    'TGuJoqrBzJdDNvqQKeQIqV9ARLf/9Pmu7neTCcdOb6dASRrIF9ddvWzNJR3GspIEORpKDkEkul57Z9MLr+fSsWkOALWWBw4On79y'
    'wdjwKORoPJIJN5eOZad9uEkrWa4Yz9VC4LPSsAGpZTN2TG8oysbYyE6vIZ8DQA4AOQBijvrHK2sZrZqFwcRslINISCl93xpjqv+V'
    'o6WU0hgLGyIrBxFZywP5QlM2nsskgnGzCdoMwSToYH9htFjKpmMWTUgk5SAiY6wk+uZNH1uzqqOlOVnlh4VZvLWn775Huh7buD2Z'
    'cPGJiZocJIS1TJIe/dm1K5e21/rzszpPvKfz00tPb7v1+8/mMjFj4UeEeitKycGh4tc+99GVS9vLFWMtMwuuFmEs+8Z+6foVnzjv'
    '1PxwqY6pEylJ1Xs08kxvFFqOirHNufhVn+q0zFpJ+cHTrfamKyLfsBDiukuXbP5rjyASNWYGjBTKA0NFUVfWj+uquKcbs7nSEYg2'
    'KhXT0pI6vjkhierL+CAiZtHelnUcVVPYEbz2yxfPFUy1ThcHyZBv7e3r2dWXSrpE1GgRz4yXg5m1lv350ff7CvG4I7ieXDJmJkl7'
    '9w1WKobIrb7lCD4K3/rqx+u+/pFCecPT3bfd/aeY5zTa+pcoxByOkn0Do49v2i6JfGODmOPwWbqjHYdijuB/NvyhWymq4/kE6yLr'
    'O5IJ94vXLv/Rt1eXSn6j5TJFQQ5jbDYd+8lv//7PbXtdR0lJRFUFiUREJJQkreQvHnr5uS09mVQ9+QCSSMo6D2b2fXvDZWecu2Le'
    'UKHcUJlEUQhIWQgpyRi79qaHb/rsyisv7jj+uOT7fSP73x/SSh6xISASxvLJ7U2JuPvm7r5fPdr12MbtmXQI/VgiEsTMfO6KeZtf'
    '7KGUJwRDjmMceSglreU77/nLvQ/+K530hkZK+aGSPPqLyMzHNSU8V/f2F4rFSrgjpB80YuitTJ0fUormXML37cGBgpIym/bGf9qF'
    '0cpwoew6MubFMbcS8Yk3ZmGMlSSkVoInThhTipSQzDxJM4xltlWs0mNBkmZQfnIEp+w50KQ6mY7JB15JElFMSZ91SbNTkRb/xDM7'
    '3tzd53lqHCeJRKlkTpnXvOaSDuaZsbAPchyDBTX3P751459fz2XG6wYrSQP50uoLF625pKOadALIERFy6diclmQ2NYEcrqtz6Rg+'
    'KyLEPqGUY1NnE0UewevLgq2ZVC/WWPZ96xs7jhzM5Pt2ZuUDREoOpWSp7I8UytaykiSVHC/cJOH7NpiaSSU8pcgikyOqcihJ/YOj'
    '7W3Zay9dctIJmbf35/e8M+BoyUcddOeORXMyKW/76weee7FnuFBOJ1xk+kRQDikpP1y6ZvXi79x8YWtLqtafv7Jj3/o7nun+7/5k'
    'wkX7EamJNylppFA++8z2e++4rLUl5RvrG2uMnXBG1BgbnHxmR9tvfrCmKRuv+JZQ5SFii5qs5fVfPo9ZVHyrldRKKiUnnBFVSgYn'
    'lyvmpLbsF9YuGxouKYmFXlGRg4jKFdM2J3PG6ScQCa2ovkiWmc9dPs91FBYoYDkkmAVyMLPrqH0H8q/+Zz+zCFKF60gXIqIXu3aX'
    'K0Yi6IhYyyEl3f3zLUTC0dIfCzOrP1xHvb1v8NePbk2nPGMxdx8hOYJMzH+8svcrt/3+vd5hPRZmVn+8smPf5295on9w1NESIUfU'
    'xjms5UzKe2Tjay/9e88nzz91bmummu0WgqUAO944sHlLT6FYwSBYZEdIjeWmbPzgQOG+h7tqGsgKhs9TMCPacyvGWEer5lyCaksO'
    'YmsYA6PRn5VlZmPwmBGQAsgBIAeAHGI6arlUuUJoFm6EgIJx1hijpNSKxg9Nfd9atigYN+sKxg2NlAZrWA6JgnGzo2Bc3QupUTBu'
    'thSMy2ViC+cfV83Ply0+cdliFIybTQXjaireMsmCcZBDzKCCcbUWbwn+57pLlxjDAv2XKKUJ+r5tysSDgnH1Pdm6C8ZBDjFTCsZZ'
    'rvPJMjORGCsYh5Yj6gXjaipSKyZXMA5yiJlVMI6q5RgUjENXdsYUjKu7MH4oBeMgRwgF42rcUqOCEdJZVDCuhpDFkR4Kxs2ugnG1'
    'JY/BDBSMA0j2AZADQA4AOQDkAJADQA4AOYDAIFg4dVeCjRGVJK3lOPniwQlaSaJpHePSSk7+woJzxslBlGMnWP7ghoS+tluHnv5Z'
    'GC0XS76jlZTU3ztcGK0c7eSBoeKB3pFy2Z/muVOtZP/BkUleWFAYP9h+VhxlZ6D+3mFHK2u54puYpxNxN9xxfR2uGf2Do4tPa73h'
    '8qWdp7UOj5S6ut+54OwFwWskPlSkfN1Vy85fsWD8nSumpG0jGhktT/LCDm2p8eGqMsF/XnD2gttvXbV8ydxU0tu+870Hn9r22s73'
    'mrJhzgjSR865KywzBgZHr7/8jO994+JU0sUH/v8YHinfetezDz31ai48P8KRQxKNlioL57dsfmBdzNMV3ypJQdJeUD5WTGa3LDEl'
    's3nH4MLG3cYrKKoc5LAZy46WxZJ/0Y33v7GrN+45oeSa6LCC0NGiv27tWYEZjpbV7D7fsLtlHZMLO1w+Kani25in16096+vf3ZSM'
    'uzaMijThdGUts+fqzkWtQVOBj8gRXWEWnYtaPVeHlaImw1rAaIzND5UaZ4PdhoTzQyVjLM2qQTAiMtZufH5nsAAaqTlHTGkjoo3P'
    '7zTWhrWUJpyYwzc2l4lteLr7ylUd562YF4RjcOLwb4rrqC0v797wdHcuE/ND6q2obPtFYTUeQvCmF3amEu7CBS2eqwmMMVwoP/Dk'
    'tvV3PmONleFt8RHaOMfYMldTKFYWzm85ub2JBdYwC2ZBQry1t/+NXb2JmKN1mGt3ddjLXFUurfa8O9Cz6yC+JodwXZVLxyyLcFd1'
    '6/BryrLwXB33sMPt4V190Qhr73SjlB1GPIp8DgA5AOQAkANADgAgB4AcAHIAyAEgB4AcAHIAyAEgB4AcAEAOADkA5ACQA0AOADkA'
    '5ACQA0AOADkA5AAAcgDIASAHgBwAcgDIASAHgBwAcgDIAQDkAJADQA4AOcD08z8JanDy2KOTTgAAAABJRU5ErkJggg=='
)
IKON_512_B64 = (
    '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'
    'AAAEAAAw9f4fwGYcLkVctq4AAAAASUVORK5CYII='
)
