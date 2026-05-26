#!/usr/bin/env python3
"""Interaktiver Enroll fuer FinTS-Finanzen — NUR der User fuehrt das aus.

Schritte:
  1. (optional) frischen FINTS_MASTER_KEY generieren + anzeigen.
  2. Anmeldename + PIN abfragen (PIN via getpass, nie echoen).
  3. Erster FinTS-Login mit pushTAN-Flow (TAN-Mechanismus + Medium waehlen,
     TAN interaktiv eingeben) — folgt dem python-fints `tans`-Pattern.
  4. Bei Erfolg: PIN verschluesselt + Client-State (system_id, BPD/UPD)
     persistieren -> danach sind Lesezugriffe ~90 Tage TAN-frei (PSD2 SCA).

Aufruf:  python enroll.py
Voraussetzung: FINTS_MASTER_KEY in der Umgebung (oder hier generieren).
"""
from __future__ import annotations

import getpass
import os
import sys

import config
import crypto
from fints.client import FinTS3PinTanClient, NeedTANResponse
from fints_client import Credentials, build_client, save_credentials, save_state


def _line(msg: str = "") -> None:
    print(msg, flush=True)


def step_master_key() -> None:
    if os.environ.get(config.ENV_MASTER_KEY):
        _line(f"[ok] {config.ENV_MASTER_KEY} ist gesetzt.")
        return
    _line(f"[!] {config.ENV_MASTER_KEY} ist NICHT gesetzt.")
    ans = input("Frischen Key generieren? [J/n] ").strip().lower()
    if ans in ("", "j", "y", "ja", "yes"):
        key = crypto.generate_key()
        _line("")
        _line("=" * 64)
        _line("Neuer Master-Key (base64, 32 Byte). Trage ihn in deine .env ein:")
        _line(f"  {config.ENV_MASTER_KEY}={key}")
        _line("=" * 64)
        _line("")
        # Fuer diesen Lauf direkt in die Umgebung legen, damit es weitergeht.
        os.environ[config.ENV_MASTER_KEY] = key
        _line("(Key fuer diese Session aktiv. Persistiere ihn JETZT, sonst sind")
        _line(" die gleich gespeicherten Credentials nach Neustart unlesbar.)")
        input("Enter zum Fortfahren ...")
    else:
        _line("Abbruch — ohne Master-Key kann nicht verschluesselt werden.")
        sys.exit(1)


def step_credentials() -> Credentials:
    _line("")
    user_id = input("DKB Anmeldename (NICHT Kontonummer): ").strip()
    if not user_id:
        _line("Anmeldename darf nicht leer sein.")
        sys.exit(1)
    pin = getpass.getpass("DKB Banking-PIN: ")
    if not pin:
        _line("PIN darf nicht leer sein.")
        sys.exit(1)
    return Credentials(user_id=user_id, pin=pin)


def step_choose_tan_mechanism(client: FinTS3PinTanClient) -> None:
    mechanisms = client.get_tan_mechanisms()
    if not mechanisms:
        _line("Keine TAN-Mechanismen gemeldet — fahre mit Default fort.")
        return
    _line("")
    _line("Verfuegbare TAN-Mechanismen:")
    items = list(mechanisms.items())
    for i, (sec_func, params) in enumerate(items):
        name = getattr(params, "name", "?")
        _line(f"  [{i}] {sec_func}  {name}")
    if len(items) == 1:
        sec_func = items[0][0]
        _line(f"-> nutze einzigen Mechanismus {sec_func}")
    else:
        idx = int(input("Mechanismus-Nummer waehlen: ").strip() or "0")
        sec_func = items[idx][0]
    client.set_tan_mechanism(sec_func)


def step_choose_tan_medium(client: FinTS3PinTanClient) -> None:
    if not client.is_tan_media_required():
        return
    _line("")
    _line("TAN-Medium-Auswahl noetig.")
    _, media = client.get_tan_media()
    if not media:
        _line("Keine TAN-Medien gemeldet.")
        return
    for i, m in enumerate(media):
        name = getattr(m, "tan_medium_name", None) or getattr(m, "card_number", "?")
        _line(f"  [{i}] {name}")
    if len(media) == 1:
        chosen = media[0]
    else:
        idx = int(input("Medium-Nummer waehlen: ").strip() or "0")
        chosen = media[idx]
    client.set_tan_medium(chosen)


def step_login_and_tan(client: FinTS3PinTanClient) -> None:
    """Oeffne den Dialog; falls die Bank eine TAN verlangt, interaktiv loesen."""
    with client:
        # Trigger fuer den initialen Dialog: Konten abrufen.
        result = client.get_sepa_accounts()

        # Manche Banken verlangen die TAN bereits beim Dialog-Init.
        challenge = client.init_tan_response
        if challenge is None and isinstance(result, NeedTANResponse):
            challenge = result

        while isinstance(challenge, NeedTANResponse):
            _line("")
            _line(">> pushTAN-Freigabe noetig.")
            if challenge.challenge:
                _line(f"   Challenge: {challenge.challenge}")
            if getattr(challenge, "decoupled", False):
                input("   Bestaetige die Freigabe in der DKB-App, dann Enter ...")
                challenge = client.send_tan(challenge, "")
            else:
                tan = input("   TAN eingeben: ").strip()
                challenge = client.send_tan(challenge, tan)

        # Nach erfolgreicher Freigabe ein zweites Mal Konten holen (bestaetigt SCA).
        accounts = client.get_sepa_accounts()
        _line("")
        _line(f"[ok] Login erfolgreich, {len(accounts)} Konto/Konten sichtbar:")
        for a in accounts:
            _line(f"   - {a.iban}  (Kto {a.accountnumber})")


def main() -> None:
    _line("=== FinTS-Finanzen Enroll (DKB, read-only) ===")
    config.ensure_config_dir()
    step_master_key()
    creds = step_credentials()

    _line("")
    _line("Verbinde mit DKB (erster Login, ohne persistierten State) ...")
    client = build_client(creds, from_data=None)

    try:
        # TAN-Mechanismen muessen vor dem Hauptdialog ausgehandelt werden.
        client.fetch_tan_mechanisms()
        step_choose_tan_mechanism(client)
        step_choose_tan_medium(client)
        step_login_and_tan(client)
    except Exception as exc:  # noqa: BLE001 - User-CLI, klare Meldung
        _line("")
        _line(f"[FEHLER] Enroll fehlgeschlagen: {exc}")
        _line("Pruefe Anmeldename/PIN und versuche es erneut.")
        sys.exit(1)

    # Erst NACH Erfolg persistieren.
    save_credentials(creds)
    save_state(client)

    _line("")
    _line("=" * 64)
    _line("[fertig] PIN verschluesselt + FinTS-State persistiert unter")
    _line(f"  {config.CONFIG_DIR}")
    _line("")
    _line("Lesezugriffe sind jetzt ~90 Tage TAN-frei (PSD2 SCA-Exemption).")
    _line("Danach meldet der MCP-Server 'Reenrollment noetig' -> enroll.py erneut.")
    _line("Stelle sicher, dass FINTS_MASTER_KEY dauerhaft in der Umgebung des")
    _line("MCP-Servers gesetzt ist (sonst sind die Credentials unlesbar).")
    _line("=" * 64)


if __name__ == "__main__":
    main()
