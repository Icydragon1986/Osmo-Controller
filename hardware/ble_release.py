"""
Utilitaire — LIBÉRER une caméra « coincée » en Bluetooth.

Après un arrêt brutal (kill), Windows peut garder la connexion BLE ouverte :
la caméra se croit connectée et cesse d'annoncer. Ce script se connecte
(Windows peut réutiliser le lien existant) puis se déconnecte PROPREMENT,
ce qui force le relâchement.

Usage : python hardware/ble_release.py [adresse]
"""
import asyncio
import sys

from bleak import BleakClient

DEFAULT_ADDRESS = "8C:58:23:2B:25:23"


async def main(address: str) -> None:
    print(f"Tentative de connexion à {address} pour la relâcher…")
    try:
        client = BleakClient(address)
        await client.connect()
        print(f"  connecté : {client.is_connected}")
        await asyncio.sleep(1)
        await client.disconnect()
        print("  déconnecté proprement ✓  — la caméra devrait se libérer.")
    except Exception as e:  # noqa: BLE001
        print(f"  échec : {type(e).__name__}: {e}")
        print("  -> Passe au plan B : coupe/rallume le Bluetooth du PC,")
        print("     et éteins complètement la caméra (bouton maintenu).")


if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    asyncio.run(main(address))
