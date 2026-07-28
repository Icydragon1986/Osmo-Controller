"""
Transport simulé : branche `CameraConnection` sur `OsmoCameraSimulator`
au lieu d'un vrai BLE. C'est lui qui permet de tester toute la couche
« erreur proof » (connexion, abonnement, reconnexion) sans matériel.

Il sait aussi *simuler des pannes* :
  - `fail_times` : échoue les N premières connexions (test de retry),
  - `simulate_drop()` : coupe le lien en plein vol (test de reconnexion auto).
"""

from __future__ import annotations
import asyncio
import random
from typing import Callable, Optional

from .connection import Transport
from .simulator import OsmoCameraSimulator


class SimulatedTransport(Transport):
    def __init__(
        self,
        camera: Optional[OsmoCameraSimulator] = None,
        *,
        tick_interval: float = 0.05,
        connect_delay: float = 0.0,
        command_latency: float = 0.0,
        jitter: float = 0.0,
        fail_times: int = 0,
    ) -> None:
        self.cam = camera or OsmoCameraSimulator()
        self._tick_interval = tick_interval
        self._connect_delay = connect_delay
        self._command_latency = command_latency  # délai avant traitement d'une commande
        self._jitter = jitter                    # variation aléatoire ajoutée aux délais
        self._fail_times = fail_times

        self._connected = False
        self._notify: Optional[Callable[[bytes], None]] = None
        self._on_disc: Optional[Callable[[], None]] = None
        self._tick_task: Optional[asyncio.Task] = None

    # --- interface Transport ---------------------------------------- #
    def set_notify_callback(self, cb: Callable[[bytes], None]) -> None:
        self._notify = cb

    def set_disconnect_callback(self, cb: Callable[[], None]) -> None:
        self._on_disc = cb

    async def connect(self) -> None:
        if self._connect_delay or self._jitter:
            await asyncio.sleep(self._connect_delay + self._rand_jitter())
        if self._fail_times > 0:
            self._fail_times -= 1
            raise ConnectionError("échec de connexion simulé")
        self._connected = True
        self._tick_task = asyncio.ensure_future(self._tick_loop())

    async def disconnect(self) -> None:
        self._connected = False
        await self._cancel_ticks()

    async def write(self, frame: bytes) -> None:
        if not self._connected:
            raise ConnectionError("non connecté")
        if self._command_latency or self._jitter:
            await asyncio.sleep(self._command_latency + self._rand_jitter())
        if not self._connected:                  # le lien a pu tomber pendant l'attente
            raise ConnectionError("non connecté")
        for resp in self.cam.handle_command(frame):
            self._emit(resp)

    # --- simulation de pannes --------------------------------------- #
    def simulate_drop(self) -> None:
        """Coupe le lien comme si le BLE tombait, et le signale en haut."""
        self._connected = False
        # On annule la boucle de ticks sans attendre (appel synchrone).
        if self._tick_task is not None:
            self._tick_task.cancel()
            self._tick_task = None
        if self._on_disc is not None:
            self._on_disc()

    # --- interne ---------------------------------------------------- #
    async def _tick_loop(self) -> None:
        try:
            while self._connected:
                await asyncio.sleep(self._tick_interval)
                for frame in self.cam.tick(self._tick_interval):
                    self._emit(frame)
        except asyncio.CancelledError:
            pass

    async def _cancel_ticks(self) -> None:
        if self._tick_task is not None:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None

    def _emit(self, frame: bytes) -> None:
        if self._notify is not None:
            self._notify(frame)

    def _rand_jitter(self) -> float:
        return random.uniform(0, self._jitter) if self._jitter else 0.0
