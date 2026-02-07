@echo off
chcp 65001 >nul
title Insaat Metraj Pro - Kurulum
echo ======================================
echo INSAAT METRAJ PRO - KURULUM
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
echo Artik masaustundeki "InsaatMetrajPro_Calistir.bat" dosyasina cift tiklayarak programi calistirabilecesiniz.
echo.
pause
