"""
Yeni logo ve arka plan görselleri oluştur
- Mavili blueprint: Kısayol logosu
- Siyahlı wireframe şehir: Arka plan
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_blueprint_logo():
    """Mavili blueprint logo oluştur (kısayol için)"""
    
    # Logo boyutları
    width, height = 512, 512
    img = Image.new('RGB', (width, height), color='#0a0a1a')  # Koyu mavi-siyah
    draw = ImageDraw.Draw(img)
    
    # Renkler
    bright_blue = '#00BFFF'  # Parlak mavi
    orange = '#FF6F00'  # Turuncu
    dark_bg = '#0a0a1a'  # Koyu arka plan
    
    # Merkez noktası
    center_x, center_y = width // 2, height // 2
    
    # 1. Circuit board pattern (alt kısım)
    circuit_spacing = 20
    for y in range(height - 100, height, circuit_spacing):
        for x in range(0, width, circuit_spacing):
            # Circuit node
            draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=bright_blue)
            # Horizontal line
            if x < width - circuit_spacing:
                draw.line([x, y, x + circuit_spacing, y], fill=bright_blue, width=1)
            # Vertical line
            if y < height - circuit_spacing:
                draw.line([x, y, x, y + circuit_spacing], fill=bright_blue, width=1)
    
    # 2. Blueprint scroll (sol taraf)
    scroll_x = 80
    scroll_y = center_y - 80
    scroll_width = 180
    scroll_height = 240
    
    # Scroll body (rolled up)
    draw.ellipse([scroll_x - 20, scroll_y, scroll_x + 20, scroll_y + scroll_height], 
                fill=bright_blue, outline=bright_blue, width=2)
    
    # Unrolled blueprint (sağa doğru)
    blueprint_x = scroll_x + 20
    blueprint_y = scroll_y + 40
    blueprint_w = 200
    blueprint_h = 160
    
    # Blueprint background (yarı saydam mavi)
    blueprint_overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    blueprint_draw = ImageDraw.Draw(blueprint_overlay)
    blueprint_draw.rectangle([blueprint_x, blueprint_y, blueprint_x + blueprint_w, blueprint_y + blueprint_h],
                           fill=(0, 191, 255, 100))  # Yarı saydam mavi
    
    # Blueprint grid pattern
    grid_spacing = 15
    for x in range(blueprint_x, blueprint_x + blueprint_w, grid_spacing):
        blueprint_draw.line([x, blueprint_y, x, blueprint_y + blueprint_h], 
                           fill=(0, 191, 255, 200), width=1)
    for y in range(blueprint_y, blueprint_y + blueprint_h, grid_spacing):
        blueprint_draw.line([blueprint_x, y, blueprint_x + blueprint_w, y], 
                           fill=(0, 191, 255, 200), width=1)
    
    # Mimari plan çizgileri (basitleştirilmiş)
    room_size = 40
    # Oda 1
    blueprint_draw.rectangle([blueprint_x + 20, blueprint_y + 20, 
                            blueprint_x + 20 + room_size, blueprint_y + 20 + room_size],
                           outline=(0, 191, 255, 255), width=2)
    # Oda 2
    blueprint_draw.rectangle([blueprint_x + 70, blueprint_y + 20, 
                            blueprint_x + 70 + room_size, blueprint_y + 20 + room_size],
                           outline=(0, 191, 255, 255), width=2)
    # Koridor
    blueprint_draw.rectangle([blueprint_x + 20, blueprint_y + 70, 
                            blueprint_x + 70 + room_size, blueprint_y + 90],
                           outline=(0, 191, 255, 255), width=2)
    
    # Blueprint overlay'i ana görsele ekle
    img = Image.alpha_composite(img.convert('RGBA'), blueprint_overlay).convert('RGB')
    
    # 3. Wireframe building (sağ taraf)
    building_x = center_x + 40
    building_y = center_y - 60
    building_width = 140
    building_height = 200
    
    # Building wireframe (mavi çizgiler)
    # Ön yüz
    draw.rectangle([building_x, building_y, building_x + building_width, building_y + building_height],
                  outline=bright_blue, width=2, fill=None)
    
    # Grid pattern (wireframe)
    for i in range(1, 4):
        y = building_y + (building_height // 4) * i
        draw.line([building_x, y, building_x + building_width, y], fill=bright_blue, width=1)
    
    for i in range(1, 3):
        x = building_x + (building_width // 3) * i
        draw.line([x, building_y, x, building_y + building_height], fill=bright_blue, width=1)
    
    # 3D perspektif çizgileri (sağa doğru)
    depth = 30
    # Üst köşeler
    draw.line([building_x + building_width, building_y, 
              building_x + building_width + depth, building_y - depth], fill=bright_blue, width=1)
    draw.line([building_x + building_width, building_y + building_height, 
              building_x + building_width + depth, building_y + building_height - depth], fill=bright_blue, width=1)
    # Arka yüz çizgileri
    draw.line([building_x + building_width + depth, building_y - depth, 
              building_x + building_width + depth, building_y + building_height - depth], fill=bright_blue, width=1)
    draw.line([building_x + building_width, building_y + building_height, 
              building_x + building_width + depth, building_y + building_height - depth], fill=bright_blue, width=1)
    
    # 4. Magnifying glass (alt kısım, turuncu)
    magnify_x = center_x - 60
    magnify_y = height - 120
    magnify_size = 50
    
    # Magnifying glass circle
    draw.ellipse([magnify_x, magnify_y, magnify_x + magnify_size, magnify_y + magnify_size],
                outline=orange, width=3, fill=None)
    
    # Magnifying glass handle
    handle_x = magnify_x + magnify_size - 10
    handle_y = magnify_y + magnify_size - 10
    draw.line([handle_x, handle_y, handle_x + 20, handle_y + 20], fill=orange, width=4)
    
    # Arrow (sağa doğru)
    arrow_start_x = magnify_x + magnify_size + 10
    arrow_start_y = magnify_y + magnify_size // 2
    arrow_length = 60
    
    draw.line([arrow_start_x, arrow_start_y, arrow_start_x + arrow_length, arrow_start_y], 
             fill=orange, width=3)
    # Arrow head
    arrow_points = [
        (arrow_start_x + arrow_length, arrow_start_y),
        (arrow_start_x + arrow_length - 10, arrow_start_y - 5),
        (arrow_start_x + arrow_length - 10, arrow_start_y + 5)
    ]
    draw.polygon(arrow_points, fill=orange)
    
    # 5. Çerçeve (beyaz, yuvarlatılmış köşeler)
    border_width = 8
    draw.rounded_rectangle(
        [border_width, border_width, width - border_width, height - border_width],
        radius=20,
        outline='#FFFFFF',
        width=border_width
    )
    
    # Logo dosyasını kaydet
    logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'blueprint_logo.png')
    os.makedirs(os.path.dirname(logo_path), exist_ok=True)
    img.save(logo_path, 'PNG', quality=95)
    print(f"✅ Blueprint logo oluşturuldu: {logo_path}")
    
    # ICO dosyası oluştur
    ico_img = img.resize((256, 256), Image.Resampling.LANCZOS)
    ico_path = os.path.join(os.path.dirname(__file__), 'assets', 'app_icon.ico')
    ico_img.save(ico_path, format='ICO')
    print(f"✅ ICO dosyası oluşturuldu: {ico_path}")
    
    return logo_path, ico_path


def create_wireframe_background():
    """Siyahlı wireframe şehir arka planı oluştur"""
    
    width, height = 1920, 1080  # Full HD
    img = Image.new('RGB', (width, height), color='#0a0a0a')  # Çok koyu gri-siyah
    draw = ImageDraw.Draw(img)
    
    # Renkler
    wireframe_color = '#2a3a4a'  # Açık gri-mavi (wireframe çizgiler)
    data_point_color = '#4a5a6a'  # Biraz daha açık (veri noktaları)
    dark_bg = '#0a0a0a'  # Çok koyu arka plan
    
    # Isometric grid oluştur
    grid_size = 80
    angle = 30  # Isometric açı
    
    # Isometric grid çizgileri
    for i in range(-height // grid_size, width // grid_size + height // grid_size):
        # Diagonal lines (soldan sağa)
        x1 = i * grid_size
        y1 = 0
        x2 = x1 + height * 1.5
        y2 = height
        if x2 > 0 and x1 < width:
            draw.line([max(0, x1), max(0, y1), min(width, x2), min(height, y2)], 
                     fill=wireframe_color, width=1)
    
    for i in range(-width // grid_size, height // grid_size + width // grid_size):
        # Diagonal lines (sağdan sola)
        x1 = width
        y1 = i * grid_size
        x2 = 0
        y2 = y1 + width * 1.5
        if y2 > 0 and y1 < height:
            draw.line([max(0, x1), max(0, y1), min(width, x2), min(height, y2)], 
                     fill=wireframe_color, width=1)
    
    # Wireframe binalar (isometric)
    building_positions = [
        (200, 300, 120, 180),  # x, y, width, height
        (400, 250, 100, 200),
        (600, 320, 140, 160),
        (850, 280, 110, 190),
        (1100, 310, 130, 170),
        (1350, 270, 120, 200),
        (300, 500, 100, 150),
        (550, 480, 120, 170),
        (800, 520, 110, 160),
        (1050, 490, 130, 180),
        (1300, 510, 100, 190),
    ]
    
    for bx, by, bw, bh in building_positions:
        # Isometric building (basitleştirilmiş)
        # Ön yüz
        draw.rectangle([bx, by, bx + bw, by + bh], outline=wireframe_color, width=1, fill=None)
        
        # Grid pattern
        for i in range(1, 4):
            y = by + (bh // 4) * i
            draw.line([bx, y, bx + bw, y], fill=wireframe_color, width=1)
        for i in range(1, 3):
            x = bx + (bw // 3) * i
            draw.line([x, by, x, by + bh], fill=wireframe_color, width=1)
        
        # 3D perspektif (isometric)
        depth = 20
        # Üst köşeler
        draw.line([bx + bw, by, bx + bw + depth, by - depth], fill=wireframe_color, width=1)
        draw.line([bx + bw, by + bh, bx + bw + depth, by + bh - depth], fill=wireframe_color, width=1)
        # Arka yüz
        draw.line([bx + bw + depth, by - depth, bx + bw + depth, by + bh - depth], 
                 fill=wireframe_color, width=1)
    
    # Veri noktaları (crosshair + sayılar)
    data_points = [
        (250, 350, "337.1110 x 9.0078"),
        (450, 300, "17.6416 x 8.931"),
        (650, 370, "382.9464 38.6724"),
        (900, 330, "3.1014 x 9.129"),
        (1150, 360, "47.8947 x 1.451"),
        (350, 550, "128.456 x 5.234"),
        (600, 530, "89.123 x 12.567"),
        (850, 570, "234.789 x 8.901"),
    ]
    
    for dx, dy, text in data_points:
        # Crosshair
        size = 8
        draw.line([dx - size, dy, dx + size, dy], fill=data_point_color, width=2)
        draw.line([dx, dy - size, dx, dy + size], fill=data_point_color, width=2)
        
        # Text (basitleştirilmiş - küçük nokta)
        draw.ellipse([dx - 2, dy - 2, dx + 2, dy + 2], fill=data_point_color)
    
    # Yol çizgileri (grid üzerinde)
    road_y = height - 200
    draw.line([0, road_y, width, road_y], fill=wireframe_color, width=2)
    
    # Kaydet
    bg_path = os.path.join(os.path.dirname(__file__), 'assets', 'wireframe_background.jpg')
    os.makedirs(os.path.dirname(bg_path), exist_ok=True)
    img.save(bg_path, 'JPEG', quality=90)
    print(f"✅ Wireframe arka plan oluşturuldu: {bg_path}")
    
    # Splash screen için küçük versiyon
    splash_img = img.resize((800, 600), Image.Resampling.LANCZOS)
    splash_path = os.path.join(os.path.dirname(__file__), 'assets', 'splash.jpg')
    splash_img.save(splash_path, 'JPEG', quality=90)
    print(f"✅ Splash screen arka planı oluşturuldu: {splash_path}")
    
    return bg_path, splash_path


if __name__ == '__main__':
    try:
        print("🎨 Logo ve arka plan görselleri oluşturuluyor...\n")
        create_blueprint_logo()
        print()
        create_wireframe_background()
        print("\n✅ Tüm görseller başarıyla oluşturuldu!")
    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        traceback.print_exc()




