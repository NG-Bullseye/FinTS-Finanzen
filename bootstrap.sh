#!/usr/bin/env bash
# bootstrap.sh — idempotentes Aufsetzen: venv + requirements + .env aus Vorlage. Startet nichts, fragt keine PIN.
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
[ -f .env ] || { cp .env.example .env; chmod 600 .env; echo ".env aus Vorlage angelegt — FINTS_MASTER_KEY eintragen (Schritt 1)"; }
echo "ok — weiter mit README § Installation Schritt 1 (Master-Key) und 2 (enroll.py)"
