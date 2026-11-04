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
