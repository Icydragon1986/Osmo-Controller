"""
Étape matériel n°7 — CONFIRMATION : connexion silencieuse (verify_mode=0).

Séquence minimale et propre :
  1. connexion BLE,
  2. requête de connexion verify_mode=0 (device_id contrôleur + MAC),
  3. abonnement statut 1D05,
  4. écoute 15 s -> compte les pushs 1D02.

Si les pushs arrivent SANS popup, l'appairage ne demande AUCUNE action de
l'utilisateur. C'est ce qu'on veut vérifier.

Usage : python hardware/clean_connect_test.py [adresse]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))

from bleak import BleakClient

from osmo_controller import protocol as p

DEFAULT_ADDRESS = "8C:58:23:2B:25:23"
FFF4 = "0000fff4-0000-1000-8000-00805f9b34fb"
FFF5 = "0000fff5-0000-1000-8000-00805f9b34fb"
DEV_CTRL = 0x11223344
MAC = b"AA:BB:CC:DD:EE"

n_push = {"v": 0}
conn_ok = {"v": False}


def on_notify(_char, data: bytearray):
    b = bytes(data)
    if b and b[0] == 0x55:
        return
    try:
        f = p.parse_frame(b)
    except Exception:  # noqa: BLE001
        return
    if (f.cmd_set, f.cmd_id) == (0x00, 0x19):
        info = p.parse_connection(f.payload)
        conn_ok["v"] = info.get("ret_code") == 0
        print(f"    connexion: {info}  -> {'OK' if conn_ok['v'] else 'refus'}")
    elif (f.cmd_set, f.cmd_id) == (0x1D, 0x02):
        n_push["v"] += 1
        if n_push["v"] <= 2 or n_push["v"] % 10 == 0:
            print(f"    push #{n_push['v']}: {p.parse_camera_status(f.payload)}")


async def main(address: str) -> None:
    async with BleakClient(address) as client:
        print(f"Connecté BLE : {client.is_connected}")
        await client.start_notify(FFF4, on_notify)

        req = p.build_connection_request(seq=1, device_id_u32=DEV_CTRL,
                                         verify_mode=0, mac_addr=MAC)
        print("Envoi connexion verify_mode=0…")
        await client.write_gatt_char(FFF5, req, response=False)
        await asyncio.sleep(1.5)

        print("Envoi abonnement statut 1D05…")
        await client.write_gatt_char(FFF5, p.build_status_subscription(seq=2), response=False)

        print("Écoute 15 s…\n")
        await asyncio.sleep(15)

        print("\n" + "=" * 50)
        print(f"  Connexion acceptée : {conn_ok['v']}")
        print(f"  Pushs de statut reçus : {n_push['v']}")
        if conn_ok["v"] and n_push["v"] > 0:
            print("  ✓ CONNEXION SILENCIEUSE SUFFIT (aucun popup) !")
        print("=" * 50)
        await client.stop_notify(FFF4)


if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    asyncio.run(main(address))
