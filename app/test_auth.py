"""
Vérifie les comptes utilisateurs et les sessions (auth.py) : hachage des mots
de passe, persistance JSON, authentification, expiration de session.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")  # console Windows : autoriser ✔ et accents

import tempfile
import time
from pathlib import Path

from osmo_controller import auth

ok = True


def check(label, cond):
    global ok
    print(f"  [{'OK ' if cond else 'FAIL'}] {label}")
    ok = ok and cond


print("1) Hachage des mots de passe")
h1 = auth.hash_password("motdepasse123")
h2 = auth.hash_password("motdepasse123")
check("bon mot de passe accepté", auth.verify_password("motdepasse123", h1))
check("mauvais mot de passe rejeté", not auth.verify_password("autrechose", h1))
check("deux hachages du même mot de passe diffèrent (sel aléatoire)", h1 != h2)
check("jamais stocké en clair", "motdepasse123" not in h1)

print("\n2) Persistance JSON (add_user / remove_user)")
tmp = Path(tempfile.mkdtemp()) / "users.json"
check("aucun fichier -> aucun utilisateur", auth.load_users(tmp) == {})
auth.add_user(tmp, "jonathan", "hunter2", role="admin")
auth.add_user(tmp, "coach1", "motdepasse", role="operator")
users = auth.load_users(tmp)
check("2 comptes créés", len(users) == 2)
check("rôle admin persisté", users["jonathan"]["role"] == "admin")
check("rôle operator persisté", users["coach1"]["role"] == "operator")
check("mot de passe jamais en clair dans le fichier", "hunter2" not in tmp.read_text())
removed = auth.remove_user(tmp, "coach1")
check("retrait réussi", removed is True)
check("retrait d'un compte inconnu -> False", auth.remove_user(tmp, "fantome") is False)
check("plus qu'un compte après retrait", len(auth.load_users(tmp)) == 1)

print("\n3) Rôle invalide rejeté")
rejected = False
try:
    auth.add_user(tmp, "x", "y", role="superadmin")
except ValueError:
    rejected = True
check("rôle inconnu lève ValueError", rejected)

print("\n4) authenticate()")
check("bons identifiants -> rôle", auth.authenticate(tmp, "jonathan", "hunter2") == "admin")
check("mauvais mot de passe -> None", auth.authenticate(tmp, "jonathan", "faux") is None)
check("utilisateur inconnu -> None", auth.authenticate(tmp, "personne", "x") is None)

print("\n5) SessionStore")
store = auth.SessionStore(ttl_s=0.2)
token = store.create("jonathan", "admin")
check("session valide juste après création", store.get(token) == ("jonathan", "admin"))
check("jeton inconnu -> None", store.get("jeton-invalide") is None)
check("jeton vide -> None", store.get(None) is None)
time.sleep(0.3)
check("session expirée -> None", store.get(token) is None)

token2 = store.create("coach1", "operator")
store.delete(token2)
check("session supprimée -> None", store.get(token2) is None)

print("\n" + ("=" * 48))
print("  TOUS LES TESTS PASSENT ✔" if ok else "  ÉCHEC — voir ci-dessus")
print("=" * 48)
sys.exit(0 if ok else 1)
