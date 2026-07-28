"""
Config Wi-Fi manuelle pour le point d'accès (hotspot) du PC — à lancer
depuis un terminal, quand tu configures/changes le hotspot.

Le Wi-Fi normal (celui du lieu) est détecté automatiquement, pas besoin de
ce script pour lui. Ce script sert seulement quand le PC crée SON PROPRE
point d'accès (Windows ne permet pas de lire son SSID/mot de passe par
programme) : Osmo Controller génère alors le code QR « rejoindre le Wi-Fi »
à partir de ce que tu entres ici.

Usage :
    python manage_wifi.py set MonHotspot motdepasse123
    python manage_wifi.py show
    python manage_wifi.py clear
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))
from osmo_controller import wifi_info  # noqa: E402

CONFIG_PATH = ROOT / "wifi_config.json"


def cmd_set(args) -> int:
    wifi_info.save_wifi_config(CONFIG_PATH, args.ssid, args.password)
    print(f"Config Wi-Fi enregistrée : « {args.ssid} ».")
    return 0


def cmd_show(_args) -> int:
    cfg = wifi_info.load_wifi_config(CONFIG_PATH)
    if cfg is None:
        print("Aucune config Wi-Fi manuelle (le Wi-Fi normal du lieu sera détecté automatiquement).")
        return 0
    print(f"SSID : {cfg['ssid']}")
    print(f"Mot de passe : {cfg['password']}")
    return 0


def cmd_clear(_args) -> int:
    wifi_info.clear_wifi_config(CONFIG_PATH)
    print("Config Wi-Fi manuelle effacée.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Config Wi-Fi (hotspot) pour Osmo Controller")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_set = sub.add_parser("set", help="enregistrer le SSID/mot de passe du hotspot")
    p_set.add_argument("ssid")
    p_set.add_argument("password", nargs="?", default="")
    p_set.set_defaults(func=cmd_set)

    p_show = sub.add_parser("show", help="afficher la config actuelle")
    p_show.set_defaults(func=cmd_show)

    p_clear = sub.add_parser("clear", help="effacer la config manuelle")
    p_clear.set_defaults(func=cmd_clear)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
