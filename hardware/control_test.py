"""
Étape matériel n°4 — CONTRÔLE.

Test décisif : est-ce que la caméra RÉAGIT à nos commandes ?
  1. connexion BLE + abonnement statut (1D05),
  2. commande ENREGISTRER (1D03 start)  -> la caméra doit démarrer,
  3. après 4 s, commande ARRÊTER (1D03 stop),
  4. journalise toutes les réponses/pushs (0xAA), ignore le bruit 0x55.

>>> REGARDE LA CAMÉRA : le voyant/point rouge d'enregistrement doit
    apparaître au START et disparaître au STOP. <<<

Usage : python hardware/control_test.py [adresse]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))

from bleak import BleakClient

from osmo_controller import protocol as p

DEFAULT_ADDRESS = "8C:58:23:2B:25:23"
FFF3 = "0000fff3-0000-1000-8000-00805f9b34fb"
FFF4 = "0000fff4-0000-1000-8000-00805f9b34fb"
FFF5 = "0000fff5-0000-1000-8000-00805f9b34fb"
DEV = p.DEVICE_IDS["osmo_action_5_pro"]   # 0xFF44


def on_notify(char, data: bytearray):
    b = bytes(data)
    if b and b[0] == 0x55:
        return                      # télémétrie DUML : ignorée
    chan = str(char.uuid).lower()[4:8]
    print(f"\n[REÇU/{chan}] {b.hex(' ')}")
    try:
        f = p.parse_frame(b)
    except Exception as e:  # noqa: BLE001
        print(f"    (non décodable : {e})")
        return
    print(f"    CmdSet/CmdID=0x{f.cmd_set:02X}{f.cmd_id:02X}  SEQ={f.seq}  "
          f"CRC16={'ok' if f.crc16_ok else 'BAD'} CRC32={'ok' if f.crc32_ok else 'BAD'}  "
          f"payload={f.payload.hex(' ')}")
    if (f.cmd_set, f.cmd_id) == (0x1D, 0x02):
        print(f"    >>> STATUT: {p.parse_camera_status(f.payload)}")
    elif (f.cmd_set, f.cmd_id) == (0x1D, 0x03):
        print(f"    >>> réponse ENREGISTREMENT, ret_code={f.payload[0] if f.payload else '?'}")


async def send(client, frame, label):
    print(f"\n>>> ENVOI {label} : {frame.hex(' ')}")
    await client.write_gatt_char(FFF5, frame, response=False)


async def main(address: str) -> None:
    async with BleakClient(address) as client:
        print(f"Connecté BLE : {client.is_connected}")
        await client.start_notify(FFF4, on_notify)
        try:
            await client.start_notify(FFF3, on_notify)
        except Exception:  # noqa: BLE001
            pass

        await send(client, p.build_status_subscription(seq=1), "abonnement statut (1D05)")
        await asyncio.sleep(2)

        print("\n" + "=" * 60)
        print(">>> REGARDE LA CAMÉRA : elle doit DÉMARRER l'enregistrement <<<")
        print("=" * 60)
        await send(client, p.build_record_command(True, DEV, seq=2), "RECORD START (1D03)")
        await asyncio.sleep(4)

        print("\n" + "=" * 60)
        print(">>> Elle doit maintenant ARRÊTER l'enregistrement <<<")
        print("=" * 60)
        await send(client, p.build_record_command(False, DEV, seq=3), "RECORD STOP (1D03)")
        await asyncio.sleep(3)

        await client.stop_notify(FFF4)
        print("\nFin du test.")


if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    asyncio.run(main(address))
