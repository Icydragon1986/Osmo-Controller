"""
Vérifie le module de mise à jour de bout en bout, sans rien publier en ligne :
un serveur HTTP local joue le rôle de GitHub (manifeste + zip), et on contrôle
la détection de version, la vérification d'intégrité (SHA-256) et l'application
par échange de dossiers.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")  # console Windows : autoriser ✔ et accents

import functools
import hashlib
import io
import json
import tempfile
import threading
import zipfile
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from osmo_controller import updater

ok = True


def check(label, cond):
    global ok
    print(f"  [{'OK ' if cond else 'FAIL'}] {label}")
    ok = ok and cond


def make_app_zip(version: str) -> bytes:
    """Construit un faux paquet d'app contenant un fichier version.py."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("version.py", f'VERSION = "{version}"\n')
        zf.writestr("webui/app.js", "// nouveau code\n")
    return buf.getvalue()


def serve(directory: Path):
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.RequestHandlerClass.log_message = lambda *a, **k: None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


print("1) Comparaison de versions")
check("0.10.0 > 0.9.0", updater.is_newer("0.10.0", "0.9.0"))
check("0.6.0 pas > 0.6.0", not updater.is_newer("0.6.0", "0.6.0"))
check("0.5.0 pas > 0.6.0", not updater.is_newer("0.5.0", "0.6.0"))

# Prépare un "serveur GitHub" local : zip 0.7.0 + manifeste avec son SHA-256.
srv_dir = Path(tempfile.mkdtemp())
zip_bytes = make_app_zip("0.7.0")
(srv_dir / "osmo-0.7.0.zip").write_bytes(zip_bytes)
httpd, base = serve(srv_dir)
manifest = {
    "version": "0.7.0",
    "url": f"{base}/osmo-0.7.0.zip",
    "sha256": hashlib.sha256(zip_bytes).hexdigest(),
    "notes": "Test",
}
(srv_dir / "manifest.json").write_text(json.dumps(manifest))
manifest_url = f"{base}/manifest.json"

print("\n2) Détection d'une version plus récente")
found = updater.check_for_update(manifest_url, local_version="0.6.0")
check("0.7.0 détectée comme plus récente", found is not None and found["version"] == "0.7.0")
check("rien à faire si déjà à 0.7.0",
      updater.check_for_update(manifest_url, local_version="0.7.0") is None)

print("\n3) Préparation : téléchargement + mise en attente (.next)")
app_dir = Path(tempfile.mkdtemp()) / "app"
app_dir.mkdir()
(app_dir / "version.py").write_text('VERSION = "0.6.0"\n')
staged = updater.prepare_update(manifest_url, app_dir, local_version="0.6.0")
check("version 0.7.0 mise en attente", staged == "0.7.0")
check("dossier .next créé", updater.has_pending_update(app_dir))
check("le code en attente est bien la 0.7.0",
      'VERSION = "0.7.0"' in (app_dir.with_name("app.next") / "version.py").read_text())
check("l'app en cours est toujours en 0.6.0",
      'VERSION = "0.6.0"' in (app_dir / "version.py").read_text())

print("\n4) Application au (re)démarrage : échange de dossiers")
applied = updater.finalize_pending_update(app_dir)
check("mise à jour appliquée", applied is True)
check("l'app est maintenant en 0.7.0",
      'VERSION = "0.7.0"' in (app_dir / "version.py").read_text())
check("plus de mise à jour en attente", not updater.has_pending_update(app_dir))
check("rien à finaliser une 2e fois", updater.finalize_pending_update(app_dir) is False)

print("\n5) Sécurité : un zip corrompu (mauvais SHA-256) est rejeté")
bad = dict(manifest, version="0.8.0", sha256="0" * 64)
(srv_dir / "bad.json").write_text(json.dumps(bad))
rejected = False
try:
    updater.prepare_update(f"{base}/bad.json", app_dir, local_version="0.7.0")
except ValueError:
    rejected = True
check("mise à jour à SHA-256 invalide refusée", rejected)
check("aucun .next créé après rejet", not updater.has_pending_update(app_dir))

httpd.shutdown()
print("\n" + ("=" * 48))
print("  TOUS LES TESTS PASSENT ✔" if ok else "  ÉCHEC — voir ci-dessus")
print("=" * 48)
sys.exit(0 if ok else 1)
