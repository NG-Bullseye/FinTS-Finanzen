# FinTS-Finanzen

**Read-only MCP server for German banks via FinTS/HBCI — accounts, balances, and transactions over PIN/TAN.**

To our knowledge, this is the only MCP server for the FinTS/HBCI protocol — the standard online-banking interface supported by virtually every German bank. It gives an LLM a safe, read-only window into your bank accounts: no transfer code exists anywhere in this codebase.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)

🇩🇪 [Deutsche Version](README.de.md)

## Features

MCP tools exposed over stdio (via FastMCP):

| Tool | Description |
|---|---|
| `accounts()` | List all accounts (IBAN, account number, BIC) |
| `balance(iban_or_account=None)` | Current balance of one account (empty → first account) |
| `transactions(days=30, account=None)` | Transactions of the last `days` days |
| `summary()` | All accounts + balances in a single call |

- **Strictly read-only** — the wrapper around `python-fints` only implements account listing, balances, and transaction retrieval. There is no code for transfers or any other write operation.
- **Any FinTS bank** — defaults to DKB (`12030000`), switchable to any other FinTS-capable bank via `FINTS_BANK_CODE` / `FINTS_ENDPOINT`.
- **Graceful errors** — expected failure modes (not enrolled, missing master key, TAN required, bank/network errors) are returned as structured tool errors (`{"ok": false, "error": "...", "message": "..."}`), never as crashes.
- **~90 days TAN-free reads** — after a one-time interactive pushTAN enrollment, the persisted FinTS client state keeps read access TAN-free under the PSD2 SCA exemption (~90 days). When it expires, tools return a `tan_required` error and you simply re-run `enroll.py`.

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/NG-Bullseye/FinTS-Finanzen.git
cd FinTS-Finanzen
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 1. Generate a master key (one-time)

```bash
cp .env.example .env
.venv/bin/python -c "import crypto; print(crypto.generate_key())"
# put the output into .env as FINTS_MASTER_KEY
```

(`enroll.py` can also generate and display a key for you.)

### 2. Enroll (one-time, interactive)

```bash
set -a; . ./.env; set +a          # load FINTS_MASTER_KEY into the environment
.venv/bin/python enroll.py
```

The enrollment asks for your online-banking login name (not the account number) and PIN, walks through the bank's pushTAN flow (including decoupled app-based approval), and — only on success — stores the PIN encrypted plus the FinTS client state.

### 3. Register the MCP server

The server runs over **stdio**. Example MCP configuration (`FINTS_MASTER_KEY` must be set in the server's environment) — use absolute paths, MCP clients do not launch servers from the repo directory. Prefer exporting `FINTS_MASTER_KEY` in the client's environment over writing it into this file:

```json
{
  "mcpServers": {
    "fints-finanzen": {
      "command": "/absolute/path/to/FinTS-Finanzen/.venv/bin/python",
      "args": ["/absolute/path/to/FinTS-Finanzen/mcp_server.py"],
      "env": {
        "FINTS_MASTER_KEY": "<base64-32-byte-key>",
        "FINTS_BANK_CODE": "12030000",
        "FINTS_PRODUCT_ID": ""
      }
    }
  }
}
```

## Configuration

All configuration is via environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `FINTS_MASTER_KEY` | — (required) | Base64-encoded 32-byte AES-256-GCM key used to encrypt/decrypt the stored credentials |
| `FINTS_BANK_CODE` | `12030000` (DKB) | Bank code (BLZ) of your bank |
| `FINTS_ENDPOINT` | `https://fints.dkb.de/fints` | FinTS endpoint URL of your bank |
| `FINTS_PRODUCT_ID` | public default from `config.py` | FinTS product ID. Empty uses a public ID reported working with DKB ([python-fints#183](https://github.com/raphaelm/python-fints/issues/183)). For a clean, permanent setup, register your own ID with the Deutsche Kreditwirtschaft ([fints.org product registration](https://www.fints.org/de/hersteller/produktregistrierung)) |

## Security model — honest description

How your bank credentials are actually handled (verifiable in `crypto.py`, `config.py`, `fints_client.py`):

- **Encryption at rest.** Your login name and PIN are stored AES-256-GCM-encrypted (12-byte random nonce per encryption, prepended to the ciphertext) in `~/.config/fints-finanzen/credentials.enc`. The FinTS client state (system ID, BPD/UPD) is stored alongside as `fints_state.bin`. Directory mode `0700`, file mode `0600`. Nothing sensitive is inside the repo directory, and `.gitignore` keeps `.env` out of git.
- **The key lives only in the environment.** The AES key comes exclusively from the `FINTS_MASTER_KEY` environment variable — it is never written to disk by this project. Without it, the stored credentials are unreadable. Flip side, stated plainly: whoever has both the key (e.g. from your MCP config file or process environment) and `credentials.enc` can decrypt your PIN. Protect your MCP configuration accordingly.
- **PIN in memory at runtime.** To talk to the bank, the server necessarily decrypts the PIN in process memory for each FinTS dialog. It is never logged or returned by any tool.
- **Read-only by construction.** The FinTS wrapper implements only `get_sepa_accounts`, `get_balance`, and `get_transactions`. Even a fully compromised LLM session cannot initiate transfers through this server, because the code for it does not exist.
- **PIN entry only in `enroll.py`.** The PIN is read via `getpass` (no echo) in the interactive enrollment; the MCP server itself never asks for or accepts credentials.

## License

[MIT](LICENSE)
