"""
Osmo Controller — lanceur (racine du dépôt, ne change quasiment jamais).

Rôle :
  1. appliquer une mise à jour déjà téléchargée lors de la session précédente
     (échange de dossiers, rapide et sûr : app/ n'est pas en cours d'utilisation
     puisque app.py tourne dans un sous-processus séparé) ;
  2. démarrer l'app (app/app.py, en sous-processus) ;
  3. en arrière-plan, pendant que l'app tourne, vérifier s'il existe une
     nouvelle version et la préparer pour le PROCHAIN démarrage.

Le code qui change à chaque version (app.py, osmo_controller/, webui/) vit
dans app/ — c'est ce dossier que remplacent les mises à jour. cameras.json et
update_config.json restent ici, à la racine, pour survivre aux mises à jour.

Configuration (update_config.json, à la racine) :
    { "manifest_url": "https://raw.githubusercontent.com/.../manifest.json" }
Absent ou "manifest_url" vide = vérification de mise à jour désactivée
(comportement par défaut tant que le dépôt GitHub n'existe pas).
"""
from __future__ import annotations
import json
import sys
import threading
from pathlib import Path

# Packagé (.exe/.app) : sys.executable est l'exe lui-même (pas de python.exe
# séparé), et son dossier est là où vivent app/, cameras.json, etc. Non
# packagé : __file__ (ce script) suffit.
ROOT = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
APP_DIR = ROOT / "app"
UPDATE_CONFIG_PATH = ROOT / "update_config.json"

sys.path.insert(0, str(APP_DIR))  # pour importer osmo_controller.updater et app.py


def load_update_config() -> dict:
    """Lit update_config.json. Absent ou invalide -> désactivé (dict vide)."""
    if not UPDATE_CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(UPDATE_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def apply_pending_update() -> None:
    """Applique au démarrage une mise à jour déjà téléchargée, s'il y en a une."""
    from osmo_controller import updater

    if not updater.has_pending_update(APP_DIR):
        return
    print("Mise à jour en attente détectée — application…", flush=True)
    try:
        if updater.finalize_pending_update(APP_DIR):
            print("Mise à jour appliquée.", flush=True)
            # app/ vient d'être remplacé sur disque, mais les modules
            # osmo_controller déjà importés ci-dessus (dont VERSION) restent
            # en mémoire avec l'ANCIEN code -- sans ça, check_for_next_update()
            # comparerait le manifeste à une version périmée et retéléchargerait
            # la même mise à jour en boucle à chaque démarrage. On invalide le
            # cache d'import pour forcer une relecture depuis le nouveau app/.
            for name in list(sys.modules):
                if name == "osmo_controller" or name.startswith("osmo_controller."):
                    del sys.modules[name]
    except OSError as e:
        print(f"Échec de l'application de la mise à jour ({e}) "
              f"— on continue avec la version actuelle.", flush=True)


def check_for_next_update() -> None:
    """En arrière-plan : prépare la prochaine version si le manifeste en annonce une.

    Ne doit jamais faire échouer ou ralentir l'app (pas de réseau, manifeste
    injoignable, etc. -> ignoré silencieusement, juste journalisé)."""
    manifest_url = load_update_config().get("manifest_url")
    if not manifest_url:
        return
    from osmo_controller import updater

    try:
        staged = updater.prepare_update(manifest_url, APP_DIR)
        if staged:
            print(f"Mise à jour {staged} téléchargée — sera appliquée au prochain démarrage.",
                  flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"Vérification de mise à jour ignorée ({type(e).__name__}: {e})", flush=True)


def main() -> int:
    apply_pending_update()
    threading.Thread(target=check_for_next_update, daemon=True).start()

    # Import EN MÉMOIRE (pas de sous-processus) : dans un .exe/.app packagé,
    # il n'y a pas de python.exe séparé à invoquer — app/app.py est chargé
    # directement dans ce même processus, depuis app/ sur disque (mis à jour
    # au besoin par apply_pending_update() juste avant).
    import app as app_module
    argv = sys.argv[1:]
    if getattr(sys, "frozen", False) and not argv:
        # Un .app/.exe packagé lancé par double-clic (Finder/Explorateur) ne
        # reçoit JAMAIS d'arguments -- contrairement à "Lancer Osmo
        # Controller.command"/.bat, qui passent --real --host 0.0.0.0 à la
        # main. Sans ce filet, le double-clic retombe silencieusement sur les
        # valeurs par défaut d'app.py (mode simulation, caméras fictives,
        # écoute sur 127.0.0.1 seulement -- donc invisible pour un iPad sur
        # le même Wi-Fi). Vécu en prod : "l'app tourne mais rien ne marche".
        argv = ["--real", "--host", "0.0.0.0"]
    return app_module.run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
