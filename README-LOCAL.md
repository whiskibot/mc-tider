# MC Slot Monitor — Lokal version (Mac/Windows)

Denna version körs på **din egen dator** (inte på servern). Du loggar in manuellt med BankID en gång, och scriptet poll:ar lediga tider i bakgrunden.

## Installation

### 1. Installera Python 3.9+
Se till att du har Python installerat:
```bash
python3 --version
```

### 2. Installera beroenden
```bash
cd mc-slot-monitor
pip install -r requirements.txt
playwright install chromium
```

### 3. Konfigurera Telegram
Skapa en bot och få token:
1. Öppna [@BotFather](https://t.me/botfather) i Telegram
2. Skriv `/newbot` och följ instruktionerna
3. Kopiera token (t.ex. `123456:ABC-DEF...`)

Sätt miljövariabel:
```bash
# Mac/Linux
export TELEGRAM_BOT_TOKEN="din-token-här"

# Windows PowerShell
$env:TELEGRAM_BOT_TOKEN="din-token-här"
```

### 4. Kör scriptet
```bash
python mc-monitor-local.py
```

## Så här fungerar det

1. **Chrome öppnas** med Trafikverkets bokningssida
2. **Du loggar in** med BankID (manuellt, som vanligt)
3. **Scriptet väntar** tills du är inloggad
4. **Automatisk sökning** startas — letar A körprov på dina orter
5. **Notifiering** skickas till Telegram-gruppen "Mc tider" när tid hittas

## Första körning

```
🛵  MC Slot Monitor — Lokal version
============================================================
Orter: Mjölby, Linköping, Örebro, Norrköping, Jönköping
Datum: 2026-06-15 → 2026-07-31
Intervall: var 5e minut
============================================================

🌐 Öppnar Trafikverkets bokningssida...
🔍 Kollar inloggningsstatus...
🔐 Inte inloggad — väntar på BankID

============================================================
🔐  LOGGA IN MED BANKID
============================================================
1. Klicka på 'Logga in med BankID' i webbläsaren
2. Öppna BankID-appen och godkänn
3. Vänta tills du är inloggad på sidan
4. Scriptet fortsätter automatiskt (timeout: 300s)
============================================================
```

## Viktigt

- **Låt Chrome vara öppet** — scriptet behöver webbläsaren
- **BankID-session** håller vanligtvis i 30 minuter
- Om du blir utloggad — scriptet pausar och väntar på ny inloggning
- **Ctrl+C** för att avsluta

## Konfiguration

Redigera `CONFIG` i början av `mc-monitor-local.py`:

```python
CONFIG = {
    "locations": ["Mjölby", "Linköping", "Örebro", "Norrköping", "Jönköping"],
    "date_window": {
        "start": "2026-06-15",
        "end": "2026-07-31"
    },
    "telegram": {
        "bot_token": "",  # Sätt via TELEGRAM_BOT_TOKEN env var
        "chat_id": "-5067205563"  # Mc tider
    },
    "poll_interval_minutes": 5,
    "headless": False,  # Sätt True för att dölj webbläsare (ej rekommenderat)
}
```
