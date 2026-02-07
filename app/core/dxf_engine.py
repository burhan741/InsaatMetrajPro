"""
DXF Engine
DXF dosyaları için gelişmiş işleme motoru
"""

import sys
import math
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

try:
    import ezdxf
    from ezdxf import DXFStructureError, DXFValueError
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False
    ezdxf = None

try:
    from shapely.geometry import box
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    box = None

logger = logging.getLogger(__name__)
# Logger seviyesini açıkça DEBUG'a ayarla (modül import edilirken logging konfigürasyonu aktif olmalı)
logger.setLevel(logging.DEBUG)


class DXFEngine:
    """
    DXF dosyaları için gelişmiş işleme motoru.
    
    DXF dosyalarını okur, analiz eder ve çeşitli metraj hesaplamaları yapar.
    """
    
    def __init__(self) -> None:
        """DXF Engine'i başlat."""
        if not EZDXF_AVAILABLE:
            logger.warning(
                "ezdxf kütüphanesi yüklü değil. "
                "CAD işlemleri için: pip install ezdxf"
            )
    
    def load_dxf(self, file_path: Path) -> Optional[Any]:
        """
        DXF dosyasını yükle.
        
        Args:
            file_path: DXF dosyasının yolu
            
        Returns:
            ezdxf.Document: Yüklenen DXF dokümanı veya None
        """
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")
        
        try:
            doc = ezdxf.readfile(str(file_path))
            logger.info(f"DXF dosyası başarıyla yüklendi: {file_path}")
            return doc
        except Exception as e:
            logger.error(f"DXF yükleme hatası: {e}")
            raise RuntimeError(f"Dosya yüklenirken hata oluştu: {e}")


class DXFAnaliz:
    """
    DXF dosyalarını analiz etmek için sınıf.
    
    Alan hesaplama, blok sayımı ve katman listeleme işlemlerini yapar.
    Tolerans ile açık çizgileri otomatik kapatma özelliği içerir.
    Çizim birimi desteği ile farklı birimlerdeki dosyaları işleyebilir.
    """
    
    def __init__(self, dosya_yolu: str, cizim_birimi: str = "cm") -> None:
        """
        DXFAnaliz sınıfını başlat.
        
        Args:
            dosya_yolu: DXF dosyasının yolu
            cizim_birimi: Çizim birimi ('m', 'cm', 'mm')
                         Varsayılan: 'cm' (mimaride en yaygını)
        """
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli")
        
        self.dosya_yolu = dosya_yolu
        self.birim = cizim_birimi
        self.doc = None
        self.msp = None
        self.yukle()
    
    def yukle(self) -> None:
        """DXF dosyasını hafızaya yükler."""
        try:
            self.doc = ezdxf.readfile(self.dosya_yolu)
            self.msp = self.doc.modelspace()
            logger.info(f"✅ Başarılı: '{self.dosya_yolu}' yüklendi. Birim: {self.birim}")
        except Exception as e:
            error_msg = f"Hata: {e}"
            logger.error(error_msg)
            print(error_msg)
            sys.exit(1)
    
    def katmanlari_listele(self) -> List[str]:
        """Dosyadaki tüm katman isimlerini döndürür."""
        if not self.doc:
            return []
        return [layer.dxf.name for layer in self.doc.layers]
    
    def acikliklari_tespit_et(self) -> Dict[str, List[str]]:
        """
        DXF dosyasındaki pencere ve kapı katmanlarını otomatik tespit eder.
        
        Returns:
            Dict: {
                'pencere': [katman_adlari],
                'kapi': [katman_adlari]
            }
        """
        tum_katmanlar = self.katmanlari_listele()
        pencere_katmanlari = []
        kapi_katmanlari = []
        
        # Pencere pattern'leri
        pencere_patterns = [
            'pencere', 'window', 'win', 'w-', 'p-', 'fenster',
            'pencere_', 'window_', 'win_', 'pencere_', 'pencere_'
        ]
        
        # Kapı pattern'leri
        kapi_patterns = [
            'kapı', 'kapi', 'door', 'd-', 'k-', 'tür', 'tur',
            'kapı_', 'kapi_', 'door_', 'kapı_', 'kapi_'
        ]
        
        for katman in tum_katmanlar:
            katman_lower = katman.lower()
            
            # Pencere kontrolü
            for pattern in pencere_patterns:
                if pattern in katman_lower:
                    pencere_katmanlari.append(katman)
                    logger.debug(f"🔍 Pencere katmanı tespit edildi: {katman}")
                    break
            
            # Kapı kontrolü
            for pattern in kapi_patterns:
                if pattern in katman_lower:
                    kapi_katmanlari.append(katman)
                    logger.debug(f"🚪 Kapı katmanı tespit edildi: {katman}")
                    break
        
        logger.info(f"📊 Açıklık tespiti: {len(pencere_katmanlari)} pencere, {len(kapi_katmanlari)} kapı katmanı bulundu")
        
        return {
            'pencere': pencere_katmanlari,
            'kapi': kapi_katmanlari
        }
    
    def aciklik_alani_hesapla(self, katman_adi: str) -> float:
        """
        Belirtilen açıklık katmanındaki toplam alanı hesaplar.
        
        Args:
            katman_adi: Açıklık katman adı (pencere veya kapı)
            
        Returns:
            float: Toplam açıklık alanı (m²)
        """
        # Önce kapalı poligonların alanını hesapla
        alan_sonuc = self.alan_hesapla(katman_adi)
        alan_m2 = alan_sonuc.get('toplam_miktar', 0.0)
        
        # Eğer alan bulunamadıysa, dikdörtgen/çizgi bazlı hesaplama yap
        if alan_m2 == 0:
            # LINE veya LWPOLYLINE (açık) entity'lerinden dikdörtgen alanı hesapla
            line_query = f'LINE[layer=="{katman_adi}"]'
            lines = list(self.msp.query(line_query))
            
            lwpolyline_query = f'LWPOLYLINE[layer=="{katman_adi}"]'
            lwpolylines = list(self.msp.query(lwpolyline_query))
            
            # Basit dikdörtgen alanı hesapla (min-max koordinatlar)
            if lines or lwpolylines:
                min_x = float('inf')
                max_x = float('-inf')
                min_y = float('inf')
                max_y = float('-inf')
                
                for entity in lines + lwpolylines:
                    try:
                        if hasattr(entity, 'start') and hasattr(entity, 'end'):
                            # LINE entity
                            points = [entity.start, entity.end]
                        elif hasattr(entity, 'points'):
                            # LWPOLYLINE entity
                            with entity.points("xy") as pts:
                                points = list(pts)
                        else:
                            continue
                        
                        for point in points:
                            x, y = point[0], point[1]
                            min_x = min(min_x, x)
                            max_x = max(max_x, x)
                            min_y = min(min_y, y)
                            max_y = max(max_y, y)
                    except:
                        continue
                
                if min_x != float('inf'):
                    # Dikdörtgen alanı hesapla
                    genislik = max_x - min_x
                    yukseklik = max_y - min_y
                    ham_alan = genislik * yukseklik
                    alan_m2 = self._birim_cevir(ham_alan)
                    logger.info(f"📐 Açıklık alanı (dikdörtgen): {alan_m2:.4f} m² (katman: {katman_adi})")
        
        logger.info(f"📊 Açıklık alanı toplam: {alan_m2:.4f} m² (katman: {katman_adi})")
        return alan_m2
    
    def alan_hesapla(self, katman_adi: str, tolerans: float = 0.20) -> Dict[str, Any]:
        """
        Belirtilen katmandaki KAPALI poligonların (LWPOLYLINE) alanını hesaplar.
        
        Tolerans parametresi ile açık çizgileri otomatik kapatma özelliği vardır.
        Çizgiler arasında belirlenen tolerans kadar boşluk varsa bunu otomatik olarak 
        kapatır ve alan hesaplar. Sonuç her zaman m² cinsinden döner.
        
        Args:
            katman_adi: Hesaplanacak katman adı
            tolerans: Çizgiler arasında kapatılacak maksimum boşluk (metre cinsinden)
                     Varsayılan: 0.20 (20 cm)
        
        Returns:
            Dict: Hesaplama sonuçları (m² cinsinden)
        """
        toplam_alan = 0.0
        parca_sayisi = 0
        tamir_edilen = 0
        
        # Birime göre toleransı ayarla (boşluk kapatma hassasiyeti)
        # Eğer çizim CM ise ve biz 20cm boşluk kapatacaksak, tolerans 20 olmalı.
        gercek_tolerans = tolerans
        if self.birim == "cm":
            gercek_tolerans = tolerans * 100  # 0.2m -> 20cm
        elif self.birim == "mm":
            gercek_tolerans = tolerans * 1000  # 0.2m -> 200mm
        
        sorgu = f'LWPOLYLINE[layer=="{katman_adi}"]'
        entities = list(self.msp.query(sorgu))
        logger.info(f"🔍 alan_hesapla() - Katman: {katman_adi}, Birim: {self.birim}, Bulunan LWPOLYLINE sayısı: {len(entities)}")
        
        for idx, entity in enumerate(entities):
            try:
                # Kapalı mı kontrol et
                is_closed = getattr(entity, 'is_closed', False)
                logger.info(f"📐 LWPOLYLINE #{idx+1} (alan): is_closed={is_closed}")
                
                # Noktaları okumak için entity.points() context manager kullan
                noktalar = None
                try:
                    with entity.points("xy") as pts:
                        noktalar = list(pts)
                        logger.info(f"✅ LWPOLYLINE #{idx+1} (alan) noktaları points() ile okundu: {len(noktalar)} nokta")
                except (AttributeError, TypeError) as e1:
                    logger.warning(f"⚠️ LWPOLYLINE #{idx+1} (alan) points() hatası: {e1}, alternatif yöntem deneniyor...")
                    # Alternatif: vertices kullan
                    try:
                        noktalar = [(v[0], v[1]) for v in entity.vertices]
                        logger.info(f"✅ LWPOLYLINE #{idx+1} (alan) noktaları vertices ile okundu: {len(noktalar)} nokta")
                    except Exception as e2:
                        logger.error(f"❌ LWPOLYLINE #{idx+1} (alan) nokta okuma hatası: {e2}")
                        continue
                
                if not noktalar or len(noktalar) < 3:
                    logger.warning(f"⚠️ LWPOLYLINE #{idx+1} (alan) yeterli nokta yok: {len(noktalar) if noktalar else 0} nokta (en az 3 gerekli)")
                    continue
                
                # Kapalı mı veya kapatılabilir mi?
                kapatildi = False
                if is_closed:
                    kapatildi = True
                    logger.info(f"✅ LWPOLYLINE #{idx+1} (alan) kapalı olarak işaretlenmiş")
                else:
                    baslangic = noktalar[0]
                    bitis = noktalar[-1]
                    mesafe = math.hypot(bitis[0] - baslangic[0], bitis[1] - baslangic[1])
                    logger.info(f"📏 LWPOLYLINE #{idx+1} (alan) başlangıç-bitiş mesafesi: {mesafe:.4f} (birim: {self.birim}), tolerans: {gercek_tolerans:.4f}")
                    if mesafe <= gercek_tolerans:
                        kapatildi = True
                        tamir_edilen += 1
                        logger.info(f"✅ LWPOLYLINE #{idx+1} (alan) tolerans içinde, kapatıldı")
                
                if kapatildi:
                    ham_alan = self._shoelace_formulu(noktalar)
                    logger.info(f"📐 LWPOLYLINE #{idx+1} (alan) ham alan (shoelace): {ham_alan:.4f} (birim²: {self.birim}²)")
                    
                    # HAM ALANI METREKAREYE ÇEVİR
                    gercek_alan = self._birim_cevir(ham_alan)
                    logger.info(f"✅ LWPOLYLINE #{idx+1} (alan) dönüştürülmüş alan: {gercek_alan:.4f} m² (ham: {ham_alan:.4f} {self.birim}²)")
                    
                    toplam_alan += gercek_alan
                    parca_sayisi += 1
                    logger.info(f"📊 LWPOLYLINE #{idx+1} (alan) eklendi. Toplam alan: {toplam_alan:.4f} m²")
                else:
                    logger.info(f"⏭️ LWPOLYLINE #{idx+1} (alan) açık ve tolerans dışında, atlandı")
            
            except Exception as e:
                logger.error(f"❌ LWPOLYLINE #{idx+1} (alan) işleme hatası: {e}", exc_info=True)
                continue
        
        logger.info(f"📊 alan_hesapla() ÖZET - Katman: {katman_adi}, Toplam alan: {toplam_alan:.4f} m², Parça sayısı: {parca_sayisi}, Tamir edilen: {tamir_edilen}")
        
        return {
            "katman": katman_adi,
            "toplam_miktar": round(toplam_alan, 2),
            "birim": "m²",
            "parca_sayisi": parca_sayisi,
            "not": f"{tamir_edilen} parça AI ile birleştirildi."
        }
    
    def uzunluk_hesapla(self, katman_adi: str) -> Dict[str, Any]:
        """
        Belirtilen katmandaki çizgilerin (LINE, LWPOLYLINE, POLYLINE, ARC, MLINE) toplam uzunluğunu hesaplar.
        Duvar metrajı için kullanılır.
        
        Args:
            katman_adi: Hesaplanacak katman adı
            
        Returns:
            Dict: Hesaplama sonuçları (m cinsinden)
        """
        logger.info(f"🔍 uzunluk_hesapla() çağrıldı - Katman: {katman_adi}, Birim: {self.birim}")
        toplam_uzunluk = 0.0
        parca_sayisi = 0
        detay_bilgi = []
        
        # LINE entity'lerini hesapla
        line_query = f'LINE[layer=="{katman_adi}"]'
        line_entities = list(self.msp.query(line_query))
        line_sayisi = len(line_entities)
        line_toplam = 0.0
        
        for entity in line_entities:
            try:
                start = entity.dxf.start
                end = entity.dxf.end
                uzunluk = math.hypot(
                    end.x - start.x,
                    end.y - start.y
                )
                # Birime göre metreye çevir (mimari projeler genelde m cinsindendir)
                if self.birim == "cm":
                    uzunluk = uzunluk / 100.0  # cm -> m
                    logger.debug(f"LINE: {uzunluk*100:.2f}cm -> {uzunluk:.4f}m")
                elif self.birim == "mm":
                    uzunluk = uzunluk / 1000.0  # mm -> m
                    logger.debug(f"LINE: {uzunluk*1000:.2f}mm -> {uzunluk:.4f}m")
                else:  # m veya başka bir değer - zaten metre kabul et
                    logger.debug(f"LINE: {uzunluk:.4f}m (birim: {self.birim}, dönüşüm yok)")
                line_toplam += uzunluk
                parca_sayisi += 1
            except Exception as e:
                logger.warning(f"LINE entity okuma hatası: {e}")
                continue
        
        if line_sayisi > 0:
            detay_bilgi.append(f"LINE: {line_sayisi} adet, toplam: {line_toplam:.2f}m")
        toplam_uzunluk += line_toplam
        
        # POLYLINE entity'lerini hesapla (eski format)
        polyline_query = f'POLYLINE[layer=="{katman_adi}"]'
        polyline_entities = list(self.msp.query(polyline_query))
        polyline_sayisi = len(polyline_entities)
        polyline_toplam = 0.0
        
        for entity in polyline_entities:
            try:
                uzunluk = 0.0
                vertices = list(entity.vertices)
                if len(vertices) < 2:
                    continue
                
                for i in range(len(vertices) - 1):
                    v1 = vertices[i].dxf.location
                    v2 = vertices[i + 1].dxf.location
                    segment_uzunluk = math.hypot(v2.x - v1.x, v2.y - v1.y)
                    uzunluk += segment_uzunluk
                
                # Birime göre metreye çevir
                if self.birim == "cm":
                    uzunluk = uzunluk / 100.0
                    logger.debug(f"POLYLINE: {uzunluk*100:.2f}cm -> {uzunluk:.4f}m")
                elif self.birim == "mm":
                    uzunluk = uzunluk / 1000.0
                    logger.debug(f"POLYLINE: {uzunluk*1000:.2f}mm -> {uzunluk:.4f}m")
                else:  # m veya başka bir değer - zaten metre kabul et
                    logger.debug(f"POLYLINE: {uzunluk:.4f}m (birim: {self.birim}, dönüşüm yok)")
                
                polyline_toplam += uzunluk
                parca_sayisi += 1
            except Exception as e:
                logger.warning(f"POLYLINE entity okuma hatası: {e}")
                continue
        
        if polyline_sayisi > 0:
            detay_bilgi.append(f"POLYLINE: {polyline_sayisi} adet, toplam: {polyline_toplam:.2f}m")
        toplam_uzunluk += polyline_toplam
        
        # LWPOLYLINE entity'lerini hesapla
        # NOT: İç içe kapalı LWPOLYLINE'lar varsa (duvar kalınlığı göstermek için), 
        # sadece en büyük olanı (dış duvar) kullanmalıyız
        lwpolyline_query = f'LWPOLYLINE[layer=="{katman_adi}"]'
        lwpolyline_entities = list(self.msp.query(lwpolyline_query))
        lwpolyline_sayisi = len(lwpolyline_entities)
        lwpolyline_toplam = 0.0
        
        # Kapalı ve açık LWPOLYLINE'ları ayır
        # İç içe olanları gruplamak için: (entity, uzunluk, merkez_nokta, alan) tuple'ları
        kapali_bilgiler = []  # İç içe duvarlar için: [(entity, uzunluk, merkez, alan), ...]
        acik_uzunluklar = []    # Açık çizgiler için
        
        for idx, entity in enumerate(lwpolyline_entities):
            try:
                # Kapalı mı kontrol et
                is_closed = getattr(entity, 'is_closed', False)
                logger.info(f"🔍 LWPOLYLINE #{idx+1}: is_closed={is_closed}")
                
                # Noktaları okumayı dene
                noktalar = None
                try:
                    with entity.points("xy") as pts:
                        noktalar = list(pts)
                        logger.info(f"✅ LWPOLYLINE #{idx+1} noktaları points() ile okundu: {len(noktalar)} nokta")
                        if len(noktalar) > 0:
                            logger.info(f"   İlk nokta: {noktalar[0]}, Son nokta: {noktalar[-1]}")
                except (AttributeError, TypeError) as e1:
                    logger.warning(f"⚠️ LWPOLYLINE #{idx+1} points() hatası: {e1}, alternatif yöntem deneniyor...")
                    try:
                        noktalar = [(v[0], v[1]) for v in entity.vertices]
                        logger.info(f"✅ LWPOLYLINE #{idx+1} noktaları vertices ile okundu: {len(noktalar)} nokta")
                        if len(noktalar) > 0:
                            logger.info(f"   İlk nokta: {noktalar[0]}, Son nokta: {noktalar[-1]}")
                    except Exception as e2:
                        logger.error(f"❌ LWPOLYLINE #{idx+1} nokta okuma hatası (hem points hem vertices): {e1}, {e2}")
                        continue
                
                if not noktalar or len(noktalar) < 2:
                    logger.warning(f"⚠️ LWPOLYLINE #{idx+1} yeterli nokta yok: {len(noktalar) if noktalar else 0} nokta (en az 2 gerekli)")
                    continue
                
                # Noktalar arası mesafeleri topla
                uzunluk = 0.0
                
                if is_closed:
                    # Kapalı poligon: tüm çevre uzunluğu
                    segment_sayisi = len(noktalar)  # Son nokta -> ilk nokta da dahil
                    logger.info(f"📏 LWPOLYLINE #{idx+1} (kapalı): {segment_sayisi} segment hesaplanıyor (çevre uzunluğu)...")
                    
                    for i in range(segment_sayisi):
                        p1 = noktalar[i]
                        p2 = noktalar[(i + 1) % len(noktalar)]  # Son nokta -> ilk nokta
                        segment_uzunluk = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                        uzunluk += segment_uzunluk
                        logger.info(f"   Segment {i+1}/{segment_sayisi}: {segment_uzunluk:.4f} (birim: {self.birim}) - P1: {p1}, P2: {p2}")
                else:
                    # Açık çizgi: başlangıç -> bitiş
                    segment_sayisi = len(noktalar) - 1
                    logger.info(f"📏 LWPOLYLINE #{idx+1} (açık): {segment_sayisi} segment hesaplanıyor...")
                    
                    for i in range(segment_sayisi):
                        p1 = noktalar[i]
                        p2 = noktalar[i + 1]
                        segment_uzunluk = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                        uzunluk += segment_uzunluk
                        logger.info(f"   Segment {i+1}/{segment_sayisi}: {segment_uzunluk:.4f} (birim: {self.birim}) - P1: {p1}, P2: {p2}")
                
                logger.info(f"📐 LWPOLYLINE #{idx+1} ham uzunluk: {uzunluk:.4f} (birim: {self.birim})")
                
                # Birime göre metreye çevir
                if self.birim == "cm":
                    uzunluk = uzunluk / 100.0  # cm -> m
                    durum = "kapalı" if is_closed else "açık"
                    logger.info(f"✅ LWPOLYLINE #{idx+1} ({durum}): {uzunluk*100:.2f}cm -> {uzunluk:.4f}m")
                elif self.birim == "mm":
                    uzunluk = uzunluk / 1000.0  # mm -> m
                    durum = "kapalı" if is_closed else "açık"
                    logger.info(f"✅ LWPOLYLINE #{idx+1} ({durum}): {uzunluk*1000:.2f}mm -> {uzunluk:.4f}m")
                else:  # m veya başka bir değer - zaten metre kabul et
                    durum = "kapalı" if is_closed else "açık"
                    logger.info(f"✅ LWPOLYLINE #{idx+1} ({durum}): {uzunluk:.4f}m (birim: {self.birim}, dönüşüm yok)")
                
                if uzunluk > 0:
                    if is_closed:
                        # Merkez noktayı ve alanı hesapla (iç içe olanları gruplamak için)
                        try:
                            # Merkez nokta (ağırlık merkezi)
                            merkez_x = sum(p[0] for p in noktalar) / len(noktalar)
                            merkez_y = sum(p[1] for p in noktalar) / len(noktalar)
                            merkez = (merkez_x, merkez_y)
                            
                            # Alan (iç içe olanları tespit etmek için)
                            alan = self._shoelace_formulu(noktalar)
                            if self.birim == "cm":
                                alan = alan / 10000.0  # cm² -> m²
                            elif self.birim == "mm":
                                alan = alan / 1000000.0  # mm² -> m²
                            
                            kapali_bilgiler.append((entity, uzunluk, merkez, alan))
                            logger.info(f"📝 LWPOLYLINE #{idx+1} (kapalı) bilgileri eklendi: uzunluk={uzunluk:.4f}m, alan={alan:.4f}m², merkez={merkez}")
                        except Exception as e:
                            logger.warning(f"⚠️ LWPOLYLINE #{idx+1} merkez/alan hesaplama hatası: {e}, sadece uzunluk kullanılıyor")
                            kapali_bilgiler.append((entity, uzunluk, None, None))
                    else:
                        acik_uzunluklar.append(uzunluk)
                        logger.info(f"📝 LWPOLYLINE #{idx+1} (açık) uzunluk listeye eklendi: {uzunluk:.4f}m")
                else:
                    logger.warning(f"⚠️ LWPOLYLINE #{idx+1} uzunluk 0, eklenmedi (ham uzunluk: {uzunluk:.4f})")
            except Exception as e:
                logger.error(f"❌ LWPOLYLINE entity okuma hatası: {e}", exc_info=True)
                continue
        
        # İç içe kapalı LWPOLYLINE'ları grupla ve her grubun en büyüğünü kullan
        if len(kapali_bilgiler) > 0:
            # İç içe olanları grupla (birbirine yakın merkez noktalara sahip olanlar = aynı duvar)
            gruplar = []
            kullanildi = set()
            
            for i, (entity1, uzunluk1, merkez1, alan1) in enumerate(kapali_bilgiler):
                if i in kullanildi:
                    continue
                
                # Yeni grup oluştur
                grup = [(entity1, uzunluk1, merkez1, alan1)]
                kullanildi.add(i)
                
                # Bu gruba yakın olanları bul
                if merkez1:
                    for j, (entity2, uzunluk2, merkez2, alan2) in enumerate(kapali_bilgiler):
                        if j in kullanildi or not merkez2:
                            continue
                        
                        # Merkez noktalar arası mesafe
                        mesafe = math.hypot(merkez2[0] - merkez1[0], merkez2[1] - merkez1[1])
                        # Birime göre tolerans (1m içinde = aynı duvar)
                        tolerans = 1.0 if self.birim == 'm' else (100.0 if self.birim == 'cm' else 1000.0)
                        
                        # Veya alan kontrolü: bir alan diğerinin içindeyse (alan farkı küçükse)
                        if mesafe <= tolerans or (alan1 and alan2 and abs(alan1 - alan2) / max(alan1, alan2) < 0.1):
                            grup.append((entity2, uzunluk2, merkez2, alan2))
                            kullanildi.add(j)
                            logger.info(f"🔗 LWPOLYLINE #{i+1} ve #{j+1} aynı gruba eklendi (mesafe: {mesafe:.4f}, alan farkı: {abs(alan1 - alan2) if alan1 and alan2 else 'N/A'})")
                
                gruplar.append(grup)
            
            # Her grubun en büyük uzunluğunu kullan (dış duvar)
            for grup_idx, grup in enumerate(gruplar):
                if len(grup) > 1:
                    # İç içe duvarlar: sadece en büyük olanı kullan
                    en_buyuk = max(grup, key=lambda x: x[1])  # Uzunluğa göre
                    lwpolyline_toplam += en_buyuk[1]
                    parca_sayisi += 1
                    logger.info(f"📦 Grup #{grup_idx+1}: {len(grup)} adet iç içe LWPOLYLINE bulundu (kalınlık göstermek için)")
                    logger.info(f"   ✅ Sadece en büyük olanı (dış duvar) kullanılıyor: {en_buyuk[1]:.4f}m")
                    logger.info(f"   ⏭️ Diğer uzunluklar atlandı: {[f'{u:.4f}m' for _, u, _, _ in grup if u != en_buyuk[1]]}")
                else:
                    # Tek başına duvar
                    lwpolyline_toplam += grup[0][1]
                    parca_sayisi += 1
                    logger.info(f"✅ Grup #{grup_idx+1}: Tek LWPOLYLINE uzunluğu: {grup[0][1]:.4f}m")
        
        # Açık LWPOLYLINE'ları ekle
        for acik_uzunluk in acik_uzunluklar:
            lwpolyline_toplam += acik_uzunluk
            parca_sayisi += 1
            logger.info(f"✅ Açık LWPOLYLINE uzunluğu eklendi: {acik_uzunluk:.4f}m (toplam: {lwpolyline_toplam:.4f}m)")
        
        if lwpolyline_sayisi > 0:
            kapali_sayisi = len(kapali_bilgiler)
            acik_sayisi = len(acik_uzunluklar)
            if kapali_sayisi > 1:
                # Grup sayısını hesapla
                gruplar_sayisi = len([g for g in [kapali_bilgiler] if len(g) > 0])  # Basitleştirilmiş
                detay_bilgi.append(f"LWPOLYLINE: {lwpolyline_sayisi} adet ({kapali_sayisi} kapalı, iç içe olanlar gruplandı; {acik_sayisi} açık), toplam: {lwpolyline_toplam:.2f}m")
            elif kapali_sayisi > 0 and acik_sayisi > 0:
                detay_bilgi.append(f"LWPOLYLINE: {lwpolyline_sayisi} adet ({kapali_sayisi} kapalı, {acik_sayisi} açık), toplam: {lwpolyline_toplam:.2f}m")
            elif kapali_sayisi > 0:
                detay_bilgi.append(f"LWPOLYLINE: {lwpolyline_sayisi} adet (kapalı), toplam: {lwpolyline_toplam:.2f}m")
            else:
                detay_bilgi.append(f"LWPOLYLINE: {lwpolyline_sayisi} adet (açık), toplam: {lwpolyline_toplam:.2f}m")
        toplam_uzunluk += lwpolyline_toplam
        
        # ARC entity'lerini hesapla (yay çizgileri)
        arc_query = f'ARC[layer=="{katman_adi}"]'
        arc_entities = list(self.msp.query(arc_query))
        arc_sayisi = len(arc_entities)
        arc_toplam = 0.0
        
        for entity in arc_entities:
            try:
                radius = entity.dxf.radius
                start_angle = math.radians(entity.dxf.start_angle)
                end_angle = math.radians(entity.dxf.end_angle)
                
                # Yay açısını hesapla
                angle_diff = abs(end_angle - start_angle)
                if angle_diff > math.pi:
                    angle_diff = 2 * math.pi - angle_diff
                
                # Yay uzunluğu = radius × açı (radyan)
                uzunluk = radius * angle_diff
                
                # Birime göre metreye çevir
                if self.birim == "cm":
                    uzunluk = uzunluk / 100.0
                    logger.debug(f"ARC: {uzunluk*100:.2f}cm -> {uzunluk:.4f}m")
                elif self.birim == "mm":
                    uzunluk = uzunluk / 1000.0
                    logger.debug(f"ARC: {uzunluk*1000:.2f}mm -> {uzunluk:.4f}m")
                else:  # m veya başka bir değer - zaten metre kabul et
                    logger.debug(f"ARC: {uzunluk:.4f}m (birim: {self.birim}, dönüşüm yok)")
                
                arc_toplam += uzunluk
                parca_sayisi += 1
            except Exception as e:
                logger.warning(f"ARC entity okuma hatası: {e}")
                continue
        
        if arc_sayisi > 0:
            detay_bilgi.append(f"ARC: {arc_sayisi} adet, toplam: {arc_toplam:.2f}m")
        toplam_uzunluk += arc_toplam
        
        # MLINE entity'lerini hesapla (MultiLine - AutoCAD MLINE komutu)
        mline_query = f'MLINE[layer=="{katman_adi}"]'
        mline_entities = list(self.msp.query(mline_query))
        mline_sayisi = len(mline_entities)
        mline_toplam = 0.0
        
        for entity in mline_entities:
            try:
                uzunluk = 0.0
                # MLINE vertex'lerini al
                vertices = list(entity.vertices)
                if len(vertices) < 2:
                    continue
                
                # Her vertex'teki merkez noktayı kullan (MLINE çoklu çizgi olduğu için)
                for i in range(len(vertices) - 1):
                    v1 = vertices[i].dxf.location  # Merkez nokta
                    v2 = vertices[i + 1].dxf.location
                    segment_uzunluk = math.hypot(v2.x - v1.x, v2.y - v1.y)
                    uzunluk += segment_uzunluk
                
                # Birime göre metreye çevir
                if self.birim == "cm":
                    uzunluk = uzunluk / 100.0
                    logger.debug(f"MLINE: {uzunluk*100:.2f}cm -> {uzunluk:.4f}m")
                elif self.birim == "mm":
                    uzunluk = uzunluk / 1000.0
                    logger.debug(f"MLINE: {uzunluk*1000:.2f}mm -> {uzunluk:.4f}m")
                else:  # m veya başka bir değer - zaten metre kabul et
                    logger.debug(f"MLINE: {uzunluk:.4f}m (birim: {self.birim}, dönüşüm yok)")
                
                mline_toplam += uzunluk
                parca_sayisi += 1
            except Exception as e:
                logger.warning(f"MLINE entity okuma hatası: {e}")
                # Alternatif yöntem dene: geometry kullan
                try:
                    # MLINE'ın geometry'sini al
                    if hasattr(entity, 'flattening'):
                        points = list(entity.flattening(distance=0.01))
                        if len(points) >= 2:
                            uzunluk = 0.0
                            for i in range(len(points) - 1):
                                p1 = points[i]
                                p2 = points[i + 1]
                                segment_uzunluk = math.hypot(p2.x - p1.x, p2.y - p1.y)
                                uzunluk += segment_uzunluk
                            
                            # Birime göre metreye çevir
                            if self.birim == "cm":
                                uzunluk = uzunluk / 100.0
                            elif self.birim == "mm":
                                uzunluk = uzunluk / 1000.0
                            
                            mline_toplam += uzunluk
                            parca_sayisi += 1
                            logger.debug(f"MLINE (alternatif yöntem): {uzunluk:.4f}m")
                except Exception as e2:
                    logger.warning(f"MLINE alternatif okuma hatası: {e2}")
                continue
        
        if mline_sayisi > 0:
            detay_bilgi.append(f"MLINE: {mline_sayisi} adet, toplam: {mline_toplam:.2f}m")
        toplam_uzunluk += mline_toplam
        
        # Debug: Toplam uzunluğu logla
        logger.info(f"=== Uzunluk Hesaplama Özeti (Katman: {katman_adi}) ===")
        logger.info(f"Çizim birimi: {self.birim}")
        logger.info(f"LINE toplam: {line_toplam:.4f}m ({line_sayisi} adet)")
        logger.info(f"POLYLINE toplam: {polyline_toplam:.4f}m ({polyline_sayisi} adet)")
        logger.info(f"LWPOLYLINE (açık) toplam: {lwpolyline_toplam:.4f}m ({lwpolyline_sayisi} adet)")
        logger.info(f"ARC toplam: {arc_toplam:.4f}m ({arc_sayisi} adet)")
        logger.info(f"MLINE toplam: {mline_toplam:.4f}m ({mline_sayisi} adet)")
        logger.info(f"TOPLAM UZUNLUK: {toplam_uzunluk:.4f}m ({parca_sayisi} parça)")
        
        not_mesaji = f"{parca_sayisi} çizgi parçası bulundu"
        if detay_bilgi:
            not_mesaji += f" ({'; '.join(detay_bilgi)})"
        
        return {
            "katman": katman_adi,
            "toplam_miktar": round(toplam_uzunluk, 2),
            "birim": "m",
            "parca_sayisi": parca_sayisi,
            "not": not_mesaji,
            "detay": detay_bilgi
        }
    
    def _shoelace_formulu(self, points: List[Tuple[float, float]]) -> float:
        """
        Koordinatları bilinen çokgenin alanını hesaplayan matematiksel formül.
        
        Args:
            points: (x, y) koordinat çiftleri listesi
            
        Returns:
            float: Hesaplanan alan (çizim birimi cinsinden)
        """
        n = len(points)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        return abs(area) / 2.0
    
    def _birim_cevir(self, alan_degeri: float) -> float:
        """
        Çizim biriminden m²'ye dönüşüm yapar.
        
        Args:
            alan_degeri: Çizim birimi cinsinden alan değeri
            
        Returns:
            float: m² cinsinden alan değeri
        """
        if self.birim == "m":
            return alan_degeri  # Zaten m²
        # Eğer birim CM ise, çıkan devasa sayıyı 10.000'e bölüp m2 yaparız.
        elif self.birim == "cm":
            return alan_degeri / 10000.0  # cm² -> m² (100x100 = 10000)
        elif self.birim == "mm":
            return alan_degeri / 1000000.0  # mm² -> m² (1000x1000 = 1000000)
        return alan_degeri
    
    def duvar_yuksekligi_tahmin_et(self, katman_adi: str, db_manager=None) -> Optional[Dict[str, Any]]:
        """
        Katman adından duvar yüksekliğini, kalınlığını ve cinsini tahmin et.
        
        Öncelik sırası:
        1. Öğrenme veritabanından (kullanıcı düzeltmeleri)
        2. Katman isminden pattern matching (örn: "DIS_DUVAR_280cm" -> 2.80m)
        3. Text entity'lerinden okuma
        4. Varsayılan değer (2.80m)
        
        Args:
            katman_adi: Katman adı
            db_manager: DatabaseManager instance (opsiyonel)
            
        Returns:
            Dict: {'yukseklik': float, 'birim': str, 'kaynak': str, 'kalinlik': float (cm), 'cins': str} veya None
        """
        result = {
            'yukseklik': None,
            'birim': 'm',
            'kaynak': 'varsayilan',
            'katman_adi': katman_adi,
            'kalinlik': None,
            'cins': None
        }
        
        # 1. Öğrenme veritabanından kontrol et (en yüksek öncelik)
        if db_manager:
            try:
                learning = db_manager.get_ai_learning(katman_adi)
                if learning:
                    yukseklik = learning['duvar_yuksekligi']
                    birim = learning.get('birim', 'm')
                    # Birimi metreye çevir
                    if birim == 'cm':
                        yukseklik = yukseklik / 100.0
                    elif birim == 'mm':
                        yukseklik = yukseklik / 1000.0
                    
                    result['yukseklik'] = yukseklik
                    result['kaynak'] = 'ogrenme_veritabani'
                    result['kalinlik'] = learning.get('duvar_kalinligi')
                    result['cins'] = learning.get('duvar_cinsi')
                    
                    if result['yukseklik']:
                        return result
            except Exception as e:
                logger.warning(f"Öğrenme veritabanı okuma hatası: {e}")
        
        # 2. Katman isminden pattern matching
        yukseklik = self._katman_isminden_yukseklik_cikar(katman_adi)
        if yukseklik:
            result['yukseklik'] = yukseklik
            result['kaynak'] = 'katman_ismi'
        
        # 3. Text entity'lerinden okuma (yükseklik, kalınlık, cins)
        text_yukseklik = self._text_entitylerinden_yukseklik_oku(katman_adi)
        if text_yukseklik:
            result['yukseklik'] = text_yukseklik
            result['kaynak'] = 'text_entity'
        
        # Text entity'lerden kalınlık ve cins bilgisini al
        text_bilgisi = self._text_entitylerinden_duvar_bilgisi_oku(katman_adi)
        if text_bilgisi.get('kalinlik'):
            result['kalinlik'] = text_bilgisi['kalinlik']
            if result['kaynak'] == 'varsayilan':
                result['kaynak'] = 'text_entity'
        if text_bilgisi.get('cins'):
            result['cins'] = text_bilgisi['cins']
            if result['kaynak'] == 'varsayilan':
                result['kaynak'] = 'text_entity'
        
        # 4. Varsayılan değer (2.80m - standart kat yüksekliği)
        if not result['yukseklik']:
            result['yukseklik'] = 2.80
            result['kaynak'] = 'varsayilan'
        
        return result
    
    def _katman_isminden_yukseklik_cikar(self, katman_adi: str) -> Optional[float]:
        """
        Katman isminden duvar yüksekliğini çıkar.
        
        Örnek pattern'ler:
        - "DIS_DUVAR_280cm" -> 2.80m
        - "DIS_DUVAR_2.80m" -> 2.80m
        - "DIS_DUVAR_280" -> 2.80m (cm varsayılır)
        - "DUVAR_280" -> 2.80m
        
        Args:
            katman_adi: Katman adı
            
        Returns:
            float: Metre cinsinden yükseklik veya None
        """
        if not katman_adi:
            return None
        
        katman_adi_upper = katman_adi.upper()
        
        # Pattern 1: "280cm", "2.80m" gibi açık birim belirtilmiş
        patterns = [
            r'(\d+\.?\d*)\s*CM',  # 280cm, 2.80cm
            r'(\d+\.?\d*)\s*M',   # 2.80m, 280m
            r'(\d+\.?\d*)\s*MM',  # 2800mm
        ]
        
        for pattern in patterns:
            match = re.search(pattern, katman_adi_upper)
            if match:
                deger = float(match.group(1))
                # Birime göre metreye çevir
                if 'CM' in pattern:
                    return deger / 100.0  # cm -> m
                elif 'MM' in pattern:
                    return deger / 1000.0  # mm -> m
                else:
                    return deger  # zaten metre
        
        # Pattern 2: Sadece sayı var, cm varsayılır (örn: "DIS_DUVAR_280")
        # 3-4 haneli sayılar cm olarak yorumlanır (100-9999cm = 1-99.99m)
        number_match = re.search(r'(\d{3,4})', katman_adi_upper)
        if number_match:
            deger = int(number_match.group(1))
            # 100-9999 arası ise cm olarak yorumla
            if 100 <= deger <= 9999:
                return deger / 100.0  # cm -> m
        
        return None
    
    def _text_entitylerinden_yukseklik_oku(self, katman_adi: str) -> Optional[float]:
        """
        Katman içindeki text entity'lerinden duvar yüksekliğini oku.
        
        Args:
            katman_adi: Katman adı
            
        Returns:
            float: Metre cinsinden yükseklik veya None
        """
        if not self.msp:
            return None
        
        try:
            # Katman içindeki tüm text entity'leri al
            text_query = f'TEXT[layer=="{katman_adi}"]'
            text_entities = self.msp.query(text_query)
            
            # MTEXT entity'leri de kontrol et
            mtext_query = f'MTEXT[layer=="{katman_adi}"]'
            mtext_entities = self.msp.query(mtext_query)
            
            all_texts = list(text_entities) + list(mtext_entities)
            
            # Yükseklik ile ilgili anahtar kelimeler
            keywords = ['yükseklik', 'yukseklik', 'yük', 'yuk', 'height', 'h=', 'h =']
            
            for entity in all_texts:
                try:
                    # Text içeriğini al
                    if hasattr(entity, 'dxf'):
                        text_content = entity.dxf.text if hasattr(entity.dxf, 'text') else ''
                    else:
                        text_content = str(entity)
                    
                    text_upper = text_content.upper()
                    logger.debug(f"Text entity okunuyor: '{text_content}' (katman: {katman_adi})")
                    
                    # Anahtar kelime var mı kontrol et
                    for keyword in keywords:
                        if keyword.upper() in text_upper:
                            # Sayıyı çıkar
                            # Pattern: "yükseklik: 2.80m" veya "h=280cm"
                            number_patterns = [
                                r'(\d+\.?\d*)\s*CM',
                                r'(\d+\.?\d*)\s*M',
                                r'(\d+\.?\d*)\s*MM',
                                r'(\d+\.?\d*)',  # Sadece sayı
                            ]
                            
                            for pattern in number_patterns:
                                match = re.search(pattern, text_upper)
                                if match:
                                    deger = float(match.group(1))
                                    # Birime göre metreye çevir
                                    if 'CM' in pattern:
                                        result = deger / 100.0
                                        logger.info(f"✅ Text'ten yükseklik bulundu: {deger}cm = {result}m")
                                        return result
                                    elif 'MM' in pattern:
                                        result = deger / 1000.0
                                        logger.info(f"✅ Text'ten yükseklik bulundu: {deger}mm = {result}m")
                                        return result
                                    elif 'M' in pattern:
                                        logger.info(f"✅ Text'ten yükseklik bulundu: {deger}m")
                                        return deger
                                    else:
                                        # Sadece sayı varsa, 100-9999 arası ise cm varsay
                                        if 100 <= deger <= 9999:
                                            result = deger / 100.0
                                            logger.info(f"✅ Text'ten yükseklik bulundu (cm varsayıldı): {deger} = {result}m")
                                            return result
                except Exception as e:
                    logger.debug(f"Text entity işleme hatası: {e}")
                    continue
            
            return None
        except Exception as e:
            logger.warning(f"Text entity okuma hatası: {e}")
            return None
    
    def _text_entitylerinden_duvar_bilgisi_oku(self, katman_adi: str) -> Dict[str, Any]:
        """
        Katman içindeki text entity'lerinden duvar kalınlığı ve cinsini oku.
        
        Args:
            katman_adi: Katman adı
            
        Returns:
            Dict: {'kalinlik': float (cm), 'cins': str} veya boş dict
        """
        if not self.msp:
            return {}
        
        result = {}
        
        try:
            # Tüm katmanlardaki text entity'leri kontrol et (duvar katmanına yakın olabilir)
            # Önce aynı katmandaki text'leri kontrol et
            text_query = f'TEXT[layer=="{katman_adi}"]'
            text_entities = list(self.msp.query(text_query))
            
            # MTEXT entity'leri de kontrol et
            mtext_query = f'MTEXT[layer=="{katman_adi}"]'
            mtext_entities = list(self.msp.query(mtext_query))
            
            # Ayrıca tüm text entity'leri kontrol et (duvar katmanına yakın olabilir)
            all_text_query = 'TEXT'
            all_mtext_query = 'MTEXT'
            all_texts = list(self.msp.query(all_text_query)) + list(self.msp.query(all_mtext_query))
            
            # Duvar katmanındaki çizgilerin konumunu al (yakın text'leri bulmak için)
            duvar_entities = list(self.msp.query(f'LWPOLYLINE[layer=="{katman_adi}"]'))
            duvar_entities += list(self.msp.query(f'LINE[layer=="{katman_adi}"]'))
            duvar_entities += list(self.msp.query(f'MLINE[layer=="{katman_adi}"]'))
            
            # Duvar çizgilerinin orta noktalarını hesapla
            duvar_orta_noktalari = []
            for entity in duvar_entities:
                try:
                    if hasattr(entity, 'points'):
                        with entity.points("xy") as pts:
                            noktalar = list(pts)
                    elif hasattr(entity, 'vertices'):
                        noktalar = [(v[0], v[1]) for v in entity.vertices]
                    else:
                        continue
                    
                    if len(noktalar) > 0:
                        # Orta noktayı hesapla
                        orta_x = sum(p[0] for p in noktalar) / len(noktalar)
                        orta_y = sum(p[1] for p in noktalar) / len(noktalar)
                        duvar_orta_noktalari.append((orta_x, orta_y))
                except:
                    continue
            
            # Kalınlık ile ilgili anahtar kelimeler
            kalinlik_keywords = ['kalınlık', 'kalinlik', 'kalın', 'kalin', 'thickness', 't=', 't =', 'cm', 'mm']
            # Duvar cinsi ile ilgili anahtar kelimeler
            cins_keywords = ['tuğla', 'tugla', 'beton', 'gazbeton', 'bims', 'ahşap', 'ahsap', 'çelik', 'celik', 
                           'brick', 'concrete', 'aerated', 'wood', 'steel']
            
            # Önce aynı katmandaki text'leri kontrol et
            for entity in text_entities + mtext_entities:
                try:
                    if hasattr(entity, 'dxf'):
                        text_content = entity.dxf.text if hasattr(entity.dxf, 'text') else ''
                    else:
                        text_content = str(entity)
                    
                    text_upper = text_content.upper()
                    logger.debug(f"Text entity okunuyor (kalınlık/cins): '{text_content}' (katman: {katman_adi})")
                    
                    # Kalınlık kontrolü
                    if not result.get('kalinlik'):
                        for keyword in kalinlik_keywords:
                            if keyword.upper() in text_upper:
                                # Sayıyı çıkar (cm veya mm olabilir)
                                number_patterns = [
                                    r'(\d+\.?\d*)\s*CM',
                                    r'(\d+\.?\d*)\s*MM',
                                    r'(\d+\.?\d*)',  # Sadece sayı
                                ]
                                
                                for pattern in number_patterns:
                                    match = re.search(pattern, text_upper)
                                    if match:
                                        deger = float(match.group(1))
                                        # MM ise cm'ye çevir
                                        if 'MM' in pattern:
                                            deger = deger / 10.0  # mm -> cm
                                        result['kalinlik'] = deger
                                        logger.info(f"✅ Text'ten kalınlık bulundu: {deger}cm")
                                        break
                    
                    # Duvar cinsi kontrolü
                    if not result.get('cins'):
                        for keyword in cins_keywords:
                            if keyword.upper() in text_upper:
                                # Cins bilgisini çıkar
                                for cins_option in ['tuğla', 'tugla', 'beton', 'gazbeton', 'bims', 'ahşap', 'ahsap', 'çelik', 'celik']:
                                    if cins_option.upper() in text_upper:
                                        result['cins'] = cins_option.title()
                                        logger.info(f"✅ Text'ten duvar cinsi bulundu: {result['cins']}")
                                        break
                except Exception as e:
                    logger.debug(f"Text entity işleme hatası: {e}")
                    continue
            
            # Eğer bulunamadıysa, yakın text'leri kontrol et
            if not result.get('kalinlik') or not result.get('cins'):
                for entity in all_texts:
                    try:
                        # Text'in konumunu al
                        if hasattr(entity, 'dxf'):
                            text_pos = (entity.dxf.insert.x, entity.dxf.insert.y) if hasattr(entity.dxf, 'insert') else None
                            text_content = entity.dxf.text if hasattr(entity.dxf, 'text') else ''
                        else:
                            text_pos = None
                            text_content = str(entity)
                        
                        # Duvar çizgilerine yakın mı kontrol et (50 birim içinde)
                        if text_pos and duvar_orta_noktalari:
                            yakın_mı = False
                            for duvar_orta in duvar_orta_noktalari:
                                mesafe = math.hypot(text_pos[0] - duvar_orta[0], text_pos[1] - duvar_orta[1])
                                # Birime göre tolerans (50m, 5000cm, 50000mm)
                                tolerans = 50.0 if self.birim == 'm' else (5000.0 if self.birim == 'cm' else 50000.0)
                                if mesafe <= tolerans:
                                    yakın_mı = True
                                    break
                            
                            if not yakın_mı:
                                continue
                        
                        text_upper = text_content.upper()
                        
                        # Kalınlık kontrolü
                        if not result.get('kalinlik'):
                            for keyword in kalinlik_keywords:
                                if keyword.upper() in text_upper:
                                    number_patterns = [
                                        r'(\d+\.?\d*)\s*CM',
                                        r'(\d+\.?\d*)\s*MM',
                                        r'(\d+\.?\d*)',
                                    ]
                                    
                                    for pattern in number_patterns:
                                        match = re.search(pattern, text_upper)
                                        if match:
                                            deger = float(match.group(1))
                                            if 'MM' in pattern:
                                                deger = deger / 10.0
                                            result['kalinlik'] = deger
                                            logger.info(f"✅ Yakın text'ten kalınlık bulundu: {deger}cm")
                                            break
                        
                        # Duvar cinsi kontrolü
                        if not result.get('cins'):
                            for keyword in cins_keywords:
                                if keyword.upper() in text_upper:
                                    for cins_option in ['tuğla', 'tugla', 'beton', 'gazbeton', 'bims', 'ahşap', 'ahsap', 'çelik', 'celik']:
                                        if cins_option.upper() in text_upper:
                                            result['cins'] = cins_option.title()
                                            logger.info(f"✅ Yakın text'ten duvar cinsi bulundu: {result['cins']}")
                                            break
                    except Exception as e:
                        logger.debug(f"Yakın text entity işleme hatası: {e}")
                        continue
            
            return result
        except Exception as e:
            logger.warning(f"Text entity okuma hatası (kalınlık/cins): {e}")
            return {}

    def oda_isimlerini_oku(self, oda_ismi_layer: str = "A_ODA_ISMI", hesap_siniri_layer: str = "HESAP_SINIRI") -> List[Dict[str, Any]]:
        """
        DXF dosyasından oda isimlerini okur.

        Mimarın belirlediği layer'daki TEXT ve MTEXT entity'lerini okur.
        Opsiyonel olarak HESAP_SINIRI layer'ı ile sınırlandırılabilir.

        Args:
            oda_ismi_layer: Oda isimlerinin bulunduğu layer adı (varsayılan: "A_ODA_ISMI")
            hesap_siniri_layer: Hesap sınırı polyline'ının bulunduğu layer (varsayılan: "HESAP_SINIRI")

        Returns:
            List[Dict]: Her oda için {"text": str, "x": float, "y": float} bilgisi içeren liste
        """
        if not self.msp:
            logger.warning("DXF dosyası yüklenmemiş!")
            return []

        logger.info(f"📄 Oda isimleri okunuyor - Layer: {oda_ismi_layer}")

        # 1. SINIR KUTUSU (Varsa okur, yoksa geçer)
        hesap_kutusu = None
        if SHAPELY_AVAILABLE:
            try:
                sinir_poly = self.msp.query(f'LWPOLYLINE[layer=="{hesap_siniri_layer}"]')
                sinir_list = list(sinir_poly)
                if sinir_list:
                    with sinir_list[0].points("xy") as pts:
                        noktalar = list(pts)
                    x_coords = [p[0] for p in noktalar]
                    y_coords = [p[1] for p in noktalar]
                    hesap_kutusu = box(min(x_coords), min(y_coords), max(x_coords), max(y_coords))
                    logger.info(f"✅ Hesap sınırı bulundu: {min(x_coords):.2f}, {min(y_coords):.2f} -> {max(x_coords):.2f}, {max(y_coords):.2f}")
            except Exception as e:
                logger.warning(f"Hesap sınırı okuma hatası: {e}")

        oda_isimleri = []

        # 2. YAZILARI TOPLA (TEXT ve MTEXT)
        for entity in self.msp.query('TEXT MTEXT'):
            try:
                if entity.dxf.layer != oda_ismi_layer:
                    continue

                # Yazı İçeriği
                if entity.dxftype() == 'TEXT':
                    text = entity.dxf.text
                else:
                    # MTEXT için
                    text = entity.text if hasattr(entity, 'text') else entity.dxf.text

                # Konum
                insert = entity.dxf.insert

                # Sınır Kontrolü
                if hesap_kutusu:
                    bounds = hesap_kutusu.bounds
                    if not (bounds[0] <= insert.x <= bounds[2] and
                            bounds[1] <= insert.y <= bounds[3]):
                        continue

                if text and text.strip():
                    # MTEXT formatlarını temizle (örn: {\fArial;ODA ADI} -> ODA ADI)
                    clean_text = re.sub(r'\\[A-Za-z][^;]*;', '', text)
                    clean_text = re.sub(r'[{}\\]', '', clean_text)
                    clean_text = clean_text.strip()

                    if clean_text:
                        oda_isimleri.append({
                            "text": clean_text,
                            "x": insert.x,
                            "y": insert.y
                        })
                        logger.info(f"  -> Bulundu: {clean_text} ({insert.x:.2f}, {insert.y:.2f})")
            except Exception as e:
                logger.warning(f"Entity okuma hatası: {e}")
                continue

        if not oda_isimleri:
            logger.warning(f"⚠️ '{oda_ismi_layer}' layer'ında hiçbir oda ismi bulunamadı!")
        else:
            logger.info(f"📊 Toplam {len(oda_isimleri)} oda ismi bulundu")

        return oda_isimleri

    def kat_isimlerini_oku(self, kat_ismi_layer: str = "A_KAT_ISMI", hesap_siniri_layer: str = "HESAP_SINIRI") -> List[Dict[str, Any]]:
        """
        DXF dosyasından kat isimlerini okur.

        Mimarın belirlediği layer'daki TEXT ve MTEXT entity'lerini okur.
        Opsiyonel olarak HESAP_SINIRI layer'ı ile sınırlandırılabilir.

        Args:
            kat_ismi_layer: Kat isimlerinin bulunduğu layer adı (varsayılan: "A_KAT_ISMI")
            hesap_siniri_layer: Hesap sınırı polyline'ının bulunduğu layer (varsayılan: "HESAP_SINIRI")

        Returns:
            List[Dict]: Her kat için {"text": str, "x": float, "y": float} bilgisi içeren liste
        """
        if not self.msp:
            logger.warning("DXF dosyası yüklenmemiş!")
            return []

        logger.info(f"📄 Kat isimleri okunuyor - Layer: {kat_ismi_layer}")

        # 1. SINIR KUTUSU (Varsa okur, yoksa geçer)
        hesap_kutusu = None
        if SHAPELY_AVAILABLE:
            try:
                sinir_poly = self.msp.query(f'LWPOLYLINE[layer=="{hesap_siniri_layer}"]')
                sinir_list = list(sinir_poly)
                if sinir_list:
                    with sinir_list[0].points("xy") as pts:
                        noktalar = list(pts)
                    x_coords = [p[0] for p in noktalar]
                    y_coords = [p[1] for p in noktalar]
                    hesap_kutusu = box(min(x_coords), min(y_coords), max(x_coords), max(y_coords))
                    logger.info(f"✅ Hesap sınırı bulundu")
            except Exception as e:
                logger.warning(f"Hesap sınırı okuma hatası: {e}")

        kat_isimleri = []

        # 2. YAZILARI TOPLA (TEXT ve MTEXT)
        for entity in self.msp.query('TEXT MTEXT'):
            try:
                if entity.dxf.layer != kat_ismi_layer:
                    continue

                # Yazı İçeriği
                if entity.dxftype() == 'TEXT':
                    text = entity.dxf.text
                else:
                    text = entity.text if hasattr(entity, 'text') else entity.dxf.text

                # Konum
                insert = entity.dxf.insert

                # Sınır Kontrolü
                if hesap_kutusu:
                    bounds = hesap_kutusu.bounds
                    if not (bounds[0] <= insert.x <= bounds[2] and
                            bounds[1] <= insert.y <= bounds[3]):
                        continue

                if text and text.strip():
                    # MTEXT formatlarını temizle
                    clean_text = re.sub(r'\\[A-Za-z][^;]*;', '', text)
                    clean_text = re.sub(r'[{}\\]', '', clean_text)
                    clean_text = clean_text.strip()

                    if clean_text:
                        kat_isimleri.append({
                            "text": clean_text,
                            "x": insert.x,
                            "y": insert.y
                        })
                        logger.info(f"  -> Kat bulundu: {clean_text} ({insert.x:.2f}, {insert.y:.2f})")
            except Exception as e:
                logger.warning(f"Entity okuma hatası: {e}")
                continue

        if not kat_isimleri:
            logger.warning(f"⚠️ '{kat_ismi_layer}' layer'ında hiçbir kat ismi bulunamadı!")
        else:
            logger.info(f"📊 Toplam {len(kat_isimleri)} kat ismi bulundu")

        return kat_isimleri

    def proje_kimligini_oku(self, oda_layer: str = "A_ODA_ISMI", kat_layer: str = "A_KAT_ISMI",
                           hesap_siniri_layer: str = "HESAP_SINIRI") -> Dict[str, Any]:
        """
        DXF dosyasından proje kimliğini okur (oda ve kat isimleri).

        Args:
            oda_layer: Oda isimlerinin bulunduğu layer
            kat_layer: Kat isimlerinin bulunduğu layer
            hesap_siniri_layer: Hesap sınırı layer'ı

        Returns:
            Dict: {
                "odalar": List[Dict],
                "katlar": List[Dict],
                "hesap_siniri": Optional[Tuple] (min_x, min_y, max_x, max_y)
            }
        """
        hesap_siniri = None

        # Hesap sınırını al
        if SHAPELY_AVAILABLE and self.msp:
            try:
                sinir_poly = self.msp.query(f'LWPOLYLINE[layer=="{hesap_siniri_layer}"]')
                sinir_list = list(sinir_poly)
                if sinir_list:
                    with sinir_list[0].points("xy") as pts:
                        noktalar = list(pts)
                    x_coords = [p[0] for p in noktalar]
                    y_coords = [p[1] for p in noktalar]
                    hesap_siniri = (min(x_coords), min(y_coords), max(x_coords), max(y_coords))
            except:
                pass

        return {
            "odalar": self.oda_isimlerini_oku(oda_layer, hesap_siniri_layer),
            "katlar": self.kat_isimlerini_oku(kat_layer, hesap_siniri_layer),
            "hesap_siniri": hesap_siniri
        }

    def tum_text_layerlarini_listele(self) -> List[str]:
        """
        DXF dosyasındaki TEXT ve MTEXT entity'lerinin bulunduğu tüm layer'ları listeler.

        Returns:
            List[str]: TEXT veya MTEXT içeren layer adları
        """
        if not self.msp:
            return []

        text_layers = set()
        for entity in self.msp.query('TEXT MTEXT'):
            try:
                text_layers.add(entity.dxf.layer)
            except:
                continue

        return sorted(list(text_layers))


# --- TEST ALANI (Sadece bu dosya çalıştırıldığında devreye girer) ---
if __name__ == "__main__":
    # Test etmek için projenin olduğu klasöre bir .dxf dosyası at ve ismini buraya yaz
    test_dosyasi = "ornek_proje.dxf"
    
    # Dosya varsa testi başlat (Hata almamak için try-except bloğu dışına aldım örnekte)
    # motor = DXFAnaliz(test_dosyasi)
    
    # 1. Mevcut katmanları gör
    # print("Katmanlar:", motor.katmanlari_listele())
    
    # 2. Örnek Alan Hesabı (Örn: 'MIMARI_PARKE' katmanı)
    # print(motor.alan_hesapla("MIMARI_PARKE"))
    
    # 3. Örnek Sayım (Örn: 'KAPI' katmanı)
    # print(motor.blok_say("KAPI", moda_gore="katman"))
    
    print("Sınıf hazır. Başka bir dosyadan import edilebilir.")

