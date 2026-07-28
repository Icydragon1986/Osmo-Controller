"""
Simulateur de caméra DJI Osmo Action (BLE) — une fausse caméra qui parle
le même protocole DJI R SDK que `protocol.py`.

But : développer et tester TOUTE l'app (machine à états de connexion,
gestionnaire multi-caméras, UI) sans aucun matériel. Quand les vraies
caméras arriveront, on remplacera le transport simulé par le vrai BLE
(`bleak`) — la logique au-dessus restera identique.

Le simulateur est volontairement *agnostique du transport* : il ne connaît
ni asyncio ni BLE. On lui donne des octets de commande, il rend des octets
(réponses + pushs de statut). C'est à la couche transport de les acheminer.

Modèle simplifié et documenté (pas deviné) :
  - Réponse à une commande : trame de même CmdSet/CmdID, bit RESPONSE (0x20)
    dans CmdType, payload = 1 octet de code retour (0x00 = OK). C'est une
    simplification raisonnable ; la vraie caméra renvoie un ACK similaire.
  - Push de statut (1D02) : payload de 38 octets, champs placés aux offsets
    décodés par protocol.parse_camera_status().
"""

from __future__ import annotations
import struct
from dataclasses import dataclass, field

from . import protocol as p


@dataclass
class OsmoCameraSimulator:
    """Une fausse Osmo Action. Stateful, déterministe, sans I/O."""

    model: str = "osmo_action_5_pro"
    battery_pct: int = 100
    remain_capacity_mb: int = 60_000          # ~60 Go libres au départ
    temperature: int = 0                       # 0 = normale (voir protocol._TEMP)

    # État interne d'enregistrement
    is_recording: bool = False
    record_time_s: int = 0                     # durée du clip courant
    mode: int = 0x01                           # 0x01 = Vidéo

    # Abonnement au statut
    subscribed: bool = False
    push_freq_hz: float = 2.0

    # Compteurs internes
    _push_seq: int = field(default=0, repr=False)
    _resp_seq: int = field(default=0, repr=False)
    _mb_per_min: int = field(default=300, repr=False)  # débit disque ~1080p30

    @property
    def device_id(self) -> int:
        return p.DEVICE_IDS[self.model]

    @property
    def camera_status(self) -> int:
        """0x03 = en enregistrement, 0x00 = au repos (voir parse_camera_status)."""
        return 0x03 if self.is_recording else 0x00

    @property
    def remain_time_s(self) -> int:
        """Temps d'enregistrement restant, dérivé de l'espace disque libre."""
        if self._mb_per_min <= 0:
            return 0
        return int(self.remain_capacity_mb / self._mb_per_min * 60)

    # ------------------------------------------------------------------ #
    # Réception d'une commande (octets venant de la couche "écriture")
    # ------------------------------------------------------------------ #
    def handle_command(self, frame: bytes) -> list[bytes]:
        """Traite une trame de commande, renvoie 0..n trames à émettre.

        Une trame avec un CRC invalide est ignorée (liste vide) — c'est ce
        que ferait la vraie caméra, et ça permet de tester la robustesse.
        """
        try:
            f = p.parse_frame(frame)
        except ValueError:
            return []
        if not (f.crc16_ok and f.crc32_ok):
            return []

        out: list[bytes] = []
        if (f.cmd_set, f.cmd_id) == (0x1D, 0x03):
            self._cmd_record(f.payload)
            out.append(self._build_response(0x1D, 0x03, f.seq))
            # Un changement d'état déclenche un push immédiat si abonné.
            if self.subscribed:
                out.append(self.build_status_push())
        elif (f.cmd_set, f.cmd_id) == (0x1D, 0x05):
            self._cmd_subscribe(f.payload)
            out.append(self._build_response(0x1D, 0x05, f.seq))
            if self.subscribed:
                out.append(self.build_status_push())
        # CmdSet/CmdID inconnu : on l'ignore silencieusement (comme la caméra).
        return out

    def _cmd_record(self, payload: bytes) -> None:
        # payload = device_id(4) + record_ctrl(1) + reserved(4)
        record_ctrl = payload[4] if len(payload) > 4 else 0x01
        if record_ctrl == 0x00:        # start
            if not self.is_recording:
                self.is_recording = True
                self.record_time_s = 0
                self._rec_frac = 0.0
        else:                          # stop
            self.is_recording = False

    def _cmd_subscribe(self, payload: bytes) -> None:
        push_mode = payload[0] if payload else 0
        self.subscribed = push_mode != 0

    # ------------------------------------------------------------------ #
    # Avancement du temps simulé
    # ------------------------------------------------------------------ #
    def tick(self, dt_s: float = 0.5) -> list[bytes]:
        """Avance l'état de `dt_s` secondes ; renvoie un push si abonné.

        Pendant l'enregistrement : la durée monte, la batterie et l'espace
        disque baissent. Au repos, seule une légère décharge batterie a lieu.
        """
        if self.is_recording:
            self._rec_frac = getattr(self, "_rec_frac", 0.0) + dt_s
            self.record_time_s = int(self._rec_frac)
            used = self._mb_per_min * dt_s / 60
            self.remain_capacity_mb = max(0, int(self.remain_capacity_mb - used))
            # Décharge ~1 % / 90 s en enregistrement
            self._drain(dt_s / 90.0)
            self._heat(dt_s * 0.10)             # chauffe en enregistrement
            if self.remain_capacity_mb == 0:    # SD pleine -> stop auto
                self.is_recording = False
        else:
            self._drain(dt_s / 600.0)           # veille : ~1 % / 10 min
            self._heat(-dt_s * 0.05)            # refroidit au repos

        return [self.build_status_push()] if self.subscribed else []

    def _heat(self, delta: float) -> None:
        """Fait monter/descendre un niveau de chaleur et en dérive la
        température (0 normale, 1 élevée, 2 trop chaude, 3 surchauffe)."""
        lvl = max(0.0, getattr(self, "_temp_level", 0.0) + delta)
        self._temp_level = lvl
        self.temperature = 3 if lvl >= 8 else 2 if lvl >= 6 else 1 if lvl >= 4 else 0

    def _drain(self, pct: float) -> None:
        self._battery_frac = getattr(self, "_battery_frac", float(self.battery_pct))
        self._battery_frac = max(0.0, self._battery_frac - pct)
        self.battery_pct = int(round(self._battery_frac))

    # ------------------------------------------------------------------ #
    # Construction des trames sortantes
    # ------------------------------------------------------------------ #
    def build_status_push(self) -> bytes:
        """Encode l'état courant dans une trame de statut (1D02)."""
        body = bytearray(38)
        body[0] = self.mode & 0xFF
        body[1] = self.camera_status & 0xFF
        struct.pack_into("<H", body, 5, min(self.record_time_s, 0xFFFF))
        struct.pack_into("<I", body, 15, self.remain_capacity_mb)
        struct.pack_into("<I", body, 23, self.remain_time_s)
        body[30] = self.temperature & 0xFF
        body[37] = self.battery_pct & 0xFF

        self._push_seq = (self._push_seq + 1) & 0xFFFF
        return p.build_frame(0x1D, 0x02, bytes(body),
                             seq=self._push_seq, cmd_type=p.FRAME_TYPE_COMMAND)

    def _build_response(self, cmd_set: int, cmd_id: int, seq: int,
                        ret_code: int = 0x00) -> bytes:
        """ACK simplifié : même CmdSet/CmdID, bit RESPONSE, code retour."""
        return p.build_frame(cmd_set, cmd_id, bytes([ret_code]),
                             seq=seq, cmd_type=p.FRAME_TYPE_RESPONSE)
