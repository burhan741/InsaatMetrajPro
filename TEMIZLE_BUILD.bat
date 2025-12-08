@echo off
chcp 65001 >nul
REM Build klasörünü temizleme scripti
REM Dosya kilitli hatası alırsanız bu scripti çalıştırın

title Build Klasoru Temizleme

echo.
echo ========================================
echo   Build Klasoru Temizleme
echo ========================================
echo.

cd /d "%~dp0"

echo Lutfen bekleyin, dosyalar kontrol ediliyor...
timeout /t 3 /nobreak >nul

REM Build klasörünü temizle
if exist "build" (
    echo Build klasoru bulundu, temizleniyor...
    rmdir /s /q "build" 2>nul
    timeout /t 2 /nobreak >nul
    
    if exist "build" (
        echo.
        echo ⚠️  UYARI: Build klasoru hala mevcut!
        echo     Dosyalar baska bir program tarafindan kullaniliyor olabilir.
        echo.
        echo Cozum onerileri:
        echo 1. Tum Python process'lerini kapatip tekrar deneyin
        echo 2. Antivirus taramasini durdurun
        echo 3. Manuel olarak build klasorunu silmeyi deneyin
        echo.
        pause
        exit /b 1
    ) else (
        echo ✅ Build klasoru basariyla temizlendi!
    )
) else (
    echo ✅ Build klasoru zaten temiz!
)

echo.
echo Temizlik tamamlandi!
echo.
pause




