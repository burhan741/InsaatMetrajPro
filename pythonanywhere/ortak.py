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


def tarih_tr(iso):
    """'2026-11-04' -> '04.11.2026'. Bos/bozuk deger oldugu gibi doner."""
    if not iso:
        return ''
    parca = str(iso)[:10].split('-')
    if len(parca) != 3:
        return str(iso)
    return parca[2] + '.' + parca[1] + '.' + parca[0]


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
<meta name="theme-color" content="#f4f5f7">'''

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
    if os.path.exists(normal_yol) and os.path.exists(kalin_yol):
        pdfmetrics.registerFont(TTFont('DejaVu', normal_yol))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', kalin_yol))
        sonuc = ('DejaVu', 'DejaVu-Bold')
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
