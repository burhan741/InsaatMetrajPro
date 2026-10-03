"""
bfa_engine.py — Birim Fiyat Analizi (BFA) Motoru
CŞB standardına uygun analiz, hesaplama, PDF ve CSV desteği.
database.py'den bağımsız, kendi SQLite bağlantısını kurar.
Rev-74 (2026-04-25)
"""

import csv
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    from app.utils.font_utils import get_fonts as _get_fonts
    _PDF_FONT, _PDF_FONT_BOLD = _get_fonts()
except Exception:
    _PDF_FONT, _PDF_FONT_BOLD = _PDF_FONT, _PDF_FONT_BOLD

# ---------------------------------------------------------------------------
# Seed verisi — 10 kritik CŞB pozu
# ---------------------------------------------------------------------------
_SEED_ANALIZLER = {
    "21.003": {
        "tanim": "C25/30 beton — Kolon, kiriş, döşeme",
        "birim": "m³",
        "bileseler": [
            ("malzeme", "Portland Çimentosu (42.5R)", "kg", 380.0, 4.20),
            ("malzeme", "Kum (0-4 mm, elek altı)", "m³", 0.45, 180.0),
            ("malzeme", "Çakıl (4-22 mm)", "m³", 0.90, 220.0),
            ("malzeme", "Beton katkı maddesi (plastifiyan)", "kg", 4.0, 22.0),
            ("malzeme", "Su", "m³", 0.18, 10.0),
            ("iscilik", "Usta (betoncu)", "gün", 0.50, 950.0),
            ("iscilik", "Yardımcı işçi", "gün", 1.20, 680.0),
            ("makine", "Beton mikseri (500 lt)", "saat", 0.40, 1800.0),
            ("makine", "Beton vibratörü (iç)", "saat", 0.50, 250.0),
        ],
    },
    "21.011": {
        "tanim": "Kalıp yapılması ve sökülmesi — Kolon, kiriş, döşeme",
        "birim": "m²",
        "bileseler": [
            ("malzeme", "Tahta kalıp (çam kereste)", "m³", 0.012, 18000.0),
            ("malzeme", "Çivi ve bağlantı elemanları", "kg", 0.80, 80.0),
            ("malzeme", "Kalıp yağı (ayrılma maddesi)", "kg", 0.15, 120.0),
            ("iscilik", "Usta (marangoz/kalıpçı)", "gün", 0.25, 950.0),
            ("iscilik", "Yardımcı işçi", "gün", 0.35, 680.0),
            ("makine", "El aletleri (tornavida, mengene vb.)", "saat", 0.50, 120.0),
        ],
    },
    "21.022": {
        "tanim": "Nervürlü çelik çubuk donatı S420",
        "birim": "kg",
        "bileseler": [
            ("malzeme", "Nervürlü demir S420 (%3 fire payı dahil)", "kg", 1.03, 36.0),
            ("malzeme", "Bağlama teli (tavlı, Ø1mm)", "kg", 0.012, 75.0),
            ("iscilik", "Usta (demirci)", "gün", 0.003, 950.0),
            ("iscilik", "Yardımcı işçi", "gün", 0.003, 680.0),
            ("makine", "Demir bükme makinesi (elektrikli)", "saat", 0.004, 600.0),
        ],
    },
    "22.001": {
        "tanim": "Tuğla duvar örülmesi (19×19×13.5 — 1 tuğla kalınlık)",
        "birim": "m²",
        "bileseler": [
            ("malzeme", "Delikli tuğla (19×19×13.5)", "adet", 68.0, 9.50),
            ("malzeme", "Kum-kireç harcı (M5)", "m³", 0.030, 850.0),
            ("malzeme", "Portland çimentosu", "kg", 8.0, 4.20),
            ("iscilik", "Usta (duvar ustası)", "gün", 0.12, 950.0),
            ("iscilik", "Yardımcı işçi", "gün", 0.18, 680.0),
        ],
    },
    "22.002": {
        "tanim": "Gazbeton duvar örülmesi (20 cm, yapıştırıcı harçlı)",
        "birim": "m²",
        "bileseler": [
            ("malzeme", "Gazbeton blok (60×20×25 cm)", "adet", 10.0, 65.0),
            ("malzeme", "Gazbeton yapıştırma harcı (hazır)", "kg", 4.5, 18.0),
            ("iscilik", "Usta (duvar ustası)", "gün", 0.08, 950.0),
            ("iscilik", "Yardımcı işçi", "gün", 0.12, 680.0),
        ],
    },
    "23.002": {
        "tanim": "İç sıva — Çimento-kireç karışımı, 2 kat, 15 mm",
        "birim": "m²",
        "bileseler": [
            ("malzeme", "Portland çimentosu (42.5)", "kg", 6.5, 4.20),
            ("malzeme", "Söndürülmüş kireç (hidrat)", "kg", 4.0, 8.50),
            ("malzeme", "Sıva kumu (elek altı, 0-3 mm)", "m³", 0.025, 250.0),
            ("malzeme", "Su", "m³", 0.010, 10.0),
            ("iscilik", "Usta (sıvacı)", "gün", 0.040, 950.0),
            ("iscilik", "Yardımcı işçi", "gün", 0.060, 680.0),
            ("makine", "Sıva makinesi (opsiyonel)", "saat", 0.020, 500.0),
        ],
    },
    "24.001": {
        "tanim": "İç boya — Akrilik plastik boya (astar + 2 kat)",
        "birim": "m²",
        "bileseler": [
            ("malzeme", "Alçı macun (düz zemin için, 1. kat)", "kg", 0.40, 35.0),
            ("malzeme", "Astar boya (nefes alan)", "kg", 0.15, 85.0),
            ("malzeme", "Plastik iç boya (mat, 2 kat)", "kg", 0.25, 120.0),
            ("iscilik", "Usta (boyacı)", "gün", 0.022, 950.0),
            ("iscilik", "Yardımcı işçi", "gün", 0.015, 680.0),
        ],
    },
    "26.001": {
        "tanim": "Seramik döşeme kaplaması (30×30 cm, C2 yapıştırıcı)",
        "birim": "m²",
        "bileseler": [
            ("malzeme", "Seramik karo (30×30, %5 fire dahil)", "m²", 1.05, 380.0),
            ("malzeme", "Fayans yapıştırıcı harcı (C2 sınıfı)", "kg", 5.5, 22.0),
            ("malzeme", "Derz dolgu malzemesi (renkli)", "kg", 0.30, 55.0),
            ("iscilik", "Usta (karocu)", "gün", 0.125, 950.0),
            ("iscilik", "Yardımcı işçi", "gün", 0.100, 680.0),
        ],
    },
    "16.001": {
        "tanim": "Her derinlikte kaya olmayan zeminlerde makineyle kazı",
        "birim": "m³",
        "bileseler": [
            ("malzeme", "Motorin (yakıt)", "lt", 0.35, 55.0),
            ("makine", "Ekskavatör (0.6 m³ kepçe, paletli)", "saat", 0.08, 1800.0),
            ("iscilik", "Operatör", "gün", 0.010, 1200.0),
            ("iscilik", "Yardımcı işçi", "gün", 0.005, 680.0),
        ],
    },
    "16.003": {
        "tanim": "Dolguda kullanılan zeminin serilip sıkıştırılması (her 20 cm'de)",
        "birim": "m³",
        "bileseler": [
            ("malzeme", "Motorin (yakıt)", "lt", 0.20, 55.0),
            ("makine", "Vibrasyonlu silindir (6-8 ton)", "saat", 0.06, 1500.0),
            ("makine", "Greyder (120-145 hp)", "saat", 0.04, 2000.0),
            ("iscilik", "Operatör", "gün", 0.015, 1200.0),
            ("iscilik", "Yardımcı işçi", "gün", 0.020, 680.0),
        ],
    },
}

# CŞB sabit oranları
_GENEL_GIDER_ORAN = 0.15
_KAR_RISK_ORAN = 0.10

# Renk kodları (PDF için hex → reportlab RGB)
_TUR_RENKLERI = {
    "malzeme": (0.85, 0.92, 1.00),   # açık mavi
    "iscilik":  (0.85, 1.00, 0.88),  # açık yeşil
    "makine":   (1.00, 0.92, 0.80),  # açık turuncu
}

_TUR_ETIKETLERI = {
    "malzeme": "Malzeme",
    "iscilik":  "İşçilik",
    "makine":   "Makine",
}


# ---------------------------------------------------------------------------
# BFAEngine
# ---------------------------------------------------------------------------
class BFAEngine:
    """
    Birim Fiyat Analizi motoru.
    database.py'den bağımsız — kendi SQLite bağlantısını kurar.

    CŞB Hesaplama Formülü:
        Ara Toplam  = Malzeme + İşçilik + Makine
        Genel Gider = Ara Toplam × 0.15
        Kar/Risk    = (Ara Toplam + Genel Gider) × 0.10
        Birim Fiyat = Ara Toplam + Genel Gider + Kar/Risk
    """

    def __init__(self):
        self._db_yolu = self._db_yolu_tespit()
        self._tablolari_olustur()
        self._seed_yukle()

    # -----------------------------------------------------------------------
    # Yardımcı: DB yolu tespiti
    # -----------------------------------------------------------------------
    @staticmethod
    def _db_yolu_tespit() -> Path:
        env = os.environ.get("QUANTIX_DATA_DIR")
        if env:
            p = Path(env) / "insaat_metraj.db"
        else:
            p = Path(__file__).parent.parent.parent / "data" / "insaat_metraj.db"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # -----------------------------------------------------------------------
    # Yardımcı: Bağlantı context manager
    # -----------------------------------------------------------------------
    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(str(self._db_yolu))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # Tablo oluşturma
    # -----------------------------------------------------------------------
    def _tablolari_olustur(self):
        ddl = """
        CREATE TABLE IF NOT EXISTS bfa_analizleri (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            poz_kodu    TEXT    NOT NULL,
            poz_tanimi  TEXT,
            birim       TEXT,
            yil         INTEGER DEFAULT 2026,
            aktif       INTEGER DEFAULT 1,
            UNIQUE(poz_kodu)
        );

        CREATE TABLE IF NOT EXISTS bfa_bilesenler (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            analiz_id   INTEGER NOT NULL,
            tur         TEXT    NOT NULL,
            aciklama    TEXT    NOT NULL,
            birim       TEXT,
            miktar      REAL    DEFAULT 0,
            birim_fiyat REAL    DEFAULT 0,
            tutar       REAL    DEFAULT 0,
            sira        INTEGER DEFAULT 0,
            FOREIGN KEY (analiz_id) REFERENCES bfa_analizleri(id) ON DELETE CASCADE
        );
        """
        try:
            with self._get_conn() as conn:
                conn.executescript(ddl)
        except Exception as e:
            logger.error("BFAEngine tablo oluşturma hatası: %s", e)

    # -----------------------------------------------------------------------
    # Seed yükleme (sadece tablo boşsa)
    # -----------------------------------------------------------------------
    def _seed_yukle(self):
        try:
            with self._get_conn() as conn:
                sayi = conn.execute(
                    "SELECT COUNT(*) FROM bfa_analizleri"
                ).fetchone()[0]
                if sayi > 0:
                    return
                for poz_kodu, veri in _SEED_ANALIZLER.items():
                    cursor = conn.execute(
                        """
                        INSERT INTO bfa_analizleri (poz_kodu, poz_tanimi, birim)
                        VALUES (?, ?, ?)
                        """,
                        (poz_kodu, veri["tanim"], veri["birim"]),
                    )
                    analiz_id = cursor.lastrowid
                    for sira, b in enumerate(veri["bileseler"], start=1):
                        tur, aciklama, birim, miktar, birim_fiyat = b
                        tutar = miktar * birim_fiyat
                        conn.execute(
                            """
                            INSERT INTO bfa_bilesenler
                                (analiz_id, tur, aciklama, birim, miktar, birim_fiyat, tutar, sira)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (analiz_id, tur, aciklama, birim, miktar, birim_fiyat, tutar, sira),
                        )
            logger.info("BFAEngine: %d seed analiz yüklendi.", len(_SEED_ANALIZLER))
        except Exception as e:
            logger.error("BFAEngine seed yükleme hatası: %s", e)

    # -----------------------------------------------------------------------
    # 1. analiz_getir — analiz + bileşenler birlikte
    # -----------------------------------------------------------------------
    def analiz_getir(self, poz_kodu: str) -> Optional[dict]:
        """Verilen poz koduna ait analiz ve bileşenlerini döndürür."""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM bfa_analizleri WHERE poz_kodu = ? AND aktif = 1",
                    (poz_kodu,),
                ).fetchone()
                if row is None:
                    return None
                analiz = dict(row)
                bileseler = conn.execute(
                    """
                    SELECT * FROM bfa_bilesenler
                    WHERE analiz_id = ?
                    ORDER BY sira, id
                    """,
                    (analiz["id"],),
                ).fetchall()
                analiz["bileseler"] = [dict(b) for b in bileseler]
                return analiz
        except Exception as e:
            logger.error("analiz_getir hatası (%s): %s", poz_kodu, e)
            return None

    # -----------------------------------------------------------------------
    # 2. tum_analizler — özet liste (bileşenler olmadan)
    # -----------------------------------------------------------------------
    def tum_analizler(self) -> List[dict]:
        """Tüm aktif analizlerin özet listesini döndürür."""
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT a.id, a.poz_kodu, a.poz_tanimi, a.birim, a.yil,
                           COUNT(b.id) AS bilesen_sayisi
                    FROM bfa_analizleri a
                    LEFT JOIN bfa_bilesenler b ON b.analiz_id = a.id
                    WHERE a.aktif = 1
                    GROUP BY a.id
                    ORDER BY a.poz_kodu
                    """
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error("tum_analizler hatası: %s", e)
            return []

    # -----------------------------------------------------------------------
    # 3. analiz_kaydet — UPSERT
    # -----------------------------------------------------------------------
    def analiz_kaydet(
        self,
        poz_kodu: str,
        tanim: str,
        birim: str,
        bileseler: List[dict],
    ) -> int:
        """
        Analizi kaydeder (varsa günceller, yoksa ekler).
        bileseler: [{"tur", "aciklama", "birim", "miktar", "birim_fiyat", "sira"}]
        Döndürür: analiz_id (int), hata durumunda -1.
        """
        try:
            with self._get_conn() as conn:
                mevcut = conn.execute(
                    "SELECT id FROM bfa_analizleri WHERE poz_kodu = ?",
                    (poz_kodu,),
                ).fetchone()
                if mevcut:
                    analiz_id = mevcut["id"]
                    conn.execute(
                        """
                        UPDATE bfa_analizleri
                        SET poz_tanimi = ?, birim = ?, aktif = 1
                        WHERE id = ?
                        """,
                        (tanim, birim, analiz_id),
                    )
                    conn.execute(
                        "DELETE FROM bfa_bilesenler WHERE analiz_id = ?",
                        (analiz_id,),
                    )
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO bfa_analizleri (poz_kodu, poz_tanimi, birim)
                        VALUES (?, ?, ?)
                        """,
                        (poz_kodu, tanim, birim),
                    )
                    analiz_id = cursor.lastrowid

                for sira, b in enumerate(bileseler, start=1):
                    miktar = float(b.get("miktar", 0))
                    birim_fiyat = float(b.get("birim_fiyat", 0))
                    tutar = miktar * birim_fiyat
                    conn.execute(
                        """
                        INSERT INTO bfa_bilesenler
                            (analiz_id, tur, aciklama, birim, miktar, birim_fiyat, tutar, sira)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            analiz_id,
                            b.get("tur", "malzeme"),
                            b.get("aciklama", ""),
                            b.get("birim", ""),
                            miktar,
                            birim_fiyat,
                            tutar,
                            b.get("sira", sira),
                        ),
                    )
                return analiz_id
        except Exception as e:
            logger.error("analiz_kaydet hatası (%s): %s", poz_kodu, e)
            return -1

    # -----------------------------------------------------------------------
    # 4. bilesen_guncelle
    # -----------------------------------------------------------------------
    def bilesen_guncelle(self, bilesen_id: int, miktar: float, birim_fiyat: float) -> bool:
        """Bileşenin miktar ve birim fiyatını günceller; tutar otomatik hesaplanır."""
        try:
            tutar = float(miktar) * float(birim_fiyat)
            with self._get_conn() as conn:
                conn.execute(
                    """
                    UPDATE bfa_bilesenler
                    SET miktar = ?, birim_fiyat = ?, tutar = ?
                    WHERE id = ?
                    """,
                    (miktar, birim_fiyat, tutar, bilesen_id),
                )
            return True
        except Exception as e:
            logger.error("bilesen_guncelle hatası (%d): %s", bilesen_id, e)
            return False

    # -----------------------------------------------------------------------
    # 5. bilesen_ekle
    # -----------------------------------------------------------------------
    def bilesen_ekle(
        self,
        analiz_id: int,
        tur: str,
        aciklama: str,
        birim: str,
        miktar: float,
        birim_fiyat: float,
        sira: int = 0,
    ) -> int:
        """Analize yeni bileşen ekler. Döndürür: bilesen_id, hata: -1."""
        try:
            tutar = float(miktar) * float(birim_fiyat)
            with self._get_conn() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO bfa_bilesenler
                        (analiz_id, tur, aciklama, birim, miktar, birim_fiyat, tutar, sira)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (analiz_id, tur, aciklama, birim, miktar, birim_fiyat, tutar, sira),
                )
                return cursor.lastrowid
        except Exception as e:
            logger.error("bilesen_ekle hatası (analiz_id=%d): %s", analiz_id, e)
            return -1

    # -----------------------------------------------------------------------
    # 6. bilesen_sil
    # -----------------------------------------------------------------------
    def bilesen_sil(self, bilesen_id: int) -> bool:
        """Bileşeni siler."""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "DELETE FROM bfa_bilesenler WHERE id = ?",
                    (bilesen_id,),
                )
            return True
        except Exception as e:
            logger.error("bilesen_sil hatası (%d): %s", bilesen_id, e)
            return False

    # -----------------------------------------------------------------------
    # 7. hesapla — tam CŞB hesaplama
    # -----------------------------------------------------------------------
    def hesapla(self, poz_kodu: str) -> dict:
        """
        CŞB standardına göre tam hesaplama yapar.
        Döndürür: hesap sonucu dict veya hata durumunda boş dict.
        """
        analiz = self.analiz_getir(poz_kodu)
        if analiz is None:
            logger.warning("hesapla: '%s' poz kodu bulunamadı.", poz_kodu)
            return {}

        bileseler = analiz.get("bileseler", [])

        malzeme_toplam = sum(
            b["miktar"] * b["birim_fiyat"]
            for b in bileseler
            if b.get("tur") == "malzeme"
        )
        iscilik_toplam = sum(
            b["miktar"] * b["birim_fiyat"]
            for b in bileseler
            if b.get("tur") == "iscilik"
        )
        makine_toplam = sum(
            b["miktar"] * b["birim_fiyat"]
            for b in bileseler
            if b.get("tur") == "makine"
        )

        ara_toplam = malzeme_toplam + iscilik_toplam + makine_toplam
        genel_gider = ara_toplam * _GENEL_GIDER_ORAN
        kar_risk = (ara_toplam + genel_gider) * _KAR_RISK_ORAN
        birim_fiyat = ara_toplam + genel_gider + kar_risk

        bilesen_listesi = [
            {
                "id": b["id"],
                "tur": b["tur"],
                "aciklama": b["aciklama"],
                "birim": b["birim"],
                "miktar": b["miktar"],
                "birim_fiyat": b["birim_fiyat"],
                "tutar": b["miktar"] * b["birim_fiyat"],
                "sira": b["sira"],
            }
            for b in bileseler
        ]

        return {
            "poz_kodu": analiz["poz_kodu"],
            "poz_tanimi": analiz["poz_tanimi"],
            "birim": analiz["birim"],
            "malzeme_toplam": round(malzeme_toplam, 4),
            "iscilik_toplam": round(iscilik_toplam, 4),
            "makine_toplam": round(makine_toplam, 4),
            "ara_toplam": round(ara_toplam, 4),
            "genel_gider_oran": _GENEL_GIDER_ORAN,
            "genel_gider": round(genel_gider, 4),
            "kar_risk_oran": _KAR_RISK_ORAN,
            "kar_risk": round(kar_risk, 4),
            "birim_fiyat": round(birim_fiyat, 4),
            "bileseler": bilesen_listesi,
        }

    # -----------------------------------------------------------------------
    # 8. pdf_analiz_belgesi_uret
    # -----------------------------------------------------------------------
    def pdf_analiz_belgesi_uret(self, poz_kodu: str, dosya_yolu: str) -> bool:
        """
        Analiz cetveli PDF'i oluşturur (A4 dikey).
        reportlab bulunamazsa False döndürür.
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, HRFlowable,
            )
        except ImportError:
            logger.error("pdf_analiz_belgesi_uret: reportlab kurulu değil.")
            return False

        sonuc = self.hesapla(poz_kodu)
        if not sonuc:
            logger.error("pdf_analiz_belgesi_uret: '%s' hesaplanamadı.", poz_kodu)
            return False

        try:
            doc = SimpleDocTemplate(
                dosya_yolu,
                pagesize=A4,
                leftMargin=1.5 * cm,
                rightMargin=1.5 * cm,
                topMargin=1.5 * cm,
                bottomMargin=2.0 * cm,
            )
            genislik = A4[0] - 3.0 * cm

            stiller = getSampleStyleSheet()
            baslik_stili = ParagraphStyle(
                "Baslik",
                parent=stiller["Heading1"],
                fontSize=14,
                leading=18,
                alignment=1,  # orta
                spaceAfter=4,
            )
            kucuk_stili = ParagraphStyle(
                "Kucuk",
                parent=stiller["Normal"],
                fontSize=8,
                leading=10,
            )
            ozet_bold = ParagraphStyle(
                "OzetBold",
                parent=stiller["Normal"],
                fontSize=9,
                leading=12,
                fontName=_PDF_FONT_BOLD,
            )

            tarih_str = datetime.now().strftime("%d.%m.%Y")
            hikaye = []

            # Başlık
            hikaye.append(Paragraph("BİRİM FİYAT ANALİZ CETVELİ", baslik_stili))
            hikaye.append(HRFlowable(width="100%", thickness=1, color=colors.black))
            hikaye.append(Spacer(1, 0.3 * cm))

            # Bilgi satırı
            bilgi_data = [
                [
                    Paragraph("<b>Poz No:</b> " + sonuc["poz_kodu"], kucuk_stili),
                    Paragraph("<b>Tanım:</b> " + (sonuc["poz_tanimi"] or ""), kucuk_stili),
                    Paragraph("<b>Birim:</b> " + (sonuc["birim"] or ""), kucuk_stili),
                    Paragraph("<b>Tarih:</b> " + tarih_str, kucuk_stili),
                ]
            ]
            bilgi_tablo = Table(bilgi_data, colWidths=[genislik * 0.15, genislik * 0.50,
                                                       genislik * 0.15, genislik * 0.20])
            bilgi_tablo.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F0F0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            hikaye.append(bilgi_tablo)
            hikaye.append(Spacer(1, 0.3 * cm))

            # Bileşen tablosu
            sutun_genislikleri = [
                genislik * 0.05,   # Sıra
                genislik * 0.10,   # Tür
                genislik * 0.42,   # Açıklama
                genislik * 0.07,   # Birim
                genislik * 0.10,   # Miktar
                genislik * 0.13,   # Birim Fiyatı
                genislik * 0.13,   # Tutarı
            ]
            tablo_data = [[
                Paragraph("<b>Sıra</b>", kucuk_stili),
                Paragraph("<b>Tür</b>", kucuk_stili),
                Paragraph("<b>Açıklama</b>", kucuk_stili),
                Paragraph("<b>Birim</b>", kucuk_stili),
                Paragraph("<b>Miktar</b>", kucuk_stili),
                Paragraph("<b>Birim Fiyatı (TL)</b>", kucuk_stili),
                Paragraph("<b>Tutarı (TL)</b>", kucuk_stili),
            ]]

            tablo_stili_komutlar = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), _PDF_FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ]

            for b in sonuc["bileseler"]:
                tur = b.get("tur", "malzeme")
                r, g, bl = _TUR_RENKLERI.get(tur, (1, 1, 1))
                tur_etiketi = _TUR_ETIKETLERI.get(tur, tur.capitalize())
                satir_idx = len(tablo_data)
                tablo_data.append([
                    str(b["sira"]),
                    tur_etiketi,
                    Paragraph(b["aciklama"], kucuk_stili),
                    b["birim"] or "",
                    "{:.4f}".format(b["miktar"]),
                    "{:,.2f}".format(b["birim_fiyat"]),
                    "{:,.2f}".format(b["tutar"]),
                ])
                tablo_stili_komutlar.append(
                    ("BACKGROUND", (0, satir_idx), (-1, satir_idx), colors.Color(r, g, bl))
                )

            bilesen_tablo = Table(tablo_data, colWidths=sutun_genislikleri)
            bilesen_tablo.setStyle(TableStyle(tablo_stili_komutlar))
            hikaye.append(bilesen_tablo)
            hikaye.append(Spacer(1, 0.4 * cm))

            # Özet tablo
            ozet_data = [
                ["Malzeme Toplamı", "{:,.2f} TL".format(sonuc["malzeme_toplam"])],
                ["İşçilik Toplamı", "{:,.2f} TL".format(sonuc["iscilik_toplam"])],
                ["Makine Toplamı",  "{:,.2f} TL".format(sonuc["makine_toplam"])],
                ["Ara Toplam",      "{:,.2f} TL".format(sonuc["ara_toplam"])],
                ["%15 Genel Gider", "{:,.2f} TL".format(sonuc["genel_gider"])],
                ["%10 Kar ve Risk", "{:,.2f} TL".format(sonuc["kar_risk"])],
                ["BİRİM FİYAT",    "{:,.2f} TL".format(sonuc["birim_fiyat"])],
            ]
            ozet_tablo = Table(
                ozet_data,
                colWidths=[genislik * 0.25, genislik * 0.20],
                hAlign="RIGHT",
            )
            ozet_stili_komutlar = [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("BACKGROUND", (0, 0), (-1, 2), colors.HexColor("#EBF5FB")),
                ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#D5D8DC")),
                ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#EBF5FB")),
                ("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#EBF5FB")),
                ("BACKGROUND", (0, 6), (-1, 6), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 6), (-1, 6), colors.white),
                ("FONTNAME", (0, 6), (-1, 6), _PDF_FONT_BOLD),
                ("FONTSIZE", (0, 6), (-1, 6), 11),
            ]
            ozet_tablo.setStyle(TableStyle(ozet_stili_komutlar))
            hikaye.append(ozet_tablo)
            hikaye.append(Spacer(1, 1.0 * cm))

            # İmza satırı
            imza_data = [[
                Paragraph("<b>Hazırlayanın İmzası</b><br/><br/><br/>__________________", kucuk_stili),
                Paragraph("<b>Teknik Şef İmzası</b><br/><br/><br/>__________________", kucuk_stili),
                Paragraph("<b>İdare Amiri İmzası</b><br/><br/><br/>__________________", kucuk_stili),
            ]]
            imza_tablo = Table(
                imza_data,
                colWidths=[genislik / 3] * 3,
            )
            imza_tablo.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            hikaye.append(imza_tablo)

            doc.build(hikaye)
            logger.info("PDF oluşturuldu: %s", dosya_yolu)
            return True

        except Exception as e:
            logger.error("pdf_analiz_belgesi_uret hatası (%s): %s", poz_kodu, e)
            return False

    # -----------------------------------------------------------------------
    # 9. csv_iceri_aktar
    # -----------------------------------------------------------------------
    def csv_iceri_aktar(self, dosya: str) -> int:
        """
        CSV'den analiz bileşenlerini içe aktarır.
        Header: poz_kodu,tur,aciklama,birim,miktar,birim_fiyat
        Döndürür: aktarılan satır sayısı.
        """
        aktarilan = 0
        try:
            with open(dosya, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                # Poz koduna göre grupla
                gruplar: dict = {}
                for satir in reader:
                    poz = satir.get("poz_kodu", "").strip()
                    if not poz:
                        continue
                    if poz not in gruplar:
                        gruplar[poz] = []
                    gruplar[poz].append(satir)

            for poz_kodu, satirlar in gruplar.items():
                # Varolan analizi al (tanim ve birim için)
                mevcut = self.analiz_getir(poz_kodu)
                tanim = mevcut["poz_tanimi"] if mevcut else ""
                birim = mevcut["birim"] if mevcut else ""
                bileseler = []
                for s in satirlar:
                    try:
                        miktar = float(s.get("miktar", 0))
                        birim_fiyat = float(s.get("birim_fiyat", 0))
                    except ValueError:
                        miktar = 0.0
                        birim_fiyat = 0.0
                    bileseler.append({
                        "tur": s.get("tur", "malzeme").strip(),
                        "aciklama": s.get("aciklama", "").strip(),
                        "birim": s.get("birim", "").strip(),
                        "miktar": miktar,
                        "birim_fiyat": birim_fiyat,
                    })
                result = self.analiz_kaydet(poz_kodu, tanim, birim, bileseler)
                if result != -1:
                    aktarilan += len(bileseler)

            logger.info("csv_iceri_aktar: %d satır aktarıldı (%s).", aktarilan, dosya)
        except Exception as e:
            logger.error("csv_iceri_aktar hatası (%s): %s", dosya, e)
        return aktarilan

    # -----------------------------------------------------------------------
    # 10. csv_disari_aktar
    # -----------------------------------------------------------------------
    def csv_disari_aktar(self, poz_kodu: str, dosya: str) -> bool:
        """
        Analizi CSV olarak dışa aktarır.
        Header: poz_kodu,tur,aciklama,birim,miktar,birim_fiyat,tutar
        """
        try:
            analiz = self.analiz_getir(poz_kodu)
            if analiz is None:
                logger.warning("csv_disari_aktar: '%s' bulunamadı.", poz_kodu)
                return False

            with open(dosya, "w", newline="", encoding="utf-8-sig") as f:
                yazici = csv.writer(f)
                yazici.writerow(["poz_kodu", "tur", "aciklama", "birim",
                                 "miktar", "birim_fiyat", "tutar"])
                for b in analiz["bileseler"]:
                    tutar = b["miktar"] * b["birim_fiyat"]
                    yazici.writerow([
                        poz_kodu,
                        b["tur"],
                        b["aciklama"],
                        b["birim"],
                        b["miktar"],
                        b["birim_fiyat"],
                        round(tutar, 4),
                    ])

            logger.info("csv_disari_aktar: '%s' → %s", poz_kodu, dosya)
            return True
        except Exception as e:
            logger.error("csv_disari_aktar hatası (%s): %s", poz_kodu, e)
            return False
