@echo off
chcp 65001 >nul
title QUANTIX PRO - Kurulum
echo ======================================
echo QUANTIX PRO - KURULUM
echo ======================================
echo.
echo Yeni kutuphaneler yukleniyor...
echo.

E:
cd "İNŞAAT METRAJ PRO\yeni_proje"
pip install -r requirements.txt

echo.
echo ======================================
echo KURULUM TAMAMLANDI!
echo ======================================
echo.
echo Artik masaustundeki "QuantixPro_Calistir.bat" dosyasina cift tiklayarak programi calistirabilecesiniz.
echo.
pause
