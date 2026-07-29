#!/bin/bash
# Construit le lanceur macOS (OsmoController.app) avec PyInstaller.
# Equivalent de build_launcher.bat, adapte a macOS (bundle .app + CoreBluetooth).
# A relancer seulement quand launcher.py change ou que bleak est mis a jour --
# PAS a chaque changement de app/ (ca, c'est le role de la mise a jour
# automatique, pas d'un nouveau build).
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 n'est pas installe."
  exit 1
fi

if ! python3 -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller n'est pas installe -- installation (pip3 install --user pyinstaller)..."
  python3 -m pip install --user pyinstaller
fi

# On passe par un .spec (genere puis patche) plutot que la ligne de commande
# directe : c'est le seul moyen d'ajouter au bundle .app la cle Info.plist
# NSBluetoothAlwaysUsageDescription, obligatoire pour que CoreBluetooth
# fonctionne (sans elle, bleak echoue silencieusement -- ni erreur, ni
# popup de permission -- verifie sur materiel reel). Le .spec est regenere
# a chaque build, pas versionne (voir .gitignore).
python3 -m PyInstaller.utils.cliutils.makespec --name OsmoController --onedir --windowed \
  --exclude-module app --exclude-module osmo_controller \
  --collect-all bleak \
  --hidden-import abc --hidden-import argparse --hidden-import asyncio \
  --hidden-import dataclasses --hidden-import enum --hidden-import gc \
  --hidden-import hashlib --hidden-import http.server --hidden-import http.cookies \
  --hidden-import io --hidden-import json --hidden-import pathlib \
  --hidden-import random --hidden-import re --hidden-import secrets \
  --hidden-import shutil --hidden-import signal --hidden-import socket \
  --hidden-import struct --hidden-import subprocess --hidden-import threading \
  --hidden-import time --hidden-import typing --hidden-import urllib.request \
  --hidden-import webbrowser --hidden-import zipfile \
  launcher.py

python3 - <<'PY'
import re
spec = "OsmoController.spec"
text = open(spec, encoding="utf-8").read()
desc = ("Osmo Controller a besoin du Bluetooth pour piloter les caméras "
        "DJI Osmo Action 5 Pro.")
text = text.replace(
    "    bundle_identifier=None,\n)",
    "    bundle_identifier=None,\n"
    "    info_plist={\n"
    f"        'NSBluetoothAlwaysUsageDescription': {desc!r},\n"
    f"        'NSBluetoothPeripheralUsageDescription': {desc!r},\n"
    "    },\n)",
)
open(spec, "w", encoding="utf-8").write(text)
PY

python3 -m PyInstaller --noconfirm --clean OsmoController.spec

echo
echo "Assemblage du dossier final (app/ + config, a cote du vrai executable)..."
# IMPORTANT : dans un bundle .app, sys.executable (utilise par launcher.py
# pour trouver sa racine) pointe vers Contents/MacOS/OsmoController -- donc
# app/, cameras.json et update_config.json doivent vivre LA, pas a cote du
# dossier OsmoController.app lui-meme.
MACOS_DIR="dist/OsmoController.app/Contents/MacOS"
rm -rf "$MACOS_DIR/app"
cp -R app "$MACOS_DIR/app"
[ -f "$MACOS_DIR/cameras.json" ] || cp cameras.json "$MACOS_DIR/cameras.json"
[ -f "$MACOS_DIR/update_config.json" ] || cp update_config.json "$MACOS_DIR/update_config.json"

echo
echo "Termine : dist/OsmoController.app"
echo "(dossier .app complet, a copier tel quel pour le distribuer)"
echo
echo "Premier lancement sur une AUTRE machine que celle-ci : si macOS refuse"
echo "d'ouvrir l'app (\"developpeur non identifie\"), clic droit sur"
echo "OsmoController.app > Ouvrir > confirmer -- une seule fois."
