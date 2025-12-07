#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test script to debug startup issues"""

import sys
import traceback

print("=" * 60)
print("TEST 1: Import kontrolü")
print("=" * 60)

try:
    print("PyQt6 import ediliyor...")
    from PyQt6.QtWidgets import QApplication
    print("✓ PyQt6 başarıyla import edildi")
except Exception as e:
    print(f"✗ PyQt6 import hatası: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    print("\nStartupDialog import ediliyor...")
    from app.ui.startup_dialog import StartupDialog
    print("✓ StartupDialog başarıyla import edildi")
except Exception as e:
    print(f"✗ StartupDialog import hatası: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    print("\nTaseronWindow import ediliyor...")
    from app.ui.taseron_window import TaseronWindow
    print("✓ TaseronWindow başarıyla import edildi")
except Exception as e:
    print(f"✗ TaseronWindow import hatası: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    print("\nMainWindow import ediliyor...")
    from app.ui.main_window import MainWindow
    print("✓ MainWindow başarıyla import edildi")
except Exception as e:
    print(f"✗ MainWindow import hatası: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    print("\nDatabaseManager import ediliyor...")
    from app.core.database import DatabaseManager
    print("✓ DatabaseManager başarıyla import edildi")
except Exception as e:
    print(f"✗ DatabaseManager import hatası: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("TEST 2: QApplication oluşturma")
print("=" * 60)

try:
    app = QApplication(sys.argv)
    print("✓ QApplication başarıyla oluşturuldu")
except Exception as e:
    print(f"✗ QApplication oluşturma hatası: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("TEST 3: StartupDialog oluşturma")
print("=" * 60)

try:
    startup = StartupDialog()
    print("✓ StartupDialog başarıyla oluşturuldu")
    print("NOT: Dialog açılacak, bir seçim yapın...")
    result = startup.exec()
    print(f"✓ Dialog sonucu: {result}")
    print(f"✓ Seçilen user_type: {startup.user_type}")
except Exception as e:
    print(f"✗ StartupDialog oluşturma/çalıştırma hatası: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("TEST 4: DatabaseManager oluşturma")
print("=" * 60)

try:
    db = DatabaseManager()
    print("✓ DatabaseManager başarıyla oluşturuldu")
except Exception as e:
    print(f"✗ DatabaseManager oluşturma hatası: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("TEST 5: Pencere oluşturma")
print("=" * 60)

user_type = startup.user_type
if user_type == 'taseron':
    try:
        print("TaseronWindow oluşturuluyor...")
        window = TaseronWindow(db=db)
        print("✓ TaseronWindow başarıyla oluşturuldu")
        window.show()
        print("✓ Pencere gösterildi")
    except Exception as e:
        print(f"✗ TaseronWindow oluşturma hatası: {e}")
        traceback.print_exc()
        sys.exit(1)
else:
    try:
        print("MainWindow oluşturuluyor...")
        window = MainWindow(user_type=user_type)
        print("✓ MainWindow başarıyla oluşturuldu")
        window.show()
        print("✓ Pencere gösterildi")
    except Exception as e:
        print(f"✗ MainWindow oluşturma hatası: {e}")
        traceback.print_exc()
        sys.exit(1)

print("\n" + "=" * 60)
print("TÜM TESTLER BAŞARILI!")
print("=" * 60)
print("\nUygulama çalışıyor. Kapatmak için pencereyi kapatın...")

sys.exit(app.exec())

