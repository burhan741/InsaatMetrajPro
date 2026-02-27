@echo off
chcp 65001 >nul
title QUANTIX PRO
E:
cd "E:\İNŞAAT METRAJ PRO\yeni_proje"
call "E:\İNŞAAT METRAJ PRO\.venv\Scripts\activate.bat"
python main.py
pause
