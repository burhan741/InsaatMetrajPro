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
# ORTAK ARAYUZ (Vinc, Muteahhit, Demirci sayfalari)
# NEYI COZUYORUZ: Yeni modullerin hepsi ayni gorunur ve ayni davranir
# (acik zemin, alttan acilan form, sola kaydir -> Duzenle/Sil, ₺ bicimi).
# Sablonlara {{ ortak_head|safe }}, {{ ortak_css|safe }},
# {{ ortak_js|safe }} olarak eklenir (degisken degeri Jinja'da islenmez).
# ====================================================================
ORTAK_HEAD = '''<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Şantiye">
<meta name="theme-color" content="#f4f5f7">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">'''

ORTAK_CSS = r'''
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#f4f5f7;--kart:#ffffff;--tx:#14161a;--soluk:#6b7280;--cizgi:#e5e7eb;--yesil:#0f8a4b;--kirmizi:#c62828;--vurgu:#14161a;--gri:#9ca3af}
html,body{background:var(--bg);color:var(--tx)}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;min-height:100vh;
  padding:calc(12px + env(safe-area-inset-top)) calc(16px + env(safe-area-inset-right)) calc(32px + env(safe-area-inset-bottom)) calc(16px + env(safe-area-inset-left))}
a{color:inherit}
.geri{display:inline-block;color:var(--soluk);text-decoration:none;font-size:15px;padding:4px 0 8px;-webkit-tap-highlight-color:transparent}
.ust{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.ust h1{font-size:24px;font-weight:700;letter-spacing:-.3px}
.yardim-btn{width:36px;height:36px;border-radius:50%;border:1px solid var(--cizgi);background:var(--kart);color:var(--tx);font-size:17px;font-weight:700;cursor:pointer;flex-shrink:0}
.ozet{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}
.ozet-kutu{background:var(--kart);border:1px solid var(--cizgi);border-radius:12px;padding:10px 8px;text-align:center;min-width:0}
.ozet-kutu .deger{font-size:16px;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}
.ozet-kutu.genis{grid-column:1/-1;display:flex;justify-content:space-between;align-items:center;padding:12px 14px;text-align:left}
.ozet-kutu.genis .deger{font-size:22px}
.ozet-kutu.genis .etiket{font-size:13px;font-weight:600;margin:0}
.ozet-kutu .etiket{font-size:11px;color:var(--soluk);margin-top:2px}
.yesil{color:var(--yesil)} .kirmizi{color:var(--kirmizi)}
.btn{display:block;width:100%;padding:13px;border:none;border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;-webkit-tap-highlight-color:transparent;background:var(--vurgu);color:#fff}
.btn:active{opacity:.85}
.btn-yesil{background:var(--yesil);color:#fff}
.btn-kirmizi{background:var(--kirmizi);color:#fff}
.btn-acik{background:var(--kart);color:var(--tx);border:1px solid var(--cizgi)}
.btn-acik.kirmizi{color:var(--kirmizi)}
.btn-satir{display:flex;gap:8px;margin-bottom:14px}
.btn-satir .btn{flex:1}
.grup-baslik{display:flex;justify-content:space-between;font-size:12px;font-weight:600;color:var(--soluk);text-transform:uppercase;letter-spacing:.4px;margin:14px 4px 6px}
.liste{background:var(--kart);border:1px solid var(--cizgi);border-radius:14px;overflow:hidden}
.satir{position:relative;overflow:hidden;border-bottom:1px solid var(--cizgi)}
.satir:last-child{border-bottom:none}
.satir-aksiyon{position:absolute;top:0;right:0;bottom:0;display:flex}
.satir-aksiyon button{width:76px;border:none;color:#fff;font-size:14px;font-weight:600;cursor:pointer}
.aks-duzenle{background:#6b7280} .aks-sil{background:var(--kirmizi)}
.satir-ic{position:relative;background:var(--kart);display:flex;justify-content:space-between;align-items:center;gap:10px;padding:12px 14px;transition:transform .2s;-webkit-tap-highlight-color:transparent;cursor:pointer}
.satir-ic.surukle{transition:none}
.satir-sol{min-width:0}
.satir-sol .baslik{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.satir-sol .alt{font-size:12px;color:var(--soluk);margin-top:2px}
.satir-tutar{font-size:15px;font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}
.bos{text-align:center;color:var(--soluk);font-size:14px;padding:28px 12px}
.ipucu{font-size:12px;color:var(--soluk);text-align:center;margin-top:10px}
.modal-arka{position:fixed;inset:0;background:#00000066;display:flex;align-items:flex-end;z-index:10}
.modal-arka.gizli{display:none}
.modal{background:var(--kart);color:var(--tx);width:100%;max-height:88vh;overflow-y:auto;border-radius:18px 18px 0 0;padding:18px 18px calc(22px + env(safe-area-inset-bottom))}
.modal-ust{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.modal-ust h2{font-size:18px}
.kapat{background:none;border:none;font-size:24px;color:var(--soluk);cursor:pointer;padding:0 4px;line-height:1}
.alan{margin-bottom:12px}
.alan label{display:block;font-size:12px;color:var(--soluk);margin-bottom:4px}
.alan input,.alan select{width:100%;padding:12px;border:1px solid var(--cizgi);border-radius:10px;background:#fff;color:var(--tx);font-size:16px;-webkit-appearance:none;appearance:none}
.alan input[type=date]{min-height:46px}
.secim{display:flex;background:var(--bg);border-radius:10px;padding:3px;margin-bottom:12px}
.secim button{flex:1;border:none;background:none;padding:9px;border-radius:8px;font-size:14px;font-weight:600;color:var(--soluk);cursor:pointer}
.secim button.aktif{background:var(--kart);color:var(--tx);box-shadow:0 1px 3px #0000001f}
.modal .btn+.btn{margin-top:8px}
.yardim p,.yardim li{font-size:14px;line-height:1.5;color:#374151}
.yardim ol{padding-left:20px;margin:8px 0}
.toast{position:fixed;left:50%;bottom:calc(28px + env(safe-area-inset-bottom));transform:translateX(-50%);background:#14161a;color:#fff;padding:10px 18px;border-radius:10px;font-size:14px;opacity:0;transition:opacity .25s;pointer-events:none;z-index:20;white-space:nowrap}
.toast.goster{opacity:1}
'''

ORTAK_JS = r'''
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
// "1.500" -> 1500 | "1500,50" -> 1500.5 | "1.500,50" -> 1500.5 (TR: nokta binlik, virgul ondalik)
function parseTLInput(s) {
  if (s === null || s === undefined) return NaN;
  s = String(s).trim().replace(/\s/g, '').replace(/₺/g, '');
  if (s === '') return NaN;
  s = s.replace(/\./g, '').replace(',', '.');
  return Number(s);
}
// Duzenleme formunda tutari TR bicimiyle doldur: 1500.5 -> "1.500,5"
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
  var el = document.getElementById('toast');
  el.textContent = m;
  el.className = 'toast goster';
  clearTimeout(el._t);
  el._t = setTimeout(function() { el.className = 'toast'; }, 2200);
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
// ---- Alttan acilan pencereler ----
function modalAc(id) { document.getElementById(id).className = 'modal-arka'; }
function modalKapat(id) { document.getElementById(id).className = 'modal-arka gizli'; }
function arkaTik(e, id) { if (e.target === document.getElementById(id)) modalKapat(id); }
// ---- confirm() sonrasi kaydirma konumu korunsun (iOS en uste ziplatir) ----
function onayla(mesaj) {
  var y = window.scrollY;
  var sonuc = confirm(mesaj);
  window.scrollTo(0, y);
  return sonuc;
}
// ---- Sola kaydir -> Duzenle / Sil ----
// Kullanim: kapsayici.innerHTML = satirlar; kaydirmaKur(kapsayici, dokununca(id), duzenle(id), sil(id))
var ACIK_SATIR = null;
var AKSIYON_GENISLIK = 152;
function satirKapat() {
  if (ACIK_SATIR) { ACIK_SATIR.style.transform = ''; ACIK_SATIR = null; }
}
function satirHtml(id, solHtml, sagHtml) {
  return '<div class="satir" data-id="' + id + '">' +
    '<div class="satir-aksiyon"><button class="aks-duzenle" data-aks="duzenle">Düzenle</button>' +
    '<button class="aks-sil" data-aks="sil">Sil</button></div>' +
    '<div class="satir-ic"><div class="satir-sol">' + solHtml + '</div>' + sagHtml + '</div></div>';
}
function kaydirmaKur(kap, dokununca, duzenle, sil) {
  var bas = null, ic = null, dx = 0, yatay = null;
  kap.addEventListener('touchstart', function(e) {
    var hedef = e.target.closest('.satir-ic');
    if (!hedef) return;
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
    var satir = e.target.closest('.satir');
    if (!satir) return;
    var id = Number(satir.getAttribute('data-id'));
    var aks = e.target.getAttribute('data-aks');
    if (aks === 'duzenle') { satirKapat(); duzenle(id); return; }
    if (aks === 'sil') { sil(id); return; }
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
# Uretim betigi: koyu zemin + sari baret + SANTIYE yazisi (180 ve 512 px).
# ====================================================================
IKON_180_B64 = (
    'iVBORw0KGgoAAAANSUhEUgAAALQAAAC0CAIAAACyr5FlAAAKg0lEQVR42u2deVRTVx7HLyGgQa1IUXZQigiIc9BOe0QFRFR2dRSR'
    'tXbGGZdxBxX3ggsi7htVqWitC4panRISQEVt7SjK0hFBwGU8LC7xDG4RJQnMH6HXJ4SQesQs7/s5/HHvey+P++775Pd+797kRc+0'
    'lyUBQBEcdAGAHAByAMgBIAeAHAByAMgBIAeAHAByAAA5AOQAkANADgA5AOQAkANADgA5AOQAAHIAyAEgB4AcAHIAyAEgB4AcAHIA'
    'yAEA5ACQA0AOADkA5ACQA0AOADkA5ACQA7AXLmuP/P6+BypuaTfFgp1dpMeex1urbgNcYYUcH0oIdoqis3J0tBZsUETX5HgPJ6of'
    'NSlcbm2mx3JLdEeO9wsVbZkBRXREjve+grRrxnv7oRuKcJBbsK1hhA3jHJrf+/IWam8I4cAMNFV3Ioc29rWWhhAOzEDjdUEOHUjx'
    'tOsQOOhWHIh2y6EzZmjX4XDQlTgobZVDJ83QlkPjoPtwgNonh86bofmHyUGX4WDxAWOgE3KwKmxo8iFz0E04cFxWgJbLwdqwoZmH'
    'z0HXwA9cVoDWyoGwoYFdgcgBNFsOhA3N7BBEDqDBciBsaGy3IHIAyAG0Tg5cUzS5cxA5AOQAkAPoiBxIODS8ixA5AOQAkANADqDT'
    'ciAb1fyOQuQAkANAjj+EKg8Yfb+HkBL8pAaSDHV13cd59tzHeIKxhmvxAZ99/pHpaEU6XA4EDO31gwMzcKOLhBRokhwIG9oePBA5'
    'AOQAkANohxys/TlWnbmbReQAapIDwQODYPADw+cY9mCNFqz7LXuAhBRADgA5AOQAkANADgA5AOQAkAMAyAEgB4AcgOjA1yF1m2tX'
    'f+3d205e7m3vKBaLETkALisAcgBA8GEfgMgBNPtuRV9fPyDAz3f06M8HDfzU9NNuXbuKxa8ePnp440YJny8QZudIpVLle7Cxti64'
    'fkVPr/lpGefOnQ+LiFay/b8vX3Jw+Exe3r5j1+o1ia238fL0OJGRLi+nH8uYPWceISQsLHTHti1/6OgG/XlwVVUVl8t9UHOfLvT0'
    '8im7detERrqXp4d8iUwm8/YZXVZ2S+FOTp087jFsqLwsFouHDPOqrX3wn+ICCwtzFZuxYePm5A2btCxyODs7ncsVpn23d1JoiIPD'
    'Zz2Mjblcbvfun/RzdAyZMH5/Wur5s9nOTk7KdxIePomaQQjx9h5ubWWlYgNmTJ/Wt6+DWt52CxctfvPmDX2HrEtco3CzAH8/agYh'
    'JHFdcm0tC34d0tbW9mRGev/+LsrtOf1jhp2dXZs5kZ5eWFjoOy3mcCIiwlRsg4EBt62z0tHcu/ffzVu20erQIe7BwYEttjE0MEiI'
    'X0mrxcW/7Uvbz4qcY/myxT179mx3MxMTk3VrV7e11svTw8bausXCiIgwfX19FZvh5ekxZkyQWjp3586U8ooKWk2IX9m5c2fmBlOn'
    '/p0OnclkspgFi2Qyme7L0alTpzHBb0/JseMnAoPH9XNytbS2c3F1m/z1lMrK23Stj493WxrRINHU1CTMzpGXrSwtR4wYrnpjVifE'
    'GxkZtbtZevrxnmZWzD//gGC6tqGhocXanmZWVVVVSnbYIJHELohramqiydOsmTPoWlNT05j5c2l1b+q+GzdKFO4nMmpy63/N/OuI'
    'hKMD5bCztaVv7traB7Nmz83Pv/a/ujqJRCoSibIEwomh4RKJlF4pnJ36td6JsXH3wAB/ebmwqDgt7QBdFR0VqXpjLC0tFsTOV8ub'
    '7+rV/MNHjtLqnNkzrSybxw6WLY3r1q2bvFxdU5O0fgNbbmXr6+tp2cLCPDZmXteuXZkb1NTWWlrbUfcv/fxL652ETBhvaGgoLwsE'
    'wl8uX3727Lm8Omqkj7m5mertmT5tqroy04RVa548eSIv83i8+PgVhJD+/V0iwt9mTnFxS1+9esUWOaqqq6uqq2lSuThuYWlJ8YH9'
    '30VHRdrY2Ki4k8iIcFoWCLIlEmnu2bPNt+BcbnjYpHb3cOHiJZqZJq1bq5Yufvr02YqVCbQ6buwYd/fBa9es4nCaOz8zk5+Te5Zd'
    'g2Bbt+5gVnk8XmCA/+ZNyYXXr+Rfubx6VfyggW5KXj5ggKura395+c6duxWVlYQQPl/AuLJEMG9xFbJiRTyNYZ4ew8aODVZLL584'
    'eSrvwkVaPZCWOnSIu7z84sWLJctWKH/54UPfix7VtPV3PP2w9slx8IdDB384pHBVnz69p0/7R7aQny3kDxjg2n7YEGY3j4Cdz3v9'
    '+nVzfmdjM9zLs90AtmXrdlpdFf9Nly5d1DTssYS23MTEhC5fm5j08OEjQtg3fB67IG7OvBglozqDBrplC/hBQa0GAAwNJ4z/C61m'
    'CYQ0lWG+BVVJS3el7L579x7NTGNj5qmlo+/fv79p87YWCwsKi/YfOEgIW+dWjh499vkXgyd/PeXkqR/rnj5VOE6VsnObra0tc2FQ'
    'YICxcXd5WSQSFRQU0lV8fhYt+/n5mpqaKm9AQ0MDM26rMTPdlZJyq7ycVqVSaUzswsbGRlZPvEml0iyBcPqMWU7OA3z9Atcnbywu'
    '/q1FOvK3v05WOLxBCMnOyWX2YHZOLp2OMTDghr87fqqQ8+fz+FkCtWemEon0yJF0Wr1yNb+0tEylxFzpOEdoWKQuzMo2NjYWFhVv'
    '3LRllG/AMA/vkpKbdJW7+2DCmGnz9BhGq1GREcz8q7K8lMvlMte2m5ZqTmba2NjE7A1CWDllf+3qr/R0Khy9Lq+o2Ljp7RSouZlZ'
    'WzNtyrG37zOEIZaKmWlUZAQB6pKjsKjobVo6fx4dCmTy5Zdf0LJIJGprpq1dvvoqSqVL/q5vaWaqunyQ48Nz5sxPtOzi4szPPD0x'
    'ZIK1lZWhgYGRkdFAN7ctmzf8c8Y0uk3R71kIc6ZNLBZb29orvNDOmj2Xmb2a9OjRbpMaJJJ2RxQA+Qgf9snOyb15s5TO1zs7OaXs'
    '2q4kF9m9Z29z8hX5zvAG/UhECzL5gg3JSTweT37fO3FiyJ69qSpmpnS+Rls4fOh75RuIRCIXVzetiRwymWzGzNl0KkQ58Qmr79y5'
    'SwgxNu4e4O9Hl58+/a+2XiIWi+kNCCEkOlrVHGL58m+Y8z5APXcrZWW3xowb39Zn4+Q8f/5iydLl3+5uDhshIRPoTNuzZ8/z8i4o'
    'ee3xjJO03M/RkZnBKKG6poaZmQK1fYa0tLTM22f0qJE+QUGBbm5/Mjcz79LFSCx+VVdXV15RceHCxdNnfqIzloSQSMZEpUAgbJBI'
    'lOz80qWfHz9+3KtXr+a0NDoqP/+aiplp2KRQe/s+OP1EQ76a4O09fOniRY6OfV+/eVNScjMpKfna9QKcAMhBCCH7UvcwBzzq6+tH'
    'jPS9ffsOzgG+t0ISk9bb9naw69N3beJ6QgiPx/P388UJYLschoaGVpaWjx+LJBLJJ590MzVtnrB++fIlTgDbH8Hg6Ng371xO63sZ'
    '5u0GYPvzOZqamsRiceXt25mZWXtT99EPvwB8kRog5wCQA0AOADkAgBwAcgDIASAHgBwAcgDIASAHgBwAcgAAOQDkAJADQA4AOQDk'
    'AJADQA4AOQDkAAByAMgBIAeAHAByAMgBNJT/A5a/4Id308QlAAAAAElFTkSuQmCC'
)
IKON_512_B64 = (
    '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'
    '9d91Y7Omzzyd3A/Zt2//RaUu/cP/VbZsmcUL3844Ze+llyd26dr9f/7jdZUrzZk9I/kPfv/9D1eU+/8nPS4u7q035pcrd2WYL+3c'
    'pfvLr0xMw19x2WWXLl74dlxcXMQtV6z8pEHDJsePH//v/7h61YoiRQqn74lYsGBhm6T2uoDOLDly5Lj3nrs/+3TlxFdebNq0cQpa'
    '/yAISpa8qNPdHRcvfPutN1+rX69ujH/CJRdfHKb1D4KgfbukTJkypePRHjTw4ZQdYSI6duzYg527Hj16NMzGvXt1z5Mndxp++5DB'
    'A8O0/keOHH3woS7/0/ojANJHs6ZNViz/8OF+ffLnz58mOyx/9VUvvzRh7uwZpUqVjNmvSEpqE3LL889PqFrl+nQ84AUKFOjdq6eC'
    'FyVr1qx9+pnnwmyZL1++Ht27pdX3NmxQv8r114XZctz48evXb3CmBEA6O/vss58a/8SzzzxVoECBNN955cqVFr3zjxbNb47BDzkr'
    'a9aWLU7ii9q3S0rfI//XW9pdVa6c6hclw0eM+vbbb0OeiNKlL0uDEnjWWf0f7htmy6+++nrU6LHOkQBIZ7ly5ZwxbXLzm2+K3ldk'
    'z559/LjHu3Z5KNq/pX6Devny5TuJ7evXi0bmndQw+6iRj4TpLiAFfv311y5de4TZMi4ubtiQQan/xrs6djj//IQg1MBDt0OHDjlH'
    'AiA9ZcuWbfq0KRUrVojBd3Xr2vmB+/8W1a9IatsmOMnh7jaJrdL3FFxxxeW33fZXNTBKFr/73oyZs0LeqjZr2iQ131WwYMEHHwhV'
    'wl99dcoHS5c5OwIgnQ0bOujqq2LXBdGrZ7eGDepHaeclihdPQZ9+u6Q26TsUHARBz+5dCxcupBJGSZ++/Xf/9FOYLQf075cjR46U'
    'f1GvHueee27EzXbu3Nl/wCDnRQCks3p167RLahvLb8yUKdNjYx8tVKhgNHbetm1i5swnfR4TEhKqVa2SviciZ86cgwcOUAmjZNeu'
    'XQ8/HOrwFi1aJOQl/O9deeUVrVq1CHUZ1LvfT3v2OC8CID1lyZIl5GhV2sqdO9ewIYOj0ZneunXLlH32lvZJ6X46mjZtXKNGdfUw'
    'SqZMnf7+kg/CbHlPp7sSEhJS8BVDBg0Ic/2xcOGi2XPmOiPeBE5nLVs2v+iiC0Nu/OWXX73+xpurP/ts/boNu3/6af/+/SeOH8+Z'
    'K1e+fHlLl77sqnLlbmzWtGjRIiH31rhxw8svL/vZZ2vS8OfUrFm9WNEUvspXt27dggULbt++PX3PyIhHhl5ftYaBwSjp3KXbkvcW'
    'Zc+ePYj0GM/gQf3btb81OMl38a699pqIm/3yyy9du3nwVwBkACHHS5f/a0X/AYM+/nj5H95Z79q1a9OmL+bOnT9w0JAmjRsNGTyg'
    'YMFQ3Tv33dvpzo6d0nH4N/jdUPDYx55I3zNy/vkJDz7wt0eGjwxi+7B8gULFTvZTLZrfPH7c40Gkd1zr1W+UcQr8N99sHjV6TJ/e'
    'PcN0jdasWWPRosVB6Ifc+vXrHWbLYY+M2LJ1a5r8nGY3Nl+67EMNty6glDjvvPNCTpbQsFHTP2z9/8fx48fnzJ1XpVqtDRs3hvkD'
    'GtSvlzt3rrT6OfHx8XVuuCE1e8gIQ8FBENx33z0lS16kNkbJuPF/X7dufRCuPydr1rAXhffd26l4scghumrVp88+N8FZEADpr3Kl'
    'ayNu8+yzzz/x5PgTJ06E3+3u3bubt2gdZoArW7ZstWrWTKufk9i6Zfjq+meJWL1a1XQ/L2dlzTpi+DC1MUqOHg079ULJkhd1vLND'
    'EG7c+L57O4X66s5djx075iwIgPR31VVXRbyiH/v4kynY848/bh80aGiYLatWTbNpGNoktk79TtpngKHgIAiqXH9dVF/KO8Ot/GTV'
    '88+/EGbLzg89EOZxtX59e4d5cvSpvz+TXnMjIgD+V7FiEcZLt23bluJB0clTpu7YsSNyCKXRFAiVKv0lTbpN6tWtE3IAI9oGDuiX'
    'hv1j/I8hw4Zv++67iJude+65/fpG6NmvWKH8zTfdGHFXmzdvHjFytCMvADKKPLlzR7pjTfm96tGjR6fPmBXmLjtNpkBo2yYxciZN'
    'nhrxxj9LlixpcicRmCQuY/v555+7hXsUp0Xzm5MZKsuUKdOQIQPD7KdL1x4HDx505AVAhvm1kVreEiWK582TJ8X7f/e994MQ02ad'
    '1Lw9wZ9MZNSkccPktzlx4sTI0WMWLXo3iDw3XJsUvEoWDbe0T4rlG9pnmrcXvDNv3mtBiPcWhw0d/GdFolWrFmHuYqdNnxGmOiAA'
    'YufA/v0RL4fvvPOOFO9/xYoVYYba8uXNm8ofcvNNN0bsgX1/yQdbtmx5ZeKkiHsrUaJE9erVMshabKNGDjdJXPT07N137959QYj3'
    'e//wFvOcc87pE+Iubffu3X37ecdbAGQwW7dti7jNA/ff16B+vZTtf9++/YWKlChQqFjy/2z8/PMg+o//T5o0+beLvh9/3B7iJqBt'
    'BjlHl19e9vbbblUzo2T79u0DBw0Js2Wf3j1+PyTzwP33hRki7ttvwO7dux1tAZCxbNjweZi5Il6Y8OyA/v0y7KpVZcuWueKKy5Pf'
    'Zs+eva+/8WYQBEePHp08ZWrEfdatc0OUpipKyVVqD5PERdErEyd9+OE/Qy0X061r8H8fGu50d8cgREfotOkzHGcBkOEsXbYsZEdE'
    'p7s7rlq5fNDA/pdcfHFG+xVhZrKbMWPm4cOHf/v3iZMmR3ytIUuWLGFGlYO0mKo+CPEgytDBpo2MlhMnTnTu2v0/xSMZt956y2WX'
    'Xvpfk4b2Peuss5L/yMGDB0MuRYAAiLV169Zv3rw5CD1X5V0dO3ywZPHihW8/+MDfLrvs0ozwE7Jnzx7mCbyJr04O/utpvCUfLA1C'
    'LCoZg6HgSZMmh+mSaty4Yc2aNdTPKNm06YswU4DExcUNGzb4PyvUN2rYIAixGFn4KoYAiPW1z8RJU4KT73Lp1bP7++8uXL1qxeNj'
    'H23ZonmK519LvSaNG0V8WP7TT1evXbvu/9z1vzIpzLoCMZiYc/+BA336PhyEmiRuSLZs2VTRKHnssSc+37Qp4mbXVa7UtGnjzJkz'
    'Dxk8MMwMS39/+lnHNjAZXIY14YUX7ul0V548uVPw2SJFCicmtkpMbBUEwbfffrt06YdLPlj63vtLYjmhZlLbyB01k/7r8v83b7zx'
    '5u7duyM+fnpL+6SFCxdF+yfMmTuvTZvWNSI9d5SQkPDQg/cPe2SEWhoNh48ceahzt/lzZ0WcDGpA/35FChcuU6Z08psdO3bswc5d'
    'jx49Gt3CM3tG9NbPefqZZ90BnOb27ds/fMTINJlXLjGx1fhxj6/97JP3Fr/Tu1ePCuWvjvbEahdeeEGlSn8JInXCzpo95/e1feq0'
    'yDWnzg21YzP62r1HrzDzP997byeTxEXPRx99/HKIW8NiRYsOGtg/4mbPPjdh1apPHVUBkNE9P+HFtF2YtHTpyx64/74335i/etWK'
    'wYP6R3xEJ6pPf85/7fU/fNA7zAsBcXFxsRkK/vrrb8L0QZ+VNevIEY+opdEzcNDgMEMyEW3ZutW9mgAITpWRgDs63LVly5Y033Ph'
    'woU63tlh4YK3Fr3zj8TEVmdlzRqk6VpmrVo2D8I9/h/80bjfRx99nEGGgoMgePyJcV9++VXEza6/rnKL5jerqNG7Ie7Rq0/q99O1'
    'W89ffvnF8RQAwamyXGrzlonff/9DELW3mR4f++jyjz9Mwxku69a5IeKsbd98s3nZnz/iHeYmoHixYjVrVo/BKTh8+HC37j1NEpfu'
    'Xnvt9Tff+kdq9jBr9pwYDB0hANLSV1993bjpTWEehEixokWLPDX+iXlzZpYoXjyISf/PpFenJPPI/9x5r4WZBuCW9u1icwreX/LB'
    'zFmzgxDr3vTt01tdjZ4ePXsfOHAgZZ/9ac+e3n0edgwFwKln8+bNdes1mjjp1ah+S6VKf3lnwZtVq6RqGYAiRQrXqFEt4mMYU6dN'
    'C5IdH54xM/J8pTfUrlWkSOHYnIK+/Qbs27c/CLFyWfmrr1Jdo+S7774fMjSFYy0P9x+4c+dOx1AAnJIOHDjw4ENdGzZu9q8VK6P3'
    'Lfny5Zs8eWKtWjVTsfhXq4hTpC1a9G7ETq0MNRQcBMGOHTuGDB1mkrgg/R+PfikFVeCDpcsmT57q6AmAU9vHHy+v36Bx8xatFy1a'
    'fFKLQQYns+rhSy88V7FihRR8NlOmTG3btE7B4/+/t3btuk9WrQpCDAXHrLV98aVXwvxJZcuWueP225TVKDl+/PhDnbseOXIST/Ef'
    'OnSoc5duDp0AOE289/6SVolJFa6pPGr0mK+++jrN958tW7Znnh6fgvHMqlWuP++885LfZufOnW8vWBBmb6+88mqYR79rxWomhuPH'
    'j3fp2iPMsrE9uneJWd/UGWj9+g3jxj8VfvtRo8dGo5oQeBM4HX377bfDR4waPmJU6dKX1a9Xt3btWleVuzKtLoeLFys2aED/vz3w'
    '0El9Kikp8vDv1GkzQl6+zZo9Z9DAh88555wg0lrBby94JzbHfPXqzyZMeLFDh9uDyJPEDbz19juV0igZNXpMk8aNLrzwgnBpMT72'
    'f2GzG5svXfahM+UOIIjBzHGjHx1bv0Hjiy8tc8tfb3/uuQnrN2xI/W5btmxeqlTJ8Nvny5s3zPoEYfp/gn8vDTh7ztyIm9WuVbNo'
    '0SIxO9rDho/84YcfI27WqFHD1AylEETq1eneo1eYLR98qMtJ9RchAIJT92WZN958q2fvvlWr1SpdtlzHu+6Z9OrkMGvLBH8yxPq3'
    'e+8Jv32LFs0jzsG7fPm/Nm36Ivw+w8wNFxcXF+bB07Syf//+Pv1CPU04fNjg7NmzK5bRuu5ZH+oqZ8XKTxyrQBfQmWbHjh2zZs/5'
    'bbKdi0uVql27Zr26da699pqTenu2QYP6ISdkD4KgbdvIw78VK1bY8eO2NP+xbdskjn50bJje+TQxd+78tomtI85ImpCQ0Pmh+4cM'
    'Ha40gjuAdPP5pk3jn3q6SbObry5/7YiRo3f/9FMQekn3qlVDvRZQofzV/70iR4wVLVqkdmz7W7qFmySuU6e7T6obDRAA0bLtu+9G'
    'jnq0fIW/vPzKxJAfKXfllUEaDf9GVczeCg7+PZXFmLGPByaJAwEQnGrvlHXu0n3EyNFhNi5T+rKI25xzzjnNmjZJ3x9Vq1aNGK9+'
    '88QT47744ssgxEIlLVs0V+ogMAYQhFhJsUB8fHx8fHyB/Pnz5//t3/Pnz18gPn98fHz++Pw5smcvc/lVqV/OYtToMfXr1b388rLJ'
    'b1Y8xOxANzZrGvFhzahfIGTOnJTUZviIUUEMFyrp1r3nrJnTIm5Zu7bHgUAAhLD8o2URlzopd+UVqZ8Q4sSJE69OmTosUgDkypUr'
    '4/f/BP8eCh41ekzMhoKDIFjywdIZM2el4USqwBndBbTpi8hPSVZJ3Xxt/7Fxw8aI25x7boRL+0svuSSDTH9WpEjhG2rXivGX9nt4'
    'YJiJSwEBEIR4cXF9EGLCtTRZ0zFrpMf2gyD49ddfk9+gXbs2GefoxXgoOAg9SRwgACL76OPlEbe54ILzq0daqTwIt3JvxG2Sf2b0'
    'rKxZm2ekZbBq1qxevFixGH/pSy9PXPnJKlUUBEBqffjhR2Gm+ezXp1eWLKkdF7mpWdOI22zbui35N8Xy5c2bgUpJ5syxH5A4fvx4'
    'l67dYzn2AIFB4OA0fYN3xcpPKpS/Oog05/C999wdZr3yP1Ovbp0wcz4nP9ocprWdN++12zt0TP2RyZo1y5rVn+TLly8IMRSc+qek'
    'Tspnn615fsILd3a4Q0UFdwBB6mYamBdms549ut18040p+4qSJS8aOybUE5PJrM9eokSJMMuHhVnbK4wjR47OnDk7zHr3dW6oHfuz'
    'NuyRUJPEAQIgOVOnTo849Ppbd8e4Jx+7q2OHk5reJwiCCuWvnj93Vv78+YMQS1EmM5dWUtvEiGPRe/bsTcNluF+dEmpRp/bt2gbp'
    '8Xpd7779VFQQAKny0549U6fNCMJN2DloYP/X5s+pVrVKmOeCihcrNmzo4NdfmxsfHx+qwZ089c8GJOLi4lq3ahlxD/Pmzz985Eha'
    'HZk1a9auXbsu4mY1alRPk9XtT9a8ea8tWrRYXYXAGEBqjH50TKuWzXPkyBFm44oVys+YPuWbbza/9Y+3V6xYuW7d+p/27Nm7d28Q'
    'BDlz5syVK2fJkheVLVOmatUq11WuFP750b1797344svBnz9vE2YW/hkhOm1OypSp0wYN7B/x3qhdu7ZDh6XDNJzdevReumRxtmzZ'
    '1Ngz3JzZM6L9FV988WWl66oKgNPQDz/8OGbs4716dg//kfPPT7irY4c0/BvGjH0smWdAw0zBv+277/75z4/S9shMnzGrX98+WbNG'
    'KA9tEluPGDk6xkPBQRBs3rz50TGP9exhBVoIdAGl3BNPjk/Hp8vXrFn77HMT/uz/FihQIMxA68yZs9N85fpdu3YtXBR5UKFQoYJ1'
    '69yQLofuySfHh5kkDhAAf+ro0aN33NFxx44dsf/q/fv333bHncmsA5PYumWYtxBmzpodjT9vypRpQai3gpPS5cQdPnKka7ceaiwI'
    'gFTZsnVrm6Rb9u3bH9P26/DhDh07ff31N0GyHSwR97N+w4Z169ZH4y98e8GC3bt3R9ysWrWqJUqUSJcT98HSZdNnzFRpQQCkyqpV'
    'nzZpdlPM7gN+/fXXxDbtkn9ws3LlShdddGGY/p8o/ZEhXwjInDlz+/Sbp8gkcSAA0sDatetq1q67bNmH0f6iDRs3NmjU9P0lHyS/'
    'WVLbxCDEXNOzZs2J3p8a8oWANomtUz9hRsrs3Llz8JCh6i0IgCD1DwXd1LxVz1599uzZG439Hzp06MlxT9W+of6aNWuDSKsEN27U'
    'MAjx/vCWrVuDaI5Rh3khoGDBgvXq1kmvs/byK5OSeY0OEABhHTt27LnnX7jm2sqPDB+Zhj1CP//887PPPl/hmkoDBg4Os8p5i+Y3'
    'Z8+ePYjV9A9Bsi8EhNmsfToNBQcmiQMBEKT1S8KjHx1b7qqKbZNumTptxvbt21O8n/nzX7+9Q8dLS1/Rq0+/8JPYtG2TGKaPft68'
    '16J9KKbPmHXkSOTH/KtXq5qQkBCk39O0zz0/QbmFVMoUX7Coo/B7pUqVLHfllZdccnH9+nUvLlUqUqfExH/+8+MVK1d+9dXXDh1w'
    'qog7+5ycjsLv7d69e9269XFxcXd1vDPixqVLl965c+eCBe8cPHjIoQMCXUCngVq1agThptS/7dZb3l38TqlSJR00QACcDmrUqB5+'
    '42JFi86eOT3iyioAAiCjy5Mn99q163r16degYZPyFStdcNElRYolXFbmypat2syaPecPZ+MpVKhg3z49HTogMAh8Gktq22bMoyN/'
    '/99/+eWXUpeUSWbCHwB3AKe2iZNe/cNZRc8+++zixYs5PoAAOJ1t+XZL8CdvKjk4gAA4bWXLlu2aayoGfzTv27Zt2xwfQACcnnLl'
    'yvn038cVKVL49/9r7tz5Yd6kBQgMAmcouXPnatK48a5du3bs3Llr164DB34+dOjgwYOHjhw5ki1btrx581xcqlT16tUSW7f8w8c9'
    'd+3aVb3mDeFngAAIrAmcQeTLl+/R0SNS9tnt27cntbtV6w8EuoDOHCdOnJg1e07tOvU/WbXK0QDcAZwR9uzZ+9Y/3n7u+Qmffrra'
    '0QACYwCntLJly1Stcn3p0qUvvPCCggXi8+bNlz17tixZshw9evTAzz//fODArl27P9+0aePGz1ev/mzpsmWGfAEBAEBgDAAAAQCA'
    'AABAAAAgAAAQAAAIAAAEAAACAAABAIAAAEAAACAAABAAAAgAAAQAgAAAQAAAIAAAEAAACAAABAAAAgAAAQCAAABAAAAgAAAQAAAI'
    'AAAEAAACAAABAIAAAEAAACAAABAAAAgAAAQAAAIAAAEAIAAAEAAACAAABAAAAgAAAQCAAABAAAAgAAAQAAAIAAAEAAACAAABAIAA'
    'AEAAACAAABAAAAgAAAQAAAIAAAEAgAAAEAAACAAABAAAAgAAAQCAAABAAAAgAAAQAAAIAAAEAAACAAABAIAAAEAAACAAABAAAAgA'
    'AAQAAAIAAAEAgAAAQAAACACHAEAAACAAADjd/T8Z+ftIeIkZfAAAAABJRU5ErkJggg=='
)
