"""
Transport BLE réel (via `bleak`) — implémente l'interface `Transport`.

C'est le SEUL fichier qui parle au vrai Bluetooth. Toute la logique au-dessus
(CameraConnection « erreur proof », CameraManager, UI) reste identique : on
remplace juste SimulatedTransport par BleakTransport.

Séquence de connexion (validée sur une Osmo Action 5 Pro, sans popup) :
  1. connexion BLE + abonnement aux notifications 0xFFF4,
  2. requête de connexion verify_mode=0 (device_id contrôleur non nul + MAC),
  3. la caméra renvoie verify_mode=2 (approuvé) -> on répond ret_code=0,
  4. dès lors : commandes record (1D03) acceptées et pushs statut (1D02) reçus.

Les frames de télémétrie DUML (0x55) émises en continu sont ignorées ; seules
les trames DJI R SDK (0xAA) sont transmises à la couche supérieure. Le handshake
de connexion (0x00/0x19) est traité ICI et n'est pas remonté.
"""

from __future__ import annotations
import asyncio
import gc
from typing import Callable, Optional

from bleak import BleakClient

from . import protocol as p
from .connection import Transport

# Identité « contrôleur » envoyée à la caméra pour la connexion.
# device_id doit être NON NUL et différent de celui de la caméra ; la MAC
# doit être non vide. Les valeurs exactes importent peu, mais ces contraintes
# sont nécessaires pour que la caméra réponde.
_CTRL_DEVICE_ID = 0x11223344
_CTRL_MAC = b"AA:BB:CC:DD:EE"

# 8 s suffit en Python normal, mais un .app macOS empaqueté (PyInstaller
# --windowed) sert la boucle d'événements CoreBluetooth plus lentement
# (pas de NSApplication au premier plan) : la connexion BLE peut alors
# prendre jusqu'à ~20 s avant d'aboutir. Une marge généreuse évite une
# boucle connexion/timeout/reconnexion infinie qui ressemble à une panne
# permanente alors que la caméra est bien joignable (vérifié sur matériel réel).
_HANDSHAKE_TIMEOUT = 25.0


class BleakTransport(Transport):
    def __init__(self, address: str, *, name: str = "cam",
                 ctrl_device_id: int = _CTRL_DEVICE_ID) -> None:
        self.address = address
        self.name = name
        self._ctrl_device_id = ctrl_device_id

        self._client: Optional[BleakClient] = None
        self._notify_cb: Optional[Callable[[bytes], None]] = None
        self._disc_cb: Optional[Callable[[], None]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Créé dans connect() (pas ici) : un asyncio.Event() construit avant
        # que la boucle de connect() ne tourne se lie, sous Python 3.9, à la
        # boucle active AU MOMENT DE SA CRÉATION (pas au premier await) --
        # ici, BleakTransport est construit AVANT asyncio.run(main(...)),
        # donc sur une autre boucle. Résultat : « Task ... attached to a
        # different loop » dès le premier await de ._approved, invisible
        # tant que _try_connect() avalait l'exception. Vérifié sur matériel
        # réel (macOS, Python 3.9) : la connexion BLE réussissait, mais le
        # handshake plantait juste après, laissant le lien à moitié ouvert.
        self._approved: Optional[asyncio.Event] = None
        self._seq = 0
        self._reassembler = p.FrameReassembler()

    # --- interface Transport ---------------------------------------- #
    def set_notify_callback(self, cb: Callable[[bytes], None]) -> None:
        self._notify_cb = cb

    def set_disconnect_callback(self, cb: Callable[[], None]) -> None:
        self._disc_cb = cb

    async def connect(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._approved = asyncio.Event()
        self._client = BleakClient(self.address,
                                   disconnected_callback=self._on_ble_disconnect)
        # timeout par défaut de bleak (10 s) trop court pour un .app macOS
        # empaqueté (--windowed) : voir _HANDSHAKE_TIMEOUT ci-dessus, même cause.
        await self._client.connect(timeout=_HANDSHAKE_TIMEOUT)
        await self._client.start_notify(p.NOTIFY_CHAR_UUID, self._on_raw_notify)

        # Handshake : requête verify_mode=0 -> attend l'approbation (verify_mode=2).
        req = p.build_connection_request(
            self._next_seq(), device_id_u32=self._ctrl_device_id,
            verify_mode=0, mac_addr=_CTRL_MAC,
        )
        await self._client.write_gatt_char(p.WRITE_CHAR_UUID, req, response=False)
        try:
            await asyncio.wait_for(self._approved.wait(), timeout=_HANDSHAKE_TIMEOUT)
        except asyncio.TimeoutError as e:
            raise ConnectionError(f"{self.name} : handshake de connexion expiré") from e

    async def disconnect(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        # Déconnexion INCONDITIONNELLE (is_connected n'est pas fiable sur WinRT)
        # et bornée dans le temps pour ne jamais bloquer l'arrêt de l'app.
        try:
            await asyncio.wait_for(client.disconnect(), timeout=6.0)
            print(f"  [{self.name}] Bluetooth déconnecté", flush=True)
        except asyncio.TimeoutError:
            print(f"  [{self.name}] déconnexion lente (délai dépassé)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  [{self.name}] déconnexion : {type(e).__name__}", flush=True)

        # IMPORTANT (Windows/WinRT) : Windows garde le lien tant que l'objet
        # BluetoothLEDevice n'est pas DÉTRUIT — une simple disconnect() ne suffit
        # pas si l'app continue de tourner (cas « Retirer une caméra »). On ferme
        # explicitement le périphérique WinRT et on force le ramasse-miettes pour
        # relâcher réellement la caméra.
        try:
            backend = getattr(client, "_backend", client)
            for attr in ("_requester", "_device", "_device_info"):
                dev = getattr(backend, attr, None)
                if dev is not None and hasattr(dev, "close"):
                    dev.close()
        except Exception:  # noqa: BLE001
            pass
        del client
        gc.collect()

    async def write(self, frame: bytes) -> None:
        if self._client is None or not self._client.is_connected:
            raise ConnectionError(f"{self.name} : non connecté")
        await self._client.write_gatt_char(p.WRITE_CHAR_UUID, frame, response=False)

    # --- réception BLE ---------------------------------------------- #
    def _on_raw_notify(self, _char, data: bytearray) -> None:
        # Une notification BLE ne contient pas forcément une trame complète
        # (dépend du MTU négocié, variable selon la plateforme) : on ré-assemble
        # via le champ Length avant de traiter quoi que ce soit.
        for frame in self._reassembler.feed(bytes(data)):
            self._handle_frame(frame)

    def _handle_frame(self, b: bytes) -> None:
        try:
            f = p.parse_frame(b)
        except ValueError:
            return
        if not (f.crc16_ok and f.crc32_ok):
            return

        # Handshake de connexion : traité ici, non remonté.
        if (f.cmd_set, f.cmd_id) == (0x00, 0x19):
            info = p.parse_connection(f.payload)
            if info.get("verify_mode") == 2 and info.get("verify_data", 1) == 0:
                # Approuvé : on accuse réception, ce qui finalise la connexion.
                resp = p.build_connection_response(f.seq, self._ctrl_device_id, ret_code=0)
                if self._client is not None:
                    asyncio.ensure_future(
                        self._client.write_gatt_char(p.WRITE_CHAR_UUID, resp, response=False)
                    )
                self._approved.set()
            return

        # Tout le reste (statut 1D02, accusés 1D03/1D05) remonte à CameraConnection.
        if self._notify_cb is not None:
            self._notify_cb(b)

    def _on_ble_disconnect(self, _client) -> None:
        if self._disc_cb is not None:
            self._disc_cb()

    # --- interne ---------------------------------------------------- #
    def _next_seq(self) -> int:
        self._seq = (self._seq + 1) & 0xFFFF
        return self._seq
