# ARCHITECTURE — FinTS-Finanzen

## Deep Modules — read-only MCP server für FinTS/HBCI

Flow: einmalig `enroll.py` (PIN + pushTAN → verschlüsselte Credentials + FinTS-State), danach beantwortet `mcp_server.py` Tool-Calls über stdio, jeder Call baut einen FinTS-Client aus dem gespeicherten State. Die Sequenz lebt in `fints_client.py::build_client`. Jede Innenleben-Zelle ist datei:zeile und muss per grep -n treffen.

## Flow

**Sequenz**

| # | Modul | Eingang | Ausgang | Bedingung | Stellschraube | Innenleben |
|---|---|---|---|---|---|---|
| 1 | Enrollment | Login, PIN (getpass), pushTAN | `credentials.enc`, `fints_state.bin` | einmalig / nach ~90 Tagen | `FINTS_BANK_CODE` | enroll.py:147 `def main` |
| 2 | Crypto | `FINTS_MASTER_KEY` | AES-256-GCM encrypt/decrypt | Key gesetzt | `FINTS_MASTER_KEY` | crypto.py:52 `def encrypt` |
| 3 | Client | Credentials + State | `FinTS3PinTanClient` | enrolled | `FINTS_ENDPOINT`, `FINTS_PRODUCT_ID` | fints_client.py:83 `def build_client` |
| 4 | Read | Client | Konten, Saldo, Umsätze | keine TAN nötig | `days` | fints_client.py:172 `def get_transactions` |
| 5 | MCP | Tool-Call (stdio) | JSON oder `{"ok": false, ...}` | — | — | mcp_server.py:33 `def _guard` |

**Parallel**

| Modul | Eingang | Ausgang | Bedingung | Stellschraube | Innenleben |
|---|---|---|---|---|---|
| TAN-Guard | FinTS-Antwort | `ReenrollmentRequired` → `tan_required` | TAN verlangt | — | fints_client.py:129 `def _guard_tan` |

## Schnittstellen

- MCP-Tools `accounts`, `balance`, `transactions`, `summary` (mcp_server.py:48 `def accounts`).
- Ablage `~/.config/fints-finanzen/` Modus 0700/0600 (config.py:34 `CONFIG_DIR`).
- Kein Schreib-Pfad zur Bank: nur `get_sepa_accounts`, `get_balance`, `get_transactions`.

## Standard: Deep Modules + Flow

Standard R1–R5 steht in `~/repos/speech-engine/ARCHITECTURE.md`.
