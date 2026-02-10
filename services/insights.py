from datetime import datetime, timedelta, date
import db


def repeated_excuse_insight(user_id: int, excuse_type: str, window_days: int = 14, threshold: int = 3):
    """
    최근 `window_days` 동안 동일 `excuse_type` 발생 횟수를 센다.
    threshold 이상이면 escalate 추천을 반환.
    반환값: {"count": int, "escalate": bool, "window_days": int}
    """
    conn = db._connect()
    cur = conn.cursor()

    since = (datetime.utcnow() - timedelta(days=window_days)).isoformat()

    # excuse_logs.created_at 기준으로 집계
    cur.execute(
        """
        SELECT COUNT(*) FROM excuse_logs el
        JOIN exercise_logs xl ON el.log_id = xl.id
        WHERE xl.user_id = ? AND el.excuse_type = ? AND el.created_at >= ?
        """,
        (user_id, excuse_type, since),
    )
    row = cur.fetchone()
    conn.close()

    count = row[0] if row else 0
    return {"count": count, "escalate": count >= threshold, "window_days": window_days}


def top_excuses(user_id: int, window_days: int = 14, limit: int = 5):
    """
    최근 window_days 동안 가장 빈도가 높은 excuse_type 목록을 반환
    """
    conn = db._connect()
    cur = conn.cursor()
    since = (datetime.utcnow() - timedelta(days=window_days)).isoformat()

    cur.execute(
        """
        SELECT el.excuse_type, COUNT(*) as cnt FROM excuse_logs el
        JOIN exercise_logs xl ON el.log_id = xl.id
        WHERE xl.user_id = ? AND el.created_at >= ?
        GROUP BY el.excuse_type
        ORDER BY cnt DESC
        LIMIT ?
        """,
        (user_id, since, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [{"excuse_type": r[0], "count": r[1]} for r in rows]


def seed_repeated_excuses(user_id: int, excuse_type: str, count: int = 3, span_days: int = 14):
    """
    시연용: 최근 `span_days` 범위에 걸쳐 동일한 `excuse_type`의 excuse_logs를 `count`개 생성합니다.
    - 모든 DB 작업을 한 연결에서 처리하여 "database is locked" 방지.
    반환: 생성된 레코드 수
    """
    conn = db._connect()
    cur = conn.cursor()

    now = datetime.utcnow()
    created = 0
    for i in range(count):
        # 분산: 0 .. span_days 사이
        if count > 1:
            days_ago = int(i * span_days / (count - 1))
        else:
            days_ago = 0

        created_at = (now - timedelta(days=days_ago)).isoformat()
        target_date = (date.today() - timedelta(days=days_ago)).isoformat()
        
        # Inline exercise_log insertion to avoid nested DB calls
        cur.execute("SELECT id FROM exercise_logs WHERE user_id = ? AND date = ?", (user_id, target_date))
        row = cur.fetchone()
        if row:
            log_id = row[0]
        else:
            cur.execute(
                "INSERT INTO exercise_logs (user_id, date, did_exercise, created_at) VALUES (?, ?, ?, ?)",
                (user_id, target_date, 0, created_at),
            )
            log_id = cur.lastrowid

        raw_text = f"demo_seed_{excuse_type}"
        confidence = 0.9
        reason = "demo seed"
        policy = "demo"

        cur.execute(
            "INSERT INTO excuse_logs (log_id, raw_text, excuse_type, confidence, reason, policy, judgment_result, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (log_id, raw_text, excuse_type, confidence, reason, policy, None, created_at),
        )
        created += 1

    conn.commit()
    conn.close()
    return created
