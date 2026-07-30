"""
Contrôle du point d'accès Wi-Fi (« Mobile Hotspot ») du PC, pour les
tournois sans Wi-Fi fiable — Windows seulement.

Deux mécanismes, essayés dans cet ordre :

  1. Mobile Hotspot (`NetworkOperatorTetheringManager`, API moderne) —
     vérifié RÉELLEMENT sur matériel : configuration lue, hotspot démarré
     (adresse 192.168.137.1 confirmée active), puis arrêté proprement. Ne
     reconfigure PAS le SSID/mot de passe par défaut — démarre/arrête avec
     la config déjà présente sur la machine (Paramètres > Réseau > Point
     d'accès mobile), pour ne pas casser un nom/mot de passe déjà communiqué
     à l'équipe.

     LIMITE (vécue en prod) : cette API exige une connexion internet déjà
     active à partager (`get_internet_connection_profile()`), même si
     techniquement elle ne s'en sert pas pour les appareils qui la
     rejoignent. Sans Ethernet ni autre Wi-Fi connecté, elle refuse de
     démarrer — ce qui contredit le besoin réel en tournoi (zéro réseau
     disponible sur place).

  2. Repli « réseau hébergé » (legacy, `netsh wlan hostednetwork`) — ne
     nécessite AUCUNE connexion à partager, seulement un SSID/mot de passe
     à créer, lus depuis `wifi_config.json` (racine, rempli une fois par
     `manage_wifi.py set <nom> <mot de passe>`). Utilisé uniquement quand
     le Mobile Hotspot n'a rien à partager. Caveat : certains pilotes Wi-Fi
     récents (surtout sous Windows 11) ont retiré le support de cette
     fonctionnalité au profit du Mobile Hotspot — vérifiable avec
     `netsh wlan show drivers` (ligne « Réseau hébergé pris en charge »).

macOS : pas d'équivalent programmable ici (Apple n'expose aucune API/CLI
publique pour "Internet Sharing"). Voir le README pour la marche à suivre
manuelle (Réglages Système > Partage de connexion internet) + `manage_wifi.py
set`, qui alimente le même code QR sans passer par ce module.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from . import wifi_info


class HotspotUnavailable(Exception):
    """Le hotspot n'est pas disponible sur cette machine (pas Windows, pas
    d'adaptateur compatible, ou aucun réseau configuré pour le repli)."""


class _NoUplink(Exception):
    """Interne : le Mobile Hotspot n'a aucune connexion à partager —
    déclenche le repli sur le réseau hébergé (legacy, sans internet)."""


def _mobile_hotspot_manager():
    # Import local : Windows seulement, et seulement si on utilise vraiment
    # cette fonctionnalité (comme bleak/qrcode, pas exigé du reste de l'app).
    try:
        from winrt.windows.networking.networkoperators import NetworkOperatorTetheringManager
        from winrt.windows.networking.connectivity import NetworkInformation
    except ImportError as e:
        raise HotspotUnavailable(
            "Fonction Windows seulement (pip install "
            "winrt-Windows.Networking.NetworkOperators winrt-Windows.Networking.Connectivity)"
        ) from e

    profile = NetworkInformation.get_internet_connection_profile()
    if profile is None:
        raise _NoUplink()
    return NetworkOperatorTetheringManager.create_from_connection_profile(profile)


_STATE_NAMES = {0: "inconnu", 1: "actif", 2: "arrêté", 3: "en cours de changement"}


# --------------------------------------------------------------------------
# Repli « réseau hébergé » (legacy, sans internet)
# --------------------------------------------------------------------------
def _hosted_network_status() -> Optional[dict]:
    """État actuel du réseau hébergé, ou None si jamais configuré / netsh
    indisponible (pas Windows)."""
    out = wifi_info._run_netsh(["wlan", "show", "hostednetwork"])
    if out is None:
        return None
    ssid = wifi_info._find_value(out, "SSID")
    if not ssid:
        return None
    status = wifi_info._find_value(out, "État", "Status") or ""
    on = status.lower().startswith(("démarré", "started"))
    passphrase = ""
    if on:
        # La clé n'apparaît pas dans "show hostednetwork" par défaut, il faut
        # le demander explicitement (même champ que pour un profil Wi-Fi normal).
        sec = wifi_info._run_netsh(["wlan", "show", "hostednetwork", "setting=security"])
        if sec:
            passphrase = wifi_info._find_value(sec, "Contenu de la clé", "Key Content") or ""
    return {"available": True, "backend": "hosted_network", "state": status or "inconnu",
            "on": on, "ssid": ssid, "passphrase": passphrase}


def _start_hosted_network(wifi_config_path: Optional[Path]) -> dict:
    cfg = wifi_info.load_wifi_config(wifi_config_path) if wifi_config_path else None
    if not cfg:
        raise HotspotUnavailable(
            "Aucune connexion internet à partager, et aucun réseau configuré pour "
            "le point d'accès autonome. Configure-en un d'abord :\n"
            "  python manage_wifi.py set <nom> <mot de passe>"
        )
    ssid, password = cfg["ssid"], cfg["password"]
    if len(password) < 8:
        raise HotspotUnavailable(
            "Le mot de passe du réseau hébergé doit faire au moins 8 caractères "
            "(exigence de Windows) — reconfigure-le avec manage_wifi.py set."
        )
    set_out = wifi_info._run_netsh(
        ["wlan", "set", "hostednetwork", "mode=allow", f"ssid={ssid}", f"key={password}"])
    if set_out is None:
        raise HotspotUnavailable("netsh indisponible (pas Windows ?).")
    wifi_info._run_netsh(["wlan", "start", "hostednetwork"])
    status = _hosted_network_status()
    if not status or not status.get("on"):
        raise HotspotUnavailable(
            "Échec du démarrage du réseau hébergé — ton adaptateur Wi-Fi ne le "
            "supporte peut-être pas. Vérifie avec :  netsh wlan show drivers  "
            "(ligne « Réseau hébergé pris en charge »)."
        )
    return status


def _stop_hosted_network() -> dict:
    wifi_info._run_netsh(["wlan", "stop", "hostednetwork"])
    return _hosted_network_status() or {"available": False}


# --------------------------------------------------------------------------
# API publique (utilisée par webserver.py)
# --------------------------------------------------------------------------
async def get_status(wifi_config_path: Optional[Path] = None) -> dict:
    """État actuel + config (SSID/mot de passe) — Mobile Hotspot si une
    connexion existe à partager, sinon l'état du réseau hébergé (repli)."""
    hosted = _hosted_network_status()
    if hosted and hosted.get("on"):
        return hosted  # déjà actif : c'est la vérité du terrain, prime sur le reste

    try:
        mgr = _mobile_hotspot_manager()
    except _NoUplink:
        return hosted or {"available": False}
    cfg = mgr.get_current_access_point_configuration()
    return {
        "available": True, "backend": "mobile_hotspot",
        "state": _STATE_NAMES.get(int(mgr.tethering_operational_state), "inconnu"),
        "on": int(mgr.tethering_operational_state) == 1,
        "ssid": cfg.ssid, "passphrase": cfg.passphrase,
    }


async def start(wifi_config_path: Optional[Path] = None) -> dict:
    """Démarre le hotspot. Mobile Hotspot si une connexion existe à
    partager (config déjà présente sur la machine, inchangée) ; sinon
    réseau hébergé (legacy) avec le SSID/mot de passe de wifi_config.json."""
    try:
        mgr = _mobile_hotspot_manager()
    except _NoUplink:
        return _start_hosted_network(wifi_config_path)
    result = await mgr.start_tethering_async()
    if int(result.status) != 0:
        raise HotspotUnavailable(f"Échec du démarrage (code {int(result.status)}).")
    return await get_status(wifi_config_path)


async def stop(wifi_config_path: Optional[Path] = None) -> dict:
    try:
        mgr = _mobile_hotspot_manager()
    except _NoUplink:
        return _stop_hosted_network()
    result = await mgr.stop_tethering_async()
    if int(result.status) != 0:
        raise HotspotUnavailable(f"Échec de l'arrêt (code {int(result.status)}).")
    return await get_status(wifi_config_path)
