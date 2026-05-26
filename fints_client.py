"""Duenner read-only Wrapper um FinTS3PinTanClient.

Laedt die verschluesselte PIN + den persistierten Client-State, stellt
list_accounts / get_balance / get_transactions bereit und schreibt den
aktualisierten State (system_id, BPD/UPD) nach jedem Lauf zurueck —
das haelt Lesezugriffe nach gueltigem Enroll ~90 Tage TAN-frei (PSD2 SCA).

STRIKT read-only. Keine Ueberweisungs-/Schreib-Methoden.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from fints.client import FinTS3PinTanClient, NeedTANResponse

import config
import crypto


class EnrollmentRequired(RuntimeError):
    """Kein gueltiger Enroll-Stand vorhanden -> enroll.py noetig."""


class ReenrollmentRequired(RuntimeError):
    """Bank verlangt erneut eine TAN -> SCA abgelaufen, enroll.py noetig."""


# --------------------------------------------------------------------------
# Credential-Persistenz
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Credentials:
    user_id: str          # Anmeldename (NICHT Kontonummer)
    pin: str
    customer_id: Optional[str] = None


def save_credentials(creds: Credentials) -> None:
    """Schreibe Login + PIN verschluesselt nach credentials.enc (0o600)."""
    config.ensure_config_dir()
    payload = json.dumps(
        {"user_id": creds.user_id, "pin": creds.pin, "customer_id": creds.customer_id}
    ).encode("utf-8")
    blob = crypto.encrypt(payload)
    config.CREDENTIALS_FILE.write_bytes(blob)
    config.CREDENTIALS_FILE.chmod(config.FILE_MODE)


def load_credentials() -> Credentials:
    if not config.CREDENTIALS_FILE.exists():
        raise EnrollmentRequired(
            "Keine gespeicherten Credentials. Fuehre `python enroll.py` aus."
        )
    data = json.loads(crypto.decrypt(config.CREDENTIALS_FILE.read_bytes()))
    return Credentials(
        user_id=data["user_id"],
        pin=data["pin"],
        customer_id=data.get("customer_id"),
    )


def save_state(client: FinTS3PinTanClient) -> None:
    """Persistiere den FinTS-Client-State inkl. system_id (including_private)."""
    config.ensure_config_dir()
    blob = client.deconstruct(including_private=True)
    config.STATE_FILE.write_bytes(blob)
    config.STATE_FILE.chmod(config.FILE_MODE)


def _load_state_blob() -> Optional[bytes]:
    if config.STATE_FILE.exists():
        return config.STATE_FILE.read_bytes()
    return None


# --------------------------------------------------------------------------
# Client-Fabrik
# --------------------------------------------------------------------------
def build_client(creds: Optional[Credentials] = None,
                 from_data: Optional[bytes] = None) -> FinTS3PinTanClient:
    """Baue einen FinTS3PinTanClient.

    Im Normalbetrieb (read-only) wird der persistierte State via from_data
    geladen — dann faellt der pushTAN-Flow weg. enroll.py ruft ohne from_data.
    """
    if creds is None:
        creds = load_credentials()
    return FinTS3PinTanClient(
        config.BANK_CODE,
        creds.user_id,
        creds.pin,
        config.FINTS_ENDPOINT,
        customer_id=creds.customer_id,
        product_id=config.product_id(),
        from_data=from_data,
    )


# --------------------------------------------------------------------------
# Read-only Operationen
# --------------------------------------------------------------------------
def _serialize_account(acc) -> dict[str, Any]:
    return {
        "iban": acc.iban,
        "bic": acc.bic,
        "accountnumber": acc.accountnumber,
        "subaccount": acc.subaccount,
        "blz": acc.blz,
    }


def _match_account(accounts, selector: Optional[str]):
    """Finde ein Konto per IBAN oder Kontonummer; None -> erstes Konto."""
    if not accounts:
        raise EnrollmentRequired("Keine Konten gefunden — Enroll-Stand pruefen.")
    if selector is None:
        return accounts[0]
    needle = selector.replace(" ", "").upper()
    for acc in accounts:
        if (acc.iban and acc.iban.upper() == needle) or acc.accountnumber == selector:
            return acc
    raise ValueError(f"Kein Konto passt zu '{selector}'.")


def _guard_tan(result) -> None:
    """Bei Lesezugriff darf nach gueltigem Enroll keine TAN kommen."""
    if isinstance(result, NeedTANResponse):
        raise ReenrollmentRequired(
            "DKB verlangt eine pushTAN-Freigabe (SCA-Exemption abgelaufen). "
            "Fuehre `python enroll.py` zum Reenrollment aus."
        )


def list_accounts() -> list[dict[str, Any]]:
    """Liste aller SEPA-Konten."""
    creds = load_credentials()
    client = build_client(creds, from_data=_load_state_blob())
    try:
        with client:
            accounts = client.get_sepa_accounts()
            _guard_tan(accounts)
        return [_serialize_account(a) for a in accounts]
    finally:
        save_state(client)


def get_balance(account: Optional[str] = None) -> dict[str, Any]:
    """Saldo eines Kontos (per IBAN/Kontonummer; None -> erstes Konto)."""
    creds = load_credentials()
    client = build_client(creds, from_data=_load_state_blob())
    try:
        with client:
            accounts = client.get_sepa_accounts()
            _guard_tan(accounts)
            acc = _match_account(accounts, account)
            bal = client.get_balance(acc)
            _guard_tan(bal)
        return {
            "account": _serialize_account(acc),
            "amount": _amount(bal),
            "currency": _currency(bal),
            "date": _bal_date(bal),
        }
    finally:
        save_state(client)


def get_transactions(days: int = 30,
                     account: Optional[str] = None) -> dict[str, Any]:
    """Umsaetze der letzten `days` Tage."""
    creds = load_credentials()
    client = build_client(creds, from_data=_load_state_blob())
    start = date.today() - timedelta(days=days)
    end = date.today()
    try:
        with client:
            accounts = client.get_sepa_accounts()
            _guard_tan(accounts)
            acc = _match_account(accounts, account)
            txs = client.get_transactions(acc, start_date=start, end_date=end)
            _guard_tan(txs)
        return {
            "account": _serialize_account(acc),
            "from": start.isoformat(),
            "to": end.isoformat(),
            "count": len(txs),
            "transactions": [_serialize_tx(t) for t in txs],
        }
    finally:
        save_state(client)


def summary() -> dict[str, Any]:
    """Alle Konten + Salden kompakt in EINEM Dialog."""
    creds = load_credentials()
    client = build_client(creds, from_data=_load_state_blob())
    out: list[dict[str, Any]] = []
    try:
        with client:
            accounts = client.get_sepa_accounts()
            _guard_tan(accounts)
            for acc in accounts:
                bal = client.get_balance(acc)
                _guard_tan(bal)
                out.append({
                    "iban": acc.iban,
                    "accountnumber": acc.accountnumber,
                    "amount": _amount(bal),
                    "currency": _currency(bal),
                    "date": _bal_date(bal),
                })
        return {"accounts": out}
    finally:
        save_state(client)


# --------------------------------------------------------------------------
# Helpers: mt-940 Transaction + Balance Objekte robust serialisieren
# --------------------------------------------------------------------------
def _to_jsonable(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date,)):
        return v.isoformat()
    return v


def _amount(balance) -> Optional[float]:
    # python-fints get_balance() liefert ein mt940 Balance-aehnliches Objekt
    # mit .amount.amount (Money). Defensiv abgreifen.
    amt = getattr(balance, "amount", None)
    inner = getattr(amt, "amount", amt)
    return _to_jsonable(inner)


def _currency(balance) -> Optional[str]:
    amt = getattr(balance, "amount", None)
    cur = getattr(amt, "currency", None)
    return str(cur) if cur is not None else None


def _bal_date(balance) -> Optional[str]:
    d = getattr(balance, "date", None)
    return d.isoformat() if hasattr(d, "isoformat") else (str(d) if d else None)


def _serialize_tx(tx) -> dict[str, Any]:
    # mt940.models.Transaction: .data ist ein dict mit den Feldern.
    data = getattr(tx, "data", {}) or {}
    fields = (
        "date", "entry_date", "amount", "currency", "purpose",
        "applicant_name", "applicant_iban", "posting_text", "transaction_code",
    )
    out: dict[str, Any] = {}
    for f in fields:
        if f in data:
            val = data[f]
            # mt940 Amount-Objekt -> amount/currency
            if f == "amount" and hasattr(val, "amount"):
                out["amount"] = _to_jsonable(val.amount)
                out["currency"] = str(getattr(val, "currency", "")) or None
            else:
                out[f] = _to_jsonable(val)
    return out
