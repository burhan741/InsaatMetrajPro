"""
Modern bina görseline uygun arka plan oluştur
Gün batımı gökyüzü, modern mimari teması
"""

from PIL import Image, ImageDraw, ImageFilter
import os

def create_background_image():
    """Gün batımı gökyüzü ve modern mimari temasında arka plan oluştur"""
    
    width, height = 1920, 1080  # Full HD
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    
    # Gün batımı gökyüzü gradient (pembe, turuncu, mor tonları)
    # Üstten alta gradient
    for y in range(height):
        ratio = y / height
        
        # Üst kısım: Açık mavi-mor
        if ratio < 0.3:
            r = int(135 + ratio * 50)  # 135-185
            g = int(206 + ratio * 30)  # 206-236
            b = int(250 - ratio * 50)  # 250-200
        # Orta kısım: Turuncu-pembe
        elif ratio < 0.6:
            local_ratio = (ratio - 0.3) / 0.3
            r = int(255 - local_ratio * 40)  # 255-215
            g = int(140 + local_ratio * 50)  # 140-190
            b = int(100 + local_ratio * 30)  # 100-130
        # Alt kısım: Koyu turuncu-mor
        else:
            local_ratio = (ratio - 0.6) / 0.4
            r = int(215 - local_ratio * 60)  # 215-155
            g = int(190 - local_ratio * 80)  # 190-110
            b = int(130 + local_ratio * 50)  # 130-180
        
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Bulut efektleri (yumuşak, organik)
    cloud_img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    cloud_draw = ImageDraw.Draw(cloud_img)
    
    # Pembe-turuncu bulutlar
    cloud_colors = [
        (255, 182, 193, 80),  # Açık pembe
        (255, 160, 122, 70),  # Turuncu
        (221, 160, 221, 60),  # Mor-pembe
    ]
    
    import random
    random.seed(42)  # Tutarlılık için
    
    for i, color in enumerate(cloud_colors):
        for _ in range(15):
            x = random.randint(0, width)
            y = random.randint(0, int(height * 0.6))
            size = random.randint(200, 400)
            # Yumuşak bulut (eliptik)
            cloud_draw.ellipse(
                [x - size//2, y - size//4, x + size//2, y + size//4],
                fill=color
            )
    
    # Bulutları yumuşat
    cloud_img = cloud_img.filter(ImageFilter.GaussianBlur(radius=50))
    
    # Bulutları ana görsele ekle
    img = Image.alpha_composite(img.convert('RGBA'), cloud_img).convert('RGB')
    
    # Alt kısımda hafif koyu gradient (zemin efekti)
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(int(height * 0.7), height):
        alpha = int(30 * (y - height * 0.7) / (height * 0.3))
        overlay_draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    
    # Kaydet
    bg_path = os.path.join(os.path.dirname(__file__), 'assets', 'background.jpg')
    os.makedirs(os.path.dirname(bg_path), exist_ok=True)
    img.save(bg_path, 'JPEG', quality=90)
    print(f"✅ Arka plan oluşturuldu: {bg_path}")
    
    # Splash screen için küçük versiyon (800x600)
    splash_img = img.resize((800, 600), Image.Resampling.LANCZOS)
    splash_path = os.path.join(os.path.dirname(__file__), 'assets', 'splash.jpg')
    splash_img.save(splash_path, 'JPEG', quality=90)
    print(f"✅ Splash screen arka planı oluşturuldu: {splash_path}")
    
    return bg_path, splash_path


if __name__ == '__main__':
    try:
        create_background_image()
        print("\n🎨 Arka plan görselleri başarıyla oluşturuldu!")
    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        traceback.print_exc()



