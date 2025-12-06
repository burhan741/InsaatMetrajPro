@echo off
REM InsaatMetrajPro - EXE ile Test Paketi Hazirlama
REM Bu script, EXE dosyasi ile birlikte test paketi hazirlar

echo ========================================
echo InsaatMetrajPro - EXE Test Paketi
echo ========================================
echo.

REM Once EXE olusturulmus mu kontrol et
if not exist "dist\InsaatMetrajPro.exe" (
    if not exist "dist\InsaatMetrajPro\InsaatMetrajPro.exe" (
        echo HATA: EXE dosyasi bulunamadi!
        echo.
        echo Once EXE olusturmalisiniz:
        echo   EXE_OLUSTUR.bat
        echo   veya
        echo   EXE_OLUSTUR_GELISMIS.bat
        echo.
        pause
        exit /b 1
    )
)

REM Paket klasoru oluştur
set PAKET_KLASORU=InsaatMetrajPro_EXE_Paketi
if exist "%PAKET_KLASORU%" (
    echo Eski paket klasoru siliniyor...
    rmdir /s /q "%PAKET_KLASORU%"
)
mkdir "%PAKET_KLASORU%"

echo.
echo EXE ile test paketi hazirlaniyor...
echo.

REM Tek dosya versiyonu varsa
if exist "dist\InsaatMetrajPro.exe" (
    echo [1/4] EXE dosyasi kopyalaniyor (tek dosya)...
    copy "dist\InsaatMetrajPro.exe" "%PAKET_KLASORU%\" >nul
    set EXE_TIPI=tek_dosya
)

REM Klasor versiyonu varsa
if exist "dist\InsaatMetrajPro\InsaatMetrajPro.exe" (
    echo [1/4] EXE klasoru kopyalaniyor...
    xcopy /E /I "dist\InsaatMetrajPro" "%PAKET_KLASORU%\InsaatMetrajPro" >nul
    set EXE_TIPI=klasor
)

REM Rehberler
echo [2/4] Rehberler kopyalaniyor...
copy TEST_KULLANICILARI_ICIN.md "%PAKET_KLASORU%\" >nul 2>&1
copy GERI_BILDIRIM_FORMU.txt "%PAKET_KLASORU%\" >nul 2>&1
copy EXE_KURULUM_REHBERI.md "%PAKET_KLASORU%\" >nul 2>&1

REM README oluştur
echo [3/4] README dosyasi olusturuluyor...
(
echo # InsaatMetrajPro - EXE Versiyonu
echo.
echo ## Hizli Baslangic
echo.
if "%EXE_TIPI%"=="tek_dosya" (
    echo 1. **InsaatMetrajPro.exe** dosyasina cift tiklayin
    echo 2. Uygulama acilacaktir!
) else (
    echo 1. **InsaatMetrajPro** klasorune gidin
    echo 2. **InsaatMetrajPro.exe** dosyasina cift tiklayin
    echo 3. Uygulama acilacaktir!
)
echo.
echo ## Onemli Notlar
echo.
echo - **Python yuklu olmasina gerek YOK!**
echo - Windows 10/11 ile uyumludur
echo - Ilk acilista Windows uyarisi verebilir - "Run anyway" secin
echo.
echo ## Detayli Bilgi
echo.
echo - **TEST_KULLANICILARI_ICIN.md** - Test rehberi
echo - **GERI_BILDIRIM_FORMU.txt** - Geri bildirim formu
echo - **EXE_KURULUM_REHBERI.md** - Detayli kurulum rehberi
echo.
echo ## Destek
echo.
echo Sorulariniz icin rehberleri okuyun veya gelistiriciye ulasin.
) > "%PAKET_KLASORU%\README.md"

echo [4/4] Paket hazirlaniyor...
echo.

echo.
echo ========================================
echo EXE Test Paketi hazir!
echo ========================================
echo.
echo Klasor: %PAKET_KLASORU%
echo.
if "%EXE_TIPI%"=="tek_dosya" (
    echo Paket icerigi:
    echo   - InsaatMetrajPro.exe (tek dosya, Python gerekmez)
    echo   - Test rehberi
    echo   - Geri bildirim formu
) else (
    echo Paket icerigi:
    echo   - InsaatMetrajPro klasoru (Python gerekmez)
    echo   - Test rehberi
    echo   - Geri bildirim formu
)
echo.
echo Bu klasoru ZIP yapip test kullanicilarina gonderebilirsiniz.
echo.
pause






