"""
Vérifie le simulateur de caméra contre notre propre moteur de protocole.

On joue le rôle de l'app : on ENVOIE des commandes construites par protocol.py,
le simulateur RÉPOND, et on relit ses trames avec protocol.py. Si la boucle
ferme proprement (CRC valides des deux côtés, état cohérent), on peut bâtir
toute l'app contre ce simulateur sans matériel.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")  # console Windows : autoriser ✔ et accents

from osmo_controller import protocol as p
from osmo_controller.simulator import OsmoCameraSimulator

ok = True


def check(label, cond):
    global ok
    print(f"  [{'OK ' if cond else 'FAIL'}] {label}")
    ok = ok and cond


print("1) START enregistrement : la caméra passe en mode enregistrement")
cam = OsmoCameraSimulator(model="osmo_action_5_pro", battery_pct=100)
dev = p.DEVICE_IDS["osmo_action_5_pro"]
resps = cam.handle_command(p.build_record_command(start=True, device_id_16=dev, seq=1))
check("la caméra enregistre", cam.is_recording is True)
check("une réponse ACK est émise", len(resps) >= 1)
ack = p.parse_frame(resps[0])
check("ACK : CRC16+CRC32 valides", ack.crc16_ok and ack.crc32_ok)
check("ACK : bit RESPONSE positionné", ack.cmd_type & p.FRAME_TYPE_RESPONSE != 0)
check("ACK : CmdSet/CmdID == 1D/03", ack.cmd_set == 0x1D and ack.cmd_id == 0x03)

print("\n2) STOP enregistrement : la caméra revient au repos")
cam.handle_command(p.build_record_command(start=False, device_id_16=dev, seq=2))
check("la caméra n'enregistre plus", cam.is_recording is False)

print("\n3) Abonnement statut : tick() émet un push (1D02) décodable")
cam = OsmoCameraSimulator(battery_pct=84, remain_capacity_mb=45_000)
cam.handle_command(p.build_status_subscription(seq=3))
check("la caméra est abonnée", cam.subscribed is True)
pushes = cam.tick(dt_s=0.5)
check("un push est émis", len(pushes) == 1)
pf = p.parse_frame(pushes[0])
check("push : CRC valides", pf.crc16_ok and pf.crc32_ok)
check("push : CmdSet/CmdID == 1D/02", pf.cmd_set == 0x1D and pf.cmd_id == 0x02)
st = p.parse_camera_status(pf.payload)
check("statut : batterie == 84 %", st["battery_pct"] == 84)
check("statut : SD restante == 45000 MB", st["remain_capacity_mb"] == 45_000)
check("statut : pas en enregistrement", st["is_recording"] is False)
print("    décodé :", st)

print("\n4) Boucle complète : START -> le statut reflète l'enregistrement qui dure")
cam = OsmoCameraSimulator(battery_pct=100, remain_capacity_mb=60_000)
cam.handle_command(p.build_status_subscription(seq=4))
cam.handle_command(p.build_record_command(start=True, device_id_16=dev, seq=5))
for _ in range(20):                     # 20 ticks de 0.5 s = 10 s simulées
    last = cam.tick(dt_s=0.5)
st = p.parse_camera_status(p.parse_frame(last[0]).payload)
check("statut : is_recording == True", st["is_recording"] is True)
check("statut : record_time ~ 10 s", 9 <= st["record_time_s"] <= 11)
check("statut : SD a diminué", st["remain_capacity_mb"] < 60_000)
check("statut : temps restant cohérent (>0)", st["remain_time_s"] > 0)
print("    décodé :", st)

print("\n5) Robustesse : une trame au CRC corrompu est ignorée")
cam = OsmoCameraSimulator()
good = p.build_record_command(start=True, device_id_16=dev, seq=6)
corrupt = bytearray(good)
corrupt[-1] ^= 0xFF                      # casse le CRC32
out = cam.handle_command(bytes(corrupt))
check("aucune réponse à une trame corrompue", out == [])
check("la caméra n'a pas démarré sur une trame corrompue", cam.is_recording is False)

print("\n" + ("=" * 48))
print("  TOUS LES TESTS PASSENT ✔" if ok else "  ÉCHEC — voir ci-dessus")
print("=" * 48)
sys.exit(0 if ok else 1)
