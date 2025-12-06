@echo off
REM InsaatMetrajPro - Otomatik Kurulum Scripti
REM Yeni bilgisayarda ilk kurulum için

echo ========================================
echo InsaatMetrajPro - Otomatik Kurulum
echo ========================================
echo.

REM Python kontrolü
python --version >nul 2>&1
if errorlevel 1 (
    echo HATA: Python bulunamadi!
    echo.
    echo Lutfen Python 3.8 veya uzeri surumu yukleyin:
    echo https://www.python.org/downloads/
    echo.
    echo Kurulum sirasinda "Add Python to PATH" secenegini isaretleyin.
    echo.
    pause
    exit /b 1
)

echo Python bulundu:
python --version
echo.

REM pip kontrolü
pip --version >nul 2>&1
if errorlevel 1 (
    echo HATA: pip bulunamadi!
    echo.
    pause
    exit /b 1
)

echo.
echo Python kutuphaneleri yukleniyor...
echo Bu islem bir kac dakika surebilir...
echo.

pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo HATA: Kutuphaneler yuklenirken hata olustu!
    echo.
    echo Manuel olarak deneyin:
    echo pip install PyQt6 pandas openpyxl reportlab ezdxf
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Kurulum tamamlandi!
echo ========================================
echo.
echo Uygulamayi baslatmak icin:
echo   python main.py
echo.
echo veya InsaatMetrajPro.bat dosyasina cift tiklayin.
echo.
pause






