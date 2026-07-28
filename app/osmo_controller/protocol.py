"""
Moteur du protocole DJI R SDK pour Osmo Action (BLE).

Porté fidèlement depuis le code de référence officiel de DJI
(dji-sdk/Osmo-GPS-Controller-Demo). Tout est vérifié contre la trame
d'exemple officielle dans test_protocol.py.

Points NON-évidents portés depuis la source C de DJI :
  - CRC16 et CRC32 utilisent une valeur d'init custom 0x3AA3 (PAS 0xFFFF/0).
  - Aucun XOR final (finalize = identité).
  - Tout le paquet est en little-endian.

Couche BLE (depuis getting_started_guide.md) :
  - Service        : 0xFFF0
  - Notifications  : 0xFFF4  (caméra -> nous ; activer les notifications)
  - Écriture       : 0xFFF5  (nous -> caméra ; on envoie les commandes ici)
"""

from __future__ import annotations
import struct
from dataclasses import dataclass

# --------------------------------------------------------------------------
# Constantes BLE
# --------------------------------------------------------------------------
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000fff5-0000-1000-8000-00805f9b34fb"

# device_id par modèle (depuis protocol_data_segment.md).
# Encodage observé dans l'exemple officiel : la valeur 16 bits est placée dans
# les octets de poids fort du champ uint32, sérialisé little-endian.
# Ex. Action 4 (0xFF33) -> octets [00, 00, 33, FF].  À confirmer sur matériel.
DEVICE_IDS = {
    "osmo_action_4": 0xFF33,
    "osmo_action_5_pro": 0xFF44,
    "osmo_action_6": 0xFF55,
    "osmo_360": 0xFF66,
}


def encode_device_id(device_id_16: int) -> bytes:
    """0xFF44 -> b'\\x00\\x00\\x44\\xFF' (uint32 LE de (valeur << 16))."""
    return struct.pack("<I", (device_id_16 & 0xFFFF) << 16)


# --------------------------------------------------------------------------
# CRC — tables et constantes copiées telles quelles depuis le code DJI
# --------------------------------------------------------------------------
CRC_INIT = 0x3AA3  # identique pour CRC16 et CRC32 chez DJI

_CRC16_TABLE = [
    0x0000, 0xc0c1, 0xc181, 0x0140, 0xc301, 0x03c0, 0x0280, 0xc241,
    0xc601, 0x06c0, 0x0780, 0xc741, 0x0500, 0xc5c1, 0xc481, 0x0440,
    0xcc01, 0x0cc0, 0x0d80, 0xcd41, 0x0f00, 0xcfc1, 0xce81, 0x0e40,
    0x0a00, 0xcac1, 0xcb81, 0x0b40, 0xc901, 0x09c0, 0x0880, 0xc841,
    0xd801, 0x18c0, 0x1980, 0xd941, 0x1b00, 0xdbc1, 0xda81, 0x1a40,
    0x1e00, 0xdec1, 0xdf81, 0x1f40, 0xdd01, 0x1dc0, 0x1c80, 0xdc41,
    0x1400, 0xd4c1, 0xd581, 0x1540, 0xd701, 0x17c0, 0x1680, 0xd641,
    0xd201, 0x12c0, 0x1380, 0xd341, 0x1100, 0xd1c1, 0xd081, 0x1040,
    0xf001, 0x30c0, 0x3180, 0xf141, 0x3300, 0xf3c1, 0xf281, 0x3240,
    0x3600, 0xf6c1, 0xf781, 0x3740, 0xf501, 0x35c0, 0x3480, 0xf441,
    0x3c00, 0xfcc1, 0xfd81, 0x3d40, 0xff01, 0x3fc0, 0x3e80, 0xfe41,
    0xfa01, 0x3ac0, 0x3b80, 0xfb41, 0x3900, 0xf9c1, 0xf881, 0x3840,
    0x2800, 0xe8c1, 0xe981, 0x2940, 0xeb01, 0x2bc0, 0x2a80, 0xea41,
    0xee01, 0x2ec0, 0x2f80, 0xef41, 0x2d00, 0xedc1, 0xec81, 0x2c40,
    0xe401, 0x24c0, 0x2580, 0xe541, 0x2700, 0xe7c1, 0xe681, 0x2640,
    0x2200, 0xe2c1, 0xe381, 0x2340, 0xe101, 0x21c0, 0x2080, 0xe041,
    0xa001, 0x60c0, 0x6180, 0xa141, 0x6300, 0xa3c1, 0xa281, 0x6240,
    0x6600, 0xa6c1, 0xa781, 0x6740, 0xa501, 0x65c0, 0x6480, 0xa441,
    0x6c00, 0xacc1, 0xad81, 0x6d40, 0xaf01, 0x6fc0, 0x6e80, 0xae41,
    0xaa01, 0x6ac0, 0x6b80, 0xab41, 0x6900, 0xa9c1, 0xa881, 0x6840,
    0x7800, 0xb8c1, 0xb981, 0x7940, 0xbb01, 0x7bc0, 0x7a80, 0xba41,
    0xbe01, 0x7ec0, 0x7f80, 0xbf41, 0x7d00, 0xbdc1, 0xbc81, 0x7c40,
    0xb401, 0x74c0, 0x7580, 0xb541, 0x7700, 0xb7c1, 0xb681, 0x7640,
    0x7200, 0xb2c1, 0xb381, 0x7340, 0xb101, 0x71c0, 0x7080, 0xb041,
    0x5000, 0x90c1, 0x9181, 0x5140, 0x9301, 0x53c0, 0x5280, 0x9241,
    0x9601, 0x56c0, 0x5780, 0x9741, 0x5500, 0x95c1, 0x9481, 0x5440,
    0x9c01, 0x5cc0, 0x5d80, 0x9d41, 0x5f00, 0x9fc1, 0x9e81, 0x5e40,
    0x5a00, 0x9ac1, 0x9b81, 0x5b40, 0x9901, 0x59c0, 0x5880, 0x9841,
    0x8801, 0x48c0, 0x4980, 0x8941, 0x4b00, 0x8bc1, 0x8a81, 0x4a40,
    0x4e00, 0x8ec1, 0x8f81, 0x4f40, 0x8d01, 0x4dc0, 0x4c80, 0x8c41,
    0x4400, 0x84c1, 0x8581, 0x4540, 0x8701, 0x47c0, 0x4680, 0x8641,
    0x8201, 0x42c0, 0x4380, 0x8341, 0x4100, 0x81c1, 0x8081, 0x4040,
]

_CRC32_TABLE = [
    0x00000000, 0x77073096, 0xee0e612c, 0x990951ba, 0x076dc419, 0x706af48f, 0xe963a535, 0x9e6495a3,
    0x0edb8832, 0x79dcb8a4, 0xe0d5e91e, 0x97d2d988, 0x09b64c2b, 0x7eb17cbd, 0xe7b82d07, 0x90bf1d91,
    0x1db71064, 0x6ab020f2, 0xf3b97148, 0x84be41de, 0x1adad47d, 0x6ddde4eb, 0xf4d4b551, 0x83d385c7,
    0x136c9856, 0x646ba8c0, 0xfd62f97a, 0x8a65c9ec, 0x14015c4f, 0x63066cd9, 0xfa0f3d63, 0x8d080df5,
    0x3b6e20c8, 0x4c69105e, 0xd56041e4, 0xa2677172, 0x3c03e4d1, 0x4b04d447, 0xd20d85fd, 0xa50ab56b,
    0x35b5a8fa, 0x42b2986c, 0xdbbbc9d6, 0xacbcf940, 0x32d86ce3, 0x45df5c75, 0xdcd60dcf, 0xabd13d59,
    0x26d930ac, 0x51de003a, 0xc8d75180, 0xbfd06116, 0x21b4f4b5, 0x56b3c423, 0xcfba9599, 0xb8bda50f,
    0x2802b89e, 0x5f058808, 0xc60cd9b2, 0xb10be924, 0x2f6f7c87, 0x58684c11, 0xc1611dab, 0xb6662d3d,
    0x76dc4190, 0x01db7106, 0x98d220bc, 0xefd5102a, 0x71b18589, 0x06b6b51f, 0x9fbfe4a5, 0xe8b8d433,
    0x7807c9a2, 0x0f00f934, 0x9609a88e, 0xe10e9818, 0x7f6a0dbb, 0x086d3d2d, 0x91646c97, 0xe6635c01,
    0x6b6b51f4, 0x1c6c6162, 0x856530d8, 0xf262004e, 0x6c0695ed, 0x1b01a57b, 0x8208f4c1, 0xf50fc457,
    0x65b0d9c6, 0x12b7e950, 0x8bbeb8ea, 0xfcb9887c, 0x62dd1ddf, 0x15da2d49, 0x8cd37cf3, 0xfbd44c65,
    0x4db26158, 0x3ab551ce, 0xa3bc0074, 0xd4bb30e2, 0x4adfa541, 0x3dd895d7, 0xa4d1c46d, 0xd3d6f4fb,
    0x4369e96a, 0x346ed9fc, 0xad678846, 0xda60b8d0, 0x44042d73, 0x33031de5, 0xaa0a4c5f, 0xdd0d7cc9,
    0x5005713c, 0x270241aa, 0xbe0b1010, 0xc90c2086, 0x5768b525, 0x206f85b3, 0xb966d409, 0xce61e49f,
    0x5edef90e, 0x29d9c998, 0xb0d09822, 0xc7d7a8b4, 0x59b33d17, 0x2eb40d81, 0xb7bd5c3b, 0xc0ba6cad,
    0xedb88320, 0x9abfb3b6, 0x03b6e20c, 0x74b1d29a, 0xead54739, 0x9dd277af, 0x04db2615, 0x73dc1683,
    0xe3630b12, 0x94643b84, 0x0d6d6a3e, 0x7a6a5aa8, 0xe40ecf0b, 0x9309ff9d, 0x0a00ae27, 0x7d079eb1,
    0xf00f9344, 0x8708a3d2, 0x1e01f268, 0x6906c2fe, 0xf762575d, 0x806567cb, 0x196c3671, 0x6e6b06e7,
    0xfed41b76, 0x89d32be0, 0x10da7a5a, 0x67dd4acc, 0xf9b9df6f, 0x8ebeeff9, 0x17b7be43, 0x60b08ed5,
    0xd6d6a3e8, 0xa1d1937e, 0x38d8c2c4, 0x4fdff252, 0xd1bb67f1, 0xa6bc5767, 0x3fb506dd, 0x48b2364b,
    0xd80d2bda, 0xaf0a1b4c, 0x36034af6, 0x41047a60, 0xdf60efc3, 0xa867df55, 0x316e8eef, 0x4669be79,
    0xcb61b38c, 0xbc66831a, 0x256fd2a0, 0x5268e236, 0xcc0c7795, 0xbb0b4703, 0x220216b9, 0x5505262f,
    0xc5ba3bbe, 0xb2bd0b28, 0x2bb45a92, 0x5cb36a04, 0xc2d7ffa7, 0xb5d0cf31, 0x2cd99e8b, 0x5bdeae1d,
    0x9b64c2b0, 0xec63f226, 0x756aa39c, 0x026d930a, 0x9c0906a9, 0xeb0e363f, 0x72076785, 0x05005713,
    0x95bf4a82, 0xe2b87a14, 0x7bb12bae, 0x0cb61b38, 0x92d28e9b, 0xe5d5be0d, 0x7cdcefb7, 0x0bdbdf21,
    0x86d3d2d4, 0xf1d4e242, 0x68ddb3f8, 0x1fda836e, 0x81be16cd, 0xf6b9265b, 0x6fb077e1, 0x18b74777,
    0x88085ae6, 0xff0f6a70, 0x66063bca, 0x11010b5c, 0x8f659eff, 0xf862ae69, 0x616bffd3, 0x166ccf45,
    0xa00ae278, 0xd70dd2ee, 0x4e048354, 0x3903b3c2, 0xa7672661, 0xd06016f7, 0x4969474d, 0x3e6e77db,
    0xaed16a4a, 0xd9d65adc, 0x40df0b66, 0x37d83bf0, 0xa9bcae53, 0xdebb9ec5, 0x47b2cf7f, 0x30b5ffe9,
    0xbdbdf21c, 0xcabac28a, 0x53b39330, 0x24b4a3a6, 0xbad03605, 0xcdd70693, 0x54de5729, 0x23d967bf,
    0xb3667a2e, 0xc4614ab8, 0x5d681b02, 0x2a6f2b94, 0xb40bbe37, 0xc30c8ea1, 0x5a05df1b, 0x2d02ef8d,
]


def calculate_crc16(data: bytes) -> int:
    crc = CRC_INIT
    for b in data:
        crc = (_CRC16_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)) & 0xFFFF
    return crc & 0xFFFF


def calculate_crc32(data: bytes) -> int:
    crc = CRC_INIT
    for b in data:
        crc = (_CRC32_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)) & 0xFFFFFFFF
    return crc & 0xFFFFFFFF


# --------------------------------------------------------------------------
# Construction / lecture des trames
# --------------------------------------------------------------------------
SOF = 0xAA

# Bits du champ CmdType
CMD_TYPE_NEED_REPLY_OK = 0x01   # réponse souhaitée mais facultative
FRAME_TYPE_COMMAND = 0x00
FRAME_TYPE_RESPONSE = 0x20      # bit [5]


def build_frame(cmd_set: int, cmd_id: int, payload: bytes,
                seq: int, cmd_type: int = CMD_TYPE_NEED_REPLY_OK) -> bytes:
    """Assemble une trame DJI R SDK complète (avec les deux CRC)."""
    data = bytes([cmd_set, cmd_id]) + payload
    total_length = 12 + len(data) + 4          # en-tête + DATA + CRC32

    header = bytearray()
    header.append(SOF)                          # 0  : SOF
    header += struct.pack("<H", total_length & 0x03FF)  # 1-2: Ver(0)/Length, LE
    header.append(cmd_type & 0xFF)              # 3  : CmdType
    header.append(0x00)                         # 4  : ENC (pas de chiffrement)
    header += b"\x00\x00\x00"                   # 5-7: RES
    header += struct.pack("<H", seq & 0xFFFF)   # 8-9: SEQ, LE

    crc16 = calculate_crc16(bytes(header))      # CRC16 sur SOF..SEQ
    frame = bytes(header) + struct.pack("<H", crc16) + data
    crc32 = calculate_crc32(frame)              # CRC32 sur SOF..DATA
    frame += struct.pack("<I", crc32)
    return frame


@dataclass
class ParsedFrame:
    cmd_type: int
    seq: int
    cmd_set: int
    cmd_id: int
    payload: bytes
    crc16_ok: bool
    crc32_ok: bool


def parse_frame(frame: bytes) -> ParsedFrame:
    """Lit une trame reçue et vérifie ses deux CRC."""
    if len(frame) < 17 or frame[0] != SOF:
        raise ValueError("Trame invalide (SOF/longueur)")
    total_length = struct.unpack("<H", frame[1:3])[0] & 0x03FF
    if total_length != len(frame):
        raise ValueError(f"Longueur incohérente : {total_length} vs {len(frame)}")

    cmd_type = frame[3]
    seq = struct.unpack("<H", frame[8:10])[0]
    crc16_recv = struct.unpack("<H", frame[10:12])[0]
    crc16_ok = (crc16_recv == calculate_crc16(frame[0:10]))

    data = frame[12:-4]
    crc32_recv = struct.unpack("<I", frame[-4:])[0]
    crc32_ok = (crc32_recv == calculate_crc32(frame[0:-4]))

    return ParsedFrame(cmd_type, seq, data[0], data[1], data[2:], crc16_ok, crc32_ok)


# --------------------------------------------------------------------------
# Commandes de la Phase 1
# --------------------------------------------------------------------------
def build_record_command(start: bool, device_id_16: int, seq: int) -> bytes:
    """Recording Control (1D03). start=True -> enregistre, False -> arrête."""
    record_ctrl = 0x00 if start else 0x01
    payload = encode_device_id(device_id_16) + bytes([record_ctrl]) + b"\x00\x00\x00\x00"
    return build_frame(0x1D, 0x03, payload, seq)


def build_connection_request(seq: int, device_id_u32: int = 0xFF440000,
                             verify_mode: int = 1, verify_data: int = 0x0000,
                             mac_addr: bytes = b"") -> bytes:
    """Connection request (0x00/0x19) — déclenche l'appairage.

    verify_mode : 0 = sans vérif, 1 = la caméra affiche un code (popup à
    confirmer sur la caméra), 2 = résultat (verify_data 0 = autorise).
    Structure de payload (33 o) tirée de protocol_data_segment.md.
    """
    payload = bytearray(33)
    struct.pack_into("<I", payload, 0, device_id_u32 & 0xFFFFFFFF)   # device_id émetteur
    m = (mac_addr or b"")[:16]
    payload[4] = len(m)                                              # mac_addr_len
    payload[5:5 + len(m)] = m                                        # mac_addr[16]
    # 21..24 fw_version = 0 ; 25 conidx = 0
    payload[26] = verify_mode & 0xFF
    struct.pack_into("<H", payload, 27, verify_data & 0xFFFF)
    return build_frame(0x00, 0x19, bytes(payload), seq=seq)


def build_connection_response(seq: int, device_id_u32: int = 0xFF440000,
                              ret_code: int = 0x00) -> bytes:
    """Réponse (0x00/0x19) à la requête verify_mode=2 de la caméra (ret_code 0 = OK)."""
    payload = bytearray(9)
    struct.pack_into("<I", payload, 0, device_id_u32 & 0xFFFFFFFF)
    payload[4] = ret_code & 0xFF
    return build_frame(0x00, 0x19, bytes(payload), seq=seq, cmd_type=FRAME_TYPE_RESPONSE)


def parse_connection(payload: bytes) -> dict:
    """Décode un payload de connexion (0x00/0x19) reçu de la caméra."""
    out = {}
    if len(payload) >= 4:
        out["device_id"] = struct.unpack_from("<I", payload, 0)[0]
    if len(payload) >= 5:
        out["ret_code"] = payload[4]           # présent sur la réponse courte (9 o)
    if len(payload) >= 27:
        out["verify_mode"] = payload[26]       # présent sur la trame longue (33 o)
    if len(payload) >= 29:
        out["verify_data"] = struct.unpack_from("<H", payload, 27)[0]
    return out


def build_status_subscription(seq: int, push_mode: int = 3, push_freq: int = 20) -> bytes:
    """Camera Status Subscription (1D05). push_mode 3 = périodique + sur changement.
    push_freq fixé à 20 (0.1 Hz) => 2 Hz, seule valeur acceptée."""
    payload = bytes([push_mode, push_freq]) + b"\x00\x00\x00\x00"
    return build_frame(0x1D, 0x05, payload, seq)


# Statut caméra (1D02) — offsets dans le payload (après CmdSet/CmdID),
# tirés de protocol_data_segment.md.
_CAMERA_MODE = {0x00: "Slow Motion", 0x01: "Vidéo", 0x02: "Timelapse",
                0x05: "Photo", 0x0A: "Hyperlapse", 0x1A: "Live Streaming",
                0x28: "SuperNight", 0x34: "Subject Tracking"}
_TEMP = {0: "normale", 1: "élevée (ok)", 2: "trop chaude (stop)", 3: "surchauffe"}


class FrameReassembler:
    """Ré-assemble des trames DJI R SDK reçues en un ou plusieurs paquets BLE.

    Sur Windows, chaque notification 0xFFF4 contient une trame complète (MTU
    suffisant), mais rien ne le garantit sur une autre plateforme (ex. macOS) :
    la trame peut arriver fragmentée sur plusieurs notifications. Le champ
    Length (octets 1-2) permet de savoir combien d'octets attendre.
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        """Ajoute des octets reçus ; renvoie les trames complètes disponibles."""
        self._buf += chunk
        frames = []
        while self._buf:
            if self._buf[0] != SOF:
                self._buf.clear()  # bruit (ex. télémétrie DUML 0x55) : resynchronise
                break
            if len(self._buf) < 3:
                break  # pas encore assez d'octets pour lire la longueur
            total_length = struct.unpack_from("<H", self._buf, 1)[0] & 0x03FF
            if total_length < 17:
                self._buf.clear()  # longueur incohérente : resynchronise
                break
            if len(self._buf) < total_length:
                break  # trame incomplète, attend la suite
            frames.append(bytes(self._buf[:total_length]))
            del self._buf[:total_length]
        return frames


def parse_camera_status(payload: bytes) -> dict:
    """Décode le push de statut (1D02) en un dict lisible.
    Lecture défensive : ne lit un champ que s'il tient dans le payload."""
    def u8(o):  return payload[o] if len(payload) > o else None
    def u16(o): return struct.unpack_from("<H", payload, o)[0] if len(payload) >= o + 2 else None
    def u32(o): return struct.unpack_from("<I", payload, o)[0] if len(payload) >= o + 4 else None

    camera_status = u8(1)
    return {
        "mode": _CAMERA_MODE.get(u8(0), f"0x{u8(0):02X}" if u8(0) is not None else None),
        "camera_status": camera_status,
        # 0x03 = photo OU enregistrement ; 0x05 = pré-enregistrement
        "is_recording": camera_status in (0x03, 0x05),
        "record_time_s": u16(5),
        "remain_capacity_mb": u32(15),
        "remain_time_s": u32(23),
        "temperature": _TEMP.get(u8(30), None),
        "battery_pct": u8(37),
    }
