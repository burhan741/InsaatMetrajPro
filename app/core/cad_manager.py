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
        """DXF dosyasını yükle."""
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
        """Belirli bir katmandaki çizgilerin toplam uzunluğunu hesapla."""
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli")

        doc = self.load_dxf(file_path)
        modelspace = doc.modelspace()
        total_length = 0.0

        try:
            for entity in modelspace:
                entity_layer = getattr(entity.dxf, 'layer', '0')

                if entity_layer.lower() != layer_name.lower():
                    continue

                if entity.dxftype() == 'LINE':
                    start = entity.dxf.start
                    end = entity.dxf.end
                    length = ((end.x - start.x)**2 +
                              (end.y - start.y)**2 +
                              (end.z - start.z)**2)**0.5
                    total_length += length

                elif entity.dxftype() == 'LWPOLYLINE':
                    try:
                        points = list(entity.vertices)
                        if len(points) > 1:
                            length = 0.0
                            for i in range(len(points) - 1):
                                x1, y1 = points[i][:2]
                                x2, y2 = points[i + 1][:2]
                                segment_length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                length += segment_length

                            if entity.is_closed or (getattr(entity.dxf, 'flags', 0) & 1):
                                x1, y1 = points[-1][:2]
                                x2, y2 = points[0][:2]
                                segment_length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                length += segment_length

                            total_length += length
                    except Exception as e:
                        logger.warning(f"Polyline uzunluk hesaplama hatası: {e}")
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
                            logger.warning(f"Alternatif polyline hesaplama hatası: {e2}")

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
                            total_length += length
                    except Exception as e:
                        logger.warning(f"Polyline işleme hatası: {e}")

        except Exception as e:
            logger.error(f"Katman analizi hatası: {e}")
            raise RuntimeError(f"Katman analizi sırasında hata: {e}")

        return total_length

    def get_layers(self, file_path: Path) -> List[str]:
        """DXF dosyasındaki katman isimlerini liste olarak döndürür."""
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli")

        doc = self.load_dxf(file_path)
        layers = set()

        try:
            for entity in doc.modelspace():
                layer = getattr(entity.dxf, 'layer', '0')
                layers.add(layer)

            if doc.layers:
                for layer in doc.layers:
                    layers.add(layer.dxf.name)

        except Exception as e:
            logger.error(f"Katman listeleme hatası: {e}")
            raise ValueError(f"Katmanlar listelenirken hata oluştu: {e}")

        return sorted(list(layers))

    def get_all_layers(self, file_path: Path) -> List[str]:
        """DXF dosyasındaki tüm katmanları listele (get_layers alias)."""
        return self.get_layers(file_path)

    def analyze_dxf_for_metraj(self, file_path: Path) -> List[Dict[str, Any]]:
        """DXF dosyasını analiz et ve metraj verilerine dönüştür."""
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli")

        doc = self.load_dxf(file_path)
        modelspace = doc.modelspace()
        layer_data: Dict[str, Dict[str, Any]] = {}

        try:
            for entity in modelspace:
                layer_name = getattr(entity.dxf, 'layer', '0')

                if layer_name not in layer_data:
                    layer_data[layer_name] = {'length': 0.0, 'area': 0.0, 'count': 0}

                if entity.dxftype() in ['LINE', 'LWPOLYLINE', 'POLYLINE']:
                    try:
                        if entity.dxftype() == 'LINE':
                            start = entity.dxf.start
                            end = entity.dxf.end
                            length = ((end.x - start.x)**2 +
                                      (end.y - start.y)**2)**0.5
                            layer_data[layer_name]['length'] += length
                        elif entity.dxftype() == 'LWPOLYLINE':
                            points = list(entity.vertices)
                            if len(points) > 1:
                                length = 0.0
                                for i in range(len(points) - 1):
                                    x1, y1 = points[i][:2]
                                    x2, y2 = points[i + 1][:2]
                                    length += ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                if entity.is_closed or (getattr(entity.dxf, 'flags', 0) & 1):
                                    x1, y1 = points[-1][:2]
                                    x2, y2 = points[0][:2]
                                    length += ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                layer_data[layer_name]['length'] += length
                        elif entity.dxftype() == 'POLYLINE':
                            points = list(entity.vertices)
                            if len(points) > 1:
                                length = 0.0
                                for i in range(len(points) - 1):
                                    p1 = points[i].dxf.location
                                    p2 = points[i + 1].dxf.location
                                    length += ((p2.x - p1.x)**2 +
                                               (p2.y - p1.y)**2)**0.5
                                layer_data[layer_name]['length'] += length
                    except Exception:
                        pass

                if entity.dxftype() in ['LWPOLYLINE', 'POLYLINE']:
                    try:
                        if entity.is_closed:
                            area = entity.area()
                            layer_data[layer_name]['area'] += abs(area)
                    except Exception:
                        pass

                if entity.dxftype() == 'INSERT':
                    layer_data[layer_name]['count'] += 1

        except Exception as e:
            logger.error(f"DXF analiz hatası: {e}")
            raise RuntimeError(f"Analiz sırasında hata: {e}")

        metraj_items = []
        for layer_name, data in layer_data.items():
            category = self._categorize_layer(layer_name)

            if data['length'] > 0:
                metraj_items.append({
                    'tanim': f"{layer_name} - Uzunluk",
                    'miktar': data['length'] / 1000.0,
                    'birim': 'm',
                    'kategori': category,
                    'layer': layer_name
                })

            if data['area'] > 0:
                metraj_items.append({
                    'tanim': f"{layer_name} - Alan",
                    'miktar': data['area'] / 1000000.0,
                    'birim': 'm²',
                    'kategori': category,
                    'layer': layer_name
                })

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
        """Belirtilen katman ve yönteme göre hesaplama yapar."""
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
                for entity in modelspace:
                    entity_layer = getattr(entity.dxf, 'layer', '0')

                    if entity_layer.lower() != layer_name.lower():
                        continue

                    layer_found = True

                    if entity.dxftype() == 'LINE':
                        start = entity.dxf.start
                        end = entity.dxf.end
                        length = ((end.x - start.x)**2 +
                                  (end.y - start.y)**2 +
                                  (end.z - start.z)**2)**0.5
                        result += length

                    elif entity.dxftype() == 'LWPOLYLINE':
                        try:
                            points = list(entity.vertices)
                            if len(points) > 1:
                                length = 0.0
                                for i in range(len(points) - 1):
                                    x1, y1 = points[i][:2]
                                    x2, y2 = points[i + 1][:2]
                                    segment_length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                    length += segment_length

                                if entity.is_closed or (getattr(entity.dxf, 'flags', 0) & 1):
                                    x1, y1 = points[-1][:2]
                                    x2, y2 = points[0][:2]
                                    segment_length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                    length += segment_length

                                result += length
                        except Exception as e:
                            logger.warning(f"Polyline uzunluk hesaplama hatası: {e}")
                            try:
                                flattened = list(entity.flattening(0.01))
                                if len(flattened) > 1:
                                    length = 0.0
                                    for i in range(len(flattened) - 1):
                                        p1 = flattened[i]
                                        p2 = flattened[i + 1]
                                        length += ((p2.x - p1.x)**2 + (p2.y - p1.y)**2)**0.5
                                    result += length
                            except Exception as e2:
                                logger.warning(f"Alternatif polyline hatası: {e2}")

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

                result = result / 1000.0

            elif method == 'alan':
                entity_count = 0
                closed_count = 0

                for entity in modelspace:
                    entity_layer = getattr(entity.dxf, 'layer', '0')

                    if entity_layer.lower() != layer_name.lower():
                        continue

                    layer_found = True
                    entity_count += 1

                    if entity.dxftype() == 'CIRCLE':
                        try:
                            radius = entity.dxf.radius
                            area = 3.141592653589793 * radius * radius
                            result += abs(area)
                            closed_count += 1
                        except Exception as e:
                            logger.warning(f"Circle alan hesaplama hatası: {e}")

                    elif entity.dxftype() == 'LWPOLYLINE':
                        try:
                            is_closed = getattr(entity.dxf, 'flags', 0) & 1
                            if is_closed or entity.is_closed:
                                area = entity.area()
                                result += abs(area)
                                closed_count += 1
                            else:
                                try:
                                    points = list(entity.vertices)
                                    if len(points) >= 3:
                                        first = points[0]
                                        last = points[-1]
                                        if abs(first[0] - last[0]) < 0.001 and abs(first[1] - last[1]) < 0.001:
                                            try:
                                                area = entity.area()
                                                result += abs(area)
                                                closed_count += 1
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                        except Exception as e:
                            logger.warning(f"Polyline alan hesaplama hatası: {e}")

                    elif entity.dxftype() == 'POLYLINE':
                        try:
                            is_closed = getattr(entity.dxf, 'flags', 0) & 1
                            if is_closed or entity.is_closed:
                                points = list(entity.vertices)
                                if len(points) >= 3:
                                    area = 0.0
                                    for i in range(len(points)):
                                        p1 = points[i].dxf.location
                                        p2 = points[(i + 1) % len(points)].dxf.location
                                        area += p1.x * p2.y - p2.x * p1.y
                                    result += abs(area) / 2.0
                                    closed_count += 1
                        except Exception as e:
                            logger.warning(f"Polyline alan hesaplama hatası: {e}")

                result = result / 1000000.0

            elif method == 'adet':
                for entity in modelspace:
                    entity_layer = getattr(entity.dxf, 'layer', '0')

                    if entity_layer.lower() != layer_name.lower():
                        continue

                    layer_found = True

                    if entity.dxftype() == 'INSERT':
                        result += 1
                    elif entity.dxftype() == 'CIRCLE':
                        result += 1
                    elif entity.dxftype() == 'ARC':
                        result += 1
                    elif entity.dxftype() in ['TEXT', 'MTEXT']:
                        result += 1
                    elif entity.dxftype() not in ['LINE', 'LWPOLYLINE', 'POLYLINE']:
                        result += 1

        except Exception as e:
            logger.error(f"Hesaplama hatası: {e}")
            raise RuntimeError(f"Hesaplama sırasında hata oluştu: {e}")

        if not layer_found:
            logger.warning(f"Katman '{layer_name}' dosyada bulunamadı veya boş")

        return result

    def _categorize_layer(self, layer_name: str) -> str:
        """Katman adına göre kategori belirle."""
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
