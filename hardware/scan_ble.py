"""
Étape matériel n°1 — DÉCOUVERTE.

Scanne les appareils Bluetooth LE autour et affiche leur nom, adresse, force
du signal (RSSI) et les services annoncés. Repère ce qui ressemble à une
caméra DJI/Osmo et le service 0xFFF0 de notre protocole.

Ne se connecte à rien, n'envoie aucune commande : lecture seule, sans risque.

Usage :
    python hardware/scan_ble.py            # scan de 10 s
    python hardware/scan_ble.py 20         # scan de 20 s

Prépare la caméra AVANT de lancer :
  - allumée,
  - Bluetooth activé,
  - PAS déjà connectée à l'app DJI Mimo sur le téléphone (sinon elle
    n'accepte pas une 2e connexion et peut cesser d'annoncer).
"""
import asyncio
import sys

from bleak import BleakScanner

# Indices qu'un appareil est probablement notre caméra.
_NAME_HINTS = ("osmo", "dji", "action", "oa5", "oa 5")
_SERVICE_HINT = "fff0"   # service BLE du DJI R SDK


def looks_like_camera(name: str, service_uuids) -> bool:
    n = (name or "").lower()
    if any(h in n for h in _NAME_HINTS):
        return True
    return any(_SERVICE_HINT in str(u).lower() for u in (service_uuids or []))


async def main(timeout: float) -> None:
    print(f"Scan BLE pendant {timeout:.0f} s… (Ctrl+C pour arrêter)\n")
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)

    if not devices:
        print("Aucun appareil BLE détecté.")
        print("Vérifie : caméra allumée, Bluetooth activé, pas connectée à Mimo,")
        print("et Bluetooth activé sur le PC.")
        return

    # Trie par signal décroissant (le plus proche en premier).
    items = sorted(
        devices.values(),
        key=lambda t: (t[1].rssi if t[1].rssi is not None else -999),
        reverse=True,
    )

    candidates = []
    print(f"{len(items)} appareil(s) détecté(s) :\n")
    for dev, adv in items:
        name = dev.name or adv.local_name or "(sans nom)"
        rssi = adv.rssi
        is_cam = looks_like_camera(name, adv.service_uuids)
        mark = "  <-- CANDIDAT CAMÉRA" if is_cam else ""
        print(f"  {rssi:>4} dBm  {dev.address}  {name}{mark}")
        if adv.service_uuids:
            for u in adv.service_uuids:
                flag = "  (service 0xFFF0 !)" if _SERVICE_HINT in str(u).lower() else ""
                print(f"              service: {u}{flag}")
        if is_cam:
            candidates.append((dev, adv, name))

    print()
    if candidates:
        print("=" * 60)
        print("CANDIDAT(S) CAMÉRA :")
        for dev, adv, name in candidates:
            print(f"  • {name}  —  {dev.address}")
        print("Note l'adresse (ou le nom) : on l'utilisera pour se connecter.")
        print("=" * 60)
    else:
        print("Aucun candidat évident. Si la caméra est bien allumée, envoie-moi")
        print("la liste ci-dessus et on identifiera le bon appareil ensemble.")


if __name__ == "__main__":
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    try:
        asyncio.run(main(timeout))
    except KeyboardInterrupt:
        print("\nScan interrompu.")
