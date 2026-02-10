# 실내운동 추천 영상 (title, url)
INDOOR_EXERCISE_LINKS = [
    {"title": "10분 전신 스트레칭 (집에서 따라하기)", "url": "https://youtu.be/unO8VyFb-BM?si=vBmYNessNm-D7Pgg"},
    {"title": "초보자용 홈트레이닝 루틴", "url": "https://www.youtube.com/watch?v=2L2lnxIcNmo"},
    {"title": "실내 유산소 운동 15분", "url": "https://www.youtube.com/watch?v=ml6cT4AZdqI"},
]


import streamlit as st
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

from typing import Dict, Any, Tuple, Optional

from services.classifier import classify_excuse
from services.weather import get_weather
import db
from services import fit
from services import insights
from services import messaging
from services.plan_evaluator import evaluate_plan

load_dotenv()

# DB 초기화
db.init_db()

# =======================
# 정책 매핑
# =======================
EXCUSE_POLICY = {
    "weather": "WEATHER_CHECK",
    "time": "TIME_CHECK",
    "condition": "LOW_INTENSITY",
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

# 기본 설정
DEFAULT_CITY = "Seoul"

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
def get_weather_fact(city: str = DEFAULT_CITY):
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
        if cond == "cold" and not (weather_fact.get("temp") is not None and weather_fact.get("temp") <= 0):
            return {"valid": False, "reason": "claimed_cold_but_not_cold"}
        if cond == "hot" and not (weather_fact.get("temp") is not None and weather_fact.get("temp") >= 30):
            return {"valid": False, "reason": "claimed_hot_but_not_hot"}

    # If any actual adverse condition exists, accept as valid
    if weather_fact.get("temp") is not None and weather_fact.get("temp") <= 0:
        return {"valid": True, "reason": "too_cold"}

    if weather_fact.get("temp") is not None and weather_fact.get("temp") >= 30:
        return {"valid": True, "reason": "too_hot"}

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
        # 캘린더 이벤트 조회 (오늘 전체 범위)
        today_date = date.today()
        day_start = datetime.combine(today_date, time_obj.min)
        day_end = datetime.combine(today_date, time_obj.max)
        events = list_upcoming_events(time_min=day_start, time_max=day_end, max_results=50)

        # 운동 시간 파싱
        ex_hour, ex_min = map(int, exercise_time_str.split(':'))
        exercise_start = time_obj(ex_hour, ex_min)
        today_date = date.today()
        exercise_start_dt = datetime.combine(today_date, exercise_start)
        exercise_end_dt = exercise_start_dt + timedelta(minutes=duration_minutes)
        exercise_end = exercise_end_dt.time()

        # 오늘 이벤트만 필터링
        today_str = date.today().isoformat()

        latest_conflict_end = None

        def _parse_event_dt(value: str) -> datetime:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt

        for ev in events:
            start = ev.get('start', '')
            end = ev.get('end', '')
            if today_str not in str(start):
                continue

            # 이벤트 시간 파싱
            if 'T' in str(start):  # dateTime 형식
                try:
                    ev_start_dt = _parse_event_dt(str(start))
                    ev_end_dt = _parse_event_dt(str(end)) if end else ev_start_dt
                    ev_time = ev_start_dt.time()
                except:
                    continue
            else:  # date 형식만 있으면 전일 일정
                return {"valid": True, "reason": "has_all_day_event"}

            # 겹침 판정 (운동 구간과 이벤트 구간 비교)
            if ev_start_dt <= exercise_end_dt and ev_end_dt >= exercise_start_dt:
                if latest_conflict_end is None or ev_end_dt > latest_conflict_end:
                    latest_conflict_end = ev_end_dt

        if latest_conflict_end is not None:
            # 30분 단위로 올림
            minute = latest_conflict_end.minute
            add_minutes = (30 - (minute % 30)) % 30
            suggested_start_dt = (latest_conflict_end + timedelta(minutes=add_minutes)).replace(second=0, microsecond=0)
            suggested_end_dt = suggested_start_dt + timedelta(minutes=duration_minutes)
            if suggested_end_dt.date() == today_date:
                return {
                    "valid": True,
                    "reason": "schedule_conflict",
                    "suggested_start": suggested_start_dt.strftime("%H:%M"),
                    "suggested_end": suggested_end_dt.strftime("%H:%M"),
                }
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
def persist_excuse_and_maybe_show_insight(
    log_id: int,
    excuse_text: str,
    excuse_type: str,
    confidence: float,
    reason: str,
    policy: str,
    eval_reason: Optional[str],
    insight: Dict[str, Any],
    insight_shown: bool,
) -> Tuple[int, bool]:
    """공통: 핑계 로그를 DB에 저장하고 필요시 인사이트(경고)를 표시한다.

    반환값: (excuse_row_id, insight_shown_flag)
    """
    exc_row_id = db.add_excuse_log(log_id, excuse_text, excuse_type, confidence, reason, policy, eval_reason)

    if not insight_shown and insight.get("escalate"):
        advice = messaging.generate_coaching_advice(excuse_type, insight.get("count"), insight.get("window_days"))
        st.warning(f"⚠️ 지난 {insight.get('window_days')}일 동안 '{excuse_type}' 핑계가 {insight.get('count')}회였습니다.\n\n{advice}")
        insight_shown = True

    return exc_row_id, insight_shown
st.title("No Excuses AI Agent")
st.write("데이터 기반 핑계 격파 운동 코치")

# =======================
# 1️⃣ 온보딩
# =======================
if not st.session_state.onboarded:
    st.subheader("👤 사용자 정보 입력")


    name = st.text_input("이름")
    col_a, col_b = st.columns(2)
    with col_a:
        height_cm = st.number_input("키 (cm)", min_value=100, max_value=250, value=170)
    with col_b:
        weight_kg = st.number_input("체중 (kg)", min_value=30, max_value=200, value=70)

    goal = st.selectbox("운동 목적", ["체중 감량", "체력 향상", "스트레스 해소", "습관 형성"])

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
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "goal": goal,
                "plan": {
                    "days": selected_days,
                    "schedules": schedules
                }
            }
            # DB 저장
            user_id = db.ensure_user(name, height_cm, weight_kg, goal)
            st.session_state.user["id"] = user_id
            db.set_schedules(user_id, schedules)
            # 1회성 평가 결과 저장 (메인 화면에서만 노출)
            st.session_state.plan_eval_result = evaluate_plan(
                height_cm=height_cm,
                weight_kg=weight_kg,
                exercise_days=selected_days,
                schedules=schedules,
                goal=goal,
            )
            st.session_state.plan_eval_status = st.session_state.plan_eval_result.get("status")
            st.session_state.plan_eval_shown = False
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
    today_schedule = schedules.get(today_weekday, None)

    user_id = st.session_state.user.get("id") or db.ensure_user(st.session_state.user.get("name", "unknown"))
    st.session_state.user["id"] = user_id
    sleeps = db.get_recent_sleep_logs(user_id, limit=10)

    with st.container(border=True):
        st.subheader("📅 오늘의 상태 요약")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("오늘 요일", today_weekday)
            st.metric("운동 예정", "O" if is_exercise_day else "X")
        with col2:
            if today_schedule:
                st.metric("운동 시간", today_schedule["start_time"])
                st.metric("운동 길이", f"{today_schedule['duration']}분")
            else:
                st.metric("운동 시간", "-")
                st.metric("운동 길이", "-")
        with col3:
            sleep_summary = "있음" if sleeps else "없음"
            st.metric("수면 데이터", sleep_summary)

    # AI 운동 계획 진단 (1회성 피드백)
    plan_eval = st.session_state.get("plan_eval_result")
    if plan_eval and not st.session_state.get("plan_eval_shown", False):
        st.subheader("AI 운동 계획 진단")
        status = plan_eval.get("status")
        reason = plan_eval.get("reason", "")
        action = plan_eval.get("action", "")

        coach_lines = {
            "insufficient": "조금만 보완하면 훨씬 탄탄한 계획이 될 수 있어요.",
            "adequate": "지금 계획은 좋은 균형을 갖추고 있어요.",
            "excessive": "열정이 느껴지는 계획이에요. 페이스를 조절해도 좋아요.",
        }
        message = f"{coach_lines.get(status, '')}\n\n{reason}\n\n{action}"

        if status == "adequate":
            st.success(message)
        elif status == "excessive":
            st.info(message)
        else:
            st.warning(message)

        st.session_state.plan_eval_shown = True
        st.session_state.pop("plan_eval_result", None)

    # 계획이 부족/과할 때만 수정 버튼 노출 (진단 출력 후에도 유지)
    if st.session_state.get("plan_eval_status") in ("insufficient", "excessive"):
        if st.button("계획 수정하러 가기"):
            st.session_state.onboarded = False
            st.session_state.plan_eval_shown = False
            st.session_state.pop("plan_eval_result", None)
            st.session_state.pop("plan_eval_status", None)
            st.rerun()

    # 탭 메뉴
    tab_action, tab_history = st.tabs(["🏋️ 오늘의 선택", "📊 기록 & 패턴"])

    with tab_action:
        with st.container(border=True):
            st.subheader("❓ 오늘 운동하셨나요?")

        if not is_exercise_day:
            st.info(f"📌 오늘은 운동 요일이 아니에요 ({today_weekday}). 하지만 운동하면 보너스입니다! 💪")

            did_ex_off_day = st.radio(
                "",
                ["선택", "했어요", "못 했어요"],
                key="did_off_day",
                horizontal=True
            )

            if did_ex_off_day == "했어요":
                st.success("🎁 보너스 운동! 멋져요!")
                st.session_state.last_check_date = today
                db.add_exercise_log(user_id, today.isoformat(), True)
            elif did_ex_off_day == "못 했어요":
                st.info("👍 괜찮아요. 내일 기대할게요!")
                st.session_state.last_check_date = today
                db.add_exercise_log(user_id, today.isoformat(), False)

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

                with st.container(border=True):
                    st.subheader("🧠 AI 핑계 분석")
                    st.write(f"**유형:** {excuse_type}")
                    st.progress(min(confidence, 1.0))
                    st.caption(f"판단 근거: {reason}")
                    st.caption(f"적용 정책: {policy}")

                verify_box = st.container(border=True)
                action_box = st.container(border=True)

                # WEATHER_CHECK
                def show_indoor_links(container=None):
                    if container is None:
                        st.info("실내에서라도 몸을 조금이라도 움직이면 건강에 큰 도움이 됩니다!")
                        st.markdown("**실내운동 참고 영상:**")
                        for v in INDOOR_EXERCISE_LINKS:
                            st.markdown(f"- [{v['title']}]({v['url']})")
                        return

                    with container:
                        st.info("실내에서라도 몸을 조금이라도 움직이면 건강에 큰 도움이 됩니다!")
                        st.markdown("**실내운동 참고 영상:**")
                        for v in INDOOR_EXERCISE_LINKS:
                            st.markdown(f"- [{v['title']}]({v['url']})")

                if policy == "WEATHER_CHECK":
                    weather_fact = get_weather_fact()
                    eval_result = evaluate_weather_excuse(excuse_text, weather_fact)

                    with verify_box:
                        st.subheader("🔍 데이터 검증 결과")
                        st.write(f"- 상태: {weather_fact['desc']}")
                        st.write(f"- 기온: {weather_fact['temp']}°C")

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

                        with verify_box:
                            st.error(message)
                        with action_box:
                            st.subheader("👉 AI의 제안")
                            st.success("외부 조건은 문제 없어 보여요. 10분만 가볍게 시작해볼까요?")

                        exc_row_id, insight_shown = persist_excuse_and_maybe_show_insight(
                            log_id,
                            excuse_text,
                            excuse_type,
                            confidence,
                            reason,
                            policy,
                            eval_result.get("reason"),
                            insight,
                            insight_shown,
                        )
                    else:
                        with verify_box:
                            st.info("오늘은 날씨가 운동하기에 부담스러웠을 수 있어요.")
                        with action_box:
                            st.subheader("👉 AI의 제안")
                            st.success("실내에서 가볍게 스트레칭부터 시작해볼까요?")
                            show_indoor_links(action_box)
                        exc_row_id, insight_shown = persist_excuse_and_maybe_show_insight(
                            log_id,
                            excuse_text,
                            excuse_type,
                            confidence,
                            reason,
                            policy,
                            eval_result.get("reason"),
                            insight,
                            insight_shown,
                        )

                # TIME_CHECK
                elif policy == "TIME_CHECK":
                    time_eval = evaluate_time_excuse(start_time_str, duration_min, excuse_text)

                    if time_eval["valid"] is None:
                        with verify_box:
                            st.subheader("🔍 데이터 검증 결과")
                            st.warning("⏰ 일정 확인이 불가능하거나 시간 관련 사유가 아닙니다.")
                        exc_row_id, insight_shown = persist_excuse_and_maybe_show_insight(
                            log_id,
                            excuse_text,
                            excuse_type,
                            confidence,
                            reason,
                            policy,
                            "inconclusive",
                            insight,
                            insight_shown,
                        )

                    elif time_eval["valid"]:
                        with verify_box:
                            st.subheader("🔍 데이터 검증 결과")
                            st.info("📅 캘린더에 일정이 있었네요. 바쁜 하루였겠어요.")
                        suggested_start = time_eval.get("suggested_start")
                        suggested_end = time_eval.get("suggested_end")
                        with action_box:
                            st.subheader("👉 AI의 제안")
                            if suggested_start and suggested_end:
                                st.success(
                                    f"오늘 {suggested_start} 이후에 {duration_min}분 정도 운동하는 건 어떨까요? (예: {suggested_start}~{suggested_end})"
                                )
                            else:
                                st.success("오늘 일정이 끝난 뒤, 같은 날 늦은 시간에 가볍게 움직여보는 건 어떨까요?")
                        exc_row_id, insight_shown = persist_excuse_and_maybe_show_insight(
                            log_id,
                            excuse_text,
                            excuse_type,
                            confidence,
                            reason,
                            policy,
                            time_eval.get("reason"),
                            insight,
                            insight_shown,
                        )

                    else:
                        with verify_box:
                            st.subheader("🔍 데이터 검증 결과")
                            st.error("❌ 운동 시간에 캘린더 일정이 없습니다.\n\n시간이 충분하셨을 것 같아요.")
                        with action_box:
                            st.subheader("👉 AI의 제안")
                            st.success("일정상 가능해 보여요. 10분만 가볍게 시작해볼까요?")
                        exc_row_id, insight_shown = persist_excuse_and_maybe_show_insight(
                            log_id,
                            excuse_text,
                            excuse_type,
                            confidence,
                            reason,
                            policy,
                            "claimed_time_but_no_conflict",
                            insight,
                            insight_shown,
                        )

                # LOW_INTENSITY -> 수면 데이터 기반 판단 (컨디션/체력/피곤함)
                elif policy == "LOW_INTENSITY":
                    sleep_eval = evaluate_sleep_excuse(user_id, excuse_text)
                    if sleep_eval["valid"] is None:
                        with verify_box:
                            st.subheader("🔍 데이터 검증 결과")
                            st.info("컨디션 관련 사유로 보이나, 수면 데이터가 부족해 판단할 수 없습니다.")
                        with action_box:
                            st.subheader("👉 AI의 제안")
                            st.success("오늘은 몸 상태를 우선해 휴식하거나, 저강도로 짧게 움직여보세요.")
                            show_indoor_links(action_box)
                        exc_row_id, insight_shown = persist_excuse_and_maybe_show_insight(
                            log_id,
                            excuse_text,
                            excuse_type,
                            confidence,
                            reason,
                            policy,
                            sleep_eval.get("reason"),
                            insight,
                            insight_shown,
                        )
                    elif sleep_eval["valid"]:
                        with verify_box:
                            st.subheader("🔍 데이터 검증 결과")
                            st.info(f"😴 최근 평균 수면이 낮습니다 ({sleep_eval.get('avg_hours'):.1f}시간).")
                        with action_box:
                            st.subheader("👉 AI의 제안")
                            st.success("오늘은 휴식을 택하거나, 저강도로 10분만 움직여보는 것도 좋아요.")
                            show_indoor_links(action_box)
                        exc_row_id, insight_shown = persist_excuse_and_maybe_show_insight(
                            log_id,
                            excuse_text,
                            excuse_type,
                            confidence,
                            reason,
                            policy,
                            sleep_eval.get("reason"),
                            insight,
                            insight_shown,
                        )
                    else:
                        with verify_box:
                            st.subheader("🔍 데이터 검증 결과")
                            st.info(f"수면 데이터 기준으로는 컨디션이 무리하지 않아도 되는 수준이에요 (평균 {sleep_eval.get('avg_hours'):.1f}시간).")
                        with action_box:
                            st.subheader("👉 AI의 제안")
                            st.success("가벼운 운동으로 기분 전환해볼까요?")
                        exc_row_id, insight_shown = persist_excuse_and_maybe_show_insight(
                            log_id,
                            excuse_text,
                            excuse_type,
                            confidence,
                            reason,
                            policy,
                            sleep_eval.get("reason"),
                            insight,
                            insight_shown,
                        )

                else:
                    with verify_box:
                        st.subheader("🔍 데이터 검증 결과")
                        st.info("기타 사유는 명확한 데이터 검증이 어려워 강한 개입 없이 사용자의 선택을 존중합니다.")
                    with action_box:
                        st.subheader("👉 AI의 제안")
                        st.info("오늘 컨디션과 일정에 맞게 스스로 선택해도 괜찮아요.")
                    exc_row_id, insight_shown = persist_excuse_and_maybe_show_insight(
                        log_id,
                        excuse_text,
                        excuse_type,
                        confidence,
                        reason,
                        policy,
                        "neutral",
                        insight,
                        insight_shown,
                    )

            # 이미 오늘 기록함
            if st.session_state.last_check_date == today:
                st.info("✅ 오늘 운동 여부는 이미 기록했어요.")

            else:
                # 아직 운동 시작 전: 미리 했는지 확인 가능
                if now < exercise_time_today:
                    st.info("⏳ 아직 운동 시작 전이에요. 미리 하셨나요?")
                    did_ex_before = st.radio(
                        "",
                        ["선택", "했어요", "못 했어요"],
                        key="did_pre",
                        horizontal=True
                    )

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
                        "",
                        ["선택", "했어요", "못 했어요"],
                        key="did_during",
                        horizontal=True
                    )

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
                        "",
                        ["선택", "했어요", "못 했어요"],
                        key="did_post",
                        horizontal=True
                    )

                    if did_ex_after == "했어요":
                        st.success("🔥 오늘 운동 완료! 기록을 남겨둘게요.")
                        st.session_state.last_check_date = today
                        db.add_exercise_log(user_id, today.isoformat(), True)
                    elif did_ex_after == "못 했어요":
                        excuse_post = st.text_input("❓ 왜 못 하셨나요?", key="excuse_post")
                        if excuse_post:
                            st.session_state.last_check_date = today
                            process_excuse_submission(excuse_post, user_id, today_start_time_str, today_duration)

    with tab_history:
        st.subheader("📊 나의 운동 패턴")
        st.caption("반복되는 핑계 유형을 기반으로 인사이트를 제공합니다")

        if sleeps:
            st.write("최근 수면 기록:")
            for r in sleeps:
                st.write(f"- {r[1]} → {r[2]} (src: {r[3]})")

        with st.expander("🛌 수면 데이터 / 데모 도구"):
            col_a, col_b = st.columns(2)
            with col_a:
                uploaded = st.file_uploader("수면 CSV 업로드 (start,end)", type=["csv"])
            if uploaded is not None:
                parsed = fit.parse_sleep_csv(uploaded)
                if parsed:
                    for s in parsed:
                        db.add_sleep_log(user_id, s["start"], s["end"], source="upload")
                    st.success(f"{len(parsed)}개의 수면 레코드를 저장했습니다.")
                else:
                    st.warning("CSV를 파싱할 수 없거나 형식이 맞지 않습니다.")
            with col_b:
                if st.button("샘플 수면 데이터 불러오기"):
                    sample = fit.generate_mock_sleep(7)
                    for s in sample:
                        db.add_sleep_log(user_id, s["start"], s["end"], source="mock")
                    st.success("샘플 수면데이터 7개가 저장되었습니다.")

                st.divider()
                st.write("테스트용으로 동일한 유형의 핑계를 과거 날짜에 생성합니다.")
                demo_excuse_type = st.selectbox("핑계 유형 선택", list(EXCUSE_POLICY.keys()), index=0)
                demo_count = st.number_input("몇 회 생성할까요?", min_value=1, max_value=20, value=3)
                demo_span = st.number_input("몇 일 범위에 분산할까요?", min_value=1, max_value=90, value=14)
                if st.button("데모: 동일 핑계 생성"):
                    created = insights.seed_repeated_excuses(user_id, demo_excuse_type, int(demo_count), int(demo_span))
                    st.success(f"{created}개의 시연용 핑계가 생성되었습니다.\n\n💡 팁: 이제 아래 '핑계 제출' 섹션에서 '{demo_excuse_type}' 핑계를 입력하면, DB에 기록된 반복 패턴을 확인할 수 있습니다.")

        st.divider()

        # 탭2: 캘린더 뷰
        from services.calendar_view import render_calendar_view
        user_name = st.session_state.user.get("name", "사용자")
        plan_days = plan.get("days", [])
        render_calendar_view(user_id, user_name, plan_days)
