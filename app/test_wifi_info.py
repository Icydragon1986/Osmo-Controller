"""
Vérifie wifi_info.py : format du code QR Wi-Fi (échappement), config
manuelle (hotspot), et lecture des sorties `netsh` (texte figé, capturé sur
une vraie machine Windows en français — pas d'appel réseau réel ici).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")  # console Windows : autoriser ✔ et accents

import tempfile
from pathlib import Path

from osmo_controller import wifi_info as w

ok = True


def check(label, cond):
    global ok
    print(f"  [{'OK ' if cond else 'FAIL'}] {label}")
    ok = ok and cond


print("1) Format du payload WIFI: (reconnu par l'appareil photo iOS/Android)")
check("réseau avec mot de passe",
      w.wifi_qr_payload("Terrain 1", "motdepasse") == "WIFI:T:WPA;S:Terrain 1;P:motdepasse;;")
check("réseau ouvert (sans mot de passe)",
      w.wifi_qr_payload("Ouvert", "") == "WIFI:T:nopass;S:Ouvert;P:;;")

print("\n2) Échappement des caractères spéciaux du format WIFI:")
escaped = w.wifi_qr_payload('Bocc;ia"Wifi', 'pa:ss,word\\x')
check("point-virgule échappé", r"Bocc\;ia" in escaped)
check("guillemet échappé", r'\"Wifi' in escaped)
check("deux-points échappé dans le mot de passe", r"pa\:ss" in escaped)
check("virgule échappée dans le mot de passe", r"ss\,word" in escaped)
check("antislash échappé dans le mot de passe", r"word\\x" in escaped)

print("\n3) Config manuelle (hotspot) — persistance JSON")
tmp = Path(tempfile.mkdtemp()) / "wifi_config.json"
check("aucun fichier -> None", w.load_wifi_config(tmp) is None)
w.save_wifi_config(tmp, "MonHotspot", "secret123")
cfg = w.load_wifi_config(tmp)
check("config relue correctement", cfg == {"ssid": "MonHotspot", "password": "secret123"})
w.clear_wifi_config(tmp)
check("config effacée -> None", w.load_wifi_config(tmp) is None)
check("effacer une config déjà absente ne plante pas", w.clear_wifi_config(tmp) is None)

print("\n4) SSID vide dans le fichier -> traité comme absent")
tmp2 = Path(tempfile.mkdtemp()) / "wifi_config.json"
w.save_wifi_config(tmp2, "", "motdepasse")
check("SSID vide -> None (pas de QR Wi-Fi cassé)", w.load_wifi_config(tmp2) is None)

print("\n5) Piège FR : « déconnecté » contient le sous-texte « connect »")
check("« connecté » reconnu comme connecté", w._is_connected_state("connecté"))
check("« Connected » (EN) reconnu comme connecté", w._is_connected_state("Connected"))
check("« déconnecté » PAS pris pour connecté (piège du préfixe dé-)",
      not w._is_connected_state("déconnecté"))
check("« Disconnected » (EN) PAS pris pour connecté", not w._is_connected_state("Disconnected"))

print("\n6) Lecture d'une sortie `netsh wlan show interfaces` (français, capturée réellement)")
sample_interfaces_connected = """
    Nom                   : Wi-Fi
    Description            : RZ616 Wi-Fi 6E 160MHz
    GUID                   : 0c778030-6570-4344-b6f5-0e53381d47cc
    Adresse physique       : 14:ac:60:e6:cb:fd
    Type d’interface         : Primaire
    État                  : connecté
    SSID                   : Boccia-Tournoi
    BSSID                  : aa:bb:cc:dd:ee:ff
"""
check("État connecté détecté",
      w._is_connected_state(w._find_value(sample_interfaces_connected, "État", "State") or ""))
check("SSID extrait", w._find_value(sample_interfaces_connected, "SSID") == "Boccia-Tournoi")

sample_interfaces_disconnected = """
    Nom                   : Wi-Fi
    État                  : déconnecté
"""
check("État déconnecté détecté comme non-connecté",
      not w._is_connected_state(w._find_value(sample_interfaces_disconnected, "État", "State") or ""))

print("\n7) Lecture d'une sortie `netsh wlan show profile ... key=clear` (français)")
sample_profile = """
Profil Wi-Fi Boccia-Tournoi sur l'interface Wi-Fi.
=======================================================================
Paramètres de connexion
    ...
Paramètres de sécurité
=======================================================================
    Authentification         : WPA2-Personnel
    Chiffrement            : CCMP
    Contenu de la clé            : motdepasse2024
"""
check("mot de passe extrait", w._find_value(sample_profile, "Contenu de la clé", "Key Content") == "motdepasse2024")

print("\n" + ("=" * 48))
print("  TOUS LES TESTS PASSENT ✔" if ok else "  ÉCHEC — voir ci-dessus")
print("=" * 48)
sys.exit(0 if ok else 1)
