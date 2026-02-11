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
    if bmi < 18.5:
        bmi_label = "저체중"
    elif bmi < 23:
        bmi_label = "정상"
    elif bmi < 25:
        bmi_label = "과체중"
    else:
        bmi_label = "비만"

    # 주당 운동 횟수
    num_days = len(exercise_days)

    # 주당 총 운동 시간
    total_minutes = 0
    for day in exercise_days:
        sched = schedules.get(day)
        if sched and "duration" in sched:
            total_minutes += sched["duration"]

    # 운동 목적별 목표치(코칭 관점, 의학적 아님)
    goal_targets = {
        "체중 감량": {"days": 3, "minutes": 150},
        "체력 향상": {"days": 3, "minutes": 120},
        "스트레스 해소": {"days": 2, "minutes": 60},
        "습관 형성": {"days": 2, "minutes": 60},
    }
    target = goal_targets.get(goal, {"days": 2, "minutes": 60})

    # 기준 설정(키/몸무게->BMI, 목적, 빈도, 시간 모두 반영)
    if num_days < target["days"] or total_minutes < target["minutes"]:
        status = "insufficient"
        reason = (
            f"AI가 키({height_cm}cm), 몸무게({weight_kg}kg)로 계산한 BMI {bmi:.1f}({bmi_label})와 "
            f"운동 목적({goal}), 주당 빈도/시간을 종합해 판단했습니다. "
            f"현재 주 {num_days}회, 총 {total_minutes}분은 목표에 비해 부족해 보여요."
        )
        action = (
            f"주 {target['days']}회 이상, {target['minutes']}분 이상을 먼저 목표로 해보세요. "
            "무리 없이 점진적으로 늘리면 좋습니다."
        )
    elif num_days >= 6 or total_minutes >= 450 or (bmi < 18.5 and total_minutes >= 300):
        status = "excessive"
        reason = (
            f"AI가 키({height_cm}cm), 몸무게({weight_kg}kg)로 계산한 BMI {bmi:.1f}({bmi_label})와 "
            f"운동 목적({goal}), 주당 빈도/시간을 종합해 판단했습니다. "
            f"주 {num_days}회, 총 {total_minutes}분은 다소 높은 편이에요."
        )
        action = "충분한 회복을 확보하고, 컨디션에 따라 강도나 횟수를 조절해보세요."
    else:
        status = "adequate"
        reason = (
            f"AI가 키({height_cm}cm), 몸무게({weight_kg}kg)로 계산한 BMI {bmi:.1f}({bmi_label})와 "
            f"운동 목적({goal}), 주당 빈도/시간을 종합해 판단했습니다. "
            f"주 {num_days}회, 총 {total_minutes}분은 목표에 맞는 균형 잡힌 수준이에요."
        )
        action = "이 페이스를 유지하면서 컨디션에 맞게 미세 조정해보세요."

    return {
        "status": status,
        "reason": reason,
        "action": action
    }
