# FinTS-Finanzen

Ein **read-only MCP-Server**, der Leos **DKB-Konto** via FinTS/HBCI PIN-TAN ausliest — Konten, Saldo, Umsätze — und Cortex damit permanenten Finanzüberblick gibt.

**Strikt read-only.** Es gibt keinen Code für Überweisungen oder sonstige Schreibzugriffe.

## Was es kann
MCP-Tools über stdio:

| Tool | Beschreibung |
|---|---|
| `accounts()` | alle DKB-Konten (IBAN, Kontonummer, BIC) |
| `balance(iban_or_account=None)` | aktueller Saldo (leer → erstes Konto) |
| `transactions(days=30, account=None)` | Umsätze der letzten `days` Tage |
| `summary()` | alle Konten + Salden kompakt in einem Aufruf |

## Sicherheit / Secret-Modell
- Die **PIN landet nie im Klartext** auf Platte, nie im Repo, nie im git.
- Verschlüsselung: **AES-256-GCM** (`cryptography`), 12-Byte-Nonce pro Verschlüsselung vor dem Ciphertext.
- Der Schlüssel kommt aus der Env-Var `FINTS_MASTER_KEY` (base64-kodierte 32 Byte). Ohne diesen Schlüssel sind die gespeicherten Credentials unbrauchbar.
- Verschlüsselte Credentials und der FinTS-State liegen unter `~/.config/fints-finanzen/` (`credentials.enc`, `fints_state.bin`), Verzeichnis `0o700`, Dateien `0o600`. Nichts davon ist im Repo.

## Die PSD2-90-Tage-Realität (wichtig)
Lesen ist **nicht TAN-frei**. Beim **ersten Login** verlangt die DKB eine **pushTAN-Freigabe** (DKB-App). `enroll.py` führt diesen Flow interaktiv durch und serialisiert danach den FinTS-Client-State (`system_id`, BPD/UPD) via `client.deconstruct(including_private=True)`. Dieser State wird beim nächsten Lauf wieder geladen — dann bleiben Lesezugriffe dank **PSD2 SCA-Exemption ~90 Tage TAN-frei**.

Nach Ablauf der ~90 Tage meldet der MCP-Server `tan_required` (Tool-Fehler, kein Crash) — dann einfach `enroll.py` erneut ausführen (Reenrollment).

## Setup
```bash
cd ~/repos/FinTS-Finanzen
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

**Enroll (nur Leo, interaktiv):**
```bash
set -a; . ./.env; set +a          # FINTS_MASTER_KEY in die Umgebung laden
.venv/bin/python enroll.py
```
Der Enroll fragt Anmeldename (nicht Kontonummer) und PIN ab, führt den pushTAN-Flow durch und speichert PIN verschlüsselt + Client-State.

> **`FINTS_PRODUCT_ID` / product_id (wichtig für DKB):** Leer lassen nutzt den Default aus `config.py` — eine öffentliche, in [python-fints#183](https://github.com/raphaelm/python-fints/issues/183) mehrfach als DKB-akzeptiert belegte ID. DKB lehnt **ungültige** product_ids bereits bei der Dialog-Initialisierung ab (`9210`/`9800`/`9050`, **vor** jeder TAN-Abfrage). Wer sauber/dauerhaft fahren will, registriert eine **eigene** ID bei der Deutschen Kreditwirtschaft ([fints.org Produktregistrierung](https://www.fints.org/de/hersteller/produktregistrierung), Formular an `registrierung@hbci-zka.de`, ~5–10 Werktage) und setzt sie via `FINTS_PRODUCT_ID`. Öffentliche IDs werden nur geduldet und können gesperrt werden.

## MCP registrieren
Der Server läuft über **stdio**. Eintrag in der MCP-Config (Pfade absolut, `FINTS_MASTER_KEY` muss in der Server-Umgebung gesetzt sein):
```json
{
  "mcpServers": {
    "fints-finanzen": {
      "command": "/home/leona/repos/FinTS-Finanzen/.venv/bin/python",
      "args": ["/home/leona/repos/FinTS-Finanzen/mcp_server.py"],
      "env": {
        "FINTS_MASTER_KEY": "<base64-32-byte-key>",
        "FINTS_PRODUCT_ID": ""
      }
    }
  }
}
```

## Dateien
`config.py` (Pfade/Konstanten) · `crypto.py` (AES-GCM) · `fints_client.py` (FinTS-Wrapper) · `enroll.py` (interaktiver Enroll) · `mcp_server.py` (FastMCP stdio).
