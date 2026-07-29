@echo off
REM Construit le lanceur Windows (OsmoController.exe) avec PyInstaller.
REM A relancer seulement quand launcher.py change ou que bleak/winrt sont mis
REM a jour -- PAS a chaque changement de app/ (ca, c'est le role de la mise
REM a jour automatique, pas d'un nouveau build).
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python n'est pas installe.
  pause
  exit /b 1
)

python -m PyInstaller --name OsmoController --onedir --console ^
  --exclude-module app --exclude-module osmo_controller ^
  --collect-all bleak --collect-all winrt ^
  --hidden-import abc --hidden-import argparse --hidden-import asyncio ^
  --hidden-import dataclasses --hidden-import enum --hidden-import gc ^
  --hidden-import hashlib --hidden-import http.server --hidden-import io ^
  --hidden-import json --hidden-import pathlib --hidden-import random ^
  --hidden-import shutil --hidden-import signal --hidden-import struct ^
  --hidden-import threading --hidden-import time --hidden-import typing ^
  --hidden-import urllib.request --hidden-import webbrowser --hidden-import zipfile ^
  --noconfirm --clean ^
  launcher.py
if errorlevel 1 (
  echo.
  echo Le build a echoue -- voir les erreurs ci-dessus.
  pause
  exit /b 1
)

echo.
echo Assemblage du dossier final (app/ + config)...
xcopy /e /i /y app "dist\OsmoController\app" >nul
if not exist "dist\OsmoController\cameras.json" copy /y cameras.json "dist\OsmoController\cameras.json" >nul
if not exist "dist\OsmoController\update_config.json" copy /y update_config.json "dist\OsmoController\update_config.json" >nul
REM users.json/wifi_config.json : copies seulement si TU en as un ici (tes
REM comptes/hotspot deja configures) -- comme ca, la personne qui recoit ce
REM dossier peut se connecter tout de suite, sans jamais toucher a un terminal.
if exist "users.json" if not exist "dist\OsmoController\users.json" copy /y users.json "dist\OsmoController\users.json" >nul
if exist "wifi_config.json" if not exist "dist\OsmoController\wifi_config.json" copy /y wifi_config.json "dist\OsmoController\wifi_config.json" >nul

echo.
echo Termine : dist\OsmoController\OsmoController.exe
echo (dossier complet, a copier tel quel pour le distribuer)
pause
