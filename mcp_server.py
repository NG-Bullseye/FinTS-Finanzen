#!/usr/bin/env python3
"""Read-only MCP-Server fuer FinTS/HBCI-Banking via PIN-TAN.

Stellt Finanzueberblick bereit: Konten, Saldo, Umsaetze.
STRIKT read-only — keine Ueberweisungen.

Transport: stdio.  Tools: accounts, balance, transactions, summary.
Fehlerfaelle (kein Enroll, fehlender Key, TAN noetig) werden als klarer
Fehler-String zurueckgegeben, NICHT als Crash.

Bank wird via FINTS_BANK_CODE / FINTS_ENDPOINT konfiguriert (Default: DKB).
"""
from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

import fints_client
from crypto import MasterKeyError

mcp = FastMCP(
    name="fints-finanzen",
    instructions=(
        "Read-only Zugriff auf FinTS/HBCI-Banking. "
        "Tools: accounts (Konten auflisten), balance (Saldo), "
        "transactions (Umsaetze der letzten N Tage), summary (alle Salden). "
        "Kein Schreibzugriff, keine Ueberweisungen."
    ),
)


def _guard(fn):
    """Wandle erwartete Fehler in lesbare Tool-Fehlermeldungen statt Crash."""
    try:
        return {"ok": True, "data": fn()}
    except fints_client.EnrollmentRequired as exc:
        return {"ok": False, "error": "not_enrolled", "message": str(exc)}
    except fints_client.ReenrollmentRequired as exc:
        return {"ok": False, "error": "tan_required", "message": str(exc)}
    except MasterKeyError as exc:
        return {"ok": False, "error": "master_key", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 - nie crashen, Bank-/Netzfehler melden
        return {"ok": False, "error": "fints_error", "message": str(exc) or exc.__class__.__name__}


@mcp.tool()
def accounts() -> dict:
    """Liste aller Konten der konfigurierten Bank (IBAN, Kontonummer, BIC)."""
    return _guard(fints_client.list_accounts)


@mcp.tool()
def balance(iban_or_account: Optional[str] = None) -> dict:
    """Aktueller Saldo eines Kontos.

    iban_or_account: IBAN oder Kontonummer. Leer -> erstes Konto.
    """
    return _guard(lambda: fints_client.get_balance(iban_or_account))


@mcp.tool()
def transactions(days: int = 30, account: Optional[str] = None) -> dict:
    """Umsaetze der letzten `days` Tage.

    account: IBAN oder Kontonummer. Leer -> erstes Konto.
    """
    return _guard(lambda: fints_client.get_transactions(days, account))


@mcp.tool()
def summary() -> dict:
    """Kompakter Ueberblick: alle Konten + Salden in einem Aufruf."""
    return _guard(fints_client.summary)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
