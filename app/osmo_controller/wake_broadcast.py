"""
Réveil à distance d'une caméra endormie — Windows seulement.

Contrairement à ce qu'on pensait d'abord (une commande envoyée sur la
connexion existante), la doc officielle DJI (`Q&A.md` + `Camera Power Mode
Settings (001A)` du SDK) documente un mécanisme différent : le contrôleur
doit lui-même DIFFUSER (broadcast) un paquet BLE spécial pendant ~2 secondes,
contenant "WKP" + l'adresse MAC de la caméra en ordre INVERSÉ. La caméra
capte cette diffusion même en veille (son GATT server est éteint, mais son
récepteur BLE écoute encore ce paquet précis) et se rallume — après quoi la
connexion BLE doit être RÉTABLIE (elle se coupe pendant la veille).

Conditions documentées par DJI :
  - le contrôleur doit s'être déjà connecté à CETTE caméra récemment ;
  - la caméra ne doit pas dormir depuis plus de 30 minutes.

Format du paquet (AD structure, Manufacturer Specific Data 0xFF) :
    company_id = 0x4B57  ('W','K' en little-endian)
    data       = 0x50 ('P') + adresse MAC inversée (6 octets)
"""

from __future__ import annotations


class WakeBroadcastUnavailable(Exception):
    """Diffusion BLE indisponible sur cette machine (Windows seulement)."""


def _mac_bytes(address: str) -> bytes:
    parts = address.replace("-", ":").split(":")
    if len(parts) != 6:
        raise ValueError(f"adresse MAC invalide : {address!r}")
    return bytes(int(p, 16) for p in parts)


async def broadcast_wake(address: str, duration_s: float = 2.0) -> None:
    """Diffuse le paquet de réveil "WKP<mac inversée>" pendant `duration_s`
    secondes. Ne se connecte PAS à la caméra ensuite — à faire séparément
    après cet appel (la doc DJI indique que la connexion se coupe pendant la
    veille et doit être rétablie après le réveil)."""
    import asyncio

    try:
        from winrt.windows.devices.bluetooth.advertisement import (
            BluetoothLEAdvertisement,
            BluetoothLEAdvertisementPublisher,
            BluetoothLEManufacturerData,
        )
        from winrt.windows.storage.streams import DataWriter
    except ImportError as e:
        raise WakeBroadcastUnavailable(
            "Fonction Windows seulement (pip install "
            "winrt-Windows.Devices.Bluetooth.Advertisement winrt-Windows.Storage.Streams)"
        ) from e

    reversed_mac = _mac_bytes(address)[::-1]
    payload = bytes([0x50]) + reversed_mac   # 'P' + MAC inversée (7 octets)

    writer = DataWriter()
    writer.write_bytes(payload)

    manufacturer_data = BluetoothLEManufacturerData()
    manufacturer_data.company_id = 0x4B57    # 'W','K' en little-endian
    manufacturer_data.data = writer.detach_buffer()

    advertisement = BluetoothLEAdvertisement()
    advertisement.manufacturer_data.append(manufacturer_data)

    publisher = BluetoothLEAdvertisementPublisher(advertisement)
    publisher.start()
    try:
        await asyncio.sleep(duration_s)
    finally:
        publisher.stop()
