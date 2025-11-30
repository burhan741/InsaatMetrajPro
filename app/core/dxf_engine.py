"""
DXF Engine
DXF dosyaları için gelişmiş işleme motoru
"""

import sys
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
    """
    
    def __init__(self, dosya_yolu: str) -> None:
        """
        DXFAnaliz sınıfını başlat.
        
        Args:
            dosya_yolu: DXF dosyasının yolu
        """
        self.dosya_yolu = dosya_yolu
        self.doc = None
        self.msp = None
        self.yukle()
    
    def yukle(self) -> None:
        """DXF dosyasını hafızaya yükler."""
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli")
        
        try:
            self.doc = ezdxf.readfile(self.dosya_yolu)
            self.msp = self.doc.modelspace()
            logger.info(f"✅ Başarılı: '{self.dosya_yolu}' yüklendi.")
        except IOError:
            error_msg = f"❌ Hata: '{self.dosya_yolu}' dosyası bulunamadı."
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        except ezdxf.DXFStructureError:
            error_msg = "❌ Hata: Geçersiz veya bozuk DXF dosyası."
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def katmanlari_listele(self) -> List[str]:
        """Dosyadaki tüm katman isimlerini döndürür."""
        if not self.doc:
            return []
        return [layer.dxf.name for layer in self.doc.layers]
    
    def alan_hesapla(self, katman_adi: str) -> Dict[str, Any]:
        """
        Belirtilen katmandaki KAPALI poligonların (LWPOLYLINE) alanını hesaplar.
        
        Örnek: Parke, Seramik, Duvar Boyası alanları.
        
        Args:
            katman_adi: Hesaplanacak katman adı
            
        Returns:
            Dict: Hesaplama sonuçları
        """
        toplam_alan = 0.0
        parca_sayisi = 0
        
        # İlgili katmandaki polylineları bul
        sorgu = f'LWPOLYLINE[layer=="{katman_adi}"]'
        
        try:
            for entity in self.msp.query(sorgu):
                # Sadece kapalı şekillerin alanı hesaplanabilir
                if entity.is_closed:
                    # Noktaları al (sadece x,y koordinatları)
                    noktalar = list(entity.points("xy"))
                    alan = self._shoelace_formulu(noktalar)
                    toplam_alan += alan
                    parca_sayisi += 1
            
            return {
                "islem": "Alan Hesabı",
                "katman": katman_adi,
                "parca_sayisi": parca_sayisi,
                "toplam_miktar": round(toplam_alan, 2),
                "birim": "m²"
            }
        except Exception as e:
            logger.error(f"Alan hesaplama hatası: {e}")
            return {"hata": str(e)}
    
    def blok_say(self, blok_adi_veya_katman: str, moda_gore: str = "katman") -> Dict[str, Any]:
        """
        Nesneleri sayar (Kapı, Pencere, Kolon vb.)
        
        Args:
            blok_adi_veya_katman: Blok adı veya katman adı
            moda_gore: 'katman' (katmandaki her şeyi sayar) veya 'isim' (blok adına göre sayar)
            
        Returns:
            Dict: Sayım sonuçları
        """
        adet = 0
        
        if moda_gore == "katman":
            # O katmandaki INSERT (blok) nesnelerini say
            adet = len(self.msp.query(f'INSERT[layer=="{blok_adi_veya_katman}"]'))
        else:
            # İsmi eşleşen blokları say
            adet = len(self.msp.query(f'INSERT[name=="{blok_adi_veya_katman}"]'))
        
        return {
            "islem": "Adet Sayımı",
            "hedef": blok_adi_veya_katman,
            "toplam_miktar": adet,
            "birim": "adet"
        }
    
    def _shoelace_formulu(self, points: List[Tuple[float, float]]) -> float:
        """
        Koordinatları bilinen çokgenin alanını hesaplayan matematiksel formül.
        
        Args:
            points: (x, y) koordinat çiftleri listesi
            
        Returns:
            float: Hesaplanan alan
        """
        n = len(points)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        return abs(area) / 2.0


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

