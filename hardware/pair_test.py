"""
Étape matériel n°3 — APPAIRAGE.

Se connecte à la caméra, s'abonne aux notifications (0xFFF4), envoie la requête
de connexion (verify_mode=1) et journalise TOUT ce que la caméra renvoie.

>>> REGARDE L'ÉCRAN DE LA CAMÉRA : un popup de code de vérification doit
    apparaître. Confirme-le SUR LA CAMÉRA. <<<

Quand la caméra renvoie verify_mode=2 (utilisateur a confirmé), le script
répond automatiquement ret_code=0. Ensuite il tente un abonnement au statut
(1D05) pour voir si des pushs (1D02) arrivent.

Usage :
    python hardware/pair_test.py [adresse] [device_id_hex]
    ex: python hardware/pair_test.py 8C:58:23:2B:25:23 FF440000
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))

from bleak import BleakClient

from osmo_controller import protocol as p

DEFAULT_ADDRESS = "8C:58:23:2B:25:23"
FFF3 = "0000fff3-0000-1000-8000-00805f9b34fb"   # canal secondaire (notify)
FFF4 = "0000fff4-0000-1000-8000-00805f9b34fb"   # notifications
FFF5 = "0000fff5-0000-1000-8000-00805f9b34fb"   # écriture


async def main(address: str, device_id: int) -> None:
    loop = asyncio.get_running_loop()
    connected_ok = asyncio.Event()
    noise = {"count": 0}   # compteur de télémétrie 0x55 (bruit), pour ne pas spammer

    async with BleakClient(address) as client:
        print(f"Connecté BLE : {client.is_connected}")

        def on_notify(char, data: bytearray):
            b = bytes(data)
            chan = str(char.uuid).lower()[4:8]
            # Bruit : télémétrie DUML 0x55 envoyée en continu -> on compte seulement.
            if b and b[0] == 0x55:
                noise["count"] += 1
                if noise["count"] % 50 == 0:
                    print(f"    … ({noise['count']} trames télémétrie 0x55 ignorées)")
                return

            print(f"\n[REÇU/{chan}] {len(b)} o : {b.hex(' ')}")
            try:
                f = p.parse_frame(b)
            except Exception as e:  # noqa: BLE001
                print(f"    (non décodable : {e})")
                return
            print(f"    CmdSet/CmdID=0x{f.cmd_set:02X}{f.cmd_id:02X}  SEQ={f.seq}  "
                  f"CRC16={'ok' if f.crc16_ok else 'BAD'} CRC32={'ok' if f.crc32_ok else 'BAD'}")

            if (f.cmd_set, f.cmd_id) == (0x00, 0x19):
                info = p.parse_connection(f.payload)
                print(f"    connexion: {info}")
                if info.get("verify_mode") == 2:
                    approved = info.get("verify_data", 0) == 0
                    print(f"    >>> la caméra {'AUTORISE' if approved else 'REFUSE'} la connexion")
                    if approved:
                        resp = p.build_connection_response(f.seq, device_id, ret_code=0)
                        print(f"    -> réponse ret_code=0 : {resp.hex(' ')}")
                        loop.create_task(client.write_gatt_char(FFF5, resp, response=False))
                        connected_ok.set()
            elif (f.cmd_set, f.cmd_id) == (0x1D, 0x02):
                print(f"    statut: {p.parse_camera_status(f.payload)}")

        # On écoute les DEUX canaux : la réponse d'appairage peut arriver sur 0xFFF3.
        await client.start_notify(FFF4, on_notify)
        try:
            await client.start_notify(FFF3, on_notify)
            print("Abonné aux notifications 0xFFF4 + 0xFFF3.\n")
        except Exception as e:  # noqa: BLE001
            print(f"Abonné à 0xFFF4 (0xFFF3 indispo : {e}).\n")

        req = p.build_connection_request(seq=1, device_id_u32=device_id, verify_mode=1)
        print(f"Envoi requête de connexion (verify_mode=1) : {req.hex(' ')}")
        await client.write_gatt_char(FFF5, req, response=False)

        print("\n" + "=" * 60)
        print(">>> REGARDE LA CAMÉRA et CONFIRME le popup de code (30 s) <<<")
        print("=" * 60)
        try:
            await asyncio.wait_for(connected_ok.wait(), timeout=30)
            print("\n✓ Connexion approuvée. Test d'abonnement au statut…")
        except asyncio.TimeoutError:
            print("\n(pas de confirmation reçue — voir ce qui est arrivé ci-dessus)")

        sub = p.build_status_subscription(seq=2)
        print(f"Envoi abonnement statut (1D05) : {sub.hex(' ')}")
        await client.write_gatt_char(FFF5, sub, response=False)
        await asyncio.sleep(5)   # écoute les pushs éventuels

        await client.stop_notify(FFF4)
        print("\nFin du test.")


if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    device_id = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0xFF440000
    asyncio.run(main(address, device_id))
