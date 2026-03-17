"""
Business Intelligence (BI) Engine
Proje verilerini analiz eder, KPI'lar hesaplar ve görselleştirme verileri hazırlar
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
from collections import defaultdict

from app.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class BIEngine:
    """
    Business Intelligence motoru.

    Proje verilerini analiz eder, KPI hesaplar, trend analizi yapar.
    """

    def __init__(self, db: DatabaseManager):
        """
        BI Engine başlat.

        Args:
            db: Veritabanı yöneticisi
        """
        self.db = db

    def get_dashboard_kpis(self, proje_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Ana dashboard KPI'larını hesapla.

        Args:
            proje_id: Belirli bir proje için (None ise tüm projeler)

        Returns:
            KPI verileri
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Toplam proje sayısı
                if proje_id:
                    cursor.execute("SELECT COUNT(*) as count FROM projects WHERE id = ?", (proje_id,))
                else:
                    cursor.execute("SELECT COUNT(*) as count FROM projects WHERE durum = 'aktif'")
                toplam_proje = cursor.fetchone()['count']

                # Toplam maliyet
                if proje_id:
                    cursor.execute("""
                        SELECT SUM(miktar * birim_fiyat) as toplam
                        FROM metraj_kalemleri
                        WHERE proje_id = ?
                    """, (proje_id,))
                else:
                    cursor.execute("""
                        SELECT SUM(mk.miktar * mk.birim_fiyat) as toplam
                        FROM metraj_kalemleri mk
                        JOIN projects p ON mk.proje_id = p.id
                        WHERE p.durum = 'aktif'
                    """)
                toplam_maliyet = cursor.fetchone()['toplam'] or 0

                # Toplam kalem sayısı
                if proje_id:
                    cursor.execute("SELECT COUNT(*) as count FROM metraj_kalemleri WHERE proje_id = ?", (proje_id,))
                else:
                    cursor.execute("""
                        SELECT COUNT(*) as count
                        FROM metraj_kalemleri mk
                        JOIN projects p ON mk.proje_id = p.id
                        WHERE p.durum = 'aktif'
                    """)
                toplam_kalem = cursor.fetchone()['count']

                # En pahalı proje
                if not proje_id:
                    cursor.execute("""
                        SELECT p.ad, SUM(mk.miktar * mk.birim_fiyat) as toplam
                        FROM projects p
                        LEFT JOIN metraj_kalemleri mk ON p.id = mk.proje_id
                        WHERE p.durum = 'aktif'
                        GROUP BY p.id
                        ORDER BY toplam DESC
                        LIMIT 1
                    """)
                    en_pahali_proje = cursor.fetchone()
                else:
                    en_pahali_proje = None

                # Ortalama proje maliyeti
                if not proje_id:
                    ortalama_maliyet = toplam_maliyet / toplam_proje if toplam_proje > 0 else 0
                else:
                    ortalama_maliyet = toplam_maliyet

                # Taşeron sayısı (unique)
                if proje_id:
                    cursor.execute("""
                        SELECT COUNT(DISTINCT firma_adi) as count
                        FROM taseron_teklifleri
                        WHERE proje_id = ?
                    """, (proje_id,))
                else:
                    cursor.execute("""
                        SELECT COUNT(DISTINCT firma_adi) as count
                        FROM taseron_teklifleri
                    """)
                taseron_sayisi = cursor.fetchone()['count']

                return {
                    'toplam_proje': toplam_proje,
                    'toplam_maliyet': round(toplam_maliyet, 2),
                    'toplam_kalem': toplam_kalem,
                    'ortalama_maliyet': round(ortalama_maliyet, 2),
                    'taseron_sayisi': taseron_sayisi,
                    'en_pahali_proje': en_pahali_proje['ad'] if en_pahali_proje else 'N/A',
                    'en_pahali_proje_maliyet': round(en_pahali_proje['toplam'], 2) if en_pahali_proje and en_pahali_proje['toplam'] else 0
                }

        except Exception as e:
            logger.error(f"KPI hesaplama hatası: {e}")
            return {
                'toplam_proje': 0,
                'toplam_maliyet': 0,
                'toplam_kalem': 0,
                'ortalama_maliyet': 0,
                'taseron_sayisi': 0,
                'en_pahali_proje': 'N/A',
                'en_pahali_proje_maliyet': 0
            }

    def get_kategori_dagilimi(self, proje_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Kategori bazında maliyet dağılımı.

        Args:
            proje_id: Belirli bir proje için (None ise tüm projeler)

        Returns:
            Kategori dağılım listesi
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                if proje_id:
                    cursor.execute("""
                        SELECT mk.kategori, SUM(mk.miktar * mk.birim_fiyat) as toplam,
                        COUNT(*) as kalem_sayisi
                        FROM metraj_kalemleri mk
                        WHERE mk.proje_id = ? AND mk.kategori IS NOT NULL
                        GROUP BY mk.kategori
                        ORDER BY toplam DESC
                    """, (proje_id,))
                else:
                    cursor.execute("""
                        SELECT mk.kategori, SUM(mk.miktar * mk.birim_fiyat) as toplam,
                        COUNT(*) as kalem_sayisi
                        FROM metraj_kalemleri mk
                        JOIN projects p ON mk.proje_id = p.id
                        WHERE p.durum = 'aktif' AND mk.kategori IS NOT NULL
                        GROUP BY mk.kategori
                        ORDER BY toplam DESC
                    """)

                rows = cursor.fetchall()
                toplam_maliyet = sum(row['toplam'] for row in rows if row['toplam'])

                return [{
                    'kategori': row['kategori'] or 'Kategorisiz',
                    'maliyet': round(row['toplam'] or 0, 2),
                    'kalem_sayisi': row['kalem_sayisi'],
                    'oran': round((row['toplam'] / toplam_maliyet * 100) if toplam_maliyet > 0 else 0, 2)
                } for row in rows]

        except Exception as e:
            logger.error(f"Kategori dağılımı hatası: {e}")
            return []

    def get_top_kalemler(self, proje_id: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        En pahalı kalemleri getir.

        Args:
            proje_id: Belirli bir proje için
            limit: Kaç tane gösterilecek

        Returns:
            En pahalı kalemler listesi
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                if proje_id:
                    cursor.execute("""
                        SELECT poz_no, tanim, birim, miktar, birim_fiyat,
                        (miktar * birim_fiyat) as toplam
                        FROM metraj_kalemleri
                        WHERE proje_id = ?
                        ORDER BY toplam DESC
                        LIMIT ?
                    """, (proje_id, limit))
                else:
                    cursor.execute("""
                        SELECT mk.poz_no, mk.tanim, mk.birim, mk.miktar, mk.birim_fiyat,
                        (mk.miktar * mk.birim_fiyat) as toplam, p.ad as proje_adi
                        FROM metraj_kalemleri mk
                        JOIN projects p ON mk.proje_id = p.id
                        WHERE p.durum = 'aktif'
                        ORDER BY toplam DESC
                        LIMIT ?
                    """, (limit,))

                rows = cursor.fetchall()

                return [{
                    'poz_no': row['poz_no'] or 'N/A',
                    'tanim': row['tanim'] or '',
                    'miktar': row['miktar'] or 0,
                    'birim': row['birim'] or '',
                    'birim_fiyat': round(row['birim_fiyat'] or 0, 2),
                    'toplam': round(row['toplam'] or 0, 2),
                    'proje_adi': row['proje_adi'] if 'proje_adi' in row.keys() else ''
                } for row in rows]

        except Exception as e:
            logger.error(f"Top kalemler hatası: {e}")
            return []

    def get_aylik_trend(self, ay_sayisi: int = 12, proje_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Aylık maliyet trendi.

        Args:
            ay_sayisi: Kaç aylık veri

        Returns:
            Aylık trend verileri
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                if proje_id:
                    cursor.execute("""
                        SELECT
                        strftime('%Y-%m', mk.olusturma_tarihi) as ay,
                        COUNT(DISTINCT mk.id) as proje_sayisi,
                        SUM(mk.miktar * mk.birim_fiyat) as toplam_maliyet
                        FROM metraj_kalemleri mk
                        WHERE mk.proje_id = ?
                        AND mk.olusturma_tarihi >= date('now', '-' || ? || ' months')
                        GROUP BY ay
                        ORDER BY ay DESC
                    """, (proje_id, ay_sayisi))
                else:
                    cursor.execute("""
                        SELECT
                        strftime('%Y-%m', p.olusturma_tarihi) as ay,
                        COUNT(DISTINCT p.id) as proje_sayisi,
                        SUM(mk.miktar * mk.birim_fiyat) as toplam_maliyet
                        FROM projects p
                        LEFT JOIN metraj_kalemleri mk ON p.id = mk.proje_id
                        WHERE p.olusturma_tarihi >= date('now', '-' || ? || ' months')
                        GROUP BY ay
                        ORDER BY ay DESC
                    """, (ay_sayisi,))

                rows = cursor.fetchall()

                return [{
                    'ay': row['ay'],
                    'proje_sayisi': row['proje_sayisi'],
                    'toplam_maliyet': round(row['toplam_maliyet'] or 0, 2)
                } for row in reversed(list(rows))]

        except Exception as e:
            logger.error(f"Aylık trend hatası: {e}")
            return []

    def get_taseron_karsilastirma(self, proje_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Taşeron teklif karşılaştırması.

        Args:
            proje_id: Belirli bir proje için

        Returns:
            Taşeron karşılaştırma verileri
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                if proje_id:
                    cursor.execute("""
                        SELECT firma_adi, AVG(toplam) as ortalama_fiyat,
                        COUNT(*) as teklif_sayisi
                        FROM taseron_teklifleri
                        WHERE proje_id = ?
                        GROUP BY firma_adi
                        ORDER BY ortalama_fiyat ASC
                    """, (proje_id,))
                else:
                    cursor.execute("""
                        SELECT firma_adi, AVG(toplam) as ortalama_fiyat,
                        COUNT(*) as teklif_sayisi
                        FROM taseron_teklifleri
                        GROUP BY firma_adi
                        ORDER BY ortalama_fiyat ASC
                    """)

                rows = cursor.fetchall()

                return [{
                    'firma': row['firma_adi'],
                    'ortalama_fiyat': round(row['ortalama_fiyat'], 2),
                    'teklif_sayisi': row['teklif_sayisi']
                } for row in rows]

        except Exception as e:
            logger.error(f"Taşeron karşılaştırma hatası: {e}")
            return []

    def get_kar_analizi(self, proje_id: int, hedef_kar_orani: float = 15.0) -> Dict[str, Any]:
        """
        Kar/Zarar analizi (basitleştirilmiş).

        Args:
            proje_id: Proje ID
            hedef_kar_orani: Hedef kar oranı (%)

        Returns:
            Kar analizi verileri
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT SUM(miktar * birim_fiyat) as toplam
                    FROM metraj_kalemleri
                    WHERE proje_id = ?
                """, (proje_id,))
                maliyet = cursor.fetchone()['toplam'] or 0

                cursor.execute("""
                    SELECT MIN(fiyat) as min_fiyat
                    FROM taseron_teklifleri
                    WHERE proje_id = ?
                """, (proje_id,))
                taseron_min = cursor.fetchone()['min_fiyat'] or 0

                hedef_satis = maliyet * (1 + hedef_kar_orani / 100)
                kar = hedef_satis - maliyet
                kar_orani = (kar / maliyet * 100) if maliyet > 0 else 0

                return {
                    'maliyet': round(maliyet, 2),
                    'hedef_satis': round(hedef_satis, 2),
                    'kar': round(kar, 2),
                    'kar_orani': round(kar_orani, 2),
                    'hedef_kar_orani': hedef_kar_orani
                }

        except Exception as e:
            logger.error(f"Kar analizi hatası: {e}")
            return {
                'maliyet': 0,
                'hedef_satis': 0,
                'kar': 0,
                'kar_orani': 0,
                'hedef_kar_orani': hedef_kar_orani
            }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db = DatabaseManager()
    engine = BIEngine(db)
    print("\n=== DASHBOARD KPI'LAR ===")
    kpis = engine.get_dashboard_kpis()
    for key, value in kpis.items():
        print(f"{key}: {value}")
