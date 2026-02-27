"""
QR Kod Bazlı Hakediş Sistemi
Her iş kalemine QR kod oluşturur ve mobil ile gerçekleşme girişi yapılmasını sağlar
"""

import qrcode
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Any, Optional
import json
import logging
from pathlib import Path

from app.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class QRHakedisEngine:
 """
 QR kod bazlı hakediş motoru.

 Her iş kalemi için QR kod oluşturur, mobil okuma simülasyonu yapar.
 """

 def __init__(self, db: DatabaseManager):
 """
 QR Hakediş Engine başlat.

 Args:
 db: Veritabanı yöneticisi
 """
 self.db = db
 self.qr_output_dir = Path("qr_codes")
 self.qr_output_dir.mkdir(exist_ok=True)

 def create_qr_code(
 self,
 proje_id: int,
 metraj_kalem_id: int,
 size: int = 10,
 border: int = 2
 ) -> bytes:
 """
 Metraj kalemi için QR kod oluştur.

 Args:
 proje_id: Proje ID
 metraj_kalem_id: Metraj kalem ID
 size: QR kod boyutu
 border: Kenar boşluğu

 Returns:
 QR kod image bytes
 """
 try:
 # QR kod verisi (JSON formatında)
 qr_data = {
 'proje_id': proje_id,
 'kalem_id': metraj_kalem_id,
 'timestamp': datetime.now().isoformat(),
 'type': 'hakedis'
 }

 # JSON string'e çevir
 qr_string = json.dumps(qr_data)

 # QR kod oluştur
 qr = qrcode.QRCode(
 version=1,
 error_correction=qrcode.constants.ERROR_CORRECT_L,
 box_size=size,
 border=border,
 )

 qr.add_data(qr_string)
 qr.make(fit=True)

 # Image oluştur
 img = qr.make_image(fill_color="black", back_color="white")

 # Bytes'a çevir
 buffer = BytesIO()
 img.save(buffer, format='PNG')
 buffer.seek(0)

 return buffer.getvalue()

 except Exception as e:
 logger.error(f"QR kod oluşturma hatası: {e}")
 return b''

 def save_qr_code(
 self,
 proje_id: int,
 metraj_kalem_id: int,
 filename: Optional[str] = None
 ) -> str:
 """
 QR kodu dosyaya kaydet.

 Args:
 proje_id: Proje ID
 metraj_kalem_id: Metraj kalem ID
 filename: Dosya adı (opsiyonel)

 Returns:
 Dosya yolu
 """
 try:
 qr_bytes = self.create_qr_code(proje_id, metraj_kalem_id)

 if not filename:
 filename = f"qr_proje{proje_id}_kalem{metraj_kalem_id}.png"

 filepath = self.qr_output_dir / filename

 with open(filepath, 'wb') as f:
 f.write(qr_bytes)

 logger.info(f"QR kod kaydedildi: {filepath}")
 return str(filepath)

 except Exception as e:
 logger.error(f"QR kod kaydetme hatası: {e}")
 return ""

 def create_hakedis_gercekeleme(
 self,
 proje_id: int,
 metraj_kalem_id: int,
 gerceklesen_miktar: float,
 aciklama: str = "",
 foto_path: Optional[str] = None,
 konum: Optional[str] = None
 ) -> int:
 """
 Hakediş gerçekleşme kaydı oluştur.

 Args:
 proje_id: Proje ID
 metraj_kalem_id: Metraj kalem ID
 gerceklesen_miktar: Gerçekleşen miktar
 aciklama: Açıklama
 foto_path: Fotoğraf yolu (opsiyonel)
 konum: GPS konumu (opsiyonel)

 Returns:
 Oluşturulan kayıt ID
 """
 try:
 with self.db.get_connection() as conn:
 cursor = conn.cursor()

 cursor.execute("""
 INSERT INTO hakedis_gerceklesme
 (proje_id, metraj_kalem_id, gerceklesen_miktar, aciklama,
 foto_path, konum, gerceklesme_tarihi, olusturma_tarihi)
 VALUES (?, ?, ?, ?, ?, ?, ?, ?)
 """, (
 proje_id,
 metraj_kalem_id,
 gerceklesen_miktar,
 aciklama,
 foto_path,
 konum,
 datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
 datetime.now().strftime("%Y-%m-%d %H:%M:%S")
 ))

 return cursor.lastrowid

 except Exception as e:
 logger.error(f"Hakediş gerçekleşme kaydetme hatası: {e}")
 return 0

 def get_hakedis_durumu(
 self,
 proje_id: int,
 metraj_kalem_id: Optional[int] = None
 ) -> Dict[str, Any]:
 """
 Hakediş durumunu getir.

 Args:
 proje_id: Proje ID
 metraj_kalem_id: Metraj kalem ID (opsiyonel, None ise tüm kalemler)

 Returns:
 Hakediş durum bilgisi
 """
 try:
 with self.db.get_connection() as conn:
 cursor = conn.cursor()

 if metraj_kalem_id:
 # Belirli bir kalem için
 cursor.execute("""
 SELECT mk.id, mk.poz_no, mk.tanim, mk.miktar, mk.birim,
 mk.birim_fiyat, (mk.miktar * mk.birim_fiyat) as toplam_tutar,
 COALESCE(SUM(hg.gerceklesen_miktar), 0) as gerceklesen_toplam
 FROM metraj_kalemleri mk
 LEFT JOIN hakedis_gerceklesme hg ON mk.id = hg.metraj_kalem_id
 WHERE mk.proje_id = ? AND mk.id = ?
 GROUP BY mk.id
 """, (proje_id, metraj_kalem_id))

 row = cursor.fetchone()

 if not row:
 return {}

 gerceklesme_orani = (row['gerceklesen_toplam'] / row['miktar'] * 100) if row['miktar'] > 0 else 0
 gerceklesen_tutar = row['gerceklesen_toplam'] * row['birim_fiyat']

 return {
 'kalem_id': row['id'],
 'poz_no': row['poz_no'],
 'tanim': row['tanim'],
 'planlanan_miktar': row['miktar'],
 'gerceklesen_miktar': row['gerceklesen_toplam'],
 'birim': row['birim'],
 'birim_fiyat': row['birim_fiyat'],
 'toplam_tutar': round(row['toplam_tutar'], 2),
 'gerceklesen_tutar': round(gerceklesen_tutar, 2),
 'gerceklesme_orani': round(gerceklesme_orani, 2),
 'durum': 'Tamamlandı' if gerceklesme_orani >= 100 else 'Devam Ediyor'
 }
 else:
 # Tüm kalemler için özet
 cursor.execute("""
 SELECT
 COUNT(DISTINCT mk.id) as toplam_kalem,
 SUM(mk.miktar * mk.birim_fiyat) as toplam_tutar,
 SUM(COALESCE(hg.gerceklesen_miktar, 0) * mk.birim_fiyat) as gerceklesen_tutar
 FROM metraj_kalemleri mk
 LEFT JOIN hakedis_gerceklesme hg ON mk.id = hg.metraj_kalem_id
 WHERE mk.proje_id = ?
 """, (proje_id,))

 row = cursor.fetchone()

 gerceklesme_orani = (row['gerceklesen_tutar'] / row['toplam_tutar'] * 100) if row['toplam_tutar'] > 0 else 0

 return {
 'toplam_kalem': row['toplam_kalem'],
 'toplam_tutar': round(row['toplam_tutar'] or 0, 2),
 'gerceklesen_tutar': round(row['gerceklesen_tutar'] or 0, 2),
 'kalan_tutar': round((row['toplam_tutar'] or 0) - (row['gerceklesen_tutar'] or 0), 2),
 'gerceklesme_orani': round(gerceklesme_orani, 2)
 }

 except Exception as e:
 logger.error(f"Hakediş durumu getirme hatası: {e}")
 return {}

 def get_qr_kalemler(self, proje_id: int) -> List[Dict[str, Any]]:
 """
 Proje için QR kodlu kalemleri listele.

 Args:
 proje_id: Proje ID

 Returns:
 QR kodlu kalemler listesi
 """
 try:
 with self.db.get_connection() as conn:
 cursor = conn.cursor()

 cursor.execute("""
 SELECT mk.id, mk.poz_no, mk.tanim, mk.miktar, mk.birim,
 mk.birim_fiyat, (mk.miktar * mk.birim_fiyat) as toplam,
 COALESCE(SUM(hg.gerceklesen_miktar), 0) as gerceklesen
 FROM metraj_kalemleri mk
 LEFT JOIN hakedis_gerceklesme hg ON mk.id = hg.metraj_kalem_id
 WHERE mk.proje_id = ?
 GROUP BY mk.id
 ORDER BY mk.id
 """, (proje_id,))

 rows = cursor.fetchall()

 return [{
 'id': row['id'],
 'poz_no': row['poz_no'] or 'N/A',
 'tanim': row['tanim'],
 'miktar': row['miktar'],
 'gerceklesen': row['gerceklesen'],
 'birim': row['birim'],
 'birim_fiyat': round(row['birim_fiyat'], 2),
 'toplam': round(row['toplam'], 2),
 'gerceklesme_orani': round((row['gerceklesen'] / row['miktar'] * 100) if row['miktar'] > 0 else 0, 2)
 } for row in rows]

 except Exception as e:
 logger.error(f"QR kalemler listesi hatası: {e}")
 return []

 def simulate_qr_scan(self, qr_data_json: str) -> Dict[str, Any]:
 """
 QR kod okuma simülasyonu (mobil uygulama simülasyonu).

 Args:
 qr_data_json: QR kod verisi (JSON string)

 Returns:
 Okunan veri
 """
 try:
 data = json.loads(qr_data_json)

 # Kalem bilgisini getir
 with self.db.get_connection() as conn:
 cursor = conn.cursor()

 cursor.execute("""
 SELECT mk.*, p.ad as proje_adi
 FROM metraj_kalemleri mk
 JOIN projects p ON mk.proje_id = p.id
 WHERE mk.proje_id = ? AND mk.id = ?
 """, (data['proje_id'], data['kalem_id']))

 row = cursor.fetchone()

 if not row:
 return {'hata': 'Kalem bulunamadı'}

 return {
 'basarili': True,
 'proje_adi': row['proje_adi'],
 'poz_no': row['poz_no'],
 'tanim': row['tanim'],
 'miktar': row['miktar'],
 'birim': row['birim'],
 'kalem_id': data['kalem_id'],
 'proje_id': data['proje_id']
 }

 except Exception as e:
 logger.error(f"QR okuma simülasyonu hatası: {e}")
 return {'hata': str(e)}


# Test kodu
if __name__ == "__main__":
 logging.basicConfig(level=logging.INFO)

 from app.core.database import DatabaseManager

 db = DatabaseManager()
 engine = QRHakedisEngine(db)

 print("\n=== QR KOD OLUŞTURMA TESTİ ===")
 qr_bytes = engine.create_qr_code(proje_id=1, metraj_kalem_id=1)
 print(f"QR kod oluşturuldu: {len(qr_bytes)} bytes")

 print("\n=== QR KOD KAYDETME ===")
 filepath = engine.save_qr_code(proje_id=1, metraj_kalem_id=1)
 print(f"QR kod kaydedildi: {filepath}")
