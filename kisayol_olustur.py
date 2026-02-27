"""
QUANTIX PRO - Masaüstü Kısayolu Oluşturucu
Bu scripti bir kere çalıştırın, masaüstüne logolu kısayol oluşturur.
"""
import os
import sys

desktop = os.path.join(os.path.expanduser("~"), "Desktop")
assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
bat_path = os.path.join(desktop, "QuantixPro_Calistir.bat")
ico_path = os.path.join(assets, "quantix_icon.ico")
png_path = os.path.join(assets, "quantix_logo.png")
lnk_path = os.path.join(desktop, "QUANTIX PRO.lnk")

# 1. PNG -> ICO dönüşümü
print("[1/3] Logo ICO'ya dönüştürülüyor...")
try:
    from PIL import Image
    img = Image.open(png_path)
    img = img.convert("RGBA")
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f" OK: {ico_path}")
except ImportError:
    print(" Pillow yüklü değil, pip install Pillow yapılıyor...")
    os.system(f'"{sys.executable}" -m pip install Pillow')
    from PIL import Image
    img = Image.open(png_path)
    img = img.convert("RGBA")
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f" OK: {ico_path}")
except Exception as e:
    print(f" HATA: {e}")
    # Mevcut app_icon.ico'yu kullan
    fallback = os.path.join(assets, "app_icon.ico")
    if os.path.exists(fallback):
        ico_path = fallback
        print(f" Yedek ikon kullanılıyor: {ico_path}")

# 2. Masaüstü kısayolu oluştur
print("[2/3] Masaüstü kısayolu oluşturuluyor...")
try:
    import win32com.client
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(lnk_path)
    shortcut.Targetpath = bat_path
    shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(__file__))
    shortcut.IconLocation = f"{ico_path},0"
    shortcut.Description = "QUANTIX PRO - İnşaat Metraj Uygulaması"
    shortcut.WindowStyle = 7 # Minimized (bat penceresi gizli)
    shortcut.save()
    print(f" OK: {lnk_path}")
except Exception as e:
    print(f" HATA: {e}")

# 3. Eski bat dosyasını sil
print("[3/3] Eski dosya temizleniyor...")
eski_bat = os.path.join(desktop, "InsaatMetrajPro_Calistir.bat")
if os.path.exists(eski_bat):
    try:
        os.remove(eski_bat)
        print(f" Silindi: {eski_bat}")
    except Exception as e:
        print(f" Silinemedi: {e}")
        print(f" Lütfen manuel silin: {eski_bat}")
else:
    print(" Eski bat dosyası zaten yok.")

print("\n" + "=" * 50)
print(" QUANTIX PRO kısayolu masaüstüne eklendi!")
print(" Artık masaüstündeki 'QUANTIX PRO' ikonuna")
print(" çift tıklayarak programı açabilirsiniz.")
print("=" * 50)
input("\nKapatmak için ENTER'a basın...")
