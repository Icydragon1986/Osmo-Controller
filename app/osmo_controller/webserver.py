"""
Serveur web local (stdlib uniquement) qui sert l'UI et fait le pont entre
le navigateur et le `CameraManager` qui tourne dans la boucle asyncio.

Pont thread → asyncio :
  - Le serveur HTTP tourne dans un thread (ThreadingHTTPServer).
  - La LECTURE de l'état (`snapshot`) est un simple accès mémoire (sûr sous GIL).
  - Les COMMANDES (coroutines) sont injectées dans la boucle asyncio via
    `asyncio.run_coroutine_threadsafe`, donc exécutées proprement côté asyncio.

Tout en stdlib (http.server + json). Seul le code QR de connexion (bouton
« Connexion iPad ») a besoin du paquet `qrcode` (pur Python, pas de Pillow
requis pour du SVG) — importé à la demande, pas exigé pour le reste de l'app
(démo/simulation comprises).
"""

from __future__ import annotations
import asyncio
import io
import json
import socket
import sys
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import auth
from . import wifi_info
from .manager import CameraManager
from .version import VERSION

_WEBUI_DIR = Path(__file__).resolve().parent.parent / "webui"


def local_network_urls(port: int) -> list[str]:
    """Adresses IPv4 locales (hors loopback) où joindre ce serveur depuis un
    autre appareil (iPad, téléphone) sur le même réseau (Wi-Fi ou hotspot).

    Une machine peut avoir plusieurs adresses (Wi-Fi, VPN…) : on les liste
    toutes plutôt que de deviner laquelle est la bonne."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return [f"http://{ip}:{port}/" for ip in sorted(ips)]


def _qr_svg(data: str) -> str:
    # Import local : n'exige `qrcode` que si on affiche vraiment un code QR
    # (le reste de l'app — y compris toute la démo/simulation — reste sans
    # dépendance externe).
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


# Actions qui touchent la config partagée (caméras, réseau) ou ferment l'app
# pour TOUT LE MONDE : réservées au rôle admin.
_ADMIN_ONLY_ACTIONS = {"scan", "add_camera", "remove_camera", "quit",
                       "hotspot_start", "hotspot_stop",
                       "add_user", "remove_user"}


def make_handler(manager: CameraManager, loop: asyncio.AbstractEventLoop,
                 admin=None, on_quit=None, users_path=None, sessions=None, port=8765,
                 wifi_config_path=None):
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

        def _send_json(self, obj, code=200, extra_headers=()):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            for name, value in extra_headers:
                self.send_header(name, value)
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

        def _redirect(self, location: str):
            self.send_response(302)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        # -- auth -------------------------------------------------------- #
        def _session_token(self):
            cookie_header = self.headers.get("Cookie")
            if not cookie_header:
                return None
            jar = SimpleCookie()
            jar.load(cookie_header)
            morsel = jar.get("session")
            return morsel.value if morsel else None

        def _session(self):
            return sessions.get(self._session_token())

        def _read_json_body(self):
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length) or b"{}")

        def _handle_login(self):
            try:
                req = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"ok": False, "error": "JSON invalide"}, 400)
                return
            username = (req.get("username") or "").strip()
            role = auth.authenticate(users_path, username, req.get("password") or "")
            if role is None:
                self._send_json({"ok": False, "error": "identifiants invalides"}, 401)
                return
            token = sessions.create(username, role)
            self._send_json(
                {"ok": True, "username": username, "role": role}, 200,
                extra_headers=[("Set-Cookie", f"session={token}; Path=/; HttpOnly; SameSite=Lax")],
            )

        def _handle_logout(self):
            sessions.delete(self._session_token())
            self._send_json(
                {"ok": True}, 200,
                extra_headers=[("Set-Cookie", "session=deleted; Path=/; Max-Age=0")],
            )

        # -- routes ---------------------------------------------------- #
        def do_GET(self):
            # Public : la page de connexion et les fichiers statiques partagés.
            if self.path in ("/login", "/login.html"):
                self._send_file(_WEBUI_DIR / "login.html", "text/html; charset=utf-8")
                return
            if self.path == "/login.js":
                self._send_file(_WEBUI_DIR / "login.js", "application/javascript; charset=utf-8")
                return
            if self.path == "/style.css":
                self._send_file(_WEBUI_DIR / "style.css", "text/css; charset=utf-8")
                return
            if self.path == "/app.js":
                self._send_file(_WEBUI_DIR / "app.js", "application/javascript; charset=utf-8")
                return

            # Protégé : le tableau de bord et son état ont besoin d'une session.
            session = self._session()
            if self.path in ("/", "/index.html"):
                if session is None:
                    self._redirect("/login")
                    return
                self._send_file(_WEBUI_DIR / "index.html", "text/html; charset=utf-8")
                return
            if self.path == "/api/state":
                if session is None:
                    self._send_json({"ok": False, "error": "non authentifié"}, 401)
                    return
                username, role = session
                self._send_json({
                    "version": VERSION,
                    "manageable": admin is not None and role == "admin",
                    "username": username, "role": role,
                    "cameras": manager.snapshot(),
                })
                return
            if self.path == "/api/connect-info":
                if session is None:
                    self._send_json({"ok": False, "error": "non authentifié"}, 401)
                    return
                _username, role = session

                hotspot_status = None
                if role == "admin":
                    from . import hotspot
                    try:
                        fut = asyncio.run_coroutine_threadsafe(
                            hotspot.get_status(wifi_config_path), loop)
                        hotspot_status = fut.result(timeout=5)
                    except Exception:  # noqa: BLE001 — indisponible (pas Windows, etc.) : pas grave
                        hotspot_status = {"available": False}

                urls = local_network_urls(port)
                try:
                    items = [{"url": u, "qr_svg": _qr_svg(u)} for u in urls]
                    # Le hotspot ACTIF a priorité (c'est la vérité du terrain) sur la
                    # config manuelle ou la détection d'un Wi-Fi normal connecté.
                    if hotspot_status and hotspot_status.get("on"):
                        wifi = {"ssid": hotspot_status["ssid"], "password": hotspot_status["passphrase"]}
                    elif wifi_config_path:
                        wifi = wifi_info.current_wifi(wifi_config_path)
                    else:
                        wifi = None
                    wifi_item = ({"ssid": wifi["ssid"],
                                 "qr_svg": _qr_svg(wifi_info.wifi_qr_payload(wifi["ssid"], wifi["password"]))}
                                if wifi else None)
                except ImportError:
                    self._send_json({"ok": False,
                                     "error": "code QR indisponible (pip install qrcode)"}, 500)
                    return
                self._send_json({"ok": True, "items": items, "wifi": wifi_item,
                                 "hotspot": hotspot_status})
                return
            if self.path == "/api/users":
                if session is None:
                    self._send_json({"ok": False, "error": "non authentifié"}, 401)
                    return
                _username, role = session
                if role != "admin":
                    self._send_json({"ok": False, "error": "réservé aux comptes admin"}, 403)
                    return
                users = auth.load_users(users_path) if users_path else {}
                # Jamais le hash du mot de passe, juste de quoi lister/gérer.
                items = [{"username": u, "role": e.get("role")} for u, e in users.items()]
                self._send_json({"ok": True, "users": items})
                return
            self.send_error(404, "Route inconnue")

        def do_POST(self):
            if self.path == "/api/login":
                self._handle_login()
                return
            if self.path == "/api/logout":
                self._handle_logout()
                return
            if self.path != "/api/command":
                self.send_error(404, "Route inconnue")
                return

            session = self._session()
            if session is None:
                self._send_json({"ok": False, "error": "non authentifié"}, 401)
                return
            _username, role = session

            try:
                req = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"ok": False, "error": "JSON invalide"}, 400)
                return

            action = req.get("action")
            if action in _ADMIN_ONLY_ACTIONS and role != "admin":
                self._send_json({"ok": False, "error": "réservé aux comptes admin"}, 403)
                return

            # Quitter : arrêt propre (déconnecte les caméras puis ferme l'app).
            if action == "quit":
                self._send_json({"ok": True})
                print("« Quitter » reçu — arrêt propre en cours…")
                if on_quit is not None:
                    on_quit()
                return

            # Gestion des comptes : pur I/O fichier, pas besoin de la boucle asyncio.
            if action == "add_user":
                new_username = (req.get("username") or "").strip()
                new_password = req.get("password") or ""
                new_role = req.get("role") or "operator"
                if not new_username or not new_password:
                    self._send_json({"ok": False, "error": "nom et mot de passe requis"}, 400)
                    return
                try:
                    auth.add_user(users_path, new_username, new_password, role=new_role)
                except ValueError as e:
                    self._send_json({"ok": False, "error": str(e)}, 400)
                    return
                self._send_json({"ok": True})
                return
            if action == "remove_user":
                target = (req.get("username") or "").strip()
                if target == _username:
                    self._send_json({"ok": False, "error": "impossible de retirer ton propre compte"}, 400)
                    return
                removed = auth.remove_user(users_path, target)
                if not removed:
                    self._send_json({"ok": False, "error": "compte introuvable"}, 404)
                    return
                self._send_json({"ok": True})
                return

            coro = self._dispatch(req)
            if coro is None:
                self._send_json({"ok": False, "error": "action inconnue"}, 400)
                return
            # Le scan BLE prend quelques secondes : timeout plus large pour lui.
            timeout = 25 if action == "scan" else 12
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
            # --- point d'accès Wi-Fi (hotspot) du PC ---
            if action == "hotspot_start":
                from . import hotspot
                return hotspot.start(wifi_config_path)
            if action == "hotspot_stop":
                from . import hotspot
                return hotspot.stop(wifi_config_path)
            return None

    return Handler


# Un appareil (iPad, téléphone) qui ferme sa connexion brutalement — perte de
# Wi-Fi, mise en veille, ou arrêt du serveur pendant qu'il pollait /api/state
# — est NORMAL, pas une erreur : on l'ignore plutôt que d'afficher une trace
# qui donne l'impression que quelque chose a planté.
_QUIET_ERRORS = (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)


class _QuietThreadingHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        if sys.exc_info()[0] in _QUIET_ERRORS:
            return
        super().handle_error(request, client_address)


def start_in_thread(manager: CameraManager, loop: asyncio.AbstractEventLoop,
                    admin=None, on_quit=None, users_path=None, wifi_config_path=None,
                    host: str = "127.0.0.1", port: int = 8765):
    """Démarre le serveur dans un thread démon. Renvoie (server, thread, url)."""
    sessions = auth.SessionStore()
    handler = make_handler(manager, loop, admin, on_quit, users_path, sessions,
                           port=port, wifi_config_path=wifi_config_path)
    server = _QuietThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True   # les requêtes en cours ne bloquent pas la fermeture
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://{host}:{port}/"
