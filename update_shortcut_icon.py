"""
Masaüstü kısayol ikonunu güncelle
"""

import os
from pathlib import Path

def update_shortcut_icon():
    """Masaüstü kısayolunun ikonunu özel logoyla güncelle"""
    
    # ICO dosyasının yolu
    ico_path = Path(__file__).parent / 'assets' / 'app_icon.ico'
    
    if not ico_path.exists():
        print("❌ ICO dosyası bulunamadı! Önce create_logo.py'yi çalıştırın.")
        return False
    
    # Masaüstü kısayol yolu
    desktop = Path.home() / 'Desktop'
    shortcut_path = desktop / 'İnşaat Metraj Pro.lnk'
    
    if not shortcut_path.exists():
        print("❌ Kısayol bulunamadı! Önce kısayol oluşturun.")
        return False
    
    # WScript.Shell kullanarak ikonu güncelle
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.IconLocation = str(ico_path)
        shortcut.save()
        print(f"✅ Kısayol ikonu güncellendi!")
        print(f"   İkon: {ico_path}")
        return True
    except ImportError:
        # win32com yoksa PowerShell ile yapalım
        try:
            import subprocess
            ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.IconLocation = "{ico_path}"
$Shortcut.Save()
Write-Host "Kısayol ikonu güncellendi"
'''
            result = subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"✅ Kısayol ikonu güncellendi!")
                print(f"   İkon: {ico_path}")
                return True
            else:
                print(f"❌ Hata: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Hata: {e}")
            print("\n💡 Alternatif yöntem:")
            print("1. Masaüstündeki 'İnşaat Metraj Pro.lnk' dosyasına sağ tıklayın")
            print("2. 'Özellikler' > 'Kısayol' sekmesi")
            print(f"3. 'Simge Değiştir' butonuna tıklayın")
            print(f"4. '{ico_path}' dosyasını seçin")
            return False


if __name__ == '__main__':
    update_shortcut_icon()



