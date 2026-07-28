"""
Contrôle du point d'accès Wi-Fi (« Mobile Hotspot ») du PC, pour les
tournois sans Wi-Fi fiable — Windows seulement.

Utilise `NetworkOperatorTetheringManager` (API Windows), vérifié RÉELLEMENT
sur matériel : configuration lue, hotspot démarré (adresse 192.168.137.1
confirmée active), puis arrêté proprement.

Ne reconfigure PAS le SSID/mot de passe par défaut — on démarre/arrête avec
la config déjà présente sur la machine (déjà définie par Windows ou par
l'utilisateur dans Paramètres > Réseau > Point d'accès mobile). Ça évite de
casser un nom/mot de passe que quelqu'un a déjà communiqué à son équipe.
"""

from __future__ import annotations
from typing import Optional


class HotspotUnavailable(Exception):
    """Le hotspot n'est pas disponible sur cette machine (pas Windows, pas
    d'adaptateur compatible, ou aucune connexion réseau à partager)."""


def _manager():
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
        raise HotspotUnavailable(
            "Aucune connexion réseau active à partager (branche l'Ethernet, "
            "ou active un adaptateur réseau, avant de démarrer le hotspot)."
        )
    return NetworkOperatorTetheringManager.create_from_connection_profile(profile)


_STATE_NAMES = {0: "inconnu", 1: "actif", 2: "arrêté", 3: "en cours de changement"}


async def get_status() -> dict:
    """État actuel + config (SSID/mot de passe) déjà présente sur la machine,
    que le hotspot soit allumé ou non."""
    mgr = _manager()
    cfg = mgr.get_current_access_point_configuration()
    return {
        "available": True,
        "state": _STATE_NAMES.get(int(mgr.tethering_operational_state), "inconnu"),
        "on": int(mgr.tethering_operational_state) == 1,
        "ssid": cfg.ssid,
        "passphrase": cfg.passphrase,
    }


async def start() -> dict:
    """Démarre le hotspot avec la config déjà présente (ne la change pas)."""
    mgr = _manager()
    result = await mgr.start_tethering_async()
    if int(result.status) != 0:
        raise HotspotUnavailable(f"Échec du démarrage (code {int(result.status)}).")
    return await get_status()


async def stop() -> dict:
    mgr = _manager()
    result = await mgr.stop_tethering_async()
    if int(result.status) != 0:
        raise HotspotUnavailable(f"Échec de l'arrêt (code {int(result.status)}).")
    return await get_status()
