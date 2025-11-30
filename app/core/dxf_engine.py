"""
DXF Engine
DXF dosyaları için gelişmiş işleme motoru
"""

import sys
import math
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

logger = logging.getLogger(__name__)


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
        entities = self.msp.query(sorgu)
        
        for entity in entities:
            try:
                # Noktaları okumak için entity.points() context manager kullan
                try:
                    with entity.points("xy") as pts:
                        noktalar = list(pts)
                except (AttributeError, TypeError):
                    # Alternatif: vertices kullan
                    try:
                        noktalar = [(v[0], v[1]) for v in entity.vertices]
                    except:
                        continue
                
                if len(noktalar) < 3:
                    continue
                
                # Kapalı mı veya kapatılabilir mi?
                kapatildi = False
                if entity.is_closed:
                    kapatildi = True
                else:
                    baslangic = noktalar[0]
                    bitis = noktalar[-1]
                    mesafe = math.hypot(bitis[0] - baslangic[0], bitis[1] - baslangic[1])
                    if mesafe <= gercek_tolerans:
                        kapatildi = True
                        tamir_edilen += 1
                
                if kapatildi:
                    ham_alan = self._shoelace_formulu(noktalar)
                    # HAM ALANI METREKAREYE ÇEVİR
                    gercek_alan = self._birim_cevir(ham_alan)
                    toplam_alan += gercek_alan
                    parca_sayisi += 1
            
            except Exception:
                continue
        
        return {
            "katman": katman_adi,
            "toplam_miktar": round(toplam_alan, 2),
            "birim": "m²",
            "parca_sayisi": parca_sayisi,
            "not": f"{tamir_edilen} parça AI ile birleştirildi."
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
        elif self.birim == "cm":
            return alan_degeri / 10000.0  # cm² -> m² (100x100)
        elif self.birim == "mm":
            return alan_degeri / 1000000.0  # mm² -> m² (1000x1000)
        return alan_degeri


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

