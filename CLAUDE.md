# FinTS-Finanzen — LLM-Pointer

> Eigenstaendiges Repo (kein cortex-Teil), kein GitHub-Remote, rein lokal.
> System-Brief: `AGENTS.md`. Gesamtsystem-Kanon: `~/cortex/CLAUDE.md`.

## Was es ist
Read-only MCP-Server, der Leos DKB-Konto via FinTS/HBCI PIN-TAN ausliest (Konten, Saldo, Umsaetze). Gibt Cortex permanenten Finanzueberblick. **STRIKT read-only — kein Schreib-/Ueberweisungs-Code.**

## Dateien
| Datei | Funktion |
|---|---|
| `config.py` | Pfade, Bank-Konstanten (BLZ `12030000`, Endpoint), Env-Var-Namen, `product_id()` |
| `crypto.py` | AES-256-GCM `encrypt`/`decrypt`/`generate_key`, Key aus `FINTS_MASTER_KEY` |
| `fints_client.py` | duenner Wrapper um `FinTS3PinTanClient`: `list_accounts`/`get_balance`/`get_transactions`/`summary`, State-Persistenz |
| `enroll.py` | interaktive CLI (NUR Leo): Key gen, Login + pushTAN, PIN+State persistieren |
| `mcp_server.py` | FastMCP stdio-Server, Tools `accounts`/`balance`/`transactions`/`summary` |

## Secret-Modell
- PIN NIE im Klartext/Repo/git. AES-256-GCM, 12-Byte-Nonce vor Ciphertext.
- Key = `FINTS_MASTER_KEY` (base64 32 Byte) aus Env.
- Secrets + FinTS-State unter `~/.config/fints-finanzen/` (`0o700` Dir, `0o600` Files): `credentials.enc`, `fints_state.bin`.

## PSD2-Realitaet (Kern-Feature)
Erster Login braucht pushTAN. Danach wird `client.deconstruct(including_private=True)` persistiert und via `from_data=` reingeladen → Lesezugriffe ~90 Tage TAN-frei. Danach meldet der Server `tan_required` → `enroll.py` erneut.

## Installierte API (fints 5.0.0)
`FinTS3PinTanClient(bank_identifier, user_id, pin, server, customer_id=, product_id=, from_data=)` · `get_sepa_accounts()` · `get_balance(acc)` · `get_transactions(acc, start_date, end_date)` · `deconstruct(including_private=True)` / `set_data(blob)` · TAN: `get_tan_mechanisms`/`set_tan_mechanism`/`get_tan_media`/`set_tan_medium`/`send_tan`. **`product_id` ist mandatory** (sonst TypeError) → `config.DEFAULT_PRODUCT_ID` als Fallback.

## Betrieb
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python enroll.py          # NUR Leo, einmalig + alle ~90 Tage
.venv/bin/python mcp_server.py      # stdio MCP
```
