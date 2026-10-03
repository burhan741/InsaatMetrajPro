# -*- coding: utf-8 -*-
"""
AutoCAD Canlı Bağlantı Modülü (COM Automation)
==============================================
Profesyonel metraj yazılımları gibi AutoCAD ile canlı bağlantı kurar.
win32com.client kullanarak ActiveX/COM üzerinden iletişim sağlar.

Yazar: İNŞAAT METRAJ PRO
Tarih: 2026
"""

import logging
import re
import os
import time
import math
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)

# win32com opsiyonel import
try:
    import win32com.client
    import pythoncom
    from pywintypes import com_error
    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False
    logger.warning("win32com.client bulunamadı. 'pip install pywin32' ile yükleyin.")

try:
    from app.core.com_mesaj_filtresi import mesaj_filtresi_kaydet, kisa_bekleme, vazgecme_sayisi
except Exception as _filtre_hata:  # filtre yoksa araçlar yine çalışır (retry katmanı devrede)
    logger.error(f"COM mesaj filtresi yüklenemedi: {_filtre_hata}")
    from contextlib import nullcontext as _nullcontext

    def mesaj_filtresi_kaydet() -> bool:
        return False

    def kisa_bekleme(azami_ms):
        return _nullcontext()

    def vazgecme_sayisi() -> int:
        return 0

# Rev-156: bağlanırken AutoCAD meşgulse (açık iletişim kutusu / devam eden komut) en fazla bu kadar bekle
BAGLANTI_MESGUL_MS = 3000
AUTOCAD_MESGUL_MESAJI = (
    "AutoCAD şu an komut kabul etmiyor (meşgul).\n\n"
    "AutoCAD ekranında açık bir pencere/uyarı olabilir — ideCAD çizimlerinde sık görülenler:\n"
    "  • Proxy bilgileri\n  • Eksik SHX font dosyaları\n  • Çizim kurtarma / Denetim\n"
    "ya da yarım kalmış bir komut.\n\n"
    "Çözüm: AutoCAD'e geçip açık pencereyi kapatın, komut satırında ESC'ye 2 kez basın, "
    "sonra 'AutoCAD'e Bağlan'a tekrar basın."
)

# win32gui opsiyonel import (pencere yönetimi için)
try:
    import win32gui
    import win32con
    WIN32GUI_AVAILABLE = True
except ImportError:
    WIN32GUI_AVAILABLE = False


class AcadColor(IntEnum):
    """AutoCAD renk sabitleri (ACI - AutoCAD Color Index)"""
    RED = 1       # acRed
    YELLOW = 2    # acYellow
    GREEN = 3     # acGreen
    CYAN = 4      # acCyan
    BLUE = 5      # acBlue
    MAGENTA = 6   # acMagenta
    WHITE = 7     # acWhite
    GRAY = 8      # Gri
    ORANGE = 30   # Turuncu (iç kiriş)
    BYLAYER = 256 # Katmana göre


class AcadEntityType:
    """AutoCAD entity tip isimleri"""
    LINE = "AcDbLine"
    POLYLINE = "AcDbPolyline"
    LWPOLYLINE = "AcDbPolyline"
    POLYLINE_2D = "AcDb2dPolyline"
    POLYLINE_3D = "AcDb3dPolyline"
    CIRCLE = "AcDbCircle"
    ARC = "AcDbArc"
    TEXT = "AcDbText"
    MTEXT = "AcDbMText"
    BLOCK_REF = "AcDbBlockReference"
    HATCH = "AcDbHatch"
    DIMENSION = "AcDbDimension"
    SPLINE = "AcDbSpline"


@dataclass
class MetrajObjesi:
    """Metrajı alınan obje bilgisi"""
    entity_type: str
    layer: str
    handle: str
    # Geometrik veriler
    uzunluk: float = 0.0
    alan: float = 0.0
    cevre: float = 0.0
    # Özel veriler
    blok_adi: str = ""
    text_icerigi: str = ""
    koordinatlar: List[Tuple[float, float]] = field(default_factory=list)
    # Orijinal renk (geri almak için)
    orijinal_renk: int = 256
    # Ek özellikler
    ozellikler: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DemirBilgisi:
    """Demir metraj bilgisi (AutoCAD'den okunan)"""
    handle: str           # AutoCAD handle (referans için)
    orijinal_metin: str   # Orijinal metin içeriği
    adet: int = 0         # Demir adedi
    cap: int = 0          # Çap (mm) - Ø değeri
    boy: float = 0.0      # Boy (cm veya m) - L değeri
    toplam_boy: float = 0.0    # adet x boy
    agirlik_birim: float = 0.0 # kg/m (çapa göre)
    toplam_agirlik: float = 0.0 # Toplam ağırlık (kg)
    katman: str = ""      # AutoCAD katmanı
    gecerli: bool = False # Regex ile eşleşti mi?
    hata_mesaji: str = "" # Eşleşmediyse neden
    eleman_tipi: str = "" # Kolon / Perde / Kiriş / Döşeme / Temel (kesim optimizasyonu için)


# Demir çap -> kg/m tablosu (nervürlü)
DEMIR_AGIRLIK_TABLOSU = {
    6: 0.222,
    8: 0.395,
    10: 0.617,
    12: 0.888,
    14: 1.208,
    16: 1.578,
    18: 1.998,
    20: 2.466,
    22: 2.984,
    24: 3.551,
    25: 3.853,
    26: 4.168,
    28: 4.834,
    30: 5.549,
    32: 6.313,
    36: 7.990,
    40: 9.865,
}

# Qt event loop — modül seviyesinde import (method içi import overhead'ı kaldırır)
try:
    from PyQt6.QtWidgets import QApplication as _QApplication
    _QT_AVAILABLE = True
except ImportError:
    _QApplication = None
    _QT_AVAILABLE = False

# ── Demir regex kalıpları — modül seviyesinde derlenir ──────────────────────
# Method çağrısı başına re.compile() overhead'ı sıfırlanır.
# Python'ın iç cache'i ne olursa olsun modül import'unda bir kez derlenir.
#
# BİRLEŞİK PATTERN — iki ayrı arama yerine tek arama:
#   Grup 1: carpan  — opsiyonel "2x" / "3x" çarpan (None → 1 kabul edilir)
#   Grup 2: adet    — demir adedi
#   Grup 3: çap     — mm cinsinden çap
#   Grup 4: boy     — L= değeri
#
# Desteklenen ayraçlar: Ø ø ƒ φ Φ ∅ T t Τ ? (encoding bozulması)  ve AutoCAD %%C / %%c
# Not: Bazı DWG dosyalarında Ø karakteri encoding sorunu nedeniyle ? olarak gelebilir.
_DEMIR_PATTERN = re.compile(
    r'(?:P\d+\s+)?(?:(\d+)\s*[xX*]\s*)?(\d+)\s*(?:[ØøƒφΦ∅TtΤ?]|%%[cC])\s*(\d+).*?[Ll]\s*=\s*(\d+(?:[.,]\d+)?)',
    re.IGNORECASE
)
# Eski _DEMIR_PATTERN_AUTOCAD artık gerekli değil;
# backward compat. için alias olarak bırakıldı.
_DEMIR_PATTERN_AUTOCAD = _DEMIR_PATTERN
_DONATI_PATTERN = re.compile(
    r'(?:P\d+[-.])?(\d+)\s*[ØøƒφΦ∅?]\s*(\d+)',
    re.IGNORECASE
)
_DONATI_PATTERN_AUTOCAD = re.compile(
    r'(?:P\d+[-.])?(\d+)\s*(?:%%[cC]|[?])\s*(\d+)',
    re.IGNORECASE
)
# Faz-2 kısmi eşleşme pattern'ları (ayrı TEXT objeleri için)
_DEMIR_KISMI = re.compile(
    r'(?:(\d+)\s*[xX*]\s*)?(\d+)\s*(?:[ØøƒφΦ∅TtΤ?]|%%[cC])\s*(\d+)',
    re.IGNORECASE
)
_L_KISMI = re.compile(r'[Ll]\s*=\s*(\d+(?:[.,]\d+)?)')

# ── İhale Demir Metrajı — Aralıklı Donatı (Ø/aralık) okuma (Rev-136) ────────
# AŞAMA 1: SAF (self/COM bağımsız) regex çekirdeği — sahte metin listeleriyle
# AutoCAD olmadan test edilebilir.
#
# Format: "Ø14/20 L=500" (çap/aralık_cm L=çubuk_boyu_cm) — ADET YOK, aralıktan
# hesaplanır (bkz. aralikli_donati_adet_hesapla). Mevcut adetli format
# ("28Ø14 L=442", _DEMIR_PATTERN) ile KARIŞMAMASI için ayrım şu: adetli
# formatta Ø'dan sonra doğrudan " L=" gelir, aralıklı formatta Ø'dan sonra
# "/<aralık>" gelir — regex'in kendisi "/" zorunlu kıldığı için adetli metin
# hiçbir zaman eşleşmez (ekstra dışlama kuralı gerekmiyor).
_ARALIKLI_DONATI_PATTERN = re.compile(
    r'(?:[ØøƒφΦ∅TtΤ?]|%%[cC]|[OD])\s*(\d+)\s*/\s*(\d+)\s*[Ll]\s*=\s*(\d+(?:[.,]\d+)?)',
    re.IGNORECASE
)


def aralikli_donati_ayristir(metin: str) -> Dict[str, Any]:
    """Ø/aralık formatlı bir donatı yazısını ("Ø14/20 L=500") ayrıştırır.

    Neyi çözüyoruz?
    İhale/döşeme çizimlerinde donatı bazen adetle değil, dağılım aralığıyla
    etiketlenir (çap 14, her 20 cm'de bir, çubuk boyu 500 cm). Mevcut demir
    okuma araçları (_DEMIR_PATTERN) sadece adetli formatı ("28Ø14 L=442")
    tanır — bu format için adet, kullanıcının gireceği dağılım mesafesinden
    ayrıca hesaplanmalı (bkz. aralikli_donati_adet_hesapla), burada sadece
    çap/aralık/boy çıkarılır.

    Nasıl test ederiz?
    "Ø14/20 L=500"  -> basarili=True, cap=14, aralik_cm=20.0, boy_cm=500.0
    "Ø12/15 L=320"  -> basarili=True, cap=12, aralik_cm=15.0, boy_cm=320.0
    "28Ø14 L=442"   -> basarili=False, ilgisiz=True (ESKİ adetli format,
                        bu araç ATLAMALI — "/" yok, regex hiç eşleşmez)
    "bozuk"         -> basarili=False, ilgisiz=True

    Args:
        metin: Ham TEXT/MTEXT içeriği (temizlenmemiş olabilir).

    Returns:
        dict: ham_metin, temiz_metin, basarili, ilgisiz (desen hiç yoksa
              True — çağıran sessizce atlamalı), cap (mm, int),
              aralik_cm (float), boy_cm (float), coklu_eslesme, hata.
    """
    temiz = mtext_temizle(metin) if metin else ""

    sonuc: Dict[str, Any] = {
        "ham_metin": metin,
        "temiz_metin": temiz,
        "basarili": False,
        "ilgisiz": True,
        "cap": 0,
        "aralik_cm": 0.0,
        "boy_cm": 0.0,
        "coklu_eslesme": False,
        "hata": "",
    }

    if not temiz:
        sonuc["hata"] = "Boş metin"
        return sonuc

    eslesmeler = list(_ARALIKLI_DONATI_PATTERN.finditer(temiz))
    if not eslesmeler:
        sonuc["hata"] = "Ø.../aralık L=... deseni bulunamadı — ilgisiz metin"
        return sonuc

    sonuc["ilgisiz"] = False
    ilk = eslesmeler[0]
    if len(eslesmeler) > 1:
        sonuc["coklu_eslesme"] = True

    try:
        cap = int(ilk.group(1))
        aralik_cm = float(ilk.group(2).replace(",", "."))
        boy_cm = float(ilk.group(3).replace(",", "."))
    except (TypeError, ValueError):
        sonuc["hata"] = "çap/aralık/boy sayıya çevrilemedi"
        return sonuc

    if cap <= 0 or aralik_cm <= 0 or boy_cm <= 0:
        sonuc["hata"] = f"Geçersiz değer: Ø{cap}/{aralik_cm} L={boy_cm}"
        return sonuc

    sonuc["basarili"] = True
    sonuc["cap"] = cap
    sonuc["aralik_cm"] = aralik_cm
    sonuc["boy_cm"] = boy_cm
    return sonuc


def aralikli_donati_adet_hesapla(aralik_cm: float, mesafe_m: float) -> int:
    """Dağılım mesafesinden donatı adedini hesaplar (uç çubuk dahil).

    Neyi çözüyoruz?
    "Ø14/20" demek her 20 cm'de bir çubuk demek — kullanıcının girdiği
    dağılım mesafesi (m) boyunca kaç çubuk gireceğini bulmak için mesafe
    aralığa bölünüp yukarı yuvarlanır, +1 ile başlangıç ucundaki çubuk da
    sayıma eklenir (kullanıcı onaylı kural, bkz. brief madde 5).

    Nasıl test ederiz?
    aralik_cm=20, mesafe_m=4.0 -> ceil(400/20)+1 = 21
    aralik_cm=15, mesafe_m=3.2 -> ceil(320/15)+1 = ceil(21.33)+1 = 23

    Args:
        aralik_cm: Donatı dağılım aralığı (cm).
        mesafe_m: Kullanıcının girdiği toplam dağılım mesafesi (metre).

    Returns:
        int: Hesaplanan donatı adedi (aralik_cm veya mesafe_m <= 0 ise 0).
    """
    if aralik_cm <= 0 or mesafe_m <= 0:
        return 0
    mesafe_cm = mesafe_m * 100.0
    # Rev-153: ikili kayan nokta — 1.10 m × 100 = 110.00000000000001 -> /10 = 11.0000000001
    # -> ceil 12 (+1 fazla çubuk). Tam bölünen değerler için oran 9 haneye yuvarlanır.
    return math.ceil(round(mesafe_cm / aralik_cm, 9)) + 1


def aralikli_donati_hesapla(cap: int, aralik_cm: float, boy_cm: float,
                             mesafe_m: float) -> Dict[str, Any]:
    """Aralıklı donatı için adet/toplam boy/ağırlık hesabını tek seferde yapar.

    Neyi çözüyoruz?
    aralikli_donati_ayristir ile çıkarılan çap/aralık/boy + kullanıcının
    girdiği dağılım mesafesinden adet, toplam boy (m) ve toplam ağırlığı
    (kg) hesaplayıp DemirBilgisi'ne aktarılacak hazır bir sonuç üretir.
    CM->M dönüşümü burada TEK YERDE yapılır (kolon betonundaki 1000-kat
    hatasının tekrarını önlemek için — bkz. CLAUDE.md Rev-134 dersi).

    Nasıl test ederiz?
    cap=14, aralik_cm=20, boy_cm=500, mesafe_m=4.0
    -> adet=21, boy_m=5.0, toplam_boy_m=105.0, toplam_agirlik_kg=126.84
       (105.0 * DEMIR_AGIRLIK_TABLOSU[14]=1.208)

    Args:
        cap: Donatı çapı (mm).
        aralik_cm: Dağılım aralığı (cm).
        boy_cm: Çubuk boyu (cm).
        mesafe_m: Dağılım mesafesi (metre, kullanıcı girişi).

    Returns:
        dict: adet, boy_m, toplam_boy_m, agirlik_birim (kg/m),
              toplam_agirlik_kg, hata (çap tabloda yoksa veya girdi
              geçersizse dolu döner).
    """
    sonuc: Dict[str, Any] = {
        "adet": 0,
        "boy_m": 0.0,
        "toplam_boy_m": 0.0,
        "agirlik_birim": 0.0,
        "toplam_agirlik_kg": 0.0,
        "hata": "",
    }

    adet = aralikli_donati_adet_hesapla(aralik_cm, mesafe_m)
    if adet <= 0:
        sonuc["hata"] = f"Geçersiz aralık/mesafe: aralik_cm={aralik_cm}, mesafe_m={mesafe_m}"
        return sonuc

    agirlik_birim = DEMIR_AGIRLIK_TABLOSU.get(int(cap))
    if agirlik_birim is None:
        sonuc["hata"] = f"Ø{cap} için birim ağırlık tablosu bulunamadı"
        return sonuc

    boy_m = boy_cm / 100.0
    toplam_boy_m = adet * boy_m
    toplam_agirlik_kg = toplam_boy_m * agirlik_birim

    sonuc["adet"] = adet
    sonuc["boy_m"] = boy_m
    sonuc["toplam_boy_m"] = round(toplam_boy_m, 3)
    sonuc["agirlik_birim"] = agirlik_birim
    sonuc["toplam_agirlik_kg"] = round(toplam_agirlik_kg, 3)
    return sonuc


# Rev-142: dağılım mesafesi AutoCAD ölçüsünden (DIMENSION). Sadece UZUNLUK
# ölçen tipler — açısal (radyan döner), yarıçap/çap, koordinat (ordinate)
# ölçüleri dağılım mesafesi DEĞİLDİR.
OLCU_UZUNLUK_TIPLERI = {"AcDbAlignedDimension", "AcDbRotatedDimension", "AcDbArcDimension"}
_SAYI_PATTERN = re.compile(r'\d+(?:[.,]\d+)?')


def olcu_mesafesi_ayikla(measurement: Any, lineer_olcek: Any = 1.0,
                         text_override: str = "") -> Dict[str, Any]:
    """Bir DIMENSION'ın ekranda GÖRÜNEN ölçü değerini (çizim/ölçü biriminde) çıkarır.

    Neyi çözüyoruz?
    `Measurement` ölçekten bağımsız DEĞİLDİR: çizimdeki ham geometrik
    uzunluktur. Ekranda yazan sayı = Measurement × LinearScaleFactor (DIMLFAC)
    — ölçekli çizilip DIMLFAC ile düzeltilmiş çizimlerde ikisi farklıdır.
    Ayrıca ölçü yazısı elle değiştirilmiş olabilir (TextOverride): "<>"
    içeriyorsa gerçek ölçüyü gösterir (yok sayılır); saf sayıysa ve görünen
    değerden farklıysa `override_farkli=True` döner, çağıran kullanıcıya sorar.

    Nasıl test ederiz?
    (400) -> deger 400 | (8, 50) -> 400 | (400, 1, "<> cm") -> override yok
    (400, 1, "450") -> override_deger 450, override_farkli True
    (0) / ("abc") -> hata

    Returns:
        dict: deger (görünen, ölçü biriminde), ham_measurement, lineer_olcek,
              override_deger (float|None), override_farkli (bool), hata.
    """
    sonuc: Dict[str, Any] = {
        "deger": 0.0, "ham_measurement": 0.0, "lineer_olcek": 1.0,
        "override_deger": None, "override_farkli": False, "hata": "",
    }
    try:
        ham = float(measurement)
        olcek = float(lineer_olcek) if lineer_olcek not in (None, "") else 1.0
    except (TypeError, ValueError):
        sonuc["hata"] = "Ölçü değeri sayı değil"
        return sonuc
    if olcek <= 0:
        olcek = 1.0
    deger = ham * olcek
    if deger <= 0:
        sonuc["hata"] = f"Ölçü değeri geçersiz: {deger:g}"
        return sonuc
    sonuc.update({"deger": round(deger, 4), "ham_measurement": ham, "lineer_olcek": olcek})

    metin = mtext_temizle(text_override or "").strip()
    if metin and "<>" not in metin:
        sayilar = _SAYI_PATTERN.findall(metin)
        if len(sayilar) == 1:
            ov = float(sayilar[0].replace(",", "."))
            sonuc["override_deger"] = ov
            sonuc["override_farkli"] = abs(ov - deger) > max(0.01 * deger, 1e-6)
    return sonuc


# ── Poza Göre Donatı Metraj Tablosu — koordinat bazlı satır/sütun kümeleme ──
# AŞAMA 1: Bu bölümdeki fonksiyonlar SAF (self/COM bağımsız) — sahte
# (text,x,y) listeleriyle AutoCAD olmadan test edilebilir. get_kolon_filizi_
# from_table'ın içerik-bazlı (donatı/boy/kolon kovaları) yaklaşımı burada
# KULLANILMAZ: bu tabloda ADET/ÇAP/BOY/TOPLAM gibi birden fazla "saf sayı"
# sütunu olduğu için içerikten ayrım yapılamaz, satır/sütun konumuna
# (X/Y koordinatı) bakmak zorunludur.

_MTEXT_KOD_PATTERN = re.compile(r'\\[A-Za-z][^;\\{}]*;')
_MTEXT_TEKLI_KOD_PATTERN = re.compile(r'\\[A-Za-z]')
_MTEXT_YIGIN_PATTERN = re.compile(r'\\S([^;]*);')


def mtext_temizle(text: str) -> str:
    """MTEXT format kodlarını (\\A1; \\H2.5x; \\C1; {...} \\P vb.) temizler.

    Neyi çözüyoruz: AutoCAD'de tablo hücreleri bazen düz TEXT değil MTEXT
    olarak girilir; MTEXT ham TextString'i "\\A1;5,30" veya "{\\C1;POZ 1}"
    gibi görünmez format kodları içerebilir. Bu kodlar sayı/regex parse'ını
    (örn. boy_pattern, çap normalizasyonu) bozar. Düz TEXT için hiçbir
    eşleşme olmadığından metin DEĞİŞMEDEN döner (zararsız).
    Nasıl test ederiz: scratchpad/test_poz_donati_kumele.py — düz metin,
    \\A1;/\\H..;/\\C..; kod örnekleri, {...} gruplama, \\P paragraf ve
    \\Sxxx^yyy; yığın kesir örnekleriyle beklenen temiz çıktı karşılaştırılır.
    """
    if not text:
        return text
    t = str(text)
    t = t.replace('\\P', '\n').replace('\\~', ' ')
    t = _MTEXT_YIGIN_PATTERN.sub(lambda m: m.group(1).replace('^', '/').replace('#', '/'), t)
    t = _MTEXT_KOD_PATTERN.sub('', t)
    t = _MTEXT_TEKLI_KOD_PATTERN.sub('', t)
    t = t.replace('{', '').replace('}', '')
    return t.strip()


# ── Kolon Beton/Kalıp — YAZI TABANLI toplu okuma (Rev-134) ──────────────────
# AŞAMA 1: Bu bölümdeki fonksiyonlar SAF (self/COM bağımsız) — sahte metin
# listeleriyle AutoCAD olmadan test edilebilir. Geometriden (BoundingBox/
# Area) alan okuma TERK EDİLDİ — Rev-133 debug kanıtı: kolon polyline'ları
# Closed=True olsa bile 1/50 ölçek + mm birim belirsizliği yüzünden
# BoundingBox/Area gerçek boyutu vermiyor (0.01x0.01 birim gibi anlamsız
# değerler). Kolon etiket yazısı (örn. "SZ12 (50/50)") ölçekten bağımsız
# gerçek tasarım boyutunu taşıdığı için bunun yerine kullanılıyor.
#
# DÜZELTME (Rev-134 devam, 2026-09-07): Gerçek çizimde doğrulanmış format
# boyutu HER ZAMAN PARANTEZ içinde taşır: "SZ12 (50/50)" — eski regex
# parantezsiz "SAYI/SAYI"yı da (örn. bir donatı ölçüsü ya da alakasız bir
# kesir) kolon sanıp binlerce ilgisiz objeyi (çizgi, donatı) kırmızıya
# boyayıp "başarısız" sayıyordu. Yeni regex SADECE parantez içindeki
# SAYI/SAYI'yı arıyor — parantez yoksa metin baştan "ilgisiz", hiç
# sınıflandırmaya girmiyor (bkz. kolon_yazisini_ayristir "ilgisiz" alanı).
_KOLON_YAZI_PATTERN = re.compile(
    r'([A-Za-zÇĞİÖŞÜçğıöşü][A-Za-zÇĞİÖŞÜçğıöşü0-9]*)?\s*\((\d+)\s*/\s*(\d+)\)'
)


def kolon_yazisini_ayristir(metin: str) -> Dict[str, Any]:
    """Tek bir TEXT/MTEXT içeriğini kolon boyut yazısı olarak ayrıştırır.

    Format: "<ad> (<en>/<boy>)" (örn. "SZ12 (50/50)", ad opsiyonel, boyut
    HER ZAMAN parantez içinde).

    Neyi çözüyoruz?
    Kolon geometrisi (1/50 ölçek + mm birim belirsizliği) güvenilir boyut
    vermiyor (bkz. CLAUDE.md Rev-133 debug kanıtı). Gerçek boyut çizim
    üzerindeki YAZIDA zaten var, ölçekten bağımsız. Bu fonksiyon o yazıyı
    okuyup en/boy (m) çıkarır ve GÜVENLİK KATMANI olarak ismin ilk harfine
    bakıp kolon (S/P) mu, kiriş (K) mi, tanımsız mı olduğuna karar verir —
    kullanıcı bir katın TÜM yazılarını (kolon+kiriş karışık) seçse bile
    kiriş yanlışlıkla kolon formülüyle hesaplanmasın diye. Parantez içinde
    SAYI/SAYI deseni hiç yoksa metin "ilgisiz" sayılır (çizgi, donatı
    etiketi vb.) — çağıran bunu SESSİZCE atlamalı, hiçbir listeye/hataya
    eklememeli.

    Nasıl test ederiz?
    "SZ12 (50/50)" -> basarili=True, ad="SZ12", tip="kolon", en_m=0.50, boy_m=0.50
    "KB110 (40/80)" -> basarili=True, tip="kiris" (çağıran hesaba katmaz)
    "(50/50)"      -> basarili=True, ad=None, tip="tanimsiz" (isim yok, kolon
                    mu kiriş mi belirsiz — otomatik hesaba KATILMAZ)
    "3Ø12" / "birsey" -> basarili=False, ilgisiz=True (parantez yok, sessizce atla)
    "P129 (0/180)" -> basarili=False, ilgisiz=False (parantez var ama geçersiz sayı)

    Args:
        metin: Ham TEXT/MTEXT içeriği (temizlenmemiş olabilir).

    Returns:
        dict: ham_metin, temiz_metin, basarili, ilgisiz (parantezli
              SAYI/SAYI deseni hiç yoksa True — çağıran sessizce atlamalı),
              ad, tip ("kolon"|"kiris"|"tanimsiz"|None), en_cm/boy_cm,
              en_m/boy_m, coklu_eslesme (aynı metinde birden fazla
              parantezli SAYI/SAYI deseni varsa True — ilk eşleşme
              kullanılır), hata (açıklama).
    """
    temiz = mtext_temizle(metin) if metin else ""

    sonuc: Dict[str, Any] = {
        "ham_metin": metin,
        "temiz_metin": temiz,
        "basarili": False,
        "ilgisiz": True,
        "ad": None,
        "tip": None,
        "en_cm": 0.0,
        "boy_cm": 0.0,
        "en_m": 0.0,
        "boy_m": 0.0,
        "coklu_eslesme": False,
        "hata": "",
    }

    if not temiz:
        sonuc["hata"] = "Boş metin"
        return sonuc

    eslesmeler = list(_KOLON_YAZI_PATTERN.finditer(temiz))
    if not eslesmeler:
        sonuc["hata"] = "Parantezli (SAYI/SAYI) deseni bulunamadı — ilgisiz metin"
        return sonuc

    # Parantez içinde SAYI/SAYI bulundu -> artık "ilgisiz" değil, gerçek bir
    # boyut adayı; geçersiz olsa bile (örn. 0/0) bu bir PARSE HATASI'dır,
    # sessizce atlanacak "ilgisiz" metin değildir.
    sonuc["ilgisiz"] = False

    ilk = eslesmeler[0]
    if len(eslesmeler) > 1:
        sonuc["coklu_eslesme"] = True

    try:
        en_cm = float(ilk.group(2))
        boy_cm = float(ilk.group(3))
    except (TypeError, ValueError):
        sonuc["hata"] = "en/boy sayıya çevrilemedi"
        return sonuc

    if en_cm <= 0 or boy_cm <= 0:
        sonuc["hata"] = f"Geçersiz boyut: {en_cm}/{boy_cm}"
        return sonuc

    ad_ham = ilk.group(1)
    ad = ad_ham.strip() if ad_ham else None
    ilk_harf = ad[0].upper() if ad else None

    if _TEMEL_KIRISI_PATTERN.search(temiz):
        # Rev-137: "SBH..." temel kirişidir (S ile başlasa da kolon DEĞİL) —
        # kendi aracına (temel_kirisi_ayristir) aittir, kolon hesabına girmez.
        tip = "temel_kirisi"
    elif ilk_harf in ("S", "P"):
        tip = "kolon"
    elif ilk_harf == "K":
        tip = "kiris"
    else:
        # ilk_harf None (isimsiz) VEYA S/P/K dışı bir harf -> tanımsız.
        # Güvenlik katmanı: ad yoksa kolon mu kiriş mi belirsizdir, bu
        # yüzden OTOMATİK HESABA KATILMAZ, kullanıcıya ayrı gösterilir.
        tip = "tanimsiz"

    sonuc.update({
        "basarili": True,
        "ad": ad,
        "tip": tip,
        "en_cm": en_cm,
        "boy_cm": boy_cm,
        "en_m": round(en_cm / 100.0, 4),
        "boy_m": round(boy_cm / 100.0, 4),
    })
    return sonuc


def kolon_yazilarini_toplu_ayristir(metinler: List[str]) -> Dict[str, Any]:
    """Birden fazla TEXT/MTEXT içeriğini toplu ayrıştırıp kolon/kiriş/
    tanımsız/başarısız olarak sınıflandırır. Parantezli (SAYI/SAYI) deseni
    hiç içermeyen ("ilgisiz") metinler SESSİZCE atlanır — hiçbir listeye
    eklenmez, sayılmaz (kullanıcı bir katı kutuyla seçtiğinde 1000+ çizgi/
    donatı objesi seçime girebilir, bunların ezici çoğunluğu bu gruptur).

    Neyi çözüyoruz?
    Kullanıcı AutoCAD'de bir katın TÜM kolon+kiriş yazılarını (S/P/K karışık)
    tek kutuyla seçebilir — bu fonksiyon K ile başlayanları otomatik ayıklar
    (kiriş formülüyle YANLIŞ hesaplanmasınlar diye), isimsiz/tanınmayan
    yazıları "tanımsız"a ayırır, geri kalanı (S/P) kolon olarak döner.

    Nasıl test ederiz?
    ["SZ12 (50/50)", "P129 (30/180)", "SZ07 (40/60)", "KB110 (40/80)",
     "birsey", "3Ø12"] ->
        kolonlar: 3 (SZ12, P129, SZ07), kirisler_atlanan: 1 (KB110),
        tanimsizlar: 0, basarisizlar: 0 (birsey/3Ø12 parantez içermediği
        için "ilgisiz" sayılıp hiçbir listeye girmeden atlandı)

    Args:
        metinler: Ham TEXT/MTEXT içerik listesi.

    Returns:
        dict: kolonlar, kirisler_atlanan, tanimsizlar, basarisizlar
              (her biri kolon_yazisini_ayristir() sözlük listesidir),
              ilgisiz_sayisi (sessizce atlanan, parantezsiz metin sayısı —
              sadece debug/bilgi amaçlı, kullanıcıya normalde gösterilmez)
              + ozet (kullanıcıya gösterilecek Türkçe özet cümlesi).
    """
    kolonlar: List[Dict[str, Any]] = []
    kirisler: List[Dict[str, Any]] = []
    tanimsizlar: List[Dict[str, Any]] = []
    basarisizlar: List[Dict[str, Any]] = []
    ilgisiz_sayisi = 0

    for metin in metinler:
        sonuc = kolon_yazisini_ayristir(metin)
        if not sonuc["basarili"]:
            if sonuc.get("ilgisiz"):
                ilgisiz_sayisi += 1
                continue
            basarisizlar.append(sonuc)
            continue

        if not sonuc["ad"]:
            # Sadece GÖRÜNTÜLEME etiketi — sınıflandırmayı (tip zaten
            # "tanimsiz") etkilemez, otomatik kolon saymaz.
            sonuc["ad"] = f"İsimsiz-{len(tanimsizlar) + 1}"

        if sonuc["tip"] == "kolon":
            sonuc["eleman_tipi"] = eleman_tipi_belirle(sonuc["en_cm"], sonuc["boy_cm"])  # Rev-160
            kolonlar.append(sonuc)
        elif sonuc["tip"] in ("kiris", "temel_kirisi"):
            kirisler.append(sonuc)
        else:
            tanimsizlar.append(sonuc)

    return {
        "kolonlar": kolonlar,
        "kirisler_atlanan": kirisler,
        "tanimsizlar": tanimsizlar,
        "basarisizlar": basarisizlar,
        "ilgisiz_sayisi": ilgisiz_sayisi,
        "ozet": _kolon_yazi_ozet_metni(kolonlar, kirisler, tanimsizlar, basarisizlar),
    }


# ── Kolon / Perde ayrımı + ortak ad havuzu (Rev-160) ─────────────────────────
# Kolon aplikasyon paftasında dikdörtgen perdeler de "S259 (210/30)" gibi
# yazılır; L/T/U perdelerde yalnız ad vardır ("S260"). TBDY 2018 perde
# tanımı: plandaki uzun kenar / kalınlık >= 6 (TS 500-2000'de 7 idi).
PERDE_KISA_UZUN_ORANI = 6.0
ELEMAN_TIPLERI = ("Kolon", "Perde")
ELEMAN_RENKLERI = {"Kolon": 3, "Perde": 4}   # ACI: yeşil / camgöbeği
OKUNAMAYAN_RENK = 1                          # ACI: kırmızı
# Boyutsuz eleman adı: "S260", "SZ07", "P12A" — tek kelime, S/P + harf* + rakam
_ELEMAN_ADI_PATTERN = re.compile(r'[SP][A-ZÇĞİÖŞÜ]{0,3}-?\d+[A-Z0-9]*')


def eleman_tipi_belirle(en_cm: float, boy_cm: float) -> str:
    """En/boydan Kolon / Perde: uzun/kısa >= 6 -> Perde (TBDY 2018).

    Neyi çözüyoruz? Kolon aracında perde yazıları kolonlarla aynı formatta.
    Nasıl test ederiz? (210,30)->Perde (oran 7), (180,30)->Perde (tam 6),
    (120,30)->Kolon (4), (50,50)->Kolon. Oran round(…, 9) ile — kayan nokta
    tam 6'yı 5.999… yapmasın (Rev-153 ceil dersi)."""
    kisa, uzun = sorted((float(en_cm), float(boy_cm)))
    if kisa <= 0:
        raise ValueError(f"Geçersiz boyut: {en_cm}/{boy_cm}")
    return "Perde" if round(uzun / kisa, 9) >= PERDE_KISA_UZUN_ORANI else "Kolon"


def eleman_ad_normalize(ad: Optional[str]) -> str:
    """Havuz karşılaştırması için: boşluksuz, büyük harf ("s259 " -> "S259")."""
    return re.sub(r'\s+', '', str(ad or '')).upper()


def eleman_ad_yazisi(metin: str) -> Optional[str]:
    """Boyutsuz S/P eleman adı yazısı mı? ("S260" -> "S260"; "6Ø16", "Etr. Ø10/20",
    "SBH-1", "S259 (210/30)" -> None). Tek kelime olmalı — donatı/açıklama
    yazıları eşleşmez."""
    temiz = mtext_temizle(metin) if metin else ""
    aday = eleman_ad_normalize(temiz)
    if not aday or ' ' in temiz.strip() or aday.startswith("SBH"):
        return None
    return aday if _ELEMAN_ADI_PATTERN.fullmatch(aday) else None


def eleman_adi_cikar(metin: str) -> Optional[str]:
    """Yazıdan eleman adı: "S259 (210/30)" -> "S259", "S260" -> "S260", diğer -> None.
    Perde aracı ad yazısını bununla seçer (kolon aracıyla aynı havuz anahtarı)."""
    a = kolon_yazisini_ayristir(metin)
    if a["basarili"] and a["tip"] == "kolon" and a["ad"]:
        return eleman_ad_normalize(a["ad"])
    return eleman_ad_yazisi(metin)


def kolon_perde_hesapla(en_cm: float, boy_cm: float, yukseklik_m: float, tip: Optional[str] = None,
                        doseme_kalinligi_m: float = 0.0, beton_esasi: str = "tam") -> Dict[str, Any]:
    """Yazıdan okunan eleman (kolon VEYA perde) beton + kalıp.

    Neyi çözüyoruz? Aynı perde kolon aracında ve Perde sekmesinde aynı sonucu
    vermeli (Rev-161 kullanıcı kararı):
    - Kolon: beton = en×boy×H, kalıp = 2(en+boy)×H — TAM KAT (Rev-135 kararı).
    - Perde: perde_hesapla ile — beton = en×boy×(tam kat / net, esasa göre),
      kalıp = 2(en+boy)×NET yükseklik (kat − döşeme). Yazıdan bitişik uç
      bilinemez -> uç düşümü yok (gerekirse Perde sekmesinden alınır).
    tip verilmezse orandan (>= 6 Perde) belirlenir.
    Nasıl test ederiz? (210,30,3.0,'Perde',0.20) -> beton 1.890, kalıp 4.8×2.8 =
    13.44; döşeme 0 -> 14.40; (50,50,3.0) -> Kolon 0.75 / 6.00 (döşemeden etkilenmez)."""
    tip = tip or eleman_tipi_belirle(en_cm, boy_cm)
    en_m, boy_m = float(en_cm) / 100.0, float(boy_cm) / 100.0
    h = float(yukseklik_m)
    if tip == "Perde":
        p = perde_hesapla(en_m * boy_m, 2 * (en_m + boy_m), h, doseme_kalinligi_m, beton_esasi, 0.0)
        return {"tip": tip, "beton_m3": round(p["beton_m3"], 4), "kalip_m2": round(p["kalip_m2"], 4),
                "net_yukseklik_m": p["net_yukseklik_m"], "hata": p["hata"]}
    return {"tip": tip, "beton_m3": round(en_m * boy_m * h, 4), "kalip_m2": round(2 * (en_m + boy_m) * h, 4),
            "net_yukseklik_m": h, "hata": ""}


def kolon_secimi_siniflandir(yazilar: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Kolon aracı kutu seçiminin yazılarını sınıflandırır (saf, COM'suz).

    Neyi çözüyoruz? Seçime kolon/perde yazıları, boyutsuz perde adları
    (L/T/U), kiriş yazıları ve donatı yazıları karışık girer. Boyutlu S/P ->
    elemanlar (tip oranla), boyutsuz S/P adı veya çözümlenemeyen boyut ->
    okunamayanlar (perde aracıyla alınacak, kırmızı), K/SBH -> atlanan,
    isimsiz -> tanımsız, geri kalan (donatı vb.) SESSİZCE yok sayılır.
    Nasıl test ederiz? scratchpad/test_kolon_perde_ayrim.py.

    Args:
        yazilar: [{metin, handle?, layer?}]
    Returns:
        dict: kolonlar (tip alanlı, Kolon+Perde), okunamayanlar [{ad, handle,
              ham_metin}], kirisler_atlanan, tanimsizlar, basarisizlar ([] —
              okunamayanlara katıldı), ilgisiz_sayisi, ozet.
    """
    elemanlar, okunamayanlar, kirisler, tanimsizlar = [], [], [], []
    ilgisiz = 0
    for y in yazilar:
        metin = y.get("metin") or ""
        a = kolon_yazisini_ayristir(metin)
        a["handle"] = y.get("handle")
        a["layer"] = y.get("layer", "")
        if a.get("ilgisiz"):
            ad = eleman_ad_yazisi(metin)
            if ad:
                okunamayanlar.append({"ad": ad, "handle": a["handle"], "ham_metin": metin})
            else:
                ilgisiz += 1   # donatı / açıklama — boyanmaz, listelenmez
            continue
        if not a["basarili"]:
            okunamayanlar.append({"ad": eleman_ad_normalize(a.get("ad")) or (mtext_temizle(metin) or metin),
                                  "handle": a["handle"], "ham_metin": metin})
            continue
        if not a["ad"]:
            a["ad"] = f"İsimsiz-{len(tanimsizlar) + 1}"
        if a["tip"] == "kolon":
            a["ad"] = eleman_ad_normalize(a["ad"])
            a["eleman_tipi"] = eleman_tipi_belirle(a["en_cm"], a["boy_cm"])
            elemanlar.append(a)
        elif a["tip"] in ("kiris", "temel_kirisi"):
            kirisler.append(a)
        else:
            tanimsizlar.append(a)
    return {
        "kolonlar": elemanlar, "okunamayanlar": okunamayanlar, "kirisler_atlanan": kirisler,
        "tanimsizlar": tanimsizlar, "basarisizlar": [], "ilgisiz_sayisi": ilgisiz,
        "ozet": _kolon_yazi_ozet_metni(elemanlar, kirisler, tanimsizlar, [], okunamayanlar),
    }


def _kolon_yazi_ozet_metni(
    kolonlar: List[Dict[str, Any]],
    kirisler: List[Dict[str, Any]],
    tanimsizlar: List[Dict[str, Any]],
    basarisizlar: List[Dict[str, Any]],
    okunamayanlar: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Kolon yazı sınıflandırma sonucundan kullanıcıya gösterilecek Türkçe
    özet cümlesini üretir. `kolon_yazilarini_toplu_ayristir()` (saf/test)
    ve `AutoCADConnector.get_kolon_beton_yazidan()` (COM, renklendirmeli)
    tarafından ortak kullanılır — tek kaynak, mesaj metni ikisinde de
    birbirinden sapmasın diye.
    """
    perde = sum(1 for k in kolonlar if k.get("eleman_tipi") == "Perde")
    parcalar = ([f"{len(kolonlar) - perde} kolon, {perde} perde bulundu"] if perde
                else [f"{len(kolonlar)} kolon bulundu"])
    if okunamayanlar:
        parcalar.append(f"{len(okunamayanlar)} eleman okunamadı (perde aracıyla alın)")
    if kirisler:
        parcalar.append(
            f"{len(kirisler)} kiriş yazısı atlandı (kiriş metrajı sonraki aşamada)"
        )
    if tanimsizlar:
        parcalar.append(f"{len(tanimsizlar)} tanımsız (kolon/kiriş belirsiz)")
    if basarisizlar:
        parcalar.append(f"{len(basarisizlar)} yazı ayrıştırılamadı")
    return ", ".join(parcalar) + "."


# ── Temel Kirişi (SBH) Beton + Kalıp — yazı tabanlı okuma (Rev-137) ─────────
# AŞAMA 1/2: SAF (self/COM bağımsız) regex + hesap çekirdeği.
# Format: "SBH-1 (20/165)" = ad + (genişlik_cm / yükseklik_cm). Uzunluk
# çizimde YOK, kullanıcı elle girer. Kalıp SADECE 2 yan yüz (alt yüz
# grobetona oturur, üst açık) — normal kirişten farkı bu.
# İsim ayrımı: "SBH" tam ön eki SADECE bu araca girer; kolon aracı
# (S/P) SBH'yi temel_kirisi olarak işaretleyip hesaba KATMAZ (bkz.
# kolon_yazisini_ayristir).
_TEMEL_KIRISI_PATTERN = re.compile(
    r'(?<![A-Za-z0-9ÇĞİÖŞÜçğıöşü])(SBH[-\w]*)\s*\(\s*(\d+(?:[.,]\d+)?)\s*/\s*'
    r'(\d+(?:[.,]\d+)?)\s*\)',
    re.IGNORECASE
)
# Elle girilen uzunluk bu değeri aşarsa büyük olasılıkla cm girilmiştir
# (Rev-134 1000-kat dersi) — engellenmez, sadece uyarılır.
TEMEL_KIRISI_UZUNLUK_UYARI_M = 50.0


def temel_kirisi_ayristir(metin: str) -> Dict[str, Any]:
    """Temel kirişi yazısını ("SBH-1 (20/165)") ayrıştırır.

    Neyi çözüyoruz?
    Temel kirişinin gerçek kesit boyutu çizimdeki etiket yazısında,
    ölçekten bağımsız olarak durur. Bu fonksiyon SADECE "SBH" ile başlayan
    etiketleri alır — kolon (SZ/SB/P) ve normal kiriş (K...) yazıları
    regex'e hiç uymaz, "ilgisiz" döner (çağıran sessizce atlar).

    Nasıl test ederiz?
    "SBH-1 (20/165)" -> basarili, ad="SBH-1", genislik_cm=20, yukseklik_cm=165
    "SZ07 (50/50)"   -> basarili=False, ilgisiz=True (kolon)
    "KB110 (25/60)"  -> basarili=False, ilgisiz=True (normal kiriş)
    "SBH-3 (0/150)"  -> basarili=False, ilgisiz=False (geçersiz boyut)
    "SBH-4 (180/20)" -> basarili=True ama uyari dolu (genişlik>yükseklik,
                        sıra ters girilmiş olabilir — kalıp 2×y×L yanlış çıkar)

    Returns:
        dict: ham_metin, temiz_metin, basarili, ilgisiz, ad, genislik_cm,
              yukseklik_cm, coklu_eslesme, uyari, hata.
    """
    temiz = mtext_temizle(metin) if metin else ""
    sonuc: Dict[str, Any] = {
        "ham_metin": metin,
        "temiz_metin": temiz,
        "basarili": False,
        "ilgisiz": True,
        "ad": None,
        "genislik_cm": 0.0,
        "yukseklik_cm": 0.0,
        "coklu_eslesme": False,
        "uyari": "",
        "hata": "",
    }
    if not temiz:
        sonuc["hata"] = "Boş metin"
        return sonuc

    eslesmeler = list(_TEMEL_KIRISI_PATTERN.finditer(temiz))
    if not eslesmeler:
        sonuc["hata"] = "SBH... (genişlik/yükseklik) deseni bulunamadı — ilgisiz metin"
        return sonuc

    sonuc["ilgisiz"] = False
    ilk = eslesmeler[0]
    sonuc["coklu_eslesme"] = len(eslesmeler) > 1
    try:
        genislik_cm = float(ilk.group(2).replace(",", "."))
        yukseklik_cm = float(ilk.group(3).replace(",", "."))
    except (TypeError, ValueError):
        sonuc["hata"] = "genişlik/yükseklik sayıya çevrilemedi"
        return sonuc

    if genislik_cm <= 0 or yukseklik_cm <= 0:
        sonuc["hata"] = f"Geçersiz boyut: {genislik_cm}/{yukseklik_cm}"
        return sonuc

    if genislik_cm > yukseklik_cm:
        sonuc["uyari"] = (
            f"Genişlik ({genislik_cm:g}) yükseklikten ({yukseklik_cm:g}) büyük — "
            f"format (genişlik/yükseklik) sırası ters olabilir, kontrol edin"
        )

    sonuc.update({
        "basarili": True,
        "ad": ilk.group(1).upper(),
        "genislik_cm": genislik_cm,
        "yukseklik_cm": yukseklik_cm,
    })
    return sonuc


def temel_kirisi_hesapla(genislik_cm: float, yukseklik_cm: float,
                         uzunluk_m: float, yan_uzunluklar_m: Optional[List[float]] = None) -> Dict[str, Any]:
    """Temel kirişi beton (m³) ve kalıp (m²) hesabı.

    Neyi çözüyoruz?
    Beton = g(m) × y(m) × L(m); Kalıp = 2 × y(m) × L(m) — sadece 2 yan yüz
    (alt yüz grobetona oturur, üst açık). CM->M dönüşümü TEK YERDE burada
    (Rev-134 1000-kat dersi).
    Rev-158: L = L_beton (kenar kapsamlarının ortalaması). yan_uzunluklar_m
    verilirse ([dolu1, dolu2] — bölünmüş kenarda parça toplamı) kalıp =
    y × (dolu1 + dolu2): kesişen kirişin girdiği boşlukta kalıp yok.

    Nasıl test ederiz?
    (20, 165, 5.0) -> beton_m3=1.65, kalip_m2=16.5
    uzunluk_m=500 -> hesaplanır ama uyari dolu (cm girilmiş olabilir)
    uzunluk_m<=0 veya boyut<=0 -> hata dolu, değerler 0

    Returns:
        dict: genislik_m, yukseklik_m, uzunluk_m, beton_m3, kalip_m2,
              uyari, hata.
    """
    sonuc: Dict[str, Any] = {
        "genislik_m": 0.0,
        "yukseklik_m": 0.0,
        "uzunluk_m": 0.0,
        "beton_m3": 0.0,
        "kalip_m2": 0.0,
        "uyari": "",
        "hata": "",
    }
    try:
        g_cm = float(genislik_cm)
        y_cm = float(yukseklik_cm)
        l_m = float(uzunluk_m)
    except (TypeError, ValueError):
        sonuc["hata"] = "Genişlik/yükseklik/uzunluk sayı değil"
        return sonuc

    if g_cm <= 0 or y_cm <= 0 or l_m <= 0:
        sonuc["hata"] = f"Geçersiz değer: g={g_cm} cm, y={y_cm} cm, L={l_m} m"
        return sonuc

    g_m = g_cm / 100.0
    y_m = y_cm / 100.0
    if yan_uzunluklar_m:
        try:
            yanlar = [float(x) for x in yan_uzunluklar_m]
        except (TypeError, ValueError):
            sonuc["hata"] = "Yan yüz uzunlukları sayı değil"
            return sonuc
        if len(yanlar) != 2 or any(x < 0 for x in yanlar):
            sonuc["hata"] = f"Yan yüz uzunlukları geçersiz: {yan_uzunluklar_m}"
            return sonuc
        kalip_uzunlugu = sum(yanlar)
    else:
        kalip_uzunlugu = 2.0 * l_m
    sonuc.update({
        "genislik_m": round(g_m, 4),
        "yukseklik_m": round(y_m, 4),
        "uzunluk_m": l_m,
        "beton_m3": round(g_m * y_m * l_m, 3),
        "kalip_m2": round(y_m * kalip_uzunlugu, 3),
    })
    if l_m > TEMEL_KIRISI_UZUNLUK_UYARI_M:
        sonuc["uyari"] = (
            f"Uzunluk {l_m:g} m — çok büyük, cm girilmiş olabilir (metre girin)"
        )
    return sonuc


# Rev-139: radye kalınlığı bu değeri aşarsa büyük olasılıkla cm girilmiştir
# (radye pratikte 0.30-2.50 m).
RADYE_KALINLIK_UYARI_M = 3.0


def radye_hesapla(alan_m2: float, kalinlik_m: float, dis_cevre_m: float,
                  ic_bosluk_cevreleri_m: Optional[List[float]] = None) -> Dict[str, Any]:
    """Radye temel beton (m³) ve kalıp (m²) hesabı — tüm girdiler METRE.

    Neyi çözüyoruz?
    Beton = alan × kalınlık (alan kullanıcının AutoCAD AREA ile ölçtüğü NET
    alan). Kalıp = (dış çevre + Σ iç boşluk çevreleri) × kalınlık — iç
    boşluğun (asansör/merdiven) yan yüzü de kalıplanır, EKLENİR. Kalınlık
    tek girdi, beton ve kalıp aynı değeri kullanır.

    Nasıl test ederiz?
    (450, 0.60, 90) -> beton 270, kalıp 54
    (450, 0.60, 90, [12, 8]) -> toplam çevre 110, kalıp 66
    kalınlık 60 -> hesaplanır ama uyari dolu (cm girilmiş olabilir)
    alan/kalınlık <= 0 -> hata, değerler 0

    Returns:
        dict: alan_m2, kalinlik_m, dis_cevre_m, ic_cevre_m, toplam_cevre_m,
              beton_m3, kalip_m2, uyari, hata.
    """
    sonuc: Dict[str, Any] = {
        "alan_m2": 0.0, "kalinlik_m": 0.0, "dis_cevre_m": 0.0,
        "ic_cevre_m": 0.0, "toplam_cevre_m": 0.0,
        "beton_m3": 0.0, "kalip_m2": 0.0, "uyari": "", "hata": "",
    }
    try:
        alan = float(alan_m2)
        kal = float(kalinlik_m)
        dis = float(dis_cevre_m or 0.0)
        ic_liste = [float(c) for c in (ic_bosluk_cevreleri_m or [])]
    except (TypeError, ValueError):
        sonuc["hata"] = "Alan/kalınlık/çevre sayı değil"
        return sonuc

    if alan <= 0 or kal <= 0:
        sonuc["hata"] = f"Alan ve kalınlık sıfırdan büyük olmalı (alan={alan}, kalınlık={kal})"
        return sonuc
    if dis < 0 or any(c < 0 for c in ic_liste):
        sonuc["hata"] = "Çevre negatif olamaz"
        return sonuc

    ic = sum(ic_liste)
    toplam = dis + ic
    sonuc.update({
        "alan_m2": alan,
        "kalinlik_m": kal,
        "dis_cevre_m": round(dis, 3),
        "ic_cevre_m": round(ic, 3),
        "toplam_cevre_m": round(toplam, 3),
        "beton_m3": round(alan * kal, 3),
        "kalip_m2": round(toplam * kal, 3),
    })
    uyarilar = []
    if kal > RADYE_KALINLIK_UYARI_M:
        uyarilar.append(f"Kalınlık {kal:g} m — çok büyük, cm girilmiş olabilir (metre girin)")
    if dis == 0:
        uyarilar.append("Dış çevre girilmedi — kalıp eksik hesaplanır")
    sonuc["uyari"] = "; ".join(uyarilar)
    return sonuc


# ── Rev-148: AutoCAD kalıcı ayarları (OSMODE orijinali vb.) ──
def _autocad_ayar_dosyasi():
    from pathlib import Path
    kok = os.environ.get("QUANTIX_DATA_DIR") or str(Path(__file__).resolve().parents[2] / "data")
    return Path(kok) / "autocad_ayarlari.json"


def autocad_ayari_oku(anahtar: str, varsayilan=None):
    """Ayar dosyasından değer okur; dosya yok/bozuksa varsayılan."""
    import json
    try:
        with open(_autocad_ayar_dosyasi(), encoding="utf-8") as f:
            return json.load(f).get(anahtar, varsayilan)
    except Exception:
        return varsayilan


def autocad_ayari_yaz(anahtar: str, deger) -> None:
    import json
    yol = _autocad_ayar_dosyasi()
    try:
        veri = {}
        if yol.exists():
            with open(yol, encoding="utf-8") as f:
                veri = json.load(f)
        veri[anahtar] = deger
        yol.parent.mkdir(parents=True, exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"AutoCAD ayarı yazılamadı ({anahtar}): {e}", exc_info=True)


def osmode_orijinal_belirle(okunan: int, kayitli, program_degeri: int = 33) -> int:
    """Oturumun OSMODE orijinali (saf kural, Rev-148).

    Neyi çözüyoruz? Önceki oturum OSMODE'u geri yükleyemeden kapandıysa
    AutoCAD'de programın değeri (33) kalır; bunu "orijinal" sanıp sonsuza
    dek 33'e geri yüklemek kullanıcının kendi ayarını kaybettirir.
    Nasıl test ederiz? (4133, None)->4133; (33, 4133)->4133; (33, None)->33;
    (33, 33)->33; (511, 4133)->511 (kullanıcı değiştirmiş, okunan esas).
    """
    try:
        kayitli = int(kayitli) if kayitli is not None else None
    except (TypeError, ValueError):
        kayitli = None
    if int(okunan) == program_degeri and kayitli is not None and kayitli != program_degeri:
        return kayitli
    return int(okunan)


# ══ Rev-143: PERDE (L/T/U kesit) BETON + KALIP ══
# Aşama 1: hesap, Aşama 2: alan AutoCAD'den (birim + ölçek + teyit),
# Aşama 3: tek seçimde poligon + düşülen uç çizgileri, ayrık yükseklik esası.

# Kat yüksekliği bu değeri aşarsa büyük olasılıkla cm girilmiştir.
PERDE_YUKSEKLIK_UYARI_M = 8.0
# Eşdeğer kalınlık t ≈ 2·Alan/Çevre (ince duvar: t×L dikdörtgende ≈ t).
# Perde pratikte 0.15-0.60 m — çok dışı birim/ölçek hatası veya yanlış seçim.
PERDE_ESDEGER_KALINLIK_MIN_M = 0.10
PERDE_ESDEGER_KALINLIK_MAX_M = 0.80
BETON_ESASLARI = {"tam": "Tam kat", "net": "Net (kat − döşeme)"}


@dataclass
class KatYukseklikAyari:
    """Katın yükseklik esası — perde (ve ileride döşeme) araçlarının ORTAK ayarı.

    Neyi çözüyoruz?
    Perde betonu tam kat yüksekliğiyle alınırsa döşeme kalınlığındaki beton
    hem perdede hem döşemede sayılır; net alınırsa sayılmaz. Hangi esasın
    seçildiği bu nesnede durur — döşeme aracı `beton_esasi`'nı okuyup
    çakışan bölgeyi düşüp düşmeyeceğine karar verir. Kalıp HER ZAMAN net
    yükseklikle hesaplanır (döşeme bölgesini döşeme kalıbı kapatır).

    Nasıl test ederiz? (3.0, 0.2, "tam") -> beton_yuk 3.0, net 2.8;
    (3.0, 0.2, "net") -> beton_yuk 2.8; döşeme >= kat -> dogrula() hata.
    """
    kat_yuksekligi_m: float = 0.0
    doseme_kalinligi_m: float = 0.0
    beton_esasi: str = "tam"

    @property
    def net_yukseklik_m(self) -> float:
        return round(float(self.kat_yuksekligi_m) - float(self.doseme_kalinligi_m), 4)

    @property
    def beton_yuksekligi_m(self) -> float:
        return float(self.kat_yuksekligi_m) if self.beton_esasi == "tam" else self.net_yukseklik_m

    def dogrula(self) -> str:
        """Boş string = geçerli; aksi halde hata metni."""
        try:
            kat = float(self.kat_yuksekligi_m)
            dos = float(self.doseme_kalinligi_m)
        except (TypeError, ValueError):
            return "Kat yüksekliği / döşeme kalınlığı sayı değil"
        if self.beton_esasi not in BETON_ESASLARI:
            return f"Bilinmeyen beton esası: {self.beton_esasi}"
        if kat <= 0:
            return "Kat yüksekliği sıfırdan büyük olmalı"
        if dos < 0:
            return "Döşeme kalınlığı negatif olamaz"
        if dos >= kat:
            return f"Döşeme kalınlığı ({dos:g} m) kat yüksekliğinden ({kat:g} m) küçük olmalı"
        return ""

    def esas_etiketi(self) -> str:
        """Tablo/rapor başlığı: hangi esasla hesaplandığı açıkça yazılır."""
        return (f"Beton: {BETON_ESASLARI.get(self.beton_esasi, '?')} "
                f"({self.beton_yuksekligi_m:.2f} m)  |  Kalıp: net "
                f"({self.net_yukseklik_m:.2f} m = {float(self.kat_yuksekligi_m):.2f} − "
                f"{float(self.doseme_kalinligi_m):.2f})")


def perde_hesapla(alan_m2: float, cevre_m: float, yukseklik_m: float,
                  doseme_kalinligi_m: float = 0.0, beton_esasi: str = "tam",
                  dusulen_m: float = 0.0) -> Dict[str, Any]:
    """Perde beton (m³) ve kalıp (m²) — tüm girdiler METRE.

    Neyi çözüyoruz?
    Beton = kesit alanı × beton yüksekliği (esas: tam kat / net).
    Kalıp = (çevre − düşülen uçlar) × NET yükseklik (kat − döşeme) — kolona /
    başka perdeye bitişen yüzde kalıp kurulmaz, döşeme bölgesini döşeme
    kalıbı kapatır. `yukseklik_m` KAT yüksekliğidir; döşeme 0 iken eski
    (Aşama 1) davranışla birebir aynıdır.
    Eşdeğer kalınlık (2A/Ç, TAM çevre) alan-çevre tutarlılığını denetler.

    Nasıl test ederiz? scratchpad/test_perde_yukseklik.py (programsız):
    (8.5, 12, 3.0) -> 25.5 / 36; çevre 12, düşüm 1, kat 3.0, döşeme 0.2 ->
    kalıp 11×2.8 = 30.8; esas "tam" -> beton alan×3.0, "net" -> alan×2.8;
    düşüm >= çevre -> hata; döşeme >= kat -> hata.

    Returns:
        dict: alan_m2, cevre_m, dusulen_m, kalip_cevre_m, yukseklik_m,
              net_yukseklik_m, beton_yuksekligi_m, beton_esasi,
              esdeger_kalinlik_m, beton_m3, kalip_m2, uyari, hata.
    """
    sonuc: Dict[str, Any] = {
        "alan_m2": 0.0, "cevre_m": 0.0, "dusulen_m": 0.0, "kalip_cevre_m": 0.0,
        "yukseklik_m": 0.0, "net_yukseklik_m": 0.0, "beton_yuksekligi_m": 0.0,
        "beton_esasi": beton_esasi, "esdeger_kalinlik_m": 0.0,
        "beton_m3": 0.0, "kalip_m2": 0.0, "uyari": "", "hata": "",
    }
    try:
        alan = float(alan_m2)
        cevre = float(cevre_m or 0.0)
        dusulen = float(dusulen_m or 0.0)
        ayar = KatYukseklikAyari(float(yukseklik_m), float(doseme_kalinligi_m or 0.0), beton_esasi)
    except (TypeError, ValueError):
        sonuc["hata"] = "Alan/çevre/yükseklik sayı değil"
        return sonuc

    if alan <= 0 or ayar.kat_yuksekligi_m <= 0:
        sonuc["hata"] = f"Alan ve yükseklik sıfırdan büyük olmalı (alan={alan}, yükseklik={ayar.kat_yuksekligi_m})"
        return sonuc
    ayar_hata = ayar.dogrula()
    if ayar_hata:
        sonuc["hata"] = ayar_hata
        return sonuc
    if cevre < 0 or dusulen < 0:
        sonuc["hata"] = "Çevre / düşülen uzunluk negatif olamaz"
        return sonuc
    if dusulen > 0 and dusulen >= cevre:
        sonuc["hata"] = f"Düşülen uçlar ({dusulen:g} m) çevreden ({cevre:g} m) küçük olmalı"
        return sonuc

    t = 2.0 * alan / cevre if cevre > 0 else 0.0
    kalip_cevre = cevre - dusulen
    sonuc.update({
        "alan_m2": alan,
        "cevre_m": round(cevre, 3),
        "dusulen_m": round(dusulen, 3),
        "kalip_cevre_m": round(kalip_cevre, 3),
        "yukseklik_m": ayar.kat_yuksekligi_m,
        "net_yukseklik_m": ayar.net_yukseklik_m,
        "beton_yuksekligi_m": ayar.beton_yuksekligi_m,
        "esdeger_kalinlik_m": round(t, 3),
        "beton_m3": round(alan * ayar.beton_yuksekligi_m, 3),
        "kalip_m2": round(kalip_cevre * ayar.net_yukseklik_m, 3),
    })
    uyarilar = []
    if ayar.kat_yuksekligi_m > PERDE_YUKSEKLIK_UYARI_M:
        uyarilar.append(f"Yükseklik {ayar.kat_yuksekligi_m:g} m — çok büyük, cm girilmiş olabilir (metre girin)")
    if cevre == 0:
        uyarilar.append("Çevre girilmedi — kalıp hesaplanmadı")
    elif t > PERDE_ESDEGER_KALINLIK_MAX_M:
        uyarilar.append(
            f"Alan/çevre tutarsız: eşdeğer kalınlık {t:.2f} m (perde 0.15-0.60 m olur) — "
            "çevrede eksik kenar veya alanda birim hatası olabilir"
        )
    elif t < PERDE_ESDEGER_KALINLIK_MIN_M:
        uyarilar.append(
            f"Alan/çevre tutarsız: eşdeğer kalınlık {t:.3f} m — alan çok küçük "
            "(ölçek/birim hatası, ör. 1/50 çizim) veya çevre fazla seçilmiş olabilir"
        )
    sonuc["uyari"] = "; ".join(uyarilar)
    return sonuc


# Rev-137 Aşama 3: kenar çizgisinden otomatik uzunluk. entity.Length ÇİZİM
# BİRİMİNDE gelir (mm/cm/m) — Rev-133 dersi: ölçek/birim kod tarafından
# kesin bilinemez, bu yüzden birim kullanıcı tarafından seçilir (varsayılan
# INSUNITS'ten okunur) ve oturumdaki ilk çizgi kullanıcıya teyit ettirilir.
CIZIM_BIRIM_CARPANI = {"mm": 0.001, "cm": 0.01, "m": 1.0}
INSUNITS_BIRIM = {4: "mm", 5: "cm", 6: "m"}


def cizim_uzunlugu_metreye_cevir(deger: float, birim: str) -> float:
    """Çizim biriminde okunan uzunluğu metreye çevirir.

    Neyi çözüyoruz? LINE.Length çizim biriminde gelir; mm çizimde 5000,
    cm çizimde 500 → ikisi de 5.0 m olmalı (Rev-134 1000-kat dersi).
    Nasıl test ederiz? (5000,"mm")->5.0, (500,"cm")->5.0, (5,"m")->5.0,
    bilinmeyen birim -> ValueError.
    """
    if birim not in CIZIM_BIRIM_CARPANI:
        raise ValueError(f"Bilinmeyen çizim birimi: {birim}")
    return round(float(deger) * CIZIM_BIRIM_CARPANI[birim], 4)


# ── Perde seçimi (Aşama 2/3) ──
# Alan ÇİZİM BİRİMİ² cinsinden gelir, ölçekli çizimde ölçek² kadar küçüktür
# (Rev-133: 1/50 çizimde 2500 kat). Birim + ölçek kullanıcıdan, ilk okuma teyitli.
PERDE_POLYLINE_TIPLERI = {"AcDbPolyline", "AcDb2dPolyline"}
PERDE_CIZGI_TIPLERI = {"AcDbLine"} | PERDE_POLYLINE_TIPLERI
PERDE_TARAMA_TIPI = "AcDbHatch"
PERDE_YAZI_TIPLERI = {"AcDbText", "AcDbMText"}
# Tek perde kesiti bu aralığın dışındaysa birim/ölçek şüphesi — teyit zorunlu
PERDE_ALAN_MIN_M2 = 0.05
PERDE_ALAN_MAX_M2 = 100.0
# Tarama ile sınır polyline'ı aynı alanı gösterir — bu oranda yakınsa tek sayılır
PERDE_ALAN_ESIT_TOLERANS = 0.005
# Düşülen uç çizgisinin uçları/ortası poligon çevresine bu GERÇEK mesafeden yakın olmalı
PERDE_UC_TOLERANS_M = 0.02


def cizim_alani_m2ye_cevir(alan: float, birim: str, olcek: float = 1.0) -> float:
    """Çizim birimi² alanı gerçek m²'ye çevirir: alan × (birim_çarpanı × ölçek)².

    Neyi çözüyoruz? Alan uzunluğun KARESİYLE ölçeklenir — cm çizimde ÷10.000,
    1/50 ölçekli mm çizimde × (0.001×50)². Dönüşüm TEK YERDE.
    Nasıl test ederiz? (42500,"cm")->4.25, (4.25e6,"mm")->4.25,
    (1700,"mm",50)->4.25, bilinmeyen birim / ölçek<=0 -> ValueError.
    """
    if birim not in CIZIM_BIRIM_CARPANI:
        raise ValueError(f"Bilinmeyen çizim birimi: {birim}")
    olcek = float(olcek)
    if olcek <= 0:
        raise ValueError(f"Ölçek sıfırdan büyük olmalı: {olcek}")
    return round(float(alan) * (CIZIM_BIRIM_CARPANI[birim] * olcek) ** 2, 6)


def _nokta_poligon_cevre_uzakligi(p, koseler) -> float:
    """Noktanın kapalı poligonun (köşe listesi) kenarlarına en kısa uzaklığı."""
    n = len(koseler)
    return min(_nokta_dogru_parcasi_uzakligi(p, koseler[i], koseler[(i + 1) % n])
               for i in range(n))


def perde_ad_yazisi_sec(yazilar: List[Dict[str, Any]], uyarilar: List[str]) -> Tuple[str, Optional[str]]:
    """Perde seçimindeki yazılardan perde adı + yazının handle'ı (Rev-160).

    Tek yazı -> o (S/P adıysa "S260" gibi normalize, değilse metnin kendisi).
    Birden çok yazı -> içlerinden TEK S/P eleman adı varsa o (donatı yazısı
    da seçime girmiş olabilir); yoksa ad boş + uyarı. Ad, kolon aracıyla
    ortak havuzun anahtarıdır — eleman_adi_cikar ile aynı normalizasyon."""
    if len(yazilar) == 1:
        metin = yazilar[0].get("metin") or ""
        return (eleman_adi_cikar(metin) or mtext_temizle(metin).strip()[:40]), yazilar[0].get("handle")
    adaylar = [(eleman_adi_cikar(y.get("metin") or ""), y.get("handle")) for y in yazilar]
    adaylar = [a for a in adaylar if a[0]]
    if len(adaylar) == 1:
        return adaylar[0]
    if yazilar:
        uyarilar.append(f"{len(yazilar)} yazı seçildi — perde adı otomatik verildi")
    return "", None


def perde_secimi_degerlendir(objeler: List[Dict[str, Any]], birim: str,
                             olcek: float = 1.0) -> Dict[str, Any]:
    """TEK perdenin seçimini değerlendirir (saf, COM'suz).

    Neyi çözüyoruz?
    Kullanıcı tek seçimde perde kesit poligonunu + (isteğe bağlı) kolona /
    başka perdeye bitişen uç çizgilerini + (isteğe bağlı) perde adı yazısını
    seçer. Kurallar:
    - TAM OLARAK BİR kapalı polyline (kesit) olmalı; açık polyline kesit
      sayılmaz (reddedilir), birden fazla kapalı poligon -> hata.
    - Tarama, sınır poligonuyla aynı alandaysa yok sayılır (çift sayım
      önlemi); farklı alanlıysa ikinci bir kapalı alan -> hata.
    - Diğer çizgiler (LINE / açık polyline) düşülecek uç adayıdır: iki ucu
      VE orta noktası poligon çevresi üzerinde (tolerans içinde) olmalı,
      değilse düşülmez + uyarı (güvenli taraf: fazla kalıp).
    - Toplam düşüm çevreye eşit/büyükse -> hata.
    - Tek yazı varsa perde adı olur.

    Nasıl test ederiz? scratchpad/test_perde_secim.py.

    Args:
        objeler: connector.perde_oku() çıktısı — her biri {handle, obje_tipi,
            alan_birim, kapali, uzunluk_birim, koseler [(x,y)...], metin, hata}.
    Returns:
        dict: poligon_handle, ad, alan_m2, cevre_m, dusulen_m,
              dusulen_handleler, kullanilan_handleler, atlananlar
              [(handle, neden)], uyari, hata.
    """
    sonuc: Dict[str, Any] = {
        "poligon_handle": None, "ad": "", "alan_m2": 0.0, "cevre_m": 0.0,
        "dusulen_m": 0.0, "dusulen_handleler": [], "kullanilan_handleler": [],
        "atlananlar": [], "uyari": "", "hata": "",
    }
    if birim not in CIZIM_BIRIM_CARPANI:
        sonuc["hata"] = f"Bilinmeyen çizim birimi: {birim}"
        return sonuc
    try:
        olcek = float(olcek)
        if olcek <= 0:
            raise ValueError
    except (TypeError, ValueError):
        sonuc["hata"] = f"Geçersiz ölçek: {olcek}"
        return sonuc
    uzunluk_carpani = CIZIM_BIRIM_CARPANI[birim] * olcek

    kapali, acik_polyler, cizgiler, taramalar, yazilar = [], [], [], [], []
    for o in objeler:
        tip = o.get("obje_tipi")
        if o.get("hata") and tip in PERDE_CIZGI_TIPLERI | {PERDE_TARAMA_TIPI}:
            sonuc["atlananlar"].append((o.get("handle"), o["hata"]))
            continue
        if tip in PERDE_POLYLINE_TIPLERI:
            (kapali if o.get("kapali") else acik_polyler).append(o)
        elif tip == "AcDbLine":
            cizgiler.append(o)
        elif tip == PERDE_TARAMA_TIPI:
            taramalar.append(o)
        elif tip in PERDE_YAZI_TIPLERI and (o.get("metin") or "").strip():
            yazilar.append(o)

    if not kapali:
        if acik_polyler or cizgiler:
            # Rev-155: kapalı polyline yok -> patlatılmış kontur (ideCAD) — parçaları zincirle
            return perde_zincir_degerlendir(objeler, birim, olcek)
        if taramalar:
            sonuc["hata"] = "Sadece tarama seçildi — kesitin kapalı sınır çizgisini (polyline) de seçin"
        else:
            sonuc["hata"] = "Kapalı perde kesiti (kapalı polyline) seçilmedi"
        return sonuc
    if len(kapali) > 1:
        sonuc["hata"] = (f"Tek seçimde {len(kapali)} kapalı poligon var — her seferinde TEK perde seçin")
        return sonuc
    poligon = kapali[0]
    alan_birim = float(poligon.get("alan_birim") or 0.0)
    if alan_birim <= 0:
        sonuc["hata"] = "Perde kesitinin alanı okunamadı (0)"
        return sonuc
    for t in taramalar:
        ta = float(t.get("alan_birim") or 0.0)
        if abs(ta - alan_birim) <= PERDE_ALAN_ESIT_TOLERANS * max(ta, alan_birim):
            sonuc["atlananlar"].append((t.get("handle"), "tarama, kesitle aynı alan (bir kez sayıldı)"))
        else:
            sonuc["hata"] = "Seçimde kesitten farklı alanlı bir tarama var — her seferinde TEK perde seçin"
            return sonuc

    alan_m2 = round(cizim_alani_m2ye_cevir(alan_birim, birim, olcek), 4)
    cevre_m = round(float(poligon.get("uzunluk_birim") or 0.0) * uzunluk_carpani, 3)
    if cevre_m <= 0:
        sonuc["hata"] = "Perde kesitinin çevresi okunamadı (0)"
        return sonuc

    # Düşülecek uç çizgileri: iki uç + orta nokta poligon çevresinde olmalı
    koseler = poligon.get("koseler") or []
    tol_birim = PERDE_UC_TOLERANS_M / uzunluk_carpani
    uyarilar = []
    dusulen_birim = 0.0
    for c in cizgiler + acik_polyler:
        if c.get("gecici"):
            continue  # blok içi çizgi uç sayılmaz — uç yalnız kullanıcının seçtiği gerçek çizgi
        k = c.get("koseler") or []
        uz = float(c.get("uzunluk_birim") or 0.0)
        if len(k) < 2 or uz <= 0 or len(koseler) < 3:
            sonuc["atlananlar"].append((c.get("handle"), "uç çizgisi okunamadı — düşülmedi"))
            uyarilar.append("okunamayan çizgi düşülmedi")
            continue
        orta = ((k[0][0] + k[-1][0]) / 2.0, (k[0][1] + k[-1][1]) / 2.0)
        if len(k) > 2:
            orta = k[len(k) // 2]
        if all(_nokta_poligon_cevre_uzakligi(p, koseler) <= tol_birim for p in (k[0], k[-1], orta)):
            dusulen_birim += uz
            sonuc["dusulen_handleler"].append(c.get("handle"))
        else:
            m = round(uz * uzunluk_carpani, 2)
            sonuc["atlananlar"].append((c.get("handle"), f"{m:g} m çizgi perde çevresi üzerinde değil — düşülmedi"))
            uyarilar.append(f"{m:g} m'lik çizgi çevre üzerinde değil, düşülmedi")
    dusulen_m = round(dusulen_birim * uzunluk_carpani, 3)
    if dusulen_m >= cevre_m:
        sonuc["hata"] = f"Düşülen uçlar ({dusulen_m:g} m) çevreyi ({cevre_m:g} m) geçemez"
        return sonuc

    sonuc["ad"], ad_handle = perde_ad_yazisi_sec(yazilar, uyarilar)

    if alan_m2 < PERDE_ALAN_MIN_M2:
        uyarilar.append(f"Alan {alan_m2:g} m² — çok küçük, birim/ölçek hatası olabilir")
    elif alan_m2 > PERDE_ALAN_MAX_M2:
        uyarilar.append(f"Alan {alan_m2:g} m² — tek perde için çok büyük, birim hatası olabilir")

    sonuc.update({
        "poligon_handle": poligon.get("handle"),
        "alan_m2": alan_m2,
        "cevre_m": cevre_m,
        "dusulen_m": dusulen_m,
        "kullanilan_handleler": [h for h in [poligon.get("handle")] + sonuc["dusulen_handleler"]
                                 + [ad_handle] if h],
        "uyari": "; ".join(uyarilar),
    })
    return _perde_blok_handle_esle(sonuc, objeler)


def _perde_blok_handle_esle(sonuc: Dict[str, Any], objeler: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rev-155: blok içeriğinden (geçici patlatılmış nesneler) gelen sonuçta anahtar ve
    boyama ORİJİNAL blok referansının handle'ı olur; geçici handle'lar (silinecek)
    kullanılanlardan çıkarılır."""
    gecici = {o.get("handle"): o.get("blok_handle") for o in objeler if o.get("gecici")}
    if not gecici or sonuc.get("hata"):
        return sonuc
    blok = gecici.get(sonuc.get("poligon_handle")) or sonuc.get("blok_handle")
    if blok:
        sonuc["poligon_handle"] = blok
        sonuc["blok_handle"] = blok
    kullanilan = [h for h in sonuc.get("kullanilan_handleler") or [] if h not in gecici]
    if blok and blok not in kullanilan:
        kullanilan.insert(0, blok)
    sonuc["kullanilan_handleler"] = kullanilan
    return sonuc


def perde_alan_supheli_mi(alan_m2: float) -> bool:
    """Teyit zorunluluğu: tek perde kesiti için olağan dışı alan."""
    return not (PERDE_ALAN_MIN_M2 <= float(alan_m2) <= PERDE_ALAN_MAX_M2)


# ── Rev-155: Perde KONTUR ZİNCİRLEME (ideCAD patlatılmış perde / blok içeriği) ──
# ideCAD perdesi patlatılınca her kenar ayrı AÇIK polyline/LINE olur (35+100+100+35).
# Kapalı polyline yoksa parçalar uç noktalarından zincirlenip kapalı kontur kurulur.
PERDE_ZINCIR_TOLERANS_M = 0.005     # uç eşleştirme toleransı (gerçek 5 mm)
PERDE_EGRI_TIPLERI = {"AcDbArc", "AcDbCircle", "AcDbEllipse", "AcDbSpline"}


def _shoelace(koseler) -> float:
    n = len(koseler)
    return abs(sum(koseler[i][0] * koseler[(i + 1) % n][1] - koseler[(i + 1) % n][0] * koseler[i][1]
                   for i in range(n))) / 2.0


def _parca_uzunlugu(koseler) -> float:
    return sum(math.dist(koseler[i], koseler[i + 1]) for i in range(len(koseler) - 1))


def kontur_zincirle(parcalar: List[Dict[str, Any]], tol_birim: float) -> Dict[str, Any]:
    """Açık parçaları (LINE / açık polyline) uç noktalarından TEK kapalı kontura zincirler (saf).

    Neyi çözüyoruz? Patlatılmış perdede kenarlar ayrı nesne. Uçları tolerans içinde
    çakışan parçalar düğümlerde birleşir; her düğümde tam 2 uç olmalı (1 = boşluk,
    3+ = dallanma), tek çevrim olmalı (2+ çevrim = seçimde birden fazla perde).
    Üst üste kopya parçalar (aynı köşeler, ters yön dahil) bir kez sayılır.

    Nasıl test ederiz? scratchpad/test_perde_zincir.py — 4 parça dikdörtgen, 6 parça L,
    boşluk, 2 dikdörtgen, dallanma, kopya.

    Args:
        parcalar: [{handle, koseler [(x,y)...]}] (en az 2 köşe).
        tol_birim: uç eşleştirme toleransı (çizim birimi).
    Returns:
        dict: koseler (sıralı kapalı poligon), alan_birim, cevre_birim,
              parca_uzunluklari {handle: uzunluk_birim}, tekrar_edenler [handle], hata.
    """
    sonuc: Dict[str, Any] = {"koseler": [], "alan_birim": 0.0, "cevre_birim": 0.0,
                             "parca_uzunluklari": {}, "tekrar_edenler": [], "hata": ""}
    temiz, anahtarlar = [], set()
    for p in parcalar:
        k = [(float(x), float(y)) for x, y in (p.get("koseler") or [])]
        if len(k) < 2 or _parca_uzunlugu(k) <= tol_birim:
            continue
        yuvarla = tuple((round(x / max(tol_birim, 1e-9)), round(y / max(tol_birim, 1e-9))) for x, y in k)
        anahtar = min(yuvarla, tuple(reversed(yuvarla)))
        if anahtar in anahtarlar:
            sonuc["tekrar_edenler"].append(p.get("handle"))
            continue
        anahtarlar.add(anahtar)
        temiz.append({"handle": p.get("handle"), "koseler": k})
    if not temiz:
        sonuc["hata"] = "Kontur kurulacak çizgi yok"
        return sonuc

    # Uçları düğümlere topla
    dugumler: List[List[float]] = []            # [x, y]
    baglar: List[List[Tuple[int, int]]] = []    # düğüm -> [(parça, uç 0/1)]

    def _dugum(p):
        for i, d in enumerate(dugumler):
            if math.dist(p, d) <= tol_birim:
                return i
        dugumler.append([p[0], p[1]])
        baglar.append([])
        return len(dugumler) - 1

    uc_dugum = []
    for i, p in enumerate(temiz):
        a, b = _dugum(p["koseler"][0]), _dugum(p["koseler"][-1])
        uc_dugum.append((a, b))
        baglar[a].append((i, 0))
        baglar[b].append((i, 1))

    def _nokta(i):
        return f"({dugumler[i][0]:.2f}, {dugumler[i][1]:.2f})"

    dal = [i for i, b in enumerate(baglar) if len(b) >= 3]
    if dal:
        sonuc["hata"] = (f"kontur dallanıyor: {_nokta(dal[0])} noktasında {len(baglar[dal[0]])} kenar "
                         "birleşiyor — perde dışı çizgi ya da iç çizgi seçilmiş olabilir")
        return sonuc
    bos = [i for i, b in enumerate(baglar) if len(b) == 1]
    if bos:
        if len(temiz) == 1:
            sonuc["hata"] = (f"Perde kesiti KAPALI DEĞİL — kontur kapanmıyor: {_nokta(bos[0])} noktasında "
                             "boşluk (AutoCAD'de PEDIT > Kapat ile kapatın ya da eksik kenarı da seçin)")
        else:
            diger = [dugumler[i] for i in bos[1:]]
            ek = (f" (en yakın açık uç {min(math.dist(dugumler[bos[0]], d) for d in diger):.3g} birim uzakta)"
                  if diger else "")
            sonuc["hata"] = f"kontur kapanmıyor: {_nokta(bos[0])} noktasında boşluk{ek}"
        return sonuc

    # Çevrim sayısı (bileşen)
    ziyaret = [False] * len(temiz)
    cevrimler = 0
    for bas in range(len(temiz)):
        if ziyaret[bas]:
            continue
        cevrimler += 1
        yigin = [bas]
        while yigin:
            i = yigin.pop()
            if ziyaret[i]:
                continue
            ziyaret[i] = True
            for d in uc_dugum[i]:
                yigin.extend(j for j, _ in baglar[d] if not ziyaret[j])
    if cevrimler > 1:
        sonuc["hata"] = f"seçimde {cevrimler} perde var, tek tek seçin"
        return sonuc

    # Tek çevrimi dolaş: her parçayı yönüne göre ekle (son köşe bir sonrakinin ilkidir)
    koseler: List[Tuple[float, float]] = []
    parca, uc = 0, 0                    # 0. parçanın başlangıç ucundan gir
    for _ in range(len(temiz)):
        k = temiz[parca]["koseler"]
        yol = k if uc == 0 else list(reversed(k))
        koseler.extend(yol[:-1])
        cikis = uc_dugum[parca][1 - uc]
        parca, uc = next((j, u) for j, u in baglar[cikis] if j != parca or len(temiz) == 1)
    uzunluklar = {p["handle"]: _parca_uzunlugu(p["koseler"]) for p in temiz}
    sonuc.update({"koseler": koseler, "alan_birim": _shoelace(koseler),
                  "cevre_birim": sum(uzunluklar.values()), "parca_uzunluklari": uzunluklar})
    return sonuc


def perde_zincir_degerlendir(objeler: List[Dict[str, Any]], birim: str, olcek: float = 1.0) -> Dict[str, Any]:
    """Kapalı polyline YOKSA: açık polyline + LINE parçalarını zincirleyip perde kesiti kurar.

    Neyi çözüyoruz? ideCAD'de patlatılmış perde (her kenar ayrı nesne) veya blok içeriği.
    Uç düşümü bu aşamada YAPILMAZ — kenarlar konturun parçası olduğu için kullanıcıya
    ikinci istemle sorulur (perde_zincir_uc_dus). Yay (bulge / ARC) desteklenmez: açık
    mesajla reddedilir. Blok içeriğinde (blok_handle) anahtar + boyama blok referansıdır.

    Nasıl test ederiz? scratchpad/test_perde_zincir.py.
    Returns: perde_secimi_degerlendir ile aynı alanlar + zincir=True, zincir_parcalari
             {handle: uzunluk_birim}, uzunluk_carpani, blok_handle.
    """
    sonuc: Dict[str, Any] = {
        "poligon_handle": None, "ad": "", "alan_m2": 0.0, "cevre_m": 0.0,
        "dusulen_m": 0.0, "dusulen_handleler": [], "kullanilan_handleler": [],
        "atlananlar": [], "uyari": "", "hata": "", "zincir": True,
        "zincir_parcalari": {}, "uzunluk_carpani": 1.0, "blok_handle": None,
    }
    if birim not in CIZIM_BIRIM_CARPANI:
        sonuc["hata"] = f"Bilinmeyen çizim birimi: {birim}"
        return sonuc
    carpan = CIZIM_BIRIM_CARPANI[birim] * float(olcek)
    sonuc["uzunluk_carpani"] = carpan
    parcalar, yazilar, egriler = [], [], []
    for o in objeler:
        tip = o.get("obje_tipi")
        if tip in PERDE_EGRI_TIPLERI:
            egriler.append(o)
        elif tip in PERDE_CIZGI_TIPLERI:
            if o.get("hata"):
                sonuc["atlananlar"].append((o.get("handle"), o["hata"]))
                continue
            if o.get("bulge_var"):
                sonuc["hata"] = ("Perde konturunda yay (bulge) içeren kenar var — yaylı kontur desteklenmiyor. "
                                 "Kapalı polyline çizip onu seçin (alan/çevre AutoCAD'den okunur)")
                return sonuc
            parcalar.append(o)
        elif tip in PERDE_YAZI_TIPLERI and (o.get("metin") or "").strip():
            yazilar.append(o)
    if not parcalar:
        sonuc["hata"] = "Kapalı perde kesiti (kapalı polyline) ya da kontur çizgileri seçilmedi"
        return sonuc
    k = kontur_zincirle(parcalar, PERDE_ZINCIR_TOLERANS_M / carpan)
    if k["hata"]:
        ek = " (seçimde yay/eğri var — yaylı kontur desteklenmiyor)" if egriler else ""
        sonuc["hata"] = k["hata"] + ek
        return sonuc
    if egriler:
        sonuc["hata"] = "Perde konturunda yay/eğri (ARC) var — yaylı kontur desteklenmiyor"
        return sonuc

    bloklar = {o.get("blok_handle") for o in parcalar}
    blok = next(iter(bloklar)) if len(bloklar) == 1 else None
    if len(bloklar) > 1:
        sonuc["hata"] = ("seçimde birden fazla perde var (blok + ayrı çizgiler ya da 2+ blok), tek tek seçin"
                         if None in bloklar else f"seçimde {len(bloklar)} perde bloğu var, tek tek seçin")
        return sonuc
    sonuc["blok_handle"] = blok
    uyarilar = []
    if k["tekrar_edenler"]:
        uyarilar.append(f"{len(k['tekrar_edenler'])} üst üste kopya kenar bir kez sayıldı")
    alan_m2 = round(cizim_alani_m2ye_cevir(k["alan_birim"], birim, olcek), 4)
    cevre_m = round(k["cevre_birim"] * carpan, 3)
    sonuc["ad"], ad_handle = perde_ad_yazisi_sec(yazilar, uyarilar)
    if alan_m2 < PERDE_ALAN_MIN_M2:
        uyarilar.append(f"Alan {alan_m2:g} m² — çok küçük, birim/ölçek hatası olabilir")
    elif alan_m2 > PERDE_ALAN_MAX_M2:
        uyarilar.append(f"Alan {alan_m2:g} m² — tek perde için çok büyük, birim hatası olabilir")
    parca_handleler = list(k["parca_uzunluklari"])
    # Mükerrer anahtarı: blok referansı ya da parça handle'larının sıralı birleşimi
    anahtar = blok or "ZINCIR:" + "+".join(sorted(str(h) for h in parca_handleler))
    kullanilan = parca_handleler + ([ad_handle] if ad_handle else [])
    sonuc.update({
        "poligon_handle": anahtar, "alan_m2": alan_m2, "cevre_m": cevre_m,
        "zincir_parcalari": k["parca_uzunluklari"],
        "kullanilan_handleler": [h for h in kullanilan if h],
        "uyari": "; ".join(uyarilar),
    })
    return _perde_blok_handle_esle(sonuc, objeler)


def perde_zincir_uc_dus(sonuc: Dict[str, Any], uc_handleler: List[Any]) -> Dict[str, Any]:
    """Zincir modunda ikinci istemde seçilen uç kenarlarını çevreden düşer (saf).

    Seçilen kenar konturun PARÇASI olmalı — değilse düşülmez + uyarı (güvenli taraf:
    fazla kalıp). Aynı kenar iki kez seçilse bir kez düşülür. Toplam düşüm çevreye
    eşit/büyükse hata. Blok içeriğinde geçici (patlatılmış) handle'lar boyanmaz.
    """
    d = dict(sonuc)
    d["dusulen_handleler"] = []
    d["atlananlar"] = list(sonuc.get("atlananlar") or [])
    parcalar = sonuc.get("zincir_parcalari") or {}
    carpan = float(sonuc.get("uzunluk_carpani") or 1.0)
    uyarilar = [u for u in (sonuc.get("uyari") or "").split("; ") if u]
    dusulen_birim = 0.0
    disarida = 0
    for h in dict.fromkeys(uc_handleler or []):
        if h in parcalar:
            dusulen_birim += parcalar[h]
            d["dusulen_handleler"].append(h)
        else:
            disarida += 1
            d["atlananlar"].append((h, "konturun parçası değil — düşülmedi"))
    if disarida:
        uyarilar.append(f"{disarida} seçilen nesne konturun parçası değil, düşülmedi")
    dusulen_m = round(dusulen_birim * carpan, 3)
    if dusulen_m >= float(sonuc.get("cevre_m") or 0):
        d["hata"] = f"Düşülen uçlar ({dusulen_m:g} m) çevreyi ({sonuc.get('cevre_m'):g} m) geçemez"
        return d
    d["dusulen_m"] = dusulen_m
    d["uyari"] = "; ".join(uyarilar)
    return d


# ══ Rev-144: DÖŞEME (PLAK) BETON + KALIP ══
# Kalınlık bu aralığın dışındaysa büyük olasılıkla birim hatası (m / mm girilmiş)
DOSEME_KALINLIK_MIN_CM = 5.0
DOSEME_KALINLIK_MAX_CM = 50.0


def hakim_doseme_kalinligi_cm(kayitlar: List[Dict[str, Any]]) -> Optional[float]:
    """Katın döşeme kayıtlarından HAKİM kalınlık (cm) — Rev-163.

    Neyi çözüyoruz? Perde kalıbı net yükseklikle (kat − döşeme) alınır; döşeme
    kalınlığı elle girilmezse 0 kalıyor ve kalıp fazla çıkıyordu. Kalınlık
    Döşeme sekmesinden otomatik alınır: kalınlık başına brüt alan toplanır,
    EN BÜYÜK alanlı kalınlık seçilir (perdelerin çoğu ana döşemeye bağlanır).
    Eşit alanda İNCE olan seçilir (daha az düşüm = güvenli taraf, fazla kalıp).
    Döşeme yoksa None (çağıran varsayılan kalınlığa düşer).
    Nasıl test ederiz? [15cm 120m², 12cm 30m²] -> 15; [15cm 50, 20cm 50] -> 15; [] -> None;
    kalınlığı 0/geçersiz kayıt yok sayılır."""
    alanlar: Dict[float, float] = {}
    for s in kayitlar or []:
        if (s or {}).get("tip") == "Saçak":
            continue   # Rev-164: saçak kat döşemesi değil (perde ana döşemeye bağlanır)
        try:
            t = float(s.get("kalinlik_cm") or 0.0)
            a = float(s.get("brut_alan_m2") or 0.0)
        except (TypeError, ValueError):
            continue
        if t > 0:
            alanlar[t] = alanlar.get(t, 0.0) + max(a, 0.0)
    if not alanlar:
        return None
    return max(alanlar.items(), key=lambda kv: (kv[1], -kv[0]))[0]


def doseme_hesapla(brut_alan_m2: float, kalinlik_cm: float, bosluk_alan_m2: float = 0.0,
                   bosluk_cevre_m: float = 0.0, serbest_kenar_m: float = 0.0) -> Dict[str, Any]:
    """Plak döşeme beton (m³) ve kalıp (m²) — alanlar m², uzunluklar m, kalınlık CM.

    Neyi çözüyoruz?
    Net alan = brüt − boşluk; beton = net × h; alt kalıp = net; kenar
    kalıbı = (serbest kenar + boşluk çevreleri) × h. Alan kiriş İÇ
    YÜZLERİ arasında ölçülür (kiriş betonu tam yükseklikle sayıldığı için
    akstan ölçmek kesişimi iki kez sayar). cm -> m dönüşümü TEK YERDE.

    Nasıl test ederiz? scratchpad/test_doseme_hesap.py (programsız):
    T1 (20, 15) -> beton 3.00, kalıp 20.00; T2 serbest kenar 5 -> kenar 0.75;
    T3 (30, 15, 5, 9) -> net 25, beton 3.75, kenar 1.35, toplam 26.35;
    T4 boşluk >= brüt -> hata; T5 h=0 -> hata; h=0.15 -> uyarı (m girilmiş).

    Returns:
        dict: brut_alan_m2, bosluk_alan_m2, net_alan_m2, kalinlik_cm,
              bosluk_cevre_m, serbest_kenar_m, beton_m3, alt_kalip_m2,
              kenar_kalip_m2, toplam_kalip_m2, uyari, hata.
    """
    sonuc: Dict[str, Any] = {
        "brut_alan_m2": 0.0, "bosluk_alan_m2": 0.0, "net_alan_m2": 0.0, "kalinlik_cm": 0.0,
        "bosluk_cevre_m": 0.0, "serbest_kenar_m": 0.0, "beton_m3": 0.0, "alt_kalip_m2": 0.0,
        "kenar_kalip_m2": 0.0, "toplam_kalip_m2": 0.0, "uyari": "", "hata": "",
    }
    try:
        brut = float(brut_alan_m2)
        h_cm = float(kalinlik_cm)
        bosluk = float(bosluk_alan_m2 or 0.0)
        bosluk_cevre = float(bosluk_cevre_m or 0.0)
        serbest = float(serbest_kenar_m or 0.0)
    except (TypeError, ValueError):
        sonuc["hata"] = "Alan / kalınlık / uzunluk sayı değil"
        return sonuc

    if brut <= 0:
        sonuc["hata"] = "Brüt alan sıfırdan büyük olmalı"
        return sonuc
    if h_cm <= 0:
        sonuc["hata"] = "Kalınlık sıfırdan büyük olmalı"
        return sonuc
    if bosluk < 0 or bosluk_cevre < 0 or serbest < 0:
        sonuc["hata"] = "Boşluk alanı / boşluk çevresi / serbest kenar negatif olamaz"
        return sonuc
    if bosluk >= brut:
        sonuc["hata"] = f"Boşluk alanı ({bosluk:g} m²) brüt alandan ({brut:g} m²) küçük olmalı"
        return sonuc

    h_m = h_cm / 100.0
    net = brut - bosluk
    kenar = (serbest + bosluk_cevre) * h_m
    sonuc.update({
        "brut_alan_m2": round(brut, 4),
        "bosluk_alan_m2": round(bosluk, 4),
        "net_alan_m2": round(net, 4),
        "kalinlik_cm": h_cm,
        "bosluk_cevre_m": round(bosluk_cevre, 3),
        "serbest_kenar_m": round(serbest, 3),
        "beton_m3": round(net * h_m, 3),
        "alt_kalip_m2": round(net, 3),
        "kenar_kalip_m2": round(kenar, 3),
        "toplam_kalip_m2": round(net + kenar, 3),
    })
    if not (DOSEME_KALINLIK_MIN_CM <= h_cm <= DOSEME_KALINLIK_MAX_CM):
        sonuc["uyari"] = (f"Kalınlık {h_cm:g} cm — olağan dışı (5-50 cm). "
                          "cm girdiğinizden emin misiniz?")
    return sonuc


# ══ Rev-150: KİRİŞ (normal, döşeme altı) BETON + KALIP ══
KIRIS_TIP_IC = "İç"
KIRIS_TIP_KENAR = "Kenar"
KIRIS_TIPLERI = (KIRIS_TIP_IC, KIRIS_TIP_KENAR)
KIRIS_UZUNLUK_SUPHE_M = 15.0


def kiris_hesapla(b_cm: float, h_cm: float, l_net_m: float, tip: str = KIRIS_TIP_IC,
                  t_cm: float = 0.0, l2_m: Optional[float] = None,
                  d1_m: Optional[float] = None, d2_m: Optional[float] = None) -> Dict[str, Any]:
    """Kiriş beton (m³) ve kalıp (m²) — b, h, t CM; kenar uzunlukları METRE.

    Rev-158: l_net_m / l2_m kenarların KAPSAMI (boşluk dahil); d1_m / d2_m
    aynı sırayla o kenarların DOLU uzunluğu (bölünmüş kenarda parça toplamı).
    Yan kalıp dolu uzunlukla, beton/alt kalıp kapsamla. d verilmezse = kapsam.

    Neyi çözüyoruz?
    İki kenar ayrı: L1 (kısa) / L2 (uzun) — yamuk/köşe kirişte farklı, düz
    kirişte eşit (l2_m verilmezse L2 = L1, elle giriş). L_ort = (L1+L2)/2.
    Beton = b × h × L_ort (h TAM — döşeme alanı kiriş iç yüzlerinden).
    Alt kalıp = b × L_ort. Yan: iç = (h−t)·L1 + (h−t)·L2; kenar =
    (h−t)·L1 + h·L2 (UZUN kenar dış yüz kabul). t = 0 → döşemesiz.
    cm -> m dönüşümü TEK YERDE.

    Nasıl test ederiz? scratchpad/test_kiris_hesap.py (programsız):
    25/50 L=4 t=12 İç -> 0.500 / 4.04; Kenar -> 4.52; t=0 -> 5.00;
    25/12 -> hata; 60/30 L=3 -> 2.88 + bilgi; U2 1/1.5 İç -> 0.156 / 1.2625;
    U3 Kenar -> 1.4425.

    Returns:
        dict: b_cm, h_cm, l1_m, l2_m, l_net_m (= L_ort), tip, t_cm,
              beton_m3, alt_kalip_m2, yan_kalip_m2, toplam_kalip_m2,
              uyari, bilgi, hata.
    """
    sonuc: Dict[str, Any] = {
        "b_cm": 0.0, "h_cm": 0.0, "l1_m": 0.0, "l2_m": 0.0, "d1_m": 0.0, "d2_m": 0.0,
        "l_net_m": 0.0, "tip": tip, "t_cm": 0.0,
        "beton_m3": 0.0, "alt_kalip_m2": 0.0, "yan_kalip_m2": 0.0, "toplam_kalip_m2": 0.0,
        "uyari": "", "bilgi": "", "hata": "",
    }
    try:
        b = float(b_cm)
        h = float(h_cm)
        l_a = float(l_net_m)
        l_b = l_a if l2_m is None else float(l2_m)
        d_a = l_a if d1_m is None else float(d1_m)
        d_b = l_b if d2_m is None else float(d2_m)
        t = float(t_cm or 0.0)
    except (TypeError, ValueError):
        sonuc["hata"] = "Kesit / uzunluk / döşeme kalınlığı sayı değil"
        return sonuc
    if tip not in KIRIS_TIPLERI:
        sonuc["hata"] = f"Geçersiz kiriş tipi: {tip!r} (İç / Kenar)"
        return sonuc
    # Kısa/uzun sıralaması kapsama göre; dolu uzunluk kendi kenarını izler
    (l1, d1), (l2, d2) = sorted([(l_a, d_a), (l_b, d_b)])
    if d1 < 0 or d2 < 0 or d1 > l1 + 1e-6 or d2 > l2 + 1e-6:
        sonuc["hata"] = "Dolu kenar uzunluğu negatif ya da kapsamdan büyük olamaz"
        return sonuc
    l_m = (l1 + l2) / 2.0
    if b <= 0 or h <= 0 or l1 <= 0:
        sonuc["hata"] = "Genişlik (b), yükseklik (h) ve uzunluk (L) sıfırdan büyük olmalı"
        return sonuc
    if t < 0:
        sonuc["hata"] = "Döşeme kalınlığı (t) negatif olamaz"
        return sonuc
    if h <= t:
        sonuc["hata"] = (f"Kiriş yüksekliği ({h:g} cm) döşeme kalınlığından ({t:g} cm) "
                         "büyük olmalı")
        return sonuc

    b_m, h_m, t_m = b / 100.0, h / 100.0, t / 100.0
    alt = b_m * l_m
    yan = (h_m - t_m) * d1 + ((h_m - t_m) if tip == KIRIS_TIP_IC else h_m) * d2
    sonuc.update({
        "b_cm": b, "h_cm": h, "l1_m": round(l1, 4), "l2_m": round(l2, 4),
        "d1_m": round(d1, 4), "d2_m": round(d2, 4),
        "l_net_m": round(l_m, 4), "t_cm": t,
        "beton_m3": round(b_m * h_m * l_m, 4),
        "alt_kalip_m2": round(alt, 4),
        "yan_kalip_m2": round(yan, 4),
        "toplam_kalip_m2": round(alt + yan, 4),
    })
    if b > h:
        sonuc["bilgi"] = f"Yassı kiriş (b={b:g} > h={h:g} cm) — kesit yönünü kontrol edin."
    if l2 > KIRIS_UZUNLUK_SUPHE_M:
        sonuc["uyari"] = f"L = {l2:g} m — 15 m üstü. Uzunluk metre cinsinden mi?"
    return sonuc


# ── Rev-150 Aşama 2: kiriş seçimi (yazı + kenar çizgileri) — saf karar katmanı ──
# İsim ayrımı YOK (kamu projelerinde K/KB/KK... karışık): kesit, yazıdaki İLK
# "sayı/sayı" kalıbından. Kolon/SBH regex'lerinden bağımsız — tek seçimli
# modda gevşek desen güvenli (kutu seçimi değil, gürültü yok).
_KIRIS_KESIT_PATTERN = re.compile(r'\(?\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*\)?')
KIRIS_RENKLERI = {KIRIS_TIP_IC: AcadColor.ORANGE, KIRIS_TIP_KENAR: AcadColor.BLUE}
# Aynı kenarın parçaları: doğrultu farkı ≤ 2° ve dik mesafe ≤ 2 cm (GERÇEK,
# çizim birimine çevrilir). İki kenar arası açı > 15° -> uç/kolon çizgisi şüphesi.
KIRIS_KENAR_ACI_TOL_DER = 2.0
KIRIS_KENAR_MESAFE_TOL_M = 0.02
KIRIS_KENAR_PARALEL_MAX_DER = 15.0


def _dogru_birim(c: Dict[str, Any]):
    """Çizginin (bas, birim yön) çifti; koordinat yoksa / sıfır boyluysa None."""
    if not c.get("bas") or not c.get("son"):
        return None
    dx, dy = c["son"][0] - c["bas"][0], c["son"][1] - c["bas"][1]
    u = math.hypot(dx, dy)
    return (c["bas"], (dx / u, dy / u)) if u > 0 else None


def kiris_kenarlara_ayir(cizgiler: List[Dict[str, Any]], mesafe_tol_birim: float) -> Dict[str, Any]:
    """Kenar çizgilerini İKİ kenara ayırır (aynı doğrultudaki parçalar aynı kenar).

    Neyi çözüyoruz? Yamuk/köşe kirişte iki kenar farklı uzunlukta; bölünmüş
    kenar birden fazla parçadır. Parçalar: doğrultu farkı ≤ 2° VE bir
    parçanın orta noktası diğerinin doğrusuna ≤ tolerans -> aynı kenar.
    Tam 2 kenar çıkmalı; iki kenar birbirine > 15° açılıysa (kolon yüzü /
    uç çizgisi seçilmiş) reddedilir. Koordinat okunamazsa sadece 2 çizgide
    her çizgi bir kenar kabul edilir.

    Nasıl test ederiz? scratchpad/test_kiris_secim.py — düz, yamuk,
    bölünmüş kenar, 3 kenar, dik uç çizgisi senaryoları.

    Returns:
        dict: kenarlar ([[çizgi,...], [çizgi,...]]), hata.
    """
    bilgiler = [_dogru_birim(c) for c in cizgiler]
    if any(b is None for b in bilgiler):
        if len(cizgiler) == 2:
            return {"kenarlar": [[cizgiler[0]], [cizgiler[1]]], "hata": ""}
        return {"kenarlar": [], "hata": "Çizgi koordinatları okunamadı — kenarlara ayrılamadı "
                                        "(her kenar için tek çizgi seçin)"}
    cos_tol = math.cos(math.radians(KIRIS_KENAR_ACI_TOL_DER))
    kumeler: List[List[int]] = []
    for i, (bas, yon) in enumerate(bilgiler):
        orta = ((cizgiler[i]["bas"][0] + cizgiler[i]["son"][0]) / 2.0,
                (cizgiler[i]["bas"][1] + cizgiler[i]["son"][1]) / 2.0)
        for kume in kumeler:
            r_bas, r_yon = bilgiler[kume[0]]
            paralel = abs(yon[0] * r_yon[0] + yon[1] * r_yon[1]) >= cos_tol
            dik = abs(r_yon[0] * (orta[1] - r_bas[1]) - r_yon[1] * (orta[0] - r_bas[0]))
            if paralel and dik <= mesafe_tol_birim:
                kume.append(i)
                break
        else:
            kumeler.append([i])
    if len(kumeler) != 2:
        return {"kenarlar": [], "hata": (
            f"Çizgiler {len(kumeler)} ayrı kenara düştü — iki kenara ayrılamadı "
            "(sadece kirişin iki uzun kenarını seçin, kolon/uç çizgisi seçmeyin)")}
    y1, y2 = bilgiler[kumeler[0][0]][1], bilgiler[kumeler[1][0]][1]
    if abs(y1[0] * y2[0] + y1[1] * y2[1]) < math.cos(math.radians(KIRIS_KENAR_PARALEL_MAX_DER)):
        return {"kenarlar": [], "hata": ("İki kenar birbirine paralel değil — kolon yüzü / uç "
                                         "çizgisi seçilmiş olabilir")}
    return {"kenarlar": [[cizgiler[i] for i in k] for k in kumeler], "hata": ""}


def _kenar_kapsam_dolu(kenar: List[Dict[str, Any]], carpan: float) -> Dict[str, Any]:
    """Tek kenarın ölçüsü (metre): dolu = parça uzunlukları toplamı; kapsam =
    kenarın ilk ve son noktası arası (aradaki boşluklar DAHİL), uç noktalar
    kenar doğrultusuna izdüşürülerek. Koordinat yoksa kapsam = dolu."""
    dolu = sum(float(c["uzunluk_birim"]) for c in kenar) * carpan
    bilgi = _dogru_birim(kenar[0])
    if bilgi is None or any(not c.get("bas") or not c.get("son") for c in kenar):
        kapsam = dolu
    else:
        (bx, by), (ux, uy) = bilgi
        ts = [(p[0] - bx) * ux + (p[1] - by) * uy for c in kenar for p in (c["bas"], c["son"])]
        kapsam = (max(ts) - min(ts)) * carpan
    return {"kapsam_m": round(kapsam, 4), "dolu_m": round(dolu, 4), "parca": len(kenar),
            "handleler": [c.get("handle") for c in kenar]}


def kiris_kenarlari_olc(cizgiler: List[Dict[str, Any]], carpan: float) -> Dict[str, Any]:
    """SBH ve K araçlarının ORTAK kenar ölçümü (Rev-158).

    Neyi çözüyoruz? Kesişen kirişte kenar parçalara bölünür; kullanıcı bir
    kenarın tüm parçalarını seçer. Çizgiler tekilleştirilir (üst üste çift),
    iki kenara ayrılır (kiris_kenarlara_ayir: aynı doğrultu + aynı hat), her
    kenar için KAPSAM (ilk-son nokta, boşluk dahil) ve DOLU (parça toplamı)
    hesaplanır. Beton / alt kalıp: L_beton = (kapsam1 + kapsam2) / 2; yan
    kalıp her yüz kendi dolu uzunluğuyla (boşlukta kesişen kiriş var, kalıp yok).

    Nasıl test ederiz? scratchpad/test_kiris_kenar_olcum.py — üst 12.45 tek,
    alt 7.75 + 3.80 (0.90 boşluk) -> L_beton 12.45, alt dolu 11.55.

    Args:
        cizgiler: [{handle, uzunluk_birim, bas, son, hata}] (çizim birimi)
        carpan: çizim birimi -> metre (ölçek dahil)

    Returns:
        dict: hata, notlar, kenarlar ([kısa kapsam, uzun kapsam] — her biri
              kapsam_m/dolu_m/parca/handleler), l_beton_m, handleler (tüm parçalar).
    """
    s: Dict[str, Any] = {"hata": "", "notlar": [], "kenarlar": [], "l_beton_m": 0.0, "handleler": []}
    tekil, gorulen = [], set()
    for c in cizgiler:
        if c.get("hata") or float(c.get("uzunluk_birim") or 0) <= 0:
            s["notlar"].append(f"çizgi {c.get('handle')} uzunluğu okunamadı")
            continue
        k = _cizgi_anahtari(c)
        if k is not None and k in gorulen:
            s["notlar"].append(f"üst üste çift çizgi ({c.get('handle')}) tekilleştirildi")
            continue
        if k is not None:
            gorulen.add(k)
        tekil.append(c)
    if len(tekil) < 2:
        s["hata"] = f"{len(tekil)} kenar çizgisi okundu — en az 2 (iki kenar) gerekli"
        return s
    ayrim = kiris_kenarlara_ayir(tekil, KIRIS_KENAR_MESAFE_TOL_M / carpan)
    if ayrim["hata"]:
        s["hata"] = ayrim["hata"]
        return s
    kenarlar = sorted((_kenar_kapsam_dolu(k, carpan) for k in ayrim["kenarlar"]),
                      key=lambda x: (x["kapsam_m"], x["dolu_m"]))
    for k in kenarlar:
        if k["dolu_m"] < k["kapsam_m"] - 0.005:
            s["notlar"].append(f"bölünmüş kenar: {k['parca']} parça, kapsam {k['kapsam_m']:.2f} m, "
                               f"dolu {k['dolu_m']:.2f} m")
    s.update(kenarlar=kenarlar, handleler=[c.get("handle") for c in tekil],
             l_beton_m=round((kenarlar[0]["kapsam_m"] + kenarlar[1]["kapsam_m"]) / 2.0, 4))
    return s


def kenar_eksik_secim_uyarisi(kapsam1_m: float, kapsam2_m: float, b_cm: float) -> str:
    """|kapsam1 − kapsam2| > 2 × b ise eksik parça şüphesi (köşe kirişinde fark en
    fazla ~2b olur: her uçta bir kiriş genişliği). Boş metin = sorun yok."""
    fark = abs(float(kapsam1_m) - float(kapsam2_m))
    if b_cm and fark > 2.0 * float(b_cm) / 100.0 + 1e-9:
        return (f"kenar kapsamları {kapsam1_m:.2f} / {kapsam2_m:.2f} m (fark {fark:.2f} m > 2×b = "
                f"{2 * float(b_cm) / 100:.2f} m) — bir kenarın parçası seçilmemiş olabilir")
    return ""


def kiris_yazisi_ayristir(metin: str) -> Dict[str, Any]:
    """Kiriş etiketini ayrıştırır: "K101 (25/50)" -> ad K101, b 25, h 50.

    Neyi çözüyoruz? Parantezli/parantezsiz/boşluklu tüm yazımlar
    ("K 101(25/50)", "K101 25/50"). Ad = kesitten önceki metin (olduğu gibi,
    boşluklar tekleştirilir). "sayı/sayı" yoksa kesitli=False: yazı yine
    ad olarak kullanılabilir, b/h elle sorulur (yedek yol).

    Nasıl test ederiz? scratchpad/test_kiris_secim.py.

    Returns:
        dict: ham_metin, ad, kesitli, b_cm, h_cm, hata.
    """
    temiz = " ".join((mtext_temizle(metin) if metin else "").split())
    sonuc: Dict[str, Any] = {"ham_metin": metin, "ad": temiz, "kesitli": False,
                             "b_cm": 0.0, "h_cm": 0.0, "hata": ""}
    if not temiz:
        sonuc["hata"] = "Boş yazı"
        return sonuc
    m = _KIRIS_KESIT_PATTERN.search(temiz)
    if not m:
        return sonuc
    b = float(m.group(1).replace(",", "."))
    h = float(m.group(2).replace(",", "."))
    sonuc["ad"] = temiz[:m.start()].strip(" -:(") or temiz
    if b <= 0 or h <= 0:
        sonuc["hata"] = f"Geçersiz kesit {b:g}/{h:g}"
        return sonuc
    sonuc.update(kesitli=True, b_cm=b, h_cm=h)
    return sonuc


def kiris_secim_degerlendir(okuma: Dict[str, Any], birim: str, olcek: float = 1.0) -> Dict[str, Any]:
    """TEK kirişin seçimini (yazı + kenar çizgileri) değerlendirir — COM'suz.

    Neyi çözüyoruz?
      - Tam 1 uygun yazı: 1 kesitli yazı (diğer kesitsiz yazılar yok sayılır)
        ya da hiç kesitli yoksa tam 1 kesitsiz yazı (kesit_elle=True). 0 ya
        da >1 kesitli -> hata.
      - Uzunluk: çizgiler (üst üste çiftler tekilleştirilir) İKİ kenara
        ayrılır (kiris_kenarlara_ayir), her kenarın parçaları toplanır:
        L1 = kısa, L2 = uzun. Soru SORULMAZ (yamuk kirişte fark normaldir).
      - Birim: cizim_uzunlugu_metreye_cevir × ölçek (yeni dönüşüm yok).

    Nasıl test ederiz? scratchpad/test_kiris_secim.py — 400/404 cm -> L1 4.00
    L2 4.04; bölünmüş 200+200 / 400 -> 4.00/4.00; tek çizgi / iki kesitli
    yazı / üç kenar -> hata.

    Returns:
        dict: gecerli, hata, ad, b_cm, h_cm, kesit_elle, yazi_handle,
              cizgi_handleler, l1_m, l2_m, l_net_m (ortalama), notlar (list).
    """
    s: Dict[str, Any] = {
        "gecerli": False, "hata": "", "ad": "", "b_cm": 0.0, "h_cm": 0.0,
        "kesit_elle": False, "yazi_handle": None, "cizgi_handleler": [],
        "l1_m": 0.0, "l2_m": 0.0, "l_net_m": 0.0, "d1_m": 0.0, "d2_m": 0.0,
        "eksik_uyari": "", "notlar": [],
    }
    ayrisimlar = []
    for y in okuma.get("yazilar", []):
        a = kiris_yazisi_ayristir(y.get("metin", ""))
        a["handle"] = y.get("handle")
        ayrisimlar.append(a)
    kesitli = [a for a in ayrisimlar if a["kesitli"]]
    hatali = [a for a in ayrisimlar if a["hata"] and a["hata"] != "Boş yazı"]
    kesitsiz = [a for a in ayrisimlar if not a["kesitli"] and not a["hata"]]
    if len(kesitli) > 1:
        s["hata"] = ("Birden fazla kiriş yazısı seçildi (" + ", ".join(a["ad"] for a in kesitli)
                     + ") — her kiriş için TEK yazı")
        return s
    if kesitli:
        yazi = kesitli[0]
    elif hatali:
        s["hata"] = f"Kiriş yazısı geçersiz: {hatali[0]['ham_metin']!r} ({hatali[0]['hata']})"
        return s
    elif len(kesitsiz) == 1:
        yazi = kesitsiz[0]
        s["kesit_elle"] = True
    elif kesitsiz:
        s["hata"] = f"{len(kesitsiz)} yazı seçildi, hiçbirinde kesit (b/h) yok — her kiriş için TEK yazı"
        return s
    else:
        s["hata"] = "Kiriş yazısı seçilmedi (etiket + 2 kenar çizgisi seçin)"
        return s
    s.update(ad=yazi["ad"], b_cm=yazi["b_cm"], h_cm=yazi["h_cm"], yazi_handle=yazi["handle"])
    if len(ayrisimlar) > 1:
        s["notlar"].append(f"{len(ayrisimlar) - 1} ek yazı yok sayıldı")

    # Rev-158: ortak kenar ölçümü — l1/l2 = KAPSAM (boşluk dahil, beton/alt kalıp),
    # d1/d2 = DOLU (parça toplamı, yan kalıp). Bölünmemiş kenarda ikisi eşit.
    carpan = cizim_uzunlugu_metreye_cevir(1.0, birim) * float(olcek)
    olc = kiris_kenarlari_olc(okuma.get("cizgiler", []), carpan)
    s["notlar"].extend(olc["notlar"])
    if olc["hata"]:
        s["hata"] = olc["hata"]
        return s
    k1, k2 = olc["kenarlar"]
    s["cizgi_handleler"] = olc["handleler"]
    s["l1_m"], s["l2_m"] = k1["kapsam_m"], k2["kapsam_m"]
    s["d1_m"], s["d2_m"] = k1["dolu_m"], k2["dolu_m"]
    s["l_net_m"] = olc["l_beton_m"]
    s["eksik_uyari"] = kenar_eksik_secim_uyarisi(k1["kapsam_m"], k2["kapsam_m"], s["b_cm"])
    s["gecerli"] = True
    return s


def kiris_mukerrer_bul(kayitlar: List[Dict[str, Any]], handleler) -> Dict[str, Any]:
    """Seçilen handle'lardan biri kayıtlı bir satırda kullanılmış mı?

    Neyi çözüyoruz? Mükerrer koruma HANDLE bazlı (aynı ad farklı handle =
    farklı açıklık, mükerrer DEĞİL). İki ayrı kayıtla çakışma -> hata.

    Returns:
        dict: index (int|None), hata (str).
    """
    hs = {h for h in handleler if h}
    bulunan = [i for i, k in enumerate(kayitlar)
               if hs & set(k.get("handleler") or [])]
    if len(bulunan) > 1:
        adlar = ", ".join(kayitlar[i].get("ad", "?") for i in bulunan)
        return {"index": None, "hata": f"Seçim birden fazla kayıtlı kirişle çakışıyor ({adlar})"}
    return {"index": bulunan[0] if bulunan else None, "hata": ""}


# ── Rev-144 Aşama 2: tıklanan köşelerden poligon (saf geometri) ──
# Tek döşeme bu aralığın dışındaysa birim/ölçek şüphesi — teyit zorunlu
DOSEME_ALAN_MIN_M2 = 0.5
DOSEME_ALAN_MAX_M2 = 2000.0


def dikdortgen_koseleri(p1, p2) -> List[Tuple[float, float]]:
    """İki karşı köşeden eksene paralel dikdörtgenin 4 köşesi (saat yönü fark etmez)."""
    (x1, y1), (x2, y2) = (float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1]))
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def poligon_temizle(koseler) -> List[Tuple[float, float]]:
    """Ardışık çift tıklamaları ve kapanış tekrarını (son = ilk) atar."""
    temiz: List[Tuple[float, float]] = []
    for p in koseler:
        q = (float(p[0]), float(p[1]))
        if not temiz or math.hypot(q[0] - temiz[-1][0], q[1] - temiz[-1][1]) > 1e-9:
            temiz.append(q)
    if len(temiz) > 1 and math.hypot(temiz[0][0] - temiz[-1][0], temiz[0][1] - temiz[-1][1]) <= 1e-9:
        temiz.pop()
    return temiz


def poligon_alani(koseler) -> float:
    """Shoelace formülü — mutlak alan (köşe sırası yönü fark etmez)."""
    n = len(koseler)
    s = sum(koseler[i][0] * koseler[(i + 1) % n][1] - koseler[(i + 1) % n][0] * koseler[i][1]
            for i in range(n))
    return abs(s) / 2.0


def poligon_cevresi(koseler) -> float:
    n = len(koseler)
    return sum(math.hypot(koseler[(i + 1) % n][0] - koseler[i][0], koseler[(i + 1) % n][1] - koseler[i][1])
               for i in range(n))


def poligon_agirlik_merkezi(koseler) -> Tuple[float, float]:
    """Alan ağırlık merkezi; alan ~0 ise köşe ortalaması."""
    n = len(koseler)
    a = cx = cy = 0.0
    for i in range(n):
        x0, y0 = koseler[i]
        x1, y1 = koseler[(i + 1) % n]
        k = x0 * y1 - x1 * y0
        a += k
        cx += (x0 + x1) * k
        cy += (y0 + y1) * k
    if abs(a) < 1e-12:
        return (sum(p[0] for p in koseler) / n, sum(p[1] for p in koseler) / n)
    return (cx / (3.0 * a), cy / (3.0 * a))


def nokta_poligon_icinde_mi(p, koseler) -> bool:
    """Işın atma (ray casting) — kenar üzerindeki nokta belirsiz, iç sayılabilir."""
    x, y = float(p[0]), float(p[1])
    ic = False
    n = len(koseler)
    for i in range(n):
        x0, y0 = koseler[i]
        x1, y1 = koseler[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            ic = not ic
    return ic


def _dogru_parcalari_kesisiyor(a, b, c, d) -> bool:
    """[ab] ile [cd] gerçekten kesişiyor mu (uç noktada değme sayılmaz)."""
    def yon(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)
    d1, d2, d3, d4 = yon(a, b, c), yon(a, b, d), yon(c, d, a), yon(c, d, b)
    return d1 * d2 < 0 and d3 * d4 < 0


def poligon_kendini_kesiyor_mu(koseler) -> bool:
    """Komşu olmayan iki kenar kesişiyorsa True (papyon şekli vb.)."""
    n = len(koseler)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue  # komşu kenarlar ortak köşede buluşur
            if _dogru_parcalari_kesisiyor(koseler[i], koseler[(i + 1) % n],
                                          koseler[j], koseler[(j + 1) % n]):
                return True
    return False


def doseme_poligon_degerlendir(koseler, birim: str, olcek: float = 1.0) -> Dict[str, Any]:
    """Tıklanan köşelerden döşeme alanı (m²) ve çevresi (m) — saf, COM'suz.

    Neyi çözüyoruz? Köşe tıklamasından gelen noktaları temizler (çift tık,
    kapanış tekrarı), en az 3 köşe / sıfırdan büyük alan / kendini
    kesmeme şartlarını denetler; alanı perde aracının dönüşümüyle
    (cizim_alani_m2ye_cevir — ölçek KARESİ) m²'ye, çevreyi ölçekle m'ye çevirir.
    Nasıl test ederiz? scratchpad/test_doseme_poligon.py — 1/50 mm
    dikdörtgen, L poligon, papyon (kendini kesen), 2 nokta, sıfır alan.

    Returns:
        dict: koseler (temiz, çizim birimi), alan_m2, cevre_m,
              agirlik_merkezi (çizim birimi), supheli (teyit gerekli), hata.
    """
    sonuc: Dict[str, Any] = {"koseler": [], "alan_m2": 0.0, "cevre_m": 0.0,
                             "agirlik_merkezi": None, "supheli": False, "hata": ""}
    try:
        temiz = poligon_temizle(koseler or [])
    except (TypeError, ValueError, IndexError):
        sonuc["hata"] = "Köşe koordinatları okunamadı"
        return sonuc
    if len(temiz) < 3:
        sonuc["hata"] = f"En az 3 köşe gerekli ({len(temiz)} köşe tıklandı)"
        return sonuc
    # Önce kesişim: papyon şeklinin işaretli alanı ~0 çıkar, yanlış mesaj vermesin
    if poligon_kendini_kesiyor_mu(temiz):
        sonuc["hata"] = "Poligon kendini kesiyor — köşeleri sırayla (çevre boyunca) tıklayın"
        return sonuc
    alan_birim = poligon_alani(temiz)
    if alan_birim <= 1e-9:
        sonuc["hata"] = "Alan sıfır — köşeler aynı doğru üzerinde"
        return sonuc
    try:
        alan_m2 = round(cizim_alani_m2ye_cevir(alan_birim, birim, olcek), 4)
        cevre_m = round(poligon_cevresi(temiz) * CIZIM_BIRIM_CARPANI[birim] * float(olcek), 3)
    except (KeyError, ValueError) as e:
        sonuc["hata"] = f"Birim/ölçek hatası: {e}"
        return sonuc
    sonuc.update({
        "koseler": temiz, "alan_m2": alan_m2, "cevre_m": cevre_m,
        "agirlik_merkezi": poligon_agirlik_merkezi(temiz),
        "supheli": not (DOSEME_ALAN_MIN_M2 <= alan_m2 <= DOSEME_ALAN_MAX_M2),
    })
    return sonuc


def _poligon_kenarlari_kesisiyor(a, b) -> bool:
    """İki poligonun herhangi iki kenarı gerçekten kesişiyor mu (değme sayılmaz)."""
    na, nb = len(a), len(b)
    return any(_dogru_parcalari_kesisiyor(a[i], a[(i + 1) % na], b[j], b[(j + 1) % nb])
               for i in range(na) for j in range(nb))


def bosluk_degerlendir(doseme_koseler, bosluk_koseler, mevcut_bosluklar, birim: str,
                       olcek: float = 1.0, brut_alan_m2: float = None) -> Dict[str, Any]:
    """Döşemeye eklenecek boşluğu (merdiven, şaft, asansör) doğrular (Rev-149 Aşama 3).

    Neyi çözüyoruz?
    - Boşluk poligonu kendi başına geçerli olmalı (≥3 köşe, alan > 0, kendini kesmez).
    - TÜM köşeleri döşemenin içinde olmalı VE kenarları döşeme kenarlarını
      kesmemeli (L döşemede köşeler içeride olup kenar iç köşeden taşabilir).
    - Aynı döşemedeki başka bir boşlukla çakışmamalı (alan iki kez düşülür).
    - Toplam boşluk alanı brüt alanı geçemez.
    Alan/çevre dönüşümü doseme_poligon_degerlendir ile aynı (ölçek karesi).

    Nasıl test ederiz? scratchpad/test_doseme_bosluk.py — 6×5 döşeme + 2×2.5
    boşluk (h=15) -> net 25, beton 3.75, kenar 1.35, toplam 26.35; kısmen
    taşan, L iç köşesinden taşan, çakışan boşluk -> reddedilir.

    Returns:
        dict: koseler, alan_m2, cevre_m, hata.
    """
    d = doseme_poligon_degerlendir(bosluk_koseler, birim, olcek)
    sonuc: Dict[str, Any] = {"koseler": d["koseler"], "alan_m2": d["alan_m2"],
                             "cevre_m": d["cevre_m"], "hata": d["hata"]}
    if d["hata"]:
        return sonuc
    b = d["koseler"]
    dos = poligon_temizle(doseme_koseler or [])
    if len(dos) < 3:
        sonuc["hata"] = "Döşeme poligonu yok — boşluk sadece tıklanarak eklenen döşemeye eklenebilir"
        return sonuc
    if not all(nokta_poligon_icinde_mi(p, dos) for p in b) or _poligon_kenarlari_kesisiyor(b, dos):
        sonuc["hata"] = "Boşluk döşemenin tamamen İÇİNDE değil — köşeleri döşeme sınırının içinden tıklayın"
        return sonuc
    for diger in mevcut_bosluklar or []:
        diger = poligon_temizle(diger)
        if (any(nokta_poligon_icinde_mi(p, diger) for p in b)
                or any(nokta_poligon_icinde_mi(p, b) for p in diger)
                or _poligon_kenarlari_kesisiyor(b, diger)):
            sonuc["hata"] = "Boşluk, bu döşemedeki başka bir boşlukla çakışıyor (alan iki kez düşülür)"
            return sonuc
    if brut_alan_m2 is not None:
        mevcut = sum(cizim_alani_m2ye_cevir(poligon_alani(poligon_temizle(x)), birim, olcek)
                     for x in (mevcut_bosluklar or []))
        if mevcut + sonuc["alan_m2"] >= float(brut_alan_m2):
            sonuc["hata"] = (f"Toplam boşluk ({mevcut + sonuc['alan_m2']:.2f} m²) brüt alanı "
                             f"({float(brut_alan_m2):.2f} m²) geçemez")
    return sonuc


# ══ Rev-164: SAÇAK (kenar kirişin dış yüzünden taşan sabit kalınlıklı konsol plak) ══
# Döşeme aracının içinde ayrı mod; satırlar döşeme listesinde "tip": "Saçak" ile durur.
# Hesap doseme_hesapla'nın AYNISI (boşluk yok): beton = alan × t, alt kalıp = alan,
# kenar kalıbı = serbest kenar (kiriş tarafı HARİÇ çevre) × t.
SACAK_TIPI = "Saçak"
SACAK_HALKA = "Halka"
SACAK_SERIT = "Şerit"
SACAK_RENK = 40   # ACI 40 kehribar — ACI 30 (turuncu) iç kirişe ayrılmış (Rev-150)


def sacak_mi(satir: Dict[str, Any]) -> bool:
    return (satir or {}).get("tip") == SACAK_TIPI


def _acik_hat_uzunlugu(noktalar) -> float:
    return sum(math.hypot(noktalar[i + 1][0] - noktalar[i][0], noktalar[i + 1][1] - noktalar[i][1])
               for i in range(len(noktalar) - 1))


def poligon_ic_noktasi(koseler, delik=None) -> Optional[Tuple[float, float]]:
    """Poligonun (varsa deliğin DIŞINDA kalan) içinden bir nokta — mükerrer denetimi için.
    L / U biçimli şeritte ve halkada ağırlık merkezi dışarıda/delikte kalabilir; sırayla
    ağırlık merkezi ve köşe çiftlerinin orta noktaları denenir."""
    dis = poligon_temizle(koseler or [])
    ic = poligon_temizle(delik or [])
    if len(dis) < 3:
        return None

    def uygun(p):
        return nokta_poligon_icinde_mi(p, dis) and not (len(ic) >= 3 and nokta_poligon_icinde_mi(p, ic))

    adaylar = [poligon_agirlik_merkezi(dis)]
    tum = dis + ic
    adaylar += [((tum[i][0] + tum[j][0]) / 2.0, (tum[i][1] + tum[j][1]) / 2.0)
                for i in range(len(tum)) for j in range(i + 1, len(tum))]
    return next((p for p in adaylar if uygun(p)), None)


def sacak_icinde_mi(p, satir: Dict[str, Any]) -> bool:
    """Nokta bu saçak satırının alanında mı (halkada iç poligon hariç)?"""
    if p is None or len(satir.get("koseler") or []) < 3:
        return False
    ic = satir.get("ic_koseler") or []
    return nokta_poligon_icinde_mi(p, satir["koseler"]) and not (len(ic) >= 3 and nokta_poligon_icinde_mi(p, ic))


def sacak_mukerrer_bul(d: Dict[str, Any], kayitlar: List[Dict[str, Any]]) -> Optional[int]:
    """Yeni saçak mevcut bir SAÇAK satırıyla çakışıyor mu (döşeme satırlarına bakılmaz —
    halka saçağın dış poligonu bütün binayı kapsar). İki yönlü: yeninin iç noktası eskinin
    içinde ya da eskinin iç noktası yeninin içinde."""
    yeni_nokta = poligon_ic_noktasi(d.get("koseler"), d.get("ic_koseler"))
    for i, s in enumerate(kayitlar or []):
        if not sacak_mi(s):
            continue
        if sacak_icinde_mi(yeni_nokta, s) or sacak_icinde_mi(poligon_ic_noktasi(s.get("koseler"),
                                                                                 s.get("ic_koseler")), d):
            return i
    return None


def sacak_halka_degerlendir(dis_koseler, ic_koseler, birim: str, olcek: float = 1.0) -> Dict[str, Any]:
    """[H]alka saçak (binayı tamamen sarar): dış = saçak ucu köşeleri, iç = kenar kirişin DIŞ yüzü.

    Neyi çözüyoruz? Alan = dış − iç. İç poligon dış poligonun TAMAMEN içinde olmalı (köşeler +
    kenar kesişimi — bosluk_degerlendir ile aynı denetim), değilse ALINMAZ. Kenar kalıbı = dış
    çevre; iç çevre kirişe bağlı olduğu için kalıba EKLENMEZ.
    Nasıl test ederiz? dış 13.6×11.6, iç 12×10 -> alan 37.76, kenar 50.4; t=16 -> beton 6.042,
    toplam kalıp 45.82; iç taşarsa hata. scratchpad/test_sacak.py.

    Returns: koseler (dış), ic_koseler, alan_m2, cevre_m (dış), kiris_m (iç çevre), kenar_m,
             supheli, hata."""
    sonuc: Dict[str, Any] = {"koseler": [], "ic_koseler": [], "alan_m2": 0.0, "cevre_m": 0.0,
                             "kiris_m": 0.0, "kenar_m": 0.0, "supheli": False, "hata": ""}
    d = doseme_poligon_degerlendir(dis_koseler, birim, olcek)
    if d["hata"]:
        sonuc["hata"] = f"Saçak ucu (dış) poligonu: {d['hata']}"
        return sonuc
    b = bosluk_degerlendir(d["koseler"], ic_koseler, [], birim, olcek, d["alan_m2"])
    if b["hata"]:
        if "İÇİNDE değil" in b["hata"]:
            sonuc["hata"] = ("Kiriş dış yüzü (iç poligon) saçak ucunun (dış poligon) tamamen İÇİNDE "
                             "olmalı — saçak ALINMADI")
        elif "geçemez" in b["hata"]:
            sonuc["hata"] = "İç poligon dış poligondan küçük olmalı — saçak ALINMADI"
        else:
            sonuc["hata"] = f"Kiriş dış yüzü (iç) poligonu: {b['hata']}"
        return sonuc
    alan = round(d["alan_m2"] - b["alan_m2"], 4)
    sonuc.update(koseler=d["koseler"], ic_koseler=b["koseler"], alan_m2=alan, cevre_m=d["cevre_m"],
                 kiris_m=b["cevre_m"], kenar_m=d["cevre_m"],
                 supheli=not (DOSEME_ALAN_MIN_M2 <= alan <= DOSEME_ALAN_MAX_M2))
    return sonuc


def sacak_serit_degerlendir(kiris_hatti, uc_hatti, birim: str, olcek: float = 1.0) -> Dict[str, Any]:
    """[Ş]erit saçak (bazı cephelerde): kiriş hattı (kiriş dış yüzü) + uç hattı (saçak ucu).

    Neyi çözüyoruz? İki açık hat uçlarından birleştirilip kapalı poligon kurulur. Uç hattı
    ters yönde tıklanmış olabilir: kiriş sonu→uç başı + uç sonu→kiriş başı toplamı, ters
    birleşimden uzunsa uç hattı ters çevrilir (kendini kesen "papyon" oluşmaz). Kenar kalıbı =
    poligon çevresi − kiriş hattı uzunluğu (uç hattı + iki yan uç).
    Nasıl test ederiz? kiriş 12 m düz, uç 12 m (0.80 dışarıda) -> alan 9.60, kenar 13.60; t=16
    -> beton 1.536, toplam kalıp 11.78; uç ters tıklanınca aynı.

    Returns: koseler (poligon), kiris_hatti, uc_hatti, alan_m2, cevre_m, kiris_m, kenar_m,
             ters_cevrildi, supheli, hata."""
    sonuc: Dict[str, Any] = {"koseler": [], "kiris_hatti": [], "uc_hatti": [], "alan_m2": 0.0,
                             "cevre_m": 0.0, "kiris_m": 0.0, "kenar_m": 0.0, "ters_cevrildi": False,
                             "supheli": False, "hata": ""}
    try:
        k = poligon_temizle(kiris_hatti or [])
        u = poligon_temizle(uc_hatti or [])
        carpan = CIZIM_BIRIM_CARPANI[birim] * float(olcek)
    except (TypeError, ValueError, IndexError, KeyError) as e:
        sonuc["hata"] = f"Hat koordinatları / birim okunamadı: {e}"
        return sonuc
    if len(k) < 2 or len(u) < 2:
        sonuc["hata"] = "Kiriş hattı ve uç hattı en az 2'şer nokta olmalı"
        return sonuc

    def uz(p, q):
        return math.hypot(p[0] - q[0], p[1] - q[1])

    duz = uz(k[-1], u[0]) + uz(u[-1], k[0])
    ters = uz(k[-1], u[-1]) + uz(u[0], k[0])
    if ters < duz:
        u = list(reversed(u))
        sonuc["ters_cevrildi"] = True
    d = doseme_poligon_degerlendir(k + u, birim, olcek)
    if d["hata"]:
        sonuc["hata"] = (f"Saçak poligonu kurulamadı: {d['hata']}"
                         + (" — kiriş hattı ile uç hattı kesişiyor olabilir" if "kesiyor" in d["hata"] else ""))
        return sonuc
    kiris_m = round(_acik_hat_uzunlugu(k) * carpan, 3)
    kenar = round(d["cevre_m"] - kiris_m, 3)
    if kenar <= 0:
        sonuc["hata"] = "Kenar kalıbı uzunluğu sıfır — uç hattını kontrol edin"
        return sonuc
    sonuc.update(koseler=d["koseler"], kiris_hatti=k, uc_hatti=u, alan_m2=d["alan_m2"], cevre_m=d["cevre_m"],
                 kiris_m=kiris_m, kenar_m=kenar, supheli=d["supheli"])
    return sonuc


def sacak_hesapla(alan_m2: float, kalinlik_cm: float, kenar_m: float) -> Dict[str, Any]:
    """Saçak beton + kalıp — doseme_hesapla ile AYNI formül (boşluk yok, serbest kenar = kenar_m).
    Nasıl test ederiz? (37.76, 16, 50.4) -> beton 6.042, alt 37.76, kenar 8.064, toplam 45.824."""
    return doseme_hesapla(alan_m2, kalinlik_cm, 0.0, 0.0, kenar_m)


# İki kenar çizgisi arasındaki bu orandan büyük fark "yanlış çizgi" şüphesi.
TEMEL_KIRISI_CIZGI_FARK_UYARI = 0.10
TEMEL_KIRISI_MIN_UZUNLUK_M = 0.10


def _nokta_dogru_parcasi_uzakligi(p, a, b) -> float:
    """p noktasının [a,b] doğru parçasına en kısa uzaklığı (2B)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    uz2 = dx * dx + dy * dy
    if uz2 == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / uz2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def _cizgi_anahtari(c: Dict[str, Any]):
    """Üst üste çift çizgi tespiti için yön bağımsız, yuvarlanmış uç noktaları."""
    if not c.get("bas") or not c.get("son"):
        return None
    uclar = sorted([(round(c["bas"][0], 3), round(c["bas"][1], 3)),
                    (round(c["son"][0], 3), round(c["son"][1], 3))])
    return tuple(uclar)


def temel_kirisi_secimi_ayir(okuma: Dict[str, Any]) -> Dict[str, Any]:
    """Tek ENTER'daki seçimi kirişlere ayırır (Rev-137, gerçek AutoCAD logu).

    Neyi çözüyoruz? Gerçek kullanımda tek seçimde 2 "SBH-1" yazısı + 4
    çizgi geldi. İki olası neden, ikisi de burada çözülür:
      (a) Üst üste kopyalanmış ÇİFT obje: uç noktaları aynı çizgiler ve aynı
          konumdaki aynı yazılar tekilleştirilir (not düşülür).
      (b) Kullanıcı ENTER'a basmadan birden fazla kiriş seçti: N yazı + 2N
          çizgi ise her yazı en YAKIN 2 çizgisiyle eşleştirilir (global en
          kısa mesafe önce, açgözlü). Eşleşen iki çizgi paralel değilse not.
    Yazı ≤ 1 ise seçim olduğu gibi (tekilleştirilmiş) tek grup döner —
    kural denetimi temel_kirisi_secim_degerlendir'de.
    Koordinat okunamazsa eşleştirme yapılmaz, açık hata döner.

    Nasıl test ederiz? scratchpad/test_temel_kirisi.py — çift obje, 2 kiriş
    tek seçim, sayı uyuşmazlığı, koordinatsız senaryolar.

    Returns:
        dict: gruplar (her biri okuma formatında: yazilar/cizgiler/
              gecersiz_yazilar/notlar), hata (str).
    """
    notlar: List[str] = []

    cizgiler: List[Dict[str, Any]] = []
    gorulen = set()
    for c in okuma.get("cizgiler", []):
        k = _cizgi_anahtari(c)
        if k is not None and k in gorulen:
            notlar.append(f"üst üste çift çizgi ({c.get('handle')}) tekilleştirildi")
            continue
        if k is not None:
            gorulen.add(k)
        cizgiler.append(c)

    yazilar: List[Dict[str, Any]] = []
    gorulen_y = set()
    for y in okuma.get("yazilar", []):
        konum = y.get("konum")
        k = (y.get("ad"), y.get("genislik_cm"), y.get("yukseklik_cm"),
             (round(konum[0], 3), round(konum[1], 3)) if konum else y.get("handle"))
        if k in gorulen_y:
            notlar.append(f"üst üste çift yazı {y.get('ad')} ({y.get('handle')}) tekilleştirildi")
            continue
        gorulen_y.add(k)
        yazilar.append(y)

    temel = {"gecersiz_yazilar": okuma.get("gecersiz_yazilar", []), "notlar": notlar}
    if len(yazilar) <= 1:
        return {"gruplar": [dict(temel, yazilar=yazilar, cizgiler=cizgiler)], "hata": ""}

    n = len(yazilar)
    if len(cizgiler) != 2 * n:
        return {"gruplar": [], "hata": (
            f"{n} SBH yazısı ve {len(cizgiler)} çizgi seçildi — birden fazla kirişi tek "
            f"seferde seçerken her yazı için tam 2 kenar çizgisi olmalı ({2 * n} çizgi)")}
    if any(y.get("konum") is None for y in yazilar) or any(
            not c.get("bas") or not c.get("son") for c in cizgiler):
        return {"gruplar": [], "hata": (
            f"{n} kiriş tek seferde seçildi ama konumlar okunamadı — kirişleri tek tek "
            "(yazı + 2 çizgi + ENTER) seçin")}

    adaylar = sorted(
        (_nokta_dogru_parcasi_uzakligi(y["konum"], c["bas"], c["son"]), yi, ci)
        for yi, y in enumerate(yazilar) for ci, c in enumerate(cizgiler)
    )
    eslesme: Dict[int, List[int]] = {i: [] for i in range(n)}
    kullanilan = set()
    for _, yi, ci in adaylar:
        if ci in kullanilan or len(eslesme[yi]) >= 2:
            continue
        eslesme[yi].append(ci)
        kullanilan.add(ci)

    gruplar = []
    for yi, y in enumerate(yazilar):
        grup_cizgileri = [cizgiler[ci] for ci in eslesme[yi]]
        grup_notlari = list(notlar) if yi == 0 else []
        if len(grup_cizgileri) == 2:
            v = []
            for c in grup_cizgileri:
                dx, dy = c["son"][0] - c["bas"][0], c["son"][1] - c["bas"][1]
                u = math.hypot(dx, dy) or 1.0
                v.append((dx / u, dy / u))
            if abs(v[0][0] * v[1][0] + v[0][1] * v[1][1]) < 0.98:
                grup_notlari.append("eşleşen 2 çizgi paralel değil — yanlış eşleşme olabilir")
        gruplar.append(dict(temel, yazilar=[y], cizgiler=grup_cizgileri, notlar=grup_notlari))
    return {"gruplar": gruplar, "hata": ""}


def temel_kirisi_secim_degerlendir(okuma: Dict[str, Any], birim: str) -> Dict[str, Any]:
    """Toplu modda TEK kirişin seçimini (yazı + kenar çizgileri) değerlendirir.

    Neyi çözüyoruz? Kullanıcı AutoCAD'de SBH yazısı + 2 kenar çizgisi (üst+
    alt) seçip ENTER'a basar. Uzunluk = 2 çizginin ORTALAMASI (çizim
    birimi -> metre). Saf fonksiyon: COM'dan bağımsız karar katmanı.
    Kurallar:
      - Tam 1 geçerli SBH yazısı şart (0 ya da >1 -> hata, kiriş atlanır).
      - Rev-158: çizgi sayısı sınırsız (bölünmüş kenar parçaları). 0 -> elle_gerekli;
        1 -> hata (en az 2); iki kenara ayrılamazsa -> hata. L = (kapsam1 +
        kapsam2) / 2, yan kalıp için yan_dolu_m; |kapsam farkı| > 2b ->
        eksik_uyari (UI kullanıcıya sorar).
      - L > 50 m veya < 0.10 m -> uyarı (engellemez, birim hatası şüphesi).

    Nasıl test ederiz? scratchpad/test_temel_kirisi.py:
      SBH-1 (20/165) + çizgiler 500/510 cm -> L=5.05, beton=1.667, kalıp=16.665

    Returns:
        dict: gecerli, hata, elle_gerekli, ad, genislik_cm, yukseklik_cm,
              yazi_handle, cizgi_handleler, cizgi_uzunluklari_m, uzunluk_m
              (elle_gerekli ise None), kaynak, uyarilar (list).
    """
    s: Dict[str, Any] = {
        "gecerli": False, "hata": "", "elle_gerekli": False,
        "ad": None, "genislik_cm": 0.0, "yukseklik_cm": 0.0,
        "yazi_handle": None, "cizgi_handleler": [], "cizgi_uzunluklari_m": [],
        "kenar_kapsam_m": [], "yan_dolu_m": [], "eksik_uyari": "",
        "uzunluk_m": None, "kaynak": "", "uyarilar": [],
    }
    yazilar = okuma.get("yazilar", [])
    if len(yazilar) == 0:
        gecersiz = okuma.get("gecersiz_yazilar", [])
        s["hata"] = (f"SBH yazısı geçersiz: {gecersiz[0].get('hata')}" if gecersiz
                     else "SBH yazısı seçilmedi (önce yazıyı, sonra 2 kenar çizgisini seçin)")
        return s
    if len(yazilar) > 1:
        adlar = ", ".join(str(y.get("ad")) for y in yazilar)
        s["hata"] = f"Birden fazla SBH yazısı seçildi ({adlar}) — her kiriş için TEK yazı"
        return s

    y = yazilar[0]
    s.update({"ad": y["ad"], "genislik_cm": y["genislik_cm"],
              "yukseklik_cm": y["yukseklik_cm"], "yazi_handle": y.get("handle")})
    if y.get("uyari"):
        s["uyarilar"].append(y["uyari"])

    cizgiler = okuma.get("cizgiler", [])
    okunan = [c for c in cizgiler if not c.get("hata") and c.get("uzunluk_birim", 0) > 0]
    if len(okunan) < len(cizgiler):
        s["uyarilar"].append(f"{len(cizgiler) - len(okunan)} çizginin uzunluğu okunamadı")
    if not okunan:
        s["elle_gerekli"] = True
        s["gecerli"] = True
        s["kaynak"] = "Elle"
        return s

    # Rev-158: çizgi sayısı sınırı YOK — bölünmüş kenarın tüm parçaları seçilebilir.
    # Ortak ölçüm (K aracıyla aynı): iki kenar, kapsam (boşluk dahil) + dolu.
    olc = kiris_kenarlari_olc(okunan, cizim_uzunlugu_metreye_cevir(1.0, birim))
    if olc["hata"]:
        s["hata"] = olc["hata"]
        return s
    k1, k2 = olc["kenarlar"]
    s["cizgi_handleler"] = olc["handleler"]
    s["cizgi_uzunluklari_m"] = [cizim_uzunlugu_metreye_cevir(c["uzunluk_birim"], birim)
                                for c in okunan]
    s["kenar_kapsam_m"] = [k1["kapsam_m"], k2["kapsam_m"]]
    s["yan_dolu_m"] = [k1["dolu_m"], k2["dolu_m"]]
    s["uzunluk_m"] = olc["l_beton_m"]
    if k1["parca"] == 1 and k2["parca"] == 1:
        s["kaynak"] = f"Çizgi ort. ({k1['kapsam_m']:.2f}/{k2['kapsam_m']:.2f})"
    else:
        s["kaynak"] = (f"Kenar kapsam ort. ({k1['kapsam_m']:.2f}/{k2['kapsam_m']:.2f}; "
                       f"dolu {k1['dolu_m']:.2f}/{k2['dolu_m']:.2f})")
    s["uyarilar"].extend(olc["notlar"])
    s["eksik_uyari"] = kenar_eksik_secim_uyarisi(k1["kapsam_m"], k2["kapsam_m"], s["genislik_cm"])

    for n in okuma.get("notlar", []):
        s["uyarilar"].append(n)

    L = s["uzunluk_m"]
    if L > TEMEL_KIRISI_UZUNLUK_UYARI_M or L < TEMEL_KIRISI_MIN_UZUNLUK_M:
        s["uyarilar"].append(f"Uzunluk {L:.2f} m olağan dışı — çizim birimi ({birim}) yanlış olabilir")
    s["gecerli"] = True
    return s


def _oto_esik_bul(sirali_degerler: List[float], min_esik: float = 1e-6) -> float:
    """Sıralı (küçükten büyüğe) 1B değer listesindeki en belirgin "sıçrama"yı
    bulup kümeleme eşiği olarak döner.

    Neyi çözüyoruz: Bir tablo satırındaki farklı sütun hücreleri neredeyse
    aynı Y'de, farklı satırlar arasında ise belirgin bir boşluk vardır (aynı
    mantık X/sütun için de geçerli). Bu fonksiyon sabit bir tolerans
    VARSAYMAK yerine, ardışık farkların sıralı listesindeki en büyük ORANSAL
    sıçramayı (elbow) bulup eşiği oradan türetir — farklı ölçekteki/DPI'daki
    çizimlerde de otomatik uyum sağlar.
    Nasıl test ederiz: scratchpad/test_poz_donati_kumele.py — bilinen
    satır/sütun aralıklarına sahip sentetik koordinatlarla, bulunan eşiğin
    intra-satır farkının üstünde ve inter-satır farkının altında kaldığı
    doğrulanır.
    """
    if len(sirali_degerler) < 2:
        return min_esik
    farklar = [sirali_degerler[i + 1] - sirali_degerler[i] for i in range(len(sirali_degerler) - 1)]
    pozitif = sorted(set(f for f in farklar if f > min_esik))
    if not pozitif:
        return min_esik
    if len(pozitif) == 1:
        return pozitif[0] / 2.0
    en_iyi_oran = -1.0
    esik_index = 0
    for i in range(len(pozitif) - 1):
        onceki = pozitif[i] if pozitif[i] > min_esik else min_esik
        oran = pozitif[i + 1] / onceki
        if oran > en_iyi_oran:
            en_iyi_oran = oran
            esik_index = i
    return (pozitif[esik_index] + pozitif[esik_index + 1]) / 2.0


def _1d_kumele(degerler_ve_index: List[Tuple[float, int]], esik: Optional[float] = None) -> List[List[int]]:
    """Tek boyutlu (X ya da Y) (değer, orijinal_indeks) listesini kümeler.

    esik verilmezse _oto_esik_bul ile otomatik bulunur. Her kümenin
    "merkezi", o kümeye o ana kadar eklenen değerlerin ortalaması olarak
    güncellenir (tek tek komşu farkına bakmak yerine) — böylece yavaş kayan
    (hafif eğik) satırlarda küme merkezi sürüklenip yanlış ayrım yapmaz.
    Dönen kümeler değere göre küçükten büyüğe sıralıdır.
    """
    if not degerler_ve_index:
        return []
    sirali = sorted(degerler_ve_index, key=lambda t: t[0])
    if esik is None:
        esik = _oto_esik_bul([d for d, _ in sirali])

    kumeler: List[List[int]] = [[sirali[0][1]]]
    kume_toplam = [sirali[0][0]]
    kume_adet = [1]
    for deger, idx in sirali[1:]:
        merkez = kume_toplam[-1] / kume_adet[-1]
        if abs(deger - merkez) <= esik:
            kumeler[-1].append(idx)
            kume_toplam[-1] += deger
            kume_adet[-1] += 1
        else:
            kumeler.append([idx])
            kume_toplam.append(deger)
            kume_adet.append(1)
    return kumeler


def tablo_hucrelerini_kumele(
    hucreler: List[Dict[str, Any]],
    y_esik: Optional[float] = None,
    x_esik: Optional[float] = None,
) -> List[List[Optional[Dict[str, Any]]]]:
    """(text,x,y) hücre listesini satır/sütun ızgarasına (grid) kümeler.

    Neyi çözüyoruz: get_kolon_filizi_from_table'ın içerik-bazlı yaklaşımı
    (donatı/boy/kolon kovaları) yalnızca TEK bir "saf sayı" sütunu olan
    tablolarda güvenli çalışır. Poza göre donatı metraj tablosunda ADET,
    ÇAP, BOY ve çap-bazlı TOPLAM sütunları HEPSİ saf sayı olduğundan içerik
    onları ayırt edemez — bu yüzden gerçek konum (X=sütun, Y=satır) kullanan
    bu fonksiyon gerekiyor. AutoCAD'in dead-code bırakılmış
    _read_entity_with_coords'unun (satır 821) tam olarak öngördüğü kullanım
    budur.

    hucreler: her biri en az {'text': str, 'x': float, 'y': float} içeren
        sözlük listesi (fazladan anahtarlar — 'entity', 'handle' vb. —
        olduğu gibi çıktıya taşınır, kayıp olmaz).
    Dönen değer: satırlar yukarıdan aşağı (Y büyükten küçüğe, AutoCAD'de
        yukarıdan aşağı okuma yönü), her satır içinde hücreler soldan sağa
        (X küçükten büyüğe) GLOBAL sütun indeksine yerleştirilir; o satırda
        karşılığı olmayan sütunlar None (boş hücre — örn. bir pozda sadece
        tek çap dolu, diğerleri boş).
    Nasıl test ederiz: scratchpad/test_poz_donati_kumele.py — ekran
        görüntüsündeki 7 satırlık gerçek tabloya benzer sentetik
        koordinatlarla (POZ/ADET/ÇAP/BOY + 3 ayrı TOPLAM-çap sütunu, bazı
        hücreler kasıtlı boş) grid boyutu ve hücre yerleşimi doğrulanır;
        ayrıca hafif eğik/gürültülü koordinatlarla dayanıklılık test edilir.
    """
    if not hucreler:
        return []

    y_girdi = [(-h['y'], i) for i, h in enumerate(hucreler)]
    satir_kumeleri = _1d_kumele(y_girdi, esik=y_esik)

    x_girdi = [(h['x'], i) for i, h in enumerate(hucreler)]
    sutun_kumeleri = _1d_kumele(x_girdi, esik=x_esik)
    sutun_sayisi = len(sutun_kumeleri)

    index_to_sutun: Dict[int, int] = {}
    for sutun_no, indeksler in enumerate(sutun_kumeleri):
        for idx in indeksler:
            index_to_sutun[idx] = sutun_no

    grid: List[List[Optional[Dict[str, Any]]]] = []
    for satir_indeksleri in satir_kumeleri:
        satir: List[Optional[Dict[str, Any]]] = [None] * sutun_sayisi
        for idx in satir_indeksleri:
            sutun_no = index_to_sutun[idx]
            if satir[sutun_no] is not None:
                # Aynı hücrede çakışma (nadir, örn. yan yana bitişik iki
                # metin objesi) — metinleri birleştir, veri kaybetme.
                birlesik = dict(satir[sutun_no])
                birlesik['text'] = f"{birlesik['text']} {hucreler[idx]['text']}".strip()
                satir[sutun_no] = birlesik
            else:
                satir[sutun_no] = hucreler[idx]
        grid.append(satir)
    return grid


# ── AŞAMA 2: Başlık tespiti + sütun→alan eşleme + çap normalizasyonu ────────
# Bu bölüm de SAF (COM bağımsız) — Aşama 1'in çıkardığı 'grid' üzerinde çalışır,
# gerçek AutoCAD veya sahte grid ile aynı şekilde test edilebilir.

_TR_ASCII = str.maketrans({
    'Ç': 'C', 'ç': 'c', 'Ş': 'S', 'ş': 's', 'İ': 'I', 'ı': 'i',
    'Ö': 'O', 'ö': 'o', 'Ü': 'U', 'ü': 'u', 'Ğ': 'G', 'ğ': 'g',
})

_POZ_ANAHTARLAR = {"POZ", "POZNO"}
_ADET_ANAHTARLAR = {"ADET", "ADED"}
_CAP_ANAHTARLAR = {"CAP", "CAPI"}
_BOY_ANAHTARLAR = {"BOY", "BOYU", "UZUNLUK"}
_SEKIL_ANAHTARLAR = {"SEKIL", "EKIL", "KROKI", "BUKUM"}

_CAP_SAYI_PATTERN = re.compile(r'(\d+)')


def _baslik_normalize(text: str) -> str:
    """Başlık hücre metnini karşılaştırılabilir hale getirir: Türkçe
    karakterleri ASCII'ye katlar, parantez içini ("(mm)","(m)") atar,
    boşluk/noktalama kaldırır, büyük harfe çevirir.
    Örn: "ÇAP(mm)" -> "CAP", "Boy (m)" -> "BOY", "Poz No" -> "POZNO".
    """
    if not text:
        return ""
    t = str(text).translate(_TR_ASCII).upper()
    t = re.sub(r'\([^)]*\)', '', t)
    t = re.sub(r'[^A-Z0-9]', '', t)
    return t


def cap_normalize_et(text) -> Optional[int]:
    """Demir çapı yazımındaki sembol/harf farklılıklarını (Ø18, φ18, Q18,
    D18, ø 18 mm, 18) sayıya indirger.

    Neyi çözüyoruz: Tablo çizenler çap sembolünü farklı yazabilir (bazen
    Ø karakteri encoding sorunuyla ?/Q'ya döner, bazen "D18" gibi yazılır).
    Regex \\d+ ile ilk sayı dizisini çekip sembol/harfi atarız.
    Nasıl test ederiz: scratchpad/test_poz_donati_baslik_esleme.py —
    "Ø18","φ18","Q18","D18","18","ø 18 mm" hepsi 18 vermeli; sayı içermeyen
    metin (örn. "-", "") None dönmeli.
    """
    if text is None:
        return None
    m = _CAP_SAYI_PATTERN.search(str(text))
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _sayi_parse_et(text) -> Optional[float]:
    """Türkçe ondalık virgüllü ('5,30') ya da noktalı ('5.30') sayı metnini
    float'a çevirir. Parse edilemezse (boş, harf içeren vb.) None döner."""
    if text is None:
        return None
    try:
        return float(str(text).strip().replace(',', '.'))
    except ValueError:
        return None


def _baslik_satirini_bul(
    grid: List[List[Optional[Dict[str, Any]]]],
    max_taranan_satir: int = 5,
):
    """İlk birkaç satır içinde ADET+ÇAP+BOY anahtar kelimelerinin ÜÇÜNÜN de
    (POZ/ŞEKİL bonus, zorunlu değil) bulunduğu satırı başlık olarak seçer.

    Neden ADET+ÇAP+BOY zorunlu: Bu üçü olmadan hesap (Aşama 3) yapılamaz;
    POZ sadece etiket/izlenebilirlik olduğundan eksik olsa da devam edilebilir.
    Birden fazla aday satır varsa (nadir), en çok alan eşleşen kazanır — bu,
    örn. "TOPLAM BOY (m)" gibi bir üst-birleşik başlık satırının yanlışlıkla
    gerçek başlık sanılmasını engeller (o satırda adet/çap/boy hiç geçmez).

    Returns: (baslik_satir_index, {sutun_index: 'poz'|'adet'|'cap'|'boy'|'sekil'})
             Bulunamazsa (None, {}).
    """
    en_iyi_index, en_iyi_harita, en_iyi_sayi = None, {}, -1
    for r_idx, satir in enumerate(grid[:max_taranan_satir]):
        harita: Dict[int, str] = {}
        for c_idx, hucre in enumerate(satir):
            if hucre is None:
                continue
            norm = _baslik_normalize(hucre['text'])
            if norm in _POZ_ANAHTARLAR:
                harita[c_idx] = 'poz'
            elif norm in _ADET_ANAHTARLAR:
                harita[c_idx] = 'adet'
            elif norm in _CAP_ANAHTARLAR:
                harita[c_idx] = 'cap'
            elif norm in _BOY_ANAHTARLAR:
                harita[c_idx] = 'boy'
            elif norm in _SEKIL_ANAHTARLAR:
                harita[c_idx] = 'sekil'

        alanlar = set(harita.values())
        if not {'adet', 'cap', 'boy'}.issubset(alanlar):
            continue
        sayi = len(alanlar)
        if sayi > en_iyi_sayi:
            en_iyi_sayi = sayi
            en_iyi_index = r_idx
            en_iyi_harita = harita

    if en_iyi_index is not None:
        return en_iyi_index, en_iyi_harita
    return None, {}


_GECERLI_MANUEL_ALANLAR = {'poz', 'adet', 'cap', 'boy', 'sekil'}


def grid_den_poz_kayitlarini_cikar(
    grid: List[List[Optional[Dict[str, Any]]]],
    sutun_sirasi: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """AŞAMA 2 çekirdeği: Aşama 1'in ham ızgarasından poz/adet/çap/boy
    kayıtlarını çıkarır.

    Neyi çözüyoruz: Proje brief'indeki karar — "Başlık satırı VARSA otomatik
    sütun eşle; YOKSA kullanıcıya sor". Bu fonksiyon başlığı ADET/ÇAP/BOY
    anahtar kelimeleriyle otomatik bulur; bulamazsa (ve `sutun_sirasi` de
    verilmemişse) hata FIRLATMAZ — "sutun_tespiti": "basarisiz" ile açıkça
    işaretleyip çağırana (ileride: UI'daki "sütun sırası nedir?" diyaloğuna)
    devreder.

    ÇAP-BAZLI TOPLAM sütunlarının (Ø8/Ø12/Ø18) hangi çapa ait olduğu HEADER
    METNİNDEN DEĞİL, veri satırlarındaki ÇAP sütunuyla çapraz korelasyondan
    çıkarılır (bir satırda hangi toplam-sütunu doluysa, o satırın ÇAP değeri
    o sütunun çapıdır) — bu sayede "TOPLAM BOY (m)" gibi çok-sütunlu birleşik
    üst başlıkların ekranda tam nereye oturduğunu bilmeye gerek kalmaz.

    Args:
        grid: tablo_hucrelerini_kumele() çıktısı.
        sutun_sirasi: başlık YOKSA elle verilecek, her sütun için bir alan
            adı listesi ('poz'|'adet'|'cap'|'boy'|'sekil'|'toplam'|'yoksay'),
            uzunluğu grid'in sütun sayısına eşit olmalı.

    Returns:
        {
            "sutun_tespiti": "otomatik" | "manuel" | "basarisiz",
            "baslik_satir_index": Optional[int],
            "sutun_alan_haritasi": {sutun_idx: alan_adi},
            "toplam_kolon_cap_haritasi": {sutun_idx: cap_int veya None},
            "belirsiz_toplam_kolonlari": [sutun_idx, ...],
            "basarili": [{"poz_no","adet","cap","boy","tablo_toplamlari":{cap:deger}}...],
            "atlanan_satir_sayisi": int,
        }

    Nasıl test ederiz: scratchpad/test_poz_donati_baslik_esleme.py — Aşama
    1'in ekran-görüntüsü grid'iyle (başlıklı) otomatik tespit + doğru
    poz/adet/çap/boy/tablo_toplamlari; başlıksız aynı grid + manuel
    sutun_sirasi ile aynı sonuç; başlık da sutun_sirasi de yoksa temiz
    "basarisiz" (crash yok); karışık-çaplı bir toplam sütununun "belirsiz"
    işaretlendiği senaryolar doğrulanır.
    """
    sonuc: Dict[str, Any] = {
        "sutun_tespiti": "basarisiz",
        "baslik_satir_index": None,
        "sutun_alan_haritasi": {},
        "toplam_kolon_cap_haritasi": {},
        "belirsiz_toplam_kolonlari": [],
        "basarili": [],
        "atlanan_satir_sayisi": 0,
    }
    if not grid:
        return sonuc

    sutun_sayisi = len(grid[0])
    baslik_index, alan_haritasi = _baslik_satirini_bul(grid)

    if baslik_index is not None:
        sonuc["sutun_tespiti"] = "otomatik"
        sonuc["baslik_satir_index"] = baslik_index
        sonuc["sutun_alan_haritasi"] = dict(alan_haritasi)
        veri_satirlari = [s for i, s in enumerate(grid) if i != baslik_index]
    elif sutun_sirasi is not None:
        if len(sutun_sirasi) != sutun_sayisi:
            raise ValueError(
                f"sutun_sirasi uzunluğu ({len(sutun_sirasi)}) grid sütun "
                f"sayısıyla ({sutun_sayisi}) uyuşmuyor."
            )
        sonuc["sutun_tespiti"] = "manuel"
        sonuc["sutun_alan_haritasi"] = {
            i: ad for i, ad in enumerate(sutun_sirasi) if ad in _GECERLI_MANUEL_ALANLAR
        }
        veri_satirlari = list(grid)
    else:
        return sonuc  # "basarisiz" — çağıran sutun_sirasi ile tekrar denemeli

    alan_haritasi_final = sonuc["sutun_alan_haritasi"]
    poz_col = next((c for c, a in alan_haritasi_final.items() if a == 'poz'), None)
    adet_col = next((c for c, a in alan_haritasi_final.items() if a == 'adet'), None)
    cap_col = next((c for c, a in alan_haritasi_final.items() if a == 'cap'), None)
    boy_col = next((c for c, a in alan_haritasi_final.items() if a == 'boy'), None)

    toplam_kolonlari = [c for c in range(sutun_sayisi) if c not in alan_haritasi_final]

    # 1. Geçerli veri satırlarını çıkar (adet/çap/boy'un ÜÇÜ de parse edilebilenler)
    gecerli_satirlar = []  # (satir, adet, cap, boy, poz_metin)
    for satir in veri_satirlari:
        adet_ham = satir[adet_col]['text'] if adet_col is not None and satir[adet_col] else None
        cap_ham = satir[cap_col]['text'] if cap_col is not None and satir[cap_col] else None
        boy_ham = satir[boy_col]['text'] if boy_col is not None and satir[boy_col] else None

        adet = _sayi_parse_et(adet_ham)
        cap = cap_normalize_et(cap_ham)
        boy = _sayi_parse_et(boy_ham)

        if adet is None or cap is None or boy is None:
            # Alt-başlık satırı (örn. Ø8/Ø12/Ø18 satırı) ya da boş satır —
            # veri dışı kabul edilip sessizce atlanır (hata DEĞİL).
            sonuc["atlanan_satir_sayisi"] += 1
            continue

        poz_metin = satir[poz_col]['text'] if poz_col is not None and satir[poz_col] else None
        gecerli_satirlar.append((satir, int(adet), cap, boy, poz_metin))

    # 2. Toplam sütunlarının çapını veri korelasyonuyla belirle
    toplam_kolon_cap: Dict[int, Optional[int]] = {}
    belirsiz: List[int] = []
    for col in toplam_kolonlari:
        gorulen_capler = set()
        for satir, _adet, cap, _boy, _poz in gecerli_satirlar:
            if col < len(satir) and satir[col] is not None:
                gorulen_capler.add(cap)
        if len(gorulen_capler) == 1:
            toplam_kolon_cap[col] = next(iter(gorulen_capler))
        else:
            toplam_kolon_cap[col] = None
            if len(gorulen_capler) > 1:
                belirsiz.append(col)

    sonuc["toplam_kolon_cap_haritasi"] = toplam_kolon_cap
    sonuc["belirsiz_toplam_kolonlari"] = belirsiz

    # 3. Başarılı kayıtları oluştur
    for satir, adet, cap, boy, poz_metin in gecerli_satirlar:
        tablo_toplamlari: Dict[Any, float] = {}
        for col in toplam_kolonlari:
            if col < len(satir) and satir[col] is not None:
                deger = _sayi_parse_et(satir[col]['text'])
                if deger is not None:
                    anahtar = toplam_kolon_cap.get(col)
                    tablo_toplamlari[anahtar if anahtar is not None else f"sutun_{col}"] = deger
        sonuc["basarili"].append({
            "poz_no": poz_metin,
            "adet": adet,
            "cap": cap,
            "boy": boy,
            "tablo_toplamlari": tablo_toplamlari,
        })

    return sonuc


# ── AŞAMA 3: Hesap (kg/ton) + tablodaki hazır TOPLAM ile karşılaştırma ──────
# Bu bölüm de SAF — grid_den_poz_kayitlarini_cikar()'ın "basarili" listesi
# üzerinde çalışır, AutoCAD/COM bağımsız test edilebilir.

_CUBUK_BOYU_M = 12.0


def poz_kayitlarindan_hesapla(poz_kayitlari_basarili: List[Dict[str, Any]]) -> Dict[str, Any]:
    """AŞAMA 3 çekirdeği: poz kayıtlarından çap-bazlı kg/ton hesaplar ve
    tablodaki hazır TOPLAM BOY sütunuyla (varsa) karşılaştırır.

    Neyi çözüyoruz: Proje brief'i madde 1 — "Toplam boy sütunu (varsa): OKU
    ve hesaplananla KARŞILAŞTIR. Tutarsa ✓, tutmazsa ⚠️ uyar." Her poz için
    kendi hesapladığımız (adet×boy) ile tablonun o satırdaki hazır TOPLAM
    hücresi karşılaştırılır — bu, tabloyu çizenin/dolduranın bir satırda
    adet/boy/toplamdan birini yanlış girdiği durumları (insan hatası) tespit
    eder; ayrıca DEMIR_AGIRLIK_TABLOSU (TS 708 kg/m) ile çap bazlı toplam
    ağırlık/tonaj çıkarılır.

    Args:
        poz_kayitlari_basarili: grid_den_poz_kayitlarini_cikar()['basarili']

    Returns:
        {
            "cap_ozeti": {cap: {"adet","boy_m","agirlik_kg","cubuk_adet"}},
            "genel": {"adet","boy_m","agirlik_kg"},
            "sapmalar": [{"poz_no","cap","hesaplanan_boy","tablo_boy","fark"}...],
            "sapma_var_mi": bool,
        }

    Nasıl test ederiz: scratchpad/test_poz_donati_hesap.py — ekran
    görüntüsündeki 7 pozun kg/ton'a çevrilmesi elle hesaplanan değerlerle
    karşılaştırılır; kasıtlı bozulmuş bir "tablo_toplamlari" değeriyle
    sapmanın YAKALANDIĞI, ufak (yuvarlama kaynaklı, örn. 0.001) farkların ise
    YANLIŞ ALARM vermediği doğrulanır.
    """
    cap_ozeti: Dict[int, Dict[str, Any]] = {}
    sapmalar: List[Dict[str, Any]] = []

    for kayit in poz_kayitlari_basarili:
        cap = kayit["cap"]
        adet = kayit["adet"]
        boy = kayit["boy"]
        hesaplanan_boy = adet * boy
        agirlik_birim = DEMIR_AGIRLIK_TABLOSU.get(cap, 0.0)
        hesaplanan_agirlik = hesaplanan_boy * agirlik_birim

        if cap not in cap_ozeti:
            cap_ozeti[cap] = {"adet": 0, "boy_m": 0.0, "agirlik_kg": 0.0, "birim_agirlik": agirlik_birim}
        cap_ozeti[cap]["adet"] += adet
        cap_ozeti[cap]["boy_m"] += hesaplanan_boy
        cap_ozeti[cap]["agirlik_kg"] += hesaplanan_agirlik

        tablo_boy = kayit.get("tablo_toplamlari", {}).get(cap)
        if tablo_boy is not None:
            fark = abs(hesaplanan_boy - tablo_boy)
            tolerans = max(0.05, abs(tablo_boy) * 0.005)
            if fark > tolerans:
                sapmalar.append({
                    "poz_no": kayit["poz_no"],
                    "cap": cap,
                    "hesaplanan_boy": round(hesaplanan_boy, 3),
                    "tablo_boy": tablo_boy,
                    "fark": round(fark, 3),
                })

    for cap in cap_ozeti:
        cap_ozeti[cap]["cubuk_adet"] = math.ceil(cap_ozeti[cap]["boy_m"] / _CUBUK_BOYU_M)

    genel = {
        "adet": sum(v["adet"] for v in cap_ozeti.values()),
        "boy_m": sum(v["boy_m"] for v in cap_ozeti.values()),
        "agirlik_kg": sum(v["agirlik_kg"] for v in cap_ozeti.values()),
    }

    return {
        "cap_ozeti": cap_ozeti,
        "genel": genel,
        "sapmalar": sapmalar,
        "sapma_var_mi": len(sapmalar) > 0,
    }


def poz_kayitlarini_demir_bilgisine_cevir(poz_kayitlari_basarili: List[Dict[str, Any]]) -> List["DemirBilgisi"]:
    """Poz kayıtlarını (poz_no/adet/cap/boy) mevcut DemirBilgisi formatına
    çevirir — get_kolon_filizi_from_table/get_rebar_report_from_selection'ın
    döndürdüğü "basarili" listesiyle AYNI TİP, böylece "Demir Metrajı"
    kat akışı (Excel'e aktar, Kesim Listesi'ne aktar) hiç değişmeden bu yeni
    araç için de çalışır.

    Neyi çözüyoruz: Aşama 4'ün UI entegrasyonu, hem başlık otomatik
    bulunduğunda (get_poz_bazli_donati_tablosu içinden) hem de kullanıcı
    manuel sütun sırası girdiğinde (UI'daki "sütun sırası" diyaloğundan
    sonra) AYNI dönüşümü kullanmalı — bu yüzden ayrı, paylaşılan bir
    fonksiyon (kod tekrarı yerine).

    Not: Tablodaki BOY sütunu METRE cinsinden (örn. "5,30"); DemirBilgisi.boy
    alanı ise projede CM konvansiyonuyla kullanılır (Excel export "Boy (cm)"
    başlığı, Kesim Listesi birim="cm" bekler) — burada ×100 ile çevrilir.
    DemirBilgisi.toplam_boy her zaman METRE'dir (proje geneli tutarlı).

    Nasıl test ederiz: scratchpad/test_poz_donati_hesap.py — dönen listenin
    uzunluğu/adet/cap/boy(cm)/toplam_boy(m)/toplam_agirlik değerleri elle
    hesaplananlarla karşılaştırılır.
    """
    demirler: List[DemirBilgisi] = []
    for kayit in poz_kayitlari_basarili:
        boy_cm = kayit["boy"] * 100.0
        toplam_boy_m = kayit["adet"] * kayit["boy"]
        agirlik_birim = DEMIR_AGIRLIK_TABLOSU.get(kayit["cap"], 0.0)
        d = DemirBilgisi(
            handle=f"poz_{kayit['poz_no']}",
            orijinal_metin=f"Poz {kayit['poz_no']}: {kayit['adet']}xØ{kayit['cap']} L={boy_cm:.0f}cm",
        )
        d.adet = kayit["adet"]
        d.cap = kayit["cap"]
        d.boy = boy_cm
        d.toplam_boy = toplam_boy_m
        d.agirlik_birim = agirlik_birim
        d.toplam_agirlik = toplam_boy_m * agirlik_birim
        d.gecerli = True
        d.eleman_tipi = "İstinat Demir Hesabı"
        demirler.append(d)
    return demirler


class AutoCADConnector:
    """
    AutoCAD Canlı Bağlantı Sınıfı
    =============================

    Bilgisayarda açık olan AutoCAD uygulamasına COM üzerinden bağlanır.
    Kullanıcı seçimlerini alır, veri okur ve görsel geri bildirim verir.

    Kullanım:
    ---------
    >>> connector = AutoCADConnector()
    >>> if connector.baglan():
    ...     objeler = connector.kullanici_secimi_al()
    ...     for obj in objeler:
    ...         print(f"{obj.entity_type}: {obj.uzunluk}m")
    ...     connector.secimi_temizle()
    """

    def __init__(self):
        """AutoCADConnector başlatıcısı"""
        self.acad_app = None
        self.aktif_cizim = None
        self.model_space = None
        self.selection_set = None
        self._bagli = False
        self._metraj_alinan_objeler: List[Any] = []
        self._orijinal_renkler: Dict[str, int] = {}

        if not WIN32COM_AVAILABLE:
            raise ImportError(
                "win32com.client modülü bulunamadı.\n"
                "Yüklemek için: pip install pywin32"
            )

    @property
    def bagli(self) -> bool:
        """AutoCAD'e bağlı mı?"""
        return self._bagli and self.acad_app is not None

    def baglan(self) -> bool:
        """
        Çalışan AutoCAD uygulamasına bağlan.

        Returns:
            bool: Bağlantı başarılı ise True

        Raises:
            ConnectionError: AutoCAD bulunamazsa veya bağlantı hatasında
        """
        # COM mesaj filtresi: AutoCAD nesnesi bu thread'de alınıp bu thread'de
        # kullanılıyor (tüm araç döngüleri Qt ana thread'inde) — filtre de
        # burada, AYNI thread'de kaydedilir (Rev-148).
        mesaj_filtresi_kaydet()
        try:
            # Farklı AutoCAD sürümlerini dene
            prog_ids = [
                "AutoCAD.Application.24",  # AutoCAD 2024
                "AutoCAD.Application.25",  # AutoCAD 2025
                "AutoCAD.Application.23",  # AutoCAD 2023
                "AutoCAD.Application.26",  # AutoCAD 2026
                "AutoCAD.Application",     # Genel
            ]

            acad_found = False
            for prog_id in prog_ids:
                try:
                    self.acad_app = win32com.client.GetActiveObject(prog_id)
                    logger.info(f"AutoCAD bulundu: {prog_id}")
                    acad_found = True
                    break
                except com_error:
                    continue

            if not acad_found:
                # Dispatch ile yeni instance dene
                try:
                    self.acad_app = win32com.client.Dispatch("AutoCAD.Application")
                    logger.info("AutoCAD Dispatch ile bağlandı")
                    acad_found = True
                except com_error:
                    pass

            if not acad_found:
                logger.warning("Açık AutoCAD uygulaması bulunamadı!")
                raise ConnectionError(
                    "AutoCAD açık değil veya bağlantı kurulamadı!\n\n"
                    "Çözüm önerileri:\n"
                    "1. AutoCAD'i kapatıp yeniden açın\n"
                    "2. AutoCAD'i YÖNETİCİ OLARAK çalıştırmayın\n"
                    "3. Bu programı YÖNETİCİ OLARAK çalıştırın\n"
                    "4. Bir DWG dosyası açık olduğundan emin olun"
                )

            # Rev-156: AutoCAD kalıcı meşgulse (açık iletişim kutusu) filtre 30 sn,
            # aşağıdaki retry döngüleri de bunu 5'er kez tekrarlıyordu -> dakikalarca
            # donma. Bağlanırken meşgul reddi 3 sn denenir; filtre vazgeçerse hemen açık mesaj.
            self._baglan_bekleme = kisa_bekleme(BAGLANTI_MESGUL_MS)
            self._baglan_bekleme.__enter__()   # dıştaki finally'de MUTLAKA geri alınır
            vazgecme_once = vazgecme_sayisi()

            def _mesgul_ise_dur(e=None):
                kod_red = e is not None and self.RPC_E_CALL_REJECTED in self._com_hata_kodlari(e)
                if kod_red or vazgecme_sayisi() > vazgecme_once:
                    logger.warning(f"[BAGLAN] AutoCAD meşgul — bağlantı durduruldu ({e!r})")
                    raise ConnectionError(AUTOCAD_MESGUL_MESAJI)

            # Uygulama görünür olsun
            try:
                self.acad_app.Visible = True
            except (com_error, AttributeError) as e:
                _mesgul_ise_dur(e)

            # Aktif çizimi al (retry ile - AutoCAD hazır olmayabilir)
            # NOT: pywin32'nin dinamik (late-bound) COM dispatch'i, tip
            # kütüphanesi cache'i (gen_py) güncel AutoCAD sürümüyle uyuşmazsa
            # com_error DEĞİL düz AttributeError ("<unknown>.ActiveDocument"
            # gibi) fırlatabilir — bu ikisi de yakalanmazsa retry hiç
            # denenmeden ilk denemede dışarı sızar (Rev-134 ek düzeltme).
            self.aktif_cizim = None
            for deneme in range(5):
                try:
                    self.aktif_cizim = self.acad_app.ActiveDocument
                    if self.aktif_cizim is not None:
                        break
                except (com_error, AttributeError) as e:
                    _mesgul_ise_dur(e)
                    time.sleep(0.5)

            if self.aktif_cizim is None:
                raise ConnectionError(
                    "AutoCAD'de açık bir çizim yok!\n"
                    "Lütfen bir DWG dosyası açın."
                )

            # Model Space'i al (retry ile - COM bazen gecikmeli yanıt verir)
            self.model_space = None
            for deneme in range(5):
                try:
                    self.model_space = self.aktif_cizim.ModelSpace
                    if self.model_space is not None:
                        break
                except (com_error, AttributeError) as e:
                    _mesgul_ise_dur(e)
                    time.sleep(0.5)
                    # Late-binding sorunu olabilir, Dispatch ile tekrar dene
                    try:
                        self.aktif_cizim = win32com.client.Dispatch(
                            self.acad_app.ActiveDocument
                        )
                        self.model_space = self.aktif_cizim.ModelSpace
                        if self.model_space is not None:
                            break
                    except (com_error, AttributeError) as e2:
                        _mesgul_ise_dur(e2)

            if self.model_space is None:
                raise ConnectionError(
                    "AutoCAD ModelSpace'e erişilemiyor!\n\n"
                    "Çözüm önerileri:\n"
                    "1. AutoCAD'de bir DWG dosyası açık olduğundan emin olun\n"
                    "2. AutoCAD'i kapatıp yeniden açın\n"
                    "3. Bu programı ve AutoCAD'i aynı yetki seviyesinde çalıştırın"
                )

            # Bağlantı bilgilerini logla
            try:
                cizim_adi = self.aktif_cizim.Name
                cizim_yolu = self.aktif_cizim.FullName
            except (com_error, AttributeError) as e:
                _mesgul_ise_dur(e)
                raise

            logger.info(f"AutoCAD bağlantısı başarılı!")
            logger.info(f"  Çizim Adı: {cizim_adi}")
            logger.info(f"  Tam Yol: {cizim_yolu}")

            print(f"\n{'='*50}")
            print(f"  AutoCAD BAĞLANTISI BAŞARILI")
            print(f"{'='*50}")
            print(f"  Çizim: {cizim_adi}")
            print(f"  Yol: {cizim_yolu}")
            print(f"{'='*50}\n")

            self._bagli = True
            return True

        except com_error as e:
            logger.error(f"AutoCAD COM hatası: {e}")
            self._bagli = False
            raise ConnectionError(f"AutoCAD ile iletişim hatası: {e}")
        except Exception as e:
            logger.error(f"Bağlantı hatası: {e}")
            self._bagli = False
            raise
        finally:
            # Kısa meşgul beklemesini HER durumda geri al — kalırsa araç döngüleri 30 sn yerine 3 sn dener
            ctx = getattr(self, "_baglan_bekleme", None)
            if ctx is not None:
                self._baglan_bekleme = None
                ctx.__exit__(None, None, None)

    def _autocad_one_getir_hafif(self):
        """AutoCAD'i öne getirir — WindowState'i SADECE simge durumundaysa
        değiştirir, sabit bekleme yok (Rev-137 takılma düzeltmesi).

        Neyi çözüyoruz? Tam sürüm (_autocad_one_getir) her çağrıda
        WindowState'i acNorm->acMax arasında değiştirip ~1.1 sn sabit bekliyor
        (log: 1.7 sn/çağrı). Pencere zaten açıkken bu gereksiz yeniden
        boyutlandırma + yeniden çizim yaptırıyor ve AutoCAD'i meşgul edip
        sonraki COM çağrılarının reddedilmesine yol açıyordu. Diğer araçlar
        tam sürümü kullanmaya devam eder (davranışları değişmez).
        Nasıl test ederiz? scratchpad/test_temel_kirisi_com.py — sahte
        acad_app ile: maximize penceresinde WindowState'e DOKUNULMAZ,
        simge durumunda acMax yapılır.
        """
        if not self.bagli:
            return
        try:
            if not self._mesgul_retry(lambda: self.acad_app.Visible, "Visible"):
                self.acad_app.Visible = True
        except Exception as e:
            self._tk_hata("_autocad_one_getir_hafif/Visible", e)
        try:
            durum = self._mesgul_retry(lambda: self.acad_app.WindowState, "WindowState")
            if durum == 2:  # acMin — sadece simge durumundaysa geri aç
                self.acad_app.WindowState = 3
                time.sleep(0.2)
        except Exception as e:
            self._tk_hata("_autocad_one_getir_hafif/WindowState", e)
        if self.aktif_cizim:
            try:
                self._mesgul_retry(lambda: self.aktif_cizim.Activate(), "Activate")
            except Exception as e:
                self._tk_hata("_autocad_one_getir_hafif/Activate", e)
        if WIN32GUI_AVAILABLE:
            self._win32_pencere_one_getir()

    def _mesgul_retry(self, func, ad: str, max_deneme: int = 8, bekleme: float = 0.15):
        """AutoCAD meşgulken reddedilen COM çağrısını tekrar dener.

        Neyi çözüyoruz? pywin32 dinamik dispatch, metot/özellik ADINI
        çözümlerken (GetIDsOfNames) AutoCAD çağrıyı reddederse (pencere öne
        gelirken/yeniden çizerken) com_error'ı YUTUP düz AttributeError
        fırlatır: "Add.SelectOnScreen" ("Add" = nesnenin elde edildiği
        metodun adı; nesne DOĞRU selection set'tir). _com_retry sadece
        com_error'ı yeniden denediği için bu hata ilk denemede kaçıyordu
        (bkz. CLAUDE.md 2026-09-06 "<unknown>.ModelSpace" aynı aile).
        UYARI: AttributeError'ı yeniden denemek SADECE özelliğin kesin var
        olduğu çağrılarda güvenli (SelectOnScreen, Add, Count, Item,
        ObjectName, Handle, çizgide Length) — gerçekten olmayan bir özellikte
        (örn. LINE.TextString) boşuna bekletir, orada kullanma.
        Nasıl test ederiz? test_temel_kirisi_com.py: ilk 2 denemede
        AttributeError, 3.'de başarı.
        """
        for deneme in range(max_deneme):
            try:
                sonuc = func()
                if deneme > 0:
                    logger.warning(f"[MESGUL_RETRY] {ad}: {deneme + 1}. denemede BAŞARILI")
                return sonuc
            except AttributeError as e:
                hata = e
            except com_error as e:
                if e.hresult != -2147418111:  # RPC_E_CALL_REJECTED değilse gerçek hata
                    raise
                hata = e
            if deneme == max_deneme - 1:
                logger.error(f"[MESGUL_RETRY] {ad}: {max_deneme} denemede vazgeçildi: {hata!r}")
                raise hata
            logger.warning(
                f"[MESGUL_RETRY] {ad}: deneme {deneme + 1}/{max_deneme} AutoCAD meşgul "
                f"({type(hata).__name__}: {hata}), {bekleme * (deneme + 1):.2f} sn bekleniyor"
            )
            time.sleep(bekleme * (deneme + 1))

    def _autocad_one_getir(self):
        """AutoCAD penceresini görünür yap ve öne getir."""
        if not self.bagli:
            return

        max_deneme = 3
        for deneme in range(max_deneme):
            try:
                # 1. COM üzerinden görünür yap
                self.acad_app.Visible = True
                time.sleep(0.3)

                # 2. Pencere durumunu ayarla
                try:
                    self.acad_app.WindowState = 1  # acNorm
                    time.sleep(0.2)
                    self.acad_app.WindowState = 3  # acMax
                except BaseException as e:
                    self._tk_hata("_autocad_one_getir/WindowState", e)

                time.sleep(0.3)

                # 3. Aktif çizimi aktifleştir
                if self.aktif_cizim:
                    try:
                        self.aktif_cizim.Activate()
                    except BaseException as e:
                        self._tk_hata("_autocad_one_getir/Activate", e)

                # 4. win32gui ile pencereyi öne getir
                if WIN32GUI_AVAILABLE:
                    self._win32_pencere_one_getir()

                # 5. Görünürlüğü doğrula
                time.sleep(0.3)
                try:
                    gorunur = self.acad_app.Visible
                    if gorunur:
                        logger.debug(f"AutoCAD penceresi öne getirildi (deneme {deneme + 1})")
                        return
                except BaseException as e:
                    self._tk_hata("_autocad_one_getir/Visible oku", e)

                # Görünür değilse - SendCommand ile REGEN dene
                if deneme < max_deneme - 1:
                    logger.debug(f"AutoCAD hâlâ görünür değil, tekrar deneniyor ({deneme + 1}/{max_deneme})")
                    try:
                        self.aktif_cizim.SendCommand("(command \"REGEN\") ")
                    except BaseException as e:
                        self._tk_hata("_autocad_one_getir/SendCommand REGEN", e)
                    time.sleep(0.5)

            except Exception as e:
                self._tk_hata(f"_autocad_one_getir deneme {deneme + 1}/{max_deneme}", e)
                if deneme < max_deneme - 1:
                    logger.debug(f"AutoCAD öne getirme denemesi {deneme + 1} başarısız: {e}")
                    time.sleep(0.5)
                else:
                    logger.warning(f"AutoCAD öne getirilemedi ({max_deneme} deneme): {e}")

    def _win32_pencere_one_getir(self):
        """win32gui ile AutoCAD penceresini bulup öne getirir."""
        def callback(hwnd, windows):
            try:
                title = win32gui.GetWindowText(hwnd)
                if "AutoCAD" in title and win32gui.IsWindow(hwnd):
                    windows.append(hwnd)
            except:
                pass
            return True

        windows = []
        try:
            win32gui.EnumWindows(callback, windows)
        except BaseException as e:
            self._tk_hata("_win32_pencere_one_getir/EnumWindows", e)
            return

        for hwnd in windows:
            try:
                # Minimize durumunu kontrol et
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.3)
                else:
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                    time.sleep(0.1)

                # Öne getir - AllowSetForegroundWindow trick
                try:
                    import ctypes
                    ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
                except BaseException as e:
                    self._tk_hata("_win32_pencere_one_getir/AllowSetForegroundWindow", e)

                try:
                    win32gui.SetForegroundWindow(hwnd)
                except BaseException as e:
                    self._tk_hata("_win32_pencere_one_getir/SetForegroundWindow", e)
                    try:
                        win32gui.BringWindowToTop(hwnd)
                    except BaseException as e2:
                        self._tk_hata("_win32_pencere_one_getir/BringWindowToTop", e2)
                break
            except BaseException as e:
                self._tk_hata(f"_win32_pencere_one_getir(hwnd={hwnd})", e)

    def _com_retry(self, func, max_deneme=5, bekleme=0.1):
        """COM çağrısını RPC_E_CALL_REJECTED hatasına karşı korumalı çağırır.

        AutoCAD meşgulken (özellikle büyük seçimlerde) COM çağrıları
        reddedilebilir. Bu metot otomatik retry ile bu sorunu aşar.
        """
        for deneme in range(max_deneme):
            try:
                sonuc = func()
                if deneme > 0:
                    logger.warning(f"[COM_RETRY] {deneme + 1}. denemede BAŞARILI")
                return sonuc
            except com_error as e:
                # -2147418111 = 0x80010001 = RPC_E_CALL_REJECTED
                if e.hresult == -2147418111 and deneme < max_deneme - 1:
                    logger.warning(
                        f"[COM_RETRY] deneme {deneme + 1}/{max_deneme} RPC_E_CALL_REJECTED "
                        f"(AutoCAD meşgul), {bekleme * (deneme + 1):.2f} sn bekleniyor: {e}"
                    )
                    time.sleep(bekleme * (deneme + 1))
                else:
                    if self._tk_aktif():
                        logger.error(
                            f"[COM_RETRY] deneme {deneme + 1}/{max_deneme} vazgeçildi, "
                            f"hresult={e.hresult}: {e}", exc_info=True
                        )
                    raise
            except Exception as e:
                # Davranış aynı (retry yok, yukarı fırlar) — sadece teşhis logu
                if self._tk_aktif():
                    logger.error(
                        f"[COM_RETRY] deneme {deneme + 1}/{max_deneme} com_error DIŞI hata "
                        f"(retry yapılmaz): {type(e).__name__}: {e}", exc_info=True
                    )
                raise

    def _guvenli_select_on_screen(self, selection_set, max_deneme=2):
        """SelectOnScreen'i 'invisible' hatasına karşı korumalı çağırır.

        AutoCAD penceresi görünür değilse tekrar öne getirmeyi dener.
        """
        for deneme in range(max_deneme):
            try:
                # Rev-137: AutoCAD meşgulken isim çözümlemesi reddedilince
                # pywin32 "Add.SelectOnScreen" AttributeError'ı fırlatır —
                # SelectOnScreen her selection set'te VAR, retry güvenli.
                self._mesgul_retry(lambda: selection_set.SelectOnScreen(), "SelectOnScreen")
                return  # Başarılı
            except com_error as e:
                self._tk_hata(f"_guvenli_select_on_screen deneme {deneme + 1}/{max_deneme}", e)
                hata_str = str(e).lower()
                if "invisible" in hata_str and deneme < max_deneme - 1:
                    logger.warning(f"AutoCAD penceresi görünür değil, tekrar öne getiriliyor (deneme {deneme + 1})")
                    print(">>> AutoCAD penceresi görünür değil, öne getiriliyor...")
                    time.sleep(0.5)
                    self._autocad_one_getir()
                    time.sleep(0.5)
                else:
                    raise  # invisible değilse veya son denemeyse hatayı fırlat

    def baglantıyi_kes(self):
        """AutoCAD bağlantısını sonlandır ve kaynakları temizle."""
        try:
            # Renkleri geri al
            self.renkleri_geri_al()

            # Selection set'i temizle
            if self.selection_set:
                try:
                    self.selection_set.Delete()
                except:
                    pass
            self.selection_set = None

            self.acad_app = None
            self.aktif_cizim = None
            self.model_space = None
            self._bagli = False

            logger.info("AutoCAD bağlantısı sonlandırıldı.")

        except Exception as e:
            logger.warning(f"Bağlantı kapatılırken hata: {e}")

    def kullanici_secimi_al(self, mesaj: str = "Metraj alınacak objeleri seçin") -> List[MetrajObjesi]:
        """
        AutoCAD ekranında kullanıcıdan obje seçimi iste.

        Args:
            mesaj: Kullanıcıya gösterilecek bilgi mesajı

        Returns:
            List[MetrajObjesi]: Seçilen objelerin metraj bilgileri
        """
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

        try:
            # AutoCAD penceresini görünür yap ve öne getir
            self._autocad_one_getir()

            # Önceki selection set'i temizle
            self._selection_set_temizle()

            # Yeni selection set oluştur
            ss_adi = f"MetrajSecim_{id(self)}"

            # Var olan aynı isimli set'i sil
            try:
                existing = self.aktif_cizim.SelectionSets.Item(ss_adi)
                existing.Delete()
            except:
                pass

            self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

            # Kullanıcıya bilgi ver
            print(f"\n>>> {mesaj}")
            print(">>> AutoCAD penceresine geçin ve objeleri seçin...")
            print(">>> Seçimi tamamlamak için ENTER tuşuna basın.\n")

            # Kullanıcı seçimi (SelectOnScreen) - invisible hatasına karşı korumalı
            # Not: Bu çağrı, kullanıcı ENTER'a basana kadar bekler
            self._guvenli_select_on_screen(self.selection_set)

            # Seçilen objeleri işle
            secilen_objeler = []
            secim_sayisi = self.selection_set.Count

            if secim_sayisi == 0:
                print(">>> Hiç obje seçilmedi.")
                return []

            print(f"\n>>> {secim_sayisi} obje seçildi. İşleniyor...")

            for i in range(secim_sayisi):
                entity = self.selection_set.Item(i)
                metraj_obj = self._obje_verisi_oku(entity)
                if metraj_obj:
                    secilen_objeler.append(metraj_obj)
                    # Görsel teyit: Yeşile boya
                    self._objeyi_renklendir(entity, AcadColor.GREEN)

            # Ekranı güncelle
            self.aktif_cizim.Regen(1)  # acActiveViewport = 1

            print(f">>> {len(secilen_objeler)} objenin metrajı alındı ve YEŞİL ile işaretlendi.\n")

            return secilen_objeler

        except com_error as e:
            if "canceled" in str(e).lower() or "esc" in str(e).lower():
                print(">>> Seçim iptal edildi (ESC).")
                return []
            logger.error(f"Seçim hatası: {e}")
            raise
        except Exception as e:
            logger.error(f"Kullanıcı seçimi alınırken hata: {e}")
            raise

    def _obje_verisi_oku(self, entity) -> Optional[MetrajObjesi]:
        """
        Tek bir AutoCAD objesinin verilerini oku.

        Args:
            entity: AutoCAD entity objesi

        Returns:
            MetrajObjesi veya None
        """
        try:
            entity_type = entity.ObjectName
            layer = entity.Layer
            handle = entity.Handle

            metraj = MetrajObjesi(
                entity_type=entity_type,
                layer=layer,
                handle=handle,
                orijinal_renk=entity.Color
            )

            # Entity tipine göre özel verileri oku

            # LINE
            if entity_type == AcadEntityType.LINE:
                metraj.uzunluk = entity.Length
                start = entity.StartPoint
                end = entity.EndPoint
                metraj.koordinatlar = [
                    (start[0], start[1]),
                    (end[0], end[1])
                ]
                metraj.ozellikler["start"] = start
                metraj.ozellikler["end"] = end

            # POLYLINE / LWPOLYLINE
            elif entity_type in [AcadEntityType.POLYLINE, AcadEntityType.LWPOLYLINE,
                                  AcadEntityType.POLYLINE_2D, AcadEntityType.POLYLINE_3D,
                                  "AcDbPolyline"]:
                metraj.uzunluk = entity.Length
                try:
                    metraj.alan = entity.Area
                except:
                    metraj.alan = 0.0
                metraj.cevre = entity.Length
                try:
                    metraj.ozellikler["closed"] = entity.Closed
                except:
                    pass
                # Koordinatları al
                try:
                    coords = entity.Coordinates
                    # Koordinatlar düz liste olarak gelir: [x1, y1, x2, y2, ...]
                    points = []
                    for j in range(0, len(coords), 2):
                        points.append((coords[j], coords[j + 1]))
                    metraj.koordinatlar = points
                except:
                    pass

            # CIRCLE
            elif entity_type == AcadEntityType.CIRCLE:
                import math
                radius = entity.Radius
                metraj.alan = math.pi * radius ** 2
                metraj.cevre = 2 * math.pi * radius
                metraj.ozellikler["radius"] = radius
                center = entity.Center
                metraj.koordinatlar = [(center[0], center[1])]

            # ARC
            elif entity_type == AcadEntityType.ARC:
                metraj.uzunluk = entity.ArcLength
                metraj.ozellikler["radius"] = entity.Radius
                metraj.ozellikler["start_angle"] = entity.StartAngle
                metraj.ozellikler["end_angle"] = entity.EndAngle

            # TEXT
            elif entity_type == AcadEntityType.TEXT:
                metraj.text_icerigi = entity.TextString
                pos = entity.InsertionPoint
                metraj.koordinatlar = [(pos[0], pos[1])]
                metraj.ozellikler["height"] = entity.Height
                metraj.ozellikler["rotation"] = entity.Rotation

            # MTEXT
            elif entity_type == AcadEntityType.MTEXT:
                metraj.text_icerigi = entity.TextString
                pos = entity.InsertionPoint
                metraj.koordinatlar = [(pos[0], pos[1])]
                try:
                    metraj.ozellikler["width"] = entity.Width
                    metraj.ozellikler["height"] = entity.Height
                except:
                    pass

            # BLOCK REFERENCE (INSERT)
            elif entity_type == AcadEntityType.BLOCK_REF:
                try:
                    metraj.blok_adi = entity.EffectiveName
                except:
                    metraj.blok_adi = entity.Name
                pos = entity.InsertionPoint
                metraj.koordinatlar = [(pos[0], pos[1])]
                metraj.ozellikler["rotation"] = entity.Rotation
                metraj.ozellikler["x_scale"] = entity.XScaleFactor
                metraj.ozellikler["y_scale"] = entity.YScaleFactor
                # Blok attribute'larını oku
                try:
                    if entity.HasAttributes:
                        attrs = {}
                        for attr in entity.GetAttributes():
                            attrs[attr.TagString] = attr.TextString
                        metraj.ozellikler["attributes"] = attrs
                except:
                    pass

            # HATCH
            elif entity_type == AcadEntityType.HATCH:
                try:
                    metraj.alan = entity.Area
                except:
                    pass
                metraj.ozellikler["pattern_name"] = entity.PatternName

            # SPLINE
            elif entity_type == AcadEntityType.SPLINE:
                try:
                    # Spline uzunluğu için yaklaşık hesap
                    metraj.uzunluk = entity.Length if hasattr(entity, 'Length') else 0.0
                except:
                    pass

            # Diğer tipler için temel bilgiler
            else:
                logger.debug(f"Bilinmeyen entity tipi: {entity_type}")

            return metraj

        except Exception as e:
            logger.warning(f"Obje verisi okunurken hata (Handle: {entity.Handle}): {e}")
            return None

    def _guvenli_text_oku(self, entity) -> Optional[str]:
        """
        COM objesinden TextString'i güvenli şekilde oku.

        Bazı objeler (dimension alt-objeleri, proxy, bayat referans)
        TextString özelliğine erişim vermeyebilir.

        Returns:
            str veya None (okunamazsa)
        """
        # Yöntem 1: Doğrudan TextString
        try:
            text = entity.TextString
            if text is not None:
                return str(text)
        except Exception as e:
            self._tk_hata("_guvenli_text_oku/Yöntem1 TextString", e)

        # Yöntem 2: Objeyi handle ile yeniden al ve dene
        try:
            handle = entity.Handle
            yeni_entity = self.aktif_cizim.HandleToObject(handle)
            text = yeni_entity.TextString
            if text is not None:
                return str(text)
        except Exception as e:
            self._tk_hata("_guvenli_text_oku/Yöntem2 HandleToObject.TextString", e)

        return None

    def _read_entity_props(self, entity) -> Optional[Dict[str, Any]]:
        """
        Bir entity'den tüm gerekli özellikleri TEK SEFERDE okur ve cache'ler.
        Böylece aynı özellik tekrar COM'dan çekilmez.
        RPC_E_CALL_REJECTED hatalarına karşı retry mekanizması içerir.

        Returns:
            Dict veya None (ObjectName okunamazsa)
        """
        try:
            obj_name = self._com_retry(lambda: entity.ObjectName)
        except Exception as e:
            self._tk_hata("_read_entity_props/ObjectName", e)
            return None

        # TEXT/MTEXT değilse: Handle/Layer/Color okumadan erken dön.
        # Bazı AutoCAD sürümleri "TEXT"/"MTEXT" kısa isim döndürebilir.
        _TEXT_NAMES = {"AcDbText", "AcDbMText", "TEXT", "MTEXT"}
        if obj_name not in _TEXT_NAMES:
            # Duck-typing: TextString varsa yine de tam oku
            try:
                ts = self._com_retry(lambda: entity.TextString)
                if ts is None:
                    raise AttributeError
            except Exception as e:
                self._tk_hata(
                    f"_read_entity_props/TextString ({obj_name} yazı değil — BEKLENEN)", e)
                return {
                    'entity': entity,
                    'object_name': obj_name,
                    'handle': None,
                    'text': None,
                    'layer': '',
                    'color': 256,
                }

        handle = None
        try:
            handle = self._com_retry(lambda: entity.Handle)
        except Exception as e:
            self._tk_hata("_read_entity_props/Handle", e)

        text = None
        try:
            t = self._com_retry(lambda: entity.TextString)
            if t is not None:
                text = str(t)
        except Exception as e:
            self._tk_hata("_read_entity_props/TextString", e)
            text = self._guvenli_text_oku(entity)

        layer = ""
        try:
            layer = self._com_retry(lambda: entity.Layer)
        except Exception as e:
            self._tk_hata("_read_entity_props/Layer", e)

        color = 256
        try:
            color = self._com_retry(lambda: entity.Color)
        except Exception as e:
            self._tk_hata("_read_entity_props/Color", e)

        return {
            'entity': entity,
            'object_name': obj_name,
            'handle': handle,
            'text': text,
            'layer': layer,
            'color': color,
        }

    def _read_entity_with_coords(self, entity) -> Optional[Dict[str, Any]]:
        """
        Entity özelliklerini koordinatlarıyla birlikte oku.
        Tablo yapılarını parse etmek için X,Y pozisyonu gerekli.

        Koordinat okuma stratejisi:
            1. GetBoundingBox (en güvenilir - her zaman görsel pozisyonu verir)
            2. TextAlignmentPoint (ortalı/sağa yaslı TEXT'ler için)
            3. InsertionPoint (sola yaslı TEXT'ler için)
        """
        props = self._read_entity_props(entity)
        if props is not None and props['object_name'] in ["AcDbText", "AcDbMText"]:
            x, y = None, None

            # Yöntem 1: GetBoundingBox (en güvenilir)
            try:
                result = self._com_retry(lambda: entity.GetBoundingBox())
                if result and len(result) == 2:
                    min_pt, max_pt = result
                    x = (min_pt[0] + max_pt[0]) / 2.0  # merkez X
                    y = (min_pt[1] + max_pt[1]) / 2.0  # merkez Y
            except Exception:
                pass

            # Yöntem 2: TextAlignmentPoint (ortalı/sağa yaslı metinler)
            if x is None:
                try:
                    pos = self._com_retry(lambda: entity.TextAlignmentPoint)
                    if pos and (abs(pos[0]) > 0.01 or abs(pos[1]) > 0.01):
                        x, y = pos[0], pos[1]
                except Exception:
                    pass

            # Yöntem 3: InsertionPoint (fallback)
            if x is None:
                try:
                    pos = self._com_retry(lambda: entity.InsertionPoint)
                    x, y = pos[0], pos[1]
                except Exception:
                    logger.debug(f"Koordinat okunamadı, obje atlanıyor: {props.get('text', '?')}")
                    return None

            props['x'] = x
            props['y'] = y
            return props

    def _objeyi_renklendir(self, entity, renk: AcadColor):
        """
        Bir objenin rengini değiştir ve orijinal rengi kaydet.

        Args:
            entity: AutoCAD entity objesi
            renk: Yeni renk (AcadColor enum değeri)
        """
        try:
            # Handle alınabiliyorsa orijinal rengi kaydet
            try:
                handle = entity.Handle
                if handle not in self._orijinal_renkler:
                    self._orijinal_renkler[handle] = entity.Color
            except Exception as e:
                self._tk_hata("_objeyi_renklendir/Handle-Color oku", e)
                # Handle alınamasa da renklendirmeye devam et

            # Katman kilidini kontrol et ve geçici olarak aç
            layer_obj = None
            layer_was_locked = False
            try:
                layer_obj = self.aktif_cizim.Layers.Item(entity.Layer)
                if layer_obj.Lock:
                    layer_was_locked = True
                    layer_obj.Lock = False
            except Exception as e:
                self._tk_hata("_objeyi_renklendir/katman kilidi", e)

            try:
                # Yeni rengi uygula
                entity.Color = int(renk)
            finally:
                # Katman kilidini geri yükle
                if layer_was_locked and layer_obj is not None:
                    try:
                        layer_obj.Lock = True
                    except Exception as e:
                        self._tk_hata("_objeyi_renklendir/katman kilidi geri", e)

            # Metrajı alınan objeler listesine ekle
            self._metraj_alinan_objeler.append(entity)

        except Exception as e:
            self._tk_hata("_objeyi_renklendir", e)
            logger.debug(f"Obje renklendirilemedi (atlanıyor): {e}")

    def _objeyi_renklendir_cached(self, entity, renk: AcadColor,
                                   handle: str = None,
                                   original_color: int = None):
        """
        Optimizeli renklendirme - önceden okunan handle/color değerlerini kullanır.
        Optimistik yaklaşım: önce Color yaz, başarısız olursa layer kilidi çöz.
        """
        try:
            # Orijinal rengi kaydet (cache'ten, COM çağrısı yok)
            if handle is not None:
                if handle not in self._orijinal_renkler:
                    self._orijinal_renkler[handle] = original_color if original_color is not None else 256
            else:
                try:
                    h = entity.Handle
                    if h not in self._orijinal_renkler:
                        self._orijinal_renkler[h] = entity.Color
                except Exception:
                    pass

            # Optimistik: Doğrudan renk yaz (1 COM çağrısı, retry korumalı)
            try:
                self._com_retry(lambda: setattr(entity, 'Color', int(renk)))
            except Exception:
                # Başarısız → muhtemelen kilitli katman, şimdi çöz
                try:
                    layer_name = self._com_retry(lambda: entity.Layer)
                    layer_obj = self._com_retry(lambda: self.aktif_cizim.Layers.Item(layer_name))
                    if layer_obj.Lock:
                        layer_obj.Lock = False
                        try:
                            self._com_retry(lambda: setattr(entity, 'Color', int(renk)))
                        finally:
                            try:
                                layer_obj.Lock = True
                            except Exception:
                                pass
                except Exception:
                    pass

            self._metraj_alinan_objeler.append(entity)

        except Exception as e:
            logger.debug(f"Obje renklendirilemedi (atlanıyor): {e}")

    def objeleri_hatali_isaretle(self, handle_listesi: List[str]):
        """
        Belirtilen handle'lara sahip objeleri KIRMIZI ile işaretle.

        Args:
            handle_listesi: İşaretlenecek objelerin handle değerleri
        """
        if not self.bagli:
            return

        try:
            for handle in handle_listesi:
                try:
                    entity = self.aktif_cizim.HandleToObject(handle)
                    self._objeyi_renklendir(entity, AcadColor.RED)
                except Exception:
                    pass

            self.aktif_cizim.Regen(1)

        except Exception as e:
            logger.warning(f"Hatalı işaretleme sırasında hata: {e}")

    def renkleri_geri_al(self):
        """Tüm değiştirilen renkleri orijinal hallerine döndür."""
        if not self.bagli or not self._orijinal_renkler:
            return

        try:
            for handle, orijinal_renk in self._orijinal_renkler.items():
                try:
                    entity = self.aktif_cizim.HandleToObject(handle)
                    entity.Color = orijinal_renk
                except Exception:
                    pass

            self._orijinal_renkler.clear()
            self._metraj_alinan_objeler.clear()

            self.aktif_cizim.Regen(1)
            logger.info("Tüm obje renkleri geri alındı.")

        except Exception as e:
            logger.warning(f"Renkler geri alınırken hata: {e}")

    def _selection_set_temizle(self):
        """Mevcut selection set'i temizle."""
        if self.selection_set:
            try:
                self.selection_set.Clear()
            except Exception as e:
                self._tk_hata("_selection_set_temizle/Clear", e)

    def katman_listesi_al(self) -> List[str]:
        """Çizimdeki tüm katman isimlerini döndür."""
        if not self.bagli:
            return []

        try:
            katmanlar = []
            for layer in self.aktif_cizim.Layers:
                katmanlar.append(layer.Name)
            return sorted(katmanlar)
        except Exception as e:
            logger.warning(f"Katman listesi alınamadı: {e}")
            return []

    def blok_listesi_al(self) -> List[str]:
        """Çizimdeki tüm blok isimlerini döndür."""
        if not self.bagli:
            return []

        try:
            bloklar = []
            for block in self.aktif_cizim.Blocks:
                name = block.Name
                # Sistem bloklarını atla
                if not name.startswith("*"):
                    bloklar.append(name)
            return sorted(bloklar)
        except Exception as e:
            logger.warning(f"Blok listesi alınamadı: {e}")
            return []

    def polyline_cizdir(self, mesaj: str = "Polyline çizin", kapat: bool = True) -> Dict[str, Any]:
        """
        AutoCAD'in yerleşik PLINE komutunu başlatarak kullanıcıya polyline çizdirir.
        AutoCAD'deki gibi tam çizim deneyimi sunar (rubber-band çizgi, snap, ortho vb.).

        Args:
            mesaj: Kullanıcıya gösterilecek bilgi mesajı
            kapat: True → polyline kapatılır (alan hesabı için)
                   False → açık kalır (duvar uzunluk ölçümü için)

        Returns:
            Dict:
                uzunluk: float (çizilen polyline'ın AÇIK uzunluğu - kapatma segmenti hariç)
                alan: float (kapalı polyline alanı, kapat=False ise 0)
                cevre: float (kapalı polyline çevresi, kapat=False ise = uzunluk)
                nokta_sayisi: int (tıklanan nokta adedi)
                handle: str (oluşturulan polyline'ın handle'ı)
                iptal: bool (True ise kullanıcı iptal etti)
        """
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil!")

        self._autocad_one_getir()

        doc = self.aktif_cizim
        ms = doc.ModelSpace

        # ── 1) Mevcut obje sayısını kaydet ──
        count_before = ms.Count

        # ── 2) Aktif komut varsa iptal et ──
        try:
            doc.SendCommand("\x1b\x1b")  # ESC ESC
            time.sleep(0.2)
        except Exception:
            pass

        # ── 3) AutoCAD'in yerleşik PLINE komutunu başlat ──
        # _PLINE = dil-bağımsız komut adı (İngilizce, Türkçe fark etmez)
        # SendCommand senkron çalışır → kullanıcı çizimi bitirene kadar bekler
        _iptal_sonuc = {
            "uzunluk": 0.0, "alan": 0.0, "cevre": 0.0,
            "nokta_sayisi": 0, "handle": "", "iptal": True
        }

        try:
            logger.info(f"PLINE komutu başlatılıyor: {mesaj}")
            doc.SendCommand("_PLINE\n")
        except Exception as e:
            logger.error(f"PLINE komutu başlatılamadı: {e}")
            return _iptal_sonuc

        # ── 4) Komut bitti → yeni obje var mı kontrol et ──
        time.sleep(0.1)
        count_after = ms.Count

        if count_after <= count_before:
            logger.info("PLINE: Kullanıcı iptal etti, yeni obje yok")
            return _iptal_sonuc

        # ── 5) Son eklenen objeyi al ──
        try:
            pline = ms.Item(count_after - 1)
            obj_name = pline.ObjectName

            if "Polyline" not in obj_name:
                logger.warning(f"PLINE: Son obje polyline değil: {obj_name}")
                return _iptal_sonuc
        except Exception as e:
            logger.error(f"PLINE: Son obje alınamadı: {e}")
            return _iptal_sonuc

        # ── 6) Önce AÇIK uzunluğu ölç (kapatma segmenti hariç) ──
        uzunluk = pline.Length

        # ── 7) Gerekirse kapat ──
        if kapat:
            try:
                pline.Closed = True
            except Exception:
                pass  # Zaten kapalı olabilir (kullanıcı C ile kapatmışsa)

        # Yeşile boya
        pline.Color = int(AcadColor.GREEN)
        pline.Update()

        handle = pline.Handle
        self._orijinal_renkler[handle] = 256  # ByLayer

        # Nokta sayısını hesapla
        try:
            coords = pline.Coordinates
            nokta_sayisi = len(coords) // 2
        except Exception:
            nokta_sayisi = 0

        # Alan ve çevre (kapatıldıysa)
        if kapat:
            alan = pline.Area
            cevre = pline.Length  # kapalı çevre
        else:
            alan = 0.0
            cevre = uzunluk  # açık uzunluk

        doc.Regen(1)

        logger.info(
            f"PLINE tamamlandı: {nokta_sayisi} nokta, kapat={kapat}, "
            f"Uzunluk={uzunluk:.4f}, Alan={alan:.4f}, Çevre={cevre:.4f}"
        )

        return {
            "uzunluk": uzunluk,
            "alan": alan,
            "cevre": cevre,
            "nokta_sayisi": nokta_sayisi,
            "handle": handle,
            "iptal": False,
        }

    def blok_sayimi_al(self, mesaj: str = "Sayılacak blokları seçin") -> Dict[str, Any]:
        """
        Kullanıcıdan blok seçimi al ve blok isimlerine göre adet say.

        Returns:
            Dict: bloklar (isim->adet), toplam_adet, obje_sayisi
        """
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil!")

        objeler = self.kullanici_secimi_al(mesaj)

        blok_sayilari: Dict[str, int] = {}
        toplam_adet = 0

        for obj in objeler:
            if obj.entity_type == AcadEntityType.BLOCK_REF and obj.blok_adi:
                blok_sayilari[obj.blok_adi] = blok_sayilari.get(obj.blok_adi, 0) + 1
                toplam_adet += 1

        return {
            "bloklar": blok_sayilari,
            "toplam_adet": toplam_adet,
            "obje_sayisi": len(objeler),
        }

    def katmana_gore_sec(self, katman_adi: str) -> List[MetrajObjesi]:
        """
        Belirtilen katmandaki tüm objeleri seç ve metrajını al.

        Args:
            katman_adi: Seçilecek katman adı

        Returns:
            List[MetrajObjesi]: Katmandaki objelerin metraj bilgileri
        """
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil!")

        try:
            self._selection_set_temizle()

            ss_adi = f"KatmanSecim_{id(self)}"
            try:
                existing = self.aktif_cizim.SelectionSets.Item(ss_adi)
                existing.Delete()
            except Exception:
                pass

            self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

            # Filtre: Katman adı (DXF code 8 = Layer)
            import array
            filter_type = array.array('h', [8])  # signed short array
            filter_data = [katman_adi]

            # Tüm model space'i tara (5 = acSelectionSetAll)
            self.selection_set.Select(5, None, None, filter_type, filter_data)

            secilen_objeler = []
            for i in range(self.selection_set.Count):
                entity = self.selection_set.Item(i)
                metraj_obj = self._obje_verisi_oku(entity)
                if metraj_obj:
                    secilen_objeler.append(metraj_obj)
                    self._objeyi_renklendir(entity, AcadColor.GREEN)

            self.aktif_cizim.Regen(1)

            print(f">>> '{katman_adi}' katmanından {len(secilen_objeler)} obje seçildi.")

            return secilen_objeler

        except Exception as e:
            logger.error(f"Katmana göre seçim hatası: {e}")
            raise

    def zoom_secim(self):
        """Seçili objelere zoom yap."""
        if not self.bagli:
            return

        try:
            self.acad_app.ZoomExtents()
        except Exception:
            pass

    def cizimi_kaydet(self):
        """Aktif çizimi kaydet."""
        if not self.bagli:
            return

        try:
            self.aktif_cizim.Save()
            logger.info("Çizim kaydedildi.")
        except Exception as e:
            logger.error(f"Kaydetme hatası: {e}")
            raise

    def komut_calistir(self, komut: str):
        """
        AutoCAD komut satırına komut gönder.

        Args:
            komut: Çalıştırılacak AutoCAD komutu
        """
        if not self.bagli:
            return

        try:
            self.aktif_cizim.SendCommand(komut + "\n")
        except Exception as e:
            logger.warning(f"Komut çalıştırılamadı: {e}")

    # ========================================================================
    # DEMİR METRAJ FONKSİYONLARI
    # ========================================================================

    def _blok_attributes_oku(self, entity) -> Optional[Dict[str, str]]:
        """
        AcDbBlockReference objesinin tüm attribute'larını okur.
        Returns: {TAG_UPPER: value_str} veya None
        """
        try:
            attrs = self._com_retry(lambda: entity.GetAttributes())
        except Exception:
            return None
        if not attrs:
            return None
        result = {}
        for attr in attrs:
            try:
                tag = self._com_retry(lambda a=attr: a.TagString)
                val = self._com_retry(lambda a=attr: a.TextString)
                if tag and val is not None:
                    result[str(tag).upper().strip()] = str(val).strip()
            except Exception:
                pass
        return result if result else None

    def _blok_attr_demir_parse(self,
                                attrs: Dict[str, str],
                                birim: str,
                                block_name: str = "") -> Optional["DemirBilgisi"]:
        """
        Blok attribute dict'inden DemirBilgisi üretir.
        Beklenen attribute adları (büyük harf): ADET, CAP, PAR1, TOPLAM, BOY, L, ARA
        Par1/TOPLAM birimi mm varsayılır (çizim birimi genellikle mm).
        """
        # CAP zorunlu
        cap_str = (attrs.get("CAP") or attrs.get("ÇAP") or attrs.get("DIA") or "").replace(",", ".")
        if not cap_str:
            return None
        try:
            cap = int(float(cap_str))
        except (ValueError, TypeError):
            return None

        # ADET zorunlu
        adet_str = (attrs.get("ADET") or attrs.get("N") or attrs.get("NO") or "").replace(",", ".")
        if not adet_str:
            return None
        try:
            adet = int(float(adet_str))
        except (ValueError, TypeError):
            return None

        if adet <= 0 or cap <= 0:
            return None

        # BOY: öncelik sırası — PAR1 > BOY > L > UZUNLUK > TOPLAM
        boy_raw = 0.0
        boy_kaynak = ""
        for key in ("PAR1", "PAR_1", "BOY", "L", "UZUNLUK", "BOY_M", "TOPLAM"):
            val_str = attrs.get(key, "").replace(",", ".")
            if val_str:
                try:
                    v = float(val_str)
                    if v > 0:
                        boy_raw = v
                        boy_kaynak = key
                        break
                except (ValueError, TypeError):
                    pass

        if boy_raw <= 0:
            return None

        # Birim dönüşümü
        # Blok attribute değerleri çizim birimi ile aynı (cm veya m).
        # Par1=1200, ARA=20 → her ikisi de cm — doğrudan kullan, bölme yapma.
        # Sadece m birimi için: 1200m saçma olur → cm kabul et → /100
        if birim.lower() == "cm":
            boy_cm = boy_raw               # doğrudan cm
            boy_m = boy_cm / 100.0
        else:
            # birim = "m"
            if boy_raw > 20:
                # 20m'den büyükse cm gelmiştir → /100
                boy_m = boy_raw / 100.0
            else:
                boy_m = boy_raw
            boy_cm = boy_m * 100.0

        agirlik_birim = DEMIR_AGIRLIK_TABLOSU.get(cap, 0.0)
        toplam_boy_m = adet * boy_m
        toplam_agirlik = toplam_boy_m * agirlik_birim

        orijinal_metin = f"[{block_name}] ADET={adet} Ø{cap} L={boy_cm:.0f}cm ({boy_kaynak})"

        d = DemirBilgisi(
            handle="",
            orijinal_metin=orijinal_metin,
            katman=attrs.get("KATMAN", "")
        )
        d.adet = adet
        d.cap = cap
        d.boy = boy_cm
        d.toplam_boy = toplam_boy_m
        d.agirlik_birim = agirlik_birim
        d.toplam_agirlik = toplam_agirlik
        d.gecerli = True
        d.hata_mesaji = ""
        return d

    def get_rebar_report_from_selection(self,
                                        birim: str = "cm",
                                        mesaj: str = "Demir yazılarını seçin") -> Dict[str, Any]:
        """
        AutoCAD'den seçilen TEXT/MTEXT objelerinden demir metrajı çıkar.

        Kullanıcı tek tek tıklayarak veya kutu çizerek obje seçer.
        ENTER'a basınca Python devreye girer ve:
        1. Sadece TEXT/MTEXT objelerini filtreler
        2. Demir regex analizi yapar: (\\d+)[Øø](\\d+).*?[Ll]=(\\d+)
        3. Başarılı olanları YEŞİL, başarısızları KIRMIZI boyar
        4. Detaylı rapor döndürür

        Args:
            birim: Boy birimi ("cm" veya "m"), varsayılan "cm"
            mesaj: Kullanıcıya gösterilecek mesaj

        Returns:
            Dict: {
                "basarili": List[DemirBilgisi], # Geçerli demir yazıları
                "basarisiz": List[DemirBilgisi], # Format dışı metinler
                "toplam_adet": int,              # Toplam demir adedi
                "toplam_boy_m": float,           # Toplam boy (metre)
                "toplam_agirlik_kg": float,      # Toplam ağırlık (kg)
                "cap_ozeti": Dict[int, Dict],    # Çap bazlı özet
                "secim_sayisi": int,             # Toplam seçilen obje
                "metin_sayisi": int,             # TEXT/MTEXT sayısı
            }

        Örnek Demir Yazıları:
            "10Ø12 L=250"    -> 10 adet, Ø12, 250cm
            "5ø16 l=180"     -> 5 adet, Ø16, 180cm
            "8Ø10 L=320 cm"  -> 8 adet, Ø10, 320cm
            "12 Ø 14 L = 150" -> 12 adet, Ø14, 150cm (boşluklu)
        """
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

        # Sonuç yapısı
        sonuc = {
            "basarili": [],
            "basarisiz": [],
            "toplam_adet": 0,
            "toplam_boy_m": 0.0,
            "toplam_agirlik_kg": 0.0,
            "cap_ozeti": {},
            "secim_sayisi": 0,
            "metin_sayisi": 0,
        }

        try:
            # AutoCAD penceresini görünür yap ve öne getir
            self._autocad_one_getir()

            # Önceki selection set'i temizle
            self._selection_set_temizle()

            # Yeni selection set oluştur
            ss_adi = f"DemirSecim_{id(self)}"
            try:
                existing = self.aktif_cizim.SelectionSets.Item(ss_adi)
                existing.Delete()
            except Exception:
                pass

            self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

            # Kullanıcıya bilgi ver
            print(f"\n{'='*50}")
            print(f" DEMİR METRAJİ - AutoCAD Seçimi")
            print(f"{'='*50}")
            print(f">>> {mesaj}")
            print(">>> Tek tek tıklayın veya kutu çizin.")
            print(">>> Seçimi tamamlamak için ENTER tuşuna basın.")
            print(">>> İptal için ESC tuşuna basın.\n")

            # SelectOnScreen - Kullanıcı seçimi (ENTER'a kadar bekler)
            self._guvenli_select_on_screen(self.selection_set)

            secim_sayisi = self.selection_set.Count
            sonuc["secim_sayisi"] = secim_sayisi

            if secim_sayisi == 0:
                print(">>> Hiç obje seçilmedi.")
                return sonuc

            print(f"\n>>> {secim_sayisi} obje seçildi. Filtreleniyor...")

            # ================================================================
            # TEK GEÇİŞ: FİLTRELE + ÖZELLİKLERİ CACHE'LE
            # ================================================================
            metin_props_listesi = []   # TEXT/MTEXT objeleri
            blok_props_listesi = []    # AcDbBlockReference (attribute'lu bloklar)

            _METIN_OBJECT_NAMES = {
                "AcDbText", "AcDbMText",   # standart
                "TEXT", "MTEXT",            # bazı sürümler kısa isim döner
            }

            for i in range(secim_sayisi):
                try:
                    entity = self._com_retry(lambda idx=i: self.selection_set.Item(idx))
                except Exception as e:
                    logger.debug(f"Obje {i} okunamadı, atlanıyor: {e}")
                    continue

                props = self._read_entity_props(entity)
                if props is None:
                    continue

                obj_name = props['object_name']

                # --- TEXT / MTEXT ---
                if obj_name in _METIN_OBJECT_NAMES:
                    if props['text'] is not None:
                        metin_props_listesi.append(props)
                    else:
                        logger.debug(f"Metin objesi okunamadı (index: {i})")

                # --- BLOK (attribute'lu demir sembolleri) ---
                elif obj_name == "AcDbBlockReference":
                    try:
                        block_name = self._com_retry(lambda e=entity: e.Name)
                    except Exception:
                        block_name = "?"
                    handle = None
                    try:
                        handle = self._com_retry(lambda e=entity: e.Handle)
                    except Exception:
                        pass
                    color = 256
                    try:
                        color = self._com_retry(lambda e=entity: e.Color)
                    except Exception:
                        pass
                    layer = ""
                    try:
                        layer = self._com_retry(lambda e=entity: e.Layer)
                    except Exception:
                        pass
                    blok_props_listesi.append({
                        'entity': entity,
                        'object_name': obj_name,
                        'handle': handle,
                        'color': color,
                        'layer': layer,
                        'block_name': block_name,
                    })
                    logger.debug(f"Blok bulundu: {block_name} (index: {i})")

                # --- Duck-typing fallback (bilinmeyen ama TextString içeren) ---
                else:
                    try:
                        ts = self._com_retry(lambda e=entity: e.TextString)
                        if ts is not None:
                            props['text'] = str(ts)
                            metin_props_listesi.append(props)
                            logger.debug(f"Duck-typing metin: ObjectName={obj_name!r}")
                    except Exception:
                        logger.debug(f"Atlandı (index: {i}, ObjectName: {obj_name!r})")

            sonuc["metin_sayisi"] = len(metin_props_listesi) + len(blok_props_listesi)

            if not metin_props_listesi and not blok_props_listesi:
                all_names = []
                for ii in range(min(secim_sayisi, 10)):
                    try:
                        ent = self._com_retry(lambda idx=ii: self.selection_set.Item(idx))
                        n = self._com_retry(lambda e=ent: e.ObjectName)
                        all_names.append(n)
                    except Exception:
                        all_names.append("?")
                print(f">>> Seçilen {secim_sayisi} objeden hiçbiri metin/blok değil!")
                print(f">>> Bulunan ObjectName'ler: {all_names}")
                print(f">>> Lütfen demir yazılarını (TEXT/MTEXT) veya demir bloklarını seçin.")
                return sonuc

            print(f">>> {len(metin_props_listesi)} metin objesi bulundu. Analiz ediliyor...")

            # ================================================================
            # DEMİR REGEX ANALİZİ (cache'lenmiş verilerle)
            # ================================================================
            # Modül seviyesi sabitler kullanılır: _DEMIR_PATTERN, _DEMIR_PATTERN_AUTOCAD
            # processEvents her 25 nesnede bir (eski: 5) — UI yanıt süresi korunur,
            # overhead 5x azalır.

            eslesmeyen_props = []  # (props, text_content, demir) — Faz 2 için bekleyen

            for idx, props in enumerate(metin_props_listesi):
                # Her 25 objede bir Qt mesaj kuyruğunu boşalt
                if _QT_AVAILABLE and idx % 25 == 0:
                    _QApplication.processEvents()

                try:
                    # Cache'ten oku (0 COM çağrısı)
                    handle = props['handle'] or str(id(props['entity']))
                    text_raw = props['text']
                    layer = props['layer'] or ""

                    # MTEXT satır birleştirme: AutoCAD \P (paragraph break) ve
                    # gerçek \n karakterlerini boşluğa çevir ki regex satırlar
                    # arası geçebilsin (örn: "65 ?8 /50\PL= 46" → "65 ?8 /50 L= 46")
                    text_content = re.sub(r'\\[Pp]|\r?\n', ' ', text_raw)
                    # AutoCAD RTF format kodlarını temizle: {\fArial|b0;...} vb.
                    text_content = re.sub(r'\\[A-Za-z][^;\\]*;|[{}]', '', text_content).strip()

                    # Demir bilgisi oluştur (orijinal_metin ham hali saklar)
                    demir = DemirBilgisi(
                        handle=handle,
                        orijinal_metin=text_raw,
                        katman=layer
                    )

                    # Debug: hex encode hesabı sadece DEBUG aktifken yapılır
                    # (f-string eager evaluation'ı önler)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            f"Metin kontrol ediliyor: '{text_content}' "
                            f"(ham: '{text_raw}' hex: {text_raw.encode('utf-8').hex()})"
                        )

                    # Regex ile eşleştir — tek birleşik pattern (Ø/%%C + 2x çarpan desteği)
                    match = _DEMIR_PATTERN.search(text_content)

                    if match:
                        # Başarılı eşleşme
                        # Grup 1: carpan (opsiyonel "2x"), Grup 2: adet, Grup 3: çap, Grup 4: boy
                        carpan = int(match.group(1)) if match.group(1) else 1
                        adet = carpan * int(match.group(2))
                        cap = int(match.group(3))
                        boy_str = match.group(4).replace(',', '.')
                        boy = float(boy_str)

                        # Birim dönüşümü (cm -> m)
                        if birim.lower() == "cm":
                            boy_m = boy / 100.0
                        else:
                            boy_m = boy

                        # Ağırlık hesabı
                        agirlik_birim = DEMIR_AGIRLIK_TABLOSU.get(cap, 0.0)
                        toplam_boy = adet * boy_m
                        toplam_agirlik = toplam_boy * agirlik_birim

                        # Demir bilgisini güncelle
                        demir.adet = adet
                        demir.cap = cap
                        demir.boy = boy
                        demir.toplam_boy = toplam_boy
                        demir.agirlik_birim = agirlik_birim
                        demir.toplam_agirlik = toplam_agirlik
                        demir.gecerli = True

                        # Başarılı listeye ekle
                        sonuc["basarili"].append(demir)

                        # Toplamları güncelle
                        sonuc["toplam_adet"] += adet
                        sonuc["toplam_boy_m"] += toplam_boy
                        sonuc["toplam_agirlik_kg"] += toplam_agirlik

                        # Çap özeti
                        if cap not in sonuc["cap_ozeti"]:
                            sonuc["cap_ozeti"][cap] = {
                                "adet": 0,
                                "boy_m": 0.0,
                                "agirlik_kg": 0.0,
                                "birim_agirlik": agirlik_birim
                            }
                        sonuc["cap_ozeti"][cap]["adet"] += adet
                        sonuc["cap_ozeti"][cap]["boy_m"] += toplam_boy
                        sonuc["cap_ozeti"][cap]["agirlik_kg"] += toplam_agirlik

                        # YEŞİL boya (cache'li, 1 COM çağrısı)
                        self._objeyi_renklendir_cached(
                            props['entity'], AcadColor.GREEN,
                            handle=props['handle'],
                            original_color=props['color']
                        )

                        carpan_str = f"{carpan}x" if carpan > 1 else ""
                        logger.debug(f"Demir bulundu: {carpan_str}{adet}Ø{cap} L={boy}{birim} -> {toplam_agirlik:.2f}kg")

                    else:
                        # Faz-1 eşleşmedi — Faz-2 yakınlık birleştirme için beklet
                        demir.gecerli = False
                        eslesmeyen_props.append((props, text_content, demir))
                        logger.debug(f"Faz1 pass, Faz2'ye: '{text_content}'")

                except Exception as e:
                    logger.warning(f"Metin işlenirken hata: {type(e).__name__}: {e}")
                    try:
                        hata_demir = DemirBilgisi(
                            handle=str(id(props.get('entity', None))),
                            orijinal_metin=f"(Okunamadı: {e})",
                            katman=""
                        )
                        hata_demir.gecerli = False
                        hata_demir.hata_mesaji = f"COM hatası: {e}"
                        sonuc["basarisiz"].append(hata_demir)
                        self._objeyi_renklendir_cached(
                            props['entity'], AcadColor.RED,
                            handle=props.get('handle'),
                            original_color=props.get('color')
                        )
                    except Exception:
                        pass

            # ================================================================
            # FAZ 2 — YAKINLIK BAZLI BİRLEŞTİRME (ayrı TEXT objeleri)
            # ================================================================
            if eslesmeyen_props:
                adet_cap_gruplari = []
                boy_gruplari = []
                direkt_basarisiz = []

                for props_f2, tc_f2, demir_f2 in eslesmeyen_props:
                    m_k = _DEMIR_KISMI.search(tc_f2)
                    m_l = _L_KISMI.search(tc_f2)
                    if m_k and not m_l:
                        carpan_f2 = int(m_k.group(1)) if m_k.group(1) else 1
                        adet_f2 = carpan_f2 * int(m_k.group(2))
                        cap_f2 = int(m_k.group(3))
                        adet_cap_gruplari.append((props_f2, carpan_f2, adet_f2, cap_f2, demir_f2))
                    elif m_l and not m_k:
                        boy_f2 = float(m_l.group(1).replace(',', '.'))
                        boy_gruplari.append((props_f2, boy_f2, demir_f2))
                    else:
                        direkt_basarisiz.append((props_f2, demir_f2))

                def _get_xy(entity):
                    try:
                        res = self._com_retry(lambda: entity.GetBoundingBox())
                        if res and len(res) == 2:
                            return ((res[0][0] + res[1][0]) / 2.0, (res[0][1] + res[1][1]) / 2.0)
                    except Exception:
                        pass
                    try:
                        pt = self._com_retry(lambda: entity.InsertionPoint)
                        return (pt[0], pt[1])
                    except Exception:
                        return (0.0, 0.0)

                if adet_cap_gruplari and boy_gruplari:
                    ac_ile_xy = [
                        (p, c, a, cap, d, _get_xy(p['entity']))
                        for p, c, a, cap, d in adet_cap_gruplari
                    ]
                    b_ile_xy = [
                        (p, b, d, _get_xy(p['entity']))
                        for p, b, d in boy_gruplari
                    ]
                    eslesilen_b = set()

                    for ac_props, carpan_v, adet_v, cap_v, ac_demir, (ax, ay) in ac_ile_xy:
                        en_yakin_i = None
                        en_mesafe = float('inf')
                        for bi, (b_props, boy_v, b_demir, (bx, by)) in enumerate(b_ile_xy):
                            if bi in eslesilen_b:
                                continue
                            mesafe = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                            if mesafe < en_mesafe:
                                en_mesafe = mesafe
                                en_yakin_i = bi

                        if en_yakin_i is not None:
                            b_props, boy_v, b_demir, _ = b_ile_xy[en_yakin_i]
                            eslesilen_b.add(en_yakin_i)
                            boy_m_v = boy_v / 100.0 if birim.lower() == "cm" else boy_v
                            agirlik_birim_v = DEMIR_AGIRLIK_TABLOSU.get(cap_v, 0.0)
                            toplam_boy_v = adet_v * boy_m_v
                            toplam_agirlik_v = toplam_boy_v * agirlik_birim_v
                            ac_demir.adet = adet_v
                            ac_demir.cap = cap_v
                            ac_demir.boy = boy_v
                            ac_demir.toplam_boy = toplam_boy_v
                            ac_demir.agirlik_birim = agirlik_birim_v
                            ac_demir.toplam_agirlik = toplam_agirlik_v
                            ac_demir.gecerli = True
                            ac_demir.orijinal_metin = f"{ac_demir.orijinal_metin} | {b_demir.orijinal_metin}"
                            ac_demir.hata_mesaji = ""
                            sonuc["basarili"].append(ac_demir)
                            sonuc["toplam_adet"] += adet_v
                            sonuc["toplam_boy_m"] += toplam_boy_v
                            sonuc["toplam_agirlik_kg"] += toplam_agirlik_v
                            if cap_v not in sonuc["cap_ozeti"]:
                                sonuc["cap_ozeti"][cap_v] = {
                                    "adet": 0, "boy_m": 0.0,
                                    "agirlik_kg": 0.0, "birim_agirlik": agirlik_birim_v
                                }
                            sonuc["cap_ozeti"][cap_v]["adet"] += adet_v
                            sonuc["cap_ozeti"][cap_v]["boy_m"] += toplam_boy_v
                            sonuc["cap_ozeti"][cap_v]["agirlik_kg"] += toplam_agirlik_v
                            self._objeyi_renklendir_cached(
                                ac_props['entity'], AcadColor.GREEN,
                                handle=ac_props['handle'], original_color=ac_props['color']
                            )
                            self._objeyi_renklendir_cached(
                                b_props['entity'], AcadColor.GREEN,
                                handle=b_props['handle'], original_color=b_props['color']
                            )
                            logger.debug(f"Faz2 eslesti: {adet_v}O{cap_v} L={boy_v}{birim} (mesafe:{en_mesafe:.0f})")
                        else:
                            ac_demir.hata_mesaji = "L= objesi secimde yok"
                            sonuc["basarisiz"].append(ac_demir)
                            self._objeyi_renklendir_cached(
                                ac_props['entity'], AcadColor.RED,
                                handle=ac_props['handle'], original_color=ac_props['color']
                            )

                    for bi, (b_props, boy_v, b_demir, _) in enumerate(b_ile_xy):
                        if bi not in eslesilen_b:
                            b_demir.hata_mesaji = "Adet+cap objesi secimde yok"
                            sonuc["basarisiz"].append(b_demir)
                            self._objeyi_renklendir_cached(
                                b_props['entity'], AcadColor.RED,
                                handle=b_props['handle'], original_color=b_props['color']
                            )
                else:
                    for p_v, c_v, a_v, cap_v, d_v in adet_cap_gruplari:
                        d_v.hata_mesaji = "L= objesi secimde yok"
                        sonuc["basarisiz"].append(d_v)
                        self._objeyi_renklendir_cached(
                            p_v['entity'], AcadColor.RED,
                            handle=p_v['handle'], original_color=p_v['color']
                        )
                    for p_v, b_v, d_v in boy_gruplari:
                        d_v.hata_mesaji = "Adet+cap objesi secimde yok"
                        sonuc["basarisiz"].append(d_v)
                        self._objeyi_renklendir_cached(
                            p_v['entity'], AcadColor.RED,
                            handle=p_v['handle'], original_color=p_v['color']
                        )

                for p_v, d_v in direkt_basarisiz:
                    d_v.hata_mesaji = "Demir formatina uymuyor"
                    sonuc["basarisiz"].append(d_v)
                    self._objeyi_renklendir_cached(
                        p_v['entity'], AcadColor.RED,
                        handle=p_v['handle'], original_color=p_v['color']
                    )

            # ================================================================
            # FAZ 3 — BLOK ATTRIBUTE OKUMA (AcDbBlockReference)
            # ================================================================
            if blok_props_listesi:
                print(f"\n>>> {len(blok_props_listesi)} blok objesi işleniyor...")
                for bprops in blok_props_listesi:
                    attrs = self._blok_attributes_oku(bprops['entity'])
                    if not attrs:
                        d_hata = DemirBilgisi(
                            handle=bprops['handle'] or "",
                            orijinal_metin=f"[{bprops['block_name']}] attribute yok",
                            katman=bprops['layer']
                        )
                        d_hata.gecerli = False
                        d_hata.hata_mesaji = "Blokta attribute bulunamadi"
                        sonuc["basarisiz"].append(d_hata)
                        self._objeyi_renklendir_cached(
                            bprops['entity'], AcadColor.RED,
                            handle=bprops['handle'], original_color=bprops['color']
                        )
                        continue

                    logger.debug(f"BLOK [{bprops['block_name']}] attrs: {attrs}")
                    d = self._blok_attr_demir_parse(attrs, birim, bprops['block_name'])
                    if d is None:
                        # ADET veya CAP bulunamadı
                        d_hata = DemirBilgisi(
                            handle=bprops['handle'] or "",
                            orijinal_metin=f"[{bprops['block_name']}] {dict(list(attrs.items())[:5])}",
                            katman=bprops['layer']
                        )
                        d_hata.gecerli = False
                        d_hata.hata_mesaji = "ADET/CAP/BOY attribute eksik"
                        sonuc["basarisiz"].append(d_hata)
                        self._objeyi_renklendir_cached(
                            bprops['entity'], AcadColor.RED,
                            handle=bprops['handle'], original_color=bprops['color']
                        )
                        logger.warning(f"Blok parse edilemedi [{bprops['block_name']}]: {dict(list(attrs.items())[:6])}")
                        continue

                    # Başarılı
                    d.handle = bprops['handle'] or ""
                    d.katman = bprops['layer']
                    sonuc["basarili"].append(d)
                    sonuc["toplam_adet"] += d.adet
                    sonuc["toplam_boy_m"] += d.toplam_boy
                    sonuc["toplam_agirlik_kg"] += d.toplam_agirlik
                    cap = d.cap
                    if cap not in sonuc["cap_ozeti"]:
                        sonuc["cap_ozeti"][cap] = {
                            "adet": 0, "boy_m": 0.0,
                            "agirlik_kg": 0.0, "birim_agirlik": d.agirlik_birim
                        }
                    sonuc["cap_ozeti"][cap]["adet"] += d.adet
                    sonuc["cap_ozeti"][cap]["boy_m"] += d.toplam_boy
                    sonuc["cap_ozeti"][cap]["agirlik_kg"] += d.toplam_agirlik
                    self._objeyi_renklendir_cached(
                        bprops['entity'], AcadColor.GREEN,
                        handle=bprops['handle'], original_color=bprops['color']
                    )
                    logger.debug(f"Blok OK: {d.orijinal_metin} → {d.toplam_agirlik:.2f} kg")

            # Ekranı güncelle
            self.aktif_cizim.Regen(1)

            # ================================================================
            # SONUÇ RAPORU
            # ================================================================
            print(f"\n{'='*50}")
            print(f" DEMİR METRAJ RAPORU")
            print(f"{'='*50}")
            print(f" Toplam seçim  : {secim_sayisi} obje")
            print(f" Metin objesi  : {len(metin_props_listesi)} adet")
            print(f" Geçerli demir : {len(sonuc['basarili'])} adet")
            print(f" Format dışı   : {len(sonuc['basarisiz'])} adet")
            print(f"{'='*50}")

            if sonuc["basarili"]:
                # Çubuk adedi hesapla (1 çubuk = 12 metre) - yukarı yuvarla
                CUBUK_BOYU = 12.0  # metre
                toplam_cubuk = math.ceil(sonuc['toplam_boy_m'] / CUBUK_BOYU)
                sonuc["toplam_cubuk"] = toplam_cubuk

                # Çap bazlı çubuk hesabı - yukarı yuvarla
                for cap in sonuc["cap_ozeti"]:
                    sonuc["cap_ozeti"][cap]["cubuk_adet"] = math.ceil(
                        sonuc["cap_ozeti"][cap]["boy_m"] / CUBUK_BOYU
                    )

                print(f"\n ÖZET:")
                print(f" ─────────────────────────────────")
                print(f" Toplam Demir Adedi : {sonuc['toplam_adet']:,}")
                print(f" Toplam Boy         : {sonuc['toplam_boy_m']:,.2f} m")
                print(f" Toplam Ağırlık     : {sonuc['toplam_agirlik_kg']:,.2f} kg")
                print(f" ─────────────────────────────────")
                print(f" ÇUBUK ADEDİ (12m)  : {toplam_cubuk:,} çubuk")

                print(f"\n ÇAP BAZLI DAĞILIM:")
                print(f" {'Çap':<6} {'Adet':>8} {'Boy(m)':>10} {'Ağırlık(kg)':>12} {'Çubuk':>8}")
                print(f" {'-'*50}")
                for cap in sorted(sonuc["cap_ozeti"].keys()):
                    ozet = sonuc["cap_ozeti"][cap]
                    print(f" Ø{cap:<4} {ozet['adet']:>8,} {ozet['boy_m']:>10,.2f} {ozet['agirlik_kg']:>12,.2f} {ozet['cubuk_adet']:>8,}")

            if sonuc["basarisiz"]:
                print(f"\n FORMAT DIŞI METİNLER (KIRMIZI):")
                for d in sonuc["basarisiz"][:5]:  # İlk 5'i göster
                    if len(d.orijinal_metin) > 40:
                        print(f"  • \"{d.orijinal_metin[:40]}...\"")
                    else:
                        print(f"  • \"{d.orijinal_metin}\"")
                if len(sonuc["basarisiz"]) > 5:
                    print(f"  ... ve {len(sonuc['basarisiz'])-5} metin daha")

            print(f"\n{'='*50}\n")

            return sonuc

        except com_error as e:
            if "canceled" in str(e).lower() or "esc" in str(e).lower():
                print(">>> Seçim iptal edildi (ESC).")
                return sonuc
            logger.error(f"Demir seçim hatası: {e}")
            raise
        except Exception as e:
            logger.error(f"Demir raporu alınırken hata: {e}")
            raise

    def get_kolon_filizi_from_table(self,
                                    birim: str = "cm",
                                    mesaj: str = "Kolon filizi tablosunu seçin") -> Dict[str, Any]:
        """
        AutoCAD'deki kolon filizi tablosunu otomatik okur.

        Kullanıcı tüm tabloyu kutu çizerek seçer.
        Program Y koordinatına göre satırları, X koordinatına göre sütunları belirler.
        Başlık satırını (KOLON, DONATI, BOY) otomatik tanır.

        Tablo formatı:
            KOLON  | DONATI      | BOY
            SB01   | P84-28Ø14  | 135
            SB02   | P84-14Ø14  | 135

        Returns:
            get_rebar_report_from_selection() ile aynı dict formatı
        """
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

        sonuc = {
            "basarili": [],
            "basarisiz": [],
            "toplam_adet": 0,
            "toplam_boy_m": 0.0,
            "toplam_agirlik_kg": 0.0,
            "cap_ozeti": {},
            "secim_sayisi": 0,
            "metin_sayisi": 0,
        }

        try:
            self._autocad_one_getir()
            self._selection_set_temizle()

            ss_adi = f"FilizSecim_{id(self)}"
            try:
                existing = self.aktif_cizim.SelectionSets.Item(ss_adi)
                existing.Delete()
            except Exception:
                pass

            self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

            print(f"\n{'='*50}")
            print(f" KOLON FİLİZİ - Tablo Okuma")
            print(f"{'='*50}")
            print(f">>> {mesaj}")
            print(">>> Tüm tabloyu kutu çizerek seçin.")
            print(">>> Seçimi tamamlamak için ENTER tuşuna basın.\n")

            self._guvenli_select_on_screen(self.selection_set)

            secim_sayisi = self.selection_set.Count
            sonuc["secim_sayisi"] = secim_sayisi

            if secim_sayisi == 0:
                print(">>> Hiç obje seçilmedi.")
                return sonuc

            print(f"\n>>> {secim_sayisi} obje seçildi. Tablo analiz ediliyor...")

            # ================================================================
            # 1. TÜM METİN OBJELERİNİ OKU
            # ================================================================
            metin_listesi = []

            for i in range(secim_sayisi):
                try:
                    entity = self._com_retry(lambda idx=i: self.selection_set.Item(idx))
                except Exception:
                    continue
                props = self._read_entity_props(entity)
                if props is None:
                    continue
                if props['object_name'] not in ("AcDbText", "AcDbMText"):
                    continue
                if props['text'] is None:
                    continue
                metin_listesi.append(props)

            sonuc["metin_sayisi"] = len(metin_listesi)

            if len(metin_listesi) < 3:
                print(">>> Yeterli metin objesi bulunamadı.")
                return sonuc

            # ================================================================
            # 2. İÇERİK BAZLI AKILLI PARSE (koordinat gerekmez)
            # ================================================================
            # Modül seviyesi sabitler kullanılır: _DONATI_PATTERN, _DONATI_PATTERN_AUTOCAD
            boy_pattern = re.compile(r'^(\d+(?:[.,]\d+)?)$')
            baslik_kelimeleri = {
                "KOLON", "DONATI", "DONAT", "BOY", "FİLİZ", "FILIZ",
                "FILIZI", "FİLİZİ", "KOLON FILIZI", "KOLON FİLİZİ"
            }

            # Tüm metinleri sınıflandır
            donati_listesi = []  # [(props, match)]
            boy_listesi = []     # [(props, değer)]
            kolon_listesi = []   # [props]
            atlanan = 0

            for props in metin_listesi:
                text = props['text'].strip()
                text_upper = text.upper().strip()

                # Başlık metinleri → atla
                if text_upper in baslik_kelimeleri:
                    atlanan += 1
                    continue

                # Donatı mı? (P84-28ƒ14, 28Ø14, vb.) — modül sabiti kullan
                match = _DONATI_PATTERN.search(text)
                if not match:
                    match = _DONATI_PATTERN_AUTOCAD.search(text)
                if match:
                    donati_listesi.append((props, match))
                    continue

                # Sayı mı? (boy değeri: 135, 150, 200 vb.)
                boy_match = boy_pattern.match(text)
                if boy_match:
                    try:
                        val = float(boy_match.group(1).replace(',', '.'))
                        if val > 0:
                            boy_listesi.append((props, val))
                            continue
                    except ValueError:
                        pass

                # Geriye kalan → kolon adı (SB01, K1, S03 vb.)
                if len(text) <= 20 and text_upper not in baslik_kelimeleri:
                    kolon_listesi.append(props)

            print(f">>> Sınıflandırma: {len(donati_listesi)} donatı, {len(boy_listesi)} boy, {len(kolon_listesi)} kolon, {atlanan} başlık")

            # Eşleştirme: donatı ve boy aynı sayıda olmalı
            if len(donati_listesi) == 0:
                print(">>> Hiç donatı metni bulunamadı!")
                print(">>> Beklenen format: P84-28Ø14 veya 28Ø14")
                return sonuc

            # Boy listesi donatıdan az/çoksa uyar
            if len(boy_listesi) != len(donati_listesi):
                print(f">>> UYARI: {len(donati_listesi)} donatı ama {len(boy_listesi)} boy değeri bulundu.")
                # Eğer tek boy değeri varsa hepsine uygula
                if len(boy_listesi) == 1:
                    tek_boy = boy_listesi[0][1]
                    print(f">>> Tek boy değeri ({tek_boy}) tüm donatılara uygulanıyor.")
                    boy_listesi = [(boy_listesi[0][0], tek_boy)] * len(donati_listesi)
                elif len(set(b[1] for b in boy_listesi)) == 1:
                    # Hepsi aynı boy
                    tek_boy = boy_listesi[0][1]
                    print(f">>> Tüm boy değerleri aynı ({tek_boy}), donatı sayısına tamamlanıyor.")
                    boy_listesi = [(boy_listesi[0][0], tek_boy)] * len(donati_listesi)

            # Satır sayısını belirle
            satir_sayisi = min(len(donati_listesi), len(boy_listesi))
            print(f">>> {satir_sayisi} veri satırı işleniyor...\n")

            for idx in range(satir_sayisi):
                d_props, d_match = donati_listesi[idx]
                b_props, boy = boy_listesi[idx]
                kolon_text = kolon_listesi[idx]['text'].strip() if idx < len(kolon_listesi) else f"Satır{idx+1}"

                donati_text = d_props['text'].strip()
                satir_entityleri = [d_props, b_props]
                if idx < len(kolon_listesi):
                    satir_entityleri.append(kolon_listesi[idx])

                if not donati_text or boy <= 0:
                    continue

                # Handle bilgisi
                handle = satir_entityleri[0]['handle'] if satir_entityleri else f"row_{idx}"
                orijinal = f"{kolon_text}: {donati_text} L={boy}" if kolon_text else f"{donati_text} L={boy}"

                # Birleşik donatıları yakala (ör: 8ƒ16+6ƒ14 → 2 ayrı demir)
                all_matches = list(_DONATI_PATTERN.finditer(donati_text))
                if not all_matches:
                    all_matches = list(_DONATI_PATTERN_AUTOCAD.finditer(donati_text))

                if not all_matches:
                    demir = DemirBilgisi(
                        handle=handle,
                        orijinal_metin=orijinal,
                        katman=kolon_text
                    )
                    demir.gecerli = False
                    demir.hata_mesaji = "Donatı parse edilemedi"
                    sonuc["basarisiz"].append(demir)

                    for p in satir_entityleri:
                        self._objeyi_renklendir_cached(
                            p['entity'], AcadColor.RED,
                            handle=p['handle'], original_color=p['color']
                        )
                    continue

                if birim.lower() == "cm":
                    boy_m = boy / 100.0
                else:
                    boy_m = boy

                for mi, match in enumerate(all_matches):
                    adet = int(match.group(1))
                    cap = int(match.group(2))

                    agirlik_birim = DEMIR_AGIRLIK_TABLOSU.get(cap, 0.0)
                    toplam_boy = adet * boy_m
                    toplam_agirlik = toplam_boy * agirlik_birim

                    demir = DemirBilgisi(
                        handle=f"{handle}_{mi}" if mi > 0 else handle,
                        orijinal_metin=orijinal if mi == 0 else f" +{adet}Ø{cap}",
                        katman=kolon_text
                    )
                    demir.adet = adet
                    demir.cap = cap
                    demir.boy = boy
                    demir.toplam_boy = toplam_boy
                    demir.agirlik_birim = agirlik_birim
                    demir.toplam_agirlik = toplam_agirlik
                    demir.gecerli = True
                    demir.eleman_tipi = "Kolon"

                    sonuc["basarili"].append(demir)
                    sonuc["toplam_adet"] += adet
                    sonuc["toplam_boy_m"] += toplam_boy
                    sonuc["toplam_agirlik_kg"] += toplam_agirlik

                    if cap not in sonuc["cap_ozeti"]:
                        sonuc["cap_ozeti"][cap] = {
                            "adet": 0, "boy_m": 0.0, "agirlik_kg": 0.0,
                            "birim_agirlik": agirlik_birim
                        }
                    sonuc["cap_ozeti"][cap]["adet"] += adet
                    sonuc["cap_ozeti"][cap]["boy_m"] += toplam_boy
                    sonuc["cap_ozeti"][cap]["agirlik_kg"] += toplam_agirlik

                    logger.debug(f"Filiz: {kolon_text} {adet}Ø{cap} L={boy} -> {toplam_agirlik:.2f}kg")

                # YEŞİL boya (satırdaki tüm donatılar başarılı)
                for p in satir_entityleri:
                    self._objeyi_renklendir_cached(
                        p['entity'], AcadColor.GREEN,
                        handle=p['handle'], original_color=p['color']
                    )

            # Ekranı güncelle
            self.aktif_cizim.Regen(1)

            # ================================================================
            # SONUÇ RAPORU
            # ================================================================
            print(f"\n{'='*50}")
            print(f" KOLON FİLİZİ RAPORU")
            print(f"{'='*50}")
            print(f" Toplam seçim  : {secim_sayisi} obje")
            print(f" Metin objesi  : {sonuc['metin_sayisi']} adet")
            print(f" Satır sayısı  : {satir_sayisi} adet")
            print(f" Geçerli demir : {len(sonuc['basarili'])} adet")
            print(f" Format dışı   : {len(sonuc['basarisiz'])} adet")

            if sonuc["basarili"]:
                CUBUK_BOYU = 12.0
                toplam_cubuk = math.ceil(sonuc['toplam_boy_m'] / CUBUK_BOYU)
                sonuc["toplam_cubuk"] = toplam_cubuk

                for cap in sonuc["cap_ozeti"]:
                    sonuc["cap_ozeti"][cap]["cubuk_adet"] = math.ceil(
                        sonuc["cap_ozeti"][cap]["boy_m"] / CUBUK_BOYU
                    )

                print(f"\n ÖZET:")
                print(f" Toplam Demir   : {sonuc['toplam_adet']:,} adet")
                print(f" Toplam Boy     : {sonuc['toplam_boy_m']:,.2f} m")
                print(f" Toplam Ağırlık : {sonuc['toplam_agirlik_kg']:,.2f} kg")
                print(f" Çubuk (12m)    : {toplam_cubuk:,} çubuk")

                print(f"\n ÇAP BAZLI DAĞILIM:")
                print(f" {'Çap':<6} {'Adet':>8} {'Boy(m)':>10} {'Ağırlık(kg)':>12}")
                print(f" {'-'*40}")
                for cap in sorted(sonuc["cap_ozeti"].keys()):
                    ozet = sonuc["cap_ozeti"][cap]
                    print(f" Ø{cap:<4} {ozet['adet']:>8,} {ozet['boy_m']:>10,.2f} {ozet['agirlik_kg']:>12,.2f}")

            print(f"\n{'='*50}\n")
            return sonuc

        except com_error as e:
            if "canceled" in str(e).lower() or "esc" in str(e).lower():
                print(">>> Seçim iptal edildi (ESC).")
                return sonuc
            logger.error(f"Kolon filizi seçim hatası: {e}")
            raise
        except Exception as e:
            logger.error(f"Kolon filizi raporu alınırken hata: {e}")
            raise

    def get_poz_bazli_donati_tablosu(
        self,
        mesaj: str = "Poza göre donatı metraj tablosunu kutu çizerek seçin",
        x_esik: Optional[float] = None,
        y_esik: Optional[float] = None,
        sutun_sirasi: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        AutoCAD'deki "Poza Göre Donatı Metraj Tablosu"nu (POZ/ADET/ÇAP/BOY/
        ŞEKİL + çap bazlı TOPLAM BOY sütunları) koordinat bazlı satır/sütun
        kümelemesiyle okur ve (bulunabiliyorsa) poz/adet/çap/boy kayıtlarına
        çevirir.

        AŞAMA 1+2 (bkz. proje brief'i): Aşama 1 (kümeleme, PROGRAM_OZELLIKLERI
        Rev-128'de gerçek AutoCAD tablosuyla doğrulandı) + Aşama 2 (başlık
        tespiti / sütun→alan eşleme / çap normalizasyonu,
        grid_den_poz_kayitlarini_cikar). Hesap (kg/ton) ve hazır TOPLAM
        sütunuyla karşılaştırma (Aşama 3), UI butonu (Aşama 4) HENÜZ YOK.

        get_kolon_filizi_from_table'daki içerik-bazlı (donatı/boy/kolon
        kovaları) yaklaşım burada KULLANILMAZ — bu tabloda ADET/ÇAP/BOY/
        TOPLAM gibi birden fazla "saf sayı" sütunu olduğu için içerikten
        ayrım yapılamaz (bkz. modül seviyesi tablo_hucrelerini_kumele
        docstring'i).

        Args:
            x_esik, y_esik: Kümeleme eşiği elle vermek için (bkz. CLAUDE.md
                Rev-128 "BİLİNEN SINIR" — oto-eşik eşit aralıklı, sıfır-jitter
                sütunlarda yanılabilir). None ise otomatik bulunur.
            sutun_sirasi: Başlık satırı otomatik BULUNAMAZSA elle sütun→alan
                eşlemesi ('poz'|'adet'|'cap'|'boy'|'sekil'|'toplam'|'yoksay',
                grid sütun sayısı kadar). None ve başlık da yoksa
                poz_kayitlari["sutun_tespiti"]=="basarisiz" döner (crash yok).

        Returns:
            {
                "secim_sayisi": int,
                "metin_sayisi": int,          # koordinatlı okunabilen metin sayısı
                "grid": List[List[Optional[str]]],       # satır x sütun, sadece metin
                "grid_ham": List[List[Optional[Dict]]],  # satır x sütun, tam hücre (entity dahil)
                "poz_kayitlari": Dict,         # grid_den_poz_kayitlarini_cikar() çıktısı
            }
        """
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

        sonuc: Dict[str, Any] = {
            "secim_sayisi": 0, "metin_sayisi": 0, "grid": [], "grid_ham": [],
            "poz_kayitlari": {}, "hesap": {},
            # get_kolon_filizi_from_table / get_rebar_report_from_selection ile
            # AYNI ŞEKİLDE doldurulur (Aşama 4 UI entegrasyonu bu ortak şekle
            # güvenir — kat_data["demirler"].extend(rapor["basarili"]) vb.):
            "basarili": [], "basarisiz": [], "toplam_adet": 0,
            "toplam_boy_m": 0.0, "toplam_agirlik_kg": 0.0, "cap_ozeti": {},
        }

        try:
            self._autocad_one_getir()
            self._selection_set_temizle()

            ss_adi = f"PozDonatiSecim_{id(self)}"
            try:
                existing = self.aktif_cizim.SelectionSets.Item(ss_adi)
                existing.Delete()
            except Exception:
                pass
            self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

            print(f"\n{'='*50}")
            print(" POZA GÖRE DONATI METRAJ TABLOSU — Okuma (AŞAMA 1: ham ızgara)")
            print(f"{'='*50}")
            print(f">>> {mesaj}")
            print(">>> Tüm tabloyu kutu çizerek seçin (başlık satırı dahil).")
            print(">>> Seçimi tamamlamak için ENTER, iptal için ESC.\n")

            self._guvenli_select_on_screen(self.selection_set)

            secim_sayisi = self.selection_set.Count
            sonuc["secim_sayisi"] = secim_sayisi
            if secim_sayisi == 0:
                print(">>> Hiç obje seçilmedi.")
                return sonuc

            print(f"\n>>> {secim_sayisi} obje seçildi. Koordinatlar okunuyor...")

            hucreler: List[Dict[str, Any]] = []
            for i in range(secim_sayisi):
                try:
                    entity = self._com_retry(lambda idx=i: self.selection_set.Item(idx))
                except Exception:
                    continue
                props = self._read_entity_with_coords(entity)
                if props is None or props.get('text') is None:
                    continue
                temiz_metin = mtext_temizle(props['text']).strip()
                if not temiz_metin:
                    continue
                props['text'] = temiz_metin
                hucreler.append(props)

            sonuc["metin_sayisi"] = len(hucreler)
            if len(hucreler) < 2:
                print(">>> Yeterli koordinatlı metin objesi bulunamadı (en az 2 gerekli).")
                return sonuc

            grid_ham = tablo_hucrelerini_kumele(hucreler, y_esik=y_esik, x_esik=x_esik)
            sonuc["grid_ham"] = grid_ham
            sonuc["grid"] = [
                [(h['text'] if h is not None else None) for h in satir]
                for satir in grid_ham
            ]

            sutun_sayisi = len(grid_ham[0]) if grid_ham else 0
            print(f"\n>>> {len(hucreler)} metin okundu -> {len(grid_ham)} satır x {sutun_sayisi} sütun ızgara.\n")
            for r_idx, satir in enumerate(sonuc["grid"]):
                hucre_metni = " | ".join(h if h is not None else "·" for h in satir)
                print(f"  Satır {r_idx + 1:2d}: {hucre_metni}")

            # ── AŞAMA 2: başlık tespiti + sütun→alan eşleme + önizleme ──
            poz_kayitlari = grid_den_poz_kayitlarini_cikar(grid_ham, sutun_sirasi=sutun_sirasi)
            sonuc["poz_kayitlari"] = poz_kayitlari

            print(f"\n{'-'*50}")
            print(f" SÜTUN TESPİTİ: {poz_kayitlari['sutun_tespiti'].upper()}")
            if poz_kayitlari["sutun_tespiti"] == "basarisiz":
                print(" >>> Başlık satırı (ADET+ÇAP+BOY) otomatik bulunamadı.")
                print(" >>> Bu çağrıya sutun_sirasi=[...] parametresini elle verip tekrar deneyin.")
            else:
                print(f" Sütun→alan eşlemesi: {poz_kayitlari['sutun_alan_haritasi']}")
                print(f" Çap-bazlı toplam sütunları: {poz_kayitlari['toplam_kolon_cap_haritasi']}")
                if poz_kayitlari["belirsiz_toplam_kolonlari"]:
                    print(f" ⚠ BELİRSİZ toplam sütunu (birden fazla farklı çap görüldü): "
                          f"{poz_kayitlari['belirsiz_toplam_kolonlari']}")
                print(f" Atlanan satır (başlık/alt-başlık/boş): {poz_kayitlari['atlanan_satir_sayisi']}")
                print(f"\n ÖNİZLEME ({len(poz_kayitlari['basarili'])} poz kaydı):")
                for kayit in poz_kayitlari["basarili"]:
                    toplam_str = ", ".join(f"Ø{k}={v}" for k, v in kayit["tablo_toplamlari"].items())
                    print(f"   Poz {kayit['poz_no']}: {kayit['adet']} adet Ø{kayit['cap']} "
                          f"x {kayit['boy']}m" + (f"  [tablo: {toplam_str}]" if toplam_str else ""))

                # ── AŞAMA 3: kg/ton hesabı + tablodaki hazır TOPLAM ile karşılaştırma ──
                if poz_kayitlari["basarili"]:
                    hesap = poz_kayitlarindan_hesapla(poz_kayitlari["basarili"])
                    sonuc["hesap"] = hesap

                    print(f"\n{'-'*50}")
                    print(" HESAP — ÇAP BAZLI TOPLAM (DEMIR_AGIRLIK_TABLOSU / TS 708)")
                    print(f" {'Çap':<6} {'Adet':>8} {'Boy(m)':>10} {'Ağırlık(kg)':>12} {'Çubuk(12m)':>10}")
                    for cap in sorted(hesap["cap_ozeti"].keys()):
                        v = hesap["cap_ozeti"][cap]
                        print(f" Ø{cap:<4} {v['adet']:>8,} {v['boy_m']:>10,.2f} "
                              f"{v['agirlik_kg']:>12,.2f} {v['cubuk_adet']:>10,}")
                    g = hesap["genel"]
                    print(f"\n GENEL TOPLAM: {g['adet']:,} adet | {g['boy_m']:,.2f} m | "
                          f"{g['agirlik_kg']:,.2f} kg | {g['agirlik_kg']/1000:,.3f} ton")

                    if hesap["sapma_var_mi"]:
                        print(f"\n ⚠ {len(hesap['sapmalar'])} POZDA SAPMA (hesaplanan ≠ tablodaki TOPLAM):")
                        for s in hesap["sapmalar"]:
                            print(f"   Poz {s['poz_no']} (Ø{s['cap']}): hesaplanan={s['hesaplanan_boy']}m, "
                                  f"tablo={s['tablo_boy']}m, fark={s['fark']}m")
                    else:
                        print("\n ✓ Tüm pozlarda hesaplanan boy, tablodaki TOPLAM ile uyuşuyor.")

                    # get_kolon_filizi_from_table ile UYUMLU üst-seviye alanlar
                    # (Aşama 4 UI handler'ı bu ortak şekli kullanır).
                    sonuc["basarili"] = poz_kayitlarini_demir_bilgisine_cevir(poz_kayitlari["basarili"])
                    sonuc["cap_ozeti"] = hesap["cap_ozeti"]
                    sonuc["toplam_adet"] = hesap["genel"]["adet"]
                    sonuc["toplam_boy_m"] = hesap["genel"]["boy_m"]
                    sonuc["toplam_agirlik_kg"] = hesap["genel"]["agirlik_kg"]
                    sonuc["toplam_cubuk"] = (
                        math.ceil(hesap["genel"]["boy_m"] / _CUBUK_BOYU_M)
                        if hesap["genel"]["boy_m"] else 0
                    )
            print(f"\n{'='*50}\n")

            return sonuc

        except com_error as e:
            if "canceled" in str(e).lower() or "esc" in str(e).lower():
                print(">>> Seçim iptal edildi (ESC).")
                return sonuc
            logger.error(f"Poz bazlı donatı tablosu seçim hatası: {e}")
            raise
        except Exception as e:
            logger.error(f"Poz bazlı donatı tablosu okunurken hata: {e}")
            raise

    def get_beton_kalip_boyutlar(
        self,
        eleman_turu: str,
        birim: str = "cm"
    ) -> Dict[str, Any]:
        """
        Seçilen AutoCAD objesi üzerinden beton elemanı boyutlarını oku.

        Eleman türüne göre beklenen obje tipi ve döndürülen boyutlar:
        Kolon / Kiriş : Kapalı POLYLINE (kesit) → BoundingBox → dim1=boy, dim2=en (m)
        Döşeme / Temel : Kapalı POLYLINE veya HATCH → BoundingBox → dim1=uzunluk, dim2=genişlik (m)
        Perde Duvar : LINE veya POLYLINE (eksen) → Length → dim1=uzunluk (m), dim2=0

        Neyi çözüyoruz?
        Kullanıcının boyutları elle girmek yerine doğrudan AutoCAD kesitini
        veya eksen çizgisini tıklayarak form alanlarını otomatik doldurması.

        Nasıl test ederiz?
        Connector bağlı durumdayken eleman_turu="Kolon", birim="cm" ile çağır,
        AutoCAD'de 50×60 cm boyutlarında bir dikdörtgen seçince
        dim1=0.50, dim2=0.60 dönmeli.

        Args:
            eleman_turu : "Kolon", "Kiriş", "Döşeme", "Temel", "Perde Duvar"
            birim : AutoCAD çizim birimi — "mm", "cm" veya "m"

        Returns:
            Dict:
                dim1 (float) — Boyut 1 (m cinsinden)
                dim2 (float) — Boyut 2 (m cinsinden); Perde Duvar = 0.0
                entity_type (str) — Seçilen AutoCAD obje tipi
                katman (str) — Objenin bulunduğu katman
                iptal (bool) — ESC ile iptal edildiyse True
                hata (str) — Hata açıklaması (varsa)
        """
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

        # Birim → metre dönüşüm katsayısı
        birim_katsayi = {"mm": 1000.0, "cm": 100.0, "m": 1.0}.get(birim, 100.0)

        _bos = {
            "dim1": 0.0, "dim2": 0.0,
            "entity_type": "", "katman": "",
            "iptal": True, "hata": ""
        }

        # Eleman türüne göre kullanıcı yönlendirme mesajları
        mesaj_haritasi = {
            "Kolon": "Kolon KESİT çizgisini (kapalı dikdörtgen) seçin → ENTER",
            "Kiriş": "Kiriş KESİT çizgisini (kapalı dikdörtgen) seçin → ENTER",
            "Döşeme": "Döşeme ALANINI (kapalı polyline veya hatch) seçin → ENTER",
            "Temel": "Temel ALANINI (kapalı polyline) seçin → ENTER",
            "Perde Duvar": "Perde duvar EKSEN çizgisini (line/polyline) seçin → ENTER",
        }
        mesaj = mesaj_haritasi.get(eleman_turu, "Elemanı seçin → ENTER")

        try:
            self._autocad_one_getir()
            self._selection_set_temizle()

            ss_adi = f"BetonKalipSecim_{id(self)}"
            try:
                self.aktif_cizim.SelectionSets.Item(ss_adi).Delete()
            except Exception:
                pass

            self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

            print(f"\n{'='*55}")
            print(f" BETON & KALIP — {eleman_turu.upper()} Boyut Okuma")
            print(f"{'='*55}")
            print(f">>> {mesaj}")
            print(f">>> Çizim birimi: {birim} (dönüşüm: 1 {birim} = {1/birim_katsayi:.4f} m)")
            print(f">>> İptal için ESC tuşuna basın.\n")

            self._guvenli_select_on_screen(self.selection_set)

            if self.selection_set.Count == 0:
                print(">>> Hiç obje seçilmedi (ESC veya boş seçim).")
                return _bos

            # Sadece ilk objeyi al (tek eleman boyutu bekleniyor)
            entity = self._com_retry(lambda: self.selection_set.Item(0))
            entity_type = entity.ObjectName
            katman = entity.Layer

            print(f">>> Seçilen obje: {entity_type} | Katman: {katman}")

            dim1 = 0.0
            dim2 = 0.0
            hata = ""

            # ── Strateji A: GetBoundingBox (Kolon/Kiriş/Döşeme/Temel için) ──
            if eleman_turu in ("Kolon", "Kiriş", "Döşeme", "Temel"):
                try:
                    result = self._com_retry(lambda: entity.GetBoundingBox())
                    if result and len(result) == 2:
                        min_pt, max_pt = result
                        dx = abs(max_pt[0] - min_pt[0]) / birim_katsayi
                        dy = abs(max_pt[1] - min_pt[1]) / birim_katsayi
                        # dim1 = uzun kenar, dim2 = kısa kenar (büyük→küçük sırala)
                        dim1 = round(max(dx, dy), 4)
                        dim2 = round(min(dx, dy), 4)
                        print(
                            f">>> BoundingBox: {dx*birim_katsayi:.1f}×{dy*birim_katsayi:.1f} {birim}"
                            f" → {dim1:.4f}×{dim2:.4f} m"
                        )
                    else:
                        hata = "GetBoundingBox geçerli değer döndürmedi."
                except Exception as e:
                    # Fallback: entity.Area üzerinden kare tahmin
                    try:
                        alan_ham = entity.Area
                        kenar = math.sqrt(alan_ham) / birim_katsayi
                        dim1 = round(kenar, 4)
                        dim2 = round(kenar, 4)
                        hata = f"BoundingBox hatası ({e}), Alan'dan tahmin edildi."
                        print(f">>> [Fallback] Area={alan_ham:.2f} → {dim1:.4f}×{dim2:.4f} m")
                    except Exception as e2:
                        hata = f"Boyut okunamadı: {e2}"

            # ── Strateji B: Length (Perde Duvar için) ──
            elif eleman_turu == "Perde Duvar":
                try:
                    uzunluk_ham = entity.Length
                    dim1 = round(uzunluk_ham / birim_katsayi, 4)
                    dim2 = 0.0
                    print(f">>> Uzunluk: {uzunluk_ham:.2f} {birim} → {dim1:.4f} m")
                except Exception as e:
                    hata = f"Uzunluk okunamadı: {e}"

            # Yeşile boya (başarılı okuma)
            if not hata:
                self._objeyi_renklendir(entity, AcadColor.GREEN)
            else:
                self._objeyi_renklendir(entity, AcadColor.YELLOW)

            try:
                self.aktif_cizim.Regen(1)
            except Exception:
                pass

            if dim1 == 0.0 and not hata:
                hata = "Boyut sıfır döndü — obje tipi uygun olmayabilir."

            return {
                "dim1": dim1,
                "dim2": dim2,
                "entity_type": entity_type,
                "katman": katman,
                "iptal": False,
                "hata": hata,
            }

        except Exception as e:
            logger.error(f"Beton & Kalıp boyut okuma hatası: {e}")
            sonuc = dict(_bos)
            sonuc["hata"] = str(e)
            return sonuc

    def get_kolon_beton_yazidan(
        self,
        mesaj: str = "Kolon (ve varsa kiriş) boyut yazılarını kutu ile seçin",
    ) -> Dict[str, Any]:
        """
        AutoCAD'de kutu (window/crossing) seçimiyle bir bölgedeki TÜM
        TEXT/MTEXT'leri okuyup kolon boyut yazısı ("SZ07 50/50") olanları
        toplu ayrıştırır — Rev-134 Aşama 2.

        Neyi çözüyoruz?
        Kolon geometrisinden (BoundingBox/Area) gerçek boyut okumak 1/50
        ölçek + mm birim belirsizliği yüzünden güvenilmez (bkz. Rev-133
        debug kanıtı). Kullanıcı bir kat planı bölgesini TEK kutuyla seçer
        (kolon+kiriş etiketleri karışık olabilir), program S/P ile
        başlayanları KOLON sayıp hesaplar, K ile başlayanları (kiriş) ve
        tanımsızları GÜVENLİK KATMANI gereği ATLAR — hesaba katmaz, sadece
        sayılarını bildirir. Renklendirme: kolon=YEŞİL, kiriş=SARI (atlandı),
        tanımsız=GRİ, ayrıştırılamayan yazı=KIRMIZI.

        Nasıl test ederiz?
        Bağlı bir AutoCAD'de kolon+kiriş etiketleri olan bir bölgeyi
        kutuyla seçince: "kolonlar" listesinde SADECE S/P ile başlayanlar,
        "kirisler_atlanan"da K ile başlayanlar, "ozet" alanında kaçının
        atlandığı bilgisi dönmeli. `scratchpad/test_kolon_yazi_ayristirma.py`
        çekirdek ayrıştırma mantığını AutoCAD'siz zaten doğruluyor — bu
        metod sadece seçim/okuma/renklendirme katmanını ekler.

        Args:
            mesaj: Kullanıcıya gösterilecek seçim yönlendirme mesajı.

        Returns:
            dict: kolonlar, kirisler_atlanan, tanimsizlar, basarisizlar
                  (her biri kolon_yazisini_ayristir() sözlüğü + handle/layer),
                  ozet, secim_sayisi, metin_sayisi.
        """
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

        bos_sonuc = {
            "kolonlar": [], "kirisler_atlanan": [], "tanimsizlar": [], "okunamayanlar": [],
            "basarisizlar": [], "ilgisiz_sayisi": 0, "ozet": "Hiç obje seçilmedi.",
            "secim_sayisi": 0, "metin_sayisi": 0,
        }

        try:
            self._autocad_one_getir()
            self._selection_set_temizle()

            ss_adi = f"KolonYaziSecim_{id(self)}"
            try:
                self.aktif_cizim.SelectionSets.Item(ss_adi).Delete()
            except Exception:
                pass

            self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

            print(f"\n{'='*55}")
            print(" KOLON BETON/KALIP — Yazıdan Toplu Okuma")
            print(f"{'='*55}")
            print(f">>> {mesaj}")
            print(">>> Kutuyla (pencere/kesişim) seçip ENTER'a basın.\n")

            self._guvenli_select_on_screen(self.selection_set)

            secim_sayisi = self.selection_set.Count
            if secim_sayisi == 0:
                print(">>> Hiç obje seçilmedi.")
                return bos_sonuc

            print(f">>> {secim_sayisi} obje seçildi. Yazılar ayrıştırılıyor...")

            # Rev-160: burada BOYAMA YOK — mükerrer sorusunda "Hayır" denen
            # elemanın rengi değişmemeli; boyamayı karar sonrası UI yapar
            # (obje_rengi_ayarla, önceki renk geri alınabilir).
            yazilar: List[Dict[str, Any]] = []
            for i in range(secim_sayisi):
                try:
                    entity = self._com_retry(lambda idx=i: self.selection_set.Item(idx))
                except Exception:
                    continue
                props = self._read_entity_props(entity)
                if props is None or props['object_name'] not in ("AcDbText", "AcDbMText"):
                    continue
                if props['text']:
                    yazilar.append({"metin": props['text'], "handle": props['handle'],
                                    "layer": props['layer']})

            sonuc = kolon_secimi_siniflandir(yazilar)
            print(f"\n>>> {sonuc['ozet']} ({sonuc['ilgisiz_sayisi']} ilgisiz metin sessizce atlandı)")
            sonuc.update(secim_sayisi=secim_sayisi, metin_sayisi=len(yazilar) - sonuc["ilgisiz_sayisi"])
            return sonuc

        except Exception as e:
            logger.error(f"Kolon yazıdan toplu okuma hatası: {e}")
            sonuc = dict(bos_sonuc)
            sonuc["ozet"] = f"Hata: {e}"
            return sonuc

    def aralikli_donati_tek_obje_sec(self) -> Dict[str, Any]:
        """Tek bir aralıklı donatı (Ø.../aralık L=...) yazısını AutoCAD'de
        seçtirip ayrıştırır — DÖNGÜSEL seçim modu (bkz. CLAUDE.md Rev-136
        güncelleme: "radye gibi dağınık donatıda aynı demiri iki kez sayma/
        atlama riski").

        Neyi çözüyoruz?
        Kutu seçimi (eski yaklaşım) düzenli/gridli döşemede iyi çalışır ama
        radye gibi dağınık, düzensiz donatıda "hangileri okundu" belirsiz
        kalır. Bu metot HER SEFERİNDE TEK bir yazı seçtirir — çağıran (UI
        katmanı) her seçimden sonra kullanıcıya hemen sonucu gösterip
        mesafe sorabilir, objeyi YEŞİLE boyayabilir (bkz.
        aralikli_donati_isaretle) — döngü boyunca hangi demirlerin alındığı
        çizimde gözle görülür.

        Nasıl test ederiz?
        Gerçek AutoCAD gerektirir (COM bağımlı) — saf ayrıştırma zaten
        aralikli_donati_ayristir() ile AutoCAD'siz test edildi
        (scratchpad/test_aralikli_donati.py), bu metot sadece tek-obje
        seçim/okuma katmanını ekler.

        Returns:
            dict: durum ("bulundu"|"bos_secim"|"ilgisiz"|"gecersiz"),
                  ayrisim (durum="bulundu" ise cap/aralik_cm/boy_cm/
                  handle/layer/temiz_metin dolu, aksi halde None), mesaj.
        """
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

        self._autocad_one_getir()
        self._selection_set_temizle()

        ss_adi = f"AralikliDonatiTekSecim_{id(self)}"
        try:
            self.aktif_cizim.SelectionSets.Item(ss_adi).Delete()
        except Exception:
            pass

        self.selection_set = self.aktif_cizim.SelectionSets.Add(ss_adi)

        print(">>> Tek bir aralıklı donatı yazısı seçin (Ø.../aralık L=...), ENTER'a basın.")
        self._guvenli_select_on_screen(self.selection_set)

        if self.selection_set.Count == 0:
            return {"durum": "bos_secim", "ayrisim": None, "mesaj": "Hiçbir şey seçilmedi."}

        # Kullanıcı yanlışlıkla birden fazla obje seçmiş olabilir — sadece
        # İLK geçerli/eşleşen olanı işle, gerisini sessizce yoksay (tekli
        # seçim modunda "hangi obje" belirsizliğine düşmemek için).
        for i in range(self.selection_set.Count):
            try:
                entity = self._com_retry(lambda idx=i: self.selection_set.Item(idx))
            except Exception:
                continue
            props = self._read_entity_props(entity)
            if props is None or props['object_name'] not in ("AcDbText", "AcDbMText"):
                continue
            if not props['text']:
                continue

            ayrisim = aralikli_donati_ayristir(props['text'])
            if ayrisim.get("ilgisiz"):
                continue

            ayrisim['handle'] = props['handle']
            ayrisim['layer'] = props['layer']

            if not ayrisim["basarili"]:
                return {
                    "durum": "gecersiz", "ayrisim": ayrisim,
                    "mesaj": f"Geçersiz aralıklı donatı yazısı: {ayrisim['hata']}",
                }

            return {"durum": "bulundu", "ayrisim": ayrisim, "mesaj": "Aralıklı donatı bulundu."}

        return {
            "durum": "ilgisiz", "ayrisim": None,
            "mesaj": "Seçilen obje(ler) 'Ø.../aralık L=...' formatında değil.",
        }

    def aralikli_donati_olcu_sec(self) -> Dict[str, Any]:
        """Dağılım mesafesi için TEK bir AutoCAD ölçüsü (DIMENSION) seçtirir (Rev-142).

        Neyi çözüyoruz? Radye ilavesinin yayıldığı genişlik çizimde ölçü
        olarak durur ("400"); elle okuyup yazmak yerine ölçüye tıklanır.
        Değer = Measurement × LinearScaleFactor (ekranda görünen), ölçü
        biriminde döner — metreye çevirme çağıranın işi (birim seçimi UI'da).
        Pencere öne getirme HAFİF sürüm: donatı yazısı seçiminden hemen sonra
        çağrılır, AutoCAD zaten öndedir.
        Nasıl test ederiz? scratchpad/test_aralikli_olcu.py (sahte COM).

        Returns:
            dict: durum ("bulundu"|"bos_secim"|"olcu_degil"|"okunamadi"),
                  handle, obje_tipi, olcu (olcu_mesafesi_ayikla sonucu), mesaj.
        """
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")

        self._autocad_one_getir_hafif()
        self._selection_set_temizle()
        ss_adi = f"AralikliDonatiOlcu_{id(self)}"
        try:
            self.aktif_cizim.SelectionSets.Item(ss_adi).Delete()
        except Exception:
            pass
        self.selection_set = self._mesgul_retry(
            lambda: self.aktif_cizim.SelectionSets.Add(ss_adi), "SelectionSets.Add")

        print(">>> Dağılım mesafesinin ÖLÇÜSÜNÜ (DIMENSION) seçin, ENTER'a basın.")
        self._guvenli_select_on_screen(self.selection_set)
        adet = self._mesgul_retry(lambda: self.selection_set.Count, "selection_set.Count")
        if adet == 0:
            return {"durum": "bos_secim", "handle": None, "obje_tipi": None, "olcu": None,
                    "mesaj": "Hiçbir şey seçilmedi."}

        diger_tipler = []
        for entity in self._secili_objeler():
            try:
                tip = self._mesgul_retry(lambda e=entity: e.ObjectName, "ObjectName")
            except Exception as e:
                logger.error(f"Ölçü seçimi: ObjectName okunamadı: {e}", exc_info=True)
                continue
            if tip not in OLCU_UZUNLUK_TIPLERI:
                diger_tipler.append(tip)
                continue
            try:
                handle = self._mesgul_retry(lambda e=entity: e.Handle, "Handle")
                measurement = self._mesgul_retry(lambda e=entity: e.Measurement, "Measurement")
            except Exception as e:
                logger.error(f"Ölçü okunamadı ({tip}): {e}", exc_info=True)
                return {"durum": "okunamadi", "handle": None, "obje_tipi": tip, "olcu": None,
                        "mesaj": f"Ölçü değeri okunamadı: {e}"}
            # LinearScaleFactor / TextOverride yardımcı bilgi — okunamazsa varsayılan
            try:
                olcek = self._com_retry(lambda e=entity: e.LinearScaleFactor)
            except Exception:
                olcek = 1.0
            try:
                override = self._com_retry(lambda e=entity: e.TextOverride) or ""
            except Exception:
                override = ""
            olcu = olcu_mesafesi_ayikla(measurement, olcek, override)
            if olcu["hata"]:
                return {"durum": "okunamadi", "handle": handle, "obje_tipi": tip, "olcu": olcu,
                        "mesaj": olcu["hata"]}
            return {"durum": "bulundu", "handle": handle, "obje_tipi": tip, "olcu": olcu,
                    "mesaj": "Ölçü okundu."}

        acisal = [t for t in diger_tipler if "Dimension" in (t or "")]
        mesaj = ("Seçilen ölçü uzunluk ölçüsü değil (açı/yarıçap/koordinat)."
                 if acisal else "Seçilen nesne ölçü (DIMENSION) değil.")
        return {"durum": "olcu_degil", "handle": None, "obje_tipi": ",".join(map(str, diger_tipler)),
                "olcu": None, "mesaj": mesaj}

    def komut_satiri_mesaj(self, metin: str) -> None:
        """Genel amaçlı: AutoCAD komut satırına geri bildirim yazar (kullanıcı AutoCAD'de kalır)."""
        try:
            self._mesgul_retry(lambda: self.aktif_cizim.Utility.Prompt(f"\n{metin}\n"), "Prompt")
        except Exception as e:
            logger.error(f"komut_satiri_mesaj hata: {e}", exc_info=True)
        print(f">>> {metin}")

    def aralikli_donati_isaretle(self, handle: str) -> None:
        """Handle'ı verilen objeyi YEŞİLE boyar (döngüsel modda bir demir
        onaylanıp listeye eklenince çağrılır). Orijinal renk
        `_objeyi_renklendir` tarafından `self._orijinal_renkler`'a
        kaydedilir — undo için gerekli (bkz. aralikli_donati_isaret_geri_al).
        """
        try:
            entity = self.aktif_cizim.HandleToObject(handle)
            self._objeyi_renklendir(entity, AcadColor.GREEN)
            self.aktif_cizim.Regen(1)
        except Exception as e:
            self._tk_hata(f"aralikli_donati_isaretle(handle={handle})", e)
            logger.debug(f"Aralıklı donatı işaretlenemedi (handle={handle}): {e}")

    def aralikli_donati_isaret_geri_al(self, handle: str) -> None:
        """Bir handle'ın rengini orijinaline döndürür — döngüsel modda
        "Son Ekleneni Geri Al" veya "İptal" ile çağrılır. `handle`
        `self._orijinal_renkler`'da yoksa (hiç boyanmamışsa) sessizce
        hiçbir şey yapmaz.
        """
        if handle not in self._orijinal_renkler:
            return
        try:
            entity = self.aktif_cizim.HandleToObject(handle)
            entity.Color = self._orijinal_renkler[handle]
            del self._orijinal_renkler[handle]
            self.aktif_cizim.Regen(1)
        except Exception as e:
            self._tk_hata(f"aralikli_donati_isaret_geri_al(handle={handle})", e)
            logger.debug(f"Aralıklı donatı rengi geri alınamadı (handle={handle}): {e}")

    # ── Temel kirişi hata logu (Rev-137) ──
    # Ortak yardımcılar (_com_retry, _read_entity_props, _objeyi_renklendir,
    # _autocad_one_getir...) diğer araçlarda binlerce obje için çağrılır —
    # yutulan hatalar SADECE _tk_teshis bayrağı açıkken (temel kirişi /
    # işaretleme akışı) loglanır, diğer araçların log dosyası şişmez.
    def _tk_aktif(self) -> bool:
        return getattr(self, "_tk_teshis", False)

    def _tk_hata(self, fonksiyon: str, e: Exception) -> None:
        """Yutulan hatayı (sadece teşhis modunda) traceback ile log'a yazar."""
        if self._tk_aktif():
            logger.error(f"[TEMEL KIRISI] {fonksiyon} hata: {e}", exc_info=True)

    @contextmanager
    def _tk_teshis_modu(self, ad: str):
        """Temel kirişi COM akışı boyunca teşhis bayrağını açar."""
        onceki = self._tk_aktif()
        self._tk_teshis = True
        try:
            yield
        finally:
            self._tk_teshis = onceki

    # Handle bazlı yeşil işaretleme genel amaçlıdır — temel kirişi de kullanır.
    def obje_isaretle(self, handle: str) -> None:
        with self._tk_teshis_modu(f"obje_isaretle({handle})"):
            self.aralikli_donati_isaretle(handle)

    def obje_isaret_geri_al(self, handle: str) -> None:
        with self._tk_teshis_modu(f"obje_isaret_geri_al({handle})"):
            self.aralikli_donati_isaret_geri_al(handle)

    # ── Temel Kirişi (SBH) — TOPLU MOD (Rev-137 Aşama 3b, 2026-09-26) ──
    # Kullanıcı AutoCAD'de KALIR: her kiriş için tek SelectOnScreen içinde
    # SBH yazısı + 2 kenar çizgisi + ENTER. Pencere öne getirme SADECE
    # oturum başında bir kez (temel_kirisi_toplu_baslat); geri bildirim ve
    # elle uzunluk AutoCAD komut satırından (Prompt/GetReal) — Qt'ye dönüş
    # yok. Eski iki adımlı akış (her adımda pencere geçişi) takılma
    # şikayeti üzerine TERK EDİLDİ.
    _YAZI_TIPLERI = {"AcDbText", "AcDbMText", "TEXT", "MTEXT"}
    _CIZGI_TIPLERI = {"AcDbLine", "AcDbPolyline", "AcDb2dPolyline", "AcDb3dPolyline"}

    def _secili_objeler(self):
        adet = self._mesgul_retry(lambda: self.selection_set.Count, "selection_set.Count")
        for i in range(adet):
            try:
                obje = self._mesgul_retry(
                    lambda idx=i: self.selection_set.Item(idx), f"selection_set.Item({i})")
            except Exception as e:
                self._tk_hata(f"_secili_objeler/selection_set.Item({i})", e)
                continue
            yield obje

    def temel_kirisi_toplu_baslat(self) -> None:
        """Oturum başı: AutoCAD'i BİR KEZ (hafif modda) öne getirir, seçim
        setini kurar. Döngü içinde (temel_kirisi_kiris_oku) öne getirme YOK."""
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")
        with self._tk_teshis_modu("temel_kirisi_toplu_baslat"):
            self._autocad_one_getir_hafif()
            self._selection_set_temizle()
            ss_adi = f"TemelKirisiToplu_{id(self)}"
            try:
                self.aktif_cizim.SelectionSets.Item(ss_adi).Delete()
            except Exception as e:
                # İlk kullanımda set yoktur ("Key not found") — hata DEĞİL
                logger.info(f"[TEMEL KIRISI] eski seçim seti yok (ilk kullanım, normal): {e}")
            # Add(...)'in DÖNÜŞÜ (AcadSelectionSet) atanıyor — diğer
            # araçlarla (get_kolon_filizi_from_table vb.) birebir aynı desen.
            self.selection_set = self._mesgul_retry(
                lambda: self.aktif_cizim.SelectionSets.Add(ss_adi), "SelectionSets.Add")

    def temel_kirisi_kiris_oku(self) -> Dict[str, Any]:
        """TEK kirişin seçimini (yazı + kenar çizgileri + ENTER) okur ve
        objeleri tipine göre sınıflandırır — karar vermez (bkz. saf
        temel_kirisi_secim_degerlendir).

        Neyi çözüyoruz? Her kiriş tek SelectOnScreen: kullanıcı AutoCAD'den
        hiç çıkmaz. Boş ENTER -> durum="bos_secim" (döngü biter).
        Nasıl test ederiz? scratchpad/test_temel_kirisi_com.py (sahte COM).

        Returns:
            dict: durum ("bos_secim"|"okundu"), yazilar (başarılı SBH
                  ayrışımları, handle dahil), gecersiz_yazilar, cizgiler
                  ([{handle, uzunluk_birim, obje_tipi, hata}]), diger_sayisi.
        """
        with self._tk_teshis_modu("temel_kirisi_kiris_oku"):
            sonuc = self._temel_kirisi_kiris_oku_ic()
            logger.debug(
                f"[TEMEL KIRISI] kiris_oku: durum={sonuc['durum']} "
                f"yazi={[(y.get('ad'), y.get('handle'), y.get('konum')) for y in sonuc['yazilar']]} "
                f"cizgi={[(c['handle'], c['uzunluk_birim'], c.get('bas'), c.get('son')) for c in sonuc['cizgiler']]} "
                f"diger={sonuc['diger_sayisi']}"
            )
            return sonuc

    def _temel_kirisi_kiris_oku_ic(self) -> Dict[str, Any]:
        sonuc: Dict[str, Any] = {
            "durum": "bos_secim", "yazilar": [], "gecersiz_yazilar": [],
            "cizgiler": [], "diger_sayisi": 0,
        }
        try:
            self._mesgul_retry(lambda: self.selection_set.Clear(), "selection_set.Clear")
        except Exception as e:
            self._tk_hata("temel_kirisi_kiris_oku/Clear", e)
        self._guvenli_select_on_screen(self.selection_set)
        adet = self._mesgul_retry(lambda: self.selection_set.Count, "selection_set.Count")
        if adet == 0:
            return sonuc
        sonuc["durum"] = "okundu"

        for entity in self._secili_objeler():
            try:
                obj_name = self._mesgul_retry(lambda e=entity: e.ObjectName, "ObjectName")
            except Exception as e:
                self._tk_hata("temel_kirisi_kiris_oku/ObjectName", e)
                sonuc["diger_sayisi"] += 1
                continue

            if obj_name in self._CIZGI_TIPLERI:
                cizgi = {"handle": None, "uzunluk_birim": 0.0, "obje_tipi": obj_name, "hata": ""}
                try:
                    cizgi["handle"] = self._mesgul_retry(lambda e=entity: e.Handle, "Handle")
                except Exception as e:
                    self._tk_hata("temel_kirisi_kiris_oku/Handle", e)
                try:
                    cizgi["uzunluk_birim"] = float(
                        self._mesgul_retry(lambda e=entity: e.Length, "Length"))
                    if cizgi["uzunluk_birim"] <= 0:
                        cizgi["hata"] = "uzunluk 0"
                except Exception as e:
                    self._tk_hata("temel_kirisi_kiris_oku/Length", e)
                    cizgi["hata"] = f"uzunluk okunamadı: {e}"
                cizgi["bas"], cizgi["son"] = self._tk_cizgi_uclari(entity, obj_name)
                sonuc["cizgiler"].append(cizgi)
                continue

            if obj_name in self._YAZI_TIPLERI:
                props = self._read_entity_props(entity)
                ayrisim = temel_kirisi_ayristir(props["text"] if props else "")
                if ayrisim.get("ilgisiz"):
                    sonuc["diger_sayisi"] += 1
                    continue
                ayrisim["handle"] = props["handle"]
                ayrisim["layer"] = props["layer"]
                ayrisim["konum"] = self._tk_yazi_merkezi(entity)
                if ayrisim["basarili"]:
                    sonuc["yazilar"].append(ayrisim)
                else:
                    sonuc["gecersiz_yazilar"].append(ayrisim)
                continue

            sonuc["diger_sayisi"] += 1
        return sonuc

    def _tk_cizgi_uclari(self, entity, obj_name: str):
        """Çizginin (bas, son) XY uç noktaları; okunamazsa (None, None).
        Tek seçimde birden fazla kiriş / üst üste çift çizgi ayrımı için."""
        try:
            if obj_name == "AcDbLine":
                b = self._mesgul_retry(lambda: entity.StartPoint, "StartPoint")
                s = self._mesgul_retry(lambda: entity.EndPoint, "EndPoint")
                return (float(b[0]), float(b[1])), (float(s[0]), float(s[1]))
            k = list(self._mesgul_retry(lambda: entity.Coordinates, "Coordinates"))
            adim = 2 if obj_name == "AcDbPolyline" else 3
            return (float(k[0]), float(k[1])), (float(k[-adim]), float(k[-adim + 1]))
        except Exception as e:
            self._tk_hata("_tk_cizgi_uclari", e)
            return None, None

    def _tk_yazi_merkezi(self, entity):
        """Yazının sınır kutusu merkezi (x, y); okunamazsa None."""
        try:
            mn, mx = self._mesgul_retry(lambda: entity.GetBoundingBox(), "GetBoundingBox")
            return ((float(mn[0]) + float(mx[0])) / 2.0, (float(mn[1]) + float(mx[1])) / 2.0)
        except Exception as e:
            self._tk_hata("_tk_yazi_merkezi", e)
            return None

    def temel_kirisi_mesaj(self, metin: str) -> None:
        """Geri bildirimi AutoCAD komut satırına yazar (kullanıcı AutoCAD'de kalır)."""
        logger.info(f"[TEMEL KIRISI] komut satırı: {metin}")
        try:
            self._mesgul_retry(lambda: self.aktif_cizim.Utility.Prompt(f"\n{metin}\n"), "Prompt")
        except Exception as e:
            logger.error(f"[TEMEL KIRISI] temel_kirisi_mesaj hata: {e}", exc_info=True)
        print(f">>> {metin}")

    def temel_kirisi_uzunluk_sor(self, istem: str) -> Optional[float]:
        """Elle uzunluk yedeği — AutoCAD komut satırından sayı ister
        (Utility.GetReal). ESC/iptal -> None."""
        try:
            with self._tk_teshis_modu("temel_kirisi_uzunluk_sor"):
                deger = float(self.aktif_cizim.Utility.GetReal(f"\n{istem} "))
            return deger if deger > 0 else None
        except Exception as e:
            logger.info(f"[TEMEL KIRISI] elle uzunluk iptal/hata: {e!r}")
            return None

    def obje_isaretle_hizli(self, handle: str) -> None:
        """Toplu mod yeşil boyama: Regen(1) YOK (tüm çizimi yeniden çizer,
        takılma şüphelisiydi) — sadece o objenin Update()'i."""
        with self._tk_teshis_modu(f"obje_isaretle_hizli({handle})"):
            try:
                entity = self._mesgul_retry(
                    lambda: self.aktif_cizim.HandleToObject(handle), "HandleToObject")
                self._objeyi_renklendir(entity, AcadColor.GREEN)
                try:
                    self._mesgul_retry(lambda: entity.Update(), "Update")
                except Exception as e:
                    self._tk_hata("obje_isaretle_hizli/Update", e)
            except Exception as e:
                self._tk_hata(f"obje_isaretle_hizli(handle={handle})", e)

    def obje_renklendir_hizli(self, handle: str, renk: AcadColor) -> None:
        """obje_isaretle_hizli'nin renk parametreli hali (kiriş: iç yeşil / kenar mavi).
        Orijinal renk ilk boyamada kaydedilir — yeşilden maviye geçişte ezilmez."""
        try:
            entity = self._mesgul_retry(
                lambda: self.aktif_cizim.HandleToObject(handle), "HandleToObject")
            self._objeyi_renklendir(entity, renk)
            self._mesgul_retry(lambda: entity.Update(), "Update")
        except Exception as e:
            logger.error(f"[KIRIS] renklendirilemedi (handle={handle}): {e}", exc_info=True)

    def obje_rengi_ayarla(self, handle: str, renk: Optional[int]) -> Optional[int]:
        """Program rengini ayarlar ve ÖNCEKİ program rengini döndürür (Rev-160).

        Neyi çözüyoruz? Kolon aracı S260'ı kırmızı boyar, perde aracı aynı
        yazıyı camgöbeğine çevirir; perde aracında geri alınca KIRMIZIYA
        (orijinale değil) dönmeli. Bu yüzden her boyama önceki program
        rengini (None = hiç boyanmamış / orijinal) döndürür; geri alma
        obje_rengi_ayarla(handle, onceki) ile yapılır. renk=None -> orijinal
        renk (ilk boyamada _orijinal_renkler'e kaydedilmişti) geri yüklenir.
        Regen YOK, sadece Update (toplu modda takılmasın).
        Nasıl test ederiz? scratchpad/test_kolon_perde_ayrim.py (sahte COM)."""
        program = self.__dict__.setdefault("_program_renkleri", {})
        onceki = program.get(handle)
        if not handle:
            return onceki
        try:
            entity = self._mesgul_retry(lambda: self.aktif_cizim.HandleToObject(handle), "HandleToObject")
            if renk is None:
                if handle in self._orijinal_renkler:
                    orijinal = self._orijinal_renkler.pop(handle)
                    self._mesgul_retry(lambda: setattr(entity, "Color", orijinal), "Color")
                program.pop(handle, None)
            else:
                self._objeyi_renklendir(entity, AcadColor(int(renk)))
                program[handle] = int(renk)
            self._mesgul_retry(lambda: entity.Update(), "Update")
        except Exception as e:
            logger.error(f"[RENK] {handle} -> {renk} ayarlanamadı: {e}", exc_info=True)
        return onceki

    # ── Kiriş (Rev-150 Aşama 2): temel kirişi toplu modu deseni ──
    # Seçim SelectOnScreen ile — OSMODE'a DOKUNULMAZ (nesne yakalama seçimi
    # etkilemez; değiştirmek geri yükleme riskini boşuna açar).
    def kiris_toplu_baslat(self) -> None:
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")
        mesaj_filtresi_kaydet()  # thread başına bir kez; COM çağrılarıyla aynı thread
        self._autocad_one_getir_hafif()
        self._selection_set_temizle()
        ss_adi = f"KirisToplu_{id(self)}"
        try:
            self.aktif_cizim.SelectionSets.Item(ss_adi).Delete()
        except Exception:
            pass  # ilk kullanımda set yoktur — normal
        self.selection_set = self._mesgul_retry(
            lambda: self.aktif_cizim.SelectionSets.Add(ss_adi), "SelectionSets.Add")

    def kiris_oku(self) -> Dict[str, Any]:
        """TEK kirişin seçimini ham okur; karar saf kiris_secim_degerlendir()'de.
        Boş ENTER -> durum="bos_secim".

        Returns:
            dict: durum, yazilar [{handle, metin}], cizgiler [{handle,
                  uzunluk_birim, bas, son, hata}], diger_sayisi.
        """
        sonuc: Dict[str, Any] = {"durum": "bos_secim", "yazilar": [], "cizgiler": [], "diger_sayisi": 0}
        try:
            self._mesgul_retry(lambda: self.selection_set.Clear(), "selection_set.Clear")
        except Exception as e:
            logger.error(f"[KIRIS] Clear hata: {e}", exc_info=True)
        self._guvenli_select_on_screen(self.selection_set)
        if self._mesgul_retry(lambda: self.selection_set.Count, "selection_set.Count") == 0:
            return sonuc
        sonuc["durum"] = "okundu"
        for entity in self._secili_objeler():
            try:
                tip = self._mesgul_retry(lambda e=entity: e.ObjectName, "ObjectName")
            except Exception as e:
                logger.error(f"[KIRIS] ObjectName okunamadı: {e}", exc_info=True)
                sonuc["diger_sayisi"] += 1
                continue
            if tip in self._CIZGI_TIPLERI:
                c = {"handle": None, "uzunluk_birim": 0.0, "bas": None, "son": None, "hata": ""}
                try:
                    c["handle"] = self._mesgul_retry(lambda e=entity: e.Handle, "Handle")
                    c["uzunluk_birim"] = float(self._mesgul_retry(lambda e=entity: e.Length, "Length"))
                except Exception as e:
                    logger.error(f"[KIRIS] çizgi okunamadı: {e}", exc_info=True)
                    c["hata"] = f"okunamadı: {e}"
                c["bas"], c["son"] = self._tk_cizgi_uclari(entity, tip)
                sonuc["cizgiler"].append(c)
            elif tip in self._YAZI_TIPLERI:
                props = self._read_entity_props(entity)
                if props:
                    sonuc["yazilar"].append({"handle": props["handle"], "metin": props["text"]})
            else:
                sonuc["diger_sayisi"] += 1
        logger.info(f"[KIRIS] seçim: yazılar={[(y['handle'], y['metin']) for y in sonuc['yazilar']]} "
                    f"çizgiler={[(c['handle'], c['uzunluk_birim']) for c in sonuc['cizgiler']]} "
                    f"diğer={sonuc['diger_sayisi']}")
        return sonuc

    def komut_satiri_sayi_sor(self, istem: str) -> Optional[float]:
        """Komut satırından pozitif sayı (GetReal). ESC / 0 / negatif -> None;
        meşgul reddi yeniden denenir (ESC sayılmaz)."""
        try:
            deger = float(self._mesgul_retry(
                lambda: self.aktif_cizim.Utility.GetReal(f"\n{istem} "), "GetReal"))
        except Exception as e:
            if self.RPC_E_CALL_REJECTED in self._com_hata_kodlari(e) or isinstance(e, AttributeError):
                raise
            logger.info(f"[KIRIS] sayı girişi iptal: {e!r}")
            return None
        return deger if deger > 0 else None

    def cizim_birimi_oku(self) -> Optional[str]:
        """INSUNITS sistem değişkeninden çizim birimini ("mm"/"cm"/"m") okur.
        Tanımsız/okunamazsa None — UI kullanıcı seçimine düşer."""
        try:
            deger = self.aktif_cizim.GetVariable("INSUNITS")
            logger.info(f"[TEMEL KIRISI] INSUNITS = {deger!r}")
            return INSUNITS_BIRIM.get(int(deger))
        except Exception as e:
            logger.error(f"[TEMEL KIRISI] cizim_birimi_oku hata: {e}", exc_info=True)
            return None

    # ── Perde (Rev-143 Aşama 3): AutoCAD'de kalan toplu döngü ──
    # Temel kirişi toplu modu deseni: öne getirme oturumda BİR KEZ, her perde
    # tek SelectOnScreen (kesit poligonu + düşülecek uç çizgileri + ad yazısı),
    # geri bildirim/teyit komut satırından (Prompt/GetKeyword).
    def perde_toplu_baslat(self) -> None:
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")
        self._autocad_one_getir_hafif()
        self._selection_set_temizle()
        ss_adi = f"PerdeToplu_{id(self)}"
        try:
            self.aktif_cizim.SelectionSets.Item(ss_adi).Delete()
        except Exception:
            pass  # ilk kullanımda set yoktur — normal
        self.selection_set = self._mesgul_retry(
            lambda: self.aktif_cizim.SelectionSets.Add(ss_adi), "SelectionSets.Add")

    def perde_oku(self) -> Dict[str, Any]:
        """TEK perdenin seçimini ham okur; karar saf perde_secimi_degerlendir()'de.

        Neyi çözüyoruz? Kesit poligonu (alan, çevre, kapalılık, köşeler), uç
        çizgileri (uzunluk, köşeler), tarama (alan) ve ad yazısı tek seçimde.
        Boş ENTER -> durum="bos_secim" (döngü biter).
        Nasıl test ederiz? scratchpad/test_perde_secim.py (sahte COM).

        Returns:
            dict: durum ("bos_secim"|"okundu"), objeler [{handle, obje_tipi,
                  alan_birim, kapali, uzunluk_birim, koseler, metin, hata}].
        """
        try:
            self._mesgul_retry(lambda: self.selection_set.Clear(), "selection_set.Clear")
        except Exception as e:
            logger.error(f"[PERDE] Clear hata: {e}", exc_info=True)
        self._guvenli_select_on_screen(self.selection_set)
        adet = self._mesgul_retry(lambda: self.selection_set.Count, "selection_set.Count")
        if adet == 0:
            return {"durum": "bos_secim", "objeler": []}

        objeler = []
        self.perde_gecici_temizle()   # önceki turdan kalan olmasın
        for entity in self._secili_objeler():
            try:
                tip = self._mesgul_retry(lambda e=entity: e.ObjectName, "ObjectName")
            except Exception as e:
                logger.error(f"[PERDE] ObjectName okunamadı: {e}", exc_info=True)
                continue
            if tip == "AcDbBlockReference":
                # Rev-155: ideCAD perde bloğu — orijinale dokunmadan geçici patlat, içeriği oku
                blok_handle = None
                try:
                    blok_handle = self._mesgul_retry(lambda e=entity: e.Handle, "Handle")
                    objeler.extend(self._perde_blok_patlat(entity, blok_handle))
                except Exception as e:
                    logger.error(f"[PERDE] blok ({blok_handle}) patlatılamadı: {e}", exc_info=True)
                    objeler.append({"handle": blok_handle, "obje_tipi": "AcDbPolyline", "alan_birim": 0.0,
                                    "kapali": False, "uzunluk_birim": 0.0, "koseler": [], "metin": "",
                                    "hata": f"blok patlatılamadı: {e}"})
                continue
            objeler.append(self._perde_obje_oku(entity, tip))
        logger.info("[PERDE] seçim: " + str([(o["obje_tipi"], o["handle"], o["alan_birim"],
                                             o["uzunluk_birim"], o["kapali"], o.get("blok_handle"))
                                            for o in objeler]))
        return {"durum": "okundu", "objeler": objeler}

    def _perde_obje_oku(self, entity, tip: str) -> Dict[str, Any]:
        """Tek nesnenin perde için ham verisi (handle, alan, kapalılık, uzunluk, köşeler, yay)."""
        o = {"handle": None, "obje_tipi": tip, "alan_birim": 0.0, "kapali": False,
             "uzunluk_birim": 0.0, "koseler": [], "metin": "", "hata": "", "bulge_var": False}
        ilgili = PERDE_CIZGI_TIPLERI | PERDE_YAZI_TIPLERI | {PERDE_TARAMA_TIPI} | PERDE_EGRI_TIPLERI
        if tip not in ilgili:
            return o
        try:
            o["handle"] = self._mesgul_retry(lambda e=entity: e.Handle, "Handle")
        except Exception as e:
            logger.error(f"[PERDE] Handle okunamadı: {e}", exc_info=True)
        if tip in PERDE_EGRI_TIPLERI:
            return o   # yaylı kontur desteklenmiyor — sadece varlığı bildirilir
        try:
            if tip in PERDE_YAZI_TIPLERI:
                o["metin"] = str(self._mesgul_retry(lambda e=entity: e.TextString, "TextString"))
            elif tip == PERDE_TARAMA_TIPI:
                o["alan_birim"] = float(self._mesgul_retry(lambda e=entity: e.Area, "Area"))
            elif tip == "AcDbLine":
                o["uzunluk_birim"] = float(self._mesgul_retry(lambda e=entity: e.Length, "Length"))
                b = self._mesgul_retry(lambda e=entity: e.StartPoint, "StartPoint")
                s = self._mesgul_retry(lambda e=entity: e.EndPoint, "EndPoint")
                o["koseler"] = [(float(b[0]), float(b[1])), (float(s[0]), float(s[1]))]
            else:  # polyline
                o["kapali"] = bool(self._mesgul_retry(lambda e=entity: e.Closed, "Closed"))
                o["uzunluk_birim"] = float(self._mesgul_retry(lambda e=entity: e.Length, "Length"))
                o["alan_birim"] = float(self._mesgul_retry(lambda e=entity: e.Area, "Area"))
                k = [float(v) for v in self._mesgul_retry(lambda e=entity: e.Coordinates, "Coordinates")]
                adim = 2 if tip == "AcDbPolyline" else 3
                o["koseler"] = [(k[i], k[i + 1]) for i in range(0, len(k) - adim + 1, adim)]
                if tip == "AcDbPolyline" and not o["kapali"]:
                    # Rev-155: zincir modunda yay desteklenmez — bulge'ı tespit et
                    for i in range(len(o["koseler"])):
                        if abs(float(self._mesgul_retry(lambda e=entity, j=i: e.GetBulge(j), "GetBulge"))) > 1e-9:
                            o["bulge_var"] = True
                            break
        except Exception as e:
            # Bozuk sınırlı tarama vb. — sessiz kalmasın
            logger.error(f"[PERDE] {tip} ({o['handle']}) okunamadı: {e}", exc_info=True)
            o["hata"] = f"okunamadı: {e}"
        return o

    def _perde_blok_patlat(self, blok, blok_handle, derinlik: int = 0) -> List[Dict[str, Any]]:
        """Blok referansını GEÇİCİ patlatır (Explode orijinali değiştirmez, kopya üretir),
        iç içe blokları da çözer. Üretilen nesneler self._perde_gecici'de tutulur —
        perde_gecici_temizle() ile silinir. Okunan her nesne gecici=True, blok_handle ile işaretli."""
        if derinlik > 8:
            raise RuntimeError("iç içe blok derinliği 8'i aştı")
        parcalar = self._mesgul_retry(lambda: blok.Explode(), "Explode") or ()
        objeler = []
        for p in parcalar:
            self._perde_gecici.append(p)
            tip = self._mesgul_retry(lambda e=p: e.ObjectName, "ObjectName")
            if tip == "AcDbBlockReference":
                objeler.extend(self._perde_blok_patlat(p, blok_handle, derinlik + 1))
                continue
            o = self._perde_obje_oku(p, tip)
            o["gecici"] = True
            o["blok_handle"] = blok_handle
            objeler.append(o)
        return objeler

    @property
    def _perde_gecici(self) -> list:
        if not hasattr(self, "_perde_gecici_liste"):
            self._perde_gecici_liste = []
        return self._perde_gecici_liste

    def perde_gecici_temizle(self) -> None:
        """Patlatmadan kalan geçici nesneleri siler (her perde turunun sonunda, finally'de)."""
        kalanlar = []
        for nesne in self._perde_gecici:
            try:
                self._mesgul_retry(lambda e=nesne: e.Delete(), "Delete")
            except Exception as e:
                logger.error(f"[PERDE] geçici nesne silinemedi: {e}", exc_info=True)
                kalanlar.append(nesne)
        self._perde_gecici_liste = []
        if kalanlar:
            self.komut_satiri_mesaj(f"UYARI: {len(kalanlar)} geçici perde çizgisi silinemedi — "
                                    "çizimde üst üste kopya kalmış olabilir (U / geri al ile temizleyin).")

    def perde_uc_sec(self) -> List[Any]:
        """Zincir modu ikinci istem: kolona bitişik uç kenarları. Boş ENTER -> [].
        Seçilen nesnelerin handle'ları döner (kontura ait olup olmadığı saf fonksiyonda denetlenir)."""
        self.komut_satiri_mesaj("Kolona bitişik uç kenarlarını seçin (yoksa ENTER):")
        try:
            self._mesgul_retry(lambda: self.selection_set.Clear(), "selection_set.Clear")
        except Exception as e:
            logger.error(f"[PERDE] uç seçimi Clear hata: {e}", exc_info=True)
        self._guvenli_select_on_screen(self.selection_set)
        if self._mesgul_retry(lambda: self.selection_set.Count, "selection_set.Count") == 0:
            return []
        handleler = []
        for entity in self._secili_objeler():
            try:
                handleler.append(self._mesgul_retry(lambda e=entity: e.Handle, "Handle"))
            except Exception as e:
                logger.error(f"[PERDE] uç handle okunamadı: {e}", exc_info=True)
        logger.info(f"[PERDE] uç seçimi: {handleler}")
        return handleler

    def komut_satiri_evet_hayir(self, istem: str, varsayilan: Optional[bool] = None) -> bool:
        """AutoCAD komut satırında Evet/Hayır sorar (kullanıcı AutoCAD'de kalır).
        varsayilan=None: cevap zorunlu (boş ENTER kabul edilmez). varsayilan
        verilirse boş ENTER onu seçer (istemde <Hayir>/<Evet> görünür).
        Meşgul reddi yeniden denenir; ESC / hata / Hayır -> False (güvenli taraf)."""
        bit = 1 if varsayilan is None else 0
        ek = "" if varsayilan is None else (" <Evet>" if varsayilan else " <Hayir>")
        try:
            self._mesgul_retry(
                lambda: self.aktif_cizim.Utility.InitializeUserInput(bit, "Evet Hayir"), "InitializeUserInput")
            cevap = self._mesgul_retry(
                lambda: self.aktif_cizim.Utility.GetKeyword(f"\n{istem} [Evet/Hayir]{ek}: "), "GetKeyword")
        except Exception as e:
            if varsayilan is not None and self.GIRDI_ANAHTAR_HRESULT in self._com_hata_kodlari(e):
                return varsayilan  # bazı sürümler boş ENTER'da hata fırlatır
            logger.info(f"evet/hayır iptal/hata: {e!r}")
            return False
        c = str(cevap or "").strip().lower()
        if not c:
            return bool(varsayilan)
        return c.startswith("e")

    def komut_satiri_secenek(self, istem: str, anahtarlar: str) -> Optional[str]:
        """Komut satırında anahtar kelime seçtirir (Rev-164 saçak: "Halka Serit").
        Boş ENTER / ESC -> None (döngü biter). Meşgul reddi yeniden denenir, ESC sayılmaz.
        "H" yazmak AutoCAD'de tam kelimeyi ("Halka") döndürür."""
        try:
            self._mesgul_retry(
                lambda: self.aktif_cizim.Utility.InitializeUserInput(0, anahtarlar), "InitializeUserInput")
            cevap = self._mesgul_retry(
                lambda: self.aktif_cizim.Utility.GetKeyword(
                    f"\n{istem} [{'/'.join(anahtarlar.split())}] <bitir>: "), "GetKeyword")
        except Exception as e:
            if self.RPC_E_CALL_REJECTED in self._com_hata_kodlari(e) or isinstance(e, AttributeError):
                raise
            logger.info(f"seçenek girişi boş/iptal: {e!r}")
            return None
        c = str(cevap or "").strip()
        return c or None

    # ── Döşeme (Rev-144 Aşama 2, Rev-148 COM sağlamlaştırma): köşe tıklama ──
    # BOUNDARY bu çizimlerde sağlıklı değil — sınırı kullanıcı köşelere
    # tıklayarak gösterir. Döngü AutoCAD'de kalır (perde/temel kirişi deseni).
    # KURAL (Rev-148): döngüdeki HER COM çağrısı zincirin TAMAMIYLA
    # (self.aktif_cizim.Utility.X dahil) _mesgul_retry içinde — ara nesneyi
    # (Utility, ModelSpace) değişkende tutup dışarıda çağırmak reddi kaçırır.
    DOSEME_KATMAN = "METRAJ_DOSEME"
    # Diğer araçlar okunanı YEŞİL (geçersiz kırmızı, atlanan sarı) boyar —
    # döşeme poligonu karışmasın diye MACENTA (Rev-147). Kırmızı: boşluklar.
    DOSEME_RENK = int(AcadColor.MAGENTA)
    DOSEME_OSMODE = 33  # Uç nokta (1) + Kesişim (32)
    # GetPoint/GetKeyword'de InitializeUserInput(128) varken ENTER / yazı girişi
    # bu kodla hata fırlatır (GetInput ile metin okunur); ESC başka kodla gelir.
    GIRDI_ANAHTAR_HRESULT = -2145320928
    RPC_E_CALL_REJECTED = -2147418111

    @staticmethod
    def _com_hata_kodlari(e: Exception) -> set:
        kodlar = set()
        for k in (getattr(e, "hresult", None), (getattr(e, "args", None) or [None])[0]):
            if isinstance(k, int):
                kodlar.add(k)
        ex = getattr(e, "excepinfo", None)
        if ex and len(ex) > 5 and isinstance(ex[5], int):
            kodlar.add(ex[5])
        return kodlar

    def _osmode_oku(self) -> int:
        return int(self._mesgul_retry(lambda: self.aktif_cizim.GetVariable("OSMODE"), "GetVariable(OSMODE)"))

    def _osmode_yaz(self, deger: int) -> None:
        """OSMODE yazar — meşgul reddi yeniden denenir; bazı sürümler VT_I2 ister."""
        try:
            self._mesgul_retry(lambda: self.aktif_cizim.SetVariable("OSMODE", int(deger)), "SetVariable(OSMODE)")
        except Exception as e:
            if self.RPC_E_CALL_REJECTED in self._com_hata_kodlari(e):
                raise
            self._mesgul_retry(
                lambda: self.aktif_cizim.SetVariable("OSMODE", win32com.client.VARIANT(pythoncom.VT_I2, int(deger))),
                "SetVariable(OSMODE, VT_I2)")

    def doseme_toplu_baslat(self) -> None:
        """Döngü başı: filtre kaydı (aynı thread), öne getirme, OSMODE orijinalini
        belirleyip 33 yapma, METRAJ_DOSEME katmanı. Geri yükleme
        doseme_toplu_bitir()'de — çağıran finally içinde çağırmalı.

        OSMODE orijinali (Rev-148 kuralı): oturumdaki İLK döngüde bir kez
        okunur ve ayar dosyasına yazılır. Okunan 33 ise ve dosyada farklı bir
        değer varsa (önceki oturum geri yükleyemeden kapanmış) 33 orijinal
        KABUL EDİLMEZ, kayıtlı değer kullanılır."""
        if not self.bagli:
            raise ConnectionError("AutoCAD'e bağlı değil! Önce baglan() çağırın.")
        mesaj_filtresi_kaydet()
        self._autocad_one_getir_hafif()
        if getattr(self, "_osmode_orijinal", None) is None:
            okunan = self._osmode_oku()
            kayitli = autocad_ayari_oku("osmode_orijinal")
            self._osmode_orijinal = osmode_orijinal_belirle(okunan, kayitli, self.DOSEME_OSMODE)
            if self._osmode_orijinal == okunan:
                autocad_ayari_yaz("osmode_orijinal", okunan)
            logger.info(f"[DOSEME] OSMODE orijinal={self._osmode_orijinal} (okunan={okunan}, kayıtlı={kayitli})")
        self._osmode_yaz(self.DOSEME_OSMODE)
        try:
            self._mesgul_retry(lambda: self.aktif_cizim.Layers.Add(self.DOSEME_KATMAN), "Layers.Add")
        except Exception as e:
            logger.error(f"[DOSEME] katman oluşturulamadı: {e}", exc_info=True)

    def doseme_toplu_bitir(self) -> str:
        """OSMODE'u orijinal değere geri yükler (retry'lı). Başarılıysa "",
        değilse kullanıcıya gösterilecek, GERÇEK değeri içeren mesaj."""
        eski = getattr(self, "_osmode_orijinal", None)
        if eski is None:
            return ""
        try:
            self._osmode_yaz(eski)
            logger.info(f"[DOSEME] OSMODE geri yüklendi: {eski}")
            return ""
        except Exception as e:
            logger.error(f"[DOSEME] OSMODE geri yüklenemedi ({eski}): {e}", exc_info=True)
            return (f"Nesne yakalama ayarı (OSMODE) eski değerine döndürülemedi — AutoCAD meşguldü.\n\n"
                    f"AutoCAD komut satırına OSMODE yazıp {eski} girin.")

    def _kullanici_girdisi(self, fonk, ad: str, anahtarlar: str = "") -> Tuple[str, Any]:
        """GetPoint sonucunu ayırır: ("nokta", (x, y)) | ("enter", None) |
        ("metin", str) | ("esc", None). Meşgul reddi (RPC_E_CALL_REJECTED)
        yeniden denenir; denemeler tükenirse ESC SAYILMAZ, hata yükselir.
        ENTER: InitializeUserInput(128) ile 'anahtar girdi' kodu + boş GetInput.
        anahtarlar (ör. "Bosluk"): AutoCAD anahtar kelimeleri — "B" yazmak
        GetInput'ta tam kelimeyi ("Bosluk") döndürür, sonuç yine ("metin", ...)."""
        try:
            self._mesgul_retry(
                lambda: self.aktif_cizim.Utility.InitializeUserInput(128, anahtarlar), "InitializeUserInput")
            p = self._mesgul_retry(fonk, ad)
            return "nokta", (float(p[0]), float(p[1]))
        except Exception as e:
            kodlar = self._com_hata_kodlari(e)
            if self.RPC_E_CALL_REJECTED in kodlar or isinstance(e, AttributeError):
                raise  # meşgul — kullanıcı girdisi değil
            if self.GIRDI_ANAHTAR_HRESULT in kodlar or "keyword" in str(e).lower():
                try:
                    metin = str(self._mesgul_retry(
                        lambda: self.aktif_cizim.Utility.GetInput(), "GetInput") or "").strip()
                except Exception:
                    metin = ""
                return ("metin", metin) if metin else ("enter", None)
            logger.info(f"[DOSEME] girdi iptal (ESC) kodlar={kodlar}")
            return "esc", None

    @staticmethod
    def _nokta_variant(p):
        return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8,
                                       (float(p[0]), float(p[1]), 0.0))

    def doseme_nokta_al(self, istem: str, baz=None, anahtarlar: str = "") -> Tuple[str, Any]:
        """Köşe noktası ister; baz verilirse ondan lastik çizgi çıkar.
        anahtarlar: istemde [Bosluk] gibi anahtar kelime seçeneği (Rev-159)."""
        if baz is None:
            self._mesgul_retry(lambda: self.aktif_cizim.Utility.Prompt(f"\n{istem} "), "Prompt")
            return self._kullanici_girdisi(lambda: self.aktif_cizim.Utility.GetPoint(), "GetPoint", anahtarlar)
        v = self._nokta_variant(baz)
        return self._kullanici_girdisi(lambda: self.aktif_cizim.Utility.GetPoint(v, f"\n{istem} "), "GetPoint",
                                       anahtarlar)

    def doseme_kose_al(self, baz, istem: str) -> Tuple[str, Any]:
        """Dikdörtgen karşı köşesi (GetCorner) — Rev-146'dan beri döşemede kullanılmıyor."""
        v = self._nokta_variant(baz)
        return self._kullanici_girdisi(lambda: self.aktif_cizim.Utility.GetCorner(v, f"\n{istem} "), "GetCorner")

    def doseme_mod_sor(self) -> str:
        """[D]ikdörtgen / [P]oligon sorusu — Rev-146'dan beri kullanılmıyor."""
        try:
            self._mesgul_retry(lambda: self.aktif_cizim.Utility.InitializeUserInput(0, "Dikdortgen Poligon"),
                               "InitializeUserInput")
            cevap = self._mesgul_retry(lambda: self.aktif_cizim.Utility.GetKeyword(
                "\nDÖŞEME: [D]ikdörtgen / [P]oligon — bitirmek için boş ENTER: "), "GetKeyword")
        except Exception as e:
            if self.GIRDI_ANAHTAR_HRESULT in self._com_hata_kodlari(e):
                return "bitti"
            return "esc"
        c = str(cevap or "").strip().lower()
        return "bitti" if not c else ("P" if c.startswith("p") else "D")

    def doseme_poligon_ciz(self, koseler, renk: int = None) -> str:
        """Kapalı LWPolyline çizer (METRAJ_DOSEME katmanı, varsayılan macenta) ve handle döner."""
        duz: List[float] = []
        for x, y in koseler:
            duz += [float(x), float(y)]
        v = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, duz)
        pl = self._mesgul_retry(
            lambda: self.aktif_cizim.ModelSpace.AddLightWeightPolyline(v), "AddLightWeightPolyline")
        self._mesgul_retry(lambda: setattr(pl, "Closed", True), "Closed")
        try:
            self._mesgul_retry(lambda: setattr(pl, "Layer", self.DOSEME_KATMAN), "Layer")
        except Exception as e:
            logger.error(f"[DOSEME] katman atanamadı: {e}", exc_info=True)
        self._mesgul_retry(lambda: setattr(pl, "Color", int(self.DOSEME_RENK if renk is None else renk)), "Color")
        try:
            self._mesgul_retry(lambda: pl.Update(), "Update")
        except Exception:
            pass
        return str(self._mesgul_retry(lambda: pl.Handle, "Handle"))

    def obje_sil(self, handle: str) -> bool:
        """Handle'ı verilen objeyi çizimden siler (geri al / güncelleme)."""
        if not handle:
            return False
        try:
            self._mesgul_retry(lambda: self.aktif_cizim.HandleToObject(handle).Delete(), "HandleToObject.Delete")
            return True
        except Exception as e:
            logger.error(f"[DOSEME] obje silinemedi ({handle}): {e}", exc_info=True)
            return False

    def get_rebar_summary_dataframe(self, rapor: Dict[str, Any]):
        """
        Demir raporunu pandas DataFrame'e çevir.

        Args:
            rapor: get_rebar_report_from_selection() çıktısı

        Returns:
            Tuple[DataFrame, DataFrame]: (detay_df, ozet_df)
        """
        try:
            import pandas as pd
        except ImportError:
            logger.warning("pandas yüklü değil, DataFrame oluşturulamadı")
            return None, None

        # Detay DataFrame
        detay_rows = []
        for d in rapor["basarili"]:
            detay_rows.append({
                "Metin": d.orijinal_metin,
                "Adet": d.adet,
                "Çap (mm)": d.cap,
                "Boy (cm)": d.boy,
                "Toplam Boy (m)": d.toplam_boy,
                "Birim Ağırlık (kg/m)": d.agirlik_birim,
                "Toplam Ağırlık (kg)": d.toplam_agirlik,
                "Katman": d.katman,
            })

        detay_df = pd.DataFrame(detay_rows) if detay_rows else pd.DataFrame()

        # Özet DataFrame
        ozet_rows = []
        for cap, ozet in sorted(rapor["cap_ozeti"].items()):
            ozet_rows.append({
                "Çap (Ø)": f"Ø{cap}",
                "Adet": ozet["adet"],
                "Toplam Boy (m)": ozet["boy_m"],
                "Birim Ağırlık (kg/m)": ozet["birim_agirlik"],
                "Toplam Ağırlık (kg)": ozet["agirlik_kg"],
            })

        # Genel toplam satırı
        if ozet_rows:
            ozet_rows.append({
                "Çap (Ø)": "TOPLAM",
                "Adet": rapor["toplam_adet"],
                "Toplam Boy (m)": rapor["toplam_boy_m"],
                "Birim Ağırlık (kg/m)": "-",
                "Toplam Ağırlık (kg)": rapor["toplam_agirlik_kg"],
            })

        ozet_df = pd.DataFrame(ozet_rows) if ozet_rows else pd.DataFrame()

        return detay_df, ozet_df

    def calculate_vertical_rebar_unified(self, birim: str = "cm") -> Dict[str, Any]:
        """
        Birleşik Düşey Eleman (Kolon/Perde) Demir Hesaplama.

        Akıllı Tekil/Grup Ayrımı ve Perde "2x" formatı desteği ile çalışır.
        Program seçilen verilere bakarak modu otomatik belirler.

        Metin Sınıflandırma:
            - BAŞLIK: "SB17", "PB055", "KOLON DETAY", "PERDE DETAY" gibi
            - LİSTE: Virgülle ayrılmış benzerler ("SB24,SB31,SB39...")
            - VERİ: Demir bilgisi ("28Ø14 L=442" veya "2x8Ø12 L=420")

        Mod Belirleme:
            - LİSTE varsa → GRUP modu (Başlık + Liste elemanları)
            - LİSTE yoksa, BAŞLIK varsa → TEKİL modu (Tek perde/kolon)

        Perde "2x" Matematiği:
            - "2x8Ø12 L=420" → 2 * 8 = 16 adet Ø12 demir

        Args:
            birim: Boy birimi ("cm" veya "m")

        Returns:
            Dict: Hesaplama sonuçları, mod bilgisi ve DemirBilgisi listesi
        """
        sonuc = {
            "basarili": False,
            "hata": None,
            "mod": None,      # "GRUP" veya "TEKİL"
            "tip": None,      # "KOLON" veya "PERDE"
            "baslik": None,
            "elemanlar": [],
            "donatilar": [],  # Birden fazla donatı satırı olabilir
            "demirler": [],   # DemirBilgisi listesi (UI'a aktarılacak)
            "ozet": {}
        }

        try:
            import pandas as pd
        except ImportError:
            sonuc["hata"] = "pandas yüklü değil"
            return sonuc

        # Bağlantı kontrolü
        if not self.bagli:
            self.baglan()

        print("\n" + "="*60)
        print(" DÜŞEY ELEMAN DEMİR HESAPLAMA (Kolon/Perde)")
        print("="*60)
        print("\n AutoCAD'de metinleri seçin:")
        print(" • BAŞLIK: Eleman adı (SB17, PB055, vb.)")
        print(" • LİSTE (opsiyonel): Benzerler (SB24,SB31,...)")
        print(" • DONATI: Demir bilgisi (28Ø14 L=442 veya 2x8Ø12 L=420)")
        print("-"*60)

        # AutoCAD'i aktif hale getir
        try:
            # 1. Visible ayarla
            self.acad_app.Visible = True
            time.sleep(0.2)

            # 2. WindowState ayarla
            try:
                self.acad_app.WindowState = 3  # Maximize
            except Exception:
                pass
            time.sleep(0.2)

            # 3. Çizimi aktifleştir
            try:
                self.aktif_cizim.Activate()
            except Exception:
                pass
            time.sleep(0.2)

            # 4. REGEN komutu gönder (AutoCAD'i zorla aktifleştirir)
            try:
                self.aktif_cizim.SendCommand("REGEN\n")
            except Exception:
                pass
            time.sleep(0.5)

            # 5. win32gui ile öne getir
            self._autocad_one_getir()
            time.sleep(0.3)

        except Exception as e:
            logger.warning(f"AutoCAD aktifleştirme hatası: {e}")

        print(" AutoCAD'e geçiliyor...")
        time.sleep(0.5)  # _autocad_one_getir() zaten ~1.3sn bekliyor

        # Selection Set oluştur
        ss_name = f"DuseyEleman_{int(time.time())}"
        try:
            ss = self.aktif_cizim.SelectionSets.Add(ss_name)
        except Exception:
            try:
                ss = self.aktif_cizim.SelectionSets.Item(ss_name)
                ss.Clear()
            except Exception:
                ss = self.aktif_cizim.SelectionSets.Add(f"DuseyEleman_{id(self)}")

        try:
            # Kullanıcı seçimi - invisible hatasına karşı korumalı
            self._guvenli_select_on_screen(ss)
            secim_sayisi = ss.Count
            print(f"\n>>> {secim_sayisi} obje seçildi")

            if secim_sayisi == 0:
                sonuc["hata"] = "Hiç obje seçilmedi"
                return sonuc

            # Metin objelerini SEÇİM SIRASINA göre topla + entity ref kaydet
            metinler = []
            metin_entityleri = []  # Renklendirme için entity referansları
            for i in range(ss.Count):
                entity = ss.Item(i)
                props = self._read_entity_props(entity)
                if props is None:
                    continue
                if props['object_name'] in ["AcDbText", "AcDbMText"]:
                    text = props['text']
                    if text is None:
                        logger.debug(f"Metin okunamadı (index: {i}), atlanıyor")
                        continue
                    text = text.strip()
                    # MText özel karakterlerini temizle
                    temiz = re.sub(r'\\[A-Za-z];?|\\P|[{}]', '', text).strip()
                    if temiz:
                        metinler.append(temiz)
                        metin_entityleri.append(props['entity'])

            if len(metinler) == 0:
                sonuc["hata"] = "Seçimde metin objesi bulunamadı"
                return sonuc

            print(f"\n Seçilen metinler (SIRASINA GÖRE):")
            for i, m in enumerate(metinler, 1):
                print(f"  {i}. \"{m}\"")

            # ════════════════════════════════════════════════════════════
            # 1. SEÇİM SIRASINA GÖRE GRUPLAMA
            # ════════════════════════════════════════════════════════════
            # Mantık: Kullanıcı sırayla seçer:
            #   1. Eleman adı (PB055, SB01, veya "SB15 KOLON DETAYI")
            #   2. [Opsiyonel] Benzerler listesi (SB16,SB18,SB19...)
            #   3. Donatı(lar) (28Ø14 L=442)
            #   4. Sonraki eleman adı... (döngü devam eder)

            # === REGEX KALIPLARI ===
            eleman_pattern = re.compile(r'(S[BK]|P[BK])\s*(\d+)', re.IGNORECASE)
            detayi_pattern = re.compile(r'(KOLON|PERDE)\s*DETAYI', re.IGNORECASE)
            veri_pattern = re.compile(
                r'(?:(\d+)\s*[xX*]\s*)?(\d+)\s*[ØøƒφΦ∅]\s*(\d+).*?[Ll]\s*=\s*(\d+(?:[.,]\d+)?)',
                re.IGNORECASE
            )
            veri_pattern_autocad = re.compile(
                r'(?:(\d+)\s*[xX*]\s*)?(\d+)\s*%%[cC]\s*(\d+).*?[Ll]\s*=\s*(\d+(?:[.,]\d+)?)',
                re.IGNORECASE
            )

            # === GRUPLARI OLUŞTUR ===
            gruplar = []  # Her grup: {"lider": str, "benzerler": [], "donatilar": [], "tip": str, "mod": str}
            aktif_grup = None

            print(f"\n SEÇİM SIRASINA GÖRE GRUPLAMA:")
            print(f" ─────────────────────────────────")

            for i, metin in enumerate(metinler, 1):
                # Metin tipi belirleme
                is_donati = veri_pattern.search(metin) or veri_pattern_autocad.search(metin)
                is_detayi = detayi_pattern.search(metin)
                is_liste = ',' in metin and eleman_pattern.search(metin)
                is_eleman = eleman_pattern.search(metin) and not is_liste

                if is_donati:
                    # DONATI → Aktif gruba ekle
                    if aktif_grup:
                        aktif_grup["donatilar"].append(metin)
                        print(f"  {i}. DONATI → {aktif_grup['lider']}'e eklendi: \"{metin[:35]}...\"")
                    else:
                        print(f"  {i}. DONATI (grup yok, atlandı): \"{metin[:35]}\"")

                elif is_detayi or is_eleman:
                    # YENİ ELEMAN ADI → Yeni grup başlat
                    match = eleman_pattern.search(metin)
                    if match:
                        eleman_adi = f"{match.group(1).upper()}{match.group(2)}"

                        # Tip belirleme
                        if eleman_adi.startswith('PB') or eleman_adi.startswith('PK') or 'PERDE' in metin.upper():
                            tip = "PERDE"
                        else:
                            tip = "KOLON"

                        # Mod belirleme
                        mod = "GRUP" if is_detayi else "TEKİL"

                        # Yeni grup oluştur
                        aktif_grup = {
                            "lider": eleman_adi,
                            "benzerler": [],
                            "donatilar": [],
                            "tip": tip,
                            "mod": mod
                        }
                        gruplar.append(aktif_grup)

                        if is_detayi:
                            print(f"  {i}. YENİ GRUP: {eleman_adi} ({tip} - DETAYI var)")
                        else:
                            print(f"  {i}. YENİ TEKİL: {eleman_adi} ({tip})")

                elif is_liste:
                    # LİSTE → Aktif gruba benzerler ekle
                    if aktif_grup:
                        parcalar = metin.split(',')
                        eklenen = 0
                        for parca in parcalar:
                            match = eleman_pattern.search(parca.strip())
                            if match:
                                eleman_adi = f"{match.group(1).upper()}{match.group(2)}"
                                if eleman_adi != aktif_grup["lider"] and eleman_adi not in aktif_grup["benzerler"]:
                                    aktif_grup["benzerler"].append(eleman_adi)
                                    eklenen += 1
                        aktif_grup["mod"] = "GRUP"  # Liste varsa grup moduna geç
                        print(f"  {i}. LİSTE → {aktif_grup['lider']}'e {eklenen} benzer eklendi")
                    else:
                        print(f"  {i}. LİSTE (grup yok, atlandı)")

                else:
                    print(f"  {i}. TANINAMADI: \"{metin[:40]}\"")

            # === GRUP KONTROLÜ ===
            if not gruplar:
                sonuc["hata"] = "Hiç eleman grubu oluşturulamadı!\nLütfen önce eleman adı (SB15, PB055) seçin."
                return sonuc

            # Donatısız grupları kontrol et
            bos_gruplar = [g["lider"] for g in gruplar if not g["donatilar"]]
            if bos_gruplar:
                print(f"\n  Donatısız elemanlar: {bos_gruplar}")

            print(f"\n  TOPLAM: {len(gruplar)} eleman/grup oluşturuldu")

            # ════════════════════════════════════════════════════════════
            # 2. SONUÇ YAPISI GÜNCELLE
            # ════════════════════════════════════════════════════════════
            sonuc["gruplar"] = gruplar
            sonuc["mod"] = "ÇOKLU" if len(gruplar) > 1 else gruplar[0]["mod"]

            # İlk grup bilgilerini ana sonuca yaz (geriye uyumluluk)
            ilk_grup = gruplar[0]
            tum_elemanlar = [ilk_grup["lider"]] + ilk_grup["benzerler"]
            eleman_tipi = ilk_grup["tip"]

            # ════════════════════════════════════════════════════════════
            # 3. HER GRUP İÇİN DONATI PARSE VE HESAPLAMA
            # ════════════════════════════════════════════════════════════
            print(f"\n HESAPLAMA:")
            print(f" ─────────────────────────────────")

            demir_listesi = []  # DemirBilgisi nesneleri (tüm gruplardan)
            genel_toplam_adet = 0
            genel_toplam_boy = 0.0
            genel_toplam_agirlik = 0.0
            cap_ozeti = {}  # Çap bazlı özet
            toplam_eleman_sayisi = 0

            for grup in gruplar:
                lider = grup["lider"]
                benzerler = grup["benzerler"]
                donatilar_raw = grup["donatilar"]
                tip = grup["tip"]

                # Gruptaki tüm elemanlar
                grup_elemanlari = [lider] + benzerler
                toplam_eleman_sayisi += len(grup_elemanlari)

                if not donatilar_raw:
                    print(f"  {lider}: Donatı yok, atlandı!")
                    continue

                # Donatıları parse et
                grup_donatilari = []
                for veri in donatilar_raw:
                    match = veri_pattern.search(veri)
                    if not match:
                        match = veri_pattern_autocad.search(veri)

                    if match:
                        carpan = int(match.group(1)) if match.group(1) else 1
                        taban_adet = int(match.group(2))
                        cap = int(match.group(3))
                        boy_str = match.group(4).replace(',', '.')
                        boy = float(boy_str)

                        gercek_adet = carpan * taban_adet

                        if birim.lower() == "cm":
                            boy_m = boy / 100.0
                        else:
                            boy_m = boy

                        agirlik_birim = DEMIR_AGIRLIK_TABLOSU.get(cap, 0.0)

                        grup_donatilari.append({
                            "orijinal": veri,
                            "gercek_adet": gercek_adet,
                            "cap": cap,
                            "boy": boy,
                            "boy_m": boy_m,
                            "agirlik_birim": agirlik_birim
                        })

                if not grup_donatilari:
                    print(f"  {lider}: Donatı parse edilemedi!")
                    continue

                # Her eleman için her donatıyı hesapla
                for eleman_adi in grup_elemanlari:
                    for donati in grup_donatilari:
                        toplam_boy = donati["gercek_adet"] * donati["boy_m"]
                        toplam_agirlik = toplam_boy * donati["agirlik_birim"]

                        demir = DemirBilgisi(
                            handle=f"{eleman_adi}_{donati['cap']}",
                            orijinal_metin=f"{eleman_adi}: {donati['orijinal']}",
                            adet=donati["gercek_adet"],
                            cap=donati["cap"],
                            boy=donati["boy"],
                            toplam_boy=toplam_boy,
                            agirlik_birim=donati["agirlik_birim"],
                            toplam_agirlik=toplam_agirlik,
                            katman=f"{tip}_{eleman_adi}",
                            gecerli=True,
                            eleman_tipi=tip.capitalize()
                        )
                        demir_listesi.append(demir)

                        genel_toplam_adet += donati["gercek_adet"]
                        genel_toplam_boy += toplam_boy
                        genel_toplam_agirlik += toplam_agirlik

                        cap = donati["cap"]
                        if cap not in cap_ozeti:
                            cap_ozeti[cap] = {"adet": 0, "boy_m": 0.0, "agirlik_kg": 0.0}
                        cap_ozeti[cap]["adet"] += donati["gercek_adet"]
                        cap_ozeti[cap]["boy_m"] += toplam_boy
                        cap_ozeti[cap]["agirlik_kg"] += toplam_agirlik

                print(f"  {lider}: {len(grup_elemanlari)} eleman × {len(grup_donatilari)} donatı")

            if not demir_listesi:
                sonuc["hata"] = "Hiç demir hesaplanamadı! Donatı bilgisi eksik olabilir."
                return sonuc

            sonuc["demirler"] = demir_listesi
            sonuc["baslik"] = gruplar[0]["lider"]
            sonuc["tip"] = gruplar[0]["tip"]
            sonuc["elemanlar"] = [g["lider"] for g in gruplar]

            # Çubuk adetleri
            for cap in cap_ozeti:
                cap_ozeti[cap]["cubuk_adet"] = math.ceil(cap_ozeti[cap]["boy_m"] / 12.0)

            genel_cubuk = math.ceil(genel_toplam_boy / 12.0)

            sonuc["ozet"] = {
                "mod": sonuc["mod"],
                "grup_sayisi": len(gruplar),
                "eleman_sayisi": toplam_eleman_sayisi,
                "toplam_adet": genel_toplam_adet,
                "toplam_boy_m": genel_toplam_boy,
                "toplam_agirlik_kg": genel_toplam_agirlik,
                "toplam_agirlik_ton": genel_toplam_agirlik / 1000,
                "cubuk_adet": genel_cubuk,
                "cap_ozeti": cap_ozeti
            }

            sonuc["basarili"] = True

            # ════════════════════════════════════════════════════════════
            # SONUÇ RAPORU
            # ════════════════════════════════════════════════════════════
            print(f"\n{'='*60}")
            print(f" DEMİR METRAJ RAPORU ({sonuc['mod']} MOD)")
            print(f"{'='*60}")
            print(f" Grup Sayısı    : {len(gruplar)}")
            print(f" Toplam Eleman  : {toplam_eleman_sayisi} adet")

            # Grup detayları
            print(f"\n GRUP DETAYLARI:")
            for i, grup in enumerate(gruplar, 1):
                eleman_sayisi = 1 + len(grup["benzerler"])
                donati_sayisi = len(grup["donatilar"])
                mod_str = "GRUP" if grup["benzerler"] else "TEKİL"
                print(f"  {i}. {grup['lider']} ({grup['tip']}) - {mod_str}")
                print(f"     Eleman: {eleman_sayisi}, Donatı: {donati_sayisi}")

            print(f"\n ─────────────────────────────────")
            print(f" Toplam Demir Adedi  : {genel_toplam_adet:,}")
            print(f" Toplam Boy          : {genel_toplam_boy:,.2f} m")
            print(f" Toplam Ağırlık      : {genel_toplam_agirlik:,.2f} kg")
            print(f" ─────────────────────────────────")

            # Çap bazlı dağılım
            print(f"\n ÇAP BAZLI DAĞILIM:")
            print(f" {'Çap':<6} {'Adet':>8} {'Boy(m)':>10} {'Ağırlık(kg)':>12} {'Çubuk':>8}")
            print(f" {'-'*50}")
            for cap in sorted(cap_ozeti.keys()):
                ozet = cap_ozeti[cap]
                print(f" Ø{cap:<4} {ozet['adet']:>8,} {ozet['boy_m']:>10,.2f} {ozet['agirlik_kg']:>12,.2f} {ozet['cubuk_adet']:>8,}")

            print(f"\n TOPLAM ÇUBUK : {genel_cubuk:,} çubuk")
            print(f"{'='*60}\n")

            # Kayıtlı metin entity'lerini yeşile boya (tekrar tarama yok)
            for entity in metin_entityleri:
                try:
                    self._objeyi_renklendir(entity, AcadColor.GREEN)
                except Exception:
                    pass

            self.aktif_cizim.Regen(1)

            return sonuc

        except com_error as e:
            if "canceled" in str(e).lower() or "esc" in str(e).lower():
                print(">>> Seçim iptal edildi (ESC).")
                sonuc["hata"] = "Seçim iptal edildi"
                return sonuc
            logger.error(f"Düşey eleman seçim hatası: {e}")
            sonuc["hata"] = str(e)
            return sonuc
        except Exception as e:
            logger.error(f"Düşey eleman hesaplama hatası: {e}")
            sonuc["hata"] = str(e)
            return sonuc
        finally:
            # Selection set temizle
            try:
                ss.Delete()
            except Exception:
                pass

    # Geriye uyumluluk için eski fonksiyon adını koru
    def calculate_all_grouped_columns(self, birim: str = "cm") -> Dict[str, Any]:
        """Geriye uyumluluk için - yeni fonksiyona yönlendir."""
        return self.calculate_vertical_rebar_unified(birim=birim)

    # ========================================================================
    # LISP MOTOR METODLARI
    # ========================================================================

    def lisp_calistir(self, lsp_dosya_adi: str, bekle: float = 0.5) -> bool:
        """
        Bir LISP dosyasını AutoCAD'e yükler ve komutunu çalıştırır.

        Akış:
            1. APPLOAD komutuyla .lsp dosyasını yükle
            2. LISP komut adını (dosya adından türet) çalıştır
            3. bekle sn sonra lisp_sonuc_oku() ile sonucu al

        Args:
            lsp_dosya_adi: .lsp dosyasının tam yolu (örn. "C:/...duvar_alan.lsp")
            bekle: Komut sonrası bekleme süresi (saniye)

        Returns:
            True: komut gönderildi, False: bağlantı yok
        """
        if not self.bagli:
            logger.warning("AutoCAD bağlantısı yok — LISP çalıştırılamadı.")
            return False

        # AutoCAD penceresini öne getir — LISP komutları ssget ile interaktif
        # seçim beklediği için kullanıcı pencereyi GÖRMEDEN seçim yapamaz.
        # Diğer tüm AutoCAD aksiyonları (get_beton_kalip_boyutlar vb.) bunu
        # zaten çağırıyordu, lisp_calistir unutulmuştu (Rev-133 ek düzeltme).
        self._autocad_one_getir()

        try:
            # LISP komut adını dosya adından çıkar: "duvar_alan.lsp" → "c:DUVAR-ALAN"
            # (defun c:DUVAR-ALAN ...) → gerçek AutoLISP sembol adı "C:DUVAR-ALAN"
            # olur, bu yüzden (c:duvar-alan) şeklinde DOĞRUDAN LISP fonksiyonu
            # olarak da çağrılabilir (AutoLISP sembolleri case-insensitive).
            import os
            base = os.path.splitext(os.path.basename(lsp_dosya_adi))[0]
            komut_suffix = base.replace("_", "-").lower()

            # Yolu AutoCAD için düzelt (ters eğik çizgi + tırnak)
            lsp_yolu_acad = lsp_dosya_adi.replace("\\", "/")

            # (load ...) + (c:...) çağrısı TEK bir (progn ...) içinde, TEK
            # SendCommand ile atomik olarak gönderiliyor. Önceki sürümde bu
            # ikisi ayrı SendCommand çağrısıydı ve arada sabit 0.2 sn
            # bekleniyordu — dosya yüklemesi bu sürede bitmezse AutoCAD henüz
            # tanımlanmamış komutu SESSİZCE yok sayıyordu, LISP hiç
            # çalışmıyordu, sonuç dosyası da hiç yazılmıyordu ("Sonuç dosyası
            # bulunamadı" hatası — Rev-133 ek düzeltme #3). (progn ...) ile
            # load bitmeden fonksiyon çağrısı asla başlamaz.
            atomik_cmd = f'(progn (load "{lsp_yolu_acad}") (c:{komut_suffix}))\n'
            self.aktif_cizim.SendCommand(atomik_cmd)
            time.sleep(bekle)

            logger.info(f"LISP çalıştırıldı: c:{komut_suffix} ({lsp_yolu_acad})")
            return True

        except Exception as e:
            logger.error(f"LISP çalıştırma hatası: {e}")
            return False

    def lisp_sonuc_oku(self) -> Dict[str, Any]:
        """
        %TEMP%\\imp_metraj.txt dosyasından LISP sonucunu okur.

        LISP rutinleri bu dosyaya JSON yazar.
        Python burada okur, parse eder ve döndürür.

        Returns:
            dict: Parse edilmiş sonuç (hata durumunda {"hata": "..."})
        """
        import os
        import json as _json

        sonuc_yolu = os.path.join(os.environ.get("TEMP", ""), "imp_metraj.txt")
        if not os.path.exists(sonuc_yolu):
            return {"hata": "Sonuç dosyası bulunamadı — LISP henüz çalışmadı mı?"}

        try:
            with open(sonuc_yolu, "r", encoding="utf-8") as f:
                icerik = f.read().strip()
            return self._parse_lisp_sonuc(icerik)
        except Exception as e:
            logger.error(f"LISP sonuç okuma hatası: {e}")
            return {"hata": str(e)}

    def _parse_lisp_sonuc(self, json_str: str) -> Dict[str, Any]:
        """
        LISP'in yazdığı JSON string'ini parse eder.
        AutoLISP'in rtos() fonksiyonu ondalık ayracı olarak nokta kullanır,
        bu yüzden direkt json.loads() çalışır.

        Args:
            json_str: LISP'ten gelen JSON string

        Returns:
            dict: Parse edilmiş veri
        """
        import json as _json
        try:
            return _json.loads(json_str)
        except _json.JSONDecodeError as e:
            logger.warning(f"JSON parse hatası: {e} | İçerik: {json_str[:200]}")
            return {"hata": f"JSON parse hatası: {e}", "ham": json_str}

    def katman_degisken_set(self, katman_dict: Dict[str, str]) -> None:
        """
        LISP global katman değişkenlerini AutoCAD'de ayarlar.

        Katman adları Python'dan LISP'e geçirilir, böylece LISP
        kendi varsayılanları yerine projeye özel isimleri kullanır.

        Örnek kullanım:
            connector.katman_degisken_set({
                "*IMP_KATMAN_DUVAR*": "DUVAR-BETON",
                "*IMP_KATMAN_KAPI*": "A-DOOR",
            })

        Args:
            katman_dict: {lisp_değişken_adı: katman_adı} sözlüğü
        """
        if not self.bagli:
            return

        for degisken, deger in katman_dict.items():
            try:
                # AutoLISP: (setq *IMP_KATMAN_DUVAR* "DUVAR")
                lisp_expr = f'(setq {degisken} "{deger}")\n'
                self.aktif_cizim.SendCommand(lisp_expr)
                logger.debug(f"Katman değişkeni ayarlandı: {degisken} = {deger}")
            except Exception as e:
                logger.warning(f"Katman değişkeni ayarlanamadı ({degisken}): {e}")

    def sayisal_degisken_set(self, degisken_dict: Dict[str, float]) -> None:
        """
        LISP global SAYISAL (numeric) değişkenlerini AutoCAD'de ayarlar.

        katman_degisken_set() değerleri tırnak içinde (string) gönderir —
        bu, katman adları için doğrudur ama kat yüksekliği/kiriş b-h gibi
        ondalık sayı değerler için YANLIŞTIR: LISP tarafında değişken bir
        STRING'e ("3.6") atanır, sonraki aritmetik işlem
        ("bad argument type: numberp") hatası verir. Bu metod değeri
        tırnaksız gönderir, LISP'te gerçek sayı (real) olarak atanır.

        Örnek: connector.sayisal_degisken_set({"*IMP_KAT_YUKSEKLIGI*": 3.6})
        → AutoCAD'e gönderilen: (setq *IMP_KAT_YUKSEKLIGI* 3.6)
        """
        if not self.bagli:
            return

        for degisken, deger in degisken_dict.items():
            try:
                deger_f = float(deger)
                # AutoLISP'in reel sayı olarak okuması için ondalık nokta zorunlu
                lisp_expr = f'(setq {degisken} {deger_f})\n'
                self.aktif_cizim.SendCommand(lisp_expr)
                logger.debug(f"Sayısal değişken ayarlandı: {degisken} = {deger_f}")
            except Exception as e:
                logger.warning(f"Sayısal değişken ayarlanamadı ({degisken}): {e}")

    def lisp_tam_calistir(
        self,
        lsp_dosya_adi: str,
        katman_dict: Optional[Dict[str, str]] = None,
        sayisal_dict: Optional[Dict[str, float]] = None,
        bekle: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Katman/sayısal değişkenlerini set et → LISP yükle/çalıştır → sonucu oku.
        Tek adımda tüm akışı yönetir.

        Args:
            lsp_dosya_adi: .lsp dosyasının tam yolu
            katman_dict: Opsiyonel katman adı override dict'i (string değerler)
            sayisal_dict: Opsiyonel sayısal değişken override dict'i
                (örn. {"*IMP_KAT_YUKSEKLIGI*": 3.6}) — kat yüksekliği/kiriş
                b-h gibi ondalık değerler İÇİN BUNU KULLAN, katman_dict'i DEĞİL.
            bekle: LISP tamamlanması için bekleme süresi (sn)

        Returns:
            dict: LISP sonucu veya hata dict'i
        """
        if not self.bagli:
            return {"hata": "AutoCAD bağlantısı yok"}

        if katman_dict:
            self.katman_degisken_set(katman_dict)
            time.sleep(0.1)

        if sayisal_dict:
            self.sayisal_degisken_set(sayisal_dict)
            time.sleep(0.1)

        basarili = self.lisp_calistir(lsp_dosya_adi, bekle=bekle)
        if not basarili:
            return {"hata": "LISP çalıştırılamadı"}

        return self.lisp_sonuc_oku()


# ============================================================================
# TEST / DEMO FONKSIYONU
# ============================================================================

def demo_autocad_baglantisi():
    """AutoCAD bağlantısını test et ve demo çalıştır."""

    print("\n" + "="*60)
    print(" AutoCAD Canlı Bağlantı Demo")
    print("="*60 + "\n")

    try:
        # Connector oluştur
        connector = AutoCADConnector()

        # Bağlan
        connector.baglan()

        # Katman listesi
        katmanlar = connector.katman_listesi_al()
        print(f"Katmanlar ({len(katmanlar)} adet):")
        for k in katmanlar[:10]:  # İlk 10 katman
            print(f"  - {k}")
        if len(katmanlar) > 10:
            print(f"  ... ve {len(katmanlar) - 10} katman daha")

        # Blok listesi
        bloklar = connector.blok_listesi_al()
        print(f"\nBloklar ({len(bloklar)} adet):")
        for b in bloklar[:10]:
            print(f"  - {b}")
        if len(bloklar) > 10:
            print(f"  ... ve {len(bloklar) - 10} blok daha")

        # Kullanıcı seçimi
        print("\n" + "-"*40)
        objeler = connector.kullanici_secimi_al("Demo için obje seçin")

        # Sonuçları göster
        if objeler:
            print("\nSeçilen Objeler:")
            print("-"*40)
            for i, obj in enumerate(objeler, 1):
                print(f"\n{i}. {obj.entity_type}")
                print(f"   Katman: {obj.layer}")
                if obj.uzunluk > 0:
                    print(f"   Uzunluk: {obj.uzunluk:.2f}")
                if obj.alan > 0:
                    print(f"   Alan: {obj.alan:.2f}")
                if obj.blok_adi:
                    print(f"   Blok Adı: {obj.blok_adi}")
                if obj.text_icerigi:
                    print(f"   Metin: {obj.text_icerigi}")

        # Renkleri geri al
        input("\n>>> Renkleri geri almak için ENTER'a basın...")
        connector.renkleri_geri_al()

        # Bağlantıyı kes
        connector.baglantıyi_kes()

        print("\nDemo tamamlandı!")

    except ImportError as e:
        print(f"HATA: {e}")
    except ConnectionError as e:
        print(f"BAĞLANTI HATASI: {e}")
    except Exception as e:
        print(f"HATA: {e}")
        import traceback
        traceback.print_exc()
