@echo off
REM InsaatMetrajPro - EXE Olusturma Scripti
REM Bu script, Python olmadan calisacak .exe dosyasi olusturur

echo ========================================
echo InsaatMetrajPro - EXE Olusturma
echo ========================================
echo.

REM PyInstaller kontrolu
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller bulunamadi. Yukleniyor...
    echo.
    pip install pyinstaller
    if errorlevel 1 (
        echo HATA: PyInstaller yuklenemedi!
        pause
        exit /b 1
    )
)

echo.
echo PyInstaller hazir!
echo.
echo EXE dosyasi olusturuluyor...
echo Bu islem 2-5 dakika surebilir...
echo.

REM PyInstaller ile EXE olustur
REM Windows'ta add-data format: "source;destination" (noktali virgul)
pyinstaller --name="InsaatMetrajPro" ^
    --onefile ^
    --windowed ^
    --icon=NONE ^
    --add-data "app;app" ^
    --hidden-import=PyQt6 ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    --hidden-import=reportlab ^
    --hidden-import=ezdxf ^
    --hidden-import=sqlite3 ^
    --hidden-import=app.core.database ^
    --hidden-import=app.core.calculator ^
    --hidden-import=app.core.material_calculator ^
    --hidden-import=app.ui.main_window ^
    --hidden-import=app.ui.dialogs ^
    --hidden-import=app.utils.data_loader ^
    --hidden-import=app.utils.export_manager ^
    --collect-all=PyQt6 ^
    --noconfirm ^
    --clean ^
    main.py

if errorlevel 1 (
    echo.
    echo HATA: EXE olusturulamadi!
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo EXE dosyasi basariyla olusturuldu!
echo ========================================
echo.
echo Dosya konumu: dist\InsaatMetrajPro.exe
echo.
echo Bu dosyayi baska bilgisayarlara kopyalayabilirsiniz.
echo Python yuklu olmasina gerek yok!
echo.
pause

