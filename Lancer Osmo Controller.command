#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo
  echo "  Python n'est pas installe sur cet ordinateur."
  echo "  Installe Python 3 depuis https://python.org puis relance ce fichier."
  echo
  read -p "Appuie sur Entree pour fermer..."
  exit 1
fi

echo
echo "  Demarrage d'Osmo Controller (cameras reelles)..."
echo "  L'interface va s'ouvrir dans ton navigateur."
echo
echo "  *** Pour QUITTER : clique le bouton \"Quitter\" dans le navigateur. ***"
echo

python3 launcher.py --real

echo
echo "  Osmo Controller est ferme. Tu peux fermer cette fenetre."
read -p "Appuie sur Entree pour fermer..."
