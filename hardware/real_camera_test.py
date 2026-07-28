"""
Étape matériel n°8 — PILE COMPLÈTE sur vraie caméra.

Utilise CameraConnection + BleakTransport (exactement comme l'app) pour :
  - se connecter (handshake auto, sans popup),
  - recevoir le statut en direct (batterie, etc.),
  - démarrer puis arrêter un enregistrement à distance.

>>> Regarde la caméra : elle doit enregistrer ~4 s puis s'arrêter. <<<

Usage : python hardware/real_camera_test.py [adresse]
"""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")   # console Windows : accents + ✓
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))

from osmo_controller.connection import CameraConnection
from osmo_controller.bleak_transport import BleakTransport

DEFAULT_ADDRESS = "8C:58:23:2B:25:23"


async def main(address: str) -> None:
    tr = BleakTransport(address, name="BCC-3")
    conn = CameraConnection(
        tr, model="osmo_action_5_pro", name="BCC-3", reconnect_delay=2.0,
        on_state=lambda st: print(f"  [état] {st.value}"),
    )

    conn.start()
    print("Connexion…")
    await conn.wait_connected(timeout=15)
    print("✓ CONNECTÉ")

    await asyncio.sleep(3)
    print(f"\nStatut en direct : {conn.last_status}\n")

    print(">>> RECORD START (regarde la caméra) <<<")
    await conn.start_recording()
    await asyncio.sleep(4)
    print(f"Statut pendant enregistrement : {conn.last_status}\n")

    print(">>> RECORD STOP <<<")
    await conn.stop_recording()
    await asyncio.sleep(2)
    print(f"Statut après arrêt : {conn.last_status}\n")

    await conn.stop()
    print("Fin — déconnecté proprement.")


if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    asyncio.run(main(address))
