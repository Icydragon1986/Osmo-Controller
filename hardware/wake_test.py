"""
Test — RÉVEIL À DISTANCE après mise en veille (hypothèse à vérifier).

La doc officielle DJI (docs/add_camera_sleep_feature_example.md du SDK)
documente une commande « Power Mode Switch » (CmdSet 0x00, CmdID 0x1A,
payload = 1 octet power_mode : 0 = normal, 3 = veille) pour mettre la caméra
EN veille. Elle ne documente PAS explicitement comment en sortir — l'hypothèse
testée ici est que renvoyer power_mode=0 via la même commande la réveille.

Contexte : Jonathan a constaté que la commande START (1D03) envoyée pendant
que la caméra est en veille ne démarre PAS l'enregistrement tout de suite,
mais que l'enregistrement débute dès qu'il réveille la caméra MANUELLEMENT
(bouton) — donc la commande semble mise en attente plutôt que perdue, et le
Bluetooth reste connecté pendant la veille.

Déroulé du test :
  1. connexion BLE + abonnement statut (1D05),
  2. commande START (1D03) — pour que la caméra ait quelque chose "en attente",
  3. commande VEILLE (0x00/0x1A, power_mode=3) — la caméra doit s'endormir,
  4. pause 5 s,
  5. commande RÉVEIL (0x00/0x1A, power_mode=0) — ÇA, c'est l'hypothèse testée,
  6. observe si les pushs de statut (1D02) reprennent et si l'enregistrement
     a bien démarré (voyant rouge, ou statut is_recording=True).

>>> REGARDE LA CAMÉRA à chaque étape : est-ce que l'écran s'éteint à l'étape 3,
    et est-ce qu'elle se rallume TOUTE SEULE (sans bouton) à l'étape 5 ? <<<

Usage : python hardware/wake_test.py [adresse]
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
DEV = p.DEVICE_IDS["osmo_action_5_pro"]

_last_status = {}


def on_notify(_char, data: bytearray):
    b = bytes(data)
    if not b or b[0] != p.SOF:
        return   # bruit DUML (0x55) : ignoré
    try:
        f = p.parse_frame(b)
    except Exception as e:  # noqa: BLE001
        print(f"    (non décodable : {e})")
        return
    if (f.cmd_set, f.cmd_id) == (0x1D, 0x02):
        st = p.parse_camera_status(f.payload)
        _last_status.update(st)
        print(f"    >>> STATUT reçu : is_recording={st['is_recording']}  batterie={st['battery_pct']}%")
    elif (f.cmd_set, f.cmd_id) == (0x1D, 0x03):
        print(f"    >>> réponse RECORD, ret_code={f.payload[0] if f.payload else '?'}")
    elif (f.cmd_set, f.cmd_id) == (0x00, 0x1A):
        print(f"    >>> réponse POWER MODE, ret_code={f.payload[0] if f.payload else '?'}")
    else:
        print(f"    >>> trame CmdSet/CmdID=0x{f.cmd_set:02X}{f.cmd_id:02X} payload={f.payload.hex(' ')}")


async def send(client, frame, label):
    print(f"\n>>> ENVOI {label} : {frame.hex(' ')}")
    await client.write_gatt_char(FFF5, frame, response=False)


async def main(address: str) -> None:
    async with BleakClient(address) as client:
        print(f"Connecté BLE : {client.is_connected}")
        await client.start_notify(FFF4, on_notify)

        await send(client, p.build_status_subscription(seq=1), "abonnement statut (1D05)")
        await asyncio.sleep(2)

        print("\n" + "=" * 60)
        print(">>> Envoi START (1D03) — la caméra a maintenant quelque chose 'en attente' <<<")
        print("=" * 60)
        await send(client, p.build_record_command(True, DEV, seq=2), "RECORD START (1D03)")
        await asyncio.sleep(2)

        print("\n" + "=" * 60)
        print(">>> VEILLE (0x00/0x1A, power_mode=3) — REGARDE si l'écran s'éteint <<<")
        print("=" * 60)
        await send(client, p.build_power_mode_command(sleep=True, seq=3), "SLEEP (0x00/0x1A)")
        await asyncio.sleep(5)

        print("\n" + "=" * 60)
        print(">>> RÉVEIL (0x00/0x1A, power_mode=0) — REGARDE si elle se rallume TOUTE SEULE <<<")
        print("=" * 60)
        await send(client, p.build_power_mode_command(sleep=False, seq=4), "WAKE (0x00/0x1A)")
        await asyncio.sleep(5)

        print("\n" + "=" * 60)
        print(">>> Dernier statut connu :", _last_status or "(aucun reçu)")
        print(">>> Est-ce que l'enregistrement a démarré (voyant rouge) ? <<<")
        print("=" * 60)

        print("\n>>> STOP (1D03) pour nettoyer, au cas où ça enregistre <<<")
        await send(client, p.build_record_command(False, DEV, seq=5), "RECORD STOP (1D03)")
        await asyncio.sleep(2)

        await client.stop_notify(FFF4)
        print("\nFin du test.")


if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    asyncio.run(main(address))
