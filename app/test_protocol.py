"""
Vérifie le moteur de protocole contre la trame de RÉFÉRENCE OFFICIELLE de DJI.

Si ces tests passent, ça prouve au bit près que notre CRC16, CRC32 et notre
assemblage de trame sont identiques à ceux de la caméra. C'est la fondation.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")  # console Windows : autoriser ✔ et accents
from osmo_controller import protocol as p

# Trame d'exemple officielle (protocol_data_segment.md, "Mode Switch" -> Hyperlapse)
GOLD = bytes([
    0xAA, 0x1B, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x05, 0x00, 0x57, 0xEE,
    0x1D, 0x04, 0x00, 0x00, 0x33, 0xFF, 0x0A, 0x01, 0x47, 0x39, 0x36,
    0xF4, 0xFA, 0xE1, 0xD0,
])

ok = True

def check(label, cond):
    global ok
    print(f"  [{'OK ' if cond else 'FAIL'}] {label}")
    ok = ok and cond


print("1) CRC contre la trame de référence officielle de DJI")
# CRC16 calculé sur SOF..SEQ (10 octets) doit donner 0xEE57 (octets 57 EE en LE)
check("CRC16 == 0xEE57", p.calculate_crc16(GOLD[0:10]) == 0xEE57)
# CRC32 calculé sur SOF..DATA (23 octets) doit donner 0xD0E1FAF4 (F4 FA E1 D0 en LE)
check("CRC32 == 0xD0E1FAF4", p.calculate_crc32(GOLD[0:23]) == 0xD0E1FAF4)

print("\n2) Reproduction de la trame complète, octet par octet")
# Reconstruire EXACTEMENT la trame de DJI à partir de notre assembleur.
# DATA = device_id(00 00 33 FF) + mode(0A) + reserved(01 47 39 36)
payload = bytes([0x00, 0x00, 0x33, 0xFF, 0x0A, 0x01, 0x47, 0x39, 0x36])
rebuilt = p.build_frame(cmd_set=0x1D, cmd_id=0x04, payload=payload,
                        seq=0x0005, cmd_type=0x01)
check("trame reconstruite == trame DJI", rebuilt == GOLD)
if rebuilt != GOLD:
    print("    attendu :", GOLD.hex(" "))
    print("    obtenu  :", rebuilt.hex(" "))

print("\n3) parse_frame() relit correctement la trame de référence")
pf = p.parse_frame(GOLD)
check("CRC16 validé à la lecture", pf.crc16_ok)
check("CRC32 validé à la lecture", pf.crc32_ok)
check("CmdSet/CmdID == 0x1D/0x04", pf.cmd_set == 0x1D and pf.cmd_id == 0x04)
check("SEQ == 5", pf.seq == 5)

print("\n4) Commande Record (1D03) pour l'Osmo Action 5 Pro — round-trip")
dev = p.DEVICE_IDS["osmo_action_5_pro"]
start = p.build_record_command(start=True, device_id_16=dev, seq=1)
stop = p.build_record_command(start=False, device_id_16=dev, seq=2)
ps = p.parse_frame(start)
check("START : CRC16+CRC32 valides", ps.crc16_ok and ps.crc32_ok)
check("START : CmdSet/CmdID == 1D/03", ps.cmd_set == 0x1D and ps.cmd_id == 0x03)
check("START : record_ctrl == 0 (start)", ps.payload[4] == 0x00)
check("STOP  : record_ctrl == 1 (stop)", p.parse_frame(stop).payload[4] == 0x01)
check("device_id encodé == 00 00 44 FF", ps.payload[0:4] == bytes([0x00, 0x00, 0x44, 0xFF]))
print("    START frame :", start.hex(" "))
print("    STOP  frame :", stop.hex(" "))

print("\n4b) Power Mode Switch (0x00/0x1A) — veille/réveil (hypothèse à vérifier sur matériel)")
sleep_frame = p.build_power_mode_command(sleep=True, seq=10)
wake_frame = p.build_power_mode_command(sleep=False, seq=11)
pf_sleep = p.parse_frame(sleep_frame)
pf_wake = p.parse_frame(wake_frame)
check("sleep : CRC valides", pf_sleep.crc16_ok and pf_sleep.crc32_ok)
check("sleep : CmdSet/CmdID == 00/1A", pf_sleep.cmd_set == 0x00 and pf_sleep.cmd_id == 0x1A)
check("sleep : power_mode == 3", pf_sleep.payload[0] == 0x03)
check("wake  : power_mode == 0", pf_wake.payload[0] == 0x00)
print("    sleep frame :", sleep_frame.hex(" "))
print("    wake  frame :", wake_frame.hex(" "))

print("\n5) Abonnement statut (1D05) + décodage d'un push (1D02) simulé")
sub = p.build_status_subscription(seq=3)
check("1D05 : CRC valides", p.parse_frame(sub).crc16_ok and p.parse_frame(sub).crc32_ok)

# Construire un faux push de statut pour valider le décodeur :
# mode=Vidéo(01), status=enr.(03), record_time=125s, remain_capacity=45000MB,
# remain_time=3600s, temp=normale(0), batterie=84%
fake = bytearray(38)
fake[0] = 0x01
fake[1] = 0x03
fake[5:7] = (125).to_bytes(2, "little")
fake[15:19] = (45000).to_bytes(4, "little")
fake[23:27] = (3600).to_bytes(4, "little")
fake[30] = 0x00
fake[37] = 84
st = p.parse_camera_status(bytes(fake))
check("statut : enregistre == True", st["is_recording"] is True)
check("statut : record_time == 125", st["record_time_s"] == 125)
check("statut : SD restante == 45000 MB", st["remain_capacity_mb"] == 45000)
check("statut : temps restant == 3600 s", st["remain_time_s"] == 3600)
check("statut : batterie == 84 %", st["battery_pct"] == 84)
print("    décodé :", st)

print("\n6) FrameReassembler — trames fragmentées sur plusieurs paquets BLE")
r = p.FrameReassembler()
# a) une trame complète d'un coup (cas Windows aujourd'hui)
check("trame entière en un paquet", r.feed(GOLD) == [GOLD])

# b) la même trame coupée en 3 paquets (cas MTU réduit, ex. macOS)
r2 = p.FrameReassembler()
frames = []
for chunk in (GOLD[:5], GOLD[5:14], GOLD[14:]):
    frames += r2.feed(chunk)
check("trame reconstituée après fragmentation", frames == [GOLD])

# c) deux trames concaténées dans un seul paquet (au cas où)
r3 = p.FrameReassembler()
frames = r3.feed(GOLD + GOLD)
check("deux trames dans un seul paquet", frames == [GOLD, GOLD])

# d) bruit (ex. télémétrie DUML 0x55) avant une trame valide : ignoré, puis resynchronisé
r4 = p.FrameReassembler()
frames = []
frames += r4.feed(bytes([0x55, 0x01, 0x02, 0x03]))
check("bruit seul ne renvoie aucune trame", frames == [])
frames += r4.feed(GOLD)
check("resynchronisation après du bruit", frames == [GOLD])

print("\n" + ("=" * 48))
print("  TOUS LES TESTS PASSENT ✔" if ok else "  ÉCHEC �’— voir ci-dessus")
print("=" * 48)
sys.exit(0 if ok else 1)
