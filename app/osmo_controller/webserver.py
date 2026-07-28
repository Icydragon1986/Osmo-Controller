"""
Serveur web local (stdlib uniquement) qui sert l'UI et fait le pont entre
le navigateur et le `CameraManager` qui tourne dans la boucle asyncio.

Pont thread → asyncio :
  - Le serveur HTTP tourne dans un thread (ThreadingHTTPServer).
  - La LECTURE de l'état (`snapshot`) est un simple accès mémoire (sûr sous GIL).
  - Les COMMANDES (coroutines) sont injectées dans la boucle asyncio via
    `asyncio.run_coroutine_threadsafe`, donc exécutées proprement côté asyncio.

Aucune dépendance externe : http.server + json de la lib standard.
"""

from __future__ import annotations
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .manager import CameraManager
from .version import VERSION

_WEBUI_DIR = Path(__file__).resolve().parent.parent / "webui"


def make_handler(manager: CameraManager, loop: asyncio.AbstractEventLoop,
                 admin=None, on_quit=None):
    class Handler(BaseHTTPRequestHandler):
        # HTTP/1.1 => connexions persistantes (keep-alive) : bien plus réactif
        # que le 1.0 par défaut, qui rouvre une connexion TCP à chaque clic.
        protocol_version = "HTTP/1.1"

        # Silence les logs HTTP par défaut (trop bavards pour notre usage).
        def log_message(self, *args):  # noqa: D401
            pass

        # -- helpers d'envoi ------------------------------------------- #
        def _no_cache(self):
            # Empêche le navigateur de servir une vieille version de l'UI
            # (et du statut) depuis son cache.
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")

        def _send_json(self, obj, code=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._no_cache()
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path, content_type: str):
            try:
                data = path.read_bytes()
            except FileNotFoundError:
                self.send_error(404, "Fichier introuvable")
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self._no_cache()
            self.end_headers()
            self.wfile.write(data)

        # -- routes ---------------------------------------------------- #
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send_file(_WEBUI_DIR / "index.html", "text/html; charset=utf-8")
            elif self.path == "/app.js":
                self._send_file(_WEBUI_DIR / "app.js", "application/javascript; charset=utf-8")
            elif self.path == "/style.css":
                self._send_file(_WEBUI_DIR / "style.css", "text/css; charset=utf-8")
            elif self.path == "/api/state":
                self._send_json({"version": VERSION, "manageable": admin is not None,
                                 "cameras": manager.snapshot()})
            else:
                self.send_error(404, "Route inconnue")

        def do_POST(self):
            if self.path != "/api/command":
                self.send_error(404, "Route inconnue")
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._send_json({"ok": False, "error": "JSON invalide"}, 400)
                return

            # Quitter : arrêt propre (déconnecte les caméras puis ferme l'app).
            if req.get("action") == "quit":
                self._send_json({"ok": True})
                print("« Quitter » reçu — arrêt propre en cours…")
                if on_quit is not None:
                    on_quit()
                return

            coro = self._dispatch(req)
            if coro is None:
                self._send_json({"ok": False, "error": "action inconnue"}, 400)
                return
            # Le scan BLE prend quelques secondes : timeout plus large pour lui.
            timeout = 25 if req.get("action") == "scan" else 12
            try:
                fut = asyncio.run_coroutine_threadsafe(coro, loop)
                result = fut.result(timeout=timeout)
                self._send_json({"ok": True, "result": result})
            except Exception as e:  # noqa: BLE001
                self._send_json({"ok": False, "error": str(e)})

        def _dispatch(self, req):
            action = req.get("action")
            cam = req.get("camera")
            if action == "start_rec_all":
                return manager.start_recording_all()
            if action == "stop_rec_all":
                return manager.stop_recording_all()
            if action == "start_rec" and cam in manager.names:
                return manager.get(cam).start_recording()
            if action == "stop_rec" and cam in manager.names:
                return manager.get(cam).stop_recording()
            if action == "reset_camera" and cam in manager.names:
                return manager.reset_camera(cam)
            # --- gestion des caméras (mode réel uniquement) ---
            if admin is not None:
                if action == "scan":
                    return admin.scan()
                if action == "add_camera":
                    return admin.add(req.get("name"), req.get("address"),
                                     req.get("model", "osmo_action_5_pro"))
                if action == "remove_camera" and cam in manager.names:
                    return admin.remove(cam)
            return None

    return Handler


def start_in_thread(manager: CameraManager, loop: asyncio.AbstractEventLoop,
                    admin=None, on_quit=None,
                    host: str = "127.0.0.1", port: int = 8765):
    """Démarre le serveur dans un thread démon. Renvoie (server, thread, url)."""
    handler = make_handler(manager, loop, admin, on_quit)
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True   # les requêtes en cours ne bloquent pas la fermeture
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://{host}:{port}/"
