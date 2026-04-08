---
name: hermes-telegram-debug
description: Troubleshoot Telegram bot connectivity and messaging failures in Hermes Agent gateway.
category: dogfood
---

# Hermes Telegram Troubleshooting

Troubleshoot Telegram bot connectivity and messaging failures in Hermes Agent.

## Quick Diagnostic Checklist

1. **Is the gateway running?**
   ```bash
   ps aux | grep "hermes_cli.main gateway" | grep -v grep
   ```

2. **Is the bot token valid?** (MOST COMMON FAILURE MODE)
   ```bash
   cd ~/.hermes/hermes-agent && source venv/bin/activate
   python3 -c "
   from dotenv import load_dotenv; load_dotenv('/Users/fernando/.hermes/.env', override=True)
   import os, httpx
   token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
   resp = httpx.get(f'https://api.telegram.org/bot{token}/getMe', timeout=10)
   print(resp.json())
   "
   ```

3. **Is the bot actually receiving messages?**
   ```bash
   tail -30 ~/.hermes/logs/gateway.log
   
   # If "Unauthorized user" appears → user not in TELEGRAM_ALLOWED_USERS
   # If only HA errors → polling is likely fine
   ```

4. **Send a direct message via API (diagnostic only)**
   ```python
   from dotenv import load_dotenv; load_dotenv('/Users/fernando/.hermes/.env', override=True)
   import os, httpx
   token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
   # NOTE: chat_id MUST be numeric, NOT a username like "ferparra83"
   resp = httpx.post(
       f'https://api.telegram.org/bot{token}/sendMessage',
       json={"chat_id": "<numeric_chat_id>", "text": "test"},
       timeout=10
   )
   print(resp.status_code, resp.json())
   ```

## Common Issues & Fixes

### "getMe" returns `{"ok": false, "error_code": 401, "description": "Unauthorized"}`
- **Cause**: The bot token has been revoked, invalidated, or was never valid.
  This is different from a token that simply hasn't started polling yet.
- **Fix**: Generate a new token via `@BotFather` on Telegram:
  1. Open Telegram and chat with `@BotFather`
  2. Send `/newbot` and follow the prompts
  3. Copy the new token (format: `123456789:ABCdef...`)
  4. Update `~/.hermes/.env`: `TELEGRAM_BOT_TOKEN=your-new-token`
  5. Kill and restart the gateway (see "Restart" section below)

### "Command length must not exceed 32" during gateway startup
- **Cause**: One or more bot commands registered via `BotCommand` exceed Telegram's
  32-character limit. This prevents the `setMyCommands` API call from succeeding.
- **Fix**: Edit the gateway platform adapter (`gateway/platforms/telegram.py`) and
  shorten any command descriptions or names that exceed 32 characters.
  Then restart the gateway.

### "Unauthorized user" despite user being in TELEGRAM_ALLOWED_USERS
- **Cause**: Gateway process started before `.env` was updated — runs with stale env vars.
- **Fix**: Kill and restart the gateway cleanly (see "Restart" section).

### Bot polls but won't send messages — "chat not found"
- **Cause**: `TELEGRAM_HOME_CHANNEL` is set to a Telegram **username** (e.g. `ferparra83`)
  instead of a **numeric chat_id**. The Telegram Bot API `sendMessage` requires numeric IDs.
  Using a username works only if the bot previously interacted with that user AND the
  library resolves it internally.
- **Fix**: Set `TELEGRAM_HOME_CHANNEL` to the numeric chat_id (e.g. `6655521245`), not the username.

### Telegram fallback IPs active
- **Cause**: DNS can't resolve `api.telegram.org` → falls back to direct IP `149.154.167.220`.
- **Fix**: Usually harmless. Fix DNS if you want cleaner resolution.

### "Another Telegram bot poller is already using this token"
- **Cause**: Stale lock file or orphaned gateway process still holding the token.
- **Fix**: Kill all gateway processes and restart.

## Restarting the Gateway

After any `.env` change (token, allowed users, home channel), you MUST kill and restart
the gateway for the changes to take effect:

```bash
# Find and kill the gateway process
kill -9 $(ps aux | grep "hermes_cli.main gateway" | grep -v grep | awk '{print $2}')

# Restart it
cd ~/.hermes/hermes-agent && source venv/bin/activate
nohup python -m hermes_cli.main gateway run --replace > ~/.hermes/logs/gateway.log 2>&1 &

# Verify it started
sleep 2 && tail -5 ~/.hermes/logs/gateway.log
```

## Getting a Numeric Chat ID

```python
# Send a message to the bot first, then:
import os, httpx
from dotenv import load_dotenv
load_dotenv(override=True)
token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
resp = httpx.get(f'https://api.telegram.org/bot{token}/getUpdates', timeout=10)
updates = resp.json().get('result', [])
for u in updates:
    msg = u.get('message', {})
    print(f"chat_id: {msg.get('chat',{}).get('id')} | username: {msg.get('chat',{}).get('username')}")
```

## Auth Allowlist Format
`TELEGRAM_ALLOWED_USERS` in `.env` takes **numeric user IDs** (e.g. `6655521245`), NOT Telegram usernames. Get numeric IDs from the `getUpdates` response above.
