# whatsapp-bot

Automated WhatsApp response system with rule-based matching, AI fallback via Gemini, and a web management panel.

## Architecture

```
bridge/     Node.js + Baileys   — WhatsApp connection, QR auth
backend/    Python + FastAPI     — bot logic, rules engine, REST API
frontend/   HTML/JS              — management panel
data/       SQLite               — messages, rules, config
auth/       Baileys session      — WhatsApp credentials (gitignored)
```

**Message flow:** WhatsApp → Bridge (Node) → Backend (Python) → Rules + AI → Response → Bridge → WhatsApp

## Setup (without Docker)

**Backend:**
```bash
cd backend
pip install -r requirements.txt
export GEMINI_API_KEY='your-key'
uvicorn main:app --reload
```

**Bridge:**
```bash
cd bridge
npm install
node index.js
# scan the QR code with your WhatsApp
```

**Panel:**
Open `frontend/index.html` in your browser.

## Setup (with Docker)

```bash
cp .env.example .env
# fill in GEMINI_API_KEY in .env
docker-compose up -d
docker-compose logs -f bridge  # scan the QR code here
```

## How it works

1. A message arrives on WhatsApp
2. Bridge forwards it to the backend via HTTP
3. Backend checks: is it business hours?
4. If outside hours → sends the off-hours message
5. If inside hours → classifies intent (greeting, bye, etc.)
6. Checks user-configured rules (keyword matching)
7. If no rule matches → calls Gemini for a context-aware response
8. Response goes back to bridge → sent via WhatsApp

## Management panel

Access at `http://localhost:8000/app`

- **Responses tab:** add/edit/pause keyword-triggered rules
- **Settings tab:** configure bot name, messages, business hours, AI toggle

## API endpoints

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
| GET | /api/history/{phone} | Chat history by phone |

## Notes

- Uses Baileys (unofficial WhatsApp client) — same protocol as WhatsApp Web
- For production use, consider WhatsApp Business API for official support
- Auth session stored in `auth/` — keep this folder safe and out of version control
- AI responses use conversation history (last 6 messages) for context

## Author

Kauã Jr — [github.com/Kauajr13](https://github.com/Kauajr13)
