@echo off
cd /d %~dp0
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
pyinstaller ^
  --noconfirm ^
  --windowed ^
  --name DeaneryStatementApp ^
  --add-data "app\templates;app\templates" ^
  --add-data "app\resources;app\resources" ^
  --add-data "config.ini;." ^
  app\main.py
pause
