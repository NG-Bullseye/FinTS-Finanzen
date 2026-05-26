"""Zentrale Pfade, Konstanten und Env-Var-Namen fuer FinTS-Finanzen.

Single source of truth — kein anderes Modul hardcodet Pfade oder Bank-Daten.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Bank (DKB, verifiziert 2024-11-25) ---
BANK_CODE = "12030000"  # BLZ / bank_identifier
FINTS_ENDPOINT = "https://fints.dkb.de/fints"

# python-fints verlangt seit v4 eine product_id (sonst TypeError im Konstruktor).
# DKB akzeptiert in der Praxis den Lib-eigenen Test-Identifier; eine echte
# Registrierung ist optional. Wer eine registrierte product_id hat, setzt sie
# via FINTS_PRODUCT_ID. NICHT selbst registrieren.
DEFAULT_PRODUCT_ID = "9FA6681DEC0CF3046BFC2F8A6"  # python-fints Default-Test-ID

# --- Env-Var-Namen ---
ENV_MASTER_KEY = "FINTS_MASTER_KEY"      # base64(32 Byte) AES-256-GCM Schluessel
ENV_PRODUCT_ID = "FINTS_PRODUCT_ID"      # optional, leer -> DEFAULT_PRODUCT_ID

# --- Persistenz (NIE im Repo) ---
CONFIG_DIR = Path.home() / ".config" / "fints-finanzen"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.enc"   # verschluesselte PIN + Login
STATE_FILE = CONFIG_DIR / "fints_state.bin"         # client.deconstruct() Blob

DIR_MODE = 0o700
FILE_MODE = 0o600


def ensure_config_dir() -> Path:
    """Lege das Config-Verzeichnis mit restriktiven Rechten an."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # mkdir respektiert umask — Mode danach hart setzen.
    os.chmod(CONFIG_DIR, DIR_MODE)
    return CONFIG_DIR


def product_id() -> str:
    """Registrierte product_id aus Env, sonst Lib-Default."""
    return os.environ.get(ENV_PRODUCT_ID) or DEFAULT_PRODUCT_ID
