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
    KARBON_FAKTORLERI: Dict[str, float] = {
        'beton': 135.0,           # kg CO2/m³
        'çimento': 900.0,         # kg CO2/ton
        'çelik': 1850.0,          # kg CO2/ton
        'demir': 1900.0,          # kg CO2/ton
        'alüminyum': 11500.0,     # kg CO2/ton
        'cam': 850.0,             # kg CO2/ton
        'tuğla': 240.0,           # kg CO2/ton
        'ahşap': -480.0,          # kg CO2/ton (negatif = karbon tutma)
        'yalıtım_taşyünü': 380.0, # kg CO2/ton
        'yalıtım_eps': 3400.0,    # kg CO2/ton
        'pvc': 2400.0,            # kg CO2/ton
        'asfalt': 45.0,           # kg CO2/ton
        'kireç': 1100.0,          # kg CO2/ton
        'mermer': 95.0,           # kg CO2/m²
        'seramik': 7.5,           # kg CO2/m²
        'boya': 2.9,              # kg CO2/kg
        'default': 100.0,
    }

    # Enerji tüketim sınıf limitleri (kWh/m²/yıl)
    ENERJI_SINIF_LIMITLERI: Dict[str, Tuple] = {
        'A+': (0, 50),
        'A': (50, 100),
        'B': (100, 150),
        'C': (150, 200),
        'D': (200, 250),
        'E': (250, 300),
        'F': (300, 350),
        'G': (350, float('inf')),
    }

    # LEED Puan Kriterleri (Basitleştirilmiş)
    LEED_KRITERLER: Dict[str, Any] = {
        'enerji_tasarrufu': {
            'max_puan': 33,
            'kriterler': [
                {'baslik': 'Enerji Verimliliği', 'puan': 18},
                {'baslik': 'Yenilenebilir Enerji', 'puan': 15},
            ],
        },
        'su_verimliligi': {
            'max_puan': 12,
            'kriterler': [
                {'baslik': 'Su Kullanım Azaltma', 'puan': 8},
                {'baslik': 'Yağmur Suyu Toplama', 'puan': 4},
            ],
        },
        'malzeme_kaynak': {
            'max_puan': 13,
            'kriterler': [
                {'baslik': 'Geri Dönüştürülmüş Malzeme', 'puan': 5},
                {'baslik': 'Yerel Malzeme', 'puan': 4},
                {'baslik': 'Düşük Emisyon Malzeme', 'puan': 4},
            ],
        },
        'ic_mekan_kalitesi': {
            'max_puan': 16,
            'kriterler': [
                {'baslik': 'Hava Kalitesi', 'puan': 8},
                {'baslik': 'Doğal Aydınlatma', 'puan': 8},
            ],
        },
        'yenilikcilik': {
            'max_puan': 6,
            'kriterler': [
                {'baslik': 'İnovatif Tasarım', 'puan': 5},
                {'baslik': 'LEED Uzmanı', 'puan': 1},
            ],
        },
    }

    # Atık Kategorileri
    ATIK_KATEGORILERI: Dict[str, Dict] = {
        'beton_moloz': {'geri_donusturulur': True, 'tehlikeli': False},
        'ahsap': {'geri_donusturulur': True, 'tehlikeli': False},
        'metal': {'geri_donusturulur': True, 'tehlikeli': False},
        'plastik': {'geri_donusturulur': True, 'tehlikeli': False},
        'cam': {'geri_donusturulur': True, 'tehlikeli': False},
        'yalitim': {'geri_donusturulur': False, 'tehlikeli': False},
        'boya_kimyasal': {'geri_donusturulur': False, 'tehlikeli': True},
        'asbest': {'geri_donusturulur': False, 'tehlikeli': True},
        'karisik': {'geri_donusturulur': False, 'tehlikeli': False},
    }

    def __init__(self, db_manager=None):
        """
        Sürdürülebilirlik motoru başlat.

        Args:
            db_manager: DatabaseManager instance (opsiyonel)
        """
        self.db = db_manager

    # ------------------------------------------------------------------
    # Karbon Ayak İzi
    # ------------------------------------------------------------------

    def hesapla_karbon_ayakizi(
        self,
        malzeme_adi: str,
        miktar: float,
        birim: str = 'ton',
    ) -> Dict[str, Any]:
        """
        Malzeme bazında karbon ayak izi hesaplar.

        Args:
            malzeme_adi: Malzeme adı
            miktar: Miktar
            birim: Birim (ton, m³, kg)

        Returns:
            Karbon ayak izi sonucu
        """
        malzeme_key = self._normalize_malzeme(malzeme_adi)
        karbon_faktor = self.KARBON_FAKTORLERI.get(
            malzeme_key, self.KARBON_FAKTORLERI['default']
        )
        miktar_kg = self._birim_donustur(miktar, birim)

        if birim in ('m3', 'm³'):
            karbon_emisyon = miktar * karbon_faktor
        else:
            karbon_emisyon = (miktar_kg / 1000) * karbon_faktor

        agac_esdegeri = abs(karbon_emisyon) / 20

        return {
            'malzeme': malzeme_adi,
            'miktar': miktar,
            'birim': birim,
            'karbon_faktor': karbon_faktor,
            'karbon_emisyon_kg': round(karbon_emisyon, 2),
            'karbon_emisyon_ton': round(karbon_emisyon / 1000, 3),
            'agac_esdegeri': round(agac_esdegeri, 1),
            'karbon_pozitif': karbon_emisyon > 0,
        }

    def hesapla_proje_karbon_ayakizi(self, proje_id: int) -> Dict[str, Any]:
        """Proje genelinde toplam karbon ayak izi hesaplar."""
        if not self.db:
            return {'error': 'Veritabanı bağlantısı yok'}

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT mk.poz_no, mk.tanim, mk.miktar, mk.birim,
                           p.poz_no as poz_kodu, p.tanim as poz_tanim
                    FROM metraj_kalemleri mk
                    LEFT JOIN pozlar p ON mk.poz_no = p.poz_no
                    WHERE mk.proje_id = ?
                """, (proje_id,))
                kalemler = cursor.fetchall()

            toplam_karbon = 0.0
            detay_liste = []
            kategori_dagilim: Dict[str, float] = {}

            for kalem in kalemler:
                sonuc = self.hesapla_karbon_ayakizi(
                    kalem['tanim'] or kalem['poz_tanim'] or 'Genel',
                    kalem['miktar'],
                    kalem['birim'],
                )
                toplam_karbon += sonuc['karbon_emisyon_kg']
                detay_liste.append({
                    'poz_no': kalem['poz_no'],
                    'tanim': kalem['tanim'],
                    'miktar': kalem['miktar'],
                    'birim': kalem['birim'],
                    'karbon_kg': sonuc['karbon_emisyon_kg'],
                })
                kategori = self._get_malzeme_kategori(kalem['tanim'] or '')
                kategori_dagilim[kategori] = (
                    kategori_dagilim.get(kategori, 0) + sonuc['karbon_emisyon_kg']
                )

            detay_liste.sort(key=lambda x: abs(x['karbon_kg']), reverse=True)

            return {
                'proje_id': proje_id,
                'toplam_karbon_kg': round(toplam_karbon, 2),
                'toplam_karbon_ton': round(toplam_karbon / 1000, 3),
                'agac_esdegeri': round(abs(toplam_karbon) / 20, 1),
                'toplam_kalem': len(kalemler),
                'kategori_dagilim': kategori_dagilim,
                'en_yuksek_10': detay_liste[:10],
                'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

        except Exception as exc:
            logger.error("Proje karbon hesaplama hatası: %s", exc)
            return {'error': str(exc)}

    # ------------------------------------------------------------------
    # Enerji Verimliliği
    # ------------------------------------------------------------------

    def hesapla_enerji_sinifi(
        self,
        yillik_tuketim_kwh: float,
        toplam_alan_m2: float,
    ) -> Dict[str, Any]:
        """
        Enerji verimliliği sınıfı hesaplar (TS 825 / AB Enerji Etiketi).

        Args:
            yillik_tuketim_kwh: Yıllık enerji tüketimi (kWh)
            toplam_alan_m2: Toplam bina alanı (m²)
        """
        if toplam_alan_m2 <= 0:
            return {'error': 'Geçersiz alan değeri'}

        birim_tuketim = yillik_tuketim_kwh / toplam_alan_m2

        enerji_sinifi = 'G'
        for sinif, (min_val, max_val) in self.ENERJI_SINIF_LIMITLERI.items():
            if min_val <= birim_tuketim < max_val:
                enerji_sinifi = sinif
                break

        sinif_sira = ['G', 'F', 'E', 'D', 'C', 'B', 'A', 'A+']
        puan = (sinif_sira.index(enerji_sinifi) / len(sinif_sira)) * 100
        yillik_maliyet = yillik_tuketim_kwh * 0.5
        co2_emisyon = yillik_tuketim_kwh * 0.45  # Türkiye elektrik şebekesi

        return {
            'enerji_sinifi': enerji_sinifi,
            'puan': round(puan, 1),
            'birim_tuketim_kwh_m2': round(birim_tuketim, 2),
            'yillik_tuketim_kwh': yillik_tuketim_kwh,
            'toplam_alan_m2': toplam_alan_m2,
            'yillik_maliyet_tl': round(yillik_maliyet, 2),
            'co2_emisyon_kg': round(co2_emisyon, 2),
            'co2_emisyon_ton': round(co2_emisyon / 1000, 3),
        }

    # ------------------------------------------------------------------
    # Geri Dönüşüm
    # ------------------------------------------------------------------

    def hesapla_geri_donusum_orani(
        self,
        toplam_atik_ton: float,
        geri_donusturulen_ton: float,
    ) -> Dict[str, Any]:
        """Geri dönüşüm oranını hesaplar. Hedef: %70."""
        if toplam_atik_ton <= 0:
            return {'error': 'Geçersiz atık miktarı'}

        geri_donusum_orani = (geri_donusturulen_ton / toplam_atik_ton) * 100
        hedef_oran = 70.0
        puan = min((geri_donusum_orani / hedef_oran) * 100, 100)

        if geri_donusum_orani >= 80:
            durum = 'Mükemmel'
        elif geri_donusum_orani >= 60:
            durum = 'İyi'
        elif geri_donusum_orani >= 40:
            durum = 'Orta'
        else:
            durum = 'Düşük'

        return {
            'toplam_atik_ton': toplam_atik_ton,
            'geri_donusturulen_ton': geri_donusturulen_ton,
            'atilan_ton': round(toplam_atik_ton - geri_donusturulen_ton, 2),
            'geri_donusum_orani': round(geri_donusum_orani, 2),
            'hedef_oran': hedef_oran,
            'hedefe_ulasildi': geri_donusum_orani >= hedef_oran,
            'puan': round(puan, 1),
            'durum': durum,
        }

    # ------------------------------------------------------------------
    # LEED
    # ------------------------------------------------------------------

    def hesapla_leed_puani(
        self,
        enerji_puan: float = 0,
        su_puan: float = 0,
        malzeme_puan: float = 0,
        ic_mekan_puan: float = 0,
        yenilikcilik_puan: float = 0,
    ) -> Dict[str, Any]:
        """LEED v4 sertifika puanı hesaplar."""
        toplam_puan = (
            enerji_puan + su_puan + malzeme_puan + ic_mekan_puan + yenilikcilik_puan
        )

        max_toplam = sum(
            v['max_puan'] for v in self.LEED_KRITERLER.values()
        )

        if toplam_puan >= 80:
            seviye, renk = 'Platinum', '#E5E4E2'
        elif toplam_puan >= 60:
            seviye, renk = 'Gold', '#FFD700'
        elif toplam_puan >= 50:
            seviye, renk = 'Silver', '#C0C0C0'
        elif toplam_puan >= 40:
            seviye, renk = 'Certified', '#90EE90'
        else:
            seviye, renk = 'Sertifika Alamaz', '#FF6B6B'

        return {
            'toplam_puan': toplam_puan,
            'max_puan': max_toplam,
            'yuzde': round((toplam_puan / max_toplam) * 100, 1),
            'seviye': seviye,
            'renk': renk,
            'detay': {
                'enerji': {'puan': enerji_puan, 'max': self.LEED_KRITERLER['enerji_tasarrufu']['max_puan']},
                'su': {'puan': su_puan, 'max': self.LEED_KRITERLER['su_verimliligi']['max_puan']},
                'malzeme': {'puan': malzeme_puan, 'max': self.LEED_KRITERLER['malzeme_kaynak']['max_puan']},
                'ic_mekan': {'puan': ic_mekan_puan, 'max': self.LEED_KRITERLER['ic_mekan_kalitesi']['max_puan']},
                'yenilikcilik': {'puan': yenilikcilik_puan, 'max': self.LEED_KRITERLER['yenilikcilik']['max_puan']},
            },
            'oneriler': self._get_leed_oneri(toplam_puan, seviye),
        }

    # ------------------------------------------------------------------
    # Atık Yönetimi
    # ------------------------------------------------------------------

    def kaydet_atik_kaydi(
        self,
        proje_id: int,
        atik_turu: str,
        miktar_ton: float,
        geri_donusturuldu: bool,
        aciklama: str = '',
    ) -> Dict[str, Any]:
        """Atık kaydı oluşturur."""
        if not self.db:
            return {'success': False, 'error': 'Veritabanı bağlantısı yok'}

        try:
            kategori_info = self.ATIK_KATEGORILERI.get(
                atik_turu, {'geri_donusturulur': False, 'tehlikeli': False}
            )
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO atik_yonetimi (
                        proje_id, atik_turu, miktar_ton,
                        geri_donusturuldu, tehlikeli, aciklama, tarih
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    proje_id, atik_turu, miktar_ton,
                    geri_donusturuldu, kategori_info['tehlikeli'],
                    aciklama, datetime.now().strftime('%Y-%m-%d'),
                ))
                conn.commit()
                return {'success': True, 'atik_id': cursor.lastrowid, 'mesaj': 'Atık kaydı oluşturuldu'}

        except Exception as exc:
            logger.error("Atık kayıt hatası: %s", exc)
            return {'success': False, 'error': str(exc)}

    def get_proje_atik_ozeti(self, proje_id: int) -> Dict[str, Any]:
        """Proje atık yönetimi özetini getirir."""
        if not self.db:
            return {'error': 'Veritabanı bağlantısı yok'}

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT atik_turu,
                           SUM(miktar_ton) as toplam_miktar,
                           SUM(CASE WHEN geri_donusturuldu = 1 THEN miktar_ton ELSE 0 END) as geri_donusum,
                           COUNT(*) as kayit_sayisi
                    FROM atik_yonetimi
                    WHERE proje_id = ?
                    GROUP BY atik_turu
                """, (proje_id,))
                atik_detay = cursor.fetchall()

            toplam_atik = sum(row['toplam_miktar'] for row in atik_detay)
            toplam_geri = sum(row['geri_donusum'] for row in atik_detay)
            analiz = self.hesapla_geri_donusum_orani(toplam_atik, toplam_geri)

            return {
                'proje_id': proje_id,
                'toplam_atik_ton': round(toplam_atik, 2),
                'geri_donusum_ton': round(toplam_geri, 2),
                'geri_donusum_orani': analiz.get('geri_donusum_orani', 0.0),
                'atik_detay': [dict(row) for row in atik_detay],
                'durum': analiz.get('durum', 'Veri Yok'),
                'puan': analiz.get('puan', 0),
            }

        except Exception as exc:
            logger.error("Atık özet hatası: %s", exc)
            return {'error': str(exc)}

    # ------------------------------------------------------------------
    # Yardımcı metodlar (private)
    # ------------------------------------------------------------------

    def _normalize_malzeme(self, malzeme_adi: str) -> str:
        """Malzeme adını normalize eder."""
        m = malzeme_adi.lower().strip()
        if 'beton' in m or 'c20' in m or 'c25' in m:
            return 'beton'
        if 'çimento' in m or 'cimento' in m:
            return 'çimento'
        if 'çelik' in m or 'celik' in m:
            return 'çelik'
        if 'demir' in m:
            return 'demir'
        if 'alüminyum' in m or 'aluminyum' in m:
            return 'alüminyum'
        if 'cam' in m:
            return 'cam'
        if 'tuğla' in m or 'tugla' in m:
            return 'tuğla'
        if 'ahşap' in m or 'ahsap' in m or 'kereste' in m:
            return 'ahşap'
        if 'yalıtım' in m or 'yalitim' in m or 'izolasyon' in m:
            return 'yalıtım_taşyünü' if ('taş' in m or 'wool' in m) else 'yalıtım_eps'
        if 'pvc' in m:
            return 'pvc'
        if 'asfalt' in m:
            return 'asfalt'
        if 'kireç' in m or 'kirec' in m:
            return 'kireç'
        if 'mermer' in m or 'granit' in m:
            return 'mermer'
        if 'seramik' in m or 'fayans' in m:
            return 'seramik'
        if 'boya' in m:
            return 'boya'
        return 'default'

    def _birim_donustur(self, miktar: float, birim: str) -> float:
        """Miktarı kg'a dönüştürür."""
        b = birim.lower().strip()
        if b in ('kg', 'kilogram'):
            return miktar
        if b in ('ton', 't'):
            return miktar * 1000
        if b in ('gr', 'gram'):
            return miktar / 1000
        if b in ('m3', 'm³'):
            return miktar * 2400  # ortalama beton yoğunluğu
        return miktar

    def _get_malzeme_kategori(self, malzeme_adi: str) -> str:
        """Malzeme kategorisini döndürür."""
        m = malzeme_adi.lower()
        if any(k in m for k in ('beton', 'çimento', 'kireç')):
            return 'Bağlayıcılar'
        if any(k in m for k in ('demir', 'çelik', 'metal')):
            return 'Metal'
        if any(k in m for k in ('tuğla', 'kiremit', 'seramik')):
            return 'Seramik/Tuğla'
        if any(k in m for k in ('yalıtım', 'izolasyon')):
            return 'Yalıtım'
        if any(k in m for k in ('ahşap', 'kereste')):
            return 'Ahşap'
        if 'cam' in m:
            return 'Cam'
        if any(k in m for k in ('boya', 'sıva')):
            return 'Kaplama'
        return 'Diğer'

    def _get_leed_oneri(self, toplam_puan: float, seviye: str) -> List[str]:
        """LEED puanına göre öneriler döndürür."""
        oneriler = {
            'Sertifika Alamaz': [
                "Enerji verimliliği için LED aydınlatma kullanın",
                "Geri dönüştürülmüş malzeme oranını artırın (%20+)",
                "Su tasarruflu armatürler tercih edin",
                "Yenilenebilir enerji kaynaklarını değerlendirin",
            ],
            'Certified': [
                "Silver sertifika için %10 daha fazla puan gerekli",
                "Güneş paneli eklemeyi düşünün",
                "Yerel malzeme kullanımını artırın",
            ],
            'Silver': [
                "Gold sertifika için %10 daha fazla puan gerekli",
                "Yağmur suyu toplama sistemi ekleyin",
                "Doğal havalandırma sistemleri değerlendirin",
            ],
            'Gold': [
                "Platinum sertifika için %20 daha fazla puan gerekli",
                "Net sıfır enerji binası hedefleyin",
                "Gelişmiş atık yönetimi uygulayın",
            ],
            'Platinum': [
                "Mükemmel! Sertifikasyon için başvurun",
                "Başarınızı pazarlama materyallerinde kullanın",
                "Diğer projelerde de bu standartları uygulayın",
            ],
        }
        return oneriler.get(seviye, [])
