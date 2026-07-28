"""
Osmo Controller — point d'entrée de l'application (Boccia Canada).

Normalement lancé via `launcher.py` (à la racine du dépôt), qui applique les
mises à jour puis démarre ce fichier en sous-processus. Pour itérer vite en
développement, ce fichier peut aussi être lancé directement (sans mise à jour) :

Deux modes :

  Simulation (par défaut) — caméras virtuelles, aucun matériel requis :
    python app.py                 # 3 terrains simulés
    python app.py --cameras 5     # 5 terrains
    python app.py --no-browser    # n'ouvre pas le navigateur

  Réel — vraies caméras via Bluetooth, listées dans cameras.json (racine du dépôt) :
    python app.py --real
    python app.py --real --config chemin/vers/mes_cameras.json

Format de cameras.json :
    [
      { "name": "Terrain 1", "address": "8C:58:23:2B:25:23",
        "model": "osmo_action_5_pro" }
    ]
(l'adresse BLE se trouve avec  python hardware/scan_ble.py, depuis la racine)
"""

from __future__ import annotations
import argparse
import asyncio
import json
import signal
import socket
import webbrowser
from pathlib import Path

from osmo_controller.manager import CameraManager
from osmo_controller.sim_transport import SimulatedTransport
from osmo_controller.simulator import OsmoCameraSimulator
from osmo_controller import webserver

# Quelques états de départ variés pour rendre la démo parlante.
_DEMO_PROFILES = [
    {"battery_pct": 96, "remain_capacity_mb": 58_000},
    {"battery_pct": 64, "remain_capacity_mb": 32_000},
    {"battery_pct": 28, "remain_capacity_mb": 12_000},
    {"battery_pct": 81, "remain_capacity_mb": 47_000},
    {"battery_pct": 12, "remain_capacity_mb": 4_500},
]


def build_simulated_manager(n: int) -> CameraManager:
    mgr = CameraManager(reconnect_delay=2.0)
    for i in range(1, n + 1):
        profile = _DEMO_PROFILES[(i - 1) % len(_DEMO_PROFILES)]
        cam = OsmoCameraSimulator(model="osmo_action_5_pro", **profile)
        # Délais réglés pour IMITER le vrai BLE (connexion ~1,5 s, commandes ~150 ms).
        transport = SimulatedTransport(
            cam, tick_interval=0.5,
            connect_delay=1.5, command_latency=0.15, jitter=0.1,
        )
        mgr.add_camera(f"Terrain {i}", transport)
    return mgr


def _lan_ips() -> list[str]:
    """Adresses IPv4 locales (hors loopback) — pour dire quoi taper sur l'iPad.

    Une machine peut avoir plusieurs adresses (Wi-Fi, VPN…) : on les liste
    toutes plutôt que de deviner, à essayer une par une si besoin."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


def already_running(port: int) -> bool:
    """Vrai si une instance d'Osmo Controller répond déjà sur ce port."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=1.5) as r:
            data = json.loads(r.read().decode("utf-8"))
        return isinstance(data, dict) and "version" in data
    except Exception:  # noqa: BLE001
        return False


def build_real_manager(config_path: Path) -> CameraManager:
    # Import local : n'exige `bleak` que si on lance réellement en mode réel.
    from osmo_controller.bleak_transport import BleakTransport

    cams = json.loads(config_path.read_text(encoding="utf-8"))
    mgr = CameraManager(reconnect_delay=3.0)
    for c in cams:
        name = c["name"]
        model = c.get("model", "osmo_action_5_pro")
        transport = BleakTransport(c["address"], name=name)
        mgr.add_camera(name, transport, model=model)
        print(f"  • {name}  ->  {c['address']}  ({model})")
    if not cams:
        print("  (aucune caméra — ajoute-les depuis l'interface)")
    return mgr


async def main(mgr: CameraManager, host: str, port: int, open_browser: bool, label: str,
               admin=None, users_path=None) -> None:
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    # Le bouton « Quitter » de l'interface et les signaux système déclenchent
    # tous le MÊME arrêt propre (déconnexion Bluetooth avant de fermer).
    def request_stop():
        loop.call_soon_threadsafe(stop_event.set)

    for sig in ("SIGINT", "SIGTERM", "SIGBREAK"):
        s = getattr(signal, sig, None)
        if s is not None:
            try:
                signal.signal(s, lambda *_: request_stop())
            except (ValueError, OSError):
                pass   # certains signaux ne sont pas réglables selon la plateforme

    try:
        server, _thread, _url = webserver.start_in_thread(
            mgr, loop, admin=admin, on_quit=request_stop,
            users_path=users_path, host=host, port=port)
    except OSError as e:
        print(f"\nImpossible de démarrer sur le port {port} : {e}")
        print(f"Ce port est peut-être utilisé par un autre programme.")
        print(f"Réessaie avec un autre port, ex :  python app.py --real --port 8766")
        return
    mgr.start_all()
    # Ouvrir le navigateur SUR CETTE MACHINE se fait toujours via 127.0.0.1,
    # même si le serveur écoute sur 0.0.0.0 (qui n'est pas une adresse à
    # laquelle se connecter, juste « toutes les interfaces »).
    local_url = f"http://127.0.0.1:{port}/"
    print("=" * 56)
    print(f"  Osmo Controller — {label}")
    print(f"  {len(mgr.names)} caméra(s)")
    print(f"  Interface (ce PC) : {local_url}")
    if host != "127.0.0.1":
        ips = _lan_ips()
        if ips:
            print(f"  Depuis un iPad/téléphone sur le même Wi-Fi, ouvre :")
            for ip in ips:
                print(f"    http://{ip}:{port}/")
        else:
            print(f"  Accessible depuis le Wi-Fi local, mais l'adresse IP n'a "
                  f"pas pu être détectée automatiquement — cherche-la avec "
                  f"'ipconfig' (Windows) ou 'ifconfig' (Mac).")
        print(f"  Connexion (compte) requise dans les deux cas.")
    print("  Quitte avec le bouton « Quitter » de l'interface, ou Ctrl+C.")
    print("=" * 56)
    if open_browser:
        webbrowser.open(local_url)

    try:
        await stop_event.wait()
    finally:
        print("\nArrêt : déconnexion des caméras…", flush=True)
        server.shutdown()
        try:
            await asyncio.wait_for(mgr.stop_all(), timeout=12)
            print("Toutes les caméras déconnectées.", flush=True)
        except asyncio.TimeoutError:
            print("Déconnexion trop lente — fermeture forcée.", flush=True)
        print("Fermé. À bientôt !", flush=True)


def run(argv=None) -> int:
    """Point d'entrée réutilisable : appelé directement (`python app.py`) ou
    en mémoire par `launcher.py` (y compris packagé en .exe/.app, où il n'y a
    pas de `python.exe` séparé à invoquer en sous-processus)."""
    ap = argparse.ArgumentParser(description="Osmo Controller")
    ap.add_argument("--real", action="store_true",
                    help="utiliser les vraies caméras BLE (cameras.json)")
    ap.add_argument("--config", default=None,
                    help="fichier de config des caméras réelles "
                         "(par défaut : cameras.json à la racine du dépôt, "
                         "à côté de launcher.py — pas dans app/)")
    ap.add_argument("--cameras", type=int, default=3,
                    help="nombre de terrains simulés (mode simulation)")
    ap.add_argument("--host", default="127.0.0.1",
                    help="adresse d'écoute (127.0.0.1 = ce PC seulement ; "
                         "0.0.0.0 = accessible depuis le Wi-Fi local, ex. iPad)")
    ap.add_argument("--port", type=int, default=8765, help="port HTTP local")
    ap.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    args = ap.parse_args(argv)

    # Idiot-proof : si l'app tourne déjà, on ouvre juste l'interface existante
    # au lieu de lancer une 2e instance (et de la faire échouer en silence).
    if already_running(args.port):
        url = f"http://127.0.0.1:{args.port}/"
        print(f"Osmo Controller tourne déjà — j'ouvre l'interface : {url}")
        print("Pour le redémarrer : clique « Quitter » dans le navigateur, puis relance.")
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    # Racine du dépôt = parent de app/ (où vit ce fichier) : users.json et
    # cameras.json doivent survivre aux mises à jour, qui remplacent app/ seul.
    root = Path(__file__).resolve().parent.parent
    users_path = root / "users.json"
    if not users_path.exists():
        users_path.write_text("{}\n", encoding="utf-8")
    if not json.loads(users_path.read_text(encoding="utf-8")):
        print("⚠ Aucun compte configuré — personne ne pourra se connecter.")
        print('  Crée-en un :  python manage_users.py add <nom> <mot de passe> --role admin')

    admin = None
    if args.real:
        default_cfg = root / "cameras.json"
        cfg = Path(args.config) if args.config else default_cfg
        if not cfg.exists():                    # config absente : on démarre vide,
            cfg.write_text("[]\n", encoding="utf-8")  # tu ajoutes les caméras dans l'UI
            print(f"(config créée : {cfg} — ajoute tes caméras depuis l'interface)")
        print("Caméras réelles :")
        manager = build_real_manager(cfg)
        from osmo_controller.camera_admin import RealCameraAdmin
        admin = RealCameraAdmin(manager, cfg)
        label = "MODE RÉEL (Bluetooth)"
    else:
        manager = build_simulated_manager(args.cameras)
        label = "MODE SIMULATION"

    try:
        asyncio.run(main(manager, args.host, args.port, not args.no_browser, label,
                         admin=admin, users_path=users_path))
    except KeyboardInterrupt:
        print("\nArrêt demandé. À bientôt !")
    # IMPORTANT : on laisse le processus se terminer NORMALEMENT (pas d'os._exit).
    # Le nettoyage normal de Python libère proprement les objets Bluetooth WinRT
    # — c'est ce qui relâche vraiment la caméra. Un arrêt brutal (os._exit/kill)
    # laisse au contraire le lien « collé ».
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
