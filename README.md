# FinTS-Finanzen

**Read-only MCP-Server** fuer FinTS/HBCI-Banking via PIN-TAN — Konten, Saldo, Umsaetze.

**Strikt read-only.** Es gibt keinen Code fuer Ueberweisungen oder sonstige Schreibzugriffe.

Standard-Bank ist DKB (`12030000`), ueber Env-Vars auf jede andere FinTS-Bank umstellbar.

## Was es kann

MCP-Tools ueber stdio:

| Tool | Beschreibung |
|---|---|
| `accounts()` | Alle Konten (IBAN, Kontonummer, BIC) |
| `balance(iban_or_account=None)` | Aktueller Saldo (leer → erstes Konto) |
| `transactions(days=30, account=None)` | Umsaetze der letzten `days` Tage |
| `summary()` | Alle Konten + Salden kompakt in einem Aufruf |

## Sicherheit / Secret-Modell

- Die **PIN landet nie im Klartext** auf Platte, nie im Repo, nie im git.
- Verschluesselung: **AES-256-GCM** (`cryptography`), 12-Byte-Nonce pro Verschluesselung vor dem Ciphertext.
- Der Schluessel kommt aus der Env-Var `FINTS_MASTER_KEY` (base64-kodierte 32 Byte). Ohne diesen Schluessel sind die gespeicherten Credentials unbrauchbar.
- Verschluesselte Credentials und der FinTS-State liegen unter `~/.config/fints-finanzen/` (`credentials.enc`, `fints_state.bin`), Verzeichnis `0o700`, Dateien `0o600`. Nichts davon ist im Repo.

## PSD2-SCA-Exemption (~90 Tage)

Lesen ist **nicht TAN-frei**. Beim **ersten Login** verlangt die Bank eine **pushTAN-Freigabe**. `enroll.py` fuehrt diesen Flow interaktiv durch und serialisiert danach den FinTS-Client-State (`system_id`, BPD/UPD) via `client.deconstruct(including_private=True)`. Dieser State wird beim naechsten Lauf wieder geladen — dann bleiben Lesezugriffe dank **PSD2 SCA-Exemption ~90 Tage TAN-frei**.

Nach Ablauf der ~90 Tage meldet der MCP-Server `tan_required` (Tool-Fehler, kein Crash) — dann einfach `enroll.py` erneut ausfuehren (Reenrollment).

## Setup

```bash
cd FinTS-Finanzen
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Master-Key erzeugen und eintragen** (einmalig):

```bash
cp .env.example .env
.venv/bin/python -c "import crypto; print(crypto.generate_key())"
# Ausgabe als FINTS_MASTER_KEY in .env eintragen
```

Alternativ bietet `enroll.py` an, den Key zu generieren und anzuzeigen.

**Enroll (interaktiv):**

```bash
set -a; . ./.env; set +a          # FINTS_MASTER_KEY in die Umgebung laden
.venv/bin/python enroll.py
```

Der Enroll fragt Anmeldename (nicht Kontonummer) und PIN ab, fuehrt den pushTAN-Flow durch und speichert PIN verschluesselt + Client-State.

> **`FINTS_PRODUCT_ID` / product_id:** Leer lassen nutzt den Default aus `config.py` — eine oeffentliche, in [python-fints#183](https://github.com/raphaelm/python-fints/issues/183) mehrfach als DKB-akzeptiert belegte ID. Die DKB lehnt **ungueltige** product_ids bereits bei der Dialog-Initialisierung ab. Wer sauber/dauerhaft fahren will, registriert eine **eigene** ID bei der Deutschen Kreditwirtschaft ([fints.org Produktregistrierung](https://www.fints.org/de/hersteller/produktregistrierung), Formular an `registrierung@hbci-zka.de`, ~5–10 Werktage) und setzt sie via `FINTS_PRODUCT_ID`.

## Andere Bank nutzen

Per Env-Vars umstellbar:

```bash
export FINTS_BANK_CODE="12345678"              # BLZ deiner Bank
export FINTS_ENDPOINT="https://fints.meine-bank.de/fints"
```

## MCP registrieren

Der Server laeuft ueber **stdio**. Eintrag in der MCP-Config (`FINTS_MASTER_KEY` muss in der Server-Umgebung gesetzt sein):

```json
{
  "mcpServers": {
    "fints-finanzen": {
      "command": "./.venv/bin/python",
      "args": ["mcp_server.py"],
      "env": {
        "FINTS_MASTER_KEY": "<base64-32-byte-key>",
        "FINTS_BANK_CODE": "12030000",
        "FINTS_PRODUCT_ID": ""
      }
    }
  }
}
```

## Dateien

`config.py` (Pfade/Konstanten) · `crypto.py` (AES-GCM) · `fints_client.py` (FinTS-Wrapper) · `enroll.py` (interaktiver Enroll) · `mcp_server.py` (FastMCP stdio).

## Lizenz

MIT License — siehe `LICENSE`.
