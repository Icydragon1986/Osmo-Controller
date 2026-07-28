"""
Gestionnaire multi-caméras : pilote N caméras INDÉPENDANTES (une par terrain).

Chaque caméra a sa propre `CameraConnection` (donc sa propre logique de
reconnexion). Le gestionnaire ajoute :
  - le contrôle GLOBAL (tout démarrer / tout arrêter l'enregistrement),
  - un instantané (`snapshot`) de l'état de chaque caméra pour l'UI.

Reste agnostique du transport : on lui passe un transport par caméra
(simulé aujourd'hui, BLE `bleak` demain).
"""

from __future__ import annotations
import asyncio
from typing import Callable, Optional

from .connection import CameraConnection, ConnectionState, Transport


class CameraManager:
    def __init__(self, *, reconnect_delay: float = 2.0) -> None:
        self._reconnect_delay = reconnect_delay
        self._cams: dict[str, CameraConnection] = {}

    # ------------------------------------------------------------------ #
    # Composition
    # ------------------------------------------------------------------ #
    def add_camera(
        self,
        name: str,
        transport: Transport,
        *,
        model: str = "osmo_action_5_pro",
        on_status: Optional[Callable[[dict], None]] = None,
        on_state: Optional[Callable[[ConnectionState], None]] = None,
    ) -> CameraConnection:
        if name in self._cams:
            raise ValueError(f"Une caméra nommée {name!r} existe déjà")
        conn = CameraConnection(
            transport, model=model, name=name,
            reconnect_delay=self._reconnect_delay,
            on_status=on_status, on_state=on_state,
        )
        self._cams[name] = conn
        return conn

    def get(self, name: str) -> CameraConnection:
        return self._cams[name]

    async def remove_camera(self, name: str) -> None:
        """Arrête et retire une caméra du gestionnaire."""
        conn = self._cams.pop(name, None)
        if conn is not None:
            await conn.stop()

    async def reset_camera(self, name: str) -> None:
        """Relance la connexion d'une caméra (récupération en un clic)."""
        conn = self._cams.get(name)
        if conn is not None:
            await conn.stop()
            conn.start()

    def has(self, name: str) -> bool:
        return name in self._cams

    @property
    def names(self) -> list[str]:
        return list(self._cams)

    @property
    def cameras(self) -> list[CameraConnection]:
        return list(self._cams.values())

    # ------------------------------------------------------------------ #
    # Contrôle global (toujours par-caméra possible via .get(name))
    # ------------------------------------------------------------------ #
    def start_all(self) -> None:
        for conn in self._cams.values():
            conn.start()

    async def stop_all(self) -> None:
        await asyncio.gather(*(c.stop() for c in self._cams.values()))

    async def start_recording_all(self) -> dict[str, bool]:
        """Démarre l'enregistrement sur toutes les caméras connectées.

        Renvoie {nom: succès}. Une caméra non connectée échoue sans
        faire planter les autres (chaque caméra est indépendante).
        """
        return await self._for_each(lambda c: c.start_recording())

    async def stop_recording_all(self) -> dict[str, bool]:
        return await self._for_each(lambda c: c.stop_recording())

    async def _for_each(self, action) -> dict[str, bool]:
        names = list(self._cams)
        results = await asyncio.gather(
            *(action(self._cams[n]) for n in names),
            return_exceptions=True,
        )
        return {n: not isinstance(r, Exception) for n, r in zip(names, results)}

    # ------------------------------------------------------------------ #
    # Vue d'ensemble pour l'UI
    # ------------------------------------------------------------------ #
    def snapshot(self) -> list[dict]:
        """Instantané sérialisable (JSON) de l'état de chaque caméra."""
        out = []
        for name, conn in self._cams.items():
            st = conn.last_status or {}
            age = conn.status_age_s
            out.append({
                "name": name,
                "model": conn.model,
                "state": conn.state.value,
                "connected": conn.is_connected,
                "status_age_s": None if age is None else round(age, 1),
                "battery_pct": st.get("battery_pct"),
                "is_recording": st.get("is_recording", False),
                "record_time_s": st.get("record_time_s"),
                "remain_time_s": st.get("remain_time_s"),
                "remain_capacity_mb": st.get("remain_capacity_mb"),
                "temperature": st.get("temperature"),
                "mode": st.get("mode"),
            })
        return out
