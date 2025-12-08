@echo off
REM InsaatMetrajPro - EXE Olusturma Scripti
REM Bu script, Python olmadan calisacak .exe dosyasi olusturur

echo ========================================
echo InsaatMetrajPro - EXE Olusturma
echo ========================================
echo.

REM PyInstaller kontrolu (Python modulu olarak - PATH sorunu cozumu)
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller bulunamadi. Yukleniyor...
    echo.
    python -m pip install pyinstaller
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

REM PyInstaller ile EXE olustur (Python modulu olarak - PATH sorunu cozumu)
REM Windows'ta add-data format: "source;destination" (noktali virgul)
REM Icon kontrolu
if exist "assets\app_icon.ico" (
    set ICON_PARAM=--icon=assets\app_icon.ico
) else (
    set ICON_PARAM=
)

python -m PyInstaller --name="InsaatMetrajPro" ^
    --onefile ^
    --windowed ^
    %ICON_PARAM% ^
    --add-data "app;app" ^
    --add-data "assets;assets" ^
    --add-data "data;data" ^
    --hidden-import=PyQt6 ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    --hidden-import=reportlab ^
    --hidden-import=ezdxf ^
    --hidden-import=sqlite3 ^
    --hidden-import=pdfplumber ^
    --hidden-import=matplotlib ^
    --hidden-import=app.core.database ^
    --hidden-import=app.core.calculator ^
    --hidden-import=app.core.material_calculator ^
    --hidden-import=app.core.dxf_engine ^
    --hidden-import=app.core.cad_manager ^
    --hidden-import=app.ui.main_window ^
    --hidden-import=app.ui.dialogs ^
    --hidden-import=app.ui.startup_dialog ^
    --hidden-import=app.ui.taseron_window ^
    --hidden-import=app.ui.styles ^
    --hidden-import=app.utils.data_loader ^
    --hidden-import=app.utils.export_manager ^
    --hidden-import=app.utils.helpers ^
    --hidden-import=app.utils.pdf_importer ^
    --hidden-import=app.data.konut_is_kalemleri ^
    --hidden-import=app.data.malzeme_formulleri ^
    --hidden-import=app.data.fire_oranlari ^
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

