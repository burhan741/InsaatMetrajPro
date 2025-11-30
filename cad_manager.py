"""
AutoCAD Dosya İşlemleri
DXF dosyalarını okuyup metraj verilerine dönüştürür
"""

import os
try:
    import ezdxf
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False


class CADManager:
    """CAD dosya yönetim sınıfı"""
    
    def __init__(self):
        """CAD manager'ı başlat"""
        if not EZDXF_AVAILABLE:
            print("Uyarı: ezdxf kütüphanesi yüklü değil. CAD işlemleri çalışmayacak.")
            print("Yüklemek için: pip install ezdxf")
            
    def import_dxf(self, file_path):
        """
        DXF dosyasını içe aktar ve metraj verilerine dönüştür
        
        Args:
            file_path: DXF dosyasının yolu
            
        Returns:
            list: Metraj kalemleri listesi
        """
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli. pip install ezdxf")
            
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")
            
        try:
            doc = ezdxf.readfile(file_path)
            modelspace = doc.modelspace()
            
            # Metraj verilerini topla
            items = []
            
            # Katman bazlı analiz
            layer_data = {}
            
            for entity in modelspace:
                layer_name = entity.dxf.layer if hasattr(entity.dxf, 'layer') else '0'
                
                if layer_name not in layer_data:
                    layer_data[layer_name] = {
                        'lines': [],
                        'polylines': [],
                        'circles': [],
                        'blocks': []
                    }
                
                # Çizgi uzunluğu
                if entity.dxftype() == 'LINE':
                    start = entity.dxf.start
                    end = entity.dxf.end
                    length = ((end.x - start.x)**2 + (end.y - start.y)**2)**0.5
                    layer_data[layer_name]['lines'].append(length)
                    
                # Polyline uzunluğu ve alanı
                elif entity.dxftype() == 'LWPOLYLINE':
                    try:
                        length = entity.length()
                        area = entity.area()
                        layer_data[layer_name]['polylines'].append({
                            'length': length,
                            'area': area
                        })
                    except:
                        pass
                        
                # Daire alanı
                elif entity.dxftype() == 'CIRCLE':
                    radius = entity.dxf.radius
                    area = 3.14159 * radius * radius
                    layer_data[layer_name]['circles'].append(area)
                    
                # Blok sayısı
                elif entity.dxftype() == 'INSERT':
                    block_name = entity.dxf.name
                    layer_data[layer_name]['blocks'].append(block_name)
            
            # Katman verilerini metraj kalemlerine dönüştür
            for layer_name, data in layer_data.items():
                # Uzunluk toplamı (m)
                if data['lines']:
                    total_length = sum(data['lines'])
                    items.append({
                        'name': f"{layer_name} - Çizgi Uzunluğu",
                        'quantity': total_length,
                        'unit': 'm',
                        'category': self._categorize_layer(layer_name)
                    })
                
                # Polyline uzunluk ve alan
                if data['polylines']:
                    total_length = sum(p['length'] for p in data['polylines'])
                    total_area = sum(p['area'] for p in data['polylines'])
                    
                    if total_length > 0:
                        items.append({
                            'name': f"{layer_name} - Polyline Uzunluğu",
                            'quantity': total_length,
                            'unit': 'm',
                            'category': self._categorize_layer(layer_name)
                        })
                    
                    if total_area > 0:
                        items.append({
                            'name': f"{layer_name} - Polyline Alanı",
                            'quantity': total_area,
                            'unit': 'm²',
                            'category': self._categorize_layer(layer_name)
                        })
                
                # Daire alanları
                if data['circles']:
                    total_area = sum(data['circles'])
                    items.append({
                        'name': f"{layer_name} - Daire Alanı",
                        'quantity': total_area,
                        'unit': 'm²',
                        'category': self._categorize_layer(layer_name)
                    })
                
                # Blok sayıları
                if data['blocks']:
                    block_counts = {}
                    for block_name in data['blocks']:
                        block_counts[block_name] = block_counts.get(block_name, 0) + 1
                    
                    for block_name, count in block_counts.items():
                        items.append({
                            'name': f"{layer_name} - {block_name}",
                            'quantity': count,
                            'unit': 'adet',
                            'category': self._categorize_layer(layer_name)
                        })
            
            return items
            
        except Exception as e:
            raise Exception(f"DXF dosyası işlenirken hata: {str(e)}")
            
    def _categorize_layer(self, layer_name):
        """Katman adına göre kategori belirle"""
        layer_lower = layer_name.lower()
        
        if any(word in layer_lower for word in ['duvar', 'wall']):
            return 'Duvar İşleri'
        elif any(word in layer_lower for word in ['kolon', 'column', 'kiriş', 'beam']):
            return 'Beton İşleri'
        elif any(word in layer_lower for word in ['kapi', 'door', 'pencere', 'window']):
            return 'Kapı/Pencere'
        elif any(word in layer_lower for word in ['elektrik', 'electric']):
            return 'Elektrik Tesisatı'
        elif any(word in layer_lower for word in ['su', 'water', 'kanal', 'sewer']):
            return 'Su Tesisatı'
        elif any(word in layer_lower for word in ['catı', 'roof', 'çatı']):
            return 'Çatı İşleri'
        else:
            return 'Genel'
            
    def import_dwg(self, file_path):
        """
        DWG dosyasını içe aktar (DXF'e dönüştürerek)
        
        Not: DWG dosyaları için özel kütüphane gerekebilir
        """
        # DWG dosyaları için özel işlem gerekir
        # Şimdilik DXF kullanılması önerilir
        raise NotImplementedError(
            "DWG desteği henüz eklenmedi. "
            "Lütfen AutoCAD'de dosyayı DXF formatına dönüştürün."
        )
        
    def export_to_dxf(self, items, output_path):
        """
        Metraj verilerini DXF formatına dışa aktar
        
        Args:
            items: Metraj kalemleri listesi
            output_path: Çıktı dosyası yolu
        """
        if not EZDXF_AVAILABLE:
            raise ImportError("ezdxf kütüphanesi gerekli")
            
        doc = ezdxf.new('R2010')
        modelspace = doc.modelspace()
        
        # Metraj verilerini DXF'e yaz
        y_offset = 0
        for item in items:
            # Metraj bilgisini text olarak ekle
            modelspace.add_text(
                f"{item['name']}: {item['quantity']} {item['unit']}",
                dxfattribs={'height': 2.5}
            ).set_placement((0, y_offset))
            y_offset -= 5
            
        doc.saveas(output_path)
        return output_path


