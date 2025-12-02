@echo off
REM InsaatMetrajPro - Aktarım Hazırlama Scripti
REM Bu script, başka bilgisayara aktarılacak dosyaları hazırlar

echo ========================================
echo InsaatMetrajPro - Aktarim Hazirlama
echo ========================================
echo.

REM Aktarım klasörü oluştur
set AKTARIM_KLASORU=InsaatMetrajPro_Aktarim
if exist "%AKTARIM_KLASORU%" (
    echo Eski aktarim klasoru siliniyor...
    rmdir /s /q "%AKTARIM_KLASORU%"
)
mkdir "%AKTARIM_KLASORU%"

echo.
echo Dosyalar kopyalaniyor...

REM Ana dosyalar
copy main.py "%AKTARIM_KLASORU%\" >nul
copy requirements.txt "%AKTARIM_KLASORU%\" >nul
copy README.md "%AKTARIM_KLASORU%\" >nul 2>&1
copy InsaatMetrajPro.bat "%AKTARIM_KLASORU%\" >nul 2>&1
copy KURULUM_REHBERI.md "%AKTARIM_KLASORU%\" >nul 2>&1

REM exclude_list.txt oluştur
echo __pycache__ > exclude_list.txt
echo *.pyc >> exclude_list.txt
echo *.db >> exclude_list.txt
echo *.xlsx >> exclude_list.txt
echo .git >> exclude_list.txt

REM app klasörünü kopyala (__pycache__ hariç)
xcopy /E /I /EXCLUDE:exclude_list.txt app "%AKTARIM_KLASORU%\app" >nul

echo.
echo Temizlik yapiliyor...

REM exclude_list.txt'yi sil
del exclude_list.txt >nul 2>&1

echo.
echo ========================================
echo Aktarim klasoru hazir!
echo ========================================
echo.
echo Klasor: %AKTARIM_KLASORU%
echo.
echo Bu klasoru ZIP yapip baska bilgisayara aktarabilirsiniz.
echo.
pause

