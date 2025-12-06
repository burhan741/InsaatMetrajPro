"""
İnşaat Metraj Pro - Logo Oluşturucu
Modern ve etkileyici bir inşaat amblemi oluşturur.
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_logo():
    """İnşaat temasında profesyonel ve modern logo oluştur"""
    
    # Logo boyutları (yüksek çözünürlük)
    width, height = 1024, 1024
    img = Image.new('RGB', (width, height), color='#FFFFFF')
    draw = ImageDraw.Draw(img)
    
    # Modern renk paleti (İnşaat teması)
    primary_blue = '#1565C0'  # Derin mavi (güven, profesyonellik)
    accent_orange = '#FF6F00'  # Canlı turuncu (enerji, inşaat)
    dark_gray = '#212121'  # Koyu gri (güç, dayanıklılık)
    light_gray = '#ECEFF1'  # Açık gri (temizlik, modernlik)
    white = '#FFFFFF'
    
    # Gradient arka plan (üstten alta açılıyor)
    for y in range(height):
        ratio = y / height
        r = int(255 - ratio * 10)
        g = int(255 - ratio * 10)
        b = int(255 - ratio * 10)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Merkez noktası
    center_x, center_y = width // 2, height // 2
    
    # ===== ANA SEMBOL: METRAJ CETVELİ + BİNA KOMBİNASYONU =====
    
    # 1. METRAJ CETVELİ (Modern, 3D görünümlü)
    ruler_width = 320
    ruler_height = 60
    ruler_x = center_x - ruler_width // 2
    ruler_y = center_y - 100
    
    # Cetvel gölgesi (3D efekti)
    shadow_offset = 4
    draw.rounded_rectangle(
        [ruler_x + shadow_offset, ruler_y + shadow_offset, 
         ruler_x + ruler_width + shadow_offset, ruler_y + ruler_height + shadow_offset],
        radius=12,
        fill='#B0BEC5',
        outline=None
    )
    
    # Cetvel gövdesi (gradient efekti)
    draw.rounded_rectangle(
        [ruler_x, ruler_y, ruler_x + ruler_width, ruler_y + ruler_height],
        radius=12,
        fill=primary_blue,
        outline=dark_gray,
        width=4
    )
    
    # Cetvel üzerinde ölçüm çizgileri (detaylı)
    for i in range(0, ruler_width, 16):
        x = ruler_x + i
        if i % 32 == 0:  # Uzun çizgi (cm işareti)
            draw.line([(x, ruler_y + 5), (x, ruler_y + ruler_height - 5)], fill=white, width=3)
        elif i % 16 == 0:  # Orta çizgi (mm işareti)
            draw.line([(x, ruler_y + 15), (x, ruler_y + ruler_height - 15)], fill=white, width=2)
    
    # Cetvel üzerinde sayılar
    try:
        # Font yüklemeyi dene
        font_large = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    for i in range(0, ruler_width, 32):
        x = ruler_x + i
        num = str(i // 16)
        bbox = draw.textbbox((0, 0), num, font=font_small)
        text_width = bbox[2] - bbox[0]
        draw.text((x - text_width // 2, ruler_y - 30), num, fill=dark_gray, font=font_small)
    
    # 2. MODERN BİNA SİLÜETİ (Geometrik, minimal)
    building_x = center_x - 120
    building_y = center_y + 40
    building_width = 240
    building_height = 180
    
    # Bina gölgesi
    draw.rounded_rectangle(
        [building_x + 6, building_y + 6, building_x + building_width + 6, building_y + building_height + 6],
        radius=8,
        fill='#CFD8DC',
        outline=None
    )
    
    # Bina gövdesi (gradient efekti)
    draw.rounded_rectangle(
        [building_x, building_y, building_x + building_width, building_y + building_height],
        radius=8,
        fill=accent_orange,
        outline=dark_gray,
        width=5
    )
    
    # Modern bina pencereleri (grid pattern)
    window_size = 30
    window_spacing = 45
    window_margin = 25
    for row in range(3):
        for col in range(4):
            win_x = building_x + window_margin + col * window_spacing
            win_y = building_y + window_margin + row * window_spacing
            # Pencere (ışıklı)
            draw.rounded_rectangle(
                [win_x, win_y, win_x + window_size, win_y + window_size],
                radius=3,
                fill='#FFF9C4',  # Açık sarı (ışık)
                outline=dark_gray,
                width=2
            )
            # Pencere çerçevesi (çapraz)
            draw.line([(win_x + window_size // 2, win_y), 
                      (win_x + window_size // 2, win_y + window_size)], 
                     fill=dark_gray, width=2)
            draw.line([(win_x, win_y + window_size // 2), 
                      (win_x + window_size, win_y + window_size // 2)], 
                     fill=dark_gray, width=2)
    
    # Modern bina çatısı (düz, modern mimari)
    roof_height = 30
    roof_points = [
        (building_x - 15, building_y),
        (center_x, building_y - roof_height),
        (building_x + building_width + 15, building_y)
    ]
    draw.polygon(roof_points, fill=dark_gray, outline=dark_gray, width=5)
    
    # Çatı üzerinde anten/çıkıntı (detay)
    antenna_x = center_x
    antenna_y = building_y - roof_height
    draw.ellipse([antenna_x - 8, antenna_y - 8, antenna_x + 8, antenna_y + 8], 
                fill=accent_orange, outline=dark_gray, width=2)
    
    # 3. DEKORATİF ÇERÇEVE (Modern, minimal)
    border_width = 12
    draw.rounded_rectangle(
        [border_width, border_width, width - border_width, height - border_width],
        radius=30,
        outline=primary_blue,
        width=border_width
    )
    
    # İç çerçeve (ince)
    inner_border = border_width + 20
    draw.rounded_rectangle(
        [inner_border, inner_border, width - inner_border, height - inner_border],
        radius=25,
        outline=light_gray,
        width=3
    )
    
    # 4. ALT YAZI ALANI (isteğe bağlı - logo için gerekli değil)
    # Logo sadece sembol olarak kullanılacaksa bu kısmı atlayabiliriz
    
    # Logo dosyasını kaydet
    logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo.png')
    os.makedirs(os.path.dirname(logo_path), exist_ok=True)
    img.save(logo_path, 'PNG', quality=95)
    print(f"✅ Logo oluşturuldu: {logo_path}")
    
    # İkon versiyonu (256x256 - küçük boyut)
    icon_size = 256
    icon = img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
    icon.save(icon_path, 'PNG', quality=95)
    print(f"✅ İkon oluşturuldu: {icon_path}")
    
    # Favicon versiyonu (32x32)
    favicon = img.resize((32, 32), Image.Resampling.LANCZOS)
    favicon_path = os.path.join(os.path.dirname(__file__), 'assets', 'favicon.png')
    favicon.save(favicon_path, 'PNG', quality=95)
    print(f"✅ Favicon oluşturuldu: {favicon_path}")
    
    # Windows ICO dosyası oluştur (256x256 - Windows 10+ için yeterli)
    ico_path = os.path.join(os.path.dirname(__file__), 'assets', 'app_icon.ico')
    ico_img = img.resize((256, 256), Image.Resampling.LANCZOS)
    # ICO formatında kaydet
    ico_img.save(ico_path, format='ICO')
    print(f"✅ Windows ICO dosyası oluşturuldu: {ico_path}")
    
    return logo_path, icon_path, favicon_path, ico_path


if __name__ == '__main__':
    try:
        create_logo()
        print("\n🎨 Logo başarıyla oluşturuldu!")
        print("📁 Konum: assets/ klasörü")
    except ImportError:
        print("❌ HATA: Pillow (PIL) kütüphanesi bulunamadı!")
        print("📦 Yüklemek için: pip install Pillow")
    except Exception as e:
        print(f"❌ Hata: {e}")

