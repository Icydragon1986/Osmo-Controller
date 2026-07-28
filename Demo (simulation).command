#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "  Python n'est pas installe. Installe Python 3 depuis https://python.org"
  read -p "Appuie sur Entree pour fermer..."
  exit 1
fi

echo "  Demarrage en mode SIMULATION (aucune camera reelle requise)..."
echo "  Pour QUITTER : bouton \"Quitter\" dans le navigateur, ou ferme cette fenetre."
echo

python3 launcher.py

read -p "Appuie sur Entree pour fermer..."
