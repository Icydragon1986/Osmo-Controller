"""
Comptes utilisateurs et sessions — protège l'accès quand le serveur est
exposé sur le réseau local (Wi-Fi de tournoi, pas toujours fiable).

Deux rôles :
  - "operator" : démarrer/arrêter l'enregistrement, voir le statut.
  - "admin"    : idem + gérer les caméras (scan/ajout/retrait) + quitter l'app.

Mots de passe jamais stockés en clair : PBKDF2-HMAC-SHA256 + sel aléatoire par
utilisateur, tout en stdlib (pas de bcrypt/argon2 à installer).
"""

from __future__ import annotations
import hashlib
import json
import secrets
import time
from pathlib import Path
from typing import Optional

ROLES = ("operator", "admin")
_PBKDF2_ITERATIONS = 200_000
_DEFAULT_SESSION_TTL_S = 12 * 3600  # 12h : large pour une journée de tournoi


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return secrets.compare_digest(actual, expected)


def load_users(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_users(path, users: dict) -> None:
    Path(path).write_text(
        json.dumps(users, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def add_user(path, username: str, password: str, role: str = "operator") -> None:
    if role not in ROLES:
        raise ValueError(f"rôle invalide : {role!r} (attendu : {ROLES})")
    if not username:
        raise ValueError("nom d'utilisateur vide")
    users = load_users(path)
    users[username] = {"password_hash": hash_password(password), "role": role}
    save_users(path, users)


def remove_user(path, username: str) -> bool:
    users = load_users(path)
    if username not in users:
        return False
    del users[username]
    save_users(path, users)
    return True


def authenticate(path, username: str, password: str) -> Optional[str]:
    """Renvoie le rôle si les identifiants sont valides, sinon None."""
    entry = load_users(path).get(username)
    if entry is None or not verify_password(password, entry.get("password_hash", "")):
        return None
    return entry.get("role")


class SessionStore:
    """Sessions en mémoire : perdues à l'arrêt de l'app (il suffit de se
    reconnecter), jamais persistées sur disque."""

    def __init__(self, ttl_s: float = _DEFAULT_SESSION_TTL_S) -> None:
        self._ttl_s = ttl_s
        self._sessions: dict[str, tuple[str, str, float]] = {}

    def create(self, username: str, role: str) -> str:
        token = secrets.token_hex(32)
        self._sessions[token] = (username, role, time.monotonic() + self._ttl_s)
        return token

    def get(self, token: Optional[str]) -> Optional[tuple[str, str]]:
        if not token:
            return None
        entry = self._sessions.get(token)
        if entry is None:
            return None
        username, role, expiry = entry
        if time.monotonic() > expiry:
            del self._sessions[token]
            return None
        return username, role

    def delete(self, token: Optional[str]) -> None:
        self._sessions.pop(token, None)
