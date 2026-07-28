@echo off
title Osmo Controller - DEMO (simulation)
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo   Python n'est pas installe. Installe Python 3 depuis https://python.org
  pause
  exit /b
)

echo   Demarrage en mode SIMULATION (aucune camera reelle requise)...
echo   Pour QUITTER : bouton "Quitter" dans le navigateur, ou ferme cette fenetre.
echo.
python launcher.py

pause
