import sqlite3
import os
from datetime import datetime
from typing import List

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = _connect()
    cur = conn.cursor()

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        created_at TEXT
    )
    """
    )

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS exercise_schedules (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        day_of_week INTEGER,
        exercise_time TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """
    )

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS exercise_logs (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        date TEXT,
        did_exercise INTEGER,
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """
    )

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS excuse_logs (
        id INTEGER PRIMARY KEY,
        log_id INTEGER,
        raw_text TEXT,
        excuse_type TEXT,
        confidence REAL,
        reason TEXT,
        policy TEXT,
        judgment_result TEXT,
        created_at TEXT,
        FOREIGN KEY(log_id) REFERENCES exercise_logs(id)
    )
    """
    )

    conn.commit()
    conn.close()


def ensure_user(name: str) -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        user_id = row[0]
    else:
        now = datetime.utcnow().isoformat()
        cur.execute("INSERT INTO users (name, created_at) VALUES (?, ?)", (name, now))
        user_id = cur.lastrowid
        conn.commit()
    conn.close()
    return user_id


def set_schedules(user_id: int, days: List[str], exercise_time: str):
    # days expect Korean short names e.g. '월','화' -> map to 0..6
    day_map = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM exercise_schedules WHERE user_id = ?", (user_id,))
    for d in days:
        dow = day_map.get(d)
        if dow is None:
            continue
        cur.execute(
            "INSERT INTO exercise_schedules (user_id, day_of_week, exercise_time) VALUES (?, ?, ?)",
            (user_id, dow, exercise_time),
        )
    conn.commit()
    conn.close()


def add_exercise_log(user_id: int, date_str: str, did_exercise: bool) -> int:
    conn = _connect()
    cur = conn.cursor()
    # check existing
    cur.execute("SELECT id FROM exercise_logs WHERE user_id = ? AND date = ?", (user_id, date_str))
    row = cur.fetchone()
    now = datetime.utcnow().isoformat()
    if row:
        log_id = row[0]
        cur.execute("UPDATE exercise_logs SET did_exercise = ?, created_at = ? WHERE id = ?", (int(did_exercise), now, log_id))
    else:
        cur.execute(
            "INSERT INTO exercise_logs (user_id, date, did_exercise, created_at) VALUES (?, ?, ?, ?)",
            (user_id, date_str, int(did_exercise), now),
        )
        log_id = cur.lastrowid

    conn.commit()
    conn.close()
    return log_id


def add_excuse_log(log_id: int, raw_text: str, excuse_type: str, confidence: float, reason: str, policy: str, judgment_result: str = None) -> int:
    conn = _connect()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO excuse_logs (log_id, raw_text, excuse_type, confidence, reason, policy, judgment_result, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (log_id, raw_text, excuse_type, confidence, reason, policy, judgment_result, now),
    )
    exc_id = cur.lastrowid
    conn.commit()
    conn.close()
    return exc_id
