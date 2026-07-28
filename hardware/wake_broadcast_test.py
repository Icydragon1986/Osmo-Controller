"""
Test — RÉVEIL PAR DIFFUSION BLE, cycle 100% logiciel (v2).

`wake_test.py` a montré que renvoyer power_mode=0 sur la connexion existante
ne réveille pas la caméra. Le 1er essai de `wake_broadcast_test.py` (mise en
veille MANUELLE par Jonathan, puis diffusion) n'a pas non plus fonctionné —
mais introduisait une variable : la doc DJI documente peut-être un cycle
logiciel complet (mise en veille PAR LA COMMANDE 0x00/0x1A power_mode=3, PUIS
réveil par diffusion) plutôt qu'un réveil universel depuis n'importe quelle
veille (bouton, délai d'inactivité...). Cette version teste EXACTEMENT ce
cycle logiciel, sans jamais toucher la caméra à la main, pour isoler la
variable.

Déroulé :
  1. connexion BLE, abonnement statut, commande START (mise en attente),
  2. commande VEILLE LOGICIELLE (0x00/0x1A, power_mode=3),
  3. déconnexion (le lien BLE tombe normalement pendant la veille),
  4. pause de quelques secondes,
  5. diffusion du paquet de réveil (WKP + MAC inversée) pendant 2 s,
  6. tentative de reconnexion (plusieurs essais),
  7. si reconnecté : le START de l'étape 1 a-t-il pris effet ?

>>> REGARDE LA CAMÉRA à chaque étape : éteinte à l'étape 2-3, rallumée TOUTE
    SEULE à l'étape 6 ? <<<

Usage : python hardware/wake_broadcast_test.py [adresse]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))

from bleak import BleakClient

from osmo_controller import protocol as p
from osmo_controller import wake_broadcast

DEFAULT_ADDRESS = "8C:58:23:2B:25:23"
FFF4 = "0000fff4-0000-1000-8000-00805f9b34fb"
FFF5 = "0000fff5-0000-1000-8000-00805f9b34fb"
DEV = p.DEVICE_IDS["osmo_action_5_pro"]

_last_status = {}


def on_notify(_char, data: bytearray):
    b = bytes(data)
    if not b or b[0] != p.SOF:
        return
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


async def send(client, frame, label):
    print(f"\n>>> ENVOI {label} : {frame.hex(' ')}")
    await client.write_gatt_char(FFF5, frame, response=False)


async def try_reconnect(address: str, attempts: int = 6, timeout: float = 5.0):
    for i in range(1, attempts + 1):
        print(f"  tentative de reconnexion {i}/{attempts}…")
        try:
            client = BleakClient(address, timeout=timeout)
            await client.connect()
            if client.is_connected:
                return client
        except Exception as e:  # noqa: BLE001
            print(f"    échec : {type(e).__name__}: {e}")
        await asyncio.sleep(2)
    return None


async def main(address: str) -> None:
    print("Étape 1 : connexion + abonnement statut + START (mis en attente)")
    async with BleakClient(address) as client:
        print(f"Connecté BLE : {client.is_connected}")
        await client.start_notify(FFF4, on_notify)
        await send(client, p.build_status_subscription(seq=1), "abonnement statut (1D05)")
        await asyncio.sleep(1)
        await send(client, p.build_record_command(True, DEV, seq=2), "RECORD START (1D03)")
        await asyncio.sleep(1)

        print("\n" + "=" * 60)
        print(">>> VEILLE LOGICIELLE (0x00/0x1A, power_mode=3) — REGARDE l'écran <<<")
        print("=" * 60)
        await send(client, p.build_power_mode_command(sleep=True, seq=3), "SLEEP (0x00/0x1A)")
        await asyncio.sleep(3)
    print("Déconnecté (context manager) — le lien BLE devrait de toute façon tomber pendant la veille.")

    print("\nPause de 3 s avant la diffusion…")
    await asyncio.sleep(3)

    print("\n" + "=" * 60)
    print(">>> Diffusion du paquet de réveil pendant 2 s (WKP + MAC inversée) <<<")
    print("=" * 60)
    await wake_broadcast.broadcast_wake(address, duration_s=2.0)
    print("Diffusion terminée.")

    print("\nÉtape finale : tentative de reconnexion…")
    client = await try_reconnect(address)
    if client is None:
        print("\n>>> ÉCHEC : impossible de se reconnecter. La caméra n'a probablement pas été réveillée. <<<")
        print(">>> Cette variante (veille logicielle + réveil par diffusion) ne fonctionne pas non plus. <<<")
        return

    print(">>> Reconnecté ! REGARDE LA CAMÉRA : est-elle réveillée toute seule ? <<<")
    await client.start_notify(FFF4, on_notify)
    await send(client, p.build_status_subscription(seq=4), "abonnement statut (1D05)")
    await asyncio.sleep(3)
    print("\n>>> Dernier statut connu :", _last_status or "(aucun reçu)")
    print(">>> is_recording devrait être True si le START de l'étape 1 a bien pris effet <<<")

    print("\n>>> STOP (1D03) pour nettoyer, au cas où ça enregistre <<<")
    await send(client, p.build_record_command(False, DEV, seq=5), "RECORD STOP (1D03)")
    await asyncio.sleep(2)
    await client.disconnect()
    print("\nFin du test.")


if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    asyncio.run(main(address))
