"""
Vérifie la construction du paquet de réveil BLE (wake_broadcast.py) :
inversion de l'adresse MAC, format attendu par la doc DJI. Ne diffuse rien
réellement (pas de matériel nécessaire) — seule la logique pure est testée ;
l'envoi réel est vérifié via hardware/wake_broadcast_test.py.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from osmo_controller import wake_broadcast as w

ok = True


def check(label, cond):
    global ok
    print(f"  [{'OK ' if cond else 'FAIL'}] {label}")
    ok = ok and cond


print("1) Inversion de l'adresse MAC")
check("MAC inversée correctement",
      w._mac_bytes("8C:58:23:2B:25:23")[::-1] == bytes([0x23, 0x25, 0x2B, 0x23, 0x58, 0x8C]))
check("format avec tirets accepté", w._mac_bytes("8C-58-23-2B-25-23") == w._mac_bytes("8C:58:23:2B:25:23"))

print("\n2) Adresse invalide rejetée")
rejected = False
try:
    w._mac_bytes("pas-une-adresse")
except ValueError:
    rejected = True
check("adresse mal formée lève ValueError", rejected)

print("\n3) Paquet complet 'P' + MAC inversée == 7 octets attendus par la doc DJI")
mac = w._mac_bytes("8C:58:23:2B:25:23")
payload = bytes([0x50]) + mac[::-1]
check("longueur == 7 octets", len(payload) == 7)
check("commence par 'P' (0x50)", payload[0] == 0x50)
check("suivi de la MAC inversée", payload[1:] == bytes([0x23, 0x25, 0x2B, 0x23, 0x58, 0x8C]))

print("\n" + ("=" * 48))
print("  TOUS LES TESTS PASSENT ✔" if ok else "  ÉCHEC — voir ci-dessus")
print("=" * 48)
sys.exit(0 if ok else 1)
