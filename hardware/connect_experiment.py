"""
Étape matériel n°6 — DÉBLOQUER LES PUSHS via l'appairage.

Hypothèse : les pushs 1D02 exigent une vraie « connexion » (0x00/0x19).
On essaie, dans l'ordre :
  Phase 0 : on écoute 4 s sans rien envoyer (au cas où la caméra initie).
  Phase 1 : connexion verify_mode=0 (silencieuse) + device_id contrôleur + MAC.
            puis abonnement 1D05 -> compte les pushs.
  Phase 2 : si toujours rien, connexion verify_mode=1 -> POPUP à confirmer
            sur la caméra ; on répond auto au verify_mode=2 ; re-abonnement.

>>> En Phase 2, REGARDE LA CAMÉRA et confirme le popup. <<<

Usage : python hardware/connect_experiment.py [adresse]
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

DEV_CTRL = 0x11223344              # identifiant contrôleur (arbitraire, non nul)
MAC = b"AA:BB:CC:DD:EE"            # fausse adresse MAC (14 o)

counts = {"1d02": 0}


async def run():
    client = BleakClient(DEFAULT_ADDRESS)
    await client.connect()
    print(f"Connecté BLE : {client.is_connected}")
    loop = asyncio.get_running_loop()

    def on_notify(char, data: bytearray):
        b = bytes(data)
        if b and b[0] == 0x55:
            return
        chan = str(char.uuid).lower()[4:8]
        print(f"[{chan}] {b.hex(' ')}")
        try:
            f = p.parse_frame(b)
        except Exception as e:  # noqa: BLE001
            print(f"    (non décodable : {e})")
            return
        tag = f"0x{f.cmd_set:02X}{f.cmd_id:02X}"
        if (f.cmd_set, f.cmd_id) == (0x00, 0x19):
            info = p.parse_connection(f.payload)
            print(f"    CONNEXION {tag}: {info}")
            if info.get("verify_mode") == 2:
                approved = info.get("verify_data", 0) == 0
                print(f"    >>> caméra {'AUTORISE' if approved else 'REFUSE'}")
                resp = p.build_connection_response(f.seq, DEV_CTRL, ret_code=0)
                loop.create_task(client.write_gatt_char(FFF5, resp, response=False))
        elif (f.cmd_set, f.cmd_id) == (0x1D, 0x02):
            counts["1d02"] += 1
            print(f"    >>> STATUT: {p.parse_camera_status(f.payload)}")
        else:
            print(f"    {tag}  ret={f.payload[:1].hex()}")

    await client.start_notify(FFF4, on_notify)
    try:
        await client.start_notify(FFF3, on_notify)
    except Exception:  # noqa: BLE001
        pass

    async def sub_and_count(seq, wait=4):
        before = counts["1d02"]
        await client.write_gatt_char(FFF5, p.build_status_subscription(seq), response=False)
        await asyncio.sleep(wait)
        n = counts["1d02"] - before
        print(f"    -> {n} push(s) 1D02")
        return n

    print("\n--- Phase 0 : écoute 4 s (caméra initie ?) ---")
    await asyncio.sleep(4)

    print("\n--- Phase 1 : connexion verify_mode=0 (silencieuse) ---")
    req0 = p.build_connection_request(seq=10, device_id_u32=DEV_CTRL,
                                      verify_mode=0, mac_addr=MAC)
    print(f"    envoi: {req0.hex(' ')}")
    await client.write_gatt_char(FFF5, req0, response=False)
    await asyncio.sleep(3)
    if await sub_and_count(11) > 0:
        print("\n✓ PUSHS DÉBLOQUÉS avec verify_mode=0 !")
        await client.disconnect()
        return

    print("\n--- Phase 2 : connexion verify_mode=1 (POPUP) ---")
    print("=" * 60)
    print(">>> REGARDE LA CAMÉRA et CONFIRME le popup (25 s) <<<")
    print("=" * 60)
    req1 = p.build_connection_request(seq=12, device_id_u32=DEV_CTRL,
                                      verify_mode=1, mac_addr=MAC)
    print(f"    envoi: {req1.hex(' ')}")
    await client.write_gatt_char(FFF5, req1, response=False)
    await asyncio.sleep(25)

    print("\n--- Ré-abonnement après tentative d'appairage ---")
    await sub_and_count(13, wait=5)

    print(f"\nRésumé final : {counts['1d02']} push(s) 1D02 au total")
    await client.disconnect()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        DEFAULT_ADDRESS = sys.argv[1]
    asyncio.run(run())
