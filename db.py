import sqlite3
import os
from datetime import datetime
from typing import List

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")


def _connect():
    # allow a longer timeout and permit cross-thread usage in Streamlit reruns
    return sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)


def init_db():
    conn = _connect()
    cur = conn.cursor()
    # enable WAL to reduce "database is locked" during concurrent reads/writes
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        height_cm REAL,
        weight_kg REAL,
        goal TEXT,
        created_at TEXT
    )
    """
    )

    # 기존 DB에 컬럼이 없을 수 있으므로 보강
    cur.execute("PRAGMA table_info(users)")
    existing_cols = {row[1] for row in cur.fetchall()}
    for col, col_type in [("height_cm", "REAL"), ("weight_kg", "REAL"), ("goal", "TEXT")]:
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS exercise_schedules (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        day_of_week INTEGER,
        start_time TEXT,
        duration_minutes INTEGER,
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

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS sleep_logs (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        start TEXT,
        end TEXT,
        source TEXT,
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """
    )

    conn.commit()
    conn.close()



def ensure_user(name: str, height_cm: float = None, weight_kg: float = None, goal: str = None) -> int:
    """
    사용자 정보가 없으면 생성, 있으면 id만 반환. height_cm, weight_kg, goal이 주어지면 업데이트.
    """
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        user_id = row[0]
        # 값이 주어지면 업데이트
        if any([height_cm is not None, weight_kg is not None, goal is not None]):
            cur.execute(
                "UPDATE users SET height_cm = COALESCE(?, height_cm), weight_kg = COALESCE(?, weight_kg), goal = COALESCE(?, goal) WHERE id = ?",
                (height_cm, weight_kg, goal, user_id)
            )
            conn.commit()
    else:
        now = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO users (name, height_cm, weight_kg, goal, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, height_cm, weight_kg, goal, now)
        )
        user_id = cur.lastrowid
        conn.commit()
    conn.close()
    return user_id


def set_schedules(user_id: int, schedules: dict):
    """
    schedules = {
        "월": {"start_time": "07:00", "duration": 60},
        "화": {"start_time": "07:00", "duration": 60},
        ...
    }
    """
    day_map = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM exercise_schedules WHERE user_id = ?", (user_id,))
    
    for day_str, sched in schedules.items():
        dow = day_map.get(day_str)
        if dow is None:
            continue
        
        start_time = sched.get("start_time", "07:00")
        duration = sched.get("duration", 60)
        
        cur.execute(
            "INSERT INTO exercise_schedules (user_id, day_of_week, start_time, duration_minutes) VALUES (?, ?, ?, ?)",
            (user_id, dow, start_time, duration),
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


def add_sleep_log(user_id: int, start_iso: str, end_iso: str, source: str = "mock") -> int:
    conn = _connect()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO sleep_logs (user_id, start, end, source, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, start_iso, end_iso, source, now),
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def get_recent_sleep_logs(user_id: int, limit: int = 10):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, start, end, source, created_at FROM sleep_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_exercise_logs_by_month(user_id: int, year: int, month: int):
    """
    특정 월의 모든 운동 기록 조회
    반환: [(date, did_exercise), ...]
    """
    conn = _connect()
    cur = conn.cursor()
    
    month_start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        month_end = f"{year+1:04d}-01-01"
    else:
        month_end = f"{year:04d}-{month+1:02d}-01"
    
    cur.execute(
        """
        SELECT date, did_exercise FROM exercise_logs 
        WHERE user_id = ? AND date >= ? AND date < ?
        ORDER BY date
        """,
        (user_id, month_start, month_end),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_excuse_summary_by_month(user_id: int, year: int, month: int):
    """
    특정 월의 핑계 기록 요약 (날짜별 핑계 유형 및 개수)
    반환: {date: [excuse_type, ...], ...}
    """
    conn = _connect()
    cur = conn.cursor()
    
    month_start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        month_end = f"{year+1:04d}-01-01"
    else:
        month_end = f"{year:04d}-{month+1:02d}-01"
    
    cur.execute(
        """
        SELECT xl.date, el.excuse_type 
        FROM excuse_logs el
        JOIN exercise_logs xl ON el.log_id = xl.id
        WHERE xl.user_id = ? AND xl.date >= ? AND xl.date < ?
        ORDER BY xl.date
        """,
        (user_id, month_start, month_end),
    )
    rows = cur.fetchall()
    conn.close()
    
    result = {}
    for date, excuse_type in rows:
        if date not in result:
            result[date] = []
        result[date].append(excuse_type)
    
    return result
