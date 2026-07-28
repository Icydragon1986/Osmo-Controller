@echo off
title Osmo Controller - Boccia Canada
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo   Python n'est pas installe sur cet ordinateur.
  echo   Installe Python 3 depuis https://python.org puis relance ce fichier.
  echo.
  pause
  exit /b
)

echo.
echo   Demarrage d'Osmo Controller (cameras reelles)...
echo   L'interface va s'ouvrir dans ton navigateur, et sera accessible
echo   depuis d'autres appareils (iPad, telephone) sur le meme Wi-Fi.
echo.
echo   *** Pour QUITTER : clique le bouton "Quitter" dans le navigateur. ***
echo.

python launcher.py --real --host 0.0.0.0

echo.
echo   Osmo Controller est ferme. Tu peux fermer cette fenetre.
pause
