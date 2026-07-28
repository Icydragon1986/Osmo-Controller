"""
Info Wi-Fi pour générer un code QR « rejoindre ce réseau » (format WIFI:
reconnu nativement par l'appareil photo d'un iPhone/iPad ou l'appli Caméra
Android — scanner ce code propose directement de se connecter).

Deux sources, dans l'ordre de priorité :
  1. `wifi_config.json` (racine, rempli une fois par `manage_wifi.py`) — pour
     le point d'accès (hotspot) du PC : son SSID/mot de passe ne peuvent PAS
     être lus automatiquement (Windows n'expose pas cette API en Python/CLI),
     donc on te demande de les entrer une fois.
  2. Détection automatique du Wi-Fi normal actuellement connecté (`netsh
     wlan`, Windows seulement) — marche pour le Wi-Fi du lieu sans rien
     configurer, à condition que Windows connaisse déjà ce réseau.
"""

from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path
from typing import Optional


def load_wifi_config(path) -> Optional[dict]:
    """Config manuelle (hotspot). None si absente/vide/invalide."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    ssid = (data.get("ssid") or "").strip()
    if not ssid:
        return None
    return {"ssid": ssid, "password": data.get("password", "")}


def save_wifi_config(path, ssid: str, password: str) -> None:
    Path(path).write_text(
        json.dumps({"ssid": ssid, "password": password}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def clear_wifi_config(path) -> None:
    p = Path(path)
    if p.exists():
        p.unlink()


def _run_netsh(args: list[str]) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["netsh", *args], capture_output=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    raw = proc.stdout
    # L'encodage de la console Windows dépend de la langue/version du système
    # (netsh ne propose pas de sortie structurée) : on essaie plusieurs
    # décodages plutôt que d'en imposer un seul.
    for enc in ("utf-8", "cp1252", "cp850", "cp437"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _find_value(text: str, *labels: str) -> Optional[str]:
    """Cherche une ligne « <label> : valeur » (FR ou EN, espaces variables)."""
    for line in text.splitlines():
        for label in labels:
            m = re.match(rf"\s*{re.escape(label)}\s*:\s*(.*)$", line, re.IGNORECASE)
            if m:
                value = m.group(1).strip()
                if value:
                    return value
    return None


def _is_connected_state(state: str) -> bool:
    """ATTENTION : "déconnecté" contient le sous-texte "connect" (préfixe
    "dé-") — un simple "in" prendrait un Wi-Fi déconnecté pour connecté.
    "connecté"/"connected" COMMENCENT par "connect", "déconnecté"/
    "disconnected" non : startswith() est la bonne vérification ici."""
    return state.lower().startswith("connect")


def detect_connected_wifi() -> Optional[dict]:
    """Wi-Fi normal actuellement connecté (Windows seulement). None si pas de
    Wi-Fi actif, ou si l'appel `netsh` échoue (pas grave : juste pas de QR Wi-Fi)."""
    interfaces = _run_netsh(["wlan", "show", "interfaces"])
    if interfaces is None:
        return None
    state = _find_value(interfaces, "État", "State") or ""
    if not _is_connected_state(state):
        return None
    ssid = _find_value(interfaces, "SSID")
    if not ssid:
        return None

    profile = _run_netsh(["wlan", "show", "profile", ssid, "key=clear"])
    password = ""
    if profile is not None:
        password = _find_value(profile, "Contenu de la clé", "Key Content") or ""
    return {"ssid": ssid, "password": password}


def current_wifi(config_path) -> Optional[dict]:
    """Config manuelle (hotspot) en priorité, sinon détection auto."""
    return load_wifi_config(config_path) or detect_connected_wifi()


def _escape(value: str) -> str:
    """Échappe les caractères spéciaux du format WIFI: (\\ ; , : ")."""
    return re.sub(r'([\\;,:"])', r"\\\1", value)


def wifi_qr_payload(ssid: str, password: str) -> str:
    """Chaîne au format WIFI: — reconnue par l'appareil photo iOS/Android
    pour proposer de rejoindre le réseau directement."""
    auth = "WPA" if password else "nopass"
    return f"WIFI:T:{auth};S:{_escape(ssid)};P:{_escape(password)};;"
