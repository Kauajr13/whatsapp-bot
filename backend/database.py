import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "bot.db"


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                phone       TEXT NOT NULL,
                direction   TEXT NOT NULL CHECK(direction IN ('in', 'out')),
                content     TEXT NOT NULL,
                intent      TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS rules (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger     TEXT NOT NULL,
                response    TEXT NOT NULL,
                match_type  TEXT NOT NULL DEFAULT 'contains',
                active      INTEGER NOT NULL DEFAULT 1,
                priority    INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS config (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_phone ON messages(phone);
            CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
        """)

        defaults = {
            "bot_name": "Assistente",
            "off_hours_message": "Obrigado pelo contato! Nosso horário de atendimento é de segunda a sexta, das 9h às 18h. Retornaremos em breve.",
            "greeting_message": "Olá! Como posso ajudar?",
            "unknown_message": "Não entendi sua mensagem. Pode reformular?",
            "business_hours_start": "09:00",
            "business_hours_end": "18:00",
            "business_days": "0,1,2,3,4",
            "ai_enabled": "true",
            "ai_fallback": "true",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO config(key, value) VALUES (?, ?)",
                (key, value)
            )


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_message(phone: str, direction: str, content: str, intent: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages(phone, direction, content, intent) VALUES (?, ?, ?, ?)",
            (phone, direction, content, intent)
        )


def get_history(phone: str, limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE phone = ? ORDER BY created_at DESC LIMIT ?",
            (phone, limit)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_rules(active_only: bool = True) -> list[dict]:
    with get_conn() as conn:
        query = "SELECT * FROM rules"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY priority DESC"
        return [dict(r) for r in conn.execute(query).fetchall()]


def upsert_rule(rule: dict) -> int:
    with get_conn() as conn:
        if rule.get("id"):
            conn.execute(
                "UPDATE rules SET trigger=?, response=?, match_type=?, active=?, priority=? WHERE id=?",
                (rule["trigger"], rule["response"], rule.get("match_type", "contains"),
                 int(rule.get("active", True)), rule.get("priority", 0), rule["id"])
            )
            return rule["id"]
        else:
            cur = conn.execute(
                "INSERT INTO rules(trigger, response, match_type, active, priority) VALUES (?, ?, ?, ?, ?)",
                (rule["trigger"], rule["response"], rule.get("match_type", "contains"),
                 int(rule.get("active", True)), rule.get("priority", 0))
            )
            return cur.lastrowid


def delete_rule(rule_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))


def get_config() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_config(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config(key, value) VALUES (?, ?)",
            (key, value)
        )


def get_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE date(created_at) = date('now')"
        ).fetchone()[0]
        unique_phones = conn.execute(
            "SELECT COUNT(DISTINCT phone) FROM messages"
        ).fetchone()[0]
        by_intent = conn.execute(
            "SELECT intent, COUNT(*) as count FROM messages WHERE intent IS NOT NULL GROUP BY intent"
        ).fetchall()
    return {
        "total_messages": total,
        "messages_today": today,
        "unique_contacts": unique_phones,
        "by_intent": {r["intent"]: r["count"] for r in by_intent},
    }
