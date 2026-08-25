import sqlite3
import secrets
import time
from contextlib import contextmanager

from config import DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                name TEXT,
                is_senior INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            );

            -- Связь "дедушка -> родственник", родственников может быть несколько
            CREATE TABLE IF NOT EXISTS links (
                senior_id INTEGER NOT NULL,
                family_id INTEGER NOT NULL,
                PRIMARY KEY (senior_id, family_id)
            );

            -- Одноразовые коды для привязки родственника к дедушке
            CREATE TABLE IF NOT EXISTS link_codes (
                code TEXT PRIMARY KEY,
                senior_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                senior_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                hour INTEGER NOT NULL,
                minute INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                last_sent_date TEXT
            );

            -- Отслеживание активности для проверки "как дела"
            CREATE TABLE IF NOT EXISTS activity (
                senior_id INTEGER PRIMARY KEY,
                last_message_at INTEGER NOT NULL,
                last_checkin_sent_at INTEGER,
                alert_sent INTEGER NOT NULL DEFAULT 0
            );
            """
        )


# ---------- users ----------

def upsert_user(telegram_id: int, name: str, is_senior: bool = True):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO users (telegram_id, name, is_senior, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET name=excluded.name""",
            (telegram_id, name, int(is_senior), int(time.time())),
        )


def get_user(telegram_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None


# ---------- linking ----------

def create_link_code(senior_id: int) -> str:
    code = secrets.token_hex(3).upper()  # например "A1B2C3"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO link_codes (code, senior_id, created_at) VALUES (?, ?, ?)",
            (code, senior_id, int(time.time())),
        )
    return code


def use_link_code(code: str, family_id: int):
    """Возвращает senior_id, если код найден, и создаёт связь. Иначе None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT senior_id FROM link_codes WHERE code=?", (code.upper().strip(),)
        ).fetchone()
        if not row:
            return None
        senior_id = row["senior_id"]
        conn.execute(
            "INSERT OR IGNORE INTO links (senior_id, family_id) VALUES (?, ?)",
            (senior_id, family_id),
        )
        conn.execute("DELETE FROM link_codes WHERE code=?", (code.upper().strip(),))
        return senior_id


def get_family_for_senior(senior_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT family_id FROM links WHERE senior_id=?", (senior_id,)
        ).fetchall()
        return [r["family_id"] for r in rows]


def get_seniors_for_family(family_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT senior_id FROM links WHERE family_id=?", (family_id,)
        ).fetchall()
        return [r["senior_id"] for r in rows]


# ---------- reminders ----------

def add_reminder(senior_id: int, text: str, hour: int, minute: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO reminders (senior_id, text, hour, minute) VALUES (?, ?, ?, ?)",
            (senior_id, text, hour, minute),
        )
        return cur.lastrowid


def list_reminders(senior_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE senior_id=? AND active=1 ORDER BY hour, minute",
            (senior_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_reminder(reminder_id: int, senior_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE reminders SET active=0 WHERE id=? AND senior_id=?",
            (reminder_id, senior_id),
        )
        return cur.rowcount > 0


def all_active_reminders():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM reminders WHERE active=1").fetchall()
        return [dict(r) for r in rows]


def mark_reminder_sent_today(reminder_id: int, date_str: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE reminders SET last_sent_date=? WHERE id=?", (date_str, reminder_id)
        )


# ---------- activity / check-in ----------

def touch_activity(senior_id: int):
    now = int(time.time())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO activity (senior_id, last_message_at, alert_sent)
               VALUES (?, ?, 0)
               ON CONFLICT(senior_id) DO UPDATE SET last_message_at=?, alert_sent=0""",
            (senior_id, now, now),
        )


def get_all_seniors():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT telegram_id FROM users WHERE is_senior=1"
        ).fetchall()
        return [r["telegram_id"] for r in rows]


def get_activity(senior_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM activity WHERE senior_id=?", (senior_id,)
        ).fetchone()
        return dict(row) if row else None


def set_checkin_sent(senior_id: int):
    now = int(time.time())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO activity (senior_id, last_message_at, last_checkin_sent_at, alert_sent)
               VALUES (?, ?, ?, 0)
               ON CONFLICT(senior_id) DO UPDATE SET last_checkin_sent_at=?""",
            (senior_id, now, now, now),
        )


def set_alert_sent(senior_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE activity SET alert_sent=1 WHERE senior_id=?", (senior_id,)
        )
