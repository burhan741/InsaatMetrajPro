"""
CŞB Birim Fiyat Poz Veritabanı Motoru
=======================================
Çevre, Şehircilik ve İklim Bakanlığı resmi birim fiyat pozlarını
SQLite'ta tutar. database.py'den bağımsız çalışır.

Tablo: csb_pozlari
  poz_kodu  : Resmi poz numarası (örn: '21.003')
  aciklama  : Poz tanımı
  birim     : Ölçü birimi (m², m³, kg, adet, m, ton, set)
  birim_fiyat: TL (yaklaşık 2026 değerleri — resmi listeden güncellenmeli)
  yil       : Fiyat yılı
  kategori  : İş grubu
  analiz_no : CŞB analiz kayıt numarası (opsiyonel)
  aktif     : 1=aktif, 0=pasif

NOT: Başlangıç seed fiyatları yaklaşık değerlerdir.
     Kesin fiyatlar için CŞB'nin resmi Yapım İşleri Birim Fiyat Listesini
     CSV/Excel olarak içe aktarın.
"""

import sqlite3
import csv
import os
import logging
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# DB YOLU TESPİTİ (database.py ile aynı mantık)
# ──────────────────────────────────────────────────────────────

def _get_db_path() -> Path:
    quantix_data = os.environ.get("QUANTIX_DATA_DIR")
    if quantix_data:
        return Path(quantix_data) / "insaat_metraj.db"
    return Path(__file__).parent.parent.parent / "data" / "insaat_metraj.db"


# ──────────────────────────────────────────────────────────────
# SEED DATA — CŞB 2026 Yapım İşleri Birim Fiyatları (Yaklaşık)
# ──────────────────────────────────────────────────────────────

_SEED_POZLAR: List[Tuple[str, str, str, float, str, str]] = [
    # (poz_kodu, aciklama, birim, birim_fiyat, kategori, analiz_no)

    # ── TOPRAK İŞLERİ ──────────────────────────────────────────
    ("16.001", "Her derinlikte kaya olmayan zeminlerde makineyle kazı", "m³",  165.00, "Toprak İşleri", ""),
    ("16.002", "Bitkisel toprak sıyrılması ve depolanması",              "m²",   32.00, "Toprak İşleri", ""),
    ("16.003", "Dolguda kullanılan zeminin serilip sıkıştırılması",      "m³",  125.00, "Toprak İşleri", ""),
    ("16.004", "Kazı malzemesinin sahadan uzaklaştırılması (1 km)",      "m³",   80.00, "Toprak İşleri", ""),
    ("16.005", "Grobeton altı temizlik betonu (C8/10, 5 cm)",            "m³", 2800.00, "Toprak İşleri", ""),

    # ── BETON İŞLERİ ───────────────────────────────────────────
    ("21.001", "C16/20 beton — Grobeton",                               "m³", 4100.00, "Beton İşleri", ""),
    ("21.002", "C25/30 beton — Temel",                                   "m³", 5200.00, "Beton İşleri", ""),
    ("21.003", "C25/30 beton — Kolon, kiriş, döşeme",                   "m³", 5450.00, "Beton İşleri", ""),
    ("21.004", "C30/37 beton — Perde",                                   "m³", 5700.00, "Beton İşleri", ""),
    ("21.005", "C35/45 beton — Köprü/viadukt üst yapısı",               "m³", 6800.00, "Beton İşleri", ""),
    ("21.011", "Kalıp yapılması ve sökülmesi — Kolon, kiriş, döşeme",   "m²",  650.00, "Beton İşleri", ""),
    ("21.012", "Kalıp yapılması ve sökülmesi — Temel, perde",            "m²",  580.00, "Beton İşleri", ""),
    ("21.013", "Kayar kalıp sistemi (özel)",                             "m²",  950.00, "Beton İşleri", ""),
    ("21.021", "Çelik hasır donatı (Q131–Q335)",                        "kg",   48.00, "Beton İşleri", ""),
    ("21.022", "Nervürlü çelik çubuk donatı S420",                      "kg",   43.00, "Beton İşleri", ""),
    ("21.023", "Düz yuvarlak çelik donatı S220",                        "kg",   41.00, "Beton İşleri", ""),
    ("21.031", "Hazır beton pompalı döküm fiyat farkı (kat başına)",    "m³",  120.00, "Beton İşleri", ""),

    # ── DUVAR İŞLERİ ───────────────────────────────────────────
    ("22.001", "Tuğla duvar örülmesi (19×19×13.5 — 1 tuğla)",           "m²",  920.00, "Duvar İşleri", ""),
    ("22.002", "Gazbeton duvar örülmesi (20 cm)",                        "m²",  850.00, "Duvar İşleri", ""),
    ("22.003", "Briket duvar (20 cm — M5 harç)",                         "m²",  760.00, "Duvar İşleri", ""),
    ("22.004", "Tuğla duvar (1/2 tuğla, 13.5 cm)",                      "m²",  680.00, "Duvar İşleri", ""),
    ("22.005", "Prefabrik beton blok duvar",                             "m²", 1100.00, "Duvar İşleri", ""),
    ("22.011", "Çelik konstrüksiyon cephe (alüminyum giydirme)",         "m²", 3200.00, "Duvar İşleri", ""),

    # ── SIVA İŞLERİ ────────────────────────────────────────────
    ("23.001", "İç sıva — Kireç harçlı, el ile (iki kat)",              "m²",  310.00, "Sıva İşleri", ""),
    ("23.002", "Dış sıva — Çimento harçlı",                             "m²",  380.00, "Sıva İşleri", ""),
    ("23.003", "Alçı sıva — İnce, makine ile",                          "m²",  245.00, "Sıva İşleri", ""),
    ("23.004", "Çimento şap (5 cm, tesviye betonu)",                    "m²",  220.00, "Sıva İşleri", ""),
    ("23.005", "Saten alçı — Tavan, el ile",                            "m²",  185.00, "Sıva İşleri", ""),
    ("23.006", "Akustik sıva (ses yalıtımlı)",                          "m²",  520.00, "Sıva İşleri", ""),

    # ── BOYA İŞLERİ ────────────────────────────────────────────
    ("24.001", "İç cephe su bazlı boya — 2 kat + astar",                "m²",  210.00, "Boya İşleri", ""),
    ("24.002", "Dış cephe silikon esaslı boya",                         "m²",  365.00, "Boya İşleri", ""),
    ("24.003", "Antipas + yağlı boya — Çelik yüzey",                   "m²",  320.00, "Boya İşleri", ""),
    ("24.004", "Epoksi boya — Zemin (endüstriyel)",                     "m²",  480.00, "Boya İşleri", ""),
    ("24.005", "İç cephe plastik boya — 3 kat",                         "m²",  245.00, "Boya İşleri", ""),

    # ── DÖŞEME İŞLERİ ──────────────────────────────────────────
    ("25.001", "Seramik döşeme (30×30 cm – 60×60 cm)",                  "m²",  580.00, "Döşeme İşleri", ""),
    ("25.002", "Granit / mermer döşeme",                                 "m²", 1400.00, "Döşeme İşleri", ""),
    ("25.003", "Laminant parke döşeme (12 mm)",                         "m²",  620.00, "Döşeme İşleri", ""),
    ("25.004", "Halıfleks döşeme",                                       "m²",  380.00, "Döşeme İşleri", ""),
    ("25.005", "Ahşap döşeme (meşe parke, 15 mm)",                      "m²", 1800.00, "Döşeme İşleri", ""),
    ("25.006", "Mozaik döşeme",                                          "m²",  720.00, "Döşeme İşleri", ""),
    ("25.011", "Mermer merdiven basamağı (2 cm kalınlık)",              "m",  1250.00, "Döşeme İşleri", ""),

    # ── YALITIM İŞLERİ ─────────────────────────────────────────
    ("26.001", "Isı yalıtımı — EPS 5 cm mantolama",                    "m²",  540.00, "Yalıtım İşleri", ""),
    ("26.002", "Su yalıtımı — Bitümlü membran, 2 kat",                  "m²",  430.00, "Yalıtım İşleri", ""),
    ("26.003", "XPS yalıtım — 5 cm, teras çatı",                        "m²",  580.00, "Yalıtım İşleri", ""),
    ("26.004", "Cam yünü yalıtım — 5 cm",                               "m²",  320.00, "Yalıtım İşleri", ""),
    ("26.005", "Poliüretan köpük yalıtım (püskürtme)",                  "m²",  680.00, "Yalıtım İşleri", ""),
    ("26.006", "Ses yalıtımı — Teraterm 3 cm",                          "m²",  280.00, "Yalıtım İşleri", ""),

    # ── ÇATI İŞLERİ ────────────────────────────────────────────
    ("27.001", "Kiremit kaplama — Beton kiremit",                        "m²",  690.00, "Çatı İşleri", ""),
    ("27.002", "Trapez sac çatı kaplama",                                "m²",  870.00, "Çatı İşleri", ""),
    ("27.003", "Çatı ahşap makas yapımı",                               "m³", 9500.00, "Çatı İşleri", ""),
    ("27.004", "Düz çatı — Beton + membran + EPS",                      "m²", 1200.00, "Çatı İşleri", ""),
    ("27.005", "Oluklu eternit çatı kaplama",                            "m²",  580.00, "Çatı İşleri", ""),

    # ── ELEKTRİK TESİSATI ──────────────────────────────────────
    ("30.001", "Sıva altı tesisat borusu + kablo (NYM 3×2.5)",          "m",   200.00, "Elektrik Tesisatı", ""),
    ("30.002", "Priz — Topraklı, 16A montajı",                          "adet", 360.00, "Elektrik Tesisatı", ""),
    ("30.003", "Aydınlatma armatürü montajı (LED panel 60×60)",         "adet", 540.00, "Elektrik Tesisatı", ""),
    ("30.004", "Sigorta panosu montajı (24 devre)",                     "adet",3800.00, "Elektrik Tesisatı", ""),
    ("30.005", "Acil aydınlatma armatürü",                              "adet", 850.00, "Elektrik Tesisatı", ""),
    ("30.006", "Topraklama sistemi (çubuk + iletken)",                  "m",   180.00, "Elektrik Tesisatı", ""),

    # ── MEKANİK TESİSAT ────────────────────────────────────────
    ("31.001", "Plastik boru tesisat — Ø32–Ø110 (PP-R)",               "m",   320.00, "Mekanik Tesisat", ""),
    ("31.002", "Kombi montajı — 24 kW, doğalgaz",                       "adet",9500.00, "Mekanik Tesisat", ""),
    ("31.003", "Banyo tesisatı — Klozet, lavabo, duş seti",             "set",14000.00, "Mekanik Tesisat", ""),
    ("31.004", "Kalorifer tesisatı — Panel radyatör (600 lük 6 dilim)", "adet",2800.00, "Mekanik Tesisat", ""),
    ("31.005", "Klima montajı — Split 12000 BTU",                       "adet",7500.00, "Mekanik Tesisat", ""),
    ("31.006", "Yangın algılama dedektörü",                             "adet",1200.00, "Mekanik Tesisat", ""),
    ("31.007", "Sprinkler başlığı montajı",                             "adet", 950.00, "Mekanik Tesisat", ""),

    # ── KAPI / PENCERE ─────────────────────────────────────────
    ("33.001", "PVC pencere — Tek kanat, Enerji sınıfı A",              "m²", 3200.00, "Kapı/Pencere", ""),
    ("33.002", "PVC balkon kapısı — Çift kanat",                        "m²", 3600.00, "Kapı/Pencere", ""),
    ("33.003", "Çelik kapı montajı — Apartman giriş",                   "adet",5200.00, "Kapı/Pencere", ""),
    ("33.004", "Ahşap iç kapı — Amerikan panel",                        "adet",4500.00, "Kapı/Pencere", ""),
    ("33.005", "Alüminyum doğrama — Cephe sistemi",                     "m²", 4800.00, "Kapı/Pencere", ""),
    ("33.006", "Cam balkon sistemi (isıcam)",                            "m²", 3800.00, "Kapı/Pencere", ""),

    # ── ÇELİK YAPI ─────────────────────────────────────────────
    ("34.001", "Çelik kolon ve kiriş imalatı + montajı (S235)",         "ton",38000.00, "Çelik Yapı", ""),
    ("34.002", "Trapez sac döşeme (t=1 mm)",                            "m²",  680.00, "Çelik Yapı", ""),
    ("34.003", "Çelik merdiven imalatı",                                "kg",   95.00, "Çelik Yapı", ""),
]


# ──────────────────────────────────────────────────────────────
# ANA SINIF
# ──────────────────────────────────────────────────────────────

class CSBPozEngine:
    """
    CŞB Birim Fiyat Poz Veritabanı Motoru.

    Neyi çözüyoruz:
    Yaklaşık maliyet cetveli hazırlarken kullanıcının poz kodunu
    yazınca otomatik tanım, birim ve fiyat gelmesi; büyük poz
    listesinde metin arama yapılabilmesi; yeni CŞB listesi
    geldiğinde CSV import ile hızla güncelleme.

    Nasıl test ederiz:
    - poz_ara('21.003') → beton poz kaydı dönmeli
    - metin_ara('beton') → en az 5 sonuç dönmeli
    - csv_import → mevcut kayıtları günceller, yeni ekler
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or _get_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tablo()
        self._seed_veri()

    # ------------------------------------------------------------------
    # CONTEXT MANAGER
    # ------------------------------------------------------------------

    @contextmanager
    def _baglanti(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # TABLO OLUŞTURMA
    # ------------------------------------------------------------------

    def _init_tablo(self) -> None:
        with self._baglanti() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS csb_pozlari (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    poz_kodu     TEXT    UNIQUE NOT NULL,
                    aciklama     TEXT    NOT NULL,
                    birim        TEXT    NOT NULL,
                    birim_fiyat  REAL    NOT NULL,
                    yil          INTEGER NOT NULL DEFAULT 2026,
                    kategori     TEXT    DEFAULT '',
                    analiz_no    TEXT    DEFAULT '',
                    aktif        INTEGER DEFAULT 1
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_csb_poz_kodu ON csb_pozlari(poz_kodu)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_csb_kategori ON csb_pozlari(kategori)"
            )
        logger.debug("csb_pozlari tablosu hazır")

    # ------------------------------------------------------------------
    # SEED VERİ
    # ------------------------------------------------------------------

    def _seed_veri(self) -> None:
        with self._baglanti() as conn:
            mevcut = conn.execute(
                "SELECT COUNT(*) FROM csb_pozlari"
            ).fetchone()[0]
            if mevcut > 0:
                return  # Tablo doluysa seed atla

        logger.info(f"CŞB poz seed verisi ekleniyor ({len(_SEED_POZLAR)} poz)…")
        with self._baglanti() as conn:
            conn.executemany(
                """INSERT OR IGNORE INTO csb_pozlari
                   (poz_kodu, aciklama, birim, birim_fiyat, yil, kategori, analiz_no)
                   VALUES (?, ?, ?, ?, 2026, ?, ?)""",
                _SEED_POZLAR,
            )
        logger.info("Seed tamamlandı")

    # ------------------------------------------------------------------
    # OKUMA
    # ------------------------------------------------------------------

    def poz_ara(self, poz_kodu: str) -> Optional[Dict[str, Any]]:
        """Poz koduna göre tam eşleşme ara."""
        with self._baglanti() as conn:
            row = conn.execute(
                "SELECT * FROM csb_pozlari WHERE poz_kodu=? AND aktif=1",
                (poz_kodu.strip(),)
            ).fetchone()
        return dict(row) if row else None

    def metin_ara(
        self,
        metin: str,
        kategori: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Tanım veya poz kodu içinde metin arama (LIKE)."""
        arama = f"%{metin.strip()}%"
        if kategori:
            with self._baglanti() as conn:
                rows = conn.execute(
                    """SELECT * FROM csb_pozlari
                       WHERE aktif=1 AND kategori=?
                         AND (aciklama LIKE ? OR poz_kodu LIKE ?)
                       ORDER BY poz_kodu LIMIT ?""",
                    (kategori, arama, arama, limit)
                ).fetchall()
        else:
            with self._baglanti() as conn:
                rows = conn.execute(
                    """SELECT * FROM csb_pozlari
                       WHERE aktif=1
                         AND (aciklama LIKE ? OR poz_kodu LIKE ?)
                       ORDER BY poz_kodu LIMIT ?""",
                    (arama, arama, limit)
                ).fetchall()
        return [dict(r) for r in rows]

    def tum_pozlar(
        self,
        kategori: Optional[str] = None,
        sadece_aktif: bool = True,
    ) -> List[Dict[str, Any]]:
        """Tüm pozları listele (opsiyonel kategori filtresi)."""
        aktif_filtre = "AND aktif=1" if sadece_aktif else ""
        if kategori:
            with self._baglanti() as conn:
                rows = conn.execute(
                    f"SELECT * FROM csb_pozlari WHERE kategori=? {aktif_filtre} ORDER BY poz_kodu",
                    (kategori,)
                ).fetchall()
        else:
            with self._baglanti() as conn:
                rows = conn.execute(
                    f"SELECT * FROM csb_pozlari WHERE 1=1 {aktif_filtre} ORDER BY poz_kodu"
                ).fetchall()
        return [dict(r) for r in rows]

    def kategoriler(self) -> List[str]:
        """Distinct kategori listesi."""
        with self._baglanti() as conn:
            rows = conn.execute(
                "SELECT DISTINCT kategori FROM csb_pozlari WHERE aktif=1 ORDER BY kategori"
            ).fetchall()
        return [r[0] for r in rows if r[0]]

    def toplam_poz_sayisi(self) -> int:
        with self._baglanti() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM csb_pozlari WHERE aktif=1"
            ).fetchone()[0]

    # ------------------------------------------------------------------
    # YAZMA
    # ------------------------------------------------------------------

    def poz_ekle(
        self,
        poz_kodu: str,
        aciklama: str,
        birim: str,
        birim_fiyat: float,
        kategori: str = "",
        analiz_no: str = "",
        yil: int = 2026,
    ) -> bool:
        """Yeni poz ekle. Mevcut kodsa False döner."""
        try:
            with self._baglanti() as conn:
                conn.execute(
                    """INSERT INTO csb_pozlari
                       (poz_kodu, aciklama, birim, birim_fiyat, yil, kategori, analiz_no)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (poz_kodu, aciklama, birim, birim_fiyat, yil, kategori, analiz_no)
                )
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Poz zaten mevcut: {poz_kodu}")
            return False

    def poz_guncelle(
        self,
        poz_kodu: str,
        aciklama: Optional[str] = None,
        birim: Optional[str] = None,
        birim_fiyat: Optional[float] = None,
        kategori: Optional[str] = None,
        yil: Optional[int] = None,
    ) -> bool:
        """Mevcut poz bilgilerini güncelle."""
        alanlar = []
        degerler = []
        if aciklama is not None:
            alanlar.append("aciklama=?"); degerler.append(aciklama)
        if birim is not None:
            alanlar.append("birim=?"); degerler.append(birim)
        if birim_fiyat is not None:
            alanlar.append("birim_fiyat=?"); degerler.append(birim_fiyat)
        if kategori is not None:
            alanlar.append("kategori=?"); degerler.append(kategori)
        if yil is not None:
            alanlar.append("yil=?"); degerler.append(yil)
        if not alanlar:
            return False
        degerler.append(poz_kodu)
        with self._baglanti() as conn:
            cur = conn.execute(
                f"UPDATE csb_pozlari SET {', '.join(alanlar)} WHERE poz_kodu=?",
                degerler
            )
        return cur.rowcount > 0

    def poz_pasife_al(self, poz_kodu: str) -> bool:
        """Poz kodunu pasif yap (silmez, sadece aktif=0)."""
        with self._baglanti() as conn:
            cur = conn.execute(
                "UPDATE csb_pozlari SET aktif=0 WHERE poz_kodu=?",
                (poz_kodu,)
            )
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # CSV İÇE/DIŞA AKTARMA
    # ------------------------------------------------------------------

    def csv_disari_aktar(self, dosya_yolu: str) -> int:
        """Tüm aktif pozları CSV'ye yaz. Yazılan satır sayısı döner."""
        pozlar = self.tum_pozlar()
        if not pozlar:
            return 0
        with open(dosya_yolu, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["poz_kodu", "aciklama", "birim", "birim_fiyat",
                            "yil", "kategori", "analiz_no"],
            )
            writer.writeheader()
            for p in pozlar:
                writer.writerow({k: p[k] for k in writer.fieldnames})
        logger.info(f"CSV dışa aktarıldı: {dosya_yolu} ({len(pozlar)} poz)")
        return len(pozlar)

    def csv_iceri_aktar(self, dosya_yolu: str, guncelle: bool = True) -> Tuple[int, int]:
        """
        CSV'den poz yükle.

        Args:
            dosya_yolu: CSV dosya yolu
            guncelle:   True=mevcut poz fiyatını güncelle, False=sadece yeni ekle

        Returns:
            (eklenen_adet, guncellenen_adet)
        """
        eklenen = 0
        guncellenen = 0
        with open(dosya_yolu, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for satir in reader:
                poz_kodu = satir.get("poz_kodu", "").strip()
                if not poz_kodu:
                    continue
                try:
                    birim_fiyat = float(satir.get("birim_fiyat", 0))
                except ValueError:
                    continue

                mevcut = self.poz_ara(poz_kodu)
                if mevcut:
                    if guncelle:
                        self.poz_guncelle(
                            poz_kodu,
                            aciklama=satir.get("aciklama"),
                            birim=satir.get("birim"),
                            birim_fiyat=birim_fiyat,
                            kategori=satir.get("kategori"),
                            yil=int(satir.get("yil", 2026)),
                        )
                        guncellenen += 1
                else:
                    self.poz_ekle(
                        poz_kodu=poz_kodu,
                        aciklama=satir.get("aciklama", ""),
                        birim=satir.get("birim", ""),
                        birim_fiyat=birim_fiyat,
                        kategori=satir.get("kategori", ""),
                        analiz_no=satir.get("analiz_no", ""),
                        yil=int(satir.get("yil", 2026)),
                    )
                    eklenen += 1

        logger.info(f"CSV içe aktarıldı: +{eklenen} yeni, ~{guncellenen} güncellendi")
        return eklenen, guncellenen

    # ------------------------------------------------------------------
    # YARDIMCI
    # ------------------------------------------------------------------

    def birim_fiyat_decimal(self, poz_kodu: str) -> Optional[Decimal]:
        """Poz birim fiyatını Decimal olarak döner (yaklaşık maliyet hesabı için)."""
        poz = self.poz_ara(poz_kodu)
        if poz is None:
            return None
        return Decimal(str(poz["birim_fiyat"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
