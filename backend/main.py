import logging
import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from database import (
    init_db, get_rules, upsert_rule, delete_rule,
    get_config, set_config, get_stats, get_history
)
from bot import process_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


@app.on_event("startup")
def startup():
    init_db()
    logger.info("Database initialized")


# ── Webhook recebido do bridge Node.js ───────────────────────────

class IncomingMessage(BaseModel):
    phone: str
    message: str
    name: Optional[str] = None


@app.post("/webhook/message")
def webhook(payload: IncomingMessage):
    logger.info(f"Message from {payload.phone}: {payload.message[:80]}")
    context = {"sender_name": payload.name}
    response = process_message(payload.phone, payload.message, context)
    return {"phone": payload.phone, "response": response}


# ── Regras ───────────────────────────────────────────────────────

class Rule(BaseModel):
    id: Optional[int] = None
    trigger: str
    response: str
    match_type: str = "contains"
    active: bool = True
    priority: int = 0


@app.get("/api/rules")
def list_rules():
    return get_rules(active_only=False)


@app.post("/api/rules")
def create_rule(rule: Rule):
    rule_id = upsert_rule(rule.dict())
    return {"id": rule_id}


@app.put("/api/rules/{rule_id}")
def update_rule(rule_id: int, rule: Rule):
    rule.id = rule_id
    upsert_rule(rule.dict())
    return {"ok": True}


@app.delete("/api/rules/{rule_id}")
def remove_rule(rule_id: int):
    delete_rule(rule_id)
    return {"ok": True}


# ── Configurações ─────────────────────────────────────────────────

@app.get("/api/config")
def get_all_config():
    return get_config()


@app.post("/api/config")
def update_config(data: dict):
    for key, value in data.items():
        set_config(key, str(value))
    return {"ok": True}


# ── Histórico e stats ─────────────────────────────────────────────

@app.get("/api/stats")
def stats():
    return get_stats()


@app.get("/api/history/{phone}")
def history(phone: str, limit: int = 50):
    return get_history(phone, limit)


@app.get("/api/health")
def health():
    return {"status": "ok"}
