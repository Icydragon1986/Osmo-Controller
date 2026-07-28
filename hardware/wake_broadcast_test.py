"""
Test — RÉVEIL PAR DIFFUSION BLE (2e hypothèse, différente de wake_test.py).

`hardware/wake_test.py` a montré que renvoyer power_mode=0 sur la connexion
existante NE réveille PAS la caméra. La doc officielle DJI (Q&A.md +
"Camera Power Mode Settings (001A)") décrit un mécanisme différent : le PC
doit DIFFUSER (broadcast) un paquet BLE spécial "WKP<MAC inversée>" pendant
~2 secondes — la caméra le capte même en veille — puis on doit RECONNECTER
(la connexion se coupe pendant la veille).

Conditions à respecter (documentées par DJI) :
  - s'être déjà connecté à CETTE caméra récemment (fais tourner
    control_test.py ou l'appli une fois avant, si ce n'est pas déjà fait) ;
  - la caméra ne doit pas dormir depuis plus de 30 minutes.

Déroulé :
  1. connexion BLE normale, abonnement statut, commande START (en attente),
  2. déconnexion volontaire,
  3. mets la caméra en veille TOI-MÊME (bouton, ou attends qu'elle s'endorme),
  4. appuie sur Entrée dans ce terminal quand elle est en veille,
  5. diffusion du paquet de réveil pendant 2 s,
  6. tentative de reconnexion (plusieurs essais, quelques secondes chacun),
  7. si reconnecté : observe si l'enregistrement (envoyé à l'étape 1) a démarré.

>>> REGARDE LA CAMÉRA à l'étape 6-7 : se rallume-t-elle TOUTE SEULE ? <<<

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


async def send(client, frame, label):
    print(f"\n>>> ENVOI {label} : {frame.hex(' ')}")
    await client.write_gatt_char(FFF5, frame, response=False)


async def try_reconnect(address: str, attempts: int = 5, timeout: float = 5.0):
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
    print(">>> Déconnecté volontairement. Mets la caméra en veille maintenant")
    print(">>> (bouton, ou attends son délai d'extinction d'écran). <<<")
    print("=" * 60)
    input("Appuie sur Entrée une fois la caméra bien en veille (écran éteint)... ")

    print("\n" + "=" * 60)
    print(">>> Diffusion du paquet de réveil pendant 2 s (WKP + MAC inversée) <<<")
    print("=" * 60)
    await wake_broadcast.broadcast_wake(address, duration_s=2.0)
    print("Diffusion terminée.")

    print("\nÉtape finale : tentative de reconnexion…")
    client = await try_reconnect(address)
    if client is None:
        print("\n>>> ÉCHEC : impossible de se reconnecter. La caméra n'a probablement pas été réveillée. <<<")
        return

    print(">>> Reconnecté ! REGARDE LA CAMÉRA : est-elle réveillée toute seule ? <<<")
    await client.start_notify(FFF4, on_notify)
    await send(client, p.build_status_subscription(seq=3), "abonnement statut (1D05)")
    await asyncio.sleep(3)
    print("\n>>> Dernier statut connu :", _last_status or "(aucun reçu)")
    print(">>> is_recording devrait être True si le START de l'étape 1 a bien pris effet <<<")

    print("\n>>> STOP (1D03) pour nettoyer, au cas où ça enregistre <<<")
    await send(client, p.build_record_command(False, DEV, seq=4), "RECORD STOP (1D03)")
    await asyncio.sleep(2)
    await client.disconnect()
    print("\nFin du test.")


if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    asyncio.run(main(address))
