"""
Ataşman Belgesi Motoru
======================
Şantiyede gerçekleştirilen imalatın sahada ölçülen boyutlarını kaydeden
resmi belge sistemi.

4735 sayılı Kamu İhale Sözleşmeleri Kanunu kapsamında hakediş belgelerinin
dayanağını oluşturur. Yüklenici, Kontrol Mühendisi ve İdare Amiri
tarafından imzalanır.

Yapım İşleri Genel Şartnamesi md. 33 gereği ataşman; imalat başlamadan
önce yapılan ölçüm ile imalat sonrası yapılan ölçümü belgeleyerek
miktarı kanıtlar.

Tablolar:
    atasaman_belgeler  — belge başlık bilgileri
    atasaman_kalemleri — boyutsal ölçüm kalemleri
"""

from __future__ import annotations

import csv
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

try:
    from app.utils.font_utils import get_fonts as _get_fonts
    _PDF_FONT, _PDF_FONT_BOLD = _get_fonts()
except Exception:
    _PDF_FONT, _PDF_FONT_BOLD = _PDF_FONT, _PDF_FONT_BOLD


# ──────────────────────────────────────────────────────────────────────────────
# DB YOLU TESPİTİ (database.py'den bağımsız)
# ──────────────────────────────────────────────────────────────────────────────

def _get_db_path() -> Path:
    """Veritabanı dosya yolunu döndürür. QUANTIX_DATA_DIR env var varsa oraya, yoksa data/ klasörüne."""
    quantix_data = os.environ.get("QUANTIX_DATA_DIR")
    if quantix_data:
        return Path(quantix_data) / "insaat_metraj.db"
    return Path(__file__).parent.parent.parent / "data" / "insaat_metraj.db"


# ──────────────────────────────────────────────────────────────────────────────
# SABİTLER
# ──────────────────────────────────────────────────────────────────────────────

ELEMAN_TIPLERI: List[str] = [
    "Kolon", "Kiriş", "Döşeme", "Perde", "Temel",
    "Merdiven", "Rampa", "Hatıl", "Lento", "Serbest",
]

DESTEKLENEN_BIRIMLER: List[str] = ["m³", "m²", "m", "adet"]

# SQL şema tanımları
_DDL_BELGELER = """
CREATE TABLE IF NOT EXISTS atasaman_belgeler (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    proje_id             INTEGER,
    belge_no             TEXT,
    belge_tarihi         TEXT,
    yuklenci             TEXT,
    idare                TEXT,
    kontrol_muhendisi    TEXT,
    yapim_tarihi         TEXT,
    aciklama             TEXT,
    olusturma_tarihi     TEXT DEFAULT (datetime('now'))
)
"""

_DDL_KALEMLER = """
CREATE TABLE IF NOT EXISTS atasaman_kalemleri (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    belge_id      INTEGER NOT NULL,
    eleman_tipi   TEXT,
    tanim         TEXT,
    poz_no        TEXT,
    birim         TEXT DEFAULT 'm³',
    en            REAL DEFAULT 0,
    boy           REAL DEFAULT 0,
    yukseklik     REAL DEFAULT 0,
    adet          REAL DEFAULT 1,
    brut_miktar   REAL DEFAULT 0,
    cikarilan     REAL DEFAULT 0,
    net_miktar    REAL DEFAULT 0,
    notlar        TEXT,
    foto_yolu     TEXT,
    sira          INTEGER DEFAULT 0,
    FOREIGN KEY (belge_id) REFERENCES atasaman_belgeler(id) ON DELETE CASCADE
)
"""

_DDL_FK_PRAGMA = "PRAGMA foreign_keys = ON"


# ──────────────────────────────────────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ──────────────────────────────────────────────────────────────────────────────

def _brut_miktar_hesapla(en: float, boy: float, yukseklik: float,
                          adet: float, birim: str) -> float:
    """
    Verilen boyutlardan birime göre brüt miktarı hesaplar.

    Formüller:
        m³  → en × boy × yükseklik × adet
        m²  → en × boy × adet
        m   → boy × adet
        adet→ adet (boyutlar kullanılmaz)

    Args:
        en         : Genişlik (m)
        boy        : Uzunluk (m)
        yukseklik  : Yükseklik (m)
        adet       : Adet çarpanı
        birim      : 'm³' | 'm²' | 'm' | 'adet'

    Returns:
        float: Brüt miktar (negatif olamaz)
    """
    en = max(0.0, float(en))
    boy = max(0.0, float(boy))
    yukseklik = max(0.0, float(yukseklik))
    adet = max(0.0, float(adet))

    if birim == "m³":
        sonuc = en * boy * yukseklik * adet
    elif birim == "m²":
        sonuc = en * boy * adet
    elif birim == "m":
        sonuc = boy * adet
    else:  # adet ve bilinmeyen birimler
        sonuc = adet

    return round(max(0.0, sonuc), 4)


def _net_miktar_hesapla(brut: float, cikarilan: float) -> float:
    """
    Net miktarı hesaplar. Çıkarılan brütten fazlaysa 0 döndürür.

    Args:
        brut      : Brüt miktar
        cikarilan : Düşülecek miktar (boşluklar, açıklıklar vb.)

    Returns:
        float: Net miktar (>= 0)
    """
    return round(max(0.0, float(brut) - float(cikarilan)), 4)


def _satiri_dict_cevir(cursor: sqlite3.Cursor, satir: sqlite3.Row) -> Dict[str, Any]:
    """sqlite3.Row nesnesini dict'e dönüştürür."""
    return dict(zip([col[0] for col in cursor.description], satir))


# ──────────────────────────────────────────────────────────────────────────────
# ANA MOTOR SINIFI
# ──────────────────────────────────────────────────────────────────────────────

class AtasamanEngine:
    """
    Ataşman belgesi CRUD + hesaplama + çıktı motoru.

    4735 sayılı KİK kapsamında sahada yapılan boyutsal ölçümleri
    kaydeder, brüt/net miktar hesaplar, PDF ve Excel/CSV çıktısı üretir.

    Kullanım:
        engine = AtasamanEngine()
        belge_id = engine.belge_olustur(
            proje_id=1,
            belge_no="AT-2026-001",
            belge_tarihi="2026-04-25",
            yuklenci="ABC İnşaat A.Ş.",
            idare="Ankara Büyükşehir Belediyesi",
            kontrol_muhendisi="İnş. Müh. Ahmet Yılmaz (Sicil: 12345)",
        )
        kalem_id = engine.kalem_ekle(
            belge_id=belge_id,
            eleman_tipi="Kolon",
            tanim="Zemin kat B aksı kolonları",
            poz_no="21.003",
            birim="m³",
            en=0.50, boy=0.50, yukseklik=3.20, adet=8,
        )
        engine.pdf_atasaman_belgesi_uret(belge_id, "output/AT-2026-001.pdf")
    """

    def __init__(self) -> None:
        """Veritabanı bağlantısını hazırla, tabloları oluştur."""
        self._db_path = _get_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._tabloları_olustur()
        logger.info("AtasamanEngine başlatıldı — DB: %s", self._db_path)

    # ──────────────────────────────────────────────────────────
    # BAĞLANTI YÖNETİMİ
    # ──────────────────────────────────────────────────────────

    @contextmanager
    def _baglanti(self) -> Generator[sqlite3.Connection, None, None]:
        """Thread-safe bağlantı context manager'ı."""
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute(_DDL_FK_PRAGMA)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _tabloları_olustur(self) -> None:
        """Gerekli tabloları yoksa oluşturur."""
        try:
            with self._baglanti() as conn:
                conn.execute(_DDL_BELGELER)
                conn.execute(_DDL_KALEMLER)
        except Exception as e:
            logger.error("Tablo oluşturma hatası: %s", e)
            raise

    # ──────────────────────────────────────────────────────────
    # BELGE CRUD
    # ──────────────────────────────────────────────────────────

    def belge_olustur(
        self,
        proje_id: Optional[int] = None,
        belge_no: str = "",
        belge_tarihi: str = "",
        yuklenci: str = "",
        idare: str = "",
        kontrol_muhendisi: str = "",
        yapim_tarihi: str = "",
        aciklama: str = "",
    ) -> int:
        """
        Yeni ataşman belgesi oluşturur.

        Args:
            proje_id           : Bağlı proje ID (opsiyonel)
            belge_no           : Belge numarası (örn: AT-2026-001)
            belge_tarihi       : ISO 8601 tarih (YYYY-MM-DD)
            yuklenci           : Yüklenici firma/kişi adı
            idare              : İşveren idare adı
            kontrol_muhendisi  : Adı, soyadı, sicil no
            yapim_tarihi       : İmalat tarihi/dönemi
            aciklama           : Serbest açıklama

        Returns:
            int: Yeni belgenin ID'si

        Raises:
            RuntimeError: Kayıt yapılamazsa
        """
        if not belge_tarihi:
            belge_tarihi = datetime.now().strftime("%Y-%m-%d")

        sql = """
            INSERT INTO atasaman_belgeler
                (proje_id, belge_no, belge_tarihi, yuklenci, idare,
                 kontrol_muhendisi, yapim_tarihi, aciklama)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with self._baglanti() as conn:
                cur = conn.execute(sql, (
                    proje_id, belge_no, belge_tarihi, yuklenci, idare,
                    kontrol_muhendisi, yapim_tarihi, aciklama,
                ))
                belge_id = cur.lastrowid
                logger.info("Ataşman belgesi oluşturuldu — ID: %d, No: %s", belge_id, belge_no)
                return belge_id
        except Exception as e:
            logger.error("belge_olustur hatası: %s", e)
            raise RuntimeError(f"Ataşman belgesi oluşturulamadı: {e}") from e

    def belge_guncelle(self, belge_id: int, **alanlar: Any) -> bool:
        """
        Belge başlık bilgilerini günceller.

        Args:
            belge_id : Güncellenecek belgenin ID'si
            **alanlar: Güncellenecek sütun=değer çiftleri
                       (belge_no, belge_tarihi, yuklenci, idare,
                        kontrol_muhendisi, yapim_tarihi, aciklama)

        Returns:
            bool: Güncelleme başarılıysa True
        """
        izin_verilen = {
            "proje_id", "belge_no", "belge_tarihi", "yuklenci", "idare",
            "kontrol_muhendisi", "yapim_tarihi", "aciklama",
        }
        gecerli = {k: v for k, v in alanlar.items() if k in izin_verilen}
        if not gecerli:
            logger.warning("belge_guncelle: Geçerli alan gönderilmedi.")
            return False

        set_kismi = ", ".join(f"{k} = ?" for k in gecerli)
        degerler = list(gecerli.values()) + [belge_id]
        sql = f"UPDATE atasaman_belgeler SET {set_kismi} WHERE id = ?"

        try:
            with self._baglanti() as conn:
                cur = conn.execute(sql, degerler)
                return cur.rowcount > 0
        except Exception as e:
            logger.error("belge_guncelle hatası — ID %d: %s", belge_id, e)
            return False

    def belge_sil(self, belge_id: int) -> bool:
        """
        Belgeyi ve tüm kalemlerini CASCADE ile siler.

        Args:
            belge_id : Silinecek belgenin ID'si

        Returns:
            bool: Silme başarılıysa True
        """
        sql = "DELETE FROM atasaman_belgeler WHERE id = ?"
        try:
            with self._baglanti() as conn:
                cur = conn.execute(sql, (belge_id,))
                silindi = cur.rowcount > 0
                if silindi:
                    logger.info("Ataşman belgesi silindi — ID: %d", belge_id)
                return silindi
        except Exception as e:
            logger.error("belge_sil hatası — ID %d: %s", belge_id, e)
            return False

    def tum_belgeler(self, proje_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Tüm ataşman belgelerini listeler.

        Args:
            proje_id : Filtre için proje ID (None ise tümü)

        Returns:
            List[dict]: Belge listesi (olusturma_tarihi DESC sırası)
        """
        if proje_id is not None:
            sql = """
                SELECT b.*, COUNT(k.id) AS kalem_sayisi
                FROM atasaman_belgeler b
                LEFT JOIN atasaman_kalemleri k ON k.belge_id = b.id
                WHERE b.proje_id = ?
                GROUP BY b.id
                ORDER BY b.olusturma_tarihi DESC
            """
            params: tuple = (proje_id,)
        else:
            sql = """
                SELECT b.*, COUNT(k.id) AS kalem_sayisi
                FROM atasaman_belgeler b
                LEFT JOIN atasaman_kalemleri k ON k.belge_id = b.id
                GROUP BY b.id
                ORDER BY b.olusturma_tarihi DESC
            """
            params = ()

        try:
            with self._baglanti() as conn:
                cur = conn.execute(sql, params)
                satirlar = cur.fetchall()
                return [_satiri_dict_cevir(cur, s) for s in satirlar]
        except Exception as e:
            logger.error("tum_belgeler hatası: %s", e)
            return []

    def belge_getir(self, belge_id: int) -> Optional[Dict[str, Any]]:
        """
        Belge başlık bilgilerini ve tüm kalemlerini birlikte döndürür.

        Args:
            belge_id : İstenen belge ID'si

        Returns:
            dict | None: {belge bilgileri, 'kalemler': [...]} veya None
        """
        sql_belge = "SELECT * FROM atasaman_belgeler WHERE id = ?"
        sql_kalemler = """
            SELECT * FROM atasaman_kalemleri
            WHERE belge_id = ?
            ORDER BY sira ASC, id ASC
        """
        try:
            with self._baglanti() as conn:
                cur = conn.execute(sql_belge, (belge_id,))
                satir = cur.fetchone()
                if satir is None:
                    return None
                belge = _satiri_dict_cevir(cur, satir)

                cur2 = conn.execute(sql_kalemler, (belge_id,))
                satirlar = cur2.fetchall()
                belge["kalemler"] = [_satiri_dict_cevir(cur2, s) for s in satirlar]
                return belge
        except Exception as e:
            logger.error("belge_getir hatası — ID %d: %s", belge_id, e)
            return None

    # ──────────────────────────────────────────────────────────
    # KALEM CRUD
    # ──────────────────────────────────────────────────────────

    def kalem_ekle(
        self,
        belge_id: int,
        eleman_tipi: str = "Serbest",
        tanim: str = "",
        poz_no: str = "",
        birim: str = "m³",
        en: float = 0.0,
        boy: float = 0.0,
        yukseklik: float = 0.0,
        adet: float = 1.0,
        cikarilan: float = 0.0,
        notlar: str = "",
        foto_yolu: str = "",
        sira: int = 0,
    ) -> int:
        """
        Ataşman belgesine yeni ölçüm kalemi ekler.
        Brüt ve net miktarı otomatik hesaplar.

        Args:
            belge_id    : Bağlı ataşman belgesi ID'si
            eleman_tipi : ELEMAN_TIPLERI listesinden biri
            tanim       : Kalem tanımı / yapı elemanı açıklaması
            poz_no      : CŞB poz numarası (örn: '21.003')
            birim       : 'm³' | 'm²' | 'm' | 'adet'
            en          : Genişlik (m)
            boy         : Uzunluk (m)
            yukseklik   : Yükseklik (m)
            adet        : Adet çarpanı
            cikarilan   : Düşülecek miktar (boşluklar, açıklıklar)
            notlar      : Serbest not
            foto_yolu   : Fotoğraf dosya yolu
            sira        : Sıralama değeri

        Returns:
            int: Yeni kalemin ID'si

        Raises:
            RuntimeError: Kayıt yapılamazsa
        """
        birim = birim if birim in DESTEKLENEN_BIRIMLER else "m³"
        brut = _brut_miktar_hesapla(en, boy, yukseklik, adet, birim)
        net = _net_miktar_hesapla(brut, cikarilan)

        sql = """
            INSERT INTO atasaman_kalemleri
                (belge_id, eleman_tipi, tanim, poz_no, birim,
                 en, boy, yukseklik, adet,
                 brut_miktar, cikarilan, net_miktar,
                 notlar, foto_yolu, sira)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with self._baglanti() as conn:
                cur = conn.execute(sql, (
                    belge_id, eleman_tipi, tanim, poz_no, birim,
                    en, boy, yukseklik, adet,
                    brut, cikarilan, net,
                    notlar, foto_yolu, sira,
                ))
                kalem_id = cur.lastrowid
                logger.debug(
                    "Kalem eklendi — ID: %d, Eleman: %s, Net: %.4f %s",
                    kalem_id, eleman_tipi, net, birim,
                )
                return kalem_id
        except Exception as e:
            logger.error("kalem_ekle hatası — belge_id %d: %s", belge_id, e)
            raise RuntimeError(f"Kalem eklenemedi: {e}") from e

    def kalem_guncelle(self, kalem_id: int, **alanlar: Any) -> bool:
        """
        Kalem günceller; brüt ve net miktarı yeniden hesaplar.

        Boyutsal alanlar (en, boy, yukseklik, adet, cikarilan) veya
        birim değişirse hesaplar güncellenir.

        Args:
            kalem_id : Güncellenecek kalemin ID'si
            **alanlar: Güncellenecek sütun=değer çiftleri

        Returns:
            bool: Güncelleme başarılıysa True
        """
        izin_verilen = {
            "eleman_tipi", "tanim", "poz_no", "birim",
            "en", "boy", "yukseklik", "adet", "cikarilan",
            "notlar", "foto_yolu", "sira",
        }
        gecerli = {k: v for k, v in alanlar.items() if k in izin_verilen}
        if not gecerli:
            logger.warning("kalem_guncelle: Geçerli alan gönderilmedi.")
            return False

        # Mevcut kalem verisini çek — eksik boyutları tamamlamak için
        mevcut = self._kalem_getir(kalem_id)
        if mevcut is None:
            logger.warning("kalem_guncelle: Kalem bulunamadı — ID %d", kalem_id)
            return False

        # Güncel değerleri mevcut ile birleştir
        birlesik = {**mevcut, **gecerli}
        birim = birlesik.get("birim", "m³")
        if birim not in DESTEKLENEN_BIRIMLER:
            birim = "m³"

        brut = _brut_miktar_hesapla(
            birlesik.get("en", 0.0),
            birlesik.get("boy", 0.0),
            birlesik.get("yukseklik", 0.0),
            birlesik.get("adet", 1.0),
            birim,
        )
        net = _net_miktar_hesapla(brut, birlesik.get("cikarilan", 0.0))

        gecerli["brut_miktar"] = brut
        gecerli["net_miktar"] = net
        gecerli["birim"] = birim

        set_kismi = ", ".join(f"{k} = ?" for k in gecerli)
        degerler = list(gecerli.values()) + [kalem_id]
        sql = f"UPDATE atasaman_kalemleri SET {set_kismi} WHERE id = ?"

        try:
            with self._baglanti() as conn:
                cur = conn.execute(sql, degerler)
                return cur.rowcount > 0
        except Exception as e:
            logger.error("kalem_guncelle hatası — ID %d: %s", kalem_id, e)
            return False

    def kalem_sil(self, kalem_id: int) -> bool:
        """
        Tekil ataşman kalemini siler.

        Args:
            kalem_id : Silinecek kalemin ID'si

        Returns:
            bool: Silme başarılıysa True
        """
        sql = "DELETE FROM atasaman_kalemleri WHERE id = ?"
        try:
            with self._baglanti() as conn:
                cur = conn.execute(sql, (kalem_id,))
                return cur.rowcount > 0
        except Exception as e:
            logger.error("kalem_sil hatası — ID %d: %s", kalem_id, e)
            return False

    def foto_ekle(self, kalem_id: int, foto_yolu: str) -> bool:
        """
        Kaleme fotoğraf yolu kaydeder.

        Args:
            kalem_id  : Kalemin ID'si
            foto_yolu : Fotoğraf dosyası tam yolu

        Returns:
            bool: Kayıt başarılıysa True
        """
        sql = "UPDATE atasaman_kalemleri SET foto_yolu = ? WHERE id = ?"
        try:
            with self._baglanti() as conn:
                cur = conn.execute(sql, (foto_yolu, kalem_id))
                return cur.rowcount > 0
        except Exception as e:
            logger.error("foto_ekle hatası — kalem_id %d: %s", kalem_id, e)
            return False

    # ──────────────────────────────────────────────────────────
    # HESAPLAMA
    # ──────────────────────────────────────────────────────────

    def toplam_hesapla(self, belge_id: int) -> Dict[str, Any]:
        """
        Belgedeki tüm kalemlerin birim bazında net miktar toplamlarını hesaplar.

        Args:
            belge_id : Ataşman belgesi ID'si

        Returns:
            dict: {
                'm³': float,
                'm²': float,
                'm' : float,
                'adet': float,
                'kalem_sayisi': int,
                'brut_toplam': float,  # tüm birimler brüt toplamı (bilgi amaçlı)
                'net_toplam': float,   # tüm birimler net toplamı (bilgi amaçlı)
            }
        """
        sql = """
            SELECT birim, SUM(net_miktar) AS net_toplam,
                   SUM(brut_miktar) AS brut_toplam,
                   COUNT(*) AS adet
            FROM atasaman_kalemleri
            WHERE belge_id = ?
            GROUP BY birim
        """
        sql_toplam = """
            SELECT COUNT(*) AS toplam_kalem,
                   SUM(brut_miktar) AS brut_genel,
                   SUM(net_miktar) AS net_genel
            FROM atasaman_kalemleri
            WHERE belge_id = ?
        """
        sonuc: Dict[str, Any] = {
            "m³": 0.0, "m²": 0.0, "m": 0.0, "adet": 0.0,
            "kalem_sayisi": 0, "brut_toplam": 0.0, "net_toplam": 0.0,
        }
        try:
            with self._baglanti() as conn:
                cur = conn.execute(sql, (belge_id,))
                for satir in cur.fetchall():
                    birim = satir[0] or "m³"
                    if birim in sonuc:
                        sonuc[birim] = round(float(satir[1] or 0), 4)

                cur2 = conn.execute(sql_toplam, (belge_id,))
                row2 = cur2.fetchone()
                if row2:
                    sonuc["kalem_sayisi"] = int(row2[0] or 0)
                    sonuc["brut_toplam"] = round(float(row2[1] or 0), 4)
                    sonuc["net_toplam"] = round(float(row2[2] or 0), 4)
        except Exception as e:
            logger.error("toplam_hesapla hatası — belge_id %d: %s", belge_id, e)
        return sonuc

    # ──────────────────────────────────────────────────────────
    # PDF ÇIKTI
    # ──────────────────────────────────────────────────────────

    def pdf_atasaman_belgesi_uret(self, belge_id: int, dosya_yolu: str) -> bool:
        """
        Ataşman belgesi PDF çıktısı üretir (reportlab A4 dikey).

        PDF İçeriği:
            - Başlık: "ATAŞMAN BELGESİ"
            - Alt başlık: "Yapım İşleri Genel Şartnamesi Kapsamında Saha Ölçüm Tutanağı"
            - Belge bilgileri (2 kolon: idare/yüklenici/proje — belge no/tarih/kontrol müh.)
            - Ölçüm tablosu (12 sütun, alternatif satır rengi)
            - Birim bazında TOPLAM satırı
            - İmza bölümü (3 kolon: Yüklenici / Kontrol Mühendisi / İdare Amiri)
            - Yasal not

        Args:
            belge_id  : Ataşman belgesi ID'si
            dosya_yolu: PDF çıktı dosyası tam yolu

        Returns:
            bool: Üretim başarılıysa True, reportlab yoksa False
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                Paragraph, Spacer, Table, TableStyle, SimpleDocTemplate,
            )
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError:
            logger.error("pdf_atasaman_belgesi_uret: reportlab kurulu değil — pip install reportlab")
            return False

        belge = self.belge_getir(belge_id)
        if belge is None:
            logger.error("pdf_atasaman_belgesi_uret: Belge bulunamadı — ID %d", belge_id)
            return False

        kalemler = belge.get("kalemler", [])
        toplamlar = self.toplam_hesapla(belge_id)

        try:
            Path(dosya_yolu).parent.mkdir(parents=True, exist_ok=True)

            doc = SimpleDocTemplate(
                dosya_yolu,
                pagesize=A4,
                topMargin=1.5 * cm,
                bottomMargin=2.0 * cm,
                leftMargin=1.8 * cm,
                rightMargin=1.8 * cm,
            )

            styles = getSampleStyleSheet()
            stil_baslik = ParagraphStyle(
                "AtasamanBaslik",
                parent=styles["Heading1"],
                fontSize=16,
                fontName=_PDF_FONT_BOLD,
                alignment=1,  # orta
                spaceAfter=4,
            )
            stil_alt_baslik = ParagraphStyle(
                "AtasamanAltBaslik",
                parent=styles["Normal"],
                fontSize=9,
                fontName=_PDF_FONT,
                alignment=1,
                spaceAfter=12,
                textColor=colors.HexColor("#555555"),
            )
            stil_bilgi = ParagraphStyle(
                "BilgiNormal",
                parent=styles["Normal"],
                fontSize=9,
                fontName=_PDF_FONT,
                spaceAfter=3,
            )
            stil_bilgi_kalin = ParagraphStyle(
                "BilgiKalin",
                parent=styles["Normal"],
                fontSize=9,
                fontName=_PDF_FONT_BOLD,
                spaceAfter=2,
            )
            stil_not = ParagraphStyle(
                "AtasamanNot",
                parent=styles["Normal"],
                fontSize=7.5,
                fontName=_PDF_FONT,
                textColor=colors.HexColor("#444444"),
                alignment=1,
                spaceBefore=6,
            )

            elemanlar = []

            # ── BAŞLIK ─────────────────────────────────────────────────
            elemanlar.append(Paragraph("ATAŞMAN BELGESİ", stil_baslik))
            elemanlar.append(Paragraph(
                "Yapım İşleri Genel Şartnamesi Kapsamında Saha Ölçüm Tutanağı",
                stil_alt_baslik,
            ))

            # ── BİLGİ SATIRI (2 KOLON) ─────────────────────────────────
            sol_bilgi = [
                [Paragraph("<b>Proje Adı / Konusu:</b>", stil_bilgi_kalin),
                 Paragraph(belge.get("aciklama", "—") or "—", stil_bilgi)],
                [Paragraph("<b>İdare:</b>", stil_bilgi_kalin),
                 Paragraph(belge.get("idare", "—") or "—", stil_bilgi)],
                [Paragraph("<b>Yüklenici:</b>", stil_bilgi_kalin),
                 Paragraph(belge.get("yuklenci", "—") or "—", stil_bilgi)],
                [Paragraph("<b>Yapım Tarihi/Dönemi:</b>", stil_bilgi_kalin),
                 Paragraph(belge.get("yapim_tarihi", "—") or "—", stil_bilgi)],
            ]
            sag_bilgi = [
                [Paragraph("<b>Belge No:</b>", stil_bilgi_kalin),
                 Paragraph(belge.get("belge_no", "—") or "—", stil_bilgi)],
                [Paragraph("<b>Belge Tarihi:</b>", stil_bilgi_kalin),
                 Paragraph(belge.get("belge_tarihi", "—") or "—", stil_bilgi)],
                [Paragraph("<b>Kontrol Mühendisi:</b>", stil_bilgi_kalin),
                 Paragraph(belge.get("kontrol_muhendisi", "—") or "—", stil_bilgi)],
                [Paragraph("<b>Oluşturma Tarihi:</b>", stil_bilgi_kalin),
                 Paragraph(belge.get("olusturma_tarihi", "—") or "—", stil_bilgi)],
            ]

            sol_tablo = Table(sol_bilgi, colWidths=[4.2 * cm, 7.3 * cm])
            sol_tablo.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), _PDF_FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            sag_tablo = Table(sag_bilgi, colWidths=[4.2 * cm, 7.3 * cm])
            sag_tablo.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), _PDF_FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))

            bilgi_tablosu = Table(
                [[sol_tablo, sag_tablo]],
                colWidths=[11.5 * cm, 11.5 * cm],
            )
            bilgi_tablosu.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
                ("LINEAFTER", (0, 0), (0, -1), 0.5, colors.HexColor("#999999")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))
            elemanlar.append(bilgi_tablosu)
            elemanlar.append(Spacer(1, 0.4 * cm))

            # ── ÖLÇÜM TABLOSU BAŞLIĞI ──────────────────────────────────
            tablo_basliklari = [
                "Sıra", "Eleman Tipi", "Tanım", "Poz No",
                "Birim", "En (m)", "Boy (m)", "Yük. (m)",
                "Adet", "Brüt Mik.", "Çıkarılan", "Net Miktar",
            ]
            tablo_verisi = [tablo_basliklari]

            # Kalem satırları
            for idx, kalem in enumerate(kalemler, start=1):
                satir = [
                    str(idx),
                    kalem.get("eleman_tipi", "") or "",
                    kalem.get("tanim", "") or "",
                    kalem.get("poz_no", "") or "",
                    kalem.get("birim", "m³") or "m³",
                    f"{kalem.get('en', 0):.3f}",
                    f"{kalem.get('boy', 0):.3f}",
                    f"{kalem.get('yukseklik', 0):.3f}",
                    f"{kalem.get('adet', 1):.2f}",
                    f"{kalem.get('brut_miktar', 0):.4f}",
                    f"{kalem.get('cikarilan', 0):.4f}",
                    f"{kalem.get('net_miktar', 0):.4f}",
                ]
                tablo_verisi.append(satir)

            # Toplam satırları — birim bazında
            for birim_kodu in DESTEKLENEN_BIRIMLER:
                toplam_deger = toplamlar.get(birim_kodu, 0.0)
                if toplam_deger > 0:
                    toplam_satiri = [
                        "", "", "", "",
                        birim_kodu,
                        "", "", "", "",
                        "", "",
                        f"{toplam_deger:.4f}",
                    ]
                    toplam_satiri[1] = f"TOPLAM ({birim_kodu})"
                    tablo_verisi.append(toplam_satiri)

            # Sütun genişlikleri (A4 sayfa içi toplam ~23 cm)
            col_widths = [
                1.0 * cm,   # Sıra
                2.5 * cm,   # Eleman Tipi
                4.5 * cm,   # Tanım
                1.8 * cm,   # Poz No
                1.2 * cm,   # Birim
                1.5 * cm,   # En
                1.5 * cm,   # Boy
                1.5 * cm,   # Yük
                1.2 * cm,   # Adet
                2.0 * cm,   # Brüt
                2.0 * cm,   # Çıkarılan
                2.3 * cm,   # Net
            ]

            tablo = Table(tablo_verisi, colWidths=col_widths, repeatRows=1)

            tablo_stili = TableStyle([
                # Başlık satırı
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), _PDF_FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, 0), 7.5),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                # Veri satırları
                ("FONTNAME", (0, 1), (-1, -1), _PDF_FONT),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 1), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
                # Sayısal sütunlar sağa hizalı (En'dan itibaren)
                ("ALIGN", (5, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 1), (4, -1), "LEFT"),
                # İzgara
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#aaaaaa")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#2c3e50")),
            ])

            # Alternatif satır rengi
            for i in range(1, len(tablo_verisi)):
                satir = tablo_verisi[i]
                # Toplam satırları farklı renklendir
                if satir[1] and str(satir[1]).startswith("TOPLAM"):
                    tablo_stili.add("BACKGROUND", (0, i), (-1, i),
                                    colors.HexColor("#d4e8d4"))
                    tablo_stili.add("FONTNAME", (0, i), (-1, i), _PDF_FONT_BOLD)
                    tablo_stili.add("FONTSIZE", (0, i), (-1, i), 7.5)
                elif i % 2 == 0:
                    tablo_stili.add("BACKGROUND", (0, i), (-1, i),
                                    colors.HexColor("#f5f5f5"))
                else:
                    tablo_stili.add("BACKGROUND", (0, i), (-1, i), colors.white)

            tablo.setStyle(tablo_stili)
            elemanlar.append(tablo)
            elemanlar.append(Spacer(1, 0.5 * cm))

            # ── İMZA BÖLÜMİ (3 KOLON) ─────────────────────────────────
            imza_stil = ParagraphStyle(
                "ImzaStil",
                parent=styles["Normal"],
                fontSize=8,
                fontName=_PDF_FONT,
                alignment=1,
                spaceAfter=2,
            )
            imza_kalin = ParagraphStyle(
                "ImzaKalin",
                parent=styles["Normal"],
                fontSize=8.5,
                fontName=_PDF_FONT_BOLD,
                alignment=1,
                spaceAfter=2,
            )

            bos_satir = Paragraph("", imza_stil)
            cizgi_satiri = Paragraph("_" * 32, imza_stil)

            yuklenci_blok = [
                Paragraph("<b>YÜKLENİCİ VEKİLİ</b>", imza_kalin),
                Spacer(1, 0.2 * cm),
                Paragraph(belge.get("yuklenci", "") or "", imza_stil),
                Spacer(1, 1.0 * cm),
                cizgi_satiri,
                Paragraph("İmza / Kaşe", imza_stil),
            ]
            kontrol_blok = [
                Paragraph("<b>KONTROL MÜHENDİSİ</b>", imza_kalin),
                Spacer(1, 0.2 * cm),
                Paragraph(belge.get("kontrol_muhendisi", "") or "", imza_stil),
                Spacer(1, 1.0 * cm),
                cizgi_satiri,
                Paragraph("İmza", imza_stil),
            ]
            idare_blok = [
                Paragraph("<b>İDARE AMİRİ</b>", imza_kalin),
                Spacer(1, 0.2 * cm),
                Paragraph(belge.get("idare", "") or "", imza_stil),
                Spacer(1, 1.0 * cm),
                cizgi_satiri,
                Paragraph("İmza", imza_stil),
            ]

            imza_tablosu = Table(
                [[yuklenci_blok, kontrol_blok, idare_blok]],
                colWidths=[7.5 * cm, 7.5 * cm, 7.5 * cm],
            )
            imza_tablosu.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#888888")),
                ("LINEAFTER", (0, 0), (1, -1), 0.5, colors.HexColor("#888888")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))
            elemanlar.append(imza_tablosu)

            # ── YASAL NOT ──────────────────────────────────────────────
            elemanlar.append(Spacer(1, 0.3 * cm))
            elemanlar.append(Paragraph(
                "Bu belge 4735 sayılı KİK kapsamında düzenlenmiştir. "
                "Ölçüler saha şartlarında kontrol mühendisi nezaretinde alınmıştır.",
                stil_not,
            ))

            doc.build(elemanlar)
            logger.info("Ataşman PDF üretildi — %s", dosya_yolu)
            return True

        except Exception as e:
            logger.error("pdf_atasaman_belgesi_uret hatası: %s", e)
            return False

    # ──────────────────────────────────────────────────────────
    # EXCEL / CSV ÇIKTI
    # ──────────────────────────────────────────────────────────

    def excel_disari_aktar(self, belge_id: int, dosya_yolu: str) -> bool:
        """
        Ataşman belgesini Excel (openpyxl) veya CSV (openpyxl yoksa) olarak dışa aktarır.

        Başlık satırı:
            Sıra | Eleman Tipi | Tanım | Poz No | Birim |
            En | Boy | Yükseklik | Adet | Brüt Miktar | Çıkarılan | Net Miktar | Notlar

        Args:
            belge_id  : Ataşman belgesi ID'si
            dosya_yolu: Çıktı dosya yolu (.xlsx veya .csv)

        Returns:
            bool: Aktarım başarılıysa True
        """
        belge = self.belge_getir(belge_id)
        if belge is None:
            logger.error("excel_disari_aktar: Belge bulunamadı — ID %d", belge_id)
            return False

        kalemler = belge.get("kalemler", [])
        basliklar = [
            "Sıra", "Eleman Tipi", "Tanım", "Poz No", "Birim",
            "En (m)", "Boy (m)", "Yükseklik (m)", "Adet",
            "Brüt Miktar", "Çıkarılan", "Net Miktar", "Notlar",
        ]

        satirlar = []
        for idx, kalem in enumerate(kalemler, start=1):
            satirlar.append([
                idx,
                kalem.get("eleman_tipi", "") or "",
                kalem.get("tanim", "") or "",
                kalem.get("poz_no", "") or "",
                kalem.get("birim", "m³") or "m³",
                kalem.get("en", 0.0),
                kalem.get("boy", 0.0),
                kalem.get("yukseklik", 0.0),
                kalem.get("adet", 1.0),
                kalem.get("brut_miktar", 0.0),
                kalem.get("cikarilan", 0.0),
                kalem.get("net_miktar", 0.0),
                kalem.get("notlar", "") or "",
            ])

        # Toplam satırları ekle
        toplamlar = self.toplam_hesapla(belge_id)
        for birim_kodu in DESTEKLENEN_BIRIMLER:
            val = toplamlar.get(birim_kodu, 0.0)
            if val > 0:
                satirlar.append([
                    "", f"TOPLAM ({birim_kodu})", "", "", birim_kodu,
                    "", "", "", "", "", "", val, "",
                ])

        # openpyxl ile Excel çıktısı
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            Path(dosya_yolu).parent.mkdir(parents=True, exist_ok=True)
            if not dosya_yolu.endswith(".xlsx"):
                dosya_yolu = dosya_yolu.rsplit(".", 1)[0] + ".xlsx"

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Ataşman Belgesi"

            # Belge bilgileri (üst kısım)
            ws.merge_cells("A1:M1")
            ws["A1"] = "ATAŞMAN BELGESİ"
            ws["A1"].font = Font(bold=True, size=14)
            ws["A1"].alignment = Alignment(horizontal="center")

            bilgi_satirlari = [
                ("Belge No:", belge.get("belge_no", ""), "Belge Tarihi:", belge.get("belge_tarihi", "")),
                ("Yüklenici:", belge.get("yuklenci", ""), "İdare:", belge.get("idare", "")),
                ("Kontrol Müh.:", belge.get("kontrol_muhendisi", ""), "Yapım Tarihi:", belge.get("yapim_tarihi", "")),
            ]
            for r_idx, (l1, v1, l2, v2) in enumerate(bilgi_satirlari, start=2):
                ws.cell(row=r_idx, column=1, value=l1).font = Font(bold=True)
                ws.cell(row=r_idx, column=2, value=v1)
                ws.cell(row=r_idx, column=8, value=l2).font = Font(bold=True)
                ws.cell(row=r_idx, column=9, value=v2)

            # Boş satır
            baslik_satir = 6

            # Başlık satırı
            for col_idx, baslik in enumerate(basliklar, start=1):
                cell = ws.cell(row=baslik_satir, column=col_idx, value=baslik)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="2C3E50")
                cell.alignment = Alignment(horizontal="center", vertical="center")

            # İnce kenar
            ince = Side(style="thin", color="AAAAAA")
            kalin = Side(style="medium", color="2C3E50")

            # Veri satırları
            for satir_idx, satir in enumerate(satirlar, start=baslik_satir + 1):
                for col_idx, deger in enumerate(satir, start=1):
                    cell = ws.cell(row=satir_idx, column=col_idx, value=deger)
                    cell.border = Border(
                        left=ince, right=ince, top=ince, bottom=ince,
                    )
                    # Sayısal sütunlar sağa hizalı
                    if col_idx >= 6:
                        cell.alignment = Alignment(horizontal="right")
                    # Alternatif satır
                    if isinstance(satir[0], int):  # normal kalem
                        if satir_idx % 2 == 0:
                            cell.fill = PatternFill("solid", fgColor="F5F5F5")
                    else:  # toplam satırı
                        cell.fill = PatternFill("solid", fgColor="D4E8D4")
                        cell.font = Font(bold=True)

            # Sütun genişlikleri (yaklaşık)
            ws.column_dimensions["A"].width = 6
            ws.column_dimensions["B"].width = 16
            ws.column_dimensions["C"].width = 30
            ws.column_dimensions["D"].width = 10
            ws.column_dimensions["E"].width = 8
            for col_harf in ["F", "G", "H", "I", "J", "K", "L"]:
                ws.column_dimensions[col_harf].width = 12
            ws.column_dimensions["M"].width = 25

            wb.save(dosya_yolu)
            logger.info("Ataşman Excel aktarıldı — %s", dosya_yolu)
            return True

        except ImportError:
            logger.warning("openpyxl bulunamadı — CSV formatında aktarılıyor")
            return self._csv_disari_aktar(belge_id, dosya_yolu, basliklar, satirlar)
        except Exception as e:
            logger.error("excel_disari_aktar hatası: %s", e)
            return False

    # ──────────────────────────────────────────────────────────
    # ÖZEL (İÇ KULLANIM) METODLAR
    # ──────────────────────────────────────────────────────────

    def _kalem_getir(self, kalem_id: int) -> Optional[Dict[str, Any]]:
        """Tek bir kalem satırını dict olarak döndürür."""
        sql = "SELECT * FROM atasaman_kalemleri WHERE id = ?"
        try:
            with self._baglanti() as conn:
                cur = conn.execute(sql, (kalem_id,))
                satir = cur.fetchone()
                if satir is None:
                    return None
                return _satiri_dict_cevir(cur, satir)
        except Exception as e:
            logger.error("_kalem_getir hatası — ID %d: %s", kalem_id, e)
            return None

    def _csv_disari_aktar(
        self,
        belge_id: int,
        dosya_yolu: str,
        basliklar: List[str],
        satirlar: List[List[Any]],
    ) -> bool:
        """openpyxl yoksa CSV fallback. utf-8-sig kodlaması ile kaydeder."""
        try:
            if not dosya_yolu.endswith(".csv"):
                dosya_yolu = dosya_yolu.rsplit(".", 1)[0] + ".csv"
            Path(dosya_yolu).parent.mkdir(parents=True, exist_ok=True)
            with open(dosya_yolu, "w", newline="", encoding="utf-8-sig") as f:
                yazar = csv.writer(f)
                yazar.writerow(basliklar)
                for satir in satirlar:
                    yazar.writerow(satir)
            logger.info("Ataşman CSV aktarıldı — %s", dosya_yolu)
            return True
        except Exception as e:
            logger.error("_csv_disari_aktar hatası: %s", e)
            return False
