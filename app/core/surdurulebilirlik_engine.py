"""
Çevre ve Sürdürülebilirlik Modülü
Karbon ayak izi, enerji verimliliği, geri dönüşüm ve yeşil bina sertifikası hesaplamaları
"""

import sqlite3
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class SurdurulebilirlikEngine:
 """
 Sürdürülebilirlik hesaplamaları ve çevre analizi sınıfı.

 - Karbon ayak izi hesaplama
 - Enerji verimliliği skoru
 - Geri dönüştürülebilir malzeme oranı
 - LEED/BREEAM sertifika hazırlık
 - Atık yönetimi
 """

 # Karbon emisyon faktörleri (kg CO2/birim)
 KARBON_FAKTORLERI = {
 # İnşaat Malzemeleri (kg CO2/ton veya kg CO2/m³)
 'beton': 135.0, # kg CO2/m³
 'çimento': 900.0, # kg CO2/ton
 'çelik': 1850.0, # kg CO2/ton
 'demir': 1900.0, # kg CO2/ton
 'alüminyum': 11500.0, # kg CO2/ton
 'cam': 850.0, # kg CO2/ton
 'tuğla': 240.0, # kg CO2/ton
 'ahşap': -480.0, # kg CO2/ton (negatif = karbon tutma)
 'yalıtım_taşyünü': 380.0, # kg CO2/ton
 'yalıtım_eps': 3400.0, # kg CO2/ton
 'pvc': 2400.0, # kg CO2/ton
 'asfalt': 45.0, # kg CO2/ton
 'kireç': 1100.0, # kg CO2/ton
 'mermer': 95.0, # kg CO2/m²
 'seramik': 7.5, # kg CO2/m²
 'boya': 2.9, # kg CO2/kg
 'default': 100.0 # Genel varsayılan
 }

 # Enerji tüketim katsayıları (kWh/m²/yıl)
 ENERJI_SINIF_LIMITLERI = {
 'A+': (0, 50),
 'A': (50, 100),
 'B': (100, 150),
 'C': (150, 200),
 'D': (200, 250),
 'E': (250, 300),
 'F': (300, 350),
 'G': (350, float('inf'))
 }

 # LEED Puan Kriterleri (Basitleştirilmiş)
 LEED_KRITERLER = {
 'enerji_tasarrufu': {
 'max_puan': 33,
 'kriterler': [
 {'baslik': 'Enerji Verimliliği', 'puan': 18},
 {'baslik': 'Yenilenebilir Enerji', 'puan': 15}
 ]
 },
 'su_verimliligi': {
 'max_puan': 12,
 'kriterler': [
 {'baslik': 'Su Kullanım Azaltma', 'puan': 8},
 {'baslik': 'Yağmur Suyu Toplama', 'puan': 4}
 ]
 },
 'malzeme_kaynak': {
 'max_puan': 13,
 'kriterler': [
 {'baslik': 'Geri Dönüştürülmüş Malzeme', 'puan': 5},
 {'baslik': 'Yerel Malzeme', 'puan': 4},
 {'baslik': 'Düşük Emisyon Malzeme', 'puan': 4}
 ]
 },
 'ic_mekan_kalitesi': {
 'max_puan': 16,
 'kriterler': [
 {'baslik': 'Hava Kalitesi', 'puan': 8},
 {'baslik': 'Doğal Aydınlatma', 'puan': 8}
 ]
 },
 'yenilikcilik': {
 'max_puan': 6,
 'kriterler': [
 {'baslik': 'İnovatif Tasarım', 'puan': 5},
 {'baslik': 'LEED Uzmanı', 'puan': 1}
 ]
 }
 }

 # Atık Kategorileri
 ATIK_KATEGORILERI = {
 'beton_moloz': {'geri_donusturulur': True, 'tehlikeli': False},
 'ahsap': {'geri_donusturulur': True, 'tehlikeli': False},
 'metal': {'geri_donusturulur': True, 'tehlikeli': False},
 'plastik': {'geri_donusturulur': True, 'tehlikeli': False},
 'cam': {'geri_donusturulur': True, 'tehlikeli': False},
 'yalitim': {'geri_donusturulur': False, 'tehlikeli': False},
 'boya_kimyasal': {'geri_donusturulur': False, 'tehlikeli': True},
 'asbest': {'geri_donusturulur': False, 'tehlikeli': True},
 'karisik': {'geri_donusturulur': False, 'tehlikeli': False}
 }

 def __init__(self, db_manager=None):
 """
 Sürdürülebilirlik motoru başlat.

 Args:
 db_manager: DatabaseManager instance (opsiyonel)
 """
 self.db = db_manager

 def hesapla_karbon_ayakizi(
 self,
 malzeme_adi: str,
 miktar: float,
 birim: str = 'ton'
 ) -> Dict[str, Any]:
 """
 Malzeme bazında karbon ayak izi hesaplar.

 Args:
 malzeme_adi: Malzeme adı
 miktar: Miktar
 birim: Birim (ton, m³, kg, vb.)

 Returns:
 Karbon ayak izi sonucu
 """
 # Malzeme adını normalize et
 malzeme_key = self._normalize_malzeme(malzeme_adi)

 # Karbon faktörünü bul
 karbon_faktor = self.KARBON_FAKTORLERI.get(
 malzeme_key,
 self.KARBON_FAKTORLERI['default']
 )

 # Birim dönüşümü (kg'a çevir)
 miktar_kg = self._birim_donustur(miktar, birim)

 # Karbon emisyonu hesapla (kg CO2)
 if birim == 'm³':
 # m³ için direkt faktör kullan
 karbon_emisyon = miktar * karbon_faktor
 else:
 # Ton/kg için
 karbon_emisyon = (miktar_kg / 1000) * karbon_faktor

 # Ağaç eşdeğeri (1 ağaç/yıl ≈ 20 kg CO2)
 agac_esdegeri = abs(karbon_emisyon) / 20

 return {
 'malzeme': malzeme_adi,
 'miktar': miktar,
 'birim': birim,
 'karbon_faktor': karbon_faktor,
 'karbon_emisyon_kg': round(karbon_emisyon, 2),
 'karbon_emisyon_ton': round(karbon_emisyon / 1000, 3),
 'agac_esdegeri': round(agac_esdegeri, 1),
 'karbon_pozitif': karbon_emisyon > 0
 }

 def hesapla_proje_karbon_ayakizi(self, proje_id: int) -> Dict[str, Any]:
 """
 Proje genelinde toplam karbon ayak izi hesaplar.

 Args:
 proje_id: Proje ID

 Returns:
 Proje karbon ayak izi özeti
 """
 if not self.db:
 return {'error': 'Veritabanı bağlantısı yok'}

 try:
 with self.db.get_connection() as conn:
 cursor = conn.cursor()

 # Projedeki tüm malzemeleri çek
 cursor.execute("""
 SELECT
 mk.poz_no,
 mk.tanim,
 mk.miktar,
 mk.birim,
 p.poz_no as poz_kodu,
 p.tanim as poz_tanim
 FROM metraj_kalemleri mk
 LEFT JOIN pozlar p ON mk.poz_no = p.poz_no
 WHERE mk.proje_id = ?
 """, (proje_id,))

 kalemler = cursor.fetchall()

 toplam_karbon = 0
 detay_liste = []
 kategori_dagilim = {}

 for kalem in kalemler:
 # Her kalem için karbon hesapla
 sonuc = self.hesapla_karbon_ayakizi(
 kalem['tanim'] or kalem['poz_tanim'] or 'Genel',
 kalem['miktar'],
 kalem['birim']
 )

 toplam_karbon += sonuc['karbon_emisyon_kg']

 detay_liste.append({
 'poz_no': kalem['poz_no'],
 'tanim': kalem['tanim'],
 'miktar': kalem['miktar'],
 'birim': kalem['birim'],
 'karbon_kg': sonuc['karbon_emisyon_kg']
 })

 # Kategori dağılımı
 kategori = self._get_malzeme_kategori(kalem['tanim'] or '')
 if kategori not in kategori_dagilim:
 kategori_dagilim[kategori] = 0
 kategori_dagilim[kategori] += sonuc['karbon_emisyon_kg']

 # Sıralama (en yüksek emisyon)
 detay_liste.sort(key=lambda x: abs(x['karbon_kg']), reverse=True)

 return {
 'proje_id': proje_id,
 'toplam_karbon_kg': round(toplam_karbon, 2),
 'toplam_karbon_ton': round(toplam_karbon / 1000, 3),
 'agac_esdegeri': round(abs(toplam_karbon) / 20, 1),
 'toplam_kalem': len(kalemler),
 'kategori_dagilim': kategori_dagilim,
 'en_yuksek_10': detay_liste[:10],
 'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
 }

 except Exception as e:
 logger.error(f"Proje karbon hesaplama hatası: {e}")
 return {'error': str(e)}

 def hesapla_enerji_sinifi(
 self,
 yillik_tuketim_kwh: float,
 toplam_alan_m2: float
 ) -> Dict[str, Any]:
 """
 Enerji verimliliği sınıfı hesaplar.

 Args:
 yillik_tuketim_kwh: Yıllık enerji tüketimi (kWh)
 toplam_alan_m2: Toplam bina alanı (m²)

 Returns:
 Enerji sınıfı ve detaylar
 """
 if toplam_alan_m2 <= 0:
 return {'error': 'Geçersiz alan değeri'}

 # Birim alan tüketimi
 birim_tuketim = yillik_tuketim_kwh / toplam_alan_m2

 # Sınıf belirle
 enerji_sinifi = 'G'
 for sinif, (min_val, max_val) in self.ENERJI_SINIF_LIMITLERI.items():
 if min_val <= birim_tuketim < max_val:
 enerji_sinifi = sinif
 break

 # Puan hesapla (A+ = 100, G = 0)
 sinif_sira = ['G', 'F', 'E', 'D', 'C', 'B', 'A', 'A+']
 puan = (sinif_sira.index(enerji_sinifi) / len(sinif_sira)) * 100

 # Yıllık maliyet tahmini (0.5 TL/kWh varsayımı)
 yillik_maliyet = yillik_tuketim_kwh * 0.5

 # CO2 emisyonu (Türkiye elektrik ağı: ~0.45 kg CO2/kWh)
 co2_emisyon = yillik_tuketim_kwh * 0.45

 return {
 'enerji_sinifi': enerji_sinifi,
 'puan': round(puan, 1),
 'birim_tuketim_kwh_m2': round(birim_tuketim, 2),
 'yillik_tuketim_kwh': yillik_tuketim_kwh,
 'toplam_alan_m2': toplam_alan_m2,
 'yillik_maliyet_tl': round(yillik_maliyet, 2),
 'co2_emisyon_kg': round(co2_emisyon, 2),
 'co2_emisyon_ton': round(co2_emisyon / 1000, 3)
 }

 def hesapla_geri_donusum_orani(
 self,
 toplam_atik_ton: float,
 geri_donusturulen_ton: float
 ) -> Dict[str, Any]:
 """
 Geri dönüşüm oranını hesaplar.

 Args:
 toplam_atik_ton: Toplam atık miktarı (ton)
 geri_donusturulen_ton: Geri dönüştürülen miktar (ton)

 Returns:
 Geri dönüşüm analizi
 """
 if toplam_atik_ton <= 0:
 return {'error': 'Geçersiz atık miktarı'}

 geri_donusum_orani = (geri_donusturulen_ton / toplam_atik_ton) * 100

 # Hedef: %70 geri dönüşüm
 hedef_oran = 70.0
 hedefe_gore_durum = geri_donusum_orani >= hedef_oran

 # Puan hesapla
 puan = min((geri_donusum_orani / hedef_oran) * 100, 100)

 return {
 'toplam_atik_ton': toplam_atik_ton,
 'geri_donusturulen_ton': geri_donusturulen_ton,
 'atilan_ton': round(toplam_atik_ton - geri_donusturulen_ton, 2),
 'geri_donusum_orani': round(geri_donusum_orani, 2),
 'hedef_oran': hedef_oran,
 'hedefe_ulasildi': hedefe_gore_durum,
 'puan': round(puan, 1),
 'durum': 'Mükemmel' if geri_donusum_orani >= 80 else
 'İyi' if geri_donusum_orani >= 60 else
 'Orta' if geri_donusum_orani >= 40 else 'Düşük'
 }

 def hesapla_leed_puani(
 self,
 enerji_puan: float = 0,
 su_puan: float = 0,
 malzeme_puan: float = 0,
 ic_mekan_puan: float = 0,
 yenilikcilik_puan: float = 0
 ) -> Dict[str, Any]:
 """
 LEED sertifika puanı hesaplar.

 Args:
 enerji_puan: Enerji kategorisi puanı
 su_puan: Su verimliliği puanı
 malzeme_puan: Malzeme kategorisi puanı
 ic_mekan_puan: İç mekan kalitesi puanı
 yenilikcilik_puan: Yenilikçilik puanı

 Returns:
 LEED sertifika analizi
 """
 # Toplam puan
 toplam_puan = (
 enerji_puan + su_puan + malzeme_puan +
 ic_mekan_puan + yenilikcilik_puan
 )

 # Maksimum puanlar
 max_enerji = self.LEED_KRITERLER['enerji_tasarrufu']['max_puan']
 max_su = self.LEED_KRITERLER['su_verimliligi']['max_puan']
 max_malzeme = self.LEED_KRITERLER['malzeme_kaynak']['max_puan']
 max_ic_mekan = self.LEED_KRITERLER['ic_mekan_kalitesi']['max_puan']
 max_yenilikcilik = self.LEED_KRITERLER['yenilikcilik']['max_puan']

 max_toplam = max_enerji + max_su + max_malzeme + max_ic_mekan + max_yenilikcilik

 # Sertifika seviyesi belirleme
 # LEED v4 kriterleri: Platinum (80+), Gold (60-79), Silver (50-59), Certified (40-49)
 if toplam_puan >= 80:
 seviye = 'Platinum'
 renk = '#E5E4E2'
 elif toplam_puan >= 60:
 seviye = 'Gold'
 renk = '#FFD700'
 elif toplam_puan >= 50:
 seviye = 'Silver'
 renk = '#C0C0C0'
 elif toplam_puan >= 40:
 seviye = 'Certified'
 renk = '#90EE90'
 else:
 seviye = 'Sertifika Alamaz'
 renk = '#FF6B6B'

 # Yüzde hesapla
 yuzde = (toplam_puan / max_toplam) * 100

 return {
 'toplam_puan': toplam_puan,
 'max_puan': max_toplam,
 'yuzde': round(yuzde, 1),
 'seviye': seviye,
 'renk': renk,
 'detay': {
 'enerji': {'puan': enerji_puan, 'max': max_enerji},
 'su': {'puan': su_puan, 'max': max_su},
 'malzeme': {'puan': malzeme_puan, 'max': max_malzeme},
 'ic_mekan': {'puan': ic_mekan_puan, 'max': max_ic_mekan},
 'yenilikcilik': {'puan': yenilikcilik_puan, 'max': max_yenilikcilik}
 },
 'oneriler': self._get_leed_oneri(toplam_puan, seviye)
 }

 def kaydet_atik_kaydi(
 self,
 proje_id: int,
 atik_turu: str,
 miktar_ton: float,
 geri_donusturuldu: bool,
 aciklama: str = ''
 ) -> Dict[str, Any]:
 """
 Atık kaydı oluşturur.

 Args:
 proje_id: Proje ID
 atik_turu: Atık türü
 miktar_ton: Miktar (ton)
 geri_donusturuldu: Geri dönüştürüldü mü?
 aciklama: Açıklama

 Returns:
 Kayıt sonucu
 """
 if not self.db:
 return {'success': False, 'error': 'Veritabanı bağlantısı yok'}

 try:
 with self.db.get_connection() as conn:
 cursor = conn.cursor()

 # Atık kategorisi kontrolü
 kategori_info = self.ATIK_KATEGORILERI.get(
 atik_turu,
 {'geri_donusturulur': False, 'tehlikeli': False}
 )

 cursor.execute("""
 INSERT INTO atik_yonetimi (
 proje_id, atik_turu, miktar_ton,
 geri_donusturuldu, tehlikeli, aciklama, tarih
 ) VALUES (?, ?, ?, ?, ?, ?, ?)
 """, (
 proje_id,
 atik_turu,
 miktar_ton,
 geri_donusturuldu,
 kategori_info['tehlikeli'],
 aciklama,
 datetime.now().strftime('%Y-%m-%d')
 ))

 conn.commit()

 return {
 'success': True,
 'atik_id': cursor.lastrowid,
 'mesaj': 'Atık kaydı oluşturuldu'
 }

 except Exception as e:
 logger.error(f"Atık kayıt hatası: {e}")
 return {'success': False, 'error': str(e)}

 def get_proje_atik_ozeti(self, proje_id: int) -> Dict[str, Any]:
 """
 Proje atık yönetimi özetini getirir.

 Args:
 proje_id: Proje ID

 Returns:
 Atık özeti
 """
 if not self.db:
 return {'error': 'Veritabanı bağlantısı yok'}

 try:
 with self.db.get_connection() as conn:
 cursor = conn.cursor()

 cursor.execute("""
 SELECT
 atik_turu,
 SUM(miktar_ton) as toplam_miktar,
 SUM(CASE WHEN geri_donusturuldu = 1 THEN miktar_ton ELSE 0 END) as geri_donusum,
 COUNT(*) as kayit_sayisi
 FROM atik_yonetimi
 WHERE proje_id = ?
 GROUP BY atik_turu
 """, (proje_id,))

 atik_detay = cursor.fetchall()

 toplam_atik = sum(row['toplam_miktar'] for row in atik_detay)
 toplam_geri_donusum = sum(row['geri_donusum'] for row in atik_detay)

 # Geri dönüşüm oranı hesapla
 geri_donusum_analiz = self.hesapla_geri_donusum_orani(
 toplam_atik,
 toplam_geri_donusum
 )

 # Hata kontrolü
 if 'error' in geri_donusum_analiz:
 return {
 'proje_id': proje_id,
 'toplam_atik_ton': round(toplam_atik, 2),
 'geri_donusum_ton': round(toplam_geri_donusum, 2),
 'geri_donusum_orani': 0.0,
 'atik_detay': [dict(row) for row in atik_detay],
 'durum': 'Veri Yok',
 'puan': 0
 }

 return {
 'proje_id': proje_id,
 'toplam_atik_ton': round(toplam_atik, 2),
 'geri_donusum_ton': round(toplam_geri_donusum, 2),
 'geri_donusum_orani': geri_donusum_analiz.get('geri_donusum_orani', 0.0),
 'atik_detay': [dict(row) for row in atik_detay],
 'durum': geri_donusum_analiz.get('durum', 'Bilinmiyor'),
 'puan': geri_donusum_analiz.get('puan', 0)
 }

 except Exception as e:
 logger.error(f"Atık özet hatası: {e}")
 return {'error': str(e)}

 # Yardımcı metodlar

 def _normalize_malzeme(self, malzeme_adi: str) -> str:
 """Malzeme adını normalize eder (küçük harf, Türkçe karakter)"""
 malzeme = malzeme_adi.lower().strip()

 # Anahtar kelime eşleştirme
 if 'beton' in malzeme or 'c20' in malzeme or 'c25' in malzeme:
 return 'beton'
 elif 'çimento' in malzeme or 'cimento' in malzeme:
 return 'çimento'
 elif 'çelik' in malzeme or 'celik' in malzeme:
 return 'çelik'
 elif 'demir' in malzeme or 'inşaat demiri' in malzeme:
 return 'demir'
 elif 'alüminyum' in malzeme or 'aluminyum' in malzeme:
 return 'alüminyum'
 elif 'cam' in malzeme:
 return 'cam'
 elif 'tuğla' in malzeme or 'tugla' in malzeme or 'brick' in malzeme:
 return 'tuğla'
 elif 'ahşap' in malzeme or 'ahsap' in malzeme or 'kereste' in malzeme:
 return 'ahşap'
 elif 'yalıtım' in malzeme or 'yalitim' in malzeme or 'izolasyon' in malzeme:
 if 'taş' in malzeme or 'tas' in malzeme or 'wool' in malzeme:
 return 'yalıtım_taşyünü'
 else:
 return 'yalıtım_eps'
 elif 'pvc' in malzeme:
 return 'pvc'
 elif 'asfalt' in malzeme:
 return 'asfalt'
 elif 'kireç' in malzeme or 'kirec' in malzeme:
 return 'kireç'
 elif 'mermer' in malzeme or 'granit' in malzeme:
 return 'mermer'
 elif 'seramik' in malzeme or 'fayans' in malzeme:
 return 'seramik'
 elif 'boya' in malzeme:
 return 'boya'
 else:
 return 'default'

 def _birim_donustur(self, miktar: float, birim: str) -> float:
 """Miktarı kg'a dönüştürür"""
 birim = birim.lower().strip()

 if birim in ['kg', 'kilogram']:
 return miktar
 elif birim in ['ton', 't']:
 return miktar * 1000
 elif birim in ['gr', 'gram']:
 return miktar / 1000
 elif birim in ['m3', 'm³']:
 # m³ için ayrı işlem (yoğunluğa bağlı)
 return miktar * 2400 # Ortalama beton yoğunluğu
 else:
 return miktar # Varsayılan kg kabul et

 def _get_malzeme_kategori(self, malzeme_adi: str) -> str:
 """Malzeme kategorisini döndürür"""
 malzeme = malzeme_adi.lower()

 if any(k in malzeme for k in ['beton', 'çimento', 'kireç']):
 return 'Bağlayıcılar'
 elif any(k in malzeme for k in ['demir', 'çelik', 'metal']):
 return 'Metal'
 elif any(k in malzeme for k in ['tuğla', 'kiremit', 'seramik']):
 return 'Seramik/Tuğla'
 elif any(k in malzeme for k in ['yalıtım', 'izolasyon']):
 return 'Yalıtım'
 elif any(k in malzeme for k in ['ahşap', 'kereste']):
 return 'Ahşap'
 elif any(k in malzeme for k in ['cam']):
 return 'Cam'
 elif any(k in malzeme for k in ['boya', 'sıva']):
 return 'Kaplama'
 else:
 return 'Diğer'

 def _get_leed_oneri(self, toplam_puan: float, seviye: str) -> List[str]:
 """LEED puanına göre öneriler döndürür"""
 oneriler = []

 if seviye == 'Sertifika Alamaz':
 oneriler.append("Enerji verimliliği için LED aydınlatma kullanın")
 oneriler.append("Geri dönüştürülmüş malzeme oranını artırın (%20+)")
 oneriler.append("Su tasarruflu armatürler tercih edin")
 oneriler.append("Yenilenebilir enerji kaynaklarını değerlendirin")
 elif seviye == 'Certified':
 oneriler.append("Silver sertifika için %10 daha fazla puan gerekli")
 oneriler.append("Güneş paneli eklemeyi düşünün")
 oneriler.append("Yerel malzeme kullanımını artırın")
 elif seviye == 'Silver':
 oneriler.append("Gold sertifika için %10 daha fazla puan gerekli")
 oneriler.append("Yağmur suyu toplama sistemi ekleyin")
 oneriler.append("Doğal havalandırma sistemleri değerlendirin")
 elif seviye == 'Gold':
 oneriler.append("Platinum sertifika için %20 daha fazla puan gerekli")
 oneriler.append("Net sıfır enerji binası hedefleyin")
 oneriler.append("Gelişmiş atık yönetimi uygulayın")
 else: # Platinum
 oneriler.append("Mükemmel! Sertifikasyon için başvurun")
 oneriler.append("Başarınızı pazarlama materyallerinde kullanın")
 oneriler.append("Diğer projelerde de bu standartları uygulayın")

 return oneriler
