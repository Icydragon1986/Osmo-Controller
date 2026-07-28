"""
Gestion des caméras depuis l'interface (mode réel) : rechercher (scan BLE),
ajouter, retirer — sans toucher au terminal ni à cameras.json à la main.

L'ajout crée un BleakTransport, l'insère dans le gestionnaire en marche,
lance la connexion, ET persiste dans cameras.json (mémorisé au prochain lancement).
"""

from __future__ import annotations
from pathlib import Path

from .config import load_cameras, save_cameras
from .manager import CameraManager

_NAME_HINTS = ("osmo", "dji", "action", "oa5", "bcc")
_DEFAULT_MODEL = "osmo_action_5_pro"


class RealCameraAdmin:
    def __init__(self, manager: CameraManager, config_path) -> None:
        self.manager = manager
        self.config_path = Path(config_path)

    def _known_addresses(self) -> set[str]:
        return {c["address"] for c in load_cameras(self.config_path)}

    async def scan(self, timeout: float = 6.0) -> list[dict]:
        """Scanne le BLE et renvoie les appareils, candidats caméra en tête."""
        from bleak import BleakScanner  # import local : n'exige bleak qu'ici

        known = self._known_addresses()
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
        out = []
        for dev, adv in devices.values():
            name = dev.name or adv.local_name or ""
            services = [str(u).lower() for u in (adv.service_uuids or [])]
            is_cam = (any(h in name.lower() for h in _NAME_HINTS)
                      or any("fff0" in u for u in services))
            out.append({
                "address": dev.address,
                "name": name or "(sans nom)",
                "rssi": adv.rssi,
                "candidate": is_cam,
                "added": dev.address in known,
            })
        out.sort(key=lambda d: (not d["candidate"], -(d["rssi"] or -999)))
        return out

    async def add(self, name: str, address: str,
                  model: str = _DEFAULT_MODEL) -> dict:
        """Ajoute une caméra : persiste, crée le transport, connecte."""
        from .bleak_transport import BleakTransport

        name = (name or "").strip()
        if not name:
            raise ValueError("Nom vide")
        if self.manager.has(name):
            raise ValueError(f"Une caméra nommée « {name} » existe déjà")

        cams = load_cameras(self.config_path)
        cams = [c for c in cams if c["address"] != address]   # évite les doublons d'adresse
        cams.append({"name": name, "address": address, "model": model})
        save_cameras(self.config_path, cams)

        conn = self.manager.add_camera(name, BleakTransport(address, name=name), model=model)
        conn.start()
        return {"name": name, "address": address, "model": model}

    async def remove(self, name: str) -> None:
        """Retire une caméra : la déconnecte et l'efface de la config."""
        await self.manager.remove_camera(name)
        cams = [c for c in load_cameras(self.config_path) if c["name"] != name]
        save_cameras(self.config_path, cams)
