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
# WICHTIG (verifiziert python-fints#183, 2025/2026): DKB lehnt seit dem
# FinTS-Umzug 10/2024 jede nicht akzeptierte product_id ab — der Dialog wird
# bankseitig VOR jeder TAN-Abfrage gekippt (9210 Auftrag abgelehnt / 9800 Dialog
# abgebrochen / 9050). Es ist KEIN PIN/TAN-Fehler, sondern Identifikations-Ebene.
# Sauber: eigene product_id bei der Deutschen Kreditwirtschaft registrieren
# (https://www.fints.org/de/hersteller/produktregistrierung, ~5-10 Werktage,
# Original-Formular an registrierung@hbci-zka.de) und via FINTS_PRODUCT_ID setzen.
# Default unten ist die in python-fints#183 mehrfach als funktionierend belegte
# oeffentliche ID (NOYB4Europe/felixschndr, 2025-08 .. 2026-05) — pragmatischer
# Start ohne Registrierung. Risiko: oeffentliche IDs werden von DKB nur geduldet,
# koennen jederzeit gesperrt werden -> dann FINTS_PRODUCT_ID auf eigene ID setzen.
DEFAULT_PRODUCT_ID = "6151256F3D4F9975B877BD4A2"  # public, DKB-akzeptiert (#183)

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
