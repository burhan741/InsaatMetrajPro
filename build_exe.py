#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EXE oluşturma scripti"""
import subprocess
import sys
import os

def build_exe():
    """PyInstaller ile EXE oluştur"""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("=" * 60)
    print("InsaatMetrajPro - EXE Oluşturma")
    print("=" * 60)
    print()
    
    # PyInstaller komutu
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "InsaatMetrajPro.spec",
        "--noconfirm",
        "--clean"
    ]
    
    print("Komut:", " ".join(cmd))
    print()
    print("EXE oluşturuluyor... Bu işlem 2-5 dakika sürebilir...")
    print()
    
    # Komutu çalıştır
    try:
        result = subprocess.run(
            cmd,
            capture_output=False,  # Çıktıyı direkt göster
            text=True,
            check=True
        )
        print()
        print("=" * 60)
        print("✅ EXE başarıyla oluşturuldu!")
        print("=" * 60)
        print()
        print("Dosya konumu: dist\\InsaatMetrajPro.exe")
        print()
        
        # Dosya boyutunu kontrol et
        exe_path = os.path.join("dist", "InsaatMetrajPro.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"EXE boyutu: {size_mb:.2f} MB")
        else:
            print("⚠️ UYARI: EXE dosyası bulunamadı!")
            
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 60)
        print("❌ HATA: EXE oluşturulamadı!")
        print("=" * 60)
        print(f"Çıkış kodu: {e.returncode}")
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ HATA:", str(e))
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    build_exe()




