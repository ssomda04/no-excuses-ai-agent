import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

def inspect_db():
    """DB 테이블 내용 조회"""
    if not os.path.exists(DB_PATH):
        print(f"❌ DB 파일을 찾을 수 없습니다: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    tables = ['users', 'exercise_schedules', 'exercise_logs', 'excuse_logs', 'sleep_logs']
    
    for table_name in tables:
        print(f"\n{'='*60}")
        print(f"📋 TABLE: {table_name}")
        print(f"{'='*60}")
        
        try:
            cur.execute(f"SELECT * FROM {table_name}")
            rows = cur.fetchall()
            
            # 컬럼명 조회
            cur.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cur.fetchall()]
            
            if not rows:
                print(f"(비어있음)")
            else:
                # 헤더 출력
                print(" | ".join(f"{col:20}" for col in columns))
                print("-" * (len(columns) * 22))
                
                # 데이터 출력
                for row in rows:
                    print(" | ".join(f"{str(val)[:20]:20}" for val in row))
                
                print(f"\n총 {len(rows)}개 레코드")
        except Exception as e:
            print(f"⚠️ 오류: {e}")
    
    conn.close()

if __name__ == "__main__":
    inspect_db()
