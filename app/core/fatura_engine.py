"""
Fatura ve Tahsilat Takibi — Engine
====================================
Serbest Piyasa / Özel Müşteri Fatura Yönetimi

KDV : %20 (2023 sonrası)
Vade: Kullanıcı tanımlı (varsayılan 30 gün)

Neyi çözüyoruz?
Müteahhidin özel müşterisine kestiği faturaların,
ödeme takviminin ve bakiye takibinin eksiksiz
yönetimini sağlıyoruz. Vadesi geçmiş alacaklar
otomatik tespit edilir.

Nasıl test ederiz?
engine = FaturaEngine(db)
fatura_id = engine.fatura_olustur(bilgi)
engine.odeme_kaydet(fatura_id, OdemeKaydi(tutar=Decimal("5000")))
bakiye = engine.bakiye_sorgula(fatura_id)
assert bakiye.kalan > 0
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import Optional
import sqlite3
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

KDV_ORANI = Decimal("0.20")
VADE_SURESI = 30 # gün

FATURA_DURUMLARI = ["Bekliyor", "Kısmen Ödendi", "Tamamlandı", "Gecikti", "İptal"]

ODEME_YONTEMLERI = [
"Nakit",
"Banka Havalesi / EFT",
"Çek",
"Kredi Kartı",
"Diğer",
]

FATURA_TURLERI = [
"Hakediş Faturası",
"Avans Faturası",
"Kesin Hesap Faturası",
"Malzeme Faturası",
"Hizmet Faturası",
]


# ---------------------------------------------------------------------------
# Veri sınıfları
# ---------------------------------------------------------------------------

@dataclass
class OdemeKaydi:
    """Tek bir ödeme satırı."""
    tarih: date = field(default_factory=date.today)
    tutar: Decimal = Decimal("0")
    yontem: str = "Banka Havalesi / EFT"
    aciklama: str = ""
    id: Optional[int] = None


@dataclass
class FaturaBilgisi:
    """Fatura oluşturmak için gereken bilgiler."""
    musteri_adi: str = ""
    musteri_tel: str = ""
    proje_adi: str = ""
    fatura_turu: str = "Hakediş Faturası"
    fatura_no: str = ""
    fatura_tarihi: Optional[date] = None
    vade_tarihi: Optional[date] = None

    # Tutar
    kdv_haric_tutar: Decimal = Decimal("0")
    kdv_tutari: Decimal = Decimal("0")
    genel_toplam: Decimal = Decimal("0")

    aciklama: str = ""
    notlar: str = ""


@dataclass
class FaturaBakiye:
    """Fatura ödeme durumu özeti."""
    fatura_id: int
    fatura_no: str
    musteri_adi: str
    genel_toplam: Decimal
    odenen_toplam: Decimal
    kalan: Decimal
    durum: str
    vade_tarihi: Optional[date]
    vadesi_gecti_mi: bool
    gecikme_gun: int


@dataclass
class TahsilatOzet:
    """Genel tahsilat durumu."""
    toplam_alacak: Decimal = Decimal("0")
    tahsil_edilen: Decimal = Decimal("0")
    bekleyen: Decimal = Decimal("0")
    vadesi_gecmis: Decimal = Decimal("0")
    fatura_sayisi: int = 0
    acik_fatura_sayisi: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class FaturaEngine:
    """
    SQLite tabanlı fatura ve tahsilat yönetim motoru.
    Tablo yoksa otomatik oluşturur.
    """

    CREATE_FATURALAR = """
    CREATE TABLE IF NOT EXISTS faturalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    musteri_adi TEXT NOT NULL,
    musteri_tel TEXT DEFAULT '',
    proje_adi TEXT DEFAULT '',
    fatura_turu TEXT DEFAULT 'Hakediş Faturası',
    fatura_no TEXT UNIQUE NOT NULL,
    fatura_tarihi TEXT NOT NULL,
    vade_tarihi TEXT,
    kdv_haric_tutar REAL DEFAULT 0,
    kdv_tutari REAL DEFAULT 0,
    genel_toplam REAL DEFAULT 0,
    odenen_toplam REAL DEFAULT 0,
    durum TEXT DEFAULT 'Bekliyor',
    aciklama TEXT DEFAULT '',
    notlar TEXT DEFAULT '',
    olusturma_tarihi TEXT DEFAULT (date('now'))
    )
    """

    CREATE_ODEMELER = """
    CREATE TABLE IF NOT EXISTS fatura_odemeler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fatura_id INTEGER NOT NULL REFERENCES faturalar(id),
    tarih TEXT NOT NULL,
    tutar REAL NOT NULL,
    yontem TEXT DEFAULT 'Banka Havalesi / EFT',
    aciklama TEXT DEFAULT '',
    kayit_tarihi TEXT DEFAULT (date('now'))
    )
    """

    def __init__(self, db=None):
        self.db = db
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

        def _get_conn(self) -> sqlite3.Connection:
            """Veritabanı bağlantısını döndür."""
            if self.db and hasattr(self.db, "conn"):
                return self.db.conn
                if self._conn is None:
                    import os
                    db_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "data", "insaat_metraj.db"
                    )
                    self._conn = sqlite3.connect(db_path, check_same_thread=False)
                    self._conn.row_factory = sqlite3.Row
                    return self._conn

                    def _init_db(self):
                        """Tabloları oluştur (yoksa)."""
                        try:
                            conn = self._get_conn()
                            conn.execute(self.CREATE_FATURALAR)
                            conn.execute(self.CREATE_ODEMELER)
                            conn.commit()
                        except Exception as e:
                            logger.error(f"Fatura tablo init hatası: {e}")

                            def _round2(self, v: Decimal) -> Decimal:
                                return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                                # ------------------------------------------------------------------
                                # Tutar hesaplama
                                # ------------------------------------------------------------------

                                def kdv_hesapla(self, kdv_haric: Decimal) -> tuple[Decimal, Decimal]:
                                    """KDV tutarı ve genel toplam döndür."""
                                    kdv = self._round2(kdv_haric * KDV_ORANI)
                                    toplam = self._round2(kdv_haric + kdv)
                                    return kdv, toplam

                                    def fatura_no_uret(self, yil: int, sira: int) -> str:
                                        """FTR-2026-0001 formatında fatura numarası."""
                                        return f"FTR-{yil}-{sira:04d}"

                                        def vade_tarihi_hesapla(self, fatura_tarihi: date, gun: int = VADE_SURESI) -> date:
                                            return fatura_tarihi + timedelta(days=gun)

                                            # ------------------------------------------------------------------
                                            # CRUD işlemleri
                                            # ------------------------------------------------------------------

                                            def fatura_olustur(self, bilgi: FaturaBilgisi) -> int:
                                                """Yeni fatura kaydet, ID döndür."""
                                                try:
                                                    conn = self._get_conn()
                                                    cur = conn.execute(
                                                    """INSERT INTO faturalar
                                                    (musteri_adi, musteri_tel, proje_adi, fatura_turu,
                                                    fatura_no, fatura_tarihi, vade_tarihi,
                                                    kdv_haric_tutar, kdv_tutari, genel_toplam,
                                                    aciklama, notlar)
                                                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                                                    (bilgi.musteri_adi, bilgi.musteri_tel, bilgi.proje_adi,
                                                    bilgi.fatura_turu, bilgi.fatura_no,
                                                    str(bilgi.fatura_tarihi),
                                                    str(bilgi.vade_tarihi) if bilgi.vade_tarihi else None,
                                                    float(bilgi.kdv_haric_tutar), float(bilgi.kdv_tutari),
                                                    float(bilgi.genel_toplam), bilgi.aciklama, bilgi.notlar)
                                                    )
                                                    conn.commit()
                                                    return cur.lastrowid
                                                except Exception as e:
                                                    logger.error(f"Fatura oluşturma hatası: {e}")
                                                    raise

                                                    def odeme_kaydet(self, fatura_id: int, odeme: OdemeKaydi) -> None:
                                                        """Faturaya ödeme ekle ve durumu güncelle."""
                                                        try:
                                                            conn = self._get_conn()
                                                            conn.execute(
                                                            """INSERT INTO fatura_odemeler
                                                            (fatura_id, tarih, tutar, yontem, aciklama)
                                                            VALUES (?,?,?,?,?)""",
                                                            (fatura_id, str(odeme.tarih), float(odeme.tutar),
                                                            odeme.yontem, odeme.aciklama)
                                                            )
                                                            # Ödeneni güncelle
                                                            conn.execute(
                                                            """UPDATE faturalar
                                                            SET odenen_toplam = (
                                                            SELECT COALESCE(SUM(tutar), 0) FROM fatura_odemeler
                                                            WHERE fatura_id = ?
                                                            )
                                                            WHERE id = ?""",
                                                            (fatura_id, fatura_id)
                                                            )
                                                            # Durum güncelle
                                                            self._durum_guncelle(conn, fatura_id)
                                                            conn.commit()
                                                        except Exception as e:
                                                            logger.error(f"Ödeme kaydetme hatası: {e}")
                                                            raise

                                                            def fatura_iptal(self, fatura_id: int) -> None:
                                                                conn = self._get_conn()
                                                                conn.execute("UPDATE faturalar SET durum='İptal' WHERE id=?", (fatura_id,))
                                                                conn.commit()

                                                                def _durum_guncelle(self, conn: sqlite3.Connection, fatura_id: int) -> None:
                                                                    row = conn.execute(
                                                                    "SELECT genel_toplam, odenen_toplam, vade_tarihi FROM faturalar WHERE id=?",
                                                                    (fatura_id,)
                                                                    ).fetchone()
                                                                    if not row:
                                                                        return

                                                                        toplam = Decimal(str(row["genel_toplam"]))
                                                                        odenen = Decimal(str(row["odened_toplam"] if "odened_toplam" in row.keys()
                                                                        else row[1]))

                                                                        # Row index erişimi
                                                                        try:
                                                                            odened = Decimal(str(row["odenen_toplam"]))
                                                                        except Exception:
                                                                            odened = Decimal("0")

                                                                            if odened >= toplam:
                                                                                durum = "Tamamlandı"
                                                                            elif odened > 0:
                                                                                durum = "Kısmen Ödendi"
                                                                            else:
                                                                                vade = row["vade_tarihi"]
                                                                                if vade and date.today() > date.fromisoformat(str(vade)):
                                                                                    durum = "Gecikti"
                                                                                else:
                                                                                    durum = "Bekliyor"

                                                                                    conn.execute("UPDATE faturalar SET durum=? WHERE id=?", (durum, fatura_id))

                                                                                    # ------------------------------------------------------------------
                                                                                    # Sorgular
                                                                                    # ------------------------------------------------------------------

                                                                                    def bakiye_sorgula(self, fatura_id: int) -> FaturaBakiye:
                                                                                        conn = self._get_conn()
                                                                                        row = conn.execute(
                                                                                        "SELECT * FROM faturalar WHERE id=?", (fatura_id,)
                                                                                        ).fetchone()
                                                                                        if not row:
                                                                                            raise ValueError(f"Fatura bulunamadı: {fatura_id}")

                                                                                            toplam = Decimal(str(row["genel_toplam"]))
                                                                                            odenen = Decimal(str(row["odenen_toplam"] or 0))
                                                                                            kalan = self._round2(toplam - odened)

                                                                                            vade = None
                                                                                            gecikme_gun = 0
                                                                                            vadesi_gecti = False
                                                                                            if row["vade_tarihi"]:
                                                                                                vade = date.fromisoformat(row["vade_tarihi"])
                                                                                                if date.today() > vade and kalan > 0:
                                                                                                    vadesi_gecti = True
                                                                                                    gecikme_gun = (date.today() - vade).days

                                                                                                    return FaturaBakiye(
                                                                                                    fatura_id = fatura_id,
                                                                                                    fatura_no = row["fatura_no"],
                                                                                                    musteri_adi = row["musteri_adi"],
                                                                                                    genel_toplam = toplam,
                                                                                                    odenen_toplam = odened,
                                                                                                    kalan = kalan,
                                                                                                    durum = row["durum"],
                                                                                                    vade_tarihi = vade,
                                                                                                    vadesi_gecti_mi = vadesi_gecti,
                                                                                                    gecikme_gun = gecikme_gun,
                                                                                                    )

                                                                                                    def tum_faturalar(
                                                                                                    self,
                                                                                                    durum_filtre: str = "",
                                                                                                    musteri_filtre: str = "",
                                                                                                    ) -> list[dict]:
                                                                                                        conn = self._get_conn()
                                                                                                    query = "SELECT * FROM faturalar WHERE 1=1"
                                                                                                    params: list = []
                                                                                                    if durum_filtre and durum_filtre != "Tümü":
                                                                                                        query += " AND durum=?"
                                                                                                        params.append(durum_filtre)
                                                                                                        if musteri_filtre:
                                                                                                            query += " AND musteri_adi LIKE ?"
                                                                                                            params.append(f"%{musteri_filtre}%")
                                                                                                            query += " ORDER BY fatura_tarihi DESC"
                                                                                                            rows = conn.execute(query, params).fetchall()
                                                                                                            return [dict(r) for r in rows]

                                                                                                            def fatura_odemeleri(self, fatura_id: int) -> list[dict]:
                                                                                                                conn = self._get_conn()
                                                                                                                rows = conn.execute(
                                                                                                                "SELECT * FROM fatura_odemeler WHERE fatura_id=? ORDER BY tarih",
                                                                                                                (fatura_id,)
                                                                                                                ).fetchall()
                                                                                                                return [dict(r) for r in rows]

                                                                                                                def tahsilat_ozeti(self) -> TahsilatOzet:
                                                                                                                    conn = self._get_conn()
                                                                                                                    rows = conn.execute(
                                                                                                                    "SELECT genel_toplam, odenen_toplam, durum, vade_tarihi FROM faturalar"
                                                                                                                    ).fetchall()
                                                                                                                    ozet = TahsilatOzet(fatura_sayisi=len(rows))
                                                                                                                    bugun = date.today()
                                                                                                                    for r in rows:
                                                                                                                        toplam = Decimal(str(r["genel_toplam"] or 0))
                                                                                                                        odenen = Decimal(str(r["odenen_toplam"] or 0))
                                                                                                                        kalan = toplam - odened
                                                                                                                        ozet.toplam_alacak += toplam
                                                                                                                        ozet.tahsil_edilen += odened
                                                                                                                        ozet.bekleyen += kalan if kalan > 0 else Decimal("0")
                                                                                                                        if r["durum"] not in ("Tamamlandı", "İptal"):
                                                                                                                            ozet.acik_fatura_sayisi += 1
                                                                                                                            vade = r["vade_tarihi"]
                                                                                                                            if vade and date.fromisoformat(str(vade)) < bugun and kalan > 0:
                                                                                                                                ozet.vadesi_gecmis += kalan
                                                                                                                                return ozet

                                                                                                                                def gecikti_durumlari_guncelle(self) -> int:
                                                                                                                                    """Vadesi geçmiş, hâlâ 'Bekliyor' faturaları 'Gecikti' yap."""
                                                                                                                                    conn = self._get_conn()
                                                                                                                                    bugun = str(date.today())
                                                                                                                                    cur = conn.execute(
                                                                                                                                    """UPDATE faturalar SET durum='Gecikti'
                                                                                                                                    WHERE durum='Bekliyor'
                                                                                                                                    AND vade_tarihi IS NOT NULL
                                                                                                                                    AND vade_tarihi < ?
                                                                                                                                    AND odenen_toplam < genel_toplam""",
                                                                                                                                    (bugun,)
                                                                                                                                    )
                                                                                                                                    conn.commit()
                                                                                                                                    return cur.rowcount

                                                                                                                                    def son_fatura_sira(self) -> int:
                                                                                                                                        conn = self._get_conn()
                                                                                                                                        row = conn.execute("SELECT COUNT(*) FROM faturalar").fetchone()
                                                                                                                                        return (row[0] or 0) + 1
