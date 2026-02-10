import streamlit as st
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

from services.classifier import classify_excuse
from services.weather import get_weather
import db
from services import fit
from services import insights
from services import messaging

load_dotenv()

# DB 초기화
db.init_db()

# =======================
# 정책 매핑
# =======================
EXCUSE_POLICY = {
    "weather": "WEATHER_CHECK",
    "time": "TIME_CHECK",
    "energy": "LOW_INTENSITY",
    "fatigue": "LOW_INTENSITY",
    "emotion": "MOTIVATION_PUSH",
    "health": "SAFE_SKIP",
    "other": "NEUTRAL_REFLECT"
}

WEEKDAY_MAP = {
    0: "월",
    1: "화",
    2: "수",
    3: "목",
    4: "금",
    5: "토",
    6: "일"
}

# =======================
# Session State 초기화
# =======================
if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

if "user" not in st.session_state:
    st.session_state.user = {}

if "last_check_date" not in st.session_state:
    st.session_state.last_check_date = None


# =======================
# 실제 날씨 기반 판단
# =======================
def get_weather_fact(city="Seoul"):
    data = get_weather(city)

    weather_main = data["weather"][0]["main"].lower()
    weather_desc = data["weather"][0]["description"]
    temp = data["main"]["temp"]

    is_rain = "rain" in weather_main
    is_snow = "snow" in weather_main
    # wind: either mentioned in main/desc or wind speed high
    wind_speed = data.get("wind", {}).get("speed", 0)
    is_windy = ("wind" in weather_main) or (wind_speed and wind_speed >= 8)

    return {
        "rain": is_rain,
        "snow": is_snow,
        "wind": is_windy,
        "temp": temp,
        "desc": weather_desc,
        "main": weather_main,
        "wind_speed": wind_speed,
    }


def evaluate_weather_excuse(user_excuse_text, weather_fact):
    """
    사용자 발화 vs 실제 날씨 불일치 판단
    """
    text = user_excuse_text.lower()

    # flexible condition keywords mapping
    WEATHER_KEYWORDS = {
        "rain": ["비", "rain"],
        "snow": ["눈", "snow"],
        "cold": ["춥", "cold", "한파", "추워"],
        "hot": ["덥", "hot", "더워", "폭염"],
        "wind": ["바람", "wind", "강풍"],
        "dust": ["미세먼지", "황사", "dust", "pm"],
    }

    claimed = {k: any(kw in text for kw in kws) for k, kws in WEATHER_KEYWORDS.items()}

    # Evaluate claimed conditions against weather facts
    # If user claims a condition that the facts don't support -> invalid
    for cond, is_claimed in claimed.items():
        if not is_claimed:
            continue

        if cond == "rain" and not weather_fact.get("rain"):
            return {"valid": False, "reason": "claimed_rain_but_no_rain"}
        if cond == "snow" and not weather_fact.get("snow"):
            return {"valid": False, "reason": "claimed_snow_but_no_snow"}
        if cond == "wind" and not weather_fact.get("wind"):
            return {"valid": False, "reason": "claimed_wind_but_no_wind"}
        if cond == "dust":
            # dust check: look for keywords in description (best-effort)
            if not any(d in weather_fact.get("desc", "") for d in ["먼지", "dust", "황사"]):
                return {"valid": False, "reason": "claimed_dust_but_no_evidence"}
        if cond == "cold" and not (weather_fact.get("temp") is not None and weather_fact.get("temp") <= -5):
            return {"valid": False, "reason": "claimed_cold_but_not_cold"}
        if cond == "hot" and not (weather_fact.get("temp") is not None and weather_fact.get("temp") >= 33):
            return {"valid": False, "reason": "claimed_hot_but_not_hot"}

    # If any actual adverse condition exists, accept as valid
    if weather_fact.get("temp") is not None and weather_fact.get("temp") <= -5:
        return {"valid": True, "reason": "too_cold"}

    if any([weather_fact.get("rain"), weather_fact.get("snow"), weather_fact.get("wind")]):
        return {"valid": True, "reason": "actual_bad_weather"}

    return {"valid": True, "reason": "neutral_weather"}


def evaluate_time_excuse(exercise_time_str: str, duration_minutes: int, excuse_text: str):
    """
    사용자가 '시간 없어서' 핑계를 댔을 때 캘린더 확인
    """
    from services.calendar import list_upcoming_events
    from datetime import time as time_obj

    text = excuse_text.lower()

    # 시간 관련 키워드
    TIME_KEYWORDS = ["시간", "바쁘", "바빴", "일정", "일이", "약속", "time", "busy", "schedule"]

    if not any(kw in text for kw in TIME_KEYWORDS):
        return {"valid": None, "reason": "not_time_related"}

    try:
        # 캘린더 이벤트 조회
        events = list_upcoming_events()

        # 운동 시간 파싱
        ex_hour, ex_min = map(int, exercise_time_str.split(':'))
        exercise_start = time_obj(ex_hour, ex_min)
        exercise_end_time = datetime.strptime(
            f"1970-01-01 {exercise_time_str}",
            "%Y-%m-%d %H:%M"
        ) + timedelta(minutes=duration_minutes)
        exercise_end = exercise_end_time.time()

        # 오늘 이벤트만 필터링
        today_str = date.today().isoformat()

        for ev in events:
            start = ev.get('start', '')
            if today_str not in str(start):
                continue

            # 이벤트 시간 파싱
            if 'T' in str(start):  # dateTime 형식
                try:
                    ev_datetime = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    ev_time = ev_datetime.time()
                except:
                    continue
            else:  # date 형식만 있으면 전일 일정
                return {"valid": True, "reason": "has_all_day_event"}

            # 겹침 판정 (운동 구간과 이벤트 구간 비교)
            if exercise_start <= ev_time <= exercise_end:
                return {"valid": True, "reason": "schedule_conflict"}

        # 겹치는 일정 없음 -> 거짓 핑계
        return {"valid": False, "reason": "claimed_time_but_no_conflict"}

    except Exception as e:
        # 캘린더 연동 실패시 판단 불가
        st.warning(f"⚠️ 캘린더 확인 불가: {str(e)}")
        return {"valid": None, "reason": "calendar_unavailable"}


def evaluate_sleep_excuse(user_id: int, excuse_text: str):
    """
    최근 수면 기록을 보고 '피곤해서 못했다' 주장 검토
    - 최근 3일 평균 수면 시간이 6시간 미만이면 피로 사유를 타당하다고 판단
    - 수면 데이터가 없으면 판단 불가 반환
    """
    sleeps = db.get_recent_sleep_logs(user_id, limit=3)
    if not sleeps:
        return {"valid": None, "reason": "no_sleep_data"}

    durations = []
    for r in sleeps:
        try:
            s = datetime.fromisoformat(r[1])
            e = datetime.fromisoformat(r[2])
        except Exception:
            continue
        durations.append((e - s).total_seconds() / 3600.0)

    if not durations:
        return {"valid": None, "reason": "no_parsable_sleep_data"}

    avg_hours = sum(durations) / len(durations)
    if avg_hours < 6.0:
        return {"valid": True, "reason": f"short_sleep_avg_{avg_hours:.1f}h", "avg_hours": avg_hours}
    else:
        return {"valid": False, "reason": f"sleep_ok_avg_{avg_hours:.1f}h", "avg_hours": avg_hours}


# =======================
# UI
# =======================
st.title("No Excuses AI Agent")
st.write("데이터 기반 핑계 격파 운동 코치")

# =======================
# 1️⃣ 온보딩
# =======================
if not st.session_state.onboarded:
    st.subheader("👤 사용자 정보 입력")

    name = st.text_input("이름")
    selected_days = st.multiselect("운동 요일", ["월", "화", "수", "목", "금", "토", "일"])

    # 요일별 운동 시간 설정
    schedules = {}
    if selected_days:
        st.subheader("⏰ 요일별 운동 시간 설정")
        for day in selected_days:
            with st.expander(f"📅 {day}요일"):
                col1, col2 = st.columns(2)
                with col1:
                    start_time = st.time_input(
                        f"{day} 시작시간",
                        value=datetime.strptime("07:00", "%H:%M").time(),
                        key=f"start_{day}"
                    )
                with col2:
                    duration = st.slider(
                        f"{day} 지속시간 (분)",
                        min_value=10,
                        max_value=180,
                        value=60,
                        step=10,
                        key=f"duration_{day}"
                    )
                schedules[day] = {
                    "start_time": start_time.strftime("%H:%M"),
                    "duration": duration
                }

    if st.button("저장하고 시작하기"):
        if not name or not selected_days:
            st.warning("이름과 운동 요일은 필수입니다.")
        else:
            # session state 저장
            st.session_state.user = {
                "name": name,
                "plan": {
                    "days": selected_days,
                    "schedules": schedules
                }
            }
            # DB 저장
            user_id = db.ensure_user(name)
            st.session_state.user["id"] = user_id
            db.set_schedules(user_id, schedules)
            st.session_state.onboarded = True
            st.rerun()

# =======================
# 2️⃣ 메인 로직
# =======================
else:
    user = st.session_state.user
    plan = user["plan"]

    st.subheader(f"💪 {user['name']}님의 운동 플랜")
    st.write(f"- 📅 요일: {', '.join(plan['days'])}")
    
    # 요일별 스케줄 표시
    schedules = plan.get("schedules", {})
    for day, sched in schedules.items():
        st.write(f"  - {day}: {sched['start_time']} ({sched['duration']}분)")
    st.divider()

    now = datetime.now()
    today = date.today()
    today_weekday = WEEKDAY_MAP[now.weekday()]
    is_exercise_day = today_weekday in plan["days"]

    # 오늘의 운동 스케줄 가져오기
    today_schedule = schedules.get(today_weekday, None)

    # 수면 데이터 섹션
    st.subheader("🛌 수면 데이터 (데모)")
    col_a, col_b = st.columns(2)
    with col_a:
        uploaded = st.file_uploader("수면 CSV 업로드 (start,end)", type=["csv"]) 
        if uploaded is not None:
            parsed = fit.parse_sleep_csv(uploaded)
            if parsed:
                user_id = st.session_state.user.get("id") or db.ensure_user(st.session_state.user.get("name", "unknown"))
                for s in parsed:
                    db.add_sleep_log(user_id, s["start"], s["end"], source="upload")
                st.success(f"{len(parsed)}개의 수면 레코드를 저장했습니다.")
            else:
                st.warning("CSV를 파싱할 수 없거나 형식이 맞지 않습니다.")
    with col_b:
        if st.button("샘플 수면 데이터 불러오기"):
            sample = fit.generate_mock_sleep(7)
            user_id = st.session_state.user.get("id") or db.ensure_user(st.session_state.user.get("name", "unknown"))
            for s in sample:
                db.add_sleep_log(user_id, s["start"], s["end"], source="mock")
            st.success("샘플 수면데이터 7개가 저장되었습니다.")

    # 최근 수면 레코드 표시
    user_id = st.session_state.user.get("id") or db.ensure_user(st.session_state.user.get("name", "unknown"))
    sleeps = db.get_recent_sleep_logs(user_id, limit=10)
    if sleeps:
        st.write("최근 수면 기록:")
        for r in sleeps:
            st.write(f"- {r[1]} → {r[2]} (src: {r[3]})")

    if not is_exercise_day:
        st.info(f"📌 오늘은 운동 요일이 아니에요 ({today_weekday}).")

    elif today_schedule is None:
        st.warning(f"⚠️ 오늘({today_weekday})의 운동 스케줄이 없습니다.")

    else:
        today_start_time_str = today_schedule["start_time"]
        today_duration = today_schedule["duration"]

        exercise_time_today = datetime.strptime(
            f"{today} {today_start_time_str}",
            "%Y-%m-%d %H:%M"
        )
        exercise_end_time_today = exercise_time_today + timedelta(minutes=today_duration)

        def process_excuse_submission(excuse_text, user_id, start_time_str, duration_min):
            st.subheader("🧠 AI 분석 결과")

            result = classify_excuse(excuse_text)
            excuse_type = result["excuse_type"]
            confidence = result["confidence"]
            reason = result["reason"]

            policy = EXCUSE_POLICY.get(excuse_type, "NEUTRAL_REFLECT")
            # 인사이트(저장 전): 최근 반복 여부 확인(저장 전 집계)
            insight = insights.repeated_excuse_insight(user_id, excuse_type)
            insight_shown = False

            # persist exercise log (did_exercise = False) and excuse
            log_id = db.add_exercise_log(user_id, today.isoformat(), False)

            st.write("📌 핑계 유형:", excuse_type)
            st.write("🔍 확신도:", round(confidence, 2))
            st.write("🧠 판단 근거:", reason)
            st.write("🤖 적용 정책:", policy)
            st.divider()

            # WEATHER_CHECK
            if policy == "WEATHER_CHECK":
                weather_fact = get_weather_fact()
                eval_result = evaluate_weather_excuse(excuse_text, weather_fact)

                st.subheader("🌤️ 실제 날씨 분석")
                st.write(f"- 상태: {weather_fact['desc']}")
                st.write(f"- 기온: {weather_fact['temp']}°C")
                st.divider()

                if not eval_result["valid"]:
                    reason_key = eval_result.get("reason", "")
                    REJECTION_MESSAGES = {
                        "claimed_rain_but_no_rain": "❌ 비가 온다고 했지만 실제로는 비가 오지 않았어요.\n\n날씨가 운동을 막은 건 아니에요.",
                        "claimed_snow_but_no_snow": "❌ 눈이 온다고 했지만 실제로는 눈이 오지 않았어요.\n\n날씨가 운동을 막은 건 아니에요.",
                        "claimed_wind_but_no_wind": "❌ 바람이 심하다고 했지만, 현재 강풍 징후가 없어요.\n\n날씨가 운동을 막은 건 아니에요.",
                        "claimed_dust_but_no_evidence": "❌ 미세먼지/황사로 운동을 못했다고 했지만, 현재 대기 상태에 근거가 없어요.\n\n날씨가 운동을 막은 건 아니에요.",
                        "claimed_cold_but_not_cold": "❌ 너무 춥다고 하셨지만, 현재 기온은 매우 낮지 않아요.\n\n날씨가 운동을 막은 건 아니에요.",
                        "claimed_hot_but_not_hot": "❌ 폭염이라고 했지만, 현재 온도는 폭염 수준이 아니에요.\n\n날씨가 운동을 막은 건 아니에요.",
                    }

                    message = REJECTION_MESSAGES.get(
                        reason_key,
                        "❌ 주장하신 날씨 사유가 현재 기상 데이터와 일치하지 않습니다.\n\n날씨가 운동을 막은 건 아닌 것 같아요."
                    )

                    st.error(message)
                    st.success(
                        "👉 이 핑계는 날씨로는 정당화되기 어려워요.\n\n운동하러 가볼까요?"
                    )

                    exc_row_id = db.add_excuse_log(log_id, excuse_text, excuse_type, confidence, reason, policy, eval_result.get("reason"))
                    if not insight_shown and insight.get("escalate"):
                        user_name = st.session_state.user.get("name", "사용자")
                        msg = messaging.generate_escalation_message(user_name, excuse_type, insight.get("count"), insight.get("window_days"))
                        st.warning(msg)
                        insight_shown = True
                else:
                    st.info("오늘은 날씨가 운동하기에 부담스러웠을 수 있어요.")
                    st.success("🏠 추천: 실내 스트레칭 10분")
                    exc_row_id = db.add_excuse_log(log_id, excuse_text, excuse_type, confidence, reason, policy, eval_result.get("reason"))
                    if not insight_shown and insight.get("escalate"):
                        user_name = st.session_state.user.get("name", "사용자")
                        msg = messaging.generate_escalation_message(user_name, excuse_type, insight.get("count"), insight.get("window_days"))
                        st.warning(msg)
                        insight_shown = True

            # TIME_CHECK
            elif policy == "TIME_CHECK":
                time_eval = evaluate_time_excuse(start_time_str, duration_min, excuse_text)

                if time_eval["valid"] is None:
                    st.warning("⏰ 일정 확인이 불가능하거나 시간 관련 사유가 아닙니다.")
                    exc_row_id = db.add_excuse_log(log_id, excuse_text, excuse_type, confidence, reason, policy, "inconclusive")
                    if not insight_shown and insight.get("escalate"):
                        user_name = st.session_state.user.get("name", "사용자")
                        msg = messaging.generate_escalation_message(user_name, excuse_type, insight.get("count"), insight.get("window_days"))
                        st.warning(msg)
                        insight_shown = True

                elif time_eval["valid"]:
                    st.info("📅 캘린더에 일정이 있었네요. 바쁜 하루였겠어요.")
                    st.success("🕐 다른 시간대에 운동을 해볼까요? 또는 내일을 기대해요!")
                    exc_row_id = db.add_excuse_log(log_id, excuse_text, excuse_type, confidence, reason, policy, time_eval.get("reason"))
                    if not insight_shown and insight.get("escalate"):
                        user_name = st.session_state.user.get("name", "사용자")
                        msg = messaging.generate_escalation_message(user_name, excuse_type, insight.get("count"), insight.get("window_days"))
                        st.warning(msg)
                        insight_shown = True

                else:
                    st.error("❌ 운동 시간에 캘린더 일정이 없습니다.\n\n시간이 충분하셨을 것 같아요.")
                    st.success("👉 이 핑계는 일정으로는 정당화되기 어려워요.\n\n운동하러 가볼까요?")
                    exc_row_id = db.add_excuse_log(log_id, excuse_text, excuse_type, confidence, reason, policy, "claimed_time_but_no_conflict")
                    if not insight_shown and insight.get("escalate"):
                        user_name = st.session_state.user.get("name", "사용자")
                        msg = messaging.generate_escalation_message(user_name, excuse_type, insight.get("count"), insight.get("window_days"))
                        st.warning(msg)
                        insight_shown = True

            # LOW_INTENSITY -> 수면 데이터 기반 판단
            elif policy == "LOW_INTENSITY":
                sleep_eval = evaluate_sleep_excuse(user_id, excuse_text)
                if sleep_eval["valid"] is None:
                    st.info("컨디션 관련 사유로 보이나, 수면 데이터가 부족해 판단할 수 없습니다.")
                    exc_row_id = db.add_excuse_log(log_id, excuse_text, excuse_type, confidence, reason, policy, sleep_eval.get("reason"))
                    if not insight_shown and insight.get("escalate"):
                        user_name = st.session_state.user.get("name", "사용자")
                        msg = messaging.generate_escalation_message(user_name, excuse_type, insight.get("count"), insight.get("window_days"))
                        st.warning(msg)
                        insight_shown = True
                elif sleep_eval["valid"]:
                    st.info(f"😴 최근 평균 수면이 낮습니다 ({sleep_eval.get('avg_hours'):.1f}시간). 오늘은 저강도로 시작해도 괜찮아요.")
                    st.success("추천: 저강도 10분 스트레칭")
                    exc_row_id = db.add_excuse_log(log_id, excuse_text, excuse_type, confidence, reason, policy, sleep_eval.get("reason"))
                    if not insight_shown and insight.get("escalate"):
                        st.warning(f"⚠️ 최근 {insight.get('window_days')}일 동안 같은 핑계({excuse_type})가 {insight.get('count')}회 발견되었습니다. 더 강하게 권유합니다.")
                        insight_shown = True
                else:
                    st.error(f"❌ 수면 데이터로는 피로로 보기 어렵습니다 (평균 {sleep_eval.get('avg_hours'):.1f}시간). 잠깐 몸을 움직여볼까요?")
                    db.add_excuse_log(log_id, excuse_text, excuse_type, confidence, reason, policy, sleep_eval.get("reason"))

            elif policy == "SAFE_SKIP":
                st.warning("🩺 건강 문제는 최우선이에요. 오늘은 쉬세요.")
                exc_row_id = db.add_excuse_log(log_id, excuse_text, excuse_type, confidence, reason, policy, "safe_skip")
                if not insight_shown and insight.get("escalate"):
                    user_name = st.session_state.user.get("name", "사용자")
                    msg = messaging.generate_escalation_message(user_name, excuse_type, insight.get("count"), insight.get("window_days"))
                    st.warning(msg)
                    insight_shown = True

            else:
                st.info("오늘을 돌아보고 내일을 준비해볼까요?")
                exc_row_id = db.add_excuse_log(log_id, excuse_text, excuse_type, confidence, reason, policy, "neutral")
                if not insight_shown and insight.get("escalate"):
                    user_name = st.session_state.user.get("name", "사용자")
                    msg = messaging.generate_escalation_message(user_name, excuse_type, insight.get("count"), insight.get("window_days"))
                    st.warning(msg)
                    insight_shown = True

        # 이미 오늘 기록함
        if st.session_state.last_check_date == today:
            st.info("✅ 오늘 운동 여부는 이미 기록했어요.")

        else:
            # 아직 운동 시작 전: 미리 했는지 확인 가능
            if now < exercise_time_today:
                st.info("⏳ 아직 운동 시작 전이에요. 미리 하셨나요?")
                did_ex_before = st.radio(
                    "오늘 운동 하셨나요?",
                    ["선택", "했어요", "못 했어요"],
                    key="did_pre"
                )

                user_id = st.session_state.user.get("id") or db.ensure_user(st.session_state.user.get("name", "unknown"))
                st.session_state.user["id"] = user_id

                if did_ex_before == "했어요":
                    st.success("🔥 이미 운동하셨군요! 멋져요.")
                    st.session_state.last_check_date = today
                    db.add_exercise_log(user_id, today.isoformat(), True)
                elif did_ex_before == "못 했어요":
                    excuse_pre = st.text_input("❓ 왜 못 하셨나요?", key="excuse_pre")
                    if excuse_pre:
                        st.session_state.last_check_date = today
                        process_excuse_submission(excuse_pre, user_id, today_start_time_str, today_duration)

            # 운동 시간(시작 ~ 종료) 도중: 체크 UI 노출
            elif exercise_time_today <= now <= exercise_end_time_today:
                st.warning("⏰ 지금은 운동 시간이에요!")
                did_exercise = st.radio(
                    "오늘 운동 하셨나요?",
                    ["선택", "했어요", "못 했어요"],
                    key="did_during"
                )

                user_id = st.session_state.user.get("id") or db.ensure_user(st.session_state.user.get("name", "unknown"))
                st.session_state.user["id"] = user_id

                if did_exercise == "했어요":
                    st.success("🔥 오늘 운동 완료! 잘하셨어요.")
                    st.session_state.last_check_date = today
                    db.add_exercise_log(user_id, today.isoformat(), True)

                elif did_exercise == "못 했어요":
                    excuse = st.text_input("❓ 왜 못 하셨나요?", key="excuse_during")
                    if excuse:
                        st.session_state.last_check_date = today
                        process_excuse_submission(excuse, user_id, today_start_time_str, today_duration)

            # 운동 시간이 이미 지남: 여전히 물어보고 핑계 받기
            else:
                st.warning("⚠️ 오늘의 운동 시간이 지났습니다. 기록을 놓치셨을 수 있어요.")
                did_ex_after = st.radio(
                    "오늘 운동 하셨나요?",
                    ["선택", "했어요", "못 했어요"],
                    key="did_post"
                )

                user_id = st.session_state.user.get("id") or db.ensure_user(st.session_state.user.get("name", "unknown"))
                st.session_state.user["id"] = user_id

                if did_ex_after == "했어요":
                    st.success("🔥 오늘 운동 완료! 기록을 남겨둘게요.")
                    st.session_state.last_check_date = today
                    db.add_exercise_log(user_id, today.isoformat(), True)
                elif did_ex_after == "못 했어요":
                    excuse_post = st.text_input("❓ 왜 못 하셨나요?", key="excuse_post")
                    if excuse_post:
                        st.session_state.last_check_date = today
                        process_excuse_submission(excuse_post, user_id, today_start_time_str, today_duration)
