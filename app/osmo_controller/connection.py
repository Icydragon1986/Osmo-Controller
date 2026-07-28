"""
Machine à états de connexion pour UNE caméra — la couche « erreur proof ».

Responsabilités :
  - connecter / (ré)appairer / s'abonner au statut,
  - recevoir les pushs de statut en continu,
  - se RECONNECTER automatiquement si le lien BLE tombe,
  - exposer start/stop enregistrement quand on est connecté.

Conception : agnostique du transport. `CameraConnection` ne connaît pas BLE ;
il parle à un `Transport` abstrait. En test on lui donne un `SimulatedTransport`
(voir sim_transport.py) ; en production on lui donnera un transport `bleak`.
Toute la logique de robustesse est donc testable à 100 % sans matériel.

Cycle de vie (un seul superviseur asyncio) :

    DISCONNECTED → CONNECTING → CONNECTED
                       ↑            │ (lien perdu)
                       │            ↓
                   RECONNECTING ←───┘
    stop() → CLOSED (définitif, plus de reconnexion)
"""

from __future__ import annotations
import abc
import asyncio
import enum
import time
from typing import Callable, Optional

from . import protocol as p


class ConnectionState(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


class NotConnectedError(RuntimeError):
    """Levée si on tente une commande alors qu'on n'est pas connecté."""


class Transport(abc.ABC):
    """Canal d'octets vers une caméra. Le vrai BLE et le simulateur en héritent.

    Le transport signale une perte de lien INATTENDUE en appelant le callback
    fourni à `set_disconnect_callback`. Les trames reçues de la caméra
    (réponses + pushs) sont remises via le callback de `set_notify_callback`.
    """

    @abc.abstractmethod
    async def connect(self) -> None:
        """Établit le lien (inclut l'appairage). Lève en cas d'échec."""

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Ferme proprement le lien (ne déclenche PAS le callback de perte)."""

    @abc.abstractmethod
    async def write(self, frame: bytes) -> None:
        """Envoie une trame de commande à la caméra."""

    @abc.abstractmethod
    def set_notify_callback(self, cb: Callable[[bytes], None]) -> None:
        """Enregistre le callback appelé pour chaque trame reçue."""

    @abc.abstractmethod
    def set_disconnect_callback(self, cb: Callable[[], None]) -> None:
        """Enregistre le callback appelé lors d'une perte de lien inattendue."""


class CameraConnection:
    """Maintient la connexion à une caméra et la rend robuste."""

    def __init__(
        self,
        transport: Transport,
        *,
        model: str = "osmo_action_5_pro",
        name: str = "cam",
        reconnect_delay: float = 2.0,
        on_status: Optional[Callable[[dict], None]] = None,
        on_state: Optional[Callable[[ConnectionState], None]] = None,
    ) -> None:
        self._transport = transport
        self.model = model
        self.name = name
        self.reconnect_delay = reconnect_delay
        self._on_status = on_status
        self._on_state = on_state

        self.state = ConnectionState.DISCONNECTED
        self.last_status: Optional[dict] = None
        self._last_status_ts: Optional[float] = None

        self._want_connected = False
        self._seq = 0
        self._task: Optional[asyncio.Task] = None
        self._link_lost = asyncio.Event()
        self._connected_event = asyncio.Event()

        transport.set_notify_callback(self._on_frame)
        transport.set_disconnect_callback(self._on_link_lost)

    @property
    def device_id(self) -> int:
        return p.DEVICE_IDS[self.model]

    @property
    def is_connected(self) -> bool:
        return self.state is ConnectionState.CONNECTED

    @property
    def status_age_s(self) -> Optional[float]:
        """Secondes depuis le dernier push de statut (None si jamais reçu)."""
        if self._last_status_ts is None:
            return None
        return time.monotonic() - self._last_status_ts

    # ------------------------------------------------------------------ #
    # Contrôle public
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Lance le superviseur qui maintient la connexion en arrière-plan."""
        if self._task is not None and not self._task.done():
            return
        self._want_connected = True
        self._task = asyncio.ensure_future(self._supervise())

    async def stop(self) -> None:
        """Arrête définitivement : plus aucune reconnexion."""
        self._want_connected = False
        self._link_lost.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._transport.disconnect()
        self._set_state(ConnectionState.CLOSED)

    async def wait_connected(self, timeout: float = 5.0) -> None:
        """Attend que l'état devienne CONNECTED (utile en test et au démarrage)."""
        await asyncio.wait_for(self._connected_event.wait(), timeout)

    async def start_recording(self) -> None:
        await self._send(p.build_record_command(True, self.device_id, self._next_seq()))

    async def stop_recording(self) -> None:
        await self._send(p.build_record_command(False, self.device_id, self._next_seq()))

    # ------------------------------------------------------------------ #
    # Superviseur : connecte et reconnecte tant qu'on le souhaite
    # ------------------------------------------------------------------ #
    async def _supervise(self) -> None:
        try:
            while self._want_connected:
                connected = await self._try_connect()
                if not connected:
                    self._set_state(ConnectionState.RECONNECTING)
                    await asyncio.sleep(self.reconnect_delay)
                    continue

                # Connecté : on attend une éventuelle perte de lien.
                self._link_lost.clear()
                await self._link_lost.wait()

                if self._want_connected:
                    self._set_state(ConnectionState.RECONNECTING)
                    await asyncio.sleep(self.reconnect_delay)
        except asyncio.CancelledError:
            raise
        finally:
            self._connected_event.clear()
            if self.state is not ConnectionState.CLOSED:
                self._set_state(ConnectionState.DISCONNECTED)

    async def _try_connect(self) -> bool:
        """Une tentative complète : connexion + appairage + abonnement."""
        try:
            self._set_state(ConnectionState.CONNECTING)
            await self._transport.connect()          # inclut l'appairage BLE
            await self._transport.write(
                p.build_status_subscription(self._next_seq())
            )
            self._set_state(ConnectionState.CONNECTED)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Callbacks venant du transport
    # ------------------------------------------------------------------ #
    def _on_frame(self, frame: bytes) -> None:
        try:
            f = p.parse_frame(frame)
        except ValueError:
            return
        if not (f.crc16_ok and f.crc32_ok):
            return
        if (f.cmd_set, f.cmd_id) == (0x1D, 0x02):     # push de statut
            self.last_status = p.parse_camera_status(f.payload)
            self._last_status_ts = time.monotonic()
            if self._on_status is not None:
                self._on_status(self.last_status)

    def _on_link_lost(self) -> None:
        """Le transport nous signale une perte de lien inattendue."""
        self._connected_event.clear()
        self._link_lost.set()

    # ------------------------------------------------------------------ #
    # Interne
    # ------------------------------------------------------------------ #
    async def _send(self, frame: bytes) -> None:
        if self.state is not ConnectionState.CONNECTED:
            raise NotConnectedError(f"{self.name} : non connecté")
        await self._transport.write(frame)

    def _next_seq(self) -> int:
        self._seq = (self._seq + 1) & 0xFFFF
        return self._seq

    def _set_state(self, state: ConnectionState) -> None:
        if state == self.state:
            return
        self.state = state
        if state is ConnectionState.CONNECTED:
            self._connected_event.set()
        else:
            self._connected_event.clear()
        if self._on_state is not None:
            self._on_state(state)
