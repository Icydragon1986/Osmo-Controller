"""
Gestion des comptes (users.json) pour Osmo Controller — à lancer depuis un
terminal, quand tu veux ajouter/retirer quelqu'un.

Usage :
    python manage_users.py add jonathan motdepasse --role admin
    python manage_users.py add coach1 motdepasse2 --role operator
    python manage_users.py remove coach1
    python manage_users.py list

Rôles :
  - admin    : tout (enregistrement + gérer les caméras + quitter l'app)
  - operator : juste démarrer/arrêter l'enregistrement et voir le statut
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))
from osmo_controller import auth  # noqa: E402

USERS_PATH = ROOT / "users.json"


def cmd_add(args) -> int:
    try:
        auth.add_user(USERS_PATH, args.username, args.password, role=args.role)
    except ValueError as e:
        print(f"Erreur : {e}")
        return 1
    print(f"Compte « {args.username} » ({args.role}) ajouté/mis à jour.")
    return 0


def cmd_remove(args) -> int:
    if auth.remove_user(USERS_PATH, args.username):
        print(f"Compte « {args.username} » retiré.")
        return 0
    print(f"Aucun compte « {args.username} ».")
    return 1


def cmd_list(_args) -> int:
    users = auth.load_users(USERS_PATH)
    if not users:
        print("Aucun compte configuré.")
        return 0
    for name, entry in users.items():
        print(f"  {name}  ({entry.get('role', '?')})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gestion des comptes Osmo Controller")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="ajouter ou mettre à jour un compte")
    p_add.add_argument("username")
    p_add.add_argument("password")
    p_add.add_argument("--role", choices=auth.ROLES, default="operator")
    p_add.set_defaults(func=cmd_add)

    p_remove = sub.add_parser("remove", help="retirer un compte")
    p_remove.add_argument("username")
    p_remove.set_defaults(func=cmd_remove)

    p_list = sub.add_parser("list", help="lister les comptes")
    p_list.set_defaults(func=cmd_list)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
