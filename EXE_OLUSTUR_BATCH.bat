@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
REM ========================================
REM InsaatMetrajPro - EXE Oluşturma
REM ========================================

title InsaatMetrajPro - EXE Oluşturma

echo.
echo ========================================
echo   InsaatMetrajPro - EXE Oluşturma
echo ========================================
echo.
echo Bu işlem 2-5 dakika sürebilir...
echo Lütfen bu pencereyi KAPATMAYIN!
echo.
echo ========================================
echo.

REM Proje klasörüne git
cd /d "%~dp0"

REM PyInstaller kontrolü
echo [1/4] PyInstaller kontrol ediliyor...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller bulunamadi. Yukleniyor...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo.
        echo ❌ HATA: PyInstaller yuklenemedi!
        echo.
        pause
        exit /b 1
    )
)
echo ✅ PyInstaller hazir!
echo.

REM Gerekli modüllerin kontrolü
echo [2/4] Gerekli moduller kontrol ediliyor...
python -c "import PyQt6; import pandas; import ezdxf" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Bazı moduller eksik olabilir. Devam ediliyor...
)
echo ✅ Moduller hazir!
echo.

REM Eski build dosyalarını temizle
echo [3/4] Eski dosyalar temizleniyor...
echo Lutfen bekleyin, dosyalar kontrol ediliyor...
timeout /t 2 /nobreak >nul

REM Build klasörünü güvenli şekilde temizle
if exist "build" (
    echo Build klasoru temizleniyor...
    rmdir /s /q "build" 2>nul
    timeout /t 1 /nobreak >nul
    if exist "build" (
        echo ⚠️  Build klasoru kilitli olabilir. Manuel olarak silmeyi deneyin.
        echo     Klasor: %CD%\build
        echo.
    )
)

REM Eski EXE'yi temizle
if exist "dist\InsaatMetrajPro.exe" (
    echo Eski EXE dosyasi kaldiriliyor...
    del /q "dist\InsaatMetrajPro.exe" 2>nul
    timeout /t 1 /nobreak >nul
)

echo ✅ Temizlik tamamlandi!
echo.

REM EXE oluştur
echo [4/4] EXE dosyasi olusturuluyor...
echo Bu islem biraz zaman alabilir, lutfen bekleyin...
echo.
echo ========================================
echo.

python -m PyInstaller InsaatMetrajPro.spec --noconfirm --clean

if errorlevel 1 (
    echo.
    echo ========================================
    echo ❌ HATA: EXE olusturulamadi!
    echo ========================================
    echo.
    echo Lutfen hata mesajlarini kontrol edin.
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ BASARILI: EXE olusturuldu!
echo ========================================
echo.

REM EXE dosyasını kontrol et
if exist "dist\InsaatMetrajPro.exe" (
    echo 📁 Dosya konumu:
    echo    %CD%\dist\InsaatMetrajPro.exe
    echo.
    
    REM Dosya boyutunu göster
    for %%A in ("dist\InsaatMetrajPro.exe") do (
        set /a size_mb=%%~zA/1024/1024
        echo 📦 Dosya boyutu: !size_mb! MB (yaklasik)
    )
    echo.
    echo ========================================
    echo ✅ HAZIR!
    echo ========================================
    echo.
    echo Bu EXE dosyasini baska bilgisayarlara kopyalayabilirsiniz.
    echo Python yuklu olmasina gerek yok!
    echo.
    echo NOT: Ilk calistirmada Windows Defender uyari verebilir.
    echo      "Daha fazla bilgi" ^> "Yine de calistir" secin.
    echo.
    
    REM Klasörü aç
    echo Klasoru acmak ister misiniz? (E/H)
    choice /C EH /N /M "Seciminiz"
    if errorlevel 2 goto :end
    if errorlevel 1 explorer dist
    
) else (
    echo.
    echo ⚠️  UYARI: EXE dosyasi bulunamadi!
    echo     Lutfen hata mesajlarini kontrol edin.
    echo.
)

:end
echo.
pause

