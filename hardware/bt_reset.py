"""
Test — RÉINITIALISER l'adaptateur Bluetooth du PC par logiciel.

Sur Windows, une déconnexion « propre » de bleak ne libère pas toujours la
caméra (WinRT garde le lien). Éteindre/rallumer la radio Bluetooth du PC force
la libération. On utilise l'API Windows.Devices.Radios (fournie avec bleak).

Usage : python hardware/bt_reset.py
"""
import asyncio


async def main() -> None:
    from winrt.windows.devices.radios import Radio, RadioKind, RadioState

    access = await Radio.request_access_async()
    print("Accès radio :", access)

    radios = await Radio.get_radios_async()
    bts = [r for r in radios if r.kind == RadioKind.BLUETOOTH]
    if not bts:
        print("Aucune radio Bluetooth trouvée.")
        return

    r = bts[0]
    print(f"Radio Bluetooth : {r.name} — état {r.state}")

    off_s = 35   # > timeout de supervision BLE (~32 s) pour forcer la caméra à lâcher
    print(f"Extinction pendant {off_s}s (laisse la caméra détecter la coupure)…")
    await r.set_state_async(RadioState.OFF)
    await asyncio.sleep(off_s)
    print("Rallumage…")
    await r.set_state_async(RadioState.ON)
    await asyncio.sleep(5)
    print("Terminé — l'adaptateur a été réinitialisé.")


if __name__ == "__main__":
    asyncio.run(main())
