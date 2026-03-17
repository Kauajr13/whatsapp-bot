# whatsapp-bot

Automated WhatsApp response system. Connects a WhatsApp number via QR code and automatically replies to incoming messages based on configurable rules or AI-generated responses (Gemini).

Includes a web management panel to add rules, configure messages, set business hours, and monitor conversations — no code changes needed after setup.

## Architecture

```
bridge/     Node.js + Baileys   — WhatsApp connection and message routing
backend/    Python + FastAPI    — response engine, rules, REST API
frontend/   HTML/JS             — web management panel
data/       SQLite              — messages, rules, config (auto-created)
auth/       Baileys session     — WhatsApp credentials (auto-created, gitignored)
```

Message flow: `WhatsApp → Bridge → Backend → Rules/AI → Bridge → WhatsApp`

## Requirements

- Python 3.11+
- Node.js 18+
- Gemini API key (free at https://aistudio.google.com/apikey)

## Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY='your-key'
uvicorn main:app --reload
```

**Bridge (separate terminal):**
```bash
cd bridge
npm install
node index.js
# scan the QR code with WhatsApp > Linked Devices > Link a Device
```

Panel available at `http://localhost:8000/app`

## How it works

When a message arrives, the bot runs through this decision chain:

1. Outside business hours → sends the off-hours message
2. Matches a configured rule → sends the rule's response
3. No rule matched → Gemini generates a context-aware reply
4. Gemini unavailable → sends the fallback message

Rules are checked by priority (higher number = checked first). The AI uses the last 6 messages of conversation history for context.

## Filtering who the bot responds to

Edit `bridge/index.js`:

```js
// Options: 'all' | 'whitelist' | 'groups_only' | 'contacts_only'
const MODE = 'whitelist'

const WHITELIST = new Set([
    '1212353245346436467356@g.us',      // group
    '1834444634645624@lid',           // individual contact (modern WhatsApp)
])
```

### Finding the correct JID

WhatsApp uses two JID formats depending on account type:

- **`@s.whatsapp.net`** — older accounts or accounts without linked devices
- **`@lid`** — accounts using WhatsApp's multi-device protocol (most modern accounts)

The only reliable way to find someone's JID is to enable debug logging temporarily:

```js
// in index.js, add this inside messages.upsert before any filters:
console.log(`[DEBUG] fromMe=${msg.key.fromMe} jid=${msg.key.remoteJid}`)
```

Set `MODE = 'all'`, restart the bridge, ask the person to send a message, copy the exact JID from the log, add it to the whitelist, and set MODE back.

### Bot prefix

To only respond to messages starting with a specific command:

```js
const BOT_PREFIX = '/bot'   // only responds to messages starting with /bot
const BOT_PREFIX = null     // responds to all messages
```

When a prefix is set, it is stripped before the message reaches the backend. So `/bot what time is it?` becomes `what time is it?` in the backend.

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | /webhook/message | Receive message from bridge |
| GET | /api/rules | List all rules |
| POST | /api/rules | Create rule |
| PUT | /api/rules/{id} | Update rule |
| DELETE | /api/rules/{id} | Delete rule |
| GET | /api/config | Get all config |
| POST | /api/config | Update config |
| GET | /api/stats | Message statistics |
| GET | /api/history/{phone} | Conversation history |

## Troubleshooting

**`Bad MAC` / `Failed to decrypt` errors in terminal**
These are Baileys internal decryption errors for messages from contacts outside the whitelist or with stale session keys. They do not affect functionality. The bridge suppresses them automatically.

If they persist after messages stop arriving correctly, delete the session and reconnect:
```bash
rm -rf auth/
node index.js
```

**Bot not responding to a contact**
The most common cause is a JID mismatch. Modern WhatsApp accounts use `@lid` format, not `@s.whatsapp.net`. Enable debug logging (see above) to confirm the exact JID arriving for that contact.

**`Response: ""` from backend**
Either the Gemini API key is not set in the terminal running uvicorn, or `ai_fallback` is disabled in the panel settings. Check:
```bash
echo $GEMINI_API_KEY
```

**`Connection closed (code: 515)` loop**
Normal reconnect behavior after a dropped connection. The bridge reconnects automatically. If it loops indefinitely, delete `auth/` and reconnect.

**Bot responds to its own messages**
Remove `if (msg.key.fromMe) continue` from the bridge only if you need this. Without it, the bot will create an infinite loop responding to itself unless a prefix is configured.

## Notes

- Session stored in `auth/` — keep it out of version control
- To reconnect with a different number: `rm -rf auth/` then restart the bridge
- Uses Baileys (WhatsApp Web protocol) — for production consider the official WhatsApp Business API
- `data/bot.db` is created automatically on first run

See [GUIDE.md](GUIDE.md) for detailed usage instructions.

## Author

Kauã Jr — [github.com/Kauajr13](https://github.com/Kauajr13)
