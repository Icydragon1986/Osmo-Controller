"""
Étape matériel n°2 — CONNEXION + INSPECTION.

Se connecte à la caméra et liste tous ses services/caractéristiques BLE avec
leurs propriétés (read/write/notify). Vérifie la présence des canaux de notre
protocole : service 0xFFF0, notifications 0xFFF4, écriture 0xFFF5.
Lit aussi le niveau de batterie standard (0x2A19) comme test de bon sens.

N'ENVOIE aucune commande DJI : il ne fait qu'explorer et lire. Sans risque.

Usage :
    python hardware/inspect_gatt.py                     # adresse par défaut
    python hardware/inspect_gatt.py 8C:58:23:2B:25:23   # adresse explicite
"""
import asyncio
import sys

from bleak import BleakClient

DEFAULT_ADDRESS = "8C:58:23:2B:25:23"   # "BCC-3", trouvée au scan

WANT = {
    "0000fff0": "service DJI R SDK",
    "0000fff4": "notifications (caméra -> nous)",
    "0000fff5": "écriture (nous -> caméra)",
}


def short_uuid(u: str) -> str:
    return str(u).lower()[:8]


async def main(address: str) -> None:
    print(f"Connexion à {address}…")
    found = {}

    def on_disconnect(_):
        print("  (déconnecté)")

    try:
        async with BleakClient(address, disconnected_callback=on_disconnect) as client:
            print(f"Connecté : {client.is_connected}\n")

            for service in client.services:
                print(f"Service {service.uuid}")
                for ch in service.characteristics:
                    props = ",".join(ch.properties)
                    print(f"    char {ch.uuid}  [{props}]")
                    s = short_uuid(ch.uuid)
                    if s in WANT:
                        found[s] = ch.properties
                    su = short_uuid(service.uuid)
                    if su in WANT:
                        found.setdefault(su, "présent")

            print("\n" + "=" * 60)
            print("VÉRIFICATION DES CANAUX DE NOTRE PROTOCOLE :")
            for key, desc in WANT.items():
                mark = "OK  " if key in found else "MANQUE"
                extra = f"  [{found[key]}]" if isinstance(found.get(key), list) else ""
                print(f"  [{mark}] 0x{key[4:].upper()}  {desc}{extra}")
            print("=" * 60)

            # Test de bon sens : lire la batterie standard (0x2A19).
            try:
                batt = await client.read_gatt_char("00002a19-0000-1000-8000-00805f9b34fb")
                print(f"\nBatterie (0x2A19) : {batt[0]} %")
            except Exception as e:  # noqa: BLE001
                print(f"\nLecture batterie standard indisponible : {e}")

    except Exception as e:  # noqa: BLE001
        print(f"\nÉCHEC de connexion : {type(e).__name__}: {e}")
        print("Pistes : la caméra demande peut-être un appairage (code de")
        print("vérification à l'écran), ou elle est encore connectée à Mimo.")
        print("Dis-moi le message exact et on avance.")


if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADDRESS
    asyncio.run(main(address))
