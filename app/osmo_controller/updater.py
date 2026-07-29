"""
Mise à jour automatique — pur stdlib, hébergement-agnostique.

Principe : un petit fichier « manifeste » (JSON) est publié quelque part
(GitHub conseillé). Il décrit la dernière version et où trouver le code :

    {
      "version": "0.7.0",
      "url":     "https://.../osmo-0.7.0.zip",
      "sha256":  "<empreinte du zip>",       (optionnel mais recommandé)
      "notes":   "Ce qui a changé"           (optionnel)
    }

Au démarrage, le LANCEUR :
  1. `finalize_pending_update(app_dir)` — applique une mise à jour déjà
     téléchargée lors de la session précédente (échange de dossiers, rapide
     et sûr car on ne touche pas aux fichiers en cours d'utilisation).
  2. lance l'app.
  3. en arrière-plan, `prepare_update(manifest_url, app_dir)` — vérifie s'il
     existe une version plus récente et, le cas échéant, télécharge + vérifie
     + met en attente le nouveau code (sera appliqué au prochain démarrage).

On sépare « préparer » (pendant l'exécution) et « finaliser » (au démarrage,
avant de charger le code) pour éviter d'écraser des fichiers verrouillés —
le piège classique de l'auto-update sous Windows.

Sécurité : téléchargement en HTTPS uniquement + vérification SHA-256 du zip
contre le manifeste avant toute application.
"""

from __future__ import annotations
import hashlib
import io
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

from .version import VERSION

DEFAULT_TIMEOUT = 10
_UA = {"User-Agent": "OsmoController-Updater"}
_SUFFIX_NEXT = ".next"     # code téléchargé, en attente d'application
_SUFFIX_BAK = ".bak"       # ancienne version, gardée comme filet


# --------------------------------------------------------------------------
# Comparaison de versions (ex. "0.10.0" > "0.9.0")
# --------------------------------------------------------------------------
def _parse_version(v: str) -> tuple[int, ...]:
    parts = []
    for chunk in str(v).split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer(remote: str, local: str = VERSION) -> bool:
    return _parse_version(remote) > _parse_version(local)


# --------------------------------------------------------------------------
# Réseau
# --------------------------------------------------------------------------
def fetch_manifest(url: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    if not url.lower().startswith("https://") and "127.0.0.1" not in url and "localhost" not in url:
        raise ValueError("Le manifeste doit être servi en HTTPS")
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _download(url: str, timeout: float = DEFAULT_TIMEOUT) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _verify_sha256(data: bytes, expected: str) -> bool:
    return hashlib.sha256(data).hexdigest().lower() == expected.lower()


# --------------------------------------------------------------------------
# Vérification + préparation
# --------------------------------------------------------------------------
def check_for_update(manifest_url: str, local_version: str = VERSION,
                     timeout: float = DEFAULT_TIMEOUT) -> Optional[dict]:
    """Renvoie le manifeste s'il décrit une version plus récente, sinon None."""
    manifest = fetch_manifest(manifest_url, timeout)
    if "version" not in manifest:
        raise ValueError("Manifeste invalide : champ 'version' manquant")
    return manifest if is_newer(manifest["version"], local_version) else None


def _extract_zip_to(data: bytes, dest: Path) -> None:
    """Extrait le zip dans `dest`. Si le zip a un unique dossier racine
    (cas des zipball GitHub), on descend dedans pour ne garder que le code."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            # Certains zips construits sous Windows (Compress-Archive,
            # "Envoyer vers > Dossier compressé") stockent les chemins avec
            # des antislashs au lieu de '/'. zipfile ne convertit que '/' en
            # separateur natif : sur macOS/Linux l'antislash reste tel quel,
            # ce qui aplatit l'arborescence en fichiers plats du genre
            # "osmo_controller\auth.py" -- vécu en prod, cf. crash
            # ModuleNotFoundError au démarrage. On normalise avant extraction.
            info.filename = info.filename.replace("\\", "/")
            zf.extract(info, dest)
    entries = [p for p in dest.iterdir() if p.name not in ("__MACOSX",)]
    if len(entries) == 1 and entries[0].is_dir():
        inner = entries[0]
        for item in inner.iterdir():
            shutil.move(str(item), str(dest / item.name))
        inner.rmdir()


def prepare_update(manifest_url: str, app_dir: Path,
                   local_version: str = VERSION,
                   timeout: float = DEFAULT_TIMEOUT) -> Optional[str]:
    """Télécharge la mise à jour si plus récente et la met EN ATTENTE.

    Ne touche pas au code en cours d'exécution : le nouveau code est extrait
    dans `<app_dir>.next`, prêt à être appliqué au prochain démarrage.
    Renvoie la nouvelle version mise en attente, ou None s'il n'y a rien.
    """
    app_dir = Path(app_dir)
    manifest = check_for_update(manifest_url, local_version, timeout)
    if manifest is None:
        return None

    data = _download(manifest["url"], timeout)
    sha = manifest.get("sha256")
    if sha and not _verify_sha256(data, sha):
        raise ValueError("Empreinte SHA-256 invalide — mise à jour rejetée")

    next_dir = app_dir.with_name(app_dir.name + _SUFFIX_NEXT)
    _extract_zip_to(data, next_dir)
    return manifest["version"]


# --------------------------------------------------------------------------
# Application (au démarrage, AVANT de charger le code de l'app)
# --------------------------------------------------------------------------
def has_pending_update(app_dir: Path) -> bool:
    return Path(app_dir).with_name(Path(app_dir).name + _SUFFIX_NEXT).exists()


def finalize_pending_update(app_dir: Path) -> bool:
    """Applique une mise à jour en attente par échange de dossiers.

    `<app_dir>` -> `<app_dir>.bak` (filet), puis `<app_dir>.next` -> `<app_dir>`.
    En cas d'échec, on restaure l'ancienne version. Renvoie True si appliquée.
    """
    app_dir = Path(app_dir)
    next_dir = app_dir.with_name(app_dir.name + _SUFFIX_NEXT)
    bak_dir = app_dir.with_name(app_dir.name + _SUFFIX_BAK)
    if not next_dir.exists():
        return False

    if bak_dir.exists():
        shutil.rmtree(bak_dir)
    try:
        if app_dir.exists():
            app_dir.rename(bak_dir)
        next_dir.rename(app_dir)
    except OSError:
        # Restauration : on remet l'ancienne version si l'échange a échoué.
        if not app_dir.exists() and bak_dir.exists():
            bak_dir.rename(app_dir)
        raise
    return True
