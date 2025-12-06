@echo off
REM InsaatMetrajPro - Test Kullanıcıları İçin Paket Hazırlama
REM Bu script, test kullanıcılarına gönderilecek paketi hazırlar

echo ========================================
echo InsaatMetrajPro - Test Paketi Hazirlama
echo ========================================
echo.

REM Paket klasörü oluştur
set PAKET_KLASORU=InsaatMetrajPro_Test_Paketi
if exist "%PAKET_KLASORU%" (
    echo Eski paket klasoru siliniyor...
    rmdir /s /q "%PAKET_KLASORU%"
)
mkdir "%PAKET_KLASORU%"

echo.
echo Test kullanicilari icin dosyalar hazirlaniyor...
echo.

REM exclude_list.txt oluştur
echo __pycache__ > exclude_list.txt
echo *.pyc >> exclude_list.txt
echo *.db >> exclude_list.txt
echo *.xlsx >> exclude_list.txt
echo .git >> exclude_list.txt
echo metraj_sonuc.xlsx >> exclude_list.txt
echo metraj_raporu.xlsx >> exclude_list.txt

REM Ana dosyalar
echo [1/6] Ana dosyalar kopyalaniyor...
copy main.py "%PAKET_KLASORU%\" >nul
copy requirements.txt "%PAKET_KLASORU%\" >nul
copy InsaatMetrajPro.bat "%PAKET_KLASORU%\" >nul
copy KURULUM.bat "%PAKET_KLASORU%\" >nul

REM Rehberler
echo [2/6] Rehberler kopyalaniyor...
copy TEST_KULLANICILARI_ICIN.md "%PAKET_KLASORU%\" >nul
copy GERI_BILDIRIM_FORMU.txt "%PAKET_KLASORU%\" >nul
copy README_AKTARIM.md "%PAKET_KLASORU%\" >nul 2>&1

REM app klasörünü kopyala (__pycache__ hariç)
echo [3/6] app klasoru kopyalaniyor...
xcopy /E /I /EXCLUDE:exclude_list.txt app "%PAKET_KLASORU%\app" >nul

REM exclude_list.txt'yi sil
del exclude_list.txt >nul 2>&1

REM README dosyası oluştur
echo [4/6] README dosyasi olusturuluyor...
(
echo # InsaatMetrajPro - Test Paketi
echo.
echo ## Hizli Baslangic
echo.
echo 1. **KURULUM.bat** dosyasina cift tiklayin
echo 2. **InsaatMetrajPro.bat** ile uygulamayi baslatin
echo.
echo ## Detayli Bilgi
echo.
echo - **TEST_KULLANICILARI_ICIN.md** - Test rehberi
echo - **GERI_BILDIRIM_FORMU.txt** - Geri bildirim formu
echo.
echo ## Gereksinimler
echo.
echo - Windows 10/11
echo - Python 3.8+ ^(https://www.python.org/downloads/^)
echo.
echo ## Destek
echo.
echo Sorulariniz icin: TEST_KULLANICILARI_ICIN.md dosyasini okuyun.
) > "%PAKET_KLASORU%\README.md"

REM ZIP için not
echo [5/6] Paket hazirlaniyor...
echo.

REM Klasör yapısını göster
echo [6/6] Paket yapisi kontrol ediliyor...
dir /B "%PAKET_KLASORU%" >nul

echo.
echo ========================================
echo Paket hazir!
echo ========================================
echo.
echo Klasor: %PAKET_KLASORU%
echo.
echo Bu klasoru ZIP yapip test kullanicilarina gonderebilirsiniz.
echo.
echo Paket icerigi:
echo   - Uygulama dosyalari
echo   - Kurulum scripti
echo   - Test rehberi
echo   - Geri bildirim formu
echo.
pause






