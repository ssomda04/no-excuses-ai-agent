"""
운동 계획 적절성 평가 모듈
- BMI, 주당 운동 빈도/시간을 바탕으로 간단한 피드백 제공
- 의학적 진단이 아닌 생활 코칭/가이드 톤
"""
from typing import List, Dict, Any

def evaluate_plan(
    height_cm: float,
    weight_kg: float,
    exercise_days: List[str],
    schedules: Dict[str, Dict[str, Any]],
    goal: str
) -> Dict[str, str]:
    # BMI 계산
    height_m = height_cm / 100.0 if height_cm else 1.0
    bmi = weight_kg / (height_m ** 2) if height_m > 0 else 0

    # 주당 운동 횟수
    num_days = len(exercise_days)

    # 주당 총 운동 시간
    total_minutes = 0
    for day in exercise_days:
        sched = schedules.get(day)
        if sched and "duration" in sched:
            total_minutes += sched["duration"]

    # 기준 설정(코칭 관점, 의학적 아님)
    if num_days < 2 or total_minutes < 60:
        status = "insufficient"
        reason = (
            f"AI가 주당 빈도와 총 운동 시간을 기준으로 판단했습니다. "
            f"현재 주 {num_days}회, 총 {total_minutes}분은 계획을 유지하기엔 다소 부족해 보여요."
        )
        action = "일주일에 2~3회 이상, 90분 이상을 목표로 해보세요! 작은 변화가 큰 차이를 만듭니다."
    elif num_days >= 6 or total_minutes >= 400:
        status = "excessive"
        reason = (
            f"AI가 주당 빈도와 총 운동 시간을 기준으로 판단했습니다. "
            f"주 {num_days}회, 총 {total_minutes}분은 꽤 높은 편이에요."
        )
        action = "충분한 휴식도 중요해요. 몸 상태를 보며 페이스를 조절해보세요."
    else:
        status = "adequate"
        reason = (
            f"AI가 주당 빈도와 총 운동 시간을 기준으로 판단했습니다. "
            f"주 {num_days}회, 총 {total_minutes}분은 균형 잡힌 편이에요."
        )
        action = "이대로 꾸준히 실천하면 좋은 변화를 경험할 수 있어요."

    return {
        "status": status,
        "reason": reason,
        "action": action
    }
