"""AES-256-GCM Ver-/Entschluesselung fuer Secrets.

Schluessel kommt ausschliesslich aus der Env-Var FINTS_MASTER_KEY
(base64-kodierte 32 Byte). NIE auf Platte, NIE im Repo.

Format des Blobs: [12-Byte-Nonce][Ciphertext+GCM-Tag].
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import ENV_MASTER_KEY

NONCE_BYTES = 12
KEY_BYTES = 32


class MasterKeyError(RuntimeError):
    """Master-Key fehlt oder ist ungueltig."""


def generate_key() -> str:
    """Erzeuge einen frischen 32-Byte-Schluessel, base64-kodiert."""
    return base64.b64encode(os.urandom(KEY_BYTES)).decode("ascii")


def _load_key() -> bytes:
    raw = os.environ.get(ENV_MASTER_KEY)
    if not raw:
        raise MasterKeyError(
            f"Env-Var {ENV_MASTER_KEY} ist nicht gesetzt. "
            f"Erzeuge einen Key mit `python enroll.py` (Option Key generieren) "
            f"und trage ihn in deine .env / Umgebung ein."
        )
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:  # noqa: BLE001 - klare Meldung statt Stacktrace
        raise MasterKeyError(
            f"{ENV_MASTER_KEY} ist kein gueltiges base64."
        ) from exc
    if len(key) != KEY_BYTES:
        raise MasterKeyError(
            f"{ENV_MASTER_KEY} muss {KEY_BYTES} Byte (base64) sein, "
            f"hat aber {len(key)} Byte."
        )
    return key


def encrypt(plaintext: bytes) -> bytes:
    """Verschluessle plaintext -> [nonce][ciphertext]."""
    key = _load_key()
    nonce = os.urandom(NONCE_BYTES)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce + ct


def decrypt(blob: bytes) -> bytes:
    """Entschluessle [nonce][ciphertext] -> plaintext."""
    key = _load_key()
    if len(blob) <= NONCE_BYTES:
        raise MasterKeyError("Verschluesselter Blob ist zu kurz / korrupt.")
    nonce, ct = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ct, None)
