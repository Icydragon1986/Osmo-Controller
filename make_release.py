"""
Construit releases/osmo-X.Y.Z.zip depuis app/ et met à jour releases/manifest.json.

Pourquoi ce script existe : zipper app/ à la main (Compress-Archive sous
PowerShell, ou l'Explorateur Windows via "Envoyer vers > Dossier compressé")
stocke parfois les chemins avec des antislashs au lieu de '/' (non standard,
la spec zip impose '/'). zipfile.extractall() ne convertit que '/' en
séparateur natif : sur macOS/Linux l'antislash reste tel quel dans le nom de
fichier, ce qui aplatit tout osmo_controller/ en fichiers plats et casse le
paquet (ModuleNotFoundError au démarrage). Vécu en prod sur les releases
0.10.1 à 0.16.0. Ce script zippe toujours avec '/', quelle que soit la
plateforme utilisée pour couper la release.

Usage :
    python3 make_release.py 0.16.1 --notes "Ce qui a changé"

Ne touche PAS à app/osmo_controller/version.py (VERSION doit déjà avoir été
bumpé à la main avant de lancer ce script, pour rester la source de vérité
unique lue par l'UI).
"""
from __future__ import annotations
import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "app"
RELEASES_DIR = ROOT / "releases"
MANIFEST_URL_BASE = (
    "https://raw.githubusercontent.com/Icydragon1986/Osmo-Controller/main/releases"
)
_SKIP_DIRS = {"__pycache__"}


def _iter_app_files():
    for path in sorted(APP_DIR.rglob("*")):
        if path.is_dir():
            continue
        if _SKIP_DIRS & set(path.relative_to(APP_DIR).parts):
            continue
        yield path


def build_zip(zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in _iter_app_files():
            arcname = path.relative_to(APP_DIR).as_posix()  # toujours '/'
            zf.write(path, arcname)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def update_manifest(version: str, sha256: str, notes: str) -> None:
    manifest_path = RELEASES_DIR / "manifest.json"
    manifest_path.write_text(
        "{\n"
        f'  "version": "{version}",\n'
        f'  "url": "{MANIFEST_URL_BASE}/osmo-{version}.zip",\n'
        f'  "sha256": "{sha256}",\n'
        f'  "notes": "{notes}"\n'
        "}\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="ex. 0.16.1 -- doit matcher app/osmo_controller/version.py")
    parser.add_argument("--notes", default="", help="notes de version pour le manifeste")
    args = parser.parse_args()

    current_version = (APP_DIR / "osmo_controller" / "version.py").read_text(encoding="utf-8")
    if f'"{args.version}"' not in current_version:
        print(
            f"Attention : app/osmo_controller/version.py ne contient pas VERSION = \"{args.version}\". "
            "Bump la version avant de couper la release.",
            file=sys.stderr,
        )
        return 1

    RELEASES_DIR.mkdir(exist_ok=True)
    zip_path = RELEASES_DIR / f"osmo-{args.version}.zip"
    build_zip(zip_path)
    sha256 = sha256_of(zip_path)
    update_manifest(args.version, sha256, args.notes)

    print(f"Release {args.version} : {zip_path} (sha256 {sha256})")
    print("releases/manifest.json mis à jour.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
