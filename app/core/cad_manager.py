"""
CAD Yöneticisi
DXF dosyalarını okuma ve analiz için core modül
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

try:
    import ezdxf
    from ezdxf import DXFStructureError, DXFValueError
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False
    ezdxf = None

logger = logging.getLogger(__name__)


class CADManager:
    """
    CAD dosya yönetim sınıfı.
    
    DXF dosyalarını okur, analiz eder ve metraj verilerine dönüştürür.
    """
    
    def __init__(self) -> None:
        """CAD yöneticisini başlat."""
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
            
        Raises:
            FileNotFoundError: Dosya bulunamazsa
            ImportError: ezdxf yüklü değilse
        """
        if not EZDXF_AVAILABLE:
            raise ImportError(
                "ezdxf kütüphanesi gerekli. Yüklemek için: pip install ezdxf"
            )
            
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")
            
        try:
            doc = ezdxf.readfile(str(file_path))
            logger.info(f"DXF dosyası başarıyla yüklendi: {file_path}")
            return doc
        except DXFStructureError as e:
            logger.error(f"DXF yapı hatası: {e}")
            raise ValueError(f"Geçersiz DXF dosyası: {e}")
        except DXFValueError as e:
            logger.error(f"DXF değer hatası: {e}")
            raise ValueError(f"DXF dosyası okunamadı: {e}")
        except Exception as e:
            logger.error(f"DXF yükleme hatası: {e}")
            raise RuntimeError(f"Dosya yüklenirken hata oluştu: {e}")
            
    def calculate_layer_length(self, file_path: Path, layer_name: str) -> float:
        """
        Belirli bir katmandaki çizgilerin toplam uzunluğunu hesapla.
        
        Args:
            file_path: DXF dosyasının yolu
            layer_name: Katman adı
            
        Returns:
            float: Toplam uzunluk (birim: çizim birimi, genellikle mm)
            
        Raises:
            ImportError: ezdxf yüklü değilse
            FileNotFoundError: Dosya bulunamazsa
        """
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli")
            
        doc = self.load_dxf(file_path)
        modelspace = doc.modelspace()
        
        total_length = 0.0
        
        try:
            for entity in modelspace:
                # Katman kontrolü
                entity_layer = getattr(entity.dxf, 'layer', '0')
                
                if entity_layer.lower() != layer_name.lower():
                    continue
                    
                # LINE entity
                if entity.dxftype() == 'LINE':
                    start = entity.dxf.start
                    end = entity.dxf.end
                    length = ((end.x - start.x)**2 + 
                             (end.y - start.y)**2 + 
                             (end.z - start.z)**2)**0.5
                    total_length += length
                    
                # LWPOLYLINE entity
                elif entity.dxftype() == 'LWPOLYLINE':
                    try:
                        length = entity.length()
                        total_length += length
                    except Exception as e:
                        logger.warning(f"Polyline uzunluk hesaplama hatası: {e}")
                        
                # POLYLINE entity (eski format)
                elif entity.dxftype() == 'POLYLINE':
                    try:
                        # Polyline noktalarını topla
                        points = list(entity.vertices)
                        if len(points) > 1:
                            length = 0.0
                            for i in range(len(points) - 1):
                                p1 = points[i].dxf.location
                                p2 = points[i + 1].dxf.location
                                length += ((p2.x - p1.x)**2 + 
                                          (p2.y - p1.y)**2 + 
                                          (p2.z - p1.z)**2)**0.5
                            total_length += length
                    except Exception as e:
                        logger.warning(f"Polyline işleme hatası: {e}")
                        
        except Exception as e:
            logger.error(f"Katman analizi hatası: {e}")
            raise RuntimeError(f"Katman analizi sırasında hata: {e}")
            
        return total_length
        
    def get_all_layers(self, file_path: Path) -> List[str]:
        """
        DXF dosyasındaki tüm katmanları listele.
        
        Args:
            file_path: DXF dosyasının yolu
            
        Returns:
            List[str]: Katman adları listesi
        """
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli")
            
        doc = self.load_dxf(file_path)
        layers = set()
        
        try:
            # Modelspace'deki tüm entity'lerden katmanları topla
            for entity in doc.modelspace():
                layer = getattr(entity.dxf, 'layer', '0')
                layers.add(layer)
                
            # Layer tablosundan da katmanları al
            if doc.layers:
                for layer in doc.layers:
                    layers.add(layer.dxf.name)
                    
        except Exception as e:
            logger.error(f"Katman listeleme hatası: {e}")
            
        return sorted(list(layers))
        
    def analyze_dxf_for_metraj(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        DXF dosyasını analiz et ve metraj verilerine dönüştür.
        
        Args:
            file_path: DXF dosyasının yolu
            
        Returns:
            List[Dict]: Metraj kalemleri listesi
        """
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli")
            
        doc = self.load_dxf(file_path)
        modelspace = doc.modelspace()
        
        # Katman bazlı veri toplama
        layer_data: Dict[str, Dict[str, Any]] = {}
        
        try:
            for entity in modelspace:
                layer_name = getattr(entity.dxf, 'layer', '0')
                
                if layer_name not in layer_data:
                    layer_data[layer_name] = {
                        'length': 0.0,
                        'area': 0.0,
                        'count': 0
                    }
                
                # Uzunluk hesaplama
                if entity.dxftype() in ['LINE', 'LWPOLYLINE', 'POLYLINE']:
                    try:
                        if entity.dxftype() == 'LINE':
                            start = entity.dxf.start
                            end = entity.dxf.end
                            length = ((end.x - start.x)**2 + 
                                     (end.y - start.y)**2)**0.5
                            layer_data[layer_name]['length'] += length
                        else:
                            length = entity.length()
                            layer_data[layer_name]['length'] += length
                    except:
                        pass
                        
                # Alan hesaplama (kapalı polyline'lar için)
                if entity.dxftype() in ['LWPOLYLINE', 'POLYLINE']:
                    try:
                        if entity.is_closed:
                            area = entity.area()
                            layer_data[layer_name]['area'] += abs(area)
                    except:
                        pass
                        
                # Blok sayısı
                if entity.dxftype() == 'INSERT':
                    layer_data[layer_name]['count'] += 1
                    
        except Exception as e:
            logger.error(f"DXF analiz hatası: {e}")
            raise RuntimeError(f"Analiz sırasında hata: {e}")
            
        # Metraj kalemlerine dönüştür
        metraj_items = []
        for layer_name, data in layer_data.items():
            category = self._categorize_layer(layer_name)
            
            # Uzunluk kalemi
            if data['length'] > 0:
                metraj_items.append({
                    'tanim': f"{layer_name} - Uzunluk",
                    'miktar': data['length'] / 1000.0,  # mm'den m'ye çevir
                    'birim': 'm',
                    'kategori': category,
                    'layer': layer_name
                })
                
            # Alan kalemi
            if data['area'] > 0:
                metraj_items.append({
                    'tanim': f"{layer_name} - Alan",
                    'miktar': data['area'] / 1000000.0,  # mm²'den m²'ye çevir
                    'birim': 'm²',
                    'kategori': category,
                    'layer': layer_name
                })
                
            # Adet kalemi
            if data['count'] > 0:
                metraj_items.append({
                    'tanim': f"{layer_name} - Blok Sayısı",
                    'miktar': float(data['count']),
                    'birim': 'adet',
                    'kategori': category,
                    'layer': layer_name
                })
                
        return metraj_items
        
    def _categorize_layer(self, layer_name: str) -> str:
        """
        Katman adına göre kategori belirle.
        
        Args:
            layer_name: Katman adı
            
        Returns:
            str: Kategori adı
        """
        layer_lower = layer_name.lower()
        
        if any(word in layer_lower for word in ['duvar', 'wall', 'dwg']):
            return 'Duvar İşleri'
        elif any(word in layer_lower for word in ['kolon', 'column', 'kiriş', 'beam']):
            return 'Beton İşleri'
        elif any(word in layer_lower for word in ['kapi', 'door', 'pencere', 'window']):
            return 'Kapı/Pencere'
        elif any(word in layer_lower for word in ['elektrik', 'electric', 'elec']):
            return 'Elektrik Tesisatı'
        elif any(word in layer_lower for word in ['su', 'water', 'kanal', 'sewer']):
            return 'Su Tesisatı'
        elif any(word in layer_lower for word in ['catı', 'roof', 'çatı']):
            return 'Çatı İşleri'
        elif any(word in layer_lower for word in ['toprak', 'earth', 'hafriyat']):
            return 'Toprak İşleri'
        else:
            return 'Genel'

