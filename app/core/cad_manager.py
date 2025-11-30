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
                        # LWPOLYLINE için noktaları al ve manuel hesapla
                        points = list(entity.vertices)
                        if len(points) > 1:
                            length = 0.0
                            for i in range(len(points) - 1):
                                # LWPOLYLINE noktaları (x, y) tuple olarak gelir
                                x1, y1 = points[i][:2]  # İlk iki değer x, y
                                x2, y2 = points[i + 1][:2]
                                # Segment uzunluğu
                                segment_length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                length += segment_length
                            
                            # Eğer kapalıysa, son noktadan ilk noktaya olan uzunluğu ekle
                            if entity.is_closed or (getattr(entity.dxf, 'flags', 0) & 1):
                                x1, y1 = points[-1][:2]
                                x2, y2 = points[0][:2]
                                segment_length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                length += segment_length
                            
                            total_length += length
                    except Exception as e:
                        logger.warning(f"Polyline uzunluk hesaplama hatası: {e}")
                        # Alternatif yöntem: flattening kullan
                        try:
                            flattened = list(entity.flattening(0.01))
                            if len(flattened) > 1:
                                length = 0.0
                                for i in range(len(flattened) - 1):
                                    p1 = flattened[i]
                                    p2 = flattened[i + 1]
                                    length += ((p2.x - p1.x)**2 + (p2.y - p1.y)**2)**0.5
                                total_length += length
                        except Exception as e2:
                            logger.warning(f"Alternatif polyline uzunluk hesaplama hatası: {e2}")
                        
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
        
    def get_layers(self, file_path: Path) -> List[str]:
        """
        DXF dosyasındaki katman isimlerini liste olarak döndürür.
        
        Args:
            file_path: DXF dosyasının yolu
            
        Returns:
            List[str]: Katman adları listesi
            
        Raises:
            ImportError: ezdxf yüklü değilse
            FileNotFoundError: Dosya bulunamazsa
            ValueError: Dosya bozuksa
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
            raise ValueError(f"Katmanlar listelenirken hata oluştu: {e}")
            
        return sorted(list(layers))
    
    def get_all_layers(self, file_path: Path) -> List[str]:
        """
        DXF dosyasındaki tüm katmanları listele.
        (get_layers için alias - geriye dönük uyumluluk)
        
        Args:
            file_path: DXF dosyasının yolu
            
        Returns:
            List[str]: Katman adları listesi
        """
        return self.get_layers(file_path)
        
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
                        elif entity.dxftype() == 'LWPOLYLINE':
                            # LWPOLYLINE için manuel hesaplama
                            points = list(entity.vertices)
                            if len(points) > 1:
                                length = 0.0
                                for i in range(len(points) - 1):
                                    x1, y1 = points[i][:2]
                                    x2, y2 = points[i + 1][:2]
                                    length += ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                # Kapalıysa son segmenti ekle
                                if entity.is_closed or (getattr(entity.dxf, 'flags', 0) & 1):
                                    x1, y1 = points[-1][:2]
                                    x2, y2 = points[0][:2]
                                    length += ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                layer_data[layer_name]['length'] += length
                        elif entity.dxftype() == 'POLYLINE':
                            # POLYLINE için mevcut kod
                            points = list(entity.vertices)
                            if len(points) > 1:
                                length = 0.0
                                for i in range(len(points) - 1):
                                    p1 = points[i].dxf.location
                                    p2 = points[i + 1].dxf.location
                                    length += ((p2.x - p1.x)**2 + 
                                              (p2.y - p1.y)**2)**0.5
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
        
    def calculate(self, file_path: Path, layer_name: str, method: str) -> float:
        """
        Belirtilen katman ve yönteme göre hesaplama yapar.
        
        Args:
            file_path: DXF dosyasının yolu
            layer_name: Katman adı
            method: Hesaplama yöntemi ('uzunluk', 'alan', 'adet')
            
        Returns:
            float: Hesaplanan değer
                - uzunluk: metre cinsinden (cm'den m'ye dönüştürülmüş)
                - alan: m² cinsinden (cm²'den m²'ye dönüştürülmüş)
                - adet: obje sayısı
            
        Raises:
            ImportError: ezdxf yüklü değilse
            FileNotFoundError: Dosya bulunamazsa
            ValueError: Geçersiz method veya katman yoksa
        """
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli")
        
        if method not in ['uzunluk', 'alan', 'adet']:
            raise ValueError(f"Geçersiz method: {method}. 'uzunluk', 'alan' veya 'adet' olmalı.")
        
        doc = self.load_dxf(file_path)
        modelspace = doc.modelspace()
        
        result = 0.0
        layer_found = False
        
        try:
            if method == 'uzunluk':
                # LINE ve LWPOLYLINE objelerinin toplam uzunluğu
                for entity in modelspace:
                    entity_layer = getattr(entity.dxf, 'layer', '0')
                    
                    if entity_layer.lower() != layer_name.lower():
                        continue
                    
                    layer_found = True
                    
                    # LINE entity
                    if entity.dxftype() == 'LINE':
                        start = entity.dxf.start
                        end = entity.dxf.end
                        length = ((end.x - start.x)**2 + 
                                 (end.y - start.y)**2 + 
                                 (end.z - start.z)**2)**0.5
                        result += length
                        
                    # LWPOLYLINE entity
                    elif entity.dxftype() == 'LWPOLYLINE':
                        try:
                            # LWPOLYLINE için noktaları al ve manuel hesapla
                            points = list(entity.vertices)
                            if len(points) > 1:
                                length = 0.0
                                for i in range(len(points) - 1):
                                    # LWPOLYLINE noktaları (x, y) tuple olarak gelir
                                    x1, y1 = points[i][:2]  # İlk iki değer x, y
                                    x2, y2 = points[i + 1][:2]
                                    # Segment uzunluğu
                                    segment_length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                    length += segment_length
                                
                                # Eğer kapalıysa, son noktadan ilk noktaya olan uzunluğu ekle
                                if entity.is_closed or (getattr(entity.dxf, 'flags', 0) & 1):
                                    x1, y1 = points[-1][:2]
                                    x2, y2 = points[0][:2]
                                    segment_length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                    length += segment_length
                                
                                result += length
                        except Exception as e:
                            logger.warning(f"Polyline uzunluk hesaplama hatası: {e}")
                            # Alternatif yöntem: flattening kullan
                            try:
                                # ezdxf'in flattening metodu ile düzleştirilmiş noktaları al
                                flattened = list(entity.flattening(0.01))  # 0.01 tolerans
                                if len(flattened) > 1:
                                    length = 0.0
                                    for i in range(len(flattened) - 1):
                                        p1 = flattened[i]
                                        p2 = flattened[i + 1]
                                        length += ((p2.x - p1.x)**2 + (p2.y - p1.y)**2)**0.5
                                    result += length
                            except Exception as e2:
                                logger.warning(f"Alternatif polyline uzunluk hesaplama hatası: {e2}")
                            
                    # POLYLINE entity (eski format)
                    elif entity.dxftype() == 'POLYLINE':
                        try:
                            points = list(entity.vertices)
                            if len(points) > 1:
                                length = 0.0
                                for i in range(len(points) - 1):
                                    p1 = points[i].dxf.location
                                    p2 = points[i + 1].dxf.location
                                    length += ((p2.x - p1.x)**2 + 
                                              (p2.y - p1.y)**2 + 
                                              (p2.z - p1.z)**2)**0.5
                                result += length
                        except Exception as e:
                            logger.warning(f"Polyline işleme hatası: {e}")
                
                # Birim dönüşümü: DXF dosyaları genellikle mm cinsinden olur
                # mm'den m'ye: /1000
                # Ama bazıları cm olabilir, o yüzden /100 de deneyelim
                # Şimdilik mm varsayalım (/1000)
                result = result / 1000.0  # mm'den m'ye
                
                # Eğer sonuç çok küçükse (0.1'den küçük), belki cm cinsindeydi
                # O zaman /100 ile tekrar dene
                if result < 0.1 and result > 0:
                    result_cm = result * 10  # m'den cm'ye geri dön, sonra /100
                    result = result_cm / 100.0
                    logger.info(f"Sonuç çok küçük, cm birimi deneniyor: {result} m")
                
            elif method == 'alan':
                # KAPALI (Closed) LWPOLYLINE, CIRCLE, ELLIPSE vb. objelerinin alanı
                entity_count = 0
                closed_count = 0
                
                for entity in modelspace:
                    entity_layer = getattr(entity.dxf, 'layer', '0')
                    
                    if entity_layer.lower() != layer_name.lower():
                        continue
                    
                    layer_found = True
                    entity_count += 1
                    
                    # CIRCLE - daire alanı
                    if entity.dxftype() == 'CIRCLE':
                        try:
                            radius = entity.dxf.radius
                            area = 3.141592653589793 * radius * radius  # π * r²
                            result += abs(area)
                            closed_count += 1
                            logger.debug(f"CIRCLE bulundu, yarıçap: {radius}, alan: {area}")
                        except Exception as e:
                            logger.warning(f"Circle alan hesaplama hatası: {e}")
                    
                    # ELLIPSE - elips alanı
                    elif entity.dxftype() == 'ELLIPSE':
                        try:
                            # Ellips için major ve minor axis gerekli
                            major_axis = entity.dxf.major_axis
                            minor_axis = entity.dxf.minor_axis
                            # Basitleştirilmiş: major ve minor axis uzunluklarını al
                            a = ((major_axis.x)**2 + (major_axis.y)**2 + (major_axis.z)**2)**0.5
                            b = ((minor_axis.x)**2 + (minor_axis.y)**2 + (minor_axis.z)**2)**0.5
                            area = 3.141592653589793 * a * b  # π * a * b
                            result += abs(area)
                            closed_count += 1
                            logger.debug(f"ELLIPSE bulundu, alan: {area}")
                        except Exception as e:
                            logger.warning(f"Ellipse alan hesaplama hatası: {e}")
                    
                    # LWPOLYLINE - kapalı olanlar
                    elif entity.dxftype() == 'LWPOLYLINE':
                        try:
                            # Kapalı mı kontrol et
                            is_closed = getattr(entity.dxf, 'flags', 0) & 1  # Bit 0 = closed flag
                            if is_closed or entity.is_closed:
                                area = entity.area()
                                result += abs(area)
                                closed_count += 1
                                logger.debug(f"Kapalı LWPOLYLINE bulundu, alan: {area}")
                            else:
                                # Kapalı değilse, ilk ve son nokta aynı mı kontrol et
                                try:
                                    points = list(entity.vertices)
                                    if len(points) >= 3:
                                        first = points[0]
                                        last = points[-1]
                                        # İlk ve son nokta yaklaşık olarak aynı mı? (0.001 tolerans)
                                        if abs(first[0] - last[0]) < 0.001 and abs(first[1] - last[1]) < 0.001:
                                            try:
                                                area = entity.area()
                                                result += abs(area)
                                                closed_count += 1
                                                logger.debug(f"Kapalı olmayan ama alan hesaplanabilir LWPOLYLINE, alan: {area}")
                                            except:
                                                pass
                                except:
                                    pass
                        except Exception as e:
                            logger.warning(f"Polyline alan hesaplama hatası: {e}")
                            
                    # POLYLINE - kapalı olanlar
                    elif entity.dxftype() == 'POLYLINE':
                        try:
                            is_closed = getattr(entity.dxf, 'flags', 0) & 1
                            if is_closed or entity.is_closed:
                                # Polyline alanını hesapla (Shoelace formülü)
                                points = list(entity.vertices)
                                if len(points) >= 3:
                                    area = 0.0
                                    for i in range(len(points)):
                                        p1 = points[i].dxf.location
                                        p2 = points[(i + 1) % len(points)].dxf.location
                                        area += p1.x * p2.y - p2.x * p1.y
                                    result += abs(area) / 2.0
                                    closed_count += 1
                                    logger.debug(f"Kapalı POLYLINE bulundu, alan: {abs(area) / 2.0}")
                        except Exception as e:
                            logger.warning(f"Polyline alan hesaplama hatası: {e}")
                    
                    # SPLINE - kapalı spline'lar (eğer kapalıysa)
                    elif entity.dxftype() == 'SPLINE':
                        try:
                            if entity.closed:
                                # Spline için alan hesaplama karmaşık, şimdilik atla
                                # veya yaklaşık hesaplama yapılabilir
                                logger.debug("Kapalı SPLINE bulundu ama alan hesaplanmadı (karmaşık)")
                        except:
                            pass
                
                # Debug bilgisi
                if entity_count > 0:
                    logger.info(f"Katman '{layer_name}': {entity_count} obje bulundu, {closed_count} tanesi kapalı/alana sahip")
                
                # Birim dönüşümü: DXF dosyaları genellikle mm cinsinden olur
                # Ama bazıları cm veya m olabilir. Güvenli tarafta kalıp mm varsayalım
                # mm²'den m²'ye: /1000000
                # Ama kullanıcı cm varsaymış olabilir, o yüzden /10000 de deneyelim
                # Şimdilik mm varsayalım (/1000000)
                result = result / 1000000.0  # mm²'den m²'ye
                
                # Eğer sonuç çok küçükse (0.01'den küçük), belki cm cinsindeydi
                # O zaman /10000 ile tekrar dene
                if result < 0.01 and result > 0:
                    result_cm = result * 100  # m²'den cm²'ye geri dön, sonra /10000
                    result = result_cm / 10000.0
                    logger.info(f"Sonuç çok küçük, cm birimi deneniyor: {result} m²")
                
            elif method == 'adet':
                # INSERT, CIRCLE vb. objeleri say
                for entity in modelspace:
                    entity_layer = getattr(entity.dxf, 'layer', '0')
                    
                    if entity_layer.lower() != layer_name.lower():
                        continue
                    
                    layer_found = True
                    
                    # INSERT (blok referansları)
                    if entity.dxftype() == 'INSERT':
                        result += 1
                    # CIRCLE
                    elif entity.dxftype() == 'CIRCLE':
                        result += 1
                    # ARC
                    elif entity.dxftype() == 'ARC':
                        result += 1
                    # TEXT, MTEXT
                    elif entity.dxftype() in ['TEXT', 'MTEXT']:
                        result += 1
                    # Diğer obje tipleri
                    elif entity.dxftype() not in ['LINE', 'LWPOLYLINE', 'POLYLINE']:
                        result += 1
                
        except Exception as e:
            logger.error(f"Hesaplama hatası: {e}")
            raise RuntimeError(f"Hesaplama sırasında hata oluştu: {e}")
        
        # Katman bulunamadıysa uyarı ver
        if not layer_found:
            logger.warning(f"Katman '{layer_name}' dosyada bulunamadı veya boş")
            # Hata fırlatmak yerine 0 döndür (kullanıcı arayüzünde uyarı gösterilebilir)
        
        return result
    
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


