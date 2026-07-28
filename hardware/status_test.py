"""
Étape matériel n°5 — PUSHS DE STATUT (1D02).

L'abonnement 1D05 est accepté mais aucun push 1D02 n'arrive. On essaie
plusieurs réglages pour trouver ce qui déclenche les pushs :
  - push_mode 1 (single)   : doit renvoyer UN push tout de suite,
  - push_mode 2 (periodic) : doit renvoyer un flux,
  - push_mode 3 + freq 10.

On journalise toute trame 0xAA (surtout les 1D02), on ignore le bruit 0x55.

Usage : python hardware/status_test.py [adresse]
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

counts = {"1d02": 0, "other": 0, "raw55": 0}


def on_notify(char, data: bytearray):
    b = bytes(data)
    if b and b[0] == 0x55:
        counts["raw55"] += 1
        return
    chan = str(char.uuid).lower()[4:8]
    print(f"[{chan}] {b.hex(' ')}")
    try:
        f = p.parse_frame(b)
    except Exception as e:  # noqa: BLE001
        print(f"    (non décodable : {e})")
        return
    if (f.cmd_set, f.cmd_id) == (0x1D, 0x02):
        counts["1d02"] += 1
        print(f"    >>> STATUT 1D02: {p.parse_camera_status(f.payload)}")
    else:
        counts["other"] += 1
        print(f"    CmdSet/CmdID=0x{f.cmd_set:02X}{f.cmd_id:02X}  ret={f.payload[:1].hex()}")


async def try_sub(client, seq, push_mode, push_freq, wait):
    before = counts["1d02"]
    frame = p.build_status_subscription(seq, push_mode=push_mode, push_freq=push_freq)
    print(f"\n=== abonnement push_mode={push_mode} push_freq={push_freq} ===")
    print(f"    envoi: {frame.hex(' ')}")
    await client.write_gatt_char(FFF5, frame, response=False)
    await asyncio.sleep(wait)
    got = counts["1d02"] - before
    print(f"    -> {got} push(s) 1D02 reçu(s) en {wait}s")


async def main(address: str) -> None:
    async with BleakClient(address) as client:
        print(f"Connecté BLE : {client.is_connected}")
        await client.start_notify(FFF4, on_notify)
        try:
            await client.start_notify(FFF3, on_notify)
        except Exception:  # noqa: BLE001
            pass

        await try_sub(client, seq=1, push_mode=1, push_freq=20, wait=3)   # single
        await try_sub(client, seq=2, push_mode=2, push_freq=20, wait=4)   # periodic
        await try_sub(client, seq=3, push_mode=3, push_freq=10, wait=4)   # periodic+event

        print(f"\nRésumé : 1D02={counts['1d02']}  autres={counts['other']}  "
              f"télémétrie0x55={counts['raw55']}")
        await client.stop_notify(FFF4)


if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    asyncio.run(main(address))
