@echo off
REM InsaatMetrajPro - Basit EXE Olusturma Scripti (Spec Dosyasi Kullanir)
REM Bu script, InsaatMetrajPro.spec dosyasini kullanarak EXE olusturur

echo ========================================
echo InsaatMetrajPro - EXE Olusturma
echo ========================================
echo.

REM PyInstaller kontrolu
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

REM Spec dosyasini kullanarak EXE olustur
python -m PyInstaller InsaatMetrajPro.spec --noconfirm --clean

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
echo NOT: Ilk calistirmada Windows Defender uyari verebilir.
echo      Bu normaldir, "Daha fazla bilgi" > "Yine de calistir" secin.
echo.
pause




