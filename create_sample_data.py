"""
DB에 임의의 테스트 데이터 생성
"""
import db
from datetime import datetime, date, timedelta
import random

def create_sample_data():
    """테스트 데이터 생성"""
    db.init_db()
    
    # 사용자 생성
    user_name = "Test User"
    user_id = db.ensure_user(user_name)
    print(f"✓ 사용자 생성: {user_name} (ID: {user_id})")
    
    # 운동 스케줄 설정
    schedules = {
        "월": {"start_time": "07:00", "duration": 60},
        "수": {"start_time": "18:00", "duration": 60},
        "금": {"start_time": "07:00", "duration": 60},
    }
    db.set_schedules(user_id, schedules)
    print(f"✓ 운동 스케줄 설정: {list(schedules.keys())}")
    
    # 지난 30일 데이터 생성
    excuse_types = ["weather", "time", "fatigue", "energy", "emotion"]
    
    for i in range(30):
        target_date = (date.today() - timedelta(days=i)).isoformat()
        
        # 70% 확률로 운동함, 30% 확률로 핑계
        if random.random() < 0.7:
            did_exercise = 1
            log_id = db.add_exercise_log(user_id, target_date, True)
            print(f"  ✓ {target_date}: 운동 완료")
        else:
            did_exercise = 0
            log_id = db.add_exercise_log(user_id, target_date, False)
            
            # 핑계 기록
            excuse_type = random.choice(excuse_types)
            db.add_excuse_log(
                log_id,
                raw_text=f"Sample excuse: {excuse_type}",
                excuse_type=excuse_type,
                confidence=0.85,
                reason="Test data",
                policy="TEST",
                judgment_result="sample"
            )
            print(f"  ✓ {target_date}: 핑계 ({excuse_type})")
    
    # 수면 데이터 생성
    for i in range(20):
        target_date = datetime.now() - timedelta(days=i)
        sleep_hours = random.uniform(4, 8)
        start_time = (target_date - timedelta(hours=sleep_hours)).isoformat()
        end_time = target_date.isoformat()
        
        db.add_sleep_log(user_id, start_time, end_time, source="sample")
    
    print(f"\n✅ 테스트 데이터 생성 완료!")
    print(f"   사용자: {user_name}")
    print(f"   운동 요일: {', '.join(schedules.keys())}")
    print(f"   데이터 범위: 지난 30일")


if __name__ == "__main__":
    create_sample_data()
