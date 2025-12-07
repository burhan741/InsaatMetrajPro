"""
Kullanıcı Tipi İkonları Oluşturucu
Müteahhit ve Taşeron ikonları oluşturur
"""

from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

def create_muteahhit_icon():
    """Müteahhit ikonu: Beyaz baretli, takım elbiseli mühendis"""
    size = 512
    img = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))  # Şeffaf arka plan
    draw = ImageDraw.Draw(img)
    
    center_x, center_y = size // 2, size // 2
    
    # Vücut (takım elbise - koyu mavi)
    body_y = center_y + 80
    body_width = 180
    body_height = 220
    
    # Takım elbise ceketi
    draw.ellipse(
        [center_x - body_width//2, body_y - body_height//2,
         center_x + body_width//2, body_y + body_height//2],
        fill='#1a237e',  # Koyu mavi takım elbise
        outline='#0d47a1',
        width=3
    )
    
    # Kafa
    head_radius = 70
    head_y = center_y - 50
    draw.ellipse(
        [center_x - head_radius, head_y - head_radius,
         center_x + head_radius, head_y + head_radius],
        fill='#ffdbac',  # Ten rengi
        outline='#d4a574',
        width=2
    )
    
    # Beyaz baret
    helmet_y = head_y - head_radius - 20
    helmet_width = 140
    helmet_height = 50
    draw.ellipse(
        [center_x - helmet_width//2, helmet_y - helmet_height//2,
         center_x + helmet_width//2, helmet_y + helmet_height//2],
        fill='#ffffff',  # Beyaz baret
        outline='#cccccc',
        width=3
    )
    
    # Baret bandı (mavi)
    band_y = helmet_y
    draw.ellipse(
        [center_x - helmet_width//2 + 10, band_y - 8,
         center_x + helmet_width//2 - 10, band_y + 8],
        fill='#1565c0',
        outline=None
    )
    
    # Gözler
    eye_size = 8
    draw.ellipse([center_x - 25, head_y - 10, center_x - 25 + eye_size, head_y - 10 + eye_size], fill='#000000')
    draw.ellipse([center_x + 17, head_y - 10, center_x + 17 + eye_size, head_y - 10 + eye_size], fill='#000000')
    
    # Gülümseme
    draw.arc([center_x - 20, head_y + 5, center_x + 20, head_y + 25], start=0, end=180, fill='#000000', width=3)
    
    # Kravat (kırmızı)
    tie_width = 20
    tie_height = 80
    draw.polygon([
        (center_x, body_y - body_height//2 + 30),
        (center_x - tie_width//2, body_y - body_height//2 + 30 + tie_height),
        (center_x + tie_width//2, body_y - body_height//2 + 30 + tie_height)
    ], fill='#c62828', outline='#b71c1c', width=2)
    
    # Planlar (mavi rulo)
    plans_x = center_x - 100
    plans_y = body_y - 20
    plans_width = 40
    plans_height = 60
    draw.ellipse(
        [plans_x - plans_width//2, plans_y - plans_height//2,
         plans_x + plans_width//2, plans_y + plans_height//2],
        fill='#1565c0',
        outline='#0d47a1',
        width=2
    )
    # Plan çizgileri
    for i in range(3):
        y = plans_y - plans_height//2 + 15 + i * 10
        draw.line([(plans_x - 15, y), (plans_x + 15, y)], fill='#ffffff', width=1)
    
    # Kol (planları tutuyor)
    arm_x = center_x - 60
    arm_y = body_y - 30
    draw.ellipse(
        [arm_x - 15, arm_y - 15,
         arm_x + 15, arm_y + 15],
        fill='#ffdbac',
        outline='#d4a574',
        width=2
    )
    
    return img

def create_taseron_icon():
    """Taşeron ikonu: Sarı baretli (TS logosu), turuncu yelekli işçi"""
    size = 512
    img = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))  # Şeffaf arka plan
    draw = ImageDraw.Draw(img)
    
    center_x, center_y = size // 2, size // 2
    
    # Vücut (turuncu yelek)
    body_y = center_y + 80
    body_width = 200
    body_height = 240
    
    # Turuncu yelek
    draw.ellipse(
        [center_x - body_width//2, body_y - body_height//2,
         center_x + body_width//2, body_y + body_height//2],
        fill='#ff6f00',  # Turuncu yelek
        outline='#e65100',
        width=3
    )
    
    # Yelek yansıtıcı şeritler (beyaz)
    for i in range(3):
        y = body_y - body_height//2 + 40 + i * 50
        draw.ellipse(
            [center_x - body_width//2 + 20, y - 8,
             center_x + body_width//2 - 20, y + 8],
            fill='#ffffff',
            outline='#cccccc',
            width=2
        )
    
    # Kafa
    head_radius = 75
    head_y = center_y - 50
    draw.ellipse(
        [center_x - head_radius, head_y - head_radius,
         center_x + head_radius, head_y + head_radius],
        fill='#ffdbac',  # Ten rengi
        outline='#d4a574',
        width=2
    )
    
    # Sarı baret
    helmet_y = head_y - head_radius - 25
    helmet_width = 150
    helmet_height = 55
    draw.ellipse(
        [center_x - helmet_width//2, helmet_y - helmet_height//2,
         center_x + helmet_width//2, helmet_y + helmet_height//2],
        fill='#ffd600',  # Sarı baret
        outline='#f9a825',
        width=3
    )
    
    # TS logosu (baret üzerinde - kırmızı kare içinde)
    logo_size = 35
    logo_x = center_x
    logo_y = helmet_y - 5
    # Kırmızı kare
    draw.rectangle(
        [logo_x - logo_size//2, logo_y - logo_size//2,
         logo_x + logo_size//2, logo_y + logo_size//2],
        fill='#d32f2f',
        outline='#b71c1c',
        width=2
    )
    # TS harfleri (beyaz)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    draw.text((logo_x - 8, logo_y - 10), "TS", fill='#ffffff', font=font, anchor="mm")
    
    # Gözler
    eye_size = 10
    draw.ellipse([center_x - 28, head_y - 8, center_x - 28 + eye_size, head_y - 8 + eye_size], fill='#000000')
    draw.ellipse([center_x + 18, head_y - 8, center_x + 18 + eye_size, head_y - 8 + eye_size], fill='#000000')
    
    # Gülümseme
    draw.arc([center_x - 25, head_y + 8, center_x + 25, head_y + 28], start=0, end=180, fill='#000000', width=3)
    
    # Alet çantası (mavi-turuncu)
    toolbox_x = center_x - 110
    toolbox_y = body_y + 20
    toolbox_width = 50
    toolbox_height = 40
    draw.rectangle(
        [toolbox_x - toolbox_width//2, toolbox_y - toolbox_height//2,
         toolbox_x + toolbox_width//2, toolbox_y + toolbox_height//2],
        fill='#1565c0',
        outline='#0d47a1',
        width=2
    )
    # Çanta kolu
    draw.rectangle(
        [toolbox_x - toolbox_width//2 - 5, toolbox_y - 15,
         toolbox_x - toolbox_width//2 + 5, toolbox_y + 15],
        fill='#ff6f00',
        outline='#e65100',
        width=2
    )
    
    # Kol (çantayı tutuyor)
    arm_x = center_x - 70
    arm_y = body_y - 10
    draw.ellipse(
        [arm_x - 18, arm_y - 18,
         arm_x + 18, arm_y + 18],
        fill='#ffdbac',
        outline='#d4a574',
        width=2
    )
    
    # Çay (sağ elde)
    tea_x = center_x + 100
    tea_y = body_y - 20
    # Çay bardağı
    draw.ellipse(
        [tea_x - 15, tea_y - 20,
         tea_x + 15, tea_y + 20],
        fill='#e3f2fd',
        outline='#90caf9',
        width=2
    )
    # Çay sıvısı
    draw.ellipse(
        [tea_x - 12, tea_y - 15,
         tea_x + 12, tea_y + 5],
        fill='#8d6e63',
        outline=None
    )
    
    return img

def create_icons():
    """Tüm ikonları oluştur"""
    assets_dir = Path(__file__).parent / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    # Müteahhit ikonu
    muteahhit_img = create_muteahhit_icon()
    muteahhit_path = assets_dir / "muteahhit_icon.png"
    muteahhit_img.save(muteahhit_path, 'PNG', quality=95)
    print(f"✅ Müteahhit ikonu oluşturuldu: {muteahhit_path}")
    
    # Taşeron ikonu
    taseron_img = create_taseron_icon()
    taseron_path = assets_dir / "taseron_icon.png"
    taseron_img.save(taseron_path, 'PNG', quality=95)
    print(f"✅ Taşeron ikonu oluşturuldu: {taseron_path}")
    
    return muteahhit_path, taseron_path

if __name__ == '__main__':
    try:
        create_icons()
        print("\n🎨 İkonlar başarıyla oluşturuldu!")
        print("📁 Konum: assets/ klasörü")
    except ImportError:
        print("❌ HATA: Pillow (PIL) kütüphanesi bulunamadı!")
        print("📦 Yüklemek için: pip install Pillow")
    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        traceback.print_exc()


